"""Minimal live public-chat input safety gate (Step 6). Reused entirely
from Phase 17's `core_model.knowledge_routing.safety_signal
.classify_safety_signal()` -- this module only *maps* that existing
signal onto the four public-chat decision values Step 6 requires; it
adds no new keyword lists and no new safety category. Full Phase 22
tool-aware safety governance is out of scope for this gate.

Phase 19 Step 31 adds one narrow addition: Phase 17's own signal is
still computed first and unchanged, but a small, independent,
checksum-versioned supplemental pattern set
(`core_model.public_chat.safety_supplemental_rules`) is also
consulted -- if *either* recommends refusal, the combined decision is
`refuse`. Phase 17's sealed policy file itself is never edited; this
closes a specific phrasing gap found during Phase 18's live browser
verification without touching that policy or its own checksum.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.knowledge_routing.safety_signal import (
    SafetySignalResult,
    classify_safety_signal,
)
from core_model.public_chat import INPUT_SAFETY_DECISIONS
from core_model.public_chat.safety_supplemental_rules import evaluate_supplemental_safety

_DECISION_BY_SAFETY_VALUE = {
    "safe": "allow",
    "sensitive_but_allowed": "allow_with_caution",
    "requires_policy_review": "needs_review",
    "likely_disallowed": "refuse",
    # An unmatched/unknown signal is not evidence of harm -- conservative
    # but not a block, matching Phase 17's own "unknown proves nothing"
    # philosophy for this minimal gate.
    "unknown": "allow_with_caution",
}


@dataclass(frozen=True)
class InputSafetyDecision:
    decision: str
    matched_category: str | None
    reason_codes: tuple[str, ...]
    matched_rules: tuple[str, ...]
    underlying: SafetySignalResult


def evaluate_input_safety(text: str) -> InputSafetyDecision:
    signal = classify_safety_signal(text)
    decision = _DECISION_BY_SAFETY_VALUE[signal.value]

    supplemental = evaluate_supplemental_safety(text)
    if supplemental.matched and decision != "refuse":
        decision = "refuse"
        return InputSafetyDecision(
            decision=decision,
            matched_category=supplemental.category,
            reason_codes=(*signal.reason_codes, supplemental.reason_code),
            matched_rules=signal.matched_rules,
            underlying=signal,
        )

    assert decision in INPUT_SAFETY_DECISIONS
    return InputSafetyDecision(
        decision=decision,
        matched_category=signal.matched_category,
        reason_codes=signal.reason_codes,
        matched_rules=signal.matched_rules,
        underlying=signal,
    )


__all__ = ["InputSafetyDecision", "evaluate_input_safety"]
