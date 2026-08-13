"""MB-08: Feedback Collector -- pure. Summarizes already-fetched,
already-privacy-filtered Public Chat routing and feedback events. Never
fetches anything itself and never sees raw conversation text -- both
event tables it summarizes store only hashes and structured
classification outputs, never question/answer content.

Honest scope: Public Chat's own `feedback_type` enum
(thumbs_up/thumbs_down/language_report/safety_report) is reused
directly. The separate, older "Feedback & Improvement" admin system
(`backend.services.feedback_service`, a richer
like/dislike/wrong_answer/... taxonomy for admin-curated dataset
improvement) is a different system this module does not read from --
conflating the two would misattribute one system's signal to another.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

UNANSWERED_ROUTES = frozenset({"clarify", "refuse", "insufficient"})


def collect_feedback(
    *, routing_events: list[dict[str, Any]], feedback_events: list[dict[str, Any]],
) -> dict[str, Any]:
    total_conversations = len(routing_events)
    unanswered = sum(1 for e in routing_events if e["resolved_route"] in UNANSWERED_ROUTES)
    blocked = sum(1 for e in routing_events if e["route_status"] == "blocked")

    feedback_by_type = Counter(f["feedback_type"] for f in feedback_events)
    total_feedback = len(feedback_events)
    positive = feedback_by_type.get("thumbs_up", 0)
    negative = feedback_by_type.get("thumbs_down", 0)

    return {
        "total_conversations_observed": total_conversations,
        "unanswered_count": unanswered,
        "unanswered_rate": round(unanswered / total_conversations, 4) if total_conversations else None,
        "blocked_count": blocked,
        "total_feedback_events": total_feedback,
        "feedback_by_type": dict(feedback_by_type),
        "positive_feedback_count": positive,
        "negative_feedback_count": negative,
        "negative_feedback_rate": round(negative / total_feedback, 4) if total_feedback else None,
    }
