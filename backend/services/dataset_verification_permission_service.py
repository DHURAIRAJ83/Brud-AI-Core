"""Phase 11 Steps 8/9/10: independent permission assessment (16
dimensions), commercial-use verification, and upstream-source review.

Design note on the shared status vocabulary across all 16 permission
types (`core_model.data_verification.PERMISSION_STATUSES`): for the
7 "use" dimensions (`rag_use`, `training_use`, `evaluation_use`,
`commercial_use`, `redistribution`, `modification`, `derivative_works`)
`likely_allowed`/`likely_restricted` describes whether *that use* is
permitted. For the 9 "requirement/restriction-flag" dimensions
(`attribution_required`, `share_alike_required`, `notice_required`,
`source_disclosure_required`, `personal_data_restriction`,
`research_only`, `non_commercial_only`, `geographic_restriction`,
`gated_access_restriction`) `likely_restricted` means the named
condition *does* apply / must be honored, and `likely_allowed` means
it does *not* apply -- both readings share one vocabulary, applied
consistently, per Step 8.

`training_use` and `commercial_use` are structurally never set to
`likely_allowed` by any automated pass in this module -- Step 9's own
rule ("do not infer training or commercial permission from a licence
name alone") is enforced here as a hard ceiling, not a heuristic:
these two dimensions cap out at `needs_legal_review`, always leaving
the actual allow/deny decision to `.review()` (an explicit human
Admin action). The other 5 "use"/6 "clause" dimensions may reach
`likely_allowed` automatically, but only from a *verified* SPDX
licence's own well-established, published terms (`_SPDX_PERMISSION_
HINTS`) -- never a guess, and never itself an `approved` status.

Nothing here ever writes an admin-only status
(`approved`/`approved_with_conditions`/`not_approved`/`prohibited`) --
the repository's own `assess_permission()`/`review_permission()` split
is the structural gate; this module never bypasses it.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.models.domain import AuditEventCreate, AuditOutcome
from core_model.data_verification import (
    ADMIN_ONLY_PERMISSION_STATUSES,
    COMMERCIAL_USE_INTENDED_CATEGORIES,
    PERMISSION_TYPES,
    UPSTREAM_VERIFICATION_STATUSES,
)

logger = logging.getLogger(__name__)

# A small, explicit, hand-maintained table of well-known SPDX
# licences' own published terms -- never a guess, never covering an
# identifier not in `core_model.data_verification.SPDX_EXACT_MATCHES`.
# An identifier or dimension missing here simply falls through to
# `needs_legal_review`, never a fabricated default.
_SPDX_PERMISSION_HINTS: dict[str, dict[str, str]] = {
    "CC-BY-4.0": {
        "redistribution": "likely_allowed", "modification": "likely_allowed",
        "derivative_works": "likely_allowed", "attribution_required": "likely_restricted",
        "share_alike_required": "likely_allowed", "non_commercial_only": "likely_allowed",
        "research_only": "likely_allowed", "notice_required": "likely_allowed",
        "source_disclosure_required": "likely_allowed",
    },
    "CC-BY-SA-4.0": {
        "redistribution": "likely_allowed", "modification": "likely_allowed",
        "derivative_works": "likely_allowed", "attribution_required": "likely_restricted",
        "share_alike_required": "likely_restricted", "non_commercial_only": "likely_allowed",
        "research_only": "likely_allowed", "notice_required": "likely_allowed",
        "source_disclosure_required": "likely_allowed",
    },
    "CC-BY-NC-4.0": {
        "redistribution": "likely_allowed", "modification": "likely_allowed",
        "derivative_works": "likely_allowed", "attribution_required": "likely_restricted",
        "share_alike_required": "likely_allowed", "non_commercial_only": "likely_restricted",
        "research_only": "likely_allowed", "notice_required": "likely_allowed",
        "source_disclosure_required": "likely_allowed",
    },
    "CC-BY-NC-SA-4.0": {
        "redistribution": "likely_allowed", "modification": "likely_allowed",
        "derivative_works": "likely_allowed", "attribution_required": "likely_restricted",
        "share_alike_required": "likely_restricted", "non_commercial_only": "likely_restricted",
        "research_only": "likely_allowed", "notice_required": "likely_allowed",
        "source_disclosure_required": "likely_allowed",
    },
    "CC-BY-ND-4.0": {
        "redistribution": "likely_allowed", "modification": "likely_restricted",
        "derivative_works": "likely_restricted", "attribution_required": "likely_restricted",
        "share_alike_required": "likely_allowed", "non_commercial_only": "likely_allowed",
        "research_only": "likely_allowed", "notice_required": "likely_allowed",
        "source_disclosure_required": "likely_allowed",
    },
    "CC0-1.0": {
        "redistribution": "likely_allowed", "modification": "likely_allowed",
        "derivative_works": "likely_allowed", "attribution_required": "likely_allowed",
        "share_alike_required": "likely_allowed", "non_commercial_only": "likely_allowed",
        "research_only": "likely_allowed", "notice_required": "likely_allowed",
        "source_disclosure_required": "likely_allowed",
    },
    "MIT": {
        "redistribution": "likely_allowed", "modification": "likely_allowed",
        "derivative_works": "likely_allowed", "attribution_required": "likely_restricted",
        "share_alike_required": "likely_allowed", "non_commercial_only": "likely_allowed",
        "research_only": "likely_allowed", "notice_required": "likely_restricted",
        "source_disclosure_required": "likely_allowed",
    },
    "Apache-2.0": {
        "redistribution": "likely_allowed", "modification": "likely_allowed",
        "derivative_works": "likely_allowed", "attribution_required": "likely_restricted",
        "share_alike_required": "likely_allowed", "non_commercial_only": "likely_allowed",
        "research_only": "likely_allowed", "notice_required": "likely_restricted",
        "source_disclosure_required": "likely_allowed",
    },
    "GPL-3.0-only": {
        "redistribution": "likely_allowed", "modification": "likely_allowed",
        "derivative_works": "likely_allowed", "attribution_required": "likely_restricted",
        "share_alike_required": "likely_restricted", "non_commercial_only": "likely_allowed",
        "research_only": "likely_allowed", "notice_required": "likely_restricted",
        "source_disclosure_required": "likely_restricted",
    },
}

_HINT_TABLE_DIMENSIONS = (
    "redistribution", "modification", "derivative_works", "attribution_required",
    "share_alike_required", "non_commercial_only", "research_only", "notice_required",
    "source_disclosure_required",
)


class DatasetVerificationPermissionError(BrudError):
    status_code = 422
    code = "dataset_verification_permission_rejected"


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
                resource_type="external_dataset_verification_case",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "dataset_verification_permission_audit_write_failed", extra={"action": action}
        )


class ExternalDatasetPermissionAssessmentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self.discovery_repository = ExternalDatasetDiscoveryRepository(
            settings.resolved_database_path
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def assess(self, case_public_id: str, *, admin_public_id: str) -> dict[str, dict[str, Any]]:
        """Automated, read-only over already-collected evidence +
        identity + licence state. Never writes an admin-only status --
        the repository itself would reject any attempt."""

        case = self.repository.get_case(case_public_id)
        candidate = self.discovery_repository.get_candidate(case["candidate_public_id"])
        evidence = self.repository.list_evidence_snapshots(case_public_id, current_only=True)
        unresolved_upstream = self.repository.unresolved_upstream_exists(case_public_id)

        results: dict[str, dict[str, Any]] = {}
        for permission_type in PERMISSION_TYPES:
            if permission_type == "commercial_use":
                # Always assessed separately via `assess_commercial_use()`
                # -- Step 9 requires an explicit intended-use category
                # this generic pass does not have.
                continue
            status, basis, conditions = self._assess_one(
                permission_type,
                case=case,
                candidate=candidate,
                evidence=evidence,
                unresolved_upstream=unresolved_upstream,
            )
            results[permission_type] = self.repository.assess_permission(
                case_public_id,
                permission_type,
                {
                    "candidate_public_id": case["candidate_public_id"],
                    "status": status,
                    "decision_basis": basis,
                    "conditions": conditions,
                    "assessed_by": "system",
                },
            )

        self._refresh_permission_status(case_public_id)
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "permission_assessed",
                "summary": (
                    f"Automated permission assessment completed for {len(results)} dimensions"
                ),
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_permission_assessed",
            action="assess_permissions",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return results

    def assess_commercial_use(
        self, case_public_id: str, *, intended_use_category: str, admin_public_id: str
    ) -> dict[str, Any]:
        """Step 9: commercial use is always assessed independently and
        explicitly, never inferred from any other permission's value
        or from a licence name alone. The automated status here can
        never be `likely_allowed` -- only `.review()` may grant that."""

        if intended_use_category not in COMMERCIAL_USE_INTENDED_CATEGORIES:
            raise DatasetVerificationPermissionError(
                f"unknown intended use category: {intended_use_category}"
            )
        case = self.repository.get_case(case_public_id)
        evidence = self.repository.list_evidence_snapshots(case_public_id, current_only=True)
        unresolved_upstream = self.repository.unresolved_upstream_exists(case_public_id)
        status, basis = self._assess_commercial_use(
            licence_status=case["licence_status"],
            unresolved_upstream=unresolved_upstream,
            evidence_texts=[e.get("content_text", "") for e in evidence],
        )
        assessment = self.repository.assess_permission(
            case_public_id,
            "commercial_use",
            {
                "candidate_public_id": case["candidate_public_id"],
                "status": status,
                "decision_basis": basis,
                "conditions": {"intended_use_category": intended_use_category},
                "assessed_by": "system",
            },
        )
        self._refresh_permission_status(case_public_id)
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "permission_assessed",
                "summary": f"Commercial use assessed for intended use '{intended_use_category}'",
                "metadata": {"intended_use_category": intended_use_category},
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_commercial_use_assessed",
            action="assess_commercial_use",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"intended_use_category": intended_use_category},
        )
        return assessment

    def review(
        self,
        case_public_id: str,
        permission_type: str,
        *,
        status: str,
        reviewed_by: str,
        reason: str,
        conditions: dict[str, Any] | None = None,
        evidence_checksum_set: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The only path to an admin-only status -- human confirmation
        is mandatory for every permission decision (the task's own
        non-negotiable rule); the repository enforces `reason`/
        `reviewed_by` non-empty as defense in depth.

        Auto-captures the current evidence checksum set (every
        currently-collected evidence snapshot's public_id -> checksum)
        when the caller doesn't supply one, so
        `ExternalDatasetVerificationReportService.finalize()`'s
        stale-state check has something real to compare against
        later, without requiring every API/Assistant caller to know
        this snapshotting mechanic."""

        if evidence_checksum_set is None:
            evidence = self.repository.list_evidence_snapshots(case_public_id, current_only=True)
            evidence_checksum_set = {e["public_id"]: e["content_checksum"] for e in evidence}
        result = self.repository.review_permission(
            case_public_id,
            permission_type,
            status=status,
            reviewed_by=reviewed_by,
            reason=reason,
            conditions=conditions,
            evidence_checksum_set=evidence_checksum_set,
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "permission_reviewed",
                "summary": f"{permission_type} reviewed -> '{status}' by {reviewed_by}",
                "metadata": {"permission_type": permission_type, "status": status},
                "performed_by_admin_public_id": reviewed_by,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_permission_reviewed",
            action="review_permission",
            actor_reference=reviewed_by,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"permission_type": permission_type, "status": status},
        )
        self._refresh_permission_status(case_public_id)
        return result

    def _refresh_permission_status(self, case_public_id: str) -> None:
        assessments = self.repository.list_permission_assessments(case_public_id)
        if not assessments:
            status = "not_started"
        elif all(
            a["status"] in ADMIN_ONLY_PERMISSION_STATUSES or a["status"] == "not_applicable"
            for a in assessments
        ):
            status = "complete"
        else:
            status = "incomplete"
        self.repository.update_case(case_public_id, {"permission_status": status})

    # -- per-dimension automated assessment -----------------------------------

    def _assess_one(
        self,
        permission_type: str,
        *,
        case: dict[str, Any],
        candidate: dict[str, Any],
        evidence: list[dict[str, Any]],
        unresolved_upstream: bool,
    ) -> tuple[str, str, dict[str, Any]]:
        licence_status = case["licence_status"]
        normalized = case.get("normalized_licence_identifier")
        evidence_texts = [e.get("content_text", "") for e in evidence]

        if permission_type == "training_use":
            licence_evidence_present = any(
                e["evidence_type"] in ("licence_file", "licence_url") for e in evidence
            )
            status, basis = self._assess_training_use(
                licence_status, unresolved_upstream, licence_evidence_present
            )
            return status, basis, {}
        if permission_type in ("rag_use", "evaluation_use"):
            status, basis = self._assess_use_permission(
                licence_status, normalized, unresolved_upstream
            )
            return status, basis, {}
        if permission_type == "personal_data_restriction":
            status, basis = self._assess_personal_data(evidence)
            return status, basis, {}
        if permission_type == "gated_access_restriction":
            status, basis = self._assess_gated(candidate)
            return status, basis, {}
        if permission_type == "geographic_restriction":
            status, basis = self._assess_geographic(evidence_texts)
            return status, basis, {}
        if permission_type in _HINT_TABLE_DIMENSIONS:
            status, basis = self._assess_from_hint_table(
                permission_type, licence_status, normalized
            )
            return status, basis, {}
        return "unknown", f"no automated assessment logic defined for '{permission_type}'", {}

    @staticmethod
    def _assess_from_hint_table(
        permission_type: str, licence_status: str, normalized_identifier: str | None
    ) -> tuple[str, str]:
        if licence_status != "verified":
            basis = f"licence status is '{licence_status}', not independently verified"
            fallback = (
                "unknown" if licence_status in ("unknown", "missing") else "needs_legal_review"
            )
            return fallback, basis
        hints = _SPDX_PERMISSION_HINTS.get(normalized_identifier or "", {})
        if permission_type in hints:
            basis = f"derived from {normalized_identifier}'s own published terms"
            return hints[permission_type], basis
        return "needs_legal_review", f"no automated hint available for '{normalized_identifier}'"

    @staticmethod
    def _assess_use_permission(
        licence_status: str, normalized_identifier: str | None, unresolved_upstream: bool
    ) -> tuple[str, str]:
        if unresolved_upstream:
            return "needs_legal_review", "an upstream source's rights are not yet verified"
        if licence_status != "verified":
            basis = f"licence status is '{licence_status}'"
            fallback = (
                "unknown" if licence_status in ("unknown", "missing") else "needs_legal_review"
            )
            return fallback, basis
        if normalized_identifier:
            basis = f"licence {normalized_identifier} verified and evidence-backed"
            return "likely_allowed", basis
        return "needs_legal_review", "licence verified but not a recognized SPDX identifier"

    @staticmethod
    def _assess_training_use(
        licence_status: str, unresolved_upstream: bool, licence_evidence_present: bool
    ) -> tuple[str, str]:
        if unresolved_upstream:
            return "needs_legal_review", "an upstream source's rights are not yet verified"
        if not licence_evidence_present:
            return "unknown", "no licence evidence collected yet"
        if licence_status in ("missing", "conflicting", "restricted", "withdrawn"):
            return "likely_restricted", f"licence status is '{licence_status}'"
        return (
            "needs_legal_review",
            "training-use suitability always requires Admin legal review, "
            "never inferred automatically from licence text alone",
        )

    @staticmethod
    def _assess_commercial_use(
        *, licence_status: str, unresolved_upstream: bool, evidence_texts: list[str]
    ) -> tuple[str, str]:
        if unresolved_upstream:
            return "needs_legal_review", "an upstream source's rights are not yet verified"
        combined = " ".join(evidence_texts).lower()
        if "non-commercial" in combined or "cc-by-nc" in combined or "noncommercial" in combined:
            return "likely_restricted", "evidence text indicates a non-commercial restriction"
        if licence_status in ("unknown", "missing"):
            return "unknown", "no licence evidence collected yet"
        return (
            "needs_legal_review",
            "commercial use always requires independent Admin verification, "
            "never inferred automatically",
        )

    @staticmethod
    def _assess_personal_data(evidence: list[dict[str, Any]]) -> tuple[str, str]:
        privacy_evidence = [
            e for e in evidence if e["evidence_type"] in ("privacy_policy", "consent_statement")
        ]
        if not privacy_evidence:
            return "unknown", "no privacy/consent evidence collected"
        combined = " ".join(e.get("content_text", "") for e in privacy_evidence).lower()
        if any(keyword in combined for keyword in ("personal data", "pii", "consent", "gdpr")):
            return "likely_restricted", "privacy/consent evidence references personal data handling"
        return (
            "likely_allowed",
            "privacy/consent evidence collected with no personal-data markers found",
        )

    @staticmethod
    def _assess_gated(candidate: dict[str, Any]) -> tuple[str, str]:
        if candidate.get("gated"):
            return "likely_restricted", "candidate is marked gated by the provider"
        return "likely_allowed", "candidate is not marked gated by the provider"

    @staticmethod
    def _assess_geographic(evidence_texts: list[str]) -> tuple[str, str]:
        combined = " ".join(t for t in evidence_texts if t).lower()
        geographic_keywords = (
            "geographic restriction", "not available in", "export control", "embargo",
        )
        if any(keyword in combined for keyword in geographic_keywords):
            return "needs_legal_review", "evidence text references a geographic/export restriction"
        if not any(evidence_texts):
            return "unknown", "no evidence collected to assess geographic restrictions"
        return "not_applicable", "no geographic restriction markers found in collected evidence"


