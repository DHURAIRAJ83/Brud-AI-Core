"""Phase 2.8C: Checkpoint-Based Process-Restart Recovery.

Phase 2.8B proved MB-22's `pause()`/`resume()` was real but strictly
in-process: `TrainingCheckpointManager.load_states()` existed, was fully
verified, and was never called from anywhere in
`mini_brain_training_engine_service.py`. A genuinely fresh
`TorchTrainingAdapter` (no live model) passed to `resume()` would return
a normal-looking `status='running'` response while its own `_model`
stayed `None` -- no real recovery occurred.

This phase closes that exact gap with the smallest change the mission
allows: `resume()` itself now detects whether the adapter it has been
given is a genuinely fresh, unconfigured `TorchTrainingAdapter`
(`adapter._model is None`) for a real (`execution_mode='gpu'`) job. If
so, it calls a new `_recover_adapter_from_checkpoint()` helper, which:

1. resolves the latest checkpoint's real, on-disk pointer file, confined
   to this job's own real checkpoint root (never an arbitrary path);
2. calls the real, unmodified `TrainingCheckpointManager.load_states()`,
   which fails closed on any checksum mismatch;
3. cross-checks the checkpoint's own recorded identity
   (`references.json`) against THIS job's own live
   `dataset_version_public_id`/`core_model_version_public_id` -- never
   trusting a checkpoint merely because it is attached to this job's own
   checkpoint list;
4. re-derives real train/validation blocks via the unmodified
   `MiniBrainDatasetPipelineService.build_blocks()` and cross-checks the
   real, live dataset/tokenizer checksums against what the checkpoint
   itself recorded;
5. constructs a real `BrudForCausalLM`, loads its real weights via
   `load_state_dict()`, and calls the new
   `TorchTrainingAdapter.restore_from_checkpoint()` to place the fully
   real, restored state (model, optimizer, scheduler, RNG, completed-step
   counter) onto the adapter.

An already-configured, same-process adapter (Phase 2.8B's own tested
case) is completely untouched by this new branch and continues to use
the existing `adapter.resume()` flag-flip exactly as before.

The core recovery claim in this file is proven via genuinely separate OS
processes (`tests/backend/_phase28c_subprocess_runner.py`), never same-
process test doubles.
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
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
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

_SUBPROCESS_RUNNER = Path(__file__).parent / "_phase28c_subprocess_runner.py"


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


def _run_subprocess(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(_SUBPROCESS_RUNNER), *args], capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


async def _real_paused_job_with_checkpoint(api_app: FastAPI, *, name_suffix: str, hidden_size: int = 16, intermediate_size: int = 32):
    """Same-process helper (used only for tests that are explicitly
    NOT about the core cross-process recovery claim -- identity checks,
    checkpoint selection, idempotency, security). Drives a real job to
    `status='paused'` with exactly one real checkpoint already saved."""

    settings = api_app.state.settings
    admin_id = _create_admin(api_app, username=f"admin-{name_suffix}")
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic=name_suffix)
    tokenizer_id = _real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = _real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
        hidden_size=hidden_size, intermediate_size=intermediate_size,
    )
    dataset_id, _, _ = _build_real_dataset_via_service(
        settings, name_suffix=name_suffix, record_texts=_generate_corpus(60, seed_offset=1),
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
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8c", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION")
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.pause(job_id, admin_id=admin_id)
    return settings, svc, adapter, job_id, admin_id, dataset_id, tokenizer_id, cmv_id


class _FailingStepAdapter:
    """Delegates every method to a real `TorchTrainingAdapter` except
    `step()`, which raises a deliberate failure -- proves Phase 2.8B's
    failure-handling path still works after Phase 2.8C's recovery."""

    def __init__(self, real_adapter: TorchTrainingAdapter) -> None:
        self._real = real_adapter

    def is_available(self):
        return self._real.is_available()

    def reserve(self, **kwargs):
        return self._real.reserve(**kwargs)

    def start(self, **kwargs):
        return self._real.start(**kwargs)

    def step(self, **kwargs):
        raise RuntimeError("simulated genuine training failure after recovery")

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

    @property
    def _model(self):
        return self._real._model

    @property
    def _optimizer_state(self):
        return self._real._optimizer_state

    @property
    def _completed_steps(self):
        return self._real._completed_steps


