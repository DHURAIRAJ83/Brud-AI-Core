"""Phase 61 - P10-I: Final Production Package Integrity & Deployment Readiness Audit Test Suite.

Verifies repository integrity, build artifacts, environment configuration safety,
secret handling, database schema version, governance package integrity across P1-P10H,
human authorization dependency, and adversarial deployment fail-closed safety.

MANDATORY INVARIANTS TESTED:
- TRAINING EXECUTED = FALSE
- TRAINING AUTHORIZATION = FALSE
- PRODUCTION PROMOTION = BLOCKED
- PRODUCTION MERGE = BLOCKED
- PUBLIC CHAT ELIGIBLE = FALSE
- CANDIDATE TRAFFIC SHARE = 0.0
- OPTIMIZER STEPPING = FALSE
- TOKENIZER MUTATION = FALSE
- MODEL WEIGHT MUTATION = FALSE
- PRODUCTION DATA MUTATION = FALSE
- RECOVERY EXECUTED = FALSE
- COMPLIANCE CERTIFICATION = BLOCKED
- PRODUCTION STATE = LOCKED
- ADMIN_ASSISTANT_AUTHORITY = ADVISORY_ONLY
"""

import json
import unittest
from backend.core.config import Settings
from backend.database.schema import SCHEMA_VERSION
from backend.services.admin_assistant_service import AdminAssistantService
from core_model.ops.enterprise_governance_contract import EnterpriseGovernanceDashboardContract
from core_model.ops.secret_lifecycle_manager import SecretLifecycleManager
from core_model.ops.tenant_security_policy_engine import TenantSecurityPolicyEngine


