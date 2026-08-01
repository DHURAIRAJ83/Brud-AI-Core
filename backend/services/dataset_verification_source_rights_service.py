"""Phase 11 Step 23/24: Source & Rights Registry and Governance
integration.

The real Source & Rights Registry Phase 2 built is `data_sources`/
`source_rights` (served at `/api/admin/data-sources`) -- distinct from
the older, simpler `dataset_sources` table the pre-existing
`dataset_source_update` Admin Assistant action targets. This module
never writes to `data_sources`/`source_rights` directly and never
duplicates the registry -- a finalized verification case may only
*draft* a proposal through the Admin Assistant's own propose ->
preview -> review -> execute pipeline, using the new
`link_dataset_verification_rights` action registered for exactly this
purpose, which an Admin must separately review and execute through
that same governed pipeline before anything is written. Governance
eligibility is a set of 4 read-only, derived boolean fields already
embedded in the finalized report by
`ExternalDatasetVerificationReportService._build_report()` -- this
module never writes to any governance table and never itself triggers
anything downstream.
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories.data_sources import DataSourceRepository, public_row
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.admin_assistant_service import AdminAssistantService

_MAX_SOURCES_SCANNED = 200

# Phase 11's own 9-value licence_status vocabulary collapsed onto the
# Source & Rights Registry's 10-value `RightsStatus` (Phase 2) -- never
# the reverse (Phase 11's own richer, evidence-backed status is never
# discarded, only summarized for this one linking proposal).
_RIGHTS_STATUS_MAP = {
    "verified": "licensed",
    "declared_only": "unknown",
    "unknown": "unknown",
    "missing": "unknown",
    "custom_needs_review": "pending_review",
    "conflicting": "pending_review",
    "restricted": "restricted",
    "withdrawn": "expired",
}

# Requirement-flag dimensions (Step 8's 9 "does this apply" dimensions,
# see core_model.data_verification's own module docstring): "does the
# requirement apply" is affirmed by either an automated
# `likely_restricted` finding or an explicit Admin `approved`/
# `approved_with_conditions` acknowledgment -- never fabricated True
# when the dimension was never assessed at all.
_REQUIREMENT_AFFIRMED_STATUSES = ("likely_restricted", "approved", "approved_with_conditions")
# "Use" dimensions only ever become True from an explicit Admin
# approval -- never from an automated `likely_allowed` alone, matching
# `governance_eligibility`'s own, identically conservative rule.
_ADMIN_APPROVED_STATUSES = ("approved", "approved_with_conditions")

_USE_PERMISSION_FIELD_MAP = {
    "rag_use": "rag_use_allowed",
    "training_use": "training_use_allowed",
    "evaluation_use": "evaluation_use_allowed",
    "commercial_use": "commercial_use_allowed",
    "redistribution": "redistribution_allowed",
    "modification": "modification_allowed",
}
_REQUIREMENT_FLAG_FIELD_MAP = {
    "attribution_required": "attribution_required",
    "share_alike_required": "share_alike_required",
}


class DatasetVerificationSourceRightsError(BrudError):
    status_code = 422
    code = "dataset_verification_source_rights_rejected"


class ExternalDatasetSourceRightsIntegrationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self.discovery_repository = ExternalDatasetDiscoveryRepository(
            settings.resolved_database_path
        )
        self.data_source_repository = DataSourceRepository(settings.resolved_database_path)
        self.assistant_service = AdminAssistantService(settings)

    def find_existing_source(self, case_public_id: str) -> dict[str, Any] | None:
        """Read-only lookup for a `data_sources` row that plausibly
        already represents this candidate -- exact `source_url` match
        against the candidate's own homepage/repository URL, or an
        exact `organization_name` match. Never a fuzzy match, so this
        can never silently propose linking to the wrong source."""

        case = self.repository.get_case(case_public_id)
        candidate = self.discovery_repository.get_candidate(case["candidate_public_id"])
        candidate_urls = {
            url for url in (candidate.get("homepage_url"), candidate.get("repository_url")) if url
        }
        organization = candidate.get("organization")

        with self.data_source_repository.transaction() as connection:
            rows, _total = self.data_source_repository.list_sources(
                connection, limit=_MAX_SOURCES_SCANNED, offset=0
            )
            for row in rows:
                data = public_row(row)
                if data.get("source_url") and data["source_url"] in candidate_urls:
                    return data
                if organization and data.get("organization_name") == organization:
                    return data
        return None

    def draft_source_update_proposal(
        self, case_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        """The one Phase 11 action that touches the Source & Rights
        Registry at all -- and only ever by drafting a proposal through
        the `link_dataset_verification_rights` Admin Assistant action,
        never a direct write. Refuses on an unfinalized case (Step 20's
        own report-first rule) and refuses to invent a brand-new source
        when none already exists, since creating one is not something
        Phase 11 was asked to (or should) automate -- an Admin creates
        it manually on the Sources & Rights page, informed by the
        finalized report, exactly as Step 23 describes."""

        case = self.repository.get_case(case_public_id)
        if case["locked_at"] is None:
            raise DatasetVerificationSourceRightsError(
                "verification case must be finalized before drafting a Source & Rights proposal"
            )
        existing = self.find_existing_source(case_public_id)
        if existing is None:
            return {
                "drafted": False,
                "reason": (
                    "no existing data source matches this candidate's URL/organization -- "
                    "create one manually on the Sources & Rights page using this case's "
                    "finalized report as reference, then re-run this action to link it"
                ),
            }

        payload = self._build_rights_payload(case)
        proposal = self.assistant_service.propose(
            action_type="link_dataset_verification_rights",
            target_type="dataset_source_rights",
            target_public_id=existing["public_id"],
            request_payload=payload,
            requested_by=admin_id,
            summary=(
                f"Declare Source & Rights findings from {case['verification_code']} "
                f"for existing data source {existing['public_id']}"
            ),
        )
        return {
            "drafted": True,
            "existing_source_public_id": existing["public_id"],
            "proposal": proposal,
        }

    def _build_rights_payload(self, case: dict[str, Any]) -> dict[str, Any]:
        assessments = {
            a["permission_type"]: a["status"]
            for a in self.repository.list_permission_assessments(case["public_id"])
        }
        payload: dict[str, Any] = {
            "rights_status": _RIGHTS_STATUS_MAP.get(case["licence_status"], "unknown"),
            "license_name": case.get("declared_licence"),
            "license_identifier": case.get("normalized_licence_identifier"),
            "reason": (
                f"Derived from finalized dataset verification case {case['verification_code']}"
            ),
        }
        for permission_type, field in _USE_PERMISSION_FIELD_MAP.items():
            payload[field] = assessments.get(permission_type) in _ADMIN_APPROVED_STATUSES
        for permission_type, field in _REQUIREMENT_FLAG_FIELD_MAP.items():
            payload[field] = assessments.get(permission_type) in _REQUIREMENT_AFFIRMED_STATUSES
        return payload
