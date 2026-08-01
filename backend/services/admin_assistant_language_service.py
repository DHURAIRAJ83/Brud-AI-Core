"""Phase 10A: Admin Assistant response-language preference service.

Wraps `AdminRepository.get_response_language`/`set_response_language`
(the persistence layer, on the existing `admin_accounts` table -- see
`docs/admin_assistant/phase10a_language_preference_plan.md` section 2)
and `core_model.admin_assistant.language_preference`'s pure
resolution. This is the one place that turns "what does this admin
want, right now, for this message" into a concrete answer -- every
other Admin Assistant code path calls `resolve()` here rather than
re-deriving language on its own.
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.database.repositories.admin import AdminRepository
from core_model.admin_assistant.language_preference import (
    RESPONSE_LANGUAGES,
    ResolvedLanguage,
    resolve_response_language,
)


class AdminAssistantLanguageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = AdminRepository(settings.resolved_database_path)

    def get_preference(self, admin_id: str) -> dict[str, Any]:
        return self.repository.get_response_language(admin_id)

    def set_preference(self, admin_id: str, response_language: str) -> dict[str, Any]:
        return self.repository.set_response_language(admin_id, response_language)

    def resolve(
        self, *, admin_id: str, message_text: str = "", request_override: str | None = None
    ) -> ResolvedLanguage:
        saved = self.repository.get_response_language(admin_id)["response_language"]
        return resolve_response_language(
            message_text=message_text,
            request_override=request_override,
            saved_preference=saved,
        )

    def preview(
        self, *, message_text: str, request_override: str | None = None
    ) -> dict[str, Any]:
        """Non-persistent preview (Step 8's optional endpoint) -- never
        reads or writes a saved preference, so it can be used to try a
        mode before committing to it."""

        resolved = resolve_response_language(
            message_text=message_text, request_override=request_override
        )
        return resolved.to_dict()


__all__ = ["AdminAssistantLanguageService", "RESPONSE_LANGUAGES"]
