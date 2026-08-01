"""Phase 19 Step 11/12 -- deterministic, explainable priority scoring.

A weighted sum over evidence-based factors, never a fabricated
value -- every point added or subtracted carries its own reason code
so `priority_reason_codes` is a complete, auditable explanation of the
final `priority_score`. Step 12's Tamil-first boost is gated by an
explicit, disjoint reason-code allowlist
(`TAMIL_FIRST_PRIORITY_REASON_CODES`) so a Tamil *current-affairs*
question (freshness-driven, not a language-capability gap) never
receives it -- see `test_tamil_current_affairs_does_not_get_tamil_boost`
for the regression test proving this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from core_model.knowledge_gap import PRIORITY_BANDS, TAMIL_FIRST_PRIORITY_REASON_CODES

_RECENCY_BANDS = (
    (1, 10, "recency_within_1_day"),
    (7, 6, "recency_within_1_week"),
    (30, 3, "recency_within_1_month"),
)

_EVENT_TYPE_FAILURE_WEIGHT = {
    "knowledge_gap": 8,
    "language_failure": 7,
    "web_capability_gap": 5,
    "tool_capability_gap": 5,
    "source_failure": 4,
    "operational_failure": 2,
    "feedback_issue": 4,
}

_FEEDBACK_SEVERITY_WEIGHT = {
    "unsafe_answer": 10,
    "wrong_answer": 8,
    "missing_evidence": 6,
    "source_conflict": 6,
    "stale_information": 5,
    "wrong_language": 5,
    "unknown_question": 4,
    "unhelpful": 2,
}


@dataclass(frozen=True)
class PriorityInput:
    event_type: str
    reason_codes: tuple[str, ...]
    frequency: int
    last_seen_at: datetime
    negative_feedback_reasons: tuple[str, ...] = field(default_factory=tuple)
    repeated_rag_failure_count: int = 0
    repeated_wrong_language_count: int = 0
    is_duplicate_uncertain: bool = False
    privacy_risk: bool = False
    reproducible: bool = True
    has_available_source: bool = True


@dataclass(frozen=True)
class PriorityResult:
    priority_score: float
    priority_band: str
    priority_reason_codes: tuple[str, ...]


def _band_for_score(score: float) -> str:
    if score >= 30:
        return "critical"
    if score >= 20:
        return "high"
    if score >= 10:
        return "medium"
    if score >= 3:
        return "low"
    return "informational"


class KnowledgeGapPriorityService:
    def score(
        self, priority_input: PriorityInput, *, now: datetime | None = None
    ) -> PriorityResult:
        now = now or datetime.now(UTC)
        score = 0.0
        reasons: list[str] = []

        frequency_points = min(priority_input.frequency, 20) * 0.75
        if frequency_points:
            score += frequency_points
            reasons.append("frequency_weighted")

        age_days = max((now - priority_input.last_seen_at).total_seconds() / 86400, 0)
        for max_days, points, reason in _RECENCY_BANDS:
            if age_days <= max_days:
                score += points
                reasons.append(reason)
                break

        for reason_code in priority_input.negative_feedback_reasons:
            weight = _FEEDBACK_SEVERITY_WEIGHT.get(reason_code, 1)
            score += weight
            reasons.append(f"feedback_severity_{reason_code}")

        failure_weight = _EVENT_TYPE_FAILURE_WEIGHT.get(priority_input.event_type, 1)
        score += failure_weight
        reasons.append(f"route_failure_severity_{priority_input.event_type}")

        if priority_input.repeated_rag_failure_count > 1:
            score += min(priority_input.repeated_rag_failure_count, 5) * 2
            reasons.append("repeated_rag_failure")

        if priority_input.repeated_wrong_language_count > 1:
            score += min(priority_input.repeated_wrong_language_count, 5) * 2
            reasons.append("repeated_wrong_language_failure")

        if any(code in TAMIL_FIRST_PRIORITY_REASON_CODES for code in priority_input.reason_codes):
            score += 6
            reasons.append("TAMIL_FIRST_PRIORITY_APPLIED")

        if priority_input.is_duplicate_uncertain:
            score -= 4
            reasons.append("penalty_duplicate_uncertainty")

        if priority_input.privacy_risk:
            score -= 6
            reasons.append("penalty_privacy_risk")

        if not priority_input.reproducible:
            score -= 5
            reasons.append("penalty_low_reproducibility")

        if not priority_input.has_available_source and priority_input.event_type == "knowledge_gap":
            score -= 2
            reasons.append("penalty_no_available_source")

        score = max(score, 0.0)
        band = _band_for_score(score)
        assert band in PRIORITY_BANDS
        return PriorityResult(
            priority_score=round(score, 2), priority_band=band, priority_reason_codes=tuple(reasons)
        )


__all__ = ["KnowledgeGapPriorityService", "PriorityInput", "PriorityResult"]
