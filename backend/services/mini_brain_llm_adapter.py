"""MB-28: LLM adapter layer -- the one designated impure exception
module for `core_model.mini_brain.llm_runtime`, the same "one
designated impure exception module" pattern MB-25's `timeout_runner.py`,
MB-26's speech/TTS backends, and MB-27's `secret_encryptor.py` already
established. Real model inference (`llama-cpp-python`) and real
outbound HTTP to external chat-completion providers live here, never
in the pure `llm_runtime` package.

Honest limitation: `llama-cpp-python` is genuinely installed in this
environment (confirmed: `import llama_cpp; llama_cpp.__version__ ==
"0.3.34"`), but no `.gguf` model file exists in this environment and
none is downloaded by this phase -- `LlamaCppMiniBrainAdapter` is real,
correct code, honestly reporting `is_available()` False here. All
functional/smoke coverage runs through `MockMiniBrainAdapter`, the
same "real-but-unexercised-without-real-weights" pattern MB-26's
faster-whisper/Coqui adapters and MB-27's external HTTP adapters
already established.
"""

from __future__ import annotations

import hashlib
import importlib.util
import time
from pathlib import Path
from typing import Any, Protocol

from backend.core.config import Settings

DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 512
DEFAULT_CONTEXT_LENGTH = 2048
DEFAULT_THREADS = 4


class MiniBrainLlmAdapterProtocol(Protocol):
    backend_type: str

    def is_available(self) -> bool: ...

    def generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int, temperature: float
    ) -> dict[str, Any]: ...


def _result(
    *, text: str, backend_type: str, tokens_generated: int, latency_ms: float, error_message: str | None = None
) -> dict[str, Any]:
    return {
        "text": text,
        "backend_type": backend_type,
        "tokens_generated": tokens_generated,
        "latency_ms": latency_ms,
        "error_message": error_message,
    }


def resolve_confined_model_path(*, settings: Settings, model_path: str | None) -> Path | None:
    """Resolve `model_path` and confine it to `settings.resolved_allowed_model_dir`.

    Rejects paths outside the confined directory, `..`-traversal that
    would escape it, and symlinks that resolve outside it -- resolution
    (`Path.resolve()`, which follows symlinks) always happens BEFORE the
    containment check, and containment is checked via `Path.is_relative_to()`
    (real parent-path comparison), never `str.startswith()` (which a
    sibling directory sharing a name prefix could defeat). Returns None
    -- never raises -- for anything invalid, so callers can treat this
    as a plain "not available" signal.
    """
    if not model_path:
        return None
    allowed_root = settings.resolved_allowed_model_dir.resolve()
    candidate = Path(model_path)
    if not candidate.is_absolute():
        candidate = allowed_root / candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(allowed_root):
        return None
    if not resolved.is_file():
        return None
    return resolved


class LlamaCppMiniBrainAdapter:
    """Real llama-cpp-python adapter. Import-guarded even though the
    library is genuinely installed here, as a matter of discipline --
    a deployment target may not have it."""

    backend_type = "local"

    def __init__(
        self,
        *,
        settings: Settings,
        model_path: str | None,
        context_length: int = DEFAULT_CONTEXT_LENGTH,
        threads: int = DEFAULT_THREADS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self._settings = settings
        self._model_path = model_path
        self._context_length = context_length
        self._threads = threads
        self._temperature = temperature
        self._model: Any = None

    @staticmethod
    def _library_available() -> bool:
        return importlib.util.find_spec("llama_cpp") is not None

    def resolved_model_path(self) -> Path | None:
        return resolve_confined_model_path(settings=self._settings, model_path=self._model_path)

    def is_available(self) -> bool:
        return self._library_available() and self.resolved_model_path() is not None

    def _load_model(self):
        if self._model is not None:
            return self._model
        resolved = self.resolved_model_path()
        if resolved is None:
            raise RuntimeError("model_path is not configured or is not confined to the allowed model directory")
        from llama_cpp import Llama

        self._model = Llama(
            model_path=str(resolved),
            n_ctx=self._context_length,
            n_threads=self._threads,
            verbose=False,
        )
        return self._model

    def generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float | None = None
    ) -> dict[str, Any]:
        started = time.perf_counter()
        if not self.is_available():
            return _result(
                text="", backend_type=self.backend_type, tokens_generated=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message="local model is not available (llama-cpp-python missing or no configured model file)",
            )
        try:
            model = self._load_model()
            completion = model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=self._temperature if temperature is None else temperature,
            )
            text = completion["choices"][0]["message"]["content"] or ""
            tokens_generated = completion.get("usage", {}).get("completion_tokens", 0)
            return _result(
                text=text, backend_type=self.backend_type, tokens_generated=tokens_generated,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
            )
        except Exception as exc:  # noqa: BLE001 -- honest failure, never a crash
            return _result(
                text="", backend_type=self.backend_type, tokens_generated=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message=str(exc),
            )


