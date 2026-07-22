from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.connection import database_connection
from backend.database.repositories.admin import AdminRepository, AuthenticationError
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio
PASSWORD = "Correct-Horse-Battery-42"


def repository(app: FastAPI) -> AdminRepository:
    return AdminRepository(app.state.settings.resolved_database_path)


def create_admin(app: FastAPI, username: str = "admin"):
    return repository(app).create_admin(
        AdminCreate(username=username, display_name="Administrator", password=PASSWORD)
    )


async def test_password_hash_login_me_csrf_logout(api_app: FastAPI) -> None:
    create_admin(api_app)
    path = api_app.state.settings.resolved_database_path
    with database_connection(path) as connection:
        stored = connection.execute("SELECT password_hash FROM admin_accounts").fetchone()[0]
    assert PASSWORD not in stored and stored.startswith("$argon2")
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        assert (await client.get("/api/admin/overview")).status_code == 401
        invalid = await client.post(
            "/api/admin/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert invalid.status_code == 401
        assert invalid.json()["detail"] == "Invalid username or password"
        login = await client.post(
            "/api/admin/auth/login", json={"username": "ADMIN", "password": PASSWORD}
        )
        assert login.status_code == 200
        assert "token" not in login.text.lower() and "password" not in login.text.lower()
        me = await client.get("/api/admin/auth/me")
        assert me.status_code == 200 and me.json()["admin"]["username"] == "admin"
        csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
        assert (await client.post("/api/admin/auth/logout")).status_code == 403
        assert (
            await client.post("/api/admin/auth/logout", headers={"X-CSRF-Token": csrf})
        ).status_code == 200
        assert (await client.get("/api/admin/auth/me")).status_code == 401
    with database_connection(path) as connection:
        token_hash = connection.execute("SELECT token_hash FROM admin_sessions").fetchone()[0]
        assert token_hash and token_hash not in login.text


def test_lockout_and_disabled_admin(api_app: FastAPI) -> None:
    create_admin(api_app)
    repo = repository(api_app)
    for _ in range(api_app.state.settings.admin_max_failed_logins):
        with pytest.raises(AuthenticationError):
            repo.authenticate("admin", "wrong", max_failures=5, lockout_minutes=15)
    with pytest.raises(AuthenticationError):
        repo.authenticate("admin", PASSWORD, max_failures=5, lockout_minutes=15)
    repo.set_status("admin", "active")
    repo.set_status("admin", "disabled")
    with pytest.raises(AuthenticationError):
        repo.authenticate("admin", PASSWORD, max_failures=5, lockout_minutes=15)


def test_expired_and_revoked_sessions_rejected(api_app: FastAPI) -> None:
    admin = create_admin(api_app)
    repo = repository(api_app)
    token, _, _ = repo.create_session(admin.public_id, 60)
    path = api_app.state.settings.resolved_database_path
    with database_connection(path) as connection:
        connection.execute(
            "UPDATE admin_sessions SET expires_at=?",
            ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(),),
        )
        connection.commit()
    with pytest.raises(AuthenticationError):
        repo.validate_session(token)
    token, _, _ = repo.create_session(admin.public_id, 60)
    repo.logout(token)
    with pytest.raises(AuthenticationError):
        repo.validate_session(token)


def test_reset_password_revokes_sessions(api_app: FastAPI) -> None:
    admin = create_admin(api_app)
    repo = repository(api_app)
    token, _, _ = repo.create_session(admin.public_id, 60)
    repo.reset_password("admin", "Another-Strong-Password-77")
    with pytest.raises(AuthenticationError):
        repo.validate_session(token)
