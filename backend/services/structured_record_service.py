"""Services for the Phase 5 Structured Record Candidate staging layer.

Bridges reviewed semantic chunks into existing dataset-compatible
record shapes and, ultimately, into `dataset_records` -- reusing
`core_model.manual_data.DATASET_RECORD_TYPE_MAP` and mirroring
`ManualDataCandidateService`'s export-bridge shape exactly (Step 23):
reads+validates in its own transaction, calls
`DatasetService.create_record()` as a separate self-committing call,
then marks the candidate exported in a final transaction. Never writes
to `dataset_records` directly and never builds a second, competing
dataset-record system.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.data_sources import public_row as source_public_row
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.semantic_chunks import SemanticChunkRepository
from backend.database.repositories.structured_records import (
    StructuredRecordRepository,
    public_row,
)
from backend.models.datasets import RecordCreate
from backend.services.dataset_service import DatasetService
from core_model.data_governance.usage_policy import rights_from_source_rights_row
from core_model.manual_data import DATASET_RECORD_TYPE_MAP
from core_model.semantic_chunk import STRUCTURED_RECORD_TYPES
from core_model.semantic_chunk.duplicates import (
    detect_dictionary_conflict,
    detect_qa_conflict,
    detect_translation_conflict,
    structured_record_content_hash,
)
from core_model.semantic_chunk.lifecycle import (
    validate_structured_record_transition as _validate_transition_raw,
)
from core_model.semantic_chunk.usage_policy import evaluate_structured_record_usage

TARGET_USES = ("rag", "training", "evaluation", "commercial", "public_export", "redistribution")


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
            "structured_record_candidate",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


def _next_candidate_code(connection) -> str:
    rows = connection.execute(
        "SELECT candidate_code FROM structured_record_candidates WHERE candidate_code LIKE 'SR-%'"
    ).fetchall()
    max_number = 0
    for row in rows:
        suffix = row[0].removeprefix("SR-")
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return f"SR-{max_number + 1:04d}"


def _content_for_export(record_type: str, revision: dict[str, Any]) -> dict[str, Any]:
    """Mirrors `manual_data_candidate_service._content_for_export`'s
    per-type mapping, adapted to this table's own field names."""
    if record_type in ("plain_text", "language_example", "grammar_example"):
        text = revision.get("text") or revision.get("grammar_rule")
        return {"input_text": text}
    if record_type == "conversation":
        return {"input_text": revision.get("text")}
    if record_type == "question_answer":
        return {"instruction": revision.get("question"), "output_text": revision.get("answer")}
    if record_type == "instruction_response":
        return {"instruction": revision.get("instruction"), "output_text": revision.get("response")}
    if record_type == "translation_pair":
        return {
            "input_text": revision.get("source_text"),
            "output_text": revision.get("target_text"),
        }
    if record_type == "tanglish_normalization":
        return {
            "input_text": revision.get("tanglish_text"),
            "normalized_input": revision.get("normalized_tamil"),
            "output_text": revision.get("english_meaning"),
        }
    if record_type == "dictionary_entry":
        meanings = "; ".join(loads_json(revision.get("meanings_json") or "[]"))
        return {"input_text": revision.get("word"), "output_text": meanings}
    if record_type == "knowledge_note":
        return {"input_text": revision.get("title"), "output_text": revision.get("text")}
    return {}


