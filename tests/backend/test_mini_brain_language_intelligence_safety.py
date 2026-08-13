"""MB-13: structural safety proofs for
MiniBrainLanguageIntelligenceService.

Static-analysis checks on the service source itself -- they prove "no
Training Engine execution, no dataset write, no Runtime activation, no
deployment, no automatic approval, no automatic RAG execution, no
automatic provider execution" is enforced by what code exists, not
merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_language_intelligence_service.py"
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


def test_only_calls_list_records_on_dataset_service() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.dataset_service"}
    assert used == {"list_records"}, f"unexpected DatasetService method(s) called: {used}"


def test_only_calls_language_on_dataset_intelligence() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.dataset_intelligence"}
    assert used == {"language"}, f"unexpected MiniBrainDatasetIntelligenceService method(s) called: {used}"


def test_only_calls_list_rules_on_correction_registry() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.correction_registry"}
    assert used == {"list_rules"}, f"unexpected DocumentTamilCorrectionRegistryService method(s) called: {used}"


def test_only_calls_group_normalized_duplicates_on_duplicate_service() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.duplicate_service"}
    assert used == {"group_normalized_duplicates"}, f"unexpected ExternalDatasetDuplicateService method(s) called: {used}"


def test_never_imports_dataset_service_write_methods() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (".create_source(", ".create_record(", ".update_source(", ".update_record(", ".delete_record("):
        assert forbidden not in source, f"MB-13 must not call DatasetService.{forbidden}"


def test_never_imports_training_runtime_release_or_rag_services() -> None:
    """MB-13 must never reach into the Training Engine, Runtime,
    Release Pipeline, MB-06, or RAG Sandbox -- proven by absence of
    the import. MB-13 never calls RAG at all (unlike MB-06/MB-10/
    MB-11, which each run real RAG Sandbox generation/evaluation)."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "PretrainingService", "ModelReleaseService", "MiniBrainInMemoryModelLoader",
        "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "RagSandboxAnswerService", "RagSandboxEvaluationService", "RagSandboxReportService",
        "RagSandboxEligibilityService", "RagSandboxCorpusService", "RagSandboxIndexService",
        "RagSandboxRetrievalService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-13 must not import {name}"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-13 must never call an external provider ({forbidden} found)"


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


def test_admin_review_never_calls_another_phases_write_method() -> None:
    """All four admin decisions (approve/reject/request_fix/archive)
    must only ever record the decision -- none may start training,
    deploy a model, write a dataset, or call RAG."""
    body = _method_source("admin_review")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "create_job", "create_source", "create_record", "update_record", "run_generation", "run_evaluation",
    ):
        assert forbidden not in body, f"admin_review() must not reference {forbidden}"


def test_admin_review_is_the_only_method_that_writes_admin_decision() -> None:
    """Structural proof that no other method transitions a session to
    'certified' or sets 'admin_decision' -- approval is never automatic."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "admin_review":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"certified"' not in body, f"{node.name}() must not set stage to 'certified' -- only admin_review() may"
            assert "admin_decision" not in body or "admin_decision:" in body, (
                f"{node.name}() must not write admin_decision -- only admin_review() may"
            )


def test_ocr_correction_planner_and_spell_analyzer_never_apply_a_correction() -> None:
    """The service must never call anything resembling 'apply' on a
    suggested correction -- corrections are always suggestions only."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("apply_correction", ".save_draft(", "apply_suggested"):
        assert forbidden not in source, f"MB-13 must never apply a correction automatically ({forbidden} found)"
