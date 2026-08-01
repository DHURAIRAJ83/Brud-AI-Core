"""Tests for the Tamil correction-rule registry lifecycle (Task
Finalization §13/§14/§15): draft -> needs_review -> approved -> active,
and that ambiguous/meaning-sensitive rules are marked human-review-required
and never automatic."""

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.document_tamil_correction_registry_service import (
    DocumentTamilCorrectionRegistryService,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000055"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "tamil_registry.db"
    initialize_database(database_path)
    return Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )


@pytest.fixture
def service(settings: Settings) -> DocumentTamilCorrectionRegistryService:
    return DocumentTamilCorrectionRegistryService(settings)


class TestRuleCreation:
    def test_mechanical_rule_is_marked_automatic_proposal_allowed(self, service):
        rule = service.create_rule(
            incorrect_form="ொ்", approved_correction="ொ", issue_category="known_ocr_substitution",
            evidence="Duplicated virama after a compound vowel sign.", confidence_band="high",
            meaning_change_risk="mechanical", admin_id=ADMIN_ID,
        )
        assert rule["automatic_proposal_allowed"] == 1
        assert rule["human_review_required"] == 0
        assert rule["status"] == "draft"

    def test_ambiguous_rule_is_marked_human_review_required(self, service):
        rule = service.create_rule(
            incorrect_form="வார்த்தை", approved_correction="சொல்", issue_category="spelling_variant",
            evidence="Two attested spellings in the reviewed source.", confidence_band="low",
            meaning_change_risk="ambiguous", admin_id=ADMIN_ID,
        )
        assert rule["automatic_proposal_allowed"] == 0
        assert rule["human_review_required"] == 1


class TestLifecycle:
    def test_full_lifecycle_to_active(self, service):
        rule = service.create_rule(
            incorrect_form="a", approved_correction="b", issue_category="pulli_error",
            evidence="e", confidence_band="high", meaning_change_risk="mechanical",
            admin_id=ADMIN_ID,
        )
        service.transition(rule["public_id"], "submit_review", ADMIN_ID)
        service.transition(rule["public_id"], "approve", ADMIN_ID)
        activated = service.transition(rule["public_id"], "activate", ADMIN_ID)
        assert activated["status"] == "active"
        assert activated["rule_version"] == 2
        history = service.review_history(rule["public_id"])
        assert [item["action"] for item in history["items"]] == [
            "submit_review", "approve", "activate",
        ]

    def test_draft_cannot_be_activated_directly(self, service):
        rule = service.create_rule(
            incorrect_form="a", approved_correction="b", issue_category="pulli_error",
            evidence="e", confidence_band="high", meaning_change_risk="mechanical",
            admin_id=ADMIN_ID,
        )
        with pytest.raises(ValidationError, match="cannot transition"):
            service.transition(rule["public_id"], "activate", ADMIN_ID)

    def test_active_rule_can_still_be_rejected(self, service):
        rule = service.create_rule(
            incorrect_form="a", approved_correction="b", issue_category="pulli_error",
            evidence="e", confidence_band="high", meaning_change_risk="mechanical",
            admin_id=ADMIN_ID,
        )
        service.transition(rule["public_id"], "submit_review", ADMIN_ID)
        service.transition(rule["public_id"], "approve", ADMIN_ID)
        service.transition(rule["public_id"], "activate", ADMIN_ID)
        rejected = service.transition(rule["public_id"], "reject", ADMIN_ID)
        assert rejected["status"] == "rejected"
