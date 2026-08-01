"""Bridges an approved, exported document SFT JSONL export into the
existing generic dataset-record and dataset-versioning systems.

This is a thin orchestration layer only: it never reimplements dataset
duplicate detection (`DatasetService.create_record` + `DatasetAdminRepository
.duplicate()`, unchanged), dataset-version building, or split/leakage logic
(`DatasetVersioningService`, unchanged). Its only new responsibility is
(a) preserving document-SFT-specific lineage that the generic
`dataset_records` schema has no columns for -- stored in that table's
existing `metadata_json` extension point -- and (b) idempotency tracking
so the same export is never imported twice.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.validation import LanguageCode
from backend.database.repositories.base import ConflictError, NotFoundError, ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.database.repositories.documents import DocumentRepository
from backend.models.dataset_versions import BuildCreate, BuildRunRequest, SplitConfiguration
from backend.models.datasets import RecordCreate
from backend.models.domain import DatasetRecordType, DatasetSourceType, LicenceStatus
from backend.services.dataset_service import DatasetService
from backend.services.dataset_versioning import DatasetVersioningService
from backend.services.document_sft_export_service import DocumentSftExportService

_TASK_TO_RECORD_TYPE: dict[str, str] = {
    "definition": "instruction",
    "explanation": "instruction",
    "grammar": "instruction",
    "fact_answer": "instruction",
    "instruction_following": "instruction",
    "summarization": "instruction",
    "spelling_correction": "instruction",
    "grammar_correction": "instruction",
    "basic_math_reasoning": "instruction",
    "Tamil_to_English": "translation",
    "English_to_Tamil": "translation",
    "Tanglish_input_to_Tamil": "tanglish_pair",
    "safety_response": "safety",
}

_LANGUAGE_ALIASES = {"tamil": "ta", "english": "en", "tanglish": "tgl"}


_VALID_LANGUAGE_CODES = {v.value for v in LanguageCode}


def _to_language_code(value: str | None) -> str:
    if not value:
        return LanguageCode.UNKNOWN.value
    normalized = _LANGUAGE_ALIASES.get(value.lower(), value.lower())
    return normalized if normalized in _VALID_LANGUAGE_CODES else LanguageCode.UNKNOWN.value


class DocumentSftDatasetHandoffService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)
        self.dataset_admin_repository = DatasetAdminRepository(settings.resolved_database_path)
        self.dataset_service = DatasetService(self.dataset_admin_repository)
        self.dataset_quality_repository = DatasetQualityRepository(settings.resolved_database_path)
        self.dataset_versioning = DatasetVersioningService(
            self.dataset_quality_repository, settings
        )
        self.export_service = DocumentSftExportService(settings)

    def _read_export_records(self, export: dict[str, Any]) -> list[dict[str, Any]]:
        path = self.settings.resolved_document_sft_export_dir / export["export_path"]
        if not path.is_file():
            raise NotFoundError("document sft export file not found on disk")
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        return [json.loads(line) for line in lines if line.strip()]

    def _find_candidate(self, connection, candidate_public_id: str) -> Any:
        return connection.execute(
            "SELECT * FROM document_sft_candidates WHERE public_id=?", (candidate_public_id,)
        ).fetchone()

    def _existing_handoff_row(self, connection, export_public_id: str) -> Any:
        return connection.execute(
            "SELECT * FROM document_sft_dataset_handoffs WHERE export_public_id=?",
            (export_public_id,),
        ).fetchone()

    def preview(self, export_public_id: str) -> dict[str, Any]:
        export = self.export_service.get_export(export_public_id)
        records = self._read_export_records(export)
        if len(records) > self.settings.document_sft_handoff_max_records:
            raise ValidationError(
                "this export exceeds the configured handoff batch limit "
                f"({self.settings.document_sft_handoff_max_records} records) -- "
                "split the export before handing it off"
            )
        with self.repository.transaction() as connection:
            existing = self._existing_handoff_row(connection, export_public_id)
            eligible, duplicates, lineage_missing = 0, 0, 0
            for record in records:
                candidate = self._find_candidate(connection, record["source_id"])
                if candidate is None:
                    lineage_missing += 1
                    continue
                digest = self._content_digest(record)
                if self.dataset_admin_repository.duplicate(connection, digest):
                    duplicates += 1
                else:
                    eligible += 1
        return {
            "export_public_id": export_public_id,
            "record_count": len(records),
            "eligible_count": eligible,
            "duplicate_count": duplicates,
            "lineage_missing_count": lineage_missing,
            "task_distribution": export["task_distribution"],
            "language_distribution": export["language_distribution"],
            "domain_distribution": export["domain_distribution"],
            "already_ingested": existing is not None,
            "existing_handoff_status": existing["status"] if existing else None,
        }

    @staticmethod
    def _content_digest(record: dict[str, Any]) -> str:
        from backend.services.dataset_service import content_hash

        return content_hash(
            {
                "record_type": _TASK_TO_RECORD_TYPE.get(record["task"], "instruction"),
                "language": _to_language_code(record.get("input_language")),
                "instruction": record.get("instruction"),
                "input_text": None,
                "output_text": record.get("response"),
                "normalized_input": None,
            }
        )

    def _record_create_payload(self, record: dict[str, Any], candidate) -> tuple[RecordCreate, str]:
        record_type = _TASK_TO_RECORD_TYPE.get(record["task"], "instruction")
        input_language = _to_language_code(record.get("input_language"))
        output_language = _to_language_code(record.get("output_language"))
        lineage = {
            "document_sft_candidate_id": record["source_id"],
            "document_sft_export_id": record.get("_export_public_id"),
            "source_document_id": candidate["document_source_id"],
            "source_chunk_id": candidate["source_chunk_id"],
            "source_page_start": candidate["source_page_start"],
            "source_page_end": candidate["source_page_end"],
            "rights_status": record.get("rights_status"),
            "task": record["task"],
            "domain": record.get("domain"),
            "input_language": input_language,
            "output_language": output_language,
            "generation_method": candidate["generation_method"],
            "quality_status": candidate["quality_status"],
        }
        if record_type == "translation":
            payload = RecordCreate(
                source_public_id="",  # filled by caller
                record_type=DatasetRecordType(record_type),
                language=LanguageCode(input_language),
                input_text=record.get("instruction"),
                output_text=record.get("response"),
                metadata={
                    **lineage,
                    "source_language": input_language,
                    "target_language": output_language,
                },
            )
        elif record_type == "tanglish_pair":
            payload = RecordCreate(
                source_public_id="",
                record_type=DatasetRecordType(record_type),
                language=LanguageCode(input_language),
                input_text=record.get("instruction"),
                normalized_input=record.get("response"),
                output_text=record.get("response"),
                metadata=lineage,
            )
        elif record_type == "safety":
            payload = RecordCreate(
                source_public_id="",
                record_type=DatasetRecordType(record_type),
                language=LanguageCode(input_language),
                input_text=record.get("instruction"),
                output_text=record.get("response"),
                metadata=lineage,
            )
        else:
            payload = RecordCreate(
                source_public_id="",
                record_type=DatasetRecordType.INSTRUCTION,
                language=LanguageCode(input_language),
                instruction=record.get("instruction"),
                output_text=record.get("response"),
                metadata=lineage,
            )
        return payload, record_type

    def ingest(self, export_public_id: str, admin_id: str) -> dict[str, Any]:
        export = self.export_service.get_export(export_public_id)
        with self.repository.transaction() as connection:
            existing = self._existing_handoff_row(connection, export_public_id)
        if existing is not None:
            if existing["export_checksum_sha256"] != export["checksum_sha256"]:
                raise ConflictError(
                    "the export's checksum has changed since it was last handed off -- "
                    "integrity conflict"
                )
            return self.get_handoff(existing["public_id"])

        records = self._read_export_records(export)
        if not records:
            raise ValidationError("export has no records to ingest")
        if len(records) > self.settings.document_sft_handoff_max_records:
            raise ValidationError(
                "this export exceeds the configured handoff batch limit "
                f"({self.settings.document_sft_handoff_max_records} records) -- "
                "split the export before handing it off"
            )

        # `DatasetService.create_source` deliberately only accepts
        # source_type=manual (it is the manual-entry admin API) -- this
        # handoff is a system-generated source, so it goes through the
        # repository directly, the same layer that service composes.
        with self.dataset_admin_repository.transaction() as connection:
            source_public_id = self.dataset_admin_repository.create_source(
                connection,
                {
                    "name": f"Document SFT export {export_public_id}",
                    "language": LanguageCode.MIXED.value,
                    "licence_status": LicenceStatus.APPROVED.value,
                    "licence_name": None,
                    "source_type": DatasetSourceType.GENERATED.value,
                    "status": "ready",
                    "metadata": {
                        "document_sft_export_public_id": export_public_id,
                        "checksum_sha256": export["checksum_sha256"],
                    },
                },
            )
            source_row = self.dataset_admin_repository.source_by_public_id(
                connection, source_public_id
            )
            source = dict(source_row)

        imported = duplicates = skipped = 0
        for record in records:
            record["_export_public_id"] = export_public_id
            with self.repository.transaction() as connection:
                candidate = self._find_candidate(connection, record["source_id"])
            if candidate is None:
                skipped += 1
                continue
            payload, _record_type = self._record_create_payload(record, candidate)
            payload = payload.model_copy(update={"source_public_id": source["public_id"]})
            try:
                created = self.dataset_service.create_record(payload, admin_id)
            except ConflictError:
                duplicates += 1
                continue
            except ValidationError:
                skipped += 1
                continue
            with self.dataset_admin_repository.transaction() as connection:
                connection.execute(
                    "UPDATE dataset_records SET status='approved' WHERE public_id=?",
                    (created["public_id"],),
                )
            imported += 1

        handoff_public_id = str(uuid4())
        with self.repository.transaction() as connection:
            connection.execute(
                """INSERT INTO document_sft_dataset_handoffs(
                    public_id,export_public_id,export_checksum_sha256,dataset_source_public_id,
                    imported_count,skipped_count,duplicate_count,rights_blocked_count,
                    security_blocked_count,status,created_by
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    handoff_public_id,
                    export_public_id,
                    export["checksum_sha256"],
                    source["public_id"],
                    imported,
                    skipped,
                    duplicates,
                    0,
                    0,
                    "imported",
                    admin_id,
                ),
            )
        return self.get_handoff(handoff_public_id)

    def get_handoff(self, handoff_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM document_sft_dataset_handoffs WHERE public_id=?",
                (handoff_public_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("document sft dataset handoff not found")
        return dict(row)

    def list_handoffs_for_document(self, document_public_id: str) -> dict[str, Any]:
        exports = self.export_service.list_exports(document_public_id)["items"]
        items = []
        with self.repository.transaction() as connection:
            for export in exports:
                row = self._existing_handoff_row(connection, export["public_id"])
                if row is not None:
                    items.append(dict(row))
        return {"items": items, "total": len(items)}

    def get_handoff_by_export(self, export_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self._existing_handoff_row(connection, export_public_id)
        if row is None:
            raise NotFoundError("no handoff has been recorded for this export yet")
        return dict(row)

    def propose_dataset_version(
        self, handoff_public_id: str, dataset_name: str, dataset_version: str, admin_id: str
    ) -> dict[str, Any]:
        handoff = self.get_handoff(handoff_public_id)
        build = self.dataset_versioning.create_build(
            BuildCreate(
                dataset_name=dataset_name,
                dataset_version=dataset_version,
                description=f"Document SFT handoff {handoff_public_id}",
                selection_filters={"source_public_id": handoff["dataset_source_public_id"]},
                split_configuration=SplitConfiguration(),
            ),
            admin_id,
        )
        with self.repository.transaction() as connection:
            connection.execute(
                "UPDATE document_sft_dataset_handoffs SET dataset_version_public_id=?,"
                "dataset_build_public_id=?,status='version_proposed',updated_at=CURRENT_TIMESTAMP "
                "WHERE public_id=?",
                (build["dataset_version_public_id"], build["public_id"], handoff_public_id),
            )
        return self.get_handoff(handoff_public_id)

    def preview_split(self, build_public_id: str, admin_id: str) -> dict[str, Any]:
        return self.dataset_versioning.validate_build(build_public_id, admin_id)

    def confirm_build(self, build_public_id: str, admin_id: str) -> dict[str, Any]:
        result = self.dataset_versioning.run_build(
            build_public_id, BuildRunRequest(confirm=True), admin_id
        )
        with self.repository.transaction() as connection:
            connection.execute(
                "UPDATE document_sft_dataset_handoffs SET status='version_built',"
                "confirmed_by=?,updated_at=CURRENT_TIMESTAMP WHERE dataset_build_public_id=?",
                (admin_id, build_public_id),
            )
        return result
