"""MB-09: Brud Mini Brain Continuous Learning Center -- the
orchestration layer for the planning-and-recommendation workflow.

MB-09 is a planning and recommendation layer, not a Training Engine,
Dataset Generator, or Model Runtime. This service NEVER edits Dataset
Studio, NEVER modifies the Training Engine, MB-06, MB-07, or Runtime,
NEVER creates a RAG dataset, NEVER launches training, and NEVER
deploys or activates a model. It composes existing, unmodified
systems through their public read methods only:

- `MiniBrainContinuousLearningService` (MB-08) -- `.list_sessions()`/
  `.session()` only, to read already-completed Continuous Learning
  Reports. MB-09 never creates or advances an MB-08 session.
- `MiniBrainDatasetIntelligenceService` (MB-05) -- `.training()`/
  `.analyze()` only, to read an existing dataset's already-computed
  readiness summary for the Dataset Evolution Planner. MB-09 never
  writes a dataset record.
- `ExternalDatasetDuplicateService` (Phase 12) -- `.group_normalized_
  duplicates()`/`.find_conflicts()`, reused unchanged for comparing
  provider outputs an admin has already collected. MB-09 never calls
  an external AI provider itself -- confirmed by audit, no such
  integration exists anywhere in this codebase.

Every stage produces a recommendation with cited evidence and stores
it on MB-09's own session; nothing here executes anything. The admin
review decision (`reject`/`edit`/`approve_draft`/
`request_provider_consensus`/`send_to_rag`/`archive`) only ever
records the admin's judgment -- none of the six decisions call MB-06,
MB-07, Dataset Studio, or RAG Sandbox. An admin who agrees acts on the
report manually, through those systems' own UIs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.mini_brain_continuous_learning_center import (
    MiniBrainContinuousLearningCenterRepository,
    public_memory_row,
    public_session_row,
)
from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_continuous_learning_service import (
    MiniBrainContinuousLearningService,
)
from backend.services.mini_brain_dataset_intelligence_service import (
    MiniBrainDatasetIntelligenceService,
)
from core_model.mini_brain.continuous_learning_center.dataset_evolution_planner import (
    plan_dataset_evolution,
)
from core_model.mini_brain.continuous_learning_center.draft_planner import build_draft_outline
from core_model.mini_brain.continuous_learning_center.knowledge_gap_evolution import (
    evolve_knowledge_gaps,
)
from core_model.mini_brain.continuous_learning_center.knowledge_roadmap import build_roadmap
from core_model.mini_brain.continuous_learning_center.learning_memory import extract_memory_fields
from core_model.mini_brain.continuous_learning_center.learning_queue import build_learning_queue
from core_model.mini_brain.continuous_learning_center.planning_report_generator import (
    generate_planning_report,
)
from core_model.mini_brain.continuous_learning_center.provider_consensus_planner import (
    build_consensus,
    build_provider_request,
)
from core_model.mini_brain.continuous_learning_center.recommendation_engine import (
    recommend_next_action,
)

MAX_CYCLES_COMPARED = 10
MAX_MEMORY_ENTRIES = 500
ADMIN_DECISIONS = {
    "reject", "edit", "approve_draft", "request_provider_consensus", "send_to_rag", "archive",
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainContinuousLearningCenterService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainContinuousLearningCenterRepository(settings.resolved_database_path)
        self.continuous_learning = MiniBrainContinuousLearningService(settings)
        dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        self.dataset_intelligence = MiniBrainDatasetIntelligenceService(dataset_service)
        self.duplicate_service = ExternalDatasetDuplicateService()

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, center_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, center_session_id=center_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset)
        return {"items": [public_session_row(row) for row in rows]}

    def _memory_entry_count(self) -> int:
        """`pagination()` caps a single page at 100, so counting up to
        `MAX_MEMORY_ENTRIES` real permanent memory rows means paging."""
        total = 0
        offset = 0
        while total < MAX_MEMORY_ENTRIES:
            page = self.list_memory(limit=100, offset=offset)["items"]
            if not page:
                break
            total += len(page)
            offset += 100
            if len(page) < 100:
                break
        return min(total, MAX_MEMORY_ENTRIES)

    def events(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_events(
                connection, center_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def _recent_closed_mb08_reports(self) -> list[dict[str, Any]]:
        """Oldest -> newest, real MB-08 Continuous Learning Reports only
        (sessions whose stage reached `closed` and actually produced a
        report). The report's own `weak_areas` field is a flat list of
        domain names (see `continuous_learning_report.py`) -- this
        rebuilds each cycle's `weak_areas` as domain+weakness_index
        dicts from that same session's real `weak_topic_report.topics`
        (only the entries already classified Weak there), so MB-09 can
        weight recurrence by real severity without MB-08 needing to
        change its own report shape."""
        sessions = self.continuous_learning.list_sessions(limit=MAX_CYCLES_COMPARED)["items"]
        closed = [s for s in sessions if s["stage"] == "closed" and s["continuous_learning_report"]]
        closed.reverse()
        reports = []
        for session in closed:
            report = dict(session["continuous_learning_report"])
            weak_topics = [
                {"domain": t["domain"], "weakness_index": t["weakness_index"]}
                for t in session["weak_topic_report"].get("topics", [])
                if t["classification"] == "Weak"
            ]
            report["weak_areas"] = weak_topics
            reports.append(report)
        return reports

    # -- learning memory (permanent, always available) -----------------

    def record_memory(
        self, *, continuous_learning_session_public_id: str, model_version_public_id: str | None = None,
        dataset_version_public_id: str | None = None, benchmark_summary: dict[str, Any] | None = None,
        admin_decision: str | None = None, improvement_notes: str = "", admin_id: str,
    ) -> dict[str, Any]:
        mb08_session = self.continuous_learning.session(continuous_learning_session_public_id)
        if not mb08_session["continuous_learning_report"]:
            raise ValidationError(
                "the referenced MB-08 session has no continuous learning report yet"
            )
        fields = extract_memory_fields(continuous_learning_report=mb08_session["continuous_learning_report"])
        with self.repository.transaction() as connection:
            public_id = self.repository.record_memory(
                connection, continuous_learning_session_public_id=continuous_learning_session_public_id,
                model_version_public_id=model_version_public_id,
                dataset_version_public_id=dataset_version_public_id,
                weak_domains=fields["weak_domains"], strong_domains=fields["strong_domains"],
                training_decision=fields["training_decision"], benchmark_summary=benchmark_summary or {},
                admin_decision=admin_decision, improvement_notes=improvement_notes,
                recorded_by_admin_public_id=admin_id,
            )
            return public_memory_row(self.repository.get_memory(connection, public_id))

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    def get_memory(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_memory_row(self.repository.get_memory(connection, public_id))

    # -- stage 1: session creation --------------------------------------

    def create_session(self, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(connection, created_by_admin_public_id=admin_id)
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="knowledge_gap_evolution",
                message="continuous learning center planning cycle created",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage: knowledge gap evolution -----------------------------------

    def evolve_knowledge_gaps_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "knowledge_gap_evolution":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'knowledge_gap_evolution'")

        reports = self._recent_closed_mb08_reports()
        report = evolve_knowledge_gaps(reports=reports)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"knowledge_gap_evolution_report_json": report, "stage": "learning_queue"},
            )
            self._event(
                connection, session_row["id"], "knowledge_gaps_evolved", stage="knowledge_gap_evolution",
                message=f"compared {report['cycles_compared']} cycle(s), {len(report['recurring_weak_domains'])} recurring weak domain(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: learning queue --------------------------------------------

    def build_learning_queue_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "learning_queue":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'learning_queue'")

        reports = self._recent_closed_mb08_reports()
        latest_dataset_suggestions = reports[-1]["dataset_suggestions"] if reports else []
        report = build_learning_queue(
            recurring_weak_domains=session_data["knowledge_gap_evolution_report"]["recurring_weak_domains"],
            latest_dataset_suggestions=latest_dataset_suggestions,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"learning_queue_report_json": report, "stage": "draft_planning"},
            )
            self._event(
                connection, session_row["id"], "learning_queue_built", stage="learning_queue",
                message=f"{report['queue_length']} queue item(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: local draft planning -----------------------------------------

    def build_draft_stage(self, session_public_id: str, *, topic: str | None = None, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "draft_planning":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'draft_planning'")

        queue = session_data["learning_queue_report"]["queue"]
        if topic is None:
            if not queue:
                raise ValidationError("learning queue is empty -- supply an explicit topic")
            topic = queue[0]["topic"]
        matching = next((item for item in queue if item["topic"] == topic), None)
        suggested_formats = matching["suggested_dataset_type"] if matching else ["QA pairs"]

        report = build_draft_outline(topic=topic, suggested_formats=suggested_formats)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"draft_report_json": report, "stage": "provider_request"},
            )
            self._event(
                connection, session_row["id"], "draft_built", stage="draft_planning",
                message=f"draft outline prepared for '{topic}' (unverified)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: provider request preparation ---------------------------------

    def prepare_provider_request_stage(
        self, session_public_id: str, *, requested_providers: list[str], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "provider_request":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'provider_request'")

        draft = session_data["draft_report"]
        report = build_provider_request(
            topic=draft["topic"], evidence={"required_topics": draft["required_topics"]},
            requested_providers=requested_providers,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            fields: dict[str, Any] = {"provider_request_json": report}
            if report["valid"]:
                fields["stage"] = "provider_consensus"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], "provider_request_prepared", stage="provider_request",
                message=f"requested providers: {report['requested_providers']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def ingest_provider_results_stage(
        self, session_public_id: str, *, provider_outputs: list[dict[str, str]], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "provider_consensus":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'provider_consensus'")

        topic = session_data["draft_report"]["topic"]
        records = [
            {
                "public_id": output["provider"],
                "normalized_content": " ".join(output["output_text"].strip().lower().split()),
                "structured_payload": {"topic": topic, "output_text": output["output_text"]},
            }
            for output in provider_outputs
        ]
        duplicate_groups = self.duplicate_service.group_normalized_duplicates(records)
        conflict_groups = self.duplicate_service.find_conflicts(
            records, key_field="topic", value_field="output_text"
        )
        report = build_consensus(
            provider_outputs=provider_outputs, duplicate_groups=duplicate_groups,
            conflict_groups=conflict_groups,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"provider_consensus_report_json": report, "stage": "dataset_evolution"},
            )
            self._event(
                connection, session_row["id"], "provider_results_ingested", stage="provider_consensus",
                message=f"consensus confidence: {report['confidence']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: dataset evolution ---------------------------------------------

    def plan_dataset_evolution_stage(
        self, session_public_id: str, *, existing_dataset_source_public_id: str | None = None, admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "dataset_evolution":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dataset_evolution'")

        topic = session_data["draft_report"]["topic"]
        if existing_dataset_source_public_id is None:
            report = plan_dataset_evolution(existing_dataset_exists=False, draft_topic=topic)
        else:
            training = self.dataset_intelligence.training(existing_dataset_source_public_id)
            analysis = self.dataset_intelligence.analyze(existing_dataset_source_public_id)
            report = plan_dataset_evolution(
                existing_dataset_exists=True, draft_topic=topic, existing_status=training["status"],
                existing_clean_ratio=training["clean_ratio"], existing_duplicate_ratio=training["duplicate_ratio"],
                existing_record_count=analysis["record_count"],
            )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"dataset_evolution_report_json": report, "stage": "knowledge_roadmap"},
            )
            self._event(
                connection, session_row["id"], "dataset_evolution_planned", stage="dataset_evolution",
                message=f"recommendation: {report['recommendation']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: knowledge roadmap ------------------------------------------------

    def build_roadmap_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "knowledge_roadmap":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'knowledge_roadmap'")

        memory_entry_count = self._memory_entry_count()
        reports = self._recent_closed_mb08_reports()
        current_strong_domains = reports[-1]["strong_areas"] if reports else []
        current_weak_domains = [
            entry["domain"] for entry in session_data["knowledge_gap_evolution_report"]["recurring_weak_domains"]
        ]
        report = build_roadmap(
            memory_entry_count=memory_entry_count, current_weak_domains=current_weak_domains,
            current_strong_domains=current_strong_domains, queue=session_data["learning_queue_report"]["queue"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"roadmap_report_json": report, "stage": "recommendation"},
            )
            self._event(
                connection, session_row["id"], "roadmap_built", stage="knowledge_roadmap",
                message=f"{memory_entry_count} cycle(s) in memory",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage: recommendation ---------------------------------------------------

    def generate_recommendation_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "recommendation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'recommendation'")

        provider_consensus = session_data["provider_consensus_report"] or None
        report = recommend_next_action(
            queue=session_data["learning_queue_report"]["queue"],
            dataset_evolution_recommendation=session_data["dataset_evolution_report"]["recommendation"],
            provider_consensus=provider_consensus,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"recommendation_report_json": report})
            self._event(
                connection, session_row["id"], "recommendation_generated", stage="recommendation",
                message=f"recommended action: {report['action']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def generate_report(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "recommendation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'recommendation'")
        if not session_data["recommendation_report"]:
            raise ValidationError("generate the recommendation before generating the report")

        memory_entry_count = self._memory_entry_count()
        report = generate_planning_report(
            session_public_id=session_public_id, memory_entry_count=memory_entry_count,
            knowledge_gap_evolution_report=session_data["knowledge_gap_evolution_report"],
            learning_queue_report=session_data["learning_queue_report"],
            draft_report=session_data["draft_report"] or None,
            provider_consensus_report=session_data["provider_consensus_report"] or None,
            dataset_evolution_report=session_data["dataset_evolution_report"] or None,
            roadmap_report=session_data["roadmap_report"],
            recommendation_report=session_data["recommendation_report"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"planning_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "planning_report_generated", stage="recommendation",
                message="admin planning report ready for review",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- admin review (advisory only -- never executes anything) --------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(
                    f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'"
                )
            status_map = {
                "reject": "admin_rejected", "edit": "admin_edited", "approve_draft": "admin_approved_draft",
                "request_provider_consensus": "admin_requested_provider_consensus",
                "send_to_rag": "admin_sent_to_rag", "archive": "admin_archived",
            }
            fields = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": status_map[decision], "stage": "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"admin_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' on the planning report -- no automatic action taken; "
                    "any follow-up happens manually via Dataset Studio, MB-06, MB-07, or RAG Sandbox"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainContinuousLearningCenterService"]
