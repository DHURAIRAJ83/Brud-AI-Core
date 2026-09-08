"""Phase 19: Clarification Intelligence & Deterministic Gap Classification.

Provides CPU-first, side-effect-free functions for classifying Public Chat knowledge gaps
and generating bilingual clarification metadata across five core cases:

  Case A — Answerable: No gap / no clarification required.
  Case B — Knowledge Gap: Query understood but knowledge/evidence unavailable.
  Case C — Ambiguous Intent: Multiple plausible intents exist -> ask concise clarification.
  Case D — Unsupported Capability: Capability does not exist -> state honestly, no fake claims.
  Case E — Security/Admin Boundary: Public user targeting admin capability -> SECURITY_ADMIN_BOUNDARY
           classification, CRITICAL severity, NO clarification question facilitating privilege escalation.

Critical invariants:
  ✅ Pure, deterministic functions.
  ✅ Preserves Public/Admin security isolation.
  ❌ No LLM calls, vector DB, or embeddings inside this pure module.
  ❌ No database writes or schema migrations.
  ❌ No network calls or process spawning.
"""

from __future__ import annotations

from typing import Any, Sequence

from core_model.capabilities.capability_matrix import get_capability
from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_AMBIGUOUS_INTENT,
    GAP_TAXONOMY_CLARIFICATION_REQUIRED,
    GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
    GAP_TAXONOMY_LOW_ROUTING_CONFIDENCE,
    GAP_TAXONOMY_MEMORY_UNAVAILABLE,
    GAP_TAXONOMY_PROVIDER_UNAVAILABLE,
    GAP_TAXONOMY_RAG_INSUFFICIENT_EVIDENCE,
    GAP_TAXONOMY_RAG_SCOPE_UNAVAILABLE,
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED,
    GAP_TAXONOMY_UNKNOWN_INTENT,
    GAP_TAXONOMY_UNSUPPORTED_CAPABILITY,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    KnowledgeGap,
    generate_gap_id,
    sanitize_summary,
)
from core_model.capabilities.public_capability_gate import GateDecision
from core_model.capabilities.smart_router import RoutingDecision
from core_model.nlp.text_processor import NLPResult

# Deterministic bilingual clarification templates
_CLARIFICATION_QUESTIONS: dict[str, dict[str, str]] = {
    GAP_TAXONOMY_CLARIFICATION_REQUIRED: {
        "ta": "உங்கள் கேள்வியை மேலும் தெளிவாகக் கூற முடியுமா? (எ.கா. ஆவணத் தேடலா அல்லது பொதுத் தகவலா?)",
        "en": "Could you clarify your question? (e.g. are you looking for document search or general info?)",
    },
    GAP_TAXONOMY_AMBIGUOUS_INTENT: {
        "ta": "தயவுசெய்து நீங்கள் எதைப் பற்றி கேட்கிறீர்கள் என்பதை சற்று விரிவாகத் தெரிவிக்கவும்.",
        "en": "Please provide a bit more detail about what specific topic you are asking about.",
    },
    GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED: {
        "ta": "இந்த தொழில்நுட்ப கட்டளை தொடர்பான எந்த குறிப்பிட்ட தகவலை அறிய விரும்புகிறீர்கள்?",
        "en": "Which specific detail regarding this technical command would you like to know?",
    },
}

_ADMIN_ONLY_CAPABILITIES: frozenset[str] = frozenset(
    {
        "admin_assistant_governance",
        "automation_evaluation",
        "manual_automation_execution",
        "tool_execution",
        "data_studio_chunking",
        "external_ai_provider_gateway",
        "incremental_training",
        "autonomous_execution",
    }
)


def should_request_clarification(
    gap_type: str,
    *,
    caller_context: str = "public_chat",
    user_role: str = "none",
) -> bool:
    """Evaluate whether a clarification question is permitted for a given gap type and security context.

    Returns False for:
      - SECURITY_ADMIN_BOUNDARY (prevents privilege escalation facilitation)
      - UNSUPPORTED_CAPABILITY (no fake capability claims)
      - UNKNOWN_INTENT / LOW_ROUTING_CONFIDENCE (fail-closed gibberish)
    """
    if gap_type in (
        GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        GAP_TAXONOMY_UNSUPPORTED_CAPABILITY,
        GAP_TAXONOMY_UNKNOWN_INTENT,
        GAP_TAXONOMY_LOW_ROUTING_CONFIDENCE,
        GAP_TAXONOMY_PROVIDER_UNAVAILABLE,
    ):
        return False

    return gap_type in (
        GAP_TAXONOMY_CLARIFICATION_REQUIRED,
        GAP_TAXONOMY_AMBIGUOUS_INTENT,
        GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED,
    )


