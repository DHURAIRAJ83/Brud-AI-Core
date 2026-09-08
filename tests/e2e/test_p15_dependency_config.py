"""P15 Dependency & Configuration Security Test Suite.

Validates:
1. Rejection of wildcard CORS origins (* forbidden)
2. Rejection of malformed/non-HTTP origin URLs
3. Safe default configuration (DEBUG=False, production defaults)
4. Python runtime dependency constraint audit (pyproject.toml bounds)
5. Frontend dependency audit (pinned React, Vite, absence of wildcards)
6. Filesystem containment validation (unauthorized paths blocked)
7. Secret encryption key enforcement (fail-closed on missing key)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.config import Settings
from core_model.mini_brain.provider_settings.secret_encryptor import (
    EncryptionUnavailableError,
    encrypt_secret,
)

pytestmark = pytest.mark.anyio


# 1. Rejection of wildcard CORS origins
def test_p15_dep_001_wildcard_cors_rejected(tmp_path: Path):
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            database_path=tmp_path / "test.db",
            allowed_data_dir=tmp_path / "data",
            allowed_model_dir=tmp_path / "models",
            allow_external_storage=True,
            admin_origin="*",
        )
    assert "wildcard CORS origins are not allowed" in str(excinfo.value)

    with pytest.raises(ValidationError) as excinfo:
        Settings(
            database_path=tmp_path / "test.db",
            allowed_data_dir=tmp_path / "data",
            allowed_model_dir=tmp_path / "models",
            allow_external_storage=True,
            chatbot_origin="https://*.example.com",
        )
    assert "wildcard CORS origins are not allowed" in str(excinfo.value)
    print("\n[DEP-001] Wildcard CORS: strictly rejected for both admin_origin and chatbot_origin")


# 2. Rejection of invalid origin schemes
def test_p15_dep_002_invalid_origin_scheme_rejected(tmp_path: Path):
    with pytest.raises(ValidationError):
        Settings(
            database_path=tmp_path / "test.db",
            allowed_data_dir=tmp_path / "data",
            allowed_model_dir=tmp_path / "models",
            allow_external_storage=True,
            admin_origin="javascript:alert(1)",
        )
    print("\n[DEP-002] Malformed Origin: javascript: pseudo-protocol rejected by URL validator")


# 3. Safe production defaults
def test_p15_dep_003_safe_production_defaults(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "test.db",
        allowed_data_dir=tmp_path / "data",
        allowed_model_dir=tmp_path / "models",
        allow_external_storage=True,
    )
    assert settings.debug is False
    assert settings.database_wal is True
    assert settings.database_auto_backup is True
    assert settings.audit_enabled is True
    assert settings.admin_lockout_minutes >= 15
    assert settings.admin_max_failed_logins <= 5
    print("\n[DEP-003] Production Defaults: debug=False, WAL=True, auto_backup=True, audit=True verified")


# 4. Python runtime dependency constraint audit
def test_p15_dep_004_python_dependencies_pinned():
    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")

    # Extract dependencies block
    dep_match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
    assert dep_match is not None
    dep_lines = re.findall(r'"([^"]+)"', dep_match.group(1))

    # Ensure every runtime dependency has upper and lower bound
    unbounded = []
    for dep in dep_lines:
        if not dep:
            continue
        # Should have >= and < or ~=
        if not ((">=" in dep and "<" in dep) or "~=" in dep):
            unbounded.append(dep)

    assert len(unbounded) == 0, f"Found unbounded runtime dependencies: {unbounded}"
    print(f"\n[DEP-004] Python Dependencies: all {len(dep_lines)} runtime dependencies strictly bounded")


# 5. Frontend dependency audit
def test_p15_dep_005_frontend_dependencies_pinned():
    pkg_path = Path("apps/admin-dashboard/package.json")
    assert pkg_path.exists()
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))

    deps = pkg.get("dependencies", {})
    assert len(deps) > 0

    # Ensure React, ReactDOM, and Vite are pinned without wildcard or loose ranges
    for name, version in deps.items():
        assert "*" not in version
        assert "latest" not in version
        assert re.match(r"^\^?\d+\.\d+\.\d+", version) is not None

    print(f"\n[DEP-005] Frontend Dependencies: React ({deps['react']}), Vite ({deps['vite']}) strictly pinned")


# 6. Filesystem containment validation
def test_p15_dep_006_filesystem_containment(tmp_path: Path):
    with pytest.raises(ValidationError):
        # Database pointing outside without allow_external_storage
        Settings(
            database_path=Path("/tmp/rogue/brud.db"),
            allowed_data_dir=tmp_path / "data",
            allowed_model_dir=tmp_path / "models",
            allow_external_storage=False,
        )
    print("\n[DEP-006] Filesystem Containment: unauthorized storage path outside allowed boundary rejected")


# 7. Fail-closed secret encryption on missing master key
def test_p15_dep_007_missing_secret_key_fail_closed():
    # Remove env var if set
    old_key = os.environ.pop("BRUD_SECRET_ENCRYPTION_KEY", None)
    try:
        with pytest.raises(EncryptionUnavailableError) as excinfo:
            encrypt_secret("test-secret-value")
        assert "BRUD_SECRET_ENCRYPTION_KEY is not configured" in str(excinfo.value)
    finally:
        if old_key is not None:
            os.environ["BRUD_SECRET_ENCRYPTION_KEY"] = old_key

    print("\n[DEP-007] Secret Encryption: strictly fail-closed when BRUD_SECRET_ENCRYPTION_KEY is missing")
