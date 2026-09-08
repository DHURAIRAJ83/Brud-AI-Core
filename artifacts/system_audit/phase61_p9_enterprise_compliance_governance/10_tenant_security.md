# 10 TENANT SECURITY & DATA ISOLATION AUDIT

- Class: `TenantSecurityPolicyEngine` in `core_model/ops/tenant_security_policy_engine.py`.
- Access Boundary: `TENANT_A -> TENANT_A` = ALLOW, `TENANT_A -> TENANT_B` = DENY, `UNKNOWN_TENANT` = DENY.
