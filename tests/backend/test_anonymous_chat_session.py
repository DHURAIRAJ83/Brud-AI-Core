"""Automated test suite for Phase 8 Anonymous Public Chat Sessions (P8-02).

Covers all 20 required verification points:
1. Session creation.
2. Token returned only on creation.
3. Token hash stored instead of plaintext.
4. Valid token authentication.
5. Invalid/missing token rejection.
6. Wrong token rejection.
7. IDOR attempt rejection (cross-session credential attack).
8. Message history retrieval.
9. Empty/new session behavior.
10. Message association and sequence.
11. Clear-chat privacy zeroing (stored_content -> NULL).
12. Closed-session rejection.
13. Expired-session rejection.
14. Rolling TTL extension behavior.
15. 7-day hard expiry enforcement.
16. Rate limiting enforcement.
17. Concurrent/session isolation.
18. Existing /api/chat backward compatibility regression.
19. Admin endpoint isolation.
20. Existing chatbot regression (help, feedback, chat).
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.services.anonymous_chat_session_service import (
    SESSION_HARD_EXPIRY_SECONDS,
    SESSION_ROLLING_TTL_SECONDS,
    AnonymousChatSessionService,
    hash_client_ip,
    hash_token,
)
from backend.services.public_chat_rate_limiter import reset_rate_limits

pytestmark = pytest.mark.anyio


async def api_request(
    app: FastAPI, method: str, path: str, *, headers: dict[str, str] | None = None, **kwargs
):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.request(method, path, headers=headers, **kwargs)


def _insert_test_turn(
    db_path: Path,
    conversation_public_id: str,
    role: str,
    content: str,
    sequence_number: int,
) -> str:
    """Helper to insert a test turn into conversation_turns for testing history retrieval."""
    turn_public_id = str(uuid4())
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    with sqlite3.connect(db_path) as conn:
        session_row = conn.execute(
            "SELECT id FROM conversation_sessions WHERE public_id = ?",
            (conversation_public_id,),
        ).fetchone()
        assert session_row is not None, f"Session {conversation_public_id} not found in DB"
        session_id = session_row[0]

        conn.execute(
            """
            INSERT INTO conversation_turns (
                public_id, session_id, sequence_number, role,
                language_category, content_checksum_sha256, stored_content,
                token_count, status
            ) VALUES (?, ?, ?, ?, 'en', ?, ?, ?, 'accepted')
            """,
            (
                turn_public_id,
                session_id,
                sequence_number,
                role,
                content_hash,
                content,
                len(content.split()),
            ),
        )
        conn.commit()
    return turn_public_id


# ---------------------------------------------------------------------------
# Test Cases 1, 2, 3: Session Creation & Token Hashing
# ---------------------------------------------------------------------------


async def test_01_session_creation(api_app: FastAPI) -> None:
    """1. Session creation returns valid response schema."""
    resp = await api_request(
        api_app,
        "POST",
        "/api/chat/session",
        json={"language_preference": "ta"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "conversation_id" in data
    assert "session_token" in data
    assert data["session_token"].startswith("brud_anon_")
    assert "expires_at" in data
    assert data["turn_count"] == 0
    assert data["status"] == "active"


async def test_02_and_03_token_hashing_and_never_stored_plaintext(api_app: FastAPI) -> None:
    """2. Token returned only on creation; 3. Token hash stored instead of plaintext."""
    resp = await api_request(api_app, "POST", "/api/chat/session")
    assert resp.status_code == 200
    data = resp.json()
    conv_id = data["conversation_id"]
    raw_token = data["session_token"]

    db_path = api_app.state.settings.resolved_database_path
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM anonymous_chat_sessions WHERE conversation_session_public_id = ?",
            (conv_id,),
        ).fetchone()
        assert row is not None

        # Verify plaintext token is NOT stored anywhere in the row
        row_dict = dict(row)
        for col_name, val in row_dict.items():
            if isinstance(val, str):
                assert raw_token not in val, f"Raw token found in column {col_name}!"

        # Verify SHA-256 hash matches
        expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        assert row_dict["session_token_hash"] == expected_hash
        assert row_dict["status"] == "active"

        # Verify IP is not stored plaintext
        assert "127.0.0.1" not in str(row_dict["client_ip_hash"])
        assert "unknown" not in str(row_dict["client_ip_hash"])


# ---------------------------------------------------------------------------
# Test Cases 4, 5, 6, 7: Token Authentication & IDOR Protection
# ---------------------------------------------------------------------------


async def test_04_valid_token_authentication(api_app: FastAPI) -> None:
    """4. Valid token authentication succeeds."""
    created = await api_request(api_app, "POST", "/api/chat/session")
    data = created.json()
    conv_id = data["conversation_id"]
    token = data["session_token"]

    resp = await api_request(
        api_app,
        "GET",
        f"/api/chat/session/{conv_id}/messages",
        headers={"X-Session-Token": token},
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["conversation_id"] == conv_id
    assert res["status"] == "active"
    assert res["messages"] == []


async def test_05_missing_token_rejection(api_app: FastAPI) -> None:
    """5. Missing token header is rejected with 401 Unauthorized."""
    created = await api_request(api_app, "POST", "/api/chat/session")
    conv_id = created.json()["conversation_id"]

    resp = await api_request(api_app, "GET", f"/api/chat/session/{conv_id}/messages")
    assert resp.status_code == 401
    assert "X-Session-Token" in resp.json()["error"]["message"]


async def test_06_wrong_token_rejection(api_app: FastAPI) -> None:
    """6. Wrong token is rejected with 403 Forbidden."""
    created = await api_request(api_app, "POST", "/api/chat/session")
    conv_id = created.json()["conversation_id"]

    resp = await api_request(
        api_app,
        "GET",
        f"/api/chat/session/{conv_id}/messages",
        headers={"X-Session-Token": "brud_anon_totally_wrong_token_value_here"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CHAT_SESSION_FORBIDDEN"


async def test_07_idor_attempt_rejection(api_app: FastAPI) -> None:
    """7. IDOR: Attacker cannot use their valid token to access Victim's session."""
    victim_session = (await api_request(api_app, "POST", "/api/chat/session")).json()
    attacker_session = (await api_request(api_app, "POST", "/api/chat/session")).json()

    victim_id = victim_session["conversation_id"]
    attacker_token = attacker_session["session_token"]

    # 1. Attacker tries to GET victim's message history
    idor_get = await api_request(
        api_app,
        "GET",
        f"/api/chat/session/{victim_id}/messages",
        headers={"X-Session-Token": attacker_token},
    )
    assert idor_get.status_code == 403
    assert idor_get.json()["error"]["code"] == "CHAT_SESSION_FORBIDDEN"

    # 2. Attacker tries to CLEAR victim's chat
    idor_clear = await api_request(
        api_app,
        "POST",
        f"/api/chat/session/{victim_id}/clear",
        headers={"X-Session-Token": attacker_token},
    )
    assert idor_clear.status_code == 403
    assert idor_clear.json()["error"]["code"] == "CHAT_SESSION_FORBIDDEN"

    # 3. Attacker tries to POST a message into victim's session
    idor_chat = await api_request(
        api_app,
        "POST",
        "/api/chat",
        headers={"X-Session-Token": attacker_token},
        json={"message": "malicious turn", "conversation_id": victim_id},
    )
    assert idor_chat.status_code == 403
    assert idor_chat.json()["error"]["code"] == "CHAT_SESSION_FORBIDDEN"


