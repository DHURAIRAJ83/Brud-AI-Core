from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
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
    DatasetVerificationReportError,
    ExternalDatasetConflictService,
    ExternalDatasetReverificationService,
    ExternalDatasetVerificationReportService,
    ExternalDatasetWithdrawalService,
)
from backend.services.dataset_verification_transport import EvidenceHttpResponse
from core_model.data_verification import ADMIN_ONLY_PERMISSION_STATUSES, PERMISSION_TYPES

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


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


def _create_case(settings: Settings, *, candidate_overrides: dict | None = None) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate_values = {
        "canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus",
        "declared_licence": "CC-BY-4.0",
    }
    candidate_values.update(candidate_overrides or {})
    candidate = discovery.create_candidate(session["public_id"], candidate_values)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    return repository.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )


def _verify_licence(
    settings: Settings, case_public_id: str, *, text: str = "Licensed under CC-BY-4.0."
) -> None:
    ExternalDatasetEvidenceService(settings).add_manual_evidence(
        case_public_id, evidence_type="licence_file", content_text=text, admin_public_id=ADMIN_ID
    )
    ExternalDatasetLicenceService(settings).assess(case_public_id, admin_public_id=ADMIN_ID)


def _approve_all_permissions(
    settings: Settings, case_public_id: str, *, status: str = "approved"
) -> None:
    perm_service = ExternalDatasetPermissionAssessmentService(settings)
    perm_service.assess(case_public_id, admin_public_id=ADMIN_ID)
    perm_service.assess_commercial_use(
        case_public_id, intended_use_category="research", admin_public_id=ADMIN_ID
    )
    for permission_type in PERMISSION_TYPES:
        perm_service.review(
            case_public_id, permission_type,
            status=status, reviewed_by=REVIEWER_ID, reason=f"Reviewed {permission_type} manually",
        )


def _fake_transport(*responses: EvidenceHttpResponse):
    remaining = list(responses)

    def transport(url, headers, timeout_seconds):
        del url, headers, timeout_seconds
        return remaining.pop(0)

    return transport


def _fake_resolver(hostname: str) -> list[str]:
    del hostname
    return ["18.0.0.1"]


# -- ExternalDatasetConflictService ---------------------------------------------


