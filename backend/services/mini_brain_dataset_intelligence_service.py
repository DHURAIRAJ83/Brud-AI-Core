"""MB-05: Dataset Intelligence -- the only impure module in this
phase. Composes the EXISTING, UNMODIFIED `DatasetService`
(`backend/services/dataset_service.py`, Phase 3's own Dataset Studio
service) as a black box, calling only its read methods:
`get_source()` and `list_records()`. No other method on that service
is ever called -- there is no code path here that can create, update,
transition, review, or delete a source or record. This is analysis
only, structurally, not merely by convention.

Records are paged in bounded chunks (100 at a time, the same page
size Dataset Studio's own routes use) up to `MAX_RECORDS_PER_ANALYSIS`
-- a real, disclosed scope limit so one analysis call cannot become an
unbounded full-table scan, matching this codebase's own established
discipline (see `ExternalDatasetDuplicateService`'s own bounded-CPU/RAM
note).
"""

from __future__ import annotations

import time
from typing import Any

from backend.services.dataset_service import DatasetService
from core_model.mini_brain.dataset_intelligence.dataset_analyzer import analyze_dataset
from core_model.mini_brain.dataset_intelligence.domain_classifier import classify_domain
from core_model.mini_brain.dataset_intelligence.duplicate_analyzer import analyze_duplicates
from core_model.mini_brain.dataset_intelligence.language_analyzer import analyze_language
from core_model.mini_brain.dataset_intelligence.quality_analyzer import analyze_quality
from core_model.mini_brain.dataset_intelligence.rag_readiness import assess_rag_readiness
from core_model.mini_brain.dataset_intelligence.recommendation_engine import generate_recommendations
from core_model.mini_brain.dataset_intelligence.score_engine import compute_scores
from core_model.mini_brain.dataset_intelligence.sft_readiness import assess_sft_readiness
from core_model.mini_brain.dataset_intelligence.token_estimator import estimate_dataset_tokens
from core_model.mini_brain.dataset_intelligence.training_readiness import assess_training_readiness

PAGE_SIZE = 100
MAX_RECORDS_PER_ANALYSIS = 500


