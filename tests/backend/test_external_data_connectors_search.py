import json

import pytest

from backend.services.external_data_connectors.base import (
    ConnectorConfig,
    ConnectorSearchError,
    HttpResponse,
)
from backend.services.external_data_connectors.builtin import (
    AI4BharatConnector,
    BhashiniConnector,
    GenericPublicApiConnector,
    GitHubConnector,
    HuggingFaceConnector,
    ManualProviderConnector,
    WikimediaConnector,
)
from core_model.data_discovery.candidate_model import DatasetSearchRequest


def _transport(response: HttpResponse):
    def transport(url, headers, timeout_seconds):
        del url, headers, timeout_seconds
        return response

    return transport


def _json_response(payload, *, status_code=200) -> HttpResponse:
    return HttpResponse(
        status_code=status_code, elapsed_ms=5, reachable=True, body=json.dumps(payload)
    )


REQUEST = DatasetSearchRequest(query="tamil asr", limit=5)


# -- connectors without a real search implementation ------------------------


@pytest.mark.parametrize(
    "connector_class,domains",
    [
        (AI4BharatConnector, {"official": "ai4bharat.org"}),
        (BhashiniConnector, {"official": "bhashini.gov.in"}),
        (GenericPublicApiConnector, {"official": "example.org"}),
    ],
)
def test_connectors_without_search_report_unsupported(connector_class, domains) -> None:
    connector = connector_class()
    config = ConnectorConfig(provider_code=connector.provider_code, domains=domains)
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(config, _transport(_json_response([])), REQUEST)
    assert excinfo.value.status == "unsupported"

    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.get_dataset_metadata(config, _transport(_json_response({})), "anything")
    assert excinfo.value.status == "unsupported"


def test_manual_connector_reports_unsupported() -> None:
    connector = ManualProviderConnector()
    config = ConnectorConfig(provider_code="manual_source")
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(config, _transport(_json_response([])), REQUEST)
    assert excinfo.value.status == "unsupported"
    assert excinfo.value.error_code == "manual_provider_has_no_api"


# -- Hugging Face -------------------------------------------------------------


def _hf_config() -> ConnectorConfig:
    return ConnectorConfig(provider_code="huggingface", domains={"api": "huggingface.co"})


def test_huggingface_search_normalizes_results() -> None:
    connector = HuggingFaceConnector()
    payload = [
        {
            "id": "ai4bharat/indicvoices-tamil",
            "cardData": {"summary": "Tamil speech corpus", "license": "cc-by-4.0"},
            "tags": ["asr", "tamil"],
            "siblings": [{"rfilename": "data/train.parquet"}, {"rfilename": "README.md"}],
            "lastModified": "2025-01-01T00:00:00.000Z",
            "gated": False,
            "private": False,
        }
    ]
    result = connector.search_datasets(_hf_config(), _transport(_json_response(payload)), REQUEST)
    assert len(result.items) == 1
    item = result.items[0]
    assert item.provider_dataset_id == "ai4bharat/indicvoices-tamil"
    assert item.organization == "ai4bharat"
    assert item.description == "Tamil speech corpus"
    assert item.licence_declared == "cc-by-4.0"
    assert item.file_formats == ("md", "parquet")
    assert item.gated is False
    assert item.raw_metadata == payload[0]


def test_huggingface_search_skips_malformed_entries() -> None:
    connector = HuggingFaceConnector()
    payload = [{"no_id_field": True}, {"id": "org/valid-dataset"}]
    result = connector.search_datasets(_hf_config(), _transport(_json_response(payload)), REQUEST)
    assert [item.provider_dataset_id for item in result.items] == ["org/valid-dataset"]


def test_huggingface_get_dataset_metadata_not_found() -> None:
    connector = HuggingFaceConnector()
    response = HttpResponse(status_code=404, elapsed_ms=5, reachable=True, body="{}")
    metadata = connector.get_dataset_metadata(_hf_config(), _transport(response), "org/missing")
    assert metadata is None


def test_huggingface_search_maps_rate_limit() -> None:
    connector = HuggingFaceConnector()
    response = HttpResponse(status_code=429, elapsed_ms=5, reachable=True, body="{}")
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(_hf_config(), _transport(response), REQUEST)
    assert excinfo.value.status == "rate_limited"


def test_huggingface_search_maps_auth_required() -> None:
    connector = HuggingFaceConnector()
    response = HttpResponse(status_code=401, elapsed_ms=5, reachable=True, body="{}")
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(_hf_config(), _transport(response), REQUEST)
    assert excinfo.value.status == "authentication_required"


def test_huggingface_search_maps_timeout() -> None:
    connector = HuggingFaceConnector()
    response = HttpResponse(
        status_code=0, elapsed_ms=5000, reachable=False, error="ConnectTimeout"
    )
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(_hf_config(), _transport(response), REQUEST)
    assert excinfo.value.status == "timeout"


