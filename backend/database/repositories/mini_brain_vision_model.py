"""Repository for MB-15: Brud Mini Brain Vision Model Integration &
Human-in-the-Loop Annotation Center.

Six tables, all MB-15's own: `mini_brain_vision_provider_registry`
(real, admin-extensible, seeded with 6 defaults by the migration
itself -- 3 real backend types, 3 disclosed future placeholders),
`mini_brain_vision_model_sessions`, `mini_brain_vision_model_
predictions` (one row per AI-predicted or admin-added object),
`mini_brain_vision_correction_memory` (permanent, insert-only),
`mini_brain_vision_learning_memory` (permanent, insert-only), and
`mini_brain_vision_model_events` (append-only). MB-15 never writes to
any other system's tables, including MB-14's own vision tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "image_load_report", "provider_report", "detection_report", "scene_report", "caption_report",
    "relationship_report", "ocr_cross_validation_report", "quality_report", "admin_review_report",
    "correction_memory_report", "knowledge_graph_report", "dataset_draft_report", "vision_report",
)
_PREDICTION_INTERNAL = {"id"}
_PROVIDER_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision model session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_prediction_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision model prediction row not found")
    data = dict(row)
    for key in list(data):
        if key in _PREDICTION_INTERNAL or key == "vision_model_session_id":
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_provider_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision provider row not found")
    data = dict(row)
    for key in list(data):
        if key in _PROVIDER_INTERNAL:
            data.pop(key)
    return data


def public_correction_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision correction memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "vision_model_session_id":
            data.pop(key)
    return data


def public_learning_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision learning memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "vision_model_session_id":
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainVisionModelRepository(BaseRepository):
    # -- provider registry ---------------------------------------------------------

    def list_providers(
        self, connection: sqlite3.Connection, *, status: str | None = None,
    ) -> list[sqlite3.Row]:
        if status:
            return connection.execute(
                "SELECT * FROM mini_brain_vision_provider_registry WHERE status=? ORDER BY id",
                (status,),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_vision_provider_registry ORDER BY id"
        ).fetchall()

    def get_provider(self, connection: sqlite3.Connection, provider_key: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_vision_provider_registry WHERE provider_key=?", (provider_key,)
        ).fetchone()

    def set_provider_status(
        self, connection: sqlite3.Connection, provider_key: str, *, status: str,
    ) -> sqlite3.Row:
        connection.execute(
            "UPDATE mini_brain_vision_provider_registry SET status=?, updated_at=CURRENT_TIMESTAMP WHERE provider_key=?",
            (status, provider_key),
        )
        row = self.get_provider(connection, provider_key)
        if row is None:
            raise NotFoundError(f"provider not found: {provider_key}")
        return row

    # -- sessions ---------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, vision_session_public_id: str,
        language_session_public_id: str | None, provider_key: str, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_model_sessions(
                public_id, vision_session_public_id, language_session_public_id, provider_key,
                created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?)""",
            (public_id, vision_session_public_id, language_session_public_id, provider_key,
             created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_vision_model_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"vision model session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_vision_model_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_vision_model_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    # -- predictions --------------------------------------------------------------

    def create_prediction(
        self, connection: sqlite3.Connection, *, vision_model_session_id: int, image_public_id: str,
        label: str, confidence: float, bounding_box: dict[str, Any] | None, object_class: str | None,
        color: str | None, shape: str | None, approximate_size: str | None, visibility: str | None,
        provider_key: str, model_version: str | None, source: str, review_status: str = "pending",
        public_id: str | None = None,
    ) -> str:
        prediction_public_id = public_id or str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_model_predictions(
                public_id, vision_model_session_id, image_public_id, label, confidence,
                bounding_box_json, object_class, color, shape, approximate_size, visibility,
                provider_key, model_version, source, review_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                prediction_public_id, vision_model_session_id, image_public_id, label, confidence,
                dumps_json(bounding_box) if bounding_box is not None else None, object_class, color,
                shape, approximate_size, visibility, provider_key, model_version, source, review_status,
            ),
        )
        return prediction_public_id

    def update_prediction(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.get_prediction(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column == "bounding_box_json" else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_vision_model_predictions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.get_prediction(connection, public_id)

    def get_prediction(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_vision_model_predictions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"vision model prediction not found: {public_id}")
        return row

    def list_predictions(
        self, connection: sqlite3.Connection, *, vision_model_session_id: int,
        review_status: str | None = None,
    ) -> list[sqlite3.Row]:
        if review_status:
            return connection.execute(
                """SELECT * FROM mini_brain_vision_model_predictions
                WHERE vision_model_session_id=? AND review_status=? ORDER BY id""",
                (vision_model_session_id, review_status),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_vision_model_predictions WHERE vision_model_session_id=? ORDER BY id",
            (vision_model_session_id,),
        ).fetchall()

    # -- correction memory (permanent, insert-only) --------------------------------

    def record_correction(
        self, connection: sqlite3.Connection, *, vision_model_session_id: int, prediction_public_id: str,
        action: str, wrong_label: str | None, correct_label: str | None, reason: str,
        original_confidence: float | None, provider_key: str, model_version: str | None,
        recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_correction_memory(
                public_id, vision_model_session_id, prediction_public_id, action, wrong_label,
                correct_label, reason, original_confidence, provider_key, model_version,
                recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, vision_model_session_id, prediction_public_id, action, wrong_label,
                correct_label, reason, original_confidence, provider_key, model_version,
                recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_corrections(
        self, connection: sqlite3.Connection, *, vision_model_session_id: int,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_vision_correction_memory WHERE vision_model_session_id=? ORDER BY id",
            (vision_model_session_id,),
        ).fetchall()

    # -- learning memory (permanent, insert-only) ----------------------------------

    def record_learning_memory(
        self, connection: sqlite3.Connection, *, vision_model_session_id: int, provider_key: str,
        model_version: str | None, total_predictions: int, approved_count: int, corrected_count: int,
        rejected_count: int, correction_rate: float | None, quality_report: dict[str, Any],
        admin_decision: str | None, notes: str, recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_learning_memory(
                public_id, vision_model_session_id, provider_key, model_version, total_predictions,
                approved_count, corrected_count, rejected_count, correction_rate, quality_report_json,
                admin_decision, notes, recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, vision_model_session_id, provider_key, model_version, total_predictions,
                approved_count, corrected_count, rejected_count, correction_rate,
                dumps_json(quality_report), admin_decision, notes, recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_learning_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_vision_learning_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- events (append-only) -----------------------------------------------------

    def record_event(
        self, connection: sqlite3.Connection, *, vision_model_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_model_events(
                public_id, vision_model_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, vision_model_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, vision_model_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_vision_model_events WHERE vision_model_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (vision_model_session_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainVisionModelRepository", "public_session_row", "public_prediction_row",
    "public_provider_row", "public_correction_row", "public_learning_memory_row", "SESSION_JSON_FIELDS",
]
