"""MB-27: unit tests for the pure (and one designated impure)
core_model/mini_brain/provider_settings/ modules -- no database, no
app, no HTTP client.
"""

from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

from core_model.mini_brain.provider_settings import (
    audit_event_builder,
    connection_test_request,
    connection_test_result,
    diagnostics_builder,
    provider_capability_matrix,
    provider_health_summary,
    provider_registry,
    provider_settings_sanitizer,
    provider_summary_builder,
    provider_validator,
    secret_encryptor,
    settings_export_builder,
    settings_import_validator,
)
from core_model.mini_brain.provider_settings.secret_masker import mask_secret, mask_secret_list

# -- provider_registry --------------------------------------------------------------------


def test_registry_has_all_seven_providers() -> None:
    assert set(provider_registry.known_providers()) == {
        "openrouter", "openai", "anthropic", "gemini", "faster_whisper", "coqui_tts", "local_llm",
    }


@pytest.mark.parametrize("provider_key", ["openrouter", "openai", "anthropic", "gemini"])
def test_registry_external_ai_providers_require_api_key(provider_key: str) -> None:
    definition = provider_registry.provider_definition(provider_key)
    assert definition["provider_type"] == "external_ai"
    assert definition["required_secrets"] == ["api_key"]
    assert definition["capability_flags"]["chat"] is True


@pytest.mark.parametrize("provider_key", ["faster_whisper", "coqui_tts"])
def test_registry_speech_providers_need_no_secrets(provider_key: str) -> None:
    definition = provider_registry.provider_definition(provider_key)
    assert definition["provider_type"] == "speech"
    assert definition["required_secrets"] == []
    assert definition["default_enabled"] is True


def test_registry_local_llm_has_real_inference_wired_by_mb28() -> None:
    # MB-28 disclosed edit: local_llm gained real llama-cpp-python
    # inference (see backend/services/mini_brain_llm_adapter.py) --
    # chat capability is genuinely True now, not a placeholder.
    definition = provider_registry.provider_definition("local_llm")
    assert definition["provider_type"] == "local_model"
    assert definition["capability_flags"]["chat"] is True
    assert definition["capability_flags"]["stt"] is False
    assert definition["capability_flags"]["tts"] is False
    assert definition["default_enabled"] is False
    assert definition["optional_settings"]["temperature"] == 0.3


def test_registry_unknown_provider_returns_none() -> None:
    assert provider_registry.provider_definition("bogus") is None
    assert provider_registry.is_known_provider("bogus") is False


def test_registry_accessor_helpers() -> None:
    assert provider_registry.required_secrets_for("openai") == ["api_key"]
    assert provider_registry.required_secrets_for("bogus") == []
    assert provider_registry.default_enabled_for("faster_whisper") is True
    assert provider_registry.provider_type_for("gemini") == "external_ai"
    assert provider_registry.provider_type_for("bogus") is None


# -- secret_masker -------------------------------------------------------------------------


def test_mask_secret_never_reflects_length() -> None:
    short = mask_secret(has_value=True, updated_at="t")
    assert short["masked_indicator"] == "•" * 6


def test_mask_secret_unset() -> None:
    result = mask_secret(has_value=False)
    assert result["is_set"] is False
    assert result["masked_indicator"] == ""
    assert result["updated_at"] is None


def test_mask_secret_list_only_reads_names() -> None:
    rows = [{"secret_name": "api_key", "updated_at": "2026-01-01"}]
    masked = mask_secret_list(rows)
    assert masked[0]["secret_name"] == "api_key"
    assert masked[0]["is_set"] is True
    assert "encrypted_value" not in masked[0]


# -- secret_encryptor (the one impure exception) --------------------------------------------


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    key = Fernet.generate_key()
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, key.decode("ascii"))
    return key


def test_encryption_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, raising=False)
    assert secret_encryptor.encryption_available() is False


def test_encryption_available_true_with_key(fernet_key: bytes) -> None:
    assert secret_encryptor.encryption_available() is True


def test_encrypt_decrypt_round_trip(fernet_key: bytes) -> None:
    encrypted = secret_encryptor.encrypt_secret("sk-real-secret-value")
    assert isinstance(encrypted, str)
    assert secret_encryptor.decrypt_secret(encrypted) == "sk-real-secret-value"


def test_encrypted_value_is_not_the_plaintext(fernet_key: bytes) -> None:
    encrypted = secret_encryptor.encrypt_secret("sk-real-secret-value")
    assert "sk-real-secret-value" not in encrypted


def test_encrypt_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, raising=False)
    with pytest.raises(secret_encryptor.EncryptionUnavailableError):
        secret_encryptor.encrypt_secret("x")


def test_decrypt_with_wrong_key_raises(fernet_key: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    encrypted = secret_encryptor.encrypt_secret("sk-real-secret-value")
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, Fernet.generate_key().decode("ascii"))
    with pytest.raises(secret_encryptor.SecretDecryptionError):
        secret_encryptor.decrypt_secret(encrypted)


