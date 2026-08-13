"""MB-29: structural + behavioral safety proofs for Local Model
Auto-Setup & Provider Configuration Center.

Static-analysis checks use `ast` node inspection or narrowed
call-pattern substrings -- never a naive whole-file substring match
against arbitrary prose (the twice-learned lesson from MB-26/27/28's
own docstring-prose false positives). Confinement/escape checks are
exercised against the real scanner and real service with real
`tmp_path` fixtures, not mocked.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.local_setup_service import LocalSetupService
from core_model.mini_brain.local_setup import model_scanner
from core_model.mini_brain.provider_settings import secret_encryptor

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SETUP_DIR = REPO_ROOT / "core_model" / "mini_brain" / "local_setup"
SERVICE_PATH = REPO_ROOT / "backend" / "services" / "local_setup_service.py"
ROUTES_PATH = REPO_ROOT / "backend" / "api" / "routes" / "mini_brain_local_setup.py"
MODELS_PATH = REPO_ROOT / "backend" / "models" / "local_setup.py"

ALL_MODULE_PATHS = sorted(p for p in LOCAL_SETUP_DIR.glob("*.py") if p.name != "__init__.py")
# hardware_probe.py and model_scanner.py are this phase's own disclosed
# real-I/O exceptions (see __init__.py) -- every other module must be
# strictly pure (no I/O at all, not even the reads those two allow).
STRICTLY_PURE_MODULE_PATHS = [
    p for p in ALL_MODULE_PATHS if p.name not in ("hardware_probe.py", "model_scanner.py")
]

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


# -- pure package: no fastapi/sqlite3/subprocess-shell-execution/network -----------------------


def test_no_module_in_package_ever_imports_fastapi_or_sqlite3() -> None:
    for path in ALL_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        overlap = {"fastapi", "sqlite3"} & (imported_modules | imported_names)
        assert not overlap, f"{path.name} must never import {overlap}"


def test_no_module_in_package_ever_calls_subprocess_eval_exec() -> None:
    for path in ALL_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_CALL_PATTERNS:
            assert forbidden not in source, f"{path.name} must never call {forbidden}"


def test_no_module_in_package_ever_imports_network_libraries() -> None:
    forbidden = {"httpx", "requests", "urllib", "socket", "http.client"}
    for path in ALL_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        overlap = forbidden & (imported_modules | imported_names)
        assert not overlap, f"{path.name} must never import {overlap} -- no network access in this package"


def test_hardware_probe_and_model_scanner_are_the_only_disclosed_real_io_modules() -> None:
    """Every other module must never import filesystem/OS-introspection
    modules used for real I/O beyond what pure data transformation needs."""
    io_capable = {"shutil"}
    for path in STRICTLY_PURE_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        overlap = io_capable & (imported_modules | imported_names)
        assert not overlap, f"{path.name} must not perform real I/O -- only hardware_probe.py/model_scanner.py may"


def test_service_never_calls_subprocess_eval_exec() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


def test_routes_never_call_subprocess_eval_exec() -> None:
    source = ROUTES_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


# -- route prefix is genuinely disjoint from every prior phase --------------------------------


def test_routes_prefix_is_local_setup_only() -> None:
    tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"))
    prefixes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "APIRouter":
            for keyword in node.keywords:
                if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                    prefixes.append(keyword.value.value)
    assert prefixes == ["/admin/mini-brain/local-setup"]


# -- no secret-shaped response field, no plaintext echo -------------------------------------------


def test_models_never_define_a_secret_shaped_response_field() -> None:
    """`SaveProviderRequest.api_key` (a REQUEST field) is the one
    allowed exception, mirroring MB-27's own SetProviderSecretRequest.value
    discipline -- but no other class, and no response-shaped class at
    all, may define a field named api_key/value/encrypted_value/secret_value."""
    tree = _module_ast(MODELS_PATH)
    forbidden_field_names = {"encrypted_value", "secret_value", "raw_value", "value"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    field_name = statement.target.id
                    assert field_name not in forbidden_field_names, f"{node.name}.{field_name} looks secret-shaped"
                    if field_name == "api_key":
                        assert node.name == "SaveProviderRequest", "api_key must only ever appear on the request model"


def test_service_never_reads_encrypted_value_directly() -> None:
    """The service must reuse MB-27's `MiniBrainProviderSettingsService.
    set_secret()` for storing secrets -- it must never touch
    `encrypted_value` or import `secret_encryptor` itself (that stays
    MB-27's own internal concern)."""
    tree = _module_ast(SERVICE_PATH)
    imported_modules, imported_names = _imported_modules_and_names(tree)
    assert "secret_encryptor" not in imported_names
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "encrypted_value" not in source


# -- real confinement / escape tests -----------------------------------------------------------


def test_scanner_never_escapes_allowed_directory(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "escape.gguf").write_bytes(b"x")
    results = model_scanner.scan_directory(root)
    assert results == []
    assert not any("outside" in entry.get("absolute_path", "") for entry in results)


def test_scanner_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    real_secret = outside / "secret.gguf"
    real_secret.write_bytes(b"y")
    (root / "link.gguf").symlink_to(real_secret)
    results = model_scanner.scan_directory(root)
    assert results == []


def test_scanner_rejects_traversal_style_input(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "evil.gguf").write_bytes(b"z")
    traversal_root = root / ".." / "outside"
    # even if a caller mistakenly passes a traversal-shaped root, the
    # scanner still only returns files confined to that root's OWN
    # resolved location -- it is not tricked into scanning "models/"
    # itself as if it were "outside/"
    results = model_scanner.scan_directory(traversal_root)
    for entry in results:
        assert Path(entry["absolute_path"]).is_relative_to(outside.resolve())


def test_scanner_accepts_genuinely_confined_real_file(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    (root / "model.gguf").write_bytes(b"real")
    results = model_scanner.scan_directory(root)
    assert len(results) == 1
    assert Path(results[0]["absolute_path"]).is_relative_to(root.resolve())


# -- no plaintext secret leaks anywhere in a real service response ------------------------------


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    allowed = tmp_path / "models"
    allowed.mkdir()
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", allowed_model_dir=allowed,
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


def test_no_plaintext_api_key_in_any_service_response(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, Fernet.generate_key().decode("ascii"))
    service = LocalSetupService(settings)
    fake_key = "sk-safety-test-plaintext-should-never-leak-999"

    saved = service.save_external_provider_configuration(
        provider_key="anthropic", api_key=fake_key, model="claude-3-5-haiku-latest", enabled=True, admin_id="admin-1",
    )
    assert fake_key not in str(saved)

    diagnostics = service.diagnostics()
    assert fake_key not in str(diagnostics)

    catalog = service.provider_catalog()
    assert fake_key not in str(catalog)

    guide = service.build_setup_guide()
    assert fake_key not in str(guide)


def test_diagnostics_masks_configured_model_path(settings: Settings) -> None:
    model_file = settings.resolved_allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"x")
    service = LocalSetupService(settings)
    service.save_local_model_configuration(
        model_path=str(model_file), context_length=2048, max_tokens=512, temperature=0.3, threads=4, admin_id="admin-1",
    )
    diagnostics = service.diagnostics()
    assert diagnostics["configured_model_path"] == "model.gguf"
    assert str(model_file) not in str(diagnostics)
    assert str(settings.resolved_allowed_model_dir) not in str(diagnostics)


def test_save_local_model_rejects_path_outside_allowed_dir(settings: Settings, tmp_path: Path) -> None:
    outside_file = tmp_path / "outside.gguf"
    outside_file.write_bytes(b"x")
    service = LocalSetupService(settings)
    with pytest.raises(Exception):
        service.save_local_model_configuration(
            model_path=str(outside_file), context_length=2048, max_tokens=512, temperature=0.3, threads=4, admin_id="admin-1",
        )
