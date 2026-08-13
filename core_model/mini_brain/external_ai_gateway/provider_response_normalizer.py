"""MB-21: Provider Response Normalizer -- pure. Converts each
provider client's already-consistent raw dispatch result (status/text/
latency_ms/error_message -- every `ProviderClientProtocol`
implementation already returns this exact shape) into a normalized
record with real, measured text statistics. Never invents structure
that isn't actually present -- section coverage is a simple keyword
presence check, never a fragile parse of provider-specific formatting.
"""

from __future__ import annotations

from typing import Any

_SECTION_KEYWORDS = {
    "candidate_facts": ("fact",),
    "candidate_explanations": ("explanation", "explain"),
    "candidate_examples": ("example",),
    "candidate_qa_pairs": ("question", "answer", "q:", "a:"),
    "candidate_references": ("reference", "source", "citation"),
}


def normalize_response(*, provider_key: str, raw_result: dict[str, Any], purpose: str) -> dict[str, Any]:
    status = raw_result["status"]
    text = raw_result.get("text")

    if status != "success" or not text:
        return {
            "provider_key": provider_key, "status": status, "normalized_text": None, "word_count": 0,
            "character_count": 0, "section_coverage": {}, "error_message": raw_result.get("error_message"),
            "latency_ms": raw_result.get("latency_ms"),
        }

    normalized_text = text.strip()
    section_coverage: dict[str, bool] = {}
    if purpose == "data_acquisition_assistance":
        lowered = normalized_text.lower()
        section_coverage = {
            section: any(keyword in lowered for keyword in keywords)
            for section, keywords in _SECTION_KEYWORDS.items()
        }

    return {
        "provider_key": provider_key, "status": "success", "normalized_text": normalized_text,
        "word_count": len(normalized_text.split()), "character_count": len(normalized_text),
        "section_coverage": section_coverage, "error_message": None,
        "latency_ms": raw_result.get("latency_ms"),
        "disclosure": (
            "section_coverage is a simple keyword-presence check, never a structured parse of "
            "provider-specific formatting -- it indicates the response likely touches on that "
            "category, not that it correctly or completely addresses it"
        ) if purpose == "data_acquisition_assistance" else None,
    }
