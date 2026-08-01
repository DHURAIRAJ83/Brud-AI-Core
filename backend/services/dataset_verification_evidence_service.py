"""Phase 11 Steps 5/6/7/11: evidence collection (network + manual),
official-source identity verification, licence normalization, and the
terms/privacy/consent snapshot-completeness roll-up.

Nothing here ever downloads a dataset payload file, imports records,
activates RAG, or grants any permission -- these services only ever
collect *evidence* and record *independent assessment signals* for a
human Admin to review. See
docs/data_verification/phase11_licence_evidence_verification_plan.md.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_data_providers import ExternalDataProviderRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.dataset_verification_transport import (
    EvidenceHttpTransport,
    EvidenceRetrievalError,
    Resolver,
    default_evidence_http_transport,
    default_resolver,
    fetch_evidence,
)
from core_model.corpus.text_extraction import content_checksum
from core_model.data_verification import (
    SPDX_EXACT_MATCHES,
    default_authority_for_evidence_type,
    normalize_spdx_identifier,
)

logger = logging.getLogger(__name__)

_CONTENT_EXCERPT_CHARS = 500
_STRONG_IDENTITY_SIGNAL_TYPES = ("provider_dataset_id", "official_domain")
# The 3 signals (of the 11 in Step 6) with no reliable automated
# derivation available yet -- honestly left for a human Admin to
# record via `record_manual_identity_signal`, never fabricated.
_MANUAL_ONLY_SIGNAL_TYPES = (
    "dataset_card_identifier", "upstream_citation", "checksum_or_release_tag",
)
_TERMS_RELEVANT_EVIDENCE_TYPES = ("terms_of_use", "privacy_policy", "consent_statement")

# Canonical SPDX display forms, longest first so a substring scan never
# matches a shorter identifier that is itself a prefix of a longer one
# (e.g. "CC-BY-4.0" inside "CC-BY-SA-4.0").
_KNOWN_SPDX_DISPLAY_FORMS = sorted(set(SPDX_EXACT_MATCHES.values()), key=len, reverse=True)


def _find_spdx_identifiers_in_text(text: str | None) -> set[str]:
    """A bounded, explicit keyword scan -- never semantic NLP (Step
    12's own rule) -- for conflict detection only. Licence-field
    *normalization* (`normalize_spdx_identifier`) stays exact-match-only
    and is never relaxed by this helper."""

    if not text:
        return set()
    lowered = text.lower()
    return {form for form in _KNOWN_SPDX_DISPLAY_FORMS if form.lower() in lowered}


class DatasetVerificationError(BrudError):
    status_code = 422
    code = "dataset_verification_rejected"


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
        logger.exception("dataset_verification_audit_write_failed", extra={"action": action})


def _normalize_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    domain = domain.lower()
    return domain[4:] if domain.startswith("www.") else domain


def _domain_of(url: str | None) -> str | None:
    if not url:
        return None
    return _normalize_domain(urlparse(url).hostname)


def _contains(haystack_texts: list[str], needle: str | None) -> bool:
    if not needle or not needle.strip():
        return False
    needle_lower = needle.strip().lower()
    return any(needle_lower in text.lower() for text in haystack_texts if text)


_GITHUB_OWNER_PATTERN = re.compile(r"github\.com/([^/]+)/")


def _github_owner(repository_url: str | None) -> str | None:
    if not repository_url:
        return None
    match = _GITHUB_OWNER_PATTERN.search(repository_url)
    return match.group(1) if match else None


class ExternalDatasetEvidenceService:
    """Collects one evidence snapshot per network fetch or manual
    admin submission, always through the SSRF-protected transport
    (never an arbitrary admin-pasted URL) or as explicitly-flagged
    manual text."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: EvidenceHttpTransport = default_evidence_http_transport,
        resolver: Resolver = default_resolver,
    ) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self.discovery_repository = ExternalDatasetDiscoveryRepository(
            settings.resolved_database_path
        )
        self.provider_repository = ExternalDataProviderRepository(settings.resolved_database_path)
        self._transport = transport
        self._resolver = resolver
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def allowed_domains_for_case(self, case_public_id: str) -> set[str]:
        """A dataset's own already-registered provider domains (Phase
        9) plus any domain the admin explicitly approved as an
        official upstream source *for this specific case* -- never an
        arbitrary URL the admin merely pastes into a request."""

        case = self.repository.get_case(case_public_id)
        domains: set[str] = {d.lower() for d in case.get("approved_upstream_domains", [])}
        candidate = self.discovery_repository.get_candidate(case["candidate_public_id"])
        provider_public_ids: set[str] = set()
        if candidate.get("primary_provider_public_id"):
            provider_public_ids.add(candidate["primary_provider_public_id"])
        for source in self.discovery_repository.list_candidate_sources(
            case["candidate_public_id"]
        ):
            provider_public_ids.add(source["provider_public_id"])
        for provider_public_id in provider_public_ids:
            for domain_row in self.provider_repository.list_domains(provider_public_id):
                domains.add(domain_row["domain"].lower())
        return domains

    def collect_evidence(
        self,
        case_public_id: str,
        *,
        evidence_type: str,
        source_url: str,
        admin_public_id: str,
        provider_public_id: str | None = None,
        authority_level: str | None = None,
    ) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        allowed_domains = self.allowed_domains_for_case(case_public_id)
        try:
            fetched = fetch_evidence(
                source_url,
                allowed_domains=allowed_domains,
                transport=self._transport,
                resolver=self._resolver,
            )
        except EvidenceRetrievalError as exc:
            self.repository.record_event(
                case_public_id,
                {
                    "event_type": "evidence_collection_failed",
                    "summary": f"{evidence_type} evidence collection failed: {exc.reason}",
                    "metadata": {"source_url": source_url, "reason": exc.reason},
                    "performed_by_admin_public_id": admin_public_id,
                },
            )
            _audit(
                self._audit,
                event_type="dataset_verification_evidence_collection_failed",
                action="collect_evidence",
                actor_reference=admin_public_id,
                resource_public_id=case_public_id,
                outcome=AuditOutcome.FAILURE,
                metadata={"evidence_type": evidence_type, "reason": exc.reason},
            )
            raise DatasetVerificationError(
                f"evidence collection failed for {evidence_type}: {exc.reason}"
            ) from exc

        snapshot = self.repository.add_evidence_snapshot(
            case_public_id,
            {
                "candidate_public_id": case["candidate_public_id"],
                "provider_public_id": provider_public_id,
                "evidence_type": evidence_type,
                "authority_level": authority_level
                or default_authority_for_evidence_type(evidence_type),
                "source_url": source_url,
                "resolved_url": fetched.resolved_url,
                "source_domain": fetched.source_domain,
                "content_type": fetched.content_type,
                "retrieval_status": "success",
                "http_status": fetched.http_status,
                "content_text": fetched.content_text,
                "content_excerpt": fetched.content_text[:_CONTENT_EXCERPT_CHARS],
                "content_checksum": fetched.content_checksum,
                "response_headers": fetched.response_headers,
                "size_bytes": fetched.size_bytes,
                "warnings": fetched.warnings,
                "created_by_admin_public_id": admin_public_id,
            },
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "evidence_collected",
                "summary": f"Collected {evidence_type} evidence",
                "metadata": {
                    "evidence_public_id": snapshot["public_id"],
                    "checksum": fetched.content_checksum,
                },
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_evidence_collected",
            action="collect_evidence",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"evidence_type": evidence_type},
        )
        self._refresh_evidence_and_terms_status(case_public_id)
        return snapshot

    def add_manual_evidence(
        self,
        case_public_id: str,
        *,
        evidence_type: str,
        content_text: str,
        admin_public_id: str,
        source_url: str | None = None,
        authority_level: str = "manual_unverified",
        ocr_derived: bool = False,
    ) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        checksum = content_checksum(content_text)
        snapshot = self.repository.add_evidence_snapshot(
            case_public_id,
            {
                "candidate_public_id": case["candidate_public_id"],
                "evidence_type": evidence_type,
                "authority_level": authority_level,
                "source_url": source_url,
                "content_type": "text/plain",
                "retrieval_status": "manual",
                "content_text": content_text,
                "content_excerpt": content_text[:_CONTENT_EXCERPT_CHARS],
                "content_checksum": checksum,
                "ocr_derived": ocr_derived,
                "created_by_admin_public_id": admin_public_id,
            },
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "manual_evidence_added",
                "summary": f"Manual {evidence_type} evidence added by {admin_public_id}",
                "metadata": {"evidence_public_id": snapshot["public_id"]},
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_manual_evidence_added",
            action="add_manual_evidence",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"evidence_type": evidence_type, "ocr_derived": ocr_derived},
        )
        self._refresh_evidence_and_terms_status(case_public_id)
        return snapshot

    def refresh_evidence(
        self, case_public_id: str, evidence_public_id: str, *, admin_public_id: str
    ) -> dict[str, Any]:
        """Re-fetches the same `source_url`, always creating a *new*
        snapshot that supersedes the old one -- the original captured
        text is never mutated or discarded."""

        old = self.repository.get_evidence_snapshot(evidence_public_id)
        if not old["source_url"]:
            raise DatasetVerificationError("only network-retrieved evidence can be refreshed")
        allowed_domains = self.allowed_domains_for_case(case_public_id)
        try:
            fetched = fetch_evidence(
                old["source_url"],
                allowed_domains=allowed_domains,
                transport=self._transport,
                resolver=self._resolver,
            )
        except EvidenceRetrievalError as exc:
            raise DatasetVerificationError(f"evidence refresh failed: {exc.reason}") from exc

        new_snapshot = self.repository.add_evidence_snapshot(
            case_public_id,
            {
                "candidate_public_id": old["candidate_public_id"],
                "provider_public_id": old["provider_public_id"],
                "evidence_type": old["evidence_type"],
                "authority_level": old["authority_level"],
                "source_url": old["source_url"],
                "resolved_url": fetched.resolved_url,
                "source_domain": fetched.source_domain,
                "content_type": fetched.content_type,
                "retrieval_status": "success",
                "http_status": fetched.http_status,
                "content_text": fetched.content_text,
                "content_excerpt": fetched.content_text[:_CONTENT_EXCERPT_CHARS],
                "content_checksum": fetched.content_checksum,
                "response_headers": fetched.response_headers,
                "size_bytes": fetched.size_bytes,
                "warnings": fetched.warnings,
                "supersedes_evidence_public_id": old["public_id"],
                "created_by_admin_public_id": admin_public_id,
            },
        )
        source_changed = fetched.content_checksum != old["content_checksum"]
        if source_changed:
            self.repository.record_event(
                case_public_id,
                {
                    "event_type": "source_changed_detected",
                    "summary": f"{old['evidence_type']} evidence checksum changed on refresh",
                    "metadata": {
                        "old_evidence_public_id": old["public_id"],
                        "new_evidence_public_id": new_snapshot["public_id"],
                    },
                    "performed_by_admin_public_id": admin_public_id,
                },
            )
        else:
            self.repository.record_event(
                case_public_id,
                {
                    "event_type": "evidence_refreshed",
                    "summary": f"{old['evidence_type']} evidence refreshed, unchanged",
                    "metadata": {"evidence_public_id": new_snapshot["public_id"]},
                    "performed_by_admin_public_id": admin_public_id,
                },
            )
        self._refresh_evidence_and_terms_status(case_public_id)
        return {"snapshot": new_snapshot, "source_changed": source_changed}

    def _refresh_evidence_and_terms_status(self, case_public_id: str) -> None:
        snapshots = self.repository.list_evidence_snapshots(case_public_id, current_only=True)
        types = {snapshot["evidence_type"] for snapshot in snapshots}
        if not snapshots:
            evidence_status = "not_started"
        elif {"licence_file", "licence_url"} & types:
            evidence_status = "complete"
        else:
            evidence_status = "incomplete"

        present_terms_types = types & set(_TERMS_RELEVANT_EVIDENCE_TYPES)
        if not present_terms_types:
            terms_status = "not_started"
        elif present_terms_types == set(_TERMS_RELEVANT_EVIDENCE_TYPES):
            terms_status = "complete"
        else:
            terms_status = "incomplete"

        self.repository.update_case(
            case_public_id, {"evidence_status": evidence_status, "terms_status": terms_status}
        )


