"""MB-04: Model Manager -- orchestrates the CPU runtime lifecycle.

State and the model registry are held in process-wide module-level
dicts, the same pattern `InferenceRuntimeService._LOADED_MODELS`
already uses in the main runtime (see that file's own comment on why
a module-level dict is the right shape for "one model loaded at a
time in this process") -- reused as a *pattern*, not as shared code;
this module never imports from `inference_runtime_service.py`.

No new database table exists for MB-04, matching its own deliverable
list (no "Database Design" item, same as MB-03) -- the registry is
intentionally process-lifetime only.

Safety enforcement lives here structurally, not just as documentation:
this file never imports `MiniBrainKnowledgeRepository` or any
Knowledge Core module at all, so it is *impossible* for
`generate_response()` to read Knowledge Core directly, regardless of
what a caller passes in -- it can only ever see whatever a Response
Plan dict already contains.
"""

from __future__ import annotations

import os
import resource
import time
from typing import Any
from uuid import uuid4

from backend.database.repositories.base import ValidationError
from backend.services.mini_brain_inference_backend import (
    BackendUnavailableError,
    GenerationTimeoutError,
    InferenceBackend,
    LlamaCppBackend,
)
from core_model.mini_brain.runtime.memory_guard import check_memory_guard
from core_model.mini_brain.runtime.response_formatter import format_response
from core_model.mini_brain.runtime.states import can_generate, can_load, can_unload
from core_model.mini_brain.runtime.validation import validate_model_file, validate_registration_payload

MINIMUM_LOAD_MEMORY_BYTES = 256 * 1024 * 1024  # 256MB headroom required before any load attempt
_REQUIRED_RESPONSE_PLAN_KEYS = {
    "validated_context", "validated_knowledge", "validated_workflow", "suggested_response_type",
}

# Process-wide, matches InferenceRuntimeService's own _LOADED_MODELS shape.
_MODEL_REGISTRY: dict[str, dict[str, Any]] = {}
_RUNTIME: dict[str, Any] = {
    "state": "unloaded",
    "current_model_id": None,
    "backend": None,
    "loaded_at": None,
    "last_error": None,
    "total_generations": 0,
    "last_load_time_ms": None,
    "last_response_time_ms": None,
}


def _set_state(state: str) -> None:
    _RUNTIME["state"] = state


