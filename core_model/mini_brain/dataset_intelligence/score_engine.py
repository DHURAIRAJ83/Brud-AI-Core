"""MB-05: Dataset Score Engine -- every score is a plain arithmetic
formula over the other analyzers' already-computed numbers. No hidden
weights: `overall` is an explicit, stated UNWEIGHTED mean of the 8
component scores -- the most transparent possible aggregation, and
every component score states its own formula, the actual numbers used
to calculate it, and a one-line reason.
"""

from __future__ import annotations

from typing import Any


def _score_entry(*, score: float, formula: str, calculation: str, reason: str) -> dict[str, Any]:
    return {"score": max(0, min(100, round(score))), "formula": formula, "calculation": calculation, "reason": reason}


def compute_scores(
    *, dataset: dict[str, Any], quality: dict[str, Any], language: dict[str, Any],
    training: dict[str, Any], rag: dict[str, Any], sft: dict[str, Any],
) -> dict[str, Any]:
    populated = dataset["populated_fields"]
    total_records = dataset["record_count"] or 1
    field_ratios = [
        v["populated"] / total_records for v in populated.values()
    ]
    structure_avg = sum(field_ratios) / len(field_ratios) if field_ratios else 0.0
    structure = _score_entry(
        score=structure_avg * 100,
        formula="mean(populated_ratio for each of instruction/input_text/output_text/normalized_input)",
        calculation=f"mean({[round(r, 3) for r in field_ratios]}) = {round(structure_avg, 3)}",
        reason="how completely the dataset's own content fields are filled in",
    )

    clean_ratio = quality.get("clean_ratio") or 0.0
    quality_score = _score_entry(
        score=clean_ratio * 100,
        formula="clean_records / total_records * 100",
        calculation=f"{quality['clean_records']} / {quality['total_records']} = {clean_ratio}",
        reason="share of records with zero detected quality issues",
    )

    total = language["total_records"] or 1
    mismatch_ratio = language.get("declared_language_mismatches", 0) / total
    language_score = _score_entry(
        score=(1 - mismatch_ratio) * 100,
        formula="(1 - declared_language_mismatches / total_records) * 100",
        calculation=f"(1 - {language['declared_language_mismatches']}/{total}) = {round(1 - mismatch_ratio, 3)}",
        reason="share of records whose declared language matches the detected language",
    )

    training_score = _score_entry(
        score=training["clean_ratio"] * (1 - training["duplicate_ratio"]) * 100,
        formula="clean_ratio * (1 - duplicate_ratio) * 100",
        calculation=f"{training['clean_ratio']} * (1 - {training['duplicate_ratio']}) = {round(training['clean_ratio'] * (1 - training['duplicate_ratio']), 3)}",
        reason="training readiness combines document cleanliness and exact-duplicate rate",
    )

    rag_score = _score_entry(
        score=((rag["chunk_suitability_ratio"] + clean_ratio) / 2) * 100,
        formula="mean(chunk_suitability_ratio, quality clean_ratio) * 100",
        calculation=f"mean({rag['chunk_suitability_ratio']}, {clean_ratio}) = {round((rag['chunk_suitability_ratio'] + clean_ratio) / 2, 3)}",
        reason="RAG suitability combines chunk-size fit and document quality",
    )

    sft_completeness = sft.get("answer_completeness_ratio") or 0.0
    sft_instruction = sft.get("instruction_quality_ratio") or 0.0
    sft_score = _score_entry(
        score=((sft_completeness + sft_instruction) / 2) * 100,
        formula="mean(instruction_quality_ratio, answer_completeness_ratio) * 100",
        calculation=f"mean({sft_instruction}, {sft_completeness}) = {round((sft_completeness + sft_instruction) / 2, 3)}",
        reason="SFT suitability combines instruction presence and answer completeness",
    )

    metadata_key_count = len(dataset.get("metadata_keys_observed", []))
    documentation = _score_entry(
        score=min(100, metadata_key_count * 20),
        formula="min(100, distinct_metadata_keys_observed * 20)",
        calculation=f"min(100, {metadata_key_count} * 20) = {min(100, metadata_key_count * 20)}",
        reason="a simple, disclosed heuristic -- 5 or more distinct metadata keys reaches full score",
    )

    records_with_metadata = quality["total_records"] - quality.get("empty_content_records", 0)
    metadata_ratio = records_with_metadata / total_records if total_records else 0.0
    metadata_score = _score_entry(
        score=metadata_ratio * 100,
        formula="(records_with_non_empty_content) / total_records * 100",
        calculation=f"{records_with_metadata} / {total_records} = {round(metadata_ratio, 3)}",
        reason="share of records that carry any real content at all",
    )

    components = {
        "structure": structure, "quality": quality_score, "language": language_score,
        "training": training_score, "rag": rag_score, "sft": sft_score,
        "documentation": documentation, "metadata": metadata_score,
    }
    overall_value = sum(c["score"] for c in components.values()) / len(components)
    overall = _score_entry(
        score=overall_value,
        formula="unweighted mean of all 8 component scores -- no hidden weights",
        calculation=f"mean({[c['score'] for c in components.values()]}) = {round(overall_value, 1)}",
        reason="a single overall figure, transparently the plain average of every component above",
    )

    return {**components, "overall": overall}
