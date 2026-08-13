"""MB-05: Token Estimator -- deterministic, NO tokenizer model. Uses a
fixed characters-per-token ratio, exactly as the task requires
("No tokenizer model. Deterministic estimation only."). This is
intentionally a cruder estimate than the existing, real
`CorpusTokenizerAnalysisService` (which runs an actual tokenizer
against real corpus builds) -- that service is part of the production
training pipeline with its own DB-backed workflow and is not reused
here, since MB-05 is a lightweight, read-only, Dataset-Studio-record
advisory tool, not a corpus-build-time tool. This estimate should
never be presented as equivalent to a real tokenizer's count -- every
returned dict says so explicitly.

The ratio itself is a widely-cited rule of thumb for English
(~4 characters/token for GPT-style BPE tokenizers) with a separate,
more conservative ratio for Tamil script (Tamil text tends to tokenize
less efficiently under Latin-script-oriented BPE vocabularies) --
still a fixed constant, not a measurement, and disclosed as such.
"""

from __future__ import annotations

from typing import Any

CHARS_PER_TOKEN_ENGLISH = 4.0
CHARS_PER_TOKEN_TAMIL = 2.5
CHARS_PER_TOKEN_DEFAULT = 3.5
BYTES_PER_ESTIMATED_TOKEN_MEMORY = 4  # a conservative, disclosed placeholder for KV-cache sizing


def _ratio_for_language(language: str | None) -> float:
    if language == "ta":
        return CHARS_PER_TOKEN_TAMIL
    if language == "en":
        return CHARS_PER_TOKEN_ENGLISH
    return CHARS_PER_TOKEN_DEFAULT


def estimate_tokens(text: str, *, language: str | None = None) -> int:
    if not text:
        return 0
    ratio = _ratio_for_language(language)
    return max(1, round(len(text) / ratio))


def estimate_dataset_tokens(records: list[dict[str, Any]]) -> dict[str, Any]:
    lengths: list[int] = []
    token_counts: list[int] = []

    for record in records:
        text = "\n".join(
            part for part in (record.get("instruction"), record.get("input_text"), record.get("output_text"))
            if part
        )
        lengths.append(len(text))
        token_counts.append(estimate_tokens(text, language=record.get("language")))

    total_tokens = sum(token_counts)
    total_records = len(records)

    return {
        "total_records": total_records,
        "estimated_total_tokens": total_tokens,
        "average_tokens_per_record": round(total_tokens / total_records, 1) if total_records else 0,
        "maximum_tokens_in_a_record": max(token_counts) if token_counts else 0,
        "minimum_tokens_in_a_record": min(token_counts) if token_counts else 0,
        "average_char_length": round(sum(lengths) / total_records, 1) if total_records else 0,
        "maximum_char_length": max(lengths) if lengths else 0,
        "minimum_char_length": min(lengths) if lengths else 0,
        "estimated_memory_bytes": total_tokens * BYTES_PER_ESTIMATED_TOKEN_MEMORY,
        "estimated_training_size_mb": round(sum(lengths) / (1024 * 1024), 3),
        "methodology": (
            f"chars/token ratio: Tamil={CHARS_PER_TOKEN_TAMIL}, English={CHARS_PER_TOKEN_ENGLISH}, "
            f"other={CHARS_PER_TOKEN_DEFAULT} -- a fixed heuristic, NOT a real tokenizer. For an "
            "exact count, use the existing CorpusTokenizerAnalysisService against a real corpus build."
        ),
    }
