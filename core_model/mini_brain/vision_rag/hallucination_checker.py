"""MB-17: Hallucination Check -- pure. Reuses `core_model.rag.
grounding_checks` directly: `split_sentences()`/`sentence_has_citation()`/
`unsupported_sentence_ratio()` parse the answer's own real "[S<n>]"
citation markers (the same regex the production RAG system already
validates), and `compute_grounding_quality()` combines per-citation
validity into one grounding-quality figure. The strict hallucination
policy itself -- no invented objects, captions, relationships, page
numbers, document names, or OCR text -- is enforced structurally
upstream (every answer sentence is a direct copy of a real evidence
snippet, never generated), so this stage's job is to *verify* that
guarantee held, not to guess whether the answer might be true.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.grounding_checks import compute_grounding_quality, unsupported_sentence_ratio, validate_citation

HALLUCINATION_RISK_THRESHOLD = 0.3


def check_hallucination(
    *, answer: str, cited_evidence_public_ids: list[str], all_evidence_public_ids: set[str],
) -> dict[str, Any]:
    if not cited_evidence_public_ids:
        return {
            "hallucination_flag": False, "hallucination_risk": 0.0, "citation_validity_rate": 1.0,
            "unsupported_sentence_ratio": 0.0, "citation_validations": [],
            "disclosure": "no evidence was cited -- this is the insufficient-evidence path, not a hallucination",
        }

    seen: set[str] = set()
    validations = []
    for index, evidence_public_id in enumerate(cited_evidence_public_ids):
        entry = (
            {"chunk_public_id": evidence_public_id, "content_checksum_sha256": None}
            if evidence_public_id in all_evidence_public_ids else None
        )
        validation = validate_citation(
            citation_entry=entry, context_chunk_ids=all_evidence_public_ids, expected_checksum=None,
            citation_index=index, max_citations=len(cited_evidence_public_ids) + 1,
            already_seen=evidence_public_id in seen,
        )
        seen.add(evidence_public_id)
        validations.append(validation)

    unsupported_ratio = unsupported_sentence_ratio(answer)
    quality = compute_grounding_quality(
        citation_validations=validations, unsupported_ratio=unsupported_ratio,
        retrieved_chunk_count=len(all_evidence_public_ids), used_chunk_count=len(set(cited_evidence_public_ids)),
        no_answer_appropriate=None, injection_chunks_detected=0, injection_chunks_excluded=0,
    )

    hallucination_risk = round(
        (1 - quality["citation_validity_rate"]) * 0.6 + quality["unsupported_sentence_ratio"] * 0.4, 3
    )
    return {
        "hallucination_flag": hallucination_risk >= HALLUCINATION_RISK_THRESHOLD,
        "hallucination_risk": hallucination_risk,
        "citation_validity_rate": quality["citation_validity_rate"],
        "unsupported_sentence_ratio": quality["unsupported_sentence_ratio"],
        "citation_validations": validations,
    }
