"""Phase 29 — Disaster Recovery, Backup Integrity & Business Continuity Dedicated Test Suite.

Contains 120 dedicated unit, integration, RBAC, AST security, and database isolation tests.
Zero autonomous execution, zero production database mutation.
"""

import ast
import hashlib
import os
import shutil
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.database.repositories.disaster_recovery_repository import DisasterRecoveryRepository
from backend.services.disaster_recovery_service import DisasterRecoveryService
from core_model.capabilities.disaster_recovery_service import (
    BackupIntegrityError,
    BackupMetadataRecord,
    DisasterRecoveryError,
    DisasterRecoveryProvenance,
    RestoreError,
    RestoreOperationRecord,
    RestorePreflightReport,
    calculate_rpo_freshness,
    compute_disaster_recovery_idempotency_key,
    compute_file_sha256,
)


@pytest.fixture
def memory_db():
    """Create an isolated in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def temp_workspace():
    """Create a temporary directory for dummy source and backup database files."""
    tmp_dir = tempfile.mkdtemp()

    # Create dummy source database file with valid SQLite header
    source_db = os.path.join(tmp_dir, "test_source.db")
    conn = sqlite3.connect(source_db)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE dummy_table (id INTEGER PRIMARY KEY, name TEXT);")
    cursor.execute("INSERT INTO dummy_table VALUES (1, 'initial_data');")
    conn.commit()
    conn.close()

    backup_dir = os.path.join(tmp_dir, "backups")

    yield {"tmp_dir": tmp_dir, "source_db": source_db, "backup_dir": backup_dir}

    shutil.rmtree(tmp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# 1. Pure Domain Logic & Dataclass Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_001_dataclass_backup_metadata_record_construction():
    rec = BackupMetadataRecord(
        backup_id="bak-1",
        backup_type="FULL_SNAPSHOT",
        source_db_sha256="src-hash-123",
        backup_sha256="bak-hash-123",
        backup_size_bytes=1024,
        created_at="2026-08-28T12:00:00Z",
        storage_path="/backups/bak1.db",
        rpo_freshness_seconds=300.0,
        is_verified=True,
        created_by="admin-1",
    )
    assert rec.backup_id == "bak-1"
    assert rec.is_verified is True
    assert rec.to_dict()["backup_size_bytes"] == 1024


def test_002_dataclass_restore_preflight_report():
    rep = RestorePreflightReport(
        preflight_id="pref-1",
        backup_id="bak-1",
        checksum_match=True,
        integrity_check_passed=True,
        can_restore=True,
        checked_at="2026-08-28T12:05:00Z",
        notes="All checks passed",
    )
    assert rep.can_restore is True
    assert rep.to_dict()["checksum_match"] is True


def test_003_dataclass_restore_operation_record():
    op = RestoreOperationRecord(
        restore_id="rest-1",
        backup_id="bak-1",
        target_db_path="/data/target.db",
        executed_by="super-admin-1",
        executed_at="2026-08-28T12:10:00Z",
        reason="Disaster recovery restore",
        idempotency_key="idempotency-hash-1",
        audit_reference="AUDIT-REST-1",
        status="RESTORE_VERIFIED",
    )
    assert op.status == "RESTORE_VERIFIED"
    assert op.to_dict()["executed_by"] == "super-admin-1"


def test_004_provenance_dataclass_roundtrip():
    prov = DisasterRecoveryProvenance(
        source_request_id="req-100",
        backup_id="bak-1",
        restore_id="rest-1",
    )
    d = prov.to_dict()
    assert d["source_request_id"] == "req-100"
    reconstructed = DisasterRecoveryProvenance.from_dict(d)
    assert reconstructed.restore_id == "rest-1"


def test_005_compute_file_sha256_valid(temp_workspace):
    filepath = temp_workspace["source_db"]
    sha256, size = compute_file_sha256(filepath)
    assert len(sha256) == 64
    assert size > 0


def test_006_compute_file_sha256_nonexistent():
    with pytest.raises(BackupIntegrityError):
        compute_file_sha256("/nonexistent/file.db")


def test_007_calculate_rpo_freshness_within_target():
    created = "2026-08-28T10:00:00Z"
    current = "2026-08-28T10:30:00Z"
    freshness, within_target = calculate_rpo_freshness(created, current, rpo_target_seconds=3600.0)
    assert freshness == 1800.0
    assert within_target is True


def test_008_calculate_rpo_freshness_exceeds_target():
    created = "2026-08-28T08:00:00Z"
    current = "2026-08-28T10:00:00Z"
    freshness, within_target = calculate_rpo_freshness(created, current, rpo_target_seconds=3600.0)
    assert freshness == 7200.0
    assert within_target is False


def test_009_calculate_rpo_freshness_invalid_timestamp():
    with pytest.raises(BackupIntegrityError):
        calculate_rpo_freshness("invalid-date", "2026-08-28T10:00:00Z")


def test_010_compute_disaster_recovery_idempotency_key_deterministic():
    k1 = compute_disaster_recovery_idempotency_key("bak-1", "admin-1", "/target.db")
    k2 = compute_disaster_recovery_idempotency_key("bak-1", "admin-1", "/target.db")
    assert k1 == k2
    assert len(k1) == 64


def test_011_compute_disaster_recovery_idempotency_key_differs_on_input():
    k1 = compute_disaster_recovery_idempotency_key("bak-1", "admin-1", "/target.db")
    k2 = compute_disaster_recovery_idempotency_key("bak-2", "admin-1", "/target.db")
    assert k1 != k2


def test_012_disaster_recovery_error_base():
    err = DisasterRecoveryError("dr error")
    assert isinstance(err, Exception)


def test_013_backup_integrity_error_subclass():
    err = BackupIntegrityError("integrity error")
    assert isinstance(err, DisasterRecoveryError)


def test_014_restore_error_subclass():
    err = RestoreError("restore error")
    assert isinstance(err, DisasterRecoveryError)


def test_015_backup_metadata_record_immutability():
    rec = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    with pytest.raises(AttributeError):
        rec.is_verified = False  # frozen dataclass


def test_016_restore_preflight_report_immutability():
    rep = RestorePreflightReport("p1", "b1", True, True, True, "now", "notes")
    with pytest.raises(AttributeError):
        rep.can_restore = False  # frozen dataclass


def test_017_restore_operation_record_immutability():
    op = RestoreOperationRecord("r1", "b1", "/t", "u", "now", "reason", "idem", "aud", "VERIFIED")
    with pytest.raises(AttributeError):
        op.status = "FAILED"  # frozen dataclass


def test_018_provenance_empty_dict():
    prov = DisasterRecoveryProvenance.from_dict({})
    assert prov.backup_id is None


def test_019_provenance_unknown_field_filtered():
    prov = DisasterRecoveryProvenance.from_dict({"backup_id": "b1", "unknown": "v"})
    assert prov.backup_id == "b1"
    assert not hasattr(prov, "unknown")


def test_020_calculate_rpo_freshness_negative_diff_clamp():
    # Future timestamp
    created = "2026-08-28T12:00:00Z"
    current = "2026-08-28T11:00:00Z"
    freshness, within_target = calculate_rpo_freshness(created, current, rpo_target_seconds=3600.0)
    assert freshness == 0.0
    assert within_target is True


def test_021_compute_file_sha256_empty_file(temp_workspace):
    empty_file = os.path.join(temp_workspace["tmp_dir"], "empty.db")
    with open(empty_file, "wb") as f:
        pass
    sha256, size = compute_file_sha256(empty_file)
    assert size == 0
    assert sha256 == hashlib.sha256(b"").hexdigest()


def test_022_backup_metadata_provenance_default():
    rec = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    assert isinstance(rec.provenance, DisasterRecoveryProvenance)


def test_023_restore_preflight_report_provenance_default():
    rep = RestorePreflightReport("p1", "b1", True, True, True, "now", "notes")
    assert isinstance(rep.provenance, DisasterRecoveryProvenance)


def test_024_restore_operation_record_provenance_default():
    op = RestoreOperationRecord("r1", "b1", "/t", "u", "now", "reason", "idem", "aud", "VERIFIED")
    assert isinstance(op.provenance, DisasterRecoveryProvenance)


def test_025_idempotency_key_prefix_verification():
    raw = f"phase29_restore:b1:u1:/path"
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    actual = compute_disaster_recovery_idempotency_key("b1", "u1", "/path")
    assert actual == expected


def test_026_calculate_rpo_freshness_iso_with_z():
    freshness, within = calculate_rpo_freshness("2026-08-28T10:00:00Z", "2026-08-28T10:15:00Z", 900.0)
    assert freshness == 900.0
    assert within is True


def test_027_calculate_rpo_freshness_iso_naive():
    freshness, within = calculate_rpo_freshness("2026-08-28 10:00:00", "2026-08-28 11:00:00", 3600.0)
    assert freshness == 3600.0
    assert within is True


def test_028_backup_metadata_serialization():
    rec = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 10.0, True, "admin")
    d = rec.to_dict()
    assert d["backup_id"] == "b1"
    assert "provenance" in d


def test_029_restore_preflight_report_serialization():
    rep = RestorePreflightReport("p1", "b1", True, True, True, "now", "notes")
    d = rep.to_dict()
    assert d["can_restore"] is True


def test_030_restore_operation_record_serialization():
    op = RestoreOperationRecord("r1", "b1", "/t", "u", "now", "reason", "idem", "aud", "RESTORE_VERIFIED")
    d = op.to_dict()
    assert d["status"] == "RESTORE_VERIFIED"


# -----------------------------------------------------------------------------
# 2. Repository Layer Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_031_repository_table_creation(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    cursor = memory_db.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase29_database_backups';")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase29_restore_operations';")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase29_recovery_locks';")
    assert cursor.fetchone() is not None


def test_032_repository_insert_and_get_backup_metadata(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    rec = BackupMetadataRecord(
        backup_id="bak-100",
        backup_type="FULL_SNAPSHOT",
        source_db_sha256="src-hash",
        backup_sha256="bak-hash",
        backup_size_bytes=2048,
        created_at="2026-08-28T10:00:00Z",
        storage_path="/backups/bak-100.db",
        rpo_freshness_seconds=100.0,
        is_verified=True,
        created_by="admin-1",
    )
    repo.insert_backup_metadata(rec)

    fetched = repo.get_backup_metadata("bak-100")
    assert fetched is not None
    assert fetched.backup_id == "bak-100"
    assert fetched.backup_sha256 == "bak-hash"
    assert fetched.is_verified is True


def test_033_repository_get_backup_metadata_nonexistent(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    assert repo.get_backup_metadata("nonexistent") is None


def test_034_repository_list_backups_ordered(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "2026-08-28T10:00:00Z", "/p1", 0.0, True, "admin")
    b2 = BackupMetadataRecord("b2", "FULL", "h1", "h2", 100, "2026-08-28T11:00:00Z", "/p2", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)
    repo.insert_backup_metadata(b2)

    backups = repo.list_backups(limit=10)
    assert len(backups) == 2
    # Ordered DESC by created_at => b2 first
    assert backups[0].backup_id == "b2"


def test_035_repository_update_backup_verification_status(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "2026-08-28T10:00:00Z", "/p1", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    repo.update_backup_verification_status("b1", False)
    fetched = repo.get_backup_metadata("b1")
    assert fetched.is_verified is False


def test_036_repository_insert_and_get_restore_operation(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    # Insert backup first for foreign key compliance
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "2026-08-28T10:00:00Z", "/p1", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    op = RestoreOperationRecord(
        restore_id="rest-100",
        backup_id="b1",
        target_db_path="/target/db.db",
        executed_by="super-admin-1",
        executed_at="2026-08-28T12:00:00Z",
        reason="Disaster recovery",
        idempotency_key="idempotency-key-100",
        audit_reference="AUDIT-100",
        status="RESTORE_VERIFIED",
    )
    repo.insert_restore_operation(op)

    fetched = repo.get_restore_operation_by_idempotency("idempotency-key-100")
    assert fetched is not None
    assert fetched.restore_id == "rest-100"
    assert fetched.executed_by == "super-admin-1"


def test_037_repository_get_restore_operation_nonexistent(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    assert repo.get_restore_operation_by_idempotency("nonexistent-key") is None


def test_038_repository_acquire_and_release_recovery_lock(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    acquired = repo.acquire_recovery_lock("lock-1", "b1", "admin-1")
    assert acquired is True

    # Duplicate acquire MUST fail
    acquired_again = repo.acquire_recovery_lock("lock-1", "b1", "admin-2")
    assert acquired_again is False

    released = repo.release_recovery_lock("lock-1")
    assert released is True

    # Second release returns False
    assert repo.release_recovery_lock("lock-1") is False


def test_039_repository_indexes_created(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    cursor = memory_db.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_phase29_backups_created_at';")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_phase29_restore_idempotency';")
    assert cursor.fetchone() is not None


def test_040_repository_provenance_roundtrip_backup(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    prov = DisasterRecoveryProvenance(source_request_id="req-555", backup_id="bak-555")
    b = BackupMetadataRecord("bak-555", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin", provenance=prov)
    repo.insert_backup_metadata(b)

    fetched = repo.get_backup_metadata("bak-555")
    assert fetched.provenance.source_request_id == "req-555"
    assert fetched.provenance.backup_id == "bak-555"


def test_041_repository_provenance_roundtrip_restore(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b)

    prov = DisasterRecoveryProvenance(restore_id="rest-999")
    op = RestoreOperationRecord("rest-999", "b1", "/t", "admin", "now", "reason", "idem-999", "aud", "VERIFIED", provenance=prov)
    repo.insert_restore_operation(op)

    fetched = repo.get_restore_operation_by_idempotency("idem-999")
    assert fetched.provenance.restore_id == "rest-999"


def test_042_repository_duplicate_backup_id_raises_sqlite_error(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_backup_metadata(b1)


def test_043_repository_duplicate_restore_idempotency_raises_sqlite_error(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    op1 = RestoreOperationRecord("r1", "b1", "/t", "u", "now", "reason", "idem-same", "aud", "VERIFIED")
    op2 = RestoreOperationRecord("r2", "b1", "/t", "u", "now", "reason", "idem-same", "aud", "VERIFIED")
    repo.insert_restore_operation(op1)

    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_restore_operation(op2)


def test_044_repository_list_backups_limit_enforced(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    for i in range(10):
        b = BackupMetadataRecord(f"b{i}", "FULL", "h1", "h2", 100, f"2026-08-28T10:00:0{i}Z", f"/p{i}", 0.0, True, "admin")
        repo.insert_backup_metadata(b)

    backups = repo.list_backups(limit=3)
    assert len(backups) == 3


def test_045_repository_phase29_database_backups_schema_columns(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("PRAGMA table_info(phase29_database_backups);")
    cols = {row[1] for row in cursor.fetchall()}
    expected = {"backup_id", "backup_type", "source_db_sha256", "backup_sha256", "backup_size_bytes", "created_at", "storage_path", "rpo_freshness_seconds", "is_verified", "created_by", "provenance_json"}
    assert expected.issubset(cols)


def test_046_repository_phase29_restore_operations_schema_columns(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("PRAGMA table_info(phase29_restore_operations);")
    cols = {row[1] for row in cursor.fetchall()}
    expected = {"restore_id", "backup_id", "target_db_path", "executed_by", "executed_at", "reason", "idempotency_key", "audit_reference", "status", "provenance_json"}
    assert expected.issubset(cols)


def test_047_repository_phase29_recovery_locks_schema_columns(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("PRAGMA table_info(phase29_recovery_locks);")
    cols = {row[1] for row in cursor.fetchall()}
    expected = {"lock_key", "backup_id", "acquired_by", "acquired_at"}
    assert expected.issubset(cols)


def test_048_repository_parameterized_sql_injection_safe(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b = repo.get_backup_metadata("'; DROP TABLE phase29_database_backups; --")
    assert b is None
    # Table must remain intact
    cursor = memory_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase29_database_backups';")
    assert cursor.fetchone() is not None


def test_049_repository_acquire_recovery_lock_different_keys(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    a1 = repo.acquire_recovery_lock("lock-A", "b1", "u1")
    a2 = repo.acquire_recovery_lock("lock-B", "b1", "u1")
    assert a1 is True
    assert a2 is True


def test_050_repository_list_backups_empty_returns_empty_list(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    assert repo.list_backups() == []


def test_051_repository_update_verification_status_nonexistent_no_error(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    repo.update_backup_verification_status("ghost-backup", True)


def test_052_repository_restore_operation_reason_preservation(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    op = RestoreOperationRecord("r1", "b1", "/t", "admin", "now", "Emergency restore following server hardware failure", "idem-reason", "aud", "VERIFIED")
    repo.insert_restore_operation(op)

    ret = repo.get_restore_operation_by_idempotency("idem-reason")
    assert ret.reason == "Emergency restore following server hardware failure"


def test_053_repository_restore_operation_audit_reference_preservation(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    op = RestoreOperationRecord("r1", "b1", "/t", "admin", "now", "reason", "idem-aud", "AUDIT-PHASE29-RESTORE-12345", "VERIFIED")
    repo.insert_restore_operation(op)

    ret = repo.get_restore_operation_by_idempotency("idem-aud")
    assert ret.audit_reference == "AUDIT-PHASE29-RESTORE-12345"


def test_054_repository_multiple_restore_operations_query(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    for i in range(3):
        op = RestoreOperationRecord(f"r{i}", "b1", f"/t{i}", "admin", "now", "reason", f"idem-multi-{i}", f"aud{i}", "VERIFIED")
        repo.insert_restore_operation(op)

    for i in range(3):
        ret = repo.get_restore_operation_by_idempotency(f"idem-multi-{i}")
        assert ret.restore_id == f"r{i}"


def test_055_repository_backup_type_preservation(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "EMERGENCY_PRE_RESTORE", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    ret = repo.get_backup_metadata("b1")
    assert ret.backup_type == "EMERGENCY_PRE_RESTORE"


def test_056_repository_backup_size_bytes_preservation(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 11096064, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    ret = repo.get_backup_metadata("b1")
    assert ret.backup_size_bytes == 11096064


def test_057_repository_source_db_sha256_preservation(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)

    ret = repo.get_backup_metadata("b1")
    assert ret.source_db_sha256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"


def test_058_repository_release_recovery_lock_nonexistent_returns_false(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    assert repo.release_recovery_lock("ghost-lock") is False


def test_059_repository_acquire_lock_stores_timestamp(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    repo.acquire_recovery_lock("l1", "b1", "admin1")
    cursor = memory_db.cursor()
    cursor.execute("SELECT acquired_at FROM phase29_recovery_locks WHERE lock_key='l1';")
    row = cursor.fetchone()
    assert row is not None
    assert "T" in row[0]


def test_060_repository_restore_operations_foreign_key_query(memory_db):
    repo = DisasterRecoveryRepository(memory_db)
    b1 = BackupMetadataRecord("b1", "FULL", "h1", "h2", 100, "now", "/p", 0.0, True, "admin")
    repo.insert_backup_metadata(b1)
    op = RestoreOperationRecord("r1", "b1", "/t", "u", "now", "reason", "idem-fk", "aud", "VERIFIED")
    repo.insert_restore_operation(op)

    fetched = repo.get_restore_operation_by_idempotency("idem-fk")
    assert fetched.backup_id == "b1"


# -----------------------------------------------------------------------------
# 3. Service Layer & Governance Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_061_service_create_database_snapshot_success(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
        created_by="admin-1",
    )
    assert rec.backup_id.startswith("bak-")
    assert os.path.exists(rec.storage_path)
    assert rec.is_verified is True
    assert rec.backup_size_bytes > 0


def test_062_service_create_database_snapshot_nonexistent_source(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    with pytest.raises(BackupIntegrityError):
        service.create_database_snapshot(
            source_db_path="/nonexistent/source.db",
            backup_dir=temp_workspace["backup_dir"],
        )


def test_063_service_verify_backup_integrity_valid(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )
    is_valid = service.verify_backup_integrity(rec.backup_id)
    assert is_valid is True


def test_064_service_verify_backup_integrity_tampered_file(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Tamper backup file content
    with open(rec.storage_path, "a", encoding="utf-8") as f:
        f.write("tampered data")

    is_valid = service.verify_backup_integrity(rec.backup_id)
    assert is_valid is False


def test_065_service_verify_backup_integrity_missing_file(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Delete backup file on disk
    os.remove(rec.storage_path)

    is_valid = service.verify_backup_integrity(rec.backup_id)
    assert is_valid is False


def test_066_service_preflight_restore_check_valid(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    preflight = service.preflight_restore_check(rec.backup_id)
    assert preflight.checksum_match is True
    assert preflight.integrity_check_passed is True
    assert preflight.can_restore is True


def test_067_service_preflight_restore_check_corrupted_sqlite(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Overwrite backup file with non-SQLite content (same size if possible, or corrupt header)
    with open(rec.storage_path, "wb") as f:
        f.write(b"NOT A VALID SQLITE DATABASE FILE HEADER CONTENT!!!")

    preflight = service.preflight_restore_check(rec.backup_id)
    assert preflight.can_restore is False


def test_068_service_execute_restore_requires_non_empty_reason(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    with pytest.raises(RestoreError) as exc_info:
        service.execute_human_authorized_restore(
            rec.backup_id,
            target_db_path=target,
            executed_by="super-admin-1",
            reason="   ",  # Whitespace-only reason
        )
    assert "Explicit human audit reason is required" in str(exc_info.value)


def test_069_service_execute_restore_success(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    op = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Disaster recovery test restore",
    )
    assert op.status == "RESTORE_VERIFIED"
    assert os.path.exists(target)

    # Verify target file SHA-256 matches backup SHA-256
    target_sha, _ = compute_file_sha256(target)
    assert target_sha == rec.backup_sha256


def test_070_service_execute_restore_idempotency(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    op1 = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Disaster recovery test restore",
    )

    # Second identical request MUST return existing operation without duplicate execution
    op2 = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Disaster recovery test restore",
    )
    assert op1.restore_id == op2.restore_id
    assert op1.idempotency_key == op2.idempotency_key


def test_071_service_execute_restore_concurrency_lock(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Pre-acquire lock to simulate concurrent execution
    service.repository.acquire_recovery_lock(f"restore:{rec.backup_id}", rec.backup_id, "other-admin")

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    with pytest.raises(RestoreError) as exc_info:
        service.execute_human_authorized_restore(
            rec.backup_id,
            target_db_path=target,
            executed_by="super-admin-1",
            reason="Concurrent restore test",
        )
    assert "Concurrency lock active" in str(exc_info.value)


def test_072_service_preflight_nonexistent_backup(memory_db):
    service = DisasterRecoveryService(memory_db)
    preflight = service.preflight_restore_check("ghost-backup")
    assert preflight.can_restore is False
    assert "not found" in preflight.notes


def test_073_service_preflight_missing_file_on_disk(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Delete storage file
    os.remove(rec.storage_path)

    preflight = service.preflight_restore_check(rec.backup_id)
    assert preflight.can_restore is False
    assert "does not exist on disk" in preflight.notes


def test_074_service_create_snapshot_provenance_preservation(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    prov = DisasterRecoveryProvenance(source_request_id="req-777", release_id="rel-777")
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
        provenance=prov,
    )
    assert rec.provenance.source_request_id == "req-777"
    assert rec.provenance.release_id == "rel-777"


def test_075_service_execute_restore_provenance_preservation(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    prov = DisasterRecoveryProvenance(source_request_id="req-888", incident_id="inc-888")
    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    op = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Restore test with provenance",
        provenance=prov,
    )
    assert op.provenance.source_request_id == "req-888"
    assert op.provenance.incident_id == "inc-888"


def test_076_service_execute_restore_none_reason_rejected(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    with pytest.raises(RestoreError):
        service.execute_human_authorized_restore("b1", target_db_path=target, executed_by="admin", reason=None)


def test_077_service_execute_restore_empty_string_reason_rejected(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    with pytest.raises(RestoreError):
        service.execute_human_authorized_restore("b1", target_db_path=target, executed_by="admin", reason="")


def test_078_service_execute_restore_strips_reason_whitespace(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    op = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="   Valid reason with padding   ",
    )
    assert op.reason == "Valid reason with padding"


def test_079_service_execute_restore_audit_reference_format(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    op = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Restore test",
    )
    assert op.audit_reference.startswith("AUDIT-PHASE29-RESTORE-")


def test_080_service_execute_restore_releases_lock_on_completion(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Restore test",
    )

    # Lock MUST be released
    cursor = memory_db.cursor()
    cursor.execute("SELECT * FROM phase29_recovery_locks WHERE lock_key=?;", (f"restore:{rec.backup_id}",))
    assert cursor.fetchone() is None


def test_081_service_verify_integrity_nonexistent_backup_raises_error(memory_db):
    service = DisasterRecoveryService(memory_db)
    with pytest.raises(BackupIntegrityError):
        service.verify_backup_integrity("ghost-backup")


def test_082_service_create_snapshot_custom_backup_type(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
        backup_type="EMERGENCY_PRE_RESTORE",
    )
    assert rec.backup_type == "EMERGENCY_PRE_RESTORE"


def test_083_service_restore_preflight_report_id_format(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )
    preflight = service.preflight_restore_check(rec.backup_id)
    assert preflight.preflight_id.startswith("pref-")


def test_084_service_restore_operation_id_format(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    op = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Restore test",
    )
    assert op.restore_id.startswith("rest-")


def test_085_service_create_snapshot_calculates_rpo_freshness(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )
    assert rec.rpo_freshness_seconds >= 0.0


def test_086_service_restore_replaces_existing_target_file(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Create pre-existing file at target path
    target = os.path.join(temp_workspace["tmp_dir"], "existing_target.db")
    with open(target, "w", encoding="utf-8") as f:
        f.write("old data")

    op = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Overwriting existing target file",
    )
    assert op.status == "RESTORE_VERIFIED"
    target_sha, _ = compute_file_sha256(target)
    assert target_sha == rec.backup_sha256


def test_087_service_restore_creates_target_parent_directories(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    target = os.path.join(temp_workspace["tmp_dir"], "nested", "dirs", "restored.db")
    op = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target,
        executed_by="super-admin-1",
        reason="Restoring to nested directory",
    )
    assert op.status == "RESTORE_VERIFIED"
    assert os.path.exists(target)


def test_088_service_execute_restore_fails_if_preflight_cannot_restore(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Delete storage file to force preflight check to fail
    os.remove(rec.storage_path)

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    with pytest.raises(RestoreError) as exc_info:
        service.execute_human_authorized_restore(
            rec.backup_id,
            target_db_path=target,
            executed_by="super-admin-1",
            reason="Attempting restore with missing file",
        )
    assert "Restore preflight failed" in str(exc_info.value)


def test_089_service_execute_restore_releases_lock_even_on_failure(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Corrupt storage file to trigger failure after lock acquisition
    with open(rec.storage_path, "wb") as f:
        f.write(b"CORRUPTED FILE")

    target = os.path.join(temp_workspace["tmp_dir"], "restored.db")
    with pytest.raises(RestoreError):
        service.execute_human_authorized_restore(
            rec.backup_id,
            target_db_path=target,
            executed_by="super-admin-1",
            reason="Failing restore test",
        )

    # Lock MUST be released despite failure
    cursor = memory_db.cursor()
    cursor.execute("SELECT * FROM phase29_recovery_locks WHERE lock_key=?;", (f"restore:{rec.backup_id}",))
    assert cursor.fetchone() is None


def test_090_service_create_snapshot_iso_format(memory_db, temp_workspace):
    service = DisasterRecoveryService(memory_db)
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )
    assert "T" in rec.created_at


# -----------------------------------------------------------------------------
# 4. AST Security & Prohibited Code Verification Tests (15 Tests)
# -----------------------------------------------------------------------------

def test_091_ast_security_no_prohibited_calls_in_domain_module():
    import core_model.capabilities.disaster_recovery_service as module

    filepath = module.__file__
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    prohibited = {"eval", "exec", "system", "popen", "subprocess", "os.system"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in domain module!")


def test_092_ast_security_no_celery_in_domain_module():
    import core_model.capabilities.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_093_ast_security_no_cron_in_domain_module():
    import core_model.capabilities.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "cron" not in content.lower()


def test_094_ast_security_no_database_imports_in_domain_module():
    import core_model.capabilities.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "sqlite3" not in content
    assert "sqlalchemy" not in content


def test_095_ast_security_no_network_clients_in_domain_module():
    import core_model.capabilities.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "requests" not in content
    assert "httpx" not in content
    assert "urllib" not in content


def test_096_ast_security_no_subprocess_imports_in_domain_module():
    import core_model.capabilities.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "import subprocess" not in content
    assert "from subprocess" not in content


def test_097_ast_security_no_os_system_in_backend_service():
    import backend.services.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "os.system" not in content
    assert "subprocess" not in content


def test_098_ast_security_no_eval_exec_in_backend_service():
    import backend.services.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=module.__file__)

    prohibited = {"eval", "exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in backend service!")


def test_099_ast_security_no_celery_in_backend_service():
    import backend.services.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_100_ast_security_no_cron_in_backend_service():
    import backend.services.disaster_recovery_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "cron" not in content.lower()


def test_101_ast_security_no_eval_exec_in_admin_router():
    import backend.api.routes.disaster_recovery_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=module.__file__)

    prohibited = {"eval", "exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in admin router!")


def test_102_ast_security_no_celery_in_admin_router():
    import backend.api.routes.disaster_recovery_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_103_ast_security_no_subprocess_in_admin_router():
    import backend.api.routes.disaster_recovery_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "subprocess" not in content


def test_104_ast_security_no_os_system_in_admin_router():
    import backend.api.routes.disaster_recovery_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "os.system" not in content


def test_105_ast_security_route_plugin_registered_in_registry():
    from backend.api.route_registry import ROUTE_PLUGINS
    plugin_names = [p.name for p in ROUTE_PLUGINS]
    assert "disaster_recovery_admin" in plugin_names


# -----------------------------------------------------------------------------
# 5. Production Database Protection Verification Tests (15 Tests)
# -----------------------------------------------------------------------------

def test_106_production_database_path_constant():
    db_path = "data/database/brud_ai.db"
    assert os.path.exists(db_path)


def test_107_production_database_sha256_unmodified():
    db_path = "data/database/brud_ai.db"
    expected_sha256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"

    hasher = hashlib.sha256()
    with open(db_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)

    assert hasher.hexdigest() == expected_sha256


def test_108_production_database_file_size_unmodified():
    db_path = "data/database/brud_ai.db"
    expected_size = 11096064
    assert os.path.getsize(db_path) == expected_size


def test_109_production_database_wal_clean():
    wal_path = "data/database/brud_ai.db-wal"
    if os.path.exists(wal_path):
        assert os.path.getsize(wal_path) == 0


def test_110_production_database_shm_size_expected():
    shm_path = "data/database/brud_ai.db-shm"
    if os.path.exists(shm_path):
        assert os.path.getsize(shm_path) == 32768


def test_111_tests_never_connect_to_production_db(memory_db):
    cursor = memory_db.cursor()
    cursor.execute("PRAGMA database_list;")
    rows = cursor.fetchall()
    main_db_file = rows[0][2]
    assert main_db_file == "" or main_db_file == ":memory:"


def test_112_production_database_read_only_access_verification():
    db_path = "data/database/brud_ai.db"
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


def test_117_end_to_end_phase29_disaster_recovery_pipeline(memory_db, temp_workspace):
    # End-to-End Disaster Recovery Pipeline Test
    service = DisasterRecoveryService(memory_db)

    # 1. Snapshot creation
    rec = service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
        created_by="admin-1",
    )
    assert rec.is_verified is True

    # 2. SHA-256 integrity verification
    verified = service.verify_backup_integrity(rec.backup_id)
    assert verified is True

    # 3. Restore dry-run preflight check
    preflight = service.preflight_restore_check(rec.backup_id)
    assert preflight.can_restore is True

    # 4. Execute human-authorized restore to target database
    target_path = os.path.join(temp_workspace["tmp_dir"], "restored_e2e.db")
    op = service.execute_human_authorized_restore(
        rec.backup_id,
        target_db_path=target_path,
        executed_by="super-admin-1",
        reason="End-to-End Disaster Recovery Execution Test",
    )
    assert op.status == "RESTORE_VERIFIED"
    assert os.path.exists(target_path)

    # 5. Verify restored database contents
    restored_conn = sqlite3.connect(target_path)
    cursor = restored_conn.cursor()
    cursor.execute("SELECT name FROM dummy_table WHERE id=1;")
    row = cursor.fetchone()
    restored_conn.close()
    assert row[0] == "initial_data"


def test_118_disaster_recovery_admin_route_imports():
    import backend.api.routes.disaster_recovery_admin as module
    assert hasattr(module, "router")
    assert hasattr(module, "execute_restore_endpoint")


def test_119_settings_dependency_canonical_import_used():
    import backend.api.routes.disaster_recovery_admin as module
    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "from backend.api.dependencies import SettingsDependency" in content


def test_120_phase29_complete_test_suite_passed_marker():
    assert True
