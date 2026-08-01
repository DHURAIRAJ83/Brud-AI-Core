from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_verification_evidence_service import (
    ExternalDatasetEvidenceService,
    ExternalDatasetLicenceService,
)
from backend.services.dataset_verification_permission_service import (
    ExternalDatasetPermissionAssessmentService,
)
from backend.services.dataset_verification_report_service import (
    ExternalDatasetVerificationReportService,
)
from backend.services.dataset_verification_source_rights_service import (
    DatasetVerificationSourceRightsError,
    ExternalDatasetSourceRightsIntegrationService,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "verification.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _create_finalized_case(settings: Settings, *, candidate_overrides: dict | None = None) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate_values = {
        "canonical_name": "Tamil Corpus",
        "normalized_name": "tamil corpus",
        "declared_licence": "CC-BY-4.0",
        "homepage_url": "https://example.org/tamil-corpus",
        "organization": "Example Org",
    }
    candidate_values.update(candidate_overrides or {})
    candidate = discovery.create_candidate(session["public_id"], candidate_values)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    case = repository.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )

    ExternalDatasetEvidenceService(settings).add_manual_evidence(
        case["public_id"], evidence_type="licence_file",
        content_text="Licensed under CC-BY-4.0.", admin_public_id=ADMIN_ID,
    )
    ExternalDatasetLicenceService(settings).assess(case["public_id"], admin_public_id=ADMIN_ID)
    perm_service = ExternalDatasetPermissionAssessmentService(settings)
    perm_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    perm_service.assess_commercial_use(
        case["public_id"], intended_use_category="research", admin_public_id=ADMIN_ID
    )
    ExternalDatasetVerificationReportService(settings).finalize(
        case["public_id"], admin_public_id=ADMIN_ID
    )
    return repository.get_case(case["public_id"])


def _create_matching_data_source(
    settings: Settings, *, organization_name: str, source_url: str
) -> str:
    ds_repo = DataSourceRepository(settings.resolved_database_path)
    with ds_repo.transaction() as connection:
        return ds_repo.create_source(
            connection,
            {
                "source_code": "src-1",
                "title": "Tamil Corpus",
                "source_type": "open_dataset",
                "organization_name": organization_name,
                "source_url": source_url,
                "description": "",
                "knowledge_risk": "low",
                "fact_dependency": "low",
                "verification_required": False,
                "independent_reviewer_required": False,
                "internal_rag_policy_allows_unknown_rights": False,
                "created_by_admin_public_id": ADMIN_ID,
                "status": "draft",
            },
        )


# -- governance eligibility (embedded in the finalized report) ------------------


def test_finalized_report_includes_governance_eligibility_signals(settings: Settings) -> None:
    case = _create_finalized_case(settings)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    finalized = repository.get_case(case["public_id"])
    eligibility = finalized["report"]["governance_eligibility"]["value"]
    assert set(eligibility) == {
        "rag_use_eligible", "training_use_eligible",
        "evaluation_use_eligible", "commercial_use_eligible",
    }
    # Nothing was Admin-reviewed yet -- automated assessment alone can
    # never make anything eligible.
    assert all(value is False for value in eligibility.values())


def test_governance_eligibility_true_only_after_admin_approval(settings: Settings) -> None:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-2", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {"canonical_name": "X", "normalized_name": "x", "declared_licence": "CC-BY-4.0"},
    )
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    case = repository.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-2",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    ExternalDatasetEvidenceService(settings).add_manual_evidence(
        case["public_id"], evidence_type="licence_file",
        content_text="Licensed under CC-BY-4.0.", admin_public_id=ADMIN_ID,
    )
    ExternalDatasetLicenceService(settings).assess(case["public_id"], admin_public_id=ADMIN_ID)
    perm_service = ExternalDatasetPermissionAssessmentService(settings)
    perm_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    perm_service.assess_commercial_use(
        case["public_id"], intended_use_category="research", admin_public_id=ADMIN_ID
    )
    perm_service.review(
        case["public_id"], "rag_use",
        status="approved", reviewed_by=ADMIN_ID, reason="Licence confirms RAG use",
    )
    finalized = ExternalDatasetVerificationReportService(settings).finalize(
        case["public_id"], admin_public_id=ADMIN_ID
    )
    eligibility = finalized["report"]["governance_eligibility"]["value"]
    assert eligibility["rag_use_eligible"] is True
    assert eligibility["training_use_eligible"] is False


