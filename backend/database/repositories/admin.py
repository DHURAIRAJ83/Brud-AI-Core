"""Admin account and server-managed session repository."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pwdlib import PasswordHash

from backend.core.json_utils import dumps_json
from backend.database.repositories.base import (
    BaseRepository,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from backend.models.auth import AdminCreate, AdminListItem, AdminPublic, SessionPublic


class AuthenticationError(ValidationError):
    """Generic authentication rejection without enumeration details."""


class AuthorizationError(ValidationError):
    """Authenticated principal cannot access the requested resource."""


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _audit(connection, event: str, outcome: str, actor: str | None = None, **metadata) -> None:
    connection.execute(
        """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
        actor_reference,outcome,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            event,
            "admin" if actor else "anonymous",
            "{}",
            str(uuid4()),
            event,
            "admin" if actor else "anonymous",
            actor,
            outcome,
            dumps_json(metadata),
        ),
    )


class AdminRepository(BaseRepository):
    def __init__(self, database_path: Path) -> None:
        super().__init__(database_path)
        self.password_hash = PasswordHash.recommended()
        self._dummy_hash = self.password_hash.hash("Brud-Dummy-Password-Only")

    @staticmethod
    def normalize_username(username: str) -> str:
        return username.strip().lower()

    def create_admin(self, item: AdminCreate) -> AdminPublic:
        username = self.normalize_username(item.username)
        password_hash = self.password_hash.hash(item.password)
        public_id = str(uuid4())
        with self.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM admin_accounts WHERE username=?", (username,)
            ).fetchone():
                raise ConflictError("admin username already exists")
            connection.execute(
                """INSERT INTO admin_accounts(public_id,username,display_name,password_hash)
                VALUES (?,?,?,?)""",
                (public_id, username, item.display_name.strip(), password_hash),
            )
            _audit(connection, "admin_account_created", "success", public_id)
        return AdminPublic(public_id=public_id, username=username, display_name=item.display_name)

    def list_admins(self) -> list[AdminListItem]:
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT public_id,username,display_name,status "
                "FROM admin_accounts ORDER BY username"
            ).fetchall()
        return [AdminListItem.model_validate(dict(row)) for row in rows]

    def set_status(self, username: str, status: str) -> None:
        if status not in {"active", "disabled"}:
            raise ValidationError("invalid admin status")
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id,public_id FROM admin_accounts WHERE username=?",
                (self.normalize_username(username),),
            ).fetchone()
            if not row:
                raise NotFoundError("admin not found")
            connection.execute(
                "UPDATE admin_accounts SET status=?,updated_at=? WHERE id=?",
                (status, _now().isoformat(), row["id"]),
            )
            if status == "disabled":
                connection.execute(
                    "UPDATE admin_sessions SET revoked_at=? "
                    "WHERE admin_account_id=? AND revoked_at IS NULL",
                    (_now().isoformat(), row["id"]),
                )
            _audit(connection, f"admin_account_{status}", "success", row["public_id"])

    def reset_password(self, username: str, password: str) -> None:
        validated = AdminCreate(username=username, display_name="reset", password=password)
        password_hash = self.password_hash.hash(validated.password)
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id,public_id FROM admin_accounts WHERE username=?",
                (self.normalize_username(username),),
            ).fetchone()
            if not row:
                raise NotFoundError("admin not found")
            connection.execute(
                """UPDATE admin_accounts SET password_hash=?,failed_login_count=0,
                locked_until=NULL,status='active',updated_at=? WHERE id=?""",
                (password_hash, _now().isoformat(), row["id"]),
            )
            connection.execute(
                "UPDATE admin_sessions SET revoked_at=? "
                "WHERE admin_account_id=? AND revoked_at IS NULL",
                (_now().isoformat(), row["id"]),
            )
            _audit(connection, "admin_password_reset", "success", row["public_id"])

    def authenticate(
        self, username: str, password: str, *, max_failures: int, lockout_minutes: int
    ) -> AdminPublic:
        normalized = self.normalize_username(username)
        authenticated: AdminPublic | None = None
        rejected = False
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM admin_accounts WHERE username=?", (normalized,)
            ).fetchone()
            valid = self.password_hash.verify(
                password, row["password_hash"] if row else self._dummy_hash
            )
            now = _now()
            if not row:
                _audit(connection, "admin_login_failure", "failure", username_supplied=True)
                rejected = True
            locked_until = (
                datetime.fromisoformat(row["locked_until"]) if row and row["locked_until"] else None
            )
            unavailable = bool(
                row and (row["status"] == "disabled" or (locked_until and locked_until > now))
            )
            if row and (not valid or unavailable):
                failures = row["failed_login_count"] + 1
                lock_until = None
                status = row["status"]
                if failures >= max_failures and status != "disabled":
                    status = "locked"
                    lock_until = now + timedelta(minutes=lockout_minutes)
                connection.execute(
                    """UPDATE admin_accounts SET failed_login_count=?,status=?,locked_until=?,
                    updated_at=? WHERE id=?""",
                    (
                        failures,
                        status,
                        lock_until.isoformat() if lock_until else row["locked_until"],
                        now.isoformat(),
                        row["id"],
                    ),
                )
                _audit(
                    connection,
                    "admin_login_lockout" if lock_until else "admin_login_failure",
                    "failure",
                    row["public_id"],
                )
                rejected = True
            elif row:
                connection.execute(
                    """UPDATE admin_accounts SET failed_login_count=0,locked_until=NULL,
                    status='active',last_login_at=?,updated_at=? WHERE id=?""",
                    (now.isoformat(), now.isoformat(), row["id"]),
                )
                _audit(connection, "admin_login_success", "success", row["public_id"])
                authenticated = AdminPublic(
                    public_id=row["public_id"],
                    username=row["username"],
                    display_name=row["display_name"],
                )
        if rejected or authenticated is None:
            raise AuthenticationError("invalid credentials")
        return authenticated

    def create_session(
        self, admin_public_id: str, ttl_minutes: int
    ) -> tuple[str, str, SessionPublic]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = _now()
        expires = now + timedelta(minutes=ttl_minutes)
        with self.transaction() as connection:
            account = connection.execute(
                "SELECT id FROM admin_accounts WHERE public_id=?", (admin_public_id,)
            ).fetchone()
            if not account:
                raise NotFoundError("admin not found")
            connection.execute(
                """INSERT INTO admin_sessions(public_id,admin_account_id,token_hash,csrf_hash,
                expires_at,last_used_at) VALUES (?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    account[0],
                    _hash_token(token),
                    _hash_token(csrf),
                    expires.isoformat(),
                    now.isoformat(),
                ),
            )
        return token, csrf, SessionPublic(expires_at=expires, last_used_at=now)

    def validate_session(self, token: str) -> tuple[AdminPublic, SessionPublic, int]:
        token_hash = _hash_token(token)
        rejection: type[ValidationError] | None = None
        result: tuple[AdminPublic, SessionPublic, int] | None = None
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT s.*,a.public_id AS admin_public_id,a.username,a.display_name,a.status
                FROM admin_sessions s JOIN admin_accounts a ON a.id=s.admin_account_id
                WHERE s.token_hash=?""",
                (token_hash,),
            ).fetchone()
            now = _now()
            if not row or row["revoked_at"] or datetime.fromisoformat(row["expires_at"]) <= now:
                if row:
                    _audit(connection, "admin_session_rejected", "denied", row["admin_public_id"])
                rejection = AuthenticationError
            elif row["status"] != "active":
                _audit(connection, "admin_session_rejected", "denied", row["admin_public_id"])
                rejection = AuthorizationError
            else:
                connection.execute(
                    "UPDATE admin_sessions SET last_used_at=? WHERE id=?",
                    (now.isoformat(), row["id"]),
                )
                result = (
                    AdminPublic(
                        public_id=row["admin_public_id"],
                        username=row["username"],
                        display_name=row["display_name"],
                    ),
                    SessionPublic(expires_at=row["expires_at"], last_used_at=now),
                    row["id"],
                )
        if rejection:
            raise rejection(
                "authentication required"
                if rejection is AuthenticationError
                else "admin account unavailable"
            )
        if result is None:
            raise AuthenticationError("authentication required")
        return result

    def validate_csrf(self, session_id: int, token: str) -> bool:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT csrf_hash FROM admin_sessions WHERE id=?", (session_id,)
            ).fetchone()
        return bool(row and hmac.compare_digest(row[0], _hash_token(token)))

    def logout(self, token: str) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT s.id,a.public_id FROM admin_sessions s JOIN admin_accounts a
                ON a.id=s.admin_account_id WHERE s.token_hash=?""",
                (_hash_token(token),),
            ).fetchone()
            if row:
                connection.execute(
                    "UPDATE admin_sessions SET revoked_at=? WHERE id=?",
                    (_now().isoformat(), row["id"]),
                )
                _audit(connection, "admin_logout", "success", row["public_id"])
