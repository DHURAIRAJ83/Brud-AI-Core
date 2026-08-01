"""`PublicRagScopeResolver` (Step 10) -- determines which production
RAG space, if any, public chat may retrieve from.

Resolution requires ALL of: a `production_rag_release_candidates` row
with `status='activated' AND production_visible=1`; its
`retrieval_profile_id` resolving to a `rag_retrieval_profiles` row with
`status='active'`; and the owning `rag_knowledge_spaces.lifecycle_status
== 'active'`. If no such chain exists, resolution returns `None` --
`insufficient`, never a sandbox/quarantine/training/evaluation-only
fallback. This directly resolves Phase 16's audit finding that
production RAG activation previously had zero runtime effect on public
chat.

A restrictive `RetrievalFiltersPayload` (approved sources, non-blocked
licence only, `restricted` excluded by explicit, documented policy
choice) is always returned alongside the resolved profile, so the
caller never has to separately remember to apply it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.models.rag import RetrievalFiltersPayload

# Deliberately conservative: 'restricted' sources are not public-safe by
# default in this phase (plan doc Step 6). 'blocked' is always excluded
# by RagRetrievalService's own access-filter logic regardless of this
# list.
_PUBLIC_SAFE_LICENCE_STATUSES = ("open", "unknown")


@dataclass(frozen=True)
class ResolvedRagScope:
    retrieval_profile_public_id: str
    knowledge_space_public_id: str
    knowledge_space_name: str
    filters: RetrievalFiltersPayload


class PublicRagScopeResolver:
    def __init__(self, database_path: Path, settings: Settings) -> None:
        self.database_path = database_path
        self.settings = settings

    def resolve(self) -> ResolvedRagScope | None:
        if not self.settings.rag_enabled:
            return None
        with database_connection(self.database_path) as connection:
            candidate = connection.execute(
                """SELECT retrieval_profile_id FROM production_rag_release_candidates
                WHERE status = 'activated' AND production_visible = 1
                ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            if candidate is None or candidate["retrieval_profile_id"] is None:
                return None

            profile = connection.execute(
                """SELECT public_id, knowledge_space_id FROM rag_retrieval_profiles
                WHERE id = ? AND status = 'active'""",
                (candidate["retrieval_profile_id"],),
            ).fetchone()
            if profile is None:
                return None

            space = connection.execute(
                """SELECT public_id, name FROM rag_knowledge_spaces
                WHERE id = ? AND lifecycle_status = 'active'""",
                (profile["knowledge_space_id"],),
            ).fetchone()
            if space is None:
                return None

            return ResolvedRagScope(
                retrieval_profile_public_id=profile["public_id"],
                knowledge_space_public_id=space["public_id"],
                knowledge_space_name=space["name"],
                filters=RetrievalFiltersPayload(
                    approval_statuses=["approved"],
                    licence_statuses=list(_PUBLIC_SAFE_LICENCE_STATUSES),
                ),
            )


__all__ = ["PublicRagScopeResolver", "ResolvedRagScope"]
