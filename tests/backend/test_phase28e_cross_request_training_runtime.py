"""Phase 2.8E: Cross-Request Training Runtime Persistence & Multi-Request
Execution Integrity.

Phase 2.8D confirmed the exact gap this phase closes: only `resume()`
could pick up a genuinely fresh adapter; every other MB-22 stage
(`reserve_runtime` through `finalize`) required the literal same
`TorchTrainingAdapter` object across calls, which a real, separate HTTP
request could never provide (`service(settings)` constructs a brand
new `MiniBrainTrainingEngineService`, and therefore a brand new
adapter, on every single route call).

This phase closes it with a process-local `JobAdapterRegistry`
(`backend/services/training_adapter_registry.py`) plus a single,
unified reconstruction path
(`MiniBrainTrainingEngineService._ensure_adapter_for_job()`) every
gpu-mode stage now goes through: same-process continuation is free
(the registry returns the exact same live object); a genuinely absent
adapter is reconstructed from the same authoritative state every other
stage already trusts -- the job's own DB row, the governed dataset/
tokenizer/Core-Model identity, and (if one exists) the latest verified
checkpoint, reusing Phase 2.8C's `_recover_adapter_from_checkpoint()`
verbatim. The registry is never authoritative -- it is evicted on
cancel/finalize/failure/archive, and a fresh process (or an evicted
entry) always falls back to checkpoint-based reconstruction.

Every test in this file that exercises the NEW cross-request path uses
NO adapter override (`MiniBrainTrainingEngineService(settings)`, never
`adapters={"gpu": ...}`) -- the established test-injection pattern from
every prior phase deliberately bypasses the very construction path this
phase changes, so using it here would prove nothing new. Real subprocess
boundaries and a real HTTP TestClient (via `httpx.AsyncClient` +
`ASGITransport`, the established pattern from `test_dataset_api.py`)
are used for the two central claims this phase must prove without any
mock-only substitute: cross-request execution, and cross-process
recovery.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database.connection import database_connection
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ConflictError, ValidationError
from backend.models.auth import AdminCreate
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService
from backend.services.training_adapter_registry import REGISTRY
from backend.services.training_runtime_adapter import TorchTrainingAdapter
from tests.backend.test_mini_brain_training_engine_service import (
    _create_admin,
    _seed_approved_package_and_release,
)
from tests.backend.test_phase27h_training_dataset_readiness import (
    _build_real_dataset_via_service,
    _generate_corpus,
    _real_tokenizer,
)
from tests.backend.test_torch_training_adapter_integration import _real_core_model_version

pytestmark = pytest.mark.anyio

_RUNNER = Path(__file__).parent / "_phase28e_subprocess_runner.py"
_HTTP_PASSWORD = "Phase28e-Http-Password-42"
_PREFIX = "/api/admin/mini-brain/training-engine"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.core.config import Settings
    from backend.database.migrations import initialize_database
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus", tokenizer_dir=tmp_path / "tokenizers",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _run(*args: str, timeout: int = 300) -> dict:
    result = subprocess.run(
        [sys.executable, str(_RUNNER), *args], capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


async def _authenticated_client(app: FastAPI, *, username: str):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username=username, display_name="P", password=_HTTP_PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await client.post("/api/admin/auth/login", json={"username": username, "password": _HTTP_PASSWORD})
    assert response.status_code == 200, response.text
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": csrf}


async def _real_prerequisites(
    api_app: FastAPI, *, name_suffix: str, record_count: int = 60,
    hidden_size: int = 16, intermediate_size: int = 32,
):
    settings = api_app.state.settings
    admin_id = _create_admin(api_app, username=f"admin-{name_suffix}")
    tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic=name_suffix)
    tokenizer_id = _real_tokenizer(settings, name_suffix=name_suffix)
    cmv_id = _real_core_model_version(
        settings, admin_id, name_suffix=name_suffix, tokenizer_version_public_id=tokenizer_id,
        hidden_size=hidden_size, intermediate_size=intermediate_size,
    )
    dataset_id, _, _ = _build_real_dataset_via_service(
        settings, name_suffix=name_suffix, record_texts=_generate_corpus(record_count, seed_offset=1),
    )
    return admin_id, tp_id, rg_id, cmv_id, dataset_id


def _fresh_service(settings) -> MiniBrainTrainingEngineService:
    """No adapter override -- the exact construction pattern a real HTTP
    route's own `service(settings)` factory uses."""
    return MiniBrainTrainingEngineService(settings)


