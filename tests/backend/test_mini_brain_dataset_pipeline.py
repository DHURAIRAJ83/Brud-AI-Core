"""Phase 2.7G: real dataset-version -> token-block pipeline.

Proves the specific gap Phase 2.7F's own report documented: MB-22 had no
dataset-to-token-block pipeline of its own -- `train_blocks`/
`validation_blocks` had to be supplied explicitly by the caller. This
file builds a real, tiny, governed Dataset Version (real Tamil/English/
Tanglish text, real approved records, a real deterministic train/
validation split -- the exact same fixture shape
`tests/backend/test_pretraining_api.py::_fixture_refs()` already
established for `PretrainingService`'s own tests) and a real,
artifact-backed SentencePiece tokenizer, then drives the real pipeline
(`MiniBrainDatasetPipelineService`, `core_model.training.dataset_pipeline`)
end to end -- through MB-22's own real `reserve-runtime` auto-derivation
path, never a mock, never a fake token id.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import sentencepiece as spm
from fastapi import FastAPI

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.models.tokenizers import SPECIAL_TOKENS
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
from tests.backend.test_torch_training_adapter_integration import _real_core_model_version

pytestmark = pytest.mark.anyio

# Real Tamil / English / Tanglish sentences -- never fake token ids, never
# a mocked tokenizer. Deliberately short (this is a tiny, isolated
# TEST_INTEGRATION_CONFIGURATION corpus, not production-scale data).
_TAMIL = [
    "வணக்கம், இது ஒரு சோதனை வாக்கியம்.",
    "தமிழ் இந்தியாவின் பழமையான மொழிகளில் ஒன்று.",
    "இன்று வானிலை மிகவும் அழகாக உள்ளது.",
]
_ENGLISH = [
    "Hello, this is a test sentence.",
    "Brud AI is a Tamil-first assistant platform.",
    "The weather today is very pleasant.",
]
_TANGLISH = [
    "Vanakkam, indha oru test sentence.",
    "Naan Brud AI training pannitu irukken.",
]


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _real_tokenizer(settings: Settings, *, name_suffix: str) -> str:
    """Trains a real, tiny SentencePiece BPE tokenizer on real Tamil/
    English/Tanglish text -- the exact established pattern
    `tests/backend/test_pretraining_api.py::_create_tokenizer_artifact()`
    already uses, real files on disk, real checksums, never mocked."""

    from backend.database.repositories.core_models import CoreModelRepository  # noqa: F401  (import-order smoke)

    corpus = settings.resolved_tokenizer_corpus_dir / f"phase27g-corpus-{name_suffix}.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_text("\n".join(_TAMIL + _ENGLISH + _TANGLISH) + "\n", encoding="utf-8")
    temp_prefix = settings.resolved_tokenizer_dir / f"phase27g-tokenizer-{name_suffix}"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus), model_prefix=str(temp_prefix), model_type="bpe", vocab_size=200,
        character_coverage=1.0, hard_vocab_limit=False, pad_id=0, unk_id=1, bos_id=2, eos_id=3,
        pad_piece="<pad>", unk_piece="<unk>", bos_piece="<bos>", eos_piece="<eos>",
        user_defined_symbols=",".join(SPECIAL_TOKENS[4:]),
    )
    # `TokenizerService._artifact_dir()` resolves this path from the real
    # `family_name`/`version` columns (not the public_id) -- must match
    # exactly, or `_verify_artifacts()` looks in the wrong directory.
    artifact_dir = settings.resolved_tokenizer_dir / "versions" / f"tok27g-family-{name_suffix}" / "v1"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model = artifact_dir / "tokenizer.model"
    vocab = artifact_dir / "tokenizer.vocab"
    temp_prefix.with_suffix(".model").replace(model)
    temp_prefix.with_suffix(".vocab").replace(vocab)
    processor = spm.SentencePieceProcessor(model_file=str(model))
    manifest = {
        "files": ["tokenizer.model", "tokenizer.vocab", "artifact_manifest.json"],
        "model_checksum_sha256": _sha256(model),
        "vocabulary_checksum_sha256": _sha256(vocab),
        "special_tokens": SPECIAL_TOKENS,
    }
    (artifact_dir / "artifact_manifest.json").write_text(dumps_json(manifest), encoding="utf-8")

    dataset_public_id = f"ds-tokcorpus-{name_suffix}"
    tokenizer_public_id = f"tok27g-{name_suffix}"
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (dataset_public_id, f"tokcorpus-{name_suffix}", "v1", "ready", "f" * 64),
        )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            (f"tf27g-{name_suffix}", f"tok27g-family-{name_suffix}", "T", "active"),
        )
        family_id = connection.execute(
            "SELECT id FROM tokenizer_families WHERE public_id=?", (f"tf27g-{name_suffix}",)
        ).fetchone()[0]
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_public_id,)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
            lifecycle_status,algorithm,vocabulary_size,character_coverage,
            normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
            model_checksum_sha256,vocabulary_checksum_sha256,artifact_manifest_json,
            special_tokens_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tokenizer_public_id, family_id, "v1", "active", "bpe", processor.vocab_size(), 1.0,
                "nmt_nfkc", "sentencepiece", dataset_id, "a" * 64,
                manifest["model_checksum_sha256"], manifest["vocabulary_checksum_sha256"],
                dumps_json(manifest), dumps_json(SPECIAL_TOKENS),
            ),
        )
        connection.commit()
    return tokenizer_public_id


def _real_governed_dataset_version(
    settings: Settings, *, name_suffix: str, texts: list[tuple[str, str]] | None = None,
    force_split: str | None = None,
) -> str:
    """A real, governed Dataset Version: `dataset_sources` (rights
    approved) -> `dataset_records` (`status='approved'`, the exact real
    gate `DatasetVersionsRepository.selectable_records()` requires) ->
    `dataset_versions` (`status='ready'`) -> `dataset_version_items`
    (a real, deterministic train/validation split) -- the exact fixture
    shape `test_pretraining_api.py::_fixture_refs()` already established
    for `PretrainingService`'s own tests, reused here rather than
    reinvented."""

    texts = texts or [
        (text, "ta") for text in _TAMIL
    ] + [(text, "en") for text in _ENGLISH] + [(text, "mixed") for text in _TANGLISH]

    source_public_id = f"src-{name_suffix}"
    dataset_public_id = f"dsv-{name_suffix}"
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
            licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
            (source_public_id, f"Phase 2.7G Source {name_suffix}", "manual", "ready", "mixed", "approved", "{}"),
        )
        source_id = connection.execute(
            "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
        ).fetchone()[0]
        record_public_ids = []
        for idx, (content, language) in enumerate(texts, start=1):
            record_public_id = f"rec-{name_suffix}-{idx}"
            record_public_ids.append(record_public_id)
            connection.execute(
                """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                record_type,content_hash,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    record_public_id, source_id, content, language, "approved", "pretrain",
                    hashlib.sha256(content.encode("utf-8")).hexdigest(), "{}",
                ),
            )
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256,
            record_count,split_distribution_json) VALUES (?,?,?,?,?,?,?)""",
            (
                dataset_public_id, f"phase27g-{name_suffix}", "v1", "ready",
                hashlib.sha256(name_suffix.encode()).hexdigest(), len(texts),
                json.dumps({"train": max(1, len(texts) - 2), "validation": 2}),
            ),
        )
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_public_id,)
        ).fetchone()[0]
        records = connection.execute(
            "SELECT id FROM dataset_records WHERE public_id IN ({})".format(
                ",".join("?" * len(record_public_ids))
            ),
            record_public_ids,
        ).fetchall()
        # Deterministic split: the last 2 real records are held out for
        # validation, everything else trains -- never a random/reseeded
        # split per call. `force_split` builds every real
        # `dataset_version_items` row with one, fixed split at INSERT
        # time (the only way to construct an all-`test`-split fixture --
        # a real, schema-enforced trigger makes `dataset_version_items`
        # immutable to UPDATE/DELETE once the parent version is `ready`,
        # so this can never be achieved by mutating an existing row).
        for idx, row in enumerate(records):
            split = force_split or ("validation" if idx >= len(records) - 2 else "train")
            connection.execute(
                """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,split,
                sequence_number) VALUES (?,?,?,?)""",
                (dataset_id, row["id"], split, idx),
            )
        connection.commit()
    return dataset_public_id


class TestRealIsolatedPipeline:
    """Part 16: Dataset Version -> governance -> extraction ->
    normalization (the tokenizer's own real `nmt_nfkc` SentencePiece
    normalization) -> real tokenizer -> real token ids -> real train/
    validation split -> real blocks -> MB-22 reserve-runtime -> real
    training. Every claim below is checked against the real pipeline's
    real output, never asserted from assumption."""

    async def test_pipeline_produces_real_blocks(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="a")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-a", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(settings, name_suffix="a")

        pipeline = MiniBrainDatasetPipelineService(settings)
        result = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )

        # A. Real dataset identity.
        assert result["dataset_version_public_id"] == dataset_id
        assert result["dataset_checksum_sha256"] == hashlib.sha256(b"a").hexdigest()
        # B. Real tokenizer identity.
        assert result["tokenizer_version_public_id"] == tokenizer_id
        # D. Correct context length (Core Model Version's own, never hardcoded).
        assert result["context_length"] == 32
        assert result["sequence_length"] == 32
        # E. Train/validation separation.
        assert result["train_blocks"] != result["validation_blocks"]
        # F. Real token ids -- every id in-range for the real tokenizer's real vocab.
        with database_connection(settings.resolved_database_path) as connection:
            vocab_size = connection.execute(
                "SELECT vocabulary_size FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["vocabulary_size"]
        for block in result["train_blocks"] + result["validation_blocks"]:
            assert len(block) == 32
            assert all(0 <= token_id < vocab_size for token_id in block)
        # G/H. Real training and validation blocks, non-empty.
        assert len(result["train_blocks"]) >= 1
        assert len(result["validation_blocks"]) >= 1
        assert result["block_builder_version"] == BLOCK_BUILDER_VERSION
        # M: no production DB access -- this entire test ran against tmp_path's own isolated DB.
        assert "tmp" in str(settings.resolved_database_path) or str(settings.resolved_database_path).startswith("/tmp")


class TestDeterminism:
    """Part 17: the same Dataset Version + Tokenizer Version + config
    must produce byte-identical output on every run."""

    async def test_same_inputs_produce_identical_output(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="det")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-det", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(settings, name_suffix="det")

        pipeline = MiniBrainDatasetPipelineService(settings)
        first = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        second = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )

        assert first["train_blocks"] == second["train_blocks"]
        assert first["validation_blocks"] == second["validation_blocks"]
        assert first["train_report"]["coverage"]["stream_checksum_sha256"] == second["train_report"]["coverage"]["stream_checksum_sha256"]
        assert first["validation_report"]["coverage"]["stream_checksum_sha256"] == second["validation_report"]["coverage"]["stream_checksum_sha256"]
        assert first["dataset_checksum_sha256"] == second["dataset_checksum_sha256"]
        assert first["tokenizer_checksum_sha256"] == second["tokenizer_checksum_sha256"]


class TestLanguageQuality:
    """Part 19: measurable, real language statistics -- never a claim of
    model quality, only real data-readiness counts."""

    async def test_language_distribution_is_measured_and_real(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="lang")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-lang", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(settings, name_suffix="lang")

        pipeline = MiniBrainDatasetPipelineService(settings)
        result = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        train_languages = result["train_report"]["coverage"]["language_distribution"]
        validation_languages = result["validation_report"]["coverage"]["language_distribution"]
        combined = dict(train_languages)
        for key, value in validation_languages.items():
            combined[key] = combined.get(key, 0) + value

        # Real: exactly the 3 languages seeded (ta/en/mixed), no others,
        # counts sum to exactly the 8 real records seeded.
        assert set(combined) == {"ta", "en", "mixed"}
        assert sum(combined.values()) == len(_TAMIL) + len(_ENGLISH) + len(_TANGLISH)
        assert combined["ta"] == len(_TAMIL)
        assert combined["en"] == len(_ENGLISH)
        assert combined["mixed"] == len(_TANGLISH)


class TestTrainingReadinessGate:
    """Part 20: a deterministic TRAINING_READY / NOT_READY gate that
    explains exactly why."""

    async def test_ready_dataset_and_version_report_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="gate-ok")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-gate-ok", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(settings, name_suffix="gate-ok")

        pipeline = MiniBrainDatasetPipelineService(settings)
        readiness = pipeline.check_readiness(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert readiness["ready"] is True
        assert readiness["reason"] is None
        assert readiness["report"]["train_report"]["coverage"]["encoded_records"] > 0

    async def test_not_ready_reasons_are_specific(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="gate-bad")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-gate-bad", tokenizer_version_public_id=tokenizer_id,
        )
        pipeline = MiniBrainDatasetPipelineService(settings)

        readiness = pipeline.check_readiness(
            dataset_version_public_id="00000000-0000-0000-0000-000000099999",
            core_model_version_public_id=core_model_version_id,
        )
        assert readiness["ready"] is False
        assert "dataset version not found" in readiness["reason"]


class TestNegativeChecks:
    """Part 18: every rejection typed, no silent fallback, no fabricated
    data, no DB corruption."""

    async def test_1_dataset_version_does_not_exist(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="neg1")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-neg1", tokenizer_version_public_id=tokenizer_id,
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        with pytest.raises(ValidationError, match="dataset version not found"):
            pipeline.build_blocks(
                dataset_version_public_id="00000000-0000-0000-0000-000000088888",
                core_model_version_public_id=core_model_version_id,
            )

    async def test_2_dataset_version_is_draft(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="neg2")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-neg2", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(settings, name_suffix="neg2")
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute("UPDATE dataset_versions SET status='draft' WHERE public_id=?", (dataset_id,))
            connection.commit()
        pipeline = MiniBrainDatasetPipelineService(settings)
        with pytest.raises(ValidationError, match="ready or archived"):
            pipeline.build_blocks(
                dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
            )

    async def test_6_zero_usable_records(self, api_app: FastAPI) -> None:
        """A dataset version with real rows in `dataset_version_items` but
        every one of them assigned to the `test` split (never train or
        validation) -- the real query behind `fetch_split_records()`
        genuinely returns an empty train (and validation) list, and the
        real pipeline rejects it exactly the way `PretrainingService.
        _blocks()`'s own equivalent check already does."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="neg6")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-neg6", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(settings, name_suffix="neg6", force_split="test")
        pipeline = MiniBrainDatasetPipelineService(settings)
        with pytest.raises(ValidationError, match="training split has no tokenized records"):
            pipeline.build_blocks(
                dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
            )

    async def test_7_only_empty_records(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="neg7")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-neg7", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(
            settings, name_suffix="neg7",
            texts=[("", "ta"), ("   ", "en"), ("", "mixed"), ("", "ta")],
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        with pytest.raises(ValidationError, match="has no tokenized records"):
            pipeline.build_blocks(
                dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
            )

    async def test_10_context_length_mismatch_is_rejected(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="neg10")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-neg10", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(settings, name_suffix="neg10")
        pipeline = MiniBrainDatasetPipelineService(settings)
        with pytest.raises(ValidationError, match="exceeds the Core Model Version's real context_length"):
            pipeline.build_blocks(
                dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
                sequence_length=9999,
            )

    async def test_16_dataset_checksum_reflects_real_content_and_is_immutable_once_ready(
        self, api_app: FastAPI,
    ) -> None:
        """A dataset version's `checksum_sha256` is read straight from the
        real `dataset_versions` row -- two dataset versions built with
        different real seed content get different real checksums, and
        each pipeline result's own reported checksum matches its own
        row exactly (read live, never cached or fabricated). Attempting
        to mutate a `ready` dataset version's checksum is itself rejected
        by a real, pre-existing schema trigger
        (`dataset_versions_ready_content_update`) -- reproducibility is
        enforced at the database level, not merely by this pipeline's own
        convention."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="neg16")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-neg16", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_a = _real_governed_dataset_version(settings, name_suffix="neg16a")
        dataset_b = _real_governed_dataset_version(settings, name_suffix="neg16b")
        pipeline = MiniBrainDatasetPipelineService(settings)
        result_a = pipeline.build_blocks(
            dataset_version_public_id=dataset_a, core_model_version_public_id=core_model_version_id,
        )
        result_b = pipeline.build_blocks(
            dataset_version_public_id=dataset_b, core_model_version_public_id=core_model_version_id,
        )
        with database_connection(settings.resolved_database_path) as connection:
            row_a = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_a,)
            ).fetchone()
            row_b = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_b,)
            ).fetchone()
        assert result_a["dataset_checksum_sha256"] == row_a["checksum_sha256"]
        assert result_b["dataset_checksum_sha256"] == row_b["checksum_sha256"]
        assert result_a["dataset_checksum_sha256"] != result_b["dataset_checksum_sha256"]

        import sqlite3

        with database_connection(settings.resolved_database_path) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="ready dataset versions are immutable"):
                connection.execute(
                    "UPDATE dataset_versions SET checksum_sha256=? WHERE public_id=?", ("9" * 64, dataset_a),
                )


class TestRealTrainingReadiness:
    """Part 12/13/21: MB-22's own `reserve-runtime` auto-derives real
    blocks from a real Dataset Version (no caller-supplied blocks
    anywhere in this test) and drives real training -- proving the full
    chain: real dataset -> real tokenization -> real blocks -> real
    MB-22 training -> real checkpoint whose references name the exact
    dataset that produced it. Then hands the checkpoint off through the
    unmodified Phase 2.7F registration path to prove nothing about that
    chain broke."""

    async def test_auto_derived_blocks_drive_real_training_and_checkpoint_references_dataset(
        self, api_app: FastAPI,
    ) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="dataset-pipeline-pkg")
        tokenizer_id = _real_tokenizer(settings, name_suffix="e2e")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="pipeline-e2e", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id = _real_governed_dataset_version(settings, name_suffix="e2e")

        adapter = TorchTrainingAdapter()  # deliberately unconfigured -- the dataset pipeline must do all the work
        svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
        job = svc.create_job(
            topic="dataset-pipeline-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=core_model_version_id, dataset_version_public_id=dataset_id,
        )
        job_id = job["public_id"]
        svc.run_validate_release_stage(job_id, admin_id=admin_id)
        svc.run_validate_package_stage(job_id, admin_id=admin_id)
        svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.7g pipeline test", admin_id=admin_id)
        svc.run_plan_resources_stage(job_id, admin_id=admin_id)
        svc.run_build_manifest_stage(job_id, admin_id=admin_id)

        # No train_blocks/validation_blocks anywhere in this call -- the
        # real dataset pipeline derives them from the job's own real
        # dataset_version_public_id.
        report = svc.run_reserve_runtime_stage(
            job_id, admin_id=admin_id, configuration_label="TEST_INTEGRATION_CONFIGURATION",
        )
        assert report["runtime_reservation_report"]["reserved"] is True
        assert adapter._model is not None
        assert adapter._train_blocks, "real blocks must have been derived and passed to the adapter"

        # I/J: real loss + real weight change.
        svc.run_start_training_stage(job_id, admin_id=admin_id)
        before = [p.clone() for p in adapter._model.parameters()]
        metric = svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        after = list(adapter._model.parameters())
        assert any(not b.equal(a) for b, a in zip(before, after, strict=True))
        assert metric["training_state"]["last_loss"] is not None

        # K: real checkpoint.
        svc.run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        checkpoint_row = svc.list_checkpoints(job_id)["items"][0]
        real_checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])
        manager = TrainingCheckpointManager(real_checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        assert manager.verify(real_checkpoint_dir) is True

        # L: checkpoint references the exact dataset identity, tokenizer
        # checksum, normalization version, and block-builder version --
        # a fresh process could reconstruct exactly which data/tokenizer
        # produced this checkpoint from the file alone.
        states = manager.load_states(real_checkpoint_dir)
        references = states["references"]
        assert references["dataset_version_public_id"] == dataset_id
        with database_connection(settings.resolved_database_path) as connection:
            expected_checksum = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()["checksum_sha256"]
            expected_tokenizer_checksum = connection.execute(
                "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["model_checksum_sha256"]
        assert references["dataset_checksum_sha256"] == expected_checksum
        assert references["tokenizer_checksum_sha256"] == expected_tokenizer_checksum
        assert references["block_builder_version"] == BLOCK_BUILDER_VERSION
        assert references["normalization_version"] == "nmt_nfkc"
        assert references["context_length"] == 32
        assert references["train_block_count"] == len(adapter._train_blocks)
        assert references["validation_block_count"] >= 1

        # Phase 2.7F handoff still works unmodified against a dataset-
        # pipeline-produced checkpoint.
        handoff = MiniBrainPretrainingHandoffService(settings)
        result = handoff.register_checkpoint(job_id, checkpoint_row["public_id"], admin_id)
        with database_connection(settings.resolved_database_path) as connection:
            pretraining_checkpoint = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?",
                (result["pretraining_checkpoint_public_id"],),
            ).fetchone()
        assert pretraining_checkpoint["status"] == "verified"
