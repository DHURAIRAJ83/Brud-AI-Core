"""Phase 21A production tokenizer and base-model pretraining
readiness admin API. Every mutation requires admin authentication and
CSRF. Nothing in this router starts long-running or production-scale
training -- the only training that runs here is the tiny, bounded
pretraining smoke test, and no route wires any result into the public
chatbot.
"""

from typing import Any

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import PoolDependency, SettingsDependency
from backend.database.connection_pool import ConnectionPool
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.pretraining_readiness import PretrainingReadinessRepository
from backend.models.pretraining_readiness import (
    BaseModelReadinessEvaluationCreate,
    PretrainingSnapshotCreate,
    ResourceEstimateCreate,
    SmokeRunCreate,
    TokenizerApprovalRequest,
    TokenizerCandidateComparisonCreate,
    TokenizerCorpusBuildCreate,
    TrainingConfigValidateRequest,
)
from backend.services.base_model_readiness_service import BaseModelReadinessService
from backend.services.base_model_resource_service import BaseModelResourceService
from backend.services.pretraining_smoke_service import PretrainingSmokeService
from backend.services.pretraining_snapshot_service import PretrainingSnapshotService
from backend.services.tokenizer_candidate_service import TokenizerCandidateService
from backend.services.tokenizer_corpus_service import TokenizerCorpusService

router = APIRouter(
    prefix="/admin/pretraining-readiness", tags=["admin-pretraining-readiness"],
    dependencies=[Depends(require_admin)],
)


def _readiness_repo(
    settings, pool: ConnectionPool | None = None
) -> PretrainingReadinessRepository:
    return PretrainingReadinessRepository(settings.resolved_database_path, pool=pool)


def _corpus_repo(settings, pool: ConnectionPool | None = None) -> CorpusRepository:
    return CorpusRepository(settings.resolved_database_path, pool=pool)


def tokenizer_corpus_service(
    settings, pool: ConnectionPool | None = None
) -> TokenizerCorpusService:
    """Phase 7C-52: `get_build()` was opted into the shared app-instance
    pool -- a single, plain read-only `self.corpus_repository.transaction()`
    block; its `_detail()` helper takes `connection` directly and never
    opens a transaction of its own, so `self.readiness_repository`'s reads
    inside it reuse the same connection rather than checking out a second
    one (Phase 7C-51's qualification, independently re-verified this
    phase).

    Phase 7C-54: `list_builds()` was also opted in -- same shape as
    `get_build()`, just iterating `self.readiness_repository
    .list_tokenizer_corpus_builds(connection)` and calling `_detail()` per
    row on the one connection already held; no second checkout, no writes,
    no threading (re-verified by direct read this phase). `build_corpus()`
    remains unpooled pending its own write-path evidence."""

    return TokenizerCorpusService(
        _corpus_repo(settings, pool), _readiness_repo(settings, pool), settings
    )


def tokenizer_candidate_service(
    settings, pool: ConnectionPool | None = None
) -> TokenizerCandidateService:
    """Phase 7C-52: `get_comparison()` was opted into the shared
    app-instance pool -- a single, plain read-only
    `self.readiness_repository.transaction()` block; its `_detail()`
    helper takes `connection` directly and never opens a transaction of
    its own, and never touches `self.tokenizer_service` (the class's
    separately-constructed, permanently-unpooled `TokenizerService`
    instance -- only the write methods `create_comparison()`/`approve()`
    touch that) (Phase 7C-51's qualification, independently re-verified
    this phase). `create_comparison()`, `approve()` remain unpooled
    pending their own evidence."""

    return TokenizerCandidateService(_readiness_repo(settings, pool), settings)


def resource_service(settings, pool: ConnectionPool | None = None) -> BaseModelResourceService:
    """Phase 7C-50: `list_estimates()`/`get_estimate()` were opted into the
    shared app-instance pool -- both are single, plain read-only
    `self.repository.transaction()` blocks with no nested call and no
    sibling repository (Phase 7C-49's qualification, independently
    re-verified this phase). `create_estimate()` remains unpooled pending
    its own write-path evidence."""

    return BaseModelResourceService(_readiness_repo(settings, pool), settings)


def snapshot_service(
    settings, pool: ConnectionPool | None = None
) -> PretrainingSnapshotService:
    """Phase 7C-50: `list_snapshots()`/`get_snapshot()` were opted into the
    shared app-instance pool -- both touch only `self.readiness_repository`
    (never `self.corpus_repository`, despite this service holding both),
    single plain read-only transaction, no nesting (Phase 7C-49's
    qualification, independently re-verified this phase). NOTE the naming
    collision: `PretrainingSnapshotService.get_snapshot()`/`list_snapshots()`
    share their exact method names with the already-wired, entirely
    different `CorpusSourceService.get_snapshot()`/`list_snapshots()`
    (Phase 7C-46, via `source_service` in `corpus.py`) -- do not confuse
    the two. `create_snapshot()` remains unpooled pending its own
    write-path evidence."""

    return PretrainingSnapshotService(
        _corpus_repo(settings, pool), _readiness_repo(settings, pool), settings
    )


