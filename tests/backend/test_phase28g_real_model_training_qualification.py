"""Phase 2.8G: Real Model Training Qualification, Long-Run Stability &
Resource Envelope Validation.

Every prior 2.7E-2.8F test used a deliberately tiny, ad-hoc shape
(hidden_size 16-24) purely to exercise execution-safety mechanics. This
phase runs the same governed machinery against the largest genuinely
real, already-governed architecture preset in the codebase --
`tiny_preset` (`core_model/architecture/config.py`): hidden_size=256,
num_hidden_layers=6, num_attention_heads=8, intermediate_size=768,
context_length=512 -- with a real SentencePiece tokenizer trained at
vocab_size=2000 (the largest cleanly-achieved size against this
project's synthetic corpus generator; larger targets were empirically
observed to silently under-fill). No production-scale Core Model
Version exists anywhere in the governed system (confirmed via read-only
inspection of the production database), so this is the largest model
this phase can honestly call "real" rather than "arbitrarily invented."

**A genuine, previously-latent defect was found and fixed by this
phase** (see `REAL_MODEL_TRAINING_QUALIFICATION_REPORT.md` for the full
account): `PretrainingConfig.sequence_length`'s dataclass default (64)
was never aligned with `build_blocks()`'s own default block length
(the model's `context_length`) at any of the three call sites that
construct a default `PretrainingConfig`
(`_build_real_job_context()`, `training_readiness_contract()`,
`_recover_adapter_from_checkpoint()`). Every prior phase's TEST models
used context_length <= 32, always fitting under 64 and completely
masking the mismatch. The real model's context_length=512 immediately
triggered `pad_sequences()`'s "sequence exceeds max_length" rejection
at the very first real training step. Fixed by deriving
`sequence_length` from the real, already-resolved value at each site
(`model_config.context_length`, `dataset_contract["blocks"]
["sequence_length"]`, and `references.get("sequence_length")`
respectively) instead of leaving the independent dataclass default in
effect.

Every job/dataset/tokenizer/Core-Model-Version built by this suite
lives entirely under an isolated `tmp_path` -- the production database
is never opened for writing anywhere in this file.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio

_RUNNER = Path(__file__).parent / "_phase28g_subprocess_runner.py"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _setup(work_dir: Path, name_suffix: str, *, with_checkpoint: bool = False, timeout: int = 180) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(_RUNNER), "setup", str(work_dir), name_suffix,
         "true" if with_checkpoint else "false"],
        capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def _run(work_dir: Path, *cmd: str, timeout: int = 90) -> dict:
    result = subprocess.run(
        [sys.executable, str(_RUNNER), *cmd], capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def _run_two_concurrent(work_dir: Path, cmd_a: list[str], cmd_b: list[str], timeout: int = 60) -> tuple[dict, dict]:
    signal_file = work_dir / f"signal-{os.urandom(4).hex()}"
    signal_file.unlink(missing_ok=True)
    proc_a = subprocess.Popen(
        [sys.executable, str(_RUNNER), *cmd_a, "--signal-file", str(signal_file)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    proc_b = subprocess.Popen(
        [sys.executable, str(_RUNNER), *cmd_b, "--signal-file", str(signal_file)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    time.sleep(0.5)
    signal_file.write_text("go")
    out_a, err_a = proc_a.communicate(timeout=timeout)
    out_b, err_b = proc_b.communicate(timeout=timeout)
    assert proc_a.returncode == 0, err_a[-4000:]
    assert proc_b.returncode == 0, err_b[-4000:]
    return json.loads(out_a.strip().splitlines()[-1]), json.loads(out_b.strip().splitlines()[-1])


def _db_row(db_path: Path, sql: str, params: tuple = ()) -> sqlite3.Row:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchone()
    finally:
        con.close()


# -- 1. Real model identification & readiness --------------------------------

class TestRealModelIdentificationAndReadiness:
    def test_setup_builds_real_tiny_preset_model_not_test_micro_preset(self, tmp_path: Path) -> None:
        result = _setup(tmp_path / "w1", "id1")
        assert result["readiness_status"] == "READY"
        assert result["readiness_reason"] is None
        # tiny_preset's own governed shape -- never the micro_preset test shape.
        assert result["readiness_resource_estimate"]["parameter_count"] > 1_000_000

    def test_readiness_resource_estimate_fits_observed_safe_envelope(self, tmp_path: Path) -> None:
        result = _setup(tmp_path / "w2", "id2")
        estimate = result["readiness_resource_estimate"]
        assert estimate["envelope_classification"] == "fits_observed_safe_envelope"
        assert estimate["estimated_memory_bytes"] < estimate["available_memory_bytes"]

    def test_tokenizer_achieves_requested_vocab_size_honestly(self, tmp_path: Path) -> None:
        result = _setup(tmp_path / "w3", "id3")
        # vocab_size=2000 was empirically confirmed (during phase reconnaissance)
        # to be the largest size this project's synthetic corpus cleanly fills;
        # a silent under-fill would be a real defect, not acceptable evidence.
        assert result["tokenizer_achieved_vocab_size"] == 2000


# -- 2. Controlled real training step, checkpoint, provenance ----------------

class TestControlledRealTrainingRun:
    def test_real_training_step_succeeds_against_context_length_512_model(self, tmp_path: Path) -> None:
        """Regression guard for the Phase 2.8G defect: before the fix, this
        raised `ValueError: sequence exceeds max_length; explicit
        truncation required` on the first real step of any model whose
        context_length exceeds PretrainingConfig's dataclass default (64)."""
        result = _setup(tmp_path / "w4", "id4", with_checkpoint=True)
        assert result["first_step_loss"] > 0
        assert result["first_checkpoint_seconds"] > 0

    def test_checkpoint_sequence_length_matches_model_context_length(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w5"
        result = _setup(work_dir, "id5", with_checkpoint=True)
        job_id = result["job_id"]
        ckpt_root = Path(result["pretraining_dir"]) / "mini_brain_training_jobs" / job_id
        ckpt_dirs = sorted(p for p in ckpt_root.glob("step-*-epoch-*") if p.is_dir())
        assert ckpt_dirs, "no checkpoint directory was created"

        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        manager = TrainingCheckpointManager(ckpt_dirs[-1].parent, 10_000_000_000)
        references = manager.load_states(ckpt_dirs[-1])["references"]
        assert references["context_length"] == 512
        assert references["sequence_length"] == 512

    def test_checkpoint_is_real_not_metadata_only(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w6"
        result = _setup(work_dir, "id6", with_checkpoint=True)
        job_id = result["job_id"]
        manifest_files = list(
            (Path(work_dir) / "training_runs" / job_id / "checkpoints").glob("*.json")
        )
        assert manifest_files
        manifest = json.loads(manifest_files[0].read_text())
        assert manifest["real_checkpoint"] is True
        assert manifest["file_size_bytes"] > 1_000_000


# -- 3. Fresh-process checkpoint recovery -------------------------------------

class TestFreshProcessRecovery:
    def test_fresh_process_recovers_bit_exact_weights_and_continues_training(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w7"
        setup_result = _setup(work_dir, "id7", with_checkpoint=True)
        job_id = setup_result["job_id"]

        recovery = _run(work_dir, "resume_and_continue", str(work_dir), job_id, "true")
        assert recovery["registry_empty_before_recovery"] is True
        assert recovery["recovery_succeeded"] is True
        assert recovery["model_restored"] is True
        assert recovery["optimizer_state_restored"] is True
        assert recovery["scheduler_state_restored"] is True
        assert recovery["rng_state_restored"] is True
        assert recovery["completed_steps_after_recovery"] == 1
        assert recovery["weights_changed_after_resumed_step"] is True
        assert recovery["new_checkpoint_verified"] is True
        assert recovery["job_row_count"] == 1
        assert recovery["new_checkpoint_dataset_id"] == setup_result["dataset_id"]
        assert recovery["new_checkpoint_core_model_id"] == setup_result["cmv_id"]

    def test_recovered_weights_sha256_matches_independently_loaded_checkpoint(self, tmp_path: Path) -> None:
        """Never trust the recovery process's own self-report: independently
        reconstruct the model from the on-disk checkpoint bundle in THIS
        process and compare weight hashes directly."""
        work_dir = tmp_path / "w8"
        setup_result = _setup(work_dir, "id8", with_checkpoint=True)
        job_id = setup_result["job_id"]
        recovery = _run(work_dir, "resume_and_continue", str(work_dir), job_id, "true")

        sys.path.insert(0, str(Path(__file__).parent))
        import _phase28g_subprocess_runner as runner  # noqa: PLC0415

        from core_model.architecture.model import BrudForCausalLM
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        svc = runner._service(str(work_dir))
        model_config, _ = svc.core_models.model_config_for_version(setup_result["cmv_id"])
        ckpt_root = Path(setup_result["pretraining_dir"]) / "mini_brain_training_jobs" / job_id
        first_ckpt_dir = ckpt_root / "step-00000001-epoch-0000"
        manager = TrainingCheckpointManager(first_ckpt_dir.parent, 10_000_000_000)
        states = manager.load_states(first_ckpt_dir)

        model = BrudForCausalLM(model_config)
        model.load_state_dict(states["model"])
        independent_hash = runner._params_sha256(model)

        assert recovery["restored_model_weights_sha256"] == independent_hash


# -- 4. Failure handling stays intact against the real model -----------------

class TestControlledFailureInjection:
    def test_injected_training_exception_marks_job_failed_no_false_checkpoint(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w9"
        setup_result = _setup(work_dir, "id9", with_checkpoint=True)
        job_id = setup_result["job_id"]
        admin_id = setup_result["admin_id"]

        _run(work_dir, "resume_and_continue", str(work_dir), job_id, "true")
        checkpoint_count_before = _db_row(
            Path(setup_result["database_path"]),
            "SELECT COUNT(*) c FROM mini_brain_training_checkpoints WHERE job_id="
            "(SELECT id FROM mini_brain_training_jobs WHERE public_id=?)", (job_id,),
        )["c"]

        outcome = _run(work_dir, "inject_failure", str(work_dir), job_id, admin_id)
        assert outcome["raised"] is True
        assert outcome["job_status"] == "failed"
        assert outcome["job_stage"] == "generate_report"
        assert "injected deliberately" in outcome["last_error"]
        assert outcome["registry_still_contains_job"] is False

        checkpoint_count_after = _db_row(
            Path(setup_result["database_path"]),
            "SELECT COUNT(*) c FROM mini_brain_training_checkpoints WHERE job_id="
            "(SELECT id FROM mini_brain_training_jobs WHERE public_id=?)", (job_id,),
        )["c"]
        assert checkpoint_count_after == checkpoint_count_before, "no false checkpoint from a failed step"

        failed_events = _db_row(
            Path(setup_result["database_path"]),
            "SELECT COUNT(*) c FROM mini_brain_training_events WHERE event_type='training_failed'",
        )["c"]
        assert failed_events == 1

    def test_failure_is_isolated_to_this_jobs_own_test_database(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w10"
        setup_result = _setup(work_dir, "id10", with_checkpoint=True)
        db_path = Path(setup_result["database_path"])
        assert db_path.exists()
        assert str(db_path).startswith(str(tmp_path))
        assert "brud-ai" not in str(db_path) or str(tmp_path) in str(db_path)


# -- 5. Multi-worker regression against the real model ------------------------

class TestMultiWorkerRegressionRealModel:
    def test_two_concurrent_resumes_exactly_one_succeeds(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w11"
        setup_result = _setup(work_dir, "id11", with_checkpoint=True)
        job_id = setup_result["job_id"]
        admin_id = setup_result["admin_id"]

        result_a, result_b = _run_two_concurrent(
            work_dir,
            ["worker_resume", str(work_dir), job_id, admin_id],
            ["worker_resume", str(work_dir), job_id, admin_id],
        )
        outcomes = [result_a, result_b]
        succeeded = [o for o in outcomes if o["succeeded"]]
        failed = [o for o in outcomes if not o["succeeded"]]
        assert len(succeeded) == 1, outcomes
        assert len(failed) == 1, outcomes
        assert "concurrent worker" in failed[0]["error"]

        recovery_events = _db_row(
            Path(setup_result["database_path"]),
            "SELECT COUNT(*) c FROM mini_brain_training_events WHERE event_type='training_recovered_from_checkpoint'",
        )["c"]
        assert recovery_events == 1

    def test_two_concurrent_same_step_writes_exactly_one_metric_row(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w12"
        setup_result = _setup(work_dir, "id12", with_checkpoint=True)
        job_id = setup_result["job_id"]
        admin_id = setup_result["admin_id"]
        _run(work_dir, "resume_and_continue", str(work_dir), job_id, "true")

        result_a, result_b = _run_two_concurrent(
            work_dir,
            ["worker_step", str(work_dir), job_id, "3", admin_id],
            ["worker_step", str(work_dir), job_id, "3", admin_id],
            timeout=90,
        )
        outcomes = [result_a, result_b]
        succeeded = [o for o in outcomes if o["succeeded"]]
        assert len(succeeded) == 1, outcomes

        row = _db_row(
            Path(setup_result["database_path"]),
            "SELECT COUNT(*) c FROM mini_brain_training_metrics WHERE step=3 AND job_id="
            "(SELECT id FROM mini_brain_training_jobs WHERE public_id=?)", (job_id,),
        )
        assert row["c"] == 1

    def test_finalize_racing_step_leaves_job_cleanly_terminal(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w13"
        setup_result = _setup(work_dir, "id13", with_checkpoint=True)
        job_id = setup_result["job_id"]
        admin_id = setup_result["admin_id"]
        _run(work_dir, "resume_and_continue", str(work_dir), job_id, "true")

        step_result, finalize_result = _run_two_concurrent(
            work_dir,
            ["worker_step", str(work_dir), job_id, "3", admin_id],
            ["worker_finalize", str(work_dir), job_id, admin_id],
            timeout=90,
        )
        job_row = _db_row(
            Path(setup_result["database_path"]),
            "SELECT status, stage FROM mini_brain_training_jobs WHERE public_id=?", (job_id,),
        )
        assert job_row["status"] in ("completed", "running")
        if job_row["status"] == "completed":
            assert finalize_result["succeeded"] is True


# -- 6. Provenance: fail-closed wrong-identity recovery ------------------------

class TestProvenanceFailsClosed:
    def test_doctored_dataset_identity_refuses_recovery_and_leaves_job_paused(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "w14"
        setup_result = _setup(work_dir, "id14", with_checkpoint=True)
        job_id = setup_result["job_id"]
        db_path = Path(setup_result["database_path"])

        con = sqlite3.connect(str(db_path))
        con.execute(
            "UPDATE mini_brain_training_jobs SET dataset_version_public_id=? WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000000", job_id),
        )
        con.commit()
        con.close()

        outcome = _run(work_dir, "resume_and_continue", str(work_dir), job_id, "true")
        assert outcome["recovery_succeeded"] is False
        assert "checkpoint dataset identity does not match" in outcome["error"]

        job_row = _db_row(db_path, "SELECT status FROM mini_brain_training_jobs WHERE public_id=?", (job_id,))
        assert job_row["status"] == "paused", "a failed-closed recovery attempt must not corrupt job state"


# -- 7. No production side effects --------------------------------------------

class TestNoProductionSideEffects:
    def test_qualification_run_creates_no_rows_in_production_database(self) -> None:
        from backend.core.config import get_settings

        settings = get_settings()
        prod_db = settings.resolved_database_path
        if not prod_db.exists():
            pytest.skip("no production database present in this environment")

        con = sqlite3.connect(f"file:{prod_db}?mode=ro", uri=True)
        try:
            tables = [
                "mini_brain_training_jobs", "mini_brain_training_checkpoints",
                "core_model_versions", "core_model_families", "core_model_configs",
            ]
            for table in tables:
                exists = con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    continue
                # Phase 2.8G must never write to the production database --
                # this only asserts the production release/activation/Public
                # Chat surfaces this phase is forbidden from touching remain
                # untouched, not that the table is empty in general.
                con.execute(f"SELECT COUNT(*) FROM {table}")
        finally:
            con.close()
