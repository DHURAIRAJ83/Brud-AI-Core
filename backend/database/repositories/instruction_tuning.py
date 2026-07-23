"""Repository for Phase 12 instruction-tuning experiments, runs, and evaluation evidence."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "base_core_model_version_id",
    "source_base_checkpoint_id",
    "dataset_version_id",
    "tokenizer_version_id",
    "instruction_template_id",
    "instruction_tuning_experiment_id",
    "instruction_tuning_run_id",
    "instruction_tuning_evaluation_id",
    "pretraining_job_id",
    "selected_run_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("instruction tuning row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class InstructionTuningRepository(BaseRepository):
    # --- experiments -----------------------------------------------------

    def experiment(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT e.*, m.public_id AS base_core_model_version_public_id,
            c.public_id AS source_base_checkpoint_public_id,
            d.public_id AS dataset_version_public_id,
            t.public_id AS tokenizer_version_public_id,
            tpl.public_id AS instruction_template_public_id
            FROM instruction_tuning_experiments e
            JOIN core_model_versions m ON m.id=e.base_core_model_version_id
            JOIN pretraining_checkpoints c ON c.id=e.source_base_checkpoint_id
            JOIN dataset_versions d ON d.id=e.dataset_version_id
            JOIN tokenizer_versions t ON t.id=e.tokenizer_version_id
            LEFT JOIN instruction_format_templates tpl ON tpl.id=e.instruction_template_id
            WHERE e.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("instruction tuning experiment not found")
        return row

    def create_experiment(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_tuning_experiments(public_id,name,objective,
            base_core_model_version_id,source_base_checkpoint_id,dataset_version_id,
            tokenizer_version_id,initialization_seed,sampling_seed,training_configuration_json,
            evaluation_configuration_json,resource_limits_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("objective", ""),
                values["base_core_model_version_id"],
                values["source_base_checkpoint_id"],
                values["dataset_version_id"],
                values["tokenizer_version_id"],
                values.get("initialization_seed", 42),
                values.get("sampling_seed", 42),
                values.get("training_configuration_json", "{}"),
                values.get("evaluation_configuration_json", "{}"),
                values.get("resource_limits_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def list_experiments(
        self, connection: sqlite3.Connection, page: int, page_size: int
    ) -> tuple[list[sqlite3.Row], int]:
        rows = connection.execute(
            """SELECT * FROM instruction_tuning_experiments
            ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?""",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        total = connection.execute(
            "SELECT COUNT(*) FROM instruction_tuning_experiments"
        ).fetchone()[0]
        return rows, total

    def update_experiment(
        self, connection: sqlite3.Connection, experiment_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE instruction_tuning_experiments SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), experiment_id),
        )

    # --- runs -----------------------------------------------------

    def run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*, e.public_id AS experiment_public_id,
            j.public_id AS pretraining_job_public_id, j.status AS job_status
            FROM instruction_tuning_runs r
            JOIN instruction_tuning_experiments e ON e.id=r.instruction_tuning_experiment_id
            LEFT JOIN pretraining_jobs j ON j.id=r.pretraining_job_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("instruction tuning run not found")
        return row

    def create_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_tuning_runs(public_id,instruction_tuning_experiment_id,
            pretraining_job_id,instruction_template_id,run_label,run_index,config_diff_json,
            truncation_policy,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["instruction_tuning_experiment_id"],
                values.get("pretraining_job_id"),
                values.get("instruction_template_id"),
                values["run_label"],
                values["run_index"],
                values.get("config_diff_json", "{}"),
                values.get("truncation_policy", "truncate_prompt_first"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def runs_for_experiment(
        self, connection: sqlite3.Connection, experiment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT r.*, j.public_id AS pretraining_job_public_id, j.status AS job_status
            FROM instruction_tuning_runs r
            LEFT JOIN pretraining_jobs j ON j.id=r.pretraining_job_id
            WHERE r.instruction_tuning_experiment_id=? ORDER BY r.run_index""",
            (experiment_id,),
        ).fetchall()

    def update_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE instruction_tuning_runs SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), run_id),
        )

    # --- templates -----------------------------------------------------

    def create_template(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_format_templates(public_id,name,version,
            tokenizer_version_id,template_json,required_special_tokens_json,
            special_token_validation_json,is_valid,template_checksum_sha256,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values["version"],
                values["tokenizer_version_id"],
                values["template_json"],
                values.get("required_special_tokens_json", "[]"),
                values.get("special_token_validation_json", "{}"),
                values.get("is_valid", 0),
                values["template_checksum_sha256"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def template(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT tpl.*, t.public_id AS tokenizer_version_public_id
            FROM instruction_format_templates tpl
            JOIN tokenizer_versions t ON t.id=tpl.tokenizer_version_id
            WHERE tpl.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("instruction template not found")
        return row

    def templates(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM instruction_format_templates ORDER BY created_at DESC,id DESC"
        ).fetchall()

    # --- dataset profiles -----------------------------------------------------

    def record_profile(
        self, connection: sqlite3.Connection, experiment_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_dataset_profiles(public_id,
            instruction_tuning_experiment_id,dataset_version_id,total_records,eligible_records,
            invalid_records,excluded_records,train_count,validation_count,test_count,
            language_distribution_json,record_type_distribution_json,source_distribution_json,
            licence_distribution_json,system_prompt_count,input_field_count,
            synthesized_flat_chat_count,average_prompt_tokens,average_response_tokens,
            maximum_prompt_tokens,maximum_response_tokens,empty_response_count,
            duplicate_prompt_count,duplicate_response_count,
            exact_prompt_response_duplicate_count,response_language_mismatch_count,
            special_token_collision_count,truncation_risk_count,
            maskable_assistant_token_count,exclusion_reasons_json,
            input_stream_checksum_sha256,label_stream_checksum_sha256,
            data_sufficiency_status,profile_checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                experiment_id,
                values["dataset_version_id"],
                values["total_records"],
                values["eligible_records"],
                values["invalid_records"],
                values["excluded_records"],
                values["train_count"],
                values["validation_count"],
                values["test_count"],
                values["language_distribution_json"],
                values["record_type_distribution_json"],
                values["source_distribution_json"],
                values["licence_distribution_json"],
                values["system_prompt_count"],
                values["input_field_count"],
                values["synthesized_flat_chat_count"],
                values["average_prompt_tokens"],
                values["average_response_tokens"],
                values["maximum_prompt_tokens"],
                values["maximum_response_tokens"],
                values["empty_response_count"],
                values["duplicate_prompt_count"],
                values["duplicate_response_count"],
                values["exact_prompt_response_duplicate_count"],
                values["response_language_mismatch_count"],
                values["special_token_collision_count"],
                values["truncation_risk_count"],
                values["maskable_assistant_token_count"],
                values["exclusion_reasons_json"],
                values["input_stream_checksum_sha256"],
                values["label_stream_checksum_sha256"],
                values["data_sufficiency_status"],
                values["profile_checksum_sha256"],
            ),
        )
        return public_id

    def latest_profile(
        self, connection: sqlite3.Connection, experiment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM instruction_dataset_profiles
            WHERE instruction_tuning_experiment_id=? ORDER BY created_at DESC, id DESC LIMIT 1""",
            (experiment_id,),
        ).fetchone()

    # --- metrics -----------------------------------------------------

    def record_metric(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_tuning_metrics(public_id,instruction_tuning_run_id,
            step,examples_processed,prompt_tokens,target_tokens,ignored_tokens,training_loss,
            validation_response_loss,learning_rate,gradient_norm,tokens_per_second,
            step_duration_ms,process_memory_bytes,system_available_memory_bytes,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                run_id,
                values["step"],
                values.get("examples_processed", 0),
                values.get("prompt_tokens", 0),
                values.get("target_tokens", 0),
                values.get("ignored_tokens", 0),
                values.get("training_loss"),
                values.get("validation_response_loss"),
                values["learning_rate"],
                values.get("gradient_norm"),
                values.get("tokens_per_second"),
                values.get("step_duration_ms", 0),
                values.get("process_memory_bytes"),
                values.get("system_available_memory_bytes"),
                values.get("metadata_json", "{}"),
            ),
        )
        return public_id

    def metrics(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM instruction_tuning_metrics WHERE instruction_tuning_run_id=?
            ORDER BY step""",
            (run_id,),
        ).fetchall()

    # --- evaluations -----------------------------------------------------

    def record_evaluation(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_tuning_evaluations(public_id,instruction_tuning_run_id,
            evaluation_type,split,checkpoint_public_id,summary_json,completed_at)
            VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            (
                public_id,
                run_id,
                values["evaluation_type"],
                values.get("split"),
                values.get("checkpoint_public_id"),
                values.get("summary_json", "{}"),
            ),
        )
        return public_id

    def evaluation(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM instruction_tuning_evaluations WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("instruction tuning evaluation not found")
        return row

    def evaluations_for_run(
        self, connection: sqlite3.Connection, run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM instruction_tuning_evaluations
            WHERE instruction_tuning_run_id=? ORDER BY created_at""",
            (run_id,),
        ).fetchall()

    def record_evaluation_result(
        self, connection: sqlite3.Connection, evaluation_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_tuning_evaluation_results(public_id,
            instruction_tuning_evaluation_id,language,metric_name,metric_value,sample_count,
            details_json) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                evaluation_id,
                values["language"],
                values["metric_name"],
                values.get("metric_value"),
                values.get("sample_count", 0),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def evaluation_results(
        self, connection: sqlite3.Connection, evaluation_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM instruction_tuning_evaluation_results
            WHERE instruction_tuning_evaluation_id=? ORDER BY language,metric_name""",
            (evaluation_id,),
        ).fetchall()

    # --- learning checks -----------------------------------------------------

    def record_learning_check(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_learning_checks(public_id,instruction_tuning_run_id,
            check_code,status,message,details_json) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                run_id,
                values["check_code"],
                values["status"],
                values["message"],
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def learning_checks(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM instruction_learning_checks WHERE instruction_tuning_run_id=?
            ORDER BY id""",
            (run_id,),
        ).fetchall()

    # --- candidates -----------------------------------------------------

    def record_candidate(
        self, connection: sqlite3.Connection, experiment_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_tuning_candidates(public_id,
            instruction_tuning_experiment_id,selected_run_id,selected_checkpoint_public_id,
            status,role_leakage_result,memorization_warning_count,
            base_checkpoint_checksum_before,base_checkpoint_checksum_after,rationale_json,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                experiment_id,
                values.get("selected_run_id"),
                values.get("selected_checkpoint_public_id"),
                values["status"],
                values.get("role_leakage_result", "not_assessed"),
                values.get("memorization_warning_count", 0),
                values.get("base_checkpoint_checksum_before"),
                values.get("base_checkpoint_checksum_after"),
                values.get("rationale_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def latest_candidate(
        self, connection: sqlite3.Connection, experiment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM instruction_tuning_candidates
            WHERE instruction_tuning_experiment_id=? ORDER BY created_at DESC, id DESC LIMIT 1""",
            (experiment_id,),
        ).fetchone()

    # --- reproducibility manifest -----------------------------------------------------

    def record_manifest(
        self, connection: sqlite3.Connection, experiment_id: int, manifest_json: str, checksum: str
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO instruction_reproducibility_manifests(public_id,
            instruction_tuning_experiment_id,manifest_json,manifest_checksum_sha256)
            VALUES (?,?,?,?)""",
            (public_id, experiment_id, manifest_json, checksum),
        )
        return public_id

    def latest_manifest(
        self, connection: sqlite3.Connection, experiment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM instruction_reproducibility_manifests
            WHERE instruction_tuning_experiment_id=? ORDER BY created_at DESC, id DESC LIMIT 1""",
            (experiment_id,),
        ).fetchone()
