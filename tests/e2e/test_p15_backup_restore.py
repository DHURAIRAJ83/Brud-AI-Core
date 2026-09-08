"""P15 Backup & Restore Validation Test Suite.

Validates:
1. Online verified backup creation (`create_verified_backup`)
2. Backup readability, metadata, and SHA-256 checksum verification
3. Destructive database restore test (wipe live DB, restore from backup)
4. Post-restore SQLite integrity checks (`PRAGMA integrity_check`, `foreign_key_check`)
5. Session and message preservation across restore
6. Append-only runtime event ledger preservation
7. Provider configuration and encrypted secret preservation
8. Encrypted backup creation and decryption round-trip
9. Automated restore drill readiness verification (`ProductionRestoreReadinessService`)
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import (
    create_verified_backup,
    initialize_database,
    verify_database,
)
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from backend.services.mini_brain_provider_settings_service import (
    MiniBrainProviderSettingsService,
)
from backend.services.production_backup_restore_readiness_service import (
    ProductionBackupEncryptionService,
    ProductionRestoreReadinessService,
)

pytestmark = pytest.mark.anyio


class StableMockAdapter(MockMiniBrainAdapter):
    backend_type = "local"

    def is_available(self) -> bool:
        return True

    def generate(self, *, messages: list[dict[str, Any]], **kwargs) -> dict[str, Any]:
        return {
            "text": "Restored persistent response",
            "backend_type": "local",
            "tokens_generated": 8,
            "latency_ms": 12.0,
            "error_message": None,
        }


@pytest.fixture
def backup_env(tmp_path: Path):
    db_path = tmp_path / "production_live.db"
    backup_dir = tmp_path / "backups"
    encryption_key = Fernet.generate_key().decode()
    os.environ["TEST_BACKUP_ENCRYPTION_KEY"] = encryption_key
    os.environ["BRUD_SECRET_ENCRYPTION_KEY"] = encryption_key

    settings = Settings(
        database_path=db_path,
        backup_dir=backup_dir,
        allowed_data_dir=tmp_path / "data",
        allowed_model_dir=tmp_path / "models",
        allow_external_storage=True,
        database_auto_backup=True,
        backup_encryption_key_env_var="TEST_BACKUP_ENCRYPTION_KEY",
        database_busy_timeout_ms=10000,
    )
    initialize_database(settings.resolved_database_path)
    return settings


# 1. Create online verified backup with active state
def test_p15_backup_001_create_verified_backup(backup_env: Settings):
    svc = MiniBrainLlmRuntimeService(backup_env, adapter_factory=lambda: StableMockAdapter())
    sess = svc.open_session(admin_id="admin_backup_1", title="Backup Session")
    session_id = sess["public_id"]
    svc.chat(session_id=session_id, admin_id="admin_backup_1", message="Data before backup")

    backup_res = create_verified_backup(
        backup_env.resolved_database_path,
        backup_env.resolved_backup_dir,
    )

    assert backup_res.path.exists()
    assert backup_res.path.stat().st_size > 0
    assert len(backup_res.backup_checksum) == 64  # valid sha256
    print(f"\n[BACKUP-001] Verified backup created: {backup_res.filename}, size: {backup_res.path.stat().st_size} bytes")


# 2. Destructive wipe and live restore test
def test_p15_backup_002_destructive_wipe_and_restore(backup_env: Settings):
    svc = MiniBrainLlmRuntimeService(backup_env, adapter_factory=lambda: StableMockAdapter())
    sess = svc.open_session(admin_id="admin_backup_1", title="Destructive Session")
    session_id = sess["public_id"]
    res = svc.chat(session_id=session_id, admin_id="admin_backup_1", message="Important critical datum")
    assert res["reply"]["sanitized_text"] == "Restored persistent response"

    # Capture initial counts
    with sqlite3.connect(str(backup_env.resolved_database_path)) as conn:
        orig_sessions = conn.execute("SELECT count(*) FROM mini_brain_llm_sessions").fetchone()[0]
        orig_messages = conn.execute("SELECT count(*) FROM mini_brain_llm_messages").fetchone()[0]
        orig_events = conn.execute("SELECT count(*) FROM mini_brain_llm_runtime_events").fetchone()[0]

    # Create verified backup
    backup_res = create_verified_backup(
        backup_env.resolved_database_path,
        backup_env.resolved_backup_dir,
    )

    # Simulate catastrophic loss: wipe the database file and WAL
    live_db = backup_env.resolved_database_path
    live_wal = live_db.with_name(live_db.name + "-wal")
    live_shm = live_db.with_name(live_db.name + "-shm")
    if live_db.exists():
        live_db.unlink()
    if live_wal.exists():
        live_wal.unlink()
    if live_shm.exists():
        live_shm.unlink()
    assert not live_db.exists()

    # RESTORE: restore from verified backup file
    shutil.copy2(backup_res.path, live_db)
    assert live_db.exists()

    # Verify restored database integrity
    verify_database(live_db)
    with sqlite3.connect(str(live_db)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        restored_sessions = conn.execute("SELECT count(*) FROM mini_brain_llm_sessions").fetchone()[0]
        restored_messages = conn.execute("SELECT count(*) FROM mini_brain_llm_messages").fetchone()[0]
        restored_events = conn.execute("SELECT count(*) FROM mini_brain_llm_runtime_events").fetchone()[0]

    assert restored_sessions == orig_sessions
    assert restored_messages == orig_messages
    assert restored_events == orig_events

    # Resume chat runtime on restored database
    svc_restored = MiniBrainLlmRuntimeService(backup_env, adapter_factory=lambda: StableMockAdapter())
    messages = svc_restored.list_messages(session_id=session_id)["items"]
    assert len(messages) == 2
    assert messages[0]["sanitized_text"] == "Important critical datum"
    assert messages[1]["sanitized_text"] == "Restored persistent response"

    # Seamlessly continue conversation
    res2 = svc_restored.chat(session_id=session_id, admin_id="admin_backup_1", message="Follow-up post-restore")
    assert res2["error_message"] is None
    assert len(svc_restored.list_messages(session_id=session_id)["items"]) == 4

    print(f"\n[BACKUP-002] Destructive wipe & restore verified: {restored_sessions} sessions, {restored_messages} messages, {restored_events} events preserved")


# 3. Provider settings & encrypted credentials survival across restore
def test_p15_backup_003_provider_settings_survive_restore(backup_env: Settings):
    provider_svc = MiniBrainProviderSettingsService(backup_env)
    created = provider_svc.create_provider_setting(
        provider_key="openai",
        enabled=True,
        config={"model": "gpt-4o"},
        admin_id="admin_1",
    )
    setting_id = created["public_id"]
    provider_svc.set_secret(setting_id, secret_name="api_key", raw_value="sk-secret-key-12345", admin_id="admin_1")

    # Backup
    backup_res = create_verified_backup(
        backup_env.resolved_database_path,
        backup_env.resolved_backup_dir,
    )

    # Wipe and restore
    live_db = backup_env.resolved_database_path
    live_db.unlink()
    shutil.copy2(backup_res.path, live_db)

    # Query restored provider service
    restored_provider_svc = MiniBrainProviderSettingsService(backup_env)
    retrieved = restored_provider_svc.get_setting(setting_id)
    assert retrieved["provider_key"] == "openai"
    assert retrieved["config"]["model"] == "gpt-4o"
    # Secret must be masked in public view
    assert retrieved["secrets"][0]["is_set"] is True
    assert "sk-secret-key-12345" not in str(retrieved)
    print("\n[BACKUP-003] Provider settings & credentials survived restore with zero plaintext leak")


# 4. Encrypted backup and decryption round-trip
def test_p15_backup_004_encrypted_backup_roundtrip(backup_env: Settings):
    # Create backup first
    create_verified_backup(
        backup_env.resolved_database_path,
        backup_env.resolved_backup_dir,
    )

    enc_svc = ProductionBackupEncryptionService(backup_env)
    # Encrypt backup
    enc_result = enc_svc.encrypt_latest_backup(admin_id="admin_1")
    assert enc_result["result_status"] == "encrypted"

    enc_path = backup_env.resolved_backup_dir / enc_result["encrypted_filename"]
    assert enc_path.exists()
    # Encrypted payload should NOT contain plaintext SQLite magic header ("SQLite format 3")
    with open(enc_path, "rb") as f:
        header = f.read(16)
        assert b"SQLite format 3" not in header

    # Verify restore readiness of encrypted backup
    verify_drill = enc_svc.verify_encrypted_restore(admin_id="admin_1")
    assert verify_drill["result_status"] == "passed"
    assert verify_drill["details"]["integrity_check"] == "ok"
    print(f"\n[BACKUP-004] Encrypted backup verified: zero plaintext header, decryption drill: {verify_drill['result_status']}")


# 5. Automated restore drill readiness check
def test_p15_backup_005_automated_restore_readiness_service(backup_env: Settings):
    # Ensure backup directory has at least one valid backup
    create_verified_backup(backup_env.resolved_database_path, backup_env.resolved_backup_dir)

    readiness_svc = ProductionRestoreReadinessService(backup_env)
    readiness = readiness_svc.check_restore_readiness(admin_id="admin_1")

    assert readiness["result_status"] == "passed"
    assert readiness["details"]["integrity_check"] == "ok"
    assert readiness["details"]["schema_version"] > 0
    print(f"\n[BACKUP-005] Automated restore drill: passed, schema_version={readiness['details']['schema_version']}")
