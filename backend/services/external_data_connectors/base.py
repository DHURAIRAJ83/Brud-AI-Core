"""Phase 9 connector contract: a strict, minimal interface every
built-in and future external-data-provider connector implements.
Connectors perform only bounded, read-only reachability/metadata
checks -- no search, no download, no write, matching this phase's
explicit scope boundary (see
docs/data_providers/phase9_external_data_provider_registry_plan.md
section 4).

Phase 10 (Step 4) adds two additive, optional-by-default search
capabilities -- ``search_datasets``/``get_dataset_metadata`` -- to the
same connector contract. They are read-only metadata lookups, never a
download: no connector here ever fetches a file body, clones a
repository, or executes anything from a provider's response. A
connector that cannot search raises `ConnectorSearchError(status=
"unsupported")` rather than fabricating an empty-but-successful
result, so the caller can honestly record why a provider contributed
nothing to a search session.

Every connector receives an injectable HTTP transport callable so
tests never make a real network call -- `default_http_transport` (the
only implementation that performs real I/O) is used solely by the
production dependency wiring in `ExternalDataProviderConnectionService`
/ the Phase 10 discovery search service.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

if TYPE_CHECKING:
    from core_model.data_discovery.candidate_model import (
        DatasetSearchRequest,
        DatasetSearchResult,
        NormalizedDatasetMetadata,
    )

DEFAULT_TIMEOUT_SECONDS = 5.0

# Bounds the *raw HTTP response body* read by `default_http_transport`,
# distinct from `core_model.data_discovery.MAX_RAW_METADATA_BYTES` (which
# bounds one candidate's persisted raw-metadata field after parsing) --
# this guards against an untrusted provider returning an unbounded
# response before any parsing happens.
MAX_TRANSPORT_BODY_BYTES = 1_000_000


class HttpResponse(NamedTuple):
    status_code: int
    elapsed_ms: int
    reachable: bool
    error: str | None = None
    body: str = ""


HttpTransport = Callable[[str, dict[str, str], float], HttpResponse]


class ConnectorSearchError(RuntimeError):
    """Raised by `search_datasets`/`get_dataset_metadata` whenever the
    provider could not be searched -- carries a `status` matching one
    of `core_model.data_discovery.PROVIDER_RUN_STATUSES` (never
    `"success"`) so the caller can record an honest provider-run
    outcome instead of inventing an empty-but-successful result."""

    def __init__(self, status: str, error_code: str, message: str = "") -> None:
        super().__init__(message or error_code)
        self.status = status
        self.error_code = error_code


def default_http_transport(
    url: str, headers: dict[str, str], timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
) -> HttpResponse:
    """The only real-network implementation of `HttpTransport` in this
    codebase. GET-only, bounded timeout, redirects not followed (a
    provider claiming a domain that merely redirects elsewhere is not
    evidence of anything about the redirect target), never raises --
    any failure (DNS, TLS, timeout, connection refused) becomes a
    bounded `HttpResponse(reachable=False, ...)` rather than an
    exception, so a connection test can never crash the request. The
    response body is bounded and always treated as untrusted text by
    callers -- never executed, never used to construct a further
    request URL."""

    import httpx

    started = time.perf_counter()
    try:
        response = httpx.get(url, headers=headers, timeout=timeout_seconds, follow_redirects=False)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return HttpResponse(
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            reachable=True,
            body=response.text[:MAX_TRANSPORT_BODY_BYTES],
        )
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return HttpResponse(
            status_code=0, elapsed_ms=elapsed_ms, reachable=False, error=type(exc).__name__
        )


@dataclass(frozen=True)
class ConnectorConfig:
    provider_code: str
    domains: dict[str, str] = field(default_factory=dict)  # domain_type -> domain
    credential_value: str | None = None  # resolved secret, in-memory only, never logged/persisted
    credential_type: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class ConnectionTestResult:
    result: str  # one of core_model.data_providers.CONNECTION_TEST_RESULTS
    capability_type: str | None = None
    latency_ms: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None


class ExternalDataProviderConnector(Protocol):
    def test_connection(
        self, config: ConnectorConfig, transport: HttpTransport
    ) -> ConnectionTestResult: ...

    def get_provider_metadata(self, config: ConnectorConfig) -> dict[str, Any]: ...

    def get_capabilities(self, config: ConnectorConfig) -> list[str]: ...

    def search_datasets(
        self, config: ConnectorConfig, transport: HttpTransport, request: DatasetSearchRequest
    ) -> DatasetSearchResult: ...

    def get_dataset_metadata(
        self, config: ConnectorConfig, transport: HttpTransport, provider_dataset_id: str
    ) -> NormalizedDatasetMetadata | None: ...


class BaseHttpConnector:
    """Shared logic for every connector that performs a bounded GET
    against one of the provider's own already-registered domains --
    never an admin-supplied arbitrary URL, which is what keeps this
    from becoming an open SSRF/crawler vector. Subclasses declare which
    `domain_type` to probe and their static capability/metadata list;
    `test_connection` does the actual bounded request."""

    provider_code: str = ""
    probe_domain_type: str = "official"
    static_capabilities: tuple[str, ...] = ("read_metadata",)
    static_metadata: dict[str, Any] = {}

    def get_capabilities(self, config: ConnectorConfig) -> list[str]:
        del config
        return list(self.static_capabilities)

    def get_provider_metadata(self, config: ConnectorConfig) -> dict[str, Any]:
        del config
        return dict(self.static_metadata)

    def test_connection(
        self, config: ConnectorConfig, transport: HttpTransport
    ) -> ConnectionTestResult:
        domain = config.domains.get(self.probe_domain_type)
        if not domain:
            return ConnectionTestResult(
                result="unsupported",
                error_code="no_registered_domain",
                evidence={"probe_domain_type": self.probe_domain_type},
            )
        headers: dict[str, str] = {}
        if config.credential_value:
            if config.credential_type == "bearer_token":
                headers["Authorization"] = f"Bearer {config.credential_value}"
            elif config.credential_type == "api_key":
                headers["X-API-Key"] = config.credential_value
        url = f"https://{domain}"
        response = transport(url, headers, config.timeout_seconds)
        if not response.reachable:
            return ConnectionTestResult(
                result="failed",
                latency_ms=response.elapsed_ms,
                error_code=response.error or "unreachable",
                evidence={"url": url},
            )
        if response.status_code in (401, 403):
            return ConnectionTestResult(
                result="authentication_required",
                latency_ms=response.elapsed_ms,
                evidence={"url": url, "status_code": response.status_code},
            )
        if response.status_code == 429:
            return ConnectionTestResult(
                result="rate_limited",
                latency_ms=response.elapsed_ms,
                evidence={"url": url, "status_code": response.status_code},
            )
        if 200 <= response.status_code < 400:
            return ConnectionTestResult(
                result="success",
                latency_ms=response.elapsed_ms,
                evidence={"url": url, "status_code": response.status_code},
            )
        return ConnectionTestResult(
            result="partial",
            latency_ms=response.elapsed_ms,
            evidence={"url": url, "status_code": response.status_code},
        )

    def search_datasets(
        self, config: ConnectorConfig, transport: HttpTransport, request: DatasetSearchRequest
    ) -> DatasetSearchResult:
        """Honest default for every connector without a dedicated
        search implementation (mirrors `ManualProviderConnector.
        test_connection`'s `"unsupported"` pattern) -- never returns a
        fabricated empty-but-successful result."""

        del config, transport, request
        raise ConnectorSearchError(
            status="unsupported",
            error_code="search_not_supported_by_connector",
            message=(
                f"{self.provider_code or self.__class__.__name__} "
                "does not support dataset search"
            ),
        )

    def get_dataset_metadata(
        self, config: ConnectorConfig, transport: HttpTransport, provider_dataset_id: str
    ) -> NormalizedDatasetMetadata | None:
        del config, transport, provider_dataset_id
        raise ConnectorSearchError(
            status="unsupported",
            error_code="metadata_lookup_not_supported_by_connector",
            message=(
                f"{self.provider_code or self.__class__.__name__} "
                "does not support single-dataset metadata lookup"
            ),
        )
