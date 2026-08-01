"""Services for the Phase 3 Manual Data Studio.

A staging layer for hand-authored records (Tamil/English/Tanglish
examples, conversations, Q&A, instructions, dictionary entries,
translations, knowledge notes) that funnels into the existing dataset
pipeline only through an explicit "create dataset candidate" action
(``backend/services/manual_data_candidate_service.py``) -- this module
never writes to ``dataset_records`` itself.

Every mutation runs inside the repository's transaction and appends both
a general ``audit_logs`` row (matching ``dataset_service.py``'s ``_audit``
convention) and a domain-specific ``manual_data_events`` row (matching
Phase 2's ``source_verification_events`` convention), so both the
system-wide audit trail and the record's own "History" tab stay
populated. Usage-eligibility decisions are never computed inline --
they always go through ``core_model.manual_data.usage_policy``, which
itself calls Phase 2's ``evaluate_source_usage`` rather than duplicating
rights logic (rule 15).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ConflictError, NotFoundError, ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.data_sources import public_row as source_public_row
from backend.database.repositories.manual_data import ManualDataRepository, public_row
from backend.models.manual_data import (
    ApprovalRequest,
    ManualDataRecordCreate,
    ManualDataRecordPatch,
    RejectRequest,
    ReviewRequest,
    RevisionCreate,
    VerificationRequest,
)
from backend.services.data_source_service import SourceRegistryService
from core_model.data_governance.usage_policy import rights_from_source_rights_row
from core_model.manual_data.duplicates import content_hash, dictionary_word_key
from core_model.manual_data.lifecycle import validate_transition as _validate_transition_raw
from core_model.manual_data.quality import assess_quality
from core_model.manual_data.usage_policy import evaluate_manual_record_usage
from core_model.manual_data.validation import validate_record_fields

TARGET_USES = ("rag", "training", "evaluation", "commercial", "public_export", "redistribution")


def _validate_transition(current_status: str, target_status: str) -> None:
    """`core_model.manual_data.lifecycle.validate_transition` raises a bare
    `ValueError` (it is a pure, framework-agnostic module) -- translate
    that into the repository layer's `ValidationError` here so an invalid
    transition surfaces as a clean 422 through the standard exception
    handler instead of falling through to the generic 500 handler."""

    try:
        _validate_transition_raw(current_status, target_status)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


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


def _record_event(
    repository: ManualDataRepository,
    connection,
    record_id: int,
    event_type: str,
    admin_id: str,
    *,
    status_before: str | None = None,
    status_after: str | None = None,
    notes: str = "",
    **metadata: Any,
) -> None:
    repository.add_event(
        connection,
        {
            "record_id": record_id,
            "event_type": event_type,
            "status_before": status_before,
            "status_after": status_after,
            "performed_by_admin_public_id": admin_id,
            "notes": notes,
            "metadata_json": dumps_json(metadata),
        },
    )


def _next_record_code(connection) -> str:
    rows = connection.execute(
        "SELECT record_code FROM manual_data_records WHERE record_code LIKE 'MD-%'"
    ).fetchall()
    max_number = 0
    for row in rows:
        suffix = row[0].removeprefix("MD-")
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return f"MD-{max_number + 1:04d}"


def _split_content(
    content: dict[str, Any],
) -> tuple[dict[str, Any], list[Any], list[Any], dict[str, Any]]:
    """Split a `ManualRecordContentInput.model_dump()` dict into the
    revision table's typed columns plus its three JSON blobs. `turns`
    (structured, conversation-specific) folds into `metadata` since
    there is no dedicated column for it (Step 4: JSON only for
    structured optional data)."""

    content = dict(content)
    meanings = content.pop("meanings", []) or []
    examples = content.pop("examples", []) or []
    turns = content.pop("turns", []) or []
    metadata = content.pop("metadata", {}) or {}
    if turns:
        metadata = {**metadata, "turns": turns}
    return content, meanings, examples, metadata


def _check_fields(record_row: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
    """Merge a record's classification with its (revision) content into
    the flat dict shape `validate_record_fields`/`assess_quality` expect.
    Works whether `content` came from a fresh
    `ManualRecordContentInput.model_dump()` (has a top-level `turns` key)
    or from a persisted revision's `public_row()` (turns live inside
    `metadata.turns`)."""

    metadata = content.get("metadata") or {}
    turns = content.get("turns") or metadata.get("turns") or []
    return {
        "primary_language": record_row.get("primary_language"),
        "input_language": record_row.get("input_language"),
        "output_language": record_row.get("output_language"),
        "knowledge_risk": record_row.get("knowledge_risk"),
        "fact_dependency": record_row.get("fact_dependency"),
        "review_expiry_at": record_row.get("review_expiry_at"),
        "title": content.get("title"),
        "input_text": content.get("input_text"),
        "output_text": content.get("output_text"),
        "instruction_text": content.get("instruction_text"),
        "response_text": content.get("response_text"),
        "question_text": content.get("question_text"),
        "answer_text": content.get("answer_text"),
        "tamil_text": content.get("tamil_text"),
        "english_text": content.get("english_text"),
        "tanglish_text": content.get("tanglish_text"),
        "word": content.get("word"),
        "part_of_speech": content.get("part_of_speech"),
        "meanings": content.get("meanings") or [],
        "examples": content.get("examples") or [],
        "turns": turns,
    }


class ManualDataRecordService:
    def __init__(
        self,
        repository: ManualDataRepository,
        source_repository: DataSourceRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.source_repository = source_repository
        self.settings = settings

    # --- source resolution ------------------------------------------------

    def _resolve_source_id(self, payload: ManualDataRecordCreate, admin_id: str) -> int:
        if payload.source_public_id:
            with self.source_repository.transaction() as connection:
                source = self.source_repository.source(connection, payload.source_public_id)
                return source["id"]
        if payload.new_source:
            registry = SourceRegistryService(self.source_repository, self.settings)
            created = registry.create(payload.new_source, admin_id)
            with self.source_repository.transaction() as connection:
                return self.source_repository.source(connection, created["public_id"])["id"]
        raise ValidationError(
            "every manual data record must be traceable to a source -- "
            "provide source_public_id or new_source"
        )

    # --- enrichment ---------------------------------------------------

    def _public_record(self, connection, row) -> dict[str, Any]:
        data = public_row(row)
        source = self.source_repository.source_by_id(connection, row["source_id"])
        data["source_public_id"] = source["public_id"]
        data["source_title"] = source["title"]
        if row["active_revision_id"]:
            revision = self.repository.revision_by_id(connection, row["active_revision_id"])
            data["active_revision"] = public_row(revision)
        else:
            data["active_revision"] = None
        return data

    # --- CRUD -----------------------------------------------------------

    def create(self, payload: ManualDataRecordCreate, admin_id: str) -> dict[str, Any]:
        source_id = self._resolve_source_id(payload, admin_id)
        content = payload.content.model_dump(mode="json")
        record_classification = {
            "primary_language": payload.primary_language,
            "input_language": payload.input_language,
            "output_language": payload.output_language,
            "knowledge_risk": payload.knowledge_risk,
            "fact_dependency": payload.fact_dependency,
            "review_expiry_at": payload.review_expiry_at,
        }
        check_fields = _check_fields(record_classification, content)
        errors = validate_record_fields(payload.record_type, check_fields)
        if errors:
            raise ValidationError("; ".join(errors))

        digest = content_hash(payload.record_type, check_fields)
        with self.repository.transaction() as connection:
            duplicate = self.repository.content_hash_exists(connection, digest)
            if duplicate is not None:
                raise ConflictError(
                    f"duplicate manual data content: revision {duplicate['public_id']}"
                )
            if payload.record_type == "dictionary_entry":
                word_key = dictionary_word_key(check_fields.get("word"), payload.primary_language)
                if word_key and self.repository.dictionary_word_exists(connection, word_key):
                    raise ConflictError(
                        f"a dictionary entry for {check_fields.get('word')!r} already exists"
                    )

            record_code = _next_record_code(connection)
            record_public_id = self.repository.create_record(
                connection,
                {
                    "record_code": record_code,
                    "record_type": payload.record_type,
                    "source_id": source_id,
                    "primary_language": payload.primary_language,
                    "input_language": payload.input_language,
                    "output_language": payload.output_language,
                    "domain": payload.domain,
                    "topic": payload.topic,
                    "difficulty": payload.difficulty,
                    "audience": payload.audience,
                    "style": payload.style,
                    "fact_dependency": payload.fact_dependency,
                    "knowledge_risk": payload.knowledge_risk,
                    "creation_method": payload.creation_method,
                    "requested_uses_json": dumps_json(payload.requested_uses),
                    "review_expiry_at": payload.review_expiry_at,
                    "created_by_admin_public_id": admin_id,
                },
            )
            record_id = self.repository.record(connection, record_public_id)["id"]

            columns, meanings, examples, metadata = _split_content(content)
            revision_public_id = self.repository.create_revision(
                connection,
                {
                    "record_id": record_id,
                    "revision_number": 1,
                    **columns,
                    "meanings_json": dumps_json(meanings),
                    "examples_json": dumps_json(examples),
                    "metadata_json": dumps_json(metadata),
                    "content_hash": digest,
                    "change_summary": payload.change_summary or "initial draft",
                    "created_by_admin_public_id": admin_id,
                },
            )
            revision_id = self.repository.revision(connection, revision_public_id)["id"]
            self.repository.update_record(
                connection, record_id, {"active_revision_id": revision_id}
            )

            _record_event(
                self.repository,
                connection,
                record_id,
                "record_created",
                admin_id,
                status_after="draft",
            )
            _audit(
                connection,
                "manual_data_record_created",
                admin_id,
                record_public_id,
                record_type=payload.record_type,
            )
            return self._public_record(
                connection, self.repository.record(connection, record_public_id)
            )

    def get(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self._public_record(connection, self.repository.record(connection, public_id))

    def list(
        self,
        *,
        status: str | None = None,
        record_type: str | None = None,
        creation_method: str | None = None,
        knowledge_risk: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size
        with self.repository.transaction() as connection:
            rows, total = self.repository.list_records(
                connection,
                status=status,
                record_type=record_type,
                creation_method=creation_method,
                knowledge_risk=knowledge_risk,
                search=search,
                limit=page_size,
                offset=offset,
            )
            items = [self._public_record(connection, row) for row in rows]
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }

    def summary(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            by_status = self.repository.summary_counts(connection)
            by_type = self.repository.counts_by(connection, "record_type")
            by_language = self.repository.counts_by(connection, "primary_language")
            by_creation_method = self.repository.counts_by(connection, "creation_method")
            total = sum(by_status.values())
        return {
            "total": total,
            "by_status": by_status,
            "by_record_type": by_type,
            "by_primary_language": by_language,
            "by_creation_method": by_creation_method,
        }

    def update(self, public_id: str, patch: ManualDataRecordPatch, admin_id: str) -> dict[str, Any]:
        fields = patch.model_dump(mode="json", exclude_unset=True)
        if "requested_uses" in fields:
            fields["requested_uses_json"] = dumps_json(fields.pop("requested_uses"))
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            if record["status"] in ("approved", "archived"):
                raise ValidationError(
                    "an approved or archived record cannot be patched directly -- "
                    "create a new revision or restore it first"
                )
            self.repository.update_record(connection, record["id"], fields)
            _audit(
                connection, "manual_data_record_updated", admin_id, public_id, fields=list(fields)
            )
            return self._public_record(connection, self.repository.record(connection, public_id))

    # --- revisions --------------------------------------------------------

    def create_revision(
        self, public_id: str, payload: RevisionCreate, admin_id: str
    ) -> dict[str, Any]:
        content = payload.content.model_dump(mode="json")
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            if record["status"] == "rejected":
                raise ValidationError("a rejected record must be moved back to draft first")
            if record["status"] == "archived":
                raise ValidationError("an archived record must be restored before editing")

            check_fields = _check_fields(dict(record), content)
            errors = validate_record_fields(record["record_type"], check_fields)
            if errors:
                raise ValidationError("; ".join(errors))

            digest = content_hash(record["record_type"], check_fields)
            duplicate = self.repository.content_hash_exists(
                connection, digest, exclude_record_id=record["id"]
            )
            if duplicate is not None:
                raise ConflictError(
                    f"duplicate manual data content: revision {duplicate['public_id']}"
                )

            next_number = self.repository.latest_revision_number(connection, record["id"]) + 1
            columns, meanings, examples, metadata = _split_content(content)
            revision_public_id = self.repository.create_revision(
                connection,
                {
                    "record_id": record["id"],
                    "revision_number": next_number,
                    **columns,
                    "meanings_json": dumps_json(meanings),
                    "examples_json": dumps_json(examples),
                    "metadata_json": dumps_json(metadata),
                    "content_hash": digest,
                    "change_summary": payload.change_summary,
                    "created_by_admin_public_id": admin_id,
                },
            )
            revision_id = self.repository.revision(connection, revision_public_id)["id"]

            new_status = "draft" if record["status"] == "approved" else record["status"]
            self.repository.update_record(
                connection,
                record["id"],
                {"active_revision_id": revision_id, "status": new_status},
            )
            _record_event(
                self.repository,
                connection,
                record["id"],
                "revision_created",
                admin_id,
                status_before=record["status"],
                status_after=new_status,
                revision_number=next_number,
            )
            _audit(
                connection,
                "manual_data_revision_created",
                admin_id,
                public_id,
                revision_number=next_number,
            )
            return self._public_record(connection, self.repository.record(connection, public_id))

    def list_revisions(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            items = [
                public_row(row) for row in self.repository.list_revisions(connection, record["id"])
            ]
            return {"items": items, "active_revision_id": record["active_revision_id"]}

    def get_revision(self, public_id: str, revision_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            self.repository.record(connection, public_id)
            return public_row(self.repository.revision(connection, revision_public_id))

    # --- lifecycle transitions ---------------------------------------------

    def _transition(
        self,
        public_id: str,
        target_status: str,
        admin_id: str,
        *,
        event: str,
        notes: str = "",
        **metadata: Any,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            _validate_transition(record["status"], target_status)
            self.repository.update_record(connection, record["id"], {"status": target_status})
            _record_event(
                self.repository,
                connection,
                record["id"],
                event,
                admin_id,
                status_before=record["status"],
                status_after=target_status,
                notes=notes,
                **metadata,
            )
            _audit(connection, event, admin_id, public_id, new_status=target_status)
            return self._public_record(connection, self.repository.record(connection, public_id))

    def submit_review(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition(
            public_id, "needs_review", admin_id, event="manual_data_submitted_for_review"
        )

    def request_correction(self, public_id: str, admin_id: str, notes: str = "") -> dict[str, Any]:
        return self._transition(
            public_id, "draft", admin_id, event="manual_data_correction_requested", notes=notes
        )

    def request_source_verification(
        self, public_id: str, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        return self._transition(
            public_id,
            "needs_source_verification",
            admin_id,
            event="manual_data_source_verification_requested",
            notes=notes,
        )

    def request_domain_review(
        self, public_id: str, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        return self._transition(
            public_id,
            "needs_domain_review",
            admin_id,
            event="manual_data_domain_review_requested",
            notes=notes,
        )

    def reject(self, public_id: str, payload: RejectRequest, admin_id: str) -> dict[str, Any]:
        return self._transition(
            public_id, "rejected", admin_id, event="manual_data_rejected", notes=payload.reason
        )

    def archive(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition(public_id, "archived", admin_id, event="manual_data_archived")

    def restore(self, public_id: str, admin_id: str) -> dict[str, Any]:
        return self._transition(public_id, "draft", admin_id, event="manual_data_restored")

    def approve(
        self,
        public_id: str,
        payload: ApprovalRequest,
        admin_id: str,
        *,
        usage_service: ManualDataUsageService,
    ) -> dict[str, Any]:
        """Approval never blindly trusts the reviewer's requested uses --
        every requested use is re-checked against the full policy gate
        (rule 7: no manual record becomes training-ready solely because
        an admin created it) with the record's status treated as already
        `approved` for that check. A use that would still be blocked
        (unreviewed AI content, unverified high-risk facts, source
        rights) is silently dropped from the granted set and reported
        back as blocked, never granted anyway."""

        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            _validate_transition(record["status"], "approved")
            quality = self._assess_for_gate(connection, record)
            if quality["blocking_issues"]:
                raise ValidationError(
                    "record cannot be approved while blocking issues remain: "
                    + ", ".join(quality["blocking_issues"])
                )

        granted: list[str] = []
        blocked: dict[str, str] = {}
        hypothetical_record = dict(record)
        hypothetical_record["status"] = "approved"
        for target_use in payload.approved_uses:
            decision = usage_service.evaluate_for_record(
                hypothetical_record, target_use, admin_id=None, persist=False
            )
            if decision["allowed"]:
                granted.append(target_use)
            else:
                blocked[target_use] = decision["decision_code"]

        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            self.repository.update_record(
                connection,
                record["id"],
                {"status": "approved", "approved_uses_json": dumps_json(granted)},
            )
            _record_event(
                self.repository,
                connection,
                record["id"],
                "manual_data_approved",
                admin_id,
                status_before=record["status"],
                status_after="approved",
                notes=payload.notes,
                approved_uses=granted,
                blocked_uses=blocked,
            )
            _audit(
                connection,
                "manual_data_approved",
                admin_id,
                public_id,
                approved_uses=granted,
                blocked_uses=blocked,
            )
            data = self._public_record(connection, self.repository.record(connection, public_id))
        data["blocked_uses"] = blocked
        return data

    def _assess_for_gate(self, connection, record) -> dict[str, Any]:
        active_revision = (
            public_row(self.repository.revision_by_id(connection, record["active_revision_id"]))
            if record["active_revision_id"]
            else {}
        )
        reviews = [public_row(r) for r in self.repository.list_reviews(connection, record["id"])]
        verifications = [
            public_row(v) for v in self.repository.list_verifications(connection, record["id"])
        ]
        fields = _check_fields(dict(record), active_revision)
        return assess_quality(
            record=dict(record),
            fields=fields,
            reviews=reviews,
            verifications=verifications,
        )

    # --- history ------------------------------------------------------

    def history(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            events = [
                public_row(row) for row in self.repository.list_events(connection, record["id"])
            ]
            reviews = [
                public_row(row) for row in self.repository.list_reviews(connection, record["id"])
            ]
            verifications = [
                public_row(row)
                for row in self.repository.list_verifications(connection, record["id"])
            ]
            usage_decisions = [
                public_row(row)
                for row in self.repository.list_usage_decisions(connection, record["id"])
            ]
            revisions = [
                public_row(row) for row in self.repository.list_revisions(connection, record["id"])
            ]
        return {
            "events": events,
            "reviews": reviews,
            "verifications": verifications,
            "usage_decisions": usage_decisions,
            "revisions": revisions,
        }


class ManualDataReviewService:
    def __init__(self, repository: ManualDataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def submit(self, public_id: str, payload: ReviewRequest, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            if not record["active_revision_id"]:
                raise ValidationError("record has no active revision to review")
            values = payload.model_dump(mode="json")
            self.repository.create_review(
                connection,
                {
                    "record_id": record["id"],
                    "revision_id": record["active_revision_id"],
                    "reviewer_admin_public_id": admin_id,
                    **values,
                },
            )
            _record_event(
                self.repository,
                connection,
                record["id"],
                "review_submitted",
                admin_id,
                review_type=payload.review_type,
                review_status=payload.review_status,
            )
            _audit(
                connection,
                "manual_data_review_submitted",
                admin_id,
                public_id,
                review_type=payload.review_type,
                review_status=payload.review_status,
            )
            return public_row(self.repository.list_reviews(connection, record["id"])[0])

    def list(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            items = [public_row(r) for r in self.repository.list_reviews(connection, record["id"])]
            return {"items": items}


class ManualDataVerificationService:
    def __init__(
        self,
        repository: ManualDataRepository,
        source_repository: DataSourceRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.source_repository = source_repository
        self.settings = settings

    def submit(self, public_id: str, payload: VerificationRequest, admin_id: str) -> dict[str, Any]:
        supporting_source_id = None
        if payload.source_public_id:
            with self.source_repository.transaction() as connection:
                supporting_source_id = self.source_repository.source(
                    connection, payload.source_public_id
                )["id"]
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            if not record["active_revision_id"]:
                raise ValidationError("record has no active revision to verify")
            verified_at = None
            verified_by = None
            if payload.verification_status in ("verified", "rejected", "expired"):
                verified_at = _now()
                verified_by = admin_id
            verification_public_id = self.repository.create_verification(
                connection,
                {
                    "record_id": record["id"],
                    "revision_id": record["active_revision_id"],
                    "verification_type": payload.verification_type,
                    "verification_status": payload.verification_status,
                    "source_id": supporting_source_id,
                    "verified_by_admin_public_id": verified_by,
                    "verification_notes": payload.verification_notes,
                    "verified_at": verified_at,
                },
            )
            _record_event(
                self.repository,
                connection,
                record["id"],
                "verification_recorded",
                admin_id,
                verification_type=payload.verification_type,
                verification_status=payload.verification_status,
            )
            _audit(
                connection,
                "manual_data_verification_recorded",
                admin_id,
                public_id,
                verification_type=payload.verification_type,
                verification_status=payload.verification_status,
            )
            for row in self.repository.list_verifications(connection, record["id"]):
                if row["public_id"] == verification_public_id:
                    return public_row(row)
            raise NotFoundError("verification not found immediately after creation")

    def list(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            items = [
                public_row(v) for v in self.repository.list_verifications(connection, record["id"])
            ]
            return {"items": items}


class ManualDataQualityService:
    def __init__(self, repository: ManualDataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def assess(self, public_id: str, *, duplicate_status: str = "unique") -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            active_revision = (
                public_row(self.repository.revision_by_id(connection, record["active_revision_id"]))
                if record["active_revision_id"]
                else {}
            )
            reviews = [
                public_row(r) for r in self.repository.list_reviews(connection, record["id"])
            ]
            verifications = [
                public_row(v) for v in self.repository.list_verifications(connection, record["id"])
            ]
        fields = _check_fields(dict(record), active_revision)
        return assess_quality(
            record=dict(record),
            fields=fields,
            reviews=reviews,
            verifications=verifications,
            duplicate_status=duplicate_status,
        )

    def check_duplicates(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            active_revision = (
                public_row(self.repository.revision_by_id(connection, record["active_revision_id"]))
                if record["active_revision_id"]
                else {}
            )
            fields = _check_fields(dict(record), active_revision)
            digest = content_hash(record["record_type"], fields)
            exact = self.repository.content_hash_exists(
                connection, digest, exclude_record_id=record["id"]
            )
            matches: list[str] = []
            status = "unique"
            reason = ""
            if exact is not None:
                match_record = self.repository.record_by_id(connection, exact["record_id"])
                matches.append(match_record["public_id"])
                status = "exact_duplicate"
                reason = "identical normalized content already exists"
            if record["record_type"] == "dictionary_entry":
                word_key = dictionary_word_key(fields.get("word"), record["primary_language"])
                if word_key:
                    existing = self.repository.dictionary_word_exists(
                        connection, word_key, exclude_record_id=record["id"]
                    )
                    if existing is not None:
                        match_record = self.repository.record_by_id(
                            connection, existing["record_id"]
                        )
                        if match_record["public_id"] not in matches:
                            matches.append(match_record["public_id"])
                        status = "exact_duplicate"
                        reason = f"a dictionary entry for {fields.get('word')!r} already exists"
        return {
            "duplicate_status": status,
            "matching_record_ids": matches,
            "similarity_or_match_reason": reason,
            "recommended_action": "keep_both_and_review" if status != "unique" else "none",
        }


class ManualDataUsageService:
    def __init__(
        self,
        repository: ManualDataRepository,
        source_repository: DataSourceRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.source_repository = source_repository
        self.settings = settings

    def _source_and_rights(self, source_id: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
        with self.source_repository.transaction() as connection:
            source = source_public_row(self.source_repository.source_by_id(connection, source_id))
            rights_row = self.source_repository.rights_for_source(connection, source_id)
            rights = (
                rights_from_source_rights_row(source_public_row(rights_row)) if rights_row else None
            )
            return source, rights

    def evaluate_for_record(
        self,
        record: dict[str, Any],
        target_use: str,
        *,
        admin_id: str | None,
        persist: bool = True,
    ) -> dict[str, Any]:
        source, rights = self._source_and_rights(record["source_id"])
        with self.repository.transaction() as connection:
            verifications = [
                public_row(v) for v in self.repository.list_verifications(connection, record["id"])
            ]
        decision = evaluate_manual_record_usage(
            record=record,
            source=source,
            rights=rights,
            verifications=verifications,
            target_use=target_use,
        )
        if persist:
            with self.repository.transaction() as connection:
                self.repository.add_usage_decision(
                    connection,
                    {
                        "record_id": record["id"],
                        "revision_id": record["active_revision_id"],
                        "target_use": target_use,
                        "allowed": decision["allowed"],
                        "decision_code": decision["decision_code"],
                        "blocking_reasons_json": dumps_json(decision["blocking_reasons"]),
                        "warnings_json": dumps_json(decision["warnings"]),
                        "evaluated_by_admin_public_id": admin_id,
                    },
                )
                if admin_id:
                    _audit(
                        connection,
                        "manual_data_usage_checked",
                        admin_id,
                        record["public_id"],
                        target_use=target_use,
                        decision_code=decision["decision_code"],
                    )
        return decision

    def evaluate(
        self, public_id: str, target_use: str, *, admin_id: str | None = None
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = dict(self.repository.record(connection, public_id))
        if not record["active_revision_id"]:
            raise ValidationError("record has no active revision to evaluate")
        return self.evaluate_for_record(record, target_use, admin_id=admin_id)

    def summary(self, public_id: str) -> dict[str, Any]:
        return {target_use: self.evaluate(public_id, target_use) for target_use in TARGET_USES}

    def history(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            record = self.repository.record(connection, public_id)
            items = [
                public_row(d)
                for d in self.repository.list_usage_decisions(connection, record["id"])
            ]
            return {"items": items}


__all__ = [
    "ManualDataQualityService",
    "ManualDataRecordService",
    "ManualDataReviewService",
    "ManualDataUsageService",
    "ManualDataVerificationService",
]
