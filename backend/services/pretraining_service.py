"""Bounded pretraining service and local worker implementation."""

from __future__ import annotations

import hashlib
import math
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import numpy as np

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json, redact_secrets
from backend.database.repositories.base import ValidationError
from backend.database.repositories.pretraining import PretrainingRepository, public_row
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.models.pretraining import PretrainingJobCreate, PretrainingJobPatch
from backend.services.tokenizer_registry import TokenizerService
from backend.services.worker_recovery_service import WorkerRecoveryService
from core_model.architecture.config import BrudModelConfig
from core_model.training.coverage import generate_coverage
from core_model.training.dataset_stream import token_sequences
from core_model.training.diagnostics import loss_improvement_ratio, safe_perplexity
from core_model.training.packing import pack_stream
from core_model.training.pretraining_config import from_mapping


class StaleWorkerError(RuntimeError):
    """Raised when a worker's lease was taken over by another worker mid-run."""


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _page(items: list[dict[str, Any]], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


def _checksum(data: dict[str, Any]) -> str:
    return hashlib.sha256(dumps_json(data).encode("utf-8")).hexdigest()


def _safe(value: str) -> str:
    return (
        "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value).strip("._")
        or uuid4().hex
    )


class PretrainingService:
    def __init__(self, repository: PretrainingRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.reliability = TrainingReliabilityRepository(repository.database_path)

    def capabilities(self) -> dict[str, Any]:
        import torch

        return {
            "pytorch_version": torch.__version__,
            "numpy_version": np.__version__,
            "cpu_available": True,
            "cuda_available": bool(torch.cuda.is_available()),
            "supported_optimizers": ["adamw"],
            "supported_schedulers": ["constant", "linear_warmup_decay", "cosine"],
            "worker_mode": "separate_local_worker",
            "limits": {
                "max_steps": self.settings.pretraining_max_steps,
                "max_batch_size": self.settings.pretraining_max_batch_size,
                "max_sequence_length": self.settings.pretraining_max_sequence_length,
            },
        }

    def estimate(self, payload: PretrainingJobCreate) -> dict[str, Any]:
        config = from_mapping(payload.configuration)
        self._enforce_config(config)
        return {
            "estimated_tokens": config.total_steps * config.batch_size * config.sequence_length,
            "estimated_memory_bytes": self.settings.core_max_estimated_memory_bytes,
            "device": "cpu",
            "warnings": ["cpu_only_slow_execution"],
        }

    def preflight_payload(self, payload: PretrainingJobCreate) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            self._references(connection, payload)
        self._enforce_config(from_mapping(payload.configuration))
        return {
            "status": "pass_with_warnings",
            "warnings": ["cpu_only_slow_execution"],
            "failures": [],
        }

    def create_job(self, payload: PretrainingJobCreate, admin_id: str) -> dict[str, Any]:
        config = from_mapping(payload.configuration)
        self._enforce_config(config)
        with self.repository.transaction() as connection:
            dataset, tokenizer, model = self._references(connection, payload)
            public_id = str(uuid4())
            checksum = _checksum(
                payload.configuration
                | {"refs": [dataset["public_id"], tokenizer["public_id"], model["public_id"]]}
            )
            connection.execute(
                """INSERT INTO pretraining_jobs(public_id,name,status,dataset_version_id,
                tokenizer_version_id,core_model_version_id,job_mode,configuration_json,
                config_checksum_sha256,initialization_seed,sampling_seed,device,dtype,
                optimizer_name,scheduler_name,total_steps,total_tokens_target,
                gradient_accumulation_steps,learning_rate,created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    payload.name,
                    "draft",
                    dataset["id"],
                    tokenizer["id"],
                    model["id"],
                    payload.job_mode,
                    dumps_json(config.to_dict()),
                    checksum,
                    config.initialization_seed,
                    config.sampling_seed,
                    config.device,
                    config.dtype,
                    config.optimizer,
                    config.scheduler,
                    config.total_steps,
                    config.maximum_tokens,
                    config.gradient_accumulation_steps,
                    config.learning_rate,
                    admin_id,
                ),
            )
            job = self.repository.job(connection, public_id)
            self.repository.add_event(connection, job["id"], "job_created", None, "draft")
            self._audit(connection, "pretraining_job_created", admin_id, public_id)
            return public_row(job)

    def list_jobs(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM pretraining_jobs ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM pretraining_jobs").fetchone()[0]
        return _page([public_row(row) for row in rows], total, page, page_size)

    def get_job(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.job(connection, public_id))

    def patch_job(
        self,
        public_id: str,
        payload: PretrainingJobPatch,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            if job["status"] != "draft":
                raise ValidationError("only draft pretraining jobs can be edited")
            configuration = loads_json(job["configuration_json"])
            if payload.configuration is not None:
                config = from_mapping(payload.configuration)
                self._enforce_config(config)
                configuration = config.to_dict()
            name = payload.name or job["name"]
            connection.execute(
                """UPDATE pretraining_jobs SET name=?,configuration_json=?,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (name, dumps_json(configuration), job["id"]),
            )
            self._audit(connection, "pretraining_job_updated", admin_id, public_id)
            return public_row(self.repository.job(connection, public_id))

    def validate_job(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            connection.execute(
                "UPDATE pretraining_jobs SET status='validating' WHERE id=?", (job["id"],)
            )
            self.repository.add_event(
                connection, job["id"], "validation_completed", job["status"], "validating"
            )
            self._audit(
                connection,
                "pretraining_preflight",
                admin_id,
                public_id,
                status="pass_with_warnings",
            )
        return {
            "status": "pass_with_warnings",
            "warnings": ["cpu_only_slow_execution"],
            "failures": [],
        }

    def queue_job(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            if job["status"] not in {"draft", "validating", "paused", "resume_requested"}:
                raise ValidationError("job cannot be queued from current status")
            connection.execute(
                """UPDATE pretraining_jobs
                SET status='queued', queued_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (job["id"],),
            )
            self.repository.add_event(connection, job["id"], "job_queued", job["status"], "queued")
            self._audit(connection, "pretraining_job_queued", admin_id, public_id)
            return public_row(self.repository.job(connection, public_id))

    def pause(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._request(
            public_id, admin_id, "pause_requested", "pause_requested", "pause_requested"
        )

    def resume(self, public_id: str, admin_id: str) -> dict[str, Any]:
        recovery = WorkerRecoveryService(self.repository, self.reliability, self.settings).recover(
            public_id, admin_id, "pause_resume"
        )
        if recovery["status"] != "completed":
            raise ValidationError("checkpoint failed recovery validation and cannot resume")
        with self.repository.transaction() as connection:
            return public_row(self.repository.job(connection, public_id))

    def cancel(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._request(
            public_id, admin_id, "cancel_requested", "cancel_requested", "cancel_requested"
        )

    def run_one(self, worker_id: str) -> dict[str, Any] | None:
        with self.repository.transaction() as connection:
            self.reliability.register_worker(connection, worker_id)
            self.reliability.heartbeat(connection, worker_id, status="claiming")
        claimed = self._claim(worker_id)
        if not claimed:
            with self.repository.transaction() as connection:
                self.reliability.heartbeat(connection, worker_id, status="idle")
            return None
        job, lease_generation = claimed
        try:
            result = self._run_claimed(job, worker_id, lease_generation)
            return result
        except StaleWorkerError as exc:
            with self.repository.transaction() as connection:
                self.reliability.heartbeat(connection, worker_id, status="idle")
            return {"status": "stale", "error": "StaleWorkerError", "message": str(exc)[:200]}
        except Exception as exc:
            with self.repository.transaction() as connection:
                current = self.repository.job(connection, job["public_id"])
                if (
                    current["worker_id"] == worker_id
                    and current["lease_generation"] == lease_generation
                ):
                    connection.execute(
                        """UPDATE pretraining_jobs SET status='failed',error_code='training_failed',
                        error_message=?,failed_at=CURRENT_TIMESTAMP WHERE id=?""",
                        (str(exc)[:500], current["id"]),
                    )
                    self.repository.add_event(
                        connection, current["id"], "training_failed", current["status"], "failed"
                    )
                self.reliability.release_lease(connection, worker_id, reason="training_failed")
                self.reliability.heartbeat(connection, worker_id, status="failed")
            return {"status": "failed", "error": type(exc).__name__, "message": str(exc)[:200]}

    def events(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            rows = connection.execute(
                """SELECT event_type,previous_status,new_status,message,metadata_json,created_at
                FROM pretraining_job_events WHERE pretraining_job_id=? ORDER BY created_at,id""",
                (job["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def metrics(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            rows = connection.execute(
                """SELECT public_id,step,processed_tokens,epoch_fraction,training_loss,
                validation_loss,learning_rate,gradient_norm,tokens_per_second,
                step_duration_ms,cpu_percent,process_memory_bytes,
                system_available_memory_bytes,metadata_json,created_at
                FROM pretraining_metrics WHERE pretraining_job_id=? ORDER BY step""",
                (job["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def checkpoints(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            rows = connection.execute(
                """SELECT public_id,checkpoint_kind,status,step,processed_tokens,
                file_size_bytes,manifest_json,model_checksum_sha256,
                optimizer_checksum_sha256,scheduler_checksum_sha256,
                trainer_state_checksum_sha256,combined_checksum_sha256,
                training_loss,validation_loss,is_best,is_latest,created_at,verified_at
                FROM pretraining_checkpoints
                WHERE pretraining_job_id=?
                ORDER BY step DESC,id DESC""",
                (job["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def checkpoint(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = connection.execute(
                """SELECT public_id,checkpoint_kind,status,step,processed_tokens,
                file_size_bytes,manifest_json,model_checksum_sha256,
                optimizer_checksum_sha256,scheduler_checksum_sha256,
                trainer_state_checksum_sha256,combined_checksum_sha256,
                training_loss,validation_loss,is_best,is_latest,created_at,verified_at
                FROM pretraining_checkpoints WHERE public_id=?""",
                (public_id,),
            ).fetchone()
        return public_row(row)

    def verify_checkpoint(self, public_id: str, admin_id: str) -> dict[str, Any]:
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?", (public_id,)
            ).fetchone()
            if not row:
                raise ValidationError("checkpoint not found")
            target = self.settings.resolved_pretraining_dir / row["safe_name"]
            try:
                TrainingCheckpointManager(
                    self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
                ).verify(target)
                status = "verified"
            except (OSError, ValueError):
                status = "corrupt"
            connection.execute(
                """UPDATE pretraining_checkpoints
                SET status=?, verified_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (status, row["id"]),
            )
            self._audit(
                connection, "pretraining_checkpoint_verified", admin_id, public_id, status=status
            )
        return {"verified": status == "verified", "status": status}


    def evaluate(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            eval_id = str(uuid4())
            connection.execute(
                """INSERT INTO pretraining_evaluations(public_id,pretraining_job_id,
                evaluation_type,status,summary_json,completed_at)
                VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (
                    eval_id,
                    job["id"],
                    "validation_loss",
                    "completed",
                    dumps_json({"validation_loss": job["latest_validation_loss"]}),
                ),
            )
            connection.execute(
                """INSERT INTO pretraining_evaluation_results(public_id,pretraining_evaluation_id,
                metric_name,metric_value,details_json) VALUES (?,?,?,?,?)""",
                (
                    str(uuid4()),
                    connection.execute(
                        "SELECT id FROM pretraining_evaluations WHERE public_id=?",
                        (eval_id,),
                    ).fetchone()["id"],
                    "validation_loss",
                    job["latest_validation_loss"] or 0.0,
                    dumps_json({"finite": job["latest_validation_loss"] is not None}),
                ),
            )
            self._audit(connection, "pretraining_validation_completed", admin_id, public_id)
            row = connection.execute(
                "SELECT * FROM pretraining_evaluations WHERE public_id=?",
                (eval_id,),
            ).fetchone()
            return public_row(row)

    def evaluations(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            rows = connection.execute(
                """SELECT * FROM pretraining_evaluations
                WHERE pretraining_job_id=?
                ORDER BY created_at DESC""",
                (job["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def evaluation(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM pretraining_evaluations WHERE public_id=?",
                (public_id,),
            ).fetchone()
            results = (
                connection.execute(
                    """SELECT public_id,metric_name,metric_value,
                details_json,created_at FROM pretraining_evaluation_results
                WHERE pretraining_evaluation_id=? ORDER BY id""",
                    (row["id"],),
                ).fetchall()
                if row
                else []
            )
        data = public_row(row)
        data["results"] = [public_row(item) for item in results]
        return data

    def promote(
        self, checkpoint_public_id: str, admin_id: str, override_comment: str | None = None
    ) -> dict[str, Any]:
        verify = self.verify_checkpoint(checkpoint_public_id, admin_id)
        if not verify["verified"]:
            raise ValidationError("only verified checkpoints can promote")
        with self.repository.transaction() as connection:
            checkpoint = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?", (checkpoint_public_id,)
            ).fetchone()
            job = connection.execute(
                "SELECT * FROM pretraining_jobs WHERE id=?", (checkpoint["pretraining_job_id"],)
            ).fetchone()
            model = connection.execute(
                "SELECT * FROM core_model_versions WHERE id=?",
                (checkpoint["core_model_version_id"],),
            ).fetchone()
            if job["status"] not in {"completed", "completed_with_warnings"}:
                raise ValidationError("only completed jobs can promote")
            assessment = self.reliability.latest_quality_assessment(connection, job["id"])
            if assessment is None:
                raise ValidationError("a training quality assessment is required before promotion")
            readiness = assessment["readiness_status"]
            if readiness == "blocked":
                raise ValidationError("promotion is blocked by a non-overridable quality issue")
            if readiness == "warning" and not (override_comment and override_comment.strip()):
                raise ValidationError(
                    "promotion has warning-level quality issues and requires an override comment"
                )
            promoted_id = str(uuid4())
            connection.execute(
                """INSERT INTO core_model_versions(public_id,core_model_family_id,version,
                lifecycle_status,config_id,tokenizer_version_id,architecture_name,
                estimated_parameter_count,actual_parameter_count,
                estimated_inference_memory_bytes,estimated_training_memory_bytes,
                initialization_seed,weights_checksum_sha256,config_checksum_sha256,
                architecture_summary_json,metrics_summary_json,initialized_at,validated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",
                (
                    promoted_id,
                    model["core_model_family_id"],
                    f"{model['version']}-base-pretrained-{checkpoint['step']}",
                    "staging",
                    model["config_id"],
                    model["tokenizer_version_id"],
                    model["architecture_name"],
                    model["estimated_parameter_count"],
                    model["actual_parameter_count"],
                    model["estimated_inference_memory_bytes"],
                    model["estimated_training_memory_bytes"],
                    model["initialization_seed"],
                    checkpoint["model_checksum_sha256"],
                    model["config_checksum_sha256"],
                    dumps_json(
                        {
                            "base_pretrained": True,
                            "not_instruction_tuned": True,
                            "not_chat_ready": True,
                            "source_job_public_id": job["public_id"],
                        }
                    ),
                    dumps_json(
                        {
                            "training_loss": checkpoint["training_loss"],
                            "validation_loss": checkpoint["validation_loss"],
                        }
                    ),
                ),
            )
            self.repository.add_event(
                connection,
                job["id"],
                "model_promoted_to_staging",
                None,
                "staging",
                dumps_json(
                    {
                        "promoted_model_public_id": promoted_id,
                        "quality_readiness_status": readiness,
                        "override_comment": override_comment if readiness == "warning" else None,
                    }
                ),
            )
            self._audit(connection, "pretraining_checkpoint_promoted", admin_id, promoted_id)
            return {
                "promoted_model_version_public_id": promoted_id,
                "lifecycle_status": "staging",
                "not_chat_ready": True,
            }

    def _run_claimed(self, job, worker_id: str, lease_generation: int) -> dict[str, Any]:
        import torch

        from core_model.architecture.model import BrudForCausalLM
        from core_model.training.trainer import run_pretraining

        config = from_mapping(loads_json(job["configuration_json"]))
        model_config = self._model_config(job)
        torch.manual_seed(int(job["initialization_seed"]))
        model = BrudForCausalLM(model_config)
        train_blocks, validation_blocks = self._blocks(job, config)
        resume_state = self._latest_checkpoint_state(job, model) if job["completed_steps"] else {}
        started = time.perf_counter()
        initial_training_loss = job["latest_training_loss"] if job["completed_steps"] else None
        non_finite_events = 0

        def on_step(metric: dict[str, Any]) -> None:
            self._metric(job["public_id"], worker_id, lease_generation, metric)

        def on_checkpoint(**state: Any) -> None:
            self._save_periodic_checkpoint(job, worker_id, lease_generation, model, config, state)

        try:
            result = run_pretraining(
                model=model,
                train_blocks=train_blocks,
                validation_blocks=validation_blocks,
                config=config,
                pad_token_id=model_config.pad_token_id,
                start_step=job["completed_steps"],
                start_processed_tokens=job["processed_tokens"],
                start_block_index=resume_state.get("trainer_state", {}).get("block_index", 0),
                optimizer_state=resume_state.get("optimizer"),
                scheduler_state=resume_state.get("scheduler"),
                rng_state=resume_state.get("rng"),
                on_step=on_step,
                on_checkpoint=on_checkpoint,
                should_pause=lambda: self._flags(job["public_id"])[0],
                should_cancel=lambda: self._flags(job["public_id"])[1],
            )
        except ValueError as exc:
            if "non-finite" in str(exc):
                non_finite_events += 1
                with self.repository.transaction() as connection:
                    current = self.repository.job(connection, job["public_id"])
                    self.repository.add_event(
                        connection, current["id"], "non_finite_training_value",
                        current["status"], current["status"], dumps_json({"error": str(exc)}),
                    )
            raise
        checkpoint = self._save_training_checkpoint(
            job, worker_id, lease_generation, model, config, result
        )
        with self.repository.transaction() as connection:
            current = self.repository.job(connection, job["public_id"])
            status = "completed" if result.status == "completed" else result.status
            timestamp_column = {
                "completed": "completed_at",
                "completed_with_warnings": "completed_at",
                "paused": "paused_at",
                "cancelled": "cancelled_at",
            }.get(status)
            timestamp_sql = f",{timestamp_column}=CURRENT_TIMESTAMP" if timestamp_column else ""
            connection.execute(
                """UPDATE pretraining_jobs SET status=?,completed_steps=?,processed_tokens=?,
                latest_training_loss=?,latest_validation_loss=?,best_validation_loss=?,
                progress=?,worker_id=?,updated_at=CURRENT_TIMESTAMP"""
                + timestamp_sql
                + """
                WHERE id=?""",
                (
                    status,
                    result.completed_steps,
                    result.processed_tokens,
                    result.final_loss,
                    result.validation_loss,
                    result.validation_loss,
                    1.0 if status == "completed" else current["progress"],
                    worker_id,
                    current["id"],
                ),
            )
            event = {
                "completed": "training_completed",
                "paused": "job_paused",
                "cancelled": "job_cancelled",
            }.get(status, "training_completed_with_warnings")
            self.repository.add_event(
                connection,
                current["id"],
                event,
                current["status"],
                status,
                dumps_json(
                    {
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                        "checkpoint": checkpoint["public_id"],
                    }
                ),
            )
            self.reliability.release_lease(connection, worker_id, reason=f"job_{status}")
            self.reliability.heartbeat(connection, worker_id, status="idle")
        if status in {"completed", "completed_with_warnings"}:
            self._select_best_checkpoint(current["id"])
            self._generate_run_summary(
                current["id"],
                status=status,
                initial_training_loss=initial_training_loss,
                elapsed_seconds=time.perf_counter() - started,
                non_finite_event_count=non_finite_events,
            )
        return {
            "status": status,
            "checkpoint_public_id": checkpoint["public_id"],
            "initial_loss": result.initial_loss,
            "final_loss": result.final_loss,
            "validation_loss": result.validation_loss,
            "processed_tokens": result.processed_tokens,
        }

    def _latest_checkpoint_state(self, job, model) -> dict[str, Any]:
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        with self.repository.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM pretraining_checkpoints
                WHERE pretraining_job_id=? AND is_latest=1
                ORDER BY step DESC,id DESC LIMIT 1""",
                (job["id"],),
            ).fetchone()
        if not row:
            return {}
        manager = TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir,
            self.settings.core_checkpoint_max_bytes,
        )
        states = manager.load_states(self.settings.resolved_pretraining_dir / row["safe_name"])
        model.load_state_dict(states["model"])
        return states

    def _claim(
        self, worker_id: str, *, require_instruction_tuning: bool = False
    ) -> tuple[sqlite3.Row, int] | None:
        with self.repository.transaction() as connection:
            stale = connection.execute(
                """SELECT id, worker_id FROM pretraining_jobs
                WHERE status='running' AND lease_expires_at IS NOT NULL
                AND lease_expires_at < CURRENT_TIMESTAMP"""
            ).fetchall()
            for stale_job in stale:
                connection.execute(
                    """UPDATE pretraining_jobs SET status='queued', recovery_required=1,
                    lease_generation=lease_generation+1, updated_at=CURRENT_TIMESTAMP
                    WHERE id=? AND status='running'""",
                    (stale_job["id"],),
                )
                self.repository.add_event(
                    connection,
                    stale_job["id"],
                    "stale_lease_detected",
                    "running",
                    "queued",
                    dumps_json({"previous_worker_id": (stale_job["worker_id"] or "")[:12]}),
                )
            linkage = """EXISTS (
                SELECT 1 FROM instruction_tuning_runs itr
                WHERE itr.pretraining_job_id = pretraining_jobs.id
            )"""
            ownership_clause = linkage if require_instruction_tuning else f"NOT {linkage}"
            row = connection.execute(
                f"""SELECT * FROM pretraining_jobs WHERE status='queued' AND recovery_required=0
                AND {ownership_clause}
                ORDER BY queued_at,id LIMIT 1"""
            ).fetchone()
            if not row:
                return None
            new_generation = row["lease_generation"] + 1
            expires_at = _iso(
                _now() + timedelta(seconds=self.settings.pretraining_worker_lease_seconds)
            )
            connection.execute(
                """UPDATE pretraining_jobs
                SET status='running',
                    worker_id=?,
                    lease_generation=?,
                    lease_expires_at=?,
                    started_at=COALESCE(started_at,CURRENT_TIMESTAMP),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND status='queued' AND recovery_required=0""",
                (worker_id, new_generation, expires_at, row["id"]),
            )
            self.repository.add_event(
                connection,
                row["id"],
                "worker_claimed",
                "queued",
                "running",
                dumps_json({"worker_id": worker_id[:12], "lease_generation": new_generation}),
            )
            worker = self.reliability.worker(connection, worker_id)
            self.reliability.upsert_lease(
                connection,
                worker_id=worker_id,
                pretraining_job_id=row["id"],
                status="claimed",
                lease_generation=new_generation,
                lease_expires_at=expires_at,
                owner_public_id=worker["public_id"],
            )
            self.reliability.heartbeat(
                connection,
                worker_id,
                status="running",
                current_job_public_id=row["public_id"],
                lease_generation=new_generation,
                lease_expires_at=expires_at,
            )
            job = self.repository.job(connection, row["public_id"])
            return job, new_generation

    def _references(self, connection, payload: PretrainingJobCreate):
        dataset = connection.execute(
            "SELECT * FROM dataset_versions WHERE public_id=?", (payload.dataset_version_public_id,)
        ).fetchone()
        tokenizer = connection.execute(
            "SELECT * FROM tokenizer_versions WHERE public_id=?",
            (payload.tokenizer_version_public_id,),
        ).fetchone()
        model = connection.execute(
            "SELECT * FROM core_model_versions WHERE public_id=?",
            (payload.core_model_version_public_id,),
        ).fetchone()
        if not dataset or dataset["status"] not in {"ready", "archived"}:
            raise ValidationError("ready or archived dataset version is required")
        if (
            not tokenizer
            or tokenizer["lifecycle_status"] not in {"active", "staging", "retired", "archived"}
            or not tokenizer["model_checksum_sha256"]
        ):
            raise ValidationError("verified tokenizer version is required")
        if not model or model["lifecycle_status"] not in {
            "architecture_verified",
            "smoke_tested",
            "staging",
            "active",
        }:
            raise ValidationError("architecture-verified core model version is required")
        return dataset, tokenizer, model

    def _enforce_config(self, config) -> None:
        if (
            config.batch_size > self.settings.pretraining_max_batch_size
            or config.sequence_length > self.settings.pretraining_max_sequence_length
            or config.total_steps > self.settings.pretraining_max_steps
        ):
            raise ValidationError("pretraining configuration exceeds configured limits")
        if config.gradient_accumulation_steps > self.settings.pretraining_max_gradient_accumulation:
            raise ValidationError("gradient accumulation exceeds configured limit")

    def _model_config(self, job) -> BrudModelConfig:
        with self.repository.transaction() as connection:
            row = connection.execute(
                """SELECT c.*
                FROM core_model_configs c
                JOIN core_model_versions v ON v.config_id=c.id
                WHERE v.id=?""",
                (job["core_model_version_id"],),
            ).fetchone()
        return BrudModelConfig(
            vocabulary_size=row["vocabulary_size"],
            context_length=row["context_length"],
            hidden_size=row["hidden_size"],
            intermediate_size=row["intermediate_size"],
            num_hidden_layers=row["num_hidden_layers"],
            num_attention_heads=row["num_attention_heads"],
            num_key_value_heads=row["num_key_value_heads"],
            pad_token_id=row["pad_token_id"],
            bos_token_id=row["bos_token_id"],
            eos_token_id=row["eos_token_id"],
            unk_token_id=row["unk_token_id"],
        )

    def _blocks(self, job, config) -> tuple[list[list[int]], list[list[int]]]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                """SELECT r.*,i.split
                FROM dataset_version_items i
                JOIN dataset_records r ON r.id=i.dataset_record_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
                (job["dataset_version_id"],),
            ).fetchall()
        train, valid = [], []
        for row in rows:
            if row["split"] == "test":
                continue
            target = train if row["split"] == "train" else valid
            target.append(dict(row))
        processor = TokenizerService(
            TokenizerRepository(self.repository.database_path),
            self.settings,
        ).processor_for_version(job["tokenizer_version_public_id"])
        model_config = self._model_config(job)
        train_sequences, train_counts = token_sequences(train, processor, model_config.eos_token_id)
        validation_sequences, validation_counts = token_sequences(
            valid,
            processor,
            model_config.eos_token_id,
        )
        if not train_sequences:
            raise ValidationError("training split has no tokenized records")
        if not validation_sequences:
            raise ValidationError("validation split has no tokenized records")
        self._validate_token_ids(
            train_sequences + validation_sequences, model_config.vocabulary_size
        )
        if train_counts["empty"] or validation_counts["empty"]:
            self._stream_event(
                job["public_id"],
                {
                    "train_empty_fields": train_counts["empty"],
                    "validation_empty_fields": validation_counts["empty"],
                },
            )
        train_packed = pack_stream(
            train_sequences,
            sequence_length=config.sequence_length,
            pad_token_id=model_config.pad_token_id,
            overlength_policy=config.overlength_policy,
            partial_block_policy="pad",
        )
        validation_packed = pack_stream(
            validation_sequences,
            sequence_length=config.sequence_length,
            pad_token_id=model_config.pad_token_id,
            overlength_policy=config.overlength_policy,
            partial_block_policy="pad",
        )
        self._record_streams(
            job, config, train, valid, processor, model_config, train_packed, validation_packed
        )
        return train_packed["blocks"], validation_packed["blocks"]

    def _record_streams(
        self,
        job,
        config,
        train_records,
        valid_records,
        processor,
        model_config,
        train_packed,
        validation_packed,
    ) -> None:
        with self.repository.transaction() as connection:
            current = self.repository.job(connection, job["public_id"])
            checksums = self._reference_checksums(connection, current)
            train_checksum = None
            train_coverage_public_id = None
            for split, records, packed in (
                ("train", train_records, train_packed),
                ("valid", valid_records, validation_packed),
            ):
                coverage = generate_coverage(
                    records,
                    processor,
                    eos_id=model_config.eos_token_id,
                    sequence_length=config.sequence_length,
                    overlength_policy=config.overlength_policy,
                )
                coverage_public_id = self.reliability.record_coverage(
                    connection,
                    current["id"],
                    split,
                    {
                        **coverage,
                        "language_distribution_json": dumps_json(
                            coverage["language_distribution"]
                        ),
                        "record_type_distribution_json": dumps_json(
                            coverage["record_type_distribution"]
                        ),
                        "source_type_distribution_json": dumps_json(
                            coverage["source_type_distribution"]
                        ),
                        "exclusion_reasons_json": dumps_json(coverage["exclusion_reasons"]),
                    },
                )
                self.reliability.record_stream_manifest(
                    connection,
                    current["id"],
                    {
                        "split": split,
                        "dataset_version_public_id": current["dataset_version_public_id"],
                        "dataset_checksum_sha256": checksums["dataset_checksum_sha256"],
                        "tokenizer_version_public_id": current["tokenizer_version_public_id"],
                        "tokenizer_checksum_sha256": checksums["tokenizer_checksum_sha256"],
                        "sequence_length": config.sequence_length,
                        "packing_policy": "fixed_length",
                        "partial_block_policy": "pad",
                        "eos_policy": config.eos_policy,
                        "overlength_policy": config.overlength_policy,
                        "shuffle": config.shuffle,
                        "seed": config.sampling_seed,
                        "eligible_records": coverage["eligible_records"],
                        "encoded_records": coverage["encoded_records"],
                        "excluded_records": coverage["excluded_records"],
                        "total_tokens": coverage["total_tokens"],
                        "usable_tokens": packed["usable_tokens"],
                        "block_count": packed["block_count"],
                        "stream_checksum_sha256": coverage["stream_checksum_sha256"],
                    },
                )
                if split == "train":
                    train_checksum = coverage["stream_checksum_sha256"]
                    train_coverage_public_id = coverage_public_id
            connection.execute(
                """UPDATE pretraining_jobs SET latest_stream_checksum_sha256=?,
                latest_coverage_public_id=? WHERE id=?""",
                (train_checksum, train_coverage_public_id, current["id"]),
            )

    def _validate_token_ids(self, sequences: list[list[int]], vocabulary_size: int) -> None:
        for sequence in sequences:
            if any(token < 0 or token >= vocabulary_size for token in sequence):
                raise ValidationError("token id outside core model vocabulary")

    def _stream_event(self, public_id: str, metadata: dict[str, Any]) -> None:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            self.repository.add_event(
                connection,
                job["id"],
                "token_stream_warning",
                job["status"],
                job["status"],
                dumps_json(metadata),
            )

    def _metric(
        self, job_id: str, worker_id: str, lease_generation: int, metric: dict[str, Any]
    ) -> None:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_id)
            if job["worker_id"] != worker_id or job["lease_generation"] != lease_generation:
                self.repository.add_event(
                    connection, job["id"], "stale_write_rejected", job["status"], job["status"],
                    dumps_json({"worker_id": worker_id[:12], "held_generation": lease_generation}),
                )
                raise StaleWorkerError(
                    f"worker {worker_id} no longer holds the lease for job {job_id}"
                )
            expires_at = _iso(
                _now() + timedelta(seconds=self.settings.pretraining_worker_lease_seconds)
            )
            connection.execute(
                "UPDATE pretraining_jobs SET lease_expires_at=? WHERE id=?",
                (expires_at, job["id"]),
            )
            self.reliability.renew_lease(connection, worker_id, lease_expires_at=expires_at)
            self.reliability.heartbeat(
                connection, worker_id, status="running",
                current_job_public_id=job["public_id"], lease_generation=lease_generation,
                lease_expires_at=expires_at,
            )
            step = metric["step"]
            connection.execute(
                """INSERT OR REPLACE INTO pretraining_metrics(public_id,pretraining_job_id,
                step,processed_tokens,epoch_fraction,training_loss,learning_rate,
                gradient_norm,tokens_per_second,step_duration_ms,process_memory_bytes,
                system_available_memory_bytes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    job["id"],
                    step,
                    metric["processed_tokens"],
                    step / job["total_steps"],
                    metric["training_loss"],
                    metric["learning_rate"],
                    metric["gradient_norm"],
                    metric["tokens_per_second"],
                    metric["step_duration_ms"],
                    metric["process_memory_bytes"],
                    metric["system_available_memory_bytes"],
                ),
            )
            connection.execute(
                """UPDATE pretraining_jobs
                SET completed_steps=?,
                    processed_tokens=?,
                    latest_training_loss=?,
                    learning_rate=?,
                    tokens_per_second=?,
                    progress=?
                WHERE id=?""",
                (
                    step,
                    metric["processed_tokens"],
                    metric["training_loss"],
                    metric["learning_rate"],
                    metric["tokens_per_second"],
                    step / job["total_steps"],
                    job["id"],
                ),
            )

    def _reference_checksums(self, connection, job) -> dict[str, str | None]:
        dataset_checksum = connection.execute(
            "SELECT checksum_sha256 FROM dataset_versions WHERE id=?", (job["dataset_version_id"],)
        ).fetchone()[0]
        tokenizer_checksum = connection.execute(
            "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE id=?",
            (job["tokenizer_version_id"],),
        ).fetchone()[0]
        model_config_checksum = connection.execute(
            """SELECT c.config_checksum_sha256 FROM core_model_configs c
            JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
            (job["core_model_version_id"],),
        ).fetchone()[0]
        return {
            "dataset_checksum_sha256": dataset_checksum,
            "tokenizer_checksum_sha256": tokenizer_checksum,
            "model_config_checksum_sha256": model_config_checksum,
            "stream_checksum_sha256": job["latest_stream_checksum_sha256"],
        }

    def _save_periodic_checkpoint(
        self, job, worker_id: str, lease_generation: int, model, config, state: dict[str, Any]
    ) -> None:
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        with self.repository.transaction() as connection:
            current = self.repository.job(connection, job["public_id"])
            if current["worker_id"] != worker_id or current["lease_generation"] != lease_generation:
                raise StaleWorkerError(
                    f"worker {worker_id} no longer holds the lease for job {job['public_id']}"
                )
            references = {
                "job_public_id": job["public_id"],
                **self._reference_checksums(connection, current),
            }
        safe_name = f"{_safe(job['public_id'])}/step-{state['step']:08d}-{uuid4().hex[:8]}"
        target = self.settings.resolved_pretraining_dir / safe_name
        saved = TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
        ).save(
            target,
            model=model,
            optimizer=None,
            scheduler=None,
            optimizer_state=state["optimizer_state"],
            scheduler_state=state["scheduler_state"],
            rng_state=state["rng_state"],
            trainer_state={
                "step": state["step"],
                "processed_tokens": state["processed_tokens"],
                "block_index": state["block_index"],
                "status": "running",
            },
            config=config.to_dict(),
            references=references,
        )
        with self.repository.transaction() as connection:
            current = self.repository.job(connection, job["public_id"])
            connection.execute(
                "UPDATE pretraining_checkpoints SET is_latest=0 WHERE pretraining_job_id=?",
                (current["id"],),
            )
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO pretraining_checkpoints(
                public_id,pretraining_job_id,core_model_version_id,
                checkpoint_kind,status,step,processed_tokens,safe_name,file_size_bytes,manifest_json,
                model_checksum_sha256,optimizer_checksum_sha256,scheduler_checksum_sha256,
                trainer_state_checksum_sha256,combined_checksum_sha256,training_loss,validation_loss,
                is_best,is_latest)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    current["id"],
                    current["core_model_version_id"],
                    "periodic",
                    "completed",
                    state["step"],
                    state["processed_tokens"],
                    safe_name,
                    saved["file_size_bytes"],
                    dumps_json(saved["manifest"]),
                    saved["model_checksum_sha256"],
                    saved["optimizer_checksum_sha256"],
                    saved["scheduler_checksum_sha256"],
                    saved["trainer_state_checksum_sha256"],
                    saved["combined_checksum_sha256"],
                    state.get("training_loss"),
                    None,
                    0,
                    1,
                ),
            )
            connection.execute(
                """UPDATE pretraining_jobs SET completed_steps=?,processed_tokens=?
                WHERE id=?""",
                (state["step"], state["processed_tokens"], current["id"]),
            )
            self.repository.add_event(
                connection,
                current["id"],
                "checkpoint_completed",
                None,
                None,
                dumps_json(
                    {
                        "step": state["step"],
                        "checksum": saved["combined_checksum_sha256"][:12],
                        "kind": "periodic",
                    }
                ),
            )

    def _save_training_checkpoint(
        self, job, worker_id: str, lease_generation: int, model, config, result
    ) -> dict[str, Any]:
        import torch as _torch

        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        opt = _torch.optim.AdamW(model.parameters(), lr=config.learning_rate)
        sched = _torch.optim.lr_scheduler.LambdaLR(opt, lambda _: 1.0)
        safe_name = f"{_safe(job['public_id'])}/step-{result.completed_steps:08d}-{uuid4().hex[:8]}"
        target = self.settings.resolved_pretraining_dir / safe_name
        with self.repository.transaction() as connection:
            current = self.repository.job(connection, job["public_id"])
            if current["worker_id"] != worker_id or current["lease_generation"] != lease_generation:
                raise StaleWorkerError(
                    f"worker {worker_id} no longer holds the lease for job {job['public_id']}"
                )
            references = {
                "job_public_id": job["public_id"],
                **self._reference_checksums(connection, current),
            }
        saved = TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
        ).save(
            target,
            model=model,
            optimizer=opt,
            scheduler=sched,
            optimizer_state=result.optimizer_state,
            scheduler_state=result.scheduler_state,
            rng_state=result.rng_state,
            trainer_state={
                "step": result.completed_steps,
                "processed_tokens": result.processed_tokens,
                "block_index": result.block_index,
                "status": result.status,
            },
            config=config.to_dict(),
            references=references,
        )
        with self.repository.transaction() as connection:
            current = self.repository.job(connection, job["public_id"])
            connection.execute(
                "UPDATE pretraining_checkpoints SET is_latest=0 WHERE pretraining_job_id=?",
                (current["id"],),
            )
            public_id = str(uuid4())
            kind = {"paused": "pause", "cancelled": "recovery"}.get(result.status, "final")
            connection.execute(
                """INSERT INTO pretraining_checkpoints(
                public_id,pretraining_job_id,core_model_version_id,
                checkpoint_kind,status,step,processed_tokens,safe_name,file_size_bytes,manifest_json,
                model_checksum_sha256,optimizer_checksum_sha256,scheduler_checksum_sha256,
                trainer_state_checksum_sha256,combined_checksum_sha256,training_loss,validation_loss,is_best,is_latest)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    current["id"],
                    current["core_model_version_id"],
                    kind,
                    "completed",
                    result.completed_steps,
                    result.processed_tokens,
                    safe_name,
                    saved["file_size_bytes"],
                    dumps_json(saved["manifest"]),
                    saved["model_checksum_sha256"],
                    saved["optimizer_checksum_sha256"],
                    saved["scheduler_checksum_sha256"],
                    saved["trainer_state_checksum_sha256"],
                    saved["combined_checksum_sha256"],
                    result.final_loss,
                    result.validation_loss,
                    0,
                    1,
                ),
            )
            self.repository.add_event(
                connection,
                current["id"],
                "checkpoint_completed",
                None,
                None,
                dumps_json(
                    {
                        "step": result.completed_steps,
                        "checksum": saved["combined_checksum_sha256"][:12],
                    }
                ),
            )
        return {"public_id": public_id, **saved}

    def _select_best_checkpoint(self, job_id: int) -> None:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                """SELECT public_id,step,training_loss,validation_loss FROM pretraining_checkpoints
                WHERE pretraining_job_id=? AND status IN ('completed','verified')
                ORDER BY step, id""",
                (job_id,),
            ).fetchall()
            if not rows:
                return
            with_validation = [row for row in rows if row["validation_loss"] is not None]
            if with_validation:
                best = min(with_validation, key=lambda row: (row["validation_loss"], row["step"]))
            else:
                with_training = [row for row in rows if row["training_loss"] is not None]
                if with_training:
                    best = min(with_training, key=lambda row: (row["training_loss"], row["step"]))
                else:
                    best = rows[-1]
            connection.execute(
                "UPDATE pretraining_checkpoints SET is_best=0 WHERE pretraining_job_id=?", (job_id,)
            )
            connection.execute(
                "UPDATE pretraining_checkpoints SET is_best=1 WHERE public_id=?",
                (best["public_id"],),
            )
            connection.execute(
                "UPDATE pretraining_jobs SET best_checkpoint_public_id=? WHERE id=?",
                (best["public_id"], job_id),
            )
            self.repository.add_event(
                connection, job_id, "best_checkpoint_selected", None, None,
                dumps_json({"checkpoint_public_id": best["public_id"], "step": best["step"]}),
            )

    def _generate_run_summary(
        self,
        job_id: int,
        *,
        status: str,
        initial_training_loss: float | None,
        elapsed_seconds: float,
        non_finite_event_count: int,
    ) -> str:
        with self.repository.transaction() as connection:
            job = connection.execute(
                "SELECT * FROM pretraining_jobs WHERE id=?", (job_id,)
            ).fetchone()
            metrics = connection.execute(
                "SELECT * FROM pretraining_metrics WHERE pretraining_job_id=? ORDER BY step",
                (job_id,),
            ).fetchall()
            checkpoints = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE pretraining_job_id=?", (job_id,)
            ).fetchall()
            events = connection.execute(
                "SELECT event_type FROM pretraining_job_events WHERE pretraining_job_id=?",
                (job_id,),
            ).fetchall()
            pause_count = sum(1 for row in events if row["event_type"] == "job_paused")
            resume_count = sum(1 for row in events if row["event_type"] == "recovery_completed")
            recovery_count = len(self.reliability.recovery_attempts(connection, job_id))
            first_loss = metrics[0]["training_loss"] if metrics else None
            initial_loss = (
                initial_training_loss if initial_training_loss is not None else first_loss
            )
            average_tps = (
                sum(row["tokens_per_second"] or 0 for row in metrics) / len(metrics)
                if metrics
                else None
            )
            peak_memory = max(
                (row["process_memory_bytes"] for row in metrics if row["process_memory_bytes"]),
                default=None,
            )
            public_id = self.reliability.record_run_summary(
                connection,
                job_id,
                {
                    "status": status,
                    "initial_step": metrics[0]["step"] if metrics else 0,
                    "final_step": job["completed_steps"],
                    "initial_training_loss": initial_loss,
                    "final_training_loss": job["latest_training_loss"],
                    "best_training_loss": min(
                        (
                            row["training_loss"]
                            for row in metrics
                            if row["training_loss"] is not None
                        ),
                        default=None,
                    ),
                    "initial_validation_loss": None,
                    "final_validation_loss": job["latest_validation_loss"],
                    "best_validation_loss": job["best_validation_loss"],
                    "initial_perplexity": safe_perplexity(initial_loss),
                    "final_perplexity": safe_perplexity(job["latest_training_loss"]),
                    "processed_tokens": job["processed_tokens"],
                    "optimizer_steps": job["completed_steps"],
                    "elapsed_seconds": elapsed_seconds,
                    "average_tokens_per_second": average_tps,
                    "peak_process_memory_bytes": peak_memory,
                    "checkpoint_count": len(checkpoints),
                    "pause_count": pause_count,
                    "resume_count": resume_count,
                    "recovery_count": recovery_count,
                    "non_finite_event_count": non_finite_event_count,
                    "summary_json": dumps_json(
                        {
                            "loss_improvement_ratio": loss_improvement_ratio(
                                initial_loss, job["latest_training_loss"]
                            )
                        }
                    ),
                },
            )
        return public_id

    def _flags(self, public_id: str) -> tuple[bool, bool]:
        from backend.database.connection import database_connection

        with database_connection(self.repository.database_path) as connection:
            row = self.repository.job(connection, public_id)
            return bool(row["pause_requested"]), bool(row["cancel_requested"])

    def _request(
        self, public_id: str, admin_id: str, status: str, column: str, event: str
    ) -> dict[str, Any]:
        if column not in {"pause_requested", "cancel_requested"}:
            if column != "resume_requested":
                raise ValidationError("invalid request flag")
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            if column == "resume_requested":
                if job["status"] != "paused":
                    raise ValidationError("only paused jobs can resume")
                connection.execute(
                    "UPDATE pretraining_jobs SET status='queued',pause_requested=0 WHERE id=?",
                    (job["id"],),
                )
                status = "queued"
            else:
                allowed = {
                    "pause_requested": {"running"},
                    "cancel_requested": {"draft", "validating", "queued", "running", "paused"},
                }
                if job["status"] not in allowed[column]:
                    raise ValidationError("job request is invalid for current status")
                connection.execute(
                    f"UPDATE pretraining_jobs SET status=?,{column}=1 WHERE id=?",
                    (status, job["id"]),
                )
            self.repository.add_event(connection, job["id"], event, job["status"], status)
            self._audit(connection, f"pretraining_{event}", admin_id, public_id)
            return public_row(self.repository.job(connection, public_id))

    def _audit(self, connection, event: str, admin_id: str, resource_id: str, **metadata) -> None:
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
                admin_id,
                "pretraining",
                resource_id,
                "success",
                dumps_json(redact_secrets(metadata)),
            ),
        )
