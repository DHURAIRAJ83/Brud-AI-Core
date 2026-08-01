"""Repository for the Phase 14 Training Dataset Promotion, Incremental
Language Training, Checkpoint Evaluation & Admin Approval workflow:
assessments, assessment items, example candidates/revisions, replay
plans, dataset promotion requests, run requests/approvals/runs/events,
checkpoints, evaluations, comparisons, human reviews, reports, and
checkpoint acceptances.

Reads (never writes) Phase 11/12/13's own tables. Writes governance
rows only -- actual dataset-version build/split/checksum and
training/checkpoint/evaluation mechanics live in the existing,
unmodified `DatasetVersioningService`/`InstructionTuningService`/
`PretrainingService`/`TrainingEvaluationService`. Never writes
`core_model_versions.lifecycle_status='active'`. See
docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError, ValidationError


def _assessment_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "assessment_code": row["assessment_code"],
        "sample_import_public_id": row["sample_import_public_id"],
        "rag_sandbox_experiment_public_id": row["rag_sandbox_experiment_public_id"],
        "verification_case_public_id": row["verification_case_public_id"],
        "status": row["status"],
        "current_stage": row["current_stage"],
        "sample_report_checksum": row["sample_report_checksum"],
        "rag_sandbox_report_checksum": row["rag_sandbox_report_checksum"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _item_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "assessment_public_id": row["assessment_public_id"],
        "sample_record_public_id": row["sample_record_public_id"],
        "rag_sandbox_record_public_id": row["rag_sandbox_record_public_id"],
        "record_category": row["record_category"],
        "suitability_status": row["suitability_status"],
        "dimension_results": loads_json(row["dimension_results_json"]),
        "reason": row["reason"],
        "contamination_flagged": bool(row["contamination_flagged"]),
        "created_at": row["created_at"],
    }


def _candidate_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "assessment_item_public_id": row["assessment_item_public_id"],
        "source_sample_record_public_id": row["source_sample_record_public_id"],
        "source_rag_sandbox_record_public_id": row["source_rag_sandbox_record_public_id"],
        "transformation_type": row["transformation_type"],
        "prompt_text": row["prompt_text"],
        "assistant_text": row["assistant_text"],
        "language": row["language"],
        "task": row["task"],
        "source_checksum": row["source_checksum"],
        "candidate_checksum": row["candidate_checksum"],
        "transformation_version": row["transformation_version"],
        "review_status": row["review_status"],
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
        "conditions": loads_json(row["conditions_json"]),
        "dataset_record_public_id": row["dataset_record_public_id"],
        "created_at": row["created_at"],
    }


def _revision_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "decision": row["decision"],
        "reason": row["reason"],
        "revised_prompt_text": row["revised_prompt_text"],
        "revised_assistant_text": row["revised_assistant_text"],
        "revised_checksum": row["revised_checksum"],
        "reviewer_admin_public_id": row["reviewer_admin_public_id"],
        "created_at": row["created_at"],
    }


def _replay_plan_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "assessment_public_id": row["assessment_public_id"],
        "new_record_count": row["new_record_count"],
        "replay_record_count": row["replay_record_count"],
        "new_data_ratio": row["new_data_ratio"],
        "replay_data_ratio": row["replay_data_ratio"],
        "replay_source_version_ids": loads_json(row["replay_source_version_ids_json"]),
        "replay_record_ids": loads_json(row["replay_record_ids_json"]),
        "language_distribution": loads_json(row["language_distribution_json"]),
        "task_distribution": loads_json(row["task_distribution_json"]),
        "domain_distribution": loads_json(row["domain_distribution_json"]),
        "selection_method": row["selection_method"],
        "selection_seed": row["selection_seed"],
        "reason": row["reason"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _promotion_request_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "assessment_public_id": row["assessment_public_id"],
        "replay_plan_public_id": row["replay_plan_public_id"],
        "selected_candidate_ids": loads_json(row["selected_candidate_ids_json"]),
        "status": row["status"],
        "approved_by_admin_id": row["approved_by_admin_id"],
        "approved_at": row["approved_at"],
        "expires_at": row["expires_at"],
        "target_fingerprint": row["target_fingerprint"],
        "dataset_version_public_id": row["dataset_version_public_id"],
        "train_split_checksum": row["train_split_checksum"],
        "validation_split_checksum": row["validation_split_checksum"],
        "test_split_checksum": row["test_split_checksum"],
        "lineage_manifest": loads_json(row["lineage_manifest_json"]),
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _run_request_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "promotion_request_public_id": row["promotion_request_public_id"],
        "dataset_version_public_id": row["dataset_version_public_id"],
        "base_checkpoint_public_id": row["base_checkpoint_public_id"],
        "tokenizer_version_public_id": row["tokenizer_version_public_id"],
        "training_strategy": row["training_strategy"],
        "configuration": loads_json(row["configuration_json"]),
        "configuration_checksum": row["configuration_checksum"],
        "resource_preview": loads_json(row["resource_preview_json"]),
        "resource_preview_checksum": row["resource_preview_checksum"],
        "execution_target": row["execution_target"],
        "status": row["status"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _run_approval_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "run_request_public_id": row["run_request_public_id"],
        "dataset_version_public_id": row["dataset_version_public_id"],
        "base_checkpoint_public_id": row["base_checkpoint_public_id"],
        "tokenizer_version_public_id": row["tokenizer_version_public_id"],
        "training_strategy": row["training_strategy"],
        "configuration_checksum": row["configuration_checksum"],
        "resource_preview_checksum": row["resource_preview_checksum"],
        "replay_plan_public_id": row["replay_plan_public_id"],
        "train_split_checksum": row["train_split_checksum"],
        "validation_split_checksum": row["validation_split_checksum"],
        "test_split_checksum": row["test_split_checksum"],
        "approved_by_admin_id": row["approved_by_admin_id"],
        "approved_at": row["approved_at"],
        "expires_at": row["expires_at"],
        "target_fingerprint": row["target_fingerprint"],
        "conditions": loads_json(row["conditions_json"]),
        "status": row["status"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _run_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "run_request_public_id": row["run_request_public_id"],
        "run_approval_public_id": row["run_approval_public_id"],
        "underlying_run_kind": row["underlying_run_kind"],
        "underlying_run_public_id": row["underlying_run_public_id"],
        "status": row["status"],
        "current_epoch": row["current_epoch"],
        "current_step": row["current_step"],
        "latest_training_loss": row["latest_training_loss"],
        "latest_validation_loss": row["latest_validation_loss"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _run_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "run_public_id": row["run_public_id"],
        "event_type": row["event_type"],
        "from_status": row["from_status"],
        "to_status": row["to_status"],
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _checkpoint_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "run_public_id": row["run_public_id"],
        "underlying_checkpoint_public_id": row["underlying_checkpoint_public_id"],
        "parent_checkpoint_public_id": row["parent_checkpoint_public_id"],
        "epoch": row["epoch"],
        "step": row["step"],
        "tokens_seen": row["tokens_seen"],
        "training_loss": row["training_loss"],
        "validation_loss": row["validation_loss"],
        "checkpoint_checksum": row["checkpoint_checksum"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _evaluation_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "checkpoint_public_id": row["checkpoint_public_id"],
        "evaluation_type": row["evaluation_type"],
        "result_status": row["result_status"],
        "automated": bool(row["automated"]),
        "score": row["score"],
        "details": loads_json(row["details_json"]),
        "evaluation_version": row["evaluation_version"],
        "created_at": row["created_at"],
    }


def _comparison_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "checkpoint_public_id": row["checkpoint_public_id"],
        "parent_checkpoint_public_id": row["parent_checkpoint_public_id"],
        "comparison_type": row["comparison_type"],
        "dimension": row["dimension"],
        "result_status": row["result_status"],
        "metrics": loads_json(row["metrics_json"]),
        "source_evaluation_ids": loads_json(row["source_evaluation_ids_json"]),
        "created_at": row["created_at"],
    }


def _human_review_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "checkpoint_public_id": row["checkpoint_public_id"],
        "prompt_text": row["prompt_text"],
        "tamil_fluency": _optional_bool(row["tamil_fluency"]),
        "english_fluency": _optional_bool(row["english_fluency"]),
        "tanglish_readability": _optional_bool(row["tanglish_readability"]),
        "instruction_following": _optional_bool(row["instruction_following"]),
        "helpfulness": _optional_bool(row["helpfulness"]),
        "correct_refusal": _optional_bool(row["correct_refusal"]),
        "hallucination_risk": _optional_bool(row["hallucination_risk"]),
        "repetition": _optional_bool(row["repetition"]),
        "formatting": _optional_bool(row["formatting"]),
        "regression": _optional_bool(row["regression"]),
        "decision": row["decision"],
        "notes": row["notes"],
        "reviewer_admin_public_id": row["reviewer_admin_public_id"],
        "reviewed_at": row["reviewed_at"],
        "created_at": row["created_at"],
    }


def _optional_bool(value: int | None) -> bool | None:
    return None if value is None else bool(value)


def _report_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "run_public_id": row["run_public_id"],
        "report_version": row["report_version"],
        "report": loads_json(row["report_json"]),
        "report_checksum_sha256": row["report_checksum_sha256"],
        "checkpoint_recommendation": row["checkpoint_recommendation"],
        "production_release_readiness": row["production_release_readiness"],
        "recommended_next_action": row["recommended_next_action"],
        "finalized_by_admin_public_id": row["finalized_by_admin_public_id"],
        "finalized_at": row["finalized_at"],
        "created_at": row["created_at"],
    }


def _acceptance_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "checkpoint_public_id": row["checkpoint_public_id"],
        "report_public_id": row["report_public_id"],
        "decision": row["decision"],
        "reason": row["reason"],
        "conditions": loads_json(row["conditions_json"]),
        "reviewer_admin_public_id": row["reviewer_admin_public_id"],
        "reviewed_at": row["reviewed_at"],
        "report_checksum_sha256": row["report_checksum_sha256"],
        "checkpoint_checksum": row["checkpoint_checksum"],
        "target_fingerprint": row["target_fingerprint"],
        "model_candidate_public_id": row["model_candidate_public_id"],
        "created_at": row["created_at"],
    }


class TrainingIncrementalRepository(BaseRepository):
    # -- shared lookups -------------------------------------------------------------

    def _assessment_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM training_data_assessments WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("training data assessment not found")
        return row["id"]

    def _item_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM training_data_assessment_items WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("assessment item not found")
        return row["id"]

    def _candidate_row(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM training_example_candidates WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("training example candidate not found")
        return row

    def _replay_plan_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM training_replay_plans WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("replay plan not found")
        return row["id"]

    def _promotion_request_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM training_dataset_promotion_requests WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("dataset promotion request not found")
        return row["id"]

    def _run_request_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM incremental_training_run_requests WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("training run request not found")
        return row["id"]

    def _run_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM incremental_training_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("incremental training run not found")
        return row["id"]

    def _checkpoint_row(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM incremental_training_checkpoints WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("incremental training checkpoint not found")
        return row

    def _report_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM incremental_training_reports WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("training report not found")
        return row["id"]

    # -- assessments -----------------------------------------------------------------

    def create_assessment(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            sample_import_id = None
            if values.get("sample_import_public_id"):
                row = connection.execute(
                    "SELECT id FROM external_dataset_sample_imports WHERE public_id=?",
                    (values["sample_import_public_id"],),
                ).fetchone()
                if not row:
                    raise NotFoundError("sample import not found")
                sample_import_id = row["id"]
            rag_sandbox_experiment_id = None
            if values.get("rag_sandbox_experiment_public_id"):
                row = connection.execute(
                    "SELECT id FROM rag_sandbox_experiments WHERE public_id=?",
                    (values["rag_sandbox_experiment_public_id"],),
                ).fetchone()
                if not row:
                    raise NotFoundError("rag sandbox experiment not found")
                rag_sandbox_experiment_id = row["id"]
            verification_row = connection.execute(
                "SELECT id FROM external_dataset_verification_cases WHERE public_id=?",
                (values["verification_case_public_id"],),
            ).fetchone()
            if not verification_row:
                raise NotFoundError("verification case not found")
            connection.execute(
                """INSERT INTO training_data_assessments(
                public_id, assessment_code, sample_import_id, rag_sandbox_experiment_id,
                verification_case_id, sample_report_checksum, rag_sandbox_report_checksum,
                created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    values["assessment_code"],
                    sample_import_id,
                    rag_sandbox_experiment_id,
                    verification_row["id"],
                    values.get("sample_report_checksum"),
                    values.get("rag_sandbox_report_checksum"),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_assessment(public_id)

    def get_assessment(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._assessment_select_sql() + " WHERE a.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("training data assessment not found")
        return _assessment_public(row)

    def list_assessments(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("a.status=?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._assessment_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY a.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_assessment_public(row) for row in rows]

    def update_assessment(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_assessment(public_id)
        with self.transaction() as connection:
            self._assessment_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE training_data_assessments SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_assessment(public_id)

    def overview_counts(self) -> dict[str, int]:
        with self.transaction() as connection:
            assessments_awaiting_review = connection.execute(
                "SELECT COUNT(*) FROM training_data_assessments WHERE status='assessed'"
            ).fetchone()[0]
            candidates_needing_transformation_review = connection.execute(
                "SELECT COUNT(*) FROM training_example_candidates "
                "WHERE review_status='pending_review'"
            ).fetchone()[0]
            promotions_awaiting_approval = connection.execute(
                "SELECT COUNT(*) FROM training_dataset_promotion_requests "
                "WHERE status='awaiting_approval'"
            ).fetchone()[0]
            runs_awaiting_approval = connection.execute(
                "SELECT COUNT(*) FROM incremental_training_run_requests "
                "WHERE status='awaiting_approval'"
            ).fetchone()[0]
            runs_in_progress = connection.execute(
                "SELECT COUNT(*) FROM incremental_training_runs WHERE status IN "
                "('queued','running')"
            ).fetchone()[0]
            runs_failed = connection.execute(
                "SELECT COUNT(*) FROM incremental_training_runs WHERE status='failed'"
            ).fetchone()[0]
            checkpoints_awaiting_evaluation = connection.execute(
                "SELECT COUNT(*) FROM incremental_training_checkpoints WHERE status IN "
                "('created','verified','evaluation_pending')"
            ).fetchone()[0]
            checkpoints_with_regression = connection.execute(
                """SELECT COUNT(DISTINCT checkpoint_id) FROM incremental_training_comparisons
                WHERE result_status IN ('minor_regression','major_regression')"""
            ).fetchone()[0]
            checkpoints_awaiting_acceptance = connection.execute(
                "SELECT COUNT(*) FROM incremental_training_checkpoints WHERE status='evaluated'"
            ).fetchone()[0]
            accepted_model_candidates = connection.execute(
                """SELECT COUNT(*) FROM incremental_training_checkpoint_acceptances
                WHERE decision IN ('accepted_candidate','accepted_with_conditions')
                AND model_candidate_public_id IS NOT NULL"""
            ).fetchone()[0]
        return {
            "training_assessments_awaiting_review": assessments_awaiting_review,
            "training_candidates_needing_transformation": candidates_needing_transformation_review,
            "dataset_promotions_awaiting_approval": promotions_awaiting_approval,
            "training_runs_awaiting_approval": runs_awaiting_approval,
            "training_runs_in_progress": runs_in_progress,
            "training_runs_failed": runs_failed,
            "checkpoints_awaiting_evaluation": checkpoints_awaiting_evaluation,
            "checkpoints_with_regression": checkpoints_with_regression,
            "checkpoints_awaiting_admin_acceptance": checkpoints_awaiting_acceptance,
            "accepted_model_candidates": accepted_model_candidates,
        }

    @staticmethod
    def _assessment_select_sql() -> str:
        return (
            "SELECT a.*, si.public_id AS sample_import_public_id, "
            "rse.public_id AS rag_sandbox_experiment_public_id, "
            "vc.public_id AS verification_case_public_id "
            "FROM training_data_assessments a "
            "LEFT JOIN external_dataset_sample_imports si ON si.id = a.sample_import_id "
            "LEFT JOIN rag_sandbox_experiments rse ON rse.id = a.rag_sandbox_experiment_id "
            "JOIN external_dataset_verification_cases vc ON vc.id = a.verification_case_id"
        )

    # -- assessment items (append-only) -----------------------------------------------

    def add_item(self, assessment_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            assessment_id = self._assessment_id(connection, assessment_public_id)
            sample_record_id = None
            if values.get("sample_record_public_id"):
                row = connection.execute(
                    "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
                    (values["sample_record_public_id"],),
                ).fetchone()
                sample_record_id = row["id"] if row else None
            rag_sandbox_record_id = None
            if values.get("rag_sandbox_record_public_id"):
                row = connection.execute(
                    "SELECT id FROM rag_sandbox_records WHERE public_id=?",
                    (values["rag_sandbox_record_public_id"],),
                ).fetchone()
                rag_sandbox_record_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO training_data_assessment_items(
                public_id, assessment_id, sample_record_id, rag_sandbox_record_id,
                record_category, suitability_status, dimension_results_json, reason,
                contamination_flagged)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    assessment_id,
                    sample_record_id,
                    rag_sandbox_record_id,
                    values["record_category"],
                    values.get("suitability_status", "not_assessed"),
                    dumps_json(values.get("dimension_results", {})),
                    values.get("reason", ""),
                    int(values.get("contamination_flagged", False)),
                ),
            )
        return self.get_item(public_id)

    def get_item(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._item_select_sql() + " WHERE i.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("assessment item not found")
        return _item_public(row)

    def list_items(
        self, assessment_public_id: str, *, suitability_status: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            assessment_id = self._assessment_id(connection, assessment_public_id)
            clauses = ["i.assessment_id=?"]
            params: list[Any] = [assessment_id]
            if suitability_status:
                clauses.append("i.suitability_status=?")
                params.append(suitability_status)
            rows = connection.execute(
                self._item_select_sql()
                + f" WHERE {' AND '.join(clauses)} "  # noqa: S608
                "ORDER BY i.id LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_item_public(row) for row in rows]

    @staticmethod
    def _item_select_sql() -> str:
        return (
            "SELECT i.*, a.public_id AS assessment_public_id, "
            "sr.public_id AS sample_record_public_id, "
            "rsr.public_id AS rag_sandbox_record_public_id "
            "FROM training_data_assessment_items i "
            "JOIN training_data_assessments a ON a.id = i.assessment_id "
            "LEFT JOIN external_dataset_sample_records sr ON sr.id = i.sample_record_id "
            "LEFT JOIN rag_sandbox_records rsr ON rsr.id = i.rag_sandbox_record_id"
        )

    # -- example candidates ------------------------------------------------------------

    def add_candidate(self, item_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            item_id = self._item_id(connection, item_public_id)
            source_sample_record_id = None
            if values.get("source_sample_record_public_id"):
                row = connection.execute(
                    "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
                    (values["source_sample_record_public_id"],),
                ).fetchone()
                source_sample_record_id = row["id"] if row else None
            source_rag_sandbox_record_id = None
            if values.get("source_rag_sandbox_record_public_id"):
                row = connection.execute(
                    "SELECT id FROM rag_sandbox_records WHERE public_id=?",
                    (values["source_rag_sandbox_record_public_id"],),
                ).fetchone()
                source_rag_sandbox_record_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO training_example_candidates(
                public_id, assessment_item_id, source_sample_record_id,
                source_rag_sandbox_record_id, transformation_type, prompt_text,
                assistant_text, language, task, source_checksum, candidate_checksum,
                transformation_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    item_id,
                    source_sample_record_id,
                    source_rag_sandbox_record_id,
                    values["transformation_type"],
                    values.get("prompt_text", ""),
                    values.get("assistant_text", ""),
                    values.get("language", "unknown"),
                    values.get("task", ""),
                    values["source_checksum"],
                    values["candidate_checksum"],
                    values.get("transformation_version", "v1"),
                ),
            )
        return self.get_candidate(public_id)

    def review_candidate(
        self, public_id: str, *, review_status: str, reviewed_by: str,
        conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            self._candidate_row(connection, public_id)
            connection.execute(
                """UPDATE training_example_candidates
                SET review_status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP,
                conditions_json=? WHERE public_id=?""",
                (review_status, reviewed_by, dumps_json(conditions or {}), public_id),
            )
        return self.get_candidate(public_id)

    def apply_revision_text(
        self, public_id: str, *, prompt_text: str, assistant_text: str, candidate_checksum: str
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            self._candidate_row(connection, public_id)
            connection.execute(
                """UPDATE training_example_candidates
                SET prompt_text=?, assistant_text=?, candidate_checksum=? WHERE public_id=?""",
                (prompt_text, assistant_text, candidate_checksum, public_id),
            )
        return self.get_candidate(public_id)

    def link_dataset_record(self, public_id: str, dataset_record_id: int) -> dict[str, Any]:
        with self.transaction() as connection:
            self._candidate_row(connection, public_id)
            connection.execute(
                "UPDATE training_example_candidates SET dataset_record_id=? WHERE public_id=?",
                (dataset_record_id, public_id),
            )
        return self.get_candidate(public_id)

    def get_candidate(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._candidate_select_sql() + " WHERE c.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("training example candidate not found")
        return _candidate_public(row)

    def list_candidates(
        self, *, assessment_public_id: str | None = None, review_status: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if assessment_public_id:
            clauses.append("a.public_id=?")
            params.append(assessment_public_id)
        if review_status:
            clauses.append("c.review_status=?")
            params.append(review_status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._candidate_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY c.id LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_candidate_public(row) for row in rows]

    @staticmethod
    def _candidate_select_sql() -> str:
        return (
            "SELECT c.*, i.public_id AS assessment_item_public_id, "
            "a.public_id AS assessment_a_public_id, "
            "ssr.public_id AS source_sample_record_public_id, "
            "srsr.public_id AS source_rag_sandbox_record_public_id, "
            "dr.public_id AS dataset_record_public_id "
            "FROM training_example_candidates c "
            "JOIN training_data_assessment_items i ON i.id = c.assessment_item_id "
            "JOIN training_data_assessments a ON a.id = i.assessment_id "
            "LEFT JOIN external_dataset_sample_records ssr ON ssr.id = c.source_sample_record_id "
            "LEFT JOIN rag_sandbox_records srsr ON srsr.id = c.source_rag_sandbox_record_id "
            "LEFT JOIN dataset_records dr ON dr.id = c.dataset_record_id"
        )

    # -- example revisions (append-only) -----------------------------------------------

    def add_revision(self, candidate_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            candidate = self._candidate_row(connection, candidate_public_id)
            connection.execute(
                """INSERT INTO training_example_revisions(
                public_id, candidate_id, decision, reason, revised_prompt_text,
                revised_assistant_text, revised_checksum, reviewer_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    candidate["id"],
                    values["decision"],
                    values["reason"],
                    values.get("revised_prompt_text"),
                    values.get("revised_assistant_text"),
                    values.get("revised_checksum"),
                    values["reviewer_admin_public_id"],
                ),
            )
        return self.get_revision(public_id)

    def get_revision(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._revision_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("training example revision not found")
        return _revision_public(row)

    def list_revisions(self, candidate_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            candidate = self._candidate_row(connection, candidate_public_id)
            rows = connection.execute(
                self._revision_select_sql() + " WHERE r.candidate_id=? ORDER BY r.id",
                (candidate["id"],),
            ).fetchall()
        return [_revision_public(row) for row in rows]

    @staticmethod
    def _revision_select_sql() -> str:
        return (
            "SELECT r.*, c.public_id AS candidate_public_id "
            "FROM training_example_revisions r "
            "JOIN training_example_candidates c ON c.id = r.candidate_id"
        )

    # -- replay plans (append-only) ------------------------------------------------------

    def create_replay_plan(
        self, assessment_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            assessment_id = self._assessment_id(connection, assessment_public_id)
            connection.execute(
                """INSERT INTO training_replay_plans(
                public_id, assessment_id, new_record_count, replay_record_count,
                new_data_ratio, replay_data_ratio, replay_source_version_ids_json,
                replay_record_ids_json, language_distribution_json, task_distribution_json,
                domain_distribution_json, selection_method, selection_seed, reason,
                created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    assessment_id,
                    values["new_record_count"],
                    values["replay_record_count"],
                    values["new_data_ratio"],
                    values["replay_data_ratio"],
                    dumps_json(values.get("replay_source_version_ids", [])),
                    dumps_json(values.get("replay_record_ids", [])),
                    dumps_json(values.get("language_distribution", {})),
                    dumps_json(values.get("task_distribution", {})),
                    dumps_json(values.get("domain_distribution", {})),
                    values.get("selection_method", "deterministic_representative_sample"),
                    values.get("selection_seed", 42),
                    values.get("reason", ""),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_replay_plan(public_id)

    def get_replay_plan(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._replay_plan_select_sql() + " WHERE p.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("replay plan not found")
        return _replay_plan_public(row)

    def list_replay_plans(self, assessment_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            assessment_id = self._assessment_id(connection, assessment_public_id)
            rows = connection.execute(
                self._replay_plan_select_sql() + " WHERE p.assessment_id=? ORDER BY p.id",
                (assessment_id,),
            ).fetchall()
        return [_replay_plan_public(row) for row in rows]

    @staticmethod
    def _replay_plan_select_sql() -> str:
        return (
            "SELECT p.*, a.public_id AS assessment_public_id "
            "FROM training_replay_plans p "
            "JOIN training_data_assessments a ON a.id = p.assessment_id"
        )

    # -- dataset promotion requests --------------------------------------------------------

    def create_promotion_request(
        self, assessment_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            assessment_id = self._assessment_id(connection, assessment_public_id)
            replay_plan_id = None
            if values.get("replay_plan_public_id"):
                replay_plan_id = self._replay_plan_id(connection, values["replay_plan_public_id"])
            connection.execute(
                """INSERT INTO training_dataset_promotion_requests(
                public_id, assessment_id, replay_plan_id, selected_candidate_ids_json,
                requested_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                (
                    public_id,
                    assessment_id,
                    replay_plan_id,
                    dumps_json(values.get("selected_candidate_ids", [])),
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_promotion_request(public_id)

    def approve_promotion_request(
        self, public_id: str, *, approved_by_admin_id: str, expires_at: str | None,
        target_fingerprint: str,
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM training_dataset_promotion_requests WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("dataset promotion request not found")
            if row["status"] not in ("draft", "awaiting_approval"):
                raise ValidationError("only a draft or awaiting-approval request may be approved")
            connection.execute(
                """UPDATE training_dataset_promotion_requests
                SET status='approved', approved_by_admin_id=?, approved_at=CURRENT_TIMESTAMP,
                expires_at=?, target_fingerprint=?, updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (approved_by_admin_id, expires_at, target_fingerprint, public_id),
            )
        return self.get_promotion_request(public_id)

    def update_promotion_request(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_promotion_request(public_id)
        with self.transaction() as connection:
            self._promotion_request_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE training_dataset_promotion_requests SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_promotion_request(public_id)

    def get_promotion_request(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._promotion_request_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("dataset promotion request not found")
        return _promotion_request_public(row)

    def get_latest_promotion_request(self, assessment_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            assessment_id = self._assessment_id(connection, assessment_public_id)
            row = connection.execute(
                self._promotion_request_select_sql()
                + " WHERE r.assessment_id=? ORDER BY r.id DESC LIMIT 1",
                (assessment_id,),
            ).fetchone()
        return _promotion_request_public(row) if row else None

    @staticmethod
    def _promotion_request_select_sql() -> str:
        return (
            "SELECT r.*, a.public_id AS assessment_public_id, "
            "p.public_id AS replay_plan_public_id, "
            "dv.public_id AS dataset_version_public_id "
            "FROM training_dataset_promotion_requests r "
            "JOIN training_data_assessments a ON a.id = r.assessment_id "
            "LEFT JOIN training_replay_plans p ON p.id = r.replay_plan_id "
            "LEFT JOIN dataset_versions dv ON dv.id = r.dataset_version_id"
        )

    # -- incremental training run requests -----------------------------------------------

    def create_run_request(
        self, promotion_request_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            promotion_request_id = self._promotion_request_id(
                connection, promotion_request_public_id
            )
            dataset_version_row = connection.execute(
                "SELECT id FROM dataset_versions WHERE public_id=?",
                (values["dataset_version_public_id"],),
            ).fetchone()
            if not dataset_version_row:
                raise NotFoundError("dataset version not found")
            base_checkpoint_id = None
            if values.get("base_checkpoint_public_id"):
                row = connection.execute(
                    "SELECT id FROM pretraining_checkpoints WHERE public_id=?",
                    (values["base_checkpoint_public_id"],),
                ).fetchone()
                base_checkpoint_id = row["id"] if row else None
            tokenizer_version_id = None
            if values.get("tokenizer_version_public_id"):
                row = connection.execute(
                    "SELECT id FROM tokenizer_versions WHERE public_id=?",
                    (values["tokenizer_version_public_id"],),
                ).fetchone()
                tokenizer_version_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO incremental_training_run_requests(
                public_id, promotion_request_id, dataset_version_id, base_checkpoint_id,
                tokenizer_version_id, training_strategy, configuration_json,
                configuration_checksum, resource_preview_json, resource_preview_checksum,
                execution_target, requested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    promotion_request_id,
                    dataset_version_row["id"],
                    base_checkpoint_id,
                    tokenizer_version_id,
                    values["training_strategy"],
                    dumps_json(values.get("configuration", {})),
                    values.get("configuration_checksum"),
                    dumps_json(values.get("resource_preview", {})),
                    values.get("resource_preview_checksum"),
                    values.get("execution_target", "local_cpu"),
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_run_request(public_id)

    def update_run_request(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_run_request(public_id)
        with self.transaction() as connection:
            self._run_request_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE incremental_training_run_requests SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_run_request(public_id)

    def get_run_request(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._run_request_select_sql() + " WHERE q.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("training run request not found")
        return _run_request_public(row)

    def list_run_requests(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("q.status=?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._run_request_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY q.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_run_request_public(row) for row in rows]

    @staticmethod
    def _run_request_select_sql() -> str:
        return (
            "SELECT q.*, p.public_id AS promotion_request_public_id, "
            "dv.public_id AS dataset_version_public_id, "
            "bc.public_id AS base_checkpoint_public_id, "
            "tv.public_id AS tokenizer_version_public_id "
            "FROM incremental_training_run_requests q "
            "JOIN training_dataset_promotion_requests p ON p.id = q.promotion_request_id "
            "JOIN dataset_versions dv ON dv.id = q.dataset_version_id "
            "LEFT JOIN pretraining_checkpoints bc ON bc.id = q.base_checkpoint_id "
            "LEFT JOIN tokenizer_versions tv ON tv.id = q.tokenizer_version_id"
        )

    # -- incremental training run approvals ------------------------------------------------

    def create_run_approval(
        self, run_request_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            run_request_id = self._run_request_id(connection, run_request_public_id)
            replay_plan_id = None
            if values.get("replay_plan_public_id"):
                replay_plan_id = self._replay_plan_id(connection, values["replay_plan_public_id"])
            connection.execute(
                """INSERT INTO incremental_training_run_approvals(
                public_id, run_request_id, dataset_version_id, base_checkpoint_id,
                tokenizer_version_id, training_strategy, configuration_checksum,
                resource_preview_checksum, replay_plan_id, train_split_checksum,
                validation_split_checksum, test_split_checksum, target_fingerprint,
                conditions_json, requested_by_admin_public_id)
                SELECT ?, id, dataset_version_id, base_checkpoint_id, tokenizer_version_id,
                training_strategy, configuration_checksum, resource_preview_checksum, ?,
                ?, ?, ?, ?, ?, ?
                FROM incremental_training_run_requests WHERE id=?""",
                (
                    public_id,
                    replay_plan_id,
                    values.get("train_split_checksum"),
                    values.get("validation_split_checksum"),
                    values.get("test_split_checksum"),
                    values["target_fingerprint"],
                    dumps_json(values.get("conditions", {})),
                    values["requested_by_admin_public_id"],
                    run_request_id,
                ),
            )
        return self.get_run_approval(public_id)

    def approve_run_approval(
        self, public_id: str, *, approved_by_admin_id: str, expires_at: str | None
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM incremental_training_run_approvals WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("training run approval not found")
            if row["status"] != "pending":
                raise ValidationError("only a pending approval may be approved")
            connection.execute(
                """UPDATE incremental_training_run_approvals
                SET status='approved', approved_by_admin_id=?, approved_at=CURRENT_TIMESTAMP,
                expires_at=COALESCE(?, expires_at), updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (approved_by_admin_id, expires_at, public_id),
            )
        return self.get_run_approval(public_id)

    def reject_run_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM incremental_training_run_approvals WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("training run approval not found")
            if row["status"] != "pending":
                raise ValidationError("only a pending approval may be rejected")
            connection.execute(
                """UPDATE incremental_training_run_approvals
                SET status='rejected', updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (public_id,),
            )
        return self.get_run_approval(public_id)

    def mark_run_approval_expired(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id, status FROM incremental_training_run_approvals WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("training run approval not found")
            if row["status"] != "approved":
                return self.get_run_approval(public_id)
            connection.execute(
                """UPDATE incremental_training_run_approvals
                SET status='expired', updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (public_id,),
            )
        return self.get_run_approval(public_id)

    def get_run_approval(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._run_approval_select_sql() + " WHERE a.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("training run approval not found")
        return _run_approval_public(row)

    def get_latest_run_approval(self, run_request_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            run_request_id = self._run_request_id(connection, run_request_public_id)
            row = connection.execute(
                self._run_approval_select_sql()
                + " WHERE a.run_request_id=? ORDER BY a.id DESC LIMIT 1",
                (run_request_id,),
            ).fetchone()
        return _run_approval_public(row) if row else None

    @staticmethod
    def _run_approval_select_sql() -> str:
        return (
            "SELECT a.*, q.public_id AS run_request_public_id, "
            "dv.public_id AS dataset_version_public_id, "
            "bc.public_id AS base_checkpoint_public_id, "
            "tv.public_id AS tokenizer_version_public_id, "
            "p.public_id AS replay_plan_public_id "
            "FROM incremental_training_run_approvals a "
            "JOIN incremental_training_run_requests q ON q.id = a.run_request_id "
            "JOIN dataset_versions dv ON dv.id = a.dataset_version_id "
            "LEFT JOIN pretraining_checkpoints bc ON bc.id = a.base_checkpoint_id "
            "LEFT JOIN tokenizer_versions tv ON tv.id = a.tokenizer_version_id "
            "LEFT JOIN training_replay_plans p ON p.id = a.replay_plan_id"
        )

    # -- incremental training runs ------------------------------------------------------

    def create_run(self, run_request_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            run_request_id = self._run_request_id(connection, run_request_public_id)
            approval_row = connection.execute(
                "SELECT id FROM incremental_training_run_approvals WHERE public_id=?",
                (values["run_approval_public_id"],),
            ).fetchone()
            if not approval_row:
                raise NotFoundError("training run approval not found")
            connection.execute(
                """INSERT INTO incremental_training_runs(
                public_id, run_request_id, run_approval_id, underlying_run_kind,
                underlying_run_public_id, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                (
                    public_id,
                    run_request_id,
                    approval_row["id"],
                    values["underlying_run_kind"],
                    values["underlying_run_public_id"],
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_run(public_id)

    def update_run(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_run(public_id)
        with self.transaction() as connection:
            self._run_id(connection, public_id)
            assignments = ", ".join(f'"{key}"=?' for key in fields)
            connection.execute(
                f'UPDATE incremental_training_runs SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_run(public_id)

    def get_run(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._run_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("incremental training run not found")
        return _run_public(row)

    def list_runs(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("r.status=?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                self._run_select_sql() + f" {where} "  # noqa: S608
                "ORDER BY r.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_run_public(row) for row in rows]

    @staticmethod
    def _run_select_sql() -> str:
        return (
            "SELECT r.*, q.public_id AS run_request_public_id, "
            "a.public_id AS run_approval_public_id "
            "FROM incremental_training_runs r "
            "JOIN incremental_training_run_requests q ON q.id = r.run_request_id "
            "JOIN incremental_training_run_approvals a ON a.id = r.run_approval_id"
        )

    # -- run events (append-only) ------------------------------------------------------

    def record_run_event(self, run_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            run_id = self._run_id(connection, run_public_id)
            connection.execute(
                """INSERT INTO incremental_training_run_events(
                public_id, run_id, event_type, from_status, to_status, summary,
                metadata_json, performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    run_id,
                    values["event_type"],
                    values.get("from_status"),
                    values.get("to_status"),
                    values.get("summary", ""),
                    dumps_json(values.get("metadata", {})),
                    values.get("performed_by_admin_public_id", "system"),
                ),
            )
        return self.get_run_event(public_id)

    def get_run_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._run_event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("run event not found")
        return _run_event_public(row)

    def list_run_events(
        self, run_public_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            run_id = self._run_id(connection, run_public_id)
            rows = connection.execute(
                self._run_event_select_sql()
                + " WHERE e.run_id=? ORDER BY e.id DESC LIMIT ? OFFSET ?",
                (run_id, limit, offset),
            ).fetchall()
        return [_run_event_public(row) for row in rows]

    @staticmethod
    def _run_event_select_sql() -> str:
        return (
            "SELECT e.*, r.public_id AS run_public_id "
            "FROM incremental_training_run_events e "
            "JOIN incremental_training_runs r ON r.id = e.run_id"
        )

    # -- checkpoints ---------------------------------------------------------------------

    def add_checkpoint(self, run_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            run_id = self._run_id(connection, run_public_id)
            parent_checkpoint_id = None
            if values.get("parent_checkpoint_public_id"):
                row = connection.execute(
                    "SELECT id FROM incremental_training_checkpoints WHERE public_id=?",
                    (values["parent_checkpoint_public_id"],),
                ).fetchone()
                parent_checkpoint_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO incremental_training_checkpoints(
                public_id, run_id, underlying_checkpoint_public_id, parent_checkpoint_id,
                epoch, step, tokens_seen, training_loss, validation_loss, checkpoint_checksum)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    run_id,
                    values["underlying_checkpoint_public_id"],
                    parent_checkpoint_id,
                    values.get("epoch"),
                    values.get("step"),
                    values.get("tokens_seen"),
                    values.get("training_loss"),
                    values.get("validation_loss"),
                    values.get("checkpoint_checksum"),
                ),
            )
        return self.get_checkpoint(public_id)

    def update_checkpoint_status(self, public_id: str, status: str) -> dict[str, Any]:
        with self.transaction() as connection:
            self._checkpoint_row(connection, public_id)
            connection.execute(
                "UPDATE incremental_training_checkpoints SET status=? WHERE public_id=?",
                (status, public_id),
            )
        return self.get_checkpoint(public_id)

    def get_checkpoint(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._checkpoint_select_sql() + " WHERE c.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("incremental training checkpoint not found")
        return _checkpoint_public(row)

    def list_checkpoints(self, run_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            run_id = self._run_id(connection, run_public_id)
            rows = connection.execute(
                self._checkpoint_select_sql() + " WHERE c.run_id=? ORDER BY c.id",
                (run_id,),
            ).fetchall()
        return [_checkpoint_public(row) for row in rows]

    @staticmethod
    def _checkpoint_select_sql() -> str:
        return (
            "SELECT c.*, r.public_id AS run_public_id, "
            "pc.public_id AS parent_checkpoint_public_id "
            "FROM incremental_training_checkpoints c "
            "JOIN incremental_training_runs r ON r.id = c.run_id "
            "LEFT JOIN incremental_training_checkpoints pc ON pc.id = c.parent_checkpoint_id"
        )

    # -- evaluations (append-only) ------------------------------------------------------

    def add_evaluation(self, checkpoint_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            connection.execute(
                """INSERT INTO incremental_training_evaluations(
                public_id, checkpoint_id, evaluation_type, result_status, automated, score,
                details_json, evaluation_version)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    checkpoint["id"],
                    values["evaluation_type"],
                    values["result_status"],
                    int(values.get("automated", True)),
                    values.get("score"),
                    dumps_json(values.get("details", {})),
                    values.get("evaluation_version", "v1"),
                ),
            )
        return self.get_evaluation(public_id)

    def get_evaluation(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._evaluation_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("training evaluation not found")
        return _evaluation_public(row)

    def list_evaluations(
        self, checkpoint_public_id: str, *, evaluation_type: str | None = None
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            clause = " AND e.evaluation_type=?" if evaluation_type else ""
            params: tuple[Any, ...] = (
                (checkpoint["id"], evaluation_type) if evaluation_type else (checkpoint["id"],)
            )
            rows = connection.execute(
                self._evaluation_select_sql()
                + f" WHERE e.checkpoint_id=?{clause} ORDER BY e.id",  # noqa: S608
                params,
            ).fetchall()
        return [_evaluation_public(row) for row in rows]

    @staticmethod
    def _evaluation_select_sql() -> str:
        return (
            "SELECT e.*, c.public_id AS checkpoint_public_id "
            "FROM incremental_training_evaluations e "
            "JOIN incremental_training_checkpoints c ON c.id = e.checkpoint_id"
        )

    # -- comparisons (append-only) ------------------------------------------------------

    def add_comparison(self, checkpoint_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            parent_checkpoint_id = None
            if values.get("parent_checkpoint_public_id"):
                row = connection.execute(
                    "SELECT id FROM incremental_training_checkpoints WHERE public_id=?",
                    (values["parent_checkpoint_public_id"],),
                ).fetchone()
                parent_checkpoint_id = row["id"] if row else None
            connection.execute(
                """INSERT INTO incremental_training_comparisons(
                public_id, checkpoint_id, parent_checkpoint_id, comparison_type, dimension,
                result_status, metrics_json, source_evaluation_ids_json)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    checkpoint["id"],
                    parent_checkpoint_id,
                    values["comparison_type"],
                    values.get("dimension", "overall"),
                    values["result_status"],
                    dumps_json(values.get("metrics", {})),
                    dumps_json(values.get("source_evaluation_ids", [])),
                ),
            )
        return self.get_comparison(public_id)

    def get_comparison(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._comparison_select_sql() + " WHERE c.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("checkpoint comparison not found")
        return _comparison_public(row)

    def list_comparisons(
        self, checkpoint_public_id: str, *, comparison_type: str | None = None
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            clause = " AND c.comparison_type=?" if comparison_type else ""
            params: tuple[Any, ...] = (
                (checkpoint["id"], comparison_type) if comparison_type else (checkpoint["id"],)
            )
            rows = connection.execute(
                self._comparison_select_sql()
                + f" WHERE c.checkpoint_id=?{clause} ORDER BY c.id",  # noqa: S608
                params,
            ).fetchall()
        return [_comparison_public(row) for row in rows]

    @staticmethod
    def _comparison_select_sql() -> str:
        return (
            "SELECT c.*, ck.public_id AS checkpoint_public_id, "
            "pc.public_id AS parent_checkpoint_public_id "
            "FROM incremental_training_comparisons c "
            "JOIN incremental_training_checkpoints ck ON ck.id = c.checkpoint_id "
            "LEFT JOIN incremental_training_checkpoints pc ON pc.id = c.parent_checkpoint_id"
        )

    # -- human reviews (append-only) -----------------------------------------------------

    def add_human_review(
        self, checkpoint_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            connection.execute(
                """INSERT INTO incremental_training_human_reviews(
                public_id, checkpoint_id, prompt_text, tamil_fluency, english_fluency,
                tanglish_readability, instruction_following, helpfulness, correct_refusal,
                hallucination_risk, repetition, formatting, regression, decision, notes,
                reviewer_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    checkpoint["id"],
                    values.get("prompt_text", ""),
                    values.get("tamil_fluency"),
                    values.get("english_fluency"),
                    values.get("tanglish_readability"),
                    values.get("instruction_following"),
                    values.get("helpfulness"),
                    values.get("correct_refusal"),
                    values.get("hallucination_risk"),
                    values.get("repetition"),
                    values.get("formatting"),
                    values.get("regression"),
                    values["decision"],
                    values.get("notes", ""),
                    values["reviewer_admin_public_id"],
                ),
            )
        return self.get_human_review(public_id)

    def get_human_review(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._human_review_select_sql() + " WHERE h.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("human review not found")
        return _human_review_public(row)

    def list_human_reviews(self, checkpoint_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            rows = connection.execute(
                self._human_review_select_sql() + " WHERE h.checkpoint_id=? ORDER BY h.id",
                (checkpoint["id"],),
            ).fetchall()
        return [_human_review_public(row) for row in rows]

    @staticmethod
    def _human_review_select_sql() -> str:
        return (
            "SELECT h.*, c.public_id AS checkpoint_public_id "
            "FROM incremental_training_human_reviews h "
            "JOIN incremental_training_checkpoints c ON c.id = h.checkpoint_id"
        )

    # -- reports (append-only, versioned) -----------------------------------------------

    def add_report(self, run_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            run_id = self._run_id(connection, run_public_id)
            next_version = connection.execute(
                "SELECT COALESCE(MAX(report_version), 0) + 1 FROM incremental_training_reports "
                "WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO incremental_training_reports(
                public_id, run_id, report_version, report_json, report_checksum_sha256,
                checkpoint_recommendation, production_release_readiness,
                recommended_next_action, finalized_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    run_id,
                    next_version,
                    dumps_json(values["report"]),
                    values["report_checksum_sha256"],
                    values["checkpoint_recommendation"],
                    values.get("production_release_readiness", "not_assessed"),
                    values.get("recommended_next_action", ""),
                    values["finalized_by_admin_public_id"],
                ),
            )
        return self.get_report(public_id)

    def get_report(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._report_select_sql() + " WHERE r.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("training report not found")
        return _report_public(row)

    def get_latest_report(self, run_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            run_id = self._run_id(connection, run_public_id)
            row = connection.execute(
                self._report_select_sql()
                + " WHERE r.run_id=? ORDER BY r.report_version DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return _report_public(row) if row else None

    def list_reports(self, run_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            run_id = self._run_id(connection, run_public_id)
            rows = connection.execute(
                self._report_select_sql() + " WHERE r.run_id=? ORDER BY r.report_version",
                (run_id,),
            ).fetchall()
        return [_report_public(row) for row in rows]

    @staticmethod
    def _report_select_sql() -> str:
        return (
            "SELECT r.*, run.public_id AS run_public_id "
            "FROM incremental_training_reports r "
            "JOIN incremental_training_runs run ON run.id = r.run_id"
        )

    # -- checkpoint acceptances (append-only) ---------------------------------------------

    def add_acceptance(self, checkpoint_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            report_id = self._report_id(connection, values["report_public_id"])
            connection.execute(
                """INSERT INTO incremental_training_checkpoint_acceptances(
                public_id, checkpoint_id, report_id, decision, reason, conditions_json,
                reviewer_admin_public_id, report_checksum_sha256, checkpoint_checksum,
                target_fingerprint, model_candidate_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    checkpoint["id"],
                    report_id,
                    values["decision"],
                    values["reason"],
                    dumps_json(values.get("conditions", {})),
                    values["reviewer_admin_public_id"],
                    values["report_checksum_sha256"],
                    values.get("checkpoint_checksum"),
                    values["target_fingerprint"],
                    values.get("model_candidate_public_id"),
                ),
            )
        return self.get_acceptance(public_id)

    def get_acceptance(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._acceptance_select_sql() + " WHERE a.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("checkpoint acceptance not found")
        return _acceptance_public(row)

    def get_latest_acceptance(self, checkpoint_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            row = connection.execute(
                self._acceptance_select_sql()
                + " WHERE a.checkpoint_id=? ORDER BY a.id DESC LIMIT 1",
                (checkpoint["id"],),
            ).fetchone()
        return _acceptance_public(row) if row else None

    def list_acceptances(self, checkpoint_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            checkpoint = self._checkpoint_row(connection, checkpoint_public_id)
            rows = connection.execute(
                self._acceptance_select_sql() + " WHERE a.checkpoint_id=? ORDER BY a.id",
                (checkpoint["id"],),
            ).fetchall()
        return [_acceptance_public(row) for row in rows]

    @staticmethod
    def _acceptance_select_sql() -> str:
        return (
            "SELECT a.*, c.public_id AS checkpoint_public_id, "
            "r.public_id AS report_public_id "
            "FROM incremental_training_checkpoint_acceptances a "
            "JOIN incremental_training_checkpoints c ON c.id = a.checkpoint_id "
            "JOIN incremental_training_reports r ON r.id = a.report_id"
        )
