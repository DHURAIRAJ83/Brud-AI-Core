from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_verification_evidence_service import (
    DatasetVerificationError,
    ExternalDatasetEvidenceService,
    ExternalDatasetIdentityVerificationService,
    ExternalDatasetLicenceService,
    ExternalDatasetTermsService,
)
from backend.services.dataset_verification_transport import EvidenceHttpResponse

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


@pytest.fixture
def repository(settings: Settings) -> DatasetVerificationRepository:
    return DatasetVerificationRepository(settings.resolved_database_path)


def _create_case(settings: Settings, *, candidate_overrides: dict | None = None) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate_values = {
        "canonical_name": "Tamil Corpus",
        "normalized_name": "tamil corpus",
        "homepage_url": "https://huggingface.co/datasets/example/tamil-corpus",
        "organization": "Example Org",
        "version": "1.0",
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


def _allow_domain(settings: Settings, case_public_id: str, domain: str) -> None:
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    repository.update_case(
        case_public_id, {"approved_upstream_domains_json": dumps_json([domain])}
    )


def _transport(*responses: EvidenceHttpResponse):
    remaining = list(responses)

    def transport(url, headers, timeout_seconds):
        del url, headers, timeout_seconds
        return remaining.pop(0)

    return transport


def _resolver(hostname: str) -> list[str]:
    del hostname
    return ["18.0.0.1"]


# -- ExternalDatasetEvidenceService --------------------------------------------


def test_collect_evidence_success_marks_evidence_status_complete(settings: Settings) -> None:
    case = _create_case(settings)
    _allow_domain(settings, case["public_id"], "huggingface.co")
    service = ExternalDatasetEvidenceService(
        settings,
        transport=_transport(
            EvidenceHttpResponse(
                status_code=200,
                headers={"content-type": "text/plain"},
                body=b"CC-BY-4.0",
            )
        ),
        resolver=_resolver,
    )
    snapshot = service.collect_evidence(
        case["public_id"],
        evidence_type="licence_file",
        source_url="https://huggingface.co/datasets/example/tamil-corpus/LICENSE",
        admin_public_id=ADMIN_ID,
    )
    assert snapshot["content_text"] == "CC-BY-4.0"
    assert snapshot["retrieval_status"] == "success"

    updated_case = service.repository.get_case(case["public_id"])
    assert updated_case["evidence_status"] == "complete"


def test_collect_evidence_rejects_domain_outside_allowlist(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetEvidenceService(settings, transport=_transport())
    with pytest.raises(DatasetVerificationError):
        service.collect_evidence(
            case["public_id"],
            evidence_type="licence_file",
            source_url="https://attacker.example.com/licence.txt",
            admin_public_id=ADMIN_ID,
        )
    events = service.repository.list_events(case["public_id"])
    assert any(event["event_type"] == "evidence_collection_failed" for event in events)


def test_add_manual_evidence_creates_manual_snapshot(settings: Settings) -> None:
    case = _create_case(settings)
    service = ExternalDatasetEvidenceService(settings)
    snapshot = service.add_manual_evidence(
        case["public_id"],
        evidence_type="terms_of_use",
        content_text="Terms of use text captured manually",
        admin_public_id=ADMIN_ID,
    )
    assert snapshot["retrieval_status"] == "manual"
    assert snapshot["content_checksum"]

    events = service.repository.list_events(case["public_id"])
    assert any(event["event_type"] == "manual_evidence_added" for event in events)


def test_refresh_evidence_detects_source_changed(settings: Settings) -> None:
    case = _create_case(settings)
    _allow_domain(settings, case["public_id"], "huggingface.co")
    service = ExternalDatasetEvidenceService(
        settings,
        transport=_transport(
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "text/plain"}, body=b"CC-BY-4.0"
            )
        ),
        resolver=_resolver,
    )
    original = service.collect_evidence(
        case["public_id"],
        evidence_type="licence_file",
        source_url="https://huggingface.co/datasets/example/tamil-corpus/LICENSE",
        admin_public_id=ADMIN_ID,
    )

    service._transport = _transport(
        EvidenceHttpResponse(
            status_code=200, headers={"content-type": "text/plain"}, body=b"CC-BY-NC-4.0"
        )
    )
    result = service.refresh_evidence(
        case["public_id"], original["public_id"], admin_public_id=ADMIN_ID
    )
    assert result["source_changed"] is True
    assert result["snapshot"]["supersedes_evidence_public_id"] == original["public_id"]

    events = service.repository.list_events(case["public_id"])
    assert any(event["event_type"] == "source_changed_detected" for event in events)


