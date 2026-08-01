"""Duplicate detection for manual data records (Phase 3, Step 8).

Deliberately mirrors `backend.services.dataset_service.normalize_text`/
`content_hash` exactly (NFC normalize + collapse whitespace + optional
casefold, SHA-256 of a canonical JSON dict) rather than introducing a
new algorithm. No semantic/embedding duplicate engine exists anywhere
in this repository; building one is explicitly out of scope for this
phase (Step 8).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

_LOGICAL_FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "plain_text": ("input_text", "tamil_text", "english_text", "tanglish_text"),
    "language_example": ("input_text", "tamil_text", "english_text", "tanglish_text"),
    "grammar_example": ("input_text", "tamil_text", "english_text", "tanglish_text"),
    "conversation": ("turns",),
    "question_answer": ("question_text", "answer_text"),
    "instruction_response": ("instruction_text", "response_text"),
    "dictionary_entry": ("word", "meanings"),
    "translation_pair": ("input_text", "output_text", "input_language", "output_language"),
    "tanglish_normalization": ("tanglish_text", "tamil_text"),
    "knowledge_note": ("title", "input_text", "output_text"),
    "evaluation_case_draft": ("question_text", "answer_text"),
}


def normalize_text(value: str | None, *, fold_case: bool = False) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold() if fold_case else normalized


def _normalize_value(value: Any, *, fold_case: bool) -> Any:
    if isinstance(value, str):
        return normalize_text(value, fold_case=fold_case)
    if isinstance(value, list):
        return [_normalize_value(item, fold_case=fold_case) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalize_value(item, fold_case=fold_case) for key, item in sorted(value.items())
        }
    return value


def content_hash(record_type: str, fields: dict[str, Any]) -> str:
    """Hash the record type's logical fields only -- classification
    metadata (domain, topic, difficulty, ...) never affects identity,
    matching the dataset pipeline's own definition of "the same
    content"."""

    language = fields.get("primary_language", "unknown")
    fold = language in {"en", "tgl"}
    keys = _LOGICAL_FIELDS_BY_TYPE.get(record_type, ())
    logical = {"record_type": record_type, "primary_language": language}
    for key in keys:
        logical[key] = _normalize_value(fields.get(key), fold_case=fold)
    return hashlib.sha256(json.dumps(logical, sort_keys=True).encode()).hexdigest()


def dictionary_word_key(word: str | None, primary_language: str | None) -> str | None:
    """A `(word, language)` uniqueness key for dictionary entries --
    two entries for the same word in the same language are a duplicate
    even if their example sentences differ."""

    if not word:
        return None
    normalized_word = normalize_text(word, fold_case=True)
    return f"{primary_language or 'unknown'}:{normalized_word}"
