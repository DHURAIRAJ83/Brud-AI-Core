"""Phase 2.8D: genuinely separate OS processes for real dataset-scale
measurement, real training qualification, and real fresh-process
checkpoint recovery at larger scale. Not a pytest module itself --
invoked as a standalone script by
tests/backend/test_phase28d_training_scale_qualification.py, and also
used directly for this phase's own ad-hoc scale-ladder measurement.

Modes:

- `scale_run`: builds a real governed Dataset Version (via
  `DatasetVersioningService.create_build()` -> `validate_build()` ->
  `run_build()`, never a direct `dataset_version_items` insert), a real
  tokenizer, and a real Core Model Version at the requested record
  count; runs the real dataset readiness contract and the real training
  readiness contract; if READY, drives a full real MB-22 job
  (create_job -> ... -> finalize) with one real training step and one
  real checkpoint save. Every timing/RSS/size number reported is
  measured in this one isolated process, not estimated.

- `recover_at_scale`: the Phase 2.8C fresh-process recovery proof,
  reused verbatim at a larger, explicitly-scaled dataset. Two
  invocations (`train_checkpoint_pause` / `recover_and_continue`) mirror
  `_phase28c_subprocess_runner.py` exactly.
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


def _dir_size_bytes(path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _params_sha256(model) -> str:
    import hashlib

    digest = hashlib.sha256()
    for param in model.parameters():
        digest.update(param.detach().numpy().tobytes())
    return digest.hexdigest()


def determinism_run(tmp_dir: str, record_count: str, name_suffix: str) -> None:
    """Builds the exact same generated corpus into two separately named
    Dataset Versions (same tokenizer, same Core Model Version) and
    compares the real pipeline output byte-for-byte -- proves the
    pipeline is deterministic at this scale, not that two dataset rows
    happen to share a public id."""

    record_count = int(record_count)
    from backend.database.migrations import initialize_database

    settings = _settings(tmp_dir)
    initialize_database(settings.resolved_database_path)

    import importlib
    mod_h = importlib.import_module("test_phase27h_training_dataset_readiness")
    mod_adapter = importlib.import_module("test_torch_training_adapter_integration")
    mod_svc = importlib.import_module("test_mini_brain_training_engine_service")

    from backend.main import create_app
    app = create_app(settings)
    admin_id = mod_svc._create_admin(app, username=f"admin-{name_suffix}")
    tokenizer_id = mod_h._real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = mod_adapter._real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )

    texts = mod_h._generate_corpus(record_count, seed_offset=record_count * 7)

    from backend.services.mini_brain_dataset_pipeline_service import MiniBrainDatasetPipelineService

    pipeline = MiniBrainDatasetPipelineService(settings)
    results = []
    for suffix in ("a", "b"):
        dataset_id, _preview, _build_result = mod_h._build_real_dataset_via_service(
            settings, name_suffix=f"{name_suffix}-{suffix}", record_texts=texts,
        )
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        blocks = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        results.append({
            "dataset_checksum_sha256": contract["dataset"]["checksum_sha256"],
            "tokenizer_checksum_sha256": contract["tokenizer"]["checksum_sha256"],
            "block_builder_version": contract["reproducibility"]["block_builder_version"],
            "train_blocks": blocks["train_blocks"],
            "validation_blocks": blocks["validation_blocks"],
        })

    a, b = results
    out = {
        "record_count": record_count,
        "dataset_checksum_identical": a["dataset_checksum_sha256"] == b["dataset_checksum_sha256"],
        "tokenizer_checksum_identical": a["tokenizer_checksum_sha256"] == b["tokenizer_checksum_sha256"],
        "block_builder_version_identical": a["block_builder_version"] == b["block_builder_version"],
        "train_blocks_identical": a["train_blocks"] == b["train_blocks"],
        "validation_blocks_identical": a["validation_blocks"] == b["validation_blocks"],
        "train_block_count": len(a["train_blocks"]),
        "validation_block_count": len(a["validation_blocks"]),
    }
    print(json.dumps(out), flush=True)


def scale_run(tmp_dir: str, record_count: str, name_suffix: str) -> None:
    record_count = int(record_count)
    import asyncio

    from backend.database.migrations import initialize_database

    settings = _settings(tmp_dir)
    initialize_database(settings.resolved_database_path)

    import importlib
    mod_h = importlib.import_module("test_phase27h_training_dataset_readiness")
    mod_adapter = importlib.import_module("test_torch_training_adapter_integration")
    mod_svc = importlib.import_module("test_mini_brain_training_engine_service")

    from backend.main import create_app
    app = create_app(settings)
    admin_id = mod_svc._create_admin(app, username=f"admin-{name_suffix}")

    result: dict = {"record_count": record_count, "name_suffix": name_suffix}

    # -- real tokenizer (fixed small corpus -- record count under test
    # is the DATASET scale, not the tokenizer's own training corpus) --
    t0 = time.perf_counter()
    tokenizer_id = mod_h._real_tokenizer(settings, name_suffix=name_suffix)
    result["tokenizer_build_seconds"] = time.perf_counter() - t0

    # -- real Core Model Version (tiny, matches the established
    # TEST_INTEGRATION_CONFIGURATION shape used since Phase 2.7E) --
    t0 = time.perf_counter()
    cmv_id = mod_adapter._real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )
    result["core_model_version_build_seconds"] = time.perf_counter() - t0

    # -- real, governed dataset build at the requested scale --
    texts = mod_h._generate_corpus(record_count, seed_offset=record_count * 7)
    t0 = time.perf_counter()
    dataset_id, _preview, build_result = mod_h._build_real_dataset_via_service(
        settings, name_suffix=name_suffix, record_texts=texts,
    )
    result["dataset_build_seconds"] = time.perf_counter() - t0
    result["dataset_id"] = dataset_id

    from backend.services.mini_brain_dataset_pipeline_service import MiniBrainDatasetPipelineService
    from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService

    pipeline = MiniBrainDatasetPipelineService(settings)
    t0 = time.perf_counter()
    dataset_contract = pipeline.readiness_contract(
        dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
    )
    result["dataset_readiness_contract_seconds"] = time.perf_counter() - t0
    result["dataset_readiness_status"] = dataset_contract["status"]
    if dataset_contract["status"] == "READY":
        result["dataset_checksum_sha256"] = dataset_contract["dataset"]["checksum_sha256"]
        result["tokenizer_checksum_sha256"] = dataset_contract["tokenizer"]["checksum_sha256"]
        result["train_block_count"] = dataset_contract["blocks"]["train_block_count"]
        result["validation_block_count"] = dataset_contract["blocks"]["validation_block_count"]
        result["train_usable_tokens"] = dataset_contract["blocks"]["train_usable_tokens"]
        result["validation_usable_tokens"] = dataset_contract["blocks"]["validation_usable_tokens"]
        result["block_builder_version"] = dataset_contract["reproducibility"]["block_builder_version"]
    else:
        result["dataset_readiness_reason"] = dataset_contract["reason"]

    svc = MiniBrainTrainingEngineService(settings)
    t0 = time.perf_counter()
    training_contract = svc.training_readiness_contract(
        dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id, execution_mode="gpu",
    )
    result["training_readiness_contract_seconds"] = time.perf_counter() - t0
    result["training_readiness_status"] = training_contract["status"]
    result["training_readiness_reason"] = training_contract.get("reason")
    if training_contract["status"] == "NOT_READY" and training_contract.get("resource_estimate"):
        result["resource_estimate"] = training_contract["resource_estimate"]

    result["disk_usage_bytes_after_dataset_and_readiness"] = _dir_size_bytes(tmp_dir)
    result["peak_rss_kib_after_dataset_and_readiness"] = _rss_kib()

    # The only NOT_READY reason this script ever proceeds past is the
    # advisory evidence-ceiling one (`envelope_classification ==
    # "insufficient_evidence"` caused specifically by `record_count >
    # LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT`) -- this phase's own
    # job is to go establish that evidence directly. Every OTHER
    # NOT_READY/BLOCKED reason (a real resource-envelope excess, a
    # genuine dataset/tokenizer/config problem) is never bypassed: the
    # underlying real memory gate in `TorchTrainingAdapter.reserve()`
    # still applies independently below regardless of this decision.
    evidence_ceiling_only = (
        training_contract["status"] == "NOT_READY"
        and training_contract.get("resource_estimate", {}).get("envelope_classification") == "insufficient_evidence"
        and training_contract["resource_estimate"]["requested_record_count"]
        > training_contract["resource_estimate"]["largest_validated_record_count"]
    )
    result["bypassed_advisory_readiness_gate_for_evidence_gathering"] = evidence_ceiling_only

    if training_contract["status"] != "READY" and not evidence_ceiling_only:
        result["training_qualification_attempted"] = False
        print(json.dumps(result), flush=True)
        return

    # -- real MB-22 training qualification --
    result["training_qualification_attempted"] = True
    tp_id, rg_id = asyncio.run(mod_svc._seed_approved_package_and_release(app, admin_id, topic=name_suffix))

    from backend.services.training_runtime_adapter import TorchTrainingAdapter

    adapter = TorchTrainingAdapter()
    train_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
    job = train_svc.create_job(
        topic=f"{name_suffix}-job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
    )
    job_id = job["public_id"]
    train_svc.run_validate_release_stage(job_id, admin_id=admin_id)
    train_svc.run_validate_package_stage(job_id, admin_id=admin_id)
    train_svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8d scale qualification", admin_id=admin_id)
    train_svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    train_svc.run_build_manifest_stage(job_id, admin_id=admin_id)

    t0 = time.perf_counter()
    train_svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label=f"TEST_SCALE_{record_count}")
    result["reserve_runtime_seconds"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    train_svc.run_start_training_stage(job_id, admin_id=admin_id)
    result["start_training_seconds"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    train_svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    result["first_training_step_seconds"] = time.perf_counter() - t0
    job_state = train_svc.job(job_id)
    result["first_step_loss"] = job_state["training_state"].get("last_loss")

    t0 = time.perf_counter()
    checkpoint = train_svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    result["checkpoint_save_seconds"] = time.perf_counter() - t0
    result["checkpoint_public_id"] = checkpoint["public_id"] if isinstance(checkpoint, dict) else None

    checkpoints = train_svc.list_checkpoints(job_id)["items"]
    checkpoint_row = checkpoints[-1]
    canonical_dir = adapter._checkpoints_saved[-1]["canonical_checkpoint_directory"]
    from pathlib import Path as _Path
    result["checkpoint_size_bytes"] = _dir_size_bytes(canonical_dir)
    result["checkpoint_file_count"] = len(list(_Path(canonical_dir).iterdir()))
    result["model_weights_sha256"] = _params_sha256(adapter._model)
    result["job_id"] = job_id
    result["database_path"] = str(settings.resolved_database_path)
    result["pretraining_dir"] = str(settings.resolved_pretraining_dir)

    from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

    t0 = time.perf_counter()
    manager = TrainingCheckpointManager(_Path(canonical_dir).parent, settings.core_checkpoint_max_bytes)
    result["checkpoint_verify_ok"] = manager.verify(_Path(canonical_dir))
    result["checkpoint_verify_seconds"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    manager.load_states(_Path(canonical_dir))
    result["checkpoint_load_states_seconds"] = time.perf_counter() - t0

    train_svc.pause(job_id, admin_id=admin_id)

    result["peak_rss_kib_final"] = _rss_kib()
    result["disk_usage_bytes_final"] = _dir_size_bytes(tmp_dir)

    print(json.dumps(result), flush=True)


def train_checkpoint_pause_at_scale(tmp_dir: str, record_count: str, name_suffix: str) -> None:
    """Phase 2.8C's own `train_checkpoint_pause`, reused verbatim at an
    explicitly larger, caller-chosen dataset scale, for the fresh-process
    recovery proof."""

    record_count = int(record_count)
    import asyncio

    from backend.database.migrations import initialize_database

    settings = _settings(tmp_dir)
    initialize_database(settings.resolved_database_path)

    import importlib
    mod_h = importlib.import_module("test_phase27h_training_dataset_readiness")
    mod_adapter = importlib.import_module("test_torch_training_adapter_integration")
    mod_svc = importlib.import_module("test_mini_brain_training_engine_service")

    from backend.main import create_app
    app = create_app(settings)
    admin_id = mod_svc._create_admin(app, username=f"admin-{name_suffix}")

    tokenizer_id = mod_h._real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = mod_adapter._real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )
    texts = mod_h._generate_corpus(record_count, seed_offset=record_count * 11)
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
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8d recovery at scale", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label=f"TEST_SCALE_{record_count}")
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.pause(job_id, admin_id=admin_id)

    info = {
        "record_count": record_count, "job_id": job_id, "dataset_id": dataset_id,
        "tokenizer_id": tokenizer_id, "cmv_id": cmv_id,
        "database_path": str(settings.resolved_database_path),
        "pretraining_dir": str(settings.resolved_pretraining_dir),
        "completed_steps": adapter._completed_steps,
        "model_weights_sha256": _params_sha256(adapter._model),
    }
    print(json.dumps(info), flush=True)


def recover_and_continue_at_scale(tmp_dir: str, job_id: str, expect_success: str) -> None:
    """Phase 2.8C's own `recover_and_continue`, reused verbatim."""

    from pathlib import Path

    settings = _settings(tmp_dir)

    from backend.database.connection import database_connection
    from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
    from backend.services.training_runtime_adapter import TorchTrainingAdapter

    adapter = TorchTrainingAdapter()
    assert adapter._model is None
    svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})

    result: dict = {"model_was_none_before_recovery": adapter._model is None}
    peak_rss_before = _rss_kib()

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

    result["peak_rss_kib_during_recovery"] = _rss_kib()

    if expect_success != "true":
        result["unexpected_success"] = True
        print(json.dumps(result), flush=True)
        return

    result["model_restored"] = adapter._model is not None
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

    with database_connection(settings.resolved_database_path) as connection:
        job_row = connection.execute(
            "SELECT COUNT(*) FROM mini_brain_training_jobs WHERE public_id=?", (job_id,)
        ).fetchone()[0]
    result["job_row_count"] = job_row
    result["peak_rss_kib_final"] = _rss_kib()

    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "scale_run":
        scale_run(sys.argv[2], sys.argv[3], sys.argv[4])
    elif mode == "determinism_run":
        determinism_run(sys.argv[2], sys.argv[3], sys.argv[4])
    elif mode == "train_checkpoint_pause_at_scale":
        train_checkpoint_pause_at_scale(sys.argv[2], sys.argv[3], sys.argv[4])
    elif mode == "recover_and_continue_at_scale":
        recover_and_continue_at_scale(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(f"unknown mode: {mode}")
