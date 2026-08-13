"""MB-28: structural safety proofs for MiniBrainLlmRuntimeService, its
route file, the adapter layer, and the entire
core_model/mini_brain/llm_runtime/ pure-module package.

Static-analysis checks on the source itself, via `ast` node inspection
or narrowed call-pattern substrings -- deliberately never a naive
whole-file substring match against arbitrary prose. This is not a
stylistic preference: MB-26's and MB-27's own safety test files both
hit real false positives from checks like `"subprocess." not in
source` tripping on a docstring sentence, or `"BLOB" not in schema`
tripping on a schema comment -- every check here is written to survive
that exact failure mode from the start.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.services.mini_brain_llm_adapter import LlamaCppMiniBrainAdapter, resolve_confined_model_path

REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_RUNTIME_DIR = REPO_ROOT / "core_model" / "mini_brain" / "llm_runtime"
SERVICE_PATH = REPO_ROOT / "backend" / "services" / "mini_brain_llm_runtime_service.py"
ADAPTER_PATH = REPO_ROOT / "backend" / "services" / "mini_brain_llm_adapter.py"
ROUTES_PATH = REPO_ROOT / "backend" / "api" / "routes" / "mini_brain_llm_runtime.py"
MODELS_PATH = REPO_ROOT / "backend" / "models" / "mini_brain_llm_runtime.py"
REPOSITORY_PATH = REPO_ROOT / "backend" / "database" / "repositories" / "mini_brain_llm_runtime.py"
SCHEMA_PATH = REPO_ROOT / "backend" / "database" / "schema.py"

PURE_MODULE_PATHS = sorted(p for p in LLM_RUNTIME_DIR.glob("*.py") if p.name != "__init__.py")

_FORBIDDEN_CALL_PATTERNS = (
    "os.system(", "os.popen(", "subprocess.run(", "subprocess.Popen(", "subprocess.call(",
    "subprocess.check_call(", "subprocess.check_output(", "eval(", "exec(",
)

_FORBIDDEN_IMPORT_PATTERNS = (
    "training_pipeline_service", "model_release_service", "model_evaluation_service",
    "release_governance_service", "pretraining_service",
)


def _module_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


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


def _method_source(name: str, path: Path = SERVICE_PATH) -> str:
    tree = _module_ast(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"method not found: {name}")


def _call_names(tree: ast.AST) -> list[str]:
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                names.append(func.attr)
            elif isinstance(func, ast.Name):
                names.append(func.id)
    return names


# -- pure package: no impure imports, no subprocess/eval/exec ---------------------------------


def test_pure_package_never_imports_forbidden_modules() -> None:
    forbidden = {"fastapi", "sqlite3", "httpx", "requests", "subprocess", "os"}
    for path in PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        overlap = forbidden & (imported_modules | imported_names)
        assert not overlap, f"{path.name} must never import {overlap}"


def test_pure_package_never_calls_subprocess_eval_exec() -> None:
    for path in PURE_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_CALL_PATTERNS:
            assert forbidden not in source, f"{path.name} must never call {forbidden}"


def test_adapter_is_the_only_module_permitted_llama_cpp_or_httpx() -> None:
    """The adapter layer is the phase spec's own explicit, documented
    exception -- no pure module may import llama_cpp or httpx."""
    for path in PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        assert "llama_cpp" not in (imported_modules | imported_names)
        assert "httpx" not in (imported_modules | imported_names)


def test_adapter_module_never_calls_subprocess_eval_exec() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


def test_service_never_calls_subprocess_eval_exec() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


def test_routes_never_call_subprocess_eval_exec() -> None:
    source = ROUTES_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


# -- never touches training/deployment/release-governance-approval, or the Phase 8 system ----------


def test_service_never_imports_training_or_deployment_or_governance_approval() -> None:
    tree = _module_ast(SERVICE_PATH)
    imported_modules, imported_names = _imported_modules_and_names(tree)
    combined = imported_modules | imported_names
    for forbidden in _FORBIDDEN_IMPORT_PATTERNS:
        assert not any(forbidden in name for name in combined), f"service must never import {forbidden}"


def test_service_never_imports_the_phase_8_admin_assistant_system() -> None:
    """MB-28 is additive and parallel -- it must never import
    `admin_assistant_service`, `admin_assistant_chat_service`,
    `admin_assistant_tools`, or `core_model.admin_assistant.
    action_registry` (the separate, pre-existing governed-proposal /
    chat system this phase deliberately does not touch), though it MAY
    reuse the read-only `dashboard_registry` (via
    `admin_explainer_templates.py`)."""
    tree = _module_ast(SERVICE_PATH)
    imported_modules, imported_names = _imported_modules_and_names(tree)
    combined = imported_modules | imported_names
    forbidden = {"admin_assistant_service", "admin_assistant_chat_service", "admin_assistant_tools", "action_registry"}
    assert not (forbidden & combined)


def test_routes_never_reuse_the_phase_8_prefix() -> None:
    source = ROUTES_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    router_call_args = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "APIRouter":
            for keyword in node.keywords:
                if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                    router_call_args.append(keyword.value.value)
    assert router_call_args == ["/admin/mini-brain/llm-runtime"]


def test_no_public_route_prefix_in_routes_file() -> None:
    tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "APIRouter":
            for keyword in node.keywords:
                if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                    assert "public" not in keyword.value.value


# -- execute_for_admin_assistant is only ever called from the designated dispatch method -------------


def test_execute_for_admin_assistant_called_only_from_dispatch_method() -> None:
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            calls = _call_names(node)
            if "execute_for_admin_assistant" in calls:
                assert node.name == "_dispatch_tool_call", (
                    f"execute_for_admin_assistant must only be called from _dispatch_tool_call, found in {node.name}"
                )


def test_dispatch_tool_call_requires_real_admin_id_argument() -> None:
    source = _method_source("_dispatch_tool_call")
    assert "admin_id" in source
    assert "requester_admin_public_id=admin_id" in source


def test_external_provider_adapter_constructed_only_via_resolve_backend() -> None:
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for call_node in ast.walk(node):
                if isinstance(call_node, ast.Call) and isinstance(call_node.func, ast.Name) and call_node.func.id == "ExternalProviderMiniBrainAdapter":
                    assert node.name == "_resolve_backend", (
                        f"ExternalProviderMiniBrainAdapter must only be constructed in _resolve_backend, found in {node.name}"
                    )


# -- no secret-shaped response fields anywhere in models.py -------------------------------------------


def test_models_never_define_a_secret_shaped_field() -> None:
    tree = _module_ast(MODELS_PATH)
    forbidden_field_names = {"value", "encrypted_value", "api_key", "secret_value", "raw_value"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    assert statement.target.id not in forbidden_field_names, (
                        f"{node.name}.{statement.target.id} looks secret-shaped"
                    )


def test_diagnostics_model_never_exposes_a_field_named_model_path() -> None:
    """Only `configured_model_path` (always masked to filename-only by
    runtime_diagnostics_builder.mask_model_path()) may appear -- never a
    raw, unmasked `model_path` field."""
    tree = _module_ast(MODELS_PATH)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DiagnosticsResponse":
            field_names = {
                statement.target.id for statement in node.body
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
            }
            assert "model_path" not in field_names
            assert "configured_model_path" in field_names


# -- schema: both new tables have real two-trigger append-only/permanent protection -------------------


def _phase69_schema_text() -> str:
    source = SCHEMA_PATH.read_text(encoding="utf-8")
    start = source.index('PHASE69_SCHEMA = """')
    end = source.index('"""', start + len('PHASE69_SCHEMA = """'))
    return source[start:end]