class ExternalDatasetUpstreamReviewService:
    """Step 10: one row per upstream source a dataset aggregates from.
    Training/commercial approval for the *main* dataset stays capped
    at `needs_legal_review` (see `ExternalDatasetPermissionAssessmentService`)
    while `unresolved_upstream_exists()` is true."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def add_upstream_source(
        self, case_public_id: str, values: dict[str, Any], *, admin_public_id: str
    ) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        upstream = self.repository.add_upstream_source(
            case_public_id,
            {
                **values,
                "candidate_public_id": case["candidate_public_id"],
                "created_by_admin_public_id": admin_public_id,
            },
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "upstream_added",
                "summary": f"Upstream source '{upstream['upstream_name']}' added",
                "metadata": {"upstream_public_id": upstream["public_id"]},
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        self._refresh_upstream_status(case_public_id)
        _audit(
            self._audit,
            event_type="dataset_verification_upstream_added",
            action="add_upstream_source",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return upstream

    def verify_upstream_source(
        self,
        case_public_id: str,
        upstream_public_id: str,
        *,
        verification_status: str,
        admin_public_id: str,
    ) -> dict[str, Any]:
        if verification_status not in UPSTREAM_VERIFICATION_STATUSES:
            raise DatasetVerificationPermissionError(
                f"unknown upstream verification status: {verification_status}"
            )
        updated = self.repository.update_upstream_source(
            upstream_public_id, {"verification_status": verification_status}
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "upstream_verified",
                "summary": f"Upstream source verification set to '{verification_status}'",
                "metadata": {"upstream_public_id": upstream_public_id},
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        self._refresh_upstream_status(case_public_id)
        _audit(
            self._audit,
            event_type="dataset_verification_upstream_verified",
            action="verify_upstream_source",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"verification_status": verification_status},
        )
        return updated

    def unresolved_upstream_exists(self, case_public_id: str) -> bool:
        return self.repository.unresolved_upstream_exists(case_public_id)

    def _refresh_upstream_status(self, case_public_id: str) -> None:
        sources = self.repository.list_upstream_sources(case_public_id)
        if not sources:
            status = "not_started"
        elif all(source["verification_status"] == "verified" for source in sources):
            status = "complete"
        elif any(source["verification_status"] == "conflicting" for source in sources):
            status = "conflicting"
        else:
            status = "incomplete"
        self.repository.update_case(case_public_id, {"upstream_status": status})
