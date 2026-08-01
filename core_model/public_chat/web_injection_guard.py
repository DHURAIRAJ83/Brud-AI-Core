"""Phase 20 Step 9 -- injection detection for fetched Web page content
entering the Trusted Web evidence pipeline.

Reuses Phase 16's bounded, context-aware RAG injection filter
unchanged for the categories it already covers (`reveal_system_prompt`,
`exfiltrate_secrets`, `act_as_system`, `execute_commands`,
`change_policies`, `follow_these_instructions_instead`,
`tool_call_directive`, `encoded_payload`, `new_instructions_marker`),
and adds Web-specific categories that neither the RAG filter nor
`core_model.conversation.injection_guard`'s memory-specific extension
needed to consider: hidden-instruction markers surviving HTML
extraction, and directives attempting to manipulate which source gets
cited. This is the third extension of the same base filter in this
codebase's lineage (RAG -> conversation -> Web), each adding only its
own domain-specific categories on top, never re-implementing detection
from scratch.

Fetched Web content is always treated as untrusted data, never as
authority -- a match here means the source is excluded from the
evidence set (with the injection reason recorded), never that the
public user's own request is rejected.
"""

from __future__ import annotations

import re

from core_model.rag.injection_filter import classify_injection_status, detect_injection_signals

_WEB_SPECIFIC_PATTERNS = {
    "hidden_instruction_marker": re.compile(
        r"\b(note to (the )?(ai|assistant|model)|assistant[- ]only|hidden instruction)\b",
        re.IGNORECASE,
    ),
    "manipulate_citations": re.compile(
        r"\b(cite|reference) (this|only this|exclusively) (page|url|source|site)\b"
        r"|\b(do not|never) cite (other|any other) sources?\b",
        re.IGNORECASE,
    ),
}


def detect_web_injection_signals(text: str) -> dict[str, object]:
    base = detect_injection_signals(text)
    extra_matches = [
        name for name, pattern in _WEB_SPECIFIC_PATTERNS.items() if pattern.search(text)
    ]
    return {"matched_categories": sorted({*base["matched_categories"], *extra_matches})}


def classify_web_injection_status(matched_categories: list[str], *, policy: str = "block") -> str:
    return classify_injection_status(matched_categories, policy=policy)


def assess_web_content_injection(text: str) -> dict[str, object]:
    signals = detect_web_injection_signals(text)
    status = classify_web_injection_status(signals["matched_categories"])
    return {"injection_status": status, "matched_categories": signals["matched_categories"]}


__all__ = [
    "assess_web_content_injection",
    "classify_web_injection_status",
    "detect_web_injection_signals",
]
