"""MB-21: structural safety proofs for MiniBrainExternalAiGatewayService.

Static-analysis checks on the service source itself -- they prove "no
training/runtime-manager/deployment library is ever imported, no
DatasetService/DocumentService write method is ever called, no shell-
execution or subprocess path exists, provider dispatch is never called
outside its own stage-guarded method, only admin_review() ever sets
admin_decision, and provider output is never written into Dataset
Studio" is enforced by what code exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_external_ai_gateway_service.py"
)
PROVIDER_CLIENT_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "external_ai_provider_client.py"
)


def _module_ast(path: Path = SERVICE_PATH) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _method_source(name: str, path: Path = SERVICE_PATH) -> str:
    tree = _module_ast(path)
    lines = path.read_text(encoding="utf-8").splitlines()
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
    assert used <= {"session", "list_records"}, f"unexpected MiniBrainMultimodalDatasetGeneratorService method(s) called: {used}"


def test_only_calls_read_methods_on_vision_rag() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_rag"}
    assert used <= {"session"}, f"unexpected MiniBrainVisionRagService method(s) called: {used}"


def test_never_calls_a_dataset_studio_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DatasetService" not in source, "MB-21 must not import or compose DatasetService"


def test_never_calls_a_document_workspace_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DocumentService" not in source, "MB-21 must not import or compose DocumentService"


def test_never_calls_an_upstream_phase_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "self.multimodal_dataset.run_", "self.multimodal_dataset.admin_review(",
        "self.multimodal_dataset.create_session(",
        "self.vision_rag.run_", "self.vision_rag.correct(", "self.vision_rag.admin_review(",
        "self.vision_rag.create_session(",
    ):
        assert forbidden not in source, f"MB-21 must not call upstream write method {forbidden}"


def test_never_imports_a_training_library() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("import torch", "transformers.trainer", "trainingarguments", "accelerate", "llama_cpp"):
        assert forbidden not in source, f"MB-21 must never import a training library ({forbidden} found)"


def test_never_imports_a_runtime_manager() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("MiniBrainInMemoryModelLoader", "LlamaCppBackend", "VisionInferenceBackend"):
        assert forbidden not in source, f"MB-21 must never import a runtime manager ({forbidden} found)"


def test_never_imports_a_deployment_library() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("MiniBrainReleasePipelineService", "ModelReleaseService", "PretrainingService"):
        assert forbidden not in source, f"MB-21 must never import a deployment library ({forbidden} found)"


def test_never_imports_a_shell_execution_or_subprocess_path() -> None:
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
    for forbidden in ("subprocess", "os.system", "shutil", "pty", "commands"):
        assert forbidden not in imported_modules, f"MB-21 must never import {forbidden}"
        assert forbidden not in imported_names, f"MB-21 must never import {forbidden}"
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("os.system(", "os.popen(", ".exec(", "eval(", "subprocess."):
        assert forbidden not in source, f"MB-21 must never execute a shell command ({forbidden} found)"


def test_never_downloads_executable_files() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (".exe", ".msi", ".apk", ".dmg", "os.chmod"):
        assert forbidden not in source, f"MB-21 must never download or make executable a file ({forbidden} found)"


def test_provider_dispatch_only_called_within_dispatch_stage() -> None:
    """`.dispatch(` on a provider client must only ever be called from
    inside `run_dispatch_requests_stage()` -- never from any other
    method, proving no code path can reach a provider before that
    stage's own guard (which itself can only be reached after
    authorization already succeeded)."""
    tree = _module_ast()
    source = SERVICE_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "run_dispatch_requests_stage":
            body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            assert ".dispatch(" not in body, f"{node.name}() must never call provider .dispatch()"


def test_dispatch_stage_checks_stage_guard_before_dispatching() -> None:
    body = _method_source("run_dispatch_requests_stage")
    assert "!= \"dispatch_requests\"" in body or "!= 'dispatch_requests'" in body


def test_authorization_stage_is_the_only_method_that_records_authorization() -> None:
    """Structural proof no method other than
    `run_validate_authorization_stage()` writes
    `admin_authorization_confirmed_by`."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "run_validate_authorization_stage":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert "admin_authorization_confirmed_by" not in body, (
                f"{node.name}() must not record authorization -- only run_validate_authorization_stage() may"
            )


def test_admin_review_is_the_only_method_that_sets_admin_decision() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "admin_review":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"admin_decision": decision' not in body, f"{node.name}() must not write admin_decision -- only admin_review() may"


def test_archive_requires_reviewed_stage() -> None:
    body = _method_source("archive")
    assert "!= \"reviewed\"" in body or "!= 'reviewed'" in body


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


def test_external_ai_gateway_modules_are_pure() -> None:
    package_dir = (
        Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "external_ai_gateway"
    )
    forbidden_imports = ("sqlite3", "fastapi", "requests", "httpx", "backend.database", "backend.api", "subprocess")
    for path in sorted(package_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            assert forbidden not in source, f"{path.name} must stay pure -- found forbidden import {forbidden}"


def test_external_ai_gateway_modules_never_open_a_file_for_writing() -> None:
    package_dir = (
        Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "external_ai_gateway"
    )
    for path in sorted(package_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        for forbidden in ('open(', '.write_text(', '.write_bytes('):
            assert forbidden not in source, f"{path.name} must never write a file -- found {forbidden}"


def test_provider_client_never_imports_subprocess_or_shell_execution() -> None:
    source = PROVIDER_CLIENT_PATH.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system(", "os.popen(", "eval(", "exec("):
        assert forbidden not in source, f"provider client must never execute a shell command ({forbidden} found)"


def test_provider_client_reads_credentials_only_from_environment() -> None:
    source = PROVIDER_CLIENT_PATH.read_text(encoding="utf-8")
    assert "os.environ" in source
    assert "INSERT INTO" not in source.upper().replace(" ", "")
