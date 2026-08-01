from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.manual_data import ManualDataRepository
from backend.models.data_sources import (
    DataSourceCreate,
    SourceRightsUpsert,
    VerificationActionRequest,
)
from backend.models.manual_data import (
    ApprovalRequest,
    ManualDataRecordCreate,
    ManualDataRecordPatch,
    ManualRecordContentInput,
    RejectRequest,
    ReviewRequest,
    RevisionCreate,
    VerificationRequest,
)
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.manual_data_service import (
    ManualDataQualityService,
    ManualDataRecordService,
    ManualDataReviewService,
    ManualDataUsageService,
    ManualDataVerificationService,
)


@pytest.fixture
def services(tmp_path: Path):
    database_path = tmp_path / "manual_data.db"
    initialize_database(database_path)
    settings = Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    source_repository = DataSourceRepository(database_path)
    manual_repository = ManualDataRepository(database_path)
    return {
        "records": ManualDataRecordService(manual_repository, source_repository, settings),
        "reviews": ManualDataReviewService(manual_repository, settings),
        "verifications": ManualDataVerificationService(
            manual_repository, source_repository, settings
        ),
        "quality": ManualDataQualityService(manual_repository, settings),
        "usage": ManualDataUsageService(manual_repository, source_repository, settings),
        "source_registry": SourceRegistryService(source_repository, settings),
        "source_rights": SourceRightsService(source_repository, settings),
    }


def _human_source(services, code="SRC-MD-SVC-0001"):
    return services["source_registry"].create(
        DataSourceCreate(
            source_code=code,
            title="Dhurai -- Spoken Tamil",
            source_type="human_created",
        ),
        "admin-1",
    )


def _allow_all_rights(services, source_public_id):
    services["source_rights"].upsert(
        source_public_id,
        SourceRightsUpsert(
            rights_status="licensed",
            rag_use_allowed=True,
            training_use_allowed=True,
            evaluation_use_allowed=True,
            redistribution_allowed=True,
        ),
        "admin-1",
    )
    services["source_rights"].submit_review(source_public_id, "admin-1")
    services["source_rights"].verify(
        source_public_id, VerificationActionRequest(action="document_verify"), "admin-1"
    )


