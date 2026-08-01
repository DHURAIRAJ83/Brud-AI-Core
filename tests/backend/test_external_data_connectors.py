from backend.services.external_data_connectors import ConnectorConfig, get_connector
from backend.services.external_data_connectors.base import HttpResponse
from backend.services.external_data_connectors.builtin import (
    AI4BharatConnector,
    BhashiniConnector,
    GenericPublicApiConnector,
    GitHubConnector,
    HuggingFaceConnector,
    ManualProviderConnector,
    WikimediaConnector,
)


def _transport(response: HttpResponse):
    def transport(url, headers, timeout_seconds):
        del url, headers, timeout_seconds
        return response

    return transport


def test_public_success() -> None:
    connector = HuggingFaceConnector()
    config = ConnectorConfig(provider_code="huggingface", domains={"api": "huggingface.co"})
    result = connector.test_connection(
        config, _transport(HttpResponse(status_code=200, elapsed_ms=42, reachable=True))
    )
    assert result.result == "success"
    assert result.latency_ms == 42
    assert result.evidence["status_code"] == 200


def test_authentication_required() -> None:
    connector = GitHubConnector()
    config = ConnectorConfig(provider_code="github", domains={"api": "api.github.com"})
    result = connector.test_connection(
        config, _transport(HttpResponse(status_code=401, elapsed_ms=10, reachable=True))
    )
    assert result.result == "authentication_required"


def test_invalid_token_still_reported_as_authentication_required() -> None:
    connector = GitHubConnector()
    config = ConnectorConfig(
        provider_code="github",
        domains={"api": "api.github.com"},
        credential_value="bad-token",
        credential_type="bearer_token",
    )
    result = connector.test_connection(
        config, _transport(HttpResponse(status_code=403, elapsed_ms=10, reachable=True))
    )
    assert result.result == "authentication_required"


def test_rate_limited() -> None:
    connector = WikimediaConnector()
    config = ConnectorConfig(provider_code="wikimedia", domains={"api": "www.wikidata.org"})
    result = connector.test_connection(
        config, _transport(HttpResponse(status_code=429, elapsed_ms=5, reachable=True))
    )
    assert result.result == "rate_limited"


def test_timeout_or_unreachable_is_failed_not_an_exception() -> None:
    connector = AI4BharatConnector()
    config = ConnectorConfig(provider_code="ai4bharat", domains={"official": "ai4bharat.org"})
    response = HttpResponse(status_code=0, elapsed_ms=5000, reachable=False, error="ConnectTimeout")
    result = connector.test_connection(config, _transport(response))
    assert result.result == "failed"
    assert result.error_code == "ConnectTimeout"


def test_unsupported_provider_never_attempts_a_network_call() -> None:
    connector = ManualProviderConnector()
    calls = []

    def transport(url, headers, timeout_seconds):
        calls.append(url)
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True)

    config = ConnectorConfig(provider_code="manual_source", domains={"official": "example.org"})
    result = connector.test_connection(config, transport)
    assert result.result == "unsupported"
    assert calls == []


def test_missing_registered_domain_is_unsupported_not_a_crash() -> None:
    connector = BhashiniConnector()
    config = ConnectorConfig(provider_code="bhashini", domains={})
    result = connector.test_connection(config, _transport(HttpResponse(0, 0, False)))
    assert result.result == "unsupported"
    assert result.error_code == "no_registered_domain"


def test_partial_result_for_unexpected_status_code() -> None:
    connector = GenericPublicApiConnector()
    config = ConnectorConfig(
        provider_code="generic_public_api", domains={"official": "example.org"}
    )
    result = connector.test_connection(
        config, _transport(HttpResponse(status_code=500, elapsed_ms=20, reachable=True))
    )
    assert result.result == "partial"


def test_get_connector_falls_back_to_generic_for_unknown_type() -> None:
    connector = get_connector("not_a_real_connector_type")
    assert isinstance(connector, GenericPublicApiConnector)


def test_get_connector_resolves_known_types() -> None:
    assert isinstance(get_connector("huggingface"), HuggingFaceConnector)
    assert isinstance(get_connector("manual_source"), ManualProviderConnector)


def test_capabilities_never_include_download_or_write() -> None:
    for connector_class in (
        AI4BharatConnector, HuggingFaceConnector, GitHubConnector, WikimediaConnector,
        BhashiniConnector, GenericPublicApiConnector, ManualProviderConnector,
    ):
        connector = connector_class()
        capabilities = connector.get_capabilities(
            ConnectorConfig(provider_code=connector_class.provider_code)
        )
        assert "download_sample" not in capabilities
        assert "download_full" not in capabilities
        assert "upload" not in capabilities
        assert "write_metadata" not in capabilities
