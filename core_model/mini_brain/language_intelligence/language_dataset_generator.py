"""MB-13: Language Dataset Generator -- pure. For a Tamil-dominant
dataset, produces a real Tanglish draft by reusing `core_model.
admin_assistant.localization.tanglish_renderer.to_tanglish()`
unchanged. Never produces an English draft -- audited finding: no
Tamil->English translation engine exists anywhere in this codebase, so
fabricating English text would violate "never fabricate language
correctness." Always `verified: false`; MB-13 never creates a final
dataset.
"""

from __future__ import annotations

from typing import Any

from core_model.admin_assistant.localization.tanglish_renderer import to_tanglish

MAX_SAMPLES = 20
SAMPLE_PREVIEW_CHARS = 200


def generate_language_drafts(*, dominant_language: str, sample_texts: list[str]) -> dict[str, Any]:
    if dominant_language != "tamil":
        return {
            "applicable": False,
            "reason": f"dataset is not Tamil-dominant (dominant_language={dominant_language}) -- draft generation only applies to Tamil-only datasets",
            "tanglish_draft": None, "english_draft": None, "multilingual_mapping": None, "verified": False,
        }

    samples = []
    for t in sample_texts[:MAX_SAMPLES]:
        try:
            tanglish_text = to_tanglish(t)[:SAMPLE_PREVIEW_CHARS]
        except KeyError:
            # A malformed/orphaned Tamil vowel-sign sequence (a real OCR
            # artifact) -- skip rather than crash or fabricate a result.
            continue
        samples.append({"tamil_text": t[:SAMPLE_PREVIEW_CHARS], "tanglish_text": tanglish_text})

    return {
        "applicable": True,
        "tanglish_draft": {"sample_count": len(samples), "samples": samples},
        "english_draft": None,
        "english_draft_unavailable_reason": (
            "no Tamil->English translation engine exists anywhere in this codebase (confirmed by "
            "audit) -- MB-13 never fabricates a translation, so no English draft is produced"
        ),
        "multilingual_mapping": {
            "tamil": "source", "tanglish": "generated (deterministic transliteration)", "english": "not_available",
        },
        "verified": False,
        "status": "needs_admin_review",
    }
