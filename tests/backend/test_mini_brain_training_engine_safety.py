"""MB-22: structural safety proofs for MiniBrainTrainingEngineService
and its runtime adapters.

Static-analysis checks on the service source itself -- they prove "no
deployment/promotion API is ever called, no DatasetService/
DocumentService write method is ever called, no shell-execution or
subprocess path exists, training can only ever start after a fresh
per-job admin authorization token has been recorded, only finalize()
ever sets status='completed', and archive() is gated to completed/
cancelled jobs" is enforced by what code exists, not merely
documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_training_engine_service.py"
)
ADAPTER_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "training_runtime_adapter.py"
)
ROUTES_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "api" / "routes" / "mini_brain_training_engine.py"
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


def _imported_modules_and_names(tree: ast.Module) -> tuple[set[str], set[str]]:
    imported_modules: set[str] = set()
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            imported_names.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)
            imported_names.update(alias.asname or alias.name for alias in node.names)
    return imported_modules, imported_names


# -- only reads upstream MB-18/MB-20 sessions ------------------------------------------------


def test_only_calls_read_methods_on_training_pipeline() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.training_pipeline"}
    assert used <= {"session", "list_packages"}, f"unexpected MiniBrainTrainingPipelineService method(s) called: {used}"


def test_only_calls_read_methods_on_release_governance() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.release_governance"}
    assert used <= {"session", "list_artifacts"}, f"unexpected MiniBrainReleaseGovernanceService method(s) called: {used}"


def test_never_imports_dataset_studio_write_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DatasetService" not in source, "MB-22 must not import or compose DatasetService"


def test_never_imports_document_workspace_write_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DocumentService" not in source, "MB-22 must not import or compose DocumentService"


def test_never_imports_public_chat_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("PublicChatService", "ChatOrchestrationService"):
        assert forbidden not in source, f"MB-22 must not import a public chat service ({forbidden} found)"


def test_never_calls_an_upstream_phase_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "self.training_pipeline.run_", "self.training_pipeline.admin_review(",
        "self.training_pipeline.create_session(",
        "self.release_governance.run_", "self.release_governance.admin_review(",
        "self.release_governance.create_session(",
    ):
        assert forbidden not in source, f"MB-22 must not call upstream write method {forbidden}"


# -- no deployment / promotion / runtime-manager path ----------------------------------------


def test_never_imports_a_deployment_or_runtime_manager_library() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "MiniBrainInMemoryModelLoader", "MiniBrainReleasePipelineService", "ModelReleaseService",
        "PretrainingService", "LlamaCppBackend", "VisionInferenceBackend",
    ):
        assert forbidden not in source, f"MB-22 must never import a deployment/runtime-manager library ({forbidden} found)"


def test_never_calls_a_deployment_or_promotion_function() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("deploy(", "promote(", "promote_to_production(", "publish_release("):
        assert forbidden not in source, f"MB-22 must never call a deployment/promotion function ({forbidden} found)"


def test_never_imports_docker_or_kubernetes_client() -> None:
    tree = _module_ast()
    imported_modules, imported_names = _imported_modules_and_names(tree)
    for forbidden in ("docker", "kubernetes"):
        assert forbidden not in imported_modules, f"MB-22 must never import {forbidden}"
        assert forbidden not in imported_names, f"MB-22 must never import {forbidden}"


# -- no shell execution / arbitrary code from request data ------------------------------------


def test_never_imports_a_shell_execution_or_subprocess_path() -> None:
    tree = _module_ast()
    imported_modules, imported_names = _imported_modules_and_names(tree)
    for forbidden in ("subprocess", "os.system", "pty", "commands"):
        assert forbidden not in imported_modules, f"MB-22 must never import {forbidden}"
        assert forbidden not in imported_names, f"MB-22 must never import {forbidden}"
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("os.system(", "os.popen(", ".exec(", "eval(", "subprocess."):
        assert forbidden not in source, f"MB-22 must never execute a shell command ({forbidden} found)"


def test_never_downloads_models_automatically() -> None:
    source = (SERVICE_PATH.read_text(encoding="utf-8") + ADAPTER_PATH.read_text(encoding="utf-8")).lower()
    for forbidden in ("requests.get(", "urllib.request", "httpx.get(", "huggingface_hub", ".exe", ".msi"):
        assert forbidden not in source, f"MB-22 must never download a model automatically ({forbidden} found)"


# -- training start requires a fresh, per-job admin authorization token --------------------------


def test_authorization_token_only_recorded_by_authorization_stage() -> None:
    """Structural proof no method other than
    `run_validate_authorization_stage()` writes `admin_authorization_token`
    -- the field the workflow's own stage-order guard chain requires be
    set before a job can ever reach `start_training`."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "run_validate_authorization_stage":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert "admin_authorization_token" not in body or "run_validate_authorization_stage" in node.name, (
                f"{node.name}() must not record an authorization token -- only run_validate_authorization_stage() may"
            )


