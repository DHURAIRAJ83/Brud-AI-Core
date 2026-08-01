"""Duplicate and conflict detection for semantic chunks and structured
record candidates (Phase 5, Step 21).

Deliberately mirrors `backend.services.dataset_service.normalize_text`/
`content_hash` and `core_model.manual_data.duplicates` exactly (NFC
normalize + collapse whitespace + optional casefold, SHA-256 of a
canonical JSON dict) rather than introducing a new algorithm. No
semantic/embedding duplicate engine exists anywhere in this repository;
building one is explicitly out of scope for this phase (Step 21).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

_STRUCTURED_LOGICAL_FIELDS: dict[str, tuple[str, ...]] = {
    "plain_text": ("text",),
    "language_example": ("text",),
    "grammar_example": ("grammar_rule", "correct_example", "incorrect_example"),
    "conversation": ("text",),
    "question_answer": ("question", "answer"),
    "instruction_response": ("instruction", "response"),
    "dictionary_entry": ("word", "meanings_json"),
    "translation_pair": ("source_text", "target_text", "source_language", "target_language"),
    "tanglish_normalization": ("tanglish_text", "normalized_tamil"),
    "knowledge_note": ("title", "text"),
    "rag_chunk": ("text",),
}


def normalize_text(value: str | None, *, fold_case: bool = False) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold() if fold_case else normalized


def _hash_json(logical: dict[str, Any]) -> str:
    encoded = json.dumps(logical, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def chunk_content_hash(text: str, language: str = "unknown") -> str:
    fold = language in {"en", "tgl"}
    return _hash_json({"text": normalize_text(text, fold_case=fold)})


def structured_record_content_hash(record_type: str, revision: dict[str, Any]) -> str:
    fields = _STRUCTURED_LOGICAL_FIELDS.get(record_type, ("text",))
    language = revision.get("source_language") or revision.get("language") or "unknown"
    fold = language in {"en", "tgl"}
    logical: dict[str, Any] = {"record_type": record_type}
    for field in fields:
        value = revision.get(field)
        logical[field] = normalize_text(value, fold_case=fold) if isinstance(value, str) else value
    return _hash_json(logical)


def find_exact_chunk_duplicate(content_hash: str, existing_hashes: dict[str, str]) -> str | None:
    """`existing_hashes` maps chunk_public_id -> content_hash. Returns the
    duplicate chunk's public_id, if any."""
    for public_id, existing_hash in existing_hashes.items():
        if existing_hash == content_hash:
            return public_id
    return None


def find_locator_duplicate(locator: dict[str, Any], existing: list[dict[str, Any]]) -> str | None:
    """A second chunk claiming the exact same source locator (same page +
    same offsets) on the same document is a duplicate regardless of any
    text difference introduced by a later edit."""
    for other in existing:
        if (
            other.get("page_number") == locator.get("page_number")
            and other.get("offset_start") == locator.get("offset_start")
            and other.get("offset_end") == locator.get("offset_end")
        ):
            return other.get("public_id")
    return None


def detect_dictionary_conflict(
    word: str, meanings: list[str], existing_entries: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Same word, different meaning set -> conflict (alternate sense), not
    an automatic duplicate and never auto-merged."""
    normalized_word = normalize_text(word, fold_case=True)
    normalized_meanings = {normalize_text(m, fold_case=True) for m in meanings}
    for entry in existing_entries:
        if normalize_text(entry.get("word"), fold_case=True) != normalized_word:
            continue
        other_meanings = {normalize_text(m, fold_case=True) for m in entry.get("meanings", [])}
        if other_meanings == normalized_meanings:
            return {"type": "duplicate_sense", "candidate_public_id": entry.get("public_id")}
        return {"type": "alternate_sense", "candidate_public_id": entry.get("public_id")}
    return None


def detect_qa_conflict(
    question: str, answer: str, existing_pairs: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Same question, different answer -> conflict, never auto-resolved."""
    normalized_question = normalize_text(question, fold_case=True)
    normalized_answer = normalize_text(answer, fold_case=True)
    for entry in existing_pairs:
        if normalize_text(entry.get("question"), fold_case=True) != normalized_question:
            continue
        if normalize_text(entry.get("answer"), fold_case=True) == normalized_answer:
            return {"type": "duplicate_answer", "candidate_public_id": entry.get("public_id")}
        return {"type": "conflicting_answer", "candidate_public_id": entry.get("public_id")}
    return None


def detect_translation_conflict(
    source_text: str, target_text: str, existing_translations: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Same source text, different target text -> inconsistent
    translation conflict."""
    normalized_source = normalize_text(source_text, fold_case=True)
    normalized_target = normalize_text(target_text, fold_case=True)
    for entry in existing_translations:
        if normalize_text(entry.get("source_text"), fold_case=True) != normalized_source:
            continue
        if normalize_text(entry.get("target_text"), fold_case=True) == normalized_target:
            return {"type": "duplicate_translation", "candidate_public_id": entry.get("public_id")}
        return {"type": "inconsistent_translation", "candidate_public_id": entry.get("public_id")}
    return None
