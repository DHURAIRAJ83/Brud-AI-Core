"""MB-27: provider-specific connection-test adapters for Secrets &
Provider Settings.

`ProviderConnectionAdapterProtocol` is a **new**, distinct structural
`Protocol` from MB-21's `ProviderClientProtocol`
(`backend/services/external_ai_provider_client.py`) -- not a reuse of
it. MB-21's clients read their API key from an environment variable
once, at construction. MB-27 stores admin-configured, Fernet-encrypted
secrets in the database and decrypts them transiently, in memory, only
for the duration of a single test-connection call -- the decrypted key
must be an explicit per-call parameter, never something an adapter
reads from `os.environ` at construction time. This is a genuine
architectural mismatch with MB-21's contract, not a style choice, so
this module reuses only the *shape* MB-21 already proved (a
`{"status", "latency_ms", "error_message"}` result dict, the same
`success`/`unavailable`/`timeout`/`failed`/`rate_limited` status
vocabulary, real `httpx`-based calls with real timeout handling) --
never the literal `OpenRouterProviderClient` class itself.

Every adapter here performs the cheapest real key-validation call each
provider's API offers -- never a full chat completion -- to keep a
"test connection" action fast and quota-safe:
  - OpenAI:      GET  /v1/models                          (list, no completion cost)
  - Gemini:      GET  /v1beta/models?key=<key>             (list, free, key as query param)
  - OpenRouter:  GET  /api/v1/auth/key                     (OpenRouter's own lightweight key-check endpoint)
  - Anthropic:   POST /v1/messages with max_tokens=1        (Anthropic has no zero-cost key-check
                                                              endpoint -- this is disclosed honestly
                                                              as a trivial-but-nonzero-cost probe,
                                                              never claimed free)

Honest limitation: these adapters are written against each provider's
publicly documented API shape but have NOT been exercised against a
live API with a real key in this session's environment (no real
credentials available) -- only `MockConnectionAdapter` is exercised by
this project's own tests and smoke test.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

DEFAULT_TEST_TIMEOUT_SECONDS = 10.0
MAX_TEST_TIMEOUT_SECONDS = 30.0


class ProviderConnectionAdapterProtocol(Protocol):
    provider_key: str

    def test_connection(self, *, api_key: str | None, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS) -> dict[str, Any]: ...


def _result(*, status: str, latency_ms: float, error_message: str | None = None) -> dict[str, Any]:
    return {"status": status, "latency_ms": latency_ms, "error_message": error_message}


def _missing_key_result() -> dict[str, Any]:
    return _result(status="missing_key", latency_ms=0.0, error_message="no API key is configured for this provider")


def _import_httpx():
    try:
        import httpx

        return httpx
    except ImportError:
        return None


class OpenAiConnectionAdapter:
    provider_key = "openai"
    _endpoint = "https://api.openai.com/v1/models"

    def test_connection(self, *, api_key: str | None, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        if not api_key:
            return _missing_key_result()
        httpx = _import_httpx()
        if httpx is None:
            return _result(status="unavailable", latency_ms=0.0, error_message="httpx is not installed")

        started = time.perf_counter()
        try:
            response = httpx.get(
                self._endpoint, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout_seconds,
            )
        except httpx.TimeoutException:
            return _result(
                status="timeout", latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=f"request exceeded {timeout_seconds}s timeout",
            )
        except httpx.HTTPError as exc:
            return _result(status="failed", latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message=str(exc))

        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        if response.status_code == 429:
            return _result(status="rate_limited", latency_ms=latency_ms, error_message="rate limited (HTTP 429)")
        if response.status_code in (401, 403):
            return _result(status="failed", latency_ms=latency_ms, error_message=f"authentication failed (HTTP {response.status_code})")
        if response.status_code >= 400:
            return _result(status="failed", latency_ms=latency_ms, error_message=f"HTTP {response.status_code}")
        return _result(status="success", latency_ms=latency_ms)


class AnthropicConnectionAdapter:
    provider_key = "anthropic"
    _endpoint = "https://api.anthropic.com/v1/messages"
    _api_version = "2023-06-01"

    def test_connection(self, *, api_key: str | None, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        if not api_key:
            return _missing_key_result()
        httpx = _import_httpx()
        if httpx is None:
            return _result(status="unavailable", latency_ms=0.0, error_message="httpx is not installed")

        started = time.perf_counter()
        try:
            response = httpx.post(
                self._endpoint,
                headers={"x-api-key": api_key, "anthropic-version": self._api_version, "Content-Type": "application/json"},
                json={"model": "claude-3-5-haiku-latest", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
                timeout=timeout_seconds,
            )
        except httpx.TimeoutException:
            return _result(
                status="timeout", latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=f"request exceeded {timeout_seconds}s timeout",
            )
        except httpx.HTTPError as exc:
            return _result(status="failed", latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message=str(exc))

        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        if response.status_code == 429:
            return _result(status="rate_limited", latency_ms=latency_ms, error_message="rate limited (HTTP 429)")
        if response.status_code in (401, 403):
            return _result(status="failed", latency_ms=latency_ms, error_message=f"authentication failed (HTTP {response.status_code})")
        if response.status_code >= 400:
            return _result(status="failed", latency_ms=latency_ms, error_message=f"HTTP {response.status_code}")
        return _result(status="success", latency_ms=latency_ms)


class GeminiConnectionAdapter:
    provider_key = "gemini"
    _endpoint = "https://generativelanguage.googleapis.com/v1beta/models"

    def test_connection(self, *, api_key: str | None, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        if not api_key:
            return _missing_key_result()
        httpx = _import_httpx()
        if httpx is None:
            return _result(status="unavailable", latency_ms=0.0, error_message="httpx is not installed")

        started = time.perf_counter()
        try:
            response = httpx.get(self._endpoint, params={"key": api_key}, timeout=timeout_seconds)
        except httpx.TimeoutException:
            return _result(
                status="timeout", latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=f"request exceeded {timeout_seconds}s timeout",
            )
        except httpx.HTTPError as exc:
            return _result(status="failed", latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message=str(exc))

        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        if response.status_code == 429:
            return _result(status="rate_limited", latency_ms=latency_ms, error_message="rate limited (HTTP 429)")
        if response.status_code in (400, 401, 403):
            return _result(status="failed", latency_ms=latency_ms, error_message=f"authentication failed (HTTP {response.status_code})")
        if response.status_code >= 400:
            return _result(status="failed", latency_ms=latency_ms, error_message=f"HTTP {response.status_code}")
        return _result(status="success", latency_ms=latency_ms)


class OpenRouterConnectionAdapter:
    provider_key = "openrouter"
    _endpoint = "https://openrouter.ai/api/v1/auth/key"

    def test_connection(self, *, api_key: str | None, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        if not api_key:
            return _missing_key_result()
        httpx = _import_httpx()
        if httpx is None:
            return _result(status="unavailable", latency_ms=0.0, error_message="httpx is not installed")

        started = time.perf_counter()
        try:
            response = httpx.get(self._endpoint, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout_seconds)
        except httpx.TimeoutException:
            return _result(
                status="timeout", latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=f"request exceeded {timeout_seconds}s timeout",
            )
        except httpx.HTTPError as exc:
            return _result(status="failed", latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message=str(exc))

        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        if response.status_code == 429:
            return _result(status="rate_limited", latency_ms=latency_ms, error_message="rate limited (HTTP 429)")
        if response.status_code in (401, 403):
            return _result(status="failed", latency_ms=latency_ms, error_message=f"authentication failed (HTTP {response.status_code})")
        if response.status_code >= 400:
            return _result(status="failed", latency_ms=latency_ms, error_message=f"HTTP {response.status_code}")
        return _result(status="success", latency_ms=latency_ms)


class LocalBackendConnectionAdapter:
    """For faster_whisper/coqui_tts: no network at all -- reuses
    MB-26's own `is_available()` probes directly, never reimplemented."""

    def __init__(self, *, provider_key: str) -> None:
        self.provider_key = provider_key

    def test_connection(self, *, api_key: str | None, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        del api_key, timeout_seconds
        from core_model.mini_brain.voice_runtime import coqui_tts_backend, faster_whisper_backend

        if self.provider_key == "faster_whisper":
            available = faster_whisper_backend.is_available()
        elif self.provider_key == "coqui_tts":
            available = coqui_tts_backend.is_available()
        else:
            available = False

        if available:
            return _result(status="success", latency_ms=0.0)
        return _result(status="unavailable", latency_ms=0.0, error_message=f"{self.provider_key} is not installed in this environment")


class LocalLlmConnectionAdapter:
    """MB-28 disclosed edit: this was an unconditional placeholder in
    MB-27 (no inference existed yet to check). Delegates to the real
    `LlamaCppMiniBrainAdapter.is_available()` path-confinement + import
    check MB-28 wires up -- never a network call, so `timeout_seconds`
    is still unused.

    `ProviderConnectionAdapterProtocol`/`adapter_for_provider()` never
    thread a `Settings` instance through to adapters (a pre-existing
    MB-27 constraint this narrow edit does not change) -- the zero-arg
    factory path used by the real `MiniBrainProviderSettingsService.
    test_connection()` therefore resolves the process's real
    environment-driven `Settings()`, exactly what a genuine admin's
    "Test Connection" click means in production. The optional
    `settings` constructor parameter exists solely so tests can verify
    this adapter's logic against a temporary database without
    constructing it through the zero-arg factory.
    """

    provider_key = "local_llm"

    def __init__(self, *, settings: Any = None) -> None:
        self._settings = settings

    def test_connection(self, *, api_key: str | None, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        del api_key, timeout_seconds
        from backend.core.config import Settings
        from backend.core.json_utils import loads_json
        from backend.database.repositories.mini_brain_provider_settings import MiniBrainProviderSettingsRepository
        from backend.services.mini_brain_llm_adapter import LlamaCppMiniBrainAdapter

        settings = self._settings or Settings()
        repository = MiniBrainProviderSettingsRepository(settings.resolved_database_path)
        with repository.transaction() as connection:
            setting_row = repository.get_setting_by_provider_key(connection, "local_llm")
        if setting_row is None:
            return _result(status="unavailable", latency_ms=0.0, error_message="local_llm provider is not configured")

        config = loads_json(setting_row["config_json"])
        adapter = LlamaCppMiniBrainAdapter(settings=settings, model_path=config.get("model_path"))
        if adapter.is_available():
            return _result(status="success", latency_ms=0.0)
        return _result(status="unavailable", latency_ms=0.0, error_message="local model is not available (llama-cpp-python missing or no configured model file)")


class MockConnectionAdapter:
    """Deterministic in-memory adapter for tests -- never makes a
    network call."""

    def __init__(
        self, *, provider_key: str = "mock", status: str = "success",
        latency_ms: float = 5.0, error_message: str | None = None,
    ) -> None:
        self.provider_key = provider_key
        self._status = status
        self._latency_ms = latency_ms
        self._error_message = error_message

    def test_connection(self, *, api_key: str | None, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        del timeout_seconds
        if not api_key and self._status == "success":
            return _missing_key_result()
        return _result(status=self._status, latency_ms=self._latency_ms, error_message=self._error_message)


CONNECTION_ADAPTER_FACTORIES: dict[str, Any] = {
    "openai": OpenAiConnectionAdapter,
    "anthropic": AnthropicConnectionAdapter,
    "gemini": GeminiConnectionAdapter,
    "openrouter": OpenRouterConnectionAdapter,
    "faster_whisper": lambda: LocalBackendConnectionAdapter(provider_key="faster_whisper"),
    "coqui_tts": lambda: LocalBackendConnectionAdapter(provider_key="coqui_tts"),
    "local_llm": LocalLlmConnectionAdapter,
}


def adapter_for_provider(provider_key: str) -> ProviderConnectionAdapterProtocol:
    factory = CONNECTION_ADAPTER_FACTORIES.get(provider_key)
    if factory is None:
        raise ValueError(f"no connection adapter registered for provider '{provider_key}'")
    return factory()


__all__ = [
    "ProviderConnectionAdapterProtocol",
    "OpenAiConnectionAdapter",
    "AnthropicConnectionAdapter",
    "GeminiConnectionAdapter",
    "OpenRouterConnectionAdapter",
    "LocalBackendConnectionAdapter",
    "LocalLlmConnectionAdapter",
    "MockConnectionAdapter",
    "CONNECTION_ADAPTER_FACTORIES",
    "adapter_for_provider",
    "DEFAULT_TEST_TIMEOUT_SECONDS",
    "MAX_TEST_TIMEOUT_SECONDS",
]
