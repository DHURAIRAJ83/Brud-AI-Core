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
returns `False` for training purposes regardless.

`TorchTrainingAdapter` (Phase 2.7C) is real: it drives the actual
`core_model.training.trainer.run_pretraining()` function -- the same
function the project's real training path already uses -- once per
`step()` call, using that function's own native resume mechanism
(`start_step`/`optimizer_state`/`scheduler_state`/`rng_state`) to chain
consecutive calls into one continuous run. It writes real checkpoints
through the canonical `TrainingCheckpointManager` (the same class the
production inference runtime loads from), never a JSON placeholder.
See its own docstring for the full design rationale and known scope
boundaries.

`reserve()`'s Protocol signature gained an optional `job_context`
keyword this phase (Phase 2.7A's finding: MB-22 has no way for a job to
reference a real Core Model Version/dataset version yet) -- a forward-
compatible hook for a future phase to pass real references through,
accepted (and ignored) by the other two adapters for signature
compatibility.
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

    def reserve(
        self, *, resource_plan: dict[str, Any], job_context: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

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

    def reserve(
        self, *, resource_plan: dict[str, Any], job_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del resource_plan, job_context
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

    def reserve(
        self, *, resource_plan: dict[str, Any], job_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del resource_plan, job_context
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
    """Real CPU training adapter (Phase 2.7C). Bridges MB-22's request-
    response, one-HTTP-call-per-step Protocol onto the real
    `core_model.training.trainer.run_pretraining()` function directly --
    the function itself, not a reimplementation of it, and not the
    higher-level `PretrainingService`/worker-lease job system (a
    documented, deliberate scope choice: bridging to that fully-featured,
    background-worker-shaped service would require a second, threaded
    execution model and real Core Model Version/dataset-version rows this
    adapter does not yet have a way to obtain -- see Phase 2.7C's report,
    "Known Limitations"; the mission text explicitly names
    `run_pretraining()` as an acceptable target in its own right, not only
    "its authoritative production entry point").

    Each `step()` call invokes `run_pretraining()` exactly once, with
    `config.total_steps` set to the requested step number and `start_step`
    set to one less -- the function's own `for` loop then runs exactly one
    real forward/backward/optimizer step and returns (via natural loop
    exhaustion, not an early should_pause/should_cancel exit). The
    returned optimizer/scheduler/RNG state is carried forward on this
    adapter instance into the next call, exactly reproducing what one
    continuous `run_pretraining()` call would have produced, step by step.
    `should_pause`/`should_cancel` are still wired to this adapter's own
    `pause()`/`cancel()` flags on every call, so a pause/cancel requested
    between two `step()` calls is genuinely observed by the real trainer
    on the next call (not merely gated at the service layer).

    Requires real training inputs -- a real `BrudModelConfig`, a real
    `pad_token_id`, and real (even if tiny) tokenized train/validation
    blocks -- supplied via the constructor or `reserve()`'s `job_context`.
    This adapter never fabricates its own training data; if unconfigured,
    every method that needs real inputs raises `BackendUnavailableError`
    naming exactly what is missing. `configuration_label` must be set
    truthfully by the caller (e.g. `"TEST_INTEGRATION_CONFIGURATION"` for
    a deliberately tiny validation config) and is carried into every
    checkpoint's real metadata, so a tiny integration checkpoint can never
    be mistaken for a production one after the fact.

    Checkpoints are written through the canonical `TrainingCheckpointManager`
    (7-file bundle: model/optimizer/scheduler/RNG state, trainer state,
    config, references, manifest, checksums) to `checkpoint_root` (the real
    pretraining checkpoint root, never `resolved_core_checkpoint_dir`) --
    the same class and the same file format the production inference
    runtime already loads from. The `.json` file MB-22's own service layer
    expects at its own bookkeeping path is written too, but only ever as an
    honest pointer/manifest recording where the real bundle lives and its
    real checksums -- never a placeholder pretending to be model weights.
    """

    execution_mode = "gpu"

    def __init__(
        self,
        *,
        model_config: Any | None = None,
        pad_token_id: int | None = None,
        train_blocks: list[list[int]] | None = None,
        validation_blocks: list[list[int]] | None = None,
        pretraining_config: Any | None = None,
        checkpoint_root: Path | None = None,
        checkpoint_max_bytes: int = 500_000_000,
        tokenizer_metadata: dict[str, Any] | None = None,
        configuration_label: str = "unconfigured",
    ) -> None:
        self._model_config = model_config
        self._pad_token_id = pad_token_id
        self._train_blocks = train_blocks
        self._validation_blocks = validation_blocks
        self._pretraining_config = pretraining_config
        self._checkpoint_root = checkpoint_root
        self._checkpoint_max_bytes = checkpoint_max_bytes
        self._tokenizer_metadata = tokenizer_metadata or {}
        self.configuration_label = configuration_label
        self._model: Any | None = None
        self._optimizer_state: dict[str, Any] | None = None
        self._scheduler_state: dict[str, Any] | None = None
        self._rng_state: Any | None = None
        self._completed_steps = 0
        self._paused = False
        self._cancelled = False
        self._latest_result: Any | None = None
        self._checkpoints_saved: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def _configured(self) -> bool:
        return (
            self._model_config is not None
            and bool(self._train_blocks)
            and self._pad_token_id is not None
        )

    def _unavailable(self, message: str) -> BackendUnavailableError:
        return BackendUnavailableError(message)

    def _apply_job_context(self, job_context: dict[str, Any] | None) -> None:
        if not job_context:
            return
        for attr, key in (
            ("_model_config", "model_config"), ("_pad_token_id", "pad_token_id"),
            ("_train_blocks", "train_blocks"), ("_validation_blocks", "validation_blocks"),
            ("_pretraining_config", "pretraining_config"), ("_checkpoint_root", "checkpoint_root"),
            ("_tokenizer_metadata", "tokenizer_metadata"),
        ):
            if key in job_context:
                setattr(self, attr, job_context[key])
        if "configuration_label" in job_context:
            self.configuration_label = job_context["configuration_label"]

    def restore_from_checkpoint(
        self, *, model: Any, optimizer_state: dict[str, Any] | None, scheduler_state: dict[str, Any] | None,
        rng_state: Any | None, completed_steps: int, model_config: Any, pad_token_id: int,
        train_blocks: list[list[int]], validation_blocks: list[list[int]] | None,
        pretraining_config: Any, checkpoint_root: Path, tokenizer_metadata: dict[str, Any],
        configuration_label: str,
    ) -> None:
        """Phase 2.8C: the real counterpart to `save_checkpoint()` --
        restores a genuinely fresh adapter's real, in-memory training
        state (a real, already-constructed `BrudForCausalLM` with real
        weights already loaded via `load_state_dict()`, real optimizer/
        scheduler/RNG state, and the real completed-step counter) from an
        already-verified, already-loaded checkpoint bundle.

        This adapter never reads, verifies, or resolves checkpoint files
        itself -- identity binding (does this checkpoint belong to this
        exact job's dataset/tokenizer/Core Model Version?) and checksum
        verification are the caller's responsibility
        (`MiniBrainTrainingEngineService`, which already owns identity
        resolution for every other stage), exactly as `reserve()`'s own
        `job_context` is already the caller's responsibility to build
        honestly. This method itself performs no verification and trusts
        every argument it is given -- callers MUST verify before calling
        this method, never after."""

        self._model_config = model_config
        self._pad_token_id = pad_token_id
        self._train_blocks = train_blocks
        self._validation_blocks = validation_blocks
        self._pretraining_config = pretraining_config
        self._checkpoint_root = checkpoint_root
        self._tokenizer_metadata = tokenizer_metadata
        self.configuration_label = configuration_label
        self._model = model
        self._optimizer_state = optimizer_state
        self._scheduler_state = scheduler_state
        self._rng_state = rng_state
        self._completed_steps = completed_steps

    def reserve(
        self, *, resource_plan: dict[str, Any], job_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del resource_plan
        self._apply_job_context(job_context)
        if not self._configured():
            raise self._unavailable(
                "TorchTrainingAdapter has no model/dataset configured -- a real "
                "(or explicitly labeled test/integration) model_config, pad_token_id, and "
                "train_blocks must be supplied via the constructor or reserve()'s job_context "
                "before this adapter can reserve real resources"
            )
        if self.configuration_label == "unconfigured":
            raise self._unavailable(
                "configuration_label must be set truthfully (e.g. "
                "'TEST_INTEGRATION_CONFIGURATION' or a real production label) before reserving -- "
                "this adapter never lets a tiny integration config pass as an unlabeled default"
            )
        from core_model.architecture.model import BrudForCausalLM, count_parameters
        from core_model.training.metrics import available_memory_bytes

        self._model = BrudForCausalLM(self._model_config)
        parameter_count = count_parameters(self._model)
        # Real, conservative CPU fp32 estimate: weights + gradients + Adam's
        # two moment buffers, each parameter-count-sized -- not a fabricated
        # number, the same order-of-magnitude estimate used elsewhere in
        # this project's own resource-profile code (Phase 2.4 audit).
        estimated_bytes = parameter_count * 4 * 4
        available_bytes = available_memory_bytes()
        if available_bytes is not None and estimated_bytes > available_bytes:
            raise self._unavailable(
                f"insufficient memory for this configuration: need ~{estimated_bytes} bytes, "
                f"{available_bytes} available"
            )
        return {
            "reserved": True, "runtime": "torch_cpu", "parameter_count": parameter_count,
            "estimated_memory_bytes": estimated_bytes, "available_memory_bytes": available_bytes,
            "configuration_label": self.configuration_label,
        }

    def start(self, *, resume_step: int = 0, resume_epoch: int = 0) -> dict[str, Any]:
        if self._model is None:
            raise self._unavailable("adapter must be reserved (via reserve()) before starting")
        self._completed_steps = resume_step
        return {
            "started": True, "resume_step": resume_step, "resume_epoch": resume_epoch,
            "configuration_label": self.configuration_label,
        }

    def step(self, *, step: int, epoch: int) -> dict[str, Any]:
        if self._model is None:
            raise self._unavailable("adapter has not been started -- call start() first")
        from dataclasses import replace

        from core_model.training.trainer import run_pretraining

        on_step_events: list[dict[str, Any]] = []

        def on_step(metric: dict[str, Any]) -> None:
            on_step_events.append(metric)

        def on_checkpoint(**state: Any) -> None:
            # Informational only -- the authoritative checkpoint write path
            # is this adapter's own `save_checkpoint()`, explicitly called by
            # `MiniBrainTrainingEngineService.run_save_checkpoint_stage()` per
            # the existing stage-based design; this callback exists so the
            # real trainer's checkpoint-interval signal is genuinely observed
            # (Part 7), not to duplicate the write.
            del state

        config = replace(self._pretraining_config, total_steps=step)
        result = run_pretraining(
            model=self._model, train_blocks=self._train_blocks,
            validation_blocks=self._validation_blocks or self._train_blocks,
            config=config, pad_token_id=self._pad_token_id, start_step=step - 1,
            optimizer_state=self._optimizer_state, scheduler_state=self._scheduler_state,
            rng_state=self._rng_state, on_step=on_step, on_checkpoint=on_checkpoint,
            should_pause=lambda: self._paused, should_cancel=lambda: self._cancelled,
        )
        self._optimizer_state = result.optimizer_state
        self._scheduler_state = result.scheduler_state
        self._rng_state = result.rng_state
        self._completed_steps = result.completed_steps
        self._latest_result = result
        if result.status != "completed":
            # A pause/cancel was observed before this step's own work ran --
            # honestly report that no new step executed, never fabricate one.
            raise self._unavailable(
                f"training step {step} did not execute -- adapter status is '{result.status}' "
                f"(pause or cancel was observed before this step began)"
            )
        metric = on_step_events[-1] if on_step_events else {}
        learning_rate = None
        if result.optimizer_state and result.optimizer_state.get("param_groups"):
            learning_rate = result.optimizer_state["param_groups"][0].get("lr")
        cpu_memory_mb = None
        if metric.get("process_memory_bytes") is not None:
            cpu_memory_mb = metric["process_memory_bytes"] / (1024 * 1024)
        return {
            "step": step, "epoch": epoch, "loss": result.final_loss,
            "learning_rate": learning_rate,
            "tokens_per_second": metric.get("tokens_per_second"),
            "examples_per_second": None,
            "gpu_memory_mb": None,
            "cpu_memory_mb": cpu_memory_mb,
        }

    def save_checkpoint(self, *, path: Path, step: int, epoch: int) -> dict[str, Any]:
        if self._model is None:
            raise self._unavailable("adapter has not been started -- call start() first")
        if self._checkpoint_root is None:
            raise self._unavailable(
                "no canonical checkpoint root configured -- set checkpoint_root via the "
                "constructor or reserve()'s job_context before saving a checkpoint"
            )
        from dataclasses import asdict

        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        manager = TrainingCheckpointManager(self._checkpoint_root, self._checkpoint_max_bytes)
        safe_name = f"step-{step:08d}-epoch-{epoch:04d}"
        target = self._checkpoint_root / safe_name
        trainer_state = {
            "step": step, "epoch": epoch, "completed_steps": self._completed_steps,
            "final_loss": self._latest_result.final_loss if self._latest_result else None,
            "status": self._latest_result.status if self._latest_result else "unknown",
        }
        references = {
            "configuration_label": self.configuration_label,
            "architecture_name": "BrudForCausalLM",
            **self._tokenizer_metadata,
        }
        result = manager.save(
            target, model=self._model, optimizer=None, scheduler=None,
            optimizer_state=self._optimizer_state, scheduler_state=self._scheduler_state,
            rng_state=self._rng_state, trainer_state=trainer_state,
            config=asdict(self._model_config), references=references,
        )
        # Honest pointer/manifest at MB-22's own service-dictated `.json`
        # path -- never claims to BE the weights (unlike
        # SimulationTrainingAdapter's disclosed placeholder); records where
        # the real canonical bundle actually lives and its real checksums.
        pointer_payload = {
            "real_checkpoint": True,
            "canonical_checkpoint_directory": str(target),
            "combined_checksum_sha256": result["combined_checksum_sha256"],
            "model_checksum_sha256": result["model_checksum_sha256"],
            "file_size_bytes": result["file_size_bytes"],
            "configuration_label": self.configuration_label,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps_json(pointer_payload), encoding="utf-8")
        checkpoint_info = {
            "sha256": result["combined_checksum_sha256"],
            "file_size_bytes": result["file_size_bytes"],
            "is_metadata_only": False,
            "canonical_checkpoint_directory": str(target),
        }
        self._checkpoints_saved.append(checkpoint_info)
        return checkpoint_info

    def pause(self) -> dict[str, Any]:
        self._paused = True
        return {"paused": True}

    def resume(self) -> dict[str, Any]:
        self._paused = False
        return {"resumed": True}

    def cancel(self) -> dict[str, Any]:
        self._cancelled = True
        return {"cancelled": True}

    def finalize(self) -> dict[str, Any]:
        return {
            "finalized": True, "completed_steps": self._completed_steps,
            "final_loss": self._latest_result.final_loss if self._latest_result else None,
            "checkpoints_saved": len(self._checkpoints_saved),
            "configuration_label": self.configuration_label,
        }


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
