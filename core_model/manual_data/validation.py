"""Record-type-specific validation for manual data records (Phase 3, Step 6).

Pure functions only. `validate_record_fields()` returns a list of
human-readable error strings (empty means valid) rather than raising,
so both the API layer (which raises `ValidationError` on any error) and
the quality module (which reports `EMPTY_REQUIRED_FIELD` as a blocking
issue) can reuse the same check.
"""

from __future__ import annotations

from typing import Any

VALID_CONVERSATION_ROLES = frozenset(
    {
        "user",
        "assistant",
        "system",
        "speaker_a",
        "speaker_b",
        "teacher",
        "student",
        "customer",
        "agent",
    }
)


def _missing(fields: dict[str, Any], *names: str) -> list[str]:
    return [name for name in names if not fields.get(name)]


def validate_record_fields(record_type: str, fields: dict[str, Any]) -> list[str]:
    """`fields` is the union of a revision's content columns (already
    un-JSONed where relevant, e.g. `turns`, `meanings`, `examples`) plus
    the record's own classification (`primary_language`,
    `input_language`, `output_language`)."""

    errors: list[str] = []

    if record_type in ("plain_text", "language_example", "grammar_example"):
        if not any(
            fields.get(key) for key in ("input_text", "tamil_text", "english_text", "tanglish_text")
        ):
            errors.append(
                "at least one of input_text/tamil_text/english_text/tanglish_text is required"
            )
        if not fields.get("primary_language"):
            errors.append("primary_language is required")

    elif record_type == "conversation":
        turns = fields.get("turns") or []
        if len(turns) < 2:
            errors.append("a conversation requires at least two ordered turns")
        for index, turn in enumerate(turns):
            if not turn.get("content"):
                errors.append(f"turn {index} has empty content")
            if turn.get("role") not in VALID_CONVERSATION_ROLES:
                errors.append(f"turn {index} has an invalid role: {turn.get('role')!r}")
        if not fields.get("primary_language"):
            errors.append("primary_language is required")

    elif record_type == "question_answer":
        errors += [
            f"{name} is required" for name in _missing(fields, "question_text", "answer_text")
        ]
        if not fields.get("primary_language"):
            errors.append("primary_language is required")

    elif record_type == "instruction_response":
        errors += [
            f"{name} is required" for name in _missing(fields, "instruction_text", "response_text")
        ]
        if not fields.get("output_language"):
            errors.append("output_language is required")

    elif record_type == "dictionary_entry":
        errors += [f"{name} is required" for name in _missing(fields, "word")]
        if not (fields.get("meanings")):
            errors.append("at least one meaning is required")
        if not fields.get("primary_language"):
            errors.append("primary_language is required")

    elif record_type == "translation_pair":
        errors += [f"{name} is required" for name in _missing(fields, "input_text", "output_text")]
        input_language = fields.get("input_language")
        output_language = fields.get("output_language")
        if not input_language or not output_language:
            errors.append("input_language and output_language are both required")
        elif input_language == output_language:
            errors.append(
                "input_language and output_language must be distinct for a translation pair"
            )

    elif record_type == "tanglish_normalization":
        errors += [
            f"{name} is required" for name in _missing(fields, "tanglish_text", "tamil_text")
        ]

    elif record_type == "knowledge_note":
        if not fields.get("title"):
            errors.append("title is required")
        if not any(fields.get(key) for key in ("input_text", "output_text")):
            errors.append("content is required")
        if not fields.get("fact_dependency"):
            errors.append("fact_dependency is required")
        if not fields.get("knowledge_risk"):
            errors.append("knowledge_risk is required")

    elif record_type == "evaluation_case_draft":
        errors += [
            f"{name} is required" for name in _missing(fields, "question_text", "answer_text")
        ]

    if fields.get("knowledge_risk") == "time_sensitive" and not fields.get("review_expiry_at"):
        errors.append("time-sensitive knowledge requires a review_expiry_at revalidation date")

    return errors
