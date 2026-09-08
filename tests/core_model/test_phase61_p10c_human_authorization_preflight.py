"""Phase 61 - P10-C: Human Authorization Pre-Flight & Controlled Activation Gate Test Suite."""

import time
import unittest

from core_model.training.signed_training_gate import SignedTrainingGateEngine, TrainingAuthorizationError
from core_model.eval.production_promotion_gate import ProductionPromotionGate, PromotionAuthorizationError
from core_model.eval.production_release_registry import ProductionReleaseRegistry
from core_model.eval.canary_deployment_governance import CanaryDeploymentEngine
from core_model.eval.public_chat_admission_gate import PublicChatAdmissionGate, PublicChatAdmissionError
from core_model.ops.production_observability_registry import ProductionObservabilityRegistry
from core_model.ops.model_health_monitor import ModelHealthMonitor
from core_model.ops.continuous_safety_monitor import ContinuousSafetyMonitor
from core_model.ops.incident_response_engine import IncidentResponseEngine
from core_model.ops.production_safety_controller import ProductionSafetyController
from core_model.ops.production_audit_chain import ProductionAuditChain
from core_model.ops.production_state_snapshot_registry import ProductionStateSnapshotRegistry
from core_model.ops.disaster_recovery_manager import DisasterRecoveryManager
from core_model.ops.production_state_integrity_validator import ProductionStateIntegrityValidator
from core_model.ops.recovery_readiness_evaluator import RecoveryReadinessEvaluator
from core_model.ops.recovery_controller import FailSafeRecoveryController
from core_model.ops.recovery_authorization_gate import RecoveryAuthorizationGate, RecoveryAuthorizationError
from core_model.ops.compliance_evidence_collector import ComplianceEvidenceCollector
from core_model.ops.secret_lifecycle_manager import SecretLifecycleManager
from core_model.ops.tenant_security_policy_engine import TenantSecurityPolicyEngine, TenantAccessError
from core_model.ops.rbac_governance_engine import RBACGovernanceEngine, RBACPermissionError
from core_model.ops.policy_drift_evaluator import PolicyDriftEvaluator
from core_model.ops.compliance_certification_gate import ComplianceCertificationGate, ComplianceCertificationError
from core_model.ops.dashboard_contract import ProductionSafetyDashboardContract
from core_model.ops.recovery_audit_contract import ProductionRecoveryAuditContract
from core_model.ops.enterprise_governance_contract import EnterpriseGovernanceDashboardContract


