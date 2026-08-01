"""Phase 20 Step 13 -- source-conflict detection between selected,
high-quality Web evidence items.

A bounded, honest heuristic -- not a semantic fact-checker (this
codebase has no such dependency, and inventing one is out of scope).
It compares standalone numbers/version-like tokens extracted from each
selected excerpt: disjoint number sets between two independently
trusted sources discussing the same claim is treated as a genuine
signal worth disclosing, never silently resolved by picking one
source. A single selected source can never itself be "conflicting" --
conflict requires at least two.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core_model.web_search import CONFLICT_STATUSES

_NUMBER_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)*\b")


@dataclass(frozen=True)
class ConflictEvidenceItem:
    source_url: str
    trust_level: str
    freshness_status: str
    excerpt: str


@dataclass(frozen=True)
class ConflictResult:
    status: str
    conflicting_source_urls: tuple[str, ...]
    preferred_source_url: str | None
    preference_reason: str | None


def _numbers_in(text: str) -> set[str]:
    return set(_NUMBER_TOKEN_RE.findall(text))


def detect_conflict(items: list[ConflictEvidenceItem]) -> ConflictResult:
    trusted = [item for item in items if item.trust_level in ("official", "authoritative")]
    if len(trusted) < 2:
        status = "no_conflict"
        assert status in CONFLICT_STATUSES
        return ConflictResult(
            status=status,
            conflicting_source_urls=(),
            preferred_source_url=None,
            preference_reason=None,
        )

    number_sets = [(item, _numbers_in(item.excerpt)) for item in trusted]
    conflicting_pairs: list[tuple[ConflictEvidenceItem, ConflictEvidenceItem]] = []
    for i in range(len(number_sets)):
        for j in range(i + 1, len(number_sets)):
            item_a, numbers_a = number_sets[i]
            item_b, numbers_b = number_sets[j]
            if numbers_a and numbers_b and numbers_a.isdisjoint(numbers_b):
                conflicting_pairs.append((item_a, item_b))

    if not conflicting_pairs:
        freshness_values = {item.freshness_status for item in trusted}
        if (
            len(freshness_values) > 1
            and ("stale" in freshness_values or "possibly_stale" in freshness_values)
            and "fresh" in freshness_values
        ):
            status = "date_version_conflict"
            fresh_item = next(item for item in trusted if item.freshness_status == "fresh")
            return ConflictResult(
                status=status,
                conflicting_source_urls=tuple(item.source_url for item in trusted),
                preferred_source_url=fresh_item.source_url,
                preference_reason="newest_available_source",
            )
        status = "no_conflict"
        return ConflictResult(
            status=status,
            conflicting_source_urls=(),
            preferred_source_url=None,
            preference_reason=None,
        )

    conflicting_urls = tuple(
        sorted({item.source_url for pair in conflicting_pairs for item in pair})
    )

    freshness_of_conflicting = {
        item.source_url: item.freshness_status for pair in conflicting_pairs for item in pair
    }
    fresh_urls = [url for url, status in freshness_of_conflicting.items() if status == "fresh"]
    stale_urls = [
        url
        for url, status in freshness_of_conflicting.items()
        if status in ("stale", "possibly_stale")
    ]
    if fresh_urls and stale_urls and len(fresh_urls) == 1:
        return ConflictResult(
            status="material_conflict",
            conflicting_source_urls=conflicting_urls,
            preferred_source_url=fresh_urls[0],
            preference_reason="only_source_with_current_freshness",
        )

    return ConflictResult(
        status="unresolved_conflict",
        conflicting_source_urls=conflicting_urls,
        preferred_source_url=None,
        preference_reason=None,
    )


__all__ = ["ConflictEvidenceItem", "ConflictResult", "detect_conflict"]
