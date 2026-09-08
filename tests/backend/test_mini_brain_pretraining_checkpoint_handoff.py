"""Phase 2.7F: MB-22 checkpoint -> governed pretraining_checkpoints
registration -> evaluation discovery -> release resolution.

Proves the specific gap Phase 2.7E's own report documented: an MB-22
checkpoint had real identity but no row in `pretraining_checkpoints`, so
`ModelReleaseService._resolve_checkpoint()` could never find it. This
file drives the real chain end to end through the new
`MiniBrainPretrainingHandoffService.register_checkpoint()` (backed by
`PretrainingService.register_external_checkpoint()`), then proves the
*existing*, unmodified `PretrainingService`/`ModelReleaseService` can
now discover and resolve it -- never releasing or activating anything.

Reuses every real fixture-building helper already established
(`_create_admin`, `_seed_approved_package_and_release`,
`_real_core_model_version`, `_real_dataset_version`) -- never a
parallel fixture system.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.models.model_release import ModelReleaseCandidateCreate, ModelReleaseFamilyCreate
from backend.services.core_model_service import CoreModelService
from backend.services.mini_brain_pretraining_handoff_service import MiniBrainPretrainingHandoffService
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
from backend.services.model_release_service import ModelReleaseService
from backend.services.pretraining_service import PretrainingService
from backend.services.training_runtime_adapter import TorchTrainingAdapter
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
from tests.backend.test_mini_brain_training_engine_service import (
    _create_admin,
    _seed_approved_package_and_release,
)
from tests.backend.test_torch_training_adapter_integration import (
    _real_core_model_version,
    _real_dataset_version,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _tiny_train_blocks(count: int = 4, length: int = 12, seed: int = 0) -> list[list[int]]:
    import random

    rng = random.Random(seed)
    return [[rng.randint(4, 100) for _ in range(length)] for _ in range(count)]


def _stage_version(settings: Settings, version_public_id: str, admin_id: str) -> None:
    """Promotes an already architecture_verified real Core Model Version
    through smoke_test() -> stage() -- the exact real backend chain Phase
    2.7D's own report proved end to end -- so it satisfies
    `ModelReleaseService`'s own `ELIGIBLE_LIFECYCLE_STATUSES = {"staging",
    "active"}` gate for release-candidate creation."""

    core_models = CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)
    core_models.smoke_test(version_public_id, admin_id=admin_id)
    core_models.stage(version_public_id, admin_id=admin_id)


async def _drive_gpu_job_to_registered_checkpoint(
    api_app: FastAPI, *, admin_id: str, tp_id: str, rg_id: str,
    core_model_version_public_id: str, dataset_version_public_id: str, topic: str,
) -> tuple[str, str, dict]:
    """Drives one real MB-22 job from creation through a real, saved
    checkpoint, then registers it -- returns (job_id, checkpoint_id,
    registration_result)."""

    adapter = TorchTrainingAdapter()
    svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
    job = svc.create_job(
        topic=topic, training_package_session_public_id=tp_id, release_governance_session_public_id=rg_id,
        execution_mode="gpu", admin_id=admin_id, core_model_version_public_id=core_model_version_public_id,
        dataset_version_public_id=dataset_version_public_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.7f handoff test", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(
        job_id, admin_id=admin_id, train_blocks=_tiny_train_blocks(),
        validation_blocks=_tiny_train_blocks(seed=1), configuration_label="TEST_INTEGRATION_CONFIGURATION",
    )
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    checkpoint_id = svc.list_checkpoints(job_id)["items"][0]["public_id"]

    handoff = MiniBrainPretrainingHandoffService(api_app.state.settings)
    result = handoff.register_checkpoint(job_id, checkpoint_id, admin_id)
    return job_id, checkpoint_id, result


class TestRealEndToEndHandoff:
    """Part 13: the full real, isolated chain -- Core Model Version ->
    MB-22 gpu training -> real checkpoint -> registration -> evaluation
    discovery -> release-checkpoint resolution. Never releases or
    activates anything."""

    async def test_full_handoff_chain(self, api_app: FastAPI, tmp_path: Path) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="handoff-pkg")
        core_model_version_public_id = _real_core_model_version(settings, admin_id, name_suffix="handoff")
        _stage_version(settings, core_model_version_public_id, admin_id)
        dataset_version_public_id = _real_dataset_version(settings, name_suffix="handoff")

        job_id, checkpoint_id, result = await _drive_gpu_job_to_registered_checkpoint(
            api_app, admin_id=admin_id, tp_id=tp_id, rg_id=rg_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id, topic="handoff-job",
        )

        # -- A/B/C/D: real loss/weights/checkpoint, checkpoint verification --
        pretraining_job_public_id = result["pretraining_job_public_id"]
        pretraining_checkpoint_public_id = result["pretraining_checkpoint_public_id"]
        with database_connection(settings.resolved_database_path) as connection:
            checkpoint_row = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?",
                (pretraining_checkpoint_public_id,),
            ).fetchone()
            job_row = connection.execute(
                "SELECT * FROM pretraining_jobs WHERE public_id=?", (pretraining_job_public_id,),
            ).fetchone()
            core_model_version_row = connection.execute(
                "SELECT id FROM core_model_versions WHERE public_id=?", (core_model_version_public_id,),
            ).fetchone()
            tokenizer_row = connection.execute(
                "SELECT public_id FROM tokenizer_versions WHERE id=?", (job_row["tokenizer_version_id"],),
            ).fetchone()
            dataset_row = connection.execute(
                "SELECT public_id FROM dataset_versions WHERE id=?", (job_row["dataset_version_id"],),
            ).fetchone()

        # -- H: pretraining_checkpoints row exists, real, verified --
        assert checkpoint_row is not None
        assert checkpoint_row["status"] == "verified"
        assert checkpoint_row["checkpoint_kind"] == "final"

        # -- E: correct Core Model Version --
        assert checkpoint_row["core_model_version_id"] == core_model_version_row["id"]
        assert job_row["core_model_version_id"] == core_model_version_row["id"]

        # -- F: correct tokenizer (the version's own, not a mismatched one) --
        with database_connection(settings.resolved_database_path) as connection:
            expected_tokenizer = connection.execute(
                "SELECT t.public_id FROM tokenizer_versions t JOIN core_model_versions v ON v.tokenizer_version_id=t.id WHERE v.id=?",
                (core_model_version_row["id"],),
            ).fetchone()["public_id"]
        assert tokenizer_row["public_id"] == expected_tokenizer

        # -- G: correct (real, non-fabricated) dataset identity --
        assert dataset_row["public_id"] == dataset_version_public_id

        # -- D again: real file-level verification through the exact class
        # InferenceRuntimeService itself uses --
        checkpoint_dir = settings.resolved_pretraining_dir / checkpoint_row["safe_name"]
        manager = TrainingCheckpointManager(settings.resolved_pretraining_dir, settings.core_checkpoint_max_bytes)
        assert manager.verify(checkpoint_dir) is True
        assert (checkpoint_dir / "model_state.pt").is_file()

        # -- job never entered the worker-claimable state machine --
        assert job_row["status"] == "completed"
        assert job_row["worker_id"] is None
        assert job_row["lease_generation"] == 0

        # -- I: evaluation can discover the checkpoint through the existing,
        # unmodified PretrainingService.evaluate() (job-scoped) --
        pretraining = PretrainingService(PretrainingRepository(settings.resolved_database_path), settings)
        evaluation = pretraining.evaluate(pretraining_job_public_id, admin_id=admin_id)
        assert evaluation["status"] == "completed"
        assert evaluation["evaluation_type"] == "validation_loss"
        listed_checkpoints = pretraining.checkpoints(pretraining_job_public_id)["items"]
        assert any(c["public_id"] == pretraining_checkpoint_public_id for c in listed_checkpoints)
        verify_result = pretraining.verify_checkpoint(pretraining_checkpoint_public_id, admin_id=admin_id)
        assert verify_result["verified"] is True

        # -- J: ModelReleaseService can resolve the checkpoint -- proving
        # only that it CAN be found, never releasing or activating it. --
        release_service = ModelReleaseService(ModelReleaseRepository(settings.resolved_database_path), settings)
        family = release_service.create_family(
            ModelReleaseFamilyCreate(name="Handoff Family", slug="handoff-family"), admin_id,
        )
        candidate = release_service.create_candidate(
            ModelReleaseCandidateCreate(
                model_release_family_public_id=family["public_id"],
                core_model_version_public_id=core_model_version_public_id,
            ),
            admin_id,
        )
        assert candidate["public_id"]

        # -- K/L/M: no automatic release, activation, or Public Chat
        # assignment anywhere in this test. --
        with database_connection(settings.resolved_database_path) as connection:
            release_count = connection.execute("SELECT COUNT(*) c FROM model_releases").fetchone()["c"]
            assignment_count = connection.execute(
                "SELECT COUNT(*) c FROM inference_model_assignments"
            ).fetchone()["c"]
        assert release_count == 0
        assert assignment_count == 0

        # -- 12 (Part 14): attempt to release before approval/evaluation is
        # rejected by the existing, unmodified release gate -- not weakened,
        # not bypassed. --
        from backend.models.model_release import ModelReleaseCreate

        with pytest.raises(ValidationError, match="candidate must be approved"):
            release_service.create_release(
                ModelReleaseCreate(candidate_public_id=candidate["public_id"], version="0.1.0-handoff"),
                admin_id,
            )


class TestNegativeChecks:
    """Part 14: every rejection must be typed and safe -- no silent
    fallback, no DB corruption."""

    async def test_1_simulation_job_checkpoint_is_rejected_missing_identity(
        self, api_app: FastAPI,
    ) -> None:
        """A simulation-mode job's checkpoint has no Core Model Version or
        dataset identity at all (and is metadata-only, never a real
        checkpoint) -- registration must reject it, never silently
        register with NULL/fake identity."""

        admin_id = _create_admin(api_app)
        settings = api_app.state.settings
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="sim-pkg")
        svc = MiniBrainTrainingEngineService(settings)
        job = svc.create_job(
            topic="sim job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="simulation", admin_id=admin_id,
        )
        job_id = job["public_id"]
        assert job["core_model_version_public_id"] is None
        svc.run_validate_release_stage(job_id, admin_id=admin_id)
        svc.run_validate_package_stage(job_id, admin_id=admin_id)
        svc.run_validate_authorization_stage(job_id, authorization_reason="sim test", admin_id=admin_id)
        svc.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc.run_build_manifest_stage(job_id, admin_id=admin_id)
        svc.run_reserve_runtime_stage(job_id, admin_id=admin_id)
        svc.run_start_training_stage(job_id, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_id = svc.list_checkpoints(job_id)["items"][0]["public_id"]

        handoff = MiniBrainPretrainingHandoffService(settings)
        with pytest.raises(ValidationError, match="only a real"):
            handoff.register_checkpoint(job_id, checkpoint_id, admin_id)

    async def test_2_wrong_core_model_version_cross_check_is_rejected(self, api_app: FastAPI) -> None:
        """`register_external_checkpoint()`'s own defensive cross-check:
        an `existing_pretraining_job_public_id` whose Core Model Version
        does not match the checkpoint's must be rejected -- this can only
        be reached by calling the lower-level service directly (the
        handoff service itself can never produce this mismatch through
        its own normal flow), so it is tested at that level."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        first_id = _real_core_model_version(settings, admin_id, name_suffix="x2a")
        second_id = _real_core_model_version(
            settings, admin_id, name_suffix="x2b", hidden_size=32, intermediate_size=64,
        )
        dataset_id = _real_dataset_version(settings, name_suffix="x2")
        pretraining = PretrainingService(PretrainingRepository(settings.resolved_database_path), settings)

        # A real pretraining_jobs row that genuinely belongs to `first_id`.
        from core_model.architecture.model import BrudForCausalLM, count_parameters
        from core_model.training.pretraining_config import PretrainingConfig

        model_config, _ = CoreModelService(
            CoreModelRepository(settings.resolved_database_path), settings
        ).model_config_for_version(first_id)
        import torch

        torch.manual_seed(0)
        model = BrudForCausalLM(model_config)
        count_parameters(model)
        target = settings.resolved_pretraining_dir / "x2-checkpoint"
        manager = TrainingCheckpointManager(settings.resolved_pretraining_dir, settings.core_checkpoint_max_bytes)
        opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda _: 1.0)
        manager.save(
            target, model=model, optimizer=opt, scheduler=sched, optimizer_state=None,
            scheduler_state=None, rng_state=None,
            trainer_state={"step": 1, "processed_tokens": 0, "block_index": 0, "status": "completed"},
            config=model_config.to_dict(), references={"source": "x2-negative-test"},
        )
        first = pretraining.register_external_checkpoint(
            core_model_version_public_id=first_id, dataset_version_public_id=dataset_id,
            checkpoint_directory=target, step=1, processed_tokens=0, training_loss=1.0,
            validation_loss=None, configuration=PretrainingConfig(total_steps=1).to_dict(),
            source_label="x2-first", admin_id=admin_id,
        )

        target2 = settings.resolved_pretraining_dir / "x2-checkpoint-2"
        manager.save(
            target2, model=model, optimizer=opt, scheduler=sched, optimizer_state=None,
            scheduler_state=None, rng_state=None,
            trainer_state={"step": 2, "processed_tokens": 0, "block_index": 0, "status": "completed"},
            config=model_config.to_dict(), references={"source": "x2-negative-test-2"},
        )
        with pytest.raises(ValidationError, match="does not match the existing pretraining job"):
            pretraining.register_external_checkpoint(
                core_model_version_public_id=second_id, dataset_version_public_id=dataset_id,
                checkpoint_directory=target2, step=2, processed_tokens=0, training_loss=1.0,
                validation_loss=None, configuration=PretrainingConfig(total_steps=2).to_dict(),
                source_label="x2-second", admin_id=admin_id,
                existing_pretraining_job_public_id=first["pretraining_job_public_id"],
            )

    async def test_3_missing_checkpoint_is_rejected(self, api_app: FastAPI) -> None:
        admin_id = _create_admin(api_app)
        settings = api_app.state.settings
        svc = MiniBrainTrainingEngineService(settings)
        handoff = MiniBrainPretrainingHandoffService(settings)
        job = svc.create_job(
            topic="no-checkpoint job", training_package_session_public_id="pkg-y",
            release_governance_session_public_id="rel-y", execution_mode="simulation", admin_id=admin_id,
        )
        with pytest.raises(Exception):  # NotFoundError from the repository -- checkpoint truly does not exist
            handoff.register_checkpoint(job["public_id"], "00000000-0000-0000-0000-000000012345", admin_id)

    async def test_4_corrupted_checkpoint_is_rejected(self, api_app: FastAPI, tmp_path: Path) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="corrupt-pkg")
        core_model_version_public_id = _real_core_model_version(settings, admin_id, name_suffix="corrupt")
        dataset_version_public_id = _real_dataset_version(settings, name_suffix="corrupt")

        adapter = TorchTrainingAdapter()
        svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
        job = svc.create_job(
            topic="corrupt-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id,
        )
        job_id = job["public_id"]
        svc.run_validate_release_stage(job_id, admin_id=admin_id)
        svc.run_validate_package_stage(job_id, admin_id=admin_id)
        svc.run_validate_authorization_stage(job_id, authorization_reason="corrupt test", admin_id=admin_id)
        svc.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc.run_build_manifest_stage(job_id, admin_id=admin_id)
        svc.run_reserve_runtime_stage(
            job_id, admin_id=admin_id, train_blocks=_tiny_train_blocks(),
            validation_blocks=_tiny_train_blocks(seed=1), configuration_label="TEST_INTEGRATION_CONFIGURATION",
        )
        svc.run_start_training_stage(job_id, admin_id=admin_id)
        svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_id = svc.list_checkpoints(job_id)["items"][0]["public_id"]

        real_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        (real_dir / "model_state.pt").write_bytes(b"corrupted-not-a-real-tensor-file")

        handoff = MiniBrainPretrainingHandoffService(settings)
        with pytest.raises(ValidationError, match="failed verification"):
            handoff.register_checkpoint(job_id, checkpoint_id, admin_id)

        with database_connection(settings.resolved_database_path) as connection:
            count = connection.execute("SELECT COUNT(*) c FROM pretraining_checkpoints").fetchone()["c"]
            job_count = connection.execute("SELECT COUNT(*) c FROM pretraining_jobs").fetchone()["c"]
        assert count == 0, "a corrupted checkpoint must never be registered"
        assert job_count == 0, "no orphan pretraining_jobs row from a failed registration"

    async def test_8_gpu_job_creation_rejects_a_not_ready_dataset(self, api_app: FastAPI) -> None:
        admin_id = _create_admin(api_app)
        settings = api_app.state.settings
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="baddataset-pkg")
        core_model_version_public_id = _real_core_model_version(settings, admin_id, name_suffix="baddataset")
        draft_dataset_id = _real_dataset_version(settings, name_suffix="baddataset", status="draft")
        svc = MiniBrainTrainingEngineService(settings)
        with pytest.raises(ValidationError, match="dataset version must be ready or archived"):
            svc.create_job(
                topic="bad dataset job", training_package_session_public_id=tp_id,
                release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
                core_model_version_public_id=core_model_version_public_id,
                dataset_version_public_id=draft_dataset_id,
            )

    async def test_9_duplicate_checkpoint_registration_is_rejected(
        self, api_app: FastAPI, tmp_path: Path,
    ) -> None:
        admin_id = _create_admin(api_app)
        settings = api_app.state.settings
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="dup-pkg")
        core_model_version_public_id = _real_core_model_version(settings, admin_id, name_suffix="dup")
        dataset_version_public_id = _real_dataset_version(settings, name_suffix="dup")
        job_id, checkpoint_id, _result = await _drive_gpu_job_to_registered_checkpoint(
            api_app, admin_id=admin_id, tp_id=tp_id, rg_id=rg_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id, topic="dup-job",
        )
        handoff = MiniBrainPretrainingHandoffService(settings)
        with pytest.raises(ValidationError, match="already been registered"):
            handoff.register_checkpoint(job_id, checkpoint_id, admin_id)

    async def test_10_metadata_only_checkpoint_is_never_registered(
        self, api_app: FastAPI, tmp_path: Path,
    ) -> None:
        """Defense-in-depth: today's two execution modes make
        `execution_mode='gpu' and is_metadata_only=True` structurally
        unreachable through the real adapters (`TorchTrainingAdapter`
        never produces a metadata-only checkpoint; `SimulationTrainingAdapter`
        never runs under `execution_mode='gpu'`) -- `test_1` above already
        covers the reachable simulation-checkpoint rejection. This proves
        the `is_metadata_only` check itself is real and independently
        enforced, in case a future adapter or manual correction ever
        produces that combination -- the one column on the row is flipped
        directly (a test-only construction, not a reachable production
        path) to isolate exactly this check from the execution_mode one."""

        admin_id = _create_admin(api_app)
        settings = api_app.state.settings
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="metaonly-pkg")
        core_model_version_public_id = _real_core_model_version(settings, admin_id, name_suffix="metaonly")
        dataset_version_public_id = _real_dataset_version(settings, name_suffix="metaonly")

        # Built directly (not via `_drive_gpu_job_to_registered_checkpoint`,
        # which also registers) so the checkpoint can be flipped to
        # metadata-only before registration is ever attempted.
        adapter = TorchTrainingAdapter()
        svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
        job = svc.create_job(
            topic="metaonly-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id,
        )
        job_id = job["public_id"]
        svc.run_validate_release_stage(job_id, admin_id=admin_id)
        svc.run_validate_package_stage(job_id, admin_id=admin_id)
        svc.run_validate_authorization_stage(job_id, authorization_reason="metaonly test", admin_id=admin_id)
        svc.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc.run_build_manifest_stage(job_id, admin_id=admin_id)
        svc.run_reserve_runtime_stage(
            job_id, admin_id=admin_id, train_blocks=_tiny_train_blocks(),
            validation_blocks=_tiny_train_blocks(seed=1), configuration_label="TEST_INTEGRATION_CONFIGURATION",
        )
        svc.run_start_training_stage(job_id, admin_id=admin_id)
        svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_id = svc.list_checkpoints(job_id)["items"][0]["public_id"]

        with database_connection(settings.resolved_database_path) as connection:
            connection.execute(
                "UPDATE mini_brain_training_checkpoints SET is_metadata_only=1 WHERE public_id=?",
                (checkpoint_id,),
            )
            connection.commit()

        handoff = MiniBrainPretrainingHandoffService(settings)
        with pytest.raises(ValidationError, match="metadata-only"):
            handoff.register_checkpoint(job_id, checkpoint_id, admin_id)

    async def test_11_release_candidate_lookup_fails_for_the_wrong_core_model_version(
        self, api_app: FastAPI,
    ) -> None:
        """A checkpoint registered under Core Model Version A must never
        resolve when a release candidate is requested for a different,
        real, staged Core Model Version B -- `ModelReleaseService.
        _resolve_checkpoint()`'s own real gate, unmodified, doing its job."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="wrongver-pkg")
        registered_id = _real_core_model_version(settings, admin_id, name_suffix="wrongver-a")
        _stage_version(settings, registered_id, admin_id)
        other_id = _real_core_model_version(
            settings, admin_id, name_suffix="wrongver-b", hidden_size=32, intermediate_size=64,
        )
        _stage_version(settings, other_id, admin_id)
        dataset_version_public_id = _real_dataset_version(settings, name_suffix="wrongver")

        await _drive_gpu_job_to_registered_checkpoint(
            api_app, admin_id=admin_id, tp_id=tp_id, rg_id=rg_id,
            core_model_version_public_id=registered_id,
            dataset_version_public_id=dataset_version_public_id, topic="wrongver-job",
        )

        release_service = ModelReleaseService(ModelReleaseRepository(settings.resolved_database_path), settings)
        family = release_service.create_family(
            ModelReleaseFamilyCreate(name="Wrongver Family", slug="wrongver-family"), admin_id,
        )
        with pytest.raises(ValidationError, match="no verified checkpoint is available"):
            release_service.create_candidate(
                ModelReleaseCandidateCreate(
                    model_release_family_public_id=family["public_id"],
                    core_model_version_public_id=other_id,
                ),
                admin_id,
            )


class TestRestartSurvival:
    """Part 15: the entire training -> checkpoint -> registration
    sequence, verified by a genuinely separate OS process -- no shared
    interpreter, no shared import state, no process-local cache."""

    async def test_registration_survives_a_genuinely_separate_process(
        self, api_app: FastAPI, tmp_path: Path,
    ) -> None:
        import json
        import subprocess
        import sys

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="restart-handoff-pkg")
        core_model_version_public_id = _real_core_model_version(settings, admin_id, name_suffix="restarth")
        dataset_version_public_id = _real_dataset_version(settings, name_suffix="restarth")

        _job_id, _checkpoint_id, result = await _drive_gpu_job_to_registered_checkpoint(
            api_app, admin_id=admin_id, tp_id=tp_id, rg_id=rg_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id, topic="restart-handoff-job",
        )

        repo_root = str(Path(__file__).resolve().parents[2])
        probe = f"""
import json, sys
sys.path.insert(0, {repo_root!r})
from pathlib import Path
from backend.core.config import Settings
from backend.database.connection import database_connection
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

tmp_path = Path({str(tmp_path)!r})
settings = Settings(
    database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
    allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
    document_report_dir=tmp_path / "documents" / "reports",
    pretraining_dir=tmp_path / "core_models" / "pretraining",
    allow_external_storage=True, log_level="CRITICAL",
)
with database_connection(settings.resolved_database_path) as connection:
    checkpoint = connection.execute(
        "SELECT * FROM pretraining_checkpoints WHERE public_id=?", ({result["pretraining_checkpoint_public_id"]!r},)
    ).fetchone()
    job = connection.execute(
        "SELECT * FROM pretraining_jobs WHERE public_id=?", ({result["pretraining_job_public_id"]!r},)
    ).fetchone()
    core_model_version = connection.execute(
        "SELECT public_id FROM core_model_versions WHERE id=?", (checkpoint["core_model_version_id"],)
    ).fetchone()

manager = TrainingCheckpointManager(settings.resolved_pretraining_dir, settings.core_checkpoint_max_bytes)
checkpoint_dir = settings.resolved_pretraining_dir / checkpoint["safe_name"]
verified = manager.verify(checkpoint_dir)

print(json.dumps({{
    "checkpoint_status": checkpoint["status"],
    "job_status": job["status"],
    "core_model_version_public_id": core_model_version["public_id"],
    "verified": verified,
    "combined_checksum_sha256": checkpoint["combined_checksum_sha256"],
}}))
"""
        proc = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        probe_result = json.loads(proc.stdout.strip().splitlines()[-1])

        assert probe_result["checkpoint_status"] == "verified"
        assert probe_result["job_status"] == "completed"
        assert probe_result["core_model_version_public_id"] == core_model_version_public_id
        assert probe_result["verified"] is True
        assert probe_result["combined_checksum_sha256"] == result["combined_checksum_sha256"]