def build_clarification_question(
    gap_type: str,
    language: str = "ta",
    *,
    caller_context: str = "public_chat",
    user_role: str = "none",
) -> str | None:
    """Construct a concise, bilingual clarification question if policy permits."""
    if not should_request_clarification(gap_type, caller_context=caller_context, user_role=user_role):
        return None

    lang_key = "ta" if language in ("ta", "tanglish") else "en"
    templates = _CLARIFICATION_QUESTIONS.get(gap_type, _CLARIFICATION_QUESTIONS[GAP_TAXONOMY_CLARIFICATION_REQUIRED])
    return templates.get(lang_key, templates["ta"])


def summarize_knowledge_gap(text: str | None, nlp_result: NLPResult | None = None) -> str:
    """Generate a sanitized, PII-free semantic summary for observation logs."""
    if text is None:
        return ""
    clean_summary = sanitize_summary(text)
    if nlp_result is not None and nlp_result.is_technical_code:
        return f"[TECHNICAL_CODE] {clean_summary}"
    return clean_summary


def classify_knowledge_gap(
    request_text: str,
    nlp_result: NLPResult,
    routing_decision: RoutingDecision,
    *,
    request_id: str = "unknown-request",
    gate_decision: GateDecision | None = None,
    route_used: str | None = None,
    evidence_status: str | None = None,
    route_reason_codes: Sequence[str] = (),
    caller_context: str = "public_chat",
    user_role: str = "none",
) -> KnowledgeGap:
    """Deterministically classify a Public Chat request turn into a structured KnowledgeGap observation.

    This function:
      - Analyzes NLP, Routing, Gate, and execution route metadata.
      - Enforces Public/Admin security isolation (Case E).
      - Assigns deterministic gap_type and severity.
      - Builds clarification questions ONLY when safe and policy-permitted.
      - Produces an immutable KnowledgeGap dataclass.
    """
    selected_cap_id = routing_decision.selected_capability_id
    reasons = tuple(route_reason_codes)

    req_low = request_text.lower()
    has_admin_kw = any(kw in req_low for kw in ("admin", "governance", "propose write", "tool_execution", "automation_evaluation", "manual_automation", "incremental_training"))
    has_destructive_kw = any(kw in req_low for kw in ("delete all", "wipe destroy", "drop table", "remove database"))

    is_admin_cap = (
        selected_cap_id in _ADMIN_ONLY_CAPABILITIES
        or has_admin_kw
        or has_destructive_kw
        or (selected_cap_id is not None and get_capability(selected_cap_id) is not None and not get_capability(selected_cap_id).supports_public_chat)
    )

    gate_denied_admin = (
        gate_decision is not None
        and not gate_decision.allowed
        and (
            (gate_decision.denial_reason or "").startswith("admin_only")
            or "admin" in (gate_decision.denial_reason or "")
            or "destructive" in (gate_decision.denial_reason or "")
        )
    )

    if is_admin_cap or gate_denied_admin:
        gap_type = GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY
        severity = SEVERITY_CRITICAL
        clarification_req = False
        clarification_q = None
        failure_class = "security_admin_boundary"
        source_stage = "gate_evaluated" if gate_denied_admin else "routing_evaluated"

    # -----------------------------------------------------------------------
    # Case D — Unsupported Capability
    # -----------------------------------------------------------------------
    elif route_used == "insufficient" and ("tool_unsupported" in reasons or "tool_unavailable" in reasons or selected_cap_id == "autonomous_execution"):
        gap_type = GAP_TAXONOMY_UNSUPPORTED_CAPABILITY
        severity = SEVERITY_MEDIUM
        clarification_req = False
        clarification_q = None
        failure_class = "unsupported_capability"
        source_stage = "service_dispatched"

    # -----------------------------------------------------------------------
    # Case C — Ambiguous Intent / Clarification Required
    # -----------------------------------------------------------------------
    elif route_used == "clarify" or selected_cap_id == "language_detection" and nlp_result.detected_language == "mixed" and routing_decision.confidence < 0.70:
        gap_type = GAP_TAXONOMY_CLARIFICATION_REQUIRED
        severity = SEVERITY_LOW
        clarification_req = True
        clarification_q = build_clarification_question(gap_type, nlp_result.detected_language, caller_context=caller_context, user_role=user_role)
        failure_class = "clarification_required"
        source_stage = "service_dispatched" if route_used == "clarify" else "routing_evaluated"

    # -----------------------------------------------------------------------
    # Case B — Knowledge / Evidence Unavailable
    # -----------------------------------------------------------------------
    elif route_used == "insufficient" and "rag_insufficient_evidence" in reasons:
        gap_type = GAP_TAXONOMY_RAG_INSUFFICIENT_EVIDENCE
        severity = SEVERITY_MEDIUM
        clarification_req = False
        clarification_q = None
        failure_class = "rag_insufficient_evidence"
        source_stage = "service_dispatched"

    elif route_used == "insufficient" and "rag_scope_unavailable" in reasons:
        gap_type = GAP_TAXONOMY_RAG_SCOPE_UNAVAILABLE
        severity = SEVERITY_MEDIUM
        clarification_req = False
        clarification_q = None
        failure_class = "rag_scope_unavailable"
        source_stage = "service_dispatched"

    elif route_used == "insufficient" and ("memory_unavailable" in reasons or "memory_consent_required" in reasons):
        gap_type = GAP_TAXONOMY_MEMORY_UNAVAILABLE
        severity = SEVERITY_LOW
        clarification_req = False
        clarification_q = None
        failure_class = "memory_unavailable"
        source_stage = "service_dispatched"

    elif route_used == "insufficient" and ("provider_unavailable" in reasons or "model_assignment_unavailable" in reasons or "trusted_web_unavailable" in reasons):
        gap_type = GAP_TAXONOMY_PROVIDER_UNAVAILABLE
        severity = SEVERITY_HIGH
        clarification_req = False
        clarification_q = None
        failure_class = "provider_unavailable"
        source_stage = "service_dispatched"

    # -----------------------------------------------------------------------
    # Unknown / Low Confidence Input
    # -----------------------------------------------------------------------
    elif nlp_result.detected_language == "unknown" or selected_cap_id is None or routing_decision.confidence < 0.60:
        if nlp_result.is_technical_code:
            gap_type = GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED
            severity = SEVERITY_MEDIUM
            clarification_req = True
            clarification_q = build_clarification_question(gap_type, nlp_result.detected_language, caller_context=caller_context, user_role=user_role)
            failure_class = "technical_context_unresolved"
        else:
            gap_type = GAP_TAXONOMY_UNKNOWN_INTENT if nlp_result.detected_language == "unknown" else GAP_TAXONOMY_LOW_ROUTING_CONFIDENCE
            severity = SEVERITY_LOW
            clarification_req = False
            clarification_q = None
            failure_class = "low_routing_confidence"
        source_stage = "routing_evaluated"

    # -----------------------------------------------------------------------
    # Case A — Answerable Request
    # -----------------------------------------------------------------------
    else:
        gap_type = GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND if evidence_status == "insufficient" else "ANSWERABLE"
        severity = SEVERITY_LOW
        clarification_req = False
        clarification_q = None
        failure_class = "none"
        source_stage = "response_generated"

    safe_sum = summarize_knowledge_gap(request_text, nlp_result)

    return KnowledgeGap(
        gap_id=generate_gap_id(),
        request_id=request_id,
        detected_language=nlp_result.detected_language,
        language_confidence=nlp_result.language_confidence,
        normalized_intent=nlp_result.normalized_text,
        requested_capability_id=routing_decision.requested_capability[:64] if routing_decision.requested_capability else None,
        selected_capability_id=selected_cap_id,
        routing_confidence=routing_decision.confidence,
        failure_classification=failure_class,
        gap_type=gap_type,
        severity=severity,
        clarification_required=clarification_req,
        clarification_question=clarification_q,
        evidence_status=evidence_status or "none",
        source_stage=source_stage,
        safe_summary=safe_sum,
        metadata={
            "is_tanglish": nlp_result.is_tanglish,
            "is_technical": nlp_result.is_technical_code,
            "route_used": route_used or "unknown",
            "route_reasons": list(reasons),
        },
    )


__all__ = [
    "build_clarification_question",
    "classify_knowledge_gap",
    "should_request_clarification",
    "summarize_knowledge_gap",
]
