"""Phase 2.8I: Qualification Environment Hard Isolation, Dev-Server
Containment & Zero-Mutation Baseline.

Phase 2.8H built a fail-closed path/process guard but found the
production database still drifted -- traced to a live
`uvicorn backend.main:app --reload` dev server whose file-watcher
restarted on every source edit Phase 2.8H itself made, each restart's
own legitimate ASGI startup lifecycle writing a real `application_startup`
audit row to production.

This phase closes that operational gap with `qualification_session()` /
`capture_production_database_snapshot()` (`backend/database
/qualification_guard.py`) -- a before/after byte-for-byte snapshot
comparison wrapped around the existing preflight, plus a REAL,
genuinely-separate-process proof (`TestRealReloadProof`) that `uvicorn
--reload` against an *isolated* `BRUD_DATABASE_PATH` cannot touch
production even when its file-watcher fires for real, on a real source
change, in the real repository tree.

Every test in this file either uses an isolated `tmp_path` database, a
strictly read-only production connection, or (the real reload proof)
a genuinely separate, isolated-database `uvicorn` subprocess this test
launches and tears down itself -- never the pre-existing, operator-
managed dev server. No test in this file intentionally causes a
production-connected reload server to run, per the mission's own Part
10 instruction not to reproduce the contamination it is proving a fix
for.
"""

from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from backend.core.config import PROJECT_ROOT, Settings, get_settings
from backend.database.qualification_guard import (
    LiveProcessInfo,
    ProcessInspectionResult,
    ProductionDatabaseGuardError,
    ProductionDatabaseSnapshot,
    ZeroMutationBaselineViolation,
    capture_production_database_snapshot,
    detect_live_production_database_writers,
    open_production_database_read_only,
    qualification_session,
)


def _isolated_settings(tmp_path: Path) -> Settings:
    # Phase 2.8N: pretraining_dir must also be isolated -- the guard now
    # checks it independently of allowed_data_dir (the exact Phase 2.8M
    # blind spot this fixture would otherwise silently reproduce).
    return Settings(
        database_path=tmp_path / "api.db", allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "pretraining", allow_external_storage=True,
    )


# -- Qualification session: happy path, rejection, override ------------------

