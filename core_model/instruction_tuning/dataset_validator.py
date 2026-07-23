"""Deterministic per-record-type instruction-dataset validation.

Operates on plain row dicts (as read from ``dataset_records`` joins) plus the
record's parsed ``metadata_json``. Never coerces invalid structure silently —
every rejection carries one fixed, explicit reason code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VALID_ROLES = ("system", "user", "assistant")

PREFERENCE_EXCLUSION_REASON = "preference_optimization_out_of_scope_phase12"


@dataclass(frozen=True)
class DatasetValidationThresholds:
    min_prompt_chars: int = 1
    min_response_chars: int = 1


def _text(value: Any) -> str:
    return (value or "").strip()


def _validate_instruction(row: dict, metadata: dict, thresholds: DatasetValidationThresholds):
    instruction = _text(row.get("instruction"))
    output_text = _text(row.get("output_text"))
    if not instruction or len(instruction) < thresholds.min_prompt_chars:
        return {"valid": False, "reason": "missing_instruction"}
    if not output_text or len(output_text) < thresholds.min_response_chars:
        return {"valid": False, "reason": "missing_output_text"}
    return {
        "valid": True,
        "reason": None,
        "system_text": _text(metadata.get("system")) or None,
        "prompt_text": instruction,
        "input_text": _text(row.get("input_text")) or None,
        "response_text": output_text,
    }


def _validate_chat(row: dict, metadata: dict, thresholds: DatasetValidationThresholds):
    turns = metadata.get("turns")
    if turns is not None:
        if not isinstance(turns, list) or not turns:
            return {"valid": False, "reason": "invalid_turn_structure"}
        parsed: list[dict[str, str]] = []
        for turn in turns:
            if not isinstance(turn, dict):
                return {"valid": False, "reason": "invalid_turn_structure"}
            role = turn.get("role")
            content = _text(turn.get("content"))
            if role not in VALID_ROLES:
                return {"valid": False, "reason": "invalid_turn_structure"}
            if not content:
                return {"valid": False, "reason": "empty_turn_content"}
            parsed.append({"role": role, "content": content})
        if parsed[-1]["role"] != "assistant":
            return {"valid": False, "reason": "missing_assistant_final_turn"}
        if not any(turn["role"] == "user" for turn in parsed):
            return {"valid": False, "reason": "no_user_turn"}
        system_turns = [turn["content"] for turn in parsed if turn["role"] == "system"]
        history_turns = parsed[:-1]
        history_text = "\n".join(
            f"{turn['role']}: {turn['content']}"
            for turn in history_turns
            if turn["role"] != "system"
        )
        return {
            "valid": True,
            "reason": None,
            "system_text": "\n".join(system_turns) or None,
            "prompt_text": history_text,
            "input_text": None,
            "response_text": parsed[-1]["content"],
            "synthesized_from_flat_fields": False,
        }
    input_text = _text(row.get("input_text"))
    output_text = _text(row.get("output_text"))
    if not input_text:
        return {"valid": False, "reason": "no_user_turn"}
    if not output_text:
        return {"valid": False, "reason": "missing_assistant_final_turn"}
    return {
        "valid": True,
        "reason": None,
        "system_text": _text(metadata.get("system")) or None,
        "prompt_text": input_text,
        "input_text": None,
        "response_text": output_text,
        "synthesized_from_flat_fields": True,
    }


def _validate_translation(row: dict, metadata: dict, thresholds: DatasetValidationThresholds):
    source_language = metadata.get("source_language")
    target_language = metadata.get("target_language")
    if not source_language or not target_language:
        return {"valid": False, "reason": "missing_language_pair_metadata"}
    input_text = _text(row.get("input_text"))
    output_text = _text(row.get("output_text"))
    if not input_text or not output_text:
        return {"valid": False, "reason": "missing_source_or_target_text"}
    warnings = []
    if source_language == target_language:
        warnings.append("source_target_language_identical")
    instruction = f"Translate from {source_language} to {target_language}: {input_text}"
    return {
        "valid": True,
        "reason": None,
        "system_text": _text(metadata.get("system")) or None,
        "prompt_text": instruction,
        "input_text": None,
        "response_text": output_text,
        "warnings": warnings,
    }


def _validate_tanglish_pair(row: dict, metadata: dict, thresholds: DatasetValidationThresholds):
    input_text = _text(row.get("input_text"))
    normalized_input = _text(row.get("normalized_input"))
    output_text = _text(row.get("output_text"))
    if not input_text:
        return {"valid": False, "reason": "missing_tanglish_input"}
    if not normalized_input and not output_text:
        return {"valid": False, "reason": "missing_normalized_or_output"}
    return {
        "valid": True,
        "reason": None,
        "system_text": _text(metadata.get("system")) or None,
        "prompt_text": input_text,
        "input_text": normalized_input or None,
        "response_text": output_text or normalized_input,
    }


def _validate_safety(row: dict, metadata: dict, thresholds: DatasetValidationThresholds):
    input_text = _text(row.get("input_text"))
    output_text = _text(row.get("output_text"))
    if not input_text:
        return {"valid": False, "reason": "missing_safety_prompt"}
    if not output_text:
        return {"valid": False, "reason": "missing_safety_response"}
    return {
        "valid": True,
        "reason": None,
        "system_text": _text(metadata.get("system")) or None,
        "prompt_text": input_text,
        "input_text": None,
        "response_text": output_text,
    }


def _validate_preference(row: dict, metadata: dict, thresholds: DatasetValidationThresholds):
    chosen = _text(metadata.get("chosen_output")) or _text(row.get("output_text"))
    rejected = _text(metadata.get("rejected_output"))
    if not chosen or not rejected:
        return {"valid": False, "reason": "missing_chosen_or_rejected_output"}
    return {
        "valid": True,
        "reason": None,
        "system_text": _text(metadata.get("system")) or None,
        "prompt_text": _text(row.get("instruction")) or _text(row.get("input_text")),
        "input_text": None,
        "response_text": chosen,
        "excluded": True,
        "exclusion_reason": PREFERENCE_EXCLUSION_REASON,
    }


_VALIDATORS = {
    "instruction": _validate_instruction,
    "chat": _validate_chat,
    "translation": _validate_translation,
    "tanglish_pair": _validate_tanglish_pair,
    "safety": _validate_safety,
    "preference": _validate_preference,
}


def validate_record(
    row: dict[str, Any], metadata: dict[str, Any], thresholds: DatasetValidationThresholds
) -> dict[str, Any]:
    """Validate one dataset record for instruction-tuning eligibility.

    Returns a dict always containing ``valid`` and ``reason``; on success also
    ``system_text``/``prompt_text``/``input_text``/``response_text`` (the raw
    structured pieces, before templating), plus optional ``excluded`` +
    ``exclusion_reason`` (set for ``preference`` records, which validate but
    never enter a training batch) and ``warnings``.
    """

    record_type = row.get("record_type")
    validator = _VALIDATORS.get(record_type)
    if validator is None:
        return {"valid": False, "reason": "unsupported_record_type"}
    result = validator(row, metadata, thresholds)
    result.setdefault("warnings", [])
    result.setdefault("excluded", False)
    result.setdefault("exclusion_reason", None)
    result.setdefault("synthesized_from_flat_fields", False)
    return result
