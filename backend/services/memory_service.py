"""Phase 17 memory consent, memory items/versions/events, memory
retrieval profiles, and memory retrieval.

Long-term memory is purpose-bound and consent-aware: a memory item can
become ``active`` only when consent is active, its category/purpose are
allowed, its safety scan passes, and (for assistant-proposed or
assistant-inferred content) it has been explicitly confirmed. Deletion,
revocation, and expiry all immediately exclude a memory item from
future retrieval -- there is no separate cache to invalidate because
every retrieval re-reads live status from the database each time.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.conversation_memory import (
    ConversationMemoryRepository,
    public_row,
)
from backend.models.conversation_memory import (
    ConsentCreate,
    MemoryItemCorrect,
    MemoryItemCreate,
    MemoryRetrieveRequest,
    RetrievalProfileCreate,
    RetrievalProfilePatch,
)
from core_model.conversation.memory_deduplication import assess_conflict
from core_model.conversation.memory_normalization import normalize_memory_value
from core_model.conversation.memory_policy import (
    category_is_allowed,
    may_become_active,
    purpose_is_bounded,
)
from core_model.conversation.memory_ranking import (
    MemoryRankingWeights,
    compute_combined_score,
    rank_with_tie_break,
)
from core_model.conversation.memory_retrieval import MemoryRetrievalFilters, apply_access_filters
from core_model.conversation.memory_safety import assess_memory_safety
from core_model.rag.embedding import compute_embedding, pack_vector, unpack_vector
from core_model.rag.vector_index import score_vectors

MEMORY_EMBEDDING_DIMENSIONS = 64
MEMORY_EMBEDDING_MODEL_NAME = "memory_local_embedding"
MEMORY_EMBEDDING_MODEL_VERSION = "v1"


class MemoryService:
    def __init__(self, repository: ConversationMemoryRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- consent -----------------------------------------------------

    def create_consent(self, payload: ConsentCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, payload.memory_policy_public_id)
            public_id = self.repository.create_consent(
                connection,
                {
                    "participant_scope_key": payload.participant_scope_key,
                    "memory_policy_id": policy["id"],
                    "purpose": payload.purpose,
                    "allowed_categories_json": dumps_json(payload.allowed_categories),
                    "prohibited_categories_json": dumps_json(payload.prohibited_categories),
                    "status": "active",
                    "granted_at": _now_sql(),
                    "expires_at": payload.expires_at,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "consent_granted", admin_id, public_id)
            return public_row(self.repository.consent(connection, public_id))

    def list_consents(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_consents(connection)]}

    def get_consent(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.consent(connection, public_id))

    def revoke_consent(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            consent = self.repository.consent(connection, public_id)
            self.repository.update_consent(
                connection, consent["id"], {"status": "revoked", "revoked_at": _now_sql()}
            )
            self._expire_memory_for_consent(connection, consent["id"])
            self._audit(connection, "consent_revoked", admin_id, public_id)
            return public_row(self.repository.consent(connection, public_id))

    def expire_consent(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            consent = self.repository.consent(connection, public_id)
            self.repository.update_consent(connection, consent["id"], {"status": "expired"})
            self._expire_memory_for_consent(connection, consent["id"])
            self._audit(connection, "consent_expired", admin_id, public_id)
            return public_row(self.repository.consent(connection, public_id))

    def _expire_memory_for_consent(self, connection, consent_id: int) -> None:
        rows = connection.execute(
            "SELECT id, public_id FROM memory_items WHERE consent_id=? AND status='active'",
            (consent_id,),
        ).fetchall()
        for row in rows:
            self.repository.update_memory_item(connection, row["id"], {"status": "revoked"})
            self.repository.record_memory_item_event(
                connection,
                {"memory_item_id": row["id"], "event_type": "revoked_via_consent_change"},
            )

    # --- memory items -----------------------------------------------------

    def propose_memory(self, payload: MemoryItemCreate, admin_id: str) -> dict[str, Any]:
        allowed, category_reason = category_is_allowed(
            payload.category, list(self.settings.memory_allowed_categories_list)
        )
        if not allowed:
            raise ValidationError(f"memory category rejected: {category_reason}")
        purpose_allowed, purpose_reason = purpose_is_bounded(payload.purpose)
        if not purpose_allowed:
            raise ValidationError(f"memory purpose rejected: {purpose_reason}")

        safety = assess_memory_safety(payload.display_value)
        if safety["status"] == "blocked" and self.settings.memory_block_sensitive_content:
            categories = safety["matched_categories"]
            raise ValidationError(f"memory content blocked by safety scan: {categories}")

        normalized = normalize_memory_value(payload.category, payload.display_value)

        with self.repository.transaction() as connection:
            consent = None
            consent_id = None
            if payload.consent_public_id:
                consent_row = self.repository.consent(connection, payload.consent_public_id)
                consent_id = consent_row["id"]
                consent = {
                    "status": consent_row["status"],
                    "allowed_categories": _loads(consent_row["allowed_categories_json"]),
                    "prohibited_categories": _loads(consent_row["prohibited_categories_json"]),
                }

            existing_active = [
                {
                    "category": row["category"], "purpose": row["purpose"],
                    "normalized_value": self._current_normalized_value(connection, row),
                    "public_id": row["public_id"], "created_at": row["created_at"],
                    "confidence_type": row["confidence_type"],
                }
                for row in self.repository.active_memory_items_for_participant(
                    connection, payload.participant_scope_key
                )
            ]
            conflict = assess_conflict(
                proposed_normalized_value=normalized["normalized_value"],
                existing_active_items=existing_active,
                category=payload.category,
                purpose=payload.purpose,
            )

            may_activate, activation_reason = may_become_active(
                creation_source=payload.creation_source,
                confidence_type=payload.confidence_type,
                consent=consent,
                category=payload.category,
                safety_status=safety["status"],
                is_duplicate=conflict["status"] == "duplicate",
                has_unconfirmed_conflict=conflict["status"] == "conflict_requires_confirmation",
            )
            initial_status = "active" if may_activate else (
                "awaiting_confirmation"
                if activation_reason == "requires_confirmation"
                else "proposed"
            )
            if activation_reason == "consent_required":
                initial_status = "proposed"

            source_session_id = None
            if payload.source_session_public_id:
                source_session_id = self.repository.session(
                    connection, payload.source_session_public_id
                )["id"]
            source_turn_id = None
            if payload.source_turn_public_id:
                source_turn_row = self.repository.turn(connection, payload.source_turn_public_id)
                source_turn_id = source_turn_row["id"]

            item_public_id = self.repository.create_memory_item(
                connection,
                {
                    "participant_scope_key": payload.participant_scope_key,
                    "category": payload.category,
                    "purpose": payload.purpose,
                    "creation_source": payload.creation_source,
                    "confidence_type": payload.confidence_type,
                    "consent_id": consent_id,
                    "source_session_id": source_session_id,
                    "source_turn_id": source_turn_id,
                    "status": initial_status,
                    "valid_from": _now_sql(),
                    "expires_at": payload.expires_at,
                },
            )
            item = self.repository.memory_item(connection, item_public_id)
            version_public_id = self._record_version(
                connection, item["id"], normalized,
                change_reason="initial_creation", created_by=admin_id,
            )
            self.repository.update_memory_item(
                connection,
                item["id"],
                {
                    "current_version_id": self.repository.memory_item_version(
                        connection, version_public_id
                    )["id"]
                },
            )
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": item["id"], "event_type": "proposed",
                    "created_by_admin_public_id": admin_id,
                    "details_json": dumps_json(
                        {"conflict_status": conflict["status"], "safety_status": safety["status"]}
                    ),
                },
            )
            self._audit(
                connection, "memory_proposed", admin_id, item_public_id,
                status=initial_status, conflict=conflict["status"],
            )
            return public_row(self.repository.memory_item(connection, item_public_id))

    def _record_version(
        self, connection, memory_item_id: int, normalized: dict[str, str], *,
        change_reason: str, created_by: str,
    ) -> str:
        existing_versions = self.repository.versions_for_memory_item(connection, memory_item_id)
        version_number = len(existing_versions) + 1
        checksum = hashlib.sha256(normalized["normalized_value"].encode("utf-8")).hexdigest()
        version_public_id = self.repository.create_memory_item_version(
            connection,
            {
                "memory_item_id": memory_item_id,
                "version_number": version_number,
                "normalized_value": normalized["normalized_value"],
                "display_value": normalized["display_value"],
                "change_reason": change_reason,
                "checksum_sha256": checksum,
                "created_by": created_by,
            },
        )
        version_id = self.repository.memory_item_version(connection, version_public_id)["id"]
        self._store_embedding(connection, version_id, normalized["display_value"])
        return version_public_id

    def _ensure_embedding_model_id(self, connection) -> int:
        """Reuses Phase 16's rag_embedding_models table and
        local_custom_embedding provider -- never a second embedding
        implementation."""

        row = connection.execute(
            "SELECT id FROM rag_embedding_models WHERE name=? AND version=?",
            (MEMORY_EMBEDDING_MODEL_NAME, MEMORY_EMBEDDING_MODEL_VERSION),
        ).fetchone()
        if row:
            return row["id"]
        model_public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_embedding_models(public_id,name,version,provider_type,
            dimensions,maximum_input_tokens,lifecycle_status)
            VALUES (?,?,?,?,?,?,?)""",
            (
                model_public_id, MEMORY_EMBEDDING_MODEL_NAME, MEMORY_EMBEDDING_MODEL_VERSION,
                "local_custom_embedding", MEMORY_EMBEDDING_DIMENSIONS, 512, "active",
            ),
        )
        return connection.execute(
            "SELECT id FROM rag_embedding_models WHERE public_id=?", (model_public_id,)
        ).fetchone()["id"]

    def _store_embedding(self, connection, version_id: int, text: str) -> None:
        model_id = self._ensure_embedding_model_id(connection)
        result = compute_embedding(
            text, provider_type="local_custom_embedding", dimensions=MEMORY_EMBEDDING_DIMENSIONS
        )
        vector_blob = pack_vector(result["vector"])
        self.repository.record_memory_embedding(
            connection,
            {
                "memory_item_version_id": version_id,
                "embedding_model_id": model_id,
                "content_checksum_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "dimensions": MEMORY_EMBEDDING_DIMENSIONS,
                "vector_blob": vector_blob,
                "vector_checksum_sha256": hashlib.sha256(vector_blob).hexdigest(),
            },
        )

    def _current_normalized_value(self, connection, item_row) -> str:
        if not item_row["current_version_id"]:
            return ""
        row = connection.execute(
            "SELECT normalized_value FROM memory_item_versions WHERE id=?",
            (item_row["current_version_id"],),
        ).fetchone()
        return row["normalized_value"] if row else ""

    def list_memory_items(self, participant_scope_key: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory_items(
                connection, participant_scope_key=participant_scope_key
            )
            return {"items": [public_row(row) for row in rows]}

    def get_memory_item(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.memory_item(connection, public_id))

    def confirm_memory(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, public_id)
            if item["status"] not in {"proposed", "awaiting_confirmation"}:
                raise ValidationError("only proposed/awaiting-confirmation memory can be confirmed")
            self.repository.update_memory_item(connection, item["id"], {"status": "active"})
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": item["id"], "event_type": "confirmed",
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "memory_confirmed", admin_id, public_id)
            return public_row(self.repository.memory_item(connection, public_id))

    def reject_memory(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, public_id)
            self.repository.update_memory_item(connection, item["id"], {"status": "rejected"})
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": item["id"], "event_type": "rejected",
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "memory_rejected", admin_id, public_id)
            return public_row(self.repository.memory_item(connection, public_id))

    def correct_memory(
        self, public_id: str, payload: MemoryItemCorrect, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, public_id)
            if item["status"] != "active":
                raise ValidationError("only active memory can be corrected")
            safety = assess_memory_safety(payload.display_value)
            if safety["status"] == "blocked" and self.settings.memory_block_sensitive_content:
                raise ValidationError("corrected memory content blocked by safety scan")
            normalized = normalize_memory_value(item["category"], payload.display_value)
            version_public_id = self._record_version(
                connection, item["id"], normalized,
                change_reason=payload.change_reason, created_by=admin_id,
            )
            self.repository.update_memory_item(
                connection,
                item["id"],
                {
                    "current_version_id": self.repository.memory_item_version(
                        connection, version_public_id
                    )["id"]
                },
            )
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": item["id"], "event_type": "corrected",
                    "created_by_admin_public_id": admin_id,
                    "details_json": dumps_json({"change_reason": payload.change_reason}),
                },
            )
            self._audit(connection, "memory_corrected", admin_id, public_id)
            return public_row(self.repository.memory_item(connection, public_id))

    def expire_memory(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, public_id)
            self.repository.update_memory_item(connection, item["id"], {"status": "expired"})
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": item["id"], "event_type": "expired",
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "memory_expired", admin_id, public_id)
            return public_row(self.repository.memory_item(connection, public_id))

    def delete_memory(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, public_id)
            self.repository.update_memory_item(connection, item["id"], {"status": "deleted"})
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": item["id"], "event_type": "deleted",
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "memory_deleted", admin_id, public_id)
            return public_row(self.repository.memory_item(connection, public_id))

    def delete_all_for_purpose(
        self, participant_scope_key: str, purpose: str, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT id, public_id FROM memory_items WHERE participant_scope_key=? "
                "AND purpose=? AND status NOT IN ('deleted','rejected')",
                (participant_scope_key, purpose),
            ).fetchall()
            for row in rows:
                self.repository.update_memory_item(connection, row["id"], {"status": "deleted"})
                self.repository.record_memory_item_event(
                    connection,
                    {
                        "memory_item_id": row["id"], "event_type": "deleted_forget_purpose",
                        "created_by_admin_public_id": admin_id,
                    },
                )
            self._audit(
                connection, "memory_forget_purpose", admin_id, participant_scope_key,
                purpose=purpose, count=len(rows),
            )
            return {"deleted_count": len(rows)}

    def get_versions(self, memory_item_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, memory_item_public_id)
            rows = self.repository.versions_for_memory_item(connection, item["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_events(self, memory_item_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, memory_item_public_id)
            rows = self.repository.events_for_memory_item(connection, item["id"])
            return {"items": [public_row(row) for row in rows]}

    # --- retrieval profiles -----------------------------------------------------

    def create_profile(self, payload: RetrievalProfileCreate, admin_id: str) -> dict[str, Any]:
        if abs(payload.keyword_weight + payload.vector_weight - 1.0) > 0.01:
            raise ValidationError("keyword_weight and vector_weight must sum to 1.0")
        with self.repository.transaction() as connection:
            public_id = self.repository.create_retrieval_profile(
                connection,
                {
                    "name": payload.name,
                    "allowed_categories_json": dumps_json(payload.allowed_categories),
                    "allowed_purposes_json": dumps_json(payload.allowed_purposes),
                    "keyword_weight": payload.keyword_weight,
                    "vector_weight": payload.vector_weight,
                    "recency_weight": payload.recency_weight,
                    "user_confirmed_boost": payload.user_confirmed_boost,
                    "maximum_results": payload.maximum_results,
                    "minimum_score": payload.minimum_score,
                    "maximum_memory_tokens": payload.maximum_memory_tokens,
                    "conflict_policy": payload.conflict_policy,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "memory_retrieval_profile_created", admin_id, public_id)
            return public_row(self.repository.retrieval_profile(connection, public_id))

    def list_profiles(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_retrieval_profiles(connection)
            return {"items": [public_row(row) for row in rows]}

    def get_profile(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.retrieval_profile(connection, public_id))

    def patch_profile(
        self, public_id: str, payload: RetrievalProfilePatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(connection, public_id)
            fields: dict[str, Any] = {}
            patchable = (
                "keyword_weight", "vector_weight", "maximum_results",
                "minimum_score", "conflict_policy",
            )
            for name in patchable:
                value = getattr(payload, name)
                if value is not None:
                    fields[name] = value
            self.repository.update_retrieval_profile(connection, profile["id"], fields)
            self._audit(connection, "memory_retrieval_profile_updated", admin_id, public_id)
            return public_row(self.repository.retrieval_profile(connection, public_id))

    def validate_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(connection, public_id)
            if abs(profile["keyword_weight"] + profile["vector_weight"] - 1.0) > 0.01:
                raise ValidationError("keyword_weight and vector_weight must sum to 1.0")
            self.repository.update_retrieval_profile(
                connection, profile["id"], {"status": "validated"}
            )
            self._audit(connection, "memory_retrieval_profile_validated", admin_id, public_id)
            return public_row(self.repository.retrieval_profile(connection, public_id))

    def activate_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(connection, public_id)
            if profile["status"] != "validated":
                raise ValidationError("profile must be validated before activation")
            self.repository.update_retrieval_profile(
                connection, profile["id"], {"status": "active"}
            )
            self._audit(connection, "memory_retrieval_profile_activated", admin_id, public_id)
            return public_row(self.repository.retrieval_profile(connection, public_id))

    # --- retrieval -----------------------------------------------------

    def retrieve(self, payload: MemoryRetrieveRequest, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(
                connection, payload.retrieval_profile_public_id
            )
            if profile["status"] != "active":
                raise ValidationError("retrieval profile must be active to be used")

            started = time.perf_counter()
            allowed_categories = _loads(profile["allowed_categories_json"])
            allowed_purposes = _loads(profile["allowed_purposes_json"])
            query_tokens = set(payload.query.lower().split())

            candidate_rows = self.repository.active_memory_items_for_participant(
                connection, payload.participant_scope_key
            )
            candidates = []
            for row in candidate_rows:
                normalized_value = self._current_normalized_value(connection, row)
                candidates.append(
                    {
                        "public_id": row["public_id"],
                        "participant_scope_key": row["participant_scope_key"],
                        "status": row["status"],
                        "category": row["category"],
                        "purpose": row["purpose"],
                        "confidence_type": row["confidence_type"],
                        "confirmed": row["status"] == "active",
                        "normalized_value": normalized_value,
                        "created_at": row["created_at"],
                        "current_version_id": row["current_version_id"],
                    }
                )

            filters = MemoryRetrievalFilters(
                participant_scope_key=payload.participant_scope_key,
                allowed_categories=tuple(allowed_categories),
                allowed_purposes=tuple(allowed_purposes),
                now_epoch=time.time(),
            )
            filtered = apply_access_filters(candidates, filters)

            weights = MemoryRankingWeights(
                keyword_weight=profile["keyword_weight"],
                vector_weight=profile["vector_weight"],
                recency_weight=profile["recency_weight"],
                user_confirmed_boost=profile["user_confirmed_boost"],
            )
            query_embedding = compute_embedding(
                payload.query, provider_type="local_custom_embedding",
                dimensions=MEMORY_EMBEDDING_DIMENSIONS,
            )

            scored = []
            for candidate in filtered["accepted"]:
                value_tokens = set(candidate["normalized_value"].lower().split())
                overlap = len(query_tokens & value_tokens)
                keyword_score = (
                    min(1.0, overlap / max(1, len(query_tokens))) if query_tokens else 0.0
                )
                vector_score = None
                if candidate["current_version_id"]:
                    embedding_row = connection.execute(
                        "SELECT * FROM memory_embeddings WHERE memory_item_version_id=? "
                        "ORDER BY id DESC LIMIT 1",
                        (candidate["current_version_id"],),
                    ).fetchone()
                    if embedding_row:
                        candidate_vector = unpack_vector(
                            embedding_row["vector_blob"], dimensions=embedding_row["dimensions"]
                        )
                        raw_scores = score_vectors(
                            query_embedding["vector"], [candidate_vector], distance_metric="cosine"
                        )
                        vector_score = max(0.0, raw_scores[0])
                score = compute_combined_score(
                    keyword_score=keyword_score,
                    vector_score=vector_score,
                    recency_score=None,
                    is_user_confirmed=candidate["confidence_type"] == "user_confirmed",
                    is_session_relevant=False,
                    has_conflict=False,
                    is_stale=False,
                    weights=weights,
                )
                scored.append(
                    {
                        "memory_item_public_id": candidate["public_id"],
                        "category": candidate["category"],
                        "purpose": candidate["purpose"],
                        "keyword_score": keyword_score,
                        "vector_score": vector_score,
                        "recency_score": None,
                        "combined_score": score,
                    }
                )
            ranked = rank_with_tie_break(scored)
            ranked = [
                entry for entry in ranked if entry["combined_score"] >= profile["minimum_score"]
            ]
            ranked = ranked[: profile["maximum_results"]]

            runtime_ms = int((time.perf_counter() - started) * 1000)
            run_public_id = self.repository.create_retrieval_run(
                connection,
                {
                    "retrieval_profile_id": profile["id"],
                    "participant_scope_key": payload.participant_scope_key,
                    "query_checksum_sha256": hashlib.sha256(
                        payload.query.encode("utf-8")
                    ).hexdigest(),
                    "total_candidates": len(candidates),
                    "final_result_count": len(ranked),
                    "runtime_milliseconds": runtime_ms,
                    "status": "completed" if ranked else "no_results",
                },
            )
            run = self.repository.retrieval_run(connection, run_public_id)
            for entry in ranked:
                item_row = self.repository.memory_item(connection, entry["memory_item_public_id"])
                self.repository.record_retrieval_result(
                    connection,
                    {
                        "retrieval_run_id": run["id"],
                        "rank": entry["rank"],
                        "memory_item_id": item_row["id"],
                        "keyword_score": entry["keyword_score"],
                        "vector_score": entry["vector_score"],
                        "recency_score": entry["recency_score"],
                        "combined_score": entry["combined_score"],
                    },
                )
            self._audit(
                connection, "memory_retrieval_executed", admin_id, run_public_id,
                result_count=len(ranked),
            )
            return {**public_row(run), "results": ranked, "excluded": filtered["excluded"]}

    def get_retrieval_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.retrieval_run(connection, public_id))

    def get_retrieval_results(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.retrieval_run(connection, public_id)
            rows = self.repository.results_for_retrieval_run(connection, run["id"])
            return {"items": [public_row(row) for row in rows]}

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


def _loads(value: str | None) -> list[Any]:
    if not value:
        return []
    return loads_json(value)