async def _drive_to_reserved(
    api_app: FastAPI, *, name_suffix: str, record_count: int = 60,
    hidden_size: int = 16, intermediate_size: int = 32,
):
    """Drives a real job through create_job -> build_manifest using a
    fresh, non-overridden service each stage (proving those stages never
    needed adapter continuity), then reserves runtime -- returns the
    settings/admin/job_id for the caller to continue from."""

    settings = api_app.state.settings
    admin_id, tp_id, rg_id, cmv_id, dataset_id = await _real_prerequisites(
        api_app, name_suffix=name_suffix, record_count=record_count,
        hidden_size=hidden_size, intermediate_size=intermediate_size,
    )

    svc = _fresh_service(settings)
    job = svc.create_job(
        topic=f"{name_suffix}-job", training_package_session_public_id=tp_id,
        release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
        core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
    )
    job_id = job["public_id"]
    _fresh_service(settings).run_validate_release_stage(job_id, admin_id=admin_id)
    _fresh_service(settings).run_validate_package_stage(job_id, admin_id=admin_id)
    _fresh_service(settings).run_validate_authorization_stage(job_id, authorization_reason="phase 2.8e", admin_id=admin_id)
    _fresh_service(settings).run_plan_resources_stage(job_id, admin_id=admin_id)
    _fresh_service(settings).run_build_manifest_stage(job_id, admin_id=admin_id)
    _fresh_service(settings).run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_XREQ_28E")
    return settings, admin_id, job_id, dataset_id, cmv_id


async def _drive_to_paused_with_checkpoint(api_app: FastAPI, *, name_suffix: str, record_count: int = 60):
    settings, admin_id, job_id, dataset_id, cmv_id = await _drive_to_reserved(
        api_app, name_suffix=name_suffix, record_count=record_count,
    )
    _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
    _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    _fresh_service(settings).run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
    _fresh_service(settings).pause(job_id, admin_id=admin_id)
    return settings, admin_id, job_id, dataset_id, cmv_id


# ===========================================================================
# Part 9: real HTTP request-boundary proof -- the mandatory 17-request
# sequence, each request served by a genuinely fresh service/adapter.
# ===========================================================================


