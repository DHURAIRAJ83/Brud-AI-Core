"""MB-21: pluggable external AI provider client contract + adapters.

`ProviderClientProtocol` is a structural `Protocol`, mirroring MB-04's
own `InferenceBackend` and MB-15's own `VisionInferenceBackend` exactly
-- any class with these methods satisfies it, with no shared base
class and no registry of implementations to keep in sync.
`MiniBrainExternalAiGatewayService` only ever talks to this Protocol,
never to a concrete client class by name.

Credentials are read from environment variables only, exactly once at
construction time -- never stored in the database, never logged, never
included in any dispatch report. `OpenRouterProviderClient.is_available()`
never makes a network call to check availability; it only checks
whether an API key is configured. `dispatch()` reuses `httpx` (already
a real dependency of this project, currently used only by its own test
suite) rather than adding a new HTTP library.

Reuses `BackendUnavailableError` from MB-04's own
`mini_brain_inference_backend.py` directly -- the same exception class
every other Mini Brain provider-integration phase (MB-04, MB-15)
already raises for "the real thing isn't configured here", never a
second exception type for the same concept.
"""

from __future__ import annotations

import os
import time
from typing import Any, Protocol

from backend.services.mini_brain_inference_backend import BackendUnavailableError

OPENROUTER_API_KEY_ENV_VAR = "BRUD_EXTERNAL_AI_OPENROUTER_API_KEY"
OPENROUTER_DEFAULT_MODEL_ENV_VAR = "BRUD_EXTERNAL_AI_OPENROUTER_MODEL"
DEFAULT_OPENROUTER_MODEL = "openrouter/auto"
DEFAULT_TIMEOUT_SECONDS = 30.0


class ProviderClientProtocol(Protocol):
    provider_key: str

    def is_available(self) -> bool: ...

    def dispatch(self, *, prompt: str, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]: ...


def _result(
    *, status: str, text: str | None, latency_ms: float, error_message: str | None = None,
) -> dict[str, Any]:
    return {"status": status, "text": text, "latency_ms": latency_ms, "error_message": error_message}


class OpenRouterProviderClient:
    """Real adapter for OpenRouter's chat-completions API. Genuinely
    dispatches an HTTP request when an API key is configured -- but no
    `BRUD_EXTERNAL_AI_OPENROUTER_API_KEY` is set in this environment,
    so `is_available()` truthfully returns `False` here today, exactly
    like MB-15's vision backends report unavailable without a real
    model file present."""

    provider_key = "openrouter"
    _endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get(OPENROUTER_API_KEY_ENV_VAR)
        self._model = model or os.environ.get(OPENROUTER_DEFAULT_MODEL_ENV_VAR) or DEFAULT_OPENROUTER_MODEL

    def is_available(self) -> bool:
        return bool(self._api_key)

    def dispatch(self, *, prompt: str, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
        if not self._api_key:
            return _result(
                status="unavailable", text=None, latency_ms=0.0,
                error_message=f"{OPENROUTER_API_KEY_ENV_VAR} is not configured in this environment",
            )
        try:
            import httpx
        except ImportError:
            return _result(
                status="unavailable", text=None, latency_ms=0.0, error_message="httpx is not installed",
            )

        started = time.perf_counter()
        try:
            response = httpx.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": self._model, "messages": [{"role": "user", "content": prompt}]},
                timeout=timeout_seconds,
            )
        except httpx.TimeoutException:
            return _result(
                status="timeout", text=None, latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=f"request exceeded {timeout_seconds}s timeout",
            )
        except httpx.HTTPError as exc:
            return _result(
                status="failed", text=None, latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=str(exc),
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)

        if response.status_code == 429:
            return _result(status="rate_limited", text=None, latency_ms=latency_ms, error_message="rate limited (HTTP 429)")
        if response.status_code >= 400:
            return _result(
                status="failed", text=None, latency_ms=latency_ms,
                error_message=f"HTTP {response.status_code}",
            )
        try:
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            return _result(
                status="failed", text=None, latency_ms=latency_ms,
                error_message=f"could not parse provider response: {exc}",
            )
        return _result(status="success", text=text, latency_ms=latency_ms)


class MockProviderClient:
    """Deterministic in-memory client for tests -- never makes a
    network call. Returns a fixed, caller-supplied response or a
    default canned response derived from the prompt itself."""

    def __init__(
        self, *, provider_key: str = "mock", canned_text: str | None = None, status: str = "success",
        latency_ms: float = 5.0, available: bool = True,
    ) -> None:
        self.provider_key = provider_key
        self._canned_text = canned_text
        self._status = status
        self._latency_ms = latency_ms
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def dispatch(self, *, prompt: str, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
        del timeout_seconds
        if not self._available:
            return _result(
                status="unavailable", text=None, latency_ms=0.0,
                error_message=f"mock provider '{self.provider_key}' is configured unavailable for this test",
            )
        if self._status != "success":
            return _result(
                status=self._status, text=None, latency_ms=self._latency_ms,
                error_message=f"mock provider '{self.provider_key}' configured to return status '{self._status}'",
            )
        text = self._canned_text if self._canned_text is not None else f"[mock:{self.provider_key}] response to: {prompt[:80]}"
        return _result(status="success", text=text, latency_ms=self._latency_ms)


PROVIDER_FACTORIES: dict[str, type] = {"openrouter": OpenRouterProviderClient}


def client_for_provider(provider_key: str) -> ProviderClientProtocol:
    factory = PROVIDER_FACTORIES.get(provider_key)
    if factory is None:
        raise BackendUnavailableError(f"no provider client implementation registered for provider '{provider_key}'")
    return factory()


__all__ = [
    "ProviderClientProtocol", "BackendUnavailableError", "OpenRouterProviderClient", "MockProviderClient",
    "PROVIDER_FACTORIES", "client_for_provider", "OPENROUTER_API_KEY_ENV_VAR", "DEFAULT_TIMEOUT_SECONDS",
]
