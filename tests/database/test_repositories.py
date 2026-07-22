from pathlib import Path

import pytest

from backend.core.validation import AssignmentKey, LanguageCode
from backend.database.migrations import initialize_database
from backend.database.repositories import (
    AuditLogRepository,
    ConflictError,
    DatasetRecordRepository,
    DatasetReviewRepository,
    DatasetSourceRepository,
    DatasetVersionRepository,
    ModelAssignmentRepository,
    ModelRegistryRepository,
    ModelVersionRepository,
    SettingsRepository,
    TrainingJobRepository,
    ValidationError,
)
from backend.database.repositories.phase2 import content_hash_for
from backend.models.domain import (
    AuditEventCreate,
    DatasetRecordCreate,
    DatasetRecordStatus,
    DatasetRecordType,
    DatasetReviewCreate,
    DatasetSourceCreate,
    DatasetSourceType,
    DatasetVersionCreate,
    DatasetVersionStatus,
    ModelAssignmentCreate,
    ModelLifecycleStatus,
    ModelRegistryCreate,
    ModelType,
    ModelVersionCreate,
    ReviewDecision,
    ReviewerType,
    TrainingJobCreate,
    TrainingStatus,
    TrainingType,
)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "repositories.db"
    initialize_database(path)
    return path


def create_source(database_path: Path):
    return DatasetSourceRepository(database_path).create(
        DatasetSourceCreate(name="Tamil manual", source_type=DatasetSourceType.MANUAL)
    )


def create_record(database_path: Path, source_public_id: str, text: str = "வணக்கம்"):
    return DatasetRecordRepository(database_path).create(
        DatasetRecordCreate(
            source_public_id=source_public_id,
            record_type=DatasetRecordType.INSTRUCTION,
            language=LanguageCode.TA,
            instruction="Greet",
            output_text=text,
            content_hash=content_hash_for("Greet", text),
        )
    )


def test_create_fetch_and_paginate_dataset_sources(database_path: Path) -> None:
    created = create_source(database_path)
    fetched = DatasetSourceRepository(database_path).get_by_public_id(created.public_id)
    assert fetched.name == "Tamil manual"
    assert DatasetSourceRepository(database_path).list(limit=1, offset=0) == [fetched]


def test_dataset_record_duplicate_hash_is_explicit(database_path: Path) -> None:
    source = create_source(database_path)
    first = create_record(database_path, source.public_id)
    assert first.record_type == "instruction"
    with pytest.raises(ConflictError, match="duplicate content hash"):
        create_record(database_path, source.public_id)


def test_review_changes_record_status_transactionally(database_path: Path) -> None:
    source = create_source(database_path)
    record = create_record(database_path, source.public_id)
    review = DatasetReviewRepository(database_path).create(
        DatasetReviewCreate(
            dataset_record_public_id=record.public_id,
            decision=ReviewDecision.APPROVE,
            reviewer_type=ReviewerType.ADMIN,
            new_status=DatasetRecordStatus.APPROVED,
        )
    )
    assert review.previous_status == "draft"
    assert (
        DatasetRecordRepository(database_path).get_by_public_id(record.public_id).status
        == "approved"
    )


def test_ready_dataset_version_is_immutable(database_path: Path) -> None:
    repository = DatasetVersionRepository(database_path)
    version = repository.create(
        DatasetVersionCreate(
            name="starter",
            version="v1",
            status=DatasetVersionStatus.READY,
            checksum_sha256="a" * 64,
        )
    )
    with pytest.raises(ValidationError, match="immutable"):
        repository.update_manifest(version.public_id, {"changed": True})


def test_invalid_training_transition_is_rejected(database_path: Path) -> None:
    repository = TrainingJobRepository(database_path)
    job = repository.create(
        TrainingJobCreate(name="future smoke", training_type=TrainingType.SMOKE_TEST)
    )
    with pytest.raises(ValidationError, match="invalid training transition"):
        repository.transition(job.public_id, TrainingStatus.COMPLETED)
    repository.transition(job.public_id, TrainingStatus.VALIDATING)
    assert repository.get_by_public_id(job.public_id).status == "validating"


def test_model_version_uniqueness_and_one_active_rule(database_path: Path) -> None:
    registry = ModelRegistryRepository(database_path).create(
        ModelRegistryCreate(name="Brud Core", model_type=ModelType.CORE)
    )
    repository = ModelVersionRepository(database_path)
    active = repository.create(
        ModelVersionCreate(
            model_registry_public_id=registry.public_id,
            version="v1",
            lifecycle_status=ModelLifecycleStatus.ACTIVE,
            architecture="placeholder",
        )
    )
    assert active.lifecycle_status == "active"
    with pytest.raises(ConflictError):
        repository.create(
            ModelVersionCreate(
                model_registry_public_id=registry.public_id,
                version="v1",
                architecture="placeholder",
            )
        )
    with pytest.raises(ConflictError):
        repository.create(
            ModelVersionCreate(
                model_registry_public_id=registry.public_id,
                version="v2",
                lifecycle_status=ModelLifecycleStatus.ACTIVE,
                architecture="placeholder",
            )
        )


def test_assignment_key_uniqueness(database_path: Path) -> None:
    repository = ModelAssignmentRepository(database_path)
    item = ModelAssignmentCreate(assignment_key=AssignmentKey.PUBLIC_CHAT)
    assert repository.create(item).assignment_key == "public_chat"
    with pytest.raises(ConflictError):
        repository.create(item)


def test_secret_setting_redaction(database_path: Path) -> None:
    repository = SettingsRepository(database_path)
    repository.set("future_api_key", "do-not-expose", is_secret=True)
    assert repository.get_safe("future_api_key")["value"] == "[REDACTED]"


def test_audit_is_append_only_redacted_and_paginated(database_path: Path) -> None:
    repository = AuditLogRepository(database_path)
    event = repository.append(
        AuditEventCreate(
            event_type="repository_test",
            actor_type="system",
            action="create",
            metadata={"api_key": "hidden", "safe": "visible"},
        )
    )
    assert event.metadata == {"api_key": "[REDACTED]", "safe": "visible"}
    assert repository.recent(limit=1, offset=0)[0].public_id == event.public_id
    with pytest.raises(ValidationError, match="append-only"):
        repository.delete(event.public_id)
