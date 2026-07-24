"""Deterministic, CPU-local flat vector index.

No FAISS dependency is installed in this environment, so this module
implements a repository-compatible brute-force flat index computed
directly over already-registered chunk embeddings — genuinely real
scoring, never fabricated similarity. Path confinement for any on-disk
index artifact is reused unchanged from Phase 14/15
(``core_model.release.artifact_inventory.resolve_confined_path``), not
re-implemented.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from core_model.release.artifact_inventory import resolve_confined_path

__all__ = [
    "resolve_confined_path",
    "build_mapping_manifest",
    "mapping_checksum",
    "validate_vector_index_inputs",
    "score_vectors",
    "normalize_scores",
    "top_k_by_score",
]


def build_mapping_manifest(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """``entries``: [{"chunk_public_id":..., "vector_checksum_sha256":...}].
    Sorted deterministically by chunk_public_id for a stable checksum."""

    sorted_entries = sorted(entries, key=lambda entry: entry["chunk_public_id"])
    return {"count": len(sorted_entries), "entries": sorted_entries}


def mapping_checksum(manifest: dict[str, Any]) -> str:
    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_vector_index_inputs(
    *,
    vector_count: int,
    mapping_count: int,
    dimensions: int,
    embedding_dimensions: int,
    quarantined_or_rejected_count: int,
) -> list[str]:
    errors = []
    if vector_count != mapping_count:
        errors.append("vector count does not equal mapping count")
    if dimensions != embedding_dimensions:
        errors.append("index dimensions do not match embedding model dimensions")
    if quarantined_or_rejected_count > 0:
        errors.append("rejected or quarantined chunks present in embedding set")
    return errors


def score_vectors(
    query_vector: np.ndarray, candidate_vectors: list[np.ndarray], *, distance_metric: str
) -> list[float]:
    if distance_metric == "cosine":
        q_norm = float(np.linalg.norm(query_vector)) + 1e-9
        return [
            float(np.dot(query_vector, vector) / (q_norm * (float(np.linalg.norm(vector)) + 1e-9)))
            for vector in candidate_vectors
        ]
    if distance_metric == "inner_product":
        return [float(np.dot(query_vector, vector)) for vector in candidate_vectors]
    if distance_metric == "l2":
        return [float(-np.linalg.norm(query_vector - vector)) for vector in candidate_vectors]
    raise ValueError(f"unknown distance metric: {distance_metric}")


def normalize_scores(scores: list[float]) -> list[float]:
    """Bounded 0..1 min-max normalization for combining with other signals —
    never a claim of probability calibration."""

    if not scores:
        return []
    lowest, highest = min(scores), max(scores)
    if highest - lowest < 1e-9:
        return [0.5 for _ in scores]
    return [(score - lowest) / (highest - lowest) for score in scores]


def top_k_by_score(
    candidate_ids: list[str], scores: list[float], *, k: int
) -> list[tuple[str, float]]:
    """Deterministic tie-break: highest score first, then candidate_id
    ascending — never hidden random ranking."""

    paired = list(zip(candidate_ids, scores, strict=True))
    paired.sort(key=lambda pair: (-pair[1], pair[0]))
    return paired[:k]
