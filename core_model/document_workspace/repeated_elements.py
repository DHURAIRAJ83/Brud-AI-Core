"""Cross-page repeated header/footer/page-number detection (Phase 4, Step 11).

`document_service.clean_document_text()` already flags a *single*
page's short boundary lines as a `header_footer_candidate` warning, but
never aggregates that signal across a document or offers a removal
action. This module fills that specific gap: given every page's text,
find lines that recur across enough pages in a boundary position and
return them as suggestions -- nothing here deletes anything; that is
always a separate, explicit, audited admin action at the service layer.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_PAGE_NUMBER_LINE = re.compile(r"^\s*[-–]?\s*\d{1,4}\s*[-–]?\s*$")
_BOUNDARY_LINE_MAX_LENGTH = 100
_BOUNDARY_WINDOW = 2

# Content-pattern classification, checked in this priority order before
# falling back to pure top/bottom position (header/footer). Copyright
# notices are always high-risk and routed to manual review regardless of
# repetition confidence -- see Task §12 "Copyright notice" rule.
_COPYRIGHT_PATTERN = re.compile(r"©|\bcopyright\b|all rights reserved", re.IGNORECASE)
_NAVIGATION_PATTERN = re.compile(
    r"^(table of contents|contents|index|next|previous|home|menu|"
    r"chapter\s+\d+|back to top)$",
    re.IGNORECASE,
)
_WATERMARK_PATTERN = re.compile(
    r"^(watermark|draft|confidential|sample|unpublished|do not distribute|"
    r"internal use only)$",
    re.IGNORECASE,
)
# Per Task §12 "Text alone is not sufficient to label something a logo
# with high confidence" and no page-image/layout metadata is available in
# this repository to corroborate a logo guess -- deliberately restricted
# to an explicit, narrow marker vocabulary rather than any short title-case
# line (an earlier, broader heuristic here misclassified ordinary repeated
# headers as logos; see docs/data_studio/document_sft_finalization_audit.md).
_LOGO_LIKE_LINE = re.compile(r"^(logo|brand mark|company logo|™|®)$", re.IGNORECASE)


def _normalize(line: str) -> str:
    normalized = unicodedata.normalize("NFC", line).strip()
    return re.sub(r"\s+", " ", normalized).casefold()


def _looks_like_page_number(line: str) -> bool:
    return bool(_PAGE_NUMBER_LINE.match(line.strip()))


def _classify_content_type(normalized_text: str, top_count: int, bottom_count: int) -> str | None:
    """Returns a content-pattern-based element_type, or None to fall back
    to the existing pure top/bottom-position header/footer heuristic."""

    if _COPYRIGHT_PATTERN.search(normalized_text):
        return "copyright_notice"
    if _NAVIGATION_PATTERN.match(normalized_text.strip()):
        return "navigation_text"
    if _WATERMARK_PATTERN.match(normalized_text.strip()):
        return "watermark_text"
    if top_count > 0 and bottom_count == 0 and _LOGO_LIKE_LINE.match(normalized_text.strip()):
        return "logo_text"
    return None


def _boundary_candidates(text: str) -> list[tuple[str, str]]:
    """Returns (position, normalized_text) for short lines near the top
    or bottom of a page -- 'position' is 'top' or 'bottom'."""

    lines = [line for line in text.split("\n") if line.strip()]
    candidates: list[tuple[str, str]] = []
    for line in lines[:_BOUNDARY_WINDOW]:
        if len(line.strip()) <= _BOUNDARY_LINE_MAX_LENGTH:
            candidates.append(("top", _normalize(line)))
    for line in lines[-_BOUNDARY_WINDOW:]:
        if len(line.strip()) <= _BOUNDARY_LINE_MAX_LENGTH:
            candidates.append(("bottom", _normalize(line)))
    return candidates


def detect_repeated_elements(
    pages: list[tuple[int, str]],
    *,
    min_page_occurrences: int = 3,
    min_page_fraction: float = 0.5,
) -> list[dict[str, Any]]:
    """`pages` is a list of `(page_number, text)` tuples, in any order.
    Returns suggestions, never a destructive action."""

    total_pages = len(pages)
    if total_pages < 2:
        return []

    occurrences: dict[str, dict[str, Any]] = {}
    for page_number, text in pages:
        if not text:
            continue
        seen_on_this_page: set[str] = set()
        for position, normalized in _boundary_candidates(text):
            if not normalized or normalized in seen_on_this_page:
                continue
            seen_on_this_page.add(normalized)
            entry = occurrences.setdefault(
                normalized, {"pages": [], "positions": [], "raw_example": normalized}
            )
            entry["pages"].append(page_number)
            entry["positions"].append(position)

    threshold = max(min_page_occurrences, int(total_pages * min_page_fraction))
    suggestions: list[dict[str, Any]] = []
    for normalized_text, entry in occurrences.items():
        page_count = len(entry["pages"])
        if page_count < threshold:
            continue
        top_count = entry["positions"].count("top")
        bottom_count = entry["positions"].count("bottom")
        content_type = _classify_content_type(normalized_text, top_count, bottom_count)
        if _looks_like_page_number(normalized_text):
            element_type = "page_number"
        elif content_type is not None:
            element_type = content_type
        elif top_count >= bottom_count:
            element_type = "header"
        else:
            element_type = "footer"
        confidence = min(0.95, 0.4 + 0.5 * (page_count / total_pages))
        if element_type == "logo_text":
            # Text alone is never sufficient to confidently label a logo
            # (Task §12) -- cap confidence and never recommend removal.
            confidence = min(confidence, 0.5)
        never_auto_remove = element_type in ("copyright_notice", "watermark_text", "logo_text")
        suggestions.append(
            {
                "candidate_text": normalized_text,
                "element_type": element_type,
                "pages": sorted(entry["pages"]),
                "confidence": round(confidence, 2),
                "recommended_action": (
                    "review" if never_auto_remove or confidence < 0.7 else "accept_removal"
                ),
            }
        )
    suggestions.sort(key=lambda item: item["confidence"], reverse=True)
    return suggestions
