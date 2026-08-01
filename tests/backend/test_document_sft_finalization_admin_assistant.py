"""Admin Assistant governed proposals for the finalization pass: real
propose -> review -> execute cycles, the target_public_id/rule linkage for
the tamil-rule-entry action, and the authority boundary (Admin Assistant
never builds a final dataset version or activates a Tamil correction rule)."""

from pathlib import Path
from uuid import uuid4

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import DataSourceCreate, SourceRightsUpsert
from backend.models.documents import (
    ProcessRequest,
    SftCandidateGenerationRequest,
    SftCandidateReviewAction,
)
from backend.services.admin_assistant_service import ACTION_EXECUTORS, AdminAssistantService
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.document_security_review_service import DocumentSecurityReviewService
from backend.services.document_service import DocumentService
from backend.services.document_sft_candidate_service import DocumentSftCandidateGenerationService
from backend.services.document_sft_export_service import DocumentSftExportService
from backend.services.document_tamil_correction_registry_service import (
    DocumentTamilCorrectionRegistryService,
)
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService
from core_model.admin_assistant.action_registry import ACTION_BY_TYPE, BLOCKED_ACTION_SUBSTRINGS

ADMIN_ID = "00000000-0000-0000-0000-000000000111"

_FINALIZATION_ACTION_TYPES = (
    "propose_sft_export_validation",
    "propose_sft_dataset_ingestion",
    "propose_sft_dataset_version_build",
    "propose_sft_task_generation",
    "propose_document_cleanup_scan",
    "propose_document_tamil_rule_entry",
    "propose_document_security_review",
    "propose_document_pii_exclusion",
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
    database_path = tmp_path / "finalization_admin_assistant.db"
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
        "security": DocumentSecurityReviewService(settings),
        "tamil_rules": DocumentTamilCorrectionRegistryService(settings),
        "assistant": AdminAssistantService(settings),
        "source_registry": SourceRegistryService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
        "rights": SourceRightsService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
    }


async def _approved_document_with_export(services):
    upload_file = FakeUploadFile("sample.pdf", make_pdf("Paragraph one content here."))
    document = await services["documents"].upload(upload_file, "embedded_text", "en", ADMIN_ID)
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID
    )
    source = services["source_registry"].create(
        DataSourceCreate(
            source_code=f"SRC-AAF-{document['public_id'][:8]}", title="s",
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
    return document["public_id"], export


def test_all_finalization_actions_are_registered_with_a_real_executor():
    for action_type in _FINALIZATION_ACTION_TYPES:
        assert action_type in ACTION_BY_TYPE
        assert action_type in ACTION_EXECUTORS


def test_no_finalization_action_is_blocked_by_the_authority_boundary():
    for action_type in _FINALIZATION_ACTION_TYPES:
        lowered = action_type.lower()
        assert not any(token in lowered for token in BLOCKED_ACTION_SUBSTRINGS)


class TestSecurityReviewProposal:
    @pytest.mark.anyio
    async def test_propose_document_security_review_end_to_end(self, services):
        document_public_id, _export = await _approved_document_with_export(services)
        proposal = services["assistant"].propose(
            action_type="propose_document_security_review",
            target_type="document",
            target_public_id=document_public_id,
            request_payload={},
            requested_by=ADMIN_ID,
            summary="Scan for security findings",
        )
        services["assistant"].review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )
        executed = services["assistant"].execute(proposal.public_id, executor_public_id=ADMIN_ID)
        assert executed.execution_status == "succeeded"


class TestTamilRuleEntryProposal:
    @pytest.mark.anyio
    async def test_propose_document_tamil_rule_entry_creates_a_draft_under_the_target_id(
        self, services
    ):
        rule_public_id = str(uuid4())
        proposal = services["assistant"].propose(
            action_type="propose_document_tamil_rule_entry",
            target_type="tamil_correction_rule",
            target_public_id=rule_public_id,
            request_payload={
                "incorrect_form": "a", "approved_correction": "b",
                "issue_category": "pulli_error", "evidence": "e",
                "confidence_band": "high", "meaning_change_risk": "mechanical",
            },
            requested_by=ADMIN_ID,
            summary="Propose a Tamil correction rule",
        )
        services["assistant"].review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )
        executed = services["assistant"].execute(proposal.public_id, executor_public_id=ADMIN_ID)
        assert executed.execution_status == "succeeded"
        rule = services["tamil_rules"].get_rule(rule_public_id)
        assert rule["status"] == "draft"

    def test_admin_assistant_has_no_action_that_activates_a_rule(self):
        # The registry's own action_type strings are the complete allowlist
        # of everything the Admin Assistant can ever propose -- confirm
        # none of them is an activation/approval action for this registry.
        for action_type in ACTION_BY_TYPE:
            assert "activate_tamil" not in action_type
            assert "approve_tamil_rule" not in action_type


class TestSftDatasetIngestionProposal:
    @pytest.mark.anyio
    async def test_propose_sft_dataset_ingestion_end_to_end(self, services):
        document_public_id, export = await _approved_document_with_export(services)
        proposal = services["assistant"].propose(
            action_type="propose_sft_dataset_ingestion",
            target_type="document",
            target_public_id=document_public_id,
            request_payload={"export_public_id": export["public_id"]},
            requested_by=ADMIN_ID,
            summary="Ingest export into dataset records",
        )
        services["assistant"].review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )
        executed = services["assistant"].execute(proposal.public_id, executor_public_id=ADMIN_ID)
        assert executed.execution_status == "succeeded"
        assert executed.execution_result["imported_count"] == 1

    @pytest.mark.anyio
    async def test_dataset_version_build_proposal_never_builds_the_version(self, services):
        document_public_id, export = await _approved_document_with_export(services)
        from backend.services.document_sft_dataset_handoff_service import (
            DocumentSftDatasetHandoffService,
        )

        handoff = DocumentSftDatasetHandoffService(services["sft"].settings).ingest(
            export["public_id"], ADMIN_ID
        )
        proposal = services["assistant"].propose(
            action_type="propose_sft_dataset_version_build",
            target_type="document",
            target_public_id=document_public_id,
            request_payload={
                "handoff_public_id": handoff["public_id"],
                "dataset_name": "finalization-test", "dataset_version": "v1",
            },
            requested_by=ADMIN_ID,
            summary="Propose a dataset version build",
        )
        services["assistant"].review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )
        executed = services["assistant"].execute(proposal.public_id, executor_public_id=ADMIN_ID)
        assert executed.execution_status == "succeeded"
        # The proposal creates a draft build record only -- it must never
        # reach a completed/built dataset-version status by itself.
        assert executed.execution_result["status"] == "version_proposed"
