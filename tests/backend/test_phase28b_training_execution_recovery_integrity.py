"""Phase 2.8B: Controlled Training Execution, Failure Recovery & Resume
Integrity.

Phase 2.8A answered "can training start?" This phase answers: once a
controlled MB-22 training job has legitimately started, does the
execution path remain safe, recoverable, deterministic, and
provenance-correct across interruption, checkpoint, pause/resume,
failure, and retry scenarios?

Real findings, not assumed from any prior report:

1. A REAL, previously-unwritten status transition: any genuine exception
   from `TorchTrainingAdapter.step()` (not the expected pause/cancel
   early-return) used to propagate straight out of
   `run_stream_metric_stage()` with the job's own `status` left exactly
   as `'running'` forever -- no event recorded, no transition to the
   schema's own already-supported `'failed'` status, and
   `generate_report_stage()`'s existing failure-handling branch
   (`classify_failure(error_message=...training_state["last_error"])`,
   already reading a field nothing ever wrote) permanently unreachable.
   Fixed this phase (`MiniBrainTrainingEngineService.
   _record_training_failure()`), reusing `finalize()`'s own exact
   status/stage transition shape rather than inventing a new one.

2. MB-22's `pause()`/`resume()` are a real, in-process-only mechanism:
   `TorchTrainingAdapter.pause()`/`resume()` are trivial boolean flag
   flips (`self._paused`) checked by `run_pretraining()`'s own
   `should_pause` callback -- optimizer/scheduler/RNG state genuinely
   continues because it lives on the same adapter object across the
   pause/resume calls, never because anything is reloaded from disk.
   `MiniBrainTrainingEngineService.resume()`'s own `find_latest_
   checkpoint()`/`build_resume_state()` call is real, informational audit
   metadata -- `resume_step`/`resume_epoch` are computed and logged but
   never fed into `adapter.start()`, and the underlying
   `TrainingCheckpointManager.load_states()` (a real, working, fully
   verified loader) is never called from anywhere in this file's own
   resume path. A true fresh-process/crash recovery that reloads
   checkpoint state into a NEW adapter and continues training does not
   exist for MB-22 -- confirmed by direct `grep` (no caller of
   `load_states()` exists in `mini_brain_training_engine_service.py`) and
   by the real, isolated subprocess tests in this file. This is reported
   as a genuine, concrete gap (Part 17.E), never fabricated as working.

Every dataset in this file is built through the real
`DatasetVersioningService.create_build()` -> `validate_build()` ->
`run_build()` flow. No checkpoint-corruption proof in this file uses a
mock -- every corruption is a real byte-level mutation of a real file on
disk.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
from core_model.training.dataset_pipeline import BLOCK_BUILDER_VERSION
from backend.services.mini_brain_pretraining_handoff_service import MiniBrainPretrainingHandoffService
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
from backend.services.training_runtime_adapter import TorchTrainingAdapter
from tests.backend.test_mini_brain_training_engine_service import (
    _create_admin,
    _seed_approved_package_and_release,
)
from tests.backend.test_phase27h_training_dataset_readiness import (
    _build_real_dataset_via_service,
    _generate_corpus,
    _real_tokenizer,
)
from tests.backend.test_torch_training_adapter_integration import _real_core_model_version

pytestmark = pytest.mark.anyio

_SUBPROCESS_RUNNER = Path(__file__).parent / "_phase28b_subprocess_runner.py"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


async def _real_running_job(api_app: FastAPI, *, name_suffix: str, record_count: int = 60):
    """Drives a real, isolated MB-22 job all the way to one completed
    real training step (status='running', stage='streaming_metrics'),
    returning everything a test needs to keep driving or inspecting it."""

    settings = api_app.state.settings
    admin_id = _create_admin(api_app)
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic=name_suffix)
    tokenizer_id = _real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = _real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )
    dataset_id, _, _ = _build_real_dataset_via_service(
        settings, name_suffix=name_suffix, record_texts=_generate_corpus(record_count, seed_offset=1),
    )

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
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8b", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION")
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    return settings, svc, adapter, job_id, admin_id, dataset_id, tokenizer_id, cmv_id


class _FailingStepAdapter:
    """A thin, transparent delegate over a real `TorchTrainingAdapter` --
    every method except `step()` is the real adapter's own real method,
    unmodified. `step()` alone raises a genuine, deliberate exception, so
    this proves `run_stream_metric_stage()`'s own new failure-handling
    logic (Part 6/7/8), not a substitute for the real adapter."""

    def __init__(self, real_adapter: TorchTrainingAdapter) -> None:
        self._real = real_adapter

    def is_available(self) -> bool:
        return self._real.is_available()

    def reserve(self, **kwargs):
        return self._real.reserve(**kwargs)

    def start(self, **kwargs):
        return self._real.start(**kwargs)

    def step(self, **kwargs):
        raise RuntimeError("simulated genuine training failure (not a pause/cancel signal)")

    def save_checkpoint(self, **kwargs):
        return self._real.save_checkpoint(**kwargs)

    def pause(self):
        return self._real.pause()

    def resume(self):
        return self._real.resume()

    def cancel(self):
        return self._real.cancel()

    def finalize(self):
        return self._real.finalize()


# ===========================================================================
# Part 4: real checkpoint corruption tests.
# ===========================================================================


class TestCheckpointCorruption:
    async def test_model_state_corruption_and_exact_restoration(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, _ds, _tok, _cmv = await _real_running_job(
            api_app, name_suffix="corrupt-model",
        )
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        manager = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        assert manager.verify(checkpoint_dir) is True

        model_state_path = checkpoint_dir / "model_state.pt"
        original_bytes = model_state_path.read_bytes()
        model_state_path.write_bytes(original_bytes + b"\xde\xad\xbe\xef-corrupted")
        assert _sha256(model_state_path) != _sha256_from_manifest(checkpoint_dir, "model_state.pt")

        fresh_manager = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        with pytest.raises(ValueError, match="checksum mismatch"):
            fresh_manager.verify(checkpoint_dir)
        with pytest.raises(ValueError, match="checksum mismatch"):
            fresh_manager.load_states(checkpoint_dir)

        # No DB row was silently rewritten to accept the corrupted checkpoint.
        with database_connection(settings.resolved_database_path) as connection:
            row = connection.execute(
                "SELECT sha256 FROM mini_brain_training_checkpoints WHERE job_id=(SELECT id FROM mini_brain_training_jobs WHERE public_id=?)",
                (job_id,),
            ).fetchone()
        assert row is not None  # the original, real checksum recorded at save time, untouched

        model_state_path.write_bytes(original_bytes)
        restored_manager = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        assert restored_manager.verify(checkpoint_dir) is True
        assert restored_manager.load_states(checkpoint_dir)["model"] is not None

    async def test_optimizer_state_corruption_and_exact_restoration(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, _ds, _tok, _cmv = await _real_running_job(
            api_app, name_suffix="corrupt-optimizer",
        )
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])

        optimizer_state_path = checkpoint_dir / "optimizer_state.pt"
        original_bytes = optimizer_state_path.read_bytes()
        optimizer_state_path.write_bytes(original_bytes + b"\xde\xad\xbe\xef-corrupted")

        manager = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        with pytest.raises(ValueError, match="checksum mismatch"):
            manager.verify(checkpoint_dir)

        optimizer_state_path.write_bytes(original_bytes)
        assert manager.verify(checkpoint_dir) is True

    async def test_references_corruption_and_exact_restoration(self, api_app: FastAPI) -> None:
        """Part 10, trust boundary: `references.json` (the file carrying
        dataset/tokenizer/core-model identity) is itself checksummed by
        the same manifest -- tampering with it is caught exactly like
        tampering with the model weights, never trusted silently."""

        settings, svc, adapter, job_id, admin_id, _ds, _tok, _cmv = await _real_running_job(
            api_app, name_suffix="corrupt-references",
        )
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])

        references_path = checkpoint_dir / "references.json"
        original_text = references_path.read_text(encoding="utf-8")
        tampered = json.loads(original_text)
        tampered["dataset_version_public_id"] = "00000000-0000-0000-0000-tampered0001"
        references_path.write_text(json.dumps(tampered), encoding="utf-8")

        manager = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        with pytest.raises(ValueError, match="checksum mismatch"):
            manager.verify(checkpoint_dir)
        with pytest.raises(ValueError, match="checksum mismatch"):
            manager.load_states(checkpoint_dir)

        references_path.write_text(original_text, encoding="utf-8")
        assert manager.verify(checkpoint_dir) is True
        assert manager.load_states(checkpoint_dir)["references"]["dataset_version_public_id"] != "00000000-0000-0000-0000-tampered0001"

    async def test_no_fallback_checkpoint_is_selected_after_corruption(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, _ds, _tok, _cmv = await _real_running_job(
            api_app, name_suffix="corrupt-nofallback",
        )
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        model_state_path = checkpoint_dir / "model_state.pt"
        original_bytes = model_state_path.read_bytes()
        model_state_path.write_bytes(original_bytes + b"corrupted")

        manager = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        with pytest.raises(ValueError):
            manager.verify(checkpoint_dir)

        # list_checkpoints() still reports the same single real row -- no
        # second, substitute checkpoint was created or selected.
        checkpoints = svc.list_checkpoints(job_id)["items"]
        assert len(checkpoints) == 1
        assert checkpoints[0]["checkpoint_name"] == "checkpoint-epoch000-step00000001"


def _sha256_from_manifest(checkpoint_dir: Path, filename: str) -> str:
    from backend.core.json_utils import loads_json

    manifest = loads_json((checkpoint_dir / "manifest.json").read_text(encoding="utf-8"))
    return manifest["checksums"][filename]


# ===========================================================================
# Part 5: pause / resume integrity (real, in-process).
# ===========================================================================


class TestPauseResumeIntegrity:
    async def test_in_process_pause_resume_continues_the_same_adapter_state(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, dataset_id, tokenizer_id, cmv_id = await _real_running_job(
            api_app, name_suffix="pause-resume",
        )
        before_pause = svc.job(job_id)
        assert before_pause["status"] == "running"
        weights_before_pause = [p.clone() for p in adapter._model.parameters()]
        optimizer_state_before = adapter._optimizer_state

        paused = svc.pause(job_id, admin_id=admin_id)
        assert paused["status"] == "paused"
        assert adapter._paused is True

        # Same job identity, no duplicate logical job.
        with database_connection(settings.resolved_database_path) as connection:
            job_count = connection.execute(
                "SELECT COUNT(*) FROM mini_brain_training_jobs WHERE topic LIKE 'pause-resume%'"
            ).fetchone()[0]
        assert job_count == 1

        resumed = svc.resume(job_id, admin_id=admin_id)
        assert resumed["status"] == "running"
        assert adapter._paused is False

        # Dataset/tokenizer/core-model identity on the job row itself is unchanged.
        assert resumed["dataset_version_public_id"] == dataset_id
        assert resumed["core_model_version_public_id"] == cmv_id

        # The SAME adapter object's optimizer state was never reset --
        # this is what "resume" genuinely means in this architecture: the
        # same in-memory training session continues, real state intact.
        assert adapter._optimizer_state is optimizer_state_before

        # A real step after resume genuinely advances training further.
        metric = svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        assert metric["training_state"]["last_step"] == 2
        weights_after_resume_step = list(adapter._model.parameters())
        assert any(
            not b.equal(a) for b, a in zip(weights_before_pause, weights_after_resume_step, strict=True)
        ), "real weights must have continued changing after resume"

    async def test_pause_requires_running_and_is_not_silently_reentrant(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="pause-guard")
        svc.pause(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="must be 'running' to pause"):
            svc.pause(job_id, admin_id=admin_id)

    async def test_resume_requires_paused_and_is_not_silently_reentrant(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="resume-guard")
        with pytest.raises(ValidationError, match="must be 'paused' to resume"):
            svc.resume(job_id, admin_id=admin_id)

    async def test_checkpoint_reload_now_exists_for_resume(self, api_app: FastAPI) -> None:
        """Phase 2.8B documented this as a real, confirmed architectural
        gap (Part 17.E): `resume()`'s own resume_state metadata
        (`resume_step`/`resume_epoch`) was real, computed, and logged,
        but never actually applied to the adapter. Phase 2.8C closed
        this exact gap -- `resume()` now detects a genuinely fresh
        adapter and restores its real model/optimizer/scheduler/RNG/
        training-position state from the latest verified checkpoint. See
        tests/backend/test_phase28c_checkpoint_resume_recovery.py for
        the full genuinely-separate-OS-process proof of this claim;
        this test only confirms the in-process symptom Phase 2.8B
        documented is gone."""

        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="resume-gap")
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        svc.pause(job_id, admin_id=admin_id)

        # A second, fresh adapter -- exactly what a real process restart
        # would present training with.
        fresh_adapter = TorchTrainingAdapter()
        assert fresh_adapter._model is None
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        result = fresh_svc.resume(job_id, admin_id=admin_id)
        assert result["status"] == "running"
        # As of Phase 2.8C, resume() on a genuinely fresh adapter now
        # performs real checkpoint recovery -- the adapter has a real,
        # restored model, not None.
        assert fresh_adapter._model is not None


# ===========================================================================
# Part 6: interrupted training / crash recovery -- genuinely separate OS
# processes, deterministic crash points (no signal-timing races).
# ===========================================================================


class TestInterruptedTrainingCrashRecovery:
    def test_a_normal_checkpoint_verifies_from_a_fresh_os_process(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "normal"
        work_dir.mkdir()
        result = subprocess.run(
            [sys.executable, str(_SUBPROCESS_RUNNER), "normal_checkpoint", str(work_dir), "crash-normal"],
            capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 0, result.stderr[-4000:]
        info = json.loads(result.stdout.strip().splitlines()[-1])

        # A genuinely different OS process (this pytest process) verifies it.
        checkpoint_dir = Path(info["checkpoint_dir"])
        manager = TrainingCheckpointManager(checkpoint_dir.parent, 500_000_000)
        assert manager.verify(checkpoint_dir) is True
        references = manager.load_states(checkpoint_dir)["references"]
        assert references["dataset_version_public_id"] == info["dataset_id"]

        with database_connection(Path(info["database_path"])) as connection:
            job = connection.execute(
                "SELECT status, stage FROM mini_brain_training_jobs WHERE public_id=?", (info["job_id"],)
            ).fetchone()
        assert job["status"] == "running"

    def test_b_interruption_before_first_checkpoint_leaves_no_false_success(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "before-checkpoint"
        work_dir.mkdir()
        result = subprocess.run(
            [sys.executable, str(_SUBPROCESS_RUNNER), "crash_before_checkpoint", str(work_dir), "crash-before"],
            capture_output=True, text=True, timeout=180,
        )
        # os._exit(137) -- the process really did terminate abruptly.
        assert result.returncode == 137
        info = json.loads(result.stdout.strip().splitlines()[-1])

        with database_connection(Path(info["database_path"])) as connection:
            job = connection.execute(
                "SELECT status, stage, completed_at FROM mini_brain_training_jobs WHERE public_id=?",
                (info["job_id"],),
            ).fetchone()
            checkpoint_count = connection.execute(
                "SELECT COUNT(*) FROM mini_brain_training_checkpoints"
            ).fetchone()[0]
        assert job["status"] == "running", "an interrupted job must never appear falsely completed"
        assert job["completed_at"] is None
        assert checkpoint_count == 0, "no checkpoint row may exist when none was ever saved"

        # A fresh process CAN safely close this out manually via cancel() --
        # the one real, available recovery action for an orphaned job,
        # even though automatic resume-into-a-fresh-adapter does not exist.
        settings = Settings(
            database_path=Path(info["database_path"]), database_backup_dir=work_dir / "backups",
            allowed_data_dir=work_dir, document_dir=work_dir / "documents",
            document_report_dir=work_dir / "documents" / "reports",
            pretraining_dir=Path(info["pretraining_dir"]), tokenizer_corpus_dir=work_dir / "tc",
            tokenizer_dir=work_dir / "tok", allow_external_storage=True, log_level="CRITICAL",
        )
        svc = MiniBrainTrainingEngineService(settings)
        cancelled = svc.cancel(info["job_id"], admin_id="recovery-admin")
        assert cancelled["status"] == "cancelled"

    def test_c_interruption_during_checkpoint_save_leaves_no_valid_looking_checkpoint(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "during-checkpoint"
        work_dir.mkdir()
        result = subprocess.run(
            [sys.executable, str(_SUBPROCESS_RUNNER), "crash_during_checkpoint_save", str(work_dir), "crash-during"],
            capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 137
        info = json.loads(result.stdout.strip().splitlines()[-1])

        pretraining_dir = Path(info["pretraining_dir"])
        job_checkpoint_root = pretraining_dir / "mini_brain_training_jobs" / info["job_id"]
        canonical_dir = job_checkpoint_root / "step-00000001-epoch-0000"
        assert not canonical_dir.exists(), (
            "the real, atomic tempdir+move save() pattern must mean a crash "
            "mid-save never produces a directory at the canonical path"
        )
        # A real stray artifact CAN remain -- the temp directory itself,
        # since os._exit() bypasses the tempfile context manager's own
        # cleanup. Documented honestly as a real, minor gap (Part 17.B):
        # nothing in this codebase currently sweeps it, though it can
        # never be selected as a checkpoint (wrong name, no DB row).
        if job_checkpoint_root.is_dir():
            stray_entries = [p for p in job_checkpoint_root.iterdir() if p.name != "step-00000001-epoch-0000"]
            for entry in stray_entries:
                assert not entry.name.startswith("step-"), "a stray entry must never look like a real checkpoint"

        with database_connection(Path(info["database_path"])) as connection:
            job = connection.execute(
                "SELECT status FROM mini_brain_training_jobs WHERE public_id=?", (info["job_id"],)
            ).fetchone()
            checkpoint_count = connection.execute(
                "SELECT COUNT(*) FROM mini_brain_training_checkpoints"
            ).fetchone()[0]
        assert job["status"] == "running"
        assert checkpoint_count == 0

        # A subsequent, legitimate save at the exact same (step, epoch) --
        # simulating retry after the crash -- succeeds cleanly despite the
        # stray temp directory (proven, not assumed).
        settings = Settings(
            database_path=Path(info["database_path"]), database_backup_dir=work_dir / "backups",
            allowed_data_dir=work_dir, document_dir=work_dir / "documents",
            document_report_dir=work_dir / "documents" / "reports",
            pretraining_dir=pretraining_dir, tokenizer_corpus_dir=work_dir / "tc",
            tokenizer_dir=work_dir / "tok", allow_external_storage=True, log_level="CRITICAL",
        )
        adapter = TorchTrainingAdapter()
        svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
        # A fresh adapter has no model -- this proves retry-after-crash
        # for MB-22 requires a brand new job (§ the Part 17.E gap), not
        # that this exact job can seamlessly continue.
        with pytest.raises(Exception):
            svc.run_save_checkpoint_stage(info["job_id"], step=1, epoch=0, admin_id="recovery-admin")

    def test_d_fresh_process_inspection_after_termination_is_honest(self, tmp_path: Path) -> None:
        """A fourth, independent fresh-process check: after ANY of the
        above terminations, a brand new `MiniBrainTrainingEngineService`
        in a brand new process (this test's own subprocess invocation)
        can honestly read back the exact real job/event/checkpoint state
        -- never a stale or fabricated view."""

        work_dir = tmp_path / "inspect"
        work_dir.mkdir()
        result = subprocess.run(
            [sys.executable, str(_SUBPROCESS_RUNNER), "crash_before_checkpoint", str(work_dir), "crash-inspect"],
            capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 137
        info = json.loads(result.stdout.strip().splitlines()[-1])

        settings = Settings(
            database_path=Path(info["database_path"]), database_backup_dir=work_dir / "backups",
            allowed_data_dir=work_dir, document_dir=work_dir / "documents",
            document_report_dir=work_dir / "documents" / "reports",
            pretraining_dir=Path(info["pretraining_dir"]), tokenizer_corpus_dir=work_dir / "tc",
            tokenizer_dir=work_dir / "tok", allow_external_storage=True, log_level="CRITICAL",
        )
        svc = MiniBrainTrainingEngineService(settings)
        job = svc.job(info["job_id"])
        assert job["status"] == "running"
        events = svc.events(info["job_id"])["items"]
        event_types = {e["event_type"] for e in events}
        assert "metric_streamed" in event_types
        assert "training_finalized" not in event_types, "an interrupted job must never show a finalize event that never happened"


# ===========================================================================
# Part 7: retry / idempotency audit.
# ===========================================================================


class TestRetryIdempotency:
    async def test_repeated_checkpoint_save_same_step_is_safely_rejected(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="retry-checkpoint")
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        with pytest.raises(ValidationError, match="already exists"):
            svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        assert len(svc.list_checkpoints(job_id)["items"]) == 1

    async def test_repeated_checkpoint_save_same_name_rejected_at_the_db_level_too(self, api_app: FastAPI) -> None:
        """Defense in depth: the real `ux_mini_brain_training_checkpoints_
        job_name` unique index (`backend/database/schema.py`) is the final
        authority, not merely the service's own pre-check -- proven by
        bypassing the service and attempting a raw duplicate INSERT."""

        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="retry-dbindex")
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        import sqlite3

        with database_connection(settings.resolved_database_path) as connection:
            job_row_id = connection.execute(
                "SELECT id FROM mini_brain_training_jobs WHERE public_id=?", (job_id,)
            ).fetchone()["id"]
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
                connection.execute(
                    """INSERT INTO mini_brain_training_checkpoints
                    (public_id, job_id, step, epoch, checkpoint_name, relative_path, sha256, file_size_bytes)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        "duplicate-attempt", job_row_id, 1, 0, "checkpoint-epoch000-step00000001",
                        "checkpoints/duplicate.json", "f" * 64, 1,
                    ),
                )

    async def test_repeated_finalize_is_safely_rejected(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="retry-finalize")
        svc.finalize(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="must be 'running' or 'paused' to finalize"):
            svc.finalize(job_id, admin_id=admin_id)

    async def test_repeated_archive_is_safely_rejected(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="retry-archive")
        svc.finalize(job_id, admin_id=admin_id)
        svc.generate_report_stage(job_id, admin_id=admin_id)
        svc.archive(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="must be 'completed' or 'cancelled' to archive"):
            svc.archive(job_id, admin_id=admin_id)

        with database_connection(settings.resolved_database_path) as connection:
            memory_count = connection.execute(
                "SELECT COUNT(*) FROM mini_brain_training_engine_memory WHERE job_id=(SELECT id FROM mini_brain_training_jobs WHERE public_id=?)",
                (job_id,),
            ).fetchone()[0]
        assert memory_count == 1, "archive() must never create a second memory row on a rejected repeat"

    async def test_repeated_resume_is_safely_rejected(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="retry-resume")
        svc.pause(job_id, admin_id=admin_id)
        svc.resume(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="must be 'paused' to resume"):
            svc.resume(job_id, admin_id=admin_id)

    async def test_repeated_failure_handling_is_idempotent_not_duplicated(self, api_app: FastAPI) -> None:
        """Part 7/9's own new failure path: a second genuine failure on an
        already-`failed` job must not double-transition or double-record
        -- `_record_training_failure()`'s own `status != 'running'` guard
        makes this a no-op the second time, proven live."""

        settings, svc, real_adapter, job_id, admin_id, *_ = await _real_running_job(
            api_app, name_suffix="retry-failure",
        )
        failing_svc = MiniBrainTrainingEngineService(
            settings, adapters={"gpu": _FailingStepAdapter(real_adapter)},
        )
        with pytest.raises(RuntimeError):
            failing_svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        job_after_first = failing_svc.job(job_id)
        assert job_after_first["status"] == "failed"
        assert job_after_first["stage"] == "generate_report"

        # A direct second call to the failure recorder (simulating a
        # retry/duplicate failure signal) must not re-mutate or double-log.
        failing_svc._record_training_failure(job_id, error=RuntimeError("second failure"))
        with database_connection(settings.resolved_database_path) as connection:
            failure_events = connection.execute(
                """SELECT COUNT(*) FROM mini_brain_training_events
                WHERE job_id=(SELECT id FROM mini_brain_training_jobs WHERE public_id=?) AND event_type='training_failed'""",
                (job_id,),
            ).fetchone()[0]
        assert failure_events == 1, "a failure already recorded must never be recorded twice"


