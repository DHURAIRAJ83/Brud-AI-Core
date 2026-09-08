"""Phase 2.7J: Tokenizer Lifecycle Integrity Hardening & Training
Artifact Trust.

Phase 2.7I fixed `TokenizerService._processor()` (the real tokenization
path) to enforce `_verify_artifacts()`'s already-computed `verified`
result instead of discarding it, but documented -- as an explicit,
out-of-scope remaining gap -- that `TokenizerService.activate()` and
`TokenizerService.export()` shared the identical discard pattern: both
called `_verify_artifacts()` and threw away the boolean, so a tokenizer
whose real files no longer matched their registered checksums could
still be rejected for *tokenization* but still successfully *activated*
or *exported*.

This file proves that gap independently (real SentencePiece artifacts,
real byte-level corruption, the real `TokenizerService` class -- never a
mock) and then proves the fix: `activate()` and `export()` now reuse
`_verify_artifacts()`'s own existing checksum recomputation verbatim (no
new checksum logic anywhere) and reject before any lifecycle mutation or
export-artifact creation occurs.
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
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.tokenizers import SPECIAL_TOKENS
from backend.services.core_model_service import CoreModelService
from backend.services.mini_brain_dataset_pipeline_service import MiniBrainDatasetPipelineService
from backend.services.tokenizer_registry import TokenizerService
from tests.backend.test_mini_brain_training_engine_service import _create_admin
from tests.backend.test_phase27h_training_dataset_readiness import (
    _build_real_dataset_via_service,
    _generate_corpus,
)
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
        tokenizer_export_dir=tmp_path / "tokenizer_exports",
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


def _service(settings: Settings) -> TokenizerService:
    return TokenizerService(TokenizerRepository(settings.resolved_database_path), settings)


def _real_tokenizer_for_lifecycle(
    settings: Settings, *, name_suffix: str, lifecycle_status: str = "staging",
) -> tuple[str, Path, Path]:
    """A real, artifact-backed SentencePiece tokenizer registered with a
    real, passing evaluation summary (`metrics_summary_json`) so
    `activate()`'s own separate evaluation-readiness gate does not block
    these tests -- the only thing under test here is the checksum-
    verification gate. Returns (tokenizer_public_id, model_path,
    vocab_path) so a test can corrupt/restore the real files directly."""

    corpus = settings.resolved_tokenizer_corpus_dir / f"phase27j-corpus-{name_suffix}.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_text("\n".join(_CORPUS) + "\n", encoding="utf-8")
    temp_prefix = settings.resolved_tokenizer_dir / f"phase27j-tokenizer-{name_suffix}"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus), model_prefix=str(temp_prefix), model_type="bpe", vocab_size=200,
        character_coverage=1.0, hard_vocab_limit=False, pad_id=0, unk_id=1, bos_id=2, eos_id=3,
        pad_piece="<pad>", unk_piece="<unk>", bos_piece="<bos>", eos_piece="<eos>",
        user_defined_symbols=",".join(SPECIAL_TOKENS[4:]),
    )
    artifact_dir = settings.resolved_tokenizer_dir / "versions" / f"tok27j-family-{name_suffix}" / "v1"
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

    dataset_public_id = f"ds-tokcorpus-j-{name_suffix}"
    tokenizer_public_id = f"tok27j-{name_suffix}"
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (dataset_public_id, f"tokcorpus-j-{name_suffix}", "v1", "ready", "f" * 64),
        )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            (f"tf27j-{name_suffix}", f"tok27j-family-{name_suffix}", "T", "active"),
        )
        family_id = connection.execute(
            "SELECT id FROM tokenizer_families WHERE public_id=?", (f"tf27j-{name_suffix}",)
        ).fetchone()[0]
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_public_id,)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
            lifecycle_status,algorithm,vocabulary_size,character_coverage,
            normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
            model_checksum_sha256,vocabulary_checksum_sha256,artifact_manifest_json,
            special_tokens_json,metrics_summary_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tokenizer_public_id, family_id, "v1", lifecycle_status, "bpe", processor.vocab_size(), 1.0,
                "nmt_nfkc", "sentencepiece", dataset_id, "a" * 64,
                manifest["model_checksum_sha256"], manifest["vocabulary_checksum_sha256"],
                dumps_json(manifest), dumps_json(SPECIAL_TOKENS),
                dumps_json({"overall": {"ready": True}}),
            ),
        )
        connection.commit()
    return tokenizer_public_id, model, vocab


def _lifecycle_row(settings: Settings, tokenizer_public_id: str) -> dict:
    with database_connection(settings.resolved_database_path) as connection:
        row = connection.execute(
            """SELECT public_id, lifecycle_status, model_checksum_sha256, vocabulary_checksum_sha256,
            activated_at FROM tokenizer_versions WHERE public_id=?""",
            (tokenizer_public_id,),
        ).fetchone()
    return dict(row)


class TestActivateIntegrity:
    async def test_1_valid_tokenizer_activates_successfully(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, _model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="act-ok")
        result = _service(settings).activate(tokenizer_id, admin_id)
        assert result["lifecycle_status"] == "active"

    async def test_2_corrupted_tokenizer_model_cannot_activate(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="act-badmodel")
        original = model.read_bytes()
        with model.open("ab") as handle:
            handle.write(b"corrupted-by-phase-2.7j")
        assert _sha256(model) != hashlib.sha256(original).hexdigest()

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            _service(settings).activate(tokenizer_id, admin_id)

    async def test_3_corrupted_tokenizer_vocab_cannot_activate(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, _model, vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="act-badvocab")
        with vocab.open("ab") as handle:
            handle.write(b"corrupted-by-phase-2.7j")

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            _service(settings).activate(tokenizer_id, admin_id)

    async def test_4_missing_tokenizer_model_cannot_activate(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="act-missmodel")
        model.unlink()
        with pytest.raises(ValidationError, match="tokenizer artifacts are incomplete"):
            _service(settings).activate(tokenizer_id, admin_id)

    async def test_5_missing_tokenizer_vocab_cannot_activate(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, _model, vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="act-missvocab")
        vocab.unlink()
        with pytest.raises(ValidationError, match="tokenizer artifacts are incomplete"):
            _service(settings).activate(tokenizer_id, admin_id)

    async def test_6_failed_activation_does_not_mutate_lifecycle_state(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="act-nomutate")
        before = _lifecycle_row(settings, tokenizer_id)
        with model.open("ab") as handle:
            handle.write(b"corrupted")

        with pytest.raises(ValidationError):
            _service(settings).activate(tokenizer_id, admin_id)

        after = _lifecycle_row(settings, tokenizer_id)
        assert after["lifecycle_status"] == before["lifecycle_status"] == "staging"
        assert after["activated_at"] is None
        assert after["model_checksum_sha256"] == before["model_checksum_sha256"]
        assert after["vocabulary_checksum_sha256"] == before["vocabulary_checksum_sha256"]


class TestExportIntegrity:
    async def test_7_valid_tokenizer_exports_successfully(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, _model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="exp-ok")
        result = _service(settings).export(tokenizer_id, "sentencepiece_bundle", admin_id)
        assert result["status"] == "completed"
        export_dir = settings.resolved_tokenizer_export_dir / result["safe_name"]
        assert (export_dir / "tokenizer.model").is_file()
        assert (export_dir / "tokenizer.vocab").is_file()

    async def test_8_corrupted_tokenizer_model_cannot_export(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="exp-badmodel")
        with model.open("ab") as handle:
            handle.write(b"corrupted-by-phase-2.7j")

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            _service(settings).export(tokenizer_id, "sentencepiece_bundle", admin_id)

    async def test_9_corrupted_tokenizer_vocab_cannot_export(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, _model, vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="exp-badvocab")
        with vocab.open("ab") as handle:
            handle.write(b"corrupted-by-phase-2.7j")

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            _service(settings).export(tokenizer_id, "sentencepiece_bundle", admin_id)

    async def test_10_missing_tokenizer_model_cannot_export(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="exp-missmodel")
        model.unlink()
        with pytest.raises(ValidationError, match="tokenizer artifacts are incomplete"):
            _service(settings).export(tokenizer_id, "sentencepiece_bundle", admin_id)

    async def test_11_missing_tokenizer_vocab_cannot_export(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, _model, vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="exp-missvocab")
        vocab.unlink()
        with pytest.raises(ValidationError, match="tokenizer artifacts are incomplete"):
            _service(settings).export(tokenizer_id, "sentencepiece_bundle", admin_id)

    async def test_12_failed_export_leaves_no_usable_bundle_or_db_row(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="exp-nostray")
        with model.open("ab") as handle:
            handle.write(b"corrupted")

        with pytest.raises(ValidationError):
            _service(settings).export(tokenizer_id, "sentencepiece_bundle", admin_id)

        # No export directory was created at all -- the rejection happens
        # before `target.mkdir()`, so there is nothing to clean up.
        export_root = settings.resolved_tokenizer_export_dir
        if export_root.exists():
            assert list(export_root.iterdir()) == []
        with database_connection(settings.resolved_database_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM tokenizer_exports").fetchone()[0]
        assert count == 0


class TestNoFallbackAndIdentityStability:
    async def test_13_valid_tokenizer_remains_usable_after_another_is_corrupted(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        bad_id, bad_model, _bad_vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="isolate-bad")
        good_id, _good_model, _good_vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="isolate-good")
        with bad_model.open("ab") as handle:
            handle.write(b"corrupted")

        service = _service(settings)
        with pytest.raises(ValidationError):
            service.activate(bad_id, admin_id)
        with pytest.raises(ValidationError):
            service.export(bad_id, "sentencepiece_bundle", admin_id)

        activated = service.activate(good_id, admin_id)
        assert activated["lifecycle_status"] == "active"
        exported = service.export(good_id, "sentencepiece_bundle", admin_id)
        assert exported["status"] == "completed"

    async def test_14_no_fallback_tokenizer_is_created(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="no-fallback")
        with database_connection(settings.resolved_database_path) as connection:
            before_count = connection.execute("SELECT COUNT(*) FROM tokenizer_versions").fetchone()[0]
        with model.open("ab") as handle:
            handle.write(b"corrupted")

        service = _service(settings)
        with pytest.raises(ValidationError):
            service.activate(tokenizer_id, admin_id)
        with pytest.raises(ValidationError):
            service.export(tokenizer_id, "sentencepiece_bundle", admin_id)

        with database_connection(settings.resolved_database_path) as connection:
            after_count = connection.execute("SELECT COUNT(*) FROM tokenizer_versions").fetchone()[0]
        assert after_count == before_count, "corruption must never spawn a substitute/fallback tokenizer row"

    async def test_15_core_model_version_tokenizer_identity_unchanged_after_corruption(
        self, api_app: FastAPI,
    ) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(
            settings, name_suffix="cmv-identity", lifecycle_status="active",
        )
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="phase27j-cmv", tokenizer_version_public_id=tokenizer_id,
        )
        core_models = CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)
        _config, version_row = core_models.model_config_for_version(core_model_version_id)
        assert version_row["tokenizer_version_public_id"] == tokenizer_id

        with model.open("ab") as handle:
            handle.write(b"corrupted-after-identity-resolution")

        _config2, version_row2 = core_models.model_config_for_version(core_model_version_id)
        assert version_row2["tokenizer_version_public_id"] == tokenizer_id

    async def test_16_dataset_pipeline_rejects_corrupted_tokenizer_via_processor_path(
        self, api_app: FastAPI,
    ) -> None:
        """Regression proof: Phase 2.7I's `_processor()` fix still holds
        after this phase's `activate()`/`export()` changes -- the real
        dataset pipeline still rejects a corrupted tokenizer before any
        real training could consume corrupted-tokenizer output."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(
            settings, name_suffix="pipeline-reject", lifecycle_status="active",
        )
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="phase27j-pipeline", tokenizer_version_public_id=tokenizer_id,
        )
        with model.open("ab") as handle:
            handle.write(b"corrupted")

        pipeline = MiniBrainDatasetPipelineService(settings)
        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            pipeline.build_blocks(
                dataset_version_public_id="00000000-0000-0000-0000-00000027jd00",
                core_model_version_public_id=core_model_version_id,
            )

    async def test_17_repeated_corrupted_activation_attempts_remain_deterministic(
        self, api_app: FastAPI,
    ) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="act-repeat")
        with model.open("ab") as handle:
            handle.write(b"corrupted")

        service = _service(settings)
        for _ in range(3):
            with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
                service.activate(tokenizer_id, admin_id)
        assert _lifecycle_row(settings, tokenizer_id)["lifecycle_status"] == "staging"

    async def test_18_repeated_corrupted_export_attempts_remain_deterministic(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="exp-repeat")
        with model.open("ab") as handle:
            handle.write(b"corrupted")

        service = _service(settings)
        for _ in range(3):
            with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
                service.export(tokenizer_id, "sentencepiece_bundle", admin_id)
        with database_connection(settings.resolved_database_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM tokenizer_exports").fetchone()[0]
        assert count == 0


class TestRealChecksumProof:
    """Part 11: for one real tokenizer, prove the actual SHA-256
    genuinely differs from the DB-recorded checksum during corruption
    (never mutate the DB checksum to match), that every lifecycle
    boundary rejects during that window, and that restoring the exact
    original bytes returns every boundary to normal."""

    async def test_model_corruption_and_exact_restoration_round_trip(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="proof-model")
        with database_connection(settings.resolved_database_path) as connection:
            db_checksum = connection.execute(
                "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["model_checksum_sha256"]
        original_bytes = model.read_bytes()
        assert _sha256(model) == db_checksum, "the real file must genuinely match the DB checksum before corruption"

        model.write_bytes(original_bytes + b"\xde\xad\xbe\xef-phase-2.7j-corruption")
        corrupted_checksum = _sha256(model)
        assert corrupted_checksum != db_checksum, "corruption must genuinely change the real file's SHA-256"

        service = _service(settings)
        with database_connection(settings.resolved_database_path) as connection:
            still_original = connection.execute(
                "SELECT model_checksum_sha256 FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["model_checksum_sha256"]
        assert still_original == db_checksum, "the DB checksum must remain the original trusted value during the corruption window"

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            service.processor_for_version(tokenizer_id)
        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            service.activate(tokenizer_id, admin_id)
        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            service.export(tokenizer_id, "sentencepiece_bundle", admin_id)

        model.write_bytes(original_bytes)
        assert _sha256(model) == db_checksum

        restored_processor = service.processor_for_version(tokenizer_id)
        assert restored_processor.encode("Hello", out_type=int)
        activated = service.activate(tokenizer_id, admin_id)
        assert activated["lifecycle_status"] == "active"
        exported = service.export(tokenizer_id, "sentencepiece_bundle", admin_id)
        assert exported["status"] == "completed"

    async def test_vocab_corruption_and_exact_restoration_round_trip(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, _model, vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="proof-vocab")
        with database_connection(settings.resolved_database_path) as connection:
            db_checksum = connection.execute(
                "SELECT vocabulary_checksum_sha256 FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["vocabulary_checksum_sha256"]
        original_bytes = vocab.read_bytes()
        assert _sha256(vocab) == db_checksum

        vocab.write_bytes(original_bytes + b"\xde\xad\xbe\xef-phase-2.7j-corruption")
        corrupted_checksum = _sha256(vocab)
        assert corrupted_checksum != db_checksum

        service = _service(settings)
        with database_connection(settings.resolved_database_path) as connection:
            still_original = connection.execute(
                "SELECT vocabulary_checksum_sha256 FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["vocabulary_checksum_sha256"]
        assert still_original == db_checksum

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            service.processor_for_version(tokenizer_id)
        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            service.activate(tokenizer_id, admin_id)
        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            service.export(tokenizer_id, "sentencepiece_bundle", admin_id)

        vocab.write_bytes(original_bytes)
        assert _sha256(vocab) == db_checksum

        restored_processor = service.processor_for_version(tokenizer_id)
        assert restored_processor.encode("Hello", out_type=int)
        activated = service.activate(tokenizer_id, admin_id)
        assert activated["lifecycle_status"] == "active"
        exported = service.export(tokenizer_id, "sentencepiece_bundle", admin_id)
        assert exported["status"] == "completed"


class TestCacheTrustBoundary:
    """Part 8: documents the existing, intentional cache trust boundary
    -- not a new fix, not something this phase changes. `activate()`/
    `export()` never touch `self._cache` at all (they always call
    `_verify_artifacts()` directly), so they are unaffected by it. Only
    `_processor()`'s own cache can serve an already-loaded processor
    without re-verifying if the file is corrupted *after* a successful
    first load within the same process."""

    async def test_cached_processor_is_not_invalidated_by_post_load_corruption(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(
            settings, name_suffix="cache-boundary", lifecycle_status="active",
        )
        service = _service(settings)
        first = service.processor_for_version(tokenizer_id)
        assert first.encode("Hello", out_type=int)

        with model.open("ab") as handle:
            handle.write(b"corrupted-after-caching")

        # Documented, intentional behavior: the cache is keyed only by
        # public_id and checked before verification, so a second call in
        # the SAME process returns the already-cached (pre-corruption)
        # processor rather than re-verifying and rejecting.
        second = service.processor_for_version(tokenizer_id)
        assert second is first

    async def test_activate_and_export_never_consult_the_processor_cache(self, api_app: FastAPI) -> None:
        """Even after a tokenizer's processor is cached from a successful
        load, `activate()` and `export()` still independently re-read and
        re-verify the real files on disk -- corrupting the file after
        caching still causes both to reject."""

        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, model, _vocab = _real_tokenizer_for_lifecycle(settings, name_suffix="cache-no-bypass")
        service = _service(settings)
        # Force a cache entry via a direct _processor() call against a
        # temporarily-relaxed lifecycle read is unnecessary here -- the
        # tokenizer is 'staging', which `_processor()` already accepts,
        # so a real cache entry can be created without activating first.
        cached = service.processor_for_version(tokenizer_id)
        assert cached.encode("Hello", out_type=int)

        with model.open("ab") as handle:
            handle.write(b"corrupted-after-caching")

        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            service.activate(tokenizer_id, admin_id)
        with pytest.raises(ValidationError, match="tokenizer artifact checksum verification failed"):
            service.export(tokenizer_id, "sentencepiece_bundle", admin_id)


class TestCoreModelDatasetPipelineRegression:
    """Part 13/14: with genuinely valid (uncorrupted) tokenizer artifacts,
    the full real chain -- governed Dataset Version -> Core Model Version
    -> tokenizer -> readiness_contract() -> deterministic token blocks --
    remains completely intact after this phase's `activate()`/`export()`
    changes. Neither `CoreModelService` nor
    `MiniBrainDatasetPipelineService` was modified this phase; this test
    proves that was the correct call, not merely an assumption."""

    async def test_valid_chain_remains_ready_and_deterministic(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id = _create_admin(api_app)
        tokenizer_id, _model, _vocab = _real_tokenizer_for_lifecycle(
            settings, name_suffix="regress-valid", lifecycle_status="active",
        )
        core_model_version_id = _real_core_model_version(
            settings, admin_id, name_suffix="phase27j-regress", tokenizer_version_public_id=tokenizer_id,
        )
        dataset_id, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="phase27j-regress", record_texts=_generate_corpus(60, seed_offset=50000),
        )

        pipeline = MiniBrainDatasetPipelineService(settings)
        contract = pipeline.readiness_contract(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert contract["status"] == "READY", contract["reason"]

        first = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        second = pipeline.build_blocks(
            dataset_version_public_id=dataset_id, core_model_version_public_id=core_model_version_id,
        )
        assert first["train_blocks"] == second["train_blocks"]
        assert first["validation_blocks"] == second["validation_blocks"]
        assert first["dataset_checksum_sha256"] == second["dataset_checksum_sha256"]

        with database_connection(settings.resolved_database_path) as connection:
            vocab_size = connection.execute(
                "SELECT vocabulary_size FROM tokenizer_versions WHERE public_id=?", (tokenizer_id,)
            ).fetchone()["vocabulary_size"]
        for block in first["train_blocks"] + first["validation_blocks"]:
            assert all(0 <= token_id < vocab_size for token_id in block)
