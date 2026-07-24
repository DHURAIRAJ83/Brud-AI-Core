"""Deterministic compatibility checks between a release candidate's
model configuration, checkpoint, tokenizer, dataset lineage, instruction
template, and evaluation suite.

Never bundles or compares artifacts that fail these checks — an
``incompatible`` result must block release-candidate eligibility.
"""

from __future__ import annotations

from typing import Any

COMPATIBLE = "compatible"
COMPATIBLE_WITH_WARNINGS = "compatible_with_warnings"
INCOMPATIBLE = "incompatible"
NOT_ASSESSED = "not_assessed"


def assess_tokenizer_model_compatibility(
    *,
    model_vocabulary_size: int,
    tokenizer_vocabulary_size: int,
    model_special_token_ids: dict[str, int],
    tokenizer_special_token_ids: dict[str, int],
    model_context_length: int,
    max_supported_context: int,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    vocab_ok = model_vocabulary_size == tokenizer_vocabulary_size
    checks.append({
        "check": "vocabulary_size_match", "status": "pass" if vocab_ok else "fail",
        "model_vocabulary_size": model_vocabulary_size,
        "tokenizer_vocabulary_size": tokenizer_vocabulary_size,
    })
    mismatched_tokens = [
        name for name, token_id in model_special_token_ids.items()
        if tokenizer_special_token_ids.get(name) != token_id
    ]
    checks.append({
        "check": "special_token_id_match",
        "status": "pass" if not mismatched_tokens else "fail",
        "mismatched_tokens": mismatched_tokens,
    })
    context_ok = model_context_length <= max_supported_context
    checks.append({
        "check": "context_length_supported", "status": "pass" if context_ok else "fail",
        "model_context_length": model_context_length,
        "max_supported_context": max_supported_context,
    })
    if not vocab_ok or mismatched_tokens:
        status = INCOMPATIBLE
    elif not context_ok:
        status = COMPATIBLE_WITH_WARNINGS
    else:
        status = COMPATIBLE
    return {"status": status, "checks": checks}


def assess_checkpoint_config_compatibility(
    *, checkpoint_config_checksum: str | None, registered_config_checksum: str | None
) -> dict[str, Any]:
    if not checkpoint_config_checksum or not registered_config_checksum:
        return {"status": NOT_ASSESSED, "reason": "checksum unavailable"}
    matches = checkpoint_config_checksum == registered_config_checksum
    return {"status": COMPATIBLE if matches else INCOMPATIBLE, "matches": matches}


def assess_lineage_compatibility(
    *, candidate_tokenizer_version_public_id: str, checkpoint_tokenizer_version_public_id: str
) -> dict[str, Any]:
    matches = candidate_tokenizer_version_public_id == checkpoint_tokenizer_version_public_id
    return {"status": COMPATIBLE if matches else INCOMPATIBLE, "matches": matches}


def assess_instruction_template_compatibility(
    *, required_special_tokens: list[str], tokenizer_special_tokens: list[str]
) -> dict[str, Any]:
    if not required_special_tokens:
        return {"status": NOT_ASSESSED, "missing_tokens": []}
    missing = [token for token in required_special_tokens if token not in tokenizer_special_tokens]
    return {"status": COMPATIBLE if not missing else INCOMPATIBLE, "missing_tokens": missing}


def assess_evaluation_lineage_compatibility(
    *, evaluation_candidate_core_model_version_public_id: str | None,
    expected_core_model_version_public_id: str,
) -> dict[str, Any]:
    if not evaluation_candidate_core_model_version_public_id:
        return {"status": NOT_ASSESSED, "matches": False}
    matches = (
        evaluation_candidate_core_model_version_public_id == expected_core_model_version_public_id
    )
    return {"status": COMPATIBLE if matches else INCOMPATIBLE, "matches": matches}


def assess_release_family_policy(
    *, compatibility_policy: dict[str, Any], candidate_summary: dict[str, Any]
) -> dict[str, Any]:
    """``compatibility_policy`` is a small, bounded JSON dict of family-level
    constraints (e.g. ``{"required_languages": ["ta","en"]}``) — never
    arbitrary code, never a claim of exhaustive policy coverage."""

    required_languages = set(compatibility_policy.get("required_languages", []))
    supported_languages = set(candidate_summary.get("supported_languages", []))
    missing_languages = sorted(required_languages - supported_languages)
    if not compatibility_policy:
        return {"status": NOT_ASSESSED, "missing_languages": []}
    return {
        "status": COMPATIBLE if not missing_languages else COMPATIBLE_WITH_WARNINGS,
        "missing_languages": missing_languages,
    }


def overall_compatibility(results: list[dict[str, Any]]) -> str:
    """Aggregate several per-dimension compatibility results into one status."""

    statuses = [result["status"] for result in results]
    if INCOMPATIBLE in statuses:
        return INCOMPATIBLE
    if all(status == NOT_ASSESSED for status in statuses):
        return NOT_ASSESSED
    if COMPATIBLE_WITH_WARNINGS in statuses:
        return COMPATIBLE_WITH_WARNINGS
    return COMPATIBLE
