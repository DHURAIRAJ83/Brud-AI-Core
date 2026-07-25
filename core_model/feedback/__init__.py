"""Phase 18 feedback/human-review/improvement-pipeline pure-function package.

Feedback must never mean "input that automatically trains the model."
Feedback means: privacy-safe, reviewed, explicitly-approved evidence
that may become a dataset candidate or a regression fixture -- both of
which still require further explicit action (dataset approval,
regression-suite activation) before they influence anything else. Every
enum below is the single source of truth shared by the backend
services, matching the corresponding CHECK constraints in
``backend/database/schema.py``'s ``PHASE18_SCHEMA``.
"""

from __future__ import annotations

SUBJECT_TYPES = (
    "inference_result",
    "rag_grounded_answer",
    "conversation_response",
    "evaluation_output",
    "memory_orchestration_response",
    "release_candidate",
    "model_release",
)

FEEDBACK_TYPES = (
    "thumbs_up",
    "thumbs_down",
    "rating",
    "issue_report",
    "correction",
    "citation_report",
    "safety_report",
    "language_report",
    "memory_report",
    "retrieval_report",
)

FEEDBACK_STATUSES = (
    "submitted",
    "triaged",
    "in_review",
    "reviewed",
    "candidate_created",
    "resolved",
    "rejected",
    "expired",
    "deleted",
    "archived",
)

SEVERITIES = ("info", "low", "medium", "high", "critical")

CLASSIFICATION_CATEGORIES = (
    "helpful",
    "unhelpful",
    "incorrect",
    "partially_correct",
    "unsupported_claim",
    "hallucination_like",
    "wrong_language",
    "poor_tamil",
    "poor_tanglish",
    "format_failure",
    "instruction_not_followed",
    "citation_missing",
    "citation_invalid",
    "citation_wrong",
    "retrieval_irrelevant",
    "retrieval_missing",
    "unsafe_response",
    "over_refusal",
    "under_refusal",
    "prompt_leakage",
    "role_token_leakage",
    "repetition",
    "memory_wrong",
    "memory_outdated",
    "memory_privacy_issue",
    "memory_not_used",
    "memory_should_not_be_used",
    "too_long",
    "too_short",
    "unclear",
    "other",
)

# Categories that are always safety-critical regardless of admin-assigned
# severity -- these must enter priority review deterministically, never
# via opaque ranking.
CRITICAL_CLASSIFICATION_CATEGORIES = frozenset(
    {
        "unsafe_response",
        "prompt_leakage",
        "role_token_leakage",
        "memory_privacy_issue",
        "memory_should_not_be_used",
    }
)

PRIVACY_STATUSES = ("safe", "redacted", "requires_review", "blocked")
SAFETY_STATUSES = ("safe", "flagged", "blocked", "requires_review")

QUEUE_TYPES = (
    "general_quality",
    "language",
    "tamil_quality",
    "tanglish_quality",
    "citation",
    "retrieval",
    "safety",
    "privacy",
    "memory",
    "dataset_candidate",
    "regression",
)

ASSIGNMENT_STATUSES = ("assigned", "in_progress", "completed", "reassigned", "cancelled", "expired")

REVIEW_VERDICTS = (
    "valid_feedback",
    "partially_valid",
    "invalid_feedback",
    "needs_second_review",
    "privacy_blocked",
    "safety_blocked",
    "candidate_recommended",
    "regression_recommended",
)

DISAGREEMENT_STATUSES = ("none", "minor", "material", "requires_adjudication")

CORRECTION_STATUSES = ("draft", "validated", "validated_with_warnings", "rejected", "superseded")
MEMORY_USE_POLICIES = ("none", "reference_existing", "propose_new")

CANDIDATE_TYPES = (
    "instruction",
    "chat",
    "translation",
    "tanglish_pair",
    "safety",
    "preference",
    "evaluation_only",
)

CANDIDATE_STATUSES = (
    "draft",
    "validating",
    "review_required",
    "approved",
    "approved_with_warnings",
    "rejected",
    "quarantined",
    "exported",
    "archived",
)

LICENCE_STATUSES = ("approved", "restricted", "unknown", "blocked", "not_applicable")

DEDUPLICATION_STATUSES = (
    "unique",
    "exact_duplicate",
    "normalized_duplicate",
    "near_duplicate",
    "prompt_duplicate",
    "response_duplicate",
    "prompt_response_duplicate",
)

CONTAMINATION_STATUSES = (
    "clean",
    "training_duplicate",
    "validation_leakage",
    "test_leakage",
    "evaluation_fixture_leakage",
    "regression_fixture_leakage",
    "subject_output_copy",
    "hidden_prompt_leakage",
)

# Leakage kinds that must block approval outright -- never merely warn.
BLOCKING_CONTAMINATION_STATUSES = frozenset(
    {
        "test_leakage",
        "evaluation_fixture_leakage",
        "regression_fixture_leakage",
        "hidden_prompt_leakage",
    }
)

QUALITY_DIMENSIONS = (
    "clarity",
    "correctness_support",
    "instruction_quality",
    "response_quality",
    "language_quality",
    "format_quality",
    "safety_quality",
    "citation_quality",
    "provenance_completeness",
    "licence_completeness",
    "privacy_safety",
    "deduplication",
    "contamination_safety",
)
QUALITY_STATUSES = ("pass", "warning", "fail", "not_assessed")

APPROVAL_DECISIONS = ("approve", "approve_with_warning", "reject", "request_changes", "quarantine")

REGRESSION_CATEGORIES = (
    "language_regression",
    "tamil_quality_regression",
    "tanglish_regression",
    "instruction_following_regression",
    "citation_regression",
    "retrieval_regression",
    "safety_regression",
    "memory_regression",
    "privacy_regression",
    "format_regression",
    "repetition_regression",
)

REGRESSION_SUITE_STATUSES = ("draft", "validated", "active", "retired", "archived")
REGRESSION_RUN_STATUSES = ("draft", "queued", "running", "completed", "failed")

COMPARISON_COMPATIBILITIES = ("compatible", "partially_compatible", "incompatible")
COMPARISON_RESULTS = ("improved", "mixed", "unchanged", "regressed", "incomparable")

POLICY_LIFECYCLE_STATUSES = ("draft", "validated", "active", "deprecated", "archived")
QUEUE_LIFECYCLE_STATUSES = ("draft", "active", "archived")

NO_AUTOMATIC_TRAINING_NOTICE = (
    "Feedback is reviewed, privacy-filtered, and explicitly approved "
    "before it can become a dataset candidate. No automatic self-training occurs."
)
DATASET_PIPELINE_REUSE_NOTICE = (
    "An approved feedback candidate still passes through the existing "
    "dataset quality and versioning pipeline before training use."
)
REGRESSION_EVALUATION_ONLY_NOTICE = (
    "Regression fixtures are evaluation-only evidence and must not "
    "automatically become training records."
)
