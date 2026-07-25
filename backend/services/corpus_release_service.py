"""Phase 20 immutable corpus release lifecycle.

``draft -> validated -> approved -> finalized -> exported -> retired``.
A release is created against one specific, already-built
``corpus_versions`` row -- new content is never folded into an
existing release; it always requires a brand new corpus version (and
therefore a brand new release with a new ``semantic_version``, which
the schema enforces via ``UNIQUE(semantic_version)``). Once
``finalized``, a release's manifest checksum is frozen and no field on
the release itself is ever mutated again except the forward-only
status transitions to ``exported``/``retired``.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import ReleaseApprovalCreate, ReleaseCreate

_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"validated"},
    "validated": {"approved", "draft"},
    "approved": {"finalized", "draft"},
    "finalized": {"exported"},
    "exported": {"retired"},
    "retired": set(),
}


class CorpusReleaseService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def create_release(self, payload: ReleaseCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version_row = self.repository.version(connection, payload.corpus_version_public_id)
            readiness_id = None
            if payload.readiness_evaluation_public_id:
                readiness_row = self.repository.readiness_evaluation(
                    connection, payload.readiness_evaluation_public_id
                )
                if readiness_row["build_id"] != version_row["build_id"]:
                    raise ValidationError(
                        "readiness evaluation does not belong to this corpus version's build"
                    )
                readiness_id = readiness_row["id"]

            release_public_id = self.repository.create_release(
                connection,
                {
                    "corpus_version_id": version_row["id"],
                    "readiness_evaluation_id": readiness_id,
                    "semantic_version": payload.semantic_version,
                    "release_name": payload.release_name,
                    "description": payload.description,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "corpus_release_created", admin_id, release_public_id)
            return self._detail(connection, release_public_id)

    def _require_transition(self, current: str, target: str) -> None:
        if target not in _TRANSITIONS.get(current, set()):
            raise ValidationError(f"cannot move release from '{current}' to '{target}'")

    def validate_release(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            release_row = self.repository.release(connection, public_id)
            self._require_transition(release_row["status"], "validated")
            if release_row["readiness_evaluation_id"] is None:
                raise ValidationError(
                    "a release cannot be validated without a linked readiness evaluation"
                )
            readiness_row = connection.execute(
                "SELECT overall_result FROM corpus_readiness_evaluations WHERE id=?",
                (release_row["readiness_evaluation_id"],),
            ).fetchone()
            if readiness_row["overall_result"] == "not_ready":
                raise ValidationError(
                    "linked readiness evaluation is 'not_ready'; release cannot be validated"
                )
            self.repository.update_release(connection, release_row["id"], {"status": "validated"})
            self._audit(connection, "corpus_release_validated", admin_id, public_id)
            return self._detail(connection, public_id)

    def record_approval(
        self, public_id: str, payload: ReleaseApprovalCreate, admin_id: str
    ) -> dict[str, Any]:
        if payload.decision not in ("approve", "reject"):
            raise ValidationError("decision must be 'approve' or 'reject'")
        with self.repository.transaction() as connection:
            release_row = self.repository.release(connection, public_id)
            if release_row["status"] != "validated":
                raise ValidationError("only a validated release can be approved or rejected")
            self.repository.record_release_approval(
                connection,
                {
                    "release_id": release_row["id"],
                    "decision": payload.decision,
                    "comment": payload.comment,
                    "approved_by_admin_public_id": admin_id,
                },
            )
            if payload.decision == "approve":
                self.repository.update_release(
                    connection,
                    release_row["id"],
                    {"status": "approved", "approved_by_admin_public_id": admin_id},
                )
            else:
                self.repository.update_release(connection, release_row["id"], {"status": "draft"})
            self._audit(
                connection, "corpus_release_approval_recorded", admin_id, public_id,
                decision=payload.decision,
            )
            return self._detail(connection, public_id)

    def finalize_release(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            release_row = self.repository.release(connection, public_id)
            self._require_transition(release_row["status"], "finalized")
            version_row = connection.execute(
                "SELECT * FROM corpus_versions WHERE id=?", (release_row["corpus_version_id"],)
            ).fetchone()
            if version_row["manifest_checksum_sha256"] is None:
                raise ValidationError(
                    "corpus version has no generated manifest; generate one before finalizing"
                )
            self.repository.update_release(
                connection,
                release_row["id"],
                {
                    "status": "finalized",
                    "manifest_checksum_sha256": version_row["manifest_checksum_sha256"],
                    "finalized_at": _now_sql(),
                },
            )
            self._audit(connection, "corpus_release_finalized", admin_id, public_id)
            return self._detail(connection, public_id)

    def mark_exported(self, public_id: str, export_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            release_row = self.repository.release(connection, public_id)
            self._require_transition(release_row["status"], "exported")
            export_row = self.repository.export(connection, export_public_id)
            version_row = connection.execute(
                "SELECT * FROM corpus_versions WHERE id=?", (release_row["corpus_version_id"],)
            ).fetchone()
            if export_row["corpus_version_id"] != version_row["id"]:
                raise ValidationError("export does not belong to this release's corpus version")
            if export_row["status"] not in ("completed", "completed_with_warnings"):
                raise ValidationError("export must be completed before it can back a release")
            self.repository.update_release(
                connection, release_row["id"], {"status": "exported", "export_id": export_row["id"]}
            )
            self._audit(connection, "corpus_release_exported", admin_id, public_id)
            return self._detail(connection, public_id)

    def retire_release(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            release_row = self.repository.release(connection, public_id)
            self._require_transition(release_row["status"], "retired")
            self.repository.update_release(connection, release_row["id"], {"status": "retired"})
            self._audit(connection, "corpus_release_retired", admin_id, public_id)
            return self._detail(connection, public_id)

    # --- read -----------------------------------------------------

    def _detail(self, connection, public_id: str) -> dict[str, Any]:
        row = self.repository.release(connection, public_id)
        result = public_row(row)
        result["approvals"] = [
            public_row(approval)
            for approval in self.repository.approvals_for_release(connection, row["id"])
        ]
        return result

    def get_release(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self._detail(connection, public_id)

    def list_releases(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_releases(connection)]}

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


def _now_sql() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
