"""MB-05.1: Advanced Dataset Intelligence -- the only impure module in
this phase. Composes TWO existing, UNMODIFIED services as black boxes:

1. `MiniBrainDatasetIntelligenceService` (MB-05) -- called for its own
   PUBLIC outputs (`.language()`, `.domain()`, `.analyze()`) so this
   phase never recomputes language distribution, domain topic scores,
   or record-type counts a second time. This is the literal
   "reuse MB-05 public outputs, never duplicate MB-05 logic" rule.
2. `DatasetService` (Dataset Studio's own service, same one MB-05
   itself composes) -- called for its own read-only `get_source()` /
   `list_records()`, using the identical bounded-pagination pattern
   MB-05 established (100 records/page, capped at
   `MAX_RECORDS_PER_ANALYSIS`), since MB-05 does not expose a "give me
   the raw records" method of its own to call instead.

No code path here can create, update, delete, approve, or transition
anything -- only these read methods are ever called.
"""

from __future__ import annotations

import time
from typing import Any

from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_dataset_intelligence_service import MiniBrainDatasetIntelligenceService
from core_model.mini_brain.dataset_advanced.advanced_dataset_score import compute_advanced_scores
from core_model.mini_brain.dataset_advanced.curriculum_analyzer import analyze_curriculum
from core_model.mini_brain.dataset_advanced.dataset_bias_analyzer import analyze_bias
from core_model.mini_brain.dataset_advanced.dataset_conflict_analyzer import detect_conflicts
from core_model.mini_brain.dataset_advanced.dataset_coverage_analyzer import analyze_coverage
from core_model.mini_brain.dataset_advanced.dataset_difficulty_analyzer import analyze_difficulty
from core_model.mini_brain.dataset_advanced.dataset_graph_builder import build_graph
from core_model.mini_brain.dataset_advanced.dataset_priority_engine import rank_priorities
from core_model.mini_brain.dataset_advanced.dataset_risk_analyzer import analyze_risk
from core_model.mini_brain.dataset_advanced.knowledge_gap_analyzer import analyze_knowledge_gaps

PAGE_SIZE = 100
MAX_RECORDS_PER_ANALYSIS = 500


