"""MB-13: Tamil Spell Analyzer -- pure. Matches record text against
the existing, admin-curated Document Tamil Correction Registry's
active rules (`DocumentTamilCorrectionRegistryService.list_rules(
status="active")`, read at the service layer and passed in here) --
never a fabricated dictionary. Suggests the registry's own approved
correction; never applies one.

Disclosure: detection is bounded to whatever corrections admins have
already curated through the existing Tamil OCR/quality review
workflow -- a record with zero matches is evidence of no *known-rule*
violation, not proof of correct spelling. This codebase has no
general-purpose Tamil dictionary anywhere (confirmed by audit), so a
comprehensive spell-check is not claimed.
"""

from __future__ import annotations

from typing import Any

MAX_MATCHES_STORED = 200


def analyze_spelling(*, texts: list[str], active_rules: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(texts)
    matches: list[dict[str, Any]] = []
    affected_indices: set[int] = set()

    for i, text in enumerate(texts):
        for rule in active_rules:
            incorrect_form = rule.get("incorrect_form") or ""
            if incorrect_form and incorrect_form in text:
                matches.append({
                    "record_index": i, "incorrect_form": incorrect_form,
                    "suggested_correction": rule.get("approved_correction"),
                    "issue_category": rule.get("issue_category"), "confidence_band": rule.get("confidence_band"),
                })
                affected_indices.add(i)

    issue_rate = (len(affected_indices) / total) if total else 0.0
    spell_score = round(max(0.0, 100.0 - issue_rate * 100.0), 1)

    return {
        "records_analyzed": total,
        "rules_checked": len(active_rules),
        "match_count": len(matches),
        "matches": matches[:MAX_MATCHES_STORED],
        "affected_record_count": len(affected_indices),
        "spell_score": spell_score,
        "disclosure": (
            "spelling detection is bounded to the admin-curated Document Tamil Correction "
            "Registry's active rules only -- not a comprehensive dictionary; a record with zero "
            "matches is not proof of correct spelling, only proof of no known-rule violation"
        ),
    }
