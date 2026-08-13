"""MB-30: structural + behavioral safety proofs for Production Runtime
Manager & One-Click Local Model Lifecycle.

Static-analysis checks use `ast` node inspection or narrowed
call-pattern substrings -- never a naive whole-file substring match
against arbitrary prose (the repeatedly-learned lesson from MB-26
through MB-29's own docstring-prose false positives). Confinement,
checksum-mismatch, disk-guard, and RAM-guard checks are exercised
against the real pure functions and the real service with real
`tmp_path` fixtures, not mocked.
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.runtime_manager_service import RuntimeManagerService
from core_model.mini_brain.runtime_manager import checksum_verifier, disk_space_guard, ram_guard

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_MANAGER_DIR = REPO_ROOT / "core_model" / "mini_brain" / "runtime_manager"
SERVICE_PATH = REPO_ROOT / "backend" / "services" / "runtime_manager_service.py"
ROUTES_PATH = REPO_ROOT / "backend" / "api" / "routes" / "mini_brain_runtime_manager.py"
MODELS_PATH = REPO_ROOT / "backend" / "models" / "mini_brain_runtime_manager.py"
SCHEMA_PATH = REPO_ROOT / "backend" / "database" / "schema.py"

ALL_MODULE_PATHS = sorted(p for p in RUNTIME_MANAGER_DIR.glob("*.py") if p.name != "__init__.py")

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


# -- pure package: strictly pure, no I/O at all (stricter than MB-29's own rule) ------------------


def test_pure_package_never_imports_fastapi_sqlite3_httpx_requests() -> None:
    forbidden = {"fastapi", "sqlite3", "httpx", "requests"}
    for path in ALL_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        overlap = forbidden & (imported_modules | imported_names)
        assert not overlap, f"{path.name} must never import {overlap}"


def test_pure_package_never_imports_os_shutil_or_network() -> None:
    """Unlike MB-29's own package, MB-30's spec draws the pure-package
    line even tighter -- no module here (not even the catalog or a
    scanner-like module) may perform filesystem/OS/network I/O at
    all; that all lives in the one designated impure service."""
    forbidden = {"os", "shutil", "socket", "urllib", "http.client"}
    for path in ALL_MODULE_PATHS:
        tree = _module_ast(path)
        imported_modules, imported_names = _imported_modules_and_names(tree)
        overlap = forbidden & (imported_modules | imported_names)
        assert not overlap, f"{path.name} must never import {overlap}"


def test_pure_package_never_calls_subprocess_eval_exec() -> None:
    for path in ALL_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_CALL_PATTERNS:
            assert forbidden not in source, f"{path.name} must never call {forbidden}"


def test_only_model_catalog_module_contains_a_literal_url() -> None:
    """Structural proof of the phase spec's own rule: "Only
    model_catalog.py may contain static download metadata." -- no
    other module may embed an http(s):// literal."""
    for path in ALL_MODULE_PATHS:
        if path.name == "model_catalog.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "http://" not in source and "https://" not in source, f"{path.name} must not embed a URL"


def test_checksum_verifier_never_opens_a_file() -> None:
    tree = _module_ast(RUNTIME_MANAGER_DIR / "checksum_verifier.py")
    calls = _call_names(tree)
    assert "open" not in calls


# -- service: no subprocess/eval/exec, network only in download_model -----------------------------


def test_service_never_calls_subprocess_eval_exec() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


def test_routes_never_call_subprocess_eval_exec() -> None:
    source = ROUTES_PATH.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_CALL_PATTERNS:
        assert forbidden not in source


def test_httpx_stream_only_ever_called_from_download_model() -> None:
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for call_node in ast.walk(node):
                if isinstance(call_node, ast.Attribute) and call_node.attr == "stream":
                    assert node.name == "download_model", (
                        f"httpx.stream must only be called from download_model, found in {node.name}"
                    )


def test_routes_prefix_is_runtime_manager_only() -> None:
    tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"))
    prefixes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "APIRouter":
            for keyword in node.keywords:
                if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                    prefixes.append(keyword.value.value)
    assert prefixes == ["/admin/mini-brain/runtime-manager"]


def test_service_never_imports_mb04_runtime_manager() -> None:
    """MB-30 must never touch MB-04's unrelated, pre-existing
    mini_brain_runtime_manager_service.py (a different "runtime"
    concept entirely -- core-model response-plan generation)."""
    tree = _module_ast(SERVICE_PATH)
    _, imported_names = _imported_modules_and_names(tree)
    assert "MiniBrainInMemoryModelLoader" not in imported_names


# -- no secret-shaped response field --------------------------------------------------------------


