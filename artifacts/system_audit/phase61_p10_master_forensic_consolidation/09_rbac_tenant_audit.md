# 09 RBAC & TENANT ISOLATION AUDIT

- Roles: `HUMAN_ADMIN`, `LEGAL_OFFICER`, `SECURITY_AUDITOR`, `SYSTEM_OPERATOR`, `ADMIN_ASSISTANT_ADVISORY`.
- Role Boundary: `ADMIN_ASSISTANT_ADVISORY` is strictly advisory only. 0 direct execution paths exist.
- Tenant Isolation: Cross-tenant data access strictly prohibited (`TENANT_A -> TENANT_B = DENY`).