# MB-47: renamed from `MiniBrainRuntimeManagerService` -- purely a
# rename, no behavior change -- to stop it being confused with the
# newer, unrelated, DB-backed `RuntimeManagerService` in
# `backend/services/runtime_manager_service.py` (MB-30, model
# install/download tracking). This class remains the original MB-04
# in-memory-only CPU runtime lifecycle manager described in this
# file's own module docstring above; the two were never the same
# system and neither replaces the other.
class MiniBrainInMemoryModelLoader:
    def __init__(self, *, backend_factory: type[InferenceBackend] = LlamaCppBackend) -> None:
        # A factory, not a shared instance, so each load() creates a
        # fresh backend object -- tests inject a fake factory here.
        self._backend_factory = backend_factory

    # -- model registry --------------------------------------------------

    def register_model(
        self, *, name: str, path: str, quantization: str, context_length: int,
    ) -> dict[str, Any]:
        issues = validate_registration_payload(
            name=name, path=path, quantization=quantization, context_length=context_length,
        )
        exists = os.path.isfile(path)
        size_bytes = os.path.getsize(path) if exists else 0
        issues += validate_model_file(path=path, exists=exists, size_bytes=size_bytes)
        if issues:
            raise ValidationError(f"model registration rejected: {issues}")

        public_id = str(uuid4())
        _MODEL_REGISTRY[public_id] = {
            "public_id": public_id, "name": name, "path": path, "quantization": quantization,
            "context_length": context_length, "size_bytes": size_bytes,
            "registered_at": time.time(),
        }
        return dict(_MODEL_REGISTRY[public_id])

    def list_models(self) -> dict[str, Any]:
        return {"items": [dict(m) for m in _MODEL_REGISTRY.values()]}

    def model_information(self, public_id: str) -> dict[str, Any]:
        if public_id not in _MODEL_REGISTRY:
            raise ValidationError(f"unknown model: {public_id}")
        entry = dict(_MODEL_REGISTRY[public_id])
        exists = os.path.isfile(entry["path"])
        size_bytes = os.path.getsize(entry["path"]) if exists else 0
        entry["validation_issues"] = validate_model_file(
            path=entry["path"], exists=exists, size_bytes=size_bytes,
        )
        entry["file_exists"] = exists
        return entry

    # -- lifecycle -----------------------------------------------------------

    def load_model(self, public_id: str) -> dict[str, Any]:
        if public_id not in _MODEL_REGISTRY:
            raise ValidationError(f"unknown model: {public_id}")
        if not can_load(_RUNTIME["state"]):
            raise ValidationError(f"cannot load from state {_RUNTIME['state']!r}")

        guard = check_memory_guard(minimum_available_bytes=MINIMUM_LOAD_MEMORY_BYTES)
        if not guard["allowed"]:
            _set_state("error")
            _RUNTIME["last_error"] = guard["reason"]
            raise ValidationError(f"memory guard refused load: {guard['reason']}")

        entry = _MODEL_REGISTRY[public_id]
        _set_state("loading")
        backend = self._backend_factory()
        if not backend.is_available():
            _set_state("error")
            _RUNTIME["last_error"] = "inference backend is not available (library not installed)"
            raise ValidationError(_RUNTIME["last_error"])

        try:
            result = backend.load(entry["path"], context_length=entry["context_length"])
        except Exception as exc:  # noqa: BLE001 -- any backend failure is a load failure
            _set_state("error")
            _RUNTIME["last_error"] = str(exc)
            raise ValidationError(f"model load failed: {exc}") from exc

        _RUNTIME["backend"] = backend
        _RUNTIME["current_model_id"] = public_id
        _RUNTIME["loaded_at"] = time.time()
        _RUNTIME["last_load_time_ms"] = result.get("load_time_ms")
        _RUNTIME["last_error"] = None
        _set_state("loaded")
        return self.status()

    def unload_model(self) -> dict[str, Any]:
        if not can_unload(_RUNTIME["state"]):
            raise ValidationError(f"cannot unload from state {_RUNTIME['state']!r}")
        _set_state("unloading")
        backend = _RUNTIME.get("backend")
        if backend is not None:
            backend.unload()
        _RUNTIME.update({
            "backend": None, "current_model_id": None, "loaded_at": None,
        })
        _set_state("unloaded")
        return self.status()

    def reload_model(self) -> dict[str, Any]:
        current = _RUNTIME["current_model_id"]
        if current is None:
            raise ValidationError("no model is currently loaded to reload")
        self.unload_model()
        return self.load_model(current)

    def switch_model(self, public_id: str) -> dict[str, Any]:
        if public_id not in _MODEL_REGISTRY:
            raise ValidationError(f"unknown model: {public_id}")
        if _RUNTIME["current_model_id"] is not None:
            self.unload_model()
        return self.load_model(public_id)

    # -- status / stats / diagnostics --------------------------------------

    def status(self) -> dict[str, Any]:
        current_model = _MODEL_REGISTRY.get(_RUNTIME["current_model_id"])
        return {
            "state": _RUNTIME["state"],
            "current_model": dict(current_model) if current_model else None,
            "loaded_at": _RUNTIME["loaded_at"],
            "last_error": _RUNTIME["last_error"],
        }

    def runtime_statistics(self) -> dict[str, Any]:
        guard = check_memory_guard(minimum_available_bytes=0)
        # A real, honest measurement -- cumulative process CPU seconds
        # via getrusage, never a fabricated live "CPU %" this service
        # has no sampling mechanism to actually compute.
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "total_generations": _RUNTIME["total_generations"],
            "last_load_time_ms": _RUNTIME["last_load_time_ms"],
            "last_response_time_ms": _RUNTIME["last_response_time_ms"],
            "available_memory_bytes": guard["available_bytes"],
            "memory_measurement": guard["label"],
            "process_cpu_time_seconds": round(usage.ru_utime + usage.ru_stime, 3),
            "process_max_rss_kb": usage.ru_maxrss,
        }

    def health(self) -> dict[str, Any]:
        state = _RUNTIME["state"]
        if state == "error":
            return {"status": "unhealthy", "reason": _RUNTIME["last_error"] or "runtime_error"}
        if state in ("loaded", "running"):
            return {"status": "healthy", "reason": f"runtime_{state}"}
        return {"status": "idle", "reason": f"runtime_{state}"}

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": self.status(),
            "statistics": self.runtime_statistics(),
            "registered_model_count": len(_MODEL_REGISTRY),
            "health": self.health(),
        }

    # -- generation (Response Plan only) -----------------------------------

    def generate_response(
        self, response_plan: dict[str, Any], *, max_tokens: int = 256, timeout_seconds: float = 30.0,
        prebuilt_prompt: str | None = None,
    ) -> dict[str, Any]:
        """MB-04A note: `prebuilt_prompt` is the one disclosed,
        additive exception to "do not change the Runtime Manager" --
        when omitted (the default), behavior is byte-for-byte
        identical to MB-04: the Response-Plan-only contract is still
        enforced below exactly as before, and `_build_prompt()` still
        runs. When a caller (MB-04A's prompt optimization service)
        supplies its own structured prompt, it is used verbatim
        instead -- the state machine, memory guard, safety checks, and
        every other Runtime Manager behavior are unchanged either way."""

        missing = _REQUIRED_RESPONSE_PLAN_KEYS - set(response_plan)
        if missing:
            raise ValidationError(
                f"refusing to generate: payload is not a valid Response Plan, missing {sorted(missing)}"
            )
        if not can_generate(_RUNTIME["state"]):
            raise ValidationError(f"cannot generate from state {_RUNTIME['state']!r} -- load a model first")

        prompt = prebuilt_prompt if prebuilt_prompt is not None else self._build_prompt(response_plan)
        backend: InferenceBackend = _RUNTIME["backend"]
        _set_state("running")
        try:
            result = backend.generate(prompt, max_tokens=max_tokens, timeout_seconds=timeout_seconds)
        except (BackendUnavailableError, GenerationTimeoutError) as exc:
            _set_state("loaded")
            raise ValidationError(f"generation failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            _set_state("error")
            _RUNTIME["last_error"] = str(exc)
            raise ValidationError(f"generation failed: {exc}") from exc

        _RUNTIME["total_generations"] += 1
        _RUNTIME["last_response_time_ms"] = result.get("response_time_ms")
        _set_state("loaded")

        return format_response(
            raw_text=result["text"], response_plan=response_plan,
            generation_stats={
                "prompt_size_chars": len(prompt), "tokens_generated": result.get("tokens_generated"),
                "response_time_ms": result.get("response_time_ms"), "stop_reason": result.get("stop_reason"),
            },
        )

    @staticmethod
    def _build_prompt(response_plan: dict[str, Any]) -> str:
        """Deterministic template, built only from Response Plan
        fields -- never a direct Knowledge Core query."""

        context = response_plan.get("validated_context", {})
        knowledge = response_plan.get("validated_knowledge", {})
        workflow = response_plan.get("validated_workflow", {})
        lines = [
            f"Intent: {response_plan.get('intent', 'unknown')}",
            f"Primary knowledge: {', '.join(knowledge.get('primary', [])) or 'none'}",
            f"Supporting knowledge: {', '.join(knowledge.get('supporting', [])) or 'none'}",
            f"Matched items: {', '.join(context.get('matched_items', [])) or 'none'}",
            f"Current workflow step: {workflow.get('current_step') or 'none'}",
            f"Next steps: {', '.join(workflow.get('next_steps', [])) or 'none'}",
        ]
        return "\n".join(lines)


def reset_runtime_for_tests() -> None:
    """Test-only helper -- clears process-wide state between tests so
    one test's loaded model can't leak into the next."""

    _MODEL_REGISTRY.clear()
    _RUNTIME.update({
        "state": "unloaded", "current_model_id": None, "backend": None, "loaded_at": None,
        "last_error": None, "total_generations": 0, "last_load_time_ms": None,
        "last_response_time_ms": None,
    })
