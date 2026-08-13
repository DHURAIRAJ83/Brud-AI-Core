"""MB-11: structural safety proofs for MiniBrainDatasetEvolutionService.

Static-analysis checks on the service source itself -- they prove the
"never writes a dataset record, never starts training, never deploys,
never modifies RAG" boundary is enforced by what code exists, not
merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_dataset_evolution_service.py"
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
    assert used <= {"training", "analyze", "language"}, f"unexpected MiniBrainDatasetIntelligenceService method(s) called: {used}"


def test_only_calls_report_on_advanced_dataset_service() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.advanced_dataset"}
    assert used == {"report"}, f"unexpected MiniBrainAdvancedDatasetService method(s) called: {used}"


def test_only_calls_list_sessions_on_mb08() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.continuous_learning"}
    assert used == {"list_sessions"}, f"unexpected MB-08 method(s) called: {used}"


def test_only_calls_list_sessions_on_mb09() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.planning_center"}
    assert used == {"list_sessions"}, f"unexpected MB-09 method(s) called: {used}"


def test_only_calls_list_sessions_on_mb10() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.research_center"}
    assert used == {"list_sessions"}, f"unexpected MB-10 method(s) called: {used}"


def test_only_calls_expected_duplicate_service_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.duplicate_service"}
    assert used <= {"group_normalized_duplicates", "find_conflicts"}, (
        f"unexpected ExternalDatasetDuplicateService method(s) called: {used}"
    )


def test_rag_sandbox_chain_only_calls_generation_evaluation_and_finalize() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    assert {m for r, m in calls if r == "self.rag_answer"} == {"run_generation"}
    assert {m for r, m in calls if r == "self.rag_evaluation"} == {"run_evaluation"}
    assert {m for r, m in calls if r == "self.rag_report"} == {"finalize"}


def test_never_imports_dataset_service_write_class_beyond_construction() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (".create_source(", ".create_record(", ".update_source("):
        assert forbidden not in source, f"MB-11 must not call DatasetService.{forbidden}"


def test_never_imports_training_release_runtime_or_mb06_services() -> None:
    """MB-11 must never reach into the Training Engine, MB-06, MB-07, or
    Runtime -- proven by absence of the import. MB-06 is not in MB-11's
    own reuse list (unlike MB-10, which reads MB-06 read-only for
    Training Report analysis); MB-11 only ever documents the eventual
    manual admin hand-off to MB-06 in an event message string, never a
    method call."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "PretrainingService", "ModelReleaseService", "MiniBrainInMemoryModelLoader",
        "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "RagSandboxCorpusService", "RagSandboxIndexService", "RagSandboxRetrievalService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-11 must not import {name}"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-11 must never call an external provider ({forbidden} found)"


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


def test_admin_review_evolution_never_calls_another_phases_write_method() -> None:
    """All ten admin decisions must only ever record the decision --
    none may start training, deploy a model, or write a dataset."""
    body = _method_source("admin_review_evolution")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "create_job", "DatasetService(", "create_source", "create_record", "run_generation", "run_evaluation",
    ):
        assert forbidden not in body, f"admin_review_evolution() must not reference {forbidden}"


def test_admin_review_rag_never_calls_mb06() -> None:
    """Approving the RAG report must never itself submit anything to
    MB-06 -- that hand-off stays a separate, manual admin action."""
    body = _method_source("admin_review_rag")
    for forbidden in ("MiniBrainLearningSupervisorService", "create_session", "submit_training_request"):
        assert forbidden not in body, f"admin_review_rag() must not reference {forbidden}"


def test_send_to_rag_requires_prior_approve_evolution_in_source() -> None:
    """Structural proof that the two-step accept/send admin gate is a
    real code guard, not just documentation."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert '"draft_admin_decision"] != "approve_evolution"' in source
