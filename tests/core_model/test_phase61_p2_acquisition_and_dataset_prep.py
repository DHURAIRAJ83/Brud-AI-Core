"""Phase 61 - P2: Autonomous Legal Tamil Book Acquisition & Dataset Preparation Test Suite."""

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core_model.corpus.book_discovery_engine import BookDiscoveryEngine, DiscoveredBookCandidate
from core_model.corpus.autonomous_book_acquisition import (
    AutonomousBookAcquisitionEngine,
    AcquisitionStateRecord,
    AcquisitionRightsError,
)
from core_model.corpus.format_adapters import EpubAdapter, adapter_for_format
from core_model.corpus.ocr_adapter import TamilOcrAdapter
from core_model.corpus.candidate_dataset_pipeline import CandidateDatasetPipelineOrchestrator
from core_model.admin_assistant.admin_review_queue import AdminReviewQueueManager
from core_model.training.signed_training_gate import SignedTrainingGateEngine, TrainingAuthorizationError


class TestPhase61P2AcquisitionAndDatasetPrep(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path("scratch/test_p2_candidate_acquisitions")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.acquisition_engine = AutonomousBookAcquisitionEngine(candidate_storage_dir=self.test_dir)
        self.discovery_engine = BookDiscoveryEngine()

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_book_discovery_engine_configurable_sources(self):
        sources = self.discovery_engine.get_registered_sources()
        self.assertGreaterEqual(len(sources), 2)
        candidates = self.discovery_engine.discover_legal_books(topic_query="history", limit=2)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].discovery_status, "DISCOVERED")
        self.assertIn("src-", candidates[0].source_id)

    def test_acquisition_rights_verification_strict(self):
        # Public domain -> APPROVED
        eval_pd = self.acquisition_engine.verify_rights_eligibility("PUBLIC_DOMAIN")
        self.assertTrue(eval_pd["rights_verified"])
        self.assertTrue(eval_pd["training_eligible"])

        # Unknown or copyright restricted -> BLOCKED
        eval_unk = self.acquisition_engine.verify_rights_eligibility("LICENSE_UNKNOWN")
        self.assertFalse(eval_unk["rights_verified"])
        self.assertFalse(eval_unk["training_eligible"])

        eval_cr = self.acquisition_engine.verify_rights_eligibility("COPYRIGHT_RESTRICTED")
        self.assertFalse(eval_cr["rights_verified"])

    def test_acquisition_execution_download_to_isolated_storage(self):
        res = self.acquisition_engine.execute_acquisition(
            book_id="book-madurai-001",
            source_id="src-madurai",
            source_url="https://www.projectmadurai.org/pm_works/pdf/pm0001.pdf",
            download_url="https://www.projectmadurai.org/pm_works/pdf/pm0001.pdf",
            rights_status="PUBLIC_DOMAIN",
            file_format="pdf",
            mock_content_bytes=b"%PDF-1.4\n% Project Madurai Tamil Book\n"
        )
        self.assertEqual(res.current_state, "INTEGRITY_VERIFIED")
        self.assertTrue(res.rights_verified)
        self.assertTrue(Path(res.local_path).exists())
        self.assertIsNotNone(res.checksum_sha256)

    def test_epub_format_adapter_extraction(self):
        import zipfile, io
        # Construct mock in-memory EPUB zip archive
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("OEBPS/ch1.html", "<html><body><h1>தமிழ் இலக்கியம்</h1><p>சங்க கால கவிதைகள்.</p></body></html>")
        epub_bytes = buf.getvalue()

        adapter = EpubAdapter()
        inspection = adapter.inspect(epub_bytes)
        self.assertEqual(inspection.warnings, [])

        res = adapter.extract(epub_bytes, MagicMock())
        self.assertIn("தமிழ் இலக்கியம்", res.text)
        self.assertIn("சங்க கால கவிதைகள்", res.text)

    def test_tamil_ocr_adapter_and_normalization(self):
        ocr = TamilOcrAdapter()
        res = ocr.process_scanned_page(mock_raw_text="தமிழ் நூல் 1920\nவரலாறு மற்றும் பண்பாடு\n")
        self.assertIn("தமிழ் நூல்", res.cleaned_text)
        self.assertFalse(res.review_required)

    def test_candidate_dataset_pipeline_full_run(self):
        acquired_books = [
            {
                "book_id": "b1",
                "source_id": "s1",
                "rights_status": "PUBLIC_DOMAIN",
                "extracted_text": "தமிழ் மொழியின் தொன்மை மற்றும் வரலாறு பற்றிய ஆய்வு."
            }
        ]
        pipeline = CandidateDatasetPipelineOrchestrator()
        manifest = pipeline.process_acquired_books_to_candidate(acquired_books, "foundation_stage8_v001")
        self.assertEqual(manifest.dataset_version, "foundation_stage8_v001")
        self.assertEqual(manifest.rights_status, "APPROVED")
        self.assertEqual(manifest.approval_status, "PENDING_ADMIN_REVIEW")
        self.assertFalse(manifest.training_authorized)  # ALWAYS FALSE IN P2

    def test_admin_review_queue_approval_workflow(self):
        queue = AdminReviewQueueManager()
        pipeline = CandidateDatasetPipelineOrchestrator()
        manifest = pipeline.process_acquired_books_to_candidate([
            {"book_id": "b2", "source_id": "s2", "rights_status": "PUBLIC_DOMAIN", "extracted_text": "சங்க இலக்கிய பாட்டுகள்"}
        ])

        review_item = queue.submit_manifest_for_review(manifest, admin_notes="Initial automated submission")
        self.assertEqual(review_item.decision, "PENDING_REVIEW")

        updated = queue.record_admin_decision(review_item.review_id, "APPROVED", reviewed_by="admin-dhurai")
        self.assertEqual(updated.decision, "APPROVED_CANDIDATE")

    def test_training_gate_remains_locked_in_p2(self):
        gate = SignedTrainingGateEngine(runtime_authorized_flag=False)
        with self.assertRaises(TrainingAuthorizationError):
            gate.verify_authorization(None)


if __name__ == "__main__":
    unittest.main()
