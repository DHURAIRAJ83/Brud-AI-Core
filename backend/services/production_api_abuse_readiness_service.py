"""Phase 15 Step 18: API-abuse / model-extraction readiness.

A read-only, deterministic assessment of protections that already
exist in the codebase -- bounded request-field lengths, CSRF
configuration, canary-abuse thresholds, and a static scan confirming
no route exposes raw model/checkpoint/tokenizer-weight/RAG-payload
content through a download-shaped endpoint. Never adds new middleware
or enforcement; a Phase 15 readiness check reports on existing state,
it does not build new infrastructure. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.inference_runtime import DiagnosticGenerateRequest
from backend.models.rag import RagSessionMessageCreate

logger = logging.getLogger(__name__)

_CANARY_THRESHOLD_SETTINGS = (
    "inference_canary_max_failure_rate",
    "inference_canary_max_timeout_rate",
    "inference_canary_max_role_leakage_rate",
    "inference_canary_max_prompt_leakage_rate",
    "inference_canary_max_duplicate_rate",
)

_FORBIDDEN_DOWNLOAD_BODY_MARKERS = (
    "resolved_pretraining_dir", "resolved_tokenizer_dir", "resolved_core_checkpoint_dir",
    "checkpoint_dir", "model_state", "weights_checksum", "rag_chunk", "rag_vector_index",
    "quarantine_content", "raw_content",
)

_ROUTE_DECORATOR_RE = re.compile(r'@router\.(?:get|post)\([^)]*download[^)]*\)', re.IGNORECASE)


def _field_max_length(model_cls: type, field_name: str) -> int | None:
    schema = model_cls.model_json_schema()
    return schema.get("properties", {}).get(field_name, {}).get("maxLength")


def _scan_route_file_for_forbidden_downloads(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    findings = []
    for match in _ROUTE_DECORATOR_RE.finditer(text):
        next_decorator = text.find("@router.", match.end())
        block = text[match.end():next_decorator if next_decorator != -1 else len(text)]
        for marker in _FORBIDDEN_DOWNLOAD_BODY_MARKERS:
            if marker in block:
                findings.append(f"{path.name}: download endpoint references '{marker}'")
    return findings


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"production_api_abuse_readiness_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_readiness_event",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "production_api_abuse_readiness_audit_write_failed", extra={"action": action}
        )


class ProductionApiAbuseReadinessService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def assess(self, *, admin_id: str) -> dict[str, Any]:
        from backend.models.public_chat import PublicChatRequest

        checks: dict[str, Any] = {
            "chat_message_length_bounded": (
                _field_max_length(PublicChatRequest, "message") is not None
            ),
            "rag_session_message_length_bounded": (
                _field_max_length(RagSessionMessageCreate, "message") is not None
            ),
            "diagnostic_prompt_length_bounded": (
                _field_max_length(DiagnosticGenerateRequest, "prompt") is not None
            ),
            "csrf_configured": bool(
                self.settings.csrf_cookie_name and self.settings.csrf_header_name
            ),
            "canary_thresholds_bounded": all(
                0 <= getattr(self.settings, name) <= 1 for name in _CANARY_THRESHOLD_SETTINGS
            ),
        }

        route_dir = Path(__file__).resolve().parents[1] / "api" / "routes"
        download_findings: list[str] = []
        for route_file in sorted(route_dir.glob("*.py")):
            download_findings.extend(_scan_route_file_for_forbidden_downloads(route_file))
        checks["no_forbidden_download_endpoints"] = not download_findings

        findings = [key for key, ok in checks.items() if ok is False] + download_findings
        result_status = "passed" if not findings else "failed"

        event = self.repository.record_readiness_event(
            {
                "event_type": "api_abuse_readiness_assessed",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"result_status={result_status}",
                "metadata": {"checks": checks, "findings": findings},
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="assess", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return {
            "result_status": result_status, "checks": checks, "findings": findings, "event": event,
        }


__all__ = ["ProductionApiAbuseReadinessService"]
