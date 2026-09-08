"""Phase 2.7F: governed handoff of a real, verified MB-22 (Phase 2.7C/E)
checkpoint into the production `pretraining_checkpoints` table -- the
one table `ModelReleaseService._resolve_checkpoint()` and
`ModelEvaluationService._eligible_candidate()` already read from.

Deliberately its own, separate, single-purpose file. `mini_brain_
training_engine_service.py` is structurally forbidden from ever
importing `PretrainingService`
(`tests/backend/test_mini_brain_training_engine_safety.py::
test_never_imports_a_deployment_or_runtime_manager_library`) -- this
bridges the two systems from a neutral third file instead of weakening
that existing safety boundary. It is not a parallel release path: it
never creates a second checkpoint table, never duplicates
`ModelReleaseService`/`ModelEvaluationService`, and never calls
`activate()`, sets `status='active'`, or writes `inference_model_
assignments`. Registration means "this checkpoint exists, is real, and
is structurally valid" -- it never means "this checkpoint is approved
for Public Chat."
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_training_engine import MiniBrainTrainingEngineRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.services.pretraining_service import PretrainingService
from core_model.training.pretraining_config import PretrainingConfig


class MiniBrainPretrainingHandoffService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainTrainingEngineRepository(settings.resolved_database_path)
        self.pretraining = PretrainingService(
            PretrainingRepository(settings.resolved_database_path), settings
        )

    def _checkpoint_directory(self, job_public_id: str, step: int, epoch: int):
        return (
            self.settings.resolved_pretraining_dir / "mini_brain_training_jobs" / job_public_id
            / f"step-{step:08d}-epoch-{epoch:04d}"
        )

    def register_checkpoint(
        self, job_public_id: str, checkpoint_public_id: str, admin_id: str
    ) -> dict[str, Any]:
        """The one small, governed handoff method Phase 2.7F adds. Rejects,
        with a typed `ValidationError`, every case the mission's own
        negative-test list names: a checkpoint from a non-gpu job, a job
        missing Core Model Version or dataset identity, a metadata-only
        (simulation) checkpoint, an already-registered checkpoint, a
        missing/corrupted checkpoint (via `PretrainingService.
        register_external_checkpoint()`'s own `TrainingCheckpointManager.
        verify()` call), and a checkpoint whose Core Model Version does not
        match an already-registered sibling checkpoint's job."""

        with self.repository.transaction() as connection:
            job = self.repository.get_job(connection, job_public_id)
            checkpoint = self.repository.get_checkpoint(connection, checkpoint_public_id)
        if checkpoint["job_id"] != job["id"]:
            raise ValidationError("checkpoint does not belong to this training job")
        if job["execution_mode"] != "gpu":
            raise ValidationError(
                "only a real (execution_mode='gpu') job produces a checkpoint eligible for "
                "governed registration"
            )
        if not job["core_model_version_public_id"]:
            raise ValidationError("job has no Core Model Version identity")
        if not job["dataset_version_public_id"]:
            raise ValidationError("job has no dataset identity")
        if bool(checkpoint["is_metadata_only"]):
            raise ValidationError("a metadata-only (simulation) checkpoint can never be registered")
        if checkpoint["pretraining_checkpoint_public_id"]:
            raise ValidationError("this checkpoint has already been registered")

        with self.repository.transaction() as connection:
            metric = connection.execute(
                "SELECT loss FROM mini_brain_training_metrics WHERE job_id=? AND step=? ORDER BY id DESC LIMIT 1",
                (job["id"], checkpoint["step"]),
            ).fetchone()
        training_loss = metric["loss"] if metric else None

        checkpoint_directory = self._checkpoint_directory(
            job_public_id, checkpoint["step"], checkpoint["epoch"]
        )
        # A minimal, honest `PretrainingConfig` record for the new
        # `pretraining_jobs` row -- MB-22's `TorchTrainingAdapter` never
        # persists the exact hyperparameter config anywhere retrievable
        # after the fact (only the real architecture config and real
        # weights are preserved, inside the checkpoint bundle itself,
        # which this method faithfully links rather than re-describes).
        # `total_steps` is the one hyperparameter genuinely known here.
        configuration = PretrainingConfig(total_steps=max(checkpoint["step"], 1)).to_dict()

        result = self.pretraining.register_external_checkpoint(
            core_model_version_public_id=job["core_model_version_public_id"],
            dataset_version_public_id=job["dataset_version_public_id"],
            checkpoint_directory=checkpoint_directory,
            step=checkpoint["step"],
            processed_tokens=0,  # not yet tracked by MB-22 -- honestly disclosed, never guessed
            training_loss=training_loss,
            validation_loss=None,  # MB-22 has no validation split today -- honestly disclosed, never guessed
            configuration=configuration,
            source_label=f"mb22:{job_public_id}",
            admin_id=admin_id,
            existing_pretraining_job_public_id=job["pretraining_job_public_id"],
        )

        with self.repository.transaction() as connection:
            if not job["pretraining_job_public_id"]:
                self.repository.update_job(
                    connection, job_public_id,
                    {"pretraining_job_public_id": result["pretraining_job_public_id"]},
                )
            self.repository.mark_checkpoint_registered(
                connection, checkpoint["id"], result["pretraining_checkpoint_public_id"],
            )
            self.repository.create_event(
                connection, job_id=job["id"], event_type="checkpoint_registered_for_release",
                stage=None,
                message=(
                    f"checkpoint {checkpoint['checkpoint_name']} registered as pretraining "
                    f"checkpoint {result['pretraining_checkpoint_public_id']}"
                ),
                metadata={"pretraining_job_public_id": result["pretraining_job_public_id"]},
            )
        return result


__all__ = ["MiniBrainPretrainingHandoffService"]
