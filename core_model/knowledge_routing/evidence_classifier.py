"""Deterministic evidence-requirement classification (Step 6).

Depends on already-computed domain, subdomain, freshness, intent, and
safety-risk (the pipeline computes this layer after all four). A fixed,
ordered precedence -- never a weighted score -- exactly mirroring the
spirit of the execution-route engine's own precedence order, since
evidence requirement is itself an input to that engine.
"""

from __future__ import annotations

from core_model.knowledge_routing import POLICY_VERSION
from core_model.knowledge_routing.reason_codes import EVIDENCE_REASON_CODE_BY_VALUE
from core_model.knowledge_routing.result_types import LayerResult

_INTERNAL_EVIDENCE_SUBDOMAINS = frozenset(
    {"software_documentation", "legal_or_regulatory_current", "application_guidance"}
)
_NO_EVIDENCE_DOMAINS = frozenset({"personal_context", "administrative_action"})
_TOOL_INTENTS = frozenset({"ask_calculation", "ask_code"})


def classify_evidence_requirement(
    *,
    domain: str,
    subdomain: str | None,
    freshness: str,
    intent: str,
    safety_value: str,
    ambiguity_value: str,
) -> LayerResult:
    if safety_value == "likely_disallowed":
        return LayerResult(
            value="blocked",
            confidence_band="high",
            reason_codes=(EVIDENCE_REASON_CODE_BY_VALUE["blocked"],),
            matched_rules=("safety:likely_disallowed",),
            policy_version=POLICY_VERSION,
        )

    if ambiguity_value == "ambiguous":
        return LayerResult(
            value="clarification_required",
            confidence_band="medium",
            reason_codes=(EVIDENCE_REASON_CODE_BY_VALUE["clarification_required"],),
            matched_rules=("ambiguity:ambiguous",),
            policy_version=POLICY_VERSION,
        )

    if intent in _TOOL_INTENTS:
        return LayerResult(
            value="deterministic_tool_required",
            confidence_band="high",
            reason_codes=(EVIDENCE_REASON_CODE_BY_VALUE["deterministic_tool_required"],),
            matched_rules=(f"intent:{intent}",),
            policy_version=POLICY_VERSION,
        )

    if freshness in ("real_time", "time_sensitive"):
        return LayerResult(
            value="external_verified_evidence_required",
            confidence_band="high" if freshness == "real_time" else "medium",
            reason_codes=(EVIDENCE_REASON_CODE_BY_VALUE["external_verified_evidence_required"],),
            matched_rules=(f"freshness:{freshness}",),
            policy_version=POLICY_VERSION,
        )

    if subdomain in _INTERNAL_EVIDENCE_SUBDOMAINS:
        return LayerResult(
            value="internal_evidence_required",
            confidence_band="medium",
            reason_codes=(EVIDENCE_REASON_CODE_BY_VALUE["internal_evidence_required"],),
            matched_rules=(f"subdomain:{subdomain}",),
            policy_version=POLICY_VERSION,
        )

    if domain in _NO_EVIDENCE_DOMAINS:
        return LayerResult(
            value="none",
            confidence_band="medium",
            reason_codes=(EVIDENCE_REASON_CODE_BY_VALUE["none"],),
            matched_rules=(f"domain:{domain}",),
            policy_version=POLICY_VERSION,
        )

    if freshness in ("timeless", "slow_changing", "historical"):
        return LayerResult(
            value="model_knowledge_ok",
            confidence_band="medium" if freshness == "timeless" else "low",
            reason_codes=(EVIDENCE_REASON_CODE_BY_VALUE["model_knowledge_ok"],),
            matched_rules=(f"freshness:{freshness}",),
            policy_version=POLICY_VERSION,
        )

    return LayerResult(
        value="model_knowledge_ok",
        confidence_band="unknown",
        reason_codes=(EVIDENCE_REASON_CODE_BY_VALUE["model_knowledge_ok"],),
        matched_rules=(),
        policy_version=POLICY_VERSION,
    )


__all__ = ["classify_evidence_requirement"]
