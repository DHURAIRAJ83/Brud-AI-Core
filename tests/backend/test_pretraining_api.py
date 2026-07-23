import hashlib
import json
import time
from threading import Thread

import pytest
import sentencepiece as spm
from fastapi import FastAPI

from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.repositories.pretraining import PretrainingRepository
from backend.models.tokenizers import SPECIAL_TOKENS
from backend.services.pretraining_service import PretrainingService
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _create_tokenizer_artifact(app: FastAPI) -> tuple[int, str, str, str]:
    settings = app.state.settings
    corpus = settings.resolved_tokenizer_corpus_dir / "phase9-test-corpus.txt"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_text(
        "\n".join(
            [
                "வணக்கம் hello tanglish mixed",
                "Say hello வணக்கம் hello",
                "தமிழ் English vanakkam",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    temp_prefix = settings.resolved_tokenizer_dir / "phase9-test-tokenizer"
    temp_prefix.parent.mkdir(parents=True, exist_ok=True)
    spm.SentencePieceTrainer.train(
        input=str(corpus),
        model_prefix=str(temp_prefix),
        model_type="bpe",
        vocab_size=64,
        character_coverage=0.9995,
        hard_vocab_limit=False,
        pad_id=0,
        unk_id=1,
        bos_id=2,
        eos_id=3,
        pad_piece="<pad>",
        unk_piece="<unk>",
        bos_piece="<bos>",
        eos_piece="<eos>",
        user_defined_symbols=",".join(SPECIAL_TOKENS[4:]),
    )
    artifact_dir = settings.resolved_tokenizer_dir / "versions" / "tok" / "v1"
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


def _fixture_refs(app: FastAPI, dataset_status: str = "ready") -> dict[str, str]:
    database = app.state.settings.resolved_database_path
    vocab_size, model_checksum, vocab_checksum, artifact_manifest_json = _create_tokenizer_artifact(
        app
    )
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO dataset_sources(public_id,name,source_type,status,language,
            licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-000000009001",
                "Phase 9 Source",
                "manual",
                "ready",
                "mixed",
                "approved",
                "{}",
            ),
        )
        source_id = connection.execute("SELECT id FROM dataset_sources").fetchone()[0]
        for idx, _split in enumerate(("train", "validation"), start=1):
            connection.execute(
                """INSERT INTO dataset_records(public_id,source_id,content,language,status,
                record_type,instruction,input_text,output_text,content_hash,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"00000000-0000-0000-0000-00000000901{idx}",
                    source_id,
                    "வணக்கம் hello tanglish mixed",
                    "mixed",
                    "approved",
                    "instruction",
                    "Say hello",
                    "வணக்கம்",
                    "hello",
                    f"h{idx}" * 32,
                    "{}",
                ),
            )
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256,
            record_count,split_distribution_json,manifest_json) VALUES (?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-000000009021",
                "phase9",
                "v1",
                dataset_status,
                "d" * 64,
                2,
                json.dumps({"train": 1, "validation": 1}),
                json.dumps({"content_checksum": "d" * 64}),
            ),
        )
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?",
            ("00000000-0000-0000-0000-000000009021",),
        ).fetchone()[0]
        records = connection.execute("SELECT id FROM dataset_records ORDER BY id").fetchall()
        for idx, row in enumerate(records):
            connection.execute(
                """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,split,
                sequence_number) VALUES (?,?,?,?)""",
                (dataset_id, row["id"], "train" if idx == 0 else "validation", idx),
            )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-000000009031", "tok", "Tok", "active"),
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
                "00000000-0000-0000-0000-000000009032",
                family_id,
                "v1",
                "active",
                "bpe",
                vocab_size,
                0.9995,
                "nmt_nfkc",
                "sentencepiece",
                dataset_id,
                "a" * 64,
                model_checksum,
                vocab_checksum,
                artifact_manifest_json,
                dumps_json(SPECIAL_TOKENS),
            ),
        )
        tokenizer_id = connection.execute("SELECT id FROM tokenizer_versions").fetchone()[0]
        connection.execute(
            """INSERT INTO core_model_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-000000009041", "brud-core", "Brud Core", "active"),
        )
        core_family_id = connection.execute("SELECT id FROM core_model_families").fetchone()[0]
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
                "00000000-0000-0000-0000-000000009042",
                "micro",
                "v1",
                vocab_size,
                16,
                16,
                32,
                1,
                2,
                2,
                8,
                10000,
                1e-6,
                0,
                0,
                0,
                0.02,
                1,
                0,
                0,
                2,
                3,
                1,
                tokenizer_id,
                1000,
                1000000,
                "{}",
                "e" * 64,
                "validated",
                "test-admin",
            ),
        )
        config_id = connection.execute("SELECT id FROM core_model_configs").fetchone()[0]
        connection.execute(
            """INSERT INTO core_model_versions(public_id,core_model_family_id,version,
            lifecycle_status,config_id,tokenizer_version_id,architecture_name,
            estimated_parameter_count,actual_parameter_count,estimated_inference_memory_bytes,
            estimated_training_memory_bytes,initialization_seed,weights_checksum_sha256,
            config_checksum_sha256,architecture_summary_json,metrics_summary_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-000000009043",
                core_family_id,
                "v0.1",
                "architecture_verified",
                config_id,
                tokenizer_id,
                "brud_decoder_transformer",
                1000 + vocab_size,
                1000 + vocab_size,
                1000000,
                2000000,
                123,
                "f" * 64,
                "e" * 64,
                "{}",
                "{}",
            ),
        )
        connection.commit()
    return {
        "dataset": "00000000-0000-0000-0000-000000009021",
        "tokenizer": "00000000-0000-0000-0000-000000009032",
        "model": "00000000-0000-0000-0000-000000009043",
    }


def _payload(refs: dict[str, str]) -> dict:
    return {
        "name": "tiny phase 9",
        "dataset_version_public_id": refs["dataset"],
        "tokenizer_version_public_id": refs["tokenizer"],
        "core_model_version_public_id": refs["model"],
        "job_mode": "smoke_pretraining",
        "configuration": {
            "batch_size": 1,
            "gradient_accumulation_steps": 1,
            "sequence_length": 8,
            "total_steps": 2,
            "learning_rate": 0.01,
            "checkpoint_interval_steps": 1,
            "validation_interval_steps": 1,
            "metric_interval_steps": 1,
        },
    }


async def test_pretraining_api_worker_checkpoint_and_promotion(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        assert (await client.get("/api/admin/pretraining/capabilities")).status_code == 200
        assert (
            await client.post("/api/admin/pretraining/jobs", json=_payload(refs))
        ).status_code == 403
        created = await client.post(
            "/api/admin/pretraining/jobs",
            headers=headers,
            json=_payload(refs),
        )
        assert created.status_code == 200
        job_id = created.json()["public_id"]
        validate = await client.post(
            f"/api/admin/pretraining/jobs/{job_id}/validate",
            headers=headers,
        )
        assert validate.status_code == 200
        queue = await client.post(f"/api/admin/pretraining/jobs/{job_id}/queue", headers=headers)
        assert queue.status_code == 200
        result = PretrainingService(
            PretrainingRepository(api_app.state.settings.resolved_database_path),
            api_app.state.settings,
        ).run_one("test-worker")
        assert result["status"] == "completed"
        assert result["processed_tokens"] > 0
        job = (await client.get(f"/api/admin/pretraining/jobs/{job_id}")).json()
        assert job["status"] == "completed"
        assert job["latest_training_loss"] is not None
        metrics = (await client.get(f"/api/admin/pretraining/jobs/{job_id}/metrics")).json()
        assert len(metrics["items"]) == 2
        checkpoints = (
            await client.get(f"/api/admin/pretraining/jobs/{job_id}/checkpoints")
        ).json()["items"]
        assert checkpoints
        checkpoint_id = checkpoints[0]["public_id"]
        verified = await client.post(
            f"/api/admin/pretraining/checkpoints/{checkpoint_id}/verify",
            headers=headers,
        )
        assert verified.json()["verified"] is True
        evaluation = await client.post(
            f"/api/admin/pretraining/jobs/{job_id}/evaluate",
            headers=headers,
        )
        assert evaluation.status_code == 200
        quality = await client.post(
            f"/api/admin/pretraining/jobs/{job_id}/quality/assess",
            headers=headers,
        )
        assert quality.status_code == 200
        promoted = await client.post(
            f"/api/admin/pretraining/checkpoints/{checkpoint_id}/promote",
            headers=headers,
        )
        assert promoted.status_code == 200
        assert promoted.json()["not_chat_ready"] is True
        payload = json.dumps([job, metrics, checkpoints, promoted.json()])
        assert "/tmp/" not in payload
        assert "pretraining_job_id" not in payload
        assert "password" not in payload
    finally:
        await client.aclose()


async def test_pretraining_coverage_and_streams_cover_the_validation_split(
    api_app: FastAPI,
) -> None:
    """Regression test: coverage/stream verification must not silently treat
    the validation split as empty. ``dataset_version_items.split`` uses
    'train'/'validation'/'test', while coverage and stream manifests use the
    shorter 'train'/'valid' labels — the two must be mapped correctly."""
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        created = await client.post(
            "/api/admin/pretraining/jobs", headers=headers, json=_payload(refs)
        )
        job_id = created.json()["public_id"]
        await client.post(f"/api/admin/pretraining/jobs/{job_id}/validate", headers=headers)
        await client.post(f"/api/admin/pretraining/jobs/{job_id}/queue", headers=headers)
        result = PretrainingService(
            PretrainingRepository(api_app.state.settings.resolved_database_path),
            api_app.state.settings,
        ).run_one("test-worker")
        assert result["status"] == "completed"

        coverage = (
            await client.get(f"/api/admin/pretraining/jobs/{job_id}/coverage")
        ).json()["items"]
        splits = {item["split"]: item for item in coverage}
        assert splits.keys() == {"train", "valid"}
        assert splits["valid"]["total_records"] > 0
        assert splits["valid"]["encoded_records"] > 0
        assert splits["valid"]["usable_tokens"] > 0

        verify = await client.post(
            f"/api/admin/pretraining/jobs/{job_id}/streams/verify", headers=headers
        )
        assert verify.status_code == 200
        body = verify.json()
        assert body["verified"] is True
        assert body["splits"]["valid"]["matches"] is True
        assert body["splits"]["train"]["matches"] is True

        generated = await client.post(
            f"/api/admin/pretraining/jobs/{job_id}/coverage", headers=headers
        )
        assert generated.status_code == 200
        assert generated.json()["valid"]["total_records"] > 0
    finally:
        await client.aclose()


async def test_pretraining_rejects_draft_dataset_and_unsafe_config(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app, dataset_status="draft")
    client, headers = await authenticated_client(api_app)
    try:
        rejected = await client.post(
            "/api/admin/pretraining/preflight",
            headers=headers,
            json=_payload(refs),
        )
        assert rejected.status_code == 422
        refs["dataset"] = "missing"
        unsafe = _payload(refs)
        unsafe["configuration"]["sequence_length"] = 99999
        assert (
            await client.post(
                "/api/admin/pretraining/estimate",
                headers=headers,
                json=unsafe,
            )
        ).status_code == 422
    finally:
        await client.aclose()


async def test_pretraining_pause_resume_uses_registered_checkpoints(api_app: FastAPI) -> None:
    refs = _fixture_refs(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        payload = _payload(refs)
        payload["configuration"]["total_steps"] = 100
        payload["configuration"]["learning_rate"] = 0.005
        created = await client.post("/api/admin/pretraining/jobs", headers=headers, json=payload)
        job_id = created.json()["public_id"]
        queued = await client.post(f"/api/admin/pretraining/jobs/{job_id}/queue", headers=headers)
        assert queued.status_code == 200
        settings = api_app.state.settings

        def run_worker() -> None:
            PretrainingService(
                PretrainingRepository(settings.resolved_database_path),
                settings,
            ).run_one("pause-worker")

        thread = Thread(target=run_worker)
        thread.start()
        pause = None
        for _ in range(200):
            metrics = (await client.get(f"/api/admin/pretraining/jobs/{job_id}/metrics")).json()
            if metrics["items"]:
                pause = await client.post(
                    f"/api/admin/pretraining/jobs/{job_id}/pause",
                    headers=headers,
                )
                if pause.status_code == 200:
                    break
            time.sleep(0.05)
        assert pause is not None and pause.status_code == 200
        thread.join(timeout=20)
        paused = (await client.get(f"/api/admin/pretraining/jobs/{job_id}")).json()
        assert paused["status"] == "paused"
        assert paused["completed_steps"] > 0
        pause_checkpoints = (
            await client.get(f"/api/admin/pretraining/jobs/{job_id}/checkpoints")
        ).json()["items"]
        assert any(item["checkpoint_kind"] == "pause" for item in pause_checkpoints)
        resumed = await client.post(f"/api/admin/pretraining/jobs/{job_id}/resume", headers=headers)
        assert resumed.status_code == 200
        result = PretrainingService(
            PretrainingRepository(settings.resolved_database_path),
            settings,
        ).run_one("resume-worker")
        assert result["status"] == "completed"
        completed = (await client.get(f"/api/admin/pretraining/jobs/{job_id}")).json()
        assert completed["completed_steps"] == 100
        checkpoints = (
            await client.get(f"/api/admin/pretraining/jobs/{job_id}/checkpoints")
        ).json()["items"]
        assert {item["checkpoint_kind"] for item in checkpoints} >= {"pause", "final"}
    finally:
        await client.aclose()
