"""MB-08: Failure Analyzer -- pure. Classifies already-fetched Public
Chat routing events into the five failure categories the task spec
names, from real, structured fields only -- never inferred from
question/answer text (routing events never store any).

Category definitions (disclosed, deterministic):
  - no_answer: resolved route is clarify/refuse/insufficient
  - blocked_answer: route_status == 'blocked' or safety_status is
    refused/output_blocked
  - timeout: error_code mentions "timeout" (case-insensitive) --
    the only signal available; other error_code values are counted
    as a separate "other_error" bucket, never silently dropped
  - low_confidence: evidence_status is insufficient/none -- no
    dedicated confidence field exists on routing events, so this is
    an explicit, disclosed proxy
  - wrong_answer: cross-referenced from a thumbs_down feedback event
    sharing the same request_id (the only real negative-outcome
    signal tied to a specific answer)
"""

from __future__ import annotations

from typing import Any

NO_ANSWER_ROUTES = frozenset({"clarify", "refuse", "insufficient"})
BLOCKED_SAFETY_STATUSES = frozenset({"refused", "output_blocked"})
LOW_CONFIDENCE_EVIDENCE = frozenset({"insufficient", "none"})


def analyze_failures(
    *, routing_events: list[dict[str, Any]], feedback_events: list[dict[str, Any]],
) -> dict[str, Any]:
    wrong_answer_request_ids = {
        f["request_id"] for f in feedback_events if f["feedback_type"] == "thumbs_down"
    }

    counts = {
        "no_answer": 0, "blocked_answer": 0, "timeout": 0, "low_confidence": 0,
        "wrong_answer": 0, "other_error": 0,
    }
    failed_conversation_count = 0
    for event in routing_events:
        signals: list[str] = []
        if event["resolved_route"] in NO_ANSWER_ROUTES:
            signals.append("no_answer")
        if event["route_status"] == "blocked" or event["safety_status"] in BLOCKED_SAFETY_STATUSES:
            signals.append("blocked_answer")
        error_code = (event.get("error_code") or "")
        if "timeout" in error_code.lower():
            signals.append("timeout")
        elif error_code:
            signals.append("other_error")
        if event["evidence_status"] in LOW_CONFIDENCE_EVIDENCE:
            signals.append("low_confidence")
        if event["request_id"] in wrong_answer_request_ids:
            signals.append("wrong_answer")

        for signal in signals:
            counts[signal] += 1
        if signals:
            failed_conversation_count += 1

    total = len(routing_events)
    total_failure_signals = sum(counts.values())
    return {
        "total_conversations_observed": total,
        "failure_counts": counts,
        "total_failure_signals": total_failure_signals,
        "failed_conversation_count": failed_conversation_count,
        "failure_rate": round(failed_conversation_count / total, 4) if total else None,
        "dominant_failure_category": max(counts, key=counts.get) if total_failure_signals else None,
    }
