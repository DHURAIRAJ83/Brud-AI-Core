from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import (
    DataSourceCreate,
    SourceRightsUpsert,
    VerificationActionRequest,
)
from backend.models.documents import ProcessRequest
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.document_service import DocumentService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService
from backend.services.structured_record_service import StructuredRecordCandidateService


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
    database_path = tmp_path / "structured_service.db"
    initialize_database(database_path)
    return Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )


@pytest.fixture
def services(settings: Settings):
    source_repo = DataSourceRepository(settings.resolved_database_path)
    return {
        "documents": DocumentService(settings),
        "workspace": PDFResearchWorkspaceService(settings),
        "review": DocumentPageReviewService(settings),
        "chunks": SemanticChunkService(settings),
        "chunk_review": SemanticChunkReviewService(settings),
        "records": StructuredRecordCandidateService(settings),
        "source_registry": SourceRegistryService(source_repo, settings),
        "source_rights": SourceRightsService(source_repo, settings),
    }


_source_counter = 0


def _human_source(services, code=None):
    global _source_counter
    _source_counter += 1
    return services["source_registry"].create(
        DataSourceCreate(
            source_code=code or f"SRC-STRUCT-SVC-{_source_counter:04d}",
            title="Test source",
            source_type="document_derived",
        ),
        "admin-1",
    )


def _allow_all_rights(services, source_public_id):
    services["source_rights"].upsert(
        source_public_id,
        SourceRightsUpsert(
            rights_status="licensed",
            rag_use_allowed=True,
            training_use_allowed=True,
            evaluation_use_allowed=True,
            redistribution_allowed=True,
        ),
        "admin-1",
    )
    services["source_rights"].submit_review(source_public_id, "admin-1")
    services["source_rights"].verify(
        source_public_id, VerificationActionRequest(action="document_verify"), "admin-1"
    )


async def _approved_chunk(services, *, with_rights=True, text="வணக்கம் தமிழ்."):
    upload_file = FakeUploadFile("sample.pdf", make_pdf("placeholder"))
    document = await services["documents"].upload(upload_file, "embedded_text", "en", "admin-1")
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
    )
    services["documents"].edit_page(document["public_id"], 1, text, "admin-1")
    source = _human_source(services)
    if with_rights:
        _allow_all_rights(services, source["public_id"])
    services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
    services["review"].approve(document["public_id"], 1, "admin-1")
    result = services["chunks"].generate(document["public_id"], "admin-1")
    chunk_id = result["chunk_public_ids"][0]
    services["chunk_review"].submit_review(chunk_id, "admin-1")
    services["chunk_review"].approve(chunk_id, "admin-1")
    return document, source, chunk_id


class TestCreateFromChunks:
    @pytest.mark.anyio
    async def test_create_dictionary_entry_from_an_approved_chunk(self, services):
        _document, _source, chunk_id = await _approved_chunk(services)
        candidate = services["records"].create_from_chunks(
            record_type="dictionary_entry",
            chunk_public_ids=[chunk_id],
            fields={"word": "வணக்கம்", "meanings_json": '["hello", "greeting"]'},
            admin_id="admin-1",
        )
        assert candidate["record_type"] == "dictionary_entry"
        assert candidate["status"] == "draft"
        assert candidate["active_revision"]["word"] == "வணக்கம்"
        assert len(candidate["chunks"]) == 1

    @pytest.mark.anyio
    async def test_create_requires_reviewed_chunks(self, services):
        upload_file = FakeUploadFile("sample.pdf", make_pdf("placeholder"))
        document = await services["documents"].upload(upload_file, "embedded_text", "en", "admin-1")
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        services["documents"].edit_page(document["public_id"], 1, "Some text.", "admin-1")
        source = _human_source(services)
        services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
        services["review"].approve(document["public_id"], 1, "admin-1")
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        # chunk is still in status "draft" -- never submitted for review
        with pytest.raises(ValidationError, match="must be reviewed"):
            services["records"].create_from_chunks(
                record_type="plain_text",
                chunk_public_ids=[chunk_id],
                fields={"text": "Some text."},
                admin_id="admin-1",
            )


class TestReviewAndRevise:
    @pytest.mark.anyio
    async def test_revise_creates_a_new_revision_and_reopens_if_approved(self, services):
        _document, _source, chunk_id = await _approved_chunk(services)
        candidate = services["records"].create_from_chunks(
            record_type="dictionary_entry",
            chunk_public_ids=[chunk_id],
            fields={"word": "வணக்கம்", "meanings_json": '["hello"]'},
            admin_id="admin-1",
        )
        candidate_id = candidate["public_id"]
        services["records"].submit_review(candidate_id, "admin-1")
        approved = services["records"].review(
            candidate_id, review_status="approved", comments="looks good", admin_id="admin-1"
        )
        assert approved["status"] == "approved"
        revised = services["records"].revise(
            candidate_id,
            fields={"word": "வணக்கம்", "meanings_json": '["hello", "greetings"]'},
            change_summary="added a second sense",
            admin_id="admin-1",
        )
        assert revised["status"] == "needs_review"
        history = services["records"].history(candidate_id)
        assert len(history["revisions"]) == 2

    @pytest.mark.anyio
    async def test_draft_cannot_be_approved_directly(self, services):
        _document, _source, chunk_id = await _approved_chunk(services)
        candidate = services["records"].create_from_chunks(
            record_type="plain_text",
            chunk_public_ids=[chunk_id],
            fields={"text": "வணக்கம் தமிழ்."},
            admin_id="admin-1",
        )
        with pytest.raises(ValidationError, match="cannot transition"):
            services["records"].review(
                candidate["public_id"], review_status="approved", comments="", admin_id="admin-1"
            )


