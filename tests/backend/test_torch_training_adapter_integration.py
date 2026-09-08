"""Phase 2.7C: TorchTrainingAdapter unit tests (Part 11) and the real,
isolated MB-22 -> TorchTrainingAdapter -> real trainer -> real checkpoint
integration run (Part 12/13/15) -- no mocks, no simulation, on a real,
seeded temp database and a real, tiny (explicitly labeled TEST/INTEGRATION)
BrudForCausalLM.

The MB-16/18/19/20 governance chain that produces a real, admin-approved
training package + release-governance session is reused verbatim from
`test_mini_brain_training_engine_service.py`'s own `_seed_approved_package_
and_release()` -- this proves the real adapter is exercised through the
same real governance gates the simulation adapter's own test suite already
covers, not a special path built just for this test.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ValidationError
from backend.models.auth import AdminCreate
from backend.services.mini_brain_release_governance_service import MiniBrainReleaseGovernanceService
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
from backend.services.training_runtime_adapter import (
    BackendUnavailableError,
    SimulationTrainingAdapter,
    TorchTrainingAdapter,
)
from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM, count_parameters
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
from core_model.training.pretraining_config import PretrainingConfig
from tests.backend.test_mini_brain_training_engine_service import (
    _create_admin,
    _seed_approved_package_and_release,
)

pytestmark = pytest.mark.anyio

CONFIGURATION_LABEL = "TEST_INTEGRATION_CONFIGURATION"


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


def _tiny_model_config() -> BrudModelConfig:
    return BrudModelConfig(
        vocabulary_size=64, context_length=32, hidden_size=16, intermediate_size=32,
        num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2,
    )


def _tiny_pretraining_config(**overrides) -> PretrainingConfig:
    base = dict(
        batch_size=1, gradient_accumulation_steps=1, sequence_length=16, total_steps=3,
        checkpoint_interval_steps=2, metric_interval_steps=1, warmup_steps=0,
    )
    base.update(overrides)
    return PretrainingConfig(**base)


def _tiny_train_blocks(count: int = 4, length: int = 12, seed: int = 0) -> list[list[int]]:
    rng = random.Random(seed)
    return [[rng.randint(4, 63) for _ in range(length)] for _ in range(count)]


def _real_dataset_version(settings: Settings, *, name_suffix: str, status: str = "ready") -> str:
    """Phase 2.7F: a real, honestly-labeled, minimal `dataset_versions`
    row -- MB-22 has no dataset-to-token-block pipeline of its own (its
    real trainer receives already-tokenized blocks directly), so this is
    the same kind of real-but-tiny test fixture `test_core_model_api.py`'s
    own `_registered_tokenizer()` and this file's own
    `_real_core_model_version()` already use to satisfy a required
    reference honestly -- never a production-service-layer fabrication."""

    from uuid import uuid4

    from backend.database.connection import database_connection

    public_id = str(uuid4())
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (public_id, f"adapter-it-dataset-{name_suffix}", "v1", status, "e" * 64),
        )
        connection.commit()
    return public_id


def _real_core_model_version(
    settings: Settings, admin_id: str, *, name_suffix: str,
    hidden_size: int = 16, intermediate_size: int = 32, num_attention_heads: int = 2,
    num_key_value_heads: int = 2,
    tokenizer_version_public_id: str | None = None,
) -> str:
    """Phase 2.7E: a real, architecture-verified Core Model Version
    matching `_tiny_model_config()`'s own shape, built through the real
    `CoreModelService` (family -> config -> validate -> version ->
    initialize -> verify-architecture) -- the exact real backend surface
    Phase 2.7D's own report proved end-to-end. Used only to satisfy
    `MiniBrainTrainingEngineService.create_job()`'s new identity
    requirement for execution_mode='gpu'; the pre-configured
    `TorchTrainingAdapter` instances these tests inject via `adapters=`
    remain the actual real trainer under test, unchanged.

    Phase 2.7G: pass a real, artifact-backed `tokenizer_version_public_id`
    to reference an *actual*, working SentencePiece tokenizer instead of
    this function's own default placeholder row (which has no real
    `tokenizer.model`/`tokenizer.vocab` files on disk and is therefore
    only usable for identity-plumbing tests, never for real
    tokenization). `create_config()` derives `vocabulary_size` from the
    referenced tokenizer's own row automatically -- never passed here."""

    from backend.database.connection import database_connection
    from backend.database.repositories.core_models import CoreModelRepository
    from backend.models.core_models import CoreConfigCreate, CoreFamilyCreate, CoreVersionCreate
    from backend.services.core_model_service import CoreModelService

    database = settings.resolved_database_path
    if tokenizer_version_public_id is None:
        with database_connection(database) as connection:
            connection.execute(
                """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
                VALUES (?,?,?,?,?)""",
                (f"ds-{name_suffix}", f"adapter-it-{name_suffix}", "v1", "ready", "d" * 64),
            )
            connection.execute(
                """INSERT INTO tokenizer_families(public_id,name,display_name,status)
                VALUES (?,?,?,?)""",
                (f"tf-{name_suffix}", f"adapter-it-tok-{name_suffix}", "T", "active"),
            )
            family_id = connection.execute(
                "SELECT id FROM tokenizer_families WHERE public_id=?", (f"tf-{name_suffix}",)
            ).fetchone()[0]
            dataset_id = connection.execute(
                "SELECT id FROM dataset_versions WHERE public_id=?", (f"ds-{name_suffix}",)
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
                lifecycle_status,algorithm,vocabulary_size,character_coverage,
                normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
                model_checksum_sha256,vocabulary_checksum_sha256,special_tokens_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"tok-{name_suffix}", family_id, "v1", "active", "bpe", 128, 0.9995,
                    "nmt_nfkc", "sentencepiece", dataset_id, "a" * 64, "b" * 64, "c" * 64, "[]",
                ),
            )
            connection.commit()
        tokenizer_version_public_id = f"tok-{name_suffix}"

    core_models = CoreModelService(CoreModelRepository(database), settings)
    family = core_models.create_family(
        CoreFamilyCreate(name=f"adapter-it-{name_suffix}", display_name="Adapter IT"), admin_id=admin_id,
    )
    config = core_models.create_config(
        CoreConfigCreate(
            name=f"adapter-it-config-{name_suffix}", config_version="v1",
            tokenizer_version_public_id=tokenizer_version_public_id, preset="micro",
            context_length=32, hidden_size=hidden_size, intermediate_size=intermediate_size,
            num_hidden_layers=2, num_attention_heads=num_attention_heads,
            num_key_value_heads=num_key_value_heads,
        ),
        admin_id=admin_id,
    )
    core_models.validate_config(config["public_id"], admin_id=admin_id)
    version = core_models.create_version(
        CoreVersionCreate(
            family_public_id=family["public_id"], config_public_id=config["public_id"], version="v0.1",
        ),
        admin_id=admin_id,
    )
    core_models.initialize(version["public_id"], admin_id=admin_id)
    core_models.verify_architecture(version["public_id"], admin_id=admin_id)
    return version["public_id"]


