"""MB-26: structural safety proofs for MiniBrainVoiceRuntimeService,
its two route files, and the entire core_model/mini_brain/
voice_runtime/ pure-module package.

Static-analysis checks on the source itself -- proving "no cloud
upload call exists, no requests/httpx is imported by any pure module,
no background recording thread/loop is ever started, no subprocess/
os.system/eval is used, no raw audio is ever persisted to the
database, the public route can never set admin_authorized=True, and
the service never re-runs text safety on a PublicChatRoutingService
reply" is enforced by what code exists, not merely documented.
"""

from __future__ import annotations

import ast
from pathlib import Path

VOICE_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "voice_runtime"
SERVICE_PATH = Path(__file__).resolve().parents[2] / "backend" / "services" / "mini_brain_voice_runtime_service.py"
ADMIN_ROUTES_PATH = Path(__file__).resolve().parents[2] / "backend" / "api" / "routes" / "mini_brain_voice_runtime.py"
PUBLIC_ROUTES_PATH = Path(__file__).resolve().parents[2] / "backend" / "api" / "routes" / "public_voice_runtime.py"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "backend" / "database" / "schema.py"
PURE_MODULE_PATHS = sorted(p for p in VOICE_RUNTIME_DIR.glob("*.py") if p.name != "__init__.py")
# Backend adapters are legitimately impure (real model I/O), excluded from
# the "pure modules never do X" checks below and covered by their own
# dedicated, narrower assertions further down.
BACKEND_ADAPTER_NAMES = {"faster_whisper_backend.py", "coqui_tts_backend.py", "audio_session_manager.py"}
STRICTLY_PURE_MODULE_PATHS = [p for p in PURE_MODULE_PATHS if p.name not in BACKEND_ADAPTER_NAMES]


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


# -- no cloud speech APIs / no direct network client anywhere ------------------------------------


def test_pure_modules_never_import_a_network_client() -> None:
    for path in STRICTLY_PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        for forbidden in ("requests", "httpx", "urllib.request", "socket", "aiohttp"):
            assert forbidden not in imported_modules, f"{path.name} must never import {forbidden}"
            assert forbidden not in imported_names, f"{path.name} must never import {forbidden}"


def test_service_never_imports_a_raw_network_client() -> None:
    tree = _module_ast(SERVICE_PATH)
    imported_modules, imported_names = _imported_modules_and_names(tree)
    for forbidden in ("requests", "httpx", "urllib.request", "socket", "aiohttp"):
        assert forbidden not in imported_modules
        assert forbidden not in imported_names


def test_backend_adapters_do_not_import_a_generic_http_client() -> None:
    """faster_whisper/Coqui are loaded via their own model-loading APIs,
    never a raw HTTP client used to phone out to a cloud speech API."""
    for name in ("faster_whisper_backend.py", "coqui_tts_backend.py"):
        source = (VOICE_RUNTIME_DIR / name).read_text(encoding="utf-8")
        for forbidden in ("requests.", "httpx.", "urllib.request", "aiohttp."):
            assert forbidden not in source, f"{name} must never call {forbidden}"


def test_no_known_cloud_speech_provider_hostname_anywhere_in_package() -> None:
    forbidden_hosts = (
        "speech.googleapis.com", "api.openai.com", "azure.microsoft.com",
        "transcribe.us-east-1.amazonaws.com", "api.assemblyai.com",
    )
    all_source = "\n".join(p.read_text(encoding="utf-8") for p in PURE_MODULE_PATHS)
    all_source += SERVICE_PATH.read_text(encoding="utf-8")
    for host in forbidden_hosts:
        assert host not in all_source


# -- no subprocess / os.system / eval / exec ------------------------------------------------------


_FORBIDDEN_CALL_PATTERNS = (
    "os.system(", "os.popen(", "subprocess.run(", "subprocess.Popen(", "subprocess.call(",
    "subprocess.check_call(", "subprocess.check_output(", "eval(", "exec(",
)


def test_pure_modules_never_import_subprocess_or_shell_execution() -> None:
    for path in PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, _ = _imported_modules_and_names(tree)
        for forbidden in ("subprocess", "pty", "commands"):
            assert forbidden not in imported_modules, f"{path.name} must never import {forbidden}"
        source = path.read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_CALL_PATTERNS:
            assert forbidden not in source, f"{path.name} must never call {forbidden}"


def test_service_never_imports_subprocess_or_uses_eval_exec() -> None:
    tree = _module_ast(SERVICE_PATH)
    imported_modules, _ = _imported_modules_and_names(tree)
    for forbidden in ("subprocess", "pty", "commands"):
        assert forbidden not in imported_modules
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


