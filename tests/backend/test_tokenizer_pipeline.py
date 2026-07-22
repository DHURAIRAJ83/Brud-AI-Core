import json

import pytest
from fastapi import FastAPI

from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio


async def _create_ready_dataset_version(client, headers) -> str:
    source = (
        await client.post(
            "/api/admin/datasets/sources",
            headers=headers,
            json={"name": "Tokenizer Source", "language": "mixed", "source_type": "manual"},
        )
    ).json()
    records = [
        {
            "record_type": "instruction",
            "language": "ta",
            "instruction": "தமிழில் வாழ்த்து சொல்லு",
            "output_text": f"வணக்கம் நண்பா {index}",
        }
        for index in range(6)
    ]
    records += [
        {
            "record_type": "instruction",
            "language": "en",
            "instruction": "Say hello in English",
            "output_text": f"Hello friend {index}",
        }
        for index in range(4)
    ]
    records += [
        {
            "record_type": "tanglish_pair",
            "language": "tgl",
            "input_text": f"vanakkam nanba {index}",
            "normalized_input": f"வணக்கம் நண்பா {index}",
            "output_text": f"seri nanba {index}",
        }
        for index in range(4)
    ]
    records += [
        {
            "record_type": "chat",
            "language": "mixed",
            "input_text": f"நாளைக்கு plan என்ன {index}?",
            "output_text": f"Tomorrow plan ready {index}.",
        }
        for index in range(4)
    ]

    for payload in records:
        created = (
            await client.post(
                "/api/admin/datasets/records",
                headers=headers,
                json={"source_public_id": source["public_id"], "metadata": {}, **payload},
            )
        ).json()
        await client.post(
            f"/api/admin/datasets/records/{created['public_id']}/submit",
            headers=headers,
        )
        approved = await client.post(
            f"/api/admin/datasets/records/{created['public_id']}/review",
            headers=headers,
            json={"decision": "approve"},
        )
        assert approved.status_code == 200

    build = await client.post(
        "/api/admin/datasets/builds",
        headers=headers,
        json={
            "dataset_name": "tokenizer_test_dataset",
            "dataset_version": "v1",
            "minimum_quality_score": 0,
            "split_configuration": {
                "train_percent": 90,
                "validation_percent": 5,
                "test_percent": 5,
                "seed": 7,
            },
        },
    )
    assert build.status_code == 200
    build_id = build.json()["public_id"]
    run = await client.post(
        f"/api/admin/datasets/builds/{build_id}/run",
        headers=headers,
        json={"confirm": True, "allow_warnings": True},
    )
    assert run.status_code == 200
    return run.json()["dataset_version_public_id"]


