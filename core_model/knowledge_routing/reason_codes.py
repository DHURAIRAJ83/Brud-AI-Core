"""Stable reason-code registry (Step 21). Every reason code any
classifier layer emits must be defined here — this is the single
source of truth `GET /admin/knowledge-routing/reason-codes` serves and
every test asserts against.

Codes explicitly named in the task's Step 21 example list are defined
by hand, verbatim, first (`_REQUIRED_REASON_CODES`). Every remaining
taxonomy value (domains, subdomains, intents, freshness, evidence
requirements not already covered by a required code) gets a generated,
mechanically-derived code so the registry always has full coverage —
merged in without ever overriding a hand-written required code.
"""

from __future__ import annotations

from core_model.knowledge_routing import (
    ALL_SUBDOMAINS,
    DOMAINS,
    EVIDENCE_REQUIREMENTS,
    FRESHNESS_VALUES,
    INTENTS,
    SAFETY_REASON_CATEGORIES,
)

# -- required, verbatim from the task's Step 21 example list -----------------------------------

_REQUIRED_REASON_CODES: dict[str, str] = {
    "LANG_TAMIL_DETECTED": "Tamil script present above the detection threshold.",
    "LANG_TANGLISH_DETECTED": "Latin script present with Tanglish lexicon hits.",
    "INTENT_CURRENT_STATUS": "Primary intent classified as 'ask_current_status'.",
    "DOMAIN_TAMIL_GRAMMAR": "Knowledge subdomain classified as 'tamil_grammar'.",
    "DOMAIN_SOFTWARE_DOCUMENTATION": "Knowledge subdomain classified as 'software_documentation'.",
    "FRESHNESS_REAL_TIME": "Freshness classified as 'real_time'.",
    "FRESHNESS_TIME_SENSITIVE": "Freshness classified as 'time_sensitive'.",
    "EVIDENCE_INTERNAL_REQUIRED": (
        "Evidence requirement classified as 'internal_evidence_required'."
    ),
    "EVIDENCE_EXTERNAL_REQUIRED": (
        "Evidence requirement classified as 'external_verified_evidence_required'."
    ),
    "EVIDENCE_TOOL_REQUIRED": "Evidence requirement classified as 'deterministic_tool_required'.",
    "AMBIGUOUS_MISSING_CONTEXT": "The request depends on context that is not available.",
    "SAFETY_LIKELY_DISALLOWED": "A high-risk safety category matched; recommend refusal.",
    "ROUTE_CORE_STABLE_LANGUAGE": (
        "Timeless language/explanation/creative request answerable from the model's own "
        "knowledge."
    ),
    "ROUTE_RAG_APPROVED_INTERNAL": "Request concerns an approved internal document/evidence set.",
    "ROUTE_WEB_CURRENT_INFORMATION": (
        "Request concerns real-time or time-sensitive information the model cannot know "
        "reliably."
    ),
    "ROUTE_TOOL_DETERMINISTIC": (
        "Request is a deterministic calculation/conversion the model should not attempt via "
        "free-text reasoning."
    ),
    "ROUTE_CLARIFY_AMBIGUOUS": "Request is ambiguous; a route cannot be safely chosen yet.",
    "TARGET_CORE_LANGUAGE_SKILL": (
        "Timeless linguistic/reasoning skill worth generalizing into the base model."
    ),
    "TARGET_RAG_STABLE_FACT": (
        "Stable fact suitable for an approved knowledge space, not model weights."
    ),
    "TARGET_WEB_VOLATILE_FACT": "Volatile fact that should never be baked into model weights.",
    "TARGET_TOOL_CALCULATION": "Deterministic-tool result; no learning signal needed.",
    "TARGET_EVALUATION_ONLY": "Session-specific/operational; useful for evaluation only.",
    "TARGET_DO_NOT_LEARN_PERSONAL": (
        "Personal/user-specific content must never become a training signal."
    ),
    "TARGET_BLOCKED_UNSAFE": "Unsafe request; must never become any kind of learning signal.",
    "TAMIL_FIRST_POLICY_VIOLATION": (
        "A Tamil-language request was routed to core_model purely because of its language, "
        "despite requiring current/external evidence."
    ),
}


