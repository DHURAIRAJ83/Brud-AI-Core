"""Deterministic dataset-version token stream."""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from typing import Any


def record_text_fields(row: dict[str, Any]) -> list[str]:
    record_type = row.get("record_type")
    if record_type == "pretrain":
        return [row.get("input_text") or row.get("output_text") or row.get("content") or ""]
    if record_type == "instruction":
        return [
            row.get("instruction") or "",
            row.get("input_text") or "",
            row.get("output_text") or "",
        ]
    if record_type in {"chat", "translation", "safety", "preference"}:
        return [row.get("input_text") or "", row.get("output_text") or ""]
    if record_type == "tanglish_pair":
        return [
            row.get("input_text") or "",
            row.get("normalized_input") or "",
            row.get("output_text") or "",
        ]
    return [row.get("content") or ""]


def token_sequences(
    records: Iterable[dict[str, Any]], processor, eos_id: int
) -> tuple[list[list[int]], dict[str, int]]:
    sequences: list[list[int]] = []
    counts = {"empty": 0, "records": 0, "sequences": 0}
    for row in records:
        counts["records"] += 1
        for text in record_text_fields(row):
            if not text or not text.strip():
                counts["empty"] += 1
                continue
            ids = processor.encode(text, out_type=int)
            if eos_id >= 0:
                ids.append(eos_id)
            if ids:
                sequences.append(ids)
    counts["sequences"] = len(sequences)
    return sequences, counts


def packed_blocks(
    sequences: list[list[int]],
    *,
    sequence_length: int,
    pad_token_id: int,
    policy: str,
) -> list[list[int]]:
    blocks: list[list[int]] = []
    if policy == "drop_oversized":
        eligible = [seq for seq in sequences if len(seq) <= sequence_length]
    else:
        eligible = []
        for seq in sequences:
            eligible.extend(
                seq[i : i + sequence_length] for i in range(0, len(seq), sequence_length)
            )
    stream = list(itertools.chain.from_iterable(eligible))
    for start in range(0, len(stream), sequence_length):
        block = stream[start : start + sequence_length]
        if len(block) < sequence_length:
            block = block + [pad_token_id] * (sequence_length - len(block))
        blocks.append(block)
    return blocks
