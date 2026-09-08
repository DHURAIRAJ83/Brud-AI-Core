# 06 UI / BACKEND CONTRACT AUDIT

- **Existing API Contracts** in [`apps/admin-dashboard/src/services/api.js`](file:///home/dhurai/Projects/brud-ai/apps/admin-dashboard/src/services/api.js): Wrappers for legacy assistant endpoints (`assistantOverview`, `assistantActions`, `assistantProposals`, `assistantPages`, `assistantHealth`, `assistantLanguagePreference`, `miniBrainWidgetHealth`).
- **Missing API Contracts for Phase 61**:
  - `get_signed_training_gate_status`
  - `get_promotion_gate_status`
  - `get_production_release_status`
  - `get_safety_observability_status`
  - `get_recovery_gate_status`
  - `get_enterprise_compliance_status`
  - `get_activation_readiness_status`
  - `get_authorization_token_inventory`
  - `get_final_activation_blockers`
