"""MB-30: Production Runtime Manager & One-Click Local Model Lifecycle
-- orchestration layer. This is the one designated impure module for
this phase (the same "one impure exception" pattern MB-25/27/28
already established) -- real streamed HTTP downloads, real file
writes/reads, real checksum computation over real bytes, and real
model loading all live here; `core_model.mini_brain.runtime_manager`
stays strictly pure.

Reuses rather than duplicates: `LocalSetupService.
save_local_model_configuration()` (MB-29) is what actually makes a
loaded model visible to MB-28's chat -- `load_model()`/`unload_model()`
call it directly instead of writing to MB-27's provider settings
table themselves. `LlamaCppMiniBrainAdapter`/`MockMiniBrainAdapter`
(MB-28) are reused directly for both loading and benchmarking -- no
second inference path is invented.

Honest limitation: `download_model()` makes a genuine `httpx` streamed
GET to a real Hugging Face URL -- real, correct code -- but is never
exercised against a live network call in this codebase's own test
suite (mocked via `httpx.stream` patching), the same real-but-
unexercised-without-live-network pattern MB-27's external provider
adapters already established.
"""

from __future__ import annotations

import hashlib
import resource
import shutil
import time
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.mini_brain_runtime_manager import (
    MiniBrainRuntimeManagerRepository,
    public_event_row,
    public_installation_row,
    public_memory_row,
    public_runtime_row,
)
from backend.services.local_setup_service import LocalSetupService
from backend.services.mini_brain_llm_adapter import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_THREADS,
    LlamaCppMiniBrainAdapter,
    MockMiniBrainAdapter,
)
from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService
from core_model.mini_brain.local_setup import hardware_probe
from core_model.mini_brain.runtime_manager import (
    benchmark_scorer,
    checksum_verifier,
    disk_space_guard,
    fallback_orchestrator,
    install_plan_builder,
    model_catalog,
    ram_guard,
    runtime_state_builder,
    uninstall_planner,
)

_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_DOWNLOAD_TIMEOUT_SECONDS = 120.0


