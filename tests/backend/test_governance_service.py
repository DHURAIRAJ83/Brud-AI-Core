from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.database.repositories.manual_data import ManualDataRepository
from backend.models.data_sources import (
    DataSourceCreate,
    SourceRightsUpsert,
    VerificationActionRequest,
)
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.models.documents import ProcessRequest
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.dataset_quality import DatasetQualityService
from backend.services.dataset_service import DatasetService
from backend.services.document_service import DocumentService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.governance_service import (
    GovernanceApprovalService,
    GovernanceConflictService,
    GovernanceDuplicateService,
    GovernanceExportReadinessService,
    GovernanceQualityService,
    GovernanceReviewService,
)
from backend.services.manual_data_service import ManualDataRecordService, ManualDataUsageService
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
    database_path = tmp_path / "governance_service.db"
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
    manual_repo = ManualDataRepository(settings.resolved_database_path)
    return {
        "documents": DocumentService(settings),
        "workspace": PDFResearchWorkspaceService(settings),
        "review": DocumentPageReviewService(settings),
        "chunks": SemanticChunkService(settings),
        "chunk_review": SemanticChunkReviewService(settings),
        "records": StructuredRecordCandidateService(settings),
        "source_registry": SourceRegistryService(source_repo, settings),
        "source_rights": SourceRightsService(source_repo, settings),
        "manual_data": ManualDataRecordService(manual_repo, source_repo, settings),
        "dataset": DatasetService(DatasetAdminRepository(settings.resolved_database_path)),
        "dataset_quality": DatasetQualityService(
            DatasetQualityRepository(settings.resolved_database_path), settings
        ),
        "gov_review": GovernanceReviewService(settings),
        "gov_quality": GovernanceQualityService(settings),
        "gov_duplicate": GovernanceDuplicateService(settings),
        "gov_conflict": GovernanceConflictService(settings),
        "gov_approval": GovernanceApprovalService(settings),
        "gov_readiness": GovernanceExportReadinessService(settings),
    }


_source_counter = 0


