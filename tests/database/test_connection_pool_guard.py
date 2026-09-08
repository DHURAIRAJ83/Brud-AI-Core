"""Phase 7C-25: real correctness tests for `backend.database.connection_pool`.

Phase 7C-24 found that no connection pool existed anywhere in the codebase
for the Phase 7C-18-qualified `ReentrantCheckout` guard to attach to, and
stopped rather than implement an unwired guard. Phase 7C-25 built
`ConnectionPool` as real, importable production code backed by the exact
same `backend.database.connection.connect()` used everywhere else. This
file proves the pool's own mechanics (checkout/checkin lifecycle,
re-entrancy rejection, exhaustion, concurrency) and -- separately -- that a
pool-sourced connection is a drop-in replacement wherever the
already-authorized `connection=` propagation idiom (Phase 7C-16
`create_turn`, Phase 7C-20 `processor_for_version`, Phase 7C-22
`evaluate_suitability`) is already used. It does NOT test, and does not
imply, that the pool is wired into any live request path -- it isn't, by
design (see `connection_pool.py`'s module docstring).
"""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

try:
    import sentencepiece as spm
except ImportError:  # pragma: no cover - exercised when dependency is absent.
    spm = None

from backend.core.config import Settings
from backend.database.connection import connect
from backend.database.connection_pool import ConnectionPool, PoolExhausted, ReentrantCheckout
from backend.database.migrations import initialize_database
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.conversation_memory import MemoryPolicyCreate, SessionCreate
from backend.models.tokenizers import SPECIAL_TOKENS, TokenizerFamilyCreate, TokenizerVersionCreate
from backend.services.conversation_session_service import ConversationSessionService
from backend.services.tokenizer_registry import TokenizerService, _sha256_file


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "pool_guard.db"
    initialize_database(path)
    return path


@pytest.fixture
def pool(db_path: Path) -> ConnectionPool:
    p = ConnectionPool(db_path, size=2, checkout_timeout_s=1.0)
    yield p
    p.close()


@pytest.fixture
def settings(tmp_path: Path, db_path: Path) -> Settings:
    return Settings(
        database_path=db_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports",
        quarantine_dir=tmp_path / "quarantine",
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports",
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
        tokenizer_min_vocab_size=50,
    )


# --------------------------------------------------------------------------
# A. Checkout / checkin lifecycle
# --------------------------------------------------------------------------


def test_checkout_returns_a_real_connection(pool: ConnectionPool) -> None:
    connection = pool.checkout()
    try:
        assert connection.execute("SELECT 1").fetchone()[0] == 1
        assert pool.outstanding == 1
        assert pool.owns_connection() is True
    finally:
        pool.checkin(connection)


def test_checkin_returns_connection_to_pool_and_it_is_reusable(pool: ConnectionPool) -> None:
    connection = pool.checkout()
    pool.checkin(connection)
    assert pool.outstanding == 0
    assert pool.owns_connection() is False

    reused = pool.checkout()
    try:
        assert reused.execute("SELECT 1").fetchone()[0] == 1
    finally:
        pool.checkin(reused)


def test_checkout_scope_checks_in_on_normal_exit(pool: ConnectionPool) -> None:
    with pool.checkout_scope() as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1
        assert pool.outstanding == 1
    assert pool.outstanding == 0
    assert pool.owns_connection() is False


def test_checkout_scope_checks_in_on_exception(pool: ConnectionPool) -> None:
    with pytest.raises(ValueError):
        with pool.checkout_scope() as connection:
            connection.execute("SELECT 1")
            raise ValueError("boom")
    assert pool.outstanding == 0
    assert pool.owns_connection() is False
    # thread can immediately check out again -- ownership was really cleared
    reused = pool.checkout()
    pool.checkin(reused)


def test_checkin_with_wrong_connection_raises(pool: ConnectionPool) -> None:
    owned = pool.checkout()
    other = connect(pool._database_path)
    try:
        with pytest.raises(RuntimeError):
            pool.checkin(other)
    finally:
        pool.checkin(owned)
        other.close()


def test_double_checkin_raises(pool: ConnectionPool) -> None:
    connection = pool.checkout()
    pool.checkin(connection)
    with pytest.raises(RuntimeError):
        pool.checkin(connection)


