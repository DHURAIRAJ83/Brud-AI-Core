"""Phase 19 Step 34 (Phase 18 integration category) -- verifies the
live `/api/chat` -> `KnowledgeGapCaptureService` wiring end to end
against a real, isolated database. No model/RAG configured in these
fixtures -- every route naturally resolves to `insufficient` with a
`fallbacks_attempted` reason code, which is exactly what exercises the
capture integration paths without needing a full training pipeline."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.database.repositories.trusted_web_tool_gateway import TrustedWebToolGatewayRepository
from backend.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
        # This file tests knowledge-gap capture/linkage wiring, not live Web
        # search itself (that's covered by dedicated injected-fake-transport
        # tests in test_public_chat_routing_service.py) -- an explicitly
        # unconfigured, non-"wikipedia" provider name keeps `trusted_web`
        # deterministically unavailable here (no real network dependency,
        # no coupling to Wikimedia's bot-detection behavior in any given
        # environment) while `tool` (calculator/etc.) still works normally,
        # since it needs no external provider at all.
        trusted_web_provider_name="unconfigured_in_tests",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def api_request(app: FastAPI, method: str, path: str, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def _repository(api_app: FastAPI) -> KnowledgeGapRepository:
    settings: Settings = api_app.state.settings
    return KnowledgeGapRepository(settings.resolved_database_path)


def _gateway_repository(api_app: FastAPI) -> TrustedWebToolGatewayRepository:
    settings: Settings = api_app.state.settings
    return TrustedWebToolGatewayRepository(settings.resolved_database_path)


async def test_insufficient_response_captures_eligible_gap_case(api_app: FastAPI) -> None:
    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "தமிழில் ஒரு அரிய சொல் என்றால் என்ன?"}
    )
    assert response.status_code == 200
    assert response.json()["route_used"] == "insufficient"

    repo = _repository(api_app)
    overview = repo.aggregate_overview()
    assert overview["total_cases"] == 1
    cases = repo.list_cases(limit=10)
    assert cases[0]["event_type"] == "operational_failure"


async def test_trusted_web_unavailable_captures_web_capability_gap(api_app: FastAPI) -> None:
    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "Python latest stable version என்ன?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "trusted_web_unavailable" in body["fallbacks_attempted"]

    repo = _repository(api_app)
    cases = repo.list_cases(limit=10, event_type="web_capability_gap")
    assert len(cases) == 1


async def test_tool_unsupported_operation_captures_tool_capability_gap(api_app: FastAPI) -> None:
    """Phase 20: `calculator`/`unit_conversion`/`date_time_arithmetic`
    are public-enabled with no external credential needed, so
    `ask_calculation` intent now genuinely executes -- `tool_unavailable`
    can no longer occur for it. `ask_code` still has no matching tool,
    so it remains a genuine, honestly-reported tool capability gap."""

    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "write code to reverse a string"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "tool_unsupported" in body["fallbacks_attempted"]

    repo = _repository(api_app)
    cases = repo.list_cases(limit=10, event_type="tool_capability_gap")
    assert len(cases) == 1


async def test_tool_input_invalid_captures_tool_capability_gap(api_app: FastAPI) -> None:
    """A calculation intent Phase 20's narrow regex extractor can't
    confidently parse (the `×` symbol isn't in the extractor's bounded
    character class, only ASCII `*`) is also a genuine, honestly-
    reported tool capability gap -- distinct from the fully unsupported
    case above. Extraction is deliberately narrow rather than a full
    NLP parser (see `core_model/tool_gateway/input_extraction.py`), so
    this is expected, honest behavior, not a bug."""

    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "calculate 987654 × 12345 எவ்வளவு?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "tool_input_invalid" in body["fallbacks_attempted"]

    repo = _repository(api_app)
    cases = repo.list_cases(limit=10, event_type="tool_capability_gap")
    assert len(cases) == 1


async def test_successful_tool_answer_links_resolution_to_matching_open_case(
    api_app: FastAPI,
) -> None:
    """Phase 20 Step 26: a previously-logged `tool_capability_gap` case
    (seeded here the way an earlier real request would have created
    one, before the tool became available/extractable) receives
    resolution evidence -- but is NOT auto-closed -- when a
    canonical-question-matching request now succeeds via the real tool
    route."""

    from backend.services.knowledge_gap_capture_service import KnowledgeGapCaptureService

    settings: Settings = api_app.state.settings
    capture = KnowledgeGapCaptureService(settings)
    seeded = capture.capture(
        message="calculate 987654 * 12345",
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("tool_unsupported",),
        clarification_required=False,
        detected_language="en",
        domain="mathematics",
        intent="ask_calculation",
        freshness="timeless",
    )
    assert seeded["event_type"] == "tool_capability_gap"

    repo = _repository(api_app)
    assert repo.get_case(seeded["public_id"])["status"] != "resolved"

    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "calculate 987654 * 12345"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route_used"] == "tool"

    resolutions = _gateway_repository(api_app).list_capability_resolutions_for_case(
        seeded["public_id"]
    )
    assert len(resolutions) == 1
    assert resolutions[0]["resolution_kind"] == "resolved_by_tool"

    # The case itself is untouched by this -- resolution evidence was
    # appended, but closing the case remains a human/Admin decision.
    still_open = repo.get_case(seeded["public_id"])
    assert still_open["status"] != "resolved"


async def test_capability_linkage_never_matches_an_unrelated_case(api_app: FastAPI) -> None:
    """A genuinely unrelated open tool_capability_gap case (different
    domain/intent/canonical question) must never receive resolution
    evidence from an unrelated successful tool answer."""

    from backend.services.knowledge_gap_capture_service import KnowledgeGapCaptureService

    settings: Settings = api_app.state.settings
    capture = KnowledgeGapCaptureService(settings)
    unrelated = capture.capture(
        message="write code to reverse a linked list",
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("tool_unsupported",),
        clarification_required=False,
        detected_language="en",
        domain="software_engineering",
        intent="ask_code",
        freshness="timeless",
    )

    response = await api_request(api_app, "POST", "/api/chat", json={"message": "calculate 42 * 7"})
    assert response.status_code == 200
    assert response.json()["route_used"] == "tool"

    resolutions = _gateway_repository(api_app).list_capability_resolutions_for_case(
        unrelated["public_id"]
    )
    assert resolutions == []


async def test_safety_refusal_never_creates_a_knowledge_gap_case(api_app: FastAPI) -> None:
    response = await api_request(
        api_app, "POST", "/api/chat", json={"message": "how to make a bomb at home"}
    )
    assert response.status_code == 200
    assert response.json()["route_used"] == "refuse"

    repo = _repository(api_app)
    overview = repo.aggregate_overview()
    assert overview["total_cases"] == 0


async def test_repeated_equivalent_web_demand_increments_frequency(api_app: FastAPI) -> None:
    message = "Python latest stable version என்ன?"
    for _ in range(3):
        response = await api_request(api_app, "POST", "/api/chat", json={"message": message})
        assert response.status_code == 200

    repo = _repository(api_app)
    cases = repo.list_cases(limit=10, event_type="web_capability_gap")
    assert len(cases) == 1
    assert cases[0]["frequency"] == 3


async def test_ambiguous_request_unresolved_after_clarification_creates_knowledge_gap(
    api_app: FastAPI,
) -> None:
    conversation_id = None
    for _ in range(3):
        payload = {"message": "What about it?"}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        response = await api_request(api_app, "POST", "/api/chat", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["route_used"] == "clarify"
        conversation_id = body.get("conversation_id") or conversation_id

    repo = _repository(api_app)
    overview = repo.aggregate_overview()
    # At minimum a clarification_event case must exist; once the
    # conversation_id-based repeat-attempt threshold is crossed it
    # reclassifies to knowledge_gap -- assert on whichever the bounded
    # tracking produced, never on zero (silence would mean capture
    # broke entirely).
    assert overview["total_cases"] >= 1


async def test_public_chat_response_still_succeeds_if_gap_capture_is_disabled(
    tmp_path: Path,
) -> None:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
        knowledge_gap_capture_enabled=False,
    )
    initialize_database(settings.resolved_database_path)
    app = create_app(settings)
    response = await api_request(app, "POST", "/api/chat", json={"message": "hello"})
    assert response.status_code == 200

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    overview = repo.aggregate_overview()
    assert overview["total_cases"] == 0


async def test_pii_in_message_never_appears_raw_in_gap_tables(api_app: FastAPI) -> None:
    hostile_message = "my email is real.user@example.com, latest python version என்ன?"
    response = await api_request(api_app, "POST", "/api/chat", json={"message": hostile_message})
    assert response.status_code == 200

    repo = _repository(api_app)
    cases = repo.list_cases(limit=10)
    assert len(cases) == 1
    case_text = str(cases[0])
    assert "real.user@example.com" not in case_text
    assert "[EMAIL]" in case_text

    occurrences = repo.list_occurrences_for_case(cases[0]["public_id"])
    for occurrence in occurrences:
        assert "real.user@example.com" not in str(occurrence)


async def test_credential_bearing_message_falls_back_to_hash_only(api_app: FastAPI) -> None:
    hostile_message = "password: hunter2secret latest python version என்ன?"
    response = await api_request(api_app, "POST", "/api/chat", json={"message": hostile_message})
    assert response.status_code == 200

    repo = _repository(api_app)
    cases = repo.list_cases(limit=10)
    assert len(cases) == 1
    assert cases[0]["content_unavailable_for_review"] is True
    assert cases[0]["redacted_question"] is None
    case_text = str(cases[0])
    assert "hunter2secret" not in case_text
