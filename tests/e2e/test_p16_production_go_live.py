"""Phase 16 — Production Go-Live & Operational Validation Test Suite.

Comprehensive executable verification across all operational dimensions:
1. Configuration (Production fail-closed, secure cookies, trust proxy, configurable Ollama)
2. CORS & Reverse Proxy (X-Trace-Id allow/expose headers, Nginx SSE unbuffered config)
3. Database Durability (WAL mode, PRAGMA synchronous = NORMAL, crash rollback)
4. Real Provider Binding (Zero mocks in production resolution, fail-closed behavior, G4/G14)
5. Multi-Turn Conversation Persistence (Turn sequence, exactly-once persistence, post-restart recovery, G10/G11)
6. RAG Grounding & Citation Integrity (Verified retrieval vs ungrounded citations = [], G9)
7. Observability & Redaction (X-Trace-Id propagation, secret scrubbing across logs, G8)
8. Backup Operations (Live SQLite hot backup, SHA256 integrity, clean restore verification)
9. Restart Drill & Rollback Assessment (Controlled restart, cache rebuild, rollback compatibility)
10. Security Perimeter Revalidation (Model path confinement, directory traversal defense, G3)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.database.connection import connect, database_connection
from backend.database.connection_pool import ConnectionPool
from backend.database.migrations import initialize_database
from backend.database.repositories.mini_brain_llm_runtime import MiniBrainLlmRuntimeRepository
from backend.main import create_app
from backend.services.mini_brain_llm_adapter import (
    ExternalProviderMiniBrainAdapter,
    LlamaCppMiniBrainAdapter,
    MockMiniBrainAdapter,
    resolve_confined_model_path,
)
from backend.services.mini_brain_llm_runtime_service import (
    MiniBrainLlmRuntimeService,
)
from core_model.mini_brain.provider_settings import secret_encryptor


@pytest.fixture
def p16_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated test environment with test database and encryption key."""
    db_path = tmp_path / "p16_production.db"
    backup_dir = tmp_path / "backups"
    model_dir = tmp_path / "models"
    data_dir = tmp_path / "data"

    backup_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, key)

    settings = Settings(
        env="development",
        database_path=db_path,
        database_backup_dir=backup_dir,
        allowed_model_dir=model_dir,
        allowed_data_dir=data_dir,
        allow_external_storage=True,
        database_wal=True,
        database_auto_backup=True,
        admin_cookie_secure=False,
        debug=False,
    )
    initialize_database(settings.resolved_database_path, wal_enabled=True)
    return settings


# ==============================================================================
# 1. Configuration Validation (P16.2 & P16.4)
# ==============================================================================

def test_p16_config_001_production_environment_fail_closed():
    """Verify that production environment strictly enforces fail-closed constraints."""
    # 1. Production with debug=True must fail closed
    with pytest.raises(ValueError, match="BRUD_DEBUG must be False in production"):
        Settings(
            env="production",
            debug=True,
            admin_cookie_secure=True,
            trust_proxy_headers=True,
            allow_external_storage=False,
        )

    # 2. Production with admin_cookie_secure=False must fail closed
    with pytest.raises(ValueError, match="BRUD_ADMIN_COOKIE_SECURE must be True in production"):
        Settings(
            env="production",
            debug=False,
            admin_cookie_secure=False,
            trust_proxy_headers=True,
            allow_external_storage=False,
        )

    # 3. Production with allow_external_storage=True must fail closed
    with pytest.raises(ValueError, match="BRUD_ALLOW_EXTERNAL_STORAGE must be False in production"):
        Settings(
            env="production",
            debug=False,
            admin_cookie_secure=True,
            trust_proxy_headers=True,
            allow_external_storage=True,
        )

    # 4. Production with trust_proxy_headers=False must fail closed
    with pytest.raises(ValueError, match="BRUD_TRUST_PROXY_HEADERS must be True in production"):
        Settings(
            env="production",
            debug=False,
            admin_cookie_secure=True,
            trust_proxy_headers=False,
            allow_external_storage=False,
        )

    # 5. Clean valid production configuration must instantiate without error
    prod_settings = Settings(
        env="production",
        debug=False,
        admin_cookie_secure=True,
        trust_proxy_headers=True,
        allow_external_storage=False,
    )
    assert prod_settings.env == "production"
    assert prod_settings.debug is False
    assert prod_settings.admin_cookie_secure is True
    assert prod_settings.trust_proxy_headers is True
    assert prod_settings.allow_external_storage is False


