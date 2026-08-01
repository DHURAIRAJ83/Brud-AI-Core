"""Phase 15 (this conversation's numbering, distinct from this
repository's own older internal "Phase 15" -- `model_assignment_service.py`
and `core_model.inference_runtime`) -- Text/NLP Final Production
Readiness enums.

Pure constants only, mirroring `core_model.training_incremental`'s shape.
No LLM, no side effects. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

# -- production RAG promotion ----------------------------------------------------------

RAG_PROMOTION_REQUEST_STATUSES = (
    "draft", "awaiting_review", "approved", "building_candidate", "candidate_ready",
    "validation_failed", "ready_for_activation", "rejected", "cancelled", "expired",
    "superseded",
)
RAG_PROMOTION_APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired", "superseded")
RAG_RELEASE_CANDIDATE_STATUSES = (
    "building", "built", "validating", "validated", "validation_failed", "activated",
    "superseded", "failed",
)
RAG_VALIDATION_RESULT_STATUSES = ("passed", "passed_with_warning", "failed", "not_applicable")
RAG_ACTIVATION_EVENT_TYPES = (
    "pre_activation_snapshot", "activated", "post_activation_check_passed",
    "post_activation_check_failed", "rolled_back", "activation_failed",
)
COMMERCIAL_USE_CONTEXTS = ("commercial", "non_commercial", "unknown")

# -- model release handoff (thin wrapper around the existing ModelReleaseService /
# ModelAssignmentService pipeline -- see plan doc section 0/3) -------------------------

MODEL_RELEASE_TYPES = ("patch", "minor", "major", "experimental", "internal")
MODEL_RELEASE_REQUEST_STATUSES = (
    "draft", "awaiting_review", "validating", "validated", "validation_failed", "approved",
    "canary", "canary_failed", "activating", "activated", "activation_failed", "rejected",
    "cancelled", "expired", "superseded",
)
MODEL_RELEASE_APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired", "superseded")
MODEL_ACTIVATION_EVENT_TYPES = (
    "pre_activation_snapshot", "canary_started", "canary_passed", "canary_failed",
    "activated", "activation_failed", "rolled_back",
)
POST_ACTIVATION_CHECK_STATUSES = ("passed", "passed_with_warning", "failed", "not_applicable")

# -- rollback (shared by both tracks) ---------------------------------------------------

ROLLBACK_TARGET_TYPES = ("rag", "model")
ROLLBACK_PLAN_STATUSES = ("draft", "verified", "used", "failed", "superseded")
ROLLBACK_EVENT_TYPES = ("validated", "executed", "execution_failed", "verified_recovered")

# -- artifact security / backup / deployment readiness ----------------------------------

ARTIFACT_TYPES = (
    "checkpoint", "tokenizer", "rag_index", "dataset_manifest", "training_manifest",
    "release_manifest", "backup", "configuration",
)
READINESS_CHECK_STATUSES = (
    "passed", "passed_with_warning", "failed", "not_configured", "not_applicable",
)
BACKUP_CHECK_TYPES = ("backup", "restore")
DEPLOYMENT_READINESS_RESULTS = ("ready", "ready_with_conditions", "not_ready", "blocked")

# -- regression --------------------------------------------------------------------------

REGRESSION_RUN_STATUSES = (
    "in_progress", "completed", "completed_with_failures", "environment_incomplete",
)
REGRESSION_RESULT_STATUSES = ("passed", "failed", "environment_incomplete")

# -- final report / acceptance -----------------------------------------------------------

READINESS_RECOMMENDATIONS = (
    "ready_for_text_nlp_production", "ready_with_conditions", "not_ready", "blocked",
)
ACCEPTANCE_DECISIONS = ("accepted", "accepted_with_conditions", "rejected", "needs_remediation")

# -- resource/concurrency bounds (Step 34) ------------------------------------------------

DEFAULT_ACTIVATION_TIMEOUT_SECONDS = 600
DEFAULT_ROLLBACK_TIMEOUT_SECONDS = 300
DEFAULT_MAX_CANARY_DURATION_SECONDS = 1800
DEFAULT_MAX_VALIDATION_QUERIES = 50
DEFAULT_MAX_SMOKE_TEST_TOKENS = 256
DEFAULT_MAX_TEMPORARY_CANDIDATE_STORAGE_BYTES = 2_000_000_000
DEFAULT_MINIMUM_FREE_DISK_RESERVE_BYTES = 2_000_000_000

__all__ = [
    "RAG_PROMOTION_REQUEST_STATUSES", "RAG_PROMOTION_APPROVAL_STATUSES",
    "RAG_RELEASE_CANDIDATE_STATUSES", "RAG_VALIDATION_RESULT_STATUSES",
    "RAG_ACTIVATION_EVENT_TYPES", "COMMERCIAL_USE_CONTEXTS",
    "MODEL_RELEASE_TYPES", "MODEL_RELEASE_REQUEST_STATUSES",
    "MODEL_RELEASE_APPROVAL_STATUSES", "MODEL_ACTIVATION_EVENT_TYPES",
    "POST_ACTIVATION_CHECK_STATUSES",
    "ROLLBACK_TARGET_TYPES", "ROLLBACK_PLAN_STATUSES", "ROLLBACK_EVENT_TYPES",
    "ARTIFACT_TYPES", "READINESS_CHECK_STATUSES", "BACKUP_CHECK_TYPES",
    "DEPLOYMENT_READINESS_RESULTS",
    "REGRESSION_RUN_STATUSES", "REGRESSION_RESULT_STATUSES",
    "READINESS_RECOMMENDATIONS", "ACCEPTANCE_DECISIONS",
    "DEFAULT_ACTIVATION_TIMEOUT_SECONDS", "DEFAULT_ROLLBACK_TIMEOUT_SECONDS",
    "DEFAULT_MAX_CANARY_DURATION_SECONDS", "DEFAULT_MAX_VALIDATION_QUERIES",
    "DEFAULT_MAX_SMOKE_TEST_TOKENS", "DEFAULT_MAX_TEMPORARY_CANDIDATE_STORAGE_BYTES",
    "DEFAULT_MINIMUM_FREE_DISK_RESERVE_BYTES",
]