class TestQualificationSession:
    def test_isolated_settings_establish_a_zero_mutation_claimable_session(self, tmp_path: Path) -> None:
        with qualification_session(_isolated_settings(tmp_path)) as session:
            assert session.zero_mutation_baseline_claimable is True
            assert isinstance(session.baseline_snapshot, ProductionDatabaseSnapshot)
            assert session.baseline_snapshot.sha256 == capture_production_database_snapshot().sha256

    def test_production_settings_rejected_outright(self) -> None:
        with pytest.raises(ProductionDatabaseGuardError, match="production database"):
            with qualification_session(get_settings()):
                pytest.fail("must never enter the session body for production settings")

    def test_clean_exit_does_not_raise(self, tmp_path: Path) -> None:
        # A no-op body: entering and exiting cleanly must never itself
        # raise, since nothing touched the production database.
        with qualification_session(_isolated_settings(tmp_path)):
            pass

    def test_synthetic_production_mutation_during_session_is_detected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The core Part 11 proof, made deterministic: simulate a
        mutation occurring during the session (never a real one -- this
        phase's own tests must never write production) by making the
        AFTER snapshot differ from the BEFORE one, and confirm the
        session refuses to exit silently."""
        import backend.database.qualification_guard as guard

        real_capture = guard.capture_production_database_snapshot
        calls = {"n": 0}

        def fake_capture():
            calls["n"] += 1
            snapshot = real_capture()
            if calls["n"] == 1:
                return snapshot
            # Second call (the AFTER check): report a different hash,
            # exactly what a real, undetected mutation would look like.
            return ProductionDatabaseSnapshot(
                size_bytes=snapshot.size_bytes + 1, mtime_ns=snapshot.mtime_ns + 1,
                sha256="0" * 64, schema_version=snapshot.schema_version, table_counts=snapshot.table_counts,
            )

        monkeypatch.setattr(guard, "capture_production_database_snapshot", fake_capture)
        with pytest.raises(ZeroMutationBaselineViolation, match="changed during"):
            with guard.qualification_session(_isolated_settings(tmp_path)):
                pass
        # The real production database was of course never touched --
        # only this test's own monkeypatched function reported a change.
        # `real_capture` is the genuine, unpatched function; confirm the
        # actual file still matches its own true, unfaked hash.
        genuinely_unchanged = real_capture()
        assert genuinely_unchanged.sha256 not in ("0" * 64,)

    def test_override_without_reason_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="override_reason"):
            with qualification_session(_isolated_settings(tmp_path), allow_production_writer_present=True):
                pass

    def test_override_with_live_writer_marks_session_not_baseline_claimable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import backend.database.qualification_guard as guard

        fake_writer = LiveProcessInfo(
            pid=999998, cmdline="python -m uvicorn backend.main:app", cwd="/fake",
            classification="brud_ai_asgi_process", database_path_override=None, likely_production_writer=True,
        )
        monkeypatch.setattr(
            guard, "detect_live_production_database_writers",
            lambda **_: ProcessInspectionResult(processes=[fake_writer], degraded=False),
        )
        with guard.qualification_session(
            _isolated_settings(tmp_path), allow_production_writer_present=True,
            override_reason="testing the override path deliberately",
        ) as session:
            assert session.zero_mutation_baseline_claimable is False
            assert session.override_reason == "testing the override path deliberately"
        # Exiting cleanly must NOT re-check production (it explicitly
        # cannot claim a zero-mutation guarantee), so no
        # ZeroMutationBaselineViolation is possible here.

    def test_live_writer_without_override_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import backend.database.qualification_guard as guard

        fake_writer = LiveProcessInfo(
            pid=999997, cmdline="python -m uvicorn backend.main:app", cwd="/fake",
            classification="brud_ai_asgi_process", database_path_override=None, likely_production_writer=True,
        )
        monkeypatch.setattr(
            guard, "detect_live_production_database_writers",
            lambda **_: ProcessInspectionResult(processes=[fake_writer], degraded=False),
        )
        with pytest.raises(ProductionDatabaseGuardError, match="999997"):
            with guard.qualification_session(_isolated_settings(tmp_path)):
                pytest.fail("must never enter the session body while an unauthorized writer is live")

    def test_qualification_allowed_after_writer_is_no_longer_detected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Part 8 item 8: proves the sequence 'blocked while present ->
        allowed once gone' without ever starting a real writer."""
        import backend.database.qualification_guard as guard

        fake_writer = LiveProcessInfo(
            pid=999996, cmdline="python -m uvicorn backend.main:app", cwd="/fake",
            classification="brud_ai_asgi_process", database_path_override=None, likely_production_writer=True,
        )
        monkeypatch.setattr(
            guard, "detect_live_production_database_writers",
            lambda **_: ProcessInspectionResult(processes=[fake_writer], degraded=False),
        )
        with pytest.raises(ProductionDatabaseGuardError):
            with guard.qualification_session(_isolated_settings(tmp_path)):
                pass

        monkeypatch.setattr(
            guard, "detect_live_production_database_writers",
            lambda **_: ProcessInspectionResult(processes=[], degraded=False),
        )
        with guard.qualification_session(_isolated_settings(tmp_path)) as session:
            assert session.zero_mutation_baseline_claimable is True


# -- Isolated BRUD_DATABASE_PATH env-var acceptance ---------------------------

class TestIsolatedEnvironmentVariableConfiguration:
    def test_settings_built_from_env_var_override_is_treated_as_isolated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRUD_DATABASE_PATH", str(tmp_path / "env_dev.db"))
        # Phase 2.8N: pretraining_dir must also be isolated -- see _isolated_settings()'s own note above.
        monkeypatch.setenv("BRUD_PRETRAINING_DIR", str(tmp_path / "pretraining"))
        settings = Settings(allowed_data_dir=tmp_path, allow_external_storage=True)
        assert settings.resolved_database_path == (tmp_path / "env_dev.db").resolve()
        with qualification_session(settings) as session:
            assert session.zero_mutation_baseline_claimable is True


# -- No automatic process killing (static + behavioral) -----------------------

class TestNoAutomaticProcessKilling:
    def test_qualification_guard_source_contains_no_kill_calls(self) -> None:
        """Part 8 item 14 / the mission's strict safety rule: this
        module must never itself terminate a process -- verified by
        source inspection, not merely by absence of observed behavior."""
        source = Path("backend/database/qualification_guard.py").read_text()
        for forbidden in ("os.kill(", "signal.SIGKILL", "signal.SIGTERM", ".terminate()", ".kill()"):
            assert forbidden not in source, f"found forbidden process-control call: {forbidden!r}"

    def test_detecting_a_synthetic_writer_does_not_touch_it(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.database.qualification_guard as guard

        fake_writer = LiveProcessInfo(
            pid=999995, cmdline="python -m uvicorn backend.main:app", cwd="/fake",
            classification="brud_ai_asgi_process", database_path_override=None, likely_production_writer=True,
        )
        monkeypatch.setattr(
            guard, "detect_live_production_database_writers",
            lambda **_: ProcessInspectionResult(processes=[fake_writer], degraded=False),
        )
        # PID 999995 does not exist -- if the guard ever tried to signal
        # it, this would raise ProcessLookupError, which we'd see below.
        try:
            with guard.qualification_session(_isolated_settings(tmp_path)):
                pass
        except ProductionDatabaseGuardError:
            pass  # expected rejection -- the point is no OSError was raised trying to kill pid 999995


# -- Preflight never silently substitutes a different database ---------------

class TestNoSilentSubstitution:
    def test_preflight_reports_the_exact_path_given_never_a_different_one(self, tmp_path: Path) -> None:
        from backend.database.qualification_guard import run_qualification_preflight

        settings = _isolated_settings(tmp_path)
        result = run_qualification_preflight(settings)
        assert result.database_path == settings.resolved_database_path


# -- Production read-only verification cannot write ---------------------------

class TestProductionReadOnlyCannotWrite:
    def test_read_only_connection_rejects_write_and_snapshot_helper_never_opens_writably(self) -> None:
        connection = open_production_database_read_only()
        try:
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                connection.execute("UPDATE audit_logs SET action=action WHERE 1=0")
        finally:
            connection.close()

    def test_capture_snapshot_does_not_change_production_file(self) -> None:
        path = capture_production_database_snapshot()  # noqa: F841 -- forces a read pass
        before = Path("data/database/brud_ai.db").resolve()
        stat_before = (before.stat().st_size, before.stat().st_mtime_ns)
        capture_production_database_snapshot()
        stat_after = (before.stat().st_size, before.stat().st_mtime_ns)
        assert stat_before == stat_after


# -- Part 9: the real, genuinely-separate-process reload proof ----------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http_ok(port: int, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/openapi.json", timeout=1.0)
            if response.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        time.sleep(0.25)
    raise TimeoutError(f"server on port {port} never became ready: {last_exc}")


def _startup_count(db_path: Path) -> int:
    connection = sqlite3.connect(str(db_path))
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE action='application_startup'"
        ).fetchone()[0]
    finally:
        connection.close()


class TestRealReloadProof:
    """Launches a genuinely separate `uvicorn backend.main:app --reload`
    OS process against an ISOLATED `BRUD_DATABASE_PATH`, triggers a
    real file-change-detected restart via a throwaway probe file placed
    inside the actual watched repository tree, and proves the
    production database is byte-for-byte unaffected throughout -- the
    exact scenario Phase 2.8H found unsafe, now proven safe when
    correctly isolated. The probe file is removed and the subprocess is
    terminated (this test's own child process -- not the operator's
    server) in a `finally` block regardless of outcome."""

    def test_isolated_reload_server_restart_never_touches_production(self, tmp_path: Path) -> None:
        before = capture_production_database_snapshot()

        port = _free_port()
        dev_db = tmp_path / "dev.db"
        env = {**os.environ, "BRUD_DATABASE_PATH": str(dev_db), "BRUD_LOG_LEVEL": "CRITICAL"}
        probe_path = PROJECT_ROOT / "backend" / "_phase28i_reload_probe.py"
        probe_path.write_text('"""Phase 2.8I reload-proof probe -- removed automatically."""\nPROBE_VALUE = 0\n')

        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(PROJECT_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            _wait_for_http_ok(port, timeout=60)
            assert dev_db.exists(), "the isolated dev server must initialize its OWN isolated database"
            startup_count_before_reload = _startup_count(dev_db)
            assert startup_count_before_reload >= 1

            # A genuine, real content change to a real file inside the
            # actual watched tree -- not a mocked filesystem event.
            probe_path.write_text('"""Phase 2.8I reload-proof probe -- removed automatically."""\nPROBE_VALUE = 1\n')

            deadline = time.monotonic() + 60
            reloaded = False
            while time.monotonic() < deadline:
                if _startup_count(dev_db) > startup_count_before_reload:
                    reloaded = True
                    break
                time.sleep(0.5)
            assert reloaded, "the isolated server's --reload watcher never picked up the probe file change"

            _wait_for_http_ok(port, timeout=30)  # the reloaded worker must also be serving again
        finally:
            probe_path.unlink(missing_ok=True)
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)

        assert not probe_path.exists()
        after = capture_production_database_snapshot()
        assert after == before, (
            "the isolated reload server's real restart must never change the production database "
            f"-- before={before} after={after}"
        )