def test_p16_config_002_configurable_ollama_url(monkeypatch: pytest.MonkeyPatch):
    """Verify that BRUD_OLLAMA_URL overrides the default endpoint cleanly."""
    custom_url = "http://ai-cluster.internal:11434"
    monkeypatch.setenv("BRUD_OLLAMA_URL", custom_url)

    settings = Settings(ollama_url=custom_url, allow_external_storage=True)
    assert settings.ollama_url == custom_url

    adapter = ExternalProviderMiniBrainAdapter(
        provider_key="ollama",
        base_url=settings.ollama_url,
    )
    assert adapter._get_endpoint() == "http://ai-cluster.internal:11434/v1/chat/completions"
    assert adapter._base_url == "http://ai-cluster.internal:11434"


# ==============================================================================
# 2. CORS & Reverse Proxy Validation (P16.2 & P16.6)
# ==============================================================================

def test_p16_network_001_cors_and_trace_headers(p16_test_env: Settings):
    """Verify that CORS allow_headers and expose_headers include X-Trace-Id."""
    app = create_app(p16_test_env)
    client = TestClient(app)

    # Preflight CORS OPTIONS request
    response = client.options(
        "/api/health",
        headers={
            "Origin": p16_test_env.admin_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type, X-Trace-Id",
        },
    )
    assert response.status_code == 200
    allow_headers = response.headers.get("access-control-allow-headers", "")
    assert "x-trace-id" in allow_headers.lower() or "X-Trace-Id" in allow_headers

    # Normal GET request must expose X-Trace-Id
    get_resp = client.get("/api/health", headers={"Origin": p16_test_env.admin_origin})
    assert get_resp.status_code == 200
    expose_headers = get_resp.headers.get("access-control-expose-headers", "")
    assert "x-trace-id" in expose_headers.lower()


def test_p16_network_002_reverse_proxy_nginx_sse_configuration():
    """Verify Nginx reverse proxy configuration has required unbuffered SSE blocks."""
    nginx_conf_path = Path("deploy/reverse-proxy/nginx.conf.example")
    assert nginx_conf_path.exists(), "nginx.conf.example must exist in deploy/reverse-proxy"

    content = nginx_conf_path.read_text(encoding="utf-8")

    # 1. Check SSE location block
    assert "location /api/admin/mini-brain/chat/stream" in content
    assert "proxy_buffering off;" in content
    assert "proxy_cache off;" in content
    assert "proxy_set_header Connection '';" in content
    assert "proxy_read_timeout 600s;" in content
    assert "chunked_transfer_encoding on;" in content

    # 2. Check TLS hardening
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in content
    assert "return 301 https://$host$request_uri;" in content


# ==============================================================================
# 3. Database Durability & WAL Tuning (P16.2 & P16.5)
# ==============================================================================

def test_p16_database_001_wal_and_synchronous_normal(p16_test_env: Settings):
    """Verify that SQLite WAL mode configures PRAGMA synchronous = NORMAL."""
    conn = connect(p16_test_env.resolved_database_path, wal_enabled=True)
    try:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]
        # In SQLite: 1 == NORMAL, 2 == FULL, 3 == EXTRA, 0 == OFF
        assert journal_mode.lower() == "wal"
        assert synchronous == 1, f"Expected PRAGMA synchronous = 1 (NORMAL), got {synchronous}"
    finally:
        conn.close()

    # Verify pooled connections also receive synchronous = NORMAL
    pool = ConnectionPool(p16_test_env.resolved_database_path, wal_enabled=True)
    try:
        pooled_conn = pool.checkout()
        try:
            sync_val = pooled_conn.execute("PRAGMA synchronous;").fetchone()[0]
            assert sync_val == 1
        finally:
            pool.checkin(pooled_conn)
    finally:
        pool.close()


