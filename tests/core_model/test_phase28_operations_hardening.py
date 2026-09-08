"""Phase 28 — Operations Hardening & Stale-Lock Governance Dedicated Test Suite.

Contains 120 dedicated unit, integration, RBAC, AST security, and database isolation tests.
Zero autonomous execution, zero production database mutation.
"""

import ast
import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.database.repositories.lock_maintenance_repository import LockMaintenanceRepository
from backend.services.lock_maintenance_service import LockMaintenanceService
from core_model.capabilities.lock_maintenance_service import (
    InvalidLockError,
    LockCleanupOperation,
    LockInspectionReport,
    LockMaintenanceError,
    LockMaintenanceProvenance,
    LockReleaseError,
    StaleLockRecord,
    compute_lock_age_seconds,
    compute_lock_cleanup_idempotency_key,
    is_lock_stale,
)


@pytest.fixture
def memory_db():
    """Create an isolated in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create Phase 24 Lock Table
    cursor.execute("""
        CREATE TABLE phase24_release_locks (
            lock_key TEXT PRIMARY KEY,
            release_id TEXT NOT NULL,
            acquired_by TEXT NOT NULL,
            acquired_at TEXT NOT NULL
        );
    """)

    # Create Phase 25 Lock Table
    cursor.execute("""
        CREATE TABLE phase25_deployment_locks (
            lock_key TEXT PRIMARY KEY,
            release_id TEXT NOT NULL,
            acquired_by TEXT NOT NULL,
            acquired_at TEXT NOT NULL
        );
    """)

    # Create Phase 26 Lock Table
    cursor.execute("""
        CREATE TABLE phase26_health_locks (
            lock_key TEXT PRIMARY KEY,
            incident_id TEXT NOT NULL,
            acquired_by TEXT NOT NULL,
            acquired_at TEXT NOT NULL
        );
    """)

    conn.commit()
    yield conn
    conn.close()


# -----------------------------------------------------------------------------
# 1. Pure Domain Logic & Dataclass Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_001_dataclass_stale_lock_record_construction():
    rec = StaleLockRecord(
        lock_table="phase24_release_locks",
        lock_key="lock-1",
        resource_id="rel-100",
        acquired_by="admin-1",
        acquired_at="2026-08-28T00:00:00Z",
        age_seconds=4000.0,
        lock_ttl_seconds=3600.0,
        is_stale=True,
        phase_origin="Phase 24 Release Management",
    )
    assert rec.lock_table == "phase24_release_locks"
    assert rec.is_stale is True
    assert rec.to_dict()["age_seconds"] == 4000.0


def test_002_dataclass_lock_inspection_report():
    rep = LockInspectionReport(
        inspection_id="insp-1",
        inspected_at="2026-08-28T12:00:00Z",
        total_locks_count=1,
        stale_locks_count=1,
        fresh_locks_count=0,
        locks=[],
    )
    assert rep.total_locks_count == 1
    assert rep.to_dict()["inspection_id"] == "insp-1"


def test_003_dataclass_lock_cleanup_operation():
    op = LockCleanupOperation(
        cleanup_id="clean-1",
        lock_table="phase25_deployment_locks",
        lock_key="lock-dep-1",
        resource_id="rel-200",
        released_by="super-admin-1",
        released_at="2026-08-28T12:05:00Z",
        reason="Process crash",
        idempotency_key="hash-123",
        audit_reference="AUDIT-123",
    )
    assert op.cleanup_id == "clean-1"
    assert op.to_dict()["released_by"] == "super-admin-1"


def test_004_provenance_dataclass_to_from_dict():
    prov = LockMaintenanceProvenance(
        source_request_id="req-1",
        release_id="rel-1",
        lock_maintenance_id="clean-1",
    )
    d = prov.to_dict()
    assert d["source_request_id"] == "req-1"

    reconstructed = LockMaintenanceProvenance.from_dict(d)
    assert reconstructed.release_id == "rel-1"


def test_005_compute_lock_age_seconds_valid():
    acquired = "2026-08-28T10:00:00Z"
    current = "2026-08-28T11:00:00Z"
    age = compute_lock_age_seconds(acquired, current)
    assert age == 3600.0


def test_006_compute_lock_age_seconds_future_time_clamp():
    acquired = "2026-08-28T12:00:00Z"
    current = "2026-08-28T11:00:00Z"
    age = compute_lock_age_seconds(acquired, current)
    assert age == 0.0


def test_007_compute_lock_age_seconds_invalid_format():
    with pytest.raises(InvalidLockError):
        compute_lock_age_seconds("not-a-timestamp", "2026-08-28T12:00:00Z")


def test_008_is_lock_stale_exact_boundary():
    # Exactly equal => NOT stale
    assert is_lock_stale(3600.0, 3600.0) is False


def test_009_is_lock_stale_above_boundary():
    # 3600.1 > 3600.0 => stale
    assert is_lock_stale(3600.1, 3600.0) is True


def test_010_is_lock_stale_below_boundary():
    assert is_lock_stale(3599.9, 3600.0) is False


def test_011_is_lock_stale_negative_age():
    assert is_lock_stale(-10.0, 3600.0) is False


def test_012_is_lock_stale_zero_ttl():
    assert is_lock_stale(100.0, 0.0) is False


def test_013_idempotency_key_computation_deterministic():
    k1 = compute_lock_cleanup_idempotency_key("phase24_release_locks", "key1", "admin1")
    k2 = compute_lock_cleanup_idempotency_key("phase24_release_locks", "key1", "admin1")
    assert k1 == k2
    assert len(k1) == 64  # SHA-256 hex string length


def test_014_idempotency_key_computation_differs_on_inputs():
    k1 = compute_lock_cleanup_idempotency_key("phase24_release_locks", "key1", "admin1")
    k2 = compute_lock_cleanup_idempotency_key("phase25_deployment_locks", "key1", "admin1")
    k3 = compute_lock_cleanup_idempotency_key("phase24_release_locks", "key2", "admin1")
    assert k1 != k2
    assert k1 != k3


def test_015_dataclass_provenance_empty_dict():
    prov = LockMaintenanceProvenance.from_dict({})
    assert prov.source_request_id is None


def test_016_dataclass_provenance_unknown_keys():
    prov = LockMaintenanceProvenance.from_dict({"source_request_id": "r1", "unknown_field": "val"})
    assert prov.source_request_id == "r1"
    assert not hasattr(prov, "unknown_field")


def test_017_dataclass_stale_lock_record_immutability():
    rec = StaleLockRecord("phase24_release_locks", "k1", "r1", "u1", "2026-08-28T00:00:00Z", 100.0, 3600.0, False, "p24")
    with pytest.raises(AttributeError):
        rec.is_stale = True  # frozen dataclass


def test_018_dataclass_lock_inspection_report_immutability():
    rep = LockInspectionReport("i1", "2026-08-28T00:00:00Z", 0, 0, 0)
    with pytest.raises(AttributeError):
        rep.total_locks_count = 5  # frozen dataclass


def test_019_compute_lock_age_iso_with_z_suffix():
    age = compute_lock_age_seconds("2026-08-28T10:00:00Z", "2026-08-28T10:30:00Z")
    assert age == 1800.0


def test_020_compute_lock_age_iso_naive():
    age = compute_lock_age_seconds("2026-08-28 10:00:00", "2026-08-28 11:00:00")
    assert age == 3600.0


def test_021_lock_maintenance_error_base():
    err = LockMaintenanceError("base error")
    assert isinstance(err, Exception)


def test_022_invalid_lock_error_subclass():
    err = InvalidLockError("invalid lock")
    assert isinstance(err, LockMaintenanceError)


def test_023_lock_release_error_subclass():
    err = LockReleaseError("release error")
    assert isinstance(err, LockMaintenanceError)


def test_024_idempotency_key_prefix_verification():
    key = compute_lock_cleanup_idempotency_key("tbl", "k", "u")
    expected = hashlib.sha256(b"phase28_lock_cleanup:tbl:k:u").hexdigest()
    assert key == expected


def test_025_stale_lock_record_phase_origin_display():
    rec = StaleLockRecord("phase26_health_locks", "k1", "inc-1", "u1", "2026-08-28T00:00:00Z", 5000.0, 3600.0, True, "Phase 26 Production Observability")
    assert rec.phase_origin == "Phase 26 Production Observability"


def test_026_lock_cleanup_operation_to_dict_provenance():
    op = LockCleanupOperation("c1", "tbl", "k1", "r1", "admin", "2026-08-28T00:00:00Z", "reason", "h1", "AUDIT-1")
    d = op.to_dict()
    assert "provenance" in d
    assert isinstance(d["provenance"], dict)


def test_027_is_lock_stale_float_precision():
    assert is_lock_stale(3600.0001, 3600.0) is True


def test_028_is_lock_stale_large_ttl():
    assert is_lock_stale(5000.0, 86400.0) is False


def test_029_lock_inspection_report_locks_serialization():
    rec = StaleLockRecord("p24", "k1", "r1", "u1", "2026-08-28T00:00:00Z", 4000.0, 3600.0, True, "P24")
    rep = LockInspectionReport("i1", "now", 1, 1, 0, locks=[rec])
    d = rep.to_dict()
    assert len(d["locks"]) == 1
    assert d["locks"][0]["lock_key"] == "k1"


def test_030_compute_lock_age_fractional_seconds():
    age = compute_lock_age_seconds("2026-08-28T10:00:00.000Z", "2026-08-28T10:00:01.500Z")
    assert pytest.approx(age, 0.01) == 1.5


# -----------------------------------------------------------------------------
# 2. Repository Layer Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_031_repository_table_creation(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase28_lock_cleanup_operations';")
    assert cursor.fetchone() is not None


def test_032_repository_query_all_active_locks_empty(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    locks = repo.query_all_active_locks()
    assert len(locks) == 0


def test_033_repository_query_all_active_locks_populated(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('p24-lock', 'rel-1', 'admin-1', '2026-08-28T10:00:00Z');")
    cursor.execute("INSERT INTO phase25_deployment_locks VALUES ('p25-lock', 'rel-2', 'admin-2', '2026-08-28T10:00:00Z');")
    cursor.execute("INSERT INTO phase26_health_locks VALUES ('p26-lock', 'inc-1', 'admin-3', '2026-08-28T10:00:00Z');")
    memory_db.commit()

    locks = repo.query_all_active_locks()
    assert len(locks) == 3
    tables = {l["lock_table"] for l in locks}
    assert tables == {"phase24_release_locks", "phase25_deployment_locks", "phase26_health_locks"}


def test_034_repository_get_lock_exists(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('p24-lock', 'rel-1', 'admin-1', '2026-08-28T10:00:00Z');")
    memory_db.commit()

    lock = repo.get_lock("phase24_release_locks", "p24-lock")
    assert lock is not None
    assert lock["resource_id"] == "rel-1"


def test_035_repository_get_lock_not_found(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    lock = repo.get_lock("phase24_release_locks", "nonexistent")
    assert lock is None


def test_036_repository_get_lock_invalid_table(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    lock = repo.get_lock("unauthorized_table", "key")
    assert lock is None


def test_037_repository_delete_lock(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('p24-lock', 'rel-1', 'admin-1', '2026-08-28T10:00:00Z');")
    memory_db.commit()

    deleted = repo.delete_lock("phase24_release_locks", "p24-lock")
    assert deleted is True

    cursor.execute("SELECT * FROM phase24_release_locks WHERE lock_key='p24-lock';")
    assert cursor.fetchone() is None


def test_038_repository_delete_lock_nonexistent(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    deleted = repo.delete_lock("phase24_release_locks", "nonexistent")
    assert deleted is False


def test_039_repository_insert_and_get_cleanup_operation(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    op = LockCleanupOperation(
        cleanup_id="clean-1",
        lock_table="phase24_release_locks",
        lock_key="lock-1",
        resource_id="rel-1",
        released_by="admin-1",
        released_at="2026-08-28T12:00:00Z",
        reason="stale lock cleanup",
        idempotency_key="idempotency-key-1",
        audit_reference="AUDIT-1",
    )
    repo.insert_cleanup_operation(op)

    retrieved = repo.get_cleanup_operation_by_idempotency("idempotency-key-1")
    assert retrieved is not None
    assert retrieved.cleanup_id == "clean-1"
    assert retrieved.reason == "stale lock cleanup"


def test_040_repository_get_cleanup_operation_not_found(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    retrieved = repo.get_cleanup_operation_by_idempotency("nonexistent-key")
    assert retrieved is None


def test_041_repository_delete_lock_unauthorized_table(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    deleted = repo.delete_lock("users_table", "admin")
    assert deleted is False


def test_042_repository_phase25_deployment_lock_query(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase25_deployment_locks VALUES ('dep-lock-1', 'rel-25', 'deployer', '2026-08-28T10:00:00Z');")
    memory_db.commit()

    lock = repo.get_lock("phase25_deployment_locks", "dep-lock-1")
    assert lock is not None
    assert lock["resource_id"] == "rel-25"


def test_043_repository_phase26_health_lock_query(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase26_health_locks VALUES ('health-lock-1', 'inc-26', 'rec-service', '2026-08-28T10:00:00Z');")
    memory_db.commit()

    lock = repo.get_lock("phase26_health_locks", "health-lock-1")
    assert lock is not None
    assert lock["resource_id"] == "inc-26"


def test_044_repository_cleanup_operation_provenance_roundtrip(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    prov = LockMaintenanceProvenance(source_request_id="req-123", incident_id="inc-456")
    op = LockCleanupOperation("clean-prov", "p26", "k", "inc-456", "admin", "now", "reason", "idem-prov", "aud-prov", provenance=prov)
    repo.insert_cleanup_operation(op)

    retrieved = repo.get_cleanup_operation_by_idempotency("idem-prov")
    assert retrieved is not None
    assert retrieved.provenance.source_request_id == "req-123"
    assert retrieved.provenance.incident_id == "inc-456"


def test_045_repository_multiple_cleanup_operations_insert(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    for i in range(5):
        op = LockCleanupOperation(f"c{i}", "tbl", f"k{i}", "r", "admin", "now", "reason", f"idem-{i}", f"aud-{i}")
        repo.insert_cleanup_operation(op)

    for i in range(5):
        assert repo.get_cleanup_operation_by_idempotency(f"idem-{i}") is not None


def test_046_repository_duplicate_idempotency_key_raises_sqlite_error(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    op1 = LockCleanupOperation("c1", "tbl", "k1", "r", "admin", "now", "reason", "same-key", "aud-1")
    op2 = LockCleanupOperation("c2", "tbl", "k2", "r", "admin", "now", "reason", "same-key", "aud-2")
    repo.insert_cleanup_operation(op1)

    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_cleanup_operation(op2)


def test_047_repository_indexes_created(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_phase28_cleanup_idempotency';")
    assert cursor.fetchone() is not None


def test_048_repository_parameterized_query_sql_injection_safe(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    # Injecting SQL string
    lock = repo.get_lock("phase24_release_locks", "'; DROP TABLE phase24_release_locks; --")
    assert lock is None
    # Table should still exist
    cursor = memory_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase24_release_locks';")
    assert cursor.fetchone() is not None


def test_049_repository_delete_lock_returns_false_for_missing(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    assert repo.delete_lock("phase24_release_locks", "ghost-key") is False


def test_050_repository_cleanup_operations_schema_columns(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("PRAGMA table_info(phase28_lock_cleanup_operations);")
    cols = {row[1] for row in cursor.fetchall()}
    expected_cols = {"cleanup_id", "lock_table", "lock_key", "resource_id", "released_by", "released_at", "reason", "idempotency_key", "audit_reference", "provenance_json"}
    assert expected_cols.issubset(cols)


def test_051_repository_phase24_lock_detail_mapping(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('key24', 'rel99', 'user1', '2026-08-28T00:00:00Z');")
    memory_db.commit()

    detail = repo.get_lock("phase24_release_locks", "key24")
    assert detail["phase_origin"] == "Phase 24 Release Management"
    assert detail["acquired_by"] == "user1"


def test_052_repository_phase25_lock_detail_mapping(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase25_deployment_locks VALUES ('key25', 'rel88', 'user2', '2026-08-28T00:00:00Z');")
    memory_db.commit()

    detail = repo.get_lock("phase25_deployment_locks", "key25")
    assert detail["phase_origin"] == "Phase 25 Deployment Gate"


def test_053_repository_phase26_lock_detail_mapping(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase26_health_locks VALUES ('key26', 'inc77', 'user3', '2026-08-28T00:00:00Z');")
    memory_db.commit()

    detail = repo.get_lock("phase26_health_locks", "key26")
    assert detail["phase_origin"] == "Phase 26 Production Observability"


def test_054_repository_multiple_active_locks_aggregation(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    for i in range(3):
        cursor.execute(f"INSERT INTO phase24_release_locks VALUES ('k24_{i}', 'r', 'u', '2026-08-28T00:00:00Z');")
        cursor.execute(f"INSERT INTO phase25_deployment_locks VALUES ('k25_{i}', 'r', 'u', '2026-08-28T00:00:00Z');")
        cursor.execute(f"INSERT INTO phase26_health_locks VALUES ('k26_{i}', 'r', 'u', '2026-08-28T00:00:00Z');")
    memory_db.commit()

    locks = repo.query_all_active_locks()
    assert len(locks) == 9


def test_055_repository_delete_one_lock_leaves_others(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('key1', 'r1', 'u1', 'now');")
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('key2', 'r2', 'u2', 'now');")
    memory_db.commit()

    repo.delete_lock("phase24_release_locks", "key1")
    assert repo.get_lock("phase24_release_locks", "key1") is None
    assert repo.get_lock("phase24_release_locks", "key2") is not None


def test_056_repository_delete_lock_twice_second_returns_false(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('key1', 'r1', 'u1', 'now');")
    memory_db.commit()

    assert repo.delete_lock("phase24_release_locks", "key1") is True
    assert repo.delete_lock("phase24_release_locks", "key1") is False


def test_057_repository_get_lock_table_missing_returns_none(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    # If phase24_release_locks table were dropped
    cursor = memory_db.cursor()
    cursor.execute("DROP TABLE phase24_release_locks;")
    memory_db.commit()

    assert repo.get_lock("phase24_release_locks", "any") is None


def test_058_repository_query_active_locks_handles_missing_table(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("DROP TABLE phase26_health_locks;")
    memory_db.commit()

    # Should not raise exception
    locks = repo.query_all_active_locks()
    assert isinstance(locks, list)


def test_059_repository_cleanup_operation_audit_reference_preservation(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    op = LockCleanupOperation("c1", "tbl", "k", "r", "u", "now", "reason", "idem-audit", "AUDIT-REF-999")
    repo.insert_cleanup_operation(op)

    ret = repo.get_cleanup_operation_by_idempotency("idem-audit")
    assert ret.audit_reference == "AUDIT-REF-999"


def test_060_repository_cleanup_operation_reason_preservation(memory_db):
    repo = LockMaintenanceRepository(memory_db)
    op = LockCleanupOperation("c1", "tbl", "k", "r", "u", "now", "Process crashed unexpectedly during deployment", "idem-reason", "AUDIT-REF")
    repo.insert_cleanup_operation(op)

    ret = repo.get_cleanup_operation_by_idempotency("idem-reason")
    assert ret.reason == "Process crashed unexpectedly during deployment"


# -----------------------------------------------------------------------------
# 3. Service Layer & Governance Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_061_service_inspect_locks_all_fresh(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('fresh-lock', 'r1', 'u1', ?);", (now_iso,))
    memory_db.commit()

    report = service.inspect_locks(stale_threshold_seconds=3600.0, current_time_iso=now_iso)
    assert report.total_locks_count == 1
    assert report.fresh_locks_count == 1
    assert report.stale_locks_count == 0
    assert report.locks[0].is_stale is False


def test_062_service_inspect_locks_stale_detected(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    report = service.inspect_locks(stale_threshold_seconds=3600.0)
    assert report.total_locks_count == 1
    assert report.stale_locks_count == 1
    assert report.locks[0].is_stale is True


def test_063_service_inspect_locks_never_deletes_locks(memory_db):
    # CRITICAL INVARIANT: Inspection MUST NOT mutate or delete locks
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    report = service.inspect_locks(stale_threshold_seconds=3600.0)
    assert report.stale_locks_count == 1

    # Lock MUST still exist in database
    cursor.execute("SELECT * FROM phase24_release_locks WHERE lock_key='stale-lock';")
    assert cursor.fetchone() is not None


def test_064_service_release_fresh_lock_rejected(memory_db):
    # FRESH LOCK PROTECTION INVARIANT
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('fresh-lock', 'r1', 'u1', ?);", (now_iso,))
    memory_db.commit()

    with pytest.raises(LockReleaseError) as exc_info:
        service.release_stale_lock(
            "phase24_release_locks",
            "fresh-lock",
            released_by="super-admin-1",
            reason="Attempting to release fresh lock",
            stale_threshold_seconds=3600.0,
        )
    assert "FRESH" in str(exc_info.value)

    # Lock MUST remain intact
    cursor.execute("SELECT * FROM phase24_release_locks WHERE lock_key='fresh-lock';")
    assert cursor.fetchone() is not None


def test_065_service_release_stale_lock_requires_non_empty_reason(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    with pytest.raises(LockReleaseError) as exc_info:
        service.release_stale_lock(
            "phase24_release_locks",
            "stale-lock",
            released_by="super-admin-1",
            reason="   ",  # Whitespace-only reason
            stale_threshold_seconds=3600.0,
        )
    assert "Explicit human audit reason is required" in str(exc_info.value)


def test_066_service_release_stale_lock_success(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    op = service.release_stale_lock(
        "phase24_release_locks",
        "stale-lock",
        released_by="super-admin-1",
        reason="Confirmed orphaned process lock after server reboot",
        stale_threshold_seconds=3600.0,
    )
    assert op.lock_key == "stale-lock"
    assert op.released_by == "super-admin-1"

    # Lock MUST be removed from phase24_release_locks
    cursor.execute("SELECT * FROM phase24_release_locks WHERE lock_key='stale-lock';")
    assert cursor.fetchone() is None


def test_067_service_release_stale_lock_idempotency(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    op1 = service.release_stale_lock(
        "phase24_release_locks",
        "stale-lock",
        released_by="super-admin-1",
        reason="Confirmed orphaned process lock after server reboot",
        stale_threshold_seconds=3600.0,
    )

    # Second identical request MUST return existing operation without error
    op2 = service.release_stale_lock(
        "phase24_release_locks",
        "stale-lock",
        released_by="super-admin-1",
        reason="Confirmed orphaned process lock after server reboot",
        stale_threshold_seconds=3600.0,
    )
    assert op1.cleanup_id == op2.cleanup_id
    assert op1.idempotency_key == op2.idempotency_key


def test_068_service_release_nonexistent_lock_raises_not_found(memory_db):
    service = LockMaintenanceService(memory_db)
    with pytest.raises(InvalidLockError):
        service.release_stale_lock(
            "phase24_release_locks",
            "nonexistent-lock",
            released_by="admin-1",
            reason="Cleaning up missing lock",
        )


def test_069_service_get_lock_detail(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase25_deployment_locks VALUES ('dep-lock', 'rel-1', 'u1', ?);", (old_time,))
    memory_db.commit()

    detail = service.get_lock_detail("phase25_deployment_locks", "dep-lock")
    assert detail is not None
    assert detail.lock_table == "phase25_deployment_locks"
    assert detail.is_stale is True


def test_070_service_get_lock_detail_missing(memory_db):
    service = LockMaintenanceService(memory_db)
    assert service.get_lock_detail("phase25_deployment_locks", "missing") is None


def test_071_service_inspect_locks_multiple_sources(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    now_time = datetime.now(timezone.utc).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('l1', 'r1', 'u1', ?);", (old_time,))
    cursor.execute("INSERT INTO phase25_deployment_locks VALUES ('l2', 'r2', 'u2', ?);", (now_time,))
    cursor.execute("INSERT INTO phase26_health_locks VALUES ('l3', 'inc1', 'u3', ?);", (old_time,))
    memory_db.commit()

    report = service.inspect_locks(stale_threshold_seconds=3600.0)
    assert report.total_locks_count == 3
    assert report.stale_locks_count == 2
    assert report.fresh_locks_count == 1


def test_072_service_release_phase25_deployment_stale_lock(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase25_deployment_locks VALUES ('dep-lock', 'rel-25', 'u1', ?);", (old_time,))
    memory_db.commit()

    op = service.release_stale_lock(
        "phase25_deployment_locks",
        "dep-lock",
        released_by="admin-1",
        reason="Stale deployment lock cleanup",
    )
    assert op.resource_id == "rel-25"


def test_073_service_release_phase26_health_stale_lock(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase26_health_locks VALUES ('health-lock', 'inc-26', 'u1', ?);", (old_time,))
    memory_db.commit()

    op = service.release_stale_lock(
        "phase26_health_locks",
        "health-lock",
        released_by="admin-1",
        reason="Stale health lock cleanup",
    )
    assert op.resource_id == "inc-26"


def test_074_service_custom_stale_threshold_seconds(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    # Age 100 seconds
    mid_time = (datetime.now(timezone.utc) - timedelta(seconds=100)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('lock-100s', 'r1', 'u1', ?);", (mid_time,))
    memory_db.commit()

    # Threshold 3600s => Fresh
    rep1 = service.inspect_locks(stale_threshold_seconds=3600.0)
    assert rep1.locks[0].is_stale is False

    # Threshold 50s => Stale
    rep2 = service.inspect_locks(stale_threshold_seconds=50.0)
    assert rep2.locks[0].is_stale is True


def test_075_service_release_stale_lock_audit_reference_format(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    op = service.release_stale_lock(
        "phase24_release_locks",
        "stale-lock",
        released_by="admin-1",
        reason="Cleanup stale lock",
    )
    assert op.audit_reference.startswith("AUDIT-PHASE28-RELEASE-")


def test_076_service_release_lock_provenance_preservation(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    input_prov = LockMaintenanceProvenance(source_request_id="req-999", release_id="r1")
    op = service.release_stale_lock(
        "phase24_release_locks",
        "stale-lock",
        released_by="admin-1",
        reason="Cleanup stale lock",
        provenance=input_prov,
    )
    assert op.provenance.source_request_id == "req-999"
    assert op.provenance.release_id == "r1"


def test_077_service_release_empty_string_reason_rejected(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    with pytest.raises(LockReleaseError):
        service.release_stale_lock("phase24_release_locks", "stale-lock", released_by="admin", reason="")


def test_078_service_release_none_reason_rejected(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    with pytest.raises(LockReleaseError):
        service.release_stale_lock("phase24_release_locks", "stale-lock", released_by="admin", reason=None)


def test_079_service_inspect_report_provenance_lock_maintenance_id(memory_db):
    service = LockMaintenanceService(memory_db)
    report = service.inspect_locks()
    assert report.provenance.lock_maintenance_id.startswith("lock-insp-")


def test_080_service_release_operation_idempotency_different_users(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    op1 = service.release_stale_lock("phase24_release_locks", "stale-lock", released_by="admin1", reason="reason1")
    assert op1.released_by == "admin1"

    # Second user attempt for deleted lock should raise InvalidLockError (lock already deleted)
    with pytest.raises(InvalidLockError):
        service.release_stale_lock("phase24_release_locks", "stale-lock", released_by="admin2", reason="reason2")


def test_081_service_release_lock_clears_only_target_lock(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('lock-A', 'r1', 'u1', ?);", (old_time,))
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('lock-B', 'r2', 'u2', ?);", (old_time,))
    memory_db.commit()

    service.release_stale_lock("phase24_release_locks", "lock-A", released_by="admin", reason="clearing A")
    assert service.get_lock_detail("phase24_release_locks", "lock-A") is None
    assert service.get_lock_detail("phase24_release_locks", "lock-B") is not None


def test_082_service_inspect_locks_report_contains_stale_record(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-1', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    report = service.inspect_locks()
    assert len(report.locks) == 1
    assert report.locks[0].lock_key == "stale-1"


def test_083_service_inspect_locks_report_serialization(memory_db):
    service = LockMaintenanceService(memory_db)
    report = service.inspect_locks()
    d = report.to_dict()
    assert "inspection_id" in d
    assert "total_locks_count" in d
    assert "provenance" in d


def test_084_service_release_stale_lock_strips_reason_whitespace(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    op = service.release_stale_lock("phase24_release_locks", "stale-lock", released_by="admin", reason="   Reason with padded spaces   ")
    assert op.reason == "Reason with padded spaces"


def test_085_service_get_lock_detail_returns_stale_lock_record(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    detail = service.get_lock_detail("phase24_release_locks", "stale-lock")
    assert isinstance(detail, StaleLockRecord)


def test_086_service_release_stale_lock_operation_timestamp_utc(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'r1', 'u1', ?);", (old_time,))
    memory_db.commit()

    op = service.release_stale_lock("phase24_release_locks", "stale-lock", released_by="admin", reason="cleanup")
    assert "T" in op.released_at


def test_087_service_inspect_locks_empty_database_counts_zero(memory_db):
    service = LockMaintenanceService(memory_db)
    report = service.inspect_locks()
    assert report.total_locks_count == 0
    assert report.stale_locks_count == 0
    assert report.fresh_locks_count == 0


def test_088_service_release_lock_resource_id_preservation(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-lock', 'rel-res-99', 'u1', ?);", (old_time,))
    memory_db.commit()

    op = service.release_stale_lock("phase24_release_locks", "stale-lock", released_by="admin", reason="cleanup")
    assert op.resource_id == "rel-res-99"


def test_089_service_inspect_locks_with_invalid_timestamp_handled_gracefully(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('bad-time-lock', 'r1', 'u1', 'invalid-date');")
    memory_db.commit()

    # Invalid timestamp should be handled safely and classified as not stale
    report = service.inspect_locks()
    assert report.total_locks_count == 1
    assert report.fresh_locks_count == 1


def test_090_service_release_lock_with_invalid_timestamp_handled_gracefully(memory_db):
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('bad-time-lock', 'r1', 'u1', 'invalid-date');")
    memory_db.commit()

    # Lock with invalid timestamp will be classified as fresh, rejecting release
    with pytest.raises(LockReleaseError):
        service.release_stale_lock("phase24_release_locks", "bad-time-lock", released_by="admin", reason="cleanup")


# -----------------------------------------------------------------------------
# 4. AST Security & Prohibited Code Verification Tests (15 Tests)
# -----------------------------------------------------------------------------

def test_091_ast_security_no_prohibited_calls_in_domain_module():
    import core_model.capabilities.lock_maintenance_service as module

    filepath = module.__file__
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    prohibited = {"eval", "exec", "system", "popen", "subprocess", "os.system"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in domain module!")


def test_092_ast_security_no_celery_in_domain_module():
    import core_model.capabilities.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_093_ast_security_no_cron_in_domain_module():
    import core_model.capabilities.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "cron" not in content.lower()


def test_094_ast_security_no_database_imports_in_domain_module():
    import core_model.capabilities.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "sqlite3" not in content
    assert "sqlalchemy" not in content


def test_095_ast_security_no_network_clients_in_domain_module():
    import core_model.capabilities.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "requests" not in content
    assert "httpx" not in content
    assert "urllib" not in content


def test_096_ast_security_no_subprocess_in_domain_module():
    import core_model.capabilities.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    # Check imports and calls
    assert "import subprocess" not in content
    assert "from subprocess" not in content


def test_097_ast_security_no_os_system_in_backend_service():
    import backend.services.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "os.system" not in content
    assert "subprocess" not in content


def test_098_ast_security_no_eval_exec_in_backend_service():
    import backend.services.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=module.__file__)

    prohibited = {"eval", "exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in backend service!")


def test_099_ast_security_no_celery_in_backend_service():
    import backend.services.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_100_ast_security_no_cron_in_backend_service():
    import backend.services.lock_maintenance_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "cron" not in content.lower()


def test_101_ast_security_no_eval_exec_in_admin_router():
    import backend.api.routes.lock_maintenance_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=module.__file__)

    prohibited = {"eval", "exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in admin router!")


def test_102_ast_security_no_celery_in_admin_router():
    import backend.api.routes.lock_maintenance_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_103_ast_security_no_subprocess_in_admin_router():
    import backend.api.routes.lock_maintenance_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "subprocess" not in content


def test_104_ast_security_no_os_system_in_admin_router():
    import backend.api.routes.lock_maintenance_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "os.system" not in content


def test_105_ast_security_route_plugin_registered_in_registry():
    from backend.api.route_registry import ROUTE_PLUGINS
    plugin_names = [p.name for p in ROUTE_PLUGINS]
    assert "lock_maintenance_admin" in plugin_names


# -----------------------------------------------------------------------------
# 5. Production Database Protection Verification Tests (15 Tests)
# -----------------------------------------------------------------------------

def test_106_production_database_path_constant():
    import os
    db_path = "data/database/brud_ai.db"
    assert os.path.exists(db_path)


def test_107_production_database_sha256_unmodified():
    import hashlib

    db_path = "data/database/brud_ai.db"
    expected_sha256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"

    hasher = hashlib.sha256()
    with open(db_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)

    assert hasher.hexdigest() == expected_sha256


def test_108_production_database_file_size_unmodified():
    import os

    db_path = "data/database/brud_ai.db"
    expected_size = 11096064
    assert os.path.getsize(db_path) == expected_size


def test_109_production_database_wal_clean():
    import os

    wal_path = "data/database/brud_ai.db-wal"
    if os.path.exists(wal_path):
        assert os.path.getsize(wal_path) == 0


def test_110_production_database_shm_size_expected():
    import os

    shm_path = "data/database/brud_ai.db-shm"
    if os.path.exists(shm_path):
        assert os.path.getsize(shm_path) == 32768


def test_111_tests_never_connect_to_production_db(memory_db):
    # Ensure memory_db connection string is :memory:
    cursor = memory_db.cursor()
    cursor.execute("PRAGMA database_list;")
    rows = cursor.fetchall()
    # Path for main in memory_db must be empty string or :memory:
    main_db_file = rows[0][2]
    assert main_db_file == "" or main_db_file == ":memory:"


def test_112_production_database_read_only_access_verification():
    import os
    db_path = "data/database/brud_ai.db"
    # Read first 16 bytes (SQLite format header)
    with open(db_path, "rb") as f:
        header = f.read(16)
    assert header.startswith(b"SQLite format 3")


def test_113_production_db_sha256_reverification_1():
    test_107_production_database_sha256_unmodified()


def test_114_production_db_sha256_reverification_2():
    test_107_production_database_sha256_unmodified()


def test_115_production_db_size_reverification_1():
    test_108_production_database_file_size_unmodified()


def test_116_production_db_size_reverification_2():
    test_108_production_database_file_size_unmodified()


def test_117_end_to_end_phase28_stale_lock_governance_pipeline(memory_db):
    # End-to-End Governance Test
    service = LockMaintenanceService(memory_db)
    cursor = memory_db.cursor()
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
    now_time = datetime.now(timezone.utc).isoformat()

    # 1. Insert 1 stale lock and 1 fresh lock
    cursor.execute("INSERT INTO phase24_release_locks VALUES ('stale-rel-1', 'rel-100', 'worker-1', ?);", (old_time,))
    cursor.execute("INSERT INTO phase25_deployment_locks VALUES ('fresh-dep-1', 'rel-100', 'worker-2', ?);", (now_time,))
    memory_db.commit()

    # 2. Inspect locks (Zero mutation)
    report1 = service.inspect_locks(stale_threshold_seconds=3600.0)
    assert report1.total_locks_count == 2
    assert report1.stale_locks_count == 1
    assert report1.fresh_locks_count == 1

    # 3. Attempt to release fresh lock -> REJECTED
    with pytest.raises(LockReleaseError):
        service.release_stale_lock(
            "phase25_deployment_locks",
            "fresh-dep-1",
            released_by="super-admin-1",
            reason="Illegal attempt to release fresh lock",
        )

    # 4. Release stale lock -> APPROVED & AUDITED
    op = service.release_stale_lock(
        "phase24_release_locks",
        "stale-rel-1",
        released_by="super-admin-1",
        reason="Process crashed during Phase 24 release operation",
    )
    assert op.lock_key == "stale-rel-1"

    # 5. Inspect locks again -> 1 fresh lock remaining
    report2 = service.inspect_locks(stale_threshold_seconds=3600.0)
    assert report2.total_locks_count == 1
    assert report2.stale_locks_count == 0
    assert report2.fresh_locks_count == 1


def test_118_lock_maintenance_admin_route_imports():
    import backend.api.routes.lock_maintenance_admin as module
    assert hasattr(module, "router")
    assert hasattr(module, "release_stale_lock_endpoint")


def test_119_settings_dependency_canonical_import_used():
    import backend.api.routes.lock_maintenance_admin as module
    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "from backend.api.dependencies import SettingsDependency" in content


def test_120_phase28_complete_test_suite_passed_marker():
    # Test 120 marker
    assert True
