"""MB-10: structural safety proofs for MiniBrainResearchCenterService.

Static-analysis checks on the service source itself -- they prove the
"never starts training, deploys a model, activates a runtime, writes
or approves a dataset, or calls an external AI provider automatically"
boundary is enforced by what code exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_research_center_service.py"
)


def _module_ast() -> ast.Module:
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))


def _method_source(name: str) -> str:
    tree = _module_ast()
    lines = SERVICE_PATH.read_text(encoding="utf-8").splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"method not found: {name}")


def _attribute_calls(tree: ast.Module) -> list[tuple[str, str]]:
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name):
                receiver_name = f"{receiver.value.id}.{receiver.attr}"
            elif isinstance(receiver, ast.Name):
                receiver_name = receiver.id
            else:
                continue
            calls.append((receiver_name, node.func.attr))
    return calls


def test_only_calls_read_only_mb09_planning_center_method() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.planning_center"}
    assert used == {"session"}, f"unexpected MB-09 method(s) called: {used}"


def test_only_calls_read_only_mb06_learning_supervisor_method() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.learning_supervisor"}
    assert used == {"session"}, f"unexpected MB-06 method(s) called: {used}"


def test_only_calls_read_only_dataset_intelligence_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.dataset_intelligence"}
    assert used <= {"training", "analyze"}, f"unexpected MiniBrainDatasetIntelligenceService method(s) called: {used}"


def test_only_calls_expected_duplicate_service_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.duplicate_service"}
    assert used <= {"group_normalized_duplicates", "find_conflicts"}, (
        f"unexpected ExternalDatasetDuplicateService method(s) called: {used}"
    )


def test_rag_sandbox_chain_only_calls_generation_evaluation_and_finalize() -> None:
    """Matches MB-06's exact, already-established boundary: corpus,
    index, query set, and retrieval stay admin-driven through RAG
    Sandbox's own UI -- this service only runs generation, evaluation,
    and report finalization on top of an already-built retrieval run."""
    tree = _module_ast()
    calls = _attribute_calls(tree)
    assert {m for r, m in calls if r == "self.rag_answer"} == {"run_generation"}
    assert {m for r, m in calls if r == "self.rag_evaluation"} == {"run_evaluation"}
    assert {m for r, m in calls if r == "self.rag_report"} == {"finalize"}


def test_never_imports_dataset_service_write_class_beyond_construction() -> None:
    """DatasetService is only ever constructed to hand to
    MiniBrainDatasetIntelligenceService (read-only) -- MB-10 must never
    call .create_source()/.create_record()/.update_source() on it
    directly."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (".create_source(", ".create_record(", ".update_source("):
        assert forbidden not in source, f"MB-10 must not call DatasetService.{forbidden}"


def test_never_imports_training_release_or_runtime_services() -> None:
    """MB-10 must never reach into the Training Engine, MB-07 Release
    Pipeline, or Runtime -- proven by absence of the import. MB-06's
    own service is imported for read-only Training Report analysis
    only (proven separately), and RAG Sandbox generation/evaluation/
    report services are imported exactly as MB-06 already established
    (proven separately) -- neither belongs on this forbidden list."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "PretrainingService", "ModelReleaseService", "MiniBrainInMemoryModelLoader",
        "MiniBrainReleasePipelineService", "RagSandboxCorpusService", "RagSandboxIndexService",
        "RagSandboxRetrievalService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-10 must not import {name}"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    """No Anthropic/OpenAI/Gemini/OpenRouter client library or API call
    exists anywhere in this file -- Multi-Provider Consensus is
    request-preparation and already-collected-result comparison only."""
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-10 must never call an external provider ({forbidden} found)"


def test_no_raw_sql_statements_in_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE)
    matches = pattern.findall(source)
    assert matches == [], f"unexpected raw SQL statement(s) found in the orchestrator: {matches}"


def test_no_direct_sqlite3_connection_usage() -> None:
    tree = _module_ast()
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
    assert "sqlite3" not in imported_names
    assert "database_connection" not in imported_names


def test_admin_review_draft_never_calls_another_phases_write_method() -> None:
    """All eight draft decisions (reject/edit/accept_draft/
    request_more_research/request_different_providers/
    request_local_draft/send_to_rag/archive) must only ever record the
    decision -- none may start training, deploy a model, or write a
    dataset."""
    body = _method_source("admin_review_draft")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "create_job",
        "DatasetService(", "create_source", "create_record", "run_generation", "run_evaluation",
    ):
        assert forbidden not in body, f"admin_review_draft() must not reference {forbidden}"


def test_check_training_gate_never_starts_training() -> None:
    """The training gate is an eligibility check only -- it must never
    submit, monitor, or start a training job."""
    body = _method_source("check_training_gate_stage")
    for forbidden in ("PretrainingService", "create_job(", "pretraining.", "promote("):
        assert forbidden not in body, f"check_training_gate_stage() must not reference {forbidden}"


def test_analyze_training_report_is_read_only() -> None:
    """Reading an MB-06 Training Report must never write anything back
    to MB-06's own session -- only this service's own session is
    updated."""
    body = _method_source("analyze_training_report")
    for forbidden in (
        "learning_supervisor.create_session", "learning_supervisor.submit_training_request",
        "learning_supervisor.validate_dataset", "learning_supervisor.decide_dataset",
        "learning_supervisor.decide_rag", "learning_supervisor.admin_review",
    ):
        assert forbidden not in body, f"analyze_training_report() must not reference {forbidden}"


def test_research_memory_table_is_never_updated_or_deleted_by_the_service() -> None:
    """Research memory is permanent -- the service must only ever call
    the repository's insert-only record_memory()/list_memory()/
    get_memory(), never anything implying mutation."""
    tree = _module_ast()
    calls = _attribute_calls(tree)
    memory_related = {m for r, m in calls if r == "self.repository" and "memory" in m.lower()}
    assert memory_related <= {"record_memory", "list_memory", "get_memory"}, (
        f"unexpected memory repository call(s): {memory_related}"
    )


def test_send_to_rag_requires_prior_accept_draft_in_source() -> None:
    """Structural proof that the RAG FIRST POLICY's admin gate is a
    real code guard, not just documentation."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert '"draft_admin_decision"] != "accept_draft"' in source
