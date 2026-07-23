"""Orchestrates validation -> formatting -> tokenization -> label masking
into deterministic, split-isolated instruction-tuning examples, plus the
full coverage/exclusion accounting needed for the dataset profile.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any

from backend.core.json_utils import loads_json
from core_model.instruction_tuning.dataset_validator import (
    DatasetValidationThresholds,
    validate_record,
)
from core_model.instruction_tuning.formatter import (
    detect_special_token_collisions,
    render_example,
)
from core_model.instruction_tuning.label_masking import (
    LabelMaskingThresholds,
    build_response_labeled_example,
)
from core_model.instruction_tuning.language_checks import requested_language_respected
from core_model.instruction_tuning.templates import InstructionTemplate

LabeledExample = tuple[list[int], list[int], list[int], str]


@dataclass(frozen=True)
class InstructionProfileThresholds:
    min_records: int
    limited_experiment_floor: int
    min_validation_records: int
    min_test_records: int


def data_sufficiency_status(eligible_records: int, thresholds: InstructionProfileThresholds) -> str:
    if eligible_records >= thresholds.min_records:
        return "sufficient"
    if eligible_records > 0:
        return "limited_instruction_experiment"
    return "insufficient"


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def build_instruction_examples(
    records: list[dict[str, Any]],
    processor,
    template: InstructionTemplate,
    *,
    eos_token_id: int,
    pad_token_id: int,
    sequence_length: int,
    dataset_thresholds: DatasetValidationThresholds,
    masking_thresholds: LabelMaskingThresholds,
    tokenizer_checksum: str,
    dataset_checksum: str,
    template_checksum: str,
    shuffle: bool,
    seed: int,
) -> dict[str, Any]:
    splits: dict[str, list[LabeledExample]] = {"train": [], "validation": [], "test": []}
    exclusion_reasons: dict[str, int] = {}
    invalid_records = 0
    excluded_records = 0
    eligible_records = 0
    language_distribution: dict[str, int] = {}
    record_type_distribution: dict[str, int] = {}
    source_distribution: dict[str, int] = {}
    licence_distribution: dict[str, int] = {}
    system_prompt_count = 0
    input_field_count = 0
    synthesized_flat_chat_count = 0
    prompt_token_counts: list[int] = []
    response_token_counts: list[int] = []
    empty_response_count = 0
    duplicate_prompt_hashes: dict[str, int] = {}
    duplicate_response_hashes: dict[str, int] = {}
    exact_pair_hashes: dict[str, int] = {}
    response_language_mismatch_count = 0
    special_token_collision_count = 0
    truncation_risk_count = 0
    maskable_assistant_token_count = 0
    input_checksum_parts: list[str] = []
    label_checksum_parts: list[str] = []

    for row in records:
        _bump(record_type_distribution, str(row.get("record_type") or "unknown"))
        _bump(source_distribution, str(row.get("source_type") or "unknown"))
        _bump(licence_distribution, str(row.get("licence_status") or "unknown"))

        metadata = loads_json(row.get("metadata_json") or "{}")
        validated = validate_record(row, metadata, dataset_thresholds)
        if not validated["valid"]:
            invalid_records += 1
            _bump(exclusion_reasons, validated["reason"])
            continue
        if validated["excluded"]:
            excluded_records += 1
            _bump(exclusion_reasons, validated["exclusion_reason"])
            continue

        response_text = (validated.get("response_text") or "").strip()
        if not response_text:
            empty_response_count += 1
            excluded_records += 1
            _bump(exclusion_reasons, "empty_response")
            continue

        eligible_records += 1
        language = row.get("language") or "unknown"
        _bump(language_distribution, language)
        if validated.get("system_text"):
            system_prompt_count += 1
        if validated.get("input_text"):
            input_field_count += 1
        if validated.get("synthesized_from_flat_fields"):
            synthesized_flat_chat_count += 1

        prompt_text = validated.get("prompt_text") or ""
        prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        response_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
        pair_hash = hashlib.sha256(f"{prompt_text}||{response_text}".encode()).hexdigest()
        _bump(duplicate_prompt_hashes, prompt_hash)
        _bump(duplicate_response_hashes, response_hash)
        _bump(exact_pair_hashes, pair_hash)

        if detect_special_token_collisions(f"{prompt_text} {response_text}"):
            special_token_collision_count += 1
        if language in {"ta", "en", "tgl", "mixed"}:
            if requested_language_respected(response_text, language)["status"] != "pass":
                response_language_mismatch_count += 1

        prompt_rendered, response_rendered = render_example(validated, language, template)
        prompt_ids = processor.encode(prompt_rendered, out_type=int)
        response_ids = processor.encode(response_rendered, out_type=int)
        prompt_token_counts.append(len(prompt_ids))
        response_token_counts.append(len(response_ids))

        built = build_response_labeled_example(
            prompt_ids, response_ids,
            pad_token_id=pad_token_id, eos_token_id=eos_token_id, thresholds=masking_thresholds,
        )
        if built["rejected"]:
            truncation_risk_count += 1
            excluded_records += 1
            eligible_records -= 1
            _bump(exclusion_reasons, built["reject_reason"])
            continue
        if built["truncated"]:
            truncation_risk_count += 1

        maskable_assistant_token_count += built["target_token_count"]
        split = row.get("split") or "train"
        example: LabeledExample = (
            built["input_ids"], built["attention_mask"], built["labels"], language,
        )
        splits.setdefault(split, []).append(example)

        content_hash = row.get("content_hash") or row.get("public_id") or pair_hash
        input_checksum_parts.append(f"{content_hash}:{built['input_ids']}")
        label_checksum_parts.append(f"{content_hash}:{built['labels']}")

    if shuffle:
        for examples in splits.values():
            random.Random(seed).shuffle(examples)

    duplicate_prompt_count = sum(
        count - 1 for count in duplicate_prompt_hashes.values() if count > 1
    )
    duplicate_response_count = sum(
        count - 1 for count in duplicate_response_hashes.values() if count > 1
    )
    exact_prompt_response_duplicate_count = sum(
        count - 1 for count in exact_pair_hashes.values() if count > 1
    )

    input_stream_checksum_sha256 = hashlib.sha256(
        (f"{tokenizer_checksum}|{dataset_checksum}|" + "|".join(input_checksum_parts)).encode()
    ).hexdigest()
    label_stream_checksum_sha256 = hashlib.sha256(
        (
            f"{masking_thresholds.truncation_policy}|{template_checksum}|"
            + "|".join(label_checksum_parts)
        ).encode()
    ).hexdigest()

    total_records = len(records)
    coverage = {
        "total_records": total_records,
        "eligible_records": eligible_records,
        "invalid_records": invalid_records,
        "excluded_records": excluded_records,
        "train_count": len(splits["train"]),
        "validation_count": len(splits["validation"]),
        "test_count": len(splits["test"]),
        "language_distribution": language_distribution,
        "record_type_distribution": record_type_distribution,
        "source_distribution": source_distribution,
        "licence_distribution": licence_distribution,
        "system_prompt_count": system_prompt_count,
        "input_field_count": input_field_count,
        "synthesized_flat_chat_count": synthesized_flat_chat_count,
        "average_prompt_tokens": (
            sum(prompt_token_counts) / len(prompt_token_counts) if prompt_token_counts else 0.0
        ),
        "average_response_tokens": (
            sum(response_token_counts) / len(response_token_counts)
            if response_token_counts
            else 0.0
        ),
        "maximum_prompt_tokens": max(prompt_token_counts, default=0),
        "maximum_response_tokens": max(response_token_counts, default=0),
        "empty_response_count": empty_response_count,
        "duplicate_prompt_count": duplicate_prompt_count,
        "duplicate_response_count": duplicate_response_count,
        "exact_prompt_response_duplicate_count": exact_prompt_response_duplicate_count,
        "response_language_mismatch_count": response_language_mismatch_count,
        "special_token_collision_count": special_token_collision_count,
        "truncation_risk_count": truncation_risk_count,
        "maskable_assistant_token_count": maskable_assistant_token_count,
        "exclusion_reasons": exclusion_reasons,
        "input_stream_checksum_sha256": input_stream_checksum_sha256,
        "label_stream_checksum_sha256": label_stream_checksum_sha256,
    }
    return {
        "train": splits["train"],
        "validation": splits["validation"],
        "test": splits["test"],
        "coverage": coverage,
    }
