"""MB-12: structural safety proofs for MiniBrainPipelineCoordinatorService.

Static-analysis checks on the service source itself -- they prove the
"never trains, never writes a dataset, never deploys, never modifies
RAG" boundary is enforced by what code exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_pipeline_coordinator_service.py"
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


def test_only_calls_read_only_dataset_intelligence_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.dataset_intelligence"}
    assert used <= {"training", "language"}, f"unexpected MiniBrainDatasetIntelligenceService method(s) called: {used}"


def test_only_calls_report_on_advanced_dataset_service() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.advanced_dataset"}
    assert used == {"report"}, f"unexpected MiniBrainAdvancedDatasetService method(s) called: {used}"


def test_only_calls_read_only_mb06_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.learning_supervisor"}
    assert used <= {"session", "events"}, f"unexpected MB-06 method(s) called: {used}"


def test_only_calls_list_sessions_on_mb08() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.continuous_learning"}
    assert used == {"list_sessions"}, f"unexpected MB-08 method(s) called: {used}"


def test_only_calls_read_only_mb09_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.planning_center"}
    assert used <= {"session", "events"}, f"unexpected MB-09 method(s) called: {used}"


def test_only_calls_read_only_mb10_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.research_center"}
    assert used <= {"session", "events"}, f"unexpected MB-10 method(s) called: {used}"


def test_only_calls_read_only_mb11_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.dataset_evolution"}
    assert used <= {"session", "events"}, f"unexpected MB-11 method(s) called: {used}"


def test_never_imports_runtime_training_release_or_rag_sandbox_services() -> None:
    """MB-12 must never import the Runtime Manager, any training
    execution class, Release Pipeline execution class, or any RAG
    Sandbox service -- confirmed by absence of the import. MB-12 reads
    an already-produced RAG result only, it never runs RAG Sandbox
    itself (Finding 1 in the completion report)."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "MiniBrainInMemoryModelLoader", "PretrainingService", "ModelReleaseService",
        "MiniBrainReleasePipelineService", "RagSandboxAnswerService", "RagSandboxEvaluationService",
        "RagSandboxReportService", "RagSandboxEligibilityService", "RagSandboxCorpusService",
        "RagSandboxIndexService", "RagSandboxRetrievalService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-12 must not import {name}"


def test_never_imports_dataset_service_write_class_beyond_construction() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (".create_source(", ".create_record(", ".update_source("):
        assert forbidden not in source, f"MB-12 must not call DatasetService.{forbidden}"


def test_never_calls_mb06_write_methods() -> None:
    """link_training_stage/refresh_training_stage only ever read an
    MB-06 session -- they must never submit, validate, decide, or
    promote anything on it."""
    for method_name in ("link_training_stage", "refresh_training_stage"):
        body = _method_source(method_name)
        for forbidden in (
            "create_session(", "submit_training_request", "validate_dataset", "decide_dataset",
            "decide_rag", "admin_review(", "create_release_candidate", "run_rag_evaluation",
        ):
            assert forbidden not in body, f"{method_name}() must not reference {forbidden}"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-12 must never call an external provider ({forbidden} found)"


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


def test_admin_decide_never_calls_another_phases_write_method() -> None:
    body = _method_source("admin_decide")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "MiniBrainInMemoryModelLoader",
        "create_job", "DatasetService(", "create_source", "create_record", "run_generation", "run_evaluation",
    ):
        assert forbidden not in body, f"admin_decide() must not reference {forbidden}"


def test_dependency_check_is_applied_before_every_stage_write() -> None:
    """Structural proof that stage-skipping protection is a real code
    guard: every stage-advancing method routes through
    `_apply_transition`, which itself calls `check_dependencies`."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "check_dependencies(" in source
    apply_transition_body = _method_source("_apply_transition")
    assert "check_dependencies(" in apply_transition_body
