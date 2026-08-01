"""Phase 10 Step 5/11 (service-layer integration): owns the search
session lifecycle (`draft -> ready -> running -> partial | completed |
failed | cancelled | expired`) and the bounded execution loop that
turns a confirmed requirement into normalized, deduplicated, scored
candidates.

Every provider is called through the same bounded contract Phase 9
already established (`ConnectorConfig` + injectable `HttpTransport`,
`PER_PROVIDER_TIMEOUT_SECONDS`); a single provider's failure --
`ConnectorSearchError` or any unexpected exception -- is always caught
locally and recorded as that provider's own run outcome, never allowed
to abort the loop over the remaining providers. Nothing here downloads
a file, imports a dataset, or grants any licence/RAG/training/
commercial approval -- discovery only ever produces candidates for
human review (see
docs/data_discovery/phase10_live_dataset_discovery_plan.md).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.external_data_providers import (
    ExternalDataProviderRepository,
)
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.external_data_connectors import (
    CONNECTOR_REGISTRY,
    ConnectorConfig,
    ConnectorSearchError,
    HttpTransport,
    default_http_transport,
    get_connector,
)
from backend.services.external_data_provider_service import resolve_active_credential
from backend.services.external_dataset_deduplication_service import (
    ExternalDatasetDeduplicationService,
)
from backend.services.external_dataset_normalization_service import (
    ExternalDatasetNormalizationService,
)
from backend.services.external_dataset_scoring_service import ExternalDatasetScoringService
from core_model.data_discovery import (
    MAX_CANDIDATES_PER_SESSION,
    MAX_PROVIDERS_PER_SEARCH,
    MAX_QUERY_LENGTH,
    MAX_RESULTS_PER_PROVIDER,
    OVERALL_SEARCH_DEADLINE_SECONDS,
    PER_PROVIDER_TIMEOUT_SECONDS,
    PROVIDER_RUN_FAILURE_STATUSES,
    TERMINAL_SESSION_STATUSES,
    is_provider_searchable,
)
from core_model.data_discovery.candidate_model import DatasetSearchRequest
from core_model.data_discovery.deduplication import normalize_name

logger = logging.getLogger(__name__)

_SEARCHABLE_SESSION_STATUSES = ("draft", "ready")
# A session that finished searching (completed/partial/failed) is still
# an open research workspace -- an admin can keep curating it (add a
# manual candidate, build a comparison) after the automated part is
# done. Only a session the admin explicitly cancelled, or one that
# expired, is truly closed to further curation.
_ABANDONED_SESSION_STATUSES = ("cancelled", "expired")


class ExternalDatasetSearchError(BrudError):
    status_code = 422
    code = "external_dataset_search_rejected"


def _now_sql_timestamp() -> str:
    """Matches SQLite's own `CURRENT_TIMESTAMP` format (UTC,
    `YYYY-MM-DD HH:MM:SS`) so a Python-computed timestamp column never
    looks different from a DB-defaulted one."""

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    event_type: str,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    resource_type: str = "external_dataset_search_session",
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
                resource_type=resource_type,
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("external_dataset_search_audit_write_failed", extra={"action": action})


def build_query(requirement: dict[str, Any]) -> str:
    """A deterministic, bounded query string -- the admin's own free
    text when given, otherwise the requirement's own declared tags/
    tasks/languages joined together. Never invents keywords the
    requirement did not state."""

    free_text = (requirement.get("free_text_requirement") or "").strip()
    if free_text:
        query = free_text
    else:
        parts = [
            *requirement.get("domain_tags", []),
            *requirement.get("tasks", []),
            *requirement.get("languages", []),
        ]
        query = " ".join(parts) if parts else "dataset"
    return query[:MAX_QUERY_LENGTH]


class ExternalDatasetSearchSessionService:
    """Session creation, requirement capture, and the lifecycle
    transitions that do not themselves run a search."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_session(self, *, title: str, admin_id: str) -> dict[str, Any]:
        session_code = f"discovery-{uuid4().hex[:12]}"
        session = self.repository.create_session(
            {
                "session_code": session_code,
                "title": title,
                "requested_by_admin_public_id": admin_id,
            }
        )
        self.repository.record_event(
            session["public_id"],
            {
                "event_type": "session_created",
                "summary": f"Search session created by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_dataset_search_session_created",
            action="create_session",
            actor_reference=admin_id,
            resource_public_id=session["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return session

    def get_session(self, session_public_id: str) -> dict[str, Any]:
        return self.repository.get_session(session_public_id)

    def list_sessions(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_sessions(**filters)

    def get_requirements(self, session_public_id: str) -> dict[str, Any] | None:
        return self.repository.get_requirements(session_public_id)

    def set_requirements(
        self, session_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        session = self.repository.get_session(session_public_id)
        if session["status"] not in _SEARCHABLE_SESSION_STATUSES:
            raise ExternalDatasetSearchError(
                f"requirements can only be set while the session is draft/ready "
                f"(currently '{session['status']}')"
            )
        requirements = self.repository.upsert_requirements(session_public_id, values)
        self.repository.update_session(
            session_public_id, {"status": "ready", "current_stage": "search"}
        )
        self.repository.record_event(
            session_public_id,
            {
                "event_type": "requirements_updated",
                "summary": f"Requirements updated by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_dataset_search_requirements_updated",
            action="set_requirements",
            actor_reference=admin_id,
            resource_public_id=session_public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return requirements

    def cancel_session(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        session = self.repository.get_session(session_public_id)
        if session["status"] in TERMINAL_SESSION_STATUSES:
            raise ExternalDatasetSearchError(f"session is already '{session['status']}'")
        updated = self.repository.update_session(
            session_public_id, {"status": "cancelled", "cancelled_at": _now_sql_timestamp()}
        )
        self.repository.record_event(
            session_public_id,
            {
                "event_type": "search_cancelled",
                "summary": f"Cancelled by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_dataset_search_session_cancelled",
            action="cancel_session",
            actor_reference=admin_id,
            resource_public_id=session_public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return updated


class ExternalDatasetSearchExecutionService:
    """Bounded, best-effort search execution across every currently
    searchable provider. `transport` defaults to the one real-network
    implementation in this codebase; tests always inject a mock."""

    def __init__(
        self, settings: Settings, *, transport: HttpTransport = default_http_transport
    ) -> None:
        self.settings = settings
        self.repository = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
        self.provider_repository = ExternalDataProviderRepository(settings.resolved_database_path)
        self.transport = transport
        self.normalization_service = ExternalDatasetNormalizationService()
        self.deduplication_service = ExternalDatasetDeduplicationService(self.repository)
        self.scoring_service = ExternalDatasetScoringService(self.repository)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _searchable_providers(self, requirement: dict[str, Any]) -> list[dict[str, Any]]:
        providers = self.provider_repository.list_providers(enabled=True, limit=100)
        searchable = []
        for provider in providers:
            capabilities = self.provider_repository.list_capabilities(provider["public_id"])
            has_search = any(
                c["capability_type"] == "search_datasets" and c["enabled"] for c in capabilities
            )
            if is_provider_searchable(
                enabled=provider["enabled"],
                lifecycle_status=provider["lifecycle_status"],
                has_search_capability=has_search,
                has_manual_discovery_capability=bool(provider["supports_manual_discovery"]),
            ):
                searchable.append(provider)

        excluded_codes = set(requirement.get("excluded_providers", []))
        searchable = [p for p in searchable if p["provider_code"] not in excluded_codes]
        searchable.sort(key=lambda p: p["provider_code"])

        preferred_codes = set(requirement.get("preferred_providers", []))
        if preferred_codes:
            preferred = [p for p in searchable if p["provider_code"] in preferred_codes]
            rest = [p for p in searchable if p["provider_code"] not in preferred_codes]
            searchable = preferred + rest

        return searchable[:MAX_PROVIDERS_PER_SEARCH]

    def _connector_config(self, provider: dict[str, Any]) -> ConnectorConfig:
        domains = {
            domain["domain_type"]: domain["domain"]
            for domain in self.provider_repository.list_domains(provider["public_id"])
        }
        credential_value, credential_type = resolve_active_credential(
            self.provider_repository, provider["public_id"]
        )
        return ConnectorConfig(
            provider_code=provider["provider_code"],
            domains=domains,
            credential_value=credential_value,
            credential_type=credential_type,
            timeout_seconds=PER_PROVIDER_TIMEOUT_SECONDS,
        )

    def _process_result_item(
        self, session_public_id: str, provider: dict[str, Any], item
    ) -> str:
        """Resolves dedup, persists the candidate (new/merged) and its
        source evidence, scores it, and returns the candidate's
        public_id."""

        decision = self.deduplication_service.resolve(
            session_public_id=session_public_id,
            provider_public_id=provider["public_id"],
            provider_code=provider["provider_code"],
            metadata=item,
        )
        source_fields = self.normalization_service.build_candidate_source_fields(
            item, provider_public_id=provider["public_id"]
        )
        if decision.action in ("merge_exact_source", "merge_strong_signal"):
            target_id = decision.target_candidate_public_id
            self.repository.add_candidate_source(target_id, source_fields)
            sources = self.repository.list_candidate_sources(target_id)
            distinct_providers = len({source["provider_public_id"] for source in sources})
            self.repository.update_candidate(target_id, {"provider_count": distinct_providers})
            return target_id

        candidate_fields = self.normalization_service.build_candidate_fields(item)
        candidate_fields["primary_provider_public_id"] = provider["public_id"]
        new_candidate = self.repository.create_candidate(session_public_id, candidate_fields)
        self.repository.add_candidate_source(new_candidate["public_id"], source_fields)
        if decision.action == "possible_duplicate":
            self.repository.mark_possible_duplicate(
                new_candidate["public_id"], decision.target_candidate_public_id
            )
        return new_candidate["public_id"]

    def _run_provider(
        self,
        session_public_id: str,
        provider: dict[str, Any],
        query: str,
        requirement: dict[str, Any],
        *,
        session_candidate_count: int,
        admin_id: str,
    ) -> tuple[str, int]:
        """Returns `(provider_run_status, candidates_added)`. Every
        failure mode -- an honest `ConnectorSearchError` or a truly
        unexpected exception -- is caught here so it can never abort
        the loop over the remaining providers."""

        run = self.repository.create_provider_run(
            session_public_id, {"provider_public_id": provider["public_id"], "query_used": query}
        )
        started = time.monotonic()
        try:
            config = self._connector_config(provider)
            connector_type = (
                provider["provider_code"]
                if provider["provider_code"] in CONNECTOR_REGISTRY
                else "generic_public_api"
            )
            connector = get_connector(connector_type)
            request = DatasetSearchRequest(
                query=query,
                modality=requirement.get("modality", "text"),
                languages=tuple(requirement.get("languages", [])),
                tasks=tuple(requirement.get("tasks", [])),
                intended_uses=tuple(requirement.get("intended_uses", [])),
                limit=MAX_RESULTS_PER_PROVIDER,
            )
            result = connector.search_datasets(config, self.transport, request)
        except ConnectorSearchError as error:
            latency_ms = int((time.monotonic() - started) * 1000)
            self.repository.update_provider_run(
                run["public_id"],
                {
                    "status": error.status,
                    "error_code": error.error_code,
                    "latency_ms": latency_ms,
                    "completed_at": _now_sql_timestamp(),
                },
            )
            self.repository.record_event(
                session_public_id,
                {
                    "event_type": "provider_run_failed",
                    "summary": f"{provider['provider_code']}: {error.status} ({error.error_code})",
                    "performed_by_admin_public_id": admin_id,
                },
            )
            return error.status, 0
        except Exception:
            logger.exception(
                "external_dataset_search_provider_run_unexpected_error",
                extra={"provider_code": provider["provider_code"]},
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            self.repository.update_provider_run(
                run["public_id"],
                {
                    "status": "failed",
                    "error_code": "unexpected_error",
                    "latency_ms": latency_ms,
                    "completed_at": _now_sql_timestamp(),
                },
            )
            self.repository.record_event(
                session_public_id,
                {
                    "event_type": "provider_run_failed",
                    "summary": f"{provider['provider_code']}: unexpected error",
                    "performed_by_admin_public_id": admin_id,
                },
            )
            return "failed", 0

        latency_ms = int((time.monotonic() - started) * 1000)
        items = result.items[:MAX_RESULTS_PER_PROVIDER]
        added = 0
        run_warnings: list[str] = []
        for item in items:
            if session_candidate_count + added >= MAX_CANDIDATES_PER_SESSION:
                run_warnings.append("session_candidate_cap_reached")
                break
            candidate_id = self._process_result_item(session_public_id, provider, item)
            self.scoring_service.rescore_candidate(
                candidate_id, requirement, provider_trust_status=provider["trust_status"]
            )
            added += 1

        status = "success" if added == len(items) else "partial"
        self.repository.update_provider_run(
            run["public_id"],
            {
                "status": status,
                "result_count": added,
                "latency_ms": latency_ms,
                "warnings_json": dumps_json(run_warnings),
                "completed_at": _now_sql_timestamp(),
            },
        )
        self.repository.record_event(
            session_public_id,
            {
                "event_type": "provider_run_completed",
                "summary": f"{provider['provider_code']}: {added} candidate(s) processed",
                "performed_by_admin_public_id": admin_id,
            },
        )
        return status, added

    def run_search(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        session = self.repository.get_session(session_public_id)
        requirement = self.repository.get_requirements(session_public_id)
        if requirement is None:
            raise ExternalDatasetSearchError("session has no requirements to search with yet")
        if session["status"] not in _SEARCHABLE_SESSION_STATUSES:
            raise ExternalDatasetSearchError(
                f"session status '{session['status']}' cannot be searched "
                "(must be draft/ready)"
            )

        self.repository.update_session(
            session_public_id,
            {"status": "running", "current_stage": "searching", "started_at": _now_sql_timestamp()},
        )
        self.repository.record_event(
            session_public_id,
            {
                "event_type": "search_started",
                "summary": f"Search started by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )

        providers = self._searchable_providers(requirement)
        query = build_query(requirement)
        deadline = time.monotonic() + OVERALL_SEARCH_DEADLINE_SECONDS
        session_candidate_count = len(
            self.repository.list_candidates(session_public_id, include_excluded=True)
        )

        successful = 0
        failed = 0
        warning_runs = 0
        for provider in providers:
            if time.monotonic() >= deadline:
                run = self.repository.create_provider_run(
                    session_public_id,
                    {"provider_public_id": provider["public_id"], "query_used": query},
                )
                self.repository.update_provider_run(
                    run["public_id"],
                    {
                        "status": "timeout",
                        "error_code": "overall_search_deadline_exceeded",
                        "completed_at": _now_sql_timestamp(),
                    },
                )
                self.repository.record_event(
                    session_public_id,
                    {
                        "event_type": "provider_run_failed",
                        "summary": f"{provider['provider_code']} skipped: overall search "
                        "deadline exceeded",
                        "performed_by_admin_public_id": admin_id,
                    },
                )
                failed += 1
                continue

            status, added = self._run_provider(
                session_public_id,
                provider,
                query,
                requirement,
                session_candidate_count=session_candidate_count,
                admin_id=admin_id,
            )
            session_candidate_count += added
            if status in PROVIDER_RUN_FAILURE_STATUSES:
                failed += 1
            else:
                successful += 1
                if status == "partial":
                    warning_runs += 1

        total_providers = len(providers)
        if total_providers == 0:
            final_status = "failed"
        elif successful == total_providers:
            final_status = "completed"
        elif successful > 0:
            final_status = "partial"
        else:
            final_status = "failed"

        result_count = len(
            self.repository.list_candidates(session_public_id, include_excluded=True)
        )
        updated_session = self.repository.update_session(
            session_public_id,
            {
                "status": final_status,
                "current_stage": "review",
                "provider_count": total_providers,
                "successful_provider_count": successful,
                "failed_provider_count": failed,
                "warning_count": warning_runs,
                "result_count": result_count,
                "completed_at": _now_sql_timestamp(),
            },
        )
        event_type = {
            "completed": "search_completed",
            "partial": "search_partial",
            "failed": "search_failed",
        }[final_status]
        self.repository.record_event(
            session_public_id,
            {
                "event_type": event_type,
                "summary": f"Search {final_status}: {successful}/{total_providers} provider(s) "
                f"succeeded, {result_count} candidate(s) found",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_dataset_search_completed",
            action="run_search",
            actor_reference=admin_id,
            resource_public_id=session_public_id,
            outcome=(
                AuditOutcome.SUCCESS if final_status in ("completed", "partial")
                else AuditOutcome.WARNING
            ),
            metadata={"status": final_status, "result_count": result_count},
        )
        return updated_session


class ExternalDatasetCandidateService:
    """Candidate-level read/mutation operations that don't require
    running a provider search: listing, detail (with sources+scores),
    excluding/restoring from the comparison view, and manual entry for
    a dataset an admin already knows about but no connector surfaced.
    Excluding/restoring a candidate never deletes it -- the schema's
    own delete-blocking trigger makes that structurally impossible; it
    only flips the `excluded` flag `list_candidates` filters on."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def list_candidates(
        self, session_public_id: str, *, include_excluded: bool = True
    ) -> list[dict[str, Any]]:
        return self.repository.list_candidates(session_public_id, include_excluded=include_excluded)

    def get_candidate_detail(self, candidate_public_id: str) -> dict[str, Any]:
        candidate = self.repository.get_candidate(candidate_public_id)
        return {
            **candidate,
            "sources": self.repository.list_candidate_sources(candidate_public_id),
            "scores": self.repository.list_candidate_scores(candidate_public_id),
        }

    def exclude_candidate(self, candidate_public_id: str, *, admin_id: str) -> dict[str, Any]:
        candidate = self.repository.get_candidate(candidate_public_id)
        updated = self.repository.update_candidate(candidate_public_id, {"excluded": 1})
        self.repository.record_event(
            candidate["search_session_public_id"],
            {
                "event_type": "candidate_excluded",
                "summary": f"Candidate '{candidate['canonical_name']}' excluded by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_dataset_candidate_excluded",
            action="exclude_candidate",
            actor_reference=admin_id,
            resource_public_id=candidate_public_id,
            resource_type="external_dataset_candidate",
            outcome=AuditOutcome.SUCCESS,
        )
        return updated

    def restore_candidate(self, candidate_public_id: str, *, admin_id: str) -> dict[str, Any]:
        candidate = self.repository.get_candidate(candidate_public_id)
        updated = self.repository.update_candidate(candidate_public_id, {"excluded": 0})
        self.repository.record_event(
            candidate["search_session_public_id"],
            {
                "event_type": "candidate_restored",
                "summary": f"Candidate '{candidate['canonical_name']}' restored by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_dataset_candidate_restored",
            action="restore_candidate",
            actor_reference=admin_id,
            resource_public_id=candidate_public_id,
            resource_type="external_dataset_candidate",
            outcome=AuditOutcome.SUCCESS,
        )
        return updated

    def add_manual_candidate(
        self, session_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        session = self.repository.get_session(session_public_id)
        if session["status"] in _ABANDONED_SESSION_STATUSES:
            raise ExternalDatasetSearchError(
                f"cannot add a candidate to a '{session['status']}' session"
            )
        fields = dict(values)
        fields["candidate_entry_method"] = "manual"
        fields.setdefault("normalized_name", normalize_name(fields["canonical_name"]))
        candidate = self.repository.create_candidate(session_public_id, fields)
        self.repository.record_event(
            session_public_id,
            {
                "event_type": "manual_candidate_added",
                "summary": f"Manual candidate '{candidate['canonical_name']}' added by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="external_dataset_manual_candidate_added",
            action="add_manual_candidate",
            actor_reference=admin_id,
            resource_public_id=candidate["public_id"],
            resource_type="external_dataset_candidate",
            outcome=AuditOutcome.SUCCESS,
        )
        return candidate