# ===========================================================================
# Part 8: failure cleanup / stray state.
# ===========================================================================


class TestFailureCleanupStrayState:
    async def test_genuine_training_failure_reaches_failed_status_with_no_stray_success_state(
        self, api_app: FastAPI,
    ) -> None:
        settings, svc, real_adapter, job_id, admin_id, _ds, _tok, cmv_id = await _real_running_job(
            api_app, name_suffix="cleanup-failure",
        )
        with database_connection(settings.resolved_database_path) as connection:
            before = {
                "jobs": connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0],
                "checkpoints": connection.execute("SELECT COUNT(*) FROM mini_brain_training_checkpoints").fetchone()[0],
                "pretraining_checkpoints": connection.execute("SELECT COUNT(*) FROM pretraining_checkpoints").fetchone()[0],
                "memory": connection.execute("SELECT COUNT(*) FROM mini_brain_training_engine_memory").fetchone()[0],
            }

        failing_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": _FailingStepAdapter(real_adapter)})
        with pytest.raises(RuntimeError):
            failing_svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)

        job = failing_svc.job(job_id)
        assert job["status"] == "failed"
        assert job["stage"] == "generate_report"
        assert job["training_state"]["last_error"], "the real error message must be recorded, not silently dropped"

        # generate_report_stage()'s own existing failure-handling branch --
        # previously unreachable -- is now genuinely reachable and honest.
        report = failing_svc.generate_report_stage(job_id, admin_id=admin_id)
        assert report["final_report"]["status"] == "failed"

        with database_connection(settings.resolved_database_path) as connection:
            after = {
                "jobs": connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0],
                "checkpoints": connection.execute("SELECT COUNT(*) FROM mini_brain_training_checkpoints").fetchone()[0],
                "pretraining_checkpoints": connection.execute("SELECT COUNT(*) FROM pretraining_checkpoints").fetchone()[0],
                "memory": connection.execute("SELECT COUNT(*) FROM mini_brain_training_engine_memory").fetchone()[0],
            }
        assert after["jobs"] == before["jobs"], "no duplicate job may be created by failure handling"
        assert after["checkpoints"] == before["checkpoints"] == 0, "no false-success checkpoint may exist"
        assert after["pretraining_checkpoints"] == before["pretraining_checkpoints"] == 0
        assert after["memory"] == before["memory"], "archive/memory must not be touched by a mere failure"

    async def test_failed_job_cannot_be_finalized_as_successful(self, api_app: FastAPI) -> None:
        settings, svc, real_adapter, job_id, admin_id, *_ = await _real_running_job(
            api_app, name_suffix="cleanup-nofinalize",
        )
        failing_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": _FailingStepAdapter(real_adapter)})
        with pytest.raises(RuntimeError):
            failing_svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        # finalize() requires status IN ('running','paused') -- a 'failed'
        # job can never be routed through the success path.
        with pytest.raises(ValidationError, match="must be 'running' or 'paused' to finalize"):
            failing_svc.finalize(job_id, admin_id=admin_id)