class MiniBrainDatasetIntelligenceService:
    def __init__(self, dataset_service: DatasetService) -> None:
        self.dataset_service = dataset_service

    def _fetch_source_and_records(self, source_public_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        source = self.dataset_service.get_source(source_public_id)
        records: list[dict[str, Any]] = []
        page = 1
        total = None
        while len(records) < MAX_RECORDS_PER_ANALYSIS:
            result = self.dataset_service.list_records({"source": source_public_id}, page, PAGE_SIZE)
            records.extend(result.items)
            total = result.total
            if len(result.items) < PAGE_SIZE or len(records) >= total:
                break
            page += 1
        truncated = total is not None and total > len(records)
        return source, records[:MAX_RECORDS_PER_ANALYSIS], truncated

    def analyze(self, source_public_id: str) -> dict[str, Any]:
        source, records, truncated = self._fetch_source_and_records(source_public_id)
        result = analyze_dataset(source=source, records=records)
        result["records_analyzed"] = len(records)
        result["analysis_truncated"] = truncated
        return result

    def quality(self, source_public_id: str) -> dict[str, Any]:
        source, records, truncated = self._fetch_source_and_records(source_public_id)
        result = analyze_quality(source_public_id=source_public_id, records=records)
        result["analysis_truncated"] = truncated
        return result

    def language(self, source_public_id: str) -> dict[str, Any]:
        _, records, truncated = self._fetch_source_and_records(source_public_id)
        result = analyze_language(records)
        result["analysis_truncated"] = truncated
        return result

    def domain(self, source_public_id: str) -> dict[str, Any]:
        _, records, truncated = self._fetch_source_and_records(source_public_id)
        language_result = analyze_language(records)
        dataset_result = analyze_dataset(source=self.dataset_service.get_source(source_public_id), records=records)
        result = classify_domain(
            records=records, language_percentages=language_result["distribution_percentages"],
            record_type_counts=dataset_result["by_record_type"],
        )
        result["analysis_truncated"] = truncated
        return result

    def training(self, source_public_id: str) -> dict[str, Any]:
        source, records, truncated = self._fetch_source_and_records(source_public_id)
        quality_result = analyze_quality(source_public_id=source_public_id, records=records)
        duplicates_result = analyze_duplicates(source=source, records=records)
        result = assess_training_readiness(record_count=len(records), quality=quality_result, duplicates=duplicates_result)
        result["analysis_truncated"] = truncated
        return result

    def rag(self, source_public_id: str) -> dict[str, Any]:
        source, records, truncated = self._fetch_source_and_records(source_public_id)
        quality_result = analyze_quality(source_public_id=source_public_id, records=records)
        duplicates_result = analyze_duplicates(source=source, records=records)
        language_result = analyze_language(records)
        result = assess_rag_readiness(records=records, quality=quality_result, duplicates=duplicates_result, language=language_result)
        result["analysis_truncated"] = truncated
        return result

    def sft(self, source_public_id: str) -> dict[str, Any]:
        _, records, truncated = self._fetch_source_and_records(source_public_id)
        quality_result = analyze_quality(source_public_id=source_public_id, records=records)
        result = assess_sft_readiness(records=records, quality=quality_result)
        result["analysis_truncated"] = truncated
        return result

    def tokens(self, source_public_id: str) -> dict[str, Any]:
        _, records, truncated = self._fetch_source_and_records(source_public_id)
        result = estimate_dataset_tokens(records)
        result["analysis_truncated"] = truncated
        return result

    def report(self, source_public_id: str) -> dict[str, Any]:
        started = time.perf_counter()
        source, records, truncated = self._fetch_source_and_records(source_public_id)

        dataset_result = analyze_dataset(source=source, records=records)
        quality_result = analyze_quality(source_public_id=source_public_id, records=records)
        language_result = analyze_language(records)
        duplicates_result = analyze_duplicates(source=source, records=records)
        domain_result = classify_domain(
            records=records, language_percentages=language_result["distribution_percentages"],
            record_type_counts=dataset_result["by_record_type"],
        )
        training_result = assess_training_readiness(record_count=len(records), quality=quality_result, duplicates=duplicates_result)
        rag_result = assess_rag_readiness(records=records, quality=quality_result, duplicates=duplicates_result, language=language_result)
        sft_result = assess_sft_readiness(records=records, quality=quality_result)
        scores = compute_scores(
            dataset=dataset_result, quality=quality_result, language=language_result,
            training=training_result, rag=rag_result, sft=sft_result,
        )
        recommendations = generate_recommendations(
            dataset=dataset_result, quality=quality_result, language=language_result,
            duplicates=duplicates_result, domain=domain_result, training=training_result,
            rag=rag_result, sft=sft_result,
        )

        warnings: list[str] = []
        if truncated:
            warnings.append(f"analysis truncated at {MAX_RECORDS_PER_ANALYSIS} records -- source has more")
        if quality_result["clean_ratio"] is not None and quality_result["clean_ratio"] < 0.5:
            warnings.append("majority of records have quality issues")
        high_priority_count = sum(1 for r in recommendations if r["priority"] == "high")

        overall_status = "Ready" if scores["overall"]["score"] >= 80 and not high_priority_count else (
            "Needs Improvement" if scores["overall"]["score"] >= 50 else "Not Ready"
        )

        return {
            "dataset_summary": dataset_result,
            "quality_report": quality_result,
            "language_report": language_result,
            "domain": domain_result,
            "duplicates": duplicates_result,
            "training_report": training_result,
            "rag_report": rag_result,
            "sft_report": sft_result,
            "scores": scores,
            "recommendations": recommendations,
            "warnings": warnings,
            "overall_status": overall_status,
            "records_analyzed": len(records),
            "analysis_truncated": truncated,
            "processing_time_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "pipeline_stages": [
                "dataset_analyzer", "quality_analyzer", "language_analyzer", "domain_classifier",
                "duplicate_analyzer", "token_estimator", "training_readiness", "rag_readiness",
                "sft_readiness", "score_engine", "recommendation_engine",
            ],
            "reused_existing_services": [
                "ExternalDatasetQualityService.assess (unmodified)",
                "ExternalDatasetDuplicateService.group_exact_duplicates (unmodified)",
                "core_model.corpus.language_detection.assess_language (unmodified)",
                "DatasetService.get_source / list_records (unmodified, read-only calls only)",
            ],
            "database_tables": 0,
            "ai_model_used": False,
            "writes_performed": 0,
            "max_records_per_analysis": MAX_RECORDS_PER_ANALYSIS,
        }
