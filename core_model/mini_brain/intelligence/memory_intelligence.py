"""Phase 17.3: Memory Intelligence Layer.

Implements structured, governed, and bounded intelligent memory:
1. Seven-Category Memory Taxonomy (EPISODIC, SEMANTIC, PROCEDURAL, TASK, PREFERENCE, SYSTEM, ADMIN)
2. Bounded Importance Scoring (0-100)
3. Calibrated Confidence Scoring (0-100)
4. Category-Aware Freshness & Decay Engine (FRESH, AGING, STALE, EXPIRED)
5. Access Frequency Tracking (UNUSED, RARELY_USED, OCCASIONALLY_USED, FREQUENTLY_USED)
6. Canonical Memory Reinforcement (evidence_count += 1 without row bloat)
7. Promotion / Demotion Lifecycle State Machine
8. Loss-Minimizing Structural Memory Compression
9. SYSTEM / ADMIN Elevated Governance & Candidate Isolation
10. Context-Aware Retrieval Ranking with Hard Budget Bounds (max 10 results, max 600 tokens)
11. Zero Secret Leakage (G8)
"""

from __future__ import annotations

import enum
import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core_model.conversation.memory_normalization import normalize_memory_value
from core_model.mini_brain.llm_runtime.message_sanitizer import sanitize_message
from core_model.mini_brain.llm_runtime.token_budget import estimate_tokens


class MemoryCategory(str, enum.Enum):
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    PROCEDURAL = "PROCEDURAL"
    TASK = "TASK"
    PREFERENCE = "PREFERENCE"
    SYSTEM = "SYSTEM"
    ADMIN = "ADMIN"


