"""MB-22: Brud Mini Brain Real Training Execution Engine -- the
orchestration layer for the 14-stage job workflow described in the
MB-22 task spec.

The first Mini Brain phase allowed to run a real training workflow --
but only ever in simulation mode in this environment (the real CPU/
GPU adapters are disclosed stubs, see `training_runtime_adapter.py`),
always CPU-first, always behind a fresh, per-job admin authorization
recorded on the job itself. This service never auto-starts training
after package approval, never auto-deploys or auto-promotes a trained
model, never overwrites an existing checkpoint, never downloads a
model, never executes an arbitrary shell command, and never modifies
any MB-16 through MB-20 historical record -- it only reads MB-18
(approved training packages) and MB-20 (approved release-governance
sessions) through their own public methods.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_training_engine import (
    MiniBrainTrainingEngineRepository,
    public_checkpoint_row,
    public_job_row,
    public_memory_row,
    public_metric_row,
)
from backend.services.mini_brain_release_governance_service import MiniBrainReleaseGovernanceService
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService
from backend.services.training_runtime_adapter import (
    TrainingRuntimeAdapterProtocol,
    adapter_for_execution_mode,
)
from core_model.mini_brain.training_engine.checkpoint_namer import (
    build_checkpoint_name,
    check_no_overwrite,
    find_latest_checkpoint,
)
from core_model.mini_brain.training_engine.experiment_fingerprint import build_experiment_fingerprint
from core_model.mini_brain.training_engine.failure_classifier import classify_failure
from core_model.mini_brain.training_engine.job_report_generator import generate_job_report
from core_model.mini_brain.training_engine.job_validator import (
    validate_release_approval,
    validate_training_package,
)
from core_model.mini_brain.training_engine.resource_planner import plan_resources
from core_model.mini_brain.training_engine.resume_state_builder import build_resume_state
from core_model.mini_brain.training_engine.training_audit_builder import build_training_audit
from core_model.mini_brain.training_engine.training_manifest_builder import build_training_manifest
from core_model.release.artifact_inventory import resolve_confined_path

EXECUTION_MODES = {"simulation", "cpu", "gpu"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _timed(fn, /, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn(**kwargs)
    return result, round((time.perf_counter() - started) * 1000, 3)


class MiniBrainTrainingEngineService:
    def __init__(self, settings: Settings, *, adapters: dict[str, TrainingRuntimeAdapterProtocol] | None = None) -> None:
        self.settings = settings
        self.repository = MiniBrainTrainingEngineRepository(settings.resolved_database_path)

        self.training_pipeline = MiniBrainTrainingPipelineService(settings)
        self.release_governance = MiniBrainReleaseGovernanceService(settings)

        # Real adapters by execution_mode. Tests inject a fresh SimulationTrainingAdapter
        # (or a test double) via `adapters` -- the default set always includes the real
        # (honestly-stubbed) cpu/gpu adapters plus the real simulation adapter.
        self._adapter_overrides = adapters or {}

    def _adapter(self, execution_mode: str) -> TrainingRuntimeAdapterProtocol:
        if execution_mode in self._adapter_overrides:
            return self._adapter_overrides[execution_mode]
        return adapter_for_execution_mode(execution_mode)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, job_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.create_event(
            connection, job_id=job_id, event_type=event_type, stage=stage, message=message, metadata=metadata,
        )

    def _job_dir(self, job_public_id: str) -> Path:
        root = self.settings.resolved_document_dir.parent / "training_runs" / job_public_id
        for sub in ("checkpoints", "logs", "manifests", "reports"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        return root

    def job(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_job_row(self.repository.get_job(connection, job_public_id))

    def list_jobs(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_jobs(connection, limit=limit, offset=offset)
        return {"items": [public_job_row(row) for row in rows]}

    def events(self, job_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            rows = self.repository.list_events(connection, job_id=job_row["id"], limit=limit, offset=offset)
        return {"items": [dict(row) for row in rows]}

    def list_checkpoints(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            rows = self.repository.list_checkpoints(connection, job_id=job_row["id"])
        return {"items": [public_checkpoint_row(row) for row in rows]}

    def list_metrics(self, job_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            rows = self.repository.list_metrics(connection, job_id=job_row["id"], limit=limit, offset=offset)
        return {"items": [public_metric_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    # -- stage 1: create job --------------------------------------

    def create_job(
        self, *, topic: str, training_package_session_public_id: str, release_governance_session_public_id: str,
        execution_mode: str, admin_id: str,
    ) -> dict[str, Any]:
        if not topic.strip():
            raise ValidationError("topic must not be empty")
        if execution_mode not in EXECUTION_MODES:
            raise ValidationError(f"execution_mode must be one of {sorted(EXECUTION_MODES)}")
        with self.repository.transaction() as connection:
            public_id = self.repository.create_job(
                connection, training_package_session_public_id=training_package_session_public_id,
                release_governance_session_public_id=release_governance_session_public_id, topic=topic,
                execution_mode=execution_mode, created_by_admin_public_id=admin_id,
            )
            job_row = self.repository.get_job(connection, public_id)
            self._event(
                connection, job_row["id"], "job_created", stage="validate_release",
                message=f"training job created for topic '{topic}' (execution_mode={execution_mode})",
            )
            return public_job_row(self.repository.get_job(connection, public_id))

    # -- stage 2: validate release approval -----------------------------

    def run_validate_release_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "validate_release":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'validate_release'")

        release_session = self.release_governance.session(job_data["release_governance_session_public_id"])
        report = validate_release_approval(release_session=release_session)
        if not report["valid"]:
            raise ValidationError(f"release validation failed: {report['reason']}")

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"release_validation_report_json": report, "stage": "validate_package"},
            )
            self._event(connection, job_row["id"], "release_validated", stage="validate_release", message="MB-20 release session approved")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 3: validate training package ------------------------------

    def run_validate_package_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "validate_package":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'validate_package'")

        package_session = self.training_pipeline.session(job_data["training_package_session_public_id"])
        report = validate_training_package(package_session=package_session)
        if not report["valid"]:
            raise ValidationError(f"package validation failed: {report['reason']}")

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"package_validation_report_json": report, "stage": "validate_authorization"},
            )
            self._event(connection, job_row["id"], "package_validated", stage="validate_package", message="MB-18 package session approved")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 4: validate admin authorization -----------------------------

    def run_validate_authorization_stage(
        self, job_public_id: str, *, authorization_reason: str, admin_id: str,
    ) -> dict[str, Any]:
        job_data = self.job(job_public_id)
        if job_data["stage"] != "validate_authorization":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'validate_authorization'")
        if not admin_id:
            raise ValidationError("a real admin identity is required to authorize a training job")
        if not authorization_reason.strip():
            raise ValidationError("authorization_reason must not be empty")

        token = str(uuid4())
        report = {
            "authorized": True, "admin_id": admin_id, "reason": authorization_reason, "token": token,
            "disclosure": "this authorization only permits this exact job to proceed -- it never grants any other job, dataset, or release approval",
        }

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {
                    "authorization_report_json": report, "admin_authorized_by": admin_id,
                    "admin_authorization_reason": authorization_reason, "admin_authorization_token": token,
                    "stage": "plan_resources",
                },
            )
            self._event(connection, job_row["id"], "authorization_validated", stage="validate_authorization", message=f"authorized by {admin_id}")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 5: plan resources -------------------------------------------

    def run_plan_resources_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "plan_resources":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'plan_resources'")

        package_session = self.training_pipeline.session(job_data["training_package_session_public_id"])
        hardware_estimate = package_session.get("hardware_estimate_report", {})

        report, latency_ms = _timed(
            plan_resources, execution_mode=job_data["execution_mode"],
            estimated_token_count=hardware_estimate.get("estimated_token_count", 0),
            ram_tier=hardware_estimate.get("ram_tier", "8GB+"), vram_tier=hardware_estimate.get("vram_tier", "none"),
            cpu_only_feasible=hardware_estimate.get("cpu_only_feasible", True),
            estimated_disk_bytes=hardware_estimate.get("estimated_disk_bytes", 0),
            expected_training_duration_category=hardware_estimate.get("expected_training_duration_category", "hours"),
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"resource_plan_report_json": report, "stage": "build_manifest"},
            )
            self._event(connection, job_row["id"], "resources_planned", stage="plan_resources", message=f"cpu_thread_count={report['cpu_thread_count']}")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 6: build training manifest ----------------------------------

    def run_build_manifest_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "build_manifest":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'build_manifest'")

        fingerprint = build_experiment_fingerprint(
            training_package_session_public_id=job_data["training_package_session_public_id"],
            release_governance_session_public_id=job_data["release_governance_session_public_id"],
            execution_mode=job_data["execution_mode"], resource_plan=job_data["resource_plan_report"],
        )
        manifest = build_training_manifest(
            job_public_id=job_public_id, topic=job_data["topic"],
            training_package_session_public_id=job_data["training_package_session_public_id"],
            release_governance_session_public_id=job_data["release_governance_session_public_id"],
            execution_mode=job_data["execution_mode"], resource_plan=job_data["resource_plan_report"],
            fingerprint=fingerprint, created_at=_now(),
        )

        job_dir = self._job_dir(job_public_id)
        from backend.core.json_utils import dumps_json
        manifest_path = resolve_confined_path(job_dir / "manifests", "training_manifest.json")
        manifest_path.write_text(dumps_json(manifest), encoding="utf-8")

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {
                    "training_manifest_json": manifest, "output_directory": str(job_dir),
                    "checkpoint_directory": str(job_dir / "checkpoints"), "stage": "reserve_runtime",
                },
            )
            self._event(connection, job_row["id"], "manifest_built", stage="build_manifest", message="training manifest written")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 7: reserve runtime --------------------------------------------

    def run_reserve_runtime_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "reserve_runtime":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'reserve_runtime'")

        adapter = self._adapter(job_data["execution_mode"])
        if not adapter.is_available():
            raise ValidationError(f"runtime adapter for execution_mode '{job_data['execution_mode']}' is not available in this environment")
        report, latency_ms = _timed(adapter.reserve, resource_plan=job_data["resource_plan_report"])
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"runtime_reservation_report_json": report, "stage": "start_training"},
            )
            self._event(connection, job_row["id"], "runtime_reserved", stage="reserve_runtime", message=f"runtime={report.get('runtime')}")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 8: start training ---------------------------------------------

    def run_start_training_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "start_training":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'start_training'")

        adapter = self._adapter(job_data["execution_mode"])
        adapter.start(resume_step=0, resume_epoch=0)
        training_state = {"last_step": 0, "last_epoch": 0, "last_loss": None}

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"training_state_json": training_state, "stage": "streaming_metrics", "status": "running", "started_at": _now()},
            )
            self._event(connection, job_row["id"], "training_started", stage="start_training", message="training started")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 9: stream metrics (repeatable while status='running') -----------

    def run_stream_metric_stage(self, job_public_id: str, *, step: int, epoch: int, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "streaming_metrics" or job_data["status"] != "running":
            raise ValidationError(f"job must be at stage 'streaming_metrics' with status 'running' to stream metrics (currently stage='{job_data['stage']}', status='{job_data['status']}')")

        adapter = self._adapter(job_data["execution_mode"])
        metric, latency_ms = _timed(adapter.step, step=step, epoch=epoch)

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.append_metric(
                connection, job_id=job_row["id"], step=metric["step"], epoch=metric["epoch"], loss=metric.get("loss"),
                learning_rate=metric.get("learning_rate"), tokens_per_second=metric.get("tokens_per_second"),
                examples_per_second=metric.get("examples_per_second"), gpu_memory_mb=metric.get("gpu_memory_mb"),
                cpu_memory_mb=metric.get("cpu_memory_mb"),
            )
            training_state = dict(job_data["training_state"])
            training_state.update({"last_step": metric["step"], "last_epoch": metric["epoch"], "last_loss": metric.get("loss")})
            self.repository.update_job(connection, job_public_id, {"training_state_json": training_state})
            self._event(
                connection, job_row["id"], "metric_streamed", stage="streaming_metrics",
                message=f"step={metric['step']} loss={metric.get('loss')}", metadata={"latency_ms": latency_ms},
            )
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 10: save checkpoint (repeatable while status IN running/paused) ---

    def run_save_checkpoint_stage(self, job_public_id: str, *, step: int, epoch: int, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["status"] not in ("running", "paused"):
            raise ValidationError(f"job status must be 'running' or 'paused' to save a checkpoint (currently '{job_data['status']}')")

        existing = self.list_checkpoints(job_public_id)["items"]
        checkpoint_name = build_checkpoint_name(step=step, epoch=epoch)
        overwrite_check = check_no_overwrite(
            checkpoint_name=checkpoint_name, existing_checkpoint_names=[c["checkpoint_name"] for c in existing],
        )
        if not overwrite_check["safe_to_write"]:
            raise ValidationError(f"checkpoint '{checkpoint_name}' already exists -- an existing checkpoint is never overwritten")

        job_dir = self._job_dir(job_public_id)
        checkpoint_path = resolve_confined_path(job_dir / "checkpoints", f"{checkpoint_name}.json")
        adapter = self._adapter(job_data["execution_mode"])
        result, latency_ms = _timed(adapter.save_checkpoint, path=checkpoint_path, step=step, epoch=epoch)

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.create_checkpoint(
                connection, job_id=job_row["id"], step=step, epoch=epoch, checkpoint_name=checkpoint_name,
                relative_path=f"checkpoints/{checkpoint_name}.json", sha256=result["sha256"],
                file_size_bytes=result["file_size_bytes"], is_metadata_only=result["is_metadata_only"],
            )
            self._event(
                connection, job_row["id"], "checkpoint_saved", stage=job_data["stage"],
                message=f"{checkpoint_name} saved", metadata={"latency_ms": latency_ms},
            )
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 11: pause / resume ----------------------------------------------

    def pause(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["status"] != "running":
            raise ValidationError(f"job status must be 'running' to pause (currently '{job_data['status']}')")

        adapter = self._adapter(job_data["execution_mode"])
        adapter.pause()

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(connection, job_public_id, {"status": "paused"})
            self._event(connection, job_row["id"], "training_paused", stage=job_data["stage"], message="training paused")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    def resume(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["status"] != "paused":
            raise ValidationError(f"job status must be 'paused' to resume (currently '{job_data['status']}')")

        checkpoints = self.list_checkpoints(job_public_id)["items"]
        latest = find_latest_checkpoint(checkpoints=checkpoints)
        recent_metrics = self.list_metrics(job_public_id, limit=100, offset=0)["items"]
        last_metric = recent_metrics[-1] if recent_metrics else None
        resume_state = build_resume_state(latest_checkpoint=latest, last_metric=last_metric)

        adapter = self._adapter(job_data["execution_mode"])
        adapter.resume()

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(connection, job_public_id, {"status": "running"})
            self._event(
                connection, job_row["id"], "training_resumed", stage=job_data["stage"], message="training resumed",
                metadata={"resume_state": resume_state},
            )
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- cancel ------------------------------------------------------------------

    def cancel(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["status"] not in ("in_progress", "running", "paused"):
            raise ValidationError(f"job status must be in-progress, running, or paused to cancel (currently '{job_data['status']}')")

        if job_data["status"] in ("running", "paused"):
            adapter = self._adapter(job_data["execution_mode"])
            adapter.cancel()

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(connection, job_public_id, {"status": "cancelled", "stage": "cancelled", "completed_at": _now()})
            self._event(connection, job_row["id"], "training_cancelled", stage=job_data["stage"], message="training cancelled by admin")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 12: finalize training ----------------------------------------------

    def finalize(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["status"] not in ("running", "paused"):
            raise ValidationError(f"job status must be 'running' or 'paused' to finalize (currently '{job_data['status']}')")

        adapter = self._adapter(job_data["execution_mode"])
        adapter.finalize()

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"status": "completed", "stage": "generate_report", "completed_at": _now()},
            )
            self._event(connection, job_row["id"], "training_finalized", stage=job_data["stage"], message="training finalized")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 13: generate final report -------------------------------------------

    def generate_report_stage(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        job_data = self.job(job_public_id)
        if job_data["stage"] != "generate_report":
            raise ValidationError(f"job is at stage '{job_data['stage']}', not 'generate_report'")

        metrics = self.list_metrics(job_public_id, limit=100, offset=0)["items"]
        checkpoints = self.list_checkpoints(job_public_id)["items"]
        failure_summary = None
        if job_data["status"] == "failed":
            failure_summary = classify_failure(error_message=job_data.get("training_state", {}).get("last_error"))

        report = generate_job_report(
            job_public_id=job_public_id, topic=job_data["topic"], execution_mode=job_data["execution_mode"],
            training_package_session_public_id=job_data["training_package_session_public_id"],
            release_governance_session_public_id=job_data["release_governance_session_public_id"],
            status=job_data["status"], started_at=job_data["started_at"], completed_at=job_data["completed_at"],
            metrics=metrics, checkpoints=checkpoints, resource_plan=job_data["resource_plan_report"],
            fingerprint=job_data["training_manifest"].get("fingerprint", {}), failure_summary=failure_summary,
        )

        job_dir = self._job_dir(job_public_id)
        from backend.core.json_utils import dumps_json
        report_path = resolve_confined_path(job_dir / "reports", "final_report.json")
        report_path.write_text(dumps_json(report), encoding="utf-8")

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.update_job(
                connection, job_public_id,
                {"final_report_json": report, "stage": "awaiting_archive"},
            )
            self._event(connection, job_row["id"], "final_report_generated", stage="generate_report", message=f"final_loss={report['final_loss']}")
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- stage 14: archive job -------------------------------------------------------

    def archive(self, job_public_id: str, *, admin_id: str) -> dict[str, Any]:
        job_data = self.job(job_public_id)
        if job_data["status"] not in ("completed", "cancelled"):
            raise ValidationError(f"job status must be 'completed' or 'cancelled' to archive (currently '{job_data['status']}')")

        final_status = job_data["status"]
        metrics = self.list_metrics(job_public_id, limit=100, offset=0)["items"]
        checkpoints = self.list_checkpoints(job_public_id)["items"]
        losses = [m["loss"] for m in metrics if m.get("loss") is not None]

        with self.repository.transaction() as connection:
            job_row = self.repository.get_job(connection, job_public_id)
            self.repository.create_memory(
                connection, job_id=job_row["id"], topic=job_data["topic"], execution_mode=job_data["execution_mode"],
                final_status=final_status, total_steps=len(metrics),
                final_loss=losses[-1] if losses else None, best_loss=min(losses) if losses else None,
                checkpoint_count=len(checkpoints), recorded_by_admin_public_id=admin_id,
            )
            self.repository.update_job(
                connection, job_public_id, {"status": "archived", "stage": "archived", "archived_at": _now()},
            )
            self._event(
                connection, job_row["id"], "job_archived", stage="awaiting_archive",
                message=f"job archived (final_status={final_status}) -- no deployment or promotion has occurred",
                metadata={"admin_id": admin_id},
            )
            return public_job_row(self.repository.get_job(connection, job_public_id))

    # -- audit -----------------------------------------------------------------------

    def audit(self, job_public_id: str) -> dict[str, Any]:
        job_data = self.job(job_public_id)
        events = self.events(job_public_id, limit=100)["items"]
        return build_training_audit(events=events, admin_authorized_by=job_data.get("admin_authorized_by"))


__all__ = ["MiniBrainTrainingEngineService"]
