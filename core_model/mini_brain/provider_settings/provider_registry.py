"""MB-27: Provider Registry -- pure. The fixed, module-level catalogue
of every provider MB-27 knows about, mirroring
`core_model.mini_brain.plugin_governance.permission_scope_registry`'s
exact dict-of-dicts + accessor-function shape.
"""

from __future__ import annotations

from typing import Any

PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "openrouter": {
        "provider_type": "external_ai",
        "required_secrets": ["api_key"],
        "optional_settings": {"model": "openrouter/auto"},
        "default_enabled": False,
        "capability_flags": {"chat": True, "stt": False, "tts": False},
        "description": "OpenRouter -- multi-model chat completion gateway.",
    },
    "openai": {
        "provider_type": "external_ai",
        "required_secrets": ["api_key"],
        "optional_settings": {"model": "gpt-4o-mini", "organization": None},
        "default_enabled": False,
        "capability_flags": {"chat": True, "stt": False, "tts": False},
        "description": "OpenAI -- direct API access.",
    },
    "anthropic": {
        "provider_type": "external_ai",
        "required_secrets": ["api_key"],
        "optional_settings": {"model": "claude-3-5-haiku-latest"},
        "default_enabled": False,
        "capability_flags": {"chat": True, "stt": False, "tts": False},
        "description": "Anthropic -- direct API access.",
    },
    "gemini": {
        "provider_type": "external_ai",
        "required_secrets": ["api_key"],
        "optional_settings": {"model": "gemini-1.5-flash"},
        "default_enabled": False,
        "capability_flags": {"chat": True, "stt": False, "tts": False},
        "description": "Google Gemini -- direct API access.",
    },
    "faster_whisper": {
        "provider_type": "speech",
        "required_secrets": [],
        "optional_settings": {"model_size": "base"},
        "default_enabled": True,
        "capability_flags": {"chat": False, "stt": True, "tts": False},
        "description": "Local faster-whisper STT backend -- no API key required.",
    },
    "coqui_tts": {
        "provider_type": "speech",
        "required_secrets": [],
        "optional_settings": {"voice": "default"},
        "default_enabled": True,
        "capability_flags": {"chat": False, "stt": False, "tts": True},
        "description": "Local Coqui TTS backend -- no API key required.",
    },
    "local_llm": {
        "provider_type": "local_model",
        "required_secrets": [],
        # MB-28 disclosed edit: additive expansion of this dict's keys
        # only -- no schema change (uses the existing free-form
        # config_json column), backward compatible with any setting
        # row created before this expansion (missing keys read as
        # None/absent, same as model_path always did in MB-27).
        "optional_settings": {
            "model_path": None,
            "context_length": 2048,
            "max_tokens": 512,
            "temperature": 0.3,
            "threads": 4,
            # MB-29 disclosed edit: one further additive key, same
            # pattern as MB-28's own expansion above -- admin-configured
            # extra directories model_scanner.py should also search,
            # required by MB-29's own spec section 4.
            "additional_model_dirs": [],
        },
        "default_enabled": False,
        "capability_flags": {"chat": True, "stt": False, "tts": False},
        "description": "Local llama-cpp-python model -- real inference wired in MB-28.",
    },
}


def known_providers() -> tuple[str, ...]:
    return tuple(PROVIDER_REGISTRY.keys())


def provider_definition(provider_key: str) -> dict[str, Any] | None:
    return PROVIDER_REGISTRY.get(provider_key)


def is_known_provider(provider_key: str) -> bool:
    return provider_key in PROVIDER_REGISTRY


def required_secrets_for(provider_key: str) -> list[str]:
    definition = PROVIDER_REGISTRY.get(provider_key)
    return list(definition["required_secrets"]) if definition else []


def default_enabled_for(provider_key: str) -> bool:
    definition = PROVIDER_REGISTRY.get(provider_key)
    return bool(definition["default_enabled"]) if definition else False


def provider_type_for(provider_key: str) -> str | None:
    definition = PROVIDER_REGISTRY.get(provider_key)
    return definition["provider_type"] if definition else None
