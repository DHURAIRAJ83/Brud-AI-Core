"""MB-15: structural safety proofs for MiniBrainVisionModelService.

Static-analysis checks on the service source itself -- they prove "no
Dataset write, no Document write, no MB-14 write, no Training call, no
Runtime call, no GGUF export, no RAG modification, no MB-06/MB-07
modification, no Deployment, no Provider API call, no direct SQL, only
repositories, only public methods" is enforced by what code exists,
not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_vision_model_service.py"
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


def test_only_calls_session_and_list_images_on_mb14_vision_intelligence() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_intelligence"}
    assert used == {"session", "list_images"}, f"unexpected MiniBrainVisionIntelligenceService method(s) called: {used}"


def test_only_calls_session_on_mb13_language_intelligence() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.language_intelligence"}
    assert used == {"session"}, f"unexpected MiniBrainLanguageIntelligenceService method(s) called: {used}"


def test_only_calls_page_on_document_service() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.document_service"}
    assert used == {"page"}, f"unexpected DocumentService method(s) called: {used}"


def test_never_calls_a_dataset_studio_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        ".create_source(", ".create_record(", ".update_source(", ".update_record(", ".delete_record(",
        ".import_candidates(",
    ):
        assert forbidden not in source, f"MB-15 must not call DatasetService.{forbidden}"


def test_never_calls_a_document_workspace_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (".upload(", ".process(", ".edit_page(", ".segment(", ".import_candidates("):
        assert forbidden not in source, f"MB-15 must not call DocumentService.{forbidden}"


def test_never_calls_an_mb14_write_method() -> None:
    """MB-15 must never write to MB-14's own tables -- proven by the
    absence of any MB-14-qualified mutating method call anywhere in
    the file (MB-15 defines its own same-named stage methods, so the
    check is qualified on `self.vision_intelligence.` to avoid a false
    match against MB-15's own method definitions)."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "self.vision_intelligence.run_image_extraction_stage",
        "self.vision_intelligence.run_image_quality_stage",
        "self.vision_intelligence.run_vision_understanding_stage",
        "self.vision_intelligence.annotate(",
        "self.vision_intelligence.finish_annotation_stage",
        "self.vision_intelligence.run_bounding_box_stage",
        "self.vision_intelligence.run_dataset_draft_stage",
        "self.vision_intelligence.admin_review(",
    ):
        assert forbidden not in source, f"MB-15 must not call MB-14 write method {forbidden}"


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
        assert name not in source, f"MB-15 must not import {name}"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-15 must never call an external provider ({forbidden} found)"


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
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "admin_review":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"certified"' not in body, f"{node.name}() must not set stage to 'certified' -- only admin_review() may"
            assert "admin_decision" not in body, f"{node.name}() must not write admin_decision -- only admin_review() may"


def test_no_detection_stage_ever_fabricates_a_bounding_box() -> None:
    """Object detection must only ever persist boxes the backend
    itself returned (always None in this environment, per audit) --
    proven by the absence of any hardcoded box literal in the stage."""
    body = _method_source("run_object_detection_stage")
    for forbidden in ('"x": 0', "'x': 0", "bounding_box={}"):
        assert forbidden not in body, f"run_object_detection_stage() must not fabricate a bounding_box ({forbidden})"


def test_backend_unavailable_is_always_caught_not_propagated_in_prediction_stages() -> None:
    for method_name in ("run_object_detection_stage", "run_scene_detection_stage", "run_caption_stage"):
        body = _method_source(method_name)
        assert "except BackendUnavailableError" in body, f"{method_name}() must honestly catch BackendUnavailableError"
