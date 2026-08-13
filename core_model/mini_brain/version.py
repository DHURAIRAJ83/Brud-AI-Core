"""Mini Brain framework version -- describes the *framework* shipped
in MB-01, not a model version, since MB-01 ships no model."""

from __future__ import annotations

MINI_BRAIN_MODULE_VERSION = "0.1.0"
MINI_BRAIN_PHASE = "MB-01"
MINI_BRAIN_PHASE_NAME = "Foundation & Architecture"


def version_info() -> dict[str, object]:
    return {
        "module_version": MINI_BRAIN_MODULE_VERSION,
        "phase": MINI_BRAIN_PHASE,
        "phase_name": MINI_BRAIN_PHASE_NAME,
        "model": None,
        "model_status": "not_integrated",
    }
