"""MB-04C: Model Profile Manager -- pure configuration, no AI, no
inference, no I/O. A static registry of what is actually known about
each model's capability, looked up by name.

Honesty discipline: only Qwen2.5-0.5B-Instruct has a `verified: True`
profile, because it is the only model this project has ever actually
run and measured (MB-04.1's load/memory numbers, MB-04A's and MB-04B's
real generation benchmarks -- ~1.7-2.0 tokens/sec on this CPU, weak
Tamil fluency, prone to echoing long structured prompts). TinyLlama's
profile is `verified: False` and says so directly -- it was named as
MB-04's fallback candidate but never downloaded or run in this
project, so its numbers are reasonable industry-published defaults
for its parameter count, not measurements. Any unrecognized model gets
a conservative, clearly-labeled generic profile.
"""

from __future__ import annotations

from typing import Any

PROFILES: dict[str, dict[str, Any]] = {
    "qwen2.5-0.5b-instruct": {
        "display_name": "Qwen2.5-0.5B-Instruct",
        "parameter_count": "0.5B",
        "max_context": 2048,
        "preferred_language": "english",
        "reasoning_quality": "low",
        "coding_quality": "low_to_medium",
        "measured_tokens_per_second": 1.85,
        "response_limits": {
            "recommended_min_tokens": 32,
            "recommended_max_tokens": 256,
            "max_tokens_ceiling": 512,
        },
        "known_issues": [
            "prone to echoing long structured prompts back instead of answering "
            "(see MB-04B completion report -- 4/10 real optimized responses were "
            "dominant echoes)",
            "weak Tamil fluency -- Tamil-script output achieved but often short "
            "and not clearly grammatical (see MB-04A completion report)",
            "very slow on this CPU hardware -- roughly 25-130 seconds per response "
            "at 48-128 tokens, measured directly across MB-04.1/MB-04A benchmarks",
        ],
        "verified": True,
        "source": "measured directly in MB-04.1 and MB-04A real-model benchmarks this project",
    },
    "tinyllama-1.1b-chat": {
        "display_name": "TinyLlama-1.1B-Chat",
        "parameter_count": "1.1B",
        "max_context": 2048,
        "preferred_language": "english",
        "reasoning_quality": "unknown_unverified",
        "coding_quality": "unknown_unverified",
        "measured_tokens_per_second": None,
        "response_limits": {
            "recommended_min_tokens": 32,
            "recommended_max_tokens": 256,
            "max_tokens_ceiling": 384,
        },
        "known_issues": [],
        "verified": False,
        "source": (
            "never downloaded or run in this project -- MB-04 named this only as a "
            "fallback candidate if Qwen2.5-0.5B failed provisioning, which it did not. "
            "These figures are conservative placeholders based on published parameter "
            "count alone, not real measurement."
        ),
    },
}

GENERIC_UNKNOWN_PROFILE: dict[str, Any] = {
    "display_name": "Unknown model",
    "parameter_count": "unknown",
    "max_context": 2048,
    "preferred_language": "unknown",
    "reasoning_quality": "unknown",
    "coding_quality": "unknown",
    "measured_tokens_per_second": None,
    "response_limits": {
        "recommended_min_tokens": 16,
        "recommended_max_tokens": 128,
        "max_tokens_ceiling": 256,
    },
    "known_issues": [],
    "verified": False,
    "source": "no profile registered for this model name -- conservative generic defaults applied",
}


def _normalize(name: str | None) -> str:
    return (name or "").strip().lower().replace(" ", "").replace("_", "-")


def get_profile(model_name: str | None, quantization: str | None = None) -> dict[str, Any]:
    """Fuzzy, deterministic lookup: normalizes the name (lowercase, no
    spaces/underscores) and checks for a substring match against the
    registry keys -- e.g. "Qwen2.5-0.5B-Instruct" registered from
    MB-04.1 matches "qwen2.5-0.5b-instruct" here. Falls back to the
    generic profile for anything unrecognized, never guesses."""

    normalized = _normalize(model_name)
    if not normalized:
        return dict(GENERIC_UNKNOWN_PROFILE)

    for key, profile in PROFILES.items():
        if key in normalized or normalized in key:
            result = dict(profile)
            result["matched_key"] = key
            result["quantization"] = quantization
            return result

    result = dict(GENERIC_UNKNOWN_PROFILE)
    result["matched_key"] = None
    result["quantization"] = quantization
    return result


def list_profiles() -> dict[str, dict[str, Any]]:
    return {key: dict(profile) for key, profile in PROFILES.items()}