def test_runtime_events_table_has_both_immutability_triggers() -> None:
    schema_text = _phase69_schema_text()
    assert "mini_brain_llm_runtime_events_immutable_update" in schema_text
    assert "mini_brain_llm_runtime_events_immutable_delete" in schema_text


def test_runtime_memory_table_has_both_immutability_triggers() -> None:
    schema_text = _phase69_schema_text()
    assert "mini_brain_llm_runtime_memory_immutable_update" in schema_text
    assert "mini_brain_llm_runtime_memory_immutable_delete" in schema_text


def test_phase69_never_redefines_a_prior_phase_table() -> None:
    schema_text = _phase69_schema_text()
    ddl_only = "\n".join(line for line in schema_text.splitlines() if not line.strip().startswith("--"))
    prior_phase_tables = ("mini_brain_provider_settings", "mini_brain_voice_sessions", "mini_brain_plugins")
    for table_name in prior_phase_tables:
        assert f"CREATE TABLE IF NOT EXISTS {table_name} (" not in ddl_only


# -- model-path confinement (user-requested, non-negotiable) ------------------------------------------
# Exercised against the real LlamaCppMiniBrainAdapter.is_available()/loader path with real
# tmp_path-based fixtures, not mocked.


@pytest.fixture
def confinement_settings(tmp_path: Path) -> Settings:
    allowed = tmp_path / "models"
    allowed.mkdir()
    (tmp_path / "outside").mkdir()
    (tmp_path / "models_evil").mkdir()
    return Settings(
        allowed_model_dir=allowed, allowed_data_dir=tmp_path,
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )


