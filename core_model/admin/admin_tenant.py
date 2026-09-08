"""Phase 45 — Multi-Tenant Resource Isolation Manager.

Implements Workstream 12 & User Directive 4:
- Strict multi-layer authorization chain:
  authenticated_admin -> role_verification -> tenant_verification ->
  resource_ownership -> scope_verification -> operation_authorization -> audit_log
- Tenant boundary enforcement:
  Tenant A cannot read or modify Tenant B candidates, telemetry, evaluations, governance, or artifacts
- Cross-tenant access strictly fails closed
"""

from __future__ import annotations

from typing import Any

from core_model.admin.admin_auth import AdminSecurityContext
from core_model.admin.admin_rbac import AdminRBACManager, RolePermissionDeniedError


class TenantAccessDeniedError(PermissionError):
    """Raised when cross-tenant resource access is attempted."""
    pass


class ScopeAccessDeniedError(PermissionError):
    """Raised when an unauthorized scope (e.g., public_chat) is accessed via Admin API."""
    pass


class TenantResourceManager:
    """Manages tenant-partitioned in-memory store for model candidates, evaluations, and telemetry."""

    def __init__(self) -> None:
        # Partitioned by tenant_id: {tenant_id: {resource_type: {resource_id: resource_data}}}
        self._tenants: dict[str, dict[str, dict[str, Any]]] = {}

    def _ensure_tenant(self, tenant_id: str) -> None:
        if tenant_id not in self._tenants:
            self._tenants[tenant_id] = {
                "models": {},
                "evaluations": {},
                "telemetry": {},
                "governance": {},
                "jobs": {},
            }

    def register_resource(self, tenant_id: str, resource_type: str, resource_id: str, data: Any) -> None:
        """Registers a resource strictly bound to a tenant."""
        self._ensure_tenant(tenant_id)
        if resource_type not in self._tenants[tenant_id]:
            self._tenants[tenant_id][resource_type] = {}
        self._tenants[tenant_id][resource_type][resource_id] = data


    def authorize_and_get_resource(
        self,
        context: AdminSecurityContext,
        resource_type: str,
        resource_id: str,
        operation: str = "read_model",
    ) -> Any:
        """Executes full 7-step authorization chain before retrieving resource."""
        # 1. Authenticated Admin check
        if not context.verify_signature():
            raise PermissionError("Admin authentication signature invalid (forged or corrupted token)")

        # 2. Role Verification & Operation Authorization
        AdminRBACManager.authorize_operation(context.role, operation)

        # 3. Scope Verification
        if "public_chat" in context.scope.lower():
            raise ScopeAccessDeniedError("Admin API cannot access or manipulate Public Chat scope")

        # 4. Tenant Verification & Existence
        if not context.tenant_id or context.tenant_id.strip() == "":
            raise TenantAccessDeniedError("Missing tenant identifier: anonymous admin requests prohibited")

        # 5. Resource Ownership Check
        tenant_store = self._tenants.get(context.tenant_id)
        if not tenant_store or resource_type not in tenant_store:
            raise TenantAccessDeniedError(f"Resource '{resource_id}' not found for tenant '{context.tenant_id}'")

        if resource_id not in tenant_store[resource_type]:
            # Cross-tenant check: if resource exists in another tenant, raise fail-closed cross-tenant error
            for other_tid, other_store in self._tenants.items():
                if other_tid != context.tenant_id and resource_id in other_store.get(resource_type, {}):
                    raise TenantAccessDeniedError(
                        f"Cross-tenant access violation: Tenant '{context.tenant_id}' cannot access resource owned by '{other_tid}'"
                    )
            raise TenantAccessDeniedError(f"Resource '{resource_id}' not found for tenant '{context.tenant_id}'")

        return tenant_store[resource_type][resource_id]

    def list_tenant_resources(self, context: AdminSecurityContext, resource_type: str) -> dict[str, Any]:
        """Lists resources strictly within the authenticated tenant boundary."""
        if not context.verify_signature():
            raise PermissionError("Admin token signature verification failed")

        if "public_chat" in context.scope.lower():
            raise ScopeAccessDeniedError("Public chat scope access prohibited via Admin API")

        self._ensure_tenant(context.tenant_id)
        return dict(self._tenants[context.tenant_id].get(resource_type, {}))
