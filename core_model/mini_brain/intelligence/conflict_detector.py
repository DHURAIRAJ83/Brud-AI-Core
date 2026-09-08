"""Phase 17.5: Conflict Detection & Resolution Layer.

Implements deterministic memory conflict detection, multi-factor confidence scoring,
structured dispute lifecycle management, supervised human resolution, and retrieval annotations:
1. 6-Class Conflict Taxonomy (VALUE, NUMERIC, STATE, TEMPORAL, POLICY, VERSION)
2. Bounded Conflict Confidence Scoring (0–100)
3. Structured DisputeRecord Representation with G8 Secret Sanitization
4. Deterministic 5-State Dispute Lifecycle State Machine (DETECTED -> PENDING_REVIEW -> UNDER_REVIEW -> RESOLVED / DISMISSED)
5. Supervised Human Resolution Strategies (SUPERSEDE_EXISTING, RETAIN_EXISTING, RETAIN_BOTH_COEXIST, DISMISS)
6. Conflict-Aware Retrieval Warnings ([DISPUTED_WARNING])
7. G1 Advisory-Only Invariant Enforcement (Zero Autonomous Overwriting)
8. G5 Participant/Tenant Scope Isolation (Max 20 Candidates)
9. Immutable Event Ledger Logging (CONFLICT_DETECTED, DISPUTE_RESOLVED, etc.)
"""

from __future__ import annotations

import enum
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

import numpy as np

from core_model.conversation.memory_normalization import normalize_memory_value
from core_model.mini_brain.llm_runtime.message_sanitizer import sanitize_message
from core_model.rag.embedding import compute_embedding, unpack_vector
from core_model.rag.vector_index import score_vectors


class ConflictClassification(str, enum.Enum):
    VALUE_CONFLICT = "VALUE_CONFLICT"
    NUMERIC_CONFLICT = "NUMERIC_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    POLICY_CONFLICT = "POLICY_CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"


class DisputeState(str, enum.Enum):
    DETECTED = "DETECTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ResolutionStrategy(str, enum.Enum):
    SUPERSEDE_EXISTING = "SUPERSEDE_EXISTING"
    RETAIN_EXISTING = "RETAIN_EXISTING"
    RETAIN_BOTH_COEXIST = "RETAIN_BOTH_COEXIST"
    DISMISS = "DISMISS"


VALID_STATE_TRANSITIONS: dict[DisputeState, set[DisputeState]] = {
    DisputeState.DETECTED: {DisputeState.PENDING_REVIEW, DisputeState.DISMISSED},
    DisputeState.PENDING_REVIEW: {DisputeState.UNDER_REVIEW, DisputeState.DISMISSED},
    DisputeState.UNDER_REVIEW: {DisputeState.RESOLVED, DisputeState.DISMISSED, DisputeState.PENDING_REVIEW},
    DisputeState.RESOLVED: set(),  # Terminal state
    DisputeState.DISMISSED: set(),  # Terminal state
}


@dataclass(frozen=True)
class DisputeRecord:
    dispute_id: str
    participant_scope_key: str
    category: str
    purpose: str
    memory_a_id: str  # Existing memory public_id
    memory_b_id: str  # Proposed candidate memory public_id or placeholder
    existing_value: str
    candidate_value: str
    conflict_classification: ConflictClassification
    conflict_confidence: float  # Bounded 0.0 - 100.0
    evidence_summary: dict[str, Any]
    detection_reason: str
    detected_at: str
    state: DisputeState = DisputeState.PENDING_REVIEW
    resolution_strategy: ResolutionStrategy | None = None
    resolved_by: str | None = None
    resolved_at: str | None = None
    resolution_reason: str | None = None
    provenance_references: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["conflict_classification"] = self.conflict_classification.value
        data["state"] = self.state.value
        if self.resolution_strategy:
            data["resolution_strategy"] = self.resolution_strategy.value
        return data


