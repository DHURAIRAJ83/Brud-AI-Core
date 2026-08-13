"""MB-26: Voice Memory Builder -- pure. Builds the permanent
`mini_brain_voice_runtime_memory` rollup-row dict from a completed
session row. No I/O -- the service persists the returned dict.
"""

from __future__ import annotations

from typing import Any


def build(*, session_row: dict[str, Any], recorded_by: str) -> dict[str, Any]:
    return {
        "session_id": session_row["id"],
        "session_mode": session_row["session_mode"],
        "final_status": session_row["status"],
        "stt_backend_used": session_row.get("stt_backend"),
        "tts_backend_used": session_row.get("tts_backend"),
        "duration_ms": session_row.get("recording_duration_ms"),
        "total_chunks": session_row.get("total_chunks", 0),
        "total_audio_bytes": session_row.get("total_audio_bytes", 0),
        "recorded_by": recorded_by,
    }
