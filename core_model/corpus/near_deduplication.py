"""Deterministic, CPU-bounded near-duplicate detection.

Every method here is exact-arithmetic deterministic (fixed hash seeds,
no ``random`` module calls) -- the same pair of texts always produces
the same similarity score, and no large external similarity service is
ever called.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

_TOKEN_PATTERN = re.compile(r"[\w஀-௿]+")

# Fixed, explicit seeds for MinHash's hash-family simulation -- never
# ``random``, so results are perfectly reproducible across runs.
_MINHASH_SEEDS = tuple(range(1, 33))


def _tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def character_ngrams(text: str, *, n: int = 3) -> set[str]:
    collapsed = " ".join(text.split())
    if len(collapsed) < n:
        return {collapsed} if collapsed else set()
    return {collapsed[i : i + n] for i in range(len(collapsed) - n + 1)}


def token_ngrams(text: str, *, n: int = 2) -> set[tuple[str, ...]]:
    tokens = _tokens(text)
    if len(tokens) < n:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def character_ngram_jaccard(text_a: str, text_b: str, *, n: int = 3) -> float:
    return jaccard_similarity(character_ngrams(text_a, n=n), character_ngrams(text_b, n=n))


def token_ngram_jaccard(text_a: str, text_b: str, *, n: int = 2) -> float:
    return jaccard_similarity(token_ngrams(text_a, n=n), token_ngrams(text_b, n=n))


def _seeded_hash(value: str, seed: int) -> int:
    digest = hashlib.md5(f"{seed}:{value}".encode()).hexdigest()
    return int(digest, 16)


def minhash_signature(text: str, *, num_hashes: int = 32, shingle_size: int = 3) -> tuple[int, ...]:
    shingles = character_ngrams(text, n=shingle_size)
    if not shingles:
        return tuple(0 for _ in range(num_hashes))
    return tuple(
        min(_seeded_hash(shingle, seed) for shingle in shingles)
        for seed in _MINHASH_SEEDS[:num_hashes]
    )


def minhash_similarity(signature_a: tuple[int, ...], signature_b: tuple[int, ...]) -> float:
    if not signature_a or len(signature_a) != len(signature_b):
        return 0.0
    matches = sum(1 for a, b in zip(signature_a, signature_b, strict=True) if a == b)
    return matches / len(signature_a)


def simhash(text: str, *, num_bits: int = 64, shingle_size: int = 3) -> int:
    shingles = character_ngrams(text, n=shingle_size)
    if not shingles:
        return 0
    bit_weights = [0] * num_bits
    for shingle in shingles:
        digest = int(hashlib.md5(shingle.encode("utf-8")).hexdigest(), 16)
        for bit in range(num_bits):
            bit_weights[bit] += 1 if (digest >> bit) & 1 else -1
    fingerprint = 0
    for bit in range(num_bits):
        if bit_weights[bit] > 0:
            fingerprint |= 1 << bit
    return fingerprint


def simhash_similarity(hash_a: int, hash_b: int, *, num_bits: int = 64) -> float:
    hamming_distance = bin(hash_a ^ hash_b).count("1")
    return 1 - (hamming_distance / num_bits)


_METHODS = {
    "character_ngram_jaccard": character_ngram_jaccard,
    "token_ngram_jaccard": token_ngram_jaccard,
}


def compute_similarity(text_a: str, text_b: str, *, method: str) -> float:
    if method in _METHODS:
        return _METHODS[method](text_a, text_b)
    if method == "minhash":
        return minhash_similarity(minhash_signature(text_a), minhash_signature(text_b))
    if method == "simhash":
        return simhash_similarity(simhash(text_a), simhash(text_b))
    raise ValueError(f"unsupported near-duplicate method: {method}")


def classify_near_duplicate(similarity: float, *, threshold: float) -> str:
    return "near_duplicate" if similarity >= threshold else "unique"


def select_representative(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic representative selection, preferring in order:
    approved licence, higher extraction confidence, better Unicode
    quality, lower OCR noise, more complete provenance, more complete
    text, earlier canonical source, then a stable public-ID tie-break.
    Never random."""

    def sort_key(candidate: dict[str, Any]) -> tuple:
        return (
            0 if candidate.get("licence_status") == "approved" else 1,
            -(candidate.get("extraction_confidence") or 0),
            0 if candidate.get("unicode_integrity_status") == "valid" else 1,
            candidate.get("ocr_corrections_applied", 0),
            0 if candidate.get("provenance_complete") else 1,
            -(candidate.get("character_count") or 0),
            candidate.get("source_created_at") or "",
            candidate.get("public_id") or "",
        )

    return sorted(candidates, key=sort_key)[0]
