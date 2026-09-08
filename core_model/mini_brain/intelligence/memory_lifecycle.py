"""Phase 17.7: Memory Lifecycle & Freshness Engine.

Implements structured, governed, deterministic, CPU-first memory lifecycle management:
1. Category-aware TTL evaluation & freshness classification (FRESH, AGING, STALE, EXPIRED)
2. Decoupled freshness vs truth validity (stale/old != false; historical preservation)
3. Deterministic freshness penalty calculation (FRESH=0, AGING=5, STALE=15, EXPIRED=40)
4. Anti-inflation reinforcement (read != evidence; verified duplicate observation resets freshness)
5. Non-destructive expiration and archival state machine
6. Strict category governance (TASK fast decay, EPISODIC/PROCEDURAL/SEMANTIC/PREFERENCE decay, SYSTEM/ADMIN G1 protected)
7. Dispute-aware protection gate (active disputes DETECTED, PENDING_REVIEW, UNDER_REVIEW block auto-expiration/archival)
8. Scope isolation & zero secret leakage (G5 & G8)
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from core_model.mini_brain.intelligence.conflict_detector import DisputeState
from core_model.mini_brain.intelligence.memory_intelligence import (
    CATEGORY_TTL_SECONDS,
    FreshnessState,
    LEGACY_CATEGORY_MAP,
    MemoryCategory,
    MemoryIntelligenceEngine,
    MemoryLifecycleState,
)

FRESHNESS_PENALTIES: dict[FreshnessState, float] = {
    FreshnessState.FRESH: 0.0,
    FreshnessState.AGING: 5.0,
    FreshnessState.STALE: 15.0,
    FreshnessState.EXPIRED: 40.0,
}

VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"active", "rejected", "awaiting_confirmation", "quarantined"},
    "awaiting_confirmation": {"active", "rejected", "quarantined"},
    "active": {"consolidated", "superseded", "expired", "archived", "deleted", "quarantined"},
    "consolidated": {"active", "superseded", "archived", "deleted"},
    "superseded": {"archived", "deleted", "active"},
    "expired": {"archived", "active", "deleted"},
    "archived": {"active", "deleted"},
    "rejected": {"deleted"},
    "revoked": {"deleted", "active"},
    "quarantined": {"rejected", "deleted", "active"},
    "deleted": set(),
}


@dataclass
class FreshnessEvaluationResult:
    memory_item_public_id: str
    category: str
    purpose: str
    age_seconds: float
    ttl_seconds: int
    freshness_state: str
    freshness_penalty: float
    importance_score: float
    confidence_score: float
    effective_rank_score: float
    is_expired: bool
    is_archived: bool
    is_stale: bool
    is_disputed: bool
    requires_human_governance: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryLifecycleEngine:
    """Pure domain engine for memory freshness evaluation, decay, and lifecycle governance."""

    @staticmethod
    def parse_timestamp_to_epoch(ts: str | float | int | None) -> float:
        """Parses ISO/SQL timestamp string or epoch integer to float UTC epoch."""
        if ts is None or ts == "":
            return time.time()
        if isinstance(ts, (int, float)):
            return float(ts)
        ts_str = str(ts).strip()
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(ts_str, fmt)
                return dt.timestamp()
            except ValueError:
                continue
        try:
            return float(ts_str)
        except ValueError:
            return time.time()

    @staticmethod
    def resolve_category(category_input: str | MemoryCategory) -> MemoryCategory:
        """Resolves input string or enum into a canonical MemoryCategory."""
        return MemoryIntelligenceEngine.resolve_category(category_input)

    @classmethod
    def get_category_ttl(
        cls, category_input: str | MemoryCategory, custom_ttl_seconds: int | None = None
    ) -> int:
        """Returns the TTL in seconds for a category."""
        if custom_ttl_seconds and custom_ttl_seconds > 0:
            return custom_ttl_seconds
        cat = cls.resolve_category(category_input)
        return CATEGORY_TTL_SECONDS.get(cat, 7_776_000)

    @staticmethod
    def compute_memory_age(created_epoch: float, now_epoch: float | None = None) -> float:
        """Computes memory age in seconds; handles future-dated timestamps gracefully."""
        now = now_epoch if now_epoch is not None else time.time()
        return max(0.0, now - created_epoch)

    @classmethod
    def determine_freshness_state(
        cls,
        category: str | MemoryCategory,
        age_seconds: float,
        *,
        custom_ttl_seconds: int | None = None,
    ) -> FreshnessState:
        """Determines the freshness state using approved threshold boundaries:
        - Age < 0.25 * TTL: FRESH
        - 0.25 * TTL <= Age < 0.75 * TTL: AGING
        - 0.75 * TTL <= Age < 1.0 * TTL: STALE
        - Age >= 1.0 * TTL: EXPIRED
        """
        cat = cls.resolve_category(category)
        # SYSTEM and ADMIN memories do not undergo autonomous freshness decay
        if cat in (MemoryCategory.SYSTEM, MemoryCategory.ADMIN):
            return FreshnessState.FRESH

        ttl = cls.get_category_ttl(cat, custom_ttl_seconds)
        if age_seconds < 0.25 * ttl:
            return FreshnessState.FRESH
        elif age_seconds < 0.75 * ttl:
            return FreshnessState.AGING
        elif age_seconds < 1.0 * ttl:
            return FreshnessState.STALE
        else:
            return FreshnessState.EXPIRED

    @staticmethod
    def compute_freshness_penalty(freshness: FreshnessState | str) -> float:
        """Computes deterministic freshness penalty: FRESH=0, AGING=5, STALE=15, EXPIRED=40."""
        if isinstance(freshness, str):
            try:
                freshness = FreshnessState(freshness.upper())
            except ValueError:
                freshness = FreshnessState.FRESH
        return FRESHNESS_PENALTIES.get(freshness, 0.0)

    @classmethod
    def compute_effective_rank(
        cls,
        *,
        importance_score: float,
        confidence_score: float,
        freshness: FreshnessState | str,
        topic_delta: float = 0.0,
        task_delta: float = 0.0,
    ) -> float:
        """Computes bounded effective rank score with freshness penalty."""
        penalty = cls.compute_freshness_penalty(freshness)
        raw_score = (0.4 * importance_score) + (0.3 * confidence_score) + topic_delta + task_delta - penalty
        if raw_score != raw_score or raw_score in (float("inf"), float("-inf")):
            return 0.0
        return round(max(0.0, min(100.0, raw_score)), 2)

    @classmethod
    def is_expiration_eligible(
        cls,
        *,
        category: str | MemoryCategory,
        age_seconds: float,
        status: str = "active",
        is_disputed: bool = False,
        custom_ttl_seconds: int | None = None,
    ) -> bool:
        """Determines if a memory is eligible for autonomous expiration."""
        if status != "active":
            return False
        if is_disputed:
            return False

        cat = cls.resolve_category(category)
        if cat in (MemoryCategory.SYSTEM, MemoryCategory.ADMIN):
            return False

        ttl = cls.get_category_ttl(cat, custom_ttl_seconds)
        return age_seconds >= 1.0 * ttl

    @classmethod
    def is_archival_eligible(
        cls,
        *,
        category: str | MemoryCategory,
        age_seconds: float,
        status: str = "active",
        is_disputed: bool = False,
        custom_ttl_seconds: int | None = None,
    ) -> bool:
        """Determines if a memory is eligible for archival transition."""
        if is_disputed:
            return False

        cat = cls.resolve_category(category)
        if cat in (MemoryCategory.SYSTEM, MemoryCategory.ADMIN):
            return False

        if status in ("expired", "superseded"):
            return True

        ttl = cls.get_category_ttl(cat, custom_ttl_seconds)
        # TASK is archived after 2 days (2.0 * TTL); other categories after 1.5 * TTL
        mult = 2.0 if cat == MemoryCategory.TASK else 1.5
        return status == "active" and age_seconds >= mult * ttl

    @classmethod
    def validate_lifecycle_transition(
        cls,
        *,
        current_status: str,
        target_status: str,
        category: str | MemoryCategory,
        is_admin_authorized: bool = False,
        is_disputed: bool = False,
    ) -> tuple[bool, str]:
        """Validates if a requested status transition is allowed under governance rules."""
        curr = current_status.lower()
        target = target_status.lower()

        allowed_targets = VALID_STATUS_TRANSITIONS.get(curr, set())
        if target not in allowed_targets:
            return False, f"invalid_transition_from_{curr}_to_{target}"

        cat = cls.resolve_category(category)

        # G1 Governance: SYSTEM / ADMIN require explicit admin authorization
        if cat in (MemoryCategory.SYSTEM, MemoryCategory.ADMIN) and not is_admin_authorized:
            if target in ("expired", "archived", "deleted", "superseded", "revoked"):
                return False, "system_admin_requires_admin_authorization"

        # Dispute Gate: Disputed memories cannot be auto-expired or archived
        if is_disputed and not is_admin_authorized:
            if target in ("expired", "archived", "deleted"):
                return False, "disputed_memory_cannot_be_auto_expired_or_archived"

        return True, "transition_allowed"

    @classmethod
    def evaluate_freshness(
        cls,
        item: dict[str, Any],
        *,
        now_epoch: float | None = None,
        custom_ttl_seconds: int | None = None,
        active_disputes: list[dict[str, Any]] | None = None,
    ) -> FreshnessEvaluationResult:
        """Evaluates memory item freshness, decay, and operational ranking."""
        now = now_epoch if now_epoch is not None else time.time()
        pub_id = str(item.get("public_id", ""))
        cat_str = str(item.get("category", "SEMANTIC"))
        purpose = str(item.get("purpose", ""))
        status = str(item.get("status", "active")).lower()

        created_epoch = cls.parse_timestamp_to_epoch(item.get("created_at"))
        age_seconds = cls.compute_memory_age(created_epoch, now)

        cat = cls.resolve_category(cat_str)
        ttl = cls.get_category_ttl(cat, custom_ttl_seconds)

        freshness = cls.determine_freshness_state(cat, age_seconds, custom_ttl_seconds=ttl)
        penalty = cls.compute_freshness_penalty(freshness)

        importance = float(item.get("importance_score", 50.0))
        confidence = float(item.get("confidence_score", 50.0))
        effective_rank = cls.compute_effective_rank(
            importance_score=importance,
            confidence_score=confidence,
            freshness=freshness,
        )

        # Dispute check
        is_disp = False
        if active_disputes:
            for disp in active_disputes:
                disp_state = disp.get("state")
                if disp_state in (
                    DisputeState.DETECTED.value,
                    DisputeState.PENDING_REVIEW.value,
                    DisputeState.UNDER_REVIEW.value,
                    "DETECTED",
                    "PENDING_REVIEW",
                    "UNDER_REVIEW",
                ):
                    if str(disp.get("memory_a_id")) == pub_id or str(disp.get("memory_b_id")) == pub_id:
                        is_disp = True
                        break

        is_expired = status == "expired" or freshness == FreshnessState.EXPIRED
        is_archived = status == "archived"
        is_stale = freshness in (FreshnessState.STALE, FreshnessState.EXPIRED)
        requires_gov = cat in (MemoryCategory.SYSTEM, MemoryCategory.ADMIN)

        return FreshnessEvaluationResult(
            memory_item_public_id=pub_id,
            category=cat.value,
            purpose=purpose,
            age_seconds=round(age_seconds, 2),
            ttl_seconds=ttl,
            freshness_state=freshness.value,
            freshness_penalty=penalty,
            importance_score=importance,
            confidence_score=confidence,
            effective_rank_score=effective_rank,
            is_expired=is_expired,
            is_archived=is_archived,
            is_stale=is_stale,
            is_disputed=is_disp,
            requires_human_governance=requires_gov,
            metadata={
                "created_epoch": created_epoch,
                "now_epoch": now,
                "status": status,
            },
        )
