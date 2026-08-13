"""MB-04: CPU Runtime & Model Integration -- service-level tests.

Uses a TEST-ONLY `FakeInferenceBackend` (defined below, never imported
by production code) to exercise the full Model Manager lifecycle
without requiring `llama-cpp-python` or a real `.gguf` file, neither
of which exists in this environment. Separately,
`test_mini_brain_runtime_api.py` proves the real `LlamaCppBackend`
path is honestly unavailable end-to-end over HTTP.
"""

from pathlib import Path

import pytest

from backend.database.repositories.base import ValidationError
from backend.services.mini_brain_runtime_manager_service import (
    MiniBrainInMemoryModelLoader,
    reset_runtime_for_tests,
)


class FakeInferenceBackend:
    """TEST-ONLY stand-in for `InferenceBackend`. Deterministic, no
    model weights, no subprocess -- never presented as a real model
    anywhere outside this test file."""

    def __init__(self) -> None:
        self.loaded = False

    def is_available(self) -> bool:
        return True

    def load(self, model_path: str, *, context_length: int) -> dict:
        self.loaded = True
        return {"load_time_ms": 5.0}

    def unload(self) -> None:
        self.loaded = False

    def generate(self, prompt: str, *, max_tokens: int, timeout_seconds: float) -> dict:
        return {
            "text": f"fake response for: {prompt[:20]}", "tokens_generated": 8,
            "stop_reason": "stop", "response_time_ms": 3.0,
        }


class UnavailableFakeBackend:
    """TEST-ONLY -- simulates a backend whose library isn't installed."""

    def is_available(self) -> bool:
        return False

    def load(self, model_path: str, *, context_length: int) -> dict:  # pragma: no cover
        raise AssertionError("load() must not be called when is_available() is False")

    def unload(self) -> None:  # pragma: no cover
        pass

    def generate(self, prompt: str, *, max_tokens: int, timeout_seconds: float) -> dict:  # pragma: no cover
        raise AssertionError("generate() must not be called")


@pytest.fixture(autouse=True)
def _reset_runtime():
    reset_runtime_for_tests()
    yield
    reset_runtime_for_tests()


@pytest.fixture
def fixture_model_path(tmp_path: Path) -> str:
    path = tmp_path / "fake-test-model.gguf"
    path.write_bytes(b"NOT A REAL MODEL -- test fixture only" * 50)
    return str(path)


VALID_RESPONSE_PLAN = {
    "suggested_response_type": "explain_with_primary_knowledge",
    "validated_context": {"matched_items": ["Tokenizer Training"], "documentation_references": []},
    "validated_knowledge": {"primary": ["Tokenizer Training"], "supporting": [], "priority_order": []},
    "validated_workflow": {
        "current_step": "Tokenizer Training", "previous_steps": [], "next_steps": ["Bounded Pretraining"],
        "dependencies": [],
    },
    "disclaimers": ["This is Admin-only guidance from Brud Mini Brain, never a Public Chat response."],
    "confidence_band": "high",
    "intent": "tokenizer",
}


def test_registration_rejects_missing_file() -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    with pytest.raises(ValidationError, match="does not exist"):
        mgr.register_model(name="X", path="/nonexistent/path.gguf", quantization="Q4_K_M", context_length=2048)


def test_registration_rejects_wrong_extension(tmp_path: Path) -> None:
    bad = tmp_path / "not-a-model.txt"
    bad.write_text("hello")
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    with pytest.raises(ValidationError, match="gguf extension"):
        mgr.register_model(name="X", path=str(bad), quantization="Q4_K_M", context_length=2048)


def test_registration_accepts_valid_fixture(fixture_model_path: str) -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    entry = mgr.register_model(name="Test Model", path=fixture_model_path, quantization="Q4_K_M", context_length=2048)
    assert entry["name"] == "Test Model"
    assert entry["size_bytes"] > 0
    assert mgr.list_models()["items"][0]["public_id"] == entry["public_id"]


def test_load_unknown_model_is_rejected() -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    with pytest.raises(ValidationError, match="unknown model"):
        mgr.load_model("not-a-real-id")


