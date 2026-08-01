import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_incremental_training_run_and_execution import (
    _TINY_CONFIG,
    _pretraining_refs,
)
from tests.backend.test_training_suitability_and_transformation import _build_accepted_experiment

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "incremental_training_api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus",
        tokenizer_dir=tmp_path / "tokenizers",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_incremental_training_governed_flow_via_http(api_app: FastAPI) -> None:
    settings = api_app.state.settings

    candidate_public_ids = []
    assessment_public_id = None
    client, headers = await authenticated_client(api_app)
    try:
        for index in range(3):
            built = _build_accepted_experiment(settings, code_suffix=str(index))

            created = await client.post(
                "/api/admin/incremental-training/assessments",
                headers=headers,
                json={"rag_sandbox_experiment_public_id": built["experiment"]["public_id"]},
            )
            assert created.status_code == 200, created.text
            assessment_public_id = created.json()["public_id"]

            ran = await client.post(
                f"/api/admin/incremental-training/assessments/{assessment_public_id}/run",
                headers=headers, json={},
            )
            assert ran.status_code == 200, ran.text

            items = await client.get(
                f"/api/admin/incremental-training/assessments/{assessment_public_id}/items",
                headers=headers,
            )
            assert items.status_code == 200
            item_id = items.json()["items"][0]["public_id"]

            transformed = await client.post(
                f"/api/admin/incremental-training/items/{item_id}/transform",
                headers=headers,
                json={
                    "transformation_type": "instruction_response_pair",
                    "prompt_text": f"தமிழ் கேள்வி {index}?",
                    "assistant_text": f"தமிழ் பதில் {index}.",
                    "language": "ta",
                    "source_checksum": "chk-record-0",
                },
            )
            assert transformed.status_code == 200, transformed.text
            candidate_id = transformed.json()["public_id"]

            reviewed = await client.post(
                f"/api/admin/incremental-training/candidates/{candidate_id}/review",
                headers=headers,
                json={"decision": "approved", "reason": "looks correct for this test"},
            )
            assert reviewed.status_code == 200, reviewed.text
            candidate_public_ids.append(candidate_id)

        recheck = await client.get(
            "/api/admin/incremental-training/contamination-recheck",
            headers=headers,
            params=[("candidate_public_ids", cid) for cid in candidate_public_ids],
        )
        assert recheck.status_code == 200, recheck.text
        assert recheck.json()["blocking_candidate_ids"] == []

        promotion_created = await client.post(
            f"/api/admin/incremental-training/assessments/{assessment_public_id}/"
            "promotion-requests",
            headers=headers,
            json={"candidate_public_ids": candidate_public_ids},
        )
        assert promotion_created.status_code == 200, promotion_created.text
        promotion_id = promotion_created.json()["public_id"]

        submitted = await client.post(
            f"/api/admin/incremental-training/promotion-requests/{promotion_id}/submit",
            headers=headers, json={},
        )
        assert submitted.status_code == 200, submitted.text

        approved_promotion = await client.post(
            f"/api/admin/incremental-training/promotion-requests/{promotion_id}/approve",
            headers=headers, json={},
        )
        assert approved_promotion.status_code == 200, approved_promotion.text

        materialized = await client.post(
            f"/api/admin/incremental-training/promotion-requests/{promotion_id}/materialize",
            headers=headers, json={},
        )
        assert materialized.status_code == 200, materialized.text
        dataset_version_public_id = materialized.json()["dataset_version_public_id"]

        refs = _pretraining_refs(settings, dataset_version_public_id)

        run_request_created = await client.post(
            f"/api/admin/incremental-training/promotion-requests/{promotion_id}/run-requests",
            headers=headers,
            json={
                "training_strategy": "continued_pretraining",
                "tokenizer_version_public_id": refs["tokenizer"],
                "configuration": {
                    **_TINY_CONFIG, "core_model_version_public_id": refs["model"],
                },
            },
        )
        assert run_request_created.status_code == 200, run_request_created.text
        run_request_id = run_request_created.json()["public_id"]

        submitted_run = await client.post(
            f"/api/admin/incremental-training/run-requests/{run_request_id}/submit",
            headers=headers, json={},
        )
        assert submitted_run.status_code == 200, submitted_run.text

        approval_requested = await client.post(
            f"/api/admin/incremental-training/run-requests/{run_request_id}/request-approval",
            headers=headers, json={},
        )
        assert approval_requested.status_code == 200, approval_requested.text
        approval_id = approval_requested.json()["public_id"]

        run_approved = await client.post(
            f"/api/admin/incremental-training/run-approvals/{approval_id}/approve",
            headers=headers, json={},
        )
        assert run_approved.status_code == 200, run_approved.text

        started = await client.post(
            f"/api/admin/incremental-training/run-approvals/{approval_id}/start",
            headers=headers, json={},
        )
        assert started.status_code == 200, started.text
        run_id = started.json()["public_id"]
        assert started.json()["status"] in ("completed", "completed_with_warnings")

        checkpoints = await client.get(
            f"/api/admin/incremental-training/runs/{run_id}/checkpoints", headers=headers,
        )
        assert checkpoints.status_code == 200
        checkpoint_id = checkpoints.json()["items"][0]["public_id"]

        verified = await client.post(
            f"/api/admin/incremental-training/checkpoints/{checkpoint_id}/verify",
            headers=headers, json={},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "verified"

        evaluated = await client.post(
            f"/api/admin/incremental-training/checkpoints/{checkpoint_id}/evaluate",
            headers=headers, json={},
        )
        assert evaluated.status_code == 200, evaluated.text
        assert evaluated.json()["checkpoint"]["status"] == "evaluated"

        reviewed_human = await client.post(
            f"/api/admin/incremental-training/checkpoints/{checkpoint_id}/human-reviews",
            headers=headers,
            json={
                "prompt_text": "தமிழில் ஒரு வாக்கியம் எழுது.",
                "decision": "pass",
                "tamil_fluency": True,
                "regression": False,
            },
        )
        assert reviewed_human.status_code == 200, reviewed_human.text

        report = await client.post(
            f"/api/admin/incremental-training/runs/{run_id}/reports",
            headers=headers,
            json={"checkpoint_public_id": checkpoint_id},
        )
        assert report.status_code == 200, report.text
        report_id = report.json()["public_id"]

        accepted = await client.post(
            f"/api/admin/incremental-training/checkpoints/{checkpoint_id}/accept",
            headers=headers,
            json={
                "report_public_id": report_id, "decision": "accepted_candidate",
                "reason": "meets bar for this http test",
            },
        )
        assert accepted.status_code == 200, accepted.text
        model_candidate_public_id = accepted.json()["model_candidate_public_id"]
        assert model_candidate_public_id

        with sqlite3.connect(settings.resolved_database_path) as connection:
            row = connection.execute(
                "SELECT lifecycle_status FROM core_model_versions WHERE public_id=?",
                (model_candidate_public_id,),
            ).fetchone()
        assert row[0] == "staging"

        overview = await client.get(
            "/api/admin/incremental-training/overview", headers=headers,
        )
        assert overview.status_code == 200
        assert "accepted_model_candidates" in overview.json()
    finally:
        await client.aclose()


async def test_mutations_require_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/incremental-training/assessments",
            json={"rag_sandbox_experiment_public_id": "x"},
        )
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_unauthenticated_requests_are_rejected(api_app: FastAPI) -> None:
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get("/api/admin/incremental-training/overview")
        assert response.status_code in (401, 403)
        response = await client.get("/api/admin/incremental-training/assessments")
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_no_production_activation_or_release_endpoints_exist(api_app: FastAPI) -> None:
    paths = {route.path for route in api_app.routes if "/incremental-training" in route.path}
    forbidden_markers = ("activate", "release", "production")
    offending = [
        path for path in paths if any(marker in path.lower() for marker in forbidden_markers)
    ]
    assert offending == []
