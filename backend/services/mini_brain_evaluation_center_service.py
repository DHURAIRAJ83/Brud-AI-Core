"""MB-19: Brud Mini Brain Evaluation & Benchmark Center -- the
orchestration layer for the 12-stage session-to-report workflow
described in the MB-19 task spec.

MB-19 is an evaluation-only system. It never starts a training job,
never fine-tunes, never exports GGUF, never quantizes, never deploys,
and never activates a runtime. It measures the quality of already-
certified MB-16 datasets, already-approved MB-17 grounded RAG
sessions, and already-built MB-18 training packages -- read exclusively
through their own public methods -- into MB-19's own tables and its
own export directory on disk. No upstream record, evidence row, or
package is ever modified.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_evaluation_center import (
    MiniBrainEvaluationCenterRepository,
    public_memory_row,
    public_result_row,
    public_session_row,
)
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService
from backend.services.mini_brain_vision_rag_service import MiniBrainVisionRagService
from core_model.mini_brain.evaluation_center.benchmark_export_builder import build_export_manifest
from core_model.mini_brain.evaluation_center.benchmark_registry import build_benchmark_suite
from core_model.mini_brain.evaluation_center.dataset_completeness_benchmark import (
    analyze_dataset_completeness,
)
from core_model.mini_brain.evaluation_center.evaluation_report_generator import generate_evaluation_report
from core_model.mini_brain.evaluation_center.grounding_benchmark import run_grounding_benchmark
from core_model.mini_brain.evaluation_center.language_benchmark import run_language_benchmark
from core_model.mini_brain.evaluation_center.multimodal_coverage_benchmark import (
    run_multimodal_coverage_benchmark,
)
from core_model.mini_brain.evaluation_center.ocr_benchmark import run_ocr_benchmark
from core_model.mini_brain.evaluation_center.package_integrity_benchmark import (
    run_package_integrity_benchmark,
)
from core_model.mini_brain.evaluation_center.regression_comparator import compare_against_baseline
from core_model.mini_brain.evaluation_center.release_readiness_evaluator import evaluate_release_readiness
from core_model.mini_brain.evaluation_center.retrieval_benchmark import run_retrieval_benchmark
from core_model.mini_brain.evaluation_center.score_aggregator import aggregate_scores
from core_model.release.artifact_inventory import file_checksum, resolve_confined_path
from core_model.release.manifest import manifest_checksum

ADMIN_DECISIONS = {"approve", "reject", "archive"}
ADMIN_STATUS_MAP = {"approve": "admin_approved", "reject": "admin_rejected", "archive": "admin_archived"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _timed(fn, /, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn(**kwargs)
    return result, round((time.perf_counter() - started) * 1000, 3)


class MiniBrainEvaluationCenterService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainEvaluationCenterRepository(settings.resolved_database_path)

        self.multimodal_dataset = MiniBrainMultimodalDatasetGeneratorService(settings)
        self.vision_rag = MiniBrainVisionRagService(settings)
        self.training_pipeline = MiniBrainTrainingPipelineService(settings)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, evaluation_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, evaluation_session_id=evaluation_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def _export_dir(self, session_public_id: str) -> Path:
        root = self.settings.resolved_document_dir.parent / "evaluation_exports"
        directory = root / session_public_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset)
        return {"items": [public_session_row(row) for row in rows]}

    def events(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_events(
                connection, evaluation_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def list_results(self, session_public_id: str, *, category: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_results(
                connection, evaluation_session_id=session_row["id"], category=category,
            )
        return {"items": [public_result_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    def _record_results(self, connection, evaluation_session_id: int, category: str, metrics: dict[str, Any]) -> None:
        for metric_name, metric_value in metrics.items():
            if isinstance(metric_value, bool) or not isinstance(metric_value, (int, float)):
                continue
            self.repository.create_result(
                connection, evaluation_session_id=evaluation_session_id, category=category,
                metric_name=metric_name, metric_value=float(metric_value), metric_status=None,
            )

    # -- stage 1: create evaluation session --------------------------------------

    def create_session(self, *, topic: str, admin_id: str) -> dict[str, Any]:
        if not topic.strip():
            raise ValidationError("topic must not be empty")
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(connection, topic=topic, created_by_admin_public_id=admin_id)
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="collect_datasets",
                message=f"evaluation session created for topic '{topic}'",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage 2: collect certified datasets -----------------------------------------

    def run_collect_datasets_stage(
        self, session_public_id: str, *, dataset_session_public_ids: list[str], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_datasets":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_datasets'")

        dataset_sessions = [self.multimodal_dataset.session(sid) for sid in dataset_session_public_ids]
        accepted = [s for s in dataset_sessions if s["status"] == "admin_approved"]
        rejected = [s["public_id"] for s in dataset_sessions if s["status"] != "admin_approved"]
        if not accepted:
            raise ValidationError("no certified (status='admin_approved') MB-16 dataset session was accepted")

        report = {
            "accepted_session_public_ids": [s["public_id"] for s in accepted],
            "rejected_session_public_ids": rejected,
            "accepted_count": len(accepted), "rejected_count": len(rejected),
            "disclosure": "only MB-16 sessions already certified (status='admin_approved') are ever accepted",
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "dataset_collection_report_json": report,
                    "source_dataset_public_ids_json": report["accepted_session_public_ids"],
                    "stage": "collect_rag_sessions",
                },
            )
            self._event(
                connection, session_row["id"], "datasets_collected", stage="collect_datasets",
                message=f"{report['accepted_count']} certified dataset(s) accepted, {report['rejected_count']} rejected",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 3: collect approved RAG sessions -------------------------------------------

    def run_collect_rag_sessions_stage(
        self, session_public_id: str, *, rag_session_public_ids: list[str], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_rag_sessions":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_rag_sessions'")

        rag_sessions = [self.vision_rag.session(sid) for sid in rag_session_public_ids]
        accepted = [s for s in rag_sessions if s.get("admin_decision") == "approve"]
        rejected = [s["public_id"] for s in rag_sessions if s.get("admin_decision") != "approve"]

        report = {
            "accepted_session_public_ids": [s["public_id"] for s in accepted],
            "rejected_session_public_ids": rejected,
            "accepted_count": len(accepted), "rejected_count": len(rejected),
            "disclosure": "only MB-17 sessions with a final admin_decision='approve' are ever accepted; zero accepted sessions is still valid",
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "rag_collection_report_json": report,
                    "source_rag_session_public_ids_json": report["accepted_session_public_ids"],
                    "stage": "collect_training_packages",
                },
            )
            self._event(
                connection, session_row["id"], "rag_sessions_collected", stage="collect_rag_sessions",
                message=f"{report['accepted_count']} approved RAG session(s) accepted, {report['rejected_count']} rejected",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 4: collect training packages -------------------------------------------

    def run_collect_training_packages_stage(
        self, session_public_id: str, *, training_package_session_public_ids: list[str], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_training_packages":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_training_packages'")

        package_sessions = [self.training_pipeline.session(sid) for sid in training_package_session_public_ids]
        accepted = [
            s for s in package_sessions
            if s["status"] == "admin_approved" and s.get("package_directory") and s["package_manifest"].get("artifact_count", 0) > 0
        ]
        rejected = [s["public_id"] for s in package_sessions if s not in accepted]

        report = {
            "accepted_session_public_ids": [s["public_id"] for s in accepted],
            "rejected_session_public_ids": rejected,
            "accepted_count": len(accepted), "rejected_count": len(rejected),
            "disclosure": "only MB-18 sessions that are admin_approved and have a real, non-empty built package are ever accepted",
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "package_collection_report_json": report,
                    "source_training_package_public_ids_json": report["accepted_session_public_ids"],
                    "stage": "run_language_benchmarks",
                },
            )
            self._event(
                connection, session_row["id"], "training_packages_collected", stage="collect_training_packages",
                message=f"{report['accepted_count']} certified training package(s) accepted, {report['rejected_count']} rejected",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- helpers: gather text/records/evidence across accepted sources, streamed --------

    def _iter_dataset_records(self, dataset_session_public_ids: list[str]):
        for dataset_session_public_id in dataset_session_public_ids:
            records = self.multimodal_dataset.list_records(dataset_session_public_id, status="active")["items"]
            yield from records

    def _record_text(self, record: dict[str, Any]) -> str | None:
        content = record["content"]
        if record["record_type"] in ("conversation", "qa"):
            return " ".join(filter(None, [content.get("user"), str(content.get("assistant") or "")]))
        if record["record_type"] in ("instruction", "training"):
            return " ".join(filter(None, [content.get("instruction"), str(content.get("output") or "")]))
        if record["record_type"] == "caption":
            return content.get("caption")
        if record["record_type"] == "reasoning":
            return content.get("statement")
        return None

    # -- stage 5: run language benchmarks ------------------------------------------

    def run_language_benchmarks_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_language_benchmarks":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_language_benchmarks'")

        texts = [
            text for record in self._iter_dataset_records(session_data["source_dataset_public_ids"])
            if (text := self._record_text(record))
        ]
        report, latency_ms = _timed(run_language_benchmark, texts=texts)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"language_benchmark_report_json": report, "stage": "run_ocr_benchmarks"},
            )
            self._record_results(connection, session_row["id"], "language", report)
            self._event(
                connection, session_row["id"], "language_benchmarks_run", stage="run_language_benchmarks",
                message=f"{report['records_analyzed']} record(s) analyzed",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: run OCR benchmarks -------------------------------------------------

    def run_ocr_benchmarks_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_ocr_benchmarks":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_ocr_benchmarks'")

        evidence_groups = []
        for rag_session_public_id in session_data["source_rag_session_public_ids"]:
            evidence = self.vision_rag.list_evidence(rag_session_public_id)["items"]
            evidence_groups.append({
                "ocr_snippets": [e["content_snippet"] for e in evidence if e["evidence_type"] == "ocr" and e["content_snippet"]],
                "text_snippets": [e["content_snippet"] for e in evidence if e["evidence_type"] == "text" and e["content_snippet"]],
            })

        report, latency_ms = _timed(run_ocr_benchmark, evidence_groups=evidence_groups)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"ocr_benchmark_report_json": report, "stage": "run_grounding_retrieval_benchmarks"},
            )
            self._record_results(connection, session_row["id"], "ocr", report)
            self._event(
                connection, session_row["id"], "ocr_benchmarks_run", stage="run_ocr_benchmarks",
                message=f"{report['session_count']} RAG session(s) evaluated",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: run grounding & retrieval benchmarks --------------------------------

    def run_grounding_retrieval_benchmarks_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_grounding_retrieval_benchmarks":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_grounding_retrieval_benchmarks'")

        grounding_inputs = []
        retrieval_inputs = []
        for rag_session_public_id in session_data["source_rag_session_public_ids"]:
            rag_session = self.vision_rag.session(rag_session_public_id)
            evidence = self.vision_rag.list_evidence(rag_session_public_id)["items"]
            cited_count = sum(1 for e in evidence if e["used_in_answer"])
            relevance_scores = [e["relevance_score"] for e in evidence if e.get("relevance_score") is not None]
            grounding_inputs.append({
                "answer": rag_session.get("answer_report", {}).get("answer"),
                "citation_validity_rate": rag_session.get("hallucination_report", {}).get("citation_validity_rate"),
                "cited_evidence_count": cited_count,
                "total_evidence_count": len(evidence),
            })
            retrieval_inputs.append({
                "evidence_count": len(evidence),
                "average_relevance_score": (
                    round(sum(relevance_scores) / len(relevance_scores), 3) if relevance_scores else None
                ),
                "answer_status": rag_session.get("answer_report", {}).get("status"),
            })

        grounding_report, grounding_latency_ms = _timed(run_grounding_benchmark, rag_sessions=grounding_inputs)
        retrieval_report, retrieval_latency_ms = _timed(run_retrieval_benchmark, rag_sessions=retrieval_inputs)
        grounding_report["latency_ms"] = grounding_latency_ms
        retrieval_report["latency_ms"] = retrieval_latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "grounding_benchmark_report_json": grounding_report,
                    "retrieval_benchmark_report_json": retrieval_report, "stage": "run_multimodal_benchmarks",
                },
            )
            self._record_results(connection, session_row["id"], "grounding", grounding_report)
            self._record_results(connection, session_row["id"], "retrieval", retrieval_report)
            self._event(
                connection, session_row["id"], "grounding_retrieval_benchmarks_run",
                stage="run_grounding_retrieval_benchmarks",
                message=f"{grounding_report['session_count']} RAG session(s) evaluated",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: run multimodal coverage benchmarks -----------------------------------

    def run_multimodal_benchmarks_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_multimodal_benchmarks":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_multimodal_benchmarks'")

        record_type_counts: dict[str, int] = {}
        for record in self._iter_dataset_records(session_data["source_dataset_public_ids"]):
            record_type_counts[record["record_type"]] = record_type_counts.get(record["record_type"], 0) + 1

        evidence_type_counts: dict[str, int] = {}
        for rag_session_public_id in session_data["source_rag_session_public_ids"]:
            evidence = self.vision_rag.list_evidence(rag_session_public_id)["items"]
            for e in evidence:
                evidence_type_counts[e["evidence_type"]] = evidence_type_counts.get(e["evidence_type"], 0) + 1

        report, latency_ms = _timed(
            run_multimodal_coverage_benchmark, record_type_counts=record_type_counts,
            evidence_type_counts=evidence_type_counts,
        )
        report["latency_ms"] = latency_ms

        dataset_sessions = []
        for dataset_session_public_id in session_data["source_dataset_public_ids"]:
            dataset_session = self.multimodal_dataset.session(dataset_session_public_id)
            record_count = len(self.multimodal_dataset.list_records(dataset_session_public_id, status="active")["items"])
            dataset_sessions.append({
                "quality_report": dataset_session.get("quality_report", {}),
                "duplicate_report": dataset_session.get("duplicate_report", {}),
                "record_count": record_count,
            })
        completeness_report, completeness_latency_ms = _timed(
            analyze_dataset_completeness, dataset_sessions=dataset_sessions,
        )
        report["dataset_completeness"] = completeness_report
        report["dataset_completeness_latency_ms"] = completeness_latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"multimodal_benchmark_report_json": report, "stage": "run_package_benchmarks"},
            )
            self._record_results(connection, session_row["id"], "multimodal", report)
            self._event(
                connection, session_row["id"], "multimodal_benchmarks_run", stage="run_multimodal_benchmarks",
                message=f"{report['total_record_count']} record(s), {report['total_evidence_count']} evidence row(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: run package integrity benchmarks ----------------------------------------

    def run_package_benchmarks_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_package_benchmarks":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_package_benchmarks'")

        package_checks = []
        for package_session_public_id in session_data["source_training_package_public_ids"]:
            package_session = self.training_pipeline.session(package_session_public_id)
            package_dir = Path(package_session["package_directory"])
            manifest = dict(package_session["package_manifest"])
            reproducibility = manifest.pop("reproducibility", {})
            manifest.pop("build_latency_ms", None)
            expected_checksum = reproducibility.get("manifest_checksum_sha256")
            checksum_valid = manifest_checksum(manifest) == expected_checksum if expected_checksum else None

            packages = self.training_pipeline.list_packages(package_session_public_id)["items"]
            artifact_count_consistent = len(packages) == manifest.get("artifact_count", 0) + 2

            missing_or_corrupt = 0
            for pkg in packages:
                path = package_dir / pkg["relative_path"]
                if not path.exists() or file_checksum(path) != pkg["sha256"]:
                    missing_or_corrupt += 1

            package_checks.append({
                "session_public_id": package_session_public_id, "manifest_checksum_valid": checksum_valid,
                "artifact_count_consistent": artifact_count_consistent,
                "missing_or_corrupt_file_count": missing_or_corrupt,
            })

        report, latency_ms = _timed(run_package_integrity_benchmark, package_checks=package_checks)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"package_benchmark_report_json": report, "stage": "run_regression_comparison"},
            )
            self._record_results(connection, session_row["id"], "package", report)
            self._event(
                connection, session_row["id"], "package_benchmarks_run", stage="run_package_benchmarks",
                message=f"{report['package_count']} package(s) evaluated, {report['missing_file_count']} missing/corrupt file(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- category composite scoring ------------------------------------------------------

    def _category_scores(self, session_data: dict[str, Any]) -> dict[str, float | None]:
        language = session_data["language_benchmark_report"]
        ocr = session_data["ocr_benchmark_report"]
        grounding = session_data["grounding_benchmark_report"]
        retrieval = session_data["retrieval_benchmark_report"]
        multimodal = session_data["multimodal_benchmark_report"]
        package = session_data["package_benchmark_report"]

        language_components = [
            v for v in (
                language.get("unicode_integrity"), language.get("tamil_character_validity"),
                language.get("tanglish_normalization_coverage"), language.get("language_consistency"),
            ) if v is not None
        ]
        language_score = round(sum(language_components) / len(language_components), 1) if language_components else None

        ocr_score = None
        if ocr.get("ocr_text_availability") is not None:
            conflict = ocr.get("ocr_conflict_ratio") or 0.0
            ocr_score = round(ocr["ocr_text_availability"] * (1 - conflict) * 100, 1)

        grounding_components = [
            v for v in (grounding.get("citation_validity_rate"), grounding.get("evidence_coverage_rate")) if v is not None
        ]
        unsupported = grounding.get("unsupported_sentence_ratio")
        grounding_score = None
        if grounding_components or unsupported is not None:
            base = sum(grounding_components) / len(grounding_components) if grounding_components else 1.0
            penalty = unsupported if unsupported is not None else 0.0
            grounding_score = round(max(0.0, base - penalty) * 100, 1)

        retrieval_components = [
            v for v in (retrieval.get("topk_evidence_availability"), retrieval.get("average_relevance_score")) if v is not None
        ]
        retrieval_score = round(sum(retrieval_components) / len(retrieval_components) * 100, 1) if retrieval_components else None

        multimodal_components = [
            v for v in (
                multimodal.get("image_coverage"), multimodal.get("object_coverage"),
                multimodal.get("qa_coverage"), multimodal.get("knowledge_graph_coverage"),
            ) if v is not None
        ]
        multimodal_score = round(sum(multimodal_components) / len(multimodal_components) * 100, 1) if multimodal_components else None

        package_components = [
            v for v in (package.get("manifest_checksum_validity_rate"), package.get("artifact_count_consistency_rate")) if v is not None
        ]
        package_score = round(sum(package_components) / len(package_components) * 100, 1) if package_components else None

        return {
            "language": language_score, "ocr": ocr_score, "grounding": grounding_score,
            "retrieval": retrieval_score, "multimodal": multimodal_score, "package": package_score,
        }

    def _flat_ratio_metrics(self, session_data: dict[str, Any]) -> dict[str, float | None]:
        """Every metric here is normalized to a 0-1 scale (dividing any
        0-100 composite score by 100) so `regression_comparator.py`'s
        summed drift score stays meaningful across mixed metric types."""
        category_scores = self._category_scores(session_data)
        flat: dict[str, float | None] = {
            f"{name}_score": (value / 100.0 if value is not None else None) for name, value in category_scores.items()
        }
        grounding = session_data["grounding_benchmark_report"]
        retrieval = session_data["retrieval_benchmark_report"]
        package = session_data["package_benchmark_report"]
        flat["citation_validity_rate"] = grounding.get("citation_validity_rate")
        flat["unsupported_sentence_ratio"] = grounding.get("unsupported_sentence_ratio")
        flat["topk_evidence_availability"] = retrieval.get("topk_evidence_availability")
        flat["insufficient_evidence_rate"] = retrieval.get("insufficient_evidence_rate")
        flat["artifact_count_consistency_rate"] = package.get("artifact_count_consistency_rate")
        return flat

    # -- stage 10: run regression comparison ----------------------------------------------

    def run_regression_comparison_stage(
        self, session_public_id: str, *, admin_id: str, baseline_session_public_id: str | None = None,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_regression_comparison":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_regression_comparison'")

        current_metrics = self._flat_ratio_metrics(session_data)

        baseline_metrics: dict[str, float | None] | None = None
        if baseline_session_public_id:
            baseline_session = self.session(baseline_session_public_id)
            if baseline_session["status"] != "admin_approved":
                raise ValidationError("baseline_session_public_id must reference an admin_approved evaluation session")
            baseline_metrics = self._flat_ratio_metrics(baseline_session)
        else:
            with self.repository.transaction() as connection:
                approved_rows = connection.execute(
                    "SELECT * FROM mini_brain_evaluation_sessions WHERE status='admin_approved' AND public_id != ? ORDER BY id DESC LIMIT 1",
                    (session_public_id,),
                ).fetchall()
            if approved_rows:
                baseline_metrics = self._flat_ratio_metrics(public_session_row(approved_rows[0]))

        report, latency_ms = _timed(
            compare_against_baseline, current_metrics=current_metrics, baseline_metrics=baseline_metrics,
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"regression_report_json": report, "stage": "generate_report"},
            )
            self._event(
                connection, session_row["id"], "regression_comparison_run", stage="run_regression_comparison",
                message=f"risk={report['release_risk_level']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11: generate evaluation & release readiness report, build exports ----------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "generate_report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'generate_report'")

        category_scores = self._category_scores(session_data)
        score_summary = aggregate_scores(category_scores=category_scores)

        package = session_data["package_benchmark_report"]
        package_integrity_ok = (
            package.get("missing_file_count", 0) == 0
            and (package.get("artifact_count_consistency_rate") in (1.0, None))
            and (package.get("manifest_checksum_validity_rate") in (1.0, None))
        )

        readiness = evaluate_release_readiness(
            overall_score=score_summary["overall_score"], grounding_composite_score=category_scores["grounding"],
            package_integrity_ok=package_integrity_ok,
            ocr_conflict_ratio=session_data["ocr_benchmark_report"].get("ocr_conflict_ratio"),
            drift_score=session_data["regression_report"].get("overall_drift_score"),
        )

        suite = build_benchmark_suite(
            topic=session_data["topic"], source_dataset_count=len(session_data["source_dataset_public_ids"]),
            source_rag_session_count=len(session_data["source_rag_session_public_ids"]),
            source_training_package_count=len(session_data["source_training_package_public_ids"]),
        )

        report = generate_evaluation_report(
            session_public_id=session_public_id, topic=session_data["topic"],
            dataset_collection_report=session_data["dataset_collection_report"],
            rag_collection_report=session_data["rag_collection_report"],
            package_collection_report=session_data["package_collection_report"],
            language_benchmark_report=session_data["language_benchmark_report"],
            ocr_benchmark_report=session_data["ocr_benchmark_report"],
            grounding_benchmark_report=session_data["grounding_benchmark_report"],
            retrieval_benchmark_report=session_data["retrieval_benchmark_report"],
            multimodal_benchmark_report=session_data["multimodal_benchmark_report"],
            package_benchmark_report=session_data["package_benchmark_report"],
            regression_report=session_data["regression_report"], score_summary=score_summary,
            release_readiness=readiness,
        )

        # -- build export artifacts ------------------------------------------------
        export_dir = self._export_dir(session_public_id)
        started = time.perf_counter()
        export_payloads = {
            "benchmark_summary.json": {
                "category_scores": category_scores, "overall_score": score_summary["overall_score"],
                "benchmark_suite": suite,
            },
            "benchmark_details.json": {
                "language": session_data["language_benchmark_report"], "ocr": session_data["ocr_benchmark_report"],
                "grounding": session_data["grounding_benchmark_report"],
                "retrieval": session_data["retrieval_benchmark_report"],
                "multimodal": session_data["multimodal_benchmark_report"],
                "package": session_data["package_benchmark_report"],
            },
            "regression_report.json": session_data["regression_report"],
            "release_readiness.json": readiness,
        }
        artifact_entries = []
        for artifact_name, payload in export_payloads.items():
            path = resolve_confined_path(export_dir, artifact_name)
            path.write_text(dumps_json(payload), encoding="utf-8")
            checksum = file_checksum(path)
            artifact_entries.append({
                "artifact_name": artifact_name, "relative_path": artifact_name, "sha256": checksum,
                "file_size_bytes": path.stat().st_size,
            })

        manifest = build_export_manifest(
            session_public_id=session_public_id, topic=session_data["topic"],
            overall_score=score_summary["overall_score"], release_readiness_status=readiness["status"],
            artifact_entries=artifact_entries, created_at=_now(),
        )
        manifest_path = resolve_confined_path(export_dir, "export_manifest.json")
        manifest_path.write_text(dumps_json(manifest), encoding="utf-8")
        manifest["build_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "benchmark_suite_json": suite, "evaluation_report_json": report,
                    "release_readiness_json": readiness, "export_directory": str(export_dir),
                    "export_manifest_json": manifest, "stage": "awaiting_admin_review",
                },
            )
            self._event(
                connection, session_row["id"], "evaluation_report_generated", stage="generate_report",
                message=f"status={report['status']}, overall_score={report['overall_score']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 12: admin review -------------------------------------------------------------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")
            session_public = public_session_row(session_row)

            self.repository.record_memory(
                connection, evaluation_session_id=session_row["id"], topic=session_public["topic"],
                source_dataset_count=len(session_public["source_dataset_public_ids"]),
                source_rag_session_count=len(session_public["source_rag_session_public_ids"]),
                source_training_package_count=len(session_public["source_training_package_public_ids"]),
                overall_score=session_public["evaluation_report"].get("overall_score"),
                release_readiness_status=session_public["release_readiness"].get("status"),
                admin_decision=decision, recorded_by_admin_public_id=admin_id,
            )

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"evaluation_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' -- no model inference was ever performed by this "
                    "service. Evaluation approval does not guarantee production model quality"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainEvaluationCenterService"]