def test_decrypt_tampered_token_raises(fernet_key: bytes) -> None:
    encrypted = secret_encryptor.encrypt_secret("sk-real-secret-value")
    tampered = encrypted[:-4] + "abcd"
    with pytest.raises(secret_encryptor.SecretDecryptionError):
        secret_encryptor.decrypt_secret(tampered)


def test_never_auto_generates_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, raising=False)
    with pytest.raises(secret_encryptor.EncryptionUnavailableError):
        secret_encryptor.encrypt_secret("x")
    # confirm nothing was written to the environment as a side effect
    assert os.environ.get(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR) is None


# -- provider_validator --------------------------------------------------------------------


def test_validate_provider_key_known() -> None:
    assert provider_validator.validate_provider_key("openai")["valid"] is True


def test_validate_provider_key_unknown() -> None:
    result = provider_validator.validate_provider_key("bogus")
    assert result["valid"] is False
    assert "bogus" in result["errors"][0]


def test_validate_config_rejects_unexpected_key() -> None:
    result = provider_validator.validate_config(provider_key="openai", config={"not_a_real_setting": 1})
    assert result["valid"] is False


def test_validate_config_accepts_declared_key() -> None:
    result = provider_validator.validate_config(provider_key="openai", config={"model": "gpt-4o-mini"})
    assert result["valid"] is True


def test_missing_required_secrets() -> None:
    assert provider_validator.missing_required_secrets(provider_key="openai", present_secret_names=[]) == ["api_key"]
    assert provider_validator.missing_required_secrets(provider_key="openai", present_secret_names=["api_key"]) == []


def test_is_fully_configured() -> None:
    assert provider_validator.is_fully_configured(provider_key="faster_whisper", present_secret_names=[]) is True
    assert provider_validator.is_fully_configured(provider_key="openai", present_secret_names=[]) is False


# -- connection_test_request / connection_test_result ------------------------------------------


def test_connection_test_request_clamps_timeout_high() -> None:
    request = connection_test_request.build(provider_key="openai", decrypted_api_key="x", timeout_seconds=999)
    assert request["timeout_seconds"] == connection_test_request.MAX_TEST_TIMEOUT_SECONDS


def test_connection_test_request_clamps_timeout_low() -> None:
    request = connection_test_request.build(provider_key="openai", decrypted_api_key="x", timeout_seconds=0)
    assert request["timeout_seconds"] == connection_test_request.MIN_TEST_TIMEOUT_SECONDS


def test_connection_test_request_default_timeout() -> None:
    request = connection_test_request.build(provider_key="openai", decrypted_api_key="x", timeout_seconds=None)
    assert request["timeout_seconds"] == connection_test_request.DEFAULT_TEST_TIMEOUT_SECONDS


def test_connection_test_result_normalizes_unknown_status() -> None:
    result = connection_test_result.normalize(provider_key="openai", raw_result={"status": "bogus_status"})
    assert result["status"] == "failed"


def test_connection_test_result_never_includes_text_field() -> None:
    result = connection_test_result.normalize(
        provider_key="openai", raw_result={"status": "success", "latency_ms": 1.0, "text": "should not survive"},
    )
    assert "text" not in result


def test_connection_test_result_contains_forbidden_keys_detector() -> None:
    assert connection_test_result.contains_forbidden_keys({"api_key": "x"}) is True
    assert connection_test_result.contains_forbidden_keys({"status": "success"}) is False


# -- audit_event_builder --------------------------------------------------------------------


def test_audit_event_builder_shape() -> None:
    event = audit_event_builder.build(
        provider_key="openai", setting_public_id="s1", action="enabled", admin_id="admin-1", changed_fields=["enabled"],
    )
    assert event["changed_fields"] == ["enabled"]


def test_audit_event_secret_field_name_never_a_value() -> None:
    name = audit_event_builder.secret_field_name("api_key")
    assert name == "secret:api_key"
    assert "=" not in name


# -- diagnostics_builder --------------------------------------------------------------------


def test_diagnostics_builder_shape() -> None:
    result = diagnostics_builder.build(
        encryption_available=True, configured_provider_count=3, enabled_provider_count=1,
        provider_health=[{"provider_key": "openai", "health": "healthy"}], unavailable_providers=[],
    )
    assert result["missing_encryption_key"] is False
    assert result["configured_provider_count"] == 3


# -- settings_export_builder / settings_import_validator ------------------------------------


def test_export_builder_never_includes_secret_fields() -> None:
    rows = [{"provider_key": "openai", "provider_type": "external_ai", "enabled": True, "config": {}, "updated_at": "t",
             "encrypted_value": "should never appear -- not a real export field anyway"}]
    result = settings_export_builder.build(rows)
    assert "encrypted_value" not in result["providers"][0]


