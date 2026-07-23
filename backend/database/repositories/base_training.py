"""Repository for Phase 11 base-training experiments, runs, and evaluation evidence."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "dataset_version_id",
    "tokenizer_version_id",
    "core_model_version_id",
    "base_training_experiment_id",
    "experiment_run_id",
    "pretraining_job_id",
    "selected_run_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("base training row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class BaseTrainingRepository(BaseRepository):
    # --- experiments -----------------------------------------------------

    def experiment(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT e.*, d.public_id AS dataset_version_public_id,
            t.public_id AS tokenizer_version_public_id,
            m.public_id AS core_model_version_public_id
            FROM base_training_experiments e
            JOIN dataset_versions d ON d.id=e.dataset_version_id
            LEFT JOIN tokenizer_versions t ON t.id=e.tokenizer_version_id
            LEFT JOIN core_model_versions m ON m.id=e.core_model_version_id
            WHERE e.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("base training experiment not found")
        return row

    def create_experiment(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_training_experiments(public_id,name,objective,
            dataset_version_id,initialization_seed,sampling_seed,training_configuration_json,
            evaluation_configuration_json,resource_limits_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("objective", ""),
                values["dataset_version_id"],
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
            """SELECT * FROM base_training_experiments
            ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?""",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        total = connection.execute("SELECT COUNT(*) FROM base_training_experiments").fetchone()[0]
        return rows, total

    def update_experiment(
        self, connection: sqlite3.Connection, experiment_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE base_training_experiments SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), experiment_id),
        )

    # --- runs -----------------------------------------------------

    def run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*, e.public_id AS experiment_public_id,
            j.public_id AS pretraining_job_public_id, j.status AS job_status
            FROM base_training_experiment_runs r
            JOIN base_training_experiments e ON e.id=r.base_training_experiment_id
            LEFT JOIN pretraining_jobs j ON j.id=r.pretraining_job_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("base training run not found")
        return row

    def create_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_training_experiment_runs(public_id,base_training_experiment_id,
            pretraining_job_id,run_label,run_index,config_diff_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["base_training_experiment_id"],
                values.get("pretraining_job_id"),
                values["run_label"],
                values["run_index"],
                values.get("config_diff_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def runs_for_experiment(
        self, connection: sqlite3.Connection, experiment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT r.*, j.public_id AS pretraining_job_public_id, j.status AS job_status
            FROM base_training_experiment_runs r
            LEFT JOIN pretraining_jobs j ON j.id=r.pretraining_job_id
            WHERE r.base_training_experiment_id=? ORDER BY r.run_index""",
            (experiment_id,),
        ).fetchall()

    def update_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE base_training_experiment_runs SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), run_id),
        )

    # --- dataset profiles -----------------------------------------------------

    def record_profile(
        self, connection: sqlite3.Connection, experiment_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_training_dataset_profiles(public_id,base_training_experiment_id,
            dataset_version_id,total_records,approved_records,train_count,validation_count,
            test_count,total_characters,total_tokens,unique_token_count,
            language_distribution_json,record_type_distribution_json,source_distribution_json,
            licence_distribution_json,average_record_length,median_record_length,
            maximum_record_length,duplicate_rate,near_duplicate_rate,zero_token_rate,
            oversized_record_rate,validation_representativeness_json,test_representativeness_json,
            tamil_script_coverage,english_latin_coverage,tanglish_coverage,mixed_script_coverage,
            warnings_json,data_sufficiency_status,profile_checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                experiment_id,
                values["dataset_version_id"],
                values["total_records"],
                values["approved_records"],
                values["train_count"],
                values["validation_count"],
                values["test_count"],
                values["total_characters"],
                values["total_tokens"],
                values["unique_token_count"],
                values["language_distribution_json"],
                values["record_type_distribution_json"],
                values["source_distribution_json"],
                values["licence_distribution_json"],
                values["average_record_length"],
                values["median_record_length"],
                values["maximum_record_length"],
                values["duplicate_rate"],
                values["near_duplicate_rate"],
                values["zero_token_rate"],
                values["oversized_record_rate"],
                values["validation_representativeness_json"],
                values["test_representativeness_json"],
                values["tamil_script_coverage"],
                values["english_latin_coverage"],
                values["tanglish_coverage"],
                values["mixed_script_coverage"],
                values["warnings_json"],
                values["data_sufficiency_status"],
                values["profile_checksum_sha256"],
            ),
        )
        return public_id

    def latest_profile(
        self, connection: sqlite3.Connection, experiment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM base_training_dataset_profiles WHERE base_training_experiment_id=?
            ORDER BY created_at DESC, id DESC LIMIT 1""",
            (experiment_id,),
        ).fetchone()

    # --- language metrics -----------------------------------------------------

    def record_language_metric(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_training_language_metrics(public_id,experiment_run_id,
            checkpoint_public_id,split,language,evaluated_records,evaluated_tokens,loss,
            perplexity,unknown_token_rate,average_tokens_per_record,maximum_tokens_per_record,
            long_sequence_rate,details_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                run_id,
                values.get("checkpoint_public_id"),
                values["split"],
                values["language"],
                values["evaluated_records"],
                values["evaluated_tokens"],
                values.get("loss"),
                values.get("perplexity"),
                values["unknown_token_rate"],
                values["average_tokens_per_record"],
                values["maximum_tokens_per_record"],
                values["long_sequence_rate"],
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def language_metrics(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM base_training_language_metrics WHERE experiment_run_id=?
            ORDER BY split,language""",
            (run_id,),
        ).fetchall()

    # --- learning checks -----------------------------------------------------

    def record_learning_check(
        self, connection: sqlite3.Connection, run_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_training_learning_checks(public_id,experiment_run_id,
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
            """SELECT * FROM base_training_learning_checks WHERE experiment_run_id=?
            ORDER BY id""",
            (run_id,),
        ).fetchall()

    # --- candidate selection -----------------------------------------------------

    def record_candidate_selection(
        self, connection: sqlite3.Connection, experiment_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_training_candidate_selections(public_id,
            base_training_experiment_id,selected_run_id,selected_checkpoint_public_id,status,
            generalization_result,memorization_warning_count,rationale_json,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                experiment_id,
                values.get("selected_run_id"),
                values.get("selected_checkpoint_public_id"),
                values["status"],
                values["generalization_result"],
                values["memorization_warning_count"],
                values.get("rationale_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def latest_candidate_selection(
        self, connection: sqlite3.Connection, experiment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM base_training_candidate_selections WHERE base_training_experiment_id=?
            ORDER BY created_at DESC, id DESC LIMIT 1""",
            (experiment_id,),
        ).fetchone()

    # --- reproducibility manifest -----------------------------------------------------

    def record_manifest(
        self, connection: sqlite3.Connection, experiment_id: int, manifest_json: str, checksum: str
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_training_reproducibility_manifests(public_id,
            base_training_experiment_id,manifest_json,manifest_checksum_sha256)
            VALUES (?,?,?,?)""",
            (public_id, experiment_id, manifest_json, checksum),
        )
        return public_id

    def latest_manifest(
        self, connection: sqlite3.Connection, experiment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM base_training_reproducibility_manifests
            WHERE base_training_experiment_id=? ORDER BY created_at DESC, id DESC LIMIT 1""",
            (experiment_id,),
        ).fetchone()
