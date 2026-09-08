"""Phase 61 - P3: High-Throughput Distributed Ingestion & Dataset Compilation Test Suite."""

import unittest
from pathlib import Path

from core_model.corpus.high_throughput_ingestion import (
    HighThroughputIngestionEngine,
    IngestionTask,
)
from core_model.corpus.dataset_compiler import HighThroughputDatasetCompiler
from core_model.admin_assistant.admin_dataset_reasoning import AdminAssistantDatasetReasoningEngine
from core_model.training.signed_training_gate import SignedTrainingGateEngine, TrainingAuthorizationError


class TestPhase61P3HighThroughputCompilation(unittest.TestCase):

    def setUp(self):
        self.ingestion_engine = HighThroughputIngestionEngine(max_workers=4)
        self.compiler = HighThroughputDatasetCompiler(target_token_goal=1000000)

    def test_worker_concurrency_and_batch_execution(self):
        tasks = [
            IngestionTask(
                task_id=f"t-{i}",
                task_key=self.ingestion_engine.generate_task_key("src-01", f"book-{i}"),
                book_id=f"book-{i}",
                source_id="src-01",
                rights_status="PUBLIC_DOMAIN",
                download_url=f"https://example.org/download/{i}.pdf",
                mock_raw_text=f"தமிழ் வரலாறு அத்தியாயம் {i}"
            )
            for i in range(5)
        ]

        summary = self.ingestion_engine.execute_batch_ingestion(tasks, batch_id="batch-test-01")
        self.assertEqual(summary.total_tasks, 5)
        self.assertEqual(summary.completed_tasks, 5)
        self.assertEqual(summary.status, "COMPLETED")
        self.assertGreater(summary.throughput_books_per_sec, 0.0)

    def test_idempotency_skip_duplicate_tasks(self):
        tkey = self.ingestion_engine.generate_task_key("src-01", "book-dup-1")
        task1 = IngestionTask(
            task_id="t-dup-1",
            task_key=tkey,
            book_id="book-dup-1",
            source_id="src-01",
            rights_status="PUBLIC_DOMAIN",
            download_url="https://example.org/download/dup.pdf",
            mock_raw_text="தமிழ் இலக்கியம்"
        )
        res1 = self.ingestion_engine.process_single_task(task1)
        self.assertEqual(res1.status, "COMPLETED")

        # Second submission of same task key
        task2 = IngestionTask(
            task_id="t-dup-2",
            task_key=tkey,
            book_id="book-dup-1",
            source_id="src-01",
            rights_status="PUBLIC_DOMAIN",
            download_url="https://example.org/download/dup.pdf",
            mock_raw_text="தமிழ் இலக்கியம்"
        )
        res2 = self.ingestion_engine.process_single_task(task2)
        self.assertEqual(res2.status, "COMPLETED")
        self.assertTrue(res2.result_data.get("idempotent_skip"))

    def test_failure_isolation_quarantine_bad_task(self):
        tasks = [
            IngestionTask(
                task_id="t-good",
                task_key=self.ingestion_engine.generate_task_key("src-01", "b-good"),
                book_id="b-good",
                source_id="src-01",
                rights_status="PUBLIC_DOMAIN",
                download_url="https://example.org/good.pdf",
                mock_raw_text="தமிழ் கவிதை"
            ),
            IngestionTask(
                task_id="t-bad-rights",
                task_key=self.ingestion_engine.generate_task_key("src-01", "b-bad"),
                book_id="b-bad",
                source_id="src-01",
                rights_status="LICENSE_UNKNOWN",  # Should be quarantined
                download_url="https://example.org/bad.pdf",
                mock_raw_text="காப்புரிமை பெற்ற நூல்"
            )
        ]

        summary = self.ingestion_engine.execute_batch_ingestion(tasks, batch_id="batch-fail-iso")
        self.assertEqual(summary.completed_tasks, 1)
        self.assertEqual(summary.quarantined_tasks, 1)
        self.assertEqual(summary.status, "COMPLETED_WITH_EXCEPTIONS")

    def test_compiler_novelty_atomicity_and_zero_duplicate_count(self):
        # Create completed tasks with identical content
        t1 = IngestionTask(
            task_id="t-nov-1",
            task_key=self.ingestion_engine.generate_task_key("src-01", "b-nov-1"),
            book_id="b-nov-1",
            source_id="src-01",
            rights_status="PUBLIC_DOMAIN",
            download_url="https://example.org/nov1.pdf",
            mock_raw_text="தமிழ் மொழியின் பழமை வரலாறு"
        )
        t2 = IngestionTask(
            task_id="t-nov-2",
            task_key=self.ingestion_engine.generate_task_key("src-01", "b-nov-2"),
            book_id="b-nov-2",
            source_id="src-01",
            rights_status="PUBLIC_DOMAIN",
            download_url="https://example.org/nov2.pdf",
            mock_raw_text="தமிழ் மொழியின் பழமை வரலாறு"  # Duplicate content
        )

        res1 = self.ingestion_engine.process_single_task(t1)
        res2 = self.ingestion_engine.process_single_task(t2)

        manifest = self.compiler.compile_candidate_dataset([res1, res2], dataset_version="foundation_stage8_v001")
        self.assertEqual(manifest.state, "PENDING_ADMIN_REVIEW")
        self.assertEqual(manifest.book_count, 2)
        # Novelty atomicity: only 1st record counts true new tokens, duplicate record yields 0 new tokens
        self.assertEqual(manifest.true_new_tokens, 4)  # "தமிழ் மொழியின் பழமை வரலாறு" = 4 words
        self.assertEqual(manifest.token_accounting_status, "PASSED")

    def test_compiler_domain_distribution_and_gap_analysis(self):
        t = IngestionTask(
            task_id="t-dom",
            task_key=self.ingestion_engine.generate_task_key("src-01", "b-dom"),
            book_id="b-dom",
            source_id="src-01",
            rights_status="PUBLIC_DOMAIN",
            download_url="https://example.org/dom.pdf",
            mock_raw_text="பண்டைய தமிழ் வரலாறு மற்றும் தொல்பொருள் சான்றுகள்"
        )
        res = self.ingestion_engine.process_single_task(t)
        manifest = self.compiler.compile_candidate_dataset([res], dataset_version="foundation_stage8_v002")

        reasoning = AdminAssistantDatasetReasoningEngine()
        gap_report = reasoning.analyze_domain_gaps_and_recommend_sources(
            domain_distribution=manifest.domain_distribution,
            target_token_goal=1000000,
            true_new_tokens=manifest.true_new_tokens
        )
        self.assertEqual(gap_report["target_token_goal"], 1000000)
        self.assertIn("underrepresented_domains", gap_report)

    def test_training_gate_hard_locked_in_p3(self):
        gate = SignedTrainingGateEngine(runtime_authorized_flag=False)
        with self.assertRaises(TrainingAuthorizationError):
            gate.verify_authorization(None)


if __name__ == "__main__":
    unittest.main()
