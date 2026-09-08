"""Phase 2.8F: Multi-Worker Process Concurrency, Distributed Job Lock &
Training State Consistency.

Phase 2.8E's `JobAdapterRegistry` and per-job `threading.Lock` are both
process-local by construction (`REGISTRY = JobAdapterRegistry()` is a
plain module-level singleton -- a second OS process importing the same
module gets its own, completely independent instance). This phase
directly, empirically proves what that implies for two genuinely
separate OS processes operating on the same MB-22 job at the same
time, using `subprocess.Popen` throughout (never threads) for every
primary concurrency claim -- no shared Python objects, no shared
adapter, no shared registry, no inherited adapter state.

**Real defects were found and fixed, not merely audited** (see
`tests/backend/_phase28f_subprocess_runner.py` and the Phase 2.8F
report for the full reproduction detail):

1. Two independent workers resuming the same paused job could both
   succeed, both recording a `training_recovered_from_checkpoint`
   event (double recovery). Fixed: `resume()`'s status write is now a
   real, atomic compare-and-swap
   (`update_job(..., expected_status="paused")`) -- SQLite itself, not
   any in-process lock, decides which worker's recovery is valid.
2. Two independent workers computing the same nominal training step
   (each reconstructing independently from the same last checkpoint)
   could both succeed, producing two metric rows for the same
   `(job, step, epoch)`. Fixed: a new DB-level UNIQUE index
   (`ux_mini_brain_training_metrics_job_step_epoch`, migration 076,
   mirroring the checkpoint table's own, already-proven unique-index
   pattern) plus the same compare-and-swap discipline for the job's
   `status` at write time.
3. A concurrent `pause()`/`cancel()`/`finalize()` from one worker could
   commit before a concurrent `run_stream_metric_stage()` from another
   worker finished its own real training step, and the step's write
   would land afterward with no re-validation -- producing an
   "impossible" persisted combination (e.g. `status='paused'` with a
   `training_state.last_step` that was actually written after the
   pause). Fixed by the same `expected_status` compare-and-swap,
   applied uniformly to every gpu-mode stage write that touches job
   status (`pause`, `resume`, `cancel`, `finalize`,
   `run_stream_metric_stage`).

Every fix uses this project's own existing SQLite architecture (a
single atomic `UPDATE ... WHERE status IN (...)` statement, and a
UNIQUE index exactly mirroring an already-existing one) -- no new
lock table, no lease, no distributed infrastructure, no change to
`TorchTrainingAdapter`, `TrainingCheckpointManager`, or any readiness
gate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.database.connection import database_connection
from tests.backend.test_mini_brain_training_engine_service import _create_admin

pytestmark = pytest.mark.anyio

_RUNNER = Path(__file__).parent / "_phase28f_subprocess_runner.py"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.core.config import Settings
    from backend.database.migrations import initialize_database
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus", tokenizer_dir=tmp_path / "tokenizers",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _setup(work_dir: Path, name_suffix: str, *, with_checkpoint: bool = True, record_count: int = 60,
           hidden_size: int = 16, intermediate_size: int = 32, timeout: int = 300) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(_RUNNER), "setup", str(work_dir), name_suffix, str(record_count),
         "true" if with_checkpoint else "false", str(hidden_size), str(intermediate_size)],
        capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def _run_two_concurrent(work_dir: Path, cmd_a: list[str], cmd_b: list[str], timeout: int = 60) -> tuple[dict, dict]:
    """Launches two genuinely independent OS processes via
    `subprocess.Popen`, synchronized to start their real operation at
    (as close as the OS scheduler allows to) the same instant via a
    plain filesystem signal file -- no shared Python state, no IPC
    beyond that one flag file's existence."""

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
    time.sleep(0.3)  # both processes are past their own setup and waiting on the signal file
    signal_file.write_text("go")
    out_a, err_a = proc_a.communicate(timeout=timeout)
    out_b, err_b = proc_b.communicate(timeout=timeout)
    assert proc_a.returncode == 0, err_a[-4000:]
    assert proc_b.returncode == 0, err_b[-4000:]
    return json.loads(out_a.strip().splitlines()[-1]), json.loads(out_b.strip().splitlines()[-1])


