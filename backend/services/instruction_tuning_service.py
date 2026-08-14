"""Phase 12 supervised instruction-tuning orchestration.

Reuses the existing Phase 9 pretraining job/worker/checkpoint machinery and
Phase 10 evaluation/comparison services rather than duplicating a trainer.
This module adds: base-model eligibility, dataset validation/profiling,
instruction templates, response-only label masking + batch building,
instruction-tuning training (via a sibling trainer function), per-language
response-only evaluation, bounded diagnostic generation, leakage/repetition/
memorization checks, candidate selection, and the reproducibility manifest.
"""

from __future__ import annotations

import hashlib
import math
import shutil
import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.instruction_tuning import (
    InstructionTuningRepository,
    public_row,
)
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.models.instruction_tuning import (
    InstructionTemplateCreate,
    InstructionTuningExperimentCreate,
    InstructionTuningExperimentPatch,
    InstructionTuningRunCreate,
)
from backend.models.pretraining import PretrainingJobCreate
from backend.services.pretraining_service import PretrainingService
from backend.services.tokenizer_registry import TokenizerService
from backend.services.training_evaluation_service import TrainingEvaluationService
from core_model.instruction_tuning.batch_builder import (
    InstructionProfileThresholds,
    build_instruction_examples,
    data_sufficiency_status,
)
from core_model.instruction_tuning.dataset_validator import DatasetValidationThresholds
from core_model.instruction_tuning.evaluation import (
    bounded_length,
    no_excessive_repetition,
    no_role_token_leakage,
    no_system_prompt_leakage,
    response_not_empty,
    valid_unicode,
)
from core_model.instruction_tuning.fixed_eval_fixtures import FIXTURE_VERSION, all_fixtures
from core_model.instruction_tuning.label_masking import LabelMaskingThresholds
from core_model.instruction_tuning.learning_checks import (
    InstructionLearningCheckThresholds,
    run_learning_checks,
)
from core_model.instruction_tuning.memorization_checks import (
    MemorizationThresholds,
    memorization_warnings,
)
from core_model.instruction_tuning.templates import (
    InstructionTemplate,
    template_checksum,
    template_from_dict,
    template_to_dict,
    validate_template_against_tokenizer,
)
from core_model.training.metrics import available_memory_bytes
from core_model.training.pretraining_config import from_mapping

LANGUAGES = ("ta", "en", "tgl", "mixed")
ELIGIBLE_BASE_STATUSES = {"staging", "active"}
BLOCKING_CHECK_CODES = {
    "response_only_masking_verified",
    "training_loss_improves",
    "validation_response_loss_finite",
    "checkpoint_integrity",
    "base_model_lineage_complete",
}


