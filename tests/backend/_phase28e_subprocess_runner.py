"""Phase 2.8E: genuinely separate OS processes proving cross-request
training runtime persistence works even across a real process
boundary, exercising the NEW, non-test-overridden registry/recovery
path (`MiniBrainTrainingEngineService._ensure_adapter_for_job()`) --
never a test-injected adapter override, so this is the closest
in-repo proxy to what the real HTTP deployment's own
`adapter_for_execution_mode()` construction actually does.

Two invocations, mirroring `_phase28c_subprocess_runner.py`'s own
proven pattern:

- `train_checkpoint_pause`: builds a real, isolated MB-22 job entirely
  through the SERVICE layer with NO adapter override (so every stage --
  reserve_runtime, start_training, stream_metric, save_checkpoint,
  pause -- goes through the new registry-backed path even within this
  one process), then exits normally.

- `resume_and_continue`: constructs a brand-new
  `MiniBrainTrainingEngineService` (again, no override) in a fresh
  process that has never seen the first process's Python objects, and
  proves the full recovery + continued-training + new-checkpoint cycle.
"""

from __future__ import annotations

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


def train_checkpoint_pause(tmp_dir: str, name_suffix: str) -> None:
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
    from backend.services.training_adapter_registry import REGISTRY

    app = create_app(settings)
    admin_id = mod_svc._create_admin(app, username=f"admin-{name_suffix}")
    tokenizer_id = mod_h._real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = mod_adapter._real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )
    texts = mod_h._generate_corpus(60, seed_offset=hash(name_suffix) % 1000)
    dataset_id, _, _ = mod_h._build_real_dataset_via_service(settings, name_suffix=name_suffix, record_texts=texts)
    tp_id, rg_id = asyncio.run(mod_svc._seed_approved_package_and_release(app, admin_id, topic=name_suffix))

    # No `adapters=` override -- exercises the real, non-test-overridden
    # `adapter_for_execution_mode()` + registry path throughout.
    svc = MiniBrainTrainingEngineService(settings)
    job = svc.create_job(
        topic=f"{name_suffix}-job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8e subprocess", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION")
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.pause(job_id, admin_id=admin_id)

    live_adapter = REGISTRY.get(job_id)
    info = {
        "job_id": job_id, "dataset_id": dataset_id, "tokenizer_id": tokenizer_id, "cmv_id": cmv_id,
        "database_path": str(settings.resolved_database_path),
        "pretraining_dir": str(settings.resolved_pretraining_dir),
        "completed_steps": live_adapter._completed_steps,
        "model_weights_sha256": _params_sha256(live_adapter._model),
        "registry_had_live_adapter_at_end": REGISTRY.contains(job_id),
    }
    print(json.dumps(info), flush=True)


def resume_and_continue(tmp_dir: str, job_id: str, expect_success: str) -> None:
    from pathlib import Path

    settings = _settings(tmp_dir)

    from backend.database.connection import database_connection
    from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
    from backend.services.training_adapter_registry import REGISTRY

    # A genuinely fresh process: this registry has NEVER held an entry
    # for this job (a brand-new Python process, brand-new module-level
    # singleton).
    result: dict = {"registry_empty_before_recovery": not REGISTRY.contains(job_id)}

    svc = MiniBrainTrainingEngineService(settings)  # no override

    try:
        t0 = time.perf_counter()
        resumed = svc.resume(job_id, admin_id="recovery-admin")
        result["recovery_seconds"] = time.perf_counter() - t0
        result["resume_status"] = resumed["status"]
        result["recovery_succeeded"] = True
    except Exception as exc:  # noqa: BLE001 -- deliberately captured for negative-path tests
        result["recovery_succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
        print(json.dumps(result), flush=True)
        return

    if expect_success != "true":
        result["unexpected_success"] = True
        print(json.dumps(result), flush=True)
        return

    adapter = REGISTRY.get(job_id)
    result["model_restored"] = adapter is not None and adapter._model is not None
    result["completed_steps_after_recovery"] = adapter._completed_steps
    result["optimizer_state_restored"] = adapter._optimizer_state is not None
    result["restored_model_weights_sha256"] = _params_sha256(adapter._model)

    weights_before_step = [p.clone() for p in adapter._model.parameters()]
    metric = svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id="recovery-admin")
    weights_after_step = list(adapter._model.parameters())
    result["resumed_step_loss"] = metric["training_state"]["last_loss"]
    result["weights_changed_after_resumed_step"] = any(
        not b.equal(a) for b, a in zip(weights_before_step, weights_after_step, strict=True)
    )

    svc.run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id="recovery-admin")
    checkpoints = svc.list_checkpoints(job_id)["items"]
    result["checkpoint_count_after_recovery"] = len(checkpoints)
    new_checkpoint_dir = Path(adapter._checkpoints_saved[-1]["canonical_checkpoint_directory"])

    from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

    manager = TrainingCheckpointManager(new_checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
    result["new_checkpoint_verified"] = manager.verify(new_checkpoint_dir)
    references = manager.load_states(new_checkpoint_dir)["references"]
    result["new_checkpoint_dataset_id"] = references.get("dataset_version_public_id")
    result["new_checkpoint_core_model_id"] = references.get("core_model_version_public_id")

    finalize_result = svc.finalize(job_id, admin_id="recovery-admin")
    result["finalize_status"] = finalize_result["status"]
    result["registry_evicted_after_finalize"] = not REGISTRY.contains(job_id)

    with database_connection(settings.resolved_database_path) as connection:
        job_row = connection.execute(
            "SELECT COUNT(*) FROM mini_brain_training_jobs WHERE public_id=?", (job_id,)
        ).fetchone()[0]
    result["job_row_count"] = job_row
    result["peak_rss_kib_final"] = _rss_kib()

    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "train_checkpoint_pause":
        train_checkpoint_pause(sys.argv[2], sys.argv[3])
    elif mode == "resume_and_continue":
        resume_and_continue(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(f"unknown mode: {mode}")
