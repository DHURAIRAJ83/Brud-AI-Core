"""Phase 14: pure enums, bounds, and status rules for Training Dataset
Promotion, Incremental Language Training, Checkpoint Evaluation &
Admin Approval.

Nothing in this package (or anything it describes) activates
production inference, releases a model, or sets
`core_model_versions.lifecycle_status='active'`. RAG sandbox accepted
never implies training data approved; training data approved never
implies training run approved; training run approved never implies
checkpoint accepted; checkpoint accepted never implies model released;
model candidate registered never implies production model activated.
See docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

# -- training data assessment (Step 3) -----------------------------------------

SUITABILITY_DIMENSIONS = (
    "licence_training_permission", "commercial_condition_compatibility",
    "source_verification_current", "rag_sandbox_acceptance", "record_review_status",
    "language_quality", "instruction_quality", "task_fit", "factuality_risk",
    "knowledge_volatility", "duplicate_risk", "evaluation_contamination", "privacy_risk",
    "safety_risk", "prompt_injection_risk", "format_suitability", "tokenizer_compatibility",
    "replay_requirement", "resource_feasibility",
)

SUITABILITY_STATUSES = (
    "not_assessed", "potentially_suitable", "suitable_with_transformation",
    "suitable_for_sft", "suitable_for_pretraining", "suitable_for_tokenizer",
    "evaluation_only", "rag_only", "not_suitable", "blocked",
)
# Statuses that may legally proceed to dataset promotion. Automated
# assessment reaching one of these never grants approval by itself --
# see ASSESSMENT_STATUSES below for the assessment lifecycle, and the
# service layer's own explicit, separate approval gates.
PROMOTABLE_SUITABILITY_STATUSES = (
    "suitable_with_transformation", "suitable_for_sft", "suitable_for_pretraining",
    "suitable_for_tokenizer",
)

ASSESSMENT_STATUSES = ("not_assessed", "assessing", "assessed", "failed")
ASSESSMENT_STAGES = (
    "lineage_check", "permission_check", "classification", "contamination_check",
    "candidate_review", "replay_plan", "dataset_promotion", "complete",
)

# -- language-vs-factual record classification (Step 4) -------------------------

RECORD_CATEGORIES = (
    "language_pattern", "grammar", "conversation", "instruction_response", "translation_pair",
    "summarization_pair", "correction_pair", "classification_example", "reasoning_example",
    "general_text_corpus", "stable_knowledge", "volatile_knowledge", "source_specific_fact",
    "evaluation_example", "unsafe_or_blocked",
)

# Deliberately explicit routing table (Step 4) -- never inferred implicitly.
# Maps a record category to the training-relevant outcome it may route to.
SFT_CANDIDATE_CATEGORIES = (
    "instruction_response", "translation_pair", "summarization_pair", "correction_pair",
    "classification_example", "reasoning_example",
)
PRETRAINING_OR_TOKENIZER_CANDIDATE_CATEGORIES = (
    "language_pattern", "grammar", "conversation", "general_text_corpus",
)
RAG_ONLY_CATEGORIES = ("stable_knowledge", "volatile_knowledge", "source_specific_fact")
EVALUATION_ONLY_CATEGORIES = ("evaluation_example",)
BLOCKED_CATEGORIES = ("unsafe_or_blocked",)

# -- transformation model (Step 5) ------------------------------------------------

TRANSFORMATION_TYPES = (
    "clean_language_sample", "question_answer_pair", "summary_pair", "translation_pair",
    "tanglish_normalization_pair", "correction_pair", "instruction_response_pair",
    "conversation_turn_sequence",
)
CANDIDATE_REVIEW_STATUSES = ("pending_review", "approved", "rejected", "needs_revision")

# -- contamination recheck (Step 6) ------------------------------------------------

CONTAMINATION_RESULTS = ("clear", "possible_overlap", "confirmed_overlap", "unknown")
BLOCKING_CONTAMINATION_RESULTS = ("confirmed_overlap",)

# -- dataset promotion (Steps 7-9) --------------------------------------------------

PROMOTION_REQUEST_STATUSES = (
    "draft", "awaiting_approval", "approved", "rejected", "expired", "superseded",
    "building", "ready", "failed",
)

# -- training run (Steps 11-15) -----------------------------------------------------

TRAINING_STRATEGIES = (
    "incremental_sft", "continued_pretraining", "tokenizer_only_assessment",
    "no_training_rag_only",
)
# Strategies that create a real underlying instruction_tuning_experiment/pretraining_job.
EXECUTABLE_TRAINING_STRATEGIES = ("incremental_sft", "continued_pretraining")

EXECUTION_TARGETS = ("local_cpu", "cpu_vps", "external_gpu_manual")

RUN_REQUEST_STATUSES = (
    "draft", "awaiting_approval", "approved", "rejected", "expired", "superseded", "started",
    "cancelled",
)
RUN_APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired", "superseded")
RUN_STATUSES = (
    "queued", "running", "completed", "completed_with_warnings", "failed", "cancelled",
)
UNDERLYING_RUN_KINDS = ("instruction_tuning_run", "pretraining_job")

# -- checkpoint lineage (Step 16) -----------------------------------------------------

CHECKPOINT_STATUSES = (
    "created", "verified", "evaluation_pending", "evaluated", "accepted_candidate",
    "rejected", "corrupt", "superseded",
)

# -- evaluation / forgetting / memorization / comparison (Steps 18-21) ----------------

EVALUATION_TYPES = (
    "training_loss", "validation_loss", "test_loss", "perplexity", "instruction_following",
    "tamil_language_quality", "english_language_quality", "tanglish_language_quality",
    "mixed_language_quality", "relevance", "groundedness", "unsupported_claim_risk", "safety",
    "refusal_behavior", "degeneration", "repetition", "memorization", "data_leakage",
    "tokenizer_round_trip",
)

REGRESSION_RESULTS = (
    "improved", "unchanged", "minor_regression", "major_regression", "not_comparable",
)
BLOCKING_REGRESSION_RESULTS = ("major_regression",)

MEMORIZATION_RISK_LEVELS = ("low_risk", "warning", "high_risk", "blocked")
BLOCKING_MEMORIZATION_RISK_LEVELS = ("blocked",)

COMPARISON_TYPES = ("general_comparison", "forgetting_check")
FORGETTING_BASELINE_DIMENSIONS = (
    "tamil_baseline", "english_baseline", "tanglish_baseline", "mixed_language_baseline",
    "instruction_following", "safety", "general_chat", "existing_domain_tasks",
    "previous_accepted_capabilities",
)

# -- human review (Step 22) ----------------------------------------------------------

HUMAN_REVIEW_DECISIONS = ("pass", "pass_with_conditions", "fail", "needs_more_testing")
HUMAN_REVIEW_DIMENSIONS = (
    "tamil_fluency", "english_fluency", "tanglish_readability", "instruction_following",
    "helpfulness", "correct_refusal", "hallucination_risk", "repetition", "formatting",
    "regression",
)

# -- report advisory fields (Step 23) -------------------------------------------------

CHECKPOINT_RECOMMENDATIONS = (
    "accept_candidate", "accept_with_conditions", "reject", "needs_more_training",
    "needs_more_evaluation",
)
PRODUCTION_RELEASE_READINESS_VALUES = (
    "not_assessed", "potentially_ready", "ready_with_conditions", "not_ready", "blocked",
)

# -- checkpoint acceptance (Step 24) --------------------------------------------------

CHECKPOINT_ACCEPTANCE_DECISIONS = (
    "accepted_candidate", "accepted_with_conditions", "rejected", "needs_more_testing",
)

# -- model registry handoff (Step 25) -------------------------------------------------

# The one, single lifecycle_status value any Phase 14 code path may ever
# write to core_model_versions. Never "active" -- production activation
# is a separate, later, out-of-scope mechanism this phase never touches.
MODEL_CANDIDATE_LIFECYCLE_STATUS = "staging"
PROHIBITED_MODEL_LIFECYCLE_STATUSES = ("active",)

# -- resource bounds (Step 36, defaults only -- Settings fields are authoritative) ----

DEFAULT_MAX_RECORDS = 2_000
DEFAULT_MAX_TOKENS = 2_000_000
DEFAULT_MAX_CONTEXT_LENGTH = 1024
DEFAULT_MAX_EPOCHS = 5
DEFAULT_MAX_STEPS = 20_000
DEFAULT_MAX_CHECKPOINT_COUNT = 20
DEFAULT_MINIMUM_FREE_DISK_BYTES = 2_000_000_000
DEFAULT_MAX_CONCURRENT_RUNS = 1

__all__ = [
    "SUITABILITY_DIMENSIONS", "SUITABILITY_STATUSES", "PROMOTABLE_SUITABILITY_STATUSES",
    "ASSESSMENT_STATUSES", "ASSESSMENT_STAGES", "RECORD_CATEGORIES",
    "SFT_CANDIDATE_CATEGORIES", "PRETRAINING_OR_TOKENIZER_CANDIDATE_CATEGORIES",
    "RAG_ONLY_CATEGORIES", "EVALUATION_ONLY_CATEGORIES", "BLOCKED_CATEGORIES",
    "TRANSFORMATION_TYPES", "CANDIDATE_REVIEW_STATUSES", "CONTAMINATION_RESULTS",
    "BLOCKING_CONTAMINATION_RESULTS", "PROMOTION_REQUEST_STATUSES", "TRAINING_STRATEGIES",
    "EXECUTABLE_TRAINING_STRATEGIES", "EXECUTION_TARGETS", "RUN_REQUEST_STATUSES",
    "RUN_APPROVAL_STATUSES", "RUN_STATUSES", "UNDERLYING_RUN_KINDS", "CHECKPOINT_STATUSES",
    "EVALUATION_TYPES", "REGRESSION_RESULTS", "BLOCKING_REGRESSION_RESULTS",
    "MEMORIZATION_RISK_LEVELS", "BLOCKING_MEMORIZATION_RISK_LEVELS", "COMPARISON_TYPES",
    "FORGETTING_BASELINE_DIMENSIONS", "HUMAN_REVIEW_DECISIONS", "HUMAN_REVIEW_DIMENSIONS",
    "CHECKPOINT_RECOMMENDATIONS", "PRODUCTION_RELEASE_READINESS_VALUES",
    "CHECKPOINT_ACCEPTANCE_DECISIONS", "MODEL_CANDIDATE_LIFECYCLE_STATUS",
    "PROHIBITED_MODEL_LIFECYCLE_STATUSES", "DEFAULT_MAX_RECORDS", "DEFAULT_MAX_TOKENS",
    "DEFAULT_MAX_CONTEXT_LENGTH", "DEFAULT_MAX_EPOCHS", "DEFAULT_MAX_STEPS",
    "DEFAULT_MAX_CHECKPOINT_COUNT", "DEFAULT_MINIMUM_FREE_DISK_BYTES",
    "DEFAULT_MAX_CONCURRENT_RUNS",
]
