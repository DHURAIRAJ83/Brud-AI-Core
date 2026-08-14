"""Phase 11 base-training experiment orchestration.

Reuses the existing Phase 9/10 pretraining job, tokenizer, checkpoint, and
quality-gate machinery rather than duplicating a trainer. This module only
adds: dataset profiling, tokenizer suitability decisions, per-language
evaluation, learning checks, generalization/memorization classification,
candidate selection, and the reproducibility manifest.
"""

from __future__ import annotations

import hashlib
import math
import shutil
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.base_training import BaseTrainingRepository, public_row
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.models.base_training import (
    BaseTrainingExperimentCreate,
    BaseTrainingExperimentPatch,
    BaseTrainingRunCreate,
)
from backend.models.pretraining import PretrainingJobCreate
from backend.services.pretraining_service import PretrainingService
from backend.services.tokenizer_registry import TokenizerService
from backend.services.training_evaluation_service import TrainingEvaluationService
from core_model.architecture.config import BrudModelConfig
from core_model.training.dataset_profile import (
    ProfileThresholds,
    build_dataset_profile,
    data_sufficiency_status,
    evaluate_warnings,
)
from core_model.training.dataset_stream import record_text_fields
from core_model.training.fixed_eval_fixtures import FIXTURE_VERSION, all_fixtures
from core_model.training.learning_checks import (
    LearningCheckThresholds,
    classify_generalization,
    memorization_warnings,
    run_learning_checks,
)
from core_model.training.metrics import available_memory_bytes

LANGUAGES = ("ta", "en", "tgl", "mixed")


