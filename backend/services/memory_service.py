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
    MemoryPolicyCreate,
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
from core_model.mini_brain.intelligence.conflict_detector import (
    ConflictClassification,
    ConflictConfidence,
    ConflictKnowledgeEngine,
    ConflictMatchResult,
    DisputeRecord,
    DisputeState,
    ResolutionStrategy,
)
from core_model.mini_brain.intelligence.duplicate_detector import (
    DuplicateClassification,
    DuplicateKnowledgeEngine,
)
from core_model.mini_brain.intelligence.memory_consolidator import (
    ConsolidationGroup,
    ConsolidationResult,
    MemoryConsolidatorEngine,
)
from core_model.mini_brain.intelligence.memory_intelligence import (
    FreshnessState,
    MemoryCategory,
    MemoryIntelligenceEngine,
    MemoryIntelligenceMetadata,
)
from core_model.mini_brain.intelligence.memory_lifecycle import (
    FreshnessEvaluationResult,
    MemoryLifecycleEngine,
)
from core_model.mini_brain.intelligence.memory_recall import (
    MemoryRecallEngine,
    MemoryRecallWeights,
    RetrievalMode,
)
from core_model.mini_brain.intelligence.memory_reasoner import (
    EvidenceCluster,
    MemoryReasoningEngine,
    MemoryReasoningPacket,
    PreferenceResolution,
    ProceduralStep,
)
from core_model.mini_brain.llm_runtime.message_sanitizer import sanitize_message
from core_model.rag.embedding import compute_embedding, pack_vector, unpack_vector
from core_model.rag.vector_index import score_vectors

MEMORY_EMBEDDING_DIMENSIONS = 64
MEMORY_EMBEDDING_MODEL_NAME = "memory_local_embedding"

MEMORY_EMBEDDING_MODEL_VERSION = "v1"


