"""Production Closure: Admin Assistant navigation metadata for the Document
SFT views. Every navigation_target must come from
`resolve_document_navigation()` (the same registry `documentNavigation.js`
mirrors), every real-data sentence folded into a reply must come from a real
read-only tool call, and no navigation reply may ever mutate anything."""

from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import DataSourceCreate, SourceRightsUpsert
from backend.models.documents import ProcessRequest, SftCandidateGenerationRequest
from backend.services.admin_assistant_chat_service import AdminAssistantChatService
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.document_security_review_service import DocumentSecurityReviewService
from backend.services.document_service import DocumentService
from backend.services.document_sft_candidate_service import DocumentSftCandidateGenerationService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService
from core_model.admin_assistant.dashboard_registry import resolve_document_navigation

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
    settings = Settings(
        database_path=tmp_path / "nav_chat.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            "INSERT INTO admin_accounts(public_id, username, display_name, password_hash) "
            "VALUES (?,?,?,?)",
            (ADMIN_ID, "nav-test-admin", "Nav Test Admin", "hash"),
        )
        connection.commit()
    return settings


@pytest.fixture
def chat(settings: Settings) -> AdminAssistantChatService:
    return AdminAssistantChatService(settings)


async def _approved_document(settings: Settings) -> str:
    documents = DocumentService(settings)
    workspace = PDFResearchWorkspaceService(settings)
    review = DocumentPageReviewService(settings)
    chunks = SemanticChunkService(settings)
    chunk_review = SemanticChunkReviewService(settings)
    sft = DocumentSftCandidateGenerationService(settings)
    security = DocumentSecurityReviewService(settings)
    source_registry = SourceRegistryService(
        DataSourceRepository(settings.resolved_database_path), settings
    )
    rights = SourceRightsService(DataSourceRepository(settings.resolved_database_path), settings)

    upload_file = FakeUploadFile("sample.pdf", make_pdf("Paragraph one content here."))
    document = await documents.upload(upload_file, "embedded_text", "en", ADMIN_ID)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID)
    source = source_registry.create(
        DataSourceCreate(
            source_code=f"SRC-NAV-{document['public_id'][:8]}", title="s",
            source_type="document_derived",
        ),
        ADMIN_ID,
    )
    rights.upsert(
        source["public_id"],
        SourceRightsUpsert(rights_status="public_domain", training_use_allowed=True),
        ADMIN_ID,
    )
    workspace.link_source(document["public_id"], source["public_id"], ADMIN_ID)
    review.approve(document["public_id"], 1, ADMIN_ID)
    generated = chunks.generate(document["public_id"], ADMIN_ID)
    chunk_public_id = generated["chunk_public_ids"][0]
    chunks.classify(chunk_public_id, ADMIN_ID, chunk_type="definition")
    chunk_review.submit_review(chunk_public_id, ADMIN_ID)
    chunk_review.approve(chunk_public_id, ADMIN_ID)
    sft.generate(document["public_id"], SftCandidateGenerationRequest(), ADMIN_ID)
    security.scan_document(document["public_id"], ADMIN_ID)
    return document["public_id"]


class TestRegistryResolution:
    def test_every_document_nav_keyword_key_resolves_in_the_registry(self):
        from backend.services.admin_assistant_chat_service import AdminAssistantChatService as Svc

        for tab_key in Svc._DOCUMENT_NAV_KEYWORDS:
            assert resolve_document_navigation(tab_key, "doc-x") is not None

    def test_unknown_tab_key_resolves_to_none(self):
        assert resolve_document_navigation("history", "doc-x") is None


