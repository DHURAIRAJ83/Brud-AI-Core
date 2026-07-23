import hashlib
import json

import pytest
import sentencepiece as spm
from fastapi import FastAPI

from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.repositories.pretraining import PretrainingRepository
from backend.models.tokenizers import SPECIAL_TOKENS
from backend.services.pretraining_service import PretrainingService
from core_model.training.learning_checks import (
    LearningCheckThresholds,
    classify_generalization,
    run_learning_checks,
)
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

ADMIN = "00000000-0000-0000-0000-000000000001"

def _pretrain(language: str, text: str, split: str) -> tuple:
    return ("pretrain", language, None, None, text, text, split)


def _instruction(language: str, question: str, answer: str, split: str) -> tuple:
    return ("instruction", language, question, None, answer, answer, split)


RECORDS = [
    # (record_type, language, instruction, input_text, output_text, content, split)
    _pretrain("ta", "வணக்கம் தமிழ் உலகம் அழகானது", "train"),
    _pretrain("ta", "இன்று நல்ல வானிலை உள்ளது", "train"),
    _pretrain("ta", "நூலகம் அறிவை வளர்க்கும் இடம்", "train"),
    _instruction("ta", "வணக்கம் என்றால் என்ன", "வணக்கம் என்பது ஒரு வாழ்த்து சொல்", "train"),
    _pretrain("en", "Hello English world today", "train"),
    _pretrain("en", "The weather is very pleasant", "train"),
    _pretrain("en", "Books help people learn things", "train"),
    _instruction("en", "What is hello", "Hello is a common greeting word", "train"),
    _pretrain("tgl", "vanakkam epdi irukeenga nalla iruku", "train"),
    _pretrain("tgl", "naan office ku poren innaiku", "train"),
    _pretrain("mixed", "இந்த laptop-ஐ configure பண்ண வேண்டும்", "train"),
    _pretrain("mixed", "This project தமிழ் மொழியில் உள்ளது", "train"),
    (
        "translation", "mixed", None, "வணக்கம் எப்படி இருக்கீங்க", "Hello how are you",
        "வணக்கம் எப்படி இருக்கீங்க Hello how are you", "train",
    ),
    _pretrain("ta", "மழை பெய்தது இன்று காலை", "validation"),
    _pretrain("en", "The train leaves at nine", "validation"),
    _pretrain("mixed", "Server maintenance இன்று night நடக்கும்", "validation"),
    _pretrain("ta", "பள்ளி செல்ல வேண்டும் நாளை", "test"),
    _pretrain("en", "Water boils at high heat", "test"),
]


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _create_tokenizer_artifact(app: FastAPI, name: str) -> tuple[int, str, str, str]:
    settings = app.state.settings
    corpus = settings.resolved_tokenizer_corpus_dir / f"{name}-corpus.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for entry in RECORDS:
        for field in (entry[3], entry[4], entry[5]):
            if field:
                lines.append(field)
    corpus.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temp_prefix = settings.resolved_tokenizer_dir / f"{name}-tokenizer"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus),
        model_prefix=str(temp_prefix),
        model_type="bpe",
        vocab_size=120,
        character_coverage=0.9995,
        hard_vocab_limit=False,
        pad_id=0, unk_id=1, bos_id=2, eos_id=3,
        pad_piece="<pad>", unk_piece="<unk>", bos_piece="<bos>", eos_piece="<eos>",
        user_defined_symbols=",".join(SPECIAL_TOKENS[4:]),
    )
    artifact_dir = settings.resolved_tokenizer_dir / "versions" / name / "v1"
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
        processor.vocab_size(),
        manifest["model_checksum_sha256"],
        manifest["vocabulary_checksum_sha256"],
        dumps_json(manifest),
    )