# ===========================================================================
# The core claim: genuine fresh-process checkpoint recovery.
# ===========================================================================


class TestFreshProcessRecovery:
    def test_train_checkpoint_pause_then_fresh_process_recovers_and_continues(self, tmp_path: Path) -> None:
        """Parts 6.A-I in one, real, two-genuinely-separate-OS-process
        proof: process 1 trains, checkpoints, and pauses; process 2 --
        which has never shared any Python object with process 1 -- is
        constructed fresh, resumes, and is proven to have really
        restored model/optimizer/training-position state, to really
        execute a further training step with real weight change, and to
        really save and verify a further checkpoint whose provenance
        still names the original dataset/tokenizer/Core Model."""

        work_dir = tmp_path / "fresh"
        work_dir.mkdir()
        before = _run_subprocess("train_checkpoint_pause", str(work_dir), "recover28c")
        assert before["completed_steps"] == 1

        after = _run_subprocess("recover_and_continue", str(work_dir), before["job_id"], "true")
        # B: a fresh process's adapter genuinely started with no model.
        assert after["model_was_none_before_recovery"] is True
        assert after["recovery_succeeded"] is True
        assert after["resume_status"] == "running"
        # C: after restoration, weights are bit-for-bit identical to what
        # was saved (SHA-256 over every real parameter tensor's raw bytes).
        assert after["model_restored"] is True
        assert after["restored_model_weights_sha256"] == before["model_weights_sha256"]
        # D: the training-position counter, not merely "some" state.
        assert after["completed_steps_after_recovery"] == before["completed_steps"] == 1
        # D: optimizer state was restored (real, non-empty Adam moment
        # buffers), not recreated from scratch (a fresh optimizer would
        # never have been loaded from anything).
        assert after["optimizer_state_restored"] is True
        # F/G: a real resumed step executed and real weights changed.
        assert after["resumed_step_loss"] is not None
        assert after["weights_changed_after_resumed_step"] is True
        # H: a new checkpoint was created and independently verified.
        assert after["checkpoint_count_after_recovery"] == 2
        assert after["new_checkpoint_verified"] is True
        # I: provenance remains tied to the ORIGINAL dataset/Core Model.
        assert after["new_checkpoint_dataset_id"] == before["dataset_id"]
        assert after["new_checkpoint_core_model_id"] == before["cmv_id"]
        # No duplicate job row was created by recovery.
        assert after["job_row_count"] == 1


# ===========================================================================
# Part 7: a job with no checkpoint cannot magically resume.
# ===========================================================================


