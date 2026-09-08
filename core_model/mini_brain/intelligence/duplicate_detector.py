"""Phase 17.4: Duplicate Knowledge Control Layer.

Implements multi-tier memory duplicate classification and semantic reinforcement:
1. Multi-tier classification:
   - EXACT_DUPLICATE
   - NORMALIZED_DUPLICATE
   - SEMANTIC_DUPLICATE
   - RELATED_BUT_DISTINCT
   - POSSIBLE_CONFLICT
   - DISTINCT
2. Scoped candidate search (max 20 candidates, isolated by participant, category, and purpose)
3. 64-dimensional local vector embedding reuse (core_model.rag.embedding)
4. Cosine similarity scoring with predicate/entity compatibility check
5. Deterministic canonical memory selection (confidence, importance, evidence, provenance, ID tie-break)
6. Semantic evidence reinforcement (canonical.evidence_count += candidate.evidence_count)
7. Immutable SEMANTIC_REINFORCED event generation with G8 secret sanitization
8. Preserves RELATED_BUT_DISTINCT and POSSIBLE_CONFLICT records without destructive merge
9. SYSTEM / ADMIN governance boundary enforcement (REVIEW_REQUIRED)
"""

from __future__ import annotations

import enum
import hashlib
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from core_model.conversation.memory_normalization import normalize_memory_value
from core_model.mini_brain.llm_runtime.message_sanitizer import sanitize_message
from core_model.rag.embedding import compute_embedding, unpack_vector
from core_model.rag.vector_index import score_vectors


class DuplicateClassification(str, enum.Enum):
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    NORMALIZED_DUPLICATE = "NORMALIZED_DUPLICATE"
    SEMANTIC_DUPLICATE = "SEMANTIC_DUPLICATE"
    RELATED_BUT_DISTINCT = "RELATED_BUT_DISTINCT"
    POSSIBLE_CONFLICT = "POSSIBLE_CONFLICT"
    DISTINCT = "DISTINCT"


@dataclass
class DuplicateMatchResult:
    classification: DuplicateClassification
    canonical_item: dict[str, Any] | None
    conflicting_item: dict[str, Any] | None
    similarity_score: float
    decision_reason: str
    review_required: bool
    evidence_count_delta: int = 1
    provenance_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["classification"] = self.classification.value
        return res


SEMANTIC_DUPLICATE_THRESHOLD = 0.88
RELATED_THRESHOLD = 0.65
MAX_CANDIDATES = 20
EMBEDDING_DIMENSIONS = 64
EMBEDDING_PROVIDER = "local_custom_embedding"


