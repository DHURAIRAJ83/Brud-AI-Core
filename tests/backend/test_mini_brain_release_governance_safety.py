"""MB-20: structural safety proofs for MiniBrainReleaseGovernanceService.

Static-analysis checks on the service source itself -- they prove "no
runtime manager, deployment library, Docker/K8s client, external
provider SDK, training library, quantization/export API, or inference
API is ever imported; no DatasetService/DocumentService write method
is ever called; no MB-16/17/18/19 write method is ever called; only
admin_review() can approve a release; and the package builder never
calls a deployment function" is enforced by what code exists, not
merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_release_governance_service.py"
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


def test_only_calls_read_methods_on_multimodal_dataset() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.multimodal_dataset"}
    assert used == {"session"}, f"unexpected MiniBrainMultimodalDatasetGeneratorService method(s) called: {used}"


def test_only_calls_read_methods_on_vision_rag() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_rag"}
    assert used == {"session"}, f"unexpected MiniBrainVisionRagService method(s) called: {used}"


def test_only_calls_read_methods_on_training_pipeline() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.training_pipeline"}
    assert used == {"session", "list_packages"}, f"unexpected MiniBrainTrainingPipelineService method(s) called: {used}"


def test_only_calls_read_methods_on_evaluation_center() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.evaluation_center"}
    assert used == {"session", "list_results"}, f"unexpected MiniBrainEvaluationCenterService method(s) called: {used}"


def test_never_calls_a_dataset_studio_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DatasetService" not in source, "MB-20 must not import or compose DatasetService"


def test_never_calls_a_document_workspace_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DocumentService" not in source, "MB-20 must not import or compose DocumentService"


def test_never_calls_an_upstream_phase_write_method() -> None:
    """MB-20 must never write to MB-16/17/18/19's own tables -- proven
    by the absence of any of their qualified mutating method calls."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "self.multimodal_dataset.run_", "self.multimodal_dataset.admin_review(",
        "self.vision_rag.run_", "self.vision_rag.correct(", "self.vision_rag.admin_review(",
        "self.training_pipeline.run_", "self.training_pipeline.admin_review(",
        "self.training_pipeline.create_session(",
        "self.evaluation_center.run_", "self.evaluation_center.admin_review(",
        "self.evaluation_center.create_session(",
    ):
        assert forbidden not in source, f"MB-20 must not call upstream write method {forbidden}"


def test_never_imports_a_runtime_manager() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("MiniBrainInMemoryModelLoader", "LlamaCppBackend", "VisionInferenceBackend"):
        assert forbidden not in source, f"MB-20 must never import a runtime manager ({forbidden} found)"


def test_never_imports_a_deployment_library() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("MiniBrainReleasePipelineService", "ModelReleaseService", "PretrainingService"):
        assert forbidden not in source, f"MB-20 must never import a deployment library ({forbidden} found)"


def test_never_imports_docker_or_kubernetes_client() -> None:
    tree = _module_ast()
    imported_names = set()
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            imported_names.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)
            imported_names.update(alias.asname or alias.name for alias in node.names)
    for forbidden in ("docker", "kubernetes", "k8s", "subprocess"):
        assert forbidden not in imported_modules, f"MB-20 must never import {forbidden}"
        assert forbidden not in imported_names, f"MB-20 must never import {forbidden}"


def test_never_imports_an_external_provider_sdk() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (
        "anthropic", "openai", "google.generativeai", "genai.", "huggingface_hub", "requests.post",
        "httpx.post", "urllib.request",
    ):
        assert forbidden not in source, f"MB-20 must never call an external provider SDK ({forbidden} found)"


def test_never_imports_a_training_library() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("import torch", "transformers.trainer", "trainingarguments", "accelerate", "llama_cpp"):
        assert forbidden not in source, f"MB-20 must never import a training library ({forbidden} found)"


def test_never_imports_a_quantization_or_export_api() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("convert_to_gguf", ".gguf", "quantize(", "export_onnx", "torch.save", "state_dict"):
        assert forbidden not in source, f"MB-20 must never import a quantization/export API ({forbidden} found)"


def test_never_imports_an_inference_api() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (".generate(", ".predict(", "load_model("):
        assert forbidden not in source, f"MB-20 must never call an inference API ({forbidden} found)"


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


def test_build_release_package_stage_never_calls_a_deployment_function() -> None:
    body = _method_source("run_build_release_package_stage")
    for forbidden in (
        "deploy(", "activate_runtime", "start_runtime", "load_model(", ".generate(", ".predict(",
        "quantize(", "docker", "kubernetes",
    ):
        assert forbidden not in body, f"run_build_release_package_stage() must never call a deployment function ({forbidden})"


def test_admin_review_never_calls_another_phases_write_method() -> None:
    body = _method_source("admin_review")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "MiniBrainInMemoryModelLoader",
        "create_job", "create_source", "create_record", "update_record", "run_generation", "run_evaluation",
        "quantize(", "export(", "deploy(", "train(", "fit(",
    ):
        assert forbidden not in body, f"admin_review() must not reference {forbidden}"


def test_admin_review_is_the_only_method_that_sets_admin_decision() -> None:
    """Structural proof no method other than `admin_review()` writes
    `admin_decision` -- an approved/rejected/archived state is never
    set automatically."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "admin_review":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"admin_decision": decision' not in body, f"{node.name}() must not write admin_decision -- only admin_review() may"


def test_release_governance_modules_are_pure() -> None:
    """Every one of the 13 core_model/mini_brain/release_governance/
    modules must import no database, filesystem-write, deployment, or
    HTTP library -- proving they are pure, deterministic functions."""
    package_dir = (
        Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "release_governance"
    )
    forbidden_imports = ("sqlite3", "fastapi", "requests", "httpx", "backend.database", "backend.api", "docker", "kubernetes")
    for path in sorted(package_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            assert forbidden not in source, f"{path.name} must stay pure -- found forbidden import {forbidden}"


def test_release_governance_modules_never_open_a_file_for_writing() -> None:
    package_dir = (
        Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "release_governance"
    )
    for path in sorted(package_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        for forbidden in ('open(', '.write_text(', '.write_bytes('):
            assert forbidden not in source, f"{path.name} must never write a file -- found {forbidden}"
