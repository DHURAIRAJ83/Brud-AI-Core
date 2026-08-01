import hashlib
import json

import pytest
import sentencepiece as spm
from fastapi import FastAPI

from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.repositories.pretraining import PretrainingRepository
from backend.models.pretraining import PretrainingJobCreate
from backend.models.tokenizers import SPECIAL_TOKENS
from backend.services.pretraining_service import PretrainingService
from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

ADMIN = "00000000-0000-0000-0000-000000000001"

VOCAB_SIZE = 160
HIDDEN_SIZE = 32
CONTEXT_LENGTH = 64

# (record_type, language, instruction, input_text, output_text, normalized_input,
#  metadata, split)
RECORDS = [
    ("instruction", "ta", "வணக்கம் என்றால் என்ன", None, "வணக்கம் என்பது ஒரு வாழ்த்து சொல்", None, {}, "train"),
    ("instruction", "ta", "இது என்ன மொழி", None, "இது தமிழ் மொழி", None, {}, "train"),
    (
        "instruction", "en", "What is hello", None, "Hello is a common greeting word", None, {},
        "train",
    ),
    (
        "instruction", "en", "Say the alphabet start", None, "A is the first letter", None, {},
        "train",
    ),
    ("instruction", "tgl", "epdi irukeenga", None, "நல்லா இருக்கேன் நன்றி", None, {}, "train"),
    (
        "instruction", "mixed", "laptop pathi sollunga", None, "Laptop ஒரு கணினி சாதனம்", None, {},
        "train",
    ),
    (
        "instruction", "ta", "பள்ளி பற்றி சொல்லுங்கள்", None, "பள்ளி கல்வி கற்கும் இடம்", None, {},
        "validation",
    ),
    ("instruction", "en", "Describe water", None, "Water is essential for life", None, {}, "test"),
    (
        "chat", "en", None, None, None, None,
        {"turns": [
            {"role": "user", "content": "Hi there"},
            {"role": "assistant", "content": "Hello, how can I help you today"},
        ]},
        "train",
    ),
    (
        "chat", "ta", None, None, None, None,
        {"turns": [
            {"role": "system", "content": "நீங்கள் ஒரு உதவியாளர்"},
            {"role": "user", "content": "நலமா"},
            {"role": "assistant", "content": "நலம் நன்றி"},
        ]},
        "train",
    ),
    (
        "chat", "en", None, None, None, None,
        {"turns": [
            {"role": "user", "content": "What time is it"},
            {"role": "assistant", "content": "I cannot check the time right now"},
        ]},
        "validation",
    ),
    ("chat", "en", None, "Good morning", "Good morning to you too", None, {}, "train"),
    ("chat", "ta", None, "காலை வணக்கம்", "காலை வணக்கம் உங்களுக்கும்", None, {}, "train"),
    ("chat", "en", None, "How are you", "I am doing well thank you", None, {}, "test"),
    (
        "translation", "mixed", None, "வணக்கம் எப்படி இருக்கீங்க", "Hello how are you", None,
        {"source_language": "ta", "target_language": "en"}, "train",
    ),
    (
        "translation", "mixed", None, "Thank you very much", "மிக்க நன்றி", None,
        {"source_language": "en", "target_language": "ta"}, "train",
    ),
    (
        "translation", "mixed", None, "Good night", "இனிய இரவு", None,
        {"source_language": "en", "target_language": "ta"}, "validation",
    ),
    (
        "tanglish_pair", "tgl", None, "eppadi irukeenga", "எப்படி இருக்கீங்க",
        "எப்படி இருக்கீங்க", {}, "train",
    ),
    (
        "tanglish_pair", "tgl", None, "naan nalla iruken", "நான் நல்லா இருக்கேன்",
        "நான் நல்லா இருக்கேன்", {}, "train",
    ),
    (
        "tanglish_pair", "tgl", None, "office ku poren", "நான் அலுவலகத்திற்கு செல்கிறேன்",
        "நான் அலுவலகத்திற்கு செல்கிறேன்", {}, "test",
    ),
    (
        "safety", "en", None, "How do I pick a lock",
        "I can't help with that, but a locksmith can assist safely", None, {}, "train",
    ),
    ("safety", "ta", None, "ஆபத்தான வேலை செய்யலாமா", "இல்லை, பாதுகாப்பாக செயல்படுங்கள்", None, {}, "train"),
    (
        "preference", "en", "pick better", None, None, None,
        {"chosen_output": "A clear concise answer", "rejected_output": "An unhelpful vague answer"},
        "train",
    ),
    (
        "preference", "en", "pick better again", None, None, None,
        {"chosen_output": "A helpful detailed reply", "rejected_output": "A rude dismissive reply"},
        "train",
    ),
]


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _corpus_text(entry: tuple) -> list[str]:
    _, _, instruction, input_text, output_text, normalized_input, metadata, _ = entry
    lines = []
    for field in (instruction, input_text, output_text, normalized_input):
        if field:
            lines.append(field)
    for turn in metadata.get("turns", []):
        if turn.get("content"):
            lines.append(turn["content"])
    for key in ("chosen_output", "rejected_output"):
        if metadata.get(key):
            lines.append(metadata[key])
    return lines


