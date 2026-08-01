"""Repository for the Phase 10 Live Dataset Discovery workspace:
search sessions, requirements (1:1), provider runs, candidates,
candidate sources (raw per-provider evidence), candidate scores,
comparisons, and an append-only search-event log.

Never writes to `data_sources`, any governance table, or any lineage
table -- a discovery session is read-only research, never an import.
See ``docs/data_discovery/phase10_live_dataset_discovery_plan.md``.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError


def _session_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "session_code": row["session_code"],
        "title": row["title"],
        "status": row["status"],
        "requested_by_admin_public_id": row["requested_by_admin_public_id"],
        "current_stage": row["current_stage"],
        "result_count": row["result_count"],
        "provider_count": row["provider_count"],
        "successful_provider_count": row["successful_provider_count"],
        "failed_provider_count": row["failed_provider_count"],
        "warning_count": row["warning_count"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "cancelled_at": row["cancelled_at"],
        "expires_at": row["expires_at"],
    }


def _requirements_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "search_session_public_id": row["search_session_public_id"],
        "modality": row["modality"],
        "languages": loads_json(row["languages_json"]),
        "tasks": loads_json(row["tasks_json"]),
        "intended_uses": loads_json(row["intended_uses_json"]),
        "commercial_requirement": row["commercial_requirement"],
        "domain_tags": loads_json(row["domain_tags_json"]),
        "preferred_providers": loads_json(row["preferred_providers_json"]),
        "excluded_providers": loads_json(row["excluded_providers_json"]),
        "minimum_records": row["minimum_records"],
        "maximum_download_size_bytes": row["maximum_download_size_bytes"],
        "preferred_file_formats": loads_json(row["preferred_file_formats_json"]),
        "quality_preferences": loads_json(row["quality_preferences_json"]),
        "licence_preferences": loads_json(row["licence_preferences_json"]),
        "free_text_requirement": row["free_text_requirement"],
        "inferred_fields": loads_json(row["inferred_fields_json"]),
        "confirmed_fields": loads_json(row["confirmed_fields_json"]),
        "unknown_fields": loads_json(row["unknown_fields_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _provider_run_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "search_session_public_id": row["search_session_public_id"],
        "provider_public_id": row["provider_public_id"],
        "provider_code": row["provider_code"],
        "status": row["status"],
        "query_used": row["query_used"],
        "result_count": row["result_count"],
        "error_code": row["error_code"],
        "warnings": loads_json(row["warnings_json"]),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "latency_ms": row["latency_ms"],
    }


def _candidate_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "search_session_public_id": row["search_session_public_id"],
        "canonical_name": row["canonical_name"],
        "normalized_name": row["normalized_name"],
        "provider_count": row["provider_count"],
        "primary_provider_public_id": row["primary_provider_public_id"],
        "modality": row["modality"],
        "languages": loads_json(row["languages_json"]),
        "tasks": loads_json(row["tasks_json"]),
        "intended_use_fit": loads_json(row["intended_use_fit_json"]),
        "description": row["description"],
        "organization": row["organization"],
        "authors": loads_json(row["authors_json"]),
        "tags": loads_json(row["tags_json"]),
        "declared_licence": row["declared_licence"],
        "licence_status": row["licence_status"],
        "commercial_use_status": row["commercial_use_status"],
        "training_use_status": row["training_use_status"],
        "rag_use_status": row["rag_use_status"],
        "evaluation_use_status": row["evaluation_use_status"],
        "record_count": row["record_count"],
        "download_size_bytes": row["download_size_bytes"],
        "file_formats": loads_json(row["file_formats_json"]),
        "dataset_card_present": bool(row["dataset_card_present"]),
        "dataset_card_url": row["dataset_card_url"],
        "homepage_url": row["homepage_url"],
        "repository_url": row["repository_url"],
        "gated": bool(row["gated"]),
        "private": bool(row["private"]),
        "authentication_required": bool(row["authentication_required"]),
        "version": row["version"],
        "revision": row["revision"],
        "last_modified_at": row["last_modified_at"],
        "freshness_status": row["freshness_status"],
        "metadata_completeness_score": row["metadata_completeness_score"],
        "quality_signal_score": row["quality_signal_score"],
        "suitability_score": row["suitability_score"],
        "risk_score": row["risk_score"],
        "recommendation_status": row["recommendation_status"],
        "warnings": loads_json(row["warnings_json"]),
        "blocking_reasons": loads_json(row["blocking_reasons_json"]),
        "excluded": bool(row["excluded"]),
        "possible_duplicate_of_candidate_public_id": row[
            "possible_duplicate_of_candidate_public_id"
        ],
        "candidate_entry_method": row["candidate_entry_method"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _candidate_source_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "provider_public_id": row["provider_public_id"],
        "provider_dataset_id": row["provider_dataset_id"],
        "source_url": row["source_url"],
        "dataset_card_url": row["dataset_card_url"],
        "metadata_url": row["metadata_url"],
        "version": row["version"],
        "revision": row["revision"],
        "raw_metadata": loads_json(row["raw_metadata_json"]),
        "raw_metadata_checksum": row["raw_metadata_checksum"],
        "retrieved_at": row["retrieved_at"],
        "response_status": row["response_status"],
        "warnings": loads_json(row["warnings_json"]),
    }


def _candidate_score_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "candidate_public_id": row["candidate_public_id"],
        "dimension": row["dimension"],
        "raw_value": row["raw_value"],
        "weight": row["weight"],
        "score": row["score"],
        "reason": row["reason"],
        "created_at": row["created_at"],
    }


def _comparison_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "search_session_public_id": row["search_session_public_id"],
        "candidate_ids": loads_json(row["candidate_ids_json"]),
        "summary": loads_json(row["summary_json"]),
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "search_session_public_id": row["search_session_public_id"],
        "event_type": row["event_type"],
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


class ExternalDatasetDiscoveryRepository(BaseRepository):
    # -- sessions -----------------------------------------------------------

    def create_session(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO external_dataset_search_sessions(
                public_id, session_code, title, requested_by_admin_public_id)
                VALUES (?,?,?,?)""",
                (
                    public_id,
                    values["session_code"],
                    values.get("title", ""),
                    values["requested_by_admin_public_id"],
                ),
            )
        return self.get_session(public_id)

    def get_session(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM external_dataset_search_sessions WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("search session not found")
        return _session_public(row)

    def get_session_by_code(self, session_code: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM external_dataset_search_sessions WHERE session_code=?",
                (session_code,),
            ).fetchone()
        return _session_public(row) if row else None

    def list_sessions(
        self,
        *,
        status: str | None = None,
        requested_by_admin_public_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if requested_by_admin_public_id:
            clauses.append("requested_by_admin_public_id=?")
            params.append(requested_by_admin_public_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                f"SELECT * FROM external_dataset_search_sessions {where} "  # noqa: S608
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_session_public(row) for row in rows]

    def update_session(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_session(public_id)
        assignments = ", ".join(f'"{key}"=?' for key in fields)
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_dataset_search_sessions WHERE public_id=?", (public_id,)
            ).fetchone()
            if not current:
                raise NotFoundError("search session not found")
            connection.execute(
                f'UPDATE external_dataset_search_sessions SET {assignments} '  # noqa: S608
                "WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_session(public_id)

    def _session_id(self, connection: sqlite3.Connection, session_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_search_sessions WHERE public_id=?",
            (session_public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("search session not found")
        return row["id"]

    # -- requirements (1:1) --------------------------------------------------

    def upsert_requirements(self, session_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            existing = connection.execute(
                "SELECT public_id FROM external_dataset_search_requirements "
                "WHERE search_session_id=?",
                (session_id,),
            ).fetchone()
            columns = {
                "modality": values.get("modality", "text"),
                "languages_json": dumps_json(values.get("languages", [])),
                "tasks_json": dumps_json(values.get("tasks", [])),
                "intended_uses_json": dumps_json(values.get("intended_uses", [])),
                "commercial_requirement": values.get("commercial_requirement", "unknown"),
                "domain_tags_json": dumps_json(values.get("domain_tags", [])),
                "preferred_providers_json": dumps_json(values.get("preferred_providers", [])),
                "excluded_providers_json": dumps_json(values.get("excluded_providers", [])),
                "minimum_records": values.get("minimum_records"),
                "maximum_download_size_bytes": values.get("maximum_download_size_bytes"),
                "preferred_file_formats_json": dumps_json(values.get("preferred_file_formats", [])),
                "quality_preferences_json": dumps_json(values.get("quality_preferences", {})),
                "licence_preferences_json": dumps_json(values.get("licence_preferences", {})),
                "free_text_requirement": values.get("free_text_requirement", ""),
                "inferred_fields_json": dumps_json(values.get("inferred_fields", {})),
                "confirmed_fields_json": dumps_json(values.get("confirmed_fields", {})),
                "unknown_fields_json": dumps_json(values.get("unknown_fields", [])),
            }
            if existing:
                assignments = ", ".join(f'"{key}"=?' for key in columns)
                connection.execute(
                    f'UPDATE external_dataset_search_requirements SET {assignments}, '  # noqa: S608
                    "updated_at=CURRENT_TIMESTAMP WHERE search_session_id=?",
                    (*columns.values(), session_id),
                )
                public_id = existing["public_id"]
            else:
                public_id = str(uuid4())
                connection.execute(
                    """INSERT INTO external_dataset_search_requirements(
                    public_id, search_session_id, modality, languages_json, tasks_json,
                    intended_uses_json, commercial_requirement, domain_tags_json,
                    preferred_providers_json, excluded_providers_json, minimum_records,
                    maximum_download_size_bytes, preferred_file_formats_json,
                    quality_preferences_json, licence_preferences_json, free_text_requirement,
                    inferred_fields_json, confirmed_fields_json, unknown_fields_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (public_id, session_id, *columns.values()),
                )
        return self.get_requirements(session_public_id)

    def get_requirements(self, session_public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                self._requirements_select_sql() + " WHERE s.public_id=?", (session_public_id,)
            ).fetchone()
        return _requirements_public(row) if row else None

    @staticmethod
    def _requirements_select_sql() -> str:
        return (
            "SELECT r.*, s.public_id AS search_session_public_id "
            "FROM external_dataset_search_requirements r "
            "JOIN external_dataset_search_sessions s ON s.id = r.search_session_id"
        )

    # -- provider runs --------------------------------------------------------

    def create_provider_run(self, session_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            provider_row = connection.execute(
                "SELECT id FROM external_data_providers WHERE public_id=?",
                (values["provider_public_id"],),
            ).fetchone()
            if not provider_row:
                raise NotFoundError("external data provider not found")
            connection.execute(
                """INSERT INTO external_dataset_search_provider_runs(
                public_id, search_session_id, provider_id, status, query_used)
                VALUES (?,?,?,?,?)""",
                (
                    public_id,
                    session_id,
                    provider_row["id"],
                    values.get("status", "success"),
                    values.get("query_used", ""),
                ),
            )
        return self.get_provider_run(public_id)

    def update_provider_run(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_provider_run(public_id)
        assignments = ", ".join(f'"{key}"=?' for key in fields)
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_dataset_search_provider_runs WHERE public_id=?",
                (public_id,),
            ).fetchone()
            if not current:
                raise NotFoundError("provider run not found")
            connection.execute(
                f'UPDATE external_dataset_search_provider_runs SET {assignments} '  # noqa: S608
                "WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_provider_run(public_id)

    def get_provider_run(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._provider_run_select_sql() + " WHERE pr.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("provider run not found")
        return _provider_run_public(row)

    def list_provider_runs(self, session_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            rows = connection.execute(
                self._provider_run_select_sql() + " WHERE pr.search_session_id=? ORDER BY pr.id",
                (session_id,),
            ).fetchall()
        return [_provider_run_public(row) for row in rows]

    @staticmethod
    def _provider_run_select_sql() -> str:
        return (
            "SELECT pr.*, s.public_id AS search_session_public_id, "
            "p.public_id AS provider_public_id, p.provider_code AS provider_code "
            "FROM external_dataset_search_provider_runs pr "
            "JOIN external_dataset_search_sessions s ON s.id = pr.search_session_id "
            "JOIN external_data_providers p ON p.id = pr.provider_id"
        )

    # -- candidates -----------------------------------------------------------

    def create_candidate(self, session_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            primary_provider_id = None
            if values.get("primary_provider_public_id"):
                provider_row = connection.execute(
                    "SELECT id FROM external_data_providers WHERE public_id=?",
                    (values["primary_provider_public_id"],),
                ).fetchone()
                primary_provider_id = provider_row["id"] if provider_row else None
            connection.execute(
                """INSERT INTO external_dataset_candidates(
                public_id, search_session_id, canonical_name, normalized_name, primary_provider_id,
                modality, languages_json, tasks_json, intended_use_fit_json, description,
                organization, authors_json, tags_json, declared_licence, licence_status,
                record_count, download_size_bytes, file_formats_json, dataset_card_present,
                dataset_card_url, homepage_url, repository_url, gated, private,
                authentication_required, version, revision, last_modified_at,
                candidate_entry_method)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    session_id,
                    values["canonical_name"],
                    values["normalized_name"],
                    primary_provider_id,
                    values.get("modality"),
                    dumps_json(values.get("languages", [])),
                    dumps_json(values.get("tasks", [])),
                    dumps_json(values.get("intended_use_fit", {})),
                    values.get("description", ""),
                    values.get("organization"),
                    dumps_json(values.get("authors", [])),
                    dumps_json(values.get("tags", [])),
                    values.get("declared_licence"),
                    values.get("licence_status", "unknown"),
                    values.get("record_count"),
                    values.get("download_size_bytes"),
                    dumps_json(values.get("file_formats", [])),
                    int(bool(values.get("dataset_card_present", False))),
                    values.get("dataset_card_url"),
                    values.get("homepage_url"),
                    values.get("repository_url"),
                    int(bool(values.get("gated", False))),
                    int(bool(values.get("private", False))),
                    int(bool(values.get("authentication_required", False))),
                    values.get("version"),
                    values.get("revision"),
                    values.get("last_modified_at"),
                    values.get("candidate_entry_method", "provider_search"),
                ),
            )
        return self.get_candidate(public_id)

    def get_candidate(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._candidate_select_sql() + " WHERE c.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("candidate not found")
        return _candidate_public(row)

    def list_candidates(
        self, session_public_id: str, *, include_excluded: bool = True
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            clause = "" if include_excluded else "AND c.excluded=0"
            rows = connection.execute(
                self._candidate_select_sql()
                + f" WHERE c.search_session_id=? {clause} ORDER BY c.suitability_score DESC, c.id",  # noqa: S608
                (session_id,),
            ).fetchall()
        return [_candidate_public(row) for row in rows]

    def update_candidate(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_candidate(public_id)
        assignments = ", ".join(f'"{key}"=?' for key in fields)
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_dataset_candidates WHERE public_id=?", (public_id,)
            ).fetchone()
            if not current:
                raise NotFoundError("candidate not found")
            connection.execute(
                f'UPDATE external_dataset_candidates SET {assignments}, '  # noqa: S608
                "updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (*fields.values(), public_id),
            )
        return self.get_candidate(public_id)

    @staticmethod
    def _candidate_select_sql() -> str:
        return (
            "SELECT c.*, s.public_id AS search_session_public_id, "
            "p.public_id AS primary_provider_public_id, "
            "d.public_id AS possible_duplicate_of_candidate_public_id "
            "FROM external_dataset_candidates c "
            "JOIN external_dataset_search_sessions s ON s.id = c.search_session_id "
            "LEFT JOIN external_data_providers p ON p.id = c.primary_provider_id "
            "LEFT JOIN external_dataset_candidates d ON d.id = c.possible_duplicate_of_candidate_id"
        )

    def mark_possible_duplicate(
        self, candidate_public_id: str, target_candidate_public_id: str
    ) -> dict[str, Any]:
        """Flags `candidate_public_id` as a *possible* (never
        auto-merged) duplicate of `target_candidate_public_id` -- both
        candidate rows continue to exist independently; this only sets
        the pointer human review acts on."""

        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_dataset_candidates WHERE public_id=?",
                (candidate_public_id,),
            ).fetchone()
            if not current:
                raise NotFoundError("candidate not found")
            target = connection.execute(
                "SELECT id FROM external_dataset_candidates WHERE public_id=?",
                (target_candidate_public_id,),
            ).fetchone()
            if not target:
                raise NotFoundError("target candidate not found")
            connection.execute(
                """UPDATE external_dataset_candidates SET possible_duplicate_of_candidate_id=?,
                updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (target["id"], candidate_public_id),
            )
        return self.get_candidate(candidate_public_id)

    # -- candidate sources ------------------------------------------------------

    def add_candidate_source(
        self, candidate_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            candidate_row = connection.execute(
                "SELECT id FROM external_dataset_candidates WHERE public_id=?",
                (candidate_public_id,),
            ).fetchone()
            if not candidate_row:
                raise NotFoundError("candidate not found")
            provider_row = connection.execute(
                "SELECT id FROM external_data_providers WHERE public_id=?",
                (values["provider_public_id"],),
            ).fetchone()
            if not provider_row:
                raise NotFoundError("external data provider not found")
            connection.execute(
                """INSERT INTO external_dataset_candidate_sources(
                public_id, candidate_id, provider_id, provider_dataset_id, source_url,
                dataset_card_url, metadata_url, version, revision, raw_metadata_json,
                raw_metadata_checksum, response_status, warnings_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(candidate_id, provider_id, provider_dataset_id) DO UPDATE SET
                    source_url=excluded.source_url, dataset_card_url=excluded.dataset_card_url,
                    metadata_url=excluded.metadata_url, version=excluded.version,
                    revision=excluded.revision, raw_metadata_json=excluded.raw_metadata_json,
                    raw_metadata_checksum=excluded.raw_metadata_checksum,
                    response_status=excluded.response_status, warnings_json=excluded.warnings_json,
                    retrieved_at=CURRENT_TIMESTAMP""",
                (
                    public_id,
                    candidate_row["id"],
                    provider_row["id"],
                    values["provider_dataset_id"],
                    values.get("source_url"),
                    values.get("dataset_card_url"),
                    values.get("metadata_url"),
                    values.get("version"),
                    values.get("revision"),
                    dumps_json(values.get("raw_metadata", {})),
                    values.get("raw_metadata_checksum"),
                    values.get("response_status", "success"),
                    dumps_json(values.get("warnings", [])),
                ),
            )
            row = connection.execute(
                self._candidate_source_select_sql()
                + " WHERE cs.candidate_id=? AND cs.provider_id=? AND cs.provider_dataset_id=?",
                (candidate_row["id"], provider_row["id"], values["provider_dataset_id"]),
            ).fetchone()
        return _candidate_source_public(row)

    def list_candidate_sources(self, candidate_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            candidate_row = connection.execute(
                "SELECT id FROM external_dataset_candidates WHERE public_id=?",
                (candidate_public_id,),
            ).fetchone()
            if not candidate_row:
                raise NotFoundError("candidate not found")
            rows = connection.execute(
                self._candidate_source_select_sql() + " WHERE cs.candidate_id=? ORDER BY cs.id",
                (candidate_row["id"],),
            ).fetchall()
        return [_candidate_source_public(row) for row in rows]

    @staticmethod
    def _candidate_source_select_sql() -> str:
        return (
            "SELECT cs.*, c.public_id AS candidate_public_id, p.public_id AS provider_public_id "
            "FROM external_dataset_candidate_sources cs "
            "JOIN external_dataset_candidates c ON c.id = cs.candidate_id "
            "JOIN external_data_providers p ON p.id = cs.provider_id"
        )

    # -- candidate scores ---------------------------------------------------------

    def set_candidate_scores(
        self, candidate_public_id: str, components: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            candidate_row = connection.execute(
                "SELECT id FROM external_dataset_candidates WHERE public_id=?",
                (candidate_public_id,),
            ).fetchone()
            if not candidate_row:
                raise NotFoundError("candidate not found")
            candidate_id = candidate_row["id"]
            connection.execute(
                "DELETE FROM external_dataset_candidate_scores WHERE candidate_id=?",
                (candidate_id,),
            )
            for component in components:
                connection.execute(
                    """INSERT INTO external_dataset_candidate_scores(
                    public_id, candidate_id, dimension, raw_value, weight, score, reason)
                    VALUES (?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()),
                        candidate_id,
                        component["dimension"],
                        component["raw_value"],
                        component["weight"],
                        component["score"],
                        component.get("reason", ""),
                    ),
                )
        return self.list_candidate_scores(candidate_public_id)

    def list_candidate_scores(self, candidate_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            candidate_row = connection.execute(
                "SELECT id FROM external_dataset_candidates WHERE public_id=?",
                (candidate_public_id,),
            ).fetchone()
            if not candidate_row:
                raise NotFoundError("candidate not found")
            rows = connection.execute(
                self._candidate_score_select_sql() + " WHERE sc.candidate_id=? ORDER BY sc.id",
                (candidate_row["id"],),
            ).fetchall()
        return [_candidate_score_public(row) for row in rows]

    @staticmethod
    def _candidate_score_select_sql() -> str:
        return (
            "SELECT sc.*, c.public_id AS candidate_public_id "
            "FROM external_dataset_candidate_scores sc "
            "JOIN external_dataset_candidates c ON c.id = sc.candidate_id"
        )

    # -- comparisons -----------------------------------------------------------

    def create_comparison(self, session_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            connection.execute(
                """INSERT INTO external_dataset_candidate_comparisons(
                public_id, search_session_id, candidate_ids_json, summary_json,
                created_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                (
                    public_id,
                    session_id,
                    dumps_json(values["candidate_ids"]),
                    dumps_json(values.get("summary", {})),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_comparison(public_id)

    def get_comparison(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._comparison_select_sql() + " WHERE cc.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("comparison not found")
        return _comparison_public(row)

    def list_comparisons(self, session_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            rows = connection.execute(
                self._comparison_select_sql()
                + " WHERE cc.search_session_id=? ORDER BY cc.id DESC",
                (session_id,),
            ).fetchall()
        return [_comparison_public(row) for row in rows]

    @staticmethod
    def _comparison_select_sql() -> str:
        return (
            "SELECT cc.*, s.public_id AS search_session_public_id "
            "FROM external_dataset_candidate_comparisons cc "
            "JOIN external_dataset_search_sessions s ON s.id = cc.search_session_id"
        )

    # -- events (append-only) -----------------------------------------------------

    def record_event(self, session_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            connection.execute(
                """INSERT INTO external_dataset_search_events(
                public_id, search_session_id, event_type, summary, metadata_json,
                performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                (
                    public_id,
                    session_id,
                    values["event_type"],
                    values.get("summary", ""),
                    dumps_json(values.get("metadata", {})),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_event(public_id)

    def get_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("search event not found")
        return _event_public(row)

    def list_events(self, session_public_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            session_id = self._session_id(connection, session_public_id)
            rows = connection.execute(
                self._event_select_sql()
                + " WHERE e.search_session_id=? ORDER BY e.id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [_event_public(row) for row in rows]

    @staticmethod
    def _event_select_sql() -> str:
        return (
            "SELECT e.*, s.public_id AS search_session_public_id "
            "FROM external_dataset_search_events e "
            "JOIN external_dataset_search_sessions s ON s.id = e.search_session_id"
        )
