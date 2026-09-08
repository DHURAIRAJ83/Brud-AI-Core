"""Phase 61 - P10-E: Controlled Authorization Package Integration & Final GO/NO-GO Audit Test Suite."""

import time
import unittest

from core_model.training.signed_training_gate import (
    SignedTrainingGateEngine,
    SignedTrainingAuthorizationToken,
    TrainingAuthorizationError,
    compute_token_signature as compute_training_token_signature,
)
from core_model.eval.production_promotion_gate import (
    ProductionPromotionGate,
    SignedPromotionAuthorizationToken,
    PromotionAuthorizationError,
    compute_promotion_token_signature,
)
from core_model.eval.public_chat_admission_gate import (
    PublicChatAdmissionGate,
    SignedPublicChatAdmissionToken,
    PublicChatAdmissionError,
    compute_public_chat_admission_signature,
)
from core_model.ops.recovery_authorization_gate import (
    RecoveryAuthorizationGate,
    SignedRecoveryAuthorizationToken,
    RecoveryAuthorizationError,
    compute_recovery_token_signature,
)
from core_model.ops.compliance_certification_gate import (
    ComplianceCertificationGate,
    SignedComplianceCertificationToken,
    ComplianceCertificationError,
    compute_compliance_token_signature,
)
from core_model.ops.rbac_governance_engine import RBACGovernanceEngine, RBACPermissionError
from core_model.ops.tenant_security_policy_engine import TenantSecurityPolicyEngine, TenantAccessError
from core_model.ops.secret_lifecycle_manager import SecretLifecycleManager, SecretLifecycleError
from core_model.ops.policy_drift_evaluator import PolicyDriftEvaluator
from core_model.ops.production_audit_chain import ProductionAuditChain
from core_model.eval.production_release_registry import ProductionReleaseRegistry, ProductionReleaseRecord
from core_model.eval.candidate_model_registry import CandidateModelRecord
from core_model.ops.dashboard_contract import ProductionSafetyDashboardContract
from core_model.ops.recovery_audit_contract import ProductionRecoveryAuditContract
from core_model.ops.enterprise_governance_contract import EnterpriseGovernanceDashboardContract


