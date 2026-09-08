"""Phase 61 - P1: Global Canonical Novelty Ledger, LLM Reasoning, & Signed Training Gate Test Suite."""

import unittest
import time
from unittest.mock import MagicMock

from core_model.corpus.global_novelty_ledger import (
    GlobalCanonicalNoveltyLedgerEngine,
    LineageNode,
    NoveltyAssessmentResult,
)
from core_model.admin_assistant.admin_dataset_reasoning import (
    AdminAssistantDatasetReasoningEngine,
    DatasetPreparationPlan,
)
from core_model.training.signed_training_gate import (
    SignedTrainingAuthorizationToken,
    SignedTrainingGateEngine,
    TrainingAuthorizationError,
    compute_token_signature,
)
from core_model.training.smoke_train import tiny_overfit


class TestPhase61P1GovernanceAndNovelty(unittest.TestCase):

    def setUp(self):
        self.novelty_engine = GlobalCanonicalNoveltyLedgerEngine()

    def test_global_novelty_ledger_new_content(self):
        lineage = LineageNode(
            source_id="src-001",
            book_id="book-100",
            page_id="p-01",
            record_id="rec-001",
            dataset_id="ds-v1",
            native_or_synthetic="NATIVE"
        )
        res = self.novelty_engine.evaluate_record_novelty(
            content="இந்த தமிழ் நூல் ஒரு பழமையான தமிழ் இலக்கியமாகும்.",
            lineage=lineage,
            estimated_tokens=50
        )
        self.assertEqual(res.novelty_status, "TRUE_GLOBAL_NEW")
        self.assertTrue(res.is_novel)
        self.assertEqual(res.new_native_tokens, 50)
        self.assertEqual(res.new_synthetic_tokens, 0)

    def test_global_novelty_ledger_exact_duplicate_zero_tokens(self):
        content = "தமிழ் இலக்கிய வரலாறு மற்றும் இலக்கண ஆய்வு சுருக்கம்."
        lineage = LineageNode(source_id="src-001", book_id="book-101", record_id="rec-002")

        # First ingestion
        res1 = self.novelty_engine.evaluate_record_novelty(content, lineage, 100)
        self.assertEqual(res1.novelty_status, "TRUE_GLOBAL_NEW")

        # Second ingestion (Exact duplicate)
        res2 = self.novelty_engine.evaluate_record_novelty(content, lineage, 100)
        self.assertEqual(res2.novelty_status, "HISTORICAL_DUPLICATE")
        self.assertFalse(res2.is_novel)
        self.assertEqual(res2.new_native_tokens, 0)
        self.assertEqual(res2.token_count, 100)

    def test_global_novelty_ledger_normalized_duplicate_zero_tokens(self):
        content1 = "தமிழ்   மொழியின்   சிறப்புகள்   மற்றும் வரலாறு."
        content2 = "தமிழ் மொழியின் சிறப்புகள் மற்றும் வரலாறு."  # normalized whitespace
        lineage = LineageNode(source_id="src-002", record_id="rec-003")

        res1 = self.novelty_engine.evaluate_record_novelty(content1, lineage, 80)
        res2 = self.novelty_engine.evaluate_record_novelty(content2, lineage, 80)
        self.assertEqual(res2.novelty_status, "NORMALIZED_DUPLICATE")
        self.assertEqual(res2.new_native_tokens, 0)

    def test_three_way_token_accounting_validation(self):
        records = [
            {"record_id": "r1", "content": "தமிழ் இலக்கணம்", "token_count": 2, "novel_token_count": 2},
            {"record_id": "r2", "content": "சங்க காலம்", "token_count": 2, "novel_token_count": 2},
        ]
        res = self.novelty_engine.validate_three_way_token_accounting(records)
        self.assertEqual(res.accounting_status, "PASSED")
        self.assertEqual(res.delta_a_b, 0)

    def test_admin_assistant_dataset_reasoning_advisory_only(self):
        reasoning_engine = AdminAssistantDatasetReasoningEngine()
        plan = reasoning_engine.generate_dataset_prep_plan(
            request_prompt="Prepare 500K native Tamil tokens from Project Madurai",
            target_tokens=500000
        )
        self.assertIsInstance(plan, DatasetPreparationPlan)
        self.assertEqual(len(plan.pipeline_stages), 18)
        # Verify LLM is advisory ONLY and deterministic gates default to unapproved
        self.assertFalse(plan.rights_approved)
        self.assertFalse(plan.novelty_approved)
        self.assertFalse(plan.human_approval_signed)
        self.assertFalse(plan.training_authorized)

    def test_signed_training_gate_unauthorized_abort(self):
        gate = SignedTrainingGateEngine(runtime_authorized_flag=False)
        with self.assertRaises(TrainingAuthorizationError) as ctx:
            gate.verify_authorization(None)
        self.assertIn("TRAINING_EXECUTION_BLOCKED", str(ctx.exception))

    def test_signed_training_gate_valid_token_pass(self):
        secret = "BRUD_GOVERNANCE_SECRET_KEY_2026"
        token_id = "tok-12345"
        admin_id = "admin-dhurai"
        manifest_hash = "manifest-sha256-abc12345"
        sig = compute_token_signature(token_id, admin_id, manifest_hash, secret)

        token = SignedTrainingAuthorizationToken(
            token_id=token_id,
            admin_public_id=admin_id,
            dataset_manifest_hash=manifest_hash,
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

        gate = SignedTrainingGateEngine(runtime_authorized_flag=True, secret_key=secret)
        self.assertTrue(gate.verify_authorization(token, expected_manifest_hash=manifest_hash))

    def test_smoke_train_unauthorized_cli_abort(self):
        mock_model = MagicMock()
        with self.assertRaises(TrainingAuthorizationError) as ctx:
            tiny_overfit(mock_model, [1, 2, 3], pad_token_id=0, steps=1, max_steps=10, authorized=False)
        self.assertIn("TRAINING_EXECUTION_BLOCKED", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