async def test_tokenizer_pipeline_api_and_artifacts(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        assert (await client.get("/api/admin/tokenizers/capabilities")).status_code == 200
        unauthenticated = await client.post(
            "/api/admin/tokenizers/families",
            json={"name": "blocked", "display_name": "Blocked"},
        )
        assert unauthenticated.status_code == 403

        dataset_version_id = await _create_ready_dataset_version(client, headers)
        family = await client.post(
            "/api/admin/tokenizers/families",
            headers=headers,
            json={
                "name": "brud-multilingual-tokenizer",
                "display_name": "Brud Multilingual Tokenizer",
            },
        )
        assert family.status_code == 200
        family_id = family.json()["public_id"]

        version = await client.post(
            "/api/admin/tokenizers/versions",
            headers=headers,
            json={
                "family_public_id": family_id,
                "version": "v0.1",
                "dataset_version_public_id": dataset_version_id,
                "algorithm": "bpe",
                "vocabulary_size": 1000,
            },
        )
        assert version.status_code == 200
        version_id = version.json()["public_id"]

        job = await client.post(
            "/api/admin/tokenizers/jobs",
            headers=headers,
            json={"tokenizer_version_public_id": version_id, "job_type": "full_pipeline"},
        )
        assert job.status_code == 200
        job_id = job.json()["public_id"]

        corpus = await client.post(
            f"/api/admin/tokenizers/jobs/{job_id}/build-corpus",
            headers=headers,
        )
        assert corpus.status_code == 200
        first_checksum = corpus.json()["corpus_checksum_sha256"]
        second_checksum = (
            await client.post(f"/api/admin/tokenizers/jobs/{job_id}/build-corpus", headers=headers)
        ).json()["corpus_checksum_sha256"]
        assert first_checksum == second_checksum

        dry_run = await client.post(f"/api/admin/tokenizers/jobs/{job_id}/dry-run", headers=headers)
        assert dry_run.status_code == 200
        assert dry_run.json()["status"] in {"pass", "pass_with_warnings"}

        train = await client.post(f"/api/admin/tokenizers/jobs/{job_id}/train", headers=headers)
        assert train.status_code == 200
        trained = train.json()
        assert trained["lifecycle_status"] == "staging"
        assert trained["model_checksum_sha256"]
        assert trained["vocabulary_checksum_sha256"]

        evaluation = await client.post(
            f"/api/admin/tokenizers/jobs/{job_id}/evaluate",
            headers=headers,
        )
        assert evaluation.status_code == 200
        assert evaluation.json()["status"] in {"completed", "completed_with_warnings"}
        results = await client.get(
            f"/api/admin/tokenizers/evaluations/{evaluation.json()['public_id']}/results"
        )
        assert results.status_code == 200
        assert {"ta", "en", "tgl", "mixed", "overall"} <= {
            item["language"] for item in results.json()["items"]
        }

        encoded = await client.post(
            f"/api/admin/tokenizers/versions/{version_id}/encode",
            json={"text": "வணக்கம் friend"},
        )
        assert encoded.status_code == 200
        assert encoded.json()["token_count"] > 0
        decoded = await client.post(
            f"/api/admin/tokenizers/versions/{version_id}/decode",
            json={"ids": encoded.json()["ids"]},
        )
        assert decoded.status_code == 200
        assert "வணக்கம்" in decoded.json()["decoded_text"]

        verified = await client.post(
            f"/api/admin/tokenizers/versions/{version_id}/verify",
            headers=headers,
        )
        assert verified.status_code == 200 and verified.json()["verified"] is True

        activated = await client.post(
            f"/api/admin/tokenizers/versions/{version_id}/activate",
            headers=headers,
        )
        assert activated.status_code == 200
        assert activated.json()["lifecycle_status"] == "active"

        assignments = (await client.get("/api/admin/tokenizers/assignments")).json()
        assert assignments["items"]

        export = await client.post(
            f"/api/admin/tokenizers/versions/{version_id}/exports",
            headers=headers,
            json={"export_format": "sentencepiece_bundle"},
        )
        assert export.status_code == 200
        export_id = export.json()["public_id"]
        assert (await client.get(f"/api/admin/tokenizers/exports/{export_id}/download")).status_code
        assert (
            await client.post(
                f"/api/admin/tokenizers/exports/{export_id}/verify",
                headers=headers,
            )
        ).json()["verified"]

        payload_dump = json.dumps(
            [trained, evaluation.json(), encoded.json(), assignments, export.json()],
            ensure_ascii=False,
        )
        assert "tokenizer_family_id" not in payload_dump
        assert "token_hash" not in payload_dump
        assert "/tmp/" not in payload_dump
    finally:
        await client.aclose()


async def test_tokenizer_rejects_draft_dataset_and_missing_csrf(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        family_id = (
            await client.post(
                "/api/admin/tokenizers/families",
                headers=headers,
                json={"name": "draft-check", "display_name": "Draft Check"},
            )
        ).json()["public_id"]
        draft = (
            await client.post(
                "/api/admin/datasets/versions",
                headers=headers,
                json={"name": "draft_dataset", "version": "v0"},
            )
        ).json()
        missing_csrf = await client.post(
            "/api/admin/tokenizers/versions",
            json={
                "family_public_id": family_id,
                "version": "v0",
                "dataset_version_public_id": draft["public_id"],
            },
        )
        assert missing_csrf.status_code == 403
        rejected = await client.post(
            "/api/admin/tokenizers/versions",
            headers=headers,
            json={
                "family_public_id": family_id,
                "version": "v0",
                "dataset_version_public_id": draft["public_id"],
            },
        )
        assert rejected.status_code == 422
    finally:
        await client.aclose()