class TestUsageAndExport:
    @pytest.mark.anyio
    async def test_usage_check_blocks_training_without_rights(self, services):
        _document, _source, chunk_id = await _approved_chunk(services, with_rights=False)
        candidate = services["records"].create_from_chunks(
            record_type="plain_text",
            chunk_public_ids=[chunk_id],
            fields={"text": "வணக்கம் தமிழ்."},
            admin_id="admin-1",
        )
        services["records"].submit_review(candidate["public_id"], "admin-1")
        services["records"].review(
            candidate["public_id"], review_status="approved", comments="", admin_id="admin-1"
        )
        decision = services["records"].usage_check(candidate["public_id"], "training")
        assert decision["allowed"] is False

    @pytest.mark.anyio
    async def test_usage_check_allows_training_with_full_rights(self, services):
        _document, _source, chunk_id = await _approved_chunk(services, with_rights=True)
        candidate = services["records"].create_from_chunks(
            record_type="plain_text",
            chunk_public_ids=[chunk_id],
            fields={"text": "வணக்கம் தமிழ்."},
            admin_id="admin-1",
        )
        services["records"].submit_review(candidate["public_id"], "admin-1")
        services["records"].review(
            candidate["public_id"], review_status="approved", comments="", admin_id="admin-1"
        )
        decision = services["records"].usage_check(candidate["public_id"], "training")
        assert decision["allowed"] is True

    @pytest.mark.anyio
    async def test_export_requires_approval(self, services):
        _document, _source, chunk_id = await _approved_chunk(services)
        candidate = services["records"].create_from_chunks(
            record_type="plain_text",
            chunk_public_ids=[chunk_id],
            fields={"text": "வணக்கம் தமிழ்."},
            admin_id="admin-1",
        )
        with pytest.raises(ValidationError, match="only an approved"):
            services["records"].export_to_dataset(candidate["public_id"], "admin-1")

    @pytest.mark.anyio
    async def test_export_to_dataset_succeeds_and_prevents_duplicate_export(self, services):
        _document, _source, chunk_id = await _approved_chunk(services)
        candidate = services["records"].create_from_chunks(
            record_type="plain_text",
            chunk_public_ids=[chunk_id],
            fields={"text": "வணக்கம் தமிழ்."},
            admin_id="admin-1",
        )
        services["records"].submit_review(candidate["public_id"], "admin-1")
        services["records"].review(
            candidate["public_id"], review_status="approved", comments="", admin_id="admin-1"
        )
        exported = services["records"].export_to_dataset(candidate["public_id"], "admin-1")
        assert exported["exported_dataset_record_public_id"] is not None
        with pytest.raises(ConflictError, match="already exported"):
            services["records"].export_to_dataset(candidate["public_id"], "admin-1")

    @pytest.mark.anyio
    async def test_rag_chunk_cannot_be_exported_to_dataset(self, services):
        _document, _source, chunk_id = await _approved_chunk(services)
        candidate = services["records"].create_from_chunks(
            record_type="rag_chunk",
            chunk_public_ids=[chunk_id],
            fields={"text": "வணக்கம் தமிழ்."},
            admin_id="admin-1",
        )
        services["records"].submit_review(candidate["public_id"], "admin-1")
        services["records"].review(
            candidate["public_id"], review_status="approved", comments="", admin_id="admin-1"
        )
        with pytest.raises(ValidationError, match="RAG handoff"):
            services["records"].export_to_dataset(candidate["public_id"], "admin-1")

    @pytest.mark.anyio
    async def test_rag_handoff_marks_candidate_ready(self, services):
        _document, _source, chunk_id = await _approved_chunk(services)
        candidate = services["records"].create_from_chunks(
            record_type="rag_chunk",
            chunk_public_ids=[chunk_id],
            fields={"text": "வணக்கம் தமிழ்."},
            admin_id="admin-1",
        )
        services["records"].submit_review(candidate["public_id"], "admin-1")
        services["records"].review(
            candidate["public_id"], review_status="approved", comments="", admin_id="admin-1"
        )
        handed_off = services["records"].create_rag_candidate(candidate["public_id"], "admin-1")
        assert handed_off["rag_handoff_at"] is not None


class TestConflictDetection:
    @pytest.mark.anyio
    async def test_conflicting_dictionary_senses_are_flagged(self, services):
        _document, _source, chunk_id = await _approved_chunk(services)
        first = services["records"].create_from_chunks(
            record_type="dictionary_entry",
            chunk_public_ids=[chunk_id],
            fields={"word": "vanakkam", "meanings_json": '["hello"]'},
            admin_id="admin-1",
        )
        services["records"].submit_review(first["public_id"], "admin-1")
        services["records"].review(
            first["public_id"], review_status="approved", comments="", admin_id="admin-1"
        )
        second = services["records"].create_from_chunks(
            record_type="dictionary_entry",
            chunk_public_ids=[chunk_id],
            fields={"word": "vanakkam", "meanings_json": '["a respectful greeting"]'},
            admin_id="admin-1",
        )
        report = services["records"].conflict_check(second["public_id"])
        assert report["conflict"]["type"] == "alternate_sense"
