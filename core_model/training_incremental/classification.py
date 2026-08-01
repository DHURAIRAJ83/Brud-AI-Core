"""Phase 14 Step 4: deterministic (no LLM) language-vs-factual record
classification and routing.

Facts, current procedures, changing knowledge, and document-specific
information default to RAG unless explicitly transformed into
high-quality language-learning examples elsewhere (Step 5) -- this
module never promotes a record to a training category on its own; it
only classifies and explains (Step 4's "explain why each record is
routed" requirement).
"""

from __future__ import annotations

import re
from typing import Any

from core_model.training_incremental import (
    BLOCKED_CATEGORIES,
    EVALUATION_ONLY_CATEGORIES,
    PRETRAINING_OR_TOKENIZER_CANDIDATE_CATEGORIES,
    RAG_ONLY_CATEGORIES,
    SFT_CANDIDATE_CATEGORIES,
)

_VOLATILITY_MARKERS = re.compile(
    r"\b(today|currently|as of|latest|this (year|month|week)|new (version|release)|"
    r"price|pricing|deadline|schedule|opening hours|contact (us|number)|address|"
    r"phone number|email address|version \d|20\d{2})\b"
    r"|இன்று|தற்போது|தற்சமயம்|சமீபத்திய|புதிய|விலை|கால அளவு|அட்டவணை|தொடர்பு எண்|"
    r"முகவரி|தேதி|இந்த ஆண்டு|இந்த மாதம்",
    re.IGNORECASE,
)
_PROCEDURAL_MARKERS = re.compile(
    r"\b(step \d|first,|second,|then,|follow these|instructions|procedure|how to)\b",
    re.IGNORECASE,
)
_INSTRUCTION_MARKERS = re.compile(
    r"\?|please (explain|write|summarize|translate|list)|^(what|why|how|when|where|who)\b"
    r"|என்ன|எப்படி|ஏன்|எப்போது|யார்|எங்கே|விளக்கு|சொல்லு",
    re.IGNORECASE,
)
_TRANSLATION_MARKERS = re.compile(
    r"\b(translate|translation|in english|in tamil)\b|தமிழில்|மொழிபெயர்", re.IGNORECASE
)
_SUMMARY_MARKERS = re.compile(
    r"\b(summar(y|ize|ise)|in short|tl;dr)\b|சுருக்கம்|சுருக்கமாக", re.IGNORECASE
)
_CORRECTION_MARKERS = re.compile(
    r"\b(correct(ed|ion)?|fix(ed)?|mistake|error|grammar)\b|திருத்த|பிழை", re.IGNORECASE
)
_UNSAFE_MARKERS = re.compile(
    r"\b(bomb|weapon|exploit|malware|child (abuse|exploitation))\b", re.IGNORECASE
)


