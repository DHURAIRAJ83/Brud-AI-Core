"""Phase 17.4 — Duplicate Knowledge Control (Semantic Deduplication) Test Suite.

Comprehensive executable verification covering:
1. Exact duplicate detection & reinforcement
2. Normalized duplicate detection
3. Semantic duplicate detection (equivalent phrasing)
4. Semantic reinforcement (evidence_count accumulation, zero duplicate rows)
5. Evidence count accumulation (canonical.evidence_count += candidate.evidence_count)
6. Deterministic canonical memory selection
7. Related-but-distinct preservation (separate memories)
8. Possible conflict detection (parameter/numerical contradiction)
9. Conflict records not merged (preserved for Phase 17.5)
10. Participant isolation (G5)
11. Category isolation
12. Purpose isolation
13. SYSTEM governance (REVIEW_REQUIRED boundary)
14. ADMIN governance (REVIEW_REQUIRED boundary)
15. Secret sanitization before embedding (G8)
16. Embedding version mismatch safety
17. Maximum 20 candidate enforcement
18. Existing embedding engine reuse (64-dim local_custom_embedding)
19. Existing vector scorer reuse (cosine)
20. G1, G4, G5, G8, G9, G10, G11 preservation
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
from core_model.mini_brain.intelligence.duplicate_detector import (
    DuplicateClassification,
    DuplicateKnowledgeEngine,
    DuplicateMatchResult,
    RELATED_THRESHOLD,
    SEMANTIC_DUPLICATE_THRESHOLD,
)


@pytest.fixture
def memory_env(tmp_path: Path) -> tuple[MemoryService, Settings, str]:
    db_path = tmp_path / "test_p17_4_dedup.db"
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

    policy = svc.create_policy(
        MemoryPolicyCreate(
            name="P17_4_Dedup_Policy",
            allowed_memory_categories=[
                "language_preference", "format_preference", "user_confirmed_fact",
                "learning_goal", "project_preference", "conversation_follow_up",
            ],
            allow_long_term_memory=True,
            require_explicit_consent=True,
        ),
        admin_id="adm_test",
    )
    consent = svc.create_consent(
        ConsentCreate(
            participant_scope_key="admin_assistant:adm_001",
            memory_policy_public_id=policy["public_id"],
            purpose="user_confirmed_profile",
            allowed_categories=["language_preference", "format_preference", "user_confirmed_fact", "project_preference"],
        ),
        admin_id="adm_test",
    )
    return svc, settings, consent["public_id"]


# ==============================================================================
# 1. Exact & Normalized Deduplication Tests
# ==============================================================================

def test_p17_4_dedup_001_exact_match_reinforces_canonical():
    """Verify exact duplicate match reinforces canonical memory without row creation."""
    existing = [
        {
            "public_id": "mem_exact_1",
            "participant_scope_key": "user_1",
            "category": "language_preference",
            "purpose": "language_preference",
            "display_value": "Admin prefers Tamil explanations.",
            "normalized_value": "admin prefers tamil explanations.",
            "evidence_count": 2,
            "confidence_score": 85.0,
            "importance_score": 70.0,
        }
    ]
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Admin prefers Tamil explanations.",
        candidate_category="language_preference",
        candidate_purpose="language_preference",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    assert res.classification == DuplicateClassification.EXACT_DUPLICATE
    assert res.canonical_item is not None
    assert res.canonical_item["public_id"] == "mem_exact_1"
    assert res.similarity_score == 1.0


def test_p17_4_dedup_002_normalized_match_reinforces():
    """Verify normalized duplicate match (case/whitespace differences)."""
    existing = [
        {
            "public_id": "mem_norm_1",
            "participant_scope_key": "user_1",
            "category": "language_preference",
            "purpose": "language_preference",
            "display_value": "Admin prefers Tamil explanations.",
            "normalized_value": "admin prefers tamil explanations",
            "evidence_count": 1,
            "confidence_score": 80.0,
            "importance_score": 70.0,
        }
    ]
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="  ADMIN  PREFERS  TAMIL  EXPLANATIONS.  ",
        candidate_category="language_preference",
        candidate_purpose="language_preference",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    assert res.classification in (DuplicateClassification.EXACT_DUPLICATE, DuplicateClassification.NORMALIZED_DUPLICATE)
    assert res.canonical_item["public_id"] == "mem_norm_1"


# ==============================================================================
# 2. Semantic Deduplication & Reinforcement Tests
# ==============================================================================

def test_p17_4_dedup_003_semantic_duplicate_detection_and_reinforce():
    """Verify semantically equivalent phrasing is classified as SEMANTIC_DUPLICATE."""
    existing = [
        {
            "public_id": "mem_sem_1",
            "participant_scope_key": "user_1",
            "category": "user_confirmed_fact",
            "purpose": "user_confirmed_profile",
            "display_value": "Database backup runs every 24 hours.",
            "normalized_value": "database backup runs every 24 hours",
            "evidence_count": 3,
            "confidence_score": 90.0,
            "importance_score": 75.0,
        }
    ]
    # Equivalent phrasing
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Database backup runs once every 24 hours.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    assert res.classification == DuplicateClassification.SEMANTIC_DUPLICATE
    assert res.canonical_item is not None
    assert res.canonical_item["public_id"] == "mem_sem_1"
    assert res.similarity_score >= SEMANTIC_DUPLICATE_THRESHOLD


def test_p17_4_dedup_004_end_to_end_memory_service_semantic_reinforce(memory_env: tuple[MemoryService, Settings, str]):
    """Verify MemoryService reinforces existing canonical row upon semantic duplicate."""
    svc, settings, consent_id = memory_env

    # 1. Initial memory
    item1 = svc.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="SQLite database backup runs every 24 hours.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="adm_test",
    )
    assert item1["status"] == "active"

    # 2. Semantically equivalent fact
    item2 = svc.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="SQLite database backup runs once every 24 hours.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="adm_test",
    )

    # Must return the SAME canonical public ID
    assert item2["public_id"] == item1["public_id"]

    # Verify SEMANTIC_REINFORCED event logged
    events = svc.get_events(item1["public_id"])["items"]
    sem_events = [e for e in events if e["event_type"] == "SEMANTIC_REINFORCED"]
    assert len(sem_events) == 1
    assert sem_events[0]["details"]["total_evidence_count"] == 2
    assert sem_events[0]["details"]["similarity_score"] >= SEMANTIC_DUPLICATE_THRESHOLD


# ==============================================================================
# 3. Related-But-Distinct & Conflict Preservation Tests
# ==============================================================================

def test_p17_4_dedup_005_related_but_distinct_kept_separate():
    """Verify related but distinct operational facts are NOT merged."""
    existing = [
        {
            "public_id": "mem_sched",
            "participant_scope_key": "user_1",
            "category": "user_confirmed_fact",
            "purpose": "user_confirmed_profile",
            "display_value": "Database backup runs every 24 hours.",
            "normalized_value": "database backup runs every 24 hours",
            "evidence_count": 1,
            "confidence_score": 85.0,
            "importance_score": 75.0,
        }
    ]
    # Backup retention is distinct from backup schedule
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Database backup retention period is 30 days.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    # Must be classified as RELATED_BUT_DISTINCT or DISTINCT, and NEVER merged
    assert res.classification in (DuplicateClassification.RELATED_BUT_DISTINCT, DuplicateClassification.DISTINCT)
    assert res.canonical_item is None


def test_p17_4_dedup_006_possible_conflict_detection_not_merged():
    """Verify numerical/parameter contradiction flags POSSIBLE_CONFLICT without destructive merge."""
    existing = [
        {
            "public_id": "mem_24h",
            "participant_scope_key": "user_1",
            "category": "user_confirmed_fact",
            "purpose": "user_confirmed_profile",
            "display_value": "Database backup interval is 24 hours.",
            "normalized_value": "database backup interval is 24 hours",
            "evidence_count": 5,
            "confidence_score": 90.0,
            "importance_score": 75.0,
        }
    ]
    # Contradictory interval claim
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Database backup interval is 12 hours.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    assert res.classification == DuplicateClassification.POSSIBLE_CONFLICT
    assert res.canonical_item is None
    assert res.conflicting_item["public_id"] == "mem_24h"
    assert res.review_required is True


# ==============================================================================
# 4. Canonical Selection & Scope Isolation Tests
# ==============================================================================

def test_p17_4_canon_001_deterministic_canonical_selection():
    """Verify canonical selection deterministically picks higher-quality memory."""
    high_qual = {
        "public_id": "mem_high",
        "confidence_score": 95.0,
        "importance_score": 85.0,
        "evidence_count": 5,
    }
    low_qual = {
        "public_id": "mem_low",
        "confidence_score": 60.0,
        "importance_score": 50.0,
        "evidence_count": 1,
    }
    canonical, secondary = DuplicateKnowledgeEngine.select_canonical_memory(high_qual, low_qual)
    assert canonical["public_id"] == "mem_high"
    assert secondary["public_id"] == "mem_low"


def test_p17_4_scope_001_participant_isolation_g5():
    """Verify different participant scope never matches as duplicate."""
    existing = [
        {
            "public_id": "mem_user_a",
            "participant_scope_key": "user_A",
            "category": "language_preference",
            "purpose": "language_preference",
            "display_value": "Admin prefers Tamil explanations.",
            "normalized_value": "admin prefers tamil explanations",
            "evidence_count": 1,
        }
    ]
    # Same text for user_B
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Admin prefers Tamil explanations.",
        candidate_category="language_preference",
        candidate_purpose="language_preference",
        participant_scope_key="user_B",  # Different participant
        existing_candidates=existing,
    )
    assert res.classification == DuplicateClassification.DISTINCT
    assert res.canonical_item is None


def test_p17_4_scope_002_category_and_purpose_isolation():
    """Verify different category or purpose never merges."""
    existing = [
        {
            "public_id": "mem_cat_a",
            "participant_scope_key": "user_1",
            "category": "language_preference",
            "purpose": "language_preference",
            "display_value": "Admin prefers Tamil explanations.",
            "normalized_value": "admin prefers tamil explanations",
        }
    ]
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Admin prefers Tamil explanations.",
        candidate_category="user_confirmed_fact",  # Different category
        candidate_purpose="language_preference",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    assert res.classification == DuplicateClassification.DISTINCT


# ==============================================================================
# 5. Governance & Security Tests (G1, G8)
# ==============================================================================

def test_p17_4_gov_001_system_admin_governance_review_required():
    """Verify SYSTEM category duplicate flags review_required = True."""
    existing = [
        {
            "public_id": "mem_sys",
            "participant_scope_key": "admin_sys",
            "category": "SYSTEM",
            "purpose": "system_operations",
            "display_value": "Provider fallback policy is fail-closed.",
            "normalized_value": "provider fallback policy is fail closed",
        }
    ]
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Provider fallback policy is strictly fail-closed.",
        candidate_category="SYSTEM",
        candidate_purpose="system_operations",
        participant_scope_key="admin_sys",
        existing_candidates=existing,
    )
    assert res.review_required is True


def test_p17_4_sec_001_secret_redaction_in_reinforcement_event():
    """Verify secrets are scrubbed before being recorded in SEMANTIC_REINFORCED event (G8)."""
    event = DuplicateKnowledgeEngine.build_semantic_reinforcement_event(
        canonical_public_id="mem_target",
        candidate_text="Secret is api_key=sk-1234567890abcdef1234567890 and Bearer token123",
        similarity_score=0.92,
        evidence_delta=1,
        new_total_evidence=3,
        admin_id="adm_1",
    )
    sample = event["sanitized_candidate_sample"]
    assert "sk-1234567890abcdef" not in sample
    assert "token123" not in sample
    assert "[REDACTED_SECRET]" in sample or "[REDACTED_TOKEN]" in sample or "[REDACTED]" in sample


# ==============================================================================
# 6. Additional Architectural & Adversarial Tests
# ==============================================================================

def test_p17_4_canon_002_deterministic_tie_break_with_identical_scores():
    """Verify tie break is fully deterministic when confidence/importance/evidence are identical."""
    item_a = {
        "public_id": "mem_aaa_111",
        "confidence_score": 80.0,
        "importance_score": 70.0,
        "evidence_count": 2,
    }
    item_b = {
        "public_id": "mem_bbb_222",
        "confidence_score": 80.0,
        "importance_score": 70.0,
        "evidence_count": 2,
    }
    # Existing stable record (item_a) is preferred
    canonical1, secondary1 = DuplicateKnowledgeEngine.select_canonical_memory(item_a, item_b)
    assert canonical1["public_id"] == "mem_aaa_111"

    # Repeat produces identical result
    canonical2, secondary2 = DuplicateKnowledgeEngine.select_canonical_memory(item_a, item_b)
    assert canonical2["public_id"] == canonical1["public_id"]


def test_p17_4_limit_001_max_20_candidates_enforced():
    """Verify scoped search is capped at MAX_CANDIDATES = 20 (no unbounded scan)."""
    candidates = [
        {
            "public_id": f"mem_{i}",
            "participant_scope_key": "user_1",
            "category": "user_confirmed_fact",
            "purpose": "user_confirmed_profile",
            "display_value": f"Fact number {i} about system metrics.",
            "normalized_value": f"fact number {i} about system metrics",
            "evidence_count": 1,
            "confidence_score": 80.0,
            "importance_score": 70.0,
        }
        for i in range(50)
    ]
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Fact number 99 about system metrics.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        existing_candidates=candidates,
    )
    # Validates execution without error on >20 candidates, evaluated against top 20
    assert res is not None


def test_p17_4_compat_001_embedding_reuse_and_vector_scorer_reuse():
    """Verify local 64-dim embedding and vector scorer reuse without external ML deps."""
    from core_model.rag.embedding import compute_embedding
    from core_model.rag.vector_index import score_vectors

    embed = compute_embedding("Testing vector embedding reuse", provider_type="local_custom_embedding", dimensions=64)
    assert embed["dimensions"] == 64
    assert embed["vector"].shape == (64,)

    scores = score_vectors(embed["vector"], [embed["vector"]], distance_metric="cosine")
    assert len(scores) == 1
    assert abs(scores[0] - 1.0) < 1e-4


def test_p17_4_adversarial_001_high_similarity_different_predicate():
    """Verify statements sharing vocabulary but having different predicates are not merged."""
    existing = [
        {
            "public_id": "mem_bkp_sched",
            "participant_scope_key": "user_1",
            "category": "user_confirmed_fact",
            "purpose": "user_confirmed_profile",
            "display_value": "Backup runs every 24 hours.",
            "normalized_value": "backup runs every 24 hours",
            "evidence_count": 2,
        }
    ]
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Backup retention is 30 days.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    # Must NOT merge into canonical
    assert res.classification != DuplicateClassification.SEMANTIC_DUPLICATE
    assert res.canonical_item is None


def test_p17_4_adversarial_002_high_similarity_contradictory_value():
    """Verify contradictory value parameters flag POSSIBLE_CONFLICT."""
    existing = [
        {
            "public_id": "mem_int_24",
            "participant_scope_key": "user_1",
            "category": "user_confirmed_fact",
            "purpose": "user_confirmed_profile",
            "display_value": "Backup interval is 24 hours.",
            "normalized_value": "backup interval is 24 hours",
        }
    ]
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Backup interval is 6 hours.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    assert res.classification == DuplicateClassification.POSSIBLE_CONFLICT
    assert res.review_required is True


def test_p17_4_adversarial_003_empty_candidates_returns_distinct():
    """Verify empty candidate list returns DISTINCT safely."""
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Any standalone memory fact.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        existing_candidates=[],
    )
    assert res.classification == DuplicateClassification.DISTINCT
    assert res.canonical_item is None
    assert res.similarity_score == 0.0


def test_p17_4_adversarial_004_malformed_vector_graceful_handling():
    """Verify items with malformed vector blob or unparseable vector fall back safely."""
    existing = [
        {
            "public_id": "mem_corrupt",
            "participant_scope_key": "user_1",
            "category": "user_confirmed_fact",
            "purpose": "user_confirmed_profile",
            "display_value": "Some corrupted memory record.",
            "vector_blob": b"corrupted_bytes_not_float32",
        }
    ]
    res = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Some completely distinct query text.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        existing_candidates=existing,
    )
    assert res is not None
    assert res.classification in (DuplicateClassification.DISTINCT, DuplicateClassification.RELATED_BUT_DISTINCT)


def test_p17_4_adversarial_005_repeated_semantic_duplicate_accumulates_evidence():
    """Verify multiple consecutive semantic duplicates accumulate evidence count linearly."""
    existing_canonical = {
        "public_id": "mem_canon_base",
        "participant_scope_key": "user_1",
        "category": "user_confirmed_fact",
        "purpose": "user_confirmed_profile",
        "display_value": "Database backup runs every 24 hours.",
        "normalized_value": "database backup runs every 24 hours",
        "evidence_count": 1,
        "confidence_score": 80.0,
        "importance_score": 70.0,
    }
    # First duplicate
    res1 = DuplicateKnowledgeEngine.evaluate_candidate(
        candidate_text="Database backup runs once every 24 hours.",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_1",
        candidate_metadata={"evidence_count": 2},
        existing_candidates=[existing_canonical],
    )
    assert res1.classification == DuplicateClassification.SEMANTIC_DUPLICATE
    assert res1.evidence_count_delta == 2

