"""MB-30: Fallback Orchestrator -- pure. The phase spec's own section
8 decision order, given pre-resolved booleans only -- extends MB-28's
`provider_fallback_policy.decide()` pattern with a fuller, four-step
order that distinguishes "loaded" from "installed but not loaded".
Never touches MB-27/28's services itself; the caller resolves the
booleans.
"""

from __future__ import annotations

from typing import Any


def decide(*, local_loaded: bool, local_installed_not_loaded: bool, external_enabled: bool) -> dict[str, Any]:
    if local_loaded:
        return {"step": 1, "backend": "local_loaded", "reason": "a local model is already loaded"}
    if local_installed_not_loaded:
        return {"step": 2, "backend": "local_installed", "reason": "a local model is installed but not currently loaded"}
    if external_enabled:
        return {"step": 3, "backend": "external", "reason": "an external provider is enabled"}
    return {"step": 4, "backend": "unavailable", "reason": "no local model installed/loaded and no external provider enabled"}
