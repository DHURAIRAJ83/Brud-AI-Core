"""MB-17: structural safety proofs for MiniBrainVisionRagService.

Static-analysis checks on the service source itself -- they prove "no
Dataset Studio write, no Document Workspace write, no MB-13/14/15/16
write, no training import, no runtime import, no release import, no
vision-model inference inside MB-17, only retrieval and read-only
access" is enforced by what code exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_vision_rag_service.py"
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


def test_only_calls_read_methods_on_multimodal_dataset_generator() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.multimodal_dataset"}
    assert used == {"session", "list_records"}, f"unexpected MiniBrainMultimodalDatasetGeneratorService method(s) called: {used}"


def test_only_calls_read_methods_on_vision_intelligence() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_intelligence"}
    assert used == {"session", "list_images", "list_objects"}, f"unexpected MiniBrainVisionIntelligenceService method(s) called: {used}"


def test_only_calls_read_methods_on_vision_model() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_model"}
    assert used == {"session", "list_predictions"}, f"unexpected MiniBrainVisionModelService method(s) called: {used}"


def test_never_calls_a_dataset_studio_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DatasetService" not in source, "MB-17 must not import or compose DatasetService"


def test_never_calls_a_document_workspace_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DocumentService" not in source, "MB-17 must not import or compose DocumentService"


def test_never_calls_an_upstream_phase_write_method() -> None:
    """MB-17 must never write to MB-14/15/16's own tables -- proven by
    the absence of any of their qualified mutating method calls."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "self.multimodal_dataset.run_", "self.multimodal_dataset.admin_review(",
        "self.multimodal_dataset.delete_draft(", "self.multimodal_dataset.split_dataset(",
        "self.multimodal_dataset.merge_datasets(",
        "self.vision_intelligence.run_", "self.vision_intelligence.annotate(",
        "self.vision_intelligence.admin_review(",
        "self.vision_model.run_", "self.vision_model.review_prediction(",
        "self.vision_model.admin_review(",
    ):
        assert forbidden not in source, f"MB-17 must not call upstream write method {forbidden}"


def test_never_imports_training_runtime_release_or_rag_sandbox_services() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "PretrainingService", "ModelReleaseService", "MiniBrainInMemoryModelLoader",
        "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "RagSandboxAnswerService", "RagSandboxEvaluationService", "RagSandboxReportService",
        "RagSandboxEligibilityService", "RagSandboxCorpusService", "RagSandboxIndexService",
        "RagSandboxRetrievalService", "InstructionTuningService", "BaseTrainingService",
        "RagRetrievalService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-17 must not import {name}"


def test_never_imports_a_vision_or_language_inference_backend() -> None:
    """MB-17 must never run its own model inference -- proven by the
    absence of MB-15's own vision backend imports and any generic ML
    inference library."""
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (
        "visioninferencebackend", "llavaggufvisionbackend", "onnxvisionbackend", "openvinovisionbackend",
        "llama_cpp", "torch", "transformers", "onnxruntime",
    ):
        assert forbidden not in source, f"MB-17 must never run its own model inference ({forbidden} found)"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-17 must never call an external provider ({forbidden} found)"


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


def test_create_session_requires_a_certified_dataset() -> None:
    body = _method_source("create_session")
    assert "admin_approved" in body


def test_admin_review_never_calls_another_phases_write_method() -> None:
    body = _method_source("admin_review")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "create_job", "create_source", "create_record", "update_record", "run_generation", "run_evaluation",
        "quantize", "export", "deploy",
    ):
        assert forbidden not in body, f"admin_review() must not reference {forbidden}"


def test_admin_review_is_the_only_method_that_sets_stage_closed_with_a_decision() -> None:
    """Structural proof no method other than `admin_review()` writes
    `admin_decision` -- a decision is never made automatically."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "admin_review":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"admin_decision": decision' not in body, f"{node.name}() must not write admin_decision -- only admin_review() may"


def test_grounded_answer_stage_never_calls_a_generation_model() -> None:
    body = _method_source("run_grounded_answer_stage")
    for forbidden in (".generate(", ".predict(", "openai", "anthropic"):
        assert forbidden not in body.lower(), f"run_grounded_answer_stage() must never call a generation model ({forbidden})"
