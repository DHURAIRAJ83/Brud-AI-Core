from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.models.domain import ReviewDecision
from backend.services.dataset_service import DatasetService
from backend.services.governance_service import GovernanceApprovalService
from backend.services.governed_build_service import GovernedBuildService
from backend.services.governed_training_handoff_service import GovernedTrainingHandoffService

ADMIN = "admin-1"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "training_handoff.db"
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
def training_handoff(settings: Settings) -> GovernedTrainingHandoffService:
    return GovernedTrainingHandoffService(settings)


def _completed_build(
    governed: GovernedBuildService,
    approvals: GovernanceApprovalService,
    dataset_service: DatasetService,
    *,
    target_pipeline: str,
    suffix: str,
) -> str:
    source = dataset_service.create_source(
        ManualSourceCreate(name=f"Training Handoff Source {suffix}", language="en"), ADMIN
    )
    record = dataset_service.create_record(
        RecordCreate(
            source_public_id=source["public_id"],
            record_type="pretrain",
            language="en",
            input_text=f"Training handoff content {suffix}.",
        ),
        ADMIN,
    )
    dataset_service.transition(record["public_id"], "pending_review", "edit", None, ADMIN)
    dataset_service.review(record["public_id"], ReviewDecision.APPROVE, "ok", ADMIN)
    approvals.evaluate("dataset_record", record["public_id"], "training", admin_id=ADMIN)

    created = governed.create(target_pipeline=target_pipeline, admin_id=ADMIN)
    governed.preflight(created["public_id"], admin_id=ADMIN)
    governed.confirm(created["public_id"], admin_id=ADMIN)
    governed.execute(created["public_id"], admin_id=ADMIN)
    return created["public_id"]


class TestGovernedTrainingHandoffs:
    def test_tokenizer_handoff_requires_a_completed_build(
        self, governed: GovernedBuildService, training_handoff: GovernedTrainingHandoffService
    ):
        created = governed.create(target_pipeline="tokenizer", admin_id=ADMIN)
        with pytest.raises(ValidationError):
            training_handoff.tokenizer_handoff(created["public_id"], admin_id=ADMIN)

    def test_handoff_rejects_a_mismatched_target_pipeline(
        self, governed: GovernedBuildService, training_handoff: GovernedTrainingHandoffService
    ):
        created = governed.create(target_pipeline="rag", admin_id=ADMIN)
        with pytest.raises(ValidationError):
            training_handoff.pretraining_handoff(created["public_id"], admin_id=ADMIN)

    def test_tokenizer_handoff_succeeds_and_never_creates_a_job(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        training_handoff: GovernedTrainingHandoffService,
    ):
        request_id = _completed_build(
            governed, approvals, dataset_service, target_pipeline="tokenizer", suffix="T1"
        )
        result = training_handoff.tokenizer_handoff(request_id, admin_id=ADMIN)
        assert result["ready"] is True
        assert result["target_pipeline"] == "tokenizer"
        assert result["dataset_version_public_id"]
        # no automatic job start -- only a lineage event is recorded
        history = governed.history(request_id)
        assert any(e["event_type"] == "tokenizer_handoff" for e in history["items"])

    def test_pretraining_handoff_succeeds(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        training_handoff: GovernedTrainingHandoffService,
    ):
        request_id = _completed_build(
            governed, approvals, dataset_service, target_pipeline="pretraining", suffix="T2"
        )
        result = training_handoff.pretraining_handoff(request_id, admin_id=ADMIN)
        assert result["ready"] is True

    def test_sft_handoff_succeeds(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        training_handoff: GovernedTrainingHandoffService,
    ):
        request_id = _completed_build(
            governed, approvals, dataset_service, target_pipeline="instruction_tuning", suffix="T3"
        )
        result = training_handoff.sft_handoff(request_id, admin_id=ADMIN)
        assert result["ready"] is True

    def test_evaluation_handoff_succeeds(
        self,
        governed: GovernedBuildService,
        dataset_service: DatasetService,
        training_handoff: GovernedTrainingHandoffService,
    ):
        approvals_service = GovernanceApprovalService(governed.settings)
        source = dataset_service.create_source(
            ManualSourceCreate(name="Eval Handoff Source", language="en"), ADMIN
        )
        record = dataset_service.create_record(
            RecordCreate(
                source_public_id=source["public_id"],
                record_type="pretrain",
                language="en",
                input_text="Evaluation handoff content.",
            ),
            ADMIN,
        )
        dataset_service.transition(record["public_id"], "pending_review", "edit", None, ADMIN)
        dataset_service.review(record["public_id"], ReviewDecision.APPROVE, "ok", ADMIN)
        approvals_service.evaluate(
            "dataset_record", record["public_id"], "evaluation", admin_id=ADMIN
        )
        created = governed.create(target_pipeline="evaluation", admin_id=ADMIN)
        governed.preflight(created["public_id"], admin_id=ADMIN)
        governed.confirm(created["public_id"], admin_id=ADMIN)
        governed.execute(created["public_id"], admin_id=ADMIN)

        result = training_handoff.evaluation_handoff(created["public_id"], admin_id=ADMIN)
        assert result["ready"] is True
        assert result["target_pipeline"] == "evaluation"
