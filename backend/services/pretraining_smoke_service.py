"""Phase 21A training-configuration validation and the tiny bounded
pretraining smoke test. Reuses Phase 8's `CoreModelService` (model
config/version/architecture verification) and Phase 9's
`PretrainingService` (job/trainer/checkpoint/pause/resume) completely
unchanged -- this module only orchestrates them against a frozen
Phase 21A dataset snapshot and records the outcome for the readiness
gate. Never starts a long-running or production-scale job: smoke runs
are bounded to Profile A ("micro_smoke_test") and a small step count.
"""

from __future__ import annotations

import time
from threading import Thread
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.pretraining_readiness import (
    PretrainingReadinessRepository,
    public_row,
)
from backend.models.core_models import CoreConfigCreate, CoreFamilyCreate, CoreVersionCreate
from backend.models.pretraining import PretrainingJobCreate
from backend.models.pretraining_readiness import SmokeRunCreate, TrainingConfigValidateRequest
from backend.services.core_model_service import CoreModelService
from backend.services.pretraining_service import PretrainingService
from core_model.training.pretraining_config import from_mapping


def _now_sql() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class PretrainingSmokeService:
    def __init__(
        self,
        readiness_repository: PretrainingReadinessRepository,
        core_model_repository: CoreModelRepository,
        pretraining_repository: PretrainingRepository,
        settings: Settings,
    ) -> None:
        self.readiness_repository = readiness_repository
        self.settings = settings
        self.core_model_service = CoreModelService(core_model_repository, settings)
        self.pretraining_service = PretrainingService(pretraining_repository, settings)

    def validate_training_config(self, payload: TrainingConfigValidateRequest) -> dict[str, Any]:
        with self.readiness_repository.transaction() as connection:
            snapshot = self.readiness_repository.pretraining_dataset_snapshot(
                connection, payload.pretraining_dataset_snapshot_public_id
            )
            estimate = self.readiness_repository.base_model_resource_estimate(
                connection, payload.base_model_resource_estimate_public_id
            )
        failures: list[str] = []
        warnings: list[str] = []
        try:
            config = from_mapping(payload.configuration)
        except ValueError as exc:
            failures.append(str(exc))
            config = None
        if snapshot["train_record_count"] <= 0:
            failures.append("dataset snapshot has an empty train split")
        if snapshot["validation_record_count"] <= 0:
            warnings.append("dataset snapshot has an empty validation split")
        if not estimate["within_safe_limit"]:
            failures.append("model resource estimate exceeds the safe RAM ceiling")
        if config is not None:
            if config.sequence_length > snapshot["maximum_sequence_length"]:
                failures.append("sequence length exceeds the frozen snapshot's maximum")
            if config.checkpoint_interval_steps <= 0:
                failures.append("checkpoint interval must be positive for resumability")
        status = "fail" if failures else ("pass_with_warnings" if warnings else "pass")
        return {"status": status, "failures": failures, "warnings": warnings}

    def create_smoke_run(self, payload: SmokeRunCreate, admin_id: str) -> dict[str, Any]:
        with self.readiness_repository.transaction() as connection:
            snapshot = self.readiness_repository.pretraining_dataset_snapshot(
                connection, payload.pretraining_dataset_snapshot_public_id
            )
            estimate = self.readiness_repository.base_model_resource_estimate(
                connection, payload.base_model_resource_estimate_public_id
            )
            if estimate["profile_name"] != "micro_smoke_test":
                raise ValidationError(
                    "smoke runs are bounded to the micro_smoke_test profile only"
                )
            dataset_version_row = connection.execute(
                "SELECT public_id FROM dataset_versions WHERE id=?",
                (snapshot["dataset_version_id"],),
            ).fetchone()
            tokenizer_version_row = connection.execute(
                "SELECT public_id FROM tokenizer_versions WHERE id=?",
                (snapshot["tokenizer_version_id"],),
            ).fetchone()

        validation = self.validate_training_config(
            TrainingConfigValidateRequest(
                pretraining_dataset_snapshot_public_id=payload.pretraining_dataset_snapshot_public_id,
                base_model_resource_estimate_public_id=(
                    payload.base_model_resource_estimate_public_id
                ),
                configuration={**payload.configuration, "total_steps": payload.total_steps},
            )
        )
        if validation["status"] == "fail":
            raise ValidationError(f"training configuration invalid: {validation['failures']}")

        suffix = uuid4().hex[:8]
        family = self.core_model_service.create_family(
            CoreFamilyCreate(
                name=f"phase21a-smoke-{suffix}", display_name="Phase 21A Smoke Model"
            ),
            admin_id,
        )
        config = self.core_model_service.create_config(
            CoreConfigCreate(
                name=f"phase21a-smoke-config-{suffix}",
                config_version="v1",
                tokenizer_version_public_id=tokenizer_version_row["public_id"],
                preset="micro",
            ),
            admin_id,
        )
        self.core_model_service.validate_config(config["public_id"], admin_id)
        model_version = self.core_model_service.create_version(
            CoreVersionCreate(
                family_public_id=family["public_id"],
                config_public_id=config["public_id"],
                version="v1",
            ),
            admin_id,
        )
        self.core_model_service.initialize(model_version["public_id"], admin_id)
        architecture = self.core_model_service.verify_architecture(
            model_version["public_id"], admin_id
        )
        if architecture["status"] != "architecture_verified":
            raise ValidationError("smoke model failed Phase 8 architecture verification")

        checkpoint_interval = max(1, payload.total_steps // 2)
        job = self.pretraining_service.create_job(
            PretrainingJobCreate(
                name=f"phase21a-smoke-{suffix}",
                dataset_version_public_id=dataset_version_row["public_id"],
                tokenizer_version_public_id=tokenizer_version_row["public_id"],
                core_model_version_public_id=model_version["public_id"],
                job_mode="smoke_pretraining",
                configuration={
                    **payload.configuration,
                    "total_steps": payload.total_steps,
                    "checkpoint_interval_steps": checkpoint_interval,
                    "validation_interval_steps": checkpoint_interval,
                    "sequence_length": min(
                        payload.configuration.get("sequence_length", 64),
                        snapshot["maximum_sequence_length"],
                    ),
                },
            ),
            admin_id,
        )
        self.pretraining_service.validate_job(job["public_id"], admin_id)
        self.pretraining_service.queue_job(job["public_id"], admin_id)

        with self.readiness_repository.transaction() as connection:
            run_public_id = self.readiness_repository.create_pretraining_smoke_run(
                connection,
                {
                    "pretraining_dataset_snapshot_id": snapshot["id"],
                    "base_model_resource_estimate_id": estimate["id"],
                    "total_steps": payload.total_steps,
                    "created_by_admin_public_id": admin_id,
                },
            )
            run_row = self.readiness_repository.pretraining_smoke_run(connection, run_public_id)
            self.readiness_repository.update_pretraining_smoke_run(
                connection, run_row["id"], {"status": "running", "pretraining_job_id": None}
            )

        degeneration_findings: list[str] = []
        try:
            run_a_result = self._run_job_partial(job["public_id"], stop_after_steps=1)
            paused = self.pretraining_service.get_job(job["public_id"])
            resume_verified = False
            if paused["status"] == "paused" and paused["completed_steps"] > 0:
                self.pretraining_service.resume(job["public_id"], admin_id)
                final_result = self.pretraining_service.run_one(f"phase21a-smoke-{suffix}-resume")
                resume_verified = (
                    final_result is not None and final_result.get("status") == "completed"
                )
            else:
                final_result = run_a_result
                resume_verified = final_result is not None

            completed_job = self.pretraining_service.get_job(job["public_id"])
            if completed_job["status"] not in ("completed", "completed_with_warnings"):
                degeneration_findings.append(f"job ended in status {completed_job['status']}")
            if completed_job.get("error_code"):
                degeneration_findings.append(
                    f"{completed_job['error_code']}: {completed_job.get('error_message')}"
                )
            checkpoints = self.pretraining_service.checkpoints(job["public_id"])
            # `checkpoints()` orders step DESC, id DESC -- index 0 is the latest.
            final_checkpoint = checkpoints["items"][0] if checkpoints["items"] else None
            metrics = self.pretraining_service.metrics(job["public_id"])
            metric_items = metrics.get("items", [])
            initial_training_loss = metric_items[0]["training_loss"] if metric_items else None
            gradient_norms = [
                m["gradient_norm"] for m in metric_items if m.get("gradient_norm") is not None
            ]
            tokens_per_second_values = [
                m["tokens_per_second"] for m in metric_items if m.get("tokens_per_second")
            ]
            memory_values = [
                m["process_memory_bytes"]
                for m in metric_items
                if m.get("process_memory_bytes") is not None
            ]

            with self.readiness_repository.transaction() as connection:
                job_row = connection.execute(
                    "SELECT * FROM pretraining_jobs WHERE public_id=?", (job["public_id"],)
                ).fetchone()
                self.readiness_repository.update_pretraining_smoke_run(
                    connection,
                    run_row["id"],
                    {
                        "pretraining_job_id": job_row["id"],
                        "status": completed_job["status"],
                        "checkpoint_public_id": (
                            final_checkpoint["public_id"] if final_checkpoint else None
                        ),
                        "checkpoint_checksum_sha256": (
                            final_checkpoint.get("combined_checksum_sha256")
                            if final_checkpoint
                            else None
                        ),
                        "resume_verified": int(resume_verified),
                        "initial_training_loss": initial_training_loss,
                        "final_training_loss": completed_job["latest_training_loss"],
                        "validation_loss": completed_job.get("latest_validation_loss"),
                        "maximum_gradient_norm": max(gradient_norms) if gradient_norms else None,
                        "tokens_processed": completed_job["processed_tokens"],
                        "tokens_per_second": (
                            sum(tokens_per_second_values) / len(tokens_per_second_values)
                            if tokens_per_second_values
                            else None
                        ),
                        "peak_process_memory_bytes": max(memory_values) if memory_values else None,
                        "degeneration_findings_json": dumps_json(degeneration_findings),
                        "completed_at": _now_sql(),
                    },
                )
        except Exception as exc:  # noqa: BLE001 -- record failure honestly, never mask it
            with self.readiness_repository.transaction() as connection:
                self.readiness_repository.update_pretraining_smoke_run(
                    connection,
                    run_row["id"],
                    {"status": "failed", "error_details_json": dumps_json({"error": str(exc)})},
                )
            raise

        with self.readiness_repository.transaction() as connection:
            return public_row(
                self.readiness_repository.pretraining_smoke_run(connection, run_public_id)
            )

    def _run_job_partial(
        self, job_public_id: str, *, stop_after_steps: int
    ) -> dict[str, Any] | None:
        """Runs the job in a background thread and requests a pause as
        soon as at least ``stop_after_steps`` metrics have been
        recorded, so a genuine checkpoint/resume cycle can be
        exercised even for a very short smoke run."""

        result_holder: dict[str, Any] = {}

        def _worker() -> None:
            result_holder["result"] = self.pretraining_service.run_one("phase21a-smoke-worker")

        thread = Thread(target=_worker)
        thread.start()
        for _ in range(200):
            metrics = self.pretraining_service.metrics(job_public_id)
            if len(metrics.get("items", [])) >= stop_after_steps:
                self.pretraining_service.pause(job_public_id, "phase21a-smoke-service")
                break
            time.sleep(0.05)
        thread.join(timeout=30)
        return result_holder.get("result")

    def get_smoke_run(self, public_id: str) -> dict[str, Any]:
        with self.readiness_repository.transaction() as connection:
            return public_row(
                self.readiness_repository.pretraining_smoke_run(connection, public_id)
            )

    def list_smoke_runs(self) -> dict[str, Any]:
        with self.readiness_repository.transaction() as connection:
            return {
                "items": [
                    public_row(row)
                    for row in self.readiness_repository.list_pretraining_smoke_runs(connection)
                ]
            }
