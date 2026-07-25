"""Phase 20 versioned normalization and segmentation profiles.

Every profile is auditable and individually configurable: a
normalization profile's ``operations`` dict gates which of Phase 19's
already-implemented normalization steps
(``unicode_normalization``/``tamil_normalization``/
``boilerplate_detection``) actually run for a given ingestion job, and
a segmentation profile pairs a content type with one of Phase 19's
existing segmentation strategies -- neither profile type re-implements
any pure function, they only parameterize which of Phase 19's already-
implemented steps run and how.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import NormalizationProfileCreate, SegmentationProfileCreate

NORMALIZATION_PROFILE_KEYS = (
    "tamil_conservative",
    "tamil_ocr_cleanup",
    "tamil_education_text",
    "tamil_web_text",
    "tamil_mixed_tanglish",
)
SEGMENTATION_CONTENT_TYPES = (
    "books",
    "school_textbooks",
    "articles",
    "government_documents",
    "agriculture_content",
    "literature",
    "conversational_text",
    "faq_instructional",
    "mixed_tamil_english",
)


class CorpusProfileService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- normalization profiles -----------------------------------------------------

    def create_normalization_profile(
        self, payload: NormalizationProfileCreate, admin_id: str
    ) -> dict[str, Any]:
        if payload.profile_key not in NORMALIZATION_PROFILE_KEYS:
            raise ValidationError(f"unsupported normalization profile_key: {payload.profile_key}")
        values = {
            "name": payload.name,
            "profile_key": payload.profile_key,
            "version": payload.version,
            "operations_json": dumps_json(payload.operations),
            "created_by_admin_public_id": admin_id,
        }
        with self.repository.transaction() as connection:
            public_id = self.repository.create_normalization_profile(connection, values)
            self._audit(connection, "corpus_normalization_profile_created", admin_id, public_id)
            return public_row(self.repository.normalization_profile(connection, public_id))

    def list_normalization_profiles(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {
                "items": [
                    public_row(row)
                    for row in self.repository.list_normalization_profiles(connection)
                ]
            }

    def get_normalization_profile(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.normalization_profile(connection, public_id))

    def activate_normalization_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.normalization_profile(connection, public_id)
            self.repository.update_normalization_profile(
                connection, row["id"], {"lifecycle_status": "active"}
            )
            self._audit(connection, "corpus_normalization_profile_activated", admin_id, public_id)
            return public_row(self.repository.normalization_profile(connection, public_id))

    def archive_normalization_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.normalization_profile(connection, public_id)
            self.repository.update_normalization_profile(
                connection, row["id"], {"lifecycle_status": "archived"}
            )
            self._audit(connection, "corpus_normalization_profile_archived", admin_id, public_id)
            return public_row(self.repository.normalization_profile(connection, public_id))

    # --- segmentation profiles -----------------------------------------------------

    def create_segmentation_profile(
        self, payload: SegmentationProfileCreate, admin_id: str
    ) -> dict[str, Any]:
        if payload.content_type not in SEGMENTATION_CONTENT_TYPES:
            raise ValidationError(f"unsupported segmentation content_type: {payload.content_type}")
        values = {
            "name": payload.name,
            "content_type": payload.content_type,
            "strategy": payload.strategy,
            "version": payload.version,
            "configuration_json": dumps_json(payload.configuration),
            "created_by_admin_public_id": admin_id,
        }
        with self.repository.transaction() as connection:
            public_id = self.repository.create_segmentation_profile(connection, values)
            self._audit(connection, "corpus_segmentation_profile_created", admin_id, public_id)
            return public_row(self.repository.segmentation_profile(connection, public_id))

    def list_segmentation_profiles(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {
                "items": [
                    public_row(row)
                    for row in self.repository.list_segmentation_profiles(connection)
                ]
            }

    def get_segmentation_profile(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.segmentation_profile(connection, public_id))

    def activate_segmentation_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.segmentation_profile(connection, public_id)
            self.repository.update_segmentation_profile(
                connection, row["id"], {"lifecycle_status": "active"}
            )
            self._audit(connection, "corpus_segmentation_profile_activated", admin_id, public_id)
            return public_row(self.repository.segmentation_profile(connection, public_id))

    def archive_segmentation_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.segmentation_profile(connection, public_id)
            self.repository.update_segmentation_profile(
                connection, row["id"], {"lifecycle_status": "archived"}
            )
            self._audit(connection, "corpus_segmentation_profile_archived", admin_id, public_id)
            return public_row(self.repository.segmentation_profile(connection, public_id))

    # --- audit -----------------------------------------------------

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
                "corpus", resource_id, "success", dumps_json(metadata),
            ),
        )
