"""Resolves the currently active `public_chat`-scope inference model
assignment, if any. Public chat may never select a raw assignment ID
itself (Rule 15) -- this is the one place that lookup happens, reading
only `status='active'` rows already scoped `public_chat` (a scope that
only passes through `ModelAssignmentService`'s own real
`_public_activation_gate()` before ever reaching `status='active'` --
this resolver builds no new activation logic, it only reads the result
of Admin governance that already ran).

Also honors `Settings.public_chat_model_enabled` -- a master kill
switch that already existed in `backend/core/config.py` (default
`False`) but was never read anywhere in the codebase before this
phase. Wiring it here gives operators one extra, independent way to
turn public-chat model answers off without touching any assignment
row.
"""

from __future__ import annotations

from pathlib import Path

from backend.core.config import Settings
from backend.database.connection import database_connection


class PublicModelAssignmentResolver:
    def __init__(self, database_path: Path, settings: Settings) -> None:
        self.database_path = database_path
        self.settings = settings

    def resolve(self) -> str | None:
        if not self.settings.public_chat_model_enabled:
            return None
        with database_connection(self.database_path) as connection:
            row = connection.execute(
                """SELECT a.public_id FROM inference_model_assignments a
                JOIN inference_assignment_scopes s ON s.id = a.model_assignment_scope_id
                WHERE s.scope_key = 'public_chat' AND s.enabled = 1 AND a.status = 'active'
                ORDER BY a.id DESC LIMIT 1"""
            ).fetchone()
            return row["public_id"] if row else None


__all__ = ["PublicModelAssignmentResolver"]
