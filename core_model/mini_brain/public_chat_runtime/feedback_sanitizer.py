"""MB-23: Feedback Sanitizer -- pure. Every piece of user-facing text
MB-23 ever normalizes for storage (a feedback comment, a rephrased
question) is run through this sanitizer first -- nothing downstream
(`feedback_signal_extractor.py`, `gap_detector.py`, the repository
layer) ever sees or stores the raw text. Regex shapes for secret-like
content, filesystem paths, and database identifiers mirror MB-21's own
`prompt_sanitizer.py` exactly (not imported, since sanitizing a
different input class -- public end-user chat text, not admin-authored
provider prompts -- but the same well-proven shapes). Email, phone
number, URL-with-token, JWT, and bearer/access-token patterns are new
to this module, matching the categories the MB-23 task spec names.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

MAX_TEXT_LENGTH = 2_000

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}\b")
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_BEARER_TOKEN_PATTERN = re.compile(r"\b(?:bearer|access[_-]?token)\s*[:=]?\s*\S+", re.IGNORECASE)
_SECRET_LIKE_PATTERN = re.compile(r"\b(api[_-]?key|password|secret|token)\s*[:=]\s*\S+", re.IGNORECASE)
_URL_WITH_TOKEN_PATTERN = re.compile(
    r"https?://\S*[?&](?:token|key|api_key|access_token|auth)=\S+", re.IGNORECASE
)
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|[\s\"])(?:/home/|/etc/|/usr/|/var/|[A-Za-z]:\\\\)\S*")
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_DB_ID_PATTERN = re.compile(r"\b(?:row[_ ]?id|record[_ ]?id|database[_ ]?id)\s*[:=#]\s*\d+", re.IGNORECASE)
_PHONE_MIN_DIGITS = 7


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _redact_phone_numbers(text: str) -> tuple[str, bool]:
    matched = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal matched
        digit_count = sum(character.isdigit() for character in match.group(0))
        if digit_count < _PHONE_MIN_DIGITS:
            return match.group(0)
        matched = True
        return "[REDACTED_PHONE]"

    return _PHONE_PATTERN.sub(_replace, text), matched


def sanitize_text(*, raw_text: str) -> dict[str, Any]:
    original_hash = _hash(raw_text)
    text = raw_text
    redactions: list[str] = []

    if _URL_WITH_TOKEN_PATTERN.search(text):
        text = _URL_WITH_TOKEN_PATTERN.sub("[REDACTED_URL_WITH_TOKEN]", text)
        redactions.append("url_with_token")

    if _JWT_PATTERN.search(text):
        text = _JWT_PATTERN.sub("[REDACTED_JWT]", text)
        redactions.append("jwt")

    if _BEARER_TOKEN_PATTERN.search(text):
        text = _BEARER_TOKEN_PATTERN.sub("[REDACTED_TOKEN]", text)
        redactions.append("access_token")

    if _SECRET_LIKE_PATTERN.search(text):
        text = _SECRET_LIKE_PATTERN.sub("[REDACTED_SECRET]", text)
        redactions.append("secret_like_content")

    if _EMAIL_PATTERN.search(text):
        text = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        redactions.append("email")

    if _ABSOLUTE_PATH_PATTERN.search(text):
        text = _ABSOLUTE_PATH_PATTERN.sub("[REDACTED_PATH]", text)
        redactions.append("filesystem_path")

    # UUID/numeric-id passes run before the phone-number pass: a UUID's
    # dash-separated digit runs (e.g. the trailing 12-digit group) can
    # otherwise satisfy the phone pattern first and get mis-categorized
    # as `phone_number` instead of `database_identifier_uuid`.
    if _UUID_PATTERN.search(text):
        text = _UUID_PATTERN.sub("[REDACTED_ID]", text)
        redactions.append("database_identifier_uuid")
    if _DB_ID_PATTERN.search(text):
        text = _DB_ID_PATTERN.sub("[REDACTED_ID]", text)
        redactions.append("database_identifier_numeric")

    text, phone_matched = _redact_phone_numbers(text)
    if phone_matched:
        redactions.append("phone_number")

    truncated = False
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        truncated = True
        redactions.append("truncated_oversized_payload")

    return {
        "sanitized_text": text, "original_hash_sha256": original_hash, "sanitized_hash_sha256": _hash(text),
        "changed": bool(redactions), "truncated": truncated,
        "original_length": len(raw_text), "sanitized_length": len(text),
        "redaction_categories_applied": redactions,
        "disclosure": (
            "regex-based redaction only -- a best-effort defense, never a guarantee that all personal "
            "data or secrets are caught; the sanitized text (not the original) is the only form MB-23 "
            "ever persists"
        ),
    }