class MockMiniBrainAdapter:
    """Deterministic, hash-seeded canned replies -- the same pattern
    MB-26's `mock_speech_backend.py` already established. Always
    available; never makes a real model call."""

    backend_type = "local"

    _TAMIL_REPLIES = (
        "இது ஒரு சோதனை பதில். Mini Brain LLM Runtime இயங்குகிறது.",
        "நான் உங்கள் கேள்வியைப் புரிந்துகொண்டேன். இது ஒரு mock பதில்.",
    )
    _ENGLISH_REPLIES = (
        "This is a mock reply from the Mini Brain LLM Runtime.",
        "I understood your question. This is a deterministic test response.",
    )

    def is_available(self) -> bool:
        return True

    def generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE
    ) -> dict[str, Any]:
        del max_tokens, temperature
        last_content = messages[-1]["content"] if messages else ""
        digest = hashlib.sha256(last_content.encode("utf-8")).hexdigest()
        index = int(digest, 16) % len(self._ENGLISH_REPLIES)
        is_tamil = any("஀" <= ch <= "௿" for ch in last_content)
        text = self._TAMIL_REPLIES[index] if is_tamil else self._ENGLISH_REPLIES[index]
        return _result(text=text, backend_type=self.backend_type, tokens_generated=len(text.split()), latency_ms=1.0)


class ExternalProviderMiniBrainAdapter:
    """Disabled by default -- reachable only when the service's
    fallback-chain (via `provider_fallback_policy.decide()`) resolves
    to "external", which itself requires MB-27's `enabled=True` and a
    fully-configured secret. Makes its own minimal chat-completion
    call per provider, reusing the proven header/auth *shape* MB-27's
    own connection adapters already established -- never MB-27's
    `test_connection()` method itself, which is a key-validation probe
    with the wrong shape for a real chat completion."""

    backend_type = "external"

    _ENDPOINTS: dict[str, str] = {
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        "openai": "https://api.openai.com/v1/chat/completions",
        "anthropic": "https://api.anthropic.com/v1/messages",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
    }

    def __init__(self, *, provider_key: str, api_key: str, model: str | None = None) -> None:
        self._provider_key = provider_key
        self._api_key = api_key
        self._model = model

    def is_available(self) -> bool:
        return bool(self._api_key) and self._provider_key in self._ENDPOINTS

    @staticmethod
    def _import_httpx():
        try:
            import httpx

            return httpx
        except ImportError:
            return None

    def generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE
    ) -> dict[str, Any]:
        started = time.perf_counter()
        if not self.is_available():
            return _result(
                text="", backend_type=self.backend_type, tokens_generated=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=f"external provider '{self._provider_key}' is not configured",
            )
        httpx = self._import_httpx()
        if httpx is None:
            return _result(
                text="", backend_type=self.backend_type, tokens_generated=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message="httpx is not installed",
            )

        try:
            if self._provider_key == "anthropic":
                response = httpx.post(
                    self._ENDPOINTS["anthropic"],
                    headers={"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                    json={
                        "model": self._model or "claude-3-5-haiku-latest", "max_tokens": max_tokens,
                        "temperature": temperature,
                        "messages": [message for message in messages if message.get("role") != "system"],
                        "system": next((m["content"] for m in messages if m.get("role") == "system"), None),
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                payload = response.json()
                text = "".join(block.get("text", "") for block in payload.get("content", []))
                tokens_generated = payload.get("usage", {}).get("output_tokens", 0)
            elif self._provider_key == "gemini":
                response = httpx.post(
                    self._ENDPOINTS["gemini"], params={"key": self._api_key},
                    json={"contents": [{"parts": [{"text": m["content"]}]} for m in messages if m.get("role") != "system"]},
                    timeout=30.0,
                )
                response.raise_for_status()
                payload = response.json()
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                tokens_generated = payload.get("usageMetadata", {}).get("candidatesTokenCount", 0)
            else:
                response = httpx.post(
                    self._ENDPOINTS[self._provider_key],
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": self._model or "gpt-4o-mini", "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
                    timeout=30.0,
                )
                response.raise_for_status()
                payload = response.json()
                text = payload["choices"][0]["message"]["content"]
                tokens_generated = payload.get("usage", {}).get("completion_tokens", 0)

            return _result(
                text=text, backend_type=self.backend_type, tokens_generated=tokens_generated,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
            )
        except Exception as exc:  # noqa: BLE001 -- honest failure, never a crash
            return _result(
                text="", backend_type=self.backend_type, tokens_generated=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message=str(exc),
            )
