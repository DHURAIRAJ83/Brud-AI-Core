"""Phase 17 orchestrating pipeline (`classify()`). Wires every layer in
dependency order into one explainable, versioned `ClassificationResult`.

This module never persists raw text, never calls Model/RAG/Web/Tool/
Memory, and never touches `/api/chat` or `ChatOrchestrationService`. It
is a pure function of its input text (plus optional structured
metadata for non-chat context types -- see `adapters.py`).

Pipeline order (dependency-driven, not the literal Step 2 listing --
documented deviation, plan doc §1): normalize -> language -> intent ->
domain/subdomain -> freshness -> safety-risk -> ambiguity -> evidence
requirement (needs domain+freshness+intent+safety) -> execution-route
(needs safety+ambiguity+domain+evidence) -> learning-target (needs
route+safety+domain+freshness+evidence) -> Tamil-first policy check
(a validator over the route, not a new layer).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from backend.services.text_normalization import normalize_text
from core_model.knowledge_routing import CONTEXT_TYPES, POLICY_VERSION, TAXONOMY_VERSION
from core_model.knowledge_routing.ambiguity_classifier import classify_ambiguity
from core_model.knowledge_routing.domain_classifier import classify_domain
from core_model.knowledge_routing.evidence_classifier import classify_evidence_requirement
from core_model.knowledge_routing.freshness_classifier import classify_freshness
from core_model.knowledge_routing.intent_classifier import classify_intent
from core_model.knowledge_routing.learning_target_recommender import recommend_learning_target
from core_model.knowledge_routing.reason_codes import REASON_CODE_REGISTRY
from core_model.knowledge_routing.route_recommender import recommend_execution_route
from core_model.knowledge_routing.safety_signal import classify_safety_signal
from core_model.knowledge_routing.tamil_first_policy import check_tamil_first_policy
from core_model.rag.language_routing import classify_language

MAX_INPUT_LENGTH = 4000

# Bidirectional-override / embedding control characters -- a text-spoofing
# vector, stripped defensively before classification (Step 25).
_BIDI_CONTROL_RE = re.compile(
    "[‪-‮⁦-⁩؜]"
)
_OTHER_C0_CONTROL_RE = re.compile(r"[\x01-\x08\x0b\x0e-\x1f\x7f]")


class ClassificationInputError(ValueError):
    """Raised when the input text cannot be safely classified at all."""


@dataclass(frozen=True)
class ClassificationResult:
    input_hash: str
    context_type: str
    policy_version: str
    taxonomy_version: str

    language_category: str
    language_reason_codes: tuple[str, ...]

    intent: str
    intent_secondary: tuple[str, ...]
    intent_confidence_band: str
    intent_reason_codes: tuple[str, ...]

    domain: str
    subdomain: str | None
    domain_secondary: tuple[str, ...]
    domain_confidence_band: str
    domain_reason_codes: tuple[str, ...]

    freshness: str
    freshness_confidence_band: str
    freshness_reason_codes: tuple[str, ...]

    ambiguity: str
    ambiguity_confidence_band: str
    ambiguity_reason_codes: tuple[str, ...]

    safety_risk: str
    safety_matched_category: str | None
    safety_confidence_band: str
    safety_reason_codes: tuple[str, ...]

    evidence_requirement: str
    evidence_confidence_band: str
    evidence_reason_codes: tuple[str, ...]

    execution_route: str
    execution_route_confidence_band: str
    execution_route_reason_codes: tuple[str, ...]
    route_blockers: tuple[str, ...]
    requires_human_review: bool

    learning_target: str
    learning_target_confidence_band: str
    learning_target_reason_codes: tuple[str, ...]
    grants_training_approval: bool

    tamil_first_policy_applied: bool
    tamil_first_policy_violation: bool
    tamil_first_reason_codes: tuple[str, ...]

    all_reason_codes: tuple[str, ...] = field(default_factory=tuple)
    input_truncated: bool = False


def _sanitize(text: str) -> tuple[str, bool]:
    truncated = False
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
        truncated = True
    text = unicodedata.normalize("NFC", text)
    text = _BIDI_CONTROL_RE.sub("", text)
    text = _OTHER_C0_CONTROL_RE.sub("", text)
    return text, truncated


def _hash_input(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify(text: str, *, context_type: str = "public_chat_question") -> ClassificationResult:
    if context_type not in CONTEXT_TYPES:
        raise ClassificationInputError(f"unknown context_type: {context_type!r}")
    if not isinstance(text, str) or not text.strip():
        raise ClassificationInputError("input text must be a non-empty string")

    sanitized_text, truncated = _sanitize(text)
    input_hash = _hash_input(sanitized_text)

    normalization = normalize_text(sanitized_text)
    normalized_text = normalization.normalized

    language = classify_language(normalized_text)
    language_category = language["language_category"]
    language_reason_codes = {
        "ta": ("LANG_TAMIL_DETECTED",),
        "en": ("LANG_ENGLISH_DETECTED",),
        "tgl": ("LANG_TANGLISH_DETECTED",),
        "mixed": ("LANG_MIXED_DETECTED",),
        "unknown": ("LANG_UNKNOWN",),
    }[language_category]

    intent_result = classify_intent(normalized_text)
    domain_result = classify_domain(normalized_text)
    freshness_result = classify_freshness(normalized_text, domain=domain_result.domain)
    safety_result = classify_safety_signal(normalized_text)
    ambiguity_result = classify_ambiguity(normalized_text)

    evidence_result = classify_evidence_requirement(
        domain=domain_result.domain,
        subdomain=domain_result.subdomain,
        freshness=freshness_result.value,
        intent=intent_result.value,
        safety_value=safety_result.value,
        ambiguity_value=ambiguity_result.value,
    )

    route_recommendation = recommend_execution_route(
        safety_value=safety_result.value,
        ambiguity_value=ambiguity_result.value,
        domain=domain_result.domain,
        evidence_value=evidence_result.value,
    )

    learning_target_recommendation = recommend_learning_target(
        execution_route=route_recommendation.execution_route,
        safety_value=safety_result.value,
        domain=domain_result.domain,
        freshness=freshness_result.value,
        evidence_value=evidence_result.value,
        route_confidence_band=route_recommendation.confidence_band,
    )

    tamil_first = check_tamil_first_policy(
        language_category=language_category,
        domain=domain_result.domain,
        freshness=freshness_result.value,
        execution_route=route_recommendation.execution_route,
    )

    all_reason_codes = tuple(
        dict.fromkeys(
            (
                *language_reason_codes,
                *intent_result.reason_codes,
                *domain_result.reason_codes,
                *freshness_result.reason_codes,
                *ambiguity_result.reason_codes,
                *safety_result.reason_codes,
                *evidence_result.reason_codes,
                *route_recommendation.reason_codes,
                *learning_target_recommendation.reason_codes,
                *tamil_first.reason_codes,
            )
        )
    )
    for code in all_reason_codes:
        assert code in REASON_CODE_REGISTRY, f"unregistered reason code emitted: {code}"

    return ClassificationResult(
        input_hash=input_hash,
        context_type=context_type,
        policy_version=POLICY_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        language_category=language_category,
        language_reason_codes=language_reason_codes,
        intent=intent_result.value,
        intent_secondary=intent_result.secondary_values,
        intent_confidence_band=intent_result.confidence_band,
        intent_reason_codes=intent_result.reason_codes,
        domain=domain_result.domain,
        subdomain=domain_result.subdomain,
        domain_secondary=domain_result.secondary_domains,
        domain_confidence_band=domain_result.confidence_band,
        domain_reason_codes=domain_result.reason_codes,
        freshness=freshness_result.value,
        freshness_confidence_band=freshness_result.confidence_band,
        freshness_reason_codes=freshness_result.reason_codes,
        ambiguity=ambiguity_result.value,
        ambiguity_confidence_band=ambiguity_result.confidence_band,
        ambiguity_reason_codes=ambiguity_result.reason_codes,
        safety_risk=safety_result.value,
        safety_matched_category=safety_result.matched_category,
        safety_confidence_band=safety_result.confidence_band,
        safety_reason_codes=safety_result.reason_codes,
        evidence_requirement=evidence_result.value,
        evidence_confidence_band=evidence_result.confidence_band,
        evidence_reason_codes=evidence_result.reason_codes,
        execution_route=route_recommendation.execution_route,
        execution_route_confidence_band=route_recommendation.confidence_band,
        execution_route_reason_codes=route_recommendation.reason_codes,
        route_blockers=route_recommendation.route_blockers,
        requires_human_review=(
            route_recommendation.requires_human_review
            or learning_target_recommendation.requires_human_review
        ),
        learning_target=learning_target_recommendation.learning_target,
        learning_target_confidence_band=learning_target_recommendation.confidence_band,
        learning_target_reason_codes=learning_target_recommendation.reason_codes,
        grants_training_approval=learning_target_recommendation.grants_training_approval,
        tamil_first_policy_applied=tamil_first.policy_applied,
        tamil_first_policy_violation=tamil_first.violation,
        tamil_first_reason_codes=tamil_first.reason_codes,
        all_reason_codes=all_reason_codes,
        input_truncated=truncated,
    )


__all__ = [
    "ClassificationInputError",
    "ClassificationResult",
    "MAX_INPUT_LENGTH",
    "classify",
]
