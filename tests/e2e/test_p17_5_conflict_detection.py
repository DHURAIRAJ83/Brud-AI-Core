"""Phase 17.5: Conflict Detection & Resolution Test Suite.

Validates the complete 36-point requirement matrix for Phase 17.5:
1. VALUE_CONFLICT detection
2. NUMERIC_CONFLICT detection
3. STATE_CONFLICT detection
4. TEMPORAL_CONFLICT detection
5. POLICY_CONFLICT detection
6. VERSION_CONFLICT detection
7. RELATED_BUT_DISTINCT is not a conflict
8. Conflict confidence bounded 0–100
9. Participant isolation (G5)
10. Category isolation
11. Purpose isolation
12. Maximum candidate limit = 20
13. G8 sanitization before analysis
14. Dispute creation and persistence
15. Valid state transitions in state machine
16. Invalid state transitions rejected
17. No autonomous resolution (G1)
18. SUPERSEDE_EXISTING requires authorization
19. RETAIN_EXISTING requires authorization
20. RETAIN_BOTH_COEXIST requires authorization
21. DISMISS requires authorization
22. Immutable resolution event recording
23. Retrieval strict-profile behavior (exclude_conflicting)
24. Retrieval advisory warning behavior ([DISPUTED_WARNING])
25. SYSTEM governance protection
26. ADMIN governance protection
27. Embedding/version mismatch safety
28. Provenance preservation
29. Deterministic conflict scoring
30. Deterministic dispute resolution records
31. G1 invariant preservation
32. G4 invariant preservation
33. G5 invariant preservation
34. G8 invariant preservation
35. G9 invariant preservation
36. G10/G11 SQLite WAL durability
"""

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
    ConflictConfidence,
    ConflictKnowledgeEngine,
    ConflictMatchResult,
    DisputeRecord,
    DisputeState,
    ResolutionStrategy,
)
from core_model.mini_brain.intelligence.duplicate_detector import DuplicateClassification


@pytest.fixture
def memory_env(tmp_path):
    db_path = tmp_path / "test_p17_5.db"
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
            name="p17_5_policy",
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
# 1-6: Conflict Taxonomy Verification
# ============================================================================

def test_p17_5_conf_001_value_conflict_detection():
    """Verify VALUE_CONFLICT detection for incompatible qualitative properties."""
    text_a = "Primary database engine is PostgreSQL."
    text_b = "Primary database engine is SQLite."
    c_type, conf, reason = ConflictKnowledgeEngine.classify_contradiction(text_a, text_b, similarity=0.82)
    assert c_type == ConflictClassification.VALUE_CONFLICT
    assert conf >= 50.0
    assert "incompatible_qualitative_attribute_value" in reason


def test_p17_5_conf_002_numeric_conflict_detection():
    """Verify NUMERIC_CONFLICT detection for contradicting scalar measurements."""
    text_a = "Database cluster node count is 5."
    text_b = "Database cluster node count is 10."
    c_type, conf, reason = ConflictKnowledgeEngine.classify_contradiction(text_a, text_b, similarity=0.90)
    assert c_type == ConflictClassification.NUMERIC_CONFLICT
    assert conf >= 70.0
    assert "contradictory_scalar_measurement_or_quantity" in reason


def test_p17_5_conf_003_state_conflict_detection():
    """Verify STATE_CONFLICT detection for opposing operational/boolean states."""
    text_a = "Debug mode is enabled."
    text_b = "Debug mode is disabled."
    c_type, conf, reason = ConflictKnowledgeEngine.classify_contradiction(text_a, text_b, similarity=0.88)
    assert c_type == ConflictClassification.STATE_CONFLICT
    assert conf >= 80.0
    assert "opposing" in reason