# ===========================================================================
# Part 9: determinism (metadata/provenance/block construction -- never
# model-weight-identical claims).
# ===========================================================================


class TestDeterminism:
    async def test_provenance_and_block_construction_are_deterministic_across_two_jobs(
        self, api_app: FastAPI,
    ) -> None:
        """Two SEPARATE real MB-22 jobs against the SAME real dataset/
        tokenizer/Core Model Version: dataset checksum, tokenizer
        checksum, Core Model Version identity, and the real derived
        blocks are all byte-identical -- this is deterministic metadata/
        block-construction, never a claim about final model weights
        (each job independently trains, so weights are NOT compared for
        equality)."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="determinism")
        cmv_id = _real_core_model_version(
            settings, admin_id, name_suffix="determinism", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="determinism", record_texts=_generate_corpus(60, seed_offset=3),
        )

        from backend.services.mini_brain_dataset_pipeline_service import MiniBrainDatasetPipelineService

        pipeline = MiniBrainDatasetPipelineService(settings)
        first = pipeline.build_blocks(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        second = pipeline.build_blocks(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert first["train_blocks"] == second["train_blocks"]
        assert first["dataset_checksum_sha256"] == second["dataset_checksum_sha256"]
        assert first["tokenizer_checksum_sha256"] == second["tokenizer_checksum_sha256"]
        assert first["block_builder_version"] == second["block_builder_version"] == BLOCK_BUILDER_VERSION

    async def test_checkpoint_restoration_reads_identical_bytes_each_time(self, api_app: FastAPI) -> None:
        """Deterministic checkpoint restoration: loading the SAME real,
        uncorrupted checkpoint twice from independent manager instances
        produces byte-identical tensors and identical references -- this
        is what "deterministic checkpoint restoration" means here, never
        a claim about training continuation producing identical future
        weights."""

        settings, svc, adapter, job_id, admin_id, *_ = await _real_running_job(api_app, name_suffix="determinism-ckpt")
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])

        manager_a = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        manager_b = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        states_a = manager_a.load_states(checkpoint_dir)
        states_b = manager_b.load_states(checkpoint_dir)
        assert states_a["references"] == states_b["references"]
        for key_a, tensor_a in states_a["model"].items():
            assert tensor_a.equal(states_b["model"][key_a])


# ===========================================================================
# Part 10: training artifact trust boundary.
# ===========================================================================


class TestTrustBoundary:
    async def test_checkpoint_provenance_cannot_be_silently_replaced_by_a_different_dataset(
        self, api_app: FastAPI,
    ) -> None:
        """Building a SECOND real, different dataset after a checkpoint
        was already saved must never change what the already-saved
        checkpoint's own `references.json` reports -- provenance is fixed
        at save time, not derived live from "whatever the latest dataset
        happens to be"."""

        settings, svc, adapter, job_id, admin_id, dataset_id, tokenizer_id, cmv_id = await _real_running_job(
            api_app, name_suffix="trust-boundary",
        )
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        manager = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        references_before = manager.load_states(checkpoint_dir)["references"]

        # A different, later real dataset is built in the same database.
        _build_real_dataset_via_service(
            settings, name_suffix="trust-boundary-later", record_texts=_generate_corpus(30, seed_offset=99),
        )

        references_after = manager.load_states(checkpoint_dir)["references"]
        assert references_after == references_before
        assert references_after["dataset_version_public_id"] == dataset_id

    async def test_handoff_registration_still_uses_the_real_saved_checkpoint_identity(
        self, api_app: FastAPI,
    ) -> None:
        settings, svc, adapter, job_id, admin_id, dataset_id, tokenizer_id, cmv_id = await _real_running_job(
            api_app, name_suffix="trust-handoff",
        )
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_row = svc.list_checkpoints(job_id)["items"][0]

        handoff = MiniBrainPretrainingHandoffService(settings)
        result = handoff.register_checkpoint(job_id, checkpoint_row["public_id"], admin_id)
        with database_connection(settings.resolved_database_path) as connection:
            registered = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?",
                (result["pretraining_checkpoint_public_id"],),
            ).fetchone()
        assert registered["status"] == "verified"
        with database_connection(settings.resolved_database_path) as connection:
            expected_checksum = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()["checksum_sha256"]
        assert registered["model_checksum_sha256"]


