"""MB-06: Brud Mini Brain Learning Supervisor -- the orchestration
layer for the 14-stage dataset-to-release-candidate workflow.

This service NEVER trains a model, NEVER writes a dataset/tokenizer/
RAG/checkpoint/Runtime row, and NEVER deploys or exports anything. It
composes existing, unmodified services purely through their public
methods:

- `MiniBrainDatasetIntelligenceService`/`MiniBrainAdvancedDatasetService`
  (MB-05/MB-05.1) for dataset validation -- read-only analysis calls.
- `RagSandboxAnswerService`/`RagSandboxEvaluationService`/
  `RagSandboxReportService` for RAG evaluation. Corpus preparation,
  indexing, and retrieval remain admin-driven through the existing RAG
  Sandbox admin flow (`backend/api/routes/rag_sandbox.py`) -- this
  service only runs grounded generation, evaluation, and report
  finalization on top of an already-built index/retrieval run, matching
  the task's own framing: "retrieval by existing RAG engine, MB-06 only
  evaluates". `RagSandboxReportService.finalize()` also enforces the
  existing human-review-coverage gate -- this service does not, and
  must not, bypass it; `finalize_rag_evaluation` simply retries after an
  admin has completed that review through the existing RAG Sandbox UI.
- `PretrainingService` -- ONLY `.create_job()` (submission) plus the
  read-only `.get_job()`/`.events()`/`.metrics()`/`.checkpoints()`/
  `.checkpoint()`/`.evaluations()`/`.evaluation()`, plus `.promote()`
  for the terminal release-candidate step. NEVER `.validate_job()`,
  `.queue_job()`, `.pause()`, `.resume()`, `.cancel()`, or `.run_one()`
  -- those remain the Training Engine's exclusive province.
- `TrainingEvaluationService.assess_quality()` -- the existing quality
  gate `promote()` itself requires; this service never re-implements it.
- `ModelEvaluationService` -- the existing benchmark system
  (`create_run`/`execute_run`/`metrics_for_run`), never a new one.
- The six pure `core_model.mini_brain.learning_supervisor` modules for
  every deterministic decision (validation, request building, result
  analysis, comparison, recommendations, report assembly).

Every irreversible step (training submission, release-candidate
creation) requires an explicit prior admin decision recorded on the
session; nothing here proceeds automatically past a decision gate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.mini_brain_learning import (
    MiniBrainLearningRepository,
    public_row,
)
from backend.database.repositories.model_evaluation import ModelEvaluationRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.models.model_evaluation import ModelEvaluationRunCreate
from backend.models.pretraining import PretrainingJobCreate
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_advanced_dataset_service import MiniBrainAdvancedDatasetService
from backend.services.mini_brain_dataset_intelligence_service import (
    MiniBrainDatasetIntelligenceService,
)
from backend.services.model_evaluation_service import ModelEvaluationService
from backend.services.pretraining_service import PretrainingService
from backend.services.rag_sandbox_answer_service import RagSandboxAnswerService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from backend.services.rag_sandbox_evaluation_service import RagSandboxEvaluationService
from backend.services.rag_sandbox_report_service import RagSandboxReportService
from backend.services.training_evaluation_service import TrainingEvaluationService
from core_model.mini_brain.learning_supervisor.learning_report_generator import (
    generate_learning_report,
)
from core_model.mini_brain.learning_supervisor.model_comparator import compare_models
from core_model.mini_brain.learning_supervisor.recommendation_engine import (
    generate_learning_recommendations,
)
from core_model.mini_brain.learning_supervisor.training_request_builder import (
    build_training_request,
)
from core_model.mini_brain.learning_supervisor.training_request_validator import (
    validate_training_request,
)
from core_model.mini_brain.learning_supervisor.training_result_analyzer import (
    analyze_training_result as _analyze_training_result,
)

DECISION_VALUES = {"approve", "reject"}
ADMIN_FINAL_DECISION_VALUES = {"reject", "retrain", "fine_tune", "accept"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainLearningSupervisorService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainLearningRepository(settings.resolved_database_path)

        dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        self.dataset_intelligence = MiniBrainDatasetIntelligenceService(dataset_service)
        self.advanced_dataset = MiniBrainAdvancedDatasetService(
            dataset_service, self.dataset_intelligence
        )

        pretraining_repository = PretrainingRepository(settings.resolved_database_path)
        reliability_repository = TrainingReliabilityRepository(settings.resolved_database_path)
        self.pretraining = PretrainingService(pretraining_repository, settings)
        self.training_evaluation = TrainingEvaluationService(
            pretraining_repository, reliability_repository, settings
        )

        self.model_evaluation = ModelEvaluationService(
            ModelEvaluationRepository(settings.resolved_database_path), settings
        )

        self.rag_answer = RagSandboxAnswerService(settings)
        self.rag_evaluation = RagSandboxEvaluationService(settings)
        self.rag_report = RagSandboxReportService(settings)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, session_row_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, learning_session_id=session_row_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset)
        return {"items": [public_row(row) for row in rows]}

    def events(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_events(
                connection, learning_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    # -- stage 1: session creation --------------------------------------

    def create_session(
        self, *, dataset_source_public_id: str, hyperparameter_profile: str = "default",
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, dataset_source_public_id=dataset_source_public_id,
                hyperparameter_profile=hyperparameter_profile, created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="dataset_validation",
                message=f"learning session created for dataset source {dataset_source_public_id}",
                metadata={"hyperparameter_profile": hyperparameter_profile},
            )
            return public_row(self.repository.session(connection, public_id))

    # -- stage 2/3: dataset validation -----------------------------------

    def validate_dataset(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            dataset_source_public_id = session_row["dataset_source_public_id"]

            training_readiness = self.dataset_intelligence.training(dataset_source_public_id)
            advanced_report = self.advanced_dataset.report(dataset_source_public_id)
            combined = {
                "training_readiness": training_readiness,
                "advanced_report": advanced_report,
            }

            self.repository.update_session(
                connection, session_public_id,
                {"dataset_readiness_report_json": combined, "stage": "awaiting_dataset_decision"},
            )
            self._event(
                connection, session_row["id"], "dataset_validated", stage="dataset_validation",
                message=f"dataset training readiness: {training_readiness['status']}",
                metadata={"status": training_readiness["status"], "reasons": training_readiness["reasons"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 4: admin dataset decision gate ----------------------------

    def decide_dataset(
        self, session_public_id: str, *, decision: str, admin_id: str,
    ) -> dict[str, Any]:
        if decision not in DECISION_VALUES:
            raise ValidationError(f"decision must be one of {sorted(DECISION_VALUES)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_dataset_decision":
                raise ValidationError(
                    f"session is at stage '{session_row['stage']}', not 'awaiting_dataset_decision'"
                )
            fields: dict[str, Any] = {
                "dataset_decision": decision, "dataset_decided_by": admin_id, "dataset_decided_at": _now(),
            }
            if decision == "reject":
                fields["status"] = "rejected_at_dataset"
                fields["stage"] = "closed"
            else:
                fields["stage"] = "rag_evaluation"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"dataset_{decision}d", stage="awaiting_dataset_decision",
                message=f"admin {decision}d dataset readiness", metadata={"admin_id": admin_id},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 5: RAG evaluation ------------------------------------------

    def run_rag_evaluation(
        self, session_public_id: str, *, rag_sandbox_experiment_public_id: str,
        retrieval_run_public_id: str, generation_assignment_public_id: str, admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["dataset_decision"] != "approve" or session_row["stage"] != "rag_evaluation":
                raise ValidationError(
                    "dataset must be approved and the session must be at stage 'rag_evaluation' "
                    "before running the RAG evaluation"
                )
            session_row_id = session_row["id"]

        generation = self.rag_answer.run_generation(
            rag_sandbox_experiment_public_id, retrieval_run_public_id=retrieval_run_public_id,
            generation_assignment_public_id=generation_assignment_public_id, admin_id=admin_id,
        )
        answer_runs = generation["answer_runs"]
        evaluation_count = 0
        for answer_run in answer_runs:
            evaluations = self.rag_evaluation.run_evaluation(
                rag_sandbox_experiment_public_id, answer_run["public_id"], admin_id=admin_id
            )
            evaluation_count += len(evaluations)

        with self.repository.transaction() as connection:
            self.repository.update_session(
                connection, session_public_id,
                {"rag_sandbox_experiment_public_id": rag_sandbox_experiment_public_id},
            )
            self._event(
                connection, session_row_id, "rag_generation_evaluated", stage="rag_evaluation",
                message=f"{len(answer_runs)} answer run(s), {evaluation_count} evaluation(s) recorded",
                metadata={"answer_run_count": len(answer_runs), "evaluation_count": evaluation_count},
            )

        return self._finalize_rag_report(session_public_id, session_row_id, admin_id)

    def finalize_rag_evaluation(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if not session_row["rag_sandbox_experiment_public_id"]:
                raise ValidationError("no RAG Sandbox experiment has been evaluated for this session yet")
            session_row_id = session_row["id"]
        return self._finalize_rag_report(
            session_public_id, session_row_id, admin_id,
            experiment_public_id=session_row["rag_sandbox_experiment_public_id"],
        )

    def _finalize_rag_report(
        self, session_public_id: str, session_row_id: int, admin_id: str,
        experiment_public_id: str | None = None,
    ) -> dict[str, Any]:
        if experiment_public_id is None:
            experiment_public_id = self.session(session_public_id)["rag_sandbox_experiment_public_id"]
        try:
            report = self.rag_report.finalize(experiment_public_id, admin_id=admin_id)
            with self.repository.transaction() as connection:
                self.repository.update_session(
                    connection, session_public_id,
                    {"rag_evaluation_report_json": report, "stage": "awaiting_rag_decision"},
                )
                self._event(
                    connection, session_row_id, "rag_report_finalized", stage="rag_evaluation",
                    message=f"RAG production readiness: {report['production_rag_readiness']}",
                    metadata={"production_rag_readiness": report["production_rag_readiness"]},
                )
        except RagSandboxError as exc:
            partial = {
                "status": "pending_human_review",
                "reason": str(exc),
                "note": (
                    "generation and automated evaluation are complete; an admin must review every "
                    "tested query in the existing RAG Sandbox UI before the report can finalize"
                ),
            }
            with self.repository.transaction() as connection:
                self.repository.update_session(
                    connection, session_public_id, {"rag_evaluation_report_json": partial},
                )
                self._event(
                    connection, session_row_id, "rag_report_pending_human_review", stage="rag_evaluation",
                    message=str(exc),
                )
        return self.session(session_public_id)

    # -- stage 6: admin RAG decision gate ---------------------------------

    def decide_rag(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in DECISION_VALUES:
            raise ValidationError(f"decision must be one of {sorted(DECISION_VALUES)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_rag_decision":
                raise ValidationError(
                    f"session is at stage '{session_row['stage']}', not 'awaiting_rag_decision'"
                )
            fields: dict[str, Any] = {
                "rag_decision": decision, "rag_decided_by": admin_id, "rag_decided_at": _now(),
            }
            if decision == "reject":
                fields["status"] = "rejected_at_rag"
                fields["stage"] = "closed"
            else:
                fields["stage"] = "training_request"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"rag_{decision}d", stage="awaiting_rag_decision",
                message=f"admin {decision}d RAG evaluation", metadata={"admin_id": admin_id},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 7: training request validation + submission -----------------

    def submit_training_request(
        self, session_public_id: str, *, name: str, dataset_version_public_id: str,
        tokenizer_version_public_id: str, core_model_version_public_id: str,
        hyperparameter_profile: str | None = None, admin_id: str,
    ) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "training_request":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'training_request'"
            )

        readiness_report = session_data["dataset_readiness_report"] or {}
        advanced_report = readiness_report.get("advanced_report") or {}
        validation = validate_training_request(
            dataset_readiness=readiness_report.get("training_readiness", {}),
            dataset_decision=session_data["dataset_decision"],
            rag_required=True,
            rag_decision=session_data["rag_decision"],
            advanced_risk=advanced_report.get("risk"),
            advanced_conflicts=advanced_report.get("conflicts"),
        )
        if not validation["valid"]:
            raise ValidationError(f"training request blocked: {validation['blockers']}")

        payload = build_training_request(
            name=name, dataset_version_public_id=dataset_version_public_id,
            tokenizer_version_public_id=tokenizer_version_public_id,
            core_model_version_public_id=core_model_version_public_id,
            hyperparameter_profile=hyperparameter_profile or session_data["hyperparameter_profile"],
        )
        job = self.pretraining.create_job(PretrainingJobCreate(**payload), admin_id)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "dataset_version_public_id": dataset_version_public_id,
                    "tokenizer_version_public_id": tokenizer_version_public_id,
                    "core_model_version_public_id": core_model_version_public_id,
                    "training_request_payload_json": payload,
                    "training_job_public_id": job["public_id"],
                    "stage": "training_monitoring",
                    "status": "training_requested",
                },
            )
            self._event(
                connection, session_row["id"], "training_request_submitted", stage="training_request",
                message=f"training job {job['public_id']} submitted to the Training Engine",
                metadata={"warnings": validation["warnings"], "job_public_id": job["public_id"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 8: read-only training monitoring -----------------------------

    def monitor_training(self, session_public_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        job_public_id = session_data["training_job_public_id"]
        if not job_public_id:
            raise ValidationError("no training job has been submitted for this session yet")
        return {
            "job": self.pretraining.get_job(job_public_id),
            "events": self.pretraining.events(job_public_id),
            "metrics": self.pretraining.metrics(job_public_id),
            "checkpoints": self.pretraining.checkpoints(job_public_id),
        }

    # -- stage 9: training completion analysis -------------------------------

    def analyze_training_result(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        job_public_id = session_data["training_job_public_id"]
        if not job_public_id:
            raise ValidationError("no training job has been submitted for this session yet")

        job = self.pretraining.get_job(job_public_id)
        if job["status"] not in {"completed", "completed_with_warnings", "failed", "paused", "cancelled"}:
            raise ValidationError(f"training job is still running (status={job['status']!r})")

        metrics = self.pretraining.metrics(job_public_id)["items"]
        step_losses = [m["training_loss"] for m in metrics if m["training_loss"] is not None]
        checkpoints = self.pretraining.checkpoints(job_public_id)["items"]

        result = _analyze_training_result(job=job, step_losses=step_losses, checkpoints=checkpoints)

        quality_assessment = None
        if job["status"] in {"completed", "completed_with_warnings"}:
            quality_assessment = self.training_evaluation.assess_quality(job_public_id, admin_id)
        result["quality_assessment"] = quality_assessment

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"training_report_json": result, "stage": "benchmark_evaluation"},
            )
            self._event(
                connection, session_row["id"], "training_result_analyzed", stage="training_analysis",
                message=f"job status={result['job_status']}, indicators={result['indicators']}",
                metadata={"job_status": result["job_status"], "indicators": result["indicators"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 10: benchmark evaluation ---------------------------------------

    def run_benchmark(
        self, session_public_id: str, *, model_evaluation_fixture_set_public_id: str,
        candidate_core_model_version_public_id: str, generation_configuration: dict[str, Any] | None = None,
        admin_id: str,
    ) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "benchmark_evaluation":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'benchmark_evaluation'"
            )

        run = self.model_evaluation.create_run(
            ModelEvaluationRunCreate(
                model_evaluation_fixture_set_public_id=model_evaluation_fixture_set_public_id,
                candidate_core_model_version_public_id=candidate_core_model_version_public_id,
                generation_configuration=generation_configuration or {},
            ),
            admin_id,
        )
        self.model_evaluation.execute_run(run["public_id"], admin_id)
        metrics = self.model_evaluation.metrics_for_run(run["public_id"])

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "benchmark_run_public_id": run["public_id"],
                    "benchmark_report_json": metrics,
                    "stage": "model_comparison",
                },
            )
            self._event(
                connection, session_row["id"], "benchmark_evaluated", stage="benchmark_evaluation",
                message=f"benchmark run {run['public_id']} executed, {len(metrics['items'])} metric(s)",
                metadata={"benchmark_run_public_id": run["public_id"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 11: model comparison ---------------------------------------------

    def compare_models(
        self, session_public_id: str, *, previous_benchmark_run_public_id: str, admin_id: str,
    ) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "model_comparison":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'model_comparison'"
            )
        previous_metrics = self.model_evaluation.metrics_for_run(previous_benchmark_run_public_id)["items"]
        new_metrics = (session_data["benchmark_report"] or {}).get("items", [])

        comparison = compare_models(previous_metrics=previous_metrics, new_metrics=new_metrics)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"comparison_report_json": comparison, "stage": "recommendation"},
            )
            self._event(
                connection, session_row["id"], "models_compared", stage="model_comparison",
                message=(
                    f"{comparison['improvement_count']} improvement(s), "
                    f"{comparison['regression_count']} regression(s)"
                ),
                metadata={
                    "improvement_count": comparison["improvement_count"],
                    "regression_count": comparison["regression_count"],
                },
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 12: recommendations + stage 13: report ------------------------------

    def generate_recommendations(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "recommendation":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'recommendation'"
            )

        readiness_report = session_data["dataset_readiness_report"] or {}
        recommendations = generate_learning_recommendations(
            dataset_readiness=readiness_report.get("training_readiness", {}),
            advanced_report=readiness_report.get("advanced_report") or None,
            rag_report=session_data["rag_evaluation_report"] or None,
            training_result=session_data["training_report"] or None,
            comparison=session_data["comparison_report"] or None,
        )
        report = generate_learning_report(
            session_public_id=session_public_id,
            dataset_report=session_data["dataset_readiness_report"] or None,
            rag_report=session_data["rag_evaluation_report"] or None,
            training_report=session_data["training_report"] or None,
            benchmark_report=session_data["benchmark_report"] or None,
            comparison_report=session_data["comparison_report"] or None,
            recommendations=recommendations,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"recommendation_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "recommendations_generated", stage="recommendation",
                message=f"{len(recommendations)} recommendation(s) generated",
                metadata={"blocking_recommendation_count": report["blocking_recommendation_count"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- admin review of the full learning report ---------------------------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_FINAL_DECISION_VALUES:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_FINAL_DECISION_VALUES)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(
                    f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'"
                )
            status_map = {
                "reject": "admin_rejected", "retrain": "retrain_requested",
                "fine_tune": "fine_tune_requested", "accept": "in_progress",
            }
            stage = "release_candidate" if decision == "accept" else "closed"
            fields = {
                "admin_final_decision": decision, "admin_decided_by": admin_id,
                "admin_decided_at": _now(), "status": status_map[decision], "stage": stage,
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"admin_review_{decision}", stage="awaiting_admin_review",
                message=f"admin decided '{decision}' on the learning report", metadata={"admin_id": admin_id},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 14: release candidate (no deployment, no GGUF export) ----------------

    def create_release_candidate(
        self, session_public_id: str, *, checkpoint_public_id: str, admin_id: str,
        override_comment: str | None = None,
    ) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "release_candidate" or session_data["admin_final_decision"] != "accept":
            raise ValidationError(
                "session must be at stage 'release_candidate' with an 'accept' admin decision"
            )

        candidate = self.pretraining.promote(checkpoint_public_id, admin_id, override_comment=override_comment)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "release_candidate_core_model_version_public_id": candidate["public_id"],
                    "stage": "closed", "status": "accepted",
                },
            )
            self._event(
                connection, session_row["id"], "release_candidate_created", stage="release_candidate",
                message=(
                    f"core model version {candidate['public_id']} created as a release candidate -- "
                    "not deployed, not exported; the Release Pipeline must continue this separately"
                ),
                metadata={"core_model_version_public_id": candidate["public_id"]},
            )
            return public_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainLearningSupervisorService"]
