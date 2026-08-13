"""MB-04: pluggable inference backend contract + the real GGUF adapter.

`InferenceBackend` is a structural `Protocol` -- any class with these
four methods satisfies it, with no shared base class and no registry
of implementations to keep in sync. This is the seam MB-04's own
"modular enough to be replaced later without changing MB-02/MB-03"
requirement is built on: `MiniBrainInMemoryModelLoader` only ever
talks to this Protocol, never to `LlamaCppBackend` by name.

`LlamaCppBackend` is the real adapter for GGUF models via
`llama-cpp-python` -- never Ollama, never Docker, never a subprocess
wrapping the `llama.cpp` CLI. It lazily imports `llama_cpp` inside
each method rather than at module level, so this whole file remains
importable (and `is_available()` remains a real, non-crashing check)
on a machine where the library isn't installed -- exactly this
environment, today. Nothing in this file has been exercised against a
real model or a real installed library; see the MB-04 Completion
Report for exactly what was and wasn't tested.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Protocol


class InferenceBackend(Protocol):
    def is_available(self) -> bool: ...

    def load(self, model_path: str, *, context_length: int) -> dict[str, Any]: ...

    def unload(self) -> None: ...

    def generate(
        self, prompt: str, *, max_tokens: int, timeout_seconds: float
    ) -> dict[str, Any]: ...


class BackendUnavailableError(RuntimeError):
    """Raised when a backend's underlying library isn't installed."""


class GenerationTimeoutError(RuntimeError):
    """Raised when a generation call exceeds its timeout."""


class LlamaCppBackend:
    """Real GGUF adapter via `llama-cpp-python`. Not installed in this
    environment as of MB-04 -- see the completion report."""

    def __init__(self) -> None:
        self._llama: Any = None

    def is_available(self) -> bool:
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            return False
        return True

    def load(self, model_path: str, *, context_length: int) -> dict[str, Any]:
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise BackendUnavailableError(
                "llama-cpp-python is not installed in this environment"
            ) from exc
        started = time.perf_counter()
        self._llama = Llama(model_path=model_path, n_ctx=context_length, verbose=False)
        load_time_ms = round((time.perf_counter() - started) * 1000, 2)
        return {"load_time_ms": load_time_ms}

    def unload(self) -> None:
        self._llama = None

    def generate(
        self, prompt: str, *, max_tokens: int, timeout_seconds: float
    ) -> dict[str, Any]:
        if self._llama is None:
            raise BackendUnavailableError("no model is loaded")

        def _run() -> dict[str, Any]:
            started = time.perf_counter()
            result = self._llama(prompt, max_tokens=max_tokens)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            text = result["choices"][0]["text"]
            stop_reason = result["choices"][0].get("finish_reason", "unknown")
            tokens_generated = result.get("usage", {}).get("completion_tokens", 0)
            return {
                "text": text, "tokens_generated": tokens_generated,
                "stop_reason": stop_reason, "response_time_ms": elapsed_ms,
            }

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run)
            try:
                return future.result(timeout=timeout_seconds)
            except FutureTimeoutError as exc:
                raise GenerationTimeoutError(
                    f"generation exceeded {timeout_seconds}s timeout"
                ) from exc
