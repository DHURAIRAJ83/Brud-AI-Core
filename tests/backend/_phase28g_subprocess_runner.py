"""Phase 2.8G: real-model training qualification harness.

Distinguishes, throughout:

- **TEST model** (`micro_preset`, hidden_size in the 16-24 range) --
  the deliberately tiny shape every prior 2.7E-2.8F phase used for pure
  execution-safety testing. Never used in this file.

- **REAL model** (`tiny_preset`, `core_model/architecture/config.py`):
  hidden_size=256, num_hidden_layers=6, num_attention_heads=8,
  intermediate_size=768, context_length=512 -- the LARGEST of the two
  named, non-test presets actually defined in the real architecture
  module and consumed by the real `CoreModelService.create_config()`,
  not a shape invented for this phase. No production-scale Core Model
  Version exists anywhere in the governed system today (confirmed via a
  read-only inspection of the production database: 0 rows in
  `core_model_versions`/`core_model_families`/`core_model_configs`), so
  this is the largest model this phase can honestly call "real and
  already governed" rather than "arbitrarily invented."

Every job/dataset/tokenizer/Core-Model-Version built by this script
lives entirely under an isolated `tmp_dir` -- the production database
and production data directories are never opened by this file at all.
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

REAL_TOKENIZER_VOCAB_SIZE = 2000
REAL_TOKENIZER_CORPUS_RECORDS = 3000
REAL_TRAINING_DATASET_RECORDS = 300


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


def _real_tokenizer_large(settings, *, name_suffix: str) -> str:
    """The REAL tokenizer for this phase's qualification -- trained via
    the real `spm.SentencePieceTrainer.train()` on a real, larger
    (3,000-record) corpus, targeting `REAL_TOKENIZER_VOCAB_SIZE=2000`
    (empirically confirmed achievable with this corpus's actual lexical
    diversity -- 6,000 was attempted and silently under-filled,
    "No valid symbol found"; 2,000 trains cleanly). This is a real,
    artifact-backed SentencePiece model on disk, not a placeholder row."""

    import hashlib

    import sentencepiece as spm

    from backend.core.json_utils import dumps_json
    from backend.database.connection import database_connection
    from backend.models.tokenizers import SPECIAL_TOKENS

    import test_phase27h_training_dataset_readiness as mod_h

    corpus_texts = [t for t, _ in mod_h._generate_corpus(REAL_TOKENIZER_CORPUS_RECORDS, seed_offset=7)]
    corpus = settings.resolved_tokenizer_corpus_dir / f"phase28g-corpus-{name_suffix}.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_text("\n".join(corpus_texts) + "\n", encoding="utf-8")
    temp_prefix = settings.resolved_tokenizer_dir / f"phase28g-tokenizer-{name_suffix}"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus), model_prefix=str(temp_prefix), model_type="bpe",
        vocab_size=REAL_TOKENIZER_VOCAB_SIZE, character_coverage=1.0, hard_vocab_limit=False,
        pad_id=0, unk_id=1, bos_id=2, eos_id=3,
        pad_piece="<pad>", unk_piece="<unk>", bos_piece="<bos>", eos_piece="<eos>",
        user_defined_symbols=",".join(SPECIAL_TOKENS[4:]),
    )
    artifact_dir = settings.resolved_tokenizer_dir / "versions" / f"tok28g-family-{name_suffix}" / "v1"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "tokenizer.model"
    vocab_path = artifact_dir / "tokenizer.vocab"
    temp_prefix.with_suffix(".model").replace(model_path)
    temp_prefix.with_suffix(".vocab").replace(vocab_path)
    processor = spm.SentencePieceProcessor(model_file=str(model_path))

    def _sha256(path):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    manifest = {
        "files": ["tokenizer.model", "tokenizer.vocab", "artifact_manifest.json"],
        "model_checksum_sha256": _sha256(model_path),
        "vocabulary_checksum_sha256": _sha256(vocab_path),
        "special_tokens": SPECIAL_TOKENS,
    }
    (artifact_dir / "artifact_manifest.json").write_text(dumps_json(manifest), encoding="utf-8")

    dataset_public_id = f"ds-tokcorpus-28g-{name_suffix}"
    tokenizer_public_id = f"tok28g-{name_suffix}"
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (dataset_public_id, f"tokcorpus-28g-{name_suffix}", "v1", "ready", "f" * 64),
        )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            (f"tf28g-{name_suffix}", f"tok28g-family-{name_suffix}", "T", "active"),
        )
        family_id = connection.execute(
            "SELECT id FROM tokenizer_families WHERE public_id=?", (f"tf28g-{name_suffix}",)
        ).fetchone()[0]
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_public_id,)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
            lifecycle_status,algorithm,vocabulary_size,character_coverage,
            normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
            model_checksum_sha256,vocabulary_checksum_sha256,artifact_manifest_json,
            special_tokens_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tokenizer_public_id, family_id, "v1", "active", "bpe", processor.vocab_size(), 1.0,
                "nmt_nfkc", "sentencepiece", dataset_id, "a" * 64,
                manifest["model_checksum_sha256"], manifest["vocabulary_checksum_sha256"],
                dumps_json(manifest), dumps_json(SPECIAL_TOKENS),
            ),
        )
        connection.commit()
    return tokenizer_public_id, processor.vocab_size()


def _real_core_model_version_tiny_preset(settings, admin_id: str, *, name_suffix: str, tokenizer_version_public_id: str):
    """The REAL model: `preset='tiny'` (`core_model/architecture/config.py`
    `tiny_preset()` -- hidden_size=256, num_hidden_layers=6,
    num_attention_heads=8, intermediate_size=768, context_length=512),
    built through the exact real `CoreModelService` pipeline (family ->
    config -> validate -> version -> initialize -> verify-architecture)
    every prior phase's own real-identity tests already use for the
    tiny MICRO test shape -- only the preset name changes."""

    from backend.models.core_models import CoreConfigCreate, CoreFamilyCreate, CoreVersionCreate
    from backend.services.core_model_service import CoreModelService
    from backend.database.repositories.core_models import CoreModelRepository

    core_models = CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)
    family = core_models.create_family(
        CoreFamilyCreate(name=f"real-28g-{name_suffix}", display_name="Real Brud AI Qualification"),
        admin_id=admin_id,
    )
    config = core_models.create_config(
        CoreConfigCreate(
            name=f"real-28g-config-{name_suffix}", config_version="v1",
            tokenizer_version_public_id=tokenizer_version_public_id, preset="tiny",
        ),
        admin_id=admin_id,
    )
    core_models.validate_config(config["public_id"], admin_id=admin_id)
    version = core_models.create_version(
        CoreVersionCreate(
            family_public_id=family["public_id"], config_public_id=config["public_id"], version="v0.1",
        ),
        admin_id=admin_id,
    )
    core_models.initialize(version["public_id"], admin_id=admin_id)
    core_models.verify_architecture(version["public_id"], admin_id=admin_id)
    return version["public_id"], config["public_id"]


def setup(tmp_dir: str, name_suffix: str, with_checkpoint: str = "false") -> None:
    from backend.database.migrations import initialize_database

    settings = _settings(tmp_dir)
    initialize_database(settings.resolved_database_path)

    import asyncio
    import importlib
    mod_h = importlib.import_module("test_phase27h_training_dataset_readiness")
    mod_svc = importlib.import_module("test_mini_brain_training_engine_service")

    from backend.main import create_app
    app = create_app(settings)
    admin_id = mod_svc._create_admin(app, username=f"admin-{name_suffix}")

    t0 = time.perf_counter()
    tokenizer_id, achieved_vocab_size = _real_tokenizer_large(settings, name_suffix=name_suffix)
    tokenizer_build_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    cmv_id, config_id = _real_core_model_version_tiny_preset(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )
    cmv_build_seconds = time.perf_counter() - t0

    texts = mod_h._generate_corpus(REAL_TRAINING_DATASET_RECORDS, seed_offset=hash(name_suffix) % 1000)
    t0 = time.perf_counter()
    dataset_id, _, _ = mod_h._build_real_dataset_via_service(settings, name_suffix=name_suffix, record_texts=texts)
    dataset_build_seconds = time.perf_counter() - t0

    tp_id, rg_id = asyncio.run(mod_svc._seed_approved_package_and_release(app, admin_id, topic=name_suffix))

    from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
    from core_model.architecture.model import BrudForCausalLM, count_parameters
    from core_model.training.metrics import available_memory_bytes

    rss_after_model_build = _rss_kib()

    svc = MiniBrainTrainingEngineService(settings)

    t0 = time.perf_counter()
    readiness = svc.training_readiness_contract(
        dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id, execution_mode="gpu",
    )
    readiness_seconds = time.perf_counter() - t0

    job = svc.create_job(
        topic=f"{name_suffix}-job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8g real model qualification", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)

    t0 = time.perf_counter()
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_SCALE_REAL_TINY_PRESET")
    reserve_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    start_seconds = time.perf_counter() - t0

    result = {
        "job_id": job_id, "admin_id": admin_id, "dataset_id": dataset_id,
        "tokenizer_id": tokenizer_id, "tokenizer_achieved_vocab_size": achieved_vocab_size,
        "cmv_id": cmv_id, "config_id": config_id,
        "database_path": str(settings.resolved_database_path),
        "pretraining_dir": str(settings.resolved_pretraining_dir),
        "tokenizer_build_seconds": tokenizer_build_seconds,
        "cmv_build_seconds": cmv_build_seconds,
        "dataset_build_seconds": dataset_build_seconds,
        "readiness_status": readiness["status"],
        "readiness_reason": readiness.get("reason"),
        "readiness_seconds": readiness_seconds,
        "readiness_resource_estimate": readiness.get("resource_estimate"),
        "reserve_seconds": reserve_seconds,
        "start_seconds": start_seconds,
        "rss_kib_after_model_build": rss_after_model_build,
        "rss_kib_after_reserve_start": _rss_kib(),
        "available_memory_bytes_at_setup": available_memory_bytes(),
    }

    if with_checkpoint == "true":
        t0 = time.perf_counter()
        metric = svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        result["first_step_seconds"] = time.perf_counter() - t0
        result["first_step_loss"] = metric["training_state"]["last_loss"]
        t0 = time.perf_counter()
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        result["first_checkpoint_seconds"] = time.perf_counter() - t0
        result["rss_kib_after_first_checkpoint"] = _rss_kib()
        svc.pause(job_id, admin_id=admin_id)

    print(json.dumps(result), flush=True)


def _service(tmp_dir: str):
    from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService

    return MiniBrainTrainingEngineService(_settings(tmp_dir))


def _wait_for_signal(signal_file: str | None) -> None:
    if not signal_file:
        return
    deadline = time.monotonic() + 30
    while not os.path.exists(signal_file):
        if time.monotonic() > deadline:
            raise TimeoutError(f"signal file never appeared: {signal_file}")
        time.sleep(0.005)


def resume_and_continue(tmp_dir: str, job_id: str, expect_success: str) -> None:
    from pathlib import Path

    settings = _settings(tmp_dir)
    from backend.database.connection import database_connection
    from backend.services.training_adapter_registry import REGISTRY

    svc = _service(tmp_dir)
    result: dict = {"registry_empty_before_recovery": not REGISTRY.contains(job_id)}
    try:
        t0 = time.perf_counter()
        resumed = svc.resume(job_id, admin_id="recovery-admin")
        result["recovery_seconds"] = time.perf_counter() - t0
        result["resume_status"] = resumed["status"]
        result["recovery_succeeded"] = True
    except Exception as exc:  # noqa: BLE001
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
    result["scheduler_state_restored"] = adapter._scheduler_state is not None
    result["rng_state_restored"] = adapter._rng_state is not None
    result["restored_model_weights_sha256"] = _params_sha256(adapter._model)

    weights_before = [p.clone() for p in adapter._model.parameters()]
    t0 = time.perf_counter()
    metric = svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id="recovery-admin")
    result["resumed_step_seconds"] = time.perf_counter() - t0
    weights_after = list(adapter._model.parameters())
    result["resumed_step_loss"] = metric["training_state"]["last_loss"]
    result["weights_changed_after_resumed_step"] = any(
        not b.equal(a) for b, a in zip(weights_before, weights_after, strict=True)
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
    result: dict = {"worker": "pause", "pid": os.getpid()}
    try:
        outcome = svc.pause(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    print(json.dumps(result), flush=True)


def worker_resume(tmp_dir: str, job_id: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    result: dict = {"worker": "resume", "pid": os.getpid()}
    try:
        outcome = svc.resume(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    print(json.dumps(result), flush=True)


def worker_finalize(tmp_dir: str, job_id: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    result: dict = {"worker": "finalize", "pid": os.getpid()}
    try:
        outcome = svc.finalize(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    print(json.dumps(result), flush=True)


def worker_cancel(tmp_dir: str, job_id: str, admin_id: str, signal_file: str | None) -> None:
    svc = _service(tmp_dir)
    _wait_for_signal(signal_file)
    result: dict = {"worker": "cancel", "pid": os.getpid()}
    try:
        outcome = svc.cancel(job_id, admin_id=admin_id)
        result["succeeded"] = True
        result["status"] = outcome["status"]
    except Exception as exc:  # noqa: BLE001
        result["succeeded"] = False
        result["error"] = str(exc)
        result["error_type"] = type(exc).__name__
    print(json.dumps(result), flush=True)


def longer_run(tmp_dir: str, job_id: str, admin_id: str, num_steps: str, checkpoint_every: str) -> None:
    """Bounded stability run -- NOT resumed in a fresh process (that is
    proven separately, Section 6). Reuses the SAME live adapter across
    many real steps in one process, measuring latency/RSS/loss trend
    directly."""

    svc = _service(tmp_dir)
    steps = int(num_steps)
    every = int(checkpoint_every)
    step_seconds: list[float] = []
    losses: list[float] = []
    rss_samples: list[int] = []
    checkpoint_seconds: list[float] = []
    errors: list[str] = []

    for i in range(2, steps + 2):  # step=1 already recorded by setup()
        try:
            t0 = time.perf_counter()
            metric = svc.run_stream_metric_stage(job_id, step=i, epoch=0, admin_id=admin_id)
            step_seconds.append(time.perf_counter() - t0)
            losses.append(metric["training_state"]["last_loss"])
            rss_samples.append(_rss_kib())
            if every > 0 and i % every == 0:
                t0 = time.perf_counter()
                svc.run_save_checkpoint_stage(job_id, step=i, epoch=0, admin_id=admin_id)
                checkpoint_seconds.append(time.perf_counter() - t0)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"step={i}: {type(exc).__name__}: {exc}")
            break

    checkpoints = svc.list_checkpoints(job_id)["items"]
    metrics = svc.list_metrics(job_id, limit=200, offset=0)["items"]

    result = {
        "steps_attempted": steps, "steps_completed": len(step_seconds),
        "step_seconds": step_seconds, "losses": losses, "rss_kib_samples": rss_samples,
        "checkpoint_seconds": checkpoint_seconds, "errors": errors,
        "checkpoint_row_count": len(checkpoints), "metric_row_count": len(metrics),
        "final_rss_kib": _rss_kib(),
    }
    print(json.dumps(result), flush=True)


def inject_failure(tmp_dir: str, job_id: str, admin_id: str) -> None:
    """Injects exactly one controlled, genuine training exception by
    monkeypatching the LIVE, already-configured adapter's `step()`
    method for a single call -- the smallest, most transparent failure-
    injection mechanism available (same technique as Phase 2.8B/2.8E's
    own established `_FailingStepAdapter`-style tests)."""

    from backend.services.training_adapter_registry import REGISTRY

    svc = _service(tmp_dir)
    adapter = REGISTRY.get(job_id)
    if adapter is None:
        # No live adapter in this process -- reconstruct one via the
        # normal recovery path first (still a real adapter, never a
        # mock), then inject the failure on it.
        job_data = svc.job(job_id)
        adapter = svc._ensure_adapter_for_job(job_data, allow_fresh_construction=False)

    def failing_step(*, step, epoch):
        raise RuntimeError("Phase 2.8G controlled test exception -- injected deliberately")

    original_step = adapter.step
    adapter.step = failing_step
    result: dict = {}
    try:
        svc.run_stream_metric_stage(job_id, step=999, epoch=0, admin_id=admin_id)
        result["raised"] = False
    except RuntimeError as exc:
        result["raised"] = True
        result["error"] = str(exc)
    finally:
        adapter.step = original_step

    job_after = svc.job(job_id)
    result["job_status"] = job_after["status"]
    result["job_stage"] = job_after["stage"]
    result["last_error"] = job_after["training_state"].get("last_error")
    result["registry_still_contains_job"] = REGISTRY.contains(job_id)
    print(json.dumps(result), flush=True)


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
    elif mode == "resume_and_continue":
        resume_and_continue(a[0], a[1], a[2])
    elif mode == "worker_step":
        worker_step(a[0], a[1], a[2], a[3], sf)
    elif mode == "worker_checkpoint":
        worker_checkpoint(a[0], a[1], a[2], a[3], sf)
    elif mode == "worker_pause":
        worker_pause(a[0], a[1], a[2], sf)
    elif mode == "worker_resume":
        worker_resume(a[0], a[1], a[2], sf)
    elif mode == "worker_finalize":
        worker_finalize(a[0], a[1], a[2], sf)
    elif mode == "worker_cancel":
        worker_cancel(a[0], a[1], a[2], sf)
    elif mode == "longer_run":
        longer_run(a[0], a[1], a[2], a[3], a[4])
    elif mode == "inject_failure":
        inject_failure(a[0], a[1], a[2])
    else:
        raise SystemExit(f"unknown mode: {mode}")
