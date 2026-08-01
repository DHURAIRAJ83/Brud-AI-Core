"""Services for the Phase 5 Semantic Chunk Studio.

Enhances the existing segmentation/candidate pipeline
(`backend/services/document_service.py`'s `segment()`/`document_candidates`)
with chunk-level typing, hierarchy, and fine-grained provenance -- it
does not replace or duplicate that pipeline. Every mutation runs inside
the repository's transaction and appends both a general `audit_logs`
row and a domain-specific `semantic_chunk_events` row, mirroring
`manual_data_service.py`'s convention exactly.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.documents import DocumentRepository
from backend.database.repositories.semantic_chunks import SemanticChunkRepository, public_row
from core_model.semantic_chunk.classification import suggest_chunk_type
from core_model.semantic_chunk.coverage import (
    plan_boundary_move,
    plan_merge,
    plan_split,
    validate_page_coverage,
)
from core_model.semantic_chunk.duplicates import (
    chunk_content_hash,
    find_exact_chunk_duplicate,
    find_locator_duplicate,
)
from core_model.semantic_chunk.hierarchy import would_create_cycle
from core_model.semantic_chunk.lifecycle import (
    validate_chunk_transition as _validate_transition_raw,
)
from core_model.semantic_chunk.quality import assess_chunk_quality


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_transition(current_status: str, target_status: str) -> None:
    try:
        _validate_transition_raw(current_status, target_status)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def _audit(connection, event: str, admin_id: str, resource_id: str, **metadata: Any) -> None:
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
            "semantic_chunk",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


def _record_event(
    repository: SemanticChunkRepository,
    connection,
    chunk_id: int,
    event_type: str,
    admin_id: str,
    notes: str = "",
    **metadata: Any,
) -> None:
    repository.add_event(
        connection,
        {
            "chunk_id": chunk_id,
            "event_type": event_type,
            "performed_by_admin_public_id": admin_id,
            "notes": notes,
            "metadata_json": dumps_json(metadata),
        },
    )


def _next_chunk_code(connection) -> str:
    rows = connection.execute(
        "SELECT chunk_code FROM semantic_chunks WHERE chunk_code LIKE 'CHK-%'"
    ).fetchall()
    max_number = 0
    for row in rows:
        suffix = row[0].removeprefix("CHK-")
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return f"CHK-{max_number + 1:05d}"


def normalize_chunk_text(text: str) -> str:
    import unicodedata

    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


class SemanticChunkService:
    """Generation, editing (split/merge/boundary/classify/hierarchy), and
    read access for semantic chunks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = SemanticChunkRepository(settings.resolved_database_path)
        self.documents = DocumentRepository(settings.resolved_database_path)
        self.sources = DataSourceRepository(settings.resolved_database_path)

    # --- eligibility & generation ----------------------------------------

    def _linked_source(self, connection, document_public_id: str) -> dict[str, Any] | None:
        links = self.sources.links_for_entity(connection, "document", document_public_id)
        if not links:
            return None
        return dict(self.sources.source_by_id(connection, links[0]["data_source_id"]))

    def _approved_pages(self, connection, document_id: int) -> tuple[list[dict], int]:
        rows = connection.execute(
            """SELECT * FROM document_pages WHERE document_source_id=? ORDER BY page_number""",
            (document_id,),
        ).fetchall()
        approved = [
            dict(row)
            for row in rows
            if row["review_status"] == "approved"
            and row["approved_revision_number"] is not None
            and row["extraction_status"] != "failed"
        ]
        excluded_count = len(rows) - len(approved)
        return approved, excluded_count

    def _page_source_text(self, connection, page: dict[str, Any]) -> tuple[str, int | None]:
        """Returns (text, page_revision_id) for the page's approved
        revision -- never the page's possibly-since-edited live text."""
        revision_row = connection.execute(
            "SELECT id, cleaned_text FROM document_page_revisions "
            "WHERE document_page_id=? AND revision_number=?",
            (page["id"], page["approved_revision_number"]),
        ).fetchone()
        if revision_row:
            return revision_row["cleaned_text"] or "", revision_row["id"]
        return page["cleaned_text"] or "", None

    def _latest_extraction_id(self, connection, page_id: int) -> int | None:
        row = connection.execute(
            "SELECT id FROM document_page_extractions WHERE document_page_id=? "
            "ORDER BY id DESC LIMIT 1",
            (page_id,),
        ).fetchone()
        return row["id"] if row else None

    def generate(self, document_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.documents.document(connection, document_public_id)
            source = self._linked_source(connection, document_public_id)
            if source is None:
                raise ValidationError(
                    "this document has no linked source -- link a source before generating chunks"
                )
            pages, excluded_count = self._approved_pages(connection, document["id"])
            if not pages:
                raise ValidationError(
                    "no approved pages are available for chunk generation -- "
                    "approve at least one page first"
                )
            reading_order = connection.execute(
                "SELECT COALESCE(MAX(reading_order), 0) FROM semantic_chunks "
                "WHERE document_source_id=?",
                (document["id"],),
            ).fetchone()[0]
            created: list[str] = []
            for page in pages:
                text, page_revision_id = self._page_source_text(connection, page)
                extraction_id = self._latest_extraction_id(connection, page["id"])
                cursor = 0
                for paragraph in re.split(r"\n\s*\n", text):
                    start = text.find(paragraph, cursor)
                    if start == -1 or not paragraph.strip():
                        continue
                    end = start + len(paragraph)
                    cursor = end
                    reading_order += 1
                    chunk_code = _next_chunk_code(connection)
                    chunk_public_id = self.repository.create_chunk(
                        connection,
                        {
                            "chunk_code": chunk_code,
                            "document_source_id": document["id"],
                            "data_source_id": source["id"],
                            "chunk_type": "paragraph",
                            "reading_order": reading_order,
                            "language": document["detected_language"],
                            "created_by_admin_public_id": admin_id,
                        },
                    )
                    chunk_id = self.repository.chunk(connection, chunk_public_id)["id"]
                    normalized = normalize_chunk_text(paragraph)
                    revision_public_id = self.repository.create_revision(
                        connection,
                        {
                            "chunk_id": chunk_id,
                            "revision_number": 1,
                            "text": paragraph,
                            "normalized_text": normalized,
                            "content_hash": chunk_content_hash(
                                normalized, document["detected_language"]
                            ),
                            "document_page_id": page["id"],
                            "page_number": page["page_number"],
                            "extraction_id": extraction_id,
                            "page_revision_id": page_revision_id,
                            "start_locator_json": dumps_json(
                                {"page": page["page_number"], "offset": start}
                            ),
                            "end_locator_json": dumps_json(
                                {"page": page["page_number"], "offset": end}
                            ),
                            "generation_method": "paragraph_boundary",
                            "created_by_admin_public_id": admin_id,
                        },
                    )
                    revision_id = self.repository.revision(connection, revision_public_id)["id"]
                    self.repository.update_chunk(
                        connection, chunk_id, {"active_revision_id": revision_id}
                    )
                    _record_event(
                        self.repository,
                        connection,
                        chunk_id,
                        "chunk_generated",
                        admin_id,
                        page_number=page["page_number"],
                    )
                    created.append(chunk_public_id)
            _audit(
                connection,
                "semantic_chunks_generated",
                admin_id,
                document_public_id,
                chunk_count=len(created),
                partial_document=bool(excluded_count),
                excluded_page_count=excluded_count,
            )
        return {
            "generated_chunk_count": len(created),
            "chunk_public_ids": created,
            "partial_document": bool(excluded_count),
            "excluded_page_count": excluded_count,
        }

    # --- read access -------------------------------------------------------

    def chunk(self, chunk_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            raw = self.repository.chunk(connection, chunk_public_id)
            row = public_row(raw)
            active_id = raw["active_revision_id"]
            revision = (
                public_row(self.repository.revision_by_id(connection, active_id))
                if active_id
                else None
            )
        row["active_revision"] = revision
        return row

    def list_chunks(
        self,
        document_public_id: str,
        *,
        status: str | None = None,
        chunk_type: str | None = None,
        parent_chunk_public_id: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.documents.document(connection, document_public_id)
            parent_id = None
            if parent_chunk_public_id:
                parent_id = self.repository.chunk(connection, parent_chunk_public_id)["id"]
            rows, total = self.repository.list_chunks(
                connection,
                document_source_id=document["id"],
                status=status,
                chunk_type=chunk_type,
                parent_chunk_id=parent_id,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
            items = []
            for row in rows:
                item = public_row(row)
                active_id = row["active_revision_id"]
                item["active_revision"] = (
                    public_row(self.repository.revision_by_id(connection, active_id))
                    if active_id
                    else None
                )
                items.append(item)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def history(self, chunk_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk_id = self.repository.chunk(connection, chunk_public_id)["id"]
            revisions = [
                public_row(r) for r in self.repository.list_revisions(connection, chunk_id)
            ]
            events = [public_row(e) for e in self.repository.list_events(connection, chunk_id)]
            reviews = [public_row(r) for r in self.repository.list_reviews(connection, chunk_id)]
        return {"revisions": revisions, "events": events, "reviews": reviews}

    # --- manual chunk creation ---------------------------------------------

    def create_manual_chunk(
        self,
        document_public_id: str,
        *,
        text: str,
        chunk_type: str,
        page_number: int,
        language: str,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.documents.document(connection, document_public_id)
            source = self._linked_source(connection, document_public_id)
            if source is None:
                raise ValidationError(
                    "this document has no linked source -- link a source before creating chunks"
                )
            page = self.documents.page(connection, document["id"], page_number)
            if page["review_status"] != "approved":
                raise ValidationError("a manual chunk can only be created against an approved page")
            reading_order = connection.execute(
                "SELECT COALESCE(MAX(reading_order), 0) FROM semantic_chunks "
                "WHERE document_source_id=?",
                (document["id"],),
            ).fetchone()[0]
            chunk_public_id = self.repository.create_chunk(
                connection,
                {
                    "chunk_code": _next_chunk_code(connection),
                    "document_source_id": document["id"],
                    "data_source_id": source["id"],
                    "chunk_type": chunk_type,
                    "reading_order": reading_order + 1,
                    "language": language,
                    "created_by_admin_public_id": admin_id,
                },
            )
            chunk_id = self.repository.chunk(connection, chunk_public_id)["id"]
            normalized = normalize_chunk_text(text)
            revision_public_id = self.repository.create_revision(
                connection,
                {
                    "chunk_id": chunk_id,
                    "revision_number": 1,
                    "text": text,
                    "normalized_text": normalized,
                    "content_hash": chunk_content_hash(normalized, language),
                    "document_page_id": page["id"],
                    "page_number": page_number,
                    "page_revision_id": page["approved_revision_number"],
                    "generation_method": "manual",
                    "created_by_admin_public_id": admin_id,
                },
            )
            revision_id = self.repository.revision(connection, revision_public_id)["id"]
            self.repository.update_chunk(connection, chunk_id, {"active_revision_id": revision_id})
            _record_event(self.repository, connection, chunk_id, "chunk_created_manually", admin_id)
            _audit(connection, "semantic_chunk_created", admin_id, chunk_public_id)
        return self.chunk(chunk_public_id)

    # --- classification -------------------------------------------------

    def classify(
        self, chunk_public_id: str, admin_id: str, *, chunk_type: str, notes: str = ""
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = self.repository.chunk(connection, chunk_public_id)
            self.repository.update_chunk(connection, chunk["id"], {"chunk_type": chunk_type})
            _record_event(
                self.repository,
                connection,
                chunk["id"],
                "chunk_classified",
                admin_id,
                notes,
                chunk_type=chunk_type,
            )
            _audit(
                connection,
                "semantic_chunk_classified",
                admin_id,
                chunk_public_id,
                chunk_type=chunk_type,
            )
        return self.chunk(chunk_public_id)

    def classification_suggestions(self, chunk_public_id: str) -> list[dict[str, Any]]:
        chunk = self.chunk(chunk_public_id)
        revision = chunk.get("active_revision") or {}
        text = revision.get("text", "")
        with self.repository.transaction() as connection:
            document_id = self.repository.chunk(connection, chunk_public_id)["document_source_id"]
            siblings, _ = self.repository.list_chunks(
                connection, document_source_id=document_id, limit=1000
            )
        next_text = ""
        reading_order = chunk.get("reading_order", 0)
        for sibling in siblings:
            if sibling["reading_order"] == reading_order + 1:
                sibling_id = sibling["active_revision_id"]
                if sibling_id:
                    with self.repository.transaction() as connection:
                        next_text = self.repository.revision_by_id(connection, sibling_id)["text"]
                break
        return suggest_chunk_type(text, next_text=next_text)

    # --- hierarchy -------------------------------------------------------

    def assign_parent(
        self, chunk_public_id: str, parent_chunk_public_id: str | None, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = self.repository.chunk(connection, chunk_public_id)
            new_parent_id = None
            if parent_chunk_public_id:
                new_parent_id = self.repository.chunk(connection, parent_chunk_public_id)["id"]
                if new_parent_id == chunk["id"]:
                    raise ValidationError("a chunk cannot be its own parent")
                if (
                    self.repository.chunk_by_id(connection, new_parent_id)["document_source_id"]
                    != chunk["document_source_id"]
                ):
                    raise ValidationError("a chunk's parent must belong to the same document")
            if would_create_cycle(
                chunk["id"],
                new_parent_id,
                parent_of=lambda cid: self.repository.parent_id_of(connection, cid),
            ):
                raise ValidationError("this parent assignment would create a hierarchy cycle")
            self.repository.update_chunk(
                connection, chunk["id"], {"parent_chunk_id": new_parent_id}
            )
            _record_event(
                self.repository,
                connection,
                chunk["id"],
                "chunk_parent_assigned",
                admin_id,
                parent_chunk_public_id=parent_chunk_public_id,
            )
            _audit(
                connection,
                "semantic_chunk_parent_assigned",
                admin_id,
                chunk_public_id,
                parent_chunk_public_id=parent_chunk_public_id,
            )
        return self.chunk(chunk_public_id)

    def reorder(
        self, document_public_id: str, ordering: list[str], admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.documents.document(connection, document_public_id)
            for index, chunk_public_id in enumerate(ordering, 1):
                chunk = self.repository.chunk(connection, chunk_public_id)
                if chunk["document_source_id"] != document["id"]:
                    raise ValidationError("all reordered chunks must belong to the same document")
                self.repository.update_chunk(connection, chunk["id"], {"reading_order": index})
            _audit(connection, "semantic_chunks_reordered", admin_id, document_public_id)
        return {"reordered": len(ordering)}

    # --- text correction (no boundary change) ------------------------------

    def edit_text(
        self, chunk_public_id: str, new_text: str, admin_id: str, *, change_summary: str = ""
    ) -> dict[str, Any]:
        """Corrects a chunk's own wording without moving its boundaries --
        the general content-correction pathway. Always permitted,
        including against an approved chunk, which reopens it to
        `needs_review` (Step 3's correction pathway) exactly like Phase 3/4's
        `approved -> draft`/`approved -> needs_correction`. Structural
        split/merge/boundary-move remain blocked on an approved chunk until
        an explicit correction request, since those touch shared boundaries
        with neighboring chunks -- a pure text edit does not."""
        with self.repository.transaction() as connection:
            chunk = self.repository.chunk(connection, chunk_public_id)
            revision = self.repository.revision_by_id(connection, chunk["active_revision_id"])
            self._append_revision(
                connection,
                chunk_id=chunk["id"],
                text=new_text,
                offset_start=loads_json(revision["start_locator_json"]).get("offset", 0),
                offset_end=loads_json(revision["end_locator_json"]).get("offset", len(new_text)),
                page=dict(revision),
                admin_id=admin_id,
                generation_method="manual",
                change_summary=change_summary or "text correction",
            )
            _audit(connection, "semantic_chunk_text_edited", admin_id, chunk_public_id)
        return self.chunk(chunk_public_id)

    # --- boundary editing --------------------------------------------------

    def split(self, chunk_public_id: str, split_at: int, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = self.repository.chunk(connection, chunk_public_id)
            if chunk["status"] == "approved":
                raise ValidationError(
                    "an approved chunk cannot be split directly -- request a correction first"
                )
            revision = self.repository.revision_by_id(connection, chunk["active_revision_id"])
            start_locator = loads_json(revision["start_locator_json"])
            end_locator = loads_json(revision["end_locator_json"])
            offset_start = start_locator.get("offset")
            offset_end = end_locator.get("offset")
            if offset_start is None or offset_end is None:
                raise ValidationError(
                    "this chunk has no character-offset locator -- split is unavailable"
                )
            plan = plan_split(revision["text"], offset_start, offset_end, split_at)
            page = dict(revision)
            new_public_ids = []
            for index, part in enumerate((plan["first"], plan["second"]), 1):
                if index == 1:
                    self._append_revision(
                        connection,
                        chunk_id=chunk["id"],
                        text=part["text"],
                        offset_start=part["offset_start"],
                        offset_end=part["offset_end"],
                        page=page,
                        admin_id=admin_id,
                        generation_method="manual",
                        change_summary="split (first half)",
                    )
                    new_public_ids.append(chunk_public_id)
                else:
                    new_chunk_public_id = self.repository.create_chunk(
                        connection,
                        {
                            "chunk_code": _next_chunk_code(connection),
                            "document_source_id": chunk["document_source_id"],
                            "data_source_id": chunk["data_source_id"],
                            "chunk_type": chunk["chunk_type"],
                            "reading_order": chunk["reading_order"],
                            "language": chunk["language"],
                            "parent_chunk_id": chunk["parent_chunk_id"],
                            "created_by_admin_public_id": admin_id,
                        },
                    )
                    new_chunk_id = self.repository.chunk(connection, new_chunk_public_id)["id"]
                    self._append_revision(
                        connection,
                        chunk_id=new_chunk_id,
                        text=part["text"],
                        offset_start=part["offset_start"],
                        offset_end=part["offset_end"],
                        page=page,
                        admin_id=admin_id,
                        generation_method="manual",
                        change_summary="split (second half)",
                    )
                    new_public_ids.append(new_chunk_public_id)
            _audit(
                connection,
                "semantic_chunk_split",
                admin_id,
                chunk_public_id,
                new_chunk_public_ids=new_public_ids,
            )
        return {"chunks": [self.chunk(cid) for cid in new_public_ids]}

    def _append_revision(
        self,
        connection,
        *,
        chunk_id: int,
        text: str,
        offset_start: int,
        offset_end: int,
        page: dict[str, Any],
        admin_id: str,
        generation_method: str,
        change_summary: str,
        warnings: list[str] | None = None,
    ) -> str:
        chunk = self.repository.chunk_by_id(connection, chunk_id)
        next_number = self.repository.latest_revision_number(connection, chunk_id) + 1
        normalized = normalize_chunk_text(text)
        revision_public_id = self.repository.create_revision(
            connection,
            {
                "chunk_id": chunk_id,
                "revision_number": next_number,
                "text": text,
                "normalized_text": normalized,
                "content_hash": chunk_content_hash(normalized, chunk["language"]),
                "document_page_id": page.get("document_page_id"),
                "page_number": page.get("page_number"),
                "extraction_id": page.get("extraction_id"),
                "page_revision_id": page.get("page_revision_id"),
                "start_locator_json": dumps_json(
                    {"page": page.get("page_number"), "offset": offset_start}
                ),
                "end_locator_json": dumps_json(
                    {"page": page.get("page_number"), "offset": offset_end}
                ),
                "generation_method": generation_method,
                "warnings_json": dumps_json(warnings or []),
                "change_summary": change_summary,
                "created_by_admin_public_id": admin_id,
            },
        )
        revision_id = self.repository.revision(connection, revision_public_id)["id"]
        self.repository.update_chunk(connection, chunk_id, {"active_revision_id": revision_id})
        if chunk["status"] == "approved":
            self.repository.update_chunk(connection, chunk_id, {"status": "needs_review"})
            _record_event(
                self.repository,
                connection,
                chunk_id,
                "chunk_reopened_for_correction",
                admin_id,
            )
        _record_event(
            self.repository,
            connection,
            chunk_id,
            "chunk_revised",
            admin_id,
            change_summary=change_summary,
        )
        return revision_public_id

    def merge(
        self, chunk_public_id: str, other_chunk_public_id: str, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            first_chunk = self.repository.chunk(connection, chunk_public_id)
            second_chunk = self.repository.chunk(connection, other_chunk_public_id)
            if first_chunk["document_source_id"] != second_chunk["document_source_id"]:
                raise ValidationError("chunks from different documents cannot be merged")
            if first_chunk["status"] == "approved" or second_chunk["status"] == "approved":
                raise ValidationError(
                    "an approved chunk cannot be merged directly -- request a correction first"
                )
            first_revision = self.repository.revision_by_id(
                connection, first_chunk["active_revision_id"]
            )
            second_revision = self.repository.revision_by_id(
                connection, second_chunk["active_revision_id"]
            )
            first_start = loads_json(first_revision["start_locator_json"])
            first_end = loads_json(first_revision["end_locator_json"])
            second_start = loads_json(second_revision["start_locator_json"])
            second_end = loads_json(second_revision["end_locator_json"])
            full_text = None
            if first_revision["page_revision_id"] == second_revision["page_revision_id"]:
                page_row = connection.execute(
                    "SELECT cleaned_text FROM document_page_revisions WHERE id=?",
                    (first_revision["page_revision_id"],),
                ).fetchone()
                full_text = page_row["cleaned_text"] if page_row else None
            plan = plan_merge(
                {
                    "page": first_revision["page_number"],
                    "offset_start": first_start.get("offset"),
                    "offset_end": first_end.get("offset"),
                    "text": first_revision["text"],
                },
                {
                    "page": second_revision["page_number"],
                    "offset_start": second_start.get("offset"),
                    "offset_end": second_end.get("offset"),
                    "text": second_revision["text"],
                },
                full_text=full_text,
            )
            self._append_revision(
                connection,
                chunk_id=first_chunk["id"],
                text=plan["text"],
                offset_start=plan["start_offset"],
                offset_end=plan["end_offset"],
                page=dict(first_revision),
                admin_id=admin_id,
                generation_method="manual",
                change_summary="merged with adjacent chunk",
                warnings=plan["warnings"],
            )
            self.repository.update_chunk(connection, second_chunk["id"], {"status": "excluded"})
            _record_event(
                self.repository,
                connection,
                second_chunk["id"],
                "chunk_merged_into_other",
                admin_id,
                merged_into_chunk_public_id=chunk_public_id,
            )
            _audit(
                connection,
                "semantic_chunks_merged",
                admin_id,
                chunk_public_id,
                merged_chunk_public_id=other_chunk_public_id,
                warnings=plan["warnings"],
            )
        return self.chunk(chunk_public_id)

    def move_boundary(
        self,
        chunk_public_id: str,
        neighbor_public_id: str,
        *,
        edge: str,
        new_offset: int,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = self.repository.chunk(connection, chunk_public_id)
            neighbor = self.repository.chunk(connection, neighbor_public_id)
            if chunk["status"] == "approved" or neighbor["status"] == "approved":
                raise ValidationError(
                    "an approved chunk cannot have its boundary moved directly -- "
                    "request a correction first"
                )
            chunk_revision = self.repository.revision_by_id(connection, chunk["active_revision_id"])
            neighbor_revision = self.repository.revision_by_id(
                connection, neighbor["active_revision_id"]
            )
            page_revision_id = chunk_revision["page_revision_id"]
            page_row = connection.execute(
                "SELECT cleaned_text FROM document_page_revisions WHERE id=?", (page_revision_id,)
            ).fetchone()
            if not page_row:
                raise ValidationError("this chunk's source page revision is unavailable")
            full_text = page_row["cleaned_text"] or ""
            chunk_start = loads_json(chunk_revision["start_locator_json"])
            chunk_end = loads_json(chunk_revision["end_locator_json"])
            neighbor_start = loads_json(neighbor_revision["start_locator_json"])
            neighbor_end = loads_json(neighbor_revision["end_locator_json"])
            plan = plan_boundary_move(
                {"offset_start": chunk_start.get("offset"), "offset_end": chunk_end.get("offset")},
                {
                    "offset_start": neighbor_start.get("offset"),
                    "offset_end": neighbor_end.get("offset"),
                },
                edge=edge,
                new_offset=new_offset,
                full_text=full_text,
            )
            page_meta = dict(chunk_revision)
            self._append_revision(
                connection,
                chunk_id=chunk["id"],
                text=plan["chunk"]["text"],
                offset_start=plan["chunk"]["offset_start"],
                offset_end=plan["chunk"]["offset_end"],
                page=page_meta,
                admin_id=admin_id,
                generation_method="manual",
                change_summary=f"boundary move ({edge})",
            )
            neighbor_meta = dict(neighbor_revision)
            self._append_revision(
                connection,
                chunk_id=neighbor["id"],
                text=plan["neighbor"]["text"],
                offset_start=plan["neighbor"]["offset_start"],
                offset_end=plan["neighbor"]["offset_end"],
                page=neighbor_meta,
                admin_id=admin_id,
                generation_method="manual",
                change_summary=f"boundary move ({edge}, neighbor)",
            )
            _audit(
                connection,
                "semantic_chunk_boundary_moved",
                admin_id,
                chunk_public_id,
                neighbor_chunk_public_id=neighbor_public_id,
                edge=edge,
            )
        return self.chunk(chunk_public_id)

    def archive(self, chunk_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = self.repository.chunk(connection, chunk_public_id)
            _validate_transition(chunk["status"], "archived")
            self.repository.update_chunk(
                connection, chunk["id"], {"status": "archived", "archived_at": _now()}
            )
            _record_event(self.repository, connection, chunk["id"], "chunk_archived", admin_id)
            _audit(connection, "semantic_chunk_archived", admin_id, chunk_public_id)
        return self.chunk(chunk_public_id)

    def restore(self, chunk_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = self.repository.chunk(connection, chunk_public_id)
            _validate_transition(chunk["status"], "draft")
            self.repository.update_chunk(
                connection, chunk["id"], {"status": "draft", "archived_at": None}
            )
            _record_event(self.repository, connection, chunk["id"], "chunk_restored", admin_id)
            _audit(connection, "semantic_chunk_restored", admin_id, chunk_public_id)
        return self.chunk(chunk_public_id)


class SemanticChunkReviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = SemanticChunkRepository(settings.resolved_database_path)

    def _transition(
        self, chunk_public_id: str, target_status: str, action: str, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = self.repository.chunk(connection, chunk_public_id)
            _validate_transition(chunk["status"], target_status)
            self.repository.update_chunk(connection, chunk["id"], {"status": target_status})
            # "submitted_for_review" advances status without recording a
            # reviewer *decision* -- `semantic_chunk_reviews.action`'s CHECK
            # constraint intentionally only accepts genuine review verdicts
            # (approve/reject/exclude/request_*/archive/reopen), matching
            # Step 19's action list. Submitting is only ever a status
            # advance, captured in the event log below instead.
            if action != "submitted_for_review":
                self.repository.create_review(
                    connection,
                    {
                        "chunk_id": chunk["id"],
                        "action": action,
                        "status_after": target_status,
                        "notes": notes,
                        "performed_by_admin_public_id": admin_id,
                    },
                )
            _record_event(
                self.repository,
                connection,
                chunk["id"],
                f"chunk_{action}",
                admin_id,
                notes,
                status_after=target_status,
            )
            _audit(connection, f"semantic_chunk_{action}", admin_id, chunk_public_id, notes=notes)
        with self.repository.transaction() as connection:
            return public_row(self.repository.chunk(connection, chunk_public_id))

    def submit_review(self, chunk_public_id: str, admin_id: str, notes: str = "") -> dict[str, Any]:
        return self._transition(
            chunk_public_id, "needs_review", "submitted_for_review", admin_id, notes
        )

    def approve(self, chunk_public_id: str, admin_id: str, notes: str = "") -> dict[str, Any]:
        return self._transition(chunk_public_id, "approved", "approve", admin_id, notes)

    def request_boundary_correction(
        self, chunk_public_id: str, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        return self._transition(
            chunk_public_id,
            "needs_structure_review",
            "request_boundary_correction",
            admin_id,
            notes,
        )

    def request_classification_correction(
        self, chunk_public_id: str, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        return self._transition(
            chunk_public_id,
            "needs_content_review",
            "request_classification_correction",
            admin_id,
            notes,
        )

    def reject(self, chunk_public_id: str, admin_id: str, notes: str = "") -> dict[str, Any]:
        return self._transition(chunk_public_id, "rejected", "reject", admin_id, notes)

    def exclude(self, chunk_public_id: str, admin_id: str, notes: str = "") -> dict[str, Any]:
        return self._transition(chunk_public_id, "excluded", "exclude", admin_id, notes)

    def reopen(self, chunk_public_id: str, admin_id: str, notes: str = "") -> dict[str, Any]:
        return self._transition(chunk_public_id, "draft", "reopen", admin_id, notes)

    def review_history(self, chunk_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk_id = self.repository.chunk(connection, chunk_public_id)["id"]
            return {
                "items": [public_row(r) for r in self.repository.list_reviews(connection, chunk_id)]
            }


class SemanticChunkQualityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = SemanticChunkRepository(settings.resolved_database_path)
        self.documents = DocumentRepository(settings.resolved_database_path)

    def assess(self, chunk_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = dict(self.repository.chunk(connection, chunk_public_id))
            if not chunk["active_revision_id"]:
                raise ValidationError("chunk has no active revision to assess")
            revision = dict(self.repository.revision_by_id(connection, chunk["active_revision_id"]))
            page_approved = True
            if revision.get("document_page_id"):
                page_row = connection.execute(
                    "SELECT review_status FROM document_pages WHERE id=?",
                    (revision["document_page_id"],),
                ).fetchone()
                page_approved = bool(page_row and page_row["review_status"] == "approved")
            hashes = self.repository.content_hashes_for_document(
                connection, chunk["document_source_id"]
            )
            duplicate_status = "unique"
            for other_public_id, other_hash in hashes.items():
                if other_public_id != chunk_public_id and other_hash == revision["content_hash"]:
                    duplicate_status = "exact_duplicate"
                    break
            locators = self.repository.locators_for_document(
                connection, chunk["document_source_id"]
            )
            page_locators = [
                loc for loc in locators if loc["page_number"] == revision.get("page_number")
            ]
            coverage = validate_page_coverage((revision.get("text") or ""), page_locators)
        result = assess_chunk_quality(
            chunk=chunk,
            revision=revision,
            page_approved=page_approved,
            coverage_issue_codes=[i["code"] for i in coverage["issues"]],
            duplicate_status=duplicate_status,
        )
        return {**result, "coverage": coverage}

    def duplicate_check(self, chunk_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk = dict(self.repository.chunk(connection, chunk_public_id))
            revision = dict(self.repository.revision_by_id(connection, chunk["active_revision_id"]))
            hashes = self.repository.content_hashes_for_document(
                connection, chunk["document_source_id"]
            )
            exact = find_exact_chunk_duplicate(
                revision["content_hash"],
                {k: v for k, v in hashes.items() if k != chunk_public_id},
            )
            locators = self.repository.locators_for_document(
                connection, chunk["document_source_id"]
            )
            start_locator = loads_json(revision["start_locator_json"])
            end_locator = loads_json(revision["end_locator_json"])
            locator_duplicate = find_locator_duplicate(
                {
                    "page_number": revision.get("page_number"),
                    "offset_start": start_locator.get("offset"),
                    "offset_end": end_locator.get("offset"),
                },
                [loc for loc in locators if loc["public_id"] != chunk_public_id],
            )
        return {
            "exact_duplicate_chunk_public_id": exact,
            "locator_duplicate_chunk_public_id": locator_duplicate,
        }


class ChunkConflictService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = SemanticChunkRepository(settings.resolved_database_path)
        self.documents = DocumentRepository(settings.resolved_database_path)

    def coverage_report(self, document_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.documents.document(connection, document_public_id)
            locators = self.repository.locators_for_document(connection, document["id"])
        by_page: dict[int, list[dict[str, Any]]] = {}
        for locator in locators:
            by_page.setdefault(locator["page_number"], []).append(locator)
        report = {}
        with self.repository.transaction() as connection:
            for page_number, segments in by_page.items():
                page = self.documents.page(connection, document["id"], page_number)
                text = page["cleaned_text"] or ""
                report[str(page_number)] = validate_page_coverage(text, segments)
        return report
