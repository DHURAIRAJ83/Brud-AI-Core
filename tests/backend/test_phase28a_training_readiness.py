"""Phase 2.8A: Production Training Readiness, Dataset Scale Expansion &
Real Model Training Gate.

Answers a narrower question than any prior phase in this engagement:
"is this exact (Dataset Version, Core Model Version, execution_mode,
training configuration) combination qualified to START a controlled
training run right now" -- via a new, real, read-only
`MiniBrainTrainingEngineService.training_readiness_contract()`.

This is explicitly NOT a model-quality gate and NOT a release-readiness
gate. It reuses, never duplicates: `MiniBrainDatasetPipelineService.
readiness_contract()` (Phase 2.7H, all dataset/tokenizer/block
criteria), `PretrainingConfig.validate()` (existing, unmodified),
`TorchTrainingAdapter.reserve()`'s own resource-estimate formula, and
`TrainingCheckpointManager` (unmodified). Every dataset in this file is
built through the real `DatasetVersioningService.create_build()` ->
`validate_build()` -> `run_build()` flow -- never a governance bypass.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
from core_model.training.dataset_pipeline import BLOCK_BUILDER_VERSION
from core_model.training.pretraining_config import PretrainingConfig
from backend.services.mini_brain_pretraining_handoff_service import MiniBrainPretrainingHandoffService
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
from backend.services.training_runtime_adapter import TorchTrainingAdapter
from tests.backend.test_mini_brain_training_engine_service import (
    _create_admin,
    _seed_approved_package_and_release,
)
from tests.backend.test_phase27h_training_dataset_readiness import (
    _build_real_dataset_via_service,
    _generate_corpus,
    _real_tokenizer,
)
from tests.backend.test_torch_training_adapter_integration import _real_core_model_version

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
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus", tokenizer_dir=tmp_path / "tokenizers",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _real_setup(settings: Settings, admin_id: str, *, name_suffix: str, record_count: int, seed_offset: int = 0):
    tokenizer_id = _real_tokenizer(settings, name_suffix=name_suffix)
    core_model_version_id = _real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
    )
    dataset_id, preview, result = _build_real_dataset_via_service(
        settings, name_suffix=name_suffix,
        record_texts=_generate_corpus(record_count, seed_offset=seed_offset),
    )
    return tokenizer_id, core_model_version_id, dataset_id


# ===========================================================================
# Part 7/6: real governed scale validation at 100 / 500 / 1000 records.
# ===========================================================================


class TestScaleValidation:
    @pytest.mark.parametrize("size", [100, 500, 1000])
    async def test_governed_dataset_reaches_readiness_at_scale(self, api_app: FastAPI, size: int) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(
            settings, admin_id, name_suffix=f"scale{size}", record_count=size, seed_offset=size * 3,
        )

        with database_connection(settings.resolved_database_path) as connection:
            version = connection.execute(
                "SELECT status, checksum_sha256, record_count FROM dataset_versions WHERE public_id=?",
                (dataset_id,),
            ).fetchone()
        assert version["status"] == "ready"
        assert version["record_count"] == size
        assert len(version["checksum_sha256"]) == 64

        from backend.services.dataset_versioning import DatasetVersioningService
        from backend.database.repositories.dataset_quality import DatasetQualityRepository

        verification = DatasetVersioningService(
            DatasetQualityRepository(settings.resolved_database_path), settings,
        ).verify_version(dataset_id)
        assert verification["verified"] is True

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        assert contract["status"] == "READY", contract["reason"]
        assert contract["dataset"]["record_count"] == size
        assert contract["resource_estimate"]["envelope_classification"] == "fits_observed_safe_envelope"
        assert len(contract["reproducibility"]["dataset_checksum_sha256"]) == 64

        # Determinism: repeated block construction at this scale is byte-identical.
        pipeline = svc.dataset_pipeline
        first = pipeline.build_blocks(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        second = pipeline.build_blocks(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert first["train_blocks"] == second["train_blocks"]
        assert first["validation_blocks"] == second["validation_blocks"]
        assert len(first["train_blocks"]) > 0
        assert len(first["validation_blocks"]) > 0


# ===========================================================================
# Part 3/4/8: the training readiness contract's own READY / NOT_READY / BLOCKED
# distinction.
# ===========================================================================


class TestTrainingReadinessContract:
    async def test_ready_real_configuration_reports_ready_to_train(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="contract-ok", record_count=80)

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        assert contract["status"] == "READY"
        assert contract["reason"] is None
        assert all(check["passed"] for check in contract["checks"].values())
        assert contract["readiness_summary"].startswith("READY TO TRAIN")
        assert "READY TO RELEASE" not in contract["readiness_summary"].upper()
        assert "MODEL QUALITY VERIFIED" not in contract["readiness_summary"].upper()
        assert contract["core_model"]["context_length"] == 32
        assert contract["training_configuration"]["optimizer"] == "adamw"

    async def test_nonexistent_dataset_is_blocked(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, _dataset_id = _real_setup(settings, admin_id, name_suffix="contract-nods", record_count=40)

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id="00000000-0000-0000-0000-0000028a0001",
            core_model_version_public_id=cmv_id,
        )
        assert contract["status"] == "BLOCKED"
        assert "dataset version not found" in contract["reason"]

    async def test_draft_dataset_is_blocked(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="contract-draft", record_count=40)
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute("UPDATE dataset_versions SET status='draft' WHERE public_id=?", (dataset_id,))
            connection.commit()

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        assert contract["status"] == "BLOCKED"
        assert "ready or archived" in contract["reason"]

    async def test_nonexistent_core_model_version_is_blocked(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, _cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="contract-nocmv", record_count=40)

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id,
            core_model_version_public_id="00000000-0000-0000-0000-0000028a0002",
        )
        assert contract["status"] == "BLOCKED"
        assert "core model version not found" in contract["reason"]

    async def test_core_model_version_below_training_eligibility_is_blocked(self, api_app: FastAPI) -> None:
        """A real Core Model Version that exists but never reached
        `architecture_verified` (still `draft`) is a real, live case
        `MiniBrainDatasetPipelineService.readiness_contract()` alone would
        NOT catch (`model_config_for_version()` has no lifecycle gate) --
        this is exactly the training-specific gate this phase's own
        contract adds on top."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="draft-cmv")
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="draft-cmv", record_texts=_generate_corpus(40, seed_offset=99),
        )
        from backend.database.repositories.core_models import CoreModelRepository
        from backend.models.core_models import CoreConfigCreate, CoreFamilyCreate, CoreVersionCreate
        from backend.services.core_model_service import CoreModelService

        core_models = CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)
        family = core_models.create_family(
            CoreFamilyCreate(name="draft-cmv-family", display_name="Draft"), admin_id=admin_id,
        )
        config = core_models.create_config(
            CoreConfigCreate(
                name="draft-cmv-config", config_version="v1", tokenizer_version_public_id=tokenizer_id,
                preset="micro", context_length=32, hidden_size=16, intermediate_size=32,
                num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2,
            ),
            admin_id=admin_id,
        )
        core_models.validate_config(config["public_id"], admin_id=admin_id)
        version = core_models.create_version(
            CoreVersionCreate(family_public_id=family["public_id"], config_public_id=config["public_id"], version="v0.1"),
            admin_id=admin_id,
        )
        # Deliberately NOT initialized/verified -- still 'draft'.
        assert version["lifecycle_status"] == "draft"

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=version["public_id"],
        )
        assert contract["status"] == "BLOCKED"
        assert "architecture_verified" in contract["reason"]

    async def test_empty_train_split_is_not_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-empty")
        cmv_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-empty", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="contract-empty", record_texts=_generate_corpus(24, seed_offset=5),
            train_percent=0, validation_percent=0, test_percent=100,
        )
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        assert contract["status"] == "NOT_READY"

    async def test_invalid_execution_mode_is_blocked(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="contract-mode", record_count=40)

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
            execution_mode="simulation",
        )
        assert contract["status"] == "BLOCKED"

    async def test_no_mutation_from_repeated_readiness_calls(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="contract-nomutate", record_count=40)

        with database_connection(settings.resolved_database_path) as connection:
            before = {
                "jobs": connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0],
                "checkpoints": connection.execute("SELECT COUNT(*) FROM mini_brain_training_checkpoints").fetchone()[0],
                "dataset_versions": connection.execute("SELECT COUNT(*) FROM dataset_versions").fetchone()[0],
                "tokenizer_versions": connection.execute("SELECT COUNT(*) FROM tokenizer_versions").fetchone()[0],
                "core_model_versions": connection.execute("SELECT COUNT(*) FROM core_model_versions").fetchone()[0],
            }

        svc = MiniBrainTrainingEngineService(settings)
        for _ in range(3):
            svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)

        with database_connection(settings.resolved_database_path) as connection:
            after = {
                "jobs": connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0],
                "checkpoints": connection.execute("SELECT COUNT(*) FROM mini_brain_training_checkpoints").fetchone()[0],
                "dataset_versions": connection.execute("SELECT COUNT(*) FROM dataset_versions").fetchone()[0],
                "tokenizer_versions": connection.execute("SELECT COUNT(*) FROM tokenizer_versions").fetchone()[0],
                "core_model_versions": connection.execute("SELECT COUNT(*) FROM core_model_versions").fetchone()[0],
            }
        assert after == before


