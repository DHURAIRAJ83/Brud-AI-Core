"""Phase 20 Step 4 -- concrete `WebSearchProvider` adapters.

Two implementations:

`WikipediaSearchProvider` -- the zero-config, key-free **default**
provider (`Settings.trusted_web_provider_name` defaults to
`"wikipedia"`). Calls Wikipedia's official, public REST search API, no
credential needed, so `trusted_web` can genuinely execute end-to-end
out of the box rather than being permanently unconfigured. Narrow,
disclosed coverage (strong for stable/encyclopedic topics) -- a real,
working, cost-controlled default, not a stub.

`ConfigurableSearchApiProvider` -- generic over any real, paid search
API that returns a Brave/Bing-shaped JSON result list
(`{"web": {"results": [...]}}` or a flat `{"results": [...]}}`) via a
configured `base_url` + API key -- not tied to one paid vendor's SDK.
Selected by setting `BRUD_TRUSTED_WEB_PROVIDER_NAME` to anything other
than `"wikipedia"`; with no `base_url`/`api_key` configured it reports
unhealthy and `trusted_web` honestly resolves to `insufficient` --
still the correct, cost-controlled, fail-closed behavior for this path
(Step 4: "Default behavior must remain cost-controlled and
fail-closed").

Every real network call goes through an injectable transport callable
(`default_search_transport` is the only implementation that performs
real I/O), mirroring `dataset_verification_transport.py`'s own
established pattern, so tests never make a real network call.

A lightweight, in-process circuit breaker (module-level, thread-safe,
same style as `public_chat_rate_limiter.py`) tracks consecutive search
failures so `health_check()` never has to make its own network call on
every single route-availability check -- it would otherwise burn
provider quota just from *asking* if the provider is healthy on every
public chat request.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NamedTuple
from urllib.parse import urlparse

from core_model.web_search.provider_contract import (
    NormalizedSearchResult,
    ProviderHealthStatus,
    SearchOptions,
    WebSearchProvider,
)

_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_COOLDOWN_SECONDS = 60.0

_circuit_lock = threading.Lock()
_consecutive_failures: dict[str, int] = {}
_circuit_opened_at: dict[str, float] = {}


def _record_search_outcome(provider_name: str, *, success: bool) -> None:
    with _circuit_lock:
        if success:
            _consecutive_failures[provider_name] = 0
            _circuit_opened_at.pop(provider_name, None)
            return
        count = _consecutive_failures.get(provider_name, 0) + 1
        _consecutive_failures[provider_name] = count
        if count >= _CIRCUIT_FAILURE_THRESHOLD:
            _circuit_opened_at[provider_name] = time.monotonic()


def _circuit_is_open(provider_name: str) -> bool:
    with _circuit_lock:
        opened_at = _circuit_opened_at.get(provider_name)
        if opened_at is None:
            return False
        if time.monotonic() - opened_at >= _CIRCUIT_COOLDOWN_SECONDS:
            _circuit_opened_at.pop(provider_name, None)
            _consecutive_failures[provider_name] = 0
            return False
        return True


def reset_provider_circuit(provider_name: str) -> None:
    """Test-only: clear circuit-breaker state."""

    with _circuit_lock:
        _consecutive_failures.pop(provider_name, None)
        _circuit_opened_at.pop(provider_name, None)


class SearchHttpResponse(NamedTuple):
    status_code: int
    body: dict[str, Any] | None
    reachable: bool = True
    error: str | None = None


SearchTransport = Any  # Callable[[str, dict[str, str], dict[str, str], float], SearchHttpResponse]


def default_search_transport(
    url: str, headers: dict[str, str], params: dict[str, str], timeout_seconds: float
) -> SearchHttpResponse:
    """The only real-network implementation. GET-only, bounded
    timeout, no redirects followed (a search-API base_url is a fixed,
    policy-configured endpoint, never a redirect chain)."""

    import httpx

    try:
        response = httpx.get(
            url, headers=headers, params=params, timeout=timeout_seconds, follow_redirects=False
        )
        try:
            body = response.json()
        except ValueError:
            body = None
        return SearchHttpResponse(status_code=response.status_code, body=body)
    except httpx.HTTPError as exc:
        return SearchHttpResponse(
            status_code=0, body=None, reachable=False, error=type(exc).__name__
        )


@dataclass(frozen=True)
class ProviderConfig:
    provider_name: str
    base_url: str | None
    api_key: str | None
    api_key_header: str = "X-Subscription-Token"
    timeout_seconds: float = 5.0


class ConfigurableSearchApiProvider:
    def __init__(
        self, config: ProviderConfig, transport: SearchTransport = default_search_transport
    ) -> None:
        self.provider_name = config.provider_name
        self._config = config
        self._transport = transport

    def capabilities(self) -> list[str]:
        return ["web_search"]

    def health_check(self) -> ProviderHealthStatus:
        if not self._config.base_url or not self._config.api_key:
            return ProviderHealthStatus(healthy=False, reason="provider_not_configured")
        if _circuit_is_open(self.provider_name):
            return ProviderHealthStatus(healthy=False, reason="circuit_open_recent_failures")
        return ProviderHealthStatus(healthy=True)

    def search(self, query: str, options: SearchOptions) -> list[NormalizedSearchResult]:
        if not self._config.base_url or not self._config.api_key:
            _record_search_outcome(self.provider_name, success=False)
            raise ProviderUnavailableError("provider_not_configured")

        headers = {
            self._config.api_key_header: self._config.api_key,
            "Accept": "application/json",
        }
        params = {"q": query, "count": str(options.max_results)}
        response = self._transport(
            self._config.base_url, headers, params, self._config.timeout_seconds
        )
        if not response.reachable:
            _record_search_outcome(self.provider_name, success=False)
            raise ProviderUnavailableError(response.error or "unreachable")
        if response.status_code == 429:
            _record_search_outcome(self.provider_name, success=False)
            raise ProviderQuotaExceededError("rate_limited_by_provider")
        if response.status_code >= 400 or response.body is None:
            _record_search_outcome(self.provider_name, success=False)
            raise ProviderUnavailableError(f"http_{response.status_code}")

        _record_search_outcome(self.provider_name, success=True)
        raw_results = _extract_raw_results(response.body)
        retrieved_at = datetime.now(UTC).isoformat()
        normalized: list[NormalizedSearchResult] = []
        for rank, raw in enumerate(raw_results[: options.max_results], start=1):
            result = _normalize_result(raw, rank, self.provider_name, retrieved_at)
            if result is not None:
                normalized.append(result)
        return normalized


class ProviderUnavailableError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ProviderQuotaExceededError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _extract_raw_results(body: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(body.get("results"), list):
        return body["results"]
    web = body.get("web")
    if isinstance(web, dict) and isinstance(web.get("results"), list):
        return web["results"]
    return []


def _normalize_result(
    raw: dict[str, Any], rank: int, provider_name: str, retrieved_at: str
) -> NormalizedSearchResult | None:
    url = raw.get("url")
    title = raw.get("title")
    if not url or not title:
        return None
    domain = urlparse(url).hostname or ""
    snippet = raw.get("description") or raw.get("snippet") or ""
    published_at = raw.get("page_age") or raw.get("published") or raw.get("age")
    return NormalizedSearchResult(
        result_id=f"{provider_name}:{rank}:{hash(url) & 0xFFFFFFFF:x}",
        title=str(title),
        url=str(url),
        display_domain=domain,
        snippet=str(snippet)[:500],
        published_at=str(published_at) if published_at else None,
        updated_at=None,
        retrieved_at=retrieved_at,
        provider_name=provider_name,
        rank=rank,
        language=raw.get("language"),
    )


WIKIPEDIA_PROVIDER_NAME = "wikipedia"
_WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page"
_WIKIPEDIA_ARTICLE_BASE_URL = "https://en.wikipedia.org/wiki/"
# Wikimedia's API etiquette (https://meta.wikimedia.org/wiki/User-Agent_policy)
# rejects requests with a generic/default User-Agent (e.g. httpx's own
# "python-httpx/x.y.z") with HTTP 403 -- a descriptive, contactable
# User-Agent is required, not optional.
_WIKIPEDIA_USER_AGENT = "BrudAI-TrustedWebSearch/1 (+bounded-search; read-only; no-scraping)"


class WikipediaSearchProvider:
    """The zero-config, key-free built-in default provider (per the
    explicit product decision: ship one real, working provider so
    `trusted_web` can genuinely execute end-to-end with no external
    account/credential needed, rather than leaving the route
    permanently unconfigured). Calls Wikipedia's official, public,
    documented REST search API -- no API key, legitimate documented
    endpoint, not HTML scraping. Narrow coverage is an honest, disclosed
    limitation (strong for stable/encyclopedic topics, weaker for fast-
    moving current-events queries), not a defect. Real paid/general
    providers plug in via `ConfigurableSearchApiProvider` above, on the
    same `WebSearchProvider` contract, once real credentials exist."""

    provider_name = WIKIPEDIA_PROVIDER_NAME

    def __init__(self, transport: SearchTransport = default_search_transport) -> None:
        self._transport = transport

    def capabilities(self) -> list[str]:
        return ["web_search"]

    def health_check(self) -> ProviderHealthStatus:
        if _circuit_is_open(self.provider_name):
            return ProviderHealthStatus(healthy=False, reason="circuit_open_recent_failures")
        return ProviderHealthStatus(healthy=True)

    def search(self, query: str, options: SearchOptions) -> list[NormalizedSearchResult]:
        params = {"q": query, "limit": str(min(options.max_results, 10))}
        headers = {"Accept": "application/json", "User-Agent": _WIKIPEDIA_USER_AGENT}
        response = self._transport(_WIKIPEDIA_SEARCH_URL, headers, params, timeout_seconds=5.0)
        if not response.reachable:
            _record_search_outcome(self.provider_name, success=False)
            raise ProviderUnavailableError(response.error or "unreachable")
        if response.status_code == 429:
            _record_search_outcome(self.provider_name, success=False)
            raise ProviderQuotaExceededError("rate_limited_by_provider")
        if response.status_code >= 400 or response.body is None:
            _record_search_outcome(self.provider_name, success=False)
            raise ProviderUnavailableError(f"http_{response.status_code}")

        _record_search_outcome(self.provider_name, success=True)
        pages = response.body.get("pages")
        if not isinstance(pages, list):
            return []
        retrieved_at = datetime.now(UTC).isoformat()
        normalized: list[NormalizedSearchResult] = []
        for rank, page in enumerate(pages[: options.max_results], start=1):
            key = page.get("key")
            title = page.get("title")
            if not key or not title:
                continue
            normalized.append(
                NormalizedSearchResult(
                    result_id=f"{self.provider_name}:{rank}:{key}",
                    title=str(title),
                    url=_WIKIPEDIA_ARTICLE_BASE_URL + str(key),
                    display_domain="en.wikipedia.org",
                    snippet=str(page.get("description") or page.get("excerpt") or "")[:500],
                    published_at=None,
                    updated_at=None,
                    retrieved_at=retrieved_at,
                    provider_name=self.provider_name,
                    rank=rank,
                    language="en",
                )
            )
        return normalized


def build_configured_provider(
    *,
    provider_name: str,
    base_url: str | None,
    api_key: str | None,
    api_key_header: str,
    timeout_seconds: float,
    transport: SearchTransport = default_search_transport,
) -> WebSearchProvider:
    """Single production wiring point -- `TrustedWebAnswerService` and
    the Admin health/test-search endpoints all construct the provider
    through this function, never by instantiating an adapter class
    directly, so a future second adapter only needs to be wired here.
    `transport` is injectable purely for tests; production callers
    never pass it."""

    if provider_name == WIKIPEDIA_PROVIDER_NAME:
        return WikipediaSearchProvider(transport=transport)

    return ConfigurableSearchApiProvider(
        ProviderConfig(
            provider_name=provider_name,
            base_url=base_url,
            api_key=api_key,
            api_key_header=api_key_header,
            timeout_seconds=timeout_seconds,
        ),
        transport=transport,
    )


__all__ = [
    "WIKIPEDIA_PROVIDER_NAME",
    "ConfigurableSearchApiProvider",
    "ProviderConfig",
    "ProviderQuotaExceededError",
    "ProviderUnavailableError",
    "WikipediaSearchProvider",
    "build_configured_provider",
    "default_search_transport",
    "reset_provider_circuit",
]
