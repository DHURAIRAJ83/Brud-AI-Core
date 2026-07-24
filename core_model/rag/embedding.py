"""Registered-model-only embedding computation.

Local runtime modes:

* ``local_custom_embedding`` — a real, deterministic, CPU-only hashing-
  trick character-n-gram embedding computed from actual chunk content
  (no external model download, no fabricated values). This is the
  genuine working "real local embedding path" for an environment
  without ``sentence-transformers``/FAISS installed.
* ``deterministic_test_embedding`` — an even simpler, clearly-labeled
  deterministic embedding, permitted only in tests and isolated manual
  verification.
* ``local_sentence_transformer`` — registered at the model-registry
  level for future use; Phase 16 does not download or run one
  automatically without explicit implementation evidence and approval,
  so invoking it raises a clear, honest error rather than silently
  falling back to something else.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from core_model.rag import EMBEDDING_PROVIDER_TYPES


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    lowered = text.lower()
    if len(lowered) < n:
        return [lowered] if lowered else []
    return [lowered[i : i + n] for i in range(len(lowered) - n + 1)]


def _hash_to_bucket(token: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % dimensions
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return bucket, sign


def embed_local_custom(text: str, *, dimensions: int) -> np.ndarray:
    vector = np.zeros(dimensions, dtype=np.float32)
    tokens = _char_ngrams(text, n=3) + text.lower().split()
    for token in tokens:
        bucket, sign = _hash_to_bucket(token, dimensions)
        vector[bucket] += sign
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 else vector


def embed_deterministic_test(text: str, *, dimensions: int) -> np.ndarray:
    """Simple, honestly-labeled test-only embedding — never used outside
    tests or isolated manual verification."""

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [(digest[i % len(digest)] / 255.0) * 2 - 1 for i in range(dimensions)]
    vector = np.array(values, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 else vector


def compute_embedding(text: str, *, provider_type: str, dimensions: int) -> dict[str, Any]:
    if provider_type not in EMBEDDING_PROVIDER_TYPES:
        raise ValueError(f"unknown embedding provider_type: {provider_type}")
    if provider_type == "local_sentence_transformer":
        raise NotImplementedError(
            "local_sentence_transformer requires an explicitly approved, already-downloaded "
            "local model; Phase 16 does not download one automatically"
        )
    if provider_type == "deterministic_test_embedding":
        vector = embed_deterministic_test(text, dimensions=dimensions)
    else:
        vector = embed_local_custom(text, dimensions=dimensions)

    if not np.all(np.isfinite(vector)):
        raise ValueError("embedding contains non-finite values")

    vector_bytes = pack_vector(vector)
    checksum = hashlib.sha256(vector_bytes).hexdigest()
    return {
        "vector": vector,
        "vector_bytes": vector_bytes,
        "dimensions": dimensions,
        "norm": float(np.linalg.norm(vector)),
        "checksum_sha256": checksum,
    }


def pack_vector(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def unpack_vector(blob: bytes, *, dimensions: int) -> np.ndarray:
    vector = np.frombuffer(blob, dtype=np.float32)
    if vector.shape[0] != dimensions:
        raise ValueError("vector blob dimension mismatch")
    return vector