def smoke_service(settings, pool: ConnectionPool | None = None) -> PretrainingSmokeService:
    """Phase 7C-53: `validate_training_config()`/`get_smoke_run()` were
    opted into the shared app-instance pool -- both are single, plain
    read-only `self.readiness_repository.transaction()` blocks with no
    nested call and no reference to `self.pretraining_service`/
    `self.core_model_service` (the objects `create_smoke_run()` uses to
    spawn its real background `Thread(target=_worker)`, confirmed
    unrelated to these two methods by direct read this phase).

    Phase 7C-54: `list_smoke_runs()` was also opted in -- same shape,
    a single `self.readiness_repository.transaction()` block wrapping one
    call to `list_pretraining_smoke_runs(connection)` (a plain accessor),
    zero writes, zero reference to the threading-capable objects (re-verified
    by direct read this phase; `Thread(` occurs exactly once in this file,
    inside `create_smoke_run()`, textually and functionally unrelated to
    this method). `create_smoke_run()` remains NOT a pooling candidate at
    all until its background-thread interaction with a pooled connection
    is separately qualified."""

    return PretrainingSmokeService(
        _readiness_repo(settings, pool),
        CoreModelRepository(settings.resolved_database_path, pool=pool),
        PretrainingRepository(settings.resolved_database_path, pool=pool),
        settings,
    )


def readiness_gate_service(
    settings, pool: ConnectionPool | None = None
) -> BaseModelReadinessService:
    """Phase 7C-41: `pool` defaults to `None` -- every existing call site
    below that still says `readiness_gate_service(settings)` keeps today's
    exact unpooled behavior. `list_readiness_evaluations()`/
    `get_readiness_evaluation()` were opted into the shared pool as this
    file's one representative pair, chosen because `BaseModelReadinessService`
    was already confirmed sequential (never nested) across multiple prior
    phases (7C-31/32/38/40). Both are read-only, so the sibling
    `_corpus_repo`/`_readiness_repo`/`PretrainingRepository` constructions
    below all receive the same pool object for identity, but none needs
    `immediate=True`.

    Phase 7C-44: `create_readiness_evaluation()` -> `.evaluate()` also now
    uses this shared pool. `.evaluate()`'s 6 transaction blocks were
    independently qualified (Phase 7C-43 read-only qualification; this
    phase's own real Barrier-synchronized re-qualification): Block 1
    (read-then-write) required `evaluate()` itself to open with
    `immediate=True` (see that method's own docstring for the evidence) --
    fixed and re-verified to eliminate the contention completely, both
    pooled and unpooled. Block 6 (a large write-then-read loop) was
    independently qualified as genuinely deferred-safe: because its first
    statement is a write (the evaluation row id is already known from
    Block 1, no preceding read in that transaction), it claims the write
    lock immediately with no read-snapshot-invalidation window -- measured
    at 0% errors across 4,800 real concurrent attempts, both pooled and
    unpooled, both BEGIN modes -- so it correctly remains at the default
    `immediate=False`."""

    return BaseModelReadinessService(
        _readiness_repo(settings, pool),
        _corpus_repo(settings, pool),
        PretrainingRepository(settings.resolved_database_path, pool=pool),
        settings,
    )


# --- tokenizer corpus -----------------------------------------------------


@router.get("/tokenizer-corpus-builds")
async def list_tokenizer_corpus_builds(settings: SettingsDependency, pool: PoolDependency):
    return tokenizer_corpus_service(settings, pool).list_builds()


