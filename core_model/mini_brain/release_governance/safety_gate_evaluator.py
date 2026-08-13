"""MB-20: Safety Gate Evaluator -- pure. Ten deterministic checks
against already-computed upstream signals (MB-17's own hallucination
report, MB-19's own benchmark reports, MB-18's own package-integrity
verification). Every threshold is a fixed, documented constant below,
never a hidden or learned value. Any failed gate blocks release
readiness -- this module never overrides that with a partial score.
"""

from __future__ import annotations

from typing import Any

GROUNDING_QUALITY_THRESHOLD = 60.0
HALLUCINATION_RISK_THRESHOLD = 0.3
OCR_CONFLICT_THRESHOLD = 0.3
UNSUPPORTED_SENTENCE_THRESHOLD = 0.4
MISSING_ARTIFACT_THRESHOLD = 0
UNICODE_INTEGRITY_THRESHOLD = 70.0
TAMIL_VALIDITY_THRESHOLD = 70.0
DUPLICATE_COUNT_THRESHOLD = 5
ACCEPTABLE_RELEASE_RISK_LEVELS = ("low", "medium", "unknown")

THRESHOLDS = {
    "grounding_quality_threshold": GROUNDING_QUALITY_THRESHOLD,
    "hallucination_risk_threshold": HALLUCINATION_RISK_THRESHOLD,
    "ocr_conflict_threshold": OCR_CONFLICT_THRESHOLD,
    "unsupported_sentence_threshold": UNSUPPORTED_SENTENCE_THRESHOLD,
    "missing_artifact_threshold": MISSING_ARTIFACT_THRESHOLD,
    "unicode_integrity_threshold": UNICODE_INTEGRITY_THRESHOLD,
    "tamil_validity_threshold": TAMIL_VALIDITY_THRESHOLD,
    "duplicate_count_threshold": DUPLICATE_COUNT_THRESHOLD,
    "acceptable_release_risk_levels": list(ACCEPTABLE_RELEASE_RISK_LEVELS),
}


def _gate(name: str, passed: bool, reason: str | None) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "reason": None if passed else reason}


def run_safety_gates(
    *, grounding_composite_score: float | None, hallucination_risk: float | None,
    ocr_conflict_ratio: float | None, unsupported_sentence_ratio: float | None,
    package_integrity_ok: bool, missing_artifact_count: int, unicode_integrity: float | None,
    tamil_character_validity: float | None, duplicate_count: int, release_risk_level: str,
) -> dict[str, Any]:
    gates = [
        _gate(
            "grounding_quality", grounding_composite_score is None or grounding_composite_score >= GROUNDING_QUALITY_THRESHOLD,
            f"grounding quality {grounding_composite_score} is below {GROUNDING_QUALITY_THRESHOLD}",
        ),
        _gate(
            "hallucination_risk", hallucination_risk is None or hallucination_risk <= HALLUCINATION_RISK_THRESHOLD,
            f"hallucination risk {hallucination_risk} exceeds {HALLUCINATION_RISK_THRESHOLD}",
        ),
        _gate(
            "ocr_conflict", ocr_conflict_ratio is None or ocr_conflict_ratio <= OCR_CONFLICT_THRESHOLD,
            f"OCR conflict rate {ocr_conflict_ratio} exceeds {OCR_CONFLICT_THRESHOLD}",
        ),
        _gate(
            "unsupported_sentence_ratio",
            unsupported_sentence_ratio is None or unsupported_sentence_ratio <= UNSUPPORTED_SENTENCE_THRESHOLD,
            f"unsupported sentence ratio {unsupported_sentence_ratio} exceeds {UNSUPPORTED_SENTENCE_THRESHOLD}",
        ),
        _gate("package_integrity", package_integrity_ok, "package integrity check failed"),
        _gate(
            "missing_artifact_count", missing_artifact_count <= MISSING_ARTIFACT_THRESHOLD,
            f"{missing_artifact_count} missing/corrupt artifact file(s) detected",
        ),
        _gate(
            "unicode_integrity", unicode_integrity is None or unicode_integrity >= UNICODE_INTEGRITY_THRESHOLD,
            f"Unicode integrity {unicode_integrity} is below {UNICODE_INTEGRITY_THRESHOLD}",
        ),
        _gate(
            "tamil_character_validity",
            tamil_character_validity is None or tamil_character_validity >= TAMIL_VALIDITY_THRESHOLD,
            f"Tamil character validity {tamil_character_validity} is below {TAMIL_VALIDITY_THRESHOLD}",
        ),
        _gate(
            "duplicate_risk", duplicate_count <= DUPLICATE_COUNT_THRESHOLD,
            f"{duplicate_count} exact duplicate(s) exceed the threshold of {DUPLICATE_COUNT_THRESHOLD}",
        ),
        _gate(
            "release_risk_level", release_risk_level in ACCEPTABLE_RELEASE_RISK_LEVELS,
            f"release risk level '{release_risk_level}' is not in the acceptable set {list(ACCEPTABLE_RELEASE_RISK_LEVELS)}",
        ),
    ]
    blocking_reasons = [gate["reason"] for gate in gates if gate["status"] == "fail"]

    return {
        "gates": gates,
        "passed_count": sum(1 for g in gates if g["status"] == "pass"),
        "failed_count": sum(1 for g in gates if g["status"] == "fail"),
        "overall_status": "pass" if not blocking_reasons else "fail",
        "blocking_reasons": blocking_reasons,
        "thresholds": THRESHOLDS,
        "disclosure": (
            "every threshold above is a fixed governance heuristic, never calibrated against a real "
            "production incident -- a passing safety gate does not guarantee production safety"
        ),
    }
