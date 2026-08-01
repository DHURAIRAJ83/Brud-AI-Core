"""Finite catalog of the fixed Admin-Assistant-specific strings Phase
10A itself introduces (preference save confirmation, invalid-language
rejection, the small set of known proposal-lifecycle messages the
Admin Assistant surfaces), plus the generic `localize()` helper.

`localize()` is what lets every existing bilingual `{en, ta}` dict
already in this codebase (dashboard pages, action definitions, help
registry, chat replies) render correctly for any resolved response
language, including Tanglish -- which is always *derived* from the
existing "ta" value via `to_tanglish()`, never hand-written a third
time. This is why this catalog stays small: it only needs entries for
strings that do not already exist as an `{en, ta}` pair somewhere
else in the codebase.
"""

from __future__ import annotations

from core_model.admin_assistant.localization.tanglish_renderer import to_tanglish

MESSAGE_CATALOG: dict[str, dict[str, str]] = {
    "preference_saved": {
        "en": "Your Admin Assistant response language preference has been saved.",
        "ta": "உங்கள் Admin Assistant பதில் மொழி விருப்பம் சேமிக்கப்பட்டது.",
    },
    "invalid_response_language": {
        "en": "That is not a supported response language. Choose Tamil, English, "
        "Tanglish, or Auto.",
        "ta": "அது ஆதரிக்கப்படும் பதில் மொழி அல்ல. தமிழ், English, Tanglish, அல்லது "
        "Auto-ஐ தேர்ந்தெடுக்கவும்.",
    },
    "proposal_stale": {
        "en": "This proposal's target has changed since it was created -- review the "
        "current state before approving.",
        "ta": "இந்த proposal-இன் target உருவாக்கப்பட்டதிலிருந்து மாறிவிட்டது -- approve "
        "செய்யும் முன் தற்போதைய நிலையை பரிசீலிக்கவும்.",
    },
    "proposal_requires_reason": {
        "en": "This action requires a written reason before it can be proposed.",
        "ta": "இந்த action-ஐ propose செய்வதற்கு முன் ஒரு எழுதப்பட்ட காரணம் தேவை.",
    },
    "unknown_action_type": {
        "en": "That action type is not recognized or allowed.",
        "ta": "அந்த action type அங்கீகரிக்கப்படவில்லை அல்லது அனுமதிக்கப்படவில்லை.",
    },
    "llm_reply_language_mismatch_retry": {
        "en": "Your previous reply was not in the requested language. Reply again, "
        "only in the requested language.",
        "ta": "உங்கள் முந்தைய பதில் கோரப்பட்ட மொழியில் இல்லை. கோரப்பட்ட மொழியில் மட்டும் "
        "மீண்டும் பதிலளிக்கவும்.",
    },
}


def localize(bilingual: dict[str, str], resolved_language: str) -> str:
    """Renders any existing bilingual `{en, ta}` dict (and this
    catalog's own entries, which share that shape) for one concrete
    resolved response language. `resolved_language` must already be
    concrete (`"tamil"`/`"english"`/`"tanglish"`) -- callers resolve
    `"auto"` before calling this, never here."""

    if resolved_language == "english":
        return bilingual.get("en", "")
    if resolved_language == "tamil":
        return bilingual.get("ta") or bilingual.get("en", "")
    if resolved_language == "tanglish":
        tamil_text = bilingual.get("ta")
        if tamil_text:
            return to_tanglish(tamil_text)
        return bilingual.get("en", "")
    raise ValueError(
        f"localize() requires a concrete resolved_language, got {resolved_language!r}"
    )


def catalog_message(key: str, resolved_language: str) -> str:
    return localize(MESSAGE_CATALOG[key], resolved_language)


def pending_work_lines(summary: dict[str, object], resolved_language: str) -> list[str]:
    """Re-derives localized "what needs attention" lines from
    `AdminAssistantService.dashboard_overview()`'s raw `summary` counts
    -- never from its `guidance` field, which stays a stable,
    English-only, unrelated contract other callers/tests already
    depend on. Shared by the floating widget's chat reply and the full
    Admin Assistant page's Guidance tab so both surfaces render the
    exact same localized text from the exact same counts."""

    dataset_records = summary.get("dataset_records", {})
    admin_approvals = summary.get("admin_approvals", {})
    pending_review = dataset_records.get("pending_review", 0) if isinstance(
        dataset_records, dict
    ) else 0
    pending_approvals = admin_approvals.get("pending", 0) if isinstance(
        admin_approvals, dict
    ) else 0

    lines: list[str] = []
    if pending_review:
        bilingual = {
            "en": f"{pending_review} dataset record(s) are pending_review -- inspect and "
            "either propose approve/reject decisions.",
            "ta": f"{pending_review} dataset record(s) pending_review நிலையில் உள்ளன -- "
            "பரிசோதித்து approve/reject முடிவுகளை propose செய்யவும்.",
        }
        lines.append(localize(bilingual, resolved_language))
    if pending_approvals:
        bilingual = {
            "en": f"{pending_approvals} Admin Assistant proposal(s) are awaiting Admin "
            "Review before they can execute.",
            "ta": f"{pending_approvals} Admin Assistant proposal(s) execute "
            "செய்யப்படுவதற்கு முன் Admin Review-ஐ எதிர்பார்த்துக் காத்திருக்கின்றன.",
        }
        lines.append(localize(bilingual, resolved_language))
    if not lines:
        bilingual = {
            "en": "Nothing is pending right now.",
            "ta": "தற்போது நிலுவையில் எதுவும் இல்லை.",
        }
        lines.append(localize(bilingual, resolved_language))
    return lines