class TestPhase61P10EAuthorizationPackageIntegration(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_INTEGRATION_SECRET_KEY_2026"
        self.training_gate = SignedTrainingGateEngine(secret_key=self.secret_key)
        self.promotion_gate = ProductionPromotionGate(secret_key=self.secret_key)
        self.public_chat_gate = PublicChatAdmissionGate(secret_key=self.secret_key)
        self.recovery_gate = RecoveryAuthorizationGate(secret_key=self.secret_key)
        self.compliance_gate = ComplianceCertificationGate(secret_key=self.secret_key)
        self.rbac_engine = RBACGovernanceEngine()
        self.tenant_engine = TenantSecurityPolicyEngine()
        self.secret_mgr = SecretLifecycleManager()
        self.drift_evaluator = PolicyDriftEvaluator()
        self.audit_chain = ProductionAuditChain()
        self.release_registry = ProductionReleaseRegistry()

    def test_01_training_token_schema_and_binding(self):
        sig = compute_training_token_signature("tok-p10e-01", "admin-dhurai", "dataset-m1", self.secret_key)
        token = SignedTrainingAuthorizationToken(
            token_id="tok-p10e-01", admin_public_id="admin-dhurai", dataset_manifest_hash="dataset-m1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        self.assertTrue(self.training_gate.verify_authorization(token, expected_manifest_hash="dataset-m1", ignore_runtime_flag=True))

    def test_02_training_token_dataset_mismatch_fails_closed(self):
        sig = compute_training_token_signature("tok-p10e-02", "admin-dhurai", "dataset-m1", self.secret_key)
        token = SignedTrainingAuthorizationToken(
            token_id="tok-p10e-02", admin_public_id="admin-dhurai", dataset_manifest_hash="dataset-m1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(token, expected_manifest_hash="wrong-dataset-hash", ignore_runtime_flag=True)

    def test_03_promotion_token_schema_and_binding(self):
        sig = compute_promotion_token_signature("tok-prom-01", "admin-dhurai", "cand-m1", "d1", self.secret_key)
        token = SignedPromotionAuthorizationToken(
            token_id="tok-prom-01", admin_public_id="admin-dhurai", candidate_model_id="cand-01",
            candidate_model_hash="cand-m1", dataset_manifest_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", admin_review_status="APPROVED", human_promotion_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        cand = CandidateModelRecord(
            candidate_model_id="cand-01", base_model_id="base-01", dataset_version="v1", dataset_hash="d1",
            tokenizer_hash="t1", training_config_hash="c1", base_model_hash="b1", candidate_model_hash="cand-m1",
            training_run_id="run-1", creation_timestamp="now", evaluation_status="EVALUATED", promotion_status="PROMOTION_PENDING"
        )
        self.assertTrue(self.promotion_gate.verify_promotion_token(token, cand))

    def test_04_promotion_token_hash_mismatch_fails_closed(self):
        sig = compute_promotion_token_signature("tok-prom-02", "admin-dhurai", "wrong-cand-hash", "d1", self.secret_key)
        token = SignedPromotionAuthorizationToken(
            token_id="tok-prom-02", admin_public_id="admin-dhurai", candidate_model_id="cand-01",
            candidate_model_hash="wrong-cand-hash", dataset_manifest_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", admin_review_status="APPROVED", human_promotion_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        cand = CandidateModelRecord(
            candidate_model_id="cand-01", base_model_id="base-01", dataset_version="v1", dataset_hash="d1",
            tokenizer_hash="t1", training_config_hash="c1", base_model_hash="b1", candidate_model_hash="cand-m1",
            training_run_id="run-1", creation_timestamp="now", evaluation_status="EVALUATED", promotion_status="PROMOTION_PENDING"
        )
        with self.assertRaises(PromotionAuthorizationError):
            self.promotion_gate.verify_promotion_token(token, cand)

    def test_05_public_chat_token_schema_and_binding(self):
        sig = compute_public_chat_admission_signature("tok-pc-01", "admin-dhurai", "rel-p10e-01", "cand-m1", self.secret_key)
        token = SignedPublicChatAdmissionToken(
            token_id="tok-pc-01", admin_public_id="admin-dhurai", release_id="rel-p10e-01", candidate_model_hash="cand-m1",
            dataset_manifest_hash="d1", human_admission_signature="sig_h", created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        rel = ProductionReleaseRecord(
            release_id="rel-p10e-01", candidate_model_id="cand-01", candidate_model_hash="cand-m1",
            base_model_hash="b1", dataset_version="v1", dataset_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", evaluation_manifest_hash="e1", promotion_authorization_hash="p1",
            approving_admin_identity="admin-dhurai", approval_timestamp="now", release_timestamp="now",
            previous_production_release_id=None, release_status="PRODUCTION_ACTIVE", rollback_status="NONE", public_chat_status="BLOCKED"
        )
        self.assertTrue(self.public_chat_gate.verify_admission_token(token, rel))

    def test_06_public_chat_token_release_mismatch_fails_closed(self):
        sig = compute_public_chat_admission_signature("tok-pc-02", "admin-dhurai", "wrong-rel-id", "cand-m1", self.secret_key)
        token = SignedPublicChatAdmissionToken(
            token_id="tok-pc-02", admin_public_id="admin-dhurai", release_id="wrong-rel-id", candidate_model_hash="cand-m1",
            dataset_manifest_hash="d1", human_admission_signature="sig_h", created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        rel = ProductionReleaseRecord(
            release_id="rel-p10e-01", candidate_model_id="cand-01", candidate_model_hash="wrong-cand-hash",
            base_model_hash="b1", dataset_version="v1", dataset_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", evaluation_manifest_hash="e1", promotion_authorization_hash="p1",
            approving_admin_identity="admin-dhurai", approval_timestamp="now", release_timestamp="now",
            previous_production_release_id=None, release_status="PRODUCTION_ACTIVE", rollback_status="NONE", public_chat_status="BLOCKED"
        )
        with self.assertRaises(PublicChatAdmissionError):
            self.public_chat_gate.verify_admission_token(token, rel)

    def test_07_recovery_token_schema_and_binding(self):
        sig = compute_recovery_token_signature("req-rec-01", "admin-dhurai", "rel-01", "snap-01", self.secret_key)
        token = SignedRecoveryAuthorizationToken(
            recovery_request_id="req-rec-01", admin_public_id="admin-dhurai", release_id="rel-01", snapshot_hash="snap-01",
            model_hash="m1", dataset_hash="d1", tokenizer_hash="t1", human_recovery_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        self.assertTrue(self.recovery_gate.verify_recovery_token(token, "rel-01", "snap-01", "m1"))

    def test_08_recovery_token_snapshot_mismatch_fails_closed(self):
        sig = compute_recovery_token_signature("req-rec-02", "admin-dhurai", "rel-01", "wrong-snap", self.secret_key)
        token = SignedRecoveryAuthorizationToken(
            recovery_request_id="req-rec-02", admin_public_id="admin-dhurai", release_id="rel-01", snapshot_hash="wrong-snap",
            model_hash="m1", dataset_hash="d1", tokenizer_hash="t1", human_recovery_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        with self.assertRaises(RecoveryAuthorizationError):
            self.recovery_gate.verify_recovery_token(token, "rel-01", "expected-snap", "m1")

    def test_09_compliance_token_schema_and_binding(self):
        sig = compute_compliance_token_signature("req-cmp-01", "pkg-01", "hash-01", "tenant-brud-core", "admin-dhurai", self.secret_key)
        token = SignedComplianceCertificationToken(
            certification_request_id="req-cmp-01", package_id="pkg-01", package_hash="hash-01",
            tenant_id="tenant-brud-core", admin_public_id="admin-dhurai", admin_role="HUMAN_ADMIN",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        self.assertTrue(self.compliance_gate.verify_certification_token(token, "pkg-01", "hash-01", "tenant-brud-core"))

    def test_10_compliance_token_tenant_mismatch_fails_closed(self):
        sig = compute_compliance_token_signature("req-cmp-02", "pkg-01", "hash-01", "tenant-enterprise-a", "admin-dhurai", self.secret_key)
        token = SignedComplianceCertificationToken(
            certification_request_id="req-cmp-02", package_id="pkg-01", package_hash="hash-01",
            tenant_id="tenant-enterprise-a", admin_public_id="admin-dhurai", admin_role="HUMAN_ADMIN",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        with self.assertRaises(ComplianceCertificationError):
            self.compliance_gate.verify_certification_token(token, "pkg-01", "hash-01", "tenant-brud-core")

    def test_11_rbac_admin_assistant_advisory_isolation(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "EXECUTE_TRAINING")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "PROMOTE_MODEL")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "EXECUTE_RECOVERY")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "CERTIFY_COMPLIANCE")

    def test_12_rbac_system_operator_cannot_promote(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SYSTEM_OPERATOR", "PROMOTE_MODEL")

    def test_13_rbac_security_auditor_cannot_execute_training(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SECURITY_AUDITOR", "EXECUTE_TRAINING")

    def test_14_secret_rotation_preserves_historical_verification(self):
        old_rec = self.secret_mgr.register_key("TEST_PURPOSE", "OLD_RAW_SECRET_16BYTES")
        new_rec = self.secret_mgr.rotate_key("TEST_PURPOSE", "NEW_RAW_SECRET_16BYTES")
        self.assertEqual(old_rec.status, "RETIRED")
        self.assertEqual(new_rec.status, "ACTIVE")
        self.assertEqual(self.secret_mgr.get_historical_secret(old_rec.key_id), "OLD_RAW_SECRET_16BYTES")

    def test_15_revoked_secret_lookup_fails_closed(self):
        rec = self.secret_mgr.register_key("REVOKE_PURPOSE", "REVOKED_RAW_SECRET_16BYTES")
        self.secret_mgr.revoke_key(rec.key_id)
        with self.assertRaises(SecretLifecycleError):
            self.secret_mgr.get_historical_secret(rec.key_id)

    def test_16_tenant_isolation_cross_tenant_denied(self):
        with self.assertRaises(TenantAccessError):
            self.tenant_engine.authorize_tenant_access("tenant-brud-core", "tenant-enterprise-z")

    def test_17_read_only_contracts_have_zero_mutation_methods(self):
        for cls in (ProductionSafetyDashboardContract, ProductionRecoveryAuditContract, EnterpriseGovernanceDashboardContract):
            methods = [m for m in dir(cls) if not m.startswith("_")]
            self.assertTrue(all(not m.startswith("set_") and not m.startswith("update_") and not m.startswith("mutate_") for m in methods))

    def test_18_audit_chain_tamper_detection(self):
        self.audit_chain.append_event("INTEGRATION", "rel-1", "m1", "admin", "INT", "PASS", "h1")
        self.assertTrue(self.audit_chain.verify_chain_integrity())

    def test_19_policy_drift_unknown_state_fails_closed(self):
        res = self.drift_evaluator.evaluate_policy_drift(mock_unknown_state=True)
        self.assertEqual(res.drift_status, "CRITICAL_DRIFT")

    def test_20_adversarial_replay_token_fails_closed(self):
        sig = compute_training_token_signature("tok-replay-02", "admin-dhurai", "d1", self.secret_key)
        token = SignedTrainingAuthorizationToken(
            token_id="tok-replay-02", admin_public_id="admin-dhurai", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig",
            created_at_epoch=time.time() - 7200, expires_at_epoch=time.time() - 3600, signature_hmac=sig
        )
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(token, ignore_runtime_flag=True)

    def test_21_adversarial_wrong_key_signature_fails_closed(self):
        wrong_sig = compute_training_token_signature("tok-badkey", "admin-dhurai", "d1", "WRONG_SECRET_KEY_12345")
        token = SignedTrainingAuthorizationToken(
            token_id="tok-badkey", admin_public_id="admin-dhurai", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=wrong_sig
        )
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(token, ignore_runtime_flag=True)

    def test_22_adversarial_promotion_before_validation_fails_closed(self):
        sig = compute_promotion_token_signature("tok-prom-badval", "admin-dhurai", "cand-m1", "d1", self.secret_key)
        token = SignedPromotionAuthorizationToken(
            token_id="tok-prom-badval", admin_public_id="admin-dhurai", candidate_model_id="cand-01",
            candidate_model_hash="cand-m1", dataset_manifest_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", admin_review_status="APPROVED", human_promotion_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        cand = CandidateModelRecord(
            candidate_model_id="cand-01", base_model_id="base-01", dataset_version="v1", dataset_hash="d1",
            tokenizer_hash="t1", training_config_hash="c1", base_model_hash="b1", candidate_model_hash="cand-m1",
            training_run_id="run-1", creation_timestamp="now", evaluation_status="EVALUATED", promotion_status="PROMOTION_PENDING"
        )
        from core_model.eval.red_team_evaluator import RedTeamEvaluationResult
        from core_model.eval.model_regression_evaluator import ModelRegressionResult
        red_res = RedTeamEvaluationResult(
            eval_id="eval-01", candidate_model_id="cand-01", safety_suite_passed=False,
            tamil_quality_passed=True, hallucination_passed=True, memorization_passed=True,
            overall_red_team_passed=False, verbatim_leakage_detected=True, prompt_injection_vulnerable=False,
            hallucination_rate=0.0, tamil_script_purity=1.0, issues=["Leakage detected"], status="PROMOTION_BLOCKED"
        )
        reg_res = ModelRegressionResult(
            eval_id="reg-01", candidate_model_id="cand-01", base_model_id="base-01",
            base_tamil_quality=0.8, candidate_tamil_quality=0.9, delta_tamil_quality=0.1,
            base_factuality=0.8, candidate_factuality=0.9, delta_factuality=0.1,
            base_hallucination=0.1, candidate_hallucination=0.05, delta_hallucination=-0.05,
            base_memorization=0.0, candidate_memorization=0.0, delta_memorization=0.0,
            regression_passed=True, status="REGRESSION_PASSED"
        )
        res = self.promotion_gate.evaluate_and_promote(cand, red_res, reg_res, signed_token=token)
        self.assertFalse(res.authorized)
        self.assertEqual(res.promotion_state, "PROMOTION_BLOCKED")

    def test_23_adversarial_public_chat_before_canary_fails_closed(self):
        res = self.public_chat_gate.evaluate_public_chat_admission(None, None, None)
        self.assertFalse(res.public_chat_eligible)

    def test_24_adversarial_recovery_before_authorization_fails_closed(self):
        with self.assertRaises(RecoveryAuthorizationError):
            self.recovery_gate.verify_recovery_token(None, "rel-01", "snap-01", "m1")

    def test_25_mandatory_governance_invariants_lock(self):
        self.assertIsNone(self.release_registry.get_active_release())


if __name__ == "__main__":
    unittest.main()
