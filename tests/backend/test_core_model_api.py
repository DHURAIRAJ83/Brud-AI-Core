import json

import pytest
from fastapi import FastAPI

from backend.database.connection import database_connection
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio


def _registered_tokenizer(app: FastAPI) -> str:
    database = app.state.settings.resolved_database_path
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            ("00000000-0000-0000-0000-000000000801", "core-api", "v1", "ready", "d" * 64),
        )
        connection.execute(
            """INSERT INTO tokenizer_families(public_id,name,display_name,status)
            VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-000000000802", "test-tokenizer", "Test", "active"),
        )
        family_id = connection.execute(
            "SELECT id FROM tokenizer_families WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000802",),
        ).fetchone()[0]
        dataset_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000801",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
            lifecycle_status,algorithm,vocabulary_size,character_coverage,
            normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
            model_checksum_sha256,vocabulary_checksum_sha256,special_tokens_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-000000000803",
                family_id,
                "v1",
                "active",
                "bpe",
                128,
                0.9995,
                "nmt_nfkc",
                "sentencepiece",
                dataset_id,
                "a" * 64,
                "b" * 64,
                "c" * 64,
                "[]",
            ),
        )
        connection.commit()
    return "00000000-0000-0000-0000-000000000803"


async def test_core_model_api_pipeline(api_app: FastAPI) -> None:
    tokenizer_id = _registered_tokenizer(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        assert (await client.get("/api/admin/core-models/capabilities")).status_code == 200
        assert (
            await client.post(
                "/api/admin/core-models/families",
                json={"name": "blocked", "display_name": "Blocked"},
            )
        ).status_code == 403
        family = await client.post(
            "/api/admin/core-models/families",
            headers=headers,
            json={"name": "brud-core", "display_name": "Brud Core"},
        )
        assert family.status_code == 200
        family_id = family.json()["public_id"]
        config_payload = {
            "name": "micro",
            "config_version": "v1",
            "tokenizer_version_public_id": tokenizer_id,
            "preset": "micro",
            "context_length": 32,
            "hidden_size": 32,
            "intermediate_size": 64,
            "num_hidden_layers": 2,
            "num_attention_heads": 4,
            "num_key_value_heads": 4,
        }
        estimate = await client.post("/api/admin/core-models/configs/estimate", json=config_payload)
        assert estimate.status_code == 200
        assert estimate.json()["parameter_count_estimate"] > 0
        created = await client.post(
            "/api/admin/core-models/configs",
            headers=headers,
            json=config_payload,
        )
        assert created.status_code == 200
        config_id = created.json()["public_id"]
        validated = await client.post(
            f"/api/admin/core-models/configs/{config_id}/validate",
            headers=headers,
        )
        assert validated.status_code == 200
        assert validated.json()["status"] == "validated"
        version = await client.post(
            "/api/admin/core-models/versions",
            headers=headers,
            json={
                "family_public_id": family_id,
                "config_public_id": config_id,
                "version": "v0.1",
                "initialization_seed": 123,
            },
        )
        assert version.status_code == 200
        version_id = version.json()["public_id"]
        initialized = await client.post(
            f"/api/admin/core-models/versions/{version_id}/initialize",
            headers=headers,
        )
        assert initialized.status_code == 200
        assert initialized.json()["lifecycle_status"] == "initialized"
        verified = await client.post(
            f"/api/admin/core-models/versions/{version_id}/verify-architecture",
            headers=headers,
        )
        assert verified.status_code == 200
        assert verified.json()["status"] == "architecture_verified"
        forward = await client.post(
            f"/api/admin/core-models/versions/{version_id}/forward-test",
            headers=headers,
            json={"input_ids": [2, 5, 6, 3]},
        )
        assert forward.status_code == 200
        assert forward.json()["logits_shape"] == [1, 4, 128]
        assert forward.json()["random_untrained_model"] is True
        smoke = await client.post(
            f"/api/admin/core-models/versions/{version_id}/smoke-test",
            headers=headers,
        )
        assert smoke.status_code == 200
        assert smoke.json()["final_loss"] < smoke.json()["initial_loss"]
        staged = await client.post(
            f"/api/admin/core-models/versions/{version_id}/stage",
            headers=headers,
        )
        assert staged.status_code == 200 and staged.json()["lifecycle_status"] == "staging"
        activated = await client.post(
            f"/api/admin/core-models/versions/{version_id}/activate",
            headers=headers,
        )
        assert activated.status_code == 200 and activated.json()["lifecycle_status"] == "active"
        assignment = await client.patch(
            "/api/admin/core-models/assignments/future_pretraining_base",
            headers=headers,
            json={"core_model_version_public_id": version_id, "enabled": True},
        )
        assert assignment.status_code == 200
        checkpoints = (
            await client.get(f"/api/admin/core-models/versions/{version_id}/checkpoints")
        ).json()
        assert checkpoints["items"]
        checkpoint_id = checkpoints["items"][0]["public_id"]
        assert (
            await client.post(
                f"/api/admin/core-models/checkpoints/{checkpoint_id}/verify",
                headers=headers,
            )
        ).json()["verified"]
        checks = (await client.get(f"/api/admin/core-models/versions/{version_id}/checks")).json()
        assert {"causal_mask", "backward_pass", "tiny_overfit"} <= {
            item["check_name"] for item in checks["items"]
        }
        payload = json.dumps(
            [initialized.json(), forward.json(), checkpoints, checks],
            ensure_ascii=False,
        )
        assert "core_model_version_id" not in payload
        assert "/tmp/" not in payload
        assert "password" not in payload
    finally:
        await client.aclose()


async def test_unsafe_config_and_auth_csrf_rejection(api_app: FastAPI) -> None:
    tokenizer_id = _registered_tokenizer(api_app)
    client, headers = await authenticated_client(api_app)
    try:
        unsafe = await client.post(
            "/api/admin/core-models/configs/estimate",
            json={
                "name": "unsafe",
                "config_version": "v1",
                "tokenizer_version_public_id": tokenizer_id,
                "preset": "micro",
                "hidden_size": 4096,
            },
        )
        assert unsafe.status_code == 422
        no_csrf = await client.post(
            "/api/admin/core-models/configs",
            json={
                "name": "csrf",
                "config_version": "v1",
                "tokenizer_version_public_id": tokenizer_id,
            },
        )
        assert no_csrf.status_code == 403
    finally:
        await client.aclose()