class TestDocumentNavigationReplies:
    @pytest.mark.anyio
    async def test_security_review_navigation_includes_real_finding_counts(
        self, chat: AdminAssistantChatService, settings: Settings
    ):
        document_public_id = await _approved_document(settings)
        result = chat.send_message(
            admin_id=ADMIN_ID,
            message="எந்த security findings exportஐ block செய்கின்றன?",
            page_id="documents",
            entity_type="document",
            entity_public_id=document_public_id,
        )
        assert result["navigation_target"]["tab_key"] == "security-review"
        assert result["navigation_target"]["document_public_id"] == document_public_id
        assert result["navigation_target"]["nav_key"] == "Documents"
        assert "finding(s)" in result["answer"]

    @pytest.mark.anyio
    async def test_navigation_without_a_document_in_context_is_honest_not_fabricated(
        self, chat: AdminAssistantChatService
    ):
        result = chat.send_message(
            admin_id=ADMIN_ID, message="open security review", page_id="documents"
        )
        assert result["navigation_target"]["tab_key"] == "security-review"
        assert result["navigation_target"]["document_public_id"] is None
        assert "Open a document first" in result["answer"]

    @pytest.mark.anyio
    async def test_sft_candidates_review_navigation(
        self, chat: AdminAssistantChatService, settings: Settings
    ):
        document_public_id = await _approved_document(settings)
        result = chat.send_message(
            admin_id=ADMIN_ID, message="SFT candidates review page திறக்கவும்.",
            page_id="documents", entity_type="document", entity_public_id=document_public_id,
        )
        assert result["navigation_target"]["tab_key"] == "sft-candidates"
        assert "approved chunk" in result["answer"]

    @pytest.mark.anyio
    async def test_dataset_handoff_navigation(
        self, chat: AdminAssistantChatService, settings: Settings
    ):
        document_public_id = await _approved_document(settings)
        result = chat.send_message(
            admin_id=ADMIN_ID, message="Dataset handoff நிலையை காட்டவும்.",
            page_id="documents", entity_type="document", entity_public_id=document_public_id,
        )
        assert result["navigation_target"]["tab_key"] == "dataset-handoff"
        assert result["navigation_target"]["nav_key"] == "Document Wizard"
        assert result["navigation_target"]["wizard_step"] == 11

    @pytest.mark.anyio
    async def test_dataset_version_result_routes_to_wizard_build_step_when_not_built(
        self, chat: AdminAssistantChatService, settings: Settings
    ):
        document_public_id = await _approved_document(settings)
        result = chat.send_message(
            admin_id=ADMIN_ID, message="உருவாக்கப்பட்ட dataset versionஐ திறக்கவும்.",
            page_id="documents", entity_type="document", entity_public_id=document_public_id,
        )
        assert result["navigation_target"]["nav_key"] == "Document Wizard"
        assert result["navigation_target"]["tab_key"] == "dataset-version"
        assert "dataset version" in result["answer"].lower()
        assert "build" in result["answer"].lower()

    @pytest.mark.anyio
    async def test_entity_type_must_be_document_for_entity_public_id_to_be_used(
        self, chat: AdminAssistantChatService, settings: Settings
    ):
        document_public_id = await _approved_document(settings)
        result = chat.send_message(
            admin_id=ADMIN_ID, message="open security review", page_id="documents",
            entity_type="dataset_record", entity_public_id=document_public_id,
        )
        assert result["navigation_target"]["document_public_id"] is None


class TestAuthorityBoundary:
    @pytest.mark.anyio
    async def test_navigation_never_mutates_anything(
        self, chat: AdminAssistantChatService, settings: Settings
    ):
        document_public_id = await _approved_document(settings)
        for message in (
            "open security review", "Dataset handoff நிலையை காட்டவும்.",
            "உருவாக்கப்பட்ட dataset versionஐ திறக்கவும்.", "training readiness",
        ):
            chat.send_message(
                admin_id=ADMIN_ID, message=message, page_id="documents",
                entity_type="document", entity_public_id=document_public_id,
            )
        with database_connection(settings.resolved_database_path) as connection:
            training_jobs = connection.execute("SELECT COUNT(*) FROM training_jobs").fetchone()[0]
            proposals = connection.execute(
                "SELECT COUNT(*) FROM admin_approvals"
            ).fetchone()[0]
            handoffs = connection.execute(
                "SELECT COUNT(*) FROM document_sft_dataset_handoffs"
            ).fetchone()[0]
        assert training_jobs == 0
        assert proposals == 0
        assert handoffs == 0
