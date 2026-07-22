"""Typed Phase 2 repositories with explicit SQL and lifecycle validation."""

import hashlib
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json, redact_secrets
from backend.models.domain import (
    AdminApprovalCreate,
    AdminApprovalPublic,
    AuditEventCreate,
    AuditEventPublic,
    DatasetRecordCreate,
    DatasetRecordPublic,
    DatasetReviewCreate,
    DatasetReviewPublic,
    DatasetSourceCreate,
    DatasetSourcePublic,
    DatasetVersionCreate,
    DatasetVersionPublic,
    DatasetVersionStatus,
    ModelAssignmentCreate,
    ModelAssignmentPublic,
    ModelLifecycleStatus,
    ModelRegistryCreate,
    ModelRegistryPublic,
    ModelVersionCreate,
    ModelVersionPublic,
    TrainingJobCreate,
    TrainingJobPublic,
    TrainingStatus,
    UserFeedbackCreate,
    UserFeedbackPublic,
)

from .base import BaseRepository, ConflictError, NotFoundError, ValidationError


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _source_public(row: sqlite3.Row) -> DatasetSourcePublic:
    return DatasetSourcePublic(
        public_id=row["public_id"],
        name=row["name"],
        source_type=row["source_type"],
        original_filename=row["original_filename"],
        source_uri=row["source_uri"],
        language=row["language"],
        licence_name=row["licence_name"],
        licence_status=row["licence_status"],
        checksum_sha256=row["checksum_sha256"],
        status=row["status"],
        metadata=loads_json(row["metadata_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SettingsRepository(BaseRepository):
    VALID_TYPES = {"string", "boolean", "integer", "float", "json"}

    def set(
        self,
        key: str,
        value: Any,
        *,
        value_type: str = "string",
        is_secret: bool = False,
        description: str | None = None,
    ) -> None:
        if value_type not in self.VALID_TYPES:
            raise ValidationError("unsupported setting value type")
        serialized = self._serialize(value, value_type)
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO app_settings(key,value,value_type,is_secret,description,updated_at)
                VALUES (?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                value_type=excluded.value_type,is_secret=excluded.is_secret,
                description=excluded.description,updated_at=excluded.updated_at""",
                (key, serialized, value_type, int(is_secret), description, _now()),
            )

    @staticmethod
    def _serialize(value: Any, value_type: str) -> str:
        try:
            if value_type == "boolean":
                if not isinstance(value, bool):
                    raise ValueError
                return "true" if value else "false"
            if value_type == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError
                return str(value)
            if value_type == "float":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError
                return str(float(value))
            if value_type == "json":
                return dumps_json(value)
            if not isinstance(value, str):
                raise ValueError
            return value
        except ValueError as exc:
            raise ValidationError(f"value does not match setting type {value_type}") from exc

    def get_safe(self, key: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT key,value,value_type,is_secret,description,updated_at "
                "FROM app_settings WHERE key=?",
                (key,),
            ).fetchone()
        if not row:
            raise NotFoundError("setting not found")
        return {
            "key": row["key"],
            "value": "[REDACTED]" if row["is_secret"] else row["value"],
            "value_type": row["value_type"],
            "is_secret": bool(row["is_secret"]),
            "description": row["description"],
            "updated_at": row["updated_at"],
        }


class DatasetSourceRepository(BaseRepository):
    def create(self, item: DatasetSourceCreate) -> DatasetSourcePublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO dataset_sources(name,source_type,status,public_id,original_filename,
                source_uri,language,licence_name,licence_status,checksum_sha256,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item.name,
                    item.source_type.value,
                    item.status.value,
                    public_id,
                    item.original_filename,
                    item.source_uri,
                    item.language.value,
                    item.licence_name,
                    item.licence_status.value,
                    item.checksum_sha256,
                    dumps_json(item.metadata),
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> DatasetSourcePublic:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM dataset_sources WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("dataset source not found")
        return _source_public(row)

    def list(self, *, limit: int = 50, offset: int = 0) -> list[DatasetSourcePublic]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM dataset_sources ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [_source_public(row) for row in rows]


class DatasetRecordRepository(BaseRepository):
    def create(self, item: DatasetRecordCreate) -> DatasetRecordPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            duplicate = connection.execute(
                "SELECT public_id FROM dataset_records WHERE content_hash=?", (item.content_hash,)
            ).fetchone()
            if duplicate:
                raise ConflictError(f"duplicate content hash belongs to {duplicate['public_id']}")
            source_id = None
            if item.source_public_id:
                row = connection.execute(
                    "SELECT id FROM dataset_sources WHERE public_id=?", (item.source_public_id,)
                ).fetchone()
                if not row:
                    raise NotFoundError("dataset source not found")
                source_id = row[0]
            legacy_content = item.output_text or item.input_text or item.instruction or ""
            connection.execute(
                """INSERT INTO dataset_records(source_id,content,language,status,public_id,
                record_type,instruction,input_text,output_text,normalized_input,content_hash,
                quality_score,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    source_id,
                    legacy_content,
                    item.language.value,
                    item.status.value,
                    public_id,
                    item.record_type.value,
                    item.instruction,
                    item.input_text,
                    item.output_text,
                    item.normalized_input,
                    item.content_hash,
                    item.quality_score,
                    dumps_json(item.metadata),
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> DatasetRecordPublic:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT r.*, s.public_id AS source_public_id FROM dataset_records r
                LEFT JOIN dataset_sources s ON s.id=r.source_id WHERE r.public_id=?""",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("dataset record not found")
        return DatasetRecordPublic(
            public_id=row["public_id"],
            source_public_id=row["source_public_id"],
            record_type=row["record_type"],
            language=row["language"],
            instruction=row["instruction"],
            input_text=row["input_text"],
            output_text=row["output_text"],
            normalized_input=row["normalized_input"],
            content_hash=row["content_hash"],
            quality_score=row["quality_score"],
            status=row["status"],
            metadata=loads_json(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list(self, *, limit: int = 50, offset: int = 0) -> list[DatasetRecordPublic]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            ids = [
                row[0]
                for row in connection.execute(
                    "SELECT public_id FROM dataset_records ORDER BY id LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ]
        return [self.get_by_public_id(public_id) for public_id in ids]


class DatasetReviewRepository(BaseRepository):
    def create(self, item: DatasetReviewCreate) -> DatasetReviewPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            record = connection.execute(
                "SELECT id,status FROM dataset_records WHERE public_id=?",
                (item.dataset_record_public_id,),
            ).fetchone()
            if not record:
                raise NotFoundError("dataset record not found")
            connection.execute(
                """INSERT INTO dataset_reviews(public_id,dataset_record_id,decision,
                reviewer_type,reviewer_reference,comments,previous_status,new_status)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    record["id"],
                    item.decision.value,
                    item.reviewer_type.value,
                    item.reviewer_reference,
                    item.comments,
                    record["status"],
                    item.new_status.value,
                ),
            )
            connection.execute(
                "UPDATE dataset_records SET status=?,updated_at=? WHERE id=?",
                (item.new_status.value, _now(), record["id"]),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> DatasetReviewPublic:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM dataset_reviews WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("dataset review not found")
        return DatasetReviewPublic(
            public_id=row["public_id"],
            decision=row["decision"],
            reviewer_type=row["reviewer_type"],
            reviewer_reference=row["reviewer_reference"],
            comments=row["comments"],
            previous_status=row["previous_status"],
            new_status=row["new_status"],
            created_at=row["created_at"],
        )


class DatasetVersionRepository(BaseRepository):
    def create(self, item: DatasetVersionCreate) -> DatasetVersionPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO dataset_versions(public_id,name,version,description,status,
                manifest_json,record_count,language_distribution_json,split_distribution_json,
                checksum_sha256,finalized_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    item.name,
                    item.version,
                    item.description,
                    item.status.value,
                    dumps_json(item.manifest),
                    item.record_count,
                    dumps_json(item.language_distribution),
                    dumps_json(item.split_distribution),
                    item.checksum_sha256,
                    _now() if item.status is DatasetVersionStatus.READY else None,
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> DatasetVersionPublic:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM dataset_versions WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("dataset version not found")
        return DatasetVersionPublic(
            public_id=row["public_id"],
            name=row["name"],
            version=row["version"],
            description=row["description"],
            status=row["status"],
            manifest=loads_json(row["manifest_json"]),
            record_count=row["record_count"],
            language_distribution=loads_json(row["language_distribution_json"]),
            split_distribution=loads_json(row["split_distribution_json"]),
            checksum_sha256=row["checksum_sha256"],
            created_at=row["created_at"],
            finalized_at=row["finalized_at"],
        )

    def update_manifest(self, public_id: str, manifest: dict[str, Any]) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT status FROM dataset_versions WHERE public_id=?", (public_id,)
            ).fetchone()
            if not row:
                raise NotFoundError("dataset version not found")
            if row[0] == DatasetVersionStatus.READY.value:
                raise ValidationError("ready dataset versions are immutable")
            connection.execute(
                "UPDATE dataset_versions SET manifest_json=? WHERE public_id=?",
                (dumps_json(manifest), public_id),
            )


VALID_TRAINING_TRANSITIONS: dict[TrainingStatus, set[TrainingStatus]] = {
    TrainingStatus.DRAFT: {TrainingStatus.VALIDATING, TrainingStatus.CANCELLED},
    TrainingStatus.VALIDATING: {
        TrainingStatus.QUEUED,
        TrainingStatus.FAILED,
        TrainingStatus.CANCELLED,
    },
    TrainingStatus.QUEUED: {TrainingStatus.RUNNING, TrainingStatus.CANCELLED},
    TrainingStatus.RUNNING: {
        TrainingStatus.PAUSED,
        TrainingStatus.COMPLETED,
        TrainingStatus.FAILED,
        TrainingStatus.CANCELLED,
    },
    TrainingStatus.PAUSED: {TrainingStatus.RUNNING, TrainingStatus.CANCELLED},
    TrainingStatus.COMPLETED: set(),
    TrainingStatus.FAILED: set(),
    TrainingStatus.CANCELLED: set(),
}


class TrainingJobRepository(BaseRepository):
    def create(self, item: TrainingJobCreate) -> TrainingJobPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            dataset_version_id = None
            base_model_version_id = None
            if item.dataset_version_public_id:
                row = connection.execute(
                    "SELECT id FROM dataset_versions WHERE public_id=?",
                    (item.dataset_version_public_id,),
                ).fetchone()
                if not row:
                    raise NotFoundError("dataset version not found")
                dataset_version_id = row[0]
            if item.base_model_version_public_id:
                row = connection.execute(
                    "SELECT id FROM model_versions WHERE public_id=?",
                    (item.base_model_version_public_id,),
                ).fetchone()
                if not row:
                    raise NotFoundError("base model version not found")
                base_model_version_id = row[0]
            connection.execute(
                """INSERT INTO training_jobs(status,configuration,public_id,name,training_type,
                dataset_version_id,base_model_version_id,tokenizer_reference,config_json,
                hardware_profile,progress,current_step,total_steps)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item.status.value,
                    dumps_json(item.config),
                    public_id,
                    item.name,
                    item.training_type.value,
                    dataset_version_id,
                    base_model_version_id,
                    item.tokenizer_reference,
                    dumps_json(item.config),
                    item.hardware_profile,
                    item.progress,
                    item.current_step,
                    item.total_steps,
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> TrainingJobPublic:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT j.*, d.public_id AS dataset_version_public_id,
                m.public_id AS base_model_version_public_id FROM training_jobs j
                LEFT JOIN dataset_versions d ON d.id=j.dataset_version_id
                LEFT JOIN model_versions m ON m.id=j.base_model_version_id
                WHERE j.public_id=?""",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("training job not found")
        return TrainingJobPublic(
            public_id=row["public_id"],
            name=row["name"],
            training_type=row["training_type"],
            status=row["status"],
            dataset_version_public_id=row["dataset_version_public_id"],
            base_model_version_public_id=row["base_model_version_public_id"],
            tokenizer_reference=row["tokenizer_reference"],
            config=loads_json(row["config_json"]),
            hardware_profile=row["hardware_profile"],
            progress=row["progress"],
            current_step=row["current_step"],
            total_steps=row["total_steps"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            updated_at=row["updated_at"],
        )

    def transition(
        self, public_id: str, new_status: TrainingStatus, message: str | None = None
    ) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id,status FROM training_jobs WHERE public_id=?", (public_id,)
            ).fetchone()
            if not row:
                raise NotFoundError("training job not found")
            current = TrainingStatus(row["status"])
            if new_status not in VALID_TRAINING_TRANSITIONS[current]:
                raise ValidationError(f"invalid training transition: {current} -> {new_status}")
            connection.execute(
                "UPDATE training_jobs SET status=?,updated_at=? WHERE id=?",
                (new_status.value, _now(), row["id"]),
            )
            connection.execute(
                """INSERT INTO training_job_events(training_job_id,event_type,previous_status,
                new_status,message) VALUES (?,?,?,?,?)""",
                (row["id"], "status_changed", current.value, new_status.value, message),
            )


class ModelRegistryRepository(BaseRepository):
    def create(self, item: ModelRegistryCreate) -> ModelRegistryPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM model_registry WHERE name=?", (item.name,)
            ).fetchone():
                raise ConflictError("model family name already exists")
            connection.execute(
                """INSERT INTO model_registry(name,version,status,metadata,public_id,model_type,
                description) VALUES (?,?,?,?,?,?,?)""",
                (
                    item.name,
                    "family",
                    item.status.value,
                    "{}",
                    public_id,
                    item.model_type.value,
                    item.description,
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> ModelRegistryPublic:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT public_id,name,model_type,description,status,created_at,updated_at "
                "FROM model_registry WHERE public_id=?",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("model registry item not found")
        return ModelRegistryPublic.model_validate(dict(row))


class ModelVersionRepository(BaseRepository):
    def create(self, item: ModelVersionCreate) -> ModelVersionPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            family = connection.execute(
                "SELECT id FROM model_registry WHERE public_id=?", (item.model_registry_public_id,)
            ).fetchone()
            if not family:
                raise NotFoundError("model registry item not found")
            dataset_version_id = None
            training_job_id = None
            if item.dataset_version_public_id:
                row = connection.execute(
                    "SELECT id FROM dataset_versions WHERE public_id=?",
                    (item.dataset_version_public_id,),
                ).fetchone()
                if not row:
                    raise NotFoundError("dataset version not found")
                dataset_version_id = row[0]
            if item.training_job_public_id:
                row = connection.execute(
                    "SELECT id FROM training_jobs WHERE public_id=?",
                    (item.training_job_public_id,),
                ).fetchone()
                if not row:
                    raise NotFoundError("training job not found")
                training_job_id = row[0]
            try:
                connection.execute(
                    """INSERT INTO model_versions(public_id,model_registry_id,version,
                    lifecycle_status,architecture,parameter_count,context_length,vocabulary_size,
                    tokenizer_reference,checkpoint_path,export_path,quantization,metrics_json,
                    dataset_version_id,training_job_id,checksum_sha256,activated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        public_id,
                        family[0],
                        item.version,
                        item.lifecycle_status.value,
                        item.architecture,
                        item.parameter_count,
                        item.context_length,
                        item.vocabulary_size,
                        item.tokenizer_reference,
                        item.checkpoint_path,
                        item.export_path,
                        item.quantization,
                        dumps_json(item.metrics),
                        dataset_version_id,
                        training_job_id,
                        item.checksum_sha256,
                        _now() if item.lifecycle_status is ModelLifecycleStatus.ACTIVE else None,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(
                    "model version conflicts with an existing version or active model"
                ) from exc
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> ModelVersionPublic:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT v.*, r.public_id AS model_registry_public_id,
                d.public_id AS dataset_version_public_id, j.public_id AS training_job_public_id
                FROM model_versions v JOIN model_registry r ON r.id=v.model_registry_id
                LEFT JOIN dataset_versions d ON d.id=v.dataset_version_id
                LEFT JOIN training_jobs j ON j.id=v.training_job_id
                WHERE v.public_id=?""",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("model version not found")
        return ModelVersionPublic(
            public_id=row["public_id"],
            model_registry_public_id=row["model_registry_public_id"],
            version=row["version"],
            lifecycle_status=row["lifecycle_status"],
            architecture=row["architecture"],
            parameter_count=row["parameter_count"],
            context_length=row["context_length"],
            vocabulary_size=row["vocabulary_size"],
            tokenizer_reference=row["tokenizer_reference"],
            checkpoint_path=row["checkpoint_path"],
            export_path=row["export_path"],
            quantization=row["quantization"],
            dataset_version_public_id=row["dataset_version_public_id"],
            training_job_public_id=row["training_job_public_id"],
            metrics=loads_json(row["metrics_json"]),
            checksum_sha256=row["checksum_sha256"],
            created_at=row["created_at"],
            activated_at=row["activated_at"],
        )

    def activate(self, public_id: str) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id,model_registry_id FROM model_versions WHERE public_id=?", (public_id,)
            ).fetchone()
            if not row:
                raise NotFoundError("model version not found")
            active = connection.execute(
                "SELECT public_id FROM model_versions "
                "WHERE model_registry_id=? AND lifecycle_status='active'",
                (row["model_registry_id"],),
            ).fetchone()
            if active and active[0] != public_id:
                raise ValidationError("model family already has an active version")
            connection.execute(
                "UPDATE model_versions SET lifecycle_status='active',activated_at=? WHERE id=?",
                (_now(), row["id"]),
            )


class ModelAssignmentRepository(BaseRepository):
    def create(self, item: ModelAssignmentCreate) -> ModelAssignmentPublic:
        with self.transaction() as connection:
            model_version_id = None
            fallback_model_version_id = None
            if item.model_version_public_id:
                row = connection.execute(
                    "SELECT id FROM model_versions WHERE public_id=?",
                    (item.model_version_public_id,),
                ).fetchone()
                if not row:
                    raise NotFoundError("model version not found")
                model_version_id = row[0]
            if item.fallback_model_version_public_id:
                row = connection.execute(
                    "SELECT id FROM model_versions WHERE public_id=?",
                    (item.fallback_model_version_public_id,),
                ).fetchone()
                if not row:
                    raise NotFoundError("fallback model version not found")
                fallback_model_version_id = row[0]
            connection.execute(
                """INSERT INTO model_assignments(assignment_key,model_version_id,
                fallback_model_version_id,enabled,configuration_json) VALUES (?,?,?,?,?)""",
                (
                    item.assignment_key.value,
                    model_version_id,
                    fallback_model_version_id,
                    int(item.enabled),
                    dumps_json(item.configuration),
                ),
            )
        return self.get_by_public_id(item.assignment_key.value)

    def get_by_public_id(self, public_id: str) -> ModelAssignmentPublic:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT a.*, m.public_id AS model_version_public_id,
                f.public_id AS fallback_model_version_public_id FROM model_assignments a
                LEFT JOIN model_versions m ON m.id=a.model_version_id
                LEFT JOIN model_versions f ON f.id=a.fallback_model_version_id
                WHERE a.assignment_key=?""",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("model assignment not found")
        return ModelAssignmentPublic(
            assignment_key=row["assignment_key"],
            model_version_public_id=row["model_version_public_id"],
            fallback_model_version_public_id=row["fallback_model_version_public_id"],
            enabled=bool(row["enabled"]),
            configuration=loads_json(row["configuration_json"]),
            updated_at=row["updated_at"],
        )


class FeedbackRepository(BaseRepository):
    def create(self, item: UserFeedbackCreate) -> UserFeedbackPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            chat_message_id = None
            if item.chat_message_public_id:
                row = connection.execute(
                    "SELECT id FROM chat_messages WHERE public_id=?",
                    (item.chat_message_public_id,),
                ).fetchone()
                if not row:
                    raise NotFoundError("chat message not found")
                chat_message_id = row[0]
            connection.execute(
                """INSERT INTO user_feedback(public_id,chat_message_id,feedback_type,rating,
                comment,suggested_answer,status) VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id,
                    chat_message_id,
                    item.feedback_type.value,
                    item.rating,
                    item.comment,
                    item.suggested_answer,
                    item.status.value,
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> UserFeedbackPublic:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT f.*, m.public_id AS chat_message_public_id FROM user_feedback f
                LEFT JOIN chat_messages m ON m.id=f.chat_message_id WHERE f.public_id=?""",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("feedback not found")
        return UserFeedbackPublic(
            public_id=row["public_id"],
            chat_message_public_id=row["chat_message_public_id"],
            feedback_type=row["feedback_type"],
            rating=row["rating"],
            comment=row["comment"],
            suggested_answer=row["suggested_answer"],
            status=row["status"],
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
        )


class AdminApprovalRepository(BaseRepository):
    def create(self, item: AdminApprovalCreate) -> AdminApprovalPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO admin_approvals(public_id,action_type,target_type,
                target_public_id,request_payload_json,requested_by) VALUES (?,?,?,?,?,?)""",
                (
                    public_id,
                    item.action_type,
                    item.target_type,
                    item.target_public_id,
                    dumps_json(item.request_payload),
                    item.requested_by,
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> AdminApprovalPublic:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM admin_approvals WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("admin approval not found")
        return AdminApprovalPublic(
            public_id=row["public_id"],
            action_type=row["action_type"],
            target_type=row["target_type"],
            target_public_id=row["target_public_id"],
            request_payload=redact_secrets(loads_json(row["request_payload_json"])),
            requested_by=row["requested_by"],
            status=row["status"],
            reviewed_by=row["reviewed_by"],
            review_comment=row["review_comment"],
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
        )


class AuditLogRepository(BaseRepository):
    def append(self, event: AuditEventCreate) -> AuditEventPublic:
        public_id = str(uuid4())
        safe_metadata = redact_secrets(event.metadata)
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
                actor_reference,resource_type,resource_public_id,outcome,request_id,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.action,
                    event.actor_type,
                    "{}",
                    public_id,
                    event.event_type,
                    event.actor_type,
                    event.actor_reference,
                    event.resource_type,
                    event.resource_public_id,
                    event.outcome.value,
                    event.request_id,
                    dumps_json(safe_metadata),
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> AuditEventPublic:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM audit_logs WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("audit event not found")
        return self._public(row)

    def recent(self, *, limit: int = 20, offset: int = 0) -> list[AuditEventPublic]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> AuditEventPublic:
        return AuditEventPublic(
            public_id=row["public_id"],
            event_type=row["event_type"],
            actor_type=row["actor_type"],
            actor_reference=row["actor_reference"],
            action=row["action"],
            resource_type=row["resource_type"],
            resource_public_id=row["resource_public_id"],
            outcome=row["outcome"],
            request_id=row["request_id"],
            metadata=redact_secrets(loads_json(row["metadata_json"])),
            created_at=row["created_at"],
        )

    def update(self, *_: object, **__: object) -> None:
        raise ValidationError("audit logs are append-only")

    def delete(self, *_: object, **__: object) -> None:
        raise ValidationError("audit logs are append-only")


# Persistence-only Phase 2 repositories that share an owning repository's API.
class TrainingJobEventRepository(TrainingJobRepository):
    pass


class DatasetVersionItemRepository(DatasetVersionRepository):
    pass


def content_hash_for(*parts: str | None) -> str:
    canonical = dumps_json(list(parts))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
