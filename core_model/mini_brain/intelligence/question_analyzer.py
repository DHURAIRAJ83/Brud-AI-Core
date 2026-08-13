"""Question Analyzer -- the front door of the Brud Intelligence Engine.

Determines question type (a fixed, deterministic classification of
the question's *shape*, not its topic), delegates topic/intent
detection to `intent_engine.detect_intent`, and extracts a small set
of candidate subject/keyword signals for the later resolver stages to
refine. Nothing here is a guess dressed up as an answer: every output
field traces to a literal substring match against the question text.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.intelligence.intent_engine import detect_intent

_QUESTION_TYPE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("definition", ("what is", "what are", "what does", "define")),
    ("howto", ("how do i", "how to", "how can i", "how does one")),
    ("troubleshooting", ("why is", "why does", "why isn't", "why doesn't", "not working", "failing", "error")),
    ("status", ("status of", "is it running", "is it healthy", "current state", "what state")),
    ("comparison", (" vs ", " versus ", "difference between", "compare")),
    ("temporal", ("when did", "when will", "when should", "when is")),
    ("location", ("where is", "where can", "where do")),
    ("procedural", ("steps to", "process for", "workflow for")),
)


def _classify_question_type(text: str) -> str:
    for question_type, patterns in _QUESTION_TYPE_PATTERNS:
        if any(pattern in text for pattern in patterns):
            return question_type
    if text.strip().endswith("?"):
        return "general"
    return "statement"


def analyze_question(question: str) -> dict[str, Any]:
    text = question.strip().lower()
    question_type = _classify_question_type(text)
    intent_result = detect_intent(question)

    # Subject candidates: matched intent keywords plus any quoted
    # phrase in the raw question -- both are literal substrings of the
    # question, never inferred.
    quoted = [q for q in question.split('"')[1::2]]
    subject_candidates = list(dict.fromkeys(intent_result["matched_keywords"] + quoted))

    return {
        "question": question,
        "question_type": question_type,
        "intent": intent_result["intent"],
        "intent_confidence_signal": intent_result["confidence_signal"],
        "subject_candidates": subject_candidates,
        # Preliminary signal only -- Feature/Workflow/Context Resolver
        # do the real resolution against Knowledge Core; this is just
        # what's visible from the question text alone.
        "related_feature_signal": subject_candidates,
        "related_workflow_signal": subject_candidates,
        "related_knowledge_signal": subject_candidates,
    }
