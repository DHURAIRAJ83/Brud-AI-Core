# 12 GOVERNANCE INTEGRATION AUDIT

- Backend Engine: 48 canonical components in `core_model/ops/`, `core_model/eval/`, `core_model/training/`.
- Endpoint: `GET /api/admin/assistant/governance-status` (`EnterpriseGovernanceDashboardContract`).
- Admin Assistant Page: Renders live status cards, invariant grids, and activation blockers (`END_TO_END_CONNECTED`).
- Authority Lock: `ADMIN_ASSISTANT_AUTHORITY = ADVISORY_ONLY` (100% Fail-Closed Enforced).