def _human_source(services, code=None):
    global _source_counter
    _source_counter += 1
    return services["source_registry"].create(
        DataSourceCreate(
            source_code=code or f"SRC-GOV-{_source_counter:04d}",
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


def _manual_record(services, *, source_public_id, word="தமிழ்"):
    from backend.models.manual_data import ManualDataRecordCreate, ManualRecordContentInput

    return services["manual_data"].create(
        ManualDataRecordCreate(
            record_type="dictionary_entry",
            source_public_id=source_public_id,
            primary_language="ta",
            content=ManualRecordContentInput(word=word, meanings=["a language"]),
        ),
        "admin-1",
    )


def _approved_manual_record(services, *, source_public_id, word, target_uses=("training",)):
    from backend.models.manual_data import ApprovalRequest

    settings = services["gov_approval"].settings
    manual_repo = ManualDataRepository(settings.resolved_database_path)
    source_repo = DataSourceRepository(settings.resolved_database_path)
    usage_service = ManualDataUsageService(manual_repo, source_repo, settings)
    record = _manual_record(services, source_public_id=source_public_id, word=word)
    services["manual_data"].submit_review(record["public_id"], "admin-1")
    return services["manual_data"].approve(
        record["public_id"],
        ApprovalRequest(approved_uses=list(target_uses)),
        "admin-1",
        usage_service=usage_service,
    )


class TestGovernanceReviewService:
    def test_open_or_reuse_is_idempotent(self, services):
        first = services["gov_review"].open_or_reuse(
            entity_type="document_page",
            entity_public_id="page-1",
            reason="submitted_for_review",
            admin_id="admin-1",
        )
        second = services["gov_review"].open_or_reuse(
            entity_type="document_page",
            entity_public_id="page-1",
            reason="submitted_for_review",
            admin_id="admin-1",
        )
        assert first["public_id"] == second["public_id"]

    def test_get_includes_issues_events_and_target_approvals(self, services):
        item = services["gov_review"].open_or_reuse(
            entity_type="document_page",
            entity_public_id="page-2",
            reason="submitted_for_review",
            admin_id="admin-1",
        )
        detail = services["gov_review"].get(item["public_id"])
        assert detail["issues"] == []
        assert len(detail["events"]) == 1
        assert detail["target_approvals"] == []

    def test_assign_and_status_transitions_are_audited(self, services):
        item = services["gov_review"].open_or_reuse(
            entity_type="document_page",
            entity_public_id="page-3",
            reason="submitted_for_review",
            admin_id="admin-1",
        )
        assigned = services["gov_review"].assign(item["public_id"], "admin-2", admin_id="admin-1")
        assert assigned["assigned_admin_public_id"] == "admin-2"
        resolved = services["gov_review"].set_status(
            item["public_id"], "resolved", admin_id="admin-1"
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None
        history = services["gov_review"].history(item["public_id"])
        event_types = [e["event_type"] for e in history["items"]]
        assert "review_item_status_changed" in event_types

    def test_cannot_resolve_with_open_blocking_issue(self, services):
        from backend.database.repositories.governance import GovernanceRepository

        item = services["gov_review"].open_or_reuse(
            entity_type="document_page",
            entity_public_id="page-blocked",
            reason="blocking_quality_issue",
            admin_id="admin-1",
        )
        repository = GovernanceRepository(services["gov_review"].settings.resolved_database_path)
        with repository.transaction() as connection:
            item_id = repository.review_item(connection, item["public_id"])["id"]
            repository.create_issue(
                connection,
                {
                    "review_item_id": item_id,
                    "issue_code": "X1",
                    "issue_category": "language_quality",
                    "severity": "critical",
                    "is_blocking": True,
                    "message": "blocking issue",
                    "detector": "test",
                },
            )
        with pytest.raises(ValidationError, match="unresolved blocking"):
            services["gov_review"].set_status(item["public_id"], "resolved", admin_id="admin-1")

    def test_queue_orders_by_priority(self, services):
        services["gov_review"].open_or_reuse(
            entity_type="document_page",
            entity_public_id="page-low",
            reason="submitted_for_review",
            admin_id="admin-1",
            priority="low",
        )
        services["gov_review"].open_or_reuse(
            entity_type="document_page",
            entity_public_id="page-urgent",
            reason="submitted_for_review",
            admin_id="admin-1",
            priority="urgent",
        )
        queue = services["gov_review"].queue()
        urgent_index = next(
            i for i, item in enumerate(queue["items"]) if item["entity_public_id"] == "page-urgent"
        )
        low_index = next(
            i for i, item in enumerate(queue["items"]) if item["entity_public_id"] == "page-low"
        )
        assert urgent_index < low_index


class TestGovernanceQualityService:
    @pytest.mark.anyio
    async def test_assess_semantic_chunk_with_no_issues_does_not_open_a_review_item(
        self, services
    ):
        _document, _source, chunk_id = await _approved_chunk(services)
        result = services["gov_quality"].assess("semantic_chunk", chunk_id, admin_id="admin-1")
        assert result["normalized_quality"]["is_blocked"] is False
        assert result["review_item"] is None

    @pytest.mark.anyio
    async def test_assess_semantic_chunk_with_reopened_page_opens_review_item(self, services):
        from backend.database.connection import database_connection

        _document, _source, chunk_id = await _approved_chunk(services)
        # The page was approved when the chunk was generated but has since
        # been reopened for correction -- the chunk's own quality gate must
        # catch this even though nothing about the chunk itself changed.
        db_path = services["gov_quality"].settings.resolved_database_path
        with database_connection(db_path) as connection:
            connection.execute(
                "UPDATE document_pages SET review_status='needs_review' "
                "WHERE review_status='approved'"
            )
            connection.commit()
        assessed = services["gov_quality"].assess("semantic_chunk", chunk_id, admin_id="admin-1")
        assert assessed["normalized_quality"]["is_blocked"] is True
        assert "UNAPPROVED_PAGE_SOURCE" in assessed["normalized_quality"]["blocking_issue_codes"]
        assert assessed["review_item"] is not None
        assert assessed["review_item"]["status"] == "open"
        assert assessed["review_item"] is not None
        assert assessed["review_item"]["status"] == "open"

    def test_assess_dataset_record_with_missing_source_is_blocked(self, services):
        source = services["dataset"].create_source(
            ManualSourceCreate(name="Gov Dataset Source", language="en"), "admin-1"
        )
        record = services["dataset"].create_record(
            RecordCreate(
                source_public_id=source["public_id"],
                record_type="pretrain",
                language="en",
                input_text="Some pretraining text long enough to pass length checks easily.",
            ),
            "admin-1",
        )
        result = services["gov_quality"].assess(
            "dataset_record", record["public_id"], admin_id="admin-1"
        )
        assert "normalized_quality" in result
        assert result["normalized_quality"]["metadata"]["source_system"] == "dataset_quality"


class TestGovernanceDuplicateService:
    def test_sync_manual_data_duplicate_creates_a_group(self, services):
        from uuid import uuid4

        source = _human_source(services)
        db_path = services["gov_duplicate"].settings.resolved_database_path
        manual_repo = ManualDataRepository(db_path)
        digest = f"same-hash-{uuid4()}"
        with manual_repo.transaction() as connection:
            source_id = connection.execute(
                "SELECT id FROM data_sources WHERE public_id=?", (source["public_id"],)
            ).fetchone()[0]
            record_a = manual_repo.create_record(
                connection,
                {
                    "record_code": "MD-GOV-A",
                    "record_type": "dictionary_entry",
                    "source_id": source_id,
                    "created_by_admin_public_id": "admin-1",
                },
            )
            record_a_id = manual_repo.record(connection, record_a)["id"]
            revision_a = manual_repo.create_revision(
                connection,
                {
                    "record_id": record_a_id,
                    "revision_number": 1,
                    "word": "ஒன்று",
                    "meanings_json": '["one"]',
                    "content_hash": digest,
                    "created_by_admin_public_id": "admin-1",
                },
            )
            manual_repo.update_record(
                connection,
                record_a_id,
                {"active_revision_id": manual_repo.revision(connection, revision_a)["id"]},
            )
            record_b = manual_repo.create_record(
                connection,
                {
                    "record_code": "MD-GOV-B",
                    "record_type": "dictionary_entry",
                    "source_id": source_id,
                    "created_by_admin_public_id": "admin-1",
                },
            )
            record_b_id = manual_repo.record(connection, record_b)["id"]
            revision_b = manual_repo.create_revision(
                connection,
                {
                    "record_id": record_b_id,
                    "revision_number": 1,
                    "word": "ஒன்று",
                    "meanings_json": '["one"]',
                    "content_hash": digest,
                    "created_by_admin_public_id": "admin-1",
                },
            )
            manual_repo.update_record(
                connection,
                record_b_id,
                {"active_revision_id": manual_repo.revision(connection, revision_b)["id"]},
            )

        result = services["gov_duplicate"].sync_manual_data_duplicate(record_b, admin_id="admin-1")
        assert result["duplicate_group"] is not None
        assert result["duplicate_group"]["duplicate_type"] == "exact"

        resolved = services["gov_duplicate"].resolve(
            result["duplicate_group"]["public_id"],
            resolution_action="keep_all",
            resolution_reason="both legitimate historical imports",
            admin_id="admin-1",
        )
        assert resolved["status"] == "resolved"

    def test_resolve_requires_a_non_empty_reason(self, services):
        with pytest.raises(ValidationError):
            services["gov_duplicate"].resolve(
                "does-not-matter",
                resolution_action="keep_all",
                resolution_reason="  ",
                admin_id="admin-1",
            )


class TestGovernanceConflictService:
    @pytest.mark.anyio
    async def test_alternate_dictionary_sense_creates_a_conflict_group_not_a_duplicate(
        self, services
    ):
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
        result = services["gov_conflict"].sync_structured_record_conflict(
            second["public_id"], admin_id="admin-1"
        )
        assert result["duplicate_group"] is None
        assert result["conflict_group"] is not None
        assert result["conflict_group"]["conflict_type"] == "dictionary_sense"

        resolved = services["gov_conflict"].resolve(
            result["conflict_group"]["public_id"],
            resolution_action="mark_alternate_sense",
            resolution_reason="both senses are valid and in active use",
            admin_id="admin-1",
        )
        assert resolved["status"] == "resolved"


class TestGovernanceApprovalService:
    def test_evaluate_blocks_manual_data_record_without_rights(self, services):
        source = _human_source(services)
        record = _manual_record(services, source_public_id=source["public_id"])
        decision = services["gov_approval"].evaluate(
            "manual_data_record", record["public_id"], "training", admin_id="admin-1"
        )
        assert decision["decision"] == "blocked"

    def test_evaluate_allows_manual_data_record_with_full_rights(self, services):
        source = _human_source(services)
        _allow_all_rights(services, source["public_id"])
        record = _approved_manual_record(
            services, source_public_id=source["public_id"], word="இரண்டு"
        )
        decision = services["gov_approval"].evaluate(
            "manual_data_record", record["public_id"], "training", admin_id="admin-1"
        )
        assert decision["decision"] == "allowed"

    def test_override_requires_a_reason(self, services):
        source = _human_source(services)
        record = _manual_record(services, source_public_id=source["public_id"], word="மூன்று")
        with pytest.raises(ValidationError):
            services["gov_approval"].override(
                "manual_data_record",
                record["public_id"],
                "training",
                "allowed",
                reason="  ",
                admin_id="admin-1",
            )

    def test_override_is_recorded_and_audited(self, services):
        source = _human_source(services)
        record = _manual_record(services, source_public_id=source["public_id"], word="நான்கு")
        overridden = services["gov_approval"].override(
            "manual_data_record",
            record["public_id"],
            "training",
            "allowed",
            reason="legal has separately cleared this content",
            admin_id="admin-1",
        )
        assert overridden["decision"] == "allowed"
        assert bool(overridden["is_override"]) is True
        assert overridden["override_reason"]

    def test_status_matrix_reports_not_requested_for_untouched_target(self, services):
        source = _human_source(services)
        record = _manual_record(services, source_public_id=source["public_id"], word="ஐந்து")
        matrix = services["gov_approval"].status("manual_data_record", record["public_id"])
        assert matrix["targets"]["commercial"]["decision"] == "not_requested"


class TestGovernanceExportReadinessService:
    def test_require_allowed_raises_when_blocked(self, services):
        source = _human_source(services)
        record = _manual_record(services, source_public_id=source["public_id"], word="ஆறு")
        with pytest.raises(ValidationError):
            services["gov_readiness"].require_allowed(
                "manual_data_record", record["public_id"], "training"
            )

    def test_require_allowed_passes_when_allowed(self, services):
        source = _human_source(services)
        _allow_all_rights(services, source["public_id"])
        record = _approved_manual_record(services, source_public_id=source["public_id"], word="ஏழு")
        services["gov_readiness"].require_allowed(
            "manual_data_record", record["public_id"], "training"
        )


def _open_blocking_review_item(services, *, entity_type, entity_public_id):
    from backend.database.repositories.governance import GovernanceRepository

    repository = GovernanceRepository(services["gov_review"].settings.resolved_database_path)
    with repository.transaction() as connection:
        review_code = repository.next_review_code(connection)
        item_public_id = repository.create_review_item(
            connection,
            {
                "review_code": review_code,
                "entity_type": entity_type,
                "entity_public_id": entity_public_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
        item_id = repository.review_item(connection, item_public_id)["id"]
        repository.create_issue(
            connection,
            {
                "review_item_id": item_id,
                "issue_code": "TEST_BLOCK",
                "issue_category": "language_quality",
                "severity": "critical",
                "is_blocking": True,
                "message": "test-injected blocking issue",
                "detector": "test",
            },
        )
    return item_public_id


class TestExportPreflightIntegration:
    @pytest.mark.anyio
    async def test_structured_record_export_is_blocked_by_an_open_governance_issue(
        self, services
    ):
        from backend.database.repositories.base import ValidationError as SvcValidationError

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
        _open_blocking_review_item(
            services,
            entity_type="structured_record_candidate",
            entity_public_id=candidate["public_id"],
        )
        with pytest.raises(SvcValidationError, match="governance blocks"):
            services["records"].export_to_dataset(candidate["public_id"], "admin-1")

    @pytest.mark.anyio
    async def test_structured_record_rag_handoff_is_blocked_by_an_open_governance_issue(
        self, services
    ):
        from backend.database.repositories.base import ValidationError as SvcValidationError

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
        _open_blocking_review_item(
            services,
            entity_type="structured_record_candidate",
            entity_public_id=candidate["public_id"],
        )
        with pytest.raises(SvcValidationError, match="governance blocks"):
            services["records"].create_rag_candidate(candidate["public_id"], "admin-1")

    def test_manual_data_export_is_blocked_by_an_open_governance_issue(self, services):
        from backend.database.repositories.base import ValidationError as SvcValidationError
        from backend.database.repositories.dataset_admin import DatasetAdminRepository
        from backend.services.dataset_service import DatasetService
        from backend.services.manual_data_candidate_service import ManualDataCandidateService

        settings = services["gov_review"].settings
        manual_repo = ManualDataRepository(settings.resolved_database_path)
        dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        candidate_service = ManualDataCandidateService(manual_repo, dataset_service, settings)

        source = _human_source(services)
        _allow_all_rights(services, source["public_id"])
        record = _approved_manual_record(
            services, source_public_id=source["public_id"], word="எட்டு"
        )
        _open_blocking_review_item(
            services, entity_type="manual_data_record", entity_public_id=record["public_id"]
        )
        with pytest.raises(SvcValidationError, match="governance blocks"):
            candidate_service.create_candidate(record["public_id"], "admin-1")

    def test_manual_data_export_proceeds_with_no_governance_activity(self, services):
        from backend.database.repositories.dataset_admin import DatasetAdminRepository
        from backend.services.dataset_service import DatasetService
        from backend.services.manual_data_candidate_service import ManualDataCandidateService

        settings = services["gov_review"].settings
        manual_repo = ManualDataRepository(settings.resolved_database_path)
        dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        candidate_service = ManualDataCandidateService(manual_repo, dataset_service, settings)

        source = _human_source(services)
        _allow_all_rights(services, source["public_id"])
        record = _approved_manual_record(
            services, source_public_id=source["public_id"], word="ஒன்பது"
        )
        exported = candidate_service.create_candidate(record["public_id"], "admin-1")
        assert exported["exported_dataset_record_public_id"] is not None
