import hashlib
from pathlib import Path

import pytest
import sentencepiece as spm

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.tokenizers import SPECIAL_TOKENS
from backend.services.incremental_training_execution_service import (
    IncrementalTrainingExecutionService,
)
from backend.services.incremental_training_run_approval_service import (
    IncrementalTrainingRunApprovalService,
)
from backend.services.training_dataset_promotion_service import TrainingDatasetPromotionService
from backend.services.training_resource_preview_service import TrainingResourcePreviewService
from tests.backend.test_training_contamination_replay_and_promotion import _approved_candidate
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "incremental_training.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus",
        tokenizer_dir=tmp_path / "tokenizers",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _create_tokenizer_artifact(settings: Settings) -> tuple[int, str, str, str]:
    corpus = settings.resolved_tokenizer_corpus_dir / "phase14-test-corpus.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_text(
        "\n".join(["வணக்கம் hello tanglish mixed", "Say hello வணக்கம் hello"]) + "\n",
        encoding="utf-8",
    )
    temp_prefix = settings.resolved_tokenizer_dir / "phase14-test-tokenizer"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus), model_prefix=str(temp_prefix), model_type="bpe", vocab_size=64,
        character_coverage=0.9995, hard_vocab_limit=False, pad_id=0, unk_id=1, bos_id=2, eos_id=3,
        pad_piece="<pad>", unk_piece="<unk>", bos_piece="<bos>", eos_piece="<eos>",
        user_defined_symbols=",".join(SPECIAL_TOKENS[4:]),
    )
    artifact_dir = settings.resolved_tokenizer_dir / "versions" / "tok14" / "v1"
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
    return (
        processor.vocab_size(), manifest["model_checksum_sha256"],
        manifest["vocabulary_checksum_sha256"], dumps_json(manifest),
    )


def _pretraining_refs(settings: Settings, dataset_version_public_id: str) -> dict[str, str]:
    """Mirrors tests/backend/test_pretraining_api.py::_fixture_refs, adapted
    to bind a tokenizer/model onto an *existing* Phase 14 dataset version
    instead of creating a new one."""

    vocab_size, model_checksum, vocab_checksum, artifact_manifest_json = (
        _create_tokenizer_artifact(settings)
    )
    with database_connection(settings.resolved_database_path) as connection:
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_version_public_id,)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO tokenizer_families(public_id,name,display_name,status) VALUES (?,?,?,?)",
            ("00000000-0000-0000-0000-0000000f9031", "tok14", "Tok14", "active"),
        )
        family_id = connection.execute(
            "SELECT id FROM tokenizer_families WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000f9031",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
            lifecycle_status,algorithm,vocabulary_size,character_coverage,
            normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
            model_checksum_sha256,vocabulary_checksum_sha256,artifact_manifest_json,
            special_tokens_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000f9032", family_id, "v1", "active", "bpe",
                vocab_size, 0.9995, "nmt_nfkc", "sentencepiece", dataset_id, "a" * 64,
                model_checksum, vocab_checksum, artifact_manifest_json,
                dumps_json(SPECIAL_TOKENS),
            ),
        )
        tokenizer_id = connection.execute(
            "SELECT id FROM tokenizer_versions WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000f9032",),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO core_model_families(public_id,name,display_name,status) VALUES (?,?,?,?)",
            ("00000000-0000-0000-0000-0000000f9041", "brud-core14", "Brud Core 14", "active"),
        )
        core_family_id = connection.execute(
            "SELECT id FROM core_model_families WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000f9041",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO core_model_configs(public_id,name,config_version,vocabulary_size,
            context_length,hidden_size,intermediate_size,num_hidden_layers,num_attention_heads,
            num_key_value_heads,head_dimension,rope_theta,rms_norm_epsilon,attention_dropout,
            residual_dropout,embedding_dropout,initializer_range,tie_word_embeddings,use_bias,
            pad_token_id,bos_token_id,eos_token_id,unk_token_id,tokenizer_version_id,
            parameter_count_estimate,memory_estimate_bytes,configuration_json,
            config_checksum_sha256,status,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000f9042", "micro14", "v1", vocab_size, 16, 16, 32,
                1, 2, 2, 8, 10000, 1e-6, 0, 0, 0, 0.02, 1, 0, 0, 2, 3, 1, tokenizer_id, 1000,
                1000000, "{}", "e" * 64, "validated", "test-admin",
            ),
        )
        config_id = connection.execute(
            "SELECT id FROM core_model_configs WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000f9042",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO core_model_versions(public_id,core_model_family_id,version,
            lifecycle_status,config_id,tokenizer_version_id,architecture_name,
            estimated_parameter_count,actual_parameter_count,estimated_inference_memory_bytes,
            estimated_training_memory_bytes,initialization_seed,weights_checksum_sha256,
            config_checksum_sha256,architecture_summary_json,metrics_summary_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000f9043", core_family_id, "v0.1",
                "architecture_verified", config_id, tokenizer_id, "brud_decoder_transformer",
                1000 + vocab_size, 1000 + vocab_size, 1000000, 2000000, 123, "f" * 64, "e" * 64,
                "{}", "{}",
            ),
        )
        connection.commit()
    return {
        "tokenizer": "00000000-0000-0000-0000-0000000f9032",
        "model": "00000000-0000-0000-0000-0000000f9043",
    }


