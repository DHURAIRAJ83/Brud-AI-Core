"""Phase 2.7G: the one canonical dataset-version -> token-block
representation, extracted from `PretrainingService._blocks()` (Phase 9)
so it can be called by more than one caller with an identical result --
never a second, divergent implementation.

`fetch_split_records()` is the exact query `PretrainingService._blocks()`
already used, unchanged. `build_split_blocks()` wraps the exact same
sequence: `token_sequences()` -> `_validate_token_ids` (inlined, a plain
range check) -> `pack_stream()` -> `generate_coverage()`, for one split.
`build_dataset_blocks()` composes both splits and raises the exact same
typed errors `PretrainingService._blocks()` already raised for an empty
split.

Deterministic and side-effect-free: no randomness anywhere in this
module, and no database write -- callers own persistence (job-scoped
provenance, checkpoint references, etc.).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.database.repositories.base import ValidationError
from core_model.architecture.config import BrudModelConfig
from core_model.training.coverage import generate_coverage, token_length_statistics, vocabulary_coverage
from core_model.training.dataset_stream import token_sequences
from core_model.training.packing import pack_stream

# Bumped only when this module's own tokenization/packing *policy*
# changes in a way that would change output for the same inputs (never
# for a pure refactor) -- persisted into checkpoint references so a
# fresh process can tell which block-construction rules produced a
# given checkpoint (Phase 2.7G, mission Part 14).
BLOCK_BUILDER_VERSION = "dataset_pipeline_v1"


def fetch_split_records(
    connection: sqlite3.Connection, dataset_version_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The exact query `PretrainingService._blocks()` always used --
    every approved, governed record already assigned to this dataset
    version's train/validation/test split by the real
    `DatasetVersioningService.run_build()` (leakage-checked, dedup-checked,
    quality-filtered *before* this query ever runs -- this function does
    not re-implement or second-guess that governance, it only reads its
    already-committed result)."""

    rows = connection.execute(
        """SELECT r.*,i.split
        FROM dataset_version_items i
        JOIN dataset_records r ON r.id=i.dataset_record_id
        WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
        (dataset_version_id,),
    ).fetchall()
    train, valid = [], []
    for row in rows:
        if row["split"] == "test":
            continue
        target = train if row["split"] == "train" else valid
        target.append(dict(row))
    return train, valid


def validate_token_ids(sequences: list[list[int]], vocabulary_size: int) -> None:
    for sequence in sequences:
        if any(token < 0 or token >= vocabulary_size for token in sequence):
            raise ValidationError("token id outside core model vocabulary")


def build_split_blocks(
    records: list[dict[str, Any]], *, processor, model_config: BrudModelConfig,
    sequence_length: int, overlength_policy: str, split_name: str,
) -> dict[str, Any]:
    """One split's real tokenization + packing + coverage -- the same
    three real, deterministic functions `PretrainingService._blocks()`
    already calls (`token_sequences`, `pack_stream`, `generate_coverage`),
    just factored so a second caller can reach them without a
    `pretraining_jobs` row."""

    sequences, counts = token_sequences(records, processor, model_config.eos_token_id)
    validate_token_ids(sequences, model_config.vocabulary_size)
    packed = pack_stream(
        sequences, sequence_length=sequence_length, pad_token_id=model_config.pad_token_id,
        overlength_policy=overlength_policy, partial_block_policy="pad",
    )
    coverage = generate_coverage(
        records, processor, eos_id=model_config.eos_token_id,
        sequence_length=sequence_length, overlength_policy=overlength_policy,
    )
    # Phase 2.7H (Part 4/5): derived from the exact `sequences` this split
    # already tokenized above -- no second tokenization pass, no invented
    # statistic.
    token_length_stats = token_length_statistics(sequences)
    vocab_coverage = vocabulary_coverage(
        sequences, vocabulary_size=model_config.vocabulary_size, unk_token_id=model_config.unk_token_id,
    )
    return {
        "split": split_name, "sequence_counts": counts, "packed": packed, "coverage": coverage,
        "token_length_stats": token_length_stats, "vocabulary_coverage": vocab_coverage,
    }


def build_dataset_blocks(
    connection: sqlite3.Connection, dataset_version_id: int, *, processor,
    model_config: BrudModelConfig, sequence_length: int, overlength_policy: str,
) -> dict[str, Any]:
    """The full, canonical dataset-version -> token-block pipeline for
    one dataset version + tokenizer + model config + packing policy.
    Raises the exact same typed `ValidationError`s
    `PretrainingService._blocks()` already raised for an empty split --
    never a silent empty-blocks result."""

    train_records, valid_records = fetch_split_records(connection, dataset_version_id)
    train = build_split_blocks(
        train_records, processor=processor, model_config=model_config,
        sequence_length=sequence_length, overlength_policy=overlength_policy, split_name="train",
    )
    validation = build_split_blocks(
        valid_records, processor=processor, model_config=model_config,
        sequence_length=sequence_length, overlength_policy=overlength_policy, split_name="validation",
    )
    if not train["packed"]["blocks"]:
        raise ValidationError("training split has no tokenized records")
    if not validation["packed"]["blocks"]:
        raise ValidationError("validation split has no tokenized records")
    return {
        "train": train, "validation": validation,
        "train_records": train_records, "validation_records": valid_records,
        "block_builder_version": BLOCK_BUILDER_VERSION,
    }


__all__ = [
    "BLOCK_BUILDER_VERSION",
    "fetch_split_records",
    "validate_token_ids",
    "build_split_blocks",
    "build_dataset_blocks",
]
