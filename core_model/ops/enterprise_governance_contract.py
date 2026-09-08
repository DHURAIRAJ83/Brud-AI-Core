"""Phase 61 - P9: Enterprise Governance Dashboard Contract.

Provides a READ-ONLY data contract for enterprise compliance, secret governance, and policy monitoring.

CRITICAL INVARIANTS:
- Strictly READ-ONLY contract. Zero mutation methods provided.
- Never exposes raw HMAC secrets, credentials, or private keys. Only exposes key IDs, status, and fingerprints.
- Accurately reflects mandatory governance invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ComplianceStatusView:
    compliance_status: str
    evidence_packages_available: int
    missing_evidence_count: int


@dataclass(frozen=True)
class SecretGovernanceView:
    active_keys_count: int
    revoked_keys_count: int
    rotation_age_days: float


@dataclass(frozen=True)
class RBACIsolationView:
    rbac_integrity_passed: bool
    tenant_isolation_passed: bool
    policy_drift_status: str


@dataclass(frozen=True)
class GovernanceInvariantsView:
    production_promotion: str = "BLOCKED"
    public_chat_eligible: bool = False
    candidate_traffic_share: float = 0.0
    training_execution_authorized: bool = False
    optimizer_stepping: bool = False
    tokenizer_mutation: bool = False
    recovery_executed: bool = False


@dataclass(frozen=True)
class EnterpriseGovernanceDashboardContract:
    """Read-only enterprise governance dashboard contract."""
    compliance: ComplianceStatusView
    secrets: SecretGovernanceView
    rbac: RBACIsolationView
    invariants: GovernanceInvariantsView
    contract_timestamp: str
