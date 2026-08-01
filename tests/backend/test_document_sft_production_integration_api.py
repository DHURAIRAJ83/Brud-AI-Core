"""Production Integration §26: API tests for the new Admin REST endpoints --
overview, generator eligibility, dataset handoff (preview/ingest/idempotency/
checksum conflict), dataset-version proposal/split-preview/confirm-build,
proof-no-automatic-training, content classification, security/PII findings,
and the global Tamil correction rule registry."""

import fitz
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.repositories.admin import AdminRepository
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Document-SFT-Prod-Integration-Password-42"


def make_pdf(*texts: str) -> bytes:
    pdf = fitz.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    value = pdf.tobytes()
    pdf.close()
    return value


async def client_and_csrf(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="prod-integration-admin", display_name="PI Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    assert (
        await client.post(
            "/api/admin/auth/login",
            json={"username": "prod-integration-admin", "password": PASSWORD},
        )
    ).status_code == 200
    token = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": token}


async def _document_with_approved_export(client, headers, *, code="SRC-PI-API-0001"):
    upload = await client.post(
        "/api/admin/documents",
        headers=headers,
        files={"file": ("sample.pdf", make_pdf("Paragraph one content here."), "application/pdf")},
        data={"extraction_strategy": "embedded_text", "language": "en"},
    )
    assert upload.status_code == 200
    document_id = upload.json()["public_id"]
    assert (
        await client.post(
            f"/api/admin/documents/{document_id}/process",
            headers=headers,
            json={"strategy": "embedded_text"},
        )
    ).status_code == 200
    source = await client.post(
        "/api/admin/data-sources",
        headers=headers,
        json={"source_code": code, "title": "Test source", "source_type": "document_derived"},
    )
    assert source.status_code == 200
    source_id = source.json()["public_id"]
    assert (
        await client.put(
            f"/api/admin/data-sources/{source_id}/rights",
            headers=headers,
            json={"rights_status": "public_domain", "training_use_allowed": True},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/admin/documents/{document_id}/source-link",
            headers=headers,
            json={"source_public_id": source_id},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/admin/documents/{document_id}/pages/1/approve", headers=headers, json={}
        )
    ).status_code == 200
    generated = await client.post(
        f"/api/admin/semantic-chunks/document/{document_id}/generate", headers=headers, json={}
    )
    assert generated.status_code == 200
    chunk_id = generated.json()["chunk_public_ids"][0]
    assert (
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/classify",
            headers=headers,
            json={"chunk_type": "definition"},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/submit-review", headers=headers, json={}
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/admin/semantic-chunks/{chunk_id}/approve", headers=headers, json={}
        )
    ).status_code == 200
    generated_candidates = await client.post(
        f"/api/admin/documents/{document_id}/sft-candidates/generate", headers=headers, json={}
    )
    assert generated_candidates.status_code == 200
    candidate_id = generated_candidates.json()["items"][0]["public_id"]
    assert (
        await client.post(
            f"/api/admin/documents/{document_id}/sft-candidates/{candidate_id}/review",
            headers=headers,
            json={"action": "approve"},
        )
    ).status_code == 200
    exported = await client.post(
        f"/api/admin/documents/{document_id}/sft-export", headers=headers, json={"confirm": True}
    )
    assert exported.status_code == 200
    return document_id, exported.json()["public_id"]


class TestAuthAndOverview:
    async def test_new_endpoints_require_auth(self, api_app: FastAPI) -> None:
        client, headers = await client_and_csrf(api_app)
        try:
            document_id, _export_id = await _document_with_approved_export(client, headers)
            unauth = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
            assert (
                await unauth.get(f"/api/admin/documents/{document_id}/overview")
            ).status_code == 401
            assert (
                await unauth.get("/api/admin/document-tamil-correction-rules")
            ).status_code == 401
            await unauth.aclose()
        finally:
            await client.aclose()

    async def test_overview_and_generator_eligibility(self, api_app: FastAPI) -> None:
        client, headers = await client_and_csrf(api_app)
        try:
            document_id, export_id = await _document_with_approved_export(client, headers)
            overview = await client.get(f"/api/admin/documents/{document_id}/overview")
            assert overview.status_code == 200
            body = overview.json()
            assert body["sft_candidates_summary"]["total_candidates"] == 1
            assert body["exports"]["items"][0]["public_id"] == export_id

            eligibility = await client.get(
                f"/api/admin/documents/{document_id}/generator-eligibility"
            )
            assert eligibility.status_code == 200
            eligibility_body = eligibility.json()
            assert eligibility_body["approved_chunk_counts_by_type"]["definition"] == 1
            assert "safety_response" in eligibility_body["deferred_generators"]
            assert "definition" in eligibility_body["available_generators"]
        finally:
            await client.aclose()