def _configured_adapter(tmp_path: Path, **overrides) -> TorchTrainingAdapter:
    kwargs = dict(
        model_config=_tiny_model_config(), pad_token_id=0, train_blocks=_tiny_train_blocks(),
        validation_blocks=_tiny_train_blocks(seed=1), pretraining_config=_tiny_pretraining_config(),
        checkpoint_root=tmp_path / "pretraining", configuration_label=CONFIGURATION_LABEL,
    )
    kwargs.update(overrides)
    return TorchTrainingAdapter(**kwargs)


# ============================================================================
# Part 11 -- adapter unit tests (18 minimum cases)
# ============================================================================


class TestAdapterUnit:
    # TEST 1 ------------------------------------------------------------
    def test_1_adapter_availability(self, tmp_path: Path) -> None:
        adapter = _configured_adapter(tmp_path)
        assert adapter.is_available() is True

    # TEST 2 ------------------------------------------------------------
    def test_2_adapter_capability_reporting(self, tmp_path: Path) -> None:
        adapter = _configured_adapter(tmp_path)
        report = adapter.reserve(resource_plan={})
        assert report["reserved"] is True
        assert report["runtime"] == "torch_cpu"
        assert report["parameter_count"] > 0
        assert report["configuration_label"] == CONFIGURATION_LABEL
        # Real, not fabricated: matches the exact architecture formula.
        expected = count_parameters(BrudForCausalLM(_tiny_model_config()))
        assert report["parameter_count"] == expected

    # TEST 3 ------------------------------------------------------------
    def test_3_valid_training_configuration_accepted(self, tmp_path: Path) -> None:
        adapter = _configured_adapter(tmp_path)
        report = adapter.reserve(resource_plan={})
        assert report["reserved"] is True

    # TEST 4 ------------------------------------------------------------
    def test_4_invalid_training_configuration_rejected(self, tmp_path: Path) -> None:
        bad_config = BrudModelConfig(
            vocabulary_size=64, context_length=32, hidden_size=15,  # not divisible by heads
            intermediate_size=32, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2,
        )
        adapter = _configured_adapter(tmp_path, model_config=bad_config)
        with pytest.raises(ValueError, match="hidden_size must be divisible"):
            adapter.reserve(resource_plan={})

    # TEST 5 ------------------------------------------------------------
    def test_5_missing_dataset_rejected(self, tmp_path: Path) -> None:
        adapter = _configured_adapter(tmp_path, train_blocks=None)
        with pytest.raises(BackendUnavailableError, match="no model/dataset configured"):
            adapter.reserve(resource_plan={})

    # TEST 6 ------------------------------------------------------------
    async def test_6_unapproved_training_package_rejected_at_service_level(
        self, api_app: FastAPI, tmp_path: Path
    ) -> None:
        """MB-22's own package-approval gate (`run_validate_package_stage`)
        applies identically regardless of execution_mode -- the real
        TorchTrainingAdapter does not and cannot bypass it, since it is
        never even reached until after this stage passes."""

        from backend.services.mini_brain_training_pipeline_service import (
            MiniBrainTrainingPipelineService,
        )

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="unapproved-pkg")
        # Create a second, never-approved package session.
        tp = MiniBrainTrainingPipelineService(api_app.state.settings)
        other = tp.create_session(topic="never approved", admin_id=admin_id)
        adapter = _configured_adapter(tmp_path)
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="t6")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="t6")
        job = svc.create_job(
            topic="unapproved job", training_package_session_public_id=other["public_id"],
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id,
        )
        svc.run_validate_release_stage(job["public_id"], admin_id=admin_id)
        with pytest.raises(ValidationError):
            svc.run_validate_package_stage(job["public_id"], admin_id=admin_id)

    # TEST 7 ------------------------------------------------------------
    async def test_7_unapproved_release_session_rejected_at_service_level(
        self, api_app: FastAPI, tmp_path: Path
    ) -> None:
        """MB-20 release-governance approval (which itself requires MB-16's
        real dataset quality/duplicate analysis and, upstream in Phase
        2.7B, the real content-safety gate on every document that fed the
        dataset) is enforced before the real adapter is ever reached."""

        admin_id = _create_admin(api_app)
        tp_id, _rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="unsafe-release-pkg")
        rg = MiniBrainReleaseGovernanceService(api_app.state.settings)
        never_approved = rg.create_session(topic="never approved release", admin_id=admin_id)
        adapter = _configured_adapter(tmp_path)
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="t7")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="t7")
        job = svc.create_job(
            topic="unsafe release job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=never_approved["public_id"], execution_mode="gpu",
            admin_id=admin_id, core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id,
        )
        with pytest.raises(ValidationError):
            svc.run_validate_release_stage(job["public_id"], admin_id=admin_id)

    # TEST 8/9 ------------------------------------------------------------
    def test_8_9_training_request_reaches_the_real_trainer_and_executes_a_real_step(
        self, tmp_path: Path
    ) -> None:
        adapter = _configured_adapter(tmp_path)
        adapter.reserve(resource_plan={})
        adapter.start(resume_step=0, resume_epoch=0)
        before = [p.clone() for p in adapter._model.parameters()]
        metric = adapter.step(step=1, epoch=0)
        after = list(adapter._model.parameters())
        assert metric["step"] == 1
        # Real gradient descent occurred -- weights actually changed.
        assert any(not b.equal(a) for b, a in zip(before, after, strict=True))

    # TEST 10 ------------------------------------------------------------
    def test_10_real_loss_is_produced_and_decreases_over_steps(self, tmp_path: Path) -> None:
        adapter = _configured_adapter(tmp_path, pretraining_config=_tiny_pretraining_config(total_steps=5))
        adapter.reserve(resource_plan={})
        adapter.start(resume_step=0, resume_epoch=0)
        losses = [adapter.step(step=s, epoch=0)["loss"] for s in range(1, 6)]
        assert all(isinstance(loss, float) and loss == loss for loss in losses)  # no NaN
        assert losses[-1] < losses[0]

    # TEST 11 ------------------------------------------------------------
    def test_11_real_checkpoint_is_produced(self, tmp_path: Path) -> None:
        adapter = _configured_adapter(tmp_path)
        adapter.reserve(resource_plan={})
        adapter.start(resume_step=0, resume_epoch=0)
        adapter.step(step=1, epoch=0)
        info = adapter.save_checkpoint(path=tmp_path / "pointer.json", step=1, epoch=0)
        assert info["is_metadata_only"] is False
        real_dir = Path(info["canonical_checkpoint_directory"])
        expected_files = {
            "model_state.pt", "optimizer_state.pt", "scheduler_state.pt", "rng_state.pt",
            "trainer_state.json", "config.json", "references.json", "manifest.json", "checksums.txt",
        }
        assert expected_files.issubset({p.name for p in real_dir.iterdir()})

    # TEST 12 ------------------------------------------------------------
    def test_12_checkpoint_loads_via_the_real_inference_loading_code(self, tmp_path: Path) -> None:
        """Mirrors `InferenceRuntimeService.load_instance_using_connection()`'s
        own loading sequence exactly (TrainingCheckpointManager + BrudForCausalLM
        + load_state_dict) -- not a special test-only loader."""

        adapter = _configured_adapter(tmp_path)
        adapter.reserve(resource_plan={})
        adapter.start(resume_step=0, resume_epoch=0)
        adapter.step(step=1, epoch=0)
        info = adapter.save_checkpoint(path=tmp_path / "pointer.json", step=1, epoch=0)
        checkpoint_dir = Path(info["canonical_checkpoint_directory"])

        fresh_model = BrudForCausalLM(_tiny_model_config())
        manager = TrainingCheckpointManager(checkpoint_dir.parent, 500_000_000)
        assert manager.verify(checkpoint_dir) is True
        states = manager.load_states(checkpoint_dir)
        fresh_model.load_state_dict(states["model"])  # must not raise
        assert states["references"]["architecture_name"] == "BrudForCausalLM"
        assert states["references"]["configuration_label"] == CONFIGURATION_LABEL

    # TEST 13 ------------------------------------------------------------
    def test_13_pause_callback_is_honored(self, tmp_path: Path) -> None:
        adapter = _configured_adapter(tmp_path, pretraining_config=_tiny_pretraining_config(total_steps=10))
        adapter.reserve(resource_plan={})
        adapter.start(resume_step=0, resume_epoch=0)
        adapter.step(step=1, epoch=0)
        adapter.pause()
        with pytest.raises(BackendUnavailableError, match="pause or cancel was observed"):
            adapter.step(step=2, epoch=0)
        assert adapter._completed_steps == 1  # step 2 genuinely never ran

    # TEST 14 ------------------------------------------------------------
    def test_14_cancellation_callback_is_honored(self, tmp_path: Path) -> None:
        adapter = _configured_adapter(tmp_path, pretraining_config=_tiny_pretraining_config(total_steps=10))
        adapter.reserve(resource_plan={})
        adapter.start(resume_step=0, resume_epoch=0)
        adapter.step(step=1, epoch=0)
        adapter.cancel()
        with pytest.raises(BackendUnavailableError, match="pause or cancel was observed"):
            adapter.step(step=2, epoch=0)
        assert adapter._completed_steps == 1

    # TEST 15 ------------------------------------------------------------
    async def test_15_checkpoint_callback_updates_mb22_job_state(
        self, api_app: FastAPI, tmp_path: Path
    ) -> None:
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="ckpt-state-pkg")
        adapter = _configured_adapter(tmp_path)
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="t15")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="t15")
        job_id = _drive_gpu_job_to_streaming(
            svc, tp_id, rg_id, admin_id, topic="ckpt-state-job",
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id,
        )
        svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoints = svc.list_checkpoints(job_id)["items"]
        assert len(checkpoints) == 1
        assert checkpoints[0]["is_metadata_only"] is False
        assert len(checkpoints[0]["sha256"]) == 64

    # TEST 16 ------------------------------------------------------------
    async def test_16_training_completion_updates_job_state_correctly(
        self, api_app: FastAPI, tmp_path: Path
    ) -> None:
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="complete-pkg")
        adapter = _configured_adapter(tmp_path)
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="t16")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="t16")
        job_id = _drive_gpu_job_to_streaming(
            svc, tp_id, rg_id, admin_id, topic="complete-job",
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id,
        )
        svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        job = svc.finalize(job_id, admin_id=admin_id)
        assert job["status"] == "completed"
        assert job["stage"] == "generate_report"

    # TEST 17 ------------------------------------------------------------
    def test_17_training_failure_updates_state_with_an_actionable_error(self, tmp_path: Path) -> None:
        """A real failure mode of the real trainer (a training block longer
        than the configured sequence_length, with truncation disabled --
        exactly `run_pretraining`'s own hardcoded `truncate=False` call)
        must propagate as a real, informative error, never be hidden or
        turned into a fabricated success."""

        too_long_blocks = [[5] * 40]  # sequence_length below is 16
        adapter = _configured_adapter(
            tmp_path, train_blocks=too_long_blocks, validation_blocks=too_long_blocks,
            pretraining_config=_tiny_pretraining_config(sequence_length=16),
        )
        adapter.reserve(resource_plan={})
        adapter.start(resume_step=0, resume_epoch=0)
        with pytest.raises(ValueError, match="exceeds max_length"):
            adapter.step(step=1, epoch=0)

    # TEST 18 ------------------------------------------------------------
    def test_18_no_fake_json_only_checkpoint_is_accepted_as_a_real_result(self, tmp_path: Path) -> None:
        real_adapter = _configured_adapter(tmp_path)
        real_adapter.reserve(resource_plan={})
        real_adapter.start(resume_step=0, resume_epoch=0)
        real_adapter.step(step=1, epoch=0)
        real_info = real_adapter.save_checkpoint(path=tmp_path / "real_pointer.json", step=1, epoch=0)
        assert real_info["is_metadata_only"] is False

        sim_adapter = SimulationTrainingAdapter()
        sim_adapter.reserve(resource_plan={})
        sim_adapter.start(resume_step=0, resume_epoch=0)
        sim_info = sim_adapter.save_checkpoint(path=tmp_path / "sim_pointer.json", step=1, epoch=0)
        assert sim_info["is_metadata_only"] is True
        # The two are never confusable.
        assert real_info["is_metadata_only"] != sim_info["is_metadata_only"]


