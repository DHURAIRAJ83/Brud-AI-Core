"""MB-22: Brud Mini Brain Real Training Execution Engine -- the
orchestration layer for the 14-stage job workflow described in the
MB-22 task spec.

The first Mini Brain phase allowed to run a real training workflow --
but only ever in simulation mode in this environment (the real CPU/
GPU adapters are disclosed stubs, see `training_runtime_adapter.py`),
always CPU-first, always behind a fresh, per-job admin authorization
recorded on the job itself. This service never auto-starts training
after package approval, never auto-deploys or auto-promotes a trained
model, never overwrites an existing checkpoint, never downloads a
model, never executes an arbitrary shell command, and never modifies
any MB-16 through MB-20 historical record -- it only reads MB-18
(approved training packages) and MB-20 (approved release-governance
sessions) through their own public methods.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.base import ConflictError, NotFoundError, ValidationError
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.mini_brain_training_engine import (
    MiniBrainTrainingEngineRepository,
    public_checkpoint_row,
    public_job_row,
    public_memory_row,
    public_metric_row,
)
from backend.services.core_model_service import CoreModelService
from backend.services.mini_brain_dataset_pipeline_service import (
    DEFAULT_OVERLENGTH_POLICY,
    MiniBrainDatasetPipelineService,
)
from backend.services.mini_brain_release_governance_service import MiniBrainReleaseGovernanceService
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService
from backend.services.training_adapter_registry import REGISTRY
from backend.services.training_runtime_adapter import (
    TrainingRuntimeAdapterProtocol,
    adapter_for_execution_mode,
)
from core_model.mini_brain.training_engine.checkpoint_namer import (
    build_checkpoint_name,
    check_no_overwrite,
    find_latest_checkpoint,
)
from core_model.mini_brain.training_engine.experiment_fingerprint import build_experiment_fingerprint
from core_model.mini_brain.training_engine.failure_classifier import classify_failure
from core_model.mini_brain.training_engine.job_report_generator import generate_job_report
from core_model.mini_brain.training_engine.job_validator import (
    validate_release_approval,
    validate_training_package,
)
from core_model.mini_brain.training_engine.resource_planner import plan_resources
from core_model.mini_brain.training_engine.resume_state_builder import build_resume_state
from core_model.mini_brain.training_engine.training_audit_builder import build_training_audit
from core_model.mini_brain.training_engine.training_manifest_builder import build_training_manifest
from core_model.release.artifact_inventory import resolve_confined_path

EXECUTION_MODES = {"simulation", "cpu", "gpu"}

# Phase 2.7E: only the real Torch adapter (execution_mode='gpu') trains an
# actual model -- simulation/cpu remain identity-free by design (nothing
# real is being trained, so nothing real needs to be identified).
REAL_TRAINING_EXECUTION_MODES = {"gpu"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _timed(fn, /, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn(**kwargs)
    return result, round((time.perf_counter() - started) * 1000, 3)


class MiniBrainTrainingEngineService:
    def __init__(self, settings: Settings, *, adapters: dict[str, TrainingRuntimeAdapterProtocol] | None = None) -> None:
        self.settings = settings
        self.repository = MiniBrainTrainingEngineRepository(settings.resolved_database_path)
        self.core_models = CoreModelService(
            CoreModelRepository(settings.resolved_database_path), settings
        )
        self.dataset_pipeline = MiniBrainDatasetPipelineService(settings)

        self.training_pipeline = MiniBrainTrainingPipelineService(settings)
        self.release_governance = MiniBrainReleaseGovernanceService(settings)

        # Real adapters by execution_mode. Tests inject a fresh SimulationTrainingAdapter
        # (or a test double) via `adapters` -- the default set always includes the real
        # (honestly-stubbed) cpu/gpu adapters plus the real simulation adapter.
        self._adapter_overrides = adapters or {}

    def _adapter(self, execution_mode: str) -> TrainingRuntimeAdapterProtocol:
        if execution_mode in self._adapter_overrides:
            return self._adapter_overrides[execution_mode]
        return adapter_for_execution_mode(execution_mode)

    # -- Phase 2.8E: cross-request adapter lifecycle --------------------

    # A single HTTP request is normally fast (sub-2s even for a real
    # training step at the largest validated scale, Phase 2.8D §7); this
    # bounds how long a second, concurrent request for the SAME job will
    # wait before receiving a typed conflict instead of hanging
    # indefinitely (Part 12).
    _JOB_LOCK_TIMEOUT_SECONDS = 30

    def _real_untested_gpu_job(self, job_data: dict[str, Any]) -> bool:
        """True only for a genuine, non-test-overridden real (gpu-mode)
        job -- the only case that needs the process-local adapter
        registry/lock at all. Every test that injects its own adapter
        via `adapters=` at construction (the established pattern since
        Phase 2.7C) is completely unaffected by this phase -- it always
        takes the original, unmodified `self._adapter(execution_mode)`
        path. Simulation/cpu-mode jobs are unaffected too: their
        adapters are either fully stateless (`SimulationTrainingAdapter`)
        or already-disclosed stubs, and have never required cross-
        request continuity."""

        execution_mode = job_data["execution_mode"]
        return execution_mode in REAL_TRAINING_EXECUTION_MODES and execution_mode not in self._adapter_overrides

    @contextmanager
    def _locked_job_operation(self, job_public_id: str):
        """Serializes every adapter-touching operation for one job
        (Part 12) -- two concurrent requests against the same job's
        adapter never race: the second blocks until the first releases,
        or times out with a typed `ConflictError` rather than hanging
        forever or corrupting shared Torch state. Different jobs never
        contend with each other (each gets its own lock, Part 7)."""

        lock = REGISTRY.lock_for(job_public_id)
        if not lock.acquire(timeout=self._JOB_LOCK_TIMEOUT_SECONDS):
            raise ConflictError(
                f"another operation is already in progress for job {job_public_id} -- retry once it completes"
            )
        try:
            yield
        finally:
            lock.release()

    def _ensure_adapter_for_job(
        self, job_data: dict[str, Any], *, allow_fresh_construction: bool,
        train_blocks: list[list[int]] | None = None, validation_blocks: list[list[int]] | None = None,
        configuration_label: str | None = None, report_sink: dict[str, Any] | None = None,
    ) -> Any:
        """Phase 2.8E: the single reconstruction path every real
        (gpu-mode) stage now goes through instead of a raw
        `self._adapter(execution_mode)` call. Callers MUST already hold
        `self._locked_job_operation(job_data["public_id"])`.

        Same-process continuation is free: if this OS process already
        holds this job's live adapter (registered by an earlier stage in
        this same request, or an earlier request served by this same
        worker), `JobAdapterRegistry.get_or_create()` returns that exact
        object -- nothing is rebuilt, nothing is re-verified, and
        `report_sink` (if given) is left empty so the caller can tell no
        fresh reservation happened.

        Only when this process has no live adapter for this job (a
        genuinely fresh process, a different worker, or an evicted
        entry) is one reconstructed, and always from the same
        authoritative state every other stage already trusts: this
        job's own DB row, the governed dataset/tokenizer/Core-Model
        identity, and -- if one exists -- the latest verified checkpoint,
        via `_recover_adapter_from_checkpoint()` (Phase 2.8C, reused
        verbatim, never duplicated).

        `allow_fresh_construction` is `True` only for `reserve_runtime`'s
        own no-checkpoint-yet path (a genuinely new, never-before-
        trained adapter, exactly matching what `reserve_runtime` has
        always done); `train_blocks`/`validation_blocks`/
        `configuration_label` let that same caller honor explicitly-
        supplied inputs (the established Phase 2.7E/2.7G test-injection
        pattern) instead of always auto-deriving from the governed
        dataset. Every later stage passes `allow_fresh_construction=False`
        and no overrides: an absent checkpoint there is a genuine,
        honest "this training position cannot be reconstructed in a
        fresh process" condition (Part 15's CHECKPOINT RECOVERY vs. LIVE
        RUNTIME CONTINUATION distinction), never silently downgraded to
        starting over."""

        job_public_id = job_data["public_id"]
        execution_mode = job_data["execution_mode"]

        def factory() -> Any:
            adapter = adapter_for_execution_mode(execution_mode)
            if not adapter.is_available():
                raise ValidationError(
                    f"runtime adapter for execution_mode '{execution_mode}' is not available in this environment"
                )
            checkpoints = self.list_checkpoints(job_public_id)["items"]
            latest = find_latest_checkpoint(checkpoints=checkpoints) if checkpoints else None
            if latest is not None:
                self._recover_adapter_from_checkpoint(job_data, adapter, checkpoint_row=latest)
            elif allow_fresh_construction:
                resolved_label = configuration_label or (
                    job_data.get("runtime_reservation_report") or {}
                ).get("configuration_label")
                if not resolved_label:
                    raise ValidationError(
                        "configuration_label is required to reserve runtime for a real training job -- "
                        "e.g. 'TEST_INTEGRATION_CONFIGURATION' for a deliberately tiny validation run"
                    )
                job_context = self._build_real_job_context(
                    job_data, train_blocks=train_blocks, validation_blocks=validation_blocks,
                    configuration_label=resolved_label,
                )
                reserve_report = adapter.reserve(
                    resource_plan=job_data["resource_plan_report"], job_context=job_context,
                )
                if report_sink is not None:
                    report_sink.update(reserve_report)
            else:
                raise ValidationError(
                    "no live runtime and no checkpoint exists to recover from for this job -- "
                    "this training position cannot be reconstructed in a fresh process"
                )
            return adapter

        return REGISTRY.get_or_create(job_public_id, factory)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, job_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.create_event(
            connection, job_id=job_id, event_type=event_type, stage=stage, message=message, metadata=metadata,
        )

    def _record_training_failure(self, job_public_id: str, *, error: Exception) -> None:
        """Phase 2.8B: records a genuine training-step failure honestly --
        `status='failed'`, `stage='generate_report'` (the exact same
        transition shape `finalize()` already uses for the success path,
        reused rather than invented), and the real error message in
        `training_state["last_error"]` (the field `generate_report_stage()`
        already reads via `classify_failure()`). Only applied if the job is
        still genuinely `'running'` in the database at the moment of the
        failure -- a concurrent, legitimate `pause()`/`cancel()` call may
        have already moved it to `'paused'`/`'cancelled'` in the same race
        window, and that real, already-correct status is never overwritten
        by this method."""

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            current = public_job_row(job_row)
            if current["status"] != "running":
                return
            training_state = dict(current.get("training_state") or {})
            training_state["last_error"] = str(error)
            self.repository.update_job(
                connection, job_public_id,
                {
                    "status": "failed", "stage": "generate_report", "completed_at": _now(),
                    "training_state_json": training_state,
                },
            )
            self._event(
                connection, job_row["id"], "training_failed", stage=current["stage"],
                message=f"training step failed: {error}",
            )
        # Phase 2.8E, Part 17: "job failed -> adapter released" -- a
        # failed job never trains further, so this process's own
        # possibly-corrupted-mid-step adapter reference must never be
        # reused by a later request for this job; the next legitimate
        # operation (there is none for a failed job except inspection/
        # archival) would reconstruct fresh from the last verified
        # checkpoint if one is ever needed again.
        REGISTRY.evict(job_public_id)

    def _resolve_real_core_model_version(self, core_model_version_public_id: str | None) -> dict[str, Any]:
        """Phase 2.7E: the one identity gate a real (gpu-mode) job must
        pass -- reused, not reinvented: the exact same eligibility rule the
        production pretraining job/worker system already enforces for its
        own job creation (`architecture_verified`, `smoke_tested`,
        `staging`, or `active`), so a Core Model Version this Mini Brain
        job is allowed to train against is never a looser standard than
        what the rest of the codebase already requires. This is a read-
        only lookup through `CoreModelService` (already imported and used
        by this file for other identity resolution) -- no dependency on
        any deployment/runtime-manager library is introduced."""
        if not core_model_version_public_id:
            raise ValidationError(
                "core_model_version_public_id is required for execution_mode='gpu' -- "
                "real training must know exactly which Core Model Version it is training"
            )
        try:
            version = self.core_models.get_version(core_model_version_public_id)
        except NotFoundError as exc:
            raise ValidationError(
                f"core model version not found: {core_model_version_public_id}"
            ) from exc
        if version["lifecycle_status"] not in CoreModelService.ELIGIBLE_FOR_REAL_TRAINING:
            raise ValidationError(
                "core model version must be at least architecture_verified before real training "
                f"(currently '{version['lifecycle_status']}')"
            )
        return version

    # Real dataset status values the production pretraining job system
    # itself accepts (mirrors that same rule, not a new invented one).
    ELIGIBLE_DATASET_STATUSES = {"ready", "archived"}

    # Phase 2.8A established 1,000 as the first real, governed, measured
    # boundary. Phase 2.8D extended real measurement -- real
    # `DatasetVersioningService.create_build()` -> `validate_build()` ->
    # `run_build()` builds, real dataset/training readiness contracts,
    # real MB-22 training qualification (real forward/backward pass,
    # real checkpoint, independently verified), and real fresh-process
    # checkpoint recovery with bit-exact weight restoration -- through
    # 2,500, 5,000, and 10,000 records, all with flat/modest peak-RSS
    # growth and no resource or execution failure. See
    # `deploy/phase-2.8D/TRAINING_SCALE_QUALIFICATION_REPORT.md` §7/§10.
    # `training_readiness_contract()`'s resource envelope classification
    # (criterion Y) treats a request beyond this as `"insufficient_evidence"`,
    # never `READY` -- this is a measured boundary, not an invented
    # production limit.
    LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT = 10000

    def _resolve_real_dataset_version(self, dataset_version_public_id: str | None) -> dict[str, Any]:
        """Phase 2.7F: real training must also know which real dataset it
        trains against -- `pretraining_jobs.dataset_version_id` is a
        required reference the governed checkpoint-registration handoff
        (Phase 2.7F) cannot satisfy without one, and this codebase never
        fabricates a required reference. Read-only lookup through this
        file's own repository (`dataset_versions` is a table MB-22 reads
        to validate identity, never writes to)."""
        if not dataset_version_public_id:
            raise ValidationError(
                "dataset_version_public_id is required for execution_mode='gpu' -- a real "
                "training run must reference a real, ready dataset version"
            )
        with self.repository.transaction() as connection:
            row = self.repository.dataset_version(connection, dataset_version_public_id)
        if row is None:
            raise ValidationError(f"dataset version not found: {dataset_version_public_id}")
        if row["status"] not in self.ELIGIBLE_DATASET_STATUSES:
            raise ValidationError(
                "dataset version must be ready or archived before real training "
                f"(currently '{row['status']}')"
            )
        return dict(row)

    def _build_real_job_context(
        self, job_data: dict[str, Any], *, train_blocks: list[list[int]] | None,
        validation_blocks: list[list[int]] | None, configuration_label: str | None,
    ) -> dict[str, Any]:
        """Phase 2.7E: the identity hand-off point -- turns this job's own
        `core_model_version_public_id` into the real, concrete inputs
        `TorchTrainingAdapter.reserve()`'s `job_context` needs (a real
        `BrudModelConfig`, real `pad_token_id`, a real canonical checkpoint
        root under `settings.resolved_pretraining_dir`). Never builds a
        second model/config representation -- `CoreModelService.
        model_config_for_version()` (Phase 2.7E addition) is the same
        conversion `CoreModelService.initialize()`/`verify_architecture()`/
        `smoke_test()` already use for this exact Core Model Version.

        `train_blocks`/`validation_blocks` are now optional (Phase 2.7G):
        when the caller does not supply them explicitly, they are derived
        for real from this job's own, already-required, real
        `dataset_version_public_id` via `MiniBrainDatasetPipelineService.
        build_blocks()` -- the same canonical dataset-version -> token-
        block pipeline the production worker training path's own
        equivalent private method is built from
        (`core_model.training.dataset_pipeline`). Explicitly-supplied
        blocks (Phase 2.7E/2.7C's own established test pattern, e.g. a
        deliberately tiny synthetic `TEST_INTEGRATION_CONFIGURATION`) are
        always honored as-is and never overridden -- this method never
        second-guesses a caller who already has real, specific blocks in
        hand.

        Checkpoint reference metadata (`tokenizer_metadata`, flows into
        the real checkpoint bundle's own `references.json`) always
        includes this job's real dataset identity/checksum and the real
        tokenizer checksum/normalization version, regardless of which
        block-source path was taken -- so a fresh process can always
        determine exactly which data and tokenizer produced a given
        checkpoint (Phase 2.7G, mission Part 14), not only when blocks
        were auto-derived.
        """
        from core_model.training.pretraining_config import PretrainingConfig

        version = self._resolve_real_core_model_version(job_data.get("core_model_version_public_id"))
        dataset_version_public_id = job_data.get("dataset_version_public_id")
        pipeline_report = None
        if not train_blocks:
            self._resolve_real_dataset_version(dataset_version_public_id)
            pipeline_result = self.dataset_pipeline.build_blocks(
                dataset_version_public_id=dataset_version_public_id,
                core_model_version_public_id=version["public_id"],
            )
            train_blocks = pipeline_result["train_blocks"]
            validation_blocks = pipeline_result["validation_blocks"]
            pipeline_report = pipeline_result
        if not train_blocks:
            raise ValidationError(
                "train_blocks is required to reserve runtime for a real (execution_mode='gpu') "
                "training job, and the real dataset pipeline produced none"
            )
        if not configuration_label:
            raise ValidationError(
                "configuration_label is required to reserve runtime for a real training job -- "
                "e.g. 'TEST_INTEGRATION_CONFIGURATION' for a deliberately tiny validation run"
            )
        model_config, _version_row = self.core_models.model_config_for_version(version["public_id"])
        # sequence_length must track context_length: build_blocks() (above) sizes
        # blocks up to context_length when no override is given, but
        # PretrainingConfig's own dataclass default (64) is independent of it --
        # leaving it unset here silently truncation-fails real models with
        # context_length > 64 at the first pad_sequences() call in run_pretraining().
        checkpoint_root = self.settings.resolved_pretraining_dir / "mini_brain_training_jobs" / job_data["public_id"]
        tokenizer_metadata = {
            "core_model_version_public_id": version["public_id"],
            "core_model_family_public_id": version["family_public_id"],
            "core_model_family_name": version["family_name"],
            "core_model_config_public_id": version["config_public_id"],
            "core_model_version": version["version"],
            "tokenizer_version_public_id": version["tokenizer_version_public_id"],
        }
        if pipeline_report is not None:
            tokenizer_metadata.update({
                "dataset_version_public_id": pipeline_report["dataset_version_public_id"],
                "dataset_checksum_sha256": pipeline_report["dataset_checksum_sha256"],
                "tokenizer_checksum_sha256": pipeline_report["tokenizer_checksum_sha256"],
                "normalization_version": pipeline_report["normalization_version"],
                "block_builder_version": pipeline_report["block_builder_version"],
                "context_length": pipeline_report["context_length"],
                "sequence_length": pipeline_report["sequence_length"],
                "overlength_policy": pipeline_report["overlength_policy"],
                "train_block_count": len(pipeline_report["train_blocks"]),
                "validation_block_count": len(pipeline_report["validation_blocks"]),
            })
        elif dataset_version_public_id:
            tokenizer_metadata["dataset_version_public_id"] = dataset_version_public_id
        return {
            "model_config": model_config,
            "pad_token_id": model_config.pad_token_id,
            "train_blocks": train_blocks,
            "validation_blocks": validation_blocks,
            "pretraining_config": PretrainingConfig(
                initialization_seed=version.get("initialization_seed") or 42,
                sequence_length=model_config.context_length,
            ),
            "checkpoint_root": checkpoint_root,
            "tokenizer_metadata": tokenizer_metadata,
            "configuration_label": configuration_label,
        }

    def _training_contract_result(
        self, status: str, reason: str | None, checks: dict[str, Any], *,
        dataset: dict[str, Any] | None = None, tokenizer: dict[str, Any] | None = None,
        core_model: dict[str, Any] | None = None, training_configuration: dict[str, Any] | None = None,
        resource_estimate: dict[str, Any] | None = None, reproducibility: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "reason": reason,
            "checks": checks,
            "dataset": dataset,
            "tokenizer": tokenizer,
            "core_model": core_model,
            "training_configuration": training_configuration,
            "resource_estimate": resource_estimate,
            "reproducibility": reproducibility,
            "readiness_summary": (
                "READY TO TRAIN -- qualified to start a controlled training run. "
                "This is not a release-readiness verdict and not a model-quality verdict."
                if status == "READY"
                else f"{status}: not qualified to start controlled training"
            ),
        }

    def training_readiness_contract(
        self, *, dataset_version_public_id: str, core_model_version_public_id: str,
        execution_mode: str = "gpu", sequence_length: int | None = None,
        overlength_policy: str = DEFAULT_OVERLENGTH_POLICY,
        pretraining_config: Any | None = None,
    ) -> dict[str, Any]:
        """Phase 2.8A: the Training Readiness Gate. Answers a narrower
        question than `MiniBrainDatasetPipelineService.readiness_contract()`
        (Phase 2.7H) does: not "is this Dataset Version's pipeline output
        usable" but "is this exact (Dataset Version, Core Model Version,
        execution_mode, training configuration) combination qualified to
        START a controlled training run right now." Reuses that dataset
        contract verbatim for every dataset/tokenizer/block criterion
        (folded into `checks["A_through_U_dataset_tokenizer_block_pipeline"]`)
        -- never a second, parallel dataset/tokenizer verification. Adds
        only the training-specific criteria (execution mode eligibility,
        Core Model Version training-lifecycle eligibility, training
        configuration validity, measured resource envelope, checkpoint
        destination writability, checkpoint-provenance infrastructure
        availability). Read-only throughout: no job, checkpoint, dataset,
        or tokenizer row is written, and no directory is created (checkpoint
        destination writability is checked via `os.access()` on the nearest
        already-existing ancestor directory, never via `mkdir()`)."""

        from core_model.training.pretraining_config import PretrainingConfig

        checks: dict[str, dict[str, Any]] = {}

        def record(key: str, passed: bool, detail: Any) -> None:
            checks[key] = {"passed": passed, "detail": detail}

        if execution_mode not in REAL_TRAINING_EXECUTION_MODES:
            record(
                "V_execution_mode_performs_real_training", False,
                f"execution_mode='{execution_mode}' performs no real training (must be one of "
                f"{sorted(REAL_TRAINING_EXECUTION_MODES)})",
            )
            return self._training_contract_result(
                "BLOCKED",
                f"execution_mode must be one of {sorted(REAL_TRAINING_EXECUTION_MODES)} for a real "
                "training readiness check",
                checks,
            )
        record("V_execution_mode_performs_real_training", True, execution_mode)

        # Q/R: Core Model Version exists AND is eligible for real training.
        # This is a stricter, training-specific gate than the dataset
        # pipeline's own CMV resolution below -- `CoreModelService.
        # model_config_for_version()` has no lifecycle requirement at all
        # (it only needs a real config+tokenizer to exist), so a dataset-
        # pipeline READY result alone does NOT prove a Core Model Version is
        # actually eligible to train against. Reused verbatim from
        # `_resolve_real_core_model_version()` (the exact same rule
        # `create_job()` itself enforces), never duplicated.
        try:
            cmv_row = self._resolve_real_core_model_version(core_model_version_public_id)
        except (ValidationError, NotFoundError) as exc:
            reason = str(exc)
            record("Q_core_model_version_eligible_for_training", False, reason)
            return self._training_contract_result("BLOCKED", reason, checks)
        record("Q_core_model_version_eligible_for_training", True, cmv_row["lifecycle_status"])

        # A-U: the real, existing dataset -> tokenizer -> token-block gate,
        # reused whole rather than re-implemented criterion by criterion.
        dataset_contract = self.dataset_pipeline.readiness_contract(
            dataset_version_public_id=dataset_version_public_id,
            core_model_version_public_id=core_model_version_public_id,
            sequence_length=sequence_length, overlength_policy=overlength_policy,
        )
        record(
            "A_through_U_dataset_tokenizer_block_pipeline",
            dataset_contract["status"] == "READY", dataset_contract["checks"],
        )
        if dataset_contract["status"] != "READY":
            return self._training_contract_result(
                dataset_contract["status"], dataset_contract["reason"], checks,
                dataset=dataset_contract.get("dataset"), tokenizer=dataset_contract.get("tokenizer"),
            )

        # V/W: training configuration exists and is internally valid --
        # reuses `PretrainingConfig.validate()` verbatim (never a second
        # validation routine), and the exact same default this service's
        # own `_build_real_job_context()` already uses when no explicit
        # configuration is supplied.
        config = pretraining_config or PretrainingConfig(
            initialization_seed=cmv_row.get("initialization_seed") or 42,
            sequence_length=dataset_contract["blocks"]["sequence_length"],
        )
        record(
            "V_training_configuration_supplied", True,
            "explicit" if pretraining_config is not None else "default (matches _build_real_job_context())",
        )
        try:
            config.validate()
        except ValueError as exc:
            record("W_training_configuration_internally_valid", False, str(exc))
            return self._training_contract_result(
                "BLOCKED", f"training configuration is invalid: {exc}", checks,
                dataset=dataset_contract["dataset"], tokenizer=dataset_contract["tokenizer"],
            )
        record("W_training_configuration_internally_valid", True, None)

        # X/Y: real resource estimate -- the exact same formula
        # `TorchTrainingAdapter.reserve()` already uses (parameter_count *
        # 4 bytes/float32 * 4 buffers: weights + gradients + 2 Adam moment
        # buffers), never a second estimate. Building a real, tiny
        # `BrudForCausalLM` to count its real parameters is itself a pure,
        # read-only computation -- nothing is persisted.
        model_config, _version_row = self.core_models.model_config_for_version(cmv_row["public_id"])
        from core_model.architecture.model import BrudForCausalLM, count_parameters
        from core_model.training.metrics import available_memory_bytes

        parameter_count = count_parameters(BrudForCausalLM(model_config))
        estimated_bytes = parameter_count * 4 * 4
        available_bytes = available_memory_bytes()
        record(
            "X_resource_requirements_known", True,
            {"parameter_count": parameter_count, "estimated_memory_bytes": estimated_bytes},
        )

        record_count = dataset_contract["dataset"]["record_count"]
        if available_bytes is None:
            envelope = "insufficient_evidence"
            y_detail = "available_memory_bytes() could not be determined on this platform"
        elif estimated_bytes > available_bytes:
            envelope = "exceeds_observed_safe_envelope"
            y_detail = f"estimated {estimated_bytes} bytes exceeds {available_bytes} bytes currently available"
        elif record_count > self.LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT:
            envelope = "insufficient_evidence"
            y_detail = (
                f"{record_count} records exceeds the largest scale this phase actually measured "
                f"({self.LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT} records) -- resource behavior "
                "beyond that scale has not been proven safe"
            )
        else:
            envelope = "fits_observed_safe_envelope"
            y_detail = (
                f"estimated {estimated_bytes} bytes fits {available_bytes} bytes available; "
                f"{record_count} records is within the "
                f"{self.LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT}-record validated range"
            )
        y_passed = envelope == "fits_observed_safe_envelope"
        record("Y_resource_requirements_fit_measured_envelope", y_passed, y_detail)
        resource_estimate = {
            "parameter_count": parameter_count,
            "estimated_memory_bytes": estimated_bytes,
            "available_memory_bytes": available_bytes,
            "envelope_classification": envelope,
            "largest_validated_record_count": self.LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT,
            "requested_record_count": record_count,
            "dataset_pipeline_wall_clock_seconds": dataset_contract["resource_estimate"]["pipeline_wall_clock_seconds"],
        }
        if not y_passed:
            return self._training_contract_result(
                "NOT_READY", y_detail, checks, dataset=dataset_contract["dataset"],
                tokenizer=dataset_contract["tokenizer"], resource_estimate=resource_estimate,
            )

        # Z: checkpoint destination writable -- read-only: `os.access()` on
        # whichever ancestor directory already exists, never `mkdir()`.
        checkpoint_root = self.settings.resolved_pretraining_dir
        probe_path = checkpoint_root
        while not probe_path.exists() and probe_path != probe_path.parent:
            probe_path = probe_path.parent
        writable = os.access(probe_path, os.W_OK)
        record("Z_checkpoint_destination_writable", writable, "writable" if writable else "not writable")
        if not writable:
            return self._training_contract_result(
                "BLOCKED", "checkpoint destination is not writable", checks,
                dataset=dataset_contract["dataset"], tokenizer=dataset_contract["tokenizer"],
                resource_estimate=resource_estimate,
            )

        # AA: checkpoint-provenance infrastructure is real and reachable --
        # `TrainingCheckpointManager` itself is not redesigned or duplicated,
        # only confirmed importable, and the real, existing
        # `core_checkpoint_max_bytes` setting is surfaced for transparency.
        try:
            from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager  # noqa: F401
        except ImportError as exc:  # pragma: no cover - defensive only
            record("AA_checkpoint_provenance_infrastructure_available", False, str(exc))
            return self._training_contract_result(
                "BLOCKED", "checkpoint provenance infrastructure is not available", checks,
                dataset=dataset_contract["dataset"], tokenizer=dataset_contract["tokenizer"],
                resource_estimate=resource_estimate,
            )
        record(
            "AA_checkpoint_provenance_infrastructure_available", True,
            f"core_checkpoint_max_bytes={self.settings.core_checkpoint_max_bytes}",
        )

        # AB: this check itself never activates, releases, or assigns
        # anything -- a structural, self-attesting confirmation (verified
        # by source: this method contains no call to `activate()`,
        # `release()`, or any inference-assignment method anywhere in this
        # file or the services it composes).
        record(
            "AB_activation_release_gates_untouched_by_this_check", True,
            "training_readiness_contract() performs no activation/release/assignment call; those "
            "gates are governed separately by the model evaluation and release-governance services, "
            "unmodified by this phase",
        )

        return self._training_contract_result(
            "READY", None, checks,
            dataset=dataset_contract["dataset"], tokenizer=dataset_contract["tokenizer"],
            core_model={
                "core_model_version_public_id": cmv_row["public_id"],
                "lifecycle_status": cmv_row["lifecycle_status"],
                "context_length": model_config.context_length,
            },
            training_configuration=config.to_dict(),
            resource_estimate=resource_estimate,
            reproducibility=dataset_contract["reproducibility"],
        )

    def _job_dir(self, job_public_id: str) -> Path:
        root = self.settings.resolved_document_dir.parent / "training_runs" / job_public_id
        for sub in ("checkpoints", "logs", "manifests", "reports"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        return root

    def job(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_job_row(self.repository.get_job(connection, job_public_id))

    def list_jobs(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_jobs(connection, limit=limit, offset=offset)
        return {"items": [public_job_row(row) for row in rows]}

    def events(self, job_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            rows = self.repository.list_events(connection, job_id=job_row["id"], limit=limit, offset=offset)
        return {"items": [dict(row) for row in rows]}

    def list_checkpoints(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            rows = self.repository.list_checkpoints(connection, job_id=job_row["id"])
        return {"items": [public_checkpoint_row(row) for row in rows]}

    def list_metrics(self, job_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            rows = self.repository.list_metrics(connection, job_id=job_row["id"], limit=limit, offset=offset)
        return {"items": [public_metric_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    # -- stage 1: create job --------------------------------------

    def create_job(
        self, *, topic: str, training_package_session_public_id: str, release_governance_session_public_id: str,
        execution_mode: str, admin_id: str, core_model_version_public_id: str | None = None,
        dataset_version_public_id: str | None = None,
    ) -> dict[str, Any]:
        if not topic.strip():
            raise ValidationError("topic must not be empty")
        if execution_mode not in EXECUTION_MODES:
            raise ValidationError(f"execution_mode must be one of {sorted(EXECUTION_MODES)}")
        if execution_mode in REAL_TRAINING_EXECUTION_MODES:
            self._resolve_real_core_model_version(core_model_version_public_id)
            self._resolve_real_dataset_version(dataset_version_public_id)
        with self.repository.transaction() as connection:
            public_id = self.repository.create_job(
                connection, training_package_session_public_id=training_package_session_public_id,
                release_governance_session_public_id=release_governance_session_public_id, topic=topic,
                execution_mode=execution_mode, created_by_admin_public_id=admin_id,
                core_model_version_public_id=core_model_version_public_id,
                dataset_version_public_id=dataset_version_public_id,
            )
            job_row = self.repository.get_job(connection, public_id)
            self._event(
                connection, job_row["id"], "job_created", stage="validate_release",
                message=f"training job created for topic '{topic}' (execution_mode={execution_mode})",
            )
            return public_job_row(self.repository.get_job(connection, public_id))

    # -- stage 2: validate release approval -----------------------------

    def run_validate_release_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "validate_release":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'validate_release'")

        release_session = self.release_governance.session(job_data["release_governance_session_public_id"])
        report = validate_release_approval(release_session=release_session)
        if not report["valid"]:
            raise ValidationError(f"release validation failed: {report['reason']}")

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"release_validation_report_json": report, "stage": "validate_package"},
            )
            self._event(connection, job_row["id"], "release_validated", stage="validate_release", message="MB-20 release session approved")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 3: validate training package ------------------------------

    def run_validate_package_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "validate_package":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'validate_package'")

        package_session = self.training_pipeline.session(job_data["training_package_session_public_id"])
        report = validate_training_package(package_session=package_session)
        if not report["valid"]:
            raise ValidationError(f"package validation failed: {report['reason']}")

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"package_validation_report_json": report, "stage": "validate_authorization"},
            )
            self._event(connection, job_row["id"], "package_validated", stage="validate_package", message="MB-18 package session approved")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 4: validate admin authorization -----------------------------

    def run_validate_authorization_stage(
        self, job_public_id: str, *, authorization_reason: str, admin_id: str,
    ) -> dict[str, Any]:
        job_data = self.job(job_public_id)
        if job_data["stage"] != "validate_authorization":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'validate_authorization'")
        if not admin_id:
            raise ValidationError("a real admin identity is required to authorize a training job")
        if not authorization_reason.strip():
            raise ValidationError("authorization_reason must not be empty")

        token = str(uuid4())
        report = {
            "authorized": True, "admin_id": admin_id, "reason": authorization_reason, "token": token,
            "disclosure": "this authorization only permits this exact job to proceed -- it never grants any other job, dataset, or release approval",
        }

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {
                    "authorization_report_json": report, "admin_authorized_by": admin_id,
                    "admin_authorization_reason": authorization_reason, "admin_authorization_token": token,
                    "stage": "plan_resources",
                },
            )
            self._event(connection, job_row["id"], "authorization_validated", stage="validate_authorization", message=f"authorized by {admin_id}")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 5: plan resources -------------------------------------------

    def run_plan_resources_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "plan_resources":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'plan_resources'")

        package_session = self.training_pipeline.session(job_data["training_package_session_public_id"])
        hardware_estimate = package_session.get("hardware_estimate_report", {})

        report, latency_ms = _timed(
            plan_resources, execution_mode=job_data["execution_mode"],
            estimated_token_count=hardware_estimate.get("estimated_token_count", 0),
            ram_tier=hardware_estimate.get("ram_tier", "8GB+"), vram_tier=hardware_estimate.get("vram_tier", "none"),
            cpu_only_feasible=hardware_estimate.get("cpu_only_feasible", True),
            estimated_disk_bytes=hardware_estimate.get("estimated_disk_bytes", 0),
            expected_training_duration_category=hardware_estimate.get("expected_training_duration_category", "hours"),
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"resource_plan_report_json": report, "stage": "build_manifest"},
            )
            self._event(connection, job_row["id"], "resources_planned", stage="plan_resources", message=f"cpu_thread_count={report['cpu_thread_count']}")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 6: build training manifest ----------------------------------

    def run_build_manifest_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "build_manifest":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'build_manifest'")

        fingerprint = build_experiment_fingerprint(
            training_package_session_public_id=job_data["training_package_session_public_id"],
            release_governance_session_public_id=job_data["release_governance_session_public_id"],
            execution_mode=job_data["execution_mode"], resource_plan=job_data["resource_plan_report"],
        )
        manifest = build_training_manifest(
            job_public_id=job_public_id, topic=job_data["topic"],
            training_package_session_public_id=job_data["training_package_session_public_id"],
            release_governance_session_public_id=job_data["release_governance_session_public_id"],
            execution_mode=job_data["execution_mode"], resource_plan=job_data["resource_plan_report"],
            fingerprint=fingerprint, created_at=_now(),
        )

        job_dir = self._job_dir(job_public_id)
        from backend.core.json_utils import dumps_json
        manifest_path = resolve_confined_path(job_dir / "manifests", "training_manifest.json")
        manifest_path.write_text(dumps_json(manifest), encoding="utf-8")

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {
                    "training_manifest_json": manifest, "output_directory": str(job_dir),
                    "checkpoint_directory": str(job_dir / "checkpoints"), "stage": "reserve_runtime",
                },
            )
            self._event(connection, job_row["id"], "manifest_built", stage="build_manifest", message="training manifest written")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 7: reserve runtime --------------------------------------------

    def run_reserve_runtime_stage(
        self, job_public_id: str, *, admin_id: str,
        train_blocks: list[list[int]] | None = None,
        validation_blocks: list[list[int]] | None = None,
        configuration_label: str | None = None,
    ) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        real_inputs_attempted = any(
            value is not None for value in (train_blocks, validation_blocks, configuration_label)
        )

        def _persist(report: dict[str, Any]) -> dict[str, Any]:
            with self.repository.transaction() as connection:
                job_row = self.repository.get_job(connection, job_public_id)
                self.repository.update_job(
                    connection, job_public_id,
                    {"runtime_reservation_report_json": report, "stage": "start_training"},
                )
                self._event(connection, job_row["id"], "runtime_reserved", stage="reserve_runtime", message=f"runtime={report.get('runtime')}")
                return public_job_row(self.repository.get_job(connection, job_public_id))

        if not self._real_untested_gpu_job(job_data):
            # Unchanged, original behavior -- test overrides and
            # simulation/cpu-mode jobs never touch the registry/lock.
            if job_data["stage"] != "reserve_runtime":
                raise ValidationError(f"job is at stage '{job_data['stage']}', not 'reserve_runtime'")
            adapter = self._adapter(job_data["execution_mode"])
            if not adapter.is_available():
                raise ValidationError(f"runtime adapter for execution_mode '{job_data['execution_mode']}' is not available in this environment")
            job_context = None
            if job_data["execution_mode"] in REAL_TRAINING_EXECUTION_MODES and real_inputs_attempted:
                job_context = self._build_real_job_context(
                    job_data, train_blocks=train_blocks, validation_blocks=validation_blocks,
                    configuration_label=configuration_label,
                )
            report, latency_ms = _timed(
                adapter.reserve, resource_plan=job_data["resource_plan_report"], job_context=job_context,
            )
            report["latency_ms"] = latency_ms
            return _persist(report)
        else:
            # Phase 2.8E: a genuine, non-test-overridden real (gpu-mode)
            # job -- locked and registry-backed, so a fresh HTTP request
            # (a fresh service, a fresh adapter) genuinely reserves real
            # runtime instead of requiring the caller to hand-supply
            # every train block over the wire (that established
            # test-injection path -- Phase 2.7E/2.7G -- still works
            # exactly as before when the caller does supply inputs).
            #
            # The DB write happens inside the SAME lock hold as the
            # stage-guard check and the reservation itself (Part 12):
            # releasing the lock first would let a second, concurrent
            # `reserve_runtime` call re-read the still-'reserve_runtime'
            # stage and also proceed.
            with self._locked_job_operation(job_public_id):
                job_data = self.job(job_public_id)  # re-read under the lock -- closes the stage-guard race
                if job_data["stage"] != "reserve_runtime":
                    raise ValidationError(f"job is at stage '{job_data['stage']}', not 'reserve_runtime'")

                captured_report: dict[str, Any] = {}
                adapter, latency_ms = _timed(
                    self._ensure_adapter_for_job, job_data=job_data, allow_fresh_construction=True,
                    train_blocks=train_blocks, validation_blocks=validation_blocks,
                    configuration_label=configuration_label, report_sink=captured_report,
                )
                if captured_report:
                    report = captured_report
                else:
                    # The adapter was already live in the registry (a
                    # genuine same-process re-entry, e.g. a retried
                    # request) -- the factory never ran `.reserve()`
                    # again, so report its real, current configuration
                    # rather than fabricating a fresh reservation.
                    report = {
                        "reserved": True, "runtime": "torch_cpu", "configuration_label": adapter.configuration_label,
                    }
                report["latency_ms"] = latency_ms
                return _persist(report)

    # -- stage 8: start training ---------------------------------------------

    def run_start_training_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)

        def _persist() -> dict[str, Any]:
            training_state = {"last_step": 0, "last_epoch": 0, "last_loss": None}
            with self.repository.transaction() as connection:
                job_row = self.repository.get_job(connection, job_public_id)
                self.repository.update_job(
                    connection, job_public_id,
                    {"training_state_json": training_state, "stage": "streaming_metrics", "status": "running", "started_at": _now()},
                )
                self._event(connection, job_row["id"], "training_started", stage="start_training", message="training started")
                return public_job_row(self.repository.get_job(connection, job_public_id))

        if not self._real_untested_gpu_job(job_data):
            if job_data["stage"] != "start_training":
                raise ValidationError(f"job is at stage '{job_data['stage']}', not 'start_training'")
            adapter = self._adapter(job_data["execution_mode"])
            adapter.start(resume_step=0, resume_epoch=0)
            return _persist()
        else:
            # Phase 2.8E: a fresh HTTP request/process may land here with
            # no live adapter -- since nothing has trained yet at this
            # stage (it is a one-time transition, stage-guarded to run
            # exactly once, so no checkpoint can exist before it
            # succeeds), reconstructing fresh from the job's own
            # persisted reservation is always safe here, exactly
            # mirroring what `reserve_runtime` itself would have done.
            # The DB write happens inside the same lock hold (Part 12).
            with self._locked_job_operation(job_public_id):
                job_data = self.job(job_public_id)
                if job_data["stage"] != "start_training":
                    raise ValidationError(f"job is at stage '{job_data['stage']}', not 'start_training'")
                adapter = self._ensure_adapter_for_job(job_data, allow_fresh_construction=True)
                adapter.start(resume_step=0, resume_epoch=0)
                return _persist()

    # -- stage 9: stream metrics (repeatable while status='running') -----------

    def run_stream_metric_stage(self, job_public_id: str, *, step: int, epoch: int, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)

        def _persist(
            job_data: dict[str, Any], metric: dict[str, Any], latency_ms: float, *,
            expected_status: str | None = None,
        ) -> dict[str, Any]:
            # Phase 2.8F: two independent OS processes can both
            # reconstruct their own adapter from the same last checkpoint
            # (neither can see the other's in-flight work -- the
            # registry/lock are process-local) and both genuinely execute
            # the same nominal step, reproduced directly as two metric
            # rows for the same (job, step, epoch). `append_metric()`'s
            # INSERT is now protected by a real DB-level UNIQUE index
            # (`ux_mini_brain_training_metrics_job_step_epoch`, mirroring
            # the checkpoint table's own, already-proven pattern) -- the
            # loser gets a real `sqlite3.IntegrityError`, wrapped as
            # `ConflictError` by `transaction()`, translated below into a
            # clear, typed rejection instead of a silent duplicate row.
            # `expected_status` (gpu-mode only) additionally guards
            # against writing a step's result onto a job a concurrent
            # worker already paused/cancelled/finalized -- reproduced
            # directly as `status='paused'`/`'completed'` coexisting with
            # a `training_state.last_step` that was written afterward.
            try:
                with self.repository.transaction() as connection:
                    job_row = self.repository.get_job(connection, job_public_id)
                    self.repository.append_metric(
                        connection, job_id=job_row["id"], step=metric["step"], epoch=metric["epoch"], loss=metric.get("loss"),
                        learning_rate=metric.get("learning_rate"), tokens_per_second=metric.get("tokens_per_second"),
                        examples_per_second=metric.get("examples_per_second"), gpu_memory_mb=metric.get("gpu_memory_mb"),
                        cpu_memory_mb=metric.get("cpu_memory_mb"),
                    )
                    training_state = dict(job_data["training_state"])
                    training_state.update({"last_step": metric["step"], "last_epoch": metric["epoch"], "last_loss": metric.get("loss")})
                    self.repository.update_job(
                        connection, job_public_id, {"training_state_json": training_state},
                        expected_status=expected_status,
                    )
                    self._event(
                        connection, job_row["id"], "metric_streamed", stage="streaming_metrics",
                        message=f"step={metric['step']} loss={metric.get('loss')}", metadata={"latency_ms": latency_ms},
                    )
                    return public_job_row(self.repository.get_job(connection, job_public_id))
            except ConflictError as exc:
                raise ValidationError(
                    f"step={metric['step']} epoch={metric['epoch']} for this job was already recorded, or the "
                    "job's status changed, by a concurrent worker -- refusing to write a duplicate/stale result"
                ) from exc

        if not self._real_untested_gpu_job(job_data):
            if job_data["stage"] != "streaming_metrics" or job_data["status"] != "running":
                raise ValidationError(f"job must be at stage 'streaming_metrics' with status 'running' to stream metrics (currently stage='{job_data['stage']}', status='{job_data['status']}')")
            adapter = self._adapter(job_data["execution_mode"])
            try:
                metric, latency_ms = _timed(adapter.step, step=step, epoch=epoch)
            except Exception as exc:
                # Phase 2.8B: before this fix, ANY exception from `adapter.step()`
                # (a genuine training-time failure, not the expected pause/cancel
                # early-return signal) propagated straight out of this method with
                # the job's own `status` left exactly as it was ('running')
                # forever -- no event recorded, no transition to the schema's own
                # already-supported 'failed' status
                # (`backend/database/schema.py` CHECK constraint), and
                # `generate_report_stage()`'s existing failure-handling branch
                # (`classify_failure(error_message=...training_state["last_error"])`,
                # already reading a field nothing ever wrote) permanently
                # unreachable. `_record_training_failure()` completes that
                # already-half-built mechanism at its exact missing boundary --
                # never invents a new one -- and re-raises the original exception
                # so callers still observe the real error.
                self._record_training_failure(job_public_id, error=exc)
                raise
            return _persist(job_data, metric, latency_ms)
        else:
            # Phase 2.8E: no live adapter in this process is no longer an
            # automatic training failure -- if a verified checkpoint
            # exists, this reconstructs and continues from it exactly as
            # `resume()` always has (Phase 2.8C); only a genuinely
            # unrecoverable position (no live adapter AND no checkpoint
            # -- live-only progress since the last save, honestly lost,
            # never fabricated back) still fails the job, distinctly from
            # a real training-time exception.
            #
            # The DB write is inside the SAME lock hold as the step
            # itself (Part 12): two concurrent, distinct-step requests
            # must commit in the same order their real `adapter.step()`
            # calls actually executed -- releasing the lock before the
            # write would let a later-executed step's write land first
            # and then be overwritten by an earlier-executed step's
            # write, silently reverting `training_state.last_step`.
            with self._locked_job_operation(job_public_id):
                job_data = self.job(job_public_id)
                if job_data["stage"] != "streaming_metrics" or job_data["status"] != "running":
                    raise ValidationError(f"job must be at stage 'streaming_metrics' with status 'running' to stream metrics (currently stage='{job_data['stage']}', status='{job_data['status']}')")
                # Reconstruction failures (no live adapter AND no
                # checkpoint) are a distinct, honest "this training
                # position cannot be reconstructed in a fresh process"
                # condition -- never conflated with a genuine training-
                # time exception, and never marks the job 'failed': the
                # job's own persisted state is not wrong, it is simply
                # unreachable from THIS process right now, and a request
                # served by the right process (or after a checkpoint
                # exists) can still succeed.
                adapter = self._ensure_adapter_for_job(job_data, allow_fresh_construction=False)
                try:
                    metric, latency_ms = _timed(adapter.step, step=step, epoch=epoch)
                except Exception as exc:
                    self._record_training_failure(job_public_id, error=exc)
                    raise
                return _persist(job_data, metric, latency_ms, expected_status="running")

    # -- stage 10: save checkpoint (repeatable while status IN running/paused) ---

    def run_save_checkpoint_stage(self, job_public_id: str, *, step: int, epoch: int, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)

        def _checkpoint_via(adapter: Any) -> tuple[dict[str, Any], float]:
            existing = self.list_checkpoints(job_public_id)["items"]
            checkpoint_name = build_checkpoint_name(step=step, epoch=epoch)
            overwrite_check = check_no_overwrite(
                checkpoint_name=checkpoint_name, existing_checkpoint_names=[c["checkpoint_name"] for c in existing],
            )
            if not overwrite_check["safe_to_write"]:
                raise ValidationError(f"checkpoint '{checkpoint_name}' already exists -- an existing checkpoint is never overwritten")
            job_dir = self._job_dir(job_public_id)
            checkpoint_path = resolve_confined_path(job_dir / "checkpoints", f"{checkpoint_name}.json")
            return _timed(adapter.save_checkpoint, path=checkpoint_path, step=step, epoch=epoch), checkpoint_name

        def _persist(job_data: dict[str, Any], result: dict[str, Any], checkpoint_name: str, latency_ms: float) -> dict[str, Any]:
            with self.repository.transaction() as connection:
                job_row = self.repository.get_job(connection, job_public_id)
                self.repository.create_checkpoint(
                    connection, job_id=job_row["id"], step=step, epoch=epoch, checkpoint_name=checkpoint_name,
                    relative_path=f"checkpoints/{checkpoint_name}.json", sha256=result["sha256"],
                    file_size_bytes=result["file_size_bytes"], is_metadata_only=result["is_metadata_only"],
                    core_model_version_public_id=job_data.get("core_model_version_public_id"),
                )
                self._event(
                    connection, job_row["id"], "checkpoint_saved", stage=job_data["stage"],
                    message=f"{checkpoint_name} saved", metadata={"latency_ms": latency_ms},
                )
                return public_job_row(self.repository.get_job(connection, job_public_id))

        if not self._real_untested_gpu_job(job_data):
            if job_data["status"] not in ("running", "paused"):
                raise ValidationError(f"job status must be 'running' or 'paused' to save a checkpoint (currently '{job_data['status']}')")
            adapter = self._adapter(job_data["execution_mode"])
            (result, latency_ms), checkpoint_name = _checkpoint_via(adapter)
            return _persist(job_data, result, checkpoint_name, latency_ms)
        else:
            # Phase 2.8E: a fresh process recovers from the latest
            # existing checkpoint (if any) before saving a new one -- the
            # new checkpoint always reflects real, restored/continued
            # state, never a placeholder. The overwrite check, the real
            # save, and the DB write all happen inside the SAME lock
            # hold (Part 12): two concurrent saves at the same step must
            # never both pass the overwrite check and both write a
            # checkpoint row.
            with self._locked_job_operation(job_public_id):
                job_data = self.job(job_public_id)
                if job_data["status"] not in ("running", "paused"):
                    raise ValidationError(f"job status must be 'running' or 'paused' to save a checkpoint (currently '{job_data['status']}')")
                adapter = self._ensure_adapter_for_job(job_data, allow_fresh_construction=False)
                (result, latency_ms), checkpoint_name = _checkpoint_via(adapter)
                return _persist(job_data, result, checkpoint_name, latency_ms)

    # -- stage 11: pause / resume ----------------------------------------------

    def pause(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)

        def _persist(job_data: dict[str, Any], *, expected_status: str | None = None) -> dict[str, Any]:
            try:
                with self.repository.transaction() as connection:
                    job_row = self.repository.get_job(connection, job_public_id)
                    self.repository.update_job(
                        connection, job_public_id, {"status": "paused"}, expected_status=expected_status,
                    )
                    self._event(connection, job_row["id"], "training_paused", stage=job_data["stage"], message="training paused")
                    return public_job_row(self.repository.get_job(connection, job_public_id))
            except ConflictError as exc:
                current = self.job(job_public_id)
                raise ValidationError(
                    f"job status must be 'running' to pause (currently '{current['status']}', "
                    "changed by a concurrent worker)"
                ) from exc

        if not self._real_untested_gpu_job(job_data):
            if job_data["status"] != "running":
                raise ValidationError(f"job status must be 'running' to pause (currently '{job_data['status']}')")
            adapter = self._adapter(job_data["execution_mode"])
            adapter.pause()
            return _persist(job_data)
        else:
            # The DB write happens inside the same lock hold (Part 12).
            # Phase 2.8F: `expected_status='running'` is a real,
            # cross-process compare-and-swap -- this process's own lock
            # cannot see a different worker that already
            # cancelled/finalized/paused this job in the meantime.
            with self._locked_job_operation(job_public_id):
                job_data = self.job(job_public_id)
                if job_data["status"] != "running":
                    raise ValidationError(f"job status must be 'running' to pause (currently '{job_data['status']}')")
                try:
                    adapter = self._ensure_adapter_for_job(job_data, allow_fresh_construction=False)
                    adapter.pause()
                except ValidationError:
                    # Phase 2.8E: no live adapter in this process AND no
                    # checkpoint to recover one from -- there is nothing
                    # live to pause here. The DB-level status transition
                    # below is still the authoritative signal a later
                    # resume() acts on; this is never treated as an
                    # error, since "pause" is fundamentally a request to
                    # stop, not a request that requires live state.
                    pass
                return _persist(job_data, expected_status="running")

    def resume(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["status"] != "paused":
            raise ValidationError(f"job status must be 'paused' to resume (currently '{job_data['status']}')")

        if not self._real_untested_gpu_job(job_data):
            checkpoints = self.list_checkpoints(job_public_id)["items"]
            latest = find_latest_checkpoint(checkpoints=checkpoints)
            recent_metrics = self.list_metrics(job_public_id, limit=100, offset=0)["items"]
            last_metric = recent_metrics[-1] if recent_metrics else None
            resume_state = build_resume_state(latest_checkpoint=latest, last_metric=last_metric)

            adapter = self._adapter(job_data["execution_mode"])
            # Phase 2.8C: distinguishes real, genuine recovery from in-process
            # pause/resume, rather than conflating them. `getattr(adapter,
            # "_model", "n/a")` is `None` only for a real `TorchTrainingAdapter`
            # that has never been configured in THIS process (a fresh process/
            # fresh service instance -- the exact scenario Phase 2.8B proved
            # was previously unsupported) -- an already-live, in-process
            # adapter (Phase 2.8B's own tested case) is untouched by this
            # branch and continues to use the existing, unmodified
            # `adapter.resume()` flag-flip. `SimulationTrainingAdapter`/
            # `LlamaCppTrainingAdapter` have no `_model` attribute at all and
            # never attempt real recovery (`getattr(..., "n/a")` is truthy for
            # them, so they fall straight to the existing `else` branch).
            recovered_from_checkpoint = False
            if (
                job_data["execution_mode"] in REAL_TRAINING_EXECUTION_MODES
                and getattr(adapter, "_model", "n/a") is None
            ):
                if latest is None:
                    raise ValidationError(
                        "no checkpoint exists for this job -- a fresh process cannot recover training "
                        "that was never checkpointed"
                    )
                self._recover_adapter_from_checkpoint(job_data, adapter, checkpoint_row=latest)
                recovered_from_checkpoint = True
            else:
                adapter.resume()

            with self.repository.transaction() as connection:
                job_row = self.repository.get_job(connection, job_public_id)
                self.repository.update_job(connection, job_public_id, {"status": "running"})
                self._event(
                    connection, job_row["id"],
                    "training_recovered_from_checkpoint" if recovered_from_checkpoint else "training_resumed",
                    stage=job_data["stage"],
                    message=(
                        f"training recovered from checkpoint {latest['checkpoint_name']}"
                        if recovered_from_checkpoint else "training resumed"
                    ),
                    metadata={"resume_state": resume_state},
                )
                return public_job_row(self.repository.get_job(connection, job_public_id))
        else:
            # Phase 2.8E: the same distinction, generalized through the
            # process-local registry rather than inspecting one specific
            # adapter's `_model` attribute -- `REGISTRY.get()` answers
            # "does THIS process already hold a live adapter for THIS
            # job" precisely, for any earlier stage (not only a prior
            # `resume()`), and the recovered/reused adapter is registered
            # (or re-confirmed registered) so every later stage in this
            # same process reuses it without re-verifying the checkpoint.
            #
            # The entire status-guard-check -> recover/reuse ->
            # status='running' DB write happens under ONE hold of the
            # per-job lock (Part 12): two concurrent resumes must never
            # both observe 'paused' and both "succeed" -- releasing the
            # lock between the recovery and the DB write would reopen
            # exactly that race.
            with self._locked_job_operation(job_public_id):
                job_data = self.job(job_public_id)
                if job_data["status"] != "paused":
                    raise ValidationError(f"job status must be 'paused' to resume (currently '{job_data['status']}')")

                checkpoints = self.list_checkpoints(job_public_id)["items"]
                latest = find_latest_checkpoint(checkpoints=checkpoints)
                recent_metrics = self.list_metrics(job_public_id, limit=100, offset=0)["items"]
                last_metric = recent_metrics[-1] if recent_metrics else None
                resume_state = build_resume_state(latest_checkpoint=latest, last_metric=last_metric)

                live = REGISTRY.get(job_public_id)
                recovered_from_checkpoint = live is None
                if live is not None:
                    live.resume()
                else:
                    if latest is None:
                        raise ValidationError(
                            "no checkpoint exists for this job -- a fresh process cannot recover training "
                            "that was never checkpointed"
                        )
                    self._ensure_adapter_for_job(job_data, allow_fresh_construction=False)

                # Phase 2.8F: the per-job lock above only serializes THIS
                # process's own threads/requests -- it cannot see a
                # different OS process's concurrent `resume()` (reproduced
                # directly: two independent worker processes both
                # observing status='paused' and both completing a real
                # recovery, each recording its own
                # 'training_recovered_from_checkpoint' event). The write
                # below is a real, atomic compare-and-swap
                # (`expected_status='paused'`, Part 5's "transactional
                # state transition") -- SQLite itself, not this process's
                # lock, is what decides whether this recovery is still
                # valid at commit time; a losing process gets a clean,
                # typed rejection instead of a second, duplicate recovery.
                try:
                    with self.repository.transaction() as connection:
                        job_row = self.repository.get_job(connection, job_public_id)
                        self.repository.update_job(
                            connection, job_public_id, {"status": "running"}, expected_status="paused",
                        )
                        self._event(
                            connection, job_row["id"],
                            "training_recovered_from_checkpoint" if recovered_from_checkpoint else "training_resumed",
                            stage=job_data["stage"],
                            message=(
                                f"training recovered from checkpoint {latest['checkpoint_name']}"
                                if recovered_from_checkpoint else "training resumed"
                            ),
                            metadata={"resume_state": resume_state},
                        )
                        return public_job_row(self.repository.get_job(connection, job_public_id))
                except ConflictError as exc:
                    current = self.job(job_public_id)
                    raise ValidationError(
                        f"job status must be 'paused' to resume (currently '{current['status']}', "
                        "changed by a concurrent worker)"
                    ) from exc

    def _recover_adapter_from_checkpoint(
        self, job_data: dict[str, Any], adapter: Any, *, checkpoint_row: dict[str, Any],
    ) -> None:
        """Phase 2.8C: the real, fresh-process checkpoint recovery path
        Phase 2.8B documented as missing. Reconstructs a genuinely fresh
        adapter's real in-memory training state from the real, on-disk
        checkpoint bundle -- never trusting the checkpoint merely because
        it exists.

        Order matters and mirrors the mission's own conceptual flow:
        (1) resolve the checkpoint's real canonical directory from this
        job's own real pointer file, confined to this job's own real
        checkpoint root (path-traversal safe -- never an arbitrary,
        caller-supplied path); (2) `TrainingCheckpointManager.load_states()`
        verifies checksums and fails closed on any corruption before
        returning anything; (3) the checkpoint's own recorded identity
        (`references.json`) is compared against THIS job's own live
        `dataset_version_public_id`/`core_model_version_public_id` --
        rejected on any mismatch, never silently substituted; (4) the
        exact real dataset/tokenizer checksums are independently
        re-verified against the live dataset/tokenizer rows via the same,
        unmodified `MiniBrainDatasetPipelineService.build_blocks()` every
        other real job creation already uses -- never a second, looser
        verification; (5) only then is a real `BrudForCausalLM`
        constructed and its real weights loaded via `load_state_dict()`,
        and the adapter's real in-memory state restored via
        `TorchTrainingAdapter.restore_from_checkpoint()`."""

        from backend.core.json_utils import loads_json
        from core_model.architecture.model import BrudForCausalLM
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
        from core_model.training.pretraining_config import PretrainingConfig

        job_dir = self._job_dir(job_data["public_id"])
        pointer_path = job_dir / checkpoint_row["relative_path"]
        if not pointer_path.is_file():
            raise ValidationError(f"checkpoint pointer file is missing: {checkpoint_row['relative_path']}")
        pointer = loads_json(pointer_path.read_text(encoding="utf-8"))
        canonical_dir = Path(pointer["canonical_checkpoint_directory"])

        expected_root = (
            self.settings.resolved_pretraining_dir / "mini_brain_training_jobs" / job_data["public_id"]
        ).resolve()
        if not canonical_dir.resolve().is_relative_to(expected_root):
            raise ValidationError("checkpoint path is outside this job's own checkpoint root")

        manager = TrainingCheckpointManager(canonical_dir.parent, self.settings.core_checkpoint_max_bytes)
        states = manager.load_states(canonical_dir)  # fails closed on any checksum mismatch
        references = states["references"]

        if references.get("dataset_version_public_id") != job_data.get("dataset_version_public_id"):
            raise ValidationError(
                "checkpoint dataset identity does not match this job's own dataset -- refusing to recover"
            )
        if references.get("core_model_version_public_id") != job_data.get("core_model_version_public_id"):
            raise ValidationError(
                "checkpoint core model identity does not match this job's own core model version -- "
                "refusing to recover"
            )

        version = self._resolve_real_core_model_version(job_data["core_model_version_public_id"])
        model_config, _version_row = self.core_models.model_config_for_version(version["public_id"])

        pipeline_result = self.dataset_pipeline.build_blocks(
            dataset_version_public_id=job_data["dataset_version_public_id"],
            core_model_version_public_id=version["public_id"],
        )
        if pipeline_result["dataset_checksum_sha256"] != references.get("dataset_checksum_sha256"):
            raise ValidationError(
                "checkpoint dataset checksum does not match the live dataset -- refusing to recover"
            )
        if pipeline_result["tokenizer_checksum_sha256"] != references.get("tokenizer_checksum_sha256"):
            raise ValidationError(
                "checkpoint tokenizer checksum does not match the live tokenizer -- refusing to recover"
            )

        model = BrudForCausalLM(model_config)
        model.load_state_dict(states["model"])

        adapter.restore_from_checkpoint(
            model=model,
            optimizer_state=states["optimizer"],
            scheduler_state=states["scheduler"],
            rng_state=states["rng"],
            completed_steps=states["trainer_state"].get("completed_steps", checkpoint_row["step"]),
            model_config=model_config,
            pad_token_id=model_config.pad_token_id,
            train_blocks=pipeline_result["train_blocks"],
            validation_blocks=pipeline_result["validation_blocks"],
            pretraining_config=PretrainingConfig(
                initialization_seed=version.get("initialization_seed") or 42,
                sequence_length=references.get("sequence_length") or model_config.context_length,
            ),
            checkpoint_root=canonical_dir.parent,
            tokenizer_metadata={k: v for k, v in references.items() if k != "architecture_name"},
            configuration_label=references.get("configuration_label", "unconfigured"),
        )

    # -- cancel ------------------------------------------------------------------

    def cancel(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["status"] not in ("in_progress", "running", "paused"):
            raise ValidationError(f"job status must be in-progress, running, or paused to cancel (currently '{job_data['status']}')")

        def _persist(job_data: dict[str, Any], *, expected_status: tuple[str, ...] | None = None) -> dict[str, Any]:
            # Phase 2.8E, Part 17: a cancelled job can never be resumed
            # or continued -- release this process's own adapter
            # reference now, so it is never kept alive indefinitely.
            REGISTRY.evict(job_public_id)
            try:
                with self.repository.transaction() as connection:
                    job_row = self.repository.get_job(connection, job_public_id)
                    self.repository.update_job(
                        connection, job_public_id,
                        {"status": "cancelled", "stage": "cancelled", "completed_at": _now()},
                        expected_status=expected_status,
                    )
                    self._event(connection, job_row["id"], "training_cancelled", stage=job_data["stage"], message="training cancelled by admin")
                    return public_job_row(self.repository.get_job(connection, job_public_id))
            except ConflictError as exc:
                current = self.job(job_public_id)
                raise ValidationError(
                    f"job status must be in-progress, running, or paused to cancel (currently "
                    f"'{current['status']}', changed by a concurrent worker)"
                ) from exc

        if not self._real_untested_gpu_job(job_data):
            if job_data["status"] in ("running", "paused"):
                adapter = self._adapter(job_data["execution_mode"])
                adapter.cancel()
            return _persist(job_data)
        else:
            # The status guard, the adapter touch, the eviction, and the
            # DB write all happen inside the same lock hold (Part 12).
            # Phase 2.8F: `expected_status` is a real, cross-process
            # compare-and-swap -- a concurrent finalize()/cancel() from a
            # DIFFERENT worker process cannot be observed by this
            # process's own lock.
            with self._locked_job_operation(job_public_id):
                job_data = self.job(job_public_id)
                if job_data["status"] not in ("in_progress", "running", "paused"):
                    raise ValidationError(f"job status must be in-progress, running, or paused to cancel (currently '{job_data['status']}')")
                if job_data["status"] in ("running", "paused"):
                    try:
                        adapter = self._ensure_adapter_for_job(job_data, allow_fresh_construction=False)
                        adapter.cancel()
                    except ValidationError:
                        # No live adapter and no checkpoint to recover --
                        # nothing live to cancel; the job is still
                        # correctly marked cancelled below.
                        pass
                return _persist(job_data, expected_status=("in_progress", "running", "paused"))

    # -- stage 12: finalize training ----------------------------------------------

    def finalize(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["status"] not in ("running", "paused"):
            raise ValidationError(f"job status must be 'running' or 'paused' to finalize (currently '{job_data['status']}')")

        def _persist(job_data: dict[str, Any], *, expected_status: tuple[str, ...] | None = None) -> dict[str, Any]:
            # Phase 2.8E, Part 17: a finalized (completed) job never
            # trains further -- release this process's own adapter
            # reference.
            REGISTRY.evict(job_public_id)
            try:
                with self.repository.transaction() as connection:
                    job_row = self.repository.get_job(connection, job_public_id)
                    self.repository.update_job(
                        connection, job_public_id,
                        {"status": "completed", "stage": "generate_report", "completed_at": _now()},
                        expected_status=expected_status,
                    )
                    self._event(connection, job_row["id"], "training_finalized", stage=job_data["stage"], message="training finalized")
                    return public_job_row(self.repository.get_job(connection, job_public_id))
            except ConflictError as exc:
                current = self.job(job_public_id)
                raise ValidationError(
                    f"job status must be 'running' or 'paused' to finalize (currently '{current['status']}', "
                    "changed by a concurrent worker)"
                ) from exc

        if not self._real_untested_gpu_job(job_data):
            adapter = self._adapter(job_data["execution_mode"])
            adapter.finalize()
            return _persist(job_data)
        else:
            # The status guard, the adapter touch, the eviction, and the
            # DB write all happen inside the same lock hold (Part 12).
            # Phase 2.8F: `expected_status` is a real, cross-process
            # compare-and-swap against a concurrent cancel()/finalize()/
            # pause() from a different worker process (reproduced
            # directly: a concurrent step's write landing after finalize
            # committed -- Part 4E).
            with self._locked_job_operation(job_public_id):
                job_data = self.job(job_public_id)
                if job_data["status"] not in ("running", "paused"):
                    raise ValidationError(f"job status must be 'running' or 'paused' to finalize (currently '{job_data['status']}')")
                try:
                    adapter = self._ensure_adapter_for_job(job_data, allow_fresh_construction=False)
                    adapter.finalize()
                except ValidationError:
                    # No live adapter and no checkpoint to recover -- the
                    # real trained state (if any) genuinely predates the
                    # last checkpoint; finalize still records completion
                    # honestly rather than blocking a legitimate terminal
                    # transition on unrecoverable, ephemeral state.
                    pass
                return _persist(job_data, expected_status=("running", "paused"))

    # -- stage 13: generate final report -------------------------------------------

    def generate_report_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "generate_report":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'generate_report'")

        metrics = self.list_metrics(job_public_id, limit=100, offset=0)["items"]
        checkpoints = self.list_checkpoints(job_public_id)["items"]
        failure_summary = None
        if job_data["status"] == "failed":
            failure_summary = classify_failure(error_message=job_data.get("training_state", {}).get("last_error"))

        report = generate_job_report(
            job_public_id=job_public_id, topic=job_data["topic"], execution_mode=job_data["execution_mode"],
            training_package_session_public_id=job_data["training_package_session_public_id"],
            release_governance_session_public_id=job_data["release_governance_session_public_id"],
            status=job_data["status"], started_at=job_data["started_at"], completed_at=job_data["completed_at"],
            metrics=metrics, checkpoints=checkpoints, resource_plan=job_data["resource_plan_report"],
            fingerprint=job_data["training_manifest"].get("fingerprint", {}), failure_summary=failure_summary,
        )

        job_dir = self._job_dir(job_public_id)
        from backend.core.json_utils import dumps_json
        report_path = resolve_confined_path(job_dir / "reports", "final_report.json")
        report_path.write_text(dumps_json(report), encoding="utf-8")

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"final_report_json": report, "stage": "awaiting_archive"},
            )
            self._event(connection, job_row["id"], "final_report_generated", stage="generate_report", message=f"final_loss={report['final_loss']}")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 14: archive job -------------------------------------------------------

    def archive(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        job_data = self.job(job_public_id)
        if job_data["status"] not in ("completed", "cancelled"):
            raise ValidationError(f"job status must be 'completed' or 'cancelled' to archive (currently '{job_data['status']}')")

        # Phase 2.8E, Part 17: defensive, idempotent double-eviction --
        # `finalize()`/`cancel()` already evict on the success path, but
        # an archived job must never retain a live adapter reference
        # under any path.
        REGISTRY.evict(job_public_id)

        final_status = job_data["status"]
        metrics = self.list_metrics(job_public_id, limit=100, offset=0)["items"]
        checkpoints = self.list_checkpoints(job_public_id)["items"]
        losses = [m["loss"] for m in metrics if m.get("loss") is not None]

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.create_memory(
                connection, job_id=job_row["id"], topic=job_data["topic"], execution_mode=job_data["execution_mode"],
                final_status=final_status, total_steps=len(metrics),
                final_loss=losses[-1] if losses else None, best_loss=min(losses) if losses else None,
                checkpoint_count=len(checkpoints), recorded_by_admin_public_id=admin_id,
            )
            self.repository.update_job(
                connection, job_public_id, {"status": "archived", "stage": "archived", "archived_at": _now()},
            )
            self._event(
                connection, job_row["id"], "job_archived", stage="awaiting_archive",
                message=f"job archived (final_status={final_status}) -- no deployment or promotion has occurred",
                metadata={"admin_id": admin_id},
            )
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- audit -----------------------------------------------------------------------

    def audit(self, job_public_id: str) -> dict[str, Any]:
        job_data = self.job(job_public_id)
        events = self.events(job_public_id, limit=100)["items"]
        return build_training_audit(events=events, admin_authorized_by=job_data.get("admin_authorized_by"))


__all__ = ["MiniBrainTrainingEngineService"]