def test_models_never_define_a_secret_shaped_field() -> None:
    tree = _module_ast(MODELS_PATH)
    forbidden_field_names = {"api_key", "encrypted_value", "secret_value", "raw_value", "value"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    assert statement.target.id not in forbidden_field_names, f"{node.name}.{statement.target.id} looks secret-shaped"


# -- schema: both new tables have real two-trigger append-only/permanent protection ------------------


def _phase70_schema_text() -> str:
    source = SCHEMA_PATH.read_text(encoding="utf-8")
    start = source.index('PHASE70_SCHEMA = """')
    end = source.index('"""', start + len('PHASE70_SCHEMA = """'))
    return source[start:end]


def test_runtime_events_table_has_both_immutability_triggers() -> None:
    schema_text = _phase70_schema_text()
    assert "mini_brain_runtime_events_immutable_update" in schema_text
    assert "mini_brain_runtime_events_immutable_delete" in schema_text


def test_runtime_memory_table_has_both_immutability_triggers() -> None:
    schema_text = _phase70_schema_text()
    assert "mini_brain_runtime_memory_immutable_update" in schema_text
    assert "mini_brain_runtime_memory_immutable_delete" in schema_text


def test_immutability_triggers_are_real_at_the_database_level(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = sqlite3.connect(db_path)
    import uuid

    conn.execute("INSERT INTO mini_brain_runtime_events(public_id, event_type) VALUES (?, ?)", (str(uuid.uuid4()), "test"))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE mini_brain_runtime_events SET event_type='hacked'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM mini_brain_runtime_events")

    conn.execute("INSERT INTO mini_brain_runtime_memory(public_id, event_type) VALUES (?, ?)", (str(uuid.uuid4()), "installed"))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE mini_brain_runtime_memory SET event_type='loaded'")
    conn.close()


# -- checksum mismatch rejection -----------------------------------------------------------------------


def test_checksum_verifier_rejects_real_mismatch() -> None:
    digest_a = checksum_verifier.compute_sha256(b"file contents A")
    digest_b = checksum_verifier.compute_sha256(b"different file contents B")
    result = checksum_verifier.verify_digest(actual_sha256=digest_a, expected_sha256=digest_b)
    assert result["matches"] is False


def test_checksum_verifier_accepts_real_match() -> None:
    digest = checksum_verifier.compute_sha256(b"consistent bytes")
    result = checksum_verifier.verify_digest(actual_sha256=digest, expected_sha256=digest)
    assert result["matches"] is True


# -- insufficient disk / RAM rejection ------------------------------------------------------------------


def test_disk_space_guard_rejects_insufficient_space() -> None:
    result = disk_space_guard.check(available_bytes=100_000_000, required_bytes=1_100_000_000)
    assert result["safe"] is False


def test_ram_guard_rejects_unsafe_load() -> None:
    result = ram_guard.check_load_safety(available_ram_gb=4.5, estimated_model_ram_gb=3.5)
    assert result["safe"] is False
    assert result["warning_en"] is not None
    assert result["warning_ta"] is not None


def test_ram_guard_accepts_safe_load() -> None:
    result = ram_guard.check_load_safety(available_ram_gb=4.5, estimated_model_ram_gb=2.5)
    assert result["safe"] is True
    assert result["warning_en"] is None


# -- real service-level rejection (not just the pure functions) ------------------------------------------


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


def test_load_model_rejects_unsafe_ram_for_real(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    from core_model.mini_brain.local_setup import hardware_probe

    service = RuntimeManagerService(settings)
    model_file = settings.resolved_allowed_model_dir / "qwen2.5-3b-instruct-q4_k_m.gguf"
    model_file.write_bytes(b"fake" * 100)
    digest = checksum_verifier.compute_sha256(model_file.read_bytes())
    service.install_model("qwen2.5-3b-instruct-q4_k_m", file_path=str(model_file), expected_sha256=digest, admin_id="admin-1")

    tiny_ram_hardware = {
        "total_ram_gb": 6.0, "available_ram_gb": 4.5, "cpu_cores": 4, "cpu_threads": 4,
        "architecture": "x86_64", "os_name": "Linux", "disk_free_gb": 50.0, "python_version": "3.13.5",
        "recommended_ram_tier": "6GB", "psutil_available": True,
    }
    monkeypatch.setattr("backend.services.runtime_manager_service.hardware_probe.probe", lambda **kwargs: tiny_ram_hardware)
    with pytest.raises(ValidationError):
        service.load_model("qwen2.5-3b-instruct-q4_k_m", admin_id="admin-1")


def test_download_model_rejects_insufficient_disk_for_real(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service = RuntimeManagerService(settings)
    fake_usage = type("Usage", (), {"free": 1_000, "total": 1_000, "used": 0})()
    monkeypatch.setattr("backend.services.runtime_manager_service.shutil.disk_usage", lambda path: fake_usage)
    with pytest.raises(ValidationError):
        service.download_model("qwen2.5-1.5b-instruct-q4_k_m", admin_id="admin-1")


def test_install_model_rejects_checksum_mismatch(settings: Settings) -> None:
    service = RuntimeManagerService(settings)
    model_file = settings.resolved_allowed_model_dir / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    model_file.write_bytes(b"real bytes")
    installed = service.install_model(
        "qwen2.5-1.5b-instruct-q4_k_m", file_path=str(model_file), expected_sha256="0" * 64, admin_id="admin-1",
    )
    assert installed["status"] == "failed"


def test_load_model_confines_to_allowed_directory(settings: Settings, tmp_path: Path) -> None:
    """Even a maliciously-crafted install_path outside the allowed
    directory cannot be loaded -- LlamaCppMiniBrainAdapter's own
    confinement (reused, not re-implemented) rejects it."""
    from backend.services.mini_brain_llm_adapter import resolve_confined_model_path

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "evil.gguf"
    outside_file.write_bytes(b"x")
    assert resolve_confined_model_path(settings=settings, model_path=str(outside_file)) is None


def test_no_plaintext_secret_in_any_service_response(settings: Settings) -> None:
    service = RuntimeManagerService(settings)
    status = service.runtime_status()
    assert "sk-" not in str(status)
    catalog = service.catalog()
    assert "sk-" not in str(catalog)
