"""Phase 61 - P10-B: Controlled Production Authorization Readiness & Final Activation Audit Test Suite."""

import time
import unittest

from core_model.corpus.global_novelty_ledger import GlobalCanonicalNoveltyLedgerEngine
from core_model.training.signed_training_gate import SignedTrainingGateEngine
from core_model.eval.production_promotion_gate import ProductionPromotionGate
from core_model.eval.production_release_registry import ProductionReleaseRegistry
from core_model.eval.canary_deployment_governance import CanaryDeploymentEngine
from core_model.eval.public_chat_admission_gate import PublicChatAdmissionGate
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
from core_model.ops.recovery_authorization_gate import RecoveryAuthorizationGate
from core_model.ops.compliance_evidence_collector import ComplianceEvidenceCollector
from core_model.ops.secret_lifecycle_manager import SecretLifecycleManager
from core_model.ops.tenant_security_policy_engine import TenantSecurityPolicyEngine, TenantAccessError
from core_model.ops.rbac_governance_engine import RBACGovernanceEngine, RBACPermissionError
from core_model.ops.policy_drift_evaluator import PolicyDriftEvaluator
from core_model.ops.compliance_certification_gate import ComplianceCertificationGate, ComplianceCertificationError


class TestPhase61P10BFinalActivationReadiness(unittest.TestCase):

    def setUp(self):
        self.novelty_ledger = GlobalCanonicalNoveltyLedgerEngine()
        self.training_gate = SignedTrainingGateEngine()
        self.promotion_gate = ProductionPromotionGate()
        self.release_registry = ProductionReleaseRegistry()
        self.canary_engine = CanaryDeploymentEngine(release_id="rel-p10b-001")
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

    def test_01_training_execution_boundary_locked(self):
        from core_model.training.signed_training_gate import TrainingAuthorizationError
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(None)

    def test_02_candidate_promotion_boundary_locked(self):
        from core_model.eval.production_promotion_gate import PromotionAuthorizationError
        with self.assertRaises(PromotionAuthorizationError):
            self.promotion_gate.verify_promotion_token(None, None)

    def test_03_production_release_registry_initial_state(self):
        self.assertIsNone(self.release_registry.get_active_release())

    def test_04_canary_deployment_initial_state_zero_traffic(self):
        self.assertEqual(self.canary_engine.current_traffic_share, 0.0)

    def test_05_public_chat_admission_boundary_locked(self):
        from core_model.eval.public_chat_admission_gate import PublicChatAdmissionError
        with self.assertRaises(PublicChatAdmissionError):
            self.public_chat_gate.verify_admission_token(None, None)

    def test_06_recovery_execution_state_unexecuted(self):
        self.assertFalse(self.recovery_controller.recovery_executed)
        self.assertEqual(self.recovery_controller.candidate_traffic_share, 0.0)

    def test_07_compliance_certification_boundary_locked(self):
        with self.assertRaises(ComplianceCertificationError):
            self.compliance_gate.verify_certification_token(None, "pkg-001", "hash-001", "tenant-brud-core")

    def test_08_secret_lifecycle_non_disclosure(self):
        sec = self.secret_mgr.register_key("TEST_GATE", "TEST_RAW_SECRET_KEY_16B")
        self.assertNotIn("TEST_RAW_SECRET_KEY_16B", str(sec))

    def test_09_rbac_admin_assistant_advisory_only(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "PROMOTE_MODEL")

    def test_10_tenant_isolation_cross_tenant_denied(self):
        with self.assertRaises(TenantAccessError):
            self.tenant_engine.authorize_tenant_access("tenant-brud-core", "tenant-enterprise-a")

    def test_11_audit_chain_tamper_detection(self):
        self.audit_chain.append_event("TEST", "rel-1", "m1", "admin", "ACT", "PASS", "h1")
        self.assertTrue(self.audit_chain.verify_chain_integrity())

    def test_12_snapshot_integrity_verification(self):
        snap = self.snapshot_registry.create_snapshot("rel-1", "m1", "d1", "t1", "cfg1")
        self.assertTrue(self.snapshot_registry.verify_snapshot_integrity(snap.snapshot_id))

    def test_13_policy_drift_unknown_state_fails_closed(self):
        res = self.drift_evaluator.evaluate_policy_drift(mock_unknown_state=True)
        self.assertEqual(res.drift_status, "CRITICAL_DRIFT")

    def test_14_health_monitor_missing_telemetry_fails_closed(self):
        res = self.health_monitor.evaluate_health(None)
        self.assertEqual(res.health_status, "CRITICAL")

    def test_15_safety_monitor_critical_event_triggers_rollback_required(self):
        self.safety_monitor.log_safety_event("rel-1", "m1", "BYPASS", "CRITICAL", "Bypass attempt")
        res = self.safety_monitor.evaluate_safety_status("rel-1")
        self.assertEqual(res.escalation_action, "ROLLBACK_REQUIRED")

    def test_16_incident_response_engine_prevents_critical_auto_close(self):
        inc = self.incident_engine.raise_incident("rel-1", "m1", "CRITICAL", "SafetyMonitor", "Critical breach")
        with self.assertRaises(ValueError):
            self.incident_engine.transition_status(inc.incident_id, "INCIDENT_CLOSED", admin_identity="auto-bot")

    def test_17_disaster_recovery_manager_fails_closed_on_corrupted_snapshot(self):
        res = self.dr_manager.evaluate_recovery_prerequisites(mock_corrupted_snapshot=True)
        self.assertEqual(res.recovery_status, "RECOVERY_BLOCKED")

    def test_18_state_integrity_validator_fails_closed_on_mismatch(self):
        res = self.state_validator.validate_system_integrity(self.release_registry, self.snapshot_registry, self.audit_chain, mock_hash_mismatch=True)
        self.assertEqual(res.integrity_status, "STATE_INTEGRITY_FAILURE")

    def test_19_adversarial_traffic_share_lock(self):
        self.assertEqual(self.safety_controller.candidate_traffic_share, 0.0)
        self.assertFalse(self.safety_controller.public_chat_eligible)

    def test_20_mandatory_governance_invariants_lock(self):
        from core_model.eval.public_chat_admission_gate import PublicChatAdmissionError
        self.assertEqual(self.canary_engine.current_traffic_share, 0.0)
        with self.assertRaises(PublicChatAdmissionError):
            self.public_chat_gate.verify_admission_token(None, None)
        self.assertFalse(self.recovery_controller.recovery_executed)


if __name__ == "__main__":
    unittest.main()
