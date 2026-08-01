from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.models.domain import ReviewDecision
from backend.services.dataset_service import DatasetService
from backend.services.dataset_versioning import DatasetVersioningService
from backend.services.governance_service import GovernanceApprovalService
from backend.services.governed_build_service import GovernedBuildService

ADMIN = "admin-1"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "governed_build.db"
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
def versioning(settings: Settings) -> DatasetVersioningService:
    repository = DatasetQualityRepository(settings.resolved_database_path)
    return DatasetVersioningService(repository, settings)


@pytest.fixture
def approvals(settings: Settings) -> GovernanceApprovalService:
    return GovernanceApprovalService(settings)


def _make_record(dataset_service: DatasetService, *, name_suffix: str, text: str) -> dict:
    source = dataset_service.create_source(
        ManualSourceCreate(name=f"Governed Build Source {name_suffix}", language="en"), ADMIN
    )
    record = dataset_service.create_record(
        RecordCreate(
            source_public_id=source["public_id"],
            record_type="pretrain",
            language="en",
            input_text=text,
        ),
        ADMIN,
    )
    dataset_service.transition(record["public_id"], "pending_review", "edit", None, ADMIN)
    return dataset_service.review(record["public_id"], ReviewDecision.APPROVE, "looks good", ADMIN)


def _scan_and_approve(approvals: GovernanceApprovalService, record_public_id: str) -> None:
    """Simulates Step 5's "explicit governance scan and approval" --
    without this, a dataset_record is always legacy_unclassified."""

    decision = approvals.evaluate(
        "dataset_record", record_public_id, "dataset_export", admin_id=ADMIN
    )
    assert decision["decision"] == "allowed"


class TestBuildRequestLifecycle:
    def test_create_and_get(self, governed: GovernedBuildService):
        created = governed.create(target_pipeline="rag", build_label="test build", admin_id=ADMIN)
        assert created["status"] == "draft"
        assert created["target_pipeline"] == "rag"
        fetched = governed.get(created["public_id"])
        assert fetched["build_code"] == created["build_code"]
        assert fetched["latest_preflight"] is None

    def test_create_rejects_unknown_pipeline(self, governed: GovernedBuildService):
        with pytest.raises(ValidationError):
            governed.create(target_pipeline="not_a_real_pipeline", admin_id=ADMIN)

    def test_list_and_counts(self, governed: GovernedBuildService):
        governed.create(target_pipeline="rag", admin_id=ADMIN)
        governed.create(target_pipeline="evaluation", admin_id=ADMIN)
        listing = governed.list()
        assert listing["total"] >= 2
        assert listing["counts_by_status"].get("draft", 0) >= 2

    def test_cancel_moves_to_terminal_status(self, governed: GovernedBuildService):
        created = governed.create(target_pipeline="rag", admin_id=ADMIN)
        cancelled = governed.cancel(created["public_id"], admin_id=ADMIN)
        assert cancelled["status"] == "cancelled"
        with pytest.raises(ValidationError):
            governed.cancel(created["public_id"], admin_id=ADMIN)


class TestPreviewAndPreflight:
    def test_preview_does_not_persist_a_preflight_result(
        self, governed: GovernedBuildService, dataset_service: DatasetService
    ):
        _make_record(dataset_service, name_suffix="A", text="Some pretraining text here.")
        created = governed.create(target_pipeline="dataset_version", admin_id=ADMIN)
        preview = governed.preview(created["public_id"], admin_id=ADMIN)
        assert "eligible_records" in preview
        fetched = governed.get(created["public_id"])
        assert fetched["latest_preflight"] is None
        assert fetched["status"] == "draft"

    def test_fresh_record_is_legacy_and_blocked_at_preflight(
        self, governed: GovernedBuildService, dataset_service: DatasetService
    ):
        _make_record(dataset_service, name_suffix="B", text="Fresh record with no governance.")
        created = governed.create(target_pipeline="dataset_version", admin_id=ADMIN)
        result = governed.preflight(created["public_id"], admin_id=ADMIN)
        assert result["status"] == "blocked"
        items = governed.items(created["public_id"])["items"]
        assert any(item["decision"] == "blocked" for item in items)
        assert any(item["decision_code"] == "LEGACY_UNCLASSIFIED" for item in items)

    def test_governance_scanned_record_is_eligible_at_preflight(
        self,
        governed: GovernedBuildService,
        dataset_service: DatasetService,
        approvals: GovernanceApprovalService,
    ):
        record = _make_record(dataset_service, name_suffix="C", text="Scanned pretraining text.")
        _scan_and_approve(approvals, record["public_id"])
        created = governed.create(target_pipeline="dataset_version", admin_id=ADMIN)
        result = governed.preflight(created["public_id"], admin_id=ADMIN)
        assert result["status"] == "preflight_ready"
        items = governed.items(created["public_id"])["items"]
        assert any(
            item["entity_public_id"] == record["public_id"] and item["decision"] == "eligible"
            for item in items
        )