def _create_tokenizer_artifact(app: FastAPI, name: str) -> tuple[int, str, str, str, list[str]]:
    settings = app.state.settings
    corpus = settings.resolved_tokenizer_corpus_dir / f"{name}-corpus.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for entry in RECORDS:
        lines.extend(_corpus_text(entry))
    corpus.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temp_prefix = settings.resolved_tokenizer_dir / f"{name}-tokenizer"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus),
        model_prefix=str(temp_prefix),
        model_type="bpe",
        vocab_size=VOCAB_SIZE,
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
        list(SPECIAL_TOKENS),
    )


def _model_config(vocab_size: int) -> BrudModelConfig:
    return BrudModelConfig(
        vocabulary_size=vocab_size,
        context_length=CONTEXT_LENGTH,
        hidden_size=HIDDEN_SIZE,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=2,
        num_key_value_heads=2,
        pad_token_id=0, bos_token_id=2, eos_token_id=3, unk_token_id=1,
    )


def _fixture_refs(app: FastAPI) -> dict[str, str]:
    settings = app.state.settings
    database = settings.resolved_database_path
    vocab_size, model_checksum, vocab_checksum, artifact_manifest_json, special_tokens = (
        _create_tokenizer_artifact(app, "instrtune")
    )

    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
            licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
            (
                "50000000-0000-0000-0000-000000000001", "Instruction Tuning Source", "manual",
                "ready", "mixed", "approved", "{}",
            ),
        )
        source_id = connection.execute("SELECT id FROM dataset_sources").fetchone()[0]
        record_ids = []
        for idx, entry in enumerate(RECORDS):
            record_type, language, instruction, input_text, output_text = entry[0:5]
            normalized_input, metadata, _split = entry[5], entry[6], entry[7]
            public_id = f"50000000-0000-0000-0000-0000000001{idx:02d}"
            body = output_text or input_text or instruction or "record"
            connection.execute(
                """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                record_type,instruction,input_text,output_text,normalized_input,content_hash,
                metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id, source_id, body, language, "approved", record_type,
                    instruction, input_text, output_text, normalized_input, f"h{idx}" * 8,
                    dumps_json(metadata),
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
                "50000000-0000-0000-0000-000000000200", "instruction-tuning-fixture", "v1",
                "ready", "d" * 64, len(record_ids), json.dumps({}), json.dumps({}),
            ),
        )
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?",
            ("50000000-0000-0000-0000-000000000200",),
        ).fetchone()[0]
        for sequence_number, (record_id, entry) in enumerate(zip(record_ids, RECORDS, strict=True)):
            connection.execute(
                """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,split,
                sequence_number) VALUES (?,?,?,?)""",
                (dataset_id, record_id, entry[7], sequence_number),
            )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            (
                "50000000-0000-0000-0000-000000000300", "instrtune", "Instruction Tuning Tok",
                "active",
            ),
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
                "50000000-0000-0000-0000-000000000301", family_id, "v1", "active", "bpe",
                vocab_size, 0.9995, "nmt_nfkc", "sentencepiece", dataset_id, "a" * 64,
                model_checksum, vocab_checksum, artifact_manifest_json,
                dumps_json(special_tokens),
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
            ("50000000-0000-0000-0000-000000000400", "instrtune-core", "Instr Tune Core", "active"),
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
                "50000000-0000-0000-0000-000000000401", "micro", "v1", vocab_size,
                CONTEXT_LENGTH, HIDDEN_SIZE, 64, 2, 2, 2, HIDDEN_SIZE // 2, 10000.0, 1e-6,
                0.0, 0.0, 0.0, 0.02, 1, 0, 0, 2, 3, 1,
                tokenizer_id, 10000, 1000000, "f" * 64, "validated", ADMIN,
            ),
        )
        config_id = connection.execute("SELECT id FROM core_model_configs").fetchone()[0]
        model_config = _model_config(vocab_size)
        model = BrudForCausalLM(model_config)
        actual_params = sum(parameter.numel() for parameter in model.parameters())
        connection.execute(
            """INSERT INTO core_model_versions(public_id,core_model_family_id,version,
            lifecycle_status,config_id,tokenizer_version_id,architecture_name,
            estimated_parameter_count,actual_parameter_count,
            estimated_inference_memory_bytes,estimated_training_memory_bytes,
            initialization_seed,config_checksum_sha256,architecture_summary_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "50000000-0000-0000-0000-000000000402", core_family_id, "v1", "staging",
                config_id, tokenizer_id, "brud_decoder_transformer",
                actual_params, actual_params, 1000000, 2000000, 123, "f" * 64,
                dumps_json(
                    {"base_pretrained": True, "not_instruction_tuned": True, "not_chat_ready": True}
                ),
            ),
        )
        core_model_id = connection.execute(
            "SELECT id FROM core_model_versions WHERE public_id=?",
            ("50000000-0000-0000-0000-000000000402",),
        ).fetchone()[0]
        connection.commit()

    pretraining_repository = PretrainingRepository(database)
    pretraining_service = PretrainingService(pretraining_repository, settings)
    job = pretraining_service.create_job(
        PretrainingJobCreate(
            name="base pretraining source job",
            dataset_version_public_id="50000000-0000-0000-0000-000000000200",
            tokenizer_version_public_id="50000000-0000-0000-0000-000000000301",
            core_model_version_public_id="50000000-0000-0000-0000-000000000402",
            job_mode="bounded_pretraining",
            configuration={
                "batch_size": 1, "gradient_accumulation_steps": 1, "sequence_length": 32,
                "total_steps": 2, "checkpoint_interval_steps": 0, "validation_interval_steps": 2,
                "metric_interval_steps": 1, "learning_rate": 0.001, "scheduler": "constant",
            },
        ),
        ADMIN,
    )
    pretraining_service.validate_job(job["public_id"], ADMIN)
    with database_connection(database) as connection:
        job_id = connection.execute(
            "SELECT id FROM pretraining_jobs WHERE public_id=?", (job["public_id"],)
        ).fetchone()[0]
        connection.execute(
            """UPDATE pretraining_jobs SET status='completed',completed_steps=2,
            latest_training_loss=4.0,latest_validation_loss=4.5,best_validation_loss=4.5
            WHERE id=?""",
            (job_id,),
        )
        connection.commit()

    checkpoint_dir = settings.resolved_pretraining_dir / "base-source-checkpoint"
    saved = TrainingCheckpointManager(
        settings.resolved_pretraining_dir, settings.core_checkpoint_max_bytes
    ).save(
        checkpoint_dir,
        model=model,
        optimizer=None,
        scheduler=None,
        optimizer_state={"state": {}, "param_groups": []},
        scheduler_state={"placeholder": True},
        rng_state=None,
        trainer_state={"step": 2, "processed_tokens": 100, "block_index": 2, "status": "completed"},
        config={},
        references={"job_public_id": job["public_id"]},
    )
    with database_connection(database) as connection:
        checkpoint_public_id = "50000000-0000-0000-0000-000000000500"
        connection.execute(
            """INSERT INTO pretraining_checkpoints(public_id,pretraining_job_id,
            core_model_version_id,checkpoint_kind,status,step,processed_tokens,safe_name,
            file_size_bytes,manifest_json,model_checksum_sha256,optimizer_checksum_sha256,
            scheduler_checksum_sha256,trainer_state_checksum_sha256,combined_checksum_sha256,
            training_loss,validation_loss,is_best,is_latest)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                checkpoint_public_id, job_id, core_model_id, "final", "completed", 2, 100,
                "base-source-checkpoint", saved["file_size_bytes"], dumps_json(saved["manifest"]),
                saved["model_checksum_sha256"], saved["optimizer_checksum_sha256"],
                saved["scheduler_checksum_sha256"], saved["trainer_state_checksum_sha256"],
                saved["combined_checksum_sha256"], 4.0, 4.5, 1, 1,
            ),
        )
        connection.commit()

    return {
        "dataset": "50000000-0000-0000-0000-000000000200",
        "tokenizer": "50000000-0000-0000-0000-000000000301",
        "base_model": "50000000-0000-0000-0000-000000000402",
    }


def _run_config() -> dict:
    return {
        "batch_size": 1,
        "gradient_accumulation_steps": 1,
        "sequence_length": 48,
        "total_steps": 6,
        "checkpoint_interval_steps": 3,
        "validation_interval_steps": 6,
        "metric_interval_steps": 1,
        "learning_rate": 0.001,
        "scheduler": "constant",
    }


async def _setup_experiment(client, headers, refs) -> str:
    created = await client.post(
        "/api/admin/instruction-tuning/experiments",
        headers=headers,
        json={
            "name": "Instruction tuning test experiment",
            "base_core_model_version_public_id": refs["base_model"],
            "dataset_version_public_id": refs["dataset"],
        },
    )
    assert created.status_code == 200, created.text
    experiment_id = created.json()["public_id"]

    template_created = await client.post(
        "/api/admin/instruction-tuning/templates",
        headers=headers,
        json={
            "name": "brud-instruction", "version": "1",
            "tokenizer_version_public_id": refs["tokenizer"],
        },
    )
    assert template_created.status_code == 200, template_created.text
    template_id = template_created.json()["public_id"]
    assert template_created.json()["is_valid"] == 1

    patched = await client.patch(
        f"/api/admin/instruction-tuning/experiments/{experiment_id}",
        headers=headers,
        json={"instruction_template_public_id": template_id},
    )
    assert patched.status_code == 200, patched.text

    profile = await client.post(
        f"/api/admin/instruction-tuning/experiments/{experiment_id}/profile", headers=headers
    )
    assert profile.status_code == 200, profile.text
    return experiment_id


async def test_experiment_rejects_ineligible_base_model(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            connection.execute(
                "UPDATE core_model_versions SET lifecycle_status='architecture_verified' "
                "WHERE public_id=?",
                (refs["base_model"],),
            )
            connection.commit()
        rejected = await client.post(
            "/api/admin/instruction-tuning/experiments",
            headers=headers,
            json={
                "name": "should fail",
                "base_core_model_version_public_id": refs["base_model"],
                "dataset_version_public_id": refs["dataset"],
            },
        )
        assert rejected.status_code in {400, 422}
    finally:
        await client.aclose()


async def test_experiment_profile_and_template(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        unauthenticated = await client.post(
            "/api/admin/instruction-tuning/experiments",
            json={
                "name": "no auth",
                "base_core_model_version_public_id": refs["base_model"],
                "dataset_version_public_id": refs["dataset"],
            },
        )
        assert unauthenticated.status_code == 403

        experiment_id = await _setup_experiment(client, headers, refs)

        profile = await client.get(
            f"/api/admin/instruction-tuning/experiments/{experiment_id}/profile"
        )
        assert profile.status_code == 200
        body = profile.json()
        assert body["eligible_records"] > 0
        assert body["excluded_records"] >= 2  # the two preference records
        assert "preference_optimization_out_of_scope_phase12" in body["exclusion_reasons"]
        assert body["data_sufficiency_status"] == "limited_instruction_experiment"
        payload_text = json.dumps(body)
        assert "வணக்கம்" not in payload_text
        assert "Hello is a common greeting word" not in payload_text
    finally:
        await client.aclose()


async def test_run_lifecycle_and_worker_dispatch_isolation(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        experiment_id = await _setup_experiment(client, headers, refs)

        run = await client.post(
            f"/api/admin/instruction-tuning/experiments/{experiment_id}/runs",
            headers=headers,
            json={"run_label": "Run A", "configuration": _run_config(), "config_diff": {}},
        )
        assert run.status_code == 200, run.text
        run_id = run.json()["public_id"]

        queued = await client.post(
            f"/api/admin/instruction-tuning/runs/{run_id}/queue", headers=headers
        )
        assert queued.status_code == 200, queued.text

        # the generic base-pretraining worker must never claim this job
        base_worker_result = PretrainingService(
            PretrainingRepository(api_app.state.settings.resolved_database_path),
            api_app.state.settings,
        ).run_one("base-pretraining-worker-should-not-claim")
        assert base_worker_result is None

        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            still_queued = connection.execute(
                "SELECT status FROM pretraining_jobs WHERE id=(SELECT pretraining_job_id "
                "FROM instruction_tuning_runs WHERE public_id=?)",
                (run_id,),
            ).fetchone()
        assert still_queued["status"] == "queued"
        from backend.database.repositories.instruction_tuning import InstructionTuningRepository
        from backend.services.instruction_tuning_service import InstructionTuningService

        service = InstructionTuningService(
            InstructionTuningRepository(api_app.state.settings.resolved_database_path),
            PretrainingRepository(api_app.state.settings.resolved_database_path),
            api_app.state.settings,
        )
        result = service.run_one("instruction-tuning-worker")
        assert result["status"] == "completed"
        assert result["assistant_target_tokens"] > 0
        assert result["prompt_tokens"] > 0

        evaluated = await client.post(
            f"/api/admin/instruction-tuning/runs/{run_id}/evaluate", headers=headers
        )
        assert evaluated.status_code == 200, evaluated.text

        metrics = await client.get(f"/api/admin/instruction-tuning/runs/{run_id}/metrics")
        assert metrics.status_code == 200
        assert len(metrics.json()["items"]) > 0

        language_metrics = await client.get(
            f"/api/admin/instruction-tuning/runs/{run_id}/language-metrics"
        )
        assert language_metrics.status_code == 200
        languages = {item["language"] for item in language_metrics.json()["items"]}
        assert {"ta", "en", "tgl", "mixed", "overall"} <= languages

        checks = await client.get(f"/api/admin/instruction-tuning/runs/{run_id}/learning-checks")
        assert checks.status_code == 200
        codes = {item["check_code"] for item in checks.json()["items"]}
        assert codes == {
            "response_only_masking_verified", "training_loss_improves",
            "validation_response_loss_finite", "language_metrics_complete",
            "instruction_format_compliance", "role_token_leakage_bounded",
            "prompt_leakage_bounded", "repetition_bounded", "memorization_risk_bounded",
            "checkpoint_integrity", "base_model_lineage_complete", "resource_limits_respected",
        }

        diagnostic = await client.post(
            f"/api/admin/instruction-tuning/runs/{run_id}/diagnostic-generate",
            headers=headers,
            json={"prompt_text": "Say hello", "max_new_tokens": 8},
        )
        assert diagnostic.status_code == 200, diagnostic.text
        assert "not the public chatbot" in diagnostic.json()["notice"]

        diagnostic_unauth = await client.post(
            f"/api/admin/instruction-tuning/runs/{run_id}/diagnostic-generate",
            json={"prompt_text": "Say hello"},
        )
        assert diagnostic_unauth.status_code == 403
    finally:
        await client.aclose()


async def test_candidate_selection_promotes_and_remains_not_public_chat_ready(
    api_app: FastAPI,
) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        experiment_id = await _setup_experiment(client, headers, refs)

        run = await client.post(
            f"/api/admin/instruction-tuning/experiments/{experiment_id}/runs",
            headers=headers,
            json={"run_label": "Only run", "configuration": _run_config(), "config_diff": {}},
        )
        run_id = run.json()["public_id"]
        await client.post(f"/api/admin/instruction-tuning/runs/{run_id}/queue", headers=headers)

        from backend.database.repositories.instruction_tuning import InstructionTuningRepository
        from backend.services.instruction_tuning_service import InstructionTuningService

        service = InstructionTuningService(
            InstructionTuningRepository(api_app.state.settings.resolved_database_path),
            PretrainingRepository(api_app.state.settings.resolved_database_path),
            api_app.state.settings,
        )
        result = service.run_one("instruction-tuning-worker")
        assert result["status"] == "completed"
        await client.post(f"/api/admin/instruction-tuning/runs/{run_id}/evaluate", headers=headers)

        base_checkpoint_before = _sha256_of_base_checkpoint(api_app)

        selected = await client.post(
            f"/api/admin/instruction-tuning/experiments/{experiment_id}/select-candidate",
            headers=headers,
        )
        assert selected.status_code == 200, selected.text
        candidate = selected.json()
        assert candidate["status"] in {
            "instruction_tuned_candidate", "instruction_tuned_with_warnings",
        }

        base_checkpoint_after = _sha256_of_base_checkpoint(api_app)
        assert base_checkpoint_before == base_checkpoint_after

        fetched = await client.get(
            f"/api/admin/instruction-tuning/experiments/{experiment_id}/candidate"
        )
        assert fetched.status_code == 200
        assert fetched.json()["status"] == candidate["status"]

        promoted_public_id = candidate["rationale"]["promoted_model_public_id"]
        assert promoted_public_id
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            row = connection.execute(
                "SELECT lifecycle_status,architecture_summary_json FROM core_model_versions "
                "WHERE public_id=?",
                (promoted_public_id,),
            ).fetchone()
        assert row["lifecycle_status"] == "staging"
        summary = json.loads(row["architecture_summary_json"])
        assert summary["instruction_tuned"] is True
        assert summary["base_pretrained"] is True
        assert summary["evaluation_required"] is True
        assert summary["not_public_chat_ready"] is True

        chat = await client.post("/api/chat", json={"message": "வணக்கம்"})
        assert "route_used" in chat.json()

        manifest = await client.get(
            f"/api/admin/instruction-tuning/experiments/{experiment_id}/manifest"
        )
        assert manifest.status_code == 200
        manifest_body = manifest.json()
        manifest_text = json.dumps(manifest_body)
        assert "/home/" not in manifest_text
        assert str(api_app.state.settings.resolved_pretraining_dir) not in manifest_text

        verify = await client.post(
            f"/api/admin/instruction-tuning/experiments/{experiment_id}/manifest/verify",
            headers=headers,
        )
        assert verify.status_code == 200
        assert verify.json()["matches"] is True

        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            experiment_row_id = connection.execute(
                "SELECT id FROM instruction_tuning_experiments WHERE public_id=?",
                (experiment_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO instruction_reproducibility_manifests(public_id,
                instruction_tuning_experiment_id,manifest_json,manifest_checksum_sha256)
                VALUES (?,?,?,?)""",
                (
                    "60000000-0000-0000-0000-000000000001", experiment_row_id,
                    json.dumps(manifest_body["manifest"]), "0" * 64,
                ),
            )
            connection.commit()
        tampered = await client.post(
            f"/api/admin/instruction-tuning/experiments/{experiment_id}/manifest/verify",
            headers=headers,
        )
        assert tampered.json()["matches"] is False
    finally:
        await client.aclose()


def _sha256_of_base_checkpoint(app: FastAPI) -> str:
    settings = app.state.settings
    with database_connection(settings.resolved_database_path) as connection:
        row = connection.execute(
            "SELECT safe_name FROM pretraining_checkpoints WHERE public_id=?",
            ("50000000-0000-0000-0000-000000000500",),
        ).fetchone()
    target = settings.resolved_pretraining_dir / row["safe_name"] / "model_state.pt"
    return _sha256(target)
