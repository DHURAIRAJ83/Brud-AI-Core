"""Secure, preview-first dataset file ingestion and transactional confirmation."""

import csv
import hashlib
import io
import json
import os
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from backend.core.config import Settings
from backend.core.json_utils import JsonValidationError, dumps_json, loads_json
from backend.core.validation import LanguageCode
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.imports import ImportRepository
from backend.models.domain import DatasetRecordType
from backend.models.imports import ImportConfirm, MappingUpdate
from backend.services.dataset_service import content_hash, validate_record
from backend.services.text_normalization import normalize_record_fields

FORMAT_BY_EXTENSION = {".json": "json", ".jsonl": "jsonl", ".csv": "csv", ".txt": "txt"}
JOB_FINAL = {"completed", "completed_with_warnings", "cancelled", "expired"}
PRESETS = {
    "instruction,input,output": {
        "instruction": "instruction",
        "input_text": "input",
        "output_text": "output",
    },
    "question,answer": {"instruction": "question", "output_text": "answer"},
    "tanglish,tamil,response": {
        "input_text": "tanglish",
        "normalized_input": "tamil",
        "output_text": "response",
    },
    "source,target": {"input_text": "source", "output_text": "target"},
    "text": {"output_text": "text"},
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _issue(code: str, message: str, field: str | None = None) -> dict[str, str]:
    issue = {"code": code, "message": message}
    if field:
        issue["field"] = field
    return issue


def _event(
    connection,
    job_id: int,
    event: str,
    previous: str | None = None,
    new: str | None = None,
    message: str | None = None,
    **metadata,
) -> None:
    connection.execute(
        """INSERT INTO dataset_import_events(import_job_id,event_type,previous_status,
        new_status,message,metadata_json) VALUES (?,?,?,?,?,?)""",
        (job_id, event, previous, new, message, dumps_json(metadata)),
    )


def _audit(
    connection, event: str, admin_id: str, job_public_id: str, outcome: str = "success", **metadata
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
            "dataset_import",
            job_public_id,
            outcome,
            dumps_json(metadata),
        ),
    )


def _safe_filename(filename: str) -> str:
    if "\x00" in filename:
        raise ValidationError("filename contains a null byte")
    name = Path(filename.replace("\\", "/")).name.strip()
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:200]
    if not name or name in {".", ".."}:
        raise ValidationError("invalid upload filename")
    return name


def _detect_format(extension: str, prefix: bytes) -> str:
    detected = FORMAT_BY_EXTENSION[extension]
    stripped = prefix.lstrip(b"\xef\xbb\xbf \t\r\n")
    if detected in {"json", "jsonl"} and stripped[:1] not in {b"{", b"["}:
        raise ValidationError("uploaded content does not match the declared JSON format")
    return detected


