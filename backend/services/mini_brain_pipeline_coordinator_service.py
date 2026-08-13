"""MB-12: Brud Mini Brain Autonomous AI Knowledge Pipeline Coordinator
-- the orchestration layer that links together, in order, the real
sessions MB-09, MB-10, MB-11, and MB-06 already produced for one
topic, and reports on the result. Orchestration, validation,
scheduling, and reporting only -- confirmed by structural/safety tests
reading this file's own source.

This service NEVER trains a model, NEVER writes a dataset record,
NEVER deploys, and NEVER modifies RAG. It composes existing,
unmodified systems through their public read methods only:

- `MiniBrainDatasetIntelligenceService` (MB-05) -- ONLY `.training()`,
  `.language()`.
- `MiniBrainAdvancedDatasetService` (MB-05.1) -- ONLY `.report()`.
- `MiniBrainLearningSupervisorService` (MB-06) -- ONLY `.session()`,
  `.events()`. MB-12 never submits, monitors, or advances an MB-06
  session -- an admin who wants to actually start training does so
  through MB-06's own UI, then links the resulting session here.
- `MiniBrainContinuousLearningService` (MB-08) -- ONLY `.list_sessions()`.
- `MiniBrainContinuousLearningCenterService` (MB-09) -- ONLY
  `.session()`, `.events()`.
- `MiniBrainResearchCenterService` (MB-10) -- ONLY `.session()`,
  `.events()`.
- `MiniBrainDatasetEvolutionService` (MB-11) -- ONLY `.session()`,
  `.events()`.

MB-12 deliberately never imports or calls RAG Sandbox at all -- unlike
MB-06/MB-10/MB-11, which each run real RAG Sandbox generation and
evaluation, MB-12's own RAG First Enforcement only ever reads a RAG
report MB-11 or MB-06 already produced. Re-running RAG Sandbox a
fourth time here would duplicate logic three other phases already
own; see the completion report's Finding 1 for the full reasoning.

Every stage transition goes through `dependency_coordinator.check_
dependencies()` before it is written, so a pipeline can never skip a
stage no matter what order the admin calls these methods in.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.mini_brain_pipeline_coordinator import (
    MiniBrainPipelineCoordinatorRepository,
    public_session_row,
)
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_advanced_dataset_service import MiniBrainAdvancedDatasetService
from backend.services.mini_brain_continuous_learning_center_service import (
    MiniBrainContinuousLearningCenterService,
)
from backend.services.mini_brain_continuous_learning_service import (
    MiniBrainContinuousLearningService,
)
from backend.services.mini_brain_dataset_evolution_service import MiniBrainDatasetEvolutionService
from backend.services.mini_brain_dataset_intelligence_service import (
    MiniBrainDatasetIntelligenceService,
)
from backend.services.mini_brain_learning_supervisor_service import (
    MiniBrainLearningSupervisorService,
)
from backend.services.mini_brain_research_center_service import MiniBrainResearchCenterService
from core_model.mini_brain.pipeline_coordinator.admin_decision_center import (
    DECISIONS,
    evaluate_decision,
)
from core_model.mini_brain.pipeline_coordinator.dependency_coordinator import check_dependencies
from core_model.mini_brain.pipeline_coordinator.improvement_predictor import predict_improvement
from core_model.mini_brain.pipeline_coordinator.lifecycle_timeline import build_timeline
from core_model.mini_brain.pipeline_coordinator.master_report_generator import (
    generate_master_report,
)
from core_model.mini_brain.pipeline_coordinator.pipeline_manager import track_pipeline
from core_model.mini_brain.pipeline_coordinator.rag_first_enforcement import check_rag_gate
from core_model.mini_brain.pipeline_coordinator.recommendation_engine import recommend_next_action
from core_model.mini_brain.pipeline_coordinator.state_machine import stage_index
from core_model.mini_brain.pipeline_coordinator.training_readiness_coordinator import (
    coordinate_training_readiness,
)

MAX_MB08_CYCLES = 10
_TRAINING_ADVANCE_TARGETS = ("training_running", "benchmark_ready", "release_candidate", "completed")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainPipelineCoordinatorService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainPipelineCoordinatorRepository(settings.resolved_database_path)

        dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        self.dataset_intelligence = MiniBrainDatasetIntelligenceService(dataset_service)
        self.advanced_dataset = MiniBrainAdvancedDatasetService(dataset_service, self.dataset_intelligence)
        self.learning_supervisor = MiniBrainLearningSupervisorService(settings)
        self.continuous_learning = MiniBrainContinuousLearningService(settings)
        self.planning_center = MiniBrainContinuousLearningCenterService(settings)
        self.research_center = MiniBrainResearchCenterService(settings)
        self.dataset_evolution = MiniBrainDatasetEvolutionService(settings)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, pipeline_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, pipeline_session_id=pipeline_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset)
        return {"items": [public_session_row(row) for row in rows]}

    def events(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_events(
                connection, pipeline_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def _apply_transition(
        self, connection, session_row, target_stage: str, evidence: dict[str, Any], event_type: str, message: str,
    ) -> dict[str, Any]:
        dependency = check_dependencies(current_stage=session_row["stage"], target_stage=target_stage, evidence=evidence)
        if not dependency["allowed"]:
            raise ValidationError(f"stage transition blocked: {dependency['reasons']}")
        self.repository.update_session(connection, session_row["public_id"], {"stage": target_stage})
        self._event(connection, session_row["id"], event_type, stage=target_stage, message=message)
        return dependency

    # -- stage 1: session creation --------------------------------------

    def create_session(self, *, topic: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(connection, topic=topic, created_by_admin_public_id=admin_id)
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="new",
                message=f"pipeline coordination started for topic '{topic}'",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- link MB-09 (Research) -----------------------------------------------

    def link_research_stage(self, session_public_id: str, *, mb09_session_public_id: str, admin_id: str) -> dict[str, Any]:
        del admin_id
        self.planning_center.session(mb09_session_public_id)
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self._apply_transition(
                connection, session_row, "under_research", {"mb09_linked": True},
                "research_linked", f"linked MB-09 planning session {mb09_session_public_id}",
            )
            self.repository.update_session(connection, session_public_id, {"mb09_session_public_id": mb09_session_public_id})
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- link MB-10 (Provider Consensus / Draft) -------------------------------

    def link_research_center_stage(self, session_public_id: str, *, mb10_session_public_id: str, admin_id: str) -> dict[str, Any]:
        del admin_id
        mb10_session = self.research_center.session(mb10_session_public_id)
        if mb10_session.get("dataset_draft"):
            target_stage = "draft_ready"
        elif mb10_session.get("consensus_report"):
            target_stage = "provider_consensus_pending"
        else:
            raise ValidationError("MB-10 session has not reached provider consensus or produced a draft yet")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self._apply_transition(
                connection, session_row, target_stage, {"mb10_linked": True},
                "research_center_linked", f"linked MB-10 research session {mb10_session_public_id} (stage={target_stage})",
            )
            self.repository.update_session(connection, session_public_id, {"mb10_session_public_id": mb10_session_public_id})
            return public_session_row(self.repository.session(connection, session_public_id))

    def refresh_research_center_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if not session_data["mb10_session_public_id"]:
            raise ValidationError("no MB-10 session linked yet")
        if session_data["stage"] != "provider_consensus_pending":
            return session_data

        mb10_session = self.research_center.session(session_data["mb10_session_public_id"])
        if not mb10_session.get("dataset_draft"):
            return session_data

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self._apply_transition(
                connection, session_row, "draft_ready", {"mb10_linked": True},
                "research_center_refreshed", "MB-10 session now has a dataset draft",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- link MB-11 (Dataset Evolution) -----------------------------------------

    def link_dataset_evolution_stage(self, session_public_id: str, *, mb11_session_public_id: str, admin_id: str) -> dict[str, Any]:
        del admin_id
        self.dataset_evolution.session(mb11_session_public_id)
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self._apply_transition(
                connection, session_row, "dataset_planned", {"mb11_linked": True},
                "dataset_evolution_linked", f"linked MB-11 evolution session {mb11_session_public_id}",
            )
            self.repository.update_session(connection, session_public_id, {"mb11_session_public_id": mb11_session_public_id})
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- RAG First Enforcement (reads an already-produced RAG report only) --------

    def run_rag_first_enforcement(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] not in {"dataset_planned", "rag_testing"}:
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dataset_planned' or 'rag_testing'")

        rag_report: dict[str, Any] | None = None
        admin_decision: str | None = None
        if session_data["mb11_session_public_id"]:
            mb11_session = self.dataset_evolution.session(session_data["mb11_session_public_id"])
            if mb11_session.get("rag_report"):
                rag_report = mb11_session["rag_report"]
                admin_decision = mb11_session.get("rag_admin_decision")
        if rag_report is None and session_data["mb06_session_public_id"]:
            mb06_session = self.learning_supervisor.session(session_data["mb06_session_public_id"])
            if mb06_session.get("rag_evaluation_report"):
                rag_report = mb06_session["rag_evaluation_report"]
                admin_decision = mb06_session.get("rag_decision")

        gate = check_rag_gate(rag_report=rag_report, admin_decision=admin_decision)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            fields: dict[str, Any] = {"rag_first_report_json": gate}
            self.repository.update_session(connection, session_public_id, fields)
            if gate["passed"] and session_row["stage"] != "rag_testing":
                self._apply_transition(
                    connection, session_row, "rag_testing", {"rag_passed": True},
                    "rag_gate_passed", "RAG First Enforcement passed",
                )
            elif not gate["passed"] and session_row["stage"] == "rag_testing":
                self._apply_transition(
                    connection, session_row, "dataset_planned", {"mb11_linked": True},
                    "rag_gate_failed_bounced_back", f"RAG gate failed: {gate['reasons']}",
                )
            else:
                self._event(
                    connection, session_row["id"], "rag_gate_checked", stage=session_row["stage"],
                    message=f"passed={gate['passed']}",
                )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- link MB-06 (Training Candidate) -----------------------------------------

    def link_training_stage(self, session_public_id: str, *, mb06_session_public_id: str, admin_id: str) -> dict[str, Any]:
        del admin_id
        self.learning_supervisor.session(mb06_session_public_id)
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self._apply_transition(
                connection, session_row, "training_candidate", {"mb06_linked": True},
                "training_linked", f"linked MB-06 learning session {mb06_session_public_id}",
            )
            self.repository.update_session(connection, session_public_id, {"mb06_session_public_id": mb06_session_public_id})
            return public_session_row(self.repository.session(connection, session_public_id))

    def refresh_training_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if not session_data["mb06_session_public_id"]:
            raise ValidationError("no MB-06 session linked yet")

        mb06_session = self.learning_supervisor.session(session_data["mb06_session_public_id"])
        evidence = {
            "mb06_linked": True,
            "mb06_job_running": bool(mb06_session.get("training_job_public_id")) and mb06_session["stage"] == "training_monitoring",
            "mb06_benchmark_ready": bool(mb06_session.get("benchmark_report")),
            "mb06_release_candidate_present": bool(mb06_session.get("release_candidate_core_model_version_public_id")),
            "mb06_accepted": mb06_session["stage"] == "closed" and mb06_session.get("status") == "accepted",
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            current_stage = session_row["stage"]
            for target in _TRAINING_ADVANCE_TARGETS:
                if stage_index(target) <= stage_index(current_stage):
                    continue
                dependency = check_dependencies(current_stage=current_stage, target_stage=target, evidence=evidence)
                if not dependency["allowed"]:
                    break
                current_stage = target
            if current_stage != session_row["stage"]:
                self.repository.update_session(connection, session_public_id, {"stage": current_stage})
                self._event(
                    connection, session_row["id"], "training_status_refreshed", stage=current_stage,
                    message=f"advanced to '{current_stage}' from real MB-06 session state",
                )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- Training Readiness Coordinator ------------------------------------------

    def generate_training_readiness_report(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)

        dataset_source_public_id = None
        mb05_training_status = None
        mb051_overall_score = None
        if session_data["mb11_session_public_id"]:
            mb11_session = self.dataset_evolution.session(session_data["mb11_session_public_id"])
            dataset_source_public_id = mb11_session["dataset_source_public_id"]
            mb05_training = self.dataset_intelligence.training(dataset_source_public_id)
            mb05_training_status = mb05_training["status"]
            mb051_report = self.advanced_dataset.report(dataset_source_public_id)
            mb051_overall_score = mb051_report["scores"]["overall"]["score"]

        mb06_quality_score = None
        if session_data["mb06_session_public_id"]:
            mb06_session = self.learning_supervisor.session(session_data["mb06_session_public_id"])
            comparison = mb06_session.get("comparison_report")
            if comparison:
                improvement = comparison.get("improvement_count", 0)
                regression = comparison.get("regression_count", 0)
                total = improvement + regression
                mb06_quality_score = round(improvement / total * 100, 1) if total else 50.0
            elif mb06_session.get("training_report"):
                job_status = mb06_session["training_report"].get("job_status")
                if job_status in {"completed", "completed_with_warnings"}:
                    mb06_quality_score = 70.0
                elif job_status == "failed":
                    mb06_quality_score = 20.0

        mb08_sessions = self.continuous_learning.list_sessions(limit=MAX_MB08_CYCLES)["items"]
        mb08_reports = [
            s["continuous_learning_report"] for s in mb08_sessions
            if s["stage"] == "closed" and s["continuous_learning_report"]
        ]
        mb08_failure_rates = [r["failure_rate"] for r in mb08_reports if r.get("failure_rate") is not None]
        mb08_average_failure_rate = round(sum(mb08_failure_rates) / len(mb08_failure_rates), 4) if mb08_failure_rates else None

        mb09_recurring_weak_domain_count = None
        if session_data["mb09_session_public_id"]:
            mb09_session = self.planning_center.session(session_data["mb09_session_public_id"])
            recurring = (mb09_session.get("knowledge_gap_evolution_report") or {}).get("recurring_weak_domains")
            if recurring is not None:
                mb09_recurring_weak_domain_count = len(recurring)

        mb10_quality_score = None
        if session_data["mb10_session_public_id"]:
            mb10_session = self.research_center.session(session_data["mb10_session_public_id"])
            quality_report = mb10_session.get("quality_report")
            if quality_report:
                mb10_quality_score = quality_report.get("overall_quality")

        mb11_predicted_quality_score = None
        if session_data["mb11_session_public_id"]:
            quality_evolution = mb11_session.get("quality_evolution")
            if quality_evolution:
                mb11_predicted_quality_score = quality_evolution.get("predicted_quality_score")

        readiness = coordinate_training_readiness(
            mb05_training_status=mb05_training_status, mb051_overall_score=mb051_overall_score,
            mb06_quality_score=mb06_quality_score, mb08_average_failure_rate=mb08_average_failure_rate,
            mb09_recurring_weak_domain_count=mb09_recurring_weak_domain_count,
            mb10_quality_score=mb10_quality_score, mb11_predicted_quality_score=mb11_predicted_quality_score,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"training_readiness_report_json": readiness})
            self._event(
                connection, session_row["id"], "training_readiness_generated", stage=session_row["stage"],
                message=f"unified readiness score {readiness['unified_readiness_score']} ({readiness['status']})",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- Knowledge Lifecycle Timeline -----------------------------------------------

    def generate_timeline(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        entries: list[dict[str, Any]] = []

        if session_data["mb09_session_public_id"]:
            for e in self.planning_center.events(session_data["mb09_session_public_id"])["items"]:
                entries.append({"phase": "mb09", "event_type": e["event_type"], "message": e["message"], "created_at": e["created_at"]})
        if session_data["mb10_session_public_id"]:
            for e in self.research_center.events(session_data["mb10_session_public_id"])["items"]:
                entries.append({"phase": "mb10", "event_type": e["event_type"], "message": e["message"], "created_at": e["created_at"]})
        if session_data["mb11_session_public_id"]:
            for e in self.dataset_evolution.events(session_data["mb11_session_public_id"])["items"]:
                entries.append({"phase": "mb11", "event_type": e["event_type"], "message": e["message"], "created_at": e["created_at"]})
        if session_data["mb06_session_public_id"]:
            for e in self.learning_supervisor.events(session_data["mb06_session_public_id"])["items"]:
                entries.append({"phase": "mb06", "event_type": e["event_type"], "message": e["message"], "created_at": e["created_at"]})

        timeline = build_timeline(entries=entries)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"lifecycle_timeline_json": timeline})
            self._event(
                connection, session_row["id"], "timeline_generated", stage=session_row["stage"],
                message=f"{timeline['event_count']} event(s) across linked phases",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- Improvement Predictor ----------------------------------------------------------

    def predict_improvement_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)

        mb11_simulation = None
        tamil_percent = None
        english_percent = None
        if session_data["mb11_session_public_id"]:
            mb11_session = self.dataset_evolution.session(session_data["mb11_session_public_id"])
            mb11_simulation = mb11_session.get("simulation_report")
            language_result = self.dataset_intelligence.language(mb11_session["dataset_source_public_id"])
            percentages = language_result.get("distribution_percentages", {})
            tamil_percent = percentages.get("tamil")
            english_percent = percentages.get("english")

        mb06_comparison = None
        if session_data["mb06_session_public_id"]:
            mb06_session = self.learning_supervisor.session(session_data["mb06_session_public_id"])
            mb06_comparison = mb06_session.get("comparison_report") or None

        prediction = predict_improvement(
            mb11_simulation=mb11_simulation, mb06_comparison=mb06_comparison,
            tamil_percent=tamil_percent, english_percent=english_percent,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"improvement_prediction_json": prediction})
            self._event(
                connection, session_row["id"], "improvement_predicted", stage=session_row["stage"],
                message=f"expected benchmark gain {prediction['expected_benchmark_gain']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- Global Recommendation Engine -------------------------------------------------

    def generate_recommendation(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if not session_data["training_readiness_report"]:
            raise ValidationError("generate the training readiness report before generating a recommendation")

        pipeline_manager_report = self._pipeline_manager_report(session_data)
        recommendation = recommend_next_action(
            current_stage=session_data["stage"], rag_gate=session_data["rag_first_report"] or None,
            training_readiness=session_data["training_readiness_report"],
            pipeline_completion_percent=pipeline_manager_report["completion_percent"],
            remaining_steps=pipeline_manager_report["remaining_steps"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"pipeline_manager_report_json": pipeline_manager_report, "recommendation_report_json": recommendation},
            )
            self._event(
                connection, session_row["id"], "recommendation_generated", stage=session_row["stage"],
                message=f"recommended: {recommendation['action']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def _pipeline_manager_report(self, session_data: dict[str, Any]) -> dict[str, Any]:
        mb10_session = self.research_center.session(session_data["mb10_session_public_id"]) if session_data["mb10_session_public_id"] else None
        return track_pipeline(
            public_chat_activity=bool(session_data["mb09_session_public_id"]),
            knowledge_gap_flagged=bool(session_data["mb09_session_public_id"]),
            mb09_linked=bool(session_data["mb09_session_public_id"]),
            mb10_consensus_done=bool(mb10_session and (mb10_session.get("consensus_report") or mb10_session.get("dataset_draft"))),
            mb11_linked=bool(session_data["mb11_session_public_id"]),
            rag_validated=bool(session_data["rag_first_report"] and session_data["rag_first_report"].get("passed")),
            mb06_linked=bool(session_data["mb06_session_public_id"]),
            release_candidate_present=session_data["stage"] in {"release_candidate", "completed"},
        )

    # -- Master Pipeline Report -----------------------------------------------------------

    def generate_master_report(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if not session_data["recommendation_report"]:
            raise ValidationError("generate the recommendation before generating the master report")

        dataset_health_score = None
        if session_data["mb11_session_public_id"]:
            mb11_session = self.dataset_evolution.session(session_data["mb11_session_public_id"])
            quality_evolution = mb11_session.get("quality_evolution")
            if quality_evolution:
                dataset_health_score = quality_evolution.get("predicted_quality_score")

        report = generate_master_report(
            session_public_id=session_public_id, topic=session_data["topic"], current_stage=session_data["stage"],
            pipeline_manager_report=session_data["pipeline_manager_report"],
            rag_first_report=session_data["rag_first_report"] or None,
            training_readiness_report=session_data["training_readiness_report"],
            recommendation_report=session_data["recommendation_report"], dataset_health_score=dataset_health_score,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"master_report_json": report})
            self._event(
                connection, session_row["id"], "master_report_generated", stage=session_row["stage"],
                message="master pipeline report ready for review",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- Admin Decision Center (always available, never executes anything) ----------------

    def admin_decide(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(DECISIONS)}")
        session_data = self.session(session_public_id)
        rag_gate_passed = session_data["rag_first_report"].get("passed") if session_data["rag_first_report"] else None
        evaluation = evaluate_decision(decision=decision, current_stage=session_data["stage"], rag_gate_passed=rag_gate_passed)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": evaluation["status"],
            }
            if evaluation["stage_override"]:
                fields["stage"] = evaluation["stage_override"]
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"admin_decided_{decision}", stage=fields.get("stage", session_row["stage"]),
                message=(
                    f"admin decided '{decision}' -- no training, dataset write, deployment, or RAG "
                    "change was performed by this service"
                ),
                metadata={"admin_id": admin_id, "warnings": evaluation["warnings"]},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainPipelineCoordinatorService"]
