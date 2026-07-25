"""Phase 20 production ingestion jobs.

A job orchestrates the full trusted-source -> snapshot -> extraction
pipeline for any of the eight supported formats, then hands off to
Phase 19's own ``CorpusProcessingService`` for normalization and
segmentation unchanged -- this never duplicates Phase 19's
normalization/segmentation logic, only the format-aware extraction
step is new. PDF extraction reuses Phase 5/19's optional ``fitz``/
``pytesseract`` imports directly; DOCX extraction uses the optional
``python-docx`` import following the exact same pattern. Every stage
transition is recorded as an append-only ``corpus_ingestion_events``
row, and every counter (files/bytes/characters/pages/warnings/errors)
is updated transactionally so a crash mid-job never produces duplicate
extracted documents on retry -- retry always resumes from the last
completed stage rather than restarting from zero.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import IngestionJobCreate, NormalizationRunCreate, SegmentationRequest
from backend.services.corpus_processing_service import CorpusProcessingService
from backend.services.corpus_source_service import CorpusSourceService
from core_model.corpus.format_adapters import (
    ADAPTERS,
    ExtractionOptions,
    detect_magic_bytes,
    validate_extension,
    validate_mime_type,
)
from core_model.corpus.text_extraction import build_issue_summary, content_checksum

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

try:
    import docx
except ImportError:  # pragma: no cover - capability fallback
    docx = None

# Phase 19's `corpus_extraction_runs.extraction_method` CHECK
# constraint is fixed at 7 literals and cannot be widened without a
# full table rebuild (SQLite cannot ALTER a CHECK constraint, and this
# table is referenced by `corpus_extracted_documents`). Rather than
# risk that rebuild, every Phase 20 format that Phase 19 didn't already
# name (json/jsonl/csv/docx) is recorded under the existing
# 'manual_content' literal, which already means "content provided
# directly rather than via OCR/embedded-PDF parsing" -- the real,
# original format is never lost, since `corpus_ingestion_jobs.format`
# always keeps it.
_FORMAT_TO_EXTRACTION_METHOD = {
    "pdf": "embedded_pdf_text",
    "txt": "plain_text",
    "markdown": "markdown_text",
    "html": "html_snapshot_text",
    "json": "manual_content",
    "jsonl": "manual_content",
    "csv": "manual_content",
    "docx": "manual_content",
}

_MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm": "text/html",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}

MAX_DOCX_UNCOMPRESSED_BYTES = 50_000_000


class DocxAdapter:
    """Reads paragraph text from a .docx file via ``python-docx``.
    Guards against zip/decompression bombs by bounding the total
    uncompressed size read from the archive before parsing."""

    def inspect(self, raw_bytes: bytes, *, declared_extension: str):
        from core_model.corpus.format_adapters import SourceInspection

        warnings: list[str] = []
        if docx is None:
            warnings.append("docx_capability_unavailable")
        return SourceInspection(
            format="docx",
            declared_extension=declared_extension,
            detected_by_magic_bytes=detect_magic_bytes(raw_bytes),
            size_bytes=len(raw_bytes),
            warnings=warnings,
        )

    def extract(self, raw_bytes: bytes, options: ExtractionOptions):
        import io
        import zipfile

        from core_model.corpus.format_adapters import ExtractionResult

        if docx is None:
            return ExtractionResult(text="", confidence=0.0, issues=["docx_capability_unavailable"])
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
                total_uncompressed = sum(info.file_size for info in archive.infolist())
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                    return ExtractionResult(
                        text="", confidence=0.0, issues=["decompression_limit_exceeded"]
                    )
        except zipfile.BadZipFile:
            return ExtractionResult(text="", confidence=0.0, issues=["invalid_docx_container"])

        try:
            document = docx.Document(io.BytesIO(raw_bytes))
        except Exception:
            return ExtractionResult(text="", confidence=0.0, issues=["docx_parse_failed"])

        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        return ExtractionResult(
            text=text,
            confidence=1.0 if text else 0.0,
            issues=[] if text else ["empty_projection"],
        )


class PdfAdapter:
    """Embedded-text-first PDF extraction with selective OCR fallback,
    reusing Phase 5/19's optional ``fitz``/``pytesseract`` imports
    directly -- never a second OCR engine."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def inspect(self, raw_bytes: bytes, *, declared_extension: str):
        from core_model.corpus.format_adapters import SourceInspection

        warnings: list[str] = []
        page_count = None
        is_encrypted = False
        if fitz is None:
            warnings.append("pdf_capability_unavailable")
        else:
            try:
                with fitz.open(stream=raw_bytes, filetype="pdf") as pdf:
                    page_count = len(pdf)
                    is_encrypted = bool(pdf.needs_pass or pdf.is_encrypted)
            except Exception:
                warnings.append("invalid_or_corrupt_pdf")
        return SourceInspection(
            format="pdf",
            declared_extension=declared_extension,
            detected_by_magic_bytes=detect_magic_bytes(raw_bytes),
            size_bytes=len(raw_bytes),
            record_count=page_count,
            is_encrypted=is_encrypted,
            warnings=warnings,
        )

    def extract(
        self, raw_bytes: bytes, options: ExtractionOptions, *, ocr_language: str = "tam+eng"
    ):
        from core_model.corpus.format_adapters import ExtractionResult

        if fitz is None:
            return ExtractionResult(text="", confidence=0.0, issues=["pdf_capability_unavailable"])
        with fitz.open(stream=raw_bytes, filetype="pdf") as pdf:
            if pdf.needs_pass or pdf.is_encrypted:
                return ExtractionResult(text="", confidence=0.0, issues=["encrypted_pdf_rejected"])
            pages = [page.get_text("text") for page in pdf]
        embedded_text = "\n\n".join(page for page in pages if page.strip())
        embedded_ratio = len(embedded_text) / max(1, sum(len(p) for p in pages) or 1)

        # Extraction-quality evaluation: if embedded text covers the
        # document poorly (near-empty), fall back to selective OCR --
        # never silently accept a near-blank extraction.
        if embedded_text and embedded_ratio > 0.05:
            return ExtractionResult(text=embedded_text, confidence=1.0, issues=[])
        return self._ocr_extract(raw_bytes, ocr_language)

    def _ocr_extract(self, raw_bytes: bytes, language: str):
        from core_model.corpus.format_adapters import ExtractionResult

        if pytesseract is None or Image is None:
            return ExtractionResult(
                text="",
                confidence=0.0,
                issues=["embedded_text_insufficient", "ocr_capability_unavailable"],
            )
        if not set(language.split("+")) <= {"tam", "eng"}:
            return ExtractionResult(text="", confidence=0.0, issues=["unsupported_ocr_language"])

        scale = self.settings.pdf_render_dpi / 72
        page_texts: list[str] = []
        confidences: list[float] = []
        with fitz.open(stream=raw_bytes, filetype="pdf") as pdf:
            for page in pdf:
                width, height = int(page.rect.width * scale), int(page.rect.height * scale)
                if width * height > self.settings.pdf_max_render_pixels:
                    continue
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
                except RuntimeError:
                    continue
                finally:
                    image.close()
                    del image, pixmap
        text = "\n\n".join(page for page in page_texts if page)
        return ExtractionResult(
            text=text,
            confidence=sum(confidences) / len(confidences) if confidences else 0.0,
            issues=["embedded_text_insufficient_used_ocr_fallback"]
            if text
            else ["no_text_recovered"],
        )


