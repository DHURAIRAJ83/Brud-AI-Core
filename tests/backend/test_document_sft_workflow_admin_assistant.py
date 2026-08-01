"""Admin Assistant read-only tools and governed proposals for the Document
SFT workflow (migration 043): real data, real propose -> review -> execute
cycles through the existing generic engine, and the authority boundary
(Admin Assistant never approves or starts training)."""

from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import DataSourceCreate
from backend.models.documents import ProcessRequest
from backend.services.admin_assistant_service import AdminAssistantService
from backend.services.admin_assistant_tools import run_tool
from backend.services.data_source_service import SourceRegistryService
from backend.services.document_service import DocumentService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService
from core_model.admin_assistant.action_registry import BLOCKED_ACTION_SUBSTRINGS

ADMIN_ID = "00000000-0000-0000-0000-000000000009"

_DOCUMENT_SFT_ACTION_TYPES = (
    "propose_document_page_correction",
    "propose_document_ocr_rerun",
    "propose_bulk_cleanup",
    "propose_tamil_corrections",
    "propose_chunk_generation",
    "propose_sft_candidate_generation",
    "propose_candidate_status_change",
    "propose_sft_export",
    "propose_dataset_version_handoff",
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
    database_path = tmp_path / "document_sft_admin_assistant.db"
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
def review(settings: Settings) -> DocumentPageReviewService:
    return DocumentPageReviewService(settings)


@pytest.fixture
def workspace(settings: Settings) -> PDFResearchWorkspaceService:
    return PDFResearchWorkspaceService(settings)


@pytest.fixture
def assistant(settings: Settings) -> AdminAssistantService:
    return AdminAssistantService(settings)


_source_counter = 0


async def _approved_document(
    documents: DocumentService,
    review: DocumentPageReviewService,
    workspace: PDFResearchWorkspaceService,
) -> str:
    global _source_counter
    _source_counter += 1
    upload_file = FakeUploadFile("sample.pdf", make_pdf("Paragraph one content here."))
    document = await documents.upload(upload_file, "embedded_text", "en", ADMIN_ID)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID)
    source_registry = SourceRegistryService(
        DataSourceRepository(documents.settings.resolved_database_path), documents.settings
    )
    source = source_registry.create(
        DataSourceCreate(
            source_code=f"SRC-AA-{_source_counter:04d}",
            title="Test source",
            source_type="document_derived",
        ),
        ADMIN_ID,
    )
    workspace.link_source(document["public_id"], source["public_id"], ADMIN_ID)
    review.approve(document["public_id"], 1, ADMIN_ID)
    return document["public_id"]


def test_no_document_sft_action_type_is_blocked_by_the_authority_boundary() -> None:
    for action_type in _DOCUMENT_SFT_ACTION_TYPES:
        lowered = action_type.lower()
        assert not any(token in lowered for token in BLOCKED_ACTION_SUBSTRINGS)


def test_all_nine_document_sft_actions_are_registered_with_a_real_executor() -> None:
    from backend.services.admin_assistant_service import ACTION_EXECUTORS
    from core_model.admin_assistant.action_registry import ACTION_BY_TYPE

    for action_type in _DOCUMENT_SFT_ACTION_TYPES:
        assert action_type in ACTION_BY_TYPE
        assert action_type in ACTION_EXECUTORS


class TestReadOnlyTools:
    @pytest.mark.anyio
    async def test_analyze_document_readiness_returns_real_data(
        self, settings, documents, review, workspace
    ):
        document_public_id = await _approved_document(documents, review, workspace)
        result = run_tool(
            "analyze_document_readiness", settings, {"document_public_id": document_public_id}
        )
        assert result["available"] is True
        assert result["review_status_counts"]["approved"] == 1

    @pytest.mark.anyio
    async def test_list_critical_document_pages_flags_nothing_for_a_clean_approved_page(
        self, settings, documents, review, workspace
    ):
        document_public_id = await _approved_document(documents, review, workspace)
        result = run_tool(
            "list_critical_document_pages", settings, {"document_public_id": document_public_id}
        )
        assert result["available"] is True
        assert result["critical_page_count"] == 0

    def test_document_tools_report_unavailable_for_an_unknown_document(self, settings):
        for tool_name in (
            "analyze_document_readiness",
            "get_document_issue_summary",
            "list_critical_document_pages",
            "get_document_cleanup_summary",
            "get_document_tamil_quality_summary",
            "get_document_chunk_summary",
            "get_document_sft_candidate_summary",
            "get_document_training_readiness",
        ):
            result = run_tool(tool_name, settings, {"document_public_id": "does-not-exist"})
            assert result["available"] is False


