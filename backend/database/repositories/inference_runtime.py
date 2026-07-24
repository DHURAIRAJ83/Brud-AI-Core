"""Repository for Phase 15 controlled inference runtime, model assignment,
canary, and rollback evidence."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "inference_runtime_profile_id",
    "inference_runtime_instance_id",
    "model_release_id",
    "model_assignment_scope_id",
    "model_assignment_id",
    "model_assignment_version_id",
    "inference_session_id",
    "inference_request_id",
    "inference_canary_run_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("inference runtime row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class InferenceRuntimeRepository(BaseRepository):
    # --- runtime profiles -----------------------------------------------------

    def create_profile(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_runtime_profiles(public_id,name,runtime_type,enabled,
            device,dtype,maximum_loaded_models,maximum_concurrent_requests,
            maximum_context_length,maximum_new_tokens,request_timeout_seconds,
            idle_unload_seconds,minimum_available_memory_bytes,minimum_available_disk_bytes,
            resource_policy_json,generation_defaults_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("runtime_type", "local_cpu"),
                1 if values.get("enabled", True) else 0,
                values.get("device", "cpu"),
                values.get("dtype", "float32"),
                values.get("maximum_loaded_models", 1),
                values.get("maximum_concurrent_requests", 1),
                values["maximum_context_length"],
                values["maximum_new_tokens"],
                values.get("request_timeout_seconds", 30),
                values.get("idle_unload_seconds", 900),
                values["minimum_available_memory_bytes"],
                values["minimum_available_disk_bytes"],
                values.get("resource_policy_json", "{}"),
                values.get("generation_defaults_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def profile(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM inference_runtime_profiles WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("runtime profile not found")
        return row

    def list_profiles(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_runtime_profiles ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def update_profile(
        self, connection: sqlite3.Connection, profile_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE inference_runtime_profiles SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), profile_id),
        )

    # --- runtime instances -----------------------------------------------------

    def create_instance(
        self, connection: sqlite3.Connection, profile_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_runtime_instances(public_id,inference_runtime_profile_id,
            status) VALUES (?,?,?)""",
            (public_id, profile_id, values.get("status", "offline")),
        )
        return public_id

    def instance(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT i.*, p.public_id AS inference_runtime_profile_public_id,
            p.maximum_context_length AS profile_maximum_context_length,
            p.maximum_new_tokens AS profile_maximum_new_tokens,
            p.maximum_loaded_models AS profile_maximum_loaded_models,
            p.maximum_concurrent_requests AS profile_maximum_concurrent_requests,
            p.request_timeout_seconds AS profile_request_timeout_seconds,
            p.minimum_available_memory_bytes AS profile_minimum_available_memory_bytes,
            p.minimum_available_disk_bytes AS profile_minimum_available_disk_bytes,
            p.dtype AS profile_dtype, p.device AS profile_device
            FROM inference_runtime_instances i
            JOIN inference_runtime_profiles p ON p.id=i.inference_runtime_profile_id
            WHERE i.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("runtime instance not found")
        return row

    def list_instances(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_runtime_instances ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def update_instance(
        self, connection: sqlite3.Connection, instance_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE inference_runtime_instances SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), instance_id),
        )

    # --- health checks -----------------------------------------------------

    def record_health_check(
        self, connection: sqlite3.Connection, instance_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_runtime_health_checks(public_id,
            inference_runtime_instance_id,check_type,status,details_json)
            VALUES (?,?,?,?,?)""",
            (
                public_id,
                instance_id,
                values["check_type"],
                values["status"],
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def health_checks_for_instance(
        self, connection: sqlite3.Connection, instance_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM inference_runtime_health_checks
            WHERE inference_runtime_instance_id=? ORDER BY id""",
            (instance_id,),
        ).fetchall()

    def latest_health_check_by_type(
        self, connection: sqlite3.Connection, instance_id: int
    ) -> dict[str, sqlite3.Row]:
        rows = self.health_checks_for_instance(connection, instance_id)
        latest: dict[str, sqlite3.Row] = {}
        for row in rows:
            latest[row["check_type"]] = row
        return latest

    # --- compatibility assessments -----------------------------------------------------

    def record_compatibility(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_model_compatibility_assessments(public_id,model_release_id,
            inference_runtime_profile_id,status,dimension_scores_json,blocking_issue_count,
            warning_issue_count,rationale_json,compatibility_checksum_sha256,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_release_id"],
                values["inference_runtime_profile_id"],
                values["status"],
                values.get("dimension_scores_json", "{}"),
                values.get("blocking_issue_count", 0),
                values.get("warning_issue_count", 0),
                values.get("rationale_json", "{}"),
                values["compatibility_checksum_sha256"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def latest_compatibility(
        self, connection: sqlite3.Connection, release_id: int, profile_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM inference_model_compatibility_assessments
            WHERE model_release_id=? AND inference_runtime_profile_id=?
            ORDER BY id DESC LIMIT 1""",
            (release_id, profile_id),
        ).fetchone()

    # --- assignment scopes -----------------------------------------------------

    def ensure_default_scopes(self, connection: sqlite3.Connection) -> None:
        defaults = (
            ("admin_diagnostic", 1, "Admin-only bounded single-prompt diagnostics."),
            ("admin_chat_lab", 1, "Admin-only bounded multi-turn testing sessions."),
            ("internal_canary", 1, "Controlled internal comparison against a small request set."),
            ("public_chat", 0, "Disabled by default; requires a separate explicit activation."),
        )
        for scope_key, enabled, description in defaults:
            existing = connection.execute(
                "SELECT 1 FROM inference_assignment_scopes WHERE scope_key=?", (scope_key,)
            ).fetchone()
            if existing:
                continue
            connection.execute(
                """INSERT INTO inference_assignment_scopes(public_id,scope_key,enabled,
                description) VALUES (?,?,?,?)""",
                (str(uuid4()), scope_key, enabled, description),
            )

    def scope_by_key(self, connection: sqlite3.Connection, scope_key: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM inference_assignment_scopes WHERE scope_key=?", (scope_key,)
        ).fetchone()
        if not row:
            raise NotFoundError("assignment scope not found")
        return row

    def list_scopes(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_assignment_scopes ORDER BY scope_key"
        ).fetchall()

    # --- assignments -----------------------------------------------------

    def create_assignment(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_model_assignments(public_id,model_assignment_scope_id,
            model_release_id,inference_runtime_profile_id,generation_config_json,
            context_policy_json,fallback_policy_json,canary_percentage,start_at,expire_at,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_assignment_scope_id"],
                values["model_release_id"],
                values["inference_runtime_profile_id"],
                values.get("generation_config_json", "{}"),
                values.get("context_policy_json", "{}"),
                values.get("fallback_policy_json", "{}"),
                values.get("canary_percentage", 0),
                values.get("start_at"),
                values.get("expire_at"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def assignment(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT a.*, s.scope_key AS scope_key, s.enabled AS scope_enabled,
            r.public_id AS release_public_id,
            p.public_id AS runtime_profile_public_id
            FROM inference_model_assignments a
            JOIN inference_assignment_scopes s ON s.id=a.model_assignment_scope_id
            JOIN model_releases r ON r.id=a.model_release_id
            JOIN inference_runtime_profiles p ON p.id=a.inference_runtime_profile_id
            WHERE a.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("assignment not found")
        return row

    def list_assignments(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_model_assignments ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def update_assignment(
        self, connection: sqlite3.Connection, assignment_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"""UPDATE inference_model_assignments SET {columns},updated_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (*fields.values(), assignment_id),
        )

    # --- assignment versions -----------------------------------------------------

    def create_version(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        next_version = connection.execute(
            """SELECT COALESCE(MAX(version_number),0)+1 FROM inference_assignment_versions
            WHERE model_assignment_id=?""",
            (values["model_assignment_id"],),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO inference_assignment_versions(public_id,model_assignment_id,
            version_number,model_release_id,inference_runtime_profile_id,
            generation_config_json,context_policy_json,fallback_policy_json,
            canary_percentage,eligibility_checksum_sha256,compatibility_checksum_sha256,
            approval_checksum_sha256,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_assignment_id"],
                next_version,
                values["model_release_id"],
                values["inference_runtime_profile_id"],
                values.get("generation_config_json", "{}"),
                values.get("context_policy_json", "{}"),
                values.get("fallback_policy_json", "{}"),
                values.get("canary_percentage", 0),
                values["eligibility_checksum_sha256"],
                values["compatibility_checksum_sha256"],
                values.get("approval_checksum_sha256"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def versions_for_assignment(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM inference_assignment_versions WHERE model_assignment_id=?
            ORDER BY version_number""",
            (assignment_id,),
        ).fetchall()

    def version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM inference_assignment_versions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("assignment version not found")
        return row

    def latest_version(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM inference_assignment_versions WHERE model_assignment_id=?
            ORDER BY version_number DESC LIMIT 1""",
            (assignment_id,),
        ).fetchone()

    # --- approvals -----------------------------------------------------

    def record_approval(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_assignment_approvals(public_id,model_assignment_id,
            model_assignment_version_id,admin_public_id,role,decision,comment,
            eligibility_checksum_sha256,compatibility_checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_assignment_id"],
                values.get("model_assignment_version_id"),
                values["admin_public_id"],
                values["role"],
                values["decision"],
                values.get("comment", ""),
                values.get("eligibility_checksum_sha256"),
                values.get("compatibility_checksum_sha256"),
            ),
        )
        return public_id

    def approvals_for_assignment(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM inference_assignment_approvals WHERE model_assignment_id=?
            ORDER BY id""",
            (assignment_id,),
        ).fetchall()

    # --- events -----------------------------------------------------

    def record_event(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_assignment_events(public_id,model_assignment_id,
            event_type,details_json,actor_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["model_assignment_id"],
                values["event_type"],
                values.get("details_json", "{}"),
                values.get("actor_admin_public_id"),
            ),
        )
        return public_id

    def events_for_assignment(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_assignment_events WHERE model_assignment_id=? ORDER BY id",
            (assignment_id,),
        ).fetchall()

    # --- sessions -----------------------------------------------------

    def create_session(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_sessions(public_id,model_assignment_id,
            inference_runtime_instance_id,scope,max_turns,created_by_admin_public_id,
            expires_at) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_assignment_id"],
                values.get("inference_runtime_instance_id"),
                values["scope"],
                values["max_turns"],
                values["created_by_admin_public_id"],
                values.get("expires_at"),
            ),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM inference_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("session not found")
        return row

    def update_session(
        self, connection: sqlite3.Connection, session_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE inference_sessions SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), session_id),
        )

    def messages_for_session(
        self, connection: sqlite3.Connection, session_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_requests WHERE inference_session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()

    # --- requests / results / failures -----------------------------------------------------

    def record_request(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_requests(public_id,inference_runtime_instance_id,
            model_assignment_id,model_assignment_version_id,scope,inference_session_id,
            prompt_checksum_sha256,input_token_count,maximum_new_token_count,status,
            started_at,ended_at,runtime_milliseconds,stop_reason,failure_code)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["inference_runtime_instance_id"],
                values["model_assignment_id"],
                values.get("model_assignment_version_id"),
                values["scope"],
                values.get("inference_session_id"),
                values["prompt_checksum_sha256"],
                values.get("input_token_count", 0),
                values.get("maximum_new_token_count", 0),
                values["status"],
                values.get("started_at"),
                values.get("ended_at"),
                values.get("runtime_milliseconds"),
                values.get("stop_reason"),
                values.get("failure_code"),
            ),
        )
        return public_id

    def requests_for_assignment(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_requests WHERE model_assignment_id=? ORDER BY id",
            (assignment_id,),
        ).fetchall()

    def record_result(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_results(public_id,inference_request_id,
            output_checksum_sha256,generated_token_count,stop_reason,runtime_milliseconds,
            role_token_leakage_flag,prompt_leakage_flag,repetition_warning,unicode_valid_flag,
            model_release_public_id,model_assignment_version_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["inference_request_id"],
                values["output_checksum_sha256"],
                values.get("generated_token_count", 0),
                values["stop_reason"],
                values.get("runtime_milliseconds", 0),
                1 if values.get("role_token_leakage_flag") else 0,
                1 if values.get("prompt_leakage_flag") else 0,
                1 if values.get("repetition_warning") else 0,
                1 if values.get("unicode_valid_flag", True) else 0,
                values["model_release_public_id"],
                values.get("model_assignment_version_public_id"),
            ),
        )
        return public_id

    def result_for_request(
        self, connection: sqlite3.Connection, request_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM inference_results WHERE inference_request_id=? LIMIT 1", (request_id,)
        ).fetchone()

    def record_failure(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_failures(public_id,inference_runtime_instance_id,
            inference_request_id,model_assignment_id,failure_code,failure_summary,
            details_json) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values.get("inference_runtime_instance_id"),
                values.get("inference_request_id"),
                values.get("model_assignment_id"),
                values["failure_code"],
                values.get("failure_summary", ""),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def failures_for_assignment(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_failures WHERE model_assignment_id=? ORDER BY id",
            (assignment_id,),
        ).fetchall()

    # --- canary -----------------------------------------------------

    def record_canary_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_canary_runs(public_id,model_assignment_id,run_status,
            percentage,max_request_count,requests_executed,stop_reason,metrics_json,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["model_assignment_id"],
                values["run_status"],
                values.get("percentage", 0),
                values.get("max_request_count", 0),
                values.get("requests_executed", 0),
                values.get("stop_reason"),
                values.get("metrics_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def latest_canary_run(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM inference_canary_runs WHERE model_assignment_id=?
            ORDER BY id DESC LIMIT 1""",
            (assignment_id,),
        ).fetchone()

    def canary_runs_for_assignment(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_canary_runs WHERE model_assignment_id=? ORDER BY id",
            (assignment_id,),
        ).fetchall()

    def record_canary_result(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_canary_results(public_id,inference_canary_run_id,
            inference_request_id,routing_key,used_model,success,timed_out,latency_ms,
            input_tokens,output_tokens,role_leakage,prompt_leakage,duplicate_output,
            unicode_valid,stop_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["inference_canary_run_id"],
                values.get("inference_request_id"),
                values["routing_key"],
                1 if values.get("used_model") else 0,
                1 if values.get("success") else 0,
                1 if values.get("timed_out") else 0,
                values.get("latency_ms", 0),
                values.get("input_tokens", 0),
                values.get("output_tokens", 0),
                1 if values.get("role_leakage") else 0,
                1 if values.get("prompt_leakage") else 0,
                1 if values.get("duplicate_output") else 0,
                1 if values.get("unicode_valid", True) else 0,
                values.get("stop_reason"),
            ),
        )
        return public_id

    def results_for_canary_run(
        self, connection: sqlite3.Connection, run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM inference_canary_results WHERE inference_canary_run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()

    # --- runtime manifests -----------------------------------------------------

    def record_manifest(
        self, connection: sqlite3.Connection, assignment_id: int, manifest_json: str, checksum: str
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO inference_runtime_manifests(public_id,model_assignment_id,
            manifest_json,manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (public_id, assignment_id, manifest_json, checksum),
        )
        return public_id

    def latest_manifest(
        self, connection: sqlite3.Connection, assignment_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM inference_runtime_manifests WHERE model_assignment_id=?
            ORDER BY id DESC LIMIT 1""",
            (assignment_id,),
        ).fetchone()
