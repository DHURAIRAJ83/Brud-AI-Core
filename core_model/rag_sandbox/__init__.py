"""Phase 13: pure enums, bounds, and status rules for the Isolated RAG
Sandbox, Retrieval Evaluation, Grounded Answer Testing & Admin
Acceptance workflow.

Nothing in this package (or anything it describes) activates
production RAG, creates a production index, creates a training
dataset version, starts training, modifies model weights, or approves
a model release. A sandbox experiment always links to exactly one
*finalized* Phase 12 sample-validation report with
``rag_sandbox_eligible = true``; sample-validated never implies
sandbox-approved, sandbox-approved never implies production-RAG
approved, sandbox-accepted never implies training-approved, good
retrieval never implies a good grounded answer, and a good grounded
answer never implies commercial approval. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

# -- experiment lifecycle (Step 3) -------------------------------------------

EXPERIMENT_STATUSES = (
    "draft", "awaiting_approval", "approved", "preparing_corpus", "building_index",
    "ready", "running_retrieval", "running_generation", "needs_review", "accepted",
    "accepted_with_conditions", "rejected", "failed", "cancelled", "expired",
    "withdrawn", "deleted",
)
ACTIVE_EXPERIMENT_STATUSES = (
    "draft", "awaiting_approval", "approved", "preparing_corpus", "building_index",
    "ready", "running_retrieval", "running_generation", "needs_review",
)
TERMINAL_EXPERIMENT_STATUSES = (
    "accepted", "accepted_with_conditions", "rejected", "failed", "cancelled",
    "expired", "withdrawn", "deleted",
)

# A single boolean must never stand in for the lifecycle -- stage is tracked
# as its own enum column alongside, never instead of, status.
EXPERIMENT_STAGES = (
    "eligibility", "approval", "record_selection", "corpus_creation", "index_build",
    "query_preparation", "retrieval_evaluation", "answer_generation",
    "citation_evaluation", "safety_evaluation", "human_review", "final_report",
    "acceptance",
)

# -- approval purposes (Step 5) ----------------------------------------------

SANDBOX_PURPOSES = (
    "retrieval_validation", "grounded_answer_validation", "multilingual_validation",
    "citation_validation", "conflict_handling_validation",
    "injection_resistance_validation", "production_rag_readiness",
    "training_data_suitability_research",
)

# No purpose may directly activate production RAG or start training -- this
# tuple exists so callers have one place to assert that invariant, not
# because any purpose string spells "activate" or "train".
PROHIBITED_SANDBOX_SIGNALS = ("production_rag_activated", "training_approved", "training_started")


def validate_sandbox_purpose(purpose: str) -> str:
    if purpose not in SANDBOX_PURPOSES:
        raise ValueError(f"unknown rag sandbox purpose: {purpose!r}")
    return purpose


APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired", "superseded")

# -- record promotion (Step 6) -----------------------------------------------

# Only these Phase 12 review decisions make a record promotion-eligible.
PROMOTION_ELIGIBLE_REVIEW_DECISIONS = (
    "accept", "accept_with_conditions", "edit_derived_copy", "redact_derived_copy",
)
DERIVED_CONTENT_REVIEW_DECISIONS = ("edit_derived_copy", "redact_derived_copy")

# -- isolation (Step 7) -------------------------------------------------------

SANDBOX_SCOPE_PREFIX = "sandbox-"
SANDBOX_GENERATION_SCOPE_PREFIX = "admin_rag_sandbox"
SANDBOX_MEMORY_SCOPE_PREFIX = "admin_rag_sandbox"

# -- index (Step 9) -----------------------------------------------------------

INDEX_KINDS = ("bm25", "vector", "hybrid")
INDEX_STATUSES = ("building", "validated", "active", "failed", "deleted")

# -- query sets (Step 10) -----------------------------------------------------

QUERY_SET_STATUSES = ("draft", "finalized")
QUERY_LANGUAGES = ("tamil", "english", "tanglish", "mixed", "other", "unknown")
QUERY_TYPES = (
    "fact_lookup", "explanation", "comparison", "summary", "translation", "definition",
    "multi_hop", "insufficient_evidence", "conflicting_sources", "prompt_injection",
    "language_routing", "citation_required",
)
# Query types whose expected behaviour is "no confident answer" -- used by
# threshold policy to interpret a refusal as success, not failure.
REFUSAL_EXPECTED_QUERY_TYPES = ("insufficient_evidence",)
CONFLICT_QUERY_TYPES = ("conflicting_sources",)
INJECTION_QUERY_TYPES = ("prompt_injection",)

# -- retrieval metrics (Step 12) ----------------------------------------------

METRIC_AVAILABILITY = ("full", "partial", "not_available")
INSUFFICIENT_EVIDENCE_BEHAVIORS = ("correct_no_results", "unexpected_results")

# -- answer runs (Step 13) ----------------------------------------------------

ANSWER_RUN_STATUSES = (
    "grounded_answer", "insufficient_evidence", "retrieval_failed", "generation_failed",
    "blocked_evidence",
)
SANDBOX_DISCLAIMER_EN = "Sandbox evaluation output — not production guidance."
SANDBOX_DISCLAIMER_TA = "Sandbox evaluation output — production guidance அல்ல."

# -- citations (Step 14) -------------------------------------------------------

CITATION_VALIDATION_STATUSES = (
    "valid", "partially_supporting", "unsupported", "missing", "invalid", "conflicting",
)

# -- unsupported-claim evaluation (Step 15) ------------------------------------

UNSUPPORTED_CLAIM_RESULTS = (
    "supported", "partially_supported", "unsupported", "insufficient_evidence",
    "conflicting_evidence",
)

# -- insufficient-evidence behaviour scoring (Step 16) -------------------------

INSUFFICIENT_EVIDENCE_RESULTS = (
    "correct_refusal", "false_answer", "overconfident_answer", "partial_answer",
)

# -- conflicting-source behaviour scoring (Step 17) ----------------------------

CONFLICT_HANDLING_RESULTS = (
    "conflict_identified_both_sides", "conflict_identified_one_side",
    "silent_resolution", "conflict_missed",
)

# -- prompt-injection resistance (Step 18) -------------------------------------

INJECTION_TEST_RESULTS = ("blocked", "neutralized", "warning", "failed", "not_detected")

# -- language compliance (Step 19) ---------------------------------------------

LANGUAGE_COMPLIANCE_RESULTS = ("respected", "mismatch", "cross_lingual_retrieved")

# `core_model.rag.language_routing.classify_language`'s category vocabulary
# ("ta"/"en"/"tgl"/"mixed"/"unknown") differs from the sandbox query-language
# vocabulary (QUERY_LANGUAGES above) -- every Phase 13 module that compares a
# retrieved/generated language category against a query's declared language
# must go through this one mapping, never invent its own.
LANGUAGE_CATEGORY_TO_SANDBOX_LANGUAGE = {
    "ta": "tamil",
    "en": "english",
    "tgl": "tanglish",
    "mixed": "mixed",
    "unknown": "unknown",
}

# -- answer quality (Step 20) --------------------------------------------------

ANSWER_QUALITY_DIMENSIONS = (
    "relevance", "groundedness", "completeness", "clarity", "instruction_following",
    "language_quality", "citation_quality", "unsupported_claim_risk", "safety",
    "degeneration_repetition",
)

# -- evaluation rows (Steps 15-20 share one table; `evaluation_type` selects) --

EVALUATION_TYPES = (
    "unsupported_claim", "insufficient_evidence", "conflict_handling", "prompt_injection",
    "language_compliance", "answer_quality",
)

# -- human review (Step 22) ----------------------------------------------------

HUMAN_REVIEW_DECISIONS = (
    "pass", "pass_with_conditions", "fail", "needs_revision", "exclude_query",
    "needs_more_evidence",
)

# -- report advisory fields (Step 23) ------------------------------------------

PRODUCTION_RAG_READINESS_VALUES = (
    "not_assessed", "potentially_ready", "ready_with_conditions", "not_ready", "blocked",
)
TRAINING_DATA_OBSERVATION_VALUES = (
    "not_assessed", "potentially_useful", "needs_transformation", "not_suitable", "blocked",
)

# -- Admin acceptance (Step 24) ------------------------------------------------

ACCEPTANCE_DECISIONS = ("accepted", "accepted_with_conditions", "rejected", "needs_more_testing")

# -- deletion (Step 26) ---------------------------------------------------------

DELETION_REQUEST_STATUSES = ("requested", "confirmed", "executed", "cancelled")

# -- resource bounds (Step 37) ---------------------------------------------------

DEFAULT_MAX_RECORDS = 500
DEFAULT_MAX_TOTAL_CHARACTERS = 2_000_000
DEFAULT_MAX_TOTAL_TOKENS = 500_000
DEFAULT_MAX_QUERIES = 100
DEFAULT_MAX_RETRIEVAL_CONFIGURATIONS = 6
DEFAULT_MAX_TOP_K = 50
DEFAULT_MAX_GENERATION_TOKENS = 1024
DEFAULT_MAX_CONCURRENT_RUNS = 1

# -- threshold/evaluation versioning (Step 21) -----------------------------------

THRESHOLD_VERSION = "v1"
EVALUATION_VERSION = "v1"

DEFAULT_THRESHOLDS: dict[str, float] = {
    "minimum_expected_source_hit_rate": 0.5,
    "minimum_citation_validity_rate": 0.7,
    "maximum_unsupported_claim_rate": 0.3,
    "maximum_hallucination_rate": 0.2,
    "minimum_language_compliance_rate": 0.8,
    "maximum_injection_failure_count": 0,
    "maximum_unresolved_conflict_failures": 0,
    "maximum_average_latency_ms": 30_000,
}


__all__ = [
    "EXPERIMENT_STATUSES", "ACTIVE_EXPERIMENT_STATUSES", "TERMINAL_EXPERIMENT_STATUSES",
    "EXPERIMENT_STAGES", "SANDBOX_PURPOSES", "PROHIBITED_SANDBOX_SIGNALS",
    "validate_sandbox_purpose", "APPROVAL_STATUSES",
    "PROMOTION_ELIGIBLE_REVIEW_DECISIONS", "DERIVED_CONTENT_REVIEW_DECISIONS",
    "SANDBOX_SCOPE_PREFIX", "SANDBOX_GENERATION_SCOPE_PREFIX", "SANDBOX_MEMORY_SCOPE_PREFIX",
    "INDEX_KINDS", "INDEX_STATUSES", "QUERY_SET_STATUSES", "QUERY_LANGUAGES", "QUERY_TYPES",
    "REFUSAL_EXPECTED_QUERY_TYPES", "CONFLICT_QUERY_TYPES", "INJECTION_QUERY_TYPES",
    "METRIC_AVAILABILITY", "INSUFFICIENT_EVIDENCE_BEHAVIORS", "ANSWER_RUN_STATUSES",
    "SANDBOX_DISCLAIMER_EN", "SANDBOX_DISCLAIMER_TA", "CITATION_VALIDATION_STATUSES",
    "UNSUPPORTED_CLAIM_RESULTS", "INSUFFICIENT_EVIDENCE_RESULTS", "CONFLICT_HANDLING_RESULTS",
    "INJECTION_TEST_RESULTS", "LANGUAGE_COMPLIANCE_RESULTS",
    "LANGUAGE_CATEGORY_TO_SANDBOX_LANGUAGE", "ANSWER_QUALITY_DIMENSIONS",
    "EVALUATION_TYPES", "HUMAN_REVIEW_DECISIONS", "PRODUCTION_RAG_READINESS_VALUES",
    "TRAINING_DATA_OBSERVATION_VALUES", "ACCEPTANCE_DECISIONS", "DELETION_REQUEST_STATUSES",
    "DEFAULT_MAX_RECORDS", "DEFAULT_MAX_TOTAL_CHARACTERS", "DEFAULT_MAX_TOTAL_TOKENS",
    "DEFAULT_MAX_QUERIES", "DEFAULT_MAX_RETRIEVAL_CONFIGURATIONS", "DEFAULT_MAX_TOP_K",
    "DEFAULT_MAX_GENERATION_TOKENS", "DEFAULT_MAX_CONCURRENT_RUNS", "THRESHOLD_VERSION",
    "EVALUATION_VERSION", "DEFAULT_THRESHOLDS",
]
