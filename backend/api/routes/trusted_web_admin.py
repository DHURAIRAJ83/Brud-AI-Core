"""Phase 20 Step 29 -- Admin-only API for the Trusted Web gateway,
under `/api/admin/trusted-web`. Read-only visibility into search/
evidence/fetch/policy events plus two bounded, audited, CSRF-protected
test actions (`test-search`, `verify-source`) -- neither writes to
public-facing chat state, neither exposes provider API keys, raw page
bodies, or provider-internal payloads.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.database.repositories.trusted_web_tool_gateway import TrustedWebToolGatewayRepository
from backend.models.public_chat import MAX_MESSAGE_LENGTH
from backend.services.safe_web_fetcher import FetchBlockedError, fetch_page, validate_fetch_url
from backend.services.trusted_web_answer_service import TrustedWebAnswerService
from backend.services.trusted_web_policy_service import load_policy

router = APIRouter(
    prefix="/admin/trusted-web",
    tags=["trusted-web"],
    dependencies=[Depends(require_admin)],
)


class TestSearchRequest(DomainModel):
    query: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    web_category: str = "current_general_information"
    language: str = "en"


class VerifySourceRequest(DomainModel):
    url: str = Field(min_length=1, max_length=2000)
    allowed_domain: str = Field(min_length=1, max_length=255)


def _repository(settings: SettingsDependency) -> TrustedWebToolGatewayRepository:
    return TrustedWebToolGatewayRepository(settings.resolved_database_path)


@router.get("/overview")
async def get_overview(settings: SettingsDependency) -> dict[str, Any]:
    repo = _repository(settings)
    overview = repo.trusted_web_overview()
    overview["web_demand"] = KnowledgeGapRepository(
        settings.resolved_database_path
    ).web_demand_summary()
    return overview


@router.get("/providers")
async def get_providers(settings: SettingsDependency) -> dict[str, Any]:
    service = TrustedWebAnswerService(settings)
    provider = service._build_provider()  # noqa: SLF001 -- Admin-only, read-only introspection
    health = provider.health_check()
    return {
        "configured_provider_name": settings.trusted_web_provider_name,
        "healthy": health.healthy,
        "reason": health.reason,
        "capabilities": provider.capabilities(),
        # Never returned: api_key, base_url (may embed a key in some provider
        # configurations), raw provider payloads.
    }


@router.get("/policy")
async def get_policy() -> dict[str, Any]:
    try:
        policy = load_policy()
    except Exception as exc:  # noqa: BLE001 -- report as a structured, honest failure
        return {"available": False, "error": str(exc)}
    return {"available": True, "policy": policy}


@router.get("/search-events")
async def list_search_events(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    repo = _repository(settings)
    return {"items": repo.list_search_events(limit=limit, offset=offset)}


@router.get("/evidence")
async def list_evidence(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    repo = _repository(settings)
    return {"items": repo.list_recent_evidence(limit=limit, offset=offset)}


@router.get("/fetch-events")
async def list_fetch_events(
    settings: SettingsDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    repo = _repository(settings)
    return {"items": repo.list_fetch_events(limit=limit, offset=offset)}


@router.get("/health")
async def get_health(settings: SettingsDependency) -> dict[str, Any]:
    service = TrustedWebAnswerService(settings)
    try:
        load_policy()
        policy_ok = True
        policy_error = None
    except Exception as exc:  # noqa: BLE001
        policy_ok = False
        policy_error = str(exc)
    return {
        "provider_available": service.is_available(),
        "policy_loaded": policy_ok,
        "policy_error": policy_error,
        "external_mcp_enabled": settings.external_mcp_enabled,
    }


@router.post("/test-search")
async def test_search(
    payload: TestSearchRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    """Admin-triggered, real (bounded, rate-limited) search -> answer
    pipeline exercise -- never exposed to public users, never bypasses
    policy/SSRF checks, audited via the same `trusted_web_search_events`
    trail a genuine public request would create."""

    service = TrustedWebAnswerService(settings)
    result = service.answer(
        query_text=payload.query,
        web_category=payload.web_category,
        language=payload.language,
        answer_language=payload.language if payload.language in ("ta", "en") else "en",
        freshness="standard",
        request_id=f"admin-test:{admin.admin.public_id}",
    )
    return {
        "status": result.status,
        "reason_codes": list(result.reason_codes),
        "citation_count": len(result.citations),
        "freshness_status": result.freshness_status,
        "conflict_status": result.conflict_status,
        "search_event_public_id": result.search_event_public_id,
    }


@router.post("/verify-source")
async def verify_source(
    payload: VerifySourceRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    """Admin-triggered manual source verification -- the exact same
    SSRF-safe `validate_fetch_url`/`fetch_page` path public evidence
    gathering uses, never a raw-URL bypass. Never returns the fetched
    page body, only bounded, safe metadata."""

    try:
        validate_fetch_url(payload.url, allowed_domain=payload.allowed_domain)
    except FetchBlockedError as exc:
        return {"verified": False, "block_reason": exc.reason}

    policy = None
    try:
        policy = load_policy()
    except Exception:  # noqa: BLE001
        pass
    max_bytes = policy["content_limits"]["max_response_bytes"] if policy else 2_000_000
    timeout = policy["timeouts"]["fetch_seconds"] if policy else 5.0

    try:
        page = fetch_page(
            payload.url, allowed_domain=payload.allowed_domain,
            max_response_bytes=max_bytes, timeout_seconds=timeout,
        )
    except FetchBlockedError as exc:
        return {"verified": False, "block_reason": exc.reason}

    return {
        "verified": True,
        "resolved_url": page.resolved_url,
        "source_domain": page.source_domain,
        "http_status": page.http_status,
        "content_type": page.content_type,
        "title": page.title,
        "published_at": page.published_at,
        "updated_at": page.updated_at,
        "language": page.language,
        "warnings": page.warnings,
        "content_length_chars": len(page.main_text),
        # Never returned: page.main_text / page.raw_bytes (the fetched body itself).
    }


__all__ = ["router"]