def test_confinement_rejects_path_outside_allowed_dir(confinement_settings: Settings, tmp_path: Path) -> None:
    outside_file = tmp_path / "outside" / "evil.gguf"
    outside_file.write_bytes(b"x")
    assert resolve_confined_model_path(settings=confinement_settings, model_path=str(outside_file)) is None


def test_confinement_rejects_dotdot_traversal(confinement_settings: Settings) -> None:
    traversal = str(confinement_settings.resolved_allowed_model_dir / ".." / "outside" / "evil.gguf")
    (confinement_settings.resolved_allowed_model_dir.parent / "outside" / "evil.gguf").write_bytes(b"x")
    assert resolve_confined_model_path(settings=confinement_settings, model_path=traversal) is None


def test_confinement_rejects_symlink_escaping_confined_dir(confinement_settings: Settings, tmp_path: Path) -> None:
    real_secret = tmp_path / "outside" / "secret.gguf"
    real_secret.write_bytes(b"y")
    symlink = confinement_settings.resolved_allowed_model_dir / "link.gguf"
    symlink.symlink_to(real_secret)
    assert resolve_confined_model_path(settings=confinement_settings, model_path=str(symlink)) is None


def test_confinement_accepts_genuinely_confined_real_file(confinement_settings: Settings) -> None:
    model_file = confinement_settings.resolved_allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"z")
    resolved = resolve_confined_model_path(settings=confinement_settings, model_path=str(model_file))
    assert resolved == model_file.resolve()


def test_confinement_rejects_nonexistent_path_honestly(confinement_settings: Settings) -> None:
    missing = confinement_settings.resolved_allowed_model_dir / "nope.gguf"
    assert resolve_confined_model_path(settings=confinement_settings, model_path=str(missing)) is None
    adapter = LlamaCppMiniBrainAdapter(settings=confinement_settings, model_path=str(missing))
    assert adapter.is_available() is False  # honest, no crash


def test_confinement_rejects_sibling_dir_sharing_name_prefix(confinement_settings: Settings, tmp_path: Path) -> None:
    """Guards against a naive str.startswith() check standing in for
    real Path-parent containment -- `models_evil/` shares the
    `models` prefix with the real confined dir but is NOT inside it."""
    evil_file = tmp_path / "models_evil" / "model.gguf"
    evil_file.write_bytes(b"w")
    assert resolve_confined_model_path(settings=confinement_settings, model_path=str(evil_file)) is None
