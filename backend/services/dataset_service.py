"""Business rules for authenticated manual dataset administration."""

import hashlib
import math
import re
import unicodedata
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository, public_row
from backend.models.datasets import ManualSourceCreate, Page, RecordCreate, RecordPatch, SourcePatch
from backend.models.domain import ReviewDecision

TRANSITIONS = {
    "draft": {"pending_review", "archived"},
    "pending_review": {"approved", "rejected", "draft", "archived"},
    "approved": {"archived"},
    "rejected": {"draft", "archived"},
    "archived": {"draft"},
}


def _audit(connection, event: str, admin_id: str, resource_id: str, **metadata) -> None:
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
            "dataset",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


def normalize_text(value: str | None, *, fold_case: bool = False) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold() if fold_case else normalized


def content_hash(values: dict[str, Any]) -> str:
    language = values["language"]
    fold = language in {"en", "tgl"}
    logical = {
        "record_type": values["record_type"],
        "language": language,
        "instruction": normalize_text(values.get("instruction"), fold_case=fold),
        "input_text": normalize_text(values.get("input_text"), fold_case=fold),
        "output_text": normalize_text(values.get("output_text"), fold_case=fold),
        "normalized_input": normalize_text(values.get("normalized_input"), fold_case=fold),
    }
    return hashlib.sha256(dumps_json(logical).encode()).hexdigest()


def validate_record(values: dict[str, Any]) -> None:
    kind = values["record_type"]
    required = {
        "instruction": ("instruction", "output_text"),
        "chat": ("input_text", "output_text"),
        "translation": ("input_text", "output_text"),
        "tanglish_pair": ("input_text", "normalized_input", "output_text"),
        "safety": ("input_text", "output_text"),
        "preference": ("input_text", "output_text"),
    }
    if kind == "pretrain":
        if not (values.get("input_text") or values.get("output_text")):
            raise ValidationError("pretrain records require input_text or output_text")
    elif any(not values.get(field) for field in required[kind]):
        raise ValidationError(f"{kind} record is missing required fields")
    if kind == "translation":
        metadata = values.get("metadata", {})
        if not metadata.get("source_language") or not metadata.get("target_language"):
            raise ValidationError(
                "translation metadata requires source_language and target_language"
            )


