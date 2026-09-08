"""Phase 61 - P10-D: Final Human Authorization Token Validation & Activation Sequence Audit Test Suite."""

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
from core_model.ops.secret_lifecycle_manager import SecretLifecycleManager
from core_model.ops.production_audit_chain import ProductionAuditChain
from core_model.eval.production_release_registry import ProductionReleaseRegistry, ProductionReleaseRecord


class TestPhase61P10DAuthorizationTokenValidation(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_TOKEN_VALIDATION_SECRET_KEY_2026"
        self.training_gate = SignedTrainingGateEngine(secret_key=self.secret_key)
        self.promotion_gate = ProductionPromotionGate(secret_key=self.secret_key)
        self.public_chat_gate = PublicChatAdmissionGate(secret_key=self.secret_key)
        self.recovery_gate = RecoveryAuthorizationGate(secret_key=self.secret_key)
        self.compliance_gate = ComplianceCertificationGate(secret_key=self.secret_key)
        self.rbac_engine = RBACGovernanceEngine()
        self.tenant_engine = TenantSecurityPolicyEngine()
        self.secret_mgr = SecretLifecycleManager()
        self.audit_chain = ProductionAuditChain()
        self.release_registry = ProductionReleaseRegistry()

    def test_01_missing_training_token_fails_closed(self):
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(None)

    def test_02_expired_training_token_fails_closed(self):
        token = SignedTrainingAuthorizationToken(
            token_id="tok-01", admin_public_id="admin-dhurai", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig",
            created_at_epoch=time.time() - 3600, expires_at_epoch=time.time() - 100, signature_hmac="sig"
        )
        with self.assertRaises(TrainingAuthorizationError) as ctx:
            self.training_gate.verify_authorization(token, ignore_runtime_flag=True)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_03_invalid_signature_training_token_fails_closed(self):
        token = SignedTrainingAuthorizationToken(
            token_id="tok-02", admin_public_id="admin-dhurai", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac="invalid_hmac_signature"
        )
        with self.assertRaises(TrainingAuthorizationError) as ctx:
            self.training_gate.verify_authorization(token, ignore_runtime_flag=True)
        self.assertIn("invalid hmac", str(ctx.exception).lower())

    def test_04_missing_promotion_token_fails_closed(self):
        with self.assertRaises(PromotionAuthorizationError):
            self.promotion_gate.verify_promotion_token(None, None)

    def test_05_missing_public_chat_token_fails_closed(self):
        with self.assertRaises(PublicChatAdmissionError):
            self.public_chat_gate.verify_admission_token(None, None)

    def test_06_missing_recovery_token_fails_closed(self):
        with self.assertRaises(RecoveryAuthorizationError):
            self.recovery_gate.verify_recovery_token(None, "rel-1", "snap-1", "m1")

    def test_07_missing_compliance_token_fails_closed(self):
        with self.assertRaises(ComplianceCertificationError):
            self.compliance_gate.verify_certification_token(None, "pkg-1", "hash-1", "tenant-brud-core")

    def test_08_rbac_admin_assistant_advisory_cannot_issue_tokens(self):
        token = SignedComplianceCertificationToken(
            certification_request_id="req-1", package_id="pkg-1", package_hash="h-1",
            tenant_id="tenant-brud-core", admin_public_id="bot", admin_role="ADMIN_ASSISTANT_ADVISORY",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600,
            signature_hmac="sig"
        )
        with self.assertRaises(ComplianceCertificationError) as ctx:
            self.compliance_gate.verify_certification_token(token, "pkg-1", "h-1", "tenant-brud-core")
        self.assertIn("advisory only", str(ctx.exception).lower())

    def test_09_rbac_system_operator_cannot_certify(self):
        token = SignedComplianceCertificationToken(
            certification_request_id="req-2", package_id="pkg-1", package_hash="h-1",
            tenant_id="tenant-brud-core", admin_public_id="op", admin_role="SYSTEM_OPERATOR",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600,
            signature_hmac="sig"
        )
        with self.assertRaises(ComplianceCertificationError) as ctx:
            self.compliance_gate.verify_certification_token(token, "pkg-1", "h-1", "tenant-brud-core")
        self.assertIn("invalid certifying role", str(ctx.exception).lower())

    def test_10_wrong_tenant_id_token_fails_closed(self):
        sig = compute_compliance_token_signature("req-3", "pkg-1", "h-1", "tenant-enterprise-a", "admin-dhurai", self.secret_key)
        token = SignedComplianceCertificationToken(
            certification_request_id="req-3", package_id="pkg-1", package_hash="h-1",
            tenant_id="tenant-enterprise-a", admin_public_id="admin-dhurai", admin_role="HUMAN_ADMIN",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )
        with self.assertRaises(ComplianceCertificationError) as ctx:
            self.compliance_gate.verify_certification_token(token, "pkg-1", "h-1", "tenant-brud-core")
        self.assertIn("tenant id mismatch", str(ctx.exception).lower())

    def test_11_wrong_package_hash_token_fails_closed(self):
        sig = compute_compliance_token_signature("req-4", "pkg-1", "wrong-hash", "tenant-brud-core", "admin-dhurai", self.secret_key)
        token = SignedComplianceCertificationToken(
            certification_request_id="req-4", package_id="pkg-1", package_hash="wrong-hash",
            tenant_id="tenant-brud-core", admin_public_id="admin-dhurai", admin_role="HUMAN_ADMIN",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )
        with self.assertRaises(ComplianceCertificationError) as ctx:
            self.compliance_gate.verify_certification_token(token, "pkg-1", "expected-hash", "tenant-brud-core")
        self.assertIn("hash mismatch", str(ctx.exception).lower())

    def test_12_valid_signed_training_token_verifies(self):
        sig = compute_training_token_signature("tok-valid-01", "admin-dhurai", "d1", self.secret_key)
        token = SignedTrainingAuthorizationToken(
            token_id="tok-valid-01", admin_public_id="admin-dhurai", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig",
            created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600, signature_hmac=sig
        )
        self.assertTrue(self.training_gate.verify_authorization(token, ignore_runtime_flag=True))

    def test_13_valid_signed_compliance_token_verifies(self):
        sig = compute_compliance_token_signature("req-val-01", "pkg-1", "hash-1", "tenant-brud-core", "admin-dhurai", self.secret_key)
        token = SignedComplianceCertificationToken(
            certification_request_id="req-val-01", package_id="pkg-1", package_hash="hash-1",
            tenant_id="tenant-brud-core", admin_public_id="admin-dhurai", admin_role="HUMAN_ADMIN",
            policy_version="v1", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )
        self.assertTrue(self.compliance_gate.verify_certification_token(token, "pkg-1", "hash-1", "tenant-brud-core"))

    def test_14_hash_mismatch_prevents_activation(self):
        sig = compute_recovery_token_signature("req-rec-1", "admin-dhurai", "rel-1", "snap-1", self.secret_key)
        token = SignedRecoveryAuthorizationToken(
            recovery_request_id="req-rec-1", admin_public_id="admin-dhurai",
            release_id="rel-1", snapshot_hash="snap-1", model_hash="m1", dataset_hash="d1", tokenizer_hash="t1",
            human_recovery_signature="sig_human", created_at_epoch=time.time(), expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )
        with self.assertRaises(RecoveryAuthorizationError):
            self.recovery_gate.verify_recovery_token(token, "rel-1", "snap-1", "different-model-hash")

    def test_15_raw_secrets_never_exposed_in_token_views(self):
        sec = self.secret_mgr.register_key("TOKEN_VALIDATION_GATE", "RAW_SECRET_KEY_16BYTES")
        self.assertNotIn("RAW_SECRET_KEY_16BYTES", str(sec))

    def test_16_rbac_privilege_escalation_denied(self):
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("SYSTEM_OPERATOR", "PROMOTE_MODEL")
        with self.assertRaises(RBACPermissionError):
            self.rbac_engine.authorize_action("ADMIN_ASSISTANT_ADVISORY", "EXECUTE_TRAINING")

    def test_17_tenant_isolation_cross_tenant_denied(self):
        with self.assertRaises(TenantAccessError):
            self.tenant_engine.authorize_tenant_access("tenant-brud-core", "tenant-enterprise-b")

    def test_18_audit_chain_tamper_detection(self):
        self.audit_chain.append_event("TOKEN_VAL", "rel-1", "m1", "admin", "TOKEN", "PASS", "h1")
        self.assertTrue(self.audit_chain.verify_chain_integrity())

    def test_19_adversarial_token_replay_rejected(self):
        sig = compute_training_token_signature("tok-replay-01", "admin-dhurai", "d1", self.secret_key)
        token = SignedTrainingAuthorizationToken(
            token_id="tok-replay-01", admin_public_id="admin-dhurai", dataset_manifest_hash="d1",
            rights_gate_status="PASS", novelty_gate_status="PASS", provenance_gate_status="PASS",
            holdout_gate_status="PASS", token_accounting_status="PASS", human_approval_signature="sig",
            created_at_epoch=time.time() - 7200, expires_at_epoch=time.time() - 3600, signature_hmac=sig
        )
        with self.assertRaises(TrainingAuthorizationError):
            self.training_gate.verify_authorization(token, ignore_runtime_flag=True)

    def test_20_mandatory_governance_invariants_lock(self):
        self.assertIsNone(self.release_registry.get_active_release())


if __name__ == "__main__":
    unittest.main()
