"""MB-06: API tests for /admin/mini-brain/learning-supervisor.

Auth/CSRF requirements, the full session-creation-through-decision-gate
path over real HTTP, and the same "wrong stage is rejected" proof
already covered at the service layer, repeated here to confirm the
routes wire request models -> service correctly.
"""

import pytest
from fastapi import FastAPI

from tests.backend.test_dataset_api import authenticated_client, create_source, instruction

pytestmark = pytest.mark.anyio

MBLS = "/api/admin/mini-brain/learning-supervisor"


async def _seeded_source(client, headers, count: int = 20) -> str:
    source = await create_source(client, headers)
    for i in range(count):
        response = await client.post(
            "/api/admin/datasets/records", headers=headers,
            json=instruction(source["public_id"], output=f"Answer {i}"),
        )
        assert response.status_code == 200
    return source["public_id"]


async def test_routes_require_admin_auth(api_app: FastAPI) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        assert (await client.get(f"{MBLS}/sessions")).status_code == 401
        assert (await client.get(f"{MBLS}/hyperparameter-profiles")).status_code == 401
    finally:
        await client.aclose()


async def test_create_session_requires_csrf_header(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBLS}/sessions", json={"dataset_source_public_id": "x"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_hyperparameter_profiles_lists_known_profiles(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLS}/hyperparameter-profiles", headers=headers)
        assert response.status_code == 200
        items = response.json()["items"]
        assert "default" in items
        assert "conservative" in items
        assert "aggressive" in items
    finally:
        await client.aclose()


async def test_full_session_lifecycle_through_dataset_decision_over_http(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source_id = await _seeded_source(client, headers, count=60)

        create_response = await client.post(
            f"{MBLS}/sessions", headers=headers,
            json={"dataset_source_public_id": source_id, "hyperparameter_profile": "default"},
        )
        assert create_response.status_code == 200
        session = create_response.json()
        assert session["stage"] == "dataset_validation"
        session_id = session["public_id"]

        get_response = await client.get(f"{MBLS}/sessions/{session_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["public_id"] == session_id

        list_response = await client.get(f"{MBLS}/sessions", headers=headers)
        assert list_response.status_code == 200
        assert any(s["public_id"] == session_id for s in list_response.json()["items"])

        validate_response = await client.post(
            f"{MBLS}/sessions/{session_id}/validate-dataset", headers=headers
        )
        assert validate_response.status_code == 200
        assert validate_response.json()["stage"] == "awaiting_dataset_decision"

        decide_response = await client.post(
            f"{MBLS}/sessions/{session_id}/decide-dataset", headers=headers,
            json={"decision": "approve"},
        )
        assert decide_response.status_code == 200
        assert decide_response.json()["stage"] == "rag_evaluation"
        assert decide_response.json()["dataset_decision"] == "approve"

        events_response = await client.get(f"{MBLS}/sessions/{session_id}/events", headers=headers)
        assert events_response.status_code == 200
        event_types = [e["event_type"] for e in events_response.json()["items"]]
        assert "dataset_approved" in event_types
    finally:
        await client.aclose()


async def test_decide_dataset_before_validation_returns_422(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        source_id = await _seeded_source(client, headers, count=5)
        create_response = await client.post(
            f"{MBLS}/sessions", headers=headers, json={"dataset_source_public_id": source_id},
        )
        session_id = create_response.json()["public_id"]

        response = await client.post(
            f"{MBLS}/sessions/{session_id}/decide-dataset", headers=headers,
            json={"decision": "approve"},
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_get_unknown_session_returns_404(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(f"{MBLS}/sessions/does-not-exist", headers=headers)
        assert response.status_code == 404
    finally:
        await client.aclose()
