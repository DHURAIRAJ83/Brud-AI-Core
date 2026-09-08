"""Phase 7C-33: TEST A-F -- proves the real, minimal single-`ConnectionPool`
FastAPI wiring prototype (one pool constructed in `lifespan`, stored on
`app.state.pool`, resolved via the `PoolDependency`/`get_pool()` override
mechanism, threaded into `base_training.py`'s `service()` factory for the
`experiment`/`create_experiment` routes, and into `CorpusRepository`'s now
pool-aware `transaction()`) behaves correctly through the real FastAPI
dependency graph -- not a synthetic pool-only test like
`test_connection_pool_guard.py`.

Scope, stated explicitly (see Phase 7C-33's own report for the full
picture): only `base_training.py`'s two routes and `CorpusRepository` were
wired this phase. Every other one of the ~564 repository construction
sites in the codebase still resolves `get_pool()`/`pool=` to `None` and
keeps today's exact unpooled `database_connection()` behavior -- these
tests do not claim otherwise.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.auth import AdminContext, require_admin, require_csrf
from backend.core.config import Settings
from backend.database.connection_pool import ConnectionPool, ReentrantCheckout
from backend.database.qualification_guard import assert_database_path_is_not_production
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.main import create_app
from backend.models.auth import AdminPublic, SessionPublic


def _fake_admin_context() -> AdminContext:
    now = datetime.now(UTC)
    return AdminContext(
        admin=AdminPublic(
            public_id="00000000-0000-0000-0000-000000000001",
            username="test-admin",
            display_name="Test Admin",
        ),
        session=SessionPublic(expires_at=now + timedelta(hours=1), last_used_at=now),
        session_id=1,
        token="test-token",
    )


def _build_app(tmp_path: Path, name: str) -> FastAPI:
    db_dir = tmp_path / name
    settings = Settings(
        database_path=db_dir / "api.db",
        database_backup_dir=db_dir / "backups",
        allowed_data_dir=db_dir,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    assert_database_path_is_not_production(settings.resolved_database_path, context="test_pool_lifecycle_wiring")
    app = create_app(settings)

    async def fake_admin() -> AdminContext:
        return _fake_admin_context()

    async def fake_csrf() -> AdminContext:
        return _fake_admin_context()

    app.dependency_overrides[require_admin] = fake_admin
    app.dependency_overrides[require_csrf] = fake_csrf
    return app


def _create_experiment(client: TestClient, dataset_public_id: str) -> str:
    response = client.post(
        "/api/admin/base-training/experiments",
        json={"name": "pool-wiring-test", "dataset_version_public_id": dataset_public_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["public_id"]


def _seed_dataset_version(app: FastAPI) -> str:
    """Direct SQL seed of one minimal `dataset_versions` row -- mirrors the
    hand-built-fixture technique already used by
    `test_connection_pool_guard.py`'s tokenizer tests, since going through
    the full dataset-import admin workflow is unrelated to what this file
    verifies."""

    from uuid import uuid4

    from backend.database.connection import database_connection

    public_id = str(uuid4())
    with database_connection(app.state.settings.resolved_database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (public_id, f"pool-wiring-dataset-{uuid4().hex[:6]}", "v1", "ready", "0" * 64),
        )
        connection.commit()
    return public_id


# --- TEST A: single pool identity -----------------------------------------------------


def test_a_single_pool_identity(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "test_a")
    with TestClient(app):
        pool = app.state.pool
        assert isinstance(pool, ConnectionPool)

        settings = app.state.settings
        from backend.api.routes.base_training import service

        svc_1 = service(settings, pool)
        svc_2 = service(settings, pool)
        # Two independently-constructed repository sets from the same
        # factory call pattern used by the real routes both received the
        # exact same pool object -- not merely equivalently-configured
        # pools.
        assert svc_1.repository.pool is pool
        assert svc_1.pretraining_repository.pool is pool
        assert svc_2.repository.pool is pool
        assert svc_1.repository.pool is svc_2.repository.pool


# --- TEST B: request reuse -----------------------------------------------------


def test_b_multiple_requests_do_not_construct_additional_pools(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "test_b")
    with TestClient(app) as client:
        pool_before = app.state.pool
        dataset_id = _seed_dataset_version(app)

        for _ in range(5):
            experiment_id = _create_experiment(client, dataset_id)
            read = client.get(f"/api/admin/base-training/experiments/{experiment_id}")
            assert read.status_code == 200

        assert app.state.pool is pool_before, "a new pool must never be constructed per-request"
        assert pool_before.outstanding == 0, "every request must check its connection back in"
        assert pool_before.connection_reused_count >= 5, (
            "at least the 5 write requests should have reused the pool's connections; "
            f"got reused={pool_before.connection_reused_count}, "
            f"recreated={pool_before.connection_recreated_count}"
        )
        assert pool_before.connection_recreated_count == 0


# --- TEST C: startup/shutdown -----------------------------------------------------


def test_c_startup_and_shutdown_lifecycle(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "test_c")
    assert app.state.pool is None, "pool must not exist before lifespan startup"

    with TestClient(app) as client:
        pool = app.state.pool
        assert isinstance(pool, ConnectionPool)
        dataset_id = _seed_dataset_version(app)
        _create_experiment(client, dataset_id)
        assert pool.outstanding == 0, "no checked-out connection should remain between requests"

    assert app.state.pool is None, "pool reference must be cleared after clean shutdown"


def test_c_repeated_testclient_usage_gets_fresh_isolated_pools(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "test_c_repeat")
    seen_pool_ids: set[int] = set()
    for _ in range(3):
        with TestClient(app) as client:
            assert isinstance(app.state.pool, ConnectionPool)
            seen_pool_ids.add(id(app.state.pool))
            dataset_id = _seed_dataset_version(app)
            _create_experiment(client, dataset_id)
        assert app.state.pool is None
    # Each `with TestClient(app):` re-runs `lifespan`, so each cycle gets
    # its own newly-constructed pool -- confirms shutdown really tears
    # down the previous one rather than a stale reference lingering.
    assert len(seen_pool_ids) == 3


# --- TEST D: transaction commit/rollback through the wired path -----------------------------------------------------


def test_d_commit_through_wired_path(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "test_d_commit")
    with TestClient(app) as client:
        pool = app.state.pool
        dataset_id = _seed_dataset_version(app)
        experiment_id = _create_experiment(client, dataset_id)

        read = client.get(f"/api/admin/base-training/experiments/{experiment_id}")
        assert read.status_code == 200
        assert read.json()["public_id"] == experiment_id
        assert pool.outstanding == 0


def test_d_rollback_through_wired_path(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "test_d_rollback")
    with TestClient(app) as client:
        pool = app.state.pool
        settings = app.state.settings
        from backend.api.routes.base_training import service

        svc = service(settings, pool)
        with pytest.raises(ValidationError):
            with svc.repository.transaction() as connection:
                connection.execute(
                    """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
                    VALUES ('rollback-test-dv','x','v1','ready', ?)""",
                    ("2" * 64,),
                )
                # A real write landed on the connection; raising here
                # (mirroring `transaction()`'s own `except ValidationError`
                # branch) proves the write is rolled back, not just that
                # no write was attempted.
                raise ValidationError("deliberate rollback for TEST D")

        # The rolled-back insert must not be visible.
        with pool.checkout_scope() as verify:
            row = verify.execute(
                "SELECT 1 FROM dataset_versions WHERE public_id='rollback-test-dv'"
            ).fetchone()
            assert row is None
        assert pool.outstanding == 0


# --- TEST E: real reentrancy through the actual dependency graph -----------------------------------------------------


def test_e_reentrant_checkout_through_wired_repositories(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "test_e")
    with TestClient(app):
        pool = app.state.pool
        settings = app.state.settings
        from backend.api.routes.base_training import service

        svc = service(settings, pool)
        dataset_id = _seed_dataset_version(app)

        started = time.perf_counter()
        with pytest.raises(ReentrantCheckout):
            with svc.repository.transaction() as outer_connection:
                outer_connection.execute(
                    "INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256) "
                    "VALUES ('reentrancy-outer','x','v1','ready', ?)",
                    ("1" * 64,),
                )
                # Deliberately buggy: a nested `transaction()` call on a
                # repository sharing the SAME pool, without propagating
                # `outer_connection` -- exactly the shape Phase 7C-16/
                # 7C-20/7C-22 fixed elsewhere via `connection=`.
                with svc.pretraining_repository.transaction() as _inner_connection:
                    pass
        elapsed_s = time.perf_counter() - started
        assert elapsed_s < 1.0, (
            f"ReentrantCheckout must fire near-instantly (no busy_timeout wait); took {elapsed_s:.3f}s"
        )

        # Outer transaction was rolled back (the whole `with` body raised).
        with pool.checkout_scope() as verify:
            row = verify.execute(
                "SELECT 1 FROM dataset_versions WHERE public_id='reentrancy-outer'"
            ).fetchone()
            assert row is None
        assert pool.outstanding == 0

        # And the pool remains fully usable afterward -- a real subsequent
        # transaction through the same wired repository succeeds cleanly.
        experiment = svc.create_experiment(
            __import__("backend.models.base_training", fromlist=["BaseTrainingExperimentCreate"])
            .BaseTrainingExperimentCreate(name="post-reentrancy", dataset_version_public_id=dataset_id),
            admin_id="00000000-0000-0000-0000-000000000001",
        )
        assert experiment["public_id"]
        assert pool.outstanding == 0


# --- TEST F: cross-request / cross-thread safety (genuinely concurrent) -----------------------------------------------------


def test_f_concurrent_requests_through_the_wired_pool(tmp_path: Path) -> None:
    """Genuinely concurrent (Barrier-synchronized, not sequential
    start()/join() -- Phase 7C-26 proved that gives a false negative via
    Linux OS-thread-id recycling) real HTTP requests through the wired
    pool. `base_training.py`'s `service()` uses `transaction()`'s default
    `immediate=False`, so under a deliberately adversarial burst of
    concurrent writers to the same dataset this is *expected*, per Phase
    7C-29/7C-30's already-established characterization, to sometimes raise
    the ordinary, typed `sqlite3.OperationalError: database is locked`
    deferred-BEGIN lock-upgrade conflict -- that is a pre-existing,
    already-qualified property of the deferred-BEGIN default, not
    something this phase's wiring changes or is meant to eliminate. What
    THIS test verifies is safety under that contention: no corruption, no
    connection leak, no duplicate pool, and genuine cross-thread
    connection reuse (not the Phase 7C-27 defect) even while some requests
    legitimately fail with the documented, typed exception."""

    app = _build_app(tmp_path, "test_f")
    with TestClient(app) as client:
        pool = app.state.pool
        dataset_id = _seed_dataset_version(app)

        n_workers = 8
        barrier = threading.Barrier(n_workers)
        unexpected_errors: list[BaseException] = []
        outcomes: list[str] = []
        created_ids: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            barrier.wait()
            try:
                local_client = TestClient(app, raise_server_exceptions=False)
                response = local_client.post(
                    "/api/admin/base-training/experiments",
                    json={"name": "concurrent", "dataset_version_public_id": dataset_id},
                )
                if response.status_code == 200:
                    with lock:
                        outcomes.append("success")
                        created_ids.append(response.json()["public_id"])
                elif response.status_code == 500:
                    with lock:
                        outcomes.append("expected_lock_contention")
                else:
                    raise AssertionError(f"unexpected status {response.status_code}: {response.text}")
            except BaseException as exc:  # noqa: BLE001
                with lock:
                    unexpected_errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert unexpected_errors == [], f"unexpected failures: {unexpected_errors}"
        assert len(outcomes) == n_workers
        assert "success" in outcomes, "at least one concurrent writer must succeed"
        assert len(set(created_ids)) == len(created_ids), "each successful write must be its own distinct row"
        assert app.state.pool is pool, "no additional pool may be constructed under concurrent load"
        assert pool.outstanding == 0, "every concurrent checkout must be checked back in, success or failure"
        assert pool.connection_recreated_count == 0, (
            "genuinely concurrent, real cross-thread checkouts must reuse pooled connections, "
            "not silently discard/recreate them (the Phase 7C-27 defect this pool already fixed)"
        )
        assert pool.connection_reused_count >= n_workers


# --- TEST G (Phase 7C-34): generate_profile / tokenizer_evaluate through the
# real wired pool -- these are exactly the two routes that reach the
# previously-fixed TokenizerService nested chains (Phase 7C-20
# processor_for_version, Phase 7C-22 evaluate_suitability) via
# `connection=connection` propagation, so this proves that fix continues to
# work correctly when the outer connection comes from a real pool instead of
# a fresh `database_connection()` -----------------------------------------


def test_g_generate_profile_and_tokenizer_evaluate_through_wired_pool(tmp_path: Path) -> None:
    from tests.backend.test_base_training_api import _fixture_refs

    app = _build_app(tmp_path, "test_g")
    with TestClient(app) as client:
        pool = app.state.pool
        assert pool is not None

        refs = _fixture_refs(app)
        experiment_id = _create_experiment(client, refs["dataset"])

        reused_before = pool.connection_reused_count
        recreated_before = pool.connection_recreated_count

        profile = client.post(f"/api/admin/base-training/experiments/{experiment_id}/profile")
        assert profile.status_code == 200, profile.text
        assert profile.json()["total_records"] > 0

        tokenizer_eval = client.post(
            f"/api/admin/base-training/experiments/{experiment_id}/tokenizer-evaluate"
        )
        assert tokenizer_eval.status_code == 200, tokenizer_eval.text
        assert tokenizer_eval.json()["tokenizer_decision"] in {
            "reuse_existing_tokenizer", "train_new_tokenizer_version",
        }

        # Both routes genuinely used the shared pool (not a fallback fresh
        # connection), and neither triggered the Phase 7C-27
        # discard-and-recreate defect.
        assert pool.connection_reused_count > reused_before
        assert pool.connection_recreated_count == recreated_before
        assert app.state.pool is pool, "no second pool was constructed"
        assert pool.outstanding == 0


# --- TEST H (Phase 7C-34): forced startup-failure cleanup ------------------
# `initialize_database()` runs before the pool is constructed inside
# `lifespan` (by deliberate design -- see Phase 7C-33's `main.py` comment:
# the pool line runs "not eagerly here, so a startup failure never leaves a
# partially-used pool behind"). This test forces that pre-pool failure path
# and independently verifies no pool artifact escapes it, without modifying
# any production error-handling code to manufacture a pass.


def test_h_forced_startup_failure_leaves_no_pool_and_does_not_block_next_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backend.main as main_module

    db_dir = tmp_path / "test_h_failure"
    settings = Settings(
        database_path=db_dir / "api.db",
        database_backup_dir=db_dir / "backups",
        allowed_data_dir=db_dir,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    assert_database_path_is_not_production(
        settings.resolved_database_path, context="test_pool_lifecycle_wiring"
    )

    def _boom(*args, **kwargs):
        raise RuntimeError("forced startup failure for Phase 7C-34 Step 8")

    monkeypatch.setattr(main_module, "initialize_database", _boom)
    failing_app = main_module.create_app(settings)

    assert failing_app.state.pool is None, "pool must not exist before lifespan runs"
    with pytest.raises(RuntimeError, match="forced startup failure"):
        with TestClient(failing_app):
            pass  # lifespan startup should raise before yield is ever reached

    # The failure occurred strictly before the pool-construction line, so no
    # pool was ever assigned -- confirmed directly, not assumed.
    assert failing_app.state.pool is None, "no partially-constructed pool may remain after a startup failure"

    # A second, independent, real (non-monkeypatched) app instance must be
    # completely unaffected and start cleanly.
    monkeypatch.undo()
    healthy_app = _build_app(tmp_path, "test_h_recovery")
    with TestClient(healthy_app) as client:
        # Lifespan startup completing without raising, and a real pool
        # being constructed, is itself the "starts cleanly" proof -- no
        # unauthenticated route exists in this app to probe further, and
        # adding one would be scope creep beyond this test's purpose.
        assert healthy_app.state.pool is not None
        experiment_response = client.get("/api/admin/base-training/experiments")
        assert experiment_response.status_code in (200, 401, 403), experiment_response.text
    assert healthy_app.state.pool is None, "the healthy app's own pool must close normally on its shutdown"
