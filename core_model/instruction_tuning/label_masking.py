"""Response-only label masking — the core Phase 12 correctness guarantee.

Builds ``input_ids``/``attention_mask``/``labels`` of identical shape where
every position except the assistant-response tokens is ``ignore_index``. The
existing causal-LM shift (``core_model.training.loss.causal_lm_loss``) is
reused unmodified: it shifts ``labels`` by one position internally, so no
shift logic belongs here — only correct construction of the unshifted labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TRUNCATION_POLICIES = ("reject", "truncate_prompt_first", "truncate_response_tail")


@dataclass(frozen=True)
class LabelMaskingThresholds:
    sequence_length: int
    ignore_index: int = -100
    truncation_policy: str = "truncate_prompt_first"


def _rejected(reason: str) -> dict[str, Any]:
    return {
        "rejected": True,
        "reject_reason": reason,
        "input_ids": None,
        "attention_mask": None,
        "labels": None,
        "prompt_token_count": 0,
        "target_token_count": 0,
        "truncated": False,
        "truncation_kind": None,
    }


def build_response_labeled_example(
    prompt_token_ids: list[int],
    response_token_ids: list[int],
    *,
    pad_token_id: int,
    eos_token_id: int,
    thresholds: LabelMaskingThresholds,
) -> dict[str, Any]:
    """Build one response-only-labeled training example.

    ``prompt_token_ids`` covers everything up to and including the assistant
    role marker (system + user + assistant-prefix tokens); ``response_token_ids``
    covers only the actual assistant response (optionally including EOS).
    Both are masked with ``ignore_index`` in ``labels`` except the response
    span, which keeps its real token ids as trainable targets.
    """

    if thresholds.truncation_policy not in TRUNCATION_POLICIES:
        return _rejected("unknown_truncation_policy")

    prompt_ids = list(prompt_token_ids)
    response_ids = list(response_token_ids)
    truncated = False
    truncation_kind = None
    total_length = len(prompt_ids) + len(response_ids)

    if total_length > thresholds.sequence_length:
        if thresholds.truncation_policy == "reject":
            return _rejected("sequence_too_long")

        if thresholds.truncation_policy == "truncate_prompt_first":
            allowed_prompt_len = thresholds.sequence_length - len(response_ids)
            if allowed_prompt_len <= 0:
                if thresholds.sequence_length < 1:
                    return _rejected("sequence_length_too_small")
                response_ids = response_ids[: thresholds.sequence_length]
                prompt_ids = []
            elif allowed_prompt_len < len(prompt_ids):
                prompt_ids = prompt_ids[-allowed_prompt_len:]
            truncated = True
            truncation_kind = "truncate_prompt_first"

        else:  # truncate_response_tail
            allowed_response_len = thresholds.sequence_length - len(prompt_ids)
            if allowed_response_len < 1:
                return _rejected("truncation_would_remove_all_targets")
            has_eos = bool(response_ids) and response_ids[-1] == eos_token_id
            if has_eos and allowed_response_len >= 2:
                response_ids = response_ids[: allowed_response_len - 1] + [eos_token_id]
            else:
                response_ids = response_ids[:allowed_response_len]
            truncated = True
            truncation_kind = "truncate_response_tail"

    input_ids = prompt_ids + response_ids
    labels = [thresholds.ignore_index] * len(prompt_ids) + list(response_ids)
    if not any(value != thresholds.ignore_index for value in labels):
        return _rejected("zero_target_tokens")

    pad_len = thresholds.sequence_length - len(input_ids)
    if pad_len < 0:
        return _rejected("sequence_too_long")
    input_ids = input_ids + [pad_token_id] * pad_len
    attention_mask = [1] * (len(prompt_ids) + len(response_ids)) + [0] * pad_len
    labels = labels + [thresholds.ignore_index] * pad_len
    target_token_count = sum(1 for value in labels if value != thresholds.ignore_index)

    return {
        "rejected": False,
        "reject_reason": None,
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels,
        "prompt_token_count": len(prompt_ids),
        "target_token_count": target_token_count,
        "truncated": truncated,
        "truncation_kind": truncation_kind,
    }
