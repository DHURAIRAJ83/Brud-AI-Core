"""MB-26: Voice Result Sanitizer -- pure. Reuses
`core_model.mini_brain.public_chat_runtime.feedback_sanitizer.
sanitize_text()` directly (not re-implemented) for all transcript/
reply text before it is ever persisted, and computes a deterministic
sha256 hash of raw audio bytes (hashing is pure -- no I/O, no disk
write; the audio bytes themselves are never persisted anywhere by
this module).
"""

from __future__ import annotations

import hashlib
from typing import Any

from core_model.mini_brain.public_chat_runtime.feedback_sanitizer import sanitize_text

MAX_TEXT_LENGTH = 4000


def sanitize_transcript(*, raw_text: str) -> dict[str, Any]:
    result = sanitize_text(raw_text=raw_text)
    text = result["sanitized_text"]
    truncated = bool(result["truncated"])
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        truncated = True
    return {
        "sanitized_text": text,
        "redaction_categories_applied": result["redaction_categories_applied"],
        "truncated": truncated,
    }


def hash_audio(audio_bytes: bytes) -> str:
    return hashlib.sha256(audio_bytes).hexdigest()
