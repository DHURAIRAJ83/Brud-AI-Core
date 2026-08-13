"""MB-11: Brud Mini Brain Autonomous Dataset Evolution & Knowledge
Factory -- the orchestration layer for the knowledge-evolution-to-
recommendation workflow described in the MB-11 task spec.

This service NEVER writes a dataset record, NEVER starts training,
NEVER deploys a model, NEVER activates a runtime, and NEVER modifies
RAG -- confirmed by structural/safety tests reading this file's own
source. It composes existing, unmodified systems through their public
methods only:

- `MiniBrainDatasetIntelligenceService` (MB-05) -- ONLY `.training()`,
  `.analyze()`, `.language()`, to read the current dataset's own
  already-computed readiness/composition summary. MB-11 never writes a
  dataset record.
- `MiniBrainAdvancedDatasetService` (MB-05.1) -- ONLY `.report()`,
  which already composes conflicts/bias/coverage/difficulty/
  curriculum/knowledge_gaps/risk/graph/priorities/scores in one real,
  unmodified call. MB-11 never re-derives any of those signals itself,
  and never re-scans a single dataset record.
- `MiniBrainContinuousLearningService` (MB-08) -- ONLY
  `.list_sessions()`, to read already-closed Continuous Learning
  Reports (weak/strong areas, failure/hallucination rates, missing
  domains). MB-11 never creates or advances an MB-08 session.
- `MiniBrainContinuousLearningCenterService` (MB-09) -- ONLY
  `.list_sessions()`, to read already-computed recurring-weak-domain
  evolution. MB-11 never creates or advances an MB-09 session.
- `MiniBrainResearchCenterService` (MB-10) -- ONLY `.list_sessions()`,
  to read already-collected research drafts and provider consensus
  verdicts. MB-11 never creates or advances an MB-10 session.
- `ExternalDatasetDuplicateService` (Phase 12) -- `.group_normalized_
  duplicates()`/`.find_conflicts()`, reused unchanged (exactly as
  MB-09/MB-10 use it) over a normalized list of "knowledge claims"
  this service assembles from MB-08's and MB-09's weak/strong-domain
  signals -- never over raw dataset records, since MB-05.1's own
  `.report()` already covers duplicate/conflict detection on those.
- `RagSandboxAnswerService`/`RagSandboxEvaluationService`/
  `RagSandboxReportService` -- reused exactly as MB-06/MB-10 already
  established: generation, evaluation, and report finalization only,
  on top of an already-built retrieval run. Corpus, index, query set,
  and retrieval remain admin-driven through the existing RAG Sandbox
  admin flow.
- The twelve pure `core_model.mini_brain.dataset_evolution` modules for
  every deterministic decision (evolution analysis, dependency
  graphing, coverage classification, expansion/version/factory/
  synthetic-dataset planning, quality-evolution prediction, knowledge-
  relationship building, simulation, recommendation, report assembly).

Every irreversible step (RAG Sandbox generation) requires an explicit
prior admin decision recorded on the session; nothing here proceeds
automatically past a decision gate, and nothing here ever calls the
Training Engine, Runtime, Release Pipeline, or a Dataset Studio
mutation API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.mini_brain_dataset_evolution import (
    MiniBrainDatasetEvolutionRepository,
    public_session_row,
)
from backend.services.dataset_service import DatasetService
from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService
from backend.services.mini_brain_advanced_dataset_service import MiniBrainAdvancedDatasetService
from backend.services.mini_brain_continuous_learning_center_service import (
    MiniBrainContinuousLearningCenterService,
)
from backend.services.mini_brain_continuous_learning_service import (
    MiniBrainContinuousLearningService,
)
from backend.services.mini_brain_dataset_intelligence_service import (
    MiniBrainDatasetIntelligenceService,
)
from backend.services.mini_brain_research_center_service import MiniBrainResearchCenterService
from backend.services.rag_sandbox_answer_service import RagSandboxAnswerService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from backend.services.rag_sandbox_evaluation_service import RagSandboxEvaluationService
from backend.services.rag_sandbox_report_service import RagSandboxReportService
from core_model.mini_brain.dataset_evolution.coverage_analyzer import analyze_coverage_summary
from core_model.mini_brain.dataset_evolution.dependency_graph import analyze_dependencies
from core_model.mini_brain.dataset_evolution.evolution_analyzer import analyze_evolution
from core_model.mini_brain.dataset_evolution.evolution_report_generator import (
    generate_evolution_report,
)
from core_model.mini_brain.dataset_evolution.evolution_simulator import simulate_evolution
from core_model.mini_brain.dataset_evolution.expansion_planner import plan_expansion
from core_model.mini_brain.dataset_evolution.knowledge_factory_planner import (
    plan_knowledge_factory,
)
from core_model.mini_brain.dataset_evolution.quality_evolution import predict_quality_evolution
from core_model.mini_brain.dataset_evolution.recommendation_engine import recommend_evolution
from core_model.mini_brain.dataset_evolution.relationship_builder import build_relationships
from core_model.mini_brain.dataset_evolution.synthetic_dataset_planner import (
    plan_synthetic_dataset,
)
from core_model.mini_brain.dataset_evolution.version_planner import plan_version

MAX_CYCLES_PER_SOURCE = 10
ADMIN_DECISIONS = {
    "approve_evolution", "edit_plan", "research_more", "request_provider_consensus",
    "expand_dataset", "split_dataset", "merge_dataset", "archive_plan", "reject", "send_to_rag",
}
ADMIN_STATUS_MAP = {
    "approve_evolution": "admin_approved_evolution", "edit_plan": "admin_edited_plan",
    "research_more": "admin_requested_more_research",
    "request_provider_consensus": "admin_requested_provider_consensus",
    "expand_dataset": "admin_expanded_dataset", "split_dataset": "admin_split_dataset",
    "merge_dataset": "admin_merged_dataset", "archive_plan": "admin_archived_plan",
    "reject": "admin_rejected", "send_to_rag": "admin_sent_to_rag",
}
RAG_ADMIN_DECISIONS = {"approve", "reject"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainDatasetEvolutionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainDatasetEvolutionRepository(settings.resolved_database_path)

        dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        self.dataset_intelligence = MiniBrainDatasetIntelligenceService(dataset_service)
        self.advanced_dataset = MiniBrainAdvancedDatasetService(dataset_service, self.dataset_intelligence)
        self.continuous_learning = MiniBrainContinuousLearningService(settings)
        self.planning_center = MiniBrainContinuousLearningCenterService(settings)
        self.research_center = MiniBrainResearchCenterService(settings)
        self.duplicate_service = ExternalDatasetDuplicateService()

        self.rag_answer = RagSandboxAnswerService(settings)
        self.rag_evaluation = RagSandboxEvaluationService(settings)
        self.rag_report = RagSandboxReportService(settings)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, evolution_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, evolution_session_id=evolution_session_id, event_type=event_type,
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
                connection, evolution_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def _knowledge_claims(self, mb08_reports: list[dict[str, Any]], mb09_sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        for i, report in enumerate(mb08_reports):
            for domain in report.get("weak_areas") or []:
                claims.append({
                    "public_id": f"mb08:weak:{i}:{domain}", "normalized_content": domain.strip().lower(),
                    "structured_payload": {"domain": domain, "status": "weak"},
                })
            for domain in report.get("strong_areas") or []:
                claims.append({
                    "public_id": f"mb08:strong:{i}:{domain}", "normalized_content": domain.strip().lower(),
                    "structured_payload": {"domain": domain, "status": "strong"},
                })
        for i, session_data in enumerate(mb09_sessions):
            recurring = (session_data.get("knowledge_gap_evolution_report") or {}).get("recurring_weak_domains") or []
            for entry in recurring:
                claims.append({
                    "public_id": f"mb09:weak:{i}:{entry['domain']}", "normalized_content": entry["domain"].strip().lower(),
                    "structured_payload": {"domain": entry["domain"], "status": "weak"},
                })
        return claims

    # -- stage 1: session creation --------------------------------------

    def create_session(self, *, dataset_source_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, dataset_source_public_id=dataset_source_public_id, created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="knowledge_evolution",
                message=f"dataset evolution cycle created for dataset source {dataset_source_public_id}",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage: knowledge evolution (analysis + graph + coverage + relationships) ---

    def run_knowledge_evolution_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "knowledge_evolution":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'knowledge_evolution'")

        source_id = session_data["dataset_source_public_id"]
        dataset_training = self.dataset_intelligence.training(source_id)
        dataset_analysis = self.dataset_intelligence.analyze(source_id)
        language_result = self.dataset_intelligence.language(source_id)
        advanced_report = self.advanced_dataset.report(source_id)

        mb08_sessions = self.continuous_learning.list_sessions(limit=MAX_CYCLES_PER_SOURCE)["items"]
        mb08_reports = [
            s["continuous_learning_report"] for s in mb08_sessions
            if s["stage"] == "closed" and s["continuous_learning_report"]
        ]
        mb09_sessions = self.planning_center.list_sessions(limit=MAX_CYCLES_PER_SOURCE)["items"]
        mb10_sessions = self.research_center.list_sessions(limit=MAX_CYCLES_PER_SOURCE)["items"]

        analysis = analyze_evolution(
            dataset_training=dataset_training, dataset_analysis=dataset_analysis, advanced_report=advanced_report,
            mb08_reports=mb08_reports, mb09_sessions=mb09_sessions, mb10_sessions=mb10_sessions,
        )
        deps = analyze_dependencies(graph=advanced_report["graph"])
        coverage = analyze_coverage_summary(
            domain_coverage=advanced_report["coverage"],
            language_distribution_percentages=language_result["distribution_percentages"],
            difficulty_distribution=advanced_report["difficulty"]["distribution"],
            record_type_counts=dataset_analysis["by_record_type"],
            curriculum_verdict_counts=advanced_report["curriculum"]["verdict_counts"],
        )

        claims = self._knowledge_claims(mb08_reports, mb09_sessions)
        duplicate_groups = self.duplicate_service.group_normalized_duplicates(claims)
        conflict_groups = self.duplicate_service.find_conflicts(claims, key_field="domain", value_field="status")
        research_backed_domains = [
            s["dataset_draft"]["topic"] for s in mb10_sessions if (s.get("dataset_draft") or {}).get("topic")
        ]
        relationships = build_relationships(
            duplicate_groups=duplicate_groups, conflict_groups=conflict_groups,
            weak_domains=analysis["weak_domains"], covered_domains=list(coverage["by_domain"].keys()),
            research_backed_domains=research_backed_domains,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "evolution_analysis_json": analysis, "dependency_graph_json": deps,
                    "coverage_report_json": coverage, "relationship_report_json": relationships,
                    "stage": "dataset_evolution",
                },
            )
            self._event(
                connection, session_row["id"], "knowledge_evolution_analyzed", stage="knowledge_evolution",
                message=f"evolution pressure {analysis['evolution_pressure']}, {len(analysis['weak_domains'])} weak domain(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: dataset evolution (expansion + version + factory + synthetic + quality) --

    def run_dataset_evolution_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "dataset_evolution":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dataset_evolution'")

        source_id = session_data["dataset_source_public_id"]
        dataset_training = self.dataset_intelligence.training(source_id)
        analysis = session_data["evolution_analysis"]
        coverage = session_data["coverage_report"]
        relationships = session_data["relationship_report"]

        expansion = plan_expansion(
            dataset_status=analysis["dataset_status"], duplicate_ratio=dataset_training["duplicate_ratio"],
            record_count=analysis["dataset_record_count"], coverage_summary=coverage,
            relationship_report=relationships, evolution_pressure=analysis["evolution_pressure"],
        )
        version = plan_version(current_record_count=analysis["dataset_record_count"], expansion_action=expansion["action"])
        factory = plan_knowledge_factory(
            coverage_summary=coverage, weak_domains=analysis["weak_domains"], missing_domains=analysis["missing_domains"],
            advanced_overall_score=analysis["advanced_overall_score"],
        )
        target_domain = analysis["weak_domains"][0] if analysis["weak_domains"] else "General"
        synthetic = plan_synthetic_dataset(
            target_domain=target_domain, content_type=factory["recommendations"][0]["content_type"],
            predicted_record_count=version["predicted_record_count"],
        )
        quality = predict_quality_evolution(
            current_advanced_score=analysis["advanced_overall_score"], expansion_action=expansion["action"],
            critical_gap_count=coverage["critical_gap_count"], needs_expansion_count=coverage["needs_expansion_count"],
            knowledge_factory_content_types=[r["content_type"] for r in factory["recommendations"]],
            growth_percent=version["growth_percent"], cycles_compared=analysis["cycles_compared"]["mb08"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "expansion_plan_json": expansion, "version_plan_json": version,
                    "knowledge_factory_plan_json": factory, "synthetic_dataset_plan_json": synthetic,
                    "quality_evolution_json": quality, "stage": "evolution_simulation",
                },
            )
            self._event(
                connection, session_row["id"], "dataset_evolution_planned", stage="dataset_evolution",
                message=f"expansion action: {expansion['action']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: evolution simulation ----------------------------------------

    def run_evolution_simulation_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "evolution_simulation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'evolution_simulation'")

        simulation = simulate_evolution(
            quality_evolution=session_data["quality_evolution"], expansion_action=session_data["expansion_plan"]["action"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"simulation_report_json": simulation, "stage": "recommendation"},
            )
            self._event(
                connection, session_row["id"], "evolution_simulated", stage="evolution_simulation",
                message=f"expected improvement {simulation['expected_improvement']}, confidence {simulation['confidence']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: recommendation + report --------------------------------------

    def generate_recommendation_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "recommendation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'recommendation'")

        recommendation = recommend_evolution(
            evolution_pressure=session_data["evolution_analysis"]["evolution_pressure"],
            expansion_action=session_data["expansion_plan"]["action"], coverage_summary=session_data["coverage_report"],
            relationship_report=session_data["relationship_report"], simulation=session_data["simulation_report"],
            risk=session_data["quality_evolution"]["risk"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"recommendation_report_json": recommendation})
            self._event(
                connection, session_row["id"], "recommendation_generated", stage="recommendation",
                message=f"recommended: {recommendation['recommendation']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def generate_report(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "recommendation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'recommendation'")
        if not session_data["recommendation_report"]:
            raise ValidationError("generate the recommendation before generating the report")

        report = generate_evolution_report(
            session_public_id=session_public_id, dataset_source_public_id=session_data["dataset_source_public_id"],
            evolution_analysis=session_data["evolution_analysis"], coverage_report=session_data["coverage_report"],
            dependency_graph=session_data["dependency_graph"], relationship_report=session_data["relationship_report"],
            expansion_plan=session_data["expansion_plan"], version_plan=session_data["version_plan"],
            knowledge_factory_plan=session_data["knowledge_factory_plan"],
            synthetic_dataset_plan=session_data["synthetic_dataset_plan"],
            quality_evolution=session_data["quality_evolution"], simulation_report=session_data["simulation_report"],
            recommendation_report=session_data["recommendation_report"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"evolution_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "evolution_report_generated", stage="recommendation",
                message="admin evolution report ready for review",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- admin review of the evolution report --------------------------------------

    def admin_review_evolution(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")
            if decision == "send_to_rag" and session_row["draft_admin_decision"] != "approve_evolution":
                raise ValidationError("the evolution plan must be approved (approve_evolution) before it can be sent to RAG Sandbox")

            fields: dict[str, Any] = {
                "draft_admin_decision": decision, "draft_admin_decided_by": admin_id, "draft_admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision],
            }
            if decision == "send_to_rag":
                fields["stage"] = "rag_evaluation"
            elif decision != "approve_evolution":
                fields["stage"] = "closed"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"evolution_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' on the evolution report -- no dataset was written, merged, "
                    "split, or approved by this service; Dataset Studio remains the only place that happens"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- RAG Sandbox evaluation (MB-06/MB-10's exact established pattern) -----------

    def run_rag_evaluation_stage(
        self, session_public_id: str, *, rag_sandbox_experiment_public_id: str,
        retrieval_run_public_id: str, generation_assignment_public_id: str, admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "rag_evaluation":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'rag_evaluation'")
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

    def finalize_rag_evaluation_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if not session_row["rag_sandbox_experiment_public_id"]:
                raise ValidationError("no RAG Sandbox experiment has been evaluated for this session yet")
            session_row_id = session_row["id"]
            experiment_public_id = session_row["rag_sandbox_experiment_public_id"]
        return self._finalize_rag_report(session_public_id, session_row_id, admin_id, experiment_public_id=experiment_public_id)

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
                    {"rag_report_json": report, "stage": "awaiting_rag_review"},
                )
                self._event(
                    connection, session_row_id, "rag_report_finalized", stage="rag_evaluation",
                    message=f"RAG production readiness: {report.get('production_rag_readiness')}",
                )
        except RagSandboxError as exc:
            partial = {
                "status": "pending_human_review", "reason": str(exc),
                "note": (
                    "generation and automated evaluation are complete; an admin must review every "
                    "tested query in the existing RAG Sandbox UI before the report can finalize"
                ),
            }
            with self.repository.transaction() as connection:
                self.repository.update_session(connection, session_public_id, {"rag_report_json": partial})
                self._event(
                    connection, session_row_id, "rag_report_pending_human_review", stage="rag_evaluation",
                    message=str(exc),
                )
        return self.session(session_public_id)

    # -- admin review of the RAG report ------------------------------------------

    def admin_review_rag(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in RAG_ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(RAG_ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_rag_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_rag_review'")
            fields: dict[str, Any] = {
                "rag_admin_decision": decision, "rag_admin_decided_by": admin_id, "rag_admin_decided_at": _now(),
                "status": "rag_admin_approved" if decision == "approve" else "rag_admin_rejected",
                "stage": "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"rag_review_{decision}d", stage="awaiting_rag_review",
                message=(
                    f"admin {decision}d the RAG evaluation report -- an admin must submit this to MB-06 "
                    "Learning Supervisor manually through MB-06's own UI; this service never does so"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainDatasetEvolutionService"]
