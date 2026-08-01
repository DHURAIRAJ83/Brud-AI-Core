"""Phase 10A: centralized Admin Assistant response localization.

One place localized copy is produced from, instead of scattering
language-specific branches across every API and component -- see
docs/admin_assistant/phase10a_language_preference_plan.md section 4.
"""

from core_model.admin_assistant.localization.message_catalog import (
    MESSAGE_CATALOG,
    catalog_message,
    localize,
    pending_work_lines,
)
from core_model.admin_assistant.localization.tanglish_renderer import to_tanglish

__all__ = [
    "MESSAGE_CATALOG", "catalog_message", "localize", "pending_work_lines", "to_tanglish",
]
