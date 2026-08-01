"""Built-in connectors for the 8 seeded providers (Step 6). Every
connector implements only bounded reachability + static
capability/metadata description -- no search, no download, no write.
Capabilities listed here are deliberately conservative and match only
what plan.md/Step 6 documents; nothing here grants a dataset licence,
training permission, or RAG-use approval -- that remains entirely a
Source & Rights Registry concern, untouched by this module.

Phase 10 (Step 4) adds real ``search_datasets``/``get_dataset_metadata``
implementations to exactly three connectors -- Hugging Face, GitHub,
and Wikimedia -- each of which has a stable, publicly documented,
unauthenticated-capable search endpoint. AI4Bharat and Bhashini keep
the inherited `BaseHttpConnector` default (`"unsupported"`, honestly)
because neither has a confirmed stable public search API; the generic
and manual connectors are unaffected. Every parsed field is read
defensively from untrusted JSON text -- a missing/malformed field
becomes ``None``/empty, never a guess, and nothing here ever follows a
link into an unregistered domain or executes any part of a response.
"""

from __future__ import annotations

import json
from urllib.parse import quote

from backend.services.external_data_connectors.base import (
    BaseHttpConnector,
    ConnectionTestResult,
    ConnectorConfig,
    ConnectorSearchError,
    ExternalDataProviderConnector,
    HttpResponse,
    HttpTransport,
)
from core_model.data_discovery import MAX_RESULTS_PER_PROVIDER
from core_model.data_discovery.candidate_model import (
    DatasetSearchRequest,
    DatasetSearchResult,
    NormalizedDatasetMetadata,
)


def _auth_headers(config: ConnectorConfig) -> dict[str, str]:
    if not config.credential_value:
        return {}
    if config.credential_type == "bearer_token":
        return {"Authorization": f"Bearer {config.credential_value}"}
    if config.credential_type == "api_key":
        return {"X-API-Key": config.credential_value}
    return {}


def _run_status_for_response(response: HttpResponse) -> tuple[str, str]:
    """Maps a bounded `HttpResponse` to a `(status, error_code)` pair
    drawn from `core_model.data_discovery.PROVIDER_RUN_FAILURE_STATUSES`
    -- shared by every real search connector below so the mapping stays
    identical to `BaseHttpConnector.test_connection`'s."""

    if not response.reachable:
        error = response.error or "unreachable"
        if error in ("ConnectTimeout", "ReadTimeout", "TimeoutException", "PoolTimeout"):
            return "timeout", error
        return "failed", error
    if response.status_code in (401, 403):
        return "authentication_required", f"http_{response.status_code}"
    if response.status_code == 429:
        return "rate_limited", "http_429"
    if response.status_code >= 500 or response.status_code == 0:
        return "failed", f"http_{response.status_code}"
    if response.status_code >= 400:
        return "failed", f"http_{response.status_code}"
    return "success", ""


def _parse_json_body(response: HttpResponse, *, error_code: str) -> object:
    try:
        return json.loads(response.body)
    except (ValueError, TypeError) as exc:
        raise ConnectorSearchError(
            status="failed", error_code=error_code, message=str(exc)
        ) from exc


class AI4BharatConnector(BaseHttpConnector):
    provider_code = "ai4bharat"
    probe_domain_type = "official"
    static_capabilities = ("read_metadata",)
    static_metadata = {
        "provider_type": "research_institution",
        "access_mode": "mixed",
        "notes": "Catalogue and manual discovery only; dataset-specific licences vary per dataset.",
    }