def _formula_safe(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _exact_hash(values: dict[str, Any]) -> str:
    logical = {
        key: values.get(key)
        for key in (
            "record_type",
            "language",
            "instruction",
            "input_text",
            "output_text",
            "normalized_input",
        )
    }
    return hashlib.sha256(dumps_json(logical).encode()).hexdigest()


class DuplicateKeyError(ValueError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class ImportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ImportRepository(settings.resolved_database_path)

    @property
    def pending_dir(self) -> Path:
        return self.settings.resolved_import_dir / "pending"

    def _artifact(self, stored_filename: str) -> Path:
        path = (self.pending_dir / stored_filename).resolve()
        if not path.is_relative_to(self.pending_dir.resolve()):
            raise ValidationError("invalid registered import artifact")
        return path

    def _public_job(self, row) -> dict[str, Any]:
        value = self.repository.public_job(row)
        status = value["status"]
        value["available_actions"] = {
            "parse": status in {"uploaded", "failed", "preview_ready"},
            "confirm": status == "preview_ready",
            "cancel": status not in JOB_FINAL,
            "report": status not in {"uploaded", "parsing"},
        }
        return value

    def audit_upload_rejection(self, admin_id: str, filename: str | None, reason: str) -> None:
        try:
            safe_name = _safe_filename(filename or "rejected-upload")
        except ValidationError:
            safe_name = "rejected-upload"
        with self.repository.transaction() as connection:
            _audit(
                connection,
                "dataset_import_upload_rejected",
                admin_id,
                str(uuid4()),
                "failure",
                filename=safe_name,
                reason=reason,
            )

    async def receive_upload(
        self,
        upload: UploadFile,
        *,
        record_type: str,
        default_language: str,
        import_mode: str,
        field_mapping: dict[str, str],
        parser_options: dict[str, Any],
        encoding: str,
        admin_id: str,
    ) -> dict[str, Any]:
        original = _safe_filename(upload.filename or "")
        extension = Path(original).suffix.lower()
        if extension not in self.settings.allowed_import_extensions:
            raise ValidationError("unsupported file type")
        mime = (upload.content_type or "application/octet-stream").split(";", 1)[0].lower()
        if mime not in self.settings.allowed_import_mime_types:
            raise ValidationError("unsupported upload MIME type")
        if encoding not in {"utf-8", "utf-8-sig"}:
            raise ValidationError("unsupported encoding")
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        stored = f"{uuid4().hex}{extension}"
        target = self._artifact(stored)
        digest = hashlib.sha256()
        size = 0
        prefix = b""
        try:
            with target.open("xb") as handle:
                os.chmod(target, 0o600)
                while chunk := await upload.read(64 * 1024):
                    size += len(chunk)
                    if size > self.settings.import_max_file_bytes:
                        raise ValidationError("file_too_large")
                    if len(prefix) < 4096:
                        prefix += chunk[: 4096 - len(prefix)]
                    digest.update(chunk)
                    handle.write(chunk)
            if size == 0:
                raise ValidationError("empty files are not allowed")
            detected = _detect_format(extension, prefix)
            prefix.decode(encoding)
        except UnicodeDecodeError as exc:
            target.unlink(missing_ok=True)
            raise ValidationError("encoding_error: upload is not valid UTF text") from exc
        except Exception:
            target.unlink(missing_ok=True)
            raise
        public_id = str(uuid4())
        try:
            with self.repository.transaction() as connection:
                connection.execute(
                    """INSERT INTO dataset_import_jobs(public_id,original_filename,stored_filename,
                    detected_file_type,declared_file_type,file_size_bytes,checksum_sha256,encoding,
                    import_mode,record_type,default_language,field_mapping_json,parser_options_json,
                    created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        public_id,
                        original,
                        stored,
                        detected,
                        extension.removeprefix("."),
                        size,
                        digest.hexdigest(),
                        encoding,
                        import_mode,
                        record_type,
                        default_language,
                        dumps_json(field_mapping),
                        dumps_json(parser_options),
                        admin_id,
                    ),
                )
                row = self.repository.job(connection, public_id)
                _event(
                    connection,
                    row["id"],
                    "upload_received",
                    None,
                    "uploaded",
                    filename=original,
                    file_size_bytes=size,
                    file_type=detected,
                )
                _audit(
                    connection,
                    "dataset_import_upload_received",
                    admin_id,
                    public_id,
                    filename=original,
                    file_size_bytes=size,
                    file_type=detected,
                )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return self.get_job(public_id)

    def get_job(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self._public_job(self.repository.job(connection, public_id))

    def list_jobs(self, **filters) -> dict[str, Any]:
        result = self.repository.list_jobs(**filters)
        result["items"] = [self._with_actions(item) for item in result["items"]]
        return result

    @staticmethod
    def _with_actions(value: dict[str, Any]) -> dict[str, Any]:
        status = value["status"]
        value["available_actions"] = {
            "parse": status in {"uploaded", "failed", "preview_ready"},
            "confirm": status == "preview_ready",
            "cancel": status not in JOB_FINAL,
            "report": status not in {"uploaded", "parsing"},
        }
        return value

    def update_mapping(
        self, public_id: str, update: MappingUpdate, admin_id: str
    ) -> dict[str, Any]:
        changes = update.model_dump(exclude_none=True, mode="json")
        with self.repository.transaction() as connection:
            row = self.repository.job(connection, public_id)
            if row["status"] in JOB_FINAL | {"importing", "confirmed"}:
                raise ConflictError("mapping cannot be changed for this import state")
            mapping = changes.get("field_mapping", loads_json(row["field_mapping_json"]))
            options = changes.get("parser_options", loads_json(row["parser_options_json"]))
            connection.execute(
                """UPDATE dataset_import_jobs SET field_mapping_json=?,parser_options_json=?,
                record_type=?,default_language=?,import_mode=?,status='uploaded',updated_at=?
                WHERE id=?""",
                (
                    dumps_json(mapping),
                    dumps_json(options),
                    changes.get("record_type", row["record_type"]),
                    changes.get("default_language", row["default_language"]),
                    changes.get("import_mode", row["import_mode"]),
                    _now(),
                    row["id"],
                ),
            )
            connection.execute(
                "DELETE FROM dataset_import_rows WHERE import_job_id=?", (row["id"],)
            )
            _event(
                connection,
                row["id"],
                "mapping_changed",
                row["status"],
                "uploaded",
                fields=sorted(changes),
            )
            _audit(
                connection,
                "dataset_import_mapping_changed",
                admin_id,
                public_id,
                fields=sorted(changes),
            )
        return self.get_job(public_id)

    def _decode_file(self, job: dict[str, Any]) -> str:
        path = self._artifact(job["stored_filename"])
        try:
            return path.read_text(encoding=job["encoding"])
        except UnicodeDecodeError as exc:
            raise ValidationError("encoding_error: file is not valid UTF text") from exc
        except OSError as exc:
            raise ValidationError("registered upload artifact is unavailable") from exc

    def _parse_rows(
        self, job: dict[str, Any]
    ) -> tuple[list[tuple[int, Any, list[dict[str, str]]]], int]:
        text = self._decode_file(job)
        kind, options = job["detected_file_type"], job["parser_options"]
        ignored_blanks = 0
        rows: list[tuple[int, Any, list[dict[str, str]]]] = []
        if kind == "json":
            try:
                value = json.loads(text, object_pairs_hook=_unique_object)
            except (json.JSONDecodeError, DuplicateKeyError) as exc:
                raise ValidationError(f"invalid_json: {exc}") from exc
            list_field = options.get("list_field")
            if list_field:
                if not isinstance(value, dict) or not isinstance(value.get(list_field), list):
                    raise ValidationError("selected JSON list field is missing or not a list")
                value = value[list_field]
            if not isinstance(value, list):
                raise ValidationError(
                    "JSON must be an array or use an explicitly selected list field"
                )
            rows = [
                (
                    number,
                    item,
                    []
                    if isinstance(item, dict)
                    else [_issue("invalid_json", "JSON row must be an object")],
                )
                for number, item in enumerate(value, 1)
            ]
        elif kind == "jsonl":
            for number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    ignored_blanks += 1
                    continue
                try:
                    item = json.loads(line, object_pairs_hook=_unique_object)
                    errors = (
                        []
                        if isinstance(item, dict)
                        else [_issue("invalid_json", "JSONL row must be an object")]
                    )
                except (json.JSONDecodeError, DuplicateKeyError) as exc:
                    item, errors = {"line_preview": line[:200]}, [_issue("invalid_json", str(exc))]
                rows.append((number, item, errors))
        elif kind == "csv":
            delimiter_names = {
                "comma": ",",
                "semicolon": ";",
                "tab": "\t",
                ",": ",",
                ";": ";",
                "\t": "\t",
            }
            delimiter = delimiter_names.get(options.get("delimiter", "comma"))
            if delimiter is None:
                raise ValidationError("unsupported CSV delimiter")
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            if not reader.fieldnames or any(not (name or "").strip() for name in reader.fieldnames):
                raise ValidationError("CSV header row is required")
            if len(reader.fieldnames) > self.settings.import_max_columns:
                raise ValidationError("row_too_wide")
            for number, item in enumerate(reader, 2):
                errors = []
                if None in item:
                    errors.append(_issue("row_too_wide", "CSV row has more cells than its header"))
                rows.append(
                    (number, {key: value for key, value in item.items() if key is not None}, errors)
                )
        else:
            mode = options.get("txt_mode", "one_record_per_line")
            if mode == "whole_file_as_pretrain":
                rows = [(1, {"text": text}, [])]
            elif mode == "one_record_per_line":
                for number, line in enumerate(text.splitlines(), 1):
                    if not line.strip():
                        ignored_blanks += 1
                        continue
                    rows.append((number, {"text": line}, []))
            else:
                raise ValidationError("unsupported TXT mode")
        if len(rows) > self.settings.import_max_rows:
            raise ValidationError("row_limit_exceeded")
        return rows, ignored_blanks

    def _map_row(
        self, raw: Any, job: dict[str, Any], initial_errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        errors = list(initial_errors)
        warnings: list[dict[str, str]] = []
        if not isinstance(raw, dict):
            raw = {"value": raw}
        if len(raw) > self.settings.import_max_columns:
            errors.append(_issue("row_too_wide", "Row exceeds the configured column limit"))
        for key, value in raw.items():
            if len(str(value)) > self.settings.import_max_cell_chars:
                errors.append(_issue("cell_too_large", "Cell exceeds the configured length", key))
        mapping = job["field_mapping"]
        if not mapping:
            mapping = PRESETS["text"] if "text" in raw else {}
        values: dict[str, Any] = {
            "record_type": job["record_type"],
            "language": job["default_language"],
            "instruction": None,
            "input_text": None,
            "output_text": None,
            "normalized_input": None,
            "metadata": {},
        }
        for target, source in mapping.items():
            if source not in raw:
                continue
            value = raw[source]
            if target == "metadata":
                if isinstance(value, dict):
                    values["metadata"].update(value)
                else:
                    try:
                        parsed = json.loads(value) if isinstance(value, str) else None
                        if not isinstance(parsed, dict):
                            raise ValueError
                        values["metadata"].update(parsed)
                    except (json.JSONDecodeError, ValueError, TypeError):
                        errors.append(
                            _issue("invalid_metadata", "Mapped metadata must be an object", source)
                        )
            elif target in {"source_language", "target_language"}:
                values["metadata"][target] = value
            else:
                values[target] = value
        try:
            values["record_type"] = DatasetRecordType(values["record_type"]).value
        except (ValueError, TypeError):
            errors.append(_issue("invalid_record_type", "Unsupported record type"))
        try:
            values["language"] = LanguageCode(values["language"]).value
        except (ValueError, TypeError):
            errors.append(_issue("invalid_language", "Unsupported language"))
        for field in ("instruction", "input_text", "output_text", "normalized_input"):
            if values.get(field) is not None and not isinstance(values[field], str):
                errors.append(_issue("invalid_field_type", "Mapped text must be a string", field))
        exact_hash = _exact_hash(values)
        values, normalization_warnings = normalize_record_fields(values)
        warnings.extend(normalization_warnings)
        try:
            dumps_json(values["metadata"], max_bytes=self.settings.max_metadata_bytes)
            validate_record(values)
        except (ValidationError, JsonValidationError, KeyError) as exc:
            errors.append(_issue("missing_required_field", str(exc)))
        digest = None if errors else content_hash(values)
        return {
            "values": values,
            "errors": errors,
            "warnings": warnings,
            "content_hash": digest,
            "exact_hash": exact_hash,
        }

    def parse(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.job(connection, public_id)
            if row["status"] not in {"uploaded", "failed", "preview_ready"}:
                raise ConflictError("import job cannot be parsed in its current state")
            previous = row["status"]
            connection.execute(
                "UPDATE dataset_import_jobs SET status='parsing',updated_at=? WHERE id=?",
                (_now(), row["id"]),
            )
            _event(connection, row["id"], "parse_started", previous, "parsing")
            _audit(connection, "dataset_import_parse_started", admin_id, public_id)
            job = self.repository.internal_job(row)
        try:
            parsed, ignored_blanks = self._parse_rows(job)
            prepared = [
                (number, raw, self._map_row(raw, job, errors)) for number, raw, errors in parsed
            ]
            existing: dict[str, tuple[str, str]] = {}
            hashes = [item[2]["content_hash"] for item in prepared if item[2]["content_hash"]]
            with self.repository.transaction() as connection:
                for offset in range(0, len(hashes), 500):
                    batch = hashes[offset : offset + 500]
                    if batch:
                        marks = ",".join("?" for _ in batch)
                        for match in connection.execute(
                            f"""SELECT content_hash,public_id,record_type,language,instruction,
                            input_text,output_text,normalized_input FROM dataset_records
                            WHERE content_hash IN ({marks})""",
                            batch,
                        ):
                            existing[match[0]] = (
                                match[1],
                                _exact_hash(
                                    {
                                        "record_type": match[2],
                                        "language": match[3],
                                        "instruction": match[4],
                                        "input_text": match[5],
                                        "output_text": match[6],
                                        "normalized_input": match[7],
                                    }
                                ),
                            )
                connection.execute(
                    "DELETE FROM dataset_import_rows WHERE import_job_id=?", (job["id"],)
                )
                seen: dict[str, tuple[str, str]] = {}
                counts = {"valid": 0, "warning": 0, "duplicate": 0, "invalid": 0}
                for number, raw, result in prepared:
                    digest = result["content_hash"]
                    matched = existing.get(digest) if digest else None
                    scope = "existing" if matched else "within_file"
                    if digest and not matched and digest in seen:
                        matched = seen[digest]
                    duplicate_id = matched[0] if matched else None
                    if result["errors"]:
                        status = "invalid"
                    elif duplicate_id:
                        status = "duplicate"
                        kind = "exact" if matched[1] == result["exact_hash"] else "normalized"
                        result["warnings"].append(
                            _issue(f"{kind}_duplicate_{scope}", "Duplicate content detected")
                        )
                    elif result["warnings"]:
                        status = "warning"
                    else:
                        status = "valid"
                    row_public_id = str(uuid4())
                    if digest and digest not in seen:
                        seen[digest] = (row_public_id, result["exact_hash"])
                    counts[status] += 1
                    values = result["values"]
                    connection.execute(
                        """INSERT INTO dataset_import_rows(public_id,import_job_id,row_number,
                        raw_data_json,normalized_data_json,record_type,language,instruction,input_text,
                        output_text,normalized_input,metadata_json,content_hash,row_status,
                        validation_errors_json,validation_warnings_json,duplicate_record_public_id)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            row_public_id,
                            job["id"],
                            number,
                            dumps_json(
                                raw,
                                max_bytes=max(
                                    self.settings.max_metadata_bytes,
                                    self.settings.import_max_cell_chars
                                    * min(len(raw), self.settings.import_max_columns),
                                ),
                            ),
                            dumps_json(values),
                            values["record_type"],
                            values["language"],
                            values.get("instruction"),
                            values.get("input_text"),
                            values.get("output_text"),
                            values.get("normalized_input"),
                            dumps_json(values["metadata"]),
                            digest,
                            status,
                            dumps_json(result["errors"]),
                            dumps_json(result["warnings"]),
                            duplicate_id,
                        ),
                    )
                now = _now()
                connection.execute(
                    """UPDATE dataset_import_jobs SET status='preview_ready',total_rows=?,valid_rows=?,
                    warning_rows=?,duplicate_rows=?,invalid_rows=?,error_code=NULL,error_message=NULL,
                    previewed_at=?,updated_at=? WHERE id=?""",
                    (
                        len(prepared),
                        counts["valid"],
                        counts["warning"],
                        counts["duplicate"],
                        counts["invalid"],
                        now,
                        now,
                        job["id"],
                    ),
                )
                _event(
                    connection,
                    job["id"],
                    "parse_completed",
                    "parsing",
                    "preview_ready",
                    total_rows=len(prepared),
                    ignored_blank_rows=ignored_blanks,
                    **{f"{k}_rows": v for k, v in counts.items()},
                )
                _event(connection, job["id"], "preview_created", "parsing", "preview_ready")
                _audit(
                    connection,
                    "dataset_import_preview_created",
                    admin_id,
                    public_id,
                    total_rows=len(prepared),
                    **counts,
                )
        except Exception as exc:
            with self.repository.transaction() as connection:
                failed = self.repository.job(connection, public_id)
                connection.execute(
                    "UPDATE dataset_import_jobs SET status='failed',error_code=?,error_message=?,updated_at=? WHERE id=?",
                    (type(exc).__name__, str(exc)[:500], _now(), failed["id"]),
                )
                _event(
                    connection,
                    failed["id"],
                    "import_failed",
                    "parsing",
                    "failed",
                    message=str(exc)[:500],
                )
                _audit(
                    connection,
                    "dataset_import_parse_failed",
                    admin_id,
                    public_id,
                    "failure",
                    error=type(exc).__name__,
                )
            if isinstance(exc, (ValidationError, ConflictError)):
                raise
            raise ValidationError(f"import parsing failed: {str(exc)[:300]}") from exc
        return self.get_job(public_id)

    def rows(self, public_id: str, status: str | None, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            job_id = job["id"]
        result = self.repository.list_rows(job_id, status, page, page_size)
        for item in result["items"]:
            item["raw_data"] = _truncate_json(item["raw_data"])
            item["normalized_data"] = _truncate_json(item["normalized_data"])
        return result

    def confirm(self, public_id: str, payload: ImportConfirm, admin_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self.repository.transaction() as connection:
            preflight = self.repository.internal_job(self.repository.job(connection, public_id))
        if preflight["status"] == "preview_ready":
            previewed = datetime.fromisoformat(preflight["previewed_at"])
            if previewed + timedelta(minutes=self.settings.import_preview_ttl_minutes) <= now:
                with self.repository.transaction() as connection:
                    connection.execute(
                        "UPDATE dataset_import_jobs SET status='expired',updated_at=? WHERE id=?",
                        (_now(), preflight["id"]),
                    )
                    _event(
                        connection,
                        preflight["id"],
                        "job_expired",
                        "preview_ready",
                        "expired",
                    )
                raise ConflictError("import preview has expired")
        with self.repository.transaction() as connection:
            job_row = self.repository.job(connection, public_id)
            job = self.repository.internal_job(job_row)
            if job["status"] in {"completed", "completed_with_warnings"}:
                return self._public_job(job_row)
            if job["status"] != "preview_ready":
                raise ConflictError("only a preview-ready import can be confirmed")
            if job["import_mode"] == "create_only" and job["duplicate_rows"]:
                raise ConflictError("create_only imports cannot be confirmed with duplicate rows")
            rows = connection.execute(
                "SELECT * FROM dataset_import_rows WHERE import_job_id=? ORDER BY row_number",
                (job["id"],),
            ).fetchall()
            connection.execute(
                "UPDATE dataset_import_jobs SET status='importing',confirmed_at=?,updated_at=? WHERE id=?",
                (_now(), _now(), job["id"]),
            )
            _event(connection, job["id"], "confirmation_received", "preview_ready", "confirmed")
            _event(connection, job["id"], "import_started", "confirmed", "importing")
            _audit(
                connection,
                "dataset_import_confirmation_received",
                admin_id,
                public_id,
                eligible_rows=job["valid_rows"]
                + (job["warning_rows"] if payload.include_warnings else 0),
            )
            source_id = None
            source_public_id = job["source_public_id"]
            if source_public_id:
                source = connection.execute(
                    "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
                ).fetchone()
                if not source:
                    raise ValidationError("configured dataset source no longer exists")
                source_id = source[0]
            else:
                source_public_id = str(uuid4())
                source_type = (
                    "text" if job["detected_file_type"] == "txt" else job["detected_file_type"]
                )
                connection.execute(
                    """INSERT INTO dataset_sources(name,source_type,status,public_id,original_filename,
                    language,licence_status,checksum_sha256,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        Path(job["original_filename"]).stem[:255],
                        source_type,
                        "ready",
                        source_public_id,
                        job["original_filename"],
                        job["default_language"],
                        "review_required",
                        job["checksum_sha256"],
                        dumps_json({"import_job_public_id": public_id}),
                    ),
                )
                source_id = connection.execute(
                    "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
                ).fetchone()[0]
            imported = failed = skipped = 0
            for row in rows:
                if row["row_status"] == "duplicate":
                    connection.execute(
                        "UPDATE dataset_import_rows SET row_status='skipped',updated_at=? WHERE id=?",
                        (_now(), row["id"]),
                    )
                    _event(
                        connection,
                        job["id"],
                        "row_skipped",
                        row_number=row["row_number"],
                        reason="duplicate",
                    )
                    skipped += 1
                    continue
                if row["row_status"] == "invalid" or (
                    row["row_status"] == "warning" and not payload.include_warnings
                ):
                    continue
                if row["row_status"] not in {"valid", "warning"}:
                    continue
                duplicate = connection.execute(
                    "SELECT public_id FROM dataset_records WHERE content_hash=?",
                    (row["content_hash"],),
                ).fetchone()
                if duplicate:
                    if job["import_mode"] == "create_only":
                        raise ConflictError("duplicate appeared after preview; import cancelled")
                    connection.execute(
                        "UPDATE dataset_import_rows SET row_status='skipped',duplicate_record_public_id=?,updated_at=? WHERE id=?",
                        (duplicate[0], _now(), row["id"]),
                    )
                    _event(
                        connection,
                        job["id"],
                        "row_skipped",
                        row_number=row["row_number"],
                        reason="duplicate_recheck",
                    )
                    skipped += 1
                    continue
                record_id = str(uuid4())
                legacy = row["output_text"] or row["input_text"] or row["instruction"] or ""
                connection.execute(
                    """INSERT INTO dataset_records(source_id,content,language,status,public_id,
                    record_type,instruction,input_text,output_text,normalized_input,content_hash,
                    metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        source_id,
                        legacy,
                        row["language"],
                        "draft",
                        record_id,
                        row["record_type"],
                        row["instruction"],
                        row["input_text"],
                        row["output_text"],
                        row["normalized_input"],
                        row["content_hash"],
                        row["metadata_json"],
                    ),
                )
                connection.execute(
                    "UPDATE dataset_import_rows SET row_status='imported',imported_record_public_id=?,updated_at=? WHERE id=?",
                    (record_id, _now(), row["id"]),
                )
                _event(
                    connection,
                    job["id"],
                    "row_imported",
                    row_number=row["row_number"],
                    record_public_id=record_id,
                )
                imported += 1
            final = (
                "completed_with_warnings"
                if job["warning_rows"] or job["invalid_rows"] or skipped or failed
                else "completed"
            )
            connection.execute(
                """UPDATE dataset_import_jobs SET source_public_id=?,status=?,imported_rows=?,
                failed_rows=?,completed_at=?,updated_at=? WHERE id=?""",
                (source_public_id, final, imported, failed, _now(), _now(), job["id"]),
            )
            _event(
                connection,
                job["id"],
                "import_completed",
                "importing",
                final,
                imported_rows=imported,
                skipped_rows=skipped,
                failed_rows=failed,
            )
            _audit(
                connection,
                "dataset_import_completed",
                admin_id,
                public_id,
                imported_rows=imported,
                skipped_rows=skipped,
                failed_rows=failed,
            )
        self._move_artifact(job["stored_filename"], "processed")
        return self.get_job(public_id)

    def cancel(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.job(connection, public_id)
            if row["status"] in JOB_FINAL | {"importing"}:
                raise ConflictError("import job cannot be cancelled in its current state")
            previous = row["status"]
            connection.execute(
                "UPDATE dataset_import_jobs SET status='cancelled',cancelled_at=?,updated_at=? WHERE id=?",
                (_now(), _now(), row["id"]),
            )
            _event(connection, row["id"], "job_cancelled", previous, "cancelled")
            _audit(connection, "dataset_import_cancelled", admin_id, public_id)
            stored = row["stored_filename"]
        self._move_artifact(stored, "quarantine")
        return self.get_job(public_id)

    def _move_artifact(self, stored: str, destination: str) -> None:
        source = self._artifact(stored)
        if source.exists():
            target_dir = self.settings.resolved_import_dir / destination
            target_dir.mkdir(parents=True, exist_ok=True)
            target = (target_dir / stored).resolve()
            if not target.is_relative_to(target_dir.resolve()):
                raise ValidationError("invalid import artifact destination")
            if not target.exists():
                shutil.move(source, target)

    def events(self, public_id: str) -> list[dict[str, Any]]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            job_id = job["id"]
        return self.repository.events(job_id)

    def report_csv(self, public_id: str, admin_id: str) -> str:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            rows = connection.execute(
                """SELECT row_number,row_status,validation_errors_json,validation_warnings_json,
                duplicate_record_public_id,imported_record_public_id FROM dataset_import_rows
                WHERE import_job_id=? AND (row_status IN ('duplicate','invalid','skipped','failed')
                OR validation_errors_json<>'[]' OR validation_warnings_json<>'[]')
                ORDER BY row_number LIMIT ?""",
                (job["id"], self.settings.import_max_error_report_rows),
            ).fetchall()
            _audit(
                connection,
                "dataset_import_report_downloaded",
                admin_id,
                public_id,
                reported_rows=len(rows),
            )
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "row_number",
                "status",
                "errors",
                "warnings",
                "duplicate_record_public_id",
                "imported_record_public_id",
            ]
        )
        for row in rows:
            writer.writerow([_formula_safe(value) for value in row])
        return output.getvalue()

    def expire_old(self, *, confirm: bool) -> int:
        if not confirm:
            raise ValidationError("expiry confirmation required")
        cutoff = datetime.now(UTC) - timedelta(minutes=self.settings.import_preview_ttl_minutes)
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM dataset_import_jobs WHERE status='preview_ready' AND previewed_at<?",
                (cutoff.isoformat(),),
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE dataset_import_jobs SET status='expired',updated_at=? WHERE id=?",
                    (_now(), row["id"]),
                )
                _event(connection, row["id"], "job_expired", "preview_ready", "expired")
        return len(rows)


def _truncate_json(value: Any, limit: int = 500) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, dict):
        return {key: _truncate_json(item, limit) for key, item in value.items()}
    if isinstance(value, list):
        return [_truncate_json(item, limit) for item in value[:50]]
    return value
