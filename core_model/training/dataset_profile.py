"""Deterministic representative-dataset profiling for Phase 11 base training.

Operates on plain record dicts only — no database access, no raw text
retained in the returned profile beyond aggregate counts and checksums.
"""

from __future__ import annotations

import hashlib
import re
import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from backend.core.json_utils import dumps_json
from core_model.training.dataset_stream import record_text_fields

TAMIL_PATTERN = re.compile(r"[஀-௿]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _combined_text(row: dict[str, Any]) -> str:
    return " ".join(text for text in record_text_fields(row) if text)


def build_dataset_profile(
    records: Iterable[dict[str, Any]],
    processor,
    *,
    eos_id: int,
    sequence_length: int,
) -> dict[str, Any]:
    records = list(records)
    total_records = len(records)
    split_counts = {"train": 0, "validation": 0, "test": 0}
    language_distribution: dict[str, int] = {}
    record_type_distribution: dict[str, int] = {}
    source_distribution: dict[str, int] = {}
    licence_distribution: dict[str, int] = {}
    record_lengths: list[int] = []
    total_tokens = 0
    zero_token_records = 0
    oversized_records = 0
    unique_token_ids: set[int] = set()
    content_hashes: dict[str, int] = {}
    normalized_texts: dict[str, int] = {}
    tamil_records = 0
    latin_records = 0
    mixed_script_records = 0
    tanglish_records = 0
    languages_by_split: dict[str, set[str]] = {"train": set(), "validation": set(), "test": set()}

    for row in records:
        split = row.get("split") or "train"
        if split in split_counts:
            split_counts[split] += 1
        language = str(row.get("language") or "unknown")
        _bump(language_distribution, language)
        _bump(record_type_distribution, str(row.get("record_type") or "unknown"))
        _bump(source_distribution, str(row.get("source_type") or "unknown"))
        _bump(licence_distribution, str(row.get("licence_status") or "unknown"))
        if split in languages_by_split:
            languages_by_split[split].add(language)

        text = _combined_text(row)
        record_lengths.append(len(text))
        content_hash = row.get("content_hash")
        if content_hash:
            content_hashes[content_hash] = content_hashes.get(content_hash, 0) + 1
        normalized = " ".join(text.lower().split())
        if normalized:
            normalized_texts[normalized] = normalized_texts.get(normalized, 0) + 1

        has_tamil = bool(TAMIL_PATTERN.search(text))
        has_latin = bool(LATIN_PATTERN.search(text))
        if has_tamil:
            tamil_records += 1
        if has_latin:
            latin_records += 1
        if has_tamil and has_latin:
            mixed_script_records += 1
        if language == "tgl":
            tanglish_records += 1

        if not text.strip():
            zero_token_records += 1
            continue
        ids = processor.encode(text, out_type=int) if processor else []
        if eos_id >= 0 and processor:
            ids = [*ids, eos_id]
        if not ids:
            zero_token_records += 1
            continue
        total_tokens += len(ids)
        unique_token_ids.update(ids)
        if len(ids) > sequence_length:
            oversized_records += 1

    duplicate_records = sum(count - 1 for count in content_hashes.values() if count > 1)
    near_duplicate_records = sum(count - 1 for count in normalized_texts.values() if count > 1)

    def _representativeness(split: str) -> dict[str, Any]:
        train_languages = languages_by_split["train"]
        split_languages = languages_by_split[split]
        coverage = (
            len(split_languages & train_languages) / len(train_languages)
            if train_languages
            else 0.0
        )
        return {
            "languages_present": sorted(split_languages),
            "language_coverage_ratio": coverage,
        }

    profile: dict[str, Any] = {
        "total_records": total_records,
        "approved_records": total_records,
        "train_count": split_counts["train"],
        "validation_count": split_counts["validation"],
        "test_count": split_counts["test"],
        "total_characters": sum(record_lengths),
        "total_tokens": total_tokens,
        "unique_token_count": len(unique_token_ids),
        "language_distribution": language_distribution,
        "record_type_distribution": record_type_distribution,
        "source_distribution": source_distribution,
        "licence_distribution": licence_distribution,
        "average_record_length": (sum(record_lengths) / total_records) if total_records else 0.0,
        "median_record_length": float(statistics.median(record_lengths)) if record_lengths else 0.0,
        "maximum_record_length": max(record_lengths) if record_lengths else 0,
        "duplicate_rate": (duplicate_records / total_records) if total_records else 0.0,
        "near_duplicate_rate": (near_duplicate_records / total_records) if total_records else 0.0,
        "zero_token_rate": (zero_token_records / total_records) if total_records else 0.0,
        "oversized_record_rate": (oversized_records / total_records) if total_records else 0.0,
        "validation_representativeness": _representativeness("validation"),
        "test_representativeness": _representativeness("test"),
        "tamil_script_coverage": (tamil_records / total_records) if total_records else 0.0,
        "english_latin_coverage": (latin_records / total_records) if total_records else 0.0,
        "tanglish_coverage": (tanglish_records / total_records) if total_records else 0.0,
        "mixed_script_coverage": (mixed_script_records / total_records) if total_records else 0.0,
    }
    profile["profile_checksum_sha256"] = hashlib.sha256(
        dumps_json(profile).encode("utf-8")
    ).hexdigest()
    return profile


@dataclass(frozen=True)
class ProfileThresholds:
    min_records: int
    min_tamil_ratio: float
    min_english_ratio: float
    min_tanglish_ratio: float
    max_duplicate_ratio: float
    min_validation_records: int
    min_test_records: int


def evaluate_warnings(
    profile: dict[str, Any], thresholds: ProfileThresholds
) -> list[dict[str, str]]:
    """Produce non-blocking, honest warnings. Never rebalances data silently."""

    warnings: list[dict[str, str]] = []
    total = profile["total_records"] or 1
    language_distribution = profile["language_distribution"]
    tamil_ratio = language_distribution.get("ta", 0) / total
    english_ratio = language_distribution.get("en", 0) / total
    tanglish_ratio = language_distribution.get("tgl", 0) / total

    if tamil_ratio < thresholds.min_tamil_ratio:
        warnings.append(
            {
                "code": "too_little_tamil",
                "message": f"Tamil ratio {tamil_ratio:.2%} is below the recommended minimum",
            }
        )
    if english_ratio < thresholds.min_english_ratio:
        warnings.append(
            {
                "code": "too_little_english",
                "message": f"English ratio {english_ratio:.2%} is below the recommended minimum",
            }
        )
    if tanglish_ratio < thresholds.min_tanglish_ratio:
        warnings.append(
            {
                "code": "too_little_tanglish",
                "message": f"Tanglish ratio {tanglish_ratio:.2%} is below the recommended minimum",
            }
        )
    if profile["validation_count"] < thresholds.min_validation_records:
        warnings.append(
            {
                "code": "tiny_validation_set",
                "message": f"validation split has only {profile['validation_count']} records",
            }
        )
    if profile["test_count"] < thresholds.min_test_records:
        warnings.append(
            {
                "code": "tiny_test_set",
                "message": f"test split has only {profile['test_count']} records",
            }
        )
    if profile["duplicate_rate"] > thresholds.max_duplicate_ratio:
        warnings.append(
            {
                "code": "high_duplication",
                "message": (
                    f"duplicate rate {profile['duplicate_rate']:.2%} exceeds the configured maximum"
                ),
            }
        )
    if profile["average_record_length"] < 20:
        warnings.append(
            {"code": "very_short_records", "message": "average record length is very short"}
        )
    source_distribution = profile["source_distribution"]
    if source_distribution:
        dominant = max(source_distribution.values())
        if dominant / total > 0.8:
            warnings.append(
                {"code": "dominant_single_source", "message": "one source dominates the dataset"}
            )
    licence_distribution = profile["licence_distribution"]
    if len(licence_distribution) <= 1:
        warnings.append(
            {"code": "low_licence_diversity", "message": "dataset has little licence diversity"}
        )
    source_type_ocr = sum(
        count for name, count in source_distribution.items() if "ocr" in name.lower()
    )
    if total and source_type_ocr / total > 0.5:
        warnings.append(
            {"code": "high_ocr_derived_ratio", "message": "majority of records are OCR-derived"}
        )
    return warnings


def data_sufficiency_status(profile: dict[str, Any], thresholds: ProfileThresholds) -> str:
    total = profile["total_records"]
    if total >= thresholds.min_records:
        return "sufficient"
    if total > 0:
        return "limited_experiment"
    return "insufficient"
