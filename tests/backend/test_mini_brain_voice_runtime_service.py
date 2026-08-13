"""MB-26: service-level tests for MiniBrainVoiceRuntimeService against
a real, seeded temp database and real on-disk confined audio storage
-- no mocks of the service's own dependencies. Drives the full
12-stage workflow with MockSpeechBackend/MockTtsBackend (since no real
faster-whisper/Coqui installation is assumed present in this test
environment) end to end.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.mini_brain_voice_runtime_service import MiniBrainVoiceRuntimeService


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, voice_audio_dir=tmp_path / "voice_audio",
        document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


def _drive_to_capturing(svc: MiniBrainVoiceRuntimeService, *, consent: bool = True) -> dict:
    session = svc.create_voice_session(session_mode="public_chat", raw_client_key="203.0.113.10")
    session = svc.run_check_microphone_permission_stage(session["public_id"], explicit_consent_given=consent)
    if session["status"] != "active":
        return session
    session = svc.run_validate_scopes_stage(session["public_id"])
    session = svc.run_start_capture_stage(session["public_id"])
    return session


def test_full_happy_path_reaches_response_ready_and_closes_completed(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = _drive_to_capturing(svc)
    sid = session["public_id"]
    assert session["stage"] == "capturing"

    svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=b"audio data chunk " * 30)
    svc.run_accept_audio_chunk_stage(sid, sequence=1, audio_bytes=b"more audio data " * 30)

    result = svc.finish_voice_session(sid)
    assert result["stage"] == "response_ready"
    assert result["status"] == "active"

    payload = svc.session_response_payload(sid)
    assert payload["transcript"]
    assert payload["reply"]
    assert payload["tts_audio_relative_path"]

    closed = svc.close_voice_session(sid)
    assert closed["stage"] == "closed"
    assert closed["status"] == "completed"


def test_permission_denied_path_public_chat_without_consent(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = svc.create_voice_session(session_mode="public_chat", raw_client_key="203.0.113.11")
    session = svc.run_check_microphone_permission_stage(session["public_id"], explicit_consent_given=False)
    assert session["status"] == "denied"
    assert session["denial_reason"]


def test_admin_authorization_substitutes_for_consent(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = svc.create_voice_session(session_mode="admin_assistant", requester_admin_public_id="admin-1")
    denied = svc.run_check_microphone_permission_stage(session["public_id"], admin_authorized=False)
    assert denied["status"] == "denied"

    session2 = svc.create_voice_session(session_mode="admin_assistant", requester_admin_public_id="admin-1")
    allowed = svc.run_check_microphone_permission_stage(session2["public_id"], admin_authorized=True)
    assert allowed["status"] == "active"
    assert allowed["stage"] == "permission_checked"


def test_stt_unavailable_falls_back_to_mock_backend(settings: Settings) -> None:
    # No real faster-whisper installation is assumed present in this test
    # environment -- diagnostics() honestly confirms unavailability, and
    # the workflow falls back to the mock backend rather than failing.
    svc = MiniBrainVoiceRuntimeService(settings)
    assert svc.diagnostics()["stt_available"] is False

    session = _drive_to_capturing(svc)
    sid = session["public_id"]
    svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=b"x" * 500)
    svc.run_assemble_stream_stage(sid)
    result = svc.run_stt_stage(sid)
    assert result["stt_backend"] == "mock"


def test_tts_unavailable_falls_back_to_mock_backend(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    assert svc.diagnostics()["tts_available"] is False

    session = _drive_to_capturing(svc)
    sid = session["public_id"]
    svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=b"x" * 500)
    result = svc.finish_voice_session(sid)
    assert result["tts_backend"] == "mock"


def test_oversized_audio_chunk_fails_session(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = _drive_to_capturing(svc)
    sid = session["public_id"]

    oversized = b"x" * int(settings.voice_max_audio_mb * 1_000_000 + 1)
    result = svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=oversized)
    assert result["status"] == "failed"
    assert "max_audio_mb" in result["denial_reason"]


def test_duration_estimate_exceeding_max_record_seconds_marks_timeout(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = svc.create_voice_session(session_mode="public_chat", raw_client_key="203.0.113.12")
    session = svc.run_check_microphone_permission_stage(session["public_id"], explicit_consent_given=True)
    session = svc.run_validate_scopes_stage(session["public_id"])
    session = svc.run_start_capture_stage(session["public_id"])
    sid = session["public_id"]

    # Under the 8MB size ceiling but, at the assembler's default
    # 32000 bytes/sec assumption, well over a tight max_record_seconds.
    settings.voice_max_record_seconds = 1.0
    svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=b"x" * 320_000)
    result = svc.run_assemble_stream_stage(sid)
    assert result["status"] == "timeout"


def test_out_of_order_stage_call_raises_validation_error(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = svc.create_voice_session(session_mode="public_chat", raw_client_key="203.0.113.13")
    sid = session["public_id"]
    with pytest.raises(ValidationError):
        svc.run_start_capture_stage(sid)  # skipping permission + scopes stages


def test_accept_chunk_before_capturing_raises_validation_error(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = svc.create_voice_session(session_mode="public_chat", raw_client_key="203.0.113.14")
    sid = session["public_id"]
    with pytest.raises(ValidationError):
        svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=b"x")


def test_close_session_deletes_on_disk_audio_directory(settings: Settings) -> None:
    from core_model.mini_brain.voice_runtime import audio_session_manager

    svc = MiniBrainVoiceRuntimeService(settings)
    session = _drive_to_capturing(svc)
    sid = session["public_id"]
    svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=b"x" * 500)
    svc.finish_voice_session(sid)

    assert audio_session_manager.session_dir_exists(settings.resolved_voice_audio_dir, sid) is True
    svc.close_voice_session(sid)
    assert audio_session_manager.session_dir_exists(settings.resolved_voice_audio_dir, sid) is False


def test_close_already_denied_session_preserves_denied_status(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = svc.create_voice_session(session_mode="public_chat", raw_client_key="203.0.113.15")
    svc.run_check_microphone_permission_stage(session["public_id"], explicit_consent_given=False)
    closed = svc.close_voice_session(session["public_id"])
    assert closed["status"] == "denied"
    assert closed["stage"] == "closed"


def test_close_already_closed_session_raises(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = svc.create_voice_session(session_mode="public_chat", raw_client_key="203.0.113.16")
    svc.run_check_microphone_permission_stage(session["public_id"], explicit_consent_given=False)
    svc.close_voice_session(session["public_id"])
    with pytest.raises(ValidationError):
        svc.close_voice_session(session["public_id"])


def test_mb24_plugin_tables_unchanged_by_a_full_voice_session(settings: Settings) -> None:
    conn = sqlite3.connect(settings.resolved_database_path)
    plugin_tables = [
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mini_brain_plugin%'"
        ).fetchall()
    ]
    before = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in plugin_tables}
    conn.close()

    svc = MiniBrainVoiceRuntimeService(settings)
    session = _drive_to_capturing(svc)
    sid = session["public_id"]
    svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=b"x" * 500)
    svc.finish_voice_session(sid)
    svc.close_voice_session(sid)

    conn = sqlite3.connect(settings.resolved_database_path)
    after = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in plugin_tables}
    conn.close()
    assert before == after


def test_verify_ownership_matches_and_rejects(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = svc.create_voice_session(session_mode="public_chat", raw_client_key="203.0.113.17")
    sid = session["public_id"]
    assert svc.verify_ownership(sid, raw_client_key="203.0.113.17") is True
    assert svc.verify_ownership(sid, raw_client_key="203.0.113.99") is False


def test_no_raw_audio_bytes_persisted_in_voice_messages_table(settings: Settings) -> None:
    svc = MiniBrainVoiceRuntimeService(settings)
    session = _drive_to_capturing(svc)
    sid = session["public_id"]
    svc.run_accept_audio_chunk_stage(sid, sequence=0, audio_bytes=b"real audio payload " * 20)
    svc.finish_voice_session(sid)

    conn = sqlite3.connect(settings.resolved_database_path)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(mini_brain_voice_messages)").fetchall()]
    assert "audio_bytes" not in columns
    assert "raw_audio" not in columns
    rows = conn.execute("SELECT sanitized_text, audio_hash FROM mini_brain_voice_messages").fetchall()
    conn.close()
    assert len(rows) >= 1
    for sanitized_text, audio_hash in rows:
        assert b"real audio payload" not in sanitized_text.encode("utf-8")
