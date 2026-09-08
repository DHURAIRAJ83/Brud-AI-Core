# 09 TENANT BINDING AUDIT

- Multi-Tenant Isolation: `TenantSecurityPolicyEngine`.
- Rules: `TENANT_A -> TENANT_A` = ALLOW, `TENANT_A -> TENANT_B` = DENY, `UNKNOWN_TENANT` = DENY.