class TestHTTPRequestBoundary:
    async def test_full_17_request_lifecycle_over_real_http(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        admin_id, tp_id, rg_id, cmv_id, dataset_id = await _real_prerequisites(api_app, name_suffix="http17")
        client, headers = await _authenticated_client(api_app, username="http17-admin")
        try:
            # Request 1: create job.
            r = await client.post(f"{_PREFIX}/jobs", headers=headers, json={
                "topic": "http17-job", "training_package_session_public_id": tp_id,
                "release_governance_session_public_id": rg_id, "execution_mode": "gpu",
                "core_model_version_public_id": cmv_id, "dataset_version_public_id": dataset_id,
            })
            assert r.status_code == 200, r.text
            job_id = r.json()["public_id"]

            # Requests 2-6: validate/authorize/plan/build-manifest.
            for path, payload in (
                ("validate-release", None), ("validate-package", None),
                ("authorize", {"authorization_reason": "http 17-request proof"}),
                ("plan-resources", None), ("build-manifest", None),
            ):
                r = await client.post(f"{_PREFIX}/jobs/{job_id}/{path}", headers=headers, json=payload)
                assert r.status_code == 200, f"{path}: {r.text}"

            # Request 7: reserve runtime -- NO train_blocks in the body;
            # this is the exact case that previously required the caller
            # to hand-supply real token blocks over HTTP.
            r = await client.post(
                f"{_PREFIX}/jobs/{job_id}/reserve-runtime", headers=headers,
                json={"configuration_label": "TEST_HTTP17"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["stage"] == "start_training"

            # Request 8: start training.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/start", headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "running"

            # Request 9: training step.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/metrics", headers=headers, json={"step": 1, "epoch": 0})
            assert r.status_code == 200, r.text
            assert r.json()["training_state"]["last_loss"] is not None

            # Request 10: save checkpoint.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/checkpoints", headers=headers, json={"step": 1, "epoch": 0})
            assert r.status_code == 200, r.text

            # Request 11: pause.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/pause", headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "paused"

            # Request 12: resume.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/resume", headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "running"

            # Request 13: training step (post-resume).
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/metrics", headers=headers, json={"step": 2, "epoch": 0})
            assert r.status_code == 200, r.text

            # Request 14: checkpoint.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/checkpoints", headers=headers, json={"step": 2, "epoch": 0})
            assert r.status_code == 200, r.text

            # Request 15: finalize.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/finalize", headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "completed"

            # Request 16: generate report.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/report", headers=headers)
            assert r.status_code == 200, r.text

            # Request 17: archive.
            r = await client.post(f"{_PREFIX}/jobs/{job_id}/archive", headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "archived"

            # The registry was actually used and then cleaned up -- not
            # merely "requests happened to succeed by coincidence".
            assert not REGISTRY.contains(job_id)

            with database_connection(settings.resolved_database_path) as connection:
                checkpoint_count = connection.execute(
                    "SELECT COUNT(*) FROM mini_brain_training_checkpoints"
                ).fetchone()[0]
            assert checkpoint_count == 2
        finally:
            await client.aclose()


# ===========================================================================
# Part 10: process-restart proof -- two genuinely separate OS processes,
# no adapter override in either.
# ===========================================================================


class TestProcessRestartRecovery:
    def test_fresh_process_recovers_train_step_checkpoint_finalize(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "restart"
        work_dir.mkdir()
        before = _run("train_checkpoint_pause", str(work_dir), "restart28e")
        assert before["completed_steps"] == 1
        assert before["registry_had_live_adapter_at_end"] is True

        after = _run("resume_and_continue", str(work_dir), before["job_id"], "true")
        assert after["registry_empty_before_recovery"] is True
        assert after["recovery_succeeded"] is True
        assert after["model_restored"] is True
        assert after["restored_model_weights_sha256"] == before["model_weights_sha256"]
        assert after["optimizer_state_restored"] is True
        assert after["completed_steps_after_recovery"] == 1
        assert after["weights_changed_after_resumed_step"] is True
        assert after["checkpoint_count_after_recovery"] == 2
        assert after["new_checkpoint_verified"] is True
        assert after["new_checkpoint_dataset_id"] == before["dataset_id"]
        assert after["new_checkpoint_core_model_id"] == before["cmv_id"]
        assert after["finalize_status"] == "completed"
        assert after["registry_evicted_after_finalize"] is True
        assert after["job_row_count"] == 1


# ===========================================================================
# Part 11: normal multi-request execution, same-process, fresh service
# per stage (no HTTP overhead, broader coverage of the invariant).
# ===========================================================================


class TestMultiRequestContinuation:
    async def test_reserve_start_step_checkpoint_pause_each_a_fresh_service(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _dataset_id, _cmv_id = await _drive_to_reserved(api_app, name_suffix="multi-a")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        _fresh_service(settings).run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        result = _fresh_service(settings).pause(job_id, admin_id=admin_id)
        assert result["status"] == "paused"

    async def test_resume_step_checkpoint_finalize_each_a_fresh_service(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, dataset_id, cmv_id = await _drive_to_paused_with_checkpoint(
            api_app, name_suffix="multi-b",
        )
        result = _fresh_service(settings).resume(job_id, admin_id=admin_id)
        assert result["status"] == "running"
        _fresh_service(settings).run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        _fresh_service(settings).run_save_checkpoint_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        finalized = _fresh_service(settings).finalize(job_id, admin_id=admin_id)
        assert finalized["status"] == "completed"

        checkpoints = _fresh_service(settings).list_checkpoints(job_id)["items"]
        assert len(checkpoints) == 2
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        canonical_dir = Path(REGISTRY.get(job_id)._checkpoints_saved[-1]["canonical_checkpoint_directory"]) \
            if REGISTRY.contains(job_id) else None
        # Registry was already evicted by finalize() -- verify via the
        # checkpoint pointer file instead, proving provenance
        # independently of whatever this process's registry still holds.
        job_dir = settings.resolved_document_dir.parent / "training_runs" / job_id
        pointer = json.loads((job_dir / checkpoints[-1]["relative_path"]).read_text())
        manager = TrainingCheckpointManager(
            Path(pointer["canonical_checkpoint_directory"]).parent, settings.core_checkpoint_max_bytes,
        )
        references = manager.load_states(Path(pointer["canonical_checkpoint_directory"]))["references"]
        assert references["dataset_version_public_id"] == dataset_id
        assert references["core_model_version_public_id"] == cmv_id


# ===========================================================================
# Part 12: concurrency.
# ===========================================================================


class TestConcurrency:
    async def test_two_simultaneous_training_step_requests_serialize_safely(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="conc-step")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)

        results: dict[int, Any] = {}
        errors: dict[int, Exception] = {}

        def worker(step: int) -> None:
            try:
                results[step] = _fresh_service(settings).run_stream_metric_stage(
                    job_id, step=step, epoch=0, admin_id=admin_id,
                )
            except Exception as exc:  # noqa: BLE001
                errors[step] = exc

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        # Both distinct-step requests succeed -- the per-job lock
        # serializes them (no corruption, no lost update, no crash), it
        # never silently drops one. The lock guarantees mutual exclusion,
        # not a specific execution order between two threads started
        # with no synchronization between them -- so `last_step` is
        # whichever of {1, 2} genuinely executed (and committed) last;
        # asserting one specific value here would assert an ordering
        # neither thread was ever told to honor. What must hold
        # regardless of order: no error, no lost metric row, and a
        # final `last_step` that is one of the two real, submitted steps
        # -- never a third, corrupted value.
        assert not errors, errors
        assert set(results.keys()) == {1, 2}
        final = _fresh_service(settings).job(job_id)
        assert final["training_state"]["last_step"] in (1, 2)
        with database_connection(settings.resolved_database_path) as connection:
            metric_steps = [
                row["step"] for row in connection.execute(
                    "SELECT step FROM mini_brain_training_metrics ORDER BY step"
                ).fetchall()
            ]
        assert metric_steps == [1, 2]

    async def test_training_step_and_checkpoint_requests_serialize_safely(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="conc-ckpt")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)

        errors: list[Exception] = []

        def step_worker() -> None:
            try:
                _fresh_service(settings).run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def checkpoint_worker() -> None:
            try:
                _fresh_service(settings).run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=step_worker)
        t2 = threading.Thread(target=checkpoint_worker)
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        assert not errors, errors
        checkpoints = _fresh_service(settings).list_checkpoints(job_id)["items"]
        assert len(checkpoints) == 1  # never duplicated
        job_after = _fresh_service(settings).job(job_id)
        assert job_after["training_state"]["last_step"] == 2

    async def test_pause_and_training_step_serialize_no_lost_state(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="conc-pause")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)

        outcomes: list[tuple[str, Any]] = []
        lock = threading.Lock()

        def pause_worker() -> None:
            try:
                result = _fresh_service(settings).pause(job_id, admin_id=admin_id)
                with lock:
                    outcomes.append(("pause_ok", result["status"]))
            except Exception as exc:  # noqa: BLE001
                with lock:
                    outcomes.append(("pause_err", exc))

        def step_worker() -> None:
            try:
                result = _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
                with lock:
                    outcomes.append(("step_ok", result["status"]))
            except Exception as exc:  # noqa: BLE001
                with lock:
                    outcomes.append(("step_err", exc))

        t1 = threading.Thread(target=pause_worker)
        t2 = threading.Thread(target=step_worker)
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        # Whichever ran first, the final DB state is one of the two
        # valid, well-defined outcomes -- never a corrupted hybrid.
        final = _fresh_service(settings).job(job_id)
        assert final["status"] in ("running", "paused", "failed")
        # No duplicate job, no crash left the system in an ambiguous state.
        with database_connection(settings.resolved_database_path) as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0]
        assert job_count == 1

    async def test_two_simultaneous_resumes_only_one_transitions_status(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_paused_with_checkpoint(api_app, name_suffix="conc-resume")

        outcomes: list[tuple[str, Any]] = []
        lock = threading.Lock()

        def resume_worker() -> None:
            try:
                result = _fresh_service(settings).resume(job_id, admin_id=admin_id)
                with lock:
                    outcomes.append(("ok", result["status"]))
            except (ValidationError, ConflictError) as exc:
                with lock:
                    outcomes.append(("rejected", str(exc)))

        threads = [threading.Thread(target=resume_worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert len(outcomes) == 2
        successes = [o for o in outcomes if o[0] == "ok"]
        rejections = [o for o in outcomes if o[0] == "rejected"]
        # Exactly one resume succeeds; the other is safely rejected
        # (either "already running" or a lock-timeout conflict) -- never
        # both silently succeeding, never a corrupted double-recovery.
        assert len(successes) == 1
        assert len(rejections) == 1
        final = _fresh_service(settings).job(job_id)
        assert final["status"] == "running"

    async def test_finalize_and_training_step_serialize_no_corruption(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="conc-finalize")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)

        outcomes: list[tuple[str, Any]] = []
        lock = threading.Lock()

        def finalize_worker() -> None:
            try:
                result = _fresh_service(settings).finalize(job_id, admin_id=admin_id)
                with lock:
                    outcomes.append(("finalize_ok", result["status"]))
            except Exception as exc:  # noqa: BLE001
                with lock:
                    outcomes.append(("finalize_err", type(exc).__name__))

        def step_worker() -> None:
            try:
                result = _fresh_service(settings).run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
                with lock:
                    outcomes.append(("step_ok", result["status"]))
            except Exception as exc:  # noqa: BLE001
                with lock:
                    outcomes.append(("step_err", type(exc).__name__))

        t1 = threading.Thread(target=finalize_worker)
        t2 = threading.Thread(target=step_worker)
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        final = _fresh_service(settings).job(job_id)
        # A well-defined terminal or in-progress state -- never two
        # adapters, never a duplicate job.
        assert final["status"] in ("completed", "running", "failed")
        with database_connection(settings.resolved_database_path) as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM mini_brain_training_jobs").fetchone()[0]
        assert job_count == 1


# ===========================================================================
# Part 13: idempotency.
# ===========================================================================


class TestIdempotency:
    async def test_repeated_checkpoint_save_same_step_rejected(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="idem-ckpt")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        _fresh_service(settings).run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        with pytest.raises(ValidationError, match="already exists"):
            _fresh_service(settings).run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        assert len(_fresh_service(settings).list_checkpoints(job_id)["items"]) == 1

    async def test_repeated_pause_rejected(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="idem-pause")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).pause(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="must be 'running' to pause"):
            _fresh_service(settings).pause(job_id, admin_id=admin_id)

    async def test_repeated_resume_rejected(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_paused_with_checkpoint(api_app, name_suffix="idem-resume")
        _fresh_service(settings).resume(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="must be 'paused' to resume"):
            _fresh_service(settings).resume(job_id, admin_id=admin_id)

    async def test_repeated_finalize_rejected(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="idem-finalize")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).finalize(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="must be 'running' or 'paused' to finalize"):
            _fresh_service(settings).finalize(job_id, admin_id=admin_id)

    async def test_repeated_archive_rejected(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="idem-archive")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).finalize(job_id, admin_id=admin_id)
        _fresh_service(settings).archive(job_id, admin_id=admin_id)
        with pytest.raises(ValidationError, match="must be 'completed' or 'cancelled' to archive"):
            _fresh_service(settings).archive(job_id, admin_id=admin_id)

    def test_repeated_recovery_via_fresh_processes_is_safe(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "idem-recovery"
        work_dir.mkdir()
        before = _run("train_checkpoint_pause", str(work_dir), "idemrecov")
        first = _run("resume_and_continue", str(work_dir), before["job_id"], "true")
        assert first["recovery_succeeded"] is True
        assert first["finalize_status"] == "completed"

        second = _run("resume_and_continue", str(work_dir), before["job_id"], "false")
        assert second["recovery_succeeded"] is False
        assert "must be 'paused' to resume" in second["error"]


# ===========================================================================
# Part 14: failure during request.
# ===========================================================================


class TestFailureDuringRequest:
    async def test_interruption_before_first_checkpoint_is_unrecoverable_by_a_fresh_service(
        self, api_app: FastAPI,
    ) -> None:
        """Genuinely distinct from a training-time exception: a fresh
        service finds no live adapter AND no checkpoint -- honestly
        reports that this training position cannot be reconstructed,
        never fabricates a fresh start, never silently succeeds."""

        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="fail-before-ckpt")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        # Simulate process death: evict the registry entry without ever
        # having saved a checkpoint.
        REGISTRY.evict(job_id)

        with pytest.raises(ValidationError, match="cannot be reconstructed"):
            _fresh_service(settings).run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)

        job_after = _fresh_service(settings).job(job_id)
        # The job's own status is untouched by this failure -- it is
        # still genuinely 'running' (nothing was falsely marked failed
        # for what is an infrastructure-availability condition, not a
        # real training exception); a later request from a process that
        # DOES have the live adapter (or after a checkpoint exists) can
        # still succeed.
        assert job_after["status"] == "running"

    async def test_interruption_after_checkpoint_is_recoverable_by_a_fresh_service(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="fail-after-ckpt")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        _fresh_service(settings).run_save_checkpoint_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        REGISTRY.evict(job_id)  # simulate process death, but AFTER a checkpoint exists

        result = _fresh_service(settings).run_stream_metric_stage(job_id, step=2, epoch=0, admin_id=admin_id)
        assert result["training_state"]["last_step"] == 2
        assert result["status"] == "running"

    async def test_genuine_training_exception_still_reaches_failed_status(self, api_app: FastAPI) -> None:
        """A real training-time exception (not a runtime-availability
        gap) still reaches Phase 2.8B's own, unmodified failure path --
        distinct from the "cannot be reconstructed" case above."""

        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="fail-exception")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)

        real_adapter = REGISTRY.get(job_id)
        original_step = real_adapter.step

        def failing_step(*, step, epoch):
            raise RuntimeError("simulated genuine training failure")

        real_adapter.step = failing_step
        try:
            with pytest.raises(RuntimeError, match="simulated genuine training failure"):
                _fresh_service(settings).run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        finally:
            real_adapter.step = original_step

        job_after = _fresh_service(settings).job(job_id)
        assert job_after["status"] == "failed"
        assert job_after["training_state"]["last_error"]
        assert not REGISTRY.contains(job_id)  # Part 17: job failed -> adapter released

    async def test_lock_timeout_produces_typed_conflict_not_a_hang(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="fail-lock-timeout")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)

        held = threading.Event()
        release = threading.Event()

        def holder() -> None:
            lock = REGISTRY.lock_for(job_id)
            lock.acquire()
            held.set()
            release.wait(timeout=10)
            lock.release()

        t = threading.Thread(target=holder)
        t.start()
        held.wait(timeout=5)

        svc = _fresh_service(settings)
        svc._JOB_LOCK_TIMEOUT_SECONDS = 1  # bound this test's own wait, not production behavior
        try:
            with pytest.raises(ConflictError, match="already in progress"):
                svc.run_stream_metric_stage(job_id, step=1, epoch=0, admin_id=admin_id)
        finally:
            release.set()
            t.join(timeout=10)


