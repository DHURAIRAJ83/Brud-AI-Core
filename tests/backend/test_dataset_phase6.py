import json

import pytest
from fastapi import FastAPI

from tests.backend.test_dataset_api import authenticated_client, create_source, instruction

pytestmark = pytest.mark.anyio


async def _approved_instruction(client, headers, source_id: str, text: str):
    created = (
        await client.post(
            "/api/admin/datasets/records",
            headers=headers,
            json=instruction(source_id, text),
        )
    ).json()
    await client.post(f"/api/admin/datasets/records/{created['public_id']}/submit", headers=headers)
    approved = await client.post(
        f"/api/admin/datasets/records/{created['public_id']}/review",
        headers=headers,
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    return approved.json()


async def test_quality_assessment_summary_and_blocked_approval(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers)
        bad = (
            await client.post(
                "/api/admin/datasets/records",
                headers=headers,
                json={
                    "source_public_id": source["public_id"],
                    "record_type": "instruction",
                    "language": "ta",
                    "instruction": "Say hello",
                    "output_text": "!!!!!!",
                    "metadata": {"api_key": "not-a-real-secret"},
                },
            )
        ).json()
        assessed = await client.post(
            f"/api/admin/datasets/records/{bad['public_id']}/quality/assess",
            headers=headers,
            json={},
        )
        assert assessed.status_code == 200
        payload = assessed.json()
        assert 0 <= payload["overall_score"] <= 1
        assert payload["issues"]
        assert "id" not in payload and "dataset_record_id" not in payload
        await client.post(f"/api/admin/datasets/records/{bad['public_id']}/submit", headers=headers)
        blocked = await client.post(
            f"/api/admin/datasets/records/{bad['public_id']}/review",
            headers=headers,
            json={"decision": "approve"},
        )
        assert blocked.status_code == 422
        summary = (await client.get("/api/admin/datasets/quality/summary")).json()
        assert summary["total_assessed"] == 1
        issues = (await client.get("/api/admin/datasets/quality/issues")).json()
        assert issues["items"]
    finally:
        await client.aclose()


async def test_dataset_build_manifest_verify_and_export(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers)
        records = [
            await _approved_instruction(client, headers, source["public_id"], f"தமிழ் பதில் {index}")
            for index in range(3)
        ]
        for record in records:
            await client.post(
                f"/api/admin/datasets/records/{record['public_id']}/quality/assess",
                headers=headers,
                json={},
            )
        build = await client.post(
            "/api/admin/datasets/builds",
            headers=headers,
            json={
                "dataset_name": "phase6_test",
                "dataset_version": "v1",
                "minimum_quality_score": 0,
                "selection_filters": {"language": "ta"},
                "split_configuration": {
                    "train_percent": 90,
                    "validation_percent": 5,
                    "test_percent": 5,
                    "seed": 42,
                },
            },
        )
        assert build.status_code == 200
        build_id = build.json()["public_id"]
        preview = await client.post(
            f"/api/admin/datasets/builds/{build_id}/validate", headers=headers
        )
        assert preview.status_code == 200
        assert preview.json()["selected_records"] == 3
        run = await client.post(
            f"/api/admin/datasets/builds/{build_id}/run",
            headers=headers,
            json={"confirm": True, "allow_warnings": True},
        )
        assert run.status_code == 200
        version_id = run.json()["dataset_version_public_id"]
        version = (await client.get(f"/api/admin/datasets/versions/{version_id}")).json()
        assert version["status"] == "ready"
        edit_ready = await client.patch(
            f"/api/admin/datasets/versions/{version_id}",
            headers=headers,
            json={"description": "cannot edit ready"},
        )
        assert edit_ready.status_code == 422
        manifest = (await client.get(f"/api/admin/datasets/versions/{version_id}/manifest")).json()
        assert manifest["record_count"] == 3
        assert "/tmp/" not in json.dumps(manifest)
        verified = await client.post(
            f"/api/admin/datasets/versions/{version_id}/verify", headers=headers
        )
        assert verified.json()["verified"] is True
        exported = await client.post(
            f"/api/admin/datasets/versions/{version_id}/exports",
            headers=headers,
            json={"export_format": "jsonl"},
        )
        assert exported.status_code == 200
        export_payload = exported.json()
        assert export_payload["status"] == "completed"
        export_verified = await client.post(
            f"/api/admin/datasets/exports/{export_payload['public_id']}/verify",
            headers=headers,
        )
        assert export_verified.json()["verified"] is True
        assert (
            await client.get(f"/api/admin/datasets/exports/{export_payload['public_id']}/download")
        ).status_code == 200
    finally:
        await client.aclose()
