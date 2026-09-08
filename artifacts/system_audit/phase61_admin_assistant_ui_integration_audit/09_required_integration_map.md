# 09 REQUIRED INTEGRATION MAP FOR FUTURE WIRING

- **Phase 61 Canonical Backend Source**:
  - `core_model/training/signed_training_gate.py`
  - `core_model/eval/production_promotion_gate.py`
  - `core_model/eval/production_release_registry.py`
  - `core_model/eval/public_chat_admission_gate.py`
  - `core_model/ops/production_observability_safety_engine.py`
  - `core_model/ops/recovery_authorization_gate.py`
  - `core_model/ops/compliance_certification_gate.py`
  - `core_model/ops/enterprise_governance_contract.py`
  - `core_model/ops/policy_drift_evaluator.py`
  - `core_model/ops/secret_lifecycle_manager.py`
  - `core_model/ops/rbac_governance_engine.py`
  - `core_model/ops/tenant_security_policy_engine.py`

- **Required Backend Integration Layer**:
  - Expose a unified read-only endpoint (e.g. `GET /api/admin/assistant/governance-status` or expand `dashboard_overview()`) calling `EnterpriseGovernanceDashboardContract.get_enterprise_governance_summary()`.

- **Required Frontend Integration Layer**:
  - Add API contract in `apps/admin-dashboard/src/services/api.js`.
  - Update `AdminAssistantPage.jsx` and `AdminAssistantWidget.jsx` to render real P1–P10G governance readiness, token inventory, and activation blocker status cards.