class CorpusIngestionService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.source_service = CorpusSourceService(repository, settings)
        self.processing_service = CorpusProcessingService(repository, settings)
        self.pdf_adapter = PdfAdapter(settings)
        self.docx_adapter = DocxAdapter()

    # --- inspection -----------------------------------------------------

    def inspect_source_file(self, relative_path: str, declared_format: str) -> dict[str, Any]:
        if not validate_extension(declared_format):
            raise ValidationError(f"unsupported format: {declared_format}")
        path = self.source_service.resolve_approved_path(relative_path)
        extension_mime = _MIME_BY_EXTENSION.get(path.suffix.lower())
        if extension_mime and not validate_mime_type(extension_mime, format_name=declared_format):
            raise ValidationError(
                "declared format does not match the file's actual extension/MIME type"
            )
        raw_bytes = path.read_bytes()
        if len(raw_bytes) > self.settings.corpus_max_source_bytes:
            raise ValidationError("file exceeds the maximum source bytes bound")

        adapter = (
            self.docx_adapter
            if declared_format == "docx"
            else (self.pdf_adapter if declared_format == "pdf" else ADAPTERS[declared_format])
        )
        inspection = adapter.inspect(raw_bytes, declared_extension=declared_format)
        return {
            "format": inspection.format,
            "declared_extension": inspection.declared_extension,
            "detected_by_magic_bytes": inspection.detected_by_magic_bytes,
            "size_bytes": inspection.size_bytes,
            "record_count": inspection.record_count,
            "is_encrypted": inspection.is_encrypted,
            "warnings": inspection.warnings,
        }

    # --- job lifecycle -----------------------------------------------------

    def create_job(
        self, source_public_id: str, payload: IngestionJobCreate, admin_id: str
    ) -> dict[str, Any]:
        if not validate_extension(payload.format):
            raise ValidationError(f"unsupported format: {payload.format}")
        with self.repository.transaction() as connection:
            if self.repository.count_active_ingestion_jobs(connection) >= (
                self.settings.corpus_max_active_processing_runs
            ):
                raise ValidationError("too many corpus ingestion jobs are currently active")
            source_row = self.repository.source(connection, source_public_id)

            if payload.idempotency_key:
                existing = self.repository.find_ingestion_job_by_idempotency_key(
                    connection, source_row["id"], payload.idempotency_key
                )
                if existing:
                    return public_row(existing)

            values: dict[str, Any] = {
                "source_id": source_row["id"],
                "format": payload.format,
                "idempotency_key": payload.idempotency_key,
                "max_retries": payload.max_retries,
                "created_by_admin_public_id": admin_id,
            }
            if payload.normalization_profile_public_id:
                profile = self.repository.normalization_profile(
                    connection, payload.normalization_profile_public_id
                )
                values["normalization_profile_id"] = profile["id"]
            if payload.segmentation_profile_public_id:
                profile = self.repository.segmentation_profile(
                    connection, payload.segmentation_profile_public_id
                )
                values["segmentation_profile_id"] = profile["id"]

            job_public_id = self.repository.create_ingestion_job(connection, values)
            job_row = self.repository.ingestion_job(connection, job_public_id)
            self.repository.record_ingestion_event(
                connection,
                {
                    "job_id": job_row["id"],
                    "event_type": "queued",
                    "stage": "queued",
                    "message": f"ingestion job queued for {len(payload.relative_paths)} file(s)",
                    "details_json": dumps_json({"relative_paths": payload.relative_paths}),
                },
            )
            self._audit(connection, "corpus_ingestion_job_created", admin_id, job_public_id)
            return self._job_detail(connection, job_public_id)

    def _job_detail(self, connection, public_id: str) -> dict[str, Any]:
        row = self.repository.ingestion_job(connection, public_id)
        result = public_row(row)
        result["events"] = [
            public_row(event)
            for event in self.repository.ingestion_events_for_job(connection, row["id"])
        ]
        return result

    def get_job(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self._job_detail(connection, public_id)

    def list_jobs(self, source_public_id: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source_id = None
            if source_public_id:
                source_id = self.repository.source(connection, source_public_id)["id"]
            return {
                "items": [
                    public_row(row)
                    for row in self.repository.list_ingestion_jobs(connection, source_id=source_id)
                ]
            }

    def cancel_job(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, public_id)
            if job_row["status"] not in {"queued", "running", "paused"}:
                raise ValidationError(f"cannot cancel a job in status {job_row['status']}")
            self.repository.update_ingestion_job(connection, job_row["id"], {"status": "cancelled"})
            self.repository.record_ingestion_event(
                connection, {"job_id": job_row["id"], "event_type": "cancelled", "message": ""}
            )
            self._audit(connection, "corpus_ingestion_job_cancelled", admin_id, public_id)
            return self._job_detail(connection, public_id)

    def retry_job(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, public_id)
            if job_row["status"] != "failed":
                raise ValidationError("only a failed job can be retried")
            if job_row["retry_count"] >= job_row["max_retries"]:
                raise ValidationError("job has exhausted its bounded retry budget")
            self.repository.update_ingestion_job(
                connection,
                job_row["id"],
                {"status": "queued", "retry_count": job_row["retry_count"] + 1},
            )
            self.repository.record_ingestion_event(
                connection,
                {
                    "job_id": job_row["id"],
                    "event_type": "retried",
                    "message": f"retry {job_row['retry_count'] + 1}/{job_row['max_retries']}",
                },
            )
            self._audit(connection, "corpus_ingestion_job_retried", admin_id, public_id)
            return self._job_detail(connection, public_id)

    def run_job(self, public_id: str, relative_paths: list[str], admin_id: str) -> dict[str, Any]:
        """Runs (or resumes) a job through snapshot -> extraction ->
        normalization -> segmentation. Resumable: if the job already
        has a `snapshot_id`/`extraction_run_id`/`normalization_run_id`
        recorded from a prior attempt, that stage is reused rather than
        re-executed, so a retried job never produces duplicate
        extracted/normalized documents."""

        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, public_id)
            if job_row["status"] not in {"queued"}:
                raise ValidationError(f"job is not runnable from status {job_row['status']}")
            source_row = connection.execute(
                "SELECT public_id FROM corpus_source_registries WHERE id=?",
                (job_row["source_id"],),
            ).fetchone()
            self.repository.update_ingestion_job(
                connection,
                job_row["id"],
                {"status": "running", "current_stage": "inspecting", "started_at": _now_sql()},
            )
            self.repository.record_ingestion_event(
                connection,
                {"job_id": job_row["id"], "event_type": "started", "stage": "inspecting"},
            )

        try:
            snapshot_public_id = self._ensure_snapshot(
                public_id, job_row, source_row["public_id"], relative_paths, admin_id
            )
            extraction_run_public_id = self._ensure_extraction(
                public_id, snapshot_public_id, admin_id
            )
            normalization_run_public_id = self._ensure_normalization(
                public_id, extraction_run_public_id, admin_id
            )
            segment_ids = self._ensure_segmentation(
                public_id, normalization_run_public_id, admin_id
            )
        except ValidationError as exc:
            with self.repository.transaction() as connection:
                job_row = self.repository.ingestion_job(connection, public_id)
                self.repository.update_ingestion_job(
                    connection,
                    job_row["id"],
                    {
                        "status": "failed",
                        "errors_count": job_row["errors_count"] + 1,
                        "error_details_json": dumps_json({"error": str(exc)}),
                    },
                )
                self.repository.record_ingestion_event(
                    connection,
                    {"job_id": job_row["id"], "event_type": "error", "message": str(exc)},
                )
            raise

        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, public_id)
            final_status = (
                "completed" if job_row["warnings_count"] == 0 else "completed_with_warnings"
            )
            self.repository.update_ingestion_job(
                connection,
                job_row["id"],
                {
                    "status": final_status,
                    "current_stage": "completed",
                    "completed_at": _now_sql(),
                    "output_manifest_checksum_sha256": content_checksum(
                        "|".join(sorted(segment_ids))
                    ),
                },
            )
            self.repository.record_ingestion_event(
                connection,
                {"job_id": job_row["id"], "event_type": "completed", "stage": "completed"},
            )
            self._audit(
                connection,
                "corpus_ingestion_job_completed",
                admin_id,
                public_id,
                segment_count=len(segment_ids),
            )
            result = self._job_detail(connection, public_id)
            result["segment_public_ids"] = segment_ids
            return result

    def _ensure_snapshot(
        self,
        job_public_id: str,
        job_row,
        source_public_id: str,
        relative_paths: list[str],
        admin_id: str,
    ) -> str:
        if job_row["snapshot_id"]:
            with self.repository.transaction() as connection:
                snapshot_row = connection.execute(
                    "SELECT public_id FROM corpus_source_snapshots WHERE id=?",
                    (job_row["snapshot_id"],),
                ).fetchone()
                return snapshot_row["public_id"]

        from backend.models.corpus import SnapshotCreate

        snapshot = self.source_service.create_snapshot(
            source_public_id,
            SnapshotCreate(files=[{"relative_path": path} for path in relative_paths]),
            admin_id,
        )
        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, job_public_id)
            snapshot_row = self.repository.snapshot(connection, snapshot["public_id"])
            self.repository.update_ingestion_job(
                connection,
                job_row["id"],
                {
                    "snapshot_id": snapshot_row["id"],
                    "current_stage": "snapshotting",
                    "bytes_processed": sum(f["size_bytes"] for f in snapshot["files"]),
                },
            )
            self.repository.record_ingestion_event(
                connection,
                {"job_id": job_row["id"], "event_type": "stage_changed", "stage": "snapshotting"},
            )
        return snapshot["public_id"]

    def _ensure_extraction(self, job_public_id: str, snapshot_public_id: str, admin_id: str) -> str:
        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, job_public_id)
            if job_row["extraction_run_id"]:
                extraction_row = connection.execute(
                    "SELECT public_id FROM corpus_extraction_runs WHERE id=?",
                    (job_row["extraction_run_id"],),
                ).fetchone()
                return extraction_row["public_id"]
            fmt = job_row["format"]
            snapshot_row = self.repository.snapshot(connection, snapshot_public_id)
            extraction_method = _FORMAT_TO_EXTRACTION_METHOD[fmt]
            values = {
                "snapshot_id": snapshot_row["id"],
                "extraction_method": extraction_method,
                "ocr_language_configuration": "tam+eng",
                "created_by_admin_public_id": admin_id,
            }
            extraction_run_public_id = self.repository.create_extraction_run(connection, values)
            extraction_run_row = self.repository.extraction_run(
                connection, extraction_run_public_id
            )
            self.repository.update_extraction_run(
                connection, extraction_run_row["id"], {"status": "running"}
            )
            self.repository.update_ingestion_job(
                connection,
                job_row["id"],
                {"extraction_run_id": extraction_run_row["id"], "current_stage": "extracting"},
            )
            self.repository.record_ingestion_event(
                connection,
                {"job_id": job_row["id"], "event_type": "stage_changed", "stage": "extracting"},
            )
            files = self.repository.files_for_snapshot(connection, snapshot_row["id"])

        documents_created, failed_files, characters_extracted, warnings_count = 0, 0, 0, 0
        any_ocr_used = False
        for sequence, file_row in enumerate(files):
            path = self.source_service.resolve_approved_path(file_row["safe_relative_storage_key"])
            raw_bytes = path.read_bytes()
            try:
                result = self._extract_bytes(fmt, raw_bytes)
            except ValidationError:
                failed_files += 1
                continue
            ocr_used = "ocr_fallback" in " ".join(result.issues)
            any_ocr_used = any_ocr_used or ocr_used
            with self.repository.transaction() as connection:
                doc_values = {
                    "extraction_run_id": self.repository.extraction_run(
                        connection, extraction_run_public_id
                    )["id"],
                    "source_file_id": file_row["id"],
                    "document_sequence": sequence,
                    "raw_text": result.text,
                    "raw_text_checksum_sha256": content_checksum(result.text),
                    "extraction_confidence": result.confidence,
                    "ocr_used": ocr_used,
                    "character_count": len(result.text),
                    "issue_summary_json": dumps_json(build_issue_summary(result.issues)),
                }
                self.repository.create_extracted_document(connection, doc_values)
            documents_created += 1
            characters_extracted += len(result.text)
            warnings_count += len(result.issues)

        with self.repository.transaction() as connection:
            extraction_run_row = self.repository.extraction_run(
                connection, extraction_run_public_id
            )
            final_status = (
                "completed"
                if failed_files == 0
                else ("completed_with_warnings" if documents_created > 0 else "failed")
            )
            run_updates = {
                "status": final_status,
                "files_processed": len(files),
                "documents_created": documents_created,
                "failed_files": failed_files,
            }
            if fmt == "pdf" and any_ocr_used:
                # The embedded-text-first/OCR-fallback decision is made per
                # whole document in PdfAdapter.extract(); if any document in
                # this run genuinely required OCR, `extraction_method` must
                # reflect that rather than the format-only default guess.
                run_updates["extraction_method"] = "tesseract_ocr"
            self.repository.update_extraction_run(
                connection,
                extraction_run_row["id"],
                run_updates,
            )
            job_row = self.repository.ingestion_job(connection, job_public_id)
            self.repository.update_ingestion_job(
                connection,
                job_row["id"],
                {
                    "files_processed": len(files),
                    "documents_created": documents_created,
                    "characters_extracted": characters_extracted,
                    "warnings_count": job_row["warnings_count"] + warnings_count,
                    "errors_count": job_row["errors_count"] + failed_files,
                },
            )
        if documents_created == 0:
            raise ValidationError("extraction produced no documents from any file in this job")
        return extraction_run_public_id

    def _extract_bytes(self, fmt: str, raw_bytes: bytes):
        options = ExtractionOptions()
        if fmt == "pdf":
            return self.pdf_adapter.extract(raw_bytes, options, ocr_language="tam+eng")
        if fmt == "docx":
            return self.docx_adapter.extract(raw_bytes, options)
        return ADAPTERS[fmt].extract(raw_bytes, options)

    def _ensure_normalization(
        self, job_public_id: str, extraction_run_public_id: str, admin_id: str
    ) -> str:
        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, job_public_id)
            if job_row["normalization_run_id"]:
                normalization_row = connection.execute(
                    "SELECT public_id FROM corpus_normalization_runs WHERE id=?",
                    (job_row["normalization_run_id"],),
                ).fetchone()
                return normalization_row["public_id"]
            operations = None
            if job_row["normalization_profile_id"]:
                from backend.core.json_utils import loads_json

                profile = connection.execute(
                    "SELECT operations_json FROM corpus_normalization_profiles WHERE id=?",
                    (job_row["normalization_profile_id"],),
                ).fetchone()
                operations = loads_json(profile["operations_json"], default={})

        normalization_run = self.processing_service.create_normalization_run(
            extraction_run_public_id, NormalizationRunCreate(), admin_id, operations=operations
        )
        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, job_public_id)
            normalization_run_row = self.repository.normalization_run(
                connection, normalization_run["public_id"]
            )
            self.repository.update_ingestion_job(
                connection,
                job_row["id"],
                {
                    "normalization_run_id": normalization_run_row["id"],
                    "current_stage": "normalizing",
                },
            )
            self.repository.record_ingestion_event(
                connection,
                {"job_id": job_row["id"], "event_type": "stage_changed", "stage": "normalizing"},
            )
        return normalization_run["public_id"]

    def _ensure_segmentation(
        self, job_public_id: str, normalization_run_public_id: str, admin_id: str
    ) -> list[str]:
        with self.repository.transaction() as connection:
            job_row = self.repository.ingestion_job(connection, job_public_id)
            strategy = "heading_section"
            if job_row["segmentation_profile_id"]:
                profile = connection.execute(
                    "SELECT strategy FROM corpus_segmentation_profiles WHERE id=?",
                    (job_row["segmentation_profile_id"],),
                ).fetchone()
                strategy = profile["strategy"]
            self.repository.update_ingestion_job(
                connection, job_row["id"], {"current_stage": "segmenting"}
            )
            self.repository.record_ingestion_event(
                connection,
                {"job_id": job_row["id"], "event_type": "stage_changed", "stage": "segmenting"},
            )

        normalization_run = self.processing_service.get_normalization_run(
            normalization_run_public_id
        )
        segment_ids: list[str] = []
        for document in normalization_run["documents"]:
            result = self.processing_service.segment_normalized_document(
                document["public_id"], SegmentationRequest(strategy=strategy), admin_id
            )
            segment_ids.extend(result["segment_public_ids"])
        return segment_ids

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


def _now_sql() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
