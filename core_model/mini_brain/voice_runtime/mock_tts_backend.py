"""MB-26: Deterministic text-to-speech test double. Never invokes a
real synthesizer -- returns a small, fixed byte sequence derived from
the input text's hash, so tests and the smoke test are reproducible
without real TTS model weights installed. Pure: no I/O beyond
in-memory hashing.
"""

from __future__ import annotations

import hashlib
from typing import Any

name = "mock"

# Not a real WAV file -- a deterministic placeholder byte sequence.
_HEADER = b"MOCKWAVE"


def synthesize(*, text: str, language: str = "auto") -> dict[str, Any]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    audio_bytes = _HEADER + digest
    duration_ms = round(max(len(text), 1) * 60.0, 3)
    return {
        "audio_bytes": audio_bytes,
        "duration_ms": duration_ms,
        "format": "mock",
        "backend": name,
    }
