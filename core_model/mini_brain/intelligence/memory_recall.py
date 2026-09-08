"""Phase 17.8: Memory Recall & Retrieval Intelligence Layer.

Implements structured, governed, deterministic, CPU-first memory recall:
1. Multi-Mode Retrieval (CURRENT, HISTORICAL, TASK, PREFERENCE)
2. Deterministic Multi-Signal Mathematical Ranking (Relevance, Intrinsic, Context, Freshness, Conflict)
3. Lexical Token Overlap + 64-dim Vector Cosine Similarity
4. Context Intelligence Integration (Active Topic & Task Boosts from Phase 17.2)
5. Consolidation Deduplication & Lineage Provenance (Phase 17.6)
6. Freshness Decay & Expiration Integration (Phase 17.7)
7. Dispute Protection Gate & Advisory Warnings (Phase 17.5)
8. Multi-Tenant Scope Isolation & G1/G8 Governance (G1, G4, G5, G8, G10/G11)
9. Hard Token (max 600) and Result (max 10) Budgeting
10. Deterministic Tie-Breaking & Zero LLM / Hallucination Dependencies
"""

from __future__ import annotations

import enum
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from core_model.mini_brain.intelligence.conflict_detector import (
    ConflictKnowledgeEngine,
    DisputeState,
)
from core_model.mini_brain.intelligence.context_intelligence import TOPIC_TAXONOMY
from core_model.mini_brain.intelligence.memory_intelligence import (
    FreshnessState,
    LEGACY_CATEGORY_MAP,
    MemoryCategory,
    MemoryIntelligenceEngine,
)
from core_model.mini_brain.intelligence.memory_lifecycle import (
    FRESHNESS_PENALTIES,
    MemoryLifecycleEngine,
)
from core_model.mini_brain.llm_runtime.message_sanitizer import sanitize_message
from core_model.mini_brain.llm_runtime.token_budget import estimate_tokens
from core_model.rag.embedding import compute_embedding, unpack_vector
from core_model.rag.vector_index import score_vectors