class HuggingFaceConnector(BaseHttpConnector):
    provider_code = "huggingface"
    probe_domain_type = "api"
    static_capabilities = ("search_datasets", "read_dataset_card", "list_files")
    static_metadata = {
        "provider_type": "repository_host",
        "access_mode": "mixed",
        "notes": "Public datasets are anonymously readable; gated/private datasets require a "
        "token.",
    }

    def search_datasets(
        self, config: ConnectorConfig, transport: HttpTransport, request: DatasetSearchRequest
    ) -> DatasetSearchResult:
        domain = config.domains.get(self.probe_domain_type) or config.domains.get("official")
        if not domain:
            raise ConnectorSearchError(status="unsupported", error_code="no_registered_domain")
        limit = max(1, min(request.limit, MAX_RESULTS_PER_PROVIDER))
        query = quote(request.query)
        url = f"https://{domain}/api/datasets?search={query}&limit={limit}&full=true"
        response = transport(url, _auth_headers(config), config.timeout_seconds)
        status, error_code = _run_status_for_response(response)
        if status != "success":
            raise ConnectorSearchError(status=status, error_code=error_code)
        payload = _parse_json_body(response, error_code="invalid_response_body")
        if not isinstance(payload, list):
            raise ConnectorSearchError(status="failed", error_code="unexpected_response_shape")
        items = tuple(
            item
            for item in (self._normalize(entry) for entry in payload[:limit])
            if item is not None
        )
        return DatasetSearchResult(items=items)

    def get_dataset_metadata(
        self, config: ConnectorConfig, transport: HttpTransport, provider_dataset_id: str
    ) -> NormalizedDatasetMetadata | None:
        domain = config.domains.get(self.probe_domain_type) or config.domains.get("official")
        if not domain:
            raise ConnectorSearchError(status="unsupported", error_code="no_registered_domain")
        url = f"https://{domain}/api/datasets/{quote(provider_dataset_id, safe='/')}"
        response = transport(url, _auth_headers(config), config.timeout_seconds)
        if response.reachable and response.status_code == 404:
            return None
        status, error_code = _run_status_for_response(response)
        if status != "success":
            raise ConnectorSearchError(status=status, error_code=error_code)
        payload = _parse_json_body(response, error_code="invalid_response_body")
        if not isinstance(payload, dict):
            raise ConnectorSearchError(status="failed", error_code="unexpected_response_shape")
        return self._normalize(payload)

    @staticmethod
    def _normalize(entry: object) -> NormalizedDatasetMetadata | None:
        if not isinstance(entry, dict):
            return None
        dataset_id = entry.get("id")
        if not isinstance(dataset_id, str) or not dataset_id:
            return None
        card_data = entry.get("cardData") if isinstance(entry.get("cardData"), dict) else {}
        tags = entry.get("tags") if isinstance(entry.get("tags"), list) else []
        siblings = entry.get("siblings") if isinstance(entry.get("siblings"), list) else []
        file_formats = tuple(
            sorted(
                {
                    sibling["rfilename"].rsplit(".", 1)[-1].lower()
                    for sibling in siblings
                    if isinstance(sibling, dict)
                    and isinstance(sibling.get("rfilename"), str)
                    and "." in sibling["rfilename"]
                }
            )
        )
        organization = dataset_id.split("/", 1)[0] if "/" in dataset_id else None
        return NormalizedDatasetMetadata(
            provider_dataset_id=dataset_id,
            name=dataset_id.split("/", 1)[-1],
            description=str(card_data.get("summary") or entry.get("description") or ""),
            organization=organization,
            tags=tuple(str(tag) for tag in tags),
            dataset_card_url=f"https://huggingface.co/datasets/{dataset_id}",
            repository_url=f"https://huggingface.co/datasets/{dataset_id}",
            homepage_url=f"https://huggingface.co/datasets/{dataset_id}",
            licence_declared=(str(card_data.get("license")) if card_data.get("license") else None),
            file_formats=file_formats,
            last_modified_at=(
                str(entry["lastModified"]) if isinstance(entry.get("lastModified"), str) else None
            ),
            gated=bool(entry.get("gated")),
            private=bool(entry.get("private")),
            requires_authentication=bool(entry.get("gated") or entry.get("private")),
            raw_metadata=entry,
        )