def _materialized_promotion(settings: Settings, *, candidate_count: int = 1) -> dict:
    """`DatasetVersioningService._split_groups()` only allocates a
    non-empty validation split once 3+ distinct-content records exist
    (see backend/services/dataset_versioning.py); tests that actually
    execute a training run need `candidate_count=3` so the underlying
    trainer's "validation split has no tokenized records" guard passes."""

    candidate_public_ids = []
    assessment = None
    for index in range(candidate_count):
        assessment, candidate = _approved_candidate(
            settings, prompt=f"தமிழ் கேள்வி {index}?", assistant=f"தமிழ் பதில் {index}.",
            code_suffix=str(index),
        )
        candidate_public_ids.append(candidate["public_id"])
    promotion_service = TrainingDatasetPromotionService(settings)
    request = promotion_service.create_request(
        assessment["public_id"], {"candidate_public_ids": candidate_public_ids},
        admin_id=ADMIN_ID,
    )
    promotion_service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    promotion_service.approve(request["public_id"], admin_id=ADMIN_ID)
    return promotion_service.materialize(request["public_id"], admin_id=ADMIN_ID)


_TINY_CONFIG = {
    "batch_size": 1,
    "gradient_accumulation_steps": 1,
    "sequence_length": 8,
    "total_steps": 2,
    "epochs": 1,
    "learning_rate": 0.01,
    "checkpoint_interval_steps": 1,
    "validation_interval_steps": 1,
    "metric_interval_steps": 1,
    "maximum_checkpoints": 2,
}


# -- resource preview -------------------------------------------------------------------------


def test_build_preview_passes_within_bounds(settings: Settings) -> None:
    service = TrainingResourcePreviewService(settings)
    preview = service.build_preview("continued_pretraining", _TINY_CONFIG)
    assert preview["status"] == "pass_with_warnings"
    assert preview["blocked_reasons"] == []


def test_build_preview_blocks_excessive_steps(settings: Settings) -> None:
    service = TrainingResourcePreviewService(settings)
    with pytest.raises(ValidationError):
        service.build_preview("continued_pretraining", {**_TINY_CONFIG, "total_steps": 10_000_000})


def test_build_preview_blocks_zero_steps(settings: Settings) -> None:
    service = TrainingResourcePreviewService(settings)
    with pytest.raises(ValidationError):
        service.build_preview("continued_pretraining", {**_TINY_CONFIG, "total_steps": 0})


# -- run request + approval --------------------------------------------------------------------


def test_create_run_request_requires_materialized_promotion(settings: Settings) -> None:
    assessment, candidate = _approved_candidate(settings)
    promotion_service = TrainingDatasetPromotionService(settings)
    request = promotion_service.create_request(
        assessment["public_id"], {"candidate_public_ids": [candidate["public_id"]]},
        admin_id=ADMIN_ID,
    )
    approval_service = IncrementalTrainingRunApprovalService(settings)
    with pytest.raises(ValidationError):
        approval_service.create_run_request(
            request["public_id"],
            {"training_strategy": "continued_pretraining", "configuration": _TINY_CONFIG},
            admin_id=ADMIN_ID,
        )