class DuplicateKnowledgeEngine:
    """Pure domain engine for duplicate knowledge detection and semantic reinforcement."""

    @staticmethod
    def extract_numbers_or_parameters(text: str) -> set[str]:
        """Extracts numerical tokens or intervals to detect parameter contradictions."""
        # Extracts numbers with units (e.g., 24 hours, 12 hours, 30 days, 94.2%)
        matches = re.findall(r"\b\d+(?:\.\d+)?(?:\s*(?:hours|hour|days|day|mins|minutes|seconds|sec|%|gb|mb|kb|tb))?\b", text.lower())
        return set(m.strip() for m in matches)

    @staticmethod
    def has_predicate_contradiction(text_a: str, text_b: str) -> bool:
        """Detects if two statements share a topic/subject but state conflicting numerical or parameter values."""
        params_a = DuplicateKnowledgeEngine.extract_numbers_or_parameters(text_a)
        params_b = DuplicateKnowledgeEngine.extract_numbers_or_parameters(text_b)
        if params_a and params_b:
            if params_a != params_b:
                return True
        return False

    @staticmethod
    def select_canonical_memory(
        existing_item: dict[str, Any],
        candidate_item: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Deterministically selects canonical record and secondary record.

        Ranking order:
        1. Higher confidence_score (or user_confirmed status)
        2. Higher importance_score
        3. Higher evidence_count
        4. Older stable record (earlier created_at / existing DB row)
        5. Deterministic ID tie-break
        """
        score_existing = (
            float(existing_item.get("confidence_score", 50.0)),
            float(existing_item.get("importance_score", 50.0)),
            int(existing_item.get("evidence_count", 1)),
            1,  # Existing record preferred for stability
            str(existing_item.get("public_id", "")),
        )
        score_candidate = (
            float(candidate_item.get("confidence_score", 50.0)),
            float(candidate_item.get("importance_score", 50.0)),
            int(candidate_item.get("evidence_count", 1)),
            0,
            str(candidate_item.get("public_id", "")),
        )

        if score_existing >= score_candidate:
            return existing_item, candidate_item
        return candidate_item, existing_item

    @classmethod
    def evaluate_candidate(
        cls,
        *,
        candidate_text: str,
        candidate_category: str,
        candidate_purpose: str,
        participant_scope_key: str,
        candidate_metadata: dict[str, Any] | None = None,
        existing_candidates: list[dict[str, Any]],
        candidate_embedding: np.ndarray | None = None,
    ) -> DuplicateMatchResult:
        """Evaluates a new memory candidate against existing active memories in scope."""
        # 1. G8 Secret Sanitization
        sanitized_cand = sanitize_message(raw_text=candidate_text)["sanitized_text"]
        normalized_cand = normalize_memory_value(candidate_category, sanitized_cand)["normalized_value"]

        cand_meta = candidate_metadata or {}
        cand_evidence = int(cand_meta.get("evidence_count", 1))

        # Filter strictly by participant scope, category, and purpose (Scope Isolation G5)
        scoped_items = [
            item for item in existing_candidates
            if str(item.get("participant_scope_key", "")) == participant_scope_key
            and str(item.get("category", "")).lower() == candidate_category.lower()
            and str(item.get("purpose", "")).lower() == candidate_purpose.lower()
        ][:MAX_CANDIDATES]

        if not scoped_items:
            return DuplicateMatchResult(
                classification=DuplicateClassification.DISTINCT,
                canonical_item=None,
                conflicting_item=None,
                similarity_score=0.0,
                decision_reason="no_scoped_candidates_found",
                review_required=False,
                evidence_count_delta=cand_evidence,
            )

        # 2. Stage A: Exact Match
        for item in scoped_items:
            raw_val = str(item.get("display_value", "")).strip()
            if raw_val == sanitized_cand.strip():
                canonical, _ = cls.select_canonical_memory(item, cand_meta)
                return DuplicateMatchResult(
                    classification=DuplicateClassification.EXACT_DUPLICATE,
                    canonical_item=canonical,
                    conflicting_item=None,
                    similarity_score=1.0,
                    decision_reason="exact_text_match",
                    review_required=False,
                    evidence_count_delta=cand_evidence,
                    provenance_metadata={"match_type": "exact", "target_public_id": canonical.get("public_id")},
                )

        # 3. Stage B: Normalized Match
        collapsed_cand = " ".join(sanitized_cand.lower().split()).rstrip(".")
        for item in scoped_items:
            norm_val = str(item.get("normalized_value", "")).strip()
            raw_val = str(item.get("display_value", "")).strip().lower()
            collapsed_raw = " ".join(raw_val.split()).rstrip(".")
            if (
                norm_val == normalized_cand
                or norm_val.lower() == normalized_cand.lower()
                or collapsed_raw == collapsed_cand
                or " ".join(norm_val.lower().split()).rstrip(".") == collapsed_cand
            ):
                canonical, _ = cls.select_canonical_memory(item, cand_meta)
                return DuplicateMatchResult(
                    classification=DuplicateClassification.NORMALIZED_DUPLICATE,
                    canonical_item=canonical,
                    conflicting_item=None,
                    similarity_score=0.99,
                    decision_reason="normalized_text_match",
                    review_required=False,
                    evidence_count_delta=cand_evidence,
                    provenance_metadata={"match_type": "normalized", "target_public_id": canonical.get("public_id")},
                )

        # 4. Stage C: Scoped Semantic Match via Local 64-Dim Embedding
        if candidate_embedding is None:
            embed_res = compute_embedding(
                sanitized_cand, provider_type=EMBEDDING_PROVIDER, dimensions=EMBEDDING_DIMENSIONS
            )
            cand_vec = embed_res["vector"]
        else:
            cand_vec = candidate_embedding

        # Collect candidate vectors
        valid_vectors = []
        valid_items = []
        for item in scoped_items:
            vec = item.get("vector")
            if vec is None and item.get("vector_blob"):
                try:
                    vec = unpack_vector(item["vector_blob"], dimensions=EMBEDDING_DIMENSIONS)
                except Exception:
                    vec = None
            if vec is None and item.get("display_value"):
                # Compute on the fly if not cached
                vec = compute_embedding(
                    str(item["display_value"]), provider_type=EMBEDDING_PROVIDER, dimensions=EMBEDDING_DIMENSIONS
                )["vector"]

            if vec is not None and isinstance(vec, np.ndarray) and vec.shape[0] == EMBEDDING_DIMENSIONS:
                valid_vectors.append(vec)
                valid_items.append(item)

        if not valid_vectors:
            return DuplicateMatchResult(
                classification=DuplicateClassification.DISTINCT,
                canonical_item=None,
                conflicting_item=None,
                similarity_score=0.0,
                decision_reason="no_valid_candidate_embeddings",
                review_required=False,
                evidence_count_delta=cand_evidence,
            )

        # Compute cosine similarity
        raw_scores = score_vectors(cand_vec, valid_vectors, distance_metric="cosine")
        best_idx = int(np.argmax(raw_scores))
        best_score = float(raw_scores[best_idx])
        best_item = valid_items[best_idx]
        best_text = str(best_item.get("display_value") or best_item.get("normalized_value") or "")

        # Check for parameter/numerical contradiction
        has_conflict = cls.has_predicate_contradiction(sanitized_cand, best_text)

        # Decision tree
        if best_score >= SEMANTIC_DUPLICATE_THRESHOLD:
            if has_conflict:
                return DuplicateMatchResult(
                    classification=DuplicateClassification.POSSIBLE_CONFLICT,
                    canonical_item=None,
                    conflicting_item=best_item,
                    similarity_score=round(best_score, 4),
                    decision_reason="high_similarity_with_parameter_contradiction",
                    review_required=True,
                    evidence_count_delta=cand_evidence,
                    provenance_metadata={"conflicting_public_id": best_item.get("public_id")},
                )

            # Governance check for SYSTEM / ADMIN categories
            is_system_or_admin = str(candidate_category).upper() in ("SYSTEM", "ADMIN")
            canonical, _ = cls.select_canonical_memory(best_item, cand_meta)
            return DuplicateMatchResult(
                classification=DuplicateClassification.SEMANTIC_DUPLICATE,
                canonical_item=canonical,
                conflicting_item=None,
                similarity_score=round(best_score, 4),
                decision_reason="semantic_similarity_exceeds_threshold",
                review_required=is_system_or_admin,
                evidence_count_delta=cand_evidence,
                provenance_metadata={
                    "similarity_score": round(best_score, 4),
                    "matched_canonical_public_id": canonical.get("public_id"),
                },
            )

        elif best_score >= RELATED_THRESHOLD:
            if has_conflict:
                return DuplicateMatchResult(
                    classification=DuplicateClassification.POSSIBLE_CONFLICT,
                    canonical_item=None,
                    conflicting_item=best_item,
                    similarity_score=round(best_score, 4),
                    decision_reason="related_topic_with_parameter_contradiction",
                    review_required=True,
                    evidence_count_delta=cand_evidence,
                    provenance_metadata={"conflicting_public_id": best_item.get("public_id")},
                )
            return DuplicateMatchResult(
                classification=DuplicateClassification.RELATED_BUT_DISTINCT,
                canonical_item=None,
                conflicting_item=best_item,
                similarity_score=round(best_score, 4),
                decision_reason="related_topic_distinct_fact",
                review_required=False,
                evidence_count_delta=cand_evidence,
            )

        return DuplicateMatchResult(
            classification=DuplicateClassification.DISTINCT,
            canonical_item=None,
            conflicting_item=None,
            similarity_score=round(best_score, 4),
            decision_reason="similarity_below_related_threshold",
            review_required=False,
            evidence_count_delta=cand_evidence,
        )

    @staticmethod
    def build_semantic_reinforcement_event(
        *,
        canonical_public_id: str,
        candidate_text: str,
        similarity_score: float,
        evidence_delta: int,
        new_total_evidence: int,
        admin_id: str,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Constructs an immutable, G8-sanitized SEMANTIC_REINFORCED audit event dictionary."""
        sanitized_sample = sanitize_message(raw_text=candidate_text[:120])["sanitized_text"]
        detail = {
            "event_type": "SEMANTIC_REINFORCED",
            "canonical_public_id": canonical_public_id,
            "similarity_score": round(similarity_score, 4),
            "evidence_count_delta": evidence_delta,
            "total_evidence_count": new_total_evidence,
            "sanitized_candidate_sample": sanitized_sample,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        }
        if trace_id:
            detail["trace_id"] = trace_id
        return detail
