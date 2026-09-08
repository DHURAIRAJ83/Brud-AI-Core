"""Phase 2/3: capability declaration, RBAC role/permission resolution, and
the single authorization decision point for Admin Assistant tool
execution.

Layering (see `run_tool()` in `admin_assistant_tools.py`, the only
caller of `authorize_tool_invocation()`):

    admin_id -> resolve_admin_role() -> permissions_for_role()
                                              |
    tool -> ToolCapability -------------------+--> authorize_tool_invocation() -> ALLOW/DENY

`ToolCapability` describes what a tool CAN do; an `AdminRole`'s
resolved `Permission` set describes what an admin MAY do. Neither, by
itself, grants authorization -- `authorize_tool_invocation()` is the
only place the two are combined into a decision. No other code should
re-implement this check (INVARIANT 3, Phase 3 design).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from backend.core.exceptions import BrudError


class ToolCapability(str, Enum):
    READ_ONLY = "read_only"
    WRITE = "write"
    PROPOSE = "propose"
    ADMIN_APPROVAL_REQUIRED = "admin_approval_required"
    SYSTEM_ONLY = "system_only"


class ToolAuthorizationError(BrudError):
    """Raised when a tool's declared capability is not authorized to
    execute in the calling context -- either because the capability
    itself has no wired execution path (Phase 2), or because the
    caller's resolved permissions do not cover it (Phase 3). Distinct
    from `ReadOnlyToolError` (422, bad params/unknown tool name): this
    is a 403 -- an authorization decision, not a validation failure."""

    status_code = 403
    code = "admin_assistant_tool_unauthorized"


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str


# --- Phase 3: RBAC role/permission model -------------------------------


class AdminRole(str, Enum):
    """Brud AI has no persisted admin role today (`AdminPublic` carries
    no role field, `admin_accounts.status` is account-lifecycle
    ['active','disabled','locked'], not a role -- confirmed by direct
    schema/model inspection). Adding a persisted role would require a
    schema migration, which this phase does not authorize (see the
    Phase 3 architecture assessment's Step 5 finding). Roles are
    therefore resolved from `Settings`-driven configuration
    (`BRUD_ADMIN_ROLE_OVERRIDES`), not a database column -- the least
    invasive correct representation available without a migration."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    AUDITOR = "auditor"
    NONE = "none"
    """Explicit zero-permission role. Never assigned by default -- it is
    the fail-closed landing spot for a `BRUD_ADMIN_ROLE_OVERRIDES` entry
    whose role name does not parse (a config typo must not fail open),
    and is available for an operator to explicitly revoke one admin's
    tool access without touching `admin_accounts.status` (which governs
    the whole account, not just Admin Assistant tools)."""


class Permission(str, Enum):
    """Kept intentionally minimal (Step 2: "do NOT implement unnecessary
    permissions merely for completeness") -- only the three permissions
    the current `ToolCapability` set can actually consult. `TOOL_PROPOSE`
    and `TOOL_EXECUTE` are declared and mapped to roles now so the model
    is complete, but -- exactly like `ToolCapability.WRITE/PROPOSE/
    ADMIN_APPROVAL_REQUIRED` -- neither is consulted by
    `authorize_tool_invocation()` yet: `run_tool()` still rejects those
    capabilities unconditionally (Phase 2 scope, unchanged by Phase 3).
    Domain permissions (dataset.*, training.*, system.*) are explicitly
    out of scope for this phase."""

    TOOL_READ = "tool.read"
    TOOL_PROPOSE = "tool.propose"
    TOOL_EXECUTE = "tool.execute"


ROLE_PERMISSIONS: Mapping[AdminRole, frozenset[Permission]] = {
    AdminRole.SUPER_ADMIN: frozenset(
        {Permission.TOOL_READ, Permission.TOOL_PROPOSE, Permission.TOOL_EXECUTE}
    ),
    AdminRole.ADMIN: frozenset({Permission.TOOL_READ, Permission.TOOL_PROPOSE}),
    AdminRole.AUDITOR: frozenset({Permission.TOOL_READ}),
    AdminRole.NONE: frozenset(),
}

# The default role for any admin_id not present in the configured
# override map -- including `admin_id=None`. This is what makes every
# pre-Phase-3 `run_tool()` call site (every real caller already passes
# an authenticated admin_id via `_run_tool_logged`; every test and the
# one internal `_reply_open_ended` call site that does not) keep
# working exactly as before: no admin previously blocked from a
# READ_ONLY tool becomes newly blocked by this phase (INVARIANT 10).
# `run_tool()` is only ever reached after `require_admin`/CSRF have
# already authenticated the HTTP caller -- there is no unauthenticated
# route that reaches it -- so this default never grants an
# unauthenticated caller anything; it only fills in the role for an
# already-authenticated caller whose identity wasn't threaded through
# yet.
DEFAULT_ROLE = AdminRole.ADMIN


def resolve_admin_role(
    admin_id: str | None, role_overrides: Mapping[str, AdminRole]
) -> AdminRole:
    """`role_overrides` is `Settings.admin_role_overrides_map` (or an
    empty mapping in a context with no `Settings`, e.g. a direct unit
    test) -- a plain `dict`, not a database read, by design (see
    `AdminRole`'s docstring for why no migration is used). Looking up
    `None` in any mapping simply misses, landing on `DEFAULT_ROLE` --
    no special-casing needed."""

    return role_overrides.get(admin_id, DEFAULT_ROLE) if admin_id else DEFAULT_ROLE


def permissions_for_role(role: AdminRole) -> frozenset[Permission]:
    """Default-deny (INVARIANT 8): a role absent from `ROLE_PERMISSIONS`
    -- which cannot happen for any `AdminRole` member today, since every
    member has an entry, but is preserved here as the safe fallback for
    any future role added to the enum without a matching grant -- yields
    zero permissions, never all of them."""

    return ROLE_PERMISSIONS.get(role, frozenset())


# Which single permission each capability requires, for the capabilities
# that actually have a wired execution path. WRITE/PROPOSE/
# ADMIN_APPROVAL_REQUIRED intentionally have no entry -- see
# `authorize_tool_invocation()`, which rejects them before this mapping
# is ever consulted (Phase 2 scope, unchanged by Phase 3: a permission
# grant alone must never be able to unlock them -- INVARIANT 4).
_CAPABILITY_REQUIRED_PERMISSION: Mapping[ToolCapability, Permission] = {
    ToolCapability.READ_ONLY: Permission.TOOL_READ,
}


def authorize_tool_invocation(
    name: str,
    capability: ToolCapability,
    *,
    admin_id: str | None,
    permissions: frozenset[Permission] = frozenset(),
    system_authorized: bool = False,
) -> AuthorizationDecision:
    """The single authorization decision point for tool execution.

    Phase 2 scope (unchanged): only `READ_ONLY` tools have a wired
    execution path today -- all 90 pre-existing Admin Assistant tools
    are `READ_ONLY` (confirmed by static call-graph inspection, see the
    Phase 2 tool census). `WRITE`/`PROPOSE`/`ADMIN_APPROVAL_REQUIRED`
    are declared capabilities with no execution path through
    `run_tool()`: the only governed mutation flow in this codebase is
    `AdminAssistantService.propose/review/execute` (a separate,
    already-audited two-actor proposal/approval pipeline). Declaring a
    tool with one of those capabilities does NOT let it execute here --
    it is unconditionally rejected regardless of admin identity AND
    regardless of resolved permissions (INVARIANT 4/5): a permission
    grant is exactly as incapable of unlocking these as the capability
    declaration alone was in Phase 2.

    Phase 3 addition: `READ_ONLY` now also requires
    `Permission.TOOL_READ` in the caller's resolved `permissions` set
    (INVARIANT 1/2: authentication is not authorization -- an
    authenticated admin whose resolved role lacks `tool.read` is
    denied). `permissions` defaults to the empty set -- a caller that
    does not resolve and pass real permissions gets denied, never
    silently allowed (no fail-open default here); `run_tool()` is the
    only caller and always resolves a real permission set via
    `resolve_admin_role()`/`permissions_for_role()` before calling this
    function, so every real dispatch is covered.

    `SYSTEM_ONLY`: rejected unless the caller explicitly asserts
    `system_authorized=True`. No internal/system caller is wired to
    tool dispatch yet, so no real tool should currently declare this
    capability -- it exists so a future system-triggered tool has
    somewhere safe to land.
    """

    if capability is ToolCapability.READ_ONLY:
        required = _CAPABILITY_REQUIRED_PERMISSION[ToolCapability.READ_ONLY]
        if required in permissions:
            return AuthorizationDecision(True, f"admin has {required.value} permission")
        return AuthorizationDecision(
            False,
            f"tool {name!r} requires {required.value}, which the caller's resolved "
            "role does not grant",
        )
    if capability is ToolCapability.SYSTEM_ONLY:
        if system_authorized:
            return AuthorizationDecision(True, "system-authorized caller")
        return AuthorizationDecision(
            False,
            f"tool {name!r} is system_only and no system-authorized caller invoked it",
        )
    return AuthorizationDecision(
        False,
        f"tool {name!r} declares capability {capability.value!r}, which has no wired "
        "execution path through run_tool() yet (Phase 2 scope) -- mutations remain "
        "governed exclusively by AdminAssistantService.propose/review/execute",
    )
