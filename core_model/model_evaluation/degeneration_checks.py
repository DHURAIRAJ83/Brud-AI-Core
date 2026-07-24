"""Repetition and degenerate-generation checks.

Reuses Phase 12's ``no_excessive_repetition``/``valid_unicode``/
``eos_termination`` and ``duplicate_output_rate`` directly rather than
duplicating them; adds token-loop and phrase-loop detection, which Phase 12
did not need (its fixtures were plain sentences, not adversarial-repetition
probes).
"""

from __future__ import annotations

from collections import Counter

from core_model.instruction_tuning.evaluation import (
    eos_termination,
    no_excessive_repetition,
    valid_unicode,
)
from core_model.instruction_tuning.memorization_checks import duplicate_output_rate


def token_loop_detected(text: str, *, min_run_length: int = 5) -> dict:
    tokens = text.split()
    if len(tokens) < min_run_length:
        return {"check": "token_loop_detected", "status": "pass", "run_length": 0}
    longest_run = 1
    current_run = 1
    for index in range(1, len(tokens)):
        if tokens[index] == tokens[index - 1]:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    detected = longest_run >= min_run_length
    status = "fail" if detected else "pass"
    return {"check": "token_loop_detected", "status": status, "run_length": longest_run}


def phrase_loop_detected(text: str, *, phrase_size: int = 3, min_repeats: int = 3) -> dict:
    tokens = text.split()
    if len(tokens) < phrase_size * min_repeats:
        return {"check": "phrase_loop_detected", "status": "pass", "max_repeats": 0}
    phrases = [
        tuple(tokens[i : i + phrase_size]) for i in range(len(tokens) - phrase_size + 1)
    ]
    counts = Counter(phrases)
    max_repeats = max(counts.values()) if counts else 0
    detected = max_repeats >= min_repeats
    status = "fail" if detected else "pass"
    return {"check": "phrase_loop_detected", "status": status, "max_repeats": max_repeats}


def eos_termination_failure_rate(stop_reasons: list[str]) -> float | None:
    if not stop_reasons:
        return None
    failures = sum(1 for reason in stop_reasons if reason != "eos")
    return failures / len(stop_reasons)


def evaluate_degeneration(text: str, *, max_repeat_ratio: float = 0.3) -> dict:
    return {
        "repetition": no_excessive_repetition(text, max_repeat_ratio=max_repeat_ratio),
        "token_loop": token_loop_detected(text),
        "phrase_loop": phrase_loop_detected(text),
        "valid_unicode": valid_unicode(text),
    }


def evaluate_run_level_degeneration(
    generated_texts: list[str], stop_reasons: list[str]
) -> dict:
    return {
        "duplicate_output_rate": duplicate_output_rate(generated_texts),
        "eos_termination_failure_rate": eos_termination_failure_rate(stop_reasons),
        "eos_terminations": [eos_termination(reason) for reason in stop_reasons],
    }


def generic_response_collapse(generated_texts: list[str], *, max_unique_ratio: float = 0.3) -> dict:
    """Same response across many unrelated prompts — a run-level collapse signal."""

    if not generated_texts:
        return {"status": "not_evaluated", "unique_ratio": None}
    unique_ratio = len(set(text.strip() for text in generated_texts)) / len(generated_texts)
    return {
        "status": "fail" if unique_ratio < max_unique_ratio else "pass",
        "unique_ratio": unique_ratio,
    }
