"""Phase 2.8N: Qualification Checkpoint-Destination Hard Isolation.

Phase 2.8M found, by direct source inspection, that
`backend.database.qualification_guard`'s preflight/session verified
`Settings.database_path` and `Settings.allowed_data_dir` were isolated
from production but never independently verified
`Settings.pretraining_dir` -- the actual MB-22 checkpoint destination.
This phase reproduced that exact blind spot empirically (a `Settings`
object with an isolated database and data directory, but
`pretraining_dir` pointed at the real production checkpoint path,
was accepted by both `run_qualification_preflight()` and
`qualification_session()`) before writing any fix, then closed it with
`is_production_pretraining_dir()` / `assert_pretraining_dir_is_not_
production()`, wired into the same preflight/session surface the
database-path guard already used.

Every test in this file uses either a real isolated `tmp_path`, or a
read-only inspection of the real production checkpoint directory's
existence/emptiness (never opening it for writing). No test in this
file creates a real production checkpoint.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings, get_settings
from backend.database.qualification_guard import (
    ProductionDatabaseGuardError,
    assert_pretraining_dir_is_not_production,
    canonical_production_pretraining_dir,
    is_production_pretraining_dir,
    qualification_session,
    run_qualification_preflight,
)


def _isolated_settings(tmp_path: Path, *, pretraining_dir: Path | None = None) -> Settings:
    return Settings(
        database_path=tmp_path / "db.sqlite",
        allowed_data_dir=tmp_path / "data",
        pretraining_dir=pretraining_dir if pretraining_dir is not None else tmp_path / "pretraining",
        allow_external_storage=True,
    )


# -- A/B: exact production path rejected, isolated path accepted -------------

class TestExactPathScenarios:
    def test_exact_production_checkpoint_path_is_rejected(self) -> None:
        prod = canonical_production_pretraining_dir()
        assert is_production_pretraining_dir(prod) is True
        with pytest.raises(ProductionDatabaseGuardError, match="production checkpoint directory"):
            assert_pretraining_dir_is_not_production(prod, context="test")

    def test_isolated_tmp_path_is_accepted(self, tmp_path: Path) -> None:
        candidate = tmp_path / "pretraining"
        assert is_production_pretraining_dir(candidate) is False
        assert_pretraining_dir_is_not_production(candidate, context="test")  # must not raise


# -- C: relative equivalent path ----------------------------------------------

class TestRelativePathScenario:
    def test_relative_path_resolving_to_production_is_rejected(self) -> None:
        # Relative to PROJECT_ROOT, exactly like Settings._resolve_path
        # resolves a relative pretraining_dir -- not relative to cwd.
        assert is_production_pretraining_dir("data/core_models/pretraining") is True


# -- D: .. traversal ------------------------------------------------------------

class TestTraversalScenario:
    def test_dot_dot_traversal_resolving_to_production_is_rejected(self) -> None:
        from backend.core.config import PROJECT_ROOT

        traversal = PROJECT_ROOT / "deploy" / ".." / "data" / "core_models" / "pretraining"
        assert is_production_pretraining_dir(traversal) is True


# -- E: symlink to production checkpoint directory ----------------------------

class TestSymlinkScenario:
    def test_symlink_to_production_checkpoint_dir_is_rejected(self, tmp_path: Path) -> None:
        alias = tmp_path / "isolated_looking_link"
        alias.symlink_to(canonical_production_pretraining_dir())
        assert is_production_pretraining_dir(alias) is True
        with pytest.raises(ProductionDatabaseGuardError):
            assert_pretraining_dir_is_not_production(alias, context="test")


# -- F: nested production checkpoint path (deliberate containment policy) ----

class TestNestedPathScenario:
    def test_subdirectory_nested_under_production_is_rejected(self) -> None:
        """A qualification-labeled subdirectory *inside* the real
        production checkpoint tree (e.g. an operator's well-intentioned
        `data/core_models/pretraining/qualification/`) would still
        permanently write real files into the production `data/` tree --
        classified unsafe by deliberate design (Section F of the
        mission), not merely equality-checked."""
        nested = canonical_production_pretraining_dir() / "qualification"
        assert is_production_pretraining_dir(nested) is True

    def test_ancestor_of_production_checkpoint_dir_is_rejected(self) -> None:
        """The reverse containment direction: a candidate that is an
        *ancestor* of the real production checkpoint directory (e.g. the
        whole data/ tree) would also let writes land under production."""
        ancestor = canonical_production_pretraining_dir().parent
        assert is_production_pretraining_dir(ancestor) is True


# -- G: the exact Phase 2.8M blind-spot scenario ------------------------------

class TestPhase28MBlindSpotScenario:
    def test_isolated_db_and_data_dir_with_production_pretraining_dir_is_rejected(
        self, tmp_path: Path,
    ) -> None:
        """The precise configuration Phase 2.8M identified and this
        phase reproduced BEFORE fixing: database_path and
        allowed_data_dir isolated, pretraining_dir left at the real
        production default."""
        unsafe = _isolated_settings(tmp_path, pretraining_dir=canonical_production_pretraining_dir())

        result = run_qualification_preflight(unsafe)
        assert result.isolated_pretraining_dir_ok is False
        assert result.safe_to_proceed is False

        with pytest.raises(ProductionDatabaseGuardError, match="pretraining_dir"):
            with qualification_session(unsafe):
                pytest.fail("must never enter the session body with a production checkpoint destination")


# -- H: all three isolated -----------------------------------------------------

class TestFullyIsolatedScenario:
    def test_all_three_isolated_is_accepted(self, tmp_path: Path) -> None:
        safe = _isolated_settings(tmp_path)
        result = run_qualification_preflight(safe)
        assert result.isolated_pretraining_dir_ok is True
        assert result.safe_to_proceed is True

        with qualification_session(safe) as session:
            assert session.zero_mutation_baseline_claimable is True


# -- I: qualification_session() rejects before yielding -----------------------

class TestSessionRejectsBeforeYielding:
    def test_session_never_enters_body_with_unsafe_pretraining_dir(self, tmp_path: Path) -> None:
        unsafe = _isolated_settings(tmp_path, pretraining_dir=canonical_production_pretraining_dir())
        entered = False
        with pytest.raises(ProductionDatabaseGuardError):
            with qualification_session(unsafe):
                entered = True
        assert entered is False


# -- J: no silent substitution -------------------------------------------------

class TestNoSilentSubstitution:
    def test_rejection_reports_the_exact_unsafe_path_never_a_different_one(self, tmp_path: Path) -> None:
        unsafe_dir = canonical_production_pretraining_dir()
        with pytest.raises(ProductionDatabaseGuardError) as excinfo:
            assert_pretraining_dir_is_not_production(unsafe_dir, context="test")
        assert str(unsafe_dir) in str(excinfo.value)

    def test_preflight_result_reports_the_exact_pretraining_dir_given(self, tmp_path: Path) -> None:
        safe = _isolated_settings(tmp_path)
        result = run_qualification_preflight(safe)
        assert result.pretraining_dir == safe.resolved_pretraining_dir


# -- Regression: existing invariants (path/URI/env-var forms) still hold -----

class TestExistingGuardBehaviorUnaffected:
    def test_database_path_guard_is_unaffected_by_this_phases_addition(self) -> None:
        from backend.database.qualification_guard import is_production_database_path

        assert is_production_database_path(get_settings().resolved_database_path) is True

    def test_allowed_data_dir_check_is_unaffected(self, tmp_path: Path) -> None:
        safe = _isolated_settings(tmp_path)
        result = run_qualification_preflight(safe)
        assert result.isolated_data_dir_ok is True

    def test_env_var_isolated_pretraining_dir_is_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("BRUD_PRETRAINING_DIR", str(tmp_path / "env_pretraining"))
        settings = Settings(
            database_path=tmp_path / "db.sqlite", allowed_data_dir=tmp_path / "data",
            allow_external_storage=True,
        )
        assert settings.resolved_pretraining_dir == (tmp_path / "env_pretraining").resolve()
        result = run_qualification_preflight(settings)
        assert result.isolated_pretraining_dir_ok is True