def _run_worker(work_dir: Path, *cmd: str, timeout: int = 60) -> dict:
    result = subprocess.run(
        [sys.executable, str(_RUNNER), *cmd], capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def _job_row(database_path: str, job_id: str) -> dict:
    with database_connection(Path(database_path)) as connection:
        row = connection.execute(
            "SELECT status, stage, training_state_json FROM mini_brain_training_jobs WHERE public_id=?", (job_id,)
        ).fetchone()
        return dict(row)


def _counts(database_path: str, job_id: str) -> dict:
    with database_connection(Path(database_path)) as connection:
        job_row = connection.execute(
            "SELECT id FROM mini_brain_training_jobs WHERE public_id=?", (job_id,)
        ).fetchone()
        job_row_id = job_row["id"]
        metrics = connection.execute(
            "SELECT COUNT(*) FROM mini_brain_training_metrics WHERE job_id=?", (job_row_id,)
        ).fetchone()[0]
        checkpoints = connection.execute(
            "SELECT COUNT(*) FROM mini_brain_training_checkpoints WHERE job_id=?", (job_row_id,)
        ).fetchone()[0]
        events = connection.execute(
            """SELECT event_type, COUNT(*) as n FROM mini_brain_training_events
            WHERE job_id=? GROUP BY event_type""", (job_row_id,),
        ).fetchall()
        jobs = connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0]
        return {
            "metrics": metrics, "checkpoints": checkpoints,
            "events": {row["event_type"]: row["n"] for row in events}, "jobs": jobs,
        }


# ===========================================================================
# Part 4A: two workers, simultaneous training step.
# ===========================================================================


class TestScenarioA_SimultaneousStep:
    def test_two_workers_same_step_exactly_one_metric_row(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "a", "scenA")
        a, b = _run_two_concurrent(
            tmp_path / "a",
            ["worker_step", str(tmp_path / "a"), info["job_id"], "2", info["admin_id"]],
            ["worker_step", str(tmp_path / "a"), info["job_id"], "2", info["admin_id"]],
        )
        outcomes = [a, b]
        successes = [o for o in outcomes if o["succeeded"]]
        rejections = [o for o in outcomes if not o["succeeded"]]
        assert len(successes) == 1, outcomes
        assert len(rejections) == 1
        assert rejections[0]["error_type"] == "ValidationError"
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["metrics"] == 2  # step 1 (setup) + step 2 (the single winner)
        row = _job_row(info["database_path"], info["job_id"])
        assert json.loads(row["training_state_json"])["last_step"] == 2


# ===========================================================================
# Part 4B: step vs checkpoint.
# ===========================================================================


class TestScenarioB_StepVsCheckpoint:
    def test_step_and_checkpoint_same_step_number_both_valid_no_corruption(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "b", "scenB")
        step_result, ckpt_result = _run_two_concurrent(
            tmp_path / "b",
            ["worker_step", str(tmp_path / "b"), info["job_id"], "2", info["admin_id"]],
            ["worker_checkpoint", str(tmp_path / "b"), info["job_id"], "2", info["admin_id"]],
        )
        # Both may legitimately succeed -- they write to disjoint tables
        # (metrics vs checkpoints) and neither corrupts the other.
        assert step_result["succeeded"] is True
        assert ckpt_result["succeeded"] is True
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["checkpoints"] == 2  # step 1 (setup) + step 2, never duplicated
        assert counts["metrics"] == 2


# ===========================================================================
# Part 4C: pause vs step.
# ===========================================================================


