"""Deterministic query normalization for Tamil/English/Tanglish/mixed
retrieval. The original query is never overwritten — only ever
supplemented by a normalized form alongside its own checksum, so audit
lineage always keeps both.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

NORMALIZATION_VERSION = "v1"

_REPEATED_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION_VARIANTS = {
    "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "–": "-", "—": "-",
}


@dataclass(frozen=True)
class QueryNormalizationConfig:
    lowercase_latin: bool = True
    tanglish_aliases: dict[str, str] = field(default_factory=dict)
    technical_term_aliases: dict[str, str] = field(default_factory=dict)
    apply_ocr_substitutions: bool = False


def _normalize_punctuation(text: str) -> str:
    for old, new in _PUNCTUATION_VARIANTS.items():
        text = text.replace(old, new)
    return text


def _lowercase_latin_only(text: str) -> str:
    """Lowercases only ASCII/Latin runs, leaving Tamil script untouched."""

    return "".join(
        char.lower() if ("A" <= char <= "Z") else char for char in text
    )


def _apply_alias_map(text: str, aliases: dict[str, str]) -> tuple[str, bool]:
    if not aliases:
        return text, False
    changed = False
    tokens = text.split(" ")
    for index, token in enumerate(tokens):
        replacement = aliases.get(token.lower())
        if replacement is not None and replacement != token:
            tokens[index] = replacement
            changed = True
    return " ".join(tokens), changed


def normalize_query(
    query: str, *, language_category: str, config: QueryNormalizationConfig | None = None
) -> dict[str, object]:
    config = config or QueryNormalizationConfig()
    applied: list[str] = []
    original_checksum = hashlib.sha256(query.encode("utf-8")).hexdigest()

    working = unicodedata.normalize("NFC", query)
    applied.append("unicode_nfc")

    collapsed = _REPEATED_WHITESPACE.sub(" ", working).strip()
    if collapsed != working:
        applied.append("whitespace_collapsed")
    working = collapsed

    punctuation_normalized = _normalize_punctuation(working)
    if punctuation_normalized != working:
        applied.append("punctuation_normalized")
    working = punctuation_normalized

    if config.lowercase_latin:
        lowered = _lowercase_latin_only(working)
        if lowered != working:
            applied.append("latin_lowercased")
        working = lowered

    if language_category in {"tgl", "mixed"} and config.tanglish_aliases:
        aliased, changed = _apply_alias_map(working, config.tanglish_aliases)
        if changed:
            applied.append("tanglish_alias_expansion")
        working = aliased

    if config.technical_term_aliases:
        aliased, changed = _apply_alias_map(working, config.technical_term_aliases)
        if changed:
            applied.append("technical_term_alias_expansion")
        working = aliased

    return {
        "normalized_query": working,
        "original_query_checksum_sha256": original_checksum,
        "detected_language_category": language_category,
        "applied_transformations": applied,
        "normalization_version": NORMALIZATION_VERSION,
    }
