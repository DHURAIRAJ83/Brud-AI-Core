"""Phase 61 - P7: Production Safety Dashboard Contract.

Provides a READ-ONLY data contract for operational safety monitoring dashboards.

CRITICAL INVARIANTS:
- Strictly READ-ONLY contract. Zero mutation methods provided.
- Accurately reflects mandatory governance invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProductionHealthView:
    release_id: str
    model_hash: str
    health_status: str
    request_count: int
    error_rate: float
    timeout_rate: float
    latency_p50: float
    latency_p95: float
    latency_p99: float


@dataclass(frozen=True)
class SafetyStatusView:
    safety_status: str
    safety_violation_count: int
    hallucination_indicator_count: int
    data_leakage_indicators: int
    prompt_injection_indicators: int


@dataclass(frozen=True)
class IncidentStatusView:
    active_incidents: int
    critical_incidents: int
    traffic_frozen: bool
    rollback_required: bool
    rollback_status: str


@dataclass(frozen=True)
class GovernanceInvariantsView:
    production_promotion: str = "BLOCKED"
    public_chat_eligible: bool = False
    candidate_traffic_share: float = 0.0
    training_execution_authorized: bool = False
    optimizer_stepping: bool = False
    tokenizer_mutation: bool = False


@dataclass(frozen=True)
class ProductionSafetyDashboardContract:
    """Read-only production safety dashboard view."""
    health: ProductionHealthView
    safety: SafetyStatusView
    incidents: IncidentStatusView
    governance: GovernanceInvariantsView
    dashboard_timestamp: str
