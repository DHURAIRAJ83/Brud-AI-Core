"""MB-15: Brud Mini Brain Vision Model Integration & Human-in-the-Loop
Annotation Center -- the orchestration layer for the 14-stage
provider-prediction-to-certification workflow described in the MB-15
task spec.

MB-15 is not another Vision Intelligence module -- that is MB-14,
whose own tables this service only ever reads through its public
methods (`.session()`, `.list_images()`, `.list_objects()`). MB-15
connects a real, pluggable vision inference backend (see `backend.
services.vision_inference_backend`) to those already-extracted images
and structures whatever it predicts into MB-15's own suggestion
tables -- it never writes to MB-14's tables, Dataset Studio, Document
Workspace, Training, Runtime, GGUF export, RAG, MB-06, or MB-07.
Everything this service produces is a suggestion; every admin decision
(approve/reject/request_fix/archive) only records state.

No vision model file exists anywhere in this environment (confirmed
by audit), so a session's real predictions are empty/unavailable
unless an admin has separately loaded a real model via `run_provider_
selection_stage(..., model_path=..., mmproj_path=...)` -- honestly
reflected at every stage, never fabricated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_vision_model import (
    MiniBrainVisionModelRepository,
    public_correction_row,
    public_learning_memory_row,
    public_prediction_row,
    public_provider_row,
    public_session_row,
)
from backend.services.document_service import DocumentService
from backend.services.mini_brain_language_intelligence_service import (
    MiniBrainLanguageIntelligenceService,
)
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)
from backend.services.vision_inference_backend import (
    BACKEND_FACTORIES,
    BackendUnavailableError,
    backend_for_provider,
)
from core_model.mini_brain.vision_model_integration.admin_review_recorder import record_review
from core_model.mini_brain.vision_model_integration.caption_report_builder import build_caption_report
from core_model.mini_brain.vision_model_integration.correction_memory_summarizer import (
    summarize_corrections,
)
from core_model.mini_brain.vision_model_integration.detection_report import summarize_detections
from core_model.mini_brain.vision_model_integration.image_load_report import summarize_loaded_images
from core_model.mini_brain.vision_model_integration.learning_memory_builder import build_learning_memory
from core_model.mini_brain.vision_model_integration.ocr_cross_validator import cross_validate_vision
from core_model.mini_brain.vision_model_integration.provider_selector import select_provider
from core_model.mini_brain.vision_model_integration.relationship_detector import detect_relationships
from core_model.mini_brain.vision_model_integration.scene_report_builder import build_scene_report
from core_model.mini_brain.vision_model_integration.vision_model_quality_engine import (
    score_vision_model_quality,
)
from core_model.mini_brain.vision_model_integration.vision_model_report_generator import (
    generate_vision_model_report,
)

ADMIN_DECISIONS = {"approve", "reject", "request_fix", "archive"}
ADMIN_STATUS_MAP = {
    "approve": "admin_approved", "reject": "admin_rejected", "request_fix": "admin_requested_fix",
    "archive": "admin_archived",
}

# Process-wide, one loaded backend per in-progress session -- mirrors
# MB-04's own Model Manager's `_RUNTIME`/`_MODEL_REGISTRY` module-level
# dict pattern exactly: intentionally process-lifetime
# only, no database table, since a loaded model handle cannot be
# serialized into SQLite.
_SESSION_BACKENDS: dict[str, Any] = {}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def reset_session_backends_for_tests() -> None:
    """Test-only helper -- clears process-wide state between tests."""
    _SESSION_BACKENDS.clear()


class MiniBrainVisionModelService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainVisionModelRepository(settings.resolved_database_path)

        self.vision_intelligence = MiniBrainVisionIntelligenceService(settings)
        self.language_intelligence = MiniBrainLanguageIntelligenceService(settings)
        self.document_service = DocumentService(settings)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, vision_model_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, vision_model_session_id=vision_model_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def _read_mb14_image_bytes(self, vision_session_public_id: str, stored_filename: str) -> bytes:
        path = self.settings.resolved_document_dir / "vision" / vision_session_public_id / stored_filename
        return path.read_bytes()

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
                connection, vision_model_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def list_predictions(self, session_public_id: str, *, review_status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_predictions(
                connection, vision_model_session_id=session_row["id"], review_status=review_status,
            )
        return {"items": [public_prediction_row(row) for row in rows]}

    def list_corrections(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_corrections(connection, vision_model_session_id=session_row["id"])
        return {"items": [public_correction_row(row) for row in rows]}

    def list_learning_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_learning_memory(connection, limit=limit, offset=offset)
        return {"items": [public_learning_memory_row(row) for row in rows]}

    # -- provider registry --------------------------------------------------------

    def list_providers(self, *, status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_providers(connection, status=status)
        return {"items": [public_provider_row(row) for row in rows]}

    def set_provider_status(self, provider_key: str, *, status: str, admin_id: str) -> dict[str, Any]:
        del admin_id
        if status not in {"active", "inactive"}:
            raise ValidationError("status must be 'active' or 'inactive'")
        with self.repository.transaction() as connection:
            return public_provider_row(
                self.repository.set_provider_status(connection, provider_key, status=status)
            )

    # -- session creation --------------------------------------------------------

    def create_session(
        self, *, vision_session_public_id: str, provider_key: str,
        language_session_public_id: str | None = None, admin_id: str,
    ) -> dict[str, Any]:
        # Read-only existence check against MB-14 -- never written to.
        self.vision_intelligence.session(vision_session_public_id)
        if language_session_public_id:
            self.language_intelligence.session(language_session_public_id)

        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, vision_session_public_id=vision_session_public_id,
                language_session_public_id=language_session_public_id, provider_key=provider_key,
                created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="image_load",
                message=f"vision model cycle created for MB-14 session {vision_session_public_id}",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage 1: image load -----------------------------------------------------

    def run_image_load_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "image_load":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'image_load'")

        images = self.vision_intelligence.list_images(session_data["vision_session_public_id"])["items"]
        report = summarize_loaded_images(images=images)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"image_load_report_json": report, "stage": "provider_selection"},
            )
            self._event(
                connection, session_row["id"], "images_loaded", stage="image_load",
                message=f"{report['image_count']} image(s) loaded read-only from MB-14",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 2: provider selection -----------------------------------------------

    def run_provider_selection_stage(
        self, session_public_id: str, *, admin_id: str, model_path: str | None = None,
        mmproj_path: str | None = None, context_length: int = 2048,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "provider_selection":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'provider_selection'")

        registry_rows = self.list_providers()["items"]
        selection = select_provider(
            provider_key=session_data["provider_key"], registry_rows=registry_rows,
            implemented_provider_keys=set(BACKEND_FACTORIES),
        )
        if not selection["selected"]:
            raise ValidationError(f"provider selection rejected: {selection['reason']}")

        backend = backend_for_provider(session_data["provider_key"])
        library_available = backend.is_available()
        model_loaded = False
        load_error = None
        if library_available and model_path:
            try:
                backend.load(model_path, mmproj_path=mmproj_path, context_length=context_length)
                model_loaded = True
                _SESSION_BACKENDS[session_public_id] = backend
            except BackendUnavailableError as exc:
                load_error = str(exc)
        elif not model_path:
            load_error = "no model_path supplied -- provider will report unavailable at every prediction stage"

        report = {
            **selection, "backend_library_available": library_available, "model_loaded": model_loaded,
            "load_error": load_error,
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"provider_report_json": report, "stage": "object_detection"},
            )
            self._event(
                connection, session_row["id"], "provider_selected", stage="provider_selection",
                message=f"provider={session_data['provider_key']} model_loaded={model_loaded}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def _backend_for_session(self, session_data: dict[str, Any]):
        cached = _SESSION_BACKENDS.get(session_data["public_id"])
        if cached is not None:
            return cached
        return backend_for_provider(session_data["provider_key"])

    # -- stage 3: object detection --------------------------------------------------

    def run_object_detection_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "object_detection":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'object_detection'")

        images = self.vision_intelligence.list_images(session_data["vision_session_public_id"])["items"]
        backend = self._backend_for_session(session_data)
        provider_key = session_data["provider_key"]

        provider_available = True
        recorded: list[dict[str, Any]] = []
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for image in images:
                image_bytes = self._read_mb14_image_bytes(
                    session_data["vision_session_public_id"], image["stored_filename"],
                )
                try:
                    result = backend.detect_objects(image_bytes)
                except BackendUnavailableError:
                    provider_available = False
                    break
                for obj in result.get("objects", []):
                    prediction_public_id = self.repository.create_prediction(
                        connection, vision_model_session_id=session_row["id"],
                        image_public_id=image["public_id"], label=obj["label"],
                        confidence=obj.get("confidence") or 0.0, bounding_box=obj.get("bounding_box"),
                        object_class=obj.get("object_class"), color=obj.get("color"),
                        shape=obj.get("shape"), approximate_size=obj.get("approximate_size"),
                        visibility=obj.get("visibility"), provider_key=provider_key, model_version=None,
                        source="ai_predicted",
                    )
                    recorded.append({**obj, "public_id": prediction_public_id})

            report = summarize_detections(provider_available=provider_available, predictions=recorded)
            self.repository.update_session(
                connection, session_public_id,
                {"detection_report_json": report, "stage": "scene_detection"},
            )
            self._event(
                connection, session_row["id"], "objects_detected", stage="object_detection",
                message=f"provider_available={provider_available} -- {report['object_count']} prediction(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 4: scene detection ---------------------------------------------------

    def run_scene_detection_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "scene_detection":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'scene_detection'")

        images = self.vision_intelligence.list_images(session_data["vision_session_public_id"])["items"]
        backend = self._backend_for_session(session_data)
        provider_available, scene, confidence = True, None, None
        if images:
            image_bytes = self._read_mb14_image_bytes(
                session_data["vision_session_public_id"], images[0]["stored_filename"],
            )
            try:
                result = backend.classify_scene(image_bytes)
                scene, confidence = result.get("scene"), result.get("confidence")
            except BackendUnavailableError:
                provider_available = False
        else:
            provider_available = False

        report = build_scene_report(provider_available=provider_available, scene=scene, confidence=confidence)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"scene_report_json": report, "stage": "caption_generation"},
            )
            self._event(
                connection, session_row["id"], "scene_detected", stage="scene_detection",
                message=f"scene={report['scene']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 5: caption generation -----------------------------------------------

    def run_caption_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "caption_generation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'caption_generation'")

        images = self.vision_intelligence.list_images(session_data["vision_session_public_id"])["items"]
        backend = self._backend_for_session(session_data)
        provider_available, caption, confidence = True, None, None
        if images:
            image_bytes = self._read_mb14_image_bytes(
                session_data["vision_session_public_id"], images[0]["stored_filename"],
            )
            try:
                result = backend.generate_caption(image_bytes)
                caption, confidence = result.get("caption"), result.get("confidence")
            except BackendUnavailableError:
                provider_available = False
        else:
            provider_available = False

        report = build_caption_report(provider_available=provider_available, caption=caption, confidence=confidence)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"caption_report_json": report, "stage": "relationship_detection"},
            )
            self._event(
                connection, session_row["id"], "caption_generated", stage="caption_generation",
                message=f"provider_available={provider_available}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: relationship detection (reuses MB-14 knowledge graph geometry) ----

    def run_relationship_detection_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "relationship_detection":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'relationship_detection'")

        predictions = self.list_predictions(session_public_id, review_status="pending")["items"]
        objects = [
            {"public_id": p["public_id"], "label": p["label"], "confidence": p["confidence"],
             "bounding_box": p["bounding_box"]}
            for p in predictions
        ]
        report = detect_relationships(objects=objects)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"relationship_report_json": report, "stage": "ocr_cross_validation"},
            )
            self._event(
                connection, session_row["id"], "relationships_detected", stage="relationship_detection",
                message=f"{report['edge_count']} edge(s) from real box geometry (reused from MB-14)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: OCR cross validation ----------------------------------------------

    def run_ocr_cross_validation_stage(
        self, session_public_id: str, *, admin_id: str, dataset_text: str | None = None,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "ocr_cross_validation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'ocr_cross_validation'")

        mb14_session = self.vision_intelligence.session(session_data["vision_session_public_id"])
        status_counts = mb14_session["ocr_cross_validation_report"].get("status_counts", {})
        if status_counts.get("conflict"):
            document_dataset_status = "conflict"
        elif status_counts.get("mismatch"):
            document_dataset_status = "mismatch"
        elif status_counts.get("match"):
            document_dataset_status = "match"
        else:
            document_dataset_status = "missing"

        pages_with_images = sorted({
            img["page_number"] for img in
            self.vision_intelligence.list_images(session_data["vision_session_public_id"])["items"]
        })
        ocr_text = " ".join(
            self.document_service.page(mb14_session["document_source_public_id"], page)["cleaned_text"] or ""
            for page in pages_with_images
        )

        predictions = self.list_predictions(session_public_id)["items"]
        vision_labels = [p["label"] for p in predictions]

        language_status = None
        if session_data.get("language_session_public_id"):
            language_session = self.language_intelligence.session(session_data["language_session_public_id"])
            language_status = language_session.get("language_report", {}).get("status")

        report = cross_validate_vision(
            ocr_text=ocr_text, dataset_text=dataset_text, vision_labels=vision_labels,
            document_dataset_status=document_dataset_status, language_report_status=language_status,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"ocr_cross_validation_report_json": report, "stage": "quality_score"},
            )
            self._event(
                connection, session_row["id"], "ocr_cross_validated", stage="ocr_cross_validation",
                message=f"status={report['status']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: quality score (pre-correction, AI-only baseline) ------------------

    def run_quality_score_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "quality_score":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'quality_score'")

        predictions = self.list_predictions(session_public_id)["items"]
        report = score_vision_model_quality(
            total_predictions=len(predictions), approved_unchanged_count=0,
            caption_available=bool(session_data["caption_report"].get("long_description")),
            scene_available=bool(session_data["scene_report"].get("scene")),
            bounding_box_count=sum(1 for p in predictions if p["bounding_box"]),
            relationship_edge_count=session_data["relationship_report"].get("edge_count", 0),
            correction_rate=None, average_confidence=session_data["detection_report"].get("average_confidence"),
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"quality_report_json": report, "stage": "admin_review"},
            )
            self._event(
                connection, session_row["id"], "quality_scored", stage="quality_score",
                message=f"AI-only overall score {report['overall_vision_model_score']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: admin review (repeatable) ------------------------------------------

    def review_prediction(
        self, session_public_id: str, *, action: str, prediction_public_id: str | None,
        payload: dict[str, Any], admin_id: str,
    ) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "admin_review":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'admin_review'")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            current_prediction = None
            if prediction_public_id:
                current_prediction = public_prediction_row(
                    self.repository.get_prediction(connection, prediction_public_id)
                )

            decision = record_review(action=action, current_prediction=current_prediction, payload=payload)
            if not decision["allowed"]:
                raise ValidationError(f"review blocked: {decision['reason']}")

            self._apply_review_action(
                connection, session_row=session_row, action=action, current_prediction=current_prediction,
                prediction_public_id=prediction_public_id, payload=payload, admin_id=admin_id,
            )

            self._event(
                connection, session_row["id"], f"review_{action}", stage="admin_review",
                message=f"admin applied '{action}'",
                metadata={"admin_id": admin_id, "prediction_public_id": prediction_public_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    def _apply_review_action(
        self, connection, *, session_row, action: str, current_prediction: dict[str, Any] | None,
        prediction_public_id: str | None, payload: dict[str, Any], admin_id: str,
    ) -> None:
        provider_key = (current_prediction or {}).get("provider_key") or session_row["provider_key"]

        if action == "approve":
            self.repository.update_prediction(
                connection, prediction_public_id,
                {"review_status": "approved", "reviewed_by_admin_public_id": admin_id, "reviewed_at": _now()},
            )
            return

        if action in ("reject", "delete"):
            new_status = "rejected" if action == "reject" else "deleted"
            self.repository.update_prediction(
                connection, prediction_public_id,
                {"review_status": new_status, "reviewed_by_admin_public_id": admin_id, "reviewed_at": _now()},
            )
            self._record_correction(
                connection, session_row=session_row, prediction_public_id=prediction_public_id,
                action=action, wrong_label=current_prediction["label"], correct_label=None,
                reason=payload.get("reason", ""), original_confidence=current_prediction["confidence"],
                provider_key=provider_key, admin_id=admin_id,
            )
            return

        if action == "rename":
            self.repository.update_prediction(
                connection, prediction_public_id,
                {
                    "label": payload["label"], "source": "admin_corrected", "review_status": "approved",
                    "reviewed_by_admin_public_id": admin_id, "reviewed_at": _now(),
                },
            )
            self._record_correction(
                connection, session_row=session_row, prediction_public_id=prediction_public_id,
                action=action, wrong_label=current_prediction["label"], correct_label=payload["label"],
                reason=payload.get("reason", ""), original_confidence=current_prediction["confidence"],
                provider_key=provider_key, admin_id=admin_id,
            )
            return

        if action in ("move_box", "resize_box", "rotate_box"):
            self.repository.update_prediction(
                connection, prediction_public_id,
                {
                    "bounding_box_json": payload["bounding_box"], "source": "admin_corrected",
                    "review_status": "approved", "reviewed_by_admin_public_id": admin_id,
                    "reviewed_at": _now(),
                },
            )
            self._record_correction(
                connection, session_row=session_row, prediction_public_id=prediction_public_id,
                action=action, wrong_label=current_prediction["label"],
                correct_label=current_prediction["label"], reason=payload.get("reason", ""),
                original_confidence=current_prediction["confidence"], provider_key=provider_key,
                admin_id=admin_id,
            )
            return

        if action == "add":
            self.repository.create_prediction(
                connection, vision_model_session_id=session_row["id"],
                image_public_id=payload["image_public_id"], label=payload["label"], confidence=1.0,
                bounding_box=payload.get("bounding_box"), object_class=payload.get("object_class"),
                color=payload.get("color"), shape=payload.get("shape"),
                approximate_size=payload.get("approximate_size"), visibility=payload.get("visibility"),
                provider_key=session_row["provider_key"], model_version=None, source="admin_added",
                review_status="approved",
            )
            return

        if action == "split":
            self.repository.update_prediction(connection, prediction_public_id, {"review_status": "split"})
            for entry in payload["new_predictions"]:
                self.repository.create_prediction(
                    connection, vision_model_session_id=session_row["id"],
                    image_public_id=current_prediction["image_public_id"], label=entry["label"],
                    confidence=1.0, bounding_box=entry["bounding_box"], object_class=None, color=None,
                    shape=None, approximate_size=None, visibility=None,
                    provider_key=session_row["provider_key"], model_version=None, source="admin_added",
                    review_status="approved",
                )
            self._record_correction(
                connection, session_row=session_row, prediction_public_id=prediction_public_id,
                action=action, wrong_label=current_prediction["label"], correct_label=None,
                reason=payload.get("reason", ""), original_confidence=current_prediction["confidence"],
                provider_key=provider_key, admin_id=admin_id,
            )
            return

        if action == "merge":
            for source_public_id in payload["source_prediction_public_ids"]:
                source_row = public_prediction_row(self.repository.get_prediction(connection, source_public_id))
                self.repository.update_prediction(connection, source_public_id, {"review_status": "merged"})
                self._record_correction(
                    connection, session_row=session_row, prediction_public_id=source_public_id,
                    action=action, wrong_label=source_row["label"], correct_label=payload["label"],
                    reason=payload.get("reason", ""), original_confidence=source_row["confidence"],
                    provider_key=source_row["provider_key"], admin_id=admin_id,
                )
            first_source = public_prediction_row(
                self.repository.get_prediction(connection, payload["source_prediction_public_ids"][0])
            )
            self.repository.create_prediction(
                connection, vision_model_session_id=session_row["id"],
                image_public_id=first_source["image_public_id"], label=payload["label"], confidence=1.0,
                bounding_box=payload["bounding_box"], object_class=None, color=None, shape=None,
                approximate_size=None, visibility=None, provider_key=session_row["provider_key"],
                model_version=None, source="admin_added", review_status="approved",
            )
            return

    def _record_correction(
        self, connection, *, session_row, prediction_public_id: str, action: str, wrong_label: str | None,
        correct_label: str | None, reason: str, original_confidence: float | None, provider_key: str,
        admin_id: str,
    ) -> None:
        self.repository.record_correction(
            connection, vision_model_session_id=session_row["id"], prediction_public_id=prediction_public_id,
            action=action, wrong_label=wrong_label, correct_label=correct_label, reason=reason,
            original_confidence=original_confidence, provider_key=provider_key, model_version=None,
            recorded_by_admin_public_id=admin_id,
        )

    def finish_admin_review_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "admin_review":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'admin_review'")

        predictions = self.list_predictions(session_public_id)["items"]
        status_counts: dict[str, int] = {}
        for prediction in predictions:
            status_counts[prediction["review_status"]] = status_counts.get(prediction["review_status"], 0) + 1
        report = {"status_counts": status_counts, "total_predictions": len(predictions)}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"admin_review_report_json": report, "stage": "correction_memory"},
            )
            self._event(
                connection, session_row["id"], "admin_review_finished", stage="admin_review",
                message=f"review complete: {status_counts}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 10: correction memory --------------------------------------------------

    def run_correction_memory_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "correction_memory":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'correction_memory'")

        corrections = self.list_corrections(session_public_id)["items"]
        report = summarize_corrections(corrections=corrections)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"correction_memory_report_json": report, "stage": "knowledge_graph"},
            )
            self._event(
                connection, session_row["id"], "correction_memory_summarized", stage="correction_memory",
                message=f"{report['total_corrections']} correction(s) recorded",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11: knowledge graph (final, post-correction) ---------------------------

    def run_knowledge_graph_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "knowledge_graph":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'knowledge_graph'")

        approved = self.list_predictions(session_public_id, review_status="approved")["items"]
        objects = [
            {"public_id": p["public_id"], "label": p["label"], "confidence": p["confidence"],
             "bounding_box": p["bounding_box"]}
            for p in approved
        ]
        report = detect_relationships(objects=objects)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"knowledge_graph_report_json": report, "stage": "dataset_draft"},
            )
            self._event(
                connection, session_row["id"], "knowledge_graph_built", stage="knowledge_graph",
                message=f"final graph: {report['node_count']} node(s), {report['edge_count']} edge(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 12: dataset draft ----------------------------------------------------------

    def run_dataset_draft_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "dataset_draft":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dataset_draft'")

        approved = self.list_predictions(session_public_id, review_status="approved")["items"]
        report = {
            "objects": approved, "scene": session_data["scene_report"], "caption": session_data["caption_report"],
            "knowledge_graph": session_data["knowledge_graph_report"], "verified": False,
            "status": "needs_admin_review",
            "disclosure": "draft only -- nothing has been inserted into Dataset Studio",
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"dataset_draft_report_json": report, "stage": "vision_report"},
            )
            self._event(
                connection, session_row["id"], "dataset_draft_built", stage="dataset_draft",
                message="draft prepared -- verified=False, nothing inserted into Dataset Studio",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 13: vision report (final quality, post-correction) ---------------------------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "vision_report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'vision_report'")

        predictions = self.list_predictions(session_public_id)["items"]
        learning = build_learning_memory(predictions=predictions)
        approved_unchanged = sum(
            1 for p in predictions if p["review_status"] == "approved" and p["source"] == "ai_predicted"
        )
        quality_report = score_vision_model_quality(
            total_predictions=learning["total_predictions"], approved_unchanged_count=approved_unchanged,
            caption_available=bool(session_data["caption_report"].get("long_description")),
            scene_available=bool(session_data["scene_report"].get("scene")),
            bounding_box_count=sum(1 for p in predictions if p["bounding_box"]),
            relationship_edge_count=session_data["knowledge_graph_report"].get("edge_count", 0),
            correction_rate=learning["correction_rate"],
            average_confidence=session_data["detection_report"].get("average_confidence"),
        )
        report = generate_vision_model_report(
            vision_model_session_public_id=session_public_id,
            vision_session_public_id=session_data["vision_session_public_id"],
            quality_score_report=quality_report,
            approved_count=learning["approved_count"], rejected_count=learning["rejected_count"],
            corrected_count=learning["corrected_count"],
            missing_labels=session_data["ocr_cross_validation_report"].get("missing_labels", []),
            conflicts=(
                [session_data["ocr_cross_validation_report"]["status"]]
                if session_data["ocr_cross_validation_report"].get("status") == "conflict" else []
            ),
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"vision_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "vision_model_report_generated", stage="vision_report",
                message=f"status={report['status']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 14: admin review -> certified -------------------------------------------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")

            predictions = [
                public_prediction_row(row)
                for row in self.repository.list_predictions(connection, vision_model_session_id=session_row["id"])
            ]
            learning = build_learning_memory(predictions=predictions)
            session_public = public_session_row(session_row)
            quality_report = session_public["vision_report"].get("components", {})

            self.repository.record_learning_memory(
                connection, vision_model_session_id=session_row["id"], provider_key=session_row["provider_key"],
                model_version=None, total_predictions=learning["total_predictions"],
                approved_count=learning["approved_count"], corrected_count=learning["corrected_count"],
                rejected_count=learning["rejected_count"], correction_rate=learning["correction_rate"],
                quality_report={"components": quality_report, "overall": session_public["vision_report"].get("overall_vision_model_score")},
                admin_decision=decision, notes="", recorded_by_admin_public_id=admin_id,
            )

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "certified" if decision == "approve" else "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            _SESSION_BACKENDS.pop(session_public_id, None)
            self._event(
                connection, session_row["id"], f"vision_model_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' -- no dataset was written by this service. A "
                    "'certified' session is eligible for MB-16/MB-17/MB-18, never automatically submitted"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainVisionModelService", "reset_session_backends_for_tests"]
