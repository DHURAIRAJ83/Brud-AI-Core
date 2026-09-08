"""Service for Anonymous Public Chat Sessions (Phase 8).

Handles 256-bit cryptographically secure token generation, constant-time
validation, rolling 24-hour TTL, 7-day hard expiry, IDOR prevention,
conversation turn history extraction, and privacy zeroing on clear-chat.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.core.validation import validate_public_id
from backend.database.repositories.anonymous_chat_session import AnonymousChatSessionRepository
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.models.conversation_memory import SessionCreate
from backend.services.conversation_session_service import ConversationSessionService
from backend.services.public_chat_routing_service import PublicChatRoutingService

# Rolling TTL: 24 hours from last activity
SESSION_ROLLING_TTL_SECONDS = 86_400
# Hard expiry: 7 days from creation
SESSION_HARD_EXPIRY_SECONDS = 604_800
# Actor string for audit logging
_ANON_ACTOR = "anonymous_public_user"


class ChatSessionError(BrudError):
    status_code = 400
    code = "CHAT_SESSION_ERROR"


class ChatSessionUnauthorizedError(BrudError):
    status_code = 401
    code = "CHAT_SESSION_UNAUTHORIZED"

    def __init__(self, message: str = "Valid X-Session-Token required.") -> None:
        super().__init__(message)


class ChatSessionForbiddenError(BrudError):
    status_code = 403
    code = "CHAT_SESSION_FORBIDDEN"

    def __init__(self, message: str = "Access to this conversation session is denied.") -> None:
        super().__init__(message)


class ChatSessionNotFoundError(BrudError):
    status_code = 404
    code = "CHAT_SESSION_NOT_FOUND"

    def __init__(self, message: str = "Conversation session not found or closed.") -> None:
        super().__init__(message)


class ChatSessionExpiredError(BrudError):
    status_code = 401
    code = "CHAT_SESSION_EXPIRED"

    def __init__(self, message: str = "Conversation session has expired.") -> None:
        super().__init__(message)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _to_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _from_iso(iso_str: str) -> datetime:
    clean = iso_str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(clean, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    # Fallback to fromisoformat
    try:
        parsed = datetime.fromisoformat(clean)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except Exception:
        return _now_utc()


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def hash_client_ip(client_ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{client_ip}".encode("utf-8")).hexdigest()


class AnonymousChatSessionService:
    def __init__(
        self,
        settings: Settings,
        *,
        repository: AnonymousChatSessionRepository | None = None,
        session_service: ConversationSessionService | None = None,
        chat_router: PublicChatRoutingService | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or AnonymousChatSessionRepository(settings.resolved_database_path)
        self.conv_repository = ConversationMemoryRepository(settings.resolved_database_path)
        self.session_service = session_service or ConversationSessionService(
            self.conv_repository, settings
        )
        self.chat_router = chat_router or PublicChatRoutingService(settings)
        self._ip_salt = getattr(settings, "mini_brain_public_chat_runtime_hash_salt", "brud_anon_ip_salt")

    def _resolve_active_memory_policy_public_id(self) -> str:
        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT public_id FROM conversation_memory_policies WHERE lifecycle_status='active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                return row["public_id"]
        # Fallback to default policy
        return "00000000-0000-4000-8000-000000000001"

    def create_session(
        self,
        *,
        client_ip: str,
        language_preference: str = "auto",
    ) -> dict[str, Any]:
        """Creates a new anonymous conversation session and returns the one-time raw token."""
        raw_token = f"brud_anon_{secrets.token_urlsafe(32)}"
        token_hash = hash_token(raw_token)
        ip_hash = hash_client_ip(client_ip, self._ip_salt)

        now = _now_utc()
        expires_at = now + timedelta(seconds=SESSION_ROLLING_TTL_SECONDS)

        # 1. Create underlying conversation_session in session_memory mode
        memory_policy_public_id = self._resolve_active_memory_policy_public_id()
        conv_session = self.session_service.create_session(
            SessionCreate(
                session_mode="session_memory",
                memory_policy_public_id=memory_policy_public_id,
                participant_type="future_user_reference",
                participant_scope_key=str(uuid4()),
                language_preference=language_preference if language_preference in ("auto", "ta", "en") else "auto",
            ),
            _ANON_ACTOR,
        )
        conversation_session_public_id = conv_session["public_id"]

        # 2. Record anonymous ownership wrapper
        anon_public_id = str(uuid4())
        with self.repository.transaction() as connection:
            self.repository.create_session(
                connection,
                public_id=anon_public_id,
                conversation_session_public_id=conversation_session_public_id,
                session_token_hash=token_hash,
                client_ip_hash=ip_hash,
                expires_at=_to_iso(expires_at),
            )

        # Return the raw token ONLY here. Never persisted, never logged.
        return {
            "conversation_id": conversation_session_public_id,
            "session_token": raw_token,
            "expires_at": expires_at.isoformat(),
            "turn_count": 0,
            "status": "active",
        }

    def validate_session(
        self,
        conversation_id: str,
        raw_token: str | None,
    ) -> dict[str, Any]:
        """Validates token authenticity, session status, and expiration in constant time.
        Raises specific domain errors on any failure.
        """
        if not raw_token:
            raise ChatSessionUnauthorizedError("Missing X-Session-Token header.")

        validate_public_id(conversation_id)

        with self.repository.transaction() as connection:
            row = self.repository.get_by_conversation_id(connection, conversation_id)
            if not row:
                raise ChatSessionNotFoundError("Conversation session not found.")

            session_data = dict(row)

            # Check status
            if session_data["status"] != "active":
                raise ChatSessionNotFoundError(f"Session is {session_data['status']}.")

            # Constant-time token verification (IDOR protection)
            computed_hash = hash_token(raw_token)
            stored_hash = session_data["session_token_hash"]
            if not hmac.compare_digest(stored_hash, computed_hash):
                raise ChatSessionForbiddenError("Invalid session credentials.")

            # Check expiry (both rolling TTL and 7-day hard expiry)
            now = _now_utc()
            created_at = _from_iso(session_data["created_at"])
            expires_at = _from_iso(session_data["expires_at"])
            hard_expiry = created_at + timedelta(seconds=SESSION_HARD_EXPIRY_SECONDS)

            is_expired = now >= expires_at or now >= hard_expiry
            if is_expired:
                self.repository.mark_expired(connection, session_data["public_id"])
            else:
                # Bumping rolling TTL
                new_expires_at = min(now + timedelta(seconds=SESSION_ROLLING_TTL_SECONDS), hard_expiry)
                self.repository.update_activity(
                    connection,
                    session_data["public_id"],
                    last_activity_at=_to_iso(now),
                    expires_at=_to_iso(new_expires_at),
                )
                session_data["expires_at"] = _to_iso(new_expires_at)
                session_data["last_activity_at"] = _to_iso(now)

        if is_expired:
            raise ChatSessionExpiredError("Conversation session has expired.")

        return session_data

    def get_messages(
        self,
        conversation_id: str,
        raw_token: str | None,
    ) -> dict[str, Any]:
        """Validates session ownership and returns historical conversation turns."""
        session = self.validate_session(conversation_id, raw_token)

        with self.repository.transaction() as connection:
            turn_rows = self.repository.get_session_turns(connection, conversation_id)

        messages = [
            {
                "id": turn["public_id"],
                "sequence_number": turn["sequence_number"],
                "role": turn["role"],
                "content": turn["stored_content"],
                "language_category": turn["language_category"],
                "created_at": turn["created_at"],
            }
            for turn in turn_rows
        ]

        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "turn_count": len(messages),
            "expires_at": session["expires_at"],
            "status": "active",
        }

    def clear_session(
        self,
        conversation_id: str,
        raw_token: str | None,
    ) -> dict[str, Any]:
        """Privacy zeroing: validates ownership, purges turn text, and closes session."""
        self.validate_session(conversation_id, raw_token)

        with self.repository.transaction() as connection:
            self.repository.clear_session_content(connection, conversation_id)

        return {
            "conversation_id": conversation_id,
            "status": "closed",
            "cleared": True,
        }
