"""Phase 2.7E: Mini Brain <-> Core Model identity integration.

Proves the specific gap Phase 2.7D's own audit found and this phase
closes: `MiniBrainTrainingEngineService` (MB-22) now requires and
carries a real `core_model_version_public_id` for any real
(execution_mode='gpu') job, that identity resolves into a real
`BrudModelConfig` fed to the real `TorchTrainingAdapter` through the
*actual HTTP-reachable* `reserve-runtime` endpoint (previously this
endpoint never passed `job_context` at all -- the real adapter was only
ever exercised via manual, test-only adapter construction, never through
its own API), and the resulting real, canonical `TrainingCheckpointManager`
checkpoint carries that same identity on its `mini_brain_training_checkpoints`
row and survives a fresh process (no process-local cache).

Reuses the exact real governance chain
(`_seed_approved_package_and_release`) and admin/session fixtures
`test_mini_brain_training_engine_service.py` and
`test_torch_training_adapter_integration.py` already established --
never a parallel fixture system.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
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


async def _drive_to_reserve_runtime(
    svc: MiniBrainTrainingEngineService, *, tp_id: str, rg_id: str, admin_id: str,
    core_model_version_public_id: str, dataset_version_public_id: str, topic: str,
) -> str:
    job = svc.create_job(
        topic=topic, training_package_session_public_id=tp_id, release_governance_session_public_id=rg_id,
        execution_mode="gpu", admin_id=admin_id, core_model_version_public_id=core_model_version_public_id,
        dataset_version_public_id=dataset_version_public_id,
    )
    job_id = job["public_id"]
    svc.run_validate_release_stage(job_id, admin_id=admin_id)
    svc.run_validate_package_stage(job_id, admin_id=admin_id)
    svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.7e identity test", admin_id=admin_id)
    svc.run_plan_resources_stage(job_id, admin_id=admin_id)
    svc.run_build_manifest_stage(job_id, admin_id=admin_id)
    return job_id


class TestJobCreationIdentityGate:
    """TEST A-D of Part 17 (negative tests): the job-creation identity gate."""

    async def test_a_gpu_job_without_core_model_version_is_rejected(self, api_app: FastAPI) -> None:
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="no-identity-pkg")
        svc = MiniBrainTrainingEngineService(api_app.state.settings)
        with pytest.raises(ValidationError, match="core_model_version_public_id is required"):
            svc.create_job(
                topic="no identity job", training_package_session_public_id=tp_id,
                release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            )

    async def test_b_gpu_job_with_nonexistent_core_model_version_is_rejected(self, api_app: FastAPI) -> None:
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="bad-identity-pkg")
        svc = MiniBrainTrainingEngineService(api_app.state.settings)
        with pytest.raises(ValidationError, match="core model version not found"):
            svc.create_job(
                topic="bad identity job", training_package_session_public_id=tp_id,
                release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
                core_model_version_public_id="00000000-0000-0000-0000-000000099999",
            )

    async def test_c_gpu_job_with_draft_core_model_version_is_rejected(self, api_app: FastAPI) -> None:
        """A version that has never been through architecture verification
        (still 'draft') must never be trainable -- the real backend's own
        lifecycle_status gate, reused, not bypassed."""

        from backend.database.repositories.core_models import CoreModelRepository
        from backend.models.core_models import CoreConfigCreate, CoreFamilyCreate, CoreVersionCreate
        from backend.services.core_model_service import CoreModelService
        from tests.backend.test_torch_training_adapter_integration import _real_core_model_version as _rcmv  # noqa: F401

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="draft-identity-pkg")

        settings = api_app.state.settings
        from backend.database.connection import database_connection

        with database_connection(settings.resolved_database_path) as connection:
            connection.execute(
                """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
                VALUES ('ds-draft','draft-ds','v1','ready',?)""",
                ("d" * 64,),
            )
            connection.execute(
                """INSERT INTO tokenizer_families(public_id,name,display_name,status)
                VALUES ('tf-draft','draft-tok','T','active')""",
            )
            family_id = connection.execute(
                "SELECT id FROM tokenizer_families WHERE public_id='tf-draft'"
            ).fetchone()[0]
            dataset_id = connection.execute(
                "SELECT id FROM dataset_versions WHERE public_id='ds-draft'"
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
                lifecycle_status,algorithm,vocabulary_size,character_coverage,
                normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
                model_checksum_sha256,vocabulary_checksum_sha256,special_tokens_json)
                VALUES ('tok-draft',?,'v1','active','bpe',128,0.9995,'nmt_nfkc','sentencepiece',?,?,?,?,'[]')""",
                (family_id, dataset_id, "a" * 64, "b" * 64, "c" * 64),
            )
            connection.commit()

        core_models = CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)
        family = core_models.create_family(
            CoreFamilyCreate(name="draft-family", display_name="Draft"), admin_id=admin_id,
        )
        config = core_models.create_config(
            CoreConfigCreate(
                name="draft-config", config_version="v1", tokenizer_version_public_id="tok-draft",
                preset="micro", context_length=64, hidden_size=16, intermediate_size=32,
                num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2,
            ),
            admin_id=admin_id,
        )
        core_models.validate_config(config["public_id"], admin_id=admin_id)
        version = core_models.create_version(
            CoreVersionCreate(family_public_id=family["public_id"], config_public_id=config["public_id"], version="v0.1"),
            admin_id=admin_id,
        )
        # Deliberately never initialized/verified -- still 'draft'.
        assert version["lifecycle_status"] == "draft"

        svc = MiniBrainTrainingEngineService(api_app.state.settings)
        with pytest.raises(ValidationError, match="must be at least architecture_verified"):
            svc.create_job(
                topic="draft identity job", training_package_session_public_id=tp_id,
                release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
                core_model_version_public_id=version["public_id"],
            )

    async def test_d_simulation_job_never_requires_a_core_model_version(self, api_app: FastAPI) -> None:
        """Backward compatibility: every historical simulation/cpu-mode
        job creation call keeps working exactly as before -- this
        identity requirement is real-training-only."""

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="sim-pkg")
        svc = MiniBrainTrainingEngineService(api_app.state.settings)
        job = svc.create_job(
            topic="simulation job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="simulation", admin_id=admin_id,
        )
        assert job["core_model_version_public_id"] is None


