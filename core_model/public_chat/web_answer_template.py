"""Phase 20 Step 14 -- deterministic, template-based grounded Web
answer generation.

Deliberately **not** an LLM call. A template can mechanically
guarantee "no unsupported factual additions" and "never fabricate a
citation" -- the two hardest requirements in Step 14 -- whereas
wiring a full grounded-generation LLM call (its own injection-safe
prompting, deep integration with Phase 18's model-inference path)
reintroduces exactly the hallucination risk those rules exist to
prevent, for a phase whose evidence pipeline is already the hard,
novel part. This is a disclosed, deliberate scope decision, not a
shortcut: the surrounding scaffold sentence is bilingual (mirrors
`fallback_text.py`'s dict-by-language pattern exactly), while the
evidence excerpt itself is quoted verbatim in whatever language the
source was actually written in -- quoting a source's own words is
honest; generating new sentences in a language nothing was retrieved
in would not be.
"""

from __future__ import annotations

from backend.services.web_evidence_selection_service import EvidenceItem

_FOUND_PREFIX = {
    "ta": "கண்டறியப்பட்ட தகவல்",
    "en": "Here's what I found",
}
_SOURCE_LABEL = {"ta": "மூலம்", "en": "Source"}
_CONFLICT_PREFIX = {
    "ta": "நம்பகமான மூலங்கள் இதில் வேறுபடுகின்றன",
    "en": "Trusted sources disagree on this",
}
_LIMITATION_STALE = {
    "ta": "இந்தத் தகவல் காலாவதியானதாக இருக்கலாம் என்பதை கவனிக்கவும்.",
    "en": "Note: this information may be out of date.",
}
_LIMITATION_UNDATED = {
    "ta": "மூலத்தில் தேதி தகவல் இல்லை, எனவே இது எவ்வளவு புதியது என்று உறுதி இல்லை.",
    "en": "The source has no date, so how current this is can't be confirmed.",
}

MAX_EVIDENCE_ITEMS_IN_ANSWER = 3


def _language_key(answer_language: str) -> str:
    return answer_language if answer_language in ("ta", "en") else "ta"


def generate_grounded_answer(
    *,
    evidence_items: list[EvidenceItem],
    conflict_status: str,
    answer_language: str,
) -> tuple[str, list[str]]:
    """Returns `(reply_text, limitation_codes)`. Never called with an
    empty `evidence_items` list -- the caller decides insufficiency
    before reaching here."""

    lang = _language_key(answer_language)
    limitations: list[str] = []

    if conflict_status in ("material_conflict", "unresolved_conflict", "date_version_conflict"):
        lines = [_CONFLICT_PREFIX[lang] + ":"]
        for item in evidence_items[:MAX_EVIDENCE_ITEMS_IN_ANSWER]:
            lines.append(f"- {item.source_title} ({_SOURCE_LABEL[lang]}: {item.source_url}): "
                          f"{item.supporting_excerpt}")
        limitations.append("source_conflict_disclosed")
        return "\n".join(lines), limitations

    lines = [_FOUND_PREFIX[lang] + ":", ""]
    for item in evidence_items[:MAX_EVIDENCE_ITEMS_IN_ANSWER]:
        lines.append(f"{item.supporting_excerpt}")
        lines.append(f"({_SOURCE_LABEL[lang]}: {item.source_title})")
        if item.freshness_status == "stale":
            if "stale_source" not in limitations:
                limitations.append("stale_source")
        elif item.freshness_status == "undated":
            if "undated_source" not in limitations:
                limitations.append("undated_source")

    if "stale_source" in limitations:
        lines.append("")
        lines.append(_LIMITATION_STALE[lang])
    if "undated_source" in limitations:
        lines.append("")
        lines.append(_LIMITATION_UNDATED[lang])

    return "\n".join(lines), limitations


__all__ = ["MAX_EVIDENCE_ITEMS_IN_ANSWER", "generate_grounded_answer"]