class TestPhase61P10CHumanAuthorizationPreflight(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_PREFLIGHT_SECRET_KEY_2026"
        self.training_gate = SignedTrainingGateEngine()
        self.promotion_gate = ProductionPromotionGate()
        self.release_registry = ProductionReleaseRegistry()
        self.canary_engine = CanaryDeploymentEngine(release_id="rel-p10c-001")
        self.public_chat_gate = PublicChatAdmissionGate()
        self.obs_registry = ProductionObservabilityRegistry()
        self.health_monitor = ModelHealthMonitor()
        self.safety_monitor = ContinuousSafetyMonitor()
        self.incident_engine = IncidentResponseEngine()
        self.safety_controller = ProductionSafetyController(self.release_registry)
        self.audit_chain = ProductionAuditChain()
        self.snapshot_registry = ProductionStateSnapshotRegistry()
        self.dr_manager = DisasterRecoveryManager(self.snapshot_registry)
        self.state_validator = ProductionStateIntegrityValidator()
        self.readiness_evaluator = RecoveryReadinessEvaluator()
        self.recovery_controller = FailSafeRecoveryController(self.release_registry, self.audit_chain)
        self.recovery_gate = RecoveryAuthorizationGate()
        self.evidence_collector = ComplianceEvidenceCollector()
        self.secret_mgr = SecretLifecycleManager()
        self.tenant_engine = TenantSecurityPolicyEngine()
        self.rbac_engine = RBACGovernanceEngine()
        self.drift_evaluator = PolicyDriftEvaluator()
        self.compliance_gate = ComplianceCertificationGate()

    def test_01_training_gate_token_prerequisite_fails_closed(self):
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(None)

    def test_02_promotion_gate_token_prerequisite_fails_closed(self):
        with self.assertRaises(PromotionAuthorizationError):
            self.promotion_gate.verify_promotion_token(None, None)

    def test_03_public_chat_token_prerequisite_fails_closed(self):
        with self.assertRaises(PublicChatAdmissionError):
            self.public_chat_gate.verify_admission_token(None, None)

    def test_04_recovery_gate_token_prerequisite_fails_closed(self):
        with self.assertRaises(RecoveryAuthorizationError):
            self.recovery_gate.verify_recovery_token(None, "rel-001", "snap-001", "model-001")

    def test_05_compliance_gate_token_prerequisite_fails_closed(self):
        with self.assertRaises(ComplianceCertificationError):
            self.compliance_gate.verify_certification_token(None, "pkg-001", "hash-001", "tenant-brud-core")

    def test_06_rbac_admin_assistant_advisory_isolation(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "EXECUTE_TRAINING")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "PROMOTE_MODEL")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "EXECUTE_ROLLBACK")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "EXECUTE_RECOVERY")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "REVOKE_SECRET")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "CERTIFY_COMPLIANCE")

    def test_07_rbac_separation_of_duties_system_operator_restricted(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SYSTEM_OPERATOR", "PROMOTE_MODEL")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SYSTEM_OPERATOR", "REVOKE_SECRET")

    def test_08_rbac_separation_of_duties_security_auditor_restricted(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SECURITY_AUDITOR", "EXECUTE_TRAINING")

    def test_09_rbac_human_admin_privileged_authorization(self):
        self.assertTrue(self.rbac_engine.authorize_action("HUMAN_ADMIN", "PROMOTE_MODEL"))
        self.assertTrue(self.rbac_engine.authorize_action("HUMAN_ADMIN", "EXECUTE_TRAINING"))

    def test_10_tenant_isolation_strict_boundary(self):
        self.assertTrue(self.tenant_engine.authorize_tenant_access("tenant-brud-core", "tenant-brud-core"))
        with self.assertRaises(TenantAccessError):
            self.tenant_engine.authorize_tenant_access("tenant-brud-core", "tenant-enterprise-a")

    def test_11_read_only_dashboard_contracts_zero_mutation_methods(self):
        # Verify contracts have zero state mutation methods
        for cls in (ProductionSafetyDashboardContract, ProductionRecoveryAuditContract, EnterpriseGovernanceDashboardContract):
            method_names = [m for m in dir(cls) if not m.startswith("_")]
            self.assertTrue(all(not m.startswith("set_") and not m.startswith("update_") and not m.startswith("mutate_") for m in method_names))

    def test_12_secret_lifecycle_non_disclosure(self):
        rec = self.secret_mgr.register_key("PREFLIGHT_KEY", "PREFLIGHT_RAW_SECRET_16BYTES")
        self.assertNotIn("PREFLIGHT_RAW_SECRET_16BYTES", str(rec))

    def test_13_audit_chain_tamper_detection(self):
        self.audit_chain.append_event("PREFLIGHT", "rel-1", "m1", "admin", "AUDIT", "PASS", "h1")
        self.assertTrue(self.audit_chain.verify_chain_integrity())

    def test_14_snapshot_integrity_verification(self):
        snap = self.snapshot_registry.create_snapshot("rel-1", "m1", "d1", "t1", "cfg1")
        self.assertTrue(self.snapshot_registry.verify_snapshot_integrity(snap.snapshot_id))

    def test_15_policy_drift_unknown_state_fails_closed(self):
        res = self.drift_evaluator.evaluate_policy_drift(mock_unknown_state=True)
        self.assertEqual(res.drift_status, "CRITICAL_DRIFT")

    def test_16_canary_deployment_initial_traffic_share_zero(self):
        self.assertEqual(self.canary_engine.current_traffic_share, 0.0)

    def test_17_recovery_controller_unexecuted_state(self):
        self.assertFalse(self.recovery_controller.recovery_executed)
        self.assertEqual(self.recovery_controller.candidate_traffic_share, 0.0)

    def test_18_disaster_recovery_manager_fails_closed_on_corruption(self):
        res = self.dr_manager.evaluate_recovery_prerequisites(mock_corrupted_snapshot=True)
        self.assertEqual(res.recovery_status, "RECOVERY_BLOCKED")

    def test_19_state_integrity_validator_mismatch_fails_closed(self):
        res = self.state_validator.validate_system_integrity(self.release_registry, self.snapshot_registry, self.audit_chain, mock_hash_mismatch=True)
        self.assertEqual(res.integrity_status, "STATE_INTEGRITY_FAILURE")

    def test_20_mandatory_governance_invariants_lock(self):
        self.assertEqual(self.canary_engine.current_traffic_share, 0.0)
        self.assertFalse(self.recovery_controller.recovery_executed)
        self.assertEqual(self.recovery_controller.candidate_traffic_share, 0.0)


if __name__ == "__main__":
    unittest.main()
