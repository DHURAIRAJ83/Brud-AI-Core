"""MB-26: Brud Mini Brain Voice & Speech Runtime -- orchestration layer
for the 12-stage voice workflow (create session -> check microphone
permission -> validate voice scopes -> start capture -> accept audio
chunk(s) -> assemble stream -> run STT -> route to
PublicChatRoutingService -> receive response -> run TTS -> return
response metadata -> close session). Each `run_<stage>_stage()` method
checks the session row's current `stage` column before proceeding and
raises `ValidationError` on an out-of-order call -- the same
structural-enforcement pattern MB-25's `run_execution` uses.

Reuses, never re-implements:
- `PublicChatRoutingService.handle_message()` for the actual answer --
  its `.reply` has ALREADY passed
  `core_model.public_chat.output_safety.evaluate_output_safety()`
  internally, so this service never re-runs text safety on it.
- `core_model.mini_brain.public_chat_runtime.feedback_sanitizer.
  sanitize_text()` (via `voice_result_sanitizer.py`) for every
  transcript before persistence.
- `hash_client_key()` with the same salt field MB-23 already uses
  (`mini_brain_public_chat_runtime_hash_salt`) for public-session
  identity hashing and ownership checks -- never a new, parallel
  hashing scheme.

Permission model (see the completion report's Reuse Audit for the
full justification): `microphone.capture` in MB-24's own registry is
`public_chat_available: False`, because that entry was designed for
third-party PLUGIN requests, not this first-party feature. Voice
Runtime therefore does not go through MB-24's plugin registration/
consent pipeline at all -- it enforces its own, separate, explicit
per-session consent for public chat (recorded in
`mini_brain_voice_permissions`), and requires real admin authorization
for admin_assistant mode. `voice_permission_guard.py` deliberately
does not call `runtime_policy_evaluator.evaluate_permission()` --
that function's signature requires `plugin_status`/`risk_level`/
`admin_reviewed`, which have no honest value for a feature with no
plugin record.

No raw audio is ever written to the database -- audio bytes live only
under `Settings.resolved_voice_audio_dir`, confined via
`resolve_confined_path()` (inside `audio_session_manager.py`), and are
deleted by `close_voice_session()` when a session closes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_voice_runtime import (
    MiniBrainVoiceRuntimeRepository,
    public_event_row,
    public_memory_row,
    public_message_row,
    public_permission_row,
    public_session_row,
)
from backend.models.public_chat import PublicChatRequest, PublicChatResponse
from backend.services.public_chat_routing_service import PublicChatRoutingService
from core_model.mini_brain.public_chat_runtime.session_builder import hash_client_key
from core_model.mini_brain.voice_runtime import (
    audio_session_manager,
    coqui_tts_backend,
    faster_whisper_backend,
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

_ACTIVE_STATUS = "active"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainVoiceRuntimeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainVoiceRuntimeRepository(settings.resolved_database_path)

    # -- diagnostics ------------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        stt_available = faster_whisper_backend.is_available()
        tts_available = coqui_tts_backend.is_available()
        wakeword_result = wakeword_policy.evaluate_wakeword(
            wakeword_enabled=self.settings.voice_wakeword_enabled, session_mode="diagnostics",
        )
        return voice_diagnostics.build(
            stt_available=stt_available,
            tts_available=tts_available,
            stt_model_size=self.settings.voice_stt_model_size,
            max_record_seconds=self.settings.voice_max_record_seconds,
            max_audio_mb=self.settings.voice_max_audio_mb,
            wakeword_active=wakeword_result["active"],
        )

    # -- helpers -------------------------------------------------------------

    def _event(
        self, connection, session_id: int | None, event_type: str, *,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.create_event(
            connection, session_id=session_id, event_type=event_type, stage=stage,
            message=message, metadata=metadata or {},
        )

    def _hash_identity(self, raw_client_key: str) -> str:
        return hash_client_key(
            raw_client_key=raw_client_key, salt=self.settings.mini_brain_public_chat_runtime_hash_salt,
        )

    def _require_stage(self, session_row, expected_stage: str) -> None:
        if session_row["status"] != _ACTIVE_STATUS:
            raise ValidationError(
                f"voice session status must be 'active' (currently '{session_row['status']}')"
            )
        if session_row["stage"] != expected_stage:
            raise ValidationError(
                f"voice session stage must be '{expected_stage}' (currently '{session_row['stage']}')"
            )

    # -- reads -----------------------------------------------------------------

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.get_session(connection, session_public_id))

    def list_sessions(
        self, *, limit: int = 50, offset: int = 0, status: str | None = None, session_mode: str | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(
                connection, limit=limit, offset=offset, status=status, session_mode=session_mode,
            )
        return {"items": [public_session_row(row) for row in rows]}

    def list_messages(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            rows = self.repository.list_messages(
                connection, session_id=session_row["id"], limit=limit, offset=offset,
            )
        return {"items": [public_message_row(row) for row in rows]}

    def list_permissions(self, session_public_id: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            rows = self.repository.list_permissions(
                connection, session_id=session_row["id"], limit=limit, offset=offset,
            )
        return {"items": [public_permission_row(row) for row in rows]}

    def list_events(
        self, session_public_id: str | None = None, *, limit: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_id = None
            if session_public_id:
                session_id = self.repository.get_session(connection, session_public_id)["id"]
            rows = self.repository.list_events(connection, session_id=session_id, limit=limit, offset=offset)
        return {"items": [public_event_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        memory_items = [public_memory_row(row) for row in rows]
        return {"items": memory_items, "metrics": voice_metrics.aggregate(memory_items)}

    def statistics(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self.repository.statistics(connection)

    def session_response_payload(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            message_rows = self.repository.list_messages(
                connection, session_id=session_row["id"], limit=100, offset=0
            )
        session_data = public_session_row(session_row)
        messages = [public_message_row(row) for row in message_rows]
        transcript = next((m["sanitized_text"] for m in messages if m["message_type"] == "transcript"), None)
        reply = next((m["sanitized_text"] for m in messages if m["message_type"] == "reply"), None)
        tts_path = next(
            (m["tts_audio_relative_path"] for m in messages if m["message_type"] == "tts_output"), None
        )
        return {
            "public_id": session_data["public_id"],
            "session_mode": session_data["session_mode"],
            "stage": session_data["stage"],
            "status": session_data["status"],
            "transcript": transcript,
            "reply": reply,
            "tts_audio_relative_path": tts_path,
            "denial_reason": session_data.get("denial_reason"),
        }

    def verify_ownership(self, session_public_id: str, *, raw_client_key: str) -> bool:
        session_data = self.session(session_public_id)
        if session_data["session_mode"] != "public_chat":
            return False
        expected_hash = session_data.get("requester_user_id_hash")
        if not expected_hash:
            return False
        return expected_hash == self._hash_identity(raw_client_key)

    # -- stage 1: create voice session --------------------------------------------

    def create_voice_session(
        self, *, session_mode: str, conversation_id: str | None = None,
        raw_client_key: str | None = None, requester_admin_public_id: str | None = None,
    ) -> dict[str, Any]:
        if session_mode not in ("public_chat", "admin_assistant"):
            raise ValidationError(f"unknown session_mode: {session_mode!r}")
        requester_user_id_hash = self._hash_identity(raw_client_key) if raw_client_key else None
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, session_mode=session_mode, conversation_id=conversation_id,
                requester_user_id_hash=requester_user_id_hash,
                requester_admin_public_id=requester_admin_public_id,
            )
            session_row = self.repository.get_session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="created",
                message=f"mode={session_mode}",
            )
            return public_session_row(self.repository.get_session(connection, public_id))

    # -- stage 2: check microphone permission --------------------------------------

    def run_check_microphone_permission_stage(
        self, session_public_id: str, *, explicit_consent_given: bool = False, admin_authorized: bool = False,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self._require_stage(session_row, "created")

            decision = voice_permission_guard.evaluate(
                scope_key="microphone.capture", session_mode=session_row["session_mode"],
                explicit_consent_given=explicit_consent_given, admin_authorized=admin_authorized,
            )
            self.repository.create_permission(
                connection, session_id=session_row["id"], scope_key="microphone.capture",
                decision="allow" if decision["allowed"] else "deny", reason=decision["reason"],
                explicit_consent_given=explicit_consent_given, admin_authorized=admin_authorized,
            )
            if not decision["allowed"]:
                self.repository.update_session(connection, session_public_id, {
                    "status": "denied", "denial_reason": decision["reason"], "completed_at": _now(),
                    "consent_given": bool(explicit_consent_given),
                })
                self._event(
                    connection, session_row["id"], "session_denied", stage="permission_checked",
                    message=decision["reason"],
                )
                return public_session_row(self.repository.get_session(connection, session_public_id))

            self.repository.update_session(connection, session_public_id, {
                "stage": "permission_checked",
                "consent_given": bool(explicit_consent_given or admin_authorized),
            })
            self._event(
                connection, session_row["id"], "permission_checked", stage="permission_checked",
                message=decision["reason"],
            )
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- stage 3: validate voice scopes ---------------------------------------------

    def run_validate_scopes_stage(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self._require_stage(session_row, "permission_checked")

            for scope_key in ("plugin.storage.local", "chat.read.current"):
                decision = voice_permission_guard.evaluate(
                    scope_key=scope_key, session_mode=session_row["session_mode"],
                )
                self.repository.create_permission(
                    connection, session_id=session_row["id"], scope_key=scope_key,
                    decision="allow" if decision["allowed"] else "deny", reason=decision["reason"],
                    explicit_consent_given=False, admin_authorized=False,
                )

            self.repository.update_session(connection, session_public_id, {"stage": "scopes_validated"})
            self._event(connection, session_row["id"], "scopes_validated", stage="scopes_validated")
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- stage 4: start capture ---------------------------------------------------

    def run_start_capture_stage(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self._require_stage(session_row, "scopes_validated")

            audio_session_manager.start_session(self.settings.resolved_voice_audio_dir, session_public_id)
            self.repository.update_session(connection, session_public_id, {
                "stage": "capturing", "started_at": _now(),
            })
            self._event(connection, session_row["id"], "capture_started", stage="capturing")
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- stage 5: accept audio chunk(s) [repeatable, stage does not advance] --------

    def run_accept_audio_chunk_stage(
        self, session_public_id: str, *, sequence: int, audio_bytes: bytes,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            if session_row["status"] != _ACTIVE_STATUS or session_row["stage"] != "capturing":
                raise ValidationError(
                    f"voice session must be in 'capturing' stage to accept a chunk "
                    f"(currently '{session_row['stage']}')"
                )

            prospective_bytes = session_row["total_audio_bytes"] + len(audio_bytes)
            max_bytes = int(self.settings.voice_max_audio_mb * 1_000_000)
            if prospective_bytes > max_bytes:
                reason = (
                    f"audio size {prospective_bytes} bytes exceeds max_audio_mb "
                    f"({self.settings.voice_max_audio_mb}MB)"
                )
                self.repository.update_session(connection, session_public_id, {
                    "status": "failed", "denial_reason": reason, "completed_at": _now(),
                })
                self._event(connection, session_row["id"], "audio_oversized", stage="capturing", message=reason)
                return public_session_row(self.repository.get_session(connection, session_public_id))

            chunk_meta = audio_session_manager.write_chunk(
                self.settings.resolved_voice_audio_dir, session_public_id, sequence, audio_bytes,
            )
            self.repository.update_session(connection, session_public_id, {
                "total_chunks": session_row["total_chunks"] + 1, "total_audio_bytes": prospective_bytes,
            })
            self._event(
                connection, session_row["id"], "chunk_accepted", stage="capturing", metadata=chunk_meta,
            )
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- stage 6: assemble stream --------------------------------------------------

    def run_assemble_stream_stage(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            if session_row["status"] != _ACTIVE_STATUS or session_row["stage"] != "capturing":
                raise ValidationError(
                    f"voice session must be in 'capturing' stage to assemble "
                    f"(currently '{session_row['stage']}')"
                )

            chunks = audio_session_manager.list_chunks(
                self.settings.resolved_voice_audio_dir, session_public_id
            )
            plan = streaming_chunk_assembler.build_assembly_plan(
                chunks=chunks, max_audio_mb=self.settings.voice_max_audio_mb,
                max_record_seconds=self.settings.voice_max_record_seconds,
            )
            if not plan["valid"]:
                status = "timeout" if "duration" in (plan["reason"] or "") else "failed"
                self.repository.update_session(connection, session_public_id, {
                    "status": status, "denial_reason": plan["reason"], "completed_at": _now(),
                })
                self._event(
                    connection, session_row["id"], "assembly_rejected", stage="capturing",
                    message=plan["reason"],
                )
                return public_session_row(self.repository.get_session(connection, session_public_id))

            assembled = audio_session_manager.assemble(
                self.settings.resolved_voice_audio_dir, session_public_id, plan["ordered_sequences"],
            )
            self.repository.update_session(connection, session_public_id, {"stage": "stream_assembled"})
            self._event(
                connection, session_row["id"], "stream_assembled", stage="stream_assembled",
                metadata=assembled,
            )
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- stage 7: run STT ---------------------------------------------------------

    def run_stt_stage(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self._require_stage(session_row, "stream_assembled")

            audio_bytes = audio_session_manager.read_assembled(
                self.settings.resolved_voice_audio_dir, session_public_id
            )
            if faster_whisper_backend.is_available():
                result = faster_whisper_backend.transcribe(
                    audio_bytes=audio_bytes, model_size=self.settings.voice_stt_model_size,
                )
            else:
                result = mock_speech_backend.transcribe(audio_bytes=audio_bytes)

            sanitized = voice_result_sanitizer.sanitize_transcript(raw_text=result["text"])
            audio_hash = voice_result_sanitizer.hash_audio(audio_bytes)

            self.repository.create_message(
                connection, session_id=session_row["id"], message_type="transcript",
                sanitized_text=sanitized["sanitized_text"],
                redaction_categories=sanitized["redaction_categories_applied"],
                truncated=sanitized["truncated"], audio_hash=audio_hash,
            )
            self.repository.update_session(connection, session_public_id, {
                "stage": "stt_complete", "stt_backend": result["backend"],
            })
            self._event(
                connection, session_row["id"], "stt_complete", stage="stt_complete",
                metadata={"backend": result["backend"], "detected_language": result.get("detected_language")},
            )
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- stage 8: route transcript to PublicChatRoutingService ----------------------

    def run_route_to_public_chat_stage(
        self, session_public_id: str,
    ) -> tuple[dict[str, Any], PublicChatResponse]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self._require_stage(session_row, "stt_complete")
            message_rows = self.repository.list_messages(
                connection, session_id=session_row["id"], limit=100, offset=0
            )
            conversation_id = session_row["conversation_id"]

        transcript_text = next(
            (public_message_row(row)["sanitized_text"] for row in message_rows
             if public_message_row(row)["message_type"] == "transcript"),
            "",
        )
        request = PublicChatRequest(
            message=transcript_text.strip() or "(no speech detected)",
            conversation_id=conversation_id,
        )
        response = PublicChatRoutingService(self.settings).handle_message(request)

        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"stage": "routed"})
            self._event(
                connection, session_row["id"], "routed_to_public_chat", stage="routed",
                metadata={"route_used": response.route_used},
            )
            return public_session_row(self.repository.get_session(connection, session_public_id)), response

    # -- stage 9: receive response --------------------------------------------------

    def run_receive_response_stage(
        self, session_public_id: str, response: PublicChatResponse,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self._require_stage(session_row, "routed")

            # response.reply has already passed
            # core_model.public_chat.output_safety.evaluate_output_safety()
            # inside handle_message() -- never re-run here.
            self.repository.create_message(
                connection, session_id=session_row["id"], message_type="reply",
                sanitized_text=response.reply, redaction_categories=[], truncated=False,
            )
            self.repository.update_session(connection, session_public_id, {"stage": "response_received"})
            self._event(
                connection, session_row["id"], "response_received", stage="response_received",
                metadata={"safety_status": response.safety_status},
            )
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- stage 10: run TTS ----------------------------------------------------------

    def run_tts_stage(
        self, session_public_id: str, *, reply_text: str, language: str = "auto",
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self._require_stage(session_row, "response_received")

            if coqui_tts_backend.is_available():
                result = coqui_tts_backend.synthesize(text=reply_text, language=language)
            else:
                result = mock_tts_backend.synthesize(text=reply_text, language=language)

            output_meta = audio_session_manager.write_output(
                self.settings.resolved_voice_audio_dir, session_public_id, result["audio_bytes"],
            )
            self.repository.create_message(
                connection, session_id=session_row["id"], message_type="tts_output",
                sanitized_text="", redaction_categories=[], truncated=False,
                audio_hash=output_meta["hash"], audio_duration_ms=result["duration_ms"],
                tts_audio_relative_path=output_meta["relative_path"],
            )
            self.repository.update_session(connection, session_public_id, {
                "stage": "tts_complete", "tts_backend": result["backend"],
            })
            self._event(
                connection, session_row["id"], "tts_complete", stage="tts_complete",
                metadata={"backend": result["backend"]},
            )
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- stage 11: return response metadata ------------------------------------------

    def run_return_response_metadata_stage(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            self._require_stage(session_row, "tts_complete")
            self.repository.update_session(connection, session_public_id, {"stage": "response_ready"})
            self._event(connection, session_row["id"], "response_ready", stage="response_ready")
            return public_session_row(self.repository.get_session(connection, session_public_id))

    # -- orchestration convenience: stages 6-11 in one call (the "finish" route) -------

    def finish_voice_session(self, session_public_id: str) -> dict[str, Any]:
        session_data = self.run_assemble_stream_stage(session_public_id)
        if session_data["status"] != _ACTIVE_STATUS:
            return session_data

        session_data = self.run_stt_stage(session_public_id)
        if session_data["status"] != _ACTIVE_STATUS:
            return session_data

        session_data, response = self.run_route_to_public_chat_stage(session_public_id)
        session_data = self.run_receive_response_stage(session_public_id, response)
        session_data = self.run_tts_stage(
            session_public_id, reply_text=response.reply, language=response.answer_language,
        )
        session_data = self.run_return_response_metadata_stage(session_public_id)
        return session_data

    # -- stage 12: close session ----------------------------------------------------

    def close_voice_session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.get_session(connection, session_public_id)
            if session_row["stage"] == "closed":
                raise ValidationError("voice session is already closed")

            if session_row["status"] == _ACTIVE_STATUS:
                final_status = "completed" if session_row["stage"] == "response_ready" else "cancelled"
            else:
                final_status = session_row["status"]

            duration_ms = session_row["recording_duration_ms"]
            if duration_ms is None and session_row["started_at"]:
                started = datetime.strptime(
                    session_row["started_at"], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=UTC)
                duration_ms = (datetime.now(UTC) - started).total_seconds() * 1000

            self.repository.update_session(connection, session_public_id, {
                "stage": "closed", "status": final_status,
                "completed_at": session_row["completed_at"] or _now(),
                "recording_duration_ms": duration_ms,
            })
            updated_row = self.repository.get_session(connection, session_public_id)

            memory_dict = voice_memory_builder.build(session_row=dict(updated_row), recorded_by="system")
            self.repository.create_memory(connection, **memory_dict)

            audio_session_manager.cleanup(self.settings.resolved_voice_audio_dir, session_public_id)
            self._event(
                connection, updated_row["id"], "session_closed", stage="closed",
                message=f"final_status={final_status}",
            )
            return public_session_row(self.repository.get_session(connection, session_public_id))
