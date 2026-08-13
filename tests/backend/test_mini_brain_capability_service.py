"""MB-04C: service-level tests for MiniBrainCapabilityService.

Uses TEST-ONLY fake backends (never imported by production code), same
discipline as MB-04/MB-04A/MB-04B's own service tests.
"""

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository
from backend.services.mini_brain_capability_service import MiniBrainCapabilityService
from backend.services.mini_brain_intelligence_service import MiniBrainIntelligenceService
from backend.services.mini_brain_knowledge_service import MiniBrainKnowledgeService
from backend.services.mini_brain_prompt_optimization_service import MiniBrainPromptOptimizationService
from backend.services.mini_brain_runtime_manager_service import (
    MiniBrainInMemoryModelLoader,
    reset_runtime_for_tests,
)


class ScriptedBackend:
    """TEST-ONLY -- returns a scripted sequence of responses so
    retry/stability behavior can be controlled deterministically."""

    responses: list[dict] = [{"text": "default", "tokens_generated": 5, "stop_reason": "stop", "response_time_ms": 1.0}]
    call_count = 0

    def is_available(self) -> bool:
        return True

    def load(self, model_path: str, *, context_length: int) -> dict:
        return {"load_time_ms": 1.0}

    def unload(self) -> None:
        pass

    def generate(self, prompt: str, *, max_tokens: int, timeout_seconds: float) -> dict:
        idx = min(ScriptedBackend.call_count, len(ScriptedBackend.responses) - 1)
        response = dict(ScriptedBackend.responses[idx])
        ScriptedBackend.call_count += 1
        return response


@pytest.fixture(autouse=True)
def _reset():
    reset_runtime_for_tests()
    ScriptedBackend.call_count = 0
    ScriptedBackend.responses = [{"text": "default", "tokens_generated": 5, "stop_reason": "stop", "response_time_ms": 1.0}]
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
    runtime = MiniBrainInMemoryModelLoader(backend_factory=ScriptedBackend)

    model_path = tmp_path / "qwen2.5-0.5b-instruct.gguf"
    model_path.write_bytes(b"x" * 10)
    entry = runtime.register_model(name="Qwen2.5-0.5B-Instruct", path=str(model_path), quantization="Q4_K_M", context_length=2048)
    runtime.load_model(entry["public_id"])

    prompt_optimization = MiniBrainPromptOptimizationService(repo, intelligence, runtime, settings)
    return MiniBrainCapabilityService(prompt_optimization)


def test_analyze_never_calls_the_model(wired_service) -> None:
    result = wired_service.analyze("How do I create a dataset?")
    assert result["category"] == "dataset"
    assert ScriptedBackend.call_count == 0


def test_analyze_matches_current_loaded_model_profile(wired_service) -> None:
    result = wired_service.analyze("What is a dataset?")
    assert result["profile"]["matched_key"] == "qwen2.5-0.5b-instruct"
    assert result["profile"]["verified"] is True


def test_generate_uses_strategy_max_tokens_capped_by_profile_ceiling(wired_service) -> None:
    ScriptedBackend.responses = [
        {"text": "A complete, well-formed answer that ends properly with a period.", "tokens_generated": 12, "stop_reason": "stop", "response_time_ms": 1.0},
    ]
    out = wired_service.generate("How do I create a dataset?")
    assert out["max_tokens_used"] <= out["profile"]["response_limits"]["max_tokens_ceiling"]
    assert out["retry"]["attempted"] is False
    assert ScriptedBackend.call_count == 1


def test_generate_retries_exactly_once_on_cut_off_and_picks_better_result(wired_service) -> None:
    ScriptedBackend.responses = [
        {"text": "This answer gets cut off mid", "tokens_generated": 200, "stop_reason": "length", "response_time_ms": 1.0},
        {"text": "This is a complete answer that finishes properly.", "tokens_generated": 12, "stop_reason": "stop", "response_time_ms": 1.0},
    ]
    out = wired_service.generate("How do I create a dataset?")
    assert out["retry"]["attempted"] is True
    assert out["retry"]["decision"]["reason"] == "output_was_cut_off"
    assert ScriptedBackend.call_count == 2
    assert out["response"]["text"] == "This is a complete answer that finishes properly."
    assert out["output_length"]["issues"] == []


def test_generate_never_retries_more_than_once_even_if_retry_also_fails(wired_service) -> None:
    ScriptedBackend.responses = [
        {"text": "Cut off mid", "tokens_generated": 200, "stop_reason": "length", "response_time_ms": 1.0},
    ]
    out = wired_service.generate("How do I create a dataset?")
    assert out["retry"]["attempted"] is True
    assert ScriptedBackend.call_count == 2  # exactly 2, never 3+


def test_generate_never_retries_a_blocked_training_boundary_response(wired_service) -> None:
    ScriptedBackend.responses = [
        {"text": "short", "tokens_generated": 1, "stop_reason": "stop", "response_time_ms": 1.0},
    ]
    out = wired_service.generate("How should tokenizer training begin?")
    assert out["retry"]["decision"]["reason"] == "blocked_response_never_retried"
    assert ScriptedBackend.call_count == 1


def test_warnings_flag_unverified_profile(wired_service, tmp_path: Path) -> None:
    # Register and load a TinyLlama-named model instead -- its profile
    # is explicitly unverified.
    reset_runtime_for_tests()
    from backend.services.mini_brain_runtime_manager_service import MiniBrainInMemoryModelLoader as RM
    runtime = RM(backend_factory=ScriptedBackend)
    model_path = tmp_path / "tinyllama.gguf"
    model_path.write_bytes(b"y" * 10)
    entry = runtime.register_model(name="TinyLlama-1.1B-Chat", path=str(model_path), quantization="Q4_K_M", context_length=2048)
    runtime.load_model(entry["public_id"])
    wired_service.prompt_optimization_service.runtime_manager = runtime

    ScriptedBackend.responses = [
        {"text": "A complete, well-formed answer that ends properly with a period.", "tokens_generated": 12, "stop_reason": "stop", "response_time_ms": 1.0},
    ]
    out = wired_service.generate("What is a dataset?")
    assert "model_profile_unverified_estimates_only" in out["warnings"]


def test_diagnostics_reports_pipeline_capabilities(wired_service) -> None:
    diag = wired_service.diagnostics()
    assert diag["ai_model_used"] is False
    assert diag["database_tables"] == 0
    assert diag["max_retries"] == 1
    assert "qwen2.5-0.5b-instruct" in diag["known_profiles"]


def test_capability_pipeline_never_touches_knowledge_core_admin_assistant_or_public_chat(
    wired_service, tmp_path: Path,
) -> None:
    from backend.database.connection import database_connection

    db_path = wired_service.prompt_optimization_service.settings.resolved_database_path
    with database_connection(db_path) as connection:
        before = connection.execute("SELECT COUNT(*) FROM mini_brain_knowledge_items").fetchone()[0]

    ScriptedBackend.responses = [
        {"text": "A complete, well-formed answer that ends properly with a period.", "tokens_generated": 12, "stop_reason": "stop", "response_time_ms": 1.0},
    ]
    wired_service.generate("What is a dataset?")

    with database_connection(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_approvals").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM inference_model_assignments").fetchone()[0] == 0
        after = connection.execute("SELECT COUNT(*) FROM mini_brain_knowledge_items").fetchone()[0]
        assert after == before
