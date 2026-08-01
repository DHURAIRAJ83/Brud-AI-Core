"""Phase 13 Step 6/7 record promotion and isolated sandbox corpus
preparation.

Promotes only *accepted* Phase 12 records bound into an *approved*
sandbox approval into a brand-new, dedicated `rag_knowledge_spaces`
row -- the sandbox namespace itself (Step 7's preferred isolation
model). Reuses `RagIngestionService.create_space`/`create_source`/
`create_source_version` verbatim; never writes directly to
`rag_knowledge_sources`/`rag_source_versions`. Never downloads
anything and never touches production RAG data -- every space this
service creates is exclusively referenced by exactly one
`rag_sandbox_corpora` row with `production_visible` hard-CHECKed to 0.
See docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.rag import RagRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.rag import KnowledgeSourceCreate, KnowledgeSourcePatch, KnowledgeSpaceCreate
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from core_model.rag.chunking import estimate_token_count
from core_model.rag_sandbox import (
    DERIVED_CONTENT_REVIEW_DECISIONS,
    PROMOTION_ELIGIBLE_REVIEW_DECISIONS,
    SANDBOX_SCOPE_PREFIX,
)

logger = logging.getLogger(__name__)


def _is_expired(expires_at: str | None) -> bool:
    """Never trusts a malformed/missing expiry as "still valid" by
    accident. Mirrors Phase 12's `dataset_sample_download_service.
    _is_expired()` exactly -- Phase 12's own post-mortem found that an
    approval's `expires_at` was validated at approval time but never
    re-checked at the first real action taken under it; Phase 13 checks
    it here, at corpus preparation (Phase 13's equivalent first
    consequential action), before any record is promoted."""

    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return datetime.now(UTC) > parsed


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"rag_sandbox_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="rag_sandbox_experiment",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("rag_sandbox_audit_write_failed", extra={"action": action})


class RagSandboxCorpusService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._rag_repository = RagRepository(settings.resolved_database_path)
        self._ingestion = RagIngestionService(self._rag_repository, settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _latest_eligible_review(
        self, sample_import_public_id: str, record_internal_id: int
    ) -> dict[str, Any] | None:
        reviews = self._samples.list_reviews(sample_import_public_id)
        matches = [
            review
            for review in reviews
            if review["target_type"] == "record" and review["target_id"] == record_internal_id
        ]
        if not matches:
            return None
        return matches[-1]

    def _record_internal_id(self, connection: sqlite3.Connection, record_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
            (record_public_id,),
        ).fetchone()
        if not row:
            raise RagSandboxError(f"sample record not found: {record_public_id}")
        return row["id"]

    def _review_internal_id(self, connection: sqlite3.Connection, review_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_dataset_sample_reviews WHERE public_id=?",
            (review_public_id,),
        ).fetchone()
        if not row:
            raise RagSandboxError(f"sample review not found: {review_public_id}")
        return row["id"]

    def _has_unresolved_pii(self, sample_import_public_id: str, record_public_id: str) -> bool:
        issues = self._samples.list_record_issues(
            sample_import_public_id, issue_category="pii", status="blocked"
        )
        return any(issue["record_public_id"] == record_public_id for issue in issues)

    def _is_contamination_flagged(
        self, sample_import_public_id: str, record_public_id: str
    ) -> bool:
        issues = self._samples.list_record_issues(
            sample_import_public_id, issue_category="contamination"
        )
        return any(issue["record_public_id"] == record_public_id for issue in issues)

    def prepare_corpus(self, experiment_public_id: str, *, admin_id: str) -> dict[str, Any]:
        """Governed record promotion (Step 6) followed by isolated corpus
        creation (Step 7). Refuses if the experiment has no approved,
        non-stale, non-expired approval bound to it. Every record that
        cannot be promoted (excluded/rejected/PII-blocked/decision not
        in the promotion-eligible set) is skipped and logged, never
        silently substituted."""

        from backend.services.rag_sandbox_eligibility_service import RagSandboxApprovalService

        experiment = self._sandbox.get_experiment(experiment_public_id)
        approval = self._sandbox.get_latest_approval(experiment_public_id)
        if approval is None or approval["status"] != "approved":
            raise RagSandboxError("no approved rag sandbox approval exists for this experiment")
        if _is_expired(approval["expires_at"]):
            raise RagSandboxError("this rag sandbox approval has expired")
        approval_service = RagSandboxApprovalService(self.settings)
        if approval_service.is_stale(approval["public_id"]):
            raise RagSandboxError(
                "the approval is stale -- the Phase 12 sample report or accepted-record set "
                "has changed since approval"
            )

        existing_corpus = self._sandbox.get_corpus_for_experiment(experiment_public_id)
        if existing_corpus is not None:
            raise RagSandboxError("a corpus already exists for this experiment")

        self._sandbox.update_experiment(
            experiment_public_id, {"status": "preparing_corpus", "current_stage": "corpus_creation"}
        )

        sandbox_scope_key = f"{SANDBOX_SCOPE_PREFIX}{experiment_public_id}"
        space = self._ingestion.create_space(
            KnowledgeSpaceCreate(
                name=f"RAG Sandbox {experiment['experiment_code']}",
                slug=sandbox_scope_key,
                description="Isolated Phase 13 RAG sandbox corpus -- never production-visible.",
            ),
            admin_id,
        )
        with self._rag_repository.transaction() as connection:
            knowledge_space_id = self._rag_repository.space(connection, space["public_id"])["id"]

        corpus = self._sandbox.create_corpus(
            experiment_public_id,
            {
                "knowledge_space_id": knowledge_space_id,
                "sandbox_scope_key": sandbox_scope_key,
                "created_by_admin_public_id": admin_id,
            },
        )

        sample_import_public_id = experiment["sample_import_public_id"]
        blocked = 0
        total_characters = 0
        maximum_records = approval["maximum_records"]
        maximum_total_characters = approval["maximum_total_characters"]
        maximum_total_tokens = approval["maximum_total_tokens"]
        total_tokens = 0
        # Pass 1: decide which records are promotion-eligible and resolve
        # their content, without creating any RAG source yet -- Phase 16's
        # retrieval model keeps exactly one active vector/keyword index per
        # knowledge space, so all promoted records are combined into one
        # heading-delimited source (one heading per record, reusing
        # `chunk_text`'s existing `heading_aware` strategy verbatim to
        # recover per-record chunk boundaries) rather than one RAG source
        # per record.
        eligible: list[dict[str, Any]] = []

        for record_public_id in approval["accepted_record_ids"]:
            if len(eligible) >= maximum_records:
                self._sandbox.record_event(
                    experiment_public_id,
                    {
                        "event_type": "record_promotion_blocked",
                        "summary": f"maximum_records ({maximum_records}) reached",
                        "metadata": {"sample_record_public_id": record_public_id},
                        "performed_by_admin_public_id": admin_id,
                    },
                )
                blocked += 1
                continue

            sample_record = self._samples.get_record(record_public_id)
            if sample_record["status"] != "accepted":
                self._sandbox.record_event(
                    experiment_public_id,
                    {
                        "event_type": "record_promotion_blocked",
                        "summary": f"record status is '{sample_record['status']}', not accepted",
                        "metadata": {"sample_record_public_id": record_public_id},
                        "performed_by_admin_public_id": admin_id,
                    },
                )
                blocked += 1
                continue

            if self._has_unresolved_pii(sample_import_public_id, record_public_id):
                self._sandbox.record_event(
                    experiment_public_id,
                    {
                        "event_type": "record_promotion_blocked",
                        "summary": "record has an unresolved blocked PII finding",
                        "metadata": {"sample_record_public_id": record_public_id},
                        "performed_by_admin_public_id": admin_id,
                    },
                )
                blocked += 1
                continue

            with sqlite3.connect(self.settings.resolved_database_path) as raw_connection:
                raw_connection.row_factory = sqlite3.Row
                record_internal_id = self._record_internal_id(raw_connection, record_public_id)
            review = self._latest_eligible_review(sample_import_public_id, record_internal_id)
            if review is None or review["decision"] not in PROMOTION_ELIGIBLE_REVIEW_DECISIONS:
                self._sandbox.record_event(
                    experiment_public_id,
                    {
                        "event_type": "record_promotion_blocked",
                        "summary": "no promotion-eligible human-review decision found",
                        "metadata": {"sample_record_public_id": record_public_id},
                        "performed_by_admin_public_id": admin_id,
                    },
                )
                blocked += 1
                continue

            if review["decision"] in DERIVED_CONTENT_REVIEW_DECISIONS:
                content = review["derived_content_text"] or ""
                content_checksum = review["derived_content_checksum"] or ""
            else:
                content = sample_record["normalized_content"] or sample_record["raw_content"] or ""
                content_checksum = sample_record["record_checksum"]

            if not content.strip():
                blocked += 1
                continue

            projected_characters = total_characters + len(content)
            projected_tokens = total_tokens + estimate_token_count(content)
            if (
                projected_characters > maximum_total_characters
                or projected_tokens > maximum_total_tokens
            ):
                self._sandbox.record_event(
                    experiment_public_id,
                    {
                        "event_type": "record_promotion_blocked",
                        "summary": (
                            "maximum_total_characters/maximum_total_tokens would be exceeded"
                        ),
                        "metadata": {"sample_record_public_id": record_public_id},
                        "performed_by_admin_public_id": admin_id,
                    },
                )
                blocked += 1
                continue

            with sqlite3.connect(self.settings.resolved_database_path) as raw_connection:
                raw_connection.row_factory = sqlite3.Row
                selected_revision_id = self._review_internal_id(
                    raw_connection, review["public_id"]
                )

            eligible.append(
                {
                    "record_public_id": record_public_id,
                    "sample_record": sample_record,
                    "selected_revision_id": selected_revision_id,
                    "content": content,
                    "content_checksum": content_checksum,
                    "contamination_flagged": self._is_contamination_flagged(
                        sample_import_public_id, record_public_id
                    ),
                }
            )
            total_characters = projected_characters
            total_tokens = projected_tokens

        if not eligible:
            self._sandbox.update_corpus(corpus["public_id"], {"status": "failed"})
            self._sandbox.update_experiment(experiment_public_id, {"status": "failed"})
            raise RagSandboxError(
                "no accepted, promotion-eligible records were available to build a sandbox "
                "corpus from"
            )

        # Pass 2: one combined RAG source/source-version for the whole
        # corpus, with each record's content under its own `# <public_id>`
        # heading -- `chunk_text`'s existing heading_aware strategy (never
        # modified) then naturally recovers per-record chunk boundaries.
        combined_content = "\n\n".join(
            f"# {entry['record_public_id']}\n\n{entry['content']}" for entry in eligible
        )
        source = self._ingestion.create_source(
            space["public_id"],
            KnowledgeSourceCreate(
                source_type="manual_admin_content",
                title=f"RAG Sandbox corpus {experiment['experiment_code']}",
                language="mixed",
                content=combined_content,
                metadata={"rag_sandbox_experiment_public_id": experiment_public_id},
            ),
            admin_id,
        )
        # A promoted sandbox record's content already passed Phase 12's
        # full safety/PII/quality gate and the experiment's own Admin
        # approval -- approving the underlying RAG source here is
        # wiring the already-made governance decision through to
        # `assess_chunk_quality`'s `source_approved` gate, not a new,
        # separate content-approval step.
        self._ingestion.patch_source(
            source["public_id"], KnowledgeSourcePatch(approval_status="approved"), admin_id
        )
        source_version = self._ingestion.create_source_version(source["public_id"], admin_id)
        with self._rag_repository.transaction() as connection:
            rag_source_id = self._rag_repository.source(connection, source["public_id"])["id"]
            rag_source_version_id = self._rag_repository.source_version(
                connection, source_version["public_id"]
            )["id"]

        # Pass 3: one append-only rag_sandbox_records row per eligible
        # record, all sharing the one combined rag_source/source_version.
        for entry in eligible:
            self._sandbox.add_record(
                experiment_public_id,
                {
                    "corpus_public_id": corpus["public_id"],
                    "sample_record_public_id": entry["record_public_id"],
                    "selected_revision_id": entry["selected_revision_id"],
                    "content": entry["content"],
                    "content_checksum": entry["content_checksum"],
                    "language": entry["sample_record"].get("language"),
                    "task": entry["sample_record"].get("task"),
                    "source_location": entry["sample_record"].get("source_row_or_page") or "",
                    "contamination_flagged": entry["contamination_flagged"],
                    "rag_source_id": rag_source_id,
                    "rag_source_version_id": rag_source_version_id,
                },
            )
            self._sandbox.record_event(
                experiment_public_id,
                {
                    "event_type": "record_promoted",
                    "summary": (
                        f"record {entry['record_public_id']} promoted into the sandbox corpus"
                    ),
                    "metadata": {"sample_record_public_id": entry["record_public_id"]},
                    "performed_by_admin_public_id": admin_id,
                },
            )

        promoted = len(eligible)
        corpus = self._sandbox.update_corpus(
            corpus["public_id"],
            {
                "status": "ready",
                "record_count": promoted,
                "total_characters": total_characters,
            },
        )
        self._sandbox.update_experiment(
            experiment_public_id,
            {"status": "preparing_corpus", "current_stage": "index_build"},
        )
        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "corpus_prepared",
                "summary": f"{promoted} record(s) promoted, {blocked} blocked",
                "metadata": {"promoted": promoted, "blocked": blocked},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="prepare_corpus",
            actor_reference=admin_id,
            resource_public_id=experiment_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"promoted": promoted, "blocked": blocked},
        )
        return corpus


__all__ = ["RagSandboxCorpusService"]
