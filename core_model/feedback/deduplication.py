"""Dataset-candidate duplicate detection.

Reuses Phase 16's ``core_model.rag.chunk_validation.near_duplicate_ratio``
(``difflib.SequenceMatcher``-based) unchanged rather than a second
similarity implementation.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.chunk_validation import near_duplicate_ratio
from core_model.rag.text_normalization import content_checksum

DEFAULT_NEAR_DUPLICATE_THRESHOLD = 0.9


def normalize_for_comparison(text: str) -> str:
    """Lowercase-Latin, whitespace-collapsed form used only for
    duplicate comparison -- the original text is never overwritten."""

    collapsed = " ".join(text.strip().split())
    return "".join(char.lower() if "A" <= char <= "Z" else char for char in collapsed)


def checksum_of(text: str) -> str:
    return content_checksum(text)


def detect_duplicate(
    *,
    prompt_text: str,
    output_text: str,
    existing_records: list[dict[str, str]],
    near_duplicate_threshold: float = DEFAULT_NEAR_DUPLICATE_THRESHOLD,
) -> dict[str, Any]:
    """``existing_records`` is a list of ``{"prompt_text": ..., "output_text": ...,
    "reference": ...}`` drawn from dataset records, other feedback
    candidates, instruction-tuning records, evaluation fixtures, or
    regression fixtures -- whatever the caller is checking against for
    this pass. Returns the single most specific duplicate status found."""

    combined = f"{prompt_text}\n{output_text}"
    combined_checksum = checksum_of(normalize_for_comparison(combined))
    prompt_checksum = checksum_of(normalize_for_comparison(prompt_text))
    output_checksum = checksum_of(normalize_for_comparison(output_text))

    for record in existing_records:
        existing_combined = f"{record['prompt_text']}\n{record['output_text']}"
        if existing_combined == combined:
            return {
                "status": "exact_duplicate",
                "matched_reference": record.get("reference"),
                "ratio": 1.0,
            }
        existing_combined_checksum = checksum_of(normalize_for_comparison(existing_combined))
        if existing_combined_checksum == combined_checksum:
            return {
                "status": "normalized_duplicate",
                "matched_reference": record.get("reference"),
                "ratio": 1.0,
            }

    prompt_match = None
    output_match = None
    for record in existing_records:
        if checksum_of(normalize_for_comparison(record["prompt_text"])) == prompt_checksum:
            prompt_match = record
        if checksum_of(normalize_for_comparison(record["output_text"])) == output_checksum:
            output_match = record
    if prompt_match is not None and output_match is not None:
        return {
            "status": "prompt_response_duplicate",
            "matched_reference": prompt_match.get("reference"),
            "ratio": 1.0,
        }
    if prompt_match is not None:
        return {
            "status": "prompt_duplicate",
            "matched_reference": prompt_match.get("reference"),
            "ratio": 1.0,
        }
    if output_match is not None:
        return {
            "status": "response_duplicate",
            "matched_reference": output_match.get("reference"),
            "ratio": 1.0,
        }

    best_ratio = 0.0
    best_reference = None
    normalized_combined = normalize_for_comparison(combined)
    for record in existing_records:
        existing_combined = normalize_for_comparison(
            f"{record['prompt_text']}\n{record['output_text']}"
        )
        ratio = near_duplicate_ratio(normalized_combined, existing_combined)
        if ratio > best_ratio:
            best_ratio = ratio
            best_reference = record.get("reference")
    if best_ratio >= near_duplicate_threshold:
        return {
            "status": "near_duplicate",
            "matched_reference": best_reference,
            "ratio": best_ratio,
        }

    return {"status": "unique", "matched_reference": None, "ratio": best_ratio}
