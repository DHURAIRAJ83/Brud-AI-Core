"""Deterministic train/validation/test partitioning.

Partitioning is source-aware, duplicate-cluster-aware, and
document-family-aware: every segment from the same near-duplicate
cluster or the same source document always lands in the same split,
so no split ever leaks a duplicate or a document-family member across
its boundary. The seed is always explicit and the resulting assignment
is always checksummed for tamper detection.
"""

from __future__ import annotations

import hashlib
from typing import Any

DEFAULT_PROPORTIONS = {"train": 0.98, "validation": 0.01, "test": 0.01}


def _stable_bucket(key: str, *, seed: int, buckets: int = 10_000) -> int:
    digest = hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()
    return int(digest, 16) % buckets


def assign_partitions(
    groups: list[dict[str, Any]],
    *,
    seed: int = 42,
    proportions: dict[str, float] | None = None,
) -> dict[str, list[str]]:
    """``groups`` is a list of ``{"group_key": ..., "segment_public_ids": [...]}``
    -- a group is a duplicate cluster or a source-document family, so
    every segment in it is assigned to the same split atomically.
    Returns ``{"train": [...], "validation": [...], "test": [...]}`` of
    segment public IDs."""

    proportions = proportions or DEFAULT_PROPORTIONS
    train_cutoff = int(proportions["train"] * 10_000)
    validation_cutoff = train_cutoff + int(proportions["validation"] * 10_000)

    assignment: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for group in sorted(groups, key=lambda g: g["group_key"]):
        bucket = _stable_bucket(group["group_key"], seed=seed)
        split = (
            "train" if bucket < train_cutoff
            else "validation" if bucket < validation_cutoff
            else "test"
        )
        assignment[split].extend(group["segment_public_ids"])
    return assignment


def partition_checksum(assignment: dict[str, list[str]]) -> str:
    parts = []
    for split in ("train", "validation", "test"):
        parts.append(f"{split}:{','.join(sorted(assignment.get(split, [])))}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def verify_partition_isolation(
    assignment: dict[str, list[str]],
    *,
    duplicate_clusters: list[list[str]],
    evaluation_fixture_ids: frozenset[str] = frozenset(),
    regression_fixture_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Returns violations found -- never a bare boolean, so the caller
    can report exactly what leaked and block finalization accordingly."""

    violations: list[dict[str, Any]] = []
    membership = {
        segment_id: split
        for split, segment_ids in assignment.items()
        for segment_id in segment_ids
    }

    for cluster in duplicate_clusters:
        splits_seen = {membership[seg_id] for seg_id in cluster if seg_id in membership}
        if len(splits_seen) > 1:
            violations.append({"type": "duplicate_cluster_split_leakage", "cluster": cluster})

    train_ids = set(assignment.get("train", []))
    fixture_leakage = train_ids & (evaluation_fixture_ids | regression_fixture_ids)
    if fixture_leakage:
        violations.append({"type": "fixture_in_training", "segment_ids": sorted(fixture_leakage)})

    return {"isolated": not violations, "violations": violations}
