from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.models.domain import ReviewDecision
from backend.services.dataset_governance_manifest_service import DatasetGovernanceManifestService
from backend.services.dataset_service import DatasetService
from backend.services.governance_service import GovernanceApprovalService
from backend.services.governed_build_service import GovernedBuildService

ADMIN = "admin-1"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "manifest.db"
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
def manifests(settings: Settings) -> DatasetGovernanceManifestService:
    return DatasetGovernanceManifestService(settings)


def _approved_record(dataset_service: DatasetService, *, suffix: str) -> dict:
    source = dataset_service.create_source(
        ManualSourceCreate(name=f"Manifest Source {suffix}", language="en"), ADMIN
    )
    record = dataset_service.create_record(
        RecordCreate(
            source_public_id=source["public_id"],
            record_type="pretrain",
            language="en",
            input_text=f"Manifest test text {suffix}.",
        ),
        ADMIN,
    )
    dataset_service.transition(record["public_id"], "pending_review", "edit", None, ADMIN)
    return dataset_service.review(record["public_id"], ReviewDecision.APPROVE, "ok", ADMIN)


def _completed_build(
    governed: GovernedBuildService, approvals: GovernanceApprovalService, dataset_service
) -> str:
    record = _approved_record(dataset_service, suffix="M1")
    approvals.evaluate("dataset_record", record["public_id"], "dataset_export", admin_id=ADMIN)
    created = governed.create(
        target_pipeline="dataset_version",
        configuration={"dataset_name": "manifest-e2e", "dataset_version": "v1"},
        admin_id=ADMIN,
    )
    governed.preflight(created["public_id"], admin_id=ADMIN)
    governed.confirm(created["public_id"], admin_id=ADMIN)
    governed.execute(created["public_id"], admin_id=ADMIN)
    return created["public_id"]


class TestManifestGeneration:
    def test_cannot_generate_before_build_is_completed(
        self, governed: GovernedBuildService, manifests: DatasetGovernanceManifestService
    ):
        created = governed.create(target_pipeline="rag", admin_id=ADMIN)
        with pytest.raises(ValidationError):
            manifests.generate(created["public_id"], admin_id=ADMIN)

    def test_generate_produces_a_complete_extension(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        manifests: DatasetGovernanceManifestService,
    ):
        request_id = _completed_build(governed, approvals, dataset_service)
        extension = manifests.generate(request_id, admin_id=ADMIN)
        assert extension["record_count"] == 1
        assert extension["target_pipeline"] == "dataset_version"
        assert "source_manifest_checksum" in extension
        assert "record_manifest_checksum" in extension

    def test_generate_is_idempotent(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        manifests: DatasetGovernanceManifestService,
    ):
        request_id = _completed_build(governed, approvals, dataset_service)
        first = manifests.generate(request_id, admin_id=ADMIN)
        second = manifests.generate(request_id, admin_id=ADMIN)
        assert first == second

    def test_get_merges_dataset_version_manifest_and_governance_extension(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        manifests: DatasetGovernanceManifestService,
    ):
        request_id = _completed_build(governed, approvals, dataset_service)
        manifests.generate(request_id, admin_id=ADMIN)
        merged = manifests.get(request_id)
        assert merged["dataset_version_manifest"]
        assert merged["governance_extension"]["record_count"] == 1
