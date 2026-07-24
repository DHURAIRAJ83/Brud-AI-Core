"""Repository for Phase 14 model-release registry, candidates, artifacts,
eligibility, model cards, manifests, approvals, releases, comparisons,
and rollback evidence."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "model_release_family_id",
    "core_model_version_id",
    "checkpoint_id",
    "tokenizer_version_id",
    "dataset_version_id",
    "instruction_tuning_candidate_id",
    "model_evaluation_run_id",
    "model_release_candidate_id",
    "left_release_id",
    "right_release_id",
    "source_release_id",
    "target_release_id",
    "model_release_rollback_plan_id",
    "model_release_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("model release row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class ModelReleaseRepository(BaseRepository):
    # --- families -----------------------------------------------------

    def create_family(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_families(public_id,name,slug,description,
            intended_use,supported_languages_json,compatibility_policy_json,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values["slug"],
                values.get("description", ""),
                values.get("intended_use", ""),
                values["supported_languages_json"],
                values["compatibility_policy_json"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def family(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM model_release_families WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("release family not found")
        return row

    def list_families(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM model_release_families ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def update_family(
        self, connection: sqlite3.Connection, family_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE model_release_families SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), family_id),
        )

    # --- candidates -----------------------------------------------------

    def create_candidate(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_candidates(public_id,model_release_family_id,
            core_model_version_id,checkpoint_id,tokenizer_version_id,dataset_version_id,
            instruction_tuning_candidate_id,model_evaluation_run_id,label,notes,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_release_family_id"],
                values["core_model_version_id"],
                values["checkpoint_id"],
                values["tokenizer_version_id"],
                values.get("dataset_version_id"),
                values.get("instruction_tuning_candidate_id"),
                values.get("model_evaluation_run_id"),
                values.get("label"),
                values.get("notes", ""),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def candidate(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT c.*, f.public_id AS model_release_family_public_id,
            f.compatibility_policy_json AS family_compatibility_policy_json,
            f.lifecycle_status AS family_lifecycle_status,
            m.public_id AS core_model_version_public_id,
            m.lifecycle_status AS core_model_lifecycle_status,
            m.architecture_summary_json AS core_model_architecture_summary_json,
            m.weights_checksum_sha256 AS core_model_weights_checksum_sha256,
            m.config_checksum_sha256 AS core_model_config_checksum_sha256,
            m.config_id AS core_model_config_id,
            ck.public_id AS checkpoint_public_id, ck.safe_name AS checkpoint_safe_name,
            ck.model_checksum_sha256 AS checkpoint_model_checksum_sha256,
            ck.status AS checkpoint_status,
            t.public_id AS tokenizer_version_public_id,
            t.model_checksum_sha256 AS tokenizer_model_checksum_sha256,
            t.vocabulary_checksum_sha256 AS tokenizer_vocabulary_checksum_sha256,
            t.vocabulary_size AS tokenizer_vocabulary_size,
            t.special_tokens_json AS tokenizer_special_tokens_json,
            t.artifact_manifest_json AS tokenizer_artifact_manifest_json,
            d.public_id AS dataset_version_public_id,
            d.checksum_sha256 AS dataset_checksum_sha256,
            d.manifest_json AS dataset_manifest_json,
            itc.public_id AS instruction_tuning_candidate_public_id,
            itc.status AS instruction_tuning_candidate_status,
            r.public_id AS model_evaluation_run_public_id,
            r.candidate_core_model_version_id AS evaluation_run_candidate_core_model_version_id
            FROM model_release_candidates c
            JOIN model_release_families f ON f.id=c.model_release_family_id
            JOIN core_model_versions m ON m.id=c.core_model_version_id
            JOIN pretraining_checkpoints ck ON ck.id=c.checkpoint_id
            JOIN tokenizer_versions t ON t.id=c.tokenizer_version_id
            LEFT JOIN dataset_versions d ON d.id=c.dataset_version_id
            LEFT JOIN instruction_tuning_candidates itc ON itc.id=c.instruction_tuning_candidate_id
            LEFT JOIN model_evaluation_runs r ON r.id=c.model_evaluation_run_id
            WHERE c.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("release candidate not found")
        return row

    def list_candidates(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM model_release_candidates ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def update_candidate(
        self, connection: sqlite3.Connection, candidate_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE model_release_candidates SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), candidate_id),
        )

    # --- artifacts -----------------------------------------------------

    def record_artifact(
        self, connection: sqlite3.Connection, candidate_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_artifacts(public_id,model_release_candidate_id,
            artifact_type,source_entity_public_id,logical_name,storage_key,size_bytes,
            checksum_algorithm,checksum,verification_status,required,details_json,verified_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                candidate_id,
                values["artifact_type"],
                values.get("source_entity_public_id"),
                values["logical_name"],
                values["storage_key"],
                values.get("size_bytes", 0),
                values.get("checksum_algorithm", "sha256"),
                values.get("checksum"),
                values.get("verification_status", "pending"),
                1 if values.get("required", True) else 0,
                values.get("details_json", "{}"),
                values.get("verified_at"),
            ),
        )
        return public_id

    def artifacts_for_candidate(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM model_release_artifacts WHERE model_release_candidate_id=?
            ORDER BY id""",
            (candidate_id,),
        ).fetchall()

    # --- manifests -----------------------------------------------------

    def record_manifest(
        self, connection: sqlite3.Connection, candidate_id: int, manifest_json: str, checksum: str
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_manifests(public_id,model_release_candidate_id,
            manifest_json,manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (public_id, candidate_id, manifest_json, checksum),
        )
        return public_id

    def latest_manifest(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM model_release_manifests WHERE model_release_candidate_id=?
            ORDER BY created_at DESC,id DESC LIMIT 1""",
            (candidate_id,),
        ).fetchone()

    # --- model cards -----------------------------------------------------

    def record_model_card(
        self, connection: sqlite3.Connection, candidate_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_model_cards(public_id,model_release_candidate_id,
            card_markdown,card_checksum_sha256,validation_status,validation_issues_json)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                candidate_id,
                values["card_markdown"],
                values["card_checksum_sha256"],
                values.get("validation_status", "not_validated"),
                values.get("validation_issues_json", "[]"),
            ),
        )
        return public_id

    def latest_model_card(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM model_release_model_cards WHERE model_release_candidate_id=?
            ORDER BY created_at DESC,id DESC LIMIT 1""",
            (candidate_id,),
        ).fetchone()

    # --- eligibility -----------------------------------------------------

    def record_eligibility(
        self, connection: sqlite3.Connection, candidate_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_eligibility_assessments(public_id,
            model_release_candidate_id,status,dimension_scores_json,blocking_issue_count,
            warning_issue_count,rationale_json,eligibility_checksum_sha256,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                candidate_id,
                values["status"],
                values.get("dimension_scores_json", "{}"),
                values.get("blocking_issue_count", 0),
                values.get("warning_issue_count", 0),
                values.get("rationale_json", "{}"),
                values["eligibility_checksum_sha256"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def latest_eligibility(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM model_release_eligibility_assessments
            WHERE model_release_candidate_id=? ORDER BY created_at DESC,id DESC LIMIT 1""",
            (candidate_id,),
        ).fetchone()

    # --- issues -----------------------------------------------------

    def record_issue(
        self, connection: sqlite3.Connection, candidate_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_issues(public_id,model_release_candidate_id,
            issue_code,severity,message,details_json) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                candidate_id,
                values["issue_code"],
                values["severity"],
                values["message"],
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def issues_for_candidate(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM model_release_issues WHERE model_release_candidate_id=? ORDER BY id",
            (candidate_id,),
        ).fetchall()

    # --- approvals -----------------------------------------------------

    def record_approval(
        self, connection: sqlite3.Connection, candidate_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_approvals(public_id,model_release_candidate_id,
            admin_public_id,role,decision,comment,eligibility_checksum_sha256,
            manifest_checksum_sha256) VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                candidate_id,
                values["admin_public_id"],
                values["role"],
                values["decision"],
                values.get("comment", ""),
                values["eligibility_checksum_sha256"],
                values.get("manifest_checksum_sha256"),
            ),
        )
        return public_id

    def approvals_for_candidate(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM model_release_approvals WHERE model_release_candidate_id=?
            ORDER BY created_at""",
            (candidate_id,),
        ).fetchall()

    # --- releases -----------------------------------------------------

    def create_release(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_releases(public_id,model_release_family_id,
            model_release_candidate_id,version,prerelease_label,status,deployment_eligibility,
            release_manifest_public_id,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_release_family_id"],
                values["model_release_candidate_id"],
                values["version"],
                values.get("prerelease_label"),
                values.get("status", "draft"),
                values.get("deployment_eligibility", "not_deployable"),
                values.get("release_manifest_public_id"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def release(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*, f.public_id AS model_release_family_public_id,
            c.public_id AS model_release_candidate_public_id
            FROM model_releases r
            JOIN model_release_families f ON f.id=r.model_release_family_id
            JOIN model_release_candidates c ON c.id=r.model_release_candidate_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("release not found")
        return row

    def list_releases(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM model_releases ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def releases_for_family(
        self, connection: sqlite3.Connection, family_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM model_releases WHERE model_release_family_id=? ORDER BY created_at",
            (family_id,),
        ).fetchall()

    def update_release(
        self, connection: sqlite3.Connection, release_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE model_releases SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), release_id),
        )

    def release_version_exists(
        self, connection: sqlite3.Connection, family_id: int, version: str
    ) -> bool:
        row = connection.execute(
            "SELECT 1 FROM model_releases WHERE model_release_family_id=? AND version=?",
            (family_id, version),
        ).fetchone()
        return row is not None

    # --- comparisons -----------------------------------------------------

    def record_comparison(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_comparisons(public_id,left_release_id,right_release_id,
            compatibility,ranked,fields_json,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["left_release_id"],
                values["right_release_id"],
                values["compatibility"],
                1 if values.get("ranked") else 0,
                values.get("fields_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def comparison(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM model_release_comparisons WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("comparison not found")
        return row

    # --- rollback plans -----------------------------------------------------

    def create_rollback_plan(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_rollback_plans(public_id,source_release_id,
            target_release_id,reason,compatibility_result_json,target_verification_json,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["source_release_id"],
                values["target_release_id"],
                values.get("reason", ""),
                values.get("compatibility_result_json", "{}"),
                values.get("target_verification_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def rollback_plan(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT p.*, s.public_id AS source_release_public_id,
            t.public_id AS target_release_public_id
            FROM model_release_rollback_plans p
            JOIN model_releases s ON s.id=p.source_release_id
            JOIN model_releases t ON t.id=p.target_release_id
            WHERE p.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("rollback plan not found")
        return row

    def update_rollback_plan(
        self, connection: sqlite3.Connection, plan_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE model_release_rollback_plans SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), plan_id),
        )

    # --- rollback events -----------------------------------------------------

    def record_rollback_event(
        self, connection: sqlite3.Connection, plan_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_rollback_events(public_id,
            model_release_rollback_plan_id,previous_release_public_id,new_release_public_id,
            approval_evidence_json,executed_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                plan_id,
                values["previous_release_public_id"],
                values["new_release_public_id"],
                values.get("approval_evidence_json", "{}"),
                values["executed_by_admin_public_id"],
            ),
        )
        return public_id

    # --- bundles -----------------------------------------------------

    def record_bundle(
        self, connection: sqlite3.Connection, release_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO model_release_bundles(public_id,model_release_id,bundle_format,
            inventory_json,bundle_checksum_sha256,size_bytes,storage_key,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                release_id,
                values.get("bundle_format", "zip"),
                values.get("inventory_json", "[]"),
                values["bundle_checksum_sha256"],
                values.get("size_bytes", 0),
                values["storage_key"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def bundles_for_release(
        self, connection: sqlite3.Connection, release_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM model_release_bundles WHERE model_release_id=? ORDER BY created_at",
            (release_id,),
        ).fetchall()

    def bundle(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM model_release_bundles WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("bundle not found")
        return row
