"""MB-10: Brud Mini Brain AI Research & Knowledge Acquisition Center --
the orchestration layer for the research-request-to-training-gate
workflow described in the MB-10 task spec.

This service NEVER starts training, deploys a model, activates a
runtime, writes or approves a dataset record, or calls an external AI
provider automatically -- confirmed by structural/safety tests reading
this file's own source. It composes existing, unmodified systems
through their public methods only:

- `MiniBrainContinuousLearningCenterService` (MB-09) -- ONLY
  `.session()`, to read an already-completed Planning Center report
  (knowledge gap evolution, learning queue, roadmap, recommendation)
  as evidence for a new research request. MB-10 never creates or
  advances an MB-09 session.
- `MiniBrainDatasetIntelligenceService` (MB-05) -- ONLY `.training()`/
  `.analyze()`, to read an existing dataset's already-computed
  readiness summary for the Local Draft mode. MB-10 never writes a
  dataset record.
- `ExternalDatasetDuplicateService` (Phase 12) -- `.group_normalized_
  duplicates()`/`.find_conflicts()`, reused unchanged (exactly as
  MB-09 uses it) for comparing provider outputs an admin has already
  collected and pasted back in. MB-10 never calls an external AI
  provider itself -- confirmed by audit, no such integration exists
  anywhere in this codebase; Provider Request Packages are prepared
  for the admin to run externally, and results only enter this
  service through `ingest_provider_results_stage`, an explicit admin
  action.
- `RagSandboxAnswerService`/`RagSandboxEvaluationService`/
  `RagSandboxReportService` -- reused exactly as MB-06 already
  established: generation, evaluation, and report finalization only,
  on top of an already-built retrieval run. Corpus, index, query set,
  and retrieval remain admin-driven through the existing RAG Sandbox
  admin flow. This enforces the RAG FIRST POLICY: every dataset draft
  must pass through this exact chain before a training gate can open.
- `MiniBrainLearningSupervisorService` (MB-06) -- ONLY `.session()`,
  to read an already-completed Training Report (loss, accuracy,
  perplexity, checkpoint, benchmark, comparison, recommendation) after
  an admin has manually run training through MB-06's own UI. MB-10
  never submits, monitors, or advances an MB-06 session.
- The eleven pure `core_model.mini_brain.research_center` modules for
  every deterministic decision (request building, provider selection,
  citation/evidence analysis, duplicate/conflict resolution, consensus,
  quality scoring, draft assembly, recommendation, report assembly).

There is no separate `research_report_json` column: `generate_report`
re-derives the full admin-facing document on demand from fields
already persisted on the session, since `research_report_generator` is
pure assembly with nothing new to store. `training_gate_report_json`
similarly carries the eligibility check (RAG FIRST POLICY: approve the
draft, then approve the RAG report, before this can ever say
`eligible`) and, once an admin has separately run MB-06, an optional
`mb06_analysis` key added by `analyze_training_report` -- never a
second column, since it is the same JSON field's natural extension
from "is this cycle allowed to reach training" to "what did training
actually produce".

Every irreversible step (RAG Sandbox generation, training-gate
eligibility) requires an explicit prior admin decision recorded on the
session; nothing here proceeds automatically past a decision gate, and
nothing here ever calls the Training Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.mini_brain_research_center import (
    MiniBrainResearchCenterRepository,
    public_memory_row,
    public_provider_row,
    public_session_row,
)
from backend.services.dataset_service import DatasetService
from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService
from backend.services.mini_brain_continuous_learning_center_service import (
    MiniBrainContinuousLearningCenterService,
)
from backend.services.mini_brain_dataset_intelligence_service import (
    MiniBrainDatasetIntelligenceService,
)
from backend.services.mini_brain_learning_supervisor_service import (
    MiniBrainLearningSupervisorService,
)
from backend.services.rag_sandbox_answer_service import RagSandboxAnswerService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from backend.services.rag_sandbox_evaluation_service import RagSandboxEvaluationService
from backend.services.rag_sandbox_report_service import RagSandboxReportService
from core_model.mini_brain.research_center.citation_analyzer import analyze_citations
from core_model.mini_brain.research_center.conflict_resolver import resolve_conflicts
from core_model.mini_brain.research_center.dataset_draft_builder import build_dataset_draft
from core_model.mini_brain.research_center.duplicate_resolver import resolve_duplicates
from core_model.mini_brain.research_center.evidence_validator import validate_evidence
from core_model.mini_brain.research_center.provider_consensus_engine import build_consensus
from core_model.mini_brain.research_center.provider_registry import select_providers
from core_model.mini_brain.research_center.research_quality_engine import (
    score_overall,
    score_provider,
)
from core_model.mini_brain.research_center.research_recommendation_engine import (
    recommend_next_step,
)
from core_model.mini_brain.research_center.research_report_generator import (
    generate_research_report,
)
from core_model.mini_brain.research_center.research_request_builder import build_research_request

MODE_VALUES = {"local_draft", "multi_provider"}
DRAFT_ADMIN_DECISIONS = {
    "reject", "edit", "accept_draft", "request_more_research", "request_different_providers",
    "request_local_draft", "send_to_rag", "archive",
}
DRAFT_STATUS_MAP = {
    "reject": "admin_rejected", "edit": "admin_edited", "accept_draft": "admin_accepted_draft",
    "request_more_research": "admin_requested_more_research",
    "request_different_providers": "admin_requested_different_providers",
    "request_local_draft": "admin_requested_local_draft", "send_to_rag": "admin_sent_to_rag",
    "archive": "admin_archived",
}
RAG_ADMIN_DECISIONS = {"approve", "reject"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainResearchCenterService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainResearchCenterRepository(settings.resolved_database_path)

        dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        self.dataset_intelligence = MiniBrainDatasetIntelligenceService(dataset_service)
        self.planning_center = MiniBrainContinuousLearningCenterService(settings)
        self.learning_supervisor = MiniBrainLearningSupervisorService(settings)
        self.duplicate_service = ExternalDatasetDuplicateService()

        self.rag_answer = RagSandboxAnswerService(settings)
        self.rag_evaluation = RagSandboxEvaluationService(settings)
        self.rag_report = RagSandboxReportService(settings)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, research_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, research_session_id=research_session_id, event_type=event_type,
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
                connection, research_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    # -- provider registry (real, admin-extensible) -------------------------

    def list_providers(self, *, status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_providers(connection, status=status)
        return {"items": [public_provider_row(row) for row in rows]}

    def add_provider(
        self, *, provider_key: str, display_name: str, requires_external_call: bool,
        description: str, admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            if self.repository.get_provider(connection, provider_key) is not None:
                raise ValidationError(f"provider already registered: {provider_key}")
            self.repository.add_provider(
                connection, provider_key=provider_key, display_name=display_name,
                requires_external_call=requires_external_call, description=description,
                created_by_admin_public_id=admin_id,
            )
            return public_provider_row(self.repository.get_provider(connection, provider_key))

    def set_provider_status(self, provider_key: str, *, status: str, admin_id: str) -> dict[str, Any]:
        del admin_id
        if status not in {"active", "inactive"}:
            raise ValidationError("status must be 'active' or 'inactive'")
        with self.repository.transaction() as connection:
            return public_provider_row(
                self.repository.set_provider_status(connection, provider_key, status=status)
            )

    # -- research memory (permanent, insert-only) ------------------------------

    def record_memory(self, session_public_id: str, *, notes: str = "", admin_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        training_gate_report = session_data["training_gate_report"] or {}
        mb06_analysis = training_gate_report.get("mb06_analysis") or {}
        admin_decision = session_data["rag_admin_decision"] or session_data["draft_admin_decision"]
        with self.repository.transaction() as connection:
            public_id = self.repository.record_memory(
                connection, research_session_public_id=session_public_id,
                provider_history=session_data["provider_outputs"],
                consensus_report=session_data["consensus_report"] or {},
                dataset_evolution=session_data["dataset_draft"] or {},
                training_results=mb06_analysis.get("training_report") or {},
                benchmark_results=mb06_analysis.get("benchmark_report") or {},
                admin_decision=admin_decision, notes=notes, recorded_by_admin_public_id=admin_id,
            )
            return public_memory_row(self.repository.get_memory(connection, public_id))

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    def get_memory(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_memory_row(self.repository.get_memory(connection, public_id))

    # -- stage 1: session + research request -------------------------------

    def create_session(self, *, topic: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(connection, topic=topic, created_by_admin_public_id=admin_id)
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="research_request",
                message=f"research session created for topic '{topic}'",
            )
            return public_session_row(self.repository.session(connection, public_id))

    def prepare_research_request_stage(
        self, session_public_id: str, *, planning_center_session_public_id: str | None = None,
        priority: str | None = None, admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "research_request":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'research_request'")

        evidence: dict[str, Any] = {}
        if planning_center_session_public_id is not None:
            planning_session = self.planning_center.session(planning_center_session_public_id)
            evidence = {
                "knowledge_gap_evolution": planning_session["knowledge_gap_evolution_report"],
                "learning_queue": planning_session["learning_queue_report"],
                "roadmap": planning_session["roadmap_report"],
                "recommendation": planning_session["recommendation_report"],
            }

        report = build_research_request(topic=session_data["topic"], evidence=evidence, priority=priority)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"research_request_json": report, "stage": "mode_selection"},
            )
            self._event(
                connection, session_row["id"], "research_request_prepared", stage="research_request",
                message=f"{len(report['questions'])} question(s) prepared",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 2: mode selection ---------------------------------------------

    def select_mode_stage(
        self, session_public_id: str, *, mode: str, requested_provider_keys: list[str] | None = None,
        admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        if mode not in MODE_VALUES:
            raise ValidationError(f"mode must be one of {sorted(MODE_VALUES)}")
        session_data = self.session(session_public_id)
        if session_data["stage"] != "mode_selection":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'mode_selection'")

        fields: dict[str, Any] = {"mode": mode}
        if mode == "local_draft":
            fields["selected_providers_json"] = []
            fields["stage"] = "local_draft"
            selection_message = "local draft mode selected -- no external provider will be contacted"
        else:
            if not requested_provider_keys:
                raise ValidationError("multi_provider mode requires at least one requested_provider_keys entry")
            with self.repository.transaction() as connection:
                registered = [public_provider_row(row) for row in self.repository.list_providers(connection)]
            selection = select_providers(
                requested_provider_keys=requested_provider_keys, registered_providers=registered
            )
            fields["selected_providers_json"] = selection["selected_providers"]
            if selection["valid"]:
                fields["stage"] = "provider_request"
            selection_message = (
                f"selected {len(selection['selected_providers'])} provider(s); "
                f"unknown/inactive: {selection['unknown_provider_keys']}"
            )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], "mode_selected", stage="mode_selection", message=selection_message,
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- Mode 1: local draft -----------------------------------------------------

    def build_local_draft_stage(
        self, session_public_id: str, *, existing_dataset_source_public_id: str | None = None, admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "local_draft":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'local_draft'")

        existing_dataset_context = None
        if existing_dataset_source_public_id is not None:
            training = self.dataset_intelligence.training(existing_dataset_source_public_id)
            analysis = self.dataset_intelligence.analyze(existing_dataset_source_public_id)
            existing_dataset_context = {
                "existing_dataset_source_public_id": existing_dataset_source_public_id,
                "status": training["status"], "clean_ratio": training["clean_ratio"],
                "record_count": analysis["record_count"],
            }

        report = {
            "topic": session_data["topic"], "research_request": session_data["research_request"],
            "existing_dataset_context": existing_dataset_context, "status": "prepared",
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"local_draft_report_json": report, "stage": "dataset_draft"},
            )
            self._event(
                connection, session_row["id"], "local_draft_built", stage="local_draft",
                message="local draft prepared from Mini Brain's own existing evidence -- no external provider used",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- Mode 2: multi-provider consensus -----------------------------------------

    def prepare_provider_request_package_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "provider_request":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'provider_request'")

        package = {
            "topic": session_data["topic"], "questions": session_data["research_request"].get("questions", []),
            "providers": [p["provider_key"] for p in session_data["selected_providers"]],
            "status": "prepared_for_external_research",
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"provider_request_json": package, "stage": "provider_consensus"},
            )
            self._event(
                connection, session_row["id"], "provider_request_package_prepared", stage="provider_request",
                message=(
                    f"package ready for {len(package['providers'])} provider(s) -- "
                    "admin must run these externally and paste results back"
                ),
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def ingest_provider_results_stage(
        self, session_public_id: str, *, provider_outputs: list[dict[str, str]], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "provider_consensus":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'provider_consensus'")
        if not provider_outputs:
            raise ValidationError("provider_outputs must not be empty")

        topic = session_data["topic"]
        per_provider_signals = []
        provider_scores = []
        for output in provider_outputs:
            citation = analyze_citations(text=output["output_text"])
            evidence = validate_evidence(text=output["output_text"], citation_marker_count=citation["total_citation_markers"])
            score = score_provider(provider=output["provider"], evidence_result=evidence, citation_result=citation)
            per_provider_signals.append({"provider": output["provider"], "citation": citation, "evidence": evidence})
            provider_scores.append(score)

        records = [
            {
                "public_id": output["provider"],
                "normalized_content": " ".join(output["output_text"].strip().lower().split()),
                "structured_payload": {"topic": topic, "output_text": output["output_text"]},
            }
            for output in provider_outputs
        ]
        duplicate_groups = self.duplicate_service.group_normalized_duplicates(records)
        conflict_groups = self.duplicate_service.find_conflicts(records, key_field="topic", value_field="output_text")

        duplicate_resolution = resolve_duplicates(duplicate_groups=duplicate_groups, provider_count=len(provider_outputs))
        conflict_resolution = resolve_conflicts(conflict_groups=conflict_groups, provider_count=len(provider_outputs))
        consensus = build_consensus(
            provider_outputs=provider_outputs, duplicate_resolution=duplicate_resolution,
            conflict_resolution=conflict_resolution,
        )
        overall_quality = score_overall(
            provider_scores=provider_scores, agreement_score=consensus["agreement_score"],
            conflict_score=conflict_resolution["conflict_score"], duplicate_score=duplicate_resolution["duplicate_score"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "provider_outputs_json": provider_outputs, "consensus_report_json": consensus,
                    "evidence_report_json": {"per_provider": per_provider_signals},
                    "quality_report_json": overall_quality, "stage": "dataset_draft",
                },
            )
            self._event(
                connection, session_row["id"], "provider_results_ingested", stage="provider_consensus",
                message=f"consensus verdict: {consensus['verdict']}, overall quality: {overall_quality['overall_quality']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: dataset draft (both modes converge here) ---------------------------

    def build_dataset_draft_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "dataset_draft":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dataset_draft'")

        mode = session_data["mode"]
        if mode == "multi_provider":
            quality_report = session_data["quality_report"]
            consensus_report = session_data["consensus_report"]
            draft = build_dataset_draft(
                topic=session_data["topic"], mode=mode, quality_report=quality_report,
                traceable_sources=consensus_report.get("traceable_outputs", []),
            )
            recommendation = recommend_next_step(
                overall_quality=quality_report["overall_quality"],
                has_unresolved_conflicts=consensus_report["conflict_summary"]["has_unresolved_conflicts"],
                provider_count=consensus_report["provider_count"],
            )
        else:
            draft = build_dataset_draft(topic=session_data["topic"], mode=mode, quality_report=None, traceable_sources=[])
            recommendation = {
                "recommendation": None,
                "why": (
                    "local draft mode has no external provider text to score -- the Research Quality "
                    "Score only applies to Multi-Provider Consensus mode; the admin reviews this draft on its own merits"
                ),
                "evidence": {},
            }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "dataset_draft_json": draft, "recommendation_report_json": recommendation,
                    "stage": "awaiting_draft_review",
                },
            )
            self._event(
                connection, session_row["id"], "dataset_draft_built", stage="dataset_draft",
                message=f"draft prepared for '{session_data['topic']}' (mode={mode}) -- verified=False, needs admin review",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- admin review of the dataset draft --------------------------------------

    def admin_review_draft(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in DRAFT_ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(DRAFT_ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_draft_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_draft_review'")
            if decision == "send_to_rag" and session_row["draft_admin_decision"] != "accept_draft":
                raise ValidationError("the draft must be accepted (accept_draft) before it can be sent to RAG Sandbox")

            fields: dict[str, Any] = {
                "draft_admin_decision": decision, "draft_admin_decided_by": admin_id, "draft_admin_decided_at": _now(),
                "status": DRAFT_STATUS_MAP[decision],
            }
            if decision == "send_to_rag":
                fields["stage"] = "rag_evaluation"
            elif decision != "accept_draft":
                fields["stage"] = "closed"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"draft_review_{decision}", stage="awaiting_draft_review",
                message=(
                    f"admin decided '{decision}' on the dataset draft -- no dataset was written or approved by "
                    "this service; Dataset Studio remains the only place that happens"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- RAG FIRST POLICY: RAG Sandbox evaluation (MB-06's exact pattern) -----------

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
            }
            if decision == "approve":
                fields["status"] = "rag_admin_approved"
                fields["stage"] = "training_gate"
            else:
                fields["status"] = "rag_admin_rejected"
                fields["stage"] = "closed"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"rag_review_{decision}d", stage="awaiting_rag_review",
                message=f"admin {decision}d the RAG evaluation report", metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- training gate: eligibility check only, never a training trigger ------------

    def check_training_gate_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "training_gate":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'training_gate'")

        draft_ok = session_data["draft_admin_decision"] in {"accept_draft", "send_to_rag"}
        rag_ok = session_data["rag_admin_decision"] == "approve"
        eligible = draft_ok and rag_ok
        reasons = []
        if not draft_ok:
            reasons.append("dataset draft was never accepted by an admin")
        if not rag_ok:
            reasons.append("RAG evaluation report was never approved by an admin")
        if eligible:
            reasons.append("admin approved both the dataset draft and the RAG evaluation report")

        report = {
            "eligible": eligible, "draft_admin_decision": session_data["draft_admin_decision"],
            "rag_admin_decision": session_data["rag_admin_decision"], "reasons": reasons, "mb06_analysis": None,
            "disclosure": (
                "this is an eligibility check only -- it never starts training; an admin must submit this "
                "dataset to the Learning Supervisor (MB-06) manually through MB-06's own UI"
            ),
        }

        fields: dict[str, Any] = {"training_gate_report_json": report}
        if eligible:
            fields["status"] = "training_eligible"
            fields["stage"] = "closed"
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], "training_gate_checked", stage="training_gate",
                message=f"eligible={eligible}", metadata={"reasons": reasons},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def analyze_training_report(
        self, session_public_id: str, *, learning_supervisor_session_public_id: str, admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if not session_data["training_gate_report"] or not session_data["training_gate_report"].get("eligible"):
            raise ValidationError("the training gate must have already reported eligible=True for this session")

        mb06_session = self.learning_supervisor.session(learning_supervisor_session_public_id)
        mb06_analysis = {
            "learning_supervisor_session_public_id": learning_supervisor_session_public_id,
            "training_report": mb06_session["training_report"],
            "benchmark_report": mb06_session["benchmark_report"],
            "comparison_report": mb06_session["comparison_report"],
            "recommendation_report": mb06_session["recommendation_report"],
        }
        updated_report = dict(session_data["training_gate_report"])
        updated_report["mb06_analysis"] = mb06_analysis

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"training_gate_report_json": updated_report})
            self._event(
                connection, session_row["id"], "training_report_analyzed", stage="training_gate",
                message=f"analyzed MB-06 session {learning_supervisor_session_public_id} (read-only)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- read-only report assembly (no separate storage) ---------------------------

    def generate_report(self, session_public_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        return generate_research_report(
            session_public_id=session_public_id, research_request=session_data["research_request"],
            mode=session_data["mode"], selected_providers=session_data["selected_providers"],
            consensus_report=session_data["consensus_report"] or None,
            quality_report=session_data["quality_report"] or None,
            dataset_draft=session_data["dataset_draft"] or None,
            recommendation=session_data["recommendation_report"] or None,
            rag_report=session_data["rag_report"] or None,
        )


__all__ = ["MiniBrainResearchCenterService"]
