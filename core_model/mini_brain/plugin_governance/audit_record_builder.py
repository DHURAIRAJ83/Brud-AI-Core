"""MB-24: Audit Record Builder -- pure. Assembles a structured record
of an already-decided governance action for persistence as a runtime
event -- this module never makes a decision itself, only formats one
that has already been made.
"""

from __future__ import annotations

from typing import Any


def build_audit_record(
    *, event_type: str, plugin_public_id: str | None, stage: str | None, actor: str, metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_type": event_type, "plugin_public_id": plugin_public_id, "stage": stage, "actor": actor,
        "metadata": metadata,
        "disclosure": "a structured record of an already-decided governance action -- this module never makes a decision itself",
    }
