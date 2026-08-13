"""MB-26: STT backend contract every speech-to-text backend module
implements (as free functions, matching this package's convention --
see mock_speech_backend.py / faster_whisper_backend.py). Pure -- a
Protocol definition carries no logic and no side effects.
"""

from __future__ import annotations

from typing import Any, Protocol


class SpeechBackend(Protocol):
    name: str

    def transcribe(self, *, audio_bytes: bytes, language: str = "auto") -> dict[str, Any]:
        """Returns {"text": str, "detected_language": str, "confidence": float, "backend": str}."""
        ...
