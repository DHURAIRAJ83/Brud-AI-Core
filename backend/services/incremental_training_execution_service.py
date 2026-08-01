"""Phase 14 Step 14 bounded incremental training execution.

A thin governance wrapper -- never reimplements training. Once a run
approval is `approved` and its fingerprint still matches the run
request's current state (Step 13's staleness guard), this service
delegates the actual execution to the *existing, unmodified*
`InstructionTuningService` (strategy `incremental_sft`) or
`PretrainingService` (strategy `continued_pretraining`), reusing their
worker claim/lease/checkpoint/crash-recovery machinery unchanged. Both
of those already run a job synchronously to completion (or to
pause/cancel) inside one `run_one()` call, which satisfies "bounded,
resumable, staged execution" without any new background
infrastructure. Every produced checkpoint is mirrored into
`incremental_training_checkpoints`, referencing the underlying
checkpoint by public id -- it is never copied or duplicated. See
docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.instruction_tuning import InstructionTuningRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.instruction_tuning import (
    InstructionTuningExperimentCreate,
    InstructionTuningExperimentPatch,
    InstructionTuningRunCreate,
)
from backend.models.pretraining import PretrainingJobCreate
from backend.services.incremental_training_run_approval_service import run_request_fingerprint
from backend.services.instruction_tuning_service import InstructionTuningService
from backend.services.pretraining_service import PretrainingService
from core_model.training_incremental import EXECUTABLE_TRAINING_STRATEGIES, TRAINING_STRATEGIES

logger = logging.getLogger(__name__)


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"incremental_training_run_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="incremental_training_run",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("incremental_training_run_audit_write_failed", extra={"action": action})


class IncrementalTrainingExecutionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._pretraining_repository = PretrainingRepository(settings.resolved_database_path)
        self._pretraining = PretrainingService(self._pretraining_repository, settings)
        self._instruction_tuning = InstructionTuningService(
            InstructionTuningRepository(settings.resolved_database_path),
            self._pretraining_repository,
            settings,
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _validated_approval(self, run_approval_public_id: str) -> tuple[dict, dict]:
        approval = self._training.get_run_approval(run_approval_public_id)
        if approval["status"] != "approved":
            raise ValidationError("only an approved training run approval may start a run")
        if approval["expires_at"] and approval["expires_at"] < datetime.now(UTC).isoformat():
            self._training.mark_run_approval_expired(run_approval_public_id)
            raise ValidationError(
                "this training run approval has expired -- request and approve a fresh one"
            )
        run_request = self._training.get_run_request(approval["run_request_public_id"])
        if run_request_fingerprint(run_request) != approval["target_fingerprint"]:
            raise ValidationError(
                "the run request changed since this approval was granted -- this approval is "
                "stale; request a fresh approval"
            )
        if run_request["training_strategy"] not in EXECUTABLE_TRAINING_STRATEGIES:
            raise ValidationError(
                f"training_strategy '{run_request['training_strategy']}' does not execute a "
                "training run -- use acknowledge_no_execution_strategy() instead"
            )
        return approval, run_request

    def acknowledge_no_execution_strategy(
        self, run_approval_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        """For `tokenizer_only_assessment`/`no_training_rag_only` -- these
        strategies are themselves the terminal governance decision; no
        underlying job is ever created."""

        approval = self._training.get_run_approval(run_approval_public_id)
        if approval["status"] != "approved":
            raise ValidationError("only an approved training run approval may be acknowledged")
        run_request = self._training.get_run_request(approval["run_request_public_id"])
        if run_request["training_strategy"] in EXECUTABLE_TRAINING_STRATEGIES:
            raise ValidationError(
                f"training_strategy '{run_request['training_strategy']}' is executable -- use "
                "start_run() instead"
            )
        if run_request["training_strategy"] not in TRAINING_STRATEGIES:
            raise ValidationError(
                f"unknown training_strategy: {run_request['training_strategy']!r}"
            )
        updated = self._training.update_run_request(run_request["public_id"], {"status": "started"})
        _audit(
            self._audit, action="acknowledge_no_execution", actor_reference=admin_id,
            resource_public_id=run_request["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"training_strategy": run_request["training_strategy"]},
        )
        return updated

    def start_run(self, run_approval_public_id: str, *, admin_id: str) -> dict[str, Any]:
        approval, run_request = self._validated_approval(run_approval_public_id)
        configuration = run_request["configuration"]

        if run_request["training_strategy"] == "continued_pretraining":
            underlying_kind, underlying_public_id = self._start_continued_pretraining(
                run_request, configuration, admin_id
            )
        else:
            underlying_kind, underlying_public_id = self._start_incremental_sft(
                run_request, configuration, admin_id
            )

        run = self._training.create_run(
            run_request["public_id"],
            {
                "run_approval_public_id": run_approval_public_id,
                "underlying_run_kind": underlying_kind,
                "underlying_run_public_id": underlying_public_id,
                "created_by_admin_public_id": admin_id,
            },
        )
        self._training.update_run_request(run_request["public_id"], {"status": "started"})
        self._training.record_run_event(
            run["public_id"],
            {
                "event_type": "run_started", "from_status": "queued", "to_status": "running",
                "summary": f"delegated to {underlying_kind} {underlying_public_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="start", actor_reference=admin_id,
            resource_public_id=run["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"underlying_run_kind": underlying_kind},
        )

        started_at = datetime.now(UTC).isoformat()
        result = self._execute_synchronously(underlying_kind, underlying_public_id)

        final_status = result["status"]
        self._training.update_run(
            run["public_id"],
            {
                "status": final_status,
                "latest_training_loss": result.get("final_loss"),
                "latest_validation_loss": result.get("validation_loss"),
                "current_step": result.get("processed_tokens"),
                "started_at": started_at,
                "completed_at": (
                    datetime.now(UTC).isoformat() if final_status.startswith("completed") else None
                ),
            },
        )
        self._training.record_run_event(
            run["public_id"],
            {
                "event_type": "run_finished", "from_status": "running", "to_status": final_status,
                "summary": f"underlying job finished with status {final_status}",
                "metadata": {k: v for k, v in result.items() if k != "status"},
                "performed_by_admin_public_id": admin_id,
            },
        )
        if result.get("checkpoint_public_id"):
            self._training.add_checkpoint(
                run["public_id"],
                {
                    "underlying_checkpoint_public_id": result["checkpoint_public_id"],
                    "step": result.get("processed_tokens"),
                    "training_loss": result.get("final_loss"),
                    "validation_loss": result.get("validation_loss"),
                },
            )
        _audit(
            self._audit, action="finish", actor_reference=admin_id,
            resource_public_id=run["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"status": final_status},
        )
        return self._training.get_run(run["public_id"])

    def _start_continued_pretraining(
        self, run_request: dict[str, Any], configuration: dict[str, Any], admin_id: str
    ) -> tuple[str, str]:
        if not run_request["tokenizer_version_public_id"]:
            raise ValidationError("continued_pretraining requires a tokenizer_version_public_id")
        core_model_version_public_id = configuration.get("core_model_version_public_id")
        if not core_model_version_public_id:
            raise ValidationError(
                "continued_pretraining requires configuration.core_model_version_public_id"
            )
        job = self._pretraining.create_job(
            PretrainingJobCreate(
                name=f"phase14-continued-pretraining-{uuid4().hex[:8]}",
                dataset_version_public_id=run_request["dataset_version_public_id"],
                tokenizer_version_public_id=run_request["tokenizer_version_public_id"],
                core_model_version_public_id=core_model_version_public_id,
                job_mode="bounded_pretraining",
                configuration=configuration,
            ),
            admin_id,
        )
        self._pretraining.validate_job(job["public_id"], admin_id)
        self._pretraining.queue_job(job["public_id"], admin_id)
        return "pretraining_job", job["public_id"]

    def _start_incremental_sft(
        self, run_request: dict[str, Any], configuration: dict[str, Any], admin_id: str
    ) -> tuple[str, str]:
        base_core_model_version_public_id = configuration.get("base_core_model_version_public_id")
        instruction_template_public_id = configuration.get("instruction_template_public_id")
        if not base_core_model_version_public_id or not instruction_template_public_id:
            raise ValidationError(
                "incremental_sft requires configuration.base_core_model_version_public_id and "
                "configuration.instruction_template_public_id"
            )
        experiment = self._instruction_tuning.create_experiment(
            InstructionTuningExperimentCreate(
                name=f"phase14-incremental-sft-{uuid4().hex[:8]}",
                objective="phase14_incremental_language_training",
                base_core_model_version_public_id=base_core_model_version_public_id,
                dataset_version_public_id=run_request["dataset_version_public_id"],
                training_configuration=configuration,
            ),
            admin_id,
        )
        self._instruction_tuning.patch_experiment(
            experiment["public_id"],
            InstructionTuningExperimentPatch(
                instruction_template_public_id=instruction_template_public_id
            ),
            admin_id,
        )
        run = self._instruction_tuning.create_run(
            experiment["public_id"],
            InstructionTuningRunCreate(run_label="phase14-run", configuration=configuration),
            admin_id,
        )
        self._instruction_tuning.queue_run(run["public_id"], admin_id)
        return "instruction_tuning_run", run["public_id"]

    def _execute_synchronously(
        self, underlying_kind: str, underlying_public_id: str
    ) -> dict[str, Any]:
        worker_id = f"phase14-worker-{uuid4().hex[:8]}"
        if underlying_kind == "pretraining_job":
            result = self._pretraining.run_one(worker_id)
        else:
            result = self._instruction_tuning.run_one(worker_id)
        if result is None:
            raise ValidationError(
                f"no claimable job was found for {underlying_kind} {underlying_public_id} -- "
                "it may already be running or in an unexpected state"
            )
        return result


__all__ = ["IncrementalTrainingExecutionService"]
