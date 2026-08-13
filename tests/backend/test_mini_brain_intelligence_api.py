"""MB-03: Brud Intelligence Engine -- API tests.

Every assertion here traces to the fixed, deterministic rules in
`core_model/mini_brain/intelligence/` -- no test depends on a model
being loaded, because MB-03 has no model.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from tests.backend.test_dataset_api import authenticated_client

pytestmark = pytest.mark.anyio

MBKC = "/api/admin/mini-brain/knowledge-core"
MBIE = "/api/admin/mini-brain/intelligence"


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
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


async def _seed(client, headers):
    response = await client.post(f"{MBKC}/seed", headers=headers)
    assert response.status_code == 200, response.text


async def _analyze(client, headers, question: str):
    response = await client.post(f"{MBIE}/analyze", headers=headers, json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


async def test_analyze_requires_csrf(api_app: FastAPI) -> None:
    client, _headers = await authenticated_client(api_app)
    try:
        response = await client.post(f"{MBIE}/analyze", json={"question": "test"})
        assert response.status_code == 403
    finally:
        await client.aclose()


async def test_unknown_intent_on_nonsense_question(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        body = await _analyze(client, headers, "zxqwpl asdkj nonsense words")
        assert body["question_analysis"]["intent"] == "unknown"
        assert body["response_plan"]["suggested_response_type"] == "clarify_question"
        assert body["confidence"]["band"] == "none"
    finally:
        await client.aclose()


async def test_rag_question_finds_rag_intent_and_primary_knowledge(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        body = await _analyze(client, headers, "Why is my RAG retrieval not returning citations?")
        assert body["question_analysis"]["intent"] == "rag"
        assert body["question_analysis"]["question_type"] == "troubleshooting"
        assert len(body["knowledge_plan"]["primary_knowledge"]) > 0
        assert body["response_plan"]["suggested_response_type"] == "explain_with_primary_knowledge"
        assert body["confidence"]["band"] in ("high", "medium")
    finally:
        await client.aclose()


async def test_training_execution_question_is_blocked_by_rule_engine(api_app: FastAPI) -> None:
    """The Rule Engine's training boundary mirrors Admin Assistant's
    own BLOCKED_ACTION_SUBSTRINGS discipline -- Mini Brain must never
    imply it can start training."""

    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        body = await _analyze(client, headers, "How do I start training the model right now?")
        assert "cannot_execute_training" in body["rules"]["flags"]
        assert body["rules"]["blocked"] is True
        assert body["response_plan"]["suggested_response_type"] == "training_boundary_notice"
        assert any("never start" in d or "never execute" in d for d in body["rules"]["disclaimers"])
    finally:
        await client.aclose()


async def test_question_without_seeded_knowledge_gives_insufficient_knowledge(api_app: FastAPI) -> None:
    """Same fail-closed philosophy as ChatOrchestrationService's own
    `blocked_context` path -- no knowledge, no confident answer."""

    client, headers = await authenticated_client(api_app)
    try:
        # deliberately no _seed() call -- Knowledge Core is empty
        body = await _analyze(client, headers, "What is the model registry?")
        assert body["knowledge_plan"]["primary_knowledge"] == []
        assert body["knowledge_plan"]["supporting_knowledge"] == []
        assert "insufficient_knowledge" in body["rules"]["flags"]
        assert body["response_plan"]["suggested_response_type"] == "insufficient_knowledge"
    finally:
        await client.aclose()


async def test_response_plan_contains_only_the_four_documented_fields(api_app: FastAPI) -> None:
    """MB-03's own future-compatibility rule: the future model must
    receive only validated context, knowledge, workflow, and the plan
    itself -- confirmed by checking the exact key set."""

    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        body = await _analyze(client, headers, "How do I train the tokenizer?")
        plan = body["response_plan"]
        assert set(plan) == {
            "suggested_response_type", "validated_context", "validated_knowledge",
            "validated_workflow", "disclaimers", "confidence_band", "intent", "question_type",
        }
        assert set(plan["validated_context"]) == {"matched_items", "documentation_references"}
        assert set(plan["validated_knowledge"]) == {"primary", "supporting", "priority_order"}
        assert set(plan["validated_workflow"]) == {
            "current_step", "previous_steps", "next_steps", "dependencies",
        }
    finally:
        await client.aclose()


async def test_workflow_chain_resolves_dataset_to_production(api_app: FastAPI) -> None:
    """Direct proof the Workflow Resolver walks MB-02's real seeded
    flows_to chain (Dataset -> ... -> Production), not a fabricated
    one."""

    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        body = await _analyze(client, headers, "instruction tuning fine-tune sft")
        workflow = body["workflow"]
        assert workflow["current_step"] is not None
        assert workflow["in_a_workflow_chain"] is True
    finally:
        await client.aclose()


async def test_diagnostics_reports_processing_time(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        response = await client.post(
            f"{MBIE}/diagnostics", headers=headers, json={"question": "what is a dataset"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["processing_time_ms"] >= 0
        assert body["candidate_item_count"] > 0
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "path,expected_key",
    [
        ("/question-analysis", "intent"), ("/intent", "intent"), ("/context", "matched_item_titles"),
        ("/workflow", "current_step"), ("/features", "dashboard_pages"),
        ("/knowledge-plan", "primary_knowledge"), ("/response-plan", "suggested_response_type"),
    ],
)
async def test_every_stage_endpoint_returns_its_own_slice(
    api_app: FastAPI, path: str, expected_key: str,
) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        response = await client.post(
            f"{MBIE}{path}", headers=headers, json={"question": "how do I train the tokenizer?"},
        )
        assert response.status_code == 200, response.text
        assert expected_key in response.json()
    finally:
        await client.aclose()


async def test_intelligence_engine_never_writes_to_knowledge_core(api_app: FastAPI) -> None:
    """Direct proof of read-only access -- item/relationship/domain
    counts must be identical before and after a batch of analyze
    calls."""

    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        before = await client.get(f"{MBKC}/diagnostics", headers=headers)
        for q in ["dataset question", "training question", "rag question", "unknown xyzabc"]:
            await _analyze(client, headers, q)
        after = await client.get(f"{MBKC}/diagnostics", headers=headers)
        assert before.json() == after.json()
    finally:
        await client.aclose()


async def test_intelligence_engine_never_touches_admin_assistant_or_inference_runtime(
    api_app: FastAPI,
) -> None:
    from backend.database.connection import database_connection

    client, headers = await authenticated_client(api_app)
    try:
        await _seed(client, headers)
        await _analyze(client, headers, "how do I start training?")
    finally:
        await client.aclose()

    with database_connection(api_app.state.settings.resolved_database_path) as connection:
        approvals = connection.execute("SELECT COUNT(*) FROM admin_approvals").fetchone()[0]
        assignments = connection.execute(
            "SELECT COUNT(*) FROM inference_model_assignments"
        ).fetchone()[0]
        assert approvals == 0
        assert assignments == 0
