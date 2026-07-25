"""Cross-document repeated-boilerplate detection and removal.

Unlike ``ocr_cleanup``'s single-document heuristics, boilerplate is
detected by *frequency across the documents in one normalization run*
-- a line is only boilerplate evidence once it recurs across enough
distinct documents to rule out being meaningful repeated educational
text. Pattern evidence, removal count, and source location are always
persisted; nothing is deleted silently.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

DEFAULT_MINIMUM_REPETITION_RATIO = 0.3
DEFAULT_MINIMUM_DOCUMENT_COUNT = 3


def _candidate_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def detect_boilerplate_lines(
    documents_text: list[str],
    *,
    minimum_repetition_ratio: float = DEFAULT_MINIMUM_REPETITION_RATIO,
    minimum_document_count: int = DEFAULT_MINIMUM_DOCUMENT_COUNT,
) -> dict[str, Any]:
    """Returns the set of lines that recur across enough documents to
    be treated as boilerplate, plus the evidence count for each. Short
    lines (headings, single dictionary entries) are excluded from
    consideration by a minimum-length floor, so meaningful short
    repeated educational text (e.g. a recurring FAQ question) is never
    swept up as boilerplate merely for being short."""

    if len(documents_text) < minimum_document_count:
        return {"boilerplate_lines": {}, "documents_considered": len(documents_text)}

    line_document_counts: Counter[str] = Counter()
    for text in documents_text:
        seen_in_this_document = set(_candidate_lines(text))
        for line in seen_in_this_document:
            if len(line) >= 8:
                line_document_counts[line] += 1

    total_documents = len(documents_text)
    boilerplate_lines = {
        line: count
        for line, count in line_document_counts.items()
        # A line appearing in only one document is never boilerplate,
        # regardless of ratio -- the count floor prevents a small
        # document set (e.g. 3 documents) from letting a single
        # incidental line cross the ratio threshold on its own.
        if count >= 2 and count / total_documents >= minimum_repetition_ratio
    }
    return {"boilerplate_lines": boilerplate_lines, "documents_considered": total_documents}


def remove_boilerplate_lines(text: str, boilerplate_lines: dict[str, int]) -> dict[str, Any]:
    kept_lines = []
    removed_evidence: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in boilerplate_lines:
            removed_evidence.append(
                {
                    "line": _bounded_excerpt(stripped),
                    "document_frequency": boilerplate_lines[stripped],
                }
            )
            continue
        kept_lines.append(line)
    return {
        "cleaned_text": "\n".join(kept_lines),
        "removed_count": len(removed_evidence),
        "removal_evidence": removed_evidence,
    }


def _bounded_excerpt(line: str, *, maximum_length: int = 120) -> str:
    return line if len(line) <= maximum_length else line[:maximum_length].rstrip() + "..."
