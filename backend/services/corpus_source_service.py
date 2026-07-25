"""Phase 19 corpus policy, source registry, licence governance, and
immutable source snapshot/file management.

Every filesystem path this service ever reads is validated against
``Settings.corpus_path_is_approved`` first -- an admin can register a
source pointing at a file, but never at an arbitrary path outside the
registered-upload directory or an explicitly configured approved root.
Original source files are only ever read, never modified or deleted.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import (
    CorpusPolicyCreate,
    CorpusPolicyPatch,
    LicenceReviewDecision,
    SnapshotCreate,
    SourceLicenceCreate,
    SourceRegistryCreate,
    SourceRegistryPatch,
)
from core_model.corpus.licence_policy import (
    assess_training_export_eligibility,
    default_review_status_for_family,
    validate_licence_record,
)
from core_model.corpus.source_policy import (
    source_is_training_eligible,
    summarize_policy,
    validate_policy_bounds,
    validate_source_type,
)
from core_model.corpus.source_snapshot import (
    file_inventory_checksum,
    snapshot_requires_new_version,
    validate_snapshot_ready,
)

_MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
}


class CorpusSourceService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- policies -----------------------------------------------------

    def create_policy(self, payload: CorpusPolicyCreate, admin_id: str) -> dict[str, Any]:
        ok, reason = validate_policy_bounds(
            maximum_source_bytes=payload.maximum_source_bytes,
            maximum_document_characters=payload.maximum_document_characters,
            maximum_segment_characters=payload.maximum_segment_characters,
            minimum_segment_characters=payload.minimum_segment_characters,
        )
        if not ok:
            raise ValidationError(reason)
        values = payload.model_dump(mode="json")
        values["supported_languages_json"] = dumps_json(values.pop("supported_languages"))
        values["allowed_source_types_json"] = dumps_json(values.pop("allowed_source_types"))
        values["allowed_licence_statuses_json"] = dumps_json(values.pop("allowed_licence_statuses"))
        values["export_format_policy_json"] = dumps_json(values.pop("export_format_policy"))
        values["created_by_admin_public_id"] = admin_id
        with self.repository.transaction() as connection:
            public_id = self.repository.create_policy(connection, values)
            self._audit(connection, "corpus_policy_created", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    def list_policies(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_policies(connection)]}

    def get_policy(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.policy(connection, public_id)
            result = public_row(row)
            result["summary"] = summarize_policy(result)
            return result

    def patch_policy(
        self, public_id: str, payload: CorpusPolicyPatch, admin_id: str
    ) -> dict[str, Any]:
        fields = {k: v for k, v in payload.model_dump(mode="json").items() if v is not None}
        with self.repository.transaction() as connection:
            row = self.repository.policy(connection, public_id)
            self.repository.update_policy(connection, row["id"], fields)
            self._audit(connection, "corpus_policy_patched", admin_id, public_id)
            return public_row(self.repository.policy(connection, public_id))

    # --- sources -----------------------------------------------------

    def create_source(self, payload: SourceRegistryCreate, admin_id: str) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        policy_public_id = values.pop("corpus_policy_public_id")
        with self.repository.transaction() as connection:
            policy_row = self.repository.policy(connection, policy_public_id)
            allowed_types = public_row(policy_row).get("allowed_source_types", [])
            ok, reason = validate_source_type(values["source_type"], allowed_types)
            if not ok:
                raise ValidationError(reason)
            values["corpus_policy_id"] = policy_row["id"]
            values["created_by_admin_public_id"] = admin_id
            public_id = self.repository.create_source(connection, values)
            self._audit(connection, "corpus_source_created", admin_id, public_id)
            return public_row(self.repository.source(connection, public_id))

    def list_sources(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_sources(connection)]}

    def get_source(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.source(connection, public_id)
            result = public_row(row)
            licence_row = self.repository.latest_licence_for_source(connection, row["id"])
            result["current_licence"] = public_row(licence_row) if licence_row else None
            return result

    def patch_source(
        self, public_id: str, payload: SourceRegistryPatch, admin_id: str
    ) -> dict[str, Any]:
        fields = {k: v for k, v in payload.model_dump(mode="json").items() if v is not None}
        with self.repository.transaction() as connection:
            row = self.repository.source(connection, public_id)
            if row["status"] not in {"draft", "origin_review"}:
                raise ValidationError("source can only be edited before licence review begins")
            self.repository.update_source(connection, row["id"], fields)
            self._audit(connection, "corpus_source_patched", admin_id, public_id)
            return public_row(self.repository.source(connection, public_id))

    def transition_source_status(
        self, public_id: str, target_status: str, admin_id: str, *, reason: str = ""
    ) -> dict[str, Any]:
        allowed_transitions = {
            "draft": {"origin_review", "archived"},
            "origin_review": {"licence_review", "rejected", "archived"},
            "licence_review": {"approved", "approved_with_restrictions", "rejected", "disputed"},
            "approved": {"quarantined", "disputed", "archived"},
            "approved_with_restrictions": {"quarantined", "disputed", "archived"},
            "disputed": {"approved", "approved_with_restrictions", "rejected", "quarantined"},
        }
        with self.repository.transaction() as connection:
            row = self.repository.source(connection, public_id)
            current = row["status"]
            if target_status not in allowed_transitions.get(current, set()):
                raise ValidationError(f"cannot transition source from {current} to {target_status}")
            fields: dict[str, Any] = {"status": target_status}
            if target_status == "origin_review":
                fields["origin_verified"] = 0
            self.repository.update_source(connection, row["id"], fields)
            self._audit(
                connection,
                "corpus_source_status_changed",
                admin_id,
                public_id,
                previous_status=current,
                target_status=target_status,
                reason=reason,
            )
            return public_row(self.repository.source(connection, public_id))

    def verify_origin(self, public_id: str, admin_id: str, *, evidence: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.source(connection, public_id)
            self.repository.update_source(
                connection, row["id"], {"origin_verified": 1, "origin_evidence": evidence}
            )
            self._audit(connection, "corpus_source_origin_verified", admin_id, public_id)
            return public_row(self.repository.source(connection, public_id))

    # --- licences -----------------------------------------------------

    def create_licence(
        self, source_public_id: str, payload: SourceLicenceCreate, admin_id: str
    ) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        values["allowed_uses_json"] = dumps_json(values.pop("allowed_uses"))
        values["prohibited_uses_json"] = dumps_json(values.pop("prohibited_uses"))
        values["review_status"] = default_review_status_for_family(values["licence_family"])
        ok, reason = validate_licence_record(
            licence_family=values["licence_family"], review_status=values["review_status"]
        )
        if not ok:
            raise ValidationError(reason)
        with self.repository.transaction() as connection:
            source_row = self.repository.source(connection, source_public_id)
            values["source_id"] = source_row["id"]
            public_id = self.repository.create_licence(connection, values)
            self._audit(connection, "corpus_licence_created", admin_id, public_id)
            return public_row(self.repository.licence(connection, public_id))

    def review_licence(
        self, licence_public_id: str, payload: LicenceReviewDecision, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.licence(connection, licence_public_id)
            ok, reason = validate_licence_record(
                licence_family=row["licence_family"], review_status=payload.review_status
            )
            if not ok:
                raise ValidationError(reason)
            self.repository.update_licence(
                connection,
                row["id"],
                {
                    "review_status": payload.review_status,
                    "review_notes": payload.review_notes,
                    "reviewer_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection,
                "corpus_licence_reviewed",
                admin_id,
                licence_public_id,
                review_status=payload.review_status,
            )
            return public_row(self.repository.licence(connection, licence_public_id))

    def training_eligibility(self, source_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source_row = self.repository.source(connection, source_public_id)
            licence_row = self.repository.latest_licence_for_source(connection, source_row["id"])
            if licence_row is None:
                return {
                    "eligible": False,
                    "blocking_reasons": ["no_licence_record"],
                }
            import datetime as _dt

            expires_at = licence_row["expires_at"]
            expired = bool(expires_at) and expires_at < _dt.datetime.now(_dt.UTC).isoformat()
            return assess_training_export_eligibility(
                review_status=licence_row["review_status"],
                ai_training_permitted=bool(licence_row["ai_training_permitted"]),
                source_status=source_row["status"],
                intended_use=source_row["intended_use"],
                licence_family=licence_row["licence_family"],
                expires_at_is_past=expired,
            )

    # --- approved-path resolution -----------------------------------------------------

    def resolve_approved_path(self, relative_path: str) -> Path:
        """Resolves a relative path against every approved corpus root
        in turn -- never accepts an absolute or `..`-escaping path, and
        never reads anything outside the approved roots or the
        registered-upload directory."""

        if ".." in Path(relative_path).parts or Path(relative_path).is_absolute():
            raise ValidationError("invalid source file path")
        for root in self.settings.corpus_approved_roots:
            candidate = (root / relative_path).resolve()
            if candidate.is_relative_to(root.resolve()) and candidate.is_file():
                return candidate
        raise ValidationError("source file path is not under an approved corpus root")

    # --- snapshots -----------------------------------------------------

    def create_snapshot(
        self, source_public_id: str, payload: SnapshotCreate, admin_id: str
    ) -> dict[str, Any]:
        if not payload.files:
            raise ValidationError("a snapshot requires at least one file")

        file_records: list[dict[str, Any]] = []
        total_bytes = 0
        for entry in payload.files:
            relative_path = entry.get("relative_path")
            if not relative_path:
                raise ValidationError("each file entry requires a relative_path")
            logical_filename = entry.get("logical_filename") or Path(relative_path).name
            path = self.resolve_approved_path(relative_path)
            raw_bytes = path.read_bytes()
            if len(raw_bytes) > self.settings.corpus_max_source_bytes:
                raise ValidationError(f"{logical_filename} exceeds the maximum source bytes bound")
            checksum = hashlib.sha256(raw_bytes).hexdigest()
            total_bytes += len(raw_bytes)
            file_records.append(
                {
                    "logical_filename": logical_filename,
                    "safe_relative_storage_key": relative_path,
                    "mime_type": _MIME_BY_EXTENSION.get(
                        path.suffix.lower(), "application/octet-stream"
                    ),
                    "size_bytes": len(raw_bytes),
                    "checksum_sha256": checksum,
                }
            )

        inventory_checksum = file_inventory_checksum(file_records)
        ok, reason = validate_snapshot_ready(
            total_files=len(file_records),
            total_bytes=total_bytes,
            maximum_source_bytes=self.settings.corpus_max_source_bytes,
        )
        if not ok:
            raise ValidationError(reason)

        with self.repository.transaction() as connection:
            source_row = self.repository.source(connection, source_public_id)
            existing = self.repository.snapshots_for_source(connection, source_row["id"])
            previous_checksum = existing[0]["file_inventory_checksum_sha256"] if existing else None
            if existing and not snapshot_requires_new_version(
                previous_file_inventory_checksum=previous_checksum,
                current_file_inventory_checksum=inventory_checksum,
            ):
                raise ValidationError("an identical snapshot already exists for this source")
            values = {
                "source_id": source_row["id"],
                "source_checksum_sha256": inventory_checksum,
                "file_inventory_checksum_sha256": inventory_checksum,
                "total_bytes": total_bytes,
                "total_files": len(file_records),
                "created_by_admin_public_id": admin_id,
            }
            snapshot_public_id = self.repository.create_snapshot(connection, values)
            snapshot_row = self.repository.snapshot(connection, snapshot_public_id)
            for record in file_records:
                record["snapshot_id"] = snapshot_row["id"]
                self.repository.create_file(connection, record)
            self.repository.update_snapshot(connection, snapshot_row["id"], {"status": "ready"})
            self._audit(
                connection,
                "corpus_snapshot_created",
                admin_id,
                snapshot_public_id,
                total_files=len(file_records),
                total_bytes=total_bytes,
            )
            return self._snapshot_detail(connection, snapshot_public_id)

    def get_snapshot(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self._snapshot_detail(connection, public_id)

    def _snapshot_detail(self, connection, public_id: str) -> dict[str, Any]:
        row = self.repository.snapshot(connection, public_id)
        result = public_row(row)
        result["files"] = [
            public_row(file_row)
            for file_row in self.repository.files_for_snapshot(connection, row["id"])
        ]
        return result

    def list_snapshots(self, source_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source_row = self.repository.source(connection, source_public_id)
            return {
                "items": [
                    public_row(row)
                    for row in self.repository.snapshots_for_source(connection, source_row["id"])
                ]
            }

    def check_training_eligibility_for_build(
        self, source_public_id: str, *, require_verified_origin: bool
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source_row = self.repository.source(connection, source_public_id)
            ok, reason = source_is_training_eligible(
                status=source_row["status"],
                require_verified_origin=require_verified_origin,
                origin_verified=bool(source_row["origin_verified"]),
            )
            return {"eligible": ok, "reason": reason}

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
                event,
                "admin",
                "{}",
                str(uuid4()),
                event,
                "admin",
                admin_id,
                "corpus",
                resource_id,
                "success",
                dumps_json(metadata),
            ),
        )
