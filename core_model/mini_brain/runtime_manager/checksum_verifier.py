"""MB-30: Checksum Verifier -- pure. `compute_sha256()` hashes bytes
already read by the caller (in-memory computation, not I/O -- the
same precedent MB-26's `voice_result_sanitizer.hash_audio()`
established); it never opens a file itself.
"""

from __future__ import annotations

import hashlib
from typing import Any


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_digest(*, actual_sha256: str, expected_sha256: str) -> dict[str, Any]:
    matches = actual_sha256.lower() == expected_sha256.lower()
    return {
        "matches": matches,
        "actual_sha256": actual_sha256,
        "expected_sha256": expected_sha256,
        "message_en": "Checksum verified." if matches else "Checksum mismatch -- the downloaded file does not match the expected model.",
        "message_ta": "செக்சம் சரிபார்க்கப்பட்டது." if matches else "செக்சம் பொருந்தவில்லை -- பதிவிறக்கம் செய்யப்பட்ட கோப்பு எதிர்பார்க்கப்பட்ட மாடலுடன் பொருந்தவில்லை.",
    }
