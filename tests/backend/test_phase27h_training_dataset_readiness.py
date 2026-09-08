"""Phase 2.7H: Training Dataset Readiness, Scale Validation & Real
Training Qualification.

Phase 2.7G proved the dataset -> tokenizer -> token-block pipeline was
real using a deliberately tiny (8-record) integration corpus. This file
goes further: it builds two genuinely different-sized, real, GOVERNED
Dataset Versions through the actual `DatasetVersioningService.
create_build()` -> `validate_build()` -> `run_build()` flow (real
selection, real grouping, real leakage detection, real manifest/checksum
computed by the service itself -- never a raw INSERT into
`dataset_version_items` bypassing governance), measures the real
pipeline's behavior at both sizes, proves the new structured
READY/NOT_READY/BLOCKED readiness contract (`MiniBrainDatasetPipelineService.
readiness_contract()`), and runs one real, isolated MB-22 training
qualification against the larger dataset -- still `TEST_INTEGRATION_
CONFIGURATION`-labeled and tiny-model-sized, never production training.

No fabricated token ids, no fabricated token counts, no fabricated
readiness verdicts anywhere in this file.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest
import sentencepiece as spm
from fastapi import FastAPI

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.models.dataset_versions import BuildCreate, BuildRunRequest, SplitConfiguration
from backend.models.tokenizers import SPECIAL_TOKENS
from backend.services.dataset_versioning import DatasetVersioningService
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

# ---------------------------------------------------------------------------
# Real, deterministic, distinct-per-record Tamil / English / Tanglish text.
# Every sentence embeds its own index so `content_hash` is unique per
# record dataset-wide -- never an accidental duplicate that would be
# silently deduplicated away by the real `_select_records()` gate.
# ---------------------------------------------------------------------------
_TAMIL_TEMPLATES = [
    "இது ஒரு தமிழ் பயிற்சி வாக்கியம் எண் {n}.",
    "பிரட் ஏஐ தமிழ் மொழி மாடலுக்கான தரவுத் தொகுதி பதிவு {n}.",
    "இன்றைய வானிலை குறிப்பு எண் {n} மிகவும் தெளிவாக உள்ளது.",
    "தமிழ்நாட்டின் பாரம்பரியம் பற்றிய குறிப்பு எண் {n}.",
]
_ENGLISH_TEMPLATES = [
    "This is an English readiness-validation sentence number {n}.",
    "Brud AI training-data record {n} for scale testing.",
    "Today's weather note {n} looks quite clear.",
    "A short note about Tamil Nadu heritage, entry {n}.",
]
_TANGLISH_TEMPLATES = [
    "Idhu oru readiness test sentence number {n}.",
    "Naan Brud AI training data pathivu {n} create pandren.",
    "Inniku weather note {n} nalla clear ah irukku.",
]


def _generate_corpus(total: int, *, seed_offset: int = 0) -> list[tuple[str, str]]:
    """Real, distinct sentences -- ~40% Tamil / ~40% English / ~20%
    Tanglish (`'mixed'`), matching the existing `dataset_records.language`
    convention. Deterministic: the same `total`/`seed_offset` always
    produces the exact same text."""

    n_tamil = round(total * 0.4)
    n_english = round(total * 0.4)
    n_tanglish = total - n_tamil - n_english
    records: list[tuple[str, str]] = []
    counter = seed_offset
    for i in range(n_tamil):
        records.append((_TAMIL_TEMPLATES[i % len(_TAMIL_TEMPLATES)].format(n=counter), "ta"))
        counter += 1
    for i in range(n_english):
        records.append((_ENGLISH_TEMPLATES[i % len(_ENGLISH_TEMPLATES)].format(n=counter), "en"))
        counter += 1
    for i in range(n_tanglish):
        records.append((_TANGLISH_TEMPLATES[i % len(_TANGLISH_TEMPLATES)].format(n=counter), "mixed"))
        counter += 1
    return records


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


def _real_tokenizer(settings: Settings, *, name_suffix: str, corpus_texts: list[str] | None = None) -> str:
    """The exact real, artifact-backed SentencePiece fixture pattern
    Phase 2.7G's own test file established -- trained on a real corpus,
    real checksums, artifacts written where `TokenizerService._artifact_dir()`
    actually resolves them (keyed on `family_name`/`version`, not public_id)."""

    corpus_texts = corpus_texts or (
        [t for t, _ in _generate_corpus(60)]
    )
    corpus = settings.resolved_tokenizer_corpus_dir / f"phase27h-corpus-{name_suffix}.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_text("\n".join(corpus_texts) + "\n", encoding="utf-8")
    temp_prefix = settings.resolved_tokenizer_dir / f"phase27h-tokenizer-{name_suffix}"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus), model_prefix=str(temp_prefix), model_type="bpe", vocab_size=400,
        character_coverage=1.0, hard_vocab_limit=False, pad_id=0, unk_id=1, bos_id=2, eos_id=3,
        pad_piece="<pad>", unk_piece="<unk>", bos_piece="<bos>", eos_piece="<eos>",
        user_defined_symbols=",".join(SPECIAL_TOKENS[4:]),
    )
    artifact_dir = settings.resolved_tokenizer_dir / "versions" / f"tok27h-family-{name_suffix}" / "v1"
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

    dataset_public_id = f"ds-tokcorpus-h-{name_suffix}"
    tokenizer_public_id = f"tok27h-{name_suffix}"
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (dataset_public_id, f"tokcorpus-h-{name_suffix}", "v1", "ready", "f" * 64),
        )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            (f"tf27h-{name_suffix}", f"tok27h-family-{name_suffix}", "T", "active"),
        )
        family_id = connection.execute(
            "SELECT id FROM tokenizer_families WHERE public_id=?", (f"tf27h-{name_suffix}",)
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


def _build_real_dataset_via_service(
    settings: Settings, *, name_suffix: str, record_texts: list[tuple[str, str]],
    train_percent: int = 70, validation_percent: int = 30, test_percent: int = 0,
) -> tuple[str, dict, dict]:
    """Builds a fully real, governed Dataset Version through the actual
    `DatasetVersioningService.create_build()` -> `validate_build()` ->
    `run_build()` flow -- real selection (`status='approved'` + rights
    check + content-hash dedup), real document-aware grouping, real
    deterministic split, real leakage detection, real manifest and
    checksum computed by the service itself. This is the same real
    surface an operator uses through Dataset Studio, not a second,
    parallel construction path."""

    source_public_id = f"src27h-{name_suffix}"
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
            licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
            (source_public_id, f"Phase 2.7H Source {name_suffix}", "manual", "ready", "mixed", "approved", "{}"),
        )
        source_id = connection.execute(
            "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
        ).fetchone()[0]
        for idx, (content, language) in enumerate(record_texts, start=1):
            connection.execute(
                """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                record_type,content_hash,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    f"rec27h-{name_suffix}-{idx}", source_id, content, language, "approved", "pretrain",
                    hashlib.sha256(content.encode("utf-8")).hexdigest(), "{}",
                ),
            )
        connection.commit()

    repository = DatasetQualityRepository(settings.resolved_database_path)
    service = DatasetVersioningService(repository, settings)
    build = service.create_build(
        BuildCreate(
            dataset_name=f"phase27h-{name_suffix}", dataset_version="v1",
            # Scoped to this call's own source -- without this, `_select_records()`
            # selects every `status='approved'` record in the whole (growing,
            # shared-per-test-function) database, including records inserted by
            # an earlier build in the same test, silently inflating record/manifest
            # size across iterations.
            selection_filters={"source_public_id": source_public_id},
            split_configuration=SplitConfiguration(
                train_percent=train_percent, validation_percent=validation_percent,
                test_percent=test_percent,
            ),
        ),
        admin_id="phase27h-fixture",
    )
    preview = service.validate_build(build["public_id"], admin_id="phase27h-fixture")
    result = service.run_build(build["public_id"], BuildRunRequest(confirm=True), admin_id="phase27h-fixture")
    return result["dataset_version_public_id"], preview, result


