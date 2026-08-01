from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError
from backend.database.repositories.external_data_providers import (
    ExternalDataProviderRepository,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def repository(tmp_path: Path) -> ExternalDataProviderRepository:
    database_path = tmp_path / "providers.db"
    initialize_database(database_path)
    return ExternalDataProviderRepository(database_path)


def _create_provider(repository, code="test-provider"):
    return repository.create_provider(
        {
            "provider_code": code,
            "name": "Test Provider",
            "provider_type": "public_api",
            "access_mode": "public",
            "created_by_admin_public_id": ADMIN_ID,
        }
    )


def test_create_and_get_provider_defaults(repository: ExternalDataProviderRepository) -> None:
    provider = _create_provider(repository)
    assert provider["lifecycle_status"] == "draft"
    assert provider["trust_status"] == "unverified"
    assert provider["enabled"] is False
    assert provider["authentication_type"] == "none"

    fetched = repository.get_provider(provider["public_id"])
    assert fetched == provider

    with pytest.raises(NotFoundError):
        repository.get_provider("does-not-exist")


def test_get_provider_by_code(repository: ExternalDataProviderRepository) -> None:
    provider = _create_provider(repository, code="by-code")
    found = repository.get_provider_by_code("by-code")
    assert found["public_id"] == provider["public_id"]
    assert repository.get_provider_by_code("missing-code") is None


def test_list_providers_filters(repository: ExternalDataProviderRepository) -> None:
    p1 = _create_provider(repository, code="p1")
    p2 = _create_provider(repository, code="p2")
    repository.update_provider(p2["public_id"], {"lifecycle_status": "enabled", "enabled": 1})

    all_items = repository.list_providers(limit=50)
    all_ids = {item["public_id"] for item in all_items}
    assert {p1["public_id"], p2["public_id"]} <= all_ids
    assert len(all_items) == 10  # 8 seeded built-ins + the 2 created here

    enabled_only = repository.list_providers(enabled=True)
    assert [item["public_id"] for item in enabled_only] == [p2["public_id"]]

    by_type = repository.list_providers(provider_type="public_api")
    assert {p1["public_id"], p2["public_id"]} <= {item["public_id"] for item in by_type}


def test_update_provider(repository: ExternalDataProviderRepository) -> None:
    provider = _create_provider(repository)
    updated = repository.update_provider(
        provider["public_id"], {"trust_status": "domain_verified", "lifecycle_status": "approved"}
    )
    assert updated["trust_status"] == "domain_verified"
    assert updated["lifecycle_status"] == "approved"
    assert updated["updated_at"] >= provider["updated_at"]

    with pytest.raises(NotFoundError):
        repository.update_provider("does-not-exist", {"trust_status": "blocked"})


def test_domains_add_list_verify(repository: ExternalDataProviderRepository) -> None:
    provider = _create_provider(repository)
    domain = repository.add_domain(
        provider["public_id"], {"domain": "example.org", "domain_type": "official"}
    )
    assert domain["verification_status"] == "unverified"
    assert domain["provider_public_id"] == provider["public_id"]

    domains = repository.list_domains(provider["public_id"])
    assert len(domains) == 1

    verified = repository.verify_domain(
        domain["public_id"], verification_status="verified", evidence="HTTPS + docs page checked"
    )
    assert verified["verification_status"] == "verified"
    assert verified["verified_at"] is not None
    assert verified["verification_evidence"] == "HTTPS + docs page checked"


def test_capabilities_upsert_is_idempotent_per_type(
    repository: ExternalDataProviderRepository,
) -> None:
    provider = _create_provider(repository)
    first = repository.upsert_capability(
        provider["public_id"],
        {"capability_type": "read_metadata", "language_codes": ["ta", "en"], "enabled": True},
    )
    second = repository.upsert_capability(
        provider["public_id"],
        {"capability_type": "read_metadata", "language_codes": ["ta"], "enabled": False},
    )
    assert first["public_id"] == second["public_id"]
    assert second["language_codes"] == ["ta"]
    assert second["enabled"] is False

    capabilities = repository.list_capabilities(provider["public_id"])
    assert len(capabilities) == 1


def test_credentials_never_expose_a_secret_value_only_a_reference(
    repository: ExternalDataProviderRepository,
) -> None:
    provider = _create_provider(repository)
    credential = repository.add_or_replace_credential(
        provider["public_id"],
        {
            "credential_type": "bearer_token",
            "reference_key": "BRUD_PROVIDER_SECRET__test_provider__bearer_token",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert credential["status"] == "configured"
    assert credential["reference_key"] == "BRUD_PROVIDER_SECRET__test_provider__bearer_token"
    # The reference key is an env var *name* -- confirm no field on this
    # row could plausibly hold an actual secret value.
    assert set(credential) == {
        "public_id", "provider_public_id", "credential_type", "reference_key", "status",
        "last_rotated_at", "last_tested_at", "created_by_admin_public_id", "created_at",
        "updated_at", "revoked_at",
    }


def test_add_or_replace_credential_upserts_per_type(
    repository: ExternalDataProviderRepository,
) -> None:
    provider = _create_provider(repository)
    first = repository.add_or_replace_credential(
        provider["public_id"],
        {
            "credential_type": "api_key",
            "reference_key": "BRUD_PROVIDER_SECRET__v1",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    second = repository.add_or_replace_credential(
        provider["public_id"],
        {
            "credential_type": "api_key",
            "reference_key": "BRUD_PROVIDER_SECRET__v2",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert first["public_id"] == second["public_id"]
    assert second["reference_key"] == "BRUD_PROVIDER_SECRET__v2"
    assert second["status"] == "configured"
    assert second["revoked_at"] is None

    credentials = repository.list_credentials(provider["public_id"])
    assert len(credentials) == 1


def test_revoke_credential(repository: ExternalDataProviderRepository) -> None:
    provider = _create_provider(repository)
    credential = repository.add_or_replace_credential(
        provider["public_id"],
        {
            "credential_type": "api_key",
            "reference_key": "BRUD_PROVIDER_SECRET__revoke_test",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    revoked = repository.revoke_credential(credential["public_id"])
    assert revoked["status"] == "revoked"
    assert revoked["revoked_at"] is not None


def test_set_credential_status(repository: ExternalDataProviderRepository) -> None:
    provider = _create_provider(repository)
    credential = repository.add_or_replace_credential(
        provider["public_id"],
        {
            "credential_type": "api_key",
            "reference_key": "BRUD_PROVIDER_SECRET__status_test",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    tested = repository.set_credential_status(
        credential["public_id"], status="test_succeeded", last_tested_at=True
    )
    assert tested["status"] == "test_succeeded"
    assert tested["last_tested_at"] is not None


def test_connection_tests_are_recorded_and_listed_newest_first(
    repository: ExternalDataProviderRepository,
) -> None:
    provider = _create_provider(repository)
    repository.record_connection_test(
        provider["public_id"], {"result": "success", "tested_by_admin_public_id": ADMIN_ID}
    )
    repository.record_connection_test(
        provider["public_id"],
        {"result": "failed", "error_code": "timeout", "tested_by_admin_public_id": ADMIN_ID},
    )
    tests = repository.list_connection_tests(provider["public_id"])
    assert len(tests) == 2
    assert tests[0]["result"] == "failed"
    assert tests[1]["result"] == "success"


def test_events_are_recorded_and_listed_newest_first(
    repository: ExternalDataProviderRepository,
) -> None:
    provider = _create_provider(repository)
    repository.record_event(
        provider["public_id"],
        {"event_type": "provider_registered", "performed_by_admin_public_id": ADMIN_ID},
    )
    repository.record_event(
        provider["public_id"],
        {"event_type": "provider_enabled", "performed_by_admin_public_id": ADMIN_ID},
    )
    events = repository.list_events(provider["public_id"])
    assert len(events) == 2
    assert events[0]["event_type"] == "provider_enabled"
    assert events[1]["event_type"] == "provider_registered"


def test_builtin_providers_are_seeded_lazily_and_conservatively(
    repository: ExternalDataProviderRepository,
) -> None:
    items = repository.list_providers(limit=50)
    codes = {item["provider_code"] for item in items}
    assert codes == {
        "ai4bharat", "huggingface", "github", "wikimedia", "bhashini",
        "government-open-data-portal", "university-research-repository",
        "custom-provider-template",
    }
    for item in items:
        assert item["lifecycle_status"] == "draft"
        assert item["trust_status"] == "unverified"
        assert item["enabled"] is False


def test_builtin_provider_seeding_is_idempotent(
    repository: ExternalDataProviderRepository,
) -> None:
    first = repository.list_providers(limit=50)
    second = repository.list_providers(limit=50)
    assert len(first) == len(second) == 8


def test_seeded_huggingface_has_real_domain_and_capabilities(
    repository: ExternalDataProviderRepository,
) -> None:
    provider = repository.get_provider_by_code("huggingface")
    assert provider is not None
    domains = repository.list_domains(provider["public_id"])
    assert any(d["domain"] == "huggingface.co" for d in domains)
    capabilities = repository.list_capabilities(provider["public_id"])
    capability_types = {c["capability_type"] for c in capabilities}
    assert capability_types == {"search_datasets", "read_dataset_card", "list_files"}
    for capability in capabilities:
        assert capability["enabled"] is False


def test_seeded_template_providers_have_no_domains(
    repository: ExternalDataProviderRepository,
) -> None:
    for code in (
        "government-open-data-portal", "university-research-repository",
        "custom-provider-template",
    ):
        provider = repository.get_provider_by_code(code)
        assert provider is not None
        assert provider["official_website"] is None
        assert repository.list_domains(provider["public_id"]) == []


def test_operations_on_unknown_provider_raise_not_found(
    repository: ExternalDataProviderRepository,
) -> None:
    with pytest.raises(NotFoundError):
        repository.add_domain("does-not-exist", {"domain": "x.org", "domain_type": "official"})
    with pytest.raises(NotFoundError):
        repository.upsert_capability("does-not-exist", {"capability_type": "read_metadata"})
    with pytest.raises(NotFoundError):
        repository.add_or_replace_credential(
            "does-not-exist",
            {
                "credential_type": "api_key",
                "reference_key": "X",
                "created_by_admin_public_id": ADMIN_ID,
            },
        )
    with pytest.raises(NotFoundError):
        repository.record_connection_test(
            "does-not-exist", {"result": "success", "tested_by_admin_public_id": ADMIN_ID}
        )
    with pytest.raises(NotFoundError):
        repository.record_event(
            "does-not-exist",
            {"event_type": "provider_registered", "performed_by_admin_public_id": ADMIN_ID},
        )
