"""Phase 9 external data provider connectors -- bounded reachability
and static capability/metadata checks only. No search, no download, no
write. See base.py for the contract and builtin.py for the seeded
providers' connectors."""

from backend.services.external_data_connectors.base import (
    DEFAULT_TIMEOUT_SECONDS,
    ConnectionTestResult,
    ConnectorConfig,
    ConnectorSearchError,
    ExternalDataProviderConnector,
    HttpResponse,
    HttpTransport,
    default_http_transport,
)
from backend.services.external_data_connectors.builtin import CONNECTOR_REGISTRY, get_connector

__all__ = [
    "CONNECTOR_REGISTRY",
    "DEFAULT_TIMEOUT_SECONDS",
    "ConnectionTestResult",
    "ConnectorConfig",
    "ConnectorSearchError",
    "ExternalDataProviderConnector",
    "HttpResponse",
    "HttpTransport",
    "default_http_transport",
    "get_connector",
]
