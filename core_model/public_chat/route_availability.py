"""`PublicRouteAvailabilityService` (Step 18) -- a pure decision
function mapping a Phase 17 recommended route onto what this phase can
actually execute. It never silently substitutes an unavailable route
for an unsafe one -- an unavailable `trusted_web`/`tool` resolves to
`insufficient`, never to `core_model`.

Phase 20 makes `trusted_web`/`tool` conditionally executable (a
healthy configured search provider / a matching enabled deterministic
tool), still resolving honestly to `insufficient` whenever that
precondition isn't met -- the same shape every other conditional route
here already uses (`approved_rag`, `memory`).

DB/network-touching prerequisite checks (does an eligible production
RAG space exist? is the Web provider healthy? is a deterministic tool
enabled?) are computed by the caller (`PublicChatRoutingService`) and
passed in as plain booleans, keeping this module itself pure and
unit-testable without a database or network call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core_model.public_chat import AVAILABILITY_STATUSES, EXECUTABLE_ROUTES


@dataclass(frozen=True)
class RouteAvailabilityResult:
    recommended_route: str
    resolved_route: str
    availability_status: str
    reason_codes: tuple[str, ...]
    fallback_allowed: bool = field(default=False)


def resolve_route_availability(
    *,
    recommended_route: str,
    rag_scope_available: bool = False,
    memory_consent_given: bool = False,
    memory_policy_active: bool = False,
    memory_has_content: bool = False,
    trusted_web_available: bool = False,
    tool_available: bool = False,
) -> RouteAvailabilityResult:
    if recommended_route == "trusted_web":
        if trusted_web_available:
            return RouteAvailabilityResult(
                recommended_route=recommended_route,
                resolved_route="trusted_web",
                availability_status="executable",
                reason_codes=(),
            )
        return RouteAvailabilityResult(
            recommended_route=recommended_route,
            resolved_route="insufficient",
            availability_status="unavailable",
            reason_codes=("trusted_web_unavailable",),
            fallback_allowed=False,
        )

    if recommended_route == "tool":
        if tool_available:
            return RouteAvailabilityResult(
                recommended_route=recommended_route,
                resolved_route="tool",
                availability_status="executable",
                reason_codes=(),
            )
        return RouteAvailabilityResult(
            recommended_route=recommended_route,
            resolved_route="insufficient",
            availability_status="unavailable",
            reason_codes=("tool_unavailable",),
            fallback_allowed=False,
        )

    if recommended_route == "approved_rag":
        if rag_scope_available:
            return RouteAvailabilityResult(
                recommended_route=recommended_route,
                resolved_route="approved_rag",
                availability_status="executable",
                reason_codes=(),
            )
        return RouteAvailabilityResult(
            recommended_route=recommended_route,
            resolved_route="insufficient",
            availability_status="unavailable",
            reason_codes=("rag_scope_unavailable",),
            fallback_allowed=False,
        )

    if recommended_route == "memory":
        if not memory_consent_given:
            return RouteAvailabilityResult(
                recommended_route=recommended_route,
                resolved_route="insufficient",
                availability_status="blocked",
                reason_codes=("memory_consent_required",),
                fallback_allowed=False,
            )
        if not memory_policy_active or not memory_has_content:
            return RouteAvailabilityResult(
                recommended_route=recommended_route,
                resolved_route="insufficient",
                availability_status="unavailable",
                reason_codes=("memory_unavailable",),
                fallback_allowed=False,
            )
        return RouteAvailabilityResult(
            recommended_route=recommended_route,
            resolved_route="memory",
            availability_status="executable",
            reason_codes=(),
        )

    # core_model / clarify / refuse / insufficient -- always executable
    # as recommended; the caller still verifies a live model assignment
    # exists at execution time for core_model and reports
    # model_assignment_unavailable there if not.
    assert recommended_route in EXECUTABLE_ROUTES, (
        f"unknown recommended_route: {recommended_route!r}"
    )
    result = RouteAvailabilityResult(
        recommended_route=recommended_route,
        resolved_route=recommended_route,
        availability_status="executable",
        reason_codes=(),
    )
    assert result.availability_status in AVAILABILITY_STATUSES
    return result


__all__ = ["RouteAvailabilityResult", "resolve_route_availability"]
