"""Phase 20 Step 3 -- `TrustedWebAnswerService`: orchestrates the
bounded Trusted Web pipeline (Search -> Policy -> Provider -> Result
Normalization -> Candidate Filtering -> Source Trust Evaluation ->
Optional Safe Fetch -> Content Extraction -> Injection Filtering ->
Freshness Evaluation -> Evidence Selection -> Conflict Detection ->
Grounded Answer Generation -> Citation Validation).

Contains zero training/RAG-ingestion logic -- a pure, request-scoped
orchestrator over already-built components, mirroring
`PublicChatRoutingService`'s own shape. Every real network call
(search, fetch) goes through the already-injectable transports those
components define, so this service is fully testable without a real
network call.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from urllib.parse import urlparse

from backend.core.config import Settings
from backend.database.repositories.trusted_web_tool_gateway import TrustedWebToolGatewayRepository
from backend.services.dataset_verification_transport import (
    EvidenceRetrievalError,
    default_evidence_http_transport,
    default_resolver,
)
from backend.services.public_chat_rate_limiter import check_rate_limit
from backend.services.safe_web_fetcher import FetchBlockedError, fetch_page
from backend.services.trusted_web_policy_service import (
    category_rule,
    domain_trust_level,
    load_policy,
)
from backend.services.web_evidence_selection_service import select_evidence
from backend.services.web_search_cache import cache_key, get_cached, set_cached
from backend.services.web_search_provider import (
    ProviderQuotaExceededError,
    ProviderUnavailableError,
    build_configured_provider,
    default_search_transport,
)
from core_model.corpus.pii_detection import detect_pii, redact_pii
from core_model.corpus.secret_detection import detect_secrets
from core_model.public_chat.web_answer_template import generate_grounded_answer
from core_model.public_chat.web_injection_guard import assess_web_content_injection
from core_model.web_search import VERIFICATION_LEVELS
from core_model.web_search.conflict_detection import ConflictEvidenceItem, detect_conflict
from core_model.web_search.freshness import evaluate_freshness, overall_freshness
from core_model.web_search.provider_contract import SearchOptions
from core_model.web_search.verification import evaluate_verification_level, meets_required_level

_REAL_TIME_CACHE_TTL_SECONDS = 30.0
_CONTENT_VERIFIED_RANK = VERIFICATION_LEVELS.index("content_verified")
_SECRET_EXCERPT_PLACEHOLDER = "[EXCERPT_WITHHELD_SECRET_PATTERN_DETECTED]"


def _privacy_safe_excerpt(excerpt: str) -> str:
    """Step 16's own retention requirement ("scan for PII/secrets")
    applied to `qualifying` excerpts *before* they reach either
    consumer -- the public reply text (`generate_grounded_answer()`
    quotes `supporting_excerpt` verbatim) and the append-only
    `excerpt_redacted` DB column both derive from this one sanitized
    value, so a page containing incidental PII (e.g. a contact e-mail
    on an official page) is never quoted back to the public user
    either. Mirrors `KnowledgeGapPrivacyService`'s exact block-then-
    redact order (Phase 19): a secret pattern withholds the excerpt
    entirely (never partially redacted -- a half-redacted API key is
    still a leak), otherwise PII is redacted in place, never both
    applied to the same text."""

    secrets = detect_secrets(excerpt)
    if secrets["status"] == "blocked":
        return _SECRET_EXCERPT_PLACEHOLDER
    pii = detect_pii(excerpt)
    if pii["total_findings"]:
        return redact_pii(excerpt, pii["findings"])
    return excerpt


def _apply_cross_source_confirmation(candidates: list[dict]) -> list[dict]:
    """Step 11's `cross_source_verified`/`official_source_verified`
    levels are otherwise unreachable -- `_gather_candidates()` scores
    each candidate independently and cannot know how many *other*
    independent domains reached the same level. This runs once, after
    all candidates are gathered: if two or more genuinely distinct
    domains each independently reached at least `content_verified`,
    each of those candidates is corroborated by the other(s) and is
    bumped one level (two, if its own trust level is `official`) --
    never for a lone source, and never for a domain confirming itself
    via a second page on the same site."""

    domains_at_or_above_content_verified = {
        urlparse(candidate["source_url"]).hostname
        for candidate in candidates
        if VERIFICATION_LEVELS.index(candidate["verification_level"]) >= _CONTENT_VERIFIED_RANK
    }
    if len(domains_at_or_above_content_verified) < 2:
        return candidates

    updated: list[dict] = []
    for candidate in candidates:
        if VERIFICATION_LEVELS.index(candidate["verification_level"]) < _CONTENT_VERIFIED_RANK:
            updated.append(candidate)
            continue
        new_level = (
            "official_source_verified"
            if candidate["source_trust_level"] == "official"
            else "cross_source_verified"
        )
        updated.append({**candidate, "verification_level": new_level})
    return updated


@dataclass(frozen=True)
class WebAnswerResult:
    status: str
    reply_text: str | None
    citations: list[dict]
    freshness_status: str | None
    conflict_status: str
    reason_codes: tuple[str, ...]
    search_event_public_id: str | None
    limitations: list[str] = field(default_factory=list)


class TrustedWebAnswerService:
    def __init__(
        self,
        settings: Settings,
        *,
        search_transport=default_search_transport,
        fetch_transport=default_evidence_http_transport,
        fetch_resolver=default_resolver,
    ) -> None:
        """`search_transport`/`fetch_transport`/`fetch_resolver` are
        injectable purely for tests -- mirroring every other real-I/O
        module in this codebase (`fetch_evidence`,
        `stream_download_to_file`, `default_search_transport` itself),
        production callers never pass them, so the real network
        implementations are always used outside tests."""

        self.settings = settings
        self.repository = TrustedWebToolGatewayRepository(settings.resolved_database_path)
        self._search_transport = search_transport
        self._fetch_transport = fetch_transport
        self._fetch_resolver = fetch_resolver

    def _build_provider(self):
        return build_configured_provider(
            provider_name=self.settings.trusted_web_provider_name,
            base_url=self.settings.trusted_web_provider_base_url,
            api_key=self.settings.trusted_web_provider_api_key,
            api_key_header=self.settings.trusted_web_provider_api_key_header,
            timeout_seconds=5.0,
            transport=self._search_transport,
        )

    def is_available(self) -> bool:
        try:
            load_policy()
        except Exception:  # noqa: BLE001 -- any policy load failure means unavailable
            return False
        return self._build_provider().health_check().healthy

    def answer(
        self,
        *,
        query_text: str,
        web_category: str,
        language: str,
        answer_language: str,
        freshness: str,
        request_id: str,
    ) -> WebAnswerResult:
        started = time.perf_counter()

        try:
            policy = load_policy()
        except Exception:  # noqa: BLE001
            return self._insufficient("web_provider_unavailable", None)

        if not check_rate_limit(
            "web_search",
            max_requests=self.settings.trusted_web_search_rate_limit_max_requests,
            window_seconds=self.settings.trusted_web_search_rate_limit_window_seconds,
        ):
            return self._insufficient("web_quota_exceeded", None)

        provider = self._build_provider()
        health = provider.health_check()
        if not health.healthy:
            return self._insufficient("web_provider_unavailable", None)

        query_hash = hashlib.sha256(query_text.strip().lower().encode("utf-8")).hexdigest()
        freshness_class = "real_time" if freshness == "real_time" else "standard"
        key = cache_key(
            normalized_query=query_hash,
            language=language,
            freshness_class=freshness_class,
            policy_version=policy["policy_version"],
            provider_name=provider.provider_name,
        )
        cached = get_cached(key)
        if cached is not None:
            return cached

        max_results = policy["maximum_results"]
        try:
            search_results = provider.search(
                query_text, SearchOptions(max_results=max_results, language=language)
            )
        except ProviderQuotaExceededError:
            result = self._insufficient("web_quota_exceeded", None)
            return result
        except ProviderUnavailableError:
            result = self._insufficient("web_provider_unavailable", None)
            return result

        if not search_results:
            result = self._insufficient("web_no_trusted_source", None)
            return result

        candidates, fetch_events = self._gather_candidates(
            search_results=search_results,
            policy=policy,
            web_category=web_category,
            query_text=query_text,
        )
        candidates = _apply_cross_source_confirmation(candidates)

        if not candidates:
            result = self._insufficient("web_no_trusted_source", None)
            self._audit_search_event(
                request_id,
                query_hash,
                web_category,
                provider.provider_name,
                policy["policy_version"],
                "no_trusted_source",
                0,
                "no_conflict",
                None,
                started,
            )
            for fetch_event in fetch_events:
                self.repository.record_fetch_event(None, fetch_event)
            return result

        max_excerpt_chars = policy["content_limits"]["max_excerpt_chars"]
        selected = select_evidence(
            query=query_text, candidates=candidates, max_excerpt_chars=max_excerpt_chars
        )

        rule = category_rule(policy, web_category)
        required_level = rule["min_verification_level"]
        qualifying = [
            replace(item, supporting_excerpt=_privacy_safe_excerpt(item.supporting_excerpt))
            for item in selected
            if meets_required_level(item.verification_level, required_level)
        ]

        if not qualifying:
            result = self._insufficient("web_evidence_insufficient", None)
            self._audit_search_event(
                request_id,
                query_hash,
                web_category,
                provider.provider_name,
                policy["policy_version"],
                "evidence_insufficient",
                len(selected),
                "no_conflict",
                None,
                started,
            )
            for fetch_event in fetch_events:
                self.repository.record_fetch_event(None, fetch_event)
            return result

        conflict_items = [
            ConflictEvidenceItem(
                source_url=item.source_url,
                trust_level=item.source_trust_level,
                freshness_status=item.freshness_status,
                excerpt=item.supporting_excerpt,
            )
            for item in qualifying
        ]
        conflict = detect_conflict(conflict_items)
        if conflict.status in ("material_conflict", "unresolved_conflict"):
            qualifying = [
                replace(item, support_type="contradicts")
                if item.source_url in conflict.conflicting_source_urls
                else item
                for item in qualifying
            ]

        reply_text, limitations = generate_grounded_answer(
            evidence_items=qualifying,
            conflict_status=conflict.status,
            answer_language=answer_language,
        )

        overall = overall_freshness([item.freshness_status for item in qualifying])
        search_event = self._audit_search_event(
            request_id,
            query_hash,
            web_category,
            provider.provider_name,
            policy["policy_version"],
            "success",
            len(selected),
            conflict.status,
            overall,
            started,
        )
        for candidate_item in qualifying:
            self.repository.record_source_evidence(
                search_event["public_id"],
                {
                    "source_url_normalized": candidate_item.source_url,
                    "source_domain": candidate_item.source_url.split("/")[2]
                    if "//" in candidate_item.source_url
                    else candidate_item.source_url,
                    "title": candidate_item.source_title,
                    "published_at": None,
                    "updated_at": None,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "trust_level": candidate_item.source_trust_level,
                    "verification_level": candidate_item.verification_level,
                    "freshness_status": candidate_item.freshness_status,
                    "support_status": candidate_item.support_type,
                    "content_hash": hashlib.sha256(
                        candidate_item.supporting_excerpt.encode("utf-8")
                    ).hexdigest(),
                    # Already privacy-scanned above (`qualifying` is built via
                    # `_privacy_safe_excerpt()`) -- both the public reply text
                    # and this stored excerpt come from the same sanitized value.
                    "excerpt_redacted": candidate_item.supporting_excerpt,
                },
            )
        for fetch_event in fetch_events:
            self.repository.record_fetch_event(search_event["public_id"], fetch_event)

        citations = [
            {
                "citation_id": f"web:{search_event['public_id']}:{index}",
                "source_type": "web",
                "title": item.source_title,
                "document_or_site_name": item.source_title,
                "page_or_section": None,
                "published_at": None,
                "updated_at": None,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "verification_status": item.verification_level,
                "support_status": item.support_type,
                "url": item.source_url,
            }
            for index, item in enumerate(qualifying)
        ]

        result = WebAnswerResult(
            status="success",
            reply_text=reply_text,
            citations=citations,
            freshness_status=overall,
            conflict_status=conflict.status,
            reason_codes=("web_answer_grounded",)
            if conflict.status == "no_conflict"
            else ("web_answer_grounded", "source_conflict"),
            search_event_public_id=search_event["public_id"],
            limitations=limitations,
        )

        ttl = (
            _REAL_TIME_CACHE_TTL_SECONDS
            if freshness_class == "real_time"
            else self.settings.trusted_web_search_cache_ttl_seconds
        )
        set_cached(key, result, ttl_seconds=ttl)
        return result

    def _gather_candidates(
        self, *, search_results, policy, web_category, query_text
    ) -> tuple[list[dict], list[dict]]:
        candidates: list[dict] = []
        fetch_events: list[dict] = []
        fetch_budget = policy["maximum_fetches"]
        fetches_used = 0

        for search_result in search_results:
            trust_level = domain_trust_level(policy, search_result.display_domain)
            if trust_level == "blocked":
                continue

            fetch_ok = trust_level in policy["fetch_allowed"] and fetches_used < fetch_budget
            content_relevant_hint = True

            if fetch_ok and self._fetch_allowed_by_rate_limit(search_result.display_domain):
                fetches_used += 1
                try:
                    page = fetch_page(
                        search_result.url,
                        allowed_domain=search_result.display_domain,
                        max_response_bytes=policy["content_limits"]["max_response_bytes"],
                        timeout_seconds=policy["timeouts"]["fetch_seconds"],
                        transport=self._fetch_transport,
                        resolver=self._fetch_resolver,
                    )
                except (FetchBlockedError, EvidenceRetrievalError) as exc:
                    reason = getattr(exc, "reason", type(exc).__name__)
                    fetch_events.append(
                        {
                            "url_domain": search_result.display_domain,
                            "http_status": None,
                            "content_type": None,
                            "outcome": "blocked",
                            "block_reason": reason,
                            "injection_status": None,
                            "bytes_fetched": 0,
                        }
                    )
                    continue

                injection = assess_web_content_injection(page.main_text)
                fetch_events.append(
                    {
                        "url_domain": page.source_domain,
                        "http_status": page.http_status,
                        "content_type": page.content_type,
                        "outcome": "success",
                        "block_reason": None,
                        "injection_status": injection["injection_status"],
                        "bytes_fetched": len(page.raw_bytes),
                    }
                )
                if injection["injection_status"] == "blocked":
                    continue

                freshness_status = evaluate_freshness(
                    published_at=page.published_at,
                    updated_at=page.updated_at,
                    category=web_category,
                    freshness_thresholds=policy["freshness_thresholds"],
                )
                verification_level = evaluate_verification_level(
                    trust_level=trust_level,
                    url_valid=True,
                    fetch_attempted=True,
                    fetch_succeeded=True,
                    content_relevant=content_relevant_hint,
                    freshness_status=freshness_status,
                    injection_status=injection["injection_status"],
                    cross_source_confirmed=False,
                )
                candidates.append(
                    {
                        "evidence_id": f"fetch:{page.source_domain}",
                        "source_url": page.resolved_url,
                        "source_title": page.title or search_result.title,
                        "text": page.main_text,
                        "freshness_status": freshness_status,
                        "verification_level": verification_level,
                        "source_trust_level": trust_level,
                    }
                )
                continue

            snippet_ok = (
                trust_level in policy["snippet_only_allowed"]
                or trust_level in policy["fetch_allowed"]
            )
            if snippet_ok:
                freshness_status = evaluate_freshness(
                    published_at=search_result.published_at,
                    updated_at=search_result.updated_at,
                    category=web_category,
                    freshness_thresholds=policy["freshness_thresholds"],
                )
                verification_level = evaluate_verification_level(
                    trust_level=trust_level,
                    url_valid=True,
                    fetch_attempted=False,
                    fetch_succeeded=False,
                    content_relevant=content_relevant_hint,
                    freshness_status=freshness_status,
                    injection_status="clean",
                    cross_source_confirmed=False,
                )
                candidates.append(
                    {
                        "evidence_id": f"snippet:{search_result.result_id}",
                        "source_url": search_result.url,
                        "source_title": search_result.title,
                        "text": search_result.snippet,
                        "freshness_status": freshness_status,
                        "verification_level": verification_level,
                        "source_trust_level": trust_level,
                    }
                )

        return candidates, fetch_events

    def _fetch_allowed_by_rate_limit(self, domain: str) -> bool:
        if not check_rate_limit(
            "web_fetch",
            max_requests=self.settings.trusted_web_fetch_rate_limit_max_requests,
            window_seconds=self.settings.trusted_web_fetch_rate_limit_window_seconds,
        ):
            return False
        return check_rate_limit(
            f"web_fetch_domain:{domain}",
            max_requests=self.settings.trusted_web_fetch_per_domain_rate_limit_max_requests,
            window_seconds=self.settings.trusted_web_fetch_rate_limit_window_seconds,
        )

    def _audit_search_event(
        self,
        request_id,
        query_hash,
        web_category,
        provider_name,
        policy_version,
        status,
        result_count,
        conflict_status,
        overall_freshness_status,
        started,
    ) -> dict:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return self.repository.record_search_event(
            {
                "request_id": request_id,
                "query_hash": query_hash,
                "web_category": web_category,
                "provider_name": provider_name,
                "policy_version": policy_version,
                "status": status,
                "result_count": result_count,
                "conflict_status": conflict_status,
                "overall_freshness_status": overall_freshness_status,
                "latency_ms": latency_ms,
            }
        )

    def _insufficient(
        self, reason_code: str, search_event_public_id: str | None
    ) -> WebAnswerResult:
        return WebAnswerResult(
            status=reason_code,
            reply_text=None,
            citations=[],
            freshness_status=None,
            conflict_status="no_conflict",
            reason_codes=(reason_code,),
            search_event_public_id=search_event_public_id,
        )


__all__ = ["TrustedWebAnswerService", "WebAnswerResult"]
