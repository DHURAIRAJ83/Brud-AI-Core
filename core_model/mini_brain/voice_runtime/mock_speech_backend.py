"""MB-26: Deterministic speech-to-text test double. Never decodes real
audio -- returns a fixed, hash-derived transcript so tests and the
smoke test are reproducible without needing real STT model weights
installed. Pure: no I/O beyond in-memory hashing.
"""

from __future__ import annotations

import hashlib
from typing import Any

name = "mock"

_CANNED_TRANSCRIPTS = (
    "hello, how can I help you today",
    "என்ன உதவி வேண்டும்",
    "what is the weather like",
    "can you tell me more about this",
)

_TAMIL_RANGE = (0x0B80, 0x0BFF)


def _looks_tamil(text: str) -> bool:
    return any(_TAMIL_RANGE[0] <= ord(ch) <= _TAMIL_RANGE[1] for ch in text)


def transcribe(*, audio_bytes: bytes, language: str = "auto") -> dict[str, Any]:
    if not audio_bytes:
        return {"text": "", "detected_language": "en", "confidence": 0.0, "backend": name}
    digest = hashlib.sha256(audio_bytes).hexdigest()
    index = int(digest[:8], 16) % len(_CANNED_TRANSCRIPTS)
    text = _CANNED_TRANSCRIPTS[index]
    detected = "ta" if _looks_tamil(text) else "en"
    return {
        "text": text,
        "detected_language": language if language != "auto" else detected,
        "confidence": 0.99,
        "backend": name,
    }
