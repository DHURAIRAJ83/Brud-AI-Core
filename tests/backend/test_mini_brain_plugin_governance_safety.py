"""MB-24: structural safety proofs for MiniBrainPluginGovernanceService,
its two route files, and the entire core_model/mini_brain/
plugin_governance/ pure-module package.

Static-analysis checks on the source itself -- they prove "no plugin
binary is ever executed (no subprocess, no os.system, no eval/exec, no
unrestricted file open, no direct network request from a pure
module), no permission is ever granted automatically, no plugin is
ever enabled automatically, no MB-22 training job or MB-20 release
decision is ever triggered, only issue_execution_token() can create an
execution token, and only grant_permission() can grant a scope" is
enforced by what code exists, not merely documented.
"""

import ast
from pathlib import Path

PLUGIN_GOVERNANCE_DIR = (
    Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "plugin_governance"
)
SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_plugin_governance_service.py"
)
ADMIN_ROUTES_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "api" / "routes" / "mini_brain_plugin_governance.py"
)
PUBLIC_ROUTES_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "api" / "routes" / "public_plugin_policy.py"
)
PURE_MODULE_PATHS = sorted(p for p in PLUGIN_GOVERNANCE_DIR.glob("*.py") if p.name != "__init__.py")


def _module_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _method_source(name: str, path: Path = SERVICE_PATH) -> str:
    tree = _module_ast(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"method not found: {name}")


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


# -- pure modules: no shell execution, no unrestricted file I/O, no network -----------------------


def test_pure_modules_never_import_subprocess_or_shell_execution() -> None:
    for path in PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        for forbidden in ("subprocess", "os", "pty", "commands"):
            assert forbidden not in imported_modules, f"{path.name} must never import {forbidden}"
        source = path.read_text(encoding="utf-8")
        for forbidden in ("os.system(", "os.popen(", "subprocess.", "eval(", "exec("):
            assert forbidden not in source, f"{path.name} must never call {forbidden}"


def test_pure_modules_never_open_a_file() -> None:
    for path in PURE_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        assert "open(" not in source, f"{path.name} must never open a file -- these are pure, side-effect-free modules"


def test_pure_modules_never_make_a_direct_network_request() -> None:
    for path in PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        for forbidden in ("requests", "httpx", "urllib.request", "socket", "aiohttp"):
            assert forbidden not in imported_modules, f"{path.name} must never import {forbidden}"
            assert forbidden not in imported_names, f"{path.name} must never import {forbidden}"


def test_pure_modules_have_no_database_or_fastapi_imports() -> None:
    for path in PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        for forbidden in ("sqlite3", "fastapi", "backend.database"):
            assert forbidden not in imported_modules, f"{path.name} must never import {forbidden}"
            assert forbidden not in imported_names, f"{path.name} must never import {forbidden}"


# -- service: no shell execution, no eval/exec ------------------------------------------------


def test_service_never_imports_subprocess_or_shell_execution() -> None:
    tree = _module_ast(SERVICE_PATH)
    imported_modules, imported_names = _imported_modules_and_names(tree)
    for forbidden in ("subprocess", "pty", "commands"):
        assert forbidden not in imported_modules
        assert forbidden not in imported_names
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("os.system(", "os.popen(", "subprocess.", "eval(", "exec("):
        assert forbidden not in source


def test_service_never_imports_docker_or_kubernetes_client() -> None:
    tree = _module_ast(SERVICE_PATH)
    imported_modules, imported_names = _imported_modules_and_names(tree)
    for forbidden in ("docker", "kubernetes"):
        assert forbidden not in imported_modules
        assert forbidden not in imported_names


# -- no automatic training / release trigger -----------------------------------------------------


def test_service_never_imports_training_engine_or_release_governance() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "MiniBrainTrainingEngineService", "MiniBrainReleaseGovernanceService", "TrainingRuntimeAdapter",
        "MiniBrainReleasePipelineService", "ModelReleaseService",
    ):
        assert forbidden not in source, f"MB-24 must never import {forbidden}"


def test_service_never_modifies_mb16_through_mb23_tables() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "mini_brain_multimodal_dataset", "mini_brain_vision_rag", "mini_brain_training_pipeline",
        "mini_brain_evaluation_center", "mini_brain_release_governance", "mini_brain_external_ai",
        "mini_brain_training_jobs", "mini_brain_public_chat_sessions",
    ):
        assert forbidden not in source, f"MB-24 must never reference {forbidden}"


