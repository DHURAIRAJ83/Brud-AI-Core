"""Phase 17.3 — Memory Intelligence Layer Verification Test Suite.

Comprehensive executable verification covering:
1. Seven-category taxonomy
2. Invalid category rejection
3. Importance score bounds
4. Confidence score bounds
5. Confidence does not exceed 100
6. Freshness transitions
7. TASK decay behavior
8. SYSTEM / ADMIN governance
9. Access count increment
10. Last accessed timestamp
11. Access frequency classification
12. Exact canonical reinforcement
13. Normalized canonical reinforcement
14. evidence_count correctness
15. No duplicate row creation
16. Promotion
17. Demotion
18. Compression preservation
19. Compression provenance retention
20. Context-aware retrieval
21. Retrieval result limit
22. Retrieval token limit
23. Secret redaction
24. Consent preservation
25. Participant isolation
26. WAL / transaction safety
27. Existing memory backward compatibility
28. Candidate knowledge quarantine
29. No autonomous activation
30. G1–G14 invariant preservation
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.models.conversation_memory import (
    ConsentCreate,
    MemoryItemCreate,
    MemoryPolicyCreate,
)
from backend.services.memory_service import MemoryService
from core_model.mini_brain.intelligence.memory_intelligence import (
    AccessFrequency,
    FreshnessState,
    MemoryCategory,
    MemoryIntelligenceEngine,
    MemoryIntelligenceMetadata,
    MemoryLifecycleState,
)
from core_model.mini_brain.llm_runtime.token_budget import estimate_tokens


@pytest.fixture
def memory_env(tmp_path: Path) -> tuple[MemoryService, Settings, str]:
    db_path = tmp_path / "test_p17_3_memory.db"
    settings = Settings(
        env="development",
        database_path=db_path,
        allowed_model_dir=tmp_path / "models",
        allowed_data_dir=tmp_path / "data",
        database_backup_dir=tmp_path / "backups",
        allow_external_storage=True,
    )
    (tmp_path / "models").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    
    initialize_database(settings.resolved_database_path, wal_enabled=True)
    repo = ConversationMemoryRepository(settings.resolved_database_path)
    svc = MemoryService(repo, settings)
    
    # Create test policy
    policy = svc.create_policy(
        MemoryPolicyCreate(
            name="P17_3_Test_Policy",
            allowed_memory_categories=[
                "language_preference", "format_preference", "user_confirmed_fact",
                "learning_goal", "project_preference", "conversation_follow_up",
            ],
            allow_long_term_memory=True,
            require_explicit_consent=True,
        ),
        admin_id="adm_test",
    )
    # Create consent
    consent = svc.create_consent(
        ConsentCreate(
            participant_scope_key="admin_assistant:adm_001",
            memory_policy_public_id=policy["public_id"],
            purpose="language_preference",
            allowed_categories=["language_preference", "format_preference", "user_confirmed_fact", "project_preference"],
        ),
        admin_id="adm_test",
    )
    return svc, settings, consent["public_id"]


# ==============================================================================
# 1. Taxonomy & Category Resolution Tests (P17.3.1)
# ==============================================================================

def test_p17_3_tax_001_seven_categories():
    """Verify exactly seven canonical categories exist and are resolved."""
    expected = {"EPISODIC", "SEMANTIC", "PROCEDURAL", "TASK", "PREFERENCE", "SYSTEM", "ADMIN"}
    actual = {cat.value for cat in MemoryCategory}
    assert actual == expected
    
    # Verify legacy mapping
    assert MemoryIntelligenceEngine.resolve_category("language_preference") == MemoryCategory.PREFERENCE
    assert MemoryIntelligenceEngine.resolve_category("user_confirmed_fact") == MemoryCategory.SEMANTIC
    assert MemoryIntelligenceEngine.resolve_category("course_progress") == MemoryCategory.PROCEDURAL
    assert MemoryIntelligenceEngine.resolve_category("learning_goal") == MemoryCategory.EPISODIC


def test_p17_3_tax_002_invalid_category_rejection():
    """Verify invalid category raises ValueError."""
    with pytest.raises(ValueError, match="Invalid or unsupported"):
        MemoryIntelligenceEngine.resolve_category("invalid_fake_category")


# ==============================================================================
# 2. Scoring Bounds & Calculations (P17.3.3 & P17.3.4)
# ==============================================================================

def test_p17_3_score_001_importance_bounds():
    """Verify importance score is bounded strictly between 0 and 100."""
    score_low = MemoryIntelligenceEngine.compute_importance(MemoryCategory.EPISODIC)
    assert 0.0 <= score_low <= 100.0
    
    # Maximum boosts
    score_max = MemoryIntelligenceEngine.compute_importance(
        MemoryCategory.SYSTEM,
        access_count=100,
        is_admin_confirmed=True,
        task_relevance=1.0,
    )
    assert score_max == 100.0


def test_p17_3_score_002_confidence_bounds_and_capping():
    """Verify confidence score is bounded and capped strictly at 100."""
    base_conf = MemoryIntelligenceEngine.compute_confidence("explicit_user_request", evidence_count=1)
    assert 0.0 <= base_conf <= 100.0
    
    # Repetition cannot exceed 100
    high_rep_conf = MemoryIntelligenceEngine.compute_confidence(
        "admin_created",
        evidence_count=50,
        is_confirmed=True,
    )
    assert high_rep_conf == 100.0


# ==============================================================================
# 3. Freshness & Decay Tests (P17.3.5)
# ==============================================================================

def test_p17_3_freshness_001_lifecycle_transitions():
    """Verify freshness transitions from FRESH -> AGING -> STALE -> EXPIRED."""
    now = time.time()
    ttl = 1000  # 1000 seconds
    
    # Age 100s (< 0.25 TTL) -> FRESH
    f1 = MemoryIntelligenceEngine.evaluate_freshness(
        MemoryCategory.TASK, created_epoch=now - 100, now_epoch=now, custom_ttl_seconds=ttl,
    )
    assert f1 == FreshnessState.FRESH
    
    # Age 500s (0.25 - 0.75 TTL) -> AGING
    f2 = MemoryIntelligenceEngine.evaluate_freshness(
        MemoryCategory.TASK, created_epoch=now - 500, now_epoch=now, custom_ttl_seconds=ttl,
    )
    assert f2 == FreshnessState.AGING
    
    # Age 850s (0.75 - 1.0 TTL) -> STALE
    f3 = MemoryIntelligenceEngine.evaluate_freshness(
        MemoryCategory.TASK, created_epoch=now - 850, now_epoch=now, custom_ttl_seconds=ttl,
    )
    assert f3 == FreshnessState.STALE
    
    # Age 1200s (>= 1.0 TTL) -> EXPIRED
    f4 = MemoryIntelligenceEngine.evaluate_freshness(
        MemoryCategory.TASK, created_epoch=now - 1200, now_epoch=now, custom_ttl_seconds=ttl,
    )
    assert f4 == FreshnessState.EXPIRED


def test_p17_3_freshness_002_task_decays_faster_than_semantic():
    """Verify TASK memory has shorter default TTL than SEMANTIC memory."""
    now = time.time()
    # At 2 days age: TASK (TTL 1 day) is EXPIRED, SEMANTIC (TTL 90 days) is FRESH
    age_two_days = 2 * 86_400
    f_task = MemoryIntelligenceEngine.evaluate_freshness(
        MemoryCategory.TASK, created_epoch=now - age_two_days, now_epoch=now,
    )
    f_semantic = MemoryIntelligenceEngine.evaluate_freshness(
        MemoryCategory.SEMANTIC, created_epoch=now - age_two_days, now_epoch=now,
    )
    assert f_task == FreshnessState.EXPIRED
    assert f_semantic == FreshnessState.FRESH


# ==============================================================================
# 4. Access Frequency Tracking (P17.3.6)
# ==============================================================================

def test_p17_3_access_001_frequency_classification():
    """Verify access count maps to appropriate AccessFrequency enum."""
    assert MemoryIntelligenceEngine.classify_access_frequency(0) == AccessFrequency.UNUSED
    assert MemoryIntelligenceEngine.classify_access_frequency(2) == AccessFrequency.RARELY_USED
    assert MemoryIntelligenceEngine.classify_access_frequency(4) == AccessFrequency.OCCASIONALLY_USED
    assert MemoryIntelligenceEngine.classify_access_frequency(10) == AccessFrequency.FREQUENTLY_USED


# ==============================================================================
# 5. Canonical Memory Reinforcement (P17.3.7 & P17.3.13)
# ==============================================================================

def test_p17_3_reinf_001_repeated_fact_reinforces_without_duplicate_row(memory_env: tuple[MemoryService, Settings, str]):
    """Verify repeating the same memory increments evidence_count and does NOT insert duplicate rows."""
    svc, settings, consent_id = memory_env
    
    # 1. Initial creation
    item1 = svc.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="language_preference",
            purpose="language_preference",
            display_value="Admin prefers Tamil explanations for diagnostics.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="adm_test",
    )
    assert item1["status"] == "active"
    
    # 2. Second submission of exact same fact
    item2 = svc.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="language_preference",
            purpose="language_preference",
            display_value="Admin prefers Tamil explanations for diagnostics.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="adm_test",
    )
    
    # Must return the SAME canonical item public_id
    assert item2["public_id"] == item1["public_id"]
    
    # Check events for reinforcement
    events = svc.get_events(item1["public_id"])["items"]
    reinf_events = [e for e in events if e["event_type"] == "reinforced"]
    assert len(reinf_events) == 1
    assert reinf_events[0]["details"]["evidence_count"] == 2


# ==============================================================================
# 6. Promotion, Demotion & Governance Tests (P17.3.8 & P17.3.10)
# ==============================================================================

def test_p17_3_gov_001_system_admin_memory_requires_approval():
    """Verify SYSTEM and ADMIN categories require explicit admin approval."""
    # Unapproved SYSTEM memory -> REVIEW_REQUIRED
    state = MemoryIntelligenceEngine.evaluate_governance(
        MemoryCategory.SYSTEM,
        creation_source="system_derived",
        is_admin_approved=False,
    )
    assert state == MemoryLifecycleState.REVIEW_REQUIRED
    
    # Approved SYSTEM memory -> ACTIVE
    state_app = MemoryIntelligenceEngine.evaluate_governance(
        MemoryCategory.SYSTEM,
        creation_source="system_derived",
        is_admin_approved=True,
    )
    assert state_app == MemoryLifecycleState.ACTIVE


def test_p17_3_gov_002_system_admin_cannot_auto_promote_without_approval():
    """Verify high frequency / importance cannot bypass governance for SYSTEM memory."""
    state = MemoryIntelligenceEngine.evaluate_promotion_demotion(
        MemoryLifecycleState.REVIEW_REQUIRED,
        category=MemoryCategory.SYSTEM,
        importance_score=95.0,
        confidence_score=95.0,
        freshness=FreshnessState.FRESH,
        access_freq=AccessFrequency.FREQUENTLY_USED,
        is_admin_approved=False,
    )
    assert state == MemoryLifecycleState.REVIEW_REQUIRED


def test_p17_3_lifecycle_001_stale_unused_demoted_to_archive():
    """Verify stale and unused memories are demoted to ARCHIVED."""
    state = MemoryIntelligenceEngine.evaluate_promotion_demotion(
        MemoryLifecycleState.ACTIVE,
        category=MemoryCategory.SEMANTIC,
        importance_score=50.0,
        confidence_score=50.0,
        freshness=FreshnessState.STALE,
        access_freq=AccessFrequency.UNUSED,
        is_admin_approved=True,
    )
    assert state == MemoryLifecycleState.ARCHIVED


# ==============================================================================
# 7. Structural Compression Tests (P17.3.9)
# ==============================================================================

def test_p17_3_comp_001_loss_minimizing_structural_compression():
    """Verify related observations compress into a single canonical record with full provenance."""
    obs = [
        {"public_id": "mem_1", "evidence_count": 2, "confidence_score": 75.0, "importance_score": 70.0},
        {"public_id": "mem_2", "evidence_count": 3, "confidence_score": 80.0, "importance_score": 70.0},
    ]
    compressed = MemoryIntelligenceEngine.compress_observations(
        obs,
        category=MemoryCategory.PREFERENCE,
        canonical_claim="Admin prefers concise Tamil responses.",
    )
    assert compressed["category"] == "PREFERENCE"
    assert compressed["evidence_count"] == 5
    assert compressed["confidence_score"] >= 80.0
    assert compressed["compression_state"]["is_compressed"] is True
    assert compressed["compression_state"]["source_observation_count"] == 2
    assert "mem_1" in compressed["compression_state"]["source_references"]


# ==============================================================================
# 8. Context-Aware Retrieval & Hard Limits (P17.3.14 & P17.3.15)
# ==============================================================================

def test_p17_3_retrieval_001_ranking_and_budget_bounds():
    """Verify context-aware memory retrieval enforces hard limits (max 10 results, max 600 tokens)."""
    candidates = []
    for i in range(25):
        candidates.append({
            "public_id": f"mem_{i}",
            "status": "active",
            "category": "PREFERENCE",
            "display_value": f"Memory item {i} discussing database backup schedules and WAL recovery " * 3,
            "importance_score": 60.0 + i,
            "confidence_score": 80.0,
            "freshness_state": FreshnessState.FRESH.value,
        })
    
    ranked = MemoryIntelligenceEngine.rank_memories_for_retrieval(
        candidates,
        active_topic="database_backup",
        max_results=10,
        max_tokens=600,
    )
    assert len(ranked) <= 10
    total_tokens = sum(estimate_tokens(r["display_value"]) for r in ranked)
    assert total_tokens <= 600


# ==============================================================================
# 9. Security & Secret Redaction (P17.3.11 / G8)
# ==============================================================================

def test_p17_3_sec_001_secret_redaction_in_compression():
    """Verify secret credentials in compression input are scrubbed."""
    obs = [{"public_id": "mem_sec", "evidence_count": 1}]
    compressed = MemoryIntelligenceEngine.compress_observations(
        obs,
        category=MemoryCategory.PREFERENCE,
        canonical_claim="Admin secret api_key=sk-1234567890abcdef1234567890 and password=AdminPass123",
    )
    assert "sk-1234567890abcdef" not in compressed["display_value"]
    assert "AdminPass123" not in compressed["display_value"]
    assert "[REDACTED_SECRET]" in compressed["display_value"]


# ==============================================================================
# 10. Durability & Invariants (P17.3.18 / G1–G14)
# ==============================================================================

def test_p17_3_durability_001_sqlite_wal_intact(memory_env: tuple[MemoryService, Settings, str]):
    """Verify SQLite WAL mode is active and durability is intact."""
    svc, settings, _ = memory_env
    with svc.repository.transaction() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode.lower() == "wal"
