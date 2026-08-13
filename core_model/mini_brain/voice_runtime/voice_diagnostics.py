"""MB-26: Voice Diagnostics -- pure. Builds the diagnostics response
shape from already-computed probe results (whether faster-whisper /
Coqui TTS are actually importable, and the actual -- always-False --
result of `wakeword_policy.evaluate_wakeword()`) passed in as
arguments. The service layer does the live `importlib.util.find_spec()`
probing (never cached) and the wakeword_policy call, then calls this
function with the results -- keeping this module deterministic and
unit-testable without any environment dependency.
"""

from __future__ import annotations

from typing import Any


def build(
    *,
    stt_available: bool,
    tts_available: bool,
    stt_model_size: str,
    max_record_seconds: float,
    max_audio_mb: float,
    wakeword_active: bool,
) -> dict[str, Any]:
    return {
        "stt_backend": "faster_whisper" if stt_available else "mock",
        "stt_available": stt_available,
        "tts_backend": "coqui_tts" if tts_available else "mock",
        "tts_available": tts_available,
        "local_only": True,
        "gpu_required": False,
        "microphone_runtime_enabled": True,
        "wakeword_enabled": wakeword_active,
        "max_record_seconds": max_record_seconds,
        "max_audio_mb": max_audio_mb,
        "stt_model_size": stt_model_size,
    }