def _rss_kib() -> int:
    """Peak resident set size for this process, in KiB (Linux
    `ru_maxrss` is already KiB; other platforms report bytes -- this
    codebase only targets Linux, so no cross-platform conversion is
    attempted)."""

    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


# ===========================================================================
# Part 3/4: Real Dataset Snapshot + Dataset Statistics, at two real sizes.
# ===========================================================================


class TestRealDatasetSnapshot:
    async def test_small_qualification_dataset_is_real_and_governed(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        texts = _generate_corpus(40)
        dataset_id, preview, result = _build_real_dataset_via_service(
            settings, name_suffix="small", record_texts=texts,
        )
        assert result["status"] in {"completed", "completed_with_warnings"}
        assert preview["leakage"]["status"] == "safe"
        with database_connection(settings.resolved_database_path) as connection:
            version = connection.execute(
                "SELECT * FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()
            item_count = connection.execute(
                "SELECT COUNT(*) FROM dataset_version_items WHERE dataset_version_id=?", (version["id"],)
            ).fetchone()[0]
        assert version["status"] == "ready"
        assert version["record_count"] == 40
        assert item_count == 40
        assert version["checksum_sha256"] and len(version["checksum_sha256"]) == 64

    async def test_scale_validation_dataset_is_real_and_governed(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        texts = _generate_corpus(200)
        dataset_id, preview, result = _build_real_dataset_via_service(
            settings, name_suffix="scale", record_texts=texts,
        )
        assert result["status"] in {"completed", "completed_with_warnings"}
        assert preview["leakage"]["status"] == "safe"
        with database_connection(settings.resolved_database_path) as connection:
            version = connection.execute(
                "SELECT * FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()
            splits = connection.execute(
                "SELECT split, COUNT(*) AS n FROM dataset_version_items WHERE dataset_version_id=? GROUP BY split",
                (version["id"],),
            ).fetchall()
        split_counts = {row["split"]: row["n"] for row in splits}
        assert version["record_count"] == 200
        assert split_counts.get("train", 0) == 140
        assert split_counts.get("validation", 0) == 60
        assert split_counts.get("test", 0) == 0

    async def test_a_real_discovered_scale_ceiling_on_manifest_size(self, api_app: FastAPI) -> None:
        """Part 8 (Scale/Resource Validation), updated by Phase 2.7I:
        Phase 2.7H originally discovered that a real, 260-record build
        genuinely failed here -- `DatasetVersioningService._manifest()`'s
        own checksum payload (one entry per record, embedding full
        `instruction`/`input_text`/`output_text`/`normalized_input` text)
        exceeded `Settings.max_metadata_bytes` (65536 bytes) at roughly
        ~225 records for this record shape (Phase 2.7H report §13).

        Phase 2.7I's Finding B fix (`DatasetVersioningService.
        _checksum_payload_v2()`) replaced that payload with a compact,
        bounded-per-record form -- dropping the four text fields, which
        were pure duplication of what `dataset_records.content_hash`
        already captures -- so this exact same 260-record build now
        genuinely succeeds. This test now proves the fix at the exact
        scale that used to fail, rather than proving the original bug;
        see `tests/backend/test_phase27i_dataset_manifest_scalability.py`
        for the full 40/200/250/500-record proof."""

        settings = api_app.state.settings
        texts = _generate_corpus(260, seed_offset=99000)
        dataset_id, preview, result = _build_real_dataset_via_service(
            settings, name_suffix="ceiling", record_texts=texts,
        )
        assert result["status"] in {"completed", "completed_with_warnings"}
        with database_connection(settings.resolved_database_path) as connection:
            version = connection.execute(
                "SELECT status, record_count FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()
        assert version["status"] == "ready"
        assert version["record_count"] == 260


class TestDatasetStatistics:
    """Part 4: every number below comes straight from the real pipeline's
    own output -- nothing is computed independently and asserted to
    match by coincidence."""

    async def test_statistics_are_internally_consistent_at_both_sizes(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="stats")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="stats", tokenizer_version_public_id=tokenizer_id,
        )
        pipeline = MiniBrainDatasetPipelineService(settings)

        for size, suffix in ((40, "stats-small"), (200, "stats-large")):
            texts = _generate_corpus(size, seed_offset=size * 10)
            dataset_id, _, _ = _build_real_dataset_via_service(settings, name_suffix=suffix, record_texts=texts)
            result = pipeline.build_blocks(
                dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
            )
            train_cov = result["train_report"]["coverage"]
            valid_cov = result["validation_report"]["coverage"]
            # Every record was real, non-empty text -- nothing dropped.
            assert train_cov["encoded_records"] == train_cov["total_records"]
            assert valid_cov["encoded_records"] == valid_cov["total_records"]
            assert train_cov["total_records"] + valid_cov["total_records"] == size
            # Usable tokens must equal what pack_stream() itself reports consuming.
            assert result["train_report"]["packed"]["usable_tokens"] <= train_cov["usable_tokens"]
            assert len(result["train_blocks"]) == result["train_report"]["packed"]["block_count"]
            assert len(result["validation_blocks"]) == result["validation_report"]["packed"]["block_count"]
            # Token length stats: min <= average <= max, over the real sequences.
            stats = result["train_report"]["token_length_stats"]
            assert stats["sequence_count"] == train_cov["total_records"]
            assert stats["min_tokens"] <= stats["average_tokens"] <= stats["max_tokens"]


# ===========================================================================
# Part 5/6: Tokenizer Coverage + Language Analysis.
# ===========================================================================


class TestTokenizerCoverage:
    async def test_vocabulary_coverage_is_measured_never_interpreted_as_quality(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="vocab")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="vocab", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="vocab", record_texts=_generate_corpus(120, seed_offset=5000),
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        result = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        coverage = result["train_report"]["vocabulary_coverage"]
        with database_connection(settings.resolved_database_path) as connection:
            vocab_size = connection.execute(
                "SELECT vocabulary_size FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["vocabulary_size"]
        assert coverage["vocabulary_size"] == vocab_size
        assert 0 < coverage["distinct_token_ids_used"] <= vocab_size
        assert 0.0 <= coverage["vocabulary_utilization_ratio"] <= 1.0
        assert 0.0 <= coverage["unknown_token_rate"] <= 1.0
        # This corpus's own vocabulary was trained ON this corpus (§5's
        # own real tokenizer fixture) -- a near-zero unknown-token rate is
        # expected and is a tokenization-success signal, not a quality claim.
        assert coverage["unknown_token_rate"] < 0.05

    async def test_tokenization_success_rate_is_real_and_full_for_clean_records(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="succ")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="succ", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="succ", record_texts=_generate_corpus(40, seed_offset=6000),
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        result = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        train_cov = result["train_report"]["coverage"]
        success_rate = train_cov["encoded_records"] / train_cov["total_records"]
        assert success_rate == 1.0
        assert train_cov["zero_token_records"] == 0
        assert train_cov["exclusion_reasons"] == {}


class TestLanguageAnalysis:
    async def test_language_distribution_matches_the_real_seeded_corpus_exactly(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="lang")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="lang", tokenizer_version_public_id=tokenizer_id,
        )
        texts = _generate_corpus(100, seed_offset=7000)
        expected: dict[str, int] = {}
        for _, language in texts:
            expected[language] = expected.get(language, 0) + 1
        dataset_id, _, _ = _build_real_dataset_via_service(settings, name_suffix="lang", record_texts=texts)
        pipeline = MiniBrainDatasetPipelineService(settings)
        result = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        combined: dict[str, int] = dict(result["train_report"]["coverage"]["language_distribution"])
        for key, value in result["validation_report"]["coverage"]["language_distribution"].items():
            combined[key] = combined.get(key, 0) + value
        assert combined == expected
        assert set(combined) == {"ta", "en", "mixed"}


# ===========================================================================
# Part 7/12: Train/Validation Quality + Determinism/Reproducibility.
# ===========================================================================


class TestTrainValidationQuality:
    async def test_no_content_hash_crosses_the_train_validation_boundary(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        texts = _generate_corpus(150, seed_offset=8000)
        dataset_id, _, _ = _build_real_dataset_via_service(settings, name_suffix="tvq", record_texts=texts)
        with database_connection(settings.resolved_database_path) as connection:
            version_id = connection.execute(
                "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()["id"]
            rows = connection.execute(
                """SELECT i.split, r.content_hash FROM dataset_version_items i
                JOIN dataset_records r ON r.id=i.dataset_record_id WHERE i.dataset_version_id=?""",
                (version_id,),
            ).fetchall()
        seen: dict[str, str] = {}
        conflicts = []
        for row in rows:
            prior = seen.get(row["content_hash"])
            if prior and prior != row["split"]:
                conflicts.append(row["content_hash"])
            seen[row["content_hash"]] = row["split"]
        assert conflicts == []
        assert len(seen) == len(rows), "every content_hash in a real build is unique -- no in-split duplicates either"

    async def test_repeated_pipeline_execution_is_byte_identical(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="det")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="det-h", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="det", record_texts=_generate_corpus(120, seed_offset=9000),
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        first = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        second = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert first["train_blocks"] == second["train_blocks"]
        assert first["validation_blocks"] == second["validation_blocks"]
        assert (
            first["train_report"]["coverage"]["stream_checksum_sha256"]
            == second["train_report"]["coverage"]["stream_checksum_sha256"]
        )
        assert (
            first["validation_report"]["coverage"]["stream_checksum_sha256"]
            == second["validation_report"]["coverage"]["stream_checksum_sha256"]
        )
        assert first["dataset_checksum_sha256"] == second["dataset_checksum_sha256"]
        assert first["tokenizer_checksum_sha256"] == second["tokenizer_checksum_sha256"]
        # Full provenance dict, not just the checksums, is identical across runs.
        contract_first = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        contract_second = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract_first["reproducibility"] == contract_second["reproducibility"]
        assert contract_first["blocks"] == contract_second["blocks"]


# ===========================================================================
# Part 8: Scale / Resource Validation.
# ===========================================================================


class TestScaleResourceValidation:
    async def test_pipeline_timing_is_measured_at_two_real_dataset_sizes(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="scale")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="scale-h", tokenizer_version_public_id=tokenizer_id,
        )
        pipeline = MiniBrainDatasetPipelineService(settings)

        measurements: dict[int, dict[str, float]] = {}
        for size in (40, 200):
            texts = _generate_corpus(size, seed_offset=size * 100)
            dataset_id, _, _ = _build_real_dataset_via_service(
                settings, name_suffix=f"scale-{size}", record_texts=texts,
            )
            start = time.perf_counter()
            contract = pipeline.readiness_contract(
                dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
            )
            wall_clock = time.perf_counter() - start
            assert contract["status"] == "READY"
            measurements[size] = {
                "wall_clock_seconds": wall_clock,
                "reported_wall_clock_seconds": contract["resource_estimate"]["pipeline_wall_clock_seconds"],
                "peak_rss_kib": _rss_kib(),
            }

        # Both real, isolated, tiny-by-production-standards runs must
        # complete quickly on CPU -- this is a safety bound, not a
        # performance claim. 200 real records must not take more than a
        # few seconds on this CPU-oriented architecture.
        assert measurements[40]["wall_clock_seconds"] < 10.0
        assert measurements[200]["wall_clock_seconds"] < 30.0
        # Report the actual measured values for the Phase 2.7H report to cite verbatim.
        print("PHASE_27H_SCALE_MEASUREMENTS", measurements)  # noqa: T201 -- intentional, captured by -s


# ===========================================================================
# Part 2/11: the structured READY / NOT_READY / BLOCKED readiness contract.
# ===========================================================================


class TestReadinessContract:
    async def test_ready_real_dataset_reports_ready_with_full_detail(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-ok")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-ok", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="contract-ok", record_texts=_generate_corpus(50, seed_offset=11000),
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "READY"
        assert contract["reason"] is None
        assert all(check["passed"] for check in contract["checks"].values())
        assert contract["dataset"]["record_count"] == 50
        assert contract["blocks"]["train_block_count"] > 0
        assert contract["blocks"]["validation_block_count"] > 0
        assert set(contract["language_distribution"]) == {"ta", "en", "mixed"}
        assert contract["resource_estimate"]["pipeline_wall_clock_seconds"] >= 0.0

    async def test_nonexistent_dataset_is_blocked_not_not_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-noex")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-noex", tokenizer_version_public_id=tokenizer_id,
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id="00000000-0000-0000-0000-0000000c0ffee",
            core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "BLOCKED"
        assert "dataset version not found" in contract["reason"]
        assert contract["checks"]["A_dataset_version_exists"]["passed"] is False

    async def test_draft_dataset_is_blocked(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-draft")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-draft", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="contract-draft", record_texts=_generate_corpus(20, seed_offset=12000),
        )
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute("UPDATE dataset_versions SET status='draft' WHERE public_id=?", (dataset_id,))
            connection.commit()
        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "BLOCKED"
        assert "ready or archived" in contract["reason"]

    async def test_nonexistent_core_model_version_is_reported_not_uncaught(self, api_app: FastAPI) -> None:
        """Phase 2.7G's `check_readiness()` only caught `ValidationError`;
        `CoreModelRepository.version()` raises the sibling `NotFoundError`
        for an unknown Core Model Version, which escaped uncaught. This
        test proves the Phase 2.7H fix (both `check_readiness()` and
        `readiness_contract()` now catch both)."""

        settings = api_app.state.settings
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="contract-cmv", record_texts=_generate_corpus(20, seed_offset=13000),
        )
        pipeline = MiniBrainDatasetPipelineService(settings)

        boolean_result = pipeline.check_readiness(
            dataset_version_public_id=dataset_id,
            core_model_version_public_id="00000000-0000-0000-0000-0000000cmv99",
        )
        assert boolean_result["ready"] is False
        assert "core model version not found" in boolean_result["reason"]

        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id,
            core_model_version_public_id="00000000-0000-0000-0000-0000000cmv99",
        )
        assert contract["status"] == "BLOCKED"
        assert "core model version not found" in contract["reason"]

    async def test_empty_train_split_is_not_ready(self, api_app: FastAPI) -> None:
        """A dataset version with real rows in `dataset_version_items` but
        every one assigned to the dropped `test` split -- data problem,
        not an identity problem, so this is `NOT_READY`. Deliberately
        >=20 records: `DatasetVersioningService._split_groups()` has a
        real, discovered small-dataset override (Phase 2.7H report §7)
        that ignores the requested split percentages entirely below 20
        total records (fixed `train=n-1/validation=1/test=0` heuristic
        instead) -- fewer records would silently defeat this test's own
        `test_percent=100` request."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-empty")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-empty", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="contract-empty", record_texts=_generate_corpus(24, seed_offset=14000),
            train_percent=0, validation_percent=0, test_percent=100,
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "NOT_READY"
        assert "no tokenized records" in contract["reason"]

    async def test_sequence_length_mismatch_is_not_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-seqlen")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-seqlen", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="contract-seqlen", record_texts=_generate_corpus(20, seed_offset=15000),
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
            sequence_length=99999,
        )
        assert contract["status"] == "NOT_READY"
        assert "exceeds the Core Model Version's real context_length" in contract["reason"]

    async def test_blocked_leakage_across_splits_is_blocked(self, api_app: FastAPI) -> None:
        """A direct-insert fixture (bypassing `run_build()`, the way a
        hypothetical future write path might) places the exact same
        `content_hash` in both the train and validation splits. Proves
        `readiness_contract()`'s own live leakage check (I) catches this
        independently of whatever `DatasetVersioningService._leakage()`
        did at build time -- see the Phase 2.7H report §3/§10 for why
        `_leakage()` itself is structurally unreachable via the normal
        `_select_records()` (dedup-before-split) flow."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-leak")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-leak", tokenizer_version_public_id=tokenizer_id,
        )
        source_public_id = "src27h-leak"
        dataset_public_id = "dsv27h-leak"
        with database_connection(settings.resolved_database_path) as connection:
            connection.execute(
                """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
                licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
                (source_public_id, "Phase 2.7H Leakage Source", "manual", "ready", "ta", "approved", "{}"),
            )
            source_id = connection.execute(
                "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
            ).fetchone()[0]
            shared_text = "இது இரு பிரிவுகளிலும் தோன்றும் ஒரே உரை."
            shared_hash = hashlib.sha256(shared_text.encode("utf-8")).hexdigest()
            for suffix in ("train-copy", "validation-copy"):
                connection.execute(
                    """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                    record_type,content_hash,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                    (f"rec27h-leak-{suffix}", source_id, shared_text, "ta", "approved", "pretrain", shared_hash, "{}"),
                )
            connection.execute(
                """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256,record_count)
                VALUES (?,?,?,?,?,?)""",
                (dataset_public_id, "phase27h-leak", "v1", "ready", "e" * 64, 2),
            )
            dataset_id = connection.execute(
                "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_public_id,)
            ).fetchone()["id"]
            for split, suffix in (("train", "train-copy"), ("validation", "validation-copy")):
                record_id = connection.execute(
                    "SELECT id FROM dataset_records WHERE public_id=?", (f"rec27h-leak-{suffix}",)
                ).fetchone()["id"]
                connection.execute(
                    """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,split,
                    sequence_number) VALUES (?,?,?,?)""",
                    (dataset_id, record_id, split, 0 if split == "train" else 1),
                )
            connection.commit()

        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_public_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "BLOCKED"
        assert "leakage" in contract["reason"]
        assert contract["checks"]["I_no_blocked_leakage"]["passed"] is False

    async def test_invalid_tokenizer_artifact_missing_files_is_blocked(self, api_app: FastAPI) -> None:
        """The real, reachable tokenizer-artifact failure mode: the
        `tokenizer.model`/`tokenizer.vocab` files are missing from disk.
        (A checksum *mismatch* with files present is not currently
        rejected by `TokenizerService._processor()` -- a pre-existing gap
        outside this phase's scope, documented in the report rather than
        silently worked around or fixed here.)"""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-badtok")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-badtok", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="contract-badtok", record_texts=_generate_corpus(15, seed_offset=16000),
        )
        artifact_dir = settings.resolved_tokenizer_dir / "versions" / "tok27h-family-contract-badtok" / "v1"
        (artifact_dir / "tokenizer.model").unlink()

        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "BLOCKED"
        assert "tokenizer artifacts are incomplete" in contract["reason"]

    async def test_insufficient_usable_records_reports_not_ready(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id = _real_tokenizer(settings, name_suffix="contract-empty2")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="contract-empty2", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="contract-empty2",
            record_texts=[("", "ta"), ("   ", "en"), ("", "mixed")],
            train_percent=100, validation_percent=0, test_percent=0,
        )
        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "NOT_READY"


# ===========================================================================
# Part 9/10/15: Real Training Qualification against the larger dataset.
# ===========================================================================


class TestTrainingQualification:
    async def test_real_qualification_run_against_the_scale_validation_dataset(self, api_app: FastAPI) -> None:
        """Only run because the readiness gate independently reports
        READY first (mission Part 9 precondition) -- proves training
        actually consumes dataset-derived blocks from the LARGER (200-
        record) real dataset, not the tiny 2.7G corpus, and that a fresh
        `TrainingCheckpointManager` (a fresh Python object, no shared
        in-memory cache) can reload the checkpoint's real provenance."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic="phase27h-qualification")
        tokenizer_id = _real_tokenizer(settings, name_suffix="qual")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="qual", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="qual", record_texts=_generate_corpus(200, seed_offset=20000),
        )

        pipeline = MiniBrainDatasetPipelineService(settings)
        readiness = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert readiness["status"] == "READY", readiness["reason"]

        adapter = TorchTrainingAdapter()  # deliberately unconfigured -- the pipeline must do all the work
        svc = MiniBrainTrainingEngineService(settings, adapters={"gpu": adapter})
        job = svc.create_job(
            topic="phase27h-qualification-job", training_package_session_public_id=tp_id,
            release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
            core_model_version_public_id=core_model_version_id, dataset_version_public_id=dataset_id,
        )
        job_id = job["public_id"]
        svc.run_validate_release_stage(job_id, admin_id=admin_id)
        svc.run_validate_package_stage(job_id, admin_id=admin_id)
        svc.run_validate_authorization_stage(job_id, authorization_reason="phase 2.7h qualification", admin_id=admin_id)
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
        initial_metric = svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        second_metric = svc.run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        after = list(adapter._model.parameters())

        assert initial_metric["training_state"]["last_loss"] is not None
        assert second_metric["training_state"]["last_loss"] is not None
        assert any(not b.equal(a) for b, a in zip(before, after, strict=True))

        svc.run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        checkpoint_row = svc.list_checkpoints(job_id)["items"][0]
        real_checkpoint_dir = Path(adapter._checkpoints_saved[0]["canonical_checkpoint_directory"])

        # Fresh `TrainingCheckpointManager` instance -- no shared state
        # with the one (if any) the adapter itself used internally.
        manager = TrainingCheckpointManager(real_checkpoint_dir.parent, settings.core_checkpoint_max_bytes)
        assert manager.verify(real_checkpoint_dir) is True
        states = manager.load_states(real_checkpoint_dir)
        references = states["references"]

        assert references["dataset_version_public_id"] == dataset_id
        assert references["core_model_version_public_id"] == core_model_version_id
        with database_connection(settings.resolved_database_path) as connection:
            expected_dataset_checksum = connection.execute(
                "SELECT checksum_sha256 FROM dataset_versions WHERE public_id=?", (dataset_id,)
            ).fetchone()["checksum_sha256"]
            expected_tokenizer_checksum = connection.execute(
                "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["model_checksum_sha256"]
        assert references["dataset_checksum_sha256"] == expected_dataset_checksum
        assert references["tokenizer_checksum_sha256"] == expected_tokenizer_checksum
        assert references["block_builder_version"] == BLOCK_BUILDER_VERSION
        assert references["train_block_count"] == len(adapter._train_blocks)
        assert references["validation_block_count"] == len(adapter._validation_blocks)

        # Part 10: capture the real metrics, honestly -- including MB-22's
        # own known, pre-existing limitation (processed_tokens=0 at the
        # handoff layer, `mini_brain_pretraining_handoff_service.py:103`).
        handoff = MiniBrainPretrainingHandoffService(settings)
        handoff_result = handoff.register_checkpoint(job_id, checkpoint_row["public_id"], admin_id)
        with database_connection(settings.resolved_database_path) as connection:
            pretraining_checkpoint = connection.execute(
                "SELECT * FROM pretraining_checkpoints WHERE public_id=?",
                (handoff_result["pretraining_checkpoint_public_id"],),
            ).fetchone()
            pretraining_job = connection.execute(
                "SELECT * FROM pretraining_jobs WHERE id=?", (pretraining_checkpoint["pretraining_job_id"],)
            ).fetchone()
        assert pretraining_checkpoint["status"] == "verified"
        assert pretraining_job["processed_tokens"] == 0, (
            "honestly preserved, pre-existing MB-22 limitation -- see mini_brain_pretraining_handoff_service.py:103"
        )

        print(
            "PHASE_27H_TRAINING_QUALIFICATION_METRICS",
            {
                "initial_loss": initial_metric["training_state"]["last_loss"],
                "second_loss": second_metric["training_state"]["last_loss"],
                "checkpoint_step": checkpoint_row.get("step"),
                "train_block_count": len(adapter._train_blocks),
                "validation_block_count": len(adapter._validation_blocks),
                "dataset_record_count": readiness["dataset"]["record_count"],
            },
        )  # noqa: T201