def classify_record_category(
    *,
    prompt_text: str,
    assistant_text: str,
    task: str,
    modality: str,
    is_evaluation_linked: bool,
    is_contamination_flagged: bool,
    is_unsafe_flagged: bool,
) -> dict[str, Any]:
    """Returns ``{"category": ..., "reason": ...}``. Pure, deterministic,
    no LLM. ``is_evaluation_linked`` means this record's content was
    also used as a Phase 13 evaluation/query-set prompt -- such records
    are always routed to ``evaluation_example``, never training,
    regardless of any other signal."""

    combined = f"{prompt_text}\n{assistant_text}".strip()
    lowered = combined.lower()

    if is_unsafe_flagged or _UNSAFE_MARKERS.search(lowered):
        return {
            "category": "unsafe_or_blocked",
            "reason": "content matched an unsafe/restricted marker or was flagged unsafe upstream",
        }
    if is_evaluation_linked:
        return {
            "category": "evaluation_example",
            "reason": "this record's content is also used as a Phase 13 evaluation/query-set "
            "prompt -- evaluation records can never be transformed into training records",
        }
    if is_contamination_flagged:
        # Still classified (never silently dropped), but the category
        # itself signals downstream blocking via the contamination
        # dimension -- classification and contamination are deliberately
        # independent checks (Step 6 is the authority on blocking).
        pass

    has_instruction = bool(prompt_text.strip()) and bool(assistant_text.strip())
    if _TRANSLATION_MARKERS.search(lowered) and has_instruction:
        return {
            "category": "translation_pair",
            "reason": "prompt/response pair contains translation-request language",
        }
    if _SUMMARY_MARKERS.search(lowered) and has_instruction:
        return {
            "category": "summarization_pair",
            "reason": "prompt/response pair contains summarization-request language",
        }
    if _CORRECTION_MARKERS.search(lowered) and has_instruction and task == "correction":
        return {
            "category": "correction_pair",
            "reason": "prompt/response pair is tagged as a correction task",
        }
    if has_instruction and _INSTRUCTION_MARKERS.search(prompt_text):
        return {
            "category": "instruction_response",
            "reason": "prompt is phrased as an instruction/question with a paired response",
        }
    if modality == "conversation" or task == "conversation":
        return {
            "category": "conversation",
            "reason": "record is structured as a multi-turn conversation",
        }

    if _VOLATILITY_MARKERS.search(lowered):
        return {
            "category": "volatile_knowledge",
            "reason": "content contains date/price/schedule/contact-style volatile markers -- "
            "defaults to RAG rather than training",
        }
    if _PROCEDURAL_MARKERS.search(lowered) and not has_instruction:
        return {
            "category": "source_specific_fact",
            "reason": "content reads as a document-specific procedure without a governed "
            "instruction/response transformation -- defaults to RAG",
        }
    if task in ("grammar", "language_pattern"):
        return {"category": task, "reason": f"record is explicitly tagged '{task}'"}
    if not has_instruction and len(combined) > 0:
        return {
            "category": "general_text_corpus",
            "reason": "plain language text with no instruction/response structure and no "
            "volatility markers -- a tokenizer/pretraining candidate, not an SFT candidate",
        }
    return {
        "category": "stable_knowledge",
        "reason": "no training-shaped structure detected -- defaults to RAG as stable "
        "reference knowledge",
    }


def route_category(category: str) -> dict[str, Any]:
    """Deterministic Step 4 routing table. Returns
    ``{"suitability_status": ..., "reason": ...}``. Never grants
    approval -- only a routing recommendation for the assessment
    service, which still requires every other Step 3 dimension to pass
    and, later, explicit human review and Admin approval."""

    if category in SFT_CANDIDATE_CATEGORIES:
        return {
            "suitability_status": "suitable_for_sft",
            "reason": f"'{category}' is a high-quality instruction/response-shaped category "
            "-- routed to SFT candidacy, pending transformation and review",
        }
    if category in PRETRAINING_OR_TOKENIZER_CANDIDATE_CATEGORIES:
        return {
            "suitability_status": "suitable_for_pretraining",
            "reason": f"'{category}' is general language-behavior content -- routed to "
            "continued-pretraining/tokenizer candidacy, not SFT",
        }
    if category in RAG_ONLY_CATEGORIES:
        return {
            "suitability_status": "rag_only",
            "reason": f"'{category}' is factual/volatile/document-specific content -- "
            "facts, current procedures, and changing knowledge default to RAG, never training",
        }
    if category in EVALUATION_ONLY_CATEGORIES:
        return {
            "suitability_status": "evaluation_only",
            "reason": "evaluation/benchmark content can never enter training",
        }
    if category in BLOCKED_CATEGORIES:
        return {
            "suitability_status": "blocked",
            "reason": "unsafe or restricted content is always blocked from training",
        }
    return {
        "suitability_status": "not_assessed",
        "reason": f"unrecognized category '{category}'",
    }


__all__ = ["classify_record_category", "route_category"]