def test_routes_never_import_subprocess_or_use_eval_exec() -> None:
    for path in (ADMIN_ROUTES_PATH, PUBLIC_ROUTES_PATH):
        source = path.read_text(encoding="utf-8")
        assert "import subprocess" not in source
        for forbidden in _FORBIDDEN_CALL_PATTERNS:
            assert forbidden not in source, f"{path.name} must never use {forbidden}"


# -- no background recording thread / loop anywhere -------------------------------------------------


def test_no_background_thread_or_task_construct_anywhere_in_package() -> None:
    forbidden = ("threading.Thread(", "asyncio.create_task(", "multiprocessing.Process(", "while True:")
    for path in PURE_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path.name} must never contain {token}"


def test_service_never_starts_a_background_thread_or_loop() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for token in ("threading.Thread(", "asyncio.create_task(", "multiprocessing.Process(", "while True:"):
        assert token not in source


def test_wakeword_policy_contains_no_listening_construct() -> None:
    """The single strongest structural proof of the wake-word non-goal:
    the module that decides wake-word activation contains no loop,
    thread, or task construct of any kind -- it can only ever return a
    static, hardcoded-inactive dict."""
    source = (VOICE_RUNTIME_DIR / "wakeword_policy.py").read_text(encoding="utf-8")
    for token in ("while ", "for ", "Thread(", "create_task(", "Process(", "async def"):
        assert token not in source, f"wakeword_policy.py must never contain {token!r}"


def test_wakeword_policy_always_returns_active_false() -> None:
    """AST-walks the function's own return dict literal (not a string
    match against source text, which is fragile against quote style and
    docstring prose) to prove the 'active' key can only ever be the
    literal False -- never True, never a variable, never conditional."""
    tree = _module_ast(VOICE_RUNTIME_DIR / "wakeword_policy.py")
    function_node = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate_wakeword"
    )
    return_nodes = [n for n in ast.walk(function_node) if isinstance(n, ast.Return)]
    assert len(return_nodes) == 1, "evaluate_wakeword must have exactly one return statement"
    dict_node = return_nodes[0].value
    assert isinstance(dict_node, ast.Dict)
    active_index = next(i for i, key in enumerate(dict_node.keys) if ast.literal_eval(key) == "active")
    active_value_node = dict_node.values[active_index]
    assert isinstance(active_value_node, ast.Constant)
    assert active_value_node.value is False


# -- no raw audio ever persisted to the database -----------------------------------------------------


def test_no_raw_audio_column_defined_in_schema() -> None:
    """Checks for an actual BLOB-typed column declaration (the only
    SQLite type that could hold raw binary audio) and for column names
    that would literally be raw audio storage -- deliberately does NOT
    bare-substring-match "audio_bytes", since the legitimate integer
    counter column `total_audio_bytes` would false-positive against
    that (it stores a byte *count*, an INTEGER, never audio content)."""
    schema_source = SCHEMA_PATH.read_text(encoding="utf-8")
    start = schema_source.index("PHASE67_SCHEMA")
    end = schema_source.index('"""', schema_source.index('"""', start) + 3)
    voice_schema = schema_source[start:end]
    assert "BLOB" not in voice_schema, "voice schema must never define a BLOB-typed column"
    for line in voice_schema.splitlines():
        stripped = line.strip()
        for forbidden_column in ("audio_bytes ", "raw_audio ", "audio_blob ", "audio_data "):
            assert not stripped.startswith(forbidden_column), (
                f"voice schema must never define a raw-audio-storage column: {stripped!r}"
            )


def test_repository_create_message_never_accepts_raw_audio_bytes_param() -> None:
    repo_path = (
        Path(__file__).resolve().parents[2]
        / "backend" / "database" / "repositories" / "mini_brain_voice_runtime.py"
    )
    tree = _module_ast(repo_path)
    function_node = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "create_message"
    )
    arg_names = {arg.arg for arg in function_node.args.args + function_node.args.kwonlyargs}
    for forbidden in ("audio_bytes", "raw_audio", "audio_blob"):
        assert forbidden not in arg_names


