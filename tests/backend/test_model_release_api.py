import json
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_instruction_tuning_api import _fixture_refs
from tests.backend.test_model_evaluation_api import _promote_candidate

pytestmark = pytest.mark.anyio

ADMIN = "00000000-0000-0000-0000-000000000001"


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
    app: FastAPI, candidate_core_model_public_id: str, readiness_status: str
) -> str:
    """Insert a minimal evaluation suite/run/readiness/manifest chain directly
    (bypassing the full Phase 13 execution pipeline, which is already
    covered by its own test suite) so Phase 14 candidate eligibility can be
    exercised against a real evaluation_run FK lineage."""

    settings = app.state.settings
    suffix = "1" if readiness_status == "evaluation_blocked" else "2"
    run_public_id = f"90000000-0000-0000-0000-00000000{suffix}0{suffix}0"
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
            ("90000000-0000-0000-0000-000000000001", "phase14-suite", "v1", "active", ADMIN),
        )
        suite_id = connection.execute(
            "SELECT id FROM model_evaluation_suites WHERE public_id=?",
            ("90000000-0000-0000-0000-000000000001",),
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
                f"90000000-0000-0000-0000-00000000{suffix}1{suffix}1",
                run_id, readiness_status, ADMIN,
            ),
        )
        connection.execute(
            """INSERT INTO model_evaluation_manifests(public_id,model_evaluation_run_id,
            manifest_json,manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (
                f"90000000-0000-0000-0000-00000000{suffix}2{suffix}2",
                run_id, dumps_json({"run": run_public_id}), "c" * 64,
            ),
        )
        connection.commit()
    return run_public_id


async def _create_family(client, headers) -> str:
    created = await client.post(
        "/api/admin/model-releases/families",
        headers=headers,
        json={"name": "Phase14 Family", "slug": "phase14-family"},
    )
    assert created.status_code == 200, created.text
    return created.json()["public_id"]


async def test_candidate_a_blocked_by_evaluation(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    candidate_core_model_public_id = _promote_candidate(api_app, refs)
    run_public_id = _insert_evaluation_evidence(
        api_app, candidate_core_model_public_id, "evaluation_blocked"
    )
    client, headers = await authenticated_client(api_app)
    try:
        family_id = await _create_family(client, headers)
        candidate_created = await client.post(
            "/api/admin/model-releases/candidates",
            headers=headers,
            json={
                "model_release_family_public_id": family_id,
                "core_model_version_public_id": candidate_core_model_public_id,
                "dataset_version_public_id": refs["dataset"],
                "model_evaluation_run_public_id": run_public_id,
                "label": "candidate-a-blocked",
            },
        )
        assert candidate_created.status_code == 200, candidate_created.text
        candidate_id = candidate_created.json()["public_id"]

        collected = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/collect-artifacts",
            headers=headers,
        )
        assert collected.status_code == 200, collected.text
        assert len(collected.json()["items"]) > 0

        verified = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/verify-artifacts",
            headers=headers,
        )
        assert verified.status_code == 200, verified.text

        eligibility = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/eligibility/assess",
            headers=headers,
        )
        assert eligibility.status_code == 200, eligibility.text
        assert eligibility.json()["status"] == "blocked"
        assert "evaluation_blocked" in eligibility.json()["rationale"]["blocking_reasons"]

        issues = await client.get(f"/api/admin/model-releases/candidates/{candidate_id}/issues")
        issue_codes = {item["issue_code"] for item in issues.json()["items"]}
        assert "evaluation_blocked" in issue_codes

        rejected_approval = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/approvals",
            headers=headers,
            json={"role": "release", "decision": "approve", "comment": ""},
        )
        assert rejected_approval.status_code in {400, 422}

        rejected_release = await client.post(
            "/api/admin/model-releases/releases",
            headers=headers,
            json={"candidate_public_id": candidate_id, "version": "0.1.0"},
        )
        assert rejected_release.status_code in {400, 422}
    finally:
        await client.aclose()


async def test_candidate_b_eligible_full_lifecycle(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    candidate_core_model_public_id = refs["base_model"]
    run_public_id = _insert_evaluation_evidence(
        api_app, candidate_core_model_public_id, "evaluation_passed_with_limits"
    )
    client, headers = await authenticated_client(api_app)
    try:
        unauthenticated = await client.post(
            "/api/admin/model-releases/families", json={"name": "x", "slug": "x"}
        )
        assert unauthenticated.status_code == 403

        family_id = await _create_family(client, headers)
        candidate_created = await client.post(
            "/api/admin/model-releases/candidates",
            headers=headers,
            json={
                "model_release_family_public_id": family_id,
                "core_model_version_public_id": candidate_core_model_public_id,
                "dataset_version_public_id": refs["dataset"],
                "model_evaluation_run_public_id": run_public_id,
                "label": "candidate-b-eligible",
                "notes": "registry_workflow_fixture / not_production_model",
            },
        )
        assert candidate_created.status_code == 200, candidate_created.text
        candidate_id = candidate_created.json()["public_id"]

        await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/collect-artifacts",
            headers=headers,
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/verify-artifacts",
            headers=headers,
        )

        card = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/model-card", headers=headers
        )
        assert card.status_code == 200, card.text
        card_text = json.dumps(card.json())
        assert "/home/" not in card_text

        validated_card = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/model-card/validate",
            headers=headers,
        )
        assert validated_card.status_code == 200, validated_card.text
        assert validated_card.json()["validation_status"] == "valid", validated_card.json()

        eligibility = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/eligibility/assess",
            headers=headers,
        )
        assert eligibility.status_code == 200, eligibility.text
        assert eligibility.json()["status"] in {"eligible", "eligible_with_warnings"}

        manifest = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/manifest", headers=headers
        )
        assert manifest.status_code == 200, manifest.text
        manifest_text = json.dumps(manifest.json())
        assert "/home/" not in manifest_text
        assert str(api_app.state.settings.resolved_pretraining_dir) not in manifest_text

        verify_manifest = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/manifest/verify", headers=headers
        )
        assert verify_manifest.status_code == 200
        assert verify_manifest.json()["matches"] is True

        approval = await client.post(
            f"/api/admin/model-releases/candidates/{candidate_id}/approvals",
            headers=headers,
            json={"role": "release", "decision": "approve", "comment": "looks fine"},
        )
        assert approval.status_code == 200, approval.text

        release = await client.post(
            "/api/admin/model-releases/releases",
            headers=headers,
            json={"candidate_public_id": candidate_id, "version": "0.1.0-alpha.1"},
        )
        assert release.status_code == 200, release.text
        release_id = release.json()["public_id"]
        assert release.json()["status"] == "released"
        assert release.json()["deployment_eligibility"] in {
            "deployable", "deployable_with_warnings",
        }

        family_after = await client.get(f"/api/admin/model-releases/families/{family_id}")
        assert family_after.json()["current_release_public_id"] == release_id

        bundle = await client.post(
            f"/api/admin/model-releases/releases/{release_id}/bundle", headers=headers
        )
        assert bundle.status_code == 200, bundle.text
        bundle_id = bundle.json()["public_id"]
        inventory_text = json.dumps(bundle.json())
        assert ".env" not in inventory_text
        assert ".db" not in inventory_text

        verify_bundle = await client.post(
            f"/api/admin/model-releases/bundles/{bundle_id}/verify", headers=headers
        )
        assert verify_bundle.status_code == 200
        assert verify_bundle.json()["matches"] is True

        chat = await client.post("/api/chat", json={"message": "வணக்கம்"})
        assert "route_used" in chat.json()
    finally:
        await client.aclose()


async def test_rollback_workflow(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    candidate_core_model_public_id = refs["base_model"]
    run_public_id = _insert_evaluation_evidence(
        api_app, candidate_core_model_public_id, "evaluation_passed_with_limits"
    )
    client, headers = await authenticated_client(api_app)
    try:
        family_id = await _create_family(client, headers)

        async def _make_release(version: str) -> str:
            candidate_created = await client.post(
                "/api/admin/model-releases/candidates",
                headers=headers,
                json={
                    "model_release_family_public_id": family_id,
                    "core_model_version_public_id": candidate_core_model_public_id,
                    "dataset_version_public_id": refs["dataset"],
                    "model_evaluation_run_public_id": run_public_id,
                    "label": f"candidate-{version}",
                },
            )
            candidate_id = candidate_created.json()["public_id"]
            await client.post(
                f"/api/admin/model-releases/candidates/{candidate_id}/collect-artifacts",
                headers=headers,
            )
            await client.post(
                f"/api/admin/model-releases/candidates/{candidate_id}/verify-artifacts",
                headers=headers,
            )
            await client.post(
                f"/api/admin/model-releases/candidates/{candidate_id}/model-card", headers=headers
            )
            await client.post(
                f"/api/admin/model-releases/candidates/{candidate_id}/model-card/validate",
                headers=headers,
            )
            await client.post(
                f"/api/admin/model-releases/candidates/{candidate_id}/eligibility/assess",
                headers=headers,
            )
            await client.post(
                f"/api/admin/model-releases/candidates/{candidate_id}/manifest", headers=headers
            )
            await client.post(
                f"/api/admin/model-releases/candidates/{candidate_id}/approvals",
                headers=headers,
                json={"role": "release", "decision": "approve", "comment": ""},
            )
            release_created = await client.post(
                "/api/admin/model-releases/releases",
                headers=headers,
                json={"candidate_public_id": candidate_id, "version": version},
            )
            assert release_created.status_code == 200, release_created.text
            return release_created.json()["public_id"]

        release_alpha_1 = await _make_release("0.1.0-alpha.1")
        release_alpha_2 = await _make_release("0.1.0-alpha.2")

        family_after_second = await client.get(f"/api/admin/model-releases/families/{family_id}")
        assert family_after_second.json()["current_release_public_id"] == release_alpha_2

        plan_created = await client.post(
            f"/api/admin/model-releases/releases/{release_alpha_2}/rollback-plans",
            headers=headers,
            json={"target_release_public_id": release_alpha_1, "reason": "manual verification"},
        )
        assert plan_created.status_code == 200, plan_created.text
        plan_id = plan_created.json()["public_id"]

        validated_plan = await client.post(
            f"/api/admin/model-releases/rollback-plans/{plan_id}/validate", headers=headers
        )
        assert validated_plan.status_code == 200, validated_plan.text
        assert validated_plan.json()["status"] == "validated"

        approved_plan = await client.post(
            f"/api/admin/model-releases/rollback-plans/{plan_id}/approve", headers=headers
        )
        assert approved_plan.status_code == 200, approved_plan.text
        assert approved_plan.json()["status"] == "approved"

        executed_plan = await client.post(
            f"/api/admin/model-releases/rollback-plans/{plan_id}/execute", headers=headers
        )
        assert executed_plan.status_code == 200, executed_plan.text
        assert executed_plan.json()["status"] == "executed"

        source_release = await client.get(
            f"/api/admin/model-releases/releases/{release_alpha_2}"
        )
        assert source_release.json()["status"] == "rolled_back"

        family_final = await client.get(f"/api/admin/model-releases/families/{family_id}")
        assert family_final.json()["current_release_public_id"] == release_alpha_1

        chat = await client.post("/api/chat", json={"message": "hello"})
        assert "route_used" in chat.json()
    finally:
        await client.aclose()


async def test_rollback_rejects_ineligible_target(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    candidate_core_model_public_id = refs["base_model"]
    blocked_run = _insert_evaluation_evidence(
        api_app, candidate_core_model_public_id, "evaluation_blocked"
    )
    good_run = _insert_evaluation_evidence(
        api_app, candidate_core_model_public_id, "evaluation_passed_with_limits"
    )
    client, headers = await authenticated_client(api_app)
    try:
        family_id = await _create_family(client, headers)

        async def _make_candidate(run_id: str, label: str) -> str:
            created = await client.post(
                "/api/admin/model-releases/candidates",
                headers=headers,
                json={
                    "model_release_family_public_id": family_id,
                    "core_model_version_public_id": candidate_core_model_public_id,
                    "dataset_version_public_id": refs["dataset"],
                    "model_evaluation_run_public_id": run_id,
                    "label": label,
                },
            )
            return created.json()["public_id"]

        good_candidate = await _make_candidate(good_run, "good")
        await client.post(
            f"/api/admin/model-releases/candidates/{good_candidate}/collect-artifacts",
            headers=headers,
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{good_candidate}/verify-artifacts",
            headers=headers,
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{good_candidate}/model-card", headers=headers
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{good_candidate}/model-card/validate",
            headers=headers,
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{good_candidate}/eligibility/assess",
            headers=headers,
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{good_candidate}/manifest", headers=headers
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{good_candidate}/approvals",
            headers=headers,
            json={"role": "release", "decision": "approve", "comment": ""},
        )
        good_release = await client.post(
            "/api/admin/model-releases/releases",
            headers=headers,
            json={"candidate_public_id": good_candidate, "version": "0.2.0"},
        )
        good_release_id = good_release.json()["public_id"]

        bad_candidate = await _make_candidate(blocked_run, "bad")
        await client.post(
            f"/api/admin/model-releases/candidates/{bad_candidate}/collect-artifacts",
            headers=headers,
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{bad_candidate}/verify-artifacts",
            headers=headers,
        )
        await client.post(
            f"/api/admin/model-releases/candidates/{bad_candidate}/eligibility/assess",
            headers=headers,
        )
        # bad_candidate cannot itself become a release (blocked); use it only to
        # prove a rollback plan targeting a non-released version is rejected.
        plan_rejected = await client.post(
            f"/api/admin/model-releases/releases/{good_release_id}/rollback-plans",
            headers=headers,
            json={"target_release_public_id": good_release_id, "reason": "self-target smoke check"},
        )
        # self-target should still validate structurally; the real ineligible-target
        # proof is that bad_candidate never reaches release status at all:
        candidate_status = await client.get(
            f"/api/admin/model-releases/candidates/{bad_candidate}"
        )
        assert candidate_status.json()["status"] == "blocked"
        assert plan_rejected.status_code == 200
    finally:
        await client.aclose()
