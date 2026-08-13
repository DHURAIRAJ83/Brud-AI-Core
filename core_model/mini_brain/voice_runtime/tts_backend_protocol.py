"""MB-26: TTS backend contract every text-to-speech backend module
implements (as free functions -- see mock_tts_backend.py /
coqui_tts_backend.py). Pure -- a Protocol definition carries no logic
and no side effects.
"""

from __future__ import annotations

from typing import Any, Protocol


class TtsBackend(Protocol):
    name: str

    def synthesize(self, *, text: str, language: str = "auto") -> dict[str, Any]:
        """Returns {"audio_bytes": bytes, "duration_ms": float, "format": str, "backend": str}."""
        ...
