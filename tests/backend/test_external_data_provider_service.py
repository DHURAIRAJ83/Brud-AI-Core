from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.external_data_connectors.base import HttpResponse
from backend.services.external_data_provider_service import (
    ExternalDataProviderCapabilityService,
    ExternalDataProviderConnectionService,
    ExternalDataProviderCredentialService,
    ExternalDataProviderError,
    ExternalDataProviderService,
    ExternalDataProviderVerificationService,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "providers.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def service(settings: Settings) -> ExternalDataProviderService:
    return ExternalDataProviderService(settings)


def _register(service: ExternalDataProviderService, code="custom-1", **overrides):
    payload = {
        "provider_code": code,
        "name": "Custom Provider",
        "provider_type": "custom_api",
        "access_mode": "public",
        **overrides,
    }
    return service.register_provider(payload, ADMIN_ID)


def test_register_provider_defaults(service: ExternalDataProviderService) -> None:
    provider = _register(service)
    assert provider["lifecycle_status"] == "draft"
    assert provider["trust_status"] == "unverified"
    assert provider["enabled"] is False


def test_register_provider_rejects_unknown_type(service: ExternalDataProviderService) -> None:
    with pytest.raises(ExternalDataProviderError):
        _register(service, provider_type="not_a_real_type")


def test_register_provider_rejects_unknown_access_mode(
    service: ExternalDataProviderService,
) -> None:
    with pytest.raises(ExternalDataProviderError):
        _register(service, access_mode="not_a_real_mode")


def test_register_provider_rejects_duplicate_code(service: ExternalDataProviderService) -> None:
    _register(service, code="dup")
    with pytest.raises(ExternalDataProviderError):
        _register(service, code="dup")


def test_update_provider_only_patches_allowlisted_fields(
    service: ExternalDataProviderService,
) -> None:
    provider = _register(service)
    updated = service.update_provider(
        provider["public_id"],
        {"description": "New description", "lifecycle_status": "enabled", "enabled": True},
        ADMIN_ID,
    )
    assert updated["description"] == "New description"
    # lifecycle_status/enabled are not patchable fields -- silently ignored here,
    # only settable through transition_lifecycle.
    assert updated["lifecycle_status"] == "draft"
    assert updated["enabled"] is False


def test_transition_lifecycle_enable_disable_restrict_block(
    service: ExternalDataProviderService,
) -> None:
    provider = _register(service)
    enabled = service.transition_lifecycle(provider["public_id"], "enable", ADMIN_ID)
    assert enabled["lifecycle_status"] == "enabled"
    assert enabled["enabled"] is True

    disabled = service.transition_lifecycle(provider["public_id"], "disable", ADMIN_ID)
    assert disabled["lifecycle_status"] == "disabled"
    assert disabled["enabled"] is False

    restricted = service.transition_lifecycle(provider["public_id"], "restrict", ADMIN_ID)
    assert restricted["lifecycle_status"] == "restricted"

    blocked = service.transition_lifecycle(provider["public_id"], "block", ADMIN_ID)
    assert blocked["lifecycle_status"] == "blocked"
    assert blocked["trust_status"] == "blocked"


def test_archive_is_terminal(service: ExternalDataProviderService) -> None:
    provider = _register(service)
    service.transition_lifecycle(provider["public_id"], "archive", ADMIN_ID)
    with pytest.raises(ExternalDataProviderError):
        service.transition_lifecycle(provider["public_id"], "enable", ADMIN_ID)


def test_archived_provider_metadata_remains_readable(service: ExternalDataProviderService) -> None:
    provider = _register(service)
    service.transition_lifecycle(provider["public_id"], "archive", ADMIN_ID)
    fetched = service.get_provider(provider["public_id"])
    assert fetched["lifecycle_status"] == "archived"
    assert fetched["name"] == "Custom Provider"


def test_unsupported_lifecycle_action_rejected(service: ExternalDataProviderService) -> None:
    provider = _register(service)
    with pytest.raises(ExternalDataProviderError):
        service.transition_lifecycle(provider["public_id"], "not_a_real_action", ADMIN_ID)


def test_add_domain_rejects_unknown_domain_type(service: ExternalDataProviderService) -> None:
    provider = _register(service)
    with pytest.raises(ExternalDataProviderError):
        service.add_domain(
            provider["public_id"], {"domain": "x.org", "domain_type": "not_a_real_type"}, ADMIN_ID
        )


def test_add_domain_success(service: ExternalDataProviderService) -> None:
    provider = _register(service)
    domain = service.add_domain(
        provider["public_id"], {"domain": "custom1.example", "domain_type": "official"}, ADMIN_ID
    )
    assert domain["verification_status"] == "unverified"
    assert service.list_domains(provider["public_id"]) == [domain]


# -- verification ---------------------------------------------------------


def test_verify_domain_requires_evidence(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    domain = service.add_domain(
        provider["public_id"], {"domain": "custom1.example", "domain_type": "official"}, ADMIN_ID
    )
    verification_service = ExternalDataProviderVerificationService(settings)
    with pytest.raises(ExternalDataProviderError):
        verification_service.verify_domain(
            domain["public_id"], verified=True, evidence="   ", admin_id=ADMIN_ID
        )


def test_evaluate_provider_never_upgrades_trust_without_a_verified_domain(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    verification_service = ExternalDataProviderVerificationService(settings)
    report = verification_service.evaluate_provider(provider["public_id"], ADMIN_ID)
    assert report["verified"] is False
    assert "no official domain registered" in report["blocking_reasons"]

    fetched = service.get_provider(provider["public_id"])
    assert fetched["trust_status"] == "unverified"


def test_evaluate_provider_upgrades_to_domain_verified_only_after_explicit_domain_verification(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service, official_website="https://custom1.example", terms_url="https://custom1.example/terms")
    domain = service.add_domain(
        provider["public_id"], {"domain": "custom1.example", "domain_type": "official"}, ADMIN_ID
    )
    verification_service = ExternalDataProviderVerificationService(settings)

    # Before the domain is independently verified, evaluation refuses to upgrade trust.
    unverified_report = verification_service.evaluate_provider(provider["public_id"], ADMIN_ID)
    assert unverified_report["verified"] is False

    verification_service.verify_domain(
        domain["public_id"],
        verified=True,
        evidence="Checked HTTPS cert and org registry",
        admin_id=ADMIN_ID,
    )
    report = verification_service.evaluate_provider(provider["public_id"], ADMIN_ID)
    assert report["verified"] is True
    assert report["trust_status_upgraded_to"] == "domain_verified"

    fetched = service.get_provider(provider["public_id"])
    assert fetched["trust_status"] == "domain_verified"


def test_set_trust_status_requires_evidence_for_evidence_required_tiers(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    verification_service = ExternalDataProviderVerificationService(settings)
    with pytest.raises(ExternalDataProviderError):
        verification_service.set_trust_status(
            provider["public_id"], "organization_verified", evidence="", admin_id=ADMIN_ID
        )
    updated = verification_service.set_trust_status(
        provider["public_id"],
        "organization_verified",
        evidence="Confirmed via official registration document",
        admin_id=ADMIN_ID,
    )
    assert updated["trust_status"] == "organization_verified"


def test_set_trust_status_allows_unverified_or_blocked_without_evidence(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    verification_service = ExternalDataProviderVerificationService(settings)
    updated = verification_service.set_trust_status(
        provider["public_id"], "blocked", evidence="", admin_id=ADMIN_ID
    )
    assert updated["trust_status"] == "blocked"


# -- credentials ------------------------------------------------------------


def test_credential_status_never_leaks_reference_key_or_secret(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    credential_service = ExternalDataProviderCredentialService(settings)
    status = credential_service.configure_credential_reference(
        provider["public_id"],
        credential_type="api_key",
        reference_key="BRUD_PROVIDER_SECRET__test_service",
        admin_id=ADMIN_ID,
    )
    assert set(status) == {
        "credential_type", "configured", "status", "last_rotated_at", "last_tested_at",
    }
    assert "reference_key" not in status
    assert status["configured"] is False  # env var not actually set


def test_credential_configured_reflects_real_environment_variable(
    settings: Settings, service: ExternalDataProviderService, monkeypatch
) -> None:
    provider = _register(service)
    credential_service = ExternalDataProviderCredentialService(settings)
    monkeypatch.setenv("BRUD_PROVIDER_SECRET__configured_test", "a-real-secret-value")
    status = credential_service.configure_credential_reference(
        provider["public_id"],
        credential_type="api_key",
        reference_key="BRUD_PROVIDER_SECRET__configured_test",
        admin_id=ADMIN_ID,
    )
    assert status["configured"] is True


def test_credential_rejects_unknown_type(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    credential_service = ExternalDataProviderCredentialService(settings)
    with pytest.raises(ExternalDataProviderError):
        credential_service.configure_credential_reference(
            provider["public_id"],
            credential_type="not_a_real_type",
            reference_key="X",
            admin_id=ADMIN_ID,
        )


def test_revoke_credential(settings: Settings, service: ExternalDataProviderService) -> None:
    provider = _register(service)
    credential_service = ExternalDataProviderCredentialService(settings)
    credential_service.configure_credential_reference(
        provider["public_id"], credential_type="api_key", reference_key="X", admin_id=ADMIN_ID
    )
    statuses = credential_service.get_credential_status(provider["public_id"])
    credential_rows = credential_service.repository.list_credentials(provider["public_id"])
    credential_public_id = credential_rows[0]["public_id"]
    revoked = credential_service.revoke_credential(
        credential_public_id, provider["public_id"], ADMIN_ID
    )
    assert revoked["status"] == "revoked"
    assert len(statuses) == 1


# -- connection tests --------------------------------------------------------


def test_connection_test_success_bumps_draft_to_connection_tested(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service, code="huggingface-like", provider_type="repository_host")
    service.add_domain(
        provider["public_id"], {"domain": "example.org", "domain_type": "official"}, ADMIN_ID
    )

    def mock_transport(url, headers, timeout_seconds):
        return HttpResponse(status_code=200, elapsed_ms=15, reachable=True)

    connection_service = ExternalDataProviderConnectionService(settings, transport=mock_transport)
    result = connection_service.test_connection(provider["public_id"], admin_id=ADMIN_ID)
    assert result["result"] == "success"

    fetched = service.get_provider(provider["public_id"])
    assert fetched["lifecycle_status"] == "connection_tested"


def test_connection_test_failure_does_not_change_lifecycle(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    service.add_domain(
        provider["public_id"], {"domain": "example.org", "domain_type": "official"}, ADMIN_ID
    )

    def mock_transport(url, headers, timeout_seconds):
        return HttpResponse(status_code=0, elapsed_ms=5000, reachable=False, error="ConnectTimeout")

    connection_service = ExternalDataProviderConnectionService(settings, transport=mock_transport)
    result = connection_service.test_connection(provider["public_id"], admin_id=ADMIN_ID)
    assert result["result"] == "failed"

    fetched = service.get_provider(provider["public_id"])
    assert fetched["lifecycle_status"] == "draft"


def test_connection_test_with_credential_updates_credential_status(
    settings: Settings, service: ExternalDataProviderService, monkeypatch
) -> None:
    provider = _register(service)
    service.add_domain(
        provider["public_id"], {"domain": "example.org", "domain_type": "official"}, ADMIN_ID
    )
    credential_service = ExternalDataProviderCredentialService(settings)
    monkeypatch.setenv("BRUD_PROVIDER_SECRET__conn_test", "token-value")
    credential_service.configure_credential_reference(
        provider["public_id"],
        credential_type="bearer_token",
        reference_key="BRUD_PROVIDER_SECRET__conn_test",
        admin_id=ADMIN_ID,
    )

    def mock_transport(url, headers, timeout_seconds):
        assert headers.get("Authorization") == "Bearer token-value"
        return HttpResponse(status_code=200, elapsed_ms=10, reachable=True)

    connection_service = ExternalDataProviderConnectionService(settings, transport=mock_transport)
    connection_service.test_connection(
        provider["public_id"], admin_id=ADMIN_ID, use_credential=True
    )

    statuses = credential_service.get_credential_status(provider["public_id"])
    assert statuses[0]["status"] == "test_succeeded"
    assert statuses[0]["last_tested_at"] is not None


def test_connection_tests_are_listed(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    service.add_domain(
        provider["public_id"], {"domain": "example.org", "domain_type": "official"}, ADMIN_ID
    )

    def mock_transport(url, headers, timeout_seconds):
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True)

    connection_service = ExternalDataProviderConnectionService(settings, transport=mock_transport)
    connection_service.test_connection(provider["public_id"], admin_id=ADMIN_ID)
    connection_service.test_connection(provider["public_id"], admin_id=ADMIN_ID)
    tests = connection_service.list_connection_tests(provider["public_id"])
    assert len(tests) == 2


# -- capabilities -------------------------------------------------------------


def test_set_capabilities_rejects_unknown_type(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    capability_service = ExternalDataProviderCapabilityService(settings)
    with pytest.raises(ExternalDataProviderError):
        capability_service.set_capabilities(
            provider["public_id"], [{"capability_type": "not_a_real_capability"}], ADMIN_ID
        )


def test_set_capabilities_never_enables_download_or_write(
    settings: Settings, service: ExternalDataProviderService
) -> None:
    provider = _register(service)
    capability_service = ExternalDataProviderCapabilityService(settings)
    results = capability_service.set_capabilities(
        provider["public_id"],
        [
            {"capability_type": "read_metadata", "enabled": True},
            {"capability_type": "download_full", "enabled": True},
            {"capability_type": "upload", "enabled": True},
        ],
        ADMIN_ID,
    )
    by_type = {r["capability_type"]: r for r in results}
    assert by_type["read_metadata"]["enabled"] is True
    assert by_type["download_full"]["enabled"] is False
    assert by_type["upload"]["enabled"] is False


def test_list_capabilities(settings: Settings, service: ExternalDataProviderService) -> None:
    provider = _register(service)
    capability_service = ExternalDataProviderCapabilityService(settings)
    capability_service.set_capabilities(
        provider["public_id"], [{"capability_type": "read_metadata"}], ADMIN_ID
    )
    capabilities = capability_service.list_capabilities(provider["public_id"])
    assert len(capabilities) == 1
