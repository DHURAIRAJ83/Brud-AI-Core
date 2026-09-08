import json
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.main import create_app
from backend.models.auth import AdminCreate
from backend.models.model_release import ApprovalCreate
from backend.services.model_release_service import ModelReleaseService
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_instruction_tuning_api import _fixture_refs

_APPROVAL_PASSWORD = "reviewer-pass-123!"  # noqa: S105 -- test fixture only

pytestmark = pytest.mark.anyio

ADMIN = "00000000-0000-0000-0000-000000000001"
CONTEXT_LENGTH = 64


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


def _insert_evaluation_evidence(
    app: FastAPI, candidate_core_model_public_id: str, suffix: str
) -> str:
    settings = app.state.settings
    run_public_id = f"91000000-0000-0000-0000-00000000{suffix}0{suffix}0"
    with database_connection(settings.resolved_database_path) as connection:
        candidate_row = connection.execute(
            "SELECT id,tokenizer_version_id FROM core_model_versions WHERE public_id=?",
            (candidate_core_model_public_id,),
        ).fetchone()
        checkpoint_row = connection.execute(
            "SELECT id FROM pretraining_checkpoints ORDER BY id DESC LIMIT 1"
        ).fetchone()
        connection.execute(
            """INSERT OR IGNORE INTO model_evaluation_suites(public_id,name,version,status,
            created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            ("91000000-0000-0000-0000-000000000001", "phase15-suite", "v1", "active", ADMIN),
        )
        suite_id = connection.execute(
            "SELECT id FROM model_evaluation_suites WHERE public_id=?",
            ("91000000-0000-0000-0000-000000000001",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO model_evaluation_runs(public_id,model_evaluation_suite_id,
            candidate_core_model_version_id,checkpoint_id,tokenizer_version_id,status,
            fixture_count,completed_fixture_count,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                run_public_id, suite_id, candidate_row["id"], checkpoint_row["id"],
                candidate_row["tokenizer_version_id"], "completed", 6, 6, ADMIN,
            ),
        )
        run_id = connection.execute(
            "SELECT id FROM model_evaluation_runs WHERE public_id=?", (run_public_id,)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO model_chat_readiness_assessments(public_id,model_evaluation_run_id,
            status,created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                f"91000000-0000-0000-0000-00000000{suffix}1{suffix}1",
                run_id, "evaluation_passed_with_limits", ADMIN,
            ),
        )
        connection.execute(
            """INSERT INTO model_evaluation_manifests(public_id,model_evaluation_run_id,
            manifest_json,manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (
                f"91000000-0000-0000-0000-00000000{suffix}2{suffix}2",
                run_id, json.dumps({"run": run_public_id}), "c" * 64,
            ),
        )
        connection.commit()
    return run_public_id


def _append_blocking_readiness(app: FastAPI, run_public_id: str, suffix: str) -> None:
    """Simulates a later re-assessment discovering a blocking issue for an
    already-released model — append-only, so this is a NEW row, never an
    UPDATE of the original passing assessment."""

    settings = app.state.settings
    with database_connection(settings.resolved_database_path) as connection:
        run_id = connection.execute(
            "SELECT id FROM model_evaluation_runs WHERE public_id=?", (run_public_id,)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO model_chat_readiness_assessments(public_id,model_evaluation_run_id,
            status,created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                f"91000000-0000-0000-0000-00000000{suffix}9{suffix}9",
                run_id, "evaluation_blocked", ADMIN,
            ),
        )
        connection.commit()


async def _build_release(
    client, headers, app: FastAPI, refs: dict[str, str], *, label: str, notes: str, slug: str
) -> tuple[str, str, str]:
    """Drives the full Phase 14 candidate->release pipeline for
    ``refs['base_model']`` and returns (release_public_id, family_id,
    evaluation_run_public_id)."""

    run_public_id = _insert_evaluation_evidence(app, refs["base_model"], suffix=slug[-1])
    family = await client.post(
        "/api/admin/model-releases/families",
        headers=headers,
        json={"name": f"Family {slug}", "slug": f"family-{slug}"},
    )
    assert family.status_code == 200, family.text
    family_id = family.json()["public_id"]

    candidate = await client.post(
        "/api/admin/model-releases/candidates",
        headers=headers,
        json={
            "model_release_family_public_id": family_id,
            "core_model_version_public_id": refs["base_model"],
            "dataset_version_public_id": refs["dataset"],
            "model_evaluation_run_public_id": run_public_id,
            "label": label,
            "notes": notes,
        },
    )
    assert candidate.status_code == 200, candidate.text
    candidate_id = candidate.json()["public_id"]

    await client.post(
        f"/api/admin/model-releases/candidates/{candidate_id}/collect-artifacts", headers=headers
    )
    await client.post(
        f"/api/admin/model-releases/candidates/{candidate_id}/verify-artifacts", headers=headers
    )
    await client.post(
        f"/api/admin/model-releases/candidates/{candidate_id}/model-card", headers=headers
    )
    await client.post(
        f"/api/admin/model-releases/candidates/{candidate_id}/model-card/validate", headers=headers
    )
    eligibility = await client.post(
        f"/api/admin/model-releases/candidates/{candidate_id}/eligibility/assess", headers=headers
    )
    assert eligibility.json()["status"] in {"eligible", "eligible_with_warnings"}, eligibility.text
    await client.post(
        f"/api/admin/model-releases/candidates/{candidate_id}/manifest", headers=headers
    )
    # GOV-26/GOV-26b: releases require `resolve_minimum_distinct_approvers`
    # distinct admin_public_id approvers (currently 2, see
    # core_model/release/approval_policy.py), and GOV-33 forbids the
    # candidate's own creator (the `headers` admin above) from approving it.
    # Submit two real, distinct, non-creator approvals via the service layer
    # directly, matching the pattern used in
    # test_production_model_release_validation_activation.py and
    # test_mini_brain_release_pipeline_service.py.
    admin_repository = AdminRepository(app.state.settings.resolved_database_path)
    reviewer_1 = admin_repository.create_admin(
        AdminCreate(
            username=f"release-reviewer-1-{slug}",
            display_name="Release Reviewer 1",
            password=_APPROVAL_PASSWORD,
        )
    )
    reviewer_2 = admin_repository.create_admin(
        AdminCreate(
            username=f"release-reviewer-2-{slug}",
            display_name="Release Reviewer 2",
            password=_APPROVAL_PASSWORD,
        )
    )
    model_release_service = ModelReleaseService(
        ModelReleaseRepository(app.state.settings.resolved_database_path), app.state.settings
    )
    model_release_service.submit_approval(
        candidate_id,
        ApprovalCreate(role="release", decision="approve", comment="first reviewer"),
        reviewer_1.public_id,
    )
    model_release_service.submit_approval(
        candidate_id,
        ApprovalCreate(role="release", decision="approve", comment="second reviewer"),
        reviewer_2.public_id,
    )
    release = await client.post(
        "/api/admin/model-releases/releases",
        headers=headers,
        json={"candidate_public_id": candidate_id, "version": "0.1.0-alpha.1"},
    )
    assert release.status_code == 200, release.text
    assert release.json()["status"] == "released"
    return release.json()["public_id"], family_id, run_public_id


async def _create_profile(client, headers) -> str:
    created = await client.post(
        "/api/admin/inference-runtime/profiles",
        headers=headers,
        json={
            "name": "cpu-profile",
            "maximum_context_length": CONTEXT_LENGTH,
            "maximum_new_tokens": 32,
            "minimum_available_memory_bytes": 0,
            "minimum_available_disk_bytes": 0,
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["public_id"]


async def _create_instance(client, headers, profile_public_id: str) -> str:
    created = await client.post(
        "/api/admin/inference-runtime/instances",
        headers=headers,
        json={"runtime_profile_public_id": profile_public_id},
    )
    assert created.status_code == 200, created.text
    return created.json()["public_id"]


async def test_runtime_profile_invalid_limits_rejected(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/inference-runtime/profiles",
            headers=headers,
            json={
                "name": "bad",
                "maximum_context_length": 16,
                "maximum_new_tokens": 32,
                "minimum_available_memory_bytes": 0,
                "minimum_available_disk_bytes": 0,
            },
        )
        assert response.status_code >= 400
    finally:
        await client.aclose()


async def test_admin_diagnostic_and_chat_lab_full_lifecycle(api_app: FastAPI) -> None:
    """Path C: a synthetic, honestly-labeled, non-registry-fixture eligible
    release exercises real runtime mechanics end to end."""

    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        release_id, _family_id, _run_id = await _build_release(
            client,
            headers,
            api_app,
            refs,
            label="test_only_runtime_fixture",
            notes="not_chat_capable / not_public_assignable / registry mechanics only",
            slug="clean1",
        )
        profile_id = await _create_profile(client, headers)

        compatibility = await client.post(
            f"/api/admin/inference-runtime/releases/{release_id}/compatibility/assess",
            headers=headers,
            json={"runtime_profile_public_id": profile_id},
        )
        assert compatibility.status_code == 200, compatibility.text
        assert compatibility.json()["status"] == "compatible", compatibility.json()

        # Explicitly create+load+health-check an instance before the
        # assignment reuses it, so /instances/{id}/health-check is exercised
        # directly (not just implicitly through diagnostic-generate).
        instance_id = await _create_instance(client, headers, profile_id)
        load_result = await client.post(
            f"/api/admin/inference-runtime/instances/{instance_id}/load",
            headers=headers,
            json={"release_public_id": release_id},
        )
        assert load_result.status_code == 200, load_result.text
        assert load_result.json()["status"] == "ready", load_result.json()

        health = await client.post(
            f"/api/admin/inference-runtime/instances/{instance_id}/health-check",
            headers=headers,
        )
        assert health.status_code == 200, health.text
        assert health.json()["overall_status"] == "healthy", health.json()
        assert set(health.json()["checks"]) == {
            "runtime_process", "model_loaded", "tokenizer_loaded",
            "checkpoint_verified", "memory_available", "generation_smoke_test",
            "latency_within_limit", "special_token_output_safe",
        }

        assignment = await client.post(
            "/api/admin/inference-runtime/assignments",
            headers=headers,
            json={
                "scope": "admin_diagnostic",
                "release_public_id": release_id,
                "runtime_profile_public_id": profile_id,
            },
        )
        assert assignment.status_code == 200, assignment.text
        assignment_id = assignment.json()["public_id"]

        validated = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/validate", headers=headers
        )
        assert validated.status_code == 200, validated.text
        assert validated.json()["eligible"] is True, validated.json()

        approved = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/approve",
            headers=headers,
            json={"role": "release", "decision": "approve", "comment": "ok"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        activated = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/activate",
            headers=headers,
            json={},
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["activated"] is True

        diagnostic = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/diagnostic-generate",
            headers=headers,
            json={"prompt": "hello there"},
        )
        assert diagnostic.status_code == 200, diagnostic.text
        body = diagnostic.json()
        assert body["disclaimer"] == (
            "Admin-only diagnostic generation. This output is not from the public chatbot."
        )
        assert body["input_token_count"] > 0
        assert body["stop_reason"] in {
            "eos", "max_new_tokens", "context_limit", "timeout", "role_token_leakage",
        }

        versions = await client.get(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/versions", headers=headers
        )
        assert len(versions.json()["items"]) == 1

        manifest = await client.get(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/manifest", headers=headers
        )
        assert manifest.status_code == 200, manifest.text
        manifest_text = json.dumps(manifest.json())
        assert "/home/" not in manifest_text
        assert str(api_app.state.settings.resolved_pretraining_dir) not in manifest_text

        verify = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/manifest/verify",
            headers=headers,
        )
        assert verify.status_code == 200
        assert verify.json()["matches"] is True

        # --- admin chat lab, separate assignment/scope ---
        chat_lab_assignment = await client.post(
            "/api/admin/inference-runtime/assignments",
            headers=headers,
            json={
                "scope": "admin_chat_lab",
                "release_public_id": release_id,
                "runtime_profile_public_id": profile_id,
            },
        )
        assert chat_lab_assignment.status_code == 200, chat_lab_assignment.text
        chat_lab_id = chat_lab_assignment.json()["public_id"]
        await client.post(
            f"/api/admin/inference-runtime/assignments/{chat_lab_id}/validate", headers=headers
        )
        await client.post(
            f"/api/admin/inference-runtime/assignments/{chat_lab_id}/approve",
            headers=headers,
            json={"role": "release", "decision": "approve", "comment": "ok"},
        )
        await client.post(
            f"/api/admin/inference-runtime/assignments/{chat_lab_id}/activate",
            headers=headers,
            json={},
        )
        session = await client.post(
            f"/api/admin/inference-runtime/assignments/{chat_lab_id}/sessions",
            headers=headers,
            json={"max_turns": 3},
        )
        assert session.status_code == 200, session.text
        session_id = session.json()["public_id"]
        message = await client.post(
            f"/api/admin/inference-runtime/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "how are you"},
        )
        assert message.status_code == 200, message.text

        chat = await client.post("/api/chat", json={"message": "வணக்கம்"})
        assert "route_used" in chat.json()
    finally:
        await client.aclose()


async def test_registry_fixture_rejected_for_all_scopes_by_default(api_app: FastAPI) -> None:
    """Path B: registry_workflow_fixture / not_production_model release must
    be rejected for admin_diagnostic (by default), internal_canary, and
    public_chat."""

    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        release_id, _family_id, _run_id = await _build_release(
            client,
            headers,
            api_app,
            refs,
            label="registry_workflow_fixture",
            notes="not_production_model",
            slug="fixture2",
        )
        profile_id = await _create_profile(client, headers)

        for scope in ("admin_diagnostic", "internal_canary", "public_chat"):
            assignment = await client.post(
                "/api/admin/inference-runtime/assignments",
                headers=headers,
                json={
                    "scope": scope,
                    "release_public_id": release_id,
                    "runtime_profile_public_id": profile_id,
                },
            )
            assert assignment.status_code == 200, assignment.text
            assignment_id = assignment.json()["public_id"]
            validated = await client.post(
                f"/api/admin/inference-runtime/assignments/{assignment_id}/validate",
                headers=headers,
            )
            assert validated.status_code == 200, validated.text
            assert validated.json()["eligible"] is False, (scope, validated.json())
            assert any(
                "registry" in reason for reason in validated.json()["blocking_reasons"]
            ), validated.json()
    finally:
        await client.aclose()


async def test_evaluation_blocked_release_rejected_end_to_end(api_app: FastAPI) -> None:
    """Path A analogue: a release that was eligible at release time is
    rejected for assignment/load once a later append-only readiness
    assessment reveals a blocking issue — Phase 15 must re-derive
    evaluation status live, never trust a stale snapshot."""

    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        release_id, _family_id, run_id = await _build_release(
            client,
            headers,
            api_app,
            refs,
            label="test_only_runtime_fixture",
            notes="not_chat_capable",
            slug="blocked3",
        )
        _append_blocking_readiness(api_app, run_id, suffix="3")
        profile_id = await _create_profile(client, headers)

        compatibility = await client.post(
            f"/api/admin/inference-runtime/releases/{release_id}/compatibility/assess",
            headers=headers,
            json={"runtime_profile_public_id": profile_id},
        )
        assert compatibility.status_code == 200, compatibility.text
        assert compatibility.json()["status"] == "incompatible"

        assignment = await client.post(
            "/api/admin/inference-runtime/assignments",
            headers=headers,
            json={
                "scope": "admin_diagnostic",
                "release_public_id": release_id,
                "runtime_profile_public_id": profile_id,
            },
        )
        assignment_id = assignment.json()["public_id"]
        validated = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/validate", headers=headers
        )
        assert validated.json()["eligible"] is False
        assert any(
            "evaluation_blocked" in reason for reason in validated.json()["blocking_reasons"]
        ), validated.json()

        instance_id = await _create_instance(client, headers, profile_id)
        load = await client.post(
            f"/api/admin/inference-runtime/instances/{instance_id}/load",
            headers=headers,
            json={"release_public_id": release_id},
        )
        assert load.status_code >= 400
    finally:
        await client.aclose()