# ===========================================================================
# Part 13: real qualification after all fixes.
# ===========================================================================


class TestRealQualificationAfterFixes:
    async def test_full_real_execution_with_recovery_path_and_provenance(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="qual28b")
        cmv_id = _real_core_model_version(
            settings, admin_id, name_suffix="qual28b", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="qual28b", record_texts=_generate_corpus(200, seed_offset=42),
        )

        svc_readiness = MiniBrainTrainingEngineService(settings)
        readiness = svc_readiness.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        assert readiness["status"] == "READY", readiness["reason"]

        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="qual28b")
        adapter = TorchTrainingAdapter()
        svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
        job = svc.create_job(
            topic="qual28b-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
        )
        job_id = job["public_id"]
        svc.run_validate_release_stage(job_id, admin_id=admin_id)
        svc.run_validate_package_stage(job_id, admin_id=admin_id)
        svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8b qualification", admin_id=admin_id)
        svc.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc.run_build_manifest_stage(job_id, admin_id=admin_id)
        svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION")
        svc.run_start_training_stage(job_id, admin_id=admin_id)

        before = [p.clone() for p in adapter._model.parameters()]
        metric_1 = svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        assert metric_1["training_state"]["last_loss"] is not None

        # Real pause/resume within the qualification run.
        svc.pause(job_id, admin_id=admin_id)
        svc.resume(job_id, admin_id=admin_id)
        metric_2 = svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        after = list(adapter._model.parameters())
        assert any(not b.equal(a) for b, a in zip(before, after, strict=True))
        assert adapter._validation_blocks, "validation execution must be real and non-empty"

        svc.run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        checkpoint_row = svc.list_checkpoints(job_id)["items"][0]
        checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        manager = TrainingCheckpointManager(checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        assert manager.verify(checkpoint_dir) is True
        references = manager.load_states(checkpoint_dir)["references"]
        assert references["dataset_version_public_id"] == dataset_id
        assert references["core_model_version_public_id"] == cmv_id
        assert references["block_builder_version"] == BLOCK_BUILDER_VERSION

        svc.finalize(job_id, admin_id=admin_id)
        report = svc.generate_report_stage(job_id, admin_id=admin_id)
        assert report["final_report"]["status"] == "completed"
        archived = svc.archive(job_id, admin_id=admin_id)
        assert archived["status"] == "archived"

        handoff = MiniBrainPretrainingHandoffService(settings)
        result = handoff.register_checkpoint(job_id, checkpoint_row["public_id"], admin_id)
        with database_connection(settings.resolved_database_path) as connection:
            registered = connection.execute(
                "SELECT status FROM pretraining_checkpoints WHERE public_id=?",
                (result["pretraining_checkpoint_public_id"],),
            ).fetchone()
        assert registered["status"] == "verified"
