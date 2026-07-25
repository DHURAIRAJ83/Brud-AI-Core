"""Phase 17 conversation memory policies, sessions, turns, and summaries.

Default session mode is ``private_no_persist``: no raw turn content, no
summary, and no long-term memory are ever persisted for that mode --
only bounded checksums/token counts, matching the same "no raw content"
discipline every prior phase has followed for prompts/answers.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.conversation_memory import (
    ConversationMemoryRepository,
    public_row,
)
from backend.models.conversation_memory import (
    MemoryPolicyCreate,
    MemoryPolicyPatch,
    SessionCreate,
    SummaryCreate,
)
from core_model.conversation import SESSION_MODES
from core_model.conversation.language_continuity import decide_language
from core_model.conversation.session_policy import (
    resolve_effective_capabilities,
    validate_policy_limits,
)
from core_model.conversation.summary_builder import deterministic_extract, estimate_token_count
from core_model.conversation.summary_validation import validate_summary
from core_model.conversation.turn_validation import (
    content_checksum,
    detect_duplicate_retry,
    validate_turn,
)


class ConversationSessionService:
    def __init__(self, repository: ConversationMemoryRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- policies -----------------------------------------------------

    def create_policy(self, payload: MemoryPolicyCreate, admin_id: str) -> dict[str, Any]:
        errors = validate_policy_limits(
            {
                "default_session_mode": payload.default_session_mode,
                "maximum_session_turns": payload.maximum_session_turns,
                "maximum_session_age_seconds": payload.maximum_session_age_seconds,
                "maximum_short_term_tokens": payload.maximum_short_term_tokens,
                "maximum_summary_tokens": payload.maximum_summary_tokens,
                "maximum_memory_items": payload.maximum_memory_items,
                "default_memory_ttl_seconds": payload.default_memory_ttl_seconds,
                "allowed_memory_categories": payload.allowed_memory_categories,
            }
        )
        if errors:
            raise ValidationError("; ".join(errors))
        with self.repository.transaction() as connection:
            public_id = self.repository.create_policy(
                connection,
                {
                    "name": payload.name,
                    "description": payload.description,
                    "default_session_mode": payload.default_session_mode,
                    "allow_short_term_context": payload.allow_short_term_context,
                    "allow_session_summary": payload.allow_session_summary,
                    "allow_long_term_memory": payload.allow_long_term_memory,
                    "require_explicit_consent": payload.require_explicit_consent,
                    "maximum_session_turns": payload.maximum_session_turns,
                    "maximum_session_age_seconds": payload.maximum_session_age_seconds,
                    "maximum_short_term_tokens": payload.maximum_short_term_tokens,
                    "maximum_summary_tokens": payload.maximum_summary_tokens,
                    "maximum_memory_items": payload.maximum_memory_items,
                    "default_memory_ttl_seconds": payload.default_memory_ttl_seconds,
                    "allowed_memory_categories_json": dumps_json(payload.allowed_memory_categories),
                    "forbidden_content_categories_json": dumps_json(
                        payload.forbidden_content_categories
                    ),
                    "retrieval_configuration_json": dumps_json(payload.retrieval_configuration),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "memory_policy_created", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    def list_policies(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_policies(connection)]}

    def get_policy(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.policy(connection, public_id))

    def patch_policy(
        self, public_id: str, payload: MemoryPolicyPatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, public_id)
            if policy["lifecycle_status"] == "archived":
                raise ValidationError("an archived policy cannot be modified")
            fields: dict[str, Any] = {}
            if payload.description is not None:
                fields["description"] = payload.description
            if payload.allow_long_term_memory is not None:
                fields["allow_long_term_memory"] = 1 if payload.allow_long_term_memory else 0
            if payload.maximum_session_turns is not None:
                fields["maximum_session_turns"] = payload.maximum_session_turns
            if payload.allowed_memory_categories is not None:
                fields["allowed_memory_categories_json"] = dumps_json(
                    payload.allowed_memory_categories
                )
            if payload.lifecycle_status is not None:
                fields["lifecycle_status"] = payload.lifecycle_status
            self.repository.update_policy(connection, policy["id"], fields)
            self._audit(connection, "memory_policy_updated", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    def validate_policy(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, public_id)
            errors = validate_policy_limits(
                {
                    "default_session_mode": policy["default_session_mode"],
                    "maximum_session_turns": policy["maximum_session_turns"],
                    "maximum_session_age_seconds": policy["maximum_session_age_seconds"],
                    "maximum_short_term_tokens": policy["maximum_short_term_tokens"],
                    "maximum_summary_tokens": policy["maximum_summary_tokens"],
                    "maximum_memory_items": policy["maximum_memory_items"],
                    "default_memory_ttl_seconds": policy["default_memory_ttl_seconds"],
                    "allowed_memory_categories": [],
                }
            )
            if errors:
                raise ValidationError("; ".join(errors))
            self.repository.update_policy(
                connection, policy["id"], {"lifecycle_status": "validated"}
            )
            self._audit(connection, "memory_policy_validated", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    def activate_policy(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, public_id)
            if policy["lifecycle_status"] != "validated":
                raise ValidationError("policy must be validated before activation")
            self.repository.update_policy(connection, policy["id"], {"lifecycle_status": "active"})
            self._audit(connection, "memory_policy_activated", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    # --- sessions -----------------------------------------------------

    def create_session(self, payload: SessionCreate, admin_id: str) -> dict[str, Any]:
        if payload.session_mode not in SESSION_MODES:
            raise ValidationError(f"session_mode must be one of {SESSION_MODES}")
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, payload.memory_policy_public_id)
            if policy["lifecycle_status"] != "active":
                raise ValidationError("memory policy must be active to start a session")

            model_assignment_id = None
            if payload.model_assignment_public_id:
                row = connection.execute(
                    "SELECT id FROM inference_model_assignments WHERE public_id=?",
                    (payload.model_assignment_public_id,),
                ).fetchone()
                model_assignment_id = row["id"] if row else None
            rag_profile_id = None
            if payload.rag_retrieval_profile_public_id:
                row = connection.execute(
                    "SELECT id FROM rag_retrieval_profiles WHERE public_id=?",
                    (payload.rag_retrieval_profile_public_id,),
                ).fetchone()
                rag_profile_id = row["id"] if row else None

            public_id = self.repository.create_session(
                connection,
                {
                    "session_mode": payload.session_mode,
                    "memory_policy_id": policy["id"],
                    "participant_scope_key": payload.participant_scope_key,
                    "language_preference": payload.language_preference,
                    "model_assignment_id": model_assignment_id,
                    "rag_retrieval_profile_id": rag_profile_id,
                    "created_by_admin_public_id": admin_id,
                    "status": "active",
                },
            )
            self.repository.add_participant(
                connection,
                {
                    "session_id": self.repository.session(connection, public_id)["id"],
                    "participant_type": payload.participant_type,
                    "participant_scope_key": payload.participant_scope_key,
                },
            )
            self._audit(connection, "session_created", admin_id, public_id)
            return public_row(self.repository.session(connection, public_id))

    def list_sessions(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_sessions(connection)]}

    def get_session(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.session(connection, public_id))

    def pause_session(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition(
            public_id, admin_id, "paused", "session_paused", from_statuses={"active"}
        )

    def resume_session(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition(
            public_id, admin_id, "active", "session_resumed", from_statuses={"paused"}
        )

    def close_session(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, public_id)
            if session["status"] in {"closed", "expired", "archived"}:
                raise ValidationError("session is already closed")
            self.repository.update_session(
                connection, session["id"], {"status": "closed", "closed_at": _now_sql()}
            )
            if session["session_mode"] == "private_no_persist":
                self._purge_private_session_content(connection, session["id"])
            self._audit(connection, "session_closed", admin_id, public_id)
            return public_row(self.repository.session(connection, public_id))

    def expire_session(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, public_id)
            if session["status"] in {"closed", "expired", "archived"}:
                raise ValidationError("session is already terminal")
            self.repository.update_session(connection, session["id"], {"status": "expired"})
            if session["session_mode"] == "private_no_persist":
                self._purge_private_session_content(connection, session["id"])
            self._audit(connection, "session_expired", admin_id, public_id)
            return public_row(self.repository.session(connection, public_id))

    def _transition(
        self, public_id: str, admin_id: str, new_status: str, event: str, *, from_statuses: set[str]
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, public_id)
            if session["status"] not in from_statuses:
                raise ValidationError(f"session must be {from_statuses} for this transition")
            self.repository.update_session(connection, session["id"], {"status": new_status})
            self._audit(connection, event, admin_id, public_id)
            return public_row(self.repository.session(connection, public_id))

    def _purge_private_session_content(self, connection, session_id: int) -> None:
        """private_no_persist sessions never write raw content in the first
        place (see create_turn's stored_content=None branch); this clears
        any residual nullable fields defensively so no raw text can ever
        remain associated with a closed/expired private session."""

        connection.execute(
            "UPDATE conversation_turns SET stored_content=NULL WHERE session_id=?", (session_id,)
        )

    # --- turns -----------------------------------------------------

    def list_turns(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, session_public_id)
            rows = self.repository.turns_for_session(connection, session["id"])
            return {"items": [public_row(row) for row in rows]}

    def create_turn(
        self,
        session_public_id: str,
        *,
        role: str,
        content: str,
        admin_id: str,
        language_category: str = "unknown",
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, session_public_id)
            if session["status"] != "active":
                raise ValidationError("session must be active to accept a new turn")
            policy = self.repository.policy(connection, session["memory_policy_public_id"])

            latest = self.repository.latest_turn(connection, session["id"])
            previous_role = latest["role"] if latest else None
            previous_checksum = latest["content_checksum_sha256"] if latest else None

            if role == "user" and detect_duplicate_retry(
                role=role,
                content=content,
                previous_turn_role=previous_role,
                previous_turn_checksum=previous_checksum,
            ):
                return public_row(latest)

            estimated_tokens = estimate_token_count(content)
            validation = validate_turn(
                role=role,
                content=content,
                previous_role=previous_role,
                session_status=session["status"],
                maximum_characters=self.settings.memory_max_turn_characters,
                maximum_tokens=policy["maximum_short_term_tokens"],
                estimated_token_count=estimated_tokens,
            )
            if not validation["valid"]:
                raise ValidationError(f"turn validation failed: {validation['issues']}")
            if session["turn_count"] >= policy["maximum_session_turns"]:
                raise ValidationError("session has reached its maximum turn count")

            capabilities = resolve_effective_capabilities(session["session_mode"], dict(policy))
            stored_content = content if capabilities["persist_turns"] else None

            public_id = self.repository.record_turn(
                connection,
                {
                    "session_id": session["id"],
                    "sequence_number": session["turn_count"],
                    "role": role,
                    "language_category": language_category,
                    "content_checksum_sha256": content_checksum(content),
                    "stored_content": stored_content,
                    "token_count": estimated_tokens,
                },
            )
            self.repository.update_session(
                connection,
                session["id"],
                {"turn_count": session["turn_count"] + 1, "last_activity_at": _now_sql()},
            )
            return public_row(self.repository.turn(connection, public_id))

    # --- summaries -----------------------------------------------------

    def create_summary(
        self, session_public_id: str, payload: SummaryCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, session_public_id)
            policy = self.repository.policy(connection, session["memory_policy_public_id"])
            capabilities = resolve_effective_capabilities(session["session_mode"], dict(policy))
            if not capabilities["allow_summary"]:
                raise ValidationError("this session mode/policy does not allow summaries")

            turn_rows = self.repository.turns_for_session(connection, session["id"])
            turns = [
                {"role": row["role"], "content": row["stored_content"] or ""}
                for row in turn_rows
                if row["stored_content"] is not None
            ]
            if not turns:
                raise ValidationError("no persisted turns are available to summarize")

            extracted = deterministic_extract(turns)
            language_info = decide_language(
                current_request_text=turns[-1]["content"],
                explicit_language_request=None,
                confirmed_language_preference=session["language_preference"],
                recent_user_turn_texts=[t["content"] for t in turns if t["role"] == "user"],
            )
            validation = validate_summary(
                summary_text=extracted["summary_text"],
                source_turns=turns,
                maximum_tokens=policy["maximum_summary_tokens"],
                estimated_token_count=extracted["token_count"],
                language_category=language_info["language_category"],
                expected_language_category=None,
            )

            summary_public_id = self.repository.create_summary(connection, session["id"])
            summary = self.repository.summary(connection, summary_public_id)
            version_public_id = self.repository.create_summary_version(
                connection,
                {
                    "summary_id": summary["id"],
                    "version_number": 1,
                    "source_turn_start_sequence": turn_rows[0]["sequence_number"],
                    "source_turn_end_sequence": turn_rows[-1]["sequence_number"],
                    "summary_language": language_info["language_category"],
                    "summary_text_checksum_sha256": hashlib.sha256(
                        extracted["summary_text"].encode("utf-8")
                    ).hexdigest(),
                    "summary_text": extracted["summary_text"],
                    "summary_token_count": extracted["token_count"],
                    "generation_method": payload.generation_method,
                    "validation_status": "validated" if validation["valid"] else "rejected",
                },
            )
            self.repository.update_summary(
                connection,
                summary["id"],
                {
                    "current_version_id": self.repository.summary_version(
                        connection, version_public_id
                    )["id"],
                    "status": "validated" if validation["valid"] else "rejected",
                },
            )
            self._audit(
                connection, "summary_created", admin_id, summary_public_id,
                valid=validation["valid"],
            )
            return public_row(self.repository.summary(connection, summary_public_id))

    def list_summaries(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session = self.repository.session(connection, session_public_id)
            rows = self.repository.summaries_for_session(connection, session["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_summary(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.summary(connection, public_id))

    def validate_summary_endpoint(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            summary = self.repository.summary(connection, public_id)
            self.repository.update_summary(connection, summary["id"], {"status": "validated"})
            self._audit(connection, "summary_validated", admin_id, public_id)
            return public_row(self.repository.summary(connection, public_id))

    def accept_summary(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            summary = self.repository.summary(connection, public_id)
            if summary["status"] != "validated":
                raise ValidationError("summary must be validated before acceptance")
            self.repository.update_summary(connection, summary["id"], {"status": "accepted"})
            self._audit(connection, "summary_accepted", admin_id, public_id)
            return public_row(self.repository.summary(connection, public_id))

    def reject_summary(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            summary = self.repository.summary(connection, public_id)
            self.repository.update_summary(connection, summary["id"], {"status": "rejected"})
            self._audit(connection, "summary_rejected", admin_id, public_id)
            return public_row(self.repository.summary(connection, public_id))

    # --- audit -----------------------------------------------------

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
                "conversation_memory", resource_id, "success", dumps_json(metadata),
            ),
        )


def _now_sql() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
