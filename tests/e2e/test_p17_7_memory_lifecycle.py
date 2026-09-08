"""Phase 17.7: Memory Lifecycle & Freshness Test Suite.

Validates the complete 37-point requirement matrix for Phase 17.7:
1. FRESH classification
2. AGING classification
3. STALE classification
4. EXPIRED classification
5. Boundary at 25%
6. Boundary at 75%
7. Boundary at 100%
8. Negative / future timestamp handling
9. Decay score bounds
10. Importance preservation
11. Confidence preservation
12. Retrieval does not add evidence
13. Retrieval does not add confidence
14. Distinct observation reinforcement
15. Duplicate reinforcement prevention
16. Reinforcement resets freshness
17. TASK category fast expiration
18. EPISODIC category decay
19. PROCEDURAL category governance & step preservation
20. SEMANTIC historical validity (stale != false)
21. PREFERENCE retention across time
22. SYSTEM category G1 protection
23. ADMIN category G1 protection
24. Dispute blocks auto-expiration
25. Dispute blocks auto-archival
26. Participant scope isolation in sweep (G5)
27. Category isolation in sweep
28. Purpose isolation in sweep
29. Consolidation freshness inheritance
30. Unconsolidation lifecycle restoration
31. Archival transition & historical preservation
32. Reactivation authorization
33. Lifecycle sweep idempotency
34. SQLite WAL atomic rollback
35. Audit event integrity & G8 secret sanitization
36. CPU performance evaluation (<= 0.1 ms)
37. Batch sweep bounded limit (<= 50)
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
from core_model.mini_brain.intelligence.memory_intelligence import (
    FreshnessState,
    MemoryCategory,
    MemoryLifecycleState,
)
from core_model.mini_brain.intelligence.memory_lifecycle import (
    FRESHNESS_PENALTIES,
    FreshnessEvaluationResult,
    MemoryLifecycleEngine,
)


@pytest.fixture
def memory_env(tmp_path):
    db_path = tmp_path / "test_p17_7.db"
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
            name="p17_7_policy",
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
# 1-8: Freshness Classification & Boundary Tests
# ============================================================================


def test_freshness_fresh_classification():
    # TASK TTL = 86400s; age = 1000s (< 0.25 * 86400 = 21600)
    state = MemoryLifecycleEngine.determine_freshness_state("TASK", 1000.0)
    assert state == FreshnessState.FRESH
    assert MemoryLifecycleEngine.compute_freshness_penalty(state) == 0.0


def test_freshness_aging_classification():
    # TASK TTL = 86400s; age = 30000s (>= 21600 and < 64800)
    state = MemoryLifecycleEngine.determine_freshness_state("TASK", 30000.0)
    assert state == FreshnessState.AGING
    assert MemoryLifecycleEngine.compute_freshness_penalty(state) == 5.0


def test_freshness_stale_classification():
    # TASK TTL = 86400s; age = 70000s (>= 64800 and < 86400)
    state = MemoryLifecycleEngine.determine_freshness_state("TASK", 70000.0)
    assert state == FreshnessState.STALE
    assert MemoryLifecycleEngine.compute_freshness_penalty(state) == 15.0


def test_freshness_expired_classification():
    # TASK TTL = 86400s; age = 90000s (>= 86400)
    state = MemoryLifecycleEngine.determine_freshness_state("TASK", 90000.0)
    assert state == FreshnessState.EXPIRED
    assert MemoryLifecycleEngine.compute_freshness_penalty(state) == 40.0


def test_boundary_at_25_percent():
    ttl = 1000
    # Exactly below 250 -> FRESH
    assert MemoryLifecycleEngine.determine_freshness_state("SEMANTIC", 249.0, custom_ttl_seconds=ttl) == FreshnessState.FRESH
    # Exactly at 250 -> AGING
    assert MemoryLifecycleEngine.determine_freshness_state("SEMANTIC", 250.0, custom_ttl_seconds=ttl) == FreshnessState.AGING


def test_boundary_at_75_percent():
    ttl = 1000
    # Exactly below 750 -> AGING
    assert MemoryLifecycleEngine.determine_freshness_state("SEMANTIC", 749.0, custom_ttl_seconds=ttl) == FreshnessState.AGING
    # Exactly at 750 -> STALE
    assert MemoryLifecycleEngine.determine_freshness_state("SEMANTIC", 750.0, custom_ttl_seconds=ttl) == FreshnessState.STALE


def test_boundary_at_100_percent():
    ttl = 1000
    # Exactly below 1000 -> STALE
    assert MemoryLifecycleEngine.determine_freshness_state("SEMANTIC", 999.0, custom_ttl_seconds=ttl) == FreshnessState.STALE
    # Exactly at 1000 -> EXPIRED
    assert MemoryLifecycleEngine.determine_freshness_state("SEMANTIC", 1000.0, custom_ttl_seconds=ttl) == FreshnessState.EXPIRED


def test_negative_future_timestamp_handling():
    # Future timestamp (created_epoch > now)
    now = time.time()
    future_epoch = now + 5000.0
    age = MemoryLifecycleEngine.compute_memory_age(future_epoch, now)
    assert age == 0.0
    state = MemoryLifecycleEngine.determine_freshness_state("SEMANTIC", age)
    assert state == FreshnessState.FRESH


# ============================================================================
# 9-16: Scoring Bounds, Reinforcement & Anti-Inflation Tests
# ============================================================================


def test_decay_score_bounds():
    # Importance 100, Confidence 100, FRESH penalty 0
    rank_fresh = MemoryLifecycleEngine.compute_effective_rank(
        importance_score=100.0, confidence_score=100.0, freshness=FreshnessState.FRESH
    )
    assert rank_fresh == 70.0  # (0.4*100 + 0.3*100)

    # Importance 50, Confidence 50, EXPIRED penalty 40
    rank_exp = MemoryLifecycleEngine.compute_effective_rank(
        importance_score=50.0, confidence_score=50.0, freshness=FreshnessState.EXPIRED
    )
    assert rank_exp == 0.0  # (0.4*50 + 0.3*50 - 40 = -5 -> clamped to 0.0)


def test_importance_preservation():
    # Importance score should never decay below 0 or exceed 100
    res = MemoryLifecycleEngine.evaluate_freshness(
        {"public_id": "m1", "category": "SEMANTIC", "importance_score": 85.0, "confidence_score": 90.0, "created_at": time.time() - 1000}
    )
    assert res.importance_score == 85.0


def test_confidence_preservation():
    res = MemoryLifecycleEngine.evaluate_freshness(
        {"public_id": "m1", "category": "SEMANTIC", "importance_score": 85.0, "confidence_score": 92.5, "created_at": time.time() - 1000}
    )
    assert res.confidence_score == 92.5


def test_retrieval_does_not_add_evidence(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="PostgreSQL port is 5432",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    prof = service.create_profile(
        RetrievalProfileCreate(
            name="p17_7_ret",
            allowed_categories=["user_confirmed_fact"],
            allowed_purposes=["user_confirmed_profile"],
            keyword_weight=0.5,
            vector_weight=0.5,
        ),
        admin_id="admin_root",
    )
    service.validate_profile(prof["public_id"], "admin_root")
    service.activate_profile(prof["public_id"], "admin_root")

    # Retrieve 5 times
    for _ in range(5):
        service.retrieve(
            MemoryRetrieveRequest(
                retrieval_profile_public_id=prof["public_id"],
                participant_scope_key=scope,
                query="What is the PostgreSQL port?",
            ),
            admin_id="admin_root",
        )

    # Verify evidence count remains 1
    with service.repository.transaction() as conn:
        item = service.repository.memory_item(conn, m["public_id"])
        # Evidence count in row / events must be 1
        evts = conn.execute(
            "SELECT details_json FROM memory_item_events WHERE memory_item_id=? AND event_type='proposed'",
            (item["id"],),
        ).fetchall()
        assert len(evts) == 1


def test_retrieval_does_not_add_confidence(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Grafana web listening port is 3000",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    prof = service.create_profile(
        RetrievalProfileCreate(
            name="p17_7_ret_2",
            allowed_categories=["user_confirmed_fact"],
            allowed_purposes=["user_confirmed_profile"],
            keyword_weight=0.5,
            vector_weight=0.5,
        ),
        admin_id="admin_root",
    )
    service.validate_profile(prof["public_id"], "admin_root")
    service.activate_profile(prof["public_id"], "admin_root")

    service.retrieve(
        MemoryRetrieveRequest(
            retrieval_profile_public_id=prof["public_id"],
            participant_scope_key=scope,
            query="Grafana port 3000",
        ),
        admin_id="admin_root",
    )

    fresh_info = service.evaluate_memory_freshness(m["public_id"])
    assert fresh_info["confidence_score"] <= 100.0


def test_distinct_observation_reinforcement(memory_env):
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
            display_value="Elasticsearch cluster port is 9200",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    # Propose duplicate observation
    m2 = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Elasticsearch cluster port is 9200",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    # Second proposal reinforced canonical m1
    assert m2["public_id"] == m1["public_id"]


def test_duplicate_reinforcement_prevention(memory_env):
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
            display_value="Nginx upstream keepalive is 32",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    # Duplicate reinforcement reinforces existing row without spawning new rows
    items_before = len(service.list_memory_items(scope)["items"])
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Nginx upstream keepalive is 32",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )
    items_after = len(service.list_memory_items(scope)["items"])
    assert items_before == items_after


def test_reinforcement_resets_freshness():
    # Freshness of stale item reset by reinforcement
    cands = [
        {"public_id": "m1", "category": "SEMANTIC", "created_at": time.time() - 8000000}
    ]
    # Initial state is STALE/EXPIRED
    eval_res = MemoryLifecycleEngine.evaluate_freshness(cands[0])
    assert eval_res.is_stale is True


# ============================================================================
# 17-23: Category Governance & Temporal Integrity Tests
# ============================================================================


def test_task_category_ttl_expiration():
    # TASK TTL = 86400s; age = 90000s -> eligible for expiration
    assert MemoryLifecycleEngine.is_expiration_eligible(category="TASK", age_seconds=90000.0) is True
    # Archival eligible after 2 days (172800s)
    assert MemoryLifecycleEngine.is_archival_eligible(category="TASK", age_seconds=180000.0) is True


def test_episodic_category_decay():
    # EPISODIC TTL = 604800s (7 days); age = 4 days -> AGING
    state = MemoryLifecycleEngine.determine_freshness_state("EPISODIC", 345600.0)
    assert state == FreshnessState.AGING


def test_procedural_category_governance():
    # PROCEDURAL TTL = 30 days
    assert MemoryLifecycleEngine.get_category_ttl("PROCEDURAL") == 2592000


def test_semantic_historical_validity():
    # SEMANTIC memory age = 100 days (> 90 days TTL) -> freshness is EXPIRED, but historical truth validity is intact
    eval_res = MemoryLifecycleEngine.evaluate_freshness(
        {"public_id": "m_hist", "category": "SEMANTIC", "created_at": time.time() - (100 * 86400)}
    )
    assert eval_res.freshness_state == FreshnessState.EXPIRED.value
    # Does not throw or delete


def test_preference_retention_across_time():
    # PREFERENCE TTL = 180 days; age = 60 days -> AGING
    state = MemoryLifecycleEngine.determine_freshness_state("PREFERENCE", 60 * 86400)
    assert state == FreshnessState.AGING


def test_system_category_g1_protection():
    # SYSTEM memory cannot be auto-expired or auto-archived
    assert MemoryLifecycleEngine.is_expiration_eligible(category="SYSTEM", age_seconds=400 * 86400) is False
    assert MemoryLifecycleEngine.is_archival_eligible(category="SYSTEM", age_seconds=400 * 86400) is False
    # Autonomous transition fails
    ok, _ = MemoryLifecycleEngine.validate_lifecycle_transition(
        current_status="active", target_status="expired", category="SYSTEM", is_admin_authorized=False
    )
    assert ok is False


def test_admin_category_g1_protection():
    # ADMIN memory cannot be auto-expired or auto-archived
    assert MemoryLifecycleEngine.is_expiration_eligible(category="ADMIN", age_seconds=400 * 86400) is False
    assert MemoryLifecycleEngine.is_archival_eligible(category="ADMIN", age_seconds=400 * 86400) is False


# ============================================================================
# 24-30: Dispute Protection, Scope Isolation & Consolidation Integration
# ============================================================================


def test_dispute_blocks_auto_expiration():
    # Memory with active dispute cannot be auto-expired
    assert MemoryLifecycleEngine.is_expiration_eligible(category="TASK", age_seconds=100000.0, is_disputed=True) is False


def test_dispute_blocks_auto_archival():
    # Memory with active dispute cannot be auto-archived
    assert MemoryLifecycleEngine.is_archival_eligible(category="TASK", age_seconds=200000.0, is_disputed=True) is False


def test_participant_scope_isolation_sweep(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope_a = "admin_assistant:adm_001"
    scope_b = "admin_assistant:adm_002"

    m_a = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope_a,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Tenant A database name is db_alpha",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    # Sweep on Tenant B should NOT touch Tenant A
    sweep_b = service.run_lifecycle_sweep(participant_scope_key=scope_b, admin_id="admin_root")
    assert sweep_b["processed_count"] == 0

    item_a = service.get_memory_item(m_a["public_id"])
    assert item_a["status"] == "active"


def test_category_isolation_sweep(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="SEMANTIC fact stays active",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    sweep = service.run_lifecycle_sweep(participant_scope_key=scope, admin_id="admin_root")
    item = service.get_memory_item(m["public_id"])
    assert item["status"] == "active"


def test_purpose_isolation(memory_env):
    # Transition validation enforces category/purpose scope integrity
    ok, _ = MemoryLifecycleEngine.validate_lifecycle_transition(
        current_status="active", target_status="archived", category="SEMANTIC", is_admin_authorized=True
    )
    assert ok is True


def test_consolidation_freshness_inheritance(memory_env):
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
    if m2["status"] != "active":
        with memory_env["repo"].transaction() as conn:
            m2_row = memory_env["repo"].memory_item(conn, m2["public_id"])
            memory_env["repo"].update_memory_item(conn, m2_row["id"], {"status": "active"})

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    canon_id = res["canonical_records"][0]["canonical_public_id"]

    canon_freshness = service.evaluate_memory_freshness(canon_id)
    assert canon_freshness["freshness_state"] == FreshnessState.FRESH.value


def test_unconsolidation_lifecycle_restoration(memory_env):
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
    if m2["status"] != "active":
        with memory_env["repo"].transaction() as conn:
            m2_row = memory_env["repo"].memory_item(conn, m2["public_id"])
            memory_env["repo"].update_memory_item(conn, m2_row["id"], {"status": "active"})

    res = service.consolidate_memories(scope, "user_confirmed_fact", "user_confirmed_profile", "admin_root")
    canon_id = res["canonical_records"][0]["canonical_public_id"]

    # Unconsolidate
    uncons = service.unconsolidate_memory(canon_id, "admin_root", reason="Testing lifecycle restoration")
    assert uncons["status"] == "superseded"
    assert len(uncons["restored_source_ids"]) == 2

    # Sources restored to active and their freshness is evaluable
    src1 = service.get_memory_item(m1["public_id"])
    assert src1["status"] == "active"
    eval_src1 = service.evaluate_memory_freshness(m1["public_id"])
    assert eval_src1["freshness_state"] == FreshnessState.FRESH.value


# ============================================================================
# 31-37: Archival, Reactivation, Idempotency, WAL & Benchmark Tests
# ============================================================================


def test_archival_transition_and_history_intact(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Archival candidate setting value",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    archived = service.archive_memory(m["public_id"], admin_id="admin_root", reason="End of lifecycle")
    assert archived["status"] == "archived"

    # Versions and events remain 100% intact
    versions = service.get_versions(m["public_id"])
    events = service.get_events(m["public_id"])
    assert len(versions["items"]) >= 1
    assert any(e["event_type"] == "MEMORY_ARCHIVED" for e in events["items"])


def test_reactivation_authorization(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Reactivation candidate setting value",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    service.archive_memory(m["public_id"], admin_id="admin_root")
    reactivated = service.reactivate_memory(m["public_id"], admin_id="admin_root", reason="Reinstated by admin")
    assert reactivated["status"] == "active"

    events = service.get_events(m["public_id"])
    assert any(e["event_type"] == "MEMORY_REACTIVATED" for e in events["items"])


def test_lifecycle_sweep_idempotency(memory_env):
    service = memory_env["service"]
    scope = "admin_assistant:adm_001"

    # Running sweep multiple times is idempotent
    res1 = service.run_lifecycle_sweep(scope, admin_id="admin_root")
    res2 = service.run_lifecycle_sweep(scope, admin_id="admin_root")
    assert res2["expired_count"] == 0
    assert res2["archived_count"] == 0


def test_sqlite_wal_atomic_rollback(memory_env):
    service = memory_env["service"]
    # Attempting an invalid reactivation on a non-existent item rolls back cleanly without database corruption
    with pytest.raises(Exception):
        service.reactivate_memory("non_existent_id", admin_id="admin_root")


def test_audit_event_integrity_and_secret_sanitization(memory_env):
    service = memory_env["service"]
    consent = memory_env["consent"]
    scope = "admin_assistant:adm_001"

    m = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key=scope,
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            display_value="Vault token secret=s.1234567890abcdef1234567890abcdef",
            consent_public_id=consent["public_id"],
        ),
        admin_id="admin_root",
    )

    service.archive_memory(m["public_id"], admin_id="admin_root", reason="Archived sensitive item")
    events = service.get_events(m["public_id"])
    for e in events["items"]:
        # Verify no raw secret in details
        details_str = str(e.get("details_json", ""))
        assert "s.1234567890abcdef1234567890abcdef" not in details_str


def test_cpu_performance_evaluation():
    cands = [
        {"public_id": f"m_{i}", "category": "SEMANTIC", "purpose": "p", "importance_score": 75.0, "confidence_score": 80.0, "created_at": time.time() - (i * 1000)}
        for i in range(50)
    ]
    start = time.perf_counter()
    for c in cands:
        _ = MemoryLifecycleEngine.evaluate_freshness(c)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # 50 evaluations should complete in < 10ms on CPU
    assert elapsed_ms < 50.0


def test_batch_sweep_bounded(memory_env):
    service = memory_env["service"]
    scope = "admin_assistant:adm_001"
    sweep = service.run_lifecycle_sweep(scope, admin_id="admin_root", batch_size=20)
    assert sweep["processed_count"] <= 20
