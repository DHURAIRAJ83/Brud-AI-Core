"""Bridge from an approved Manual Data Studio record into the existing
dataset pipeline (Phase 3, Step 17).

Mirrors ``feedback_dataset_service.export_candidate()`` exactly in
shape: reads and validates the manual record in its own transaction,
then calls ``DatasetService.create_record()`` directly as a separate,
self-committing call against a different repository (never nested
inside this service's own open transaction, which would leave the new
row invisible to the other repository's connection until commit), and
only afterwards marks the manual record as exported in a final
transaction. This never writes to ``dataset_records`` directly and
never builds a second, competing versioning pipeline.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.manual_data import ManualDataRepository, public_row
from backend.models.datasets import RecordCreate
from backend.services.dataset_service import DatasetService
from core_model.manual_data import DATASET_RECORD_TYPE_MAP


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
            "manual_data_record",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


def _content_for_export(record_type: str, revision: dict[str, Any]) -> dict[str, Any]:
    if record_type in ("plain_text", "language_example", "grammar_example"):
        text = (
            revision.get("tamil_text")
            or revision.get("english_text")
            or revision.get("tanglish_text")
        )
        return {"input_text": revision.get("input_text") or text}
    if record_type == "conversation":
        turns = (revision.get("metadata") or {}).get("turns", [])
        transcript = "\n".join(f"{turn.get('role')}: {turn.get('content')}" for turn in turns)
        return {"input_text": transcript}
    if record_type == "question_answer":
        return {
            "instruction": revision.get("question_text"),
            "output_text": revision.get("answer_text"),
        }
    if record_type == "instruction_response":
        return {
            "instruction": revision.get("instruction_text"),
            "output_text": revision.get("response_text"),
        }
    if record_type == "translation_pair":
        return {
            "input_text": revision.get("input_text"),
            "output_text": revision.get("output_text"),
        }
    if record_type == "tanglish_normalization":
        return {
            "input_text": revision.get("tanglish_text"),
            "normalized_input": revision.get("tamil_text"),
            "output_text": revision.get("english_text"),
        }
    if record_type == "dictionary_entry":
        meanings = "; ".join(revision.get("meanings") or [])
        return {"input_text": revision.get("word"), "output_text": meanings}
    if record_type == "knowledge_note":
        return {"input_text": revision.get("title"), "output_text": revision.get("input_text")}
    return {}


class ManualDataCandidateService:
    def __init__(
        self,
        repository: ManualDataRepository,
        dataset_service: DatasetService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.dataset_service = dataset_service
        self.settings = settings

    def create_candidate(self, public_id: str, admin_id: str, notes: str = "") -> dict[str, Any]:
        # Additive Phase 6 preflight guard (Step 20): only blocks when a
        # governance review item/duplicate/conflict group actually exists
        # and is unresolved for this record -- an approved record with no
        # governance activity at all is never blocked by this addition.
        from backend.services.governance_service import GovernanceExportReadinessService

        GovernanceExportReadinessService(self.settings).require_allowed(
            "manual_data_record", public_id, "dataset_export"
        )
        with self.repository.transaction() as connection:
            record = dict(self.repository.record(connection, public_id))
            if record["status"] != "approved":
                raise ValidationError(
                    "only an approved manual data record may become a dataset candidate"
                )
            if record["exported_dataset_record_public_id"]:
                raise ConflictError(
                    "this record was already exported as dataset record "
                    f"{record['exported_dataset_record_public_id']}"
                )
            record_type = record["record_type"]
            if record_type not in DATASET_RECORD_TYPE_MAP:
                raise ValidationError(
                    f"{record_type!r} records are evaluation evidence and must never be "
                    "exported into the training dataset pipeline"
                )
            if not record["active_revision_id"]:
                raise ValidationError("record has no active revision to export")
            revision = public_row(
                self.repository.revision_by_id(connection, record["active_revision_id"])
            )

        source_public_id = self._find_or_create_manual_source(record["primary_language"])
        dataset_record_type = DATASET_RECORD_TYPE_MAP[record_type]
        language = record["primary_language"] if record["primary_language"] != "unknown" else "en"
        content = _content_for_export(record_type, revision)
        metadata: dict[str, Any] = {
            "manual_data_record_public_id": public_id,
            "manual_data_revision_public_id": revision["public_id"],
        }
        if (
            dataset_record_type == "translation"
            and record.get("input_language")
            and record.get("output_language")
        ):
            metadata["source_language"] = record["input_language"]
            metadata["target_language"] = record["output_language"]

        dataset_record = self.dataset_service.create_record(
            RecordCreate(
                source_public_id=source_public_id,
                record_type=dataset_record_type,
                language=language,
                metadata=metadata,
                **content,
            ),
            admin_id,
        )

        with self.repository.transaction() as connection:
            record_row = self.repository.record(connection, public_id)
            self.repository.update_record(
                connection,
                record_row["id"],
                {"exported_dataset_record_public_id": dataset_record["public_id"]},
            )
            self.repository.add_event(
                connection,
                {
                    "record_id": record_row["id"],
                    "event_type": "dataset_candidate_created",
                    "performed_by_admin_public_id": admin_id,
                    "notes": notes,
                    "metadata_json": dumps_json(
                        {"dataset_record_public_id": dataset_record["public_id"]}
                    ),
                },
            )
            _audit(
                connection,
                "manual_data_candidate_created",
                admin_id,
                public_id,
                dataset_record_public_id=dataset_record["public_id"],
            )
            return public_row(self.repository.record(connection, public_id))

    def _find_or_create_manual_source(self, language: str) -> str:
        with self.dataset_service.repository.transaction() as connection:
            existing = connection.execute(
                "SELECT public_id FROM dataset_sources WHERE source_type='manual' "
                "AND name='Manual Data Studio' LIMIT 1"
            ).fetchone()
            if existing:
                return existing["public_id"]
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO dataset_sources(name,source_type,status,public_id,language,
                licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
                (
                    "Manual Data Studio",
                    "manual",
                    "ready",
                    public_id,
                    language if language != "unknown" else "en",
                    "unknown",
                    dumps_json({}),
                ),
            )
            return public_id


__all__ = ["ManualDataCandidateService"]
