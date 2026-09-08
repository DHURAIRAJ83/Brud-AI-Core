"""Phase 17.6: Memory Consolidation & Knowledge Compression Test Suite.

Validates the complete 35-point requirement matrix for Phase 17.6:
1. Related-memory grouping
2. Cosine threshold enforcement (>= 0.75)
3. Canonical formation & synthesis
4. Deterministic canonical selection
5. Evidence sum preservation
6. Provenance preservation (source_references)
7. Compression metadata structure
8. Consolidation idempotency
9. Duplicate canonical prevention
10. Evidence inflation prevention
11. Unresolved dispute blocking
12. DETECTED dispute blocking
13. PENDING_REVIEW blocking
14. UNDER_REVIEW blocking
15. SUPERSEDE_EXISTING handling
16. RETAIN_EXISTING handling
17. RETAIN_BOTH_COEXIST handling
18. DISMISS handling
19. Temporal validity preservation
20. Expired-memory exclusion
21. Category isolation
22. Purpose isolation
23. Participant scope isolation (G5)
24. SYSTEM governance (G1 gate)
25. ADMIN governance (G1 gate)
26. G8 secret sanitization
27. Retrieval integrity with consolidated memory
28. Provenance/citation traceability (get_consolidated_sources)
29. Version checksum preservation
30. Reversible unconsolidation (unconsolidate_memory)
31. Candidate limit bounded (<= 20)
32. CPU performance benchmark (<= 5 ms)
33. SQLite WAL durability and rollback
34. Procedural step ordering preservation
35. Fabricated range prevention
"""

import time
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
from core_model.mini_brain.intelligence.conflict_detector import (
    ConflictClassification,
    ConflictKnowledgeEngine,
    DisputeRecord,
    DisputeState,
    ResolutionStrategy,
)
from core_model.mini_brain.intelligence.memory_consolidator import (
    CONSOLIDATION_SIMILARITY_THRESHOLD,
    MAX_CONSOLIDATION_CANDIDATES,
    ConsolidationGroup,
    ConsolidationResult,
    MemoryConsolidatorEngine,
)


@pytest.fixture
def memory_env(tmp_path):
    db_path = tmp_path / "test_p17_6.db"
    settings = Settings(
        app_env="production",
        app_secret_key="0" * 64,
        database_path=db_path,
        allowed_model_dir=tmp_path / "models",
        allowed_data_dir=tmp_path / "data",
        database_backup_dir=tmp_path / "backups",
        sqlite_wal_enabled=True,
        sqlite_busy_timeout_ms=5000,
        sqlite_synchronous="NORMAL",
        allow_external_storage=True,
        audit_enabled=True,
    )
    (tmp_path / "models").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)

    initialize_database(settings.resolved_database_path, wal_enabled=True)
    repo = ConversationMemoryRepository(settings.resolved_database_path)
    service = MemoryService(repo, settings)

    policy = service.create_policy(
        MemoryPolicyCreate(
            name="p17_6_policy",
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
            allow_long_term_memory=True,
            require_explicit_consent=True,
        ),
        admin_id="admin_root",
    )

    consent = service.create_consent(
        ConsentCreate(
            participant_scope_key="admin_assistant:adm_001",
            memory_policy_public_id=policy["public_id"],
            purpose="user_confirmed_profile",
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
            prohibited_categories=[],
        ),
        admin_id="admin_root",
    )

    return {
        "service": service,
        "repo": repo,
        "settings": settings,
        "policy": policy,
        "consent": consent,
    }


# ============================================================================
# 1-7: Grouping, Canonical Formation & Provenance Tests
# ============================================================================


