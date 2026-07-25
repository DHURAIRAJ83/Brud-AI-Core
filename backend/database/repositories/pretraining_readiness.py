"""Repository for Phase 21A: tokenizer corpus builds (bridging approved
Phase 20 corpus releases into Phase 6 dataset-version format),
tokenizer candidate comparisons/selection evaluations, frozen
pretraining dataset snapshots, base-model resource estimates, tiny
bounded pretraining smoke runs, and the 17-dimension base-model
readiness gate."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "corpus_release_id",
    "dataset_version_id",
    "tokenizer_corpus_build_id",
    "recommended_tokenizer_version_id",
    "tokenizer_candidate_comparison_id",
    "tokenizer_version_id",
    "pretraining_dataset_snapshot_id",
    "base_model_resource_estimate_id",
    "pretraining_job_id",
    "evaluation_id",
    "pretraining_smoke_run_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("pretraining readiness row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class PretrainingReadinessRepository(BaseRepository):
    # --- tokenizer corpus builds -----------------------------------------------------

    def create_tokenizer_corpus_build(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO tokenizer_corpus_builds(public_id,corpus_release_id,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (public_id, values["corpus_release_id"], values["created_by_admin_public_id"]),
        )
        return public_id

    def tokenizer_corpus_build(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM tokenizer_corpus_builds WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("tokenizer corpus build not found")
        return row

    def list_tokenizer_corpus_builds(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM tokenizer_corpus_builds ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_tokenizer_corpus_build(
        self, connection: sqlite3.Connection, build_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE tokenizer_corpus_builds SET {columns} WHERE id=?",
            (*fields.values(), build_id),
        )

    # --- tokenizer candidate comparisons -----------------------------------------------------

    def create_tokenizer_candidate_comparison(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO tokenizer_candidate_comparisons(public_id,tokenizer_corpus_build_id,
            candidate_tokenizer_version_ids_json,created_by_admin_public_id)
            VALUES (?,?,?,?)""",
            (
                public_id,
                values["tokenizer_corpus_build_id"],
                values.get("candidate_tokenizer_version_ids_json", "[]"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def tokenizer_candidate_comparison(
        self, connection: sqlite3.Connection, public_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM tokenizer_candidate_comparisons WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("tokenizer candidate comparison not found")
        return row

    def update_tokenizer_candidate_comparison(
        self, connection: sqlite3.Connection, comparison_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE tokenizer_candidate_comparisons SET {columns} WHERE id=?",
            (*fields.values(), comparison_id),
        )

    # --- tokenizer selection evaluations (append-only) -----------------------

    def record_tokenizer_selection_evaluation(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO tokenizer_selection_evaluations(public_id,
            tokenizer_candidate_comparison_id,tokenizer_version_id,vocabulary_size,
            dimensions_json,metrics_json,final_status,rationale)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["tokenizer_candidate_comparison_id"],
                values["tokenizer_version_id"],
                values["vocabulary_size"],
                values.get("dimensions_json", "{}"),
                values.get("metrics_json", "{}"),
                values["final_status"],
                values.get("rationale", ""),
            ),
        )
        return public_id

    def evaluations_for_comparison(
        self, connection: sqlite3.Connection, comparison_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM tokenizer_selection_evaluations "
            "WHERE tokenizer_candidate_comparison_id=? ORDER BY id",
            (comparison_id,),
        ).fetchall()

    # --- pretraining dataset snapshots (immutable) -----------------------------

    def create_pretraining_dataset_snapshot(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO pretraining_dataset_snapshots(public_id,corpus_release_id,
            dataset_version_id,tokenizer_version_id,manifest_checksum_sha256,
            export_checksums_json,tokenizer_checksum_sha256,train_record_count,
            validation_record_count,test_record_count,train_token_count,
            validation_token_count,test_token_count,maximum_sequence_length,
            partition_algorithm_version,deterministic_seed,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["corpus_release_id"],
                values["dataset_version_id"],
                values["tokenizer_version_id"],
                values["manifest_checksum_sha256"],
                values.get("export_checksums_json", "[]"),
                values["tokenizer_checksum_sha256"],
                values.get("train_record_count", 0),
                values.get("validation_record_count", 0),
                values.get("test_record_count", 0),
                values.get("train_token_count", 0),
                values.get("validation_token_count", 0),
                values.get("test_token_count", 0),
                values["maximum_sequence_length"],
                values.get("partition_algorithm_version", "v1"),
                values.get("deterministic_seed", 42),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def pretraining_dataset_snapshot(
        self, connection: sqlite3.Connection, public_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM pretraining_dataset_snapshots WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("pretraining dataset snapshot not found")
        return row

    def list_pretraining_dataset_snapshots(
        self, connection: sqlite3.Connection
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM pretraining_dataset_snapshots ORDER BY created_at DESC, id DESC"
        ).fetchall()

    # --- base model resource estimates -----------------------------------------------------

    def create_base_model_resource_estimate(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_model_resource_estimates(public_id,profile_name,
            vocabulary_size,context_length,hidden_size,num_hidden_layers,
            num_attention_heads,intermediate_size,parameter_count,parameter_memory_bytes,
            gradient_memory_bytes,optimizer_state_memory_bytes,activation_memory_bytes,
            estimated_peak_ram_bytes,checkpoint_disk_bytes,optimizer_disk_bytes,
            estimated_tokens_per_second,estimated_training_duration_seconds_min,
            estimated_training_duration_seconds_max,safe_ram_ceiling_bytes,
            within_safe_limit,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["profile_name"],
                values["vocabulary_size"],
                values["context_length"],
                values["hidden_size"],
                values["num_hidden_layers"],
                values["num_attention_heads"],
                values["intermediate_size"],
                values["parameter_count"],
                values["parameter_memory_bytes"],
                values["gradient_memory_bytes"],
                values["optimizer_state_memory_bytes"],
                values["activation_memory_bytes"],
                values["estimated_peak_ram_bytes"],
                values["checkpoint_disk_bytes"],
                values["optimizer_disk_bytes"],
                values["estimated_tokens_per_second"],
                values["estimated_training_duration_seconds_min"],
                values["estimated_training_duration_seconds_max"],
                values["safe_ram_ceiling_bytes"],
                values["within_safe_limit"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def base_model_resource_estimate(
        self, connection: sqlite3.Connection, public_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM base_model_resource_estimates WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("base model resource estimate not found")
        return row

    def list_base_model_resource_estimates(
        self, connection: sqlite3.Connection
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM base_model_resource_estimates ORDER BY created_at DESC, id DESC"
        ).fetchall()

    # --- pretraining smoke runs -----------------------------------------------------

    def create_pretraining_smoke_run(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO pretraining_smoke_runs(public_id,pretraining_dataset_snapshot_id,
            base_model_resource_estimate_id,total_steps,created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["pretraining_dataset_snapshot_id"],
                values["base_model_resource_estimate_id"],
                values.get("total_steps", 0),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def pretraining_smoke_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM pretraining_smoke_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("pretraining smoke run not found")
        return row

    def update_pretraining_smoke_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE pretraining_smoke_runs SET {columns} WHERE id=?", (*fields.values(), run_id)
        )

    def list_pretraining_smoke_runs(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM pretraining_smoke_runs ORDER BY created_at DESC, id DESC"
        ).fetchall()

    # --- base model readiness -----------------------------------------------------

    def create_base_model_readiness_evaluation(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_model_readiness_evaluations(public_id,
            pretraining_dataset_snapshot_id,tokenizer_candidate_comparison_id,
            base_model_resource_estimate_id,pretraining_smoke_run_id,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["pretraining_dataset_snapshot_id"],
                values.get("tokenizer_candidate_comparison_id"),
                values.get("base_model_resource_estimate_id"),
                values.get("pretraining_smoke_run_id"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def base_model_readiness_evaluation(
        self, connection: sqlite3.Connection, public_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM base_model_readiness_evaluations WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("base model readiness evaluation not found")
        return row

    def update_base_model_readiness_evaluation(
        self, connection: sqlite3.Connection, evaluation_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE base_model_readiness_evaluations SET {columns} WHERE id=?",
            (*fields.values(), evaluation_id),
        )

    def list_base_model_readiness_evaluations(
        self, connection: sqlite3.Connection
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM base_model_readiness_evaluations ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def record_base_model_readiness_dimension(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO base_model_readiness_dimensions(public_id,evaluation_id,dimension,
            status,details_json) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["evaluation_id"],
                values["dimension"],
                values["status"],
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def dimensions_for_evaluation(
        self, connection: sqlite3.Connection, evaluation_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM base_model_readiness_dimensions WHERE evaluation_id=? ORDER BY id",
            (evaluation_id,),
        ).fetchall()
