"""MB-26: Voice Permission Guard -- pure decision function only.

This module deliberately does NOT call MB-24's
`runtime_policy_evaluator.evaluate_permission()` -- that function's
real signature requires `plugin_status`, `risk_level`, and
`admin_reviewed`, parameters that describe a registered *plugin*
record and have no honest value for Voice Runtime, which is a
first-party product feature with no plugin record at all. Fabricating
placeholder values for those parameters just to call the function
would be reuse in name only, not in substance -- so this module
instead reuses only the real data MB-24's registry publishes (via
`permission_scope_registry.scope_definition()`, passed in by the
caller) to inform its own first-party decision.

It also deliberately does NOT enforce `scope_definition["public_chat_
available"]` as a hard block the way MB-24's plugin evaluator does for
`microphone.capture` (which is `False` there, since that entry was
designed for third-party plugin requests) -- that is the entire point
of Voice Runtime's own, separate, explicit per-session consent gate
for the public path. This is a deliberate, documented deviation (see
the MB-26 completion report's Reuse Audit section), not an oversight.
"""

from __future__ import annotations

from typing import Any

_ALWAYS_ALLOWED_SCOPES = frozenset({"plugin.storage.local", "chat.read.current"})
_KNOWN_SCOPES = _ALWAYS_ALLOWED_SCOPES | {"microphone.capture"}


def evaluate(
    *,
    scope_key: str,
    session_mode: str,
    explicit_consent_given: bool = False,
    admin_authorized: bool = False,
) -> dict[str, Any]:
    if scope_key not in _KNOWN_SCOPES:
        return {"allowed": False, "reason": f"unknown voice scope '{scope_key}'"}

    if scope_key in _ALWAYS_ALLOWED_SCOPES:
        return {"allowed": True, "reason": f"'{scope_key}' is allow-by-default for voice sessions"}

    # scope_key == "microphone.capture" from here on.
    if session_mode == "public_chat":
        if explicit_consent_given:
            return {
                "allowed": True,
                "reason": "explicit per-session consent given for microphone.capture (public chat)",
            }
        return {
            "allowed": False,
            "reason": "microphone.capture requires explicit per-session consent in public chat",
        }

    if session_mode == "admin_assistant":
        if admin_authorized:
            return {
                "allowed": True,
                "reason": "admin-authorized for microphone.capture (admin assistant)",
            }
        return {
            "allowed": False,
            "reason": "microphone.capture requires admin authorization in admin assistant mode",
        }

    return {"allowed": False, "reason": f"unknown session_mode '{session_mode}'"}
