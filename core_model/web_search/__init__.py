"""Phase 20 Trusted Web Search taxonomy. Single source of truth for
every enum the Web-search pipeline uses -- mirrors
`core_model/knowledge_gap/__init__.py`'s own pattern exactly.

Nothing in this package performs a real HTTP request, executes model
inference, or writes to RAG/training tables -- it only classifies,
scores, and describes. Real I/O lives in `backend/services/`.
"""

from __future__ import annotations

POLICY_VERSION = "v1"

# -- Web query category (Step 2) -----------------------------------------------------------------

WEB_QUERY_CATEGORIES = (
    "current_software_documentation",
    "government_service_information",
    "current_rules_and_regulations",
    "current_general_information",
    "official_product_documentation",
)

# -- source trust levels (Step 5) ----------------------------------------------------------------

SOURCE_TRUST_LEVELS = (
    "official",
    "authoritative",
    "reputable_secondary",
    "community",
    "unknown",
    "blocked",
)

# -- verification levels (Step 11) ---------------------------------------------------------------

VERIFICATION_LEVELS = (
    "search_result_only",
    "domain_verified",
    "page_fetched",
    "content_verified",
    "cross_source_verified",
    "official_source_verified",
)

# -- freshness result (Step 10) ------------------------------------------------------------------

FRESHNESS_RESULTS = (
    "fresh",
    "possibly_stale",
    "stale",
    "undated",
    "conflicting",
)

# -- source-conflict status (Step 13) ------------------------------------------------------------

CONFLICT_STATUSES = (
    "no_conflict",
    "minor_difference",
    "material_conflict",
    "date_version_conflict",
    "unresolved_conflict",
)

# -- evidence support type (Step 12) -------------------------------------------------------------

SUPPORT_TYPES = (
    "directly_supports",
    "partially_supports",
    "background_context",
    "contradicts",
)

# -- injection status (Step 9, reused shape from core_model.rag.injection_filter) ----------------

WEB_INJECTION_CATEGORIES = (
    "override_system_instructions",
    "request_secret_disclosure",
    "request_tool_execution",
    "redirect_model",
    "claim_false_authority",
    "insert_hidden_instructions",
    "manipulate_citations",
)

# -- stable public error codes (Step 35) ----------------------------------------------------------

WEB_TOOL_ERROR_CODES = (
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

__all__ = [
    "CONFLICT_STATUSES",
    "FRESHNESS_RESULTS",
    "POLICY_VERSION",
    "SOURCE_TRUST_LEVELS",
    "SUPPORT_TYPES",
    "VERIFICATION_LEVELS",
    "WEB_INJECTION_CATEGORIES",
    "WEB_QUERY_CATEGORIES",
    "WEB_TOOL_ERROR_CODES",
]