def test_repeated_checkout_checkin_cycles_leave_no_leak(pool: ConnectionPool) -> None:
    for _ in range(50):
        connection = pool.checkout()
        connection.execute("SELECT 1")
        pool.checkin(connection)
    assert pool.outstanding == 0
    assert pool.owns_connection() is False


def test_broken_connection_is_replaced_at_checkin(pool: ConnectionPool) -> None:
    connection = pool.checkout()
    connection.close()  # simulate a connection that died while checked out
    pool.checkin(connection)  # must not raise -- health check catches it
    assert pool.outstanding == 0

    replacement = pool.checkout()
    try:
        assert replacement is not connection
        assert replacement.execute("SELECT 1").fetchone()[0] == 1
    finally:
        pool.checkin(replacement)


def test_broken_connection_is_replaced_at_checkout(pool: ConnectionPool) -> None:
    # Corrupt an idle connection directly in the pool's queue (not one
    # currently checked out -- the guard only ever allows a thread to hold
    # one at a time, so this is the only way to exercise checkout-time
    # health detection without a second thread).
    idle = pool._available.get_nowait()
    idle.close()
    pool._available.put(idle)

    seen = []
    for _ in range(pool._size):
        c = pool.checkout()
        pool.checkin(c)
        seen.append(c)

    assert any(c is not idle for c in seen)  # the broken one was replaced
    final = pool.checkout()
    try:
        assert final.execute("SELECT 1").fetchone()[0] == 1
    finally:
        pool.checkin(final)


# --------------------------------------------------------------------------
# B. ReentrantCheckout -- the guard itself
# --------------------------------------------------------------------------


def test_reentrant_checkout_raises_immediately(pool: ConnectionPool) -> None:
    outer = pool.checkout()
    try:
        start = time.monotonic()
        with pytest.raises(ReentrantCheckout):
            pool.checkout()
        elapsed = time.monotonic() - start
        # Must reject before any pool wait / SQLite busy_timeout (5000ms
        # default) could ever be reached -- generous bound for CI jitter.
        assert elapsed < 0.25
    finally:
        pool.checkin(outer)


def test_reentrant_checkout_does_not_create_a_second_connection(pool: ConnectionPool) -> None:
    outer = pool.checkout()
    try:
        with patch.object(pool, "_new_connection", wraps=pool._new_connection) as spy:
            with pytest.raises(ReentrantCheckout):
                pool.checkout()
            spy.assert_not_called()
    finally:
        pool.checkin(outer)


def test_reentrant_checkout_does_not_mutate_pool_accounting(pool: ConnectionPool) -> None:
    outer = pool.checkout()
    try:
        with pytest.raises(ReentrantCheckout):
            pool.checkout()
        assert pool.outstanding == 1  # still just the outer checkout
    finally:
        pool.checkin(outer)
    assert pool.outstanding == 0


def test_outer_connection_remains_usable_after_rejected_nested_checkout(
    pool: ConnectionPool,
) -> None:
    outer = pool.checkout()
    try:
        outer.execute("BEGIN")
        outer.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")
        outer.execute("INSERT INTO t(v) VALUES (1)")

        with pytest.raises(ReentrantCheckout):
            pool.checkout()

        # outer transaction is still perfectly usable after the rejection
        outer.execute("INSERT INTO t(v) VALUES (2)")
        outer.commit()
        rows = outer.execute("SELECT v FROM t ORDER BY v").fetchall()
        assert [r[0] for r in rows] == [1, 2]
    finally:
        pool.checkin(outer)


def test_outer_transaction_can_still_rollback_after_rejected_nested_checkout(
    pool: ConnectionPool,
) -> None:
    outer = pool.checkout()
    try:
        outer.execute("BEGIN")
        outer.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")
        with pytest.raises(ReentrantCheckout):
            pool.checkout()
        outer.rollback()
        # table creation was rolled back -- connection still fully usable
        outer.execute("BEGIN")
        tables = outer.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='t'"
        ).fetchall()
        assert tables == []
        outer.commit()
    finally:
        pool.checkin(outer)


def test_ownership_cleared_after_reentrant_rejection_allows_next_checkin(
    pool: ConnectionPool,
) -> None:
    outer = pool.checkout()
    with pytest.raises(ReentrantCheckout):
        pool.checkout()
    # the rejection itself must not have touched ownership -- checkin the
    # real outer connection still works cleanly
    pool.checkin(outer)
    assert pool.outstanding == 0
    assert pool.owns_connection() is False


