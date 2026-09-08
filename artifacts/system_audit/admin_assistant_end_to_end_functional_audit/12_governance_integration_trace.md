# 12 GOVERNANCE INTEGRATION TRACE

- Backend Contracts: 48 canonical components in `core_model/ops/`, `core_model/eval/`, `core_model/training/`.
- Endpoint: `GET /api/admin/assistant/governance-status` exposes `EnterpriseGovernanceDashboardContract`.
- Admin Assistant Page: Renders real-time governance status cards, invariants grid, and final activation blockers (`END_TO_END_CONNECTED`).
- Authority Boundary: `ADMIN_ASSISTANT_AUTHORITY = ADVISORY_ONLY` strictly enforced. Proposal creation for mutating action types is fail-closed blocked (`END_TO_END_CONNECTED`).
