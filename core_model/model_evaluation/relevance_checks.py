"""Bounded, deterministic surface-relevance checks.

This measures ``surface_relevance`` — keyword/lexical overlap and basic
structural signals — never ``factual_correctness``. Keyword overlap alone
cannot prove a response is true or semantically correct, and this module
never claims that.
"""

from __future__ import annotations

from difflib import SequenceMatcher

GENERIC_RESPONSE_PHRASES = (
    "i don't know",
    "i am not sure",
    "i cannot answer",
    "no information",
    "unable to respond",
)


def _tokens(text: str) -> set[str]:
    return {token.strip(".,!?;:").lower() for token in text.split() if token.strip(".,!?;:")}


def keyword_presence(text: str, expected_keywords: list[str]) -> dict:
    if not expected_keywords:
        return {
            "check": "keyword_presence", "status": "not_evaluated", "present": [], "missing": [],
        }
    normalized = text.lower()
    present = [keyword for keyword in expected_keywords if keyword.lower() in normalized]
    missing = [keyword for keyword in expected_keywords if keyword.lower() not in normalized]
    status = "pass" if present else "fail"
    return {"check": "keyword_presence", "status": status, "present": present, "missing": missing}


def forbidden_keyword_absence(text: str, forbidden_keywords: list[str]) -> dict:
    if not forbidden_keywords:
        return {"check": "forbidden_keyword_absence", "status": "not_evaluated", "found": []}
    normalized = text.lower()
    found = [keyword for keyword in forbidden_keywords if keyword.lower() in normalized]
    status = "fail" if found else "pass"
    return {"check": "forbidden_keyword_absence", "status": status, "found": found}


def reference_concept_overlap(text: str, reference_answer: str | None) -> dict:
    if not reference_answer:
        return {
            "check": "reference_concept_overlap", "status": "not_evaluated", "overlap_ratio": None,
        }
    response_tokens = _tokens(text)
    reference_tokens = _tokens(reference_answer)
    if not reference_tokens:
        return {
            "check": "reference_concept_overlap", "status": "not_evaluated", "overlap_ratio": None,
        }
    overlap = len(response_tokens & reference_tokens) / len(reference_tokens)
    status = "pass" if overlap >= 0.2 else "warning" if overlap > 0 else "fail"
    return {"check": "reference_concept_overlap", "status": status, "overlap_ratio": overlap}


def prompt_topic_overlap(text: str, prompt: str) -> dict:
    response_tokens = _tokens(text)
    prompt_tokens = _tokens(prompt)
    if not prompt_tokens or not response_tokens:
        return {"check": "prompt_topic_overlap", "status": "not_evaluated", "overlap_ratio": None}
    overlap = len(response_tokens & prompt_tokens) / len(prompt_tokens)
    status = "pass" if overlap > 0 else "warning"
    return {"check": "prompt_topic_overlap", "status": status, "overlap_ratio": overlap}


def prompt_copy_ratio(text: str, prompt: str) -> dict:
    if not text or not prompt:
        return {"check": "prompt_copy_ratio", "status": "not_evaluated", "ratio": 0.0}
    matcher = SequenceMatcher(None, text, prompt, autojunk=False)
    match = matcher.find_longest_match(0, len(text), 0, len(prompt))
    ratio = match.size / max(1, len(text))
    status = "warning" if ratio > 0.6 else "pass"
    return {"check": "prompt_copy_ratio", "status": status, "ratio": ratio}


def response_length_bounds(text: str, *, min_chars: int = 1, max_chars: int = 4000) -> dict:
    length = len(text.strip())
    if length < min_chars:
        return {"check": "response_length_bounds", "status": "fail", "length": length}
    if length > max_chars:
        return {"check": "response_length_bounds", "status": "warning", "length": length}
    return {"check": "response_length_bounds", "status": "pass", "length": length}


def generic_response_detection(text: str) -> dict:
    normalized = text.strip().lower()
    matched = [phrase for phrase in GENERIC_RESPONSE_PHRASES if phrase in normalized]
    status = "warning" if matched else "pass"
    return {"check": "generic_response_detection", "status": status, "matched": matched}


def evaluate_surface_relevance(
    text: str,
    *,
    prompt: str,
    expected_keywords: list[str] | None,
    forbidden_keywords: list[str] | None,
    reference_answer: str | None,
) -> dict:
    checks = [
        keyword_presence(text, expected_keywords or []),
        forbidden_keyword_absence(text, forbidden_keywords or []),
        reference_concept_overlap(text, reference_answer),
        prompt_topic_overlap(text, prompt),
        prompt_copy_ratio(text, prompt),
        response_length_bounds(text),
        generic_response_detection(text),
    ]
    evaluated = [c for c in checks if c["status"] != "not_evaluated"]
    passed = sum(1 for c in evaluated if c["status"] == "pass")
    warned = sum(1 for c in evaluated if c["status"] == "warning")
    total = len(evaluated)
    score = None if total == 0 else (passed + 0.5 * warned) / total
    return {"surface_relevance_score": score, "checks": checks}
