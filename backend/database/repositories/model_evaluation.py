"""Repository for Phase 13 multilingual evaluation, safety, and readiness evidence."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "model_evaluation_suite_id",
    "model_evaluation_fixture_set_id",
    "model_evaluation_fixture_id",
    "model_evaluation_run_id",
    "model_evaluation_output_id",
    "model_evaluation_evaluation_id",
    "candidate_core_model_version_id",
    "checkpoint_id",
    "tokenizer_version_id",
    "left_run_id",
    "right_run_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("model evaluation row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class ModelEvaluationRepository(BaseRepository):
    # --- suites -----------------------------------------------------

    def create_suite(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_suites(public_id,name,version,description,
            supported_languages_json,generation_configuration_json,automated_thresholds_json,
            human_review_rubric_json,readiness_gate_configuration_json,suite_checksum_sha256,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values["version"],
                values.get("description", ""),
                values["supported_languages_json"],
                values["generation_configuration_json"],
                values["automated_thresholds_json"],
                values["human_review_rubric_json"],
                values["readiness_gate_configuration_json"],
                values.get("suite_checksum_sha256"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def suite(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM model_evaluation_suites WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("evaluation suite not found")
        return row

    def list_suites(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM model_evaluation_suites ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def update_suite(
        self, connection: sqlite3.Connection, suite_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE model_evaluation_suites SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), suite_id),
        )

    # --- fixture sets / fixtures -----------------------------------------------------

    def create_fixture_set(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_fixture_sets(public_id,model_evaluation_suite_id,
            name,description,fixture_count,checksum_sha256,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_evaluation_suite_id"],
                values["name"],
                values.get("description", ""),
                values["fixture_count"],
                values["checksum_sha256"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def fixture_set(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT fs.*, s.public_id AS model_evaluation_suite_public_id
            FROM model_evaluation_fixture_sets fs
            JOIN model_evaluation_suites s ON s.id=fs.model_evaluation_suite_id
            WHERE fs.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("fixture set not found")
        return row

    def fixture_sets_for_suite(
        self, connection: sqlite3.Connection, suite_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM model_evaluation_fixture_sets
            WHERE model_evaluation_suite_id=? ORDER BY created_at DESC,id DESC""",
            (suite_id,),
        ).fetchall()

    def create_fixture(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_fixtures(public_id,model_evaluation_fixture_set_id,
            category,language,prompt,system_prompt,expected_response_language,expected_format,
            expected_keywords_json,forbidden_keywords_json,reference_answer,reference_facts_json,
            refusal_expected,max_new_tokens,timeout_seconds,severity,metadata_json,
            checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_evaluation_fixture_set_id"],
                values["category"],
                values["language"],
                values["prompt"],
                values.get("system_prompt"),
                values.get("expected_response_language"),
                values.get("expected_format"),
                values["expected_keywords_json"],
                values["forbidden_keywords_json"],
                values.get("reference_answer"),
                values["reference_facts_json"],
                1 if values.get("refusal_expected") else 0,
                values.get("max_new_tokens", 32),
                values.get("timeout_seconds", 5.0),
                values.get("severity", "medium"),
                values["metadata_json"],
                values["checksum_sha256"],
            ),
        )
        return public_id

    def fixtures_for_set(
        self, connection: sqlite3.Connection, fixture_set_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM model_evaluation_fixtures
            WHERE model_evaluation_fixture_set_id=? ORDER BY id""",
            (fixture_set_id,),
        ).fetchall()

    def fixture(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM model_evaluation_fixtures WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("fixture not found")
        return row

    # --- runs -----------------------------------------------------

    def create_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_runs(public_id,model_evaluation_suite_id,
            candidate_core_model_version_id,checkpoint_id,tokenizer_version_id,
            generation_configuration_json,generation_config_checksum_sha256,status,
            fixture_count,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_evaluation_suite_id"],
                values["candidate_core_model_version_id"],
                values["checkpoint_id"],
                values["tokenizer_version_id"],
                values["generation_configuration_json"],
                values.get("generation_config_checksum_sha256"),
                values.get("status", "draft"),
                values.get("fixture_count", 0),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*, s.public_id AS model_evaluation_suite_public_id,
            s.readiness_gate_configuration_json AS suite_readiness_gate_configuration_json,
            s.automated_thresholds_json AS suite_automated_thresholds_json,
            m.public_id AS candidate_core_model_version_public_id,
            m.architecture_summary_json AS candidate_architecture_summary_json,
            c.public_id AS checkpoint_public_id, c.safe_name AS checkpoint_safe_name,
            c.model_checksum_sha256 AS checkpoint_model_checksum_sha256,
            c.status AS checkpoint_status,
            t.public_id AS tokenizer_version_public_id
            FROM model_evaluation_runs r
            JOIN model_evaluation_suites s ON s.id=r.model_evaluation_suite_id
            JOIN core_model_versions m ON m.id=r.candidate_core_model_version_id
            JOIN pretraining_checkpoints c ON c.id=r.checkpoint_id
            JOIN tokenizer_versions t ON t.id=r.tokenizer_version_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("evaluation run not found")
        return row

    def list_runs(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM model_evaluation_runs ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def update_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE model_evaluation_runs SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), run_id),
        )

    # --- outputs -----------------------------------------------------

    def record_output(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_outputs(public_id,model_evaluation_run_id,
            model_evaluation_fixture_id,generated_text,prompt_token_count,generated_token_count,
            stop_reason,runtime_ms,output_checksum_sha256,error_status)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                run_id,
                values["model_evaluation_fixture_id"],
                values.get("generated_text", ""),
                values.get("prompt_token_count", 0),
                values.get("generated_token_count", 0),
                values.get("stop_reason", "unknown"),
                values.get("runtime_ms", 0),
                values["output_checksum_sha256"],
                values.get("error_status"),
            ),
        )
        return public_id

    def outputs_for_run(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT o.*, f.category AS fixture_category, f.language AS fixture_language,
            f.public_id AS fixture_public_id
            FROM model_evaluation_outputs o
            JOIN model_evaluation_fixtures f ON f.id=o.model_evaluation_fixture_id
            WHERE o.model_evaluation_run_id=? ORDER BY o.id""",
            (run_id,),
        ).fetchall()

    def output(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT o.*, f.category AS fixture_category, f.language AS fixture_language,
            f.prompt AS fixture_prompt
            FROM model_evaluation_outputs o
            JOIN model_evaluation_fixtures f ON f.id=o.model_evaluation_fixture_id
            WHERE o.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("evaluation output not found")
        return row

    # --- metrics -----------------------------------------------------

    def record_metric(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_metrics(public_id,model_evaluation_run_id,language,
            category,severity,metric_name,metric_value,sample_count,details_json)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                run_id,
                values.get("language"),
                values.get("category"),
                values.get("severity"),
                values["metric_name"],
                values.get("metric_value"),
                values.get("sample_count", 0),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def metrics_for_run(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM model_evaluation_metrics WHERE model_evaluation_run_id=?
            ORDER BY language,category,metric_name""",
            (run_id,),
        ).fetchall()

    # --- issues -----------------------------------------------------

    def record_issue(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_issues(public_id,model_evaluation_run_id,
            model_evaluation_output_id,issue_code,severity,message,details_json)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                run_id,
                values.get("model_evaluation_output_id"),
                values["issue_code"],
                values["severity"],
                values["message"],
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def issues_for_run(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM model_evaluation_issues WHERE model_evaluation_run_id=?
            ORDER BY id""",
            (run_id,),
        ).fetchall()

    # --- human reviews -----------------------------------------------------

    def record_human_review(
        self, connection: sqlite3.Connection, output_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_human_reviews(public_id,model_evaluation_output_id,
            reviewer_admin_public_id,rubric_version,language,category,relevance_score,
            correctness_score,instruction_following_score,language_quality_score,safety_score,
            overall_score,verdict,comment)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                output_id,
                values["reviewer_admin_public_id"],
                values.get("rubric_version", "1"),
                values["language"],
                values["category"],
                values["relevance_score"],
                values.get("correctness_score"),
                values["instruction_following_score"],
                values["language_quality_score"],
                values["safety_score"],
                values["overall_score"],
                values["verdict"],
                values.get("comment", ""),
            ),
        )
        return public_id

    def reviews_for_output(
        self, connection: sqlite3.Connection, output_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM model_evaluation_human_reviews WHERE model_evaluation_output_id=?
            ORDER BY created_at""",
            (output_id,),
        ).fetchall()

    def reviews_for_run(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT hr.*, o.public_id AS output_public_id
            FROM model_evaluation_human_reviews hr
            JOIN model_evaluation_outputs o ON o.id=hr.model_evaluation_output_id
            WHERE o.model_evaluation_run_id=? ORDER BY hr.created_at""",
            (run_id,),
        ).fetchall()

    # --- comparisons -----------------------------------------------------

    def record_comparison(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_comparisons(public_id,left_run_id,right_run_id,
            compatibility,ranked,fields_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["left_run_id"],
                values["right_run_id"],
                values["compatibility"],
                1 if values.get("ranked") else 0,
                values.get("fields_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def comparison(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM model_evaluation_comparisons WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("comparison not found")
        return row

    # --- chat readiness -----------------------------------------------------

    def record_readiness(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_chat_readiness_assessments(public_id,model_evaluation_run_id,
            status,dimension_scores_json,blocking_issue_count,warning_issue_count,
            rationale_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                run_id,
                values["status"],
                values.get("dimension_scores_json", "{}"),
                values.get("blocking_issue_count", 0),
                values.get("warning_issue_count", 0),
                values.get("rationale_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def latest_readiness(self, connection: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM model_chat_readiness_assessments
            WHERE model_evaluation_run_id=? ORDER BY created_at DESC,id DESC LIMIT 1""",
            (run_id,),
        ).fetchone()

    # --- manifests -----------------------------------------------------

    def record_manifest(
        self, connection: sqlite3.Connection, run_id: int, manifest_json: str, checksum: str
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_evaluation_manifests(public_id,model_evaluation_run_id,
            manifest_json,manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (public_id, run_id, manifest_json, checksum),
        )
        return public_id

    def latest_manifest(self, connection: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM model_evaluation_manifests
            WHERE model_evaluation_run_id=? ORDER BY created_at DESC,id DESC LIMIT 1""",
            (run_id,),
        ).fetchone()
