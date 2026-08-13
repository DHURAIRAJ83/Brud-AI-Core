"""MB-04B: service-level tests for MiniBrainQualityService.

Uses a TEST-ONLY `FakeInferenceBackend` (never imported by production
code), same discipline as MB-04's and MB-04A's own service tests --
fast, deterministic, no real model or `llama-cpp-python` required.
"""

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository
from backend.services.mini_brain_intelligence_service import MiniBrainIntelligenceService
from backend.services.mini_brain_knowledge_service import MiniBrainKnowledgeService
from backend.services.mini_brain_prompt_optimization_service import MiniBrainPromptOptimizationService
from backend.services.mini_brain_quality_service import MiniBrainQualityService
from backend.services.mini_brain_runtime_manager_service import (
    MiniBrainInMemoryModelLoader,
    reset_runtime_for_tests,
)


class FakeInferenceBackend:
    """TEST-ONLY -- returns a scripted response so echo/quality
    behavior can be controlled deterministically."""

    responses: list[str] = ["default response"]
    call_count = 0

    def is_available(self) -> bool:
        return True

    def load(self, model_path: str, *, context_length: int) -> dict:
        return {"load_time_ms": 1.0}

    def unload(self) -> None:
        pass

    def generate(self, prompt: str, *, max_tokens: int, timeout_seconds: float) -> dict:
        idx = min(FakeInferenceBackend.call_count, len(FakeInferenceBackend.responses) - 1)
        text = FakeInferenceBackend.responses[idx]
        FakeInferenceBackend.call_count += 1
        return {"text": text, "tokens_generated": 5, "stop_reason": "stop", "response_time_ms": 1.0}


@pytest.fixture(autouse=True)
def _reset():
    reset_runtime_for_tests()
    FakeInferenceBackend.call_count = 0
    FakeInferenceBackend.responses = ["default response"]
    yield
    reset_runtime_for_tests()


@pytest.fixture
def wired_service(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "t.db", database_backup_dir=tmp_path / "b",
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    repo = MiniBrainKnowledgeRepository(settings.resolved_database_path)
    MiniBrainKnowledgeService(repo, settings).seed_defaults("test-admin")
    intelligence = MiniBrainIntelligenceService(repo, settings)
    runtime = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)

    model_path = tmp_path / "fake.gguf"
    model_path.write_bytes(b"x" * 10)
    entry = runtime.register_model(name="fake", path=str(model_path), quantization="Q4_K_M", context_length=2048)
    runtime.load_model(entry["public_id"])

    prompt_optimization = MiniBrainPromptOptimizationService(repo, intelligence, runtime, settings)
    return MiniBrainQualityService(prompt_optimization)


def test_check_detects_and_cleans_a_real_echo_pattern(wired_service) -> None:
    prompt = "Role: You are an assistant.\n\nTask: explain things.\n\nAnswer:"
    response = "Role: You are an assistant.\n\nTask: explain things.\n\nAnswer: The real content goes here and is long enough."
    result = wired_service.check(response, prompt_text=prompt, expected_output_language="english")
    assert result["echo"]["echo_detected"] is True
    assert "real content goes here" in result["final_text"]
    assert "echo_removed" in result["actions_performed"]
    assert result["processing_time_ms"] >= 0


def test_check_never_calls_the_model(wired_service) -> None:
    wired_service.check("Some response text.", prompt_text="Some prompt.")
    assert FakeInferenceBackend.call_count == 0


def test_check_runs_tamil_validator_only_when_expected_language_is_tamil(wired_service) -> None:
    result_en = wired_service.check("English text here.", expected_output_language="english")
    assert result_en["tamil_fluency"] is None

    result_ta = wired_service.check("தமிழ் உரை இது ஒரு சோதனை", expected_output_language="tamil")
    assert result_ta["tamil_fluency"] is not None


def test_validate_only_never_modifies_text(wired_service) -> None:
    text = "word   with  extra spaces.No space here."
    result = wired_service.validate_only(text, expected_output_language="english")
    assert "final_text" not in result
    assert result["formatting"]["passed"] is False


def test_generate_and_check_composes_prompt_optimization_service(wired_service) -> None:
    FakeInferenceBackend.responses = ["A genuine on-topic answer about datasets and duplicate detection here."]
    out = wired_service.generate_and_check("How does dataset duplicate detection work?")
    assert out["question"] == "How does dataset duplicate detection work?"
    assert "response_plan" in out
    assert "quality" in out
    assert FakeInferenceBackend.call_count == 1


def test_generate_and_check_flags_a_real_echo_from_the_model(wired_service) -> None:
    # Capture the real prompt the service builds, then script the fake
    # backend to echo the tail of that exact prompt -- proving the
    # service wires the ACTUAL prompt (not a copy) into echo detection.
    built = wired_service.prompt_optimization_service.build_optimized_prompt("What is dataset duplicate detection?")
    FakeInferenceBackend.responses = [built["prompt"][-60:] + " extra"]
    out = wired_service.generate_and_check("What is dataset duplicate detection?")
    assert out["quality"]["echo"]["echo_detected"] is True


def test_diagnostics_reports_pipeline_capabilities(wired_service) -> None:
    diag = wired_service.diagnostics()
    assert diag["ai_model_used"] is False
    assert diag["database_tables"] == 0
    assert "echo_detector" in diag["pipeline_stages"]


def test_quality_pipeline_never_touches_knowledge_core_admin_assistant_or_public_chat(
    wired_service, tmp_path: Path,
) -> None:
    from backend.database.connection import database_connection

    db_path = wired_service.prompt_optimization_service.settings.resolved_database_path
    with database_connection(db_path) as connection:
        knowledge_items_before = connection.execute("SELECT COUNT(*) FROM mini_brain_knowledge_items").fetchone()[0]

    FakeInferenceBackend.responses = ["A genuine on-topic answer here."]
    wired_service.generate_and_check("What is a dataset?")

    with database_connection(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_approvals").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM inference_model_assignments").fetchone()[0] == 0
        knowledge_items_after = connection.execute("SELECT COUNT(*) FROM mini_brain_knowledge_items").fetchone()[0]
        assert knowledge_items_after == knowledge_items_before