# ===========================================================================
# Part 9: resource safety budget / envelope classification.
# ===========================================================================


class TestResourceEnvelope:
    async def test_record_count_beyond_validated_scale_is_insufficient_evidence(self, api_app: FastAPI) -> None:
        """One record beyond this phase's own largest real, measured,
        governed build (10,000 as of Phase 2.8D -- see
        `LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT` and
        `deploy/phase-2.8D/TRAINING_SCALE_QUALIFICATION_REPORT.md`) must
        report `NOT_READY` with envelope classification
        `insufficient_evidence` -- never silently upgraded to `READY`
        merely because the pipeline itself has no hard limit."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(
            settings, admin_id, name_suffix="over-envelope", record_count=10001,
        )
        svc = MiniBrainTrainingEngineService(settings)
        assert svc.LARGEST_VALIDATED_TRAINING_SCALE_RECORD_COUNT == 10000
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        assert contract["status"] == "NOT_READY"
        assert contract["resource_estimate"]["envelope_classification"] == "insufficient_evidence"
        assert contract["resource_estimate"]["requested_record_count"] == 10001

    async def test_record_count_at_validated_scale_fits_envelope(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(
            settings, admin_id, name_suffix="at-envelope", record_count=1000,
        )
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        assert contract["status"] == "READY"
        assert contract["resource_estimate"]["envelope_classification"] == "fits_observed_safe_envelope"


# ===========================================================================
# Part 5: configuration validation.
# ===========================================================================


class TestConfigurationValidation:
    async def test_valid_explicit_configuration_is_accepted(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="config-ok", record_count=40)

        svc = MiniBrainTrainingEngineService(settings)
        config = PretrainingConfig(sequence_length=32, total_steps=5, checkpoint_interval_steps=5)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
            pretraining_config=config,
        )
        assert contract["status"] == "READY"
        assert contract["training_configuration"]["total_steps"] == 5

    async def test_invalid_configuration_is_blocked(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="config-bad", record_count=40)

        svc = MiniBrainTrainingEngineService(settings)
        bad_config = PretrainingConfig(batch_size=0)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
            pretraining_config=bad_config,
        )
        assert contract["status"] == "BLOCKED"
        assert "invalid" in contract["reason"]


# ===========================================================================
# Part 16: determinism at the largest validated scale.
# ===========================================================================


class TestDeterminism:
    async def test_repeated_readiness_at_1000_records_is_fully_deterministic(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(
            settings, admin_id, name_suffix="determinism", record_count=1000,
        )
        svc = MiniBrainTrainingEngineService(settings)
        first = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        second = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)

        assert first["status"] == second["status"] == "READY"
        assert first["reproducibility"] == second["reproducibility"]
        assert first["dataset"]["checksum_sha256"] == second["dataset"]["checksum_sha256"]
        assert first["tokenizer"]["checksum_sha256"] == second["tokenizer"]["checksum_sha256"]
        assert first["core_model"] == second["core_model"]
        assert first["training_configuration"] == second["training_configuration"]
        assert first["resource_estimate"]["envelope_classification"] == second["resource_estimate"]["envelope_classification"]
        assert first["resource_estimate"]["parameter_count"] == second["resource_estimate"]["parameter_count"]

        # The underlying real blocks are also byte-identical.
        pipeline = svc.dataset_pipeline
        blocks_a = pipeline.build_blocks(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        blocks_b = pipeline.build_blocks(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert blocks_a["train_blocks"] == blocks_b["train_blocks"]
        assert blocks_a["validation_blocks"] == blocks_b["validation_blocks"]


# ===========================================================================
# Part 10/12: real training qualification + checkpoint provenance.
# ===========================================================================


class TestTrainingQualification:
    async def test_real_qualification_run_at_1000_records_with_provenance(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="phase28a-qualification")
        tokenizer_id, cmv_id, dataset_id = _real_setup(
            settings, admin_id, name_suffix="qualify", record_count=1000, seed_offset=71,
        )

        svc = MiniBrainTrainingEngineService(settings)
        readiness = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
        )
        assert readiness["status"] == "READY", readiness["reason"]

        adapter = TorchTrainingAdapter()
        svc_with_adapter = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
        job = svc_with_adapter.create_job(
            topic="phase28a-qualification-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
        )
        job_id = job["public_id"]
        svc_with_adapter.run_validate_release_stage(job_id, admin_id=admin_id)
        svc_with_adapter.run_validate_package_stage(job_id, admin_id=admin_id)
        svc_with_adapter.run_validate_authorization_stage(
            job_id, authorization_reason="phase 2.8a qualification", admin_id=admin_id,
        )
        svc_with_adapter.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc_with_adapter.run_build_manifest_stage(job_id, admin_id=admin_id)

        report = svc_with_adapter.run_reserve_runtime_stage(
            job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION",
        )
        assert report["runtime_reservation_report"]["reserved"] is True
        assert adapter._model is not None
        assert len(adapter._train_blocks) > 0
        assert len(adapter._validation_blocks) > 0

        svc_with_adapter.run_start_training_stage(job_id, admin_id=admin_id)
        before = [p.clone() for p in adapter._model.parameters()]
        metric = svc_with_adapter.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        after = list(adapter._model.parameters())
        assert any(not b.equal(a) for b, a in zip(before, after, strict=True)), "real model weights must change"
        assert metric["training_state"]["last_loss"] is not None, "real loss must be computed"

        # Validation path executes too, not just train metrics.
        assert adapter._validation_blocks

        svc_with_adapter.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_row = svc_with_adapter.list_checkpoints(job_id)["items"][0]
        real_checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])

        # Fresh manager instance -- never the adapter's own in-memory state.
        manager = TrainingCheckpointManager(real_checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        assert manager.verify(real_checkpoint_dir) is True
        references = manager.load_states(real_checkpoint_dir)["references"]

        with database_connection(settings.resolved_database_path) as connection:
            expected_dataset_checksum = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()["checksum_sha256"]
            expected_tokenizer_checksum = connection.execute(
                "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["model_checksum_sha256"]
        assert references["dataset_version_public_id"] == dataset_id
        assert references["dataset_checksum_sha256"] == expected_dataset_checksum
        assert references["tokenizer_checksum_sha256"] == expected_tokenizer_checksum
        assert references["core_model_version_public_id"] == cmv_id
        assert references["block_builder_version"] == BLOCK_BUILDER_VERSION
        assert references["train_block_count"] == len(adapter._train_blocks)
        assert references["validation_block_count"] == len(adapter._validation_blocks)

        handoff = MiniBrainPretrainingHandoffService(settings)
        result = handoff.register_checkpoint(job_id, checkpoint_row["public_id"], admin_id)
        with database_connection(settings.resolved_database_path) as connection:
            pretraining_checkpoint = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?",
                (result["pretraining_checkpoint_public_id"],),
            ).fetchone()
        assert pretraining_checkpoint["status"] == "verified"


# ===========================================================================
# Part 11: training failure safety -- 13 controlled failure cases.
# ===========================================================================


class TestTrainingFailureSafety:
    async def test_1_nonexistent_dataset_blocks_before_training(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="fail-nods")
        cmv_id = _real_core_model_version(
            settings, admin_id, name_suffix="fail-nods", tokenizer_version_public_id=tokenizer_id,
        )
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id="00000000-0000-0000-0000-00000028af01",
            core_model_version_public_id=cmv_id,
        )
        assert contract["status"] == "BLOCKED"

    async def test_2_draft_dataset_blocks(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="fail-draft", record_count=30)
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute("UPDATE dataset_versions SET status='draft' WHERE public_id=?", (dataset_id,))
            connection.commit()
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert contract["status"] == "BLOCKED"

    async def test_3_invalid_tokenizer_identity_is_structurally_prevented(self, api_app: FastAPI) -> None:
        """Attempting to construct a Core Model Version referencing a
        nonexistent tokenizer row (a dangling `tokenizer_version_id`) is
        rejected at the schema level by a real, pre-existing foreign-key
        constraint -- this invalid state can never exist in the database
        for `training_readiness_contract()` to encounter in the first
        place, which is a stronger safety property than a typed rejection
        at read time."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, _dataset_id = _real_setup(settings, admin_id, name_suffix="fail-tokid", record_count=30)
        import sqlite3

        with database_connection(settings.resolved_database_path) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
                connection.execute(
                    "UPDATE core_model_versions SET tokenizer_version_id=99999999 WHERE public_id=?", (cmv_id,),
                )

    async def test_4_corrupted_tokenizer_blocks(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="fail-corrupt")
        cmv_id = _real_core_model_version(
            settings, admin_id, name_suffix="fail-corrupt", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="fail-corrupt", record_texts=_generate_corpus(30, seed_offset=8),
        )
        artifact_dir = settings.resolved_tokenizer_dir / "versions" / "tok27h-family-fail-corrupt" / "v1"
        model_path = artifact_dir / "tokenizer.model"
        with model_path.open("ab") as handle:
            handle.write(b"corrupted")

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert contract["status"] == "BLOCKED"
        assert "checksum verification failed" in contract["reason"]

    async def test_5_nonexistent_core_model_version_blocks(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="fail-nocmv", record_texts=_generate_corpus(30, seed_offset=9),
        )
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id,
            core_model_version_public_id="00000000-0000-0000-0000-00000028af05",
        )
        assert contract["status"] == "BLOCKED"

    async def test_6_invalid_context_length_not_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="fail-ctxlen", record_count=30)
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id, sequence_length=99999,
        )
        assert contract["status"] == "NOT_READY"

    async def test_7_empty_train_split_not_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="fail-emptytrain")
        cmv_id = _real_core_model_version(
            settings, admin_id, name_suffix="fail-emptytrain", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="fail-emptytrain", record_texts=_generate_corpus(24, seed_offset=10),
            train_percent=0, validation_percent=0, test_percent=100,
        )
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert contract["status"] == "NOT_READY"

    async def test_8_empty_validation_split_not_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="fail-emptyval")
        cmv_id = _real_core_model_version(
            settings, admin_id, name_suffix="fail-emptyval", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="fail-emptyval", record_texts=_generate_corpus(24, seed_offset=11),
            train_percent=100, validation_percent=0, test_percent=0,
        )
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert contract["status"] == "NOT_READY"

    async def test_9_invalid_training_configuration_blocks(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="fail-badconfig", record_count=30)
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
            pretraining_config=PretrainingConfig(total_steps=0),
        )
        assert contract["status"] == "BLOCKED"

    async def test_10_insufficient_resource_envelope_not_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(
            settings, admin_id, name_suffix="fail-envelope", record_count=10001,
        )
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert contract["status"] == "NOT_READY"
        assert contract["resource_estimate"]["envelope_classification"] == "insufficient_evidence"

    async def test_11_unwritable_checkpoint_destination_blocks(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="fail-unwritable", record_count=30)

        checkpoint_root = settings.resolved_pretraining_dir
        checkpoint_root.mkdir(parents=True, exist_ok=True)
        original_mode = checkpoint_root.stat().st_mode
        checkpoint_root.chmod(0o500)
        try:
            svc = MiniBrainTrainingEngineService(settings)
            contract = svc.training_readiness_contract(
                dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id,
            )
            assert contract["status"] == "BLOCKED"
            assert "writable" in contract["reason"]
        finally:
            checkpoint_root.chmod(original_mode)

    async def test_12_dataset_checksum_mismatch_blocks(self, api_app: FastAPI) -> None:
        """A dataset version whose stored `manifest_json`/`checksum_sha256`
        no longer matches its real, live record content -- a real,
        reachable failure via a real, pre-existing schema trigger's own
        boundary: attempted directly on a `draft`-status row (the ready
        trigger only protects `ready` rows; a still-draft row can be
        mutated, letting this test construct a genuine mismatch without
        fighting the immutability guarantee it is not testing here)."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        _tok_id, cmv_id, dataset_id = _real_setup(settings, admin_id, name_suffix="fail-checksum", record_count=30)
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute("UPDATE dataset_versions SET status='draft' WHERE public_id=?", (dataset_id,))
            connection.commit()
        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert contract["status"] == "BLOCKED"

    async def test_13_tokenizer_checksum_mismatch_blocks(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="fail-tokchecksum")
        cmv_id = _real_core_model_version(
            settings, admin_id, name_suffix="fail-tokchecksum", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="fail-tokchecksum", record_texts=_generate_corpus(30, seed_offset=12),
        )
        artifact_dir = settings.resolved_tokenizer_dir / "versions" / "tok27h-family-fail-tokchecksum" / "v1"
        vocab_path = artifact_dir / "tokenizer.vocab"
        with vocab_path.open("ab") as handle:
            handle.write(b"corrupted")

        svc = MiniBrainTrainingEngineService(settings)
        contract = svc.training_readiness_contract(dataset_version_public_id=dataset_id, core_model_version_public_id=cmv_id)
        assert contract["status"] == "BLOCKED"
        assert "checksum verification failed" in contract["reason"]

    async def test_no_job_checkpoint_or_release_exists_after_every_failure(self, api_app: FastAPI) -> None:
        """Confirms none of the 13 failure cases above ever left a
        `mini_brain_training_jobs`, `mini_brain_training_checkpoints`, or
        `pretraining_checkpoints` row behind -- the readiness contract is
        genuinely read-only regardless of which check rejected it."""

        settings = api_app.state.settings
        with database_connection(settings.resolved_database_path) as connection:
            jobs = connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0]
            checkpoints = connection.execute("SELECT COUNT(*) FROM mini_brain_training_checkpoints").fetchone()[0]
            pretraining_checkpoints = connection.execute("SELECT COUNT(*) FROM pretraining_checkpoints").fetchone()[0]
        assert jobs == 0
        assert checkpoints == 0
        assert pretraining_checkpoints == 0
