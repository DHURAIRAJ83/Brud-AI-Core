"""Phase 2.8D: Training Scale Qualification, Resource Envelope Expansion
& Cross-Request Execution Integrity.

Phase 2.8A established the first real, measured training-readiness
boundary at 1,000 records (`LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT`).
This phase extends real measurement -- real, governed dataset builds
(`DatasetVersioningService.create_build()` -> `validate_build()` ->
`run_build()`, never a direct `dataset_version_items` insert), real
training readiness contracts, real MB-22 training qualification (real
forward/backward pass, real loss, real checkpoint, independently
verified), and real fresh-process checkpoint recovery with bit-exact
weight restoration -- through 2,500, 5,000, and 10,000 records. Every
number asserted below was independently measured via
`tests/backend/_phase28d_subprocess_runner.py`, run in genuinely
separate OS processes, before this file was written; the ceiling was
only raised to 10,000 in
`backend/services/mini_brain_training_engine_service.py` after that
evidence was gathered (Part 3/5 of the phase mission: audit first,
measure second, only then adjust the evidence-based constant).

This file also formalizes this phase's cross-request adapter audit
(Part 8): Phase 2.8C proved `resume()` recovers a genuinely fresh
adapter from a checkpoint, but explicitly left open whether *other*
MB-22 stages tolerate a fresh adapter too. They do not -- this is
confirmed here, not fixed (fixing it would require general
cross-request adapter persistence, an architecture-level change
explicitly out of this phase's scope), and the failure mode is proven
safe: fails closed via Phase 2.8B's own failure-handling path, never a
silent success or corruption.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.database.connection import database_connection
from backend.database.repositories.base import ValidationError
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

_RUNNER = Path(__file__).parent / "_phase28d_subprocess_runner.py"


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


def _run(*args: str, timeout: int = 300) -> dict:
    result = subprocess.run(
        [sys.executable, str(_RUNNER), *args], capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


async def _fresh_gpu_job_paused_with_checkpoint(api_app: FastAPI, *, name_suffix: str, record_count: int = 40):
    """Same-process helper for the cross-request adapter audit -- drives
    a real job to `status='paused'` with one real checkpoint, returning
    everything needed to construct further genuinely fresh service/
    adapter pairs against it."""

    settings = api_app.state.settings
    admin_id = _create_admin(api_app, username=f"admin-{name_suffix}")
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic=name_suffix)
    tokenizer_id = _real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = _real_core_model_version(settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id)
    dataset_id, _, _ = _build_real_dataset_via_service(
        settings, name_suffix=name_suffix, record_texts=_generate_corpus(record_count, seed_offset=1),
    )

    def fresh_service() -> MiniBrainTrainingEngineService:
        return MiniBrainTrainingEngineService(settings, adapters={"gpu": TorchTrainingAdapter()})

    svc = fresh_service()
    job = svc.create_job(
        topic=f"{name_suffix}-job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.8d", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_XREQ")
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.pause(job_id, admin_id=admin_id)
    return settings, admin_id, job_id, fresh_service


# ===========================================================================
# Scale ladder: 1,000 (control), 2,500, 5,000, 10,000.
# ===========================================================================


class TestScaleLadder:
    @pytest.mark.parametrize("record_count", [1000, 2500, 5000, 10000])
    def test_real_scale_run_reaches_ready_and_qualifies(self, tmp_path: Path, record_count: int) -> None:
        work_dir = tmp_path / f"scale{record_count}"
        work_dir.mkdir()
        result = _run("scale_run", str(work_dir), str(record_count), f"scale{record_count}", timeout=300)

        # Real, governed dataset build.
        assert result["dataset_readiness_status"] == "READY"
        assert result["dataset_checksum_sha256"]
        assert result["tokenizer_checksum_sha256"]
        assert result["train_block_count"] > 0
        assert result["validation_block_count"] > 0
        assert result["block_builder_version"] == "dataset_pipeline_v1"

        # The advisory training-readiness gate is now genuinely READY at
        # this scale (the ceiling was raised to 10,000 only after real
        # measurement established it was safe -- see the source comment
        # next to LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT).
        assert result["training_readiness_status"] == "READY"
        assert result["bypassed_advisory_readiness_gate_for_evidence_gathering"] is False

        # Real MB-22 training qualification: real loss, real checkpoint,
        # independently re-verified.
        assert result["training_qualification_attempted"] is True
        assert result["first_step_loss"] is not None
        assert result["checkpoint_verify_ok"] is True
        assert result["checkpoint_size_bytes"] > 0
        assert result["model_weights_sha256"]

        # Real, measured resource numbers -- never fabricated.
        assert result["peak_rss_kib_final"] > 0
        assert result["disk_usage_bytes_final"] > 0
        assert result["reserve_runtime_seconds"] > 0
        assert result["first_training_step_seconds"] > 0

    def test_record_count_beyond_new_ceiling_still_reports_not_ready(self, tmp_path: Path) -> None:
        """10,001 records -- one beyond this phase's own new, measured
        ceiling -- must still report NOT_READY / insufficient_evidence,
        never silently READY. Proves the ceiling was moved to a specific,
        evidence-backed value, not removed."""

        work_dir = tmp_path / "scale10001"
        work_dir.mkdir()
        result = _run("scale_run", str(work_dir), "10001", "scale10001", timeout=300)
        assert result["dataset_readiness_status"] == "READY"
        assert result["training_readiness_status"] == "NOT_READY"
        assert result["resource_estimate"]["envelope_classification"] == "insufficient_evidence"
        assert result["resource_estimate"]["largest_validated_record_count"] == 10000
        assert result["bypassed_advisory_readiness_gate_for_evidence_gathering"] is True
        # The real memory gate itself is untouched by record count -- it
        # only concerns whether the (fixed-size) model fits in available
        # memory, and still reports a trivial estimate here.
        assert result["resource_estimate"]["estimated_memory_bytes"] < result["resource_estimate"]["available_memory_bytes"]


# ===========================================================================
# Determinism at every tested scale.
# ===========================================================================


class TestDatasetDeterminism:
    @pytest.mark.parametrize("record_count", [1000, 2500, 5000, 10000])
    def test_pipeline_output_is_byte_identical_across_two_builds(self, tmp_path: Path, record_count: int) -> None:
        work_dir = tmp_path / f"det{record_count}"
        work_dir.mkdir()
        result = _run("determinism_run", str(work_dir), str(record_count), f"det{record_count}", timeout=300)
        assert result["tokenizer_checksum_identical"] is True
        assert result["block_builder_version_identical"] is True
        assert result["train_blocks_identical"] is True
        assert result["validation_blocks_identical"] is True
        assert result["train_block_count"] > 0
        assert result["validation_block_count"] > 0


# ===========================================================================
# Fresh-process recovery at the largest validated scale (10,000).
# ===========================================================================


class TestRecoveryAtScale:
    def test_fresh_process_recovery_at_10000_records(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "recover10000"
        work_dir.mkdir()
        before = _run("train_checkpoint_pause_at_scale", str(work_dir), "10000", "recov10k", timeout=300)
        assert before["completed_steps"] == 1

        after = _run("recover_and_continue_at_scale", str(work_dir), before["job_id"], "true", timeout=300)
        assert after["model_was_none_before_recovery"] is True
        assert after["recovery_succeeded"] is True
        assert after["model_restored"] is True
        assert after["restored_model_weights_sha256"] == before["model_weights_sha256"]
        assert after["optimizer_state_restored"] is True
        assert after["completed_steps_after_recovery"] == 1
        assert after["weights_changed_after_resumed_step"] is True
        assert after["checkpoint_count_after_recovery"] == 2
        assert after["new_checkpoint_verified"] is True
        assert after["new_checkpoint_dataset_id"] == before["dataset_id"]
        assert after["new_checkpoint_core_model_id"] == before["cmv_id"]
        assert after["job_row_count"] == 1
        assert after["peak_rss_kib_final"] > 0

    def test_corrupted_checkpoint_at_10000_records_fails_closed_then_recovers_after_exact_restoration(
        self, tmp_path: Path,
    ) -> None:
        work_dir = tmp_path / "corrupt10000"
        work_dir.mkdir()
        before = _run("train_checkpoint_pause_at_scale", str(work_dir), "10000", "corrupt10k", timeout=300)

        job_root = work_dir / "core_models" / "pretraining" / "mini_brain_training_jobs" / before["job_id"]
        checkpoint_dirs = sorted(p for p in job_root.iterdir() if p.is_dir() and p.name.startswith("step-"))
        model_path = checkpoint_dirs[-1] / "model_state.pt"
        original_bytes = model_path.read_bytes()
        model_path.write_bytes(original_bytes + b"\xde\xad\xbe\xef-phase28d-corruption")

        rejected = _run("recover_and_continue_at_scale", str(work_dir), before["job_id"], "false", timeout=300)
        assert rejected["recovery_succeeded"] is False
        assert "checksum mismatch" in rejected["error"]

        model_path.write_bytes(original_bytes)
        recovered = _run("recover_and_continue_at_scale", str(work_dir), before["job_id"], "true", timeout=300)
        assert recovered["recovery_succeeded"] is True
        assert recovered["restored_model_weights_sha256"] == before["model_weights_sha256"]


# ===========================================================================
# Cross-request adapter audit (Part 8) -- confirms, does not fix, the
# Phase 2.8C-documented gap; proves the failure mode is safe.
# ===========================================================================


class TestCrossRequestExecutionIntegrity:
    async def test_reserve_and_start_require_the_same_adapter_object(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="xreq-cd")
        tokenizer_id = _real_tokenizer(settings, name_suffix="xreq-cd")
        cmv_id = _real_core_model_version(settings, admin_id, name_suffix="xreq-cd", tokenizer_version_public_id=tokenizer_id)
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="xreq-cd", record_texts=_generate_corpus(40, seed_offset=1),
        )

        def fresh_service() -> MiniBrainTrainingEngineService:
            return MiniBrainTrainingEngineService(settings, adapters={"gpu": TorchTrainingAdapter()})

        svc_a = fresh_service()
        job = svc_a.create_job(
            topic="xreq-cd-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
        )
        job_id = job["public_id"]
        svc_a.run_validate_release_stage(job_id, admin_id=admin_id)
        svc_a.run_validate_package_stage(job_id, admin_id=admin_id)
        svc_a.run_validate_authorization_stage(job_id, authorization_reason="xreq", admin_id=admin_id)
        svc_a.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc_a.run_build_manifest_stage(job_id, admin_id=admin_id)

        # C: reserve_runtime via one fresh service -- succeeds on its own.
        svc_reserve = fresh_service()
        svc_reserve.run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_XREQ")

        # D: start_training via a genuinely DIFFERENT fresh service -- fails.
        # This is the pre-existing, Phase 2.8C-documented gap, confirmed
        # here, not fixed (fixing it is a cross-request architecture
        # change, out of this phase's scope).
        svc_start = fresh_service()
        with pytest.raises(Exception, match="adapter must be reserved"):
            svc_start.run_start_training_stage(job_id, admin_id=admin_id)

        # The same call on the service that actually reserved succeeds --
        # confirming the boundary is exactly "same adapter object", not a
        # broader failure.
        svc_reserve.run_start_training_stage(job_id, admin_id=admin_id)

    async def test_training_step_via_a_fresh_adapter_fails_closed_not_silently(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, fresh_service = await _fresh_gpu_job_paused_with_checkpoint(
            api_app, name_suffix="xreq-efresh",
        )
        # Resume normally (Phase 2.8C recovery) so the job is 'running' again.
        svc_resume = fresh_service()
        svc_resume.resume(job_id, admin_id=admin_id)

        # A THIRD, genuinely fresh service/adapter attempts the next step --
        # this is the exact scenario a real, separate HTTP request would
        # produce. It must fail, and fail SAFELY: no silent success, no
        # corrupted state -- the job transitions to 'failed' via Phase
        # 2.8B's own, unmodified failure-handling path.
        svc_third = fresh_service()
        with pytest.raises(Exception, match="adapter has not been started"):
            svc_third.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)

        job_after = svc_resume.job(job_id)
        assert job_after["status"] == "failed"
        assert job_after["training_state"]["last_error"]

        # A failed job correctly cannot be resumed -- no unsafe recovery
        # from this state either.
        with pytest.raises(ValidationError, match="must be 'paused' to resume"):
            svc_resume.resume(job_id, admin_id=admin_id)

        # No duplicate job row, no stray checkpoint from the failed attempt.
        with database_connection(settings.resolved_database_path) as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0]
            checkpoint_count = connection.execute("SELECT COUNT(*) FROM mini_brain_training_checkpoints").fetchone()[0]
        assert job_count == 1
        assert checkpoint_count == 1  # only the one saved before the failed attempt

    async def test_full_sequence_succeeds_when_the_same_service_is_reused_after_resume(self, api_app: FastAPI) -> None:
        """The one boundary that DOES work across a fresh service:
        resume() itself, and every stage called on THAT SAME service
        object afterward -- proving the gap is specifically "a new
        service per call", not "resume() is broken"."""

        settings, admin_id, job_id, fresh_service = await _fresh_gpu_job_paused_with_checkpoint(
            api_app, name_suffix="xreq-happy",
        )
        svc = fresh_service()
        svc.resume(job_id, admin_id=admin_id)
        svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        result = svc.finalize(job_id, admin_id=admin_id)
        assert result["status"] == "completed"