class FreshnessState(str, enum.Enum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


class AccessFrequency(str, enum.Enum):
    UNUSED = "UNUSED"
    RARELY_USED = "RARELY_USED"
    OCCASIONALLY_USED = "OCCASIONALLY_USED"
    FREQUENTLY_USED = "FREQUENTLY_USED"


class MemoryLifecycleState(str, enum.Enum):
    PROPOSED = "PROPOSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    QUARANTINED = "QUARANTINED"


# Default Category TTLs (in seconds)
CATEGORY_TTL_SECONDS: dict[MemoryCategory, int] = {
    MemoryCategory.TASK: 86_400,            # 1 day
    MemoryCategory.EPISODIC: 604_800,       # 7 days
    MemoryCategory.PROCEDURAL: 2_592_000,   # 30 days
    MemoryCategory.SEMANTIC: 7_776_000,     # 90 days
    MemoryCategory.PREFERENCE: 15_552_000,  # 180 days
    MemoryCategory.SYSTEM: 31_536_000,      # 365 days / long-lived
    MemoryCategory.ADMIN: 31_536_000,       # 365 days / long-lived
}

# Category Base Importance Weights (0-100)
CATEGORY_BASE_IMPORTANCE: dict[MemoryCategory, float] = {
    MemoryCategory.SYSTEM: 90.0,
    MemoryCategory.ADMIN: 85.0,
    MemoryCategory.PROCEDURAL: 80.0,
    MemoryCategory.SEMANTIC: 75.0,
    MemoryCategory.PREFERENCE: 70.0,
    MemoryCategory.TASK: 65.0,
    MemoryCategory.EPISODIC: 50.0,
}

# Source Base Confidence Weights (0-100)
SOURCE_BASE_CONFIDENCE: dict[str, float] = {
    "admin_created": 95.0,
    "user_confirmed": 95.0,
    "explicit_user_request": 90.0,
    "deterministically_extracted": 85.0,
    "system_derived": 75.0,
    "assistant_proposed": 60.0,
    "assistant_inferred": 55.0,
}

# Mapping legacy category strings to Intelligence 2.0 MemoryCategory
LEGACY_CATEGORY_MAP: dict[str, MemoryCategory] = {
    "language_preference": MemoryCategory.PREFERENCE,
    "format_preference": MemoryCategory.PREFERENCE,
    "project_preference": MemoryCategory.PREFERENCE,
    "confirmed_name_or_alias": MemoryCategory.SEMANTIC,
    "user_confirmed_fact": MemoryCategory.SEMANTIC,
    "learning_goal": MemoryCategory.EPISODIC,
    "conversation_follow_up": MemoryCategory.EPISODIC,
    "course_progress": MemoryCategory.PROCEDURAL,
    # Direct uppercase support
    "EPISODIC": MemoryCategory.EPISODIC,
    "SEMANTIC": MemoryCategory.SEMANTIC,
    "PROCEDURAL": MemoryCategory.PROCEDURAL,
    "TASK": MemoryCategory.TASK,
    "PREFERENCE": MemoryCategory.PREFERENCE,
    "SYSTEM": MemoryCategory.SYSTEM,
    "ADMIN": MemoryCategory.ADMIN,
}

MAX_MEMORY_RESULTS = 10
MAX_MEMORY_TOKENS = 600


@dataclass
class MemoryIntelligenceMetadata:
    importance_score: float = 50.0
    confidence_score: float = 50.0
    evidence_count: int = 1
    access_count: int = 0
    last_accessed_at: str = ""
    freshness_state: str = FreshnessState.FRESH.value
    lifecycle_state: str = MemoryLifecycleState.PROPOSED.value
    compression_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryIntelligenceEngine:
    """Pure domain intelligence layer for Brud Mini Brain memory."""

    @staticmethod
    def resolve_category(category_input: str | MemoryCategory) -> MemoryCategory:
        """Resolves input string or enum into a canonical MemoryCategory."""
        if isinstance(category_input, MemoryCategory):
            return category_input
        cat_str = str(category_input).strip()
        if cat_str in LEGACY_CATEGORY_MAP:
            return LEGACY_CATEGORY_MAP[cat_str]
        upper_cat = cat_str.upper()
        if upper_cat in MemoryCategory.__members__:
            return MemoryCategory[upper_cat]
        raise ValueError(f"Invalid or unsupported memory category: '{category_input}'")

    @staticmethod
    def compute_importance(
        category: MemoryCategory,
        *,
        access_count: int = 0,
        is_admin_confirmed: bool = False,
        task_relevance: float = 0.0,
    ) -> float:
        """Computes bounded importance score (0.0 to 100.0)."""
        base = CATEGORY_BASE_IMPORTANCE.get(category, 50.0)
        access_boost = min(10.0, access_count * 1.5)
        admin_boost = 10.0 if is_admin_confirmed else 0.0
        task_boost = min(15.0, task_relevance * 15.0)

        total = base + access_boost + admin_boost + task_boost
        return round(min(100.0, max(0.0, total)), 2)

    @staticmethod
    def compute_confidence(
        creation_source: str,
        *,
        evidence_count: int = 1,
        is_confirmed: bool = False,
    ) -> float:
        """Computes bounded confidence score (0.0 to 100.0).

        Note: Repeated evidence increases confidence, capped strictly at 100.0.
        Repetition alone does not bypass governance for SYSTEM/ADMIN categories.
        """
        base = SOURCE_BASE_CONFIDENCE.get(creation_source, 50.0)
        if is_confirmed:
            base = max(base, 95.0)

        # Repetition reinforcement boost (up to +15)
        reinforcement_boost = min(15.0, max(0, evidence_count - 1) * 2.0)
        total = base + reinforcement_boost
        return round(min(100.0, max(0.0, total)), 2)

    @staticmethod
    def evaluate_freshness(
        category: MemoryCategory,
        *,
        created_epoch: float,
        now_epoch: float | None = None,
        custom_ttl_seconds: int | None = None,
    ) -> FreshnessState:
        """Calculates category-aware freshness state."""
        now = now_epoch if now_epoch is not None else time.time()
        ttl = custom_ttl_seconds or CATEGORY_TTL_SECONDS.get(category, 7_776_000)
        age = max(0.0, now - created_epoch)

        if age < 0.25 * ttl:
            return FreshnessState.FRESH
        elif age < 0.75 * ttl:
            return FreshnessState.AGING
        elif age < 1.0 * ttl:
            return FreshnessState.STALE
        else:
            return FreshnessState.EXPIRED

    @staticmethod
    def classify_access_frequency(access_count: int) -> AccessFrequency:
        """Categorizes access frequency."""
        if access_count <= 0:
            return AccessFrequency.UNUSED
        elif access_count <= 2:
            return AccessFrequency.RARELY_USED
        elif access_count <= 5:
            return AccessFrequency.OCCASIONALLY_USED
        else:
            return AccessFrequency.FREQUENTLY_USED

    @staticmethod
    def evaluate_governance(
        category: MemoryCategory,
        *,
        creation_source: str,
        is_admin_approved: bool = False,
        safety_blocked: bool = False,
    ) -> MemoryLifecycleState:
        """Enforces governance boundaries for SYSTEM and ADMIN memory."""
        if safety_blocked:
            return MemoryLifecycleState.QUARANTINED

        # SYSTEM and ADMIN require explicit approval before becoming ACTIVE
        if category in (MemoryCategory.SYSTEM, MemoryCategory.ADMIN):
            if is_admin_approved:
                return MemoryLifecycleState.ACTIVE
            return MemoryLifecycleState.REVIEW_REQUIRED

        # Standard categories
        if creation_source in ("explicit_user_request", "user_confirmed", "admin_created"):
            return MemoryLifecycleState.ACTIVE
        return MemoryLifecycleState.PROPOSED

    @staticmethod
    def evaluate_promotion_demotion(
        current_state: MemoryLifecycleState,
        *,
        category: MemoryCategory,
        importance_score: float,
        confidence_score: float,
        freshness: FreshnessState,
        access_freq: AccessFrequency,
        is_admin_approved: bool = False,
    ) -> MemoryLifecycleState:
        """Evaluates promotion/demotion transitions."""
        # Sensitive governance overrides
        if category in (MemoryCategory.SYSTEM, MemoryCategory.ADMIN) and not is_admin_approved:
            return MemoryLifecycleState.REVIEW_REQUIRED

        if freshness == FreshnessState.EXPIRED:
            return MemoryLifecycleState.EXPIRED

        if freshness == FreshnessState.STALE and access_freq == AccessFrequency.UNUSED:
            return MemoryLifecycleState.ARCHIVED

        if importance_score >= 80.0 and confidence_score >= 80.0 and access_freq in (
            AccessFrequency.OCCASIONALLY_USED, AccessFrequency.FREQUENTLY_USED
        ):
            return MemoryLifecycleState.ACTIVE

        return current_state

    @staticmethod
    def check_canonical_match(
        proposed_normalized: str,
        existing_items: list[dict[str, Any]],
        category: MemoryCategory,
    ) -> dict[str, Any] | None:
        """Checks for exact or normalized canonical match within the same category."""
        target = proposed_normalized.strip().lower()
        for item in existing_items:
            item_cat = LEGACY_CATEGORY_MAP.get(str(item.get("category")), None)
            if item_cat == category:
                existing_norm = str(item.get("normalized_value", "")).strip().lower()
                if existing_norm == target:
                    return item
        return None

    @staticmethod
    def reinforce_canonical_memory(
        canonical_item: dict[str, Any],
        *,
        creation_source: str,
        now_epoch: float | None = None,
    ) -> dict[str, Any]:
        """Reinforces existing canonical memory without spawning duplicate rows."""
        now = now_epoch if now_epoch is not None else time.time()
        new_evidence_count = int(canonical_item.get("evidence_count", 1)) + 1
        new_confidence = MemoryIntelligenceEngine.compute_confidence(
            creation_source=creation_source,
            evidence_count=new_evidence_count,
            is_confirmed=canonical_item.get("status") == "active",
        )
        category = MemoryIntelligenceEngine.resolve_category(canonical_item.get("category", "SEMANTIC"))
        new_importance = MemoryIntelligenceEngine.compute_importance(
            category=category,
            access_count=int(canonical_item.get("access_count", 0)),
            is_admin_confirmed=canonical_item.get("status") == "active",
        )

        reinforced = dict(canonical_item)
        reinforced["evidence_count"] = new_evidence_count
        reinforced["confidence_score"] = new_confidence
        reinforced["importance_score"] = new_importance
        reinforced["last_accessed_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now))
        reinforced["freshness_state"] = FreshnessState.FRESH.value
        return reinforced

    @staticmethod
    def compress_observations(
        observations: list[dict[str, Any]],
        *,
        category: MemoryCategory,
        canonical_claim: str,
    ) -> dict[str, Any]:
        """Compresses multiple related observations into a single canonical record with full provenance."""
        if not observations:
            raise ValueError("observations list cannot be empty for compression")

        total_evidence = sum(int(o.get("evidence_count", 1)) for o in observations)
        source_refs = [o.get("public_id") or o.get("source_reference", "") for o in observations if o.get("public_id") or o.get("source_reference")]
        max_confidence = max((float(o.get("confidence_score", 50.0)) for o in observations), default=50.0)
        max_importance = max((float(o.get("importance_score", 50.0)) for o in observations), default=50.0)

        # Sanitization (G8)
        sanitized_claim = sanitize_message(raw_text=canonical_claim)["sanitized_text"]
        normalized = normalize_memory_value(category.value.lower(), sanitized_claim)

        compression_state = {
            "is_compressed": True,
            "source_observation_count": len(observations),
            "source_references": source_refs,
            "compressed_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "compression_method": "deterministic_structural",
        }

        return {
            "category": category.value,
            "display_value": sanitized_claim,
            "normalized_value": normalized["normalized_value"],
            "evidence_count": total_evidence,
            "confidence_score": min(100.0, max_confidence + 5.0),
            "importance_score": max_importance,
            "compression_state": compression_state,
        }

    @staticmethod
    def rank_memories_for_retrieval(
        candidates: list[dict[str, Any]],
        *,
        active_topic: str | None = None,
        active_task: str | None = None,
        max_results: int = MAX_MEMORY_RESULTS,
        max_tokens: int = MAX_MEMORY_TOKENS,
    ) -> list[dict[str, Any]]:
        """Context-aware memory ranking enforcing hard bounds (max 10 results, max 600 tokens)."""
        scored_candidates = []
        for cand in candidates:
            # Exclude revoked or quarantined memories
            status = cand.get("status", "")
            if status in ("revoked", "deleted", "quarantined", "rejected"):
                continue
            # Exclude unapproved SYSTEM / ADMIN memories
            cat_str = str(cand.get("category", "")).upper()
            if cat_str in ("SYSTEM", "ADMIN") and status != "active":
                continue

            content = str(cand.get("display_value") or cand.get("normalized_value") or "")
            content_lower = content.lower()

            # Base scores
            importance = float(cand.get("importance_score", 50.0))
            confidence = float(cand.get("confidence_score", 50.0))

            # Context boost from Phase 17.2
            topic_boost = 0.0
            if active_topic and active_topic.lower() in content_lower:
                topic_boost = 20.0

            task_boost = 0.0
            if active_task and active_task.lower() in content_lower:
                task_boost = 25.0

            # Freshness penalty
            freshness = cand.get("freshness_state", FreshnessState.FRESH.value)
            freshness_mod = 0.0
            if freshness == FreshnessState.STALE.value:
                freshness_mod = -15.0
            elif freshness == FreshnessState.EXPIRED.value:
                freshness_mod = -40.0

            final_rank_score = (0.4 * importance) + (0.3 * confidence) + topic_boost + task_boost + freshness_mod
            scored_candidates.append((cand, final_rank_score))

        # Sort descending by rank score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Apply hard token and result budget limits
        selected = []
        used_tokens = 0
        for cand, _ in scored_candidates:
            if len(selected) >= max_results:
                break
            text = str(cand.get("display_value") or cand.get("normalized_value") or "")
            tokens = estimate_tokens(text)
            if used_tokens + tokens <= max_tokens:
                selected.append(cand)
                used_tokens += tokens

        return selected
