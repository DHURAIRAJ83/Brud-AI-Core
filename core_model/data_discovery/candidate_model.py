"""Pure data contracts every connector's ``search_datasets``/
``get_dataset_metadata`` must honor (Step 3). A field a connector
cannot determine is left ``None``/empty -- never invented."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetSearchRequest:
    query: str
    modality: str = "text"
    languages: tuple[str, ...] = ()
    tasks: tuple[str, ...] = ()
    intended_uses: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    limit: int = 10
    cursor: str | None = None


@dataclass(frozen=True)
class NormalizedDatasetMetadata:
    provider_dataset_id: str
    name: str
    description: str = ""
    authors: tuple[str, ...] = ()
    organization: str | None = None
    languages: tuple[str, ...] = ()
    modality: str | None = None
    tasks: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    dataset_card_url: str | None = None
    repository_url: str | None = None
    homepage_url: str | None = None
    licence_declared: str | None = None
    licence_url: str | None = None
    record_count: int | None = None
    download_size_bytes: int | None = None
    file_formats: tuple[str, ...] = ()
    last_modified_at: str | None = None
    version: str | None = None
    revision: str | None = None
    gated: bool = False
    private: bool = False
    requires_authentication: bool = False
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DatasetSearchResult:
    items: tuple[NormalizedDatasetMetadata, ...] = ()
    next_cursor: str | None = None
    total_estimated: int | None = None