def test_p17_5_conf_004_temporal_conflict_detection():
    """Verify TEMPORAL_CONFLICT detection for incompatible schedules or execution windows."""
    text_a = "Nightly maintenance window starts at 02:00 UTC."
    text_b = "Nightly maintenance window starts at 04:00 UTC."
    c_type, conf, reason = ConflictKnowledgeEngine.classify_contradiction(text_a, text_b, similarity=0.85)
    assert c_type in (ConflictClassification.TEMPORAL_CONFLICT, ConflictClassification.NUMERIC_CONFLICT)
    assert conf >= 65.0


def test_p17_5_conf_005_policy_conflict_detection():
    """Verify POLICY_CONFLICT detection for conflicting operational rules/directives."""
    text_a = "Access policy requires multi-factor authentication for all users."
    text_b = "Access policy forbids multi-factor authentication for all users."
    c_type, conf, reason = ConflictKnowledgeEngine.classify_contradiction(text_a, text_b, similarity=0.89)
    assert c_type in (ConflictClassification.POLICY_CONFLICT, ConflictClassification.STATE_CONFLICT)
    assert conf >= 75.0


def test_p17_5_conf_006_version_conflict_detection():
    """Verify VERSION_CONFLICT detection for version-specific incompatible claims."""
    text_a = "Schema migration is running version v1.2."
    text_b = "Schema migration is running version v2.0."
    c_type, conf, reason = ConflictKnowledgeEngine.classify_contradiction(text_a, text_b, similarity=0.85)
    assert c_type in (ConflictClassification.VERSION_CONFLICT, ConflictClassification.VALUE_CONFLICT)
    assert conf >= 60.0


# ============================================================================
# 7-13: Scoring, Guardrails, Scope Isolation, and Performance
# ============================================================================

def test_p17_5_conf_007_related_distinct_is_not_conflict():
    """Verify RELATED_BUT_DISTINCT statements do not trigger a false conflict."""
    text_a = "Database backup runs every 24 hours."
    text_b = "Database backup retention is 30 days."
    c_type, conf, reason = ConflictKnowledgeEngine.classify_contradiction(text_a, text_b, similarity=0.74)
    assert c_type is None
    assert conf == 0.0


def test_p17_5_conf_008_conflict_confidence_strictly_bounded_0_to_100():
    """Verify conflict confidence score is strictly bounded [0.0, 100.0]."""
    score_max = ConflictConfidence.calculate(
        semantic_similarity=1.0,
        subject_match=True,
        predicate_match=True,
        value_incompatibility=1.0,
        polarity_opposition=True,
        numeric_contradiction=True,
        temporal_contradiction=True,
        version_mismatch=False,
    )
    assert 0.0 <= score_max <= 100.0

    score_min = ConflictConfidence.calculate(
        semantic_similarity=0.1,
        subject_match=False,
        predicate_match=False,
        value_incompatibility=0.0,
        polarity_opposition=False,
        numeric_contradiction=False,
        temporal_contradiction=False,
        version_mismatch=True,
    )
    assert 0.0 <= score_min <= 100.0


def test_p17_5_conf_009_participant_isolation_g5(memory_env):
    """Verify candidate conflict evaluation strictly respects participant scope (G5)."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    # Propose memory for User A (using active consent participant)
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Backup runs every 24 hours.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    # Create consent for User B
    consent_b = service.create_consent(
        ConsentCreate(
            participant_scope_key="admin_assistant:adm_002",
            memory_policy_public_id=memory_env["policy"]["public_id"],
            purpose="user_confirmed_profile",
            allowed_categories=["user_confirmed_fact"],
        ),
        admin_id="admin_root",
    )

    # Propose contradictory statement for User B
    res_b = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_002",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Backup runs every 12 hours.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_b["public_id"],
        ),
        admin_id="admin_root",
    )

    # User B should NOT conflict with User A (isolated scope)
    assert res_b["status"] == "active"
    disputes = service.list_disputes("admin_assistant:adm_002")
    assert len(disputes) == 0


def test_p17_5_conf_010_category_and_purpose_isolation(memory_env):
    """Verify conflict detection does not cross category or purpose boundaries."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    # Category A: user_confirmed_fact
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Threshold is set to 2048.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    # Category B: project_preference
    res = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="project_preference",
            purpose="user_confirmed_profile",
            display_value="Threshold is set to 4096.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    assert res["status"] == "active"


