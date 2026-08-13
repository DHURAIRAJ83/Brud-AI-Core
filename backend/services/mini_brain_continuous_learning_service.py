"""MB-08: Brud Mini Brain Continuous Learning & Feedback Engine -- the
orchestration layer for the 10-stage observe-analyze-recommend
workflow.

This service NEVER retrains a model, NEVER edits a dataset, NEVER
modifies a checkpoint, and NEVER activates a model -- it only reads
already-existing, real production evidence and produces a report for
an explicit admin decision. Approving that decision records the
admin's judgment only; it never itself creates an MB-06 session, never
calls MB-07, and never writes to any table outside its own two. An
admin who agrees with the report acts on it manually, through MB-06's
and MB-07's own UIs, informed by this report's evidence.

Composes existing, unmodified systems through their public read
methods only:

- `PublicChatRoutingRepository` -- `.list_events()` (routing events,
  including the real `evidence_status` grounding signal) and
  `.list_feedback_events()` (the one small, purely additive read
  method this phase added -- no table or existing method changed).
- `KnowledgeGapRepository` -- `.list_cases()`, the real, already
  privacy-filtered, deduplicated, priority-scored Knowledge Gap
  Registry (Phase 19/20). MB-08 only ever reads from it -- it never
  calls any of that registry's own write methods (capture, classify,
  assess-handoff, resolve, etc.); those remain that system's own,
  separately admin-driven workflow.
- `core_model.mini_brain.dataset_advanced.dataset_difficulty_analyzer.
  difficulty_for_text` -- reused unchanged inside MB-08's own
  `difficulty_analyzer` pure module.

Honest scope: neither `list_events()` nor `list_cases()` supports a
date-range filter, so `cycle_window_days` is stored as an admin-facing
intent label, not an enforced live filter -- every stage instead
analyzes the most recent bounded batch (see `MAX_RECORDS_PER_SOURCE`),
the same disclosed-bound pattern MB-05 used for dataset analysis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.database.repositories.mini_brain_continuous_learning import (
    MiniBrainContinuousLearningRepository,
    public_row,
)
from backend.database.repositories.public_chat import PublicChatRoutingRepository
from core_model.mini_brain.continuous_learning.continuous_learning_report import (
    generate_continuous_learning_report,
)
from core_model.mini_brain.continuous_learning.dataset_recommendation import recommend_datasets
from core_model.mini_brain.continuous_learning.difficulty_analyzer import analyze_difficulty
from core_model.mini_brain.continuous_learning.failure_analyzer import analyze_failures
from core_model.mini_brain.continuous_learning.feedback_collector import collect_feedback
from core_model.mini_brain.continuous_learning.hallucination_detector import detect_hallucinations
from core_model.mini_brain.continuous_learning.knowledge_gap_detector import detect_knowledge_gaps
from core_model.mini_brain.continuous_learning.priority_engine import rank_priorities
from core_model.mini_brain.continuous_learning.training_recommendation import (
    recommend_training_action,
)
from core_model.mini_brain.continuous_learning.weak_topic_detector import detect_weak_topics

def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


MAX_RECORDS_PER_SOURCE = 500
_PAGE_SIZE = 100
ADMIN_DECISIONS = {"approve", "reject"}


class MiniBrainContinuousLearningService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainContinuousLearningRepository(settings.resolved_database_path)
        self.public_chat = PublicChatRoutingRepository(settings.resolved_database_path)
        self.knowledge_gap = KnowledgeGapRepository(settings.resolved_database_path)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, session_row_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, learning_cycle_session_id=session_row_id, event_type=event_type,
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
                connection, learning_cycle_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def _bounded(self, fetch_page) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0
        while len(items) < MAX_RECORDS_PER_SOURCE:
            page = fetch_page(limit=_PAGE_SIZE, offset=offset)
            if not page:
                break
            items.extend(page)
            offset += _PAGE_SIZE
            if len(page) < _PAGE_SIZE:
                break
        return items[:MAX_RECORDS_PER_SOURCE]

    def _routing_events(self) -> list[dict[str, Any]]:
        return self._bounded(lambda *, limit, offset: self.public_chat.list_events(limit=limit, offset=offset))

    def _feedback_events(self) -> list[dict[str, Any]]:
        return self._bounded(
            lambda *, limit, offset: self.public_chat.list_feedback_events(limit=limit, offset=offset)
        )

    def _knowledge_gap_cases(self) -> list[dict[str, Any]]:
        return self._bounded(lambda *, limit, offset: self.knowledge_gap.list_cases(limit=limit, offset=offset))

    # -- stage 1: session creation --------------------------------------

    def create_session(self, *, cycle_window_days: int = 30, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, cycle_window_days=cycle_window_days, created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="feedback_collection",
                message=f"continuous learning cycle created (window intent: {cycle_window_days} days)",
            )
            return public_row(self.repository.session(connection, public_id))

    # -- stage 1: feedback collection -----------------------------------

    def collect_feedback_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "feedback_collection":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'feedback_collection'")

        report = collect_feedback(routing_events=self._routing_events(), feedback_events=self._feedback_events())

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"feedback_report_json": report, "stage": "failure_analysis"},
            )
            self._event(
                connection, session_row["id"], "feedback_collected", stage="feedback_collection",
                message=f"{report['total_conversations_observed']} conversation(s) observed",
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 2: failure analysis ----------------------------------------

    def analyze_failures_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "failure_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'failure_analysis'")

        report = analyze_failures(routing_events=self._routing_events(), feedback_events=self._feedback_events())

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"failure_report_json": report, "stage": "hallucination_analysis"},
            )
            self._event(
                connection, session_row["id"], "failures_analyzed", stage="failure_analysis",
                message=f"failure_rate={report['failure_rate']}", metadata={"failure_counts": report["failure_counts"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 3: hallucination analysis -----------------------------------

    def analyze_hallucinations_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "hallucination_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'hallucination_analysis'")

        report = detect_hallucinations(routing_events=self._routing_events())

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"hallucination_report_json": report, "stage": "knowledge_gap_analysis"},
            )
            self._event(
                connection, session_row["id"], "hallucinations_analyzed", stage="hallucination_analysis",
                message=f"hallucination_rate={report['hallucination_rate']}",
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 4: knowledge gap analysis -----------------------------------

    def analyze_knowledge_gaps_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "knowledge_gap_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'knowledge_gap_analysis'")

        report = detect_knowledge_gaps(knowledge_gap_cases=self._knowledge_gap_cases())

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"knowledge_gap_report_json": report, "stage": "weak_topic_detection"},
            )
            self._event(
                connection, session_row["id"], "knowledge_gaps_analyzed", stage="knowledge_gap_analysis",
                message=f"{report['total_knowledge_gap_cases']} knowledge gap case(s)",
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 5: weak topic detection --------------------------------------

    def detect_weak_topics_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "weak_topic_detection":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'weak_topic_detection'")

        report = detect_weak_topics(knowledge_gap_cases=self._knowledge_gap_cases())

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"weak_topic_report_json": report, "stage": "difficulty_analysis"},
            )
            self._event(
                connection, session_row["id"], "weak_topics_detected", stage="weak_topic_detection",
                message=f"{len(report['weak_topics'])} weak topic(s)", metadata={"weak_topics": report["weak_topics"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 6: difficulty analysis --------------------------------------

    def analyze_difficulty_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "difficulty_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'difficulty_analysis'")

        report = analyze_difficulty(knowledge_gap_cases=self._knowledge_gap_cases())

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"difficulty_report_json": report, "stage": "dataset_recommendation"},
            )
            self._event(
                connection, session_row["id"], "difficulty_analyzed", stage="difficulty_analysis",
                message=f"{report['total_cases_classified']} case(s) classified",
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 7: dataset recommendation -------------------------------------

    def recommend_datasets_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "dataset_recommendation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dataset_recommendation'")

        report = recommend_datasets(
            weak_topics=session_data["weak_topic_report"]["topics"],
            missing_documentation_domains=session_data["knowledge_gap_report"]["missing_documentation_domains"],
            missing_workflow_domains=session_data["knowledge_gap_report"]["missing_workflow_domains"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"dataset_recommendation_report_json": report, "stage": "training_recommendation"},
            )
            self._event(
                connection, session_row["id"], "datasets_recommended", stage="dataset_recommendation",
                message=f"{len(report['recommendations'])} recommendation(s)",
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 8: training recommendation ------------------------------------

    def recommend_training_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "training_recommendation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'training_recommendation'")

        cases = self._knowledge_gap_cases()
        training_eligible_case_count = sum(1 for c in cases if c["eligible_for_training_assessment"])

        report = recommend_training_action(
            failure_rate=session_data["failure_report"]["failure_rate"],
            hallucination_rate=session_data["hallucination_report"]["hallucination_rate"],
            weak_topics=session_data["weak_topic_report"]["topics"],
            training_eligible_case_count=training_eligible_case_count,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"training_recommendation_report_json": report, "stage": "priority_ranking"},
            )
            self._event(
                connection, session_row["id"], "training_recommended", stage="training_recommendation",
                message=f"recommended action: {report['action']}",
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 9: priority ranking --------------------------------------------

    def rank_priorities_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "priority_ranking":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'priority_ranking'")

        report = rank_priorities(
            dataset_recommendations=session_data["dataset_recommendation_report"]["recommendations"],
            knowledge_gap_cases=self._knowledge_gap_cases(),
            training_recommendation=session_data["training_recommendation_report"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"priority_report_json": report})
            self._event(
                connection, session_row["id"], "priorities_ranked", stage="priority_ranking",
                message=f"training recommendation priority: {report['training_recommendation']['priority']}",
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 10: continuous learning report ----------------------------------

    def generate_report(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "priority_ranking":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'priority_ranking'")

        report = generate_continuous_learning_report(
            session_public_id=session_public_id,
            feedback_report=session_data["feedback_report"],
            failure_report=session_data["failure_report"],
            hallucination_report=session_data["hallucination_report"],
            knowledge_gap_report=session_data["knowledge_gap_report"],
            weak_topic_report=session_data["weak_topic_report"],
            difficulty_report=session_data["difficulty_report"],
            dataset_recommendation_report=session_data["dataset_recommendation_report"],
            training_recommendation=session_data["priority_report"]["training_recommendation"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"continuous_learning_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "report_generated", stage="priority_ranking",
                message=f"overall_health={report['overall_health']}",
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- admin review (advisory only -- never triggers MB-06/MB-07) -----------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(
                    f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'"
                )
            status_map = {"approve": "admin_approved", "reject": "admin_rejected"}
            fields = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": status_map[decision], "stage": "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"admin_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin {decision}d the continuous learning report -- "
                    "no automatic action taken; any follow-up happens manually via MB-06/MB-07"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainContinuousLearningService"]
