"""MB-29: Provider Model Catalog -- pure. Static catalog for external
providers (OpenAI, Anthropic, Gemini, OpenRouter), reusing MB-27's own
`provider_registry.known_providers()` as the authoritative set of
known provider keys rather than re-declaring a second, possibly
divergent list. No network call is required or made anywhere here.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.local_setup import capability_catalog
from core_model.mini_brain.provider_settings import provider_registry

_CATALOG: dict[str, dict[str, Any]] = {
    "openai": {
        "recommended_models": ["gpt-4o-mini", "gpt-4o", "o1-mini"],
        "context_window": 128_000,
        "reasoning_level": "high",
        "cost_hint": "medium",
        "coding_quality": "excellent",
        "tamil_quality": "good",
    },
    "anthropic": {
        "recommended_models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
        "context_window": 200_000,
        "reasoning_level": "high",
        "cost_hint": "medium",
        "coding_quality": "excellent",
        "tamil_quality": "good",
    },
    "gemini": {
        "recommended_models": ["gemini-1.5-flash", "gemini-1.5-pro"],
        "context_window": 1_000_000,
        "reasoning_level": "high",
        "cost_hint": "low",
        "coding_quality": "good",
        "tamil_quality": "fair",
    },
    "openrouter": {
        "recommended_models": ["openrouter/auto", "meta-llama/llama-3.1-8b-instruct"],
        "context_window": 128_000,
        "reasoning_level": "medium",
        "cost_hint": "low",
        "coding_quality": "good",
        "tamil_quality": "fair",
    },
}

_EXTERNAL_PROVIDER_KEYS = ("openai", "anthropic", "gemini", "openrouter")


def known_external_providers() -> tuple[str, ...]:
    # Cross-check against MB-27's own registry rather than trusting
    # this module's own hardcoded tuple in isolation.
    return tuple(key for key in _EXTERNAL_PROVIDER_KEYS if provider_registry.is_known_provider(key))


def catalog_entry(provider_key: str) -> dict[str, Any] | None:
    if provider_key not in _CATALOG:
        return None
    raw = _CATALOG[provider_key]
    return {
        "provider_key": provider_key,
        "recommended_models": list(raw["recommended_models"]),
        "context_window": raw["context_window"],
        "reasoning_level": capability_catalog.label(capability_catalog.REASONING_LEVELS, raw["reasoning_level"]),
        "cost_hint": capability_catalog.label(capability_catalog.COST_HINTS, raw["cost_hint"]),
        "coding_quality": capability_catalog.label(capability_catalog.SUPPORT_LEVELS, raw["coding_quality"]),
        "tamil_quality": capability_catalog.label(capability_catalog.SUPPORT_LEVELS, raw["tamil_quality"]),
    }


def full_catalog() -> dict[str, Any]:
    return {"providers": [catalog_entry(key) for key in known_external_providers()]}
