"""Validated repository boundary for Brud AI persistence."""

from backend.database.repositories.base import (
    ConflictError,
    NotFoundError,
    RepositoryError,
    ValidationError,
)
from backend.database.repositories.phase2 import (
    AdminApprovalRepository,
    AuditLogRepository,
    DatasetRecordRepository,
    DatasetReviewRepository,
    DatasetSourceRepository,
    DatasetVersionRepository,
    FeedbackRepository,
    ModelAssignmentRepository,
    ModelRegistryRepository,
    ModelVersionRepository,
    SettingsRepository,
    TrainingJobRepository,
)

__all__ = [
    "AdminApprovalRepository",
    "AuditLogRepository",
    "ConflictError",
    "DatasetRecordRepository",
    "DatasetReviewRepository",
    "DatasetSourceRepository",
    "DatasetVersionRepository",
    "FeedbackRepository",
    "ModelAssignmentRepository",
    "ModelRegistryRepository",
    "ModelVersionRepository",
    "NotFoundError",
    "RepositoryError",
    "SettingsRepository",
    "TrainingJobRepository",
    "ValidationError",
]
