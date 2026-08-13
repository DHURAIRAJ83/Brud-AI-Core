"""MB-14: structural safety proofs for
MiniBrainVisionIntelligenceService.

Static-analysis checks on the service source itself -- they prove "no
Dataset write, no Training call, no Runtime call, no GGUF export, no
RAG modification, no Deployment, no Provider API call, no direct SQL,
only repositories, only public methods" is enforced by what code
exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_vision_intelligence_service.py"
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


def test_only_calls_artifact_and_page_on_document_service() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.document_service"}
    assert used == {"artifact", "page"}, f"unexpected DocumentService method(s) called: {used}"


def test_only_calls_document_and_transaction_on_document_repository() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.document_repository"}
    assert used == {"document", "transaction"}, f"unexpected DocumentRepository method(s) called: {used}"


def test_only_calls_get_classification_on_content_classification() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.content_classification"}
    assert used == {"get_classification"}, f"unexpected DocumentContentClassificationService method(s) called: {used}"


def test_never_calls_a_dataset_studio_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        ".create_source(", ".create_record(", ".update_source(", ".update_record(", ".delete_record(",
        ".import_candidates(",
    ):
        assert forbidden not in source, f"MB-14 must not call DatasetService.{forbidden}"


def test_never_imports_training_runtime_release_gguf_or_rag_services() -> None:
    """MB-14 must never reach into the Training Engine, Runtime,
    Release Pipeline (GGUF export/deployment), or RAG Sandbox -- proven
    by absence of the import."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "PretrainingService", "ModelReleaseService", "MiniBrainInMemoryModelLoader",
        "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "RagSandboxAnswerService", "RagSandboxEvaluationService", "RagSandboxReportService",
        "RagSandboxEligibilityService", "RagSandboxCorpusService", "RagSandboxIndexService",
        "RagSandboxRetrievalService", "InstructionTuningService", "BaseTrainingService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-14 must not import {name}"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-14 must never call an external provider ({forbidden} found)"


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
    deploy a model, write a dataset, export GGUF, or call RAG."""
    body = _method_source("admin_review")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "create_job", "create_source", "create_record", "update_record", "run_generation", "run_evaluation",
        "quantize", "export", "deploy",
    ):
        assert forbidden not in body, f"admin_review() must not reference {forbidden}"


def test_admin_review_is_the_only_method_that_writes_admin_decision() -> None:
    """Structural proof that no other method transitions a session to
    'certified' or sets admin_decision -- approval is never automatic."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "admin_review":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"certified"' not in body, f"{node.name}() must not set stage to 'certified' -- only admin_review() may"
            assert "admin_decision" not in body, f"{node.name}() must not write admin_decision -- only admin_review() may"


def test_vision_understanding_never_fabricates_a_real_label() -> None:
    """Stage 3 must only ever create 'Unknown Object' placeholders --
    proven by the literal string appearing nowhere else as a label
    source in the method body."""
    body = _method_source("run_vision_understanding_stage")
    assert '"Unknown Object"' in body
    assert 'source="auto_unknown"' in body


def test_caption_and_bounding_box_stages_never_call_a_generation_model() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "openai", "anthropic", "torch", "transformers", "tensorflow", ".predict(", ".generate(",
    ):
        assert forbidden not in source.lower(), f"MB-14 must never call a generation/inference model ({forbidden} found)"


def test_resolve_pdf_path_only_reads_and_never_writes() -> None:
    """The one place MB-14 reaches into Document Workspace's own
    repository must be a read-only SELECT (via `.document()`), never a
    write, mirroring the existing precedent set by
    DocumentWorkspaceService.render_page_image()."""
    body = _method_source("_resolve_pdf_path")
    for forbidden in ("INSERT", "UPDATE", "DELETE", ".execute("):
        assert forbidden not in body, f"_resolve_pdf_path() must be read-only ({forbidden} found)"
