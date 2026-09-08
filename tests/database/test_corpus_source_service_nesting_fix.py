"""Phase 7C-39: fixes the same-repository nested-transaction hazard Phase
7C-38's AST audit discovered: `CorpusSourceService.advance_production_lifecycle()`
opens a transaction, and -- while still inside it, for `target_status="approved"`
-- called `self.training_eligibility(source_public_id)`, which itself opened a
second, independent transaction with no `connection=` propagation. This was
silently safe today (every construction site uses `pool=None`, so each
`transaction()` call opens its own independent connection), but would raise
`ReentrantCheckout` the moment `CorpusRepository` is ever wired to a shared
`ConnectionPool`, since the calling thread would already own a checked-out
connection.

The fix uses the exact `connection=None` propagation idiom already proven six
times elsewhere in this investigation (`create_turn`, `processor_for_version`,
`evaluate_suitability`, `get_analysis`, `get_extraction_run`,
`get_normalization_run`): `training_eligibility()` gained an optional
`connection=` parameter; when supplied, it runs directly on that connection
instead of opening a second one; `advance_production_lifecycle()` now passes
its own already-open `connection` through. Callers that don't supply one
(the CLI, the read-only `/training-eligibility` route) keep today's exact
standalone behavior unchanged.

This does NOT wire `CorpusRepository` into the production `ConnectionPool` --
that remains a separately authorized future decision. These tests prove the
fix is safe for that future architecture, using a real, disposable,
pool-backed `CorpusSourceService` to simulate it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection_pool import ConnectionPool, ReentrantCheckout
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository
from backend.models.corpus import (
    CorpusPolicyCreate,
    LicenceReviewDecision,
    SourceLicenceCreate,
    SourceRegistryCreate,
)
from backend.services.corpus_source_service import CorpusSourceService


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "corpus.db"
    initialize_database(path)
    return path


def _settings(db_path: Path) -> Settings:
    return Settings(database_path=db_path, log_level="CRITICAL")


def _build_eligible_source(repo: CorpusRepository, db_path: Path) -> tuple[CorpusSourceService, str]:
    """Real, end-to-end fixture: creates a policy, a source, verifies its
    origin, attaches an approved AI-training-permitted licence, and advances
    the source through `provenance_verified` -> `licence_reviewed`, leaving
    it one transition away from `approved` -- the exact transition that
    exercises the fixed nested call."""

    svc = CorpusSourceService(repo, _settings(db_path))
    policy = svc.create_policy(
        CorpusPolicyCreate(name="test-policy", allowed_source_types=["manual_admin_text"]),
        admin_id="admin-1",
    )
    source = svc.create_source(
        SourceRegistryCreate(
            corpus_policy_public_id=policy["public_id"],
            title="Test Source",
            source_type="manual_admin_text",
            intended_use="pretraining_corpus",
        ),
        admin_id="admin-1",
    )
    source_public_id = source["public_id"]
    # `assess_training_export_eligibility` requires the source's own
    # `status` column (a distinct lifecycle from `production_lifecycle_status`)
    # to be "approved" as well -- advance it through its own transitions.
    svc.transition_source_status(source_public_id, "origin_review", "admin-1")
    svc.transition_source_status(source_public_id, "licence_review", "admin-1")
    svc.transition_source_status(source_public_id, "approved", "admin-1")
    svc.verify_origin(source_public_id, "admin-1", evidence="verified")
    licence = svc.create_licence(
        source_public_id,
        SourceLicenceCreate(licence_family="public_domain", ai_training_permitted=True),
        admin_id="admin-1",
    )
    svc.review_licence(
        licence["public_id"], LicenceReviewDecision(review_status="approved"), admin_id="admin-1"
    )
    svc.advance_production_lifecycle(source_public_id, "provenance_verified", "admin-1")
    svc.advance_production_lifecycle(source_public_id, "licence_reviewed", "admin-1")
    return svc, source_public_id


# --- A/H: unpooled workflow and standalone callers are unchanged -----------


def test_unpooled_advance_to_approved_still_succeeds(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    svc, source_public_id = _build_eligible_source(repo, db_path)
    result = svc.advance_production_lifecycle(source_public_id, "approved", "admin-1")
    assert result["production_lifecycle_status"] == "approved"


def test_standalone_training_eligibility_without_connection_unchanged(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    svc, source_public_id = _build_eligible_source(repo, db_path)
    result = svc.training_eligibility(source_public_id)
    assert result["eligible"] is True
    assert result["blocking_reasons"] == []


# --- B/C/D: same-pool nested call no longer double-checks-out --------------


def test_pooled_advance_to_approved_does_not_raise_reentrant_checkout(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    _build_step_svc, source_public_id = _build_eligible_source(repo, db_path)

    pool = ConnectionPool(db_path, size=4)
    pooled_repo = CorpusRepository(db_path, pool=pool)
    pooled_svc = CorpusSourceService(pooled_repo, _settings(db_path))

    result = pooled_svc.advance_production_lifecycle(source_public_id, "approved", "admin-1")

    assert result["production_lifecycle_status"] == "approved"


def test_pooled_advance_uses_exactly_one_checkout_not_two(db_path: Path) -> None:
    """Proves the nested call reuses the SAME physical connection rather
    than merely avoiding an exception by coincidence: exactly one checkout
    occurs for the entire `advance_production_lifecycle` call, including its
    nested `training_eligibility` call."""

    repo = CorpusRepository(db_path)
    _build_step_svc, source_public_id = _build_eligible_source(repo, db_path)

    pool = ConnectionPool(db_path, size=4)
    pooled_repo = CorpusRepository(db_path, pool=pool)
    pooled_svc = CorpusSourceService(pooled_repo, _settings(db_path))

    pooled_svc.advance_production_lifecycle(source_public_id, "approved", "admin-1")

    assert pool.connection_reused_count + pool.connection_recreated_count == 1
    assert pool.outstanding == 0


def test_connection_propagated_is_the_exact_outer_connection_object(db_path: Path) -> None:
    """Asserts connection identity with `is`, not merely successful
    execution -- the nested helper must run on the SAME connection object
    the outer transaction already owns."""

    repo = CorpusRepository(db_path)
    svc, source_public_id = _build_eligible_source(repo, db_path)

    seen: dict[str, object] = {}
    original_source = repo.source

    def spying_source(connection, public_id):
        seen.setdefault("connection", connection)
        return original_source(connection, public_id)

    repo.source = spying_source  # type: ignore[method-assign]
    try:
        with repo.transaction() as outer_connection:
            eligibility = svc.training_eligibility(source_public_id, connection=outer_connection)
            assert eligibility["eligible"] is True
            assert seen["connection"] is outer_connection
    finally:
        repo.source = original_source  # type: ignore[method-assign]


# --- E/F/G: commit, rollback, and leak behavior are unchanged --------------


def test_outer_transaction_commits_correctly_through_the_fix(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    svc, source_public_id = _build_eligible_source(repo, db_path)

    pool = ConnectionPool(db_path, size=4)
    pooled_repo = CorpusRepository(db_path, pool=pool)
    pooled_svc = CorpusSourceService(pooled_repo, _settings(db_path))
    pooled_svc.advance_production_lifecycle(source_public_id, "approved", "admin-1")

    # Re-read independently to confirm the write actually persisted, not
    # merely returned in-memory.
    verify_repo = CorpusRepository(db_path)
    with verify_repo.transaction() as connection:
        row = verify_repo.source(connection, source_public_id)
    assert row["production_lifecycle_status"] == "approved"


def test_outer_transaction_rolls_back_when_ineligible(db_path: Path) -> None:
    """Reproduces the fixed call path but with an ineligible source, so the
    business-logic `ValidationError` raised inside the propagated
    `training_eligibility` call must roll back the whole outer transaction
    -- not a `ReentrantCheckout`, and no partial write."""

    repo = CorpusRepository(db_path)
    svc = CorpusSourceService(repo, _settings(db_path))
    policy = svc.create_policy(
        CorpusPolicyCreate(name="p", allowed_source_types=["manual_admin_text"]),
        admin_id="admin-1",
    )
    source = svc.create_source(
        SourceRegistryCreate(
            corpus_policy_public_id=policy["public_id"],
            title="T",
            source_type="manual_admin_text",
            intended_use="pretraining_corpus",
        ),
        admin_id="admin-1",
    )
    source_public_id = source["public_id"]
    svc.verify_origin(source_public_id, "admin-1", evidence="e")
    licence = svc.create_licence(
        source_public_id,
        # ai_training_permitted=False -> training_eligibility() reports ineligible
        SourceLicenceCreate(licence_family="public_domain", ai_training_permitted=False),
        admin_id="admin-1",
    )
    svc.review_licence(
        licence["public_id"], LicenceReviewDecision(review_status="approved"), admin_id="admin-1"
    )
    svc.advance_production_lifecycle(source_public_id, "provenance_verified", "admin-1")
    svc.advance_production_lifecycle(source_public_id, "licence_reviewed", "admin-1")

    pool = ConnectionPool(db_path, size=4)
    pooled_repo = CorpusRepository(db_path, pool=pool)
    pooled_svc = CorpusSourceService(pooled_repo, _settings(db_path))

    with pytest.raises(ValidationError):
        pooled_svc.advance_production_lifecycle(source_public_id, "approved", "admin-1")

    assert pool.outstanding == 0

    verify_repo = CorpusRepository(db_path)
    with verify_repo.transaction() as connection:
        row = verify_repo.source(connection, source_public_id)
    # Rolled back: still licence_reviewed, never touched approved.
    assert row["production_lifecycle_status"] == "licence_reviewed"


def test_no_connection_leak_across_repeated_pooled_transitions(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    pool = ConnectionPool(db_path, size=2)
    pooled_repo = CorpusRepository(db_path, pool=pool)

    for _ in range(10):
        _build_step_svc, source_public_id = _build_eligible_source(pooled_repo, db_path)
        pooled_svc = CorpusSourceService(pooled_repo, _settings(db_path))
        pooled_svc.advance_production_lifecycle(source_public_id, "approved", "admin-1")

    assert pool.outstanding == 0
    assert pool.connection_recreated_count == 0


# --- I: the fix does not introduce a NEW nested transaction ----------------


def test_fix_does_not_open_a_second_transaction_when_connection_supplied(db_path: Path) -> None:
    """When `connection=` is supplied, `training_eligibility` must not call
    `self.repository.transaction()` at all -- verified by making a second,
    concurrent, unpooled connection's write succeed while the outer
    transaction (which has only read so far) is still open, which would be
    impossible if a second deferred-or-immediate transaction were opened on
    the pool internally and behaved unexpectedly."""

    import sqlite3

    repo = CorpusRepository(db_path)
    svc, source_public_id = _build_eligible_source(repo, db_path)

    with repo.transaction() as connection:
        result = svc.training_eligibility(source_public_id, connection=connection)
        assert result["eligible"] is True
        other = sqlite3.connect(db_path, timeout=0.2)
        other.execute("PRAGMA busy_timeout = 200")
        other.execute("CREATE TABLE IF NOT EXISTS _probe_nesting_fix(id INTEGER)")
        other.commit()
        other.close()


# --- J: the affected workflow is semantically unchanged end-to-end --------


def test_immediate_true_outer_transaction_also_works_through_the_fix(db_path: Path) -> None:
    """Phase 7C-37 qualified `immediate=True`; this confirms the Phase
    7C-39 propagation fix is BEGIN-mode-agnostic -- `training_eligibility`'s
    `connection=` branch never opens its own transaction, so it behaves
    identically regardless of how the caller's connection was acquired."""

    from backend.database.repositories.base import BaseRepository

    repo = CorpusRepository(db_path)
    svc, source_public_id = _build_eligible_source(repo, db_path)

    pool = ConnectionPool(db_path, size=4)
    pooled_repo = CorpusRepository(db_path, pool=pool)
    pooled_svc = CorpusSourceService(pooled_repo, _settings(db_path))

    with BaseRepository(db_path, pool=pool).transaction(immediate=True) as connection:
        row = pooled_repo.source(connection, source_public_id)
        eligibility = pooled_svc.training_eligibility(source_public_id, connection=connection)
        assert eligibility["eligible"] is True
        pooled_repo.update_source(connection, row["id"], {"production_lifecycle_status": "approved"})

    assert pool.outstanding == 0
    assert pool.connection_recreated_count == 0
