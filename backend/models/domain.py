"""Validated Phase 2 database and public domain schemas."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from backend.core.validation import (
    AssignmentKey,
    DomainModel,
    LanguageCode,
    PublicIdModel,
    validate_version_label,
)


class DatasetSourceType(StrEnum):
    MANUAL = "manual"
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PDF = "pdf"
    TEXT = "text"
    CHAT_FEEDBACK = "chat_feedback"
    GENERATED = "generated"


class LicenceStatus(StrEnum):
    UNKNOWN = "unknown"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"


class DatasetSourceStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class DatasetRecordType(StrEnum):
    PRETRAIN = "pretrain"
    INSTRUCTION = "instruction"
    CHAT = "chat"
    TRANSLATION = "translation"
    TANGLISH_PAIR = "tanglish_pair"
    SAFETY = "safety"
    PREFERENCE = "preference"


class DatasetRecordStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    EDIT = "edit"
    RESTORE = "restore"


class ReviewerType(StrEnum):
    ADMIN = "admin"
    SYSTEM = "system"
    ADMIN_ASSISTANT = "admin_assistant"


class DatasetVersionStatus(StrEnum):
    DRAFT = "draft"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class TrainingType(StrEnum):
    TOKENIZER = "tokenizer"
    SMOKE_TEST = "smoke_test"
    BASE_PRETRAINING = "base_pretraining"
    CONTINUED_PRETRAINING = "continued_pretraining"
    INSTRUCTION_TUNING = "instruction_tuning"
    TANGLISH_TUNING = "tanglish_tuning"
    TRANSLATION_TUNING = "translation_tuning"
    SAFETY_TUNING = "safety_tuning"
    PREFERENCE_TUNING = "preference_tuning"


class TrainingStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelType(StrEnum):
    CORE = "core"
    CHAT = "chat"
    EMBEDDING = "embedding"
    TANGLISH_NORMALIZER = "tanglish_normalizer"
    EXTERNAL_REFERENCE = "external_reference"


class RegistryStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class ModelLifecycleStatus(StrEnum):
    DRAFT = "draft"
    TRAINING = "training"
    EVALUATING = "evaluating"
    STAGING = "staging"
    ACTIVE = "active"
    FAILED = "failed"
    RETIRED = "retired"


class FeedbackType(StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"
    WRONG_ANSWER = "wrong_answer"
    LANGUAGE_ISSUE = "language_issue"
    UNSAFE_ANSWER = "unsafe_answer"
    INCOMPLETE_ANSWER = "incomplete_answer"
    SUGGESTED_CORRECTION = "suggested_correction"


class FeedbackStatus(StrEnum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONVERTED_TO_DATASET = "converted_to_dataset"
    ARCHIVED = "archived"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    WARNING = "warning"


class DatasetSourceCreate(DomainModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: DatasetSourceType
    original_filename: str | None = None
    source_uri: str | None = None
    language: LanguageCode = LanguageCode.UNKNOWN
    licence_name: str | None = None
    licence_status: LicenceStatus = LicenceStatus.UNKNOWN
    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: DatasetSourceStatus = DatasetSourceStatus.DRAFT
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetSourceUpdate(DomainModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: DatasetSourceStatus | None = None
    metadata: dict[str, Any] | None = None


class DatasetSourceRecord(PublicIdModel, DatasetSourceCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class DatasetSourcePublic(DatasetSourceCreate, PublicIdModel):
    created_at: datetime
    updated_at: datetime


class DatasetRecordCreate(DomainModel):
    source_public_id: str | None = None
    record_type: DatasetRecordType
    language: LanguageCode
    instruction: str | None = None
    input_text: str | None = None
    output_text: str | None = None
    normalized_input: str | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality_score: float | None = Field(default=None, ge=0, le=1)
    status: DatasetRecordStatus = DatasetRecordStatus.DRAFT
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetRecordUpdate(DomainModel):
    quality_score: float | None = Field(default=None, ge=0, le=1)
    status: DatasetRecordStatus | None = None
    metadata: dict[str, Any] | None = None


class DatasetRecordRecord(PublicIdModel, DatasetRecordCreate):
    id: int
    source_id: int | None = None
    created_at: datetime
    updated_at: datetime


class DatasetRecordPublic(DatasetRecordCreate, PublicIdModel):
    created_at: datetime
    updated_at: datetime


class DatasetReviewCreate(DomainModel):
    dataset_record_public_id: str
    decision: ReviewDecision
    reviewer_type: ReviewerType
    reviewer_reference: str | None = None
    comments: str | None = None
    new_status: DatasetRecordStatus


class DatasetReviewUpdate(DomainModel):
    comments: str | None = None


class DatasetReviewRecord(PublicIdModel):
    id: int
    dataset_record_id: int
    decision: ReviewDecision
    reviewer_type: ReviewerType
    reviewer_reference: str | None
    comments: str | None
    previous_status: DatasetRecordStatus
    new_status: DatasetRecordStatus
    created_at: datetime


class DatasetReviewPublic(PublicIdModel):
    decision: ReviewDecision
    reviewer_type: ReviewerType
    reviewer_reference: str | None
    comments: str | None
    previous_status: DatasetRecordStatus
    new_status: DatasetRecordStatus
    created_at: datetime


class DatasetVersionCreate(DomainModel):
    name: str = Field(min_length=1, max_length=255)
    version: str
    description: str | None = None
    status: DatasetVersionStatus = DatasetVersionStatus.DRAFT
    manifest: dict[str, Any] = Field(default_factory=dict)
    record_count: int = Field(default=0, ge=0)
    language_distribution: dict[str, Any] = Field(default_factory=dict)
    split_distribution: dict[str, Any] = Field(default_factory=dict)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return validate_version_label(value)


class DatasetVersionUpdate(DomainModel):
    description: str | None = None
    status: DatasetVersionStatus | None = None
    manifest: dict[str, Any] | None = None


class DatasetVersionRecord(PublicIdModel, DatasetVersionCreate):
    id: int
    created_at: datetime
    finalized_at: datetime | None


class DatasetVersionPublic(DatasetVersionCreate, PublicIdModel):
    created_at: datetime
    finalized_at: datetime | None


class TrainingJobCreate(DomainModel):
    name: str = Field(min_length=1, max_length=255)
    training_type: TrainingType
    status: TrainingStatus = TrainingStatus.DRAFT
    dataset_version_public_id: str | None = None
    base_model_version_public_id: str | None = None
    tokenizer_reference: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    hardware_profile: str = "unspecified"
    progress: float = Field(default=0, ge=0, le=1)
    current_step: int = Field(default=0, ge=0)
    total_steps: int = Field(default=0, ge=0)


class TrainingJobUpdate(DomainModel):
    status: TrainingStatus | None = None
    progress: float | None = Field(default=None, ge=0, le=1)
    current_step: int | None = Field(default=None, ge=0)


class TrainingJobRecord(PublicIdModel, TrainingJobCreate):
    id: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class TrainingJobPublic(TrainingJobCreate, PublicIdModel):
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class TrainingJobEventCreate(DomainModel):
    training_job_public_id: str
    event_type: str
    previous_status: TrainingStatus | None = None
    new_status: TrainingStatus | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrainingJobEventUpdate(DomainModel):
    message: str | None = None


class TrainingJobEventRecord(TrainingJobEventCreate):
    id: int
    training_job_id: int
    created_at: datetime


class TrainingJobEventPublic(TrainingJobEventCreate):
    created_at: datetime


class ModelRegistryCreate(DomainModel):
    name: str = Field(min_length=1, max_length=255)
    model_type: ModelType
    description: str | None = None
    status: RegistryStatus = RegistryStatus.DRAFT


class ModelRegistryUpdate(DomainModel):
    description: str | None = None
    status: RegistryStatus | None = None


class ModelRegistryRecord(PublicIdModel, ModelRegistryCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class ModelRegistryPublic(ModelRegistryCreate, PublicIdModel):
    created_at: datetime
    updated_at: datetime


class ModelVersionCreate(DomainModel):
    model_registry_public_id: str
    version: str
    lifecycle_status: ModelLifecycleStatus = ModelLifecycleStatus.DRAFT
    architecture: str
    parameter_count: int | None = Field(default=None, ge=0)
    context_length: int | None = Field(default=None, ge=1)
    vocabulary_size: int | None = Field(default=None, ge=1)
    tokenizer_reference: str | None = None
    checkpoint_path: str | None = None
    export_path: str | None = None
    quantization: str | None = None
    dataset_version_public_id: str | None = None
    training_job_public_id: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return validate_version_label(value)


class ModelVersionUpdate(DomainModel):
    lifecycle_status: ModelLifecycleStatus | None = None
    metrics: dict[str, Any] | None = None


class ModelVersionRecord(PublicIdModel, ModelVersionCreate):
    id: int
    model_registry_id: int
    created_at: datetime
    activated_at: datetime | None


class ModelVersionPublic(ModelVersionCreate, PublicIdModel):
    created_at: datetime
    activated_at: datetime | None


class ModelAssignmentCreate(DomainModel):
    assignment_key: AssignmentKey
    model_version_public_id: str | None = None
    fallback_model_version_public_id: str | None = None
    enabled: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)


class ModelAssignmentUpdate(DomainModel):
    model_version_public_id: str | None = None
    fallback_model_version_public_id: str | None = None
    enabled: bool | None = None
    configuration: dict[str, Any] | None = None


class ModelAssignmentRecord(ModelAssignmentCreate):
    id: int
    updated_at: datetime


class ModelAssignmentPublic(ModelAssignmentCreate):
    updated_at: datetime


class UserFeedbackCreate(DomainModel):
    chat_message_public_id: str | None = None
    feedback_type: FeedbackType
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None
    suggested_answer: str | None = None
    status: FeedbackStatus = FeedbackStatus.NEW


class UserFeedbackUpdate(DomainModel):
    status: FeedbackStatus | None = None


class UserFeedbackRecord(PublicIdModel, UserFeedbackCreate):
    id: int
    created_at: datetime
    reviewed_at: datetime | None


class UserFeedbackPublic(UserFeedbackCreate, PublicIdModel):
    created_at: datetime
    reviewed_at: datetime | None


class AdminApprovalCreate(DomainModel):
    action_type: str
    target_type: str
    target_public_id: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    requested_by: str


class AdminApprovalUpdate(DomainModel):
    status: ApprovalStatus | None = None
    reviewed_by: str | None = None
    review_comment: str | None = None


class AdminApprovalRecord(PublicIdModel, AdminApprovalCreate):
    id: int
    status: ApprovalStatus
    reviewed_by: str | None
    review_comment: str | None
    created_at: datetime
    reviewed_at: datetime | None


class AdminApprovalPublic(AdminApprovalCreate, PublicIdModel):
    status: ApprovalStatus
    reviewed_by: str | None
    review_comment: str | None
    created_at: datetime
    reviewed_at: datetime | None


class AuditEventCreate(DomainModel):
    event_type: str
    actor_type: str
    actor_reference: str | None = None
    action: str
    resource_type: str | None = None
    resource_public_id: str | None = None
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEventUpdate(DomainModel):
    """Audit events are append-only; no fields are intentionally available."""


class AuditEventRecord(PublicIdModel, AuditEventCreate):
    id: int
    created_at: datetime


class AuditEventPublic(AuditEventCreate, PublicIdModel):
    created_at: datetime