@dataclass
class ConflictMatchResult:
    has_conflict: bool
    classification: ConflictClassification | None
    conflict_confidence: float  # 0.0 - 100.0
    conflicting_item: dict[str, Any] | None
    dispute_record: DisputeRecord | None
    decision_reason: str
    review_required: bool
    provenance_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        if self.classification:
            res["classification"] = self.classification.value
        if self.dispute_record:
            res["dispute_record"] = self.dispute_record.to_dict()
        return res


MAX_CANDIDATES = 20
EMBEDDING_DIMENSIONS = 64
EMBEDDING_PROVIDER = "local_custom_embedding"

# Polarity state pairs (affirmative vs negative / operational flags)
OPPOSING_STATE_PAIRS = [
    (r"\benabled\b", r"\bdisabled\b"),
    (r"\bactive\b", r"\binactive\b"),
    (r"\ballowed\b", r"\bforbidden\b|\bprohibited\b|\bblocked\b"),
    (r"\bon\b", r"\boff\b"),
    (r"\btrue\b", r"\bfalse\b"),
    (r"\byes\b", r"\bno\b"),
    (r"\bvalid\b", r"\binvalid\b"),
    (r"\bopen\b", r"\bclosed\b"),
    (r"\bstarted\b", r"\bstopped\b"),
    (r"\bsuccess\b", r"\bfailure\b|\bfailed\b"),
]

# Temporal indicators
TEMPORAL_KEYWORDS = [
    "every", "daily", "hourly", "weekly", "monthly", "interval",
    "schedule", "cron", "seconds", "minutes", "hours", "days"
]

# Policy indicators
POLICY_KEYWORDS = [
    "policy", "rule", "require", "mandatory", "permission", "consent",
    "retention", "compliance", "restriction", "allow", "disallow"
]

# Version indicators
VERSION_PATTERN = re.compile(r"\b(?:v\d+(?:\.\d+)*|version\s*\d+(?:\.\d+)*|phase\s*\d+(?:\.\d+)*)\b", re.IGNORECASE)


class ConflictConfidence:
    """Computes bounded conflict confidence scores (0.0 to 100.0)."""

    @staticmethod
    def calculate(
        *,
        semantic_similarity: float,
        subject_match: bool,
        predicate_match: bool,
        value_incompatibility: float,  # 0.0 to 1.0
        polarity_opposition: bool,
        numeric_contradiction: bool,
        temporal_contradiction: bool,
        version_mismatch: bool,
    ) -> float:
        """Calculates bounded conflict confidence (0.0 to 100.0).

        Note: Represents confidence that a conflict exists, NOT truth of either claim.
        """
        score = 0.0

        # Base semantic & structural alignment (needs high similarity to be comparing the same subject)
        if semantic_similarity >= 0.85:
            score += 30.0
        elif semantic_similarity >= 0.65:
            score += 15.0

        if subject_match:
            score += 25.0

        if predicate_match:
            score += 20.0

        # Specific contradiction signals
        if polarity_opposition:
            score += 25.0

        if numeric_contradiction:
            score += 25.0

        if temporal_contradiction:
            score += 20.0

        if value_incompatibility > 0.0:
            score += (value_incompatibility * 20.0)

        # Version mismatch reduces conflict confidence if they refer to separate versions
        if version_mismatch:
            score = min(score, 60.0)

        # Bound strictly to [0.0, 100.0]
        return round(float(np.clip(score, 0.0, 100.0)), 2)


