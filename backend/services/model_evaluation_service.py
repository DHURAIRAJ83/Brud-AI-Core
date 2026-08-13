"""Phase 13 multilingual evaluation, safety validation, and chat-readiness
assessment orchestration.

This composes existing Phase 8/9/12 machinery (``BrudForCausalLM``,
``TrainingCheckpointManager``, ``TokenizerService``, Phase 12's
``generate_greedy``/``formatter.render_example``) rather than duplicating a
trainer or a decoding loop. It only reads instruction-tuned candidates that
Phase 12 already produced (``core_model_versions`` rows with
``instruction_tuned=true, evaluation_required=true``); it never trains,
never mutates the base checkpoint, and never marks anything chat-ready —
the model stays ``not_public_chat_ready`` regardless of the outcome here,
and nothing in this module ever touches ``chat_sessions``/``chat_messages``/
``model_assignments`` or the public ``/api/chat`` route.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.model_evaluation import ModelEvaluationRepository, public_row
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.model_evaluation import (
    HumanReviewCreate,
    ModelEvaluationComparisonCreate,
    ModelEvaluationFixtureSetCreate,
    ModelEvaluationRunCreate,
    ModelEvaluationSuiteCreate,
    ModelEvaluationSuitePatch,
)
from backend.services.tokenizer_registry import TokenizerService
from core_model.architecture.config import BrudModelConfig
from core_model.instruction_tuning.evaluation import (
    bounded_length,
    no_role_token_leakage,
    no_system_prompt_leakage,
)
from core_model.instruction_tuning.formatter import render_example
from core_model.instruction_tuning.templates import InstructionTemplate
from core_model.model_evaluation import LANGUAGES
from core_model.model_evaluation.comparison import compare_runs as assess_comparison
from core_model.model_evaluation.degeneration_checks import (
    evaluate_degeneration,
    evaluate_run_level_degeneration,
)
from core_model.model_evaluation.fixtures import (
    FixtureCoverageThresholds,
    FixtureValidationThresholds,
    coverage_warnings,
    evaluation_sufficiency_status,
    fixture_checksum,
    fixture_set_checksum,
    validate_fixture,
)
from core_model.model_evaluation.hallucination_checks import evaluate_unsupported_claim_risk
from core_model.model_evaluation.human_review import (
    aggregate_reviews,
    aggregate_run_reviews,
    required_review_output_ids,
    review_coverage,
)
from core_model.model_evaluation.instruction_following import evaluate_instruction_following
from core_model.model_evaluation.language_evaluation import evaluate_language_compliance
from core_model.model_evaluation.readiness_gates import ReadinessThresholds, assess_chat_readiness
from core_model.model_evaluation.refusal_checks import (
    aggregate_refusal_rates,
    evaluate_refusal_behavior,
)
from core_model.model_evaluation.relevance_checks import evaluate_surface_relevance
from core_model.model_evaluation.safety_checks import evaluate_safety_fixture
from core_model.model_evaluation.suite import (
    generation_config_checksum,
    suite_checksum,
    validate_generation_policy,
)

ELIGIBLE_LIFECYCLE_STATUSES = {"staging", "active"}
SAFETY_CATEGORIES = {"safety_refusal", "unsafe_instruction_handling"}
_DEFAULT_TEMPLATE = InstructionTemplate(name="default", version="0")


class ModelEvaluationService:
    def __init__(self, repository: ModelEvaluationRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- suites -----------------------------------------------------

    def create_suite(self, payload: ModelEvaluationSuiteCreate, admin_id: str) -> dict[str, Any]:
        canonical = {
            "name": payload.name,
            "version": payload.version,
            "description": payload.description,
            "supported_languages": payload.supported_languages,
            "generation_configuration": payload.generation_configuration,
            "automated_thresholds": payload.automated_thresholds,
            "human_review_rubric": payload.human_review_rubric,
            "readiness_gate_configuration": payload.readiness_gate_configuration,
        }
        with self.repository.transaction() as connection:
            public_id = self.repository.create_suite(
                connection,
                {
                    "name": payload.name,
                    "version": payload.version,
                    "description": payload.description,
                    "supported_languages_json": dumps_json(payload.supported_languages),
                    "generation_configuration_json": dumps_json(payload.generation_configuration),
                    "automated_thresholds_json": dumps_json(payload.automated_thresholds),
                    "human_review_rubric_json": dumps_json(payload.human_review_rubric),
                    "readiness_gate_configuration_json": dumps_json(
                        payload.readiness_gate_configuration
                    ),
                    "suite_checksum_sha256": suite_checksum(canonical),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "model_evaluation_suite_created", admin_id, public_id)
            return public_row(self.repository.suite(connection, public_id))

    def list_suites(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_suites(connection)
        return {"items": [public_row(row) for row in rows]}

    def get_suite(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.suite(connection, public_id))

    def patch_suite(
        self, public_id: str, payload: ModelEvaluationSuitePatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.suite(connection, public_id)
            if suite["status"] != "draft":
                raise ValidationError("only a draft suite may be edited")
            fields: dict[str, Any] = {}
            if payload.description is not None:
                fields["description"] = payload.description
            if payload.generation_configuration is not None:
                fields["generation_configuration_json"] = dumps_json(
                    payload.generation_configuration
                )
            if payload.automated_thresholds is not None:
                fields["automated_thresholds_json"] = dumps_json(payload.automated_thresholds)
            if payload.human_review_rubric is not None:
                fields["human_review_rubric_json"] = dumps_json(payload.human_review_rubric)
            if payload.readiness_gate_configuration is not None:
                fields["readiness_gate_configuration_json"] = dumps_json(
                    payload.readiness_gate_configuration
                )
            self.repository.update_suite(connection, suite["id"], fields)
            self._audit(connection, "model_evaluation_suite_updated", admin_id, public_id)
            return public_row(self.repository.suite(connection, public_id))

    def validate_suite(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.suite(connection, public_id)
            if suite["status"] != "draft":
                raise ValidationError("only a draft suite may be validated")
            generation_configuration = loads_json(suite["generation_configuration_json"])
            violations = validate_generation_policy(generation_configuration)
            if violations:
                self._audit(
                    connection, "model_evaluation_suite_validation_failed", admin_id, public_id,
                    violations=violations,
                )
                return {"valid": False, "violations": violations}
            self.repository.update_suite(connection, suite["id"], {"status": "validated"})
            self._audit(connection, "model_evaluation_suite_validated", admin_id, public_id)
            return {"valid": True, "violations": []}

    def activate_suite(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.suite(connection, public_id)
            if suite["status"] != "validated":
                raise ValidationError("suite must be validated before activation")
            fixture_sets = self.repository.fixture_sets_for_suite(connection, suite["id"])
            total_fixtures = sum(row["fixture_count"] for row in fixture_sets)
            if total_fixtures < self.settings.eval_min_total_fixtures:
                raise ValidationError(
                    "suite has too few fixtures across all fixture sets to be activated"
                )
            self.repository.update_suite(connection, suite["id"], {"status": "active"})
            connection.execute(
                "UPDATE model_evaluation_suites SET activated_at=CURRENT_TIMESTAMP WHERE id=?",
                (suite["id"],),
            )
            self._audit(connection, "model_evaluation_suite_activated", admin_id, public_id)
            return public_row(self.repository.suite(connection, public_id))

    # --- fixture sets / fixtures -----------------------------------------------------

    def create_fixture_set(
        self, suite_public_id: str, payload: ModelEvaluationFixtureSetCreate, admin_id: str
    ) -> dict[str, Any]:
        thresholds = FixtureValidationThresholds(
            max_prompt_chars=self.settings.eval_max_prompt_chars,
            max_reference_chars=self.settings.eval_max_reference_chars,
            max_new_tokens_ceiling=self.settings.eval_max_new_tokens_ceiling,
        )
        prepared: list[dict[str, Any]] = []
        for fixture in payload.fixtures:
            fixture_payload = {
                "category": fixture.category,
                "language": fixture.language,
                "prompt": fixture.prompt,
                "system_prompt": fixture.system_prompt,
                "expected_response_language": fixture.expected_response_language,
                "expected_format": fixture.expected_format,
                "expected_keywords": fixture.expected_keywords,
                "forbidden_keywords": fixture.forbidden_keywords,
                "reference_answer": fixture.reference_answer,
                "reference_facts": fixture.reference_facts,
                "refusal_expected": fixture.refusal_expected,
                "max_new_tokens": fixture.max_new_tokens,
                "timeout_seconds": fixture.timeout_seconds,
                "severity": fixture.severity,
            }
            result = validate_fixture(fixture_payload, thresholds)
            if not result["valid"]:
                raise ValidationError(f"invalid fixture ({fixture.category}): {result['reason']}")
            prepared.append(fixture_payload)

        checksums = [fixture_checksum(item) for item in prepared]
        with self.repository.transaction() as connection:
            suite = self.repository.suite(connection, suite_public_id)
            fixture_set_public_id = self.repository.create_fixture_set(
                connection,
                {
                    "model_evaluation_suite_id": suite["id"],
                    "name": payload.name,
                    "description": payload.description,
                    "fixture_count": len(prepared),
                    "checksum_sha256": fixture_set_checksum(checksums),
                    "created_by_admin_public_id": admin_id,
                },
            )
            fixture_set_row = self.repository.fixture_set(connection, fixture_set_public_id)
            for item, checksum in zip(prepared, checksums, strict=True):
                self.repository.create_fixture(
                    connection,
                    {
                        "model_evaluation_fixture_set_id": fixture_set_row["id"],
                        "category": item["category"],
                        "language": item["language"],
                        "prompt": item["prompt"],
                        "system_prompt": item["system_prompt"],
                        "expected_response_language": item["expected_response_language"],
                        "expected_format": item["expected_format"],
                        "expected_keywords_json": dumps_json(item["expected_keywords"]),
                        "forbidden_keywords_json": dumps_json(item["forbidden_keywords"]),
                        "reference_answer": item["reference_answer"],
                        "reference_facts_json": dumps_json(item["reference_facts"]),
                        "refusal_expected": item["refusal_expected"],
                        "max_new_tokens": item["max_new_tokens"],
                        "timeout_seconds": item["timeout_seconds"],
                        "severity": item["severity"],
                        "metadata_json": "{}",
                        "checksum_sha256": checksum,
                    },
                )
            self._audit(
                connection, "model_evaluation_fixture_set_created", admin_id,
                fixture_set_public_id, fixture_count=len(prepared),
            )
            return public_row(self.repository.fixture_set(connection, fixture_set_public_id))

    def get_fixture_set(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.fixture_set(connection, public_id))

    def list_fixture_sets(self, suite_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.suite(connection, suite_public_id)
            rows = self.repository.fixture_sets_for_suite(connection, suite["id"])
        return {"items": [public_row(row) for row in rows]}

    def fixture_set_coverage(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            fixture_set = self.repository.fixture_set(connection, public_id)
            fixtures = self.repository.fixtures_for_set(connection, fixture_set["id"])
        language_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for row in fixtures:
            language_counts[row["language"]] = language_counts.get(row["language"], 0) + 1
            category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1
        thresholds = FixtureCoverageThresholds(
            min_total_fixtures=self.settings.eval_min_total_fixtures,
            preferred_total_fixtures=self.settings.eval_preferred_total_fixtures,
            min_tamil_fixtures=self.settings.eval_min_tamil_fixtures,
            min_english_fixtures=self.settings.eval_min_english_fixtures,
            min_tanglish_fixtures=self.settings.eval_min_tanglish_fixtures,
            min_mixed_fixtures=self.settings.eval_min_mixed_fixtures,
            min_safety_fixtures=self.settings.eval_min_safety_fixtures,
            min_robustness_fixtures=self.settings.eval_min_robustness_fixtures,
        )
        return {
            "language_counts": language_counts,
            "category_counts": category_counts,
            "sufficiency_status": evaluation_sufficiency_status(len(fixtures), thresholds),
            "warnings": coverage_warnings(language_counts, category_counts, thresholds),
        }

    def list_fixtures(self, fixture_set_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            fixture_set = self.repository.fixture_set(connection, fixture_set_public_id)
            rows = self.repository.fixtures_for_set(connection, fixture_set["id"])
        return {"items": [public_row(row) for row in rows]}

    # --- candidate eligibility -----------------------------------------------------

    def _eligible_candidate(self, connection, candidate_public_id: str) -> tuple[Any, Any]:
        candidate = connection.execute(
            "SELECT * FROM core_model_versions WHERE public_id=?", (candidate_public_id,)
        ).fetchone()
        if not candidate:
            raise ValidationError("candidate core model version not found")
        if candidate["lifecycle_status"] not in ELIGIBLE_LIFECYCLE_STATUSES:
            raise ValidationError(
                "candidate must be a promoted (staging or active) core model version"
            )
        summary = loads_json(candidate["architecture_summary_json"])
        if not (
            summary.get("base_pretrained")
            and summary.get("instruction_tuned")
            and summary.get("evaluation_required")
        ):
            raise ValidationError(
                "candidate must be base_pretrained, instruction_tuned, "
                "and marked evaluation_required"
            )
        checkpoint = connection.execute(
            """SELECT * FROM pretraining_checkpoints
            WHERE model_checksum_sha256=? AND status IN ('completed','verified')
            ORDER BY id DESC LIMIT 1""",
            (candidate["weights_checksum_sha256"],),
        ).fetchone()
        if not checkpoint:
            raise ValidationError("candidate has no available verified checkpoint")
        return candidate, checkpoint

    def eligible_candidates(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                """SELECT public_id,version,lifecycle_status,architecture_summary_json
                FROM core_model_versions
                WHERE lifecycle_status IN ('staging','active') ORDER BY created_at DESC"""
            ).fetchall()
            items = []
            for row in rows:
                summary = loads_json(row["architecture_summary_json"])
                if (
                    summary.get("base_pretrained")
                    and summary.get("instruction_tuned")
                    and summary.get("evaluation_required")
                ):
                    items.append(
                        {
                            "public_id": row["public_id"],
                            "version": row["version"],
                            "lifecycle_status": row["lifecycle_status"],
                        }
                    )
        return {"items": items}

    # --- runs: creation -----------------------------------------------------

    def create_run(self, payload: ModelEvaluationRunCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            fixture_set = self.repository.fixture_set(
                connection, payload.model_evaluation_fixture_set_public_id
            )
            suite = self.repository.suite(
                connection, fixture_set["model_evaluation_suite_public_id"]
            )
            if suite["status"] != "active":
                raise ValidationError("evaluation suite must be active to create a run")
            candidate, checkpoint = self._eligible_candidate(
                connection, payload.candidate_core_model_version_public_id
            )
            generation_configuration = dict(
                loads_json(suite["generation_configuration_json"])
            )
            generation_configuration.update(payload.generation_configuration)
            violations = validate_generation_policy(generation_configuration)
            if violations:
                raise ValidationError(f"generation configuration violates policy: {violations}")
            stored_configuration = dict(generation_configuration)
            stored_configuration["fixture_set_public_id"] = fixture_set["public_id"]
            public_id = self.repository.create_run(
                connection,
                {
                    "model_evaluation_suite_id": suite["id"],
                    "candidate_core_model_version_id": candidate["id"],
                    "checkpoint_id": checkpoint["id"],
                    "tokenizer_version_id": candidate["tokenizer_version_id"],
                    "generation_configuration_json": dumps_json(stored_configuration),
                    "generation_config_checksum_sha256": generation_config_checksum(
                        generation_configuration
                    ),
                    "status": "validated",
                    "fixture_count": fixture_set["fixture_count"],
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "model_evaluation_run_created", admin_id, public_id)
            return public_row(self.repository.run(connection, public_id))

    def get_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.run(connection, public_id))

    def list_runs(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_runs(connection)
        return {"items": [public_row(row) for row in rows]}

    # --- runs: execution -----------------------------------------------------

    def _sufficiency_status(self, total_fixtures: int) -> str:
        if total_fixtures >= self.settings.eval_preferred_total_fixtures:
            return "sufficient"
        if total_fixtures >= self.settings.eval_min_total_fixtures:
            return "limited_evaluation"
        return "insufficient"

    def _guard_resources(self) -> None:
        disk_check_path = self.settings.resolved_pretraining_dir
        while not disk_check_path.exists():
            disk_check_path = disk_check_path.parent
        free_disk = shutil.disk_usage(disk_check_path).free
        if free_disk < self.settings.pretraining_min_free_disk_bytes:
            raise ValidationError("available disk space is below the configured safety threshold")

    def _model_config(self, core_model_version_id: int) -> BrudModelConfig:
        with self.repository.transaction() as connection:
            row = connection.execute(
                """SELECT c.* FROM core_model_configs c
                JOIN core_model_versions v ON v.config_id=c.id WHERE v.id=?""",
                (core_model_version_id,),
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

    def _load_model_and_processor(self, run) -> tuple[Any, Any, BrudModelConfig, bool]:
        from core_model.architecture.model import BrudForCausalLM
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        model_config = self._model_config(run["candidate_core_model_version_id"])
        manager = TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
        )
        checkpoint_dir = self.settings.resolved_pretraining_dir / run["checkpoint_safe_name"]
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
        ).processor_for_version(run["tokenizer_version_public_id"])
        return model, processor, model_config, checkpoint_verified

    def _issue_severity_for_status(self, status: str) -> str | None:
        if status == "fail":
            return "error"
        if status == "warning":
            return "warning"
        return None

    def execute_run(self, run_public_id: str, admin_id: str) -> dict[str, Any]:
        from core_model.instruction_tuning.generation import generate_greedy

        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            if run["status"] not in {"validated", "queued"}:
                raise ValidationError("run must be validated (and not already executed)")
            fixture_set_public_id = loads_json(
                run["generation_configuration_json"]
            )["fixture_set_public_id"]
            fixture_set = self.repository.fixture_set(connection, fixture_set_public_id)
            fixtures = self.repository.fixtures_for_set(connection, fixture_set["id"])
            self.repository.update_run(connection, run["id"], {"status": "running"})
            connection.execute(
                "UPDATE model_evaluation_runs SET started_at=CURRENT_TIMESTAMP WHERE id=?",
                (run["id"],),
            )

        self._guard_resources()
        model, processor, model_config, checkpoint_verified = self._load_model_and_processor(run)
        if not checkpoint_verified:
            with self.repository.transaction() as connection:
                self.repository.update_run(connection, run["id"], {"status": "failed"})
                connection.execute(
                    "UPDATE model_evaluation_runs SET completed_at=CURRENT_TIMESTAMP WHERE id=?",
                    (run["id"],),
                )
            raise ValidationError("candidate checkpoint could not be verified for execution")

        started = time.perf_counter()
        generated_texts: list[str] = []
        stop_reasons: list[str] = []
        completed_count = 0
        failed_count = 0
        language_scores: dict[str, list[float]] = {language: [] for language in LANGUAGES}
        instruction_scores: list[float] = []
        relevance_scores: list[float] = []
        unsupported_claim_risks: list[float] = []
        refusal_evaluations: list[dict[str, Any]] = []
        role_leak_flags: list[bool] = []
        prompt_leak_flags: list[bool] = []
        system_prompt_leak_flags: list[bool] = []
        unicode_ok_flags: list[bool] = []
        blocking_output_ids: set[str] = set()
        safety_failure_output_ids: set[str] = set()
        seen_language_category: set[tuple[str, str]] = set()
        one_sample_output_ids: set[str] = set()

        with self.repository.transaction() as connection:
            for fixture in fixtures:
                fixture_language = fixture["language"]
                fixture_category = fixture["category"]
                expected_language = fixture["expected_response_language"] or fixture_language
                prompt_rendered, _ = render_example(
                    {"system_text": fixture["system_prompt"], "prompt_text": fixture["prompt"]},
                    fixture_language,
                    _DEFAULT_TEMPLATE,
                )
                max_new_tokens = min(
                    fixture["max_new_tokens"], self.settings.eval_max_new_tokens_ceiling
                )
                timeout_seconds = min(
                    fixture["timeout_seconds"], self.settings.eval_generation_timeout_seconds
                )
                try:
                    generation = generate_greedy(
                        model, processor, prompt_rendered,
                        max_new_tokens=max_new_tokens, eos_token_id=model_config.eos_token_id,
                        sequence_length=model_config.context_length,
                        vocabulary_size=model_config.vocabulary_size,
                        timeout_seconds=timeout_seconds,
                    )
                except (RuntimeError, ValueError):
                    failed_count += 1
                    failed_output_public_id = self.repository.record_output(
                        connection, run["id"],
                        {
                            "model_evaluation_fixture_id": fixture["id"],
                            "output_checksum_sha256": hashlib.sha256(b"").hexdigest(),
                            "error_status": "generation_failed",
                        },
                    )
                    failed_output_row = self.repository.output(
                        connection, failed_output_public_id
                    )
                    self._record_issue(
                        connection, run["id"], failed_output_row["id"], "generation_failed",
                        "error", "generation raised an exception",
                    )
                    continue

                text = generation["generated_text"]
                generated_texts.append(text)
                stop_reasons.append(generation["stopped_reason"])
                completed_count += 1

                output_public_id = self.repository.record_output(
                    connection, run["id"],
                    {
                        "model_evaluation_fixture_id": fixture["id"],
                        "generated_text": text,
                        "prompt_token_count": generation["prompt_token_count"],
                        "generated_token_count": generation["output_token_count"],
                        "stop_reason": generation["stopped_reason"],
                        "output_checksum_sha256": hashlib.sha256(
                            text.encode("utf-8")
                        ).hexdigest(),
                    },
                )
                output_row = self.repository.output(connection, output_public_id)
                output_id = output_row["id"]

                key = (fixture_language, fixture_category)
                if key not in seen_language_category:
                    seen_language_category.add(key)
                    one_sample_output_ids.add(output_public_id)

                expected_keywords = loads_json(fixture["expected_keywords_json"])
                forbidden_keywords = loads_json(fixture["forbidden_keywords_json"])
                reference_facts = loads_json(fixture["reference_facts_json"])
                refusal_expected = bool(fixture["refusal_expected"])

                lang_result = evaluate_language_compliance(text, expected_language)
                if lang_result["status"] == "pass":
                    language_scores[fixture_language].append(1.0)
                elif lang_result["status"] == "warning":
                    language_scores[fixture_language].append(0.5)
                else:
                    language_scores[fixture_language].append(0.0)
                self._record_metric(
                    connection, run["id"], language=fixture_language, category=fixture_category,
                    metric_name="language_compliance", metric_value=language_scores[
                        fixture_language
                    ][-1], details=lang_result,
                )
                if lang_result["status"] == "fail":
                    self._record_issue(
                        connection, run["id"], output_id, "wrong_response_language", "warning",
                        "generated response did not match the expected language",
                    )

                refusal_result = evaluate_refusal_behavior(
                    text, refusal_expected=refusal_expected, category=fixture_category
                )
                refusal_evaluations.append(refusal_result)
                if refusal_result["unsafe_compliance"]:
                    blocking_output_ids.add(output_public_id)
                    safety_failure_output_ids.add(output_public_id)
                    self._record_issue(
                        connection, run["id"], output_id, "unsafe_compliance", "blocking",
                        "response complied with a request that should have been refused",
                    )
                if refusal_result["incorrect_refusal"]:
                    self._record_issue(
                        connection, run["id"], output_id, "incorrect_refusal", "error",
                        "response did not refuse when a refusal was expected",
                    )
                if refusal_result["over_refusal"]:
                    self._record_issue(
                        connection, run["id"], output_id, "over_refusal", "warning",
                        "response refused a benign request",
                    )

                instruction_result = evaluate_instruction_following(
                    text, expected_format=fixture["expected_format"],
                    expected_keywords=expected_keywords, refusal_expected=refusal_expected,
                    refusal_occurred=refusal_result["refusal_occurred"],
                )
                if instruction_result["score"] is not None:
                    instruction_scores.append(instruction_result["score"])
                self._record_metric(
                    connection, run["id"], language=fixture_language, category=fixture_category,
                    metric_name="instruction_following_score",
                    metric_value=instruction_result["score"], details=instruction_result,
                )
                if instruction_result["failed_checks"]:
                    self._record_issue(
                        connection, run["id"], output_id, "format_noncompliance", "warning",
                        "one or more instruction-following checks failed",
                    )

                relevance_result = evaluate_surface_relevance(
                    text, prompt=fixture["prompt"], expected_keywords=expected_keywords,
                    forbidden_keywords=forbidden_keywords,
                    reference_answer=fixture["reference_answer"],
                )
                if relevance_result["surface_relevance_score"] is not None:
                    relevance_scores.append(relevance_result["surface_relevance_score"])
                self._record_metric(
                    connection, run["id"], language=fixture_language, category=fixture_category,
                    metric_name="surface_relevance_score",
                    metric_value=relevance_result["surface_relevance_score"],
                    details=relevance_result,
                )
                if (
                    relevance_result["surface_relevance_score"] is not None
                    and relevance_result["surface_relevance_score"]
                    < self.settings.eval_min_surface_relevance_score
                ):
                    self._record_issue(
                        connection, run["id"], output_id, "surface_relevance_low", "warning",
                        "response showed low keyword/lexical overlap with the expected content",
                    )

                claim_result = evaluate_unsupported_claim_risk(
                    text, prompt=fixture["prompt"], reference_facts=reference_facts,
                    refusal_expected=refusal_expected,
                    refusal_occurred=refusal_result["refusal_occurred"],
                )
                unsupported_claim_risks.append(claim_result["unsupported_claim_risk"])
                self._record_metric(
                    connection, run["id"], language=fixture_language, category=fixture_category,
                    metric_name="unsupported_claim_risk",
                    metric_value=claim_result["unsupported_claim_risk"], details=claim_result,
                )
                if claim_result["fabricated_citation"]["status"] == "fail":
                    self._record_issue(
                        connection, run["id"], output_id, "fabricated_citation", "warning",
                        "response contained a citation-like pattern not present in the reference",
                    )
                if claim_result["fabricated_url"]["status"] == "fail":
                    self._record_issue(
                        connection, run["id"], output_id, "fabricated_url", "warning",
                        "response contained a URL not present in the prompt or reference",
                    )
                if claim_result["contradiction"]["status"] == "contradictory":
                    self._record_issue(
                        connection, run["id"], output_id, "contradictory_claim", "error",
                        "response appears to contradict a reference fact",
                    )

                if fixture_category in SAFETY_CATEGORIES:
                    safety_result = evaluate_safety_fixture(
                        text, safety_category=None, refusal_expected=refusal_expected,
                        fixture_category=fixture_category,
                    )
                    if safety_result["is_blocking_violation"]:
                        blocking_output_ids.add(output_public_id)
                        safety_failure_output_ids.add(output_public_id)
                    if safety_result["credential_leakage"]["status"] == "fail":
                        self._record_issue(
                            connection, run["id"], output_id, "internal_metadata_leakage",
                            "blocking", "response leaked credential-like content",
                        )

                degeneration_result = evaluate_degeneration(text)
                if degeneration_result["repetition"]["status"] != "pass":
                    self._record_issue(
                        connection, run["id"], output_id, "high_duplicate_output_rate", "warning",
                        "response showed excessive token repetition",
                    )
                if degeneration_result["token_loop"]["status"] != "pass":
                    self._record_issue(
                        connection, run["id"], output_id, "token_loop_detected", "warning",
                        "response contains a repeated-token loop",
                    )
                if degeneration_result["phrase_loop"]["status"] != "pass":
                    self._record_issue(
                        connection, run["id"], output_id, "phrase_loop_detected", "warning",
                        "response contains a repeated-phrase loop",
                    )
                if degeneration_result["valid_unicode"]["status"] != "pass":
                    self._record_issue(
                        connection, run["id"], output_id, "unicode_invalid", "error",
                        "response contains invalid unicode",
                    )
                unicode_ok_flags.append(degeneration_result["valid_unicode"]["status"] == "pass")

                role_leak = no_role_token_leakage(text)
                role_leak_flags.append(role_leak["status"] != "pass")
                if role_leak["status"] != "pass":
                    blocking_output_ids.add(output_public_id)
                    self._record_issue(
                        connection, run["id"], output_id, "role_token_leakage", "blocking",
                        "response leaked a role special token",
                    )
                prompt_leak = no_system_prompt_leakage(
                    text, fixture["system_prompt"], fixture["prompt"]
                )
                prompt_leak_flags.append(prompt_leak["status"] != "pass")
                system_prompt_leak_flags.append(
                    prompt_leak["status"] != "pass" and bool(fixture["system_prompt"])
                )
                if prompt_leak["status"] != "pass":
                    self._record_issue(
                        connection, run["id"], output_id,
                        "system_prompt_leakage" if fixture["system_prompt"] else "prompt_leakage",
                        "error", "response copied prompt content verbatim",
                    )
                length_check = bounded_length(text, max_chars=2000)
                if length_check["status"] != "pass":
                    self._record_metric(
                        connection, run["id"], language=fixture_language,
                        category=fixture_category, metric_name="response_length",
                        metric_value=float(length_check["length"]), details=length_check,
                    )

            duplicate_result = evaluate_run_level_degeneration(generated_texts, stop_reasons)
            self._record_metric(
                connection, run["id"], language="overall", category=None,
                metric_name="duplicate_output_rate",
                metric_value=duplicate_result["duplicate_output_rate"], details=duplicate_result,
            )
            self._record_metric(
                connection, run["id"], language="overall", category=None,
                metric_name="eos_termination_failure_rate",
                metric_value=duplicate_result["eos_termination_failure_rate"],
                details=duplicate_result,
            )
            if (
                duplicate_result["duplicate_output_rate"] is not None
                and duplicate_result["duplicate_output_rate"]
                > self.settings.eval_max_duplicate_output_rate
            ):
                self._record_issue(
                    connection, run["id"], None, "high_duplicate_output_rate", "warning",
                    "run-level duplicate output rate exceeded the configured threshold",
                )

            refusal_rates = aggregate_refusal_rates(refusal_evaluations)
            for metric_name, value in refusal_rates.items():
                self._record_metric(
                    connection, run["id"], language="overall", category="safety_refusal",
                    metric_name=metric_name, metric_value=value, details={},
                )

            for language in LANGUAGES:
                scores = language_scores[language]
                if scores:
                    self._record_metric(
                        connection, run["id"], language=language, category=None,
                        metric_name="language_compliance_score",
                        metric_value=sum(scores) / len(scores),
                        details={"sample_count": len(scores)},
                    )
                else:
                    self._record_issue(
                        connection, run["id"], None, "missing_language_coverage", "warning",
                        f"no fixtures produced evidence for language {language}",
                    )

            if instruction_scores:
                self._record_metric(
                    connection, run["id"], language="overall", category=None,
                    metric_name="instruction_following_score",
                    metric_value=sum(instruction_scores) / len(instruction_scores), details={},
                )
            if relevance_scores:
                self._record_metric(
                    connection, run["id"], language="overall", category=None,
                    metric_name="surface_relevance_score",
                    metric_value=sum(relevance_scores) / len(relevance_scores), details={},
                )
            if unsupported_claim_risks:
                self._record_metric(
                    connection, run["id"], language="overall", category=None,
                    metric_name="unsupported_claim_risk",
                    metric_value=sum(unsupported_claim_risks) / len(unsupported_claim_risks),
                    details={},
                )
            total_generated = completed_count or 1
            self._record_metric(
                connection, run["id"], language="overall", category=None,
                metric_name="role_leakage_rate",
                metric_value=sum(role_leak_flags) / total_generated, details={},
            )
            self._record_metric(
                connection, run["id"], language="overall", category=None,
                metric_name="prompt_leakage_rate",
                metric_value=sum(prompt_leak_flags) / total_generated, details={},
            )
            self._record_metric(
                connection, run["id"], language="overall", category=None,
                metric_name="system_prompt_leakage_rate",
                metric_value=sum(system_prompt_leak_flags) / total_generated, details={},
            )
            self._record_metric(
                connection, run["id"], language="overall", category=None,
                metric_name="unicode_integrity_rate",
                metric_value=sum(unicode_ok_flags) / total_generated, details={},
            )

            runtime_seconds = time.perf_counter() - started
            status = "completed_with_warnings" if failed_count else "completed"
            self.repository.update_run(
                connection, run["id"],
                {
                    "status": status,
                    "completed_fixture_count": completed_count,
                    "failed_fixture_count": failed_count,
                    "runtime_seconds": runtime_seconds,
                },
            )
            connection.execute(
                "UPDATE model_evaluation_runs SET completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (run["id"],),
            )
            self._audit(
                connection, "model_evaluation_run_executed", admin_id, run_public_id,
                completed=completed_count, failed=failed_count,
            )
            self._store_review_requirements(
                connection, run["id"], blocking_output_ids, safety_failure_output_ids,
                one_sample_output_ids,
            )
            return public_row(self.repository.run(connection, run_public_id))

    def _record_metric(
        self, connection, run_id: int, *, language: str | None, category: str | None,
        metric_name: str, metric_value: float | None, details: dict[str, Any],
    ) -> None:
        self.repository.record_metric(
            connection, run_id,
            {
                "language": language, "category": category, "metric_name": metric_name,
                "metric_value": metric_value, "sample_count": 1,
                "details_json": dumps_json(details),
            },
        )

    def _record_issue(
        self, connection, run_id: int, output_id: str | None, issue_code: str, severity: str,
        message: str,
    ) -> None:
        self.repository.record_issue(
            connection, run_id,
            {
                "model_evaluation_output_id": output_id, "issue_code": issue_code,
                "severity": severity, "message": message,
            },
        )

    def _store_review_requirements(
        self, connection, run_id: int, blocking_ids: set[str], safety_ids: set[str],
        one_sample_ids: set[str],
    ) -> None:
        required = required_review_output_ids(
            blocking_issue_output_ids=blocking_ids, safety_failure_output_ids=safety_ids,
            one_sample_per_language_category_output_ids=one_sample_ids,
            borderline_candidate_output_ids=set(),
        )
        self.repository.record_metric(
            connection, run_id,
            {
                "language": None, "category": None, "metric_name": "required_review_output_ids",
                "metric_value": float(len(required)),
                "details_json": dumps_json({"output_ids": sorted(required)}),
            },
        )

    def outputs_for_run(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            rows = self.repository.outputs_for_run(connection, run["id"])
        return {"items": [public_row(row) for row in rows]}

    def metrics_for_run(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            rows = self.repository.metrics_for_run(connection, run["id"])
        return {"items": [public_row(row) for row in rows]}

    def issues_for_run(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            rows = self.repository.issues_for_run(connection, run["id"])
        return {"items": [public_row(row) for row in rows]}

    # --- human review -----------------------------------------------------

    def submit_review(self, payload: HumanReviewCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            output = self.repository.output(
                connection, payload.model_evaluation_output_public_id
            )
            review_id = self.repository.record_human_review(
                connection, output["id"],
                {
                    "reviewer_admin_public_id": admin_id,
                    "language": payload.language,
                    "category": payload.category,
                    "relevance_score": payload.relevance_score,
                    "correctness_score": payload.correctness_score,
                    "instruction_following_score": payload.instruction_following_score,
                    "language_quality_score": payload.language_quality_score,
                    "safety_score": payload.safety_score,
                    "overall_score": payload.overall_score,
                    "verdict": payload.verdict,
                    "comment": payload.comment,
                },
            )
            self._audit(
                connection, "model_evaluation_human_review_submitted", admin_id, review_id,
                verdict=payload.verdict,
            )
            reviews = self.repository.reviews_for_output(connection, output["id"])
            return {
                "review": public_row(
                    connection.execute(
                        "SELECT * FROM model_evaluation_human_reviews WHERE public_id=?",
                        (review_id,),
                    ).fetchone()
                ),
                "aggregate": aggregate_reviews([dict(row) for row in reviews]),
            }

    def review_queue(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            required_row = connection.execute(
                """SELECT details_json FROM model_evaluation_metrics
                WHERE model_evaluation_run_id=? AND metric_name='required_review_output_ids'
                ORDER BY id DESC LIMIT 1""",
                (run["id"],),
            ).fetchone()
            required_ids = set(
                loads_json(required_row["details_json"])["output_ids"] if required_row else []
            )
            outputs = self.repository.outputs_for_run(connection, run["id"])
            reviewed_ids = set()
            for output in outputs:
                if self.repository.reviews_for_output(connection, output["id"]):
                    reviewed_ids.add(output["public_id"])
        coverage = review_coverage(required_ids, reviewed_ids)
        return {"required_output_ids": sorted(required_ids), **coverage}

    def reviews_for_run(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            rows = self.repository.reviews_for_run(connection, run["id"])
            reviews_by_output: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                reviews_by_output.setdefault(row["output_public_id"], []).append(dict(row))
        return {
            "items": [public_row(row) for row in rows],
            "aggregate": aggregate_run_reviews(reviews_by_output),
        }

    # --- chat readiness -----------------------------------------------------

    def assess_readiness(self, run_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            if run["status"] not in {"completed", "completed_with_warnings"}:
                raise ValidationError("run must complete before readiness can be assessed")
            issues = self.repository.issues_for_run(connection, run["id"])
            metrics = {
                (row["language"], row["metric_name"]): row["metric_value"]
                for row in self.repository.metrics_for_run(connection, run["id"])
            }
            reviews_rows = self.repository.reviews_for_run(connection, run["id"])
            reviews_by_output: dict[str, list[dict[str, Any]]] = {}
            for row in reviews_rows:
                reviews_by_output.setdefault(row["output_public_id"], []).append(dict(row))
            review_summary = aggregate_run_reviews(reviews_by_output)
            required_row = connection.execute(
                """SELECT details_json FROM model_evaluation_metrics
                WHERE model_evaluation_run_id=? AND metric_name='required_review_output_ids'
                ORDER BY id DESC LIMIT 1""",
                (run["id"],),
            ).fetchone()
            required_ids = set(
                loads_json(required_row["details_json"])["output_ids"] if required_row else []
            )
            coverage = review_coverage(required_ids, set(reviews_by_output))

            checkpoint_lineage_verified = run["checkpoint_status"] in {"completed", "verified"}
            fixture_public_ids = {
                row["public_id"] for row in self.repository.outputs_for_run(connection, run["id"])
            }
            tamil_fixture_count = metrics.get(("ta", "language_compliance_score")) is not None
            tanglish_fixture_count = metrics.get(("tgl", "language_compliance_score")) is not None
            safety_fixture_count = metrics.get(
                ("overall", "correct_refusal_rate")
            ) is not None

        blocking_count = sum(1 for row in issues if row["severity"] == "blocking")
        warning_count = sum(1 for row in issues if row["severity"] == "warning")

        thresholds = ReadinessThresholds(
            min_total_fixtures=self.settings.eval_min_total_fixtures,
            min_instruction_following_score=self.settings.eval_min_instruction_following_score,
            min_language_compliance_score=self.settings.eval_min_language_compliance_score,
            min_surface_relevance_score=self.settings.eval_min_surface_relevance_score,
            max_unsupported_claim_rate=self.settings.eval_max_unsupported_claim_rate,
            max_over_refusal_rate=self.settings.eval_max_over_refusal_rate,
            max_prompt_leakage_rate=self.settings.eval_max_prompt_leakage_rate,
            max_duplicate_output_rate=self.settings.eval_max_duplicate_output_rate,
            min_unicode_integrity_rate=self.settings.eval_min_unicode_integrity_rate,
            min_human_review_coverage=self.settings.eval_min_human_review_coverage,
            max_human_review_disagreement=self.settings.eval_max_human_review_disagreement,
        )
        result = assess_chat_readiness(
            blocking_issue_count=blocking_count,
            checkpoint_lineage_verified=checkpoint_lineage_verified,
            tamil_fixture_count=1 if tamil_fixture_count else 0,
            tanglish_fixture_count=1 if tanglish_fixture_count else 0,
            safety_fixture_count=1 if safety_fixture_count else 0,
            total_fixture_count=len(fixture_public_ids),
            instruction_following_score=metrics.get(("overall", "instruction_following_score")),
            language_compliance_scores={
                language: metrics.get((language, "language_compliance_score"))
                for language in LANGUAGES
            },
            surface_relevance_score=metrics.get(("overall", "surface_relevance_score")),
            unsupported_claim_rate=metrics.get(("overall", "unsupported_claim_risk")),
            unsafe_compliance_rate=metrics.get(("overall", "unsafe_compliance_rate")),
            over_refusal_rate=metrics.get(("overall", "over_refusal_rate")),
            prompt_leakage_rate=metrics.get(("overall", "prompt_leakage_rate")),
            role_leakage_rate=metrics.get(("overall", "role_leakage_rate")),
            duplicate_output_rate=metrics.get(("overall", "duplicate_output_rate")),
            unicode_integrity_rate=metrics.get(("overall", "unicode_integrity_rate")),
            human_review_coverage=coverage["coverage_ratio"],
            human_review_disagreement_rate=review_summary["disagreement_rate"],
            evaluation_sufficiency_status=self._sufficiency_status(len(fixture_public_ids)),
            thresholds=thresholds,
        )

        with self.repository.transaction() as connection:
            public_id = self.repository.record_readiness(
                connection, run["id"],
                {
                    "status": result["status"],
                    "dimension_scores_json": dumps_json(result["dimension_scores"]),
                    "blocking_issue_count": blocking_count,
                    "warning_issue_count": warning_count,
                    "rationale_json": dumps_json(result["rationale"]),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "model_chat_readiness_assessed", admin_id, run_public_id,
                status=result["status"],
            )
            row = connection.execute(
                "SELECT * FROM model_chat_readiness_assessments WHERE public_id=?", (public_id,)
            ).fetchone()
            return public_row(row)

    def latest_readiness(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            row = self.repository.latest_readiness(connection, run["id"])
        if row is None:
            raise NotFoundError("no chat-readiness assessment exists for this run")
        return public_row(row)

    # --- comparisons -----------------------------------------------------

    def compare_runs(
        self, payload: ModelEvaluationComparisonCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            left_run = self.repository.run(connection, payload.left_run_public_id)
            right_run = self.repository.run(connection, payload.right_run_public_id)
            left_fixture_set_id = loads_json(
                left_run["generation_configuration_json"]
            )["fixture_set_public_id"]
            right_fixture_set_id = loads_json(
                right_run["generation_configuration_json"]
            )["fixture_set_public_id"]
            left_fixture_set = self.repository.fixture_set(connection, left_fixture_set_id)
            right_fixture_set = self.repository.fixture_set(connection, right_fixture_set_id)
            left_suite = self.repository.suite(
                connection, left_run["model_evaluation_suite_public_id"]
            )
            right_suite = self.repository.suite(
                connection, right_run["model_evaluation_suite_public_id"]
            )
            left = {
                "suite_version_public_id": left_run["model_evaluation_suite_public_id"],
                "generation_config_checksum_sha256": left_run[
                    "generation_config_checksum_sha256"
                ],
                "tokenizer_version_public_id": left_run["tokenizer_version_public_id"],
                "fixture_set_checksum_sha256": left_fixture_set["checksum_sha256"],
                "threshold_configuration_checksum_sha256": hashlib.sha256(
                    (
                        left_suite["automated_thresholds_json"]
                        + left_suite["readiness_gate_configuration_json"]
                    ).encode("utf-8")
                ).hexdigest(),
            }
            right = {
                "suite_version_public_id": right_run["model_evaluation_suite_public_id"],
                "generation_config_checksum_sha256": right_run[
                    "generation_config_checksum_sha256"
                ],
                "tokenizer_version_public_id": right_run["tokenizer_version_public_id"],
                "fixture_set_checksum_sha256": right_fixture_set["checksum_sha256"],
                "threshold_configuration_checksum_sha256": hashlib.sha256(
                    (
                        right_suite["automated_thresholds_json"]
                        + right_suite["readiness_gate_configuration_json"]
                    ).encode("utf-8")
                ).hexdigest(),
            }
            comparison = assess_comparison(left, right, list(left))
            public_id = self.repository.record_comparison(
                connection,
                {
                    "left_run_id": left_run["id"],
                    "right_run_id": right_run["id"],
                    "compatibility": comparison["compatibility"],
                    "ranked": comparison["ranked"],
                    "fields_json": dumps_json(comparison["fields"]),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "model_evaluation_comparison_created", admin_id, public_id,
                compatibility=comparison["compatibility"],
            )
            return public_row(self.repository.comparison(connection, public_id))

    # --- reproducibility manifest -----------------------------------------------------

    def generate_manifest(self, run_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            fixture_set_public_id = loads_json(
                run["generation_configuration_json"]
            )["fixture_set_public_id"]
            fixture_set = self.repository.fixture_set(connection, fixture_set_public_id)
            readiness = self.repository.latest_readiness(connection, run["id"])
            metrics = self.repository.metrics_for_run(connection, run["id"])
            issues = self.repository.issues_for_run(connection, run["id"])
            manifest = {
                "run_public_id": run["public_id"],
                "suite_public_id": run["model_evaluation_suite_public_id"],
                "candidate_core_model_version_public_id": run[
                    "candidate_core_model_version_public_id"
                ],
                "checkpoint_public_id": run["checkpoint_public_id"],
                "checkpoint_checksum_sha256": run["checkpoint_model_checksum_sha256"],
                "tokenizer_version_public_id": run["tokenizer_version_public_id"],
                "fixture_set_public_id": fixture_set["public_id"],
                "fixture_set_checksum_sha256": fixture_set["checksum_sha256"],
                "generation_configuration": loads_json(run["generation_configuration_json"]),
                "generation_config_checksum_sha256": run["generation_config_checksum_sha256"],
                "metric_count": len(metrics),
                "issue_count": len(issues),
                "blocking_issue_count": sum(
                    1 for row in issues if row["severity"] == "blocking"
                ),
                "readiness_status": readiness["status"] if readiness else "not_assessed",
                "not_public_chat_ready": True,
                "known_limitations": {
                    "surface_relevance_is_not_factual_correctness": True,
                    "safety_checks_are_keyword_based_and_non_exhaustive": True,
                    "unsupported_claim_risk_is_a_bounded_heuristic_not_hallucination_detection": (
                        True
                    ),
                },
            }
            manifest_json = dumps_json(manifest)
            checksum = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
            self.repository.record_manifest(connection, run["id"], manifest_json, checksum)
            self._audit(connection, "model_evaluation_manifest_generated", admin_id, run_public_id)
            return public_row(self.repository.latest_manifest(connection, run["id"]))

    def verify_manifest(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.run(connection, run_public_id)
            row = self.repository.latest_manifest(connection, run["id"])
            if row is None:
                raise NotFoundError("no reproducibility manifest exists for this run")
            recomputed = hashlib.sha256(row["manifest_json"].encode("utf-8")).hexdigest()
            matches = recomputed == row["manifest_checksum_sha256"]
        return {
            "public_id": row["public_id"],
            "stored_checksum": row["manifest_checksum_sha256"],
            "recomputed_checksum": recomputed,
            "matches": matches,
        }

    # --- helpers -----------------------------------------------------

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
                "model_evaluation", resource_id, "success", dumps_json(metadata),
            ),
        )
