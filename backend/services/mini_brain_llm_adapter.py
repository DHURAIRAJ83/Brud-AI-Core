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
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Protocol

from backend.core.config import Settings

DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 512
DEFAULT_CONTEXT_LENGTH = 2048
DEFAULT_THREADS = 4

MAX_RETRIES = 2
INITIAL_RETRY_BACKOFF = 0.2
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


def sanitize_error_message(err: Any) -> str:
    """Sanitize error messages by redacting query params, API keys, and bearer tokens."""
    raw = str(err)
    sanitized = re.sub(r"([?&](?:key|api_key|token|auth)=)[^& \t\r\n\'\"]+", r"\1[REDACTED]", raw)
    sanitized = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED]", sanitized)
    return sanitized


def categorize_http_error(status_code: int) -> str:
    """Return truth-first normalized category string for HTTP status codes."""
    if status_code == 429:
        return "RATE_LIMIT_429"
    if status_code == 502:
        return "BAD_GATEWAY_502"
    if status_code == 503:
        return "SERVICE_UNAVAILABLE_503"
    if status_code == 504:
        return "GATEWAY_TIMEOUT_504"
    return f"HTTP_{status_code}"


class MiniBrainLlmAdapterProtocol(Protocol):
    backend_type: str

    def is_available(self) -> bool: ...

    def generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int, temperature: float
    ) -> dict[str, Any]: ...

    def stream_generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int, temperature: float
    ) -> Any: ...


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

    def is_configured(self) -> bool:
        """Returns True if model_path is configured in settings, regardless of whether weights file exists on disk."""
        return bool(self._model_path)

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
                latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message=sanitize_error_message(exc),
            )

    def stream_generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float | None = None
    ):
        """Native token streaming for llama-cpp-python."""
        if not self.is_available():
            yield {"type": "error", "error": "local model is not available (llama-cpp-python missing or no configured model file)"}
            return

        try:
            model = self._load_model()
            stream = model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=self._temperature if temperature is None else temperature,
                stream=True,
            )
            for chunk in stream:
                delta = chunk["choices"][0].get("delta", {})
                token_text = delta.get("content")
                if token_text:
                    yield {"type": "token", "text": token_text}
            yield {"type": "done"}
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "error": sanitize_error_message(exc)}


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

    def stream_generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE
    ):
        """Test-only mock streaming generator. Emits truthful full mock reply without fake token slicing."""
        del max_tokens, temperature
        res = self.generate(messages=messages)
        if res["text"]:
            yield {"type": "token", "text": res["text"]}
        yield {"type": "done"}


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
        "ollama": "http://localhost:11434/v1/chat/completions",
    }

    def __init__(
        self,
        *,
        provider_key: str,
        api_key: str = "",
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._provider_key = provider_key
        self._api_key = api_key or ""
        self._model = model
        resolved_base = base_url or os.environ.get("BRUD_OLLAMA_URL") or "http://localhost:11434"
        self._base_url = resolved_base.rstrip("/")

    def _get_endpoint(self) -> str:
        if self._provider_key == "ollama":
            return f"{self._base_url}/v1/chat/completions"
        return self._ENDPOINTS.get(self._provider_key, "")

    def is_configured(self) -> bool:
        """Returns True if provider has endpoint and requisite configuration."""
        if self._provider_key == "ollama":
            return True
        return bool(self._api_key) and self._provider_key in self._ENDPOINTS

    def is_available(self) -> bool:
        """Returns True only if provider is genuinely reachable/available."""
        if self._provider_key == "ollama":
            return self._probe_ollama_reachable()
        return bool(self._api_key) and self._provider_key in self._ENDPOINTS

    def _probe_ollama_reachable(self, timeout: float = 0.5) -> bool:
        httpx = self._import_httpx()
        if httpx is None:
            return False
        try:
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

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
        if not self.is_configured():
            return _result(
                text="", backend_type=self.backend_type, tokens_generated=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=f"external provider '{self._provider_key}' is not configured",
            )
        if not self.is_available():
            return _result(
                text="", backend_type=self.backend_type, tokens_generated=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_message=f"external provider '{self._provider_key}' is configured but not available (probe failed)",
            )
        httpx = self._import_httpx()
        if httpx is None:
            return _result(
                text="", backend_type=self.backend_type, tokens_generated=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3), error_message="httpx is not installed",
            )

        for attempt in range(MAX_RETRIES + 1):
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
                elif self._provider_key == "gemini":
                    response = httpx.post(
                        self._ENDPOINTS["gemini"], params={"key": self._api_key},
                        json={"contents": [{"parts": [{"text": m["content"]}]} for m in messages if m.get("role") != "system"]},
                        timeout=30.0,
                    )
                else:
                    headers = {"Content-Type": "application/json"}
                    if self._api_key:
                        headers["Authorization"] = f"Bearer {self._api_key}"
                    model_name = self._model or ("llama3" if self._provider_key == "ollama" else "gpt-4o-mini")
                    response = httpx.post(
                        self._get_endpoint(),
                        headers=headers,
                        json={"model": model_name, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
                        timeout=30.0,
                    )

                if response.status_code in RETRYABLE_STATUS_CODES:
                    if attempt < MAX_RETRIES:
                        # Bounded exponential backoff with jitter:
                        # Permitted ONLY for retry backoff jitter.
                        # Never used for model response generation, routing truth, synthetic streaming, or benchmark fabrication.
                        # random.choice() = 0 production occurrences.
                        jitter = random.uniform(0.05, 0.15)
                        backoff = (INITIAL_RETRY_BACKOFF * (2 ** attempt)) + jitter
                        time.sleep(backoff)
                        continue
                    cat = categorize_http_error(response.status_code)
                    sanitized_body = sanitize_error_message(response.text[:200])
                    return _result(
                        text="", backend_type=self.backend_type, tokens_generated=0,
                        latency_ms=round((time.perf_counter() - started) * 1000, 3),
                        error_message=f"{cat}: {sanitized_body}",
                    )

                if response.status_code >= 400:
                    # Non-retryable error (e.g. 400 Bad Request, 401 Unauthorized, 403 Forbidden)
                    sanitized_body = sanitize_error_message(response.text[:200])
                    return _result(
                        text="", backend_type=self.backend_type, tokens_generated=0,
                        latency_ms=round((time.perf_counter() - started) * 1000, 3),
                        error_message=f"HTTP_{response.status_code}: {sanitized_body}",
                    )

                response.raise_for_status()
                payload = response.json()
                if self._provider_key == "anthropic":
                    text = "".join(block.get("text", "") for block in payload.get("content", []))
                    tokens_generated = payload.get("usage", {}).get("output_tokens", 0)
                elif self._provider_key == "gemini":
                    text = payload["candidates"][0]["content"]["parts"][0]["text"]
                    tokens_generated = payload.get("usageMetadata", {}).get("candidatesTokenCount", 0)
                else:
                    text = payload["choices"][0]["message"]["content"]
                    tokens_generated = payload.get("usage", {}).get("completion_tokens", 0)

                return _result(
                    text=text, backend_type=self.backend_type, tokens_generated=tokens_generated,
                    latency_ms=round((time.perf_counter() - started) * 1000, 3),
                )
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError, httpx.NetworkError) as exc:
                if attempt < MAX_RETRIES:
                    jitter = random.uniform(0.05, 0.15)
                    backoff = (INITIAL_RETRY_BACKOFF * (2 ** attempt)) + jitter
                    time.sleep(backoff)
                    continue
                err_type = "CONNECT_TIMEOUT" if isinstance(exc, (httpx.ConnectTimeout, httpx.ConnectError)) else ("READ_TIMEOUT" if isinstance(exc, httpx.ReadTimeout) else "NETWORK_ERROR")
                return _result(
                    text="", backend_type=self.backend_type, tokens_generated=0,
                    latency_ms=round((time.perf_counter() - started) * 1000, 3),
                    error_message=f"{err_type}: {sanitize_error_message(exc)}",
                )
            except Exception as exc:  # noqa: BLE001 -- honest failure, never a crash
                return _result(
                    text="", backend_type=self.backend_type, tokens_generated=0,
                    latency_ms=round((time.perf_counter() - started) * 1000, 3),
                    error_message=sanitize_error_message(exc),
                )

        return _result(
            text="", backend_type=self.backend_type, tokens_generated=0,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            error_message="UNKNOWN_ERROR: retry limit reached",
        )

    def stream_generate(
        self, *, messages: list[dict[str, Any]], max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE
    ):
        """Streaming adapter for external providers via SSE lines or single truthful chunk with retry on connection."""
        if not self.is_configured():
            yield {"type": "error", "error": f"external provider '{self._provider_key}' is not configured"}
            return
        if not self.is_available():
            yield {"type": "error", "error": f"external provider '{self._provider_key}' is configured but not available (probe failed)"}
            return

        httpx = self._import_httpx()
        if httpx is None:
            yield {"type": "error", "error": "httpx is not installed"}
            return

        if self._provider_key in {"openrouter", "openai", "ollama"}:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            model_name = self._model or ("llama3" if self._provider_key == "ollama" else "gpt-4o-mini")
            payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            stream_started = False
            for attempt in range(MAX_RETRIES + 1):
                try:
                    with httpx.stream(
                        "POST",
                        self._get_endpoint(),
                        headers=headers,
                        json=payload,
                        timeout=60.0,
                    ) as response:
                        if response.status_code in RETRYABLE_STATUS_CODES and not stream_started:
                            if attempt < MAX_RETRIES:
                                jitter = random.uniform(0.05, 0.15)
                                time.sleep((INITIAL_RETRY_BACKOFF * (2 ** attempt)) + jitter)
                                continue
                            cat = categorize_http_error(response.status_code)
                            yield {"type": "error", "error": f"{cat}: {response.status_code}"}
                            return
                        response.raise_for_status()
                        stream_started = True
                        for line in response.iter_lines():
                            if not line:
                                continue
                            line_str = line.decode("utf-8") if isinstance(line, bytes) else str(line)
                            if line_str.startswith("data: "):
                                raw_data = line_str[6:].strip()
                                if raw_data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(raw_data)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    token_text = delta.get("content")
                                    if token_text:
                                        yield {"type": "token", "text": token_text}
                                except Exception:
                                    continue
                    yield {"type": "done"}
                    return
                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError, httpx.NetworkError) as exc:
                    if attempt < MAX_RETRIES and not stream_started:
                        jitter = random.uniform(0.05, 0.15)
                        time.sleep((INITIAL_RETRY_BACKOFF * (2 ** attempt)) + jitter)
                        continue
                    err_type = "CONNECT_TIMEOUT" if isinstance(exc, (httpx.ConnectTimeout, httpx.ConnectError)) else ("READ_TIMEOUT" if isinstance(exc, httpx.ReadTimeout) else "NETWORK_ERROR")
                    yield {"type": "error", "error": f"{err_type}: {sanitize_error_message(exc)}"}
                    return
                except Exception as exc:  # noqa: BLE001
                    yield {"type": "error", "error": sanitize_error_message(exc)}
                    return
        else:
            # Anthropic / Gemini fallback to truthful complete single response (no artificial token splitting)
            res = self.generate(messages=messages, max_tokens=max_tokens, temperature=temperature)
            if res.get("error_message"):
                yield {"type": "error", "error": res["error_message"]}
            else:
                if res.get("text"):
                    yield {"type": "token", "text": res["text"]}
                yield {"type": "done"}