# --------------------------------------------------------------------------
# C. Deliberate reproduction of the old unsafe nested-checkout shape
# --------------------------------------------------------------------------


def test_old_unsafe_nested_pattern_now_fails_fast_instead_of_lock_waiting(
    pool: ConnectionPool,
) -> None:
    """Reproduces exactly the shape Phase 7C-13/7C-14 found dangerous and
    Phase 7C-16/7C-20/7C-22 fixed at each real call site: an outer
    operation holds a connection with a write transaction open, and a
    nested operation forgets to propagate `connection=` and instead tries
    to acquire its own. Before this phase, that would have raced SQLite's
    lock (a fast lock-upgrade conflict or, worst case, the full 5000ms
    busy_timeout). With the guard, it must fail immediately and typed,
    with zero SQLite lock involvement at all -- checked here by proving no
    second connection was ever created, not just that an exception fired.
    """

    outer = pool.checkout()
    try:
        outer.execute("BEGIN")
        outer.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
        outer.execute("INSERT INTO t DEFAULT VALUES")

        with patch.object(pool, "_new_connection", wraps=pool._new_connection) as spy:
            start = time.monotonic()
            with pytest.raises(ReentrantCheckout):
                pool.checkout()  # the "forgot connection=" nested call
            elapsed = time.monotonic() - start

        assert spy.call_count == 0  # zero connections created for the attempt
        assert elapsed < 0.25  # nowhere near the 5000ms busy_timeout
        assert pool.outstanding == 1  # only the real outer checkout counted

        outer.commit()
        assert outer.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    finally:
        pool.checkin(outer)


# --------------------------------------------------------------------------
# D. Pool exhaustion (correctness only -- not a capacity/throughput claim)
# --------------------------------------------------------------------------


def test_pool_exhaustion_raises_bounded_error(db_path: Path) -> None:
    small_pool = ConnectionPool(db_path, size=1, checkout_timeout_s=0.3)
    try:
        holder = small_pool.checkout()
        result: dict[str, object] = {}

        def attempt_from_another_thread() -> None:
            start = time.monotonic()
            try:
                small_pool.checkout()
                result["outcome"] = "unexpectedly succeeded"
            except PoolExhausted:
                result["outcome"] = "PoolExhausted"
            result["elapsed"] = time.monotonic() - start

        thread = threading.Thread(target=attempt_from_another_thread)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert result["outcome"] == "PoolExhausted"
        assert result["elapsed"] < 2.0  # bounded, not an indefinite hang

        small_pool.checkin(holder)
        # pool is usable again immediately after the holder returns it
        reused = small_pool.checkout()
        small_pool.checkin(reused)
    finally:
        small_pool.close()


def test_pool_exhaustion_does_not_corrupt_waiter_ownership(db_path: Path) -> None:
    small_pool = ConnectionPool(db_path, size=1, checkout_timeout_s=0.2)
    try:
        holder = small_pool.checkout()

        def waiter() -> None:
            with pytest.raises(PoolExhausted):
                small_pool.checkout()
            # this thread never actually got a connection -- it must not
            # believe it owns one
            assert small_pool.owns_connection() is False

        thread = threading.Thread(target=waiter)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()

        small_pool.checkin(holder)
    finally:
        small_pool.close()


# --------------------------------------------------------------------------
# E. Concurrency correctness (not a capacity/throughput benchmark)
# --------------------------------------------------------------------------


def test_independent_threads_checkout_independently(db_path: Path) -> None:
    wide_pool = ConnectionPool(db_path, size=4, checkout_timeout_s=2.0)
    try:
        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            connection = wide_pool.checkout()
            try:
                ok = connection.execute("SELECT 1").fetchone()[0] == 1
            finally:
                wide_pool.checkin(connection)
            with lock:
                results.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
            assert not t.is_alive()

        assert results == [True] * 4
        assert wide_pool.outstanding == 0
    finally:
        wide_pool.close()


