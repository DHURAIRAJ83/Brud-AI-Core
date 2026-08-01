"""Resolves whether the `memory` public-chat route has its
prerequisites met: an active `conversation_memory_policies` row and an
active `memory_retrieval_profiles` row. Neither is auto-created by this
phase -- provisioning either is a normal Admin governance action
(`ConversationSessionService`/existing Admin Dashboard tooling), not
something Phase 18 does on the public path. If either is absent, the
`memory` route honestly resolves to `insufficient`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.core.config import Settings
from backend.database.connection import database_connection


@dataclass(frozen=True)
class ResolvedMemoryScope:
    memory_policy_public_id: str
    retrieval_profile_public_id: str


class PublicMemoryScopeResolver:
    def __init__(self, database_path: Path, settings: Settings) -> None:
        self.database_path = database_path
        self.settings = settings

    def resolve(self) -> ResolvedMemoryScope | None:
        if not self.settings.memory_enabled:
            return None
        with database_connection(self.database_path) as connection:
            policy = connection.execute(
                """SELECT public_id FROM conversation_memory_policies
                WHERE lifecycle_status = 'active' ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            if policy is None:
                return None
            profile = connection.execute(
                "SELECT public_id FROM memory_retrieval_profiles ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if profile is None:
                return None
            return ResolvedMemoryScope(
                memory_policy_public_id=policy["public_id"],
                retrieval_profile_public_id=profile["public_id"],
            )


__all__ = ["PublicMemoryScopeResolver", "ResolvedMemoryScope"]
