"""Tests for text-data-only content classification (Task Finalization
§16/§17): text_only, image_without_usable_text (vision_required), and
table detection -- no vision model involved anywhere."""

from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.models.documents import ProcessRequest
from backend.services.document_content_classification_service import (
    DocumentContentClassificationService,
)
from backend.services.document_service import DocumentService

ADMIN_ID = "00000000-0000-0000-0000-000000000066"


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
    database_path = tmp_path / "classification.db"
    initialize_database(database_path)
    return Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )


@pytest.fixture
def documents(settings: Settings) -> DocumentService:
    return DocumentService(settings)


@pytest.fixture
def classification(settings: Settings) -> DocumentContentClassificationService:
    return DocumentContentClassificationService(settings)


class TestClassification:
    @pytest.mark.anyio
    async def test_ordinary_text_page_classified_text_only(self, documents, classification):
        upload_file = FakeUploadFile("sample.pdf", make_pdf("A perfectly ordinary text page."))
        document = await documents.upload(upload_file, "embedded_text", "en", ADMIN_ID)
        documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID)
        result = classification.classify_page(document["public_id"], 1, ADMIN_ID)
        assert result["content_type"] == "text_only"
        assert result["vision_required"] == 0

    @pytest.mark.anyio
    async def test_image_only_page_is_marked_vision_required(self, documents, classification):
        upload_file = FakeUploadFile("sample.pdf", make_pdf("short"))
        document = await documents.upload(upload_file, "embedded_text", "en", ADMIN_ID)
        documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID)
        # Simulate an image-bearing, text-sparse page directly at the
        # repository layer -- this test's job is to verify the
        # classification rule, not PDF image embedding mechanics.
        with classification.repository.transaction() as connection:
            document_row = classification.repository.document(connection, document["public_id"])
            connection.execute(
                "UPDATE document_pages SET image_count=1,cleaned_text='x' WHERE "
                "document_source_id=? AND page_number=1",
                (document_row["id"],),
            )
        result = classification.classify_page(document["public_id"], 1, ADMIN_ID)
        assert result["content_type"] == "image_without_usable_text"
        assert result["vision_required"] == 1

    @pytest.mark.anyio
    async def test_table_like_text_detected_without_a_vision_model(self, documents, classification):
        # Column gaps made of repeated spaces do not survive the existing
        # extraction pipeline's whitespace normalization -- pipe-separated
        # columns do, so this is what a real extracted table-like page
        # looks like by the time it reaches classification.
        table_text = (
            "Name | Age | City\n"
            "Kumar | 30 | Chennai\n"
            "Priya | 28 | Madurai\n"
            "Arun | 35 | Coimbatore"
        )
        upload_file = FakeUploadFile("sample.pdf", make_pdf(table_text))
        document = await documents.upload(upload_file, "embedded_text", "en", ADMIN_ID)
        documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID)
        result = classification.classify_page(document["public_id"], 1, ADMIN_ID)
        assert result["content_type"] == "table"

    @pytest.mark.anyio
    async def test_classify_document_and_summary_cover_every_page(self, documents, classification):
        upload_file = FakeUploadFile("sample.pdf", make_pdf("Page one text.", "Page two text."))
        document = await documents.upload(upload_file, "embedded_text", "en", ADMIN_ID)
        documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID)
        summary = classification.classify_document(document["public_id"], ADMIN_ID)
        assert summary["by_content_type"].get("text_only") == 2
        assert summary["vision_required_count"] == 0