class StructuredRecordCandidateService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = StructuredRecordRepository(settings.resolved_database_path)
        self.chunks = SemanticChunkRepository(settings.resolved_database_path)
        self.sources = DataSourceRepository(settings.resolved_database_path)

    # --- read access -----------------------------------------------------

    def candidate(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            raw = self.repository.candidate(connection, candidate_public_id)
            row = public_row(raw)
            active_id = raw["active_revision_id"]
            revision = (
                public_row(self.repository.revision_by_id(connection, active_id))
                if active_id
                else None
            )
            chunks = [dict(c) for c in self.repository.list_candidate_chunks(connection, raw["id"])]
        row["active_revision"] = revision
        row["chunks"] = chunks
        return row

    def list_candidates(
        self,
        *,
        status: str | None = None,
        record_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows, total = self.repository.list_candidates(
                connection,
                status=status,
                record_type=record_type,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
            items = [public_row(row) for row in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def history(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate_id = self.repository.candidate(connection, candidate_public_id)["id"]
            revisions = [
                public_row(r) for r in self.repository.list_revisions(connection, candidate_id)
            ]
            reviews = [
                public_row(r) for r in self.repository.list_reviews(connection, candidate_id)
            ]
        return {"revisions": revisions, "reviews": reviews}

    # --- creation from chunks --------------------------------------------

    def create_from_chunks(
        self,
        *,
        record_type: str,
        chunk_public_ids: list[str],
        fields: dict[str, Any],
        admin_id: str,
        requested_uses: list[str] | None = None,
    ) -> dict[str, Any]:
        if record_type not in STRUCTURED_RECORD_TYPES:
            raise ValidationError(f"unsupported structured record type: {record_type}")
        if not chunk_public_ids:
            raise ValidationError("at least one chunk must be selected")
        with self.repository.transaction() as connection:
            chunk_rows = []
            document_source_id = None
            data_source_id = None
            for chunk_public_id in chunk_public_ids:
                chunk = self.chunks.chunk(connection, chunk_public_id)
                if chunk["status"] not in ("approved", "needs_review", "needs_content_review"):
                    raise ValidationError(
                        f"chunk {chunk_public_id} must be reviewed before it can back a "
                        "structured record"
                    )
                if document_source_id is None:
                    document_source_id = chunk["document_source_id"]
                    data_source_id = chunk["data_source_id"]
                elif chunk["document_source_id"] != document_source_id:
                    raise ValidationError("all selected chunks must belong to the same document")
                chunk_rows.append(chunk)

            candidate_public_id = self.repository.create_candidate(
                connection,
                {
                    "candidate_code": _next_candidate_code(connection),
                    "record_type": record_type,
                    "data_source_id": data_source_id,
                    "document_source_id": document_source_id,
                    "primary_chunk_id": chunk_rows[0]["id"],
                    "requested_uses_json": dumps_json(requested_uses or []),
                    "created_by_admin_public_id": admin_id,
                },
            )
            candidate_id = self.repository.candidate(connection, candidate_public_id)["id"]
            for index, chunk in enumerate(chunk_rows):
                self.repository.link_chunk(connection, candidate_id, chunk["id"], sort_order=index)

            content_hash = structured_record_content_hash(record_type, fields)
            revision_public_id = self.repository.create_revision(
                connection,
                {
                    "candidate_id": candidate_id,
                    "revision_number": 1,
                    "content_hash": content_hash,
                    "created_by_admin_public_id": admin_id,
                    **{
                        key: value
                        for key, value in fields.items()
                        if key in self.repository.REVISION_FIELDS
                    },
                },
            )
            revision_id = self.repository.revision(connection, revision_public_id)["id"]
            self.repository.update_candidate(
                connection, candidate_id, {"active_revision_id": revision_id}
            )
            _audit(
                connection,
                "structured_record_candidate_created",
                admin_id,
                candidate_public_id,
                record_type=record_type,
                chunk_count=len(chunk_public_ids),
            )
        return self.candidate(candidate_public_id)

    def revise(
        self,
        candidate_public_id: str,
        *,
        fields: dict[str, Any],
        change_summary: str,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            next_number = self.repository.latest_revision_number(connection, candidate["id"]) + 1
            content_hash = structured_record_content_hash(candidate["record_type"], fields)
            revision_public_id = self.repository.create_revision(
                connection,
                {
                    "candidate_id": candidate["id"],
                    "revision_number": next_number,
                    "content_hash": content_hash,
                    "change_summary": change_summary,
                    "created_by_admin_public_id": admin_id,
                    **{
                        key: value
                        for key, value in fields.items()
                        if key in self.repository.REVISION_FIELDS
                    },
                },
            )
            revision_id = self.repository.revision(connection, revision_public_id)["id"]
            update_fields: dict[str, Any] = {"active_revision_id": revision_id}
            if candidate["status"] == "approved":
                update_fields["status"] = "needs_review"
            self.repository.update_candidate(connection, candidate["id"], update_fields)
            _audit(
                connection,
                "structured_record_candidate_revised",
                admin_id,
                candidate_public_id,
                change_summary=change_summary,
            )
        return self.candidate(candidate_public_id)

    # --- lifecycle ---------------------------------------------------------

    def _transition(
        self, candidate_public_id: str, target_status: str, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            _validate_transition(candidate["status"], target_status)
            update: dict[str, Any] = {"status": target_status}
            if target_status == "archived":
                update["archived_at"] = _now()
            self.repository.update_candidate(connection, candidate["id"], update)
            _audit(
                connection,
                f"structured_record_candidate_{target_status}",
                admin_id,
                candidate_public_id,
            )
        return self.candidate(candidate_public_id)

    def submit_review(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition(candidate_public_id, "needs_review", admin_id)

    def review(
        self, candidate_public_id: str, *, review_status: str, comments: str, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            if not candidate["active_revision_id"]:
                raise ValidationError("candidate has no active revision to review")
            self.repository.create_review(
                connection,
                {
                    "candidate_id": candidate["id"],
                    "revision_id": candidate["active_revision_id"],
                    "review_status": review_status,
                    "comments": comments,
                    "reviewer_admin_public_id": admin_id,
                },
            )
            target = {"approved": "approved", "rejected": "rejected", "changes_requested": "draft"}[
                review_status
            ]
            _validate_transition(candidate["status"], target)
            self.repository.update_candidate(connection, candidate["id"], {"status": target})
            _audit(
                connection,
                "structured_record_candidate_reviewed",
                admin_id,
                candidate_public_id,
                review_status=review_status,
            )
        return self.candidate(candidate_public_id)

    def archive(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition(candidate_public_id, "archived", admin_id)

    # --- usage eligibility --------------------------------------------------

    def usage_check(self, candidate_public_id: str, target_use: str) -> dict[str, Any]:
        if target_use not in TARGET_USES:
            raise ValidationError(f"unsupported target use: {target_use}")
        with self.repository.transaction() as connection:
            candidate = dict(self.repository.candidate(connection, candidate_public_id))
        with self.sources.transaction() as connection:
            source = source_public_row(
                self.sources.source_by_id(connection, candidate["data_source_id"])
            )
            rights_row = self.sources.rights_for_source(connection, candidate["data_source_id"])
        rights = rights_from_source_rights_row(dict(rights_row)) if rights_row else None
        return evaluate_structured_record_usage(
            candidate=candidate, source=source, rights=rights, target_use=target_use
        )

    # --- conflict detection --------------------------------------------------

    def conflict_check(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = dict(self.repository.candidate(connection, candidate_public_id))
            revision = dict(
                self.repository.revision_by_id(connection, candidate["active_revision_id"])
            )
            existing = [
                entry
                for entry in self.repository.list_by_type(connection, candidate["record_type"])
                if entry["public_id"] != candidate_public_id
            ]
        record_type = candidate["record_type"]
        conflict = None
        if record_type == "dictionary_entry":
            conflict = detect_dictionary_conflict(
                revision.get("word") or "",
                loads_json(revision.get("meanings_json") or "[]"),
                [{**e, "meanings": loads_json(e.get("meanings_json") or "[]")} for e in existing],
            )
        elif record_type == "question_answer":
            conflict = detect_qa_conflict(
                revision.get("question") or "", revision.get("answer") or "", existing
            )
        elif record_type == "translation_pair":
            conflict = detect_translation_conflict(
                revision.get("source_text") or "", revision.get("target_text") or "", existing
            )
        exact_duplicate = self._exact_duplicate(
            record_type, revision["content_hash"], candidate_public_id
        )
        return {"conflict": conflict, "exact_duplicate_candidate_public_id": exact_duplicate}

    def _exact_duplicate(
        self, record_type: str, content_hash: str, exclude_public_id: str
    ) -> str | None:
        with self.repository.transaction() as connection:
            match = self.repository.content_hash_exists(connection, record_type, content_hash)
        return match if match and match != exclude_public_id else None

    # --- dataset export ----------------------------------------------------

    def export_to_dataset(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        # Additive Phase 6 preflight guard (Step 20): a lazy import avoids a
        # circular import (`governance_service` itself imports this class
        # to run usage/conflict checks). Only blocks when a governance
        # review item/duplicate/conflict group actually exists and is
        # unresolved for this candidate -- never regresses the common case
        # of a candidate with no governance activity at all.
        from backend.services.governance_service import GovernanceExportReadinessService

        GovernanceExportReadinessService(self.settings).require_allowed(
            "structured_record_candidate", candidate_public_id, "dataset_export"
        )
        with self.repository.transaction() as connection:
            candidate = dict(self.repository.candidate(connection, candidate_public_id))
            if candidate["status"] != "approved":
                raise ValidationError(
                    "only an approved structured record may become a dataset candidate"
                )
            if candidate["exported_dataset_record_public_id"]:
                raise ConflictError(
                    "this candidate was already exported as dataset record "
                    f"{candidate['exported_dataset_record_public_id']}"
                )
            record_type = candidate["record_type"]
            if record_type not in DATASET_RECORD_TYPE_MAP:
                raise ValidationError(
                    f"{record_type!r} candidates cannot be exported to the training dataset "
                    "pipeline -- use the RAG handoff instead"
                )
            if not candidate["active_revision_id"]:
                raise ValidationError("candidate has no active revision to export")
            revision = dict(
                self.repository.revision_by_id(connection, candidate["active_revision_id"])
            )
            source = source_public_row(
                self.sources.source_by_id(connection, candidate["data_source_id"])
            )
        dataset_record_type = DATASET_RECORD_TYPE_MAP[record_type]
        language = revision.get("source_language") or "unknown"
        content = _content_for_export(record_type, revision)
        metadata: dict[str, Any] = {
            "structured_record_candidate_public_id": candidate_public_id,
            "structured_record_candidate_revision_public_id": revision["public_id"],
            "data_source_public_id": source["public_id"],
        }
        dataset_repository = DatasetAdminRepository(self.settings.resolved_database_path)
        dataset_source_public_id = self._find_or_create_dataset_source(dataset_repository, language)
        dataset_service = DatasetService(dataset_repository)
        dataset_record = dataset_service.create_record(
            RecordCreate(
                source_public_id=dataset_source_public_id,
                record_type=dataset_record_type,
                language=language if language != "unknown" else "en",
                metadata=metadata,
                **content,
            ),
            admin_id,
        )
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            self.repository.update_candidate(
                connection,
                candidate["id"],
                {"exported_dataset_record_public_id": dataset_record["public_id"]},
            )
            _audit(
                connection,
                "structured_record_candidate_exported",
                admin_id,
                candidate_public_id,
                dataset_record_public_id=dataset_record["public_id"],
            )
        return self.candidate(candidate_public_id)

    def _find_or_create_dataset_source(
        self, dataset_repository: DatasetAdminRepository, language: str
    ) -> str:
        """`DatasetService.create_record()`/`RecordCreate.source_public_id`
        points at the older `dataset_sources` table (Phase 1), which is a
        distinct table from Phase 2's `data_sources` registry that
        `structured_record_candidates.data_source_id` links to -- exactly
        the same gap `ManualDataCandidateService._find_or_create_manual_source()`
        already bridges for Manual Data Studio. Mirrors that fix: find or
        create one dedicated `dataset_sources` row for this bridge rather
        than trying to reuse the Phase 2 source's own public_id, which
        belongs to a different table entirely."""
        with dataset_repository.transaction() as connection:
            existing = connection.execute(
                "SELECT public_id FROM dataset_sources "
                "WHERE source_type='structured_record_studio' "
                "AND name='Structured Record Studio' LIMIT 1"
            ).fetchone()
            if existing:
                return existing["public_id"]
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO dataset_sources(name,source_type,status,public_id,language,
                licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
                (
                    "Structured Record Studio",
                    "structured_record_studio",
                    "ready",
                    public_id,
                    language if language != "unknown" else "en",
                    "unknown",
                    dumps_json({}),
                ),
            )
            return public_id

    def create_rag_candidate(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        """Explicit RAG handoff (Step 24) -- never automatic indexing.
        Marks the candidate ready; the actual ingestion still runs
        through the existing RAG source/version workflow."""
        from backend.services.governance_service import GovernanceExportReadinessService

        GovernanceExportReadinessService(self.settings).require_allowed(
            "structured_record_candidate", candidate_public_id, "rag_handoff"
        )
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            if candidate["status"] != "approved":
                raise ValidationError("only an approved structured record may be handed off to RAG")
            self.repository.update_candidate(
                connection, candidate["id"], {"rag_handoff_at": _now()}
            )
            _audit(
                connection, "structured_record_candidate_rag_handoff", admin_id, candidate_public_id
            )
        return self.candidate(candidate_public_id)
