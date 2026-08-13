"""MB-25: Audit Record Builder -- pure. Mirrors MB-24's own
`audit_record_builder.py` exactly: assembles a structured record of an
already-decided runtime action for persistence -- this module never
makes a decision itself, only formats one that has already been made.
"""

from __future__ import annotations

from typing import Any


def build_audit_record(
    *, event_type: str, execution_public_id: str | None, stage: str | None, actor: str, metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_type": event_type, "execution_public_id": execution_public_id, "stage": stage, "actor": actor,
        "metadata": metadata,
        "disclosure": "a structured record of an already-decided runtime action -- this module never makes a decision itself",
    }
