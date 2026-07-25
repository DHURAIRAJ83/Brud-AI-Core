"""Repository for Phase 17 conversation sessions, turns, summaries,
memory consent/items/versions/embeddings, memory retrieval, chat
orchestration, evaluation, and the conversation-memory manifest."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "memory_policy_id",
    "session_id",
    "consent_id",
    "source_session_id",
    "source_turn_id",
    "current_version_id",
    "turn_id",
    "summary_id",
    "memory_item_id",
    "memory_item_version_id",
    "embedding_model_id",
    "retrieval_profile_id",
    "retrieval_run_id",
    "context_assembly_id",
    "request_turn_id",
    "orchestration_run_id",
    "response_turn_id",
    "rag_chunk_id",
    "evaluation_suite_id",
    "evaluation_run_id",
    "model_assignment_id",
    "rag_retrieval_profile_id",
    "memory_retrieval_run_id",
    "rag_retrieval_run_id",
    "grounded_response_id",
    "parent_turn_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("conversation memory row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class ConversationMemoryRepository(BaseRepository):
    # --- memory policies -----------------------------------------------------

    def create_policy(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO conversation_memory_policies(public_id,name,description,
            default_session_mode,allow_short_term_context,allow_session_summary,
            allow_long_term_memory,require_explicit_consent,maximum_session_turns,
            maximum_session_age_seconds,maximum_short_term_tokens,maximum_summary_tokens,
            maximum_memory_items,default_memory_ttl_seconds,allowed_memory_categories_json,
            forbidden_content_categories_json,retrieval_configuration_json,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("description", ""),
                values.get("default_session_mode", "private_no_persist"),
                1 if values.get("allow_short_term_context", True) else 0,
                1 if values.get("allow_session_summary", True) else 0,
                1 if values.get("allow_long_term_memory", False) else 0,
                1 if values.get("require_explicit_consent", True) else 0,
                values.get("maximum_session_turns", 20),
                values.get("maximum_session_age_seconds", 3600),
                values.get("maximum_short_term_tokens", 800),
                values.get("maximum_summary_tokens", 200),
                values.get("maximum_memory_items", 50),
                values.get("default_memory_ttl_seconds", 7_776_000),
                values.get("allowed_memory_categories_json", "[]"),
                values.get("forbidden_content_categories_json", "[]"),
                values.get("retrieval_configuration_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def policy(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM conversation_memory_policies WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("memory policy not found")
        return row

    def list_policies(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM conversation_memory_policies ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_policy(
        self, connection: sqlite3.Connection, policy_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        fields = {**fields, "updated_at": "CURRENT_TIMESTAMP"}
        columns = ",".join(
            f"{key}=CURRENT_TIMESTAMP" if value == "CURRENT_TIMESTAMP" else f"{key}=?"
            for key, value in fields.items()
        )
        params = [value for value in fields.values() if value != "CURRENT_TIMESTAMP"]
        connection.execute(
            f"UPDATE conversation_memory_policies SET {columns} WHERE id=?", (*params, policy_id)
        )

    # --- sessions -----------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO conversation_sessions(public_id,session_mode,memory_policy_id,
            participant_scope_key,language_preference,model_assignment_id,
            rag_retrieval_profile_id,created_by_admin_public_id,status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["session_mode"],
                values["memory_policy_id"],
                values["participant_scope_key"],
                values.get("language_preference", "unknown"),
                values.get("model_assignment_id"),
                values.get("rag_retrieval_profile_id"),
                values["created_by_admin_public_id"],
                values.get("status", "active"),
            ),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT s.*, p.public_id AS memory_policy_public_id,
            rp.public_id AS rag_retrieval_profile_public_id
            FROM conversation_sessions s
            JOIN conversation_memory_policies p ON p.id=s.memory_policy_id
            LEFT JOIN rag_retrieval_profiles rp ON rp.id=s.rag_retrieval_profile_id
            WHERE s.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("session not found")
        return row

    def list_sessions(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM conversation_sessions ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_session(
        self, connection: sqlite3.Connection, session_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE conversation_sessions SET {columns} WHERE id=?",
            (*fields.values(), session_id),
        )

    # --- session participants -----------------------------------------------------

    def add_participant(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO conversation_session_participants(public_id,session_id,
            participant_type,participant_scope_key,role) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["session_id"],
                values["participant_type"],
                values["participant_scope_key"],
                values.get("role", "primary"),
            ),
        )
        return public_id

    def participants_for_session(
        self, connection: sqlite3.Connection, session_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM conversation_session_participants WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()

    # --- turns -----------------------------------------------------

    def record_turn(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO conversation_turns(public_id,session_id,sequence_number,role,
            language_category,content_checksum_sha256,stored_content,token_count,status,
            parent_turn_id) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["session_id"],
                values["sequence_number"],
                values["role"],
                values.get("language_category", "unknown"),
                values["content_checksum_sha256"],
                values.get("stored_content"),
                values.get("token_count", 0),
                values.get("status", "accepted"),
                values.get("parent_turn_id"),
            ),
        )
        return public_id

    def turn(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM conversation_turns WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("turn not found")
        return row

    def turns_for_session(
        self, connection: sqlite3.Connection, session_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM conversation_turns WHERE session_id=? ORDER BY sequence_number",
            (session_id,),
        ).fetchall()

    def latest_turn(self, connection: sqlite3.Connection, session_id: int) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM conversation_turns WHERE session_id=? "
            "ORDER BY sequence_number DESC LIMIT 1",
            (session_id,),
        ).fetchone()

    def record_turn_event(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO conversation_turn_events(public_id,turn_id,event_type,details_json)
            VALUES (?,?,?,?)""",
            (public_id, values["turn_id"], values["event_type"], values.get("details_json", "{}")),
        )
        return public_id

    # --- summaries -----------------------------------------------------

    def create_summary(self, connection: sqlite3.Connection, session_id: int) -> str:
        public_id = str(uuid4())
        connection.execute(
            "INSERT INTO conversation_summaries(public_id,session_id) VALUES (?,?)",
            (public_id, session_id),
        )
        return public_id

    def summary(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM conversation_summaries WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("summary not found")
        return row

    def summaries_for_session(
        self, connection: sqlite3.Connection, session_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM conversation_summaries WHERE session_id=? ORDER BY id DESC",
            (session_id,),
        ).fetchall()

    def update_summary(
        self, connection: sqlite3.Connection, summary_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE conversation_summaries SET {columns} WHERE id=?",
            (*fields.values(), summary_id),
        )

    def create_summary_version(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO conversation_summary_versions(public_id,summary_id,version_number,
            source_turn_start_sequence,source_turn_end_sequence,summary_language,
            summary_text_checksum_sha256,summary_text,summary_token_count,generation_method,
            validation_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["summary_id"],
                values["version_number"],
                values["source_turn_start_sequence"],
                values["source_turn_end_sequence"],
                values.get("summary_language", "unknown"),
                values["summary_text_checksum_sha256"],
                values.get("summary_text"),
                values.get("summary_token_count", 0),
                values["generation_method"],
                values.get("validation_status", "draft"),
            ),
        )
        return public_id

    def summary_version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM conversation_summary_versions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("summary version not found")
        return row

    # --- consents -----------------------------------------------------

    def create_consent(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_consents(public_id,participant_scope_key,memory_policy_id,
            purpose,allowed_categories_json,prohibited_categories_json,status,granted_at,
            expires_at,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["participant_scope_key"],
                values["memory_policy_id"],
                values["purpose"],
                values.get("allowed_categories_json", "[]"),
                values.get("prohibited_categories_json", "[]"),
                values.get("status", "active"),
                values.get("granted_at"),
                values.get("expires_at"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def consent(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM memory_consents WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("consent not found")
        return row

    def list_consents(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_consents ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def active_consent_for_purpose(
        self, connection: sqlite3.Connection, participant_scope_key: str, purpose: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM memory_consents WHERE participant_scope_key=? AND purpose=? "
            "AND status='active' ORDER BY id DESC LIMIT 1",
            (participant_scope_key, purpose),
        ).fetchone()

    def update_consent(
        self, connection: sqlite3.Connection, consent_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE memory_consents SET {columns} WHERE id=?", (*fields.values(), consent_id)
        )

    # --- memory items -----------------------------------------------------

    def create_memory_item(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_items(public_id,participant_scope_key,category,purpose,
            creation_source,confidence_type,consent_id,source_session_id,source_turn_id,
            status,valid_from,expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["participant_scope_key"],
                values["category"],
                values["purpose"],
                values["creation_source"],
                values["confidence_type"],
                values.get("consent_id"),
                values.get("source_session_id"),
                values.get("source_turn_id"),
                values.get("status", "proposed"),
                values.get("valid_from"),
                values.get("expires_at"),
            ),
        )
        return public_id

    def memory_item(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM memory_items WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("memory item not found")
        return row

    def list_memory_items(
        self, connection: sqlite3.Connection, *, participant_scope_key: str | None = None
    ) -> list[sqlite3.Row]:
        if participant_scope_key:
            return connection.execute(
                "SELECT * FROM memory_items WHERE participant_scope_key=? "
                "ORDER BY created_at DESC, id DESC",
                (participant_scope_key,),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM memory_items ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def active_memory_items_for_participant(
        self, connection: sqlite3.Connection, participant_scope_key: str
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_items WHERE participant_scope_key=? AND status='active'",
            (participant_scope_key,),
        ).fetchall()

    def update_memory_item(
        self, connection: sqlite3.Connection, item_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        fields = {**fields, "updated_at": "CURRENT_TIMESTAMP"}
        columns = ",".join(
            f"{key}=CURRENT_TIMESTAMP" if value == "CURRENT_TIMESTAMP" else f"{key}=?"
            for key, value in fields.items()
        )
        params = [value for value in fields.values() if value != "CURRENT_TIMESTAMP"]
        connection.execute(f"UPDATE memory_items SET {columns} WHERE id=?", (*params, item_id))

    def create_memory_item_version(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_item_versions(public_id,memory_item_id,version_number,
            normalized_value,display_value,source_reference,change_reason,checksum_sha256,
            created_by) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["memory_item_id"],
                values["version_number"],
                values["normalized_value"],
                values["display_value"],
                values.get("source_reference", ""),
                values.get("change_reason", "initial_creation"),
                values["checksum_sha256"],
                values["created_by"],
            ),
        )
        return public_id

    def memory_item_version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM memory_item_versions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("memory item version not found")
        return row

    def versions_for_memory_item(
        self, connection: sqlite3.Connection, memory_item_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_item_versions WHERE memory_item_id=? ORDER BY version_number",
            (memory_item_id,),
        ).fetchall()

    def record_memory_item_event(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_item_events(public_id,memory_item_id,event_type,details_json,
            created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["memory_item_id"],
                values["event_type"],
                values.get("details_json", "{}"),
                values.get("created_by_admin_public_id"),
            ),
        )
        return public_id

    def events_for_memory_item(
        self, connection: sqlite3.Connection, memory_item_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_item_events WHERE memory_item_id=? ORDER BY id",
            (memory_item_id,),
        ).fetchall()

    # --- memory embeddings -----------------------------------------------------

    def record_memory_embedding(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_embeddings(public_id,memory_item_version_id,embedding_model_id,
            content_checksum_sha256,dimensions,vector_blob,vector_checksum_sha256)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["memory_item_version_id"],
                values["embedding_model_id"],
                values["content_checksum_sha256"],
                values["dimensions"],
                values["vector_blob"],
                values["vector_checksum_sha256"],
            ),
        )
        return public_id

    def embedding_for_version(
        self, connection: sqlite3.Connection, memory_item_version_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM memory_embeddings WHERE memory_item_version_id=? "
            "ORDER BY id DESC LIMIT 1",
            (memory_item_version_id,),
        ).fetchone()

    # --- memory retrieval profiles -----------------------------------------------------

    def create_retrieval_profile(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_retrieval_profiles(public_id,name,allowed_categories_json,
            allowed_purposes_json,keyword_weight,vector_weight,recency_weight,
            user_confirmed_boost,maximum_results,minimum_score,maximum_memory_tokens,
            conflict_policy,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("allowed_categories_json", "[]"),
                values.get("allowed_purposes_json", "[]"),
                values.get("keyword_weight", 0.4),
                values.get("vector_weight", 0.6),
                values.get("recency_weight", 0.1),
                values.get("user_confirmed_boost", 0.2),
                values.get("maximum_results", 5),
                values.get("minimum_score", 0.15),
                values.get("maximum_memory_tokens", 200),
                values.get("conflict_policy", "prefer_recent"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def retrieval_profile(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM memory_retrieval_profiles WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("retrieval profile not found")
        return row

    def list_retrieval_profiles(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_retrieval_profiles ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_retrieval_profile(
        self, connection: sqlite3.Connection, profile_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        fields = {**fields, "updated_at": "CURRENT_TIMESTAMP"}
        columns = ",".join(
            f"{key}=CURRENT_TIMESTAMP" if value == "CURRENT_TIMESTAMP" else f"{key}=?"
            for key, value in fields.items()
        )
        params = [value for value in fields.values() if value != "CURRENT_TIMESTAMP"]
        connection.execute(
            f"UPDATE memory_retrieval_profiles SET {columns} WHERE id=?", (*params, profile_id)
        )

    # --- memory retrieval runs/results -----------------------------------------------------

    def create_retrieval_run(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_retrieval_runs(public_id,retrieval_profile_id,
            participant_scope_key,query_checksum_sha256,query_language,total_candidates,
            final_result_count,runtime_milliseconds,status) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["retrieval_profile_id"],
                values["participant_scope_key"],
                values["query_checksum_sha256"],
                values.get("query_language", "unknown"),
                values.get("total_candidates", 0),
                values.get("final_result_count", 0),
                values.get("runtime_milliseconds", 0),
                values.get("status", "completed"),
            ),
        )
        return public_id

    def retrieval_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM memory_retrieval_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("retrieval run not found")
        return row

    def record_retrieval_result(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_retrieval_results(public_id,retrieval_run_id,rank,
            memory_item_id,keyword_score,vector_score,recency_score,combined_score,
            conflict_status) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["retrieval_run_id"],
                values["rank"],
                values["memory_item_id"],
                values.get("keyword_score"),
                values.get("vector_score"),
                values.get("recency_score"),
                values["combined_score"],
                values.get("conflict_status", "no_conflict"),
            ),
        )
        return public_id

    def results_for_retrieval_run(
        self, connection: sqlite3.Connection, retrieval_run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_retrieval_results WHERE retrieval_run_id=? ORDER BY rank",
            (retrieval_run_id,),
        ).fetchall()

    # --- chat orchestration -----------------------------------------------------

    def record_context_assembly(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO chat_context_assemblies(public_id,session_id,maximum_model_context,
            system_tokens,current_request_tokens,conversation_tokens,summary_tokens,
            memory_tokens,rag_tokens,reserved_output_tokens,dropped_item_count,
            final_context_checksum_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["session_id"],
                values["maximum_model_context"],
                values.get("system_tokens", 0),
                values.get("current_request_tokens", 0),
                values.get("conversation_tokens", 0),
                values.get("summary_tokens", 0),
                values.get("memory_tokens", 0),
                values.get("rag_tokens", 0),
                values.get("reserved_output_tokens", 0),
                values.get("dropped_item_count", 0),
                values["final_context_checksum_sha256"],
            ),
        )
        return public_id

    def context_assembly(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM chat_context_assemblies WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("context assembly not found")
        return row

    def record_context_item(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO chat_context_items(public_id,context_assembly_id,item_type,
            source_public_id,rank,token_count,included,exclusion_reason,
            content_checksum_sha256,access_verified,injection_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["context_assembly_id"],
                values["item_type"],
                values.get("source_public_id"),
                values["rank"],
                values.get("token_count", 0),
                1 if values.get("included", True) else 0,
                values.get("exclusion_reason"),
                values.get("content_checksum_sha256"),
                1 if values.get("access_verified", True) else 0,
                values.get("injection_status", "clean"),
            ),
        )
        return public_id

    def items_for_context_assembly(
        self, connection: sqlite3.Connection, context_assembly_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM chat_context_items WHERE context_assembly_id=? ORDER BY rank",
            (context_assembly_id,),
        ).fetchall()

    def create_orchestration_run(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO chat_orchestration_runs(public_id,session_id,request_turn_id,
            memory_retrieval_run_id,rag_retrieval_run_id,context_assembly_id,status,
            language_decision,runtime_milliseconds) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["session_id"],
                values["request_turn_id"],
                values.get("memory_retrieval_run_id"),
                values.get("rag_retrieval_run_id"),
                values.get("context_assembly_id"),
                values["status"],
                values.get("language_decision", "unknown"),
                values.get("runtime_milliseconds", 0),
            ),
        )
        return public_id

    def orchestration_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM chat_orchestration_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("orchestration run not found")
        return row

    def record_grounded_response(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO chat_grounded_responses(public_id,orchestration_run_id,
            response_turn_id,answer_status,answer_checksum_sha256,answer_language,
            memory_used,stop_reason,runtime_milliseconds,role_token_leakage,prompt_leakage,
            unicode_valid) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["orchestration_run_id"],
                values.get("response_turn_id"),
                values["answer_status"],
                values.get("answer_checksum_sha256"),
                values.get("answer_language", "unknown"),
                1 if values.get("memory_used") else 0,
                values.get("stop_reason"),
                values.get("runtime_milliseconds", 0),
                1 if values.get("role_token_leakage") else 0,
                1 if values.get("prompt_leakage") else 0,
                1 if values.get("unicode_valid", True) else 0,
            ),
        )
        return public_id

    def grounded_response(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM chat_grounded_responses WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("grounded response not found")
        return row

    def response_for_orchestration_run(
        self, connection: sqlite3.Connection, orchestration_run_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM chat_grounded_responses WHERE orchestration_run_id=?",
            (orchestration_run_id,),
        ).fetchone()

    def record_citation(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO chat_response_citations(public_id,grounded_response_id,
            citation_label,evidence_type,rag_chunk_id,memory_item_id,rank,
            content_checksum_sha256,validation_status) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["grounded_response_id"],
                values["citation_label"],
                values["evidence_type"],
                values.get("rag_chunk_id"),
                values.get("memory_item_id"),
                values.get("rank"),
                values.get("content_checksum_sha256"),
                values["validation_status"],
            ),
        )
        return public_id

    def citations_for_response(
        self, connection: sqlite3.Connection, grounded_response_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM chat_response_citations WHERE grounded_response_id=? ORDER BY rank",
            (grounded_response_id,),
        ).fetchall()

    def record_orchestration_issue(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO chat_orchestration_issues(public_id,orchestration_run_id,issue_code,
            severity,message,details_json) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["orchestration_run_id"],
                values["issue_code"],
                values.get("severity", "warning"),
                values.get("message", ""),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def issues_for_orchestration_run(
        self, connection: sqlite3.Connection, orchestration_run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM chat_orchestration_issues WHERE orchestration_run_id=? ORDER BY id",
            (orchestration_run_id,),
        ).fetchall()

    # --- evaluation -----------------------------------------------------

    def create_evaluation_suite(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_evaluation_suites(public_id,name,version,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (public_id, values["name"], values["version"], values["created_by_admin_public_id"]),
        )
        return public_id

    def evaluation_suite(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM memory_evaluation_suites WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("evaluation suite not found")
        return row

    def list_evaluation_suites(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_evaluation_suites ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def record_fixture(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_evaluation_fixtures(public_id,evaluation_suite_id,
            participant_scope_key,session_mode,query,query_language,
            expected_retrieved_memory_ids_json,expected_excluded_memory_ids_json,
            expected_language,expected_rag_use,expected_no_memory_behavior,
            expected_response_status,injection_test,severity,fixture_checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["evaluation_suite_id"],
                values["participant_scope_key"],
                values["session_mode"],
                values["query"],
                values.get("query_language", "unknown"),
                values.get("expected_retrieved_memory_ids_json", "[]"),
                values.get("expected_excluded_memory_ids_json", "[]"),
                values.get("expected_language"),
                1 if values.get("expected_rag_use") else 0,
                1 if values.get("expected_no_memory_behavior") else 0,
                values.get("expected_response_status"),
                1 if values.get("injection_test") else 0,
                values.get("severity", "info"),
                values["fixture_checksum_sha256"],
            ),
        )
        return public_id

    def fixtures_for_suite(
        self, connection: sqlite3.Connection, evaluation_suite_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_evaluation_fixtures WHERE evaluation_suite_id=? ORDER BY id",
            (evaluation_suite_id,),
        ).fetchall()

    def create_evaluation_run(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_evaluation_runs(public_id,evaluation_suite_id,
            retrieval_profile_id,total_fixtures,created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["evaluation_suite_id"],
                values.get("retrieval_profile_id"),
                values.get("total_fixtures", 0),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def evaluation_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM memory_evaluation_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("evaluation run not found")
        return row

    def update_evaluation_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE memory_evaluation_runs SET {columns} WHERE id=?", (*fields.values(), run_id)
        )

    def record_metric(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO memory_evaluation_metrics(public_id,evaluation_run_id,metric_scope,
            metric_name,metric_value,sample_size,details_json) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["evaluation_run_id"],
                values["metric_scope"],
                values["metric_name"],
                values.get("metric_value"),
                values.get("sample_size", 0),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def metrics_for_run(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM memory_evaluation_metrics WHERE evaluation_run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()

    # --- manifest -----------------------------------------------------

    def record_manifest(
        self, connection: sqlite3.Connection, policy_id: int, manifest_json: str, checksum: str
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO conversation_memory_manifests(public_id,memory_policy_id,
            manifest_json,manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (public_id, policy_id, manifest_json, checksum),
        )
        return public_id

    def latest_manifest(self, connection: sqlite3.Connection, policy_id: int) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM conversation_memory_manifests WHERE memory_policy_id=? "
            "ORDER BY id DESC LIMIT 1",
            (policy_id,),
        ).fetchone()
