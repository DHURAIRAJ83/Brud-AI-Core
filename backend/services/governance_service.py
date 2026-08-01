"""Services for the Phase 6 unified governance layer: one consolidated
review queue, quality normalization, duplicate/conflict grouping, and
per-target-use approval across the six existing, independently-owned
entity types (see
docs/data_studio/phase6_quality_duplicate_conflict_approval_plan.md).

This module never re-implements quality scoring, duplicate/conflict
pairwise detection, or usage-eligibility -- it calls the *existing*
`DatasetQualityService`/`ManualDataQualityService`/`SemanticChunkQualityService`,
`core_model.*.duplicates`, and `ManualDataUsageService`/
`StructuredRecordCandidateService.usage_check`/`evaluate_source_usage`,
then persists the result as a queue item, a duplicate/conflict group, or
a target-approval decision. Every mutation is audited (`audit_logs`) and
appended to the entity's own `governance_review_events` history.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.database.repositories.governance import GovernanceRepository, public_row
from backend.database.repositories.manual_data import ManualDataRepository
from backend.database.repositories.semantic_chunks import SemanticChunkRepository
from backend.services.dataset_quality import DatasetQualityService
from backend.services.manual_data_service import ManualDataQualityService, ManualDataUsageService
from backend.services.semantic_chunk_service import SemanticChunkQualityService
from backend.services.structured_record_service import StructuredRecordCandidateService
from core_model.data_governance.gate_rules import evaluate_target_approval, is_approval_expired
from core_model.data_governance.quality_adapter import (
    normalize_chunk_quality_result,
    normalize_dataset_quality_result,
    normalize_manual_data_quality_result,
)
from core_model.data_governance.review import (
    CLOSED_REVIEW_STATUSES,
    GOVERNANCE_ENTITY_TYPES,
    GOVERNANCE_TARGET_USES,
    REVIEW_STATUSES,
    compute_review_priority,
)

# Rights-target uses ("dataset_export"/"rag_handoff" are handoff-only
# gate checks -- neither existing usage-policy module knows about them,
# so they are never sent to a rights evaluator; the approval decision
# for those two rests solely on quality/duplicate/conflict/review gates).
_RIGHTS_TARGET_USES = frozenset(
    {"rag", "training", "evaluation", "commercial", "public_export", "redistribution"}
)


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
            "governance",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


def _require_entity_type(entity_type: str) -> None:
    if entity_type not in GOVERNANCE_ENTITY_TYPES:
        raise ValidationError(f"unsupported governance entity_type: {entity_type}")


class GovernanceReviewService:
    """The unified review queue: `governance_review_items` +
    `governance_review_issues` + `governance_review_events`."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernanceRepository(settings.resolved_database_path)

    def open_or_reuse(
        self,
        *,
        entity_type: str,
        entity_public_id: str,
        reason: str,
        admin_id: str,
        priority: str = "normal",
        entity_revision_public_id: str | None = None,
        source_public_id: str | None = None,
        document_public_id: str | None = None,
        page_public_id: str | None = None,
    ) -> dict[str, Any]:
        """Idempotent: returns the existing open item for this entity if
        one exists (Step 13's "never open two open review items for the
        same entity" -- also enforced by the DB's partial unique index),
        otherwise creates a new one."""

        _require_entity_type(entity_type)
        with self.repository.transaction() as connection:
            existing = self.repository.find_open_review_item(
                connection, entity_type, entity_public_id
            )
            if existing is not None:
                return public_row(existing)
            review_code = self.repository.next_review_code(connection)
            public_id = self.repository.create_review_item(
                connection,
                {
                    "review_code": review_code,
                    "entity_type": entity_type,
                    "entity_public_id": entity_public_id,
                    "entity_revision_public_id": entity_revision_public_id,
                    "source_public_id": source_public_id,
                    "document_public_id": document_public_id,
                    "page_public_id": page_public_id,
                    "priority": priority,
                    "created_by_admin_public_id": admin_id,
                },
            )
            item_id = self.repository.review_item(connection, public_id)["id"]
            self.repository.create_event(
                connection,
                {
                    "review_item_id": item_id,
                    "event_type": "review_item_opened",
                    "performed_by_admin_public_id": admin_id,
                    "notes": reason,
                },
            )
            _audit(
                connection,
                "governance_review_item_opened",
                admin_id,
                entity_public_id,
                entity_type=entity_type,
                reason=reason,
            )
            return public_row(self.repository.review_item(connection, public_id))

    def get(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.review_item(connection, public_id)
            data = public_row(item)
            data["issues"] = [
                public_row(i) for i in self.repository.issues_for_item(connection, item["id"])
            ]
            data["events"] = [
                public_row(e) for e in self.repository.events_for_item(connection, item["id"])
            ]
            data["target_approvals"] = [
                public_row(a)
                for a in self.repository.target_approvals_for_entity(
                    connection, item["entity_type"], item["entity_public_id"]
                )
            ]
            return data

    def history(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.review_item(connection, public_id)
            return {
                "items": [
                    public_row(e) for e in self.repository.events_for_item(connection, item["id"])
                ]
            }

    def queue(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        entity_type: str | None = None,
        assigned_admin_public_id: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows, total = self.repository.list_review_items(
                connection,
                status=status,
                priority=priority,
                entity_type=entity_type,
                assigned_admin_public_id=assigned_admin_public_id,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
            counts = self.repository.review_queue_counts(connection)
        return {
            "items": [public_row(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
            "counts_by_status": counts,
        }

    def assign(
        self, public_id: str, assignee_admin_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.review_item(connection, public_id)
            self.repository.update_review_item(
                connection, item["id"], {"assigned_admin_public_id": assignee_admin_public_id}
            )
            self.repository.create_event(
                connection,
                {
                    "review_item_id": item["id"],
                    "event_type": "review_item_assigned",
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"assigned to {assignee_admin_public_id}",
                },
            )
            _audit(
                connection,
                "governance_review_item_assigned",
                admin_id,
                item["entity_public_id"],
                assignee=assignee_admin_public_id,
            )
            return public_row(self.repository.review_item(connection, public_id))

    def set_status(
        self, public_id: str, status: str, *, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        if status not in REVIEW_STATUSES:
            raise ValidationError(f"unsupported review status: {status}")
        with self.repository.transaction() as connection:
            item = self.repository.review_item(connection, public_id)
            if status in CLOSED_REVIEW_STATUSES:
                open_issues = self.repository.issues_for_item(
                    connection, item["id"], open_only=True
                )
                blocking_open = [i for i in open_issues if i["is_blocking"]]
                if status == "resolved" and blocking_open:
                    raise ValidationError(
                        "cannot resolve a review item with unresolved blocking issues"
                    )
            self.repository.update_review_item(connection, item["id"], {"status": status})
            if status in CLOSED_REVIEW_STATUSES:
                connection.execute(
                    "UPDATE governance_review_items SET resolved_at=CURRENT_TIMESTAMP WHERE id=?",
                    (item["id"],),
                )
            self.repository.create_event(
                connection,
                {
                    "review_item_id": item["id"],
                    "event_type": "review_item_status_changed",
                    "performed_by_admin_public_id": admin_id,
                    "notes": notes or f"status -> {status}",
                },
            )
            _audit(
                connection,
                "governance_review_item_status_changed",
                admin_id,
                item["entity_public_id"],
                status=status,
            )
            return public_row(self.repository.review_item(connection, public_id))

    def add_note(self, public_id: str, note: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.review_item(connection, public_id)
            self.repository.create_event(
                connection,
                {
                    "review_item_id": item["id"],
                    "event_type": "note_added",
                    "performed_by_admin_public_id": admin_id,
                    "notes": note,
                },
            )
            return public_row(self.repository.review_item(connection, public_id))


class GovernanceQualityService:
    """Normalizes each entity's own authoritative quality result (Step 7)
    and syncs the outcome onto its governance review item's issues --
    never recomputes a score a subsystem already owns."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernanceRepository(settings.resolved_database_path)
        self.dataset_quality = DatasetQualityService(
            DatasetQualityRepository(settings.resolved_database_path), settings
        )
        self.manual_data_quality = ManualDataQualityService(
            ManualDataRepository(settings.resolved_database_path), settings
        )
        self.chunk_quality = SemanticChunkQualityService(settings)
        self.review_service = GovernanceReviewService(settings)

    def assess(self, entity_type: str, entity_public_id: str, *, admin_id: str) -> dict[str, Any]:
        if entity_type == "dataset_record":
            assessment = self.dataset_quality.assess_record(entity_public_id, admin_id)
            normalized = normalize_dataset_quality_result(assessment)
        elif entity_type == "manual_data_record":
            result = self.manual_data_quality.assess(entity_public_id)
            normalized = normalize_manual_data_quality_result(result)
        elif entity_type == "semantic_chunk":
            result = self.chunk_quality.assess(entity_public_id)
            normalized = normalize_chunk_quality_result(result)
        else:
            raise ValidationError(
                f"no quality adapter is wired for entity_type {entity_type!r} yet"
            )
        return self._sync(entity_type, entity_public_id, normalized, admin_id=admin_id)

    def _sync(
        self,
        entity_type: str,
        entity_public_id: str,
        normalized: dict[str, Any],
        *,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            item = self.repository.find_open_review_item(connection, entity_type, entity_public_id)
            if normalized["is_blocked"] and item is None:
                review_code = self.repository.next_review_code(connection)
                item_public_id = self.repository.create_review_item(
                    connection,
                    {
                        "review_code": review_code,
                        "entity_type": entity_type,
                        "entity_public_id": entity_public_id,
                        "created_by_admin_public_id": admin_id,
                    },
                )
                item = self.repository.review_item(connection, item_public_id)
                self.repository.create_event(
                    connection,
                    {
                        "review_item_id": item["id"],
                        "event_type": "review_item_opened",
                        "performed_by_admin_public_id": admin_id,
                        "notes": "blocking_quality_issue",
                    },
                )
            if item is None:
                _audit(
                    connection,
                    "governance_quality_assessed",
                    admin_id,
                    entity_public_id,
                    entity_type=entity_type,
                    is_blocked=False,
                )
                return {"review_item": None, "normalized_quality": normalized}

            existing_open = {
                row["issue_code"]
                for row in self.repository.issues_for_item(connection, item["id"], open_only=True)
            }
            created_issues: list[str] = []
            for entry in normalized["issue_categories"]:
                if entry["issue_code"] in existing_open:
                    continue
                issue_public_id = self.repository.create_issue(
                    connection,
                    {
                        "review_item_id": item["id"],
                        "issue_code": entry["issue_code"],
                        "issue_category": entry["issue_category"],
                        "severity": "critical",
                        "is_blocking": True,
                        "message": f"quality gate blocked on {entry['issue_code']}",
                        "detector": f"quality_adapter:{normalized['metadata']['source_system']}",
                    },
                )
                created_issues.append(issue_public_id)

            all_open_issues = [
                dict(row)
                for row in self.repository.issues_for_item(connection, item["id"], open_only=True)
            ]
            priority = compute_review_priority(all_open_issues)
            self.repository.update_review_item(connection, item["id"], {"priority": priority})
            _audit(
                connection,
                "governance_quality_assessed",
                admin_id,
                entity_public_id,
                entity_type=entity_type,
                is_blocked=normalized["is_blocked"],
                new_issue_count=len(created_issues),
            )
            return {
                "review_item": public_row(
                    self.repository.review_item_by_id(connection, item["id"])
                ),
                "normalized_quality": normalized,
                "new_issue_public_ids": created_issues,
            }


class GovernanceDuplicateService:
    """Persists the *existing* pairwise duplicate detectors' output as an
    assignable, resolvable group (the one genuinely new capability --
    the detectors themselves are reused verbatim)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernanceRepository(settings.resolved_database_path)
        self.manual_data = ManualDataRepository(settings.resolved_database_path)
        self.manual_data_quality = ManualDataQualityService(self.manual_data, settings)
        self.chunk_quality = SemanticChunkQualityService(settings)
        self.chunk_repository = SemanticChunkRepository(settings.resolved_database_path)

    def sync_manual_data_duplicate(self, public_id: str, *, admin_id: str) -> dict[str, Any]:
        check = self.manual_data_quality.check_duplicates(public_id)
        if check["duplicate_status"] != "exact_duplicate" or not check["matching_record_ids"]:
            return {"duplicate_group": None, "check": check}
        canonical_public_id = check["matching_record_ids"][0]
        group = self._ensure_duplicate_group(
            duplicate_type="exact",
            match_reason=check["similarity_or_match_reason"] or "identical normalized content",
            canonical_entity_type="manual_data_record",
            canonical_entity_public_id=canonical_public_id,
            members=[
                ("manual_data_record", canonical_public_id),
                ("manual_data_record", public_id),
            ],
            admin_id=admin_id,
        )
        return {"duplicate_group": group, "check": check}

    def sync_chunk_duplicate(self, chunk_public_id: str, *, admin_id: str) -> dict[str, Any]:
        check = self.chunk_quality.duplicate_check(chunk_public_id)
        duplicate_public_id = check.get("exact_duplicate_chunk_public_id") or check.get(
            "locator_duplicate_chunk_public_id"
        )
        if not duplicate_public_id:
            return {"duplicate_group": None, "check": check}
        duplicate_type = (
            "exact" if check.get("exact_duplicate_chunk_public_id") else "source_locator"
        )
        group = self._ensure_duplicate_group(
            duplicate_type=duplicate_type,
            match_reason="identical content hash"
            if duplicate_type == "exact"
            else "identical source page locator",
            canonical_entity_type="semantic_chunk",
            canonical_entity_public_id=duplicate_public_id,
            members=[
                ("semantic_chunk", duplicate_public_id),
                ("semantic_chunk", chunk_public_id),
            ],
            admin_id=admin_id,
        )
        return {"duplicate_group": group, "check": check}

    def _ensure_duplicate_group(
        self,
        *,
        duplicate_type: str,
        match_reason: str,
        canonical_entity_type: str,
        canonical_entity_public_id: str,
        members: list[tuple[str, str]],
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            existing = None
            for entity_type, entity_public_id in members:
                existing = self.repository.find_open_duplicate_group_for_entity(
                    connection, entity_type, entity_public_id
                )
                if existing:
                    break
            if existing is not None:
                group_id = existing["id"]
                group_public_id = existing["public_id"]
            else:
                group_code = self.repository.next_group_code(connection, "duplicate")
                group_public_id = self.repository.create_duplicate_group(
                    connection,
                    {
                        "group_code": group_code,
                        "duplicate_type": duplicate_type,
                        "canonical_entity_type": canonical_entity_type,
                        "canonical_entity_public_id": canonical_entity_public_id,
                        "match_reason": match_reason,
                    },
                )
                group_id = self.repository.duplicate_group(connection, group_public_id)["id"]
            for entity_type, entity_public_id in members:
                role = "canonical" if entity_public_id == canonical_entity_public_id else "member"
                self.repository.add_duplicate_member(
                    connection, group_id, entity_type, entity_public_id, role=role
                )
            _audit(
                connection,
                "governance_duplicate_group_synced",
                admin_id,
                group_public_id,
                duplicate_type=duplicate_type,
                member_count=len(members),
            )
            return public_row(self.repository.duplicate_group(connection, group_public_id))

    def resolve(
        self,
        group_public_id: str,
        *,
        resolution_action: str,
        resolution_reason: str,
        admin_id: str,
        selected_entities: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        if not resolution_reason.strip():
            raise ValidationError("a resolution reason is required")
        with self.repository.transaction() as connection:
            group = self.repository.duplicate_group(connection, group_public_id)
            self.repository.create_resolution(
                connection,
                {
                    "duplicate_group_id": group["id"],
                    "resolution_action": resolution_action,
                    "resolution_reason": resolution_reason,
                    "selected_entities_json": dumps_json(selected_entities or []),
                    "performed_by_admin_public_id": admin_id,
                },
            )
            self.repository.resolve_duplicate_group(connection, group["id"])
            _audit(
                connection,
                "governance_duplicate_group_resolved",
                admin_id,
                group_public_id,
                resolution_action=resolution_action,
            )
            return public_row(self.repository.duplicate_group(connection, group_public_id))

    def list_groups(self, *, status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            groups = self.repository.list_duplicate_groups(connection, status=status)
            items = []
            for group in groups:
                members = self.repository.duplicate_group_members(connection, group["id"])
                data = public_row(group)
                data["members"] = [public_row(m) for m in members]
                items.append(data)
        return {"items": items}


class GovernanceConflictService:
    """Persists conflicts detected by `core_model.semantic_chunk.duplicates`'
    `detect_dictionary_conflict`/`detect_qa_conflict`/`detect_translation_conflict`
    -- routing a genuine "alternate sense" to a *conflict* group (never a
    duplicate group), matching the task's "alternate dictionary senses
    are never duplicates" rule."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernanceRepository(settings.resolved_database_path)
        self.structured_records = StructuredRecordCandidateService(settings)

    _DUPLICATE_CONFLICT_TYPES = frozenset(
        {"duplicate_sense", "duplicate_answer", "duplicate_translation"}
    )
    _CONFLICT_TYPE_MAP = {
        "alternate_sense": "dictionary_sense",
        "duplicate_sense": "dictionary_sense",
        "conflicting_answer": "answer",
        "duplicate_answer": "answer",
        "inconsistent_translation": "translation",
        "duplicate_translation": "translation",
    }

    def sync_structured_record_conflict(
        self, candidate_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        check = self.structured_records.conflict_check(candidate_public_id)
        conflict = check.get("conflict")
        if conflict is None:
            return {"conflict_group": None, "duplicate_group": None, "check": check}

        other_public_id = conflict["candidate_public_id"]
        members = [
            ("structured_record_candidate", other_public_id),
            ("structured_record_candidate", candidate_public_id),
        ]
        if conflict["type"] in self._DUPLICATE_CONFLICT_TYPES:
            duplicate_service = GovernanceDuplicateService(self.settings)
            group = duplicate_service._ensure_duplicate_group(
                duplicate_type="normalized",
                match_reason=f"structured record conflict type: {conflict['type']}",
                canonical_entity_type="structured_record_candidate",
                canonical_entity_public_id=other_public_id,
                members=members,
                admin_id=admin_id,
            )
            return {"conflict_group": None, "duplicate_group": group, "check": check}

        conflict_type = self._CONFLICT_TYPE_MAP[conflict["type"]]
        group = self._ensure_conflict_group(
            conflict_type=conflict_type,
            match_reason=f"structured record conflict type: {conflict['type']}",
            members=members,
            admin_id=admin_id,
        )
        return {"conflict_group": group, "duplicate_group": None, "check": check}

    def _ensure_conflict_group(
        self,
        *,
        conflict_type: str,
        match_reason: str,
        members: list[tuple[str, str]],
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            existing = None
            for entity_type, entity_public_id in members:
                existing = self.repository.find_open_conflict_group_for_entity(
                    connection, entity_type, entity_public_id
                )
                if existing:
                    break
            if existing is not None:
                group_id = existing["id"]
                group_public_id = existing["public_id"]
            else:
                group_code = self.repository.next_group_code(connection, "conflict")
                group_public_id = self.repository.create_conflict_group(
                    connection,
                    {
                        "group_code": group_code,
                        "conflict_type": conflict_type,
                        "match_reason": match_reason,
                    },
                )
                group_id = self.repository.conflict_group(connection, group_public_id)["id"]
            for entity_type, entity_public_id in members:
                self.repository.add_conflict_member(
                    connection, group_id, entity_type, entity_public_id
                )
            _audit(
                connection,
                "governance_conflict_group_synced",
                admin_id,
                group_public_id,
                conflict_type=conflict_type,
                member_count=len(members),
            )
            return public_row(self.repository.conflict_group(connection, group_public_id))

    def resolve(
        self,
        group_public_id: str,
        *,
        resolution_action: str,
        resolution_reason: str,
        admin_id: str,
        selected_entities: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        if not resolution_reason.strip():
            raise ValidationError("a resolution reason is required")
        with self.repository.transaction() as connection:
            group = self.repository.conflict_group(connection, group_public_id)
            self.repository.create_resolution(
                connection,
                {
                    "conflict_group_id": group["id"],
                    "resolution_action": resolution_action,
                    "resolution_reason": resolution_reason,
                    "selected_entities_json": dumps_json(selected_entities or []),
                    "performed_by_admin_public_id": admin_id,
                },
            )
            self.repository.resolve_conflict_group(connection, group["id"])
            _audit(
                connection,
                "governance_conflict_group_resolved",
                admin_id,
                group_public_id,
                resolution_action=resolution_action,
            )
            return public_row(self.repository.conflict_group(connection, group_public_id))

    def list_groups(self, *, status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            groups = self.repository.list_conflict_groups(connection, status=status)
            items = []
            for group in groups:
                members = self.repository.conflict_group_members(connection, group["id"])
                data = public_row(group)
                data["members"] = [public_row(m) for m in members]
                items.append(data)
        return {"items": items}


class GovernanceApprovalService:
    """Combines an entity's rights-usage decision (where one exists),
    normalized quality issues, and open duplicate/conflict groups into a
    per-target-use approval decision (Step 4/15), and persists it as a
    new, append-only `governance_target_approvals` row -- never a single
    global `approved` flag."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernanceRepository(settings.resolved_database_path)
        self.sources = DataSourceRepository(settings.resolved_database_path)
        self.manual_data = ManualDataRepository(settings.resolved_database_path)
        self.manual_data_usage = ManualDataUsageService(self.manual_data, self.sources, settings)
        self.structured_records = StructuredRecordCandidateService(settings)

    def _usage_decision(
        self, entity_type: str, entity_public_id: str, target_use: str
    ) -> dict[str, Any] | None:
        if target_use not in _RIGHTS_TARGET_USES:
            return None
        if entity_type == "manual_data_record":
            return self.manual_data_usage.evaluate(entity_public_id, target_use)
        if entity_type == "structured_record_candidate":
            return self.structured_records.usage_check(entity_public_id, target_use)
        # No rights-usage evaluator is wired yet for document_page,
        # semantic_chunk, document_candidate, or dataset_record at this
        # call site -- the approval decision for those rests on the
        # quality/duplicate/conflict/review gates only, never a fabricated
        # rights check.
        return None

    def evaluate(
        self,
        entity_type: str,
        entity_public_id: str,
        target_use: str,
        *,
        admin_id: str,
        persist: bool = True,
    ) -> dict[str, Any]:
        _require_entity_type(entity_type)
        if target_use not in GOVERNANCE_TARGET_USES:
            raise ValidationError(f"unsupported governance target_use: {target_use}")

        usage_decision = self._usage_decision(entity_type, entity_public_id, target_use)
        with self.repository.transaction() as connection:
            review_item = self.repository.find_open_review_item(
                connection, entity_type, entity_public_id
            )
            open_issues = (
                [
                    dict(row)
                    for row in self.repository.issues_for_item(
                        connection, review_item["id"], open_only=True
                    )
                ]
                if review_item
                else []
            )
            open_duplicate = (
                self.repository.find_open_duplicate_group_for_entity(
                    connection, entity_type, entity_public_id
                )
                is not None
            )
            open_conflict = (
                self.repository.find_open_conflict_group_for_entity(
                    connection, entity_type, entity_public_id
                )
                is not None
            )

        decision = evaluate_target_approval(
            target_use=target_use,
            usage_decision=usage_decision,
            normalized_issues=open_issues,
            open_duplicate_group=open_duplicate,
            open_conflict_group=open_conflict,
            review_item_open=review_item is not None,
        )

        if not persist:
            return {
                **decision,
                "entity_type": entity_type,
                "entity_public_id": entity_public_id,
                "target_use": target_use,
            }

        with self.repository.transaction() as connection:
            if review_item is not None:
                item_id = review_item["id"]
            else:
                review_code = self.repository.next_review_code(connection)
                initial_status = "open" if decision["decision"] != "allowed" else "resolved"
                item_public_id = self.repository.create_review_item(
                    connection,
                    {
                        "review_code": review_code,
                        "entity_type": entity_type,
                        "entity_public_id": entity_public_id,
                        "created_by_admin_public_id": admin_id,
                    },
                )
                item_id = self.repository.review_item(connection, item_public_id)["id"]
                if initial_status == "resolved":
                    self.repository.update_review_item(
                        connection, item_id, {"status": "resolved"}
                    )
                    connection.execute(
                        "UPDATE governance_review_items SET resolved_at=CURRENT_TIMESTAMP "
                        "WHERE id=?",
                        (item_id,),
                    )
                self.repository.create_event(
                    connection,
                    {
                        "review_item_id": item_id,
                        "event_type": "review_item_opened",
                        "performed_by_admin_public_id": admin_id,
                        "notes": "target_approval_requested",
                    },
                )

            approval_public_id = self.repository.create_target_approval(
                connection,
                {
                    "review_item_id": item_id,
                    "entity_type": entity_type,
                    "entity_public_id": entity_public_id,
                    "target_use": target_use,
                    "decision": decision["decision"],
                    "decision_code": decision["decision_code"],
                    "blocking_issue_ids_json": dumps_json(decision["blocking_issue_ids"]),
                    "warnings_json": dumps_json(decision["warnings"]),
                    "required_actions_json": dumps_json(decision["required_actions"]),
                    "decided_by_admin_public_id": admin_id,
                },
            )
            self.repository.create_event(
                connection,
                {
                    "review_item_id": item_id,
                    "event_type": "target_approval_decided",
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"{target_use}: {decision['decision']} ({decision['decision_code']})",
                },
            )
            _audit(
                connection,
                "governance_target_approval_decided",
                admin_id,
                entity_public_id,
                entity_type=entity_type,
                target_use=target_use,
                decision=decision["decision"],
                decision_code=decision["decision_code"],
            )
            approval = public_row(
                connection.execute(
                    "SELECT * FROM governance_target_approvals WHERE public_id=?",
                    (approval_public_id,),
                ).fetchone()
            )
        return approval

    def override(
        self,
        entity_type: str,
        entity_public_id: str,
        target_use: str,
        decision: str,
        *,
        reason: str,
        admin_id: str,
    ) -> dict[str, Any]:
        """An explicit human override -- always requires a non-empty
        reason, always recorded as `is_override=True`, and always
        audited, per the task's "overrides require explicit reason +
        reviewer + audit" rule. Never silently supersedes a blocking
        rights decision -- overriding a `blocked` rights code still
        requires the admin to state why."""

        _require_entity_type(entity_type)
        if target_use not in GOVERNANCE_TARGET_USES:
            raise ValidationError(f"unsupported governance target_use: {target_use}")
        if decision not in ("allowed", "blocked", "needs_review"):
            raise ValidationError(f"unsupported override decision: {decision}")
        if not reason.strip():
            raise ValidationError("an override reason is required")

        with self.repository.transaction() as connection:
            review_item = self.repository.find_open_review_item(
                connection, entity_type, entity_public_id
            )
            if review_item is None:
                review_code = self.repository.next_review_code(connection)
                item_public_id = self.repository.create_review_item(
                    connection,
                    {
                        "review_code": review_code,
                        "entity_type": entity_type,
                        "entity_public_id": entity_public_id,
                        "created_by_admin_public_id": admin_id,
                    },
                )
                item_id = self.repository.review_item(connection, item_public_id)["id"]
            else:
                item_id = review_item["id"]

            approval_public_id = self.repository.create_target_approval(
                connection,
                {
                    "review_item_id": item_id,
                    "entity_type": entity_type,
                    "entity_public_id": entity_public_id,
                    "target_use": target_use,
                    "decision": decision,
                    "decision_code": "ADMIN_OVERRIDE",
                    "is_override": True,
                    "override_reason": reason,
                    "decided_by_admin_public_id": admin_id,
                },
            )
            self.repository.create_event(
                connection,
                {
                    "review_item_id": item_id,
                    "event_type": "target_approval_overridden",
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"{target_use}: overridden to {decision} -- {reason}",
                },
            )
            _audit(
                connection,
                "governance_target_approval_overridden",
                admin_id,
                entity_public_id,
                entity_type=entity_type,
                target_use=target_use,
                decision=decision,
                reason=reason,
            )
            return public_row(
                connection.execute(
                    "SELECT * FROM governance_target_approvals WHERE public_id=?",
                    (approval_public_id,),
                ).fetchone()
            )

    def status(self, entity_type: str, entity_public_id: str) -> dict[str, Any]:
        """Read-only per-target-use matrix for an entity, expiry-aware --
        used both by the frontend approval matrix and by export/handoff
        preflight (Step 20)."""

        _require_entity_type(entity_type)
        with self.repository.transaction() as connection:
            rows = self.repository.target_approvals_for_entity(
                connection, entity_type, entity_public_id
            )
        latest_by_target: dict[str, dict[str, Any]] = {}
        for row in rows:
            data = public_row(row)
            target = data["target_use"]
            if target not in latest_by_target:
                latest_by_target[target] = data
        matrix: dict[str, dict[str, Any]] = {}
        for target_use in GOVERNANCE_TARGET_USES:
            entry = latest_by_target.get(target_use)
            if entry is None:
                matrix[target_use] = {"decision": "not_requested", "decision_code": "NOT_REQUESTED"}
                continue
            if is_approval_expired(entry.get("expires_at")):
                matrix[target_use] = {**entry, "decision": "needs_review", "expired": True}
            else:
                matrix[target_use] = {**entry, "expired": False}
        return {"entity_type": entity_type, "entity_public_id": entity_public_id, "targets": matrix}


class GovernanceExportReadinessService:
    """Read-only preflight check for the export/RAG-handoff call sites
    (Step 20) -- a `GET`-only view of whether `target_use` is currently
    `allowed` for an entity, with no side effects. Export methods call
    `require_allowed()` as an additive guard *before* their existing
    logic runs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.approvals = GovernanceApprovalService(settings)

    def check(self, entity_type: str, entity_public_id: str, target_use: str) -> dict[str, Any]:
        return self.approvals.evaluate(
            entity_type, entity_public_id, target_use, admin_id="system", persist=False
        )

    def require_allowed(self, entity_type: str, entity_public_id: str, target_use: str) -> None:
        result = self.check(entity_type, entity_public_id, target_use)
        if result["decision"] != "allowed":
            reasons = "; ".join(result["blocking_issue_ids"]) or result["decision"]
            raise ValidationError(
                f"governance blocks {target_use} for this {entity_type} "
                f"({result['decision_code']}): {reasons}"
            )


__all__ = [
    "GovernanceReviewService",
    "GovernanceQualityService",
    "GovernanceDuplicateService",
    "GovernanceConflictService",
    "GovernanceApprovalService",
    "GovernanceExportReadinessService",
]
