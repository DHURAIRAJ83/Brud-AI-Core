"""MB-26: Streaming Chunk Assembler -- pure. Validates a set of
already-received chunk metadata (sequence, byte length) for
ordering/contiguity and against configured size/duration bounds, and
returns an assembly plan (an ordered sequence list) -- it never
touches actual audio bytes; `audio_session_manager.py` does the real
file I/O using the plan this module returns.

Honest limitation: this is chunked upload/accumulation across
sequential HTTP requests (push-to-talk chunks posted one at a time),
not a true low-latency bidirectional streaming/websocket protocol.
"""

from __future__ import annotations

from typing import Any

_DEFAULT_APPROX_BYTES_PER_SECOND = 32_000.0


def build_assembly_plan(
    *,
    chunks: list[dict[str, Any]],
    max_audio_mb: float,
    max_record_seconds: float,
    approx_bytes_per_second: float = _DEFAULT_APPROX_BYTES_PER_SECOND,
) -> dict[str, Any]:
    if not chunks:
        return {"valid": False, "reason": "no chunks received", "ordered_sequences": [], "total_bytes": 0}

    sequences = sorted(chunk["sequence"] for chunk in chunks)
    expected = list(range(sequences[0], sequences[0] + len(sequences)))
    if sequences != expected:
        return {
            "valid": False,
            "reason": "chunk sequence is not contiguous/ordered",
            "ordered_sequences": [],
            "total_bytes": 0,
        }

    total_bytes = sum(chunk["byte_length"] for chunk in chunks)
    max_bytes = int(max_audio_mb * 1_000_000)
    if total_bytes > max_bytes:
        return {
            "valid": False,
            "reason": f"total audio size {total_bytes} bytes exceeds max_audio_mb ({max_audio_mb}MB)",
            "ordered_sequences": [],
            "total_bytes": total_bytes,
        }

    estimated_seconds = total_bytes / approx_bytes_per_second
    if estimated_seconds > max_record_seconds:
        return {
            "valid": False,
            "reason": (
                f"estimated recording duration {estimated_seconds:.1f}s exceeds "
                f"max_record_seconds ({max_record_seconds}s)"
            ),
            "ordered_sequences": [],
            "total_bytes": total_bytes,
        }

    return {"valid": True, "reason": None, "ordered_sequences": sequences, "total_bytes": total_bytes}
