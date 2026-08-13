"""MB-28: Report Summarizer -- pure. Extracts key facts/test-counts
deterministically from a report or regression-result payload before
any LLM prose pass runs -- numbers are always taken from this
extraction, never invented by the LLM.
"""

from __future__ import annotations

from typing import Any


def extract_report_facts(*, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": report.get("title") or report.get("phase") or "Untitled report",
        "status": report.get("status", "unknown"),
        "key_numbers": {
            key: value
            for key, value in report.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        },
    }


def extract_regression_facts(*, regression_result: dict[str, Any]) -> dict[str, Any]:
    passed = int(regression_result.get("passed", 0))
    failed = int(regression_result.get("failed", 0))
    errors = int(regression_result.get("errors", 0))
    total = int(regression_result.get("total", passed + failed + errors))
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "is_green": failed == 0 and errors == 0,
    }


def build_summary_prompt_facts(*, facts: dict[str, Any]) -> str:
    lines = [f"{key}: {value}" for key, value in facts.items()]
    return "\n".join(lines)
