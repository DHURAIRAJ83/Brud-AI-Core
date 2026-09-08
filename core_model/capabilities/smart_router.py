"""Phase 16: Deterministic Smart Routing Decision Layer for Brud AI.

route_capability() returns a RoutingDecision that declares WHICH capability
should handle a request and under WHAT governance constraints.

CRITICAL: This module NEVER executes the selected capability.
          `executable` means "policy-permitted to dispatch, if the appropriate
           human-controlled caller subsequently invokes it."
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core_model.capabilities.capability_matrix import (
    SYSTEM_CAPABILITIES,
    CapabilityDefinition,
    get_capability,
)
from core_model.nlp.text_processor import is_code_or_technical_text, process_text

# ---------------------------------------------------------------------------
# Caller context & role taxonomies (read-only constants)
# ---------------------------------------------------------------------------
VALID_CALLER_CONTEXTS = {"public_chat", "admin_assistant", "internal"}
VALID_USER_ROLES = {"none", "authenticated", "admin", "super_admin"}

_ACCESS_RANK: dict[str, int] = {
    "public": 0,
    "authenticated": 1,
    "internal": 2,
    "admin": 3,
    "super_admin": 4,
    "unavailable": 999,
}

_ROLE_RANK: dict[str, int] = {
    "none": 0,
    "authenticated": 1,
    "admin": 3,
    "super_admin": 4,
}

# ---------------------------------------------------------------------------
# RoutingDecision — immutable result produced by route_capability()
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingDecision:
    requested_capability: str
    selected_capability_id: str | None
    selected_component: str | None
    confidence: float  # 0.0 – 1.0
    routing_reason: str
    alternative_capabilities: tuple[str, ...]
    access_level_required: str
    requires_human_approval: bool
    risk_level: str
    executable: bool  # True = policy permits future dispatch by authorized caller
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]


# ---------------------------------------------------------------------------
# Internal helpers — keyword signal tables
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("language_detection",  ("detect language", "மொழி", "language", "tamil", "tanglish", "identify language")),
    ("tanglish_normalization", ("tanglish", "தமிழ் மாற்று", "convert to tamil", "normalize tanglish")),
    ("rag_retrieval", ("search", "retrieve", "knowledge base", "find", "ஆவணம்", "தகவல்", "தேடு", "query my")),
    ("conversation_memory", ("remember", "recall", "memory", "previous", "நினைவு", "context")),
    ("tool_execution", ("run action", "execute action", "admin action", "tool", "கட்டளை செய்")),
    ("automation_evaluation", ("automation", "dry run", "simulate", "தானியக்க", "dry-run")),
    ("manual_automation_execution", ("manual execution", "trigger automation", "manually run")),
    ("admin_assistant_governance", ("propose", "review", "approve", "governance", "write action", "delete")),
    ("incremental_training", ("train", "training", "model training", "பயிற்சி", "dataset promotion")),
    ("vision_rag", ("image", "photo", "ocr", "visual", "படம்", "see")),
    ("voice_runtime", ("voice", "speak", "audio", "குரல்")),
    ("safety_filtering", ("safe", "unsafe", "security", "block", "பாதுகாப்பு")),
    ("data_studio_chunking", ("chunk", "structured record", "data studio")),
    ("external_ai_provider_gateway", ("provider", "openai", "gemini", "external model")),
    ("unicode_validation", ("unicode", "character", "orthography", "script validation")),
    ("text_normalization", ("normalize", "normalise", "whitespace", "control character")),
)

# Destructive keyword signals → high-risk warning
_DESTRUCTIVE_KEYWORDS = frozenset(("delete", "drop", "truncate", "remove all", "wipe", "destroy"))

# Admin-only high-risk signals (prevent public routing)
_ADMIN_ONLY_KEYWORDS = frozenset(
    ("execute", "run action", "admin action", "propose", "approve", "automation", "train")
)


def _classify_request(text: str) -> tuple[str, float]:
    """Returns (best_capability_id, confidence_score) using deterministic keyword matching."""
    low = text.lower()
    best_cap = ""
    best_score = 0.0
    for cap_id, keywords in _CATEGORY_KEYWORDS:
        cap = get_capability(cap_id)
        if cap is None or cap.availability == "unavailable":
            continue
        matched = sum(1 for kw in keywords if kw in low)
        if matched == 0:
            continue
        score = min(0.6 + 0.12 * matched, 0.99)
        if score > best_score:
            best_score = score
            best_cap = cap_id
    return best_cap, best_score


def _detect_destructive(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _DESTRUCTIVE_KEYWORDS)


def _caller_allows_access(cap: CapabilityDefinition, caller_context: str, user_role: str) -> tuple[bool, str]:
    """Returns (allowed, reason)."""
    if caller_context == "public_chat" and not cap.supports_public_chat:
        return False, "capability_not_public_safe"
    if cap.access_level == "unavailable":
        return False, "capability_unavailable"
    if cap.availability in {"unavailable", "blocked"}:
        return False, f"capability_{cap.availability}"
    caller_rank = _ROLE_RANK.get(user_role, 0)
    required_rank = _ACCESS_RANK.get(cap.access_level, 999)
    if required_rank > 4:
        return False, "capability_unavailable"
    if required_rank >= 3 and caller_rank < 3:
        return False, "insufficient_role"
    if required_rank == 4 and caller_rank < 4:
        return False, "insufficient_role"
    return True, ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def route_capability(
    request_text: str,
    *,
    caller_context: str = "public_chat",
    user_role: str = "none",
) -> RoutingDecision:
    """Deterministically map `request_text` to the best CapabilityDefinition.

    Args:
        request_text: The natural-language or mixed request.
        caller_context: "public_chat" | "admin_assistant" | "internal".
        user_role: "none" | "authenticated" | "admin" | "super_admin".

    Returns:
        A frozen RoutingDecision. Never executes any capability.
    """
    # ------- Phase 15 NLP classification -----------------------------------
    nlp = process_text(request_text)
    is_technical = is_code_or_technical_text(request_text) or nlp.is_technical_code

    # ------- Keyword-based intent matching ----------------------------------
    cap_id, confidence = _classify_request(request_text)

    # Apply NLP language-based boost for language-specific capabilities
    if nlp.detected_language in {"ta", "tanglish"} and confidence < 0.60:
        lang_cap = "language_detection"
        _, lang_score = "language_detection", 0.62
        if lang_score > confidence:
            cap_id, confidence = "language_detection", lang_score

    # Technical text → always language-safe routing; don't guess admin capabilities
    if is_technical and caller_context == "public_chat":
        if cap_id in {"tool_execution", "admin_assistant_governance", "incremental_training",
                      "manual_automation_execution", "automation_evaluation"}:
            cap_id = ""
            confidence = 0.0

    # ------- Fail-closed for low confidence --------------------------------
    if not cap_id or confidence < 0.60:
        return RoutingDecision(
            requested_capability=request_text[:256],
            selected_capability_id=None,
            selected_component=None,
            confidence=confidence,
            routing_reason="No capability matched with sufficient confidence.",
            alternative_capabilities=(),
            access_level_required="unavailable",
            requires_human_approval=False,
            risk_level="low",
            executable=False,
            blocking_reasons=("insufficient_routing_confidence",),
            warnings=(),
        )

    cap = get_capability(cap_id)
    assert cap is not None  # guaranteed by _classify_request

    # ------- Caller-context access check -----------------------------------
    allowed, deny_reason = _caller_allows_access(cap, caller_context, user_role)

    # ------- Destructive signal ------------------------------------------
    is_destructive = _detect_destructive(request_text)
    warnings: list[str] = []
    if is_destructive:
        warnings.append("destructive_intent_detected_governance_required")

    # ------- Alternatives (same category, different id) --------------------
    alternatives = tuple(
        c.capability_id
        for c in SYSTEM_CAPABILITIES.values()
        if c.category == cap.category and c.capability_id != cap_id and c.availability == "available"
    )

    # ------- Compute executable -------------------------------------------
    # executable = policy permits future dispatch; NEVER means "execute now"
    executable = (
        allowed
        and cap.availability in {"available", "partial"}
        and not (caller_context == "public_chat" and cap.risk_level in {"high", "critical"})
    )

    return RoutingDecision(
        requested_capability=request_text[:256],
        selected_capability_id=cap_id,
        selected_component=cap.source_component,
        confidence=confidence,
        routing_reason=f"Keyword match → capability '{cap_id}' (category: {cap.category}).",
        alternative_capabilities=alternatives,
        access_level_required=cap.access_level,
        requires_human_approval=cap.requires_human_approval,
        risk_level=cap.risk_level,
        executable=executable,
        blocking_reasons=(deny_reason,) if not allowed else (),
        warnings=tuple(warnings),
    )