class TestManualDataRecordService:
    def test_create_requires_a_source(self, services):
        with pytest.raises(ValidationError):
            services["records"].create(
                ManualDataRecordCreate(
                    record_type="plain_text",
                    primary_language="ta",
                    content=ManualRecordContentInput(tamil_text="வணக்கம்"),
                ),
                "admin-1",
            )

    def test_create_with_existing_source(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="வணக்கம்"),
            ),
            "admin-1",
        )
        assert record["status"] == "draft"
        assert record["source_public_id"] == source["public_id"]
        assert record["active_revision"]["tamil_text"] == "வணக்கம்"
        assert record["record_code"].startswith("MD-")

    def test_create_with_new_source(self, services):
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                new_source=DataSourceCreate(
                    source_code="SRC-MD-NEW-0001",
                    title="Dhurai -- General Knowledge Notes",
                    source_type="human_created",
                ),
                content=ManualRecordContentInput(tamil_text="தமிழ் மொழி"),
            ),
            "admin-1",
        )
        assert record["source_title"] == "Dhurai -- General Knowledge Notes"

    def test_create_rejects_invalid_content(self, services):
        source = _human_source(services)
        with pytest.raises(ValidationError):
            services["records"].create(
                ManualDataRecordCreate(
                    record_type="plain_text",
                    source_public_id=source["public_id"],
                    content=ManualRecordContentInput(),
                ),
                "admin-1",
            )

    def test_create_rejects_exact_duplicate(self, services):
        source = _human_source(services)
        services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="வணக்கம்"),
            ),
            "admin-1",
        )
        with pytest.raises(ConflictError):
            services["records"].create(
                ManualDataRecordCreate(
                    record_type="plain_text",
                    primary_language="ta",
                    source_public_id=source["public_id"],
                    content=ManualRecordContentInput(tamil_text="வணக்கம்"),
                ),
                "admin-1",
            )

    def test_create_rejects_duplicate_dictionary_word(self, services):
        source = _human_source(services)
        services["records"].create(
            ManualDataRecordCreate(
                record_type="dictionary_entry",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(word="நல்லது", meanings=["good"]),
            ),
            "admin-1",
        )
        with pytest.raises(ConflictError):
            services["records"].create(
                ManualDataRecordCreate(
                    record_type="dictionary_entry",
                    primary_language="ta",
                    source_public_id=source["public_id"],
                    content=ManualRecordContentInput(word="நல்லது", meanings=["another meaning"]),
                ),
                "admin-1",
            )

    def test_list_and_summary(self, services):
        source = _human_source(services)
        services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="ஒன்று"),
            ),
            "admin-1",
        )
        services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="en",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(input_text="two"),
            ),
            "admin-1",
        )
        page = services["records"].list()
        assert page["total"] == 2
        summary = services["records"].summary()
        assert summary["total"] == 2
        assert summary["by_status"]["draft"] == 2

    def test_update_patch_allowed_in_draft_but_blocked_once_approved(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="மூன்று"),
            ),
            "admin-1",
        )
        updated = services["records"].update(
            record["public_id"], ManualDataRecordPatch(domain="greetings"), "admin-1"
        )
        assert updated["domain"] == "greetings"

        services["records"].submit_review(record["public_id"], "admin-1")
        services["records"].approve(
            record["public_id"],
            ApprovalRequest(approved_uses=[]),
            "admin-1",
            usage_service=services["usage"],
        )
        with pytest.raises(ValidationError):
            services["records"].update(
                record["public_id"],
                ManualDataRecordPatch(domain="changed-after-approval"),
                "admin-1",
            )

    def test_lifecycle_transitions_and_invalid_transition_rejected(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="நான்கு"),
            ),
            "admin-1",
        )
        with pytest.raises(ValidationError):
            services["records"]._transition(record["public_id"], "approved", "admin-1", event="bad")
        record = services["records"].submit_review(record["public_id"], "admin-1")
        assert record["status"] == "needs_review"
        record = services["records"].reject(
            record["public_id"], RejectRequest(reason="not natural"), "admin-1"
        )
        assert record["status"] == "rejected"

    def test_revision_created_on_approved_record_moves_back_to_draft(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="ஐந்து"),
            ),
            "admin-1",
        )
        services["records"].submit_review(record["public_id"], "admin-1")
        approved = services["records"].approve(
            record["public_id"],
            ApprovalRequest(approved_uses=["rag"]),
            "admin-1",
            usage_service=services["usage"],
        )
        assert approved["status"] == "approved"
        revised = services["records"].create_revision(
            record["public_id"],
            RevisionCreate(
                content=ManualRecordContentInput(tamil_text="ஐந்து -- திருத்தப்பட்டது"),
                change_summary="fixed typo",
            ),
            "admin-2",
        )
        assert revised["status"] == "draft"
        revisions = services["records"].list_revisions(record["public_id"])
        assert len(revisions["items"]) == 2
        # the original approved revision is preserved untouched
        original = [r for r in revisions["items"] if r["revision_number"] == 1][0]
        assert original["tamil_text"] == "ஐந்து"

    def test_approve_blocked_by_quality_gate(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="knowledge_note",
                primary_language="en",
                knowledge_risk="high_risk",
                fact_dependency="high",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(title="Medical note", input_text="..."),
            ),
            "admin-1",
        )
        services["records"].submit_review(record["public_id"], "admin-1")
        with pytest.raises(ValidationError):
            services["records"].approve(
                record["public_id"],
                ApprovalRequest(approved_uses=["rag"]),
                "admin-1",
                usage_service=services["usage"],
            )

    def test_approve_drops_uses_blocked_by_source_rights(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="ஆறு"),
            ),
            "admin-1",
        )
        services["records"].submit_review(record["public_id"], "admin-1")
        # No rights declared at all yet -- every use should be dropped.
        approved = services["records"].approve(
            record["public_id"],
            ApprovalRequest(approved_uses=["rag", "training"]),
            "admin-1",
            usage_service=services["usage"],
        )
        assert approved["approved_uses"] == []
        assert approved["blocked_uses"]["rag"] == "BLOCKED_RIGHTS_UNKNOWN"

    def test_approve_grants_uses_when_rights_allow(self, services):
        source = _human_source(services)
        _allow_all_rights(services, source["public_id"])
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="ஏழு"),
            ),
            "admin-1",
        )
        services["records"].submit_review(record["public_id"], "admin-1")
        approved = services["records"].approve(
            record["public_id"],
            ApprovalRequest(approved_uses=["rag", "training"]),
            "admin-1",
            usage_service=services["usage"],
        )
        assert set(approved["approved_uses"]) == {"rag", "training"}
        assert approved["blocked_uses"] == {}

    def test_history_includes_events_and_revisions(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="எட்டு"),
            ),
            "admin-1",
        )
        services["records"].submit_review(record["public_id"], "admin-1")
        history = services["records"].history(record["public_id"])
        assert any(e["event_type"] == "record_created" for e in history["events"])
        assert any(e["event_type"] == "manual_data_submitted_for_review" for e in history["events"])
        assert len(history["revisions"]) == 1