class DatasetService:
    def __init__(self, repository: DatasetAdminRepository) -> None:
        self.repository = repository

    @staticmethod
    def page(items, total: int, page: int, page_size: int) -> Page:
        return Page(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def create_source(self, item: ManualSourceCreate, admin_id: str) -> dict[str, Any]:
        if item.source_type.value != "manual":
            raise ValidationError("manual source API accepts source_type=manual only")
        values = item.model_dump(mode="json")
        values["name"] = normalize_text(item.name)
        if item.description:
            values["metadata"]["description"] = item.description
        with self.repository.transaction() as connection:
            public_id = self.repository.create_source(connection, values)
            _audit(connection, "dataset_source_created", admin_id, public_id, name=values["name"])
            row = self.repository.source_by_public_id(connection, public_id)
        return public_row(row)

    def get_source(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.source_by_public_id(connection, public_id))

    def update_source(self, public_id: str, patch: SourcePatch, admin_id: str) -> dict[str, Any]:
        changes = patch.model_dump(exclude_unset=True, mode="json")
        allowed = {"name", "language", "licence_name", "licence_status", "status", "metadata"}
        with self.repository.transaction() as connection:
            self.repository.source_by_public_id(connection, public_id)
            assignments, params = [], []
            for key, value in changes.items():
                if key not in allowed:
                    continue
                column = "metadata_json" if key == "metadata" else key
                assignments.append(f"{column}=?")
                params.append(
                    dumps_json(value)
                    if key == "metadata"
                    else normalize_text(value)
                    if key == "name"
                    else value
                )
            if assignments:
                assignments.append("updated_at=CURRENT_TIMESTAMP")
                connection.execute(
                    f"UPDATE dataset_sources SET {','.join(assignments)} WHERE public_id=?",
                    (*params, public_id),
                )
            _audit(
                connection, "dataset_source_updated", admin_id, public_id, fields=sorted(changes)
            )
            row = self.repository.source_by_public_id(connection, public_id)
        return public_row(row)

    def list_sources(self, filters, page: int, page_size: int) -> Page:
        items, total = self.repository.list_sources(filters, page, page_size)
        return self.page(items, total, page, page_size)

    def create_record(self, item: RecordCreate, admin_id: str) -> dict[str, Any]:
        values = item.model_dump(mode="json")
        validate_record(values)
        digest = content_hash(values)
        duplicate_id = None
        with self.repository.transaction() as connection:
            source = self.repository.source_by_public_id(connection, item.source_public_id)
            duplicate = self.repository.duplicate(connection, digest)
            if duplicate:
                duplicate_id = duplicate["public_id"]
                _audit(
                    connection,
                    "dataset_duplicate_rejected",
                    admin_id,
                    duplicate_id,
                    content_hash=digest,
                )
            else:
                public_id = str(uuid4())
                legacy = item.output_text or item.input_text or item.instruction or ""
                connection.execute(
                    """INSERT INTO dataset_records(source_id,content,language,status,public_id,
                    record_type,instruction,input_text,output_text,normalized_input,content_hash,
                    metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        source["id"],
                        legacy,
                        item.language.value,
                        "draft",
                        public_id,
                        item.record_type.value,
                        item.instruction,
                        item.input_text,
                        item.output_text,
                        item.normalized_input,
                        digest,
                        dumps_json(item.metadata),
                    ),
                )
                _audit(
                    connection, "dataset_record_created", admin_id, public_id, content_hash=digest
                )
                row = self.repository.record_by_public_id(connection, public_id)
        if duplicate_id:
            raise ConflictError(f"duplicate record: {duplicate_id}")
        return public_row(row)

    def get_record(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.record_by_public_id(connection, public_id))

    def update_record(self, public_id: str, patch: RecordPatch, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.record_by_public_id(connection, public_id)
            if row["status"] not in {"draft", "pending_review"}:
                raise ValidationError("only draft or pending-review records can be edited")
            values = {
                key: row[key]
                for key in (
                    "record_type",
                    "language",
                    "instruction",
                    "input_text",
                    "output_text",
                    "normalized_input",
                )
            }
            values["metadata"] = loads_json(row["metadata_json"])
            values.update(patch.model_dump(exclude_unset=True, mode="json"))
            validate_record(values)
            digest = content_hash(values)
            duplicate = self.repository.duplicate(connection, digest, public_id)
            if duplicate:
                raise ConflictError(f"duplicate record: {duplicate['public_id']}")
            connection.execute(
                """UPDATE dataset_records SET record_type=?,language=?,instruction=?,input_text=?,
                output_text=?,normalized_input=?,content_hash=?,metadata_json=?,updated_at=CURRENT_TIMESTAMP
                WHERE public_id=?""",
                (
                    values["record_type"],
                    values["language"],
                    values.get("instruction"),
                    values.get("input_text"),
                    values.get("output_text"),
                    values.get("normalized_input"),
                    digest,
                    dumps_json(values["metadata"]),
                    public_id,
                ),
            )
            _audit(connection, "dataset_record_updated", admin_id, public_id, content_hash=digest)
            updated = self.repository.record_by_public_id(connection, public_id)
        return public_row(updated)

    def transition(
        self, public_id: str, target: str, decision: str, comments: str | None, admin_id: str
    ):
        with self.repository.transaction() as connection:
            row = self.repository.record_by_public_id(connection, public_id)
            previous = row["status"]
            if target not in TRANSITIONS.get(previous, set()):
                raise ValidationError(f"invalid dataset transition: {previous} -> {target}")
            if decision in {"reject", "request_changes"} and not normalize_text(comments):
                raise ValidationError("comments are required for this review decision")
            if target == "approved":
                assessment = connection.execute(
                    """SELECT readiness_status FROM dataset_quality_assessments
                    WHERE dataset_record_id=? ORDER BY created_at DESC,id DESC LIMIT 1""",
                    (row["id"],),
                ).fetchone()
                if assessment and assessment["readiness_status"] == "blocked":
                    raise ValidationError("blocked-quality records require an explicit override")
                values = {
                    key: row[key]
                    for key in (
                        "record_type",
                        "language",
                        "instruction",
                        "input_text",
                        "output_text",
                        "normalized_input",
                    )
                }
                values["metadata"] = loads_json(row["metadata_json"])
                validate_record(values)
            connection.execute(
                "UPDATE dataset_records SET status=?,updated_at=CURRENT_TIMESTAMP "
                "WHERE public_id=?",
                (target, public_id),
            )
            connection.execute(
                """INSERT INTO dataset_reviews(public_id,dataset_record_id,decision,reviewer_type,
                reviewer_reference,comments,previous_status,new_status) VALUES (?,?,?,?,?,?,?,?)""",
                (str(uuid4()), row["id"], decision, "admin", admin_id, comments, previous, target),
            )
            event = {
                "approved": "dataset_record_approved",
                "rejected": "dataset_record_rejected",
                "archived": "dataset_record_archived",
                "draft": "dataset_record_restored",
                "pending_review": "dataset_record_submitted",
            }[target]
            _audit(
                connection, event, admin_id, public_id, previous_status=previous, new_status=target
            )
            updated = self.repository.record_by_public_id(connection, public_id)
        return public_row(updated)

    def review(self, public_id: str, decision: ReviewDecision, comments: str | None, admin_id: str):
        mapping = {
            "approve": "approved",
            "reject": "rejected",
            "request_changes": "draft",
            "edit": "draft",
            "restore": "draft",
        }
        return self.transition(
            public_id, mapping[decision.value], decision.value, comments, admin_id
        )

    def list_records(self, filters, page: int, page_size: int) -> Page:
        items, total = self.repository.list_records(filters, page, page_size)
        return self.page(items, total, page, page_size)

    def reviews(self, public_id: str) -> list[dict[str, Any]]:
        with self.repository.transaction() as connection:
            row = self.repository.record_by_public_id(connection, public_id)
            rows = connection.execute(
                """SELECT public_id,decision,reviewer_type,reviewer_reference,comments,
                previous_status,new_status,created_at FROM dataset_reviews
                WHERE dataset_record_id=? ORDER BY created_at,id""",
                (row["id"],),
            ).fetchall()
        return [dict(item) for item in rows]

    def statistics(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            sources = connection.execute("SELECT COUNT(*) FROM dataset_sources").fetchone()[0]
            records = connection.execute("SELECT COUNT(*) FROM dataset_records").fetchone()[0]

            def grouped(column):
                return {
                    row[0]: row[1]
                    for row in connection.execute(
                        f"SELECT {column},COUNT(*) FROM dataset_records GROUP BY {column}"
                    )
                }

            by_status, by_language, by_type = (
                grouped("status"),
                grouped("language"),
                grouped("record_type"),
            )
            duplicates = connection.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE event_type='dataset_duplicate_rejected'"
            ).fetchone()[0]
        return {
            "total_sources": sources,
            "total_records": records,
            "by_status": by_status,
            "by_language": by_language,
            "by_record_type": by_type,
            "approved_records": by_status.get("approved", 0),
            "pending_review_records": by_status.get("pending_review", 0),
            "duplicate_conflicts": duplicates,
        }

    def duplicates(self) -> list[dict[str, Any]]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                """SELECT resource_public_id,metadata_json,created_at FROM audit_logs
                WHERE event_type='dataset_duplicate_rejected' ORDER BY id DESC LIMIT 100"""
            ).fetchall()
        return [
            {
                "existing_record_public_id": row[0],
                "context": loads_json(row[1]),
                "created_at": row[2],
            }
            for row in rows
        ]
