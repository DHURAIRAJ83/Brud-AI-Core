"""Phase 19 text extraction, normalization, and segmentation.

Actual PDF parsing and OCR reuse Phase 5's optional ``fitz``/
``pytesseract``/``PIL.Image`` imports directly -- exactly
``backend/services/document_service.py``'s established pattern, never a
second OCR engine. Dataset-record and document-record sources reuse
Phase 3/5's already-extracted text via projection, never a second
extraction pass over content already processed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import ExtractionRunCreate, NormalizationRunCreate, SegmentationRequest
from core_model.corpus.boilerplate_removal import detect_boilerplate_lines, remove_boilerplate_lines
from core_model.corpus.document_segmentation import segment_document
from core_model.corpus.ocr_cleanup import clean_ocr_text
from core_model.corpus.tamil_normalization import normalize_tamil_text
from core_model.corpus.text_extraction import (
    build_issue_summary,
    content_checksum,
    extract_html_snapshot_text,
    extract_markdown_text,
    extract_plain_text,
    project_dataset_record,
    project_document_pages,
)
from core_model.corpus.unicode_normalization import normalize_unicode

try:
    import fitz
except ImportError:  # pragma: no cover - capability fallback
    fitz = None

try:
    import pytesseract
    from PIL import Image
except ImportError:  # pragma: no cover - capability fallback
    pytesseract = None
    Image = None


class CorpusProcessingService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- approved-path resolution -----------------------------------------------------

    def _resolve_approved_path(self, relative_path: str) -> Path:
        if ".." in Path(relative_path).parts or Path(relative_path).is_absolute():
            raise ValidationError("invalid source file path")
        for root in self.settings.corpus_approved_roots:
            candidate = (root / relative_path).resolve()
            if candidate.is_relative_to(root.resolve()) and candidate.is_file():
                return candidate
        raise ValidationError("source file path is not under an approved corpus root")

    # --- extraction -----------------------------------------------------

    def _extract_one_file(
        self, connection, file_row, *, extraction_method: str, ocr_language: str
    ) -> dict[str, Any]:
        path = self._resolve_approved_path(file_row["safe_relative_storage_key"])
        raw_bytes = path.read_bytes()

        if extraction_method == "plain_text":
            result = extract_plain_text(raw_bytes)
        elif extraction_method == "markdown_text":
            result = extract_markdown_text(raw_bytes)
        elif extraction_method == "html_snapshot_text":
            result = extract_html_snapshot_text(raw_bytes)
        elif extraction_method == "manual_content":
            result = extract_plain_text(raw_bytes)
        elif extraction_method == "embedded_pdf_text":
            result = self._extract_pdf_embedded(raw_bytes)
        elif extraction_method == "tesseract_ocr":
            result = self._extract_pdf_ocr(raw_bytes, ocr_language)
        else:
            raise ValidationError(f"unsupported extraction method: {extraction_method}")

        return result

    def _extract_pdf_embedded(self, raw_bytes: bytes) -> dict[str, Any]:
        if fitz is None:
            raise ValidationError("PDF extraction capability is unavailable")
        with fitz.open(stream=raw_bytes, filetype="pdf") as pdf:
            if pdf.needs_pass or pdf.is_encrypted:
                raise ValidationError("encrypted PDFs are not accepted as corpus sources")
            pages = [page.get_text("text") for page in pdf]
        text = "\n\n".join(page for page in pages if page.strip())
        return {
            "text": text,
            "confidence": 1.0 if text else 0.0,
            "issues": [] if text else ["no_embedded_text_found"],
            "page_or_section_range": f"1-{len(pages)}" if pages else None,
        }

    def _extract_pdf_ocr(self, raw_bytes: bytes, language: str) -> dict[str, Any]:
        if fitz is None or pytesseract is None or Image is None:
            raise ValidationError("OCR extraction capability is unavailable")
        if not set(language.split("+")) <= {"tam", "eng"}:
            raise ValidationError("unsupported OCR language configuration")
        scale = self.settings.pdf_render_dpi / 72
        page_texts: list[str] = []
        confidences: list[float] = []
        with fitz.open(stream=raw_bytes, filetype="pdf") as pdf:
            for page in pdf:
                width = int(page.rect.width * scale)
                height = int(page.rect.height * scale)
                if width * height > self.settings.pdf_max_render_pixels:
                    raise ValidationError("render pixel limit exceeded")
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                try:
                    data = pytesseract.image_to_data(
                        image,
                        lang=language,
                        output_type=pytesseract.Output.DICT,
                        timeout=self.settings.ocr_page_timeout_seconds,
                    )
                    words, page_confidences = [], []
                    for word, confidence in zip(data["text"], data["conf"], strict=True):
                        if word.strip():
                            words.append(word)
                            try:
                                score = float(confidence)
                                if score >= 0:
                                    page_confidences.append(score / 100)
                            except (TypeError, ValueError):
                                pass
                    page_texts.append(" ".join(words))
                    confidences.extend(page_confidences)
                except RuntimeError as exc:
                    raise ValidationError("OCR page timed out or failed") from exc
                finally:
                    image.close()
                    del image, pixmap
        text = "\n\n".join(page for page in page_texts if page)
        return {
            "text": text,
            "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "issues": [] if text else ["no_ocr_text_recognized"],
            "page_or_section_range": f"1-{len(page_texts)}" if page_texts else None,
        }

    def _extract_dataset_record(self, connection, origin_public_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT instruction, input_text, output_text FROM dataset_records WHERE public_id=?",
            (origin_public_id,),
        ).fetchone()
        if row is None:
            raise ValidationError("referenced dataset record was not found")
        result = project_dataset_record(
            instruction=row["instruction"],
            input_text=row["input_text"],
            output_text=row["output_text"],
        )
        return {**result, "page_or_section_range": None}

    def _extract_document_record(self, connection, origin_public_id: str) -> dict[str, Any]:
        document_row = connection.execute(
            "SELECT id FROM document_sources WHERE public_id=?", (origin_public_id,)
        ).fetchone()
        if document_row is None:
            raise ValidationError("referenced document record was not found")
        pages = connection.execute(
            """SELECT cleaned_text FROM document_pages WHERE document_source_id=?
            ORDER BY page_number""",
            (document_row["id"],),
        ).fetchall()
        result = project_document_pages([page["cleaned_text"] or "" for page in pages])
        return {**result, "page_or_section_range": f"1-{len(pages)}" if pages else None}

    def create_extraction_run(
        self, snapshot_public_id: str, payload: ExtractionRunCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            if self.repository.count_active_extraction_runs(connection) >= (
                self.settings.corpus_max_active_processing_runs
            ):
                raise ValidationError("too many corpus extraction runs are currently active")
            snapshot_row = self.repository.snapshot(connection, snapshot_public_id)
            if snapshot_row["status"] != "ready":
                raise ValidationError("snapshot must be ready before extraction")

            values = payload.model_dump(mode="json")
            values["snapshot_id"] = snapshot_row["id"]
            values["created_by_admin_public_id"] = admin_id
            run_public_id = self.repository.create_extraction_run(connection, values)
            run_row = self.repository.extraction_run(connection, run_public_id)
            self.repository.update_extraction_run(connection, run_row["id"], {"status": "running"})

            files = self.repository.files_for_snapshot(connection, snapshot_row["id"])
            source_row = self.repository.source(connection, snapshot_row["source_public_id"])
            documents_created, failed_files = 0, 0
            for sequence, file_row in enumerate(files):
                try:
                    if payload.extraction_method == "dataset_record_projection":
                        result = self._extract_dataset_record(
                            connection, source_row["origin_reference_public_id"]
                        )
                    elif (
                        payload.extraction_method == "manual_content"
                        and source_row["source_type"] == "document_record"
                    ):
                        result = self._extract_document_record(
                            connection, source_row["origin_reference_public_id"]
                        )
                    else:
                        result = self._extract_one_file(
                            connection,
                            file_row,
                            extraction_method=payload.extraction_method,
                            ocr_language=payload.ocr_language_configuration,
                        )
                except ValidationError:
                    failed_files += 1
                    continue

                text = result["text"]
                doc_values = {
                    "extraction_run_id": run_row["id"],
                    "source_file_id": file_row["id"],
                    "document_sequence": sequence,
                    "raw_text": text,
                    "raw_text_checksum_sha256": content_checksum(text),
                    "page_or_section_range": result.get("page_or_section_range"),
                    "extraction_confidence": result.get("confidence"),
                    "ocr_used": payload.extraction_method == "tesseract_ocr",
                    "character_count": len(text),
                    "issue_summary_json": dumps_json(build_issue_summary(result.get("issues", []))),
                }
                self.repository.create_extracted_document(connection, doc_values)
                documents_created += 1

            final_status = (
                "completed"
                if failed_files == 0
                else "completed_with_warnings"
                if documents_created > 0
                else "failed"
            )
            self.repository.update_extraction_run(
                connection,
                run_row["id"],
                {
                    "status": final_status,
                    "files_processed": len(files),
                    "documents_created": documents_created,
                    "failed_files": failed_files,
                },
            )
            self._audit(
                connection,
                "corpus_extraction_run_completed",
                admin_id,
                run_public_id,
                documents_created=documents_created,
                failed_files=failed_files,
            )
            return self.get_extraction_run(run_public_id, connection=connection)

    def get_extraction_run(self, public_id: str, *, connection=None) -> dict[str, Any]:
        if connection is not None:
            row = self.repository.extraction_run(connection, public_id)
            result = public_row(row)
            result["documents"] = [
                public_row(doc)
                for doc in self.repository.documents_for_extraction_run(connection, row["id"])
            ]
            return result
        with self.repository.transaction() as connection:
            return self.get_extraction_run(public_id, connection=connection)

    # --- normalization -----------------------------------------------------

    def create_normalization_run(
        self,
        extraction_run_public_id: str,
        payload: NormalizationRunCreate,
        admin_id: str,
        *,
        operations: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        """``operations`` gates Phase 20's named normalization profiles
        (``unicode_normalization``/``tamil_normalization``/
        ``boilerplate_detection``, each defaulting to enabled) -- when
        omitted, every operation runs exactly as Phase 19 always did,
        so this is purely additive and never changes default behavior."""

        ops = {
            "unicode_normalization": True,
            "tamil_normalization": True,
            "boilerplate_detection": True,
            **(operations or {}),
        }
        with self.repository.transaction() as connection:
            if self.repository.count_active_normalization_runs(connection) >= (
                self.settings.corpus_max_active_processing_runs
            ):
                raise ValidationError("too many corpus normalization runs are currently active")
            extraction_row = self.repository.extraction_run(connection, extraction_run_public_id)
            if extraction_row["status"] not in {"completed", "completed_with_warnings"}:
                raise ValidationError("extraction run must complete before normalization")

            values = payload.model_dump(mode="json")
            values["extraction_run_id"] = extraction_row["id"]
            values["created_by_admin_public_id"] = admin_id
            run_public_id = self.repository.create_normalization_run(connection, values)
            run_row = self.repository.normalization_run(connection, run_public_id)
            self.repository.update_normalization_run(
                connection, run_row["id"], {"status": "running"}
            )

            documents = self.repository.documents_for_extraction_run(
                connection, extraction_row["id"]
            )
            ocr_cleaned = []
            for document in documents:
                if document["ocr_used"]:
                    cleaned = clean_ocr_text(document["raw_text"])
                    ocr_cleaned.append(
                        {
                            "document": document,
                            "text": cleaned["cleaned_text"],
                            "ocr_corrections": cleaned["total_corrections"],
                        }
                    )
                else:
                    ocr_cleaned.append(
                        {"document": document, "text": document["raw_text"], "ocr_corrections": 0}
                    )

            boilerplate = (
                detect_boilerplate_lines([item["text"] for item in ocr_cleaned])
                if ops["boilerplate_detection"]
                else {"boilerplate_lines": {}}
            )
            transformation_totals: dict[str, int] = {}
            for item in ocr_cleaned:
                if ops["boilerplate_detection"]:
                    removal = remove_boilerplate_lines(
                        item["text"], boilerplate["boilerplate_lines"]
                    )
                else:
                    removal = {"cleaned_text": item["text"], "removed_count": 0}

                if ops["tamil_normalization"]:
                    tamil = normalize_tamil_text(removal["cleaned_text"])
                else:
                    tamil = {
                        "normalized_text": removal["cleaned_text"],
                        "transformation_counts": {},
                    }

                if ops["unicode_normalization"]:
                    unicode_result = normalize_unicode(tamil["normalized_text"])
                    normalized_text = unicode_result["normalized_text"]
                    unicode_integrity_status = unicode_result["unicode_integrity_status"]
                else:
                    normalized_text = tamil["normalized_text"]
                    unicode_integrity_status = "unknown"

                for category, count in tamil["transformation_counts"].items():
                    transformation_totals[category] = transformation_totals.get(category, 0) + count
                transformation_totals["boilerplate_lines_removed"] = (
                    transformation_totals.get("boilerplate_lines_removed", 0)
                    + removal["removed_count"]
                )

                normalized_values = {
                    "normalization_run_id": run_row["id"],
                    "extracted_document_id": item["document"]["id"],
                    "normalized_text": normalized_text,
                    "normalized_text_checksum_sha256": content_checksum(normalized_text),
                    "unicode_integrity_status": unicode_integrity_status,
                    "ocr_corrections_applied": item["ocr_corrections"],
                    "boilerplate_removals_applied": removal["removed_count"],
                    "transformation_counts_json": dumps_json(
                        {
                            **tamil["transformation_counts"],
                            "boilerplate_lines_removed": removal["removed_count"],
                        }
                    ),
                }
                self.repository.create_normalized_document(connection, normalized_values)

            self.repository.update_normalization_run(
                connection,
                run_row["id"],
                {
                    "status": "completed",
                    "documents_processed": len(documents),
                    "transformation_summary_json": dumps_json(transformation_totals),
                },
            )
            self._audit(
                connection,
                "corpus_normalization_run_completed",
                admin_id,
                run_public_id,
                documents_processed=len(documents),
            )
            return self.get_normalization_run(run_public_id, connection=connection)

    def get_normalization_run(self, public_id: str, *, connection=None) -> dict[str, Any]:
        if connection is not None:
            row = self.repository.normalization_run(connection, public_id)
            result = public_row(row)
            result["documents"] = [
                public_row(doc)
                for doc in self.repository.documents_for_normalization_run(connection, row["id"])
            ]
            return result
        with self.repository.transaction() as connection:
            return self.get_normalization_run(public_id, connection=connection)

    # --- segmentation -----------------------------------------------------

    def segment_normalized_document(
        self, normalized_document_public_id: str, payload: SegmentationRequest, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document_row = self.repository.normalized_document(
                connection, normalized_document_public_id
            )
            normalization_run_row = self.repository.normalization_run(
                connection,
                self._public_id_for_normalization_run(
                    connection, document_row["normalization_run_id"]
                ),
            )
            extraction_row = self.repository.extraction_run(
                connection,
                self._public_id_for_extraction_run(
                    connection, normalization_run_row["extraction_run_id"]
                ),
            )
            snapshot_row = self.repository.snapshot(
                connection, self._public_id_for_snapshot(connection, extraction_row["snapshot_id"])
            )
            source_row = self.repository.source(connection, snapshot_row["source_public_id"])
            policy = self.repository.policy(connection, source_row["corpus_policy_public_id"])

            segments = segment_document(
                document_row["normalized_text"],
                strategy=payload.strategy,
                minimum_characters=policy["minimum_segment_characters"],
                maximum_characters=policy["maximum_segment_characters"],
            )
            created = []
            for segment in segments:
                values = {**segment, "normalized_document_id": document_row["id"]}
                values["heading_hierarchy_json"] = dumps_json(values.pop("heading_hierarchy"))
                segment_public_id = self.repository.create_segment(connection, values)
                created.append(segment_public_id)

            self._audit(
                connection,
                "corpus_document_segmented",
                admin_id,
                normalized_document_public_id,
                segment_count=len(created),
            )
            return {
                "normalized_document_public_id": normalized_document_public_id,
                "segment_public_ids": created,
                "segment_count": len(created),
            }

    @staticmethod
    def _public_id_for_normalization_run(connection, row_id: int) -> str:
        return connection.execute(
            "SELECT public_id FROM corpus_normalization_runs WHERE id=?", (row_id,)
        ).fetchone()["public_id"]

    @staticmethod
    def _public_id_for_extraction_run(connection, row_id: int) -> str:
        return connection.execute(
            "SELECT public_id FROM corpus_extraction_runs WHERE id=?", (row_id,)
        ).fetchone()["public_id"]

    @staticmethod
    def _public_id_for_snapshot(connection, row_id: int) -> str:
        return connection.execute(
            "SELECT public_id FROM corpus_source_snapshots WHERE id=?", (row_id,)
        ).fetchone()["public_id"]

    # --- audit -----------------------------------------------------

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event,
                "admin",
                "{}",
                str(uuid4()),
                event,
                "admin",
                admin_id,
                "corpus",
                resource_id,
                "success",
                dumps_json(metadata),
            ),
        )
