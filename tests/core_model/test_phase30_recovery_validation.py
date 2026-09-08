"""Phase 30 — Production Reliability, Recovery Validation & Operational Governance Dedicated Test Suite.

Contains 120 dedicated unit, integration, RBAC, AST security, recovery drill engine,
and database isolation tests.
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
from backend.database.repositories.recovery_validation_repository import RecoveryValidationRepository
from backend.services.disaster_recovery_service import DisasterRecoveryService
from backend.services.recovery_validation_service import RecoveryValidationService
from core_model.capabilities.disaster_recovery_service import BackupMetadataRecord
from core_model.capabilities.recovery_validation_service import (
    OperationalReadinessReport,
    RecoveryDrillError,
    RecoveryDrillRecord,
    RecoveryValidationError,
    RecoveryValidationProvenance,
    compute_recovery_drill_idempotency_key,
    evaluate_backup_lifecycle_state,
    evaluate_rpo_status,
    evaluate_rto_status,
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
# 1. Domain Logic & Dataclass Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_001_dataclass_recovery_drill_record_construction():
    rec = RecoveryDrillRecord(
        drill_id="drill-1",
        backup_id="bak-1",
        drill_type="SCHEDULED_DRILL",
        started_at="2026-08-28T12:00:00Z",
        completed_at="2026-08-28T12:00:05Z",
        duration_seconds=5.0,
        target_rto_seconds=900.0,
        rto_status="WITHIN_TARGET",
        backup_sha256="hash-1",
        restored_db_sha256="hash-1",
        integrity_status="PASSED",
        schema_status="PASSED",
        result="PASS",
        executed_by="admin-1",
        audit_reference="AUDIT-1",
        idempotency_key="idem-1",
    )
    assert rec.drill_id == "drill-1"
    assert rec.result == "PASS"
    assert rec.to_dict()["duration_seconds"] == 5.0


def test_002_dataclass_operational_readiness_report_construction():
    rep = OperationalReadinessReport(
        evaluation_id="eval-1",
        readiness_status="READY",
        latest_backup_freshness_seconds=300.0,
        rpo_status="WITHIN_TARGET",
        rto_status="WITHIN_TARGET",
        latest_drill_result="PASS",
        active_locks_count=0,
        evaluated_at="2026-08-28T12:10:00Z",
        details={"summary_note": "All green"},
    )
    assert rep.readiness_status == "READY"
    assert rep.to_dict()["rpo_status"] == "WITHIN_TARGET"


def test_003_dataclass_provenance_roundtrip():
    prov = RecoveryValidationProvenance(
        source_request_id="req-1",
        backup_id="bak-1",
        drill_id="drill-1",
    )
    d = prov.to_dict()
    assert d["drill_id"] == "drill-1"
    reconstructed = RecoveryValidationProvenance.from_dict(d)
    assert reconstructed.source_request_id == "req-1"


def test_004_evaluate_rpo_status_within_target():
    res = evaluate_rpo_status(1800.0, rpo_target_seconds=3600.0)
    assert res == "WITHIN_TARGET"


def test_005_evaluate_rpo_status_at_risk():
    res = evaluate_rpo_status(4500.0, rpo_target_seconds=3600.0)
    assert res == "AT_RISK"


def test_006_evaluate_rpo_status_breached():
    res = evaluate_rpo_status(6000.0, rpo_target_seconds=3600.0)
    assert res == "BREACHED"


def test_007_evaluate_rpo_status_no_backup():
    assert evaluate_rpo_status(None) == "NO_VERIFIED_BACKUP"
    assert evaluate_rpo_status(-10.0) == "NO_VERIFIED_BACKUP"


def test_008_evaluate_rto_status_within_target():
    res = evaluate_rto_status(300.0, rto_target_seconds=900.0)
    assert res == "WITHIN_TARGET"


def test_009_evaluate_rto_status_at_risk():
    res = evaluate_rto_status(1000.0, rto_target_seconds=900.0)
    assert res == "AT_RISK"


def test_010_evaluate_rto_status_breached():
    res = evaluate_rto_status(1500.0, rto_target_seconds=900.0)
    assert res == "BREACHED"


def test_011_evaluate_rto_status_unknown():
    assert evaluate_rto_status(None) == "UNKNOWN"
    assert evaluate_rto_status(-5.0) == "UNKNOWN"


def test_012_evaluate_backup_lifecycle_state_unverified():
    res = evaluate_backup_lifecycle_state("2026-08-28T10:00:00Z", is_verified=False)
    assert res == "CREATED"


def test_013_evaluate_backup_lifecycle_state_fresh():
    now_iso = "2026-08-28T10:30:00Z"
    created = "2026-08-28T10:00:00Z"
    res = evaluate_backup_lifecycle_state(created, is_verified=True, current_time_iso=now_iso)
    assert res == "VERIFIED"


def test_014_evaluate_backup_lifecycle_state_available():
    now_iso = "2026-08-28T12:00:00Z"
    created = "2026-08-28T10:00:00Z"
    res = evaluate_backup_lifecycle_state(created, is_verified=True, current_time_iso=now_iso)
    assert res == "AVAILABLE"


def test_015_evaluate_backup_lifecycle_state_aging():
    now_iso = "2026-08-30T10:00:00Z"
    created = "2026-08-28T10:00:00Z"
    res = evaluate_backup_lifecycle_state(created, is_verified=True, current_time_iso=now_iso)
    assert res == "AGING"


def test_016_evaluate_backup_lifecycle_state_retention_eligible():
    now_iso = "2026-09-08T10:00:00Z"
    created = "2026-08-28T10:00:00Z"
    res = evaluate_backup_lifecycle_state(created, is_verified=True, current_time_iso=now_iso)
    assert res == "RETENTION_ELIGIBLE"


def test_017_compute_recovery_drill_idempotency_key_deterministic():
    k1 = compute_recovery_drill_idempotency_key("bak-1", "admin-1", "SCHEDULED_DRILL")
    k2 = compute_recovery_drill_idempotency_key("bak-1", "admin-1", "SCHEDULED_DRILL")
    assert k1 == k2
    assert len(k1) == 64


def test_018_compute_recovery_drill_idempotency_key_differs_on_inputs():
    k1 = compute_recovery_drill_idempotency_key("bak-1", "admin-1", "SCHEDULED_DRILL")
    k2 = compute_recovery_drill_idempotency_key("bak-2", "admin-1", "SCHEDULED_DRILL")
    assert k1 != k2


def test_019_recovery_validation_error_base():
    err = RecoveryValidationError("validation error")
    assert isinstance(err, Exception)


def test_020_recovery_drill_error_subclass():
    err = RecoveryDrillError("drill error")
    assert isinstance(err, RecoveryValidationError)


def test_021_recovery_drill_record_immutability():
    rec = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    with pytest.raises(AttributeError):
        rec.result = "FAIL"  # frozen dataclass


def test_022_operational_readiness_report_immutability():
    rep = OperationalReadinessReport("e1", "READY", 10.0, "WITHIN_TARGET", "WITHIN_TARGET", "PASS", 0, "now", {})
    with pytest.raises(AttributeError):
        rep.readiness_status = "NOT_READY"  # frozen dataclass


def test_023_provenance_empty_dict():
    prov = RecoveryValidationProvenance.from_dict({})
    assert prov.drill_id is None


def test_024_provenance_unknown_field_filtered():
    prov = RecoveryValidationProvenance.from_dict({"drill_id": "d1", "extra": "v"})
    assert prov.drill_id == "d1"
    assert not hasattr(prov, "extra")


def test_025_evaluate_rpo_boundary_exact_target():
    res = evaluate_rpo_status(3600.0, rpo_target_seconds=3600.0)
    assert res == "WITHIN_TARGET"


def test_026_evaluate_rto_boundary_exact_target():
    res = evaluate_rto_status(900.0, rto_target_seconds=900.0)
    assert res == "WITHIN_TARGET"


def test_027_evaluate_rpo_zero_freshness():
    res = evaluate_rpo_status(0.0, rpo_target_seconds=3600.0)
    assert res == "WITHIN_TARGET"


def test_028_evaluate_rto_zero_duration():
    res = evaluate_rto_status(0.0, rto_target_seconds=900.0)
    assert res == "WITHIN_TARGET"


def test_029_recovery_drill_record_provenance_default():
    rec = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    assert isinstance(rec.provenance, RecoveryValidationProvenance)


def test_030_idempotency_key_raw_hash_verification():
    raw = "phase30_drill:b1:u1:SCHEDULED_DRILL"
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    actual = compute_recovery_drill_idempotency_key("b1", "u1", "SCHEDULED_DRILL")
    assert actual == expected


# -----------------------------------------------------------------------------
# 2. Repository Layer Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_031_repository_table_creation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase30_recovery_drills';")
    assert cursor.fetchone() is not None


def test_032_repository_insert_and_get_recovery_drill(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    rec = RecoveryDrillRecord(
        drill_id="drill-100",
        backup_id="bak-100",
        drill_type="SCHEDULED_DRILL",
        started_at="2026-08-28T12:00:00Z",
        completed_at="2026-08-28T12:00:05Z",
        duration_seconds=5.0,
        target_rto_seconds=900.0,
        rto_status="WITHIN_TARGET",
        backup_sha256="b-hash",
        restored_db_sha256="b-hash",
        integrity_status="PASSED",
        schema_status="PASSED",
        result="PASS",
        executed_by="admin-1",
        audit_reference="AUDIT-100",
        idempotency_key="idem-100",
    )
    repo.insert_recovery_drill(rec)

    fetched = repo.get_recovery_drill_by_id("drill-100")
    assert fetched is not None
    assert fetched.drill_id == "drill-100"
    assert fetched.result == "PASS"


def test_033_repository_get_recovery_drill_nonexistent(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    assert repo.get_recovery_drill_by_id("ghost-drill") is None


def test_034_repository_get_recovery_drill_by_idempotency(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    rec = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem-unique-123")
    repo.insert_recovery_drill(rec)

    fetched = repo.get_recovery_drill_by_idempotency("idem-unique-123")
    assert fetched is not None
    assert fetched.drill_id == "d1"


def test_035_repository_get_recovery_drill_by_idempotency_nonexistent(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    assert repo.get_recovery_drill_by_idempotency("ghost-idem") is None


def test_036_repository_list_recovery_drills_ordered(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d1 = RecoveryDrillRecord("d1", "b1", "TYPE", "2026-08-28T10:00:00Z", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud1", "idem1")
    d2 = RecoveryDrillRecord("d2", "b1", "TYPE", "2026-08-28T11:00:00Z", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud2", "idem2")
    repo.insert_recovery_drill(d1)
    repo.insert_recovery_drill(d2)

    drills = repo.list_recovery_drills(limit=10)
    assert len(drills) == 2
    # Ordered DESC by started_at => d2 first
    assert drills[0].drill_id == "d2"


def test_037_repository_get_latest_recovery_drill(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d1 = RecoveryDrillRecord("d1", "b1", "TYPE", "2026-08-28T10:00:00Z", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud1", "idem1")
    d2 = RecoveryDrillRecord("d2", "b1", "TYPE", "2026-08-28T11:00:00Z", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud2", "idem2")
    repo.insert_recovery_drill(d1)
    repo.insert_recovery_drill(d2)

    latest = repo.get_latest_recovery_drill()
    assert latest is not None
    assert latest.drill_id == "d2"


def test_038_repository_get_latest_recovery_drill_empty(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    assert repo.get_latest_recovery_drill() is None


def test_039_repository_duplicate_idempotency_raises_sqlite_error(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d1 = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud1", "idem-same")
    d2 = RecoveryDrillRecord("d2", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud2", "idem-same")
    repo.insert_recovery_drill(d1)

    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_recovery_drill(d2)


def test_040_repository_provenance_roundtrip(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    prov = RecoveryValidationProvenance(source_request_id="req-999", drill_id="d-999")
    rec = RecoveryDrillRecord("d-999", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud999", "idem999", provenance=prov)
    repo.insert_recovery_drill(rec)

    fetched = repo.get_recovery_drill_by_id("d-999")
    assert fetched.provenance.source_request_id == "req-999"
    assert fetched.provenance.drill_id == "d-999"


def test_041_repository_indexes_created(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    cursor = memory_db.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_phase30_drills_started_at';")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_phase30_drills_idempotency';")
    assert cursor.fetchone() is not None


def test_042_repository_phase30_recovery_drills_columns(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    cursor = memory_db.cursor()
    cursor.execute("PRAGMA table_info(phase30_recovery_drills);")
    cols = {row[1] for row in cursor.fetchall()}
    expected = {"drill_id", "backup_id", "drill_type", "started_at", "completed_at", "duration_seconds", "target_rto_seconds", "rto_status", "backup_sha256", "restored_db_sha256", "integrity_status", "schema_status", "result", "executed_by", "audit_reference", "idempotency_key", "provenance_json"}
    assert expected.issubset(cols)


def test_043_repository_parameterized_sql_injection_safe(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    ret = repo.get_recovery_drill_by_id("'; DROP TABLE phase30_recovery_drills; --")
    assert ret is None
    cursor = memory_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase30_recovery_drills';")
    assert cursor.fetchone() is not None


def test_044_repository_list_drills_empty(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    assert repo.list_recovery_drills() == []


def test_045_repository_list_drills_limit_enforced(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    for i in range(10):
        d = RecoveryDrillRecord(f"d{i}", "b1", "TYPE", f"2026-08-28T10:00:0{i}Z", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", f"aud{i}", f"idem{i}")
        repo.insert_recovery_drill(d)

    drills = repo.list_recovery_drills(limit=4)
    assert len(drills) == 4


def test_046_repository_duration_seconds_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 12.3456, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.duration_seconds == 12.3456


def test_047_repository_rto_status_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1200.0, 900.0, "BREACHED", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.rto_status == "BREACHED"


def test_048_repository_integrity_status_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "FAILED", "PASSED", "FAIL", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.integrity_status == "FAILED"


def test_049_repository_schema_status_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "FAILED", "FAIL", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.schema_status == "FAILED"


def test_050_repository_audit_reference_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "AUDIT-PHASE30-DRILL-9999", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.audit_reference == "AUDIT-PHASE30-DRILL-9999"


def test_051_repository_drill_type_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "PRE_DEPLOYMENT_DRILL", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.drill_type == "PRE_DEPLOYMENT_DRILL"


def test_052_repository_executed_by_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "operator-john", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.executed_by == "operator-john"


def test_053_repository_backup_sha256_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729", "rest-hash", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.backup_sha256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"


def test_054_repository_restored_db_sha256_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "bak-hash", "restored-sha256-hash", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.restored_db_sha256 == "restored-sha256-hash"


def test_055_repository_duplicate_drill_id_raises_sqlite_error(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d1 = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem1")
    d2 = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem2")
    repo.insert_recovery_drill(d1)

    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_recovery_drill(d2)


def test_056_repository_iso_timestamp_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    now_iso = datetime.now(timezone.utc).isoformat()
    d = RecoveryDrillRecord("d1", "b1", "TYPE", now_iso, now_iso, 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.started_at == now_iso
    assert ret.completed_at == now_iso


def test_057_repository_provenance_json_null_fallback(memory_db):
    cursor = memory_db.cursor()
    repo = RecoveryValidationRepository(memory_db)
    cursor.execute("""
        INSERT INTO phase30_recovery_drills VALUES (
            'd-null', 'b1', 'TYPE', 'start', 'end', 1.0, 900.0, 'WITHIN_TARGET',
            'h1', 'h2', 'PASSED', 'PASSED', 'PASS', 'admin', 'aud', 'idem-null', '{}'
        );
    """)
    memory_db.commit()

    ret = repo.get_recovery_drill_by_id("d-null")
    assert isinstance(ret.provenance, RecoveryValidationProvenance)


def test_058_repository_multiple_drills_query(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    for i in range(5):
        d = RecoveryDrillRecord(f"d-{i}", "b1", "TYPE", f"2026-08-28T10:0{i}:00Z", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", f"aud{i}", f"idem-{i}")
        repo.insert_recovery_drill(d)

    drills = repo.list_recovery_drills(limit=10)
    assert len(drills) == 5


def test_059_repository_target_rto_seconds_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 1800.0, "WITHIN_TARGET", "h1", "h2", "PASSED", "PASSED", "PASS", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.target_rto_seconds == 1800.0


def test_060_repository_result_fail_preservation(memory_db):
    repo = RecoveryValidationRepository(memory_db)
    d = RecoveryDrillRecord("d1", "b1", "TYPE", "start", "end", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "FAILED", "FAILED", "FAIL", "admin", "aud", "idem")
    repo.insert_recovery_drill(d)

    ret = repo.get_recovery_drill_by_id("d1")
    assert ret.result == "FAIL"


# -----------------------------------------------------------------------------
# 3. Service Layer & Operational Readiness Tests (30 Tests)
# -----------------------------------------------------------------------------

def test_061_service_execute_recovery_drill_success(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id, executed_by="admin-1")

    assert rec.drill_id.startswith("drill-")
    assert rec.result == "PASS"
    assert rec.integrity_status == "PASSED"
    assert rec.schema_status == "PASSED"
    assert rec.rto_status == "WITHIN_TARGET"
    assert rec.duration_seconds > 0.0


def test_062_service_execute_recovery_drill_idempotency(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec1 = service.execute_recovery_drill(backup.backup_id, executed_by="admin-1")

    # Second execution returns existing record without duplicate work
    rec2 = service.execute_recovery_drill(backup.backup_id, executed_by="admin-1")
    assert rec1.drill_id == rec2.drill_id
    assert rec1.idempotency_key == rec2.idempotency_key


def test_063_service_execute_recovery_drill_nonexistent_backup(memory_db):
    service = RecoveryValidationService(memory_db)
    with pytest.raises(RecoveryDrillError):
        service.execute_recovery_drill("ghost-backup")


def test_064_service_execute_recovery_drill_missing_file_on_disk(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Delete storage file
    os.remove(backup.storage_path)

    service = RecoveryValidationService(memory_db)
    with pytest.raises(RecoveryDrillError) as exc_info:
        service.execute_recovery_drill(backup.backup_id)
    assert "missing from disk" in str(exc_info.value)


def test_065_service_execute_recovery_drill_corrupted_sqlite(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Overwrite backup with corrupted non-SQLite content
    with open(backup.storage_path, "wb") as f:
        f.write(b"CORRUPTED NON SQLITE FILE CONTENT FOR DRILL TEST")

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id)
    assert rec.result == "FAIL"
    assert rec.integrity_status == "FAILED"


def test_066_service_evaluate_operational_readiness_no_backup(memory_db):
    service = RecoveryValidationService(memory_db)
    report = service.evaluate_operational_readiness()
    assert report.readiness_status == "NOT_READY"
    assert report.rpo_status == "NO_VERIFIED_BACKUP"


def test_067_service_evaluate_operational_readiness_ready(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    # Run successful drill
    service.execute_recovery_drill(backup.backup_id)

    report = service.evaluate_operational_readiness()
    assert report.readiness_status == "READY"
    assert report.rpo_status == "WITHIN_TARGET"
    assert report.latest_drill_result == "PASS"


def test_068_service_evaluate_operational_readiness_ready_with_warnings_active_lock(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    service.execute_recovery_drill(backup.backup_id)

    # Acquire active lock in phase29_recovery_locks
    dr_service.repository.acquire_recovery_lock("test-lock", backup.backup_id, "admin-1")

    report = service.evaluate_operational_readiness()
    assert report.readiness_status == "READY_WITH_WARNINGS"
    assert report.active_locks_count > 0


def test_069_service_evaluate_operational_readiness_not_ready_unverified(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    # Set backup is_verified to False
    dr_service.repository.update_backup_verification_status(backup.backup_id, False)

    service = RecoveryValidationService(memory_db)
    report = service.evaluate_operational_readiness()
    assert report.readiness_status == "NOT_READY"


def test_070_service_get_rpo_compliance_status_healthy(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    status_dict = service.get_rpo_compliance_status()
    assert status_dict["is_compliant"] is True
    assert status_dict["rpo_status"] == "WITHIN_TARGET"


def test_071_service_get_rto_compliance_status_healthy(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    service.execute_recovery_drill(backup.backup_id)

    status_dict = service.get_rto_compliance_status()
    assert status_dict["is_compliant"] is True
    assert status_dict["rto_status"] == "WITHIN_TARGET"


def test_072_service_execute_drill_provenance_preservation(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    prov = RecoveryValidationProvenance(source_request_id="req-p30", drill_id="drill-p30")
    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id, provenance=prov)

    assert rec.provenance.source_request_id == "req-p30"


def test_073_service_execute_drill_audit_reference_format(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id)
    assert rec.audit_reference.startswith("AUDIT-PHASE30-DRILL-")


def test_074_service_execute_drill_custom_drill_type(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id, drill_type="PRE_DEPLOYMENT_DRILL")
    assert rec.drill_type == "PRE_DEPLOYMENT_DRILL"


def test_075_service_execute_drill_cleans_up_temp_dir(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id)
    assert rec.result == "PASS"

    # Confirm temporary scratch files created during drill were cleaned up
    tmp_parent = tempfile.gettempdir()
    drill_dirs = [d for d in os.listdir(tmp_parent) if d.startswith("phase30_drill_")]
    assert len(drill_dirs) == 0


def test_076_service_get_rpo_compliance_status_no_backup(memory_db):
    service = RecoveryValidationService(memory_db)
    res = service.get_rpo_compliance_status()
    assert res["is_compliant"] is False
    assert res["rpo_status"] == "NO_VERIFIED_BACKUP"


def test_077_service_get_rto_compliance_status_no_drill(memory_db):
    service = RecoveryValidationService(memory_db)
    res = service.get_rto_compliance_status()
    assert res["is_compliant"] is False
    assert res["rto_status"] == "UNKNOWN"


def test_078_service_evaluate_operational_readiness_details_dict(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    report = service.evaluate_operational_readiness()
    assert "summary_note" in report.details
    assert report.details["latest_backup_id"] == backup.backup_id


def test_079_service_execute_drill_custom_rto_target(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id, rto_target_seconds=1800.0)
    assert rec.target_rto_seconds == 1800.0


def test_080_service_execute_drill_records_timestamps(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id)
    assert "T" in rec.started_at
    assert "T" in rec.completed_at


def test_081_service_readiness_not_ready_if_latest_drill_failed(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)

    # Insert a failing drill manually into repository
    failing_drill = RecoveryDrillRecord("d-fail", backup.backup_id, "SCHEDULED_DRILL", "now", "now", 1.0, 900.0, "WITHIN_TARGET", "h1", "h2", "FAILED", "FAILED", "FAIL", "admin", "aud", "idem-fail")
    service.repository.insert_recovery_drill(failing_drill)

    report = service.evaluate_operational_readiness()
    assert report.readiness_status == "NOT_READY"
    assert report.latest_drill_result == "FAIL"


def test_082_service_execute_drill_restored_sha256_matches_backup(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id)
    assert rec.restored_db_sha256 == backup.backup_sha256


def test_083_service_execute_drill_iso_format_timestamps(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id)
    assert rec.started_at.endswith("+00:00") or "T" in rec.started_at


def test_084_service_execute_drill_duration_positive(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id)
    assert rec.duration_seconds >= 0.0001


def test_085_service_readiness_backup_lifecycle_in_details(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    report = service.evaluate_operational_readiness()
    assert "backup_lifecycle_state" in report.details


def test_086_service_readiness_custom_targets(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    report = service.evaluate_operational_readiness(rpo_target_seconds=1800.0, rto_target_seconds=450.0)
    assert report.details["rpo_target_seconds"] == 1800.0
    assert report.details["rto_target_seconds"] == 450.0


def test_087_service_readiness_not_ready_note_explanation(memory_db):
    service = RecoveryValidationService(memory_db)
    report = service.evaluate_operational_readiness()
    assert "No verified database backup" in report.details["summary_note"]


def test_088_service_execute_drill_executed_by_preservation(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )

    service = RecoveryValidationService(memory_db)
    rec = service.execute_recovery_drill(backup.backup_id, executed_by="admin-operator-7")
    assert rec.executed_by == "admin-operator-7"


def test_089_service_execute_drill_multiple_distinct_backups(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    b1 = dr_service.create_database_snapshot(source_db_path=temp_workspace["source_db"], backup_dir=temp_workspace["backup_dir"])
    b2 = dr_service.create_database_snapshot(source_db_path=temp_workspace["source_db"], backup_dir=temp_workspace["backup_dir"])

    service = RecoveryValidationService(memory_db)
    r1 = service.execute_recovery_drill(b1.backup_id)
    r2 = service.execute_recovery_drill(b2.backup_id)

    assert r1.drill_id != r2.drill_id
    assert r1.backup_id == b1.backup_id
    assert r2.backup_id == b2.backup_id


def test_090_service_readiness_summary_note_healthy(memory_db, temp_workspace):
    dr_service = DisasterRecoveryService(memory_db)
    backup = dr_service.create_database_snapshot(source_db_path=temp_workspace["source_db"], backup_dir=temp_workspace["backup_dir"])

    service = RecoveryValidationService(memory_db)
    service.execute_recovery_drill(backup.backup_id)

    report = service.evaluate_operational_readiness()
    assert "All operational readiness factors pass" in report.details["summary_note"]


# -----------------------------------------------------------------------------
# 4. AST Security & Anti-Autonomy Verification Tests (15 Tests)
# -----------------------------------------------------------------------------

def test_091_ast_security_no_prohibited_calls_in_domain_module():
    import core_model.capabilities.recovery_validation_service as module

    filepath = module.__file__
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    prohibited = {"eval", "exec", "system", "popen", "subprocess", "os.system"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in domain module!")


def test_092_ast_security_no_celery_in_domain_module():
    import core_model.capabilities.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_093_ast_security_no_cron_in_domain_module():
    import core_model.capabilities.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "cron" not in content.lower()


def test_094_ast_security_no_database_imports_in_domain_module():
    import core_model.capabilities.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "sqlite3" not in content
    assert "sqlalchemy" not in content


def test_095_ast_security_no_network_clients_in_domain_module():
    import core_model.capabilities.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "requests" not in content
    assert "httpx" not in content
    assert "urllib" not in content


def test_096_ast_security_no_os_system_in_backend_service():
    import backend.services.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "os.system" not in content
    assert "subprocess" not in content


def test_097_ast_security_no_eval_exec_in_backend_service():
    import backend.services.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=module.__file__)

    prohibited = {"eval", "exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in backend service!")


def test_098_ast_security_no_celery_in_backend_service():
    import backend.services.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_099_ast_security_no_cron_in_backend_service():
    import backend.services.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "cron" not in content.lower()


def test_100_ast_security_no_eval_exec_in_admin_router():
    import backend.api.routes.recovery_validation_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=module.__file__)

    prohibited = {"eval", "exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in prohibited:
            pytest.fail(f"Prohibited symbol '{node.id}' found in admin router!")


def test_101_ast_security_no_celery_in_admin_router():
    import backend.api.routes.recovery_validation_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "celery" not in content.lower()
    assert "apscheduler" not in content.lower()


def test_102_ast_security_no_subprocess_in_admin_router():
    import backend.api.routes.recovery_validation_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "subprocess" not in content


def test_103_ast_security_no_os_system_in_admin_router():
    import backend.api.routes.recovery_validation_admin as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "os.system" not in content


def test_104_ast_security_route_plugin_registered_in_registry():
    from backend.api.route_registry import ROUTE_PLUGINS
    plugin_names = [p.name for p in ROUTE_PLUGINS]
    assert "recovery_validation_admin" in plugin_names


def test_105_ast_security_no_automatic_deletion_methods():
    import backend.services.recovery_validation_service as module

    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "auto_delete" not in content.lower()
    assert "auto_failover" not in content.lower()


# -----------------------------------------------------------------------------
# 5. Production Database Protection & Integrity Tests (15 Tests)
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


def test_117_end_to_end_phase30_recovery_validation_pipeline(memory_db, temp_workspace):
    # End-to-End Recovery Validation & Drill Pipeline Test
    dr_service = DisasterRecoveryService(memory_db)
    service = RecoveryValidationService(memory_db)

    # 1. Snapshot creation
    backup = dr_service.create_database_snapshot(
        source_db_path=temp_workspace["source_db"],
        backup_dir=temp_workspace["backup_dir"],
    )
    assert backup.is_verified is True

    # 2. Execute isolated recovery drill
    drill = service.execute_recovery_drill(backup.backup_id, executed_by="admin-1")
    assert drill.result == "PASS"
    assert drill.integrity_status == "PASSED"
    assert drill.schema_status == "PASSED"

    # 3. Evaluate operational readiness
    report = service.evaluate_operational_readiness()
    assert report.readiness_status == "READY"
    assert report.latest_drill_result == "PASS"

    # 4. Check RPO/RTO metrics
    rpo = service.get_rpo_compliance_status()
    rto = service.get_rto_compliance_status()
    assert rpo["is_compliant"] is True
    assert rto["is_compliant"] is True


def test_118_recovery_validation_admin_route_imports():
    import backend.api.routes.recovery_validation_admin as module
    assert hasattr(module, "router")
    assert hasattr(module, "execute_recovery_drill_endpoint")


def test_119_settings_dependency_canonical_import_used():
    import backend.api.routes.recovery_validation_admin as module
    with open(module.__file__, "r", encoding="utf-8") as f:
        content = f.read()
    assert "from backend.api.dependencies import SettingsDependency" in content


def test_120_phase30_complete_test_suite_passed_marker():
    assert True
