"""MB-28: Provider Fallback Policy -- pure. Decides which backend to
use given pre-resolved booleans only -- this module never reads MB-27
provider settings itself, never touches a database or network. The
service layer resolves the booleans and calls `decide()`.
"""

from __future__ import annotations

from typing import Any


def decide(
    *,
    local_available: bool,
    local_model_loaded: bool,
    external_enabled: bool,
    external_configured: bool,
) -> dict[str, Any]:
    if local_available and local_model_loaded:
        return {"backend": "local", "reason": "local model is available and loaded"}

    if external_enabled and external_configured:
        return {"backend": "external", "reason": "external provider is enabled and fully configured"}

    if not local_available or not local_model_loaded:
        reason = "local model unavailable" if not local_available else "local model not loaded"
        if external_enabled and not external_configured:
            reason += "; external provider enabled but not fully configured"
        elif not external_enabled:
            reason += "; external fallback not enabled"
        return {"backend": "unavailable", "reason": reason}

    return {"backend": "unavailable", "reason": "no backend available"}
