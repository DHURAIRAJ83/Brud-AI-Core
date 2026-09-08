# 02 BACKEND INTEGRATION REPORT

- **Endpoint**: `GET /api/admin/assistant/governance-status`
- **Controller**: `governance_status()` in [`backend/api/routes/admin_assistant.py`](file:///home/dhurai/Projects/brud-ai/backend/api/routes/admin_assistant.py)
- **Service Handler**: `AdminAssistantService.get_governance_status()` in [`backend/services/admin_assistant_service.py`](file:///home/dhurai/Projects/brud-ai/backend/services/admin_assistant_service.py)
- **Canonical Contracts Consumed**:
  - `EnterpriseGovernanceDashboardContract`
  - `ComplianceStatusView`
  - `SecretGovernanceView`
  - `RBACIsolationView`
  - `GovernanceInvariantsView`
  - `PolicyDriftEvaluator`
  - `SecretLifecycleManager`
- **Zero Raw Secrets Disclosed**: Key counts, rotation status, and policy drift states exposed only. Raw secret material, HMAC keys, and private signing keys are never serialized.