def test_one_threads_reentrant_rejection_does_not_affect_another_thread(
    db_path: Path,
) -> None:
    wide_pool = ConnectionPool(db_path, size=2, checkout_timeout_s=2.0)
    try:
        barrier = threading.Barrier(2)
        outcomes: dict[str, str] = {}

        def offender() -> None:
            connection = wide_pool.checkout()
            try:
                barrier.wait(timeout=5)
                try:
                    wide_pool.checkout()
                    outcomes["offender"] = "unexpectedly succeeded"
                except ReentrantCheckout:
                    outcomes["offender"] = "ReentrantCheckout"
            finally:
                wide_pool.checkin(connection)

        def innocent() -> None:
            barrier.wait(timeout=5)
            connection = wide_pool.checkout()
            try:
                outcomes["innocent"] = (
                    "ok" if connection.execute("SELECT 1").fetchone()[0] == 1 else "bad"
                )
            finally:
                wide_pool.checkin(connection)

        t1 = threading.Thread(target=offender)
        t2 = threading.Thread(target=innocent)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        assert not t1.is_alive() and not t2.is_alive()

        assert outcomes["offender"] == "ReentrantCheckout"
        assert outcomes["innocent"] == "ok"
        assert wide_pool.outstanding == 0
    finally:
        wide_pool.close()


def test_concurrent_checkout_checkin_leaves_pool_consistent(db_path: Path) -> None:
    wide_pool = ConnectionPool(db_path, size=3, checkout_timeout_s=2.0)
    try:
        errors: list[BaseException] = []
        lock = threading.Lock()

        def hammer() -> None:
            try:
                for _ in range(25):
                    connection = wide_pool.checkout()
                    connection.execute("SELECT 1")
                    wide_pool.checkin(connection)
            except BaseException as exc:  # noqa: BLE001
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=hammer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive()

        assert errors == []
        assert wide_pool.outstanding == 0
    finally:
        wide_pool.close()


def test_separate_processes_are_unaffected_by_thread_local_ownership(db_path: Path) -> None:
    """Thread-local ownership is process-local by construction (a
    `threading.local()` in one process shares no memory with another
    process's). This test proves the pool itself is usable from a
    completely separate process against the same database file, i.e. that
    nothing about the guard's design assumes single-process execution."""

    import multiprocessing

    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_checkout_once_in_child_process, args=(str(db_path), q))
    p.start()
    p.join(timeout=30)
    assert p.exitcode == 0
    assert q.get(timeout=5) == 1


def _checkout_once_in_child_process(path: str, queue) -> None:  # pragma: no cover - runs in a child process
    child_pool = ConnectionPool(Path(path), size=1, checkout_timeout_s=2.0)
    try:
        connection = child_pool.checkout()
        try:
            queue.put(connection.execute("SELECT 1").fetchone()[0])
        finally:
            child_pool.checkin(connection)
    finally:
        child_pool.close()


# --------------------------------------------------------------------------
# F. Phase 7C-27: cross-thread physical connection reuse.
#
# Phase 7C-26 found that `ConnectionPool` never passed
# `check_same_thread=False`, so a genuinely cross-thread checkout silently
# tripped `_is_healthy()`'s `SELECT 1` into a `sqlite3.ProgrammingError`,
# converted to a plain `False`, causing every cross-thread checkout to
# discard-and-recreate instead of reuse -- defeating pooling with zero
# observable signal. The tests below prove the Phase 7C-27 fix closes this.
#
# Methodology note (load-bearing, not decorative): sequential
# `t.start(); t.join()` pairs give a FALSE NEGATIVE for this bug, because
# Linux can recycle an OS thread id once a thread has fully exited, so two
# different `threading.Thread` objects run one-after-another can share the
# same underlying OS thread id -- which trivially satisfies
# `check_same_thread` even though they are logically distinct threads. All
# tests in this section use `threading.Barrier` to force every worker
# thread's lifetime to genuinely overlap before any of them checks out.
# --------------------------------------------------------------------------