class TestReserveRuntimeRealJobContext:
    """The new HTTP-reachable real path: `reserve-runtime` now builds a
    real `job_context` from the job's own Core Model Version identity and
    passes it to the real `TorchTrainingAdapter` -- proven via the actual
    HTTP route, not by importing the service directly."""

    async def test_e_reserve_runtime_without_train_blocks_auto_derives_and_fails_typed_without_a_real_tokenizer(
        self, api_app: FastAPI,
    ) -> None:
        """TEST 17-E (missing tokenizer/dataset input path): omitting
        `train_blocks` no longer means "caller forgot something" (Phase
        2.7G superseded that) -- it means "auto-derive from the job's own
        real dataset". `_real_core_model_version()`'s own tokenizer
        fixture (Phase 2.7E) was only ever a placeholder row with no real
        SentencePiece artifact files on disk, so auto-derivation reaches
        the real `TokenizerService.processor_for_version()` and fails
        there, honestly and typed -- never a silent no-op, never a 500.
        Phase 2.7G's own dedicated test suite
        (`test_mini_brain_dataset_pipeline.py`) proves the real, working,
        artifact-backed path end to end."""

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="missing-blocks-pkg")
        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="e")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="e")
        adapter = TorchTrainingAdapter()  # deliberately unconfigured -- this test proves reserve-runtime configures it
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
        job_id = await _drive_to_reserve_runtime(
            svc, tp_id=tp_id, rg_id=rg_id, admin_id=admin_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id, topic="missing-blocks-job",
        )
        with pytest.raises(ValidationError, match="tokenizer artifacts are incomplete"):
            svc.run_reserve_runtime_stage(
                job_id, admin_id=admin_id, train_blocks=None,
                configuration_label="TEST_INTEGRATION_CONFIGURATION",
            )

    async def test_f_real_http_reserve_runtime_builds_a_real_identity_linked_job_context(
        self, api_app: FastAPI,
    ) -> None:
        """The specific gap this phase closes, proven over real HTTP: a
        POST to `.../reserve-runtime` with real `train_blocks` in the
        body now genuinely configures the real `TorchTrainingAdapter`
        with a `BrudModelConfig` derived from this exact job's own Core
        Model Version -- previously this endpoint never passed any
        `job_context` at all, so this call would have failed with
        "no model/dataset configured" for any real (gpu-mode) job.
        `parameter_count` in the response is not self-reported by the
        request -- it is computed by `BrudForCausalLM`/`count_parameters`
        from whichever config the adapter actually received, so a value
        matching this exact Core Model Version's own real, independently-
        computed estimate is proof the real identity -- not a stub --
        flowed all the way through the real HTTP boundary.

        Deliberately a single call on its own job (not continued to
        `/start`): each HTTP request gets its own fresh service/adapter
        instance (`service(settings)` has no cross-request cache), so a
        real adapter configured by one request is not reachable from a
        later one -- a genuine, pre-existing MB-22 execution-model
        constraint independent of identity, documented in the Phase 2.7E
        report rather than routed around here. TEST G below proves the
        full multi-step loop (start -> step -> checkpoint) the same way
        Phase 2.7C's own adapter tests already do: one persistent service
        instance for the whole run."""

        from tests.backend.test_dataset_api import authenticated_client

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="real-http-pkg")
        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="f")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="f")
        # `actual_parameter_count` -- set by `CoreModelService.initialize()`
        # (already called inside `_real_core_model_version()`) via the
        # exact same `count_parameters(BrudForCausalLM(config))` the real
        # adapter's own `reserve()` uses -- not `estimated_parameter_count`,
        # which is a formula-based approximation allowed to differ by up
        # to 1% (see `CoreModelService.validate_config()`).
        expected_parameter_count = MiniBrainTrainingEngineService(
            api_app.state.settings
        ).core_models.get_version(core_model_version_public_id)["actual_parameter_count"]

        svc = MiniBrainTrainingEngineService(api_app.state.settings)  # no override -- proves the real HTTP path, not a test double
        job_id = await _drive_to_reserve_runtime(
            svc, tp_id=tp_id, rg_id=rg_id, admin_id=admin_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id, topic="real-http-job",
        )

        client, headers = await authenticated_client(api_app)
        try:
            TE = "/api/admin/mini-brain/training-engine"
            response = await client.post(
                f"{TE}/jobs/{job_id}/reserve-runtime",
                json={
                    "train_blocks": _tiny_train_blocks(),
                    "validation_blocks": _tiny_train_blocks(seed=1),
                    "configuration_label": "TEST_INTEGRATION_CONFIGURATION",
                },
                headers=headers,
            )
        finally:
            await client.aclose()

        assert response.status_code == 200, response.text
        report = response.json()["runtime_reservation_report"]
        assert report["reserved"] is True
        assert report["runtime"] == "torch_cpu"
        assert report["configuration_label"] == "TEST_INTEGRATION_CONFIGURATION"
        assert report["parameter_count"] == expected_parameter_count

    async def test_g_full_real_training_loop_via_identity_derived_job_context(
        self, api_app: FastAPI,
    ) -> None:
        """Part 15's full real, isolated run -- but through THIS phase's
        new code path specifically: `run_reserve_runtime_stage()` is
        called WITH `train_blocks` (unlike Phase 2.7C's own 18 adapter
        tests, which all pre-configure the adapter via its constructor
        and call reserve-runtime with nothing), so this test is the one
        that actually exercises `_build_real_job_context()` end to end:
        Core Model Version -> real BrudModelConfig -> real
        TorchTrainingAdapter -> real step -> real loss/weight change ->
        real canonical checkpoint carrying the same identity -> fresh-
        process-safe reload."""

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="full-loop-pkg")
        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="g")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="g")

        adapter = TorchTrainingAdapter()  # deliberately unconfigured -- job_context must do all the work
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
        job_id = await _drive_to_reserve_runtime(
            svc, tp_id=tp_id, rg_id=rg_id, admin_id=admin_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id, topic="full-loop-job",
        )

        svc.run_reserve_runtime_stage(
            job_id, admin_id=admin_id, train_blocks=_tiny_train_blocks(),
            validation_blocks=_tiny_train_blocks(seed=1), configuration_label="TEST_INTEGRATION_CONFIGURATION",
        )
        assert adapter._model is not None
        assert adapter.configuration_label == "TEST_INTEGRATION_CONFIGURATION"
        assert adapter._checkpoint_root == (
            api_app.state.settings.resolved_pretraining_dir / "mini_brain_training_jobs" / job_id
        )

        svc.run_start_training_stage(job_id, admin_id=admin_id)
        before = [p.clone() for p in adapter._model.parameters()]
        svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        after = list(adapter._model.parameters())
        assert any(not b.equal(a) for b, a in zip(before, after, strict=True)), "real weights must have changed"

        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)

        # -- checkpoint identity: the checkpoint row carries the same
        # Core Model Version this job trained, and the real files live
        # under the canonical pretraining checkpoint root. --
        checkpoints = svc.list_checkpoints(job_id)["items"]
        assert len(checkpoints) == 1
        checkpoint = checkpoints[0]
        assert checkpoint["is_metadata_only"] is False
        assert checkpoint["core_model_version_public_id"] == core_model_version_public_id

        real_checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        assert real_checkpoint_dir.is_relative_to(api_app.state.settings.resolved_pretraining_dir)
        assert (real_checkpoint_dir / "model_state.pt").is_file()

        # -- the same class/method InferenceRuntimeService.
        # load_instance_using_connection() itself calls -- proves file-
        # level, architecture-level compatibility even though this
        # checkpoint is not (yet -- see the Phase 2.7E report's
        # documented remaining gap) registered through the full
        # `pretraining_checkpoints`/release-governance chain. --
        manager = TrainingCheckpointManager(real_checkpoint_dir.parent, 500_000_000)
        assert manager.verify(real_checkpoint_dir) is True
        states = manager.load_states(real_checkpoint_dir)
        assert states["references"]["core_model_version_public_id"] == core_model_version_public_id
        assert states["references"]["configuration_label"] == "TEST_INTEGRATION_CONFIGURATION"

        from core_model.architecture.model import BrudForCausalLM

        model_config, version_row = svc.core_models.model_config_for_version(core_model_version_public_id)
        fresh_model = BrudForCausalLM(model_config)
        fresh_model.load_state_dict(states["model"])  # must not raise -- same real architecture
        assert version_row["public_id"] == core_model_version_public_id


