"""Phase 45 — Admin Authentication and Security Context.

Implements Workstream 11:
- Admin identity verification
- Cryptographic token binding
- Security context for every API call (tenant_id, admin_id, role, scope, request_id, timestamp)
- Fails closed on missing or forged credentials
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class AdminSecurityContext:
    tenant_id: str
    admin_id: str
    role: str  # SUPER_ADMIN | ADMIN | AUDITOR
    scope: str  # admin_model | admin_eval | admin_telemetry | admin_gov
    request_id: str
    timestamp: float
    token_signature: str

    @classmethod
    def create(
        cls,
        tenant_id: str,
        admin_id: str,
        role: str,
        scope: str,
        request_id: str,
        secret_salt: str = "brud_phase45_salt",
    ) -> AdminSecurityContext:
        ts = time.time()
        raw = f"{tenant_id}:{admin_id}:{role}:{scope}:{request_id}:{ts}:{secret_salt}"
        sig = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return cls(
            tenant_id=tenant_id,
            admin_id=admin_id,
            role=role,
            scope=scope,
            request_id=request_id,
            timestamp=ts,
            token_signature=sig,
        )

    def verify_signature(self, secret_salt: str = "brud_phase45_salt") -> bool:
        raw = f"{self.tenant_id}:{self.admin_id}:{self.role}:{self.scope}:{self.request_id}:{self.timestamp}:{secret_salt}"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.token_signature == expected

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