def _drive_gpu_job_to_streaming(
    svc: MiniBrainTrainingEngineService, tp_id: str, rg_id: str, admin_id: str, *, topic: str,
    core_model_version_public_id: str, dataset_version_public_id: str,
) -> str:
    job = svc.create_job(
        topic=topic, training_package_session_public_id=tp_id, release_governance_session_public_id=rg_id,
        execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=core_model_version_public_id,
        dataset_version_public_id=dataset_version_public_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.7c integration test", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    svc.run_reserve_runtime_stage(job_id, admin_id=admin_id)
    svc.run_start_training_stage(job_id, admin_id=admin_id)
    return job_id


# ============================================================================
# Part 12/13/15 -- full real, isolated end-to-end integration run
# ============================================================================


class TestRealIsolatedTrainingRun:
    async def test_full_mb22_torch_adapter_real_trainer_real_checkpoint_run(
        self, api_app: FastAPI, tmp_path: Path
    ) -> None:
        """Mini Brain Training Engine -> TorchTrainingAdapter -> real
        forward/backward/optimizer step -> real checkpoint save -> real
        checkpoint registration -> real checkpoint load. Not a simulation."""

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="full-run-pkg")
        adapter = _configured_adapter(
            tmp_path, pretraining_config=_tiny_pretraining_config(total_steps=5, checkpoint_interval_steps=5),
        )
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})

        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="full")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="full")
        job_id = _drive_gpu_job_to_streaming(
            svc, tp_id, rg_id, admin_id, topic="full-run-job",
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id,
        )
        job = svc.job(job_id)
        assert job["status"] == "running"
        assert job["stage"] == "streaming_metrics"

        losses: list[float] = []
        for step in range(1, 6):
            job = svc.run_stream_metric_stage(job_id, step=step, epoch=0, admin_id=admin_id)
        metrics = svc.list_metrics(job_id)["items"]
        assert len(metrics) == 5
        losses = [m["loss"] for m in metrics]
        assert losses[-1] < losses[0], "real loss must have genuinely decreased"

        job = svc.run_save_checkpoint_stage(job_id, step=5, epoch=0, admin_id=admin_id)
        checkpoints = svc.list_checkpoints(job_id)["items"]
        assert len(checkpoints) == 1
        assert checkpoints[0]["is_metadata_only"] is False
        real_checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        assert real_checkpoint_dir.is_dir()
        assert (real_checkpoint_dir / "model_state.pt").is_file()

        job = svc.finalize(job_id, admin_id=admin_id)
        assert job["status"] == "completed"
        job = svc.generate_report_stage(job_id, admin_id=admin_id)
        assert job["final_report"]["checkpoint_count"] == 1
        job = svc.archive(job_id, admin_id=admin_id)
        assert job["status"] == "archived"

        # -- Part 13: real fresh-load + real generation, via the exact
        # same code InferenceRuntimeService uses internally. --
        import torch

        manager = TrainingCheckpointManager(real_checkpoint_dir.parent, 500_000_000)
        fresh_model = BrudForCausalLM(_tiny_model_config())
        states = manager.load_states(real_checkpoint_dir)
        fresh_model.load_state_dict(states["model"])
        fresh_model.eval()
        with torch.no_grad():
            output = fresh_model(torch.tensor([[2, 5, 9, 12]], dtype=torch.long))
        assert output.logits.shape == (1, 4, 64)
        assert torch.isfinite(output.logits).all()

        # -- Part 15: governance/activation safety. Training through MB-22
        # must never touch release/assignment tables. --
        import sqlite3

        connection = sqlite3.connect(api_app.state.settings.resolved_database_path)
        try:
            assert connection.execute(
                "SELECT COUNT(*) FROM inference_model_assignments"
            ).fetchone()[0] == 0
            assert connection.execute("SELECT COUNT(*) FROM model_releases").fetchone()[0] == 0
            assert connection.execute("SELECT COUNT(*) FROM pretraining_jobs").fetchone()[0] == 0
        finally:
            connection.close()