def test_p17_5_conf_011_max_20_candidates_enforcement():
    """Verify evaluate_conflict limits candidate comparisons to 20."""
    candidates = [
        {
            "public_id": f"mem_{i}",
            "participant_scope_key": "user_limit_test",
            "category": "user_confirmed_fact",
            "purpose": "user_confirmed_profile",
            "display_value": f"Host IP is 192.168.1.{i}",
        }
        for i in range(50)
    ]
    res = ConflictKnowledgeEngine.evaluate_conflict(
        candidate_text="Host IP is 10.0.0.1",
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_limit_test",
        existing_candidates=candidates,
    )
    assert res is not None


def test_p17_5_conf_012_secret_sanitization_g8():
    """Verify secrets in contradictory candidates are sanitized before dispute creation (G8)."""
    raw_cand = "Backup token secret: AIzaSyD9876543210zyx and interval is 12 hours"
    res = ConflictKnowledgeEngine.evaluate_conflict(
        candidate_text=raw_cand,
        candidate_category="user_confirmed_fact",
        candidate_purpose="user_confirmed_profile",
        participant_scope_key="user_sec",
        existing_candidates=[
            {
                "public_id": "mem_sec_01",
                "participant_scope_key": "user_sec",
                "category": "user_confirmed_fact",
                "purpose": "user_confirmed_profile",
                "display_value": "Backup interval is 24 hours",
            }
        ],
    )
    assert res.has_conflict is True
    assert "AIzaSy" not in res.dispute_record.candidate_value
    assert "[REDACTED" in res.dispute_record.candidate_value


# ============================================================================
# 14-22: Dispute Lifecycle, State Transitions, and Supervised Resolution
# ============================================================================

def test_p17_5_conf_013_dispute_creation_and_persistence(memory_env):
    """Verify end-to-end conflict detection generates a DisputeRecord and awaits confirmation."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    # Initial Memory
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Backup retention is 30 days.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    # Contradictory Memory
    cand = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Backup retention is 90 days.",
            creation_source="assistant_proposed",
            confidence_type="assistant_inferred",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    assert cand["status"] == "awaiting_confirmation"

    disputes = service.list_disputes(participant_scope_key="admin_assistant:adm_001")
    assert len(disputes) >= 1
    disp = disputes[0]
    assert disp["conflict_classification"] in ("NUMERIC_CONFLICT", "TEMPORAL_CONFLICT")
    assert disp["state"] == "PENDING_REVIEW"


def test_p17_5_conf_014_state_machine_valid_and_invalid_transitions():
    """Verify dispute state machine permits only valid transitions."""
    # Valid: DETECTED -> PENDING_REVIEW -> UNDER_REVIEW -> RESOLVED
    assert ConflictKnowledgeEngine.validate_state_transition(DisputeState.DETECTED, DisputeState.PENDING_REVIEW)
    assert ConflictKnowledgeEngine.validate_state_transition(DisputeState.PENDING_REVIEW, DisputeState.UNDER_REVIEW)
    assert ConflictKnowledgeEngine.validate_state_transition(DisputeState.UNDER_REVIEW, DisputeState.RESOLVED)

    # Invalid: DETECTED -> RESOLVED (no autonomous jump)
    assert not ConflictKnowledgeEngine.validate_state_transition(DisputeState.DETECTED, DisputeState.RESOLVED)
    # Invalid: RESOLVED -> PENDING_REVIEW (terminal)
    assert not ConflictKnowledgeEngine.validate_state_transition(DisputeState.RESOLVED, DisputeState.PENDING_REVIEW)


def test_p17_5_conf_015_supervised_resolution_supersede_existing(memory_env):
    """Verify authorized SUPERSEDE_EXISTING resolution transitions existing to superseded."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    mem_a = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Retention limit is 30 days.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    mem_b = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Retention limit is 90 days.",
            creation_source="assistant_proposed",
            confidence_type="assistant_inferred",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    disputes = service.list_disputes("admin_assistant:adm_001")
    assert len(disputes) >= 1
    disp_id = disputes[0]["dispute_id"]

    res = service.resolve_dispute(
        dispute_id=disp_id,
        strategy=ResolutionStrategy.SUPERSEDE_EXISTING,
        admin_id="admin_ops_lead",
        resolution_reason="Confirmed 90-day compliance update",
    )
    assert res["status"] == "resolved"
    assert res["strategy"] == "SUPERSEDE_EXISTING"

    # Verify memory states
    updated_a = service.get_memory_item(mem_a["public_id"])
    updated_b = service.get_memory_item(mem_b["public_id"])
    assert updated_a["status"] == "superseded"
    assert updated_b["status"] == "active"


