"""End-to-end backend smoke tests for the Document SFT workflow (migration 043):
Tamil quality detection/review, SFT candidate generation/review/export, all built
on top of the existing PDF upload -> extraction -> page review -> chunk pipeline
without modifying any of it."""

from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import DataSourceCreate, SourceRightsUpsert
from backend.models.documents import (
    ProcessRequest,
    SftBulkApprovalRequest,
    SftCandidateGenerationRequest,
    SftCandidateReviewAction,
    TamilQualityReviewAction,
)
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.document_service import DocumentService
from backend.services.document_sft_candidate_service import DocumentSftCandidateGenerationService
from backend.services.document_sft_export_service import DocumentSftExportService
from backend.services.document_tamil_quality_service import DocumentTamilQualityService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService


def make_pdf(*texts: str) -> bytes:
    pdf = fitz.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    value = pdf.tobytes()
    pdf.close()
    return value


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str = "application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self._content[self._offset : self._offset + size]
        self._offset += size
        return chunk


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "document_sft.db"
    initialize_database(database_path)
    return Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        document_sft_export_dir=tmp_path / "document_sft_exports",
        allow_external_storage=True,
    )


@pytest.fixture
def services(settings: Settings):
    return {
        "documents": DocumentService(settings),
        "workspace": PDFResearchWorkspaceService(settings),
        "review": DocumentPageReviewService(settings),
        "chunks": SemanticChunkService(settings),
        "chunk_review": SemanticChunkReviewService(settings),
        "tamil_quality": DocumentTamilQualityService(settings),
        "sft": DocumentSftCandidateGenerationService(settings),
        "export": DocumentSftExportService(settings),
        "source_registry": SourceRegistryService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
        "rights": SourceRightsService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
    }


_source_counter = 0


def _linked_source(services, code=None):
    global _source_counter
    _source_counter += 1
    return services["source_registry"].create(
        DataSourceCreate(
            source_code=code or f"SRC-SFT-{_source_counter:04d}",
            title="Test source",
            source_type="document_derived",
        ),
        "admin-1",
    )


async def _ready_document_with_approved_chunk(
    services, *, text="Paragraph one content here.", verified_rights=False
):
    upload_file = FakeUploadFile("sample.pdf", make_pdf(text))
    document = await services["documents"].upload(upload_file, "embedded_text", "en", "admin-1")
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
    )
    source = _linked_source(services)
    services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
    if verified_rights:
        services["rights"].upsert(
            source["public_id"],
            SourceRightsUpsert(rights_status="public_domain", training_use_allowed=True),
            "admin-1",
        )
    services["review"].approve(document["public_id"], 1, "admin-1")
    result = services["chunks"].generate(document["public_id"], "admin-1")
    chunk_public_id = result["chunk_public_ids"][0]
    services["chunks"].classify(chunk_public_id, "admin-1", chunk_type="definition")
    services["chunk_review"].submit_review(chunk_public_id, "admin-1")
    services["chunk_review"].approve(chunk_public_id, "admin-1")
    return document, source, chunk_public_id


class TestTamilQuality:
    @pytest.mark.anyio
    async def test_detect_is_idempotent_and_summary_reflects_zero_issues_for_clean_english_text(
        self, services
    ):
        document, _source, _chunk = await _ready_document_with_approved_chunk(services)
        first = services["tamil_quality"].detect(document["public_id"], "admin-1")
        second = services["tamil_quality"].detect(document["public_id"], "admin-1")
        assert first["total_issues"] == second["total_issues"]

    @pytest.mark.anyio
    async def test_review_rejects_unknown_action_payload(self, services):
        with pytest.raises(ValueError):
            TamilQualityReviewAction(action="not_a_real_action")

    @pytest.mark.anyio
    async def test_detect_finds_a_mechanical_ocr_substitution_and_accept_applies_the_fix(
        self, services
    ):
        upload_file = FakeUploadFile("sample.pdf", make_pdf("placeholder"))
        document = await services["documents"].upload(upload_file, "embedded_text", "ta", "admin-1")
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        artefact_text = "தமிழ் வாசகம் ஒொ்டு தவறு"
        services["documents"].edit_page(document["public_id"], 1, artefact_text, "admin-1")
        detection = services["tamil_quality"].detect(document["public_id"], "admin-1")
        assert detection["by_correction_risk"].get("mechanical", 0) >= 1
        issues = services["tamil_quality"].list_issues(
            document["public_id"], review_status="pending", issue_type="ocr_character_substitution"
        )
        assert issues["items"], "expected a mechanical OCR-substitution issue to be queued"
        issue = issues["items"][0]
        reviewed = services["tamil_quality"].review(
            document["public_id"],
            issue["public_id"],
            TamilQualityReviewAction(action="accept"),
            "admin-1",
        )
        accepted = next(
            item for item in reviewed["items"] if item["public_id"] == issue["public_id"]
        )
        assert accepted["review_status"] == "accepted"
        page = services["documents"].page(document["public_id"], 1)
        assert "ொ்" not in page["cleaned_text"]

    @pytest.mark.anyio
    async def test_ambiguous_issue_cannot_be_accepted_without_a_manual_edit(self, services):
        upload_file = FakeUploadFile("sample.pdf", make_pdf("placeholder"))
        document = await services["documents"].upload(upload_file, "embedded_text", "ta", "admin-1")
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        services["documents"].edit_page(document["public_id"], 1, "broken � text", "admin-1")
        services["tamil_quality"].detect(document["public_id"], "admin-1")
        issues = services["tamil_quality"].list_issues(
            document["public_id"], issue_type="invalid_unicode"
        )
        issue = issues["items"][0]
        assert issue["correction_risk"] == "mandatory_review"
        with pytest.raises(ValidationError, match="manual"):
            services["tamil_quality"].review(
                document["public_id"],
                issue["public_id"],
                TamilQualityReviewAction(action="accept"),
                "admin-1",
            )


