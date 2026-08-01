"""Integration tests: the Phase 2 Source, Rights & Usage Registry's
preflight checks against existing dataset-build and RAG-ingestion
workflows, without changing those workflows' own contracts."""

import pytest
from fastapi import FastAPI

from tests.backend.test_dataset_api import authenticated_client, create_source, instruction

pytestmark = pytest.mark.anyio


async def _approved_instruction(client, headers, source_id: str, text: str):
    created = (
        await client.post(
            "/api/admin/datasets/records", headers=headers, json=instruction(source_id, text)
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


async def _build_version(client, headers, source_id: str, count: int = 3) -> str:
    records = [
        await _approved_instruction(client, headers, source_id, f"தமிழ் பதில் {index}")
        for index in range(count)
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
            "dataset_name": "phase2_integration_test",
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
    run = await client.post(
        f"/api/admin/datasets/builds/{build.json()['public_id']}/run",
        headers=headers,
        json={"confirm": True, "allow_warnings": True},
    )
    assert run.status_code == 200
    return run.json()["dataset_version_public_id"], [record["public_id"] for record in records]


async def test_dataset_version_rights_summary_reports_unlinked_records_by_default(
    api_app: FastAPI,
) -> None:
    """Existing records that predate the registry (and every record does,
    since nothing links to it unless an admin explicitly does so) must be
    reported as unlinked -- never silently treated as blocked or allowed,
    and the existing build/export flow itself is untouched by this check."""

    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers)
        version_id, _record_ids = await _build_version(client, headers, source["public_id"])

        summary = await client.get(
            f"/api/admin/datasets/versions/{version_id}/rights-summary",
            params={"target_use": "training"},
        )
        assert summary.status_code == 200
        body = summary.json()
        assert body["total"] == 3
        assert body["unlinked_count"] == 3
        assert body["allowed_count"] == 0
        assert body["blocked_count"] == 0

        # The existing build/version/export endpoints are completely
        # unaffected -- the version is still "ready", still exportable.
        version = await client.get(f"/api/admin/datasets/versions/{version_id}")
        assert version.json()["status"] == "ready"
    finally:
        await client.aclose()


async def test_dataset_version_rights_summary_reflects_linked_and_verified_records(
    api_app: FastAPI,
) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source = await create_source(client, headers)
        version_id, record_ids = await _build_version(client, headers, source["public_id"], count=2)

        data_source = (
            await client.post(
                "/api/admin/data-sources",
                headers=headers,
                json={
                    "source_code": "SRC-INTEGRATION-0001",
                    "title": "Admin-authored Tamil replies",
                    "source_type": "human_created",
                },
            )
        ).json()
        await client.put(
            f"/api/admin/data-sources/{data_source['public_id']}/rights",
            headers=headers,
            json={"rights_status": "licensed", "training_use_allowed": True},
        )
        await client.post(
            f"/api/admin/data-sources/{data_source['public_id']}/links",
            headers=headers,
            json={"entity_type": "dataset_record", "entity_public_id": record_ids[0]},
        )

        summary = await client.get(
            f"/api/admin/datasets/versions/{version_id}/rights-summary",
            params={"target_use": "training"},
        )
        body = summary.json()
        assert body["total"] == 2
        assert body["allowed"] == [record_ids[0]]
        assert body["unlinked"] == [record_ids[1]]

        # Public export uses the same generic parameterized endpoint.
        export_summary = await client.get(
            f"/api/admin/datasets/versions/{version_id}/rights-summary",
            params={"target_use": "public_export"},
        )
        assert export_summary.status_code == 200
        assert export_summary.json()["allowed_count"] == 0  # training-only rights declared
    finally:
        await client.aclose()


async def test_rag_source_rights_check_reports_unlinked_then_allowed(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        space = (
            await client.post(
                "/api/admin/rag/spaces",
                headers=headers,
                json={"name": "Test space", "slug": "test-space", "description": ""},
            )
        ).json()
        source = (
            await client.post(
                f"/api/admin/rag/spaces/{space['public_id']}/sources",
                headers=headers,
                json={
                    "source_type": "manual_admin_content",
                    "title": "Admin FAQ",
                    "language": "ta",
                    "content": "வணக்கம்! இது ஒரு admin FAQ உள்ளடக்கம்.",
                },
            )
        ).json()

        unlinked = await client.get(f"/api/admin/rag/sources/{source['public_id']}/rights-check")
        assert unlinked.status_code == 200
        assert unlinked.json()["status"] == "unlinked"

        data_source = (
            await client.post(
                "/api/admin/data-sources",
                headers=headers,
                json={
                    "source_code": "SRC-RAG-INTEGRATION-0001",
                    "title": "Admin FAQ source",
                    "source_type": "admin_created",
                },
            )
        ).json()
        await client.put(
            f"/api/admin/data-sources/{data_source['public_id']}/rights",
            headers=headers,
            json={"rights_status": "internal_only", "rag_use_allowed": True, "internal_only": True},
        )
        await client.post(
            f"/api/admin/data-sources/{data_source['public_id']}/links",
            headers=headers,
            json={"entity_type": "rag_knowledge_source", "entity_public_id": source["public_id"]},
        )

        allowed = await client.get(f"/api/admin/rag/sources/{source['public_id']}/rights-check")
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "allowed"

        # The existing RAG source endpoint itself is untouched.
        fetched = await client.get(f"/api/admin/rag/sources/{source['public_id']}")
        assert fetched.status_code == 200
    finally:
        await client.aclose()
