"""Phase 10 live dataset discovery -- pure enums, bounds, and predicates.

Read-only, comparison-only: nothing in this package (or anything it
describes) ever downloads a file, imports a dataset, approves a
licence, or activates RAG/training. See
``docs/data_discovery/phase10_live_dataset_discovery_plan.md``.

``languages`` here is a deliberately different vocabulary from
``core_model.rag.language_routing``'s short detection codes (``ta, en,
tgl, mixed, unknown``) -- that module detects the language of one chat
message; this one describes a dataset requirement/candidate's
(possibly multiple) declared languages using the task's own full-word
vocabulary. ``LANGUAGE_CATEGORY_TO_REQUIREMENT_LANGUAGE`` is the one
explicit bridge between them, used only when the Assistant infers a
requirement's language from an admin's message.
"""

from __future__ import annotations

from core_model.data_providers import is_usable_for_discovery

MODALITIES = ("text", "image", "audio", "video", "multimodal")

# Per the task's own current-implementation expectation: only "text" has
# real search+normalization support in this phase; the rest are
# discoverable-metadata-only (a connector may still return a result, but
# no modality-specific validation exists for them, and callers must
# never claim otherwise).
FULLY_SUPPORTED_MODALITIES = ("text",)
METADATA_ONLY_MODALITIES = ("image", "audio", "video", "multimodal")

LANGUAGES = ("tamil", "english", "tanglish", "mixed", "other", "unknown")

LANGUAGE_CATEGORY_TO_REQUIREMENT_LANGUAGE = {
    "ta": "tamil",
    "en": "english",
    "tgl": "tanglish",
    "mixed": "mixed",
    "unknown": "unknown",
}

TASKS = (
    "chat", "language_modeling", "instruction_tuning", "question_answering",
    "translation", "summarization", "classification", "ocr", "asr", "tts",
    "vision", "object_detection", "image_classification", "video_understanding",
    "multimodal_alignment", "evaluation", "other",
)

INTENDED_USES = (
    "rag", "training", "evaluation", "tokenizer", "research",
    "commercial_product", "internal_testing",
)

COMMERCIAL_REQUIREMENTS = ("required", "preferred", "not_required", "unknown")

# Whether a requirement field's value came from the admin explicitly, was
# inferred by the assistant (and must be disclosed as an inference, never
# presented as a stated fact), or is materially missing.
FIELD_SOURCES = ("admin_explicit", "assistant_inferred", "unknown")

SEARCH_SESSION_STATUSES = (
    "draft", "ready", "running", "partial", "completed", "failed",
    "cancelled", "expired",
)
ACTIVE_SESSION_STATUSES = ("draft", "ready", "running")
TERMINAL_SESSION_STATUSES = ("completed", "failed", "cancelled", "expired")

# Per-provider run outcome (Step 11) -- one failed/timed-out provider run
# must never discard another provider's successful results.
PROVIDER_RUN_STATUSES = (
    "success", "partial", "authentication_required", "rate_limited",
    "timeout", "unsupported", "failed",
)
PROVIDER_RUN_FAILURE_STATUSES = (
    "authentication_required", "rate_limited", "timeout", "unsupported", "failed",
)

LICENCE_STATUSES = ("unknown", "declared", "missing", "conflicting", "needs_verification")

RECOMMENDATION_STATUSES = (
    "recommended_for_review", "possible", "low_fit", "high_risk",
    "insufficient_metadata", "excluded",
)

FRESHNESS_STATUSES = ("fresh", "aging", "stale", "unknown")

# `commercial_use_status`/`training_use_status`/`rag_use_status`/
# `evaluation_use_status` never contain a real "approved" value in this
# phase -- there is no verification or approval action anywhere in
# Phase 10's execution logic, so "approved" is structurally unreachable
# rather than merely undocumented.
USE_APPROVAL_STATUSES = ("not_approved", "unknown")

CANDIDATE_ENTRY_METHODS = ("provider_search", "manual")

POSSIBLE_DUPLICATE_STATUS = "possible_duplicate_group"

SEARCH_EVENT_TYPES = (
    "session_created",
    "requirements_updated",
    "requirements_confirmed",
    "search_started",
    "provider_run_completed",
    "provider_run_failed",
    "search_completed",
    "search_partial",
    "search_failed",
    "search_cancelled",
    "candidate_excluded",
    "candidate_restored",
    "manual_candidate_added",
    "comparison_created",
    "report_finalized",
)

# -- bounded execution (Step 11) --------------------------------------------

MAX_PROVIDERS_PER_SEARCH = 8
MAX_RESULTS_PER_PROVIDER = 20
MAX_CANDIDATES_PER_SESSION = 100
PER_PROVIDER_TIMEOUT_SECONDS = 5.0
OVERALL_SEARCH_DEADLINE_SECONDS = 30.0
MAX_RAW_METADATA_BYTES = 32_768
MAX_RETRIES_PER_PROVIDER = 0
MAX_QUERY_LENGTH = 300

# -- scoring (Step 8) ---------------------------------------------------------

SCORING_DIMENSIONS = (
    "requirement_fit", "language_fit", "task_fit", "modality_fit",
    "intended_use_fit", "metadata_completeness", "provider_trust",
    "dataset_card_presence", "version_traceability", "size_suitability",
    "format_suitability", "recency", "accessibility",
)
PENALTY_DIMENSIONS = (
    "risk_penalty", "unknown_licence_penalty", "gated_access_penalty", "conflict_penalty",
)
ALL_SCORING_DIMENSIONS = SCORING_DIMENSIONS + PENALTY_DIMENSIONS

DEFAULT_SCORING_WEIGHTS: dict[str, float] = {
    "requirement_fit": 1.5,
    "language_fit": 1.5,
    "task_fit": 1.25,
    "modality_fit": 1.0,
    "intended_use_fit": 1.0,
    "metadata_completeness": 0.75,
    "provider_trust": 0.75,
    "dataset_card_presence": 0.5,
    "version_traceability": 0.5,
    "size_suitability": 0.5,
    "format_suitability": 0.5,
    "recency": 0.25,
    "accessibility": 0.25,
    "risk_penalty": -1.0,
    "unknown_licence_penalty": -0.75,
    "gated_access_penalty": -0.5,
    "conflict_penalty": -0.5,
}


def is_provider_searchable(
    *,
    enabled: bool,
    lifecycle_status: str,
    has_search_capability: bool,
    has_manual_discovery_capability: bool,
) -> bool:
    """The exact non-negotiable predicate: enabled AND lifecycle permits
    discovery AND (search_datasets OR manual_discovery capability). A
    ``blocked``/``restricted``/``disabled``/``draft``/``archived``
    provider is excluded by ``is_usable_for_discovery`` alone; this adds
    the capability requirement on top."""

    if not is_usable_for_discovery(lifecycle_status=lifecycle_status, enabled=enabled):
        return False
    return has_search_capability or has_manual_discovery_capability


def requirement_language_from_category(language_category: str) -> str:
    """Bridges Phase 16's short detection code to this phase's
    full-word requirement language vocabulary. Unknown/unmapped codes
    become the honest ``"unknown"`` rather than a guess."""

    return LANGUAGE_CATEGORY_TO_REQUIREMENT_LANGUAGE.get(language_category, "unknown")