def test_cross_thread_checkout_reuses_the_same_physical_connections(db_path: Path) -> None:
    """The central Phase 7C-27 regression test: more worker threads than
    the pool has slots, all genuinely overlapping (Barrier-synchronized),
    must reuse exactly `size` physical connection objects -- not create a
    new one per thread."""

    POOL_SIZE = 4
    WORKER_COUNT = 8

    wide_pool = ConnectionPool(db_path, size=POOL_SIZE, checkout_timeout_s=5.0)
    try:
        start_barrier = threading.Barrier(WORKER_COUNT)
        results: list[tuple[int, int]] = []
        lock = threading.Lock()

        def worker(n: int) -> None:
            start_barrier.wait(timeout=5)  # force genuinely overlapping lifetimes
            connection = wide_pool.checkout()
            with lock:
                results.append((n, id(connection)))
            time.sleep(0.05)  # hold it long enough that all 8 threads overlap
            assert connection.execute("SELECT 1").fetchone()[0] == 1
            wide_pool.checkin(connection)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(WORKER_COUNT)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive()

        unique_connections = {conn_id for _, conn_id in results}
        assert len(results) == WORKER_COUNT  # every worker completed successfully
        assert len(unique_connections) == POOL_SIZE, (
            f"expected exactly {POOL_SIZE} reused physical connections across "
            f"{WORKER_COUNT} genuinely concurrent cross-thread checkouts, got "
            f"{len(unique_connections)} -- the check_same_thread regression is back"
        )
        assert wide_pool.outstanding == 0  # no leak
        # Every checkout beyond the first `POOL_SIZE` had to be a genuine
        # reuse of an existing connection (there are only `POOL_SIZE` of them
        # and `WORKER_COUNT` checkouts happened), and zero were misdiagnosed
        # as broken and recreated.
        assert wide_pool.connection_reused_count == WORKER_COUNT
        assert wide_pool.connection_recreated_count == 0
    finally:
        wide_pool.close()


def test_connection_reused_counter_increments_on_healthy_cross_thread_checkout(
    db_path: Path,
) -> None:
    wide_pool = ConnectionPool(db_path, size=1, checkout_timeout_s=5.0)
    try:
        assert wide_pool.connection_reused_count == 0
        assert wide_pool.connection_recreated_count == 0

        def worker() -> None:
            connection = wide_pool.checkout()
            connection.execute("SELECT 1")
            wide_pool.checkin(connection)

        for _ in range(3):
            t = threading.Thread(target=worker)
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()

        # 3 cross-thread checkouts, all against a genuinely healthy
        # connection -- all 3 must count as reuse, none as recreation.
        assert wide_pool.connection_reused_count == 3
        assert wide_pool.connection_recreated_count == 0
    finally:
        wide_pool.close()


def test_connection_recreated_counter_increments_only_for_genuinely_broken_connections(
    db_path: Path,
) -> None:
    wide_pool = ConnectionPool(db_path, size=1, checkout_timeout_s=5.0)
    try:
        connection = wide_pool.checkout()
        # The pool's one connection was freshly created in `__init__` and is
        # healthy, so this first checkout is correctly counted as a reuse
        # (checkout() didn't need to create anything new to satisfy it).
        assert wide_pool.connection_reused_count == 1
        assert wide_pool.connection_recreated_count == 0

        connection.close()  # genuinely break it -- not a cross-thread issue
        wide_pool.checkin(connection)  # checkin's own health check should catch this

        assert wide_pool.connection_recreated_count == 1  # checkin replaced it

        # The replacement connection must be immediately usable, and its
        # checkout is itself a reuse (it's healthy, just created by checkin).
        replacement = wide_pool.checkout()
        try:
            assert replacement.execute("SELECT 1").fetchone()[0] == 1
        finally:
            wide_pool.checkin(replacement)

        assert wide_pool.connection_reused_count == 2
        assert wide_pool.connection_recreated_count == 1  # unchanged -- no new break
        assert wide_pool.outstanding == 0
    finally:
        wide_pool.close()


# --------------------------------------------------------------------------
# G. Real service compatibility: pool-sourced connections through the
#    already-authorized `connection=` propagation idiom.
# --------------------------------------------------------------------------