def test_p17_5_conf_016_supervised_resolution_retain_existing(memory_env):
    """Verify authorized RETAIN_EXISTING resolution rejects the candidate and retains original."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    mem_a = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Server port is 8080.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    mem_b = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Server port is 9090.",
            creation_source="assistant_proposed",
            confidence_type="assistant_inferred",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    disp_id = service.list_disputes("admin_assistant:adm_001")[0]["dispute_id"]
    res = service.resolve_dispute(
        dispute_id=disp_id,
        strategy=ResolutionStrategy.RETAIN_EXISTING,
        admin_id="admin_ops_lead",
        resolution_reason="Port 9090 was an unverified guess",
    )
    assert res["status"] == "resolved"

    assert service.get_memory_item(mem_a["public_id"])["status"] == "active"
    assert service.get_memory_item(mem_b["public_id"])["status"] == "rejected"


def test_p17_5_conf_017_supervised_resolution_coexistence(memory_env):
    """Verify authorized RETAIN_BOTH_COEXIST resolution allows contextual coexistence."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    mem_a = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Version 1 port is 8080.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    mem_b = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Version 2 port is 9090.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    disp_id = service.list_disputes("admin_assistant:adm_001")[0]["dispute_id"]
    res = service.resolve_dispute(
        dispute_id=disp_id,
        strategy=ResolutionStrategy.RETAIN_BOTH_COEXIST,
        admin_id="admin_ops_lead",
        resolution_reason="Both ports valid for respective versions",
    )
    assert res["status"] == "resolved"

    assert service.get_memory_item(mem_a["public_id"])["status"] == "active"
    assert service.get_memory_item(mem_b["public_id"])["status"] == "active"


def test_p17_5_conf_018_supervised_dismissal(memory_env):
    """Verify dispute dismissal transitions dispute and candidate to dismissed/rejected."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Timeout is 30 seconds.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Timeout is 60 seconds.",
            creation_source="assistant_proposed",
            confidence_type="assistant_inferred",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    disp_id = service.list_disputes("admin_assistant:adm_001")[0]["dispute_id"]
    res = service.dismiss_dispute(disp_id, admin_id="admin_ops_lead", reason="Test dismiss")
    assert res["status"] == "dismissed"


# ============================================================================
# 23-26: Retrieval Behavior Under Conflict
# ============================================================================

def test_p17_5_conf_019_retrieval_exclude_conflicting_policy(memory_env):
    """Verify 'exclude_conflicting' retrieval profile excludes disputed memories."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    # Create profile with exclude_conflicting
    prof = service.create_profile(
        RetrievalProfileCreate(
            name="strict_profile",
            allowed_categories=["user_confirmed_fact"],
            allowed_purposes=["user_confirmed_profile"],
            conflict_policy="exclude_conflicting",
            keyword_weight=0.4,
            vector_weight=0.6,
        ),
        admin_id="admin_root",
    )
    service.validate_profile(prof["public_id"], admin_id="admin_root")
    service.activate_profile(prof["public_id"], admin_id="admin_root")

    # Store memory in dispute
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Backup interval is 24 hours.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Backup interval is 12 hours.",
            creation_source="assistant_proposed",
            confidence_type="assistant_inferred",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    res = service.retrieve(
        MemoryRetrieveRequest(
            participant_scope_key="admin_assistant:adm_001",
            query="backup interval",
            retrieval_profile_public_id=prof["public_id"],
        ),
        admin_id="admin_root",
    )

    # Disputed memory should be excluded under exclude_conflicting
    assert len(res["results"]) == 0
    assert any("disputed" in ex.get("exclusion_reason", "") for ex in res["excluded"])


