"""Phase 20 Step 4 -- provider-neutral Web search contract.

Every concrete provider adapter (one shipped in this phase; more may
be added later behind the same shape) implements this. Provider-
specific raw payloads must never escape the adapter -- callers only
ever see `NormalizedSearchResult`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NormalizedSearchResult:
    result_id: str
    title: str
    url: str
    display_domain: str
    snippet: str
    published_at: str | None
    updated_at: str | None
    retrieved_at: str
    provider_name: str
    rank: int
    language: str | None = None


@dataclass(frozen=True)
class SearchOptions:
    max_results: int = 5
    language: str | None = None
    freshness_hint: str | None = None


@dataclass(frozen=True)
class ProviderHealthStatus:
    healthy: bool
    reason: str | None = None
    latency_ms: int | None = None


class WebSearchProvider(Protocol):
    provider_name: str

    def search(self, query: str, options: SearchOptions) -> list[NormalizedSearchResult]: ...

    def health_check(self) -> ProviderHealthStatus: ...

    def capabilities(self) -> list[str]: ...


__all__ = [
    "NormalizedSearchResult",
    "ProviderHealthStatus",
    "SearchOptions",
    "WebSearchProvider",
]
