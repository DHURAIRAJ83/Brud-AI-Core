"""Phase 61 - P6: Production Release, Canary Deployment & Public Chat Admission Gate Test Suite."""

import time
import unittest
from pathlib import Path

from core_model.eval.production_release_registry import (
    ProductionReleaseRecord,
    ProductionReleaseRegistry,
)
from core_model.eval.canary_deployment_governance import (
    CanaryDeploymentEngine,
    CanaryDeploymentResult,
    CanaryGovernanceError,
)
from core_model.eval.public_chat_admission_gate import (
    PublicChatAdmissionError,
    PublicChatAdmissionGate,
    PublicChatAdmissionResult,
    SignedPublicChatAdmissionToken,
    compute_public_chat_admission_signature,
)
from core_model.admin_assistant.admin_review_queue import AdminReviewQueueManager


class TestPhase61P6ProductionReleaseAndCanary(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_PUBLIC_CHAT_SECRET_KEY_2026"
        self.release_registry = ProductionReleaseRegistry()
        self.admission_gate = PublicChatAdmissionGate(
            secret_key=self.secret_key,
            existing_approved_production_hash="approved-prod-hash-0000"
        )
        self.admin_review = AdminReviewQueueManager()

        # Register initial production release candidate
        self.release_rec = self.release_registry.register_release(
            release_id="rel-p6-001",
            candidate_model_id="cand-p5-001",
            candidate_model_hash="cand-sha256-555",
            base_model_hash="base-sha256-444",
            dataset_version="foundation_stage8_v001",
            dataset_hash="dataset-manifest-sha256-111",
            tokenizer_hash="tokenizer-sha256-222",
            training_config_hash="config-sha256-333",
            evaluation_manifest_hash="eval-manifest-sha256-999",
            promotion_authorization_hash="prom-auth-sha256-888",
            approving_admin_identity="admin-dhurai",
            previous_production_release_id="rel-p5-base"
        )

        # Set active release
        self.release_registry.set_active_release("rel-p6-001")

        # Build valid signed public chat admission token
        tok_id = "tok-chat-001"
        admin_id = "admin-dhurai"
        sig = compute_public_chat_admission_signature(
            tok_id, admin_id, self.release_rec.release_id, self.release_rec.candidate_model_hash, self.secret_key
        )

        self.valid_chat_token = SignedPublicChatAdmissionToken(
            token_id=tok_id,
            admin_public_id=admin_id,
            release_id=self.release_rec.release_id,
            candidate_model_hash=self.release_rec.candidate_model_hash,
            dataset_manifest_hash=self.release_rec.dataset_hash,
            human_admission_signature="SIGNATURE_VERIFIED_CHAT_ADMISSION",
            created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )

    def test_01_production_release_registry_creation(self):
        active = self.release_registry.get_active_release()
        self.assertIsNotNone(active)
        self.assertEqual(active.release_id, "rel-p6-001")
        self.assertEqual(active.release_status, "PRODUCTION_ACTIVE")
        self.assertEqual(active.public_chat_status, "BLOCKED")

    def test_02_canary_initialization_starts_at_zero_traffic(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        self.assertEqual(engine.current_traffic_share, 0.0)
        self.assertEqual(engine.canary_status, "CANARY_ELIGIBLE")

    def test_03_canary_staged_progression_success(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        stages = (0.01, 0.05, 0.10, 0.25, 0.50, 1.00)
        for st in stages:
            res = engine.advance_canary_stage(st)
            self.assertEqual(res.candidate_traffic_share, st)
            if st < 1.00:
                self.assertEqual(res.canary_status, "CANARY_RUNNING")
            else:
                self.assertEqual(res.canary_status, "CANARY_PASSED")

    def test_04_canary_high_error_rate_triggers_rollback(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        engine.advance_canary_stage(0.01)
        # Simulate high error rate on next step
        res = engine.advance_canary_stage(0.05, mock_high_error_rate=True)
        self.assertEqual(res.canary_status, "ROLLBACK_REQUIRED")
        self.assertEqual(res.candidate_traffic_share, 0.0)

    def test_05_canary_safety_violation_triggers_rollback(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        res = engine.advance_canary_stage(0.01, mock_safety_violation=True)
        self.assertEqual(res.canary_status, "ROLLBACK_REQUIRED")
        self.assertEqual(res.candidate_traffic_share, 0.0)

    def test_06_invalid_canary_stage_rejection(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        with self.assertRaises(CanaryGovernanceError):
            engine.advance_canary_stage(0.15)  # 15% is not in allowed stages

    def test_07_production_release_success_does_not_grant_public_chat_eligibility(self):
        active = self.release_registry.get_active_release()
        self.assertEqual(active.public_chat_status, "BLOCKED")

    def test_08_public_chat_admission_fails_without_signed_token(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        canary_res = engine.advance_canary_stage(1.00)

        res = self.admission_gate.evaluate_public_chat_admission(
            self.release_rec, canary_res, signed_token=None, admin_admission_decision="PUBLIC_CHAT_APPROVED"
        )
        self.assertFalse(res.admitted)
        self.assertFalse(res.public_chat_eligible)
        self.assertEqual(res.active_routing_model_hash, "approved-prod-hash-0000")

    def test_09_public_chat_admission_fails_on_invalid_hmac_signature(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        canary_res = engine.advance_canary_stage(1.00)

        bad_token = SignedPublicChatAdmissionToken(**{**self.valid_chat_token.__dict__, "signature_hmac": "bad-sig-999"})
        res = self.admission_gate.evaluate_public_chat_admission(
            self.release_rec, canary_res, signed_token=bad_token, admin_admission_decision="PUBLIC_CHAT_APPROVED"
        )
        self.assertFalse(res.admitted)
        self.assertFalse(res.public_chat_eligible)

    def test_10_public_chat_admission_fails_on_expired_token(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        canary_res = engine.advance_canary_stage(1.00)

        exp_token = SignedPublicChatAdmissionToken(**{**self.valid_chat_token.__dict__, "expires_at_epoch": time.time() - 10})
        res = self.admission_gate.evaluate_public_chat_admission(
            self.release_rec, canary_res, signed_token=exp_token, admin_admission_decision="PUBLIC_CHAT_APPROVED"
        )
        self.assertFalse(res.admitted)
        self.assertFalse(res.public_chat_eligible)

    def test_11_public_chat_admission_fails_if_canary_incomplete(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        canary_res = engine.advance_canary_stage(0.50)  # Only reached 50%

        res = self.admission_gate.evaluate_public_chat_admission(
            self.release_rec, canary_res, signed_token=self.valid_chat_token, admin_admission_decision="PUBLIC_CHAT_APPROVED"
        )
        self.assertFalse(res.admitted)
        self.assertFalse(res.public_chat_eligible)

    def test_12_public_chat_admission_fails_if_release_status_not_active(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        canary_res = engine.advance_canary_stage(1.00)

        inactive_rec = ProductionReleaseRecord(**{**self.release_rec.__dict__, "release_status": "ROLLED_BACK"})
        res = self.admission_gate.evaluate_public_chat_admission(
            inactive_rec, canary_res, signed_token=self.valid_chat_token, admin_admission_decision="PUBLIC_CHAT_APPROVED"
        )
        self.assertFalse(res.admitted)
        self.assertFalse(res.public_chat_eligible)

    def test_13_public_chat_admission_fails_without_human_admin_approval(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        canary_res = engine.advance_canary_stage(1.00)

        res = self.admission_gate.evaluate_public_chat_admission(
            self.release_rec, canary_res, signed_token=self.valid_chat_token, admin_admission_decision="PUBLIC_CHAT_REJECTED"
        )
        self.assertFalse(res.admitted)
        self.assertFalse(res.public_chat_eligible)

    def test_14_public_chat_admission_success_grants_eligibility_and_routes(self):
        engine = CanaryDeploymentEngine("rel-p6-001")
        canary_res = engine.advance_canary_stage(1.00)

        res = self.admission_gate.evaluate_public_chat_admission(
            self.release_rec, canary_res, signed_token=self.valid_chat_token, admin_admission_decision="PUBLIC_CHAT_APPROVED"
        )
        self.assertTrue(res.admitted)
        self.assertTrue(res.public_chat_eligible)
        self.assertEqual(res.active_routing_model_hash, self.release_rec.candidate_model_hash)

    def test_15_fail_closed_fallback_routing_on_unadmitted_public_chat(self):
        res = self.admission_gate.evaluate_public_chat_admission(
            self.release_rec, canary_res=None, signed_token=None
        )
        self.assertFalse(res.public_chat_eligible)
        # Fallback to existing approved production model hash
        self.assertEqual(res.active_routing_model_hash, "approved-prod-hash-0000")

    def test_16_atomic_release_rollback_preserves_previous_release(self):
        self.release_registry.mark_rollback("rel-p6-001", previous_release_id="rel-p5-base")
        rec = self.release_registry.get_release("rel-p6-001")
        self.assertEqual(rec.release_status, "ROLLED_BACK")
        self.assertEqual(rec.rollback_status, "ROLLBACK_EXECUTED")

    def test_17_single_active_production_release_concurrency_invariant(self):
        rel2 = self.release_registry.register_release(
            release_id="rel-p6-002",
            candidate_model_id="cand-p5-002",
            candidate_model_hash="cand-sha256-777",
            base_model_hash="base-sha256-444",
            dataset_version="foundation_stage8_v002",
            dataset_hash="dataset-manifest-sha256-222",
            tokenizer_hash="tokenizer-sha256-222",
            training_config_hash="config-sha256-333",
            evaluation_manifest_hash="eval-manifest-sha256-999",
            promotion_authorization_hash="prom-auth-sha256-888",
            approving_admin_identity="admin-dhurai"
        )
        self.release_registry.set_active_release("rel-p6-002")
        active = self.release_registry.get_active_release()
        self.assertEqual(active.release_id, "rel-p6-002")

    def test_18_admin_review_queue_extension(self):
        rev_rec = self.admin_review.record_admin_decision("rev-rel-001", "PUBLIC_CHAT_APPROVED")
        self.assertEqual(rev_rec.decision, "PUBLIC_CHAT_APPROVED")

    def test_19_model_hash_mismatch_in_admission_token_fails(self):
        mismatch_hash = "wrong-model-hash"
        sig = compute_public_chat_admission_signature(
            self.valid_chat_token.token_id,
            self.valid_chat_token.admin_public_id,
            self.valid_chat_token.release_id,
            mismatch_hash,
            self.secret_key
        )
        mismatch_token = SignedPublicChatAdmissionToken(
            **{**self.valid_chat_token.__dict__, "candidate_model_hash": mismatch_hash, "signature_hmac": sig}
        )
        with self.assertRaises(PublicChatAdmissionError) as ctx:
            self.admission_gate.verify_admission_token(mismatch_token, self.release_rec)
        self.assertIn("mismatch", str(ctx.exception))

    def test_20_default_governance_invariants(self):
        self.assertFalse(self.release_rec.public_chat_status == "ADMITTED")


if __name__ == "__main__":
    unittest.main()