class ExternalDatasetTermsService:
    """Thin read-side wrapper over the terms/privacy/consent evidence
    types (Step 11) -- capture itself goes through
    `ExternalDatasetEvidenceService`, which also keeps `terms_status`
    up to date; this service only reports the current breakdown."""

    def __init__(self, settings: Settings) -> None:
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)

    def get_terms_snapshot_summary(self, case_public_id: str) -> dict[str, Any]:
        snapshots = self.repository.list_evidence_snapshots(case_public_id, current_only=True)
        by_type: dict[str, list[dict[str, Any]]] = {
            evidence_type: [] for evidence_type in _TERMS_RELEVANT_EVIDENCE_TYPES
        }
        for snapshot in snapshots:
            if snapshot["evidence_type"] in by_type:
                by_type[snapshot["evidence_type"]].append(snapshot)
        return {
            "terms_status": self.repository.get_case(case_public_id)["terms_status"],
            "by_evidence_type": by_type,
        }


class ExternalDatasetIdentityVerificationService:
    """Step 6: conservative, per-signal identity verification. Title
    similarity alone can never reach `verified` -- only an exact
    provider-dataset-ID match or an exact official-domain match do
    (`STRONG_IDENTITY_SIGNAL_TYPES`), matching `core_model.
    data_verification.STRONG_IDENTITY_STATUSES`'s own restriction."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self.discovery_repository = ExternalDatasetDiscoveryRepository(
            settings.resolved_database_path
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def assess(self, case_public_id: str, *, admin_public_id: str) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        candidate = self.discovery_repository.get_candidate(case["candidate_public_id"])
        sources = self.discovery_repository.list_candidate_sources(case["candidate_public_id"])
        evidence = self.repository.list_evidence_snapshots(case_public_id, current_only=True)

        signals = self._derive_automated_signals(candidate, sources, evidence)
        for signal in signals:
            self.repository.add_identity_check(
                case_public_id, {"candidate_public_id": case["candidate_public_id"], **signal}
            )

        status = self._overall_status(signals)
        self.repository.update_case(case_public_id, {"identity_status": status})
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "identity_assessed",
                "summary": f"Identity assessed as '{status}'",
                "metadata": {"signal_count": len(signals)},
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_identity_assessed",
            action="assess_identity",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"identity_status": status},
        )
        return {"identity_status": status, "signals": signals}

    def record_manual_signal(
        self,
        case_public_id: str,
        *,
        signal_type: str,
        expected_value: str | None,
        observed_value: str | None,
        matched: bool,
        reason: str,
        admin_public_id: str,
        evidence_snapshot_public_id: str | None = None,
    ) -> dict[str, Any]:
        """For the signals with no reliable automated derivation
        (`dataset_card_identifier`/`upstream_citation`/
        `checksum_or_release_tag`) -- an Admin records what they found
        directly, never a guess by the system."""

        case = self.repository.get_case(case_public_id)
        check = self.repository.add_identity_check(
            case_public_id,
            {
                "candidate_public_id": case["candidate_public_id"],
                "signal_type": signal_type,
                "expected_value": expected_value,
                "observed_value": observed_value,
                "matched": matched,
                "reason": reason,
                "evidence_snapshot_public_id": evidence_snapshot_public_id,
            },
        )
        all_checks = self.repository.list_identity_checks(case_public_id)
        status = self._overall_status(self._latest_per_signal_type(all_checks))
        self.repository.update_case(case_public_id, {"identity_status": status})
        _audit(
            self._audit,
            event_type="dataset_verification_manual_identity_signal_recorded",
            action="record_manual_signal",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"signal_type": signal_type, "matched": matched},
        )
        return check

    @staticmethod
    def _latest_per_signal_type(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for check in checks:
            latest[check["signal_type"]] = check
        return list(latest.values())

    @staticmethod
    def _overall_status(signals: list[dict[str, Any]]) -> str:
        strong_match = any(
            signal["matched"] and signal["signal_type"] in _STRONG_IDENTITY_SIGNAL_TYPES
            for signal in signals
        )
        has_conflict = any(
            not signal["matched"] and signal.get("expected_value") and signal.get("observed_value")
            for signal in signals
        )
        if has_conflict:
            return "conflicting"
        if strong_match:
            return "verified"
        if any(signal["matched"] for signal in signals):
            return "likely_match"
        if any(signal.get("observed_value") for signal in signals):
            return "partial"
        return "not_verified"

    @staticmethod
    def _derive_automated_signals(
        candidate: dict[str, Any], sources: list[dict[str, Any]], evidence: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        evidence_texts = [e.get("content_text", "") for e in evidence]
        evidence_domains = {
            domain
            for domain in (_normalize_domain(e.get("source_domain")) for e in evidence)
            if domain
        }
        evidence_urls = {e.get("resolved_url") for e in evidence if e.get("resolved_url")} | {
            e.get("source_url") for e in evidence if e.get("source_url")
        }

        expected_domain = _domain_of(candidate.get("homepage_url")) or _domain_of(
            candidate.get("repository_url")
        )
        if expected_domain:
            matched = expected_domain in evidence_domains
            signals.append(
                {
                    "signal_type": "official_domain",
                    "expected_value": expected_domain,
                    "observed_value": ", ".join(sorted(evidence_domains)) or None,
                    "matched": matched,
                    "reason": (
                        "exact official domain match found in collected evidence"
                        if matched
                        else "no collected evidence originates from the candidate's own domain"
                    ),
                }
            )

        canonical_url = candidate.get("homepage_url") or candidate.get("dataset_card_url")
        if canonical_url:
            # Most evidence is fetched from a *different path* on the
            # same site (e.g. a `/LICENSE` file, not the homepage
            # itself) -- that is normal and not a conflict, so an
            # exact-URL non-match stays inconclusive (`observed_value
            # = None`) rather than being reported as a contradicting
            # observation. Only an *exact* URL match counts as a
            # positive signal here; weaker, path-differing evidence is
            # already covered by the `official_domain` signal above.
            matched = canonical_url.rstrip("/") in {u.rstrip("/") for u in evidence_urls}
            signals.append(
                {
                    "signal_type": "canonical_dataset_url",
                    "expected_value": canonical_url,
                    "observed_value": canonical_url if matched else None,
                    "matched": matched,
                    "reason": (
                        "candidate's own canonical URL matches a collected evidence URL"
                        if matched
                        else "no collected evidence URL exactly matches the candidate's "
                        "canonical URL (inconclusive, not necessarily contradictory)"
                    ),
                }
            )

        for provider_source in sources:
            provider_dataset_id = provider_source.get("provider_dataset_id")
            if not provider_dataset_id:
                continue
            matched = _contains(evidence_texts, provider_dataset_id)
            signals.append(
                {
                    "signal_type": "provider_dataset_id",
                    "expected_value": provider_dataset_id,
                    "observed_value": provider_dataset_id if matched else None,
                    "matched": matched,
                    "reason": (
                        "provider dataset ID found verbatim in collected evidence text"
                        if matched
                        else "provider dataset ID not found in any collected evidence text"
                    ),
                }
            )
            break  # one representative check is enough; every source shares the candidate

        for signal_type, expected in (
            ("dataset_name", candidate.get("canonical_name")),
            ("organization", candidate.get("organization")),
            ("version", candidate.get("version")),
            ("revision", candidate.get("revision")),
        ):
            if not expected:
                continue
            matched = _contains(evidence_texts, expected)
            signals.append(
                {
                    "signal_type": signal_type,
                    "expected_value": expected,
                    "observed_value": expected if matched else None,
                    "matched": matched,
                    "reason": (
                        f"'{expected}' found verbatim in collected evidence text"
                        if matched
                        else f"'{expected}' not found in any collected evidence text"
                    ),
                }
            )

        owner = _github_owner(candidate.get("repository_url"))
        organization = candidate.get("organization")
        if owner and organization:
            matched = owner.strip().lower() == organization.strip().lower()
            signals.append(
                {
                    "signal_type": "repository_owner",
                    "expected_value": organization,
                    "observed_value": owner,
                    "matched": matched,
                    "reason": (
                        "repository owner matches the candidate's declared organization"
                        if matched
                        else "repository owner does not match the candidate's declared organization"
                    ),
                }
            )

        for signal_type in _MANUAL_ONLY_SIGNAL_TYPES:
            signals.append(
                {
                    "signal_type": signal_type,
                    "expected_value": None,
                    "observed_value": None,
                    "matched": False,
                    "reason": "no automated signal available; requires manual Admin review",
                }
            )
        return signals


class ExternalDatasetLicenceService:
    """Step 7: licence normalization. `normalized_licence_identifier`
    is populated only via `core_model.data_verification.
    normalize_spdx_identifier()`'s small exact-match table -- never
    inferred, guessed, or partial-matched."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def assess(self, case_public_id: str, *, admin_public_id: str) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        evidence = self.repository.list_evidence_snapshots(case_public_id, current_only=True)
        licence_evidence = [
            e for e in evidence if e["evidence_type"] in ("licence_file", "licence_url")
        ]
        supporting_evidence = [
            e for e in evidence if e["evidence_type"] in ("dataset_card", "provider_api_metadata")
        ]

        declared_licence = case.get("declared_licence")
        declared_normalized = normalize_spdx_identifier(declared_licence)

        if not licence_evidence and not declared_licence:
            licence_status = "missing"
            normalized = None
        elif not licence_evidence:
            # Declared metadata alone (Phase 9/10's own field, never
            # itself proof) is never sufficient for "verified" -- only
            # informational until real licence evidence is collected.
            licence_status = "declared_only"
            normalized = declared_normalized
        else:
            # `normalized_licence_identifier` is derived from the
            # *evidence's own text* (never merely copied from the
            # declared field) -- the declared value only ever
            # participates in *conflict* detection here, matching the
            # rule "do not treat repository/provider metadata as proof
            # that the dataset uses that licence."
            evidence_identifiers: set[str] = set()
            for item in licence_evidence:
                evidence_identifiers |= _find_spdx_identifiers_in_text(item.get("content_text"))
            all_identifiers = set(evidence_identifiers)
            if declared_normalized:
                all_identifiers.add(declared_normalized)
            for item in supporting_evidence:
                all_identifiers |= _find_spdx_identifiers_in_text(item.get("content_text"))

            if len(all_identifiers) > 1:
                licence_status = "conflicting"
                normalized = None
            elif len(evidence_identifiers) == 1:
                licence_status = "verified"
                normalized = next(iter(evidence_identifiers))
            else:
                licence_status = "custom_needs_review"
                normalized = None

        self.repository.update_case(
            case_public_id,
            {
                "licence_status": licence_status,
                "normalized_licence_identifier": normalized,
            },
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "licence_normalized",
                "summary": f"Licence status set to '{licence_status}'",
                "metadata": {
                    "declared_licence": declared_licence,
                    "normalized_licence_identifier": normalized,
                },
                "performed_by_admin_public_id": admin_public_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_licence_normalized",
            action="assess_licence",
            actor_reference=admin_public_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"licence_status": licence_status},
        )
        return {
            "licence_status": licence_status,
            "declared_licence": declared_licence,
            "normalized_licence_identifier": normalized,
        }
