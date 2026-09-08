"""Phase 61 - P9: Tenant Security Policy Engine.

Enforces multi-tenant data isolation and cross-tenant boundary access controls.

CRITICAL INVARIANTS:
- Access Rules: TENANT_A -> TENANT_A = ALLOW, TENANT_A -> TENANT_B = DENY, UNKNOWN_TENANT -> ANY = DENY, MISSING_TENANT_CONTEXT = DENY.
- No tenant may access another tenant's datasets, evidence, secrets, audit records, or snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class TenantAccessError(PermissionError):
    """Raised when cross-tenant data access attempt is blocked."""


class TenantSecurityPolicyEngine:
    """Multi-tenant security policy & data isolation enforcement engine."""

    def __init__(self, registered_tenants: set[str] | None = None) -> None:
        self.registered_tenants = registered_tenants or {"tenant-brud-core", "tenant-enterprise-a"}

    def authorize_tenant_access(
        self,
        requestor_tenant_id: str | None,
        target_resource_tenant_id: str | None,
    ) -> bool:
        """Evaluate cross-tenant data isolation boundary rules."""
        if not requestor_tenant_id or not target_resource_tenant_id:
            raise TenantAccessError("DENY: Missing tenant context.")

        if requestor_tenant_id not in self.registered_tenants:
            raise TenantAccessError(f"DENY: Unknown requestor tenant '{requestor_tenant_id}'.")

        if target_resource_tenant_id not in self.registered_tenants:
            raise TenantAccessError(f"DENY: Unknown target resource tenant '{target_resource_tenant_id}'.")

        if requestor_tenant_id != target_resource_tenant_id:
            raise TenantAccessError(f"DENY: Cross-tenant access forbidden ({requestor_tenant_id} -> {target_resource_tenant_id}).")

        return True
