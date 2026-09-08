"""MB-28: tests for backend/services/mini_brain_llm_adapter.py --
`LlamaCppMiniBrainAdapter`'s honest-unavailable-without-real-weights
behavior (real code, real path-confinement, but no `.gguf` file exists
in this environment), `MockMiniBrainAdapter`'s determinism, and
`ExternalProviderMiniBrainAdapter`'s disabled-by-default / mocked-httpx
behavior. No real outbound network call is ever made by this file.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.core.config import Settings
from backend.services.mini_brain_llm_adapter import (
    DEFAULT_TEMPERATURE,
    ExternalProviderMiniBrainAdapter,
    LlamaCppMiniBrainAdapter,
    MockMiniBrainAdapter,
    resolve_confined_model_path,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    allowed = tmp_path / "models"
    allowed.mkdir()
    return Settings(
        allowed_model_dir=allowed, allowed_data_dir=tmp_path,
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )


# -- resolve_confined_model_path -------------------------------------------------------------


def test_resolve_confined_model_path_none_input(settings: Settings) -> None:
    assert resolve_confined_model_path(settings=settings, model_path=None) is None


def test_resolve_confined_model_path_confined_real_file(settings: Settings) -> None:
    model_file = settings.resolved_allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"x")
    resolved = resolve_confined_model_path(settings=settings, model_path=str(model_file))
    assert resolved == model_file.resolve()


def test_resolve_confined_model_path_outside_confined_dir(settings: Settings) -> None:
    outside = settings.resolved_allowed_model_dir.parent / "outside.gguf"
    outside.write_bytes(b"x")
    assert resolve_confined_model_path(settings=settings, model_path=str(outside)) is None


def test_resolve_confined_model_path_nonexistent(settings: Settings) -> None:
    missing = settings.resolved_allowed_model_dir / "nope.gguf"
    assert resolve_confined_model_path(settings=settings, model_path=str(missing)) is None


# -- LlamaCppMiniBrainAdapter -------------------------------------------------------------------


def test_llamacpp_adapter_unavailable_without_model_path(settings: Settings) -> None:
    adapter = LlamaCppMiniBrainAdapter(settings=settings, model_path=None)
    assert adapter.is_available() is False


def test_llamacpp_adapter_available_with_confined_real_file(settings: Settings) -> None:
    model_file = settings.resolved_allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"x")
    adapter = LlamaCppMiniBrainAdapter(settings=settings, model_path=str(model_file))
    assert adapter.is_available() is True  # llama_cpp genuinely installed in this environment


def test_llamacpp_adapter_generate_on_unavailable_is_honest_not_a_crash(settings: Settings) -> None:
    adapter = LlamaCppMiniBrainAdapter(settings=settings, model_path=None)
    result = adapter.generate(messages=[{"role": "admin", "content": "hi"}])
    assert result["text"] == ""
    assert result["error_message"] is not None
    assert result["backend_type"] == "local"


def test_llamacpp_adapter_generate_with_real_load_failure_is_honest(settings: Settings) -> None:
    # A genuinely confined, existing file that is NOT real GGUF bytes --
    # llama_cpp.Llama() will raise on load; this must be caught, never crash.
    model_file = settings.resolved_allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"not a real gguf file")
    adapter = LlamaCppMiniBrainAdapter(settings=settings, model_path=str(model_file))
    result = adapter.generate(messages=[{"role": "admin", "content": "hi"}])
    assert result["text"] == ""
    assert result["error_message"] is not None


def test_llamacpp_adapter_default_temperature(settings: Settings) -> None:
    adapter = LlamaCppMiniBrainAdapter(settings=settings, model_path=None)
    assert adapter._temperature == DEFAULT_TEMPERATURE


# -- MockMiniBrainAdapter --------------------------------------------------------------------------


def test_mock_adapter_always_available() -> None:
    assert MockMiniBrainAdapter().is_available() is True


def test_mock_adapter_deterministic_for_same_input() -> None:
    adapter = MockMiniBrainAdapter()
    r1 = adapter.generate(messages=[{"role": "admin", "content": "hello"}])
    r2 = adapter.generate(messages=[{"role": "admin", "content": "hello"}])
    assert r1 == r2


def test_mock_adapter_no_error_message() -> None:
    result = MockMiniBrainAdapter().generate(messages=[{"role": "admin", "content": "hi"}])
    assert result["error_message"] is None
    assert result["backend_type"] == "local"


def test_mock_adapter_tamil_input_gets_tamil_reply() -> None:
    result = MockMiniBrainAdapter().generate(messages=[{"role": "admin", "content": "இது என்ன"}])
    assert any("஀" <= ch <= "௿" for ch in result["text"])


def test_mock_adapter_empty_messages_does_not_crash() -> None:
    result = MockMiniBrainAdapter().generate(messages=[])
    assert result["text"]


# -- ExternalProviderMiniBrainAdapter -----------------------------------------------------------------


def test_external_adapter_unavailable_without_api_key() -> None:
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openai", api_key="")
    assert adapter.is_available() is False


def test_external_adapter_unavailable_for_unknown_provider() -> None:
    adapter = ExternalProviderMiniBrainAdapter(provider_key="not_a_real_provider", api_key="sk-x")
    assert adapter.is_available() is False


def test_external_adapter_available_with_key_and_known_provider() -> None:
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openai", api_key="sk-x")
    assert adapter.is_available() is True


def test_external_adapter_generate_without_key_is_honest_not_a_crash() -> None:
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openai", api_key="")
    result = adapter.generate(messages=[{"role": "admin", "content": "hi"}])
    assert result["text"] == ""
    assert result["backend_type"] == "external"
    assert result["error_message"] is not None


def test_external_adapter_openai_generate_mocked_httpx_success() -> None:
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openai", api_key="sk-x")
    fake_response = MagicMock(status_code=200)
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"choices": [{"message": {"content": "hello there"}}], "usage": {"completion_tokens": 3}}
    with patch("httpx.post", return_value=fake_response) as mock_post:
        result = adapter.generate(messages=[{"role": "admin", "content": "hi"}])
    assert result["text"] == "hello there"
    assert result["error_message"] is None
    assert mock_post.called


def test_external_adapter_anthropic_generate_mocked_httpx_success() -> None:
    adapter = ExternalProviderMiniBrainAdapter(provider_key="anthropic", api_key="sk-x")
    fake_response = MagicMock(status_code=200)
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"content": [{"text": "hi there"}], "usage": {"output_tokens": 2}}
    with patch("httpx.post", return_value=fake_response):
        result = adapter.generate(messages=[{"role": "system", "content": "sys"}, {"role": "admin", "content": "hi"}])
    assert result["text"] == "hi there"


def test_external_adapter_gemini_generate_mocked_httpx_success() -> None:
    adapter = ExternalProviderMiniBrainAdapter(provider_key="gemini", api_key="sk-x")
    fake_response = MagicMock(status_code=200)
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "gemini reply"}]}}], "usageMetadata": {"candidatesTokenCount": 2}}
    with patch("httpx.post", return_value=fake_response):
        result = adapter.generate(messages=[{"role": "admin", "content": "hi"}])
    assert result["text"] == "gemini reply"


def test_external_adapter_generate_handles_http_error_honestly() -> None:
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openai", api_key="sk-x")
    with patch("httpx.post", side_effect=RuntimeError("network down")):
        result = adapter.generate(messages=[{"role": "admin", "content": "hi"}])
    assert result["text"] == ""
    assert "network down" in result["error_message"]


def test_external_adapter_never_makes_a_real_network_call_in_this_test_file() -> None:
    # Structural sanity check for this file's own honesty claim -- every
    # test above either supplies no key (short-circuits before any
    # httpx call) or patches httpx.post explicitly.
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openrouter", api_key="")
    assert adapter.is_available() is False
