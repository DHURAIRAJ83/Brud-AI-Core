"""Deterministic fixture structural validation and checksums.

Fixtures are hand-authored via the admin API, not hardcoded in this
codebase (unlike Phase 11/12's fixed evaluation sentences) — this module
validates and checksums whatever an admin submits, it does not supply
fixture content itself.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from backend.core.json_utils import dumps_json
from core_model.model_evaluation import FIXTURE_CATEGORIES, LANGUAGES


@dataclass(frozen=True)
class FixtureValidationThresholds:
    max_prompt_chars: int = 2000
    max_system_prompt_chars: int = 2000
    max_reference_chars: int = 4000
    max_new_tokens_ceiling: int = 128


def validate_fixture(
    payload: dict[str, Any], thresholds: FixtureValidationThresholds
) -> dict[str, Any]:
    """Validate one fixture submission.

    Returns {"valid": bool, "reason": str|None, "warnings": [...]}.
    """

    category = payload.get("category")
    language = payload.get("language")
    prompt = (payload.get("prompt") or "").strip()

    if category not in FIXTURE_CATEGORIES:
        return {"valid": False, "reason": "invalid_category", "warnings": []}
    if language not in LANGUAGES:
        return {"valid": False, "reason": "invalid_language", "warnings": []}
    if not prompt:
        return {"valid": False, "reason": "missing_prompt", "warnings": []}
    if len(prompt) > thresholds.max_prompt_chars:
        return {"valid": False, "reason": "prompt_too_long", "warnings": []}
    system_prompt = payload.get("system_prompt")
    if system_prompt and len(system_prompt) > thresholds.max_system_prompt_chars:
        return {"valid": False, "reason": "system_prompt_too_long", "warnings": []}
    reference_answer = payload.get("reference_answer")
    if reference_answer and len(reference_answer) > thresholds.max_reference_chars:
        return {"valid": False, "reason": "reference_answer_too_long", "warnings": []}
    max_new_tokens = payload.get("max_new_tokens", 32)
    if not isinstance(max_new_tokens, int) or max_new_tokens < 1:
        return {"valid": False, "reason": "invalid_max_new_tokens", "warnings": []}
    if max_new_tokens > thresholds.max_new_tokens_ceiling:
        return {"valid": False, "reason": "max_new_tokens_exceeds_ceiling", "warnings": []}

    warnings: list[str] = []
    if payload.get("refusal_expected") and category not in {
        "safety_refusal", "unsafe_instruction_handling",
    }:
        warnings.append("refusal_expected_outside_safety_category")
    if category in {"translation", "classification", "definition"} and not payload.get(
        "expected_format"
    ):
        warnings.append("missing_expected_format_for_structured_category")
    if category in {"safety_refusal", "unsafe_instruction_handling"} and not payload.get(
        "severity"
    ):
        warnings.append("missing_severity_for_safety_category")

    return {"valid": True, "reason": None, "warnings": warnings}


_CHECKSUM_FIELDS = (
    "category", "language", "prompt", "system_prompt", "expected_response_language",
    "expected_format", "expected_keywords", "forbidden_keywords", "reference_answer",
    "reference_facts", "refusal_expected", "max_new_tokens", "timeout_seconds", "severity",
)


def fixture_checksum(payload: dict[str, Any]) -> str:
    canonical = {field: payload.get(field) for field in _CHECKSUM_FIELDS}
    return hashlib.sha256(dumps_json(canonical).encode("utf-8")).hexdigest()


def fixture_set_checksum(fixture_checksums: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(fixture_checksums)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FixtureCoverageThresholds:
    min_total_fixtures: int = 50
    preferred_total_fixtures: int = 325  # 100+50+50+50+50+25 per the spec's recommended counts
    min_tamil_fixtures: int = 100
    min_english_fixtures: int = 50
    min_tanglish_fixtures: int = 50
    min_mixed_fixtures: int = 50
    min_safety_fixtures: int = 50
    min_robustness_fixtures: int = 25


def evaluation_sufficiency_status(
    total_fixtures: int, thresholds: FixtureCoverageThresholds
) -> str:
    if total_fixtures >= thresholds.preferred_total_fixtures:
        return "sufficient"
    if total_fixtures >= thresholds.min_total_fixtures:
        return "limited_evaluation"
    return "insufficient"


def coverage_warnings(
    language_counts: dict[str, int],
    category_counts: dict[str, int],
    thresholds: FixtureCoverageThresholds,
) -> list[dict[str, str]]:
    """Non-blocking, honest coverage warnings — never fabricates fixtures."""

    warnings: list[dict[str, str]] = []
    checks = (
        ("ta", thresholds.min_tamil_fixtures, "too_few_tamil_fixtures"),
        ("en", thresholds.min_english_fixtures, "too_few_english_fixtures"),
        ("tgl", thresholds.min_tanglish_fixtures, "too_few_tanglish_fixtures"),
        ("mixed", thresholds.min_mixed_fixtures, "too_few_mixed_fixtures"),
    )
    for language, minimum, code in checks:
        count = language_counts.get(language, 0)
        if count == 0:
            warnings.append({
                "code": f"missing_{language}_coverage",
                "message": f"no fixtures for language {language}",
            })
        elif count < minimum:
            warnings.append({
                "code": code,
                "message": f"only {count} fixtures for language {language} (recommended {minimum})",
            })
    safety_count = category_counts.get("safety_refusal", 0) + category_counts.get(
        "unsafe_instruction_handling", 0
    )
    if safety_count < thresholds.min_safety_fixtures:
        warnings.append({
            "code": "too_few_safety_fixtures",
            "message": (
                f"only {safety_count} safety fixtures "
                f"(recommended {thresholds.min_safety_fixtures})"
            ),
        })
    robustness_count = category_counts.get("robustness", 0)
    if robustness_count < thresholds.min_robustness_fixtures:
        warnings.append({
            "code": "too_few_robustness_fixtures",
            "message": (
                f"only {robustness_count} robustness fixtures "
                f"(recommended {thresholds.min_robustness_fixtures})"
            ),
        })
    return warnings
