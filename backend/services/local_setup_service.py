"""MB-29: Local Model Auto-Setup & Provider Configuration Center --
orchestration layer.

All persistence reuses MB-27's `MiniBrainProviderSettingsService`
directly -- this service creates no new tables and writes no SQL of
its own. Model-path confinement reuses MB-28's own
`resolve_confined_model_path()` (not re-implemented). No file is ever
downloaded automatically; "save" only ever writes a path/config an
admin already typed in.

`additional_model_dirs` (admin-configured extra directories to scan,
required by the phase spec's section 4 but not explicitly drawn in
section 9's Local Configuration wireframe) is exposed as an optional
extra field on `save_local_model_configuration()` / `POST
/save-local-model` -- disclosed here as the minimal, additive UI
surface needed to make that stated scanning capability actually
configurable, since no dedicated route exists for it in the spec's
8-route list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.services.mini_brain_llm_adapter import LlamaCppMiniBrainAdapter, resolve_confined_model_path
from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService
from core_model.mini_brain.local_setup import (
    diagnostics_formatter,
    hardware_probe,
    health_status_builder,
    model_recommender,
    model_scanner,
    provider_model_catalog,
    setup_guide_builder,
)


class LocalSetupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider_service = MiniBrainProviderSettingsService(settings)

    # -- internal helpers -------------------------------------------------------------

    def _local_llm_setting(self) -> dict[str, Any] | None:
        for item in self.provider_service.list_settings(provider_type="local_model")["items"]:
            if item["provider_key"] == "local_llm":
                return item
        return None

    def _additional_model_dirs(self) -> list[Path]:
        setting = self._local_llm_setting()
        raw_dirs = (setting or {}).get("config", {}).get("additional_model_dirs") or []
        resolved_dirs: list[Path] = []
        for raw in raw_dirs:
            try:
                resolved = Path(raw).resolve()
            except OSError:
                continue
            if resolved.is_dir():
                resolved_dirs.append(resolved)
        return resolved_dirs

    def _configured_model_path(self) -> str | None:
        setting = self._local_llm_setting()
        return (setting or {}).get("config", {}).get("model_path") if setting else None

    def _local_model_available(self, model_path: str | None) -> bool:
        if not model_path:
            return False
        return LlamaCppMiniBrainAdapter(settings=self.settings, model_path=model_path).is_available()

    # -- capabilities ------------------------------------------------------------------

    def hardware_summary(self) -> dict[str, Any]:
        hardware = hardware_probe.probe(disk_check_path=self.settings.resolved_allowed_model_dir)
        model_path = self._configured_model_path()
        health = health_status_builder.build(
            hardware=hardware, local_model_configured=bool(model_path),
            local_model_available=self._local_model_available(model_path),
        )
        return {**hardware, "health": health}

    def scan_local_models(self) -> dict[str, Any]:
        roots = [self.settings.resolved_allowed_model_dir, *self._additional_model_dirs()]
        seen_paths: set[str] = set()
        items: list[dict[str, Any]] = []
        scanned_dirs: list[str] = []
        for root in roots:
            scanned_dirs.append(str(root))
            if not root.exists():
                continue
            for entry in model_scanner.scan_directory(root):
                if entry["absolute_path"] in seen_paths:
                    continue
                seen_paths.add(entry["absolute_path"])
                items.append(entry)
        return {"items": items, "scanned_directories": scanned_dirs}

    def recommend_models(self) -> dict[str, Any]:
        hardware = hardware_probe.probe(disk_check_path=self.settings.resolved_allowed_model_dir)
        return model_recommender.recommend(
            total_ram_gb=hardware["total_ram_gb"], recommended_ram_tier=hardware["recommended_ram_tier"],
        )

    def save_local_model_configuration(
        self, *, model_path: str | None, context_length: int, max_tokens: int, temperature: float,
        threads: int, additional_model_dirs: list[str] | None = None, admin_id: str,
    ) -> dict[str, Any]:
        if model_path and resolve_confined_model_path(settings=self.settings, model_path=model_path) is None:
            raise ValidationError(
                "model_path must resolve to a real, existing file inside the allowed model directory"
            )

        existing = self._local_llm_setting()
        config: dict[str, Any] = {
            "model_path": model_path, "context_length": context_length, "max_tokens": max_tokens,
            "temperature": temperature, "threads": threads,
        }
        if additional_model_dirs is not None:
            config["additional_model_dirs"] = additional_model_dirs
        elif existing is not None and "additional_model_dirs" in existing.get("config", {}):
            config["additional_model_dirs"] = existing["config"]["additional_model_dirs"]

        if existing is None:
            return self.provider_service.create_provider_setting(
                provider_key="local_llm", enabled=True, config=config, admin_id=admin_id,
            )
        return self.provider_service.update_provider_setting(existing["public_id"], config=config, admin_id=admin_id)

    def save_external_provider_configuration(
        self, *, provider_key: str, api_key: str | None, model: str | None, enabled: bool, admin_id: str,
    ) -> dict[str, Any]:
        if provider_key not in provider_model_catalog.known_external_providers():
            raise ValidationError(f"unknown external provider: {provider_key}")

        existing = None
        for item in self.provider_service.list_settings(provider_type="external_ai")["items"]:
            if item["provider_key"] == provider_key:
                existing = item
                break

        setting: dict[str, Any]
        if existing is None:
            setting = self.provider_service.create_provider_setting(
                provider_key=provider_key, enabled=False, config={"model": model} if model else {}, admin_id=admin_id,
            )
        elif model:
            setting = self.provider_service.update_provider_setting(existing["public_id"], config={"model": model}, admin_id=admin_id)
        else:
            setting = existing

        if api_key:
            setting = self.provider_service.set_secret(setting["public_id"], secret_name="api_key", raw_value=api_key, admin_id=admin_id)

        if enabled and not setting["enabled"]:
            setting = self.provider_service.enable_provider(setting["public_id"], admin_id=admin_id)
        elif not enabled and setting["enabled"]:
            setting = self.provider_service.disable_provider(setting["public_id"], admin_id=admin_id)

        return setting

    def provider_catalog(self) -> dict[str, Any]:
        return provider_model_catalog.full_catalog()

    def build_setup_guide(self) -> dict[str, Any]:
        hardware = self.hardware_summary()
        scan = self.scan_local_models()
        recommendation = self.recommend_models()
        return setup_guide_builder.build_guide(
            hardware=hardware, scanned_model_count=len(scan["items"]),
            top_recommendation=recommendation["top_recommendation"],
            local_model_configured=bool(self._configured_model_path()),
        )

    def diagnostics(self) -> dict[str, Any]:
        hardware = hardware_probe.probe(disk_check_path=self.settings.resolved_allowed_model_dir)
        scan = self.scan_local_models()
        model_path = self._configured_model_path()
        external_items = self.provider_service.list_settings(provider_type="external_ai", enabled=True)["items"]
        return diagnostics_formatter.build_diagnostics(
            hardware=hardware, scanned_model_count=len(scan["items"]), configured_model_path=model_path,
            local_model_available=self._local_model_available(model_path),
            additional_model_dirs_count=len(self._additional_model_dirs()),
            configured_external_providers=[item["provider_key"] for item in external_items],
        )


__all__ = ["LocalSetupService"]