def test_full_lifecycle_load_generate_unload(fixture_model_path: str) -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    entry = mgr.register_model(name="Test Model", path=fixture_model_path, quantization="Q4_K_M", context_length=2048)

    assert mgr.status()["state"] == "unloaded"

    loaded = mgr.load_model(entry["public_id"])
    assert loaded["state"] == "loaded"
    assert loaded["current_model"]["public_id"] == entry["public_id"]

    response = mgr.generate_response(VALID_RESPONSE_PLAN)
    assert response["text"].startswith("fake response for:")
    assert response["disclaimers"] == VALID_RESPONSE_PLAN["disclaimers"]
    assert response["confidence_band"] == "high"
    assert response["generation_stats"]["tokens_generated"] == 8

    # generation must not leave the runtime stuck in "running"
    assert mgr.status()["state"] == "loaded"
    assert mgr.runtime_statistics()["total_generations"] == 1

    unloaded = mgr.unload_model()
    assert unloaded["state"] == "unloaded"
    assert unloaded["current_model"] is None


def test_generate_without_loaded_model_is_rejected() -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    with pytest.raises(ValidationError, match="cannot generate"):
        mgr.generate_response(VALID_RESPONSE_PLAN)


def test_generate_rejects_payload_that_is_not_a_response_plan(fixture_model_path: str) -> None:
    """Direct proof of the safety rule: the model must never generate
    without a real Response Plan."""

    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    entry = mgr.register_model(name="Test Model", path=fixture_model_path, quantization="Q4_K_M", context_length=2048)
    mgr.load_model(entry["public_id"])
    with pytest.raises(ValidationError, match="not a valid Response Plan"):
        mgr.generate_response({"just_some_text": "please answer my question"})


def test_load_with_unavailable_backend_fails_honestly(fixture_model_path: str) -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=UnavailableFakeBackend)
    entry = mgr.register_model(name="Test Model", path=fixture_model_path, quantization="Q4_K_M", context_length=2048)
    with pytest.raises(ValidationError, match="not available"):
        mgr.load_model(entry["public_id"])
    assert mgr.status()["state"] == "error"


def test_reload_unloads_then_loads_same_model(fixture_model_path: str) -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    entry = mgr.register_model(name="Test Model", path=fixture_model_path, quantization="Q4_K_M", context_length=2048)
    mgr.load_model(entry["public_id"])
    result = mgr.reload_model()
    assert result["state"] == "loaded"
    assert result["current_model"]["public_id"] == entry["public_id"]


def test_switch_model_between_two_registered_models(fixture_model_path: str, tmp_path: Path) -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    first = mgr.register_model(name="Model A", path=fixture_model_path, quantization="Q4_K_M", context_length=2048)
    second_path = tmp_path / "second.gguf"
    second_path.write_bytes(b"NOT A REAL MODEL -- fixture two" * 50)
    second = mgr.register_model(name="Model B", path=str(second_path), quantization="Q8_0", context_length=4096)

    mgr.load_model(first["public_id"])
    switched = mgr.switch_model(second["public_id"])
    assert switched["current_model"]["public_id"] == second["public_id"]


def test_statistics_include_real_cpu_and_memory_measurements() -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    stats = mgr.runtime_statistics()
    assert stats["process_cpu_time_seconds"] >= 0
    assert stats["process_max_rss_kb"] > 0
    assert stats["memory_measurement"] in ("measured", "unmeasurable")


def test_diagnostics_reports_health_by_state(fixture_model_path: str) -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    assert mgr.diagnostics()["health"]["status"] == "idle"
    entry = mgr.register_model(name="Test Model", path=fixture_model_path, quantization="Q4_K_M", context_length=2048)
    mgr.load_model(entry["public_id"])
    assert mgr.diagnostics()["health"]["status"] == "healthy"


def test_model_information_reports_validation_issues_if_file_removed(fixture_model_path: str) -> None:
    mgr = MiniBrainInMemoryModelLoader(backend_factory=FakeInferenceBackend)
    entry = mgr.register_model(name="Test Model", path=fixture_model_path, quantization="Q4_K_M", context_length=2048)
    Path(fixture_model_path).unlink()
    info = mgr.model_information(entry["public_id"])
    assert info["file_exists"] is False
    assert any("does not exist" in issue for issue in info["validation_issues"])