def _generated(prefix: str, values: tuple[str, ...], describe: str) -> dict[str, str]:
    return {f"{prefix}_{value.upper()}": f"{describe} classified as '{value}'" for value in values}


_LANGUAGE_SUPPLEMENTARY = {
    "LANG_ENGLISH_DETECTED": "Latin script present with no Tanglish lexicon hits.",
    "LANG_MIXED_DETECTED": "Both Tamil and Latin script present above the detection threshold.",
    "LANG_UNKNOWN": "Neither Tamil nor Latin script detected above the threshold.",
}
_INTENT_SUPPLEMENTARY = _generated("INTENT", INTENTS, "Primary intent")
_DOMAIN_SUPPLEMENTARY = {
    **_generated("DOMAIN", DOMAINS, "Knowledge domain"),
    **_generated("DOMAIN", ALL_SUBDOMAINS, "Knowledge subdomain"),
}
_FRESHNESS_SUPPLEMENTARY = _generated("FRESHNESS", FRESHNESS_VALUES, "Freshness/volatility")
_EVIDENCE_SUPPLEMENTARY = _generated("EVIDENCE", EVIDENCE_REQUIREMENTS, "Evidence requirement")
_AMBIGUITY_SUPPLEMENTARY = {
    "AMBIGUOUS_MISSING_SUBJECT": "The request appears to be missing a clear subject.",
    "AMBIGUOUS_MISSING_OBJECT": "The request appears to be missing a clear object/target.",
    "AMBIGUOUS_UNCLEAR_PRONOUN": "A pronoun has no resolvable antecedent.",
    "AMBIGUOUS_UNKNOWN_ACRONYM": "An unrecognized acronym was used without expansion.",
    "AMBIGUOUS_INCOMPLETE_ACTION": "An action verb has no stated target.",
    "AMBIGUOUS_CONFLICTING_INSTRUCTION": "The request contains mutually conflicting instructions.",
    "NOT_AMBIGUOUS_DETERMINISTIC_ROUTE": (
        "A deterministic route is available without clarification."
    ),
}
_SAFETY_SUPPLEMENTARY = {
    **{
        f"SAFETY_{category.upper()}": f"Safety-relevant category matched: {category}."
        for category in SAFETY_REASON_CATEGORIES
    },
    "SAFETY_SAFE": "No safety-risk signal matched.",
    "SAFETY_SENSITIVE_BUT_ALLOWED": (
        "A sensitive but explicitly-allowed category matched (e.g. benign cybersecurity "
        "education, political criticism, legal information)."
    ),
    "SAFETY_REQUIRES_POLICY_REVIEW": "A category matched that a human safety policy should review.",
    "SAFETY_UNKNOWN": "No safety signal could be determined.",
}
_ROUTE_SUPPLEMENTARY = {
    "ROUTE_MEMORY_PERSONAL_CONTEXT": "Request concerns the user's own prior context/preference.",
    "ROUTE_REFUSE_UNSAFE": "Request matched a likely-disallowed safety category.",
    "ROUTE_INSUFFICIENT_NO_EVIDENCE_PATH": "No viable evidence path exists for this request.",
}
_TARGET_SUPPLEMENTARY: dict[str, str] = {
    "TARGET_FUTURE_TRAINING_CANDIDATE": (
        "Stable, generalizable content flagged for a future, separately-approved training cycle "
        "-- not an automatic training approval."
    ),
}
_TAMIL_FIRST_SUPPLEMENTARY = {
    "TAMIL_FIRST_PRIORITY_APPLIED": (
        "Tamil-first policy correctly prioritized core-model language handling for a timeless "
        "Tamil-language request."
    ),
}

REASON_CODE_REGISTRY: dict[str, str] = {
    **_LANGUAGE_SUPPLEMENTARY,
    **_INTENT_SUPPLEMENTARY,
    **_DOMAIN_SUPPLEMENTARY,
    **_FRESHNESS_SUPPLEMENTARY,
    **_EVIDENCE_SUPPLEMENTARY,
    **_AMBIGUITY_SUPPLEMENTARY,
    **_SAFETY_SUPPLEMENTARY,
    **_ROUTE_SUPPLEMENTARY,
    **_TARGET_SUPPLEMENTARY,
    **_TAMIL_FIRST_SUPPLEMENTARY,
    **_REQUIRED_REASON_CODES,  # required codes always win over any generated duplicate
}


