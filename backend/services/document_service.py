"""Secure review-first PDF extraction, OCR, segmentation, and candidate import."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import shutil
import subprocess
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.documents import (
    CANDIDATE_JSON,
    DOCUMENT_JSON,
    JOB_JSON,
    PAGE_JSON,
    DocumentRepository,
    decode,
)
from backend.models.documents import CandidatePatch, ProcessRequest, SegmentRequest
from backend.services.dataset_service import content_hash, validate_record

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


def now() -> str:
    return datetime.now(UTC).isoformat()


def safe_filename(filename: str) -> str:
    if "\x00" in filename:
        raise ValidationError("filename contains a null byte")
    name = Path(filename.replace("\\", "/")).name.strip()
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:200]
    if not name or name in {".", ".."}:
        raise ValidationError("invalid upload filename")
    return name


def audit(
    connection, event: str, admin_id: str, resource_id: str, outcome: str = "success", **metadata
) -> None:
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
            "document",
            resource_id,
            outcome,
            dumps_json(metadata),
        ),
    )


def event(
    connection,
    job_id: int,
    event_type: str,
    page_number: int | None = None,
    previous: str | None = None,
    new: str | None = None,
    message: str | None = None,
    **metadata,
) -> None:
    connection.execute(
        """INSERT INTO document_processing_events(processing_job_id,event_type,page_number,
        previous_status,new_status,message,metadata_json) VALUES (?,?,?,?,?,?,?)""",
        (job_id, event_type, page_number, previous, new, message, dumps_json(metadata)),
    )


def clean_document_text(raw: str) -> dict[str, Any]:
    text = unicodedata.normalize("NFC", raw.replace("\r\n", "\n").replace("\r", "\n"))
    text = text.replace("\x00", "").replace("\u200b", "").replace("\ufeff", "")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    warnings: list[dict[str, str]] = []
    if "\ufffd" in raw:
        warnings.append(
            {"code": "replacement_character", "message": "Replacement characters were detected."}
        )
    if re.search(r"([^\w\s])\1{5,}", cleaned, re.UNICODE):
        warnings.append(
            {"code": "repeated_garbage", "message": "Repeated punctuation may indicate OCR noise."}
        )
    visible = [char for char in cleaned if not char.isspace()]
    non_letters = sum(not char.isalnum() for char in visible)
    if visible and non_letters / len(visible) > 0.45:
        warnings.append(
            {
                "code": "high_non_letter_ratio",
                "message": "The page has an unusually high non-letter ratio.",
            }
        )
    if cleaned and len(cleaned) < 24:
        warnings.append({"code": "very_short_text", "message": "The extracted text is very short."})
    nonempty = [line for line in lines if line]
    if len(nonempty) > 2 and (len(nonempty[0]) < 100 or len(nonempty[-1]) < 100):
        warnings.append(
            {
                "code": "header_footer_candidate",
                "message": "Short boundary lines may be a header or footer; review before removal.",
            }
        )
    return {
        "cleaned": cleaned,
        "warnings": warnings,
        "statistics": {"raw_length": len(raw), "cleaned_length": len(cleaned)},
    }


def ocr_capabilities(settings: Settings) -> dict[str, Any]:
    languages: list[str] = []
    version = None
    if pytesseract is not None and settings.ocr_enabled:
        try:
            languages = sorted(set(pytesseract.get_languages(config="")) & {"tam", "eng"})
            version = str(pytesseract.get_tesseract_version()).splitlines()[0]
        except (OSError, RuntimeError, subprocess.SubprocessError):
            languages = []
    configured = settings.ocr_languages.split("+")
    available = bool(languages) and all(item in languages for item in configured)
    return {
        "pdf_extraction": fitz is not None,
        "ocr_available": available,
        "tesseract_version": version,
        "ocr_languages": languages,
        "default_ocr_language": settings.ocr_languages if available else None,
        "max_file_bytes": settings.document_max_file_bytes,
        "max_pages": settings.document_max_pages,
        "render_dpi": settings.pdf_render_dpi,
    }


class DocumentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)

    @property
    def pending_dir(self) -> Path:
        return self.settings.resolved_document_dir / "pending"

    def artifact(self, stored: str) -> Path:
        path = (self.pending_dir / stored).resolve()
        if not path.is_relative_to(self.pending_dir.resolve()):
            raise ValidationError("invalid registered document artifact")
        return path

    def capabilities(self) -> dict[str, Any]:
        return ocr_capabilities(self.settings)

    def audit_rejection(self, admin_id: str, filename: str | None, reason: str) -> None:
        try:
            name = safe_filename(filename or "rejected-document.pdf")
        except ValidationError:
            name = "rejected-document.pdf"
        with self.repository.transaction() as connection:
            audit(
                connection,
                "document_upload_rejected",
                admin_id,
                str(uuid4()),
                "failure",
                filename=name,
                reason=reason,
            )

    async def upload(
        self, upload: UploadFile, strategy: str, language: str, admin_id: str
    ) -> dict[str, Any]:
        if fitz is None:
            raise ValidationError("PDF extraction capability is unavailable")
        original = safe_filename(upload.filename or "")
        if Path(original).suffix.lower() != ".pdf":
            raise ValidationError("unsupported document type")
        mime = (upload.content_type or "").split(";", 1)[0].lower()
        if mime not in {"application/pdf", "application/octet-stream"}:
            raise ValidationError("unsupported document MIME type")
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        stored = f"{uuid4().hex}.pdf"
        target = self.artifact(stored)
        digest, size, prefix = hashlib.sha256(), 0, b""
        try:
            with target.open("xb") as handle:
                os.chmod(target, 0o600)
                while chunk := await upload.read(64 * 1024):
                    size += len(chunk)
                    if size > self.settings.document_max_file_bytes:
                        raise ValidationError("document_too_large")
                    if len(prefix) < 8:
                        prefix += chunk[: 8 - len(prefix)]
                    digest.update(chunk)
                    handle.write(chunk)
            if size == 0:
                raise ValidationError("empty documents are not allowed")
            if not prefix.startswith(b"%PDF-"):
                raise ValidationError("invalid PDF signature")
            with fitz.open(target) as pdf:
                if pdf.needs_pass or pdf.is_encrypted:
                    raise ValidationError("encrypted PDFs are not supported")
                if pdf.page_count < 1:
                    raise ValidationError("PDF has no pages")
                if pdf.page_count > self.settings.document_max_pages:
                    raise ValidationError("PDF page limit exceeded")
                page_count = pdf.page_count
                page_info = []
                for index, page in enumerate(pdf):
                    images = len(page.get_images(full=True))
                    if images > self.settings.pdf_max_images_per_page:
                        raise ValidationError(f"page {index + 1} exceeds the image limit")
                    page_info.append(
                        (
                            index + 1,
                            page.rect.width,
                            page.rect.height,
                            page.rotation,
                            images,
                            len(page.get_text("text").strip()) > 0,
                        )
                    )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        checksum = digest.hexdigest()
        duplicate_public_id = None
        with self.repository.transaction() as connection:
            duplicate = connection.execute(
                "SELECT public_id FROM document_sources WHERE checksum_sha256=?", (checksum,)
            ).fetchone()
            if duplicate:
                target.unlink(missing_ok=True)
                duplicate_public_id = duplicate["public_id"]
                audit(
                    connection,
                    "document_duplicate_upload",
                    admin_id,
                    duplicate_public_id,
                    "warning",
                    filename=original,
                )
        if duplicate_public_id:
            raise ConflictError(f"duplicate document: {duplicate_public_id}")
        with self.repository.transaction() as connection:
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO document_sources(public_id,original_filename,stored_filename,
                document_type,mime_type,file_size_bytes,checksum_sha256,page_count,detected_language,
                extraction_strategy,status,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    original,
                    stored,
                    "pdf",
                    "application/pdf",
                    size,
                    checksum,
                    page_count,
                    language,
                    strategy,
                    "ready",
                    admin_id,
                ),
            )
            document = self.repository.document(connection, public_id)
            for number, width, height, rotation, images, embedded in page_info:
                connection.execute(
                    """INSERT INTO document_pages(public_id,document_source_id,page_number,
                    width_points,height_points,rotation,embedded_text_available,image_count,language)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()),
                        document["id"],
                        number,
                        width,
                        height,
                        rotation,
                        int(embedded),
                        images,
                        language,
                    ),
                )
            job_id, _ = self._create_job(connection, document, "analyze", strategy, admin_id)
            event(
                connection,
                job_id,
                "document_uploaded",
                new="ready",
                filename=original,
                page_count=page_count,
            )
            event(
                connection,
                job_id,
                "validation_completed",
                previous="validating",
                new="completed",
                page_count=page_count,
            )
            connection.execute(
                "UPDATE document_processing_jobs SET status='completed',progress=1,processed_pages=?,successful_pages=?,started_at=?,completed_at=?,updated_at=? WHERE id=?",
                (page_count, page_count, now(), now(), now(), job_id),
            )
            audit(
                connection,
                "document_upload_accepted",
                admin_id,
                public_id,
                filename=original,
                file_size_bytes=size,
                page_count=page_count,
            )
        return self.get(public_id)

    def _create_job(
        self,
        connection,
        document,
        job_type: str,
        strategy: str,
        admin_id: str,
        pages: list[int] | None = None,
    ) -> tuple[int, str]:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO document_processing_jobs(public_id,document_source_id,job_type,status,
            requested_strategy,selected_pages_json,total_pages,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                document["id"],
                job_type,
                "running",
                strategy,
                dumps_json(pages or []),
                len(pages) if pages else document["page_count"],
                admin_id,
            ),
        )
        row = connection.execute(
            "SELECT id FROM document_processing_jobs WHERE public_id=?", (public_id,)
        ).fetchone()
        return row["id"], public_id

    def get(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            value = decode(document, DOCUMENT_JSON)
            counts = connection.execute(
                "SELECT extraction_status,COUNT(*) count FROM document_pages WHERE document_source_id=? GROUP BY extraction_status",
                (document["id"],),
            ).fetchall()
            value["page_status_counts"] = {row["extraction_status"]: row["count"] for row in counts}
            value["checksum_prefix"] = value.pop("checksum_sha256")[:12]
            return value

    def list(
        self, status: str | None, search: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        result = self.repository.list_documents(status, search, page, page_size)
        for item in result["items"]:
            item["checksum_prefix"] = item.pop("checksum_sha256")[:12]
        return result

    def analyze(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            if document["status"] in {"cancelled", "archived"}:
                raise ConflictError("document cannot be analyzed in its current state")
            job_id, job_public_id = self._create_job(
                connection, document, "analyze", document["extraction_strategy"], admin_id
            )
            event(connection, job_id, "analysis_started", previous="queued", new="running")
            rows = connection.execute(
                "SELECT page_number,embedded_text_available,image_count FROM document_pages WHERE document_source_id=? ORDER BY page_number",
                (document["id"],),
            ).fetchall()
            warnings = sum(
                not row["embedded_text_available"] and not row["image_count"] for row in rows
            )
            final = "completed_with_warnings" if warnings else "completed"
            connection.execute(
                "UPDATE document_processing_jobs SET status=?,processed_pages=?,successful_pages=?,warning_pages=?,progress=1,started_at=?,completed_at=?,updated_at=? WHERE id=?",
                (final, len(rows), len(rows) - warnings, warnings, now(), now(), now(), job_id),
            )
            event(
                connection,
                job_id,
                "analysis_completed",
                previous="running",
                new=final,
                warning_pages=warnings,
            )
            audit(
                connection,
                "document_analysis_completed",
                admin_id,
                public_id,
                warning_pages=warnings,
            )
        return self.job(job_public_id)

    def process(
        self, public_id: str, request: ProcessRequest, admin_id: str, *, reprocess: bool = False
    ) -> dict[str, Any]:
        if fitz is None:
            raise ValidationError("PDF extraction capability is unavailable")
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            if document["status"] in {"cancelled", "archived"}:
                raise ConflictError("document cannot be processed in its current state")
            pages = request.pages or list(range(1, document["page_count"] + 1))
            if any(number > document["page_count"] for number in pages):
                raise ValidationError("selected page is outside the document")
            if request.strategy.value == "ocr" and len(pages) > self.settings.ocr_max_pages_per_job:
                raise ValidationError("OCR page limit exceeded")
            job_type = "reprocess_pages" if reprocess else "extract"
            job_id, job_public_id = self._create_job(
                connection, document, job_type, request.strategy.value, admin_id, pages
            )
            event(
                connection,
                job_id,
                "analysis_started" if not reprocess else "page_reprocessed",
                previous="queued",
                new="running",
                page_count=len(pages),
            )
            connection.execute(
                "UPDATE document_sources SET status='processing',updated_at=? WHERE id=?",
                (now(), document["id"]),
            )
        successes = warnings_count = failures = total_chars = 0
        artifact = self.artifact(document["stored_filename"])
        try:
            with fitz.open(artifact) as pdf:
                for number in pages:
                    started = time.monotonic()
                    page = pdf[number - 1]
                    embedded = page.get_text("text")
                    method = "embedded"
                    confidence = None
                    warnings: list[dict[str, str]] = []
                    raw = embedded
                    with self.repository.transaction() as connection:
                        event(
                            connection,
                            job_id,
                            "page_extraction_started",
                            number,
                            "pending",
                            "extracting",
                        )
                    needs_ocr = request.strategy.value == "ocr" or (
                        request.strategy.value in {"auto", "hybrid"}
                        and len(embedded.strip()) < self.settings.ocr_min_text_length
                    )
                    try:
                        if needs_ocr:
                            with self.repository.transaction() as connection:
                                event(
                                    connection,
                                    job_id,
                                    "ocr_started",
                                    number,
                                    "extracting",
                                    "extracting",
                                    language=request.ocr_language or self.settings.ocr_languages,
                                )
                            raw, confidence = self._ocr_page(
                                page, request.ocr_language or self.settings.ocr_languages
                            )
                            method = "ocr" if not embedded.strip() else "hybrid"
                            if (
                                confidence is not None
                                and confidence < self.settings.ocr_confidence_warning_threshold
                            ):
                                warnings.append(
                                    {
                                        "code": "low_ocr_confidence",
                                        "message": "OCR confidence is below the configured threshold.",
                                    }
                                )
                            with self.repository.transaction() as connection:
                                event(
                                    connection,
                                    job_id,
                                    "ocr_completed",
                                    number,
                                    "extracting",
                                    "extracting",
                                    confidence_score=confidence,
                                )
                        result = clean_document_text(raw)
                        warnings.extend(result["warnings"])
                        cleaned = result["cleaned"]
                        if len(cleaned) > self.settings.document_max_page_text_chars:
                            cleaned = cleaned[: self.settings.document_max_page_text_chars]
                            raw = raw[: self.settings.document_max_page_text_chars]
                            warnings.append(
                                {
                                    "code": "page_text_truncated",
                                    "message": "Page text reached the configured limit.",
                                }
                            )
                        if total_chars + len(cleaned) > self.settings.document_max_total_text_chars:
                            raise ValidationError("document total text limit exceeded")
                        total_chars += len(cleaned)
                        status = "warning" if warnings else "success"
                        successes += status == "success"
                        warnings_count += status == "warning"
                        with self.repository.transaction() as connection:
                            connection.execute(
                                """UPDATE document_pages SET extraction_method=?,extraction_status=?,raw_text=?,cleaned_text=?,text_length=?,confidence_score=?,warnings_json=?,error_code=NULL,error_message=NULL,processing_duration_ms=?,updated_at=? WHERE document_source_id=? AND page_number=?""",
                                (
                                    method,
                                    status,
                                    raw,
                                    cleaned,
                                    len(cleaned),
                                    confidence,
                                    dumps_json(warnings),
                                    int((time.monotonic() - started) * 1000),
                                    now(),
                                    document["id"],
                                    number,
                                ),
                            )
                            event(
                                connection,
                                job_id,
                                "page_extraction_warning"
                                if warnings
                                else "page_extraction_completed",
                                number,
                                "extracting",
                                status,
                                method=method,
                                text_length=len(cleaned),
                            )
                    except (
                        ValidationError,
                        RuntimeError,
                        OSError,
                        subprocess.SubprocessError,
                    ) as exc:
                        failures += 1
                        with self.repository.transaction() as connection:
                            connection.execute(
                                "UPDATE document_pages SET extraction_status='failed',error_code=?,error_message=?,processing_duration_ms=?,updated_at=? WHERE document_source_id=? AND page_number=?",
                                (
                                    type(exc).__name__,
                                    str(exc)[:500],
                                    int((time.monotonic() - started) * 1000),
                                    now(),
                                    document["id"],
                                    number,
                                ),
                            )
                            event(
                                connection,
                                job_id,
                                "page_extraction_failed",
                                number,
                                "extracting",
                                "failed",
                                message=str(exc)[:200],
                            )
        except Exception:
            with self.repository.transaction() as connection:
                connection.execute(
                    "UPDATE document_processing_jobs SET status='failed',error_code='processing_error',error_message=?,updated_at=? WHERE id=?",
                    ("document processing failed", now(), job_id),
                )
                connection.execute(
                    "UPDATE document_sources SET status='failed',updated_at=? WHERE id=?",
                    (now(), document["id"]),
                )
                event(connection, job_id, "processing_failed", previous="running", new="failed")
                audit(connection, "document_processing_failed", admin_id, public_id, "failure")
            raise
        final = "completed_with_warnings" if warnings_count or failures else "completed"
        document_status = "review_ready" if successes or warnings_count else "failed"
        with self.repository.transaction() as connection:
            connection.execute(
                "UPDATE document_processing_jobs SET status=?,processed_pages=?,successful_pages=?,warning_pages=?,failed_pages=?,progress=1,started_at=COALESCE(started_at,?),completed_at=?,updated_at=? WHERE id=?",
                (
                    final,
                    len(pages),
                    successes,
                    warnings_count,
                    failures,
                    now(),
                    now(),
                    now(),
                    job_id,
                ),
            )
            connection.execute(
                "UPDATE document_sources SET status=?,updated_at=? WHERE id=?",
                (document_status, now(), document["id"]),
            )
            event(
                connection,
                job_id,
                "processing_completed",
                previous="running",
                new=final,
                successful_pages=successes,
                warning_pages=warnings_count,
                failed_pages=failures,
            )
            audit(
                connection,
                "document_processing_completed",
                admin_id,
                public_id,
                successful_pages=successes,
                warning_pages=warnings_count,
                failed_pages=failures,
            )
        return self.job(job_public_id)

    def _ocr_page(self, page, language: str) -> tuple[str, float | None]:
        capabilities = self.capabilities()
        if not capabilities["ocr_available"] or pytesseract is None or Image is None:
            raise ValidationError("OCR capability is unavailable for configured languages")
        if not set(language.split("+")) <= {"tam", "eng"}:
            raise ValidationError("unsupported OCR language")
        scale = self.settings.pdf_render_dpi / 72
        width, height = int(page.rect.width * scale), int(page.rect.height * scale)
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
            words, confidences = [], []
            for word, confidence in zip(data["text"], data["conf"], strict=True):
                if word.strip():
                    words.append(word)
                    try:
                        score = float(confidence)
                        if score >= 0:
                            confidences.append(score / 100)
                    except (TypeError, ValueError):
                        pass
            return " ".join(words), sum(confidences) / len(confidences) if confidences else None
        except RuntimeError as exc:
            raise ValidationError("OCR page timed out or failed") from exc
        finally:
            image.close()
            del image, pixmap

    def pages(
        self, public_id: str, status: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
        result = self.repository.list_children(
            "document_pages", document["id"], page, page_size, status=status
        )
        for item in result["items"]:
            item["raw_text_preview"] = (item.pop("raw_text") or "")[:300]
            item["cleaned_text_preview"] = (item.pop("cleaned_text") or "")[:300]
        return result

    def page(self, public_id: str, number: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            return decode(self.repository.page(connection, document["id"], number), PAGE_JSON)

    def edit_page(self, public_id: str, number: int, text: str, admin_id: str) -> dict[str, Any]:
        result = clean_document_text(text)
        if len(result["cleaned"]) > self.settings.document_max_page_text_chars:
            raise ValidationError("cleaned page text exceeds the configured limit")
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            page = self.repository.page(connection, document["id"], number)
            revision = connection.execute(
                "SELECT COALESCE(MAX(revision_number),0)+1 FROM document_page_revisions WHERE document_page_id=?",
                (page["id"],),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO document_page_revisions(document_page_id,revision_number,cleaned_text,edited_by_admin_public_id) VALUES (?,?,?,?)",
                (page["id"], revision, result["cleaned"], admin_id),
            )
            connection.execute(
                "UPDATE document_pages SET cleaned_text=?,text_length=?,extraction_method='manual',warnings_json=?,updated_at=? WHERE id=?",
                (
                    result["cleaned"],
                    len(result["cleaned"]),
                    dumps_json(result["warnings"]),
                    now(),
                    page["id"],
                ),
            )
            job_id, _ = self._create_job(
                connection, document, "reprocess_pages", "manual", admin_id, [number]
            )
            connection.execute(
                "UPDATE document_processing_jobs SET status='completed',processed_pages=1,successful_pages=1,progress=1,started_at=?,completed_at=? WHERE id=?",
                (now(), now(), job_id),
            )
            event(
                connection,
                job_id,
                "cleaned_text_edited",
                number,
                "running",
                "completed",
                revision=revision,
            )
            audit(
                connection,
                "document_page_edited",
                admin_id,
                public_id,
                page_number=number,
                revision=revision,
            )
        return self.page(public_id, number)

    def segment(self, public_id: str, request: SegmentRequest, admin_id: str) -> dict[str, Any]:
        max_chars = request.max_chars or self.settings.document_segment_max_chars
        overlap = (
            request.overlap_chars
            if request.overlap_chars is not None
            else self.settings.document_segment_overlap_chars
        )
        if overlap >= max_chars:
            raise ValidationError("segment overlap must be smaller than segment size")
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            pages = connection.execute(
                "SELECT page_number,cleaned_text FROM document_pages WHERE document_source_id=? AND extraction_status IN ('success','warning') ORDER BY page_number",
                (document["id"],),
            ).fetchall()
            if not pages:
                raise ValidationError("no extracted pages are available for segmentation")
            imported = connection.execute(
                "SELECT COUNT(*) FROM document_candidates WHERE document_source_id=? AND status='imported'",
                (document["id"],),
            ).fetchone()[0]
            if imported:
                raise ConflictError("imported candidate history prevents regeneration")
            connection.execute(
                "DELETE FROM document_candidates WHERE document_source_id=?", (document["id"],)
            )
            job_id, job_public_id = self._create_job(
                connection, document, "segment", request.mode.value, admin_id
            )
            event(
                connection,
                job_id,
                "segmentation_started",
                previous="queued",
                new="running",
                mode=request.mode.value,
            )
            segments: list[tuple[int, int, str]] = []
            for page in pages:
                text = page["cleaned_text"] or ""
                if request.mode.value == "page_as_pretrain":
                    chunks = self._windows(text, max_chars, overlap)
                elif request.mode.value == "fixed_window_pretrain":
                    chunks = self._windows(text, max_chars, overlap)
                else:
                    chunks, current = [], ""
                    for paragraph in re.split(r"\n\s*\n", text):
                        paragraph = paragraph.strip()
                        if not paragraph:
                            continue
                        if current and len(current) + len(paragraph) + 2 > max_chars:
                            chunks.extend(self._windows(current, max_chars, overlap))
                            current = paragraph
                        else:
                            current = f"{current}\n\n{paragraph}".strip()
                    if current:
                        chunks.extend(self._windows(current, max_chars, overlap))
                segments.extend(
                    (page["page_number"], page["page_number"], chunk) for chunk in chunks if chunk
                )
            seen: dict[str, str] = {}
            for sequence, (start, end, text) in enumerate(segments, 1):
                values = {
                    "record_type": "pretrain",
                    "language": request.language.value,
                    "instruction": None,
                    "input_text": None,
                    "output_text": text,
                    "normalized_input": None,
                    "metadata": {
                        "document_public_id": public_id,
                        "source_page_start": start,
                        "source_page_end": end,
                    },
                }
                digest = content_hash(values)
                duplicate = connection.execute(
                    "SELECT public_id FROM dataset_records WHERE content_hash=?", (digest,)
                ).fetchone()
                status = "duplicate" if duplicate or digest in seen else "valid"
                duplicate_id = duplicate["public_id"] if duplicate else seen.get(digest)
                candidate_id = str(uuid4())
                seen[digest] = candidate_id
                connection.execute(
                    """INSERT INTO document_candidates(public_id,document_source_id,source_page_start,source_page_end,sequence_number,candidate_type,language,output_text,candidate_text,metadata_json,content_hash,status,duplicate_record_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        candidate_id,
                        document["id"],
                        start,
                        end,
                        sequence,
                        "pretrain",
                        request.language.value,
                        text,
                        text,
                        dumps_json(values["metadata"]),
                        digest,
                        status,
                        duplicate_id,
                    ),
                )
                event(
                    connection,
                    job_id,
                    "candidate_created",
                    metadata={"candidate_public_id": candidate_id, "status": status},
                )
            final = (
                "completed_with_warnings"
                if any(
                    connection.execute(
                        "SELECT 1 FROM document_candidates WHERE document_source_id=? AND status='duplicate'",
                        (document["id"],),
                    ).fetchall()
                )
                else "completed"
            )
            connection.execute(
                "UPDATE document_processing_jobs SET status=?,processed_pages=?,successful_pages=?,progress=1,started_at=?,completed_at=?,updated_at=? WHERE id=?",
                (final, len(pages), len(pages), now(), now(), now(), job_id),
            )
            event(
                connection,
                job_id,
                "segmentation_completed",
                previous="running",
                new=final,
                candidate_count=len(segments),
            )
            audit(
                connection,
                "document_segmented",
                admin_id,
                public_id,
                candidate_count=len(segments),
                mode=request.mode.value,
            )
        return {
            "job": self.job(job_public_id),
            "candidates": self.candidates(public_id, None, 1, 200),
        }

    @staticmethod
    def _windows(text: str, size: int, overlap: int) -> list[str]:
        chunks, start = [], 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                boundary = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
                if boundary > start + size // 2:
                    end = boundary
            while end > start and unicodedata.combining(text[end - 1]):
                end -= 1
            chunks.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
            while start < len(text) and unicodedata.combining(text[start]):
                start += 1
        return [chunk for chunk in chunks if chunk]

    def candidates(
        self, public_id: str, status: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
        return self.repository.list_children(
            "document_candidates", document["id"], page, page_size, status=status
        )

    def candidate(self, public_id: str, candidate_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            return decode(
                self.repository.candidate(connection, document["id"], candidate_id), CANDIDATE_JSON
            )

    def edit_candidate(
        self, public_id: str, candidate_id: str, patch: CandidatePatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            row = self.repository.candidate(connection, document["id"], candidate_id)
            if row["status"] == "imported":
                raise ConflictError("imported candidates are immutable")
            values = {
                key: row[key]
                for key in (
                    "candidate_type",
                    "language",
                    "instruction",
                    "input_text",
                    "output_text",
                    "normalized_input",
                    "candidate_text",
                )
            }
            values.update(patch.model_dump(exclude_unset=True, mode="json"))
            record = {
                "record_type": values["candidate_type"],
                "language": values["language"],
                "instruction": values.get("instruction"),
                "input_text": values.get("input_text"),
                "output_text": values.get("output_text") or values.get("candidate_text"),
                "normalized_input": values.get("normalized_input"),
                "metadata": loads_json(row["metadata_json"]),
            }
            validate_record(record)
            digest = content_hash(record)
            duplicate = connection.execute(
                "SELECT public_id FROM dataset_records WHERE content_hash=?", (digest,)
            ).fetchone()
            status = "duplicate" if duplicate else "valid"
            connection.execute(
                """UPDATE document_candidates SET candidate_type=?,language=?,instruction=?,input_text=?,output_text=?,normalized_input=?,candidate_text=?,content_hash=?,status=?,duplicate_record_public_id=?,updated_at=? WHERE id=?""",
                (
                    values["candidate_type"],
                    values["language"],
                    values.get("instruction"),
                    values.get("input_text"),
                    record["output_text"],
                    values.get("normalized_input"),
                    values.get("candidate_text"),
                    digest,
                    status,
                    duplicate["public_id"] if duplicate else None,
                    now(),
                    row["id"],
                ),
            )
            audit(
                connection,
                "document_candidate_edited",
                admin_id,
                public_id,
                candidate_public_id=candidate_id,
            )
        return self.candidate(public_id, candidate_id)

    def candidate_action(
        self, public_id: str, candidate_id: str, target: str, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            row = self.repository.candidate(connection, document["id"], candidate_id)
            if row["status"] == "imported":
                raise ConflictError("imported candidates are immutable")
            if target == "selected" and row["status"] not in {"valid", "warning", "draft"}:
                raise ConflictError("candidate is not eligible for selection")
            connection.execute(
                "UPDATE document_candidates SET status=?,updated_at=? WHERE id=?",
                (target, now(), row["id"]),
            )
            audit(
                connection,
                f"document_candidate_{target}",
                admin_id,
                public_id,
                candidate_public_id=candidate_id,
            )
        return self.candidate(public_id, candidate_id)

    def import_candidates(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            rows = connection.execute(
                "SELECT * FROM document_candidates WHERE document_source_id=? AND status='selected' ORDER BY sequence_number",
                (document["id"],),
            ).fetchall()
            if not rows:
                already = connection.execute(
                    "SELECT COUNT(*) FROM document_candidates WHERE document_source_id=? AND status='imported'",
                    (document["id"],),
                ).fetchone()[0]
                return {"imported": 0, "already_imported": already, "status": "completed"}
            source_public_id = document["dataset_source_public_id"]
            if not source_public_id:
                source_public_id = str(uuid4())
                connection.execute(
                    """INSERT INTO dataset_sources(name,source_type,status,public_id,original_filename,language,licence_status,checksum_sha256,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        document["original_filename"],
                        "pdf",
                        "ready",
                        source_public_id,
                        document["original_filename"],
                        document["detected_language"],
                        "review_required",
                        document["checksum_sha256"],
                        dumps_json({"document_public_id": public_id}),
                    ),
                )
                connection.execute(
                    "UPDATE document_sources SET dataset_source_public_id=? WHERE id=?",
                    (source_public_id, document["id"]),
                )
            source = connection.execute(
                "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
            ).fetchone()
            job_id, job_public_id = self._create_job(
                connection, document, "candidate_import", "selected", admin_id, []
            )
            imported = skipped = 0
            for row in rows:
                duplicate = connection.execute(
                    "SELECT public_id FROM dataset_records WHERE content_hash=?",
                    (row["content_hash"],),
                ).fetchone()
                if duplicate:
                    connection.execute(
                        "UPDATE document_candidates SET status='duplicate',duplicate_record_public_id=?,updated_at=? WHERE id=?",
                        (duplicate["public_id"], now(), row["id"]),
                    )
                    skipped += 1
                    event(
                        connection,
                        job_id,
                        "candidate_skipped",
                        metadata={
                            "candidate_public_id": row["public_id"],
                            "duplicate_public_id": duplicate["public_id"],
                        },
                    )
                    continue
                record_id = str(uuid4())
                output = row["output_text"] or row["candidate_text"]
                metadata = loads_json(row["metadata_json"])
                metadata.update(
                    {
                        "document_public_id": public_id,
                        "source_page_start": row["source_page_start"],
                        "source_page_end": row["source_page_end"],
                    }
                )
                connection.execute(
                    """INSERT INTO dataset_records(source_id,content,language,status,public_id,record_type,instruction,input_text,output_text,normalized_input,content_hash,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        source["id"],
                        output or row["input_text"] or "",
                        row["language"],
                        "draft",
                        record_id,
                        row["candidate_type"],
                        row["instruction"],
                        row["input_text"],
                        output,
                        row["normalized_input"],
                        row["content_hash"],
                        dumps_json(metadata),
                    ),
                )
                connection.execute(
                    "UPDATE document_candidates SET status='imported',imported_record_public_id=?,imported_at=?,updated_at=? WHERE id=?",
                    (record_id, now(), now(), row["id"]),
                )
                imported += 1
                event(
                    connection,
                    job_id,
                    "candidate_imported",
                    metadata={
                        "candidate_public_id": row["public_id"],
                        "record_public_id": record_id,
                    },
                )
            final = "completed_with_warnings" if skipped else "completed"
            connection.execute(
                "UPDATE document_processing_jobs SET status=?,processed_pages=?,successful_pages=?,warning_pages=?,progress=1,started_at=?,completed_at=?,updated_at=? WHERE id=?",
                (final, len(rows), imported, skipped, now(), now(), now(), job_id),
            )
            connection.execute(
                "UPDATE document_sources SET status=?,completed_at=?,updated_at=? WHERE id=?",
                (final, now(), now(), document["id"]),
            )
            event(
                connection,
                job_id,
                "processing_completed",
                previous="running",
                new=final,
                imported=imported,
                skipped=skipped,
            )
            audit(
                connection,
                "document_candidates_imported",
                admin_id,
                public_id,
                imported=imported,
                skipped=skipped,
                dataset_source_public_id=source_public_id,
            )
        return {
            "imported": imported,
            "skipped": skipped,
            "dataset_source_public_id": source_public_id,
            "job_public_id": job_public_id,
            "status": final,
        }

    def jobs(self, public_id: str, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
        return self.repository.list_children(
            "document_processing_jobs", document["id"], page, page_size
        )

    def job(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return decode(self.repository.job(connection, public_id), JOB_JSON)

    def events(self, job_public_id: str, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            total = connection.execute(
                "SELECT COUNT(*) FROM document_processing_events WHERE processing_job_id=?",
                (job["id"],),
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT event_type,page_number,previous_status,new_status,message,metadata_json,created_at FROM document_processing_events WHERE processing_job_id=? ORDER BY id LIMIT ? OFFSET ?",
                (job["id"], page_size, (page - 1) * page_size),
            ).fetchall()
        import math

        return {
            "items": [decode(row, {"metadata_json"}) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    def state_action(self, public_id: str, target: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, public_id)
            if target == "cancelled" and document["status"] in {
                "completed",
                "completed_with_warnings",
                "archived",
            }:
                raise ConflictError("completed or archived documents cannot be cancelled")
            timestamp_column = "archived_at" if target == "archived" else None
            sql = f"UPDATE document_sources SET status=?,updated_at=?{f',{timestamp_column}=?' if timestamp_column else ''} WHERE id=?"
            params = (
                (target, now(), now(), document["id"])
                if timestamp_column
                else (target, now(), document["id"])
            )
            connection.execute(sql, params)
            job_id, _ = self._create_job(connection, document, "analyze", target, admin_id)
            connection.execute(
                "UPDATE document_processing_jobs SET status='cancelled' WHERE id=?", (job_id,)
            )
            event(
                connection,
                job_id,
                "document_archived" if target == "archived" else "processing_cancelled",
                previous=document["status"],
                new=target,
            )
            audit(connection, f"document_{target}", admin_id, public_id)
            if target == "cancelled":
                quarantine = self.settings.resolved_document_dir / "quarantine"
                quarantine.mkdir(parents=True, exist_ok=True)
                source = self.artifact(document["stored_filename"])
                if source.exists():
                    shutil.move(str(source), quarantine / document["stored_filename"])
        return self.get(public_id)

    def report_csv(self, public_id: str, admin_id: str) -> str:
        document = self.get(public_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "document_public_id",
                "filename",
                "page_count",
                "status",
                "page_number",
                "method",
                "page_status",
                "error_code",
                "candidate_count",
                "imported_count",
            ]
        )
        with self.repository.transaction() as connection:
            row = self.repository.document(connection, public_id)
            candidates = connection.execute(
                "SELECT COUNT(*),SUM(status='imported') FROM document_candidates WHERE document_source_id=?",
                (row["id"],),
            ).fetchone()
            pages = connection.execute(
                "SELECT page_number,extraction_method,extraction_status,error_code FROM document_pages WHERE document_source_id=? ORDER BY page_number",
                (row["id"],),
            ).fetchall()
            for page in pages:
                writer.writerow(
                    [
                        public_id,
                        document["original_filename"],
                        document["page_count"],
                        document["status"],
                        page["page_number"],
                        page["extraction_method"],
                        page["extraction_status"],
                        page["error_code"] or "",
                        candidates[0],
                        candidates[1] or 0,
                    ]
                )
            audit(
                connection, "document_report_downloaded", admin_id, public_id, page_count=len(pages)
            )
        return output.getvalue()