def _fixture_refs(app: FastAPI) -> dict[str, str]:
    database = app.state.settings.resolved_database_path
    vocab_size, model_checksum, vocab_checksum, artifact_manifest_json = _create_tokenizer_artifact(
        app, "basetrain"
    )
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
            licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
            (
                "30000000-0000-0000-0000-000000000001", "Base Training Source", "manual",
                "ready", "mixed", "approved", "{}",
            ),
        )
        source_id = connection.execute("SELECT id FROM dataset_sources").fetchone()[0]
        record_ids = []
        for idx, entry in enumerate(RECORDS):
            record_type, language = entry[0], entry[1]
            instruction, input_text, output_text, content = entry[2], entry[3], entry[4], entry[5]
            public_id = f"30000000-0000-0000-0000-0000000001{idx:02d}"
            body = content or output_text or input_text or ""
            connection.execute(
                """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                record_type,instruction,input_text,output_text,content_hash,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, source_id, body, language, "approved", record_type,
                    instruction, input_text, output_text, f"h{idx}" * 8, "{}",
                ),
            )
            record_ids.append(
                connection.execute(
                    "SELECT id FROM dataset_records WHERE public_id=?", (public_id,)
                ).fetchone()[0]
            )
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256,
            record_count,split_distribution_json,manifest_json) VALUES (?,?,?,?,?,?,?,?)""",
            (
                "30000000-0000-0000-0000-000000000200", "base-training-fixture", "v1", "ready",
                "d" * 64, len(record_ids), json.dumps({}), json.dumps({}),
            ),
        )
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?",
            ("30000000-0000-0000-0000-000000000200",),
        ).fetchone()[0]
        for sequence_number, (record_id, entry) in enumerate(zip(record_ids, RECORDS, strict=True)):
            split = entry[-1]
            connection.execute(
                """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,split,
                sequence_number) VALUES (?,?,?,?)""",
                (dataset_id, record_id, split, sequence_number),
            )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            ("30000000-0000-0000-0000-000000000300", "basetrain", "Base Train Tok", "active"),
        )
        family_id = connection.execute("SELECT id FROM tokenizer_families").fetchone()[0]
        connection.execute(
            """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
            lifecycle_status,algorithm,vocabulary_size,character_coverage,
            normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
            model_checksum_sha256,vocabulary_checksum_sha256,artifact_manifest_json,
            special_tokens_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "30000000-0000-0000-0000-000000000301", family_id, "v1", "active", "bpe",
                vocab_size, 0.9995, "nmt_nfkc", "sentencepiece", dataset_id, "a" * 64,
                model_checksum, vocab_checksum, artifact_manifest_json, dumps_json(SPECIAL_TOKENS),
            ),
        )
        tokenizer_id = connection.execute("SELECT id FROM tokenizer_versions").fetchone()[0]
        connection.execute(
            """INSERT INTO tokenizer_assignments(assignment_key,tokenizer_version_id,enabled,
            configuration_json) VALUES ('default',?,1,'{}')""",
            (tokenizer_id,),
        )
        connection.execute(
            """INSERT INTO core_model_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            ("30000000-0000-0000-0000-000000000400", "basetrain-core", "Base Train Core", "active"),
        )
        core_family_id = connection.execute("SELECT id FROM core_model_families").fetchone()[0]
        connection.execute(
            """INSERT INTO core_model_configs(public_id,name,config_version,vocabulary_size,
            context_length,hidden_size,intermediate_size,num_hidden_layers,num_attention_heads,
            num_key_value_heads,head_dimension,rope_theta,rms_norm_epsilon,attention_dropout,
            residual_dropout,embedding_dropout,initializer_range,tie_word_embeddings,use_bias,
            pad_token_id,bos_token_id,eos_token_id,unk_token_id,tokenizer_version_id,
            parameter_count_estimate,memory_estimate_bytes,config_checksum_sha256,status,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "30000000-0000-0000-0000-000000000401", "micro", "v1", vocab_size, 32, 16, 32,
                2, 2, 2, 8, 10000.0, 1e-6, 0.0, 0.0, 0.0, 0.02, 1, 0, 0, 2, 3, 1,
                tokenizer_id, 10000, 1000000, "f" * 64, "validated", ADMIN,
            ),
        )
        config_id = connection.execute("SELECT id FROM core_model_configs").fetchone()[0]
        connection.execute(
            """INSERT INTO core_model_versions(public_id,core_model_family_id,version,
            lifecycle_status,config_id,tokenizer_version_id,architecture_name,
            estimated_parameter_count,actual_parameter_count,
            estimated_inference_memory_bytes,estimated_training_memory_bytes,
            initialization_seed,config_checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "30000000-0000-0000-0000-000000000402", core_family_id, "v1",
                "architecture_verified", config_id, tokenizer_id, "brud_decoder_transformer",
                10000, 10000, 1000000, 2000000, 123, "f" * 64,
            ),
        )
        connection.commit()
    return {
        "dataset": "30000000-0000-0000-0000-000000000200",
        "tokenizer": "30000000-0000-0000-0000-000000000301",
        "core_model": "30000000-0000-0000-0000-000000000402",
    }