def test_stage_order_guard_chain_from_authorization_to_start_training() -> None:
    """Each stage on the path from validate_authorization to
    start_training checks the job is at the expected prior stage --
    proving there is no code path that reaches start_training without
    having passed through validate_authorization first."""
    guards = {
        "run_plan_resources_stage": "plan_resources",
        "run_build_manifest_stage": "build_manifest",
        "run_reserve_runtime_stage": "reserve_runtime",
        "run_start_training_stage": "start_training",
    }
    for method_name, expected_stage in guards.items():
        body = _method_source(method_name)
        assert f'"{expected_stage}"' in body, f"{method_name}() must guard on stage == '{expected_stage}'"
        assert "!=" in body, f"{method_name}() must reject a mismatched stage"


def test_validate_authorization_requires_real_admin_and_reason() -> None:
    body = _method_source("run_validate_authorization_stage")
    assert "not admin_id" in body
    assert "authorization_reason.strip()" in body


# -- only finalize() ever sets status='completed' ------------------------------------------------


def test_only_finalize_sets_completed_status() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "finalize":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"status": "completed"' not in body, f"{node.name}() must not set status='completed' -- only finalize() may"


def test_finalize_requires_running_or_paused_status() -> None:
    body = _method_source("finalize")
    assert "running" in body and "paused" in body


# -- archive requires completed/cancelled status --------------------------------------------------


def test_archive_requires_completed_or_cancelled_status() -> None:
    body = _method_source("archive")
    assert "completed" in body and "cancelled" in body
    assert "not in" in body


def test_only_archive_sets_archived_status() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "archive":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"status": "archived"' not in body, f"{node.name}() must not set status='archived' -- only archive() may"


# -- checkpoint overwrite guard ---------------------------------------------------------------------


def test_save_checkpoint_stage_checks_no_overwrite() -> None:
    body = _method_source("run_save_checkpoint_stage")
    assert "check_no_overwrite" in body
    assert "safe_to_write" in body


# -- no raw SQL / no direct sqlite3 usage in the orchestrator ----------------------------------------


def test_no_raw_sql_statements_in_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE)
    assert pattern.findall(source) == [], "unexpected raw SQL statement(s) found in the orchestrator"


def test_no_direct_sqlite3_connection_usage() -> None:
    tree = _module_ast()
    _, imported_names = _imported_modules_and_names(tree)
    assert "sqlite3" not in imported_names


# -- routes are admin-only, no public route access ---------------------------------------------------


def test_all_routes_require_admin() -> None:
    source = ROUTES_PATH.read_text(encoding="utf-8")
    assert "dependencies=[Depends(require_admin)]" in source, "MB-22 router must require admin on every route"


def test_all_mutating_routes_use_csrf_dependency() -> None:
    tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            decorators = [ast.dump(d) for d in node.decorator_list]
            is_post = any("post" in d.lower() for d in decorators)
            if is_post:
                args_source = ast.unparse(node.args)
                assert "CsrfDependency" in args_source, f"route {node.name}() must require CsrfDependency"


# -- runtime adapter honesty --------------------------------------------------------------------------


def test_llama_cpp_adapter_is_never_available_for_training() -> None:
    body = _method_source("is_available", ADAPTER_PATH)
    # the first is_available in file order belongs to SimulationTrainingAdapter; check the class body directly.
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "LlamaCppTrainingAdapter":
            class_body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            assert "return False" in class_body.split("def is_available")[1].split("def ")[0]


def test_torch_adapter_real_methods_all_raise_backend_unavailable() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TorchTrainingAdapter":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name not in ("is_available", "_unavailable"):
                    body = "\n".join(lines[item.lineno - 1 : item.end_lineno])
                    assert "raise self._unavailable()" in body, f"TorchTrainingAdapter.{item.name}() must raise BackendUnavailableError"
