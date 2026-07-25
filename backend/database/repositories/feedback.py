"""Repository for Phase 18 feedback events, classifications, attachments,
review queues/assignments/human reviews, corrected responses, privacy/
safety findings, dataset candidates/versions/issues/approvals,
regression suites/fixtures/runs/results, model comparisons, improvement
reports, and the feedback manifest."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "feedback_policy_id",
    "subject_id",
    "feedback_event_id",
    "queue_id",
    "candidate_id",
    "candidate_version_id",
    "current_version_id",
    "source_feedback_event_id",
    "source_subject_id",
    "source_corrected_response_id",
    "suite_id",
    "run_id",
    "fixture_id",
    "regression_suite_id",
    "left_run_id",
    "right_run_id",
    "model_assignment_id",
    "regression_run_id",
    "comparison_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("feedback row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class FeedbackRepository(BaseRepository):
    # --- policies -----------------------------------------------------

    def create_policy(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_policies(public_id,name,description,
            allowed_subject_types_json,allowed_feedback_types_json,allow_free_text,
            allow_corrected_response,require_privacy_scan,require_safety_scan,
            require_human_review,require_dataset_approval,maximum_feedback_characters,
            maximum_attachment_bytes,default_retention_seconds,
            allow_regression_fixture_creation,allow_dataset_candidate_creation,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("description", ""),
                values.get("allowed_subject_types_json", "[]"),
                values.get("allowed_feedback_types_json", "[]"),
                1 if values.get("allow_free_text", True) else 0,
                1 if values.get("allow_corrected_response", True) else 0,
                1 if values.get("require_privacy_scan", True) else 0,
                1 if values.get("require_safety_scan", True) else 0,
                1 if values.get("require_human_review", True) else 0,
                1 if values.get("require_dataset_approval", True) else 0,
                values.get("maximum_feedback_characters", 2000),
                values.get("maximum_attachment_bytes", 2_000_000),
                values.get("default_retention_seconds", 7_776_000),
                1 if values.get("allow_regression_fixture_creation", True) else 0,
                1 if values.get("allow_dataset_candidate_creation", True) else 0,
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def policy(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_policies WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("feedback policy not found")
        return row

    def list_policies(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_policies ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_policy(
        self, connection: sqlite3.Connection, policy_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE feedback_policies SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), policy_id),
        )

    # --- subjects -----------------------------------------------------

    def create_subject(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_subjects(public_id,subject_type,subject_reference_public_id,
            model_release_public_id,model_version_public_id,checkpoint_checksum_sha256,
            tokenizer_version_public_id,assignment_version_public_id,
            generation_configuration_json,rag_retrieval_run_public_id,citation_public_ids_json,
            memory_item_public_ids_json,conversation_session_public_id,
            evaluation_suite_public_id,evaluation_run_public_id,output_checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["subject_type"],
                values["subject_reference_public_id"],
                values.get("model_release_public_id"),
                values.get("model_version_public_id"),
                values.get("checkpoint_checksum_sha256"),
                values.get("tokenizer_version_public_id"),
                values.get("assignment_version_public_id"),
                values.get("generation_configuration_json", "{}"),
                values.get("rag_retrieval_run_public_id"),
                values.get("citation_public_ids_json", "[]"),
                values.get("memory_item_public_ids_json", "[]"),
                values.get("conversation_session_public_id"),
                values.get("evaluation_suite_public_id"),
                values.get("evaluation_run_public_id"),
                values["output_checksum_sha256"],
            ),
        )
        return public_id

    def subject(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_subjects WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("feedback subject not found")
        return row

    # --- events -----------------------------------------------------

    def create_event(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_events(public_id,feedback_policy_id,subject_id,
            participant_scope_key,feedback_type,rating,comment_text,comment_checksum_sha256,
            suggested_correction_text,suggested_correction_checksum_sha256,expected_language,
            expected_citation_reference,expected_retrieval_source_reference,severity,
            privacy_status,safety_status,retention_expires_at,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["feedback_policy_id"],
                values["subject_id"],
                values["participant_scope_key"],
                values["feedback_type"],
                values.get("rating"),
                values.get("comment_text"),
                values.get("comment_checksum_sha256"),
                values.get("suggested_correction_text"),
                values.get("suggested_correction_checksum_sha256"),
                values.get("expected_language"),
                values.get("expected_citation_reference"),
                values.get("expected_retrieval_source_reference"),
                values.get("severity", "info"),
                values.get("privacy_status", "requires_review"),
                values.get("safety_status", "requires_review"),
                values.get("retention_expires_at"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def event(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT e.*, p.public_id AS feedback_policy_public_id,
            s.public_id AS subject_public_id, s.subject_type AS subject_type_ref
            FROM feedback_events e
            JOIN feedback_policies p ON p.id=e.feedback_policy_id
            JOIN feedback_subjects s ON s.id=e.subject_id
            WHERE e.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("feedback event not found")
        return row

    def list_events(
        self, connection: sqlite3.Connection, *, participant_scope_key: str | None = None
    ) -> list[sqlite3.Row]:
        if participant_scope_key:
            return connection.execute(
                """SELECT * FROM feedback_events WHERE participant_scope_key=?
                ORDER BY created_at DESC, id DESC""",
                (participant_scope_key,),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM feedback_events ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_event(
        self, connection: sqlite3.Connection, event_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE feedback_events SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), event_id),
        )

    # --- classifications -----------------------------------------------------

    def create_classification(
        self, connection: sqlite3.Connection, event_id: int, category: str, severity: str,
        assigned_by: str = "admin",
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_classifications(public_id,feedback_event_id,category,
            severity,assigned_by) VALUES (?,?,?,?,?)""",
            (public_id, event_id, category, severity, assigned_by),
        )
        return public_id

    def classifications_for_event(
        self, connection: sqlite3.Connection, event_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_classifications WHERE feedback_event_id=? ORDER BY id",
            (event_id,),
        ).fetchall()

    # --- attachments -----------------------------------------------------

    def create_attachment(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_attachments(public_id,feedback_event_id,attachment_type,
            checksum_sha256,byte_size,mime_type) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["feedback_event_id"],
                values.get("attachment_type", "excerpt"),
                values["checksum_sha256"],
                values.get("byte_size", 0),
                values.get("mime_type"),
            ),
        )
        return public_id

    # --- privacy / safety findings -----------------------------------------------------

    def record_privacy_finding(
        self, connection: sqlite3.Connection, *, event_id: int | None, candidate_id: int | None,
        category: str, status: str, details: dict[str, Any],
    ) -> str:
        from backend.core.json_utils import dumps_json

        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_privacy_findings(public_id,feedback_event_id,candidate_id,
            category,status,details_json) VALUES (?,?,?,?,?,?)""",
            (public_id, event_id, candidate_id, category, status, dumps_json(details)),
        )
        return public_id

    def record_safety_finding(
        self, connection: sqlite3.Connection, *, event_id: int | None, candidate_id: int | None,
        category: str, status: str, details: dict[str, Any],
    ) -> str:
        from backend.core.json_utils import dumps_json

        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_safety_findings(public_id,feedback_event_id,candidate_id,
            category,status,details_json) VALUES (?,?,?,?,?,?)""",
            (public_id, event_id, candidate_id, category, status, dumps_json(details)),
        )
        return public_id

    def findings_for_event(self, connection: sqlite3.Connection, event_id: int) -> dict[str, Any]:
        privacy = connection.execute(
            "SELECT * FROM feedback_privacy_findings WHERE feedback_event_id=? ORDER BY id",
            (event_id,),
        ).fetchall()
        safety = connection.execute(
            "SELECT * FROM feedback_safety_findings WHERE feedback_event_id=? ORDER BY id",
            (event_id,),
        ).fetchall()
        return {"privacy": privacy, "safety": safety}

    # --- review queues -----------------------------------------------------

    def create_queue(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_review_queues(public_id,name,queue_type,description,
            created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                public_id, values["name"], values["queue_type"], values.get("description", ""),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def queue(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_review_queues WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("review queue not found")
        return row

    def list_queues(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_review_queues ORDER BY created_at DESC, id DESC"
        ).fetchall()

    # --- review assignments -----------------------------------------------------

    def create_assignment(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_review_assignments(public_id,queue_id,feedback_event_id,
            reviewer_admin_public_id,due_at,priority,conflict_of_interest_flag)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["queue_id"],
                values["feedback_event_id"],
                values["reviewer_admin_public_id"],
                values.get("due_at"),
                values.get("priority", "medium"),
                1 if values.get("conflict_of_interest_flag", False) else 0,
            ),
        )
        return public_id

    def assignments_for_queue(
        self, connection: sqlite3.Connection, queue_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM feedback_review_assignments WHERE queue_id=?
            ORDER BY created_at DESC, id DESC""",
            (queue_id,),
        ).fetchall()

    def update_assignment(
        self, connection: sqlite3.Connection, assignment_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE feedback_review_assignments SET {columns} WHERE id=?",
            (*fields.values(), assignment_id),
        )

    def count_active_assignments(self, connection: sqlite3.Connection) -> int:
        return connection.execute(
            "SELECT COUNT(*) FROM feedback_review_assignments WHERE status IN "
            "('assigned','in_progress')"
        ).fetchone()[0]

    # --- human reviews -----------------------------------------------------

    def create_human_review(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_human_reviews(public_id,feedback_event_id,
            reviewer_admin_public_id,rubric_version,classification_confirmed,
            severity_confirmed,correctness_score,relevance_score,language_quality_score,
            safety_score,citation_score,retrieval_score,memory_use_score,overall_score,
            verdict,comment) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["feedback_event_id"],
                values["reviewer_admin_public_id"],
                values.get("rubric_version", "1"),
                values.get("classification_confirmed"),
                values.get("severity_confirmed"),
                values.get("correctness_score"),
                values.get("relevance_score"),
                values.get("language_quality_score"),
                values.get("safety_score"),
                values.get("citation_score"),
                values.get("retrieval_score"),
                values.get("memory_use_score"),
                values["overall_score"],
                values["verdict"],
                values.get("comment", ""),
            ),
        )
        return public_id

    def reviews_for_event(self, connection: sqlite3.Connection, event_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_human_reviews WHERE feedback_event_id=? ORDER BY id",
            (event_id,),
        ).fetchall()

    # --- corrected responses -----------------------------------------------------

    def create_corrected_response(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_corrected_responses(public_id,feedback_event_id,
            original_output_checksum_sha256,corrected_response_text,
            corrected_response_checksum_sha256,language,citation_map_json,memory_use_policy,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["feedback_event_id"],
                values["original_output_checksum_sha256"],
                values["corrected_response_text"],
                values["corrected_response_checksum_sha256"],
                values.get("language", "unknown"),
                values.get("citation_map_json", "[]"),
                values.get("memory_use_policy", "none"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def corrected_response(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_corrected_responses WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corrected response not found")
        return row

    def corrected_responses_for_event(
        self, connection: sqlite3.Connection, event_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM feedback_corrected_responses WHERE feedback_event_id=?
            ORDER BY created_at DESC, id DESC""",
            (event_id,),
        ).fetchall()

    def update_corrected_response(
        self, connection: sqlite3.Connection, correction_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE feedback_corrected_responses SET {columns} WHERE id=?",
            (*fields.values(), correction_id),
        )

    # --- dataset candidates -----------------------------------------------------

    def create_candidate(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_dataset_candidates(public_id,source_feedback_event_id,
            source_subject_id,source_corrected_response_id,candidate_type,
            failed_model_version_public_id,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["source_feedback_event_id"],
                values["source_subject_id"],
                values.get("source_corrected_response_id"),
                values["candidate_type"],
                values.get("failed_model_version_public_id"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def candidate(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_dataset_candidates WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("dataset candidate not found")
        return row

    def list_candidates(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_dataset_candidates ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_candidate(
        self, connection: sqlite3.Connection, candidate_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE feedback_dataset_candidates SET {columns}, updated_at=CURRENT_TIMESTAMP "
            f"WHERE id=?",
            (*fields.values(), candidate_id),
        )

    # --- candidate versions -----------------------------------------------------

    def create_candidate_version(
        self, connection: sqlite3.Connection, candidate_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        next_version = connection.execute(
            "SELECT COALESCE(MAX(version_number),0)+1 FROM feedback_candidate_versions "
            "WHERE candidate_id=?",
            (candidate_id,),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO feedback_candidate_versions(public_id,candidate_id,version_number,
            prompt_text,input_text,output_text,language,prompt_checksum_sha256,
            output_checksum_sha256,metadata_checksum_sha256,change_reason,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                candidate_id,
                next_version,
                values["prompt_text"],
                values.get("input_text"),
                values["output_text"],
                values.get("language", "unknown"),
                values["prompt_checksum_sha256"],
                values["output_checksum_sha256"],
                values["metadata_checksum_sha256"],
                values["change_reason"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def candidate_version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_candidate_versions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("candidate version not found")
        return row

    def versions_for_candidate(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM feedback_candidate_versions WHERE candidate_id=?
            ORDER BY version_number""",
            (candidate_id,),
        ).fetchall()

    # --- candidate issues -----------------------------------------------------

    def record_candidate_issue(
        self, connection: sqlite3.Connection, *, candidate_id: int, issue_code: str,
        severity: str, details: dict[str, Any],
    ) -> str:
        from backend.core.json_utils import dumps_json

        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_candidate_issues(public_id,candidate_id,issue_code,
            severity,details_json) VALUES (?,?,?,?,?)""",
            (public_id, candidate_id, issue_code, severity, dumps_json(details)),
        )
        return public_id

    def issues_for_candidate(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_candidate_issues WHERE candidate_id=? ORDER BY id",
            (candidate_id,),
        ).fetchall()

    # --- candidate approvals -----------------------------------------------------

    def record_candidate_approval(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_candidate_approvals(public_id,candidate_id,
            candidate_version_id,decision,review_evidence_checksum_sha256,privacy_assessment,
            safety_assessment,deduplication_result,contamination_result,licence_result,
            intended_use_decision,admin_public_id,comment) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["candidate_id"],
                values["candidate_version_id"],
                values["decision"],
                values.get("review_evidence_checksum_sha256"),
                values["privacy_assessment"],
                values["safety_assessment"],
                values["deduplication_result"],
                values["contamination_result"],
                values["licence_result"],
                values.get("intended_use_decision", "training_candidate"),
                values["admin_public_id"],
                values.get("comment", ""),
            ),
        )
        return public_id

    def approvals_for_candidate(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM feedback_candidate_approvals WHERE candidate_id=?
            ORDER BY created_at DESC, id DESC""",
            (candidate_id,),
        ).fetchall()

    # --- quality assessments -----------------------------------------------------

    def record_quality_assessment(
        self, connection: sqlite3.Connection, *, candidate_id: int, dimension: str, status: str,
        details: dict[str, Any],
    ) -> str:
        from backend.core.json_utils import dumps_json

        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_quality_assessments(public_id,candidate_id,dimension,
            status,details_json) VALUES (?,?,?,?,?)""",
            (public_id, candidate_id, dimension, status, dumps_json(details)),
        )
        return public_id

    def quality_assessments_for_candidate(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_quality_assessments WHERE candidate_id=? ORDER BY id",
            (candidate_id,),
        ).fetchall()

    # --- regression suites -----------------------------------------------------

    def create_regression_suite(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_regression_suites(public_id,name,description,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                public_id, values["name"], values.get("description", ""),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def regression_suite(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_regression_suites WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("regression suite not found")
        return row

    def list_regression_suites(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_regression_suites ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_regression_suite(
        self, connection: sqlite3.Connection, suite_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE feedback_regression_suites SET {columns}, updated_at=CURRENT_TIMESTAMP "
            f"WHERE id=?",
            (*fields.values(), suite_id),
        )

    # --- regression fixtures -----------------------------------------------------

    def create_regression_fixture(
        self, connection: sqlite3.Connection, suite_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_regression_fixtures(public_id,suite_id,category,language,
            input_text,controlled_context_json,expected_behavior,forbidden_behavior,
            expected_citations_json,expected_memory_behavior_json,severity,
            source_feedback_event_ids_json,checksum_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                suite_id,
                values["category"],
                values.get("language", "unknown"),
                values["input_text"],
                values.get("controlled_context_json", "{}"),
                values["expected_behavior"],
                values.get("forbidden_behavior"),
                values.get("expected_citations_json", "[]"),
                values.get("expected_memory_behavior_json", "{}"),
                values.get("severity", "medium"),
                values.get("source_feedback_event_ids_json", "[]"),
                values["checksum_sha256"],
            ),
        )
        return public_id

    def fixtures_for_suite(
        self, connection: sqlite3.Connection, suite_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_regression_fixtures WHERE suite_id=? ORDER BY id",
            (suite_id,),
        ).fetchall()

    def fixture(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_regression_fixtures WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("regression fixture not found")
        return row

    # --- regression runs -----------------------------------------------------

    def create_regression_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_regression_runs(public_id,suite_id,model_assignment_id,
            generation_configuration_checksum_sha256,created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["suite_id"],
                values["model_assignment_id"],
                values.get("generation_configuration_checksum_sha256"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def regression_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*, s.public_id AS suite_public_id, s.checksum_sha256 AS suite_checksum
            FROM feedback_regression_runs r
            JOIN feedback_regression_suites s ON s.id=r.suite_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("regression run not found")
        return row

    def update_regression_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE feedback_regression_runs SET {columns} WHERE id=?",
            (*fields.values(), run_id),
        )

    def count_active_regression_runs(self, connection: sqlite3.Connection) -> int:
        return connection.execute(
            "SELECT COUNT(*) FROM feedback_regression_runs WHERE status IN ('queued','running')"
        ).fetchone()[0]

    # --- regression results -----------------------------------------------------

    def record_regression_result(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        from backend.core.json_utils import dumps_json

        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_regression_results(public_id,run_id,fixture_id,passed,
            failure_reason,details_json) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["run_id"],
                values["fixture_id"],
                1 if values["passed"] else 0,
                values.get("failure_reason"),
                dumps_json(values.get("details", {})),
            ),
        )
        return public_id

    def results_for_run(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM feedback_regression_results WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()

    # --- model comparisons -----------------------------------------------------

    def create_comparison(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_model_comparisons(public_id,regression_suite_id,left_run_id,
            right_run_id,compatibility,comparison_result,fixed_failure_rate,
            persistent_failure_rate,new_regression_rate,language_regression_rate,
            citation_regression_rate,safety_regression_rate,memory_regression_rate,
            privacy_regression_rate,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["regression_suite_id"],
                values["left_run_id"],
                values["right_run_id"],
                values["compatibility"],
                values["comparison_result"],
                values.get("fixed_failure_rate"),
                values.get("persistent_failure_rate"),
                values.get("new_regression_rate"),
                values.get("language_regression_rate"),
                values.get("citation_regression_rate"),
                values.get("safety_regression_rate"),
                values.get("memory_regression_rate"),
                values.get("privacy_regression_rate"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def comparison(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_model_comparisons WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("model comparison not found")
        return row

    # --- improvement reports -----------------------------------------------------

    def create_improvement_report(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_improvement_reports(public_id,feedback_policy_id,
            regression_run_id,comparison_id,report_json,report_checksum_sha256,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values.get("feedback_policy_id"),
                values.get("regression_run_id"),
                values.get("comparison_id"),
                values["report_json"],
                values["report_checksum_sha256"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def improvement_report(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM feedback_improvement_reports WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("improvement report not found")
        return row

    # --- manifests -----------------------------------------------------

    def create_manifest(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO feedback_manifests(public_id,feedback_policy_id,manifest_json,
            manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (
                public_id,
                values["feedback_policy_id"],
                values["manifest_json"],
                values["manifest_checksum_sha256"],
            ),
        )
        return public_id

    def latest_manifest_for_policy(
        self, connection: sqlite3.Connection, policy_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM feedback_manifests WHERE feedback_policy_id=?
            ORDER BY created_at DESC, id DESC LIMIT 1""",
            (policy_id,),
        ).fetchone()