class TestConfirmAndExecute:
    def test_cannot_confirm_before_preflight(self, governed: GovernedBuildService):
        created = governed.create(target_pipeline="rag", admin_id=ADMIN)
        with pytest.raises(ValidationError):
            governed.confirm(created["public_id"], admin_id=ADMIN)

    def test_cannot_execute_before_confirm(
        self,
        governed: GovernedBuildService,
        dataset_service: DatasetService,
        approvals: GovernanceApprovalService,
    ):
        record = _make_record(dataset_service, name_suffix="D", text="Needs confirm first.")
        _scan_and_approve(approvals, record["public_id"])
        created = governed.create(target_pipeline="dataset_version", admin_id=ADMIN)
        governed.preflight(created["public_id"], admin_id=ADMIN)
        with pytest.raises(ValidationError):
            governed.execute(created["public_id"], admin_id=ADMIN)

    def test_full_lifecycle_creates_a_real_dataset_version_with_lineage(
        self,
        governed: GovernedBuildService,
        dataset_service: DatasetService,
        approvals: GovernanceApprovalService,
        versioning: DatasetVersioningService,
    ):
        record = _make_record(dataset_service, name_suffix="E", text="Full lifecycle text here.")
        _scan_and_approve(approvals, record["public_id"])
        created = governed.create(
            target_pipeline="dataset_version",
            build_label="full lifecycle test",
            configuration={"dataset_name": "governed-e2e", "dataset_version": "v1"},
            admin_id=ADMIN,
        )
        governed.preflight(created["public_id"], admin_id=ADMIN)
        governed.confirm(created["public_id"], admin_id=ADMIN)
        completed = governed.execute(created["public_id"], admin_id=ADMIN)
        assert completed["status"] == "completed"
        assert completed["result_entity_type"] == "dataset_version"
        assert completed["result_entity_public_id"]

        fetched = governed.get(created["public_id"])
        assert len(fetched["artifact_links"]) == 1
        assert fetched["artifact_links"][0]["artifact_type"] == "dataset_version"

        version = versioning.get_version(fetched["artifact_links"][0]["artifact_public_id"])
        assert version["status"] == "ready"
        assert version["record_count"] == 1


class TestSelectionOverrides:
    def test_cannot_manually_include_a_blocked_item(
        self, governed: GovernedBuildService, dataset_service: DatasetService
    ):
        _make_record(dataset_service, name_suffix="G", text="Blocked legacy record.")
        created = governed.create(target_pipeline="dataset_version", admin_id=ADMIN)
        governed.preflight(created["public_id"], admin_id=ADMIN)
        items = governed.items(created["public_id"])["items"]
        blocked_item = next(i for i in items if i["decision"] == "blocked")
        with pytest.raises(ValidationError):
            governed.update_selection(
                created["public_id"], blocked_item["public_id"], included=True, admin_id=ADMIN
            )

    def test_legacy_override_reason_allows_inclusion_with_a_warning(
        self, governed: GovernedBuildService, dataset_service: DatasetService
    ):
        record = _make_record(dataset_service, name_suffix="F", text="Legacy override case.")
        created = governed.create(
            target_pipeline="dataset_version",
            configuration={"legacy_overrides": {record["public_id"]: "reviewed offline"}},
            admin_id=ADMIN,
        )
        result = governed.preflight(created["public_id"], admin_id=ADMIN)
        assert result["status"] == "preflight_ready"
        items = governed.items(created["public_id"])["items"]
        matching = [i for i in items if i["entity_public_id"] == record["public_id"]]
        assert matching[0]["decision"] == "warning"
