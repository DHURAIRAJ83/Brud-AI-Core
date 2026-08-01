import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.services.production_rag_candidate_service import ProductionRagCandidateService
from backend.services.production_rag_eligibility_service import ProductionRagEligibilityService
from backend.services.production_rag_promotion_service import ProductionRagPromotionService
from tests.backend.test_training_suitability_and_transformation import (
    ADMIN_ID,
    _build_accepted_experiment,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "production_rag.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _mark_eligible_for_production_rag(settings: Settings, experiment_public_id: str) -> None:
    """`_build_accepted_experiment()` fabricates a Phase 13 report directly
    via `RagSandboxRepository.add_report()`, bypassing the real
    `RagSandboxReportService.finalize_report()` that would otherwise set
    the experiment's own `eligible_for_production_rag_proposal` flag --
    the same simplification the Phase 14 test suite already relies on for
    `production_rag_readiness`. This helper closes that one gap directly."""

    with sqlite3.connect(settings.resolved_database_path) as connection:
        connection.execute(
            "UPDATE rag_sandbox_experiments SET eligible_for_production_rag_proposal=1 "
            "WHERE public_id=?",
            (experiment_public_id,),
        )
        connection.commit()


def _insert_knowledge_space(settings: Settings) -> str:
    public_id = str(uuid4())
    with sqlite3.connect(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO rag_knowledge_spaces(public_id,name,slug,created_by_admin_public_id)
            VALUES (?,?,?,?)""",
            (public_id, "Prod Space", f"prod-space-{public_id[:8]}", ADMIN_ID),
        )
        connection.commit()
    return public_id


# -- eligibility -----------------------------------------------------------------------------


def test_eligibility_blocks_without_production_rag_flag(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    service = ProductionRagEligibilityService(settings)
    result = service.check_eligibility(built["experiment"]["public_id"])
    assert result["eligible"] is False
    assert any(
        "eligible_for_production_rag_proposal" in reason for reason in result["blocking_reasons"]
    )


def test_eligibility_passes_once_flag_and_report_are_current(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    _mark_eligible_for_production_rag(settings, built["experiment"]["public_id"])
    service = ProductionRagEligibilityService(settings)
    result = service.check_eligibility(built["experiment"]["public_id"])
    assert result["eligible"] is True, result["blocking_reasons"]
    assert result["accepted_record_checksum_set_hash"]
    assert result["report_public_id"]


def test_eligibility_blocks_unapproved_commercial_use(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    _mark_eligible_for_production_rag(settings, built["experiment"]["public_id"])
    with sqlite3.connect(settings.resolved_database_path) as connection:
        connection.execute(
            "UPDATE external_dataset_permission_assessments SET status='not_approved' "
            "WHERE permission_type='commercial_use'"
        )
        connection.commit()

    service = ProductionRagEligibilityService(settings)
    result = service.check_eligibility(
        built["experiment"]["public_id"], commercial_use_context="commercial"
    )
    assert result["eligible"] is False
    assert any("commercial" in reason for reason in result["blocking_reasons"])


def test_eligibility_blocks_when_no_acceptance_exists(settings: Settings) -> None:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )
    from backend.database.repositories.dataset_verification import (
        DatasetVerificationRepository,
    )
    from backend.database.repositories.external_dataset_discovery import (
        ExternalDatasetDiscoveryRepository,
    )
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-x", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "X", "normalized_name": "x"}
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"], "verification_code": "VC-X",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    sandbox = RagSandboxRepository(settings.resolved_database_path)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-X", "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"], "purpose": "manual_review",
            "selection_method": "deterministic_first_n", "requested_count": 10,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    experiment = sandbox.create_experiment(
        {
            "experiment_code": "RSE-x", "sample_import_public_id": sample_import["public_id"],
            "sample_report_public_id": None, "verification_case_public_id": case["public_id"],
            "purpose": "production_rag_readiness", "created_by_admin_public_id": ADMIN_ID,
        }
    )
    service = ProductionRagEligibilityService(settings)
    result = service.check_eligibility(experiment["public_id"])
    assert result["eligible"] is False
    assert any("acceptance" in reason for reason in result["blocking_reasons"])


# -- promotion request -----------------------------------------------------------------------


def test_create_request_blocked_when_not_eligible(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    space_id = _insert_knowledge_space(settings)
    service = ProductionRagPromotionService(settings)
    with pytest.raises(ValidationError):
        service.create_request(
            {
                "rag_sandbox_experiment_public_id": built["experiment"]["public_id"],
                "knowledge_space_public_id": space_id,
                "selected_record_ids": [r["public_id"] for r in built["records"]],
            },
            admin_id=ADMIN_ID,
        )


def test_create_request_and_approval_lifecycle(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    _mark_eligible_for_production_rag(settings, built["experiment"]["public_id"])
    space_id = _insert_knowledge_space(settings)
    service = ProductionRagPromotionService(settings)
    request = service.create_request(
        {
            "rag_sandbox_experiment_public_id": built["experiment"]["public_id"],
            "knowledge_space_public_id": space_id,
            "selected_record_ids": [r["public_id"] for r in built["records"]],
        },
        admin_id=ADMIN_ID,
    )
    assert request["status"] == "draft"
    assert request["target_fingerprint"]

    service.submit_for_review(request["public_id"], admin_id=ADMIN_ID)
    approval = service.request_approval(request["public_id"], admin_id=ADMIN_ID)
    assert approval["status"] == "pending"

    approved = service.approve(approval["public_id"], admin_id=ADMIN_ID)
    assert approved["status"] == "approved"

    repository = ProductionReadinessRepository(settings.resolved_database_path)
    refreshed = repository.get_rag_promotion_request(request["public_id"])
    assert refreshed["status"] == "approved"


# -- candidate build guard clauses (full ingestion pipeline is exercised manually --
# see docs/production/phase15_text_nlp_production_readiness_plan.md known limitations) ------


def test_build_candidate_requires_approved_request(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    _mark_eligible_for_production_rag(settings, built["experiment"]["public_id"])
    space_id = _insert_knowledge_space(settings)
    promotion_service = ProductionRagPromotionService(settings)
    request = promotion_service.create_request(
        {
            "rag_sandbox_experiment_public_id": built["experiment"]["public_id"],
            "knowledge_space_public_id": space_id,
            "selected_record_ids": [r["public_id"] for r in built["records"]],
        },
        admin_id=ADMIN_ID,
    )
    candidate_service = ProductionRagCandidateService(settings)
    with pytest.raises(ValidationError):
        candidate_service.build_candidate(request["public_id"], admin_id=ADMIN_ID)
