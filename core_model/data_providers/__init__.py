"""Phase 9 external data provider registry — pure enums and policy.

Describes *where Brud AI could potentially look* for external
training/RAG source material (an organization, website, or API) --
deliberately distinct from the existing Source & Rights Registry
(``core_model.data_governance``), which describes rights for one
specific piece of content already inside Brud AI. Registering a
provider here never implies anything about dataset licensing, RAG use,
training use, or commercial use for any content that might later be
discovered through it (see
``docs/data_providers/phase9_external_data_provider_registry_plan.md``
section 1.2).

Also deliberately distinct from AI *inference* provider/model routing
(``core_model.inference_runtime`` / Phase 15's
``inference_model_assignments``) -- that answers "which trained model
generates a chat reply", this answers "which external data source
could be connected to". No table, service, or API name is shared
between the two.

Every enum below is the single source of truth shared by the backend
services, matching the corresponding CHECK constraints in
``backend/database/schema.py``'s Phase 9 schema block.
"""

from __future__ import annotations

PROVIDER_TYPES = (
    "dataset_catalogue",
    "repository_host",
    "government_portal",
    "research_institution",
    "university_library",
    "public_api",
    "file_repository",
    "custom_api",
    "manual_source",
)

ACCESS_MODES = ("public", "gated", "private", "mixed", "manual")

AUTHENTICATION_TYPES = (
    "none",
    "api_key",
    "bearer_token",
    "oauth",
    "username_password",
    "custom_header",
    "manual_login",
)

TRUST_STATUSES = (
    "unverified",
    "domain_verified",
    "organization_verified",
    "government_verified",
    "research_verified",
    "community_reviewed",
    "restricted",
    "blocked",
)

# A trust status an admin may never assign directly without evidence --
# only `ExternalDataProviderVerificationService` may set these, and only
# when it actually produced supporting evidence (Step 7).
EVIDENCE_REQUIRED_TRUST_STATUSES = (
    "domain_verified",
    "organization_verified",
    "government_verified",
    "research_verified",
)

LIFECYCLE_STATUSES = (
    "draft",
    "connection_tested",
    "needs_review",
    "approved",
    "enabled",
    "disabled",
    "restricted",
    "blocked",
    "archived",
)

# A provider in any of these lifecycle states must never be usable for
# discovery, regardless of its `enabled` flag -- checked structurally
# by `ExternalDataProviderService`, not left to callers to remember.
INACTIVE_LIFECYCLE_STATUSES = ("draft", "disabled", "restricted", "blocked", "archived")

DOMAIN_TYPES = ("official", "api", "download", "documentation", "authentication", "mirror")

DOMAIN_VERIFICATION_STATUSES = ("unverified", "verified", "failed")

CAPABILITY_TYPES = (
    "search_datasets",
    "read_metadata",
    "read_dataset_card",
    "read_licence",
    "list_files",
    "download_sample",
    "download_full",
    "upload",
    "write_metadata",
)

# Phase 9 never executes these regardless of what a capability row
# claims to support -- enforced in the connector layer (Step 3) and
# re-asserted here as the canonical list so any future caller has one
# place to check "is this capability allowed to run yet".
CAPABILITY_TYPES_DISABLED_IN_PHASE_9 = (
    "download_sample",
    "download_full",
    "upload",
    "write_metadata",
)

CREDENTIAL_TYPES = AUTHENTICATION_TYPES[1:]  # every auth type except "none"

CREDENTIAL_STATUSES = ("not_configured", "configured", "test_succeeded", "test_failed", "revoked")

CONNECTION_TEST_RESULTS = (
    "success",
    "partial",
    "failed",
    "authentication_required",
    "rate_limited",
    "unsupported",
)

PROVIDER_EVENT_TYPES = (
    "provider_registered",
    "provider_updated",
    "domain_added",
    "domain_verified",
    "capability_updated",
    "credential_configured",
    "credential_revoked",
    "connection_tested",
    "verification_evaluated",
    "provider_enabled",
    "provider_disabled",
    "provider_restricted",
    "provider_blocked",
    "provider_archived",
)


def is_usable_for_discovery(*, lifecycle_status: str, enabled: bool) -> bool:
    """A provider may be used for read-only discovery only when it is
    both explicitly enabled and outside every inactive lifecycle state.
    Pure and total -- an unknown lifecycle_status is treated as unusable
    rather than raising, since callers should never construct one
    outside the CHECK-constrained values above."""

    if lifecycle_status not in LIFECYCLE_STATUSES:
        return False
    return enabled and lifecycle_status not in INACTIVE_LIFECYCLE_STATUSES