def test_refresh_evidence_reports_unchanged_when_checksum_matches(settings: Settings) -> None:
    case = _create_case(settings)
    _allow_domain(settings, case["public_id"], "huggingface.co")
    service = ExternalDatasetEvidenceService(
        settings,
        transport=_transport(
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "text/plain"}, body=b"CC-BY-4.0"
            ),
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "text/plain"}, body=b"CC-BY-4.0"
            ),
        ),
        resolver=_resolver,
    )
    original = service.collect_evidence(
        case["public_id"],
        evidence_type="licence_file",
        source_url="https://huggingface.co/datasets/example/tamil-corpus/LICENSE",
        admin_public_id=ADMIN_ID,
    )
    result = service.refresh_evidence(
        case["public_id"], original["public_id"], admin_public_id=ADMIN_ID
    )
    assert result["source_changed"] is False


# -- ExternalDatasetIdentityVerificationService --------------------------------


def test_identity_assess_verified_on_matching_official_domain(settings: Settings) -> None:
    case = _create_case(settings)
    _allow_domain(settings, case["public_id"], "huggingface.co")
    evidence_service = ExternalDatasetEvidenceService(
        settings,
        transport=_transport(
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "text/plain"}, body=b"CC-BY-4.0"
            )
        ),
        resolver=_resolver,
    )
    evidence_service.collect_evidence(
        case["public_id"],
        evidence_type="licence_file",
        source_url="https://huggingface.co/datasets/example/tamil-corpus/LICENSE",
        admin_public_id=ADMIN_ID,
    )

    identity_service = ExternalDatasetIdentityVerificationService(settings)
    result = identity_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["identity_status"] == "verified"

    updated_case = identity_service.repository.get_case(case["public_id"])
    assert updated_case["identity_status"] == "verified"


def test_identity_assess_not_verified_with_no_evidence(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"homepage_url": None, "organization": None})
    identity_service = ExternalDatasetIdentityVerificationService(settings)
    result = identity_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["identity_status"] == "not_verified"


def test_identity_assess_conflicting_when_evidence_domain_differs(settings: Settings) -> None:
    case = _create_case(
        settings, candidate_overrides={"homepage_url": "https://huggingface.co/datasets/real"}
    )
    _allow_domain(settings, case["public_id"], "some-other-official-source.org")
    evidence_service = ExternalDatasetEvidenceService(
        settings,
        transport=_transport(
            EvidenceHttpResponse(
                status_code=200, headers={"content-type": "text/plain"}, body=b"some text"
            )
        ),
        resolver=_resolver,
    )
    evidence_service.collect_evidence(
        case["public_id"],
        evidence_type="licence_file",
        source_url="https://some-other-official-source.org/licence.txt",
        admin_public_id=ADMIN_ID,
    )
    identity_service = ExternalDatasetIdentityVerificationService(settings)
    result = identity_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["identity_status"] == "conflicting"


def test_identity_title_similarity_alone_never_reaches_verified(settings: Settings) -> None:
    # Only `canonical_name` (a title-like field) matches -- no
    # `provider_dataset_id`/`official_domain` strong signal at all.
    case = _create_case(settings, candidate_overrides={"homepage_url": None, "organization": None})
    evidence_service = ExternalDatasetEvidenceService(settings)
    evidence_service.add_manual_evidence(
        case["public_id"],
        evidence_type="dataset_card",
        content_text="This dataset is called Tamil Corpus and is very useful.",
        admin_public_id=ADMIN_ID,
    )
    identity_service = ExternalDatasetIdentityVerificationService(settings)
    result = identity_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["identity_status"] != "verified"
    assert result["identity_status"] == "likely_match"


