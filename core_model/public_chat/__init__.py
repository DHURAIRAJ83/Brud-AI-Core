"""Phase 18 public Smart Answer Router taxonomy. Single source of truth
for every enum the public chat pipeline uses -- mirrors the
`core_model/knowledge_routing/__init__.py` pattern (Phase 17) exactly.

Nothing in this package executes Model, RAG, or Memory actions --
`pipeline.py` (the orchestrating module) is the only place that calls
into `ChatOrchestrationService`, and only ever for exactly one resolved
route per request.
"""

from __future__ import annotations

POLICY_VERSION = "v1"

# -- executable vs. unavailable routes (Step 2; Phase 20 makes trusted_web/tool conditionally
# executable -- moved out of UNAVAILABLE_ROUTES, which is kept (now empty) for import compat) ---

EXECUTABLE_ROUTES = (
    "core_model", "approved_rag", "memory", "trusted_web", "tool", "clarify", "refuse",
    "insufficient",
)
UNAVAILABLE_ROUTES: tuple[str, ...] = ()
ALL_ROUTES = EXECUTABLE_ROUTES + UNAVAILABLE_ROUTES

# -- route availability status (Step 18) ---------------------------------------------------------

AVAILABILITY_STATUSES = ("executable", "unavailable", "blocked")

# -- evidence status (Step 9) -------------------------------------------------------------------

EVIDENCE_STATUSES = (
    "grounded", "partially_grounded", "insufficient", "conflicting", "model_only", "none",
    # -- Phase 20 Step 21: a deterministic tool result is neither model-generated nor
    # evidence-grounded -- its own distinct status, never conflated with "grounded" -----------
    "deterministic",
)

# -- confidence bands (Step 25) -- never a fabricated percentage --------------------------------

CONFIDENCE_BANDS = ("high", "medium", "low", "unknown")

# -- source types (response metadata) ------------------------------------------------------------

SOURCE_TYPES = ("model", "rag", "memory", "web", "tool")

# -- safety status (Step 6/7) -------------------------------------------------------------------

INPUT_SAFETY_DECISIONS = ("allow", "allow_with_caution", "refuse", "needs_review")
SAFETY_STATUSES = ("safe", "caution", "refused", "output_blocked", "review_flagged")

# -- language categories reused verbatim from core_model.rag.LANGUAGE_CATEGORIES ----------------

PUBLIC_OUTPUT_LANGUAGES = ("ta", "en")  # Tanglish is never a public output language

# -- stable public error codes (Step 23) ---------------------------------------------------------

ERROR_CODES = (
    "CHAT_INPUT_TOO_LARGE",
    "CHAT_RATE_LIMITED",
    "CHAT_MODEL_UNAVAILABLE",
    "CHAT_RAG_UNAVAILABLE",
    "CHAT_RAG_INSUFFICIENT",
    "CHAT_MEMORY_CONSENT_REQUIRED",
    "CHAT_CLARIFICATION_REQUIRED",
    "CHAT_WEB_NOT_AVAILABLE",
    "CHAT_TOOL_NOT_AVAILABLE",
    "CHAT_SAFETY_REFUSAL",
    "CHAT_OUTPUT_BLOCKED",
    "CHAT_INTERNAL_ERROR",
    # -- Phase 20 (Step 35): the route was attempted, not merely unavailable -----------------
    "CHAT_WEB_PROVIDER_UNAVAILABLE",
    "CHAT_WEB_QUOTA_EXCEEDED",
    "CHAT_WEB_NO_TRUSTED_SOURCE",
    "CHAT_WEB_SOURCE_CONFLICT",
    "CHAT_WEB_FETCH_BLOCKED",
    "CHAT_WEB_FETCH_TIMEOUT",
    "CHAT_WEB_EVIDENCE_INSUFFICIENT",
    "CHAT_TOOL_UNSUPPORTED",
    "CHAT_TOOL_INPUT_INVALID",
    "CHAT_TOOL_DISABLED",
    "CHAT_TOOL_TIMEOUT",
    "CHAT_TOOL_EXECUTION_FAILED",
    "CHAT_MCP_DISABLED",
)

# -- fallback reason codes (structured metadata, Step 16/17/18) ---------------------------------
# lowercase snake_case internal reason codes used in `route_reason_codes`; each Phase-20 entry
# below maps 1:1 to one of the new stable `CHAT_*` codes above (see
# docs/smart_routing/phase20_trusted_web_tool_gateway.md for the mapping table).

FALLBACK_REASON_CODES = (
    "trusted_web_unavailable",
    "tool_unavailable",
    "rag_scope_unavailable",
    "rag_insufficient_evidence",
    "model_assignment_unavailable",
    "memory_unavailable",
    "memory_consent_required",
    "classification_failed",
    "output_safety_blocked",
    "input_safety_refused",
    "web_provider_unavailable",
    "web_quota_exceeded",
    "web_no_trusted_source",
    "web_evidence_insufficient",
    "web_fetch_blocked",
    "tool_disabled",
    "tool_unsupported",
    "tool_input_invalid",
    "tool_rate_limited",
    "tool_timeout",
    "tool_execution_failed",
)

# -- feedback categories (Step 28) -- reused verbatim from core_model.feedback.FEEDBACK_TYPES ---

PUBLIC_FEEDBACK_TYPES = ("thumbs_up", "thumbs_down", "language_report", "safety_report")

__all__ = [
    "ALL_ROUTES",
    "AVAILABILITY_STATUSES",
    "CONFIDENCE_BANDS",
    "ERROR_CODES",
    "EVIDENCE_STATUSES",
    "EXECUTABLE_ROUTES",
    "FALLBACK_REASON_CODES",
    "INPUT_SAFETY_DECISIONS",
    "POLICY_VERSION",
    "PUBLIC_FEEDBACK_TYPES",
    "PUBLIC_OUTPUT_LANGUAGES",
    "SAFETY_STATUSES",
    "SOURCE_TYPES",
    "UNAVAILABLE_ROUTES",
]
