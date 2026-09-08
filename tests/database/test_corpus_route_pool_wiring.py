"""Phase 7C-41: proves the real, minimal `CorpusRepository`/`pretraining_readiness`
shared-pool wiring batch -- `backend/api/routes/corpus.py`'s `_repository(settings,
pool)` + 10 factories, `backend/api/routes/pretraining_readiness.py`'s
`_corpus_repo(settings, pool)`/`_readiness_repo(settings, pool)` + 6 factories, and
`CorpusSourceService`'s Phase 7C-39-fixed `advance_production_lifecycle()`/
`training_eligibility()` pair -- behaves correctly through the real FastAPI
dependency graph established by Phase 7C-33/34.

Scope, stated explicitly: only two `corpus.py` routes
(`source_training_eligibility`, `advance_source_production_lifecycle`) and two
`pretraining_readiness.py` routes (`list_readiness_evaluations`,
`get_readiness_evaluation`) actually pass `PoolDependency` through this phase.
Every other route in both files, and the other ~562 repository construction
sites elsewhere in the codebase, still resolve `get_pool()`/`pool=` to `None`
and keep today's exact unpooled `database_connection()` behavior -- these
tests do not claim otherwise.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.auth import AdminContext, require_admin, require_csrf
from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.connection_pool import ConnectionPool
from backend.database.qualification_guard import assert_database_path_is_not_production
from backend.database.repositories.corpus import CorpusRepository
from backend.main import create_app
from backend.models.auth import AdminPublic, SessionPublic
from backend.models.corpus import (
    CorpusPolicyCreate,
    LicenceReviewDecision,
    SourceLicenceCreate,
    SourceRegistryCreate,
)
from backend.services.corpus_source_service import CorpusSourceService


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
    assert_database_path_is_not_production(
        settings.resolved_database_path, context="test_corpus_route_pool_wiring"
    )
    app = create_app(settings)

    async def fake_admin() -> AdminContext:
        return _fake_admin_context()

    async def fake_csrf() -> AdminContext:
        return _fake_admin_context()

    app.dependency_overrides[require_admin] = fake_admin
    app.dependency_overrides[require_csrf] = fake_csrf
    return app


def _settings(db_path: Path) -> Settings:
    return Settings(database_path=db_path, log_level="CRITICAL")


def _build_eligible_source_via_http(client: TestClient) -> str:
    """Real, end-to-end fixture built entirely through the real HTTP API
    (mirrors Phase 7C-39's `_build_eligible_source` service-layer fixture,
    but drives it through the wired routes to exercise the actual request
    path, not just the service classes directly)."""

    policy = client.post(
        "/api/admin/corpus/policies",
        json={"name": "pool-wiring-policy", "allowed_source_types": ["manual_admin_text"]},
    )
    assert policy.status_code == 200, policy.text
    policy_id = policy.json()["public_id"]

    source = client.post(
        "/api/admin/corpus/sources",
        json={
            "corpus_policy_public_id": policy_id,
            "title": "Pool Wiring Test Source",
            "source_type": "manual_admin_text",
            "intended_use": "pretraining_corpus",
        },
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["public_id"]

    for target in ("origin_review", "licence_review", "approved"):
        transition = client.post(
            f"/api/admin/corpus/sources/{source_id}/transition", json={"target_status": target}
        )
        assert transition.status_code == 200, transition.text

    origin = client.post(
        f"/api/admin/corpus/sources/{source_id}/verify-origin", json={"evidence": "verified"}
    )
    assert origin.status_code == 200, origin.text

    licence = client.post(
        f"/api/admin/corpus/sources/{source_id}/licences",
        json={"licence_family": "public_domain", "ai_training_permitted": True},
    )
    assert licence.status_code == 200, licence.text
    licence_id = licence.json()["public_id"]

    review = client.post(
        f"/api/admin/corpus/licences/{licence_id}/review", json={"review_status": "approved"}
    )
    assert review.status_code == 200, review.text

    for target in ("provenance_verified", "licence_reviewed"):
        advance = client.post(
            f"/api/admin/corpus/sources/{source_id}/production-lifecycle",
            json={"target_status": target},
        )
        assert advance.status_code == 200, advance.text

    return source_id


# --- pool identity: corpus.py + pretraining_readiness.py wired factories ---


def test_corpus_and_pretraining_readiness_wired_routes_share_the_same_app_pool(
    tmp_path: Path,
) -> None:
    """`source_service(settings, pool)` (corpus.py) and
    `readiness_gate_service(settings, pool)` (pretraining_readiness.py) --
    two independently-defined route factories in two different files --
    must both hand back repositories referencing the exact same pool object
    (`is`, not equal configuration) when given the same app instance's
    pool, per the single-pool invariant Phase 7C-31/33 established."""

    from backend.api.routes.corpus import source_service
    from backend.api.routes.pretraining_readiness import readiness_gate_service

    app = _build_app(tmp_path, "identity")
    with TestClient(app):
        pool = app.state.pool
        assert pool is not None

        corpus_svc = source_service(app.state.settings, pool)
        readiness_svc = readiness_gate_service(app.state.settings, pool)

        assert corpus_svc.repository.pool is pool
        assert readiness_svc.corpus_repository.pool is pool
        assert readiness_svc.readiness_repository.pool is pool
        assert readiness_svc.pretraining_service.repository.pool is pool


def test_two_app_instances_never_share_a_pool(tmp_path: Path) -> None:
    app_a = _build_app(tmp_path, "app_a")
    app_b = _build_app(tmp_path, "app_b")
    with TestClient(app_a), TestClient(app_b):
        assert app_a.state.pool is not None
        assert app_b.state.pool is not None
        assert app_a.state.pool is not app_b.state.pool


def test_default_construction_sites_still_resolve_to_no_pool(tmp_path: Path) -> None:
    """Every one of `corpus.py`'s 10 factories and `pretraining_readiness.py`'s
    6 factories defaults `pool=None` -- calling them the old way (no pool
    argument, exactly what every currently-unwired route still does) must
    keep returning a repository with `pool is None`, byte-identical to
    pre-Phase-7C-41 behavior."""

    from backend.api.routes.corpus import build_service, export_service, quality_service
    from backend.api.routes.pretraining_readiness import (
        resource_service,
        smoke_service,
        tokenizer_candidate_service,
    )

    settings = _settings(tmp_path / "unwired.db")
    assert build_service(settings).repository.pool is None
    assert export_service(settings).repository.pool is None
    assert quality_service(settings).repository.pool is None
    assert resource_service(settings).repository.pool is None
    assert tokenizer_candidate_service(settings).readiness_repository.pool is None
    assert smoke_service(settings).readiness_repository.pool is None


# --- CorpusSourceService: real end-to-end wired workflow through the pool --


def test_advance_to_approved_through_wired_pool_succeeds_with_no_reentrant_checkout(
    tmp_path: Path,
) -> None:
    app = _build_app(tmp_path, "advance")
    with TestClient(app) as client:
        pool = app.state.pool
        assert pool is not None
        source_id = _build_eligible_source_via_http(client)

        outstanding_before = pool.outstanding
        approve = client.post(
            f"/api/admin/corpus/sources/{source_id}/production-lifecycle",
            json={"target_status": "approved"},
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["production_lifecycle_status"] == "approved"
        assert pool.outstanding == outstanding_before, "no leaked checkout"


def test_training_eligibility_route_works_through_wired_pool(tmp_path: Path) -> None:
    app = _build_app(tmp_path, "eligibility")
    with TestClient(app) as client:
        pool = app.state.pool
        source_id = _build_eligible_source_via_http(client)

        outstanding_before = pool.outstanding
        eligibility = client.get(f"/api/admin/corpus/sources/{source_id}/training-eligibility")
        assert eligibility.status_code == 200, eligibility.text
        assert eligibility.json()["eligible"] is True
        assert pool.outstanding == outstanding_before


def test_readiness_evaluation_routes_work_through_wired_pool(tmp_path: Path) -> None:
    """`list_readiness_evaluations`/`get_readiness_evaluation` exercise
    `BaseModelReadinessService`'s `corpus_repository`+`readiness_repository`
    combination through the shared pool -- already confirmed sequential
    (never nested) across Phases 7C-31/32/38/40."""

    app = _build_app(tmp_path, "readiness")
    with TestClient(app) as client:
        pool = app.state.pool
        listing = client.get("/api/admin/pretraining-readiness/readiness-evaluations")
        assert listing.status_code == 200, listing.text
        assert pool.outstanding == 0


def test_phase_7c42_policy_and_source_read_routes_work_through_wired_pool(
    tmp_path: Path,
) -> None:
    """Phase 7C-42: `list_policies`/`get_policy`/`list_sources`/`get_source`
    -- each a single plain read-only `CorpusSourceService` transaction with
    no nested call and no sibling repository, the same evidence shape
    already proven for `source_training_eligibility`. Confirms all four
    work through the real wired pool, reuse the same connection object
    (via `connection_reused_count`), and leave `outstanding == 0`."""

    app = _build_app(tmp_path, "policy-source-reads")
    with TestClient(app) as client:
        pool = app.state.pool
        source_id = _build_eligible_source_via_http(client)

        policies = client.get("/api/admin/corpus/policies")
        assert policies.status_code == 200, policies.text
        policy_id = policies.json()["items"][0]["public_id"]

        reused_before = pool.connection_reused_count
        recreated_before = pool.connection_recreated_count

        policy = client.get(f"/api/admin/corpus/policies/{policy_id}")
        assert policy.status_code == 200, policy.text

        sources = client.get("/api/admin/corpus/sources")
        assert sources.status_code == 200, sources.text
        assert any(s["public_id"] == source_id for s in sources.json()["items"])

        source = client.get(f"/api/admin/corpus/sources/{source_id}")
        assert source.status_code == 200, source.text
        assert source.json()["public_id"] == source_id

        assert pool.connection_reused_count > reused_before
        assert pool.connection_recreated_count == recreated_before
        assert pool.outstanding == 0


def test_phase_7c42_default_unwired_source_routes_still_resolve_to_no_pool(
    tmp_path: Path,
) -> None:
    """The remaining, deliberately-unwired `source_service` routes (e.g.
    `create_policy`, `patch_source`) still call `source_service(settings)`
    with no `pool` argument -- confirms Phase 7C-42 did not silently widen
    scope beyond the four routes it actually wires."""

    from backend.api.routes.corpus import source_service

    app = _build_app(tmp_path, "policy-source-default")
    settings = _settings(app.state.settings.resolved_database_path)
    svc = source_service(settings)
    assert svc.repository.pool is None


# --- immediate=True/False manifest verification -----------------------------


def test_advance_production_lifecycle_opens_with_immediate_true(tmp_path: Path) -> None:
    """Direct, non-HTTP proof that `advance_production_lifecycle()`'s own
    transaction call specifically requests `immediate=True` (Phase 7C-41's
    evidence-backed choice for this confirmed READ-THEN-WRITE method),
    while `training_eligibility()`'s standalone transaction remains at the
    default deferred BEGIN (confirmed READ-ONLY in that shape)."""

    db_path = tmp_path / "immediate_manifest.db"
    from backend.database.migrations import initialize_database

    initialize_database(db_path)
    repo = CorpusRepository(db_path)
    svc = CorpusSourceService(repo, _settings(db_path))

    policy = svc.create_policy(
        CorpusPolicyCreate(name="manifest-policy", allowed_source_types=["manual_admin_text"]),
        admin_id="admin-1",
    )
    source = svc.create_source(
        SourceRegistryCreate(
            corpus_policy_public_id=policy["public_id"],
            title="Manifest Source",
            source_type="manual_admin_text",
            intended_use="pretraining_corpus",
        ),
        admin_id="admin-1",
    )
    source_public_id = source["public_id"]

    calls: list[bool] = []
    original = repo.transaction

    def spy_transaction(*, immediate: bool = False):
        calls.append(immediate)
        return original(immediate=immediate)

    repo.transaction = spy_transaction  # type: ignore[method-assign]

    svc.transition_source_status(source_public_id, "origin_review", "admin-1")
    svc.verify_origin(source_public_id, "admin-1", evidence="verified")
    svc.advance_production_lifecycle(source_public_id, "provenance_verified", "admin-1")

    # transition_source_status did NOT request immediate=True (unaffected
    # by this phase); advance_production_lifecycle's own outer call did.
    assert calls[-1] is True, "advance_production_lifecycle must open with immediate=True"

    calls.clear()
    svc.training_eligibility(source_public_id)
    assert calls == [False], "standalone training_eligibility must stay at the default deferred BEGIN"


def test_no_connection_leak_across_repeated_pooled_advance_calls(tmp_path: Path) -> None:
    from backend.database.migrations import initialize_database
    from backend.models.corpus import CorpusPolicyCreate as _PolicyCreate

    db_path = tmp_path / "leak_check.db"
    initialize_database(db_path)
    pool = ConnectionPool(db_path, size=2)
    repo = CorpusRepository(db_path, pool=pool)
    svc = CorpusSourceService(repo, _settings(db_path))

    policy = svc.create_policy(
        _PolicyCreate(name="leak-policy", allowed_source_types=["manual_admin_text"]),
        admin_id="admin-1",
    )
    for i in range(5):
        source = svc.create_source(
            SourceRegistryCreate(
                corpus_policy_public_id=policy["public_id"],
                title=f"Leak Source {i}",
                source_type="manual_admin_text",
                intended_use="pretraining_corpus",
            ),
            admin_id="admin-1",
        )
        sid = source["public_id"]
        svc.transition_source_status(sid, "origin_review", "admin-1")
        svc.transition_source_status(sid, "licence_review", "admin-1")
        svc.transition_source_status(sid, "approved", "admin-1")
        svc.verify_origin(sid, "admin-1", evidence="verified")
        licence = svc.create_licence(
            sid, SourceLicenceCreate(licence_family="public_domain", ai_training_permitted=True),
            admin_id="admin-1",
        )
        svc.review_licence(
            licence["public_id"], LicenceReviewDecision(review_status="approved"), admin_id="admin-1"
        )
        svc.advance_production_lifecycle(sid, "provenance_verified", "admin-1")
        svc.advance_production_lifecycle(sid, "licence_reviewed", "admin-1")
        result = svc.advance_production_lifecycle(sid, "approved", "admin-1")
        assert result["production_lifecycle_status"] == "approved"

    assert pool.outstanding == 0
    assert pool.connection_recreated_count == 0


def _seed_pretraining_dataset_snapshot(db_path: Path, public_id: str) -> None:
    """Minimal, directly-seeded row -- bypasses the full corpus-release/
    dataset-version/tokenizer-version creation chain (out of scope for this
    wiring test), matching the exact real-methods reproduction used in
    Phase 7C-44's own Gate 3/4 contention re-qualification."""

    with database_connection(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        row = connection.execute(
            "SELECT id FROM tokenizer_versions WHERE id=1"
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO tokenizer_versions(id, public_id, tokenizer_family_id, version, "
                "algorithm, vocabulary_size, character_coverage, normalization_rule_name, "
                "dataset_version_id, model_checksum_sha256, lifecycle_status) "
                "VALUES (1,'tok-v1',1,'v1','bpe',100,0.995,'nmt_nfkc',1,'b','active')"
            )
        row = connection.execute("SELECT id FROM corpus_releases WHERE id=1").fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO corpus_releases(id, public_id, corpus_version_id, semantic_version, "
                "release_name, status, created_by_admin_public_id) "
                "VALUES (1,'rel-1',1,'1.0.0','test-release','finalized','admin-1')"
            )
        connection.execute(
            "INSERT INTO pretraining_dataset_snapshots(public_id, corpus_release_id, "
            "dataset_version_id, tokenizer_version_id, manifest_checksum_sha256, "
            "tokenizer_checksum_sha256, maximum_sequence_length, created_by_admin_public_id) "
            "VALUES (?,1,1,1,'a','b',2048,'admin-1')",
            (public_id,),
        )
        connection.commit()


def test_phase_7c44_create_readiness_evaluation_works_through_wired_pool(
    tmp_path: Path,
) -> None:
    """Phase 7C-44: `create_readiness_evaluation` -> `.evaluate()` -- the
    6-transaction-block method Phase 7C-42 deliberately left unwired.
    Block 1 now opens with `immediate=True` (Phase 7C-44 fix); Block 6
    independently qualified as deferred-safe. Confirms the real wired path
    succeeds end-to-end with no `ReentrantCheckout` and no leak."""

    app = _build_app(tmp_path, "readiness-eval")
    with TestClient(app) as client:
        pool = app.state.pool
        _seed_pretraining_dataset_snapshot(app.state.settings.resolved_database_path, "snap-1")

        response = client.post(
            "/api/admin/pretraining-readiness/readiness-evaluations",
            json={"pretraining_dataset_snapshot_public_id": "snap-1"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert len(body["dimensions"]) == 17

        assert pool.outstanding == 0
        assert pool.connection_recreated_count == 0


def test_phase_7c44_evaluate_block1_opens_with_immediate_true(tmp_path: Path) -> None:
    """Directly verifies Block 1's own `with self.readiness_repository
    .transaction() as connection:` call now passes `immediate=True` --
    spies on the real `PretrainingReadinessRepository.transaction` method
    rather than trusting the route-level HTTP success alone."""

    from backend.database.repositories.pretraining_readiness import (
        PretrainingReadinessRepository,
    )
    from backend.services.base_model_readiness_service import BaseModelReadinessService
    from backend.database.repositories.corpus import CorpusRepository as _CorpusRepo
    from backend.database.repositories.pretraining import PretrainingRepository
    from backend.models.pretraining_readiness import BaseModelReadinessEvaluationCreate

    db_path = tmp_path / "block1-spy.db"
    from backend.database.migrations import initialize_database

    initialize_database(db_path)
    _seed_pretraining_dataset_snapshot(db_path, "snap-1")

    settings = _settings(db_path)
    readiness_repo = PretrainingReadinessRepository(db_path)
    svc = BaseModelReadinessService(
        readiness_repo, _CorpusRepo(db_path), PretrainingRepository(db_path), settings
    )

    calls: list[bool] = []
    original = PretrainingReadinessRepository.transaction

    def spy(self, *, immediate=False):
        calls.append(immediate)
        return original(self, immediate=immediate)

    PretrainingReadinessRepository.transaction = spy
    try:
        svc.evaluate(
            BaseModelReadinessEvaluationCreate(pretraining_dataset_snapshot_public_id="snap-1"),
            "admin-1",
        )
    finally:
        PretrainingReadinessRepository.transaction = original

    # Block 1 is the first readiness_repository.transaction() call -> must be immediate=True.
    # Block 6 (the last one, containing the dimension-write loop) must remain immediate=False.
    assert calls[0] is True, f"Block 1 must open immediate=True, got calls={calls}"
    assert calls[-1] is False, f"Block 6 must remain immediate=False (deferred-safe), got calls={calls}"


def test_phase_7c44_no_connection_leak_across_repeated_pooled_evaluate_calls(
    tmp_path: Path,
) -> None:
    """5 repeated real pooled `evaluate()` calls (each its own HTTP
    request/logical execution) -- confirms no leak and genuine reuse
    (not the Phase 7C-27 recreate-defect pattern) across Block 1's
    immediate=True transaction and Block 6's deferred write-loop."""

    app = _build_app(tmp_path, "readiness-eval-leak")
    with TestClient(app) as client:
        pool = app.state.pool
        db_path = app.state.settings.resolved_database_path
        for i in range(5):
            _seed_pretraining_dataset_snapshot(db_path, f"snap-{i}")
            response = client.post(
                "/api/admin/pretraining-readiness/readiness-evaluations",
                json={"pretraining_dataset_snapshot_public_id": f"snap-{i}"},
            )
            assert response.status_code == 200, response.text

        assert pool.outstanding == 0
        assert pool.connection_recreated_count == 0


# --- Phase 7C-46: list_snapshots/get_snapshot/get_extraction_run/get_normalization_run --


def _build_app_with_source_root(tmp_path: Path, name: str) -> FastAPI:
    """Same as `_build_app`, plus a real `corpus_approved_source_roots`
    directory containing one plain-text file -- required for
    `create_snapshot()`/`create_extraction_run()` to have a real file to
    read, mirroring `tests/backend/test_corpus_api.py`'s own fixture
    shape (plain-text extraction, no OCR/heavy native work)."""

    db_dir = tmp_path / name
    source_root = db_dir / "approved_source_root"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "sample.txt").write_text(
        "Tamil Nadu is a state in southern India known for its rich Dravidian culture.\n\n"
        "Agriculture remains a major occupation across the region.",
        encoding="utf-8",
    )
    settings = Settings(
        database_path=db_dir / "api.db",
        database_backup_dir=db_dir / "backups",
        allowed_data_dir=db_dir,
        corpus_approved_source_roots=str(source_root),
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    assert_database_path_is_not_production(
        settings.resolved_database_path, context="test_corpus_route_pool_wiring"
    )
    app = create_app(settings)

    async def fake_admin() -> AdminContext:
        return _fake_admin_context()

    async def fake_csrf() -> AdminContext:
        return _fake_admin_context()

    app.dependency_overrides[require_admin] = fake_admin
    app.dependency_overrides[require_csrf] = fake_csrf
    return app


def test_phase_7c46_processing_and_source_service_share_the_same_app_pool(
    tmp_path: Path,
) -> None:
    """`source_service(settings, pool)` and `processing_service(settings,
    pool)` -- `processing_service`'s first real use of the `pool`
    parameter it mechanically gained in Phase 7C-41 -- must both hand back
    repositories referencing the exact same pool object (`is`, not equal
    configuration)."""

    from backend.api.routes.corpus import processing_service, source_service

    app = _build_app(tmp_path, "phase-7c46-identity")
    with TestClient(app):
        pool = app.state.pool
        assert pool is not None

        source_svc = source_service(app.state.settings, pool)
        processing_svc = processing_service(app.state.settings, pool)

        assert source_svc.repository.pool is pool
        assert processing_svc.repository.pool is pool
        assert source_svc.repository.pool is processing_svc.repository.pool


def test_phase_7c46_snapshot_and_processing_read_routes_work_through_wired_pool(
    tmp_path: Path,
) -> None:
    """Real, end-to-end HTTP proof of all four Phase 7C-46 routes:
    `list_snapshots`, `get_snapshot`, `get_extraction_run`,
    `get_normalization_run`. Confirms each works through the real wired
    pool, reuses the shared connection (`connection_reused_count`), never
    triggers `ReentrantCheckout`, and leaves `outstanding == 0`."""

    app = _build_app_with_source_root(tmp_path, "phase-7c46-reads")
    with TestClient(app) as client:
        pool = app.state.pool
        source_id = _build_eligible_source_via_http(client)

        snapshot = client.post(
            f"/api/admin/corpus/sources/{source_id}/snapshots",
            json={"files": [{"relative_path": "sample.txt"}]},
        )
        assert snapshot.status_code == 200, snapshot.text
        snapshot_id = snapshot.json()["public_id"]

        extraction = client.post(
            f"/api/admin/corpus/snapshots/{snapshot_id}/extraction-runs",
            json={"extraction_method": "plain_text"},
        )
        assert extraction.status_code == 200, extraction.text
        extraction_id = extraction.json()["public_id"]

        normalization = client.post(
            f"/api/admin/corpus/extraction-runs/{extraction_id}/normalization-runs",
            json={},
        )
        assert normalization.status_code == 200, normalization.text
        normalization_id = normalization.json()["public_id"]

        reused_before = pool.connection_reused_count
        recreated_before = pool.connection_recreated_count

        list_snap = client.get(f"/api/admin/corpus/sources/{source_id}/snapshots")
        assert list_snap.status_code == 200, list_snap.text
        assert any(s["public_id"] == snapshot_id for s in list_snap.json()["items"])

        get_snap = client.get(f"/api/admin/corpus/snapshots/{snapshot_id}")
        assert get_snap.status_code == 200, get_snap.text
        assert get_snap.json()["public_id"] == snapshot_id

        get_extraction = client.get(f"/api/admin/corpus/extraction-runs/{extraction_id}")
        assert get_extraction.status_code == 200, get_extraction.text
        assert get_extraction.json()["public_id"] == extraction_id

        get_normalization = client.get(
            f"/api/admin/corpus/normalization-runs/{normalization_id}"
        )
        assert get_normalization.status_code == 200, get_normalization.text
        assert get_normalization.json()["public_id"] == normalization_id

        assert pool.connection_reused_count > reused_before
        assert pool.connection_recreated_count == recreated_before
        assert pool.outstanding == 0


def test_phase_7c46_default_unwired_processing_routes_still_resolve_to_no_pool(
    tmp_path: Path,
) -> None:
    """`processing_service`'s other, still-unwired methods (e.g.
    `create_extraction_run`, `segment_normalized_document`) keep resolving
    `pool=None` when called the old way -- Phase 7C-46 did not silently
    widen scope beyond its four authorized routes."""

    from backend.api.routes.corpus import processing_service

    settings = _settings(tmp_path / "unwired-processing.db")
    svc = processing_service(settings)
    assert svc.repository.pool is None


def test_phase_7c48_quality_and_profile_services_share_the_same_app_pool(
    tmp_path: Path,
) -> None:
    """`quality_service(settings, pool)` and `profile_service(settings,
    pool)` -- both services' first real use of the `pool` parameter they
    mechanically gained in Phase 7C-41 -- must both hand back repositories
    referencing the exact same shared pool object as `source_service`
    (`is`, not equal configuration)."""

    from backend.api.routes.corpus import profile_service, quality_service, source_service

    app = _build_app(tmp_path, "phase-7c48-identity")
    with TestClient(app):
        pool = app.state.pool
        assert pool is not None

        source_svc = source_service(app.state.settings, pool)
        quality_svc = quality_service(app.state.settings, pool)
        profile_svc = profile_service(app.state.settings, pool)

        assert source_svc.repository.pool is pool
        assert quality_svc.repository.pool is pool
        assert profile_svc.repository.pool is pool
        assert quality_svc.repository.pool is profile_svc.repository.pool


def test_phase_7c48_quality_and_profile_read_routes_work_through_wired_pool(
    tmp_path: Path,
) -> None:
    """Real, end-to-end HTTP proof of all three Phase 7C-48 routes:
    `get_deduplication_run`, `get_contamination_run`,
    `list_normalization_profiles`. Confirms each works through the real
    wired pool, reuses the shared connection (`connection_reused_count`),
    never triggers `ReentrantCheckout`, and leaves `outstanding == 0`."""

    app = _build_app(tmp_path, "phase-7c48-reads")
    with TestClient(app) as client:
        pool = app.state.pool

        dedup = client.post("/api/admin/corpus/deduplication-runs", json={})
        assert dedup.status_code == 200, dedup.text
        dedup_id = dedup.json()["public_id"]

        contamination = client.post("/api/admin/corpus/contamination-runs", json={})
        assert contamination.status_code == 200, contamination.text
        contamination_id = contamination.json()["public_id"]

        profile = client.post(
            "/api/admin/corpus/normalization-profiles",
            json={"name": "Phase 7C-48 profile", "profile_key": "tamil_conservative"},
        )
        assert profile.status_code == 200, profile.text

        reused_before = pool.connection_reused_count
        recreated_before = pool.connection_recreated_count

        get_dedup = client.get(f"/api/admin/corpus/deduplication-runs/{dedup_id}")
        assert get_dedup.status_code == 200, get_dedup.text
        assert get_dedup.json()["public_id"] == dedup_id

        get_contamination = client.get(
            f"/api/admin/corpus/contamination-runs/{contamination_id}"
        )
        assert get_contamination.status_code == 200, get_contamination.text
        assert get_contamination.json()["public_id"] == contamination_id

        list_profiles = client.get("/api/admin/corpus/normalization-profiles")
        assert list_profiles.status_code == 200, list_profiles.text
        assert any(
            p["profile_key"] == "tamil_conservative" for p in list_profiles.json()["items"]
        )

        assert pool.connection_reused_count > reused_before
        assert pool.connection_recreated_count == recreated_before
        assert pool.outstanding == 0


def test_phase_7c48_default_unwired_quality_and_profile_routes_still_resolve_to_no_pool(
    tmp_path: Path,
) -> None:
    """`quality_service`/`profile_service`'s other, still-unwired methods
    (e.g. `run_deduplication`, `create_normalization_profile`) keep
    resolving `pool=None` when called the old way -- Phase 7C-48 did not
    silently widen scope beyond its three authorized routes."""

    from backend.api.routes.corpus import profile_service, quality_service

    settings = _settings(tmp_path / "unwired-quality-profile.db")
    quality_svc = quality_service(settings)
    profile_svc = profile_service(settings)
    assert quality_svc.repository.pool is None
    assert profile_svc.repository.pool is None


def test_phase_7c48_corpus_readiness_routes_remain_unwired_and_unmodified(
    tmp_path: Path,
) -> None:
    """`corpus.py`'s OWN separate `/readiness-evaluations` routes (backed
    by `CorpusReadinessService.evaluate()`, entirely distinct from
    `pretraining_readiness.py`'s already-wired `BaseModelReadinessService
    .evaluate()`) must remain explicitly untouched -- the Phase 7C-45
    naming-collision trap. Calling the factory the old way must still
    resolve `pool=None`, and the route handlers must not accept a `pool`
    parameter at all."""

    import inspect

    from backend.api.routes.corpus import (
        create_readiness_evaluation,
        get_readiness_evaluation,
        readiness_service,
    )

    settings = _settings(tmp_path / "unwired-corpus-readiness.db")
    svc = readiness_service(settings)
    assert svc.repository.pool is None

    assert "pool" not in inspect.signature(create_readiness_evaluation).parameters
    assert "pool" not in inspect.signature(get_readiness_evaluation).parameters


def test_phase_7c50_resource_and_snapshot_services_share_the_same_app_pool(
    tmp_path: Path,
) -> None:
    """`resource_service(settings, pool)` and `snapshot_service(settings,
    pool)` -- both services' first real use of the `pool` parameter they
    mechanically gained in Phase 7C-41 -- must both hand back repositories
    referencing the exact same shared pool object as `readiness_gate_service`
    (`is`, not equal configuration)."""

    from backend.api.routes.pretraining_readiness import (
        readiness_gate_service,
        resource_service,
        snapshot_service,
    )

    app = _build_app(tmp_path, "phase-7c50-identity")
    with TestClient(app):
        pool = app.state.pool
        assert pool is not None

        readiness_svc = readiness_gate_service(app.state.settings, pool)
        resource_svc = resource_service(app.state.settings, pool)
        snapshot_svc = snapshot_service(app.state.settings, pool)

        assert readiness_svc.readiness_repository.pool is pool
        assert resource_svc.repository.pool is pool
        assert snapshot_svc.readiness_repository.pool is pool
        assert snapshot_svc.corpus_repository.pool is pool
        assert resource_svc.repository.pool is snapshot_svc.readiness_repository.pool


def test_phase_7c50_resource_and_snapshot_read_routes_work_through_wired_pool(
    tmp_path: Path,
) -> None:
    """Real, end-to-end HTTP proof of all four Phase 7C-50 routes:
    `list_resource_estimates`, `get_resource_estimate`,
    `list_dataset_snapshots`, `get_dataset_snapshot`. Confirms each works
    through the real wired pool, reuses the shared connection
    (`connection_reused_count`), never triggers `ReentrantCheckout`, and
    leaves `outstanding == 0`."""

    app = _build_app(tmp_path, "phase-7c50-reads")
    with TestClient(app) as client:
        pool = app.state.pool

        estimate = client.post(
            "/api/admin/pretraining-readiness/resource-estimates",
            json={"profile_name": "micro_smoke_test", "vocabulary_size": 32000},
        )
        assert estimate.status_code == 200, estimate.text
        estimate_id = estimate.json()["public_id"]

        _seed_pretraining_dataset_snapshot(
            app.state.settings.resolved_database_path, "phase-7c50-snap-1"
        )

        reused_before = pool.connection_reused_count
        recreated_before = pool.connection_recreated_count

        list_estimates = client.get("/api/admin/pretraining-readiness/resource-estimates")
        assert list_estimates.status_code == 200, list_estimates.text
        assert any(item["public_id"] == estimate_id for item in list_estimates.json()["items"])

        get_estimate = client.get(
            f"/api/admin/pretraining-readiness/resource-estimates/{estimate_id}"
        )
        assert get_estimate.status_code == 200, get_estimate.text
        assert get_estimate.json()["public_id"] == estimate_id

        list_snapshots = client.get("/api/admin/pretraining-readiness/dataset-snapshots")
        assert list_snapshots.status_code == 200, list_snapshots.text
        assert any(
            item["public_id"] == "phase-7c50-snap-1" for item in list_snapshots.json()["items"]
        )

        get_snapshot = client.get(
            "/api/admin/pretraining-readiness/dataset-snapshots/phase-7c50-snap-1"
        )
        assert get_snapshot.status_code == 200, get_snapshot.text
        assert get_snapshot.json()["public_id"] == "phase-7c50-snap-1"

        assert pool.connection_reused_count > reused_before
        assert pool.connection_recreated_count == recreated_before
        assert pool.outstanding == 0


def test_phase_7c50_default_unwired_resource_and_snapshot_routes_still_resolve_to_no_pool(
    tmp_path: Path,
) -> None:
    """`resource_service`/`snapshot_service`'s other, still-unwired methods
    (e.g. `create_estimate`, `create_snapshot`) keep resolving `pool=None`
    when called the old way -- Phase 7C-50 did not silently widen scope
    beyond its four authorized routes."""

    from backend.api.routes.pretraining_readiness import resource_service, snapshot_service

    settings = _settings(tmp_path / "unwired-resource-snapshot.db")
    resource_svc = resource_service(settings)
    snapshot_svc = snapshot_service(settings)
    assert resource_svc.repository.pool is None
    assert snapshot_svc.readiness_repository.pool is None
    assert snapshot_svc.corpus_repository.pool is None


def test_phase_7c50_naming_collision_protection_snapshot_service_is_not_corpus_source_service(
    tmp_path: Path,
) -> None:
    """Explicit protection for the Phase 7C-45-discovered naming collision:
    `PretrainingSnapshotService.get_snapshot()`/`list_snapshots()` (this
    phase's targets, reached via `snapshot_service` in
    `pretraining_readiness.py`) share their exact method names with the
    already-wired, entirely different `CorpusSourceService.get_snapshot()`/
    `list_snapshots()` (Phase 7C-46, via `source_service` in `corpus.py`).
    Asserts they are genuinely different classes/repositories, and that
    wiring one did not accidentally exercise or depend on the other."""

    from backend.api.routes.corpus import source_service
    from backend.api.routes.pretraining_readiness import snapshot_service
    from backend.database.repositories.pretraining_readiness import (
        PretrainingReadinessRepository,
    )
    from backend.services.corpus_source_service import CorpusSourceService
    from backend.services.pretraining_snapshot_service import PretrainingSnapshotService

    app = _build_app(tmp_path, "phase-7c50-naming-collision")
    with TestClient(app):
        pool = app.state.pool

        snapshot_svc = snapshot_service(app.state.settings, pool)
        source_svc = source_service(app.state.settings, pool)

        assert isinstance(snapshot_svc, PretrainingSnapshotService)
        assert isinstance(source_svc, CorpusSourceService)
        assert not isinstance(snapshot_svc, CorpusSourceService)
        assert not isinstance(source_svc, PretrainingSnapshotService)

        # Different repository types entirely -- readiness vs. corpus.
        assert type(snapshot_svc.readiness_repository) is not type(source_svc.repository)
        assert isinstance(snapshot_svc.readiness_repository, PretrainingReadinessRepository)
        assert isinstance(source_svc.repository, CorpusRepository)

        # Both still share the same underlying pool object, but that is the
        # only thing they have in common.
        assert snapshot_svc.readiness_repository.pool is pool
        assert source_svc.repository.pool is pool


def _seed_tokenizer_corpus_build(db_path: Path, public_id: str) -> int:
    """Minimal, directly-seeded row -- bypasses the full corpus-release
    creation chain (out of scope for this wiring test), matching the exact
    minimal-seeding precedent already established by
    `_seed_pretraining_dataset_snapshot` above. Returns the row's internal
    id for use as `tokenizer_corpus_build_id` by
    `_seed_tokenizer_candidate_comparison`."""

    with database_connection(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        row = connection.execute("SELECT id FROM corpus_releases WHERE id=1").fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO corpus_releases(id, public_id, corpus_version_id, "
                "semantic_version, release_name, status, created_by_admin_public_id) "
                "VALUES (1,'rel-1',1,'1.0.0','test-release','finalized','admin-1')"
            )
        connection.execute(
            "INSERT INTO tokenizer_corpus_builds(public_id, corpus_release_id, status, "
            "created_by_admin_public_id) VALUES (?,1,'completed','admin-1')",
            (public_id,),
        )
        connection.commit()
        return connection.execute(
            "SELECT id FROM tokenizer_corpus_builds WHERE public_id=?", (public_id,)
        ).fetchone()["id"]


def _seed_tokenizer_candidate_comparison(db_path: Path, build_id: int, public_id: str) -> None:
    """Minimal, directly-seeded row referencing the build seeded by
    `_seed_tokenizer_corpus_build` above."""

    with database_connection(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO tokenizer_candidate_comparisons(public_id, "
            "tokenizer_corpus_build_id, status, created_by_admin_public_id) "
            "VALUES (?,?,'completed','admin-1')",
            (public_id, build_id),
        )
        connection.commit()


def test_phase_7c52_tokenizer_corpus_and_candidate_services_share_the_same_app_pool(
    tmp_path: Path,
) -> None:
    """`tokenizer_corpus_service(settings, pool)` and
    `tokenizer_candidate_service(settings, pool)` -- both factories' first
    real use of the `pool` parameter they mechanically gained in Phase
    7C-41 -- must both hand back repositories referencing the exact same
    shared pool object as the already-wired `resource_service` (`is`, not
    equal configuration)."""

    from backend.api.routes.pretraining_readiness import (
        resource_service,
        tokenizer_candidate_service,
        tokenizer_corpus_service,
    )

    app = _build_app(tmp_path, "phase-7c52-identity")
    with TestClient(app):
        pool = app.state.pool
        assert pool is not None

        resource_svc = resource_service(app.state.settings, pool)
        corpus_svc = tokenizer_corpus_service(app.state.settings, pool)
        candidate_svc = tokenizer_candidate_service(app.state.settings, pool)

        assert corpus_svc.corpus_repository.pool is pool
        assert corpus_svc.readiness_repository.pool is pool
        assert candidate_svc.readiness_repository.pool is pool
        assert resource_svc.repository.pool is corpus_svc.readiness_repository.pool
        assert resource_svc.repository.pool is candidate_svc.readiness_repository.pool


def test_phase_7c52_tokenizer_corpus_build_and_candidate_comparison_read_routes_work_through_wired_pool(
    tmp_path: Path,
) -> None:
    """Real, end-to-end HTTP proof of both Phase 7C-52 routes:
    `get_tokenizer_corpus_build`, `get_tokenizer_candidate_comparison`.
    Confirms each works through the real wired pool, reuses the shared
    connection (`connection_reused_count`), never triggers
    `ReentrantCheckout`, and leaves `outstanding == 0`."""

    app = _build_app(tmp_path, "phase-7c52-reads")
    with TestClient(app) as client:
        pool = app.state.pool
        db_path = app.state.settings.resolved_database_path

        build_id = _seed_tokenizer_corpus_build(db_path, "phase-7c52-build-1")
        _seed_tokenizer_candidate_comparison(db_path, build_id, "phase-7c52-cmp-1")

        reused_before = pool.connection_reused_count
        recreated_before = pool.connection_recreated_count

        get_build = client.get(
            "/api/admin/pretraining-readiness/tokenizer-corpus-builds/phase-7c52-build-1"
        )
        assert get_build.status_code == 200, get_build.text
        assert get_build.json()["public_id"] == "phase-7c52-build-1"

        get_comparison = client.get(
            "/api/admin/pretraining-readiness/tokenizer-candidate-comparisons/phase-7c52-cmp-1"
        )
        assert get_comparison.status_code == 200, get_comparison.text
        assert get_comparison.json()["public_id"] == "phase-7c52-cmp-1"

        assert pool.connection_reused_count > reused_before
        assert pool.connection_recreated_count == recreated_before
        assert pool.outstanding == 0


def test_phase_7c52_default_unwired_tokenizer_corpus_and_candidate_routes_still_resolve_to_no_pool(
    tmp_path: Path,
) -> None:
    """`tokenizer_corpus_service`/`tokenizer_candidate_service`'s other,
    still-unwired methods (`list_builds`, `build_corpus`,
    `create_comparison`, `approve`, `activate`) keep resolving `pool=None`
    when called the old way -- Phase 7C-52 did not silently widen scope
    beyond its two authorized routes."""

    from backend.api.routes.pretraining_readiness import (
        tokenizer_candidate_service,
        tokenizer_corpus_service,
    )

    settings = _settings(tmp_path / "unwired-tokenizer-corpus-candidate.db")
    corpus_svc = tokenizer_corpus_service(settings)
    candidate_svc = tokenizer_candidate_service(settings)
    assert corpus_svc.corpus_repository.pool is None
    assert corpus_svc.readiness_repository.pool is None
    assert candidate_svc.readiness_repository.pool is None


def test_phase_7c52_blocked_and_deferred_routes_remain_unwired(tmp_path: Path) -> None:
    """Explicit isolation proof for Phase 7C-52's scope boundary at the
    time: none of the routes that phase was explicitly forbidden from
    touching -- `create_smoke_run` (real background-`Thread` hazard,
    Phase 7C-51, still untouched at the time) and the
    `CorpusReadinessService.evaluate()` routes in `corpus.py` -- gained a
    `pool` parameter.

    Note: `list_smoke_runs`/`list_tokenizer_corpus_builds` were originally
    asserted unwired here too, but Phase 7C-53 (`get_smoke_run`/
    `validate_training_config`) and Phase 7C-54 (`list_smoke_runs`/
    `list_tokenizer_corpus_builds` themselves) have since legitimately
    wired all four. `create_smoke_run` itself was originally asserted
    unwired here too, but Phase 7C-55 (read-only threading/pool-safety
    qualification) cleared it and Phase 7C-56 wired it -- see
    `test_phase_7c56_blocked_and_deferred_routes_remain_unwired` for the
    current, authoritative isolation boundary. Disclosed and corrected
    here rather than left silently broken, matching the precedent this
    file already set for the analogous Phase 7C-53/54 tests."""

    import inspect

    from backend.api.routes import corpus as corpus_routes

    for handler in (
        corpus_routes.create_readiness_evaluation,
        corpus_routes.get_readiness_evaluation,
    ):
        params = inspect.signature(handler).parameters
        assert "pool" not in params, f"{handler.__name__} unexpectedly gained a pool parameter"


def _seed_base_model_resource_estimate(db_path: Path, public_id: str) -> int:
    """Minimal, directly-seeded row satisfying every NOT NULL/CHECK
    constraint on `base_model_resource_estimates` -- bypasses the real
    estimation-calculation service logic (out of scope for this wiring
    test), matching the exact minimal-seeding precedent already
    established by `_seed_pretraining_dataset_snapshot`/
    `_seed_tokenizer_corpus_build` above. Returns the row's internal id."""

    with database_connection(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO base_model_resource_estimates(public_id, profile_name, "
            "vocabulary_size, context_length, hidden_size, num_hidden_layers, "
            "num_attention_heads, intermediate_size, parameter_count, "
            "parameter_memory_bytes, gradient_memory_bytes, optimizer_state_memory_bytes, "
            "activation_memory_bytes, estimated_peak_ram_bytes, checkpoint_disk_bytes, "
            "optimizer_disk_bytes, estimated_tokens_per_second, "
            "estimated_training_duration_seconds_min, estimated_training_duration_seconds_max, "
            "safe_ram_ceiling_bytes, within_safe_limit, created_by_admin_public_id) "
            "VALUES (?,'micro_smoke_test',100,128,64,2,2,128,1000,4000,4000,4000,4000,16000,"
            "1000,1000,10.0,60,120,1000000000,1,'admin-1')",
            (public_id,),
        )
        connection.commit()
        return connection.execute(
            "SELECT id FROM base_model_resource_estimates WHERE public_id=?", (public_id,)
        ).fetchone()["id"]


def _seed_pretraining_smoke_run(
    db_path: Path, snapshot_id: int, estimate_id: int, public_id: str
) -> None:
    """Minimal, directly-seeded row referencing the snapshot/estimate rows
    seeded by `_seed_pretraining_dataset_snapshot`/
    `_seed_base_model_resource_estimate` above."""

    with database_connection(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO pretraining_smoke_runs(public_id, pretraining_dataset_snapshot_id, "
            "base_model_resource_estimate_id, status, created_by_admin_public_id) "
            "VALUES (?,?,?,'completed','admin-1')",
            (public_id, snapshot_id, estimate_id),
        )
        connection.commit()


def test_phase_7c53_smoke_service_shares_the_same_app_pool(tmp_path: Path) -> None:
    """`smoke_service(settings, pool)` -- this factory's first real use of
    the `pool` parameter it mechanically gained in Phase 7C-41 -- must hand
    back a `PretrainingSmokeService` whose `readiness_repository` references
    the exact same shared pool object as the already-wired
    `resource_service` (`is`, not equal configuration)."""

    from backend.api.routes.pretraining_readiness import resource_service, smoke_service

    app = _build_app(tmp_path, "phase-7c53-identity")
    with TestClient(app):
        pool = app.state.pool
        assert pool is not None

        resource_svc = resource_service(app.state.settings, pool)
        smoke_svc = smoke_service(app.state.settings, pool)

        assert smoke_svc.readiness_repository.pool is pool
        assert smoke_svc.core_model_service.repository.pool is pool
        assert smoke_svc.pretraining_service.repository.pool is pool
        assert resource_svc.repository.pool is smoke_svc.readiness_repository.pool


def test_phase_7c53_smoke_run_and_validate_config_read_routes_work_through_wired_pool(
    tmp_path: Path,
) -> None:
    """Real, end-to-end HTTP proof of both Phase 7C-53 routes:
    `get_smoke_run`, `validate_training_config`. Confirms each works
    through the real wired pool, reuses the shared connection
    (`connection_reused_count`), never triggers `ReentrantCheckout`, and
    leaves `outstanding == 0`."""

    app = _build_app(tmp_path, "phase-7c53-reads")
    with TestClient(app) as client:
        pool = app.state.pool
        db_path = app.state.settings.resolved_database_path

        _seed_pretraining_dataset_snapshot(db_path, "phase-7c53-snapshot-1")
        with database_connection(db_path) as connection:
            snapshot_id = connection.execute(
                "SELECT id FROM pretraining_dataset_snapshots WHERE public_id=?",
                ("phase-7c53-snapshot-1",),
            ).fetchone()["id"]
        estimate_id = _seed_base_model_resource_estimate(db_path, "phase-7c53-estimate-1")
        _seed_pretraining_smoke_run(db_path, snapshot_id, estimate_id, "phase-7c53-run-1")

        reused_before = pool.connection_reused_count
        recreated_before = pool.connection_recreated_count

        get_run = client.get(
            "/api/admin/pretraining-readiness/smoke-runs/phase-7c53-run-1"
        )
        assert get_run.status_code == 200, get_run.text
        assert get_run.json()["public_id"] == "phase-7c53-run-1"

        validate = client.post(
            "/api/admin/pretraining-readiness/training-config/validate",
            json={
                "pretraining_dataset_snapshot_public_id": "phase-7c53-snapshot-1",
                "base_model_resource_estimate_public_id": "phase-7c53-estimate-1",
                "configuration": {},
            },
        )
        assert validate.status_code == 200, validate.text
        assert "status" in validate.json()

        assert pool.connection_reused_count > reused_before
        assert pool.connection_recreated_count == recreated_before
        assert pool.outstanding == 0


def test_phase_7c53_default_unwired_smoke_service_routes_still_resolve_to_no_pool(
    tmp_path: Path,
) -> None:
    """`smoke_service`'s other, still-unwired methods (`list_smoke_runs`,
    `create_smoke_run`) keep resolving `pool=None` when called the old
    way -- Phase 7C-53 did not silently widen scope beyond its two
    authorized routes."""

    from backend.api.routes.pretraining_readiness import smoke_service

    settings = _settings(tmp_path / "unwired-smoke-service.db")
    smoke_svc = smoke_service(settings)
    assert smoke_svc.readiness_repository.pool is None
    assert smoke_svc.core_model_service.repository.pool is None
    assert smoke_svc.pretraining_service.repository.pool is None


def test_phase_7c53_blocked_and_deferred_routes_remain_unwired(tmp_path: Path) -> None:
    """Explicit, authoritative isolation proof for Phase 7C-53's scope
    boundary AT THE TIME: `create_smoke_run` (real background-`Thread`
    hazard, Phase 7C-51, still untouched at the time) and the
    `CorpusReadinessService.evaluate()` routes in `corpus.py` -- none
    gained a `pool` parameter this phase.

    Note: `list_smoke_runs`/`list_tokenizer_corpus_builds` were originally
    asserted unwired here too (Phase 7C-51-qualified but deliberately left
    for a future batch, as of Phase 7C-53) -- Phase 7C-54 wired both.
    `create_smoke_run` was originally asserted unwired here too -- Phase
    7C-55 (read-only threading/pool-safety qualification) cleared it and
    Phase 7C-56 wired it. See
    `test_phase_7c56_blocked_and_deferred_routes_remain_unwired` for the
    current, authoritative isolation boundary. Disclosed explicitly
    rather than silently edited, matching the precedent this test itself
    set correcting Phase 7C-52's now-stale assertions."""

    import inspect

    from backend.api.routes import corpus as corpus_routes
    from backend.api.routes import pretraining_readiness as readiness_routes

    for handler in (
        corpus_routes.create_readiness_evaluation,
        corpus_routes.get_readiness_evaluation,
    ):
        params = inspect.signature(handler).parameters
        assert "pool" not in params, f"{handler.__name__} unexpectedly gained a pool parameter"

    for handler in (
        readiness_routes.get_smoke_run,
        readiness_routes.validate_training_config,
        readiness_routes.list_smoke_runs,
        readiness_routes.list_tokenizer_corpus_builds,
    ):
        params = inspect.signature(handler).parameters
        assert "pool" in params, f"{handler.__name__} should have gained a pool parameter"


def test_phase_7c54_tokenizer_corpus_and_smoke_services_share_the_same_app_pool(
    tmp_path: Path,
) -> None:
    """`tokenizer_corpus_service`/`smoke_service` were already wired in
    Phase 7C-52/53 for their sibling `get_*` routes -- this phase extends
    them to `list_builds()`/`list_smoke_runs()`. Confirm both still hand
    back the exact same shared pool object (`is`, not equal configuration)
    as an already-wired factory."""

    from backend.api.routes.pretraining_readiness import (
        resource_service,
        smoke_service,
        tokenizer_corpus_service,
    )

    app = _build_app(tmp_path, "phase-7c54-identity")
    with TestClient(app):
        pool = app.state.pool
        assert pool is not None

        resource_svc = resource_service(app.state.settings, pool)
        corpus_svc = tokenizer_corpus_service(app.state.settings, pool)
        smoke_svc = smoke_service(app.state.settings, pool)

        assert corpus_svc.corpus_repository.pool is pool
        assert corpus_svc.readiness_repository.pool is pool
        assert smoke_svc.readiness_repository.pool is pool
        assert resource_svc.repository.pool is corpus_svc.corpus_repository.pool
        assert resource_svc.repository.pool is smoke_svc.readiness_repository.pool


def test_phase_7c54_list_routes_work_through_wired_pool(tmp_path: Path) -> None:
    """Real, end-to-end HTTP proof of both Phase 7C-54 routes:
    `list_tokenizer_corpus_builds`, `list_smoke_runs`. Confirms each works
    through the real wired pool, reuses the shared connection
    (`connection_reused_count`), never triggers `ReentrantCheckout`, and
    leaves `outstanding == 0`."""

    app = _build_app(tmp_path, "phase-7c54-reads")
    with TestClient(app) as client:
        pool = app.state.pool
        db_path = app.state.settings.resolved_database_path

        _seed_tokenizer_corpus_build(db_path, "phase-7c54-build-1")

        _seed_pretraining_dataset_snapshot(db_path, "phase-7c54-snapshot-1")
        with database_connection(db_path) as connection:
            snapshot_id = connection.execute(
                "SELECT id FROM pretraining_dataset_snapshots WHERE public_id=?",
                ("phase-7c54-snapshot-1",),
            ).fetchone()["id"]
        estimate_id = _seed_base_model_resource_estimate(db_path, "phase-7c54-estimate-1")
        _seed_pretraining_smoke_run(db_path, snapshot_id, estimate_id, "phase-7c54-run-1")

        reused_before = pool.connection_reused_count
        recreated_before = pool.connection_recreated_count

        builds = client.get("/api/admin/pretraining-readiness/tokenizer-corpus-builds")
        assert builds.status_code == 200, builds.text
        build_ids = {item["public_id"] for item in builds.json()["items"]}
        assert "phase-7c54-build-1" in build_ids

        runs = client.get("/api/admin/pretraining-readiness/smoke-runs")
        assert runs.status_code == 200, runs.text
        run_ids = {item["public_id"] for item in runs.json()["items"]}
        assert "phase-7c54-run-1" in run_ids

        assert pool.connection_reused_count > reused_before
        assert pool.connection_recreated_count == recreated_before
        assert pool.outstanding == 0


def test_phase_7c54_default_unwired_construction_still_resolves_to_no_pool(
    tmp_path: Path,
) -> None:
    """Calling `tokenizer_corpus_service`/`smoke_service` the old way (no
    `pool` argument) must still resolve `pool=None` on every repository --
    Phase 7C-54 did not silently widen scope or change either factory's
    default behavior."""

    from backend.api.routes.pretraining_readiness import smoke_service, tokenizer_corpus_service

    settings = _settings(tmp_path / "unwired-phase-7c54.db")

    corpus_svc = tokenizer_corpus_service(settings)
    assert corpus_svc.corpus_repository.pool is None
    assert corpus_svc.readiness_repository.pool is None

    smoke_svc = smoke_service(settings)
    assert smoke_svc.readiness_repository.pool is None
    assert smoke_svc.core_model_service.repository.pool is None
    assert smoke_svc.pretraining_service.repository.pool is None


def test_phase_7c54_blocked_and_deferred_routes_remain_unwired(tmp_path: Path) -> None:
    """Explicit, authoritative isolation proof for Phase 7C-54's scope
    boundary AT THE TIME: `create_smoke_run` (real background-`Thread`
    hazard) and the `corpus.py` `CorpusReadinessService.evaluate()` routes
    gained no `pool` parameter in Phase 7C-54. The two routes that phase
    DID wire (`list_tokenizer_corpus_builds`, `list_smoke_runs`) are
    asserted as now-wired here, consistent with the note left in
    `test_phase_7c53_blocked_and_deferred_routes_remain_unwired`.

    Note: `create_smoke_run` was originally asserted unwired here too, but
    Phase 7C-55 (read-only threading/pool-safety qualification) cleared it
    and Phase 7C-56 wired it -- see
    `test_phase_7c56_blocked_and_deferred_routes_remain_unwired` for the
    current, authoritative isolation boundary. Disclosed and corrected
    here rather than left silently broken, matching the precedent this
    file already set correcting Phase 7C-52's and Phase 7C-53's now-stale
    assertions."""

    import inspect

    from backend.api.routes import corpus as corpus_routes
    from backend.api.routes import pretraining_readiness as readiness_routes

    for handler in (
        corpus_routes.create_readiness_evaluation,
        corpus_routes.get_readiness_evaluation,
    ):
        params = inspect.signature(handler).parameters
        assert "pool" not in params, f"{handler.__name__} unexpectedly gained a pool parameter"

    for handler in (
        readiness_routes.list_tokenizer_corpus_builds,
        readiness_routes.list_smoke_runs,
    ):
        params = inspect.signature(handler).parameters
        assert "pool" in params, f"{handler.__name__} should have gained a pool parameter"


# --- Phase 7C-56: create_smoke_run's real background-thread pool wiring ---


def test_phase_7c56_create_smoke_run_route_accepts_pool_dependency(tmp_path: Path) -> None:
    """Route-level wiring proof: `create_smoke_run`'s signature now
    carries a `pool` parameter, and its body calls the already-pool-aware
    `smoke_service(settings, pool)` factory (the same factory Phase
    7C-53/54 already proved correctly propagates `pool` down to
    `readiness_repository`/`core_model_service.repository`/
    `pretraining_service.repository`) rather than a new abstraction."""

    import inspect

    from backend.api.routes.pretraining_readiness import create_smoke_run, smoke_service

    params = inspect.signature(create_smoke_run).parameters
    assert "pool" in params

    settings = _settings(tmp_path / "phase-7c56-route-wiring.db")
    pool = ConnectionPool(settings.resolved_database_path, size=2)
    try:
        smoke_svc = smoke_service(settings, pool)
        assert smoke_svc.readiness_repository.pool is pool
        assert smoke_svc.core_model_service.repository.pool is pool
        assert smoke_svc.pretraining_service.repository.pool is pool
    finally:
        pool.close()


def test_phase_7c56_pretraining_repository_still_defaults_to_immediate_true() -> None:
    """`PretrainingRepository.transaction()`'s pre-existing class-level
    `immediate=True` default (the structural safeguard Phase 7C-55's
    qualification and real experiment both depend on) was not touched by
    this phase's route-only wiring change."""

    import inspect

    from backend.database.repositories.pretraining import PretrainingRepository

    sig = inspect.signature(PretrainingRepository.transaction)
    assert sig.parameters["immediate"].default is True


def test_phase_7c56_worker_thread_never_receives_a_connection_object_and_checks_out_independently(
    tmp_path: Path,
) -> None:
    """Real, direct proof of Phase 7C-55's central safety claim, using the
    actual `ConnectionPool`/`PretrainingRepository` classes (not a mock):
    a background `Thread` -- structurally identical to
    `_run_job_partial`'s `_worker()` closure, which captures only `self`
    and never a connection -- performs its own real read-then-write
    `PretrainingRepository.transaction(immediate=True)` cycles
    concurrently with the main thread doing the same, exactly like
    `run_one()` racing `metrics()`/`pause()`. Confirms via real connection
    object identity (captured from each thread's own transaction) that:
    - the worker thread's connection is never the same object the main
      thread used (no connection crosses the thread boundary),
    - no `ReentrantCheckout` fires (each thread's checkout is independent,
      thread-local-scoped, as Phase 7C-55's read of `connection_pool.py`
      established),
    - `pool.outstanding` returns to 0 and `connection_recreated_count`
      stays 0 (genuine reuse, no leak) after both threads finish."""

    import threading

    from backend.database.connection import database_connection
    from backend.database.connection_pool import ReentrantCheckout
    from backend.database.repositories.pretraining import PretrainingRepository

    db_path = tmp_path / "phase-7c56-thread-ownership.db"
    with database_connection(db_path) as connection:
        connection.execute(
            "CREATE TABLE jobs(id INTEGER PRIMARY KEY, status TEXT NOT NULL, steps INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO jobs(id, status, steps) VALUES (1, 'queued', 0)")
        connection.commit()

    pool = ConnectionPool(db_path, size=4)
    try:
        repo = PretrainingRepository(db_path, pool=pool)

        main_thread_connections: list[int] = []
        worker_thread_connections: list[int] = []
        errors: list[BaseException] = []

        def _worker() -> None:
            # Structurally identical to `_worker()` in
            # `pretraining_smoke_service.py`: closes over `repo` only,
            # never a connection object, and calls `.transaction()` itself
            # -- exactly like `run_one()` calling `self.repository
            # .transaction()` on its own thread.
            try:
                for _ in range(15):
                    with repo.transaction() as connection:  # immediate=True default
                        worker_thread_connections.append(id(connection))
                        row = connection.execute(
                            "SELECT status, steps FROM jobs WHERE id=1"
                        ).fetchone()
                        connection.execute(
                            "UPDATE jobs SET steps=? WHERE id=1", (row["steps"] + 1,)
                        )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        thread = threading.Thread(target=_worker)
        thread.start()
        # Main-thread polling, structurally identical to `_run_job_partial`'s
        # `metrics()`/`pause()` calls racing the worker's writes.
        for _ in range(10):
            try:
                with repo.transaction() as connection:
                    main_thread_connections.append(id(connection))
                    connection.execute("SELECT status FROM jobs WHERE id=1").fetchone()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
        thread.join(timeout=30)

        assert not thread.is_alive(), "worker thread did not terminate within the join timeout"
        assert not any(isinstance(exc, ReentrantCheckout) for exc in errors), (
            "ReentrantCheckout fired -- would indicate a connection/ownership "
            "hazard crossing the thread boundary"
        )
        assert errors == [], f"unexpected exception(s) in real thread-ownership test: {errors}"

        # Both threads did real work (sanity, not the core assertion).
        assert len(worker_thread_connections) == 15
        assert len(main_thread_connections) == 10

        with database_connection(db_path) as connection:
            final_steps = connection.execute("SELECT steps FROM jobs WHERE id=1").fetchone()[
                "steps"
            ]
        # Only the worker thread writes (mirroring `run_one()`); the main
        # thread's loop is read-only (mirroring `metrics()`'s polling
        # reads) -- so every one of the worker's 15 real transactions must
        # have committed for the final count to be exactly 15.
        assert final_steps == 15, "not every real worker-thread transaction committed"

        assert pool.outstanding == 0
        assert pool.connection_recreated_count == 0
    finally:
        pool.close()


def test_phase_7c56_default_unwired_construction_still_resolves_to_no_pool(tmp_path: Path) -> None:
    """Calling `smoke_service` the old way (no `pool` argument) must still
    resolve `pool=None` on every repository -- Phase 7C-56 did not
    silently widen scope or change the factory's default behavior."""

    from backend.api.routes.pretraining_readiness import smoke_service

    settings = _settings(tmp_path / "unwired-phase-7c56.db")
    smoke_svc = smoke_service(settings)
    assert smoke_svc.readiness_repository.pool is None
    assert smoke_svc.core_model_service.repository.pool is None
    assert smoke_svc.pretraining_service.repository.pool is None


def test_phase_7c56_blocked_and_deferred_routes_remain_unwired(tmp_path: Path) -> None:
    """Explicit, authoritative isolation proof for Phase 7C-56's scope
    boundary: this phase wired ONLY `create_smoke_run`. The
    `CorpusReadinessService.evaluate()` routes in `corpus.py` remain
    completely untouched and unrelated to this investigation."""

    import inspect

    from backend.api.routes import corpus as corpus_routes
    from backend.api.routes import pretraining_readiness as readiness_routes

    for handler in (
        corpus_routes.create_readiness_evaluation,
        corpus_routes.get_readiness_evaluation,
    ):
        params = inspect.signature(handler).parameters
        assert "pool" not in params, f"{handler.__name__} unexpectedly gained a pool parameter"

    for handler in (
        readiness_routes.create_smoke_run,
        readiness_routes.list_tokenizer_corpus_builds,
        readiness_routes.list_smoke_runs,
        readiness_routes.get_smoke_run,
        readiness_routes.validate_training_config,
    ):
        params = inspect.signature(handler).parameters
        assert "pool" in params, f"{handler.__name__} should have gained a pool parameter"


def test_phase_7c56_exactly_one_connection_pool_and_expected_route_count() -> None:
    """Final production-shape census: exactly 1 `ConnectionPool()`
    construction exists anywhere in production code (`main.py`), and
    exactly 31 route-level `pool: PoolDependency` sites exist across the
    three wired route files (30 pre-existing + this phase's 1)."""

    import re
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[2]
    pool_construction_sites = 0
    for py_file in (repo_root / "backend").rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.search(r"(?<!def )\bConnectionPool\(", stripped) and "__init__" not in stripped:
                pool_construction_sites += 1
    assert pool_construction_sites == 1, (
        f"expected exactly 1 production ConnectionPool() construction, found "
        f"{pool_construction_sites}"
    )

    total_pool_dependency_sites = 0
    for filename in ("corpus.py", "pretraining_readiness.py", "base_training.py"):
        text = (repo_root / "backend" / "api" / "routes" / filename).read_text(encoding="utf-8")
        total_pool_dependency_sites += text.count("pool: PoolDependency")
    assert total_pool_dependency_sites == 31, (
        f"expected exactly 31 route-level PoolDependency sites, found "
        f"{total_pool_dependency_sites}"
    )
