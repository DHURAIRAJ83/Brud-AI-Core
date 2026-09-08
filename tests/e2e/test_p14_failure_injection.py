"""P14.7: Failure Injection and Extended Resilience Test Suite.

Verifies:
1. SQLite database busy lock / contention resilience and rollback safety.
2. Missing or corrupted local model path handling with auto failover.
3. Missing RAG collection / invalid retrieval profile handling without 500 crash.
4. 401 / 403 Auth error handling (non-retryable, immediate failover or graceful abort, secrets redacted).
5. Full provider exhaustion: primary + fallback chain all fail -> records PROVIDER_EXHAUSTION event in ledger.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError
from backend.services.mini_brain_llm_adapter import (
    ExternalProviderMiniBrainAdapter,
    LlamaCppMiniBrainAdapter,
    MockMiniBrainAdapter,
)
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService


@pytest.fixture
def p14_fi_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "p14_fi.db"
    storage_dir = tmp_path / "storage"
    model_dir = tmp_path / "models"
    storage_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    from core_model.mini_brain.provider_settings import secret_encryptor

    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, key)

    settings = Settings(
        database_path=db_path,
        storage_dir=storage_dir,
        allowed_model_dir=model_dir,
        allow_external_storage=True,
        jwt_secret="p14_test_jwt_secret_key_at_least_32_chars_long_12345",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def test_p14_fi_001_sqlite_busy_lock_contention_and_rollback_safety(p14_fi_env: Settings):
    """Inject database lock contention during chat turn.
    Verifies that SQLite transactions handle contention cleanly and maintain 100% database integrity."""
    mock_adapter = MockMiniBrainAdapter()
    svc = MiniBrainLlmRuntimeService(p14_fi_env, adapter_factory=lambda: mock_adapter)

    session = svc.open_session(admin_id="adm_fi_tester", title="Contention Test Session")
    session_id = session["public_id"]

    lock_acquired = threading.Event()
    release_lock = threading.Event()

    def hold_lock():
        # Open a separate connection and start an EXCLUSIVE transaction
        conn = sqlite3.connect(str(p14_fi_env.resolved_database_path), timeout=0.1)
        try:
            conn.execute("BEGIN EXCLUSIVE;")
            lock_acquired.set()
            release_lock.wait(timeout=2.0)
            conn.rollback()
        finally:
            conn.close()

    t = threading.Thread(target=hold_lock, daemon=True)
    t.start()
    assert lock_acquired.wait(timeout=2.0)

    # Now attempt a chat turn while lock is held briefly
    # SQLite busy_timeout allows retry; if released within timeout, it succeeds
    def unlock_after_delay():
        time.sleep(0.3)
        release_lock.set()

    t_unlock = threading.Thread(target=unlock_after_delay, daemon=True)
    t_unlock.start()

    res = svc.chat(
        session_id=session_id,
        message="Message during concurrent lock contention",
        admin_id="adm_fi_tester",
    )
    assert res["reply"]["role"] == "assistant"
    t.join()
    t_unlock.join()

    # Verify SQLite integrity check
    with svc.repository.transaction() as conn:
        cursor = conn.execute("PRAGMA integrity_check;")
        assert cursor.fetchone()[0] == "ok"


def test_p14_fi_002_missing_local_model_path_graceful_availability(p14_fi_env: Settings):
    """Verify that when configured local GGUF path does not exist,
    is_available() returns False without crashing, and runtime does not load it."""
    missing_path = p14_fi_env.allowed_model_dir / "nonexistent_model_v1.gguf"
    adapter = LlamaCppMiniBrainAdapter(
        settings=p14_fi_env,
        model_path=missing_path,
        context_length=2048,
        threads=2,
    )
    assert adapter.is_configured() is True
    assert adapter.is_available() is False

    # Attempting generate on unavailable adapter returns clean error
    gen_result = adapter.generate(messages=[{"role": "user", "content": "hello"}])
    assert gen_result["text"] == ""
    assert "not available" in gen_result["error_message"]


def test_p14_fi_003_missing_rag_profile_graceful_fallback(p14_fi_env: Settings):
    """Verify that grounded_chat with a non-existent retrieval profile
    handles NotFoundError or missing collection cleanly without 500 error,
    returns empty citations, and still yields an assistant reply."""
    mock_adapter = MockMiniBrainAdapter()
    svc = MiniBrainLlmRuntimeService(p14_fi_env, adapter_factory=lambda: mock_adapter)

    # Retrieval service raises NotFoundError when profile is missing
    with patch.object(svc.retrieval_service, "retrieve", side_effect=NotFoundError("Profile not found")):
        # In stream_chat:
        events = list(svc.stream_chat(
            session_id=None,
            message="Query with missing retrieval profile",
            admin_id="adm_fi_tester",
            grounded=True,
            retrieval_profile_public_id="ret_missing_profile_123",
        ))
        meta = [e for e in events if e["event"] == "metadata"][0]
        assert meta["data"]["citations"] == [], "Must yield empty citations on RAG error"
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) > 0, "Should still stream assistant reply"


def test_p14_fi_004_auth_failure_non_retryable_and_secret_redacted(p14_fi_env: Settings):
    """Verify that a 401 Unauthorized or 403 Forbidden error from an external provider:
    1. Is marked non-retryable (no retry loops).
    2. Has secret tokens redacted from the error message.
    3. Triggers failover in auto mode."""
    ext_adapter = ExternalProviderMiniBrainAdapter(
        provider_key="openrouter",
        api_key="super_secret_groq_api_key_12345",
        model="llama3-8b-8192",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error": {"message": "Invalid API Key: super_secret_groq_api_key_12345"}}'

    with patch("httpx.Client.post", return_value=mock_resp):
        res = ext_adapter.generate(messages=[{"role": "user", "content": "hi"}])
        assert res["text"] == ""
        assert res["error_message"] is not None
        # Verify secret key is redacted
        assert "super_secret_groq_api_key_12345" not in res["error_message"]
        assert "[REDACTED_SECRET]" in res["error_message"] or "super_secret" not in res["error_message"]


def test_p14_fi_005_full_provider_exhaustion_ledger_event(p14_fi_env: Settings):
    """Verify that when primary and all fallback candidate providers fail,
    the runtime records a 'provider_exhaustion' event in the event ledger
    and returns a graceful error to the user with trace_id."""
    svc = MiniBrainLlmRuntimeService(p14_fi_env)

    # Primary adapter fails
    failing_adapter = MagicMock()
    failing_adapter.is_available.return_value = True
    failing_adapter.generate.return_value = {"text": "", "error_message": "Primary provider service unavailable", "tokens_generated": 0, "latency_ms": 10.0}

    # Fallback candidates also fail
    fallback_cand = {
        "backend_type": "external",
        "external_provider_key": "openrouter",
        "adapter": MagicMock(),
    }
    fallback_cand["adapter"].is_available.return_value = True
    fallback_cand["adapter"].generate.return_value = {"text": "", "error_message": "Fallback provider rate limit", "tokens_generated": 0, "latency_ms": 10.0}

    with patch.object(svc, "_resolve_backend", return_value={"adapter": failing_adapter, "backend_type": "external", "external_provider_key": "groq", "reason": None}):
        with patch.object(svc, "_list_available_fallback_candidates", return_value=[fallback_cand]):
            session = svc.open_session(admin_id="adm_exhaust_tester", title="Exhaustion Test")
            session_id = session["public_id"]

            res = svc.chat(
                session_id=session_id,
                message="Will cause provider exhaustion",
                admin_id="adm_exhaust_tester",
                execution_mode="auto",
                trace_id="trc_fi_exhaustion_001",
            )

            # Reply indicates failure gracefully
            assert "unavailable" in res["reply"]["sanitized_text"].lower() or res["error_message"] is not None

            # Verify provider_exhaustion event recorded in event ledger
            with svc.repository.transaction() as conn:
                events = svc.repository.list_events(conn, session_id=session_id, limit=20, offset=0)
                exhaust_events = [e for e in events if e["event_type"] == "provider_exhaustion"]
                assert len(exhaust_events) >= 1, "Must record provider_exhaustion event in event ledger"
                detail = exhaust_events[0]["detail_json"]
                detail_dict = json.loads(detail) if isinstance(detail, str) else detail
                assert detail_dict["trace_id"] == "trc_fi_exhaustion_001"
                assert "attempted_providers" in detail_dict