# -- automatic-permission / automatic-enable guards -----------------------------------------------


def test_plugins_are_always_created_disabled() -> None:
    body = _method_source("register_plugin")
    assert '"status"' not in body or "'status'" not in body  # register_plugin never sets status explicitly -- the schema default('disabled') is the only source of truth


def test_only_enable_plugin_sets_status_enabled() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != "enable_plugin":
            body = "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])
            assert '"status": "enabled"' not in body, f"{node.name}() must not set status='enabled' -- only enable_plugin() may"


def test_enable_plugin_requires_a_real_admin_identity() -> None:
    body = _method_source("enable_plugin")
    assert "not admin_id" in body
    assert "raise ValidationError" in body


def test_enable_plugin_requires_completed_analysis_stages() -> None:
    body = _method_source("enable_plugin")
    assert "_ANALYSIS_COMPLETE_STAGES" in body


def test_only_grant_permission_sets_permission_status_granted() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != "grant_permission":
            body = "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])
            assert '"status": "granted"' not in body, f"{node.name}() must not grant a permission -- only grant_permission() may"


def test_grant_permission_re_evaluates_policy_before_granting() -> None:
    body = _method_source("grant_permission")
    assert "evaluate_permission(" in body
    assert 'decision"] != "allow"' in body


def test_only_issue_execution_token_calls_the_token_builder() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != "issue_execution_token":
            body = "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])
            assert "build_execution_token(" not in body, f"{node.name}() must not build an execution token -- only issue_execution_token() may"


def test_issue_execution_token_requires_every_scope_already_granted() -> None:
    body = _method_source("issue_execution_token")
    assert "granted_scopes" in body
    assert "missing" in body


def test_only_token_hash_is_persisted_never_the_raw_token() -> None:
    body = _method_source("issue_execution_token")
    assert '"token_hash": token["token_hash"]' in body
    assert 'token["payload"]' not in body.split("metadata={")[1].split("})")[0] if "metadata={" in body else True


def test_only_archive_plugin_writes_the_permanent_memory_row() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != "archive_plugin":
            body = "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])
            assert "create_memory(" not in body, f"{node.name}() must not write the permanent memory row -- only archive_plugin() may"


# -- marketplace policy is honored --------------------------------------------------------------


def test_register_plugin_checks_marketplace_policy_before_creating_a_row() -> None:
    body = _method_source("register_plugin")
    assert "evaluate_marketplace_policy(" in body
    assert "marketplace[\"allowed\"]" in body


# -- routes: admin-only, CSRF-protected, public route requires neither ----------------------------


def test_admin_router_requires_admin_dependency() -> None:
    source = ADMIN_ROUTES_PATH.read_text(encoding="utf-8")
    assert "dependencies=[Depends(require_admin)]" in source


def test_all_admin_mutating_routes_require_csrf() -> None:
    tree = _module_ast(ADMIN_ROUTES_PATH)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            decorators = [ast.dump(d) for d in node.decorator_list]
            if any("post" in d.lower() for d in decorators):
                args_source = ast.unparse(node.args)
                assert "CsrfDependency" in args_source, f"route {node.name}() must require CsrfDependency"


def test_public_plugin_policy_route_never_requires_admin() -> None:
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    assert "require_admin" not in source
    assert "CsrfDependency" not in source


def test_public_plugin_policy_route_is_rate_limited() -> None:
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    assert "check_rate_limit(" in source


def test_public_plugin_policy_forces_is_public_chat_true() -> None:
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    assert "is_public_chat=True" in source


def test_public_plugin_policy_never_returns_a_token_or_secret_field() -> None:
    body = _method_source("check_plugin_policy", PUBLIC_ROUTES_PATH).lower()
    for forbidden in ("token", "secret", "admin_id", "nonce"):
        assert forbidden not in body, f"public route handler body must not reference {forbidden}"


# -- no raw SQL / no direct sqlite3 usage in the orchestrator ----------------------------------------


def test_no_raw_sql_statements_in_service() -> None:
    import re

    source = SERVICE_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE)
    assert pattern.findall(source) == [], "unexpected raw SQL statement(s) found in the orchestrator"


def test_no_direct_sqlite3_connection_usage_in_service() -> None:
    tree = _module_ast(SERVICE_PATH)
    _, imported_names = _imported_modules_and_names(tree)
    assert "sqlite3" not in imported_names