class ConflictKnowledgeEngine:
    """Pure domain engine for conflict detection, classification, and dispute governance."""

    @staticmethod
    def extract_numbers_and_units(text: str) -> set[tuple[str, str]]:
        """Extracts (scalar, unit) pairs from text."""
        matches = re.findall(
            r"\b(\d+(?:\.\d+)?)\s*(hours|hour|days|day|mins|minutes|seconds|sec|%|gb|mb|kb|tb|tokens|tok|ms|s)?\b",
            text.lower(),
        )
        results = set()
        for num, unit in matches:
            norm_unit = unit.rstrip("s") if unit else ""
            results.add((num, norm_unit))
        return results

    @staticmethod
    def detect_polarity_opposition(text_a: str, text_b: str) -> bool:
        """Detects if two statements have directly opposing polarity or state terms."""
        a_low = text_a.lower()
        b_low = text_b.lower()
        for pos_pat, neg_pat in OPPOSING_STATE_PAIRS:
            if (re.search(pos_pat, a_low) and re.search(neg_pat, b_low)) or (
                re.search(neg_pat, a_low) and re.search(pos_pat, b_low)
            ):
                return True
        return False

    @staticmethod
    def extract_version_tags(text: str) -> set[str]:
        """Extracts version identifiers."""
        matches = VERSION_PATTERN.findall(text.lower())
        return set(m.strip() for m in matches)

    @classmethod
    def classify_contradiction(
        cls,
        text_a: str,
        text_b: str,
        *,
        similarity: float,
    ) -> tuple[ConflictClassification | None, float, str]:
        """Classifies the contradiction type and returns (ConflictClassification, confidence, reason)."""
        # 0. Property & Attribute Compatibility Check
        props_a = {w for w in ["retention", "interval", "schedule", "runs", "port", "timeout", "limit", "cap", "window", "threshold", "size", "count"] if w in text_a.lower()}
        props_b = {w for w in ["retention", "interval", "schedule", "runs", "port", "timeout", "limit", "cap", "window", "threshold", "size", "count"] if w in text_b.lower()}
        if props_a and props_b and not (props_a & props_b):
            # Differing property attributes (e.g., schedule vs retention) -> RELATED_BUT_DISTINCT, not a conflict
            return None, 0.0, "distinct_property_attributes"

        # 1. Version Detection
        vers_a = cls.extract_version_tags(text_a)
        vers_b = cls.extract_version_tags(text_b)
        has_version_mismatch = bool(vers_a and vers_b and vers_a != vers_b)

        # 2. Polarity / State Opposition
        has_polarity = cls.detect_polarity_opposition(text_a, text_b)

        # 3. Numeric & Parameter Contradictions
        nums_a = cls.extract_numbers_and_units(text_a)
        nums_b = cls.extract_numbers_and_units(text_b)
        has_numeric = bool(nums_a and nums_b and nums_a != nums_b)

        # 4. Temporal Keyword Check
        is_temporal = any(k in text_a.lower() or k in text_b.lower() for k in TEMPORAL_KEYWORDS)
        # 5. Policy Keyword Check
        is_policy = any(k in text_a.lower() or k in text_b.lower() for k in POLICY_KEYWORDS)

        # Subject / Predicate heuristic overlap
        words_a = set(re.findall(r"\b\w{3,}\b", text_a.lower()))
        words_b = set(re.findall(r"\b\w{3,}\b", text_b.lower()))
        common_words = words_a & words_b
        subject_match = len(common_words) >= 2 or similarity >= 0.70
        predicate_match = len(common_words) >= 1

        if has_version_mismatch:
            conf = ConflictConfidence.calculate(
                semantic_similarity=similarity,
                subject_match=subject_match,
                predicate_match=predicate_match,
                value_incompatibility=0.8,
                polarity_opposition=has_polarity,
                numeric_contradiction=has_numeric,
                temporal_contradiction=is_temporal and has_numeric,
                version_mismatch=True,
            )
            return ConflictClassification.VERSION_CONFLICT, conf, "version_specific_specification_mismatch"

        if has_polarity:
            conf = ConflictConfidence.calculate(
                semantic_similarity=similarity,
                subject_match=subject_match,
                predicate_match=predicate_match,
                value_incompatibility=1.0,
                polarity_opposition=True,
                numeric_contradiction=False,
                temporal_contradiction=False,
                version_mismatch=False,
            )
            return ConflictClassification.STATE_CONFLICT, conf, "opposing_operational_or_boolean_state"

        if has_numeric and is_temporal:
            conf = ConflictConfidence.calculate(
                semantic_similarity=similarity,
                subject_match=subject_match,
                predicate_match=predicate_match,
                value_incompatibility=1.0,
                polarity_opposition=False,
                numeric_contradiction=True,
                temporal_contradiction=True,
                version_mismatch=False,
            )
            return ConflictClassification.TEMPORAL_CONFLICT, conf, "incompatible_temporal_schedule_or_interval"

        if has_numeric:
            conf = ConflictConfidence.calculate(
                semantic_similarity=similarity,
                subject_match=subject_match,
                predicate_match=predicate_match,
                value_incompatibility=1.0,
                polarity_opposition=False,
                numeric_contradiction=True,
                temporal_contradiction=False,
                version_mismatch=False,
            )
            return ConflictClassification.NUMERIC_CONFLICT, conf, "contradictory_scalar_measurement_or_quantity"

        if is_policy and similarity >= 0.75:
            conf = ConflictConfidence.calculate(
                semantic_similarity=similarity,
                subject_match=subject_match,
                predicate_match=predicate_match,
                value_incompatibility=0.8,
                polarity_opposition=False,
                numeric_contradiction=False,
                temporal_contradiction=False,
                version_mismatch=False,
            )
            return ConflictClassification.POLICY_CONFLICT, conf, "incompatible_administrative_policy_rule"

        # General qualitative value conflict
        INCOMPATIBLE_PAIRS = [
            ("dark", "light"),
            ("enabled", "disabled"),
            ("active", "inactive"),
            ("true", "false"),
            ("yes", "no"),
            ("allow", "deny"),
            ("block", "permit"),
            ("primary", "secondary"),
            ("json", "xml"),
            ("yaml", "toml"),
            ("python", "rust"),
            ("postgres", "mysql"),
            ("postgres", "sqlite"),
            ("postgresql", "sqlite"),
            ("postgresql", "mysql"),
            ("mongodb", "postgresql"),
            ("redis", "memcached"),
            ("nginx", "apache"),
            ("react", "vue"),
            ("react", "angular"),
            ("fast", "slow"),
            ("high", "low"),
            ("minimum", "maximum"),
        ]
        has_incompatible_option = False
        words_a_low = {w.lower() for w in words_a}
        words_b_low = {w.lower() for w in words_b}
        for opt1, opt2 in INCOMPATIBLE_PAIRS:
            if (opt1 in words_a_low and opt2 in words_b_low) or (opt2 in words_a_low and opt1 in words_b_low):
                has_incompatible_option = True
                break

        if has_incompatible_option and (similarity >= 0.60 or subject_match):
            conf = ConflictConfidence.calculate(
                semantic_similarity=similarity,
                subject_match=subject_match,
                predicate_match=predicate_match,
                value_incompatibility=0.8,
                polarity_opposition=False,
                numeric_contradiction=False,
                temporal_contradiction=False,
                version_mismatch=False,
            )
            return ConflictClassification.VALUE_CONFLICT, conf, "incompatible_qualitative_attribute_value"

        return None, 0.0, "no_contradiction_detected"

    @classmethod
    def evaluate_conflict(
        cls,
        *,
        candidate_text: str,
        candidate_category: str,
        candidate_purpose: str,
        participant_scope_key: str,
        candidate_public_id: str | None = None,
        existing_candidates: list[dict[str, Any]],
        candidate_embedding: np.ndarray | None = None,
    ) -> ConflictMatchResult:
        """Evaluates whether candidate conflicts with any existing active memory in scope."""
        # 1. G8 Sanitization
        sanitized_cand = sanitize_message(raw_text=candidate_text)["sanitized_text"]

        # Filter candidates strictly by participant scope, category, and purpose (G5 Isolation)
        scoped_items = [
            item for item in existing_candidates
            if str(item.get("participant_scope_key", "")) == participant_scope_key
            and str(item.get("category", "")).lower() == candidate_category.lower()
            and str(item.get("purpose", "")).lower() == candidate_purpose.lower()
        ][:MAX_CANDIDATES]

        if not scoped_items:
            return ConflictMatchResult(
                has_conflict=False,
                classification=None,
                conflict_confidence=0.0,
                conflicting_item=None,
                dispute_record=None,
                decision_reason="no_scoped_candidates_found",
                review_required=False,
            )

        # 2. Embeddings & Cosine Scoring
        if candidate_embedding is None:
            cand_vec = compute_embedding(
                sanitized_cand, provider_type=EMBEDDING_PROVIDER, dimensions=EMBEDDING_DIMENSIONS
            )["vector"]
        else:
            cand_vec = candidate_embedding

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
                vec = compute_embedding(
                    str(item["display_value"]), provider_type=EMBEDDING_PROVIDER, dimensions=EMBEDDING_DIMENSIONS
                )["vector"]
            if vec is not None and isinstance(vec, np.ndarray) and vec.shape[0] == EMBEDDING_DIMENSIONS:
                valid_vectors.append(vec)
                valid_items.append(item)

        if not valid_vectors:
            return ConflictMatchResult(
                has_conflict=False,
                classification=None,
                conflict_confidence=0.0,
                conflicting_item=None,
                dispute_record=None,
                decision_reason="no_valid_candidate_vectors",
                review_required=False,
            )

        raw_scores = score_vectors(cand_vec, valid_vectors, distance_metric="cosine")
        best_idx = int(np.argmax(raw_scores))
        best_score = float(raw_scores[best_idx])
        best_item = valid_items[best_idx]
        best_text = str(best_item.get("display_value") or best_item.get("normalized_value") or "")

        # 3. Classify contradiction
        classification, confidence, reason = cls.classify_contradiction(
            sanitized_cand, best_text, similarity=best_score
        )

        if classification is not None and confidence >= 50.0:
            dispute_id = f"disp_{uuid4().hex[:12]}"
            dispute = DisputeRecord(
                dispute_id=dispute_id,
                participant_scope_key=participant_scope_key,
                category=candidate_category,
                purpose=candidate_purpose,
                memory_a_id=str(best_item.get("public_id", "")),
                memory_b_id=str(candidate_public_id or "pending_candidate"),
                existing_value=best_text,
                candidate_value=sanitized_cand,
                conflict_classification=classification,
                conflict_confidence=confidence,
                evidence_summary={
                    "similarity_score": round(best_score, 4),
                    "existing_evidence": int(best_item.get("evidence_count", 1)),
                    "candidate_evidence": 1,
                },
                detection_reason=reason,
                detected_at=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                state=DisputeState.PENDING_REVIEW,
                provenance_references={
                    "existing_memory_id": best_item.get("public_id"),
                    "category": candidate_category,
                    "purpose": candidate_purpose,
                },
            )
            return ConflictMatchResult(
                has_conflict=True,
                classification=classification,
                conflict_confidence=confidence,
                conflicting_item=best_item,
                dispute_record=dispute,
                decision_reason=reason,
                review_required=True,
                provenance_metadata={"dispute_id": dispute_id, "similarity_score": round(best_score, 4)},
            )

        return ConflictMatchResult(
            has_conflict=False,
            classification=None,
            conflict_confidence=0.0,
            conflicting_item=None,
            dispute_record=None,
            decision_reason="no_conflict_above_confidence_threshold",
            review_required=False,
        )

    @staticmethod
    def validate_state_transition(current_state: DisputeState, target_state: DisputeState) -> bool:
        """Validates state transitions in the dispute state machine."""
        allowed = VALID_STATE_TRANSITIONS.get(current_state, set())
        return target_state in allowed

    @staticmethod
    def format_retrieval_dispute_warning(dispute: DisputeRecord | dict[str, Any]) -> str:
        """Generates a truthful, honest [DISPUTED_WARNING] annotation for memory context."""
        if isinstance(dispute, dict):
            c_type = dispute.get("conflict_classification", "VALUE_CONFLICT")
            reason = dispute.get("detection_reason", "competing claims detected")
        else:
            c_type = dispute.conflict_classification.value
            reason = dispute.detection_reason

        return (
            f"[DISPUTED_WARNING: {c_type}]\n"
            f"Note: This memory is subject to an unresolved dispute ({reason}). "
            "Human administrative review has not established an authoritative resolution. "
            "Do not assert this statement as undisputed truth."
        )
