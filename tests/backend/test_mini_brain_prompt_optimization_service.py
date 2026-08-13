"""MB-04A: service-level tests for MiniBrainPromptOptimizationService.

Uses a TEST-ONLY `FakeInferenceBackend` (never imported by production
code), same discipline as MB-04's own
`test_mini_brain_runtime_service.py` -- fast, deterministic, no real
model or `llama-cpp-python` required.
"""

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository
from backend.services.mini_brain_intelligence_service import MiniBrainIntelligenceService
from backend.services.mini_brain_knowledge_service import MiniBrainKnowledgeService
from backend.services.mini_brain_prompt_optimization_service import MiniBrainPromptOptimizationService
from backend.services.mini_brain_runtime_manager_service import (
    MiniBrainInMemoryModelLoader,
    reset_runtime_for_tests,
)


class FakeInferenceBackend:
    """TEST-ONLY -- returns a scripted response so validator behavior
    (pass / rebuild-once) can be controlled deterministically."""

    responses: list[str] = ["default response"]
    call_count = 0

    def __init__(self) -> None:
        pass

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

    return MiniBrainPromptOptimizationService(repo, intelligence, runtime, settings)


def test_build_optimized_prompt_is_pure_no_generation(wired_service) -> None:
    built = wired_service.build_optimized_prompt("How do I create a dataset?")
    assert "Role:" in built["prompt"]
    assert built["output_language"] == "english"
    assert FakeInferenceBackend.call_count == 0


def test_optimize_and_generate_passes_prebuilt_prompt_to_runtime(wired_service) -> None:
    FakeInferenceBackend.responses = ["This is an English answer about datasets."]
    result = wired_service.optimize_and_generate("How do I create a dataset?")
    assert result["rebuilt"] is False
    assert FakeInferenceBackend.call_count == 1
    assert "Role:" in result["prompt_used"]
    assert result["validation"]["passed"] is True


def test_rebuild_triggers_exactly_once_on_language_mismatch(wired_service) -> None:
    # Tamil question -> Tamil expected, but the fake backend answers in
    # English both times -- validation must fail both times, but the
    # service must attempt exactly ONE rebuild, never more.
    FakeInferenceBackend.responses = ["English answer.", "Still English answer."]
    result = wired_service.optimize_and_generate("தமிழில் dataset எப்படி உருவாக்குவது?")
    assert result["rebuilt"] is True
    assert FakeInferenceBackend.call_count == 2
    assert result["validation"]["passed"] is False
    assert "IMPORTANT" in result["prompt_used"]


def test_no_rebuild_when_first_response_already_matches_language(wired_service) -> None:
    FakeInferenceBackend.responses = ["தமிழில் பதில் இது."]
    result = wired_service.optimize_and_generate("தமிழில் dataset எப்படி உருவாக்குவது?")
    assert result["rebuilt"] is False
    assert FakeInferenceBackend.call_count == 1
    assert result["validation"]["passed"] is True


def test_language_detect_helper_matches_pure_module(wired_service) -> None:
    result = wired_service.language_detect("dataset epadi prepare pannalam?")
    assert result["language"] == "tanglish"
    assert result["resolved_output_language"] == "tamil"
    assert result["tanglish_normalized_internal"] is not None


def test_knowledge_grounding_pulls_real_seeded_descriptions(wired_service) -> None:
    built = wired_service.build_optimized_prompt("How does dataset duplicate detection work?")
    assert built["template_category"] == "dataset"
    # At least one real MB-02 seeded item description should have made
    # it into the prompt, not just a bare title.
    assert ":" in built["prompt"].split("Knowledge:")[1].split("Workflow:")[0]
