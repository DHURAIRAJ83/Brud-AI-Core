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
from backend.services.public_commercial_preflight_service import (
    PublicCommercialPreflightService,
)

ADMIN = "admin-1"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "public_commercial.db"
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
def preflight(settings: Settings) -> PublicCommercialPreflightService:
    return PublicCommercialPreflightService(settings)


def _approved_record(dataset_service: DatasetService, *, suffix: str) -> dict:
    source = dataset_service.create_source(
        ManualSourceCreate(name=f"Public Export Source {suffix}", language="en"), ADMIN
    )
    record = dataset_service.create_record(
        RecordCreate(
            source_public_id=source["public_id"],
            record_type="pretrain",
            language="en",
            input_text=f"Public export candidate text {suffix}.",
        ),
        ADMIN,
    )
    dataset_service.transition(record["public_id"], "pending_review", "edit", None, ADMIN)
    return dataset_service.review(record["public_id"], ReviewDecision.APPROVE, "ok", ADMIN)


class TestPublicCommercialPreflight:
    def test_rejects_a_non_public_commercial_target(
        self, governed: GovernedBuildService, preflight: PublicCommercialPreflightService
    ):
        created = governed.create(target_pipeline="rag", admin_id=ADMIN)
        with pytest.raises(ValidationError):
            preflight.check(created["public_id"])

    def test_reports_blocked_items_with_reasons_for_unapproved_public_export(
        self,
        governed: GovernedBuildService,
        dataset_service: DatasetService,
        preflight: PublicCommercialPreflightService,
    ):
        _approved_record(dataset_service, suffix="P1")
        created = governed.create(target_pipeline="public_export", admin_id=ADMIN)
        governed.preflight(created["public_id"], admin_id=ADMIN)
        report = preflight.check(created["public_id"])
        assert report["target_use"] == "public_export"
        assert report["blocked_count"] >= 1
        assert all("decision_code" in item for item in report["blocked_items"])

    def test_allows_an_entity_with_a_genuine_public_export_approval(
        self,
        governed: GovernedBuildService,
        approvals: GovernanceApprovalService,
        dataset_service: DatasetService,
        preflight: PublicCommercialPreflightService,
    ):
        record = _approved_record(dataset_service, suffix="P2")
        # A prior explicit governance scan (Step 5) makes this record
        # non-legacy before the governed build's own preflight runs.
        approvals.evaluate("dataset_record", record["public_id"], "public_export", admin_id=ADMIN)
        created = governed.create(target_pipeline="public_export", admin_id=ADMIN)
        governed.preflight(created["public_id"], admin_id=ADMIN)
        report = preflight.check(created["public_id"])
        matching = [
            item for item in report["allowed_items"]
            if item["entity_public_id"] == record["public_id"]
        ]
        assert len(matching) == 1
        assert matching[0]["decision"] == "allowed"
