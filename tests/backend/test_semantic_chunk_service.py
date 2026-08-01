from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import DataSourceCreate
from backend.models.documents import ProcessRequest
from backend.services.data_source_service import SourceRegistryService
from backend.services.document_service import DocumentService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import (
    ChunkConflictService,
    SemanticChunkQualityService,
    SemanticChunkReviewService,
    SemanticChunkService,
)


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
    database_path = tmp_path / "chunk_service.db"
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
    return {
        "documents": DocumentService(settings),
        "workspace": PDFResearchWorkspaceService(settings),
        "review": DocumentPageReviewService(settings),
        "chunks": SemanticChunkService(settings),
        "chunk_review": SemanticChunkReviewService(settings),
        "quality": SemanticChunkQualityService(settings),
        "conflicts": ChunkConflictService(settings),
        "source_registry": SourceRegistryService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
    }


async def _upload_document(services, *, texts=("First paragraph here.\n\nSecond paragraph here.",)):
    upload_file = FakeUploadFile("sample.pdf", make_pdf(*texts))
    return await services["documents"].upload(upload_file, "embedded_text", "en", "admin-1")


_source_counter = 0


def _human_source(services, code=None):
    global _source_counter
    _source_counter += 1
    return services["source_registry"].create(
        DataSourceCreate(
            source_code=code or f"SRC-CHUNK-SVC-{_source_counter:04d}",
            title="Test source",
            source_type="document_derived",
        ),
        "admin-1",
    )


async def _ready_document(services):
    document = await _upload_document(services)
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
    )
    # A genuine two-paragraph blank-line separator does not survive a
    # PyMuPDF insert_text()/get_text() round-trip (verified directly --
    # it collapses to a single newline), so the paragraph-boundary
    # generator is exercised against a realistic OCR-corrected page text
    # via the existing edit_page() path instead, exactly as an admin
    # fixing up extracted text would produce it.
    services["documents"].edit_page(
        document["public_id"], 1, "First paragraph here.\n\nSecond paragraph here.", "admin-1"
    )
    source = _human_source(services)
    services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
    services["review"].approve(document["public_id"], 1, "admin-1")
    return document, source


