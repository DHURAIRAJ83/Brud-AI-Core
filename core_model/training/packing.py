"""Partial-block policy and manifest bookkeeping layered on top of ``packed_blocks``."""

from __future__ import annotations

from typing import Any

from core_model.training.dataset_stream import packed_blocks


def pack_stream(
    sequences: list[list[int]],
    *,
    sequence_length: int,
    pad_token_id: int,
    overlength_policy: str,
    partial_block_policy: str = "pad",
) -> dict[str, Any]:
    """Pack token sequences into fixed-length blocks with an explicit partial-block policy.

    ``packed_blocks`` always pads a trailing partial block; when
    ``partial_block_policy == "drop"`` that same trailing block is discarded
    here instead, so no synthetic padding tokens ever reach the trainer.
    """

    if partial_block_policy not in {"pad", "drop"}:
        raise ValueError("partial_block_policy must be 'pad' or 'drop'")
    if overlength_policy == "drop_oversized":
        eligible_token_count = sum(len(seq) for seq in sequences if len(seq) <= sequence_length)
    else:
        eligible_token_count = sum(len(seq) for seq in sequences)
    blocks = packed_blocks(
        sequences,
        sequence_length=sequence_length,
        pad_token_id=pad_token_id,
        policy=overlength_policy,
    )
    remainder = (eligible_token_count % sequence_length) if sequence_length else 0
    padding_tokens = (sequence_length - remainder) if remainder else 0
    dropped_final_block = False
    usable_tokens = eligible_token_count
    if partial_block_policy == "drop" and remainder and blocks:
        blocks = blocks[:-1]
        padding_tokens = 0
        dropped_final_block = True
        usable_tokens = eligible_token_count - remainder
    return {
        "blocks": blocks,
        "block_count": len(blocks),
        "usable_tokens": usable_tokens,
        "padding_tokens": padding_tokens,
        "dropped_final_block": dropped_final_block,
    }