class TestScenarioC_PauseVsStep:
    def test_pause_and_step_produce_one_coherent_state(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "c", "scenC")
        pause_result, step_result = _run_two_concurrent(
            tmp_path / "c",
            ["worker_pause", str(tmp_path / "c"), info["job_id"], info["admin_id"]],
            ["worker_step", str(tmp_path / "c"), info["job_id"], "2", info["admin_id"]],
        )
        assert pause_result["succeeded"] is True
        assert pause_result["status"] == "paused"
        row = _job_row(info["database_path"], info["job_id"])
        assert row["status"] == "paused"
        training_state = json.loads(row["training_state_json"])
        if step_result["succeeded"]:
            # The step's real execution (and commit) genuinely preceded
            # the pause's own commit -- a coherent, explainable ordering,
            # never an impossible hybrid.
            assert training_state["last_step"] == 2
        else:
            # The step was correctly rejected because pause committed
            # first -- training_state must NOT show a step that was
            # written after the job was already paused.
            assert training_state["last_step"] == 1
            assert step_result["error_type"] == "ValidationError"


# ===========================================================================
# Part 4D: resume vs resume.
# ===========================================================================


class TestScenarioD_ResumeVsResume:
    def test_exactly_one_recovery_succeeds(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "d", "scenD")
        with database_connection(Path(info["database_path"])) as connection:
            connection.execute(
                "UPDATE mini_brain_training_jobs SET status='paused' WHERE public_id=?", (info["job_id"],)
            )
            connection.commit()

        a, b = _run_two_concurrent(
            tmp_path / "d",
            ["worker_resume", str(tmp_path / "d"), info["job_id"], info["admin_id"]],
            ["worker_resume", str(tmp_path / "d"), info["job_id"], info["admin_id"]],
        )
        outcomes = [a, b]
        successes = [o for o in outcomes if o["succeeded"]]
        rejections = [o for o in outcomes if not o["succeeded"]]
        assert len(successes) == 1, outcomes
        assert len(rejections) == 1
        assert "concurrent worker" in rejections[0]["error"] or "paused" in rejections[0]["error"]
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["events"].get("training_recovered_from_checkpoint", 0) == 1
        assert counts["jobs"] == 1
        row = _job_row(info["database_path"], info["job_id"])
        assert row["status"] == "running"


# ===========================================================================
# Part 4E / 4F: finalize vs step, cancel vs step.
# ===========================================================================


class TestScenarioEF_TerminalVsStep:
    def test_finalize_vs_step_no_training_state_committed_after_finalization(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "e", "scenE")
        finalize_result, step_result = _run_two_concurrent(
            tmp_path / "e",
            ["worker_finalize", str(tmp_path / "e"), info["job_id"], info["admin_id"]],
            ["worker_step", str(tmp_path / "e"), info["job_id"], "2", info["admin_id"]],
        )
        assert finalize_result["succeeded"] is True
        assert finalize_result["status"] == "completed"
        row = _job_row(info["database_path"], info["job_id"])
        assert row["status"] == "completed"
        assert row["stage"] == "generate_report"
        training_state = json.loads(row["training_state_json"])
        if not step_result["succeeded"]:
            # The step was correctly rejected -- training_state must
            # still show only the setup's own step (1), never the
            # rejected step=2 attempt.
            assert training_state["last_step"] == 1
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["jobs"] == 1
        assert counts["events"].get("training_finalized", 0) == 1

    def test_cancel_vs_step_no_impossible_terminal_state(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "f", "scenF")
        cancel_result, step_result = _run_two_concurrent(
            tmp_path / "f",
            ["worker_cancel", str(tmp_path / "f"), info["job_id"], info["admin_id"]],
            ["worker_step", str(tmp_path / "f"), info["job_id"], "2", info["admin_id"]],
        )
        assert cancel_result["succeeded"] is True
        assert cancel_result["status"] == "cancelled"
        row = _job_row(info["database_path"], info["job_id"])
        assert row["status"] == "cancelled"
        assert row["stage"] == "cancelled"
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["jobs"] == 1
        assert counts["events"].get("training_cancelled", 0) == 1


# ===========================================================================
# Part 4G: checkpoint vs checkpoint, same (job, step, epoch).
# ===========================================================================


