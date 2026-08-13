"""MB-26: Audio Session Manager -- the one explicit local-file-I/O
module in this package, the same class of exception `timeout_runner.py`
establishes for MB-25's otherwise-pure package. Writes/reads/deletes
audio chunk and TTS-output files under a caller-supplied, already-
confined root directory (Settings.resolved_voice_audio_dir) -- never a
database write, never a network call, never a subprocess.

No raw audio blob is ever written anywhere except this confined local
directory, and every file this module creates for a session is
deleted by `cleanup()` when that session closes (ephemeral by
default, matching this project's established PII/no-raw-persistence
discipline).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from core_model.release.artifact_inventory import resolve_confined_path

_ASSEMBLED_FILENAME = "assembled.wav"


def _session_dir(root: Path, session_public_id: str) -> Path:
    return resolve_confined_path(root, session_public_id)


def start_session(root: Path, session_public_id: str) -> Path:
    session_dir = _session_dir(root, session_public_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def write_chunk(root: Path, session_public_id: str, sequence: int, audio_bytes: bytes) -> dict[str, Any]:
    session_dir = _session_dir(root, session_public_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = session_dir / f"chunk_{sequence:06d}.bin"
    chunk_path.write_bytes(audio_bytes)
    return {
        "sequence": sequence,
        "byte_length": len(audio_bytes),
        "hash": hashlib.sha256(audio_bytes).hexdigest(),
    }


def list_chunks(root: Path, session_public_id: str) -> list[dict[str, Any]]:
    """Reads real per-chunk byte lengths directly from disk (never from
    the event log, which is pagination-capped at 100 rows and would
    silently truncate a long recording's chunk list)."""

    session_dir = _session_dir(root, session_public_id)
    if not session_dir.exists():
        return []
    chunks = []
    for path in sorted(session_dir.glob("chunk_*.bin")):
        sequence = int(path.stem.split("_")[1])
        chunks.append({"sequence": sequence, "byte_length": path.stat().st_size})
    return chunks


def assemble(root: Path, session_public_id: str, ordered_sequences: list[int]) -> dict[str, Any]:
    session_dir = _session_dir(root, session_public_id)
    assembled = bytearray()
    for sequence in ordered_sequences:
        chunk_path = session_dir / f"chunk_{sequence:06d}.bin"
        assembled.extend(chunk_path.read_bytes())
    assembled_bytes = bytes(assembled)
    output_path = session_dir / _ASSEMBLED_FILENAME
    output_path.write_bytes(assembled_bytes)
    return {
        "relative_path": f"{session_public_id}/{_ASSEMBLED_FILENAME}",
        "byte_length": len(assembled_bytes),
        "hash": hashlib.sha256(assembled_bytes).hexdigest(),
    }


def read_assembled(root: Path, session_public_id: str) -> bytes:
    session_dir = _session_dir(root, session_public_id)
    return (session_dir / _ASSEMBLED_FILENAME).read_bytes()


def write_output(
    root: Path, session_public_id: str, audio_bytes: bytes, *, filename: str = "response.wav"
) -> dict[str, Any]:
    session_dir = _session_dir(root, session_public_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    output_path = session_dir / filename
    output_path.write_bytes(audio_bytes)
    return {
        "relative_path": f"{session_public_id}/{filename}",
        "byte_length": len(audio_bytes),
        "hash": hashlib.sha256(audio_bytes).hexdigest(),
    }


def read_output(root: Path, session_public_id: str, *, filename: str = "response.wav") -> bytes:
    session_dir = _session_dir(root, session_public_id)
    return (session_dir / filename).read_bytes()


def session_dir_exists(root: Path, session_public_id: str) -> bool:
    return _session_dir(root, session_public_id).exists()


def cleanup(root: Path, session_public_id: str) -> bool:
    session_dir = _session_dir(root, session_public_id)
    if not session_dir.exists():
        return False
    for child in session_dir.iterdir():
        child.unlink()
    session_dir.rmdir()
    return True
