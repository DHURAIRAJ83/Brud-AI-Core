"""Phase 2.8P: Settings Failure-Path Production Write Elimination.

Phase 2.8O independently reproduced a real production database mutation:
an invalid `Settings()` configuration (a `BRUD_*` environment variable
combination that fails one of `Settings`' own field/model validators)
caused `get_settings()`'s own pre-existing exception handler to open a
raw, writable `sqlite3.connect()` against the hardcoded literal
production database path and insert a real `audit_logs` row --
completely unreachable by `backend.database.qualification_guard`,
because the write happens *while constructing* the very `Settings`
object every guard check requires as its own input.

Phase 2.8P removed that write entirely, replacing it with the same
`logging` mechanism the rest of this application already uses (now
enriched with per-field error detail), and this file proves the removal
directly: not merely that the production file is unchanged afterward
(weaker evidence), but that `sqlite3.connect()` is never even invoked
with the production path during the failure handler's own execution.

Every test in this file either uses `Settings()` directly (no caching,
safe to construct repeatedly), or clears `get_settings`'s `@lru_cache`
via `get_settings.cache_clear()` before/after touching it, to avoid
leaking a cached (valid or invalid) Settings instance across tests in
the same pytest process. No test in this file leaves the process-wide
`get_settings` cache in a state that could affect an unrelated test
file run afterward in the same session.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.config import PROJECT_ROOT, Settings, get_settings
from backend.database.qualification_guard import (
    canonical_production_database_path,
    canonical_production_pretraining_dir,
    is_production_pretraining_dir,
    qualification_session,
    run_qualification_preflight,
)

PRODUCTION_DB_PATH = PROJECT_ROOT / "data" / "database" / "brud_ai.db"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """`get_settings()` is a zero-argument `@lru_cache`d function -- once
    it succeeds in a process, every later call returns the same cached
    instance regardless of subsequent environment changes. Clearing the
    cache before and after every test in this file keeps each test's own
    environment manipulation from leaking into the next test, or into
    unrelated test files run later in the same pytest session."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _production_db_fingerprint() -> tuple[int, str, int]:
    """(size, sha256, audit_logs count) -- read-only.

    Deliberately does NOT go through `capture_production_database_snapshot()`
    / `canonical_production_database_path()`, both of which call
    `get_settings()` internally: several tests in this file call this
    helper while an intentionally-invalid environment is active (via
    `monkeypatch`), specifically to prove no production write occurs
    during the failure. Routing through `get_settings()` here would
    either (a) populate its `@lru_cache` with a valid result before the
    bad env var is applied, masking the very failure being tested, or
    (b) raise itself once the bad env var *is* active, when this helper
    is called a second time as the test's own "after" measurement. Using
    the fixed, hardcoded `PRODUCTION_DB_PATH` constant directly (already
    used for the same purpose elsewhere in this file) avoids both."""

    stat = PRODUCTION_DB_PATH.stat()
    digest = hashlib.sha256()
    with open(PRODUCTION_DB_PATH, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    con = sqlite3.connect(f"file:{PRODUCTION_DB_PATH}?mode=ro", uri=True)
    try:
        audit_count = con.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    finally:
        con.close()
    return stat.st_size, digest.hexdigest(), audit_count


# -- 1. Invalid Settings construction never writes production ----------------

class TestInvalidConfigurationNeverWritesProduction:
    def test_invalid_settings_raises_and_production_is_untouched(self, tmp_path: Path) -> None:
        before = _production_db_fingerprint()

        with pytest.raises(ValidationError):
            Settings(allowed_data_dir=tmp_path / "outside_but_flagged_external", allow_external_storage=False,
                     database_path=tmp_path / "db.sqlite")
            # allowed_data_dir defaults are inside the project; force an
            # out-of-project value explicitly to trigger the same
            # model_validator Phase 2.8O's own incident hit.

        after = _production_db_fingerprint()
        assert after == before, "an invalid Settings() construction must never touch the production database"

    def test_exact_phase_28o_trigger_via_get_settings_writes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The precise scenario Phase 2.8O reproduced: an invalid
        `BRUD_ALLOWED_DATA_DIR` (external, `allow_external_storage`
        left at its default False), reached through `get_settings()`
        itself (not raw `Settings()`), exactly matching how the
        original incident was triggered
        (`canonical_production_pretraining_dir()` -> `get_settings()`)."""

        before = _production_db_fingerprint()
        # Defensive: ensure no earlier test in this process left a valid
        # `get_settings()` result cached, so the env var below is
        # guaranteed to force a fresh, failing evaluation (the autouse
        # `_clear_settings_cache` fixture already does this too; this is
        # belt-and-suspenders since this specific test is the direct
        # Phase 2.8O reproduction).
        get_settings.cache_clear()

        monkeypatch.setenv("BRUD_ALLOWED_DATA_DIR", "/some/external/path/not/in/project")
        with pytest.raises(ValidationError):
            get_settings()

        after = _production_db_fingerprint()
        assert after == before, "the exact Phase 2.8O trigger must no longer write to production"


# -- 2. No raw production sqlite3.connect() is ever invoked -------------------

class TestNoRawProductionConnectionAttempt:
    def test_sqlite3_connect_is_never_called_with_the_production_path(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Stronger than an unchanged-file check: instruments the real
        `sqlite3.connect` to record every path it is called with,
        without altering its actual behavior (each call still delegates
        to the real function) -- proving the unsafe call site is
        unreachable, not merely that its effects happened to cancel out."""

        calls: list[str] = []
        real_connect = sqlite3.connect

        def recording_connect(database, *args, **kwargs):
            calls.append(str(database))
            return real_connect(database, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", recording_connect)
        monkeypatch.setenv("BRUD_ALLOWED_DATA_DIR", "/some/external/path/not/in/project")

        with pytest.raises(ValidationError):
            get_settings()

        production_path_str = str(PRODUCTION_DB_PATH)
        offending = [c for c in calls if production_path_str in c or "brud_ai.db" in c]
        assert offending == [], f"sqlite3.connect() was called against the production path: {offending}"


# -- 3. Valid configuration behavior is unaffected -----------------------------

class TestValidConfigurationRegression:
    def test_valid_settings_construction_still_succeeds(self, tmp_path: Path) -> None:
        settings = Settings(
            database_path=tmp_path / "db.sqlite", allowed_data_dir=tmp_path / "data",
            pretraining_dir=tmp_path / "pretraining", allow_external_storage=True,
        )
        assert settings.resolved_database_path == (tmp_path / "db.sqlite").resolve()

    def test_get_settings_still_resolves_the_real_production_configuration(self) -> None:
        settings = get_settings()
        assert settings.resolved_database_path == canonical_production_database_path()

    def test_get_settings_caching_behavior_is_unchanged(self) -> None:
        first = get_settings()
        second = get_settings()
        assert first is second


# -- 4. Environment override regression (valid + invalid) ---------------------

class TestEnvironmentOverrideRegression:
    def test_valid_in_project_pretraining_dir_override_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRUD_PRETRAINING_DIR", "data/phase28p_alt_pretraining_probe")
        settings = get_settings()
        assert settings.resolved_pretraining_dir == (PROJECT_ROOT / "data" / "phase28p_alt_pretraining_probe").resolve()
        # The guard must correctly follow the override as the new "production" value.
        assert canonical_production_pretraining_dir() == settings.resolved_pretraining_dir
        assert is_production_pretraining_dir(settings.resolved_pretraining_dir) is True

    def test_invalid_external_pretraining_dir_override_fails_cleanly_with_no_production_write(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        before = _production_db_fingerprint()
        # Defensive, same reasoning as the analogous test above.
        get_settings.cache_clear()
        monkeypatch.setenv("BRUD_PRETRAINING_DIR", "/some/external/path/not/in/project")
        with pytest.raises(ValidationError):
            get_settings()
        after = _production_db_fingerprint()
        assert after == before


# -- 5. Diagnostic preservation -------------------------------------------------

class TestDiagnosticsArePreserved:
    def test_invalid_configuration_still_logs_a_useful_diagnostic(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        monkeypatch.setenv("BRUD_ALLOWED_DATA_DIR", "/some/external/path/not/in/project")
        with caplog.at_level(logging.ERROR, logger="backend.core.config"):
            with pytest.raises(ValidationError):
                get_settings()

        records = [r for r in caplog.records if r.message == "configuration_validation_failure"]
        assert len(records) == 1
        assert records[0].error_count >= 1
        assert records[0].errors  # field-level detail is present, not just a bare count


# -- 6. Qualification guard still works after the hardening -------------------

class TestQualificationGuardStillWorksAfterHardening:
    def test_preflight_and_session_still_function_normally(self, tmp_path: Path) -> None:
        settings = Settings(
            database_path=tmp_path / "db.sqlite", allowed_data_dir=tmp_path / "data",
            pretraining_dir=tmp_path / "pretraining", allow_external_storage=True,
        )
        result = run_qualification_preflight(settings)
        assert result.safe_to_proceed is True
        with qualification_session(settings) as session:
            assert session.zero_mutation_baseline_claimable is True


# -- 7. No production checkpoint path is created -------------------------------

class TestNoProductionCheckpointPathCreated:
    def test_production_pretraining_dir_does_not_exist_or_was_not_created_by_this_suite(self) -> None:
        prod_pretraining_dir = PROJECT_ROOT / "data" / "core_models" / "pretraining"
        # This suite never constructs a Settings object that resolves to
        # the real production pretraining_dir for writable use -- if it
        # exists at all, this suite did not create it.
        if prod_pretraining_dir.exists():
            pytest.skip(
                "production pretraining_dir already exists from state outside this test suite; "
                "this test only asserts this suite itself never creates it"
            )
        assert not prod_pretraining_dir.exists()