class TestChunkAndSftProposals:
    @pytest.mark.anyio
    async def test_propose_chunk_generation_end_to_end(
        self, settings, documents, review, workspace, assistant
    ):
        document_public_id = await _approved_document(documents, review, workspace)
        proposal = assistant.propose(
            action_type="propose_chunk_generation",
            target_type="document",
            target_public_id=document_public_id,
            request_payload={},
            requested_by=ADMIN_ID,
            summary="Generate chunks for this document",
        )
        assert proposal.risk_level == "low"
        assistant.review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )
        executed = assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
        assert executed.execution_status == "succeeded"
        assert executed.execution_result["generated_chunk_count"] >= 1

    @pytest.mark.anyio
    async def test_propose_sft_candidate_generation_requires_an_approved_chunk_and_reports_failure(
        self, settings, documents, review, workspace, assistant
    ):
        document_public_id = await _approved_document(documents, review, workspace)
        proposal = assistant.propose(
            action_type="propose_sft_candidate_generation",
            target_type="document",
            target_public_id=document_public_id,
            request_payload={},
            requested_by=ADMIN_ID,
            summary="Generate SFT candidates",
        )
        assistant.review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )
        with pytest.raises(Exception, match="approved chunks"):
            assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
        recorded = assistant.get_proposal(proposal.public_id)
        assert recorded.execution_status == "failed"
        assert "approved chunks" in recorded.execution_result["error"]

    @pytest.mark.anyio
    async def test_propose_candidate_status_change_end_to_end(
        self, settings, documents, review, workspace, assistant
    ):
        document_public_id = await _approved_document(documents, review, workspace)
        chunks = SemanticChunkService(settings)
        chunk_review = SemanticChunkReviewService(settings)
        generated = chunks.generate(document_public_id, ADMIN_ID)
        chunk_public_id = generated["chunk_public_ids"][0]
        chunks.classify(chunk_public_id, ADMIN_ID, chunk_type="definition")
        chunk_review.submit_review(chunk_public_id, ADMIN_ID)
        chunk_review.approve(chunk_public_id, ADMIN_ID)

        from backend.models.documents import SftCandidateGenerationRequest
        from backend.services.document_sft_candidate_service import (
            DocumentSftCandidateGenerationService,
        )

        generation = DocumentSftCandidateGenerationService(settings).generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        candidate_public_id = generation["items"][0]["public_id"]

        proposal = assistant.propose(
            action_type="propose_candidate_status_change",
            target_type="document_sft_candidate",
            target_public_id=candidate_public_id,
            request_payload={"document_public_id": document_public_id, "action": "reject"},
            requested_by=ADMIN_ID,
            summary="Reject this SFT candidate",
        )
        assistant.review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )
        executed = assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
        assert executed.execution_status == "succeeded"
        rejected = [
            item
            for item in executed.execution_result["items"]
            if item["public_id"] == candidate_public_id
        ][0]
        assert rejected["quality_status"] == "rejected"


class TestAuthorityBoundary:
    @pytest.mark.anyio
    async def test_admin_assistant_cannot_bypass_review_before_execute(
        self, settings, documents, review, workspace, assistant
    ):
        document_public_id = await _approved_document(documents, review, workspace)
        proposal = assistant.propose(
            action_type="propose_chunk_generation",
            target_type="document",
            target_public_id=document_public_id,
            request_payload={},
            requested_by=ADMIN_ID,
            summary="Generate chunks",
        )
        from backend.services.admin_assistant_service import AdminAssistantError

        with pytest.raises(AdminAssistantError, match="approved"):
            assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
