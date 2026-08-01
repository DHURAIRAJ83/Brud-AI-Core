from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.admin_assistant_service import AdminAssistantError, AdminAssistantService
from backend.services.admin_assistant_tools import run_tool
from backend.services.external_data_provider_service import ExternalDataProviderService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def _approve(assistant, proposal_id):
    return assistant.review(proposal_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "assistant_providers.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


# -- read-only tools ----------------------------------------------------


def test_list_external_data_providers_tool_returns_seeded_builtins(settings: Settings) -> None:
    result = run_tool("list_external_data_providers", settings)
    codes = {item["provider_code"] for item in result["items"]}
    assert "huggingface" in codes
    assert "ai4bharat" in codes


def test_get_external_data_provider_tool(settings: Settings) -> None:
    ExternalDataProviderService(settings).list_providers()  # trigger seeding
    providers = run_tool("list_external_data_providers", settings)["items"]
    huggingface = next(p for p in providers if p["provider_code"] == "huggingface")
    result = run_tool(
        "get_external_data_provider", settings, {"public_id": huggingface["public_id"]}
    )
    assert result["available"] is True
    assert result["provider_code"] == "huggingface"

    missing = run_tool("get_external_data_provider", settings, {"public_id": "does-not-exist"})
    assert missing["available"] is False


def test_get_provider_capabilities_tool(settings: Settings) -> None:
    providers = run_tool("list_external_data_providers", settings)["items"]
    huggingface = next(p for p in providers if p["provider_code"] == "huggingface")
    result = run_tool(
        "get_provider_capabilities", settings, {"public_id": huggingface["public_id"]}
    )
    assert result["available"] is True
    capability_types = {item["capability_type"] for item in result["items"]}
    assert "search_datasets" in capability_types


def test_get_provider_connection_status_tool_with_no_tests_yet(settings: Settings) -> None:
    providers = run_tool("list_external_data_providers", settings)["items"]
    huggingface = next(p for p in providers if p["provider_code"] == "huggingface")
    result = run_tool(
        "get_provider_connection_status", settings, {"public_id": huggingface["public_id"]}
    )
    assert result["available"] is True
    assert result["most_recent"] is None
    assert result["recent_tests"] == []


# -- controlled actions: propose -> review -> execute --------------------


def test_register_external_data_provider_end_to_end(settings: Settings) -> None:
    assistant = AdminAssistantService(settings)
    proposal = assistant.propose(
        action_type="register_external_data_provider",
        target_type="external_data_provider_registration",
        target_public_id="my-assistant-registered-provider",
        request_payload={
            "provider_code": "my-assistant-registered-provider",
            "name": "Assistant Registered Provider",
            "provider_type": "custom_api",
            "access_mode": "public",
            "description": "Registered via the Admin Assistant.",
        },
        requested_by=ADMIN_ID,
        summary="Register a new provider",
    )
    assert proposal.risk_level == "moderate"
    assert proposal.preview["proposed_state"]["provider_code"] == "my-assistant-registered-provider"

    reviewed = assistant.review(
        proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
    )
    assert reviewed.status == "approved"

    executed = assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["provider_code"] == "my-assistant-registered-provider"
    assert executed.execution_result["lifecycle_status"] == "draft"
    assert executed.execution_result["enabled"] is False


def test_register_duplicate_provider_rejected_at_confirm_via_stale_check(
    settings: Settings,
) -> None:
    assistant = AdminAssistantService(settings)
    provider_service = ExternalDataProviderService(settings)

    proposal = assistant.propose(
        action_type="register_external_data_provider",
        target_type="external_data_provider_registration",
        target_public_id="race-condition-provider",
        request_payload={
            "provider_code": "race-condition-provider",
            "name": "Race Condition Provider",
            "provider_type": "custom_api",
            "access_mode": "public",
        },
        requested_by=ADMIN_ID,
        summary="Register",
    )

    # Someone else registers the same provider_code before this proposal is confirmed.
    provider_service.register_provider(
        {
            "provider_code": "race-condition-provider",
            "name": "Someone Else's Provider",
            "provider_type": "custom_api",
            "access_mode": "public",
        },
        "00000000-0000-0000-0000-000000000002",
    )

    with pytest.raises(AdminAssistantError, match="changed since this proposal"):
        _approve(assistant, proposal.public_id)


def test_verify_enable_disable_external_data_provider_end_to_end(settings: Settings) -> None:
    provider_service = ExternalDataProviderService(settings)
    provider = provider_service.register_provider(
        {
            "provider_code": "verify-enable-test",
            "name": "Verify Enable Test",
            "provider_type": "custom_api",
            "access_mode": "public",
            "official_website": "https://verify-enable-test.example",
            "terms_url": "https://verify-enable-test.example/terms",
        },
        ADMIN_ID,
    )
    provider_service.add_domain(
        provider["public_id"],
        {"domain": "verify-enable-test.example", "domain_type": "official"},
        ADMIN_ID,
    )

    assistant = AdminAssistantService(settings)

    verify_proposal = assistant.propose(
        action_type="verify_external_data_provider",
        target_type="external_data_provider",
        target_public_id=provider["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Evaluate verification",
    )
    _approve(assistant, verify_proposal.public_id)
    verify_executed = assistant.execute(verify_proposal.public_id, executor_public_id=ADMIN_ID)
    assert verify_executed.execution_status == "succeeded"
    assert "verified" in verify_executed.execution_result

    enable_proposal = assistant.propose(
        action_type="enable_external_data_provider",
        target_type="external_data_provider",
        target_public_id=provider["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Enable for discovery",
    )
    _approve(assistant, enable_proposal.public_id)
    enable_executed = assistant.execute(enable_proposal.public_id, executor_public_id=ADMIN_ID)
    assert enable_executed.execution_result["lifecycle_status"] == "enabled"
    assert enable_executed.execution_result["enabled"] is True

    disable_proposal = assistant.propose(
        action_type="disable_external_data_provider",
        target_type="external_data_provider",
        target_public_id=provider["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Disable",
    )
    _approve(assistant, disable_proposal.public_id)
    disable_executed = assistant.execute(disable_proposal.public_id, executor_public_id=ADMIN_ID)
    assert disable_executed.execution_result["lifecycle_status"] == "disabled"
    assert disable_executed.execution_result["enabled"] is False


def test_test_connection_action_end_to_end(settings: Settings) -> None:
    provider_service = ExternalDataProviderService(settings)
    provider = provider_service.register_provider(
        {
            "provider_code": "connection-test-provider",
            "name": "Connection Test Provider",
            "provider_type": "custom_api",
            "access_mode": "public",
        },
        ADMIN_ID,
    )
    provider_service.add_domain(
        provider["public_id"], {"domain": "example.org", "domain_type": "official"}, ADMIN_ID
    )

    assistant = AdminAssistantService(settings)
    proposal = assistant.propose(
        action_type="test_external_data_provider_connection",
        target_type="external_data_provider",
        target_public_id=provider["public_id"],
        request_payload={"use_credential": False},
        requested_by=ADMIN_ID,
        summary="Test connection",
    )
    assert proposal.risk_level == "low"
    _approve(assistant, proposal.public_id)
    executed = assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["result"] in (
        "success", "partial", "failed", "authentication_required", "rate_limited", "unsupported",
    )


def test_configure_provider_credential_reference_requires_reason_and_never_leaks_secret(
    settings: Settings,
) -> None:
    provider_service = ExternalDataProviderService(settings)
    provider = provider_service.register_provider(
        {
            "provider_code": "credential-action-provider",
            "name": "Credential Action Provider",
            "provider_type": "custom_api",
            "access_mode": "gated",
        },
        ADMIN_ID,
    )

    assistant = AdminAssistantService(settings)
    with pytest.raises(AdminAssistantError):
        assistant.propose(
            action_type="configure_provider_credential_reference",
            target_type="external_data_provider",
            target_public_id=provider["public_id"],
            request_payload={
                "credential_type": "api_key",
                "reference_key": "BRUD_PROVIDER_SECRET__x",
                "reason": "",
            },
            requested_by=ADMIN_ID,
            summary="Configure credential",
        )

    proposal = assistant.propose(
        action_type="configure_provider_credential_reference",
        target_type="external_data_provider",
        target_public_id=provider["public_id"],
        request_payload={
            "credential_type": "api_key",
            "reference_key": "BRUD_PROVIDER_SECRET__x",
            "reason": "Admin obtained an API key from the provider dashboard.",
        },
        requested_by=ADMIN_ID,
        summary="Configure credential",
    )
    assert proposal.risk_level == "high"
    _approve(assistant, proposal.public_id)
    executed = assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert set(executed.execution_result) == {
        "credential_type", "configured", "status", "last_rotated_at", "last_tested_at",
    }
