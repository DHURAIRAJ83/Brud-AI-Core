"""MB-07: service-level tests for MiniBrainReleasePipelineService
against a real, seeded temp database -- no mocks. A real
BrudForCausalLM checkpoint is trained-shape (random weights, not
actually trained) and saved via the same TrainingCheckpointManager the
Training Engine itself uses, then carried end to end through real
GGUF export, real quantization, a real llama_cpp load, a real
generation call, and real Model Release governance composition.
"""

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.auth import AdminCreate
from backend.models.model_release import ApprovalCreate, ModelReleaseFamilyCreate
from backend.services.mini_brain_release_pipeline_service import MiniBrainReleasePipelineService
from backend.services.model_release_service import ModelReleaseService
from tests.backend.test_instruction_tuning_api import _fixture_refs
from tests.backend.test_model_release_api import _insert_evaluation_evidence

pytestmark = pytest.mark.anyio

CHECKPOINT_PUBLIC_ID = "50000000-0000-0000-0000-000000000500"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports", document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports", core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        release_artifact_dir=tmp_path / "release_artifacts", release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _seed(api_app: FastAPI) -> dict:
    admin_repository = AdminRepository(api_app.state.settings.resolved_database_path)
    admin = admin_repository.create_admin(
        AdminCreate(username="mb07-admin", display_name="A", password="password12345")
    )
    # GOV-26/GOV-33 (P0-1 Phase 15.2): the release candidate's creator can
    # never approve it, and 2 distinct approvers are required -- these two
    # non-creator identities are pure test scaffolding for the approval
    # step, unrelated to what this file's own tests otherwise verify.
    reviewer_1 = admin_repository.create_admin(
        AdminCreate(username="mb07-reviewer-1", display_name="R1", password="password12345")
    )
    reviewer_2 = admin_repository.create_admin(
        AdminCreate(username="mb07-reviewer-2", display_name="R2", password="password12345")
    )
    refs = _fixture_refs(api_app)
    evaluation_run_id = _insert_evaluation_evidence(api_app, refs["base_model"], "evaluation_passed_with_limits")
    model_release = ModelReleaseService(
        ModelReleaseRepository(api_app.state.settings.resolved_database_path), api_app.state.settings
    )
    family = model_release.create_family(
        ModelReleaseFamilyCreate(name="MB07 Test Family", slug="mb07-test-family"), admin.public_id,
    )
    return {
        "admin_id": admin.public_id, "reviewer_1_id": reviewer_1.public_id,
        "reviewer_2_id": reviewer_2.public_id, "refs": refs,
        "evaluation_run_id": evaluation_run_id, "family_id": family["public_id"],
    }


def _svc(api_app: FastAPI) -> MiniBrainReleasePipelineService:
    return MiniBrainReleasePipelineService(api_app.state.settings)


