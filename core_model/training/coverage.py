"""Deterministic per-split dataset coverage accounting for tokenizer-backed streams."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from core_model.training.dataset_stream import record_text_fields


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def generate_coverage(
    records: Iterable[dict[str, Any]],
    processor,
    *,
    eos_id: int,
    sequence_length: int,
    overlength_policy: str,
) -> dict[str, Any]:
    """Compute deterministic coverage stats for one dataset split.

    A record is ``eligible`` when it has at least one non-empty extractable text
    field. It becomes ``encoded`` when tokenization of that text produces at
    least one non-empty token sequence. Every record that is not ``encoded`` is
    ``excluded`` with a recorded reason; there is no silent drop.
    """

    total_records = 0
    eligible_records = 0
    encoded_records = 0
    zero_token_records = 0
    oversized_records = 0
    split_records = 0
    dropped_records = 0
    total_tokens = 0
    usable_tokens = 0
    padding_tokens = 0
    language_distribution: dict[str, int] = {}
    record_type_distribution: dict[str, int] = {}
    source_type_distribution: dict[str, int] = {}
    exclusion_reasons: dict[str, int] = {}
    stream_fingerprint = hashlib.sha256()

    for row in records:
        total_records += 1
        _bump(language_distribution, str(row.get("language") or "unknown"))
        _bump(record_type_distribution, str(row.get("record_type") or "unknown"))
        _bump(source_type_distribution, str(row.get("source_type") or "unknown"))

        texts = [text for text in record_text_fields(row) if text and text.strip()]
        if not texts:
            _bump(exclusion_reasons, "no_extractable_text")
            dropped_records += 1
            continue
        eligible_records += 1

        sequences: list[list[int]] = []
        for text in texts:
            ids = processor.encode(text, out_type=int)
            if eos_id >= 0:
                ids.append(eos_id)
            if ids:
                sequences.append(ids)

        if not sequences:
            zero_token_records += 1
            _bump(exclusion_reasons, "zero_token_sequence")
            dropped_records += 1
            continue

        record_oversized = any(len(seq) > sequence_length for seq in sequences)
        if record_oversized:
            oversized_records += 1
            if overlength_policy == "drop_oversized":
                sequences = [seq for seq in sequences if len(seq) <= sequence_length]
                if not sequences:
                    _bump(exclusion_reasons, "oversized_dropped")
                    dropped_records += 1
                    continue
            else:
                split_records += 1

        encoded_records += 1
        for seq in sequences:
            total_tokens += len(seq)
            usable_tokens += len(seq)
            stream_fingerprint.update(str(len(seq)).encode("utf-8"))
            for token_id in seq:
                stream_fingerprint.update(token_id.to_bytes(4, "big", signed=False))

    excluded_records = total_records - encoded_records
    block_estimate = usable_tokens // sequence_length if sequence_length else 0
    remainder = usable_tokens - block_estimate * sequence_length if sequence_length else 0
    if remainder:
        padding_tokens = sequence_length - remainder

    coverage_ratio = (usable_tokens / total_tokens) if total_tokens else 0.0
    coverage_ratio = min(1.0, max(0.0, coverage_ratio))

    return {
        "total_records": total_records,
        "eligible_records": eligible_records,
        "encoded_records": encoded_records,
        "excluded_records": excluded_records,
        "zero_token_records": zero_token_records,
        "oversized_records": oversized_records,
        "split_records": split_records,
        "dropped_records": dropped_records,
        "total_tokens": total_tokens,
        "usable_tokens": usable_tokens,
        "padding_tokens": padding_tokens,
        "language_distribution": language_distribution,
        "record_type_distribution": record_type_distribution,
        "source_type_distribution": source_type_distribution,
        "exclusion_reasons": exclusion_reasons,
        "coverage_ratio": coverage_ratio,
        "stream_checksum_sha256": stream_fingerprint.hexdigest(),
    }


def token_length_statistics(sequences: list[list[int]]) -> dict[str, Any]:
    """Phase 2.7H: min/max/average token length per real tokenized
    sequence -- one sequence per extracted text field (`record_text_fields()`),
    which is 1:1 with records for `record_type='pretrain'`. Purely
    read-only arithmetic over sequences already produced by
    `token_sequences()`; never re-tokenizes and never invents a count."""

    lengths = [len(sequence) for sequence in sequences]
    if not lengths:
        return {
            "sequence_count": 0, "min_tokens": 0, "max_tokens": 0,
            "average_tokens": 0.0, "total_tokens": 0,
        }
    total = sum(lengths)
    return {
        "sequence_count": len(lengths),
        "min_tokens": min(lengths),
        "max_tokens": max(lengths),
        "average_tokens": total / len(lengths),
        "total_tokens": total,
    }


def vocabulary_coverage(
    sequences: list[list[int]], *, vocabulary_size: int, unk_token_id: int,
) -> dict[str, Any]:
    """Phase 2.7H: how much of the tokenizer's real vocabulary this real
    dataset split actually exercises, and how often it falls back to the
    unknown-token id -- a training-data-readiness signal, never a claim
    about model quality (mission Part 5)."""

    used_token_ids: set[int] = set()
    total_tokens = 0
    unknown_tokens = 0
    for sequence in sequences:
        for token_id in sequence:
            used_token_ids.add(token_id)
            total_tokens += 1
            if token_id == unk_token_id:
                unknown_tokens += 1
    return {
        "vocabulary_size": vocabulary_size,
        "distinct_token_ids_used": len(used_token_ids),
        "vocabulary_utilization_ratio": (
            len(used_token_ids) / vocabulary_size if vocabulary_size else 0.0
        ),
        "total_tokens": total_tokens,
        "unknown_token_count": unknown_tokens,
        "unknown_token_rate": (unknown_tokens / total_tokens) if total_tokens else 0.0,
    }
