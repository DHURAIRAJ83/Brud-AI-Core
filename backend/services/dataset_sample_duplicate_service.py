"""Phase 12 Step 19 duplicate and conflict detection for quarantine
records. Never merges or deletes automatically -- every group found
here is a *candidate* for `external_dataset_sample_record_issues`
rows the human review workflow resolves.

Near-duplicate detection uses a bounded Jaccard word-shingle
similarity over the records supplied in one call only (never an
unbounded corpus-wide search), matching Step 36's CPU/RAM budget.
Comparison against an existing approved dataset/RAG corpus/evaluation
set is a thin checksum-membership check -- the caller supplies the
comparison set; this service never queries those tables itself.
"""

from __future__ import annotations

import hashlib
import re
from itertools import combinations
from typing import Any

_WHITESPACE_PATTERN = re.compile(r"\s+")
NEAR_DUPLICATE_JACCARD_THRESHOLD = 0.85


def _normalized_checksum(text: str) -> str:
    normalized = _WHITESPACE_PATTERN.sub(" ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _shingles(text: str, size: int = 3) -> set[str]:
    words = text.lower().split()
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class ExternalDatasetDuplicateService:
    def group_exact_duplicates(self, records: list[dict[str, Any]]) -> list[list[str]]:
        by_checksum: dict[str, list[str]] = {}
        for record in records:
            by_checksum.setdefault(record["record_checksum"], []).append(record["public_id"])
        return [ids for ids in by_checksum.values() if len(ids) > 1]

    def group_normalized_duplicates(self, records: list[dict[str, Any]]) -> list[list[str]]:
        by_checksum: dict[str, list[str]] = {}
        for record in records:
            checksum = _normalized_checksum(record["normalized_content"])
            by_checksum.setdefault(checksum, []).append(record["public_id"])
        return [ids for ids in by_checksum.values() if len(ids) > 1]

    def group_near_duplicates(
        self, records: list[dict[str, Any]], *, threshold: float = NEAR_DUPLICATE_JACCARD_THRESHOLD
    ) -> list[list[str]]:
        shingle_sets = [
            (record["public_id"], _shingles(record["normalized_content"])) for record in records
        ]
        parent = {public_id: public_id for public_id, _ in shingle_sets}

        def find(node: str) -> str:
            while parent[node] != node:
                node = parent[node]
            return node

        def union(a: str, b: str) -> None:
            root_a, root_b = find(a), find(b)
            if root_a != root_b:
                parent[root_a] = root_b

        for (id_a, shingles_a), (id_b, shingles_b) in combinations(shingle_sets, 2):
            if not shingles_a or not shingles_b:
                continue
            if _jaccard(shingles_a, shingles_b) >= threshold:
                union(id_a, id_b)

        groups: dict[str, list[str]] = {}
        for public_id, _ in shingle_sets:
            groups.setdefault(find(public_id), []).append(public_id)
        return [ids for ids in groups.values() if len(ids) > 1]

    @staticmethod
    def is_duplicate_against_external_set(
        record_checksum: str, external_checksums: frozenset[str]
    ) -> bool:
        return record_checksum in external_checksums

    def find_conflicts(
        self, records: list[dict[str, Any]], *, key_field: str, value_field: str
    ) -> list[dict[str, Any]]:
        """Groups records whose `structured_payload[key_field]` matches
        but whose `structured_payload[value_field]` disagrees -- the
        generic shape behind conflicting_label/conflicting_answer/
        conflicting_translation/conflicting_metadata (Step 19); the
        caller chooses which pair of fields to compare."""

        by_key: dict[Any, list[dict[str, Any]]] = {}
        for record in records:
            payload = record.get("structured_payload") or {}
            if key_field not in payload:
                continue
            by_key.setdefault(payload[key_field], []).append(record)

        conflicts: list[dict[str, Any]] = []
        for key, group in by_key.items():
            values = {
                record.get("structured_payload", {}).get(value_field)
                for record in group
                if value_field in record.get("structured_payload", {})
            }
            if len(values) > 1:
                conflicts.append(
                    {
                        "key": key,
                        "record_public_ids": [record["public_id"] for record in group],
                        "conflicting_values": sorted(str(value) for value in values),
                    }
                )
        return conflicts