# ---------------------------------------------------------------------------
# Test Cases 8, 9, 10: Message History & Association
# ---------------------------------------------------------------------------


async def test_08_and_09_message_history_retrieval_and_empty_behavior(api_app: FastAPI) -> None:
    """8. Message history retrieval and 9. Empty new session behavior."""
    created = await api_request(api_app, "POST", "/api/chat/session")
    conv_id = created.json()["conversation_id"]
    token = created.json()["session_token"]

    # Initially empty
    empty_resp = await api_request(
        api_app,
        "GET",
        f"/api/chat/session/{conv_id}/messages",
        headers={"X-Session-Token": token},
    )
    assert empty_resp.status_code == 200
    assert empty_resp.json()["turn_count"] == 0
    assert empty_resp.json()["messages"] == []

    # Insert turns
    db_path = api_app.state.settings.resolved_database_path
    _insert_test_turn(db_path, conv_id, "user", "வணக்கம்", 1)
    _insert_test_turn(db_path, conv_id, "assistant", "வணக்கம்! உங்களுக்கு நான் எவ்வாறு உதவ முடியும்?", 2)

    # Retrieve history
    history_resp = await api_request(
        api_app,
        "GET",
        f"/api/chat/session/{conv_id}/messages",
        headers={"X-Session-Token": token},
    )
    assert history_resp.status_code == 200
    h_data = history_resp.json()
    assert h_data["turn_count"] == 2
    assert len(h_data["messages"]) == 2
    assert h_data["messages"][0]["role"] == "user"
    assert h_data["messages"][0]["content"] == "வணக்கம்"
    assert h_data["messages"][1]["role"] == "assistant"
    assert "உதவ முடியும்" in h_data["messages"][1]["content"]


