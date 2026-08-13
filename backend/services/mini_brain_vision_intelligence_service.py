"""MB-14: Brud Mini Brain Vision Intelligence & Image Understanding
Center -- the orchestration layer for the 14-stage image-extraction-
to-certification workflow described in the MB-14 task spec.

This service NEVER edits a dataset, NEVER starts training, NEVER
activates a runtime, NEVER exports GGUF, NEVER modifies RAG, and NEVER
deploys a model -- confirmed by structural/safety tests reading this
file's own source. It composes existing, unmodified systems through
their public methods only:

- `DocumentService` (Document Workspace's own service) -- ONLY
  `.get()`, `.page()`, `.artifact()`, to read an already-validated,
  already-stored PDF document and its already-OCR'd page text. MB-14
  never writes to `document_sources`/`document_pages`. `.get()`'s own
  public projection deliberately strips `stored_filename`, so
  resolving the on-disk PDF path reuses `DocumentRepository.document()`
  (a plain read-only SELECT) exactly as `DocumentWorkspaceService.
  render_page_image()` already does for the same purpose, rather than
  adding a new method to Document Workspace's own service.
- `DocumentContentClassificationService` (Task Finalization) -- ONLY
  `.get_classification()`, to read which pages were already flagged
  `vision_required`. MB-14 never classifies a page itself.
- The new, bounded, read-only `vision_image_extraction_utility` --
  the first real image-byte extraction in this codebase (confirmed by
  audit: `document_service.py`'s own PyMuPDF usage only ever *counts*
  images). It opens the already-stored PDF file read-only via
  `DocumentService.artifact()` and never writes to it.
- The twelve pure `core_model.mini_brain.vision_intelligence` modules
  for every deterministic decision. No vision model, object-detection
  model, or captioning model exists anywhere in this codebase
  (confirmed by audit) -- every automated detection is honestly
  "Unknown Object" with confidence 0.0 until an admin annotates it.

Extracted image bytes are stored as files under this service's own
`document_dir/vision/<session>/` subdirectory (mirroring Document
Workspace's own pending/quarantine file-storage pattern) -- the
database only ever holds metadata. Every irreversible step (a real
dataset record actually being written) requires an explicit prior
admin decision recorded on this session; nothing here writes to
Dataset Studio, and nothing here proceeds automatically past a
decision gate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.documents import DocumentRepository
from backend.database.repositories.mini_brain_vision_intelligence import (
    MiniBrainVisionIntelligenceRepository,
    public_image_row,
    public_object_row,
    public_session_row,
)
from backend.services.document_content_classification_service import (
    DocumentContentClassificationService,
)
from backend.services.document_service import DocumentService
from backend.services.vision_image_extraction_utility import analyze_pixels, extract_images
from core_model.mini_brain.vision_intelligence.annotation_recorder import record_annotation
from core_model.mini_brain.vision_intelligence.bounding_box_planner import plan_bounding_boxes
from core_model.mini_brain.vision_intelligence.caption_generator import generate_captions
from core_model.mini_brain.vision_intelligence.image_extraction_report import (
    summarize_extraction,
)
from core_model.mini_brain.vision_intelligence.image_quality_analyzer import analyze_image_quality
from core_model.mini_brain.vision_intelligence.knowledge_graph_builder import (
    build_knowledge_graph,
)
from core_model.mini_brain.vision_intelligence.ocr_cross_validator import cross_validate_ocr
from core_model.mini_brain.vision_intelligence.vision_dataset_draft_builder import (
    build_vision_dataset_draft,
)
from core_model.mini_brain.vision_intelligence.vision_question_generator import (
    generate_questions,
)
from core_model.mini_brain.vision_intelligence.vision_quality_engine import score_vision_quality
from core_model.mini_brain.vision_intelligence.vision_report_generator import (
    generate_vision_report,
)
from core_model.mini_brain.vision_intelligence.vision_understanding import detect_objects

ADMIN_DECISIONS = {"approve", "reject", "request_fix", "archive"}
ADMIN_STATUS_MAP = {
    "approve": "admin_approved", "reject": "admin_rejected", "request_fix": "admin_requested_fix",
    "archive": "admin_archived",
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainVisionIntelligenceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainVisionIntelligenceRepository(settings.resolved_database_path)

        self.document_service = DocumentService(settings)
        self.document_repository = DocumentRepository(settings.resolved_database_path)
        self.content_classification = DocumentContentClassificationService(settings)

    # -- helpers -------------------------------------------------------

    def _vision_dir(self, session_public_id: str) -> Path:
        directory = self.settings.resolved_document_dir / "vision" / session_public_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _resolve_pdf_path(self, document_public_id: str) -> Path:
        with self.document_repository.transaction() as connection:
            document = self.document_repository.document(connection, document_public_id)
            stored_filename = document["stored_filename"]
        return self.document_service.artifact(stored_filename)

    def _event(
        self, connection, vision_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, vision_session_id=vision_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

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
                connection, vision_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def list_images(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_images(connection, vision_session_id=session_row["id"])
        return {"items": [public_image_row(row) for row in rows]}

    def list_objects(self, session_public_id: str, *, status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_objects(connection, vision_session_id=session_row["id"], status=status)
        return {"items": [public_object_row(row) for row in rows]}

    # -- stage 1: session creation --------------------------------------

    def create_session(
        self, *, document_source_public_id: str, dataset_source_public_id: str | None = None, admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, document_source_public_id=document_source_public_id,
                dataset_source_public_id=dataset_source_public_id, created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="image_extraction",
                message=f"vision cycle created for document {document_source_public_id}",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage 1: image extraction ------------------------------------------

    def run_image_extraction_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "image_extraction":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'image_extraction'")

        pdf_path = self._resolve_pdf_path(session_data["document_source_public_id"])
        extracted = extract_images(pdf_path=pdf_path)

        vision_required_pages: list[int] = []
        for page_number in sorted({image["page_number"] for image in extracted}):
            try:
                classification = self.content_classification.get_classification(
                    session_data["document_source_public_id"], page_number
                )
            except ValidationError:
                continue
            if classification.get("vision_required"):
                vision_required_pages.append(page_number)

        vision_dir = self._vision_dir(session_public_id)
        recorded: list[dict[str, Any]] = []
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for image in extracted:
                stored_filename = f"{uuid4()}.{image['image_format']}"
                (vision_dir / stored_filename).write_bytes(image["image_bytes"])
                image_public_id = self.repository.record_image(
                    connection, vision_session_id=session_row["id"], page_number=image["page_number"],
                    image_index=image["image_index"], stored_filename=stored_filename,
                    image_format=image["image_format"], width_pixels=image["width_pixels"],
                    height_pixels=image["height_pixels"], file_size_bytes=image["file_size_bytes"],
                    checksum_sha256=image["checksum_sha256"],
                )
                recorded.append({**image, "public_id": image_public_id})

            report = summarize_extraction(images=[
                {k: v for k, v in r.items() if k != "image_bytes"} for r in recorded
            ])
            report["vision_required_pages"] = vision_required_pages
            self.repository.update_session(
                connection, session_public_id,
                {"image_extraction_report_json": report, "stage": "image_quality"},
            )
            self._event(
                connection, session_row["id"], "images_extracted", stage="image_extraction",
                message=f"{report['total_images']} image(s) extracted from the stored PDF, never modified",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 2: image quality -----------------------------------------------

    def run_image_quality_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "image_quality":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'image_quality'")

        vision_dir = self._vision_dir(session_public_id)
        per_image: list[dict[str, Any]] = []
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            images = self.repository.list_images(connection, vision_session_id=session_row["id"])
            for image in images:
                image_bytes = (vision_dir / image["stored_filename"]).read_bytes()
                pixels = analyze_pixels(image_bytes=image_bytes)
                quality = analyze_image_quality(
                    width=pixels["width"], height=pixels["height"], brightness_mean=pixels["brightness_mean"],
                    contrast_std=pixels["contrast_std"], blur_variance=pixels["blur_variance"],
                    exif_rotation=pixels["exif_rotation"],
                )
                per_image.append({"image_public_id": image["public_id"], **quality})

            average_score = round(sum(r["quality_score"] for r in per_image) / len(per_image), 1) if per_image else 0.0
            report = {"per_image": per_image, "average_quality_score": average_score, "image_count": len(per_image)}

            self.repository.update_session(
                connection, session_public_id, {"quality_report_json": report, "stage": "vision_understanding"},
            )
            self._event(
                connection, session_row["id"], "image_quality_analyzed", stage="image_quality",
                message=f"average quality score {average_score} across {len(per_image)} image(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 3: vision understanding (honest stub) ---------------------------

    def run_vision_understanding_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "vision_understanding":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'vision_understanding'")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            images = self.repository.list_images(connection, vision_session_id=session_row["id"])
            image_public_ids = [i["public_id"] for i in images]
            report = detect_objects(image_public_ids=image_public_ids)

            for image_public_id in image_public_ids:
                self.repository.create_object(
                    connection, vision_session_id=session_row["id"], image_public_id=image_public_id,
                    label="Unknown Object", confidence=0.0, bounding_box=None, source="auto_unknown",
                    created_by_admin_public_id=admin_id,
                )

            self.repository.update_session(
                connection, session_public_id,
                {"vision_understanding_report_json": report, "stage": "ocr_cross_validation"},
            )
            self._event(
                connection, session_row["id"], "vision_understanding_run", stage="vision_understanding",
                message=f"vision_model_available=False -- {len(image_public_ids)} Unknown Object placeholder(s) created",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 4: OCR cross validation ------------------------------------------

    def run_ocr_cross_validation_stage(
        self, session_public_id: str, *, admin_id: str, dataset_text: str | None = None,
        language_report_status: str | None = None,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "ocr_cross_validation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'ocr_cross_validation'")

        pages_with_images = sorted({img["page_number"] for img in self.list_images(session_public_id)["items"]})
        per_page: dict[str, Any] = {}
        for page_number in pages_with_images:
            page = self.document_service.page(session_data["document_source_public_id"], page_number)
            result = cross_validate_ocr(
                ocr_text=page.get("cleaned_text") or "", dataset_text=dataset_text,
                language_report_status=language_report_status,
            )
            per_page[str(page_number)] = result

        status_counts: dict[str, int] = {}
        for result in per_page.values():
            status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
        report = {"per_page": per_page, "status_counts": status_counts, "pages_compared": len(per_page)}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"ocr_cross_validation_report_json": report, "stage": "caption_generation"},
            )
            self._event(
                connection, session_row["id"], "ocr_cross_validated", stage="ocr_cross_validation",
                message=f"{len(per_page)} page(s) compared: {status_counts}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 5: caption (admin-supplied only) -----------------------------------

    def run_caption_stage(
        self, session_public_id: str, *, admin_id: str, admin_caption: str | None = None,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "caption_generation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'caption_generation'")

        report = generate_captions(admin_caption=admin_caption)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"caption_report_json": report, "stage": "bounding_box_planning"},
            )
            self._event(
                connection, session_row["id"], "caption_generated", stage="caption_generation",
                message=f"source={report['source']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: bounding box planning (admin-drawn only) -------------------------

    def run_bounding_box_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "bounding_box_planning":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'bounding_box_planning'")

        objects = self.list_objects(session_public_id, status="active")["items"]
        report = plan_bounding_boxes(objects=objects)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"bounding_box_report_json": report, "stage": "admin_annotation"},
            )
            self._event(
                connection, session_row["id"], "bounding_boxes_planned", stage="bounding_box_planning",
                message=f"{report['box_count']} admin-drawn box(es), {report['unboxed_object_count']} unboxed",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: admin annotation (repeatable) ------------------------------------

    def annotate(
        self, session_public_id: str, *, action: str, object_public_id: str | None, payload: dict[str, Any],
        admin_id: str,
    ) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "admin_annotation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'admin_annotation'")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            current_object = None
            if object_public_id:
                current_object = public_object_row(self.repository.get_object(connection, object_public_id))

            decision = record_annotation(action=action, current_object=current_object, payload=payload)
            if not decision["allowed"]:
                raise ValidationError(f"annotation blocked: {decision['reason']}")

            if action in ("rename", "correct_label"):
                self.repository.update_object(
                    connection, object_public_id, {"label": payload["label"], "source": "admin_corrected"},
                )
            elif action == "delete":
                self.repository.update_object(connection, object_public_id, {"status": "deleted"})
            elif action == "add":
                self.repository.create_object(
                    connection, vision_session_id=session_row["id"], image_public_id=payload["image_public_id"],
                    label=payload["label"], confidence=payload.get("confidence", 1.0),
                    bounding_box=payload.get("bounding_box"), source="admin_added",
                    created_by_admin_public_id=admin_id,
                )
            elif action == "redraw_box":
                self.repository.update_object(
                    connection, object_public_id,
                    {"bounding_box_json": payload["bounding_box"], "source": "admin_corrected"},
                )
            elif action == "correct_caption":
                caption_report = generate_captions(admin_caption=payload["caption"])
                self.repository.update_session(connection, session_public_id, {"caption_report_json": caption_report})

            self._event(
                connection, session_row["id"], f"annotation_{action}", stage="admin_annotation",
                message=f"admin applied '{action}'", metadata={"admin_id": admin_id, "object_public_id": object_public_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def finish_annotation_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "admin_annotation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'admin_annotation'")

        events = self.events(session_public_id, limit=100)["items"]
        action_counts: dict[str, int] = {}
        for event in events:
            if event["event_type"].startswith("annotation_"):
                action = event["event_type"].removeprefix("annotation_")
                action_counts[action] = action_counts.get(action, 0) + 1
        report = {"action_counts": action_counts, "total_annotations": sum(action_counts.values())}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"annotation_report_json": report, "stage": "knowledge_graph"},
            )
            self._event(
                connection, session_row["id"], "annotation_finished", stage="admin_annotation",
                message=f"{report['total_annotations']} annotation(s) recorded: {action_counts}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: knowledge graph --------------------------------------------------

    def run_knowledge_graph_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "knowledge_graph":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'knowledge_graph'")

        objects = self.list_objects(session_public_id, status="active")["items"]
        report = build_knowledge_graph(objects=objects)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"knowledge_graph_report_json": report, "stage": "qa_generation"},
            )
            self._event(
                connection, session_row["id"], "knowledge_graph_built", stage="knowledge_graph",
                message=f"{report['node_count']} node(s), {report['edge_count']} edge(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: QA generation -------------------------------------------------------

    def run_qa_generation_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "qa_generation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'qa_generation'")

        objects = self.list_objects(session_public_id, status="active")["items"]
        caption = session_data["caption_report"].get("dataset_caption")
        report = generate_questions(objects=objects, caption=caption)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"qa_report_json": report, "stage": "vision_dataset_draft"},
            )
            self._event(
                connection, session_row["id"], "qa_generated", stage="qa_generation",
                message=f"{report['question_count']} question(s), verified=False",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 10: vision dataset draft ------------------------------------------------

    def run_dataset_draft_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "vision_dataset_draft":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'vision_dataset_draft'")

        images = self.list_images(session_public_id)["items"]
        objects = self.list_objects(session_public_id, status="active")["items"]
        ocr_text = " ".join(
            self.document_service.page(session_data["document_source_public_id"], int(page))["cleaned_text"] or ""
            for page in session_data["ocr_cross_validation_report"].get("per_page", {})
        )

        report = build_vision_dataset_draft(
            image_metadata=images, ocr_text=ocr_text, caption_report=session_data["caption_report"],
            bounding_box_report=session_data["bounding_box_report"], objects=objects,
            qa_report=session_data["qa_report"], knowledge_graph_report=session_data["knowledge_graph_report"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"vision_dataset_draft_report_json": report, "stage": "vision_quality_score"},
            )
            self._event(
                connection, session_row["id"], "vision_dataset_draft_built", stage="vision_dataset_draft",
                message="draft prepared -- verified=False, nothing inserted into Dataset Studio",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11: vision quality score ------------------------------------------------

    def run_quality_score_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "vision_quality_score":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'vision_quality_score'")

        objects = self.list_objects(session_public_id, status="active")["items"]
        ocr_matches = [
            r["match_ratio"] for r in session_data["ocr_cross_validation_report"].get("per_page", {}).values()
            if r.get("match_ratio") is not None
        ]
        average_ocr_match = round(sum(ocr_matches) / len(ocr_matches), 3) if ocr_matches else None

        report = score_vision_quality(
            average_image_quality_score=session_data["quality_report"].get("average_quality_score", 0.0),
            average_ocr_match_ratio=average_ocr_match,
            caption_available=bool(session_data["caption_report"].get("dataset_caption")),
            total_object_count=len(objects),
            admin_verified_object_count=sum(1 for o in objects if o["source"] != "auto_unknown"),
            qa_question_count=session_data["qa_report"].get("question_count", 0),
            kg_edge_count=session_data["knowledge_graph_report"].get("edge_count", 0),
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"vision_quality_score_report_json": report, "stage": "vision_report"},
            )
            self._event(
                connection, session_row["id"], "vision_quality_scored", stage="vision_quality_score",
                message=f"overall vision score {report['overall_vision_score']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 12: vision report ---------------------------------------------------------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "vision_report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'vision_report'")

        objects = self.list_objects(session_public_id, status="active")["items"]
        unknown_count = sum(1 for o in objects if o["source"] == "auto_unknown")

        report = generate_vision_report(
            session_public_id=session_public_id, document_source_public_id=session_data["document_source_public_id"],
            quality_score_report=session_data["vision_quality_score_report"], unknown_object_count=unknown_count,
            ocr_status_counts=session_data["ocr_cross_validation_report"].get("status_counts", {}),
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"vision_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "vision_report_generated", stage="vision_report",
                message=f"status={report['status']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 13/14: admin review -> certified -------------------------------------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "certified" if decision == "approve" else "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"vision_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' -- no dataset was written by this service. A "
                    "'certified' session is eligible for MB-15/MB-16/MB-17, never automatically submitted"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainVisionIntelligenceService"]