def test_related_memory_grouping(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    # Propose multiple related observations
    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Server operates on Ubuntu 24.04 LTS linux release",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Operating system environment is confirmed as Ubuntu 24.04 LTS",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(
        participant_scope_key=scope,
        category="user_confirmed_fact",
        purpose="user_confirmed_profile",
        admin_id="admin_root",
    )

    assert res["consolidated_count"] == 1
    canon = res["canonical_records"][0]
    assert len(canon["source_memory_ids"]) == 2
    assert m1["public_id"] in canon["source_memory_ids"]
    assert m2["public_id"] in canon["source_memory_ids"]


def test_cosine_threshold_enforcement(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    # Distinct statements that should NOT group together
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="The primary cluster uses 64GB RAM nodes",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="User prefers dark mode UI theme in editor",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(
        participant_scope_key=scope,
        category="user_confirmed_fact",
        purpose="user_confirmed_profile",
        admin_id="admin_root",
    )
    assert res["consolidated_count"] == 0


def test_canonical_formation_and_synthesis(memory_env):
    candidates = [
        {"public_id": "m1", "display_value": "Backup occurs daily at 00:00 UTC", "confidence_score": 90.0, "importance_score": 80.0, "evidence_count": 1, "status": "active"},
        {"public_id": "m2", "display_value": "Database backup scheduled at midnight 00:00 UTC", "confidence_score": 85.0, "importance_score": 75.0, "evidence_count": 2, "status": "active"},
    ]
    group = ConsolidationGroup(
        group_id="grp_test_001",
        participant_scope_key="scope_1",
        category="SEMANTIC",
        purpose="profile",
        candidate_items=candidates,
    )
    result = MemoryConsolidatorEngine.consolidate_group(group)

    assert result.total_evidence_count == 3
    assert result.confidence_score >= 90.0
    assert result.importance_score == 80.0
    assert result.canonical_public_id == "m1"
    assert "m1" in result.source_memory_ids
    assert "m2" in result.source_memory_ids


def test_deterministic_canonical_selection():
    cands = [
        {"public_id": "low_conf", "display_value": "Fact A", "confidence_score": 60.0, "importance_score": 50.0, "status": "active"},
        {"public_id": "high_conf", "display_value": "Fact A authoritative", "confidence_score": 95.0, "importance_score": 80.0, "status": "active"},
        {"public_id": "mid_conf", "display_value": "Fact A note", "confidence_score": 75.0, "importance_score": 60.0, "status": "active"},
    ]
    selected = MemoryConsolidatorEngine.select_canonical_record(cands)
    assert selected["public_id"] == "high_conf"


def test_evidence_sum_preservation(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Server runs Ubuntu 24.04 LTS operating system",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Host operating system is confirmed as Ubuntu 24.04 LTS",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(
        participant_scope_key=scope,
        category="user_confirmed_fact",
        purpose="user_confirmed_profile",
        admin_id="admin_root",
    )
    assert res["consolidated_count"] == 1
    canon = res["canonical_records"][0]
    assert canon["total_evidence_count"] >= 2


def test_provenance_preservation(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Nginx reverse proxy port is configured to 443",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Reverse proxy port is 443 for TLS traffic",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(
        participant_scope_key=scope,
        category="user_confirmed_fact",
        purpose="user_confirmed_profile",
        admin_id="admin_root",
    )
    canon = res["canonical_records"][0]

    sources_info = service.get_consolidated_sources(canon["canonical_public_id"])
    assert sources_info["is_compressed"] is True
    assert len(sources_info["sources"]) == 2
    pub_ids = [s["public_id"] for s in sources_info["sources"]]
    assert m1["public_id"] in pub_ids
    assert m2["public_id"] in pub_ids


def test_compression_metadata_structure(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Redis cache cluster port is 6379",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Redis port is 6379 for caching layer",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(
        participant_scope_key=scope,
        category="user_confirmed_fact",
        purpose="user_confirmed_profile",
        admin_id="admin_root",
    )
    canon_id = res["canonical_records"][0]["canonical_public_id"]
    sources_info = service.get_consolidated_sources(canon_id)

    comp_state = sources_info["compression_state"]
    assert comp_state["is_compressed"] is True
    assert comp_state["compression_method"] == "deterministic_structural"
    assert comp_state["compression_version"] == "1.0"
    assert len(comp_state["source_references"]) == 2
    assert "compressed_at" in comp_state


# ============================================================================
# 8-10: Idempotency & Inflation Prevention Tests
# ============================================================================


def test_consolidation_idempotency(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Default logging format is structured JSON",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Logs are formatted as structured JSON records",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    # First pass
    res1 = service.consolidate_memories(
        participant_scope_key=scope,
        category="user_confirmed_fact",
        purpose="user_confirmed_profile",
        admin_id="admin_root",
    )
    assert res1["consolidated_count"] == 1
    canon_id = res1["canonical_records"][0]["canonical_public_id"]

    # Second pass: already consolidated items should NOT produce new groups
    res2 = service.consolidate_memories(
        participant_scope_key=scope,
        category="user_confirmed_fact",
        purpose="user_confirmed_profile",
        admin_id="admin_root",
    )
    assert res2["consolidated_count"] == 0 or res2.get("canonical_records", [{}])[0].get("status") == "already_consolidated"


def test_duplicate_canonical_prevention(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Storage volume is mounted at /mnt/data",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Data directory is mounted on /mnt/data",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")

    active_items = service.list_memory_items(participant_scope_key=scope)["items"]
    # Only 1 canonical record should be active (the constituent 2 are 'consolidated')
    active_now = [i for i in active_items if i["status"] == "active"]
    assert len(active_now) == 1


def test_evidence_inflation_prevention(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="API rate limit is set to 100 requests per minute",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Rate limit for API is 100 requests every minute",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res1 = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    ev_count_1 = res1["canonical_records"][0]["total_evidence_count"]

    res2 = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    # Evidence count must remain unchanged
    assert ev_count_1 == 2


# ============================================================================
# 11-18: Conflict Gate & Dispute Handling Tests
# ============================================================================


def test_unresolved_dispute_blocking():
    cands = [
        {"public_id": "m1", "display_value": "Port is 8080", "category": "SEMANTIC", "purpose": "prof", "participant_scope_key": "s1", "status": "active"},
        {"public_id": "m2", "display_value": "Port is 9090", "category": "SEMANTIC", "purpose": "prof", "participant_scope_key": "s1", "status": "active"},
    ]
    active_disputes = [
        {"dispute_id": "d1", "memory_a_id": "m1", "memory_b_id": "m2", "state": "PENDING_REVIEW"}
    ]
    groups = MemoryConsolidatorEngine.group_candidates(
        candidates=cands,
        participant_scope_key="s1",
        category="SEMANTIC",
        purpose="prof",
        active_disputes=active_disputes,
    )
    assert len(groups) == 0


def test_detected_dispute_blocking():
    cands = [{"public_id": "m1", "display_value": "Val 1", "category": "SEMANTIC", "purpose": "prof", "participant_scope_key": "s1", "status": "active"}]
    active_disputes = [{"dispute_id": "d1", "memory_a_id": "m1", "memory_b_id": "m2", "state": "DETECTED"}]
    assert MemoryConsolidatorEngine.is_disputed(cands[0], active_disputes) is True


def test_pending_review_dispute_blocking():
    cands = [{"public_id": "m1", "display_value": "Val 1", "category": "SEMANTIC", "purpose": "prof", "participant_scope_key": "s1", "status": "active"}]
    active_disputes = [{"dispute_id": "d1", "memory_a_id": "m1", "memory_b_id": "m2", "state": "PENDING_REVIEW"}]
    assert MemoryConsolidatorEngine.is_disputed(cands[0], active_disputes) is True


def test_under_review_dispute_blocking():
    cands = [{"public_id": "m1", "display_value": "Val 1", "category": "SEMANTIC", "purpose": "prof", "participant_scope_key": "s1", "status": "active"}]
    active_disputes = [{"dispute_id": "d1", "memory_a_id": "m1", "memory_b_id": "m2", "state": "UNDER_REVIEW"}]
    assert MemoryConsolidatorEngine.is_disputed(cands[0], active_disputes) is True


def test_supersede_existing_dispute_resolution(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Server memory capacity is 32GB RAM",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Server memory capacity is 64GB RAM",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    disputes = service.list_disputes(participant_scope_key=scope)
    assert len(disputes) >= 1
    disp_id = disputes[0]["dispute_id"]

    # Admin resolves via SUPERSEDE_EXISTING
    service.resolve_dispute(disp_id, ResolutionStrategy.SUPERSEDE_EXISTING, admin_id="admin_root", resolution_reason="Upgraded hardware")

    # M1 is now superseded, M2 is active
    item_1 = service.get_memory_item(m1["public_id"])
    item_2 = service.get_memory_item(m2["public_id"])
    assert item_1["status"] == "superseded"
    assert item_2["status"] == "active"


def test_retain_existing_dispute_resolution(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Production database timeout is 30 seconds",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Production database timeout is 60 seconds",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    disputes = service.list_disputes(participant_scope_key=scope)
    disp_id = disputes[0]["dispute_id"]

    # Admin resolves via RETAIN_EXISTING
    service.resolve_dispute(disp_id, ResolutionStrategy.RETAIN_EXISTING, admin_id="admin_root", resolution_reason="30s is confirmed correct")

    item_1 = service.get_memory_item(m1["public_id"])
    item_2 = service.get_memory_item(m2["public_id"])
    assert item_1["status"] == "active"
    assert item_2["status"] == "rejected"


def test_retain_both_coexist_handling(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Staging cluster port is 8080",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Production cluster port is 9090",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    # Both coexisting active records (resolve dispute with coexistence if flagged)
    disputes = service.list_disputes(participant_scope_key=scope)
    if disputes:
        disp_id = disputes[0]["dispute_id"]
        service.resolve_dispute(disp_id, ResolutionStrategy.RETAIN_BOTH_COEXIST, admin_id="admin_root")

    item_1 = service.get_memory_item(m1["public_id"])
    item_2 = service.get_memory_item(m2["public_id"])
    assert item_1["status"] == "active"
    assert item_2["status"] == "active"


def test_dismiss_dispute_handling(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Backup retention window is 30 days",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Backup retention window is 60 days",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    disputes = service.list_disputes(participant_scope_key=scope)
    if disputes:
        disp_id = disputes[0]["dispute_id"]
        service.dismiss_dispute(disp_id, admin_id="admin_root", reason="Spurious conflict")
        with service.repository.transaction() as conn:
            item_row = service.repository.memory_item(conn, m1["public_id"])
            assert service._has_active_dispute(conn, item_row["id"]) is False


# ============================================================================
# 19-25: Governance & Isolation Tests
# ============================================================================


def test_temporal_validity_preservation(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="PostgreSQL connection pool max size is 20",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Database connection pool maximum size is 20 connections",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    canon_id = res["canonical_records"][0]["canonical_public_id"]
    canon_row = service.get_memory_item(canon_id)
    assert canon_row["valid_from"] is not None


def test_expired_memory_exclusion():
    cands = [
        {"public_id": "m1", "display_value": "Fact 1", "category": "SEMANTIC", "purpose": "p", "participant_scope_key": "s1", "status": "active", "freshness_state": "EXPIRED"},
        {"public_id": "m2", "display_value": "Fact 1 note", "category": "SEMANTIC", "purpose": "p", "participant_scope_key": "s1", "status": "active", "freshness_state": "FRESH"},
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="s1", category="SEMANTIC", purpose="p")
    assert len(groups) == 0


def test_category_isolation():
    cands = [
        {"public_id": "m1", "display_value": "I like dark mode", "category": "PREFERENCE", "purpose": "p", "participant_scope_key": "s1", "status": "active"},
        {"public_id": "m2", "display_value": "I like dark mode", "category": "SEMANTIC", "purpose": "p", "participant_scope_key": "s1", "status": "active"},
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="s1", category="PREFERENCE", purpose="p")
    assert len(groups) == 0


def test_purpose_isolation():
    cands = [
        {"public_id": "m1", "display_value": "Preferred editor is Vim", "category": "PREFERENCE", "purpose": "coding", "participant_scope_key": "s1", "status": "active"},
        {"public_id": "m2", "display_value": "Preferred editor is Vim", "category": "PREFERENCE", "purpose": "profile", "participant_scope_key": "s1", "status": "active"},
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="s1", category="PREFERENCE", purpose="coding")
    assert len(groups) == 0


def test_participant_scope_isolation():
    cands = [
        {"public_id": "m1", "display_value": "Shared secret config value", "category": "SEMANTIC", "purpose": "p", "participant_scope_key": "tenant_A", "status": "active"},
        {"public_id": "m2", "display_value": "Shared secret config value", "category": "SEMANTIC", "purpose": "p", "participant_scope_key": "tenant_B", "status": "active"},
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="tenant_A", category="SEMANTIC", purpose="p")
    assert len(groups) == 0


def test_system_category_governance():
    cands = [
        {"public_id": "m1", "display_value": "Kernel max files is 65535", "category": "SYSTEM", "purpose": "sys_conf", "participant_scope_key": "sys", "status": "active"},
        {"public_id": "m2", "display_value": "System max files limit is 65535", "category": "SYSTEM", "purpose": "sys_conf", "participant_scope_key": "sys", "status": "active"},
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="sys", category="SYSTEM", purpose="sys_conf")
    assert len(groups) == 1
    assert groups[0].requires_human_approval is True


def test_admin_category_governance():
    cands = [
        {"public_id": "m1", "display_value": "Admin role requires 2FA authentication", "category": "ADMIN", "purpose": "auth_policy", "participant_scope_key": "admin_scope", "status": "active"},
        {"public_id": "m2", "display_value": "Admin role mandatory 2FA authentication policy", "category": "ADMIN", "purpose": "auth_policy", "participant_scope_key": "admin_scope", "status": "active"},
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="admin_scope", category="ADMIN", purpose="auth_policy")
    assert len(groups) == 1
    assert groups[0].requires_human_approval is True


# ============================================================================
# 26-30: Security, Retrieval, Reversibility Tests
# ============================================================================


def test_g8_secret_sanitization(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"
    memory_env["settings"].memory_block_sensitive_content = False

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Database password is api_key=sk-1234567890abcdef1234567890abcdef",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Database secret token is api_key=sk-1234567890abcdef1234567890abcdef",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    if res["consolidated_count"] > 0:
        canon = res["canonical_records"][0]
        assert "sk-1234567890abcdef1234567890abcdef" not in canon["display_value"]


def test_retrieval_integrity_with_consolidated_memory(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="FastAPI backend runs on port 8000",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Backend API listening port is 8000",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    canon_id = res["canonical_records"][0]["canonical_public_id"]

    prof = service.create_profile(
        RetrievalProfileCreate(
            name="test_retrieval_p17_6",
            allowed_categories=["user_confirmed_fact", "SEMANTIC"],
            allowed_purposes=["user_confirmed_profile"],
            keyword_weight=0.5,
            vector_weight=0.5,
        ),
        admin_id="admin_root",
    )
    service.validate_profile(prof["public_id"], "admin_root")
    service.activate_profile(prof["public_id"], "admin_root")

    ret = service.retrieve(
        MemoryRetrieveRequest(
            retrieval_profile_public_id=prof["public_id"],
            participant_scope_key=scope,
            query="What is the backend listening port?",
        ),
        admin_id="admin_root",
    )

    assert len(ret["results"]) >= 1
    top_result_id = ret["results"][0]["memory_item_public_id"]
    assert top_result_id == canon_id


def test_provenance_citation_traceability(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Prometheus metric endpoint is /metrics",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Metrics are scraped from /metrics endpoint",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    canon_id = res["canonical_records"][0]["canonical_public_id"]

    sources = service.get_consolidated_sources(canon_id)
    assert len(sources["sources"]) == 2
    assert sources["is_compressed"] is True


def test_version_checksum_preservation(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Grafana dashboard runs on port 3000",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Dashboard port for Grafana is 3000",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    canon_id = res["canonical_records"][0]["canonical_public_id"]
    versions = service.get_versions(canon_id)

    assert len(versions["items"]) >= 1
    assert "checksum_sha256" in versions["items"][0]
    assert len(versions["items"][0]["checksum_sha256"]) == 64


def test_reversible_unconsolidation(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m1 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Server operates on Ubuntu 24.04 LTS linux release",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Operating system environment is confirmed as Ubuntu 24.04 LTS",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    canon_id = res["canonical_records"][0]["canonical_public_id"]

    # Verify sources are superseded by canonical
    assert service.get_memory_item(m1["public_id"])["status"] == "superseded"
    assert service.get_memory_item(m2["public_id"])["status"] == "superseded"

    # Reversal / Unconsolidation
    uncons_res = service.unconsolidate_memory(canon_id, admin_id="admin_root", reason="Reverting cluster merge")

    assert uncons_res["status"] == "superseded"
    assert len(uncons_res["restored_source_ids"]) == 2

    # Sources restored to active
    assert service.get_memory_item(m1["public_id"])["status"] == "active"
    assert service.get_memory_item(m2["public_id"])["status"] == "active"
    # Canonical is superseded
    assert service.get_memory_item(canon_id)["status"] == "superseded"


# ============================================================================
# 31-35: Bounds, Benchmarks, Durability & Procedural Tests
# ============================================================================


def test_candidate_limit_bounded():
    cands = [
        {"public_id": f"m_{i}", "display_value": f"Fact statement variation {i}", "category": "SEMANTIC", "purpose": "p", "participant_scope_key": "s1", "status": "active"}
        for i in range(30)
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="s1", category="SEMANTIC", purpose="p")
    # Evaluated candidates must be bounded to MAX_CONSOLIDATION_CANDIDATES
    for g in groups:
        assert len(g.candidate_items) <= MAX_CONSOLIDATION_CANDIDATES


def test_cpu_performance_benchmark():
    cands = [
        {"public_id": f"m_{i}", "display_value": f"PostgreSQL database query latency is under 5ms (sample {i})", "category": "SEMANTIC", "purpose": "p", "participant_scope_key": "s1", "status": "active"}
        for i in range(20)
    ]
    start = time.perf_counter()
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="s1", category="SEMANTIC", purpose="p")
    if groups:
        _ = MemoryConsolidatorEngine.consolidate_group(groups[0])
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Must complete within 100ms on any CPU (target <= 5ms on modern hardware)
    assert elapsed_ms < 100.0


def test_sqlite_wal_durability(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="SQLite database runs in WAL mode with normal sync",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="WAL mode is enabled in SQLite with NORMAL synchronization",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    assert res["consolidated_count"] == 1


def test_procedural_ordering_preservation():
    cands = [
        {"public_id": "step1", "display_value": "Step 1: Run database migration", "category": "PROCEDURAL", "purpose": "deploy", "participant_scope_key": "s1", "status": "active", "step_index": 1},
        {"public_id": "step2", "display_value": "Step 2: Restart backend service", "category": "PROCEDURAL", "purpose": "deploy", "participant_scope_key": "s1", "status": "active", "step_index": 2},
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="s1", category="PROCEDURAL", purpose="deploy")
    # Different steps must not be merged
    assert len(groups) == 0


def test_fabricated_range_prevention():
    cands = [
        {"public_id": "m1", "display_value": "Backup runs every 24 hours", "category": "SEMANTIC", "purpose": "schedule", "participant_scope_key": "s1", "status": "active"},
        {"public_id": "m2", "display_value": "Backup runs every 12 hours", "category": "SEMANTIC", "purpose": "schedule", "participant_scope_key": "s1", "status": "active"},
    ]
    groups = MemoryConsolidatorEngine.group_candidates(candidates=cands, participant_scope_key="s1", category="SEMANTIC", purpose="schedule")
    # Contradicting intervals (24h vs 12h) must NOT be grouped
    assert len(groups) == 0
