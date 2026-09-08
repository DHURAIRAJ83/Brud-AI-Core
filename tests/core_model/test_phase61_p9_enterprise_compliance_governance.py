"""Phase 61 - P9: Enterprise Compliance Evidence, Secret Governance & Policy Test Suite."""

import time
import unittest

from core_model.ops.compliance_evidence_collector import (
    ComplianceError,
    ComplianceEvidenceCollector,
    ComplianceEvidencePackage,
)
from core_model.ops.secret_lifecycle_manager import (
    SecretLifecycleError,
    SecretLifecycleManager,
    SecretMetadataRecord,
)
from core_model.ops.tenant_security_policy_engine import (
    TenantAccessError,
    TenantSecurityPolicyEngine,
)
from core_model.ops.compliance_audit_generator import (
    ComplianceAuditGenerator,
    ComplianceAuditReport,
)
from core_model.ops.rbac_governance_engine import (
    RBACGovernanceEngine,
    RBACPermissionError,
)
from core_model.ops.policy_drift_evaluator import (
    PolicyDriftEvaluationResult,
    PolicyDriftEvaluator,
)
from core_model.ops.compliance_certification_gate import (
    ComplianceCertificationError,
    ComplianceCertificationGate,
    SignedComplianceCertificationToken,
    compute_compliance_token_signature,
)
from core_model.ops.enterprise_governance_contract import (
    ComplianceStatusView,
    EnterpriseGovernanceDashboardContract,
    GovernanceInvariantsView,
    RBACIsolationView,
    SecretGovernanceView,
)
from core_model.admin_assistant.admin_review_queue import AdminReviewQueueManager