_RESTART_PROBE_SCRIPT = """
import json, sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.repositories.core_models import CoreModelRepository
from backend.services.core_model_service import CoreModelService
from core_model.architecture.model import BrudForCausalLM
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

tmp_path = Path(sys.argv[2])
job_public_id = sys.argv[3]
settings = Settings(
    database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
    allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
    document_report_dir=tmp_path / "documents" / "reports",
    pretraining_dir=tmp_path / "core_models" / "pretraining",
    allow_external_storage=True, log_level="CRITICAL",
)
with database_connection(settings.resolved_database_path) as connection:
    job = connection.execute(
        "SELECT * FROM mini_brain_training_jobs WHERE public_id=?", (job_public_id,)
    ).fetchone()
    checkpoint = connection.execute(
        "SELECT * FROM mini_brain_training_checkpoints WHERE job_id=?", (job["id"],)
    ).fetchone()

core_model_version_public_id = job["core_model_version_public_id"]
core_models = CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)
model_config, version_row = core_models.model_config_for_version(core_model_version_public_id)

checkpoint_root = settings.resolved_pretraining_dir / "mini_brain_training_jobs" / job_public_id
checkpoint_dir = checkpoint_root / f"step-{checkpoint['step']:08d}-epoch-{checkpoint['epoch']:04d}"
manager = TrainingCheckpointManager(checkpoint_root, 500_000_000)
verified = manager.verify(checkpoint_dir)
states = manager.load_states(checkpoint_dir)
model = BrudForCausalLM(model_config)
model.load_state_dict(states["model"])

print(json.dumps({
    "job_core_model_version_public_id": core_model_version_public_id,
    "checkpoint_core_model_version_public_id": checkpoint["core_model_version_public_id"],
    "resolved_version_public_id": version_row["public_id"],
    "resolved_lifecycle_status": version_row["lifecycle_status"],
    "checkpoint_verified": verified,
    "checkpoint_references_core_model_version_public_id": states["references"].get("core_model_version_public_id"),
    "model_loaded": True,
}))
"""