class InstructionTuningService:
    def __init__(
        self,
        repository: InstructionTuningRepository,
        pretraining_repository: PretrainingRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.pretraining_repository = pretraining_repository
        self.settings = settings
        self.pretraining_service = PretrainingService(pretraining_repository, settings)

    # --- experiments -----------------------------------------------------

    def create_experiment(
        self, payload: InstructionTuningExperimentCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            dataset = connection.execute(
                "SELECT id,status FROM dataset_versions WHERE public_id=?",
                (payload.dataset_version_public_id,),
            ).fetchone()
            if not dataset or dataset["status"] not in {"ready", "archived"}:
                raise ValidationError("ready or archived dataset version is required")
            base_model = connection.execute(
                "SELECT * FROM core_model_versions WHERE public_id=?",
                (payload.base_core_model_version_public_id,),
            ).fetchone()
            if not base_model:
                raise ValidationError("base core model version not found")
            if base_model["lifecycle_status"] not in ELIGIBLE_BASE_STATUSES:
                raise ValidationError(
                    "base model must be a promoted (staging or active) base-pretrained candidate"
                )
            summary = loads_json(base_model["architecture_summary_json"])
            if not summary.get("base_pretrained"):
                raise ValidationError("base model must be marked base_pretrained")
            if summary.get("instruction_tuned"):
                raise ValidationError(
                    "base model is already instruction-tuned; "
                    "select the original base-pretrained candidate instead"
                )
            checkpoint = connection.execute(
                """SELECT * FROM pretraining_checkpoints WHERE core_model_version_id=?
                AND status IN ('completed','verified')
                ORDER BY is_best DESC, is_latest DESC, step DESC LIMIT 1""",
                (base_model["id"],),
            ).fetchone()
            if not checkpoint:
                raise ValidationError("base model has no available verified checkpoint")
            public_id = self.repository.create_experiment(
                connection,
                {
                    "name": payload.name,
                    "objective": payload.objective,
                    "base_core_model_version_id": base_model["id"],
                    "source_base_checkpoint_id": checkpoint["id"],
                    "dataset_version_id": dataset["id"],
                    "tokenizer_version_id": base_model["tokenizer_version_id"],
                    "initialization_seed": payload.initialization_seed,
                    "sampling_seed": payload.sampling_seed,
                    "training_configuration_json": dumps_json(payload.training_configuration),
                    "evaluation_configuration_json": dumps_json(payload.evaluation_configuration),
                    "resource_limits_json": dumps_json(payload.resource_limits),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "instruction_tuning_experiment_created", admin_id, public_id)
            return public_row(self.repository.experiment(connection, public_id))

    def list_experiments(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows, total = self.repository.list_experiments(connection, page, page_size)
        return {
            "items": [public_row(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    def get_experiment(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.experiment(connection, public_id))

    def patch_experiment(
        self, public_id: str, payload: InstructionTuningExperimentPatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            fields: dict[str, Any] = {}
            if payload.name is not None:
                fields["name"] = payload.name
            if payload.objective is not None:
                fields["objective"] = payload.objective
            if payload.instruction_template_public_id is not None:
                template_row = connection.execute(
                    "SELECT id,tokenizer_version_id,is_valid FROM instruction_format_templates "
                    "WHERE public_id=?",
                    (payload.instruction_template_public_id,),
                ).fetchone()
                if not template_row or not template_row["is_valid"]:
                    raise ValidationError("a valid instruction template is required")
                if template_row["tokenizer_version_id"] != experiment["tokenizer_version_id"]:
                    raise ValidationError(
                        "template must be validated against this experiment's tokenizer"
                    )
                fields["instruction_template_id"] = template_row["id"]
                if experiment["status"] in {"profiled"}:
                    fields["status"] = "template_validated"
            self.repository.update_experiment(connection, experiment["id"], fields)
            self._audit(connection, "instruction_tuning_experiment_updated", admin_id, public_id)
            return public_row(self.repository.experiment(connection, public_id))

    # --- dataset profile -----------------------------------------------------

    def _dataset_rows(self, connection, dataset_version_id: int) -> list[dict[str, Any]]:
        rows = connection.execute(
            """SELECT r.*,i.split,s.source_type,s.licence_status
            FROM dataset_version_items i
            JOIN dataset_records r ON r.id=i.dataset_record_id
            JOIN dataset_sources s ON s.id=r.source_id
            WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
            (dataset_version_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _resolve_template(self, connection, experiment) -> InstructionTemplate:
        if not experiment["instruction_template_id"]:
            # Dataset profiling is allowed before a template is assigned (the manual
            # verification workflow generates the profile first) — use a default,
            # unpersisted template purely to render text for profile statistics.
            # Actual runs still require an experiment-assigned, validated template
            # (enforced in create_run), so this fallback never affects training.
            return InstructionTemplate(name="default", version="0")
        row = connection.execute(
            "SELECT template_json FROM instruction_format_templates WHERE id=?",
            (experiment["instruction_template_id"],),
        ).fetchone()
        return template_from_dict(loads_json(row["template_json"]))

    def _build_examples(
        self, connection, experiment, *, shuffle: bool, sequence_length: int | None = None
    ) -> dict[str, Any]:
        records = self._dataset_rows(connection, experiment["dataset_version_id"])
        processor = TokenizerService(
            TokenizerRepository(self.repository.database_path), self.settings
        ).processor_for_version(experiment["tokenizer_version_public_id"])
        template = self._resolve_template(connection, experiment)
        if sequence_length is None:
            evaluation_configuration = loads_json(experiment["evaluation_configuration_json"])
            sequence_length = evaluation_configuration.get("sequence_length", 128)
        dataset_checksum = connection.execute(
            "SELECT checksum_sha256 FROM dataset_versions WHERE id=?",
            (experiment["dataset_version_id"],),
        ).fetchone()[0]
        tokenizer_checksum = connection.execute(
            "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE id=?",
            (experiment["tokenizer_version_id"],),
        ).fetchone()[0]
        return build_instruction_examples(
            records, processor, template,
            eos_token_id=3, pad_token_id=0, sequence_length=sequence_length,
            dataset_thresholds=DatasetValidationThresholds(),
            masking_thresholds=LabelMaskingThresholds(sequence_length=sequence_length),
            tokenizer_checksum=tokenizer_checksum or "",
            dataset_checksum=dataset_checksum or "",
            template_checksum=template_checksum(template),
            shuffle=shuffle, seed=experiment["sampling_seed"],
        )

    def generate_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            built = self._build_examples(connection, experiment, shuffle=False)
            coverage = built["coverage"]
            thresholds = InstructionProfileThresholds(
                min_records=self.settings.instruction_tuning_min_records,
                limited_experiment_floor=self.settings.instruction_tuning_limited_experiment_floor,
                min_validation_records=self.settings.instruction_tuning_min_validation_records,
                min_test_records=self.settings.instruction_tuning_min_test_records,
            )
            sufficiency = data_sufficiency_status(coverage["eligible_records"], thresholds)
            public_profile_id = self.repository.record_profile(
                connection, experiment["id"],
                {
                    "dataset_version_id": experiment["dataset_version_id"],
                    "total_records": coverage["total_records"],
                    "eligible_records": coverage["eligible_records"],
                    "invalid_records": coverage["invalid_records"],
                    "excluded_records": coverage["excluded_records"],
                    "train_count": coverage["train_count"],
                    "validation_count": coverage["validation_count"],
                    "test_count": coverage["test_count"],
                    "language_distribution_json": dumps_json(coverage["language_distribution"]),
                    "record_type_distribution_json": dumps_json(
                        coverage["record_type_distribution"]
                    ),
                    "source_distribution_json": dumps_json(coverage["source_distribution"]),
                    "licence_distribution_json": dumps_json(coverage["licence_distribution"]),
                    "system_prompt_count": coverage["system_prompt_count"],
                    "input_field_count": coverage["input_field_count"],
                    "synthesized_flat_chat_count": coverage["synthesized_flat_chat_count"],
                    "average_prompt_tokens": coverage["average_prompt_tokens"],
                    "average_response_tokens": coverage["average_response_tokens"],
                    "maximum_prompt_tokens": coverage["maximum_prompt_tokens"],
                    "maximum_response_tokens": coverage["maximum_response_tokens"],
                    "empty_response_count": coverage["empty_response_count"],
                    "duplicate_prompt_count": coverage["duplicate_prompt_count"],
                    "duplicate_response_count": coverage["duplicate_response_count"],
                    "exact_prompt_response_duplicate_count": coverage[
                        "exact_prompt_response_duplicate_count"
                    ],
                    "response_language_mismatch_count": coverage[
                        "response_language_mismatch_count"
                    ],
                    "special_token_collision_count": coverage["special_token_collision_count"],
                    "truncation_risk_count": coverage["truncation_risk_count"],
                    "maskable_assistant_token_count": coverage["maskable_assistant_token_count"],
                    "exclusion_reasons_json": dumps_json(coverage["exclusion_reasons"]),
                    "input_stream_checksum_sha256": coverage["input_stream_checksum_sha256"],
                    "label_stream_checksum_sha256": coverage["label_stream_checksum_sha256"],
                    "data_sufficiency_status": sufficiency,
                    "profile_checksum_sha256": hashlib.sha256(
                        dumps_json(coverage).encode("utf-8")
                    ).hexdigest(),
                },
            )
            fields = {"latest_profile_public_id": public_profile_id}
            if experiment["status"] == "draft":
                fields["status"] = "profiled"
            self.repository.update_experiment(connection, experiment["id"], fields)
            self._audit(
                connection, "instruction_tuning_profile_generated", admin_id, public_id,
                data_sufficiency_status=sufficiency,
            )
            return public_row(self.repository.latest_profile(connection, experiment["id"]))

    def get_profile(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            row = self.repository.latest_profile(connection, experiment["id"])
        if row is None:
            raise NotFoundError("dataset profile has not been generated for this experiment")
        return public_row(row)

    # --- templates -----------------------------------------------------

    def create_template(self, payload: InstructionTemplateCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            tokenizer = connection.execute(
                "SELECT id,special_tokens_json FROM tokenizer_versions WHERE public_id=?",
                (payload.tokenizer_version_public_id,),
            ).fetchone()
            if not tokenizer:
                raise ValidationError("tokenizer version not found")
            template = InstructionTemplate(
                name=payload.name, version=payload.version,
                insert_language_marker=payload.insert_language_marker,
            )
            special_tokens = loads_json(tokenizer["special_tokens_json"])
            missing = validate_template_against_tokenizer(template, special_tokens)
            template_id = self.repository.create_template(
                connection,
                {
                    "name": template.name,
                    "version": template.version,
                    "tokenizer_version_id": tokenizer["id"],
                    "template_json": dumps_json(template_to_dict(template)),
                    "required_special_tokens_json": dumps_json(
                        list(template.required_special_tokens)
                    ),
                    "special_token_validation_json": dumps_json({"missing_tokens": missing}),
                    "is_valid": 0 if missing else 1,
                    "template_checksum_sha256": template_checksum(template),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "instruction_template_created", admin_id, template_id,
                valid=not missing,
            )
            return public_row(self.repository.template(connection, template_id))

    def get_template(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.template(connection, public_id))

    def list_templates(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.templates(connection)
        return {"items": [public_row(row) for row in rows]}

    def validate_template(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.template(connection, public_id)
            tokenizer = connection.execute(
                "SELECT special_tokens_json FROM tokenizer_versions WHERE id=?",
                (row["tokenizer_version_id"],),
            ).fetchone()
            template = template_from_dict(loads_json(row["template_json"]))
            missing = validate_template_against_tokenizer(
                template, loads_json(tokenizer["special_tokens_json"])
            )
            self._audit(
                connection, "instruction_template_validated", admin_id, public_id,
                valid=not missing,
            )
        return {"public_id": public_id, "is_valid": not missing, "missing_tokens": missing}

    # --- runs -----------------------------------------------------

    def create_run(
        self, public_id: str, payload: InstructionTuningRunCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            if not experiment["instruction_template_id"]:
                raise ValidationError("experiment requires a validated instruction template")
            self._guard_single_active_job(connection)
            existing_runs = self.repository.runs_for_experiment(connection, experiment["id"])
            training_configuration = loads_json(experiment["training_configuration_json"])
            configuration = {**training_configuration, **payload.configuration}
            job_payload = PretrainingJobCreate(
                name=f"{experiment['name']} — {payload.run_label}",
                dataset_version_public_id=experiment["dataset_version_public_id"],
                tokenizer_version_public_id=experiment["tokenizer_version_public_id"],
                core_model_version_public_id=experiment["base_core_model_version_public_id"],
                job_mode="bounded_pretraining",
                configuration=configuration,
            )
        job = self.pretraining_service.create_job(job_payload, admin_id)
        self.pretraining_service.validate_job(job["public_id"], admin_id)
        with self.repository.transaction() as connection:
            job_row = self.pretraining_repository.job(connection, job["public_id"])
            run_public_id = self.repository.create_run(
                connection,
                {
                    "instruction_tuning_experiment_id": experiment["id"],
                    "pretraining_job_id": job_row["id"],
                    "instruction_template_id": experiment["instruction_template_id"],
                    "run_label": payload.run_label,
                    "run_index": len(existing_runs) + 1,
                    "config_diff_json": dumps_json(payload.config_diff),
                    "truncation_policy": payload.truncation_policy,
                    "created_by_admin_public_id": admin_id,
                },
            )
            fields = {}
            if experiment["status"] == "template_validated":
                fields["status"] = "ready"
            if fields:
                self.repository.update_experiment(connection, experiment["id"], fields)
            self._audit(connection, "instruction_tuning_run_created", admin_id, run_public_id)
            return public_row(self.repository.run(connection, run_public_id))

    def list_runs(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            rows = self.repository.runs_for_experiment(connection, experiment["id"])
        return {"items": [public_row(row) for row in rows]}

    def get_run(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.run(connection, run_public_id))

    def queue_run(self, run_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            self._guard_single_active_job(connection)
            self._guard_resources()
        self.pretraining_service.queue_job(run["pretraining_job_public_id"], admin_id)
        with self.repository.transaction() as connection:
            self.repository.update_run(connection, run["id"], {"status": "queued"})
            self._audit(connection, "instruction_tuning_run_queued", admin_id, run_public_id)
            return public_row(self.repository.run(connection, run_public_id))

    def run_one(self, worker_id: str) -> dict[str, Any] | None:
        """Instruction-tuning worker entry point.

        Reuses PretrainingService's claim/lease/heartbeat/recovery machinery
        unchanged, scoped to instruction-tuning-linked jobs only via
        ``require_instruction_tuning=True`` — the generic base-pretraining
        worker (``PretrainingService.run_one``) can never claim these jobs.
        """

        with self.pretraining_repository.transaction() as connection:
            self.pretraining_service.reliability.register_worker(connection, worker_id)
            self.pretraining_service.reliability.heartbeat(connection, worker_id, status="claiming")
        claimed = self.pretraining_service._claim(worker_id, require_instruction_tuning=True)
        if not claimed:
            with self.pretraining_repository.transaction() as connection:
                self.pretraining_service.reliability.heartbeat(connection, worker_id, status="idle")
            return None
        job, lease_generation = claimed
        return self._run_claimed_instruction_job(job, worker_id, lease_generation)

    def _run_claimed_instruction_job(
        self, job, worker_id: str, lease_generation: int
    ) -> dict[str, Any]:
        import torch

        from core_model.architecture.model import BrudForCausalLM
        from core_model.training.trainer import run_instruction_tuning

        config = from_mapping(loads_json(job["configuration_json"]))
        model_config = self.pretraining_service._model_config(job)
        torch.manual_seed(int(job["initialization_seed"]))
        model = BrudForCausalLM(model_config)
        with self.repository.transaction() as connection:
            run_row = connection.execute(
                "SELECT * FROM instruction_tuning_runs WHERE pretraining_job_id=?", (job["id"],)
            ).fetchone()
            experiment = connection.execute(
                "SELECT * FROM instruction_tuning_experiments WHERE id=?",
                (run_row["instruction_tuning_experiment_id"],),
            ).fetchone()
            experiment_public = self.repository.experiment(connection, experiment["public_id"])
            built = self._build_examples(
                connection, experiment_public, shuffle=True,
                sequence_length=min(config.sequence_length, model_config.context_length),
            )
        train_examples = [(a, b, c) for a, b, c, _ in built["train"]]
        validation_examples = [(a, b, c) for a, b, c, _ in built["validation"]]
        started = time.perf_counter()
        initial_training_loss = job["latest_training_loss"] if job["completed_steps"] else None
        non_finite_events = 0

        def on_step(metric: dict[str, Any]) -> None:
            with self.repository.transaction() as connection:
                self.repository.record_metric(
                    connection, run_row["id"],
                    {
                        "step": metric["step"],
                        "examples_processed": metric["step"] * config.gradient_accumulation_steps,
                        "prompt_tokens": metric["prompt_tokens"],
                        "target_tokens": metric["target_tokens"],
                        "ignored_tokens": metric["ignored_tokens"],
                        "training_loss": metric["training_loss"],
                        "learning_rate": metric["learning_rate"],
                        "gradient_norm": metric["gradient_norm"],
                        "tokens_per_second": metric["tokens_per_second"],
                        "step_duration_ms": metric["step_duration_ms"],
                        "process_memory_bytes": metric["process_memory_bytes"],
                        "system_available_memory_bytes": metric["system_available_memory_bytes"],
                    },
                )
            self.pretraining_service._metric(
                job["public_id"], worker_id, lease_generation,
                {
                    "step": metric["step"],
                    "processed_tokens": metric["processed_tokens"],
                    "training_loss": metric["training_loss"],
                    "learning_rate": metric["learning_rate"],
                    "gradient_norm": metric["gradient_norm"],
                    "tokens_per_second": metric["tokens_per_second"],
                    "step_duration_ms": metric["step_duration_ms"],
                    "process_memory_bytes": metric["process_memory_bytes"],
                    "system_available_memory_bytes": metric["system_available_memory_bytes"],
                },
            )

        def on_checkpoint(**state: Any) -> None:
            self.pretraining_service._save_periodic_checkpoint(
                job, worker_id, lease_generation, model, config, state
            )

        try:
            result = run_instruction_tuning(
                model=model,
                train_examples=train_examples,
                validation_examples=validation_examples,
                config=config,
                start_step=job["completed_steps"],
                start_processed_tokens=job["processed_tokens"],
                on_step=on_step,
                on_checkpoint=on_checkpoint,
                should_pause=lambda: self.pretraining_service._flags(job["public_id"])[0],
                should_cancel=lambda: self.pretraining_service._flags(job["public_id"])[1],
            )
        except ValueError as exc:
            if "non-finite" in str(exc):
                non_finite_events += 1
                with self.repository.transaction() as connection:
                    current = self.pretraining_repository.job(connection, job["public_id"])
                    self.pretraining_repository.add_event(
                        connection, current["id"], "non_finite_training_value",
                        current["status"], current["status"], dumps_json({"error": str(exc)}),
                    )
            raise
        checkpoint = self.pretraining_service._save_training_checkpoint(
            job, worker_id, lease_generation, model, config, result
        )
        with self.pretraining_repository.transaction() as connection:
            current = self.pretraining_repository.job(connection, job["public_id"])
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
                    status, result.completed_steps, result.processed_tokens,
                    result.final_loss, result.validation_loss, result.validation_loss,
                    1.0 if status == "completed" else current["progress"],
                    worker_id, current["id"],
                ),
            )
            event = {
                "completed": "training_completed",
                "paused": "job_paused",
                "cancelled": "job_cancelled",
            }.get(status, "training_completed_with_warnings")
            self.pretraining_repository.add_event(
                connection, current["id"], event, current["status"], status,
                dumps_json(
                    {
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                        "checkpoint": checkpoint["public_id"],
                    }
                ),
            )
            self.pretraining_service.reliability.release_lease(
                connection, worker_id, reason=f"job_{status}"
            )
            self.pretraining_service.reliability.heartbeat(connection, worker_id, status="idle")
        if status in {"completed", "completed_with_warnings"}:
            self.pretraining_service._select_best_checkpoint(current["id"])
            self.pretraining_service._generate_run_summary(
                current["id"], status=status, initial_training_loss=initial_training_loss,
                elapsed_seconds=time.perf_counter() - started,
                non_finite_event_count=non_finite_events,
            )
        with self.repository.transaction() as connection:
            self.repository.update_run(
                connection, run_row["id"],
                {
                    "status": status,
                    "assistant_target_tokens": result.processed_target_tokens,
                    "prompt_tokens": result.processed_prompt_tokens,
                    "ignored_tokens": result.processed_ignored_tokens,
                    "processed_examples": (
                        result.completed_steps * config.gradient_accumulation_steps
                    ),
                    "input_stream_checksum_sha256": built["coverage"][
                        "input_stream_checksum_sha256"
                    ],
                    "label_stream_checksum_sha256": built["coverage"][
                        "label_stream_checksum_sha256"
                    ],
                },
            )
        return {
            "status": status,
            "checkpoint_public_id": checkpoint["public_id"],
            "initial_loss": result.initial_loss,
            "final_loss": result.final_loss,
            "validation_loss": result.validation_loss,
            "processed_tokens": result.processed_tokens,
            "assistant_target_tokens": result.processed_target_tokens,
            "prompt_tokens": result.processed_prompt_tokens,
            "ignored_tokens": result.processed_ignored_tokens,
        }

    # --- evaluation -----------------------------------------------------

    def evaluate_run(self, run_public_id: str, admin_id: str) -> dict[str, Any]:
        return self._evaluate_run(run_public_id, admin_id, include_test=False)

    def _resolve_checkpoint(self, connection, job) -> Any:
        checkpoint = connection.execute(
            """SELECT * FROM pretraining_checkpoints WHERE pretraining_job_id=?
            AND public_id=COALESCE(
                (SELECT best_checkpoint_public_id FROM pretraining_jobs WHERE id=?),
                (SELECT public_id FROM pretraining_checkpoints
                WHERE pretraining_job_id=? AND is_latest=1)
            )""",
            (job["id"], job["id"], job["id"]),
        ).fetchone()
        if checkpoint is None:
            raise ValidationError("run has no checkpoint available for evaluation")
        return checkpoint

    def _load_model_and_processor(self, job, checkpoint):
        from core_model.architecture.model import BrudForCausalLM
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        model_config = self.pretraining_service._model_config(job)
        manager = TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
        )
        checkpoint_dir = self.settings.resolved_pretraining_dir / checkpoint["safe_name"]
        model = BrudForCausalLM(model_config)
        checkpoint_verified = False
        try:
            states = manager.load_states(checkpoint_dir)
            model.load_state_dict(states["model"])
            checkpoint_verified = True
        except (OSError, ValueError, RuntimeError):
            pass
        processor = TokenizerService(
            TokenizerRepository(self.repository.database_path), self.settings
        ).processor_for_version(job["tokenizer_version_public_id"])
        return model, processor, model_config, checkpoint_verified

    def _evaluate_run(
        self, run_public_id: str, admin_id: str, *, include_test: bool
    ) -> dict[str, Any]:
        from core_model.instruction_tuning.generation import generate_greedy
        from core_model.training.trainer import instruction_response_loss

        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            if run["job_status"] not in {"completed", "completed_with_warnings"}:
                raise ValidationError("run must complete before evaluation")
            if include_test and run["test_evaluated"]:
                raise ValidationError("test split has already been evaluated once for this run")
            job = self.pretraining_repository.job(connection, run["pretraining_job_public_id"])
            checkpoint = self._resolve_checkpoint(connection, job)
            experiment = self.repository.experiment(connection, run["experiment_public_id"])
            job_config = from_mapping(loads_json(job["configuration_json"]))
            model_config_for_build = self.pretraining_service._model_config(job)
            built = self._build_examples(
                connection, experiment, shuffle=False,
                sequence_length=min(
                    job_config.sequence_length, model_config_for_build.context_length
                ),
            )

        model, processor, model_config, checkpoint_verified = self._load_model_and_processor(
            job, checkpoint
        )

        reliability = TrainingReliabilityRepository(self.repository.database_path)
        evaluation_service = TrainingEvaluationService(
            self.pretraining_repository, reliability, self.settings
        )
        run_summary = self._safe_run_summary(evaluation_service, run["pretraining_job_public_id"])
        stream_verification = evaluation_service.verify_streams(
            run["pretraining_job_public_id"], admin_id
        )

        target_split = "test" if include_test else "validation"
        examples = built[target_split]

        evaluation_id_holder: dict[str, str] = {}
        with self.repository.transaction() as connection:
            evaluation_type = "test_response_loss" if include_test else "validation_response_loss"
            evaluation_id = self.repository.record_evaluation(
                connection, run["id"],
                {
                    "evaluation_type": evaluation_type,
                    "split": target_split,
                    "checkpoint_public_id": checkpoint["public_id"],
                    "summary_json": dumps_json({"fixture_version": FIXTURE_VERSION}),
                },
            )
            evaluation_id_holder["public_id"] = evaluation_id

        languages_with_metrics: set[str] = set()
        overall_response_loss: float | None = None
        with self.repository.transaction() as connection:
            evaluation_row = self.repository.evaluation(
                connection, evaluation_id_holder["public_id"]
            )
            for language in (*LANGUAGES, "overall"):
                subset = [
                    (a, b, c)
                    for a, b, c, lang in examples
                    if language == "overall" or lang == language
                ]
                result = instruction_response_loss(model, subset, max_batches=200)
                if result["tokens"]:
                    languages_with_metrics.add(language)
                if language == "overall":
                    overall_response_loss = result["loss"]
                self.repository.record_evaluation_result(
                    connection, evaluation_row["id"],
                    {
                        "language": language,
                        "metric_name": "response_loss",
                        "metric_value": result["loss"],
                        "sample_count": len(subset),
                        "details_json": dumps_json(
                            {"perplexity": result["perplexity"], "tokens": result["tokens"]}
                        ),
                    },
                )

        # bounded diagnostic-generation-based structural checks, fixed fixtures only
        fixtures = all_fixtures()
        generation_evaluation_id_holder: dict[str, str] = {}
        with self.repository.transaction() as connection:
            generation_evaluation_id = self.repository.record_evaluation(
                connection, run["id"],
                {
                    "evaluation_type": "bounded_generation_sample",
                    "split": target_split,
                    "checkpoint_public_id": checkpoint["public_id"],
                    "summary_json": dumps_json({"fixture_version": FIXTURE_VERSION}),
                },
            )
            generation_evaluation_id_holder["public_id"] = generation_evaluation_id

        role_leak_count = 0
        prompt_leak_count = 0
        repetition_flag_count = 0
        total_generations = 0
        instruction_format_pass_count = 0
        generated_texts: list[str] = []
        max_new_tokens = self.settings.instruction_tuning_generation_max_new_tokens
        timeout_seconds = self.settings.instruction_tuning_generation_timeout_seconds

        with self.repository.transaction() as connection:
            gen_eval_row = self.repository.evaluation(
                connection, generation_evaluation_id_holder["public_id"]
            )
            for language in LANGUAGES:
                for prompt_text, expected_language, _format_category in fixtures.get(language, ()):
                    generation = generate_greedy(
                        model, processor, prompt_text,
                        max_new_tokens=max_new_tokens, eos_token_id=model_config.eos_token_id,
                        sequence_length=model_config.context_length,
                        vocabulary_size=model_config.vocabulary_size,
                        timeout_seconds=timeout_seconds,
                    )
                    text = generation["generated_text"]
                    generated_texts.append(text)
                    total_generations += 1
                    checks = {
                        "response_not_empty": response_not_empty(text),
                        "no_role_token_leakage": no_role_token_leakage(text),
                        "no_system_prompt_leakage": no_system_prompt_leakage(
                            text, None, prompt_text
                        ),
                        "no_excessive_repetition": no_excessive_repetition(text),
                        "bounded_length": bounded_length(text, max_chars=2000),
                        "valid_unicode": valid_unicode(text),
                    }
                    if checks["no_role_token_leakage"]["status"] != "pass":
                        role_leak_count += 1
                    if checks["no_system_prompt_leakage"]["status"] != "pass":
                        prompt_leak_count += 1
                    if checks["no_excessive_repetition"]["status"] != "pass":
                        repetition_flag_count += 1
                    if all(item["status"] == "pass" for item in checks.values()):
                        instruction_format_pass_count += 1
                    self.repository.record_evaluation_result(
                        connection, gen_eval_row["id"],
                        {
                            "language": language,
                            "metric_name": "generation_check",
                            "metric_value": 1.0 if all(
                                item["status"] == "pass" for item in checks.values()
                            ) else 0.0,
                            "sample_count": 1,
                            "details_json": dumps_json(
                                {"expected_language": expected_language, "checks": checks}
                            ),
                        },
                    )

        role_leakage_rate = role_leak_count / total_generations if total_generations else 0.0
        prompt_leakage_rate = prompt_leak_count / total_generations if total_generations else 0.0
        repetition_rate = repetition_flag_count / total_generations if total_generations else 0.0
        instruction_format_status = (
            "pass" if instruction_format_pass_count == total_generations
            else "warning" if instruction_format_pass_count > 0
            else "fail"
        )

        with self.repository.transaction() as connection:
            training_response_hashes = {
                hashlib.sha256(response.strip().encode("utf-8")).hexdigest()
                for response in self._train_response_texts(connection, experiment)
            }
        memorization_thresholds = MemorizationThresholds(
            max_exact_match_rate=self.settings.instruction_tuning_max_exact_match_rate,
            max_duplicate_output_rate=self.settings.instruction_tuning_max_duplicate_output_rate,
            max_longest_span_ratio=self.settings.instruction_tuning_max_longest_span_ratio,
            max_train_validation_gap=self.settings.instruction_tuning_max_train_validation_gap,
        )
        mem_warnings = memorization_warnings(
            generated_texts=generated_texts,
            training_response_hashes=training_response_hashes,
            training_responses_sample=self._train_response_sample(experiment),
            train_loss=run_summary.get("final_training_loss"),
            validation_response_loss=overall_response_loss,
            thresholds=memorization_thresholds,
        )

        train_validation_gap = None
        if overall_response_loss is not None and run_summary.get("final_training_loss") is not None:
            train_validation_gap = overall_response_loss - run_summary["final_training_loss"]

        thresholds = InstructionLearningCheckThresholds(
            max_role_leakage_rate=self.settings.instruction_tuning_max_role_leakage_rate,
            max_prompt_leakage_rate=self.settings.instruction_tuning_max_prompt_leakage_rate,
            max_repetition_rate=self.settings.instruction_tuning_max_repetition_rate,
        )
        check_inputs = {
            "assistant_target_tokens": run["assistant_target_tokens"],
            "prompt_tokens": run["prompt_tokens"],
            "initial_training_loss": run_summary.get("initial_training_loss"),
            "final_training_loss": run_summary.get("final_training_loss"),
            "validation_response_loss": overall_response_loss,
            "languages_expected": set(LANGUAGES),
            "languages_with_metrics": languages_with_metrics,
            "instruction_format_status": instruction_format_status,
            "role_leakage_rate": role_leakage_rate,
            "prompt_leakage_rate": prompt_leakage_rate,
            "repetition_rate": repetition_rate,
            "memorization_warning_count": len(mem_warnings),
            "checkpoint_verified": checkpoint_verified,
            "base_model_lineage_complete": bool(
                experiment["base_core_model_version_public_id"]
                and experiment["source_base_checkpoint_public_id"]
                and experiment["dataset_version_public_id"]
                and experiment["tokenizer_version_public_id"]
            ),
            "resource_limit_exceeded": False,
        }
        checks = run_learning_checks(check_inputs, thresholds)
        with self.repository.transaction() as connection:
            for check in checks:
                self.repository.record_learning_check(
                    connection, run["id"],
                    {
                        "check_code": check["check_code"],
                        "status": check["status"],
                        "message": check["message"],
                        "details_json": dumps_json(check["details"]),
                    },
                )
            if include_test:
                self.repository.update_run(connection, run["id"], {"test_evaluated": 1})
            self._audit(
                connection, "instruction_tuning_run_evaluated", admin_id, run_public_id,
                include_test=include_test,
            )
        return {
            "checkpoint_public_id": checkpoint["public_id"],
            "run_summary": run_summary,
            "overall_response_loss": overall_response_loss,
            "learning_checks": checks,
            "train_validation_gap": train_validation_gap,
            "role_leakage_rate": role_leakage_rate,
            "prompt_leakage_rate": prompt_leakage_rate,
            "repetition_rate": repetition_rate,
            "memorization_warnings": mem_warnings,
            "stream_verification": stream_verification,
        }

    def _train_response_texts(self, connection, experiment) -> list[str]:
        rows = connection.execute(
            """SELECT r.output_text,r.record_type FROM dataset_version_items i
            JOIN dataset_records r ON r.id=i.dataset_record_id
            WHERE i.dataset_version_id=? AND i.split='train'""",
            (experiment["dataset_version_id"],),
        ).fetchall()
        return [row["output_text"] for row in rows if row["output_text"]]

    def _train_response_sample(self, experiment) -> list[str]:
        with self.repository.transaction() as connection:
            return self._train_response_texts(connection, experiment)[:50]

    def metrics(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            rows = self.repository.metrics(connection, run["id"])
        return {"items": [public_row(row) for row in rows]}

    def language_metrics(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            evaluations = self.repository.evaluations_for_run(connection, run["id"])
            items = []
            for evaluation in evaluations:
                if evaluation["evaluation_type"] not in {
                    "validation_response_loss", "test_response_loss",
                }:
                    continue
                for result in self.repository.evaluation_results(connection, evaluation["id"]):
                    items.append(public_row(result))
        return {"items": items}

    def learning_checks_for_run(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            rows = self.repository.learning_checks(connection, run["id"])
        return {"items": [public_row(row) for row in rows]}

    # --- diagnostic generation -----------------------------------------------------

    def diagnostic_generate(
        self, run_public_id: str, prompt_text: str, max_new_tokens: int, admin_id: str
    ) -> dict[str, Any]:
        from core_model.instruction_tuning.generation import generate_greedy

        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            if run["job_status"] not in {"completed", "completed_with_warnings"}:
                raise ValidationError("run must complete before diagnostic generation")
            job = self.pretraining_repository.job(connection, run["pretraining_job_public_id"])
            checkpoint = self._resolve_checkpoint(connection, job)
        self._guard_resources()
        model, processor, model_config, checkpoint_verified = self._load_model_and_processor(
            job, checkpoint
        )
        if not checkpoint_verified:
            raise ValidationError("checkpoint could not be verified for diagnostic generation")
        bounded_new_tokens = min(
            max_new_tokens, self.settings.instruction_tuning_generation_max_new_tokens
        )
        result = generate_greedy(
            model, processor, prompt_text,
            max_new_tokens=bounded_new_tokens, eos_token_id=model_config.eos_token_id,
            sequence_length=model_config.context_length,
            vocabulary_size=model_config.vocabulary_size,
            timeout_seconds=self.settings.instruction_tuning_generation_timeout_seconds,
        )
        with self.repository.transaction() as connection:
            self._audit(
                connection, "instruction_tuning_diagnostic_generated", admin_id, run_public_id,
                stopped_reason=result["stopped_reason"],
            )
        return {
            "generated_text": result["generated_text"],
            "stopped_reason": result["stopped_reason"],
            "output_token_count": result["output_token_count"],
            "notice": "Admin-only bounded diagnostic generation. This is not the public chatbot.",
        }

    # --- comparisons -----------------------------------------------------

    def compare_runs(self, public_id: str, left: str, right: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            left_run = self.repository.run(connection, left)
            right_run = self.repository.run(connection, right)
            if (
                left_run["instruction_tuning_experiment_id"] != experiment["id"]
                or right_run["instruction_tuning_experiment_id"] != experiment["id"]
            ):
                raise ValidationError("both runs must belong to this experiment")
        reliability = TrainingReliabilityRepository(self.repository.database_path)
        evaluation_service = TrainingEvaluationService(
            self.pretraining_repository, reliability, self.settings
        )
        return evaluation_service.compare_runs(
            left_run["pretraining_job_public_id"], right_run["pretraining_job_public_id"], admin_id
        )

    def comparisons(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            runs = self.repository.runs_for_experiment(connection, experiment["id"])
            job_public_ids = {
                row["pretraining_job_public_id"] for row in runs if row["pretraining_job_public_id"]
            }
            if not job_public_ids:
                return {"items": []}
            placeholders = ",".join("?" for _ in job_public_ids)
            rows = connection.execute(
                f"""SELECT * FROM training_run_comparisons
                WHERE left_job_public_id IN ({placeholders})
                OR right_job_public_id IN ({placeholders})
                ORDER BY created_at DESC""",
                (*job_public_ids, *job_public_ids),
            ).fetchall()
        return {"items": [dict(row) for row in rows]}

    # --- candidate selection -----------------------------------------------------

    def _best_validation_loss(self, connection, run_id: int) -> float:
        row = connection.execute(
            """SELECT j.latest_validation_loss FROM instruction_tuning_runs r
            JOIN pretraining_jobs j ON j.id=r.pretraining_job_id WHERE r.id=?""",
            (run_id,),
        ).fetchone()
        value = row["latest_validation_loss"] if row else None
        return value if value is not None else float("inf")

    def select_candidate(
        self, public_id: str, override_comment: str | None, admin_id: str
    ) -> dict[str, Any]:
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            runs = self.repository.runs_for_experiment(connection, experiment["id"])
            completed = [
                row for row in runs
                if row["job_status"] in {"completed", "completed_with_warnings"}
            ]
            if not completed:
                selection_id = self.repository.record_candidate(
                    connection, experiment["id"],
                    {
                        "status": "rejected",
                        "rationale_json": dumps_json({"reason": "no completed runs available"}),
                        "created_by_admin_public_id": admin_id,
                    },
                )
                self.repository.update_experiment(
                    connection, experiment["id"], {"latest_candidate_public_id": selection_id}
                )
                return public_row(self.repository.latest_candidate(connection, experiment["id"]))
            best_run = min(
                completed, key=lambda row: self._best_validation_loss(connection, row["id"])
            )
            best_run_public_id = best_run["public_id"]
            base_checkpoint_before = connection.execute(
                "SELECT model_checksum_sha256,safe_name FROM pretraining_checkpoints WHERE id=?",
                (experiment["source_base_checkpoint_id"],),
            ).fetchone()

        evaluation = self._evaluate_run(best_run_public_id, admin_id, include_test=True)

        base_checkpoint_after_verified = False
        try:
            TrainingCheckpointManager(
                self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
            ).verify(self.settings.resolved_pretraining_dir / base_checkpoint_before["safe_name"])
            base_checkpoint_after_verified = True
        except (OSError, ValueError):
            base_checkpoint_after_verified = False

        with self.repository.transaction() as connection:
            best_run = self.repository.run(connection, best_run_public_id)

        reliability = TrainingReliabilityRepository(self.repository.database_path)
        evaluation_service = TrainingEvaluationService(
            self.pretraining_repository, reliability, self.settings
        )
        quality = evaluation_service.assess_quality(best_run["pretraining_job_public_id"], admin_id)

        checks = evaluation["learning_checks"]
        has_blocking_failure = any(
            check["status"] == "fail" and check["check_code"] in BLOCKING_CHECK_CODES
            for check in checks
        )
        has_severe_leakage = (
            evaluation["role_leakage_rate"] > 0 or evaluation["prompt_leakage_rate"] > 0.5
        )
        has_warning = any(check["status"] != "pass" for check in checks) or evaluation[
            "memorization_warnings"
        ]
        role_leakage_result = "bounded" if evaluation["role_leakage_rate"] == 0 else "severe"

        promoted_model_public_id = None
        if (
            quality["readiness_status"] == "blocked"
            or has_blocking_failure
            or has_severe_leakage
            or not base_checkpoint_after_verified
        ):
            status = "rejected"
        else:
            status = "instruction_tuned_with_warnings" if (
                quality["readiness_status"] == "warning" or has_warning
            ) else "instruction_tuned_candidate"
            promoted_model_public_id = self._promote_instruction_candidate(
                evaluation["checkpoint_public_id"], experiment, admin_id, override_comment
            )

        with self.repository.transaction() as connection:
            selection_id = self.repository.record_candidate(
                connection, experiment["id"],
                {
                    "selected_run_id": best_run["id"],
                    "selected_checkpoint_public_id": evaluation["checkpoint_public_id"],
                    "status": status,
                    "role_leakage_result": role_leakage_result,
                    "memorization_warning_count": len(evaluation["memorization_warnings"]),
                    "base_checkpoint_checksum_before": (
                        base_checkpoint_before["model_checksum_sha256"]
                    ),
                    "base_checkpoint_checksum_after": (
                        base_checkpoint_before["model_checksum_sha256"]
                        if base_checkpoint_after_verified
                        else None
                    ),
                    "rationale_json": dumps_json(
                        {
                            "quality_readiness_status": quality["readiness_status"],
                            "memorization_warnings": evaluation["memorization_warnings"],
                            "promoted_model_public_id": promoted_model_public_id,
                            "override_comment": override_comment,
                            "role_leakage_rate": evaluation["role_leakage_rate"],
                            "prompt_leakage_rate": evaluation["prompt_leakage_rate"],
                        }
                    ),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self.repository.update_experiment(
                connection, experiment["id"],
                {"latest_candidate_public_id": selection_id, "status": "completed"},
            )
            self._audit(
                connection, "instruction_tuning_candidate_selected", admin_id, public_id,
                status=status,
            )
            return public_row(self.repository.latest_candidate(connection, experiment["id"]))

    def _promote_instruction_candidate(
        self, checkpoint_public_id: str, experiment, admin_id: str, override_comment: str | None
    ) -> str:
        with self.repository.transaction() as connection:
            checkpoint = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?", (checkpoint_public_id,)
            ).fetchone()
            base_model = connection.execute(
                "SELECT * FROM core_model_versions WHERE id=?",
                (experiment["base_core_model_version_id"],),
            ).fetchone()
        verify = self.pretraining_service.verify_checkpoint(checkpoint_public_id, admin_id)
        if not verify["verified"]:
            raise ValidationError("only verified checkpoints can be promoted")
        with self.repository.transaction() as connection:
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
                    base_model["core_model_family_id"],
                    f"{base_model['version']}-instruction-tuned-{checkpoint['step']}",
                    "staging",
                    base_model["config_id"],
                    base_model["tokenizer_version_id"],
                    base_model["architecture_name"],
                    base_model["estimated_parameter_count"],
                    base_model["actual_parameter_count"],
                    base_model["estimated_inference_memory_bytes"],
                    base_model["estimated_training_memory_bytes"],
                    base_model["initialization_seed"],
                    checkpoint["model_checksum_sha256"],
                    base_model["config_checksum_sha256"],
                    dumps_json(
                        {
                            "base_pretrained": True,
                            "instruction_tuned": True,
                            "evaluation_required": True,
                            "not_public_chat_ready": True,
                            "source_experiment_public_id": experiment["public_id"],
                            "source_base_model_public_id": base_model["public_id"],
                            "override_comment": override_comment,
                        }
                    ),
                    dumps_json({}),
                ),
            )
            self._audit(
                connection, "instruction_tuning_candidate_promoted", admin_id, promoted_id,
                source_checkpoint=checkpoint_public_id,
            )
        return promoted_id

    def candidate(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            row = self.repository.latest_candidate(connection, experiment["id"])
        if row is None:
            raise NotFoundError("no candidate has been selected for this experiment")
        return public_row(row)

    # --- reproducibility manifest -----------------------------------------------------

    def generate_manifest(self, public_id: str, admin_id: str) -> dict[str, Any]:
        import torch

        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            runs = self.repository.runs_for_experiment(connection, experiment["id"])
            profile = self.repository.latest_profile(connection, experiment["id"])
            candidate_row = self.repository.latest_candidate(connection, experiment["id"])
            dataset_checksum = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE id=?",
                (experiment["dataset_version_id"],),
            ).fetchone()[0]
            tokenizer_checksum = connection.execute(
                "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE id=?",
                (experiment["tokenizer_version_id"],),
            ).fetchone()[0]
            template_row = (
                connection.execute(
                    "SELECT template_checksum_sha256 FROM instruction_format_templates WHERE id=?",
                    (experiment["instruction_template_id"],),
                ).fetchone()
                if experiment["instruction_template_id"]
                else None
            )
            base_checkpoint = connection.execute(
                "SELECT model_checksum_sha256 FROM pretraining_checkpoints WHERE id=?",
                (experiment["source_base_checkpoint_id"],),
            ).fetchone()
            run_entries = []
            for run in runs:
                job = (
                    self.pretraining_repository.job(connection, run["pretraining_job_public_id"])
                    if run["pretraining_job_public_id"]
                    else None
                )
                checkpoints = connection.execute(
                    """SELECT public_id,combined_checksum_sha256,step,is_best
                    FROM pretraining_checkpoints WHERE pretraining_job_id=?""",
                    (job["id"],),
                ).fetchall() if job else []
                run_entries.append(
                    {
                        "run_public_id": run["public_id"],
                        "run_label": run["run_label"],
                        "job_status": run["job_status"],
                        "config_diff": loads_json(run["config_diff_json"]),
                        "assistant_target_tokens": run["assistant_target_tokens"],
                        "prompt_tokens": run["prompt_tokens"],
                        "ignored_tokens": run["ignored_tokens"],
                        "input_stream_checksum_sha256": run["input_stream_checksum_sha256"],
                        "label_stream_checksum_sha256": run["label_stream_checksum_sha256"],
                        "checkpoint_checksums": [
                            {
                                "public_id": row["public_id"],
                                "combined_checksum_sha256": row["combined_checksum_sha256"],
                                "step": row["step"],
                                "is_best": bool(row["is_best"]),
                            }
                            for row in checkpoints
                        ],
                    }
                )
            manifest = {
                "experiment_public_id": experiment["public_id"],
                "run_public_ids": [run["public_id"] for run in runs],
                "dataset_version_public_id": experiment["dataset_version_public_id"],
                "dataset_checksum_sha256": dataset_checksum,
                "dataset_profile_checksum_sha256": (
                    profile["profile_checksum_sha256"] if profile else None
                ),
                "tokenizer_version_public_id": experiment["tokenizer_version_public_id"],
                "tokenizer_checksum_sha256": tokenizer_checksum,
                "base_model_public_id": experiment["base_core_model_version_public_id"],
                "base_checkpoint_checksum_sha256": (
                    base_checkpoint["model_checksum_sha256"] if base_checkpoint else None
                ),
                "instruction_template_checksum_sha256": (
                    template_row["template_checksum_sha256"] if template_row else None
                ),
                "initialization_seed": experiment["initialization_seed"],
                "sampling_seed": experiment["sampling_seed"],
                "training_configuration": loads_json(experiment["training_configuration_json"]),
                "optimizer": "adamw",
                "software_versions": {
                    "pytorch": torch.__version__,
                    "fixture_version": FIXTURE_VERSION,
                },
                "runs": run_entries,
                "candidate_selection": public_row(candidate_row) if candidate_row else None,
                "known_limitations": self._known_limitations(profile),
            }
            manifest_json = dumps_json(manifest)
            checksum = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
            manifest_public_id = self.repository.record_manifest(
                connection, experiment["id"], manifest_json, checksum
            )
            self.repository.update_experiment(
                connection, experiment["id"], {"latest_manifest_public_id": manifest_public_id}
            )
            self._audit(connection, "instruction_tuning_manifest_generated", admin_id, public_id)
            return public_row(self.repository.latest_manifest(connection, experiment["id"]))

    def verify_manifest(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            row = self.repository.latest_manifest(connection, experiment["id"])
            if row is None:
                raise NotFoundError("no reproducibility manifest exists for this experiment")
            recomputed = hashlib.sha256(row["manifest_json"].encode("utf-8")).hexdigest()
            matches = recomputed == row["manifest_checksum_sha256"]
        return {
            "public_id": row["public_id"],
            "stored_checksum": row["manifest_checksum_sha256"],
            "recomputed_checksum": recomputed,
            "matches": matches,
        }

    # --- helpers -----------------------------------------------------

    def _safe_run_summary(
        self, evaluation_service: TrainingEvaluationService, job_public_id: str
    ) -> dict[str, Any]:
        try:
            return evaluation_service.run_summary(job_public_id)
        except NotFoundError:
            return {}

    def _known_limitations(self, profile) -> dict[str, Any]:
        sufficiency = profile["data_sufficiency_status"] if profile else "insufficient"
        test_reliable = bool(
            profile and profile["test_count"] >= self.settings.instruction_tuning_min_test_records
        )
        limitations: dict[str, Any] = {
            "data_sufficiency_status": sufficiency,
            "test_evaluation_reliable": test_reliable,
        }
        if not test_reliable:
            limitations["test_evaluation_notice"] = "TEST_EVALUATION_NOT_RELIABLE"
        if sufficiency != "sufficient":
            limitations["data_sufficiency_notice"] = (
                "dataset is below the recommended 1,000-record minimum; this experiment is a "
                "limited-scale trial, not a representative-scale result"
            )
        limitations["generation_evidence_notice"] = (
            "instruction tuning teaches response behavior and formatting; it does not prove "
            "factual accuracy, safety, or production chat readiness"
        )
        return limitations

    def _guard_single_active_job(self, connection) -> None:
        active = connection.execute(
            "SELECT 1 FROM pretraining_jobs WHERE status='running' LIMIT 1"
        ).fetchone()
        if active:
            raise ValidationError(
                "another pretraining job is currently running; only one active job is allowed"
            )

    def _guard_resources(self) -> None:
        available = available_memory_bytes()
        min_available = self.settings.pretraining_min_available_memory_bytes
        if available is not None and available < min_available:
            raise ValidationError("available memory is below the configured safety threshold")
        disk_check_path = self.settings.resolved_pretraining_dir
        while not disk_check_path.exists():
            disk_check_path = disk_check_path.parent
        free_disk = shutil.disk_usage(disk_check_path).free
        if free_disk < self.settings.pretraining_min_free_disk_bytes:
            raise ValidationError("available disk space is below the configured safety threshold")

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
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "instruction_tuning", resource_id, "success", dumps_json(metadata),
            ),
        )
