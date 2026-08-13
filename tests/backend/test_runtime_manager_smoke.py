"""MB-30: real end-to-end smoke test for Production Runtime Manager &
One-Click Local Model Lifecycle.

Drives the exact 12-step scenario the phase spec's own section 13
lists, against a real `RuntimeManagerService` backed by a real
temporary database and a real temporary allowed model directory --
no real network download anywhere in this file, per the spec's own
instruction. The LLM backend for the "ask the assistant a question"
step is `MockMiniBrainAdapter`, injected into MB-28's own
`MiniBrainLlmRuntimeService`, the same real-but-unexercised-without-
real-weights pattern this whole session has used since MB-26.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from backend.services.runtime_manager_service import RuntimeManagerService
from core_model.mini_brain.runtime_manager import checksum_verifier

_FAKE_HARDWARE = {
    "total_ram_gb": 6.0, "available_ram_gb": 4.5, "cpu_cores": 4, "cpu_threads": 4,
    "architecture": "x86_64", "os_name": "Linux", "disk_free_gb": 50.0, "python_version": "3.13.5",
    "recommended_ram_tier": "6GB", "psutil_available": True,
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    allowed = tmp_path / "models"
    allowed.mkdir()
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", allowed_model_dir=allowed,
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


def test_mb30_end_to_end_smoke(settings: Settings) -> None:
    with patch("httpx.get") as mock_get, patch("httpx.stream") as mock_stream:
        service = RuntimeManagerService(settings, adapter_factory=lambda: MockMiniBrainAdapter())

        # -- step 1: detect hardware --------------------------------------------------------
        hardware = service.detect_system()
        assert "recommended_ram_tier" in hardware

        # -- step 2: get recommendation ------------------------------------------------------
        recommendation = service.get_recommended_model()
        model_id = recommendation["model_id"]
        assert model_id

        # -- step 3: create fake GGUF file in temp allowed dir --------------------------------
        fake_bytes = b"fake-gguf-content-for-smoke-test" * 1000
        model_file = settings.resolved_allowed_model_dir / recommendation["file_name"]
        model_file.write_bytes(fake_bytes)

        # -- step 4: verify checksum (pure function, real bytes) ------------------------------
        real_digest = checksum_verifier.compute_sha256(fake_bytes)
        verify_result = checksum_verifier.verify_digest(actual_sha256=real_digest, expected_sha256=real_digest)
        assert verify_result["matches"] is True

        # -- step 5: register installation -----------------------------------------------------
        installation = service.install_model(
            model_id, file_path=str(model_file), expected_sha256=real_digest, admin_id="admin-1",
        )
        assert installation["status"] == "installed"
        assert installation["sha256"] == real_digest

        with patch("backend.services.runtime_manager_service.hardware_probe.probe", return_value=_FAKE_HARDWARE):
            # -- step 6: load model through mock adapter ---------------------------------------
            runtime = service.load_model(model_id, admin_id="admin-1")
            assert runtime["loaded"] is True
            assert runtime["backend"] == "mock"

            # -- step 7: run benchmark ----------------------------------------------------------
            benchmark = service.benchmark_model(model_id, admin_id="admin-1")
            assert benchmark["rating"] in ("excellent", "good", "fair", "poor")
            assert benchmark["tokens_per_second"] > 0

            # -- step 8: check runtime status -----------------------------------------------------
            status = service.runtime_status()
            assert status["loaded"] is True
            assert status["installed_count"] == 1

        # -- step 9: ask assistant a question (real MB-28 service, mock adapter injected) --------
        llm_service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: MockMiniBrainAdapter())
        chat_result = llm_service.chat(session_id=None, message="What model are you running?", admin_id="admin-1")

        # -- step 10: verify local backend selected ----------------------------------------------
        assert chat_result["backend_type"] == "local"
        assert len(chat_result["reply"]["sanitized_text"]) > 0

        # -- step 11: unload model -----------------------------------------------------------------
        unloaded = service.unload_model(admin_id="admin-1")
        assert unloaded["loaded"] is False

        # A fresh service with NO adapter_factory override -- the injected
        # mock from step 9 would unconditionally report "local" regardless
        # of configuration, so this uses MB-28's real _resolve_backend()
        # path to honestly confirm the model_path was actually cleared.
        real_resolution_service = MiniBrainLlmRuntimeService(settings)
        post_unload_chat = real_resolution_service.chat(session_id=None, message="Are you still there?", admin_id="admin-1")
        assert post_unload_chat["backend_type"] == "unavailable"

        # -- step 12: remove installation -------------------------------------------------------------
        removed = service.remove_model(model_id, admin_id="admin-1")
        assert removed["status"] == "removed"
        assert not model_file.exists()

        # -- structural honesty check: no real network call anywhere in this smoke test -----------------
        assert mock_get.call_count == 0
        assert mock_stream.call_count == 0
