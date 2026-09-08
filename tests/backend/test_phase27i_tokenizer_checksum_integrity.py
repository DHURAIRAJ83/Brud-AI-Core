"""Phase 2.7I, Finding A: `TokenizerService._processor()` computed
`_verify_artifacts()`'s real, recomputed checksum-comparison result but
discarded it -- a `tokenizer.model`/`tokenizer.vocab` file physically
present but no longer matching the DB-recorded SHA-256 (corruption,
tampering, a stale artifact left behind by a failed re-export) was
silently loaded and used for real tokenization instead of being
rejected. Only *missing* files were ever rejected
(`"tokenizer artifacts are incomplete"`).

The fix (`backend/services/tokenizer_registry.py::_processor()`) reuses
`_verify_artifacts()`'s own existing checksum recomputation verbatim --
no new checksum logic, no change to tokenizer training behavior, no
change to tokenizer identity resolution, no change to the Core Model ->
tokenizer relationship. This file proves the fix with real files on
disk, real SHA-256 corruption, and the real `TokenizerService` class --
never a mock.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import sentencepiece as spm
from fastapi import FastAPI

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.tokenizers import SPECIAL_TOKENS
from backend.services.core_model_service import CoreModelService
from backend.services.mini_brain_dataset_pipeline_service import MiniBrainDatasetPipelineService
from backend.services.tokenizer_registry import TokenizerService
from tests.backend.test_mini_brain_training_engine_service import _create_admin
from tests.backend.test_torch_training_adapter_integration import _real_core_model_version

pytestmark = pytest.mark.anyio

_CORPUS = [
    "வணக்கம், இது ஒரு சோதனை வாக்கியம்.",
    "தமிழ் இந்தியாவின் பழமையான மொழிகளில் ஒன்று.",
    "Hello, this is a test sentence.",
    "Brud AI is a Tamil-first assistant platform.",
    "Vanakkam, indha oru test sentence.",
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


def _real_tokenizer_with_paths(settings: Settings, *, name_suffix: str) -> tuple[str, Path, Path]:
    """The exact real, artifact-backed SentencePiece fixture pattern
    established in Phase 2.7G/2.7H, returning the model/vocab file paths
    too so a test can corrupt them afterward -- real training, real
    files on disk, real checksums recorded in the DB row exactly once at
    insert time (never recomputed after corruption)."""

    corpus = settings.resolved_tokenizer_corpus_dir / f"phase27i-corpus-{name_suffix}.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_text("\n".join(_CORPUS) + "\n", encoding="utf-8")
    temp_prefix = settings.resolved_tokenizer_dir / f"phase27i-tokenizer-{name_suffix}"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus), model_prefix=str(temp_prefix), model_type="bpe", vocab_size=200,
        character_coverage=1.0, hard_vocab_limit=False, pad_id=0, unk_id=1, bos_id=2, eos_id=3,
        pad_piece="<pad>", unk_piece="<unk>", bos_piece="<bos>", eos_piece="<eos>",
        user_defined_symbols=",".join(SPECIAL_TOKENS[4:]),
    )
    artifact_dir = settings.resolved_tokenizer_dir / "versions" / f"tok27i-family-{name_suffix}" / "v1"
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

    dataset_public_id = f"ds-tokcorpus-i-{name_suffix}"
    tokenizer_public_id = f"tok27i-{name_suffix}"
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (dataset_public_id, f"tokcorpus-i-{name_suffix}", "v1", "ready", "f" * 64),
        )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            (f"tf27i-{name_suffix}", f"tok27i-family-{name_suffix}", "T", "active"),
        )
        family_id = connection.execute(
            "SELECT id FROM tokenizer_families WHERE public_id=?", (f"tf27i-{name_suffix}",)
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
    return tokenizer_public_id, model, vocab


def _service(settings: Settings) -> TokenizerService:
    return TokenizerService(TokenizerRepository(settings.resolved_database_path), settings)


class TestTokenizerChecksumIntegrity:
    async def test_1_valid_tokenizer_loads_successfully(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        tokenizer_id, _model, _vocab = _real_tokenizer_with_paths(settings, name_suffix="valid")
        processor = _service(settings).processor_for_version(tokenizer_id)
        ids = processor.encode("வணக்கம்", out_type=int)
        assert isinstance(ids, list) and len(ids) > 0

    async def test_2_missing_tokenizer_model_is_rejected(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        tokenizer_id, model, _vocab = _real_tokenizer_with_paths(settings, name_suffix="missmodel")
        model.unlink()
        with pytest.raises(ValidationError, match="tokenizer artifacts are incomplete"):
            _service(settings).processor_for_version(tokenizer_id)

    async def test_3_missing_tokenizer_vocab_is_rejected(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        tokenizer_id, _model, vocab = _real_tokenizer_with_paths(settings, name_suffix="missvocab")
        vocab.unlink()
        with pytest.raises(ValidationError, match="tokenizer artifacts are incomplete"):
            _service(settings).processor_for_version(tokenizer_id)

    async def test_4_corrupted_tokenizer_model_checksum_mismatch_is_rejected(self, api_app: FastAPI) -> None:
        """The real regression case for the Phase 2.7H finding: the file
        is physically present (so the old `"tokenizer artifacts are
        incomplete"` missing-file check does NOT fire), but its bytes no
        longer match the DB-recorded `model_checksum_sha256` -- before
        the fix, `_processor()` would have silently loaded this
        corrupted model and used it for real tokenization."""

        settings = api_app.state.settings
        tokenizer_id, model, _vocab = _real_tokenizer_with_paths(settings, name_suffix="badmodel")
        original_checksum = _sha256(model)
        with model.open("ab") as handle:
            handle.write(b"\x00\x01\x02corruption-injected-by-phase-2.7i-test")
        assert _sha256(model) != original_checksum, "the corruption must actually change the file's checksum"

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            _service(settings).processor_for_version(tokenizer_id)

        # No DB mutation: the recorded checksum is untouched (still the
        # original, now-mismatched value) -- rejection never rewrites it.
        with database_connection(settings.resolved_database_path) as connection:
            row = connection.execute(
                "SELECT model_checksum_sha256, lifecycle_status FROM tokenizer_versions WHERE public_id=?",
                (tokenizer_id,),
            ).fetchone()
        assert row["model_checksum_sha256"] == original_checksum
        assert row["lifecycle_status"] == "active"

    async def test_5_corrupted_tokenizer_vocab_checksum_mismatch_is_rejected(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        tokenizer_id, _model, vocab = _real_tokenizer_with_paths(settings, name_suffix="badvocab")
        original_checksum = _sha256(vocab)
        with vocab.open("ab") as handle:
            handle.write(b"\x00\x01\x02corruption-injected-by-phase-2.7i-test")
        assert _sha256(vocab) != original_checksum

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            _service(settings).processor_for_version(tokenizer_id)

        with database_connection(settings.resolved_database_path) as connection:
            row = connection.execute(
                "SELECT vocabulary_checksum_sha256 FROM tokenizer_versions WHERE public_id=?",
                (tokenizer_id,),
            ).fetchone()
        assert row["vocabulary_checksum_sha256"] == original_checksum

    async def test_6_correct_files_and_checksums_load_successfully_fresh_instance(self, api_app: FastAPI) -> None:
        """A second, independent `TokenizerService` instance (no shared
        in-process processor cache) still loads a genuinely correct
        tokenizer successfully -- the fix does not reject valid
        artifacts."""

        settings = api_app.state.settings
        tokenizer_id, _model, _vocab = _real_tokenizer_with_paths(settings, name_suffix="fresh")
        service_a = _service(settings)
        service_b = _service(settings)
        processor_a = service_a.processor_for_version(tokenizer_id)
        processor_b = service_b.processor_for_version(tokenizer_id)
        assert processor_a.encode("Hello", out_type=int) == processor_b.encode("Hello", out_type=int)

    async def test_7_no_fallback_tokenizer_after_corruption(self, api_app: FastAPI) -> None:
        """Corruption must never trigger a silent substitute: the same
        call always fails the same way (deterministic rejection, not an
        eventual fallback success), and only the corrupted version's own
        row is affected -- a separate, valid tokenizer version remains
        completely unaffected and still resolvable."""

        settings = api_app.state.settings
        bad_id, bad_model, _bad_vocab = _real_tokenizer_with_paths(settings, name_suffix="nofallback-bad")
        good_id, _good_model, _good_vocab = _real_tokenizer_with_paths(settings, name_suffix="nofallback-good")
        with bad_model.open("ab") as handle:
            handle.write(b"corrupted")

        service = _service(settings)
        for _ in range(3):
            with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
                service.processor_for_version(bad_id)

        # The separate, valid tokenizer is completely unaffected.
        processor = service.processor_for_version(good_id)
        assert processor.encode("Hello", out_type=int)

        with database_connection(settings.resolved_database_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM tokenizer_versions").fetchone()[0]
        assert count == 2, "corruption must never spawn a substitute/fallback tokenizer row"

    async def test_8_core_model_version_still_resolves_the_same_tokenizer_identity_after_corruption(
        self, api_app: FastAPI,
    ) -> None:
        """Identity resolution (which tokenizer a Core Model Version
        points to) and artifact integrity (whether that tokenizer's real
        files can be safely loaded) are two different concerns --
        corruption must break only the second, never silently change the
        first. Also proves the fix reaches all the way through the real
        dataset pipeline: `MiniBrainDatasetPipelineService.build_blocks()`
        must reject the corrupted tokenizer with the same typed error,
        not silently train on corrupted-tokenizer output."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_with_paths(settings, name_suffix="cmv")
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="phase27i-cmv", tokenizer_version_public_id=tokenizer_id,
        )

        core_models = CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)
        _config, version_row = core_models.model_config_for_version(core_model_version_id)
        assert version_row["tokenizer_version_public_id"] == tokenizer_id

        with model.open("ab") as handle:
            handle.write(b"corrupted-after-identity-resolution")

        # Identity resolution itself still succeeds and still names the
        # exact same tokenizer -- corruption doesn't change *which*
        # tokenizer a Core Model Version resolves to.
        _config2, version_row2 = core_models.model_config_for_version(core_model_version_id)
        assert version_row2["tokenizer_version_public_id"] == tokenizer_id

        # But actually loading that tokenizer's real artifacts now
        # correctly fails -- and that failure propagates through the real
        # dataset pipeline before any real training could consume
        # corrupted-tokenizer output.
        pipeline = MiniBrainDatasetPipelineService(settings)
        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            pipeline.build_blocks(
                dataset_version_public_id="00000000-0000-0000-0000-00000027ida0",
                core_model_version_public_id=core_model_version_id,
            )
