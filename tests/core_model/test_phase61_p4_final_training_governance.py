"""Phase 61 - P4: Final Dataset Approval, Training Readiness & Controlled Training Governance Test Suite."""

import time
import unittest
from pathlib import Path

from core_model.corpus.dataset_compiler import CompiledDatasetManifest
from core_model.training.signed_training_gate import (
    SignedTrainingAuthorizationToken,
    SignedTrainingGateEngine,
    TrainingAuthorizationError,
    compute_token_signature,
)
from core_model.training.training_readiness_certifier import (
    PreFlightSnapshot,
    ReadinessCertificationResult,
    TrainingReadinessCertifier,
)
from core_model.training.controlled_training_runner import (
    ControlledTrainingRunner,
    ControlledTrainingRunResult,
)
from core_model.eval.post_training_evaluator import PostTrainingEvaluator


class TestPhase61P4FinalTrainingGovernance(unittest.TestCase):

    def setUp(self):
        self.secret_key = "BRUD_GOVERNANCE_SECRET_KEY_2026"
        self.signed_gate = SignedTrainingGateEngine(secret_key=self.secret_key)
        self.certifier = TrainingReadinessCertifier(signed_gate_engine=self.signed_gate)
        self.runner = ControlledTrainingRunner(certifier=self.certifier, signed_gate_engine=self.signed_gate)
        self.evaluator = PostTrainingEvaluator()

        # Build standard valid mock manifest
        self.valid_manifest = CompiledDatasetManifest(
            dataset_id="ds-v001",
            dataset_version="foundation_stage8_v001",
            pipeline_version="P3-v1.0",
            creation_timestamp="2026-09-02T12:00:00Z",
            state="APPROVED_CANDIDATE",
            source_count=2,
            book_count=4,
            record_count=100,
            total_tokens=10000,
            native_tokens=10000,
            synthetic_tokens=0,
            translated_tokens=0,
            derived_tokens=0,
            true_new_tokens=10000,
            target_token_goal=10000000,
            remaining_target_gap=9990000,
            domain_distribution={"LITERATURE": 5000, "HISTORY": 5000},
            rights_summary={"status": "PASSED"},
            quality_summary={"status": "PASSED"},
            token_accounting_status="PASSED",
            manifest_sha256="manifest-sha256-abcdef123456",
            training_authorized=False
        )

        # Build valid signed token
        token_id = "tok-p4-001"
        admin_id = "admin-dhurai"
        sig = compute_token_signature(token_id, admin_id, self.valid_manifest.manifest_sha256, self.secret_key)

        self.valid_token = SignedTrainingAuthorizationToken(
            token_id=token_id,
            admin_public_id=admin_id,
            dataset_manifest_hash=self.valid_manifest.manifest_sha256,
            rights_gate_status="PASS",
            novelty_gate_status="PASS",
            provenance_gate_status="PASS",
            holdout_gate_status="PASS",
            token_accounting_status="PASS",
            human_approval_signature="SIGNATURE_VERIFIED_DHURAI",
            created_at_epoch=time.time(),
            expires_at_epoch=time.time() + 3600,
            signature_hmac=sig
        )

    def test_01_readiness_certification_success_with_valid_token(self):
        res = self.certifier.certify_readiness(self.valid_manifest, self.valid_token, admin_decision="APPROVED_CANDIDATE")
        self.assertTrue(res.certified)
        self.assertEqual(res.readiness_status, "CERTIFIED")
        self.assertIsNotNone(res.snapshot)
        self.assertEqual(res.snapshot.dataset_version, "foundation_stage8_v001")

    def test_02_readiness_fails_without_signed_token(self):
        res = self.certifier.certify_readiness(self.valid_manifest, signed_token=None, admin_decision="APPROVED_CANDIDATE")
        self.assertFalse(res.certified)
        self.assertEqual(res.readiness_status, "READINESS_FAILED")
        self.assertEqual(res.signed_token_gate, "FAIL")

    def test_03_readiness_fails_if_rights_unverified(self):
        bad_rights_manifest = CompiledDatasetManifest(**{**self.valid_manifest.__dict__, "rights_summary": {"status": "FAILED"}})
        res = self.certifier.certify_readiness(bad_rights_manifest, self.valid_token)
        self.assertFalse(res.certified)
        self.assertEqual(res.rights_gate, "FAIL")

    def test_04_readiness_fails_if_token_accounting_mismatch(self):
        bad_acc_manifest = CompiledDatasetManifest(**{**self.valid_manifest.__dict__, "token_accounting_status": "FAILED"})
        res = self.certifier.certify_readiness(bad_acc_manifest, self.valid_token)
        self.assertFalse(res.certified)
        self.assertEqual(res.token_accounting_gate, "FAIL")

    def test_05_readiness_fails_if_human_approval_missing(self):
        res = self.certifier.certify_readiness(self.valid_manifest, self.valid_token, admin_decision="PENDING_REVIEW")
        self.assertFalse(res.certified)
        self.assertEqual(res.human_approval_gate, "FAIL")

    def test_06_preflight_snapshot_hash_generation(self):
        res = self.certifier.certify_readiness(self.valid_manifest, self.valid_token)
        snap = res.snapshot
        self.assertIsNotNone(snap.base_model_hash)
        self.assertIsNotNone(snap.dataset_hash)
        self.assertIsNotNone(snap.tokenizer_hash)
        self.assertIsNotNone(snap.training_config_hash)

    def test_07_controlled_training_fails_if_runtime_authorized_flag_false(self):
        readiness_res = self.certifier.certify_readiness(self.valid_manifest, self.valid_token)
        run_res = self.runner.execute_controlled_training(readiness_res, self.valid_token, authorized_runtime_flag=False)
        self.assertEqual(run_res.final_state, "AUTHORIZATION_FAILED")
        self.assertFalse(run_res.production_promoted)

    def test_08_controlled_training_success_with_authorized_flag(self):
        readiness_res = self.certifier.certify_readiness(self.valid_manifest, self.valid_token)
        run_res = self.runner.execute_controlled_training(readiness_res, self.valid_token, authorized_runtime_flag=True, epochs=1)
        self.assertEqual(run_res.final_state, "TRAINED_CANDIDATE")
        self.assertEqual(run_res.epochs_completed, 1)
        self.assertEqual(len(run_res.checkpoints), 1)
        self.assertEqual(run_res.checkpoints[0].integrity_status, "VERIFIED")
        # Production promotion must remain strictly FALSE
        self.assertFalse(run_res.production_promoted)
        self.assertFalse(run_res.public_chat_eligible)

    def test_09_continuous_governance_abort_on_revocation(self):
        readiness_res = self.certifier.certify_readiness(self.valid_manifest, self.valid_token)
        # Token valid at start, but set to expire almost immediately so mid-loop check fails
        exp_token = SignedTrainingAuthorizationToken(**{**self.valid_token.__dict__, "expires_at_epoch": time.time() - 1})
        # Execute training with authorized_runtime_flag=True and valid readiness_res
        run_res = self.runner.execute_controlled_training(readiness_res, exp_token, authorized_runtime_flag=True, epochs=2)
        # Should abort on authorization check
        self.assertIn(run_res.final_state, ("AUTHORIZATION_FAILED", "TRAINING_ABORTED"))

    def test_10_post_training_evaluation_and_memorization_safety(self):
        readiness_res = self.certifier.certify_readiness(self.valid_manifest, self.valid_token)
        run_res = self.runner.execute_controlled_training(readiness_res, self.valid_token, authorized_runtime_flag=True, epochs=1)

        eval_report = self.evaluator.evaluate_candidate_model(run_res, mock_verbatim_leakage=False)
        self.assertEqual(eval_report.evaluation_status, "PASSED_EVALUATION")
        self.assertGreater(eval_report.candidate_tamil_quality_score, eval_report.base_tamil_quality_score)
        # Production promotion & Public chat must remain strictly FALSE
        self.assertFalse(eval_report.promotion_eligible)
        self.assertFalse(eval_report.public_chat_eligible)

    def test_11_post_training_evaluation_blocks_on_verbatim_memorization(self):
        readiness_res = self.certifier.certify_readiness(self.valid_manifest, self.valid_token)
        run_res = self.runner.execute_controlled_training(readiness_res, self.valid_token, authorized_runtime_flag=True, epochs=1)

        eval_report = self.evaluator.evaluate_candidate_model(run_res, mock_verbatim_leakage=True)
        self.assertEqual(eval_report.evaluation_status, "PROMOTION_BLOCKED")
        self.assertEqual(eval_report.memorization_risk_status, "PROMOTION_BLOCKED")
        self.assertFalse(eval_report.promotion_eligible)


if __name__ == "__main__":
    unittest.main()