def test_run_request_and_approval_round_trip(settings: Settings) -> None:
    promotion = _materialized_promotion(settings)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    approval_service = IncrementalTrainingRunApprovalService(settings)
    request = approval_service.create_run_request(
        promotion["public_id"],
        {
            "training_strategy": "continued_pretraining",
            "tokenizer_version_public_id": refs["tokenizer"],
            "configuration": {**_TINY_CONFIG, "core_model_version_public_id": refs["model"]},
        },
        admin_id=ADMIN_ID,
    )
    assert request["status"] == "draft"
    assert request["resource_preview"]["status"] == "pass_with_warnings"

    approval_service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    approval = approval_service.request_approval(request["public_id"], admin_id=ADMIN_ID)
    assert approval["status"] == "pending"

    approved = approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)
    assert approved["status"] == "approved"
    refreshed_request = TrainingIncrementalRepository(
        settings.resolved_database_path
    ).get_run_request(request["public_id"])
    assert refreshed_request["status"] == "approved"


def test_no_execution_strategy_uses_acknowledge_path(settings: Settings) -> None:
    promotion = _materialized_promotion(settings)
    approval_service = IncrementalTrainingRunApprovalService(settings)
    request = approval_service.create_run_request(
        promotion["public_id"], {"training_strategy": "no_training_rag_only"}, admin_id=ADMIN_ID,
    )
    approval_service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    approval = approval_service.request_approval(request["public_id"], admin_id=ADMIN_ID)
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)

    execution_service = IncrementalTrainingExecutionService(settings)
    with pytest.raises(ValidationError):
        execution_service.start_run(approval["public_id"], admin_id=ADMIN_ID)
    updated = execution_service.acknowledge_no_execution_strategy(
        approval["public_id"], admin_id=ADMIN_ID
    )
    assert updated["status"] == "started"


def test_start_run_rejects_unapproved(settings: Settings) -> None:
    promotion = _materialized_promotion(settings)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    approval_service = IncrementalTrainingRunApprovalService(settings)
    request = approval_service.create_run_request(
        promotion["public_id"],
        {
            "training_strategy": "continued_pretraining",
            "tokenizer_version_public_id": refs["tokenizer"],
            "configuration": {**_TINY_CONFIG, "core_model_version_public_id": refs["model"]},
        },
        admin_id=ADMIN_ID,
    )
    approval_service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    approval = approval_service.request_approval(request["public_id"], admin_id=ADMIN_ID)

    execution_service = IncrementalTrainingExecutionService(settings)
    with pytest.raises(ValidationError):
        execution_service.start_run(approval["public_id"], admin_id=ADMIN_ID)


# -- execution ----------------------------------------------------------------------------------


def test_start_run_executes_continued_pretraining_end_to_end(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    approval_service = IncrementalTrainingRunApprovalService(settings)
    request = approval_service.create_run_request(
        promotion["public_id"],
        {
            "training_strategy": "continued_pretraining",
            "tokenizer_version_public_id": refs["tokenizer"],
            "configuration": {**_TINY_CONFIG, "core_model_version_public_id": refs["model"]},
        },
        admin_id=ADMIN_ID,
    )
    approval_service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    approval = approval_service.request_approval(request["public_id"], admin_id=ADMIN_ID)
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)

    execution_service = IncrementalTrainingExecutionService(settings)
    run = execution_service.start_run(approval["public_id"], admin_id=ADMIN_ID)
    assert run["status"] in ("completed", "completed_with_warnings")
    assert run["underlying_run_kind"] == "pretraining_job"

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    checkpoints = training.list_checkpoints(run["public_id"])
    assert len(checkpoints) == 1
    assert checkpoints[0]["underlying_checkpoint_public_id"]

    events = training.list_run_events(run["public_id"])
    event_types = {event["event_type"] for event in events}
    assert "run_started" in event_types
    assert "run_finished" in event_types