class TestNoCheckpointRecovery:
    def test_fresh_process_cannot_recover_a_job_with_no_checkpoint(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "nocheckpoint"
        work_dir.mkdir()
        # A subprocess mode that trains one step, pauses, but never saves
        # a checkpoint -- reusing the existing Phase 2.8B crash_before_checkpoint
        # style is unnecessary here since we want a clean pause (not a
        # crash) with genuinely zero checkpoints; drive it directly.
        settings_script = f"""
import sys, json, asyncio
sys.path.insert(0, {str(Path(__file__).parent.parent.parent)!r})
sys.path.insert(0, {str(Path(__file__).parent)!r})
from pathlib import Path
from backend.core.config import Settings
from backend.database.migrations import initialize_database
tmp = Path({str(work_dir)!r})
settings = Settings(database_path=tmp/"api.db", database_backup_dir=tmp/"backups", allowed_data_dir=tmp,
    document_dir=tmp/"documents", document_report_dir=tmp/"documents"/"reports",
    pretraining_dir=tmp/"core_models"/"pretraining", tokenizer_corpus_dir=tmp/"tc", tokenizer_dir=tmp/"tok",
    allow_external_storage=True, log_level="CRITICAL")
initialize_database(settings.resolved_database_path)
import importlib
mod_h = importlib.import_module("test_phase27h_training_dataset_readiness")
mod_adapter = importlib.import_module("test_torch_training_adapter_integration")
mod_svc = importlib.import_module("test_mini_brain_training_engine_service")
from backend.main import create_app
app = create_app(settings)
admin_id = mod_svc._create_admin(app)
tokenizer_id = mod_h._real_tokenizer(settings, name_suffix="nockpt")
cmv_id = mod_adapter._real_core_model_version(settings, admin_id, name_suffix="nockpt", tokenizer_version_public_id=tokenizer_id)
dataset_id, _, _ = mod_h._build_real_dataset_via_service(settings, name_suffix="nockpt", record_texts=mod_h._generate_corpus(60, seed_offset=1))
tp_id, rg_id = asyncio.run(mod_svc._seed_approved_package_and_release(app, admin_id, topic="nockpt"))
from backend.services.training_runtime_adapter import TorchTrainingAdapter
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
adapter = TorchTrainingAdapter()
svc = MiniBrainTrainingEngineService(settings, adapters={{"gpu": adapter}})
job = svc.create_job(topic="nockpt-job", training_package_session_public_id=tp_id, release_governance_session_public_id=rg_id,
    execution_mode="gpu", admin_id=admin_id, core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id)
job_id = job["public_id"]
svc.run_validate_release_stage(job_id, admin_id=admin_id)
svc.run_validate_package_stage(job_id, admin_id=admin_id)
svc.run_validate_authorization_stage(job_id, authorization_reason="r", admin_id=admin_id)
svc.run_plan_resources_stage(job_id, admin_id=admin_id)
svc.run_build_manifest_stage(job_id, admin_id=admin_id)
svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION")
svc.run_start_training_stage(job_id, admin_id=admin_id)
svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
svc.pause(job_id, admin_id=admin_id)
print(json.dumps({{"job_id": job_id, "database_path": str(settings.resolved_database_path)}}))
"""
        result = subprocess.run([sys.executable, "-c", settings_script], capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stderr[-4000:]
        info = json.loads(result.stdout.strip().splitlines()[-1])

        recovered = _run_subprocess("recover_and_continue", str(work_dir), info["job_id"], "false")
        assert recovered["recovery_succeeded"] is False
        assert "no checkpoint exists" in recovered["error"]
        assert recovered["error_type"] == "ValidationError"

        # No fallback checkpoint was fabricated; no different job was
        # silently started; the job's own status remains genuinely 'paused'.
        with database_connection(Path(info["database_path"])) as connection:
            job_row = connection.execute(
                "SELECT status FROM mini_brain_training_jobs WHERE public_id=?", (info["job_id"],)
            ).fetchone()
            job_count = connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0]
            checkpoint_count = connection.execute("SELECT COUNT(*) FROM mini_brain_training_checkpoints").fetchone()[0]
        assert job_row["status"] == "paused"
        assert job_count == 1
        assert checkpoint_count == 0


# ===========================================================================
# Part 8: real byte-level corruption -- every materially important file.
# ===========================================================================


class TestCorruptedCheckpointRecovery:
    def test_corrupted_model_state_fails_closed_then_exact_restoration_recovers(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "corrupt-model"
        work_dir.mkdir()
        before = _run_subprocess("train_checkpoint_pause", str(work_dir), "corruptmodel")

        checkpoint_dir = self._checkpoint_dir(work_dir, before["job_id"])
        model_path = checkpoint_dir / "model_state.pt"
        original_bytes = model_path.read_bytes()
        model_path.write_bytes(original_bytes + b"\xde\xad\xbe\xef-corrupted")

        rejected = _run_subprocess("recover_and_continue", str(work_dir), before["job_id"], "false")
        assert rejected["recovery_succeeded"] is False
        assert "checksum mismatch" in rejected["error"]

        model_path.write_bytes(original_bytes)
        recovered = _run_subprocess("recover_and_continue", str(work_dir), before["job_id"], "true")
        assert recovered["recovery_succeeded"] is True
        assert recovered["restored_model_weights_sha256"] == before["model_weights_sha256"]

    def test_corrupted_optimizer_state_fails_closed_then_exact_restoration_recovers(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "corrupt-optimizer"
        work_dir.mkdir()
        before = _run_subprocess("train_checkpoint_pause", str(work_dir), "corruptopt")

        checkpoint_dir = self._checkpoint_dir(work_dir, before["job_id"])
        optimizer_path = checkpoint_dir / "optimizer_state.pt"
        original_bytes = optimizer_path.read_bytes()
        optimizer_path.write_bytes(original_bytes + b"\xde\xad\xbe\xef-corrupted")

        rejected = _run_subprocess("recover_and_continue", str(work_dir), before["job_id"], "false")
        assert rejected["recovery_succeeded"] is False
        assert "checksum mismatch" in rejected["error"]

        optimizer_path.write_bytes(original_bytes)
        recovered = _run_subprocess("recover_and_continue", str(work_dir), before["job_id"], "true")
        assert recovered["recovery_succeeded"] is True
        assert recovered["optimizer_state_restored"] is True

    def test_corrupted_references_fails_closed_then_exact_restoration_recovers(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "corrupt-references"
        work_dir.mkdir()
        before = _run_subprocess("train_checkpoint_pause", str(work_dir), "corruptrefs")

        checkpoint_dir = self._checkpoint_dir(work_dir, before["job_id"])
        references_path = checkpoint_dir / "references.json"
        original_text = references_path.read_text(encoding="utf-8")
        tampered = json.loads(original_text)
        tampered["dataset_version_public_id"] = "00000000-0000-0000-0000-tampered0002"
        references_path.write_text(json.dumps(tampered), encoding="utf-8")

        rejected = _run_subprocess("recover_and_continue", str(work_dir), before["job_id"], "false")
        assert rejected["recovery_succeeded"] is False
        assert "checksum mismatch" in rejected["error"]

        references_path.write_text(original_text, encoding="utf-8")
        recovered = _run_subprocess("recover_and_continue", str(work_dir), before["job_id"], "true")
        assert recovered["recovery_succeeded"] is True
        assert recovered["new_checkpoint_dataset_id"] == before["dataset_id"]

    @staticmethod
    def _checkpoint_dir(work_dir: Path, job_id: str) -> Path:
        job_root = work_dir / "core_models" / "pretraining" / "mini_brain_training_jobs" / job_id
        candidates = sorted(p for p in job_root.iterdir() if p.is_dir() and p.name.startswith("step-"))
        assert candidates, "expected at least one real checkpoint directory"
        return candidates[-1]


# ===========================================================================
# Part 9: wrong-identity checkpoint recovery must be rejected.
# ===========================================================================


class TestWrongIdentityRecovery:
    async def test_job_b_cannot_recover_using_job_a_checkpoint_path_escape(self, api_app: FastAPI) -> None:
        """Job B's own checkpoint pointer is made to reference Job A's
        real, genuinely different checkpoint directory -- outside Job B's
        own checkpoint root. Rejected by the path-confinement check,
        which is itself a real security control (Part 20), not merely an
        identity nicety."""

        settings, svc_a, adapter_a, job_a_id, admin_id, ds_a, tok_a, cmv_a = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="wrongid-a", hidden_size=16, intermediate_size=32,
        )
        job_b_dir_settings, svc_b, adapter_b, job_b_id, _admin_id_b, ds_b, tok_b, cmv_b = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="wrongid-b", hidden_size=24, intermediate_size=48,
        )
        assert ds_a != ds_b and cmv_a != cmv_b

        real_checkpoint_dir = Path(adapter_a._checkpoints_saved[0]["canonical_checkpoint_directory"])
        job_b_dir = svc_b._job_dir(job_b_id)
        pointer_path = job_b_dir / "checkpoints" / "checkpoint-epoch000-step00000001-alias.json"
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        pointer_path.write_text(
            dumps_json({
                "real_checkpoint": True, "canonical_checkpoint_directory": str(real_checkpoint_dir),
                "combined_checksum_sha256": "x" * 64, "model_checksum_sha256": "y" * 64,
                "file_size_bytes": 1, "configuration_label": "TEST_INTEGRATION_CONFIGURATION",
            }),
            encoding="utf-8",
        )
        with database_connection(settings.resolved_database_path) as connection:
            job_b_row = connection.execute(
                "SELECT id FROM mini_brain_training_jobs WHERE public_id=?", (job_b_id,)
            ).fetchone()
            connection.execute(
                """INSERT INTO mini_brain_training_checkpoints
                (public_id, job_id, step, epoch, checkpoint_name, relative_path, sha256, file_size_bytes)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    "aliased-escape", job_b_row["id"], 2, 0, "checkpoint-epoch000-step00000001-alias",
                    "checkpoints/checkpoint-epoch000-step00000001-alias.json", "z" * 64, 1,
                ),
            )
            connection.commit()

        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        with pytest.raises(ValidationError, match="outside this job's own checkpoint root"):
            fresh_svc.resume(job_b_id, admin_id=admin_id)
        assert fresh_adapter._model is None, "no model substitution may occur on a rejected recovery"

    async def test_same_root_checkpoint_with_mismatched_identity_is_rejected(self, api_app: FastAPI) -> None:
        """A checkpoint physically copied INTO Job B's own checkpoint
        root (so path confinement alone would not catch it) but whose
        `references.json` still names Job A's real dataset/Core Model --
        rejected specifically by the identity cross-check, proving that
        check is real and independent of the path-confinement check."""

        settings, svc_a, adapter_a, job_a_id, admin_id, ds_a, tok_a, cmv_a = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="sameroot-a", hidden_size=16, intermediate_size=32,
        )
        _settings_b, svc_b, adapter_b, job_b_id, _admin_b, ds_b, tok_b, cmv_b = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="sameroot-b", hidden_size=24, intermediate_size=48,
        )

        import shutil

        real_checkpoint_dir = Path(adapter_a._checkpoints_saved[0]["canonical_checkpoint_directory"])
        job_b_checkpoint_root = svc_b.settings.resolved_pretraining_dir / "mini_brain_training_jobs" / job_b_id
        copied_dir = job_b_checkpoint_root / "step-00000009-epoch-0000"
        shutil.copytree(real_checkpoint_dir, copied_dir)

        job_b_dir = svc_b._job_dir(job_b_id)
        pointer_path = job_b_dir / "checkpoints" / "checkpoint-epoch000-step00000009.json"
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        pointer_path.write_text(
            dumps_json({
                "real_checkpoint": True, "canonical_checkpoint_directory": str(copied_dir),
                "combined_checksum_sha256": "x" * 64, "model_checksum_sha256": "y" * 64,
                "file_size_bytes": 1, "configuration_label": "TEST_INTEGRATION_CONFIGURATION",
            }),
            encoding="utf-8",
        )
        with database_connection(settings.resolved_database_path) as connection:
            job_b_row = connection.execute(
                "SELECT id FROM mini_brain_training_jobs WHERE public_id=?", (job_b_id,)
            ).fetchone()
            connection.execute(
                """INSERT INTO mini_brain_training_checkpoints
                (public_id, job_id, step, epoch, checkpoint_name, relative_path, sha256, file_size_bytes)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    "copied-mismatched", job_b_row["id"], 9, 0, "checkpoint-epoch000-step00000009",
                    "checkpoints/checkpoint-epoch000-step00000009.json", "z" * 64, 1,
                ),
            )
            connection.commit()

        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        with pytest.raises(ValidationError, match="does not match this job"):
            fresh_svc.resume(job_b_id, admin_id=admin_id)
        assert fresh_adapter._model is None

        # No pretraining checkpoint registration, no release, no
        # activation, no Public Chat assignment resulted from the
        # rejected attempt.
        with database_connection(settings.resolved_database_path) as connection:
            pretraining_checkpoints = connection.execute("SELECT COUNT(*) FROM pretraining_checkpoints").fetchone()[0]
        assert pretraining_checkpoints == 0


# ===========================================================================
# Part 10: checkpoint selection -- deterministic latest, no unsafe fallback.
# ===========================================================================


class TestCheckpointSelection:
    async def test_latest_of_multiple_checkpoints_is_selected_deterministically(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, dataset_id, tokenizer_id, cmv_id = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="multickpt",
        )
        # Resume in-process (already-configured adapter -- Phase 2.8B's
        # own path, untouched), take a second real step, save a second checkpoint.
        svc.resume(job_id, admin_id=admin_id)
        svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        svc.pause(job_id, admin_id=admin_id)

        checkpoints = svc.list_checkpoints(job_id)["items"]
        assert len(checkpoints) == 2

        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        fresh_svc.resume(job_id, admin_id=admin_id)
        assert fresh_adapter._completed_steps == 2, "the LATER (step=2) checkpoint must be selected, not the older one"

    async def test_corrupted_latest_checkpoint_does_not_silently_fall_back_to_older_one(
        self, api_app: FastAPI,
    ) -> None:
        settings, svc, adapter, job_id, admin_id, dataset_id, tokenizer_id, cmv_id = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="staleckpt",
        )
        svc.resume(job_id, admin_id=admin_id)
        svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        svc.pause(job_id, admin_id=admin_id)

        latest_dir = Path(adapter._checkpoints_saved[-1]["canonical_checkpoint_directory"])
        model_path = latest_dir / "model_state.pt"
        original_bytes = model_path.read_bytes()
        model_path.write_bytes(original_bytes + b"corrupted-latest")

        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        with pytest.raises(ValueError, match="checksum mismatch"):
            fresh_svc.resume(job_id, admin_id=admin_id)
        # No silent fallback to the older, uncorrupted step=1 checkpoint --
        # the adapter has no model at all after the rejection.
        assert fresh_adapter._model is None


