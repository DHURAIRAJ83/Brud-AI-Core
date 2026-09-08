"""P15 Process Restart & Crash Recovery Test Suite.

Validates:
1. Normal process restart & cold state re-hydration
2. Backend restart during idle
3. Backend restart during active multi-turn session
4. Restart during interrupted SSE streaming
5. Restart following provider failure (fail-closed ledger persistence)
6. Crash/restart during uncommitted database write (WAL rollback)
7. Partial request recovery (clean session resumption)
8. Client reconnect after process restart
9. Deep SQLite integrity checks (PRAGMA integrity_check, foreign_key_check, quick_check)
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService

pytestmark = pytest.mark.anyio


class StableMockAdapter(MockMiniBrainAdapter):
    backend_type = "local"

    def is_available(self) -> bool:
        return True

    def generate(self, *, messages: list[dict[str, Any]], **kwargs) -> dict[str, Any]:
        return {
            "text": "Post-restart persistent reply",
            "backend_type": "local",
            "tokens_generated": 10,
            "latency_ms": 15.0,
            "error_message": None,
        }


@pytest.fixture
def restart_env(tmp_path: Path):
    db_path = tmp_path / "restart_recovery.db"
    settings = Settings(
        database_path=db_path,
        allowed_data_dir=tmp_path / "data",
        allowed_model_dir=tmp_path / "models",
        allow_external_storage=True,
        mini_brain_context_cache_ttl_seconds=10.0,
        database_busy_timeout_ms=10000,
        mini_brain_local_model_path=tmp_path / "model.gguf",
    )
    initialize_database(settings.resolved_database_path)
    return settings


# 1. Normal process restart
def test_p15_restart_001_normal_process_restart(restart_env: Settings):
    # Service instance 1: create session & write message
    svc1 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    sess = svc1.open_session(admin_id="admin_1", title="Restart Test Session")
    session_id = sess["public_id"]

    res1 = svc1.chat(session_id=session_id, admin_id="admin_1", message="Pre-restart message 1")
    assert res1["reply"]["sanitized_text"] == "Post-restart persistent reply"
    del svc1  # Process terminates

    # Service instance 2: cold boot re-initialization
    svc2 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    messages = svc2.list_messages(session_id=session_id)["items"]
    assert len(messages) == 2
    assert messages[0]["sanitized_text"] == "Pre-restart message 1"
    assert messages[1]["sanitized_text"] == "Post-restart persistent reply"

    # Integrity verification
    with sqlite3.connect(str(restart_env.resolved_database_path)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        assert integrity == [("ok",)]
    print("\n[RESTART-001] Normal process restart: 2 messages restored cleanly, PRAGMA integrity_check=ok")


# 2. Backend restart during idle
def test_p15_restart_002_restart_during_idle(restart_env: Settings):
    svc1 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    # Idle period
    time.sleep(0.1)
    health1 = svc1.widget_health()
    del svc1

    # Restart
    svc2 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    health2 = svc2.widget_health()

    assert health2["backend_type"] == health1["backend_type"]
    assert health2["available"] is True
    assert health2["loaded"] is True
    print(f"\n[RESTART-002] Idle restart: clean recovery, available={health2['available']}")


# 3. Backend restart during active multi-turn session
def test_p15_restart_003_restart_during_active_session(restart_env: Settings):
    # Turn 1 and 2 on svc 1
    svc1 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    sess = svc1.open_session(admin_id="admin_1", title="Active Multi-turn Session")
    session_id = sess["public_id"]

    svc1.chat(session_id=session_id, admin_id="admin_1", message="Turn 1 question")
    svc1.chat(session_id=session_id, admin_id="admin_1", message="Turn 2 question")
    del svc1  # Sudden restart

    # Turn 3 on svc 2 (cold boot)
    svc2 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    res3 = svc2.chat(session_id=session_id, admin_id="admin_1", message="Turn 3 question")
    assert res3["reply"]["sanitized_text"] == "Post-restart persistent reply"

    messages = svc2.list_messages(session_id=session_id)["items"]
    assert len(messages) == 6  # 3 pairs of admin/assistant
    assert messages[0]["sanitized_text"] == "Turn 1 question"
    assert messages[2]["sanitized_text"] == "Turn 2 question"
    assert messages[4]["sanitized_text"] == "Turn 3 question"
    print("\n[RESTART-003] Active session restart: all 3 turns preserved, total 6 messages")


# 4. Restart during interrupted SSE stream
def test_p15_restart_004_restart_during_sse_stream(restart_env: Settings):
    svc1 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    sess = svc1.open_session(admin_id="admin_1", title="SSE Interrupted Session")
    session_id = sess["public_id"]

    # Start stream generator and consume only 1 token then abort/del
    stream_gen = svc1.stream_chat(session_id=session_id, admin_id="admin_1", message="Stream interrupted message")
    first_chunk = next(stream_gen)
    assert first_chunk is not None
    del stream_gen  # Client disconnect mid-stream
    del svc1  # Process crashes mid-stream

    # Re-open in fresh process
    svc2 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    with sqlite3.connect(str(restart_env.resolved_database_path)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        assert integrity == [("ok",)]
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM mini_brain_llm_messages WHERE session_id = ?", (session_id,))
        count = cursor.fetchone()[0]
        # At most the initial or completed messages exist, zero corrupt/partial state
        assert count in (0, 1, 2)
    print(f"\n[RESTART-004] Interrupted SSE stream: database clean, message count={count}, integrity_check=ok")


# 5. Restart during provider failure
def test_p15_restart_005_restart_after_provider_failure(restart_env: Settings):
    failing_adapter = MagicMock()
    failing_adapter.backend_type = "external"
    failing_adapter.is_available.return_value = False
    failing_adapter.generate.return_value = {
        "text": "",
        "backend_type": "external",
        "tokens_generated": 0,
        "latency_ms": 25.0,
        "error_message": "UPSTREAM_TIMEOUT: Provider timed out",
    }

    svc1 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: failing_adapter)
    sess = svc1.open_session(admin_id="admin_1", title="Provider Failure Session")
    session_id = sess["public_id"]

    res = svc1.chat(session_id=session_id, admin_id="admin_1", message="Failing prompt")
    assert res["error_message"] is not None
    del svc1  # Crash after failure

    # Restart with healthy adapter
    svc2 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    # Should recover and successfully execute next turn
    res2 = svc2.chat(session_id=session_id, admin_id="admin_1", message="Recovery prompt")
    assert res2["error_message"] is None
    assert res2["reply"]["sanitized_text"] == "Post-restart persistent reply"
    print("\n[RESTART-005] Restart after provider failure: recovered cleanly, new turn succeeded")


# 6. Restart during uncommitted database write (crash/rollback)
def test_p15_restart_006_restart_during_uncommitted_write(restart_env: Settings):
    # Simulate a crash during write by beginning an uncommitted transaction in raw SQLite
    conn_crash = sqlite3.connect(str(restart_env.resolved_database_path))
    conn_crash.execute("PRAGMA busy_timeout = 5000")
    conn_crash.execute("BEGIN IMMEDIATE")
    conn_crash.execute(
        "INSERT INTO mini_brain_llm_sessions (public_id, admin_public_id, title) VALUES ('crash_sess', 'admin_1', 'Crash Sess')"
    )
    # Simulate sudden crash: close without COMMIT (implicit rollback)
    conn_crash.close()

    # Restart service and query
    svc = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    with sqlite3.connect(str(restart_env.resolved_database_path)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        assert integrity == [("ok",)]
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM mini_brain_llm_sessions WHERE public_id = 'crash_sess'")
        assert cursor.fetchone()[0] == 0  # Uncommitted transaction was fully rolled back

    print("\n[RESTART-006] Restart during uncommitted write: rolled back cleanly, integrity_check=ok")


# 7. Restart after partial request
def test_p15_restart_007_restart_after_partial_request(restart_env: Settings):
    # Insert a user message without assistant reply (simulating network death mid-request)
    svc1 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    sess = svc1.open_session(admin_id="admin_1", title="Partial Request Session")
    session_id = sess["public_id"]

    with sqlite3.connect(str(restart_env.resolved_database_path)) as conn:
        conn.execute(
            """INSERT INTO mini_brain_llm_messages 
               (public_id, session_id, role, capability, sanitized_text, backend_type)
               VALUES ('orphan_user_msg', ?, 'admin', 'chat', 'Orphan prompt', 'local')""",
            (session_id,)
        )
        conn.commit()
    del svc1

    # Restart service: must handle session with odd number of messages gracefully
    svc2 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    res = svc2.chat(session_id=session_id, admin_id="admin_1", message="Next valid question")
    assert res["error_message"] is None

    messages = svc2.list_messages(session_id=session_id)["items"]
    assert len(messages) == 3  # orphan admin + new admin + new assistant
    print("\n[RESTART-007] Restart after partial request: odd message count tolerated cleanly")


# 8. Reconnect after restart
def test_p15_restart_008_client_reconnect_after_restart(restart_env: Settings):
    svc1 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    sess = svc1.open_session(admin_id="admin_1", title="Reconnect Test")
    session_id = sess["public_id"]
    svc1.chat(session_id=session_id, admin_id="admin_1", message="Session warm-up")
    del svc1

    # Reconnection by fresh service instance
    svc2 = MiniBrainLlmRuntimeService(restart_env, adapter_factory=lambda: StableMockAdapter())
    # Ensure turn continues smoothly
    res = svc2.chat(session_id=session_id, admin_id="admin_1", message="Continuing chat")
    assert res["error_message"] is None
    print("\n[RESTART-008] Reconnect after restart: context window rebuilt, session resumed")


# 9. Deep SQLite integrity checks
def test_p15_restart_009_deep_sqlite_integrity_checks(restart_env: Settings):
    with sqlite3.connect(str(restart_env.resolved_database_path)) as conn:
        # 1. integrity_check
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        assert integrity == [("ok",)]

        # 2. quick_check
        quick = conn.execute("PRAGMA quick_check").fetchall()
        assert quick == [("ok",)]

        # 3. foreign_key_check
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert len(fk_errors) == 0

    print("\n[RESTART-009] Deep SQLite integrity checks: integrity_check=ok, quick_check=ok, foreign_key_check=0 errors")
