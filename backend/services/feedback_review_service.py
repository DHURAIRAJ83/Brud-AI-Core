"""Phase 18 human review queues, review assignments, human reviews, and
corrected responses.

Reviews are append-only: multiple reviewers may review the same
feedback event, and disagreement is measured explicitly rather than
silently averaged away. A corrected response is a proposed
replacement, never an in-place rewrite of the model's original output.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.feedback import FeedbackRepository, public_row
from backend.models.feedback import (
    CorrectedResponseCreate,
    HumanReviewCreate,
    ReviewAssignmentCreate,
    ReviewQueueCreate,
)
from core_model.feedback import QUEUE_TYPES, REVIEW_VERDICTS
from core_model.feedback.correction_validation import validate_correction
from core_model.feedback.quality_scoring import assess_review_disagreement


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FeedbackReviewService:
    def __init__(self, repository: FeedbackRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- review queues -----------------------------------------------------

    def create_queue(self, payload: ReviewQueueCreate, admin_id: str) -> dict[str, Any]:
        if payload.queue_type not in QUEUE_TYPES:
            raise ValidationError("unsupported queue_type")
        with self.repository.transaction() as connection:
            public_id = self.repository.create_queue(
                connection,
                {
                    "name": payload.name,
                    "queue_type": payload.queue_type,
                    "description": payload.description,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "feedback_review_queue_created", admin_id, public_id)
            return public_row(self.repository.queue(connection, public_id))

    def list_queues(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_queues(connection)]}

    def get_queue(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.queue(connection, public_id))

    def assign_review(
        self, queue_public_id: str, payload: ReviewAssignmentCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            queue = self.repository.queue(connection, queue_public_id)
            event = self.repository.event(connection, payload.feedback_event_public_id)
            reviewer = connection.execute(
                "SELECT 1 FROM admin_accounts WHERE public_id=?",
                (payload.reviewer_admin_public_id,),
            ).fetchone()
            if not reviewer:
                raise ValidationError("reviewer admin not found")
            active_count = self.repository.count_active_assignments(connection)
            if active_count >= self.settings.feedback_max_active_review_assignments:
                raise ValidationError("maximum active review assignments reached")
            public_id = self.repository.create_assignment(
                connection,
                {
                    "queue_id": queue["id"],
                    "feedback_event_id": event["id"],
                    "reviewer_admin_public_id": payload.reviewer_admin_public_id,
                    "due_at": payload.due_at,
                    "priority": payload.priority,
                    "conflict_of_interest_flag": payload.conflict_of_interest_flag,
                },
            )
            self.repository.update_event(connection, event["id"], {"status": "in_review"})
            self._audit(
                connection, "feedback_review_assigned", admin_id, public_id,
                reviewer=payload.reviewer_admin_public_id,
            )
            rows = self.repository.assignments_for_queue(connection, queue["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_queue_items(self, queue_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            queue = self.repository.queue(connection, queue_public_id)
            rows = self.repository.assignments_for_queue(connection, queue["id"])
            return {"items": [public_row(row) for row in rows]}

    # --- human reviews -----------------------------------------------------

    def create_review(
        self, event_public_id: str, payload: HumanReviewCreate, admin_id: str
    ) -> dict[str, Any]:
        if payload.verdict not in REVIEW_VERDICTS:
            raise ValidationError("unsupported verdict")
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            review_public_id = self.repository.create_human_review(
                connection,
                {
                    "feedback_event_id": event["id"],
                    "reviewer_admin_public_id": admin_id,
                    "rubric_version": payload.rubric_version,
                    "classification_confirmed": payload.classification_confirmed,
                    "severity_confirmed": payload.severity_confirmed,
                    "correctness_score": payload.correctness_score,
                    "relevance_score": payload.relevance_score,
                    "language_quality_score": payload.language_quality_score,
                    "safety_score": payload.safety_score,
                    "citation_score": payload.citation_score,
                    "retrieval_score": payload.retrieval_score,
                    "memory_use_score": payload.memory_use_score,
                    "overall_score": payload.overall_score,
                    "verdict": payload.verdict,
                    "comment": payload.comment,
                },
            )
            active_assignments = connection.execute(
                """SELECT id FROM feedback_review_assignments
                WHERE feedback_event_id=? AND reviewer_admin_public_id=?
                AND status IN ('assigned','in_progress')""",
                (event["id"], admin_id),
            ).fetchall()
            for assignment_row in active_assignments:
                self.repository.update_assignment(
                    connection, assignment_row["id"], {"status": "completed"}
                )
            if payload.verdict in {"privacy_blocked", "safety_blocked"}:
                self.repository.update_event(connection, event["id"], {"status": "rejected"})
            else:
                self.repository.update_event(connection, event["id"], {"status": "reviewed"})
            self._audit(
                connection, "feedback_review_completed", admin_id, review_public_id,
                verdict=payload.verdict,
            )
            return self._review_summary(connection, event_public_id, event["id"])

    def get_reviews(self, event_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            rows = self.repository.reviews_for_event(connection, event["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_review_summary(self, event_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            return self._review_summary(connection, event_public_id, event["id"])

    def _review_summary(self, connection, event_public_id: str, event_id: int) -> dict[str, Any]:
        rows = [dict(row) for row in self.repository.reviews_for_event(connection, event_id)]
        disagreement = assess_review_disagreement(rows)
        return {
            "feedback_event_public_id": event_public_id,
            "review_count": len(rows),
            "reviews": [public_row_dict(row) for row in rows],
            "disagreement": disagreement,
        }

    # --- corrected responses -----------------------------------------------------

    def create_corrected_response(
        self, event_public_id: str, payload: CorrectedResponseCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            subject = connection.execute(
                "SELECT * FROM feedback_subjects WHERE id=?", (event["subject_id"],)
            ).fetchone()

            existing = self.repository.corrected_responses_for_event(connection, event["id"])
            for prior in existing:
                if prior["validation_status"] not in {"rejected", "superseded"}:
                    self.repository.update_corrected_response(
                        connection, prior["id"], {"validation_status": "superseded"}
                    )

            corrected_checksum = _checksum(payload.corrected_response_text)
            public_id = self.repository.create_corrected_response(
                connection,
                {
                    "feedback_event_id": event["id"],
                    "original_output_checksum_sha256": subject["output_checksum_sha256"],
                    "corrected_response_text": payload.corrected_response_text,
                    "corrected_response_checksum_sha256": corrected_checksum,
                    "language": payload.language,
                    "citation_map_json": dumps_json(payload.citation_ids),
                    "memory_use_policy": payload.memory_use_policy,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "feedback_correction_created", admin_id, public_id)
            return public_row(self.repository.corrected_response(connection, public_id))

    def list_corrected_responses(self, event_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            rows = self.repository.corrected_responses_for_event(connection, event["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_corrected_response(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.corrected_response(connection, public_id))

    def validate_corrected_response(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            correction = self.repository.corrected_response(connection, public_id)
            if correction["validation_status"] not in {"draft"}:
                raise ValidationError("correction must be draft to validate")
            event = connection.execute(
                "SELECT * FROM feedback_events WHERE id=?", (correction["feedback_event_id"],)
            ).fetchone()
            subject = connection.execute(
                "SELECT * FROM feedback_subjects WHERE id=?", (event["subject_id"],)
            ).fetchone()

            citation_ids = loads_json(correction["citation_map_json"])
            accessible_citation_ids = set(loads_json(subject["citation_public_ids_json"]))
            result = validate_correction(
                corrected_text=correction["corrected_response_text"],
                requested_language=event["expected_language"],
                system_text=None,
                original_prompt_text=None,
                citation_ids=citation_ids,
                accessible_citation_ids=accessible_citation_ids,
                correction_checksum=correction["corrected_response_checksum_sha256"],
            )
            self.repository.update_corrected_response(
                connection, correction["id"],
                {
                    "validation_status": result["status"],
                    "validation_issues_json": dumps_json(result["issues"]),
                    "validated_at": "CURRENT_TIMESTAMP",
                },
            )
            self._audit(
                connection, "feedback_correction_validated", admin_id, public_id,
                status=result["status"],
            )
            return public_row(self.repository.corrected_response(connection, public_id))

    def reject_corrected_response(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            correction = self.repository.corrected_response(connection, public_id)
            self.repository.update_corrected_response(
                connection, correction["id"], {"validation_status": "rejected"}
            )
            self._audit(connection, "feedback_correction_rejected", admin_id, public_id)
            return public_row(self.repository.corrected_response(connection, public_id))

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


def public_row_dict(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    for key in ("id", "feedback_event_id"):
        data.pop(key, None)
    return data
