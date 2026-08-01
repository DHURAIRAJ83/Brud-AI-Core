from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.rag import RagRepository
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.models.domain import ReviewDecision
from backend.models.rag import KnowledgeSpaceCreate
from backend.services.dataset_service import DatasetService
from backend.services.governance_service import GovernanceApprovalService
from backend.services.governed_build_service import GovernedBuildService
from backend.services.governed_rag_handoff_service import GovernedRagHandoffService
from backend.services.rag_ingestion_service import RagIngestionService

ADMIN = "admin-1"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "rag_handoff.db"
    initialize_database(database_path)
    return Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )


@pytest.fixture
def dataset_service(settings: Settings) -> DatasetService:
    return DatasetService(DatasetAdminRepository(settings.resolved_database_path))


@pytest.fixture
def governed(settings: Settings) -> GovernedBuildService:
    return GovernedBuildService(settings)


@pytest.fixture
def approvals(settings: Settings) -> GovernanceApprovalService:
    return GovernanceApprovalService(settings)


@pytest.fixture
def rag_handoff(settings: Settings) -> GovernedRagHandoffService:
    return GovernedRagHandoffService(settings)


@pytest.fixture
def knowledge_space(settings: Settings) -> dict:
    ingestion = RagIngestionService(RagRepository(settings.resolved_database_path), settings)
    return ingestion.create_space(
        KnowledgeSpaceCreate(name="Governed RAG Test Space", slug="governed-rag-test"), ADMIN
    )


def _completed_rag_build(
    governed: GovernedBuildService, approvals: GovernanceApprovalService, dataset_service
) -> str:
    source = dataset_service.create_source(
        ManualSourceCreate(name="RAG Handoff Source", language="en"), ADMIN
    )
    record = dataset_service.create_record(
        RecordCreate(
            source_public_id=source["public_id"],
            record_type="pretrain",
            language="en",
            input_text="RAG handoff eligible content.",
        ),
        ADMIN,
    )
    dataset_service.transition(record["public_id"], "pending_review", "edit", None, ADMIN)
    dataset_service.review(record["public_id"], ReviewDecision.APPROVE, "ok", ADMIN)
    approvals.evaluate("dataset_record", record["public_id"], "rag", admin_id=ADMIN)

    created = governed.create(target_pipeline="rag", admin_id=ADMIN)
    governed.preflight(created["public_id"], admin_id=ADMIN)
    governed.confirm(created["public_id"], admin_id=ADMIN)
    governed.execute(created["public_id"], admin_id=ADMIN)
    return created["public_id"]


class TestGovernedRagIngestion:
    def test_cannot_ingest_before_build_is_completed(
        self,
        governed: GovernedBuildService,
        rag_handoff: GovernedRagHandoffService,
        knowledge_space: dict,
    ):
        created = governed.create(target_pipeline="rag", admin_id=ADMIN)
        with pytest.raises(ValidationError):
            rag_handoff.ingest(
                created["public_id"],
                knowledge_space_public_id=knowledge_space["public_id"],
                title="Test RAG Source",
                admin_id=ADMIN,
            )

    def test_cannot_ingest_a_non_rag_target_build(
        self,
        governed: GovernedBuildService,
        rag_handoff: GovernedRagHandoffService,
        knowledge_space: dict,
    ):
        created = governed.create(target_pipeline="evaluation", admin_id=ADMIN)
        with pytest.raises(ValidationError):
            rag_handoff.ingest(
                created["public_id"],
                knowledge_space_public_id=knowledge_space["public_id"],
                title="Test RAG Source",
                admin_id=ADMIN,
            )

    def test_ingest_creates_a_real_rag_source_with_lineage(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        rag_handoff: GovernedRagHandoffService,
        knowledge_space: dict,
    ):
        request_id = _completed_rag_build(governed, approvals, dataset_service)
        source = rag_handoff.ingest(
            request_id,
            knowledge_space_public_id=knowledge_space["public_id"],
            title="Governed RAG Source",
            admin_id=ADMIN,
        )
        assert source["source_type"] == "dataset_version"
        assert source["approval_status"] in ("draft", "review_required")

        fetched = governed.get(request_id)
        assert any(link["artifact_type"] == "rag_source" for link in fetched["artifact_links"])

    def test_ingest_prevents_duplicate_ingestion_of_the_same_build(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        rag_handoff: GovernedRagHandoffService,
        knowledge_space: dict,
    ):
        request_id = _completed_rag_build(governed, approvals, dataset_service)
        rag_handoff.ingest(
            request_id,
            knowledge_space_public_id=knowledge_space["public_id"],
            title="First Ingestion",
            admin_id=ADMIN,
        )
        with pytest.raises(ConflictError):
            rag_handoff.ingest(
                request_id,
                knowledge_space_public_id=knowledge_space["public_id"],
                title="Second Ingestion",
                admin_id=ADMIN,
            )