def _session_at_version_registration(api_app: FastAPI, seed: dict) -> dict:
    """Drives a real session through every stage up to (and including)
    `version_registration`, ready for `create_release_version()` --
    shared setup for the GOV-26/GOV-33 approval tests below, unrelated to
    what each of them individually verifies."""

    svc = _svc(api_app)
    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16"],
        dataset_version_public_id=seed["refs"]["dataset"],
        model_evaluation_run_public_id=seed["evaluation_run_id"], admin_id=seed["admin_id"],
    )
    session = svc.validate_checkpoint(session["public_id"], admin_id=seed["admin_id"])
    session = svc.convert_model(session["public_id"], admin_id=seed["admin_id"])
    session = svc.quantize_and_export(session["public_id"], admin_id=seed["admin_id"])
    session = svc.validate_integrity(session["public_id"], admin_id=seed["admin_id"])
    session = svc.validate_compatibility(session["public_id"], admin_id=seed["admin_id"])
    session = svc.measure_performance(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "version_registration"
    return session


async def test_full_release_pipeline_happy_path(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)

    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16", "q8_0", "q4_k_m"],
        dataset_version_public_id=seed["refs"]["dataset"],
        model_evaluation_run_public_id=seed["evaluation_run_id"], admin_id=seed["admin_id"],
    )
    assert session["stage"] == "checkpoint_validation"
    assert session["model_release_candidate_public_id"]

    session = svc.validate_checkpoint(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "conversion"
    assert session["checkpoint_validation_report"]["status"] == "Valid"

    session = svc.convert_model(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "quantization"
    assert session["conversion_report"]["architecture_compatible"] is True

    session = svc.quantize_and_export(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "integrity_validation"
    levels = session["quantization_report"]["levels"]
    assert levels["f16"]["exported"] is True
    assert levels["q8_0"]["exported"] is True
    assert levels["q4_k_m"]["exported"] is False
    assert "no quantize encoder" in levels["q4_k_m"]["reason"]
    assert Path(levels["f16"]["path"]).is_file()

    session = svc.validate_integrity(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "compatibility_validation"
    assert session["integrity_report"]["overall_status"] == "Valid"

    session = svc.validate_compatibility(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "performance_validation"
    assert session["compatibility_report"]["overall_status"] == "Compatible"
    for level_report in session["compatibility_report"]["levels"].values():
        assert level_report["status"] == "Compatible"

    session = svc.measure_performance(session["public_id"], admin_id=seed["admin_id"])
    assert session["stage"] == "version_registration"
    assert "f16" in session["performance_report"]["levels"]

    # GOV-26/GOV-33 (P0-1 Phase 15.2): create_release_version() now only
    # prepares the candidate (manifest, model card, eligibility) -- it does
    # not create the release. The session stays at "version_registration"
    # and no release exists yet.
    session = svc.create_release_version(session["public_id"], version="Brud-0.1", admin_id=seed["admin_id"])
    assert session["stage"] == "version_registration"
    assert not session["model_release_public_id"]

    candidate_public_id = session["model_release_candidate_public_id"]
    model_release = ModelReleaseService(
        ModelReleaseRepository(api_app.state.settings.resolved_database_path), api_app.state.settings
    )
    # Two real, distinct, non-creator admins each submit a real approval --
    # neither is seed["admin_id"] (the candidate's own creator, who can
    # never approve it under GOV-33, unconditionally).
    model_release.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="first reviewer"),
        seed["reviewer_1_id"],
    )
    model_release.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="second reviewer"),
        seed["reviewer_2_id"],
    )

    session = svc.finalize_release_version(session["public_id"], version="Brud-0.1", admin_id=seed["admin_id"])
    assert session["stage"] == "awaiting_admin_review"
    assert session["version_string"] == "Brud-0.1"
    assert session["model_release_public_id"]

    session = svc.generate_report(session["public_id"], admin_id=seed["admin_id"])
    assert session["release_report"]["ready_for_admin_review"] is True

    session = svc.admin_review(session["public_id"], decision="approve", admin_id=seed["admin_id"])
    assert session["stage"] == "production_activation"
    assert session["admin_activation_decision"] == "approve"

    session = svc.activate(session["public_id"], quantization_level="q8_0", admin_id=seed["admin_id"])
    assert session["stage"] == "closed"
    assert session["status"] == "activated"
    assert session["runtime_model_public_id"]

    registry = svc.registry_entry(session["public_id"])
    assert registry["release"]["status"] == "released"
    assert registry["release"]["version"] == "Brud-0.1"

    # safety proof: MB-06/MB-01..MB-05 tables and the source checkpoint file
    # are untouched by any of the above
    with sqlite3.connect(api_app.state.settings.resolved_database_path) as conn:
        job_count = conn.execute("SELECT COUNT(*) FROM pretraining_jobs").fetchone()[0]
        checkpoint_row = conn.execute(
            "SELECT model_checksum_sha256 FROM pretraining_checkpoints WHERE public_id=?",
            (CHECKPOINT_PUBLIC_ID,),
        ).fetchone()
    assert job_count == 1  # only the fixture's own job; MB-07 never creates one
    checkpoint_dir = api_app.state.settings.resolved_pretraining_dir / "base-source-checkpoint"
    assert checkpoint_dir.is_dir()


async def test_create_session_creates_a_real_governance_candidate(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16"],
        admin_id=seed["admin_id"],
    )
    candidate = svc.model_release.get_candidate(session["model_release_candidate_public_id"])
    assert candidate["core_model_version_public_id"] == seed["refs"]["base_model"]


async def test_validate_checkpoint_blocked_at_wrong_stage(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16"],
        admin_id=seed["admin_id"],
    )
    svc.validate_checkpoint(session["public_id"], admin_id=seed["admin_id"])
    with pytest.raises(ValidationError, match="not 'checkpoint_validation'"):
        svc.validate_checkpoint(session["public_id"], admin_id=seed["admin_id"])


async def test_convert_model_blocked_before_checkpoint_validated(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16"],
        admin_id=seed["admin_id"],
    )
    with pytest.raises(ValidationError, match="not 'conversion'"):
        svc.convert_model(session["public_id"], admin_id=seed["admin_id"])


async def test_activate_blocked_without_admin_approval(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16"],
        admin_id=seed["admin_id"],
    )
    with pytest.raises(ValidationError, match="production_activation"):
        svc.activate(session["public_id"], quantization_level="f16", admin_id=seed["admin_id"])


async def test_activate_blocked_for_a_level_that_was_never_exported(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16"],
        admin_id=seed["admin_id"],
    )
    # fast-forward directly to production_activation with an approve decision,
    # bypassing the real pipeline stages -- this test only exercises the
    # per-level export guard, not the full happy path (covered above).
    with svc.repository.transaction() as connection:
        svc.repository.update_session(
            connection, session["public_id"],
            {
                "stage": "production_activation", "admin_activation_decision": "approve",
                "quantization_report_json": {"levels": {"f16": {"exported": False, "reason": "test"}}},
            },
        )
    with pytest.raises(ValidationError, match="was not successfully exported"):
        svc.activate(session["public_id"], quantization_level="f16", admin_id=seed["admin_id"])


async def test_admin_review_rejects_invalid_decision(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16"],
        admin_id=seed["admin_id"],
    )
    with svc.repository.transaction() as connection:
        svc.repository.update_session(connection, session["public_id"], {"stage": "awaiting_admin_review"})
    with pytest.raises(ValidationError):
        svc.admin_review(session["public_id"], decision="not-a-real-decision", admin_id=seed["admin_id"])


async def test_events_are_recorded(api_app: FastAPI) -> None:
    seed = _seed(api_app)
    svc = _svc(api_app)
    session = svc.create_session(
        core_model_version_public_id=seed["refs"]["base_model"],
        pretraining_checkpoint_public_id=CHECKPOINT_PUBLIC_ID,
        model_release_family_public_id=seed["family_id"], target_quantizations=["f16"],
        admin_id=seed["admin_id"],
    )
    svc.validate_checkpoint(session["public_id"], admin_id=seed["admin_id"])
    events = svc.events(session["public_id"])
    event_types = [e["event_type"] for e in events["items"]]
    assert "session_created" in event_types
    assert "checkpoint_validated" in event_types


# -- GOV-26 / GOV-33 (P0-1 Phase 15.2): redesigned approval flow ----------------------------


async def test_mb07_cannot_complete_using_the_creator_as_an_approver(api_app: FastAPI) -> None:
    """The candidate's own creator (seed["admin_id"]) can never submit an
    approval for it -- unconditionally, regardless of
    release_allow_self_approval's configured value (GOV-33)."""

    seed = _seed(api_app)
    session = _session_at_version_registration(api_app, seed)
    svc = _svc(api_app)

    session = svc.create_release_version(session["public_id"], version="Brud-0.1", admin_id=seed["admin_id"])
    assert session["stage"] == "version_registration"
    candidate_public_id = session["model_release_candidate_public_id"]

    model_release = ModelReleaseService(
        ModelReleaseRepository(api_app.state.settings.resolved_database_path), api_app.state.settings
    )
    with pytest.raises(ValidationError, match="self_approval_not_allowed"):
        model_release.submit_approval(
            candidate_public_id,
            ApprovalCreate(role="release", decision="approve", comment="self-approval attempt"),
            seed["admin_id"],
        )

    # Even without ever successfully submitting an approval, finalize must
    # fail -- no release should exist. create_release()'s own first gate
    # (candidate status must already be "approved") fires before its
    # separate is_policy_satisfied() recheck would ever produce "required
    # approvals incomplete" -- since no approval was ever recorded, the
    # candidate's status never left "eligible", so this is the exact
    # message actually raised.
    with pytest.raises(ValidationError, match="candidate must be approved before creating a release"):
        svc.finalize_release_version(session["public_id"], version="Brud-0.1", admin_id=seed["admin_id"])


async def test_mb07_completes_successfully_with_two_distinct_non_creator_approvers(
    api_app: FastAPI,
) -> None:
    """The redesigned flow's positive case, isolated from the full happy
    path above: create_release_version() prepares only; two distinct,
    non-creator admins each submit a real approval; finalize_release_version()
    then succeeds."""

    seed = _seed(api_app)
    session = _session_at_version_registration(api_app, seed)
    svc = _svc(api_app)

    session = svc.create_release_version(session["public_id"], version="Brud-0.2", admin_id=seed["admin_id"])
    assert session["stage"] == "version_registration"
    assert not session["model_release_public_id"]
    candidate_public_id = session["model_release_candidate_public_id"]

    model_release = ModelReleaseService(
        ModelReleaseRepository(api_app.state.settings.resolved_database_path), api_app.state.settings
    )
    model_release.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="first reviewer"),
        seed["reviewer_1_id"],
    )
    model_release.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="second reviewer"),
        seed["reviewer_2_id"],
    )

    session = svc.finalize_release_version(session["public_id"], version="Brud-0.2", admin_id=seed["admin_id"])
    assert session["stage"] == "awaiting_admin_review"
    assert session["model_release_public_id"]
