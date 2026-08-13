"""MB-16: structural safety proofs for
MiniBrainMultimodalDatasetGeneratorService.

Static-analysis checks on the service source itself -- they prove "no
Dataset Studio write, no Document Workspace write, no MB-13/14/15
write, no Training call, no Runtime call, no Deployment, no direct
SQL, only repositories, only public methods" is enforced by what code
exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_multimodal_dataset_generator_service.py"
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


def test_only_calls_get_and_page_on_document_service() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.document_service"}
    assert used == {"get", "page"}, f"unexpected DocumentService method(s) called: {used}"


def test_only_calls_session_on_language_intelligence() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.language_intelligence"}
    assert used == {"session"}, f"unexpected MiniBrainLanguageIntelligenceService method(s) called: {used}"


def test_only_calls_read_methods_on_vision_intelligence() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_intelligence"}
    assert used == {"session", "list_images", "list_objects"}, f"unexpected MiniBrainVisionIntelligenceService method(s) called: {used}"


def test_only_calls_read_methods_on_vision_model() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_model"}
    assert used == {"session", "list_predictions", "list_corrections", "list_learning_memory"}, f"unexpected MiniBrainVisionModelService method(s) called: {used}"


def test_only_calls_grouping_methods_on_duplicate_service() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.duplicate_service"}
    assert used == {"group_exact_duplicates", "group_normalized_duplicates"}, f"unexpected ExternalDatasetDuplicateService method(s) called: {used}"


def test_never_imports_dataset_service() -> None:
    """MB-16 never composes DatasetService at all -- proven by the
    absence of the import (its own repository also defines a
    same-named `create_record`/`update_record` for its own table,
    so a bare substring check on those names would false-positive)."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DatasetService" not in source, "MB-16 must not import or compose DatasetService"


def test_never_calls_a_document_workspace_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (".upload(", ".process(", ".edit_page(", ".segment("):
        assert forbidden not in source, f"MB-16 must not call DocumentService.{forbidden}"


def test_never_calls_an_upstream_phase_write_method() -> None:
    """MB-16 must never write to MB-13/14/15's own tables -- proven by
    the absence of any of their qualified mutating method calls."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "self.language_intelligence.run_", "self.language_intelligence.admin_review(",
        "self.vision_intelligence.run_", "self.vision_intelligence.annotate(",
        "self.vision_intelligence.admin_review(",
        "self.vision_model.run_", "self.vision_model.review_prediction(",
        "self.vision_model.admin_review(",
    ):
        assert forbidden not in source, f"MB-16 must not call upstream write method {forbidden}"


def test_never_imports_training_runtime_release_gguf_or_rag_services() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "PretrainingService", "ModelReleaseService", "MiniBrainInMemoryModelLoader",
        "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "RagSandboxAnswerService", "RagSandboxEvaluationService", "RagSandboxReportService",
        "RagSandboxEligibilityService", "RagSandboxCorpusService", "RagSandboxIndexService",
        "RagSandboxRetrievalService", "InstructionTuningService", "BaseTrainingService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-16 must not import {name}"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-16 must never call an external provider ({forbidden} found)"


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
    body = _method_source("admin_review")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "create_job", "create_source", "create_record", "update_record", "run_generation", "run_evaluation",
        "quantize", "export", "deploy",
    ):
        assert forbidden not in body, f"admin_review() must not reference {forbidden}"


def test_admin_review_is_the_only_method_that_writes_admin_decision() -> None:
    """Structural proof no method other than `admin_review()` writes
    the session into the 'certified' stage -- a read-only comparison
    (`session_row["stage"] == "certified"`, used by `delete_draft()`/
    `split_dataset()`/`merge_datasets()` to gate their own behavior)
    is not a write and is deliberately excluded from this check."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "admin_review":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"stage": "certified"' not in body, f"{node.name}() must not write stage 'certified' -- only admin_review() may"


def test_every_generated_record_is_created_unverified() -> None:
    """Structural proof -- `create_record` is never called with
    `verified=True` anywhere in the orchestrator."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "verified=True" not in source


def test_export_draft_never_writes_to_the_database() -> None:
    body = _method_source("export_draft")
    assert "self.repository.transaction(" not in body, "export_draft() must be read-only"
    assert "update_session" not in body and "create_record" not in body