# ===========================================================================
# Part 11: repeated recovery / idempotency.
# ===========================================================================


class TestRepeatedRecoveryIdempotency:
    async def test_resume_twice_in_a_row_is_safely_rejected_the_second_time(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="retry-resume",
        )
        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        first = fresh_svc.resume(job_id, admin_id=admin_id)
        assert first["status"] == "running"
        with pytest.raises(ValidationError, match="must be 'paused' to resume"):
            fresh_svc.resume(job_id, admin_id=admin_id)

    async def test_resume_after_successful_recovery_reuses_live_state_not_recovery_again(
        self, api_app: FastAPI,
    ) -> None:
        """Once a fresh adapter has genuinely recovered (now has a real,
        live model), pausing and resuming it AGAIN within the same
        process must use the existing Phase 2.8B in-process path, not
        attempt a second real recovery -- proven by confirming the model
        object identity is unchanged across the second pause/resume."""

        settings, svc, adapter, job_id, admin_id, *_ = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="retry-after-recovery",
        )
        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        fresh_svc.resume(job_id, admin_id=admin_id)
        recovered_model = fresh_adapter._model
        assert recovered_model is not None

        fresh_svc.pause(job_id, admin_id=admin_id)
        fresh_svc.resume(job_id, admin_id=admin_id)
        assert fresh_adapter._model is recovered_model, "a second resume on an already-recovered adapter must not reconstruct the model again"

    async def test_checkpoint_save_at_same_step_after_recovery_is_rejected(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="retry-samestep",
        )
        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        fresh_svc.resume(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="already exists"):
            fresh_svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        assert len(fresh_svc.list_checkpoints(job_id)["items"]) == 1

    async def test_no_duplicate_events_from_repeated_recovery_attempts(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="retry-events",
        )
        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        fresh_svc.resume(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError):
            fresh_svc.resume(job_id, admin_id=admin_id)

        with database_connection(settings.resolved_database_path) as connection:
            recovery_events = connection.execute(
                """SELECT COUNT(*) FROM mini_brain_training_events
                WHERE job_id=(SELECT id FROM mini_brain_training_jobs WHERE public_id=?)
                AND event_type='training_recovered_from_checkpoint'""",
                (job_id,),
            ).fetchone()[0]
        assert recovery_events == 1


