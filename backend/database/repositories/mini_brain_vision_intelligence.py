"""Repository for MB-14: Brud Mini Brain Vision Intelligence & Image
Understanding Center.

Four tables, all MB-14's own: `mini_brain_vision_sessions`,
`mini_brain_vision_images` (extracted image metadata -- the bytes
themselves live on disk, matching Document Workspace's own PDF-storage
pattern), `mini_brain_vision_objects` (admin-annotated/auto-detected
objects, soft-deleted never row-deleted), and `mini_brain_vision_events`
(append-only, immutability triggers). MB-14 never writes to any other
system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "image_extraction_report", "quality_report", "vision_understanding_report",
    "ocr_cross_validation_report", "caption_report", "bounding_box_report", "annotation_report",
    "knowledge_graph_report", "qa_report", "vision_dataset_draft_report",
    "vision_quality_score_report", "vision_report",
)
_OBJECT_INTERNAL = {"id"}
_OBJECT_JSON_FIELDS = ("bounding_box",)


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_image_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision image row not found")
    data = dict(row)
    data.pop("id", None)
    data.pop("vision_session_id", None)
    return data


def public_object_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision object row not found")
    data = dict(row)
    for key in list(data):
        if key in _OBJECT_INTERNAL or key == "vision_session_id":
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainVisionIntelligenceRepository(BaseRepository):
    # -- sessions ---------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, document_source_public_id: str,
        dataset_source_public_id: str | None, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_sessions(
                public_id, document_source_public_id, dataset_source_public_id, created_by_admin_public_id
            ) VALUES (?, ?, ?, ?)""",
            (public_id, document_source_public_id, dataset_source_public_id, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_vision_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"vision session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_vision_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def update_session(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.session(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        json_columns = {f"{f}_json" for f in SESSION_JSON_FIELDS}
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_vision_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    # -- images (metadata only -- bytes live on disk) ----------------------------

    def record_image(
        self, connection: sqlite3.Connection, *, vision_session_id: int, page_number: int,
        image_index: int, stored_filename: str, image_format: str, width_pixels: int,
        height_pixels: int, file_size_bytes: int, checksum_sha256: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_images(
                public_id, vision_session_id, page_number, image_index, stored_filename, image_format,
                width_pixels, height_pixels, file_size_bytes, checksum_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, vision_session_id, page_number, image_index, stored_filename, image_format,
                width_pixels, height_pixels, file_size_bytes, checksum_sha256,
            ),
        )
        return public_id

    def list_images(
        self, connection: sqlite3.Connection, *, vision_session_id: int,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_vision_images WHERE vision_session_id=? ORDER BY page_number, image_index",
            (vision_session_id,),
        ).fetchall()

    def get_image(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_vision_images WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"vision image not found: {public_id}")
        return row

    # -- objects (soft-deleted, never row-deleted) --------------------------------

    def create_object(
        self, connection: sqlite3.Connection, *, vision_session_id: int, image_public_id: str,
        label: str, confidence: float, bounding_box: dict[str, Any] | None, source: str,
        created_by_admin_public_id: str, public_id: str | None = None,
    ) -> str:
        object_public_id = public_id or str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_objects(
                public_id, vision_session_id, image_public_id, label, confidence, bounding_box_json,
                source, created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                object_public_id, vision_session_id, image_public_id, label, confidence,
                dumps_json(bounding_box) if bounding_box is not None else None, source,
                created_by_admin_public_id,
            ),
        )
        return object_public_id

    def update_object(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.get_object(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column == "bounding_box_json" else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_vision_objects SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.get_object(connection, public_id)

    def get_object(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_vision_objects WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"vision object not found: {public_id}")
        return row

    def list_objects(
        self, connection: sqlite3.Connection, *, vision_session_id: int, status: str | None = None,
    ) -> list[sqlite3.Row]:
        if status:
            return connection.execute(
                "SELECT * FROM mini_brain_vision_objects WHERE vision_session_id=? AND status=? ORDER BY id",
                (vision_session_id, status),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_vision_objects WHERE vision_session_id=? ORDER BY id",
            (vision_session_id,),
        ).fetchall()

    # -- events (append-only) -----------------------------------------------------

    def record_event(
        self, connection: sqlite3.Connection, *, vision_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_events(
                public_id, vision_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, vision_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, vision_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_vision_events WHERE vision_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (vision_session_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainVisionIntelligenceRepository", "public_session_row", "public_image_row",
    "public_object_row", "SESSION_JSON_FIELDS",
]
