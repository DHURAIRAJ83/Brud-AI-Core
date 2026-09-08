"""Phase 2.8H: explicit, fail-closed isolation between qualification/test
code and the real production database.

Phase 2.8G proved its own training/checkpoint tests never opened the
production database, but it also found the production database was no
longer byte-for-byte identical to its recorded baseline -- caused by an
independently-running `uvicorn backend.main:app` dev server writing
routine audit-log rows in response to real dashboard traffic, not by
anything the qualification tests themselves did. That reconnaissance
also surfaced the concrete, currently-latent risk this module exists to
close: `backend.main.create_app(settings=None)` silently falls back to
`get_settings()` -- the real production `Settings` -- whenever a caller
forgets to pass its own isolated settings. No test currently does this,
but nothing previously made it impossible either.

This module is deliberately NOT wired into
`backend.database.connection.connect()`/`database_connection()`: those
functions are the one production `create_app()` legitimately uses to
reach the real database on every request, and baking an unconditional
block into them would either break production or require every
legitimate production call site to carry an explicit opt-out flag -- a
strictly worse safety shape than requiring qualification/test code to
explicitly assert safety before it begins. Every function in this
module that opens the production database at all
(`open_production_database_read_only()`) does so strictly read-only,
via SQLite's own `mode=ro` URI connection flag; every other function is
pure path/process inspection with no I/O against the database file
itself. None of them ever open the production database for writing,
and none silently substitute a different path -- callers that fail the
guard must fix their own configuration, not be redirected.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from backend.core.config import get_settings

# The real Brud AI uvicorn/gunicorn ASGI target string, as used both by
# `uvicorn backend.main:app` (the actual production launch command) and
# by this module's own process-identity check below. Kept as a single
# named constant so both call sites and this module agree on it.
BRUD_AI_ASGI_TARGET = "backend.main:app"


class ProductionDatabaseGuardError(Exception):
    """Raised when qualification/test code's resolved database path
    turns out to be the real production database. Fails closed: the
    caller must fix its own configuration to use an isolated database:
    this exception never triggers a silent redirect or a fallback
    database of this module's own choosing."""


def canonical_production_database_path() -> Path:
    """The production database's canonical, symlink-resolved path.

    Deliberately reuses `get_settings().resolved_database_path` (the
    exact same value the real, currently-configured application would
    connect to) rather than a hardcoded literal, so this stays correct
    under `BRUD_DATABASE_PATH` environment-variable overrides and any
    future default change -- there is exactly one definition of "the
    production database path" in this codebase, and this function reads
    it rather than repeating it (Part 2, item 12 of the Phase 2.8H
    mission: any environment-variable based database overrides must not
    create a blind spot)."""

    return get_settings().resolved_database_path


def _strip_sqlite_uri(candidate: str) -> str:
    """Extract the real filesystem path out of a `sqlite3` URI
    (`sqlite3.connect(f"file:{path}?mode=ro", uri=True)` is used
    elsewhere in this codebase for read-only production inspection) so
    URI-wrapped paths cannot bypass path comparison by looking like an
    opaque string instead of a path (Invariant J). Handles both
    `file:/abs/path` and `file:///abs/path`; query strings
    (`?mode=ro`, `?cache=shared`, ...) are dropped; percent-encoding is
    undone."""

    if not candidate.startswith("file:"):
        return candidate
    from urllib.parse import unquote, urlsplit

    parts = urlsplit(candidate)
    # `file:/x` parses with an empty netloc and path=/x; `file:///x`
    # also parses with an empty netloc and path=/x -- both forms land
    # on `parts.path` directly. A non-empty `parts.netloc` (e.g.
    # `file://host/x`, not used by sqlite3 but handled defensively)
    # is prepended back so it is not silently dropped.
    raw_path = (parts.netloc + parts.path) if parts.netloc else parts.path
    return unquote(raw_path)


