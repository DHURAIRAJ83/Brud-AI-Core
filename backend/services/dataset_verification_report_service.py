"""Phase 11 Steps 12/13/14/15: conflict detection, the immutable
verification report, lazy reverification, and withdrawal notices.

Nothing here ever silently chooses one evidence source over another
(Step 12), finalizes over stale evidence (Step 13/20), auto-schedules
anything (Step 14 explicitly excludes a background scheduler), or
deletes/quarantines anything on a withdrawal notice (Step 15 --
Phase 12's own job). See
docs/data_verification/phase11_licence_evidence_verification_plan.md.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.dataset_verification_evidence_service import ExternalDatasetEvidenceService
from backend.services.dataset_verification_transport import fetch_evidence
from core_model.data_verification import (
    ADMIN_ONLY_PERMISSION_STATUSES,
    BLOCKING_CONFLICT_SEVERITIES,
    WITHDRAWAL_NOTICE_TYPES,
)

logger = logging.getLogger(__name__)

_REVERIFICATION_INTERVAL_DAYS = 180
_PERMISSIVE_LANGUAGE_MARKERS = ("permit", "allow", "free to use", "may be used", "no restriction")
_RESTRICTIVE_LANGUAGE_MARKERS = (
    "prohibit", "restricted", "no automated", "not permitted", "may not be used",
)


class DatasetVerificationReportError(BrudError):
    status_code = 422
    code = "dataset_verification_report_rejected"


def _now_sql_timestamp() -> str:
    """Matches SQLite's own `CURRENT_TIMESTAMP` format (UTC,
    `YYYY-MM-DD HH:MM:SS`)."""

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


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
        logger.exception("dataset_verification_report_audit_write_failed", extra={"action": action})


class ExternalDatasetConflictService:
    """Step 12: a fixed set of deterministic, bounded keyword-signal
    comparisons -- never semantic NLP -- across already-collected
    evidence. Conflicts are `external_dataset_verification_events`
    rows (`event_type='conflict_detected'`), never a 9th table (see
    migration 033's own design note)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def detect(self, case_public_id: str, *, admin_public_id: str) -> list[dict[str, Any]]:
        case = self.repository.get_case(case_public_id)
        evidence = self.repository.list_evidence_snapshots(case_public_id, current_only=True)
        already_unresolved = {
            event["conflict_type"] for event in self.list_unresolved_conflicts(case_public_id)
        }

        detected: list[dict[str, Any]] = []
        for conflict_type, severity, description in self._run_checks(case, evidence):
            if conflict_type in already_unresolved:
                continue
            event = self.repository.record_event(
                case_public_id,
                {
                    "event_type": "conflict_detected",
                    "summary": description,
                    "conflict_type": conflict_type,
                    "conflict_severity": severity,
                    "evidence_ids": [e["public_id"] for e in evidence],
                    "resolution_status": "unresolved",
                    "performed_by_admin_public_id": admin_public_id,
                },
            )
            detected.append(event)

        if detected:
            unresolved_count = len(self.list_unresolved_conflicts(case_public_id))
            self.repository.update_case(case_public_id, {"conflict_count": unresolved_count})
            _audit(
                self._audit,
                event_type="dataset_verification_conflicts_detected",
                action="detect_conflicts",
                actor_reference=admin_public_id,
                resource_public_id=case_public_id,
                outcome=AuditOutcome.SUCCESS,
                metadata={"conflict_count": len(detected)},
            )
        return detected

    def resolve(
        self,
        case_public_id: str,
        conflict_event_public_id: str,
        *,
        resolution_status: str,
        resolution_reason: str,
        admin_public_id: str,
    ) -> dict[str, Any]:
        """Verification events are append-only -- "resolving" a
        conflict inserts a *new* `conflict_resolved` event referencing
        the original, never rewrites the original row."""

        if not resolution_reason or not resolution_reason.strip():
            raise DatasetVerificationReportError("a non-empty resolution reason is required")
        original = self.repository.get_event(conflict_event_public_id)
        if original["event_type"] != "conflict_detected":
            raise DatasetVerificationReportError("target event is not a detected conflict")

        resolved_event = self.repository.record_event(
            case_public_id,
            {
                "event_type": "conflict_resolved",
                "summary": f"Conflict '{original['conflict_type']}' resolved: {resolution_status}",
                "metadata": {"original_conflict_event_public_id": conflict_event_public_id},
                "conflict_type": original["conflict_type"],
                "conflict_severity": original["conflict_severity"],
                "resolution_status": resolution_status,
                "resolution_reason": resolution_reason,
                "resolved_by_admin_public_id": admin_public_id,
                "resolved_at": _now_sql_timestamp(),
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        unresolved_count = len(self.list_unresolved_conflicts(case_public_id))
        self.repository.update_case(case_public_id, {"conflict_count": unresolved_count})
        _audit(
            self._audit,
            event_type="dataset_verification_conflict_resolved",
            action="resolve_conflict",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"resolution_status": resolution_status},
        )
        return resolved_event

    def list_unresolved_conflicts(self, case_public_id: str) -> list[dict[str, Any]]:
        conflict_events = self.repository.list_conflict_events(case_public_id)
        resolved_originals = {
            event["metadata"].get("original_conflict_event_public_id")
            for event in self.repository.list_events(case_public_id)
            if event["event_type"] == "conflict_resolved"
        }
        return [event for event in conflict_events if event["public_id"] not in resolved_originals]

    def has_unresolved_blocking_conflict(self, case_public_id: str) -> bool:
        return any(
            event["conflict_severity"] in BLOCKING_CONFLICT_SEVERITIES
            for event in self.list_unresolved_conflicts(case_public_id)
        )

    @staticmethod
    def _run_checks(
        case: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> list[tuple[str, str, str]]:
        checks: list[tuple[str, str, str]] = []

        if case["licence_status"] == "conflicting":
            checks.append((
                "declared_vs_licence_file",
                "blocking",
                "Declared licence and collected licence evidence disagree on the SPDX identifier",
            ))

        licence_evidence = [
            e for e in evidence if e["evidence_type"] in ("licence_file", "licence_url")
        ]
        if case.get("declared_licence") and not licence_evidence and any(
            e["evidence_type"] == "repository_licence_metadata" for e in evidence
        ):
            checks.append((
                "provider_vs_repository_metadata",
                "moderate",
                "Provider declares a licence but no licence file was found in the repository",
            ))

        dataset_card_texts = [
            e["content_text"] for e in evidence if e["evidence_type"] == "dataset_card"
        ]
        terms_texts = [e["content_text"] for e in evidence if e["evidence_type"] == "terms_of_use"]
        if dataset_card_texts and terms_texts:
            card_permissive = any(
                marker in text.lower()
                for text in dataset_card_texts
                for marker in _PERMISSIVE_LANGUAGE_MARKERS
            )
            terms_restrictive = any(
                marker in text.lower()
                for text in terms_texts
                for marker in _RESTRICTIVE_LANGUAGE_MARKERS
            )
            if card_permissive and terms_restrictive:
                checks.append((
                    "permissive_language_vs_restrictive_terms",
                    "moderate",
                    "Dataset card language appears permissive while terms "
                    "of use appear restrictive",
                ))

        return checks


class ExternalDatasetVerificationReportService:
    """Step 13/20: the one place `locked_at` is set. Requires no
    unresolved blocking conflict and no stale admin-reviewed
    permission assessment (an evidence snapshot referenced by a review
    whose checksum has since changed)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self.discovery_repository = ExternalDatasetDiscoveryRepository(
            settings.resolved_database_path
        )
        self.conflict_service = ExternalDatasetConflictService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def finalize(self, case_public_id: str, *, admin_public_id: str) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        if case["locked_at"] is not None:
            raise DatasetVerificationReportError("verification case is already finalized")
        if self.conflict_service.has_unresolved_blocking_conflict(case_public_id):
            raise DatasetVerificationReportError(
                "cannot finalize: an unresolved blocking conflict exists"
            )

        assessments = self.repository.list_permission_assessments(case_public_id)
        stale = self._find_stale_reviewed_assessments(case_public_id, assessments)
        if stale:
            raise DatasetVerificationReportError(
                f"cannot finalize: evidence has changed since review for: {', '.join(stale)}"
            )

        report = self._build_report(case, assessments)
        final_status = self._determine_final_status(case, assessments)
        now = _now_sql_timestamp()
        next_reverification = (
            datetime.now(UTC) + timedelta(days=_REVERIFICATION_INTERVAL_DAYS)
        ).strftime("%Y-%m-%d %H:%M:%S")
        self.repository.update_case(
            case_public_id,
            {
                "status": final_status,
                "completed_at": now,
                "last_verified_at": now,
                "next_reverification_at": next_reverification,
            },
        )
        locked = self.repository.lock_case(case_public_id, report)
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "case_finalized",
                "summary": f"Verification finalized as '{final_status}'",
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_case_finalized",
            action="finalize",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"final_status": final_status},
        )
        return locked

    def _find_stale_reviewed_assessments(
        self, case_public_id: str, assessments: list[dict[str, Any]]
    ) -> list[str]:
        """A reviewed evidence snapshot goes stale not by its own
        checksum changing in place (evidence rows are never mutated --
        `refresh_evidence`/reverification always insert a *new* row
        with a *new* public_id and mark the old one superseded) but by
        the specific public_id a review referenced no longer being the
        current snapshot at all. So this checks `is_current` on each
        referenced row by its own public_id, not a checksum lookup
        keyed by public_id (which would silently miss every real
        supersede, since the new row never shares the old public_id)."""

        all_evidence = {
            e["public_id"]: e
            for e in self.repository.list_evidence_snapshots(case_public_id)
        }
        stale: list[str] = []
        for assessment in assessments:
            if assessment["status"] not in ADMIN_ONLY_PERMISSION_STATUSES:
                continue
            checksum_set = assessment.get("evidence_checksum_set") or {}
            for evidence_public_id, checksum_at_review in checksum_set.items():
                evidence_row = all_evidence.get(evidence_public_id)
                if evidence_row is None:
                    continue
                if (
                    not evidence_row["is_current"]
                    or evidence_row["content_checksum"] != checksum_at_review
                ):
                    stale.append(assessment["permission_type"])
                    break
        return stale

    @staticmethod
    def _determine_final_status(case: dict[str, Any], assessments: list[dict[str, Any]]) -> str:
        statuses = {a["permission_type"]: a["status"] for a in assessments}
        if any(status == "prohibited" for status in statuses.values()):
            return "blocked"
        if any(status == "approved_with_conditions" for status in statuses.values()):
            return "verified_with_conditions"
        if case["evidence_status"] != "complete" or case["licence_status"] != "verified":
            return "insufficient_evidence"
        return "verified"

    def _build_report(
        self, case: dict[str, Any], assessments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        candidate = self.discovery_repository.get_candidate(case["candidate_public_id"])
        upstream_sources = self.repository.list_upstream_sources(case["public_id"])
        evidence = self.repository.list_evidence_snapshots(case["public_id"], current_only=True)
        reviews = self.repository.list_reviews(case["public_id"])
        conflicts = self.repository.list_conflict_events(case["public_id"])
        evidence_types_collected = sorted({e["evidence_type"] for e in evidence})

        permissions_report = {
            a["permission_type"]: {
                "status": a["status"],
                "decision_basis": a["decision_basis"],
                "conditions": a["conditions"],
                "reviewed_by": a["reviewed_by"],
                "reviewed_at": a["reviewed_at"],
                "provenance": "admin_decision" if a["reviewed_by"] else "assistant_inference",
            }
            for a in assessments
        }
        # Step 24: 4 read-only, derived boolean eligibility signals --
        # `True` only when the matching permission is an Admin-approved
        # status. `finalize()` has already refused to run at all if any
        # unresolved blocking conflict exists, so reaching this point
        # already satisfies that half of the gate. These signals are
        # never written to any governance table and never themselves
        # trigger anything -- Phase 12+ owns the actual approval gate.
        approved_statuses = {"approved", "approved_with_conditions"}
        governance_eligibility = {
            f"{permission_type}_eligible": permissions_report.get(permission_type, {}).get("status")
            in approved_statuses
            for permission_type in ("rag_use", "training_use", "evaluation_use", "commercial_use")
        }

        return {
            "dataset_identity": {
                "value": {
                    "canonical_name": candidate["canonical_name"],
                    "organization": candidate["organization"],
                    "version": candidate["version"],
                    "revision": candidate["revision"],
                },
                "provenance": "provider_declared",
            },
            "identity_status": {"value": case["identity_status"], "provenance": "verified_fact"},
            "provider": {
                "value": candidate.get("primary_provider_public_id"),
                "provenance": "provider_declared",
            },
            "upstream_sources": {
                "value": [
                    {
                        "name": u["upstream_name"],
                        "relationship_type": u["relationship_type"],
                        "verification_status": u["verification_status"],
                    }
                    for u in upstream_sources
                ],
                "provenance": "assistant_inference",
            },
            "evidence_collected": {
                "value": evidence_types_collected, "provenance": "verified_fact",
            },
            "evidence_missing": {
                "value": sorted(
                    {"licence_file", "terms_of_use", "privacy_policy"}
                    - set(evidence_types_collected)
                ),
                "provenance": "verified_fact",
            },
            "declared_licence": {
                "value": case.get("declared_licence"), "provenance": "provider_declared",
            },
            "normalized_licence_identifier": {
                "value": case.get("normalized_licence_identifier"),
                "provenance": (
                    "verified_fact" if case["licence_status"] == "verified" else "unknown"
                ),
            },
            "licence_status": {"value": case["licence_status"], "provenance": "verified_fact"},
            "terms_status": {"value": case["terms_status"], "provenance": "verified_fact"},
            "permissions": {"value": permissions_report, "provenance": "admin_decision"},
            "conflicts": {
                "value": [
                    {
                        "conflict_type": c["conflict_type"],
                        "severity": c["conflict_severity"],
                        "resolution_status": c["resolution_status"],
                    }
                    for c in conflicts
                ],
                "provenance": "verified_fact",
            },
            "warnings": {"value": case["warning_count"], "provenance": "verified_fact"},
            "blocking_reasons": {
                "value": case["blocking_reason_count"], "provenance": "verified_fact",
            },
            "reviewers": {
                "value": sorted({r["reviewer_admin_public_id"] for r in reviews}),
                "provenance": "verified_fact",
            },
            "evidence_checksums": {
                "value": {e["public_id"]: e["content_checksum"] for e in evidence},
                "provenance": "verified_fact",
            },
            "next_reverification_at": {
                "value": None,  # set on the case row itself, not duplicated pre-finalize
                "provenance": "assistant_inference",
            },
            "recommended_next_action": {
                "value": self._recommended_next_action(case, permissions_report),
                "provenance": "assistant_inference",
            },
            "governance_eligibility": {
                "value": governance_eligibility,
                "provenance": "assistant_inference",
            },
        }

    @staticmethod
    def _recommended_next_action(
        case: dict[str, Any], permissions_report: dict[str, Any]
    ) -> str:
        if case["licence_status"] != "verified":
            return "Collect and verify official licence evidence"
        needs_review = [
            permission_type
            for permission_type, entry in permissions_report.items()
            if entry["status"] == "needs_legal_review"
        ]
        if needs_review:
            return f"Admin review required for: {', '.join(sorted(needs_review))}"
        return "No further action recommended at this time"


class ExternalDatasetReverificationService:
    """Step 14: lazy, explicit-refresh-only reverification -- no
    background scheduler. Works even on an already-finalized case
    (the 3 narrowly-scoped repository exceptions to "immutable once
    locked" exist exactly for this)."""

    def __init__(
        self, settings: Settings, *, evidence_service: ExternalDatasetEvidenceService | None = None
    ) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self.evidence_service = evidence_service or ExternalDatasetEvidenceService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def check(self, case_public_id: str, *, admin_public_id: str) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        network_evidence = [
            e
            for e in self.repository.list_evidence_snapshots(case_public_id, current_only=True)
            if e["source_url"]
        ]

        any_source_changed = False
        refreshed: list[dict[str, Any]] = []
        for evidence in network_evidence:
            try:
                result = self._refresh_for_reverification(case_public_id, evidence, admin_public_id)
            except Exception:
                logger.exception(
                    "dataset_verification_reverification_refresh_failed",
                    extra={"evidence_public_id": evidence["public_id"]},
                )
                continue
            refreshed.append(result)
            if result["source_changed"]:
                any_source_changed = True

        if any_source_changed:
            expiry_status = "source_changed"
            self._demote_admin_approved_permissions(case_public_id, admin_public_id)
        else:
            expiry_status = self._expiry_status_from_dates(case.get("next_reverification_at"))

        updated = self.repository.update_case_reverification_fields(
            case_public_id,
            {"verification_expiry_status": expiry_status, "last_verified_at": _now_sql_timestamp()},
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "reverification_checked",
                "summary": f"Reverification checked -- expiry status '{expiry_status}'",
                "metadata": {
                    "evidence_refreshed": len(refreshed), "source_changed": any_source_changed,
                },
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_reverification_checked",
            action="reverify",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"expiry_status": expiry_status},
        )
        return {"case": updated, "source_changed": any_source_changed, "refreshed": refreshed}

    def _refresh_for_reverification(
        self, case_public_id: str, evidence: dict[str, Any], admin_public_id: str
    ) -> dict[str, Any]:
        allowed_domains = self.evidence_service.allowed_domains_for_case(case_public_id)
        fetched = fetch_evidence(
            evidence["source_url"],
            allowed_domains=allowed_domains,
            transport=self.evidence_service._transport,  # noqa: SLF001
            resolver=self.evidence_service._resolver,  # noqa: SLF001
        )
        source_changed = fetched.content_checksum != evidence["content_checksum"]
        new_snapshot = self.repository.add_evidence_snapshot(
            case_public_id,
            {
                "candidate_public_id": evidence["candidate_public_id"],
                "provider_public_id": evidence["provider_public_id"],
                "evidence_type": evidence["evidence_type"],
                "authority_level": evidence["authority_level"],
                "source_url": evidence["source_url"],
                "resolved_url": fetched.resolved_url,
                "source_domain": fetched.source_domain,
                "content_type": fetched.content_type,
                "retrieval_status": "success",
                "http_status": fetched.http_status,
                "content_text": fetched.content_text,
                "content_excerpt": fetched.content_text[:500],
                "content_checksum": fetched.content_checksum,
                "response_headers": fetched.response_headers,
                "size_bytes": fetched.size_bytes,
                "warnings": fetched.warnings,
                "supersedes_evidence_public_id": evidence["public_id"],
                "created_by_admin_public_id": admin_public_id,
            },
            allow_locked_case=True,
        )
        if source_changed:
            self.repository.record_event(
                case_public_id,
                {
                    "event_type": "source_changed_detected",
                    "summary": f"{evidence['evidence_type']} evidence checksum changed on reverify",
                    "metadata": {
                        "old_evidence_public_id": evidence["public_id"],
                        "new_evidence_public_id": new_snapshot["public_id"],
                    },
                    "performed_by_admin_public_id": admin_public_id,
                },
            )
        return {"snapshot": new_snapshot, "source_changed": source_changed}

    def _demote_admin_approved_permissions(self, case_public_id: str, admin_public_id: str) -> None:
        del admin_public_id
        for assessment in self.repository.list_permission_assessments(case_public_id):
            if assessment["status"] in ADMIN_ONLY_PERMISSION_STATUSES:
                self.repository.demote_permission_status(
                    case_public_id,
                    assessment["permission_type"],
                    new_status="needs_legal_review",
                    reason="source evidence checksum changed; prior approval requires re-review",
                )

    @staticmethod
    def _expiry_status_from_dates(next_reverification_at: str | None) -> str:
        if not next_reverification_at:
            return "current"
        try:
            deadline = datetime.strptime(next_reverification_at, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=UTC
            )
        except ValueError:
            return "current"
        now = datetime.now(UTC)
        if now > deadline:
            return "expired"
        if now > deadline - timedelta(days=14):
            return "due_soon"
        return "current"


class ExternalDatasetWithdrawalService:
    """Step 15: recording a notice that a provider or rights holder
    requests removal or a terms change. Never deletes or quarantines
    anything -- that decision belongs to Phase 12."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def record_notice(
        self, case_public_id: str, values: dict[str, Any], *, admin_public_id: str
    ) -> dict[str, Any]:
        if values.get("notice_type") not in WITHDRAWAL_NOTICE_TYPES:
            raise DatasetVerificationReportError(
                f"unknown withdrawal notice type: {values.get('notice_type')}"
            )
        case = self.repository.get_case(case_public_id)
        impact_summary = self._compute_impact_summary(case_public_id, case)
        notice = self.repository.record_withdrawal_notice(
            case_public_id,
            {
                **values,
                "candidate_public_id": case["candidate_public_id"],
                "recorded_by_admin_public_id": admin_public_id,
                "impact_status": "assessed",
                "impact_summary": impact_summary,
            },
        )
        self.repository.update_case_reverification_fields(
            case_public_id, {"verification_expiry_status": "withdrawn"}
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "withdrawal_notice_recorded",
                "summary": f"Withdrawal notice recorded: {values['notice_type']}",
                "metadata": {"notice_public_id": notice["public_id"]},
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_withdrawal_notice_recorded",
            action="record_withdrawal_notice",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"notice_type": values["notice_type"]},
        )
        return notice

    def _compute_impact_summary(self, case_public_id: str, case: dict[str, Any]) -> dict[str, Any]:
        """Purely derived from already-known state -- reuses Phase 10's
        own `search_session`/candidate linkage, never a new lineage
        system. A withdrawal notice conservatively blocks every future
        action until an Admin re-reviews (Step 15's own safety-first
        rule); `previously_approved_permissions` names exactly which
        prior Admin approvals now need that re-review."""

        assessments = self.repository.list_permission_assessments(case_public_id)
        approved_statuses = {"approved", "approved_with_conditions"}
        previously_approved = sorted(
            a["permission_type"] for a in assessments if a["status"] in approved_statuses
        )
        return {
            "future_sample_import_blocked": True,
            "future_rag_use_blocked": True,
            "future_training_use_blocked": True,
            "commercial_use_blocked": True,
            "existing_downstream_lineage_found": case["search_session_public_id"] is not None,
            "human_review_required": True,
            "previously_approved_permissions": previously_approved,
        }