async def test_canary_and_rollback_workflow(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        release_a, _family_a, _run_a = await _build_release(
            client,
            headers,
            api_app,
            refs,
            label="test_only_runtime_fixture",
            notes="not_chat_capable",
            slug="canary4",
        )
        profile_id = await _create_profile(client, headers)

        # --- internal_canary mechanics ---
        canary_assignment = await client.post(
            "/api/admin/inference-runtime/assignments",
            headers=headers,
            json={
                "scope": "internal_canary",
                "release_public_id": release_a,
                "runtime_profile_public_id": profile_id,
                "context_policy": {"acknowledge_missing_human_review": True},
            },
        )
        assert canary_assignment.status_code == 200, canary_assignment.text
        canary_id = canary_assignment.json()["public_id"]
        canary_validated = await client.post(
            f"/api/admin/inference-runtime/assignments/{canary_id}/validate", headers=headers
        )
        assert canary_validated.json()["eligible"] is True, canary_validated.json()
        await client.post(
            f"/api/admin/inference-runtime/assignments/{canary_id}/approve",
            headers=headers,
            json={"role": "release", "decision": "approve", "comment": "ok"},
        )
        await client.post(
            f"/api/admin/inference-runtime/assignments/{canary_id}/activate",
            headers=headers,
            json={},
        )
        started = await client.post(
            f"/api/admin/inference-runtime/assignments/{canary_id}/canary/start",
            headers=headers,
            json={"percentage": 100, "max_request_count": 10},
        )
        assert started.status_code == 200, started.text
        executed = await client.post(
            f"/api/admin/inference-runtime/assignments/{canary_id}/canary/execute",
            headers=headers,
            json={"fixture_prompts": [f"prompt {i}" for i in range(5)]},
        )
        assert executed.status_code == 200, executed.text
        metrics = executed.json()["metrics"]
        assert metrics["total_requests"] == 5
        assert metrics["sample_size_small"] is True
        stopped = await client.post(
            f"/api/admin/inference-runtime/assignments/{canary_id}/canary/stop",
            headers=headers,
            json={"reason": "manual_test_stop"},
        )
        assert stopped.status_code == 200, stopped.text

        # --- rollback drill: two versions of one admin_diagnostic assignment ---
        release_b, _family_b, _run_b = await _build_release(
            client,
            headers,
            api_app,
            refs,
            label="test_only_runtime_fixture",
            notes="not_chat_capable",
            slug="canary5",
        )
        rollback_assignment = await client.post(
            "/api/admin/inference-runtime/assignments",
            headers=headers,
            json={
                "scope": "admin_diagnostic",
                "release_public_id": release_a,
                "runtime_profile_public_id": profile_id,
            },
        )
        assignment_id = rollback_assignment.json()["public_id"]
        await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/validate", headers=headers
        )
        await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/approve",
            headers=headers,
            json={"role": "release", "decision": "approve", "comment": "v1"},
        )
        await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/activate",
            headers=headers,
            json={},
        )
        versions_after_v1 = await client.get(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/versions", headers=headers
        )
        version_1_public_id = versions_after_v1.json()["items"][0]["public_id"]

        patched = await client.patch(
            f"/api/admin/inference-runtime/assignments/{assignment_id}",
            headers=headers,
            json={"release_public_id": release_b},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["status"] == "draft"
        await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/validate", headers=headers
        )
        await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/approve",
            headers=headers,
            json={"role": "release", "decision": "approve", "comment": "v2"},
        )
        activated_v2 = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/activate",
            headers=headers,
            json={},
        )
        assert activated_v2.json()["activated"] is True
        assert activated_v2.json()["assignment"]["release_public_id"] == release_b

        preview = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/rollback/preview",
            headers=headers,
            json={"target_version_public_id": version_1_public_id},
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["eligible"] is True

        execute = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/rollback/execute",
            headers=headers,
            json={"target_version_public_id": version_1_public_id},
        )
        assert execute.status_code == 200, execute.text
        assert execute.json()["rolled_back"] is True
        assert execute.json()["current_version_public_id"] == version_1_public_id
        assert execute.json()["assignment"]["release_public_id"] == release_a
        assert execute.json()["assignment"]["status"] == "active"

        chat = await client.post("/api/chat", json={"message": "வணக்கம்"})
        assert "route_used" in chat.json()
    finally:
        await client.aclose()


