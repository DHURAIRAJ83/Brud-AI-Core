"""MB-23: Brud Mini Brain Public Chat Runtime & Self-Improvement
Feedback Loop -- the orchestration layer for the task spec's own
15-stage workflow.

Real-time turns (Steps 1-11 and 15) run inline on every request; they
never touch model inference, RAG retrieval, vision inference, or tool
dispatch directly -- `PublicChatRoutingService.handle_message()` is
called exactly once per user message and owns all of that. This
service only derives MB-23-specific bookkeeping (used_rag/used_vision/
used_tool flags, gap-detection signals) from that response's own
already-computed fields.

Clustering and candidate generation (Steps 12-14) are a separate,
explicit, admin-triggered batch operation (`run_generate_candidates`)
over already-persisted signals -- never run automatically on the hot
per-message path, and never anything but advisory: every candidate is
born `status='pending_admin_review'` and can only leave that status
through `review_candidate()`. This service never calls a write method
on MB-16/17/18/19/20/21/22 -- no dataset is approved, no grounded
answer is approved, no training package is approved, no evaluation is
approved, no release is approved, no external provider is dispatched,
and no training job is started or finalized as a result of anything in
this file.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_public_chat_runtime import (
    MiniBrainPublicChatRuntimeRepository,
    public_candidate_row,
    public_message_row,
    public_session_row,
    public_signal_row,
)
from backend.models.public_chat import PublicChatRequest
from backend.services.public_chat_routing_service import PublicChatRoutingService
from core_model.conversation.summary_builder import estimate_token_count
from core_model.mini_brain.public_chat_runtime import (
    admin_handoff_builder,
    conversation_window,
    failure_clusterer,
    feedback_sanitizer,
    feedback_signal_extractor,
    gap_detector,
    improvement_candidate_builder,
    priority_ranker,
    query_classifier,
    rag_orchestrator,
    response_safety_filter,
    runtime_report_generator,
    session_builder,
    tool_routing_policy,
    vision_request_router,
)

MINIMUM_CLUSTER_FREQUENCY = 2
DEFAULT_SIGNAL_SCAN_LIMIT = 100
_SUPPORTED_LANGUAGES = ("auto", "ta", "en")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _epoch_seconds(timestamp: str | None) -> float:
    if not timestamp:
        return time.time()
    try:
        return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
    except ValueError:
        return time.time()


class MiniBrainPublicChatRuntimeService:
    def __init__(self, settings: Settings, *, chat_router: PublicChatRoutingService | None = None) -> None:
        self.settings = settings
        self.repository = MiniBrainPublicChatRuntimeRepository(settings.resolved_database_path)
        self.chat_router = chat_router or PublicChatRoutingService(settings)
        self._salt = settings.mini_brain_public_chat_runtime_hash_salt

    # -- diagnostics ------------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        return {
            "mb16_dataset_approvals_performed": False,
            "mb17_grounded_answer_approvals_performed": False,
            "mb18_package_approvals_performed": False,
            "mb19_evaluation_approvals_performed": False,
            "mb20_release_approvals_performed": False,
            "mb21_provider_dispatch_performed": False,
            "mb22_training_started_or_finalized": False,
            "automatic_learning_performed": False,
            "automatic_training_performed": False,
            "raw_personal_data_stored": False,
            "raw_message_content_stored": False,
            "shell_commands_executed": False,
            "models_deployed": False,
            "production_models_changed": False,
            "candidates_require_admin_review": True,
            "writes_scope": (
                "own tables only (mini_brain_public_chat_sessions/_messages, mini_brain_feedback_signals, "
                "mini_brain_improvement_candidates, mini_brain_public_chat_events); every real chat "
                "message is answered by the existing PublicChatRoutingService, never a second inference/"
                "RAG/vision/tool path"
            ),
        }

    # -- sessions ------------------------------------------------------------------

    def start_session(self, *, raw_client_key: str, language: str = "auto") -> dict[str, Any]:
        shape = session_builder.build_session(raw_client_key=raw_client_key, salt=self._salt, language=language)
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, user_session_hash=shape["user_session_hash"], language=shape["language"],
            )
            session_row = self.repository.get_session(connection, public_id)
            self.repository.create_event(
                connection, session_id=session_row["id"], event_type="session_created", stage="create_session",
            )
            return public_session_row(session_row)

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.get_session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0, status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset, status=status)
        return {"items": [public_session_row(row) for row in rows]}

    def messages(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            rows = self.repository.list_messages(connection, session_id=session_row["id"], limit=limit, offset=offset)
        return {"items": [public_message_row(row) for row in rows]}

    def signals(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            rows = self.repository.list_signals(connection, session_id=session_row["id"], limit=limit, offset=offset)
        return {"items": [public_signal_row(row) for row in rows]}

    def events(
        self, *, session_public_id: str | None = None, candidate_public_id: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_id = None
            candidate_id = None
            if session_public_id:
                session_id = self.repository.get_session(connection, session_public_id)["id"]
            if candidate_public_id:
                candidate_id = self.repository.get_candidate(connection, candidate_public_id)["id"]
            rows = self.repository.list_events(
                connection, session_id=session_id, candidate_id=candidate_id, limit=limit, offset=offset,
            )
        return {"items": [dict(row) for row in rows]}

    # -- send message (steps 2-11) --------------------------------------------------

    def send_message(self, session_public_id: str, *, raw_message: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
        if session_row["status"] != "active":
            raise ValidationError("session must be active to send a message")

        capped = conversation_window.cap_message_size(text=raw_message)
        classification = query_classifier.classify_query(text=capped["text"])
        topic_key = query_classifier.normalize_topic_key(text=capped["text"])
        sanitized_user = feedback_sanitizer.sanitize_text(raw_text=capped["text"])

        language_override = session_row["language"] if session_row["language"] in _SUPPORTED_LANGUAGES else "auto"
        response = self.chat_router.handle_message(
            PublicChatRequest(
                message=capped["text"], conversation_id=session_row["conversation_id"],
                language_override=language_override,
            )
        )

        tool_flags = tool_routing_policy.derive_tool_usage(
            route_used=response.route_used, tool_name=response.tool_name, tool_status=response.tool_status,
        )
        rag_flags = rag_orchestrator.derive_rag_usage(
            source_types=response.source_types, evidence_status=response.evidence_status,
            citation_count=len(response.citations), insufficient_evidence=response.insufficient_evidence,
        )
        vision_flags = vision_request_router.derive_vision_usage(
            query_category=classification["category"], source_types=response.source_types,
        )
        safety_evaluation = response_safety_filter.evaluate_response_safety(safety_status=response.safety_status)
        sanitized_reply = feedback_sanitizer.sanitize_text(raw_text=response.reply or "")

        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            recent_topic_keys = self.repository.recent_user_topic_keys(connection, session_id=session_row["id"])

            self.repository.create_message(
                connection, session_id=session_row["id"], role="user",
                content_hash=sanitized_user["sanitized_hash_sha256"], topic_key=topic_key,
                token_estimate=estimate_token_count(capped["text"]), used_rag=False, used_vision=False,
                used_tool=False, route_used=None, evidence_status=None,
            )
            assistant_message_pid = self.repository.create_message(
                connection, session_id=session_row["id"], role="assistant",
                content_hash=sanitized_reply["sanitized_hash_sha256"], topic_key=None,
                token_estimate=estimate_token_count(response.reply or ""), used_rag=rag_flags["used_rag"],
                used_vision=vision_flags["used_vision"], used_tool=tool_flags["used_tool"],
                route_used=response.route_used, evidence_status=response.evidence_status,
            )
            assistant_message_row = connection.execute(
                "SELECT * FROM mini_brain_public_chat_messages WHERE public_id=?", (assistant_message_pid,),
            ).fetchone()

            gap_signals = gap_detector.detect_gaps(
                sanitized_user_text=sanitized_user["sanitized_text"], confidence_band=response.confidence_band,
                evidence_sufficient=rag_flags["evidence_sufficient"],
                insufficient_evidence_flag=response.insufficient_evidence, current_topic_key=topic_key,
                recent_topic_keys=recent_topic_keys,
            )
            signals = feedback_signal_extractor.extract_feedback_signals(
                sanitized_text=sanitized_user["sanitized_text"], topic_key=topic_key, gap_signals=gap_signals,
                safety_evaluation=safety_evaluation,
            )
            for signal in signals:
                self.repository.create_signal(
                    connection, session_id=session_row["id"], message_id=assistant_message_row["id"],
                    signal_type=signal["signal_type"], severity=signal["severity"],
                    normalized_text=signal["normalized_text"], topic_key=signal["topic_key"],
                )

            session_updates: dict[str, Any] = {"message_count": session_row["message_count"] + 2}
            if not session_row["conversation_id"] and response.conversation_id:
                session_updates["conversation_id"] = response.conversation_id
            if session_row["language"] == "auto" and response.detected_language:
                session_updates["language"] = (
                    response.detected_language if response.detected_language in _SUPPORTED_LANGUAGES else "auto"
                )
            if signals:
                session_updates["unresolved_count"] = session_row["unresolved_count"] + 1
            self.repository.update_session(connection, session_public_id, session_updates)

            self.repository.create_event(
                connection, session_id=session_row["id"], event_type="message_processed", stage="send_message",
                message=f"route={response.route_used} signals={len(signals)}",
            )

            return {
                "reply": response.reply, "route_used": response.route_used, "evidence_status": response.evidence_status,
                "confidence_band": response.confidence_band, "citations": [c.model_dump() for c in response.citations],
                "insufficient_evidence": response.insufficient_evidence, "clarification_required": response.clarification_required,
                "safety_status": response.safety_status, "used_rag": rag_flags["used_rag"],
                "used_vision": vision_flags["used_vision"], "used_tool": tool_flags["used_tool"],
                "signals_raised": len(signals), "session_public_id": session_public_id,
            }

    # -- explicit feedback (step 10, explicit path) -------------------------------------

    def submit_feedback(
        self, session_public_id: str, *, satisfaction_rating: float | None, raw_comment: str | None,
    ) -> dict[str, Any]:
        if satisfaction_rating is not None and not (0.0 <= satisfaction_rating <= 1.0):
            raise ValidationError("satisfaction_rating must be within [0, 1]")

        sanitized_comment = feedback_sanitizer.sanitize_text(raw_text=raw_comment or "")
        topic_key = query_classifier.normalize_topic_key(text=raw_comment) if raw_comment else "general_feedback"

        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)

            is_negative = satisfaction_rating is not None and satisfaction_rating < 0.5
            gap_signals = []
            if raw_comment:
                gap_signals = gap_detector.detect_gaps(
                    sanitized_user_text=sanitized_comment["sanitized_text"], confidence_band="unknown",
                    evidence_sufficient=True, insufficient_evidence_flag=False, current_topic_key=topic_key,
                    recent_topic_keys=[],
                )
            if is_negative and not any(g["signal_type"] == "explicit_negative" for g in gap_signals):
                gap_signals.append({
                    "signal_type": "explicit_negative", "severity": "high",
                    "reason": f"explicit satisfaction_rating={satisfaction_rating} below 0.5 threshold",
                })

            for gap in gap_signals:
                self.repository.create_signal(
                    connection, session_id=session_row["id"], message_id=None, signal_type=gap["signal_type"],
                    severity=gap["severity"], normalized_text=sanitized_comment["sanitized_text"], topic_key=topic_key,
                )

            existing_score = session_row["satisfaction_score"]
            if satisfaction_rating is not None:
                new_score = (
                    satisfaction_rating if existing_score is None else (existing_score + satisfaction_rating) / 2
                )
                updates: dict[str, Any] = {"satisfaction_score": new_score}
                if gap_signals:
                    updates["unresolved_count"] = session_row["unresolved_count"] + 1
                self.repository.update_session(connection, session_public_id, updates)
            elif gap_signals:
                self.repository.update_session(
                    connection, session_public_id, {"unresolved_count": session_row["unresolved_count"] + 1},
                )

            self.repository.create_event(
                connection, session_id=session_row["id"], event_type="feedback_submitted", stage="submit_feedback",
                message=f"satisfaction_rating={satisfaction_rating} signals={len(gap_signals)}",
            )
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- close session (step 15) ---------------------------------------------------------

    def end_session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            if session_row["status"] != "active":
                raise ValidationError("session is already ended")

            self.repository.update_session(connection, session_public_id, {"status": "ended", "ended_at": _now()})
            session_row = self.repository.get_session(connection, session_public_id)

            usage_counts = self.repository.session_usage_counts(connection, session_id=session_row["id"])
            signal_counts = self.repository.session_signal_counts_by_type(connection, session_id=session_row["id"])

            report = runtime_report_generator.generate_session_report(
                session_public_id=session_public_id, message_count=usage_counts["message_count"],
                used_rag_count=usage_counts["used_rag_count"], used_vision_count=usage_counts["used_vision_count"],
                used_tool_count=usage_counts["used_tool_count"], signal_counts_by_type=signal_counts,
                satisfaction_score=session_row["satisfaction_score"], unresolved_count=session_row["unresolved_count"],
                started_at=session_row["started_at"], ended_at=session_row["ended_at"],
            )
            self.repository.create_event(
                connection, session_id=session_row["id"], event_type="session_closed", stage="close_session",
                message="session ended", metadata=report,
            )
            return {"session": public_session_row(session_row), "report": report}

    # -- clusters (read-only, computed live) ---------------------------------------------

    def list_clusters(self, *, signal_limit: int = DEFAULT_SIGNAL_SCAN_LIMIT) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.signals_for_clustering(connection, limit=signal_limit, offset=0)
        signals = [dict(row) for row in rows]
        clusters = failure_clusterer.cluster_failures(signals=signals)
        return {"items": clusters}

    # -- admin: generate improvement candidates (steps 12-14) -------------------------------

    def run_generate_candidates(
        self, *, admin_id: str, minimum_frequency: int = MINIMUM_CLUSTER_FREQUENCY,
        signal_limit: int = DEFAULT_SIGNAL_SCAN_LIMIT,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.signals_for_clustering(connection, limit=signal_limit, offset=0)
            signals = [dict(row) for row in rows]
            clusters = failure_clusterer.cluster_failures(signals=signals)
            now_epoch = time.time()

            created_or_updated: list[dict[str, Any]] = []
            for cluster in clusters:
                if cluster["frequency"] < minimum_frequency:
                    continue

                candidate_shape = improvement_candidate_builder.build_candidate(cluster=cluster)
                high = cluster["severity_counts"].get("high", 0)
                unresolved_rate = min(1.0, (
                    cluster["signal_type_counts"].get("explicit_negative", 0)
                    + cluster["signal_type_counts"].get("repeated_question", 0)
                ) / cluster["frequency"])
                dissatisfaction_rate = min(1.0, high / cluster["frequency"])
                priority = priority_ranker.compute_priority_score(
                    frequency=cluster["frequency"], distinct_session_count=cluster["distinct_session_count"],
                    most_recent_at_epoch_seconds=_epoch_seconds(cluster["most_recent_at"]),
                    now_epoch_seconds=now_epoch, unresolved_rate=unresolved_rate,
                    dissatisfaction_rate=dissatisfaction_rate,
                )
                handoff = admin_handoff_builder.build_admin_handoff(
                    topic=candidate_shape["topic"], topic_key=candidate_shape["topic_key"],
                    frequency=candidate_shape["frequency"], priority_score=priority["priority_score"],
                    recommended_action=candidate_shape["recommended_action"],
                    example_questions=candidate_shape["example_questions"],
                    suggested_missing_knowledge=candidate_shape["suggested_missing_knowledge"],
                )

                existing = self.repository.find_candidate_by_topic_key(connection, candidate_shape["topic_key"])
                if existing is None:
                    public_id = self.repository.create_candidate(
                        connection, topic=candidate_shape["topic"], topic_key=candidate_shape["topic_key"],
                        frequency=candidate_shape["frequency"], impact_score=candidate_shape["impact_score"],
                        priority_score=priority["priority_score"], recommended_action=candidate_shape["recommended_action"],
                        example_questions=candidate_shape["example_questions"],
                        suggested_missing_knowledge=candidate_shape["suggested_missing_knowledge"],
                    )
                    self.repository.update_candidate(connection, public_id, {"handoff_report_json": handoff})
                    candidate_id = self.repository.get_candidate(connection, public_id)["id"]
                elif existing["status"] == "pending_admin_review":
                    public_id = existing["public_id"]
                    self.repository.update_candidate(
                        connection, public_id,
                        {
                            "frequency": candidate_shape["frequency"], "impact_score": candidate_shape["impact_score"],
                            "priority_score": priority["priority_score"],
                            "recommended_action": candidate_shape["recommended_action"],
                            "example_questions_json": candidate_shape["example_questions"],
                            "suggested_missing_knowledge_json": candidate_shape["suggested_missing_knowledge"],
                            "handoff_report_json": handoff,
                        },
                    )
                    candidate_id = existing["id"]
                else:
                    # already reviewed -- never silently overwrite an admin's own decision.
                    continue

                self.repository.create_event(
                    connection, candidate_id=candidate_id, event_type="candidate_generated",
                    stage="generate_candidates", message=f"topic_key={candidate_shape['topic_key']}",
                    metadata={"admin_id": admin_id},
                )
                created_or_updated.append(public_candidate_row(self.repository.get_candidate(connection, public_id)))

            return {"items": created_or_updated, "cluster_count": len(clusters)}

    # -- admin: candidate read/review ----------------------------------------------------

    def candidate(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_candidate_row(self.repository.get_candidate(connection, candidate_public_id))

    def list_candidates(self, *, status: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_candidates(connection, limit=limit, offset=offset, status=status)
        return {"items": [public_candidate_row(row) for row in rows]}

    def review_candidate(
        self, candidate_public_id: str, *, admin_id: str, decision: str, notes: str | None = None,
    ) -> dict[str, Any]:
        if decision not in ("approve", "reject"):
            raise ValidationError("decision must be 'approve' or 'reject'")

        with self.repository.transaction() as connection:
            existing = self.repository.get_candidate(connection, candidate_public_id)
            if existing["status"] != "pending_admin_review":
                raise ValidationError(f"candidate is already '{existing['status']}' -- only a pending candidate can be reviewed")

            new_status = "approved" if decision == "approve" else "rejected"
            self.repository.update_candidate(
                connection, candidate_public_id,
                {
                    "status": new_status, "reviewed_by_admin_public_id": admin_id, "review_decision": decision,
                    "review_notes": notes or "", "reviewed_at": _now(),
                },
            )
            self.repository.create_event(
                connection, candidate_id=existing["id"], event_type="candidate_reviewed",
                stage="review_candidate", message=f"decision={decision}", metadata={"admin_id": admin_id},
            )
            return public_candidate_row(self.repository.get_candidate(connection, candidate_public_id))

    # -- analytics & exports ------------------------------------------------------------

    def analytics(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            summary = self.repository.analytics_summary(connection)
            top_rows = self.repository.list_candidates(connection, limit=10, offset=0, status="pending_admin_review")
        top_candidates = [public_candidate_row(row) for row in top_rows]
        return runtime_report_generator.generate_runtime_analytics_summary(
            total_sessions=summary["total_sessions"], total_messages=summary["total_messages"],
            total_signals_by_type=summary["total_signals_by_type"], top_candidates=top_candidates,
            generated_at=_now(),
        )

    def export_analytics(self) -> dict[str, Any]:
        return {"export_format": "json", "generated_at": _now(), "analytics": self.analytics()}

    def export_candidates(self, *, status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_candidates(connection, limit=100, offset=0, status=status)
        return {
            "export_format": "json", "generated_at": _now(),
            "items": [public_candidate_row(row) for row in rows],
        }


__all__ = ["MiniBrainPublicChatRuntimeService"]
