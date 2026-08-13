"""MB-21: Brud Mini Brain External AI Evaluation Gateway -- the
orchestration layer for the 12-stage session-to-archive workflow
described in the MB-21 task spec.

External AI providers are used strictly as evaluation assistants,
never as autonomous decision-makers. This service never trains a
model, modifies weights, starts a runtime, deploys, approves a
dataset, approves a release, writes into Dataset Studio or Document
Workspace, executes shell commands, downloads executable files, or
calls a provider before an explicit admin authorization is recorded on
this exact session. Every provider output remains untrusted candidate
evidence -- `admin_review()` only ever marks this session's own
findings as accepted/rejected/needs-followup, it never approves
anything downstream.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_external_ai_gateway import (
    MiniBrainExternalAiGatewayRepository,
    public_memory_row,
    public_provider_run_row,
    public_session_row,
)
from backend.services.external_ai_provider_client import (
    OpenRouterProviderClient,
    ProviderClientProtocol,
)
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_vision_rag_service import MiniBrainVisionRagService
from core_model.mini_brain.external_ai_gateway.agreement_analyzer import analyze_agreement
from core_model.mini_brain.external_ai_gateway.data_request_prompt_builder import build_data_request_prompt
from core_model.mini_brain.external_ai_gateway.evaluation_scoring import score_evaluation
from core_model.mini_brain.external_ai_gateway.evidence_bundle_builder import build_evidence_bundle
from core_model.mini_brain.external_ai_gateway.failure_detector import detect_failures
from core_model.mini_brain.external_ai_gateway.gateway_report_generator import generate_gateway_report
from core_model.mini_brain.external_ai_gateway.prompt_sanitizer import sanitize_prompt
from core_model.mini_brain.external_ai_gateway.provider_registry import select_providers
from core_model.mini_brain.external_ai_gateway.provider_response_normalizer import normalize_response
from core_model.mini_brain.external_ai_gateway.public_test_prompt_builder import build_public_test_prompts
from core_model.mini_brain.external_ai_gateway.recommendation_builder import (
    build_data_acquisition_handoff,
    build_public_evaluation_recommendations,
)
from core_model.mini_brain.external_ai_gateway.reproducibility_hasher import build_reproducibility_record
from core_model.mini_brain.external_ai_gateway.request_policy import validate_authorization
from core_model.mini_brain.external_ai_gateway.safety_violation_detector import detect_safety_violations

ADMIN_DECISIONS = {"accept", "reject", "needs_followup"}
ADMIN_STATUS_MAP = {
    "accept": "admin_accepted", "reject": "admin_rejected", "needs_followup": "admin_needs_followup",
}
DEFAULT_TIMEOUT_SECONDS = 30.0


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _timed(fn, /, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn(**kwargs)
    return result, round((time.perf_counter() - started) * 1000, 3)


class MiniBrainExternalAiGatewayService:
    def __init__(self, settings: Settings, *, provider_clients: dict[str, ProviderClientProtocol] | None = None) -> None:
        self.settings = settings
        self.repository = MiniBrainExternalAiGatewayRepository(settings.resolved_database_path)

        self.multimodal_dataset = MiniBrainMultimodalDatasetGeneratorService(settings)
        self.vision_rag = MiniBrainVisionRagService(settings)

        # Real provider clients by key. Tests inject MockProviderClient instances via
        # `provider_clients` -- never a real network call happens unless an admin has
        # genuinely configured BRUD_EXTERNAL_AI_OPENROUTER_API_KEY in this environment.
        self.provider_clients: dict[str, ProviderClientProtocol] = provider_clients or {
            "openrouter": OpenRouterProviderClient(),
        }

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, external_ai_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, external_ai_session_id=external_ai_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset)
        return {"items": [public_session_row(row) for row in rows]}

    def events(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_events(
                connection, external_ai_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def list_provider_runs(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_provider_runs(connection, external_ai_session_id=session_row["id"])
        return {"items": [public_provider_run_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    # -- stage 1: create session --------------------------------------

    def create_session(
        self, *, topic: str, purpose: str, admin_id: str, dataset_session_public_ids: list[str] | None = None,
        rag_session_public_id: str | None = None,
    ) -> dict[str, Any]:
        if not topic.strip():
            raise ValidationError("topic must not be empty")
        if purpose not in ("public_style_stress_test", "data_acquisition_assistance"):
            raise ValidationError("purpose must be 'public_style_stress_test' or 'data_acquisition_assistance'")
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, topic=topic, purpose=purpose, created_by_admin_public_id=admin_id,
            )
            self.repository.update_session(
                connection, public_id,
                {
                    "source_dataset_public_ids_json": dataset_session_public_ids or [],
                    "source_rag_session_public_id": rag_session_public_id,
                },
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="validate_authorization",
                message=f"external AI evaluation session created for topic '{topic}' (purpose={purpose})",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage 2: validate admin authorization -----------------------------------

    def run_validate_authorization_stage(
        self, session_public_id: str, *, authorization_note: str, admin_id: str,
    ) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "validate_authorization":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'validate_authorization'")

        report = validate_authorization(
            admin_public_id=admin_id, authorization_note=authorization_note, purpose=session_data["purpose"],
        )
        if not report["authorized"]:
            raise ValidationError(f"authorization failed: {'; '.join(report['reasons'])}")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "authorization_report_json": report, "admin_authorization_confirmed_by": admin_id,
                    "admin_authorization_note": authorization_note, "admin_authorization_confirmed_at": _now(),
                    "stage": "sanitize_inputs",
                },
            )
            self._event(
                connection, session_row["id"], "authorization_validated", stage="validate_authorization",
                message=f"authorized by {admin_id}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 3: sanitize inputs -------------------------------------------------

    def run_sanitize_inputs_stage(
        self, session_public_id: str, *, admin_stated_need: str = "", admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "sanitize_inputs":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'sanitize_inputs'")

        if session_data["purpose"] == "data_acquisition_assistance":
            if not admin_stated_need.strip():
                raise ValidationError("admin_stated_need is required for data_acquisition_assistance sessions")
            raw_input_text = admin_stated_need
        else:
            context_parts = [session_data["topic"]]
            for dataset_session_public_id in session_data["source_dataset_public_ids"]:
                self.multimodal_dataset.session(dataset_session_public_id)
                records = self.multimodal_dataset.list_records(dataset_session_public_id, status="active")["items"]
                context_parts.extend(
                    str(record["content"].get("assistant") or record["content"].get("output") or "")
                    for record in records[:3]
                )
            if session_data["source_rag_session_public_id"]:
                rag_session = self.vision_rag.session(session_data["source_rag_session_public_id"])
                context_parts.append(rag_session.get("query", ""))
            raw_input_text = " ".join(part for part in context_parts if part)

        report, latency_ms = _timed(sanitize_prompt, raw_prompt=raw_input_text)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"sanitization_report_json": report, "stage": "select_providers"},
            )
            self._event(
                connection, session_row["id"], "inputs_sanitized", stage="sanitize_inputs",
                message=f"redactions: {report['privacy_audit']['redaction_categories_applied']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 4: select providers -------------------------------------------------

    def run_select_providers_stage(
        self, session_public_id: str, *, requested_provider_keys: list[str], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "select_providers":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'select_providers'")

        availability = [
            {"provider_key": key, "status": "enabled" if client.is_available() else "unavailable"}
            for key, client in self.provider_clients.items()
        ]
        report, latency_ms = _timed(
            select_providers, requested_provider_keys=requested_provider_keys, provider_availability=availability,
        )
        report["latency_ms"] = latency_ms
        if not report["ready"]:
            raise ValidationError("no requested provider is currently enabled -- check provider configuration")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "provider_selection_report_json": report, "requested_provider_keys_json": requested_provider_keys,
                    "stage": "dispatch_requests",
                },
            )
            self._event(
                connection, session_row["id"], "providers_selected", stage="select_providers",
                message=f"{report['selected_count']} provider(s) selected",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 5: dispatch provider requests ---------------------------------------

    def run_dispatch_requests_stage(
        self, session_public_id: str, *, admin_id: str, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retain_raw_responses: bool = False,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "dispatch_requests":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dispatch_requests'")

        selected_keys = [p["provider_key"] for p in session_data["provider_selection_report"]["selected_providers"]]

        if session_data["purpose"] == "data_acquisition_assistance":
            prompt_record = build_data_request_prompt(admin_stated_need=session_data["sanitization_report"]["sanitized_prompt"])
            dispatch_prompt = prompt_record["prompt"]
        else:
            prompts = build_public_test_prompts(topic=session_data["topic"])
            dispatch_prompt = "\n\n".join(f"[{p['category']}] {p['prompt']}" for p in prompts["prompts"])

        import hashlib

        request_hash = hashlib.sha256(dispatch_prompt.encode("utf-8")).hexdigest()
        dispatch_started = time.perf_counter()
        run_public_ids: list[str] = []

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for provider_key in selected_keys:
                client = self.provider_clients[provider_key]
                raw_result, provider_latency_ms = _timed(client.dispatch, prompt=dispatch_prompt, timeout_seconds=timeout_seconds)
                response_hash = (
                    hashlib.sha256(raw_result["text"].encode("utf-8")).hexdigest() if raw_result.get("text") else None
                )
                normalized = normalize_response(provider_key=provider_key, raw_result=raw_result, purpose=session_data["purpose"])
                if retain_raw_responses and raw_result.get("text"):
                    normalized = dict(normalized, retained_raw_text=raw_result["text"])

                run_id = self.repository.create_provider_run(
                    connection, external_ai_session_id=session_row["id"], provider_key=provider_key,
                    status=raw_result["status"], request_hash=request_hash, response_hash=response_hash,
                    raw_response_retained=retain_raw_responses and bool(raw_result.get("text")),
                    normalized_response=normalized, latency_ms=raw_result.get("latency_ms"),
                    error_message=raw_result.get("error_message"),
                )
                run_public_ids.append(run_id)

            dispatch_report = {
                "dispatched_provider_keys": selected_keys, "dispatched_count": len(selected_keys),
                "request_hash": request_hash, "total_latency_ms": round((time.perf_counter() - dispatch_started) * 1000, 3),
                "disclosure": "the full raw prompt is never persisted -- only its SHA-256 hash is stored",
            }
            self.repository.update_session(
                connection, session_public_id,
                {"dispatch_report_json": dispatch_report, "stage": "collect_responses"},
            )
            self._event(
                connection, session_row["id"], "requests_dispatched", stage="dispatch_requests",
                message=f"{len(selected_keys)} provider(s) dispatched",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: collect provider responses ---------------------------------------

    def run_collect_responses_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_responses":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_responses'")

        runs = self.list_provider_runs(session_public_id)["items"]
        report = {
            "collected_count": len(runs),
            "status_counts": {status: sum(1 for r in runs if r["status"] == status) for status in {r["status"] for r in runs}},
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"collection_report_json": report, "stage": "normalize_responses"},
            )
            self._event(
                connection, session_row["id"], "responses_collected", stage="collect_responses",
                message=f"{report['collected_count']} provider run(s) collected",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: normalize responses -----------------------------------------------

    def run_normalize_responses_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "normalize_responses":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'normalize_responses'")

        runs = self.list_provider_runs(session_public_id)["items"]
        normalized_responses = []
        for run in runs:
            already_normalized = run["normalized_response"]
            raw_result = {
                "status": run["status"], "text": already_normalized.get("normalized_text"),
                "latency_ms": run["latency_ms"], "error_message": run["error_message"],
            }
            normalized, _ = _timed(normalize_response, provider_key=run["provider_key"], raw_result=raw_result, purpose=session_data["purpose"])
            normalized_responses.append(normalized)

        report = {"normalized_responses": normalized_responses, "normalized_count": len(normalized_responses)}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"normalization_report_json": report, "stage": "analyze_agreement"},
            )
            self._event(
                connection, session_row["id"], "responses_normalized", stage="normalize_responses",
                message=f"{report['normalized_count']} response(s) normalized",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: analyze agreement & failures ---------------------------------------

    def run_analyze_agreement_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "analyze_agreement":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'analyze_agreement'")

        normalized_responses = session_data["normalization_report"]["normalized_responses"]
        runs = self.list_provider_runs(session_public_id)["items"]

        agreement_report, _ = _timed(analyze_agreement, normalized_responses=normalized_responses)
        failure_report, _ = _timed(detect_failures, provider_runs=runs)
        safety_report, _ = _timed(detect_safety_violations, normalized_responses=normalized_responses)

        combined = {"agreement": agreement_report, "failures": failure_report, "safety": safety_report}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"agreement_report_json": combined, "stage": "build_evidence"},
            )
            self._event(
                connection, session_row["id"], "agreement_analyzed", stage="analyze_agreement",
                message=f"agreement_score={agreement_report['agreement_score']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: build evidence bundle -----------------------------------------------

    def run_build_evidence_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "build_evidence":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'build_evidence'")

        agreement_report = session_data["agreement_report"]["agreement"]
        failure_report = session_data["agreement_report"]["failures"]
        safety_report = session_data["agreement_report"]["safety"]
        normalized_responses = session_data["normalization_report"]["normalized_responses"]
        runs = self.list_provider_runs(session_public_id)["items"]

        if session_data["purpose"] == "public_style_stress_test":
            recommendations = build_public_evaluation_recommendations(
                normalized_responses=normalized_responses, agreement_report=agreement_report,
            )
            follow_up = recommendations["suggested_dataset_improvements"] + recommendations["suggested_rag_improvements"]
        else:
            recommendations = build_data_acquisition_handoff(normalized_responses=normalized_responses)
            follow_up = recommendations["next_actions"]

        evidence, latency_ms = _timed(
            build_evidence_bundle, sanitized_prompt_record=session_data["sanitization_report"], provider_runs=runs,
            normalized_responses=normalized_responses, agreement_report=agreement_report,
            failure_report=failure_report, safety_report=safety_report, suggested_follow_up_actions=follow_up,
        )
        evidence["latency_ms"] = latency_ms
        evidence["recommendations"] = recommendations

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"evidence_bundle_json": evidence, "stage": "generate_report"},
            )
            self._event(
                connection, session_row["id"], "evidence_built", stage="build_evidence",
                message="evidence bundle assembled",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 10: generate evaluation report -----------------------------------------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "generate_report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'generate_report'")

        agreement_report = session_data["agreement_report"]["agreement"]
        failure_report = session_data["agreement_report"]["failures"]
        safety_report = session_data["agreement_report"]["safety"]
        scoring_report = score_evaluation(agreement_report=agreement_report, failure_report=failure_report, safety_report=safety_report)
        runs = self.list_provider_runs(session_public_id)["items"]

        report = generate_gateway_report(
            session_public_id=session_public_id, topic=session_data["topic"], purpose=session_data["purpose"],
            provider_runs=runs, agreement_report=agreement_report, failure_report=failure_report,
            safety_report=safety_report, scoring_report=scoring_report,
            recommendations=session_data["evidence_bundle"]["recommendations"],
            privacy_audit=session_data["sanitization_report"]["privacy_audit"],
        )
        reproducibility = build_reproducibility_record(
            gateway_report=report, sanitized_prompt_hash=session_data["sanitization_report"]["sanitized_hash_sha256"],
            source_dataset_public_ids=session_data["source_dataset_public_ids"],
            source_rag_session_public_id=session_data["source_rag_session_public_id"],
        )
        report["reproducibility"] = reproducibility

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"gateway_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "gateway_report_generated", stage="generate_report",
                message=f"confidence={report['confidence_level']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11: admin review -------------------------------------------------------------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")
            session_public = public_session_row(session_row)

            self.repository.record_memory(
                connection, external_ai_session_id=session_row["id"], topic=session_public["topic"],
                purpose=session_public["purpose"],
                provider_count=session_public["agreement_report"]["agreement"]["provider_count"],
                successful_provider_count=session_public["agreement_report"]["agreement"]["successful_provider_count"],
                agreement_score=session_public["agreement_report"]["agreement"]["agreement_score"],
                admin_decision=decision, recorded_by_admin_public_id=admin_id,
            )

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "reviewed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"gateway_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' -- this only marks this evaluation session's own "
                    "findings; no dataset, release, or training decision was made"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 12: archive session -----------------------------------------------------------------

    def archive(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "reviewed":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'reviewed'")
            self.repository.update_session(
                connection, session_public_id, {"stage": "archived", "status": "archived", "archived_at": _now()},
            )
            self._event(
                connection, session_row["id"], "session_archived", stage="reviewed",
                message="external AI evaluation session archived", metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainExternalAiGatewayService"]
