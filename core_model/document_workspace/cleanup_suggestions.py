"""Deterministic correction *suggestions* only (Phase 4, Step 10/18).

Every function here detects a candidate correction and returns it as a
structured suggestion (`suggestion_type`, `original_text`,
`proposed_text`, `reason`, `confidence`) -- nothing here ever mutates
text. Acceptance/rejection is an explicit admin action at the service
layer. Mirrors the detection style already used by
`document_service.clean_document_text()` (NFC-normalize first, regex-
based signal detection) without importing from the unrelated
`core_model.corpus.ocr_cleanup` module (a different pipeline that
already applies its corrections directly -- this module's philosophy
is deliberately "suggest only").
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_TAMIL_RANGE = (0x0B80, 0x0BFF)
_PAGE_NUMBER_LINE = re.compile(r"^\s*[-–]?\s*\d{1,4}\s*[-–]?\s*$")
_HYPHENATED_BREAK = re.compile(r"(\w+)-\n(\w+)")
_REPEATED_WHITESPACE = re.compile(r"[ \t]{2,}")
_MATCHING_PUNCTUATION = {"(": ")", "[": "]", "{": "}", '"': '"'}

# Finalization-pass detectors (Task §11/§12) -- conservative, per-page,
# regex-only. Never auto-removes: every result is a preview-only suggestion,
# identical in shape to the Phase 4 detectors above.
_WEB_URL = re.compile(r"\b(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
_EMAIL_ADDRESS = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_NUMBER = re.compile(
    r"(?<!\w)(?:\+91[\s-]?)?(?:\(\d{2,4}\)[\s-]?)?\d{3,5}[\s-]\d{3,4}[\s-]?\d{0,4}(?!\w)"
)
_NOISE_LINE = re.compile(r"^[^\w\s]{3,}$|^(.)\1{4,}$")


def _suggestion(
    suggestion_type: str,
    original_text: str,
    proposed_text: str,
    reason: str,
    confidence: float,
    *,
    risk_level: str = "low",
    reason_code: str | None = None,
) -> dict[str, Any]:
    return {
        "suggestion_type": suggestion_type,
        "original_text": original_text,
        "proposed_text": proposed_text,
        "reason": reason,
        "confidence": round(confidence, 2),
        "risk_level": risk_level,
        "reason_code": reason_code or suggestion_type,
    }


def _is_tamil(char: str) -> bool:
    return _TAMIL_RANGE[0] <= ord(char) <= _TAMIL_RANGE[1]


def suggest_replacement_glyph_warnings(text: str) -> list[dict[str, Any]]:
    if "�" not in text:
        return []
    count = text.count("�")
    return [
        _suggestion(
            "replacement_glyph",
            "�",
            "",
            f"{count} replacement character(s) found -- the original glyph could not be "
            "recovered automatically; review the source page image.",
            0.9,
        )
    ]


def suggest_repeated_whitespace(text: str) -> list[dict[str, Any]]:
    suggestions = []
    for match in _REPEATED_WHITESPACE.finditer(text):
        suggestions.append(
            _suggestion(
                "repeated_whitespace",
                match.group(0),
                " ",
                "Repeated spaces/tabs likely came from OCR column artifacts.",
                0.7,
            )
        )
    return suggestions[:20]


def suggest_broken_word_joins(text: str) -> list[dict[str, Any]]:
    suggestions = []
    for match in _HYPHENATED_BREAK.finditer(text):
        joined = match.group(1) + match.group(2)
        suggestions.append(
            _suggestion(
                "broken_tamil_word" if any(_is_tamil(c) for c in joined) else "other",
                match.group(0),
                joined,
                "A hyphenated line break likely split one word across two lines.",
                0.65,
            )
        )
    return suggestions


def suggest_suspicious_latin_in_tamil(text: str) -> list[dict[str, Any]]:
    suggestions = []
    normalized = unicodedata.normalize("NFC", text)
    for match in re.finditer(r"[஀-௿]+[A-Za-z][஀-௿]+", normalized):
        suggestions.append(
            _suggestion(
                "suspicious_latin_in_tamil",
                match.group(0),
                match.group(0),
                "A single Latin letter appears inside a Tamil word -- likely an OCR "
                "misrecognition; review before correcting.",
                0.55,
            )
        )
    return suggestions[:20]


def suggest_duplicated_lines(text: str) -> list[dict[str, Any]]:
    suggestions = []
    lines = text.split("\n")
    for index in range(1, len(lines)):
        current, previous = lines[index].strip(), lines[index - 1].strip()
        if current and current == previous:
            suggestions.append(
                _suggestion(
                    "duplicated_line",
                    current,
                    "",
                    "This line is an exact duplicate of the line immediately above it.",
                    0.6,
                )
            )
    return suggestions


def suggest_page_number_lines(text: str) -> list[dict[str, Any]]:
    suggestions = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and _PAGE_NUMBER_LINE.match(stripped):
            suggestions.append(
                _suggestion(
                    "likely_page_number",
                    stripped,
                    "",
                    "This line looks like a standalone page number.",
                    0.75,
                )
            )
    return suggestions


def suggest_unbalanced_punctuation(text: str) -> list[dict[str, Any]]:
    suggestions = []
    for opener, closer in _MATCHING_PUNCTUATION.items():
        if opener == closer:
            count = text.count(opener)
            if count % 2 != 0:
                suggestions.append(
                    _suggestion(
                        "unbalanced_punctuation",
                        opener,
                        "",
                        f"An odd number of {opener!r} characters suggests a missing pair.",
                        0.4,
                    )
                )
        else:
            open_count, close_count = text.count(opener), text.count(closer)
            if open_count != close_count:
                reason = f"{open_count} {opener!r} vs {close_count} {closer!r} -- unbalanced."
                suggestions.append(
                    _suggestion("unbalanced_punctuation", f"{opener}...{closer}", "", reason, 0.4)
                )
    return suggestions


def suggest_web_urls(text: str) -> list[dict[str, Any]]:
    suggestions = []
    for match in _WEB_URL.finditer(text):
        suggestions.append(
            _suggestion(
                "web_url",
                match.group(0),
                match.group(0),
                "A URL was detected -- review before removal; it may be meaningful source "
                "attribution rather than noise.",
                0.8,
                risk_level="medium",
            )
        )
    return suggestions[:20]


def suggest_email_addresses(text: str) -> list[dict[str, Any]]:
    suggestions = []
    for match in _EMAIL_ADDRESS.finditer(text):
        suggestions.append(
            _suggestion(
                "email_address",
                match.group(0),
                match.group(0),
                "An email-address-shaped string was detected.",
                0.75,
                risk_level="medium",
            )
        )
    return suggestions[:20]


def suggest_phone_numbers(text: str) -> list[dict[str, Any]]:
    suggestions = []
    for match in _PHONE_NUMBER.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 7:
            # Too short to be confidently a phone number -- likely an
            # ordinary numeric lesson or measurement; skip rather than
            # misclassify per the task's own conservative requirement.
            continue
        suggestions.append(
            _suggestion(
                "phone_number",
                match.group(0),
                match.group(0),
                "A phone-number-shaped digit sequence was detected.",
                0.6,
                risk_level="medium",
            )
        )
    return suggestions[:20]


def suggest_noise_lines(text: str) -> list[dict[str, Any]]:
    suggestions = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and _NOISE_LINE.match(stripped):
            suggestions.append(
                _suggestion(
                    "noise_line",
                    stripped,
                    "",
                    "This line contains only scanner-artifact-like symbols or repeated "
                    "punctuation, not meaningful text.",
                    0.55,
                    risk_level="low",
                )
            )
    return suggestions[:20]


def suggest_duplicate_paragraphs(text: str) -> list[dict[str, Any]]:
    suggestions = []
    seen: dict[str, int] = {}
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", " ", paragraph).casefold()
        if len(normalized) < 40:
            continue
        if normalized in seen:
            suggestions.append(
                _suggestion(
                    "duplicate_paragraph",
                    paragraph[:200],
                    "",
                    "This paragraph is an exact (normalized) duplicate of an earlier "
                    "paragraph on the same page -- never merged merely for discussing "
                    "the same topic, only for matching text.",
                    0.7,
                    risk_level="medium",
                )
            )
        seen[normalized] = seen.get(normalized, 0) + 1
    return suggestions[:20]


def generate_cleanup_suggestions(text: str) -> list[dict[str, Any]]:
    """Every suggestion is deterministic and additive-only -- calling this
    twice on the same text returns the same suggestions; nothing here
    mutates `text` itself."""

    if not text:
        return []
    suggestions: list[dict[str, Any]] = []
    suggestions.extend(suggest_replacement_glyph_warnings(text))
    suggestions.extend(suggest_broken_word_joins(text))
    suggestions.extend(suggest_repeated_whitespace(text))
    suggestions.extend(suggest_suspicious_latin_in_tamil(text))
    suggestions.extend(suggest_duplicated_lines(text))
    suggestions.extend(suggest_page_number_lines(text))
    suggestions.extend(suggest_unbalanced_punctuation(text))
    suggestions.extend(suggest_web_urls(text))
    suggestions.extend(suggest_email_addresses(text))
    suggestions.extend(suggest_phone_numbers(text))
    suggestions.extend(suggest_noise_lines(text))
    suggestions.extend(suggest_duplicate_paragraphs(text))
    return suggestions
