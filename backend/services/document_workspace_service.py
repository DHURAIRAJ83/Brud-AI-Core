"""Phase 4 (Data Studio) PDF Research Workspace services.

Enhances the existing Phase 5 PDF pipeline (`backend/services/document_service.py`)
rather than replacing it: every service here composes `DocumentService`/
`DocumentRepository` for shared primitives (fetching a document/page,
the artifact path, OCR capabilities, running extraction/segmentation)
instead of re-implementing them. `DocumentService.process()`,
`.edit_page()`, and `.segment()` are called exactly as they already
exist and are never modified.
"""

from __future__ import annotations

import hashlib
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.data_sources import public_row as source_public_row
from backend.database.repositories.documents import (
    EXTRACTION_JSON,
    REPEATED_ELEMENT_JSON,
    REVIEW_EVENT_JSON,
    DocumentRepository,
    decode,
)
from backend.models.documents import ProcessRequest
from backend.services.document_service import DocumentService, audit, now
from core_model.document_workspace.cleanup_suggestions import generate_cleanup_suggestions
from core_model.document_workspace.extraction_decision import decide_extraction_method
from core_model.document_workspace.lifecycle import validate_transition
from core_model.document_workspace.repeated_elements import detect_repeated_elements

_REVIEW_STATUS_COUNT_KEYS = (
    "pending",
    "needs_correction",
    "corrected",
    "approved",
    "rejected",
    "excluded",
)


class PDFResearchWorkspaceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)
        self.documents = DocumentService(settings)
        self.source_repository = DataSourceRepository(settings.resolved_database_path)

    def _source_context(self, document_public_id: str) -> dict[str, Any]:
        with self.source_repository.transaction() as connection:
            links = self.source_repository.links_for_entity(
                connection, "document", document_public_id
            )
            if not links:
                return {"source_status": "unlinked", "source": None, "rights_warnings": []}
            link = links[0]
            source = self.source_repository.source_by_id(connection, link["data_source_id"])
            rights_row = self.source_repository.rights_for_source(connection, source["id"])
        source_public = source_public_row(source)
        warnings: list[str] = []
        if rights_row is None or rights_row["rights_status"] in ("unknown", "pending_review"):
            warnings.append("Source rights are unknown or still pending review.")
        if source_public["status"] in ("rejected", "restricted"):
            warnings.append(f"Source is currently {source_public['status']}.")
        return {
            "source_status": "linked",
            "source": source_public,
            "rights_warnings": warnings,
        }

    def link_source(
        self, document_public_id: str, source_public_id: str, admin_id: str
    ) -> dict[str, Any]:
        with self.source_repository.transaction() as connection:
            source = self.source_repository.source(connection, source_public_id)
            existing = self.source_repository.links_for_entity(
                connection, "document", document_public_id
            )
            for link in existing:
                self.source_repository.delete_link(connection, link["id"])
            link_public_id = self.source_repository.create_link(
                connection,
                {
                    "data_source_id": source["id"],
                    "entity_type": "document",
                    "entity_public_id": document_public_id,
                    "relationship_type": "primary_source",
                    "created_by_admin_public_id": admin_id,
                },
            )
            result = source_public_row(self.source_repository.link(connection, link_public_id))
        with self.documents.repository.transaction() as connection:
            audit(
                connection,
                "document_source_linked",
                admin_id,
                document_public_id,
                source_public_id=source_public_id,
            )
        return result

    def workspace(self, document_public_id: str) -> dict[str, Any]:
        document = self.documents.get(document_public_id)
        with self.repository.transaction() as connection:
            document_row = self.repository.document(connection, document_public_id)
            review_counts_rows = connection.execute(
                "SELECT review_status,COUNT(*) count FROM document_pages "
                "WHERE document_source_id=? GROUP BY review_status",
                (document_row["id"],),
            ).fetchall()
            low_confidence = connection.execute(
                "SELECT COUNT(*) FROM document_pages WHERE document_source_id=? "
                "AND confidence_score IS NOT NULL AND confidence_score < ?",
                (document_row["id"], self.settings.ocr_confidence_warning_threshold),
            ).fetchone()[0]
            with_warnings = connection.execute(
                "SELECT COUNT(*) FROM document_pages WHERE document_source_id=? "
                "AND warnings_json != '[]'",
                (document_row["id"],),
            ).fetchone()[0]
        review_counts = {key: 0 for key in _REVIEW_STATUS_COUNT_KEYS}
        review_counts.update({row["review_status"]: row["count"] for row in review_counts_rows})
        source_context = self._source_context(document_public_id)
        readiness = self._readiness(document_row["page_count"], review_counts, source_context)
        return {
            **document,
            **source_context,
            "review_status_counts": review_counts,
            "low_confidence_page_count": low_confidence,
            "pages_with_warnings_count": with_warnings,
            "readiness": readiness,
        }

    @staticmethod
    def _readiness(
        total_pages: int, review_counts: dict[str, int], source_context: dict[str, Any]
    ) -> str:
        approved = review_counts.get("approved", 0)
        unresolved = (
            review_counts.get("pending", 0)
            + review_counts.get("needs_correction", 0)
            + review_counts.get("corrected", 0)
        )
        if not total_pages or approved == 0 or source_context["source_status"] == "unlinked":
            return "not_ready"
        if unresolved == 0:
            return "ready_for_segmentation"
        return "partially_ready"

    def send_to_segmentation(
        self, document_public_id: str, request, admin_id: str
    ) -> dict[str, Any]:
        workspace = self.workspace(document_public_id)
        if workspace["readiness"] == "not_ready":
            raise ValidationError(
                "this document is not ready for segmentation -- link a source and approve "
                "at least one page first"
            )
        return self.documents.segment(document_public_id, request, admin_id)

    def render_page_image(self, document_public_id: str, page_number: int) -> bytes:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - capability fallback
            raise ValidationError("PDF rendering capability is unavailable") from exc
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            self.repository.page(connection, document["id"], page_number)
        artifact = self.documents.artifact(document["stored_filename"])
        scale = self.settings.pdf_render_dpi / 72
        with fitz.open(artifact) as pdf:
            if page_number < 1 or page_number > pdf.page_count:
                raise NotFoundError("document page not found")
            page = pdf[page_number - 1]
            width, height = int(page.rect.width * scale), int(page.rect.height * scale)
            if width * height > self.settings.pdf_max_render_pixels:
                raise ValidationError("render pixel limit exceeded")
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return pixmap.tobytes("png")

    def extract_with_history(
        self,
        document_public_id: str,
        request: ProcessRequest,
        admin_id: str,
        *,
        reprocess: bool = False,
    ) -> dict[str, Any]:
        """Wraps the existing, unmodified `DocumentService.process()` and
        additionally records an immutable extraction-attempt snapshot per
        page afterwards -- satisfies "raw text must never be overwritten"
        (rule 6) without changing what `process()`/`reprocess` already do."""

        with self.documents.repository.transaction() as connection:
            document_row = self.documents.repository.document(connection, document_public_id)
        page_numbers = request.pages or list(range(1, document_row["page_count"] + 1))
        result = self.documents.process(document_public_id, request, admin_id, reprocess=reprocess)
        capabilities = self.documents.capabilities()
        with self.repository.transaction() as connection:
            document_row = self.repository.document(connection, document_public_id)
            for number in page_numbers:
                page = self.repository.page(connection, document_row["id"], number)
                method = page["extraction_method"]
                if method == "none":
                    continue
                raw_text = page["raw_text"] or ""
                preprocessing = {
                    "rotation_applied": page["rotation"],
                    "preprocessing_profile": "default_v1",
                    "preprocessing_version": 1,
                }
                self.repository.create_extraction(
                    connection,
                    {
                        "document_page_id": page["id"],
                        "extraction_method": method if method != "none" else "failed",
                        "raw_text": raw_text,
                        "raw_text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
                        "ocr_engine": "tesseract" if method in ("ocr", "hybrid") else None,
                        "ocr_engine_version": capabilities.get("tesseract_version")
                        if method in ("ocr", "hybrid")
                        else None,
                        "ocr_language_mode": request.ocr_language or self.settings.ocr_languages
                        if method in ("ocr", "hybrid")
                        else None,
                        "ocr_confidence": page["confidence_score"],
                        "preprocessing_metadata_json": dumps_json(preprocessing),
                        "extraction_warnings_json": page["warnings_json"],
                        "created_by_admin_public_id": admin_id,
                    },
                )
        return result

    def extraction_history(self, document_public_id: str, page_number: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            items = [
                decode(row, EXTRACTION_JSON)
                for row in self.repository.list_extractions(connection, page["id"])
            ]
        return {"items": items}

    def decide_extraction_method_preview(
        self, document_public_id: str, page_number: int
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
        # OCR renders the *whole page* via PyMuPDF regardless of whether it
        # contains embedded raster images, so "can we fall back to OCR" is
        # really a question of OCR capability, not this page's image count.
        capabilities = self.documents.capabilities()
        return decide_extraction_method(
            page["raw_text"] or "",
            has_renderable_image=capabilities["ocr_available"],
            min_text_length=self.settings.ocr_min_text_length,
        )


class DocumentPageRevisionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)
        self.documents = DocumentService(settings)

    def save_draft(
        self,
        document_public_id: str,
        page_number: int,
        cleaned_text: str,
        admin_id: str,
        *,
        change_summary: str = "",
        correction_types: list[str] | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            if page["review_status"] == "excluded":
                raise ValidationError(
                    "an excluded page must be reopened before it can be corrected"
                )
        self.documents.edit_page(document_public_id, page_number, cleaned_text, admin_id)
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            was_approved = page["review_status"] == "approved"
            if was_approved:
                self.repository.update_page_review(
                    connection, page["id"], {"review_status": "needs_correction"}
                )
                self.repository.add_review_event(
                    connection,
                    {
                        "document_page_id": page["id"],
                        "action": "request_correction",
                        "review_status_after": "needs_correction",
                        "performed_by_admin_public_id": admin_id,
                        "notes": change_summary
                        or "Edited after approval -- new draft revision created; "
                        "the approved revision is preserved.",
                    },
                )
            # Preserved here (rather than on the append-only, pre-existing
            # `document_page_revisions` row, which this phase does not
            # alter) so correction categories remain auditable per Step 10.
            audit(
                connection,
                "document_page_correction_after_approval"
                if was_approved
                else "document_page_saved",
                admin_id,
                document_public_id,
                page_number=page_number,
                change_summary=change_summary,
                correction_types=correction_types or [],
            )
        return self.documents.page(document_public_id, page_number)

    def restore_revision(
        self, document_public_id: str, page_number: int, revision_number: int, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            revision = connection.execute(
                "SELECT cleaned_text FROM document_page_revisions "
                "WHERE document_page_id=? AND revision_number=?",
                (page["id"], revision_number),
            ).fetchone()
            if not revision:
                raise NotFoundError("document page revision not found")
        result = self.save_draft(
            document_public_id,
            page_number,
            revision["cleaned_text"],
            admin_id,
            change_summary=f"Restored revision {revision_number}",
        )
        with self.repository.transaction() as connection:
            page = self.repository.page(connection, document["id"], page_number)
            self.repository.add_review_event(
                connection,
                {
                    "document_page_id": page["id"],
                    "action": "restore_previous_revision",
                    "review_status_after": page["review_status"],
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"Restored content from revision {revision_number}",
                },
            )
        return result

    def revisions(self, document_public_id: str, page_number: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            rows = connection.execute(
                "SELECT * FROM document_page_revisions WHERE document_page_id=? "
                "ORDER BY revision_number DESC",
                (page["id"],),
            ).fetchall()
        return {
            "items": [dict(row) for row in rows],
            "approved_revision_number": page["approved_revision_number"],
        }


class DocumentPageReviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)
        self.documents = DocumentService(settings)
        self.source_repository = DataSourceRepository(settings.resolved_database_path)

    def _transition(
        self,
        document_public_id: str,
        page_number: int,
        target_status: str,
        action: str,
        admin_id: str,
        notes: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            try:
                validate_transition(page["review_status"], target_status)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            fields: dict[str, Any] = {
                "review_status": target_status,
                "reviewed_by_admin_public_id": admin_id,
                "reviewed_at": now(),
                "review_notes": notes,
            }
            if target_status == "approved":
                latest_revision = connection.execute(
                    "SELECT COALESCE(MAX(revision_number),0) FROM document_page_revisions "
                    "WHERE document_page_id=?",
                    (page["id"],),
                ).fetchone()[0]
                fields["approved_revision_number"] = latest_revision
            self.repository.update_page_review(connection, page["id"], fields)
            self.repository.add_review_event(
                connection,
                {
                    "document_page_id": page["id"],
                    "action": action,
                    "review_status_after": target_status,
                    "performed_by_admin_public_id": admin_id,
                    "notes": notes,
                },
            )
            audit(
                connection,
                f"document_page_{action}",
                admin_id,
                document_public_id,
                page_number=page_number,
                review_status=target_status,
            )
        return self.documents.page(document_public_id, page_number)

    def approve(
        self, document_public_id: str, page_number: int, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            if page["extraction_status"] == "failed":
                raise ValidationError("a page with a failed extraction cannot be approved")
            if not (page["cleaned_text"] or "").strip():
                raise ValidationError(
                    "the page has no corrected or accepted text -- save a draft first"
                )
            links = self.source_repository.links_for_entity(
                connection, "document", document_public_id
            )
            if not links:
                raise ValidationError(
                    "the document has no linked source -- link a source before approving pages"
                )
            has_revision = connection.execute(
                "SELECT 1 FROM document_page_revisions WHERE document_page_id=? LIMIT 1",
                (page["id"],),
            ).fetchone()
        if not has_revision:
            # "Raw extraction explicitly accepted" (Step 19) is given a
            # concrete, addressable form here: a revision snapshot of the
            # current auto-extracted text, so every approved page always
            # has a real revision backing it -- never just an implicit
            # "nothing was ever revised" state with nothing to compare
            # against or restore later.
            self.documents.edit_page(
                document_public_id, page_number, page["cleaned_text"], admin_id
            )
        return self._transition(
            document_public_id, page_number, "approved", "approve", admin_id, notes
        )

    def reject(
        self, document_public_id: str, page_number: int, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        return self._transition(
            document_public_id, page_number, "rejected", "reject", admin_id, notes
        )

    def exclude(
        self, document_public_id: str, page_number: int, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        return self._transition(
            document_public_id, page_number, "excluded", "exclude", admin_id, notes
        )

    def reopen(
        self, document_public_id: str, page_number: int, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        return self._transition(
            document_public_id, page_number, "pending", "reopen", admin_id, notes
        )

    def request_correction(
        self, document_public_id: str, page_number: int, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        return self._transition(
            document_public_id,
            page_number,
            "needs_correction",
            "request_correction",
            admin_id,
            notes,
        )

    def request_ocr_rerun(
        self,
        document_public_id: str,
        page_number: int,
        admin_id: str,
        ocr_language: str | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            if page["review_status"] == "excluded":
                raise ValidationError("an excluded page must be reopened before rerunning OCR")
        workspace_service = PDFResearchWorkspaceService(self.settings)
        request = ProcessRequest(strategy="ocr", pages=[page_number], ocr_language=ocr_language)
        workspace_service.extract_with_history(
            document_public_id, request, admin_id, reprocess=True
        )
        return self._transition(
            document_public_id,
            page_number,
            "pending",
            "request_ocr_rerun",
            admin_id,
            "OCR rerun requested; prior review outcome cleared pending re-review.",
        )

    def request_extraction_rerun(
        self, document_public_id: str, page_number: int, admin_id: str, strategy: str = "auto"
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            if page["review_status"] == "excluded":
                raise ValidationError(
                    "an excluded page must be reopened before rerunning extraction"
                )
        workspace_service = PDFResearchWorkspaceService(self.settings)
        request = ProcessRequest(strategy=strategy, pages=[page_number])
        workspace_service.extract_with_history(
            document_public_id, request, admin_id, reprocess=True
        )
        return self._transition(
            document_public_id,
            page_number,
            "pending",
            "request_extraction_rerun",
            admin_id,
            "Extraction rerun requested; prior review outcome cleared pending re-review.",
        )

    def review_events(self, document_public_id: str, page_number: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            rows = self.repository.list_review_events(connection, page["id"])
        return {"items": [decode(row, REVIEW_EVENT_JSON) for row in rows]}

    def review_summary(self, document_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            rows = connection.execute(
                "SELECT page_number,review_status,extraction_status,confidence_score,"
                "warnings_json FROM document_pages WHERE document_source_id=? ORDER BY page_number",
                (document["id"],),
            ).fetchall()
        counts = {key: 0 for key in _REVIEW_STATUS_COUNT_KEYS}
        for row in rows:
            counts[row["review_status"]] = counts.get(row["review_status"], 0) + 1
        next_unreviewed = next(
            (r["page_number"] for r in rows if r["review_status"] == "pending"), None
        )
        low_confidence_pages = [
            r["page_number"]
            for r in rows
            if r["confidence_score"] is not None
            and r["confidence_score"] < self.settings.ocr_confidence_warning_threshold
        ]
        return {
            "total_pages": len(rows),
            "review_status_counts": counts,
            "next_unreviewed_page": next_unreviewed,
            "next_low_confidence_page": low_confidence_pages[0] if low_confidence_pages else None,
            "low_confidence_pages": low_confidence_pages,
        }


class DocumentCleanupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)
        self.revisions = DocumentPageRevisionService(settings)

    def suggestions(self, document_public_id: str, page_number: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
        text = page["cleaned_text"] or page["raw_text"] or ""
        items = generate_cleanup_suggestions(text)
        return {"items": items[: self.settings.document_cleanup_max_findings_per_page]}

    def apply_suggestions(
        self,
        document_public_id: str,
        page_number: int,
        suggestions: list[dict[str, Any]],
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
        text = page["cleaned_text"] or page["raw_text"] or ""
        applied_types = []
        for suggestion in suggestions:
            original = suggestion.get("original_text", "")
            proposed = suggestion.get("proposed_text", "")
            if original and original in text:
                text = text.replace(original, proposed, 1)
                applied_types.append(suggestion.get("suggestion_type", "other"))
        return self.revisions.save_draft(
            document_public_id,
            page_number,
            text,
            admin_id,
            change_summary=f"Applied {len(applied_types)} cleanup suggestion(s)",
            correction_types=applied_types,
        )

    def detect_repeated_elements(self, document_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            pages = connection.execute(
                "SELECT page_number,COALESCE(cleaned_text,raw_text,'') AS text "
                "FROM document_pages WHERE document_source_id=? ORDER BY page_number",
                (document["id"],),
            ).fetchall()
            found = detect_repeated_elements([(row["page_number"], row["text"]) for row in pages])
            self.repository.clear_repeated_elements(connection, document["id"])
            for item in found:
                self.repository.create_repeated_element(
                    connection,
                    {
                        "document_source_id": document["id"],
                        "normalized_text": item["candidate_text"],
                        "element_type": item["element_type"],
                        "page_occurrences_json": dumps_json(item["pages"]),
                        "confidence": item["confidence"],
                    },
                )
            rows = self.repository.list_repeated_elements(connection, document["id"])
        return {"items": [decode(row, REPEATED_ELEMENT_JSON) for row in rows]}

    def list_repeated_elements(
        self, document_public_id: str, status: str | None = None
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            rows = self.repository.list_repeated_elements(connection, document["id"], status=status)
        return {"items": [decode(row, REPEATED_ELEMENT_JSON) for row in rows]}

    def review_repeated_element(
        self,
        document_public_id: str,
        element_public_id: str,
        action: str,
        admin_id: str,
        *,
        confirm: bool = False,
        target_pages: list[int] | None = None,
    ) -> dict[str, Any]:
        if action not in ("accept", "reject", "apply_selected", "apply_all"):
            raise ValidationError(f"unsupported repeated-element action: {action!r}")
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            element = self.repository.repeated_element(connection, element_public_id)
            if element["document_source_id"] != document["id"]:
                raise NotFoundError("repeated element suggestion not found")

        if action in ("apply_selected", "apply_all"):
            if not confirm:
                raise ValidationError("bulk removal requires explicit confirmation (confirm=true)")
            all_pages = loads_json(element["page_occurrences_json"], default=[])
            pages_to_clean = target_pages if action == "apply_selected" else all_pages
            if action == "apply_selected" and not (set(pages_to_clean) <= set(all_pages)):
                raise ValidationError("selected pages must be a subset of the detected occurrences")
            for page_number in pages_to_clean:
                with self.repository.transaction() as connection:
                    page = self.repository.page(connection, document["id"], page_number)
                    if page["review_status"] == "excluded":
                        continue
                    text = page["cleaned_text"] or page["raw_text"] or ""
                lines = [
                    line
                    for line in text.split("\n")
                    if line.strip().casefold() != element["normalized_text"]
                ]
                new_text = "\n".join(lines)
                if new_text != text:
                    self.revisions.save_draft(
                        document_public_id,
                        page_number,
                        new_text,
                        admin_id,
                        change_summary=f"Removed repeated {element['element_type']}",
                        correction_types=[f"{element['element_type']}_removed"],
                    )
            new_status = "applied"
        elif action == "accept":
            new_status = "accepted"
        else:
            new_status = "rejected"

        with self.repository.transaction() as connection:
            self.repository.update_repeated_element(
                connection,
                element["id"],
                {
                    "status": new_status,
                    "reviewed_by_admin_public_id": admin_id,
                    "reviewed_at": now(),
                },
            )
            audit(
                connection,
                "document_repeated_element_reviewed",
                admin_id,
                document_public_id,
                element_public_id=element_public_id,
                action=action,
            )
            updated = self.repository.repeated_element(connection, element_public_id)
        return decode(updated, REPEATED_ELEMENT_JSON)


__all__ = [
    "DocumentCleanupService",
    "DocumentPageRevisionService",
    "DocumentPageReviewService",
    "PDFResearchWorkspaceService",
]
