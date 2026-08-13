"""MB-26: Real text-to-speech adapter wrapping Coqui TTS/XTTS-v2, if
available locally. Import-guarded -- Coqui TTS is an optional
dependency, never a hard requirement; `is_available()` and the
service's own diagnostics both report its real, live availability
rather than assuming it is installed.

Legitimately impure: real model loading and real audio synthesis are
unavoidable I/O/CPU work, the same class of exception as
`faster_whisper_backend.py` above.

Honest limitation: this adapter is unverified against real model
weights in this repository's own test environment (no Coqui TTS
installation is assumed present) -- it is exercised only via
`is_available() is False` fallback-to-mock behavior in the automated
test suite.
"""

from __future__ import annotations

import importlib.util
import tempfile
import time
from pathlib import Path
from typing import Any

name = "coqui_tts"

_synthesizer = None


def is_available() -> bool:
    return importlib.util.find_spec("TTS") is not None


def _load_synthesizer():
    global _synthesizer
    if _synthesizer is None:
        from TTS.api import TTS

        _synthesizer = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            progress_bar=False,
            gpu=False,
        )
    return _synthesizer


def synthesize(*, text: str, language: str = "auto") -> dict[str, Any]:
    if not is_available():
        raise RuntimeError("Coqui TTS is not installed -- call is_available() first")
    synthesizer = _load_synthesizer()
    started = time.perf_counter()
    lang = "en" if language == "auto" else language
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "output.wav"
        synthesizer.tts_to_file(text=text, file_path=str(output_path), language=lang)
        audio_bytes = output_path.read_bytes()
    return {
        "audio_bytes": audio_bytes,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "format": "wav",
        "backend": name,
    }