def _run_config() -> dict:
    return {
        "batch_size": 1,
        "gradient_accumulation_steps": 1,
        "sequence_length": 32,
        "total_steps": 10,
        "checkpoint_interval_steps": 5,
        "validation_interval_steps": 10,
        "metric_interval_steps": 1,
        "learning_rate": 0.001,
        "scheduler": "constant",
    }


async def test_create_experiment_and_generate_profile(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        unauthenticated = await client.post(
            "/api/admin/base-training/experiments",
            json={"name": "Test experiment", "dataset_version_public_id": refs["dataset"]},
        )
        assert unauthenticated.status_code == 403

        created = await client.post(
            "/api/admin/base-training/experiments",
            headers=headers,
            json={
                "name": "Test experiment",
                "objective": "Determine learning signal",
                "dataset_version_public_id": refs["dataset"],
            },
        )
        assert created.status_code == 200
        experiment_id = created.json()["public_id"]
        assert created.json()["tokenizer_decision"] == "not_evaluated"

        profile = await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/profile", headers=headers
        )
        assert profile.status_code == 200
        body = profile.json()
        assert body["total_records"] == len(RECORDS)
        assert body["train_count"] == 13
        assert body["validation_count"] == 3
        assert body["test_count"] == 2
        assert body["language_distribution"]["ta"] > 0
        assert body["language_distribution"]["en"] > 0
        assert body["language_distribution"]["tgl"] > 0
        assert body["language_distribution"]["mixed"] > 0
        assert body["data_sufficiency_status"] == "limited_experiment"
        assert body["profile_checksum_sha256"]
        payload_text = json.dumps(body)
        assert "வணக்கம்" not in payload_text
        assert "Hello English world" not in payload_text

        read_back = await client.get(
            f"/api/admin/base-training/experiments/{experiment_id}/profile"
        )
        assert read_back.status_code == 200
        assert read_back.json()["profile_checksum_sha256"] == body["profile_checksum_sha256"]

        tokenizer_eval = await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/tokenizer-evaluate",
            headers=headers,
        )
        assert tokenizer_eval.status_code == 200
        assert tokenizer_eval.json()["tokenizer_decision"] in {
            "reuse_existing_tokenizer", "train_new_tokenizer_version",
        }
    finally:
        await client.aclose()