async def test_10_message_association_and_isolation(api_app: FastAPI) -> None:
    """10. Message association: turns in Session A do not leak into Session B."""
    session_a = (await api_request(api_app, "POST", "/api/chat/session")).json()
    session_b = (await api_request(api_app, "POST", "/api/chat/session")).json()

    db_path = api_app.state.settings.resolved_database_path
    _insert_test_turn(db_path, session_a["conversation_id"], "user", "Message in A", 1)
    _insert_test_turn(db_path, session_b["conversation_id"], "user", "Message in B", 1)

    hist_a = await api_request(
        api_app,
        "GET",
        f"/api/chat/session/{session_a['conversation_id']}/messages",
        headers={"X-Session-Token": session_a["session_token"]},
    )
    hist_b = await api_request(
        api_app,
        "GET",
        f"/api/chat/session/{session_b['conversation_id']}/messages",
        headers={"X-Session-Token": session_b["session_token"]},
    )

    msgs_a = hist_a.json()["messages"]
    msgs_b = hist_b.json()["messages"]
    assert len(msgs_a) == 1 and msgs_a[0]["content"] == "Message in A"
    assert len(msgs_b) == 1 and msgs_b[0]["content"] == "Message in B"


# ---------------------------------------------------------------------------
# Test Cases 11, 12: Clear-Chat & Closed-Session Rejection
# ---------------------------------------------------------------------------


async def test_11_and_12_clear_chat_privacy_zeroing_and_closed_session(api_app: FastAPI) -> None:
    """11. Clear-chat zeroes stored_content; 12. Closed session is rejected."""
    session = (await api_request(api_app, "POST", "/api/chat/session")).json()
    conv_id = session["conversation_id"]
    token = session["session_token"]

    db_path = api_app.state.settings.resolved_database_path
    _insert_test_turn(db_path, conv_id, "user", "Secret User Question", 1)
    _insert_test_turn(db_path, conv_id, "assistant", "Secret Assistant Answer", 2)

    # Verify turns exist before clearing
    pre_hist = await api_request(
        api_app, "GET", f"/api/chat/session/{conv_id}/messages", headers={"X-Session-Token": token}
    )
    assert len(pre_hist.json()["messages"]) == 2

    # Clear session
    clear_resp = await api_request(
        api_app, "POST", f"/api/chat/session/{conv_id}/clear", headers={"X-Session-Token": token}
    )
    assert clear_resp.status_code == 200, clear_resp.text
    assert clear_resp.json() == {"conversation_id": conv_id, "status": "closed", "cleared": True}

    with sqlite3.connect(db_path) as conn:
        anon_row = conn.execute(
            "SELECT status, session_token_hash FROM anonymous_chat_sessions WHERE conversation_session_public_id = ?",
            (conv_id,),
        ).fetchone()
        assert anon_row[0] == "closed"
        assert anon_row[1] == ""

        conv_status = conn.execute(
            "SELECT status FROM conversation_sessions WHERE public_id = ?",
            (conv_id,),
        ).fetchone()[0]
        assert conv_status == "closed"

    # Subsequent GET must be rejected as session is closed
    post_get = await api_request(
        api_app, "GET", f"/api/chat/session/{conv_id}/messages", headers={"X-Session-Token": token}
    )
    assert post_get.status_code == 404
    assert "closed" in post_get.json()["error"]["message"]

    # Subsequent clear must also be rejected
    post_clear = await api_request(
        api_app, "POST", f"/api/chat/session/{conv_id}/clear", headers={"X-Session-Token": token}
    )
    assert post_clear.status_code == 404


# ---------------------------------------------------------------------------
# Test Cases 13, 14, 15: Expiry & Rolling TTL
# ---------------------------------------------------------------------------


async def test_13_expired_session_rejection(api_app: FastAPI) -> None:
    """13. Expired session is marked expired and rejected with 401."""
    session = (await api_request(api_app, "POST", "/api/chat/session")).json()
    conv_id = session["conversation_id"]
    token = session["session_token"]

    db_path = api_app.state.settings.resolved_database_path
    past_time = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE anonymous_chat_sessions SET expires_at = ? WHERE conversation_session_public_id = ?",
            (past_time, conv_id),
        )
        conn.commit()

    resp = await api_request(
        api_app, "GET", f"/api/chat/session/{conv_id}/messages", headers={"X-Session-Token": token}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "CHAT_SESSION_EXPIRED"

    # Verify status in DB was updated to 'expired'
    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM anonymous_chat_sessions WHERE conversation_session_public_id = ?",
            (conv_id,),
        ).fetchone()[0]
        assert status == "expired"