class TestGeneration:
    @pytest.mark.anyio
    async def test_generate_requires_a_linked_source(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        with pytest.raises(ValidationError, match="linked source"):
            services["chunks"].generate(document["public_id"], "admin-1")

    @pytest.mark.anyio
    async def test_generate_requires_at_least_one_approved_page(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        source = _human_source(services)
        services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
        with pytest.raises(ValidationError, match="approved"):
            services["chunks"].generate(document["public_id"], "admin-1")

    @pytest.mark.anyio
    async def test_generate_creates_one_chunk_per_paragraph_with_lineage(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        assert result["generated_chunk_count"] == 2
        assert result["partial_document"] is False
        chunk = services["chunks"].chunk(result["chunk_public_ids"][0])
        assert chunk["chunk_type"] == "paragraph"
        revision = chunk["active_revision"]
        assert revision["page_number"] == 1
        assert revision["generation_method"] == "paragraph_boundary"
        assert revision["confidence"] is None

    @pytest.mark.anyio
    async def test_generate_labels_partial_document_when_some_pages_unapproved(self, services):
        document = await _upload_document(
            services, texts=("Page one paragraph.", "Page two paragraph.")
        )
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        source = _human_source(services)
        services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
        services["review"].approve(document["public_id"], 1, "admin-1")
        result = services["chunks"].generate(document["public_id"], "admin-1")
        assert result["partial_document"] is True
        assert result["excluded_page_count"] == 1


class TestSplitMergeBoundary:
    @pytest.mark.anyio
    async def test_split_a_generated_chunk_preserves_combined_text(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        original = services["chunks"].chunk(chunk_id)
        original_text = original["active_revision"]["text"]
        start = original["active_revision"]["start_locator"]["offset"]
        midpoint = start + len(original_text) // 2
        split_result = services["chunks"].split(chunk_id, midpoint, "admin-1")
        combined = "".join(c["active_revision"]["text"] for c in split_result["chunks"])
        assert combined == original_text

    @pytest.mark.anyio
    async def test_split_an_approved_chunk_is_rejected(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        services["chunk_review"].submit_review(chunk_id, "admin-1")
        services["chunk_review"].approve(chunk_id, "admin-1")
        chunk = services["chunks"].chunk(chunk_id)
        start = chunk["active_revision"]["start_locator"]["offset"]
        text_len = len(chunk["active_revision"]["text"])
        with pytest.raises(ValidationError, match="approved chunk cannot be split"):
            services["chunks"].split(chunk_id, start + text_len // 2, "admin-1")

    @pytest.mark.anyio
    async def test_merge_two_generated_chunks(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        first_id, second_id = result["chunk_public_ids"]
        first_before = services["chunks"].chunk(first_id)["active_revision"]["text"]
        second_before = services["chunks"].chunk(second_id)["active_revision"]["text"]
        merged = services["chunks"].merge(first_id, second_id, "admin-1")
        assert merged["active_revision"]["text"].startswith(first_before[:5])
        assert second_before[:5] in merged["active_revision"]["text"]
        excluded = services["chunks"].chunk(second_id)
        assert excluded["status"] == "excluded"

    @pytest.mark.anyio
    async def test_merge_across_documents_is_rejected(self, services):
        document_a, _ = await _ready_document(services)
        document_b, _ = await _ready_document(services)
        result_a = services["chunks"].generate(document_a["public_id"], "admin-1")
        result_b = services["chunks"].generate(document_b["public_id"], "admin-1")
        with pytest.raises(ValidationError, match="different documents"):
            services["chunks"].merge(
                result_a["chunk_public_ids"][0], result_b["chunk_public_ids"][0], "admin-1"
            )


class TestClassificationAndHierarchy:
    @pytest.mark.anyio
    async def test_classify_updates_chunk_type_and_logs_event(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        updated = services["chunks"].classify(chunk_id, "admin-1", chunk_type="heading")
        assert updated["chunk_type"] == "heading"
        history = services["chunks"].history(chunk_id)
        assert any(e["event_type"] == "chunk_classified" for e in history["events"])

    @pytest.mark.anyio
    async def test_assign_parent_and_cycle_prevention(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        parent_id, child_id = result["chunk_public_ids"]
        services["chunks"].assign_parent(child_id, parent_id, "admin-1")
        child = services["chunks"].chunk(child_id)
        assert child is not None
        with pytest.raises(ValidationError, match="cycle"):
            services["chunks"].assign_parent(parent_id, child_id, "admin-1")

    @pytest.mark.anyio
    async def test_reorder_chunks(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        reversed_order = list(reversed(result["chunk_public_ids"]))
        outcome = services["chunks"].reorder(document["public_id"], reversed_order, "admin-1")
        assert outcome["reordered"] == 2
        first_chunk = services["chunks"].chunk(reversed_order[0])
        assert first_chunk["reading_order"] == 1


class TestReviewLifecycle:
    @pytest.mark.anyio
    async def test_draft_cannot_be_approved_directly(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        with pytest.raises(ValidationError, match="cannot transition"):
            services["chunk_review"].approve(chunk_id, "admin-1")

    @pytest.mark.anyio
    async def test_full_review_cycle_to_approved(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        services["chunk_review"].submit_review(chunk_id, "admin-1")
        approved = services["chunk_review"].approve(chunk_id, "admin-1")
        assert approved["status"] == "approved"
        history = services["chunk_review"].review_history(chunk_id)
        assert len(history["items"]) == 1

    @pytest.mark.anyio
    async def test_editing_an_approved_chunk_reopens_it(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        services["chunk_review"].submit_review(chunk_id, "admin-1")
        services["chunk_review"].approve(chunk_id, "admin-1")
        services["chunks"].edit_text(chunk_id, "First paragraph corrected.", "admin-1")
        reopened = services["chunks"].chunk(chunk_id)
        assert reopened["status"] == "needs_review"
        history = services["chunks"].history(chunk_id)
        assert len(history["revisions"]) == 2

    @pytest.mark.anyio
    async def test_split_requires_a_correction_request_first_when_approved(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        services["chunk_review"].submit_review(chunk_id, "admin-1")
        services["chunk_review"].approve(chunk_id, "admin-1")
        chunk = services["chunks"].chunk(chunk_id)
        start = chunk["active_revision"]["start_locator"]["offset"]
        text_len = len(chunk["active_revision"]["text"])
        with pytest.raises(ValidationError, match="approved chunk cannot be split"):
            services["chunks"].split(chunk_id, start + max(1, text_len // 2), "admin-1")


class TestQualityAndConflicts:
    @pytest.mark.anyio
    async def test_assess_a_clean_generated_chunk(self, services):
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        chunk_id = result["chunk_public_ids"][0]
        quality = services["quality"].assess(chunk_id)
        assert "MISSING_SOURCE_LINEAGE" not in quality["blocking_issues"]

    @pytest.mark.anyio
    async def test_duplicate_check_finds_exact_duplicate(self, services):
        document, source = await _ready_document(services)
        services["chunks"].create_manual_chunk(
            document["public_id"],
            text="First paragraph here.",
            chunk_type="paragraph",
            page_number=1,
            language="en",
            admin_id="admin-1",
        )
        services["chunks"].create_manual_chunk(
            document["public_id"],
            text="First paragraph here.",
            chunk_type="paragraph",
            page_number=1,
            language="en",
            admin_id="admin-1",
        )
        chunks = services["chunks"].list_chunks(document["public_id"])
        second_chunk_id = chunks["items"][-1]["public_id"]
        duplicate = services["quality"].duplicate_check(second_chunk_id)
        assert duplicate["exact_duplicate_chunk_public_id"] is not None

    @pytest.mark.anyio
    async def test_coverage_report_reflects_clean_generation(self, services):
        document, _source = await _ready_document(services)
        services["chunks"].generate(document["public_id"], "admin-1")
        report = services["conflicts"].coverage_report(document["public_id"])
        assert "1" in report

    @pytest.mark.anyio
    async def test_coverage_report_ignores_a_chunk_excluded_by_merge(self, services):
        # A merge leaves the absorbed chunk's stale locator behind (status
        # 'excluded'); the coverage report must not count that as a real
        # overlap against the chunk that replaced it.
        document, _source = await _ready_document(services)
        result = services["chunks"].generate(document["public_id"], "admin-1")
        first_id, second_id = result["chunk_public_ids"]
        services["chunks"].merge(first_id, second_id, "admin-1")
        report = services["conflicts"].coverage_report(document["public_id"])
        assert report["1"]["overlap_count"] == 0
        assert report["1"]["issues"] == []

    @pytest.mark.anyio
    async def test_duplicate_check_ignores_an_excluded_chunk(self, services):
        document, _source = await _ready_document(services)
        first = services["chunks"].create_manual_chunk(
            document["public_id"], text="Repeated text.", chunk_type="paragraph",
            page_number=1, language="en", admin_id="admin-1",
        )
        second = services["chunks"].create_manual_chunk(
            document["public_id"], text="Repeated text.", chunk_type="paragraph",
            page_number=1, language="en", admin_id="admin-1",
        )
        services["chunks"].archive(first["public_id"], "admin-1")
        duplicate = services["quality"].duplicate_check(second["public_id"])
        assert duplicate["exact_duplicate_chunk_public_id"] is None