def test_huggingface_search_rejects_invalid_json_body() -> None:
    connector = HuggingFaceConnector()
    response = HttpResponse(status_code=200, elapsed_ms=5, reachable=True, body="not json")
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(_hf_config(), _transport(response), REQUEST)
    assert excinfo.value.status == "failed"
    assert excinfo.value.error_code == "invalid_response_body"


def test_huggingface_search_rejects_unexpected_shape() -> None:
    connector = HuggingFaceConnector()
    response = _json_response({"not": "a list"})
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(_hf_config(), _transport(response), REQUEST)
    assert excinfo.value.error_code == "unexpected_response_shape"


def test_huggingface_search_without_registered_domain() -> None:
    connector = HuggingFaceConnector()
    config = ConnectorConfig(provider_code="huggingface", domains={})
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(config, _transport(_json_response([])), REQUEST)
    assert excinfo.value.status == "unsupported"
    assert excinfo.value.error_code == "no_registered_domain"


# -- GitHub -------------------------------------------------------------------


def _github_config() -> ConnectorConfig:
    return ConnectorConfig(provider_code="github", domains={"api": "api.github.com"})


def test_github_search_normalizes_results() -> None:
    connector = GitHubConnector()
    payload = {
        "items": [
            {
                "full_name": "ai4bharat/indic-asr",
                "name": "indic-asr",
                "description": "Indic ASR datasets",
                "owner": {"login": "ai4bharat"},
                "topics": ["asr", "tamil"],
                "html_url": "https://github.com/ai4bharat/indic-asr",
                "license": {"spdx_id": "MIT"},
                "updated_at": "2025-02-01T00:00:00Z",
                "private": False,
            }
        ]
    }
    result = connector.search_datasets(
        _github_config(), _transport(_json_response(payload)), REQUEST
    )
    assert len(result.items) == 1
    item = result.items[0]
    assert item.provider_dataset_id == "ai4bharat/indic-asr"
    assert item.organization == "ai4bharat"
    assert item.licence_declared == "MIT"
    assert item.repository_url == "https://github.com/ai4bharat/indic-asr"


def test_github_search_rejects_unexpected_shape() -> None:
    connector = GitHubConnector()
    response = _json_response({"items": "not a list"})
    with pytest.raises(ConnectorSearchError) as excinfo:
        connector.search_datasets(_github_config(), _transport(response), REQUEST)
    assert excinfo.value.error_code == "unexpected_response_shape"


def test_github_get_dataset_metadata_not_found() -> None:
    connector = GitHubConnector()
    response = HttpResponse(status_code=404, elapsed_ms=5, reachable=True, body="{}")
    metadata = connector.get_dataset_metadata(_github_config(), _transport(response), "org/x")
    assert metadata is None


# -- Wikimedia ------------------------------------------------------------------


def _wikimedia_config() -> ConnectorConfig:
    return ConnectorConfig(provider_code="wikimedia", domains={"api": "www.wikidata.org"})


def test_wikimedia_search_normalizes_results() -> None:
    connector = WikimediaConnector()
    payload = {
        "search": [
            {"id": "Q123", "label": "Tamil language corpus", "description": "a dataset item"}
        ]
    }
    result = connector.search_datasets(
        _wikimedia_config(), _transport(_json_response(payload)), REQUEST
    )
    assert len(result.items) == 1
    item = result.items[0]
    assert item.provider_dataset_id == "Q123"
    assert item.name == "Tamil language corpus"
    assert item.homepage_url == "https://www.wikidata.org/wiki/Q123"


def test_wikimedia_get_dataset_metadata_missing_entity() -> None:
    connector = WikimediaConnector()
    payload = {"entities": {"Q999": {"id": "Q999", "missing": ""}}}
    result = connector.get_dataset_metadata(
        _wikimedia_config(), _transport(_json_response(payload)), "Q999"
    )
    assert result is None


def test_wikimedia_get_dataset_metadata_found() -> None:
    connector = WikimediaConnector()
    payload = {
        "entities": {
            "Q123": {
                "id": "Q123",
                "labels": {"en": {"value": "Tamil language corpus"}},
                "descriptions": {"en": {"value": "a dataset item"}},
            }
        }
    }
    result = connector.get_dataset_metadata(
        _wikimedia_config(), _transport(_json_response(payload)), "Q123"
    )
    assert result is not None
    assert result.name == "Tamil language corpus"
    assert result.description == "a dataset item"


# -- one provider's failure never crashes another's request -------------------


def test_connector_search_error_carries_status_for_caller_bookkeeping() -> None:
    connector = HuggingFaceConnector()
    response = HttpResponse(status_code=503, elapsed_ms=10, reachable=True, body="{}")
    try:
        connector.search_datasets(_hf_config(), _transport(response), REQUEST)
        raise AssertionError("expected ConnectorSearchError")
    except ConnectorSearchError as error:
        assert error.status == "failed"
        assert error.error_code == "http_503"
