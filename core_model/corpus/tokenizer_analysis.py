"""Phase 20 tokenizer compatibility analysis -- pure aggregation only.

The actual SentencePiece encode/decode call is impure (it loads a
registered tokenizer artifact) and stays in
``backend/services/corpus_tokenizer_analysis_service.py``, which reuses
Phase 7's ``TokenizerService.processor_for_version`` unchanged -- this
module only ever aggregates already-computed token-id lists, so it
never re-implements or duplicates Phase 7's own tokenizer loading and
never trains a tokenizer itself.
"""

from __future__ import annotations

from typing import Any

# Deterministic, bounded per-record token-level analysis.
DEFAULT_MAX_SEQUENCE_LENGTH = 512


def analyze_token_ids(
    text: str,
    token_ids: list[int],
    *,
    unk_id: int,
    max_sequence_length: int = DEFAULT_MAX_SEQUENCE_LENGTH,
) -> dict[str, Any]:
    token_count = len(token_ids)
    character_count = len(text)
    unknown_count = sum(1 for token_id in token_ids if token_id == unk_id)
    word_count = len(text.split()) or 1
    return {
        "character_count": character_count,
        "token_count": token_count,
        "unknown_token_count": unknown_count,
        "characters_per_token": character_count / token_count if token_count else 0.0,
        "tokens_per_word": token_count / word_count,
        "unknown_token_rate": unknown_count / token_count if token_count else 0.0,
        "is_long_sequence": token_count > max_sequence_length,
        "truncation_risk": token_count > max_sequence_length,
    }


def aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "total_characters": 0,
            "total_tokens": 0,
            "characters_per_token": 0.0,
            "unknown_token_rate": 0.0,
            "long_sequence_rate": 0.0,
            "truncation_risk_rate": 0.0,
        }
    total_characters = sum(row["character_count"] for row in rows)
    total_tokens = sum(row["token_count"] for row in rows)
    total_unknown = sum(row["unknown_token_count"] for row in rows)
    long_count = sum(1 for row in rows if row["is_long_sequence"])
    truncation_risk_count = sum(1 for row in rows if row["truncation_risk"])
    return {
        "total_characters": total_characters,
        "total_tokens": total_tokens,
        "characters_per_token": total_characters / total_tokens if total_tokens else 0.0,
        "unknown_token_rate": total_unknown / total_tokens if total_tokens else 0.0,
        "long_sequence_rate": long_count / len(rows),
        "truncation_risk_rate": truncation_risk_count / len(rows),
    }


def round_trip_integrity_rate(pairs: list[tuple[str, str]]) -> float:
    if not pairs:
        return 0.0
    return sum(1 for original, decoded in pairs if original == decoded) / len(pairs)


def script_token_bucket(language_category: str) -> str:
    """Maps a segment's already-classified language category onto the
    token-level breakdown bucket the readiness report expects."""

    return {
        "ta": "tamil_token_ratio",
        "en": "english_token_ratio",
        "tgl": "tanglish_token_ratio",
        "mixed": "mixed_script_token_ratio",
    }.get(language_category, "other_token_ratio")


def compute_script_token_ratios(rows_by_language: dict[str, dict[str, Any]]) -> dict[str, float]:
    """``rows_by_language`` maps language_category -> aggregated metrics
    (from ``aggregate_metrics``). Returns each bucket's share of the
    total token count across all languages."""

    total_tokens = sum(metrics["total_tokens"] for metrics in rows_by_language.values())
    if total_tokens == 0:
        return {}
    ratios: dict[str, float] = {}
    for language_category, metrics in rows_by_language.items():
        bucket = script_token_bucket(language_category)
        ratios[bucket] = ratios.get(bucket, 0.0) + metrics["total_tokens"] / total_tokens
    return ratios
