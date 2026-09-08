"""Phase 45 — Admin Structured Audit Logger.

Implements Workstream 15:
- Machine-readable JSONL audit logging
- Records timestamp, request_id, admin_id, tenant_id, operation, status, details
- Strictly sanitizes and excludes secrets, credentials, passwords, and tokens
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AdminAuditRecord:
    timestamp: str
    request_id: str
    admin_id: str
    tenant_id: str
    role: str
    scope: str
    operation: str
    status: str  # SUCCESS | DENIED | ERROR
    resource_id: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdminAuditLogger:
    """Logs structured audit events to phase45_admin_audit.jsonl while filtering sensitive data."""

    FORBIDDEN_KEYS = {"password", "secret", "token", "api_key", "credential"}

    def __init__(self, log_path: Path) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, record: AdminAuditRecord) -> None:
        """Appends sanitized audit record to audit JSONL file."""
        data = record.to_dict()
        # Security scan: Ensure no secrets leak
        for k, v in data.items():
            if any(forbidden in k.lower() for forbidden in self.FORBIDDEN_KEYS) and k != "token_signature":
                data[k] = "[REDACTED]"
            if isinstance(v, str) and any(forbidden in v.lower() for forbidden in self.FORBIDDEN_KEYS):
                data[k] = "[REDACTED_CONTENT]"

        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
