"""MB-04C: Response Stability Checker -- compares a first generation
against its retry. Deliberately reuses MB-04B's `echo_detector` by
import (unmodified, not duplicated) for the echo check, since
detecting echo is exactly the same problem regardless of which phase
is asking -- matching the reuse pattern MB-04B itself established for
MB-04A's `language_detector`.

Honest scope: "contradiction" and "hallucination indicator" detection
here are coarse, disclosed heuristics (word-overlap ratio between the
two outputs), not real semantic/factual verification, which would
require language understanding out of scope for a non-AI phase.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.quality.echo_detector import detect_echo

LOW_OVERLAP_THRESHOLD = 0.15


def check_stability(*, first_text: str, retry_text: str, prompt_text: str = "") -> dict[str, Any]:
    issues: list[str] = []

    retry_text = retry_text or ""
    if not retry_text.strip():
        issues.append("empty_output_on_retry")

    retry_echo = detect_echo(retry_text, prompt_text=prompt_text) if retry_text else {"severity": "none"}
    if retry_echo.get("severity") == "dominant":
        issues.append("echo_persisted_on_retry")

    first_words = set((first_text or "").lower().split())
    retry_words = set(retry_text.lower().split())
    union = first_words | retry_words
    overlap_ratio = (len(first_words & retry_words) / len(union)) if union else 1.0

    # A very low word overlap between two answers to the SAME question
    # is a coarse, honest signal of instability -- not proof of a
    # factual contradiction, which this module cannot verify.
    if union and overlap_ratio < LOW_OVERLAP_THRESHOLD:
        issues.append("low_overlap_possible_instability")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "word_overlap_ratio": round(overlap_ratio, 3),
        "retry_echo_severity": retry_echo.get("severity", "none"),
    }