# ===========================================================================
# Part 12: Phase 2.8B failure handling must still apply after recovery.
# ===========================================================================


class TestFailureHandlingAfterRecovery:
    async def test_genuine_failure_after_recovery_still_reaches_failed_status(self, api_app: FastAPI) -> None:
        settings, svc, real_adapter, job_id, admin_id, *_ = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="failure-after-recovery",
        )
        fresh_adapter = TorchTrainingAdapter()
        fresh_svc_recover = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        fresh_svc_recover.resume(job_id, admin_id=admin_id)
        assert fresh_adapter._model is not None

        failing_svc = MiniBrainTrainingEngineService(
            settings, adapters={"gpu": _FailingStepAdapter(fresh_adapter)},
        )
        with pytest.raises(RuntimeError):
            failing_svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)

        job = failing_svc.job(job_id)
        assert job["status"] == "failed"
        assert job["stage"] == "generate_report"
        assert job["training_state"]["last_error"]

        with database_connection(settings.resolved_database_path) as connection:
            failure_events = connection.execute(
                """SELECT COUNT(*) FROM mini_brain_training_events
                WHERE job_id=(SELECT id FROM mini_brain_training_jobs WHERE public_id=?) AND event_type='training_failed'""",
                (job_id,),
            ).fetchone()[0]
        assert failure_events == 1

        report = failing_svc.generate_report_stage(job_id, admin_id=admin_id)
        assert report["final_report"]["status"] == "failed"


