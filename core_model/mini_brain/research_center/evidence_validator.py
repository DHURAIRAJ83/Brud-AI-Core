"""MB-10: Evidence Validator -- pure, rule-based, no AI. Flags
surface-level signals of weak evidence: absolute claims made without
any nearby citation marker, hedging language, and outputs too short to
plausibly cover the requested topic. This is a heuristic screen, not a
fact-checker -- MB-10 cannot verify whether any claim is actually
true, and never claims to.
"""

from __future__ import annotations

from typing import Any

_ABSOLUTE_CLAIM_WORDS = ("always", "never", "definitely", "certainly", "undeniably", "guaranteed")
_HEDGING_WORDS = ("might", "may", "possibly", "perhaps", "unclear", "i think", "it seems")
_MIN_WORDS_FOR_COMPLETENESS = 25


def validate_evidence(*, text: str, citation_marker_count: int) -> dict[str, Any]:
    lowered = text.lower()
    words = text.split()
    word_count = len(words)

    absolute_claim_count = sum(1 for word in _ABSOLUTE_CLAIM_WORDS if word in lowered)
    hedging_count = sum(1 for phrase in _HEDGING_WORDS if phrase in lowered)

    unsupported_claims = absolute_claim_count > 0 and citation_marker_count == 0
    weak_evidence = hedging_count >= 2 or (absolute_claim_count > 0 and hedging_count > 0)
    missing_facts = word_count < _MIN_WORDS_FOR_COMPLETENESS

    reasons = []
    if unsupported_claims:
        reasons.append(f"{absolute_claim_count} absolute claim(s) with no citation marker nearby")
    if weak_evidence:
        reasons.append(f"{hedging_count} hedging phrase(s) detected")
    if missing_facts:
        reasons.append(f"only {word_count} word(s), below the {_MIN_WORDS_FOR_COMPLETENESS}-word completeness bound")

    evidence_score = 100.0
    if unsupported_claims:
        evidence_score -= 40.0
    if weak_evidence:
        evidence_score -= 30.0
    if missing_facts:
        evidence_score -= 30.0
    evidence_score = max(0.0, evidence_score)

    return {
        "word_count": word_count,
        "unsupported_claims": unsupported_claims,
        "weak_evidence": weak_evidence,
        "missing_facts": missing_facts,
        "reasons": reasons,
        "evidence_score": round(evidence_score, 1),
    }