def resolve_database_path(candidate: Path | str) -> Path:
    """Resolve `candidate` to an absolute, symlink-following canonical
    path, exactly like `Settings.resolved_database_path` resolves
    relative paths against `PROJECT_ROOT` and follows symlinks via
    `Path.resolve()`. Works whether or not the file exists yet
    (`Path.resolve()` is non-strict by default) so a not-yet-created
    qualification database can still be checked before it is opened.
    Also accepts `sqlite3` URI strings (Invariant J) via
    `_strip_sqlite_uri()`."""

    from backend.core.config import PROJECT_ROOT

    text = str(candidate)
    path = Path(_strip_sqlite_uri(text) if text.startswith("file:") else text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def is_production_database_path(candidate: Path | str) -> bool:
    """True if `candidate` -- after resolving symlinks and relative-path
    indirection exactly like the real application does -- points at the
    same file as the production database (Invariant I: a symlink or
    path alias must not bypass this check, because both sides of the
    comparison go through the identical canonicalization)."""

    return resolve_database_path(candidate) == canonical_production_database_path()


def assert_database_path_is_not_production(database_path: Path | str, *, context: str) -> None:
    """Fail closed: raise `ProductionDatabaseGuardError` if
    `database_path` resolves to the production database. `context`
    should name the caller (e.g. a fixture or subprocess-runner mode)
    so the resulting message is actionable."""

    if is_production_database_path(database_path):
        raise ProductionDatabaseGuardError(
            f"{context}: database path resolves to the production database "
            f"({canonical_production_database_path()}); refusing to run writable "
            "qualification/test code against it. Construct an isolated "
            "Settings(database_path=<tmp_path>/...) instead -- this guard never "
            "substitutes a database of its own choosing."
        )


# -- Checkpoint destination guard (Phase 2.8N) --------------------------------
#
# Phase 2.8M found, and Phase 2.8N directly reproduced before fixing, a real
# blind spot: this module verified `Settings.database_path` and
# `Settings.allowed_data_dir` were isolated from production, but never
# `Settings.pretraining_dir` -- the actual MB-22 checkpoint destination
# (`_build_real_job_context()`'s `checkpoint_root = self.settings.
# resolved_pretraining_dir / "mini_brain_training_jobs" / job_id`, the sole
# path every real training checkpoint is written under -- traced directly
# this phase; `core_checkpoint_dir` is a separate setting governing a
# different, non-MB-22 checkpoint system and is out of this phase's scope).
# A `Settings` object could isolate its database and top-level data
# directory while leaving `pretraining_dir` at its real default
# (`data/core_models/pretraining`) and this module's own preflight/session
# would report `safe_to_proceed: True` regardless -- reproduced directly,
# not merely inferred, before any code here was changed.


def canonical_production_pretraining_dir() -> Path:
    """The production checkpoint destination's canonical, symlink-resolved
    path. Reuses `get_settings().resolved_pretraining_dir` for the same
    reason `canonical_production_database_path()` reuses
    `resolved_database_path` -- one single definition of "the production
    checkpoint directory" in this codebase, staying correct under any
    `BRUD_PRETRAINING_DIR` environment override rather than a second,
    hardcoded literal."""

    return get_settings().resolved_pretraining_dir


def is_production_pretraining_dir(candidate: Path | str) -> bool:
    """True if `candidate` -- after the same `PROJECT_ROOT`-relative +
    symlink-resolving canonicalization `resolve_database_path()` already
    applies -- is the production checkpoint directory, OR is nested
    *inside* it, OR *contains* it.

    The containment check (not merely equality) is a deliberate, traced
    decision, not a guess: `resolve_database_path()` is reused here purely
    for its generic "resolve any path against `PROJECT_ROOT`, following
    symlinks" behavior (it does not require the target to be a database
    file). A qualification directory nested under the real production
    checkpoint tree (e.g. `data/core_models/pretraining/qualification/`)
    would still permanently write real files into the production `data/`
    tree -- exactly the kind of write this whole guard module exists to
    prevent -- so it is classified unsafe exactly like an exact-path
    collision, not treated as a lesser case. The reverse direction (a
    caller naming an *ancestor* of the real production directory, e.g. the
    whole `data/` tree) is caught for the same reason: any write under
    that candidate would also land under the production checkpoint tree."""

    candidate_resolved = resolve_database_path(candidate)
    canonical = canonical_production_pretraining_dir()
    return candidate_resolved.is_relative_to(canonical) or canonical.is_relative_to(candidate_resolved)


def assert_pretraining_dir_is_not_production(pretraining_dir: Path | str, *, context: str) -> None:
    """Fail closed: raise `ProductionDatabaseGuardError` if `pretraining_dir`
    is the production checkpoint directory, is nested inside it, or
    contains it. Never silently substitutes a different directory."""

    if is_production_pretraining_dir(pretraining_dir):
        raise ProductionDatabaseGuardError(
            f"{context}: pretraining_dir resolves to (or overlaps with) the production "
            f"checkpoint directory ({canonical_production_pretraining_dir()}); refusing to "
            "run writable qualification/test code against it. Construct an isolated "
            "Settings(pretraining_dir=<tmp_path>/..., ...) instead -- this guard never "
            "substitutes a checkpoint directory of its own choosing."
        )


# -- Live process detection (Part 6) -----------------------------------------


@dataclass(frozen=True)
class LiveProcessInfo:
    pid: int
    cmdline: str
    cwd: str | None
    classification: str  # "brud_ai_asgi_process" | "unrelated_process" | "unknown_process"
    database_path_override: str | None  # value of BRUD_DATABASE_PATH in that process's environ, if readable
    likely_production_writer: bool


@dataclass(frozen=True)
class ProcessInspectionResult:
    """Honest result of a `/proc`-based process scan. `degraded` is True
    when process inspection was not fully available in this environment
    (e.g. `/proc` missing, as on a non-Linux host, or every candidate
    process's details were unreadable) -- callers must treat a degraded
    result as "unknown", never as "no writer exists" (Part 6: "Do NOT
    claim 'no production writer exists' merely because ... unavailable")."""

    processes: list[LiveProcessInfo]
    degraded: bool
    degraded_reason: str | None = field(default=None)

    @property
    def production_writers(self) -> list[LiveProcessInfo]:
        return [p for p in self.processes if p.likely_production_writer]


def _read_proc_text(pid: int, name: str) -> str | None:
    try:
        with open(f"/proc/{pid}/{name}", "rb") as handle:
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return None


def _read_proc_cwd(pid: int) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


def _read_proc_environ_database_path(pid: int) -> str | None:
    raw = _read_proc_text(pid, "environ")
    if raw is None:
        return None
    for entry in raw.split("\x00"):
        if entry.startswith("BRUD_DATABASE_PATH="):
            return entry[len("BRUD_DATABASE_PATH="):]
    return None


def detect_live_production_database_writers(*, repo_root: Path | None = None) -> ProcessInspectionResult:
    """Scan `/proc` (the same OS-level evidence source Phase 2.8G's own
    reconnaissance used manually: `ps`, `/proc/<pid>/cmdline`,
    `/proc/<pid>/cwd`) for processes that are the real Brud AI
    application server -- classified by process IDENTITY
    (`backend.main:app` on the command line, launched from this repo's
    own directory), not by whether a file descriptor for the database is
    currently open.

    This is a deliberate design choice, not an oversight: direct
    `lsof`/`fuser`/`/proc/<pid>/fd` inspection of the running Phase 2.8G
    dev server found NO open file descriptor for the production database
    at any single instant, even though that exact process demonstrably
    wrote to it -- this codebase's `connect()` opens a fresh, short-lived
    SQLite connection per operation rather than holding one open, so
    fd-snapshot evidence alone would systematically under-report real
    writers with false negatives. Identity-based classification does
    not have this blind spot.

    A process whose `BRUD_DATABASE_PATH` environment variable (read from
    `/proc/<pid>/environ` where permission allows) points somewhere else
    is correctly classified as NOT a production writer, honoring the
    same environment-variable-override precedent every prior phase's
    `deploy/*/setup.py` sandbox script already relies on."""

    from backend.core.config import PROJECT_ROOT

    root = repo_root or PROJECT_ROOT
    proc_dir = Path("/proc")
    if not proc_dir.is_dir():
        return ProcessInspectionResult(
            processes=[], degraded=True,
            degraded_reason="/proc is not available in this environment -- live-writer "
            "detection could not run; this must not be read as \"no writer exists\".",
        )

    processes: list[LiveProcessInfo] = []
    unreadable_count = 0
    candidate_count = 0

    for entry in proc_dir.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        cmdline_raw = _read_proc_text(pid, "cmdline")
        if cmdline_raw is None:
            unreadable_count += 1
            continue
        candidate_count += 1
        cmdline = cmdline_raw.replace("\x00", " ").strip()
        if not cmdline:
            continue
        cwd = _read_proc_cwd(pid)

        references_asgi_target = BRUD_AI_ASGI_TARGET in cmdline
        references_repo = str(root) in cmdline or (cwd is not None and cwd.startswith(str(root)))

        if references_asgi_target and references_repo:
            classification = "brud_ai_asgi_process"
        elif references_repo:
            classification = "unrelated_process"
        else:
            # Not a Brud AI process at all (e.g. an unrelated project's
            # server, or a system service) -- correctly excluded rather
            # than flagged, per Part 6 item 4/5.
            continue

        db_override = _read_proc_environ_database_path(pid) if classification == "brud_ai_asgi_process" else None
        if classification == "brud_ai_asgi_process":
            # No readable/present override -> the process uses the real
            # Settings default, which is the production database.
            likely_writer = True if db_override is None else is_production_database_path(db_override)
        else:
            likely_writer = False

        processes.append(
            LiveProcessInfo(
                pid=pid, cmdline=cmdline, cwd=cwd, classification=classification,
                database_path_override=db_override, likely_production_writer=likely_writer,
            )
        )

    degraded = candidate_count == 0 and unreadable_count > 0
    degraded_reason = (
        "every /proc/<pid>/cmdline entry was unreadable in this environment -- live-writer "
        "detection could not confirm any process's identity; this must not be read as "
        "\"no writer exists\"."
        if degraded else None
    )
    return ProcessInspectionResult(processes=processes, degraded=degraded, degraded_reason=degraded_reason)


# -- Read-only production inspection (Part 7) --------------------------------

PRODUCTION_INSPECTION_TABLES: tuple[str, ...] = (
    "mini_brain_training_jobs",
    "mini_brain_training_checkpoints",
    "core_model_versions",
    "model_evaluation_runs",
    "model_releases",
    "production_model_activation_events",
    "mini_brain_public_chat_sessions",
    "inference_model_assignments",
)


def open_production_database_read_only() -> sqlite3.Connection:
    """Open the real production database strictly read-only, via
    SQLite's own `mode=ro` URI flag (Part 7): the OS/SQLite layer
    itself refuses any write against a `mode=ro` connection -- this is
    enforced by SQLite regardless of what the caller subsequently tries
    to execute, not merely a convention this module follows. Raises
    `ProductionDatabaseGuardError` if the production database file does
    not exist, rather than letting SQLite raise its own, less clear
    `sqlite3.OperationalError: unable to open database file`."""

    path = canonical_production_database_path()
    if not path.is_file():
        raise ProductionDatabaseGuardError(
            f"production database does not exist at {path} -- refusing to open a "
            "read-only inspection connection against a nonexistent file"
        )
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def read_only_production_snapshot(
    tables: tuple[str, ...] = PRODUCTION_INSPECTION_TABLES,
) -> dict[str, object]:
    """A minimal, read-only production inspection snapshot (Part 7):
    schema version plus the row count of every table in `tables` that
    actually exists (a missing table is reported as `None`, never
    fabricated as `0` -- "table does not exist" and "table exists and
    is empty" are different facts). Executes only `PRAGMA user_version`,
    a `sqlite_master` lookup, and `SELECT COUNT(*)` -- never anything
    capable of mutating state."""

    connection = open_production_database_read_only()
    try:
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        existing_tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        counts: dict[str, int | None] = {}
        for table in tables:
            if table not in existing_tables:
                counts[table] = None
                continue
            counts[table] = connection.execute(
                f"SELECT COUNT(*) FROM {table}"  # noqa: S608 -- table names come only from the fixed internal tuple above, never user input
            ).fetchone()[0]
        return {"schema_version": schema_version, "table_counts": counts}
    finally:
        connection.close()


# -- Qualification preflight (Part 5) -----------------------------------------


@dataclass(frozen=True)
class QualificationPreflightResult:
    database_path: Path
    is_production_database: bool
    live_production_writers: list[LiveProcessInfo]
    process_inspection_degraded: bool
    process_inspection_degraded_reason: str | None
    available_memory_bytes: int | None
    isolated_data_dir_ok: bool
    data_dir: Path
    isolated_pretraining_dir_ok: bool
    pretraining_dir: Path

    @property
    def safe_to_proceed(self) -> bool:
        """True only if every hard-blocking check passed. Deliberately
        does NOT factor in `process_inspection_degraded` -- a degraded
        (unavailable) process scan is a *limitation* to disclose, not by
        itself a reason to block a database-path-isolated qualification
        run; callers that want a stricter policy can check
        `process_inspection_degraded` themselves."""

        return (
            not self.is_production_database
            and not self.live_production_writers
            and self.isolated_data_dir_ok
            and self.isolated_pretraining_dir_ok
        )


def run_qualification_preflight(settings) -> QualificationPreflightResult:
    """A single, reusable preflight qualification phases should run
    once at their own start (Part 5) -- deliberately scoped to
    qualification *safety*, not general system health: it answers
    "is it safe to begin writable qualification with this Settings
    object right now", nothing more.

    Checks, in order:
      B/C/D. the settings' own resolved database path is not the
             production database (Invariant B);
      E/F.   no live Brud AI application process is currently capable of
             writing to the production database (Part 6), with an
             honestly-disclosed `degraded` state if process inspection
             itself was unavailable rather than a false "clear";
      I.     available system memory, measured directly (never
             estimated) via the same `/proc/meminfo`-based helper the
             real training-resource checks already use;
      J.     the settings' own data directory is not the production
             `data/` directory (guards against a qualification run that
             isolated its database path but left other artifacts —
             tokenizer corpora, checkpoints — pointed at production).
      K.     (Phase 2.8N) the settings' own `pretraining_dir` -- the
             actual MB-22 checkpoint destination -- neither is, nor is
             nested inside, nor contains, the production checkpoint
             directory. This is independent of check J:
             `allowed_data_dir` and `pretraining_dir` are two separate
             `Settings` fields with two separate environment-variable
             overrides, and a caller can isolate one while forgetting
             the other (the exact Phase 2.8M finding, reproduced
             directly before this check was added).

    Raises nothing itself: callers decide whether to proceed by
    inspecting `.safe_to_proceed` (and, for a stricter policy,
    `.process_inspection_degraded`) themselves, since only the caller
    knows whether a given qualification run can tolerate a degraded
    process scan."""

    from core_model.training.metrics import available_memory_bytes

    database_path = settings.resolved_database_path
    is_prod = is_production_database_path(database_path)

    process_result = detect_live_production_database_writers()

    data_dir = settings.resolved_allowed_data_dir
    isolated_data_dir_ok = data_dir != get_settings().resolved_allowed_data_dir

    pretraining_dir = settings.resolved_pretraining_dir
    isolated_pretraining_dir_ok = not is_production_pretraining_dir(pretraining_dir)

    return QualificationPreflightResult(
        database_path=database_path,
        is_production_database=is_prod,
        live_production_writers=process_result.production_writers,
        process_inspection_degraded=process_result.degraded,
        process_inspection_degraded_reason=process_result.degraded_reason,
        available_memory_bytes=available_memory_bytes(),
        isolated_data_dir_ok=isolated_data_dir_ok,
        data_dir=data_dir,
        isolated_pretraining_dir_ok=isolated_pretraining_dir_ok,
        pretraining_dir=pretraining_dir,
    )


def assert_qualification_is_safe_to_proceed(settings) -> QualificationPreflightResult:
    """Runs `run_qualification_preflight()` and fails closed
    (`ProductionDatabaseGuardError`) if it is not safe to proceed.
    Returns the full result on success so the caller can still record
    or report every measurement it gathered."""

    result = run_qualification_preflight(settings)
    if result.is_production_database:
        raise ProductionDatabaseGuardError(
            f"qualification preflight: database path resolves to the production database "
            f"({result.database_path}); refusing to proceed"
        )
    if result.live_production_writers:
        writer_summary = "; ".join(
            f"pid={w.pid} cmd={w.cmdline!r}" for w in result.live_production_writers
        )
        raise ProductionDatabaseGuardError(
            "qualification preflight: a live Brud AI application process is currently capable "
            f"of writing to the production database -- refusing to proceed: {writer_summary}"
        )
    if not result.isolated_data_dir_ok:
        raise ProductionDatabaseGuardError(
            f"qualification preflight: data directory ({result.data_dir}) is the production "
            "data directory; refusing to proceed"
        )
    if not result.isolated_pretraining_dir_ok:
        raise ProductionDatabaseGuardError(
            f"qualification preflight: pretraining_dir ({result.pretraining_dir}) resolves to "
            f"(or overlaps with) the production checkpoint directory "
            f"({canonical_production_pretraining_dir()}); refusing to proceed"
        )
    return result


# -- Qualification session / clean-baseline verification (Phase 2.8I, Parts 5-6) --


class ZeroMutationBaselineViolation(ProductionDatabaseGuardError):
    """Raised when the production database changed during an active
    qualification session that had claimed a zero-mutation baseline.
    Never auto-repaired, never silently swallowed -- Phase 2.8I's own
    mission is explicit that a contaminated baseline must be reported,
    not papered over."""


@dataclass(frozen=True)
class ProductionDatabaseSnapshot:
    """A point-in-time, read-only fingerprint of the production
    database: exact enough that any real mutation -- even one that
    leaves every governed table's row COUNT unchanged (Part 11: "Do not
    assume that 'no training rows changed' is sufficient") -- is still
    caught, because `size_bytes`/`mtime_ns`/`sha256` change on ANY
    write, not just ones that touch a counted table."""

    size_bytes: int
    mtime_ns: int
    sha256: str
    schema_version: int
    table_counts: dict[str, int | None]


def capture_production_database_snapshot() -> ProductionDatabaseSnapshot:
    """Read-only in every sense: stats the file (no open needed for
    size/mtime), hashes it by reading bytes (no SQLite connection at
    all for the hash, so this cannot itself perturb the file), and uses
    `open_production_database_read_only()` (`mode=ro`) for the schema
    version and table counts."""

    import hashlib

    path = canonical_production_database_path()
    stat = path.stat()
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    inspection = read_only_production_snapshot()
    return ProductionDatabaseSnapshot(
        size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=digest.hexdigest(),
        schema_version=inspection["schema_version"], table_counts=inspection["table_counts"],
    )


@dataclass
class QualificationSession:
    """The Part 5 "qualification reservation": not a lock (no other
    process is excluded -- this is a single-process environment-safety
    record, not a training-job lock, per the mission's own explicit
    instruction not to build distributed locking here), but a durable
    record of what was verified true when the session started, so its
    own end-of-session check has something concrete to compare against."""

    settings: object
    preflight: QualificationPreflightResult
    baseline_snapshot: ProductionDatabaseSnapshot
    zero_mutation_baseline_claimable: bool
    override_reason: str | None


@contextmanager
def qualification_session(
    settings, *, allow_production_writer_present: bool = False, override_reason: str | None = None,
) -> Iterator[QualificationSession]:
    """The Part 5/6 reservation + clean-baseline procedure, composed
    into one context manager:

    1. Runs the full preflight (database path, live writers, data
       directory isolation).
    2. Refuses outright (fails closed) if the database path itself is
       production, or the data directory is production's -- no override
       exists for these, they are not "an active writer might exist"
       risks, they are "this IS production" facts.
    3. If a live production writer is present, refuses UNLESS the
       caller explicitly passes `allow_production_writer_present=True`
       with a non-empty `override_reason` (Part 2 policy C/D) -- and
       even then, the resulting session is marked
       `zero_mutation_baseline_claimable=False`, so nothing downstream
       can accidentally claim a guarantee that was never actually
       verified.
    4. Captures a full before-snapshot (Part 6 items 5-7).
    5. Yields the session for the caller's own qualification work.
    6. On a clean exit (no exception raised inside the `with` block)
       AND `zero_mutation_baseline_claimable`, re-snapshots and compares
       -- raising `ZeroMutationBaselineViolation` (never silently
       passing, never repairing/hiding the difference) if the production
       database changed during the session, per Part 11's explicit
       "Do not reset/rewrite the production database to fake a clean
       result."
    """

    if allow_production_writer_present and not override_reason:
        raise ValueError("override_reason is required when allow_production_writer_present=True")

    preflight = run_qualification_preflight(settings)
    if preflight.is_production_database:
        raise ProductionDatabaseGuardError(
            f"qualification_session: database path resolves to the production database "
            f"({preflight.database_path}); refusing to establish a session"
        )
    if not preflight.isolated_data_dir_ok:
        raise ProductionDatabaseGuardError(
            f"qualification_session: data directory ({preflight.data_dir}) is the production "
            "data directory; refusing to establish a session"
        )
    if not preflight.isolated_pretraining_dir_ok:
        raise ProductionDatabaseGuardError(
            f"qualification_session: pretraining_dir ({preflight.pretraining_dir}) resolves to "
            f"(or overlaps with) the production checkpoint directory "
            f"({canonical_production_pretraining_dir()}); refusing to establish a session"
        )
    if preflight.live_production_writers and not allow_production_writer_present:
        writer_summary = "; ".join(
            f"pid={w.pid} cmd={w.cmdline!r}" for w in preflight.live_production_writers
        )
        raise ProductionDatabaseGuardError(
            "qualification_session: a live Brud AI application process is currently capable of "
            f"writing to the production database -- refusing to establish a session: {writer_summary}. "
            "Stop/reconfigure it, or explicitly pass allow_production_writer_present=True with an "
            "override_reason to proceed WITHOUT a zero-mutation baseline guarantee."
        )

    zero_mutation_baseline_claimable = not preflight.live_production_writers
    baseline = capture_production_database_snapshot()
    session = QualificationSession(
        settings=settings, preflight=preflight, baseline_snapshot=baseline,
        zero_mutation_baseline_claimable=zero_mutation_baseline_claimable, override_reason=override_reason,
    )

    yield session

    if session.zero_mutation_baseline_claimable:
        after = capture_production_database_snapshot()
        if after != baseline:
            raise ZeroMutationBaselineViolation(
                "production database changed during an active qualification session that had "
                f"claimed a zero-mutation baseline -- before={baseline} after={after}. This is not "
                "auto-repaired: investigate the cause before running any further qualification work."
            )