class GitHubConnector(BaseHttpConnector):
    provider_code = "github"
    probe_domain_type = "api"
    static_capabilities = ("read_metadata", "read_licence", "list_files")
    static_metadata = {
        "provider_type": "repository_host",
        "access_mode": "mixed",
        "notes": "Repository metadata, releases, and licence files only; a token raises rate "
        "limits.",
    }

    def search_datasets(
        self, config: ConnectorConfig, transport: HttpTransport, request: DatasetSearchRequest
    ) -> DatasetSearchResult:
        domain = config.domains.get(self.probe_domain_type)
        if not domain:
            raise ConnectorSearchError(status="unsupported", error_code="no_registered_domain")
        limit = max(1, min(request.limit, MAX_RESULTS_PER_PROVIDER))
        query = quote(request.query)
        url = f"https://{domain}/search/repositories?q={query}&per_page={limit}"
        response = transport(url, self._headers(config), config.timeout_seconds)
        status, error_code = _run_status_for_response(response)
        if status != "success":
            raise ConnectorSearchError(status=status, error_code=error_code)
        payload = _parse_json_body(response, error_code="invalid_response_body")
        items_raw = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items_raw, list):
            raise ConnectorSearchError(status="failed", error_code="unexpected_response_shape")
        items = tuple(
            item
            for item in (self._normalize(entry) for entry in items_raw[:limit])
            if item is not None
        )
        return DatasetSearchResult(items=items)

    def get_dataset_metadata(
        self, config: ConnectorConfig, transport: HttpTransport, provider_dataset_id: str
    ) -> NormalizedDatasetMetadata | None:
        domain = config.domains.get(self.probe_domain_type)
        if not domain:
            raise ConnectorSearchError(status="unsupported", error_code="no_registered_domain")
        url = f"https://{domain}/repos/{quote(provider_dataset_id, safe='/')}"
        response = transport(url, self._headers(config), config.timeout_seconds)
        if response.reachable and response.status_code == 404:
            return None
        status, error_code = _run_status_for_response(response)
        if status != "success":
            raise ConnectorSearchError(status=status, error_code=error_code)
        payload = _parse_json_body(response, error_code="invalid_response_body")
        if not isinstance(payload, dict):
            raise ConnectorSearchError(status="failed", error_code="unexpected_response_shape")
        return self._normalize(payload)

    @staticmethod
    def _headers(config: ConnectorConfig) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "BrudAI-DataDiscovery"}
        headers.update(_auth_headers(config))
        return headers

    @staticmethod
    def _normalize(entry: object) -> NormalizedDatasetMetadata | None:
        if not isinstance(entry, dict):
            return None
        full_name = entry.get("full_name")
        if not isinstance(full_name, str) or not full_name:
            return None
        owner = entry.get("owner") if isinstance(entry.get("owner"), dict) else {}
        license_info = entry.get("license") if isinstance(entry.get("license"), dict) else {}
        topics = entry.get("topics") if isinstance(entry.get("topics"), list) else []
        return NormalizedDatasetMetadata(
            provider_dataset_id=full_name,
            name=str(entry.get("name") or full_name.split("/")[-1]),
            description=str(entry.get("description") or ""),
            organization=(str(owner.get("login")) if owner.get("login") else None),
            tags=tuple(str(topic) for topic in topics),
            repository_url=(
                str(entry["html_url"]) if isinstance(entry.get("html_url"), str) else None
            ),
            homepage_url=(
                str(entry["homepage"]) if isinstance(entry.get("homepage"), str) else None
            ),
            licence_declared=(
                str(license_info.get("spdx_id")) if license_info.get("spdx_id") else None
            ),
            last_modified_at=(
                str(entry["updated_at"]) if isinstance(entry.get("updated_at"), str) else None
            ),
            private=bool(entry.get("private")),
            requires_authentication=bool(entry.get("private")),
            raw_metadata=entry,
        )


class WikimediaConnector(BaseHttpConnector):
    provider_code = "wikimedia"
    probe_domain_type = "api"
    static_capabilities = ("read_metadata", "search_datasets")
    static_metadata = {
        "provider_type": "public_api",
        "access_mode": "public",
        "notes": "Read-only metadata/API access; no authentication required for public content.",
    }

    def search_datasets(
        self, config: ConnectorConfig, transport: HttpTransport, request: DatasetSearchRequest
    ) -> DatasetSearchResult:
        domain = config.domains.get(self.probe_domain_type)
        if not domain:
            raise ConnectorSearchError(status="unsupported", error_code="no_registered_domain")
        limit = max(1, min(request.limit, MAX_RESULTS_PER_PROVIDER))
        query = quote(request.query)
        url = (
            f"https://{domain}/w/api.php?action=wbsearchentities&search={query}"
            f"&language=en&format=json&limit={limit}"
        )
        response = transport(url, _auth_headers(config), config.timeout_seconds)
        status, error_code = _run_status_for_response(response)
        if status != "success":
            raise ConnectorSearchError(status=status, error_code=error_code)
        payload = _parse_json_body(response, error_code="invalid_response_body")
        hits = payload.get("search") if isinstance(payload, dict) else None
        if not isinstance(hits, list):
            raise ConnectorSearchError(status="failed", error_code="unexpected_response_shape")
        items = tuple(
            item
            for item in (self._normalize(entry, domain) for entry in hits[:limit])
            if item is not None
        )
        return DatasetSearchResult(items=items)

    def get_dataset_metadata(
        self, config: ConnectorConfig, transport: HttpTransport, provider_dataset_id: str
    ) -> NormalizedDatasetMetadata | None:
        domain = config.domains.get(self.probe_domain_type)
        if not domain:
            raise ConnectorSearchError(status="unsupported", error_code="no_registered_domain")
        entity_id = quote(provider_dataset_id)
        url = (
            f"https://{domain}/w/api.php?action=wbgetentities&ids={entity_id}"
            "&languages=en&format=json"
        )
        response = transport(url, _auth_headers(config), config.timeout_seconds)
        status, error_code = _run_status_for_response(response)
        if status != "success":
            raise ConnectorSearchError(status=status, error_code=error_code)
        payload = _parse_json_body(response, error_code="invalid_response_body")
        entities = payload.get("entities") if isinstance(payload, dict) else None
        entity = entities.get(provider_dataset_id) if isinstance(entities, dict) else None
        if not isinstance(entity, dict) or entity.get("missing") is not None:
            return None
        labels = entity.get("labels") if isinstance(entity.get("labels"), dict) else {}
        descriptions = (
            entity.get("descriptions") if isinstance(entity.get("descriptions"), dict) else {}
        )
        label = labels.get("en", {}).get("value") if isinstance(labels.get("en"), dict) else None
        description = (
            descriptions.get("en", {}).get("value")
            if isinstance(descriptions.get("en"), dict)
            else None
        )
        return NormalizedDatasetMetadata(
            provider_dataset_id=str(entity.get("id") or provider_dataset_id),
            name=str(label or provider_dataset_id),
            description=str(description or ""),
            homepage_url=f"https://{domain}/wiki/{provider_dataset_id}",
            raw_metadata=entity,
        )

    @staticmethod
    def _normalize(entry: object, domain: str) -> NormalizedDatasetMetadata | None:
        if not isinstance(entry, dict):
            return None
        entity_id = entry.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            return None
        return NormalizedDatasetMetadata(
            provider_dataset_id=entity_id,
            name=str(entry.get("label") or entity_id),
            description=str(entry.get("description") or ""),
            homepage_url=f"https://{domain}/wiki/{entity_id}",
            raw_metadata=entry,
        )


