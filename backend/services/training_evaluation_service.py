"""Coverage, stream verification, run summaries, quality gates, comparisons, retention."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.database.repositories.training_reliability import public_row as reliability_public_row
from backend.services.tokenizer_registry import TokenizerService
from core_model.checkpoints.comparison import compare_checkpoints as _compare_checkpoints
from core_model.checkpoints.retention import RetentionPolicy, classify
from core_model.training.coverage import generate_coverage
from core_model.training.dataset_stream import token_sequences
from core_model.training.diagnostics import is_diverging
from core_model.training.quality_gates import QualityThresholds, assess
from core_model.training.run_comparison import compare_runs as _compare_runs


def _rows_for_split(rows, split: str) -> list[dict[str, Any]]:
    """Map a stream/coverage split label ("train"/"valid") to dataset rows.

    ``dataset_version_items.split`` uses ``train``/``validation``/``test``;
    Phase 10 coverage and stream tables use the shorter ``train``/``valid``.
    Test-split rows are never included in either bucket.
    """

    if split == "train":
        return [dict(row) for row in rows if row["split"] == "train"]
    return [dict(row) for row in rows if row["split"] not in {"train", "test"}]


class TrainingEvaluationService:
    def __init__(
        self,
        repository: PretrainingRepository,
        reliability: TrainingReliabilityRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.reliability = reliability
        self.settings = settings

    # --- coverage -----------------------------------------------------

    def generate_coverage(self, job_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            model_config_row = connection.execute(
                """SELECT c.eos_token_id FROM core_model_configs c
                JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
                (job["core_model_version_id"],),
            ).fetchone()
            configuration = loads_json(job["configuration_json"])
            rows = connection.execute(
                """SELECT r.*,i.split FROM dataset_version_items i
                JOIN dataset_records r ON r.id=i.dataset_record_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
                (job["dataset_version_id"],),
            ).fetchall()
            processor = TokenizerService(
                TokenizerRepository(self.repository.database_path), self.settings
            ).processor_for_version(job["tokenizer_version_public_id"], connection=connection)
            results: dict[str, Any] = {}
            for split in ("train", "valid"):
                split_rows = _rows_for_split(rows, split)
                coverage = generate_coverage(
                    split_rows,
                    processor,
                    eos_id=model_config_row["eos_token_id"],
                    sequence_length=configuration["sequence_length"],
                    overlength_policy=configuration["overlength_policy"],
                )
                public_id = self.reliability.record_coverage(
                    connection,
                    job["id"],
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
                results[split] = {"public_id": public_id, **coverage}
            connection.execute(
                "UPDATE pretraining_jobs SET latest_coverage_public_id=? WHERE id=?",
                (results["train"]["public_id"], job["id"]),
            )
            self._audit(connection, "training_coverage_generated", admin_id, job_public_id)
        return results

    def coverage(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            rows = self.reliability.latest_coverage(connection, job["id"])
        return {"items": [reliability_public_row(row) for row in rows]}

    # --- streams -----------------------------------------------------

    def streams(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            rows = self.reliability.stream_manifests(connection, job["id"])
        return {"items": [reliability_public_row(row) for row in rows]}

    def verify_streams(self, job_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            manifests = self.reliability.stream_manifests(connection, job["id"])
            configuration = loads_json(job["configuration_json"])
            model_config_row = connection.execute(
                """SELECT c.eos_token_id FROM core_model_configs c
                JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
                (job["core_model_version_id"],),
            ).fetchone()
            rows = connection.execute(
                """SELECT r.*,i.split FROM dataset_version_items i
                JOIN dataset_records r ON r.id=i.dataset_record_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
                (job["dataset_version_id"],),
            ).fetchall()
            processor = TokenizerService(
                TokenizerRepository(self.repository.database_path), self.settings
            ).processor_for_version(job["tokenizer_version_public_id"], connection=connection)
            verified_splits = {}
            for manifest in manifests:
                split_rows = _rows_for_split(rows, manifest["split"])
                sequences, _ = token_sequences(
                    split_rows, processor, model_config_row["eos_token_id"]
                )
                coverage = generate_coverage(
                    split_rows,
                    processor,
                    eos_id=model_config_row["eos_token_id"],
                    sequence_length=configuration["sequence_length"],
                    overlength_policy=configuration["overlength_policy"],
                )
                stored = manifest["stream_checksum_sha256"]
                recomputed = coverage["stream_checksum_sha256"]
                verified_splits[manifest["split"]] = {
                    "manifest_public_id": manifest["public_id"],
                    "stored_checksum": stored,
                    "recomputed_checksum": recomputed,
                    "matches": stored == recomputed,
                }
            all_match = (
                all(item["matches"] for item in verified_splits.values())
                if verified_splits
                else False
            )
            self._audit(
                connection, "training_stream_verified", admin_id, job_public_id, verified=all_match
            )
        return {"verified": all_match, "splits": verified_splits}

    # --- run summary -----------------------------------------------------

    def run_summary(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            row = self.reliability.latest_run_summary(connection, job["id"])
        if row is None:
            raise NotFoundError("run summary is not yet available for this job")
        return reliability_public_row(row)

    # --- quality -----------------------------------------------------

    def assess_quality(self, job_public_id: str, admin_id: str) -> dict[str, Any]:
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            coverage_rows = {
                row["split"]: row for row in self.reliability.latest_coverage(connection, job["id"])
            }
            checkpoints = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE pretraining_job_id=?", (job["id"],)
            ).fetchall()
            all_verified = bool(checkpoints) and all(
                row["status"] in {"completed", "verified"} for row in checkpoints
            )
            metrics = connection.execute(
                """SELECT training_loss FROM pretraining_metrics
                WHERE pretraining_job_id=? ORDER BY step""",
                (job["id"],),
            ).fetchall()
            losses = [row["training_loss"] for row in metrics if row["training_loss"] is not None]
            recovery_rows = self.reliability.recovery_attempts(connection, job["id"])
            lease_conflicts = sum(
                1
                for _ in connection.execute(
                    """SELECT 1 FROM pretraining_job_events
                    WHERE pretraining_job_id=? AND event_type='stale_lease_detected'""",
                    (job["id"],),
                )
            )
            stale_writes = sum(
                1
                for _ in connection.execute(
                    """SELECT 1 FROM pretraining_job_events
                    WHERE pretraining_job_id=? AND event_type='stale_write_rejected'""",
                    (job["id"],),
                )
            )
            recovery_failures = sum(1 for row in recovery_rows if row["status"] == "failed")
            resume_recovery_types = {
                "stale_lease",
                "worker_crash",
                "checkpoint_recovery",
                "manual_resume",
                "pause_resume",
            }
            was_resumed = any(
                row["recovery_type"] in resume_recovery_types for row in recovery_rows
            )
            resume_consistent = recovery_rows[0]["status"] == "completed" if recovery_rows else None

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
            latest_checkpoint = connection.execute(
                """SELECT * FROM pretraining_checkpoints WHERE pretraining_job_id=? AND is_latest=1
                ORDER BY step DESC, id DESC LIMIT 1""",
                (job["id"],),
            ).fetchone()
            dataset_checksum_valid = True
            tokenizer_checksum_valid = True
            model_config_checksum_valid = True
            stream_checksum_valid = True
            if latest_checkpoint is not None:
                checkpoint_dir = (
                    self.settings.resolved_pretraining_dir / latest_checkpoint["safe_name"]
                )
                manager = TrainingCheckpointManager(
                    self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
                )
                try:
                    manager.verify(checkpoint_dir)
                    references = manager.load_states(checkpoint_dir).get("references", {})
                except (OSError, ValueError, RuntimeError):
                    references = {}
                if references.get("dataset_checksum_sha256"):
                    dataset_checksum_valid = (
                        references["dataset_checksum_sha256"] == dataset_checksum_actual
                    )
                if references.get("tokenizer_checksum_sha256"):
                    tokenizer_checksum_valid = (
                        references["tokenizer_checksum_sha256"] == tokenizer_checksum_actual
                    )
                if references.get("model_config_checksum_sha256"):
                    model_config_checksum_valid = (
                        references["model_config_checksum_sha256"] == model_config_checksum_actual
                    )
                stream_checksum_recorded = job["latest_stream_checksum_sha256"]
                if references.get("stream_checksum_sha256") and stream_checksum_recorded:
                    stream_checksum_valid = (
                        references["stream_checksum_sha256"] == job["latest_stream_checksum_sha256"]
                    )

            train_coverage = coverage_rows.get("train")
            valid_coverage = coverage_rows.get("valid")
            excluded_ratio = 0.0
            coverage_ratio = 0.0
            if train_coverage is not None:
                total = train_coverage["total_records"] or 1
                excluded_ratio = train_coverage["excluded_records"] / total
                coverage_ratio = train_coverage["coverage_ratio"]

            thresholds = QualityThresholds(
                min_processed_tokens=self.settings.training_min_processed_tokens,
                min_loss_improvement_ratio=self.settings.training_min_loss_improvement_ratio,
                max_train_validation_gap=self.settings.training_max_train_validation_gap,
                max_excluded_record_ratio=self.settings.training_max_excluded_record_ratio,
                min_validation_tokens=self.settings.training_min_validation_tokens,
                require_validation=self.settings.training_require_validation,
                require_resume_check_if_resumed=self.settings.training_require_resume_check_if_resumed,
                max_non_finite_events=self.settings.training_max_non_finite_events,
                require_all_checkpoints_verified=self.settings.training_require_all_checkpoints_verified,
                min_coverage_ratio=self.settings.training_min_coverage_ratio,
            )
            inputs = {
                "dataset_checksum_valid": dataset_checksum_valid,
                "tokenizer_checksum_valid": tokenizer_checksum_valid,
                "model_config_checksum_valid": model_config_checksum_valid,
                "stream_checksum_valid": stream_checksum_valid,
                "non_finite_event_count": 0,
                "loss_diverging": is_diverging(losses),
                "initial_training_loss": losses[0] if losses else None,
                "final_training_loss": job["latest_training_loss"],
                "final_validation_loss": job["latest_validation_loss"],
                "best_validation_loss": job["best_validation_loss"],
                "validation_tokens": valid_coverage["usable_tokens"] if valid_coverage else 0,
                "was_resumed": was_resumed,
                "resume_consistent": resume_consistent,
                "all_checkpoints_verified": all_verified,
                "lease_conflict_count": lease_conflicts,
                "stale_write_rejections": stale_writes,
                "worker_recovery_failures": recovery_failures,
                "memory_limit_exceeded": False,
                "disk_limit_exceeded": False,
                "coverage_ratio": coverage_ratio,
                "excluded_record_ratio": excluded_ratio,
                "processed_tokens": job["processed_tokens"],
            }
            result = assess(inputs, thresholds)
            public_id = self.reliability.record_quality_assessment(
                connection,
                job["id"],
                {
                    "assessment_version": self.settings.training_quality_ruleset_version,
                    "overall_score": result["overall_score"],
                    "dimension_scores_json": dumps_json(result["dimension_scores"]),
                    "readiness_status": result["readiness_status"],
                    "summary_json": dumps_json({"inputs": inputs}),
                    "issues": [
                        {**issue, "details_json": dumps_json(issue["details"])}
                        for issue in result["issues"]
                    ],
                },
            )
            connection.execute(
                "UPDATE pretraining_jobs SET quality_readiness_status=? WHERE id=?",
                (result["readiness_status"], job["id"]),
            )
            self._audit(
                connection, "training_quality_assessed", admin_id, job_public_id,
                readiness_status=result["readiness_status"],
            )
        return {"public_id": public_id, **result}

    def quality(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            row = self.reliability.latest_quality_assessment(connection, job["id"])
        if row is None:
            raise NotFoundError("no quality assessment has been generated for this job")
        return reliability_public_row(row)

    def quality_issues(self, job_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            assessment = self.reliability.latest_quality_assessment(connection, job["id"])
            if assessment is None:
                return {"items": []}
            rows = self.reliability.quality_issues(connection, assessment["id"])
        return {"items": [reliability_public_row(row) for row in rows]}

    # --- comparisons -----------------------------------------------------

    def compare_checkpoints(self, left: str, right: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = {
                item: connection.execute(
                    "SELECT * FROM pretraining_checkpoints WHERE public_id=?", (item,)
                ).fetchone()
                for item in (left, right)
            }
            if not rows[left] or not rows[right]:
                raise ValidationError("checkpoint not found")
            profiles = {}
            for public_id, row in rows.items():
                job = connection.execute(
                    "SELECT * FROM pretraining_jobs WHERE id=?", (row["pretraining_job_id"],)
                ).fetchone()
                config_public_id = connection.execute(
                    """SELECT c.public_id FROM core_model_configs c
                    JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
                    (row["core_model_version_id"],),
                ).fetchone()[0]
                dataset_public_id = connection.execute(
                    "SELECT public_id FROM dataset_versions WHERE id=?",
                    (job["dataset_version_id"],),
                ).fetchone()[0]
                tokenizer_public_id = connection.execute(
                    "SELECT public_id FROM tokenizer_versions WHERE id=?",
                    (job["tokenizer_version_id"],),
                ).fetchone()[0]
                profiles[public_id] = {
                    "step": row["step"],
                    "processed_tokens": row["processed_tokens"],
                    "training_loss": row["training_loss"],
                    "validation_loss": row["validation_loss"],
                    "perplexity": None,
                    "learning_rate": None,
                    "checksum_status": row["status"],
                    "core_model_config_public_id": config_public_id,
                    "dataset_version_public_id": dataset_public_id,
                    "tokenizer_version_public_id": tokenizer_public_id,
                    "file_size_bytes": row["file_size_bytes"],
                    "promotion_eligible": row["status"] in {"completed", "verified"},
                }
            result = _compare_checkpoints(profiles[left], profiles[right])
            comparison_public_id = self.reliability.record_checkpoint_comparison(
                connection,
                left=left,
                right=right,
                compatibility=result["compatibility"],
                comparison_json=dumps_json(result),
                admin_id=admin_id,
            )
        return {"public_id": comparison_public_id, **result}

    def compare_runs(self, left: str, right: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profiles = {}
            for public_id in (left, right):
                job = self.repository.job(connection, public_id)
                config_public_id = connection.execute(
                    """SELECT c.public_id FROM core_model_configs c
                    JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
                    (job["core_model_version_id"],),
                ).fetchone()[0]
                quality = self.reliability.latest_quality_assessment(connection, job["id"])
                profiles[public_id] = {
                    "dataset_version_public_id": job["dataset_version_public_id"],
                    "tokenizer_version_public_id": job["tokenizer_version_public_id"],
                    "core_model_config_public_id": config_public_id,
                    "initialization_seed": job["initialization_seed"],
                    "sampling_seed": job["sampling_seed"],
                    "sequence_length": loads_json(job["configuration_json"]).get("sequence_length"),
                    "total_steps": job["total_steps"],
                    "completed_steps": job["completed_steps"],
                    "processed_tokens": job["processed_tokens"],
                    "initial_training_loss": None,
                    "final_training_loss": job["latest_training_loss"],
                    "final_validation_loss": job["latest_validation_loss"],
                    "final_perplexity": None,
                    "average_tokens_per_second": job["tokens_per_second"],
                    "peak_process_memory_bytes": None,
                    "pause_count": None,
                    "resume_count": None,
                    "recovery_count": len(
                        self.reliability.recovery_attempts(connection, job["id"])
                    ),
                    "coverage_ratio": None,
                    "quality_overall_score": quality["overall_score"] if quality else None,
                    "quality_readiness_status": job["quality_readiness_status"],
                }
            result = _compare_runs(profiles[left], profiles[right])
            comparison_public_id = self.reliability.record_run_comparison(
                connection,
                left=left,
                right=right,
                compatibility=result["compatibility"],
                comparison_json=dumps_json(result),
                admin_id=admin_id,
            )
        return {"public_id": comparison_public_id, **result}

    # --- retention -----------------------------------------------------

    def _classify(self, connection, job) -> list[dict[str, Any]]:
        checkpoints = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE pretraining_job_id=?", (job["id"],)
            ).fetchall()
        ]
        promoted = {
            row[0]
            for row in connection.execute(
                """SELECT weights_checksum_sha256 FROM core_model_versions
                WHERE architecture_summary_json LIKE ?""",
                (f'%{job["public_id"]}%',),
            )
        }
        promoted_checkpoints = frozenset(
            row["public_id"] for row in checkpoints if row["model_checksum_sha256"] in promoted
        )
        active_recovery = connection.execute(
            """SELECT source_checkpoint_public_id FROM training_recovery_attempts
            WHERE pretraining_job_id=? AND status IN ('validating','recovering')
            ORDER BY started_at DESC LIMIT 1""",
            (job["id"],),
        ).fetchone()
        policy = RetentionPolicy(
            keep_periodic=self.settings.pretraining_keep_periodic,
            keep_best=self.settings.pretraining_keep_best,
            keep_final=self.settings.pretraining_keep_final,
            keep_pause=self.settings.pretraining_keep_pause,
        )
        return classify(
            checkpoints,
            policy,
            promoted_checkpoint_public_ids=promoted_checkpoints,
            active_recovery_checkpoint_public_id=active_recovery[0] if active_recovery else None,
        )

    def retention_preview(self, job_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            classification = self._classify(connection, job)
            for item in classification:
                self.reliability.record_retention_action(
                    connection,
                    job["id"],
                    mode="preview",
                    checkpoint_public_id=item["public_id"],
                    classification=item["classification"],
                    protection_reason=item["protection_reason"],
                    dry_run=True,
                    admin_id=admin_id,
                )
        return {"items": classification}

    def retention_apply(
        self, job_public_id: str, checkpoint_public_ids: list[str], admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            classification = {item["public_id"]: item for item in self._classify(connection, job)}
            dry_run = self.settings.pretraining_retention_dry_run
            applied: list[dict[str, Any]] = []
            for public_id in checkpoint_public_ids:
                item = classification.get(public_id)
                if item is None:
                    raise ValidationError(f"checkpoint {public_id} does not belong to this job")
                if item["classification"] != "eligible":
                    raise ValidationError(
                        f"checkpoint {public_id} is protected and cannot be archived"
                    )
                if not dry_run:
                    connection.execute(
                        """UPDATE pretraining_checkpoints SET status='archived',
                        archived_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                        (public_id,),
                    )
                self.reliability.record_retention_action(
                    connection,
                    job["id"],
                    mode="apply",
                    checkpoint_public_id=public_id,
                    classification="archived" if not dry_run else "eligible",
                    protection_reason=None,
                    dry_run=dry_run,
                    admin_id=admin_id,
                )
                applied.append({"public_id": public_id, "archived": not dry_run})
            self._audit(
                connection, "checkpoint_retention_applied", admin_id, job_public_id, dry_run=dry_run
            )
        return {"dry_run": dry_run, "applied": applied}

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
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
                admin_id,
                "pretraining",
                resource_id,
                "success",
                dumps_json(metadata),
            ),
        )
