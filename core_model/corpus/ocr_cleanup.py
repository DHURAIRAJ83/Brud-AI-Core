"""Deterministic, versioned, bounded OCR cleanup.

Every correction is deterministic (same input always produces the same
output), counted by category, and never model-generated -- this phase
explicitly forbids using a language model to "fix" OCR text. Corrections
remain reversible through provenance: the pre-cleanup extracted text is
always preserved unchanged in ``corpus_extracted_documents``, only the
post-cleanup text lives in ``corpus_normalized_documents``.
"""

from __future__ import annotations

import re
from typing import Any

OCR_CLEANUP_VERSION = "v1"

# A line consisting only of digits (optionally with surrounding
# whitespace/punctuation), 1-4 characters long -- a common scanned
# page-number artefact.
_PAGE_NUMBER_LINE = re.compile(r"^\s*[-–]?\s*\d{1,4}\s*[-–]?\s*$", re.MULTILINE)

# A hyphen at the end of a line followed by a lowercase Latin letter on
# the next line -- a classic PDF/OCR line-wrap hyphenation artefact.
_HYPHENATED_LINE_BREAK = re.compile(r"(\w+)-\n(\w+)")

# Three or more identical non-whitespace characters in a row (e.g.
# "-----" or "....." from a scanned divider/artefact).
_REPEATED_CHARACTER_NOISE = re.compile(r"([^\sA-Za-z஀-௿])\1{2,}")

_EXCESSIVE_WHITESPACE = re.compile(r"[ \t]{3,}")

# A Tamil consonant immediately followed by a stray Latin letter with
# no space -- a common OCR mis-segmentation garbling script boundaries.
_GARBLED_SCRIPT_MIXING = re.compile(r"([஀-௿])([A-Za-z])(?![A-Za-z])")


def remove_page_number_lines(text: str) -> tuple[str, int]:
    matches = _PAGE_NUMBER_LINE.findall(text)
    return _PAGE_NUMBER_LINE.sub("", text), len(matches)


def join_hyphenated_line_breaks(text: str) -> tuple[str, int]:
    matches = _HYPHENATED_LINE_BREAK.findall(text)
    return _HYPHENATED_LINE_BREAK.sub(r"\1\2", text), len(matches)


def collapse_repeated_character_noise(text: str) -> tuple[str, int]:
    matches = _REPEATED_CHARACTER_NOISE.findall(text)
    return _REPEATED_CHARACTER_NOISE.sub(r"\1", text), len(matches)


def collapse_excessive_whitespace(text: str) -> tuple[str, int]:
    matches = _EXCESSIVE_WHITESPACE.findall(text)
    return _EXCESSIVE_WHITESPACE.sub(" ", text), len(matches)


def flag_garbled_script_mixing(text: str) -> int:
    """Detection only -- garbled Tamil/Latin boundary mixing is
    reported as a quality signal, never auto-rewritten, since a
    correct fix requires knowing the intended word."""

    return len(_GARBLED_SCRIPT_MIXING.findall(text))


def clean_ocr_text(text: str) -> dict[str, Any]:
    working = text
    counts: dict[str, int] = {}

    working, counts["hyphenated_line_breaks_joined"] = join_hyphenated_line_breaks(working)
    working, counts["page_number_lines_removed"] = remove_page_number_lines(working)
    working, counts["repeated_character_noise_collapsed"] = collapse_repeated_character_noise(
        working
    )
    working, counts["excessive_whitespace_collapsed"] = collapse_excessive_whitespace(working)
    garbled_mixing_count = flag_garbled_script_mixing(working)

    return {
        "cleaned_text": working.strip(),
        "correction_counts": counts,
        "total_corrections": sum(counts.values()),
        "garbled_script_mixing_flagged": garbled_mixing_count,
        "ocr_cleanup_version": OCR_CLEANUP_VERSION,
    }
