"""MB-04B: Echo Cleaner -- mechanically removes a detected verbatim
overlap from a response. Deliberately conservative: it only ever
REMOVES the exact substring the Echo Detector already found:
- never invents replacement text (nothing is ever inserted)
- never touches the response if no verbatim overlap was found
  (a label-only echo has no `overlap_text` to safely remove -- the
  matched words are ordinary English words like "Task" that could
  legitimately appear in a real answer, so removing them would risk
  deleting real content)
- if nothing meaningful survives the removal, that is reported
  honestly (`insufficient_after_cleaning`) rather than backfilled
  with fabricated text
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.quality.echo_detector import detect_echo

MIN_MEANINGFUL_REMAINDER_CHARS = 20
MAX_CLEANING_PASSES = 3


def clean_echo(response_text: str, *, echo_diagnostics: dict[str, Any]) -> dict[str, Any]:
    response_text = response_text or ""
    overlap_text = echo_diagnostics.get("overlap_text") or ""

    if not overlap_text:
        return {
            "cleaned_text": response_text,
            "removed": False,
            "removed_chars": 0,
            "insufficient_after_cleaning": False,
        }

    remainder = response_text.replace(overlap_text, "", 1)
    # Collapse whitespace left behind by the removal -- plain str
    # operations, no regex.
    cleaned = " ".join(remainder.split())

    insufficient = len(cleaned) < MIN_MEANINGFUL_REMAINDER_CHARS

    return {
        "cleaned_text": cleaned if not insufficient else "",
        "removed": True,
        "removed_chars": len(overlap_text),
        "insufficient_after_cleaning": insufficient,
        "original_text": response_text,
    }


def clean_echo_iteratively(response_text: str, *, prompt_text: str) -> dict[str, Any]:
    """A single response can echo more than one disjoint fragment of
    the prompt (verified directly against real MB-04A benchmark data --
    a response echoed both the Response Format text AND a separate
    Confidence/language-directive fragment). Repeatedly detects and
    removes the current largest verbatim overlap, capped at
    `MAX_CLEANING_PASSES` -- bounded and safe: each pass can only
    shrink the text, and the loop stops the moment no overlap at or
    above the detector's own threshold remains."""

    current = response_text or ""
    total_removed_chars = 0
    passes = 0

    for _ in range(MAX_CLEANING_PASSES):
        echo = detect_echo(current, prompt_text=prompt_text)
        # Stop once there is no MEANINGFUL overlap left, not merely
        # "no overlap at all" -- almost any two texts share some tiny
        # coincidental substring, which would otherwise keep the loop
        # running until the pass cap on completely unrelated text.
        if not echo.get("echo_detected") or not echo.get("overlap_text"):
            break
        result = clean_echo(current, echo_diagnostics=echo)
        if not result["removed"]:
            break
        passes += 1
        total_removed_chars += result["removed_chars"]
        if result["insufficient_after_cleaning"]:
            return {
                "cleaned_text": "",
                "removed": True,
                "removed_chars": total_removed_chars,
                "insufficient_after_cleaning": True,
                "original_text": response_text,
                "passes": passes,
            }
        current = result["cleaned_text"]

    return {
        "cleaned_text": current,
        "removed": passes > 0,
        "removed_chars": total_removed_chars,
        "insufficient_after_cleaning": False,
        "original_text": response_text,
        "passes": passes,
    }