class MemoryService:
    def __init__(self, repository: ConversationMemoryRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.intelligence_engine = MemoryIntelligenceEngine()

    # --- policy delegation -------------------------------------------

    def create_policy(self, payload: MemoryPolicyCreate, admin_id: str) -> dict[str, Any]:
        from backend.services.conversation_session_service import ConversationSessionService

        return ConversationSessionService(self.repository, self.settings).create_policy(payload, admin_id)

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
                    "category": row["category"],
                    "purpose": row["purpose"],
                    "participant_scope_key": payload.participant_scope_key,
                    "display_value": self._current_display_value(connection, row),
                    "normalized_value": self._current_normalized_value(connection, row),
                    "id": row["id"],
                    "public_id": row["public_id"],
                    "created_at": row["created_at"],
                    "confidence_type": row["confidence_type"],
                    "evidence_count": row["evidence_count"] if "evidence_count" in row.keys() else 1,
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

            # 1. Exact / Normalized Deduplication & Canonical Reinforcement
            if conflict["status"] == "duplicate" and conflict.get("conflicting_item_public_id"):
                canonical_public_id = conflict["conflicting_item_public_id"]
                canonical_item = self.repository.memory_item(connection, canonical_public_id)
                reinforced_meta = MemoryIntelligenceEngine.reinforce_canonical_memory(
                    canonical_item=dict(canonical_item),
                    creation_source=payload.creation_source,
                )
                self.repository.record_memory_item_event(
                    connection,
                    {
                        "memory_item_id": canonical_item["id"],
                        "event_type": "reinforced",
                        "created_by_admin_public_id": admin_id,
                        "details_json": dumps_json({
                            "evidence_count": reinforced_meta["evidence_count"],
                            "confidence_score": reinforced_meta["confidence_score"],
                            "importance_score": reinforced_meta["importance_score"],
                            "freshness_state": reinforced_meta["freshness_state"],
                        }),
                    },
                )
                self._audit(
                    connection, "memory_reinforced", admin_id, canonical_public_id,
                    evidence_count=reinforced_meta["evidence_count"],
                )
                return public_row(self.repository.memory_item(connection, canonical_public_id))

            # 2. Phase 17.4 Semantic Deduplication & Conflict Check
            dup_eval = DuplicateKnowledgeEngine.evaluate_candidate(
                candidate_text=payload.display_value,
                candidate_category=payload.category,
                candidate_purpose=payload.purpose,
                participant_scope_key=payload.participant_scope_key,
                candidate_metadata={"confidence_type": payload.confidence_type, "creation_source": payload.creation_source},
                existing_candidates=existing_active,
            )

            if dup_eval.classification == DuplicateClassification.SEMANTIC_DUPLICATE and dup_eval.canonical_item:
                canonical_public_id = dup_eval.canonical_item["public_id"]
                canonical_item = self.repository.memory_item(connection, canonical_public_id)
                reinforced_meta = MemoryIntelligenceEngine.reinforce_canonical_memory(
                    canonical_item=dict(canonical_item),
                    creation_source=payload.creation_source,
                )
                reinforce_event_detail = DuplicateKnowledgeEngine.build_semantic_reinforcement_event(
                    canonical_public_id=canonical_public_id,
                    candidate_text=payload.display_value,
                    similarity_score=dup_eval.similarity_score,
                    evidence_delta=dup_eval.evidence_count_delta,
                    new_total_evidence=reinforced_meta["evidence_count"],
                    admin_id=admin_id,
                )
                self.repository.record_memory_item_event(
                    connection,
                    {
                        "memory_item_id": canonical_item["id"],
                        "event_type": "SEMANTIC_REINFORCED",
                        "created_by_admin_public_id": admin_id,
                        "details_json": dumps_json(reinforce_event_detail),
                    },
                )
                self._audit(
                    connection, "memory_semantic_reinforced", admin_id, canonical_public_id,
                    similarity_score=dup_eval.similarity_score, evidence_count=reinforced_meta["evidence_count"],
                )
                return public_row(self.repository.memory_item(connection, canonical_public_id))

            # 3. Phase 17.5 Conflict Knowledge Detection
            conf_eval = ConflictKnowledgeEngine.evaluate_conflict(
                candidate_text=payload.display_value,
                candidate_category=payload.category,
                candidate_purpose=payload.purpose,
                participant_scope_key=payload.participant_scope_key,
                existing_candidates=existing_active,
            )

            has_conflict_flag = (
                dup_eval.classification == DuplicateClassification.POSSIBLE_CONFLICT
                or conf_eval.has_conflict
            )
            if has_conflict_flag:
                conflict["status"] = "conflict_requires_confirmation"

            may_activate, activation_reason = may_become_active(
                creation_source=payload.creation_source,
                confidence_type=payload.confidence_type,
                consent=consent,
                category=payload.category,
                safety_status=safety["status"],
                is_duplicate=conflict["status"] == "duplicate",
                has_unconfirmed_conflict=has_conflict_flag,
            )
            initial_status = "active" if may_activate else (
                "awaiting_confirmation"
                if activation_reason == "requires_confirmation"
                else "proposed"
            )
            if activation_reason == "consent_required":
                initial_status = "proposed"

            # Compute initial Intelligence 2.0 metadata
            try:
                mem_cat = MemoryIntelligenceEngine.resolve_category(payload.category)
            except Exception:
                mem_cat = MemoryCategory.SEMANTIC
            initial_importance = MemoryIntelligenceEngine.compute_importance(
                category=mem_cat,
                access_count=0,
                is_admin_confirmed=initial_status == "active",
            )
            initial_confidence = MemoryIntelligenceEngine.compute_confidence(
                creation_source=payload.creation_source,
                evidence_count=1,
                is_confirmed=initial_status == "active",
            )

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
                        {
                            "conflict_status": conflict["status"],
                            "safety_status": safety["status"],
                            "importance_score": initial_importance,
                            "confidence_score": initial_confidence,
                            "evidence_count": 1,
                            "freshness_state": FreshnessState.FRESH.value,
                        }
                    ),
                },
            )

            # Phase 17.5 Dispute Event Recording
            if conf_eval.has_conflict and conf_eval.dispute_record:
                dispute_dict = conf_eval.dispute_record.to_dict()
                dispute_dict["memory_b_id"] = item_public_id
                self.repository.record_memory_item_event(
                    connection,
                    {
                        "memory_item_id": item["id"],
                        "event_type": "CONFLICT_DETECTED",
                        "created_by_admin_public_id": admin_id,
                        "details_json": dumps_json(dispute_dict),
                    },
                )
                self.repository.record_memory_item_event(
                    connection,
                    {
                        "memory_item_id": item["id"],
                        "event_type": "DISPUTE_CREATED",
                        "created_by_admin_public_id": admin_id,
                        "details_json": dumps_json(dispute_dict),
                    },
                )
                if conf_eval.conflicting_item:
                    conf_id = conf_eval.conflicting_item.get("id")
                    if not conf_id and conf_eval.conflicting_item.get("public_id"):
                        conf_row = self.repository.memory_item(connection, conf_eval.conflicting_item["public_id"])
                        conf_id = conf_row["id"]
                    if conf_id:
                        self.repository.record_memory_item_event(
                            connection,
                            {
                                "memory_item_id": conf_id,
                                "event_type": "CONFLICT_DETECTED",
                                "created_by_admin_public_id": admin_id,
                                "details_json": dumps_json(dispute_dict),
                            },
                        )
                        self.repository.record_memory_item_event(
                            connection,
                            {
                                "memory_item_id": conf_id,
                                "event_type": "DISPUTE_CREATED",
                                "created_by_admin_public_id": admin_id,
                                "details_json": dumps_json(dispute_dict),
                            },
                        )

            self._audit(
                connection, "memory_proposed", admin_id, item_public_id,
                status=initial_status, conflict=conflict["status"],
                importance_score=initial_importance, confidence_score=initial_confidence,
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

    def _current_display_value(self, connection, item_row) -> str:
        if not item_row["current_version_id"]:
            return ""
        row = connection.execute(
            "SELECT display_value FROM memory_item_versions WHERE id=?",
            (item_row["current_version_id"],),
        ).fetchone()
        return row["display_value"] if row else ""

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

    def retrieve(
        self,
        payload: MemoryRetrieveRequest,
        admin_id: str,
        *,
        retrieval_mode: str | RetrievalMode = RetrievalMode.CURRENT,
        active_topic: str | None = None,
        active_task: str | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(
                connection, payload.retrieval_profile_public_id
            )
            if profile["status"] != "active":
                raise ValidationError("retrieval profile must be active to be used")

            started = time.perf_counter()
            allowed_categories = _loads(profile["allowed_categories_json"])
            allowed_purposes = _loads(profile["allowed_purposes_json"])

            effective_mode = getattr(payload, "retrieval_mode", None) or retrieval_mode
            req_topic = getattr(payload, "active_topic", None) or active_topic
            req_task = getattr(payload, "active_task", None) or active_task

            mode_enum = MemoryRecallEngine.resolve_mode(effective_mode)
            if mode_enum == RetrievalMode.HISTORICAL:
                candidate_rows = self.repository.list_memory_items(
                    connection, participant_scope_key=payload.participant_scope_key
                )
            else:
                candidate_rows = self.repository.active_memory_items_for_participant(
                    connection, payload.participant_scope_key
                )

            candidates = []
            for row in candidate_rows:
                norm_val = self._current_normalized_value(connection, row)
                disp_val = self._current_display_value(connection, row)
                is_disputed = self._has_active_dispute(connection, row["id"])

                vector = None
                if row["current_version_id"]:
                    embedding_row = connection.execute(
                        "SELECT * FROM memory_embeddings WHERE memory_item_version_id=? "
                        "ORDER BY id DESC LIMIT 1",
                        (row["current_version_id"],),
                    ).fetchone()
                    if embedding_row:
                        vector = unpack_vector(
                            embedding_row["vector_blob"], dimensions=embedding_row["dimensions"]
                        )

                # Check consolidation compression metadata
                comp_event = connection.execute(
                    "SELECT details_json FROM memory_item_events WHERE memory_item_id=? "
                    "AND event_type='CONSOLIDATION_CREATED' ORDER BY id DESC LIMIT 1",
                    (row["id"],),
                ).fetchone()
                compression_state = loads_json(comp_event["details_json"]) if comp_event else {}

                candidates.append(
                    {
                        "public_id": row["public_id"],
                        "participant_scope_key": row["participant_scope_key"],
                        "status": row["status"],
                        "category": row["category"],
                        "purpose": row["purpose"],
                        "confidence_type": row["confidence_type"],
                        "confirmed": row["status"] == "active",
                        "display_value": disp_val,
                        "normalized_value": norm_val,
                        "created_at": row["created_at"],
                        "current_version_id": row["current_version_id"],
                        "vector": vector,
                        "is_disputed": is_disputed,
                        "compression_state": compression_state,
                        "is_canonical": bool(compression_state.get("is_compressed")),
                        "constituent_source_ids": compression_state.get("source_references", []),
                        "importance_score": float(row.get("importance_score", 50.0)) if "importance_score" in row.keys() else 50.0,
                        "confidence_score": float(row.get("confidence_score", 50.0)) if "confidence_score" in row.keys() else 50.0,
                        "evidence_count": int(row.get("evidence_count", 1)) if "evidence_count" in row.keys() else 1,
                    }
                )

            conflict_policy = profile["conflict_policy"] if "conflict_policy" in profile.keys() else "prefer_recent"
            weights = MemoryRecallWeights(
                keyword_weight=profile["keyword_weight"],
                vector_weight=profile["vector_weight"],
                importance_weight=0.20,
                confidence_weight=0.10,
                conflict_penalty=20.0,
                minimum_score_threshold=profile["minimum_score"],
            )

            recall_res = MemoryRecallEngine.recall_memories(
                query=payload.query,
                candidates=candidates,
                participant_scope_key=payload.participant_scope_key,
                retrieval_mode=mode_enum,
                active_topic=req_topic,
                active_task=req_task,
                allowed_categories=allowed_categories,
                allowed_purposes=allowed_purposes,
                conflict_policy=conflict_policy,
                weights=weights,
                max_results=profile["maximum_results"],
                max_tokens=profile["maximum_memory_tokens"] if "maximum_memory_tokens" in profile.keys() else 600,
                is_admin=bool(admin_id),
                now_epoch=time.time(),
            )

            ranked = []
            for item in recall_res.results:
                ranked.append(
                    {
                        "memory_item_public_id": item.memory_item_public_id,
                        "category": item.category,
                        "purpose": item.purpose,
                        "display_value": item.display_value,
                        "normalized_value": item.normalized_value,
                        "status": item.status,
                        "confidence_type": item.confidence_type,
                        "importance_score": item.importance_score,
                        "confidence_score": item.confidence_score,
                        "evidence_count": item.evidence_count,
                        "freshness_state": item.freshness_state,
                        "keyword_score": item.keyword_score,
                        "vector_score": item.vector_score,
                        "recency_score": None,
                        "combined_score": item.effective_recall_score,
                        "rank": item.rank,
                        "is_canonical": item.is_canonical,
                        "constituent_source_ids": item.constituent_source_ids,
                        "conflict_status": item.conflict_status,
                        "disputed_warning": item.disputed_warning,
                        "provenance": item.provenance,
                    }
                )

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
                        "conflict_status": entry.get("conflict_status", "no_conflict"),
                    },
                )
            self._audit(
                connection, "memory_retrieval_executed", admin_id, run_public_id,
                result_count=len(ranked),
            )
            return {
                **public_row(run),
                "results": ranked,
                "excluded": recall_res.excluded,
                "retrieval_mode": recall_res.retrieval_mode,
            }

    def reason_over_memories(
        self,
        payload: MemoryRetrieveRequest,
        admin_id: str,
        *,
        retrieval_mode: str | RetrievalMode = RetrievalMode.CURRENT,
        active_topic: str | None = None,
        active_task: str | None = None,
        now_epoch: float | None = None,
    ) -> MemoryReasoningPacket:
        """Executes retrieval and constructs a coherent, structured MemoryReasoningPacket."""
        retrieval = self.retrieve(
            payload,
            admin_id,
            retrieval_mode=retrieval_mode,
            active_topic=active_topic,
            active_task=active_task,
        )

        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(
                connection, payload.retrieval_profile_public_id
            )
            conflict_policy = profile["conflict_policy"] if "conflict_policy" in profile.keys() else "prefer_recent"
            max_tokens = profile["maximum_memory_tokens"] if "maximum_memory_tokens" in profile.keys() else 600

        packet = MemoryReasoningEngine.assemble_reasoning_packet(
            query=payload.query,
            participant_scope_key=payload.participant_scope_key,
            retrieval_mode=retrieval.get("retrieval_mode", retrieval_mode),
            retrieved_items=retrieval.get("results", []),
            conflict_policy=conflict_policy,
            max_tokens=max_tokens,
            now_epoch=now_epoch,
        )
        return packet

    def _has_active_dispute(self, connection, memory_item_id: int) -> bool:
        """Checks if a memory item is currently subject to an unresolved dispute."""
        rows = connection.execute(
            "SELECT event_type FROM memory_item_events WHERE memory_item_id=? "
            "ORDER BY id DESC",
            (memory_item_id,),
        ).fetchall()
        for r in rows:
            evt = r["event_type"]
            if evt in ("DISPUTE_RESOLVED", "DISPUTE_DISMISSED", "MEMORY_SUPERSEDED"):
                return False
            if evt in ("CONFLICT_DETECTED", "DISPUTE_CREATED"):
                return True
        return False

    def get_dispute(self, dispute_id: str) -> dict[str, Any] | None:
        """Retrieves structured dispute details by dispute_id."""
        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT details_json FROM memory_item_events WHERE event_type='DISPUTE_CREATED' "
                "AND details_json LIKE ? ORDER BY id DESC LIMIT 1",
                (f'%"{dispute_id}"%',),
            ).fetchone()
            if not row:
                return None
            return loads_json(row["details_json"])

    def list_disputes(self, participant_scope_key: str | None = None) -> list[dict[str, Any]]:
        """Lists disputes, optionally filtered by participant scope."""
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT details_json FROM memory_item_events WHERE event_type='DISPUTE_CREATED' "
                "ORDER BY id DESC"
            ).fetchall()
            disputes = []
            seen_ids = set()
            for r in rows:
                details = loads_json(r["details_json"])
                disp_id = details.get("dispute_id")
                if disp_id and disp_id not in seen_ids:
                    seen_ids.add(disp_id)
                    if participant_scope_key is None or details.get("participant_scope_key") == participant_scope_key:
                        disputes.append(details)
            return disputes

    def resolve_dispute(
        self,
        dispute_id: str,
        strategy: str | ResolutionStrategy,
        admin_id: str,
        resolution_reason: str = "",
    ) -> dict[str, Any]:
        """Applies an authorized human arbitration decision to a dispute."""
        strat = ResolutionStrategy(strategy) if isinstance(strategy, str) else strategy
        with self.repository.transaction() as connection:
            dispute_row = connection.execute(
                "SELECT details_json FROM memory_item_events WHERE event_type='DISPUTE_CREATED' "
                "AND details_json LIKE ? ORDER BY id DESC LIMIT 1",
                (f'%"{dispute_id}"%',),
            ).fetchone()
            if not dispute_row:
                raise ValidationError(f"Dispute with ID '{dispute_id}' not found")

            details = loads_json(dispute_row["details_json"])
            mem_a_id = details.get("memory_a_id")
            mem_b_id = details.get("memory_b_id")

            item_a = self.repository.memory_item(connection, mem_a_id) if mem_a_id else None
            item_b = (
                self.repository.memory_item(connection, mem_b_id)
                if mem_b_id and mem_b_id != "pending_candidate"
                else None
            )

            if strat == ResolutionStrategy.SUPERSEDE_EXISTING:
                if item_a:
                    self.repository.update_memory_item(connection, item_a["id"], {"status": "superseded"})
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": item_a["id"],
                            "event_type": "MEMORY_SUPERSEDED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {"dispute_id": dispute_id, "superseded_by": mem_b_id, "reason": resolution_reason}
                            ),
                        },
                    )
                if item_b:
                    self.repository.update_memory_item(connection, item_b["id"], {"status": "active"})
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": item_b["id"],
                            "event_type": "DISPUTE_RESOLVED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {"dispute_id": dispute_id, "strategy": strat.value, "reason": resolution_reason}
                            ),
                        },
                    )
            elif strat == ResolutionStrategy.RETAIN_EXISTING:
                if item_b:
                    self.repository.update_memory_item(connection, item_b["id"], {"status": "rejected"})
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": item_b["id"],
                            "event_type": "rejected",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {"dispute_id": dispute_id, "strategy": strat.value, "reason": resolution_reason}
                            ),
                        },
                    )
                if item_a:
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": item_a["id"],
                            "event_type": "DISPUTE_RESOLVED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {"dispute_id": dispute_id, "strategy": strat.value, "reason": resolution_reason}
                            ),
                        },
                    )
            elif strat == ResolutionStrategy.RETAIN_BOTH_COEXIST:
                if item_a:
                    self.repository.update_memory_item(connection, item_a["id"], {"status": "active"})
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": item_a["id"],
                            "event_type": "CONFLICT_COEXISTENCE_CONFIRMED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {"dispute_id": dispute_id, "strategy": strat.value, "reason": resolution_reason}
                            ),
                        },
                    )
                if item_b:
                    self.repository.update_memory_item(connection, item_b["id"], {"status": "active"})
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": item_b["id"],
                            "event_type": "CONFLICT_COEXISTENCE_CONFIRMED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {"dispute_id": dispute_id, "strategy": strat.value, "reason": resolution_reason}
                            ),
                        },
                    )
            elif strat == ResolutionStrategy.DISMISS:
                if item_b and item_b["status"] in ("proposed", "awaiting_confirmation"):
                    self.repository.update_memory_item(connection, item_b["id"], {"status": "rejected"})
                if item_a:
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": item_a["id"],
                            "event_type": "DISPUTE_DISMISSED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json({"dispute_id": dispute_id, "reason": resolution_reason}),
                        },
                    )

            self._audit(
                connection, "memory_conflict_resolved", admin_id, dispute_id,
                strategy=strat.value, reason=resolution_reason,
            )
            return {
                "dispute_id": dispute_id,
                "status": "resolved" if strat != ResolutionStrategy.DISMISS else "dismissed",
                "strategy": strat.value,
                "resolved_by": admin_id,
                "resolution_reason": resolution_reason,
            }

    def dismiss_dispute(self, dispute_id: str, admin_id: str, reason: str = "") -> dict[str, Any]:
        """Dismisses an erroneous dispute."""
        return self.resolve_dispute(dispute_id, ResolutionStrategy.DISMISS, admin_id, reason)

    def get_retrieval_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.retrieval_run(connection, public_id))

    def get_retrieval_results(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.retrieval_run(connection, public_id)
            rows = self.repository.results_for_retrieval_run(connection, run["id"])
            return {"items": [public_row(row) for row in rows]}

    # --- memory consolidation (Phase 17.6) -------------------------------------------

    def consolidate_memories(
        self,
        participant_scope_key: str,
        category: str,
        purpose: str,
        admin_id: str,
    ) -> dict[str, Any]:
        """Consolidates eligible active memory observations into canonical knowledge."""
        with self.repository.transaction() as connection:
            # 1. Fetch active memories in scope
            active_rows = self.repository.active_memory_items_for_participant(
                connection, participant_scope_key
            )
            candidate_items = []
            for row in active_rows:
                if (
                    str(row["category"]).lower() == category.lower()
                    and str(row["purpose"]).lower() == purpose.lower()
                ):
                    disp_val = self._current_display_value(connection, row)
                    norm_val = self._current_normalized_value(connection, row)

                    vector_blob = None
                    if row["current_version_id"]:
                        emb_row = connection.execute(
                            "SELECT vector_blob FROM memory_embeddings WHERE memory_item_version_id=? "
                            "ORDER BY id DESC LIMIT 1",
                            (row["current_version_id"],),
                        ).fetchone()
                        if emb_row:
                            vector_blob = emb_row["vector_blob"]

                    candidate_items.append(
                        {
                            "id": row["id"],
                            "public_id": row["public_id"],
                            "participant_scope_key": row["participant_scope_key"],
                            "category": row["category"],
                            "purpose": row["purpose"],
                            "creation_source": row["creation_source"],
                            "confidence_type": row["confidence_type"],
                            "status": row["status"],
                            "valid_from": row["valid_from"],
                            "expires_at": row["expires_at"],
                            "created_at": row["created_at"],
                            "display_value": disp_val,
                            "normalized_value": norm_val,
                            "vector_blob": vector_blob,
                            "current_version_id": row["current_version_id"],
                            "source_session_id": row["source_session_id"] if "source_session_id" in row.keys() else None,
                            "source_turn_id": row["source_turn_id"] if "source_turn_id" in row.keys() else None,
                            "evidence_count": row["evidence_count"] if "evidence_count" in row.keys() else 1,
                        }
                    )

            # 2. Fetch active disputes to enforce Conflict Gate
            active_disputes = self.list_disputes(participant_scope_key=participant_scope_key)

            # 3. Group candidates using pure domain engine
            groups = MemoryConsolidatorEngine.group_candidates(
                candidates=candidate_items,
                participant_scope_key=participant_scope_key,
                category=category,
                purpose=purpose,
                active_disputes=active_disputes,
            )

            if not groups:
                return {
                    "participant_scope_key": participant_scope_key,
                    "category": category,
                    "purpose": purpose,
                    "consolidated_count": 0,
                    "canonical_records": [],
                    "message": "no_eligible_groups_found",
                }

            results = []
            for grp in groups:
                res = MemoryConsolidatorEngine.consolidate_group(grp)

                # Check governance: SYSTEM / ADMIN require human approval (G1 gate)
                canonical_status = "active"
                if res.requires_human_approval:
                    canonical_status = "proposed"

                # Check idempotency: Check if canonical already created
                existing_canonical_id = None
                for c in grp.candidate_items:
                    evts = connection.execute(
                        "SELECT id FROM memory_item_events WHERE memory_item_id=? "
                        "AND event_type='CONSOLIDATION_CREATED'",
                        (c["id"],),
                    ).fetchall()
                    if evts:
                        existing_canonical_id = c["public_id"]
                        break

                if existing_canonical_id:
                    results.append(
                        {
                            "canonical_public_id": existing_canonical_id,
                            "group_id": grp.group_id,
                            "source_memory_ids": res.source_memory_ids,
                            "status": "already_consolidated",
                            "total_evidence_count": res.total_evidence_count,
                        }
                    )
                    continue

                # Create canonical memory item in DB
                canonical_item_public_id = self.repository.create_memory_item(
                    connection,
                    {
                        "participant_scope_key": participant_scope_key,
                        "category": category,
                        "purpose": purpose,
                        "creation_source": "system_derived",
                        "confidence_type": "user_confirmed",
                        "status": canonical_status,
                        "valid_from": _now_sql(),
                    },
                )
                canon_row = self.repository.memory_item(connection, canonical_item_public_id)

                # Record version & embedding
                norm_dict = {
                    "normalized_value": res.normalized_value,
                    "display_value": res.display_value,
                }
                version_public_id = self._record_version(
                    connection,
                    canon_row["id"],
                    norm_dict,
                    change_reason="consolidated_canonical_synthesis",
                    created_by=admin_id,
                )
                self.repository.update_memory_item(
                    connection,
                    canon_row["id"],
                    {
                        "current_version_id": self.repository.memory_item_version(
                            connection, version_public_id
                        )["id"]
                    },
                )

                # Transition constituent memories to status = 'consolidated'
                for src_id_str in res.source_memory_ids:
                    src_row = self.repository.memory_item(connection, src_id_str)
                    self.repository.update_memory_item(
                        connection, src_row["id"], {"status": "superseded"}
                    )
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": src_row["id"],
                            "event_type": "MEMORY_CONSOLIDATED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {
                                    "canonical_public_id": canonical_item_public_id,
                                    "group_id": grp.group_id,
                                }
                            ),
                        },
                    )

                # Record immutable audit event on canonical item
                comp_state_dict = dict(res.compression_state)
                comp_state_dict["canonical_public_id"] = canonical_item_public_id
                self.repository.record_memory_item_event(
                    connection,
                    {
                        "memory_item_id": canon_row["id"],
                        "event_type": "CONSOLIDATION_CREATED",
                        "created_by_admin_public_id": admin_id,
                        "details_json": dumps_json(comp_state_dict),
                    },
                )

                self._audit(
                    connection,
                    "memory_consolidated",
                    admin_id,
                    canonical_item_public_id,
                    group_id=grp.group_id,
                    source_count=len(res.source_memory_ids),
                    total_evidence=res.total_evidence_count,
                    status=canonical_status,
                )

                results.append(
                    {
                        "canonical_public_id": canonical_item_public_id,
                        "group_id": grp.group_id,
                        "display_value": res.display_value,
                        "source_memory_ids": res.source_memory_ids,
                        "total_evidence_count": res.total_evidence_count,
                        "confidence_score": res.confidence_score,
                        "importance_score": res.importance_score,
                        "status": canonical_status,
                        "requires_human_approval": res.requires_human_approval,
                    }
                )

            return {
                "participant_scope_key": participant_scope_key,
                "category": category,
                "purpose": purpose,
                "consolidated_count": len(results),
                "canonical_records": results,
            }

    def unconsolidate_memory(
        self, canonical_public_id: str, admin_id: str, reason: str = "administrative_rollback"
    ) -> dict[str, Any]:
        """Reverses consolidation: restores constituent memories to active, supersedes canonical."""
        with self.repository.transaction() as connection:
            canon_row = self.repository.memory_item(connection, canonical_public_id)

            event_row = connection.execute(
                "SELECT details_json FROM memory_item_events WHERE memory_item_id=? "
                "AND event_type='CONSOLIDATION_CREATED' ORDER BY id DESC LIMIT 1",
                (canon_row["id"],),
            ).fetchone()

            if not event_row:
                raise ValidationError(
                    f"No consolidation event found for memory '{canonical_public_id}'"
                )

            comp_state = loads_json(event_row["details_json"])
            source_refs = comp_state.get("source_references", [])

            restored_ids = []
            for src_pub_id in source_refs:
                src_item = self.repository.memory_item(connection, src_pub_id)
                self.repository.update_memory_item(
                    connection, src_item["id"], {"status": "active"}
                )
                self.repository.record_memory_item_event(
                    connection,
                    {
                        "memory_item_id": src_item["id"],
                        "event_type": "UNCONSOLIDATED",
                        "created_by_admin_public_id": admin_id,
                        "details_json": dumps_json(
                            {
                                "canonical_public_id": canonical_public_id,
                                "reason": reason,
                            }
                        ),
                    },
                )
                restored_ids.append(src_pub_id)

            self.repository.update_memory_item(
                connection, canon_row["id"], {"status": "superseded"}
            )
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": canon_row["id"],
                    "event_type": "UNCONSOLIDATED",
                    "created_by_admin_public_id": admin_id,
                    "details_json": dumps_json(
                        {
                            "restored_sources": restored_ids,
                            "reason": reason,
                        }
                    ),
                },
            )

            self._audit(
                connection,
                "memory_unconsolidated",
                admin_id,
                canonical_public_id,
                restored_count=len(restored_ids),
                reason=reason,
            )

            return {
                "canonical_public_id": canonical_public_id,
                "status": "superseded",
                "restored_source_ids": restored_ids,
                "restored_count": len(restored_ids),
                "unconsolidated_by": admin_id,
                "reason": reason,
            }

    def get_consolidated_sources(self, canonical_public_id: str) -> dict[str, Any]:
        """Retrieves constituent source observations for a canonical consolidated memory."""
        with self.repository.transaction() as connection:
            canon_row = self.repository.memory_item(connection, canonical_public_id)
            event_row = connection.execute(
                "SELECT details_json FROM memory_item_events WHERE memory_item_id=? "
                "AND event_type='CONSOLIDATION_CREATED' ORDER BY id DESC LIMIT 1",
                (canon_row["id"],),
            ).fetchone()
            if not event_row:
                return {
                    "canonical_public_id": canonical_public_id,
                    "is_consolidated": False,
                    "sources": [],
                }

            comp_state = loads_json(event_row["details_json"])
            sources = []
            for src_pub_id in comp_state.get("source_references", []):
                src_row = self.repository.memory_item(connection, src_pub_id)
                sources.append(
                    {
                        **public_row(src_row),
                        "display_value": self._current_display_value(connection, src_row),
                        "normalized_value": self._current_normalized_value(connection, src_row),
                    }
                )
            return {
                "canonical_public_id": canonical_public_id,
                "is_compressed": True,
                "compression_state": comp_state,
                "sources": sources,
            }

    # --- memory lifecycle & freshness (Phase 17.7) -----------------------------------

    def evaluate_memory_freshness(self, public_id: str) -> dict[str, Any]:
        """Dynamically evaluates freshness, decay penalty, and effective rank for a memory."""
        with self.repository.transaction() as connection:
            row = self.repository.memory_item(connection, public_id)
            active_disputes = self.list_disputes(participant_scope_key=row["participant_scope_key"])

            disp_val = self._current_display_value(connection, row)
            norm_val = self._current_normalized_value(connection, row)

            item_dict = {
                "id": row["id"],
                "public_id": row["public_id"],
                "category": row["category"],
                "purpose": row["purpose"],
                "status": row["status"],
                "created_at": row["created_at"],
                "valid_from": row["valid_from"],
                "expires_at": row["expires_at"],
                "display_value": disp_val,
                "normalized_value": norm_val,
                "importance_score": 50.0,
                "confidence_score": 50.0,
            }

            # Fetch most recent importance and confidence from events if available
            evt_row = connection.execute(
                "SELECT details_json FROM memory_item_events WHERE memory_item_id=? "
                "ORDER BY id DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            if evt_row:
                evt_details = loads_json(evt_row["details_json"])
                if "importance_score" in evt_details:
                    item_dict["importance_score"] = evt_details["importance_score"]
                if "confidence_score" in evt_details:
                    item_dict["confidence_score"] = evt_details["confidence_score"]
                elif "total_evidence_count" in evt_details:
                    item_dict["confidence_score"] = min(
                        100.0, 50.0 + min(15.0, (int(evt_details["total_evidence_count"]) - 1) * 2.0)
                    )

            res = MemoryLifecycleEngine.evaluate_freshness(
                item=item_dict,
                active_disputes=active_disputes,
            )
            return res.to_dict()

    def archive_memory(
        self, public_id: str, admin_id: str, reason: str = ""
    ) -> dict[str, Any]:
        """Transitions a memory item to archived status with full audit logging."""
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, public_id)
            is_disputed = self._has_active_dispute(connection, item["id"])

            ok, msg = MemoryLifecycleEngine.validate_lifecycle_transition(
                current_status=item["status"],
                target_status="archived",
                category=item["category"],
                is_admin_authorized=True,
                is_disputed=is_disputed,
            )
            if not ok:
                raise ValidationError(f"Cannot archive memory: {msg}")

            self.repository.update_memory_item(connection, item["id"], {"status": "archived"})
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": item["id"],
                    "event_type": "MEMORY_ARCHIVED",
                    "created_by_admin_public_id": admin_id,
                    "details_json": dumps_json(
                        {
                            "previous_status": item["status"],
                            "new_status": "archived",
                            "reason": reason or "administrative_archival",
                        }
                    ),
                },
            )
            self._audit(
                connection,
                "memory_archived",
                admin_id,
                public_id,
                previous_status=item["status"],
                reason=reason,
            )
            return public_row(self.repository.memory_item(connection, public_id))

    def reactivate_memory(
        self, public_id: str, admin_id: str, reason: str = ""
    ) -> dict[str, Any]:
        """Reactivates an archived or expired memory item under admin authorization."""
        with self.repository.transaction() as connection:
            item = self.repository.memory_item(connection, public_id)
            ok, msg = MemoryLifecycleEngine.validate_lifecycle_transition(
                current_status=item["status"],
                target_status="active",
                category=item["category"],
                is_admin_authorized=True,
                is_disputed=False,
            )
            if not ok:
                raise ValidationError(f"Cannot reactivate memory: {msg}")

            self.repository.update_memory_item(connection, item["id"], {"status": "active"})
            self.repository.record_memory_item_event(
                connection,
                {
                    "memory_item_id": item["id"],
                    "event_type": "MEMORY_REACTIVATED",
                    "created_by_admin_public_id": admin_id,
                    "details_json": dumps_json(
                        {
                            "previous_status": item["status"],
                            "new_status": "active",
                            "reason": reason or "administrative_reactivation",
                        }
                    ),
                },
            )
            self._audit(
                connection,
                "memory_reactivated",
                admin_id,
                public_id,
                previous_status=item["status"],
                reason=reason,
            )
            return public_row(self.repository.memory_item(connection, public_id))

    def run_lifecycle_sweep(
        self, participant_scope_key: str, admin_id: str, batch_size: int = 50
    ) -> dict[str, Any]:
        """Runs a bounded, idempotent maintenance sweep for expiration and archival within participant scope."""
        with self.repository.transaction() as connection:
            now = time.time()

            rows = connection.execute(
                "SELECT * FROM memory_items WHERE participant_scope_key=? "
                "AND status IN ('active', 'expired') ORDER BY id ASC LIMIT ?",
                (participant_scope_key, batch_size),
            ).fetchall()

            expired_count = 0
            archived_count = 0
            processed_count = 0
            results = []

            for row in rows:
                processed_count += 1
                cat = row["category"]
                status = row["status"]
                created_epoch = MemoryLifecycleEngine.parse_timestamp_to_epoch(row["created_at"])
                age = MemoryLifecycleEngine.compute_memory_age(created_epoch, now)
                is_disp = self._has_active_dispute(connection, row["id"])

                # Check archival eligibility first
                if MemoryLifecycleEngine.is_archival_eligible(
                    category=cat, age_seconds=age, status=status, is_disputed=is_disp
                ):
                    self.repository.update_memory_item(connection, row["id"], {"status": "archived"})
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": row["id"],
                            "event_type": "MEMORY_ARCHIVED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {
                                    "previous_status": status,
                                    "new_status": "archived",
                                    "age_seconds": round(age, 2),
                                    "reason": "lifecycle_sweep_archival",
                                }
                            ),
                        },
                    )
                    archived_count += 1
                    results.append({"public_id": row["public_id"], "transition": f"{status}->archived"})

                # Check expiration eligibility for active memories
                elif status == "active" and MemoryLifecycleEngine.is_expiration_eligible(
                    category=cat, age_seconds=age, status=status, is_disputed=is_disp
                ):
                    self.repository.update_memory_item(connection, row["id"], {"status": "expired"})
                    self.repository.record_memory_item_event(
                        connection,
                        {
                            "memory_item_id": row["id"],
                            "event_type": "MEMORY_EXPIRED",
                            "created_by_admin_public_id": admin_id,
                            "details_json": dumps_json(
                                {
                                    "previous_status": "active",
                                    "new_status": "expired",
                                    "age_seconds": round(age, 2),
                                    "reason": "lifecycle_sweep_expiration",
                                }
                            ),
                        },
                    )
                    expired_count += 1
                    results.append({"public_id": row["public_id"], "transition": "active->expired"})

            self._audit(
                connection,
                "memory_lifecycle_sweep",
                admin_id,
                participant_scope_key,
                processed_count=processed_count,
                expired_count=expired_count,
                archived_count=archived_count,
            )

            return {
                "participant_scope_key": participant_scope_key,
                "processed_count": processed_count,
                "expired_count": expired_count,
                "archived_count": archived_count,
                "actions": results,
            }

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
