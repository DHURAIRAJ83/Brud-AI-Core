"""MB-18: Brud Mini Brain Multimodal Training Pipeline Center -- the
orchestration layer for the 12-stage session-to-package workflow
described in the MB-18 task spec.

MB-18 is a planning, validation, packaging, and reporting system
only. It never starts a training job, never calls a training or
quantization API, never creates a GGUF file, and never deploys or
activates a runtime. It prepares a deterministic, checksummed package
of JSON metadata files from already-certified MB-16 datasets and
already-approved MB-17 grounded RAG memory -- read exclusively through
their own public methods, plus MB-13/14/15's own session detail and
MB-05/MB-05.1's own dataset-readiness reports when a Dataset Studio
source happens to be linked -- into MB-18's own tables and its own
artifact directory on disk. No model weights are ever produced.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.mini_brain_training_pipeline import (
    MiniBrainTrainingPipelineRepository,
    public_memory_row,
    public_package_row,
    public_session_row,
)
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_advanced_dataset_service import MiniBrainAdvancedDatasetService
from backend.services.mini_brain_dataset_intelligence_service import (
    MiniBrainDatasetIntelligenceService,
)
from backend.services.mini_brain_language_intelligence_service import (
    MiniBrainLanguageIntelligenceService,
)
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)
from backend.services.mini_brain_vision_rag_service import MiniBrainVisionRagService
from core_model.release.artifact_inventory import file_checksum, resolve_confined_path
from core_model.mini_brain.training_pipeline.curriculum_planner import plan_curriculum
from core_model.mini_brain.training_pipeline.dataset_splitter import split_dataset
from core_model.mini_brain.training_pipeline.grounding_quality_analyzer import analyze_grounding_quality
from core_model.mini_brain.training_pipeline.hardware_estimator import estimate_hardware
from core_model.mini_brain.training_pipeline.image_statistics_analyzer import analyze_image_statistics
from core_model.mini_brain.training_pipeline.language_distribution_analyzer import (
    analyze_language_distribution,
)
from core_model.mini_brain.training_pipeline.package_manifest_builder import build_package_manifest
from core_model.mini_brain.training_pipeline.pipeline_report_generator import generate_readiness_report
from core_model.mini_brain.training_pipeline.reproducibility_hasher import build_reproducibility_record
from core_model.mini_brain.training_pipeline.source_collector import collect_datasets, collect_rag_memory
from core_model.mini_brain.training_pipeline.tokenizer_coverage_analyzer import (
    analyze_tokenizer_coverage,
)
from core_model.mini_brain.training_pipeline.training_recipe_builder import build_training_recipe

ADMIN_DECISIONS = {"approve", "reject", "archive"}
ADMIN_STATUS_MAP = {"approve": "admin_approved", "reject": "admin_rejected", "archive": "admin_archived"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _timed(fn, /, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn(**kwargs)
    return result, round((time.perf_counter() - started) * 1000, 3)


class MiniBrainTrainingPipelineService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainTrainingPipelineRepository(settings.resolved_database_path)

        self.multimodal_dataset = MiniBrainMultimodalDatasetGeneratorService(settings)
        self.vision_rag = MiniBrainVisionRagService(settings)
        self.language_intelligence = MiniBrainLanguageIntelligenceService(settings)
        self.vision_intelligence = MiniBrainVisionIntelligenceService(settings)

        dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        self.dataset_intelligence = MiniBrainDatasetIntelligenceService(dataset_service)
        self.advanced_dataset = MiniBrainAdvancedDatasetService(dataset_service, self.dataset_intelligence)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, training_pipeline_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, training_pipeline_session_id=training_pipeline_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def _package_dir(self, session_public_id: str) -> Path:
        root = self.settings.resolved_document_dir.parent / "training_packages"
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
                connection, training_pipeline_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def list_packages(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_packages(connection, training_pipeline_session_id=session_row["id"])
        return {"items": [public_package_row(row) for row in rows]}

    def get_package_metadata(self, package_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_package_row(self.repository.get_package(connection, package_public_id))

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    def list_available_rag_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Read-only proxy to MB-17's own global RAG Memory listing, for
        the dashboard's Sources picker."""
        return self.vision_rag.list_memory(limit=limit, offset=offset)

    # -- stage 1: create training session --------------------------------------

    def create_session(self, *, topic: str, admin_id: str) -> dict[str, Any]:
        if not topic.strip():
            raise ValidationError("topic must not be empty")
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, topic=topic, source_dataset_public_ids=[], source_rag_memory_public_ids=[],
                created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="collect_datasets",
                message=f"training pipeline session created for topic '{topic}'",
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
        for dataset_session in dataset_sessions:
            record_count = len(self.multimodal_dataset.list_records(dataset_session["public_id"], status="active")["items"])
            dataset_session["record_count"] = record_count

        report = collect_datasets(dataset_sessions=dataset_sessions)
        if not report["ready"]:
            raise ValidationError("no certified (status='admin_approved') MB-16 dataset session was accepted")

        readiness_signals = []
        for dataset_session in dataset_sessions:
            source_public_id = dataset_session.get("dataset_source_public_id")
            if not source_public_id:
                continue
            try:
                training_signal = self.dataset_intelligence.training(source_public_id)
                advanced_signal = self.advanced_dataset.report(source_public_id)
                readiness_signals.append({
                    "dataset_source_public_id": source_public_id, "mb05_training": training_signal,
                    "mb05_1_report": advanced_signal,
                })
            except NotFoundError:
                continue
        report["mb05_readiness_signals"] = readiness_signals

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "dataset_collection_report_json": report,
                    "source_dataset_public_ids_json": report["accepted_session_public_ids"],
                    "stage": "collect_rag_memory",
                },
            )
            self._event(
                connection, session_row["id"], "datasets_collected", stage="collect_datasets",
                message=f"{report['accepted_count']} certified dataset(s) accepted, {report['rejected_count']} rejected",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 3: collect grounded RAG memory -------------------------------------------

    def run_collect_rag_memory_stage(
        self, session_public_id: str, *, rag_session_public_ids: list[str], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_rag_memory":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_rag_memory'")

        rag_sessions = [self.vision_rag.session(sid) for sid in rag_session_public_ids]
        memory_entries = [
            {
                "public_id": s["public_id"], "admin_decision": s["admin_decision"],
                "hallucination_flag": s.get("hallucination_report", {}).get("hallucination_flag", False),
                "confidence": s.get("answer_report", {}).get("confidence"),
            }
            for s in rag_sessions
        ]
        report = collect_rag_memory(rag_memory_entries=memory_entries)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "rag_memory_collection_report_json": report,
                    "source_rag_memory_public_ids_json": report["accepted_memory_public_ids"],
                    "stage": "analyze_language",
                },
            )
            self._event(
                connection, session_row["id"], "rag_memory_collected", stage="collect_rag_memory",
                message=f"{report['accepted_count']} approved RAG session(s) accepted, {report['grounded_count']} free of hallucination flags",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- helper: gather text/records across accepted datasets, streamed -----------------

    def _iter_records(self, dataset_session_public_ids: list[str]):
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

    # -- stage 4: analyze language distribution ------------------------------------------

    def run_analyze_language_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "analyze_language":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'analyze_language'")

        language_sessions = []
        for dataset_session_public_id in session_data["source_dataset_public_ids"]:
            dataset_session = self.multimodal_dataset.session(dataset_session_public_id)
            language_session_public_id = dataset_session.get("language_session_public_id")
            if language_session_public_id:
                language_sessions.append(self.language_intelligence.session(language_session_public_id))

        report, latency_ms = _timed(analyze_language_distribution, language_sessions=language_sessions)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"language_distribution_report_json": report, "stage": "analyze_vision"},
            )
            self._event(
                connection, session_row["id"], "language_analyzed", stage="analyze_language",
                message=f"{report['session_count']} language session(s) analyzed",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 5: analyze vision coverage --------------------------------------------------

    def run_analyze_vision_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "analyze_vision":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'analyze_vision'")

        images: list[dict[str, Any]] = []
        for dataset_session_public_id in session_data["source_dataset_public_ids"]:
            dataset_session = self.multimodal_dataset.session(dataset_session_public_id)
            vision_session_public_id = dataset_session.get("vision_session_public_id")
            if vision_session_public_id:
                images.extend(self.vision_intelligence.list_images(vision_session_public_id)["items"])

        rag_memory_entries = []
        for rag_session_public_id in session_data["source_rag_memory_public_ids"]:
            rag_session = self.vision_rag.session(rag_session_public_id)
            rag_memory_entries.append({
                "public_id": rag_session["public_id"],
                "confidence": rag_session["answer_report"].get("confidence"),
                "hallucination_flag": rag_session["hallucination_report"].get("hallucination_flag", False),
            })

        image_stats, image_latency_ms = _timed(analyze_image_statistics, images=images)
        grounding_report, grounding_latency_ms = _timed(
            analyze_grounding_quality, rag_memory_entries=rag_memory_entries,
        )
        image_stats["latency_ms"] = image_latency_ms
        grounding_report["latency_ms"] = grounding_latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "image_statistics_report_json": image_stats,
                    "grounding_quality_report_json": grounding_report, "stage": "analyze_tokenizer",
                },
            )
            self._event(
                connection, session_row["id"], "vision_analyzed", stage="analyze_vision",
                message=f"{image_stats['image_count']} image(s), grounding query count {grounding_report['query_count']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: analyze tokenizer coverage ------------------------------------------------

    def run_analyze_tokenizer_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "analyze_tokenizer":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'analyze_tokenizer'")

        texts = [
            text for record in self._iter_records(session_data["source_dataset_public_ids"])
            if (text := self._record_text(record))
        ]
        report, latency_ms = _timed(analyze_tokenizer_coverage, texts=texts)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"tokenizer_coverage_report_json": report, "stage": "plan_splits"},
            )
            self._event(
                connection, session_row["id"], "tokenizer_analyzed", stage="analyze_tokenizer",
                message=f"{report['unique_character_count']} unique character(s) across {len(texts)} text(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: plan dataset splits ---------------------------------------------------------

    def run_plan_splits_stage(
        self, session_public_id: str, *, admin_id: str, seed: int | None = None,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "plan_splits":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'plan_splits'")

        record_public_ids = [
            record["public_id"] for record in self._iter_records(session_data["source_dataset_public_ids"])
        ]
        kwargs: dict[str, Any] = {"record_public_ids": record_public_ids}
        if seed is not None:
            kwargs["seed"] = seed
        report, latency_ms = _timed(split_dataset, **kwargs)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"splits_report_json": report, "stage": "plan_curriculum"},
            )
            self._event(
                connection, session_row["id"], "splits_planned", stage="plan_splits",
                message=f"{report['counts']} (seed={report['seed']})",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: plan curriculum -------------------------------------------------------------

    def run_plan_curriculum_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "plan_curriculum":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'plan_curriculum'")

        record_type_counts: dict[str, int] = {}
        for record in self._iter_records(session_data["source_dataset_public_ids"]):
            record_type_counts[record["record_type"]] = record_type_counts.get(record["record_type"], 0) + 1

        curriculum_report, curriculum_latency_ms = _timed(plan_curriculum, record_type_counts=record_type_counts)
        recipe, recipe_latency_ms = _timed(
            build_training_recipe, total_record_count=sum(record_type_counts.values()),
            curriculum_stage_count=curriculum_report["stage_count"],
        )
        curriculum_report["latency_ms"] = curriculum_latency_ms
        curriculum_report["training_recipe"] = recipe
        curriculum_report["training_recipe_latency_ms"] = recipe_latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"curriculum_report_json": curriculum_report, "stage": "estimate_hardware"},
            )
            self._event(
                connection, session_row["id"], "curriculum_planned", stage="plan_curriculum",
                message=f"{curriculum_report['stage_count']} curriculum stage(s) planned",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: estimate hardware & storage ----------------------------------------------------

    def run_estimate_hardware_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "estimate_hardware":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'estimate_hardware'")

        text_bytes = sum(
            len((self._record_text(record) or "").encode("utf-8"))
            for record in self._iter_records(session_data["source_dataset_public_ids"])
        )
        report, latency_ms = _timed(
            estimate_hardware,
            total_character_count=session_data["tokenizer_coverage_report"]["total_character_count"],
            image_count=session_data["image_statistics_report"]["image_count"],
            total_image_pixels=session_data["image_statistics_report"]["total_pixels"],
            total_image_bytes=session_data["image_statistics_report"]["total_bytes"],
            total_text_bytes=text_bytes,
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"hardware_estimate_report_json": report, "stage": "build_package"},
            )
            self._event(
                connection, session_row["id"], "hardware_estimated", stage="estimate_hardware",
                message=f"~{report['estimated_token_count']} token(s), {report['expected_training_duration_category']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 10: build training package -------------------------------------------------------

    def run_build_package_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "build_package":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'build_package'")

        package_dir = self._package_dir(session_public_id)
        artifact_payloads = {
            "dataset_summary.json": session_data["dataset_collection_report"],
            "splits.json": session_data["splits_report"],
            "curriculum_plan.json": session_data["curriculum_report"],
            "training_recipe.json": session_data["curriculum_report"].get("training_recipe", {}),
            "tokenizer_coverage.json": session_data["tokenizer_coverage_report"],
            "language_distribution.json": session_data["language_distribution_report"],
            "image_statistics.json": session_data["image_statistics_report"],
            "grounding_quality.json": session_data["grounding_quality_report"],
            "hardware_estimate.json": session_data["hardware_estimate_report"],
        }

        started = time.perf_counter()
        artifact_entries = []
        for artifact_name, payload in artifact_payloads.items():
            path = resolve_confined_path(package_dir, artifact_name)
            path.write_text(dumps_json(payload), encoding="utf-8")
            checksum = file_checksum(path)
            artifact_entries.append({
                "artifact_name": artifact_name, "relative_path": artifact_name, "sha256": checksum,
                "file_size_bytes": path.stat().st_size,
            })

        manifest = build_package_manifest(
            session_public_id=session_public_id, topic=session_data["topic"],
            source_dataset_public_ids=session_data["source_dataset_public_ids"],
            source_rag_memory_public_ids=session_data["source_rag_memory_public_ids"],
            artifact_entries=artifact_entries, created_at=_now(),
        )
        manifest_path = resolve_confined_path(package_dir, "manifest.json")
        manifest_path.write_text(dumps_json(manifest), encoding="utf-8")
        manifest_entry = {
            "artifact_name": "manifest.json", "relative_path": "manifest.json",
            "sha256": file_checksum(manifest_path), "file_size_bytes": manifest_path.stat().st_size,
        }
        artifact_entries.append(manifest_entry)

        reproducibility = build_reproducibility_record(
            package_manifest=manifest, split_seed=session_data["splits_report"]["seed"],
            source_dataset_public_ids=session_data["source_dataset_public_ids"],
            source_rag_memory_public_ids=session_data["source_rag_memory_public_ids"],
        )
        reproducibility_path = resolve_confined_path(package_dir, "reproducibility.json")
        reproducibility_path.write_text(dumps_json(reproducibility), encoding="utf-8")
        artifact_entries.append({
            "artifact_name": "reproducibility.json", "relative_path": "reproducibility.json",
            "sha256": file_checksum(reproducibility_path), "file_size_bytes": reproducibility_path.stat().st_size,
        })
        build_latency_ms = round((time.perf_counter() - started) * 1000, 3)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for entry in artifact_entries:
                self.repository.create_package(
                    connection, training_pipeline_session_id=session_row["id"],
                    artifact_name=entry["artifact_name"], relative_path=entry["relative_path"],
                    sha256=entry["sha256"], file_size_bytes=entry["file_size_bytes"],
                )
            manifest["reproducibility"] = reproducibility
            manifest["build_latency_ms"] = build_latency_ms
            self.repository.update_session(
                connection, session_public_id,
                {
                    "package_directory": str(package_dir), "package_manifest_json": manifest,
                    "stage": "generate_report",
                },
            )
            self._event(
                connection, session_row["id"], "package_built", stage="build_package",
                message=f"{len(artifact_entries)} artifact file(s) written and checksummed",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11: generate training readiness report --------------------------------------------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "generate_report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'generate_report'")

        report = generate_readiness_report(
            session_public_id=session_public_id, topic=session_data["topic"],
            dataset_collection_report=session_data["dataset_collection_report"],
            rag_memory_collection_report=session_data["rag_memory_collection_report"],
            language_distribution_report=session_data["language_distribution_report"],
            image_statistics_report=session_data["image_statistics_report"],
            grounding_quality_report=session_data["grounding_quality_report"],
            tokenizer_coverage_report=session_data["tokenizer_coverage_report"],
            curriculum_report=session_data["curriculum_report"],
            hardware_estimate_report=session_data["hardware_estimate_report"],
            reproducibility_record=session_data["package_manifest"].get("reproducibility", {}),
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"readiness_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "readiness_report_generated", stage="generate_report",
                message=f"status={report['status']}",
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
                connection, training_pipeline_session_id=session_row["id"], topic=session_public["topic"],
                source_dataset_count=len(session_public["source_dataset_public_ids"]),
                source_rag_memory_count=len(session_public["source_rag_memory_public_ids"]),
                package_manifest_checksum=session_public["package_manifest"].get("reproducibility", {}).get("manifest_checksum_sha256"),
                readiness_score=session_public["readiness_report"].get("overall_readiness_score"),
                admin_decision=decision, recorded_by_admin_public_id=admin_id,
            )

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"training_pipeline_review_{decision}",
                stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' -- no training was ever started by this service. "
                    "Package approval does not imply model quality"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainTrainingPipelineService"]