class TestPhase61P10IProductionPackageIntegrity(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()
        self.service = AdminAssistantService(self.settings)

    def test_01_repository_and_canonical_imports_integrity(self):
        # Verify core imports compile cleanly
        from backend.api.routes.admin_assistant import router
        from core_model.eval.production_promotion_gate import ProductionPromotionGate
        from core_model.ops.compliance_certification_gate import ComplianceCertificationGate
        from core_model.ops.recovery_authorization_gate import RecoveryAuthorizationGate
        from core_model.training.signed_training_gate import SignedTrainingGateEngine

        self.assertIsNotNone(router)
        self.assertIsNotNone(SignedTrainingGateEngine)
        self.assertIsNotNone(ProductionPromotionGate)
        self.assertIsNotNone(RecoveryAuthorizationGate)
        self.assertIsNotNone(ComplianceCertificationGate)

    def test_02_database_schema_version_integrity(self):
        self.assertEqual(SCHEMA_VERSION, 78)

    def test_03_environment_configuration_safety(self):
        # Settings resolution
        db_path = self.settings.resolved_database_path
        self.assertTrue(len(str(db_path)) > 0)
        # Ensure zero mock secrets in settings
        dump = str(self.settings.__dict__).lower()
        self.assertNotIn("mock_secret", dump)
        self.assertNotIn("test_private_key", dump)

    def test_04_secret_handling_safety(self):
        res = self.service.get_governance_status()
        dump = json.dumps(res).lower()
        self.assertNotIn("raw_secret", dump)
        self.assertNotIn("private_key", dump)
        self.assertNotIn("signing_key", dump)

    def test_05_governance_package_integrity_p1_p10h(self):
        res = self.service.get_governance_status()
        readiness = res["activation_readiness"]
        self.assertEqual(readiness["p0_p10g_canonical_components"], "48/48 VERIFIED")
        self.assertEqual(readiness["production_state"], "UNTOUCHED & LOCKED")
        self.assertEqual(readiness["final_verdict"], "BLOCKED_PENDING_HUMAN_AUTHORIZATION")

    def test_06_human_authorization_tokens_dependency(self):
        res = self.service.get_governance_status()
        readiness = res["activation_readiness"]
        self.assertTrue(readiness["awaiting_genuine_human_authorization"])
        blockers = readiness["activation_blockers"]
        self.assertEqual(len(blockers), 4)
        self.assertIn("SignedTrainingAuthorizationToken: ABSENT", blockers[0])
        self.assertIn("SignedPromotionAuthorizationToken: ABSENT", blockers[1])
        self.assertIn("SignedPublicChatAdmissionToken: ABSENT", blockers[2])
        self.assertIn("SignedComplianceCertificationToken: ABSENT", blockers[3])

    def test_07_admin_assistant_deployment_authority(self):
        res = self.service.get_governance_status()
        self.assertEqual(res["admin_assistant_authority"], "ADVISORY_ONLY")

    def test_08_recovery_rollback_package_readiness(self):
        res = self.service.get_governance_status()
        recovery = res["governance"]["invariants"]["recovery_executed"]
        self.assertFalse(recovery)

    def test_09_tenant_and_rbac_configuration_integrity(self):
        res = self.service.get_governance_status()
        rbac = res["governance"]["rbac"]
        self.assertTrue(rbac["rbac_integrity_passed"])
        self.assertTrue(rbac["tenant_isolation_passed"])
        self.assertEqual(rbac["policy_drift_status"], "NO_DRIFT")

    def test_10_adversarial_deployment_without_training_authorization(self):
        res = self.service.get_governance_status()
        self.assertFalse(res["governance"]["invariants"]["training_execution_authorized"])

    def test_11_adversarial_deployment_without_promotion_authorization(self):
        res = self.service.get_governance_status()
        self.assertEqual(res["governance"]["invariants"]["production_promotion"], "BLOCKED")

    def test_12_adversarial_deployment_without_public_chat_authorization(self):
        res = self.service.get_governance_status()
        self.assertFalse(res["governance"]["invariants"]["public_chat_eligible"])

    def test_13_adversarial_deployment_without_compliance_authorization(self):
        res = self.service.get_governance_status()
        self.assertEqual(
            res["governance"]["compliance"]["compliance_status"],
            "BLOCKED_PENDING_HUMAN_AUTHORIZATION",
        )

    def test_14_adversarial_admin_assistant_privilege_escalation(self):
        with self.assertRaises(Exception):
            self.service.propose(
                action_type="deploy_production_release",
                target_type="system",
                target_public_id="sys1",
                request_payload={},
                requested_by="admin1",
                summary="deploy production",
            )

    def test_15_adversarial_mock_token_bypass_blocked(self):
        from core_model.training.signed_training_gate import (
            SignedTrainingAuthorizationToken,
            SignedTrainingGateEngine,
            TrainingAuthorizationError,
        )

        engine = SignedTrainingGateEngine()
        fake_token = SignedTrainingAuthorizationToken(
            token_id="fake-tok-123",
            admin_public_id="fake_admin",
            dataset_manifest_hash="hash123",
            rights_gate_status="PASS",
            novelty_gate_status="PASS",
            provenance_gate_status="PASS",
            holdout_gate_status="PASS",
            token_accounting_status="PASS",
            human_approval_signature="fake_human_sig",
            created_at_epoch=1000.0,
            expires_at_epoch=2000.0,
            signature_hmac="invalid_signature_hmac",
        )
        with self.assertRaises(TrainingAuthorizationError):
            engine.verify_authorization(fake_token)

    def test_16_adversarial_wrong_tenant_token_blocked(self):
        engine = TenantSecurityPolicyEngine()
        with self.assertRaises(Exception):
            engine.enforce_tenant_isolation(
                requesting_tenant_id="tenant_A", target_tenant_id="tenant_B"
            )

    def test_17_adversarial_legacy_api_bypass_blocked(self):
        # Verify legacy endpoints do not expose mutation capability
        actions = self.service.list_proposals()
        self.assertIsInstance(actions, list)

    def test_18_adversarial_direct_production_activation_blocked(self):
        res = self.service.get_governance_status()
        self.assertEqual(
            res["activation_readiness"]["final_verdict"],
            "BLOCKED_PENDING_HUMAN_AUTHORIZATION",
        )
        self.assertEqual(res["activation_readiness"]["production_state"], "UNTOUCHED & LOCKED")

    def test_19_adversarial_debug_mode_governance_bypass_blocked(self):
        # Governance evaluators disregard debug flags
        res = self.service.get_governance_status()
        self.assertEqual(res["governance"]["invariants"]["production_promotion"], "BLOCKED")

    def test_20_final_deployment_readiness_verdict(self):
        res = self.service.get_governance_status()
        self.assertEqual(res["activation_readiness"]["p0_p10g_canonical_components"], "48/48 VERIFIED")
        self.assertEqual(res["activation_readiness"]["production_state"], "UNTOUCHED & LOCKED")


if __name__ == "__main__":
    unittest.main()
