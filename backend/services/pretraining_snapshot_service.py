"""Phase 21A immutable pretraining dataset snapshot. Freezes one
finalized/exported Phase 20 corpus release, materialized via
`pretraining_bridge.materialize_corpus_release`, together with the
release's own manifest/export checksums and the assigned tokenizer's
artifact checksum. Never overwrites a prior snapshot -- new content
always produces a new snapshot row."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.pretraining_readiness import (
    PretrainingReadinessRepository,
    public_row,
)
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.pretraining_readiness import PretrainingSnapshotCreate
from backend.services.pretraining_bridge import materialize_corpus_release
from backend.services.tokenizer_registry import TokenizerService


class PretrainingSnapshotService:
    def __init__(
        self,
        corpus_repository: CorpusRepository,
        readiness_repository: PretrainingReadinessRepository,
        settings: Settings,
    ) -> None:
        self.corpus_repository = corpus_repository
        self.readiness_repository = readiness_repository
        self.settings = settings
        self.tokenizer_service = TokenizerService(
            TokenizerRepository(settings.resolved_database_path), settings
        )

    def create_snapshot(self, payload: PretrainingSnapshotCreate, admin_id: str) -> dict[str, Any]:
        with self.corpus_repository.transaction() as connection:
            release_row = self.corpus_repository.release(
                connection, payload.corpus_release_public_id
            )
            if release_row["status"] not in ("finalized", "exported"):
                raise ValidationError(
                    "corpus release must be finalized or exported before a snapshot is frozen"
                )
            if not release_row["manifest_checksum_sha256"]:
                raise ValidationError("corpus release has no manifest checksum")
            export_checksums: list[str] = []
            if release_row["export_id"] is not None:
                shards = self.corpus_repository.shards_for_export(
                    connection, release_row["export_id"]
                )
                export_checksums = [shard["checksum_sha256"] for shard in shards]

            tokenizer_row = connection.execute(
                "SELECT * FROM tokenizer_versions WHERE public_id=?",
                (payload.tokenizer_version_public_id,),
            ).fetchone()
            if tokenizer_row is None or not tokenizer_row["model_checksum_sha256"]:
                raise ValidationError(
                    "tokenizer version must exist and have a verified artifact checksum"
                )

            materialized = materialize_corpus_release(
                connection, release_row, name_prefix="Phase21A Pretraining Snapshot"
            )

        processor = self.tokenizer_service.processor_for_version(
            payload.tokenizer_version_public_id
        )
        token_counts = {"train": 0, "validation": 0, "test": 0}
        with self.corpus_repository.transaction() as connection:
            items = connection.execute(
                """SELECT r.content, i.split FROM dataset_version_items i
                JOIN dataset_records r ON r.id = i.dataset_record_id
                WHERE i.dataset_version_id=?""",
                (materialized["dataset_version_id"],),
            ).fetchall()
        for item in items:
            token_counts[item["split"]] += len(processor.encode(item["content"], out_type=int))

        with self.readiness_repository.transaction() as connection:
            public_id = self.readiness_repository.create_pretraining_dataset_snapshot(
                connection,
                {
                    "corpus_release_id": release_row["id"],
                    "dataset_version_id": materialized["dataset_version_id"],
                    "tokenizer_version_id": tokenizer_row["id"],
                    "manifest_checksum_sha256": release_row["manifest_checksum_sha256"],
                    "export_checksums_json": dumps_json(export_checksums),
                    "tokenizer_checksum_sha256": tokenizer_row["model_checksum_sha256"],
                    "train_record_count": materialized["train_record_count"],
                    "validation_record_count": materialized["validation_record_count"],
                    "test_record_count": materialized["test_record_count"],
                    "train_token_count": token_counts["train"],
                    "validation_token_count": token_counts["validation"],
                    "test_token_count": token_counts["test"],
                    "maximum_sequence_length": payload.maximum_sequence_length,
                    "deterministic_seed": payload.deterministic_seed,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "pretraining_dataset_snapshot_created", admin_id, public_id,
                train_records=materialized["train_record_count"],
                validation_records=materialized["validation_record_count"],
                test_records=materialized["test_record_count"],
            )
            return public_row(
                self.readiness_repository.pretraining_dataset_snapshot(connection, public_id)
            )

    def get_snapshot(self, public_id: str) -> dict[str, Any]:
        with self.readiness_repository.transaction() as connection:
            return public_row(
                self.readiness_repository.pretraining_dataset_snapshot(connection, public_id)
            )

    def list_snapshots(self) -> dict[str, Any]:
        with self.readiness_repository.transaction() as connection:
            return {
                "items": [
                    public_row(row)
                    for row in self.readiness_repository.list_pretraining_dataset_snapshots(
                        connection
                    )
                ]
            }

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "pretraining_readiness", resource_id, "success", dumps_json(metadata),
            ),
        )