def test_pool_connection_compatible_with_create_turn(
    pool: ConnectionPool, db_path: Path
) -> None:
    """Chain #14 (Phase 7C-16): ChatOrchestrationService._persist_final ->
    ConversationSessionService.create_turn(connection=connection). Proves a
    pool-checked-out connection works identically to a
    `database_connection()`-sourced one through this exact idiom, and that
    no second connection is opened while it's used."""

    settings = Settings(database_path=db_path, log_level="CRITICAL")
    repository = ConversationMemoryRepository(db_path)
    service = ConversationSessionService(repository, settings)

    policy = service.create_policy(
        MemoryPolicyCreate(name=f"pool-test-policy-{uuid4().hex[:8]}"), admin_id="admin-1"
    )
    service.validate_policy(policy["public_id"], admin_id="admin-1")
    service.activate_policy(policy["public_id"], admin_id="admin-1")
    session = service.create_session(
        SessionCreate(
            session_mode="session_memory",
            memory_policy_public_id=policy["public_id"],
            participant_scope_key="pool-test-participant",
        ),
        admin_id="admin-1",
    )

    connection = pool.checkout()
    try:
        connection.execute("BEGIN")
        with patch.object(pool, "_new_connection", wraps=pool._new_connection) as spy:
            turn = service.create_turn(
                session["public_id"],
                role="user",
                content="hello from the pool",
                admin_id="admin-1",
                connection=connection,
            )
            spy.assert_not_called()  # no second connection opened
        assert pool.outstanding == 1  # still just the one pool checkout
        connection.commit()
    finally:
        pool.checkin(connection)

    assert turn["role"] == "user"
    # confirm it actually persisted (not just returned in-memory)
    verify = pool.checkout()
    try:
        row = verify.execute(
            "SELECT content_checksum_sha256 FROM conversation_turns WHERE public_id=?",
            (turn["public_id"],),
        ).fetchone()
        assert row is not None
    finally:
        pool.checkin(verify)


