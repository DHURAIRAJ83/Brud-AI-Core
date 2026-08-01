"""Phase 20 Step 10 -- `WebFreshnessEvaluationService`.

A pure function over already-extracted date metadata and the source
policy's per-category thresholds -- never guesses a date that was not
actually present in the fetched content. Undated content is never
promoted to "fresh" just because a query needs current information;
the honest result in that case is `undated`, which the caller (Step
11's verification service) then factors into the achieved
verification level.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core_model.web_search import FRESHNESS_RESULTS


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def evaluate_freshness(
    *,
    published_at: str | None,
    updated_at: str | None,
    category: str,
    freshness_thresholds: dict[str, dict[str, Any]],
    reference_time: datetime | None = None,
) -> str:
    reference = reference_time or datetime.now(UTC)
    most_recent = None
    for candidate in (_parse_date(updated_at), _parse_date(published_at)):
        if candidate is not None and (most_recent is None or candidate > most_recent):
            most_recent = candidate

    if most_recent is None:
        result = "undated"
        assert result in FRESHNESS_RESULTS
        return result

    age_days = (reference - most_recent).total_seconds() / 86400.0
    thresholds = freshness_thresholds.get(category, {"fresh_days": 180, "possibly_stale_days": 365})
    fresh_days = thresholds.get("fresh_days", 180)
    possibly_stale_days = thresholds.get("possibly_stale_days", 365)

    if age_days < 0:
        # A future-dated document is treated conservatively as
        # possibly_stale rather than trusted as "fresh" -- clock skew
        # or a fabricated date are both plausible, and neither should
        # be rewarded with the strongest freshness label.
        result = "possibly_stale"
    elif age_days <= fresh_days:
        result = "fresh"
    elif age_days <= possibly_stale_days:
        result = "possibly_stale"
    else:
        result = "stale"

    assert result in FRESHNESS_RESULTS
    return result


def overall_freshness(per_source_results: list[str]) -> str:
    """Combines multiple selected evidence items' freshness into one
    response-level status. `conflicting` only ever comes from here --
    never assigned to a single source in isolation."""

    unique = set(per_source_results)
    if not unique:
        return "undated"
    if len(unique) == 1:
        return unique.pop()
    if "fresh" in unique and ("stale" in unique or "possibly_stale" in unique):
        return "conflicting"
    if "stale" in unique:
        return "stale"
    if "possibly_stale" in unique:
        return "possibly_stale"
    return "undated"


__all__ = ["evaluate_freshness", "overall_freshness"]