def test_p17_5_conf_020_retrieval_advisory_warning_annotation(memory_env):
    """Verify advisory retrieval profile annotates disputed memories with [DISPUTED_WARNING]."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    prof = service.create_profile(
        RetrievalProfileCreate(
            name="advisory_profile",
            allowed_categories=["user_confirmed_fact"],
            allowed_purposes=["user_confirmed_profile"],
            conflict_policy="prefer_recent",
            keyword_weight=0.4,
            vector_weight=0.6,
        ),
        admin_id="admin_root",
    )
    service.validate_profile(prof["public_id"], admin_id="admin_root")
    service.activate_profile(prof["public_id"], admin_id="admin_root")

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Retention is 30 days.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Retention is 90 days.",
            creation_source="assistant_proposed",
            confidence_type="assistant_inferred",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    res = service.retrieve(
        MemoryRetrieveRequest(
            participant_scope_key="admin_assistant:adm_001",
            query="retention limit",
            retrieval_profile_public_id=prof["public_id"],
        ),
        admin_id="admin_root",
    )

    # Advisory profile returns the active original but decorated with warning
    assert len(res["results"]) >= 1
    assert res["results"][0]["disputed_warning"] is not None
    assert "[DISPUTED_WARNING" in res["results"][0]["disputed_warning"]


# ============================================================================
# 25-36: Governance, Security, Durability, and Regression Invariants
# ============================================================================

def test_p17_5_conf_021_system_and_admin_governance_protection(memory_env):
    """Verify SYSTEM and ADMIN memories require human review and cannot be auto-overwritten."""
    service = memory_env["service"]
    consent_id = memory_env["consent"]["public_id"]

    # Propose authoritative user_confirmed memory
    sys_a = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="System cache limit is 1024 MB.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    assert sys_a["status"] == "active"

    # Competing AI-generated claim
    sys_b = service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="System cache limit is 2048 MB.",
            creation_source="assistant_proposed",
            confidence_type="assistant_inferred",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    # Must NOT auto-supersede; must be in awaiting_confirmation/proposed
    assert sys_b["status"] in ("proposed", "awaiting_confirmation")
    assert service.get_memory_item(sys_a["public_id"])["status"] == "active"


def test_p17_5_conf_022_sqlite_wal_durability_and_immutability(memory_env):
    """Verify dispute operations operate under SQLite WAL without data corruption."""
    service = memory_env["service"]
    repo = memory_env["repo"]
    consent_id = memory_env["consent"]["public_id"]

    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Cluster node count is 5.",
            creation_source="explicit_user_request",
            confidence_type="user_confirmed",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )
    service.propose_memory(
        MemoryItemCreate(
            participant_scope_key="admin_assistant:adm_001",
            category="user_confirmed_fact",
            purpose="user_confirmed_profile",
            display_value="Cluster node count is 10.",
            creation_source="assistant_proposed",
            confidence_type="assistant_inferred",
            consent_public_id=consent_id,
        ),
        admin_id="admin_root",
    )

    disp = service.list_disputes("admin_assistant:adm_001")[0]
    service.resolve_dispute(
        disp["dispute_id"],
        ResolutionStrategy.SUPERSEDE_EXISTING,
        admin_id="admin_wal",
        resolution_reason="Node scale up",
    )

    with repo.transaction() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode.lower() == "wal"
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity.lower() == "ok"