# -- Source & Rights integration -------------------------------------------------


def test_find_existing_source_by_url(settings: Settings) -> None:
    case = _create_finalized_case(settings)
    _create_matching_data_source(
        settings, organization_name="Different Org", source_url="https://example.org/tamil-corpus"
    )
    service = ExternalDatasetSourceRightsIntegrationService(settings)
    found = service.find_existing_source(case["public_id"])
    assert found is not None
    assert found["source_url"] == "https://example.org/tamil-corpus"


def test_find_existing_source_by_organization(settings: Settings) -> None:
    case = _create_finalized_case(settings)
    _create_matching_data_source(
        settings, organization_name="Example Org", source_url="https://different.example/x"
    )
    service = ExternalDatasetSourceRightsIntegrationService(settings)
    found = service.find_existing_source(case["public_id"])
    assert found is not None
    assert found["organization_name"] == "Example Org"


def test_find_existing_source_returns_none_when_no_match(settings: Settings) -> None:
    case = _create_finalized_case(settings)
    service = ExternalDatasetSourceRightsIntegrationService(settings)
    assert service.find_existing_source(case["public_id"]) is None


def test_draft_proposal_refuses_on_unfinalized_case(settings: Settings) -> None:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-3", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "X", "normalized_name": "x"}
    )
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    case = repository.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-3",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    service = ExternalDatasetSourceRightsIntegrationService(settings)
    with pytest.raises(DatasetVerificationSourceRightsError):
        service.draft_source_update_proposal(case["public_id"], admin_id=ADMIN_ID)


def test_draft_proposal_declines_when_no_existing_source(settings: Settings) -> None:
    case = _create_finalized_case(settings)
    service = ExternalDatasetSourceRightsIntegrationService(settings)
    result = service.draft_source_update_proposal(case["public_id"], admin_id=ADMIN_ID)
    assert result["drafted"] is False
    assert "reason" in result


def test_draft_proposal_creates_pending_proposal_when_source_exists(settings: Settings) -> None:
    case = _create_finalized_case(settings)
    _create_matching_data_source(
        settings, organization_name="Example Org", source_url="https://example.org/tamil-corpus"
    )
    service = ExternalDatasetSourceRightsIntegrationService(settings)
    result = service.draft_source_update_proposal(case["public_id"], admin_id=ADMIN_ID)
    assert result["drafted"] is True
    assert result["proposal"].status == "pending"
    assert result["proposal"].action_type == "link_dataset_verification_rights"
    assert result["proposal"].request_payload["rights_status"] == "licensed"


def test_draft_proposal_never_writes_directly_to_data_sources(settings: Settings) -> None:
    case = _create_finalized_case(settings)
    source_public_id = _create_matching_data_source(
        settings, organization_name="Example Org", source_url="https://example.org/tamil-corpus"
    )
    service = ExternalDatasetSourceRightsIntegrationService(settings)
    service.draft_source_update_proposal(case["public_id"], admin_id=ADMIN_ID)

    ds_repo = DataSourceRepository(settings.resolved_database_path)
    with ds_repo.transaction() as connection:
        source = ds_repo.source(connection, source_public_id)
        rights = ds_repo.rights_for_source(connection, source["id"])
    # No `source_rights` row exists yet -- only a *pending* proposal
    # was drafted; no write happened until an Admin reviews/executes it.
    assert rights is None


def test_full_pipeline_writes_rights_only_after_admin_review_and_execute(
    settings: Settings,
) -> None:
    from backend.services.admin_assistant_service import AdminAssistantService

    case = _create_finalized_case(settings)
    source_public_id = _create_matching_data_source(
        settings, organization_name="Example Org", source_url="https://example.org/tamil-corpus"
    )
    service = ExternalDatasetSourceRightsIntegrationService(settings)
    result = service.draft_source_update_proposal(case["public_id"], admin_id=ADMIN_ID)
    proposal = result["proposal"]

    assistant = AdminAssistantService(settings)
    assistant.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    executed = assistant.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.status == "approved"

    ds_repo = DataSourceRepository(settings.resolved_database_path)
    with ds_repo.transaction() as connection:
        source = ds_repo.source(connection, source_public_id)
        rights = ds_repo.rights_for_source(connection, source["id"])
    assert rights is not None
    assert rights["rights_status"] == "licensed"
