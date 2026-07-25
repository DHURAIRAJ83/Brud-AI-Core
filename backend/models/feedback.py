"""Phase 18 feedback/human-review/improvement-pipeline API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class FeedbackPolicyCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    allowed_subject_types: list[str] = Field(default_factory=list)
    allowed_feedback_types: list[str] = Field(default_factory=list)
    allow_free_text: bool = True
    allow_corrected_response: bool = True
    require_privacy_scan: bool = True
    require_safety_scan: bool = True
    require_human_review: bool = True
    require_dataset_approval: bool = True
    maximum_feedback_characters: int = Field(default=2000, ge=1, le=20_000)
    maximum_attachment_bytes: int = Field(default=2_000_000, ge=0, le=20_000_000)
    default_retention_seconds: int = Field(default=7_776_000, ge=0, le=31_536_000)
    allow_regression_fixture_creation: bool = True
    allow_dataset_candidate_creation: bool = True


class FeedbackPolicyPatch(DomainModel):
    description: str | None = Field(default=None, max_length=2000)
    maximum_feedback_characters: int | None = Field(default=None, ge=1, le=20_000)
    default_retention_seconds: int | None = Field(default=None, ge=0, le=31_536_000)


class FeedbackEventCreate(DomainModel):
    subject_type: str = Field(min_length=1, max_length=40)
    subject_reference_public_id: str = Field(min_length=1, max_length=80)
    feedback_policy_public_id: str
    participant_scope_key: str = Field(min_length=1, max_length=200)
    feedback_type: str = Field(min_length=1, max_length=40)
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=20_000)
    suggested_correction: str | None = Field(default=None, max_length=20_000)
    expected_language: str | None = Field(default=None, max_length=10)
    expected_citation_reference: str | None = Field(default=None, max_length=200)
    expected_retrieval_source_reference: str | None = Field(default=None, max_length=200)
    severity: str = Field(default="info", max_length=20)


class FeedbackClassificationCreate(DomainModel):
    category: str = Field(min_length=1, max_length=60)
    severity: str = Field(default="info", max_length=20)


class ReviewQueueCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    queue_type: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=2000)


class ReviewAssignmentCreate(DomainModel):
    feedback_event_public_id: str
    reviewer_admin_public_id: str
    due_at: str | None = None
    priority: str = Field(default="medium", max_length=20)
    conflict_of_interest_flag: bool = False


class HumanReviewCreate(DomainModel):
    rubric_version: str = Field(default="1", max_length=20)
    classification_confirmed: str | None = Field(default=None, max_length=60)
    severity_confirmed: str | None = Field(default=None, max_length=20)
    correctness_score: int | None = Field(default=None, ge=1, le=5)
    relevance_score: int | None = Field(default=None, ge=1, le=5)
    language_quality_score: int | None = Field(default=None, ge=1, le=5)
    safety_score: int | None = Field(default=None, ge=1, le=5)
    citation_score: int | None = Field(default=None, ge=1, le=5)
    retrieval_score: int | None = Field(default=None, ge=1, le=5)
    memory_use_score: int | None = Field(default=None, ge=1, le=5)
    overall_score: int = Field(ge=1, le=5)
    verdict: str = Field(min_length=1, max_length=40)
    comment: str = Field(default="", max_length=4000)


class CorrectedResponseCreate(DomainModel):
    corrected_response_text: str = Field(min_length=1, max_length=20_000)
    language: str = Field(default="unknown", max_length=10)
    citation_ids: list[str] = Field(default_factory=list)
    memory_use_policy: str = Field(default="none", max_length=40)


class DatasetCandidateCreate(DomainModel):
    prompt_text: str = Field(min_length=1, max_length=20_000)
    corrected_response_public_id: str | None = None
    candidate_type: str | None = Field(default=None, max_length=40)
    is_preference_pair: bool = False
    rejected_output_text: str | None = Field(default=None, max_length=20_000)


class CandidateApprovalCreate(DomainModel):
    comment: str = Field(default="", max_length=2000)


class RegressionSuiteCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class RegressionFixtureCreate(DomainModel):
    category: str = Field(min_length=1, max_length=60)
    language: str = Field(default="unknown", max_length=10)
    input_text: str = Field(min_length=1, max_length=4000)
    controlled_context: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: str = Field(min_length=1, max_length=2000)
    forbidden_behavior: str | None = Field(default=None, max_length=2000)
    expected_citations: list[str] = Field(default_factory=list)
    expected_memory_behavior: dict[str, Any] = Field(default_factory=dict)
    severity: str = Field(default="medium", max_length=20)
    source_feedback_event_public_ids: list[str] = Field(default_factory=list)


class RegressionRunCreate(DomainModel):
    model_assignment_public_id: str


class RegressionRunCompareRequest(DomainModel):
    left_run_public_id: str
    right_run_public_id: str


class ImprovementReportCreate(DomainModel):
    feedback_policy_public_id: str | None = None
    regression_run_public_id: str | None = None
    comparison_public_id: str | None = None
