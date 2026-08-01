from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import (
    DataSourceCreate,
    DataSourcePatch,
    LinkCreate,
    SourceRightsUpsert,
    VerificationActionRequest,
)
from backend.services.data_source_service import (
    SourceRegistryService,
    SourceRightsService,
    SourceUsagePolicyService,
    SourceVerificationService,
)


@pytest.fixture
def services(tmp_path: Path):
    database_path = tmp_path / "data_sources.db"
    initialize_database(database_path)
    settings = Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    repository = DataSourceRepository(database_path)
    return {
        "registry": SourceRegistryService(repository, settings),
        "rights": SourceRightsService(repository, settings),
        "usage": SourceUsagePolicyService(repository, settings),
        "verification": SourceVerificationService(repository),
        "repository": repository,
    }


def _audit_events(repository: DataSourceRepository, database_path: Path) -> list[str]:
    from backend.database.connection import database_connection

    with database_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT action FROM audit_logs WHERE resource_type='data_source' ORDER BY id"
        ).fetchall()
    return [row["action"] for row in rows]


class TestSourceRegistryService:
    def test_create_get_list_update(self, services):
        registry = services["registry"]
        created = registry.create(
            DataSourceCreate(
                source_code="SRC-HUMAN-TEST-0001",
                title="Spoken Tamil examples",
                source_type="human_created",
            ),
            admin_id="admin-1",
        )
        assert created["status"] == "draft"
        assert created["source_code"] == "SRC-HUMAN-TEST-0001"

        fetched = registry.get(created["public_id"])
        assert fetched["title"] == "Spoken Tamil examples"

        listing = registry.list()
        assert listing["total"] == 1
        assert listing["items"][0]["public_id"] == created["public_id"]

        updated = registry.update(
            created["public_id"], DataSourcePatch(title="Updated title"), admin_id="admin-1"
        )
        assert updated["title"] == "Updated title"

    def test_duplicate_source_code_rejected(self, services):
        registry = services["registry"]
        registry.create(
            DataSourceCreate(source_code="SRC-DUP", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        with pytest.raises(ValidationError):
            registry.create(
                DataSourceCreate(source_code="SRC-DUP", title="B", source_type="human_created"),
                admin_id="admin-1",
            )

    def test_archive_blocks_edits_and_new_links_until_restored(self, services):
        registry = services["registry"]
        created = registry.create(
            DataSourceCreate(source_code="SRC-ARCH", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        archived = registry.archive(created["public_id"], admin_id="admin-1")
        assert archived["status"] == "archived"

        with pytest.raises(ValidationError):
            registry.update(created["public_id"], DataSourcePatch(title="X"), admin_id="admin-1")

        with pytest.raises(ValidationError):
            registry.create_link(
                created["public_id"],
                LinkCreate(entity_type="dataset_record", entity_public_id="rec-1"),
                admin_id="admin-1",
            )

        restored = registry.restore(created["public_id"], admin_id="admin-1")
        assert restored["status"] == "draft"
        registry.update(created["public_id"], DataSourcePatch(title="X"), admin_id="admin-1")

    def test_links_create_list_delete(self, services):
        registry = services["registry"]
        created = registry.create(
            DataSourceCreate(source_code="SRC-LINK", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        link = registry.create_link(
            created["public_id"],
            LinkCreate(entity_type="dataset_record", entity_public_id="rec-1"),
            admin_id="admin-1",
        )
        assert registry.list_links(created["public_id"])["items"][0]["entity_public_id"] == "rec-1"
        registry.delete_link(created["public_id"], link["public_id"], admin_id="admin-1")
        assert registry.list_links(created["public_id"])["items"] == []

    def test_every_mutation_appends_an_audit_event(self, services, tmp_path):
        registry = services["registry"]
        created = registry.create(
            DataSourceCreate(source_code="SRC-AUDIT", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        registry.update(created["public_id"], DataSourcePatch(title="B"), admin_id="admin-1")
        registry.archive(created["public_id"], admin_id="admin-1")
        registry.restore(created["public_id"], admin_id="admin-1")

        events = _audit_events(services["repository"], tmp_path / "data_sources.db")
        assert "data_source_created" in events
        assert "data_source_updated" in events
        assert "data_source_archived" in events
        assert "data_source_restored" in events


class TestSourceRightsLifecycle:
    def test_rights_default_to_no_permissions_and_fail_closed(self, services):
        registry, rights, usage = services["registry"], services["rights"], services["usage"]
        created = registry.create(
            DataSourceCreate(
                source_code="SRC-EXT-0001", title="Government PDF", source_type="government_source"
            ),
            admin_id="admin-1",
        )
        decision = usage.evaluate(created["public_id"], "training")
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_RIGHTS_UNKNOWN"

        rights.upsert(
            created["public_id"],
            SourceRightsUpsert(rights_status="pending_review"),
            admin_id="admin-1",
        )
        decision = usage.evaluate(created["public_id"], "training")
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_PERMISSION_PENDING"

    def test_invalid_rights_combination_is_rejected_at_write_time(self, services):
        registry, rights = services["registry"], services["rights"]
        created = registry.create(
            DataSourceCreate(source_code="SRC-INVALID", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        with pytest.raises(ValidationError):
            rights.upsert(
                created["public_id"],
                SourceRightsUpsert(public_export_allowed=True, redistribution_allowed=False),
                admin_id="admin-1",
            )

    def test_full_verification_flow_enables_training(self, services):
        registry, rights, usage, verification = (
            services["registry"],
            services["rights"],
            services["usage"],
            services["verification"],
        )
        created = registry.create(
            DataSourceCreate(
                source_code="SRC-FLOW-0001", title="Open dataset", source_type="open_dataset"
            ),
            admin_id="admin-1",
        )
        rights.upsert(
            created["public_id"],
            SourceRightsUpsert(
                rights_status="open_license",
                license_name="CC BY 4.0",
                training_use_allowed=True,
                rag_use_allowed=True,
                evaluation_use_allowed=True,
            ),
            admin_id="admin-1",
        )
        rights.submit_review(created["public_id"], admin_id="admin-1")
        source_after_submit = registry.get(created["public_id"])
        assert source_after_submit["status"] == "needs_review"

        rights.verify(
            created["public_id"],
            VerificationActionRequest(action="document_verify", evidence_reference="licence.pdf"),
            admin_id="admin-2",
        )
        source_after_verify = registry.get(created["public_id"])
        assert source_after_verify["status"] == "verified"

        decision = usage.evaluate(created["public_id"], "training")
        assert decision["allowed"] is True
        assert decision["decision_code"] == "ALLOWED"

        events = verification.list_events(created["public_id"])["items"]
        assert len(events) == 1
        assert events[0]["action"] == "document_verify"

    def test_reject_blocks_every_use_and_is_recorded(self, services):
        registry, rights, usage = services["registry"], services["rights"], services["usage"]
        created = registry.create(
            DataSourceCreate(source_code="SRC-REJECT", title="A", source_type="web_source"),
            admin_id="admin-1",
        )
        rights.upsert(
            created["public_id"],
            SourceRightsUpsert(rights_status="pending_review"),
            admin_id="admin-1",
        )
        rights.reject(
            created["public_id"],
            VerificationActionRequest(action="reject", notes="Not usable."),
            admin_id="admin-2",
        )
        assert registry.get(created["public_id"])["status"] == "rejected"
        decision = usage.evaluate(created["public_id"], "rag")
        assert decision["allowed"] is False
        assert decision["decision_code"] == "BLOCKED_SOURCE_REJECTED"

    def test_ai_generated_source_requires_verification_before_training(self, services):
        registry, rights, usage = services["registry"], services["rights"], services["usage"]
        created = registry.create(
            DataSourceCreate(
                source_code="SRC-AI-0001", title="AI draft", source_type="ai_generated"
            ),
            admin_id="admin-1",
        )
        rights.upsert(
            created["public_id"],
            SourceRightsUpsert(
                rights_status="licensed", training_use_allowed=True, rag_use_allowed=True
            ),
            admin_id="admin-1",
        )
        blocked = usage.evaluate(created["public_id"], "training")
        assert blocked["allowed"] is False
        assert blocked["decision_code"] == "BLOCKED_VERIFICATION_REQUIRED"

        rights.submit_review(created["public_id"], admin_id="admin-1")
        rights.verify(
            created["public_id"],
            VerificationActionRequest(action="owner_confirm"),
            admin_id="admin-2",
        )
        allowed = usage.evaluate(created["public_id"], "training")
        assert allowed["allowed"] is True

    def test_usage_evaluate_persists_decision_history(self, services):
        registry, usage = services["registry"], services["usage"]
        created = registry.create(
            DataSourceCreate(source_code="SRC-HIST", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        usage.evaluate(created["public_id"], "rag", admin_id="admin-1")
        usage.evaluate(created["public_id"], "training", admin_id="admin-1")
        history = registry.history(created["public_id"])
        assert len(history["usage_decisions"]) == 2

    def test_effective_permissions_covers_all_target_uses(self, services):
        registry, usage = services["registry"], services["usage"]
        created = registry.create(
            DataSourceCreate(source_code="SRC-EFFECTIVE", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        permissions = usage.effective_permissions(created["public_id"])
        assert set(permissions) == {
            "rag",
            "training",
            "evaluation",
            "commercial",
            "public_export",
            "redistribution",
        }


class TestRightsSummaryForEntities:
    """This is the preflight helper existing systems (dataset build, RAG
    ingestion, pretraining readiness, export) call -- it must never treat
    an entity with no source link at all as either allowed or blocked."""

    def test_unlinked_entities_are_reported_separately_not_blocked_or_allowed(self, services):
        usage = services["usage"]
        summary = usage.rights_summary_for_entities(
            "dataset_record", ["rec-a", "rec-b"], "training"
        )
        assert summary["total"] == 2
        assert summary["unlinked_count"] == 2
        assert summary["allowed_count"] == 0
        assert summary["blocked_count"] == 0
        assert set(summary["unlinked"]) == {"rec-a", "rec-b"}

    def test_linked_entity_with_allowed_rights_is_reported_allowed(self, services):
        registry, rights = services["registry"], services["rights"]
        created = registry.create(
            DataSourceCreate(source_code="SRC-SUMMARY-OK", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        rights.upsert(
            created["public_id"],
            SourceRightsUpsert(rights_status="licensed", training_use_allowed=True),
            admin_id="admin-1",
        )
        registry.create_link(
            created["public_id"],
            LinkCreate(entity_type="dataset_record", entity_public_id="rec-ok"),
            admin_id="admin-1",
        )
        summary = services["usage"].rights_summary_for_entities(
            "dataset_record", ["rec-ok", "rec-unlinked"], "training"
        )
        assert summary["allowed"] == ["rec-ok"]
        assert summary["unlinked"] == ["rec-unlinked"]
        assert summary["blocked"] == []

    def test_linked_entity_with_blocked_rights_reports_reasons(self, services):
        registry = services["registry"]
        created = registry.create(
            DataSourceCreate(
                source_code="SRC-SUMMARY-BLOCKED", title="A", source_type="government_source"
            ),
            admin_id="admin-1",
        )
        registry.create_link(
            created["public_id"],
            LinkCreate(entity_type="dataset_record", entity_public_id="rec-blocked"),
            admin_id="admin-1",
        )
        summary = services["usage"].rights_summary_for_entities(
            "dataset_record", ["rec-blocked"], "training"
        )
        assert summary["blocked"] == ["rec-blocked"]
        assert summary["blocking_reasons"]["rec-blocked"] == ["rights_unknown"]

    def test_entity_linked_to_two_sources_needs_both_to_allow(self, services):
        registry, rights = services["registry"], services["rights"]
        good = registry.create(
            DataSourceCreate(source_code="SRC-MULTI-GOOD", title="A", source_type="human_created"),
            admin_id="admin-1",
        )
        rights.upsert(
            good["public_id"],
            SourceRightsUpsert(rights_status="licensed", training_use_allowed=True),
            admin_id="admin-1",
        )
        bad = registry.create(
            DataSourceCreate(source_code="SRC-MULTI-BAD", title="B", source_type="web_source"),
            admin_id="admin-1",
        )
        for source in (good, bad):
            registry.create_link(
                source["public_id"],
                LinkCreate(
                    entity_type="dataset_record",
                    entity_public_id="rec-multi",
                    relationship_type="supporting_source" if source is bad else "primary_source",
                ),
                admin_id="admin-1",
            )
        summary = services["usage"].rights_summary_for_entities(
            "dataset_record", ["rec-multi"], "training"
        )
        assert summary["blocked"] == ["rec-multi"]