class TestPhase61P9EnterpriseComplianceGovernance(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_COMPLIANCE_SECRET_KEY_2026"
        self.collector = ComplianceEvidenceCollector()
        self.secret_mgr = SecretLifecycleManager()
        self.tenant_engine = TenantSecurityPolicyEngine()
        self.audit_gen = ComplianceAuditGenerator()
        self.rbac_engine = RBACGovernanceEngine()
        self.drift_eval = PolicyDriftEvaluator()
        self.cert_gate = ComplianceCertificationGate(secret_key=self.secret_key)
        self.admin_review = AdminReviewQueueManager()

    def test_01_evidence_package_generation_success(self):
        pkg = self.collector.collect_evidence(
            release_id="rel-p9-001",
            dataset_hash="dataset-sha256-111",
            model_hash="model-sha256-222",
            tokenizer_hash="tokenizer-sha256-333"
        )
        self.assertEqual(pkg.release_id, "rel-p9-001")
        self.assertTrue(pkg.audit_chain_continuous)

    def test_02_missing_evidence_fails_closed(self):
        with self.assertRaises(ComplianceError):
            self.collector.collect_evidence(
                release_id="", dataset_hash="", model_hash="", tokenizer_hash="", mock_missing_evidence=True
            )

    def test_03_secret_key_registration_and_versioning(self):
        rec = self.secret_mgr.register_key("TRAINING_GATE", "RAW_SECRET_KEY_STRING_16BYTES")
        self.assertEqual(rec.key_purpose, "TRAINING_GATE")
        self.assertEqual(rec.version, 1)
        self.assertEqual(rec.status, "ACTIVE")

    def test_04_secret_key_rotation_workflow(self):
        self.secret_mgr.register_key("PROMOTION_GATE", "OLD_PROMOTION_SECRET_KEY_16B")
        new_rec = self.secret_mgr.rotate_key("PROMOTION_GATE", "NEW_PROMOTION_SECRET_KEY_16B")

        self.assertEqual(new_rec.version, 2)
        self.assertEqual(new_rec.status, "ACTIVE")
        k_id, act_sec = self.secret_mgr.get_active_secret("PROMOTION_GATE")
        self.assertEqual(act_sec, "NEW_PROMOTION_SECRET_KEY_16B")

    def test_05_revoked_secret_key_fails_closed(self):
        rec = self.secret_mgr.register_key("RECOVERY_GATE", "RECOVERY_SECRET_KEY_16BYTES")
        self.secret_mgr.revoke_key(rec.key_id)

        with self.assertRaises(SecretLifecycleError):
            self.secret_mgr.get_historical_secret(rec.key_id)

    def test_06_raw_secret_non_disclosure_in_metadata(self):
        rec = self.secret_mgr.register_key("SNAPSHOT_HMAC", "SNAPSHOT_SECRET_KEY_16BYTES")
        self.assertNotIn("SNAPSHOT_SECRET_KEY_16BYTES", str(rec))
        self.assertTrue(len(rec.fingerprint) > 0)

    def test_07_tenant_isolation_allow_same_tenant(self):
        self.assertTrue(
            self.tenant_engine.authorize_tenant_access("tenant-brud-core", "tenant-brud-core")
        )

    def test_08_tenant_isolation_deny_cross_tenant(self):
        with self.assertRaises(TenantAccessError) as ctx:
            self.tenant_engine.authorize_tenant_access("tenant-brud-core", "tenant-enterprise-a")
        self.assertIn("Cross-tenant access forbidden", str(ctx.exception))

    def test_09_tenant_isolation_deny_unknown_tenant(self):
        with self.assertRaises(TenantAccessError):
            self.tenant_engine.authorize_tenant_access("tenant-rogue", "tenant-brud-core")

    def test_10_deterministic_compliance_audit_report_generation(self):
        pkg = self.collector.collect_evidence("rel-p9-001", "d1", "m1", "t1")
        rpt = self.audit_gen.generate_report(pkg)
        self.assertEqual(rpt.overall_compliance_status, "COMPLIANT")
        self.assertEqual(len(rpt.missing_evidence_categories), 0)

    def test_11_compliance_audit_report_identifies_missing_evidence(self):
        pkg = self.collector.collect_evidence("rel-p9-001", "d1", "m1", "t1", licensing_policy_passed=False)
        rpt = self.audit_gen.generate_report(pkg)
        self.assertEqual(rpt.overall_compliance_status, "NON_COMPLIANT")
        self.assertIn("LICENSING", rpt.missing_evidence_categories)

    def test_12_rbac_human_admin_privileged_action_authorized(self):
        self.assertTrue(self.rbac_engine.authorize_action("HUMAN_ADMIN", "PROMOTE_MODEL"))

    def test_13_rbac_admin_assistant_advisory_privileged_action_denied(self):
        with self.assertRaises(RBACPermissionError) as ctx:
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "PROMOTE_MODEL")
        self.assertIn("ADVISORY ONLY", str(ctx.exception))

    def test_14_rbac_unauthorized_role_privilege_escalation_denied(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SYSTEM_OPERATOR", "REVOKE_SECRET")

    def test_15_enterprise_policy_drift_evaluator(self):
        res = self.drift_eval.evaluate_policy_drift(rbac_drift=True)
        self.assertEqual(res.drift_status, "CRITICAL_DRIFT")
        self.assertTrue(res.escalation_required)

    def test_16_policy_drift_unknown_state_fails_closed(self):
        res = self.drift_eval.evaluate_policy_drift(mock_unknown_state=True)
        self.assertEqual(res.drift_status, "CRITICAL_DRIFT")
        self.assertIn("Unknown policy evaluation state", res.reasons[0])

    def test_17_compliance_certification_token_verification_success(self):
        pkg = self.collector.collect_evidence("rel-p9-001", "d1", "m1", "t1")
        req_id = "req-cert-001"
        tenant_id = "tenant-brud-core"
        admin_id = "admin-dhurai"

        sig = compute_compliance_token_signature(req_id, pkg.package_id, pkg.package_hash, tenant_id, admin_id, self.secret_key)
        token = SignedComplianceCertificationToken(
            certification_request_id=req_id,
            package_id=pkg.package_id,
            package_hash=pkg.package_hash,
            tenant_id=tenant_id,
            admin_public_id=admin_id,
            admin_role="HUMAN_ADMIN",
            policy_version="p9-v1.0",
            created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )
        self.assertTrue(self.cert_gate.verify_certification_token(token, pkg.package_id, pkg.package_hash, tenant_id))

    def test_18_compliance_certification_token_admin_assistant_role_rejected(self):
        pkg = self.collector.collect_evidence("rel-p9-001", "d1", "m1", "t1")
        token = SignedComplianceCertificationToken(
            certification_request_id="req-1", package_id=pkg.package_id, package_hash=pkg.package_hash,
            tenant_id="tenant-brud-core", admin_public_id="bot", admin_role="ADMIN_ASSISTANT_ADVISORY",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac="sig"
        )
        with self.assertRaises(ComplianceCertificationError) as ctx:
            self.cert_gate.verify_certification_token(token, pkg.package_id, pkg.package_hash, "tenant-brud-core")
        self.assertIn("advisory only", str(ctx.exception).lower())

    def test_19_admin_review_queue_extension_supports_compliance_decisions(self):
        rec = self.admin_review.record_admin_decision("rev-cmp-001", "COMPLIANCE_APPROVED")
        self.assertEqual(rec.decision, "COMPLIANCE_APPROVED")

    def test_20_enterprise_governance_contract_read_only_and_invariants(self):
        contract = EnterpriseGovernanceDashboardContract(
            compliance=ComplianceStatusView("COMPLIANT", 1, 0),
            secrets=SecretGovernanceView(1, 0, 0.0),
            rbac=RBACIsolationView(True, True, "NO_DRIFT"),
            invariants=GovernanceInvariantsView(),
            contract_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        self.assertEqual(contract.invariants.candidate_traffic_share, 0.0)
        self.assertFalse(contract.invariants.public_chat_eligible)
        self.assertFalse(contract.invariants.recovery_executed)


if __name__ == "__main__":
    unittest.main()
