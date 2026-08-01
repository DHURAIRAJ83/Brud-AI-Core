from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import DataSourceCreate
from backend.models.documents import ProcessRequest, SegmentRequest
from backend.services.data_source_service import SourceRegistryService
from backend.services.document_service import DocumentService
from backend.services.document_workspace_service import (
    DocumentCleanupService,
    DocumentPageReviewService,
    DocumentPageRevisionService,
    PDFResearchWorkspaceService,
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
    database_path = tmp_path / "workspace.db"
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
        "workspace": PDFResearchWorkspaceService(settings),
        "revisions": DocumentPageRevisionService(settings),
        "review": DocumentPageReviewService(settings),
        "cleanup": DocumentCleanupService(settings),
        "documents": DocumentService(settings),
        "source_registry": SourceRegistryService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
    }


async def _upload_document(
    services, *, texts=("First page text for the workspace.", "Second page text here.")
):
    upload_file = FakeUploadFile("sample.pdf", make_pdf(*texts))
    return await services["documents"].upload(upload_file, "embedded_text", "en", "admin-1")


def _human_source(services, code="SRC-DOC-WORKSPACE-0001"):
    return services["source_registry"].create(
        DataSourceCreate(source_code=code, title="Test source", source_type="document_derived"),
        "admin-1",
    )