class MiniBrainAdvancedDatasetService:
    def __init__(self, dataset_service: DatasetService, dataset_intelligence_service: MiniBrainDatasetIntelligenceService) -> None:
        self.dataset_service = dataset_service
        self.dataset_intelligence_service = dataset_intelligence_service

    def _fetch_records(self, source_public_id: str) -> tuple[list[dict[str, Any]], bool]:
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
        return records[:MAX_RECORDS_PER_ANALYSIS], truncated

    def conflicts(self, source_public_id: str) -> dict[str, Any]:
        records, truncated = self._fetch_records(source_public_id)
        result = detect_conflicts(records)
        result["analysis_truncated"] = truncated
        return result

    def bias(self, source_public_id: str) -> dict[str, Any]:
        records, truncated = self._fetch_records(source_public_id)
        language_result = self.dataset_intelligence_service.language(source_public_id)
        dataset_result = self.dataset_intelligence_service.analyze(source_public_id)
        domain_result = self.dataset_intelligence_service.domain(source_public_id)
        result = analyze_bias(
            records=records, language_counts=language_result["distribution_counts"],
            record_type_counts=dataset_result["by_record_type"], domain_topic_scores=domain_result["topic_scores"],
        )
        result["analysis_truncated"] = truncated
        return result

    def coverage(self, source_public_id: str) -> dict[str, Any]:
        records, truncated = self._fetch_records(source_public_id)
        result = analyze_coverage(records)
        return {"coverage": result, "analysis_truncated": truncated}

    def difficulty(self, source_public_id: str) -> dict[str, Any]:
        records, truncated = self._fetch_records(source_public_id)
        result = analyze_difficulty(records)
        result["analysis_truncated"] = truncated
        return result

    def curriculum(self, source_public_id: str) -> dict[str, Any]:
        records, truncated = self._fetch_records(source_public_id)
        coverage_result = analyze_coverage(records)
        difficulty_result = analyze_difficulty(records)
        result = analyze_curriculum(coverage=coverage_result, difficulty_by_id=difficulty_result["difficulty_by_id"])
        result["analysis_truncated"] = truncated
        return result

    def knowledge_gap(self, source_public_id: str) -> dict[str, Any]:
        records, truncated = self._fetch_records(source_public_id)
        result = analyze_knowledge_gaps(records)
        result["analysis_truncated"] = truncated
        return result

    def risk(self, source_public_id: str) -> dict[str, Any]:
        records, truncated = self._fetch_records(source_public_id)
        result = analyze_risk(records)
        result["analysis_truncated"] = truncated
        return result

    def graph(self, source_public_id: str) -> dict[str, Any]:
        records, truncated = self._fetch_records(source_public_id)
        coverage_result = analyze_coverage(records)
        records_by_id = {record.get("public_id"): record for record in records}
        result = build_graph(coverage=coverage_result, records_by_id=records_by_id)
        result["analysis_truncated"] = truncated
        return result

    def priority(self, source_public_id: str) -> dict[str, Any]:
        report = self.report(source_public_id)
        return {"priorities": report["priorities"], "analysis_truncated": report["analysis_truncated"]}

    def report(self, source_public_id: str) -> dict[str, Any]:
        started = time.perf_counter()
        records, truncated = self._fetch_records(source_public_id)

        language_result = self.dataset_intelligence_service.language(source_public_id)
        dataset_result = self.dataset_intelligence_service.analyze(source_public_id)
        domain_result = self.dataset_intelligence_service.domain(source_public_id)

        conflicts_result = detect_conflicts(records)
        bias_result = analyze_bias(
            records=records, language_counts=language_result["distribution_counts"],
            record_type_counts=dataset_result["by_record_type"], domain_topic_scores=domain_result["topic_scores"],
        )
        coverage_result = analyze_coverage(records)
        difficulty_result = analyze_difficulty(records)
        curriculum_result = analyze_curriculum(coverage=coverage_result, difficulty_by_id=difficulty_result["difficulty_by_id"])
        knowledge_gap_result = analyze_knowledge_gaps(records)
        risk_result = analyze_risk(records)
        records_by_id = {record.get("public_id"): record for record in records}
        graph_result = build_graph(coverage=coverage_result, records_by_id=records_by_id)

        priorities = rank_priorities(
            conflicts=conflicts_result, bias=bias_result, curriculum=curriculum_result,
            knowledge_gaps=knowledge_gap_result, risk=risk_result,
        )
        scores = compute_advanced_scores(
            conflicts=conflicts_result, bias=bias_result, coverage=coverage_result,
            difficulty=difficulty_result, curriculum=curriculum_result,
            knowledge_gaps=knowledge_gap_result, risk=risk_result,
        )

        return {
            "conflicts": conflicts_result,
            "bias": bias_result,
            "coverage": coverage_result,
            "difficulty": difficulty_result,
            "curriculum": curriculum_result,
            "knowledge_gaps": knowledge_gap_result,
            "risk": risk_result,
            "graph": graph_result,
            "priorities": priorities,
            "scores": scores,
            "records_analyzed": len(records),
            "analysis_truncated": truncated,
            "processing_time_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "pipeline_stages": [
                "dataset_conflict_analyzer", "dataset_bias_analyzer", "dataset_coverage_analyzer",
                "dataset_difficulty_analyzer", "curriculum_analyzer", "knowledge_gap_analyzer",
                "dataset_risk_analyzer", "dataset_graph_builder", "dataset_priority_engine",
                "advanced_dataset_score",
            ],
            "reused_existing_services": [
                "ExternalDatasetDuplicateService.find_conflicts (unmodified)",
                "ExternalDatasetPIIScanService.scan (unmodified)",
                "DatasetService.get_source / list_records (unmodified, read-only calls only)",
            ],
            "reused_mb05_outputs": [
                "MiniBrainDatasetIntelligenceService.language (unmodified)",
                "MiniBrainDatasetIntelligenceService.domain (unmodified)",
                "MiniBrainDatasetIntelligenceService.analyze (unmodified)",
            ],
            "database_tables": 0,
            "ai_model_used": False,
            "writes_performed": 0,
            "max_records_per_analysis": MAX_RECORDS_PER_ANALYSIS,
        }
