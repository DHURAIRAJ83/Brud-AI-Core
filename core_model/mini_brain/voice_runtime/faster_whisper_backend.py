"""MB-26: Real CPU speech-to-text adapter wrapping `faster-whisper`
(quantized `tiny`/`base` model, CPU-only, no GPU requirement).
Import-guarded -- `faster-whisper` is an optional dependency, never a
hard requirement; `is_available()` and the service's own diagnostics
both report its real, live availability rather than assuming it is
installed.

Legitimately impure: real model loading and real audio inference are
unavoidable I/O/CPU work, the same class of exception
`timeout_runner.py` establishes for MB-25's package.

Honest limitation: this adapter is unverified against real model
weights in this repository's own test environment (no faster-whisper
installation is assumed present) -- it is exercised only via
`is_available() is False` fallback-to-mock behavior in the automated
test suite.
"""

from __future__ import annotations

import importlib.util
import io
from typing import Any

name = "faster_whisper"

_model = None
_model_size_loaded: str | None = None


def is_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def _load_model(model_size: str):
    global _model, _model_size_loaded
    if _model is None or _model_size_loaded != model_size:
        from faster_whisper import WhisperModel

        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _model_size_loaded = model_size
    return _model


def transcribe(*, audio_bytes: bytes, language: str = "auto", model_size: str = "tiny") -> dict[str, Any]:
    if not is_available():
        raise RuntimeError("faster-whisper is not installed -- call is_available() first")
    model = _load_model(model_size)
    lang = None if language == "auto" else language
    segments, info = model.transcribe(io.BytesIO(audio_bytes), language=lang)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    return {
        "text": text,
        "detected_language": info.language,
        "confidence": float(info.language_probability),
        "backend": name,
    }