class RetrievalMode(str, enum.Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    TASK = "TASK"
    PREFERENCE = "PREFERENCE"


@dataclass(frozen=True)
class MemoryRecallWeights:
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    importance_weight: float = 0.20
    confidence_weight: float = 0.10
    topic_boost: float = 20.0
    task_boost: float = 25.0
    conflict_penalty: float = 20.0
    stale_penalty: float = 15.0
    expired_penalty: float = 40.0
    minimum_score_threshold: float = 15.0


@dataclass
class MemoryRecallItem:
    memory_item_public_id: str
    category: str
    purpose: str
    display_value: str
    normalized_value: str
    status: str
    confidence_type: str
    importance_score: float
    confidence_score: float
    evidence_count: int
    freshness_state: str
    keyword_score: float
    vector_score: float | None
    effective_recall_score: float
    rank: int = 1
    is_canonical: bool = False
    parent_canonical_id: str | None = None
    constituent_source_ids: list[str] = field(default_factory=list)
    conflict_status: str = "no_conflict"
    disputed_warning: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryRecallResult:
    query: str
    retrieval_mode: str
    participant_scope_key: str
    total_candidates: int
    final_result_count: int
    results: list[MemoryRecallItem]
    excluded: list[dict[str, Any]]
    runtime_milliseconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["results"] = [item.to_dict() if hasattr(item, "to_dict") else item for item in self.results]
        return res


class MemoryRecallEngine:
    """Pure domain engine for deterministic multi-signal memory recall and retrieval intelligence."""

    @staticmethod
    def resolve_mode(mode_input: str | RetrievalMode | None) -> RetrievalMode:
        """Resolves input string or enum to RetrievalMode."""
        if not mode_input:
            return RetrievalMode.CURRENT
        if isinstance(mode_input, RetrievalMode):
            return mode_input
        m_str = str(mode_input).strip().upper()
        if m_str in RetrievalMode.__members__:
            return RetrievalMode[m_str]
        return RetrievalMode.CURRENT

    @staticmethod
    def compute_lexical_overlap(query_tokens: set[str], content_tokens: set[str]) -> float:
        """Computes normalized lexical token overlap in [0.0, 1.0]."""
        if not query_tokens or not content_tokens:
            return 0.0
        overlap = len(query_tokens & content_tokens)
        return min(1.0, overlap / max(1, len(query_tokens)))

    @staticmethod
    def is_candidate_eligible_for_mode(
        candidate: dict[str, Any],
        mode: RetrievalMode,
        *,
        allowed_categories: tuple[str, ...] | list[str] | None = None,
        allowed_purposes: tuple[str, ...] | list[str] | None = None,
        is_admin: bool = False,
    ) -> tuple[bool, str | None]:
        """Evaluates whether a candidate is eligible under governance and active retrieval mode."""
        status = str(candidate.get("status", "")).lower()
        cat_str = str(candidate.get("category", "")).upper()
        purpose = str(candidate.get("purpose", ""))

        # Disallow unconditionally invalid/destroyed states
        if status in ("deleted", "revoked", "quarantined", "rejected"):
            return False, f"status_{status}_excluded"

        # Disallow proposed or awaiting confirmation unless confirmed active
        if status in ("proposed", "awaiting_confirmation"):
            return False, f"status_{status}_excluded"

        # SYSTEM and ADMIN governance (G1)
        if cat_str in ("SYSTEM", "ADMIN") and not is_admin and status != "active":
            return False, "governance_g1_restricted"

        # Allowed category filter
        if allowed_categories:
            norm_allowed_cats = {str(c).upper() for c in allowed_categories}
            if cat_str not in norm_allowed_cats:
                return False, "category_not_in_profile"

        # Allowed purpose filter
        if allowed_purposes and purpose not in allowed_purposes:
            return False, "purpose_not_in_profile"

        # Mode specific status filtering
        if mode == RetrievalMode.CURRENT:
            if status not in ("active", "consolidated"):
                return False, f"mode_current_status_{status}_excluded"
        elif mode == RetrievalMode.TASK:
            if cat_str not in ("TASK", "PROCEDURAL"):
                return False, "mode_task_non_task_category_excluded"
            if status not in ("active", "consolidated"):
                return False, f"mode_task_status_{status}_excluded"
        elif mode == RetrievalMode.PREFERENCE:
            if cat_str != "PREFERENCE":
                return False, "mode_preference_non_pref_category_excluded"
            if status not in ("active", "consolidated"):
                return False, f"mode_preference_status_{status}_excluded"
        elif mode == RetrievalMode.HISTORICAL:
            if status not in ("active", "consolidated", "superseded", "expired", "archived"):
                return False, f"mode_historical_status_{status}_excluded"

        return True, None

    @classmethod
    def compute_recall_score(
        cls,
        *,
        keyword_score: float,
        vector_score: float | None,
        importance_score: float,
        confidence_score: float,
        freshness_state: FreshnessState | str,
        retrieval_mode: RetrievalMode,
        is_disputed: bool,
        has_topic_match: bool = False,
        has_task_match: bool = False,
        weights: MemoryRecallWeights | None = None,
    ) -> float:
        """Computes calibrated, bounded effective recall score in [0.0, 100.0]."""
        w = weights or MemoryRecallWeights()

        v_score = max(0.0, min(1.0, float(vector_score))) if vector_score is not None else 0.0
        k_score = max(0.0, min(1.0, float(keyword_score)))

        # Relevance component (max 70.0)
        relevance = (w.vector_weight * v_score * 40.0) + (w.keyword_weight * k_score * 30.0)

        # Intrinsic component (max 30.0)
        intrinsic = (w.importance_weight * importance_score) + (w.confidence_weight * confidence_score)

        # Context boosts from Phase 17.2
        topic_boost = w.topic_boost if has_topic_match else 0.0
        task_boost = w.task_boost if has_task_match else 0.0

        # Freshness penalty: applied in CURRENT/TASK/PREFERENCE modes; neutralized in HISTORICAL mode
        if retrieval_mode == RetrievalMode.HISTORICAL:
            freshness_penalty = 0.0
        else:
            freshness_penalty = MemoryLifecycleEngine.compute_freshness_penalty(freshness_state)

        # Conflict penalty: applied if memory is currently in active dispute
        conflict_penalty = w.conflict_penalty if is_disputed else 0.0

        raw_score = relevance + intrinsic + topic_boost + task_boost - freshness_penalty - conflict_penalty

        if math.isnan(raw_score) or math.isinf(raw_score):
            return 0.0

        return round(max(0.0, min(100.0, raw_score)), 2)

    @classmethod
    def recall_memories(
        cls,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        participant_scope_key: str,
        retrieval_mode: str | RetrievalMode = RetrievalMode.CURRENT,
        active_topic: str | None = None,
        active_task: str | None = None,
        allowed_categories: tuple[str, ...] | list[str] | None = None,
        allowed_purposes: tuple[str, ...] | list[str] | None = None,
        conflict_policy: str = "prefer_recent",
        weights: MemoryRecallWeights | None = None,
        max_results: int = 10,
        max_tokens: int = 600,
        is_admin: bool = False,
        now_epoch: float | None = None,
    ) -> MemoryRecallResult:
        """Executes full 12-stage cognitive memory recall pipeline."""
        start_time = time.perf_counter()
        mode = cls.resolve_mode(retrieval_mode)
        w = weights or MemoryRecallWeights()
        now = now_epoch if now_epoch is not None else time.time()

        # 1. Query Normalization & Sanitization (G8)
        sanitized_query_obj = sanitize_message(raw_text=query or "")
        clean_query = sanitized_query_obj["sanitized_text"].strip()
        query_tokens = set(clean_query.lower().split()) if clean_query else set()

        query_embedding_dict = compute_embedding(
            clean_query, provider_type="local_custom_embedding", dimensions=64
        )
        query_vector = query_embedding_dict["vector"]

        accepted_candidates: list[dict[str, Any]] = []
        excluded_list: list[dict[str, Any]] = []

        # 2-4. Scope, Governance, and Mode Eligibility
        for cand in candidates:
            cand_scope = str(cand.get("participant_scope_key", ""))
            # Multi-Tenant Scope Isolation (G5)
            if cand_scope != participant_scope_key:
                excluded_list.append({**cand, "exclusion_reason": "cross_participant_denied"})
                continue

            eligible, reason = cls.is_candidate_eligible_for_mode(
                cand,
                mode,
                allowed_categories=allowed_categories,
                allowed_purposes=allowed_purposes,
                is_admin=is_admin,
            )
            if not eligible:
                excluded_list.append({**cand, "exclusion_reason": reason or "ineligible"})
                continue

            accepted_candidates.append(cand)

        # 5-9. Multi-Signal Scoring
        scored_items: list[MemoryRecallItem] = []
        canonical_suppression_map: dict[str, list[str]] = {}

        for cand in accepted_candidates:
            pub_id = str(cand.get("public_id", ""))
            display_val = str(cand.get("display_value") or cand.get("normalized_value") or "")
            norm_val = str(cand.get("normalized_value") or display_val)
            content_lower = display_val.lower()
            content_tokens = set(content_lower.split())

            # Keyword Lexical Score
            keyword_score = cls.compute_lexical_overlap(query_tokens, content_tokens)

            # Vector Cosine Score
            vector_score: float | None = None
            cand_vector = cand.get("vector")
            if cand_vector is None and cand.get("vector_blob"):
                cand_vector = unpack_vector(cand["vector_blob"], dimensions=cand.get("dimensions", 64))
            if cand_vector is None and display_val:
                cand_vector = compute_embedding(
                    display_val, provider_type="local_custom_embedding", dimensions=64
                )["vector"]

            if cand_vector is not None:
                vec_scores = score_vectors(query_vector, [cand_vector], distance_metric="cosine")
                vector_score = max(0.0, float(vec_scores[0]))

            # Intrinsic Scores
            importance = float(cand.get("importance_score", 50.0))
            confidence = float(cand.get("confidence_score", 50.0))
            evidence_count = int(cand.get("evidence_count", 1))

            # Temporal Freshness (Phase 17.7)
            created_epoch = cand.get("created_epoch")
            if created_epoch is None:
                created_epoch = MemoryLifecycleEngine.parse_timestamp_to_epoch(cand.get("created_at"))
            age_sec = MemoryLifecycleEngine.compute_memory_age(created_epoch, now_epoch=now)
            freshness = MemoryLifecycleEngine.determine_freshness_state(
                cand.get("category", "SEMANTIC"), age_sec
            )

            # Context Topic & Task Matching (Phase 17.2)
            has_topic_match = False
            if active_topic:
                top_str = str(active_topic).lower()
                top_norm = top_str.replace("_", " ")
                if top_str in content_lower or top_norm in content_lower:
                    has_topic_match = True
                elif active_topic in TOPIC_TAXONOMY:
                    has_topic_match = any(kw.lower() in content_lower for kw in TOPIC_TAXONOMY[active_topic])

            has_task_match = bool(active_task and active_task.lower() in content_lower)

            # Conflict & Dispute Handling (Phase 17.5)
            is_disputed = bool(cand.get("is_disputed") or cand.get("has_active_dispute"))
            if is_disputed and conflict_policy == "exclude_conflicting":
                excluded_list.append({**cand, "exclusion_reason": "disputed_memory_pending_resolution"})
                continue
            if is_disputed and conflict_policy == "prefer_user_confirmed" and cand.get("confidence_type") != "user_confirmed":
                excluded_list.append({**cand, "exclusion_reason": "disputed_unconfirmed_excluded"})
                continue

            # Effective Recall Score
            recall_score = cls.compute_recall_score(
                keyword_score=keyword_score,
                vector_score=vector_score,
                importance_score=importance,
                confidence_score=confidence,
                freshness_state=freshness,
                retrieval_mode=mode,
                is_disputed=is_disputed,
                has_topic_match=has_topic_match,
                has_task_match=has_task_match,
                weights=w,
            )

            # Minimum score threshold
            if recall_score < w.minimum_score_threshold:
                excluded_list.append({**cand, "exclusion_reason": "score_below_minimum_threshold", "score": recall_score})
                continue

            # Consolidation Provenance (Phase 17.6)
            compression_state = cand.get("compression_state") or {}
            is_canonical = bool(cand.get("is_canonical") or compression_state.get("is_compressed"))
            constituent_source_ids = cand.get("constituent_source_ids") or compression_state.get("source_references") or []
            if is_canonical and constituent_source_ids:
                canonical_suppression_map[pub_id] = [str(s) for s in constituent_source_ids]

            dispute_warning = (
                ConflictKnowledgeEngine.format_retrieval_dispute_warning(
                    {"conflict_classification": "VALUE_CONFLICT", "detection_reason": "unresolved dispute"}
                )
                if is_disputed
                else None
            )

            sanitized_display = sanitize_message(raw_text=display_val)["sanitized_text"]

            item = MemoryRecallItem(
                memory_item_public_id=pub_id,
                category=str(cand.get("category", "SEMANTIC")),
                purpose=str(cand.get("purpose", "general_context")),
                display_value=sanitized_display,
                normalized_value=norm_val,
                status=str(cand.get("status", "active")),
                confidence_type=str(cand.get("confidence_type", "system_derived")),
                importance_score=importance,
                confidence_score=confidence,
                evidence_count=evidence_count,
                freshness_state=freshness.value,
                keyword_score=round(keyword_score, 4),
                vector_score=round(vector_score, 4) if vector_score is not None else None,
                effective_recall_score=recall_score,
                is_canonical=is_canonical,
                parent_canonical_id=cand.get("parent_canonical_id"),
                constituent_source_ids=constituent_source_ids,
                conflict_status="conflict_requires_confirmation" if is_disputed else "no_conflict",
                disputed_warning=dispute_warning,
                provenance={
                    "created_at": cand.get("created_at"),
                    "version_id": cand.get("current_version_id"),
                    "mode": mode.value,
                },
            )
            scored_items.append(item)

        # 10. Consolidation Deduplication in CURRENT / TASK / PREFERENCE modes
        if mode != RetrievalMode.HISTORICAL and canonical_suppression_map:
            all_suppressed_sources = set()
            for src_list in canonical_suppression_map.values():
                all_suppressed_sources.update(src_list)

            deduped_items = []
            for item in scored_items:
                if item.memory_item_public_id in all_suppressed_sources:
                    excluded_list.append({
                        "public_id": item.memory_item_public_id,
                        "exclusion_reason": "suppressed_by_canonical_memory",
                    })
                else:
                    deduped_items.append(item)
            scored_items = deduped_items

        # 11. Deterministic Tie-Breaking & Ranking
        # Primary: effective_recall_score DESC, Secondary: confidence_score DESC, Tertiary: importance_score DESC, Quaternary: public_id ASC
        scored_items.sort(
            key=lambda x: (
                -x.effective_recall_score,
                -x.confidence_score,
                -x.importance_score,
                x.memory_item_public_id,
            )
        )

        # 12. Token & Result Budgeting
        final_results: list[MemoryRecallItem] = []
        accumulated_tokens = 0
        effective_max_results = min(max_results, 10)
        effective_max_tokens = min(max_tokens, 600)

        for rank_idx, item in enumerate(scored_items, start=1):
            if len(final_results) >= effective_max_results:
                break
            tokens = estimate_tokens(item.display_value)
            if accumulated_tokens + tokens <= effective_max_tokens:
                item.rank = rank_idx
                final_results.append(item)
                accumulated_tokens += tokens
            else:
                excluded_list.append({
                    "public_id": item.memory_item_public_id,
                    "exclusion_reason": "token_budget_exceeded",
                })

        runtime_ms = round((time.perf_counter() - start_time) * 1000, 3)

        return MemoryRecallResult(
            query=clean_query,
            retrieval_mode=mode.value,
            participant_scope_key=participant_scope_key,
            total_candidates=len(candidates),
            final_result_count=len(final_results),
            results=final_results,
            excluded=excluded_list,
            runtime_milliseconds=runtime_ms,
            metadata={
                "accumulated_tokens": accumulated_tokens,
                "max_tokens": effective_max_tokens,
                "max_results": effective_max_results,
                "is_admin": is_admin,
            },
        )