async def test_run_lifecycle_language_metrics_and_learning_checks(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/base-training/experiments",
            headers=headers,
            json={"name": "Run test experiment", "dataset_version_public_id": refs["dataset"]},
        )
        experiment_id = created.json()["public_id"]
        await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/profile", headers=headers
        )
        await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/tokenizer-evaluate",
            headers=headers,
        )
        patched = await client.patch(
            f"/api/admin/base-training/experiments/{experiment_id}",
            headers=headers,
            json={"core_model_version_public_id": refs["core_model"]},
        )
        assert patched.status_code == 200
        assert patched.json()["tokenizer_version_public_id"] == refs["tokenizer"]

        run = await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/runs",
            headers=headers,
            json={
                "run_label": "Run A", "configuration": _run_config(),
                "config_diff": {"baseline": True},
            },
        )
        assert run.status_code == 200
        run_id = run.json()["public_id"]
        job_public_id = run.json()["pretraining_job_public_id"]
        assert job_public_id

        queued = await client.post(
            f"/api/admin/base-training/runs/{run_id}/queue", headers=headers
        )
        assert queued.status_code == 200

        result = PretrainingService(
            PretrainingRepository(api_app.state.settings.resolved_database_path),
            api_app.state.settings,
        ).run_one("base-training-test-worker")
        assert result["status"] == "completed"

        evaluated = await client.post(
            f"/api/admin/base-training/runs/{run_id}/evaluate", headers=headers
        )
        assert evaluated.status_code == 200
        eval_body = evaluated.json()
        languages = {item["language"] for item in eval_body["language_metrics"]}
        assert {"ta", "en", "tgl", "mixed"} <= languages
        for item in eval_body["language_metrics"]:
            if item["language"] in {"ta", "en"}:
                assert item["evaluated_records"] > 0

        metrics = await client.get(
            f"/api/admin/base-training/runs/{run_id}/language-metrics"
        )
        assert metrics.status_code == 200
        assert len(metrics.json()["items"]) >= 5

        checks = await client.get(f"/api/admin/base-training/runs/{run_id}/learning-checks")
        assert checks.status_code == 200
        codes = {item["check_code"] for item in checks.json()["items"]}
        assert codes == {
            "training_loss_improves", "validation_loss_finite", "test_loss_finite",
            "no_non_finite_gradients", "checkpoint_integrity", "dataset_stream_integrity",
            "language_metrics_complete", "generalization_gap_bounded", "memorization_risk_bounded",
            "tokenizer_coverage_adequate", "resource_limits_respected",
        }
        test_check = next(
            item for item in checks.json()["items"] if item["check_code"] == "test_loss_finite"
        )
        assert test_check["status"] == "warning"
    finally:
        await client.aclose()


