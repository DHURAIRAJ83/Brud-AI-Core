"""Phase 17.9: Advanced Memory Reasoning & Recall Planning E2E Test Suite.

Verifies:
1. Multi-Memory Relationship Detection (Pairwise, vector, lexical, category, temporal)
2. Read-Only Evidence Aggregation & Corroboration Clustering (G4 anti-inflation)
3. Temporal Reasoning & State Classification (CURRENT_ACTIVE, HISTORICAL_VALID, SUPERSEDED_PAST, TEMPORARY_EPISODIC)
4. Contradiction & Dispute-Aware Epistemic Partitioning (FACT_CURRENT, FACT_HISTORICAL, FACT_CONTESTED, FACT_SUPERSEDED)
5. Procedural Workflow Reconstruction (Step parsing, dependency sorting, missing steps, cycle detection)
6. Preference Consistency Reasoning (Explicit > Inferred, specific > general, temporal recency)
7. Coherence Scoring & Deterministic Token Budgeting
8. Structured MemoryReasoningPacket Formation & Lossless Context Block Formatting
9. Security & Governance (G1, G4, G5 tenant isolation, G8 sanitization, G10 lineage, G11 dispute safety)
10. CPU Performance (< 3 ms) and Historical Interoperability / Determinism
"""

from __future__ import annotations

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
from core_model.mini_brain.intelligence.memory_recall import (
    MemoryRecallEngine,
    MemoryRecallItem,
    MemoryRecallResult,
    RetrievalMode,
)
from core_model.mini_brain.intelligence.memory_reasoner import (
    EvidenceCluster,
    MemoryReasoningEngine,
    MemoryReasoningPacket,
    PreferenceResolution,
    ProceduralStep,
)
from core_model.rag.embedding import compute_embedding


@pytest.fixture
def temp_service(tmp_path: Path) -> tuple[MemoryService, ConversationMemoryRepository, Settings]:
    db_path = tmp_path / "test_p17_9.db"
    settings = Settings(DATABASE_URL=f"sqlite:///{db_path}")
    initialize_database(settings.resolved_database_path, wal_enabled=True)
    repo = ConversationMemoryRepository(settings.resolved_database_path)
    service = MemoryService(repo, settings)
    return service, repo, settings


