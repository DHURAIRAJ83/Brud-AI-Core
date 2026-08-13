"""MB-09: Multi-Provider Consensus Planner -- pure. Prepares a
Provider Request (topic, prompt, cited evidence, which providers) and,
once an admin has separately run those providers externally and
supplied their outputs back, builds a consensus report from
already-computed duplicate/conflict groupings.

Confirmed by audit before writing this phase: no external AI provider
integration (Anthropic/Claude, OpenAI, Gemini, OpenRouter) exists
anywhere in this codebase. This module never calls one -- it only ever
shapes a request an admin runs manually, and analyzes results the
admin supplies back. Duplicate/conflict detection over the supplied
outputs is done by the service layer calling the existing, real
`ExternalDatasetDuplicateService` (Phase 12) -- this module only
turns those already-computed groupings into a confidence report, it
never re-implements duplicate or conflict detection itself.
"""

from __future__ import annotations

from typing import Any

SUPPORTED_PROVIDERS = ("claude", "openai", "gemini", "openrouter", "local_only")


def build_provider_request(
    *, topic: str, evidence: dict[str, Any], requested_providers: list[str],
) -> dict[str, Any]:
    unknown_providers = [p for p in requested_providers if p not in SUPPORTED_PROVIDERS]
    return {
        "topic": topic,
        "prompt": f"Provide a factual, well-sourced answer about: {topic}",
        "context_evidence": evidence,
        "requested_providers": [p for p in requested_providers if p in SUPPORTED_PROVIDERS],
        "unknown_providers": unknown_providers,
        "valid": not unknown_providers and bool(requested_providers),
        "disclosure": (
            "Brud AI does not call any of these providers automatically -- an admin must run "
            "them externally and supply the outputs back for comparison"
        ),
    }


def build_consensus(
    *, provider_outputs: list[dict[str, Any]], duplicate_groups: list[list[str]],
    conflict_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    provider_count = len(provider_outputs)
    duplicated_providers = {provider for group in duplicate_groups for provider in group}
    has_conflicts = bool(conflict_groups)

    if provider_count == 0:
        confidence = "None"
    elif has_conflicts:
        confidence = "Low"
    elif provider_count >= 2 and len(duplicated_providers) >= 2:
        confidence = "High"
    elif provider_count >= 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "provider_count": provider_count,
        "duplicate_groups": duplicate_groups,
        "conflict_groups": conflict_groups,
        "has_conflicts": has_conflicts,
        "confidence": confidence,
        "traceable_outputs": [
            {"provider": output["provider"], "output_text": output["output_text"]}
            for output in provider_outputs
        ],
    }