def test_record_manual_identity_signal(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"homepage_url": None, "organization": None})
    identity_service = ExternalDatasetIdentityVerificationService(settings)
    check = identity_service.record_manual_signal(
        case["public_id"],
        signal_type="upstream_citation",
        expected_value="Smith et al. 2020",
        observed_value="Smith et al. 2020",
        matched=True,
        reason="Citation confirmed against the dataset's paper",
        admin_public_id=ADMIN_ID,
    )
    assert check["matched"] is True
    updated_case = identity_service.repository.get_case(case["public_id"])
    assert updated_case["identity_status"] == "likely_match"


# -- ExternalDatasetLicenceService ----------------------------------------------


def test_licence_assess_missing_when_no_declared_or_evidence(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"declared_licence": None})
    licence_service = ExternalDatasetLicenceService(settings)
    result = licence_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["licence_status"] == "missing"
    assert result["normalized_licence_identifier"] is None


def test_licence_assess_declared_only_without_licence_evidence(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"declared_licence": "CC-BY-4.0"})
    licence_service = ExternalDatasetLicenceService(settings)
    result = licence_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["licence_status"] == "declared_only"
    assert result["normalized_licence_identifier"] == "CC-BY-4.0"


def test_licence_assess_verified_when_evidence_confirms_spdx_licence(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"declared_licence": "CC-BY-4.0"})
    evidence_service = ExternalDatasetEvidenceService(settings)
    evidence_service.add_manual_evidence(
        case["public_id"],
        evidence_type="licence_file",
        content_text="This work is licensed under CC-BY-4.0.",
        admin_public_id=ADMIN_ID,
    )
    licence_service = ExternalDatasetLicenceService(settings)
    result = licence_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["licence_status"] == "verified"


def test_licence_assess_conflicting_when_evidence_disagrees(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"declared_licence": "CC-BY-4.0"})
    evidence_service = ExternalDatasetEvidenceService(settings)
    evidence_service.add_manual_evidence(
        case["public_id"],
        evidence_type="licence_file",
        content_text="This work is licensed under CC-BY-NC-4.0, non-commercial only.",
        admin_public_id=ADMIN_ID,
    )
    licence_service = ExternalDatasetLicenceService(settings)
    result = licence_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["licence_status"] == "conflicting"


def test_licence_assess_custom_needs_review_when_no_spdx_match(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"declared_licence": "Our Custom Licence v2"})
    evidence_service = ExternalDatasetEvidenceService(settings)
    evidence_service.add_manual_evidence(
        case["public_id"],
        evidence_type="licence_file",
        content_text="This is a fully custom licence text with bespoke terms.",
        admin_public_id=ADMIN_ID,
    )
    licence_service = ExternalDatasetLicenceService(settings)
    result = licence_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    assert result["licence_status"] == "custom_needs_review"
    assert result["normalized_licence_identifier"] is None


def test_licence_service_never_overwrites_candidate_declared_licence(settings: Settings) -> None:
    case = _create_case(settings, candidate_overrides={"declared_licence": "CC-BY-4.0"})
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    licence_service = ExternalDatasetLicenceService(settings)
    licence_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    candidate = discovery.get_candidate(case["candidate_public_id"])
    assert candidate["declared_licence"] == "CC-BY-4.0"


# -- ExternalDatasetTermsService -------------------------------------------------


def test_terms_snapshot_summary_tracks_completeness(settings: Settings) -> None:
    case = _create_case(settings)
    evidence_service = ExternalDatasetEvidenceService(settings)
    terms_service = ExternalDatasetTermsService(settings)

    summary = terms_service.get_terms_snapshot_summary(case["public_id"])
    assert summary["terms_status"] == "not_started"

    evidence_service.add_manual_evidence(
        case["public_id"], evidence_type="terms_of_use", content_text="Terms",
        admin_public_id=ADMIN_ID,
    )
    summary = terms_service.get_terms_snapshot_summary(case["public_id"])
    assert summary["terms_status"] == "incomplete"

    evidence_service.add_manual_evidence(
        case["public_id"], evidence_type="privacy_policy", content_text="Privacy",
        admin_public_id=ADMIN_ID,
    )
    evidence_service.add_manual_evidence(
        case["public_id"],
        evidence_type="consent_statement",
        content_text="Consent",
        admin_public_id=ADMIN_ID,
    )
    summary = terms_service.get_terms_snapshot_summary(case["public_id"])
    assert summary["terms_status"] == "complete"
    assert len(summary["by_evidence_type"]["terms_of_use"]) == 1
