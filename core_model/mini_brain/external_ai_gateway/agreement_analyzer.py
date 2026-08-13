"""MB-21: Agreement Analyzer -- pure. Measures pairwise lexical
overlap (Jaccard word-set similarity, the same simple, disclosed
technique `core_model.mini_brain.vision_intelligence.ocr_cross_
validator.cross_validate_ocr()` already uses for text comparison)
between every pair of successful provider responses. This is a lexical
similarity proxy, never a semantic judgment of truth -- no majority
voting ever produces an automatic truth decision here.
"""

from __future__ import annotations

from typing import Any

CONTRADICTION_THRESHOLD = 0.1
_HEDGE_PHRASES = (
    "i'm not sure", "i am not sure", "i don't have", "i do not have", "i cannot verify",
    "i can't verify", "i am not certain", "i'm not certain", "no information", "unable to confirm",
    "cannot confirm",
)


def _word_overlap(text_a: str, text_b: str) -> float:
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    union = len(words_a | words_b) or 1
    return len(words_a & words_b) / union


def analyze_agreement(*, normalized_responses: list[dict[str, Any]]) -> dict[str, Any]:
    provider_count = len(normalized_responses)
    successful = [r for r in normalized_responses if r["status"] == "success" and r.get("normalized_text")]
    failed = [r for r in normalized_responses if r not in successful]
    successful_count = len(successful)
    failed_count = provider_count - successful_count

    pairwise_scores: list[float] = []
    for i in range(len(successful)):
        for j in range(i + 1, len(successful)):
            pairwise_scores.append(_word_overlap(successful[i]["normalized_text"], successful[j]["normalized_text"]))

    if pairwise_scores:
        agreement_score = round(sum(pairwise_scores) / len(pairwise_scores) * 100, 1)
    elif successful_count == 1:
        agreement_score = 100.0
    else:
        agreement_score = 0.0

    contradiction_count = sum(1 for score in pairwise_scores if score < CONTRADICTION_THRESHOLD)

    unsupported_claim_count = 0
    if successful_count > 1:
        for i, response in enumerate(successful):
            others = [o for j, o in enumerate(successful) if j != i]
            if all(_word_overlap(response["normalized_text"], o["normalized_text"]) < CONTRADICTION_THRESHOLD for o in others):
                unsupported_claim_count += 1

    hallucination_warning_count = sum(
        1 for r in successful if any(phrase in r["normalized_text"].lower() for phrase in _HEDGE_PHRASES)
    )

    return {
        "provider_count": provider_count, "successful_provider_count": successful_count,
        "failed_provider_count": failed_count, "agreement_score": agreement_score,
        "contradiction_count": contradiction_count, "unsupported_claim_count": unsupported_claim_count,
        "hallucination_warning_count": hallucination_warning_count,
        "failed_provider_keys": [r["provider_key"] for r in failed],
        "disclosure": (
            "agreement_score is pairwise lexical word-overlap, never a semantic truth judgment; "
            "contradiction_count flags low-overlap response pairs, not verified factual conflicts; "
            "unsupported_claim_count flags a response with no lexical corroboration from any other "
            "provider; hallucination_warning_count counts a provider's own hedge language, never a "
            "detector of actual hallucination. No majority voting here ever produces an automatic "
            "truth decision"
        ),
    }