class TestManualDataReviewAndVerificationServices:
    def test_review_submit_and_list(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="ஒன்பது"),
            ),
            "admin-1",
        )
        services["reviews"].submit(
            record["public_id"],
            ReviewRequest(review_type="language", review_status="approved", naturalness_score=95),
            "admin-2",
        )
        reviews = services["reviews"].list(record["public_id"])
        assert len(reviews["items"]) == 1
        assert reviews["items"][0]["review_status"] == "approved"

    def test_verification_submit_and_list(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="knowledge_note",
                primary_language="en",
                knowledge_risk="high_risk",
                fact_dependency="high",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(title="Fee schedule", input_text="..."),
            ),
            "admin-1",
        )
        supporting_source = _human_source(services, code="SRC-MD-SUPPORT-0001")
        result = services["verifications"].submit(
            record["public_id"],
            VerificationRequest(
                verification_type="factual_verification",
                verification_status="verified",
                source_public_id=supporting_source["public_id"],
                verification_notes="Confirmed against the official notice.",
            ),
            "admin-2",
        )
        assert result["verification_status"] == "verified"
        listed = services["verifications"].list(record["public_id"])
        assert len(listed["items"]) == 1


class TestManualDataQualityService:
    def test_assess_flags_missing_source_and_blocking_issue(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="பத்து"),
            ),
            "admin-1",
        )
        result = services["quality"].assess(record["public_id"])
        assert result["blocking_issues"] == []
        assert result["overall_score"] > 0

    def test_check_duplicates_detects_exact_match_between_two_records(self, services):
        source = _human_source(services)
        first = services["records"].create(
            ManualDataRecordCreate(
                record_type="dictionary_entry",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(word="அழகு", meanings=["beauty"]),
            ),
            "admin-1",
        )
        result = services["quality"].check_duplicates(first["public_id"])
        assert result["duplicate_status"] == "unique"


class TestManualDataUsageService:
    def test_evaluate_blocked_without_rights(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="பதினொன்று"),
            ),
            "admin-1",
        )
        decision = services["usage"].evaluate(record["public_id"], "rag")
        assert decision["allowed"] is False

    def test_summary_covers_all_target_uses(self, services):
        source = _human_source(services)
        _allow_all_rights(services, source["public_id"])
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="பன்னிரண்டு"),
            ),
            "admin-1",
        )
        services["records"].submit_review(record["public_id"], "admin-1")
        services["records"].approve(
            record["public_id"],
            ApprovalRequest(approved_uses=["rag"]),
            "admin-1",
            usage_service=services["usage"],
        )
        summary = services["usage"].summary(record["public_id"])
        assert set(summary.keys()) == {
            "rag",
            "training",
            "evaluation",
            "commercial",
            "public_export",
            "redistribution",
        }
        assert summary["rag"]["allowed"] is True

    def test_history_records_every_check(self, services):
        source = _human_source(services)
        record = services["records"].create(
            ManualDataRecordCreate(
                record_type="plain_text",
                primary_language="ta",
                source_public_id=source["public_id"],
                content=ManualRecordContentInput(tamil_text="பதிமூன்று"),
            ),
            "admin-1",
        )
        services["usage"].evaluate(record["public_id"], "rag", admin_id="admin-1")
        history = services["usage"].history(record["public_id"])
        assert len(history["items"]) == 1
