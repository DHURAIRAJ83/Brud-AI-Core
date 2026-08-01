"""Phase 9 External Data Provider Registry services.

Five small, focused services over `ExternalDataProviderRepository`:
`ExternalDataProviderService` (CRUD + lifecycle transitions),
`ExternalDataProviderVerificationService` (evidence-based trust
evaluation), `ExternalDataProviderCredentialService` (secret-safe
credential references), `ExternalDataProviderConnectionService`
(bounded, read-only connection tests via the Phase 9 connector
contract), `ExternalDataProviderCapabilityService` (capability
toggles, structurally blocked from ever enabling download/write in
this phase).

Every mutation is transactional (via the repository) and audited both
to this registry's own `external_data_provider_events` table (a
registry-specific history) and to the existing global `audit_logs`
(`AuditLogRepository`) -- never a competing audit system.

Registering, verifying, enabling, or testing a provider never writes
to `data_sources`, any governance table, or any lineage table --
provider approval structurally cannot imply dataset, RAG, training, or
commercial approval (see plan.md section 1.2/7).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.external_data_providers import (
    ExternalDataProviderRepository,
)
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.external_data_connectors import (
    CONNECTOR_REGISTRY,
    ConnectorConfig,
    HttpTransport,
    default_http_transport,
    get_connector,
)
from core_model.data_providers import (
    ACCESS_MODES,
    AUTHENTICATION_TYPES,
    CAPABILITY_TYPES,
    CAPABILITY_TYPES_DISABLED_IN_PHASE_9,
    CREDENTIAL_TYPES,
    DOMAIN_TYPES,
    EVIDENCE_REQUIRED_TRUST_STATUSES,
    PROVIDER_TYPES,
)

logger = logging.getLogger(__name__)

# Fields an admin may change via a plain PATCH -- lifecycle_status,
# trust_status, and enabled are deliberately excluded here and only
# ever change through a dedicated, audited transition method, so every
# state change has its own event type rather than being buried in a
# generic "provider_updated".
_PATCHABLE_FIELDS = (
    "name",
    "description",
    "official_website",
    "catalogue_url",
    "access_mode",
    "authentication_type",
    "rate_limit_notes",
    "terms_url",
    "privacy_url",
    "support_url",
    "supports_anonymous_read",
    "supports_authenticated_read",
    "supports_download",
    "supports_api_search",
    "supports_manual_discovery",
    "supports_write",
)

_LIFECYCLE_TRANSITIONS = {
    "enable": ("enabled", 1, "provider_enabled"),
    "disable": ("disabled", 0, "provider_disabled"),
    "restrict": ("restricted", 0, "provider_restricted"),
    "block": ("blocked", 0, "provider_blocked"),
    "archive": ("archived", 0, "provider_archived"),
}
# Once archived, no further lifecycle transition is allowed -- archival
# is terminal, matching Flow D's "historical metadata remains readable"
# without also remaining mutable.
_TERMINAL_LIFECYCLE_STATUSES = ("archived",)


class ExternalDataProviderError(BrudError):
    status_code = 422
    code = "external_data_provider_rejected"


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    event_type: str,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=event_type,
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="external_data_provider",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("external_data_provider_audit_write_failed", extra={"action": action})


class ExternalDataProviderService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ExternalDataProviderRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def register_provider(self, payload: dict[str, Any], admin_id: str) -> dict[str, Any]:
        if payload.get("provider_type") not in PROVIDER_TYPES:
            raise ExternalDataProviderError(
                f"unsupported provider_type: {payload.get('provider_type')}"
            )
        if payload.get("access_mode") not in ACCESS_MODES:
            raise ExternalDataProviderError(
                f"unsupported access_mode: {payload.get('access_mode')}"
            )
        auth_type = payload.get("authentication_type", "none")
        if auth_type not in AUTHENTICATION_TYPES:
            raise ExternalDataProviderError(f"unsupported authentication_type: {auth_type}")
        if self.repository.get_provider_by_code(payload["provider_code"]) is not None:
            raise ExternalDataProviderError(
                f"provider_code already registered: {payload['provider_code']}"
            )
        provider = self.repository.create_provider(
            {**payload, "created_by_admin_public_id": admin_id}
        )
        self.repository.record_event(
            provider["public_id"],
            {
                "event_type": "provider_registered",
                "summary": f"Registered by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_registered",
            action="register",
            actor_reference=admin_id,
            resource_public_id=provider["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"provider_code": provider["provider_code"]},
        )
        return provider

    def get_provider(self, public_id: str) -> dict[str, Any]:
        return self.repository.get_provider(public_id)

    def list_providers(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_providers(**filters)

    def update_provider(
        self, public_id: str, patch: dict[str, Any], admin_id: str
    ) -> dict[str, Any]:
        fields = {key: value for key, value in patch.items() if key in _PATCHABLE_FIELDS}
        if "access_mode" in fields and fields["access_mode"] not in ACCESS_MODES:
            raise ExternalDataProviderError(
                f"unsupported access_mode: {fields['access_mode']}"
            )
        if (
            "authentication_type" in fields
            and fields["authentication_type"] not in AUTHENTICATION_TYPES
        ):
            raise ExternalDataProviderError(
                f"unsupported authentication_type: {fields['authentication_type']}"
            )
        updated = self.repository.update_provider(public_id, fields)
        self.repository.record_event(
            public_id,
            {
                "event_type": "provider_updated",
                "summary": f"Updated by {admin_id}: {', '.join(sorted(fields))}",
                "metadata": {"fields": sorted(fields)},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_updated",
            action="update",
            actor_reference=admin_id,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"fields": sorted(fields)},
        )
        return updated

    def transition_lifecycle(self, public_id: str, action: str, admin_id: str) -> dict[str, Any]:
        if action not in _LIFECYCLE_TRANSITIONS:
            raise ExternalDataProviderError(f"unsupported lifecycle action: {action}")
        provider = self.repository.get_provider(public_id)
        if provider["lifecycle_status"] in _TERMINAL_LIFECYCLE_STATUSES:
            raise ExternalDataProviderError(
                f"provider is archived and cannot transition (requested={action})"
            )
        lifecycle_status, enabled, event_type = _LIFECYCLE_TRANSITIONS[action]
        fields: dict[str, Any] = {"lifecycle_status": lifecycle_status, "enabled": enabled}
        if action == "block":
            fields["trust_status"] = "blocked"
        updated = self.repository.update_provider(public_id, fields)
        self.repository.record_event(
            public_id,
            {
                "event_type": event_type,
                "summary": f"{action} by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type=f"external_data_provider_{action}",
            action=action,
            actor_reference=admin_id,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return updated

    # -- domains ----------------------------------------------------------

    def add_domain(self, public_id: str, values: dict[str, Any], admin_id: str) -> dict[str, Any]:
        if values.get("domain_type") not in DOMAIN_TYPES:
            raise ExternalDataProviderError(f"unsupported domain_type: {values.get('domain_type')}")
        domain = self.repository.add_domain(public_id, values)
        self.repository.record_event(
            public_id,
            {
                "event_type": "domain_added",
                "summary": f"Domain {domain['domain']} ({domain['domain_type']}) "
                f"added by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_domain_added",
            action="add_domain",
            actor_reference=admin_id,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"domain": domain["domain"], "domain_type": domain["domain_type"]},
        )
        return domain

    def list_domains(self, public_id: str) -> list[dict[str, Any]]:
        return self.repository.list_domains(public_id)


class ExternalDataProviderVerificationService:
    """Evidence-based trust evaluation (Step 7). Never claims a
    provider is officially verified without evidence -- the only
    automatic trust upgrade this service performs is `unverified ->
    domain_verified`, and only when at least one domain has already
    been explicitly, separately marked `verified` (via `verify_domain`,
    itself an audited admin action). Any higher trust tier
    (`organization_verified`, `government_verified`, `research_verified`,
    `community_reviewed`) requires a human admin to set it directly
    with a non-empty evidence string -- this service never assigns one
    itself."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ExternalDataProviderRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def verify_domain(
        self, domain_public_id: str, *, verified: bool, evidence: str, admin_id: str
    ) -> dict[str, Any]:
        if not evidence.strip():
            raise ExternalDataProviderError(
                "domain verification requires a non-empty evidence note"
            )
        domain = self.repository.verify_domain(
            domain_public_id,
            verification_status="verified" if verified else "failed",
            evidence=evidence,
        )
        self.repository.record_event(
            domain["provider_public_id"],
            {
                "event_type": "domain_verified",
                "summary": f"Domain {domain['domain']} marked {domain['verification_status']} "
                f"by {admin_id}",
                "metadata": {"evidence": evidence},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_domain_verified",
            action="verify_domain",
            actor_reference=admin_id,
            resource_public_id=domain["provider_public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"domain": domain["domain"], "status": domain["verification_status"]},
        )
        return domain

    def evaluate_provider(self, public_id: str, admin_id: str) -> dict[str, Any]:
        provider = self.repository.get_provider(public_id)
        domains = self.repository.list_domains(public_id)
        warnings: list[str] = []
        blocking_reasons: list[str] = []
        evidence: dict[str, Any] = {}

        official_domains = [d for d in domains if d["domain_type"] == "official"]
        if not official_domains:
            blocking_reasons.append("no official domain registered")
        verified_official = [d for d in official_domains if d["verification_status"] == "verified"]
        if official_domains and not verified_official:
            blocking_reasons.append("no official domain has been independently verified")
        evidence["verified_domains"] = [d["domain"] for d in verified_official]

        if not provider["official_website"]:
            warnings.append("no official website recorded")
        elif not provider["official_website"].startswith("https://"):
            warnings.append("official website is not HTTPS")

        if not provider["terms_url"]:
            warnings.append("no terms_url recorded")

        capabilities = self.repository.list_capabilities(public_id)
        if not capabilities:
            warnings.append("no capabilities declared yet")

        verified = bool(verified_official) and not blocking_reasons
        upgraded = False
        if verified and provider["trust_status"] == "unverified":
            self.repository.update_provider(public_id, {"trust_status": "domain_verified"})
            upgraded = True

        report = {
            "verified": verified,
            "warnings": warnings,
            "blocking_reasons": blocking_reasons,
            "evidence": evidence,
            "trust_status_upgraded_to": "domain_verified" if upgraded else None,
        }
        self.repository.record_event(
            public_id,
            {
                "event_type": "verification_evaluated",
                "summary": f"Verification evaluated by {admin_id}: verified={verified}",
                "metadata": report,
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_verification_evaluated",
            action="verify",
            actor_reference=admin_id,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS if verified else AuditOutcome.WARNING,
            metadata=report,
        )
        return {**report, "last_checked_at": self.repository.get_provider(public_id)["updated_at"]}

    def set_trust_status(
        self, public_id: str, trust_status: str, *, evidence: str, admin_id: str
    ) -> dict[str, Any]:
        """A human admin's direct judgment call for a trust tier this
        service cannot derive automatically -- always requires a
        non-empty evidence note, always audited."""

        if trust_status in EVIDENCE_REQUIRED_TRUST_STATUSES and not evidence.strip():
            raise ExternalDataProviderError(
                f"trust_status={trust_status} requires a non-empty evidence note"
            )
        updated = self.repository.update_provider(public_id, {"trust_status": trust_status})
        self.repository.record_event(
            public_id,
            {
                "event_type": "verification_evaluated",
                "summary": f"trust_status manually set to {trust_status} by {admin_id}",
                "metadata": {"evidence": evidence, "trust_status": trust_status},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_trust_status_set",
            action="set_trust_status",
            actor_reference=admin_id,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"trust_status": trust_status, "evidence": evidence},
        )
        return updated


def _public_credential_status(credential: dict[str, Any]) -> dict[str, Any]:
    """Step 4's exact contract: configured/credential_type/
    last_rotated_at/last_tested_at/status only -- never `reference_key`,
    `public_id`-of-credential internals beyond what's listed, and never
    a secret value (there is no secret value anywhere in this row)."""

    configured = bool(os.environ.get(credential["reference_key"], "").strip())
    return {
        "credential_type": credential["credential_type"],
        "configured": configured,
        "status": credential["status"],
        "last_rotated_at": credential["last_rotated_at"],
        "last_tested_at": credential["last_tested_at"],
    }


class ExternalDataProviderCredentialService:
    """Never stores, logs, or returns a secret value -- only a
    `reference_key` (an environment variable name) and derived status.
    See plan.md section 5 for the full, honestly-documented limitation
    of this reference-only model."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ExternalDataProviderRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def configure_credential_reference(
        self, provider_public_id: str, *, credential_type: str, reference_key: str, admin_id: str
    ) -> dict[str, Any]:
        if credential_type not in CREDENTIAL_TYPES:
            raise ExternalDataProviderError(f"unsupported credential_type: {credential_type}")
        if not reference_key.strip():
            raise ExternalDataProviderError("reference_key must not be empty")
        credential = self.repository.add_or_replace_credential(
            provider_public_id,
            {
                "credential_type": credential_type,
                "reference_key": reference_key,
                "created_by_admin_public_id": admin_id,
            },
        )
        self.repository.record_event(
            provider_public_id,
            {
                "event_type": "credential_configured",
                "summary": f"{credential_type} credential reference configured by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_credential_configured",
            action="configure_credential",
            actor_reference=admin_id,
            resource_public_id=provider_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"credential_type": credential_type},
        )
        return _public_credential_status(credential)

    def revoke_credential(
        self, credential_public_id: str, provider_public_id: str, admin_id: str
    ) -> dict[str, Any]:
        credential = self.repository.revoke_credential(credential_public_id)
        self.repository.record_event(
            provider_public_id,
            {
                "event_type": "credential_revoked",
                "summary": f"{credential['credential_type']} credential revoked by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_credential_revoked",
            action="revoke_credential",
            actor_reference=admin_id,
            resource_public_id=provider_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"credential_type": credential["credential_type"]},
        )
        return _public_credential_status(credential)

    def get_credential_status(self, provider_public_id: str) -> list[dict[str, Any]]:
        credentials = self.repository.list_credentials(provider_public_id)
        return [_public_credential_status(credential) for credential in credentials]


def resolve_active_credential(
    repository: ExternalDataProviderRepository, provider_public_id: str
) -> tuple[str | None, str | None]:
    """Resolves the first non-revoked credential's *reference_key* to
    its live environment-variable value -- never a cached/stored
    secret. Returns `(credential_value, credential_type)`, both `None`
    when no active credential is configured. Shared by every service
    that needs to build a `ConnectorConfig` (connection tests, Phase 10
    dataset search) so credential resolution stays in exactly one
    place."""

    credentials = repository.list_credentials(provider_public_id)
    active = next((c for c in credentials if c["status"] != "revoked"), None)
    if active is None:
        return None, None
    return os.environ.get(active["reference_key"]) or None, active["credential_type"]


class ExternalDataProviderConnectionService:
    """Bounded, read-only connection tests only -- never search,
    download, or write. `transport` defaults to the one real-network
    implementation in this codebase (`default_http_transport`); tests
    always inject a mock instead (see
    `tests/backend/test_external_data_connectors.py`)."""

    def __init__(
        self, settings: Settings, *, transport: HttpTransport = default_http_transport
    ) -> None:
        self.settings = settings
        self.repository = ExternalDataProviderRepository(settings.resolved_database_path)
        self.transport = transport
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def test_connection(
        self, provider_public_id: str, *, admin_id: str, use_credential: bool = False
    ) -> dict[str, Any]:
        provider = self.repository.get_provider(provider_public_id)
        domains = self.repository.list_domains(provider_public_id)
        domain_map = {d["domain_type"]: d["domain"] for d in domains}

        connector_type = (
            provider["provider_code"]
            if provider["provider_code"] in CONNECTOR_REGISTRY
            else "generic_public_api"
        )
        connector = get_connector(connector_type)

        credential_value: str | None = None
        credential_type: str | None = None
        if use_credential:
            credential_value, credential_type = resolve_active_credential(
                self.repository, provider_public_id
            )

        config = ConnectorConfig(
            provider_code=provider["provider_code"],
            domains=domain_map,
            credential_value=credential_value,
            credential_type=credential_type,
        )
        outcome = connector.test_connection(config, self.transport)

        recorded = self.repository.record_connection_test(
            provider_public_id,
            {
                "result": outcome.result,
                "capability_type": outcome.capability_type,
                "latency_ms": outcome.latency_ms,
                "evidence": outcome.evidence,
                "error_code": outcome.error_code,
                "tested_by_admin_public_id": admin_id,
            },
        )

        if outcome.result in ("success", "partial") and provider["lifecycle_status"] == "draft":
            self.repository.update_provider(
                provider_public_id, {"lifecycle_status": "connection_tested"}
            )

        if use_credential and credential_type:
            provider_credentials = self.repository.list_credentials(provider_public_id)
            active_credential = next(
                (c for c in provider_credentials if c["credential_type"] == credential_type),
                None,
            )
            if active_credential:
                self.repository.set_credential_status(
                    active_credential["public_id"],
                    status="test_succeeded" if outcome.result == "success" else "test_failed",
                    last_tested_at=True,
                )

        self.repository.record_event(
            provider_public_id,
            {
                "event_type": "connection_tested",
                "summary": f"Connection test by {admin_id}: {outcome.result}",
                "metadata": {"result": outcome.result},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_connection_tested",
            action="test_connection",
            actor_reference=admin_id,
            resource_public_id=provider_public_id,
            outcome=AuditOutcome.SUCCESS if outcome.result == "success" else AuditOutcome.WARNING,
            metadata={"result": outcome.result},
        )
        return recorded

    def list_connection_tests(
        self, provider_public_id: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        return self.repository.list_connection_tests(provider_public_id, limit=limit)


class ExternalDataProviderCapabilityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ExternalDataProviderRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def set_capabilities(
        self, provider_public_id: str, capabilities: list[dict[str, Any]], admin_id: str
    ) -> list[dict[str, Any]]:
        results = []
        for values in capabilities:
            if values.get("capability_type") not in CAPABILITY_TYPES:
                raise ExternalDataProviderError(
                    f"unsupported capability_type: {values.get('capability_type')}"
                )
            safe_values = dict(values)
            # Structurally impossible to enable a download/write capability in
            # Phase 9, regardless of what was requested -- see rule "do not
            # enable download actions in Phase 9 execution logic".
            if safe_values.get("capability_type") in CAPABILITY_TYPES_DISABLED_IN_PHASE_9:
                safe_values["enabled"] = False
            results.append(self.repository.upsert_capability(provider_public_id, safe_values))
        self.repository.record_event(
            provider_public_id,
            {
                "event_type": "capability_updated",
                "summary": f"Capabilities updated by {admin_id}",
                "metadata": {"capability_types": [c["capability_type"] for c in results]},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_data_provider_capabilities_updated",
            action="set_capabilities",
            actor_reference=admin_id,
            resource_public_id=provider_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"capability_types": [c["capability_type"] for c in results]},
        )
        return results

    def list_capabilities(self, provider_public_id: str) -> list[dict[str, Any]]:
        return self.repository.list_capabilities(provider_public_id)
