"""Deterministic memorization-risk signals for instruction-tuning candidates.

Never exposes full matched training text — only counts, rates, and ratios.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


@dataclass(frozen=True)
class MemorizationThresholds:
    max_exact_match_rate: float = 0.2
    max_duplicate_output_rate: float = 0.3
    max_longest_span_ratio: float = 0.8
    max_train_validation_gap: float = 4.0
    near_zero_training_loss: float = 0.05


def exact_training_response_reproduction_rate(
    generated_texts: list[str], training_response_hashes: set[str]
) -> float:
    if not generated_texts:
        return 0.0
    matches = sum(
        1
        for text in generated_texts
        if hashlib.sha256(text.strip().encode("utf-8")).hexdigest() in training_response_hashes
    )
    return matches / len(generated_texts)


def duplicate_output_rate(generated_texts: list[str]) -> float:
    if not generated_texts:
        return 0.0
    counts = Counter(text.strip() for text in generated_texts)
    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    return duplicates / len(generated_texts)


def longest_matching_span_ratio(generated_text: str, training_responses: list[str]) -> float:
    if not generated_text or not training_responses:
        return 0.0
    best = 0
    for response in training_responses:
        matcher = SequenceMatcher(None, generated_text, response, autojunk=False)
        match = matcher.find_longest_match(0, len(generated_text), 0, len(response))
        best = max(best, match.size)
    return best / max(1, len(generated_text))


def memorization_warnings(
    *,
    generated_texts: list[str],
    training_response_hashes: set[str],
    training_responses_sample: list[str],
    train_loss: float | None,
    validation_response_loss: float | None,
    thresholds: MemorizationThresholds,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    exact_rate = exact_training_response_reproduction_rate(
        generated_texts, training_response_hashes
    )
    if exact_rate > thresholds.max_exact_match_rate:
        warnings.append(
            {
                "code": "high_exact_training_response_reproduction",
                "message": "generated held-out responses exactly reproduce training responses",
                "rate": exact_rate,
            }
        )

    dup_rate = duplicate_output_rate(generated_texts)
    if dup_rate > thresholds.max_duplicate_output_rate:
        warnings.append(
            {
                "code": "high_duplicate_output_rate",
                "message": "generated outputs duplicate each other at a high rate",
                "rate": dup_rate,
            }
        )

    if generated_texts and training_responses_sample:
        max_span_ratio = max(
            longest_matching_span_ratio(text, training_responses_sample) for text in generated_texts
        )
        if max_span_ratio > thresholds.max_longest_span_ratio:
            warnings.append(
                {
                    "code": "long_matching_span_against_training_responses",
                    "message": (
                        "generated output has a long matching span against a "
                        "training response"
                    ),
                    "span_ratio": max_span_ratio,
                }
            )

    if train_loss is not None and validation_response_loss is not None:
        gap = validation_response_loss - train_loss
        low_loss = train_loss < thresholds.near_zero_training_loss
        large_gap = gap > thresholds.max_train_validation_gap
        if low_loss and large_gap:
            warnings.append(
                {
                    "code": "low_train_high_validation_response_loss_gap",
                    "message": "near-zero training loss with a large validation response-loss gap",
                    "gap": gap,
                }
            )

    return warnings
