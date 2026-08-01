"""Phase 9 External Data Provider Registry API.

Admin-only, CSRF-protected, under `/api/admin/external-data-providers`.
Structurally separate from inference-provider routing and from the
Source & Rights Registry -- no endpoint here writes to `data_sources`,
`inference_model_assignments`, or any governance/lineage table.
Registering, verifying, or enabling a provider never implies dataset
licence, RAG, training, or commercial approval.

Credentials: every credential response is the Step 4 status-only
contract (`credential_type`, `configured`, `status`, `last_rotated_at`,
`last_tested_at`) -- no endpoint here can return a secret value,
because the underlying service never reads one into a response in the
first place.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.services.external_data_provider_service import (
    ExternalDataProviderCapabilityService,
    ExternalDataProviderConnectionService,
    ExternalDataProviderCredentialService,
    ExternalDataProviderService,
    ExternalDataProviderVerificationService,
)

router = APIRouter(
    prefix="/admin/external-data-providers",
    tags=["external-data-providers"],
    dependencies=[Depends(require_admin)],
)


def provider_service(settings) -> ExternalDataProviderService:
    return ExternalDataProviderService(settings)


def verification_service(settings) -> ExternalDataProviderVerificationService:
    return ExternalDataProviderVerificationService(settings)


def credential_service(settings) -> ExternalDataProviderCredentialService:
    return ExternalDataProviderCredentialService(settings)


def connection_service(settings) -> ExternalDataProviderConnectionService:
    return ExternalDataProviderConnectionService(settings)


def capability_service(settings) -> ExternalDataProviderCapabilityService:
    return ExternalDataProviderCapabilityService(settings)


class ProviderCreateRequest(DomainModel):
    provider_code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    provider_type: str
    description: str = Field(default="", max_length=4000)
    official_website: str | None = Field(default=None, max_length=500)
    catalogue_url: str | None = Field(default=None, max_length=500)
    access_mode: str
    authentication_type: str = "none"
    rate_limit_notes: str = Field(default="", max_length=2000)
    terms_url: str | None = Field(default=None, max_length=500)
    privacy_url: str | None = Field(default=None, max_length=500)
    support_url: str | None = Field(default=None, max_length=500)


class ProviderPatchRequest(DomainModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    official_website: str | None = Field(default=None, max_length=500)
    catalogue_url: str | None = Field(default=None, max_length=500)
    access_mode: str | None = None
    authentication_type: str | None = None
    rate_limit_notes: str | None = Field(default=None, max_length=2000)
    terms_url: str | None = Field(default=None, max_length=500)
    privacy_url: str | None = Field(default=None, max_length=500)
    support_url: str | None = Field(default=None, max_length=500)
    supports_anonymous_read: bool | None = None
    supports_authenticated_read: bool | None = None
    supports_download: bool | None = None
    supports_api_search: bool | None = None
    supports_manual_discovery: bool | None = None
    supports_write: bool | None = None


class DomainCreateRequest(DomainModel):
    domain: str = Field(min_length=1, max_length=300)
    domain_type: str


class DomainVerifyRequest(DomainModel):
    verified: bool
    evidence: str = Field(min_length=1, max_length=2000)


class CapabilityItem(DomainModel):
    capability_type: str
    language_codes: list[str] = Field(default_factory=list)
    dataset_categories: list[str] = Field(default_factory=list)
    connector_type: str | None = None
    enabled: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)


class CapabilitiesSetRequest(DomainModel):
    capabilities: list[CapabilityItem]


class CredentialConfigureRequest(DomainModel):
    credential_type: str
    reference_key: str = Field(min_length=1, max_length=200)


class CredentialRevokeRequest(DomainModel):
    credential_public_id: str


class TrustStatusRequest(DomainModel):
    trust_status: str
    evidence: str = Field(default="", max_length=2000)


class ConnectionTestRequest(DomainModel):
    use_credential: bool = False


@router.get("")
async def list_providers(
    settings: SettingsDependency,
    provider_type: str | None = None,
    lifecycle_status: str | None = None,
    enabled: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = provider_service(settings).list_providers(
        provider_type=provider_type,
        lifecycle_status=lifecycle_status,
        enabled=enabled,
        limit=page_size,
        offset=offset,
    )
    return {"items": items, "page": page, "page_size": page_size}


@router.post("")
async def register_provider(
    payload: ProviderCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return provider_service(settings).register_provider(
        payload.model_dump(), admin.admin.public_id
    )


@router.get("/{public_id}")
async def get_provider(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return provider_service(settings).get_provider(public_id)


@router.patch("/{public_id}")
async def update_provider(
    public_id: str,
    payload: ProviderPatchRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return provider_service(settings).update_provider(
        public_id, payload.model_dump(exclude_unset=True), admin.admin.public_id
    )


@router.post("/{public_id}/verify")
async def verify_provider(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return verification_service(settings).evaluate_provider(public_id, admin.admin.public_id)


@router.post("/{public_id}/trust-status")
async def set_trust_status(
    public_id: str,
    payload: TrustStatusRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return verification_service(settings).set_trust_status(
        public_id, payload.trust_status, evidence=payload.evidence, admin_id=admin.admin.public_id
    )


@router.post("/{public_id}/test-connection")
async def test_connection(
    public_id: str,
    payload: ConnectionTestRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return connection_service(settings).test_connection(
        public_id, admin_id=admin.admin.public_id, use_credential=payload.use_credential
    )


@router.get("/{public_id}/connection-tests")
async def list_connection_tests(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": connection_service(settings).list_connection_tests(public_id)}


@router.post("/{public_id}/enable")
async def enable_provider(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return provider_service(settings).transition_lifecycle(
        public_id, "enable", admin.admin.public_id
    )


@router.post("/{public_id}/disable")
async def disable_provider(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return provider_service(settings).transition_lifecycle(
        public_id, "disable", admin.admin.public_id
    )


@router.post("/{public_id}/restrict")
async def restrict_provider(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return provider_service(settings).transition_lifecycle(
        public_id, "restrict", admin.admin.public_id
    )


@router.post("/{public_id}/block")
async def block_provider(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return provider_service(settings).transition_lifecycle(
        public_id, "block", admin.admin.public_id
    )


@router.post("/{public_id}/archive")
async def archive_provider(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return provider_service(settings).transition_lifecycle(
        public_id, "archive", admin.admin.public_id
    )


@router.get("/{public_id}/domains")
async def list_domains(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": provider_service(settings).list_domains(public_id)}


@router.post("/{public_id}/domains")
async def add_domain(
    public_id: str,
    payload: DomainCreateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return provider_service(settings).add_domain(
        public_id, payload.model_dump(), admin.admin.public_id
    )


@router.post("/{public_id}/domains/{domain_public_id}/verify")
async def verify_domain(
    public_id: str,
    domain_public_id: str,
    payload: DomainVerifyRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    del public_id
    return verification_service(settings).verify_domain(
        domain_public_id,
        verified=payload.verified,
        evidence=payload.evidence,
        admin_id=admin.admin.public_id,
    )


@router.get("/{public_id}/capabilities")
async def list_capabilities(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": capability_service(settings).list_capabilities(public_id)}


@router.put("/{public_id}/capabilities")
async def set_capabilities(
    public_id: str,
    payload: CapabilitiesSetRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    capabilities = [item.model_dump() for item in payload.capabilities]
    return {
        "items": capability_service(settings).set_capabilities(
            public_id, capabilities, admin.admin.public_id
        )
    }


@router.get("/{public_id}/credential-status")
async def credential_status(public_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": credential_service(settings).get_credential_status(public_id)}


@router.post("/{public_id}/credentials")
async def configure_credential(
    public_id: str,
    payload: CredentialConfigureRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return credential_service(settings).configure_credential_reference(
        public_id,
        credential_type=payload.credential_type,
        reference_key=payload.reference_key,
        admin_id=admin.admin.public_id,
    )


@router.post("/{public_id}/credentials/revoke")
async def revoke_credential(
    public_id: str,
    payload: CredentialRevokeRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return credential_service(settings).revoke_credential(
        payload.credential_public_id, public_id, admin.admin.public_id
    )


@router.get("/{public_id}/history")
async def provider_history(
    public_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    service = provider_service(settings)
    return {"items": service.repository.list_events(public_id, limit=limit)}
