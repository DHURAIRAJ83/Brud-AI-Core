"""Phase 19 Step 9/10 -- conservative duplicate clustering.

Reuses `ExternalDatasetDuplicateService` (Phase 12) verbatim for all
three matching layers -- exact checksum, normalized checksum, and
bounded Jaccard word-shingle near-duplicates. The only new logic here
is the domain/intent/freshness compatibility bucket applied *before*
candidates are even compared: this is what keeps "Python latest stable
version" (`intent=ask_current_status`) and "Python version means what"
(`intent=ask_definition`) in separate clusters without any bespoke
similarity math -- they are simply never compared against each other.

Per Step 9's explicit rule, only `same_case` (exact) and
`probable_duplicate` (normalized) may auto-merge; a `possible_duplicate`
(Jaccard match) always requires Admin review.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from backend.services.dataset_sample_duplicate_service import (
    NEAR_DUPLICATE_JACCARD_THRESHOLD,
    ExternalDatasetDuplicateService,
)

MAX_CANDIDATES_PER_BUCKET = 200


@dataclass(frozen=True)
class ClusterCandidate:
    case_public_id: str
    canonical_question: str
    language: str
    domain: str | None
    intent: str | None
    freshness: str | None


@dataclass(frozen=True)
class ClusterDecision:
    case_public_id: str
    matched_case_public_id: str
    decision: str


def _bucket_key(candidate: ClusterCandidate) -> tuple[str | None, str | None, str | None]:
    # Deliberately excludes `language` -- a Tamil-suffixed question
    # ("Python latest stable version என்ன?") and its plain-English
    # equivalent ("latest Python version?") share the same domain/
    # intent/freshness and enough English-token overlap for the
    # Jaccard pass to catch them (Step 7's own worked example says
    # these "may cluster together"). `domain`+`intent` already keeps
    # genuinely unrelated questions apart regardless of language.
    return (candidate.domain, candidate.intent, candidate.freshness)


class KnowledgeGapClusteringService:
    def __init__(self) -> None:
        self._duplicates = ExternalDatasetDuplicateService()

    def find_cluster_decisions(
        self, candidates: list[ClusterCandidate]
    ) -> list[ClusterDecision]:
        """Bounded, CPU-first: candidates are bucketed by
        (language, domain, intent) first, and each bucket is capped at
        `MAX_CANDIDATES_PER_BUCKET` -- never an unbounded full-table
        pairwise scan (Step 33)."""

        buckets: dict[tuple[str, str | None, str | None], list[ClusterCandidate]] = {}
        for candidate in candidates:
            bucket = buckets.setdefault(_bucket_key(candidate), [])
            if len(bucket) < MAX_CANDIDATES_PER_BUCKET:
                bucket.append(candidate)

        decisions: list[ClusterDecision] = []
        for bucket in buckets.values():
            if len(bucket) < 2:
                continue
            decisions.extend(self._decide_within_bucket(bucket))
        return decisions

    def _decide_within_bucket(
        self, bucket: list[ClusterCandidate]
    ) -> list[ClusterDecision]:
        records = [
            {
                "public_id": candidate.case_public_id,
                "record_checksum": _exact_checksum(candidate.canonical_question),
                "normalized_content": candidate.canonical_question,
            }
            for candidate in bucket
        ]

        exact_groups = self._duplicates.group_exact_duplicates(records)
        normalized_groups = self._duplicates.group_normalized_duplicates(records)
        near_groups = self._duplicates.group_near_duplicates(
            records, threshold=NEAR_DUPLICATE_JACCARD_THRESHOLD
        )

        decisions: list[ClusterDecision] = []
        already_decided: set[str] = set()
        for group in exact_groups:
            decisions.extend(_pairwise(group, "same_case"))
            already_decided.update(group)
        for group in normalized_groups:
            remaining = [item for item in group if item not in already_decided]
            if len(remaining) > 1:
                decisions.extend(_pairwise(remaining, "probable_duplicate"))
                already_decided.update(remaining)
        for group in near_groups:
            remaining = [item for item in group if item not in already_decided]
            if len(remaining) > 1:
                decisions.extend(_pairwise(remaining, "possible_duplicate"))
                already_decided.update(remaining)
        return decisions


def _exact_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pairwise(group: list[str], decision: str) -> list[ClusterDecision]:
    anchor = group[0]
    return [
        ClusterDecision(case_public_id=member, matched_case_public_id=anchor, decision=decision)
        for member in group[1:]
    ]


__all__ = ["ClusterCandidate", "ClusterDecision", "KnowledgeGapClusteringService"]
