"""MB-28: Message Sanitizer -- pure. Reuses `core_model.mini_brain.
public_chat_runtime.feedback_sanitizer.sanitize_text()` directly (not
re-implemented), the same reuse pattern MB-26's `voice_result_
sanitizer.py` already established, for every admin/assistant message
before it is ever persisted.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from core_model.mini_brain.public_chat_runtime.feedback_sanitizer import sanitize_text

MAX_MESSAGE_LENGTH = 8000


def sanitize_message(*, raw_text: str) -> dict[str, Any]:
    nfc_text = unicodedata.normalize("NFC", raw_text) if raw_text else ""
    result = sanitize_text(raw_text=nfc_text)
    text = unicodedata.normalize("NFC", result["sanitized_text"])
    truncated = bool(result["truncated"])
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]
        truncated = True
    return {
        "sanitized_text": text,
        "redaction_categories_applied": result["redaction_categories_applied"],
        "truncated": truncated,
    }
