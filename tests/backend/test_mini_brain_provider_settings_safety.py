"""MB-27: structural safety proofs for MiniBrainProviderSettingsService,
its route file, the connection-adapters module, and the entire
core_model/mini_brain/provider_settings/ pure-module package.

Static-analysis checks on the source itself, via `ast` node
inspection or narrowed call-pattern substrings -- deliberately never a
naive whole-file substring match against arbitrary prose. This is not
a stylistic preference: MB-26's own safety test file hit real false
positives from checks like `"subprocess." not in source` tripping on
a docstring sentence ending "...never a subprocess." -- every check
here is written to survive that exact failure mode from the start.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROVIDER_SETTINGS_DIR = Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "provider_settings"
SERVICE_PATH = Path(__file__).resolve().parents[2] / "backend" / "services" / "mini_brain_provider_settings_service.py"
ADAPTERS_PATH = Path(__file__).resolve().parents[2] / "backend" / "services" / "provider_settings_connection_adapters.py"
ROUTES_PATH = Path(__file__).resolve().parents[2] / "backend" / "api" / "routes" / "mini_brain_provider_settings.py"
MODELS_PATH = Path(__file__).resolve().parents[2] / "backend" / "models" / "mini_brain_provider_settings.py"
REPOSITORY_PATH = Path(__file__).resolve().parents[2] / "backend" / "database" / "repositories" / "mini_brain_provider_settings.py"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "backend" / "database" / "schema.py"

PURE_MODULE_PATHS = sorted(p for p in PROVIDER_SETTINGS_DIR.glob("*.py") if p.name != "__init__.py")
ENCRYPTOR_PATH = PROVIDER_SETTINGS_DIR / "secret_encryptor.py"
STRICTLY_PURE_MODULE_PATHS = [p for p in PURE_MODULE_PATHS if p.name != "secret_encryptor.py"]

_FORBIDDEN_CALL_PATTERNS = (
    "os.system(", "os.popen(", "subprocess.run(", "subprocess.Popen(", "subprocess.call(",
    "subprocess.check_call(", "subprocess.check_output(", "eval(", "exec(",
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


# -- pure modules never import fastapi/sqlite3/httpx/requests/subprocess -----------------------


def test_strictly_pure_modules_never_import_forbidden_modules() -> None:
    forbidden = {"fastapi", "sqlite3", "httpx", "requests", "subprocess"}
    for path in STRICTLY_PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        overlap = forbidden & (imported_modules | imported_names)
        assert not overlap, f"{path.name} must never import {overlap}"


def test_secret_encryptor_is_the_only_module_permitted_os_or_cryptography() -> None:
    """secret_encryptor.py is the phase spec's own explicit, documented
    exception -- every OTHER pure module must never import os or
    cryptography."""
    for path in STRICTLY_PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        assert "os" not in imported_modules, f"{path.name} must not import os -- only secret_encryptor.py may"
        assert not any(name.startswith("cryptography") for name in imported_modules), (
            f"{path.name} must not import cryptography -- only secret_encryptor.py may"
        )


def test_secret_encryptor_imports_are_exactly_the_documented_exception() -> None:
    tree = _module_ast(ENCRYPTOR_PATH)
    imported_modules, _ = _imported_modules_and_names(tree)
    assert "os" in imported_modules
    assert "cryptography.fernet" in imported_modules


def test_pure_package_never_imports_subprocess_or_uses_eval_exec() -> None:
    for path in PURE_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_CALL_PATTERNS:
            assert forbidden not in source, f"{path.name} must never call {forbidden}"


def test_service_never_imports_subprocess_or_uses_eval_exec() -> None:
    tree = _module_ast(SERVICE_PATH)
    imported_modules, _ = _imported_modules_and_names(tree)
    assert "subprocess" not in imported_modules
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


def test_routes_never_import_subprocess_or_use_eval_exec() -> None:
    source = ROUTES_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


def test_adapters_never_use_subprocess_eval_exec() -> None:
    source = ADAPTERS_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


# -- no raw SQL string literals in the service (repository is where SQL belongs) ---------------


def test_service_contains_no_raw_sql_string_literals() -> None:
    """Inspects only ast.Constant string-literal nodes -- not the whole
    file's characters -- so a docstring mentioning the word 'SELECT' in
    passing would not false-positive."""
    tree = _module_ast(SERVICE_PATH)
    sql_keywords = ("SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for keyword in sql_keywords:
                assert keyword not in node.value, f"raw SQL literal found in service: {node.value!r}"


def test_service_never_imports_sqlite3_directly() -> None:
    tree = _module_ast(SERVICE_PATH)
    _, imported_names = _imported_modules_and_names(tree)
    assert "sqlite3" not in imported_names


# -- no training/deployment imports ------------------------------------------------------------


def test_no_training_or_deployment_imports_anywhere_in_the_phase() -> None:
    forbidden_substrings = ("training", "deployment", "pretraining", "governed_build")
    all_paths = [*PURE_MODULE_PATHS, SERVICE_PATH, ADAPTERS_PATH, ROUTES_PATH, MODELS_PATH, REPOSITORY_PATH]
    for path in all_paths:
        tree = _module_ast(path)
        imported_modules, _ = _imported_modules_and_names(tree)
        for module_name in imported_modules:
            lowered = module_name.lower()
            for forbidden in forbidden_substrings:
                assert forbidden not in lowered, f"{path.name} imports {module_name!r}, which looks training/deployment-related"


# -- no response model defines a plaintext-secret-shaped field ---------------------------------


def test_no_response_model_defines_a_secret_shaped_field() -> None:
    """Walks ast.AnnAssign field definitions on every DomainModel class
    in the models file and asserts none is named like a plaintext
    secret holder. SetProviderSecretRequest.value is the one documented
    exception (a REQUEST model, not used as a response_model)."""
    forbidden_field_names = {"encrypted_value", "api_key", "secret_value", "plaintext_value"}
    tree = _module_ast(MODELS_PATH)
    response_class_names = {
        "ProviderSettingResponse", "MaskedSecretResponse", "ConnectionTestResponse", "DiagnosticsResponse",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in response_class_names:
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    assert item.target.id not in forbidden_field_names, (
                        f"{node.name}.{item.target.id} is a forbidden secret-shaped response field"
                    )
                    assert item.target.id != "value", f"{node.name}.value would be a plaintext-shaped response field"


def test_secret_plaintext_field_exists_only_on_the_one_documented_request_model() -> None:
    tree = _module_ast(MODELS_PATH)
    classes_with_value_field = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == "value":
                    classes_with_value_field.append(node.name)
    assert classes_with_value_field == ["SetProviderSecretRequest"]


# -- no route returns encrypted_value or a raw secret ------------------------------------------


def test_repository_has_no_public_secret_projection_function() -> None:
    """There must be no function in the repository shaped like
    `public_secret_row` -- the whole point is that no "public"
    projection of the secrets table exists at all."""
    source = REPOSITORY_PATH.read_text(encoding="utf-8")
    assert "def public_secret_row(" not in source


def test_list_secrets_return_value_never_flows_directly_into_a_route_response() -> None:
    """AST-walks the route file's function bodies and confirms none of
    them call `list_secrets` directly -- only the service does, and
    only to compute presence/names, never to hand raw rows to a route."""
    tree = _module_ast(ROUTES_PATH)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "list_secrets", "routes must never call list_secrets directly"


# -- test_connection is reachable only from the one designated admin route ---------------------


def test_adapter_factory_is_called_only_from_the_service_test_connection_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != "test_connection":
            body = "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])
            assert "adapter_for_provider(" not in body, f"{node.name}() must not call adapter_for_provider directly"


def test_route_file_exposes_exactly_one_test_connection_endpoint() -> None:
    tree = _module_ast(ROUTES_PATH)
    test_connection_routes = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "test_connection"
    ]
    assert len(test_connection_routes) == 1


def test_service_test_connection_calls_the_adapter_factory() -> None:
    body = _method_source("test_connection")
    assert "adapter_for_provider(" in body


# -- audit events and settings memory are append-only (schema-level trigger check) -------------


def _phase68_schema_text() -> str:
    schema_source = SCHEMA_PATH.read_text(encoding="utf-8")
    start = schema_source.index("PHASE68_SCHEMA")
    end = schema_source.index('"""', schema_source.index('"""', start) + 3)
    return schema_source[start:end]


def test_provider_audit_events_table_has_two_immutability_triggers() -> None:
    phase_schema = _phase68_schema_text()
    assert "CREATE TRIGGER IF NOT EXISTS mini_brain_provider_audit_events_immutable_update" in phase_schema
    assert "CREATE TRIGGER IF NOT EXISTS mini_brain_provider_audit_events_immutable_delete" in phase_schema


def test_provider_settings_memory_table_has_two_immutability_triggers() -> None:
    phase_schema = _phase68_schema_text()
    assert "CREATE TRIGGER IF NOT EXISTS mini_brain_provider_settings_memory_immutable_update" in phase_schema
    assert "CREATE TRIGGER IF NOT EXISTS mini_brain_provider_settings_memory_immutable_delete" in phase_schema


def test_no_blob_column_defined_anywhere_in_phase68_schema() -> None:
    """Strips SQL comment lines (`--`) before checking -- this schema
    block's own comment explicitly discusses *why* TEXT was chosen over
    BLOB ("TEXT, not BLOB"), which would false-positive a raw
    whole-text substring check. Only real DDL lines are inspected."""
    phase_schema = _phase68_schema_text()
    ddl_only = "\n".join(
        line for line in phase_schema.splitlines() if not line.strip().startswith("--")
    )
    assert "BLOB" not in ddl_only


def test_no_raw_secret_storage_column_defined_outside_the_secrets_table() -> None:
    phase_schema = _phase68_schema_text()
    settings_table_start = phase_schema.index("CREATE TABLE IF NOT EXISTS mini_brain_provider_settings (")
    settings_table_end = phase_schema.index(");", settings_table_start)
    settings_table_ddl = phase_schema[settings_table_start:settings_table_end]
    assert "encrypted_value" not in settings_table_ddl


# -- export excludes secret fields (structural, not just behavioral) ---------------------------


def test_export_builder_function_signature_never_accepts_secret_rows() -> None:
    """AST-inspects settings_export_builder.build()'s parameter names --
    none may be named/shaped like a secrets-table input, structurally
    guaranteeing secrets cannot flow into an export regardless of what
    the caller passes."""
    export_builder_path = PROVIDER_SETTINGS_DIR / "settings_export_builder.py"
    tree = _module_ast(export_builder_path)
    build_fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "build")
    param_names = {arg.arg for arg in build_fn.args.args}
    assert not any("secret" in name.lower() for name in param_names)


def test_service_export_settings_never_calls_list_secrets() -> None:
    """AST-walks the real ast.Call nodes inside export_settings() --
    not a substring match against the method's raw source, which would
    false-positive against this very method's own docstring
    explaining *why* it deliberately never calls list_secrets()."""
    tree = _module_ast(SERVICE_PATH)
    export_fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "export_settings"
    )
    for node in ast.walk(export_fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "list_secrets", "export_settings() must never call list_secrets()"
