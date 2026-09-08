"""Phase 2.8B: a genuinely separate OS process that drives a real,
isolated MB-22 training job up to a controlled point, then either exits
normally (mode=normal_checkpoint) or terminates abruptly via os._exit()
without any Python cleanup handler running (mode=crash_before_checkpoint,
mode=crash_during_checkpoint_save) -- simulating a real process kill at
an exact, reproducible boundary rather than racing a real OS signal
against wall-clock timing.

Prints one JSON line to stdout right before any crash/exit point so the
parent test process (a genuinely different OS process) knows exactly
what state to inspect afterward. Not a pytest test module itself --
invoked as a standalone script by tests/backend/test_phase28b_training_
execution_recovery_integrity.py via `subprocess.run([sys.executable,
__file__, ...])`.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "backend"))


def main() -> None:
    mode = sys.argv[1]
    tmp_dir = sys.argv[2]
    name_suffix = sys.argv[3]

    from pathlib import Path

    from backend.core.config import Settings
    from backend.database.migrations import initialize_database

    tmp = Path(tmp_dir)
    settings = Settings(
        database_path=tmp / "api.db", database_backup_dir=tmp / "backups", allowed_data_dir=tmp,
        document_dir=tmp / "documents", document_report_dir=tmp / "documents" / "reports",
        pretraining_dir=tmp / "core_models" / "pretraining", tokenizer_corpus_dir=tmp / "tc",
        tokenizer_dir=tmp / "tok", allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)

    import importlib
    mod_h = importlib.import_module("test_phase27h_training_dataset_readiness")
    mod_adapter = importlib.import_module("test_torch_training_adapter_integration")
    mod_svc = importlib.import_module("test_mini_brain_training_engine_service")

    from backend.main import create_app
    app = create_app(settings)
    admin_id = mod_svc._create_admin(app)

    tokenizer_id = mod_h._real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = mod_adapter._real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )
    texts = mod_h._generate_corpus(60, seed_offset=hash(name_suffix) % 1000)
    dataset_id, _, _ = mod_h._build_real_dataset_via_service(
        settings, name_suffix=name_suffix, record_texts=texts,
    )

    tp_id, rg_id = asyncio.run(mod_svc._seed_approved_package_and_release(app, admin_id, topic=name_suffix))

    from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
    from backend.services.training_runtime_adapter import TorchTrainingAdapter

    adapter = TorchTrainingAdapter()
    svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
    job = svc.create_job(
        topic=f"{name_suffix}-job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8b subprocess", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION")
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)

    info = {
        "job_id": job_id, "dataset_id": dataset_id, "tokenizer_id": tokenizer_id, "cmv_id": cmv_id,
        "database_path": str(settings.resolved_database_path),
        "pretraining_dir": str(settings.resolved_pretraining_dir),
    }

    if mode == "crash_before_checkpoint":
        print(json.dumps(info), flush=True)
        os._exit(137)  # abrupt termination -- no Python cleanup handler runs

    if mode == "crash_during_checkpoint_save":
        def _crash_instead_of_move(*_args, **_kwargs):
            print(json.dumps(info), flush=True)
            os._exit(137)

        import core_model.checkpoints.training_checkpoint as checkpoint_module
        checkpoint_module.shutil.move = _crash_instead_of_move
        # This call never returns -- the patched move() exits the process
        # at the exact moment the real checkpoint's temp files are fully
        # written but before the atomic rename to the canonical path.
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        return  # unreachable

    # mode == "normal_checkpoint"
    svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    checkpoint_row = svc.list_checkpoints(job_id)["items"][0]
    info["checkpoint_dir"] = str(Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"]))
    info["checkpoint_public_id"] = checkpoint_row["public_id"]
    print(json.dumps(info), flush=True)


if __name__ == "__main__":
    main()
