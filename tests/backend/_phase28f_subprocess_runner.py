"""Phase 2.8F: genuinely independent OS-process workers for multi-worker
concurrency testing. No shared Python objects, no shared adapter, no
shared registry, no inherited adapter state across any two invocations
of this script -- each `python _phase28f_subprocess_runner.py <mode> ...`
call is a brand-new process with its own module-level
`training_adapter_registry.REGISTRY` singleton.

Modes:

- `setup`: builds a real, isolated MB-22 job (real dataset/tokenizer/
  Core Model Version) and drives it through reserve_runtime ->
  start_training in ONE process (not a race -- this establishes the
  common starting point every worker-pair test then races from).
  Prints job/dataset/tokenizer/cmv identity and the database/pretraining
  paths as JSON.

- `worker_step` / `worker_checkpoint` / `worker_pause` / `worker_resume`
  / `worker_cancel` / `worker_finalize` / `worker_archive`: each
  performs exactly one real MB-22 operation against an EXISTING job
  (built by `setup`), in a fresh process with a fresh, non-overridden
  `MiniBrainTrainingEngineService`. Accepts `--signal-file PATH` to
  synchronize start time against a sibling worker (each worker busy-
  waits for the file to appear, giving the parent test precise control
  over "genuinely simultaneous" without any shared IPC state beyond a
  plain filesystem flag file).

- `kill_mid_checkpoint_save`: monkeypatches `shutil.move` to call
  `os._exit(137)` immediately before the atomic checkpoint move,
  deterministically reproducing "process dies during checkpoint save"
  without a wall-clock signal race.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "backend"))


def _settings(tmp_dir: str):
    from pathlib import Path

    from backend.core.config import Settings

    tmp = Path(tmp_dir)
    return Settings(
        database_path=tmp / "api.db", database_backup_dir=tmp / "backups", allowed_data_dir=tmp,
        document_dir=tmp / "documents", document_report_dir=tmp / "documents" / "reports",
        pretraining_dir=tmp / "core_models" / "pretraining", tokenizer_corpus_dir=tmp / "tc",
        tokenizer_dir=tmp / "tok", allow_external_storage=True, log_level="CRITICAL",
    )


def _rss_kib() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _params_sha256(model) -> str:
    import hashlib

    digest = hashlib.sha256()
    for param in model.parameters():
        digest.update(param.detach().numpy().tobytes())
    return digest.hexdigest()


def _wait_for_signal(signal_file: str | None) -> None:
    if not signal_file:
        return
    deadline = time.monotonic() + 30
    while not os.path.exists(signal_file):
        if time.monotonic() > deadline:
            raise TimeoutError(f"signal file never appeared: {signal_file}")
        time.sleep(0.005)


def setup(
    tmp_dir: str, name_suffix: str, record_count: str = "60", with_checkpoint: str = "false",
    hidden_size: str = "16", intermediate_size: str = "32",
) -> None:
    from backend.database.migrations import initialize_database

    settings = _settings(tmp_dir)
    initialize_database(settings.resolved_database_path)

    import importlib
    mod_h = importlib.import_module("test_phase27h_training_dataset_readiness")
    mod_adapter = importlib.import_module("test_torch_training_adapter_integration")
    mod_svc = importlib.import_module("test_mini_brain_training_engine_service")

    import asyncio

    from backend.main import create_app
    from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService

    app = create_app(settings)
    admin_id = mod_svc._create_admin(app, username=f"admin-{name_suffix}")
    tokenizer_id = mod_h._real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = mod_adapter._real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
        hidden_size=int(hidden_size), intermediate_size=int(intermediate_size),
    )
    texts = mod_h._generate_corpus(int(record_count), seed_offset=hash(name_suffix) % 1000)
    dataset_id, _, _ = mod_h._build_real_dataset_via_service(settings, name_suffix=name_suffix, record_texts=texts)
    tp_id, rg_id = asyncio.run(mod_svc._seed_approved_package_and_release(app, admin_id, topic=name_suffix))

    svc = MiniBrainTrainingEngineService(settings)  # no override
    job = svc.create_job(
        topic=f"{name_suffix}-job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8f subprocess", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION")
    svc.run_start_training_stage(job_id, admin_id=admin_id)

    completed_steps_at_checkpoint = None
    if with_checkpoint == "true":
        svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        completed_steps_at_checkpoint = 1

    print(json.dumps({
        "job_id": job_id, "admin_id": admin_id, "dataset_id": dataset_id,
        "tokenizer_id": tokenizer_id, "cmv_id": cmv_id,
        "completed_steps_at_checkpoint": completed_steps_at_checkpoint,
        "database_path": str(settings.resolved_database_path),
        "pretraining_dir": str(settings.resolved_pretraining_dir),
    }), flush=True)


def _service(tmp_dir: str):
    from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService

    return MiniBrainTrainingEngineService(_settings(tmp_dir))


def worker_step(tmp_dir: str, job_id: str, step: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    started = time.perf_counter()
    result: dict = {"worker": "step", "step": int(step), "pid": os.getpid()}
    try:
        outcome = svc.run_stream_metric_stage(job_id, step=int(step), epoch=0, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
        result["training_state"] = outcome["training_state"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    result["elapsed_seconds"] = time.perf_counter() - started
    print(json.dumps(result), flush=True)


def worker_checkpoint(tmp_dir: str, job_id: str, step: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    started = time.perf_counter()
    result: dict = {"worker": "checkpoint", "step": int(step), "pid": os.getpid()}
    try:
        outcome = svc.run_save_checkpoint_stage(job_id, step=int(step), epoch=0, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    result["elapsed_seconds"] = time.perf_counter() - started
    print(json.dumps(result), flush=True)


def worker_pause(tmp_dir: str, job_id: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    started = time.perf_counter()
    result: dict = {"worker": "pause", "pid": os.getpid()}
    try:
        outcome = svc.pause(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    result["elapsed_seconds"] = time.perf_counter() - started
    print(json.dumps(result), flush=True)


def worker_resume(tmp_dir: str, job_id: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    started = time.perf_counter()
    result: dict = {"worker": "resume", "pid": os.getpid()}
    try:
        outcome = svc.resume(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    result["elapsed_seconds"] = time.perf_counter() - started
    print(json.dumps(result), flush=True)


def worker_cancel(tmp_dir: str, job_id: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    started = time.perf_counter()
    result: dict = {"worker": "cancel", "pid": os.getpid()}
    try:
        outcome = svc.cancel(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    result["elapsed_seconds"] = time.perf_counter() - started
    print(json.dumps(result), flush=True)


def worker_finalize(tmp_dir: str, job_id: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    started = time.perf_counter()
    result: dict = {"worker": "finalize", "pid": os.getpid()}
    try:
        outcome = svc.finalize(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    result["elapsed_seconds"] = time.perf_counter() - started
    print(json.dumps(result), flush=True)


def worker_archive(tmp_dir: str, job_id: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    started = time.perf_counter()
    result: dict = {"worker": "archive", "pid": os.getpid()}
    try:
        outcome = svc.archive(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    result["elapsed_seconds"] = time.perf_counter() - started
    print(json.dumps(result), flush=True)


def kill_mid_checkpoint_save(tmp_dir: str, job_id: str, step: str, admin_id: str) -> None:
    """Deterministically terminates this process (`os._exit(137)`,
    bypassing Python cleanup, exactly like the Phase 2.8B/2.8C
    precedent) immediately before the atomic `shutil.move()` that
    publishes a checkpoint -- proves the atomic-save boundary under a
    genuinely separate worker process, not a same-process monkeypatch a
    parent test could accidentally share state with."""

    import shutil

    original_move = shutil.move

    def _move_then_die(src, dst, *a, **kw):
        # The temp directory is fully built (all 9 real files written)
        # at this point -- only the atomic publish step remains.
        os._exit(137)

    shutil.move = _move_then_die
    svc = _service(tmp_dir)
    try:
        svc.run_save_checkpoint_stage(job_id, step=int(step), epoch=0, admin_id=admin_id)
    finally:
        shutil.move = original_move  # unreachable if os._exit fired, kept for clarity


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode")
    parser.add_argument("args", nargs="*")
    parser.add_argument("--signal-file", default=None)
    parsed = parser.parse_args()

    mode = parsed.mode
    a = parsed.args
    sf = parsed.signal_file

    if mode == "setup":
        setup(*a)
    elif mode == "worker_step":
        worker_step(a[0], a[1], a[2], a[3], sf)
    elif mode == "worker_checkpoint":
        worker_checkpoint(a[0], a[1], a[2], a[3], sf)
    elif mode == "worker_pause":
        worker_pause(a[0], a[1], a[2], sf)
    elif mode == "worker_resume":
        worker_resume(a[0], a[1], a[2], sf)
    elif mode == "worker_cancel":
        worker_cancel(a[0], a[1], a[2], sf)
    elif mode == "worker_finalize":
        worker_finalize(a[0], a[1], a[2], sf)
    elif mode == "worker_archive":
        worker_archive(a[0], a[1], a[2], sf)
    elif mode == "kill_mid_checkpoint_save":
        kill_mid_checkpoint_save(a[0], a[1], a[2], a[3])
    else:
        raise SystemExit(f"unknown mode: {mode}")