async def test_candidate_selection_promotes_and_remains_not_chat_ready(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/base-training/experiments",
            headers=headers,
            json={"name": "Candidate experiment", "dataset_version_public_id": refs["dataset"]},
        )
        experiment_id = created.json()["public_id"]
        await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/profile", headers=headers
        )
        await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/tokenizer-evaluate",
            headers=headers,
        )
        await client.patch(
            f"/api/admin/base-training/experiments/{experiment_id}",
            headers=headers,
            json={"core_model_version_public_id": refs["core_model"]},
        )
        run = await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/runs",
            headers=headers,
            json={"run_label": "Only run", "configuration": _run_config(), "config_diff": {}},
        )
        run_id = run.json()["public_id"]
        await client.post(f"/api/admin/base-training/runs/{run_id}/queue", headers=headers)
        result = PretrainingService(
            PretrainingRepository(api_app.state.settings.resolved_database_path),
            api_app.state.settings,
        ).run_one("candidate-test-worker")
        assert result["status"] == "completed"
        await client.post(f"/api/admin/base-training/runs/{run_id}/evaluate", headers=headers)

        selected = await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/select-candidate",
            headers=headers,
        )
        assert selected.status_code == 200
        candidate = selected.json()
        assert candidate["status"] in {"selected_base_candidate", "selected_with_warnings"}
        assert candidate["generalization_result"] in {
            "optimization_success_only", "limited_generalization_evidence",
        }

        fetched = await client.get(
            f"/api/admin/base-training/experiments/{experiment_id}/candidate"
        )
        assert fetched.status_code == 200
        assert fetched.json()["status"] == candidate["status"]

        promoted_public_id = candidate["rationale"]["promoted_model_public_id"]
        assert promoted_public_id
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            row = connection.execute(
                """SELECT lifecycle_status,architecture_summary_json FROM core_model_versions
                WHERE public_id=?""",
                (promoted_public_id,),
            ).fetchone()
        assert row["lifecycle_status"] == "staging"
        summary = json.loads(row["architecture_summary_json"])
        assert summary["not_chat_ready"] is True
        assert summary["not_instruction_tuned"] is True

        chat = await client.post(
            "/api/chat", json={"message": "வணக்கம்", "language": "auto"}
        )
        assert chat.json()["model"] == "placeholder"

        manifest = await client.get(
            f"/api/admin/base-training/experiments/{experiment_id}/manifest"
        )
        assert manifest.status_code == 200
        manifest_body = manifest.json()
        limitations = manifest_body["manifest"]["known_limitations"]
        assert limitations["test_evaluation_notice"] == "TEST_EVALUATION_NOT_RELIABLE"
        manifest_text = json.dumps(manifest_body)
        assert "/home/" not in manifest_text
        assert str(api_app.state.settings.resolved_pretraining_dir) not in manifest_text

        verify = await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/manifest/verify",
            headers=headers,
        )
        assert verify.status_code == 200
        assert verify.json()["matches"] is True

        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            experiment_row_id = connection.execute(
                "SELECT id FROM base_training_experiments WHERE public_id=?", (experiment_id,)
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO base_training_reproducibility_manifests(public_id,
                base_training_experiment_id,manifest_json,manifest_checksum_sha256)
                VALUES (?,?,?,?)""",
                (
                    "40000000-0000-0000-0000-000000000001", experiment_row_id,
                    json.dumps(manifest_body["manifest"]), "0" * 64,
                ),
            )
            connection.commit()
        tampered = await client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/manifest/verify",
            headers=headers,
        )
        assert tampered.json()["matches"] is False
    finally:
        await client.aclose()


def test_learning_checks_pure_function_detects_divergence_and_gap() -> None:
    thresholds = LearningCheckThresholds(
        generalization_max_gap=3.0, memorization_max_gap=4.0, tokenizer_max_unknown_rate=0.05
    )
    good = run_learning_checks(
        {
            "initial_training_loss": 5.0,
            "final_training_loss": 2.0,
            "validation_loss": 2.5,
            "test_loss": None,
            "non_finite_event_count": 0,
            "checkpoint_verified": True,
            "stream_verified": True,
            "languages_with_metrics": {"ta", "en"},
            "languages_expected": {"ta", "en"},
            "train_validation_gap": 0.5,
            "unknown_token_rate": 0.01,
            "resource_limit_exceeded": False,
        },
        thresholds,
    )
    statuses = {item["check_code"]: item["status"] for item in good}
    assert statuses["training_loss_improves"] == "pass"
    assert statuses["generalization_gap_bounded"] == "pass"

    diverging = run_learning_checks(
        {
            "initial_training_loss": 2.0,
            "final_training_loss": 5.0,
            "validation_loss": 6.0,
            "test_loss": None,
            "non_finite_event_count": 1,
            "checkpoint_verified": False,
            "stream_verified": False,
            "languages_with_metrics": {"ta"},
            "languages_expected": {"ta", "en"},
            "train_validation_gap": 10.0,
            "unknown_token_rate": 0.5,
            "resource_limit_exceeded": True,
        },
        thresholds,
    )
    bad_statuses = {item["check_code"]: item["status"] for item in diverging}
    assert bad_statuses["training_loss_improves"] == "fail"
    assert bad_statuses["no_non_finite_gradients"] == "fail"
    assert bad_statuses["checkpoint_integrity"] == "fail"
    assert bad_statuses["dataset_stream_integrity"] == "fail"
    assert bad_statuses["language_metrics_complete"] == "warning"
    assert bad_statuses["generalization_gap_bounded"] == "warning"
    assert bad_statuses["tokenizer_coverage_adequate"] == "warning"
    assert bad_statuses["resource_limits_respected"] == "fail"


def test_classify_generalization_categories() -> None:
    assert classify_generalization(
        train_initial=5.0, train_final=2.0, validation_initial=None,
        validation_final=None, languages_with_improvement=0,
    ) == "not_assessed"
    assert classify_generalization(
        train_initial=5.0, train_final=5.0, validation_initial=5.0,
        validation_final=4.0, languages_with_improvement=1,
    ) == "not_assessed"
    assert classify_generalization(
        train_initial=5.0, train_final=2.0, validation_initial=5.0,
        validation_final=5.0, languages_with_improvement=0,
    ) == "optimization_success_only"
    assert classify_generalization(
        train_initial=5.0, train_final=2.0, validation_initial=5.0,
        validation_final=4.0, languages_with_improvement=1,
    ) == "limited_generalization_evidence"