class BhashiniConnector(BaseHttpConnector):
    provider_code = "bhashini"
    probe_domain_type = "official"
    static_capabilities = ("read_metadata",)
    static_metadata = {
        "provider_type": "government_portal",
        "access_mode": "mixed",
        "notes": "India's National Language Translation Mission; some endpoints require API "
        "access.",
    }


class GenericPublicApiConnector(BaseHttpConnector):
    """Fallback connector for any `custom_api` provider an admin
    registers without a dedicated built-in connector -- deliberately
    the most conservative: reachability only, no capability assumed
    beyond reading metadata."""

    provider_code = "generic_public_api"
    probe_domain_type = "official"
    static_capabilities = ("read_metadata",)
    static_metadata = {"provider_type": "custom_api", "access_mode": "mixed"}


class ManualProviderConnector:
    """For `manual_source` providers with no API at all (e.g. "a
    university library you email"). Never attempts a network call --
    `test_connection` always reports `unsupported`, honestly, rather
    than fabricating a reachability result for a provider that has no
    programmatic endpoint to reach."""

    provider_code = "manual_source"
    static_capabilities: tuple[str, ...] = ()
    static_metadata = {"provider_type": "manual_source", "access_mode": "manual"}

    def get_capabilities(self, config: ConnectorConfig) -> list[str]:
        del config
        return list(self.static_capabilities)

    def get_provider_metadata(self, config: ConnectorConfig) -> dict[str, str]:
        del config
        return dict(self.static_metadata)

    def test_connection(
        self, config: ConnectorConfig, transport: HttpTransport
    ) -> ConnectionTestResult:
        del config, transport
        return ConnectionTestResult(
            result="unsupported",
            error_code="manual_provider_has_no_api",
            evidence={"reason": "manual_source providers have no programmatic endpoint"},
        )

    def search_datasets(
        self, config: ConnectorConfig, transport: HttpTransport, request: DatasetSearchRequest
    ) -> DatasetSearchResult:
        del config, transport, request
        raise ConnectorSearchError(
            status="unsupported",
            error_code="manual_provider_has_no_api",
            message="manual_source providers have no programmatic search endpoint",
        )

    def get_dataset_metadata(
        self, config: ConnectorConfig, transport: HttpTransport, provider_dataset_id: str
    ) -> NormalizedDatasetMetadata | None:
        del config, transport, provider_dataset_id
        raise ConnectorSearchError(
            status="unsupported",
            error_code="manual_provider_has_no_api",
            message="manual_source providers have no programmatic metadata endpoint",
        )


CONNECTOR_REGISTRY: dict[str, type] = {
    "ai4bharat": AI4BharatConnector,
    "huggingface": HuggingFaceConnector,
    "github": GitHubConnector,
    "wikimedia": WikimediaConnector,
    "bhashini": BhashiniConnector,
    "generic_public_api": GenericPublicApiConnector,
    "manual_source": ManualProviderConnector,
}


def get_connector(connector_type: str | None) -> ExternalDataProviderConnector:
    connector_class = CONNECTOR_REGISTRY.get(connector_type or "", GenericPublicApiConnector)
    return connector_class()