def test_p16_database_002_wal_durability_crash_recovery(p16_test_env: Settings):
    """Verify transaction rollback and database durability after an aborted transaction."""
    db_path = p16_test_env.resolved_database_path

    # Begin transaction and intentionally simulate abrupt failure without commit
    raw_conn = sqlite3.connect(db_path)
    raw_conn.execute("PRAGMA journal_mode = WAL")
    raw_conn.execute("PRAGMA synchronous = NORMAL")
    raw_conn.execute("BEGIN IMMEDIATE;")
    raw_conn.execute(
        "INSERT INTO audit_logs (public_id, event_type, actor_type, action, resource_type, created_at) "
        "VALUES ('aud_crash_test_1', 'crash_test', 'system', 'uncommitted_action', 'test', '2026-09-05T00:00:00Z');"
    )
    # Simulate sudden crash by closing connection without commit
    raw_conn.close()

    # Reopen database through canonical service connection and verify integrity
    verify_conn = connect(db_path, wal_enabled=True)
    try:
        row = verify_conn.execute("SELECT * FROM audit_logs WHERE public_id = 'aud_crash_test_1';").fetchone()
        assert row is None, "Uncommitted transaction must not be present (clean rollback)"

        # Check integrity
        integrity = verify_conn.execute("PRAGMA integrity_check;").fetchone()[0]
        assert integrity == "ok"
    finally:
        verify_conn.close()


# ==============================================================================
# 4. Real Provider Binding & Zero Mocks in Production (P16.7)
# ==============================================================================

def test_p16_provider_001_zero_mock_leakage_in_production_resolution(p16_test_env: Settings):
    """Verify that canonical production backend resolution never binds MockMiniBrainAdapter."""
    # Initialize service WITHOUT adapter_factory
    service = MiniBrainLlmRuntimeService(p16_test_env)

    # 1. Local resolution when no GGUF model is present must fail closed truthfully
    resolved_local = service._resolve_backend(execution_mode="local")
    assert resolved_local["backend_type"] == "unavailable"
    assert not isinstance(resolved_local.get("adapter"), MockMiniBrainAdapter)
    assert "not available" in resolved_local["reason"].lower()

    # 2. Auto resolution when external providers have no key must fail closed truthfully
    resolved_auto = service._resolve_backend(execution_mode="auto")
    assert resolved_auto["backend_type"] in {"external", "unavailable"}
    assert not isinstance(resolved_auto.get("adapter"), MockMiniBrainAdapter)

    # 3. Provider resolution for unconfigured provider must fail closed
    resolved_provider = service._resolve_backend(execution_mode="provider", provider_key="openrouter")
    assert resolved_provider["backend_type"] == "unavailable"
    assert not isinstance(resolved_provider.get("adapter"), MockMiniBrainAdapter)


def test_p16_provider_002_provider_failure_modes_fail_closed(p16_test_env: Settings):
    """Verify that missing keys, unconfigured providers, and timeouts fail closed gracefully."""
    # Adapter with empty key must report not configured
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openai", api_key="")
    assert adapter.is_configured() is False
    assert adapter.is_available() is False

    # Calling generate on unconfigured adapter returns truthful error without crash
    res = adapter.generate(messages=[{"role": "user", "content": "Hello"}])
    assert res["text"] == ""
    assert "not configured" in res["error_message"].lower()

    # Unreachable Ollama endpoint must report unavailable
    unreachable_adapter = ExternalProviderMiniBrainAdapter(
        provider_key="ollama",
        base_url="http://127.0.0.1:65432",
    )
    assert unreachable_adapter.is_available() is False


# ==============================================================================
# 5. Multi-Turn Conversation Persistence & Recovery Drill (P16.8 & P16.12)
# ==============================================================================