async def test_public_chat_activation_blocked_by_default(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        release_id, _family_id, _run_id = await _build_release(
            client,
            headers,
            api_app,
            refs,
            label="test_only_runtime_fixture",
            notes="not_chat_capable",
            slug="public6",
        )
        profile_id = await _create_profile(client, headers)
        assignment = await client.post(
            "/api/admin/inference-runtime/assignments",
            headers=headers,
            json={
                "scope": "public_chat",
                "release_public_id": release_id,
                "runtime_profile_public_id": profile_id,
            },
        )
        assignment_id = assignment.json()["public_id"]
        validated = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/validate", headers=headers
        )
        # public_chat requires all four approval roles; even once fully approved,
        # (in this minimal fixture) canary/diagnostics/rollback-target evidence is
        # still missing, so activation must still be rejected below.
        if validated.json()["eligible"]:
            for role in ("technical", "evaluation", "security", "release"):
                approved = await client.post(
                    f"/api/admin/inference-runtime/assignments/{assignment_id}/approve",
                    headers=headers,
                    json={"role": role, "decision": "approve", "comment": "ok"},
                )
                assert approved.status_code == 200, approved.text
        activated = await client.post(
            f"/api/admin/inference-runtime/assignments/{assignment_id}/activate",
            headers=headers,
            json={"explicit_activation_confirmed": True},
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["activated"] is False
        assert activated.json()["rejection_reasons"]

        chat = await client.post("/api/chat", json={"message": "வணக்கம்"})
        assert "route_used" in chat.json()
    finally:
        await client.aclose()