@router.post("/tokenizer-corpus-builds")
async def create_tokenizer_corpus_build(
    payload: TokenizerCorpusBuildCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return tokenizer_corpus_service(settings).build_corpus(payload, admin.admin.public_id)


@router.get("/tokenizer-corpus-builds/{public_id}")
async def get_tokenizer_corpus_build(
    public_id: str, settings: SettingsDependency, pool: PoolDependency
):
    return tokenizer_corpus_service(settings, pool).get_build(public_id)


# --- tokenizer candidates -----------------------------------------------------


@router.post("/tokenizer-candidate-comparisons")
async def create_tokenizer_candidate_comparison(
    payload: TokenizerCandidateComparisonCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return tokenizer_candidate_service(settings).create_comparison(payload, admin.admin.public_id)


@router.get("/tokenizer-candidate-comparisons/{public_id}")
async def get_tokenizer_candidate_comparison(
    public_id: str, settings: SettingsDependency, pool: PoolDependency
):
    return tokenizer_candidate_service(settings, pool).get_comparison(public_id)


@router.post("/tokenizer-candidate-comparisons/{public_id}/approve")
async def approve_tokenizer_candidate(
    public_id: str, payload: TokenizerApprovalRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return tokenizer_candidate_service(settings).approve(public_id, payload, admin.admin.public_id)


@router.post("/tokenizer-versions/{public_id}/activate")
async def activate_tokenizer_version(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return tokenizer_candidate_service(settings).activate(public_id, admin.admin.public_id)


# --- resource estimates -----------------------------------------------------


@router.get("/resource-estimates")
async def list_resource_estimates(settings: SettingsDependency, pool: PoolDependency):
    return resource_service(settings, pool).list_estimates()


@router.post("/resource-estimates")
async def create_resource_estimate(
    payload: ResourceEstimateCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return resource_service(settings).create_estimate(payload, admin.admin.public_id)


@router.get("/resource-estimates/{public_id}")
async def get_resource_estimate(
    public_id: str, settings: SettingsDependency, pool: PoolDependency
):
    return resource_service(settings, pool).get_estimate(public_id)


# --- pretraining dataset snapshots -----------------------------------------------------


@router.get("/dataset-snapshots")
async def list_dataset_snapshots(settings: SettingsDependency, pool: PoolDependency):
    return snapshot_service(settings, pool).list_snapshots()


@router.post("/dataset-snapshots")
async def create_dataset_snapshot(
    payload: PretrainingSnapshotCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return snapshot_service(settings).create_snapshot(payload, admin.admin.public_id)


@router.get("/dataset-snapshots/{public_id}")
async def get_dataset_snapshot(
    public_id: str, settings: SettingsDependency, pool: PoolDependency
):
    return snapshot_service(settings, pool).get_snapshot(public_id)


# --- training configuration + smoke runs -----------------------------------------------------


@router.post("/training-config/validate")
async def validate_training_config(
    payload: TrainingConfigValidateRequest, settings: SettingsDependency, pool: PoolDependency
) -> dict[str, Any]:
    return smoke_service(settings, pool).validate_training_config(payload)


@router.get("/smoke-runs")
async def list_smoke_runs(settings: SettingsDependency, pool: PoolDependency):
    return smoke_service(settings, pool).list_smoke_runs()


@router.post("/smoke-runs")
async def create_smoke_run(
    payload: SmokeRunCreate, settings: SettingsDependency, admin: CsrfDependency,
    pool: PoolDependency,
):
    """Phase 7C-56: opted into the shared app-instance pool. `create_smoke_run()`
    spawns a real background `Thread(target=_worker)` (`pretraining_smoke_service
    .py:288`) that calls `self.pretraining_service.run_one(...)` on its own
    thread -- Phase 7C-55's read-only qualification (independently re-verified
    this phase) established that the worker never receives a connection object,
    only the already-pool-aware `PretrainingRepository` instance (via
    `self.pretraining_service.repository`), so the worker's own
    `self.repository.transaction()` calls independently checkout/checkin from
    the shared pool on the worker's own thread -- exactly the safe pattern this
    pool architecture was built for. `PretrainingRepository.transaction()`
    already defaults to `immediate=True` at the class level (unchanged), which
    Phase 7C-55's real concurrent experiment (main-thread polling + worker-thread
    writing, both under `immediate=True`) confirmed eliminates the deferred-BEGIN
    contention class for this exact shape: 0 errors/0 ReentrantCheckout/0 leaks
    across 6 runs. No worker-thread-aware code was added -- the existing
    per-call checkout/checkin design in `smoke_service(settings, pool)`'s
    already-pool-aware `PretrainingRepository` construction handles this
    automatically."""

    return smoke_service(settings, pool).create_smoke_run(payload, admin.admin.public_id)


@router.get("/smoke-runs/{public_id}")
async def get_smoke_run(public_id: str, settings: SettingsDependency, pool: PoolDependency):
    return smoke_service(settings, pool).get_smoke_run(public_id)


# --- base-model readiness gate -----------------------------------------------------


@router.get("/readiness-evaluations")
async def list_readiness_evaluations(settings: SettingsDependency, pool: PoolDependency):
    return readiness_gate_service(settings, pool).list_evaluations()


@router.post("/readiness-evaluations")
async def create_readiness_evaluation(
    payload: BaseModelReadinessEvaluationCreate, settings: SettingsDependency,
    admin: CsrfDependency, pool: PoolDependency,
):
    return readiness_gate_service(settings, pool).evaluate(payload, admin.admin.public_id)


@router.get("/readiness-evaluations/{public_id}")
async def get_readiness_evaluation(
    public_id: str, settings: SettingsDependency, pool: PoolDependency
):
    return readiness_gate_service(settings, pool).get_evaluation(public_id)
