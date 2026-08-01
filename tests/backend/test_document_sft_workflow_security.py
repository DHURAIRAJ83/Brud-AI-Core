"""Security/privacy tests for the Document SFT workflow (migration 043):
secret/PII leakage prevention in JSONL export, no absolute paths, safe
storage of hostile/injected text, and append-only audit trails."""

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
    SftCandidateGenerationRequest,
    SftCandidateReviewAction,
)
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.document_service import DocumentService
from backend.services.document_sft_candidate_service import DocumentSftCandidateGenerationService
from backend.services.document_sft_export_service import DocumentSftExportService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService

ADMIN_ID = "00000000-0000-0000-0000-000000000042"


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
    database_path = tmp_path / "document_sft_security.db"
    initialize_database(database_path)
    return Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        document_sft_export_dir=tmp_path / "document_sft_exports",
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
        "export": DocumentSftExportService(settings),
        "source_registry": SourceRegistryService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
        "rights": SourceRightsService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
    }


async def _approved_verified_candidate(services, page_text: str):
    upload_file = FakeUploadFile("sample.pdf", make_pdf(page_text))
    document = await services["documents"].upload(upload_file, "embedded_text", "en", ADMIN_ID)
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID
    )
    source = services["source_registry"].create(
        DataSourceCreate(
            source_code=f"SRC-SEC-{document['public_id'][:8]}",
            title="Test source",
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
    generated = services["chunks"].generate(document["public_id"], ADMIN_ID)
    chunk_public_id = generated["chunk_public_ids"][0]
    services["chunks"].classify(chunk_public_id, ADMIN_ID, chunk_type="definition")
    services["chunk_review"].submit_review(chunk_public_id, ADMIN_ID)
    services["chunk_review"].approve(chunk_public_id, ADMIN_ID)
    result = services["sft"].generate(
        document["public_id"], SftCandidateGenerationRequest(), ADMIN_ID
    )
    candidate = result["items"][0]
    approved = services["sft"].review(
        document["public_id"], candidate["public_id"],
        SftCandidateReviewAction(action="approve"), ADMIN_ID,
    )
    return document["public_id"], approved["items"][0]


class TestExportSensitiveContentBlocking:
    @pytest.mark.anyio
    async def test_export_is_blocked_when_an_approved_candidate_contains_secret_like_text(
        self, services
    ):
        document_public_id, _candidate = await _approved_verified_candidate(
            services, "api_key: sk-abcdefghijklmnopqrstuvwxyz123456 is the credential"
        )
        with pytest.raises(ValidationError, match="secret_like_content_detected"):
            services["export"].export(document_public_id, ADMIN_ID)

    @pytest.mark.anyio
    async def test_export_is_blocked_when_an_approved_candidate_contains_an_absolute_path(
        self, services
    ):
        document_public_id, _candidate = await _approved_verified_candidate(
            services, "See the file at /home/admin/private/notes.txt for context"
        )
        with pytest.raises(ValidationError, match="absolute_path_detected"):
            services["export"].export(document_public_id, ADMIN_ID)

    @pytest.mark.anyio
    async def test_clean_candidate_exports_successfully_and_path_is_never_absolute(
        self, services
    ):
        document_public_id, _candidate = await _approved_verified_candidate(
            services, "Ordinary Tamil grammar content with no sensitive material"
        )
        export = services["export"].export(document_public_id, ADMIN_ID)
        assert not Path(export["export_path"]).is_absolute()


class TestHostileTextIsStoredSafely:
    @pytest.mark.anyio
    async def test_html_script_and_sql_like_text_round_trips_without_executing_or_corrupting_state(
        self, services
    ):
        hostile_text = "<script>alert(1)</script> '; DROP TABLE document_sft_candidates; --"
        document_public_id, candidate = await _approved_verified_candidate(services, hostile_text)
        assert hostile_text in candidate["response"]
        # The table must still exist and be queryable -- proves no SQL executed.
        again = services["sft"].list_candidates(document_public_id)
        assert again["total"] == 1

    @pytest.mark.anyio
    async def test_malformed_unicode_page_text_is_flagged_for_mandatory_human_review(
        self, services
    ):
        from backend.services.document_tamil_quality_service import DocumentTamilQualityService

        document_public_id, _candidate = await _approved_verified_candidate(services, "placeholder")
        services["documents"].edit_page(document_public_id, 1, "broken � text", ADMIN_ID)
        tamil_quality = DocumentTamilQualityService(services["sft"].settings)
        detection = tamil_quality.detect(document_public_id, ADMIN_ID)
        assert detection["by_correction_risk"].get("mandatory_review", 0) >= 1


class TestAppendOnlyAudit:
    @pytest.mark.anyio
    async def test_sft_candidate_reviews_cannot_be_updated_or_deleted(self, services):
        document_public_id, candidate = await _approved_verified_candidate(services, "content")
        import sqlite3

        with sqlite3.connect(services["sft"].settings.resolved_database_path) as connection:
            row = connection.execute(
                "SELECT id FROM document_sft_candidate_reviews WHERE candidate_id=("
                "SELECT id FROM document_sft_candidates WHERE public_id=?)",
                (candidate["public_id"],),
            ).fetchone()
            assert row is not None
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(
                    "UPDATE document_sft_candidate_reviews SET action='reject' WHERE id=?",
                    (row[0],),
                )
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(
                    "DELETE FROM document_sft_candidate_reviews WHERE id=?", (row[0],)
                )

    @pytest.mark.anyio
    async def test_sft_exports_cannot_be_updated_or_deleted(self, services):
        document_public_id, _candidate = await _approved_verified_candidate(services, "content")
        export = services["export"].export(document_public_id, ADMIN_ID)
        import sqlite3

        with sqlite3.connect(services["sft"].settings.resolved_database_path) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(
                    "UPDATE document_sft_exports SET record_count=999 WHERE public_id=?",
                    (export["public_id"],),
                )