# ===========================================================================
# Provenance continuity + no stray/side-effect state.
# ===========================================================================


class TestProvenanceAndNoSideEffects:
    async def test_recovery_alone_creates_no_release_activation_or_public_chat_state(
        self, api_app: FastAPI,
    ) -> None:
        settings, svc, adapter, job_id, admin_id, *_ = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="no-side-effects",
        )
        tables = (
            "pretraining_checkpoints", "pretraining_evaluations", "mini_brain_release_sessions",
            "mini_brain_public_chat_sessions", "inference_model_assignments",
        )
        with database_connection(settings.resolved_database_path) as connection:
            before = {t: connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}

        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        fresh_svc.resume(job_id, admin_id=admin_id)

        with database_connection(settings.resolved_database_path) as connection:
            after = {t: connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        assert after == before

    async def test_handoff_registration_still_works_after_a_recovered_checkpoint(self, api_app: FastAPI) -> None:
        settings, svc, adapter, job_id, admin_id, dataset_id, tokenizer_id, cmv_id = await _real_paused_job_with_checkpoint(
            api_app, name_suffix="handoff-after-recovery",
        )
        fresh_adapter = TorchTrainingAdapter()
        fresh_svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": fresh_adapter})
        fresh_svc.resume(job_id, admin_id=admin_id)
        fresh_svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        fresh_svc.run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        checkpoint_row = fresh_svc.list_checkpoints(job_id)["items"][-1]

        handoff = MiniBrainPretrainingHandoffService(settings)
        result = handoff.register_checkpoint(job_id, checkpoint_row["public_id"], admin_id)
        with database_connection(settings.resolved_database_path) as connection:
            registered = connection.execute(
                "SELECT status, model_checksum_sha256 FROM pretraining_checkpoints WHERE public_id=?",
                (result["pretraining_checkpoint_public_id"],),
            ).fetchone()
        assert registered["status"] == "verified"
