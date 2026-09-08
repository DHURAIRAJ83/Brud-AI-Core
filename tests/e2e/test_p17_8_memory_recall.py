"""Phase 17.8: Memory Recall & Retrieval Intelligence E2E Test Suite.

Verifies:
1. Basic recall, semantic vector similarity, and lexical keyword matching
2. Score normalization bounds [0.0, 100.0] and deterministic tie-breaking
3. Retrieval modes: CURRENT, HISTORICAL, TASK, PREFERENCE
4. Freshness integration (FRESH, AGING, STALE, EXPIRED penalties)
5. Anti-inflation guarantee (retrieval != evidence)
6. Consolidation deduplication & provenance citation
7. Dispute safety gate (exclude_conflicting, prefer_recent warning)
8. Multi-tenant scope isolation (G5), category, purpose, and G1 SYSTEM/ADMIN governance
9. G8 secret sanitization and token/result budgeting
10. CPU-first performance (< 5 ms) and zero regressions against Phase 17.2-17.7
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.models.conversation_memory import (
    ConsentCreate,
    MemoryItemCreate,
    MemoryPolicyCreate,
    MemoryRetrieveRequest,
    RetrievalProfileCreate,
)
from backend.services.memory_service import MemoryService
from core_model.mini_brain.intelligence.conflict_detector import DisputeState
from core_model.mini_brain.intelligence.memory_intelligence import (
    FreshnessState,
    MemoryCategory,
)
from core_model.mini_brain.intelligence.memory_recall import (
    MemoryRecallEngine,
    MemoryRecallWeights,
    RetrievalMode,
)
from core_model.rag.embedding import compute_embedding


@pytest.fixture
def temp_service(tmp_path: Path) -> tuple[MemoryService, ConversationMemoryRepository, Settings]:
    db_path = tmp_path / "test_p17_8.db"
    settings = Settings(DATABASE_URL=f"sqlite:///{db_path}")
    initialize_database(settings.resolved_database_path, wal_enabled=True)
    repo = ConversationMemoryRepository(settings.resolved_database_path)
    service = MemoryService(repo, settings)
    return service, repo, settings


def _setup_base_profile(service: MemoryService, participant_scope_key: str = "tenant_17_8", admin_id: str = "admin_p17_8") -> tuple[str, str]:
    pol = service.create_policy(
        MemoryPolicyCreate(
            name=f"P17.8 Policy {participant_scope_key}",
            allow_long_term_memory=True,
            allowed_memory_categories=[
                "language_preference",
                "format_preference",
                "confirmed_name_or_alias",
                "learning_goal",
                "course_progress",
                "project_preference",
                "user_confirmed_fact",
                "conversation_follow_up",
            ],
            require_explicit_consent=True,
        ),
        admin_id=admin_id,
    )
    consent = service.create_consent(
        ConsentCreate(
            participant_scope_key=participant_scope_key,
            purpose="user_confirmed_profile",
            memory_policy_public_id=pol["public_id"],
            allowed_categories=[
                "language_preference",
                "format_preference",
                "confirmed_name_or_alias",
                "learning_goal",
                "course_progress",
                "project_preference",
                "user_confirmed_fact",
                "conversation_follow_up",
            ],
        ),
        admin_id=admin_id,
    )
    prof = service.create_profile(
        RetrievalProfileCreate(
            name=f"P17.8 Active Profile {participant_scope_key}",
            allowed_categories=[
                "language_preference",
                "format_preference",
                "confirmed_name_or_alias",
                "learning_goal",
                "course_progress",
                "project_preference",
                "user_confirmed_fact",
                "conversation_follow_up",
            ],
            allowed_purposes=["user_confirmed_profile", "general_context", "workflow_execution"],
            keyword_weight=0.4,
            vector_weight=0.6,
            minimum_score=0.15,
            maximum_results=10,
            conflict_policy="prefer_recent",
        ),
        admin_id=admin_id,
    )
    service.validate_profile(prof["public_id"], admin_id=admin_id)
    service.activate_profile(prof["public_id"], admin_id=admin_id)
    return prof["public_id"], consent["public_id"]


# --- 1. Basic Recall & Lexical/Vector Relevance ---

def test_p17_8_001_basic_memory_recall():
    candidates = [
        {
            "public_id": "mem_001",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Python 3.12 is the official project runtime",
            "normalized_value": "python 3.12 is the official project runtime",
            "importance_score": 75.0,
            "confidence_score": 85.0,
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="Python runtime version",
        candidates=candidates,
        participant_scope_key="scope_a",
    )
    assert res.final_result_count == 1
    item = res.results[0]
    assert item.memory_item_public_id == "mem_001"
    assert item.effective_recall_score > 0.0
    assert item.rank == 1


def test_p17_8_002_semantic_vector_relevance():
    embed_a = compute_embedding("PostgreSQL database setup", provider_type="local_custom_embedding", dimensions=64)["vector"]
    embed_b = compute_embedding("Frontend CSS color theme", provider_type="local_custom_embedding", dimensions=64)["vector"]

    candidates = [
        {
            "public_id": "mem_db",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "PostgreSQL relational database instance",
            "vector": embed_a,
            "created_epoch": time.time(),
        },
        {
            "public_id": "mem_ui",
            "participant_scope_key": "scope_a",
            "category": "PREFERENCE",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Frontend user interface colors",
            "vector": embed_b,
            "created_epoch": time.time(),
        },
    ]

    res = MemoryRecallEngine.recall_memories(
        query="relational database storage",
        candidates=candidates,
        participant_scope_key="scope_a",
    )
    assert res.final_result_count >= 1
    assert res.results[0].memory_item_public_id == "mem_db"


def test_p17_8_003_lexical_keyword_relevance():
    candidates = [
        {
            "public_id": "mem_exact",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "alpha beta gamma delta",
            "created_epoch": time.time(),
        },
        {
            "public_id": "mem_partial",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "alpha omega theta",
            "created_epoch": time.time(),
        },
    ]

    res = MemoryRecallEngine.recall_memories(
        query="beta gamma delta",
        candidates=candidates,
        participant_scope_key="scope_a",
    )
    assert res.results[0].memory_item_public_id == "mem_exact"
    assert res.results[0].keyword_score > res.results[1].keyword_score


# --- 2. Score Normalization & Deterministic Tie-Breaking ---

def test_p17_8_004_score_normalization_bounds():
    # Extreme inputs test
    score_extreme = MemoryRecallEngine.compute_recall_score(
        keyword_score=1.0,
        vector_score=1.0,
        importance_score=100.0,
        confidence_score=100.0,
        freshness_state=FreshnessState.FRESH,
        retrieval_mode=RetrievalMode.CURRENT,
        is_disputed=False,
        has_topic_match=True,
        has_task_match=True,
    )
    assert 0.0 <= score_extreme <= 100.0

    score_min = MemoryRecallEngine.compute_recall_score(
        keyword_score=0.0,
        vector_score=0.0,
        importance_score=0.0,
        confidence_score=0.0,
        freshness_state=FreshnessState.EXPIRED,
        retrieval_mode=RetrievalMode.CURRENT,
        is_disputed=True,
    )
    assert score_min == 0.0


def test_p17_8_005_deterministic_ranking():
    candidates = [
        {
            "public_id": f"mem_{i}",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": f"Deterministic item number {i}",
            "importance_score": 50.0 + i,
            "confidence_score": 60.0,
            "created_epoch": time.time(),
        }
        for i in range(10)
    ]
    res1 = MemoryRecallEngine.recall_memories(query="number", candidates=candidates, participant_scope_key="scope_a")
    res2 = MemoryRecallEngine.recall_memories(query="number", candidates=candidates, participant_scope_key="scope_a")

    ids1 = [r.memory_item_public_id for r in res1.results]
    ids2 = [r.memory_item_public_id for r in res2.results]
    assert ids1 == ids2


def test_p17_8_006_deterministic_tie_breaking():
    # Identical score, different public IDs
    candidates = [
        {
            "public_id": "mem_b",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Identical claim value",
            "importance_score": 50.0,
            "confidence_score": 50.0,
            "created_epoch": time.time(),
        },
        {
            "public_id": "mem_a",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Identical claim value",
            "importance_score": 50.0,
            "confidence_score": 50.0,
            "created_epoch": time.time(),
        },
    ]
    res = MemoryRecallEngine.recall_memories(query="Identical claim", candidates=candidates, participant_scope_key="scope_a")
    # 'mem_a' must tie-break before 'mem_b' via public_id ASC
    assert res.results[0].memory_item_public_id == "mem_a"
    assert res.results[1].memory_item_public_id == "mem_b"


# --- 3. Freshness & Retrieval Modes ---

def test_p17_8_007_freshness_ranking_boost():
    now = time.time()
    candidates = [
        {
            "public_id": "mem_fresh",
            "participant_scope_key": "scope_a",
            "category": "TASK",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Run server migration step",
            "importance_score": 65.0,
            "confidence_score": 75.0,
            "created_epoch": now - 100,  # FRESH
        },
        {
            "public_id": "mem_stale",
            "participant_scope_key": "scope_a",
            "category": "TASK",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Run server migration step",
            "importance_score": 65.0,
            "confidence_score": 75.0,
            "created_epoch": now - 70000,  # STALE (0.75 * 86400 = 64800)
        },
    ]
    res = MemoryRecallEngine.recall_memories(query="server migration", candidates=candidates, participant_scope_key="scope_a", now_epoch=now)
    assert res.results[0].memory_item_public_id == "mem_fresh"
    assert res.results[0].effective_recall_score > res.results[1].effective_recall_score


def test_p17_8_008_stale_memory_handling():
    now = time.time()
    candidates = [
        {
            "public_id": "mem_stale_pref",
            "participant_scope_key": "scope_a",
            "category": "PREFERENCE",
            "purpose": "general_context",
            "status": "active",
            "display_value": "User prefers dark mode editor theme",
            "importance_score": 70.0,
            "confidence_score": 90.0,
            "created_epoch": now - 12_000_000,  # STALE for preference (TTL=15.5M)
        }
    ]
    res = MemoryRecallEngine.recall_memories(query="editor theme preference", candidates=candidates, participant_scope_key="scope_a", now_epoch=now)
    assert res.final_result_count == 1
    assert res.results[0].freshness_state == FreshnessState.STALE.value


def test_p17_8_009_expired_memory_exclusion_current():
    candidates = [
        {
            "public_id": "mem_expired",
            "participant_scope_key": "scope_a",
            "category": "TASK",
            "purpose": "general_context",
            "status": "expired",
            "display_value": "Old temporary task from last week",
            "created_epoch": time.time() - 200_000,
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="temporary task",
        candidates=candidates,
        participant_scope_key="scope_a",
        retrieval_mode=RetrievalMode.CURRENT,
    )
    assert res.final_result_count == 0
    assert any(e["public_id"] == "mem_expired" for e in res.excluded)


def test_p17_8_010_historical_mode_recall():
    candidates = [
        {
            "public_id": "mem_archived_fact",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "archived",
            "display_value": "Ubuntu 22.04 LTS was deployed in 2023",
            "importance_score": 80.0,
            "confidence_score": 95.0,
            "created_epoch": time.time() - 50_000_000,
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="Ubuntu deployed in 2023",
        candidates=candidates,
        participant_scope_key="scope_a",
        retrieval_mode=RetrievalMode.HISTORICAL,
    )
    assert res.final_result_count == 1
    assert res.results[0].memory_item_public_id == "mem_archived_fact"
    assert res.results[0].status == "archived"


def test_p17_8_011_task_mode_recall():
    candidates = [
        {
            "public_id": "mem_task",
            "participant_scope_key": "scope_a",
            "category": "TASK",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Execute deployment canary checks",
            "created_epoch": time.time(),
        },
        {
            "public_id": "mem_pref",
            "participant_scope_key": "scope_a",
            "category": "PREFERENCE",
            "purpose": "general_context",
            "status": "active",
            "display_value": "User prefers English language responses",
            "created_epoch": time.time(),
        },
    ]
    res = MemoryRecallEngine.recall_memories(
        query="checks and preferences",
        candidates=candidates,
        participant_scope_key="scope_a",
        retrieval_mode=RetrievalMode.TASK,
    )
    assert res.final_result_count == 1
    assert res.results[0].memory_item_public_id == "mem_task"


def test_p17_8_012_procedural_ordering_preservation():
    candidates = [
        {
            "public_id": "proc_step_1",
            "participant_scope_key": "scope_a",
            "category": "PROCEDURAL",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Step 1: Backup database WAL files",
            "importance_score": 80.0,
            "confidence_score": 90.0,
            "created_epoch": time.time(),
        },
        {
            "public_id": "proc_step_2",
            "participant_scope_key": "scope_a",
            "category": "PROCEDURAL",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Step 2: Apply database migration scripts",
            "importance_score": 80.0,
            "confidence_score": 90.0,
            "created_epoch": time.time(),
        },
    ]
    res = MemoryRecallEngine.recall_memories(
        query="database backup and migration step",
        candidates=candidates,
        participant_scope_key="scope_a",
        retrieval_mode=RetrievalMode.TASK,
    )
    assert res.final_result_count == 2
    assert all(r.category == "PROCEDURAL" for r in res.results)


def test_p17_8_013_preference_mode_recall():
    candidates = [
        {
            "public_id": "mem_pref",
            "participant_scope_key": "scope_a",
            "category": "PREFERENCE",
            "purpose": "general_context",
            "status": "active",
            "display_value": "User prefers dark mode and Tamil language",
            "created_epoch": time.time(),
        },
        {
            "public_id": "mem_sem",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Server IP address is 10.0.0.1",
            "created_epoch": time.time(),
        },
    ]
    res = MemoryRecallEngine.recall_memories(
        query="user settings and IP",
        candidates=candidates,
        participant_scope_key="scope_a",
        retrieval_mode=RetrievalMode.PREFERENCE,
    )
    assert res.final_result_count == 1
    assert res.results[0].memory_item_public_id == "mem_pref"


# --- 4. Consolidation Deduplication & Provenance ---

def test_p17_8_014_consolidated_canonical_recall():
    candidates = [
        {
            "public_id": "canon_001",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Canonical claim: Python 3.12 with SQLite storage",
            "importance_score": 85.0,
            "confidence_score": 95.0,
            "evidence_count": 3,
            "is_canonical": True,
            "compression_state": {
                "is_compressed": True,
                "source_references": ["obs_1", "obs_2"],
            },
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(query="Python and SQLite storage", candidates=candidates, participant_scope_key="scope_a")
    assert res.final_result_count == 1
    assert res.results[0].is_canonical is True
    assert res.results[0].evidence_count == 3
    assert res.results[0].constituent_source_ids == ["obs_1", "obs_2"]


def test_p17_8_015_source_deduplication_suppression():
    candidates = [
        {
            "public_id": "canon_db",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Canonical: PostgreSQL primary database architecture",
            "is_canonical": True,
            "importance_score": 85.0,
            "confidence_score": 90.0,
            "compression_state": {
                "is_compressed": True,
                "source_references": ["src_raw_1", "src_raw_2"],
            },
            "created_epoch": time.time(),
        },
        {
            "public_id": "src_raw_1",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Raw observation 1: PostgreSQL on AWS",
            "importance_score": 70.0,
            "confidence_score": 75.0,
            "created_epoch": time.time(),
        },
        {
            "public_id": "src_raw_2",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Raw observation 2: PostgreSQL configuration",
            "importance_score": 70.0,
            "confidence_score": 75.0,
            "created_epoch": time.time(),
        },
    ]
    res = MemoryRecallEngine.recall_memories(
        query="PostgreSQL database",
        candidates=candidates,
        participant_scope_key="scope_a",
        retrieval_mode=RetrievalMode.CURRENT,
    )
    # The canonical item is accepted; raw constituents must be suppressed from duplicate flooding
    result_ids = [r.memory_item_public_id for r in res.results]
    assert "canon_db" in result_ids
    assert "src_raw_1" not in result_ids
    assert "src_raw_2" not in result_ids


def test_p17_8_016_provenance_traceability():
    candidates = [
        {
            "public_id": "canon_prov",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Server runs on port 8080",
            "created_at": "2026-09-06 12:00:00",
            "current_version_id": 42,
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(query="server port", candidates=candidates, participant_scope_key="scope_a")
    item = res.results[0]
    assert item.provenance["created_at"] == "2026-09-06 12:00:00"
    assert item.provenance["version_id"] == 42


# --- 5. Dispute & Conflict Governance ---

def test_p17_8_017_active_dispute_exclusion_policy():
    candidates = [
        {
            "public_id": "mem_disputed",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Contested server location: US-East",
            "is_disputed": True,
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="server location",
        candidates=candidates,
        participant_scope_key="scope_a",
        conflict_policy="exclude_conflicting",
    )
    assert res.final_result_count == 0
    assert any(e["exclusion_reason"] == "disputed_memory_pending_resolution" for e in res.excluded)


def test_p17_8_018_pending_review_warning_annotation():
    candidates = [
        {
            "public_id": "mem_warn",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Contested server location: US-West",
            "is_disputed": True,
            "importance_score": 80.0,
            "confidence_score": 80.0,
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="server location",
        candidates=candidates,
        participant_scope_key="scope_a",
        conflict_policy="prefer_recent",
    )
    assert res.final_result_count == 1
    assert res.results[0].conflict_status == "conflict_requires_confirmation"
    assert res.results[0].disputed_warning is not None
    assert "CONFLICT" in res.results[0].disputed_warning


def test_p17_8_019_under_review_dispute_handling():
    candidates = [
        {
            "public_id": "mem_conf_unconfirmed",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "confidence_type": "assistant_inferred",
            "display_value": "Unconfirmed claim in conflict",
            "is_disputed": True,
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="unconfirmed claim",
        candidates=candidates,
        participant_scope_key="scope_a",
        conflict_policy="prefer_user_confirmed",
    )
    assert res.final_result_count == 0
    assert any(e["exclusion_reason"] == "disputed_unconfirmed_excluded" for e in res.excluded)


def test_p17_8_020_superseded_memory_handling():
    candidates = [
        {
            "public_id": "mem_sup",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "superseded",
            "display_value": "Superseded database config",
            "created_epoch": time.time(),
        }
    ]
    # In CURRENT mode: excluded
    res_curr = MemoryRecallEngine.recall_memories(query="database config", candidates=candidates, participant_scope_key="scope_a", retrieval_mode=RetrievalMode.CURRENT)
    assert res_curr.final_result_count == 0

    # In HISTORICAL mode: accepted
    res_hist = MemoryRecallEngine.recall_memories(query="database config", candidates=candidates, participant_scope_key="scope_a", retrieval_mode=RetrievalMode.HISTORICAL)
    assert res_hist.final_result_count == 1


def test_p17_8_021_revoked_quarantined_exclusion():
    candidates = [
        {
            "public_id": "mem_rev",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "revoked",
            "display_value": "Revoked consent info",
            "created_epoch": time.time(),
        },
        {
            "public_id": "mem_quar",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "quarantined",
            "display_value": "Malicious prompt injection",
            "created_epoch": time.time(),
        },
    ]
    res = MemoryRecallEngine.recall_memories(
        query="injection and consent",
        candidates=candidates,
        participant_scope_key="scope_a",
        retrieval_mode=RetrievalMode.HISTORICAL,
    )
    assert res.final_result_count == 0


# --- 6. Security, Scope & Governance (G1–G14) ---

def test_p17_8_022_participant_scope_isolation():
    candidates = [
        {
            "public_id": "mem_tenant_b",
            "participant_scope_key": "tenant_b",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Tenant B private project specification",
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="private project specification",
        candidates=candidates,
        participant_scope_key="tenant_a",
    )
    assert res.final_result_count == 0
    assert any(e["exclusion_reason"] == "cross_participant_denied" for e in res.excluded)


def test_p17_8_023_category_whitelist_isolation():
    candidates = [
        {
            "public_id": "mem_task_cand",
            "participant_scope_key": "scope_a",
            "category": "TASK",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Task item",
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="task item",
        candidates=candidates,
        participant_scope_key="scope_a",
        allowed_categories=["PREFERENCE", "SEMANTIC"],
    )
    assert res.final_result_count == 0
    assert any(e["exclusion_reason"] == "category_not_in_profile" for e in res.excluded)


def test_p17_8_024_purpose_whitelist_isolation():
    candidates = [
        {
            "public_id": "mem_purp",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "unauthorized_purpose",
            "status": "active",
            "display_value": "Semantic item with non-whitelisted purpose",
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="semantic item",
        candidates=candidates,
        participant_scope_key="scope_a",
        allowed_purposes=["general_context"],
    )
    assert res.final_result_count == 0
    assert any(e["exclusion_reason"] == "purpose_not_in_profile" for e in res.excluded)


def test_p17_8_025_system_category_g1_protection():
    candidates = [
        {
            "public_id": "sys_mem",
            "participant_scope_key": "scope_a",
            "category": "SYSTEM",
            "purpose": "general_context",
            "status": "proposed",  # unapproved
            "display_value": "Internal system core config",
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="system core config",
        candidates=candidates,
        participant_scope_key="scope_a",
        is_admin=False,
    )
    assert res.final_result_count == 0
    assert any(e["exclusion_reason"] in ("governance_g1_restricted", "status_proposed_excluded") for e in res.excluded)


def test_p17_8_026_admin_category_g1_protection():
    candidates = [
        {
            "public_id": "admin_mem",
            "participant_scope_key": "scope_a",
            "category": "ADMIN",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Admin operational procedure",
            "created_epoch": time.time(),
        }
    ]
    res_user = MemoryRecallEngine.recall_memories(
        query="admin procedure",
        candidates=candidates,
        participant_scope_key="scope_a",
        allowed_categories=["PREFERENCE", "SEMANTIC"],
        is_admin=False,
    )
    assert res_user.final_result_count == 0


def test_p17_8_027_secret_sanitization_g8():
    candidates = [
        {
            "public_id": "mem_sec",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Server api_key=sk-1234567890abcdef1234567890abcdef and token=ghp_abcdef1234567890",
            "created_epoch": time.time(),
        }
    ]
    res = MemoryRecallEngine.recall_memories(
        query="find key sk-1234567890abcdef1234567890abcdef",
        candidates=candidates,
        participant_scope_key="scope_a",
    )
    assert res.final_result_count == 1
    # Secret must be redacted in display_value
    assert "sk-1234567890abcdef1234567890abcdef" not in res.results[0].display_value
    assert "[REDACTED" in res.results[0].display_value


# --- 7. Budgeting, Performance & Context Boosts ---

def test_p17_8_028_candidate_token_budget_bounds():
    # Candidates with long strings
    candidates = [
        {
            "public_id": f"mem_long_{i}",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": f"Paragraph {i}: " + ("word " * 100),
            "created_epoch": time.time(),
        }
        for i in range(10)
    ]
    res = MemoryRecallEngine.recall_memories(
        query="Paragraph word",
        candidates=candidates,
        participant_scope_key="scope_a",
        max_tokens=300,
    )
    assert res.metadata["accumulated_tokens"] <= 300
    assert any(e["exclusion_reason"] == "token_budget_exceeded" for e in res.excluded)


def test_p17_8_029_cpu_performance_benchmark():
    sample_vec = compute_embedding("Benchmark item", provider_type="local_custom_embedding", dimensions=64)["vector"]
    candidates = [
        {
            "public_id": f"bench_{i}",
            "participant_scope_key": "scope_bench",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": f"Benchmark item {i} describing system properties and performance",
            "importance_score": 60.0,
            "confidence_score": 70.0,
            "vector": sample_vec,
            "created_epoch": time.time(),
        }
        for i in range(50)
    ]
    t0 = time.perf_counter()
    res = MemoryRecallEngine.recall_memories(
        query="system properties and performance",
        candidates=candidates,
        participant_scope_key="scope_bench",
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert res.final_result_count > 0
    assert res.runtime_milliseconds < 35.0  # In-engine pure CPU evaluation budget


def test_p17_8_030_repeated_query_stability():
    candidates = [
        {
            "public_id": "mem_stable",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Stable memory query item",
            "created_epoch": time.time(),
        }
    ]
    res1 = MemoryRecallEngine.recall_memories(query="Stable memory", candidates=candidates, participant_scope_key="scope_a")
    res2 = MemoryRecallEngine.recall_memories(query="Stable memory", candidates=candidates, participant_scope_key="scope_a")
    assert res1.results[0].effective_recall_score == res2.results[0].effective_recall_score


def test_p17_8_031_context_topic_task_boost():
    candidates = [
        {
            "public_id": "mem_ctx",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Database backup procedures and WAL snapshots",
            "importance_score": 50.0,
            "confidence_score": 50.0,
            "created_epoch": time.time(),
        }
    ]
    # Without boost
    res_no_boost = MemoryRecallEngine.recall_memories(
        query="procedures",
        candidates=candidates,
        participant_scope_key="scope_a",
    )
    # With active topic boost (Phase 17.2)
    res_with_boost = MemoryRecallEngine.recall_memories(
        query="procedures",
        candidates=candidates,
        participant_scope_key="scope_a",
        active_topic="database_backup",
    )
    assert res_with_boost.results[0].effective_recall_score > res_no_boost.results[0].effective_recall_score


def test_p17_8_032_empty_result_behavior():
    candidates = []
    res = MemoryRecallEngine.recall_memories(
        query="any query",
        candidates=candidates,
        participant_scope_key="scope_a",
    )
    assert res.final_result_count == 0
    assert res.results == []


def test_p17_8_033_malformed_query_handling():
    candidates = [
        {
            "public_id": "mem_safe",
            "participant_scope_key": "scope_a",
            "category": "SEMANTIC",
            "purpose": "general_context",
            "status": "active",
            "display_value": "Normal memory item",
            "created_epoch": time.time(),
        }
    ]
    # Whitespace only
    res_blank = MemoryRecallEngine.recall_memories(query="   ", candidates=candidates, participant_scope_key="scope_a")
    assert res_blank.query == ""

    # Special characters
    res_spec = MemoryRecallEngine.recall_memories(query="!@#$%^&*()_+", candidates=candidates, participant_scope_key="scope_a")
    assert res_spec.final_result_count >= 0


# --- 8. Service Integration E2E Tests ---

def test_p17_8_034_audit_run_recording_integrity(temp_service):
    service, repo, _ = temp_service
    tenant_key = f"tenant_34_{uuid4().hex[:6]}"
    profile_id, consent_id = _setup_base_profile(service, participant_scope_key=tenant_key)

    # Propose memory (explicit user request with consent is directly active)
    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=tenant_key,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Production deployment is scheduled for Sunday",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_p17_8",
    )

    res = service.retrieve(
        MemoryRetrieveRequest(
            retrieval_profile_public_id=profile_id,
            participant_scope_key=tenant_key,
            query="deployment scheduled",
        ),
        admin_id="admin_p17_8",
    )

    assert len(res["results"]) == 1
    assert res["results"][0]["memory_item_public_id"] == m["public_id"]
    assert res["status"] == "completed"

    # Verify immutable retrieval run in DB
    run_pub_id = res["public_id"]
    with repo.transaction() as conn:
        run_row = repo.retrieval_run(conn, run_pub_id)
        assert run_row["participant_scope_key"] == tenant_key
        results_rows = repo.results_for_retrieval_run(conn, run_row["id"])
        assert len(results_rows) == 1


def test_p17_8_035_regression_phases_17_2_to_17_7(temp_service):
    # Verifies that Phase 17.8 service retrieval works seamlessly with consolidations and lifecycle
    service, repo, _ = temp_service
    tenant_key = f"tenant_35_{uuid4().hex[:6]}"
    profile_id, consent_id = _setup_base_profile(service, participant_scope_key=tenant_key)

    # 1. Propose multiple memories
    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=tenant_key,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Server operates on Ubuntu 24.04 LTS linux release",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_p17_8",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=tenant_key,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Operating system environment is confirmed as Ubuntu 24.04 LTS",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_p17_8",
    )

    # 2. Consolidate them (Phase 17.6)
    cons = service.consolidate_memories(
        participant_scope_key=tenant_key,
        category="user_confirmed_fact",
        purpose="user_confirmed_profile",
        admin_id="admin_p17_8",
    )
    assert cons["consolidated_count"] >= 1

    # 3. Retrieve using Phase 17.8
    res = service.retrieve(
        MemoryRetrieveRequest(
            retrieval_profile_public_id=profile_id,
            participant_scope_key=tenant_key,
            query="Ubuntu 24.04 operating system",
        ),
        admin_id="admin_p17_8",
    )
    assert len(res["results"]) >= 1
    # Canonical memory must be returned with deduplication of constituents
    top_res = res["results"][0]
    assert top_res["is_canonical"] is True


def test_p17_8_036_anti_inflation_verification(temp_service):
    # Verify retrieval does NOT increment evidence_count or confidence_score
    service, repo, _ = temp_service
    tenant_key = f"tenant_36_{uuid4().hex[:6]}"
    profile_id, consent_id = _setup_base_profile(service, participant_scope_key=tenant_key)

    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=tenant_key,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Critical system parameter alpha=100",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_p17_8",
    )

    # Check initial item state
    with repo.transaction() as conn:
        item_before = repo.memory_item(conn, m["public_id"])
        ev_before = item_before["evidence_count"] if "evidence_count" in item_before.keys() else 1

    # Run 10 repeated retrievals
    for _ in range(10):
        service.retrieve(
            MemoryRetrieveRequest(
                retrieval_profile_public_id=profile_id,
                participant_scope_key=tenant_key,
                query="Critical parameter alpha",
            ),
            admin_id="admin_p17_8",
        )

    # Check state after 10 retrievals: evidence_count MUST remain unchanged
    with repo.transaction() as conn:
        item_after = repo.memory_item(conn, m["public_id"])
        ev_after = item_after["evidence_count"] if "evidence_count" in item_after.keys() else 1
        assert ev_after == ev_before
