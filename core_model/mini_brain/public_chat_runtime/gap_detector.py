"""MB-23: Gap Detector -- pure. Implements the task spec's own Step 8
detection rules over already-sanitized/already-computed inputs: an
explicit negative phrase in the user's own (sanitized) text, a low
`confidence_band` already returned by the public chat response, an
already-reported insufficient-evidence signal, and a topic repeated
within the bounded conversation window. Never a semantic-similarity or
ML classifier -- every rule here is a disclosed, literal heuristic.
"""

from __future__ import annotations

from typing import Any

_NEGATIVE_PHRASES = (
    "wrong", "not correct", "incorrect", "didn't answer", "did not answer",
    "doesn't answer", "does not answer", "not what i asked", "that's not right",
    "makes no sense", "useless",
)
DEFAULT_REPEATED_QUESTION_THRESHOLD = 2


def detect_explicit_negative(*, sanitized_user_text: str) -> dict[str, Any]:
    lowered = sanitized_user_text.lower()
    matched = [phrase for phrase in _NEGATIVE_PHRASES if phrase in lowered]
    return {"detected": bool(matched), "matched_phrases": matched}


def detect_low_confidence(*, confidence_band: str) -> dict[str, Any]:
    return {"detected": confidence_band == "low"}


def detect_insufficient_evidence(*, evidence_sufficient: bool, insufficient_evidence_flag: bool) -> dict[str, Any]:
    return {"detected": (not evidence_sufficient) or insufficient_evidence_flag}


def detect_repeated_question(
    *, current_topic_key: str, recent_topic_keys: list[str], threshold: int = DEFAULT_REPEATED_QUESTION_THRESHOLD,
) -> dict[str, Any]:
    occurrences = recent_topic_keys.count(current_topic_key)
    return {"detected": occurrences >= threshold, "occurrences": occurrences}


def detect_gaps(
    *, sanitized_user_text: str, confidence_band: str, evidence_sufficient: bool, insufficient_evidence_flag: bool,
    current_topic_key: str, recent_topic_keys: list[str],
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []

    negative = detect_explicit_negative(sanitized_user_text=sanitized_user_text)
    if negative["detected"]:
        signals.append({
            "signal_type": "explicit_negative", "severity": "high",
            "reason": f"user text matched negative phrase(s): {negative['matched_phrases']}",
        })

    if detect_low_confidence(confidence_band=confidence_band)["detected"]:
        signals.append({
            "signal_type": "low_confidence", "severity": "medium",
            "reason": "assistant confidence_band was reported as low",
        })

    if detect_insufficient_evidence(
        evidence_sufficient=evidence_sufficient, insufficient_evidence_flag=insufficient_evidence_flag,
    )["detected"]:
        signals.append({
            "signal_type": "insufficient_evidence", "severity": "medium",
            "reason": "the public chat response reported insufficient evidence for this answer",
        })

    repeated = detect_repeated_question(current_topic_key=current_topic_key, recent_topic_keys=recent_topic_keys)
    if repeated["detected"]:
        signals.append({
            "signal_type": "repeated_question", "severity": "high",
            "reason": f"the same topic was rephrased {repeated['occurrences']} time(s) within this session's window",
        })

    return signals
