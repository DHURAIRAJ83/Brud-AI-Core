# 03 GOVERNANCE VISIBILITY MATRIX

| Canonical State Item | Backend Source | API Endpoint & Field | Frontend Component Field | Rendered UI Value | Consistency Result |
|---|---|---|---|---|---|
| 1. Canonical Components | P0-P10G Inventory | `activation_readiness.p0_p10g_canonical_components` | `govStatus.activation_readiness.p0_p10g_canonical_components` | `48/48 VERIFIED` | MATCH / VERIFIED |
| 2. Production State | Master Invariant | `activation_readiness.production_state` | `govStatus.activation_readiness.production_state` | `UNTOUCHED & LOCKED` | MATCH / VERIFIED |
| 3. Final Verdict | P10-G Audit Report | `activation_readiness.final_verdict` | `govStatus.activation_readiness.final_verdict` | `BLOCKED_PENDING_HUMAN_AUTHORIZATION` | MATCH / VERIFIED |
| 4. Training Authorization | SignedTrainingGateEngine | `governance.invariants.training_execution_authorized` | `govStatus.governance.invariants.training_execution_authorized` | `false` | MATCH / VERIFIED |
| 5. Optimizer Stepping | Training Engine | `governance.invariants.optimizer_stepping` | `govStatus.governance.invariants.optimizer_stepping` | `false` | MATCH / VERIFIED |
| 6. Tokenizer Mutation | Tokenizer Registry | `governance.invariants.tokenizer_mutation` | `govStatus.governance.invariants.tokenizer_mutation` | `false` | MATCH / VERIFIED |
| 7. Production Promotion | ProductionPromotionGate | `governance.invariants.production_promotion` | `govStatus.governance.invariants.production_promotion` | `BLOCKED` | MATCH / VERIFIED |
| 8. Public Chat Eligibility | PublicChatAdmissionGate | `governance.invariants.public_chat_eligible` | `govStatus.governance.invariants.public_chat_eligible` | `false` | MATCH / VERIFIED |
| 9. Candidate Traffic Share | CanaryDeploymentController | `governance.invariants.candidate_traffic_share` | `govStatus.governance.invariants.candidate_traffic_share` | `0.0` | MATCH / VERIFIED |
| 10. Recovery Status | RecoveryAuthorizationGate | `governance.invariants.recovery_executed` | `govStatus.governance.invariants.recovery_executed` | `false` | MATCH / VERIFIED |
| 11. Compliance Status | ComplianceCertificationGate | `governance.compliance.compliance_status` | `govStatus.governance.compliance.compliance_status` | `BLOCKED_PENDING_HUMAN_AUTHORIZATION` | MATCH / VERIFIED |
| 12. RBAC Integrity | RBACGovernanceEngine | `governance.rbac.rbac_integrity_passed` | `govStatus.governance.rbac.rbac_integrity_passed` | `PASSED` | MATCH / VERIFIED |
| 13. Tenant Isolation | TenantSecurityPolicyEngine | `governance.rbac.tenant_isolation_passed` | `govStatus.governance.rbac.tenant_isolation_passed` | `PASSED` | MATCH / VERIFIED |
| 14. Policy Drift Status | PolicyDriftEvaluator | `governance.rbac.policy_drift_status` | `govStatus.governance.rbac.policy_drift_status` | `NO_DRIFT` | MATCH / VERIFIED |
| 15. Active Secret Keys | SecretLifecycleManager | `governance.secrets.active_keys_count` | `govStatus.governance.secrets.active_keys_count` | `1` | MATCH / VERIFIED |
| 16. Revoked Secret Keys | SecretLifecycleManager | `governance.secrets.revoked_keys_count` | `govStatus.governance.secrets.revoked_keys_count` | `0` | MATCH / VERIFIED |
| 17. Assistant Authority | RBAC Role Lock | `admin_assistant_authority` | `govStatus.admin_assistant_authority` | `ADVISORY_ONLY` | MATCH / VERIFIED |
| 18. Activation Blockers | Authorization Token Inventory | `activation_readiness.activation_blockers` | `govStatus.activation_readiness.activation_blockers` | `4 Missing Human Tokens` | MATCH / VERIFIED |
