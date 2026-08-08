import base64
import json
import os
import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from backend.services.production_regression_service import _DEFAULT_MANIFEST_PATH
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def test_overview_requires_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.get("/api/admin/production-readiness/overview")
        assert response.status_code in (401, 403)
    finally:
        await client.aclose()


async def test_overview_returns_zero_counts_on_fresh_database(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(
            "/api/admin/production-readiness/overview", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["rag_promotions_awaiting_approval"] == 0
        assert body["activation_failures"] == 0
    finally:
        await client.aclose()


async def test_rag_eligibility_404_for_unknown_experiment(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(
            "/api/admin/production-readiness/rag/eligibility/does-not-exist",
            headers=headers,
        )
        assert response.status_code >= 400
    finally:
        await client.aclose()


async def test_api_abuse_readiness_assess_endpoint(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/production-readiness/api-abuse-readiness/assess", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["result_status"] == "passed"
    finally:
        await client.aclose()


async def test_secret_scan_redaction_endpoint(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/production-readiness/secret-scan/verify-redaction", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["result_status"] == "passed"
    finally:
        await client.aclose()


async def test_backup_readiness_check_endpoint_not_configured(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/production-readiness/backup-readiness/check",
            headers=headers,
            json={},
        )
        assert response.status_code == 200, response.text
        assert response.json()["result_status"] == "not_configured"
    finally:
        await client.aclose()


async def test_backup_encryption_assessment_endpoint_honestly_reports_not_configured(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/production-readiness/backup-readiness/assess-encryption",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["result_status"] == "not_configured"
        assert "no_backup_present" in body["findings"]
    finally:
        await client.aclose()


async def test_backup_encryption_endpoint_full_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "api2.db",
        database_backup_dir=tmp_path / "backups2",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    settings.resolved_backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        settings.resolved_database_path,
        settings.resolved_backup_dir / "brud_ai_before_v38_20260101000000.db",
    )
    monkeypatch.setenv(
        settings.backup_encryption_key_env_var,
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    )

    client, headers = await authenticated_client(create_app(settings))
    try:
        response = await client.post(
            "/api/admin/production-readiness/backup-readiness/encrypt", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["result_status"] == "encrypted"

        assess_response = await client.post(
            "/api/admin/production-readiness/backup-readiness/assess-encryption", headers=headers
        )
        assert assess_response.status_code == 200
        assert assess_response.json()["result_status"] == "encrypted"

        restore_response = await client.post(
            "/api/admin/production-readiness/backup-readiness/verify-encrypted-restore",
            headers=headers,
        )
        assert restore_response.status_code == 200, restore_response.text
        assert restore_response.json()["result_status"] == "passed"
    finally:
        await client.aclose()


async def test_system_health_endpoint_is_a_real_get_and_needs_no_csrf_header(
    api_app: FastAPI,
) -> None:
    # Regression test for a real bug found by Phase 15A browser
    # automation: this route is declared `@router.get(...)` but required
    # `CsrfDependency` (every sibling GET route in this router relies
    # only on the router-wide auth dependency, never CSRF) -- combined
    # with the frontend calling it via POST, clicking "System health
    # snapshot" in the real UI always failed with 405 Method Not Allowed.
    client, headers = await authenticated_client(api_app)
    try:
        get_only_headers = {k: v for k, v in headers.items() if k.lower() != "x-csrf-token"}
        response = await client.get(
            "/api/admin/production-readiness/system-health", headers=get_only_headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["overall_status"] in {"healthy", "degraded"}
    finally:
        await client.aclose()


async def test_regression_run_requires_batch_plan(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/production-readiness/regression/runs",
            headers=headers,
            json={"batch_plan": []},
        )
        assert response.status_code >= 400
    finally:
        await client.aclose()


async def test_regression_full_run_through_api(api_app: FastAPI, tmp_path: Path) -> None:
    # execute_batch() confines admin-supplied test_paths to resolve under
    # tests/ (backend/services/production_regression_service.py) -- this
    # synthetic single-test fixture file must therefore live under tests/,
    # not in pytest's own tmp_path (which resolves outside the repo).
    repo_root = Path(__file__).resolve().parents[2]
    fixture_dir = repo_root / "tests" / "_regression_fixtures" / tmp_path.name
    fixture_dir.mkdir(parents=True, exist_ok=True)
    try:
        test_file = fixture_dir / "trivial_passing.py"
        test_file.write_text("def test_trivial_ok():\n    assert True\n", encoding="utf-8")
        test_path = str(test_file.relative_to(repo_root))

        client, headers = await authenticated_client(api_app)
        try:
            created = await client.post(
                "/api/admin/production-readiness/regression/runs",
                headers=headers,
                json={"batch_plan": [{"batch_name": "trivial", "command": [test_path]}]},
            )
            assert created.status_code == 200, created.text
            run_id = created.json()["public_id"]

            executed = await client.post(
                f"/api/admin/production-readiness/regression/runs/{run_id}/batches",
                headers=headers,
                json={"batch_name": "trivial", "test_paths": [test_path]},
            )
            assert executed.status_code == 200, executed.text
            assert executed.json()["status"] == "passed"

            finalized = await client.post(
                f"/api/admin/production-readiness/regression/runs/{run_id}/finalize",
                headers=headers,
            )
            assert finalized.status_code == 200, finalized.text
            assert finalized.json()["status"] == "completed"
        finally:
            await client.aclose()
    finally:
        shutil.rmtree(fixture_dir, ignore_errors=True)


async def test_readiness_report_endpoint_reflects_not_ready_state(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/production-readiness/readiness-reports", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["recommendation"] == "not_ready"

        latest = await client.get(
            "/api/admin/production-readiness/readiness-reports/latest", headers=headers
        )
        assert latest.status_code == 200
        assert latest.json()["public_id"] == response.json()["public_id"]
    finally:
        await client.aclose()


async def test_acceptance_review_endpoint_binds_to_latest_report(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        report = await client.post(
            "/api/admin/production-readiness/readiness-reports", headers=headers
        )
        report_id = report.json()["public_id"]

        review = await client.post(
            f"/api/admin/production-readiness/readiness-reports/{report_id}/acceptance-review",
            headers=headers,
            json={"decision": "needs_remediation", "reason": "nothing assessed yet"},
        )
        assert review.status_code == 200, review.text
        assert review.json()["decision"] == "needs_remediation"
        assert review.json()["target_fingerprint"]
    finally:
        await client.aclose()


async def test_regression_manifest_endpoint_returns_the_real_checked_in_manifest(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(
            "/api/admin/production-readiness/regression-manifest", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        real_manifest = json.loads(_DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
        assert body["manifest_version"] == real_manifest["manifest_version"]
        assert body["manifest_checksum_sha256"]

        batches = await client.get(
            "/api/admin/production-readiness/regression-manifest/batches", headers=headers
        )
        assert batches.status_code == 200
        assert len(batches.json()["items"]) == len(body["batches"])
    finally:
        await client.aclose()


async def test_manifest_regression_run_full_flow_through_api(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/production-readiness/regression-runs", headers=headers
        )
        assert created.status_code == 200, created.text
        run_id = created.json()["public_id"]

        executed = await client.post(
            f"/api/admin/production-readiness/regression-runs/{run_id}/execute/secret_scan_01",
            headers=headers,
        )
        assert executed.status_code == 200, executed.text
        assert executed.json()["status"] == "passed"

        batch_result = await client.get(
            f"/api/admin/production-readiness/regression-runs/{run_id}/batches/secret_scan_01",
            headers=headers,
        )
        assert batch_result.status_code == 200, batch_result.text
        assert batch_result.json()["batch_name"] == "secret_scan:secret_scan_01"

        finalized = await client.post(
            f"/api/admin/production-readiness/regression-runs/{run_id}/finalize", headers=headers
        )
        assert finalized.status_code == 200, finalized.text
        assert finalized.json()["fine_status"] == "blocked"
    finally:
        await client.aclose()


async def test_manifest_regression_run_rejects_unregistered_batch_id(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/production-readiness/regression-runs", headers=headers
        )
        run_id = created.json()["public_id"]

        response = await client.post(
            f"/api/admin/production-readiness/regression-runs/{run_id}/execute/"
            "not_a_real_batch_id",
            headers=headers,
        )
        assert response.status_code >= 400
    finally:
        await client.aclose()
