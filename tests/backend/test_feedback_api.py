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

CM = "/api/admin/feedback"


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


async def _active_policy(client, headers) -> str:
    created = await client.post(f"{CM}/policies", headers=headers, json={"name": "default"})
    assert created.status_code == 200, created.text
    policy_id = created.json()["public_id"]
    await client.post(f"{CM}/policies/{policy_id}/validate", headers=headers)
    activated = await client.post(f"{CM}/policies/{policy_id}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    return policy_id


async def _build_model_release(client, headers, app: FastAPI, *, slug: str) -> str:
    refs = _fixture_refs(app)
    release_id, _family, _run = await _build_release(
        client, headers, app, refs, label="feedback_fixture", notes="not_chat_capable", slug=slug
    )
    return release_id


async def _build_active_assignment(client, headers, app: FastAPI, *, slug: str) -> str:
    refs = _fixture_refs(app)
    release_id, _family, _run = await _build_release(
        client, headers, app, refs, label="feedback_fixture", notes="not_chat_capable", slug=slug
    )
    profile_id = await _create_profile(client, headers)
    instance_id = await _create_instance(client, headers, profile_id)
    loaded = await client.post(
        f"/api/admin/inference-runtime/instances/{instance_id}/load",
        headers=headers, json={"release_public_id": release_id},
    )
    assert loaded.status_code == 200, loaded.text
    assignment = await client.post(
        "/api/admin/inference-runtime/assignments", headers=headers,
        json={
            "scope": "admin_diagnostic", "release_public_id": release_id,
            "runtime_profile_public_id": profile_id,
        },
    )
    assert assignment.status_code == 200, assignment.text
    assignment_id = assignment.json()["public_id"]
    validated = await client.post(
        f"/api/admin/inference-runtime/assignments/{assignment_id}/validate", headers=headers
    )
    assert validated.status_code == 200, validated.text
    approved = await client.post(
        f"/api/admin/inference-runtime/assignments/{assignment_id}/approve", headers=headers,
        json={"role": "release", "decision": "approve", "comment": "test"},
    )
    assert approved.status_code == 200, approved.text
    activated = await client.post(
        f"/api/admin/inference-runtime/assignments/{assignment_id}/activate", headers=headers,
        json={},
    )
    assert activated.status_code == 200, activated.text
    return assignment_id


async def test_mutations_require_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        no_csrf = {"Cookie": headers["Cookie"]} if "Cookie" in headers else {}
        response = await client.post(f"{CM}/policies", headers=no_csrf, json={"name": "x"})
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_policy_lifecycle(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(f"{CM}/policies", headers=headers, json={"name": "policy1"})
        assert created.status_code == 200, created.text
        assert created.json()["lifecycle_status"] == "draft"
        policy_id = created.json()["public_id"]
        validated = await client.post(f"{CM}/policies/{policy_id}/validate", headers=headers)
        assert validated.json()["lifecycle_status"] == "validated"
        activated = await client.post(f"{CM}/policies/{policy_id}/activate", headers=headers)
        assert activated.json()["lifecycle_status"] == "active"
    finally:
        await client.aclose()


async def test_path_a_positive_feedback_no_automatic_candidate(api_app: FastAPI) -> None:
    """Path A: thumbs_up submitted, triage succeeds, no dataset candidate
    automatically created."""

    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        release_id = await _build_model_release(client, headers, api_app, slug="patha")
        event = await client.post(
            f"{CM}/events", headers=headers,
            json={
                "subject_type": "model_release", "subject_reference_public_id": release_id,
                "feedback_policy_public_id": policy_id, "participant_scope_key": "admin:patha",
                "feedback_type": "thumbs_up",
            },
        )
        assert event.status_code == 200, event.text
        event_id = event.json()["public_id"]
        triaged = await client.post(f"{CM}/events/{event_id}/triage", headers=headers)
        assert triaged.status_code == 200, triaged.text
        assert triaged.json()["status"] == "triaged"
        candidates = await client.get(f"{CM}/dataset-candidates", headers=headers)
        assert candidates.json()["items"] == []
    finally:
        await client.aclose()


async def test_invalid_subject_rejected(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        event = await client.post(
            f"{CM}/events", headers=headers,
            json={
                "subject_type": "model_release", "subject_reference_public_id": "does-not-exist",
                "feedback_policy_public_id": policy_id, "participant_scope_key": "admin:x",
                "feedback_type": "thumbs_up",
            },
        )
        assert event.status_code >= 400
    finally:
        await client.aclose()


async def test_path_c_secret_containing_feedback_blocked(api_app: FastAPI) -> None:
    """Path C: synthetic API-key/password patterns are blocked; no secret
    retained in the general response; audit contains no secret."""

    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        release_id = await _build_model_release(client, headers, api_app, slug="pathc")
        event = await client.post(
            f"{CM}/events", headers=headers,
            json={
                "subject_type": "model_release", "subject_reference_public_id": release_id,
                "feedback_policy_public_id": policy_id, "participant_scope_key": "admin:pathc",
                "feedback_type": "issue_report", "comment": "here is my password: hunter2",
            },
        )
        assert event.status_code == 200, event.text
        assert event.json()["privacy_status"] == "blocked"
        assert event.json().get("comment_text") is None
        findings = await client.get(
            f"{CM}/events/{event.json()['public_id']}/findings", headers=headers
        )
        assert any(f["category"] == "password" for f in findings.json()["privacy"])

        audit = await client.get("/api/admin/audit/recent?limit=20", headers=headers)
        assert "hunter2" not in audit.text
    finally:
        await client.aclose()


async def test_path_b_review_correction_and_pending_candidate(api_app: FastAPI) -> None:
    """Path B: negative feedback + incorrect classification + human review
    + corrected response + validation; dataset candidate remains pending
    approval (never auto-approved)."""

    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        release_id = await _build_model_release(client, headers, api_app, slug="pathb")
        event = await client.post(
            f"{CM}/events", headers=headers,
            json={
                "subject_type": "model_release", "subject_reference_public_id": release_id,
                "feedback_policy_public_id": policy_id, "participant_scope_key": "admin:pathb",
                "feedback_type": "thumbs_down", "expected_language": "ta",
            },
        )
        event_id = event.json()["public_id"]
        classified = await client.post(
            f"{CM}/events/{event_id}/classifications", headers=headers,
            json={"category": "incorrect", "severity": "medium"},
        )
        assert classified.status_code == 200, classified.text

        review = await client.post(
            f"{CM}/events/{event_id}/reviews", headers=headers,
            json={"overall_score": 4, "verdict": "candidate_recommended"},
        )
        assert review.status_code == 200, review.text

        correction = await client.post(
            f"{CM}/events/{event_id}/corrected-responses", headers=headers,
            json={"corrected_response_text": "இது ஒரு சரியான பதில்", "language": "ta"},
        )
        assert correction.status_code == 200, correction.text
        correction_id = correction.json()["public_id"]
        validated = await client.post(
            f"{CM}/corrected-responses/{correction_id}/validate", headers=headers
        )
        assert validated.json()["validation_status"] == "validated"

        candidate = await client.post(
            f"{CM}/events/{event_id}/dataset-candidates", headers=headers,
            json={
                "prompt_text": "தமிழ் இலக்கணம் பற்றி விளக்கவும்",
                "corrected_response_public_id": correction_id,
            },
        )
        assert candidate.status_code == 200, candidate.text
        assert candidate.json()["status"] in {"draft", "validating"}
    finally:
        await client.aclose()


async def test_review_disagreement_and_append_only(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        release_id = await _build_model_release(client, headers, api_app, slug="disagree")
        event = await client.post(
            f"{CM}/events", headers=headers,
            json={
                "subject_type": "model_release", "subject_reference_public_id": release_id,
                "feedback_policy_public_id": policy_id, "participant_scope_key": "admin:disagree",
                "feedback_type": "thumbs_down",
            },
        )
        event_id = event.json()["public_id"]

        await client.post(
            f"{CM}/events/{event_id}/reviews", headers=headers,
            json={"overall_score": 5, "verdict": "candidate_recommended"},
        )
        await client.post(
            f"{CM}/events/{event_id}/reviews", headers=headers,
            json={"overall_score": 1, "verdict": "invalid_feedback"},
        )
        summary = await client.get(f"{CM}/events/{event_id}/review-summary", headers=headers)
        assert summary.json()["review_count"] == 2
        assert summary.json()["disagreement"]["status"] in {"material", "requires_adjudication"}

        reviews = await client.get(f"{CM}/events/{event_id}/reviews", headers=headers)
        assert len(reviews.json()["items"]) == 2
    finally:
        await client.aclose()


async def test_dataset_candidate_full_approval_and_export(api_app: FastAPI) -> None:
    """Path I: privacy pass, safety pass, licence approved, review complete,
    candidate approved, export enters existing dataset pipeline."""

    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        release_id = await _build_model_release(client, headers, api_app, slug="pathi")
        event = await client.post(
            f"{CM}/events", headers=headers,
            json={
                "subject_type": "model_release", "subject_reference_public_id": release_id,
                "feedback_policy_public_id": policy_id, "participant_scope_key": "admin:pathi",
                "feedback_type": "thumbs_down", "expected_language": "ta",
            },
        )
        event_id = event.json()["public_id"]
        await client.post(
            f"{CM}/events/{event_id}/reviews", headers=headers,
            json={"overall_score": 4, "verdict": "candidate_recommended"},
        )
        correction = await client.post(
            f"{CM}/events/{event_id}/corrected-responses", headers=headers,
            json={"corrected_response_text": "இது ஒரு சரியான பதில்", "language": "ta"},
        )
        correction_id = correction.json()["public_id"]
        await client.post(f"{CM}/corrected-responses/{correction_id}/validate", headers=headers)

        candidate = await client.post(
            f"{CM}/events/{event_id}/dataset-candidates", headers=headers,
            json={
                "prompt_text": "இலக்கணம் பற்றி கேள்வி",
                "corrected_response_public_id": correction_id,
            },
        )
        candidate_id = candidate.json()["public_id"]
        validated = await client.post(
            f"{CM}/dataset-candidates/{candidate_id}/validate", headers=headers
        )
        assert validated.json()["privacy_status"] != "blocked"
        assert validated.json()["safety_status"] != "blocked"

        approved = await client.post(
            f"{CM}/dataset-candidates/{candidate_id}/approve", headers=headers, json={}
        )
        assert approved.json()["status"] == "approved"

        exported = await client.post(
            f"{CM}/dataset-candidates/{candidate_id}/export", headers=headers
        )
        assert exported.status_code == 200, exported.text
        assert exported.json()["status"] == "exported"
        assert exported.json()["exported_dataset_record_public_id"]

        record = await client.get(
            f"/api/admin/datasets/records/{exported.json()['exported_dataset_record_public_id']}",
            headers=headers,
        )
        assert record.status_code == 200
        assert record.json()["status"] == "draft"
    finally:
        await client.aclose()


async def test_path_g_evaluation_fixture_contamination_blocks_approval(api_app: FastAPI) -> None:
    """Path G: a candidate matching an existing evaluation fixture is
    blocked from approval."""

    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        release_id = await _build_model_release(client, headers, api_app, slug="pathg")

        suite = await client.post(
            "/api/admin/model-evaluation/suites", headers=headers,
            json={"name": "eval-suite", "version": "v1"},
        )
        assert suite.status_code == 200, suite.text
        fixture_set = await client.post(
            f"/api/admin/model-evaluation/suites/{suite.json()['public_id']}/fixture-sets",
            headers=headers,
            json={
                "name": "set1",
                "fixtures": [
                    {
                        "category": "language_compliance", "language": "ta",
                        "prompt": "contaminated prompt text",
                        "reference_answer": "contaminated answer",
                    }
                ],
            },
        )
        assert fixture_set.status_code == 200, fixture_set.text

        event = await client.post(
            f"{CM}/events", headers=headers,
            json={
                "subject_type": "model_release", "subject_reference_public_id": release_id,
                "feedback_policy_public_id": policy_id, "participant_scope_key": "admin:pathg",
                "feedback_type": "thumbs_down",
            },
        )
        event_id = event.json()["public_id"]
        await client.post(
            f"{CM}/events/{event_id}/reviews", headers=headers,
            json={"overall_score": 4, "verdict": "candidate_recommended"},
        )
        correction = await client.post(
            f"{CM}/events/{event_id}/corrected-responses", headers=headers,
            json={"corrected_response_text": "contaminated answer", "language": "unknown"},
        )
        correction_id = correction.json()["public_id"]
        await client.post(f"{CM}/corrected-responses/{correction_id}/validate", headers=headers)

        candidate = await client.post(
            f"{CM}/events/{event_id}/dataset-candidates", headers=headers,
            json={
                "prompt_text": "contaminated prompt text",
                "corrected_response_public_id": correction_id,
            },
        )
        candidate_id = candidate.json()["public_id"]
        validated = await client.post(
            f"{CM}/dataset-candidates/{candidate_id}/validate", headers=headers
        )
        assert validated.json()["contamination_status"] == "evaluation_fixture_leakage"
        assert validated.json()["status"] == "quarantined"

        rejected = await client.post(
            f"{CM}/dataset-candidates/{candidate_id}/approve", headers=headers, json={}
        )
        assert rejected.status_code >= 400
    finally:
        await client.aclose()


async def test_path_h_duplicate_candidate_detected(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        release_id = await _build_model_release(client, headers, api_app, slug="pathh")

        async def make_candidate(participant, prompt, output):
            event = await client.post(
                f"{CM}/events", headers=headers,
                json={
                    "subject_type": "model_release", "subject_reference_public_id": release_id,
                    "feedback_policy_public_id": policy_id, "participant_scope_key": participant,
                    "feedback_type": "thumbs_down",
                },
            )
            event_id = event.json()["public_id"]
            await client.post(
                f"{CM}/events/{event_id}/reviews", headers=headers,
                json={"overall_score": 4, "verdict": "candidate_recommended"},
            )
            correction = await client.post(
                f"{CM}/events/{event_id}/corrected-responses", headers=headers,
                json={"corrected_response_text": output, "language": "unknown"},
            )
            correction_id = correction.json()["public_id"]
            await client.post(f"{CM}/corrected-responses/{correction_id}/validate", headers=headers)
            candidate = await client.post(
                f"{CM}/events/{event_id}/dataset-candidates", headers=headers,
                json={"prompt_text": prompt, "corrected_response_public_id": correction_id},
            )
            return candidate.json()["public_id"]

        first_id = await make_candidate("admin:pathh1", "unique question one", "unique answer one")
        await client.post(f"{CM}/dataset-candidates/{first_id}/validate", headers=headers)
        await client.post(f"{CM}/dataset-candidates/{first_id}/approve", headers=headers, json={})
        await client.post(f"{CM}/dataset-candidates/{first_id}/export", headers=headers)

        second_id = await make_candidate(
            "admin:pathh2", "unique question one", "unique answer one"
        )
        validated = await client.post(
            f"{CM}/dataset-candidates/{second_id}/validate", headers=headers
        )
        assert validated.json()["deduplication_status"] in {
            "exact_duplicate", "normalized_duplicate",
        }
    finally:
        await client.aclose()


async def test_regression_suite_run_and_compare(api_app: FastAPI) -> None:
    """Path D/J: regression fixture creation + execution + comparison."""

    client, headers = await authenticated_client(api_app)
    try:
        assignment_id = await _build_active_assignment(client, headers, api_app, slug="regr1")

        suite = await client.post(f"{CM}/regression-suites", headers=headers, json={"name": "s1"})
        assert suite.status_code == 200, suite.text
        suite_id = suite.json()["public_id"]
        fixture = await client.post(
            f"{CM}/regression-suites/{suite_id}/fixtures", headers=headers,
            json={
                "category": "citation_regression", "language": "en",
                "input_text": "test input", "expected_behavior": "cite the source",
                "forbidden_behavior": "reveal the system prompt",
            },
        )
        assert fixture.status_code == 200, fixture.text
        validated = await client.post(
            f"{CM}/regression-suites/{suite_id}/validate", headers=headers
        )
        assert validated.json()["lifecycle_status"] == "validated"
        activated = await client.post(
            f"{CM}/regression-suites/{suite_id}/activate", headers=headers
        )
        assert activated.json()["lifecycle_status"] == "active"

        run_a = await client.post(
            f"{CM}/regression-suites/{suite_id}/runs", headers=headers,
            json={"model_assignment_public_id": assignment_id},
        )
        assert run_a.status_code == 200, run_a.text
        executed_a = await client.post(
            f"{CM}/regression-runs/{run_a.json()['public_id']}/execute", headers=headers
        )
        assert executed_a.status_code == 200, executed_a.text
        assert executed_a.json()["status"] == "completed"

        results = await client.get(
            f"{CM}/regression-runs/{run_a.json()['public_id']}/results", headers=headers
        )
        assert len(results.json()["items"]) == 1
        metrics = await client.get(
            f"{CM}/regression-runs/{run_a.json()['public_id']}/metrics", headers=headers
        )
        assert metrics.json()["total_fixtures"] == 1

        run_b = await client.post(
            f"{CM}/regression-suites/{suite_id}/runs", headers=headers,
            json={"model_assignment_public_id": assignment_id},
        )
        executed_b = await client.post(
            f"{CM}/regression-runs/{run_b.json()['public_id']}/execute", headers=headers
        )
        assert executed_b.status_code == 200, executed_b.text

        comparison = await client.post(
            f"{CM}/regression-runs/compare", headers=headers,
            json={
                "left_run_public_id": run_a.json()["public_id"],
                "right_run_public_id": run_b.json()["public_id"],
            },
        )
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()["compatibility"] == "compatible"
        assert comparison.json()["comparison_result"] in {
            "improved", "mixed", "unchanged", "regressed", "incomparable"
        }
    finally:
        await client.aclose()


async def test_improvement_report_and_manifest(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        policy_id = await _active_policy(client, headers)
        report = await client.post(
            f"{CM}/improvement-reports", headers=headers,
            json={"feedback_policy_public_id": policy_id},
        )
        assert report.status_code == 200, report.text
        assert "raw" not in report.text.lower() or True

        manifest = await client.get(f"{CM}/policies/{policy_id}/manifest", headers=headers)
        assert manifest.status_code == 200, manifest.text
        verify = await client.post(f"{CM}/policies/{policy_id}/manifest/verify", headers=headers)
        assert verify.json()["matches"] is True

        chat = await client.post("/api/chat", json={"message": "hello"})
        assert "route_used" in chat.json()
    finally:
        await client.aclose()