def test_detect_finds_declared_vs_licence_file_conflict(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"], text="Licensed under CC-BY-NC-4.0.")
    service = ExternalDatasetConflictService(settings)
    conflicts = service.detect(case["public_id"], admin_public_id=ADMIN_ID)
    assert any(c["conflict_type"] == "declared_vs_licence_file" for c in conflicts)
    assert any(c["conflict_severity"] == "blocking" for c in conflicts)
    assert service.has_unresolved_blocking_conflict(case["public_id"]) is True


def test_detect_is_idempotent_for_the_same_unresolved_conflict(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"], text="Licensed under CC-BY-NC-4.0.")
    service = ExternalDatasetConflictService(settings)
    first = service.detect(case["public_id"], admin_public_id=ADMIN_ID)
    second = service.detect(case["public_id"], admin_public_id=ADMIN_ID)
    assert len(first) == 1
    assert len(second) == 0


def test_detect_finds_no_conflict_on_clean_case(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"])
    service = ExternalDatasetConflictService(settings)
    conflicts = service.detect(case["public_id"], admin_public_id=ADMIN_ID)
    assert conflicts == []
    assert service.has_unresolved_blocking_conflict(case["public_id"]) is False


def test_resolve_requires_nonempty_reason(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"], text="Licensed under CC-BY-NC-4.0.")
    service = ExternalDatasetConflictService(settings)
    [conflict] = service.detect(case["public_id"], admin_public_id=ADMIN_ID)
    with pytest.raises(DatasetVerificationReportError):
        service.resolve(
            case["public_id"], conflict["public_id"],
            resolution_status="resolved", resolution_reason="   ", admin_public_id=ADMIN_ID,
        )


def test_resolve_clears_unresolved_status_and_blocking_gate(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"], text="Licensed under CC-BY-NC-4.0.")
    service = ExternalDatasetConflictService(settings)
    [conflict] = service.detect(case["public_id"], admin_public_id=ADMIN_ID)
    assert service.has_unresolved_blocking_conflict(case["public_id"]) is True

    service.resolve(
        case["public_id"], conflict["public_id"],
        resolution_status="resolved", resolution_reason="Confirmed CC-BY-NC-4.0 is correct",
        admin_public_id=ADMIN_ID,
    )
    assert service.list_unresolved_conflicts(case["public_id"]) == []
    assert service.has_unresolved_blocking_conflict(case["public_id"]) is False

    repository = DatasetVerificationRepository(settings.resolved_database_path)
    assert repository.get_case(case["public_id"])["conflict_count"] == 0


# -- ExternalDatasetVerificationReportService ------------------------------------


def test_finalize_succeeds_and_locks_the_case(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"])
    _approve_all_permissions(settings, case["public_id"], status="approved")
    service = ExternalDatasetVerificationReportService(settings)
    finalized = service.finalize(case["public_id"], admin_public_id=ADMIN_ID)
    assert finalized["locked_at"] is not None
    assert finalized["status"] == "verified"
    assert finalized["report"]["licence_status"]["value"] == "verified"


def test_finalize_refuses_twice(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"])
    _approve_all_permissions(settings, case["public_id"])
    service = ExternalDatasetVerificationReportService(settings)
    service.finalize(case["public_id"], admin_public_id=ADMIN_ID)
    with pytest.raises(DatasetVerificationReportError):
        service.finalize(case["public_id"], admin_public_id=ADMIN_ID)


def test_finalize_blocked_by_unresolved_blocking_conflict(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"], text="Licensed under CC-BY-NC-4.0.")
    ExternalDatasetConflictService(settings).detect(case["public_id"], admin_public_id=ADMIN_ID)
    service = ExternalDatasetVerificationReportService(settings)
    with pytest.raises(DatasetVerificationReportError):
        service.finalize(case["public_id"], admin_public_id=ADMIN_ID)


def test_finalize_blocked_by_stale_reviewed_evidence(settings: Settings) -> None:
    case = _create_case(settings)
    evidence_service = ExternalDatasetEvidenceService(settings)
    snapshot = evidence_service.add_manual_evidence(
        case["public_id"], evidence_type="licence_file",
        content_text="Licensed under CC-BY-4.0.", admin_public_id=ADMIN_ID,
    )
    ExternalDatasetLicenceService(settings).assess(case["public_id"], admin_public_id=ADMIN_ID)

    perm_service = ExternalDatasetPermissionAssessmentService(settings)
    perm_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    perm_service.review(
        case["public_id"], "rag_use",
        status="approved", reviewed_by=REVIEWER_ID, reason="Licence confirms RAG use",
    )

    # Superseding the reviewed evidence changes its checksum "as of
    # review time" relative to the newly-current snapshot.
    evidence_service.repository.add_evidence_snapshot(
        case["public_id"],
        {
            "candidate_public_id": case["candidate_public_id"],
            "evidence_type": "licence_file",
            "authority_level": "primary",
            "content_type": "text/plain",
            "content_checksum": "b" * 64,
            "content_text": "Licensed under CC-BY-NC-4.0.",
            "supersedes_evidence_public_id": snapshot["public_id"],
            "created_by_admin_public_id": ADMIN_ID,
        },
    )

    service = ExternalDatasetVerificationReportService(settings)
    with pytest.raises(DatasetVerificationReportError):
        service.finalize(case["public_id"], admin_public_id=ADMIN_ID)


def test_finalize_status_blocked_when_any_permission_prohibited(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"])
    perm_service = ExternalDatasetPermissionAssessmentService(settings)
    perm_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    perm_service.assess_commercial_use(
        case["public_id"], intended_use_category="research", admin_public_id=ADMIN_ID
    )
    for permission_type in PERMISSION_TYPES:
        status = "prohibited" if permission_type == "training_use" else "approved"
        perm_service.review(
            case["public_id"], permission_type,
            status=status, reviewed_by=REVIEWER_ID, reason=f"Reviewed {permission_type}",
        )
    service = ExternalDatasetVerificationReportService(settings)
    finalized = service.finalize(case["public_id"], admin_public_id=ADMIN_ID)
    assert finalized["status"] == "blocked"


def test_finalize_status_insufficient_evidence_when_evidence_incomplete(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetVerificationReportService(settings)
    finalized = service.finalize(case["public_id"], admin_public_id=ADMIN_ID)
    assert finalized["status"] == "insufficient_evidence"


def test_finalize_report_tags_fields_with_provenance(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"])
    _approve_all_permissions(settings, case["public_id"])
    service = ExternalDatasetVerificationReportService(settings)
    finalized = service.finalize(case["public_id"], admin_public_id=ADMIN_ID)
    for field in finalized["report"].values():
        assert set(field) == {"value", "provenance"}
        assert field["provenance"] in (
            "verified_fact", "provider_declared", "assistant_inference",
            "admin_decision", "unknown",
        )


# -- ExternalDatasetReverificationService ----------------------------------------


def test_reverify_with_unchanged_evidence_reports_no_source_change(settings: Settings) -> None:
    case = _create_case(settings)
    evidence_service = ExternalDatasetEvidenceService(
        settings,
        transport=_fake_transport(
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "text/plain"}, body=b"CC-BY-4.0"
            )
        ),
        resolver=_fake_resolver,
    )
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    repository.update_case(case["public_id"], {"approved_upstream_domains_json": '["example.org"]'})
    evidence_service.collect_evidence(
        case["public_id"], evidence_type="licence_file",
        source_url="https://example.org/LICENSE", admin_public_id=ADMIN_ID,
    )

    evidence_service._transport = _fake_transport(  # noqa: SLF001
        EvidenceHttpResponse(
            status_code=200, headers={"content-type": "text/plain"}, body=b"CC-BY-4.0"
        )
    )
    reverify_service = ExternalDatasetReverificationService(
        settings, evidence_service=evidence_service
    )
    result = reverify_service.check(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["source_changed"] is False
    assert repository.get_case(case["public_id"])["verification_expiry_status"] == "current"


def test_reverify_after_finalize_detects_source_change_and_demotes_permissions(
    settings: Settings,
) -> None:
    case = _create_case(settings)
    evidence_service = ExternalDatasetEvidenceService(
        settings,
        transport=_fake_transport(
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "text/plain"},
                body=b"Licensed under CC-BY-4.0.",
            )
        ),
        resolver=_fake_resolver,
    )
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    repository.update_case(case["public_id"], {"approved_upstream_domains_json": '["example.org"]'})
    evidence_service.collect_evidence(
        case["public_id"], evidence_type="licence_file",
        source_url="https://example.org/LICENSE", admin_public_id=ADMIN_ID,
    )
    ExternalDatasetLicenceService(settings).assess(case["public_id"], admin_public_id=ADMIN_ID)
    _approve_all_permissions(settings, case["public_id"])

    report_service = ExternalDatasetVerificationReportService(settings)
    finalized = report_service.finalize(case["public_id"], admin_public_id=ADMIN_ID)
    assert finalized["locked_at"] is not None

    evidence_service._transport = _fake_transport(  # noqa: SLF001
        EvidenceHttpResponse(
            status_code=200,
            headers={"content-type": "text/plain"},
            body=b"Licensed under CC-BY-NC-4.0.",
        )
    )
    reverify_service = ExternalDatasetReverificationService(
        settings, evidence_service=evidence_service
    )
    result = reverify_service.check(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["source_changed"] is True

    updated_case = repository.get_case(case["public_id"])
    assert updated_case["verification_expiry_status"] == "source_changed"

    for permission_type in PERMISSION_TYPES:
        assessment = repository.get_permission_assessment(case["public_id"], permission_type)
        assert assessment["status"] not in ADMIN_ONLY_PERMISSION_STATUSES


# -- ExternalDatasetWithdrawalService ---------------------------------------------


def test_record_notice_rejects_unknown_notice_type(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetWithdrawalService(settings)
    with pytest.raises(DatasetVerificationReportError):
        service.record_notice(
            case["public_id"], {"notice_type": "not_a_real_type"}, admin_public_id=ADMIN_ID
        )


def test_record_notice_sets_case_withdrawn_and_impact_summary(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"])
    _approve_all_permissions(settings, case["public_id"])

    service = ExternalDatasetWithdrawalService(settings)
    notice = service.record_notice(
        case["public_id"],
        {"notice_type": "licence_changed", "notice_text": "Rights holder changed the licence"},
        admin_public_id=ADMIN_ID,
    )
    assert notice["impact_status"] == "assessed"
    assert notice["impact_summary"]["human_review_required"] is True
    assert notice["impact_summary"]["future_training_use_blocked"] is True
    assert set(PERMISSION_TYPES) >= set(notice["impact_summary"]["previously_approved_permissions"])

    repository = DatasetVerificationRepository(settings.resolved_database_path)
    assert repository.get_case(case["public_id"])["verification_expiry_status"] == "withdrawn"


def test_record_notice_works_on_an_already_finalized_case(settings: Settings) -> None:
    case = _create_case(settings)
    _verify_licence(settings, case["public_id"])
    _approve_all_permissions(settings, case["public_id"])
    ExternalDatasetVerificationReportService(settings).finalize(
        case["public_id"], admin_public_id=ADMIN_ID
    )

    service = ExternalDatasetWithdrawalService(settings)
    notice = service.record_notice(
        case["public_id"], {"notice_type": "dataset_withdrawn"}, admin_public_id=ADMIN_ID
    )
    assert notice["impact_status"] == "assessed"