def test_import_validator_accepts_clean_payload() -> None:
    result = settings_import_validator.validate({"providers": [{"provider_key": "openai", "enabled": True}]})
    assert result["valid"] is True


def test_import_validator_rejects_encrypted_value_field() -> None:
    result = settings_import_validator.validate({"providers": [{"provider_key": "openai", "encrypted_value": "x"}]})
    assert result["valid"] is False


def test_import_validator_rejects_unknown_provider() -> None:
    result = settings_import_validator.validate({"providers": [{"provider_key": "bogus"}]})
    assert result["valid"] is False


def test_import_validator_rejects_non_list_providers() -> None:
    result = settings_import_validator.validate({"providers": "not-a-list"})
    assert result["valid"] is False


def test_import_validator_rejects_unexpected_field() -> None:
    result = settings_import_validator.validate({"providers": [{"provider_key": "openai", "unexpected_field": 1}]})
    assert result["valid"] is False


# -- provider_capability_matrix --------------------------------------------------------------


def test_capabilities_for_known_provider() -> None:
    assert provider_capability_matrix.capabilities_for("faster_whisper") == {"chat": False, "stt": True, "tts": False}


def test_capabilities_for_unknown_provider() -> None:
    assert provider_capability_matrix.capabilities_for("bogus") == {}


def test_full_matrix_has_all_providers() -> None:
    matrix = provider_capability_matrix.full_matrix()
    assert set(matrix.keys()) == set(provider_registry.known_providers())


# -- provider_health_summary ----------------------------------------------------------------


def test_health_disabled() -> None:
    result = provider_health_summary.summarize(provider_key="openai", enabled=False, present_secret_names=[])
    assert result["health"] == "disabled"


def test_health_unconfigured() -> None:
    result = provider_health_summary.summarize(provider_key="openai", enabled=True, present_secret_names=[])
    assert result["health"] == "unconfigured"


def test_health_healthy() -> None:
    result = provider_health_summary.summarize(provider_key="openai", enabled=True, present_secret_names=["api_key"])
    assert result["health"] == "healthy"


def test_health_degraded_on_failed_last_test() -> None:
    result = provider_health_summary.summarize(
        provider_key="openai", enabled=True, present_secret_names=["api_key"], last_test_status="failed",
    )
    assert result["health"] == "degraded"


def test_health_local_backend_never_unconfigured() -> None:
    result = provider_health_summary.summarize(provider_key="faster_whisper", enabled=True, present_secret_names=[])
    assert result["health"] == "healthy"


# -- provider_summary_builder ----------------------------------------------------------------


def test_summary_builder_masks_secrets() -> None:
    summary = provider_summary_builder.build(
        setting_row={"public_id": "p1", "provider_key": "openai", "provider_type": "external_ai", "enabled": True, "config": {}, "updated_at": "t"},
        secret_rows=[{"secret_name": "api_key", "updated_at": "t"}],
    )
    assert summary["secrets"][0]["masked_indicator"] == "•" * 6
    assert "encrypted_value" not in summary["secrets"][0]


def test_summary_builder_includes_capability_flags() -> None:
    summary = provider_summary_builder.build(
        setting_row={"public_id": "p1", "provider_key": "faster_whisper", "provider_type": "speech", "enabled": True, "config": {}, "updated_at": "t"},
        secret_rows=[],
    )
    assert summary["capability_flags"]["stt"] is True


# -- provider_settings_sanitizer (adversarial fuzzing) --------------------------------------


@pytest.mark.parametrize("forbidden_key", ["encrypted_value", "api_key", "value", "secret_value", "plaintext_value"])
def test_sanitizer_strips_forbidden_keys(forbidden_key: str) -> None:
    dirty = {"enabled": True, forbidden_key: "should be stripped"}
    clean = provider_settings_sanitizer.sanitize(dirty)
    assert forbidden_key not in clean


def test_sanitizer_recurses_into_nested_dicts() -> None:
    dirty = {"outer": {"inner": {"encrypted_value": "deep"}}}
    clean = provider_settings_sanitizer.sanitize(dirty)
    assert "encrypted_value" not in clean["outer"]["inner"]


def test_sanitizer_recurses_into_lists() -> None:
    dirty = {"items": [{"api_key": "x"}, {"ok": "fine"}]}
    clean = provider_settings_sanitizer.sanitize(dirty)
    assert "api_key" not in clean["items"][0]
    assert clean["items"][1]["ok"] == "fine"


def test_sanitizer_preserves_safe_keys() -> None:
    clean_input = {"enabled": True, "provider_key": "openai", "masked_indicator": "•" * 6}
    assert provider_settings_sanitizer.sanitize(clean_input) == clean_input


def test_sanitizer_case_insensitive() -> None:
    dirty = {"Encrypted_Value": "should be stripped too"}
    clean = provider_settings_sanitizer.sanitize(dirty)
    assert clean == {}
