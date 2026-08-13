"""MB-21: Prompt Sanitizer -- pure. Every prompt is sanitized before
it is ever handed to a provider client: API keys, filesystem paths,
database identifiers, and local usernames are redacted; oversized
payloads are truncated; a privacy audit record is attached; both the
original and sanitized text are hashed (never the plain text itself
persisted by the caller) so a later admin can verify what was actually
sent without this module ever storing the raw prompt.

Regex shapes for secret-like and absolute-path content intentionally
mirror `core_model.release.manifest`'s own private detection patterns
(the same real, already-tested concerns MB-18/19/20's manifests are
scanned for) -- not imported directly since those names are private to
that module, but the same well-proven shapes, now doing redaction
instead of only detection.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

MAX_PROMPT_LENGTH = 8_000

_SECRET_LIKE_PATTERN = re.compile(r"\b(api[_-]?key|password|secret|token)\s*[:=]\s*\S+", re.IGNORECASE)
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|[\s\"])(?:/home/|/etc/|/usr/|/var/|[A-Za-z]:\\\\)\S*")
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_DB_ID_PATTERN = re.compile(r"\b(?:row[_ ]?id|record[_ ]?id|database[_ ]?id)\s*[:=#]\s*\d+", re.IGNORECASE)
_USERNAME_PATH_PATTERN = re.compile(r"/home/([A-Za-z0-9_.-]+)/")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitize_prompt(*, raw_prompt: str, allow_private_context: bool = False, private_context: str = "") -> dict[str, Any]:
    original_hash = _hash(raw_prompt)
    text = raw_prompt
    redactions: list[str] = []

    if _SECRET_LIKE_PATTERN.search(text):
        text = _SECRET_LIKE_PATTERN.sub("[REDACTED_SECRET]", text)
        redactions.append("secret_like_content")

    if _USERNAME_PATH_PATTERN.search(text):
        redactions.append("local_username")
    if _ABSOLUTE_PATH_PATTERN.search(text):
        text = _ABSOLUTE_PATH_PATTERN.sub("[REDACTED_PATH]", text)
        redactions.append("filesystem_path")

    if _UUID_PATTERN.search(text):
        text = _UUID_PATTERN.sub("[REDACTED_ID]", text)
        redactions.append("database_identifier_uuid")
    if _DB_ID_PATTERN.search(text):
        text = _DB_ID_PATTERN.sub("[REDACTED_ID]", text)
        redactions.append("database_identifier_numeric")

    if allow_private_context and private_context.strip():
        text = f"{text}\n\n{private_context.strip()}"
        redactions.append("private_context_explicitly_included")
    elif private_context.strip():
        redactions.append("private_context_excluded_not_approved")

    truncated = False
    if len(text) > MAX_PROMPT_LENGTH:
        text = text[:MAX_PROMPT_LENGTH]
        truncated = True
        redactions.append("truncated_oversized_payload")

    sanitized_hash = _hash(text)

    return {
        "sanitized_prompt": text, "original_hash_sha256": original_hash, "sanitized_hash_sha256": sanitized_hash,
        "changed": original_hash != sanitized_hash, "truncated": truncated,
        "original_length": len(raw_prompt), "sanitized_length": len(text),
        "privacy_audit": {
            "redaction_categories_applied": redactions,
            "private_context_included": allow_private_context and bool(private_context.strip()),
        },
        "disclosure": (
            "regex-based redaction only -- a best-effort defense, never a guarantee that all "
            "sensitive content is caught; the sanitized prompt (not the original) is the only text "
            "ever handed to a provider client"
        ),
    }