class RuntimeManagerService:
    def __init__(self, settings: Settings, *, adapter_factory: Any = None) -> None:
        self.settings = settings
        self.repository = MiniBrainRuntimeManagerRepository(settings.resolved_database_path)
        self.local_setup_service = LocalSetupService(settings)
        self.provider_service = MiniBrainProviderSettingsService(settings)
        # test seam only -- production always resolves LlamaCppMiniBrainAdapter directly.
        self._adapter_factory = adapter_factory

    # -- internal helpers ----------------------------------------------------------------

    def _event(self, *, model_name: str | None, event_type: str, admin_id: str | None, detail: dict[str, Any]) -> None:
        with self.repository.transaction() as connection:
            self.repository.create_event(connection, model_name=model_name, event_type=event_type, admin_id=admin_id, detail=detail)

    def _memory(self, *, model_name: str | None, event_type: str, admin_id: str | None) -> None:
        with self.repository.transaction() as connection:
            self.repository.create_memory(connection, model_name=model_name, event_type=event_type, admin_id=admin_id)

    def _current_adapter(self, model_path: str | None):
        if self._adapter_factory is not None:
            return self._adapter_factory()
        return LlamaCppMiniBrainAdapter(settings=self.settings, model_path=model_path)

    @staticmethod
    def _runtime_backend_label(adapter: Any) -> str:
        """Maps an MB-28 adapter instance to this phase's own
        CHECK-constrained backend vocabulary (llama_cpp/mock/external/
        none) -- MB-28's own `backend_type` attribute uses a different,
        coarser vocabulary ("local"/"external") that both
        LlamaCppMiniBrainAdapter and MockMiniBrainAdapter share, so a
        class-identity check is required to tell them apart here."""
        if isinstance(adapter, LlamaCppMiniBrainAdapter):
            return "llama_cpp"
        if isinstance(adapter, MockMiniBrainAdapter):
            return "mock"
        if getattr(adapter, "backend_type", None) == "external":
            return "external"
        return "none"

    # -- 1: detect_system ------------------------------------------------------------------

    def detect_system(self) -> dict[str, Any]:
        return hardware_probe.probe(disk_check_path=self.settings.resolved_allowed_model_dir)

    # -- 2: list_installed_models -----------------------------------------------------------

    def list_installed_models(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_installations(connection, status="installed")
        return {"items": [public_installation_row(row) for row in rows]}

    # -- 3: get_recommended_model -------------------------------------------------------------

    def get_recommended_model(self) -> dict[str, Any]:
        model_id = model_catalog.recommended_model_id()
        entry = model_catalog.catalog_entry(model_id)
        return {"model_id": model_id, **entry}

    # -- 4: create_download_plan --------------------------------------------------------------

    def create_download_plan(self, model_id: str) -> dict[str, Any]:
        entry = model_catalog.catalog_entry(model_id)
        if entry is None:
            raise ValidationError(f"unknown model_id: {model_id}")
        return install_plan_builder.build_plan(
            model_id=model_id, catalog_entry=entry, allowed_model_dir=str(self.settings.resolved_allowed_model_dir),
        )

    # -- 5: download_model (real network -- the phase's one designated network call) -----------

    def download_model(self, model_id: str, *, admin_id: str) -> dict[str, Any]:
        import httpx

        plan = self.create_download_plan(model_id)
        target_path = Path(plan["target_path"])
        target_path.parent.mkdir(parents=True, exist_ok=True)

        usage = shutil.disk_usage(target_path.parent)
        disk_check = disk_space_guard.check(available_bytes=usage.free, required_bytes=plan["expected_size_bytes"])
        if not disk_check["safe"]:
            self._event(model_name=model_id, event_type="download_rejected_disk_space", admin_id=admin_id, detail=disk_check)
            raise ValidationError(disk_check["message_en"])

        with self.repository.transaction() as connection:
            installation_id = self.repository.create_installation(
                connection, model_name=model_id, family=plan["family"], quantization=plan["quantization"],
                file_name=plan["file_name"], install_path=plan["target_path"], file_size_bytes=None, sha256=None,
                status="downloading",
            )
        self._event(model_name=model_id, event_type="download_started", admin_id=admin_id, detail={"url": plan["download_url"]})

        hasher = hashlib.sha256()
        total_bytes = 0
        try:
            with httpx.stream("GET", plan["download_url"], follow_redirects=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
                response.raise_for_status()
                with open(target_path, "wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                        handle.write(chunk)
                        hasher.update(chunk)
                        total_bytes += len(chunk)
        except Exception as exc:  # noqa: BLE001 -- honest failure, never a crash
            with self.repository.transaction() as connection:
                self.repository.update_installation(connection, installation_id, {"status": "failed"})
            self._event(model_name=model_id, event_type="download_failed", admin_id=admin_id, detail={"error": str(exc)})
            self._memory(model_name=model_id, event_type="download_failed", admin_id=admin_id)
            target_path.unlink(missing_ok=True)
            raise ValidationError(f"download failed: {exc}") from exc

        actual_sha256 = hasher.hexdigest()
        with self.repository.transaction() as connection:
            self.repository.update_installation(
                connection, installation_id, {"file_size_bytes": total_bytes, "sha256": actual_sha256},
            )
        self._event(model_name=model_id, event_type="download_complete", admin_id=admin_id, detail={"bytes": total_bytes})

        return self.install_model(model_id, admin_id=admin_id)

    # -- 6: verify_model ------------------------------------------------------------------------

    def verify_model(self, model_id: str, *, admin_id: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            installation_row = self.repository.latest_installation_for_model(connection, model_id)
        if installation_row is None:
            raise NotFoundError(f"no installation exists for model_id: {model_id}")
        installation = public_installation_row(installation_row)

        path = Path(installation["install_path"])
        if not path.is_file():
            result = {"matches": False, "message_en": "installed file is missing", "message_ta": "நிறுவப்பட்ட கோப்பு காணவில்லை"}
        else:
            actual_sha256 = checksum_verifier.compute_sha256(path.read_bytes())
            expected = installation.get("sha256") or actual_sha256
            result = checksum_verifier.verify_digest(actual_sha256=actual_sha256, expected_sha256=expected)

        self._event(model_name=model_id, event_type="verified" if result["matches"] else "verify_failed", admin_id=admin_id, detail=result)
        return result

    # -- 7: install_model (registers/finalizes a file already on disk) --------------------------

    def install_model(
        self, model_id: str, *, file_path: str | None = None, expected_sha256: str | None = None, admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            existing = self.repository.latest_installation_for_model(connection, model_id)

        if file_path is not None:
            path = Path(file_path)
        elif existing is not None:
            path = Path(existing["install_path"])
        else:
            plan = self.create_download_plan(model_id)
            path = Path(plan["target_path"])

        if not path.is_file():
            raise ValidationError(f"no file exists at {path} to install for model_id: {model_id}")

        data = path.read_bytes()
        actual_sha256 = checksum_verifier.compute_sha256(data)
        catalog_entry = model_catalog.catalog_entry(model_id)
        reference_sha256 = expected_sha256
        if reference_sha256 is None and existing is not None and existing["sha256"]:
            reference_sha256 = existing["sha256"]

        status = "installed"
        if reference_sha256 is not None:
            verify_result = checksum_verifier.verify_digest(actual_sha256=actual_sha256, expected_sha256=reference_sha256)
            if not verify_result["matches"]:
                status = "failed"

        with self.repository.transaction() as connection:
            if existing is not None:
                installation_id = existing["public_id"]
                self.repository.update_installation(
                    connection, installation_id,
                    {"status": status, "sha256": actual_sha256, "file_size_bytes": len(data), "install_path": str(path),
                     "installed_at": None if status != "installed" else _now()},
                )
            else:
                installation_id = self.repository.create_installation(
                    connection, model_name=model_id,
                    family=(catalog_entry or {}).get("family"), quantization=(catalog_entry or {}).get("quantization"),
                    file_name=path.name, install_path=str(path), file_size_bytes=len(data), sha256=actual_sha256, status=status,
                )
                if status == "installed":
                    self.repository.update_installation(connection, installation_id, {"installed_at": _now()})
            installation = public_installation_row(self.repository.get_installation(connection, installation_id))

        event_type = "installed" if status == "installed" else "install_failed"
        self._event(model_name=model_id, event_type=event_type, admin_id=admin_id, detail={"status": status})
        if status == "installed":
            self._memory(model_name=model_id, event_type="installed", admin_id=admin_id)
        return installation

    # -- 8: load_model --------------------------------------------------------------------------

    def load_model(
        self, model_id: str, *, context_length: int = DEFAULT_CONTEXT_LENGTH, max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE, threads: int = DEFAULT_THREADS, admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            installation_row = self.repository.latest_installation_for_model(connection, model_id)
        if installation_row is None or installation_row["status"] != "installed":
            raise ValidationError(f"model_id {model_id!r} is not installed -- install it before loading")
        installation = public_installation_row(installation_row)

        hardware = hardware_probe.probe(disk_check_path=self.settings.resolved_allowed_model_dir)
        catalog_entry = model_catalog.catalog_entry(model_id) or {}
        estimated_ram_gb = catalog_entry.get("expected_ram_usage_gb", 2.5)
        ram_check = ram_guard.check_load_safety(available_ram_gb=hardware["available_ram_gb"], estimated_model_ram_gb=estimated_ram_gb)
        if not ram_check["safe"]:
            self._event(model_name=model_id, event_type="load_rejected_ram", admin_id=admin_id, detail=ram_check)
            raise ValidationError(ram_check["warning_en"])

        started = time.perf_counter()
        adapter = self._current_adapter(installation["install_path"])
        backend_type = self._runtime_backend_label(adapter)
        available = adapter.is_available()
        load_time_ms = round((time.perf_counter() - started) * 1000, 3)

        # Reuses MB-29's own save flow -- this is what makes the loaded
        # model visible to MB-28's chat, never a bespoke second write path.
        self.local_setup_service.save_local_model_configuration(
            model_path=installation["install_path"], context_length=context_length, max_tokens=max_tokens,
            temperature=temperature, threads=threads, admin_id=admin_id,
        )

        with self.repository.transaction() as connection:
            runtime_id = self.repository.create_runtime_row(
                connection, model_name=model_id, loaded=bool(available), backend=backend_type,
                context_length=context_length, max_tokens=max_tokens, temperature=temperature, threads=threads,
                load_time_ms=load_time_ms, peak_ram_mb=None, tokens_per_second=None,
            )
            runtime_row = public_runtime_row(connection.execute(
                "SELECT * FROM mini_brain_model_runtime WHERE public_id=?", (runtime_id,)
            ).fetchone())

        self._event(model_name=model_id, event_type="loaded" if available else "load_unavailable", admin_id=admin_id, detail={"backend": backend_type})
        if available:
            self._memory(model_name=model_id, event_type="loaded", admin_id=admin_id)
        return runtime_row

    # -- 9: unload_model ------------------------------------------------------------------------

    def unload_model(self, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            current = self.repository.latest_runtime_row(connection)
        model_name = current["model_name"] if current else None

        self.local_setup_service.save_local_model_configuration(
            model_path=None, context_length=DEFAULT_CONTEXT_LENGTH, max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE, threads=DEFAULT_THREADS, admin_id=admin_id,
        )

        with self.repository.transaction() as connection:
            runtime_id = self.repository.create_runtime_row(
                connection, model_name=model_name or "none", loaded=False, backend="none",
                context_length=None, max_tokens=None, temperature=None, threads=None,
                load_time_ms=None, peak_ram_mb=None, tokens_per_second=None,
            )
            runtime_row = public_runtime_row(connection.execute(
                "SELECT * FROM mini_brain_model_runtime WHERE public_id=?", (runtime_id,)
            ).fetchone())

        self._event(model_name=model_name, event_type="unloaded", admin_id=admin_id, detail={})
        self._memory(model_name=model_name, event_type="unloaded", admin_id=admin_id)
        return runtime_row

    # -- 10: benchmark_model --------------------------------------------------------------------

    def benchmark_model(self, model_id: str, *, prompt: str = "Say hello in one short sentence.", admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            installation_row = self.repository.latest_installation_for_model(connection, model_id)
        if installation_row is None or installation_row["status"] != "installed":
            raise ValidationError(f"model_id {model_id!r} is not installed -- install it before benchmarking")
        installation = public_installation_row(installation_row)

        load_started = time.perf_counter()
        adapter = self._current_adapter(installation["install_path"])
        load_time_ms = round((time.perf_counter() - load_started) * 1000, 3)

        first_token_started = time.perf_counter()
        result = adapter.generate(messages=[{"role": "admin", "content": prompt}], max_tokens=64, temperature=DEFAULT_TEMPERATURE)
        elapsed_seconds = max(time.perf_counter() - first_token_started, 1e-6)
        first_token_latency_ms = round(elapsed_seconds * 1000, 3)

        tokens_generated = max(result.get("tokens_generated", 0), 1)
        tokens_per_second = round(tokens_generated / elapsed_seconds, 2)
        peak_ram_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)

        score = benchmark_scorer.score(
            load_time_ms=load_time_ms, first_token_latency_ms=first_token_latency_ms,
            tokens_per_second=tokens_per_second, peak_ram_mb=peak_ram_mb,
        )

        with self.repository.transaction() as connection:
            runtime_id = self.repository.create_runtime_row(
                connection, model_name=model_id, loaded=adapter.is_available(), backend=self._runtime_backend_label(adapter),
                context_length=None, max_tokens=None, temperature=None, threads=None,
                load_time_ms=load_time_ms, peak_ram_mb=peak_ram_mb, tokens_per_second=tokens_per_second,
            )
            runtime_row = public_runtime_row(connection.execute(
                "SELECT * FROM mini_brain_model_runtime WHERE public_id=?", (runtime_id,)
            ).fetchone())

        self._event(model_name=model_id, event_type="benchmarked", admin_id=admin_id, detail=score)
        self._memory(model_name=model_id, event_type="benchmarked", admin_id=admin_id)
        return {**score, "runtime_row": runtime_row, "reply_error": result.get("error_message")}

    # -- 11: remove_model -----------------------------------------------------------------------

    def remove_model(self, model_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            installation_row = self.repository.latest_installation_for_model(connection, model_id)
        if installation_row is None:
            raise NotFoundError(f"no installation exists for model_id: {model_id}")
        installation = public_installation_row(installation_row)
        plan = uninstall_planner.build_removal_plan(installation=installation)

        file_path = Path(plan["file_to_delete"])
        file_path.unlink(missing_ok=True)

        with self.repository.transaction() as connection:
            self.repository.update_installation(
                connection, plan["public_id"], {"status": "removed", "removed_at": _now()},
            )
            updated = public_installation_row(self.repository.get_installation(connection, plan["public_id"]))

        self._event(model_name=model_id, event_type="removed", admin_id=admin_id, detail=plan)
        self._memory(model_name=model_id, event_type="removed", admin_id=admin_id)
        return updated

    # -- 12: runtime_status ---------------------------------------------------------------------

    def runtime_status(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            current_runtime_row = self.repository.latest_runtime_row(connection)
            installation_rows = self.repository.list_installations(connection, limit=100)
        current_runtime = public_runtime_row(current_runtime_row) if current_runtime_row else None
        installations = [public_installation_row(row) for row in installation_rows]
        hardware = hardware_probe.probe(disk_check_path=self.settings.resolved_allowed_model_dir)
        return runtime_state_builder.build_status(current_runtime=current_runtime, installations=installations, hardware=hardware)

    # -- 13: auto_fallback_status ----------------------------------------------------------------

    def auto_fallback_status(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            current_runtime_row = self.repository.latest_runtime_row(connection)
            installation_rows = self.repository.list_installations(connection, status="installed", limit=100)

        local_loaded = bool(current_runtime_row and current_runtime_row["loaded"])
        local_installed_not_loaded = bool(installation_rows) and not local_loaded
        external_items = self.provider_service.list_settings(provider_type="external_ai", enabled=True)["items"]
        external_enabled = len(external_items) > 0

        return fallback_orchestrator.decide(
            local_loaded=local_loaded, local_installed_not_loaded=local_installed_not_loaded, external_enabled=external_enabled,
        )

    # -- diagnostics helpers ---------------------------------------------------------------------

    def list_events(self, *, model_name: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_events(connection, model_name=model_name, limit=limit, offset=offset)
        return {"items": [public_event_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    def catalog(self) -> dict[str, Any]:
        return model_catalog.full_catalog()

    def diagnostics(self) -> dict[str, Any]:
        """Post-audit remediation: a single consolidated diagnostics
        view. Composes `runtime_status()` and `auto_fallback_status()`
        directly -- no repository query or hardware probe is
        duplicated here, only the two already-real methods above are
        reused and reshaped."""
        status = self.runtime_status()
        fallback = self.auto_fallback_status()
        current_runtime = status["current_model"]
        has_benchmark_data = bool(current_runtime and current_runtime.get("tokens_per_second") is not None)
        return {
            "hardware": status["hardware"],
            "model_status": {
                "installed_count": status["installed_count"],
                "installed_models": status["installed_models"],
            },
            "load_state": {
                "loaded": status["loaded"],
                "current_model": current_runtime,
            },
            "benchmark_availability": {
                "has_benchmark_data": has_benchmark_data,
                "last_benchmark": {
                    "tokens_per_second": current_runtime.get("tokens_per_second"),
                    "peak_ram_mb": current_runtime.get("peak_ram_mb"),
                    "load_time_ms": current_runtime.get("load_time_ms"),
                } if has_benchmark_data else None,
            },
            "storage_paths": {
                "allowed_model_dir": str(self.settings.resolved_allowed_model_dir),
            },
            "fallback_state": fallback,
        }


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["RuntimeManagerService"]
