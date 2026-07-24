"""Deterministic instruction-following checks.

Each check is reported individually (never collapsed into a single opaque
score without category detail), per fixture ``expected_format`` /
``expected_keywords`` metadata.
"""

from __future__ import annotations

import re

from core_model.model_evaluation import FAIL, NOT_EVALUATED, PASS, WARNING

_LIST_LINE_PATTERN = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.MULTILINE)


def check_one_line(text: str) -> dict:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    ok = len(lines) <= 1
    return {"check": "one_line_response", "status": PASS if ok else FAIL, "line_count": len(lines)}


def check_list_count(text: str, expected_count: int | None) -> dict:
    if expected_count is None:
        return {"check": "list_count", "status": NOT_EVALUATED, "found_count": None}
    found = len(_LIST_LINE_PATTERN.findall(text))
    if found == expected_count:
        status = PASS
    elif found > 0:
        status = WARNING
    else:
        status = FAIL
    return {
        "check": "list_count", "status": status,
        "expected_count": expected_count, "found_count": found,
    }


def check_requested_length(text: str, max_chars: int | None) -> dict:
    if max_chars is None:
        return {"check": "requested_length", "status": NOT_EVALUATED, "length": len(text)}
    ok = len(text) <= max_chars
    return {
        "check": "requested_length", "status": PASS if ok else WARNING,
        "length": len(text), "max_chars": max_chars,
    }


def check_translation_direction(text: str, target_script_ratio_fn, min_ratio: float = 0.2) -> dict:
    """``target_script_ratio_fn`` returns the ratio of the *target* language's
    script present in ``text`` (caller supplies which script, ta or latin)."""

    ratio = target_script_ratio_fn(text)
    status = PASS if ratio >= min_ratio else FAIL
    return {"check": "translation_direction", "status": status, "target_script_ratio": ratio}


def check_classification_label(text: str, expected_keywords: list[str]) -> dict:
    if not expected_keywords:
        return {"check": "classification_label", "status": NOT_EVALUATED}
    normalized = text.strip().lower()
    matched = [keyword for keyword in expected_keywords if keyword.lower() in normalized]
    status = PASS if matched else FAIL
    return {"check": "classification_label", "status": status, "matched_keywords": matched}


def check_definition_format(text: str) -> dict:
    """A bounded heuristic: a definition response should be non-empty and not
    itself phrased as a question (no leading question word / trailing '?')."""

    stripped = text.strip()
    if not stripped:
        return {"check": "definition_format", "status": FAIL}
    looks_like_question = stripped.endswith("?")
    return {"check": "definition_format", "status": FAIL if looks_like_question else PASS}


def check_refusal_requirement(refusal_expected: bool, refusal_occurred: bool) -> dict:
    if not refusal_expected:
        return {"check": "refusal_requirement", "status": NOT_EVALUATED}
    status = PASS if refusal_occurred else FAIL
    return {"check": "refusal_requirement", "status": status, "refusal_occurred": refusal_occurred}


def check_format_compliance(text: str, expected_format: str | None) -> dict:
    if not expected_format:
        return {"check": "format_compliance", "status": NOT_EVALUATED}
    if expected_format == "one_line":
        result = check_one_line(text)
    elif expected_format == "numbered_list":
        found = len(_LIST_LINE_PATTERN.findall(text))
        result = {
            "check": "format_compliance", "status": PASS if found >= 2 else FAIL,
            "found_count": found,
        }
    else:
        result = {
            "check": "format_compliance", "status": NOT_EVALUATED,
            "reason": f"unknown expected_format: {expected_format}",
        }
    result["check"] = "format_compliance"
    return result


def evaluate_instruction_following(
    text: str,
    *,
    expected_format: str | None,
    expected_keywords: list[str] | None,
    refusal_expected: bool,
    refusal_occurred: bool,
    max_chars: int | None = None,
) -> dict:
    checks = [
        check_format_compliance(text, expected_format),
        check_requested_length(text, max_chars),
        check_refusal_requirement(refusal_expected, refusal_occurred),
    ]
    if expected_keywords:
        checks.append(check_classification_label(text, expected_keywords))

    evaluated = [c for c in checks if c["status"] != NOT_EVALUATED]
    passed = [c["check"] for c in evaluated if c["status"] == PASS]
    warned = [c["check"] for c in evaluated if c["status"] == WARNING]
    failed = [c["check"] for c in evaluated if c["status"] == FAIL]
    total = len(evaluated)
    score = None if total == 0 else (len(passed) + 0.5 * len(warned)) / total

    return {
        "score": score,
        "passed_checks": passed,
        "warning_checks": warned,
        "failed_checks": failed,
        "evidence": {"checks": checks},
    }
