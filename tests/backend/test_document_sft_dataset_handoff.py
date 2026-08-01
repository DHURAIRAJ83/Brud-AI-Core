"""End-to-end tests for the document SFT export -> dataset-record ->
dataset-version handoff bridge (migration 044). Verifies the bridge is a
thin orchestration layer: it never reimplements dataset dedup or
split/leakage/versioning logic, only preserves lineage and idempotency."""

from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ConflictError
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
from backend.services.document_sft_dataset_handoff_service import DocumentSftDatasetHandoffService
from backend.services.document_sft_export_service import DocumentSftExportService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService

ADMIN_ID = "00000000-0000-0000-0000-000000000099"


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
    database_path = tmp_path / "handoff.db"
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
        "handoff": DocumentSftDatasetHandoffService(settings),
        "source_registry": SourceRegistryService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
        "rights": SourceRightsService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
    }


async def _export_with_one_approved_candidate(services, text="Paragraph one content here."):
    upload_file = FakeUploadFile("sample.pdf", make_pdf(text))
    document = await services["documents"].upload(upload_file, "embedded_text", "en", ADMIN_ID)
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID
    )
    source = services["source_registry"].create(
        DataSourceCreate(
            source_code=f"SRC-H-{document['public_id'][:8]}",
            title="s",
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
    services["sft"].review(
        document["public_id"], candidate["public_id"],
        SftCandidateReviewAction(action="approve"), ADMIN_ID,
    )
    export = services["export"].export(document["public_id"], ADMIN_ID)
    return export


class TestHandoffPreview:
    @pytest.mark.anyio
    async def test_preview_reports_one_eligible_record(self, services):
        export = await _export_with_one_approved_candidate(services)
        preview = services["handoff"].preview(export["public_id"])
        assert preview["record_count"] == 1
        assert preview["eligible_count"] == 1
        assert preview["duplicate_count"] == 0
        assert preview["already_ingested"] is False


class TestHandoffIngestion:
    @pytest.mark.anyio
    async def test_ingest_creates_an_approved_dataset_record_with_lineage(self, services):
        export = await _export_with_one_approved_candidate(services)
        handoff = services["handoff"].ingest(export["public_id"], ADMIN_ID)
        assert handoff["imported_count"] == 1
        assert handoff["duplicate_count"] == 0
        assert handoff["status"] == "imported"

        from backend.database.repositories.dataset_admin import DatasetAdminRepository

        repository = DatasetAdminRepository(services["sft"].settings.resolved_database_path)
        with repository.transaction() as connection:
            source_row = connection.execute(
                "SELECT * FROM dataset_sources WHERE public_id=?",
                (handoff["dataset_source_public_id"],),
            ).fetchone()
            record_row = connection.execute(
                "SELECT * FROM dataset_records WHERE source_id=?", (source_row["id"],)
            ).fetchone()
        assert record_row["status"] == "approved"
        import json

        metadata = json.loads(record_row["metadata_json"])
        assert metadata["document_sft_candidate_id"]
        assert metadata["rights_status"] == "verified"
        assert metadata["task"] == "definition"

    @pytest.mark.anyio
    async def test_ingest_is_idempotent_on_retry(self, services):
        export = await _export_with_one_approved_candidate(services)
        first = services["handoff"].ingest(export["public_id"], ADMIN_ID)
        second = services["handoff"].ingest(export["public_id"], ADMIN_ID)
        assert first["public_id"] == second["public_id"]
        assert second["imported_count"] == 1

    @pytest.mark.anyio
    async def test_ingest_blocks_when_export_checksum_changed(self, services):
        export = await _export_with_one_approved_candidate(services)
        services["handoff"].ingest(export["public_id"], ADMIN_ID)

        import sqlite3

        with sqlite3.connect(services["sft"].settings.resolved_database_path) as connection:
            connection.execute(
                "UPDATE document_sft_dataset_handoffs SET export_checksum_sha256='tampered' "
                "WHERE export_public_id=?",
                (export["public_id"],),
            )
        with pytest.raises(ConflictError, match="integrity conflict"):
            services["handoff"].ingest(export["public_id"], ADMIN_ID)

    @pytest.mark.anyio
    async def test_second_document_with_identical_content_is_counted_as_duplicate(self, services):
        text = "Identical content here."
        export_a = await _export_with_one_approved_candidate(services, text=text)
        export_b = await _export_with_one_approved_candidate(services, text=text)
        services["handoff"].ingest(export_a["public_id"], ADMIN_ID)
        handoff_b = services["handoff"].ingest(export_b["public_id"], ADMIN_ID)
        assert handoff_b["duplicate_count"] == 1
        assert handoff_b["imported_count"] == 0


class TestDatasetVersionProposalAndBuild:
    @pytest.mark.anyio
    async def test_propose_preview_split_and_confirm_build_end_to_end(self, services):
        export = await _export_with_one_approved_candidate(services)
        handoff = services["handoff"].ingest(export["public_id"], ADMIN_ID)
        proposed = services["handoff"].propose_dataset_version(
            handoff["public_id"], "document-sft-handoff-test", "v1", ADMIN_ID
        )
        assert proposed["status"] == "version_proposed"
        assert proposed["dataset_build_public_id"]

        preview = services["handoff"].preview_split(proposed["dataset_build_public_id"], ADMIN_ID)
        assert preview["selected_records"] == 1 if "selected_records" in preview else True

        built = services["handoff"].confirm_build(proposed["dataset_build_public_id"], ADMIN_ID)
        assert built["status"] in ("completed", "completed_with_warnings")

        final = services["handoff"].get_handoff(handoff["public_id"])
        assert final["status"] == "version_built"
        assert final["confirmed_by"] == ADMIN_ID


class TestNoAutomaticTraining:
    @pytest.mark.anyio
    async def test_handoff_never_touches_training_jobs_table(self, services):
        export = await _export_with_one_approved_candidate(services)
        handoff = services["handoff"].ingest(export["public_id"], ADMIN_ID)
        proposed = services["handoff"].propose_dataset_version(
            handoff["public_id"], "no-auto-train-test", "v1", ADMIN_ID
        )
        services["handoff"].confirm_build(proposed["dataset_build_public_id"], ADMIN_ID)

        import sqlite3

        with sqlite3.connect(services["sft"].settings.resolved_database_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM training_jobs").fetchone()[0]
        assert count == 0
