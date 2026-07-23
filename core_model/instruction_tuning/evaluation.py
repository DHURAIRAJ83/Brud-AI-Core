"""Deterministic instruction-following evaluation checks.

None of these prove factual correctness — they check structural/behavioral
properties only: emptiness, role/prompt leakage, repetition, length,
Unicode validity, EOS termination, and bounded exact-reproduction rate.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from difflib import SequenceMatcher
from typing import Any

ROLE_TOKENS = ("<system>", "<user>", "<assistant>")


def response_not_empty(text: str) -> dict[str, Any]:
    ok = bool(text.strip())
    message = "response is non-empty" if ok else "response is empty"
    return {"status": "pass" if ok else "fail", "message": message}


def no_role_token_leakage(text: str) -> dict[str, Any]:
    leaked = [token for token in ROLE_TOKENS if token in text]
    return {
        "status": "fail" if leaked else "pass",
        "message": f"role tokens leaked: {leaked}" if leaked else "no role tokens in response",
        "leaked_tokens": leaked,
    }


def _longest_common_substring_length(left: str, right: str) -> int:
    if not left or not right:
        return 0
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    match = matcher.find_longest_match(0, len(left), 0, len(right))
    return match.size


def no_system_prompt_leakage(
    text: str, system_text: str | None, user_text: str | None, *, min_match_chars: int = 20
) -> dict[str, Any]:
    system_match = _longest_common_substring_length(text, system_text or "")
    user_match = _longest_common_substring_length(text, user_text or "")
    leaked = system_match >= min_match_chars or user_match >= min_match_chars
    message = "prompt content copied into response" if leaked else "no prompt leakage detected"
    return {
        "status": "fail" if leaked else "pass",
        "message": message,
        "system_match_chars": system_match,
        "user_match_chars": user_match,
    }


def no_excessive_repetition(text: str, *, max_repeat_ratio: float = 0.5) -> dict[str, Any]:
    tokens = text.split()
    if not tokens:
        return {
            "status": "pass",
            "message": "empty response has no repetition",
            "repetition_ratio": 0.0,
        }
    counts = Counter(tokens)
    most_common_count = counts.most_common(1)[0][1]
    ratio = most_common_count / len(tokens)
    return {
        "status": "warning" if ratio > max_repeat_ratio else "pass",
        "message": f"most-repeated token ratio {ratio:.2f}",
        "repetition_ratio": ratio,
    }


def bounded_length(text: str, *, max_chars: int) -> dict[str, Any]:
    ok = len(text) <= max_chars
    return {
        "status": "pass" if ok else "warning",
        "message": f"response length {len(text)} chars",
        "length": len(text),
    }


def valid_unicode(text: str) -> dict[str, Any]:
    try:
        text.encode("utf-8").decode("utf-8")
        ok = True
    except UnicodeError:
        ok = False
    message = "valid unicode" if ok else "invalid unicode"
    return {"status": "pass" if ok else "fail", "message": message}


def eos_termination(stopped_reason: str) -> dict[str, Any]:
    ok = stopped_reason == "eos"
    return {
        "status": "pass" if ok else "warning",
        "message": f"generation stopped due to: {stopped_reason}",
        "stopped_reason": stopped_reason,
    }


def training_response_exact_match_rate_bounded(
    generated_texts: list[str], training_response_hashes: set[str], *, max_rate: float
) -> dict[str, Any]:
    if not generated_texts:
        return {"status": "pass", "message": "no generated samples to check", "rate": 0.0}
    matches = sum(
        1
        for text in generated_texts
        if hashlib.sha256(text.strip().encode("utf-8")).hexdigest() in training_response_hashes
    )
    rate = matches / len(generated_texts)
    return {
        "status": "warning" if rate > max_rate else "pass",
        "message": f"exact training-response reproduction rate {rate:.2f}",
        "rate": rate,
    }


def validation_loss_finite(loss: float | None) -> dict[str, Any]:
    ok = loss is not None and math.isfinite(loss)
    message = (
        "validation response loss is finite"
        if ok
        else "validation response loss missing or non-finite"
    )
    return {"status": "pass" if ok else "fail", "message": message, "loss": loss}
