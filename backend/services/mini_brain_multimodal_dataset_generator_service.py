"""MB-16: Brud Mini Brain Multimodal Dataset Generator Center -- the
orchestration layer for the 12-stage source-to-certification workflow
described in the MB-16 task spec.

MB-16 is not an OCR engine, vision model, language model, dataset
writer, training engine, or runtime. It combines already-computed
output from MB-13 (Language Intelligence), MB-14 (Vision
Intelligence), MB-15 (Vision Model Center), Dataset Studio, and
Document Workspace -- read exclusively through their own public
methods -- into one unified multimodal dataset draft. This service
never writes to any of those systems' tables; every generated record
stays `verified=false` in MB-16's own tables until an admin certifies
the session, and even then nothing is copied into Dataset Studio --
that remains a separate, human-triggered step outside this service.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_multimodal_dataset_generator import (
    MiniBrainMultimodalDatasetGeneratorRepository,
    public_memory_row,
    public_record_row,
    public_session_row,
)
from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService
from backend.services.document_service import DocumentService
from backend.services.mini_brain_language_intelligence_service import (
    MiniBrainLanguageIntelligenceService,
)
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)
from backend.services.mini_brain_vision_model_service import MiniBrainVisionModelService
from core_model.mini_brain.multimodal_dataset_generator.conversation_builder import build_conversations
from core_model.mini_brain.multimodal_dataset_generator.dataset_draft_assembler import (
    assemble_dataset_draft,
)
from core_model.mini_brain.multimodal_dataset_generator.dataset_memory_builder import (
    build_dataset_memory,
)
from core_model.mini_brain.multimodal_dataset_generator.dataset_report_generator import (
    generate_dataset_report,
)
from core_model.mini_brain.multimodal_dataset_generator.duplicate_report_builder import (
    build_duplicate_report,
)
from core_model.mini_brain.multimodal_dataset_generator.image_section_builder import (
    build_image_section,
)
from core_model.mini_brain.multimodal_dataset_generator.instruction_builder import build_instructions
from core_model.mini_brain.multimodal_dataset_generator.knowledge_graph_reference import (
    reference_knowledge_graph,
)
from core_model.mini_brain.multimodal_dataset_generator.metadata_merger import merge_metadata
from core_model.mini_brain.multimodal_dataset_generator.quality_engine import score_dataset_quality
from core_model.mini_brain.multimodal_dataset_generator.source_collector import collect_sources
from core_model.mini_brain.multimodal_dataset_generator.text_section_builder import build_text_section

ADMIN_DECISIONS = {"approve", "reject", "archive", "request_changes"}
ADMIN_STATUS_MAP = {
    "approve": "admin_approved", "reject": "admin_rejected", "archive": "admin_archived",
    "request_changes": "admin_requested_changes",
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _record_checksum(record_type: str, content: dict[str, Any]) -> str:
    normalized = json.dumps({"type": record_type, "content": content}, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class MiniBrainMultimodalDatasetGeneratorService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainMultimodalDatasetGeneratorRepository(settings.resolved_database_path)

        self.language_intelligence = MiniBrainLanguageIntelligenceService(settings)
        self.vision_intelligence = MiniBrainVisionIntelligenceService(settings)
        self.vision_model = MiniBrainVisionModelService(settings)
        self.document_service = DocumentService(settings)
        self.duplicate_service = ExternalDatasetDuplicateService()

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, multimodal_dataset_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, multimodal_dataset_session_id=multimodal_dataset_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def _read_full_document_text(self, document_source_public_id: str) -> str:
        document = self.document_service.get(document_source_public_id)
        total_pages = sum(document["page_status_counts"].values())
        texts = []
        for number in range(1, total_pages + 1):
            page = self.document_service.page(document_source_public_id, number)
            if page.get("cleaned_text"):
                texts.append(page["cleaned_text"])
        return "\n".join(texts)

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
                connection, multimodal_dataset_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def list_records(
        self, session_public_id: str, *, record_type: str | None = None, status: str | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_records(
                connection, multimodal_dataset_session_id=session_row["id"], record_type=record_type,
                status=status,
            )
        return {"items": [public_record_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    # -- session creation --------------------------------------------------------

    def create_session(
        self, *, document_source_public_id: str, dataset_source_public_id: str | None = None,
        language_session_public_id: str | None = None, vision_session_public_id: str | None = None,
        vision_model_session_public_id: str | None = None, parent_session_public_id: str | None = None,
        admin_id: str,
    ) -> dict[str, Any]:
        self.document_service.get(document_source_public_id)
        if language_session_public_id:
            self.language_intelligence.session(language_session_public_id)
        if vision_session_public_id:
            self.vision_intelligence.session(vision_session_public_id)
        if vision_model_session_public_id:
            self.vision_model.session(vision_model_session_public_id)

        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, document_source_public_id=document_source_public_id,
                dataset_source_public_id=dataset_source_public_id,
                language_session_public_id=language_session_public_id,
                vision_session_public_id=vision_session_public_id,
                vision_model_session_public_id=vision_model_session_public_id,
                parent_session_public_id=parent_session_public_id, created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="collect_sources",
                message=f"multimodal dataset cycle created for document {document_source_public_id}",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage 1: collect sources --------------------------------------------------

    def run_collect_sources_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_sources":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_sources'")

        report = collect_sources(
            document_source_public_id=session_data["document_source_public_id"],
            dataset_source_public_id=session_data["dataset_source_public_id"],
            language_session_public_id=session_data["language_session_public_id"],
            vision_session_public_id=session_data["vision_session_public_id"],
            vision_model_session_public_id=session_data["vision_model_session_public_id"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"source_report_json": report, "stage": "collect_text"},
            )
            self._event(
                connection, session_row["id"], "sources_collected", stage="collect_sources",
                message=f"{report['available_source_count']} source(s) linked",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 2: collect text -----------------------------------------------------

    def run_collect_text_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_text":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_text'")

        ocr_text = self._read_full_document_text(session_data["document_source_public_id"])
        language_session = None
        if session_data["language_session_public_id"]:
            language_session = self.language_intelligence.session(session_data["language_session_public_id"])

        report = build_text_section(ocr_text=ocr_text, language_session=language_session)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"text_section_json": report, "stage": "collect_images"},
            )
            self._event(
                connection, session_row["id"], "text_collected", stage="collect_text",
                message=f"{report['ocr_char_count']} character(s) of OCR text collected",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 3: collect images ---------------------------------------------------

    def run_collect_images_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_images":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_images'")

        vision_session = None
        images: list[dict[str, Any]] = []
        objects: list[dict[str, Any]] = []
        vision_model_session = None
        vm_predictions: list[dict[str, Any]] = []
        vm_corrections: list[dict[str, Any]] = []

        if session_data["vision_session_public_id"]:
            vision_session = self.vision_intelligence.session(session_data["vision_session_public_id"])
            images = self.vision_intelligence.list_images(session_data["vision_session_public_id"])["items"]
            objects = self.vision_intelligence.list_objects(
                session_data["vision_session_public_id"], status="active",
            )["items"]
        if session_data["vision_model_session_public_id"]:
            vision_model_session = self.vision_model.session(session_data["vision_model_session_public_id"])
            vm_predictions = self.vision_model.list_predictions(
                session_data["vision_model_session_public_id"], review_status="approved",
            )["items"]
            vm_corrections = self.vision_model.list_corrections(
                session_data["vision_model_session_public_id"],
            )["items"]

        report = build_image_section(
            vision_session=vision_session, images=images, objects=objects,
            vision_model_session=vision_model_session, vm_predictions=vm_predictions,
            vm_corrections=vm_corrections,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"image_section_json": report, "stage": "merge_metadata"},
            )
            self._event(
                connection, session_row["id"], "images_collected", stage="collect_images",
                message=f"{report['image_count']} image(s) collected",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 4: merge metadata ----------------------------------------------------

    def run_merge_metadata_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "merge_metadata":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'merge_metadata'")

        graph_source = session_data["image_section"].get("relationships", {})
        knowledge_graph = reference_knowledge_graph(graph=graph_source)
        report = merge_metadata(
            source_report=session_data["source_report"], text_section=session_data["text_section"],
            image_section=session_data["image_section"], knowledge_graph=knowledge_graph,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"metadata_report_json": report, "stage": "conversation_builder"},
            )
            self._event(
                connection, session_row["id"], "metadata_merged", stage="merge_metadata",
                message=f"is_multimodal={report['is_multimodal']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 5: conversation builder -----------------------------------------------

    def run_conversation_builder_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "conversation_builder":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'conversation_builder'")

        qa_items: list[dict[str, Any]] = []
        if session_data["vision_session_public_id"]:
            vision_session = self.vision_intelligence.session(session_data["vision_session_public_id"])
            qa_items = vision_session.get("qa_report", {}).get("questions", [])

        report = build_conversations(
            merged_metadata=session_data["metadata_report"], qa_items=qa_items,
            document_source_public_id=session_data["document_source_public_id"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"conversation_report_json": report, "stage": "instruction_builder"},
            )
            self._event(
                connection, session_row["id"], "conversations_built", stage="conversation_builder",
                message=f"{report['conversation_count']} conversation(s) built",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: instruction builder ------------------------------------------------

    def run_instruction_builder_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "instruction_builder":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'instruction_builder'")

        report = build_instructions(merged_metadata=session_data["metadata_report"])

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"instruction_report_json": report, "stage": "dataset_draft"},
            )
            self._event(
                connection, session_row["id"], "instructions_built", stage="instruction_builder",
                message=f"{report['instruction_count']} instruction(s) built",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: dataset draft --------------------------------------------------------

    def run_dataset_draft_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "dataset_draft":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dataset_draft'")

        assembled = assemble_dataset_draft(
            conversations=session_data["conversation_report"]["conversations"],
            instructions=session_data["instruction_report"]["instructions"],
            merged_metadata=session_data["metadata_report"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for record in assembled["records"]:
                checksum = _record_checksum(record["record_type"], record["content"])
                self.repository.create_record(
                    connection, multimodal_dataset_session_id=session_row["id"],
                    record_type=record["record_type"], content=record["content"], record_checksum=checksum,
                )
            report = {k: v for k, v in assembled.items() if k != "records"}
            self.repository.update_session(
                connection, session_public_id,
                {"dataset_draft_report_json": report, "stage": "quality_analysis"},
            )
            self._event(
                connection, session_row["id"], "dataset_draft_assembled", stage="dataset_draft",
                message=f"{report['record_count']} record(s) drafted -- verified=False, nothing inserted into Dataset Studio",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: quality analysis --------------------------------------------------------

    def run_quality_analysis_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "quality_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'quality_analysis'")

        text_section = session_data["text_section"]
        image_section = session_data["image_section"]
        objects = image_section.get("objects", [])
        object_quality = (
            round(sum(1 for o in objects if o.get("source") != "auto_unknown") / len(objects) * 100, 1)
            if objects else None
        )
        ocr_match_score = None
        if session_data["vision_session_public_id"]:
            vision_session = self.vision_intelligence.session(session_data["vision_session_public_id"])
            status_counts = vision_session.get("ocr_cross_validation_report", {}).get("status_counts", {})
            total = sum(status_counts.values())
            ocr_match_score = round(status_counts.get("match", 0) / total * 100, 1) if total else None

        caption = image_section.get("caption", {})
        report = score_dataset_quality(
            language_quality_score=text_section.get("language_quality_score"),
            vision_quality_score=image_section.get("quality", {}).get("average_quality_score"),
            ocr_match_score=ocr_match_score, object_quality_score=object_quality,
            caption_quality_score=100.0 if (caption.get("long_description") or caption.get("dataset_caption")) else None,
            knowledge_graph_edge_count=session_data["metadata_report"]["knowledge_graph"]["edge_count"],
            conversation_count=session_data["conversation_report"]["conversation_count"],
            instruction_count=session_data["instruction_report"]["instruction_count"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"quality_report_json": report, "stage": "duplicate_detection"},
            )
            self._event(
                connection, session_row["id"], "quality_scored", stage="quality_analysis",
                message=f"overall dataset quality {report['overall_dataset_quality']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: duplicate detection --------------------------------------------------------

    def run_duplicate_detection_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "duplicate_detection":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'duplicate_detection'")

        records = self.list_records(session_public_id)["items"]
        duplicate_input = [{"record_checksum": r["record_checksum"], "public_id": r["public_id"]} for r in records]
        exact_groups = self.duplicate_service.group_exact_duplicates(duplicate_input)

        # Scoped per record_type -- an "instruction" record and its
        # "training" alias are expected to share content by design
        # (disclosed in dataset_draft_assembler.py) and must never be
        # flagged as a false-positive cross-type duplicate.
        text_records = [
            {
                "public_id": r["public_id"],
                "normalized_content": r["record_type"] + "::" + json.dumps(r["content"], sort_keys=True, default=str).lower(),
            }
            for r in records
        ]
        normalized_groups = self.duplicate_service.group_normalized_duplicates(text_records)

        images = session_data["image_section"].get("images", [])
        image_input = [{"record_checksum": i["checksum_sha256"], "public_id": i["public_id"]} for i in images]
        image_groups = self.duplicate_service.group_exact_duplicates(image_input)

        report = build_duplicate_report(
            exact_groups=exact_groups, normalized_groups=normalized_groups, image_checksum_groups=image_groups,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for group in exact_groups:
                for public_id in group[1:]:
                    self.repository.update_record(connection, public_id, {"status": "duplicate"})
            self.repository.update_session(
                connection, session_public_id, {"duplicate_report_json": report, "stage": "report"},
            )
            self._event(
                connection, session_row["id"], "duplicates_detected", stage="duplicate_detection",
                message=f"{report['exact_duplicate_count']} exact, {report['normalized_duplicate_count']} normalized duplicate(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 10: report -----------------------------------------------------------------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'report'")

        active_records = self.list_records(session_public_id, status="active")["items"]
        report = generate_dataset_report(
            multimodal_dataset_session_public_id=session_public_id,
            document_source_public_id=session_data["document_source_public_id"],
            quality_report=session_data["quality_report"], record_count=len(active_records),
            duplicate_report=session_data["duplicate_report"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"dataset_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "dataset_report_generated", stage="report",
                message=f"status={report['status']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11/12: admin review -> certified -------------------------------------------

    def _record_dataset_memory(self, connection, *, session_row, admin_id: str, decision: str | None) -> None:
        session_public = public_session_row(session_row)
        active_records = [
            public_record_row(r)
            for r in self.repository.list_records(
                connection, multimodal_dataset_session_id=session_row["id"], status="active",
            )
        ]
        correction_history: list[dict[str, Any]] = []
        learning_memory: list[dict[str, Any]] = []
        provider_key = None
        if session_public["vision_model_session_public_id"]:
            correction_history = self.vision_model.list_corrections(
                session_public["vision_model_session_public_id"],
            )["items"]
            vm_session = self.vision_model.session(session_public["vision_model_session_public_id"])
            provider_key = vm_session["provider_key"]
            learning_memory = [
                m for m in self.vision_model.list_learning_memory()["items"]
                if m["provider_key"] == provider_key
            ]

        memory = build_dataset_memory(
            generated_at=_now(), source_document_public_id=session_public["document_source_public_id"],
            source_dataset_public_id=session_public["dataset_source_public_id"],
            source_language_session_public_id=session_public["language_session_public_id"],
            source_vision_session_public_id=session_public["vision_session_public_id"],
            source_vision_model_session_public_id=session_public["vision_model_session_public_id"],
            total_records=len(active_records), correction_history=correction_history,
            learning_memory=learning_memory, provider_key=provider_key,
        )
        self.repository.record_memory(
            connection, multimodal_dataset_session_id=session_row["id"], dataset_version=1,
            generated_at=memory["generated_at"], source_document_public_id=memory["source_document_public_id"],
            source_dataset_public_id=memory["source_dataset_public_id"],
            source_language_session_public_id=memory["source_language_session_public_id"],
            source_vision_session_public_id=memory["source_vision_session_public_id"],
            source_vision_model_session_public_id=memory["source_vision_model_session_public_id"],
            total_records=memory["total_records"], correction_history=memory["correction_history"],
            learning_memory=memory["learning_memory"], provider_information=memory["provider_information"],
            admin_decision=decision, recorded_by_admin_public_id=admin_id,
        )

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")

            self._record_dataset_memory(connection, session_row=session_row, admin_id=admin_id, decision=decision)

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "certified" if decision == "approve" else "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"dataset_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' -- no dataset was written into Dataset Studio by this "
                    "service. A 'certified' session is eligible for MB-17/18/19/20, never auto-submitted"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- draft-lifecycle admin actions: delete, export, split, merge ---------------------

    def delete_draft(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] == "certified":
                raise ValidationError("a certified dataset cannot be deleted as a draft -- archive it instead")
            self.repository.update_session(
                connection, session_public_id, {"status": "draft_deleted", "stage": "closed"},
            )
            self._event(
                connection, session_row["id"], "draft_deleted", message="admin deleted this draft",
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def export_draft(self, session_public_id: str, *, export_format: str = "json") -> dict[str, Any]:
        if export_format not in ("json", "jsonl"):
            raise ValidationError("export_format must be 'json' or 'jsonl'")
        session_data = self.session(session_public_id)
        records = self.list_records(session_public_id, status="active")["items"]
        payload = [{"record_type": r["record_type"], "content": r["content"]} for r in records]
        if export_format == "jsonl":
            body = "\n".join(json.dumps(item, default=str) for item in payload)
        else:
            body = json.dumps(payload, indent=2, default=str)
        return {
            "session_public_id": session_public_id, "status": session_data["status"],
            "format": export_format, "record_count": len(records), "content": body,
            "disclosure": "this export is a file only -- nothing has been written into Dataset Studio",
        }

    def split_dataset(
        self, session_public_id: str, *, record_public_ids: list[str], admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            parent_row = self.repository.session(connection, session_public_id)
            if parent_row["stage"] != "certified":
                raise ValidationError("only a certified dataset can be split")
            parent_public = public_session_row(parent_row)

            child_public_id = self.repository.create_session(
                connection, document_source_public_id=parent_public["document_source_public_id"],
                dataset_source_public_id=parent_public["dataset_source_public_id"],
                language_session_public_id=parent_public["language_session_public_id"],
                vision_session_public_id=parent_public["vision_session_public_id"],
                vision_model_session_public_id=parent_public["vision_model_session_public_id"],
                parent_session_public_id=session_public_id, created_by_admin_public_id=admin_id,
            )
            child_row = self.repository.session(connection, child_public_id)

            copied = 0
            for public_id in record_public_ids:
                source_record = public_record_row(self.repository.get_record(connection, public_id))
                self.repository.create_record(
                    connection, multimodal_dataset_session_id=child_row["id"],
                    record_type=source_record["record_type"], content=source_record["content"],
                    record_checksum=source_record["record_checksum"],
                )
                copied += 1

            self.repository.update_session(
                connection, child_public_id,
                {"dataset_draft_report_json": {"record_count": copied, "status": "needs_admin_review", "verified": False}, "stage": "report"},
            )
            self._event(
                connection, child_row["id"], "dataset_split_from_parent", stage="collect_sources",
                message=f"split from {session_public_id} with {copied} record(s)",
                metadata={"admin_id": admin_id, "parent_session_public_id": session_public_id},
            )
            return public_session_row(self.repository.session(connection, child_public_id))

    def merge_datasets(self, session_public_ids: list[str], *, admin_id: str) -> dict[str, Any]:
        if len(session_public_ids) < 2:
            raise ValidationError("merge_datasets requires at least 2 session_public_ids")
        with self.repository.transaction() as connection:
            parent_rows = [self.repository.session(connection, sid) for sid in session_public_ids]
            for row in parent_rows:
                if row["stage"] != "certified":
                    raise ValidationError("all sessions being merged must already be certified")
            first_public = public_session_row(parent_rows[0])

            merged_public_id = self.repository.create_session(
                connection, document_source_public_id=first_public["document_source_public_id"],
                dataset_source_public_id=first_public["dataset_source_public_id"],
                language_session_public_id=None, vision_session_public_id=None,
                vision_model_session_public_id=None, parent_session_public_id=session_public_ids[0],
                created_by_admin_public_id=admin_id,
            )
            merged_row = self.repository.session(connection, merged_public_id)

            copied = 0
            for row in parent_rows:
                for source_record in self.repository.list_records(
                    connection, multimodal_dataset_session_id=row["id"], status="active",
                ):
                    record = public_record_row(source_record)
                    self.repository.create_record(
                        connection, multimodal_dataset_session_id=merged_row["id"],
                        record_type=record["record_type"], content=record["content"],
                        record_checksum=record["record_checksum"],
                    )
                    copied += 1

            self.repository.update_session(
                connection, merged_public_id,
                {"dataset_draft_report_json": {"record_count": copied, "status": "needs_admin_review", "verified": False}, "stage": "report"},
            )
            self._event(
                connection, merged_row["id"], "dataset_merged_from_parents", stage="collect_sources",
                message=f"merged from {session_public_ids} with {copied} record(s)",
                metadata={"admin_id": admin_id, "parent_session_public_ids": session_public_ids},
            )
            return public_session_row(self.repository.session(connection, merged_public_id))


__all__ = ["MiniBrainMultimodalDatasetGeneratorService"]