class BaseTrainingService:
    def __init__(
        self,
        repository: BaseTrainingRepository,
        pretraining_repository: PretrainingRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.pretraining_repository = pretraining_repository
        self.settings = settings

    # --- experiments -----------------------------------------------------

    def create_experiment(
        self, payload: BaseTrainingExperimentCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            dataset = connection.execute(
                "SELECT id,status FROM dataset_versions WHERE public_id=?",
                (payload.dataset_version_public_id,),
            ).fetchone()
            if not dataset or dataset["status"] not in {"ready", "archived"}:
                raise ValidationError("ready or archived dataset version is required")
            public_id = self.repository.create_experiment(
                connection,
                {
                    "name": payload.name,
                    "objective": payload.objective,
                    "dataset_version_id": dataset["id"],
                    "initialization_seed": payload.initialization_seed,
                    "sampling_seed": payload.sampling_seed,
                    "training_configuration_json": dumps_json(payload.training_configuration),
                    "evaluation_configuration_json": dumps_json(payload.evaluation_configuration),
                    "resource_limits_json": dumps_json(payload.resource_limits),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "base_training_experiment_created", admin_id, public_id)
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
        self, public_id: str, payload: BaseTrainingExperimentPatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            fields: dict[str, Any] = {}
            if payload.name is not None:
                fields["name"] = payload.name
            if payload.objective is not None:
                fields["objective"] = payload.objective
            if payload.tokenizer_version_public_id is not None:
                tokenizer = connection.execute(
                    "SELECT id,lifecycle_status FROM tokenizer_versions WHERE public_id=?",
                    (payload.tokenizer_version_public_id,),
                ).fetchone()
                if not tokenizer or tokenizer["lifecycle_status"] not in {
                    "active", "staging", "retired", "archived",
                }:
                    raise ValidationError("verified tokenizer version is required")
                fields["tokenizer_version_id"] = tokenizer["id"]
            if payload.core_model_version_public_id is not None:
                model = connection.execute(
                    "SELECT id,lifecycle_status FROM core_model_versions WHERE public_id=?",
                    (payload.core_model_version_public_id,),
                ).fetchone()
                if not model or model["lifecycle_status"] not in {
                    "architecture_verified", "smoke_tested", "staging", "active",
                }:
                    raise ValidationError("architecture-verified core model version is required")
                fields["core_model_version_id"] = model["id"]
            self.repository.update_experiment(connection, experiment["id"], fields)
            self._audit(connection, "base_training_experiment_updated", admin_id, public_id)
            return public_row(self.repository.experiment(connection, public_id))

    # --- dataset profile -----------------------------------------------------

    def generate_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            rows = connection.execute(
                """SELECT r.*,i.split,s.source_type,s.licence_status
                FROM dataset_version_items i
                JOIN dataset_records r ON r.id=i.dataset_record_id
                JOIN dataset_sources s ON s.id=r.source_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
                (experiment["dataset_version_id"],),
            ).fetchall()
            records = [dict(row) for row in rows]
            processor, eos_id = self._processor_for_experiment(connection, experiment)
            sequence_length = loads_json(experiment["evaluation_configuration_json"]).get(
                "sequence_length", 128
            )
            profile = build_dataset_profile(
                records, processor, eos_id=eos_id, sequence_length=sequence_length
            )
            thresholds = ProfileThresholds(
                min_records=self.settings.base_training_min_records,
                min_tamil_ratio=self.settings.base_training_min_tamil_ratio,
                min_english_ratio=self.settings.base_training_min_english_ratio,
                min_tanglish_ratio=self.settings.base_training_min_tanglish_ratio,
                max_duplicate_ratio=self.settings.base_training_max_duplicate_ratio,
                min_validation_records=self.settings.base_training_min_validation_records,
                min_test_records=self.settings.base_training_min_test_records,
            )
            warnings = evaluate_warnings(profile, thresholds)
            sufficiency = data_sufficiency_status(profile, thresholds)
            public_profile_id = self.repository.record_profile(
                connection,
                experiment["id"],
                {
                    "dataset_version_id": experiment["dataset_version_id"],
                    "total_records": profile["total_records"],
                    "approved_records": profile["approved_records"],
                    "train_count": profile["train_count"],
                    "validation_count": profile["validation_count"],
                    "test_count": profile["test_count"],
                    "total_characters": profile["total_characters"],
                    "total_tokens": profile["total_tokens"],
                    "unique_token_count": profile["unique_token_count"],
                    "language_distribution_json": dumps_json(
                        profile["language_distribution"]
                    ),
                    "record_type_distribution_json": dumps_json(
                        profile["record_type_distribution"]
                    ),
                    "source_distribution_json": dumps_json(profile["source_distribution"]),
                    "licence_distribution_json": dumps_json(profile["licence_distribution"]),
                    "average_record_length": profile["average_record_length"],
                    "median_record_length": profile["median_record_length"],
                    "maximum_record_length": profile["maximum_record_length"],
                    "duplicate_rate": profile["duplicate_rate"],
                    "near_duplicate_rate": profile["near_duplicate_rate"],
                    "zero_token_rate": profile["zero_token_rate"],
                    "oversized_record_rate": profile["oversized_record_rate"],
                    "validation_representativeness_json": dumps_json(
                        profile["validation_representativeness"]
                    ),
                    "test_representativeness_json": dumps_json(profile["test_representativeness"]),
                    "tamil_script_coverage": profile["tamil_script_coverage"],
                    "english_latin_coverage": profile["english_latin_coverage"],
                    "tanglish_coverage": profile["tanglish_coverage"],
                    "mixed_script_coverage": profile["mixed_script_coverage"],
                    "warnings_json": dumps_json(warnings),
                    "data_sufficiency_status": sufficiency,
                    "profile_checksum_sha256": profile["profile_checksum_sha256"],
                },
            )
            fields = {"latest_profile_public_id": public_profile_id}
            if experiment["status"] == "draft":
                fields["status"] = "profiled"
            self.repository.update_experiment(connection, experiment["id"], fields)
            self._audit(
                connection, "base_training_profile_generated", admin_id, public_id,
                data_sufficiency_status=sufficiency,
            )
            return public_row(
                self.repository.latest_profile(connection, experiment["id"])
            )

    def get_profile(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            row = self.repository.latest_profile(connection, experiment["id"])
        if row is None:
            raise NotFoundError("dataset profile has not been generated for this experiment")
        return public_row(row)

    # --- tokenizer suitability -----------------------------------------------------

    def evaluate_tokenizer(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            tokenizer_row = self._resolve_tokenizer(connection, experiment)
            if tokenizer_row is None:
                decision = "blocked_tokenizer_unsuitable"
                evaluation: dict[str, Any] = {"reason": "no registered tokenizer is available"}
            else:
                tokenizer_service = TokenizerService(
                    TokenizerRepository(self.repository.database_path), self.settings
                )
                evaluation = tokenizer_service.evaluate_suitability(
                    tokenizer_row["public_id"], experiment["dataset_version_public_id"]
                )
                overall = evaluation["metrics"]["overall"]
                min_round_trip = self.settings.base_training_tokenizer_min_round_trip
                max_unknown_rate = self.settings.base_training_tokenizer_max_unknown_rate
                if overall["round_trip_success_rate"] < min_round_trip:
                    decision = "blocked_tokenizer_unsuitable"
                elif overall["unknown_token_rate"] > max_unknown_rate:
                    decision = "train_new_tokenizer_version"
                else:
                    decision = "reuse_existing_tokenizer"
            fields: dict[str, Any] = {
                "tokenizer_decision": decision,
                "tokenizer_evaluation_json": dumps_json(evaluation),
                "status": "tokenizer_evaluated",
            }
            if tokenizer_row is not None and not experiment["tokenizer_version_id"]:
                fields["tokenizer_version_id"] = tokenizer_row["id"]
            self.repository.update_experiment(connection, experiment["id"], fields)
            self._audit(
                connection, "base_training_tokenizer_evaluated", admin_id, public_id,
                decision=decision,
            )
            return {"tokenizer_decision": decision, "evaluation": evaluation}

    def get_tokenizer_evaluation(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
        return {
            "tokenizer_decision": experiment["tokenizer_decision"],
            "evaluation": loads_json(experiment["tokenizer_evaluation_json"]),
        }

    # --- runs -----------------------------------------------------

    def create_run(
        self, public_id: str, payload: BaseTrainingRunCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            if not experiment["tokenizer_version_id"] or not experiment["core_model_version_id"]:
                raise ValidationError(
                    "experiment requires an assigned tokenizer and core model version before runs"
                )
            if experiment["tokenizer_decision"] == "blocked_tokenizer_unsuitable":
                raise ValidationError("tokenizer was evaluated as unsuitable for this experiment")
            self._guard_single_active_job(connection)
            existing_runs = self.repository.runs_for_experiment(connection, experiment["id"])
            training_configuration = loads_json(experiment["training_configuration_json"])
            configuration = {**training_configuration, **payload.configuration}
            job_payload = PretrainingJobCreate(
                name=f"{experiment['name']} — {payload.run_label}",
                dataset_version_public_id=experiment["dataset_version_public_id"],
                tokenizer_version_public_id=experiment["tokenizer_version_public_id"],
                core_model_version_public_id=experiment["core_model_version_public_id"],
                job_mode="bounded_pretraining",
                configuration=configuration,
            )
        pretraining_service = PretrainingService(self.pretraining_repository, self.settings)
        job = pretraining_service.create_job(job_payload, admin_id)
        pretraining_service.validate_job(job["public_id"], admin_id)
        with self.repository.transaction() as connection:
            job_row = self.pretraining_repository.job(connection, job["public_id"])
            run_public_id = self.repository.create_run(
                connection,
                {
                    "base_training_experiment_id": experiment["id"],
                    "pretraining_job_id": job_row["id"],
                    "run_label": payload.run_label,
                    "run_index": len(existing_runs) + 1,
                    "config_diff_json": dumps_json(payload.config_diff),
                    "created_by_admin_public_id": admin_id,
                },
            )
            fields = {}
            if experiment["status"] in {"profiled", "tokenizer_evaluated"}:
                fields["status"] = "ready"
            if fields:
                self.repository.update_experiment(connection, experiment["id"], fields)
            self._audit(connection, "base_training_run_created", admin_id, run_public_id)
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
        pretraining_service = PretrainingService(self.pretraining_repository, self.settings)
        pretraining_service.queue_job(run["pretraining_job_public_id"], admin_id)
        with self.repository.transaction() as connection:
            self.repository.update_run(connection, run["id"], {"status": "queued"})
            self._audit(connection, "base_training_run_queued", admin_id, run_public_id)
            return public_row(self.repository.run(connection, run_public_id))

    def evaluate_run(self, run_public_id: str, admin_id: str) -> dict[str, Any]:
        return self._evaluate_run(run_public_id, admin_id, include_test=False)

    def _evaluate_run(
        self, run_public_id: str, admin_id: str, *, include_test: bool
    ) -> dict[str, Any]:
        from core_model.architecture.model import BrudForCausalLM
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
        from core_model.training.language_evaluation import evaluate_language_texts

        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            if run["job_status"] not in {"completed", "completed_with_warnings"}:
                raise ValidationError("run must complete before evaluation")
            if include_test and run["test_evaluated"]:
                raise ValidationError(
                    "test split has already been evaluated once for this run"
                )
            job = self.pretraining_repository.job(connection, run["pretraining_job_public_id"])
            model_config = self._model_config(connection, job)
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
            dataset_rows = connection.execute(
                """SELECT r.*,i.split FROM dataset_version_items i
                JOIN dataset_records r ON r.id=i.dataset_record_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
                (job["dataset_version_id"],),
            ).fetchall()
        reliability = TrainingReliabilityRepository(self.repository.database_path)
        evaluation_service = TrainingEvaluationService(
            self.pretraining_repository, reliability, self.settings
        )
        run_summary = self._safe_run_summary(evaluation_service, run["pretraining_job_public_id"])
        stream_verification = evaluation_service.verify_streams(
            run["pretraining_job_public_id"], admin_id
        )
        manager = TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
        )
        checkpoint_dir = self.settings.resolved_pretraining_dir / checkpoint["safe_name"]
        try:
            states = manager.load_states(checkpoint_dir)
            checkpoint_verified = True
        except (OSError, ValueError, RuntimeError):
            states = None
            checkpoint_verified = False
        model = BrudForCausalLM(model_config)
        if states is not None:
            model.load_state_dict(states["model"])

        with self.repository.transaction() as connection:
            processor = TokenizerService(
                TokenizerRepository(self.repository.database_path), self.settings
            ).processor_for_version(job["tokenizer_version_public_id"])
        eos_id = model_config.eos_token_id
        splits_to_evaluate = ["test"] if include_test else ["valid"]
        source_split = "test" if include_test else "validation"
        language_metric_rows: list[dict[str, Any]] = []
        languages_with_metrics: set[str] = set()
        overall_loss: float | None = None
        overall_unknown_rate = 0.0

        for target_split in splits_to_evaluate:
            texts_by_language: dict[str, list[str]] = {language: [] for language in LANGUAGES}
            for row in dataset_rows:
                if row["split"] != source_split:
                    continue
                language = row["language"] if row["language"] in texts_by_language else "mixed"
                for field_text in _record_texts(dict(row)):
                    if field_text:
                        texts_by_language[language].append(field_text)
            fixtures = all_fixtures()
            for language in LANGUAGES:
                texts_by_language[language].extend(fixtures.get(language, ()))

            all_texts: list[str] = []
            for language in LANGUAGES:
                texts = texts_by_language[language]
                all_texts.extend(texts)
                result = evaluate_language_texts(
                    model, processor, texts,
                    pad_token_id=model_config.pad_token_id,
                    eos_token_id=eos_id,
                    sequence_length=min(
                        model_config.context_length, self.settings.pretraining_max_sequence_length
                    ),
                    vocabulary_size=model_config.vocabulary_size,
                )
                if result["evaluated_records"] > 0:
                    languages_with_metrics.add(language)
                with self.repository.transaction() as connection:
                    self.repository.record_language_metric(
                        connection, run["id"],
                        {
                            "checkpoint_public_id": checkpoint["public_id"],
                            "split": target_split,
                            "language": language,
                            "evaluated_records": result["evaluated_records"],
                            "evaluated_tokens": result["evaluated_tokens"],
                            "loss": result["loss"],
                            "perplexity": result["perplexity"],
                            "unknown_token_rate": result["unknown_token_rate"],
                            "average_tokens_per_record": result["average_tokens_per_record"],
                            "maximum_tokens_per_record": result["maximum_tokens_per_record"],
                            "long_sequence_rate": result["long_sequence_rate"],
                            "details_json": dumps_json({"fixture_version": FIXTURE_VERSION}),
                        },
                    )
                language_metric_rows.append({"language": language, "split": target_split, **result})

            overall_result = evaluate_language_texts(
                model, processor, all_texts,
                pad_token_id=model_config.pad_token_id,
                eos_token_id=eos_id,
                sequence_length=min(
                    model_config.context_length, self.settings.pretraining_max_sequence_length
                ),
                vocabulary_size=model_config.vocabulary_size,
            )
            with self.repository.transaction() as connection:
                self.repository.record_language_metric(
                    connection, run["id"],
                    {
                        "checkpoint_public_id": checkpoint["public_id"],
                        "split": target_split,
                        "language": "overall",
                        "evaluated_records": overall_result["evaluated_records"],
                        "evaluated_tokens": overall_result["evaluated_tokens"],
                        "loss": overall_result["loss"],
                        "perplexity": overall_result["perplexity"],
                        "unknown_token_rate": overall_result["unknown_token_rate"],
                        "average_tokens_per_record": overall_result["average_tokens_per_record"],
                        "maximum_tokens_per_record": overall_result["maximum_tokens_per_record"],
                        "long_sequence_rate": overall_result["long_sequence_rate"],
                        "details_json": dumps_json({"fixture_version": FIXTURE_VERSION}),
                    },
                )
            if target_split == "valid":
                overall_loss = overall_result["loss"]
            overall_unknown_rate = overall_result["unknown_token_rate"]

        train_validation_gap = None
        if overall_loss is not None and run_summary.get("final_training_loss") is not None:
            train_validation_gap = overall_loss - run_summary["final_training_loss"]

        thresholds = LearningCheckThresholds(
            generalization_max_gap=self.settings.base_training_generalization_max_gap,
            memorization_max_gap=self.settings.base_training_memorization_max_gap,
            tokenizer_max_unknown_rate=self.settings.base_training_tokenizer_max_unknown_rate,
        )
        check_inputs = {
            "initial_training_loss": run_summary.get("initial_training_loss"),
            "final_training_loss": run_summary.get("final_training_loss"),
            "validation_loss": (
                overall_loss if not include_test else run_summary.get("final_validation_loss")
            ),
            "test_loss": overall_loss if include_test else None,
            "non_finite_event_count": run_summary.get("non_finite_event_count", 0),
            "checkpoint_verified": checkpoint_verified,
            "stream_verified": stream_verification.get("verified", False),
            "languages_with_metrics": languages_with_metrics,
            "languages_expected": {
                language for language in LANGUAGES if texts_by_language.get(language)
            },
            "train_validation_gap": train_validation_gap,
            "unknown_token_rate": overall_unknown_rate,
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
                connection, "base_training_run_evaluated", admin_id, run_public_id,
                include_test=include_test,
            )
        return {
            "checkpoint_public_id": checkpoint["public_id"],
            "run_summary": run_summary,
            "language_metrics": language_metric_rows,
            "learning_checks": checks,
            "train_validation_gap": train_validation_gap,
        }

    def language_metrics(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            rows = self.repository.language_metrics(connection, run["id"])
        return {"items": [public_row(row) for row in rows]}

    def learning_checks_for_run(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            rows = self.repository.learning_checks(connection, run["id"])
        return {"items": [public_row(row) for row in rows]}

    # --- comparisons -----------------------------------------------------

    def compare_runs(self, public_id: str, left: str, right: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            left_run = self.repository.run(connection, left)
            right_run = self.repository.run(connection, right)
            if (
                left_run["base_training_experiment_id"] != experiment["id"]
                or right_run["base_training_experiment_id"] != experiment["id"]
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

    def select_candidate(
        self, public_id: str, override_comment: str | None, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            runs = self.repository.runs_for_experiment(connection, experiment["id"])
            completed_statuses = {"completed", "completed_with_warnings"}
            completed = [row for row in runs if row["job_status"] in completed_statuses]
            if not completed:
                selection_id = self.repository.record_candidate_selection(
                    connection, experiment["id"],
                    {
                        "status": "rejected",
                        "generalization_result": "not_assessed",
                        "memorization_warning_count": 0,
                        "rationale_json": dumps_json({"reason": "no completed runs available"}),
                        "created_by_admin_public_id": admin_id,
                    },
                )
                self.repository.update_experiment(
                    connection,
                    experiment["id"],
                    {"latest_candidate_selection_public_id": selection_id},
                )
                return public_row(
                    self.repository.latest_candidate_selection(connection, experiment["id"])
                )
            best_run = min(
                completed,
                key=lambda row: self._best_validation_loss(connection, row["id"]),
            )
            best_run_public_id = best_run["public_id"]

        evaluation = self._evaluate_run(best_run_public_id, admin_id, include_test=True)

        with self.repository.transaction() as connection:
            best_run = self.repository.run(connection, best_run_public_id)
            profile = self.repository.latest_profile(connection, experiment["id"])
            duplicate_rate = profile["duplicate_rate"] if profile else 0.0
            near_duplicate_rate = profile["near_duplicate_rate"] if profile else 0.0

        reliability = TrainingReliabilityRepository(self.repository.database_path)
        evaluation_service = TrainingEvaluationService(
            self.pretraining_repository, reliability, self.settings
        )
        quality = evaluation_service.assess_quality(best_run["pretraining_job_public_id"], admin_id)

        run_summary = evaluation["run_summary"]
        thresholds = LearningCheckThresholds(
            generalization_max_gap=self.settings.base_training_generalization_max_gap,
            memorization_max_gap=self.settings.base_training_memorization_max_gap,
            tokenizer_max_unknown_rate=self.settings.base_training_tokenizer_max_unknown_rate,
        )
        overall_valid_loss = next(
            (
                item["loss"] for item in evaluation["language_metrics"]
                if item.get("language") == "overall"
            ),
            None,
        )
        generalization_result = classify_generalization(
            train_initial=run_summary.get("initial_training_loss"),
            train_final=run_summary.get("final_training_loss"),
            validation_initial=None,
            validation_final=run_summary.get("final_validation_loss") or overall_valid_loss,
            languages_with_improvement=(
                1 if run_summary.get("final_validation_loss") is not None else 0
            ),
        )
        mem_warnings = memorization_warnings(
            train_loss=run_summary.get("final_training_loss"),
            validation_loss=run_summary.get("final_validation_loss"),
            duplicate_rate=duplicate_rate,
            near_duplicate_rate=near_duplicate_rate,
            thresholds=thresholds,
            duplicate_max_ratio=self.settings.base_training_max_duplicate_ratio,
        )

        blocking_codes = {
            "training_loss_improves", "validation_loss_finite", "no_non_finite_gradients",
            "checkpoint_integrity", "dataset_stream_integrity",
        }
        checks = evaluation["learning_checks"]
        has_blocking_failure = any(
            check["status"] == "fail" and check["check_code"] in blocking_codes for check in checks
        )
        has_warning = any(check["status"] != "pass" for check in checks) or mem_warnings

        promoted_model_public_id = None
        if quality["readiness_status"] == "blocked" or has_blocking_failure:
            status = "rejected"
        else:
            if quality["readiness_status"] == "warning" or has_warning:
                status = "selected_with_warnings"
            else:
                status = "selected_base_candidate"
            promotion = PretrainingService(self.pretraining_repository, self.settings).promote(
                evaluation["checkpoint_public_id"], admin_id, override_comment
            )
            promoted_model_public_id = promotion["promoted_model_version_public_id"]

        with self.repository.transaction() as connection:
            selection_id = self.repository.record_candidate_selection(
                connection, experiment["id"],
                {
                    "selected_run_id": best_run["id"],
                    "selected_checkpoint_public_id": evaluation["checkpoint_public_id"],
                    "status": status,
                    "generalization_result": generalization_result,
                    "memorization_warning_count": len(mem_warnings),
                    "rationale_json": dumps_json(
                        {
                            "quality_readiness_status": quality["readiness_status"],
                            "memorization_warnings": mem_warnings,
                            "promoted_model_public_id": promoted_model_public_id,
                            "override_comment": override_comment,
                        }
                    ),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self.repository.update_experiment(
                connection, experiment["id"],
                {"latest_candidate_selection_public_id": selection_id, "status": "completed"},
            )
            self._audit(
                connection, "base_training_candidate_selected", admin_id, public_id, status=status
            )
            return public_row(
                self.repository.latest_candidate_selection(connection, experiment["id"])
            )

    def candidate(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            experiment = self.repository.experiment(connection, public_id)
            row = self.repository.latest_candidate_selection(connection, experiment["id"])
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
            candidate_row = self.repository.latest_candidate_selection(connection, experiment["id"])
            core_model_config = connection.execute(
                """SELECT c.config_checksum_sha256 FROM core_model_configs c
                JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
                (experiment["core_model_version_id"],),
            ).fetchone() if experiment["core_model_version_id"] else None
            dataset_checksum = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE id=?",
                (experiment["dataset_version_id"],),
            ).fetchone()[0]
            tokenizer_checksum = None
            if experiment["tokenizer_version_id"]:
                tokenizer_checksum = connection.execute(
                    "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE id=?",
                    (experiment["tokenizer_version_id"],),
                ).fetchone()[0]
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
                        "job_public_id": run["pretraining_job_public_id"],
                        "job_status": run["job_status"],
                        "config_diff": loads_json(run["config_diff_json"]),
                        "config_checksum_sha256": job["config_checksum_sha256"] if job else None,
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
                "core_model_config_checksum_sha256": (
                    core_model_config["config_checksum_sha256"] if core_model_config else None
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
            self._audit(connection, "base_training_manifest_generated", admin_id, public_id)
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

    def _resolve_tokenizer(self, connection, experiment):
        if experiment["tokenizer_version_id"]:
            return connection.execute(
                "SELECT * FROM tokenizer_versions WHERE id=?", (experiment["tokenizer_version_id"],)
            ).fetchone()
        return connection.execute(
            """SELECT t.* FROM tokenizer_assignments a
            JOIN tokenizer_versions t ON t.id=a.tokenizer_version_id
            WHERE a.assignment_key='default' AND a.enabled=1"""
        ).fetchone()

    def _processor_for_experiment(self, connection, experiment):
        tokenizer_row = self._resolve_tokenizer(connection, experiment)
        if tokenizer_row is None:
            return None, -1
        service = TokenizerService(
            TokenizerRepository(self.repository.database_path), self.settings
        )
        return service.processor_for_version(tokenizer_row["public_id"]), 3

    def _model_config(self, connection, job) -> BrudModelConfig:
        row = connection.execute(
            """SELECT c.* FROM core_model_configs c
            JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
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

    def _best_validation_loss(self, connection, run_id: int) -> float:
        row = connection.execute(
            """SELECT j.latest_validation_loss FROM base_training_experiment_runs r
            JOIN pretraining_jobs j ON j.id=r.pretraining_job_id WHERE r.id=?""",
            (run_id,),
        ).fetchone()
        value = row["latest_validation_loss"] if row else None
        return value if value is not None else float("inf")

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
            profile and profile["test_count"] >= self.settings.base_training_min_test_records
        )
        limitations: dict[str, Any] = {
            "data_sufficiency_status": sufficiency,
            "test_evaluation_reliable": test_reliable,
        }
        if not test_reliable:
            limitations["test_evaluation_notice"] = "TEST_EVALUATION_NOT_RELIABLE"
        if sufficiency != "sufficient":
            limitations["data_sufficiency_notice"] = (
                "dataset is below the recommended 500-record minimum; this experiment is a "
                "limited-scale trial, not a representative-scale result"
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
                event,
                "admin",
                "{}",
                str(uuid4()),
                event,
                "admin",
                admin_id,
                "base_training",
                resource_id,
                "success",
                dumps_json(metadata),
            ),
        )


def _record_texts(row: dict[str, Any]) -> list[str]:
    return [text for text in record_text_fields(row) if text]
