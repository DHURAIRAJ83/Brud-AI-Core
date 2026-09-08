"""Phase 2.8J: training determinism, extended stability, and independent
checkpoint state-restoration proof, against the same real `tiny_preset`
qualification model Phase 2.8G established (vocab_size=2000,
300-record dataset, context_length=512, sequence_length=512).

Reuses Phase 2.8G's real tokenizer/Core-Model-Version construction
helpers (`_real_tokenizer_large`, `_real_core_model_version_tiny_preset`)
and worker primitives (`worker_step`, `worker_checkpoint`, `worker_pause`,
`worker_resume`, `worker_finalize`) verbatim via import, rather than
duplicating them -- this file adds only what Phase 2.8G did not already
prove: independent (never merely `restore_from_checkpoint()`-trusting)
checkpoint state verification, and a controlled paused/resumed vs.
continuous training determinism comparison.

Every job/dataset/tokenizer/Core-Model-Version this file builds lives
entirely under an isolated `tmp_dir` -- the production database is never
opened by this file at all, matching every prior phase's own runner.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "backend"))

import _phase28g_subprocess_runner as g  # noqa: E402

# Re-exported so a caller can invoke this file's own CLI for these too.
worker_step = g.worker_step
worker_checkpoint = g.worker_checkpoint
worker_pause = g.worker_pause
worker_resume = g.worker_resume
worker_finalize = g.worker_finalize
worker_cancel = g.worker_cancel
_settings = g._settings
_service = g._service
_rss_kib = g._rss_kib
_params_sha256 = g._params_sha256
_wait_for_signal = g._wait_for_signal


def build_shared_fixtures(tmp_dir: str, name_suffix: str) -> None:
    """Builds ONE real tokenizer + Core Model Version + dataset, shared
    by every job this file creates afterward -- so a determinism
    comparison between two jobs is actually comparing the same
    architecture/weights-initialization-seed/tokenizer/dataset, not two
    independently (and therefore differently) constructed ones."""

    import time

    from backend.database.migrations import initialize_database

    settings = _settings(tmp_dir)
    initialize_database(settings.resolved_database_path)

    import importlib
    mod_h = importlib.import_module("test_phase27h_training_dataset_readiness")
    mod_svc = importlib.import_module("test_mini_brain_training_engine_service")

    from backend.main import create_app
    app = create_app(settings)
    admin_id = mod_svc._create_admin(app, username=f"admin-{name_suffix}")

    t0 = time.perf_counter()
    tokenizer_id, achieved_vocab_size = g._real_tokenizer_large(settings, name_suffix=name_suffix)
    tokenizer_build_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    cmv_id, config_id = g._real_core_model_version_tiny_preset(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )
    cmv_build_seconds = time.perf_counter() - t0

    texts = mod_h._generate_corpus(g.REAL_TRAINING_DATASET_RECORDS, seed_offset=hash(name_suffix) % 1000)
    t0 = time.perf_counter()
    dataset_id, _, _ = mod_h._build_real_dataset_via_service(settings, name_suffix=name_suffix, record_texts=texts)
    dataset_build_seconds = time.perf_counter() - t0

    import asyncio
    tp_id, rg_id = asyncio.run(mod_svc._seed_approved_package_and_release(app, admin_id, topic=name_suffix))

    print(json.dumps({
        "admin_id": admin_id, "tokenizer_id": tokenizer_id, "tokenizer_achieved_vocab_size": achieved_vocab_size,
        "cmv_id": cmv_id, "config_id": config_id, "dataset_id": dataset_id,
        "training_package_session_public_id": tp_id, "release_governance_session_public_id": rg_id,
        "tokenizer_build_seconds": tokenizer_build_seconds, "cmv_build_seconds": cmv_build_seconds,
        "dataset_build_seconds": dataset_build_seconds,
    }))


def _create_job_impl(svc, name_suffix, admin_id, cmv_id, dataset_id, tp_id, rg_id, configuration_label) -> str:
    """Creates and advances ONE job through reserve+start against the
    shared fixtures, without training any steps yet. Returns the job's
    public_id. MUST be called in the SAME process that will also train
    the job's first step -- `run_stream_metric_stage()`'s very first
    call for a job has no checkpoint to recover from yet, so a fresh
    process cannot pick it up (`allow_fresh_construction=True` is only
    ever used by `reserve_runtime` itself)."""

    import torch

    job = svc.create_job(
        topic=f"{name_suffix}-job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8j determinism/stability", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    # NOTE (a Phase 2.8J finding, not a code change): `TorchTrainingAdapter
    # .reserve()` constructs `BrudForCausalLM(self._model_config)` with NO
    # `torch.manual_seed()` call of its own -- unlike
    # `CoreModelService.model_config_for_version()`'s separate CMV-audit
    # path, which does seed before construction. Left exactly as found
    # (Part H: no code change without a reproduced defect, and a fresh,
    # unseeded random initialization per job is plausibly intentional
    # production behavior, not a bug). For THIS controlled determinism
    # comparison, the seed is set explicitly here, in test code, so Path A
    # and Path B start from bit-identical initial weights -- see the
    # report's Objective B section for the full account.
    version = svc._resolve_real_core_model_version(cmv_id)
    torch.manual_seed(int(version.get("initialization_seed") or 42))
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label=configuration_label)
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    return job_id


def create_job(
    tmp_dir: str, name_suffix: str, admin_id: str, cmv_id: str, dataset_id: str,
    tp_id: str, rg_id: str, configuration_label: str,
) -> None:
    svc = _service(tmp_dir)
    job_id = _create_job_impl(svc, name_suffix, admin_id, cmv_id, dataset_id, tp_id, rg_id, configuration_label)
    print(json.dumps({"job_id": job_id}))


def _run_train_continuous(svc, job_id: str, admin_id: str, steps: int, checkpoint_at: str, *, extra: dict | None = None) -> None:
    import time

    checkpoint_steps = {int(s) for s in checkpoint_at.split(",") if s}

    step_seconds: list[float] = []
    losses: list[float] = []
    rss_samples: list[int] = []
    checkpoint_seconds: list[float] = []
    errors: list[str] = []

    for i in range(1, steps + 1):
        try:
            t0 = time.perf_counter()
            metric = svc.run_stream_metric_stage(job_id, step=i, epoch=0, admin_id=admin_id)
            step_seconds.append(time.perf_counter() - t0)
            losses.append(metric["training_state"]["last_loss"])
            rss_samples.append(_rss_kib())
            if i in checkpoint_steps:
                t0 = time.perf_counter()
                svc.run_save_checkpoint_stage(job_id, step=i, epoch=0, admin_id=admin_id)
                checkpoint_seconds.append(time.perf_counter() - t0)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"step={i}: {type(exc).__name__}: {exc}")
            break

    from backend.services.training_adapter_registry import REGISTRY
    adapter = REGISTRY.get(job_id)
    final_model_sha256 = _params_sha256(adapter._model) if adapter is not None else None

    checkpoints = svc.list_checkpoints(job_id)["items"]
    metrics = svc.list_metrics(job_id, limit=100, offset=0)["items"]

    result = {
        "steps_attempted": steps, "steps_completed": len(step_seconds),
        "step_seconds": step_seconds, "losses": losses, "rss_kib_samples": rss_samples,
        "checkpoint_seconds": checkpoint_seconds, "errors": errors,
        "checkpoint_row_count": len(checkpoints), "metric_row_count": len(metrics),
        "final_rss_kib": _rss_kib(), "final_model_sha256": final_model_sha256,
    }
    if extra:
        result.update(extra)
    print(json.dumps(result))


def train_continuous(
    tmp_dir: str, job_id: str, admin_id: str, num_steps: str, checkpoint_at: str,
) -> None:
    """Trains steps 1..num_steps in ONE unbroken process (no pause/resume
    anywhere) -- Path A of the determinism comparison, and also reused
    for the extended-stability run (Objective C) with a larger num_steps
    and denser checkpoint_at. Requires a job already trained at least one
    step in THIS process (or `create_and_train_continuous` for a fresh
    job)."""

    svc = _service(tmp_dir)
    _run_train_continuous(svc, job_id, admin_id, int(num_steps), checkpoint_at)


def train_to_and_pause(tmp_dir: str, job_id: str, admin_id: str, checkpoint_step: str) -> None:
    """Path B, first half: trains 1..checkpoint_step, checkpoints, then
    pauses (this same process then exits, simulating a worker
    termination at a checkpoint boundary)."""

    import time

    svc = _service(tmp_dir)
    step = int(checkpoint_step)
    losses = []
    for i in range(1, step + 1):
        t0 = time.perf_counter()
        metric = svc.run_stream_metric_stage(job_id, step=i, epoch=0, admin_id=admin_id)
        losses.append(metric["training_state"]["last_loss"])
    svc.run_save_checkpoint_stage(job_id, step=step, epoch=0, admin_id=admin_id)
    svc.pause(job_id, admin_id=admin_id)
    print(json.dumps({"losses_to_checkpoint": losses, "checkpoint_step": step}))


def create_and_train_continuous(
    tmp_dir: str, name_suffix: str, admin_id: str, cmv_id: str, dataset_id: str,
    tp_id: str, rg_id: str, configuration_label: str, num_steps: str, checkpoint_at: str,
) -> None:
    """Combines `_create_job_impl()` + the `train_continuous()` loop in
    ONE process -- required because a job's very first training step has
    no checkpoint yet to let a later, separate process pick it up."""

    svc = _service(tmp_dir)
    job_id = _create_job_impl(svc, name_suffix, admin_id, cmv_id, dataset_id, tp_id, rg_id, configuration_label)
    _run_train_continuous(svc, job_id, admin_id, int(num_steps), checkpoint_at, extra={"job_id": job_id})


def create_and_train_to_and_pause(
    tmp_dir: str, name_suffix: str, admin_id: str, cmv_id: str, dataset_id: str,
    tp_id: str, rg_id: str, configuration_label: str, checkpoint_step: str,
) -> None:
    svc = _service(tmp_dir)
    job_id = _create_job_impl(svc, name_suffix, admin_id, cmv_id, dataset_id, tp_id, rg_id, configuration_label)
    step = int(checkpoint_step)
    losses = []
    for i in range(1, step + 1):
        metric = svc.run_stream_metric_stage(job_id, step=i, epoch=0, admin_id=admin_id)
        losses.append(metric["training_state"]["last_loss"])
    svc.run_save_checkpoint_stage(job_id, step=step, epoch=0, admin_id=admin_id)

    from backend.services.training_adapter_registry import REGISTRY
    live_fingerprint = _live_state_fingerprint(REGISTRY.get(job_id))

    svc.pause(job_id, admin_id=admin_id)
    print(json.dumps({
        "job_id": job_id, "losses_to_checkpoint": losses, "checkpoint_step": step,
        "live_fingerprint_at_checkpoint": live_fingerprint,
    }))


def fresh_resume_and_continue_to(
    tmp_dir: str, job_id: str, admin_id: str, target_step: str, checkpoint_every: str = "0",
) -> None:
    """Path B, second half -- a genuinely FRESH OS process (empty
    JobAdapterRegistry): resumes from the on-disk checkpoint via the
    normal, real recovery path, then continues training up to
    target_step."""

    import time

    from backend.services.training_adapter_registry import REGISTRY

    svc = _service(tmp_dir)
    registry_empty_before = not REGISTRY.contains(job_id)

    t0 = time.perf_counter()
    resumed = svc.resume(job_id, admin_id=admin_id)
    recovery_seconds = time.perf_counter() - t0

    adapter = REGISTRY.get(job_id)
    completed_steps_after_recovery = adapter._completed_steps

    every = int(checkpoint_every)
    losses = []
    step_seconds = []
    for i in range(completed_steps_after_recovery + 1, int(target_step) + 1):
        t0 = time.perf_counter()
        metric = svc.run_stream_metric_stage(job_id, step=i, epoch=0, admin_id=admin_id)
        step_seconds.append(time.perf_counter() - t0)
        losses.append(metric["training_state"]["last_loss"])
        if every > 0 and i % every == 0:
            svc.run_save_checkpoint_stage(job_id, step=i, epoch=0, admin_id=admin_id)

    final_model_sha256 = _params_sha256(adapter._model)
    result = {
        "registry_empty_before": registry_empty_before, "resume_status": resumed["status"],
        "recovery_seconds": recovery_seconds, "completed_steps_after_recovery": completed_steps_after_recovery,
        "losses_after_resume": losses, "step_seconds_after_resume": step_seconds,
        "final_model_sha256": final_model_sha256,
    }
    print(json.dumps(result))


def _hash_tensor(tensor) -> str:
    return hashlib.sha256(tensor.detach().cpu().numpy().tobytes()).hexdigest()


def _hash_optimizer_state_dict(state_dict: dict) -> str:
    digest = hashlib.sha256()
    state = state_dict.get("state", {})
    for key in sorted(state.keys()):
        entry = state[key]
        for field_name in sorted(entry.keys()):
            value = entry[field_name]
            if hasattr(value, "detach"):
                digest.update(_hash_tensor(value).encode())
            else:
                digest.update(json.dumps(value, sort_keys=True, default=str).encode())
    digest.update(json.dumps(state_dict.get("param_groups", []), sort_keys=True, default=str).encode())
    return digest.hexdigest()


def verify_checkpoint_independently(tmp_dir: str, job_id: str, step: str) -> None:
    """The core Objective A proof: a genuinely FRESH process loads the
    on-disk checkpoint bundle DIRECTLY via `TrainingCheckpointManager`
    -- never through `MiniBrainTrainingEngineService`,
    `_ensure_adapter_for_job()`, `resume()`, or
    `TorchTrainingAdapter.restore_from_checkpoint()` at all -- and
    independently reconstructs the model/optimizer/scheduler exactly as
    `core_model.training.trainer.run_pretraining()` itself does
    (fresh `BrudForCausalLM` + `adamw()` + `build_scheduler()`, then
    `load_state_dict()` from the checkpoint's own saved dicts), then
    computes fingerprints for every piece of state independently,
    never trusting any boolean "restored" flag from the service layer."""

    from pathlib import Path

    from core_model.architecture.model import BrudForCausalLM
    from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
    from core_model.training.optimizer import adamw
    from core_model.training.pretraining_config import PretrainingConfig
    from core_model.training.scheduler import build_scheduler

    svc = _service(tmp_dir)
    settings = _settings(tmp_dir)
    job_data = svc.job(job_id)
    model_config, _ = svc.core_models.model_config_for_version(job_data["core_model_version_public_id"])

    ckpt_root = Path(settings.resolved_pretraining_dir) / "mini_brain_training_jobs" / job_id
    step_int = int(step)
    ckpt_dir = ckpt_root / f"step-{step_int:08d}-epoch-0000"
    manager = TrainingCheckpointManager(ckpt_dir.parent, settings.core_checkpoint_max_bytes)
    verified = manager.verify(ckpt_dir)
    states = manager.load_states(ckpt_dir)

    model = BrudForCausalLM(model_config)
    model.load_state_dict(states["model"])
    model_sha256 = _params_sha256(model)

    pretraining_config = PretrainingConfig(sequence_length=model_config.context_length)
    optimizer = adamw(
        model, lr=pretraining_config.learning_rate, weight_decay=pretraining_config.weight_decay,
        betas=(pretraining_config.beta1, pretraining_config.beta2), eps=pretraining_config.epsilon,
    )
    optimizer.load_state_dict(states["optimizer"])
    optimizer_sha256 = _hash_optimizer_state_dict(optimizer.state_dict())

    scheduler = build_scheduler(
        optimizer, pretraining_config.scheduler,
        total_steps=pretraining_config.total_steps, warmup_steps=pretraining_config.warmup_steps,
    )
    scheduler.load_state_dict(states["scheduler"])
    scheduler_sha256 = hashlib.sha256(
        json.dumps(scheduler.state_dict(), sort_keys=True, default=str).encode()
    ).hexdigest()

    rng_tensor = states["rng"]
    rng_sha256 = hashlib.sha256(rng_tensor.numpy().tobytes()).hexdigest()

    completed_steps = states["trainer_state"].get("completed_steps")

    print(json.dumps({
        "checkpoint_verified": verified,
        "model_sha256": model_sha256, "optimizer_sha256": optimizer_sha256,
        "scheduler_sha256": scheduler_sha256, "rng_sha256": rng_sha256,
        "completed_steps": completed_steps,
        "references": {k: v for k, v in states["references"].items()},
    }))


def _live_state_fingerprint(adapter) -> dict:
    model_sha256 = _params_sha256(adapter._model)
    optimizer_sha256 = _hash_optimizer_state_dict(adapter._optimizer_state) if adapter._optimizer_state else None
    scheduler_sha256 = (
        hashlib.sha256(json.dumps(adapter._scheduler_state, sort_keys=True, default=str).encode()).hexdigest()
        if adapter._scheduler_state else None
    )
    rng_sha256 = hashlib.sha256(adapter._rng_state.numpy().tobytes()).hexdigest() if adapter._rng_state is not None else None
    return {
        "model_sha256": model_sha256, "optimizer_sha256": optimizer_sha256,
        "scheduler_sha256": scheduler_sha256, "rng_sha256": rng_sha256,
        "completed_steps": adapter._completed_steps,
    }


def capture_live_state_fingerprint(tmp_dir: str, job_id: str) -> None:
    """Captures the SAME four fingerprints from the LIVE, in-memory
    adapter state of a job that just trained in THIS process (no
    checkpoint round-trip involved) -- the "what should be there"
    reference the independently-loaded checkpoint (from
    `verify_checkpoint_independently`, run in a SEPARATE process) is
    compared against."""

    from backend.services.training_adapter_registry import REGISTRY

    adapter = REGISTRY.get(job_id)
    if adapter is None:
        print(json.dumps({"error": "no live adapter for this job in this process"}))
        sys.exit(1)

    print(json.dumps(_live_state_fingerprint(adapter)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("mode")
    parser.add_argument("args", nargs="*")
    parser.add_argument("--signal-file", default=None)
    parsed = parser.parse_args()

    dispatch = {
        "build_shared_fixtures": build_shared_fixtures,
        "create_job": create_job,
        "train_continuous": train_continuous,
        "train_to_and_pause": train_to_and_pause,
        "create_and_train_continuous": create_and_train_continuous,
        "create_and_train_to_and_pause": create_and_train_to_and_pause,
        "fresh_resume_and_continue_to": fresh_resume_and_continue_to,
        "verify_checkpoint_independently": verify_checkpoint_independently,
        "capture_live_state_fingerprint": capture_live_state_fingerprint,
        "worker_step": lambda *a: worker_step(*a, parsed.signal_file),
        "worker_checkpoint": lambda *a: worker_checkpoint(*a, parsed.signal_file),
        "worker_pause": lambda *a: worker_pause(*a, parsed.signal_file),
        "worker_resume": lambda *a: worker_resume(*a, parsed.signal_file),
        "worker_finalize": lambda *a: worker_finalize(*a, parsed.signal_file),
        "worker_cancel": lambda *a: worker_cancel(*a, parsed.signal_file),
    }
    if parsed.mode not in dispatch:
        raise SystemExit(f"unknown mode: {parsed.mode}")
    dispatch[parsed.mode](*parsed.args)
