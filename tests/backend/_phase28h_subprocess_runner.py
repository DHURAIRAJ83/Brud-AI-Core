"""Phase 2.8H: tiny standalone subprocess helper for proving the
production-database guard (`backend.database.qualification_guard`)
works from a genuinely separate OS process -- not merely importable
inside the parent pytest process. Every mode prints one JSON line and
exits 0 on success / 1 on a caught `ProductionDatabaseGuardError` (the
caller distinguishes the two via the process return code, exactly like
every prior phase's `_phase28*_subprocess_runner.py`)."""

from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)


def check_database_path(database_path: str) -> None:
    from backend.database.qualification_guard import (
        ProductionDatabaseGuardError,
        assert_database_path_is_not_production,
    )

    try:
        assert_database_path_is_not_production(database_path, context="subprocess check_database_path")
    except ProductionDatabaseGuardError as exc:
        print(json.dumps({"allowed": False, "error": str(exc)}))
        sys.exit(1)
    print(json.dumps({"allowed": True}))
    sys.exit(0)


def isolated_setup(tmp_dir: str) -> None:
    """Mirrors what every real Phase 2.8A-2.8G subprocess runner does at
    startup: build an isolated `Settings`, then explicitly assert it is
    safe before initializing the database -- proving the guard composes
    cleanly with the established qualification pattern."""

    from pathlib import Path

    from backend.core.config import Settings
    from backend.database.migrations import initialize_database
    from backend.database.qualification_guard import assert_database_path_is_not_production

    tmp = Path(tmp_dir)
    settings = Settings(
        database_path=tmp / "api.db", database_backup_dir=tmp / "backups", allowed_data_dir=tmp,
        document_dir=tmp / "documents", document_report_dir=tmp / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    assert_database_path_is_not_production(settings.resolved_database_path, context="isolated_setup")
    initialize_database(settings.resolved_database_path)
    print(json.dumps({"allowed": True, "database_path": str(settings.resolved_database_path)}))
    sys.exit(0)


if __name__ == "__main__":
    mode = sys.argv[1]
    args = sys.argv[2:]
    if mode == "check_database_path":
        check_database_path(*args)
    elif mode == "isolated_setup":
        isolated_setup(*args)
    else:
        raise SystemExit(f"unknown mode: {mode}")