class TestRestartSurvival:
    """Part 16: guards against the exact process-local-cache class of bug
    Phase 2.2 previously found. The producing process (this test) and the
    verifying process (a genuinely separate `subprocess.run` invocation,
    no shared Python interpreter, no shared import state, no shared
    in-memory object) only share the on-disk SQLite database and
    checkpoint files -- if identity only "worked" because of something
    cached in this test's own process, the subprocess would fail to
    reconstruct it."""

    async def test_h_identity_survives_a_genuinely_separate_process(
        self, api_app: FastAPI, tmp_path: Path,
    ) -> None:
        import json
        import subprocess
        import sys

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="restart-pkg")
        core_model_version_public_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="h")
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="h")

        adapter = TorchTrainingAdapter()
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
        job_id = await _drive_to_reserve_runtime(
            svc, tp_id=tp_id, rg_id=rg_id, admin_id=admin_id,
            core_model_version_public_id=core_model_version_public_id,
            dataset_version_public_id=dataset_version_public_id, topic="restart-job",
        )
        svc.run_reserve_runtime_stage(
            job_id, admin_id=admin_id, train_blocks=_tiny_train_blocks(),
            validation_blocks=_tiny_train_blocks(seed=1), configuration_label="TEST_INTEGRATION_CONFIGURATION",
        )
        svc.run_start_training_stage(job_id, admin_id=admin_id)
        svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)

        # -- everything above ran in THIS process; the DB path and
        # checkpoint files are the only things carried across. --
        repo_root = str(Path(__file__).resolve().parents[2])
        result = subprocess.run(
            [sys.executable, "-c", _RESTART_PROBE_SCRIPT, repo_root, str(tmp_path), job_id],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, result.stderr
        probe = json.loads(result.stdout.strip().splitlines()[-1])

        assert probe["job_core_model_version_public_id"] == core_model_version_public_id
        assert probe["checkpoint_core_model_version_public_id"] == core_model_version_public_id
        assert probe["resolved_version_public_id"] == core_model_version_public_id
        assert probe["resolved_lifecycle_status"] == "architecture_verified"
        assert probe["checkpoint_verified"] is True
        assert probe["checkpoint_references_core_model_version_public_id"] == core_model_version_public_id
        assert probe["model_loaded"] is True


class TestCrossVersionCheckpointMismatch:
    """Part 17-I: proves checkpoint identity is load-bearing, not
    decorative -- a real checkpoint trained under one Core Model Version
    must never silently load against a different, architecturally
    incompatible one."""

    async def test_i_checkpoint_rejects_loading_against_the_wrong_core_model_version(
        self, api_app: FastAPI, tmp_path: Path,
    ) -> None:
        from core_model.architecture.model import BrudForCausalLM

        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="mismatch-pkg")
        correct_id = _real_core_model_version(api_app.state.settings, admin_id, name_suffix="i-correct")
        # A second, real, architecture-verified version with a genuinely
        # different shape (double hidden_size/intermediate_size) -- not
        # the same config reused under a new name.
        wrong_id = _real_core_model_version(
            api_app.state.settings, admin_id, name_suffix="i-wrong",
            hidden_size=32, intermediate_size=64,
        )
        dataset_version_public_id = _real_dataset_version(api_app.state.settings, name_suffix="i")

        adapter = TorchTrainingAdapter()
        svc = MiniBrainTrainingEngineService(api_app.state.settings, adapters={"gpu": adapter})
        job_id = await _drive_to_reserve_runtime(
            svc, tp_id=tp_id, rg_id=rg_id, admin_id=admin_id,
            core_model_version_public_id=correct_id,
            dataset_version_public_id=dataset_version_public_id, topic="mismatch-job",
        )
        svc.run_reserve_runtime_stage(
            job_id, admin_id=admin_id, train_blocks=_tiny_train_blocks(),
            validation_blocks=_tiny_train_blocks(seed=1), configuration_label="TEST_INTEGRATION_CONFIGURATION",
        )
        svc.run_start_training_stage(job_id, admin_id=admin_id)
        svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)

        real_checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        manager = TrainingCheckpointManager(real_checkpoint_dir.parent, 500_000_000)
        states = manager.load_states(real_checkpoint_dir)

        # Load against the *other* real, architecture-verified version's
        # own real config -- genuinely incompatible (different hidden_size/
        # intermediate_size), not a synthetically-mutated one.
        wrong_config, _wrong_row = svc.core_models.model_config_for_version(wrong_id)
        mismatched_model = BrudForCausalLM(wrong_config)
        with pytest.raises((RuntimeError, ValueError)):
            mismatched_model.load_state_dict(states["model"])