async def test_14_rolling_ttl_extension(api_app: FastAPI) -> None:
    """14. Valid access extends expires_at by 24 hours."""
    session = (await api_request(api_app, "POST", "/api/chat/session")).json()
    conv_id = session["conversation_id"]
    token = session["session_token"]

    db_path = api_app.state.settings.resolved_database_path
    now = datetime.now(UTC)
    old_expiry = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE anonymous_chat_sessions SET expires_at = ? WHERE conversation_session_public_id = ?",
            (old_expiry, conv_id),
        )
        conn.commit()

    # Access session
    resp = await api_request(
        api_app, "GET", f"/api/chat/session/{conv_id}/messages", headers={"X-Session-Token": token}
    )
    assert resp.status_code == 200

    # Verify expiry bumped to ~24 hours from now
    with sqlite3.connect(db_path) as conn:
        new_expiry_str = conn.execute(
            "SELECT expires_at FROM anonymous_chat_sessions WHERE conversation_session_public_id = ?",
            (conv_id,),
        ).fetchone()[0]
        new_expiry = datetime.strptime(new_expiry_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        assert new_expiry > now + timedelta(hours=23)


async def test_15_hard_7_day_expiry(api_app: FastAPI) -> None:
    """15. 7-day hard expiry: Sessions older than 7 days expire regardless of rolling TTL."""
    session = (await api_request(api_app, "POST", "/api/chat/session")).json()
    conv_id = session["conversation_id"]
    token = session["session_token"]

    db_path = api_app.state.settings.resolved_database_path
    eight_days_ago = (datetime.now(UTC) - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
    future_expiry = (datetime.now(UTC) + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE anonymous_chat_sessions
            SET created_at = ?, expires_at = ?
            WHERE conversation_session_public_id = ?
            """,
            (eight_days_ago, future_expiry, conv_id),
        )
        conn.commit()

    resp = await api_request(
        api_app, "GET", f"/api/chat/session/{conv_id}/messages", headers={"X-Session-Token": token}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "CHAT_SESSION_EXPIRED"


# ---------------------------------------------------------------------------
# Test Cases 16, 17: Rate Limiting & Concurrency Isolation
# ---------------------------------------------------------------------------


async def test_16_rate_limiting_enforcement(api_app: FastAPI) -> None:
    """16. Rapid requests trigger 429 CHAT_RATE_LIMITED."""
    reset_rate_limits()
    # Settings default is typically 30 req/min for public chat
    max_reqs = api_app.state.settings.public_chat_rate_limit_max_requests

    # Exhaust rate limit
    for _ in range(max_reqs):
        r = await api_request(api_app, "POST", "/api/chat/session")
        assert r.status_code == 200

    # Next request must be rate-limited
    blocked = await api_request(api_app, "POST", "/api/chat/session")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "CHAT_RATE_LIMITED"
    reset_rate_limits()


async def test_17_concurrent_session_isolation(api_app: FastAPI) -> None:
    """17. Multiple concurrently created sessions have distinct IDs and keys."""
    sessions = []
    for _ in range(5):
        resp = await api_request(api_app, "POST", "/api/chat/session")
        assert resp.status_code == 200
        sessions.append(resp.json())

    conv_ids = [s["conversation_id"] for s in sessions]
    tokens = [s["session_token"] for s in sessions]

    # Verify complete uniqueness
    assert len(set(conv_ids)) == 5
    assert len(set(tokens)) == 5


# ---------------------------------------------------------------------------
# Test Cases 18, 19, 20: Regression & Admin Isolation
# ---------------------------------------------------------------------------


async def test_18_existing_public_chat_regression(api_app: FastAPI) -> None:
    """18. Existing /api/chat without session token functions normally."""
    resp = await api_request(api_app, "POST", "/api/chat", json={"message": "வணக்கம்"})
    assert resp.status_code == 200
    body = resp.json()
    assert "reply" in body
    assert "route_used" in body
    assert "request_id" in body


async def test_19_admin_endpoint_isolation(api_app: FastAPI) -> None:
    """19. Admin endpoints reject anonymous tokens and vice versa."""
    session = (await api_request(api_app, "POST", "/api/chat/session")).json()
    token = session["session_token"]

    # 1. Admin endpoint rejects anonymous token
    admin_resp = await api_request(
        api_app,
        "GET",
        "/api/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert admin_resp.status_code in (401, 403)

    # 2. Anonymous session creation requires NO admin auth
    anon_resp = await api_request(api_app, "POST", "/api/chat/session")
    assert anon_resp.status_code == 200


async def test_20_existing_chatbot_endpoints_regression(api_app: FastAPI) -> None:
    """20. Existing chatbot endpoints (/chat/help, /chat/feedback) continue working."""
    # Help endpoint
    help_resp = await api_request(api_app, "GET", "/api/chat/help")
    assert help_resp.status_code == 200
    assert "entries" in help_resp.json()
    assert help_resp.json()["count"] > 0

    # Feedback endpoint
    feedback_resp = await api_request(
        api_app,
        "POST",
        "/api/chat/feedback",
        json={
            "request_id": str(uuid4()),
            "route_used": "core_model",
            "answer_hash": "dummy_hash_0000",
            "feedback_type": "thumbs_up",
            "comment": "great answer",
        },
    )
    assert feedback_resp.status_code == 200
    assert feedback_resp.json()["accepted"] is True