# ===========================================================================
# Failure safety at the largest validated scale.
# ===========================================================================


class TestFailureSafetyAtScale:
    def test_repeated_recovery_at_10000_records_is_safe(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "repeat10000"
        work_dir.mkdir()
        before = _run("train_checkpoint_pause_at_scale", str(work_dir), "10000", "repeat10k", timeout=300)
        first = _run("recover_and_continue_at_scale", str(work_dir), before["job_id"], "true", timeout=300)
        assert first["recovery_succeeded"] is True

        # A second recovery attempt on the same job (now 'running', not
        # 'paused') must be rejected, not silently repeat recovery.
        second = _run("recover_and_continue_at_scale", str(work_dir), before["job_id"], "false", timeout=300)
        assert second["recovery_succeeded"] is False
        assert "must be 'paused' to resume" in second["error"]

        with database_connection(Path(before["database_path"])) as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0]
        assert job_count == 1

    async def test_no_release_activation_or_public_chat_state_at_scale(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, fresh_service = await _fresh_gpu_job_paused_with_checkpoint(
            api_app, name_suffix="xreq-noeffects", record_count=1000,
        )
        tables = (
            "pretraining_checkpoints", "pretraining_evaluations", "mini_brain_release_sessions",
            "mini_brain_public_chat_sessions", "inference_model_assignments",
        )
        with database_connection(settings.resolved_database_path) as connection:
            before_counts = {t: connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}

        svc = fresh_service()
        svc.resume(job_id, admin_id=admin_id)
        svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        svc.finalize(job_id, admin_id=admin_id)

        with database_connection(settings.resolved_database_path) as connection:
            after_counts = {t: connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        assert after_counts == before_counts
