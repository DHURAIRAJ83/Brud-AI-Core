"""Controlled recovery of stale, crashed, or paused pretraining jobs.

A job is never resumed without first validating its latest checkpoint. If
validation fails the checkpoint is marked corrupt and the failure is recorded;
there is no automatic fallback to an earlier checkpoint.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.pretraining import PretrainingRepository, public_row
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.database.repositories.training_reliability import public_row as reliability_public_row
from core_model.architecture.config import BrudModelConfig
from core_model.checkpoints.recovery_validator import validate_checkpoint_for_recovery
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

RECOVERY_TYPES = {
    "pause_resume",
    "manual_resume",
    "stale_lease",
    "worker_crash",
    "checkpoint_recovery",
}


class WorkerRecoveryService:
    def __init__(
        self,
        repository: PretrainingRepository,
        reliability: TrainingReliabilityRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.reliability = reliability
        self.settings = settings

    def stale_jobs(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.reliability.stale_jobs(connection)
            items = [public_row(self.repository.job(connection, row["public_id"])) for row in rows]
        return {"items": items}

    def recoveries(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            rows = self.reliability.recovery_attempts(connection, job["id"])
        return {"items": [reliability_public_row(row) for row in rows]}

    def recovery(self, recovery_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.reliability.recovery_attempt(connection, recovery_public_id)
        return reliability_public_row(row)

    def verify_resume(self, job_public_id: str) -> dict[str, Any]:
        """Read-only dry check of whether the job's latest checkpoint would pass recovery."""

        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            checkpoint_row, validation_summary, failures, recovered_step, recovered_tokens = (
                self._validate_latest_checkpoint(connection, job)
            )
        return {
            "would_succeed": not failures,
            "checkpoint_public_id": checkpoint_row["public_id"] if checkpoint_row else None,
            "recovered_step": recovered_step,
            "recovered_tokens": recovered_tokens,
            "validation": validation_summary,
        }

    def _validate_latest_checkpoint(
        self, connection, job
    ) -> tuple[Any, dict[str, Any], list[str], int | None, int | None]:
        checkpoint_row = connection.execute(
            """SELECT * FROM pretraining_checkpoints
            WHERE pretraining_job_id=? AND is_latest=1
            ORDER BY step DESC, id DESC LIMIT 1""",
            (job["id"],),
        ).fetchone()

        if checkpoint_row is None:
            return (
                None,
                {"checkpoint": None, "note": "no checkpoint exists; resuming from step 0"},
                [],
                None,
                None,
            )

        checkpoint = dict(checkpoint_row)
        dataset_checksum_actual = connection.execute(
            "SELECT checksum_sha256 FROM dataset_versions WHERE id=?",
            (job["dataset_version_id"],),
        ).fetchone()[0]
        tokenizer_checksum_actual = connection.execute(
            "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE id=?",
            (job["tokenizer_version_id"],),
        ).fetchone()[0]
        model_config_checksum_actual = connection.execute(
            """SELECT c.config_checksum_sha256 FROM core_model_configs c
            JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
            (job["core_model_version_id"],),
        ).fetchone()[0]
        model_config_row = connection.execute(
            """SELECT c.* FROM core_model_configs c
            JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
            (job["core_model_version_id"],),
        ).fetchone()
        prior = connection.execute(
            """SELECT step, processed_tokens FROM pretraining_checkpoints
            WHERE pretraining_job_id=? AND id<? ORDER BY step DESC, id DESC LIMIT 1""",
            (job["id"], checkpoint["id"]),
        ).fetchone()
        step_monotonic = prior is None or checkpoint["step"] >= prior["step"]
        token_monotonic = (
            prior is None or checkpoint["processed_tokens"] >= prior["processed_tokens"]
        )

        model_config = BrudModelConfig(
            vocabulary_size=model_config_row["vocabulary_size"],
            context_length=model_config_row["context_length"],
            hidden_size=model_config_row["hidden_size"],
            intermediate_size=model_config_row["intermediate_size"],
            num_hidden_layers=model_config_row["num_hidden_layers"],
            num_attention_heads=model_config_row["num_attention_heads"],
            num_key_value_heads=model_config_row["num_key_value_heads"],
            pad_token_id=model_config_row["pad_token_id"],
            bos_token_id=model_config_row["bos_token_id"],
            eos_token_id=model_config_row["eos_token_id"],
            unk_token_id=model_config_row["unk_token_id"],
        )
        checkpoint_dir = self.settings.resolved_pretraining_dir / checkpoint["safe_name"]

        references: dict[str, Any] = {}
        manager = TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
        )
        try:
            manager.verify(checkpoint_dir)
            states = manager.load_states(checkpoint_dir)
            references = states.get("references", {})
        except (OSError, ValueError, RuntimeError):
            references = {}

        validation = validate_checkpoint_for_recovery(
            checkpoint_row=checkpoint,
            checkpoint_dir=checkpoint_dir,
            max_bytes=self.settings.core_checkpoint_max_bytes,
            model_config=model_config,
            dataset_checksum_expected=references.get("dataset_checksum_sha256"),
            dataset_checksum_actual=dataset_checksum_actual,
            tokenizer_checksum_expected=references.get("tokenizer_checksum_sha256"),
            tokenizer_checksum_actual=tokenizer_checksum_actual,
            model_config_checksum_expected=references.get("model_config_checksum_sha256"),
            model_config_checksum_actual=model_config_checksum_actual,
            stream_checksum_expected=references.get("stream_checksum_sha256"),
            stream_checksum_actual=job["latest_stream_checksum_sha256"],
            step_monotonic=step_monotonic,
            token_monotonic=token_monotonic,
        )
        validation_summary = {"checks": validation.checks, "failures": validation.failures}
        return (
            checkpoint_row,
            validation_summary,
            validation.failures,
            validation.recovered_step,
            validation.recovered_tokens,
        )

    def recover(
        self, job_public_id: str, initiator_id: str, recovery_type: str, comment: str | None = None
    ) -> dict[str, Any]:
        if recovery_type not in RECOVERY_TYPES:
            raise ValidationError("unsupported recovery type")
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            if recovery_type == "pause_resume" and job["status"] != "paused":
                raise ValidationError("pause_resume recovery requires a paused job")
            if recovery_type in {"stale_lease", "worker_crash"} and not job["recovery_required"]:
                raise ValidationError("job is not flagged as requiring recovery")
            if recovery_type in {"manual_resume", "checkpoint_recovery"} and job["status"] not in {
                "failed",
                "paused",
                "queued",
            }:
                raise ValidationError("job status does not allow manual recovery")

            previous_generation = job["lease_generation"]
            new_generation = previous_generation + 1
            checkpoint_row, validation_summary, failures, recovered_step, recovered_tokens = (
                self._validate_latest_checkpoint(connection, job)
            )

            if failures:
                connection.execute(
                    "UPDATE pretraining_checkpoints SET status='corrupt' WHERE public_id=?",
                    (checkpoint_row["public_id"],),
                )

            status = "failed" if failures else "completed"
            self.reliability.record_recovery_attempt(
                connection,
                job["id"],
                {
                    "recovery_type": recovery_type,
                    "status": status,
                    "source_worker_id": job["worker_id"],
                    "recovering_worker_id": initiator_id,
                    "source_checkpoint_public_id": (
                        checkpoint_row["public_id"] if checkpoint_row else None
                    ),
                    "previous_lease_generation": previous_generation,
                    "new_lease_generation": new_generation,
                    "recovered_step": recovered_step,
                    "recovered_tokens": recovered_tokens,
                    "validation_summary_json": dumps_json(validation_summary),
                    "error_code": "checkpoint_validation_failed" if failures else None,
                    "error_message": "; ".join(failures)[:500] if failures else None,
                },
            )

            if failures:
                connection.execute(
                    """UPDATE pretraining_jobs SET status='failed',
                    error_code='recovery_checkpoint_corrupt',
                    error_message=?,failed_at=CURRENT_TIMESTAMP,lease_generation=?,updated_at=CURRENT_TIMESTAMP
                    WHERE id=?""",
                    ("; ".join(failures)[:500], new_generation, job["id"]),
                )
                self.repository.add_event(
                    connection, job["id"], "recovery_failed", job["status"], "failed",
                    dumps_json({"recovery_type": recovery_type, "failures": failures}),
                )
                self._audit(
                    connection, "training_recovery_failed", initiator_id, job_public_id,
                    recovery_type=recovery_type,
                )
                return {"status": "failed", "failures": failures}

            # Roll the job's step/token counters back to exactly what the
            # recovered checkpoint reflects. Metrics can be logged more often
            # than checkpoints are saved, so completed_steps may be ahead of
            # the last verified checkpoint at crash time; resuming from the
            # job's counters instead of the checkpoint's would silently lose
            # those in-between steps' training effect while claiming they
            # happened.
            connection.execute(
                """UPDATE pretraining_jobs SET status='queued',recovery_required=0,
                pause_requested=0,cancel_requested=0,
                completed_steps=?,processed_tokens=?,
                lease_generation=?,worker_id=NULL,lease_expires_at=NULL,updated_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (recovered_step or 0, recovered_tokens or 0, new_generation, job["id"]),
            )
            self.repository.add_event(
                connection, job["id"], "recovery_completed", job["status"], "queued",
                dumps_json({"recovery_type": recovery_type, "recovered_step": recovered_step}),
            )
            self._audit(
                connection, "training_recovery_completed", initiator_id, job_public_id,
                recovery_type=recovery_type, comment=comment,
            )
            return {
                "status": "completed",
                "recovered_step": recovered_step,
                "recovered_tokens": recovered_tokens,
                "new_lease_generation": new_generation,
            }

    def _audit(
        self, connection, event: str, actor_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event,
                "admin",
                "{}",
                str(uuid4()),
                event,
                "admin",
                actor_id,
                "pretraining",
                resource_id,
                "success" if event.endswith("completed") else "failure",
                dumps_json(metadata),
            ),
        )
