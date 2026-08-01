"""Deterministic, input-side safety-risk signal (Step 8).

Structural template only from `core_model.model_evaluation.
refusal_checks` (bounded, explicit marker tuples, conservative default)
-- that module classifies *model output*; this one classifies the
*incoming request*, a different direction, so no function is called
directly. The category vocabulary is reused verbatim from
`core_model.model_evaluation.SAFETY_CATEGORIES` via
`SAFETY_REASON_CATEGORIES`.

This is explicitly NOT the final live safety gate (plan doc, Step 8) --
it is an advisory signal the route recommender consults. A
`likely_disallowed` result forces `refuse`/`blocked` in the route and
learning-target engines; it never itself blocks anything by executing
a refusal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core_model.knowledge_routing import POLICY_VERSION, SAFETY_REASON_CATEGORIES
from core_model.knowledge_routing.reason_codes import (
    SAFETY_CATEGORY_REASON_CODE_BY_VALUE,
    SAFETY_REASON_CODE_BY_VALUE,
)

# High-risk: matching any of these forces `likely_disallowed`, regardless
# of any allowed-category marker also present in the same text (fail
# conservative, per the task's own non-negotiable rule).
_HIGH_RISK_MARKERS: dict[str, tuple[str, ...]] = {
    "violent_operational": (
        "how to attack a person", "how to assault", "plan an attack on",
        "தாக்குதல் திட்டமிட",
    ),
    "weapon_instruction": (
        "make a bomb", "build a bomb", "make a weapon", "build a gun", "3d print a gun",
        "ஆயுதம் தயாரிக்க", "வெடிகுண்டு தயாரிக்க",
    ),
    "malware_or_credential_theft": (
        "write malware", "write a virus", "how to hack into", "steal credentials",
        "steal a password", "crack a password", "bypass login security",
        "கடவுச்சொல் திருட",
    ),
    "fraud_or_forgery": (
        "forge a signature", "forge a document", "counterfeit currency", "fake id card",
        "போலி ஆவணம் தயாரிக்க",
    ),
    "personal_data_extraction": (
        "find someone's home address without consent", "get someone's private phone number",
        "dox this person", "track this person's location without them knowing",
    ),
    "dangerous_substance": (
        "how to synthesize a drug", "synthesize methamphetamine", "make poison",
        "நச்சுப்பொருள் தயாரிக்க",
    ),
    "self_harm_instruction": (
        "how to kill myself", "how to end my life", "self harm methods",
        "தற்கொலை செய்முறை",
    ),
}

# Requires human policy review, but not an automatic disallow.
_REVIEW_MARKERS: dict[str, tuple[str, ...]] = {
    "deliberate_disinformation": (
        "write fake news that looks real", "create a hoax to fool people",
        "spread false information about",
    ),
}

# Explicitly must remain allowed -- these exist so the classifier does not
# over-trigger on adjacent-sounding benign topics (Step 23 false-positive
# controls).
_ALLOWED_SENSITIVE_MARKERS: dict[str, tuple[str, ...]] = {
    "benign_cybersecurity": (
        "how does a firewall work", "what is penetration testing", "cybersecurity course",
        "learn about encryption", "how does encryption work", "secure coding practices",
        "cybersecurity", "vulnerability disclosure",
    ),
    "political_discussion": (
        "what do you think about this political party", "compare these two political ideologies",
        "explain this political movement",
    ),
    "government_criticism": (
        "criticize the government's policy", "why did the government fail",
        "government's mistake", "அரசின் தவறு",
    ),
    "legal_information": (
        "what does this law say", "explain this legal right", "what are my legal rights",
        "சட்ட உரிமை",
    ),
}


@dataclass(frozen=True)
class SafetySignalResult:
    value: str
    matched_category: str | None
    confidence_band: str
    reason_codes: tuple[str, ...]
    matched_rules: tuple[str, ...]
    policy_version: str
    secondary_values: tuple[str, ...] = field(default_factory=tuple)


def _hits(text_lower: str, markers: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(marker for marker in markers if marker in text_lower)


def classify_safety_signal(text: str) -> SafetySignalResult:
    text_lower = text.lower()

    for category, markers in _HIGH_RISK_MARKERS.items():
        hits = _hits(text_lower, markers)
        if hits:
            assert category in SAFETY_REASON_CATEGORIES
            return SafetySignalResult(
                value="likely_disallowed",
                matched_category=category,
                confidence_band="high" if len(hits) >= 2 else "medium",
                reason_codes=(
                    SAFETY_REASON_CODE_BY_VALUE["likely_disallowed"],
                    SAFETY_CATEGORY_REASON_CODE_BY_VALUE[category],
                ),
                matched_rules=hits,
                policy_version=POLICY_VERSION,
            )

    for category, markers in _REVIEW_MARKERS.items():
        hits = _hits(text_lower, markers)
        if hits:
            return SafetySignalResult(
                value="requires_policy_review",
                matched_category=category,
                confidence_band="medium",
                reason_codes=(
                    SAFETY_REASON_CODE_BY_VALUE["requires_policy_review"],
                    SAFETY_CATEGORY_REASON_CODE_BY_VALUE[category],
                ),
                matched_rules=hits,
                policy_version=POLICY_VERSION,
            )

    for category, markers in _ALLOWED_SENSITIVE_MARKERS.items():
        hits = _hits(text_lower, markers)
        if hits:
            return SafetySignalResult(
                value="sensitive_but_allowed",
                matched_category=category,
                confidence_band="medium",
                reason_codes=(
                    SAFETY_REASON_CODE_BY_VALUE["sensitive_but_allowed"],
                    SAFETY_CATEGORY_REASON_CODE_BY_VALUE[category],
                ),
                matched_rules=hits,
                policy_version=POLICY_VERSION,
            )

    return SafetySignalResult(
        value="safe",
        matched_category=None,
        confidence_band="low",
        reason_codes=(SAFETY_REASON_CODE_BY_VALUE["safe"],),
        matched_rules=(),
        policy_version=POLICY_VERSION,
    )


__all__ = ["SafetySignalResult", "classify_safety_signal"]
