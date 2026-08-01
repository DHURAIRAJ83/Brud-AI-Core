"""Phase 15 Step 19: secret and frontend-bundle verification.

Reuses the *existing, unmodified* `redact_secrets`/`SECRET_KEYS`
mechanism (`backend.core.json_utils`) as both the thing being verified
(a functional self-check that it still redacts) and the vocabulary
for a real, bounded text scan over the built admin-dashboard bundle
and over domain-model field names. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import redact_secrets
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome

logger = logging.getLogger(__name__)

_BUNDLE_EXTENSIONS = (".js", ".css", ".html", ".json")
_MAX_SCANNED_FILE_BYTES = 5_000_000

_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
)

_FIELD_NAME_EXCEPTIONS = {"token_count", "input_token_count", "output_token_count"}

# `SECRET_KEYS` includes "token", which is overwhelmingly a false-positive
# marker in this codebase's domain-model field names (tokenizer/max_tokens/
# etc. -- NLP tokenization, not an auth token). The field-name scan below
# uses a narrower, domain-appropriate marker set instead of `SECRET_KEYS`.
_FIELD_NAME_MARKERS = {"secret", "password", "api_key", "apikey", "authorization"}


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
                event_type=f"production_secret_scan_{action}",
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
        logger.exception("production_secret_scan_audit_write_failed", extra={"action": action})


class ProductionSecretScanService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def verify_redaction_mechanism(self, *, admin_id: str) -> dict[str, Any]:
        sample = {
            "password": "hunter2", "api_key": "abc123", "safe_field": "keep-me",
            "nested": {"authorization": "Bearer xyz", "still_safe": "keep-me-too"},
        }
        redacted = redact_secrets(sample)
        checks = {
            "top_level_password_redacted": redacted["password"] == "[REDACTED]",
            "top_level_api_key_redacted": redacted["api_key"] == "[REDACTED]",
            "nested_authorization_redacted": redacted["nested"]["authorization"] == "[REDACTED]",
            "safe_fields_preserved": (
                redacted["safe_field"] == "keep-me"
                and redacted["nested"]["still_safe"] == "keep-me-too"
            ),
        }
        findings = [key for key, ok in checks.items() if not ok]
        result_status = "passed" if not findings else "failed"
        event = self.repository.record_readiness_event(
            {
                "event_type": "secret_redaction_mechanism_verified",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"result_status={result_status}",
                "metadata": {"checks": checks, "findings": findings},
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="verify_redaction", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
        )
        return {
            "result_status": result_status, "checks": checks, "findings": findings, "event": event,
        }

    def scan_frontend_bundle(
        self, *, admin_id: str, build_dir: Path | None = None
    ) -> dict[str, Any]:
        if build_dir is None:
            build_dir = (
                Path(__file__).resolve().parents[2] / "apps" / "admin-dashboard" / "dist"
            )
        findings: list[str] = []
        scanned_files = 0
        if not build_dir.exists():
            result_status = "not_applicable"
        else:
            for file_path in build_dir.rglob("*"):
                if not file_path.is_file() or file_path.suffix not in _BUNDLE_EXTENSIONS:
                    continue
                if file_path.stat().st_size > _MAX_SCANNED_FILE_BYTES:
                    continue
                scanned_files += 1
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                for pattern in _SECRET_VALUE_PATTERNS:
                    if pattern.search(text):
                        findings.append(
                            f"{file_path.relative_to(build_dir)}: matches {pattern.pattern}"
                        )
            result_status = "passed" if not findings else "failed"

        event = self.repository.record_readiness_event(
            {
                "event_type": "frontend_bundle_secret_scan",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"result_status={result_status} scanned_files={scanned_files}",
                "metadata": {"findings": findings, "scanned_files": scanned_files},
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="scan_frontend_bundle", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return {
            "result_status": result_status, "findings": findings,
            "scanned_files": scanned_files, "event": event,
        }

    def scan_backup_sidecar_files(self, *, admin_id: str) -> dict[str, Any]:
        """Phase 15A Step 19: a defense-in-depth check that the backup-
        encryption sidecar files (`*.enc.meta.json`) never accidentally
        contain a secret-shaped value. By construction
        (`ProductionBackupEncryptionService`) the sidecar only ever holds
        the key *reference* (an environment variable name), never the key
        value itself -- this scan verifies that guarantee against the
        real files on disk rather than merely trusting the code that
        writes them.
        """
        backup_dir = self.settings.resolved_backup_dir
        findings: list[str] = []
        scanned_files = 0
        if backup_dir.exists():
            for sidecar_path in sorted(backup_dir.glob("*.enc.meta.json")):
                scanned_files += 1
                text = sidecar_path.read_text(encoding="utf-8", errors="ignore")
                for pattern in _SECRET_VALUE_PATTERNS:
                    if pattern.search(text):
                        findings.append(
                            f"{sidecar_path.name}: matches {pattern.pattern}"
                        )
        result_status = "passed" if not findings else "failed"

        event = self.repository.record_readiness_event(
            {
                "event_type": "backup_sidecar_secret_scan",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"result_status={result_status} scanned_files={scanned_files}",
                "metadata": {"findings": findings, "scanned_files": scanned_files},
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="scan_backup_sidecar_files", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return {
            "result_status": result_status, "findings": findings,
            "scanned_files": scanned_files, "event": event,
        }

    def scan_domain_model_field_names(self, *, admin_id: str) -> dict[str, Any]:
        models_dir = Path(__file__).resolve().parents[1] / "models"
        findings: list[str] = []
        field_re = re.compile(r"^\s{4}(\w+)\s*:", re.MULTILINE)
        for model_file in sorted(models_dir.glob("*.py")):
            text = model_file.read_text(encoding="utf-8")
            for match in field_re.finditer(text):
                field_name = match.group(1)
                if field_name in _FIELD_NAME_EXCEPTIONS:
                    continue
                if any(marker in field_name.lower() for marker in _FIELD_NAME_MARKERS):
                    findings.append(f"{model_file.name}: field '{field_name}'")
        result_status = "passed" if not findings else "passed_with_warning"
        event = self.repository.record_readiness_event(
            {
                "event_type": "domain_model_field_name_scan",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"result_status={result_status}",
                "metadata": {"findings": findings},
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="scan_field_names", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
        )
        return {"result_status": result_status, "findings": findings, "event": event}


__all__ = ["ProductionSecretScanService"]