class TestScenarioG_CheckpointVsCheckpoint:
    def test_exactly_one_checkpoint_row_and_one_canonical_directory(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "g", "scenG")
        a, b = _run_two_concurrent(
            tmp_path / "g",
            ["worker_checkpoint", str(tmp_path / "g"), info["job_id"], "2", info["admin_id"]],
            ["worker_checkpoint", str(tmp_path / "g"), info["job_id"], "2", info["admin_id"]],
        )
        outcomes = [a, b]
        successes = [o for o in outcomes if o["succeeded"]]
        rejections = [o for o in outcomes if not o["succeeded"]]
        assert len(successes) == 1, outcomes
        assert len(rejections) == 1
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["checkpoints"] == 2  # step 1 (setup) + the single step-2 winner

        job_dir = Path(info["pretraining_dir"]) / "mini_brain_training_jobs" / info["job_id"]
        canonical_dirs = sorted(p.name for p in job_dir.iterdir() if p.is_dir() and p.name.startswith("step-"))
        assert canonical_dirs == ["step-00000001-epoch-0000", "step-00000002-epoch-0000"]


# ===========================================================================
# Part 8: crash / worker death, genuinely separate subprocesses.
# ===========================================================================


class TestCrashRecovery:
    def test_worker_terminated_before_operation_commit_no_false_success(self, tmp_path: Path) -> None:
        """A worker is deterministically killed (`os._exit(137)`)
        immediately before its checkpoint's atomic publish -- proves no
        false-success DB row, no canonical partial checkpoint, and that
        the next worker recovers correctly from the surviving prior
        checkpoint."""

        info = _setup(tmp_path / "crash", "scenCrash")
        result = subprocess.run(
            [sys.executable, str(_RUNNER), "kill_mid_checkpoint_save", str(tmp_path / "crash"),
             info["job_id"], "2", info["admin_id"]],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 137

        counts = _counts(info["database_path"], info["job_id"])
        assert counts["checkpoints"] == 1  # only the setup's own step-1 checkpoint

        job_dir = Path(info["pretraining_dir"]) / "mini_brain_training_jobs" / info["job_id"]
        canonical_dirs = sorted(p.name for p in job_dir.iterdir() if p.is_dir() and p.name.startswith("step-"))
        assert canonical_dirs == ["step-00000001-epoch-0000"]  # no partial step-2 canonical directory
        # An orphaned temp directory from the interrupted build may
        # exist (this is expected and harmless -- it is never named
        # like a canonical checkpoint, so no reader ever selects it).
        stray_dirs = [
            p.name for p in job_dir.iterdir() if p.is_dir() and not p.name.startswith("step-")
        ]
        for name in stray_dirs:
            assert not name.startswith("step-")

        # The next worker recovers cleanly from the surviving checkpoint
        # and can itself save a real, valid step-2 checkpoint.
        recovery = _run_worker(
            tmp_path / "crash", "worker_checkpoint", str(tmp_path / "crash"), info["job_id"], "2", info["admin_id"],
        )
        assert recovery["succeeded"] is True
        final_counts = _counts(info["database_path"], info["job_id"])
        assert final_counts["checkpoints"] == 2

    def test_worker_terminated_before_any_checkpoint_next_worker_reports_honestly(self, tmp_path: Path) -> None:
        """No checkpoint exists at all when the worker dies -- the next
        worker must never fabricate one; it reports the same, honest
        'cannot be reconstructed' condition Phase 2.8E established."""

        info = _setup(tmp_path / "crash2", "scenCrash2", with_checkpoint=False)
        # Simulate the dead worker: nothing was ever checkpointed.
        result = _run_worker(
            tmp_path / "crash2", "worker_step", str(tmp_path / "crash2"), info["job_id"], "1", info["admin_id"],
        )
        assert result["succeeded"] is False
        assert "cannot be reconstructed" in result["error"]
        row = _job_row(info["database_path"], info["job_id"])
        assert row["status"] == "running"  # not falsely marked failed (Part 13)
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["checkpoints"] == 0
        assert counts["jobs"] == 1


# ===========================================================================
# Part 7: TOCTOU-adjacent -- interrupted-then-recovered checkpoint state
# remains selectable and correct after exact-byte restoration.
# ===========================================================================


class TestStaleCheckpointNotSilentlySubstituted:
    def test_corrupted_latest_checkpoint_never_falls_back_to_older_one_under_concurrent_workers(
        self, tmp_path: Path,
    ) -> None:
        info = _setup(tmp_path / "stale", "scenStale")
        # Build a second, real checkpoint (step 2) via one worker.
        second = _run_worker(
            tmp_path / "stale", "worker_checkpoint", str(tmp_path / "stale"), info["job_id"], "2", info["admin_id"],
        )
        assert second["succeeded"] is True

        job_dir = Path(info["pretraining_dir"]) / "mini_brain_training_jobs" / info["job_id"]
        latest_dir = job_dir / "step-00000002-epoch-0000"
        model_path = latest_dir / "model_state.pt"
        original = model_path.read_bytes()
        model_path.write_bytes(original + b"corrupted-by-phase28f")

        # resume() requires status='paused' -- force it back to paused
        # (mirroring a real pause the operator would have issued), then
        # attempt recovery, which must fail closed on the corrupted
        # latest checkpoint rather than silently falling back to the
        # older, uncorrupted step-1 checkpoint.
        with database_connection(Path(info["database_path"])) as connection:
            connection.execute(
                "UPDATE mini_brain_training_jobs SET status='paused' WHERE public_id=?", (info["job_id"],)
            )
            connection.commit()
        result = _run_worker(
            tmp_path / "stale", "worker_resume", str(tmp_path / "stale"), info["job_id"], info["admin_id"],
        )
        assert result["succeeded"] is False
        assert "checksum mismatch" in result["error"]

        model_path.write_bytes(original)
        recovered = _run_worker(
            tmp_path / "stale", "worker_resume", str(tmp_path / "stale"), info["job_id"], info["admin_id"],
        )
        assert recovered["succeeded"] is True


# ===========================================================================
# Part 10: cross-job isolation, three independent jobs, concurrent workers.
# ===========================================================================


class TestCrossJobIsolation:
    def test_three_jobs_concurrent_workers_never_cross_contaminate(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "iso"
        info_a = _setup(work_dir, "isoA", hidden_size=16, intermediate_size=32)
        info_b = _setup(work_dir, "isoB", hidden_size=24, intermediate_size=48)
        info_c = _setup(work_dir, "isoC", hidden_size=32, intermediate_size=64)

        signal_file = work_dir / "signal-iso"
        signal_file.unlink(missing_ok=True)
        procs = [
            subprocess.Popen(
                [sys.executable, str(_RUNNER), "worker_step", str(work_dir), info_a["job_id"], "2",
                 info_a["admin_id"], "--signal-file", str(signal_file)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ),
            subprocess.Popen(
                [sys.executable, str(_RUNNER), "worker_cancel", str(work_dir), info_b["job_id"],
                 info_b["admin_id"], "--signal-file", str(signal_file)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ),
            subprocess.Popen(
                [sys.executable, str(_RUNNER), "worker_checkpoint", str(work_dir), info_c["job_id"], "2",
                 info_c["admin_id"], "--signal-file", str(signal_file)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ),
        ]
        time.sleep(0.3)
        signal_file.write_text("go")
        outputs = []
        for proc in procs:
            out, err = proc.communicate(timeout=60)
            assert proc.returncode == 0, err[-4000:]
            outputs.append(json.loads(out.strip().splitlines()[-1]))

        result_a, result_b, result_c = outputs
        assert result_a["succeeded"] is True
        assert result_b["succeeded"] is True
        assert result_b["status"] == "cancelled"
        assert result_c["succeeded"] is True

        with database_connection(Path(info_a["database_path"])) as connection:
            rows = {
                row["public_id"]: dict(row)
                for row in connection.execute(
                    "SELECT public_id, status, core_model_version_public_id FROM mini_brain_training_jobs"
                )
            }
            checkpoint_provenance = connection.execute(
                """SELECT j.public_id as job, c.core_model_version_public_id as cmv
                FROM mini_brain_training_checkpoints c JOIN mini_brain_training_jobs j ON j.id=c.job_id"""
            ).fetchall()

        # Job A untouched by B's cancel; Job C untouched by either.
        assert rows[info_a["job_id"]]["status"] == "running"
        assert rows[info_b["job_id"]]["status"] == "cancelled"
        assert rows[info_c["job_id"]]["status"] == "running"

        # Every checkpoint's recorded Core Model Version matches its own
        # job's -- never another job's identity.
        for row in checkpoint_provenance:
            assert rows[row["job"]]["core_model_version_public_id"] == row["cmv"]


# ===========================================================================
# Part 11: adversarial cross-job checkpoint substitution, independent
# processes.
# ===========================================================================


class TestCrossJobCheckpointSubstitution:
    def test_job_b_cannot_recover_from_job_as_checkpoint_via_independent_worker(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "xjob"
        info_a = _setup(work_dir, "xjobA", hidden_size=16, intermediate_size=32)
        info_b = _setup(work_dir, "xjobB", hidden_size=24, intermediate_size=48)

        real_checkpoint_dir = (
            Path(info_a["pretraining_dir"]) / "mini_brain_training_jobs" / info_a["job_id"]
            / "step-00000001-epoch-0000"
        )
        job_b_root = Path(info_b["pretraining_dir"]) / "mini_brain_training_jobs" / info_b["job_id"]
        copied_dir = job_b_root / "step-00000001-epoch-0000"
        # Job B already has its own real step-1 checkpoint from setup --
        # remove it first so the planted, cross-job one is genuinely the
        # only (and therefore "latest") one available for recovery.
        shutil.rmtree(copied_dir)
        shutil.copytree(real_checkpoint_dir, copied_dir)

        # Job B's own DB checkpoint row still points at its own,
        # now-replaced-on-disk canonical directory (same path, swapped
        # content) -- recovery must still fail on the references.json
        # identity embedded in that directory, not on path confinement.
        with database_connection(Path(info_b["database_path"])) as connection:
            connection.execute(
                "UPDATE mini_brain_training_jobs SET status='paused' WHERE public_id=?", (info_b["job_id"],)
            )
            connection.commit()

        result = _run_worker(work_dir, "worker_resume", str(work_dir), info_b["job_id"], info_b["admin_id"])
        assert result["succeeded"] is False
        assert "does not match this job" in result["error"]

        with database_connection(Path(info_b["database_path"])) as connection:
            pretraining_checkpoints = connection.execute("SELECT COUNT(*) FROM pretraining_checkpoints").fetchone()[0]
        assert pretraining_checkpoints == 0


# ===========================================================================
# Part 12: idempotency under multi-process retries.
# ===========================================================================


class TestIdempotency:
    def test_repeated_checkpoint_same_step_across_processes_rejected(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "idem-ckpt", "idemCkpt")
        first = _run_worker(tmp_path / "idem-ckpt", "worker_checkpoint", str(tmp_path / "idem-ckpt"), info["job_id"], "1", info["admin_id"])
        assert first["succeeded"] is False  # step 1 already exists from setup
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["checkpoints"] == 1

    def test_repeated_cancel_across_processes_rejected(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "idem-cancel", "idemCancel")
        first = _run_worker(tmp_path / "idem-cancel", "worker_cancel", str(tmp_path / "idem-cancel"), info["job_id"], info["admin_id"])
        assert first["succeeded"] is True
        second = _run_worker(tmp_path / "idem-cancel", "worker_cancel", str(tmp_path / "idem-cancel"), info["job_id"], info["admin_id"])
        assert second["succeeded"] is False
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["jobs"] == 1
        assert counts["events"].get("training_cancelled", 0) == 1

    def test_repeated_finalize_across_processes_rejected(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "idem-finalize", "idemFinalize")
        first = _run_worker(tmp_path / "idem-finalize", "worker_finalize", str(tmp_path / "idem-finalize"), info["job_id"], info["admin_id"])
        assert first["succeeded"] is True
        second = _run_worker(tmp_path / "idem-finalize", "worker_finalize", str(tmp_path / "idem-finalize"), info["job_id"], info["admin_id"])
        assert second["succeeded"] is False
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["events"].get("training_finalized", 0) == 1

    def test_repeated_resume_across_processes_rejected(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "idem-resume", "idemResume")
        with database_connection(Path(info["database_path"])) as connection:
            connection.execute(
                "UPDATE mini_brain_training_jobs SET status='paused' WHERE public_id=?", (info["job_id"],)
            )
            connection.commit()
        first = _run_worker(tmp_path / "idem-resume", "worker_resume", str(tmp_path / "idem-resume"), info["job_id"], info["admin_id"])
        assert first["succeeded"] is True
        second = _run_worker(tmp_path / "idem-resume", "worker_resume", str(tmp_path / "idem-resume"), info["job_id"], info["admin_id"])
        assert second["succeeded"] is False
        counts = _counts(info["database_path"], info["job_id"])
        assert counts["events"].get("training_recovered_from_checkpoint", 0) == 1


# ===========================================================================
# Part 13: failure classification remains correct across independent
# workers.
# ===========================================================================


class TestFailureClassification:
    def test_reconstruction_failure_never_becomes_status_failed(self, tmp_path: Path) -> None:
        info = _setup(tmp_path / "faildist", "failDist", with_checkpoint=False)
        result = _run_worker(
            tmp_path / "faildist", "worker_step", str(tmp_path / "faildist"), info["job_id"], "1", info["admin_id"],
        )
        assert result["succeeded"] is False
        assert result["error_type"] == "ValidationError"
        row = _job_row(info["database_path"], info["job_id"])
        assert row["status"] == "running"

    async def test_genuine_training_exception_still_reaches_failed_status(self, api_app: FastAPI) -> None:
        """A real training-time exception (in-process, since a genuine
        exception requires controlling the adapter's own `step()` call
        directly) still reaches Phase 2.8B's failure path unchanged --
        confirms Phase 2.8F's new cross-process CAS logic never
        interferes with this distinct, pre-existing failure path."""

        from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
        from backend.services.training_adapter_registry import REGISTRY
        from tests.backend.test_mini_brain_training_engine_service import _seed_approved_package_and_release
        from tests.backend.test_phase27h_training_dataset_readiness import (
            _build_real_dataset_via_service, _generate_corpus, _real_tokenizer,
        )
        from tests.backend.test_torch_training_adapter_integration import _real_core_model_version

        settings = api_app.state.settings
        admin_id = _create_admin(api_app, username="admin-failexc")
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="failexc")
        tokenizer_id = _real_tokenizer(settings, name_suffix="failexc")
        cmv_id = _real_core_model_version(settings, admin_id, name_suffix="failexc", tokenizer_version_public_id=tokenizer_id)
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="failexc", record_texts=_generate_corpus(60, seed_offset=1),
        )
        svc = MiniBrainTrainingEngineService(settings)
        job = svc.create_job(
            topic="failexc-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
        )
        job_id = job["public_id"]
        svc.run_validate_release_stage(job_id, admin_id=admin_id)
        svc.run_validate_package_stage(job_id, admin_id=admin_id)
        svc.run_validate_authorization_stage(job_id, authorization_reason="failexc", admin_id=admin_id)
        svc.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc.run_build_manifest_stage(job_id, admin_id=admin_id)
        svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION")
        svc.run_start_training_stage(job_id, admin_id=admin_id)

        real_adapter = REGISTRY.get(job_id)
        original_step = real_adapter.step

        def failing_step(*, step, epoch):
            raise RuntimeError("simulated genuine training failure")

        real_adapter.step = failing_step
        try:
            with pytest.raises(RuntimeError, match="simulated genuine training failure"):
                svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        finally:
            real_adapter.step = original_step

        job_after = svc.job(job_id)
        assert job_after["status"] == "failed"
        assert job_after["stage"] == "generate_report"
        assert job_after["training_state"]["last_error"]
        assert not REGISTRY.contains(job_id)
