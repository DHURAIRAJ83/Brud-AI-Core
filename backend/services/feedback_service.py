"""Phase 18 feedback policies, subject lineage resolution, feedback
event submission, classification, triage, and privacy/safety scanning.

Feedback must never become training data automatically -- this service
only ever produces ``feedback_events``/``feedback_classifications``
rows and privacy/safety findings. Converting reviewed feedback into a
dataset candidate is a separate, explicitly-triggered action handled by
``FeedbackDatasetService``.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.feedback import FeedbackRepository, public_row
from backend.models.feedback import FeedbackEventCreate, FeedbackPolicyCreate, FeedbackPolicyPatch
from core_model.feedback import FEEDBACK_TYPES, SEVERITIES, SUBJECT_TYPES
from core_model.feedback.classification import validate_classification
from core_model.feedback.privacy_filter import assess_feedback_privacy, bounded_excerpt, redact_text
from core_model.feedback.safety_filter import assess_feedback_safety
from core_model.feedback.triage import compute_priority, route_to_queue_type

_SUBJECT_RESOLVERS: dict[str, str] = {
    "inference_result": "_resolve_inference_result",
    "rag_grounded_answer": "_resolve_rag_grounded_answer",
    "conversation_response": "_resolve_conversation_response",
    "evaluation_output": "_resolve_evaluation_output",
    "memory_orchestration_response": "_resolve_memory_orchestration_response",
    "release_candidate": "_resolve_release_candidate",
    "model_release": "_resolve_model_release",
}


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FeedbackService:
    def __init__(self, repository: FeedbackRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- policies -----------------------------------------------------

    def create_policy(self, payload: FeedbackPolicyCreate, admin_id: str) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        values["allowed_subject_types_json"] = dumps_json(values.pop("allowed_subject_types"))
        values["allowed_feedback_types_json"] = dumps_json(values.pop("allowed_feedback_types"))
        values["created_by_admin_public_id"] = admin_id
        with self.repository.transaction() as connection:
            public_id = self.repository.create_policy(connection, values)
            self._audit(connection, "feedback_policy_created", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    def list_policies(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_policies(connection)]}

    def get_policy(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.policy(connection, public_id))

    def patch_policy(
        self, public_id: str, payload: FeedbackPolicyPatch, admin_id: str
    ) -> dict[str, Any]:
        changes = payload.model_dump(exclude_unset=True, mode="json")
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, public_id)
            if policy["lifecycle_status"] not in {"draft", "validated"}:
                raise ValidationError("policy must be draft or validated to patch")
            self.repository.update_policy(connection, policy["id"], changes)
            self._audit(connection, "feedback_policy_patched", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    def validate_policy(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, public_id)
            if policy["maximum_feedback_characters"] <= 0:
                raise ValidationError("maximum_feedback_characters must be positive")
            self.repository.update_policy(
                connection, policy["id"], {"lifecycle_status": "validated"}
            )
            self._audit(connection, "feedback_policy_validated", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    def activate_policy(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, public_id)
            if policy["lifecycle_status"] != "validated":
                raise ValidationError("policy must be validated before activation")
            self.repository.update_policy(connection, policy["id"], {"lifecycle_status": "active"})
            self._audit(connection, "feedback_policy_activated", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    # --- subject lineage resolution -----------------------------------------------------

    def _resolve_inference_result(self, connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            """SELECT r.*, req.model_assignment_id, req.prompt_checksum_sha256
            FROM inference_results r JOIN inference_requests req ON req.id=r.inference_request_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise ValidationError("inference_result subject not found")
        return {
            "model_release_public_id": row["model_release_public_id"],
            "assignment_version_public_id": row["model_assignment_version_public_id"],
            "output_checksum_sha256": row["output_checksum_sha256"],
        }

    def _resolve_rag_grounded_answer(self, connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            """SELECT a.*, req.retrieval_run_id, rr.public_id AS retrieval_run_public_id
            FROM rag_grounded_answers a
            JOIN rag_grounded_requests req ON req.id=a.grounded_request_id
            JOIN rag_retrieval_runs rr ON rr.id=req.retrieval_run_id
            WHERE a.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise ValidationError("rag_grounded_answer subject not found")
        citations = connection.execute(
            "SELECT public_id FROM rag_answer_citations WHERE grounded_answer_id=?", (row["id"],)
        ).fetchall()
        return {
            "rag_retrieval_run_public_id": row["retrieval_run_public_id"],
            "citation_public_ids_json": dumps_json([c["public_id"] for c in citations]),
            "output_checksum_sha256": row["answer_checksum_sha256"] or _checksum(public_id),
        }

    def _resolve_conversation_response(self, connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            """SELECT t.*, s.public_id AS session_public_id
            FROM conversation_turns t JOIN conversation_sessions s ON s.id=t.session_id
            WHERE t.public_id=? AND t.role='assistant'""",
            (public_id,),
        ).fetchone()
        if not row:
            raise ValidationError("conversation_response subject not found")
        return {
            "conversation_session_public_id": row["session_public_id"],
            "output_checksum_sha256": row["content_checksum_sha256"],
        }

    def _resolve_evaluation_output(self, connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            """SELECT o.*, run.public_id AS run_public_id, run.model_evaluation_suite_id
            FROM model_evaluation_outputs o
            JOIN model_evaluation_runs run ON run.id=o.model_evaluation_run_id
            WHERE o.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise ValidationError("evaluation_output subject not found")
        suite = connection.execute(
            "SELECT public_id FROM model_evaluation_suites WHERE id=?",
            (row["model_evaluation_suite_id"],),
        ).fetchone()
        return {
            "evaluation_run_public_id": row["run_public_id"],
            "evaluation_suite_public_id": suite["public_id"] if suite else None,
            "output_checksum_sha256": row["output_checksum_sha256"],
        }

    def _resolve_memory_orchestration_response(self, connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            """SELECT g.*, orch.id AS orchestration_run_ref_id, orch.session_id,
            s.public_id AS session_public_id
            FROM chat_grounded_responses g
            JOIN chat_orchestration_runs orch ON orch.id=g.orchestration_run_id
            JOIN conversation_sessions s ON s.id=orch.session_id
            WHERE g.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise ValidationError("memory_orchestration_response subject not found")
        memory_items = connection.execute(
            """SELECT DISTINCT ci.source_public_id FROM chat_context_items ci
            WHERE ci.context_assembly_id = (
                SELECT context_assembly_id FROM chat_orchestration_runs WHERE id=?
            ) AND ci.item_type='memory_item' AND ci.included=1
            AND ci.source_public_id IS NOT NULL""",
            (row["orchestration_run_ref_id"],),
        ).fetchall()
        citations = connection.execute(
            "SELECT public_id FROM chat_response_citations WHERE grounded_response_id=?",
            (row["id"],),
        ).fetchall()
        return {
            "conversation_session_public_id": row["session_public_id"],
            "memory_item_public_ids_json": dumps_json([m["public_id"] for m in memory_items]),
            "citation_public_ids_json": dumps_json([c["public_id"] for c in citations]),
            "output_checksum_sha256": row["answer_checksum_sha256"] or _checksum(public_id),
        }

    def _resolve_release_candidate(self, connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM model_release_candidates WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise ValidationError("release_candidate subject not found")
        return {"output_checksum_sha256": _checksum(f"release_candidate:{public_id}")}

    def _resolve_model_release(self, connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM model_releases WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise ValidationError("model_release subject not found")
        return {
            "model_release_public_id": public_id,
            "output_checksum_sha256": _checksum(f"model_release:{public_id}"),
        }

    def resolve_subject(
        self, connection, subject_type: str, subject_reference_public_id: str
    ) -> dict[str, Any]:
        if subject_type not in SUBJECT_TYPES:
            raise ValidationError(f"unsupported subject type: {subject_type}")
        method_name = _SUBJECT_RESOLVERS[subject_type]
        lineage = getattr(self, method_name)(connection, subject_reference_public_id)
        lineage["subject_type"] = subject_type
        lineage["subject_reference_public_id"] = subject_reference_public_id
        return lineage

    # --- feedback events -----------------------------------------------------

    def submit_feedback(self, payload: FeedbackEventCreate, admin_id: str) -> dict[str, Any]:
        if payload.feedback_type not in FEEDBACK_TYPES:
            raise ValidationError("unsupported feedback_type")
        if payload.severity not in SEVERITIES:
            raise ValidationError("unsupported severity")

        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, payload.feedback_policy_public_id)
            if policy["lifecycle_status"] != "active":
                raise ValidationError("feedback policy must be active")

            lineage = self.resolve_subject(
                connection, payload.subject_type, payload.subject_reference_public_id
            )
            subject_public_id = self.repository.create_subject(connection, lineage)
            subject_row = self.repository.subject(connection, subject_public_id)

            privacy_status = "safe"
            safety_status = "safe"
            comment_text = None
            comment_checksum = None
            correction_text = None
            correction_checksum = None

            if payload.comment:
                comment_checksum = _checksum(payload.comment)
                if policy["require_privacy_scan"]:
                    privacy = assess_feedback_privacy(payload.comment)
                    privacy_status = privacy["status"]
                    if privacy_status == "blocked":
                        comment_text = None
                    elif privacy_status == "redacted":
                        comment_text = redact_text(payload.comment, privacy["matched_categories"])
                    else:
                        comment_text = bounded_excerpt(payload.comment, maximum_length=2000)
                else:
                    comment_text = bounded_excerpt(payload.comment, maximum_length=2000)
                if policy["require_safety_scan"]:
                    safety = assess_feedback_safety(payload.comment)
                    safety_status = safety["status"]
                    if safety_status == "blocked":
                        comment_text = None

            if payload.suggested_correction:
                correction_checksum = _checksum(payload.suggested_correction)
                correction_privacy = assess_feedback_privacy(payload.suggested_correction)
                if correction_privacy["status"] == "blocked":
                    if privacy_status != "blocked":
                        privacy_status = "blocked"
                    correction_text = None
                else:
                    correction_text = bounded_excerpt(
                        payload.suggested_correction, maximum_length=2000
                    )

            retention_expires_at = None
            if policy["default_retention_seconds"] > 0:
                retention_expires_at = _seconds_from_now(policy["default_retention_seconds"])

            event_public_id = self.repository.create_event(
                connection,
                {
                    "feedback_policy_id": policy["id"],
                    "subject_id": subject_row["id"],
                    "participant_scope_key": payload.participant_scope_key,
                    "feedback_type": payload.feedback_type,
                    "rating": payload.rating,
                    "comment_text": comment_text,
                    "comment_checksum_sha256": comment_checksum,
                    "suggested_correction_text": correction_text,
                    "suggested_correction_checksum_sha256": correction_checksum,
                    "expected_language": payload.expected_language,
                    "expected_citation_reference": payload.expected_citation_reference,
                    "expected_retrieval_source_reference": (
                        payload.expected_retrieval_source_reference
                    ),
                    "severity": payload.severity,
                    "privacy_status": privacy_status,
                    "safety_status": safety_status,
                    "retention_expires_at": retention_expires_at,
                    "created_by_admin_public_id": admin_id,
                },
            )

            event_row = self.repository.event(connection, event_public_id)
            if payload.comment and policy["require_privacy_scan"]:
                privacy = assess_feedback_privacy(payload.comment)
                for category in privacy["matched_categories"]:
                    self.repository.record_privacy_finding(
                        connection, event_id=event_row["id"], candidate_id=None,
                        category=category, status=privacy_status, details={},
                    )
            if payload.comment and policy["require_safety_scan"]:
                safety = assess_feedback_safety(payload.comment)
                for category in safety["matched_categories"]:
                    self.repository.record_safety_finding(
                        connection, event_id=event_row["id"], candidate_id=None,
                        category=category, status=safety_status, details={},
                    )

            self._audit(
                connection, "feedback_submitted", admin_id, event_public_id,
                feedback_type=payload.feedback_type, privacy_status=privacy_status,
                safety_status=safety_status,
            )
            return public_row(self.repository.event(connection, event_public_id))

    def get_event(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.event(connection, public_id))

    def list_events(self, *, participant_scope_key: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_events(
                connection, participant_scope_key=participant_scope_key
            )
            return {"items": [public_row(row) for row in rows]}

    def add_classification(
        self, event_public_id: str, category: str, severity: str, admin_id: str
    ) -> dict[str, Any]:
        allowed, reason = validate_classification(category, severity)
        if not allowed:
            raise ValidationError(f"classification rejected: {reason}")
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            self.repository.create_classification(connection, event["id"], category, severity)
            self._audit(
                connection, "feedback_classified", admin_id, event_public_id, category=category
            )
            return self.get_classifications(event_public_id)

    def get_classifications(self, event_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            rows = self.repository.classifications_for_event(connection, event["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_findings(self, event_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            findings = self.repository.findings_for_event(connection, event["id"])
            return {
                "privacy": [public_row(row) for row in findings["privacy"]],
                "safety": [public_row(row) for row in findings["safety"]],
            }

    def triage(self, event_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            if event["status"] != "submitted":
                raise ValidationError("event must be in submitted status to triage")
            classifications = [
                dict(row)["category"]
                for row in self.repository.classifications_for_event(connection, event["id"])
            ]
            severities = [
                dict(row)["severity"]
                for row in self.repository.classifications_for_event(connection, event["id"])
            ]
            explicit_severity = severities[0] if severities else event["severity"]
            priority = compute_priority(
                severity=explicit_severity,
                categories=classifications,
                privacy_status=event["privacy_status"],
                safety_status=event["safety_status"],
                rating=event["rating"],
                similar_open_feedback_count=0,
                is_regression_recurrence=False,
            )
            queue_type = route_to_queue_type(classifications)
            self.repository.update_event(
                connection, event["id"],
                {"status": "triaged", "severity": priority, "triaged_at": "CURRENT_TIMESTAMP"},
            )
            self._audit(
                connection, "feedback_triaged", admin_id, event_public_id,
                priority=priority, queue_type=queue_type,
            )
            result = public_row(self.repository.event(connection, event_public_id))
            result["recommended_queue_type"] = queue_type
            return result

    def delete_event(self, event_public_id: str, admin_id: str) -> dict[str, Any]:
        """Deletes raw feedback content -- retains only checksums and
        event metadata, matching the requirement that deleted feedback
        must not remain retrievable."""

        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            self.repository.update_event(
                connection, event["id"],
                {
                    "comment_text": None,
                    "suggested_correction_text": None,
                    "status": "deleted",
                    "deleted_at": "CURRENT_TIMESTAMP",
                },
            )
            self._audit(connection, "feedback_deleted", admin_id, event_public_id)
            return public_row(self.repository.event(connection, event_public_id))

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
                "feedback", resource_id, "success", dumps_json(metadata),
            ),
        )


def _seconds_from_now(seconds: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")
