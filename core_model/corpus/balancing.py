"""Corpus balancing.

Balance targets are configurable goals, never automatic truth: this
module only ever selects a subset of already-eligible segments,
reports gaps, and caps overrepresentation -- it never fabricates a
record and never duplicates a record to inflate a category.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def compute_actual_distribution(segments: list[dict[str, Any]], *, key: str) -> dict[str, float]:
    counts = Counter(segment[key] for segment in segments)
    total = sum(counts.values()) or 1
    return {category: count / total for category, count in counts.items()}


def compare_to_targets(
    actual: dict[str, float], targets: dict[str, tuple[float, float]]
) -> dict[str, Any]:
    """``targets`` maps category -> (minimum_share, maximum_share).
    Returns per-category status: ``within_target`` /
    ``underrepresented`` / ``overrepresented`` / ``untargeted``."""

    report = {}
    for category, (minimum, maximum) in targets.items():
        share = actual.get(category, 0.0)
        if share < minimum:
            status = "underrepresented"
        elif share > maximum:
            status = "overrepresented"
        else:
            status = "within_target"
        report[category] = {
            "actual_share": share, "target_range": [minimum, maximum], "status": status,
        }
    for category, share in actual.items():
        if category not in targets:
            report[category] = {"actual_share": share, "target_range": None, "status": "untargeted"}
    return report


def cap_source_share(
    segments: list[dict[str, Any]], *, source_key: str, maximum_single_source_share: float
) -> dict[str, Any]:
    """Deterministically excludes the excess segments from any source
    exceeding ``maximum_single_source_share`` -- keeping the earliest
    (by stable sort order) segments up to the cap, never a random
    sample."""

    source_counts = Counter(segment[source_key] for segment in segments)
    total = len(segments) or 1
    cap_count = {
        source: int(maximum_single_source_share * total)
        for source, count in source_counts.items()
        if count / total > maximum_single_source_share
    }
    if not cap_count:
        return {"included": segments, "excluded": [], "capped_sources": {}}

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    running_counts: Counter[str] = Counter()
    for segment in segments:
        source = segment[source_key]
        if source in cap_count and running_counts[source] >= cap_count[source]:
            excluded.append(segment)
            continue
        running_counts[source] += 1
        included.append(segment)

    return {"included": included, "excluded": excluded, "capped_sources": cap_count}


def source_diversity_report(segments: list[dict[str, Any]], *, source_key: str) -> dict[str, Any]:
    counts = Counter(segment[source_key] for segment in segments)
    total = sum(counts.values()) or 1
    shares = {source: count / total for source, count in counts.items()}
    dominant = max(shares.items(), key=lambda item: item[1]) if shares else (None, 0.0)
    return {
        "distinct_sources": len(counts),
        "shares": shares,
        "most_dominant_source": dominant[0],
        "most_dominant_share": dominant[1],
    }
