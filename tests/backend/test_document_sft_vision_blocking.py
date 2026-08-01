"""Production Integration §13: vision_required content classification must
block text-only SFT generation for the pages it applies to, while leaving
generation on other pages of the same document unaffected."""

from pathlib import Path
from uuid import uuid4

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.documents import DocumentRepository
from backend.models.data_sources import DataSourceCreate, SourceRightsUpsert
from backend.models.documents import ProcessRequest, SftCandidateGenerationRequest
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.document_service import DocumentService
from backend.services.document_sft_candidate_service import DocumentSftCandidateGenerationService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService

ADMIN_ID = "00000000-0000-0000-0000-000000000088"


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
    database_path = tmp_path / "vision_blocking.db"
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
def services(settings: Settings):
    return {
        "documents": DocumentService(settings),
        "workspace": PDFResearchWorkspaceService(settings),
        "review": DocumentPageReviewService(settings),
        "chunks": SemanticChunkService(settings),
        "chunk_review": SemanticChunkReviewService(settings),
        "sft": DocumentSftCandidateGenerationService(settings),
        "source_registry": SourceRegistryService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
        "rights": SourceRightsService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
    }


def _mark_page_vision_required(
    settings: Settings, document_public_id: str, page_number: int
) -> None:
    repository = DocumentRepository(settings.resolved_database_path)
    with repository.transaction() as connection:
        document = repository.document(connection, document_public_id)
        connection.execute(
            """INSERT INTO document_content_classifications(
                public_id,document_source_id,page_number,content_type,caption_text,
                vision_required
            ) VALUES (?,?,?,?,?,1)""",
            (str(uuid4()), document["id"], page_number, "image_without_usable_text", ""),
        )


async def _two_page_document_with_definitions(services):
    upload_file = FakeUploadFile("sample.pdf", make_pdf("Page one text.", "Page two text."))
    document = await services["documents"].upload(upload_file, "embedded_text", "en", ADMIN_ID)
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID
    )
    source = services["source_registry"].create(
        DataSourceCreate(
            source_code=f"SRC-VIS-{document['public_id'][:8]}", title="s",
            source_type="document_derived",
        ),
        ADMIN_ID,
    )
    services["rights"].upsert(
        source["public_id"],
        SourceRightsUpsert(rights_status="public_domain", training_use_allowed=True),
        ADMIN_ID,
    )
    services["workspace"].link_source(document["public_id"], source["public_id"], ADMIN_ID)
    services["review"].approve(document["public_id"], 1, ADMIN_ID)
    services["review"].approve(document["public_id"], 2, ADMIN_ID)
    blocked_chunk = services["chunks"].create_manual_chunk(
        document["public_id"], text="Blocked term definition.", chunk_type="definition",
        page_number=1, language="en", admin_id=ADMIN_ID,
    )
    allowed_chunk = services["chunks"].create_manual_chunk(
        document["public_id"], text="Allowed term definition.", chunk_type="definition",
        page_number=2, language="en", admin_id=ADMIN_ID,
    )
    for chunk in (blocked_chunk, allowed_chunk):
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)
    return document["public_id"]


class TestVisionRequiredBlocksGeneration:
    @pytest.mark.anyio
    async def test_chunk_on_vision_required_page_is_excluded_and_reported(self, services, settings):
        document_public_id = await _two_page_document_with_definitions(services)
        _mark_page_vision_required(settings, document_public_id, 1)

        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )

        pages_generated = {item["source_page_start"] for item in result["items"]}
        assert 1 not in pages_generated
        assert 2 in pages_generated
        assert len(result["vision_blocked"]) == 1
        blocked = result["vision_blocked"][0]
        assert blocked["page_number"] == 1
        assert blocked["content_classification"] == "image_without_usable_text"
        assert blocked["review_status"] == "vision_required"
        assert blocked["blocking_reason"]

    @pytest.mark.anyio
    async def test_generation_still_succeeds_when_no_page_is_vision_required(self, services):
        document_public_id = await _two_page_document_with_definitions(services)

        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )

        pages_generated = {item["source_page_start"] for item in result["items"]}
        assert pages_generated == {1, 2}
        assert result["vision_blocked"] == []

    @pytest.mark.anyio
    async def test_generation_blocked_entirely_when_every_approved_chunk_is_vision_required(
        self, services, settings
    ):
        document_public_id = await _two_page_document_with_definitions(services)
        _mark_page_vision_required(settings, document_public_id, 1)
        _mark_page_vision_required(settings, document_public_id, 2)

        from backend.database.repositories.base import ValidationError

        with pytest.raises(ValidationError, match="vision_required"):
            services["sft"].generate(
                document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
            )
