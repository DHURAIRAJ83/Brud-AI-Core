"""Phase 61 - P5: Candidate Validation, Red-Team, Shadow Evaluation & Production Promotion Test Suite."""

import time
import unittest
from pathlib import Path

from core_model.eval.candidate_model_registry import (
    CandidateModelRecord,
    CandidateModelRegistry,
)
from core_model.eval.red_team_evaluator import (
    RedTeamEvaluationResult,
    RedTeamEvaluator,
)
from core_model.eval.model_regression_evaluator import (
    ModelRegressionResult,
    ModelRegressionEvaluator,
)
from core_model.eval.shadow_evaluator import (
    ShadowEvaluationResult,
    ShadowEvaluator,
)
from core_model.eval.production_promotion_gate import (
    ProductionPromotionGate,
    PromotionAuthorizationError,
    PromotionVerificationResult,
    SignedPromotionAuthorizationToken,
    compute_promotion_token_signature,
)


class TestPhase61P5CandidateValidationAndPromotion(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_PROMOTION_SECRET_KEY_2026"
        self.registry = CandidateModelRegistry()
        self.red_team_eval = RedTeamEvaluator()
        self.regression_eval = ModelRegressionEvaluator()
        self.shadow_eval = ShadowEvaluator()
        self.promotion_gate = ProductionPromotionGate(secret_key=self.secret_key)

        # Register valid candidate model
        self.cand_rec = self.registry.register_candidate_model(
            candidate_model_id="cand-p5-001",
            base_model_id="base-model-v1",
            dataset_version="foundation_stage8_v001",
            dataset_hash="dataset-manifest-sha256-111",
            tokenizer_hash="tokenizer-sha256-222",
            training_config_hash="config-sha256-333",
            base_model_hash="base-sha256-444",
            candidate_model_hash="cand-sha256-555",
            training_run_id="run-p4-001"
        )

        # Build valid signed promotion token
        tok_id = "tok-prom-001"
        admin_id = "admin-dhurai"
        sig = compute_promotion_token_signature(
            tok_id, admin_id, self.cand_rec.candidate_model_hash, self.cand_rec.dataset_hash, self.secret_key
        )

        self.valid_promotion_token = SignedPromotionAuthorizationToken(
            token_id=tok_id,
            admin_public_id=admin_id,
            candidate_model_id=self.cand_rec.candidate_model_id,
            candidate_model_hash=self.cand_rec.candidate_model_hash,
            dataset_manifest_hash=self.cand_rec.dataset_hash,
            tokenizer_hash=self.cand_rec.tokenizer_hash,
            training_config_hash=self.cand_rec.training_config_hash,
            admin_review_status="PROMOTION_APPROVED",
            human_promotion_signature="SIGNATURE_VERIFIED_PROMOTION",
            created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )

    def test_01_candidate_registry_creation_and_isolation(self):
        self.assertEqual(self.cand_rec.evaluation_status, "TRAINED_CANDIDATE")
        self.assertEqual(self.cand_rec.promotion_status, "PROMOTION_BLOCKED")
        self.assertFalse(self.cand_rec.is_production)
        self.assertFalse(self.cand_rec.public_chat_eligible)
        self.assertEqual(self.cand_rec.candidate_traffic_share, 0.0)

    def test_02_candidate_registry_state_transitions(self):
        updated = self.registry.update_evaluation_status("cand-p5-001", "EVALUATION_PASSED")
        self.assertEqual(updated.evaluation_status, "EVALUATION_PASSED")

    def test_03_candidate_model_hash_binding(self):
        self.assertEqual(self.cand_rec.candidate_model_hash, "cand-sha256-555")
        self.assertEqual(self.cand_rec.base_model_hash, "base-sha256-444")

    def test_04_dataset_hash_binding(self):
        self.assertEqual(self.cand_rec.dataset_hash, "dataset-manifest-sha256-111")

    def test_05_tokenizer_hash_binding(self):
        self.assertEqual(self.cand_rec.tokenizer_hash, "tokenizer-sha256-222")

    def test_06_training_config_hash_binding(self):
        self.assertEqual(self.cand_rec.training_config_hash, "config-sha256-333")

    def test_07_red_team_safety_evaluation_pass(self):
        res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        self.assertTrue(res.overall_red_team_passed)
        self.assertEqual(res.status, "EVALUATION_PASSED")

    def test_08_red_team_prompt_injection_vulnerability_blocks_promotion(self):
        res = self.red_team_eval.evaluate_candidate(self.cand_rec, mock_prompt_injection_fail=True)
        self.assertFalse(res.overall_red_team_passed)
        self.assertEqual(res.status, "PROMOTION_BLOCKED")
        self.assertTrue(res.prompt_injection_vulnerable)

    def test_09_governance_bypass_resistance(self):
        res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        self.assertTrue(res.safety_suite_passed)

    def test_10_tamil_quality_evaluation(self):
        res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        self.assertTrue(res.tamil_quality_passed)
        self.assertGreaterEqual(res.tamil_script_purity, 0.90)

    def test_11_tanglish_normalization(self):
        res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        self.assertTrue(res.tamil_quality_passed)

    def test_12_hallucination_rate_evaluation(self):
        res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        self.assertLessEqual(res.hallucination_rate, 0.15)
        self.assertTrue(res.hallucination_passed)

    def test_13_memorization_detection_verbatim_leakage_blocks_promotion(self):
        res = self.red_team_eval.evaluate_candidate(self.cand_rec, mock_verbatim_memorization_fail=True)
        self.assertFalse(res.memorization_passed)
        self.assertEqual(res.status, "PROMOTION_BLOCKED")

    def test_14_leakage_detection(self):
        res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        self.assertFalse(res.verbatim_leakage_detected)

    def test_15_base_vs_candidate_regression_deltas(self):
        res = self.regression_eval.evaluate_regression(self.cand_rec)
        self.assertTrue(res.regression_passed)
        self.assertEqual(res.delta_tamil_quality, 0.23)
        self.assertEqual(res.delta_factuality, 0.20)

    def test_16_shadow_evaluation(self):
        res = self.shadow_eval.evaluate_shadow_benchmark(self.cand_rec)
        self.assertTrue(res.shadow_passed)
        self.assertEqual(res.shadow_quality_score, 0.91)

    def test_17_candidate_traffic_remains_zero(self):
        res = self.shadow_eval.evaluate_shadow_benchmark(self.cand_rec)
        self.assertEqual(res.candidate_traffic_share, 0.0)

    def test_18_public_chat_remains_blocked(self):
        res = self.shadow_eval.evaluate_shadow_benchmark(self.cand_rec)
        self.assertFalse(res.public_chat_eligible)

    def test_19_invalid_promotion_token_hmac_signature_rejection(self):
        bad_token = SignedPromotionAuthorizationToken(**{**self.valid_promotion_token.__dict__, "signature_hmac": "bad-sig-123"})
        with self.assertRaises(PromotionAuthorizationError) as ctx:
            self.promotion_gate.verify_promotion_token(bad_token, self.cand_rec)
        self.assertIn("Invalid HMAC signature", str(ctx.exception))

    def test_20_expired_promotion_token_rejection(self):
        exp_token = SignedPromotionAuthorizationToken(**{**self.valid_promotion_token.__dict__, "expires_at_epoch": time.time() - 10})
        with self.assertRaises(PromotionAuthorizationError) as ctx:
            self.promotion_gate.verify_promotion_token(exp_token, self.cand_rec)
        self.assertIn("expired", str(ctx.exception))

    def test_21_replay_or_hash_mismatch_rejection(self):
        mismatch_hash = "wrong-hash"
        sig = compute_promotion_token_signature(
            self.valid_promotion_token.token_id,
            self.valid_promotion_token.admin_public_id,
            mismatch_hash,
            self.valid_promotion_token.dataset_manifest_hash,
            self.secret_key
        )
        mismatch_token = SignedPromotionAuthorizationToken(
            **{**self.valid_promotion_token.__dict__, "candidate_model_hash": mismatch_hash, "signature_hmac": sig}
        )
        with self.assertRaises(PromotionAuthorizationError) as ctx:
            self.promotion_gate.verify_promotion_token(mismatch_token, self.cand_rec)
        self.assertIn("hash mismatch", str(ctx.exception))

    def test_22_missing_human_approval_rejection(self):
        red_team_res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        regr_res = self.regression_eval.evaluate_regression(self.cand_rec)

        res = self.promotion_gate.evaluate_and_promote(
            self.cand_rec, red_team_res, regr_res, self.valid_promotion_token, admin_approval_decision="PENDING_REVIEW"
        )
        self.assertFalse(res.authorized)
        self.assertEqual(res.promotion_state, "PROMOTION_BLOCKED")

    def test_23_failed_red_team_blocks_promotion(self):
        failed_red_team = self.red_team_eval.evaluate_candidate(self.cand_rec, mock_prompt_injection_fail=True)
        regr_res = self.regression_eval.evaluate_regression(self.cand_rec)

        res = self.promotion_gate.evaluate_and_promote(
            self.cand_rec, failed_red_team, regr_res, self.valid_promotion_token
        )
        self.assertFalse(res.authorized)
        self.assertEqual(res.promotion_state, "PROMOTION_BLOCKED")

    def test_24_memorization_failure_blocks_promotion(self):
        mem_fail_red_team = self.red_team_eval.evaluate_candidate(self.cand_rec, mock_verbatim_memorization_fail=True)
        regr_res = self.regression_eval.evaluate_regression(self.cand_rec)

        res = self.promotion_gate.evaluate_and_promote(
            self.cand_rec, mem_fail_red_team, regr_res, self.valid_promotion_token
        )
        self.assertFalse(res.authorized)
        self.assertEqual(res.promotion_state, "PROMOTION_BLOCKED")

    def test_25_atomic_promotion_verification_success(self):
        red_team_res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        regr_res = self.regression_eval.evaluate_regression(self.cand_rec)

        res = self.promotion_gate.evaluate_and_promote(
            self.cand_rec, red_team_res, regr_res, self.valid_promotion_token, admin_approval_decision="PROMOTION_APPROVED"
        )
        self.assertTrue(res.authorized)
        self.assertEqual(res.promotion_state, "PROMOTION_VERIFIED")
        self.assertEqual(res.new_production_model_hash, self.cand_rec.candidate_model_hash)

    def test_26_atomic_rollback_validation_on_failure(self):
        red_team_res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        regr_res = self.regression_eval.evaluate_regression(self.cand_rec)

        res = self.promotion_gate.evaluate_and_promote(
            self.cand_rec, red_team_res, regr_res, self.valid_promotion_token, simulate_promotion_failure=True
        )
        self.assertFalse(res.authorized)
        self.assertEqual(res.promotion_state, "ROLLBACK_REQUIRED")
        self.assertTrue(res.rollback_performed)

    def test_27_full_promotion_gate_blocks_without_signed_token(self):
        red_team_res = self.red_team_eval.evaluate_candidate(self.cand_rec)
        regr_res = self.regression_eval.evaluate_regression(self.cand_rec)

        res = self.promotion_gate.evaluate_and_promote(
            self.cand_rec, red_team_res, regr_res, signed_token=None
        )
        self.assertFalse(res.authorized)
        self.assertEqual(res.promotion_state, "PROMOTION_BLOCKED")


if __name__ == "__main__":
    unittest.main()
