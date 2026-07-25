"""Corpus quality scoring across 17 dimensions, assessed at five
subject levels (source, document, segment, collection, build).

Every dimension result distinguishes a measured fact (e.g. an actual
Unicode-integrity scan result) from a heuristic score (e.g. domain
value) -- callers must not present a heuristic as a hard measurement.
"""

from __future__ import annotations

from typing import Any

from core_model.corpus import QUALITY_DIMENSIONS

# Dimensions backed by a deterministic measurement rather than a
# heuristic judgment call -- surfaced separately so reports never
# blur the two together.
MEASURED_DIMENSIONS = frozenset(
    {
        "unicode_integrity", "tamil_integrity", "ocr_quality", "sentence_completeness",
        "language_confidence", "privacy_safety", "safety_quality", "licence_completeness",
        "provenance_completeness", "length_quality", "format_integrity",
    }
)
HEURISTIC_DIMENSIONS = frozenset(QUALITY_DIMENSIONS) - MEASURED_DIMENSIONS


def assess_segment_quality(
    *,
    unicode_integrity_status: str,
    tamil_combining_marks_preserved: bool,
    ocr_corrections_applied: int,
    character_count: int,
    sentence_count: int,
    language_confidence: float,
    boilerplate_removed_ratio: float,
    duplicate_status: str,
    privacy_status: str,
    safety_status: str,
    licence_status: str,
    provenance_complete: bool,
    minimum_segment_characters: int,
    maximum_ocr_noise_ratio: float,
    minimum_language_confidence: float,
) -> dict[str, str]:
    """Returns one pass/warning/fail/not_assessed status per dimension."""

    result: dict[str, str] = dict.fromkeys(QUALITY_DIMENSIONS, "not_assessed")

    result["unicode_integrity"] = "fail" if unicode_integrity_status not in {"valid"} else "pass"
    result["tamil_integrity"] = "pass" if tamil_combining_marks_preserved else "fail"

    ocr_noise_ratio = ocr_corrections_applied / max(1, character_count // 100)
    result["ocr_quality"] = (
        "fail" if ocr_noise_ratio > maximum_ocr_noise_ratio
        else "warning" if ocr_corrections_applied > 0
        else "pass"
    )
    result["sentence_completeness"] = "pass" if sentence_count > 0 else "warning"
    result["language_confidence"] = (
        "fail" if language_confidence == 0
        else "warning" if language_confidence < minimum_language_confidence
        else "pass"
    )
    result["content_density"] = "pass" if character_count >= minimum_segment_characters else "fail"
    result["length_quality"] = result["content_density"]
    result["boilerplate_ratio"] = (
        "warning" if boilerplate_removed_ratio > 0.3 else "pass"
    )
    result["duplicate_risk"] = "warning" if duplicate_status != "unique" else "pass"
    result["privacy_safety"] = (
        "fail" if privacy_status == "blocked"
        else "warning" if privacy_status != "safe"
        else "pass"
    )
    result["safety_quality"] = (
        "fail" if safety_status == "blocked"
        else "warning" if safety_status != "safe"
        else "pass"
    )
    result["licence_completeness"] = (
        "fail" if licence_status in {"unknown", "blocked"}
        else "warning" if licence_status == "restricted"
        else "pass"
    )
    result["provenance_completeness"] = "pass" if provenance_complete else "fail"
    result["format_integrity"] = "pass" if character_count > 0 else "fail"
    result["readability"] = "not_assessed"
    result["domain_value"] = "not_assessed"
    result["style_value"] = "not_assessed"

    return result


def overall_verdict(dimension_results: dict[str, str]) -> str:
    if any(status == "fail" for status in dimension_results.values()):
        return "fail"
    if any(status == "warning" for status in dimension_results.values()):
        return "warning"
    return "pass"


def quality_band(dimension_results: dict[str, str]) -> str:
    verdict = overall_verdict(dimension_results)
    if verdict == "fail":
        return "low"
    if verdict == "warning":
        return "medium"
    return "high"


def build_quality_details(measurements: dict[str, Any]) -> dict[str, Any]:
    """Separates measured facts from heuristic scores explicitly for
    report/manifest consumers."""

    return {
        "measured": {k: v for k, v in measurements.items() if k in MEASURED_DIMENSIONS},
        "heuristic": {k: v for k, v in measurements.items() if k in HEURISTIC_DIMENSIONS},
    }