def is_known_reason_code(code: str) -> bool:
    return code in REASON_CODE_REGISTRY


# -- value -> reason-code lookup tables ---------------------------------------------------------
#
# Mechanical generation (`_generated`) does not always match the exact
# spelling the task's Step 21 example list requires (e.g. intent value
# 'ask_current_status' must map to reason code 'INTENT_CURRENT_STATUS',
# not the mechanically-generated 'INTENT_ASK_CURRENT_STATUS'). These
# tables start from the mechanical form and apply the small number of
# explicit overrides needed so every classifier can look up a reason
# code by taxonomy value without hand-coding the exception locally.

INTENT_REASON_CODE_BY_VALUE: dict[str, str] = {
    value: f"INTENT_{value.upper()}" for value in INTENTS
}
INTENT_REASON_CODE_BY_VALUE["ask_current_status"] = "INTENT_CURRENT_STATUS"

DOMAIN_REASON_CODE_BY_VALUE: dict[str, str] = {
    value: f"DOMAIN_{value.upper()}" for value in (*DOMAINS, *ALL_SUBDOMAINS)
}

FRESHNESS_REASON_CODE_BY_VALUE: dict[str, str] = {
    value: f"FRESHNESS_{value.upper()}" for value in FRESHNESS_VALUES
}

EVIDENCE_REASON_CODE_BY_VALUE: dict[str, str] = {
    value: f"EVIDENCE_{value.upper()}" for value in EVIDENCE_REQUIREMENTS
}
EVIDENCE_REASON_CODE_BY_VALUE["internal_evidence_required"] = "EVIDENCE_INTERNAL_REQUIRED"
EVIDENCE_REASON_CODE_BY_VALUE["external_verified_evidence_required"] = "EVIDENCE_EXTERNAL_REQUIRED"
EVIDENCE_REASON_CODE_BY_VALUE["deterministic_tool_required"] = "EVIDENCE_TOOL_REQUIRED"

SAFETY_REASON_CODE_BY_VALUE: dict[str, str] = {
    "safe": "SAFETY_SAFE",
    "sensitive_but_allowed": "SAFETY_SENSITIVE_BUT_ALLOWED",
    "requires_policy_review": "SAFETY_REQUIRES_POLICY_REVIEW",
    "likely_disallowed": "SAFETY_LIKELY_DISALLOWED",
    "unknown": "SAFETY_UNKNOWN",
}

SAFETY_CATEGORY_REASON_CODE_BY_VALUE: dict[str, str] = {
    category: f"SAFETY_{category.upper()}" for category in SAFETY_REASON_CATEGORIES
}

TARGET_REASON_CODE_BY_VALUE: dict[str, str] = {
    "core_model": "TARGET_CORE_LANGUAGE_SKILL",
    "rag_only": "TARGET_RAG_STABLE_FACT",
    "web_preferred": "TARGET_WEB_VOLATILE_FACT",
    "tool_required": "TARGET_TOOL_CALCULATION",
    "evaluation_only": "TARGET_EVALUATION_ONLY",
    "future_training_candidate": "TARGET_FUTURE_TRAINING_CANDIDATE",
    "do_not_learn": "TARGET_DO_NOT_LEARN_PERSONAL",
    "blocked": "TARGET_BLOCKED_UNSAFE",
}


__all__ = [
    "DOMAIN_REASON_CODE_BY_VALUE",
    "EVIDENCE_REASON_CODE_BY_VALUE",
    "FRESHNESS_REASON_CODE_BY_VALUE",
    "INTENT_REASON_CODE_BY_VALUE",
    "REASON_CODE_REGISTRY",
    "SAFETY_CATEGORY_REASON_CODE_BY_VALUE",
    "SAFETY_REASON_CODE_BY_VALUE",
    "TARGET_REASON_CODE_BY_VALUE",
    "is_known_reason_code",
]
