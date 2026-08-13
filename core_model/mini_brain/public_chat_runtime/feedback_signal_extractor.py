"""MB-23: Feedback Signal Extractor -- pure. Assembles the final,
persistable feedback-signal records for one turn -- combining
`gap_detector.py`'s own detected gaps with `response_safety_filter.py`'s
severity escalation. It never performs detection itself and never
touches unsanitized text; `sanitized_text`/`topic_key` are passed in
already produced by `feedback_sanitizer.py` / `query_classifier.py`.
"""

from __future__ import annotations

from typing import Any

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def _escalate(severity: str) -> str:
    if severity == "low":
        return "medium"
    if severity == "medium":
        return "high"
    return severity


def extract_feedback_signals(
    *, sanitized_text: str, topic_key: str, gap_signals: list[dict[str, Any]],
    safety_evaluation: dict[str, Any],
) -> list[dict[str, Any]]:
    escalate = bool(safety_evaluation.get("escalate_severity"))
    signals: list[dict[str, Any]] = []

    for gap in gap_signals:
        severity = gap["severity"]
        if escalate:
            severity = _escalate(severity)
        signals.append({
            "signal_type": gap["signal_type"], "severity": severity, "normalized_text": sanitized_text,
            "topic_key": topic_key, "reason": gap["reason"],
        })

    if safety_evaluation.get("raise_safety_flag_signal"):
        signals.append({
            "signal_type": "safety_flag", "severity": "high", "normalized_text": sanitized_text,
            "topic_key": topic_key, "reason": f"response safety_status escalated: {safety_evaluation.get('safety_status')}",
        })

    signals.sort(key=lambda s: _SEVERITY_ORDER.get(s["severity"], 0), reverse=True)
    return signals