def test_service_never_persists_result_audio_bytes_to_the_database() -> None:
    """`result["audio_bytes"]` (an in-memory dict key on a backend's own
    return value) is legitimately read by the service to pass to
    audio_session_manager.write_output() -- but must never itself be
    passed as an argument to a self.repository.* persistence call.
    Scoped to actual repository-call lines specifically, not the whole
    file, since the raw dict-key read itself is expected and safe."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    persisted_call_lines = [
        line for line in source.splitlines()
        if "self.repository.create_" in line or "self.repository.update_" in line
    ]
    combined = "\n".join(persisted_call_lines)
    assert 'result["audio_bytes"]' not in combined
    assert "audio_bytes=" not in combined


def test_audio_session_manager_is_the_only_module_touching_the_filesystem_for_audio() -> None:
    """Every other pure module in the package must never call open() or
    Path.write_bytes()/read_bytes() directly -- only
    audio_session_manager.py (the designated impure module) may."""
    for path in STRICTLY_PURE_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        for forbidden in ("open(", "write_bytes(", "read_bytes("):
            assert forbidden not in source, f"{path.name} must never call {forbidden}"


# -- admin_authorized can only ever be set True from the admin route ---------------------------------


def test_public_route_never_sets_admin_authorized_true() -> None:
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    assert "admin_authorized=True" not in source
    assert "admin_authorized" not in source


def test_only_admin_route_sets_admin_authorized_true() -> None:
    source = ADMIN_ROUTES_PATH.read_text(encoding="utf-8")
    assert "admin_authorized=True" in source


def test_admin_authorized_true_only_reachable_via_authenticated_admin_route() -> None:
    """The literal string 'admin_authorized=True' must never appear
    anywhere in the public route file or in any pure module -- the only
    place in the entire codebase that can produce it is the CSRF- and
    require_admin-gated admin route."""
    forbidden_paths = [PUBLIC_ROUTES_PATH, *PURE_MODULE_PATHS]
    for path in forbidden_paths:
        source = path.read_text(encoding="utf-8")
        assert "admin_authorized=True" not in source, f"{path.name} must never hardcode admin_authorized=True"


# -- routes: admin-only, CSRF-protected, public route forces public_chat mode, rate-limited -----------


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


def test_public_route_never_requires_admin_or_csrf() -> None:
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    assert "require_admin" not in source
    assert "CsrfDependency" not in source


def test_public_route_is_rate_limited() -> None:
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    assert "check_rate_limit(" in source


def test_public_route_always_forces_public_chat_session_mode() -> None:
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    assert 'session_mode="public_chat"' in source
    assert 'session_mode="admin_assistant"' not in source


def test_admin_route_always_forces_admin_assistant_session_mode() -> None:
    source = ADMIN_ROUTES_PATH.read_text(encoding="utf-8")
    assert 'session_mode="admin_assistant"' in source


# -- text safety reuse: the service never re-runs it, PublicChatRoutingService already did -------------


def test_service_never_imports_evaluate_output_safety() -> None:
    """The reply returned by PublicChatRoutingService.handle_message()
    has already passed evaluate_output_safety() internally -- MB-26
    must never import it a second time (the module's own docstring
    legitimately mentions the function by name in prose, so this check
    is import-based, not a whole-file substring match)."""
    tree = _module_ast(SERVICE_PATH)
    _, imported_names = _imported_modules_and_names(tree)
    assert "evaluate_output_safety" not in imported_names


def test_service_reuses_public_chat_routing_service_handle_message() -> None:
    body = _method_source("run_route_to_public_chat_stage")
    assert "PublicChatRoutingService(" in body
    assert ".handle_message(" in body


def test_service_reuses_feedback_sanitizer_not_a_reimplementation() -> None:
    sanitizer_source = (VOICE_RUNTIME_DIR / "voice_result_sanitizer.py").read_text(encoding="utf-8")
    assert "from core_model.mini_brain.public_chat_runtime.feedback_sanitizer import sanitize_text" in sanitizer_source


# -- diagnostics discloses honestly, always live-probed, never cached ---------------------------------


def test_diagnostics_probes_backend_availability_live() -> None:
    body = _method_source("diagnostics")
    assert "faster_whisper_backend.is_available()" in body
    assert "coqui_tts_backend.is_available()" in body


def test_diagnostics_includes_all_required_fields() -> None:
    diagnostics_module_source = (VOICE_RUNTIME_DIR / "voice_diagnostics.py").read_text(encoding="utf-8")
    for field in (
        "stt_backend", "stt_available", "tts_backend", "tts_available", "local_only",
        "gpu_required", "microphone_runtime_enabled", "wakeword_enabled",
        "max_record_seconds", "max_audio_mb",
    ):
        assert f'"{field}"' in diagnostics_module_source


# -- no raw SQL / no direct sqlite3 usage in the orchestrator ------------------------------------------


def test_no_raw_sql_statements_in_service() -> None:
    import re

    source = SERVICE_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE)
    assert pattern.findall(source) == [], "unexpected raw SQL statement(s) found in the orchestrator"


def test_no_direct_sqlite3_connection_usage_in_service() -> None:
    tree = _module_ast(SERVICE_PATH)
    _, imported_names = _imported_modules_and_names(tree)
    assert "sqlite3" not in imported_names