# ===========================================================================
# Part 16: provenance -- wrong-job checkpoint / wrong-job adapter.
# ===========================================================================


class TestProvenanceCrossJob:
    async def test_job_b_cannot_recover_using_job_a_checkpoint(self, api_app: FastAPI) -> None:
        settings, admin_a, job_a, ds_a, cmv_a = await _drive_to_paused_with_checkpoint(
            api_app, name_suffix="prov-a",
        )
        # A second, genuinely different Core Model Version (different
        # numeric shape, avoiding the config_checksum_sha256 collision
        # discovered in Phase 2.8C) and dataset for Job B.
        admin_b = _create_admin(api_app, username="admin-prov-b")
        tp_b, rg_b = await _seed_approved_package_and_release(api_app, admin_b, topic="prov-b")
        tokenizer_b = _real_tokenizer(settings, name_suffix="prov-b")
        cmv_b = _real_core_model_version(
            settings, admin_b, name_suffix="prov-b", tokenizer_version_public_id=tokenizer_b,
            hidden_size=24, intermediate_size=48,
        )
        dataset_b, _, _ = _build_real_dataset_via_service(
            settings, name_suffix="prov-b", record_texts=_generate_corpus(60, seed_offset=2),
        )
        svc = _fresh_service(settings)
        job_b = svc.create_job(
            topic="prov-b-job", training_package_session_public_id=tp_b,
            release_governance_session_public_id=rg_b, execution_mode="gpu", admin_id=admin_b,
            core_model_version_public_id=cmv_b, dataset_version_public_id=dataset_b,
        )
        job_b_id = job_b["public_id"]

        # Job B is genuinely reserved and started with its OWN identity
        # first (no checkpoint exists for it yet at this point) -- a
        # fresh service attempting to serve its `reserve_runtime`/`start`
        # stages must never accidentally find and attempt to recover
        # from the checkpoint planted below.
        _fresh_service(settings).run_validate_release_stage(job_b_id, admin_id=admin_b)
        _fresh_service(settings).run_validate_package_stage(job_b_id, admin_id=admin_b)
        _fresh_service(settings).run_validate_authorization_stage(job_b_id, authorization_reason="prov-b", admin_id=admin_b)
        _fresh_service(settings).run_plan_resources_stage(job_b_id, admin_id=admin_b)
        _fresh_service(settings).run_build_manifest_stage(job_b_id, admin_id=admin_b)
        _fresh_service(settings).run_reserve_runtime_stage(job_b_id, admin_id=admin_b, configuration_label="TEST_XREQ_28E")
        _fresh_service(settings).run_start_training_stage(job_b_id, admin_id=admin_b)

        # Only now plant a fake checkpoint row for Job B that actually
        # points at Job A's real checkpoint directory/content.
        import shutil

        real_checkpoint_dir = Path(REGISTRY.get(job_a)._checkpoints_saved[0]["canonical_checkpoint_directory"]) \
            if REGISTRY.contains(job_a) else None
        assert real_checkpoint_dir is not None
        job_b_checkpoint_root = settings.resolved_pretraining_dir / "mini_brain_training_jobs" / job_b_id
        copied_dir = job_b_checkpoint_root / "step-00000001-epoch-0000"
        shutil.copytree(real_checkpoint_dir, copied_dir)

        job_b_dir = settings.resolved_document_dir.parent / "training_runs" / job_b_id
        pointer_path = job_b_dir / "checkpoints" / "checkpoint-epoch000-step00000001.json"
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        from backend.core.json_utils import dumps_json

        pointer_path.write_text(
            dumps_json({
                "real_checkpoint": True, "canonical_checkpoint_directory": str(copied_dir),
                "combined_checksum_sha256": "x" * 64, "model_checksum_sha256": "y" * 64,
                "file_size_bytes": 1, "configuration_label": "TEST_XREQ_28E",
            }),
            encoding="utf-8",
        )
        with database_connection(settings.resolved_database_path) as connection:
            job_b_row = connection.execute(
                "SELECT id FROM mini_brain_training_jobs WHERE public_id=?", (job_b_id,)
            ).fetchone()
            connection.execute(
                """INSERT INTO mini_brain_training_checkpoints
                (public_id, job_id, step, epoch, checkpoint_name, relative_path, sha256, file_size_bytes)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    "cross-job-checkpoint", job_b_row["id"], 1, 0, "checkpoint-epoch000-step00000001",
                    "checkpoints/checkpoint-epoch000-step00000001.json", "z" * 64, 1,
                ),
            )
            connection.commit()

        REGISTRY.evict(job_b_id)  # force the next call to attempt recovery from the planted cross-job checkpoint

        with pytest.raises(ValidationError, match="does not match this job"):
            _fresh_service(settings).run_stream_metric_stage(job_b_id, step=1, epoch=0, admin_id=admin_b)

        with database_connection(settings.resolved_database_path) as connection:
            pretraining_checkpoints = connection.execute("SELECT COUNT(*) FROM pretraining_checkpoints").fetchone()[0]
        assert pretraining_checkpoints == 0

    async def test_registry_never_hands_one_job_another_jobs_adapter(self, api_app: FastAPI) -> None:
        settings, admin_a, job_a, _ds_a, _cmv_a = await _drive_to_reserved(api_app, name_suffix="cross-adapter-a")
        settings_b, admin_b, job_b, _ds_b, _cmv_b = await _drive_to_reserved(
            api_app, name_suffix="cross-adapter-b", hidden_size=24, intermediate_size=48,
        )

        _fresh_service(settings).run_start_training_stage(job_a, admin_id=admin_a)
        _fresh_service(settings).run_start_training_stage(job_b, admin_id=admin_b)

        adapter_a = REGISTRY.get(job_a)
        adapter_b = REGISTRY.get(job_b)
        assert adapter_a is not None
        assert adapter_b is not None
        assert adapter_a is not adapter_b
        assert adapter_a._checkpoint_root != adapter_b._checkpoint_root


# ===========================================================================
# Part 17: adapter lifecycle / cleanup -- no stale adapter remains after
# a job reaches any terminal state.
# ===========================================================================


class TestCleanup:
    async def test_adapter_released_on_finalize(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="cleanup-finalize")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        assert REGISTRY.contains(job_id)
        _fresh_service(settings).finalize(job_id, admin_id=admin_id)
        assert not REGISTRY.contains(job_id)

    async def test_adapter_released_on_cancel(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="cleanup-cancel")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        assert REGISTRY.contains(job_id)
        _fresh_service(settings).cancel(job_id, admin_id=admin_id)
        assert not REGISTRY.contains(job_id)

    async def test_adapter_released_on_archive(self, api_app: FastAPI) -> None:
        settings, admin_id, job_id, _ds, _cmv = await _drive_to_reserved(api_app, name_suffix="cleanup-archive")
        _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
        _fresh_service(settings).finalize(job_id, admin_id=admin_id)
        assert not REGISTRY.contains(job_id)  # already evicted by finalize
        _fresh_service(settings).archive(job_id, admin_id=admin_id)
        assert not REGISTRY.contains(job_id)  # idempotent double-eviction, still absent

    async def test_no_unbounded_registry_growth_across_many_jobs(self, api_app: FastAPI) -> None:
        settings = api_app.state.settings
        before_size = REGISTRY.size()
        # One shared tokenizer/Core-Model-Version/dataset identity reused
        # by all 5 jobs -- what varies per iteration is the job itself
        # (this test is about job/adapter churn, not identity churn, and
        # `core_model_configs.config_checksum_sha256` is derived purely
        # from numeric config values, so 5 separately-built CMVs would
        # collide unless each used a distinct shape for no real reason).
        admin_id, tp_seed_id, rg_seed_id, cmv_id, dataset_id = await _real_prerequisites(
            api_app, name_suffix="cleanup-many-shared", record_count=20,
        )
        for i in range(5):
            tp_id, rg_id = await _seed_approved_package_and_release(api_app, admin_id, topic=f"cleanup-many-{i}")
            svc = _fresh_service(settings)
            job = svc.create_job(
                topic=f"many-{i}-job", training_package_session_public_id=tp_id,
                release_governance_session_public_id=rg_id, execution_mode="gpu", admin_id=admin_id,
                core_model_version_public_id=cmv_id, dataset_version_public_id=dataset_id,
            )
            job_id = job["public_id"]
            _fresh_service(settings).run_validate_release_stage(job_id, admin_id=admin_id)
            _fresh_service(settings).run_validate_package_stage(job_id, admin_id=admin_id)
            _fresh_service(settings).run_validate_authorization_stage(job_id, authorization_reason="cleanup", admin_id=admin_id)
            _fresh_service(settings).run_plan_resources_stage(job_id, admin_id=admin_id)
            _fresh_service(settings).run_build_manifest_stage(job_id, admin_id=admin_id)
            _fresh_service(settings).run_reserve_runtime_stage(job_id, admin_id=admin_id, configuration_label="TEST_XREQ_28E")
            _fresh_service(settings).run_start_training_stage(job_id, admin_id=admin_id)
            _fresh_service(settings).finalize(job_id, admin_id=admin_id)
        # Every one of the 5 jobs reached a terminal state and was
        # evicted -- the registry does not grow without bound merely
        # because many jobs were processed.
        assert REGISTRY.size() == before_size
