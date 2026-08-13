"""MB-17: Brud Mini Brain Vision RAG & Multimodal Retrieval Center --
the orchestration layer for the 14-stage query-to-closed workflow
described in the MB-17 task spec.

MB-17 is not an OCR engine, vision model, dataset generator, embedding
trainer, training engine, runtime, or release pipeline. It answers
questions by retrieving already-computed evidence from an already-
certified MB-16 dataset (and, through it, MB-14/MB-15's own real
image/object/knowledge-graph data) -- read exclusively through their
own public methods -- fusing that evidence, and grounding an answer in
it. This service never writes to Dataset Studio, Document Workspace,
or any of MB-13/14/15/16's own tables; every retrieval result stays
evidence-linked in MB-17's own tables, and every answer is either
grounded in real, citable evidence or is honestly reported as
insufficient evidence -- never fabricated.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_vision_rag import (
    MiniBrainVisionRagRepository,
    public_evidence_row,
    public_memory_row,
    public_session_row,
)
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)
from backend.services.mini_brain_vision_model_service import MiniBrainVisionModelService
from core_model.mini_brain.vision_rag.evidence_fusion import fuse_evidence
from core_model.mini_brain.vision_rag.grounded_answer_builder import build_grounded_answer
from core_model.mini_brain.vision_rag.hallucination_checker import check_hallucination
from core_model.mini_brain.vision_rag.image_retrieval import retrieve_images
from core_model.mini_brain.vision_rag.knowledge_graph_retrieval import retrieve_graph_edges
from core_model.mini_brain.vision_rag.object_retrieval import retrieve_objects
from core_model.mini_brain.vision_rag.ocr_retrieval import retrieve_ocr
from core_model.mini_brain.vision_rag.query_session_builder import build_query_session
from core_model.mini_brain.vision_rag.rag_memory_builder import build_rag_memory
from core_model.mini_brain.vision_rag.rag_quality_engine import score_rag_quality
from core_model.mini_brain.vision_rag.rag_report_generator import generate_rag_report
from core_model.mini_brain.vision_rag.text_retrieval import retrieve_text

ADMIN_DECISIONS = {"approve", "reject", "flag_hallucination", "archive"}
ADMIN_STATUS_MAP = {
    "approve": "admin_approved", "reject": "admin_rejected", "flag_hallucination": "admin_flagged_hallucination",
    "archive": "admin_archived",
}
CORRECTION_ACTIONS = {"correct_answer", "correct_evidence", "add_evidence"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _timed(fn, /, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn(**kwargs)
    return result, round((time.perf_counter() - started) * 1000, 3)


class MiniBrainVisionRagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainVisionRagRepository(settings.resolved_database_path)

        self.multimodal_dataset = MiniBrainMultimodalDatasetGeneratorService(settings)
        self.vision_intelligence = MiniBrainVisionIntelligenceService(settings)
        self.vision_model = MiniBrainVisionModelService(settings)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, vision_rag_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, vision_rag_session_id=vision_rag_session_id, event_type=event_type,
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
                connection, vision_rag_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def list_evidence(
        self, session_public_id: str, *, evidence_type: str | None = None, status: str | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_evidence(
                connection, vision_rag_session_id=session_row["id"], evidence_type=evidence_type, status=status,
            )
        return {"items": [public_evidence_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    # -- stage 1: create query session --------------------------------------------

    def create_session(
        self, *, multimodal_dataset_session_public_id: str, query: str, admin_id: str,
    ) -> dict[str, Any]:
        dataset_session = self.multimodal_dataset.session(multimodal_dataset_session_public_id)
        if dataset_session["status"] != "admin_approved":
            raise ValidationError(
                "MB-16 dataset session must be certified (status='admin_approved') before Vision RAG can query it"
            )

        setup = build_query_session(query=query, multimodal_dataset_status=dataset_session["status"])
        if not setup["ready"]:
            raise ValidationError("query session is not ready -- an empty query or an uncertified dataset")

        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, multimodal_dataset_session_public_id=multimodal_dataset_session_public_id,
                document_source_public_id=dataset_session["document_source_public_id"],
                language_session_public_id=dataset_session["language_session_public_id"],
                vision_session_public_id=dataset_session["vision_session_public_id"],
                vision_model_session_public_id=dataset_session["vision_model_session_public_id"],
                query=query, query_language=setup["language_category"], created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="query_session",
                message=f"query session created for MB-16 dataset {multimodal_dataset_session_public_id}",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage 2: text retrieval ----------------------------------------------------

    def run_text_retrieval_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "query_session":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'query_session'")

        setup = build_query_session(query=session_data["query"], multimodal_dataset_status="admin_approved")
        records = self.multimodal_dataset.list_records(
            session_data["multimodal_dataset_session_public_id"], status="active",
        )["items"]
        report, latency_ms = _timed(
            retrieve_text, normalized_query=setup["normalized_query"], records=records,
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"text_retrieval_report_json": report, "stage": "ocr_retrieval"},
            )
            self._event(
                connection, session_row["id"], "text_retrieved", stage="text_retrieval",
                message=f"{report['result_count']} text result(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 3: OCR retrieval ------------------------------------------------------

    def run_ocr_retrieval_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "ocr_retrieval":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'ocr_retrieval'")

        setup = build_query_session(query=session_data["query"], multimodal_dataset_status="admin_approved")
        records = self.multimodal_dataset.list_records(
            session_data["multimodal_dataset_session_public_id"], status="active",
        )["items"]
        report, latency_ms = _timed(retrieve_ocr, normalized_query=setup["normalized_query"], records=records)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"ocr_retrieval_report_json": report, "stage": "image_retrieval"},
            )
            self._event(
                connection, session_row["id"], "ocr_retrieved", stage="ocr_retrieval",
                message=f"{report['result_count']} OCR result(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 4: image retrieval -----------------------------------------------------

    def run_image_retrieval_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "image_retrieval":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'image_retrieval'")

        setup = build_query_session(query=session_data["query"], multimodal_dataset_status="admin_approved")
        images: list[dict[str, Any]] = []
        if session_data["vision_session_public_id"]:
            images = self.vision_intelligence.list_images(session_data["vision_session_public_id"])["items"]
        caption_records = self.multimodal_dataset.list_records(
            session_data["multimodal_dataset_session_public_id"], record_type="caption", status="active",
        )["items"]
        report, latency_ms = _timed(
            retrieve_images, normalized_query=setup["normalized_query"], images=images,
            caption_records=caption_records,
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"image_retrieval_report_json": report, "stage": "object_retrieval"},
            )
            self._event(
                connection, session_row["id"], "images_retrieved", stage="image_retrieval",
                message=f"{report['result_count']} image result(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 5: object retrieval -------------------------------------------------------

    def run_object_retrieval_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "object_retrieval":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'object_retrieval'")

        setup = build_query_session(query=session_data["query"], multimodal_dataset_status="admin_approved")
        vision_model_objects: list[dict[str, Any]] = []
        if session_data["vision_model_session_public_id"]:
            vision_model_objects = self.vision_model.list_predictions(
                session_data["vision_model_session_public_id"], review_status="approved",
            )["items"]
        vision_objects: list[dict[str, Any]] = []
        if session_data["vision_session_public_id"]:
            vision_objects = self.vision_intelligence.list_objects(
                session_data["vision_session_public_id"], status="active",
            )["items"]
        report, latency_ms = _timed(
            retrieve_objects, normalized_query=setup["normalized_query"],
            vision_model_objects=vision_model_objects, vision_objects=vision_objects,
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"object_retrieval_report_json": report, "stage": "knowledge_graph_retrieval"},
            )
            self._event(
                connection, session_row["id"], "objects_retrieved", stage="object_retrieval",
                message=f"{report['result_count']} object result(s) from {report['source']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: knowledge graph retrieval ------------------------------------------------

    def run_knowledge_graph_retrieval_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "knowledge_graph_retrieval":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'knowledge_graph_retrieval'")

        setup = build_query_session(query=session_data["query"], multimodal_dataset_status="admin_approved")
        graph: dict[str, Any] = {"nodes": [], "edges": []}
        if session_data["vision_model_session_public_id"]:
            vm_session = self.vision_model.session(session_data["vision_model_session_public_id"])
            graph = vm_session.get("knowledge_graph_report", graph)
        elif session_data["vision_session_public_id"]:
            vi_session = self.vision_intelligence.session(session_data["vision_session_public_id"])
            graph = vi_session.get("knowledge_graph_report", graph)

        report, latency_ms = _timed(retrieve_graph_edges, normalized_query=setup["normalized_query"], graph=graph)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"knowledge_graph_retrieval_report_json": report, "stage": "evidence_fusion"},
            )
            self._event(
                connection, session_row["id"], "graph_retrieved", stage="knowledge_graph_retrieval",
                message=f"{report['matched_edge_count']} matched edge(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: evidence fusion --------------------------------------------------------

    def run_evidence_fusion_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "evidence_fusion":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'evidence_fusion'")

        fused, latency_ms = _timed(
            fuse_evidence, document_source_public_id=session_data["document_source_public_id"],
            text_report=session_data["text_retrieval_report"], ocr_report=session_data["ocr_retrieval_report"],
            image_report=session_data["image_retrieval_report"],
            object_report=session_data["object_retrieval_report"],
            graph_report=session_data["knowledge_graph_retrieval_report"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for item in fused["evidence"]:
                self.repository.create_evidence(
                    connection, vision_rag_session_id=session_row["id"], evidence_type=item["evidence_type"],
                    source_record_public_id=item["source_record_public_id"],
                    document_source_public_id=item["document_source_public_id"], page_number=item["page_number"],
                    image_public_id=item["image_public_id"], object_label=item["object_label"],
                    bounding_box=item["bounding_box"], graph_edge=item["graph_edge"],
                    content_snippet=item["content_snippet"], relevance_score=item["relevance_score"],
                )
            report = {
                "evidence_count": fused["evidence_count"], "counts_by_type": fused["counts_by_type"],
                "latency_ms": latency_ms,
            }
            self.repository.update_session(
                connection, session_public_id, {"evidence_fusion_report_json": report, "stage": "grounded_answer"},
            )
            self._event(
                connection, session_row["id"], "evidence_fused", stage="evidence_fusion",
                message=f"{fused['evidence_count']} evidence item(s) persisted",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: grounded answer ---------------------------------------------------------

    def run_grounded_answer_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "grounded_answer":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'grounded_answer'")

        evidence = self.list_evidence(session_public_id, status="active")["items"]
        evidence_sorted = sorted(evidence, key=lambda item: -item["relevance_score"])
        answer, latency_ms = _timed(
            build_grounded_answer, evidence=evidence_sorted, language_category=session_data["query_language"] or "en",
        )
        answer["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for evidence_public_id in answer["cited_evidence_public_ids"]:
                self.repository.update_evidence(connection, evidence_public_id, {"used_in_answer": 1})
            self.repository.update_session(
                connection, session_public_id, {"answer_report_json": answer, "stage": "quality_evaluation"},
            )
            self._event(
                connection, session_row["id"], "answer_generated", stage="grounded_answer",
                message=f"status={answer['status']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: quality evaluation ------------------------------------------------------

    def run_quality_evaluation_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "quality_evaluation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'quality_evaluation'")

        all_evidence = self.list_evidence(session_public_id)["items"]
        all_ids = {item["public_id"] for item in all_evidence}
        preliminary_hallucination = check_hallucination(
            answer=session_data["answer_report"]["answer"],
            cited_evidence_public_ids=session_data["answer_report"]["cited_evidence_public_ids"],
            all_evidence_public_ids=all_ids,
        )

        report = score_rag_quality(
            text_result_count=session_data["text_retrieval_report"]["result_count"],
            ocr_result_count=session_data["ocr_retrieval_report"]["result_count"],
            image_result_count=session_data["image_retrieval_report"]["result_count"],
            object_result_count=session_data["object_retrieval_report"]["result_count"],
            graph_matched_count=session_data["knowledge_graph_retrieval_report"]["matched_edge_count"],
            evidence_count=session_data["evidence_fusion_report"]["evidence_count"],
            cited_evidence_count=len(session_data["answer_report"]["cited_evidence_public_ids"]),
            hallucination_risk=preliminary_hallucination["hallucination_risk"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"quality_report_json": report, "stage": "hallucination_check"},
            )
            self._event(
                connection, session_row["id"], "quality_scored", stage="quality_evaluation",
                message=f"overall RAG quality {report['overall_rag_quality']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 10: hallucination check ----------------------------------------------------

    def run_hallucination_check_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "hallucination_check":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'hallucination_check'")

        all_evidence = self.list_evidence(session_public_id)["items"]
        all_ids = {item["public_id"] for item in all_evidence}
        report = check_hallucination(
            answer=session_data["answer_report"]["answer"],
            cited_evidence_public_ids=session_data["answer_report"]["cited_evidence_public_ids"],
            all_evidence_public_ids=all_ids,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"hallucination_report_json": report, "stage": "report"},
            )
            self._event(
                connection, session_row["id"], "hallucination_checked", stage="hallucination_check",
                message=f"hallucination_flag={report['hallucination_flag']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11: report ------------------------------------------------------------------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'report'")

        total_latency_ms = sum(
            session_data[key].get("latency_ms", 0.0) or 0.0
            for key in (
                "text_retrieval_report", "ocr_retrieval_report", "image_retrieval_report",
                "object_retrieval_report", "knowledge_graph_retrieval_report", "evidence_fusion_report",
                "answer_report",
            )
        )
        report = generate_rag_report(
            vision_rag_session_public_id=session_public_id, query=session_data["query"],
            quality_report=session_data["quality_report"],
            evidence_report=session_data["evidence_fusion_report"],
            hallucination_report=session_data["hallucination_report"],
            answer_status=session_data["answer_report"]["status"], retrieval_latency_ms=round(total_latency_ms, 3),
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"rag_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "rag_report_generated", stage="report",
                message=f"status={report['status']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 12: admin review (repeatable corrections) -------------------------------------

    def correct_response(
        self, session_public_id: str, *, action: str, payload: dict[str, Any], admin_id: str,
    ) -> dict[str, Any]:
        if action not in CORRECTION_ACTIONS:
            raise ValidationError(f"action must be one of {sorted(CORRECTION_ACTIONS)}")
        session_data = self.session(session_public_id)
        if session_data["stage"] != "awaiting_admin_review":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'awaiting_admin_review'")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)

            if action == "correct_answer":
                if not (payload.get("answer") or "").strip():
                    raise ValidationError("'correct_answer' requires a non-empty answer")
                answer_report = dict(session_data["answer_report"])
                answer_report["answer"] = payload["answer"]
                answer_report["status"] = "admin_corrected"
                self.repository.update_session(connection, session_public_id, {"answer_report_json": answer_report})
            elif action == "correct_evidence":
                evidence_public_id = payload.get("evidence_public_id")
                if not evidence_public_id:
                    raise ValidationError("'correct_evidence' requires an evidence_public_id")
                self.repository.update_evidence(
                    connection, evidence_public_id,
                    {"content_snippet": payload.get("content_snippet", ""), "source": "admin_added"},
                )
            elif action == "add_evidence":
                if not (payload.get("content_snippet") or "").strip():
                    raise ValidationError("'add_evidence' requires a non-empty content_snippet")
                self.repository.create_evidence(
                    connection, vision_rag_session_id=session_row["id"],
                    evidence_type=payload.get("evidence_type", "text"), source_record_public_id=None,
                    document_source_public_id=session_data["document_source_public_id"], page_number=None,
                    image_public_id=None, object_label=None, bounding_box=None, graph_edge=None,
                    content_snippet=payload["content_snippet"], relevance_score=1.0, source="admin_added",
                )

            self._event(
                connection, session_row["id"], f"correction_{action}", stage="awaiting_admin_review",
                message=f"admin applied '{action}'", metadata={"admin_id": admin_id, "payload": payload},
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 13/14: admin review decision -> RAG memory -> closed --------------------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")
            session_public = public_session_row(session_row)

            correction_events = [
                dict(row) for row in self.repository.list_events(
                    connection, vision_rag_session_id=session_row["id"], limit=100, offset=0,
                )
                if row["event_type"].startswith("correction_")
            ]
            memory_fields = build_rag_memory(
                query=session_public["query"], evidence_counts_by_type=session_public["evidence_fusion_report"].get("counts_by_type", {}),
                final_answer=session_public["answer_report"].get("answer"),
                confidence=session_public["answer_report"].get("confidence"),
                hallucination_flag=session_public["hallucination_report"].get("hallucination_flag", False) or decision == "flag_hallucination",
                correction_history=correction_events,
                retrieval_latency_ms=session_public["rag_report"].get("usage_report", {}).get("retrieval_latency_ms"),
            )
            self.repository.record_memory(
                connection, vision_rag_session_id=session_row["id"], query=memory_fields["query"],
                evidence_summary=memory_fields["evidence_summary"], final_answer=memory_fields["final_answer"],
                confidence=memory_fields["confidence"], admin_decision=decision,
                hallucination_flag=memory_fields["hallucination_flag"],
                correction_history=memory_fields["correction_history"],
                retrieval_latency_ms=memory_fields["retrieval_latency_ms"], recorded_by_admin_public_id=admin_id,
            )

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"vision_rag_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' -- RAG Memory recorded. No dataset, document, or "
                    "prior-phase row was ever written by this service"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainVisionRagService"]