class TestDatasetHandoffFlow:
    async def test_validate_preview_ingest_idempotent_and_checksum_conflict(
        self, api_app: FastAPI
    ) -> None:
        client, headers = await client_and_csrf(api_app)
        try:
            document_id, export_id = await _document_with_approved_export(client, headers)

            validated = await client.post(
                f"/api/admin/documents/{document_id}/sft-export/{export_id}/validate",
                headers=headers,
            )
            assert validated.status_code == 200
            assert validated.json()["valid"] is True

            no_csrf = await client.post(
                f"/api/admin/documents/{document_id}/sft-export/{export_id}/handoff-ingest",
                json={"confirm": True},
            )
            assert no_csrf.status_code == 403

            preview = await client.post(
                f"/api/admin/documents/{document_id}/sft-export/{export_id}/handoff-preview",
                headers=headers,
            )
            assert preview.status_code == 200
            assert preview.json()["eligible_count"] == 1
            assert preview.json()["already_ingested"] is False

            unconfirmed = await client.post(
                f"/api/admin/documents/{document_id}/sft-export/{export_id}/handoff-ingest",
                headers=headers,
                json={"confirm": False},
            )
            assert unconfirmed.status_code == 422

            ingested = await client.post(
                f"/api/admin/documents/{document_id}/sft-export/{export_id}/handoff-ingest",
                headers=headers,
                json={"confirm": True},
            )
            assert ingested.status_code == 200
            handoff = ingested.json()
            assert handoff["imported_count"] == 1
            assert handoff["status"] == "imported"

            # Idempotent retry: same export, same checksum -> no duplicate record.
            retried = await client.post(
                f"/api/admin/documents/{document_id}/sft-export/{export_id}/handoff-ingest",
                headers=headers,
                json={"confirm": True},
            )
            assert retried.status_code == 200
            assert retried.json()["public_id"] == handoff["public_id"]
            assert retried.json()["imported_count"] == 1

            listed = await client.get(f"/api/admin/documents/{document_id}/handoffs")
            assert listed.status_code == 200
            assert listed.json()["total"] == 1

            # Simulate a tampered/re-exported checksum -> integrity conflict.
            from backend.database.repositories.documents import DocumentRepository

            repository = DocumentRepository(api_app.state.settings.resolved_database_path)
            with repository.transaction() as connection:
                connection.execute(
                    "UPDATE document_sft_dataset_handoffs SET export_checksum_sha256='tampered' "
                    "WHERE public_id=?",
                    (handoff["public_id"],),
                )
            conflict = await client.post(
                f"/api/admin/documents/{document_id}/sft-export/{export_id}/handoff-ingest",
                headers=headers,
                json={"confirm": True},
            )
            assert conflict.status_code == 409
        finally:
            await client.aclose()

    async def test_dataset_version_build_and_proof_no_automatic_training(
        self, api_app: FastAPI
    ) -> None:
        client, headers = await client_and_csrf(api_app)
        try:
            document_id, export_id = await _document_with_approved_export(client, headers)
            ingested = await client.post(
                f"/api/admin/documents/{document_id}/sft-export/{export_id}/handoff-ingest",
                headers=headers,
                json={"confirm": True},
            )
            handoff_id = ingested.json()["public_id"]

            not_ready = await client.get(
                f"/api/admin/documents/{document_id}/handoffs/{handoff_id}/split-preview"
            )
            assert not_ready.status_code == 422

            proposed = await client.post(
                f"/api/admin/documents/{document_id}/handoffs/{handoff_id}/dataset-version-proposal",
                headers=headers,
                json={"dataset_name": "pi-api-test", "dataset_version": "v1"},
            )
            assert proposed.status_code == 200
            assert proposed.json()["status"] == "version_proposed"

            status_before = await client.get(
                f"/api/admin/documents/{document_id}/dataset-version-status"
            )
            assert status_before.status_code == 200
            assert status_before.json()["status"] == "version_proposed"

            split_preview = await client.get(
                f"/api/admin/documents/{document_id}/handoffs/{handoff_id}/split-preview"
            )
            assert split_preview.status_code == 200
            assert "selected_records" in split_preview.json()

            confirmed = await client.post(
                f"/api/admin/documents/{document_id}/handoffs/{handoff_id}/confirm-build",
                headers=headers,
                json={"confirm": True},
            )
            assert confirmed.status_code == 200

            status_after = await client.get(
                f"/api/admin/documents/{document_id}/dataset-version-status"
            )
            assert status_after.status_code == 200
            assert status_after.json()["status"] == "version_built"

            from backend.database.repositories.documents import DocumentRepository

            repository = DocumentRepository(api_app.state.settings.resolved_database_path)
            with repository.transaction() as connection:
                training_jobs = connection.execute("SELECT COUNT(*) FROM training_jobs").fetchone()[
                    0
                ]
            assert training_jobs == 0
        finally:
            await client.aclose()


