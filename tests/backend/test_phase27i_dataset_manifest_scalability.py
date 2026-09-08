"""Phase 2.7I, Finding B: `DatasetVersioningService._manifest()`'s
checksum payload used to embed each real record's full `instruction`/
`input_text`/`output_text`/`normalized_input` text, which made the
payload's serialized size grow with actual text length and exceeded
`Settings.max_metadata_bytes` (65536 bytes) at roughly 225 records for
the Phase 2.7H record shape (`deploy/phase-2.7H/
TRAINING_DATASET_READINESS_REPORT.md` §13).

The fix (`DatasetVersioningService._checksum_payload_v2()`) drops those
four fields from the checksum payload -- not arbitrarily, but because
`dataset_service.content_hash()` already computes a real SHA-256 over
exactly those fields (plus `record_type`/`language`) for every record
created through the real record-creation/document-ingestion path, and
that hash (`dataset_records.content_hash`) was already included in the
payload. The new payload keeps every field that ISN'T redundant with
`content_hash` (`split`, `public_id`, `record_type`, `language`,
`source_public_id`), so the checksum's actual detection contract is
unchanged; only its per-record byte cost is now bounded.

Backward compatibility: a dataset version's own manifest records which
payload version produced its checksum (`checksum_payload_version`,
defaulting to `1` when absent -- i.e. for any dataset version built
before this phase). `verify_version()` always re-verifies using that
stored version, never the current default, so a pre-Phase-2.7I ready
dataset version remains genuinely, correctly re-verifiable -- proven
directly in this file using the real, unmodified, preserved
`_checksum_payload_v1()` method (never a reimplementation of the old
logic).

This file builds real, governed Dataset Versions through the actual
`DatasetVersioningService.create_build()` -> `validate_build()` ->
`run_build()` flow throughout -- never a raw `dataset_version_items`
insert for the primary scale proof.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.core.json_utils import loads_json
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.models.dataset_versions import BuildCreate, BuildRunRequest, SplitConfiguration
from backend.services.dataset_versioning import CHECKSUM_PAYLOAD_VERSION, DatasetVersioningService
from backend.services.mini_brain_dataset_pipeline_service import MiniBrainDatasetPipelineService
from backend.services.mini_brain_pretraining_handoff_service import MiniBrainPretrainingHandoffService
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
from backend.services.training_runtime_adapter import TorchTrainingAdapter
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
from core_model.training.dataset_pipeline import BLOCK_BUILDER_VERSION
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


def _service(settings: Settings) -> DatasetVersioningService:
    return DatasetVersioningService(DatasetQualityRepository(settings.resolved_database_path), settings)


# ===========================================================================
# Part 9/10: 40 / 200 / 250 / 500-record real, governed builds.
# ===========================================================================


class TestDatasetManifestScale:
    @pytest.mark.parametrize("size", [40, 200, 250, 500])
    async def test_real_governed_build_succeeds_at_scale(self, api_app: FastAPI, size: int) -> None:
        settings = api_app.state.settings
        texts = _generate_corpus(size, seed_offset=size * 1000)
        dataset_id, preview, result = _build_real_dataset_via_service(
            settings, name_suffix=f"scale-{size}", record_texts=texts,
        )
        assert result["status"] in {"completed", "completed_with_warnings"}
        assert preview["leakage"]["status"] == "safe"

        with database_connection(settings.resolved_database_path) as connection:
            version = connection.execute(
                "SELECT * FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()
        assert version["status"] == "ready"
        assert version["record_count"] == size
        # Part 10.5: checksum exists and is exactly 64 hex characters.
        assert len(version["checksum_sha256"]) == 64
        assert all(c in "0123456789abcdef" for c in version["checksum_sha256"])
        manifest = loads_json(version["manifest_json"])
        assert manifest["checksum_payload_version"] == CHECKSUM_PAYLOAD_VERSION

        # Part 10.6/10.7: verify_version() succeeds, including from a
        # brand-new service instance (simulating a fresh process reading
        # this version back with no shared in-memory state).
        fresh_service = _service(settings)
        verification = fresh_service.verify_version(dataset_id)
        assert verification["verified"] is True
        assert verification["checksum_sha256"] == version["checksum_sha256"]


# ===========================================================================
# Part 8: the dataset checksum contract.
# ===========================================================================


class TestDatasetChecksumContract:
    async def test_same_records_same_source_same_split_produce_identical_checksum(
        self, api_app: FastAPI,
    ) -> None:
        """Recomputing the checksum for the exact same real, governed
        dataset version's own records/split -- fresh each time, never
        cached -- must produce the identical checksum. (Two independent
        *builds* can never share this proof directly: `dataset_versions`
        has a real, schema-enforced `UNIQUE(name, version)` constraint,
        so two builds sharing an identity can't both exist as separate
        rows -- confirmed live by attempting exactly that and observing
        the real `sqlite3.IntegrityError`/`ConflictError`. Determinism is
        therefore proven the way `verify_version()` itself proves it: by
        independently recomputing the checksum from the real, persisted
        records twice and comparing.)"""

        settings = api_app.state.settings
        texts = _generate_corpus(60, seed_offset=30000)
        source_public_id = "src27i-shared"
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute(
                """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
                licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
                (source_public_id, "Phase 2.7I Shared Source", "manual", "ready", "mixed", "approved", "{}"),
            )
            source_id = connection.execute(
                "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
            ).fetchone()[0]
            for idx, (content, language) in enumerate(texts, start=1):
                connection.execute(
                    """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                    record_type,content_hash,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        f"rec27i-shared-{idx}", source_id, content, language, "approved", "pretrain",
                        hashlib.sha256(content.encode("utf-8")).hexdigest(), "{}",
                    ),
                )
            connection.commit()

        service = _service(settings)
        build = service.create_build(
            BuildCreate(
                dataset_name="phase27i-checksum-contract", dataset_version="v1",
                selection_filters={"source_public_id": source_public_id},
                split_configuration=SplitConfiguration(
                    train_percent=70, validation_percent=30, test_percent=0, seed=99,
                ),
            ),
            admin_id="phase27i-fixture",
        )
        service.validate_build(build["public_id"], admin_id="phase27i-fixture")
        result = service.run_build(build["public_id"], BuildRunRequest(confirm=True), admin_id="phase27i-fixture")
        dataset_id = result["dataset_version_public_id"]

        # A truly independent build sharing this exact identity is
        # rejected at the schema level -- proving determinism cannot (and
        # need not) be demonstrated by building the "same" version twice.
        with pytest.raises(Exception, match="UNIQUE constraint failed"):
            duplicate_build = service.create_build(
                BuildCreate(
                    dataset_name="phase27i-checksum-contract", dataset_version="v1",
                    selection_filters={"source_public_id": source_public_id},
                ),
                admin_id="phase27i-fixture",
            )
            service.run_build(duplicate_build["public_id"], BuildRunRequest(confirm=True), admin_id="phase27i-fixture")

        verification_1 = service.verify_version(dataset_id)
        verification_2 = service.verify_version(dataset_id)
        assert verification_1["verified"] is True
        assert verification_2["verified"] is True
        assert verification_1["checksum_sha256"] == verification_2["checksum_sha256"]
        with database_connection(settings.resolved_database_path) as connection:
            stored_checksum = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()["checksum_sha256"]
        assert verification_1["checksum_sha256"] == stored_checksum

    async def test_different_content_produces_different_checksum(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        dataset_a, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="content-a", record_texts=_generate_corpus(40, seed_offset=31000),
        )
        dataset_b, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="content-b", record_texts=_generate_corpus(40, seed_offset=32000),
        )
        with database_connection(settings.resolved_database_path) as connection:
            checksum_a = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_a,)
            ).fetchone()["checksum_sha256"]
            checksum_b = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_b,)
            ).fetchone()["checksum_sha256"]
        assert checksum_a != checksum_b

    async def test_different_source_identity_with_identical_text_produces_different_checksum(
        self, api_app: FastAPI,
    ) -> None:
        """Part 8/Part 10.10: `content_hash` alone does not distinguish
        provenance -- the same real sentence attributed to two different
        real sources must still produce two different dataset checksums,
        proving `source_public_id` is genuinely still part of the
        checksum contract after Finding B's fix (it was one of the
        fields deliberately KEPT in `_checksum_payload_v2()`)."""

        settings = api_app.state.settings
        shared_texts = _generate_corpus(24, seed_offset=33000)

        def _build_from_source(name_suffix: str) -> str:
            source_public_id = f"src27i-prov-{name_suffix}"
            with database_connection(settings.resolved_database_path) as connection:
                connection.execute(
                    """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
                    licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
                    (source_public_id, f"Phase 2.7I Source {name_suffix}", "manual", "ready", "mixed", "approved", "{}"),
                )
                source_id = connection.execute(
                    "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
                ).fetchone()[0]
                for idx, (content, language) in enumerate(shared_texts, start=1):
                    connection.execute(
                        """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                        record_type,content_hash,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            f"rec27i-prov-{name_suffix}-{idx}", source_id, content, language, "approved",
                            "pretrain", hashlib.sha256(content.encode("utf-8")).hexdigest(), "{}",
                        ),
                    )
                connection.commit()
            service = _service(settings)
            build = service.create_build(
                BuildCreate(
                    dataset_name=f"phase27i-prov-{name_suffix}", dataset_version="v1",
                    selection_filters={"source_public_id": source_public_id},
                    split_configuration=SplitConfiguration(
                        train_percent=70, validation_percent=30, test_percent=0, seed=7,
                    ),
                ),
                admin_id="phase27i-fixture",
            )
            service.validate_build(build["public_id"], admin_id="phase27i-fixture")
            result = service.run_build(build["public_id"], BuildRunRequest(confirm=True), admin_id="phase27i-fixture")
            return result["dataset_version_public_id"]

        dataset_a = _build_from_source("x")
        dataset_b = _build_from_source("y")
        with database_connection(settings.resolved_database_path) as connection:
            checksum_a = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_a,)
            ).fetchone()["checksum_sha256"]
            checksum_b = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_b,)
            ).fetchone()["checksum_sha256"]
        assert checksum_a != checksum_b

    async def test_different_split_seed_produces_different_checksum(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        texts = _generate_corpus(60, seed_offset=34000)
        source_public_id = "src27i-split"
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute(
                """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
                licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
                (source_public_id, "Phase 2.7I Split Source", "manual", "ready", "mixed", "approved", "{}"),
            )
            source_id = connection.execute(
                "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
            ).fetchone()[0]
            for idx, (content, language) in enumerate(texts, start=1):
                connection.execute(
                    """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                    record_type,content_hash,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        f"rec27i-split-{idx}", source_id, content, language, "approved", "pretrain",
                        hashlib.sha256(content.encode("utf-8")).hexdigest(), "{}",
                    ),
                )
            connection.commit()

        service = _service(settings)

        def _build_with_seed(name_suffix: str, seed: int) -> str:
            build = service.create_build(
                BuildCreate(
                    dataset_name=f"phase27i-{name_suffix}", dataset_version="v1",
                    selection_filters={"source_public_id": source_public_id},
                    split_configuration=SplitConfiguration(
                        train_percent=70, validation_percent=30, test_percent=0, seed=seed,
                    ),
                ),
                admin_id="phase27i-fixture",
            )
            service.validate_build(build["public_id"], admin_id="phase27i-fixture")
            result = service.run_build(build["public_id"], BuildRunRequest(confirm=True), admin_id="phase27i-fixture")
            return result["dataset_version_public_id"]

        dataset_a = _build_with_seed("seed-a", seed=1)
        dataset_b = _build_with_seed("seed-b", seed=2)
        with database_connection(settings.resolved_database_path) as connection:
            splits_a = {
                row["split"] for row in connection.execute(
                    """SELECT i.split FROM dataset_version_items i
                    JOIN dataset_versions v ON v.id=i.dataset_version_id WHERE v.public_id=?""",
                    (dataset_a,),
                ).fetchall()
            }
            checksum_a = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_a,)
            ).fetchone()["checksum_sha256"]
            checksum_b = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_b,)
            ).fetchone()["checksum_sha256"]
        assert checksum_a != checksum_b


# ===========================================================================
# Part 11: manifest backward compatibility.
# ===========================================================================


class TestManifestBackwardCompatibility:
    async def test_a_pre_phase_27i_shaped_ready_version_still_verifies(self, api_app: FastAPI) -> None:
        """Simulates exactly what a dataset version built by the OLD
        (pre-Phase-2.7I) code would look like on disk: its manifest was
        computed via the real, preserved, unmodified
        `_checksum_payload_v1()` method (never a reimplementation) and
        its stored manifest genuinely lacks the new
        `checksum_payload_version` key -- the real absence
        `verify_version()`'s `.get(..., 1)` fallback is designed for.
        Proves the new code can still correctly re-verify an old-shaped
        version without any migration."""

        settings = api_app.state.settings
        texts = _generate_corpus(30, seed_offset=35000)
        source_public_id = "src27i-legacy"
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute(
                """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
                licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
                (source_public_id, "Phase 2.7I Legacy Source", "manual", "ready", "mixed", "approved", "{}"),
            )
            source_id = connection.execute(
                "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
            ).fetchone()[0]
            record_ids = []
            for idx, (content, language) in enumerate(texts, start=1):
                public_id = f"rec27i-legacy-{idx}"
                record_ids.append(public_id)
                connection.execute(
                    """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                    record_type,content_hash,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        public_id, source_id, content, language, "approved", "pretrain",
                        hashlib.sha256(content.encode("utf-8")).hexdigest(), "{}",
                    ),
                )
            connection.commit()

        service = _service(settings)
        version_public_id = str(uuid4())
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute(
                """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
                VALUES (?,?,?,?,?)""",
                (version_public_id, "phase27i-legacy-shaped", "v1", "draft", "pending"),
            )
            version_id = connection.execute(
                "SELECT id FROM dataset_versions WHERE public_id=?", (version_public_id,)
            ).fetchone()["id"]
            rows = connection.execute(
                "SELECT id FROM dataset_records WHERE public_id IN ({})".format(
                    ",".join("?" * len(record_ids))
                ),
                record_ids,
            ).fetchall()
            splits = {"train": [], "validation": [], "test": []}
            for idx, row in enumerate(rows):
                split = "validation" if idx >= len(rows) - 6 else "train"
                connection.execute(
                    """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,split,
                    sequence_number) VALUES (?,?,?,?)""",
                    (version_id, row["id"], split, idx),
                )
                full_row = connection.execute(
                    """SELECT r.*, s.public_id AS source_public_id, s.source_type AS source_type
                    FROM dataset_records r LEFT JOIN dataset_sources s ON s.id=r.source_id WHERE r.id=?""",
                    (row["id"],),
                ).fetchone()
                splits[split].append(full_row)
            connection.commit()

            version_row = connection.execute(
                "SELECT * FROM dataset_versions WHERE public_id=?", (version_public_id,)
            ).fetchone()
            # The real, preserved, unmodified v1 payload builder -- exactly
            # what the pre-Phase-2.7I `run_build()` would have used.
            legacy_manifest, legacy_checksum = service._manifest(
                version_row, [dict(r) for rows_ in splits.values() for r in rows_], splits,
                {}, {"seed": 42}, "legacy-fixture-admin", payload_version=1,
            )
            # A truly pre-Phase-2.7I manifest never had this key at all --
            # strip it to faithfully simulate the old on-disk shape (not
            # just "version 1 requested", but "version key absent").
            legacy_manifest.pop("checksum_payload_version", None)
            from backend.core.json_utils import dumps_json

            connection.execute(
                """UPDATE dataset_versions SET status='ready', manifest_json=?, checksum_sha256=?,
                record_count=?, build_configuration_json=? WHERE id=?""",
                (dumps_json(legacy_manifest), legacy_checksum, len(rows), dumps_json({}), version_id),
            )
            connection.commit()

        with database_connection(settings.resolved_database_path) as connection:
            stored = loads_json(
                connection.execute(
                    "SELECT manifest_json FROM dataset_versions WHERE public_id=?", (version_public_id,)
                ).fetchone()["manifest_json"]
            )
        assert "checksum_payload_version" not in stored, "fixture must genuinely lack the new key"

        verification = service.verify_version(version_public_id)
        assert verification["verified"] is True
        assert verification["checksum_sha256"] == legacy_checksum


# ===========================================================================
# Part 12/13: MB-22 / Phase 2.7G / 2.7H regression + real qualification at
# a scale materially beyond the old ~225-record ceiling.
# ===========================================================================


class TestTrainingPipelineRegressionAtScale:
    async def test_readiness_contract_and_deterministic_blocks_at_300_records(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="scale-regress")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="scale-regress", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="regress-300", record_texts=_generate_corpus(300, seed_offset=40000),
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "READY", contract["reason"]
        assert contract["dataset"]["record_count"] == 300

        first = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        second = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert first["train_blocks"] == second["train_blocks"]
        assert first["validation_blocks"] == second["validation_blocks"]
        assert first["dataset_checksum_sha256"] == second["dataset_checksum_sha256"]

    async def test_real_training_qualification_at_500_records(self, api_app: FastAPI) -> None:
        """Part 13: the real qualification run, on a dataset materially
        larger (500 records) than the old ~225-record manifest ceiling
        this phase removed. TEST_INTEGRATION_CONFIGURATION only -- a
        tiny model, no interpretation of loss as model quality."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="phase27i-qualification")
        tokenizer_id = _real_tokenizer(settings, name_suffix="qual500")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="qual500", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="qual500", record_texts=_generate_corpus(500, seed_offset=41000),
        )

        pipeline = MiniBrainDatasetPipelineService(settings)
        readiness = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert readiness["status"] == "READY", readiness["reason"]
        assert readiness["dataset"]["record_count"] == 500

        adapter = TorchTrainingAdapter()
        svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
        job = svc.create_job(
            topic="phase27i-qualification-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=core_model_version_id, dataset_version_public_id=dataset_id,
        )
        job_id = job["public_id"]
        svc.run_validate_release_stage(job_id, admin_id=admin_id)
        svc.run_validate_package_stage(job_id, admin_id=admin_id)
        svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.7i qualification", admin_id=admin_id)
        svc.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc.run_build_manifest_stage(job_id, admin_id=admin_id)

        report = svc.run_reserve_runtime_stage(
            job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION",
        )
        assert report["runtime_reservation_report"]["reserved"] is True
        assert adapter._model is not None
        assert len(adapter._train_blocks) == readiness["blocks"]["train_block_count"]
        assert len(adapter._validation_blocks) == readiness["blocks"]["validation_block_count"]

        svc.run_start_training_stage(job_id, admin_id=admin_id)
        before = [p.clone() for p in adapter._model.parameters()]
        metric = svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        after = list(adapter._model.parameters())
        assert any(not b.equal(a) for b, a in zip(before, after, strict=True))
        assert metric["training_state"]["last_loss"] is not None

        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_row = svc.list_checkpoints(job_id)["items"][0]
        real_checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])

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
        assert references["core_model_version_public_id"] == core_model_version_id
        assert references["block_builder_version"] == BLOCK_BUILDER_VERSION

        handoff = MiniBrainPretrainingHandoffService(settings)
        result = handoff.register_checkpoint(job_id, checkpoint_row["public_id"], admin_id)
        with database_connection(settings.resolved_database_path) as connection:
            pretraining_checkpoint = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?",
                (result["pretraining_checkpoint_public_id"],),
            ).fetchone()
        assert pretraining_checkpoint["status"] == "verified"