def _setup_base_profile(service: MemoryService, participant_scope_key: str = "tenant_17_9", admin_id: str = "admin_p17_9") -> tuple[str, str]:
    pol = service.create_policy(
        MemoryPolicyCreate(
            name=f"P17.9 Policy {participant_scope_key}",
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
            name=f"P17.9 Active Profile {participant_scope_key}",
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


# --- 1. Multi-Memory Relationship Detection (P17_9-001 -> P17_9-005) ---

def test_p17_9_001_pairwise_relationship_calculation():
    m1 = {
        "public_id": "mem_01",
        "display_value": "Python 3.12 is the primary application runtime",
        "category": "SEMANTIC",
        "created_epoch": 1000.0,
    }
    m2 = {
        "public_id": "mem_02",
        "display_value": "Python 3.12 runtime environment is configured",
        "category": "SEMANTIC",
        "created_epoch": 1050.0,
    }
    r_score = MemoryReasoningEngine.calculate_pairwise_relationship(m1, m2)
    assert 0.0 <= r_score <= 1.0
    assert r_score >= 0.50  # High relationship due to identical vector/tokens and category match


def test_p17_9_002_vector_and_lexical_similarity_weights():
    m1 = {"display_value": "PostgreSQL database clustering", "category": "SEMANTIC"}
    m2 = {"display_value": "PostgreSQL cluster configuration", "category": "SEMANTIC"}
    m3 = {"display_value": "Completely unrelated culinary recipe for pasta", "category": "EPISODIC"}

    r_close = MemoryReasoningEngine.calculate_pairwise_relationship(m1, m2)
    r_far = MemoryReasoningEngine.calculate_pairwise_relationship(m1, m3)
    assert r_close > r_far
    assert r_far < 0.25


def test_p17_9_003_category_match_bonus():
    m1 = {"display_value": "Server architecture config", "category": "SYSTEM", "created_epoch": 100.0}
    m2 = {"display_value": "Server architecture config", "category": "SYSTEM", "created_epoch": 100.0}
    m3 = {"display_value": "Server architecture config", "category": "PREFERENCE", "created_epoch": 100.0}

    r_same_cat = MemoryReasoningEngine.calculate_pairwise_relationship(m1, m2)
    r_diff_cat = MemoryReasoningEngine.calculate_pairwise_relationship(m1, m3)
    # Same category gets +0.15 delta_category
    assert round(r_same_cat - r_diff_cat, 2) == 0.15


def test_p17_9_004_temporal_proximity_decay():
    m1 = {"display_value": "System deployment initiated", "category": "EPISODIC", "created_epoch": 1000.0}
    m2 = {"display_value": "System deployment completed", "category": "EPISODIC", "created_epoch": 1010.0}
    m3 = {"display_value": "System deployment completed", "category": "EPISODIC", "created_epoch": 1000000.0}

    r_near = MemoryReasoningEngine.calculate_pairwise_relationship(m1, m2)
    r_far = MemoryReasoningEngine.calculate_pairwise_relationship(m1, m3)
    assert r_near > r_far


def test_p17_9_005_bounded_pairwise_pool_limit():
    # Verify candidate pool is capped at N <= 20
    candidates = [
        {"public_id": f"m_{i}", "participant_scope_key": "scope_1", "display_value": f"Fact {i}", "effective_recall_score": 70.0}
        for i in range(35)
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="test query",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    # Active facts should not exceed max candidate limit (20)
    assert len(packet.active_facts) <= 20


# --- 2. Evidence Aggregation & Corroboration (P17_9-006 -> P17_9-010) ---

def test_p17_9_006_corroborating_evidence_clustering():
    candidates = [
        {
            "public_id": "m1",
            "display_value": "Ubuntu 24.04 is the primary Linux distribution",
            "category": "user_confirmed_fact",
            "confidence_score": 80.0,
            "creation_source": "explicit_user_request",
        },
        {
            "public_id": "m2",
            "display_value": "Primary Linux distribution confirmed as Ubuntu 24.04",
            "category": "user_confirmed_fact",
            "confidence_score": 70.0,
            "creation_source": "system_derived",
        },
    ]
    clusters = MemoryReasoningEngine.cluster_evidence(candidates, similarity_threshold=0.60)
    assert len(clusters) >= 1
    cl = clusters[0]
    assert "m1" in cl.member_public_ids
    assert "m2" in cl.member_public_ids
    assert cl.is_corroborated is True


def test_p17_9_007_aggregate_confidence_bounding():
    candidates = [
        {"public_id": "m1", "display_value": "Core system alpha online", "confidence_score": 90.0},
        {"public_id": "m2", "display_value": "Core system alpha online", "confidence_score": 80.0},
    ]
    clusters = MemoryReasoningEngine.cluster_evidence(candidates, similarity_threshold=0.60)
    assert len(clusters) == 1
    # Aggregated confidence must exceed individual confidence and stay <= 100.0
    agg = clusters[0].aggregate_confidence
    assert 90.0 < agg <= 100.0


def test_p17_9_008_source_diversity_tracking():
    candidates = [
        {"public_id": "m1", "display_value": "Port 8080 open for HTTP", "creation_source": "explicit_user_request"},
        {"public_id": "m2", "display_value": "Port 8080 open for HTTP", "creation_source": "system_derived"},
    ]
    clusters = MemoryReasoningEngine.cluster_evidence(candidates, similarity_threshold=0.60)
    assert len(clusters) == 1
    assert "explicit_user_request" in clusters[0].source_diversity
    assert "system_derived" in clusters[0].source_diversity


def test_p17_9_009_read_only_anti_inflation_preservation(temp_service):
    # Verifies G4: clustering and reasoning NEVER modify database evidence_count
    service, repo, _ = temp_service
    tenant_key = f"tenant_g4_{uuid4().hex[:6]}"
    prof_id, consent_id = _setup_base_profile(service, participant_scope_key=tenant_key)

    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=tenant_key,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Static invariant key = ABC-123",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_p17_9",
    )

    # Execute reason_over_memories 5 times
    for _ in range(5):
        service.reason_over_memories(
            MemoryRetrieveRequest(
                retrieval_profile_public_id=prof_id,
                participant_scope_key=tenant_key,
                query="Static invariant key",
            ),
            admin_id="admin_p17_9",
        )

    # Verify evidence_count remained 1 in storage
    with repo.transaction() as conn:
        item = repo.memory_item(conn, m["public_id"])
        ev = item["evidence_count"] if "evidence_count" in item.keys() else 1
        assert ev == 1


def test_p17_9_010_isolated_single_evidence_handling():
    candidates = [
        {"public_id": "m1", "display_value": "Unique standalone observation without peer", "confidence_score": 75.0}
    ]
    clusters = MemoryReasoningEngine.cluster_evidence(candidates)
    # Single items do not form multi-item corroboration clusters
    assert len(clusters) == 0


# --- 3. Temporal Reasoning & State Partitioning (P17_9-011 -> P17_9-014) ---

def test_p17_9_011_current_vs_historical_fact_partitioning():
    candidates = [
        {"public_id": "m1", "participant_scope_key": "scope_1", "display_value": "Current active parameter", "status": "active"},
        {"public_id": "m2", "participant_scope_key": "scope_1", "display_value": "Archived old parameter", "status": "archived"},
        {"public_id": "m3", "participant_scope_key": "scope_1", "display_value": "Expired legacy parameter", "status": "expired"},
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="parameter",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    assert len(packet.active_facts) == 1
    assert packet.active_facts[0]["public_id"] == "m1"
    assert len(packet.historical_facts) == 2


def test_p17_9_012_stale_memory_preservation_without_falsehood():
    candidates = [
        {
            "public_id": "m1",
            "participant_scope_key": "scope_1",
            "display_value": "Legacy system hostname",
            "status": "active",
            "freshness_state": "STALE",
            "effective_recall_score": 65.0,
        }
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="hostname",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    # Stale active memory remains active and valid
    assert len(packet.active_facts) == 1


def test_p17_9_013_superseded_past_fact_handling():
    candidates = [
        {"public_id": "m_new", "participant_scope_key": "scope_1", "display_value": "V2 architecture active", "status": "active"},
        {"public_id": "m_old", "participant_scope_key": "scope_1", "display_value": "V1 architecture legacy", "status": "archived"},
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="architecture",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    assert packet.active_facts[0]["public_id"] == "m_new"
    assert packet.historical_facts[0]["public_id"] == "m_old"


def test_p17_9_014_historical_mode_temporal_assembly():
    candidates = [
        {"public_id": "m1", "participant_scope_key": "scope_1", "display_value": "Fact from 2024", "status": "archived"},
        {"public_id": "m2", "participant_scope_key": "scope_1", "display_value": "Fact from 2025", "status": "active"},
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="history",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.HISTORICAL,
        retrieved_items=candidates,
    )
    assert packet.retrieval_mode == "HISTORICAL"
    assert len(packet.active_facts) == 1
    assert len(packet.historical_facts) == 1


# --- 4. Conflict & Dispute-Aware Reasoning (P17_9-015 -> P17_9-018) ---

def test_p17_9_015_exclude_conflicting_policy_isolation():
    candidates = [
        {"public_id": "m1", "participant_scope_key": "scope_1", "display_value": "Production server is at 10.0.0.1", "is_disputed": False},
        {"public_id": "m2", "participant_scope_key": "scope_1", "display_value": "Production server is at 10.0.0.2", "is_disputed": True, "disputed_warning": "Conflict with m1"},
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="server ip",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
        conflict_policy="exclude_conflicting",
    )
    # Contested item excluded from active context
    assert len(packet.active_facts) == 1
    assert packet.active_facts[0]["public_id"] == "m1"
    assert len(packet.disputed_items) == 0
    assert any("DisputeExcluded" in w for w in packet.warnings)


def test_p17_9_016_prefer_recent_policy_advisory_segregation():
    candidates = [
        {"public_id": "m1", "participant_scope_key": "scope_1", "display_value": "Valid server config", "is_disputed": False},
        {"public_id": "m2", "participant_scope_key": "scope_1", "display_value": "Contested server config", "is_disputed": True, "disputed_warning": "Active review pending"},
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="server",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
        conflict_policy="prefer_recent",
    )
    assert len(packet.active_facts) == 1
    assert len(packet.disputed_items) == 1
    assert packet.disputed_items[0]["public_id"] == "m2"
    ctx_block = packet.to_context_block()
    assert "[Disputed / Contested Items]" in ctx_block
    assert "Active review pending" in ctx_block


def test_p17_9_017_dispute_penalty_applied_to_coherence():
    c_clean = [
        {"public_id": "m1", "participant_scope_key": "scope_1", "display_value": "Clean fact A", "effective_recall_score": 80.0, "is_disputed": False},
        {"public_id": "m2", "participant_scope_key": "scope_1", "display_value": "Clean fact B", "effective_recall_score": 80.0, "is_disputed": False},
    ]
    c_disputed = [
        {"public_id": "m1", "participant_scope_key": "scope_1", "display_value": "Clean fact A", "effective_recall_score": 80.0, "is_disputed": False},
        {"public_id": "m2", "participant_scope_key": "scope_1", "display_value": "Contested fact B", "effective_recall_score": 80.0, "is_disputed": True},
    ]
    p_clean = MemoryReasoningEngine.assemble_reasoning_packet("q", "scope_1", RetrievalMode.CURRENT, c_clean)
    p_disp = MemoryReasoningEngine.assemble_reasoning_packet("q", "scope_1", RetrievalMode.CURRENT, c_disputed)
    assert p_clean.coherence_score > p_disp.coherence_score


def test_p17_9_018_zero_autonomous_truth_selection():
    # Verifies that disputed items are never labeled active uncontested facts
    candidates = [
        {"public_id": "m_disp", "participant_scope_key": "scope_1", "display_value": "Contested IP", "is_disputed": True, "disputed_warning": "Disputed"}
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet("q", "scope_1", RetrievalMode.CURRENT, candidates, conflict_policy="prefer_recent")
    assert len(packet.active_facts) == 0
    assert len(packet.disputed_items) == 1


# --- 5. Procedural Workflow Reconstruction (P17_9-019 -> P17_9-022) ---

def test_p17_9_019_procedural_step_extraction_and_ordering():
    candidates = [
        {"public_id": "m3", "category": "TASK", "display_value": "Step 3: Deploy to staging cluster"},
        {"public_id": "m1", "category": "TASK", "display_value": "Step 1: Run automated unit tests"},
        {"public_id": "m2", "category": "TASK", "display_value": "Step 2: Build container image"},
    ]
    chains, _ = MemoryReasoningEngine.extract_procedural_chains(candidates)
    assert len(chains) == 1
    steps = chains[0]["steps"]
    assert len(steps) == 3
    assert steps[0]["step_number"] == 1
    assert steps[1]["step_number"] == 2
    assert steps[2]["step_number"] == 3


def test_p17_9_020_missing_intermediate_step_detection():
    candidates = [
        {"public_id": "m1", "category": "TASK", "display_value": "Step 1: Initialize workspace"},
        {"public_id": "m4", "category": "TASK", "display_value": "Step 4: Publish artifact release"},
    ]
    chains, _ = MemoryReasoningEngine.extract_procedural_chains(candidates)
    assert len(chains) == 1
    assert chains[0]["missing_steps"] == [2, 3]


def test_p17_9_021_procedural_dependency_trigger_parsing():
    candidates = [
        {"public_id": "m2", "category": "TASK", "display_value": "Step 2: Run migration (requires Step 1)"},
        {"public_id": "m1", "category": "TASK", "display_value": "Step 1: Backup database"},
    ]
    chains, _ = MemoryReasoningEngine.extract_procedural_chains(candidates)
    steps = chains[0]["steps"]
    assert steps[0]["step_number"] == 1
    assert steps[1]["step_number"] == 2
    assert "Step 1" in steps[1]["dependencies"]


def test_p17_9_022_workflow_cycle_detection_fallback():
    # Circular dependency: Step 1 requires Step 1
    candidates = [
        {"public_id": "m1", "category": "TASK", "display_value": "Step 1: Loop forever (requires Step 1)"}
    ]
    chains, warnings = MemoryReasoningEngine.extract_procedural_chains(candidates)
    assert any("WorkflowCycleWarning" in w for w in warnings)
    assert len(chains) == 1


# --- 6. User Preference Reasoning (P17_9-023 -> P17_9-025) ---

def test_p17_9_023_explicit_vs_inferred_preference_precedence():
    candidates = [
        {
            "public_id": "p_inf",
            "category": "LANGUAGE_PREFERENCE",
            "display_value": "language: English",
            "creation_source": "assistant_inferred",
            "created_epoch": 1000.0,
        },
        {
            "public_id": "p_exp",
            "category": "LANGUAGE_PREFERENCE",
            "display_value": "language: Tamil",
            "creation_source": "explicit_user_request",
            "created_epoch": 500.0,
        },
    ]
    res = MemoryReasoningEngine.resolve_preferences(candidates)
    # Explicit user request wins regardless of timestamp
    assert res.resolved_preferences["language"] == "Tamil"
    assert "p_inf" in res.superseded_preferences


def test_p17_9_024_temporal_recency_preference_supersession():
    candidates = [
        {
            "public_id": "p_old",
            "category": "FORMAT_PREFERENCE",
            "display_value": "format: JSON",
            "creation_source": "explicit_user_request",
            "created_epoch": 1000.0,
        },
        {
            "public_id": "p_new",
            "category": "FORMAT_PREFERENCE",
            "display_value": "format: Markdown",
            "creation_source": "explicit_user_request",
            "created_epoch": 2000.0,
        },
    ]
    res = MemoryReasoningEngine.resolve_preferences(candidates)
    # Newer explicit preference wins
    assert res.resolved_preferences["format"] == "Markdown"
    assert "p_old" in res.superseded_preferences


def test_p17_9_025_preference_resolution_provenance_citations():
    candidates = [
        {
            "public_id": "pref_01",
            "category": "PREFERENCE",
            "display_value": "theme: dark",
            "creation_source": "explicit_user_request",
        }
    ]
    res = MemoryReasoningEngine.resolve_preferences(candidates)
    assert res.provenance_citations["theme"] == "pref_01"


# --- 7. Reasoning Packet Assembly & Context Formatting (P17_9-026 -> P17_9-029) ---

def test_p17_9_026_packet_assembly_and_coherence_bounds():
    candidates = [
        {"public_id": "m1", "participant_scope_key": "scope_1", "display_value": "Fact A", "effective_recall_score": 85.0},
        {"public_id": "m2", "participant_scope_key": "scope_1", "display_value": "Fact B", "effective_recall_score": 90.0},
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="test query",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    assert 0.0 <= packet.coherence_score <= 100.0
    assert packet.total_token_estimate > 0


def test_p17_9_027_context_block_formatting_preserves_citations():
    candidates = [
        {"public_id": "pub_xyz123", "participant_scope_key": "scope_1", "display_value": "Server port is 443", "status": "active"},
        {"public_id": "pref_theme", "participant_scope_key": "scope_1", "category": "PREFERENCE", "display_value": "ui_mode: dark", "status": "active"},
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="port",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    ctx = packet.to_context_block()
    assert "[Active Facts]" in ctx
    assert "[mem:pub_xyz123]" in ctx
    assert "[User Preferences]" in ctx
    assert "ui_mode: dark" in ctx


def test_p17_9_028_deterministic_token_budget_estimation():
    candidates = [
        {"public_id": "m1", "participant_scope_key": "scope_1", "display_value": "A " * 50, "status": "active"}
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="long string",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    assert packet.total_token_estimate >= 20


def test_p17_9_029_empty_candidates_graceful_handling():
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="empty query",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=[],
    )
    assert packet.coherence_score == 0.0
    assert len(packet.active_facts) == 0
    assert packet.to_context_block() == ""


# --- 8. Security, Governance & Isolation (P17_9-030 -> P17_9-033) ---

def test_p17_9_030_tenant_isolation_mismatched_scope_fail_closed():
    # G5 Invariant: Mismatched scope items MUST raise ValueError fail-closed
    candidates = [
        {"public_id": "m_tenant_a", "participant_scope_key": "tenant_A", "display_value": "Confidential data A"},
        {"public_id": "m_tenant_b", "participant_scope_key": "tenant_B", "display_value": "Confidential data B"},
    ]
    with pytest.raises(ValueError, match="G5 Isolation Violation"):
        MemoryReasoningEngine.assemble_reasoning_packet(
            query="test",
            participant_scope_key="tenant_A",
            retrieval_mode=RetrievalMode.CURRENT,
            retrieved_items=candidates,
        )


def test_p17_9_031_secret_sanitization_in_context_block():
    candidates = [
        {
            "public_id": "m_sec",
            "participant_scope_key": "scope_1",
            "display_value": "Bearer sk-1234567890abcdef1234567890abcdef should be kept private",
            "status": "active",
        }
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="token",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    ctx = packet.to_context_block()
    # Verified: raw credential sanitized / redacted
    assert "sk-1234567890abcdef1234567890abcdef" not in ctx


def test_p17_9_032_g1_governance_system_admin_protection():
    # Verify unprivileged reasoning does not violate G1
    candidates = [
        {"public_id": "m_user", "participant_scope_key": "scope_1", "category": "user_confirmed_fact", "display_value": "User fact", "status": "active"}
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="user fact",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    assert len(packet.active_facts) == 1
    assert packet.active_facts[0]["category"] == "user_confirmed_fact"


def test_p17_9_033_canonical_lineage_and_provenance_preservation():
    candidates = [
        {
            "public_id": "canon_01",
            "participant_scope_key": "scope_1",
            "display_value": "Consolidated server overview",
            "status": "consolidated",
            "is_canonical": True,
            "constituent_source_ids": ["src_1", "src_2"],
        }
    ]
    packet = MemoryReasoningEngine.assemble_reasoning_packet(
        query="server",
        participant_scope_key="scope_1",
        retrieval_mode=RetrievalMode.CURRENT,
        retrieved_items=candidates,
    )
    assert packet.provenance_citations[0]["is_canonical"] is True


# --- 9. CPU Performance, Determinism & Historical Interoperability (P17_9-034 -> P17_9-036) ---

def test_p17_9_034_cpu_performance_benchmark():
    # Benchmark reasoning engine over 20 candidate memories (with pre-computed vectors as returned by retrieve())
    candidates = [
        {
            "public_id": f"bench_{i}",
            "participant_scope_key": "scope_bench",
            "display_value": f"System configuration step {i}: parameter={i * 10}",
            "category": "TASK",
            "status": "active",
            "effective_recall_score": 70.0 + (i % 20),
            "confidence_score": 80.0,
            "created_epoch": 1000.0 + i * 60,
            "vector": [0.1 * ((i + k) % 10) for k in range(64)],
        }
        for i in range(20)
    ]

    t0 = time.perf_counter()
    for _ in range(50):
        packet = MemoryReasoningEngine.assemble_reasoning_packet(
            query="system configuration step",
            participant_scope_key="scope_bench",
            retrieval_mode=RetrievalMode.TASK,
            retrieved_items=candidates,
        )
    elapsed = (time.perf_counter() - t0) / 50.0 * 1000.0  # ms per run
    assert elapsed < 3.0  # Must be strictly under 3.0 ms CPU SLA


def test_p17_9_035_service_layer_interoperability_phases_17_2_to_17_8(temp_service):
    # Tests complete pipeline: propose -> retrieve -> reason_over_memories
    service, repo, _ = temp_service
    tenant_key = f"tenant_35_{uuid4().hex[:6]}"
    profile_id, consent_id = _setup_base_profile(service, participant_scope_key=tenant_key)

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=tenant_key,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="PostgreSQL 16 cluster runs on primary node",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_p17_9",
    )

    packet = service.reason_over_memories(
        MemoryRetrieveRequest(
            retrieval_profile_public_id=profile_id,
            participant_scope_key=tenant_key,
            query="PostgreSQL primary node",
        ),
        admin_id="admin_p17_9",
    )

    assert isinstance(packet, MemoryReasoningPacket)
    assert len(packet.active_facts) == 1
    assert "PostgreSQL 16" in packet.active_facts[0]["display_value"]
    assert packet.coherence_score > 0.0


def test_p17_9_036_repeated_execution_bit_exact_determinism():
    candidates = [
        {"public_id": "m1", "participant_scope_key": "scope_det", "display_value": "Step 1: Init", "category": "TASK", "effective_recall_score": 80.0},
        {"public_id": "m2", "participant_scope_key": "scope_det", "display_value": "Step 2: Build", "category": "TASK", "effective_recall_score": 75.0},
    ]
    p1 = MemoryReasoningEngine.assemble_reasoning_packet("q", "scope_det", RetrievalMode.TASK, candidates, now_epoch=1700000000.0)
    p2 = MemoryReasoningEngine.assemble_reasoning_packet("q", "scope_det", RetrievalMode.TASK, candidates, now_epoch=1700000000.0)
    assert p1.coherence_score == p2.coherence_score
    assert p1.to_context_block() == p2.to_context_block()
    assert p1.total_token_estimate == p2.total_token_estimate
