"""Services for the Phase 2 Source, Rights & Usage Registry.

Every mutation runs inside the repository's transaction and appends an
audit-log row in the same transaction (atomic, matching the pattern in
``corpus_source_service.py``/``admin_assistant_service.py``). Policy
decisions are never computed inline here -- they always go through
``core_model.data_governance.usage_policy``, so the same brain governs
both this registry and (via its adapters) the corpus pipeline.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.data_sources import DataSourceRepository, public_row
from backend.models.data_sources import (
    DataSourceCreate,
    DataSourcePatch,
    LinkCreate,
    SourceRightsUpsert,
    VerificationActionRequest,
)
from core_model.data_governance.usage_policy import (
    evaluate_source_usage,
    rights_from_source_rights_row,
    validate_rights_combination,
)

_SOURCE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"needs_review", "rejected", "archived"},
    "needs_review": {"verified", "restricted", "rejected", "archived"},
    "verified": {"restricted", "rejected", "archived"},
    "restricted": {"verified", "rejected", "archived"},
    "rejected": {"archived"},
    "archived": {"draft"},
}

_VERIFICATION_ACTION_STATUS: dict[str, str] = {
    "self_declare": "self_declared",
    "document_verify": "document_verified",
    "owner_confirm": "owner_confirmed",
    "legal_review": "legal_reviewed",
    "reject": "rejected",
    "expire": "unverified",
    "restrict": "unverified",
}


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class SourceRegistryService:
    def __init__(self, repository: DataSourceRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def create(self, payload: DataSourceCreate, admin_id: str) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        values["language_codes_json"] = dumps_json(values.pop("language_codes"))
        values["created_by_admin_public_id"] = admin_id
        with self.repository.transaction() as connection:
            existing = self.repository.source_by_code(connection, values["source_code"])
            if existing is not None:
                raise ValidationError(f"source_code already exists: {values['source_code']}")
            public_id = self.repository.create_source(connection, values)
            self._audit(
                connection,
                "data_source_created",
                admin_id,
                public_id,
                source_code=values["source_code"],
            )
            return public_row(self.repository.source(connection, public_id))

    def get(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.source(connection, public_id))

    def list(
        self,
        *,
        status: str | None = None,
        source_type: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size
        with self.repository.transaction() as connection:
            rows, total = self.repository.list_sources(
                connection,
                status=status,
                source_type=source_type,
                search=search,
                limit=page_size,
                offset=offset,
            )
            items = [public_row(row) for row in rows]
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }

    def update(self, public_id: str, patch: DataSourcePatch, admin_id: str) -> dict[str, Any]:
        fields = patch.model_dump(mode="json", exclude_unset=True)
        if "language_codes" in fields:
            fields["language_codes_json"] = dumps_json(fields.pop("language_codes"))
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, public_id)
            if source["status"] == "archived":
                raise ValidationError("an archived source must be restored before it can be edited")
            self.repository.update_source(connection, source["id"], fields)
            self._audit(connection, "data_source_updated", admin_id, public_id, fields=list(fields))
            return public_row(self.repository.source(connection, public_id))

    def archive(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition_status(
            public_id, "archived", admin_id, event="data_source_archived"
        )

    def restore(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition_status(public_id, "draft", admin_id, event="data_source_restored")

    def _transition_status(
        self, public_id: str, new_status: str, admin_id: str, *, event: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, public_id)
            allowed = _SOURCE_STATUS_TRANSITIONS.get(source["status"], set())
            if new_status not in allowed:
                raise ValidationError(
                    f"cannot move source from status {source['status']!r} to {new_status!r}"
                )
            self.repository.update_source(connection, source["id"], {"status": new_status})
            self._audit(
                connection,
                event,
                admin_id,
                public_id,
                previous_status=source["status"],
                new_status=new_status,
            )
            return public_row(self.repository.source(connection, public_id))

    # --- links ------------------------------------------------------

    def create_link(self, public_id: str, payload: LinkCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, public_id)
            if source["status"] == "archived":
                raise ValidationError("an archived source cannot receive new links")
            values = payload.model_dump(mode="json")
            values["data_source_id"] = source["id"]
            values["created_by_admin_public_id"] = admin_id
            link_public_id = self.repository.create_link(connection, values)
            self._audit(
                connection,
                "source_link_created",
                admin_id,
                public_id,
                entity_type=values["entity_type"],
                entity_public_id=values["entity_public_id"],
            )
            return public_row(self.repository.link(connection, link_public_id))

    def list_links(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, public_id)
            items = [
                public_row(row) for row in self.repository.list_links(connection, source["id"])
            ]
            return {"items": items}

    def delete_link(self, public_id: str, link_public_id: str, admin_id: str) -> None:
        with self.repository.transaction() as connection:
            self.repository.source(connection, public_id)
            link = self.repository.link(connection, link_public_id)
            self.repository.delete_link(connection, link["id"])
            self._audit(
                connection,
                "source_link_deleted",
                admin_id,
                public_id,
                link_public_id=link_public_id,
            )

    def history(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, public_id)
            events = [
                public_row(row)
                for row in self.repository.list_verification_events(connection, source["id"])
            ]
            decisions = [
                public_row(row)
                for row in self.repository.list_usage_decisions(connection, source["id"])
            ]
            links = [
                public_row(row) for row in self.repository.list_links(connection, source["id"])
            ]
        return {
            "verification_events": events,
            "usage_decisions": decisions,
            "links": links,
        }

    # --- audit -----------------------------------------------------

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        _write_audit(connection, self.settings, event, admin_id, resource_id, **metadata)


class SourceRightsService:
    def __init__(self, repository: DataSourceRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def get(self, source_public_id: str) -> dict[str, Any] | None:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, source_public_id)
            row = self.repository.rights_for_source(connection, source["id"])
            return public_row(row) if row else None

    def upsert(
        self, source_public_id: str, payload: SourceRightsUpsert, admin_id: str
    ) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        errors = validate_rights_combination(values)
        if errors:
            raise ValidationError("; ".join(errors))
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, source_public_id)
            existing = self.repository.rights_for_source(connection, source["id"])
            if existing is None:
                self.repository.create_rights(connection, source["id"], values)
                event = "source_rights_created"
            else:
                self.repository.update_rights(connection, existing["id"], values)
                event = "source_rights_updated"
            self._audit(
                connection, event, admin_id, source_public_id, rights_status=values["rights_status"]
            )
            return public_row(self.repository.rights_for_source(connection, source["id"]))

    def submit_review(self, source_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, source_public_id)
            rights = self.repository.rights_for_source(connection, source["id"])
            if rights is None:
                raise ValidationError(
                    "a rights declaration must exist before it can be submitted for review"
                )
            # Only downgrade to pending_review when nothing concrete has been
            # declared yet -- an admin who already asserted a specific
            # rights_status (open_license, licensed, permission_granted, ...)
            # keeps that self-declared assertion through review; submitting
            # for review must never silently erase it.
            if rights["rights_status"] == "unknown":
                self.repository.update_rights(
                    connection, rights["id"], {"rights_status": "pending_review"}
                )
            allowed = _SOURCE_STATUS_TRANSITIONS.get(source["status"], set())
            if "needs_review" in allowed:
                self.repository.update_source(connection, source["id"], {"status": "needs_review"})
            self._audit(
                connection, "source_rights_submitted_for_review", admin_id, source_public_id
            )
            return public_row(self.repository.rights_for_source(connection, source["id"]))

    def verify(
        self, source_public_id: str, request: VerificationActionRequest, admin_id: str
    ) -> dict[str, Any]:
        return self._apply_verification_action(
            source_public_id, request, admin_id, target_source_status="verified"
        )

    def restrict(
        self, source_public_id: str, request: VerificationActionRequest, admin_id: str
    ) -> dict[str, Any]:
        return self._apply_verification_action(
            source_public_id, request, admin_id, target_source_status="restricted"
        )

    def reject(
        self, source_public_id: str, request: VerificationActionRequest, admin_id: str
    ) -> dict[str, Any]:
        return self._apply_verification_action(
            source_public_id, request, admin_id, target_source_status="rejected"
        )

    def _apply_verification_action(
        self,
        source_public_id: str,
        request: VerificationActionRequest,
        admin_id: str,
        *,
        target_source_status: str,
    ) -> dict[str, Any]:
        verification_status_after = _VERIFICATION_ACTION_STATUS[request.action]
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, source_public_id)
            allowed = _SOURCE_STATUS_TRANSITIONS.get(source["status"], set())
            if target_source_status not in allowed:
                raise ValidationError(
                    f"cannot move source from status {source['status']!r} "
                    f"to {target_source_status!r}"
                )
            rights = self.repository.rights_for_source(connection, source["id"])
            rights_fields: dict[str, Any] = {"verification_status": verification_status_after}
            if request.action == "reject":
                rights_fields["rights_status"] = "prohibited"
            elif request.action == "expire":
                rights_fields["rights_status"] = "expired"
            if rights is not None:
                self.repository.update_rights(connection, rights["id"], rights_fields)
                self.repository.update_rights(
                    connection,
                    rights["id"],
                    {"verified_by_admin_public_id": admin_id, "verified_at": _now()},
                )
            self.repository.update_source(
                connection, source["id"], {"status": target_source_status}
            )
            # Append-only verification history -- never overwritten, always a
            # new row, even if the same action is repeated later.
            self.repository.add_verification_event(
                connection,
                {
                    "data_source_id": source["id"],
                    "action": request.action,
                    "verification_status_after": verification_status_after,
                    "performed_by_admin_public_id": admin_id,
                    "evidence_reference": request.evidence_reference,
                    "notes": request.notes,
                },
            )
            self._audit(
                connection,
                f"source_verification_{request.action}",
                admin_id,
                source_public_id,
                new_source_status=target_source_status,
            )
            return public_row(self.repository.source(connection, source_public_id))

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        _write_audit(connection, self.settings, event, admin_id, resource_id, **metadata)


class SourceUsagePolicyService:
    def __init__(self, repository: DataSourceRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def evaluate(
        self, source_public_id: str, target_use: str, *, admin_id: str | None = None
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, source_public_id)
            rights_row = self.repository.rights_for_source(connection, source["id"])
            rights = rights_from_source_rights_row(public_row(rights_row)) if rights_row else None
            decision = evaluate_source_usage(
                source=public_row(source), rights=rights, target_use=target_use
            )
            self.repository.add_usage_decision(
                connection,
                {
                    "data_source_id": source["id"],
                    "target_use": target_use,
                    "allowed": decision["allowed"],
                    "decision_code": decision["decision_code"],
                    "blocking_reasons_json": dumps_json(decision["blocking_reasons"]),
                    "warnings_json": dumps_json(decision["warnings"]),
                    "required_actions_json": dumps_json(decision["required_actions"]),
                    "evaluated_by_admin_public_id": admin_id,
                },
            )
            if admin_id:
                self._audit(
                    connection,
                    "source_usage_checked",
                    admin_id,
                    source_public_id,
                    target_use=target_use,
                    decision_code=decision["decision_code"],
                )
            return decision

    def effective_permissions(self, source_public_id: str) -> dict[str, Any]:
        target_uses = (
            "rag",
            "training",
            "evaluation",
            "commercial",
            "public_export",
            "redistribution",
        )
        return {
            target_use: self.evaluate(source_public_id, target_use) for target_use in target_uses
        }

    def rights_summary_for_entities(
        self, entity_type: str, entity_public_ids: list[str], target_use: str
    ) -> dict[str, Any]:
        """Preflight for an existing system (dataset build, RAG ingestion,
        pretraining readiness, export) to check a batch of entities against
        this registry without changing that system's own contract.

        Rule 6/7: an entity with no ``source_record_links`` row at all is
        reported as ``unlinked`` -- never silently treated as blocked *or*
        as allowed, since this new registry has no evidence about it either
        way. Only entities that are explicitly linked get a real policy
        decision, and if an entity has more than one linked source, the
        entity is blocked unless *every* linked source allows the use
        (the weakest link governs).
        """

        total = len(entity_public_ids)
        unlinked: list[str] = []
        allowed: list[str] = []
        blocked: list[str] = []
        review_required: list[str] = []
        blocking_reasons: dict[str, list[str]] = {}

        with self.repository.transaction() as connection:
            for entity_public_id in entity_public_ids:
                links = self.repository.links_for_entity(connection, entity_type, entity_public_id)
                if not links:
                    unlinked.append(entity_public_id)
                    continue
                entity_reasons: list[str] = []
                entity_allowed = True
                entity_review_required = False
                for link in links:
                    source = self.repository.source_by_id(connection, link["data_source_id"])
                    rights_row = self.repository.rights_for_source(connection, source["id"])
                    rights = (
                        rights_from_source_rights_row(public_row(rights_row))
                        if rights_row
                        else None
                    )
                    decision = evaluate_source_usage(
                        source=public_row(source), rights=rights, target_use=target_use
                    )
                    if decision["decision_code"] == "REVIEW_REQUIRED_INTERNAL_RAG":
                        entity_review_required = True
                    if not decision["allowed"]:
                        entity_allowed = False
                        entity_reasons.extend(decision["blocking_reasons"])
                if entity_review_required and entity_allowed:
                    review_required.append(entity_public_id)
                elif entity_allowed:
                    allowed.append(entity_public_id)
                else:
                    blocked.append(entity_public_id)
                    blocking_reasons[entity_public_id] = entity_reasons

        return {
            "target_use": target_use,
            "total": total,
            "unlinked_count": len(unlinked),
            "allowed_count": len(allowed),
            "blocked_count": len(blocked),
            "review_required_count": len(review_required),
            "unlinked": unlinked,
            "allowed": allowed,
            "blocked": blocked,
            "review_required": review_required,
            "blocking_reasons": blocking_reasons,
        }

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        _write_audit(connection, self.settings, event, admin_id, resource_id, **metadata)


class SourceVerificationService:
    """Read access to the append-only verification history. Writes only
    ever happen via ``SourceRightsService``'s transition methods, which
    call the repository directly within their own transaction -- this
    class exists so callers who only need the history don't have to
    depend on the rights service."""

    def __init__(self, repository: DataSourceRepository) -> None:
        self.repository = repository

    def list_events(self, source_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, source_public_id)
            items = [
                public_row(row)
                for row in self.repository.list_verification_events(connection, source["id"])
            ]
            return {"items": items}


def _write_audit(
    connection, settings: Settings, event: str, admin_id: str, resource_id: str, **metadata: Any
) -> None:
    if not settings.audit_enabled:
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
            "data_source",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


__all__ = [
    "NotFoundError",
    "SourceRegistryService",
    "SourceRightsService",
    "SourceUsagePolicyService",
    "SourceVerificationService",
]
