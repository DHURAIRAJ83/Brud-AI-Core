"""MB-26: Voice Metrics -- pure aggregation over already-fetched
`mini_brain_voice_runtime_memory` row dicts. No I/O; the service
fetches rows from the repository and passes them in here.
"""

from __future__ import annotations

from typing import Any


def aggregate(memory_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(memory_rows)
    if total == 0:
        return {
            "total_sessions": 0,
            "completed_sessions": 0,
            "denied_sessions": 0,
            "failed_sessions": 0,
            "average_duration_ms": 0.0,
            "stt_backend_usage": {},
            "tts_backend_usage": {},
            "total_audio_bytes": 0,
            "total_chunks": 0,
        }

    durations = [row.get("duration_ms") or 0.0 for row in memory_rows]
    stt_usage: dict[str, int] = {}
    tts_usage: dict[str, int] = {}
    for row in memory_rows:
        stt_backend = row.get("stt_backend_used") or "none"
        tts_backend = row.get("tts_backend_used") or "none"
        stt_usage[stt_backend] = stt_usage.get(stt_backend, 0) + 1
        tts_usage[tts_backend] = tts_usage.get(tts_backend, 0) + 1

    return {
        "total_sessions": total,
        "completed_sessions": sum(1 for row in memory_rows if row.get("final_status") == "completed"),
        "denied_sessions": sum(1 for row in memory_rows if row.get("final_status") == "denied"),
        "failed_sessions": sum(
            1 for row in memory_rows if row.get("final_status") in ("failed", "timeout")
        ),
        "average_duration_ms": round(sum(durations) / total, 3),
        "stt_backend_usage": stt_usage,
        "tts_backend_usage": tts_usage,
        "total_audio_bytes": sum(row.get("total_audio_bytes") or 0 for row in memory_rows),
        "total_chunks": sum(row.get("total_chunks") or 0 for row in memory_rows),
    }
