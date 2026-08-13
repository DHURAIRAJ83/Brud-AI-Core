"""MB-22: pluggable training runtime adapter contract + adapters.

`TrainingRuntimeAdapterProtocol` is a structural `Protocol`, mirroring
MB-04's own `InferenceBackend`, MB-15's `VisionInferenceBackend`, and
MB-21's `ProviderClientProtocol` exactly -- any class with these
methods satisfies it, with no shared base class.
`MiniBrainTrainingEngineService` only ever talks to this Protocol,
never to a concrete adapter class by name.

`SimulationTrainingAdapter` is the only adapter that actually runs
here -- it emits a fully deterministic, formulaic metric sequence
(never randomness, never a seeded RNG) so the same step always
produces the same fake metric point across runs and across machines.
It writes a real, small JSON file per checkpoint (so checksum/
file-existence logic downstream is exercised against a real file) but
that file's content is an honestly disclosed placeholder, never real
model weights.

`LlamaCppTrainingAdapter` is a disclosed stub: `llama-cpp-python` is
genuinely installed in this environment (confirmed during MB-15's own
audit), but its Python bindings do not expose a real fine-tuning/
training API -- only inference -- so `is_available()` truthfully
returns `False` for training purposes regardless. `TorchTrainingAdapter`
is a disclosed stub too: `torch` is genuinely installed (CPU build,
confirmed during this phase's own audit), so `is_available()` reports
`True`, but no real training loop, dataset-feeding pipeline, or model-
loading integration exists in this codebase yet, so every actual
training method honestly raises `BackendUnavailableError` -- exactly
the same "library present, integration not built" disclosure MB-15's
own `LlavaGgufVisionBackend` already established.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from backend.core.json_utils import dumps_json
from backend.services.mini_brain_inference_backend import BackendUnavailableError
from core_model.release.artifact_inventory import file_checksum

SIMULATION_BASE_LOSS = 3.0
SIMULATION_LOSS_DECAY_PER_STEP = 0.002
SIMULATION_MIN_LOSS = 0.05
SIMULATION_BASE_LEARNING_RATE = 2e-5
SIMULATION_TOKENS_PER_SECOND = 500.0
SIMULATION_EXAMPLES_PER_SECOND = 10.0
SIMULATION_CPU_MEMORY_MB = 256.0


class TrainingRuntimeAdapterProtocol(Protocol):
    execution_mode: str

    def is_available(self) -> bool: ...

    def reserve(self, *, resource_plan: dict[str, Any]) -> dict[str, Any]: ...

    def start(self, *, resume_step: int = 0, resume_epoch: int = 0) -> dict[str, Any]: ...

    def step(self, *, step: int, epoch: int) -> dict[str, Any]: ...

    def save_checkpoint(self, *, path: Path, step: int, epoch: int) -> dict[str, Any]: ...

    def pause(self) -> dict[str, Any]: ...

    def resume(self) -> dict[str, Any]: ...

    def cancel(self) -> dict[str, Any]: ...

    def finalize(self) -> dict[str, Any]: ...


class SimulationTrainingAdapter:
    """Deterministic fake trainer -- no real computation, no real
    model. Every metric is a pure function of `step`, never
    randomness, so tests are fully reproducible."""

    execution_mode = "simulation"

    def is_available(self) -> bool:
        return True

    def reserve(self, *, resource_plan: dict[str, Any]) -> dict[str, Any]:
        del resource_plan
        return {"reserved": True, "reservation_id": "simulation-reservation", "runtime": "simulation"}

    def start(self, *, resume_step: int = 0, resume_epoch: int = 0) -> dict[str, Any]:
        return {"started": True, "resume_step": resume_step, "resume_epoch": resume_epoch}

    def step(self, *, step: int, epoch: int) -> dict[str, Any]:
        loss = max(SIMULATION_MIN_LOSS, SIMULATION_BASE_LOSS - SIMULATION_LOSS_DECAY_PER_STEP * step)
        learning_rate = SIMULATION_BASE_LEARNING_RATE * (0.99 ** (step // 100))
        return {
            "step": step, "epoch": epoch, "loss": round(loss, 6), "learning_rate": learning_rate,
            "tokens_per_second": SIMULATION_TOKENS_PER_SECOND, "examples_per_second": SIMULATION_EXAMPLES_PER_SECOND,
            "gpu_memory_mb": None, "cpu_memory_mb": SIMULATION_CPU_MEMORY_MB,
        }

    def save_checkpoint(self, *, path: Path, step: int, epoch: int) -> dict[str, Any]:
        payload = {
            "simulation": True, "step": step, "epoch": epoch,
            "disclosure": "this is a simulated checkpoint placeholder -- it contains no real model weights",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps_json(payload), encoding="utf-8")
        return {
            "sha256": file_checksum(path), "file_size_bytes": path.stat().st_size, "is_metadata_only": True,
        }

    def pause(self) -> dict[str, Any]:
        return {"paused": True}

    def resume(self) -> dict[str, Any]:
        return {"resumed": True}

    def cancel(self) -> dict[str, Any]:
        return {"cancelled": True}

    def finalize(self) -> dict[str, Any]:
        return {"finalized": True}


class LlamaCppTrainingAdapter:
    """Disclosed stub. `llama-cpp-python`'s Python bindings expose
    inference only -- no fine-tuning/training API -- so this is never
    available for training regardless of whether the library itself
    is importable."""

    execution_mode = "cpu"

    def is_available(self) -> bool:
        return False

    def _unavailable(self) -> BackendUnavailableError:
        return BackendUnavailableError(
            "llama-cpp-python provides inference only -- no fine-tuning/training API exists in its "
            "Python bindings, so this adapter is never available for real training"
        )

    def reserve(self, *, resource_plan: dict[str, Any]) -> dict[str, Any]:
        del resource_plan
        raise self._unavailable()

    def start(self, *, resume_step: int = 0, resume_epoch: int = 0) -> dict[str, Any]:
        del resume_step, resume_epoch
        raise self._unavailable()

    def step(self, *, step: int, epoch: int) -> dict[str, Any]:
        del step, epoch
        raise self._unavailable()

    def save_checkpoint(self, *, path: Path, step: int, epoch: int) -> dict[str, Any]:
        del path, step, epoch
        raise self._unavailable()

    def pause(self) -> dict[str, Any]:
        raise self._unavailable()

    def resume(self) -> dict[str, Any]:
        raise self._unavailable()

    def cancel(self) -> dict[str, Any]:
        raise self._unavailable()

    def finalize(self) -> dict[str, Any]:
        raise self._unavailable()


class TorchTrainingAdapter:
    """Disclosed stub. `torch` is genuinely installed in this
    environment (CPU build), so `is_available()` reports `True` -- but
    no real training loop, dataset-feeding pipeline, or model-loading
    integration exists in this codebase yet, so every real method
    honestly raises `BackendUnavailableError`, exactly the same
    "library present, integration not built" disclosure MB-15's own
    `LlavaGgufVisionBackend` already established for the vision case."""

    execution_mode = "gpu"

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def _unavailable(self) -> BackendUnavailableError:
        return BackendUnavailableError(
            "torch is installed but no real training loop, dataset-feeding pipeline, or model-loading "
            "integration exists in this codebase yet -- this adapter is a disclosed stub, never "
            "exercised end-to-end against a real model"
        )

    def reserve(self, *, resource_plan: dict[str, Any]) -> dict[str, Any]:
        del resource_plan
        raise self._unavailable()

    def start(self, *, resume_step: int = 0, resume_epoch: int = 0) -> dict[str, Any]:
        del resume_step, resume_epoch
        raise self._unavailable()

    def step(self, *, step: int, epoch: int) -> dict[str, Any]:
        del step, epoch
        raise self._unavailable()

    def save_checkpoint(self, *, path: Path, step: int, epoch: int) -> dict[str, Any]:
        del path, step, epoch
        raise self._unavailable()

    def pause(self) -> dict[str, Any]:
        raise self._unavailable()

    def resume(self) -> dict[str, Any]:
        raise self._unavailable()

    def cancel(self) -> dict[str, Any]:
        raise self._unavailable()

    def finalize(self) -> dict[str, Any]:
        raise self._unavailable()


ADAPTER_FACTORIES: dict[str, type] = {
    "simulation": SimulationTrainingAdapter, "cpu": LlamaCppTrainingAdapter, "gpu": TorchTrainingAdapter,
}


def adapter_for_execution_mode(execution_mode: str) -> TrainingRuntimeAdapterProtocol:
    factory = ADAPTER_FACTORIES.get(execution_mode)
    if factory is None:
        raise BackendUnavailableError(f"no runtime adapter registered for execution_mode '{execution_mode}'")
    return factory()


__all__ = [
    "TrainingRuntimeAdapterProtocol", "BackendUnavailableError", "SimulationTrainingAdapter",
    "LlamaCppTrainingAdapter", "TorchTrainingAdapter", "ADAPTER_FACTORIES", "adapter_for_execution_mode",
]
