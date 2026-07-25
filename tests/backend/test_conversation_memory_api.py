from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_inference_runtime_api import (
    _build_release,
    _create_instance,
    _create_profile,
)
from tests.backend.test_instruction_tuning_api import _fixture_refs

pytestmark = pytest.mark.anyio

CM = "/api/admin/conversation-memory"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports",
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports",
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        release_artifact_dir=tmp_path / "release_artifacts",
        release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def _create_active_policy(
    client, headers, *, mode: str = "consented_memory", allow_long_term=True
):
    created = await client.post(
        f"{CM}/policies",
        headers=headers,
        json={
            "name": f"policy-{mode}",
            "default_session_mode": mode,
            "allow_long_term_memory": allow_long_term,
        },
    )
    assert created.status_code == 200, created.text
    policy_id = created.json()["public_id"]
    await client.post(f"{CM}/policies/{policy_id}/validate", headers=headers)
    activated = await client.post(f"{CM}/policies/{policy_id}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    return policy_id


async def _grant_consent(client, headers, *, policy_id, participant, purpose):
    consent = await client.post(
        f"{CM}/consents",
        headers=headers,
        json={
            "participant_scope_key": participant,
            "memory_policy_public_id": policy_id,
            "purpose": purpose,
        },
    )
    assert consent.status_code == 200, consent.text
    return consent.json()["public_id"]


async def _active_memory_profile(client, headers):
    created = await client.post(
        f"{CM}/retrieval-profiles", headers=headers, json={"name": "profile"}
    )
    assert created.status_code == 200, created.text
    profile_id = created.json()["public_id"]
    await client.post(f"{CM}/retrieval-profiles/{profile_id}/validate", headers=headers)
    activated = await client.post(f"{CM}/retrieval-profiles/{profile_id}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    return profile_id


async def _build_eligible_assignment(client, headers, api_app: FastAPI, *, slug: str) -> str:
    refs = _fixture_refs(api_app)
    release_id, _family_id, _run_id = await _build_release(
        client, headers, api_app, refs,
        label="test_only_runtime_fixture", notes="not_chat_capable", slug=slug,
    )
    profile_id = await _create_profile(client, headers)
    instance_id = await _create_instance(client, headers, profile_id)
    loaded = await client.post(
        f"/api/admin/inference-runtime/instances/{instance_id}/load",
        headers=headers, json={"release_public_id": release_id},
    )
    assert loaded.status_code == 200, loaded.text

    assignment = await client.post(
        "/api/admin/inference-runtime/assignments",
        headers=headers,
        json={
            "scope": "admin_diagnostic", "release_public_id": release_id,
            "runtime_profile_public_id": profile_id,
        },
    )
    assert assignment.status_code == 200, assignment.text
    assignment_id = assignment.json()["public_id"]
    validate_url = f"/api/admin/inference-runtime/assignments/{assignment_id}/validate"
    await client.post(validate_url, headers=headers)
    await client.post(
        f"/api/admin/inference-runtime/assignments/{assignment_id}/approve",
        headers=headers, json={"role": "release", "decision": "approve", "comment": "test"},
    )
    activated = await client.post(
        f"/api/admin/inference-runtime/assignments/{assignment_id}/activate",
        headers=headers, json={},
    )
    assert activated.status_code == 200, activated.text
    return assignment_id


async def test_mutations_require_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{CM}/policies", json={"name": "no-csrf"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_policy_lifecycle_and_invalid_limits_rejected(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        invalid = await client.post(
            f"{CM}/policies",
            headers=headers,
            json={
                "name": "bad", "default_session_mode": "consented_memory",
                "maximum_session_turns": 0,
            },
        )
        assert invalid.status_code >= 400

        policy_id = await _create_active_policy(client, headers, mode="private_no_persist")
        policy = await client.get(f"{CM}/policies/{policy_id}", headers=headers)
        assert policy.json()["lifecycle_status"] == "active"
    finally:
        await client.aclose()


async def test_path_a_private_no_persist_session(api_app: FastAPI) -> None:
    """Path A: private_no_persist -- no raw turn content, no summary, no
    long-term memory is ever persisted."""

    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _create_active_policy(
            client, headers, mode="private_no_persist", allow_long_term=False
        )
        assignment_id = await _build_eligible_assignment(client, headers, api_app, slug="priv1")
        created = await client.post(
            f"{CM}/sessions",
            headers=headers,
            json={
                "session_mode": "private_no_persist",
                "memory_policy_public_id": policy_id,
                "participant_scope_key": "admin:private1",
                "model_assignment_public_id": assignment_id,
            },
        )
        assert created.status_code == 200, created.text
        session_id = created.json()["public_id"]

        message = await client.post(
            f"{CM}/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "hello, how are you"},
        )
        assert message.status_code == 200, message.text

        turns = await client.get(f"{CM}/sessions/{session_id}/turns", headers=headers)
        assert turns.status_code == 200
        for turn in turns.json()["items"]:
            assert turn.get("stored_content") is None

        summaries = await client.get(f"{CM}/sessions/{session_id}/summaries", headers=headers)
        assert summaries.json()["items"] == []

        memory_items = await client.get(
            f"{CM}/memory-items", headers=headers,
            params={"participant_scope_key": "admin:private1"},
        )
        assert memory_items.json()["items"] == []

        chat = await client.post("/api/chat", json={"message": "வணக்கம்", "language": "auto"})
        assert chat.json()["model"] == "placeholder"
    finally:
        await client.aclose()


async def test_path_b_session_only_memory_and_summary(api_app: FastAPI) -> None:
    """Path B: bounded conversation, latest turn preserved, summary
    created and validated, no long-term memory created."""

    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _create_active_policy(
            client, headers, mode="session_memory", allow_long_term=False
        )
        assignment_id = await _build_eligible_assignment(client, headers, api_app, slug="sessb1")
        created = await client.post(
            f"{CM}/sessions",
            headers=headers,
            json={
                "session_mode": "session_memory",
                "memory_policy_public_id": policy_id,
                "participant_scope_key": "admin:sessionb1",
                "model_assignment_public_id": assignment_id,
            },
        )
        session_id = created.json()["public_id"]

        for text in ["எனக்கு பதில் தமிழில் வேண்டும்", "தமிழ் பண்டிகைகள் பற்றி சொல்லுங்கள்"]:
            result = await client.post(
                f"{CM}/sessions/{session_id}/messages", headers=headers, json={"message": text}
            )
            assert result.status_code == 200, result.text

        turns = await client.get(f"{CM}/sessions/{session_id}/turns", headers=headers)
        assert len(turns.json()["items"]) >= 2
        last_turn = turns.json()["items"][-1]
        assert last_turn["stored_content"] is not None

        summary = await client.post(
            f"{CM}/sessions/{session_id}/summaries", headers=headers, json={}
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["status"] in {"validated", "rejected"}

        memory_items = await client.get(
            f"{CM}/memory-items", headers=headers,
            params={"participant_scope_key": "admin:sessionb1"},
        )
        assert memory_items.json()["items"] == []
    finally:
        await client.aclose()


async def test_path_c_consent_and_confirmed_memory(api_app: FastAPI) -> None:
    """Path C: explicit consent + memory proposed + confirmed + active,
    retrievable in a future retrieval call."""

    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _create_active_policy(client, headers, mode="consented_memory")

        consent = await client.post(
            f"{CM}/consents",
            headers=headers,
            json={
                "participant_scope_key": "admin:consentc1",
                "memory_policy_public_id": policy_id,
                "purpose": "language_preference",
            },
        )
        assert consent.status_code == 200, consent.text
        assert consent.json()["status"] == "active"

        item = await client.post(
            f"{CM}/memory-items",
            headers=headers,
            json={
                "participant_scope_key": "admin:consentc1",
                "category": "language_preference",
                "purpose": "language_preference",
                "creation_source": "explicit_user_request",
                "confidence_type": "user_confirmed",
                "display_value": "Tamil",
                "consent_public_id": consent.json()["public_id"],
            },
        )
        assert item.status_code == 200, item.text
        assert item.json()["status"] == "active"

        profile_id = await _active_memory_profile(client, headers)
        retrieved = await client.post(
            f"{CM}/retrieve",
            headers=headers,
            json={
                "retrieval_profile_public_id": profile_id,
                "participant_scope_key": "admin:consentc1",
                "query": "language preference",
            },
        )
        assert retrieved.status_code == 200, retrieved.text
        assert len(retrieved.json()["results"]) == 1
    finally:
        await client.aclose()


async def test_path_d_assistant_inferred_memory_requires_confirmation(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _create_active_policy(client, headers, mode="consented_memory")
        item = await client.post(
            f"{CM}/memory-items",
            headers=headers,
            json={
                "participant_scope_key": "admin:inferredd1",
                "category": "learning_goal",
                "purpose": "learning_goal",
                "creation_source": "assistant_proposed",
                "confidence_type": "assistant_inferred",
                "display_value": "wants to learn Tamil grammar",
            },
        )
        assert item.status_code == 200, item.text
        assert item.json()["status"] == "awaiting_confirmation"

        profile_id = await _active_memory_profile(client, headers)
        retrieved = await client.post(
            f"{CM}/retrieve",
            headers=headers,
            json={
                "retrieval_profile_public_id": profile_id,
                "participant_scope_key": "admin:inferredd1",
                "query": "learn Tamil grammar",
            },
        )
        assert retrieved.json()["results"] == []

        confirmed = await client.post(
            f"{CM}/memory-items/{item.json()['public_id']}/confirm", headers=headers
        )
        assert confirmed.json()["status"] == "active"
        retrieved_after = await client.post(
            f"{CM}/retrieve",
            headers=headers,
            json={
                "retrieval_profile_public_id": profile_id,
                "participant_scope_key": "admin:inferredd1",
                "query": "learn Tamil grammar",
            },
        )
        assert len(retrieved_after.json()["results"]) == 1
    finally:
        await client.aclose()


async def test_path_e_sensitive_memory_rejected(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _create_active_policy(client, headers, mode="consented_memory")
        item = await client.post(
            f"{CM}/memory-items",
            headers=headers,
            json={
                "participant_scope_key": "admin:sensitivee1",
                "category": "user_confirmed_fact",
                "purpose": "user_confirmed_profile",
                "creation_source": "explicit_user_request",
                "confidence_type": "user_confirmed",
                "display_value": "my password: hunter2",
            },
        )
        assert item.status_code >= 400
        assert "hunter2" not in item.text

        memory_items = await client.get(
            f"{CM}/memory-items", headers=headers,
            params={"participant_scope_key": "admin:sensitivee1"},
        )
        assert memory_items.json()["items"] == []
    finally:
        await client.aclose()


async def test_path_f_correction_creates_new_version(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _create_active_policy(client, headers, mode="consented_memory")
        consent_id = await _grant_consent(
            client, headers, policy_id=policy_id, participant="admin:correctf1",
            purpose="language_preference",
        )
        item = await client.post(
            f"{CM}/memory-items",
            headers=headers,
            json={
                "participant_scope_key": "admin:correctf1",
                "category": "language_preference",
                "purpose": "language_preference",
                "creation_source": "explicit_user_request",
                "confidence_type": "user_confirmed",
                "display_value": "Tamil",
                "consent_public_id": consent_id,
            },
        )
        assert item.status_code == 200, item.text
        assert item.json()["status"] == "active"
        item_id = item.json()["public_id"]
        corrected = await client.post(
            f"{CM}/memory-items/{item_id}/correct",
            headers=headers,
            json={"display_value": "Tanglish", "change_reason": "changed mind"},
        )
        assert corrected.status_code == 200, corrected.text

        versions = await client.get(f"{CM}/memory-items/{item_id}/versions", headers=headers)
        assert len(versions.json()["items"]) == 2
        assert versions.json()["items"][0]["display_value"] == "Tamil"
        assert versions.json()["items"][1]["display_value"] == "Tanglish"

        profile_id = await _active_memory_profile(client, headers)
        retrieved = await client.post(
            f"{CM}/retrieve",
            headers=headers,
            json={
                "retrieval_profile_public_id": profile_id,
                "participant_scope_key": "admin:correctf1",
                "query": "tanglish",
            },
        )
        assert len(retrieved.json()["results"]) == 1
    finally:
        await client.aclose()


async def test_path_g_deletion_excludes_from_retrieval(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _create_active_policy(client, headers, mode="consented_memory")
        consent_id = await _grant_consent(
            client, headers, policy_id=policy_id, participant="admin:deleteg1",
            purpose="language_preference",
        )
        item = await client.post(
            f"{CM}/memory-items",
            headers=headers,
            json={
                "participant_scope_key": "admin:deleteg1",
                "category": "language_preference",
                "purpose": "language_preference",
                "creation_source": "explicit_user_request",
                "confidence_type": "user_confirmed",
                "display_value": "Tamil",
                "consent_public_id": consent_id,
            },
        )
        assert item.status_code == 200, item.text
        assert item.json()["status"] == "active"
        item_id = item.json()["public_id"]
        profile_id = await _active_memory_profile(client, headers)

        before = await client.post(
            f"{CM}/retrieve",
            headers=headers,
            json={
                "retrieval_profile_public_id": profile_id,
                "participant_scope_key": "admin:deleteg1",
                "query": "tamil",
            },
        )
        assert len(before.json()["results"]) == 1

        deleted = await client.post(f"{CM}/memory-items/{item_id}/delete", headers=headers)
        assert deleted.json()["status"] == "deleted"

        after = await client.post(
            f"{CM}/retrieve",
            headers=headers,
            json={
                "retrieval_profile_public_id": profile_id,
                "participant_scope_key": "admin:deleteg1",
                "query": "tamil",
            },
        )
        assert after.json()["results"] == []
    finally:
        await client.aclose()


async def test_path_h_cross_participant_isolation(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _create_active_policy(client, headers, mode="consented_memory")
        consent_id = await _grant_consent(
            client, headers, policy_id=policy_id, participant="admin:isoA",
            purpose="language_preference",
        )
        created = await client.post(
            f"{CM}/memory-items",
            headers=headers,
            json={
                "participant_scope_key": "admin:isoA",
                "category": "language_preference",
                "purpose": "language_preference",
                "creation_source": "explicit_user_request",
                "confidence_type": "user_confirmed",
                "display_value": "Tamil",
                "consent_public_id": consent_id,
            },
        )
        assert created.status_code == 200, created.text
        assert created.json()["status"] == "active"
        profile_id = await _active_memory_profile(client, headers)

        own = await client.post(
            f"{CM}/retrieve",
            headers=headers,
            json={
                "retrieval_profile_public_id": profile_id,
                "participant_scope_key": "admin:isoA",
                "query": "tamil",
            },
        )
        assert len(own.json()["results"]) == 1

        other = await client.post(
            f"{CM}/retrieve",
            headers=headers,
            json={
                "retrieval_profile_public_id": profile_id,
                "participant_scope_key": "admin:isoB",
                "query": "tamil",
            },
        )
        assert other.json()["results"] == []
    finally:
        await client.aclose()


async def test_orchestration_lookups_and_public_chat_unchanged(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _create_active_policy(client, headers, mode="session_memory")
        assignment_id = await _build_eligible_assignment(client, headers, api_app, slug="orch1")
        created = await client.post(
            f"{CM}/sessions",
            headers=headers,
            json={
                "session_mode": "session_memory",
                "memory_policy_public_id": policy_id,
                "participant_scope_key": "admin:orchestration1",
                "model_assignment_public_id": assignment_id,
            },
        )
        session_id = created.json()["public_id"]

        message = await client.post(
            f"{CM}/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "hello there"},
        )
        assert message.status_code == 200, message.text
        run_id = message.json()["orchestration_run"]["public_id"]

        run = await client.get(f"{CM}/orchestration-runs/{run_id}", headers=headers)
        assert run.status_code == 200
        context = await client.get(f"{CM}/orchestration-runs/{run_id}/context", headers=headers)
        assert context.status_code == 200
        response = await client.get(f"{CM}/orchestration-runs/{run_id}/response", headers=headers)
        assert response.status_code == 200
        issues = await client.get(f"{CM}/orchestration-runs/{run_id}/issues", headers=headers)
        assert issues.status_code == 200

        closed = await client.post(f"{CM}/sessions/{session_id}/close", headers=headers)
        assert closed.json()["status"] == "closed"
        rejected = await client.post(
            f"{CM}/sessions/{session_id}/messages", headers=headers, json={"message": "again"}
        )
        assert rejected.status_code >= 400

        chat = await client.post("/api/chat", json={"message": "வணக்கம்", "language": "auto"})
        assert chat.json()["model"] == "placeholder"
    finally:
        await client.aclose()


async def test_evaluation_suite_and_manifest(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _create_active_policy(client, headers, mode="consented_memory")
        consent_id = await _grant_consent(
            client, headers, policy_id=policy_id, participant="admin:evalp1",
            purpose="language_preference",
        )
        item = await client.post(
            f"{CM}/memory-items",
            headers=headers,
            json={
                "participant_scope_key": "admin:evalp1",
                "category": "language_preference",
                "purpose": "language_preference",
                "creation_source": "explicit_user_request",
                "confidence_type": "user_confirmed",
                "display_value": "Tamil",
                "consent_public_id": consent_id,
            },
        )
        assert item.status_code == 200, item.text
        assert item.json()["status"] == "active"
        memory_id = item.json()["public_id"]
        profile_id = await _active_memory_profile(client, headers)

        suite = await client.post(
            f"{CM}/evaluation-suites", headers=headers, json={"name": "s", "version": "v1"}
        )
        assert suite.status_code == 200, suite.text
        suite_id = suite.json()["public_id"]

        fixture = await client.post(
            f"{CM}/evaluation-suites/{suite_id}/fixtures",
            headers=headers,
            json={
                "participant_scope_key": "admin:evalp1",
                "query": "tamil",
                "expected_retrieved_memory_ids": [memory_id],
            },
        )
        assert fixture.status_code == 200, fixture.text

        run = await client.post(
            f"{CM}/evaluation-suites/{suite_id}/runs",
            headers=headers,
            json={"retrieval_profile_public_id": profile_id},
        )
        run_id = run.json()["public_id"]
        executed = await client.post(f"{CM}/evaluation-runs/{run_id}/execute", headers=headers)
        assert executed.status_code == 200, executed.text
        assert executed.json()["status"] == "completed"

        metrics = await client.get(f"{CM}/evaluation-runs/{run_id}/metrics", headers=headers)
        metric_names = {m["metric_name"]: m["metric_value"] for m in metrics.json()["items"]}
        assert metric_names["recall_at_k"] == 1.0

        policies = await client.get(f"{CM}/policies", headers=headers)
        policy_id = policies.json()["items"][0]["public_id"]
        manifest = await client.post(f"{CM}/policies/{policy_id}/manifest", headers=headers)
        assert manifest.status_code == 200, manifest.text
        manifest_text = str(manifest.json())
        assert "/home/" not in manifest_text

        verify = await client.get(f"{CM}/policies/{policy_id}/manifest/verify", headers=headers)
        assert verify.status_code == 200
        assert verify.json()["matches"] is True
    finally:
        await client.aclose()