class TestContentClassificationAndSecurityApi:
    async def test_classification_scan_and_list(self, api_app: FastAPI) -> None:
        client, headers = await client_and_csrf(api_app)
        try:
            document_id, _export_id = await _document_with_approved_export(client, headers)
            scanned = await client.post(
                f"/api/admin/documents/{document_id}/content-classifications/scan",
                headers=headers,
            )
            assert scanned.status_code == 200
            listed = await client.get(
                f"/api/admin/documents/{document_id}/content-classifications"
            )
            assert listed.status_code == 200
            assert listed.json()["total"] >= 1
        finally:
            await client.aclose()

    async def test_security_scan_pii_findings_and_review(self, api_app: FastAPI) -> None:
        client, headers = await client_and_csrf(api_app)
        try:
            document_id, _export_id = await _document_with_approved_export(client, headers)
            scanned = await client.post(
                f"/api/admin/documents/{document_id}/security/scan", headers=headers
            )
            assert scanned.status_code == 200

            all_findings = await client.get(f"/api/admin/documents/{document_id}/security-findings")
            assert all_findings.status_code == 200

            pii = await client.get(f"/api/admin/documents/{document_id}/pii-findings")
            assert pii.status_code == 200
            for item in pii.json()["items"]:
                assert item["finding_type"].startswith("pii_")

            bad_action = await client.post(
                f"/api/admin/documents/{document_id}/security/some-nonexistent-id/review",
                headers=headers,
                json={"action": "block_export"},
            )
            assert bad_action.status_code == 422
        finally:
            await client.aclose()


class TestTamilCorrectionRulesApi:
    async def test_create_and_govern_lifecycle_via_api(self, api_app: FastAPI) -> None:
        client, headers = await client_and_csrf(api_app)
        try:
            created = await client.post(
                "/api/admin/document-tamil-correction-rules",
                headers=headers,
                json={
                    "incorrect_form": "a", "approved_correction": "b",
                    "issue_category": "pulli_error", "evidence": "e",
                    "confidence_band": "high", "meaning_change_risk": "mechanical",
                },
            )
            assert created.status_code == 200
            rule_id = created.json()["public_id"]
            assert created.json()["status"] == "draft"

            invalid_skip = await client.post(
                f"/api/admin/document-tamil-correction-rules/{rule_id}/review",
                headers=headers,
                json={"action": "activate"},
            )
            assert invalid_skip.status_code == 422

            submitted = await client.post(
                f"/api/admin/document-tamil-correction-rules/{rule_id}/review",
                headers=headers,
                json={"action": "submit_review"},
            )
            assert submitted.status_code == 200
            assert submitted.json()["status"] == "needs_review"

            approved = await client.post(
                f"/api/admin/document-tamil-correction-rules/{rule_id}/review",
                headers=headers,
                json={"action": "approve"},
            )
            assert approved.status_code == 200
            assert approved.json()["status"] == "approved"

            activated = await client.post(
                f"/api/admin/document-tamil-correction-rules/{rule_id}/review",
                headers=headers,
                json={"action": "activate"},
            )
            assert activated.status_code == 200
            assert activated.json()["status"] == "active"
            assert activated.json()["rule_version"] == 2

            history = await client.get(
                f"/api/admin/document-tamil-correction-rules/{rule_id}/history"
            )
            assert history.status_code == 200
            assert len(history.json()["items"]) == 3

            listed = await client.get(
                "/api/admin/document-tamil-correction-rules", params={"status": "active"}
            )
            assert listed.status_code == 200
            assert listed.json()["total"] == 1
        finally:
            await client.aclose()