class TestPDFResearchWorkspaceService:
    @pytest.mark.anyio
    async def test_workspace_reports_unlinked_and_not_ready_for_fresh_document(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        workspace = services["workspace"].workspace(document["public_id"])
        assert workspace["source_status"] == "unlinked"
        assert workspace["readiness"] == "not_ready"
        assert workspace["review_status_counts"]["pending"] == 2

    @pytest.mark.anyio
    async def test_link_source_and_readiness_transitions(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        source = _human_source(services)
        services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
        workspace = services["workspace"].workspace(document["public_id"])
        assert workspace["source_status"] == "linked"
        assert workspace["readiness"] == "not_ready"  # no page approved yet

        services["review"].approve(document["public_id"], 1, "admin-1")
        services["review"].approve(document["public_id"], 2, "admin-1")
        workspace = services["workspace"].workspace(document["public_id"])
        assert workspace["readiness"] == "ready_for_segmentation"

    @pytest.mark.anyio
    async def test_relinking_source_replaces_previous_link(self, services):
        document = await _upload_document(services)
        source_a = _human_source(services, code="SRC-DOC-A")
        source_b = _human_source(services, code="SRC-DOC-B")
        services["workspace"].link_source(document["public_id"], source_a["public_id"], "admin-1")
        services["workspace"].link_source(document["public_id"], source_b["public_id"], "admin-1")
        workspace = services["workspace"].workspace(document["public_id"])
        assert workspace["source"]["public_id"] == source_b["public_id"]

    @pytest.mark.anyio
    async def test_send_to_segmentation_blocked_when_not_ready(self, services):
        document = await _upload_document(services)
        with pytest.raises(ValidationError):
            services["workspace"].send_to_segmentation(
                document["public_id"],
                SegmentRequest(mode="page_as_pretrain", language="en"),
                "admin-1",
            )

    @pytest.mark.anyio
    async def test_render_page_image_returns_png_bytes(self, services):
        document = await _upload_document(services)
        image_bytes = services["workspace"].render_page_image(document["public_id"], 1)
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.anyio
    async def test_extract_with_history_records_extraction_snapshot(self, services):
        document = await _upload_document(services)
        services["workspace"].extract_with_history(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        history = services["workspace"].extraction_history(document["public_id"], 1)
        assert len(history["items"]) == 1
        assert history["items"][0]["extraction_method"] == "embedded"
        assert "document_page_id" not in history["items"][0]


class TestDocumentPageRevisionService:
    @pytest.mark.anyio
    async def test_save_draft_creates_revision_without_touching_raw_text(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        before = services["documents"].page(document["public_id"], 1)
        services["revisions"].save_draft(document["public_id"], 1, "Corrected text.", "admin-1")
        after = services["documents"].page(document["public_id"], 1)
        assert after["raw_text"] == before["raw_text"]
        assert after["cleaned_text"] == "Corrected text."

    @pytest.mark.anyio
    async def test_editing_approved_page_reopens_to_needs_correction_and_preserves_history(
        self, services
    ):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        source = _human_source(services)
        services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
        # Approved directly from the auto-extracted text -- approving
        # snapshots that text as revision 1 ("raw extraction explicitly
        # accepted"), even though no manual edit ever happened first.
        approved_page = services["review"].approve(document["public_id"], 1, "admin-1")
        approved_text = approved_page["cleaned_text"]

        services["revisions"].save_draft(
            document["public_id"], 1, "Corrected after approval.", "admin-2"
        )
        page = services["documents"].page(document["public_id"], 1)
        assert page["review_status"] == "needs_correction"

        revisions = services["revisions"].revisions(document["public_id"], 1)
        assert len(revisions["items"]) == 2
        assert revisions["approved_revision_number"] == 1
        # Revision 1 (the approved snapshot) is preserved untouched even
        # though the page's *current* cleaned_text has since moved on.
        preserved = next(r for r in revisions["items"] if r["revision_number"] == 1)
        assert preserved["cleaned_text"] == approved_text
        latest = next(r for r in revisions["items"] if r["revision_number"] == 2)
        assert latest["cleaned_text"] == "Corrected after approval."

    @pytest.mark.anyio
    async def test_restore_revision_creates_new_revision_matching_old_content(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        services["revisions"].save_draft(document["public_id"], 1, "First correction.", "admin-1")
        services["revisions"].save_draft(document["public_id"], 1, "Second correction.", "admin-1")
        services["revisions"].restore_revision(document["public_id"], 1, 1, "admin-1")
        page = services["documents"].page(document["public_id"], 1)
        assert page["cleaned_text"] == "First correction."
        revisions = services["revisions"].revisions(document["public_id"], 1)
        assert len(revisions["items"]) == 3

    @pytest.mark.anyio
    async def test_excluded_page_cannot_be_edited(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        services["review"].exclude(document["public_id"], 1, "admin-1")
        with pytest.raises(ValidationError):
            services["revisions"].save_draft(document["public_id"], 1, "Should fail.", "admin-1")


class TestDocumentPageReviewService:
    @pytest.mark.anyio
    async def test_approve_requires_source_link_and_nonempty_text(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        with pytest.raises(ValidationError):
            services["review"].approve(document["public_id"], 1, "admin-1")

        source = _human_source(services)
        services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
        approved = services["review"].approve(document["public_id"], 1, "admin-1")
        assert approved["review_status"] == "approved"

    @pytest.mark.anyio
    async def test_invalid_transition_raises_validation_error(self, services):
        document = await _upload_document(services)
        source = _human_source(services)
        services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
        services["review"].exclude(document["public_id"], 1, "admin-1")
        with pytest.raises(ValidationError):
            services["review"].approve(document["public_id"], 1, "admin-1")

    @pytest.mark.anyio
    async def test_reopen_excluded_page(self, services):
        document = await _upload_document(services)
        services["review"].exclude(document["public_id"], 1, "admin-1")
        reopened = services["review"].reopen(document["public_id"], 1, "admin-1")
        assert reopened["review_status"] == "pending"

    @pytest.mark.anyio
    async def test_review_events_and_summary(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        source = _human_source(services)
        services["workspace"].link_source(document["public_id"], source["public_id"], "admin-1")
        services["review"].approve(document["public_id"], 1, "admin-1")
        services["review"].reject(document["public_id"], 2, "admin-1", "not usable")

        events = services["review"].review_events(document["public_id"], 1)
        assert len(events["items"]) == 1
        assert events["items"][0]["action"] == "approve"

        summary = services["review"].review_summary(document["public_id"])
        assert summary["review_status_counts"]["approved"] == 1
        assert summary["review_status_counts"]["rejected"] == 1


class TestDocumentCleanupService:
    @pytest.mark.anyio
    async def test_suggestions_and_apply(self, services):
        document = await _upload_document(services)
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        services["revisions"].save_draft(
            document["public_id"], 1, "hello    world with bro-\nken text", "admin-1"
        )
        suggestions = services["cleanup"].suggestions(document["public_id"], 1)
        assert len(suggestions["items"]) > 0
        result = services["cleanup"].apply_suggestions(
            document["public_id"], 1, suggestions["items"], "admin-1"
        )
        assert "  " not in result["cleaned_text"]

    @pytest.mark.anyio
    async def test_detect_and_bulk_apply_repeated_elements(self, services):
        document = await _upload_document(
            services,
            texts=tuple(f"Confidential Draft\npage body number {i}" for i in range(1, 6)),
        )
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        detected = services["cleanup"].detect_repeated_elements(document["public_id"])
        assert len(detected["items"]) >= 1
        element = detected["items"][0]
        assert element["status"] == "suggested"

        with pytest.raises(ValidationError):
            services["cleanup"].review_repeated_element(
                document["public_id"], element["public_id"], "apply_all", "admin-1", confirm=False
            )

        updated = services["cleanup"].review_repeated_element(
            document["public_id"], element["public_id"], "apply_all", "admin-1", confirm=True
        )
        assert updated["status"] == "applied"
        page = services["documents"].page(document["public_id"], 1)
        assert "confidential draft" not in (page["cleaned_text"] or "").casefold()

    @pytest.mark.anyio
    async def test_accept_and_reject_do_not_mutate_page_content(self, services):
        document = await _upload_document(
            services,
            texts=tuple(f"Static Header\nunique body {i}" for i in range(1, 5)),
        )
        services["documents"].process(
            document["public_id"], ProcessRequest(strategy="embedded_text"), "admin-1"
        )
        detected = services["cleanup"].detect_repeated_elements(document["public_id"])
        element = detected["items"][0]
        before = services["documents"].page(document["public_id"], 1)["cleaned_text"]
        services["cleanup"].review_repeated_element(
            document["public_id"], element["public_id"], "accept", "admin-1"
        )
        after = services["documents"].page(document["public_id"], 1)["cleaned_text"]
        assert before == after
