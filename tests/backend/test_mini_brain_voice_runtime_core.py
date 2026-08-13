"""MB-26: unit tests for the pure (and one designated impure)
core_model/mini_brain/voice_runtime/ modules -- no database, no app,
no HTTP client.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from core_model.mini_brain.voice_runtime import (
    audio_session_manager,
    mock_speech_backend,
    mock_tts_backend,
    streaming_chunk_assembler,
    voice_diagnostics,
    voice_memory_builder,
    voice_metrics,
    voice_permission_guard,
    voice_result_sanitizer,
    wakeword_policy,
)

# -- voice_result_sanitizer ------------------------------------------------------------


def test_sanitize_transcript_redacts_email() -> None:
    result = voice_result_sanitizer.sanitize_transcript(raw_text="my email is a@b.com, call me")
    assert "[REDACTED_EMAIL]" in result["sanitized_text"]
    assert "email" in result["redaction_categories_applied"]


def test_sanitize_transcript_clean_text_unchanged() -> None:
    result = voice_result_sanitizer.sanitize_transcript(raw_text="what is the weather today")
    assert result["sanitized_text"] == "what is the weather today"
    assert result["redaction_categories_applied"] == []
    assert result["truncated"] is False


def test_sanitize_transcript_truncates_long_text() -> None:
    # The reused upstream feedback_sanitizer.sanitize_text() applies its
    # own (shorter, 2000-char) truncation bound first -- so this
    # module's own MAX_TEXT_LENGTH (4000) is a looser outer bound that
    # only ever fires if the upstream sanitizer's output is itself
    # longer than 4000 chars, which cannot happen. This test asserts
    # the actually-observed layered behavior, not an assumed one.
    long_text = "a" * (voice_result_sanitizer.MAX_TEXT_LENGTH + 500)
    result = voice_result_sanitizer.sanitize_transcript(raw_text=long_text)
    assert len(result["sanitized_text"]) <= voice_result_sanitizer.MAX_TEXT_LENGTH
    assert result["truncated"] is True


def test_sanitize_transcript_respects_own_bound_when_upstream_does_not_truncate() -> None:
    # A string just over this module's own MAX_TEXT_LENGTH but under the
    # upstream sanitizer's own (shorter) bound would never occur in
    # practice given the upstream bound is smaller -- this test instead
    # confirms sanitize_transcript() never returns text longer than its
    # own declared MAX_TEXT_LENGTH, regardless of input length.
    long_text = "b" * 10_000
    result = voice_result_sanitizer.sanitize_transcript(raw_text=long_text)
    assert len(result["sanitized_text"]) <= voice_result_sanitizer.MAX_TEXT_LENGTH


def test_hash_audio_deterministic() -> None:
    h1 = voice_result_sanitizer.hash_audio(b"same bytes")
    h2 = voice_result_sanitizer.hash_audio(b"same bytes")
    assert h1 == h2


def test_hash_audio_differs_for_different_bytes() -> None:
    h1 = voice_result_sanitizer.hash_audio(b"bytes one")
    h2 = voice_result_sanitizer.hash_audio(b"bytes two")
    assert h1 != h2


def test_hash_audio_is_sha256_hex() -> None:
    digest = voice_result_sanitizer.hash_audio(b"x")
    assert len(digest) == 64
    int(digest, 16)  # raises ValueError if not valid hex


def test_sanitize_transcript_redacts_phone_number() -> None:
    result = voice_result_sanitizer.sanitize_transcript(raw_text="call me at 987-654-3210")
    assert "phone_number" in result["redaction_categories_applied"]


# -- streaming_chunk_assembler -----------------------------------------------------------


def test_assembly_plan_valid_contiguous_chunks() -> None:
    chunks = [{"sequence": 0, "byte_length": 100}, {"sequence": 1, "byte_length": 100}]
    plan = streaming_chunk_assembler.build_assembly_plan(chunks=chunks, max_audio_mb=8.0, max_record_seconds=30.0)
    assert plan["valid"] is True
    assert plan["ordered_sequences"] == [0, 1]
    assert plan["total_bytes"] == 200


def test_assembly_plan_empty_chunks_invalid() -> None:
    plan = streaming_chunk_assembler.build_assembly_plan(chunks=[], max_audio_mb=8.0, max_record_seconds=30.0)
    assert plan["valid"] is False
    assert "no chunks" in plan["reason"]


def test_assembly_plan_rejects_missing_sequence() -> None:
    chunks = [{"sequence": 0, "byte_length": 10}, {"sequence": 2, "byte_length": 10}]
    plan = streaming_chunk_assembler.build_assembly_plan(chunks=chunks, max_audio_mb=8.0, max_record_seconds=30.0)
    assert plan["valid"] is False
    assert "contiguous" in plan["reason"]


def test_assembly_plan_rejects_duplicate_sequence() -> None:
    chunks = [{"sequence": 0, "byte_length": 10}, {"sequence": 0, "byte_length": 10}]
    plan = streaming_chunk_assembler.build_assembly_plan(chunks=chunks, max_audio_mb=8.0, max_record_seconds=30.0)
    assert plan["valid"] is False


def test_assembly_plan_sorts_out_of_order_input() -> None:
    chunks = [{"sequence": 1, "byte_length": 10}, {"sequence": 0, "byte_length": 10}]
    plan = streaming_chunk_assembler.build_assembly_plan(chunks=chunks, max_audio_mb=8.0, max_record_seconds=30.0)
    assert plan["valid"] is True
    assert plan["ordered_sequences"] == [0, 1]


def test_assembly_plan_rejects_oversized_total() -> None:
    chunks = [{"sequence": 0, "byte_length": 9_000_000}]
    plan = streaming_chunk_assembler.build_assembly_plan(chunks=chunks, max_audio_mb=8.0, max_record_seconds=30.0)
    assert plan["valid"] is False
    assert "max_audio_mb" in plan["reason"]


def test_assembly_plan_rejects_excessive_duration() -> None:
    # 32000 bytes/sec default rate * 40s = 1,280,000 bytes, well under 8MB
    # but exceeding a tight max_record_seconds bound.
    chunks = [{"sequence": 0, "byte_length": 1_280_000}]
    plan = streaming_chunk_assembler.build_assembly_plan(
        chunks=chunks, max_audio_mb=8.0, max_record_seconds=5.0,
    )
    assert plan["valid"] is False
    assert "max_record_seconds" in plan["reason"]


def test_assembly_plan_nonzero_start_sequence() -> None:
    chunks = [{"sequence": 5, "byte_length": 10}, {"sequence": 6, "byte_length": 10}]
    plan = streaming_chunk_assembler.build_assembly_plan(chunks=chunks, max_audio_mb=8.0, max_record_seconds=30.0)
    assert plan["valid"] is True
    assert plan["ordered_sequences"] == [5, 6]


# -- voice_permission_guard --------------------------------------------------------------


def test_guard_public_chat_denied_without_consent() -> None:
    decision = voice_permission_guard.evaluate(
        scope_key="microphone.capture", session_mode="public_chat", explicit_consent_given=False,
    )
    assert decision["allowed"] is False


def test_guard_public_chat_allowed_with_consent() -> None:
    decision = voice_permission_guard.evaluate(
        scope_key="microphone.capture", session_mode="public_chat", explicit_consent_given=True,
    )
    assert decision["allowed"] is True


def test_guard_admin_denied_without_authorization() -> None:
    decision = voice_permission_guard.evaluate(
        scope_key="microphone.capture", session_mode="admin_assistant", admin_authorized=False,
    )
    assert decision["allowed"] is False


def test_guard_admin_allowed_with_authorization() -> None:
    decision = voice_permission_guard.evaluate(
        scope_key="microphone.capture", session_mode="admin_assistant", admin_authorized=True,
    )
    assert decision["allowed"] is True


def test_guard_plugin_storage_local_always_allowed() -> None:
    decision = voice_permission_guard.evaluate(scope_key="plugin.storage.local", session_mode="public_chat")
    assert decision["allowed"] is True


def test_guard_chat_read_current_always_allowed() -> None:
    decision = voice_permission_guard.evaluate(scope_key="chat.read.current", session_mode="admin_assistant")
    assert decision["allowed"] is True


def test_guard_unknown_scope_denied() -> None:
    decision = voice_permission_guard.evaluate(scope_key="camera.capture", session_mode="public_chat")
    assert decision["allowed"] is False
    assert "unknown voice scope" in decision["reason"]


def test_guard_unknown_session_mode_denied() -> None:
    decision = voice_permission_guard.evaluate(scope_key="microphone.capture", session_mode="bogus")
    assert decision["allowed"] is False


def test_guard_public_chat_admin_authorized_alone_insufficient() -> None:
    # admin_authorized must not leak allowance into public_chat mode
    decision = voice_permission_guard.evaluate(
        scope_key="microphone.capture", session_mode="public_chat",
        explicit_consent_given=False, admin_authorized=True,
    )
    assert decision["allowed"] is False


# -- voice_metrics -----------------------------------------------------------------------


def test_metrics_aggregate_empty() -> None:
    result = voice_metrics.aggregate([])
    assert result["total_sessions"] == 0
    assert result["average_duration_ms"] == 0.0


def test_metrics_aggregate_counts_by_status() -> None:
    rows = [
        {"final_status": "completed", "duration_ms": 100, "stt_backend_used": "mock", "tts_backend_used": "mock", "total_audio_bytes": 10, "total_chunks": 1},
        {"final_status": "denied", "duration_ms": 0, "stt_backend_used": None, "tts_backend_used": None, "total_audio_bytes": 0, "total_chunks": 0},
        {"final_status": "timeout", "duration_ms": 5000, "stt_backend_used": "mock", "tts_backend_used": None, "total_audio_bytes": 20, "total_chunks": 2},
    ]
    result = voice_metrics.aggregate(rows)
    assert result["total_sessions"] == 3
    assert result["completed_sessions"] == 1
    assert result["denied_sessions"] == 1
    assert result["failed_sessions"] == 1


def test_metrics_average_duration_computed() -> None:
    rows = [
        {"final_status": "completed", "duration_ms": 100, "total_audio_bytes": 0, "total_chunks": 0},
        {"final_status": "completed", "duration_ms": 300, "total_audio_bytes": 0, "total_chunks": 0},
    ]
    result = voice_metrics.aggregate(rows)
    assert result["average_duration_ms"] == 200.0


def test_metrics_backend_usage_breakdown() -> None:
    rows = [
        {"final_status": "completed", "stt_backend_used": "faster_whisper", "tts_backend_used": "coqui_tts", "total_audio_bytes": 0, "total_chunks": 0},
        {"final_status": "completed", "stt_backend_used": "mock", "tts_backend_used": "mock", "total_audio_bytes": 0, "total_chunks": 0},
    ]
    result = voice_metrics.aggregate(rows)
    assert result["stt_backend_usage"] == {"faster_whisper": 1, "mock": 1}
    assert result["tts_backend_usage"] == {"coqui_tts": 1, "mock": 1}


def test_metrics_sums_bytes_and_chunks() -> None:
    rows = [
        {"final_status": "completed", "total_audio_bytes": 100, "total_chunks": 2},
        {"final_status": "completed", "total_audio_bytes": 200, "total_chunks": 3},
    ]
    result = voice_metrics.aggregate(rows)
    assert result["total_audio_bytes"] == 300
    assert result["total_chunks"] == 5


# -- wakeword_policy (always inactive, structurally) -------------------------------------


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("mode", ["public_chat", "admin_assistant", "diagnostics"])
def test_wakeword_always_inactive(enabled: bool, mode: str) -> None:
    result = wakeword_policy.evaluate_wakeword(wakeword_enabled=enabled, session_mode=mode)
    assert result["active"] is False
    assert "non-goal" in result["reason"]


# -- voice_memory_builder -----------------------------------------------------------------


def test_memory_builder_shape() -> None:
    session_row = {
        "id": 42, "session_mode": "public_chat", "status": "completed",
        "stt_backend": "mock", "tts_backend": "mock", "recording_duration_ms": 1500.0,
        "total_chunks": 3, "total_audio_bytes": 900,
    }
    result = voice_memory_builder.build(session_row=session_row, recorded_by="system")
    assert result["session_id"] == 42
    assert result["session_mode"] == "public_chat"
    assert result["final_status"] == "completed"
    assert result["stt_backend_used"] == "mock"
    assert result["tts_backend_used"] == "mock"
    assert result["duration_ms"] == 1500.0
    assert result["total_chunks"] == 3
    assert result["total_audio_bytes"] == 900
    assert result["recorded_by"] == "system"


def test_memory_builder_missing_optional_fields_default() -> None:
    session_row = {"id": 1, "session_mode": "admin_assistant", "status": "denied"}
    result = voice_memory_builder.build(session_row=session_row, recorded_by="system")
    assert result["total_chunks"] == 0
    assert result["total_audio_bytes"] == 0
    assert result["stt_backend_used"] is None


# -- voice_diagnostics ---------------------------------------------------------------------


def test_diagnostics_build_shape_all_unavailable() -> None:
    result = voice_diagnostics.build(
        stt_available=False, tts_available=False, stt_model_size="tiny",
        max_record_seconds=30.0, max_audio_mb=8.0, wakeword_active=False,
    )
    assert result["stt_backend"] == "mock"
    assert result["tts_backend"] == "mock"
    assert result["local_only"] is True
    assert result["gpu_required"] is False
    assert result["wakeword_enabled"] is False
    for field in (
        "stt_backend", "stt_available", "tts_backend", "tts_available", "local_only",
        "gpu_required", "microphone_runtime_enabled", "wakeword_enabled",
        "max_record_seconds", "max_audio_mb",
    ):
        assert field in result


def test_diagnostics_build_shape_all_available() -> None:
    result = voice_diagnostics.build(
        stt_available=True, tts_available=True, stt_model_size="base",
        max_record_seconds=60.0, max_audio_mb=16.0, wakeword_active=False,
    )
    assert result["stt_backend"] == "faster_whisper"
    assert result["tts_backend"] == "coqui_tts"


def test_diagnostics_wakeword_reflects_active_input_but_wakeword_policy_never_yields_true() -> None:
    # voice_diagnostics.build() itself just echoes whatever wakeword_active
    # value it's given -- the structural guarantee that it's always False
    # lives in wakeword_policy.evaluate_wakeword(), tested above.
    result = voice_diagnostics.build(
        stt_available=False, tts_available=False, stt_model_size="tiny",
        max_record_seconds=30.0, max_audio_mb=8.0, wakeword_active=False,
    )
    assert result["wakeword_enabled"] is False


# -- mock backends (deterministic) ---------------------------------------------------------


def test_mock_speech_backend_deterministic() -> None:
    r1 = mock_speech_backend.transcribe(audio_bytes=b"abc")
    r2 = mock_speech_backend.transcribe(audio_bytes=b"abc")
    assert r1["text"] == r2["text"]


def test_mock_speech_backend_empty_audio() -> None:
    result = mock_speech_backend.transcribe(audio_bytes=b"")
    assert result["text"] == ""


def test_mock_tts_backend_deterministic() -> None:
    r1 = mock_tts_backend.synthesize(text="hello")
    r2 = mock_tts_backend.synthesize(text="hello")
    assert r1["audio_bytes"] == r2["audio_bytes"]


def test_mock_tts_backend_different_text_different_bytes() -> None:
    r1 = mock_tts_backend.synthesize(text="hello")
    r2 = mock_tts_backend.synthesize(text="goodbye")
    assert r1["audio_bytes"] != r2["audio_bytes"]


# -- audio_session_manager (the one designated impure module) ------------------------------


def test_audio_session_manager_write_and_read_chunk() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sid = "session-a"
        audio_session_manager.start_session(root, sid)
        meta = audio_session_manager.write_chunk(root, sid, 0, b"hello")
        assert meta["byte_length"] == 5
        chunks = audio_session_manager.list_chunks(root, sid)
        assert chunks == [{"sequence": 0, "byte_length": 5}]


def test_audio_session_manager_assemble_concatenates_in_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sid = "session-b"
        audio_session_manager.start_session(root, sid)
        audio_session_manager.write_chunk(root, sid, 0, b"hello ")
        audio_session_manager.write_chunk(root, sid, 1, b"world")
        audio_session_manager.assemble(root, sid, [0, 1])
        assert audio_session_manager.read_assembled(root, sid) == b"hello world"


def test_audio_session_manager_write_output_and_read() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sid = "session-c"
        audio_session_manager.start_session(root, sid)
        meta = audio_session_manager.write_output(root, sid, b"tts bytes")
        assert meta["relative_path"] == f"{sid}/response.wav"
        assert audio_session_manager.read_output(root, sid) == b"tts bytes"


def test_audio_session_manager_cleanup_removes_directory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sid = "session-d"
        audio_session_manager.start_session(root, sid)
        audio_session_manager.write_chunk(root, sid, 0, b"data")
        assert audio_session_manager.session_dir_exists(root, sid) is True
        cleaned = audio_session_manager.cleanup(root, sid)
        assert cleaned is True
        assert audio_session_manager.session_dir_exists(root, sid) is False


def test_audio_session_manager_cleanup_nonexistent_returns_false() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        assert audio_session_manager.cleanup(root, "never-existed") is False


def test_audio_session_manager_confines_session_id_no_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with pytest.raises(ValueError):
            audio_session_manager.start_session(root, "../escape")


def test_audio_session_manager_list_chunks_empty_when_no_session() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        assert audio_session_manager.list_chunks(root, "never-created") == []