def _train_minimal_tokenizer_fixture(settings: Settings, db_path: Path) -> tuple[str, str]:
    """Directly constructs one real, loadable trained tokenizer version and
    one empty-but-valid dataset version, using the exact same
    `spm.SentencePieceTrainer.train()` call and artifact layout as
    `TokenizerService.train()` (mirrored, not imported, since the real
    method also requires a queued training-job row and a persisted corpus
    file this test has no need for). Returns
    (tokenizer_version_public_id, dataset_version_public_id). This is a
    deliberately hand-built fixture, not a run through the full
    dataset/record/review/tokenizer-job admin workflow (already covered by
    `test_tokenizer_pipeline.py` / `test_training_suitability_and_transformation.py`)
    -- disclosed here and in the Phase 7C-25 report."""

    if spm is None:
        pytest.skip("sentencepiece is not installed")

    repository = TokenizerRepository(db_path)
    service = TokenizerService(repository, settings)

    family = service.create_family(
        TokenizerFamilyCreate(
            name=f"pool-test-{uuid4().hex[:6]}", display_name="Pool Test", description=""
        ),
        admin_id="admin-1",
    )

    with repository.transaction() as connection:
        dataset_public_id = str(uuid4())
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (dataset_public_id, f"pool-test-dataset-{uuid4().hex[:6]}", "v1", "ready", "0" * 64),
        )

    version = service.create_version(
        TokenizerVersionCreate(
            family_public_id=family["public_id"],
            version="v1",
            dataset_version_public_id=dataset_public_id,
            vocabulary_size=80,
        ),
        admin_id="admin-1",
    )

    corpus_lines = [
        "வணக்கம் தமிழ் உலகம்",
        "Hello English world",
        "vanakkam nanba seri",
        "இன்று நல்ல நாள்",
        "Today is a good day",
        "நாளைக்கு plan என்ன",
        "Tomorrow plan ready",
        "தமிழ் மற்றும் English mixed text",
    ] * 8

    tmp_dir = settings.resolved_tokenizer_dir / "pool_test_corpus"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = tmp_dir / f"{version['public_id']}.txt"
    corpus_path.write_text("\n".join(corpus_lines), encoding="utf-8")

    artifact_dir = (
        settings.resolved_tokenizer_dir / "versions" / family["name"] / version["version"]
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prefix = artifact_dir / "tokenizer"
    user_symbols = ",".join(SPECIAL_TOKENS[4:])
    spm.SentencePieceTrainer.train(
        input=str(corpus_path),
        model_prefix=str(prefix),
        model_type="bpe",
        vocab_size=80,
        character_coverage=0.9995,
        normalization_rule_name="nmt_nfkc",
        hard_vocab_limit=False,
        pad_id=0,
        unk_id=1,
        bos_id=2,
        eos_id=3,
        pad_piece="<pad>",
        unk_piece="<unk>",
        bos_piece="<bos>",
        eos_piece="<eos>",
        user_defined_symbols=user_symbols,
    )
    (prefix.with_suffix(".model")).rename(artifact_dir / "tokenizer.model")
    (prefix.with_suffix(".vocab")).rename(artifact_dir / "tokenizer.vocab")

    model_checksum = _sha256_file(artifact_dir / "tokenizer.model")
    vocab_checksum = _sha256_file(artifact_dir / "tokenizer.vocab")
    manifest = {"files": ["tokenizer.model", "tokenizer.vocab"]}
    with repository.transaction() as connection:
        connection.execute(
            """UPDATE tokenizer_versions
            SET lifecycle_status='staging', model_checksum_sha256=?,
                vocabulary_checksum_sha256=?, artifact_manifest_json=?
            WHERE public_id=?""",
            (
                model_checksum,
                vocab_checksum,
                __import__("json").dumps(manifest),
                version["public_id"],
            ),
        )

    return version["public_id"], dataset_public_id


def test_pool_connection_compatible_with_processor_for_version(
    pool: ConnectionPool, settings: Settings, db_path: Path
) -> None:
    """Phase 7C-20: `TokenizerService.processor_for_version(connection=...)`.
    Proves a pool-sourced connection works through this idiom and yields a
    real, working SentencePiece processor."""

    tokenizer_public_id, _dataset_public_id = _train_minimal_tokenizer_fixture(settings, db_path)
    repository = TokenizerRepository(db_path)
    service = TokenizerService(repository, settings)

    connection = pool.checkout()
    try:
        connection.execute("BEGIN")
        with patch.object(pool, "_new_connection", wraps=pool._new_connection) as spy:
            processor = service.processor_for_version(tokenizer_public_id, connection=connection)
            spy.assert_not_called()
        assert pool.outstanding == 1
        connection.commit()
    finally:
        pool.checkin(connection)

    encoded = processor.encode("வணக்கம் hello", out_type=int)
    assert isinstance(encoded, list) and len(encoded) > 0
    assert processor.decode(encoded)


def test_pool_connection_compatible_with_evaluate_suitability(
    pool: ConnectionPool, settings: Settings, db_path: Path
) -> None:
    """Phase 7C-22: `TokenizerService.evaluate_suitability(connection=...)`
    -- the exact nested chain (`BaseTrainingService.evaluate_tokenizer` ->
    `evaluate_suitability`) that Phase 7C-21 discovered was still unsafe
    and Phase 7C-22 fixed. Proves a pool-sourced connection works through
    it end to end."""

    tokenizer_public_id, dataset_public_id = _train_minimal_tokenizer_fixture(settings, db_path)
    repository = TokenizerRepository(db_path)
    service = TokenizerService(repository, settings)

    connection = pool.checkout()
    try:
        connection.execute("BEGIN")
        with patch.object(pool, "_new_connection", wraps=pool._new_connection) as spy:
            result = service.evaluate_suitability(
                tokenizer_public_id, dataset_public_id, connection=connection
            )
            spy.assert_not_called()
        assert pool.outstanding == 1
        connection.commit()
    finally:
        pool.checkin(connection)

    assert result["tokenizer_version_public_id"] == tokenizer_public_id
    assert result["dataset_version_public_id"] == dataset_public_id
    assert result["vocabulary_size"] > 0


def test_pool_connection_reproduces_the_fixed_evaluate_tokenizer_nested_chain(
    pool: ConnectionPool, settings: Settings, db_path: Path
) -> None:
    """End-to-end reproduction of the real production nested chain that
    Phase 7C-21 found unsafe and Phase 7C-22 fixed --
    `BaseTrainingService.evaluate_tokenizer()`'s outer transaction calling
    `TokenizerService.evaluate_suitability(connection=connection)` -- but
    with the outer connection sourced from the pool instead of
    `database_connection()`, proving the fix is connection-source-agnostic."""

    tokenizer_public_id, dataset_public_id = _train_minimal_tokenizer_fixture(settings, db_path)
    repository = TokenizerRepository(db_path)
    tokenizer_service = TokenizerService(repository, settings)

    outer = pool.checkout()
    try:
        outer.execute("BEGIN")
        # Mirrors base_training_service.py:239-251 exactly: an outer
        # transaction already open, a fresh TokenizerService constructed,
        # and evaluate_suitability called with the outer connection
        # explicitly propagated -- the Phase 7C-22 fix.
        with patch.object(pool, "_new_connection", wraps=pool._new_connection) as spy:
            evaluation = tokenizer_service.evaluate_suitability(
                tokenizer_public_id, dataset_public_id, connection=outer
            )
            spy.assert_not_called()
        assert pool.outstanding == 1
        outer.commit()
    finally:
        pool.checkin(outer)

    assert evaluation["metrics"]
