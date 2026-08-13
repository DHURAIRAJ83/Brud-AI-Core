"""MB-28: Admin Explainer Templates -- pure. Deterministic
page-explanation lookup, reusing `core_model.admin_assistant.
dashboard_registry` directly (the same real page catalogue
`admin_assistant_tools.py`'s `_tool_page_help` already reads) rather
than duplicating page metadata. The LLM is only ever attempted when
this lookup misses.
"""

from __future__ import annotations

from typing import Any

from core_model.admin_assistant.dashboard_registry import get_page_by_id, get_page_by_nav_key


def _bilingual_text(value: dict[str, str] | str | None) -> str:
    """`PageEntry.title`/`.purpose`/`.safety_note` are bilingual dicts
    (`{"en": ..., "ta": ...}`), not plain strings -- this renders both,
    English first, matching the bilingual convention this project's own
    dashboard/reports already use."""
    if not value:
        return ""
    if isinstance(value, str):
        return value
    english = value.get("en", "")
    tamil = value.get("ta", "")
    if english and tamil and english != tamil:
        return f"{english} ({tamil})"
    return english or tamil


def explain_page(*, page_id: str | None = None, nav_key: str | None = None) -> dict[str, Any]:
    page = None
    if page_id:
        page = get_page_by_id(page_id)
    if page is None and nav_key:
        page = get_page_by_nav_key(nav_key)

    if page is None:
        return {"found": False, "explanation": None}

    lines = [f"{_bilingual_text(page.title)}: {_bilingual_text(page.purpose)}"]
    if page.tabs:
        lines.append("Tabs: " + ", ".join(page.tabs))
    if page.safety_note:
        lines.append(f"Safety note: {_bilingual_text(page.safety_note)}")

    return {
        "found": True,
        "page_id": page.page_id,
        "nav_key": page.nav_key,
        "explanation": " ".join(lines),
    }
