"""Conversation turn validation.

Checks role order, content bounds, Unicode validity, secret patterns,
session state, and duplicate-retry detection -- all before a turn is
ever persisted.
"""

from __future__ import annotations

import hashlib
import unicodedata

from core_model.conversation import TURN_ROLES
from core_model.conversation.memory_safety import assess_memory_safety


def content_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_valid_unicode(text: str) -> bool:
    try:
        unicodedata.normalize("NFC", text)
        text.encode("utf-8")
        return True
    except (UnicodeError, ValueError):
        return False


def validate_role_order(role: str, previous_role: str | None) -> tuple[bool, str | None]:
    if role not in TURN_ROLES:
        return False, "unsupported_role"
    if role == "assistant" and previous_role not in {"user", "system"}:
        return False, "assistant_turn_without_preceding_user_turn"
    if previous_role is None:
        return True, None
    return True, None


def detect_duplicate_retry(
    *, role: str, content: str, previous_turn_role: str | None, previous_turn_checksum: str | None
) -> bool:
    """A duplicate request retry submits the same role+content as the
    immediately preceding turn -- must not create a second turn/response."""

    if previous_turn_role is None or previous_turn_checksum is None:
        return False
    return role == previous_turn_role and content_checksum(content) == previous_turn_checksum


def validate_turn(
    *,
    role: str,
    content: str,
    previous_role: str | None,
    session_status: str,
    maximum_characters: int,
    maximum_tokens: int,
    estimated_token_count: int,
) -> dict[str, object]:
    issues: list[str] = []

    role_ok, role_issue = validate_role_order(role, previous_role)
    if not role_ok:
        issues.append(role_issue)

    if session_status != "active":
        issues.append("session_not_active")

    if not content or not content.strip():
        issues.append("empty_content")

    if len(content) > maximum_characters:
        issues.append("maximum_characters_exceeded")

    if estimated_token_count > maximum_tokens:
        issues.append("maximum_tokens_exceeded")

    if not is_valid_unicode(content):
        issues.append("invalid_unicode")

    safety = assess_memory_safety(content)
    if safety["status"] == "blocked":
        issues.append("secret_pattern_detected")

    return {"valid": not issues, "issues": issues, "safety_status": safety["status"]}