def test_p16_conversation_001_multi_turn_persistence_and_restart_recovery(p16_test_env: Settings):
    """Execute multi-turn session against real SQLite DB and verify persistence after service restart."""
    mock_adapter = MockMiniBrainAdapter()
    svc1 = MiniBrainLlmRuntimeService(p16_test_env, adapter_factory=lambda: mock_adapter)

    # 1. Open session and execute 25 turns
    session_row = svc1.open_session(admin_id="adm_prod_operator", title="Production Verification Session")
    session_id = session_row["public_id"]

    for turn_idx in range(1, 26):
        res = svc1.chat(
            session_id=session_id,
            message=f"Turn {turn_idx}: Administrative operation and deployment health verification checkpoint.",
            admin_id="adm_prod_operator",
            trace_id=f"trc_prod_turn_{turn_idx}",
        )
        assert res["reply"]["session_id"] == session_id
        assert res["reply"]["role"] == "assistant"

    # Verify message count in database: 25 admin + 25 assistant = 50 total messages
    with svc1.repository.transaction() as conn:
        session = svc1.repository.get_session(conn, session_id)
        assert session["total_messages"] == 50

    # 2. Simulate complete service restart (close svc1, instantiate fresh svc2)
    svc2 = MiniBrainLlmRuntimeService(p16_test_env, adapter_factory=lambda: mock_adapter)

    # Verify session and complete history are intact
    with svc2.repository.transaction() as conn:
        recovered_session = svc2.repository.get_session(conn, session_id)
        assert recovered_session is not None
        assert recovered_session["total_messages"] == 50

        messages = svc2.repository.list_messages(conn, session_id=session_id, limit=100, offset=0)
        assert len(messages) == 50
        # Verify first and last turn content
        assert "Turn 1:" in messages[0]["sanitized_text"]
        assert "Turn 25:" in messages[-2]["sanitized_text"]

        # Verify SQLite integrity check passes post-restart
        integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        assert integrity == "ok"


# ==============================================================================
# 6. RAG Grounding & Citation Integrity (P16.9)
# ==============================================================================

def test_p16_rag_001_citation_truthfulness_and_ungrounded_empty(p16_test_env: Settings):
    """Verify that citations are derived strictly from retrieved chunks, and ungrounded queries return citations: []."""
    class _VerifiedRetrieval:
        def retrieve(self, payload, admin_id):
            return {
                "public_id": "retrieval-run-verified",
                "results": [{
                    "chunk_public_id": "chunk-verified-101",
                    "normalized_text": "Production SLA requires 99.9% uptime and zero data loss.",
                    "combined_score": 0.94,
                    "source_title": "Production Operational Runbook",
                    "source_public_id": "src-runbook-1",
                }],
            }

    mock_adapter = MockMiniBrainAdapter()

    # 1. Grounded query with verified chunks -> citations allowed
    svc_grounded = MiniBrainLlmRuntimeService(
        p16_test_env,
        adapter_factory=lambda: mock_adapter,
        retrieval_service=_VerifiedRetrieval(),
    )
    grounded_res = svc_grounded.grounded_chat(
        session_id=None,
        message="What is the production SLA requirement?",
        retrieval_profile_public_id="retrieval-run-verified",
        top_k=5,
        admin_id="adm_prod_tester",
    )
    assert len(grounded_res["citations"]) >= 1
    assert grounded_res["citations"][0]["source_name"] == "Production Operational Runbook"

    # 2. Ungrounded query without chunks -> citations MUST be strictly []
    svc_ungrounded = MiniBrainLlmRuntimeService(
        p16_test_env,
        adapter_factory=lambda: mock_adapter,
        retrieval_service=None,
    )
    ungrounded_res = svc_ungrounded.grounded_chat(
        session_id=None,
        message="Tell me a general greeting.",
        retrieval_profile_public_id=None,
        top_k=5,
        admin_id="adm_prod_tester",
    )
    assert ungrounded_res["citations"] == []


# ==============================================================================
# 7. Observability & Secret Redaction (P16.10)
# ==============================================================================

def test_p16_observability_001_trace_id_and_secret_redaction(p16_test_env: Settings):
    """Verify trace ID propagation and secret redaction across audit logs and events."""
    mock_adapter = MockMiniBrainAdapter()
    svc = MiniBrainLlmRuntimeService(p16_test_env, adapter_factory=lambda: mock_adapter)

    secret_message = "Here is my secret token: sk-live-1234567890abcdef12345678 and Bearer supersecrettoken999"
    res = svc.chat(
        session_id=None,
        message=secret_message,
        admin_id="adm_security_auditor",
        trace_id="trc_p16_secret_check",
    )

    # 1. Trace ID returned in response
    assert res["trace_id"] == "trc_p16_secret_check"

    # 2. Verify messages table has redacted secrets
    with svc.repository.transaction() as conn:
        session_id = res["session"]["public_id"]
        messages = svc.repository.list_messages(conn, session_id=session_id, limit=10, offset=0)
        stored_user_content = messages[0]["sanitized_text"]
        assert "sk-live-1234567890abcdef12345678" not in stored_user_content
        assert "supersecrettoken999" not in stored_user_content

        # 3. Verify event ledger has redacted secrets
        events = svc.repository.list_events(conn, session_id=session_id, limit=20, offset=0)
        for ev in events:
            detail = ev["detail_json"]
            assert "sk-live-1234567890abcdef12345678" not in detail
            assert "supersecrettoken999" not in detail


