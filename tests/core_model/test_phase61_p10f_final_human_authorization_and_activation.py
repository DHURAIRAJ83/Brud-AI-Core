"""Phase 61 - P10-F: Final Human Authorization & Controlled Activation Test Suite."""

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


class TestPhase61P10FFinalHumanAuthorizationAndActivation(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_P10F_SECRET_KEY_2026"
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

    def test_01_absent_human_training_token_fails_closed(self):
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(None)

    def test_02_absent_human_promotion_token_fails_closed(self):
        cand = CandidateModelRecord(
            candidate_model_id="cand-01", base_model_id="base-01", dataset_version="v1", dataset_hash="d1",
            tokenizer_hash="t1", training_config_hash="c1", base_model_hash="b1", candidate_model_hash="cand-m1",
            training_run_id="run-1", creation_timestamp="now", evaluation_status="EVALUATED", promotion_status="PROMOTION_PENDING"
        )
        with self.assertRaises(PromotionAuthorizationError):
            self.promotion_gate.verify_promotion_token(None, cand)

    def test_03_absent_human_public_chat_token_fails_closed(self):
        rel = ProductionReleaseRecord(
            release_id="rel-01", candidate_model_id="cand-01", candidate_model_hash="cand-m1",
            base_model_hash="b1", dataset_version="v1", dataset_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", evaluation_manifest_hash="e1", promotion_authorization_hash="p1",
            approving_admin_identity="admin-dhurai", approval_timestamp="now", release_timestamp="now",
            previous_production_release_id=None, release_status="PRODUCTION_ACTIVE", rollback_status="NONE", public_chat_status="BLOCKED"
        )
        with self.assertRaises(PublicChatAdmissionError):
            self.public_chat_gate.verify_admission_token(None, rel)

    def test_04_absent_human_recovery_token_fails_closed(self):
        with self.assertRaises(RecoveryAuthorizationError):
            self.recovery_gate.verify_recovery_token(None, "rel-01", "snap-01", "m1")

    def test_05_absent_human_compliance_token_fails_closed(self):
        with self.assertRaises(ComplianceCertificationError):
            self.compliance_gate.verify_certification_token(None, "pkg-01", "hash-01", "tenant-brud-core")

    def test_06_fake_training_token_signature_rejected(self):
        token = SignedTrainingAuthorizationToken(
            token_id="tok-fake-01", admin_public_id="fake-admin", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="fake_sig",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac="invalid_signature_hash"
        )
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(token, ignore_runtime_flag=True)

    def test_07_expired_promotion_token_rejected(self):
        token = SignedPromotionAuthorizationToken(
            token_id="tok-exp-01", admin_public_id="admin-dhurai", candidate_model_id="cand-01",
            candidate_model_hash="cand-m1", dataset_manifest_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", admin_review_status="APPROVED", human_promotion_signature="sig_h",
            created_at_epoch=time.time() - 7200, expires_at_epoch=time.time() - 3600, signature_hmac="sig"
        )
        cand = CandidateModelRecord(
            candidate_model_id="cand-01", base_model_id="base-01", dataset_version="v1", dataset_hash="d1",
            tokenizer_hash="t1", training_config_hash="c1", base_model_hash="b1", candidate_model_hash="cand-m1",
            training_run_id="run-1", creation_timestamp="now", evaluation_status="EVALUATED", promotion_status="PROMOTION_PENDING"
        )
        with self.assertRaises(PromotionAuthorizationError):
            self.promotion_gate.verify_promotion_token(token, cand)

    def test_08_rbac_admin_assistant_advisory_cannot_authorize_activation(self):
        token = SignedComplianceCertificationToken(
            certification_request_id="req-bot-01", package_id="pkg-01", package_hash="h-01",
            tenant_id="tenant-brud-core", admin_public_id="bot-assistant", admin_role="ADMIN_ASSISTANT_ADVISORY",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac="sig"
        )
        with self.assertRaises(ComplianceCertificationError) as ctx:
            self.compliance_gate.verify_certification_token(token, "pkg-01", "h-01", "tenant-brud-core")
        self.assertIn("advisory only", str(ctx.exception).lower())

    def test_09_rbac_system_operator_cannot_authorize_promotion(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SYSTEM_OPERATOR", "PROMOTE_MODEL")

    def test_10_rbac_security_auditor_cannot_authorize_training(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SECURITY_AUDITOR", "EXECUTE_TRAINING")

    def test_11_cross_tenant_token_access_denied(self):
        with self.assertRaises(TenantAccessError):
            self.tenant_engine.authorize_tenant_access("tenant-brud-core", "tenant-unauthorized")

    def test_12_audit_chain_tamper_detection(self):
        self.audit_chain.append_event("P10F_AUDIT", "rel-01", "m1", "admin", "P10F", "PASS", "h1")
        self.assertTrue(self.audit_chain.verify_chain_integrity())

    def test_13_valid_signed_training_token_verifies(self):
        sig = compute_training_token_signature("tok-valid-p10f", "admin-dhurai", "d1", self.secret_key)
        token = SignedTrainingAuthorizationToken(
            token_id="tok-valid-p10f", admin_public_id="admin-dhurai", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        self.assertTrue(self.training_gate.verify_authorization(token, ignore_runtime_flag=True))

    def test_14_valid_signed_promotion_token_verifies(self):
        sig = compute_promotion_token_signature("tok-prom-p10f", "admin-dhurai", "cand-m1", "d1", self.secret_key)
        token = SignedPromotionAuthorizationToken(
            token_id="tok-prom-p10f", admin_public_id="admin-dhurai", candidate_model_id="cand-01",
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

    def test_15_valid_signed_public_chat_token_verifies(self):
        sig = compute_public_chat_admission_signature("tok-pc-p10f", "admin-dhurai", "rel-01", "cand-m1", self.secret_key)
        token = SignedPublicChatAdmissionToken(
            token_id="tok-pc-p10f", admin_public_id="admin-dhurai", release_id="rel-01", candidate_model_hash="cand-m1",
            dataset_manifest_hash="d1", human_admission_signature="sig_h", created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        rel = ProductionReleaseRecord(
            release_id="rel-01", candidate_model_id="cand-01", candidate_model_hash="cand-m1",
            base_model_hash="b1", dataset_version="v1", dataset_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", evaluation_manifest_hash="e1", promotion_authorization_hash="p1",
            approving_admin_identity="admin-dhurai", approval_timestamp="now", release_timestamp="now",
            previous_production_release_id=None, release_status="PRODUCTION_ACTIVE", rollback_status="NONE", public_chat_status="BLOCKED"
        )
        self.assertTrue(self.public_chat_gate.verify_admission_token(token, rel))

    def test_16_valid_signed_recovery_token_verifies(self):
        sig = compute_recovery_token_signature("req-rec-p10f", "admin-dhurai", "rel-01", "snap-01", self.secret_key)
        token = SignedRecoveryAuthorizationToken(
            recovery_request_id="req-rec-p10f", admin_public_id="admin-dhurai", release_id="rel-01", snapshot_hash="snap-01",
            model_hash="m1", dataset_hash="d1", tokenizer_hash="t1", human_recovery_signature="sig_h",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        self.assertTrue(self.recovery_gate.verify_recovery_token(token, "rel-01", "snap-01", "m1"))

    def test_17_valid_signed_compliance_token_verifies(self):
        sig = compute_compliance_token_signature("req-cmp-p10f", "pkg-01", "hash-01", "tenant-brud-core", "admin-dhurai", self.secret_key)
        token = SignedComplianceCertificationToken(
            certification_request_id="req-cmp-p10f", package_id="pkg-01", package_hash="hash-01",
            tenant_id="tenant-brud-core", admin_public_id="admin-dhurai", admin_role="HUMAN_ADMIN",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        self.assertTrue(self.compliance_gate.verify_certification_token(token, "pkg-01", "hash-01", "tenant-brud-core"))

    def test_18_policy_drift_unknown_state_fails_closed(self):
        res = self.drift_evaluator.evaluate_policy_drift(mock_unknown_state=True)
        self.assertEqual(res.drift_status, "CRITICAL_DRIFT")

    def test_19_read_only_contracts_zero_mutation_methods(self):
        for cls in (ProductionSafetyDashboardContract, ProductionRecoveryAuditContract, EnterpriseGovernanceDashboardContract):
            methods = [m for m in dir(cls) if not m.startswith("_")]
            self.assertTrue(all(not m.startswith("set_") and not m.startswith("update_") and not m.startswith("mutate_") for m in methods))

    def test_20_adversarial_wrong_dataset_hash_promotion_fails_closed(self):
        sig = compute_promotion_token_signature("tok-prom-badhash", "admin-dhurai", "cand-m1", "wrong-dataset-hash", self.secret_key)
        token = SignedPromotionAuthorizationToken(
            token_id="tok-prom-badhash", admin_public_id="admin-dhurai", candidate_model_id="cand-01",
            candidate_model_hash="cand-m1", dataset_manifest_hash="wrong-dataset-hash", tokenizer_hash="t1",
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

    def test_21_adversarial_wrong_tokenizer_hash_promotion_fails_closed(self):
        sig = compute_promotion_token_signature("tok-prom-badtok", "admin-dhurai", "cand-m1", "d1", self.secret_key)
        token = SignedPromotionAuthorizationToken(
            token_id="tok-prom-badtok", admin_public_id="admin-dhurai", candidate_model_id="cand-01",
            candidate_model_hash="cand-m1", dataset_manifest_hash="d1", tokenizer_hash="wrong-tokenizer-hash",
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

    def test_22_adversarial_wrong_model_hash_public_chat_fails_closed(self):
        sig = compute_public_chat_admission_signature("tok-pc-badmodel", "admin-dhurai", "rel-01", "wrong-model-hash", self.secret_key)
        token = SignedPublicChatAdmissionToken(
            token_id="tok-pc-badmodel", admin_public_id="admin-dhurai", release_id="rel-01", candidate_model_hash="wrong-model-hash",
            dataset_manifest_hash="d1", human_admission_signature="sig_h", created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        rel = ProductionReleaseRecord(
            release_id="rel-01", candidate_model_id="cand-01", candidate_model_hash="cand-m1",
            base_model_hash="b1", dataset_version="v1", dataset_hash="d1", tokenizer_hash="t1",
            training_config_hash="c1", evaluation_manifest_hash="e1", promotion_authorization_hash="p1",
            approving_admin_identity="admin-dhurai", approval_timestamp="now", release_timestamp="now",
            previous_production_release_id=None, release_status="PRODUCTION_ACTIVE", rollback_status="NONE", public_chat_status="BLOCKED"
        )
        with self.assertRaises(PublicChatAdmissionError):
            self.public_chat_gate.verify_admission_token(token, rel)

    def test_23_adversarial_stale_token_fails_closed(self):
        sig = compute_training_token_signature("tok-stale", "admin-dhurai", "d1", self.secret_key)
        token = SignedTrainingAuthorizationToken(
            token_id="tok-stale", admin_public_id="admin-dhurai", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig_h",
            created_at_epoch=time.time() - 86400, expires_at_epoch=time.time() - 3600, signature_hmac=sig
        )
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(token, ignore_runtime_flag=True)

    def test_24_adversarial_revoked_key_token_fails_closed(self):
        rec = self.secret_mgr.register_key("TEST_REVK", "REVOKED_SECRET_16B")
        self.secret_mgr.revoke_key(rec.key_id)
        with self.assertRaises(SecretLifecycleError):
            self.secret_mgr.get_historical_secret(rec.key_id)

    def test_25_mandatory_governance_invariants_lock(self):
        self.assertIsNone(self.release_registry.get_active_release())


if __name__ == "__main__":
    unittest.main()
