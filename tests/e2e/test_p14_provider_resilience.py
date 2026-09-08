"""P14.4 Provider Resilience & Failover Test Suite.

Verifies:
1. configured != available invariant (Ollama & LlamaCpp).
2. Jittered retry backoff on transient HTTP errors (429, 502, 503, 504, timeout).
3. Truth-first error categorization and zero secret leakage in error strings.
4. Auto-mode provider failover (primary failure -> retry -> secondary -> ledger event).
5. Provider exhaustion truthfulness when all candidates fail or are unavailable.
6. SSE streaming provider failover.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.mini_brain_llm_runtime import MiniBrainLlmRuntimeRepository
from backend.database.repositories.mini_brain_provider_settings import MiniBrainProviderSettingsRepository
from backend.main import create_app
from backend.services.mini_brain_llm_adapter import (
    ExternalProviderMiniBrainAdapter,
    LlamaCppMiniBrainAdapter,
    categorize_http_error,
    sanitize_error_message,
)
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService


from cryptography.fernet import Fernet
from core_model.mini_brain.provider_settings import secret_encryptor


@pytest.fixture
def p14_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "p14_resilience.db"
    storage_dir = tmp_path / "storage"
    model_dir = tmp_path / "models"
    storage_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, key)

    settings = Settings(
        database_path=db_path,
        storage_dir=storage_dir,
        allowed_model_dir=model_dir,
        allow_external_storage=True,
        jwt_secret="p14_test_jwt_secret_key_at_least_32_chars_long_12345",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def test_p14_resilience_001_configured_not_equal_available_ollama():
    """Verify configured != available: Ollama endpoint is configured, but unavailable when daemon is not running."""
    adapter = ExternalProviderMiniBrainAdapter(provider_key="ollama", api_key="", model="llama3")
    assert adapter.is_configured() is True, "Ollama must report is_configured() True"
    # When port 11434 is not open or unreachable, probe fails -> is_available() is False
    with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
        assert adapter.is_available() is False, "Ollama must report is_available() False when probe fails"


def test_p14_resilience_002_configured_not_equal_available_llamacpp(p14_env: Settings):
    """Verify configured != available: model_path is configured in settings, but unavailable when .gguf weights are absent."""
    non_existent_model = "non_existent_weights.gguf"
    adapter = LlamaCppMiniBrainAdapter(settings=p14_env, model_path=non_existent_model)
    assert adapter.is_configured() is True, "LlamaCpp must report is_configured() True when model_path is set"
    assert adapter.is_available() is False, "LlamaCpp must report is_available() False when model file does not exist"


def test_p14_resilience_003_retry_loop_backoff_jitter_on_transient_http():
    """Verify bounded exponential retry loop with jitter succeeds after transient errors."""
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openai", api_key="sk-test-mock-key-12345")
    assert adapter.is_available() is True

    # Simulate 2 transient 503 errors followed by a 200 OK success
    attempt_count = 0
    resp_503 = httpx.Response(503, text="Service Unavailable", request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
    resp_200 = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "Resilient response after retry"}}], "usage": {"completion_tokens": 5}},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )

    def mock_post(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            return resp_503
        return resp_200

    with patch("httpx.post", side_effect=mock_post):
        with patch("time.sleep") as mock_sleep:
            res = adapter.generate(messages=[{"role": "user", "content": "Hello"}])
            assert res["error_message"] is None
            assert res["text"] == "Resilient response after retry"
            assert attempt_count == 3
            assert mock_sleep.call_count == 2
            # Verify backoff sleeps were bounded with jitter
            for call in mock_sleep.call_args_list:
                sleep_duration = call[0][0]
                assert 0.2 <= sleep_duration <= 1.5, f"Sleep duration {sleep_duration} outside expected bounded range"


def test_p14_resilience_004_categorized_errors_and_zero_secret_leakage():
    """Verify normalized error categories and strict redaction of sensitive query params in error strings."""
    assert categorize_http_error(429) == "RATE_LIMIT_429"
    assert categorize_http_error(502) == "BAD_GATEWAY_502"
    assert categorize_http_error(503) == "SERVICE_UNAVAILABLE_503"
    assert categorize_http_error(504) == "GATEWAY_TIMEOUT_504"

    # Secret sanitization test
    leak_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5?key=AIzaSySecretApiKey12345&other=ok"
    sanitized = sanitize_error_message(f"Failed to connect to {leak_url}")
    assert "AIzaSySecretApiKey12345" not in sanitized
    assert "key=[REDACTED]" in sanitized

    bearer_leak = "Request failed with Authorization: Bearer sk-ant-secret-long-token-987654321"
    sanitized_bearer = sanitize_error_message(bearer_leak)
    assert "sk-ant-secret" not in sanitized_bearer
    assert "Bearer [REDACTED]" in sanitized_bearer


def test_p14_resilience_005_failover_primary_to_secondary_and_ledger_event(p14_env: Settings):
    """Verify that when primary provider fails after retries in auto mode, service fails over to secondary provider and logs provider_failover event."""
    svc = MiniBrainLlmRuntimeService(p14_env)

    # Seed two external providers: primary openrouter (which will fail), secondary openai (which will succeed)
    with svc._provider_repository.transaction() as conn:
        from core_model.mini_brain.provider_settings import secret_encryptor
        enc_key1 = secret_encryptor.encrypt_secret("sk-or-primary-secret-key-12345")
        enc_key2 = secret_encryptor.encrypt_secret("sk-oa-secondary-secret-key-67890")
        p1_id = svc._provider_repository.create_setting(
            conn,
            provider_type="external_ai",
            provider_key="openrouter",
            enabled=True,
            config={"model": "deepseek-chat"},
        )
        svc._provider_repository.upsert_secret(conn, setting_public_id=p1_id, secret_name="api_key", encrypted_value=enc_key1)

        p2_id = svc._provider_repository.create_setting(
            conn,
            provider_type="external_ai",
            provider_key="openai",
            enabled=True,
            config={"model": "gpt-4o-mini"},
        )
        svc._provider_repository.upsert_secret(conn, setting_public_id=p2_id, secret_name="api_key", encrypted_value=enc_key2)

    # Primary openrouter will fail with 502, secondary openai will succeed
    resp_502 = httpx.Response(502, text="Bad Gateway", request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"))
    resp_200 = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "Successful reply from secondary OpenAI provider"}}], "usage": {"completion_tokens": 7}},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )

    def mock_post(url, *args, **kwargs):
        if "openrouter" in str(url):
            return resp_502
        return resp_200

    with patch("httpx.post", side_effect=mock_post):
        res = svc.chat(
            session_id=None,
            message="Test resilience failover",
            admin_id="adm_tester_resilience",
            execution_mode="auto",
        )

        assert res["reply"]["sanitized_text"] == "Successful reply from secondary OpenAI provider"
        assert res["backend_type"] == "external"

        # Verify provider_failover event in event ledger
        session_id = res["session"]["public_id"]
        with svc.repository.transaction() as conn:
            events = svc.repository.list_events(conn, session_id=session_id, limit=20, offset=0)
            failover_events = [e for e in events if e["event_type"] == "provider_failover"]
            assert len(failover_events) >= 1, "Must record at least one provider_failover event in event ledger"
            raw_detail = failover_events[0]["detail_json"]
            detail = json.loads(raw_detail) if isinstance(raw_detail, str) else raw_detail
            assert detail["from_provider"] == "openrouter"
            assert detail["to_provider"] == "openai"
            assert "BAD_GATEWAY_502" in detail["failure_reason"]


def test_p14_resilience_006_failover_all_exhaustion(p14_env: Settings):
    """Verify that when all candidates fail or are unavailable, service returns truthful PROVIDER_EXHAUSTION."""
    svc = MiniBrainLlmRuntimeService(p14_env)

    # Seed one external provider that will fail
    with svc._provider_repository.transaction() as conn:
        from core_model.mini_brain.provider_settings import secret_encryptor
        enc_key = secret_encryptor.encrypt_secret("sk-test-exhaust-key-12345")
        p_id = svc._provider_repository.create_setting(
            conn,
            provider_type="external_ai",
            provider_key="openai",
            enabled=True,
            config={"model": "gpt-4o-mini"},
        )
        svc._provider_repository.upsert_secret(conn, setting_public_id=p_id, secret_name="api_key", encrypted_value=enc_key)

    resp_503 = httpx.Response(503, text="Service Unavailable", request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))

    with patch("httpx.post", return_value=resp_503):
        # Ollama probe will also fail
        with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
            res = svc.chat(
                session_id=None,
                message="Test exhaustion",
                admin_id="adm_tester_resilience",
                execution_mode="auto",
            )

            assert res["backend_type"] == "unavailable"
            assert "PROVIDER_EXHAUSTION" in res["reply"]["sanitized_text"]


def test_p14_resilience_007_stream_chat_failover(p14_env: Settings):
    """Verify stream_chat fails over to secondary candidate when primary fails on stream initiation."""
    svc = MiniBrainLlmRuntimeService(p14_env)

    with svc._provider_repository.transaction() as conn:
        from core_model.mini_brain.provider_settings import secret_encryptor
        enc_key1 = secret_encryptor.encrypt_secret("sk-or-primary-secret-key-12345")
        enc_key2 = secret_encryptor.encrypt_secret("sk-oa-secondary-secret-key-67890")
        p1_id = svc._provider_repository.create_setting(
            conn,
            provider_type="external_ai",
            provider_key="openrouter",
            enabled=True,
            config={"model": "deepseek-chat"},
        )
        svc._provider_repository.upsert_secret(conn, setting_public_id=p1_id, secret_name="api_key", encrypted_value=enc_key1)

        p2_id = svc._provider_repository.create_setting(
            conn,
            provider_type="external_ai",
            provider_key="openai",
            enabled=True,
            config={"model": "gpt-4o-mini"},
        )
        svc._provider_repository.upsert_secret(conn, setting_public_id=p2_id, secret_name="api_key", encrypted_value=enc_key2)

    # Primary openrouter stream raises ConnectError, secondary openai stream succeeds
    lines_200 = [
        b'data: {"choices": [{"delta": {"content": "Streamed "}}]}',
        b'data: {"choices": [{"delta": {"content": "failover token"}}]}',
        b"data: [DONE]",
    ]

    class MockStreamContext:
        def __init__(self, *args, **kwargs):
            self.url = str(args[1]) if len(args) > 1 else str(kwargs.get("url", ""))

        def __enter__(self):
            if "openrouter" in self.url:
                raise httpx.ConnectError("OpenRouter unreachable")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.iter_lines = MagicMock(return_value=lines_200)
            return mock_resp

        def __exit__(self, *args):
            pass

    with patch("httpx.stream", side_effect=MockStreamContext):
        events = list(
            svc.stream_chat(
                session_id=None,
                message="Test streaming failover",
                admin_id="adm_tester_resilience",
                execution_mode="auto",
            )
        )

        event_types = [e.get("event") for e in events]
        assert "metadata" in event_types
        assert "token" in event_types
        assert "done" in event_types

        tokens = [e["data"]["text"] for e in events if e.get("event") == "token"]
        assert "".join(tokens) == "Streamed failover token"