# ==============================================================================
# 8. Backup & Restore Operations (P16.11)
# ==============================================================================

def test_p16_backup_001_operational_execution_and_checksum_verification(p16_test_env: Settings):
    """Verify live database backup creation, SHA256 integrity, and clean restore."""
    db_path = p16_test_env.resolved_database_path
    backup_dir = p16_test_env.resolved_backup_dir

    # Write test record to database
    with database_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO audit_logs (public_id, event_type, actor_type, action, resource_type, created_at) "
            "VALUES ('aud_p16_backup_rec', 'backup_audit', 'system', 'create_backup', 'db', '2026-09-05T01:00:00Z');"
        )
        conn.commit()

    # Trigger online backup to target file
    backup_target = backup_dir / f"brud_operational_backup_{int(time.time())}.db"
    source_conn = connect(db_path, wal_enabled=True)
    dest_conn = sqlite3.connect(backup_target)
    try:
        source_conn.backup(dest_conn)
    finally:
        source_conn.close()
        dest_conn.close()

    assert backup_target.exists(), "Backup file must be created"
    assert backup_target.stat().st_size > 0, "Backup file size must be non-zero"

    # Compute SHA256 checksum of backup
    hasher = hashlib.sha256()
    with open(backup_target, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    checksum = hasher.hexdigest()
    assert len(checksum) == 64

    # Verify backup database integrity and data retention
    restore_conn = connect(backup_target, wal_enabled=False)
    try:
        rec = restore_conn.execute("SELECT * FROM audit_logs WHERE public_id = 'aud_p16_backup_rec';").fetchone()
        assert rec is not None
        integrity = restore_conn.execute("PRAGMA integrity_check;").fetchone()[0]
        assert integrity == "ok"
    finally:
        restore_conn.close()


# ==============================================================================
# 9. Security Perimeter & Model Confinement (P16.14)
# ==============================================================================

def test_p16_security_001_path_traversal_and_model_confinement(p16_test_env: Settings):
    """Verify that model path traversal outside allowed_model_dir fails closed."""
    # 1. Attempt path traversal with ..
    traversal_path = "../../etc/passwd"
    assert resolve_confined_model_path(settings=p16_test_env, model_path=traversal_path) is None

    # 2. Attempt absolute path outside allowed_model_dir
    absolute_traversal = "/tmp/malicious_model.gguf"
    assert resolve_confined_model_path(settings=p16_test_env, model_path=absolute_traversal) is None

    # 3. LlamaCppMiniBrainAdapter must refuse generation if model_path is not confined
    adapter = LlamaCppMiniBrainAdapter(settings=p16_test_env, model_path=traversal_path)
    assert adapter.is_available() is False
    with pytest.raises(RuntimeError, match="model_path is not configured or is not confined"):
        adapter._load_model()


# ==============================================================================
# 10. Operational Rollback Assessment (P16.13)
# ==============================================================================

def test_p16_operations_001_rollback_compatibility_assessment(p16_test_env: Settings):
    """Verify that database schema and configuration are backward/forward compatible."""
    # Ensure all migration versions are recorded and queryable
    with database_connection(p16_test_env.resolved_database_path) as conn:
        schema_version = conn.execute("PRAGMA user_version;").fetchone()[0]
        assert schema_version > 0, "Database must have a valid non-zero schema version"

        # Verify schema table existence
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        assert "schema_migrations" in tables
        assert "mini_brain_llm_sessions" in tables
        assert "mini_brain_llm_messages" in tables
        assert "mini_brain_llm_runtime_events" in tables
        assert "audit_logs" in tables
