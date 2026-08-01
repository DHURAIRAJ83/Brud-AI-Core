"""Phase 20 Deterministic Tool Gateway + MCP-ready contract taxonomy.
Mirrors `core_model/web_search/__init__.py`'s own pattern.

Nothing in this package executes a tool -- it only classifies,
describes, and bounds. Real execution lives in `backend/services/`.
"""

from __future__ import annotations

POLICY_VERSION = "v1"

# -- built-in Phase 20 tool names (Step 2 minimum scope) ------------------------------------------

TOOL_NAMES = (
    "calculator",
    "unit_conversion",
    "date_time_arithmetic",
)

# -- tool source (Step 23) -------------------------------------------------------------------------

TOOL_SOURCES = (
    "built_in_deterministic",
    "internal_service",
    "external_mcp",
)

# -- tool permission tier (Step 24) ----------------------------------------------------------------

TOOL_PERMISSIONS = (
    "public_safe_deterministic",
    "admin_read_only",
    "disabled",
)

# -- tool risk level -------------------------------------------------------------------------------

TOOL_RISK_LEVELS = ("low", "moderate", "high", "critical")

# -- tool execution status -------------------------------------------------------------------------

TOOL_EXECUTION_STATUSES = (
    "success",
    "input_invalid",
    "disabled",
    "unsupported",
    "timeout",
    "execution_failed",
)

# -- unit-conversion categories (Step 19) -----------------------------------------------------

UNIT_CATEGORIES = (
    "length",
    "mass",
    "volume",
    "temperature",
    "time",
    "area",
    "speed",
    "data_size",
)

__all__ = [
    "POLICY_VERSION",
    "TOOL_EXECUTION_STATUSES",
    "TOOL_NAMES",
    "TOOL_PERMISSIONS",
    "TOOL_RISK_LEVELS",
    "TOOL_SOURCES",
    "UNIT_CATEGORIES",
]