class TestSftCandidateGeneration:
    @pytest.mark.anyio
    async def test_generate_requires_at_least_one_approved_chunk(self, services):
        upload_file = FakeUploadFile("sample.pdf", make_pdf("Some text."))
        document = await services["documents"].upload(upload_file, "embedded_text", "en", "admin-1")
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        with pytest.raises(ValidationError, match="approved chunks"):
            services["sft"].generate(
                document["public_id"], SftCandidateGenerationRequest(), "admin-1"
            )

    @pytest.mark.anyio
    async def test_generate_creates_a_definition_candidate_from_an_approved_chunk(self, services):
        document, _source, _chunk = await _ready_document_with_approved_chunk(services)
        result = services["sft"].generate(
            document["public_id"], SftCandidateGenerationRequest(), "admin-1"
        )
        assert result["total"] == 1
        candidate = result["items"][0]
        assert candidate["task"] == "definition"
        assert candidate["response"] == "Paragraph one content here."
        assert candidate["instruction"]
        assert candidate["source_document_id"] == document["public_id"]
        assert candidate["source_id"] == candidate["public_id"]
        assert candidate["generation_method"] == "template_heuristic_v1"

    @pytest.mark.anyio
    async def test_generate_is_deduplicated_on_regeneration(self, services):
        document, _source, _chunk = await _ready_document_with_approved_chunk(services)
        services["sft"].generate(document["public_id"], SftCandidateGenerationRequest(), "admin-1")
        second = services["sft"].generate(
            document["public_id"], SftCandidateGenerationRequest(), "admin-1"
        )
        statuses = {item["quality_status"] for item in second["items"]}
        assert "duplicate" in statuses

    @pytest.mark.anyio
    async def test_candidate_without_verified_rights_cannot_be_approved(self, services):
        document, source, _chunk = await _ready_document_with_approved_chunk(services)
        result = services["sft"].generate(
            document["public_id"], SftCandidateGenerationRequest(), "admin-1"
        )
        candidate = result["items"][0]
        assert candidate["rights_status"] == "pending"
        with pytest.raises(ValidationError, match="verified"):
            services["sft"].review(
                document["public_id"],
                candidate["public_id"],
                SftCandidateReviewAction(action="approve"),
                "admin-1",
            )

    @pytest.mark.anyio
    async def test_reject_action_does_not_require_verified_rights(self, services):
        document, _source, _chunk = await _ready_document_with_approved_chunk(services)
        result = services["sft"].generate(
            document["public_id"], SftCandidateGenerationRequest(), "admin-1"
        )
        candidate = result["items"][0]
        reviewed = services["sft"].review(
            document["public_id"],
            candidate["public_id"],
            SftCandidateReviewAction(action="reject"),
            "admin-1",
        )
        assert reviewed["items"][0]["quality_status"] == "rejected"

    @pytest.mark.anyio
    async def test_bulk_approve_enforces_batch_size_limit(self, services):
        document, _source, _chunk = await _ready_document_with_approved_chunk(services)
        services["sft"].settings.document_sft_bulk_approval_max_items = 1
        with pytest.raises(ValidationError, match="maximum allowed batch size"):
            services["sft"].bulk_approve(
                document["public_id"],
                SftBulkApprovalRequest(candidate_public_ids=["a", "b"], confirm=True),
                "admin-1",
            )


class TestSftExport:
    @pytest.mark.anyio
    async def test_export_requires_at_least_one_approved_candidate(self, services):
        document, _source, _chunk = await _ready_document_with_approved_chunk(services)
        services["sft"].generate(document["public_id"], SftCandidateGenerationRequest(), "admin-1")
        with pytest.raises(ValidationError, match="approved SFT candidates"):
            services["export"].export(document["public_id"], "admin-1")

    @pytest.mark.anyio
    async def test_export_produces_valid_jsonl_and_manifest_for_an_approved_candidate(
        self, services
    ):
        document, source, _chunk = await _ready_document_with_approved_chunk(
            services, verified_rights=True
        )
        result = services["sft"].generate(
            document["public_id"], SftCandidateGenerationRequest(), "admin-1"
        )
        candidate = result["items"][0]
        assert candidate["rights_status"] == "verified"
        services["sft"].review(
            document["public_id"],
            candidate["public_id"],
            SftCandidateReviewAction(action="approve"),
            "admin-1",
        )
        export = services["export"].export(document["public_id"], "admin-1")
        assert export["record_count"] == 1
        assert export["excluded_count"] == 0
        assert not Path(export["export_path"]).is_absolute()
        export_dir = services["export"].settings.resolved_document_sft_export_dir
        exported_file = export_dir / export["export_path"]
        lines = exported_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        import json

        record = json.loads(lines[0])
        assert set(record.keys()) == {
            "instruction", "context", "response", "input_language", "output_language",
            "task", "domain", "difficulty", "source_id", "rights_status",
        }
        assert record["rights_status"] == "verified"
        assert export["checksum_sha256"]
