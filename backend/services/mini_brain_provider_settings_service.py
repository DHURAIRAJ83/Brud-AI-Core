"""MB-27: Brud AI Secrets & Provider Settings UI -- orchestration
layer. Admin-only, configuration-only: no route or method in this
service starts inference, training, or deployment; the only outbound
network call anywhere in this phase happens inside `test_connection()`,
and only when an admin explicitly requests it.

Secret handling discipline, enforced structurally, not just by
convention:
  - `set_secret()` calls `secret_encryptor.encrypt_secret()` BEFORE any
    repository write -- the plaintext value never reaches the database.
  - `get_setting()`/`list_settings()` read secret rows only to extract
    `secret_name` for masking (via `secret_masker`) -- `encrypted_value`
    is never assigned to a variable that survives past that read.
  - `test_connection()` decrypts into a local variable, calls the
    adapter, and lets that variable fall out of scope at return --
    never logged, never assigned to `self`, never included in the
    audit event or the returned result.
  - `export_settings()` calls `repository.list_settings()` ONLY -- it
    never calls `list_secrets()` at all, a structural guarantee that
    secrets cannot appear in an export, not merely a masking step.
  - `import_settings_metadata()` validates via
    `settings_import_validator` (which rejects any `encrypted_value`-
    shaped key) and never creates or updates a secret.

If `BRUD_SECRET_ENCRYPTION_KEY` is not configured,
`EncryptionUnavailableError` propagates from `secret_encryptor.py`
rather than ever silently generating and persisting a new key -- the
phase spec is explicit: "Never auto-generate and silently persist a
key."
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_provider_settings import (
    MiniBrainProviderSettingsRepository,
    public_audit_event_row,
    public_memory_row,
    public_setting_row,
)
from backend.services.provider_settings_connection_adapters import adapter_for_provider
from core_model.mini_brain.provider_settings import (
    audit_event_builder,
    connection_test_request,
    connection_test_result,
    diagnostics_builder,
    provider_health_summary,
    provider_registry,
    provider_settings_sanitizer,
    provider_summary_builder,
    provider_validator,
    secret_encryptor,
    settings_export_builder,
    settings_import_validator,
)


class MiniBrainProviderSettingsService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainProviderSettingsRepository(settings.resolved_database_path)

    # -- diagnostics ------------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        encryption_available = secret_encryptor.encryption_available()
        with self.repository.transaction() as connection:
            setting_rows = self.repository.list_settings(connection)
            health_summaries = []
            unavailable_providers = []
            for row in setting_rows:
                secret_rows = self.repository.list_secrets(connection, setting_public_id=row["public_id"])
                present = [secret_row["secret_name"] for secret_row in secret_rows]
                health = provider_health_summary.summarize(
                    provider_key=row["provider_key"], enabled=bool(row["enabled"]), present_secret_names=present,
                )
                health_summaries.append(health)
                if health["health"] in ("unconfigured", "degraded"):
                    unavailable_providers.append(row["provider_key"])

        enabled_count = sum(1 for row in setting_rows if row["enabled"])
        return provider_settings_sanitizer.sanitize(
            diagnostics_builder.build(
                encryption_available=encryption_available,
                configured_provider_count=len(setting_rows),
                enabled_provider_count=enabled_count,
                provider_health=health_summaries,
                unavailable_providers=unavailable_providers,
            )
        )

    # -- helpers -------------------------------------------------------------

    def _audit(
        self, connection, *, provider_key: str, setting_public_id: str | None, action: str,
        admin_id: str | None, changed_fields: list[str],
    ) -> None:
        record = audit_event_builder.build(
            provider_key=provider_key, setting_public_id=setting_public_id, action=action,
            admin_id=admin_id, changed_fields=changed_fields,
        )
        self.repository.create_audit_event(connection, **record)
        try:
            from backend.services.mini_brain_dashboard_context_service import (
                MiniBrainDashboardContextService,
            )
            MiniBrainDashboardContextService.invalidate_cache(f"provider_{action}")
        except Exception:
            pass

    def _memory(self, connection, *, provider_key: str, setting_public_id: str, event_type: str, recorded_by: str) -> None:
        self.repository.create_memory(
            connection, provider_key=provider_key, setting_public_id=setting_public_id,
            event_type=event_type, recorded_by=recorded_by,
        )

    def _build_summary(self, connection, setting_row) -> dict[str, Any]:
        secret_rows = self.repository.list_secrets(connection, setting_public_id=setting_row["public_id"])
        secret_dicts = [{"secret_name": row["secret_name"], "updated_at": row["updated_at"]} for row in secret_rows]
        summary = provider_summary_builder.build(setting_row=dict(public_setting_row(setting_row)), secret_rows=secret_dicts)
        return provider_settings_sanitizer.sanitize(summary)

    # -- reads -----------------------------------------------------------------

    def get_setting(self, setting_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            return self._build_summary(connection, setting_row)

    def list_settings(self, *, provider_type: str | None = None, enabled: bool | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_settings(connection, provider_type=provider_type, enabled=enabled)
            items = [self._build_summary(connection, row) for row in rows]
        return {"items": items}

    def list_audit_events(self, setting_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            rows = self.repository.list_audit_events(
                connection, provider_key=setting_row["provider_key"], limit=limit, offset=offset,
            )
        return {"items": [public_audit_event_row(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    # -- create / update ---------------------------------------------------------

    def create_provider_setting(self, *, provider_key: str, enabled: bool, config: dict[str, Any], admin_id: str) -> dict[str, Any]:
        key_check = provider_validator.validate_provider_key(provider_key)
        if not key_check["valid"]:
            raise ValidationError("; ".join(key_check["errors"]))
        config_check = provider_validator.validate_config(provider_key=provider_key, config=config)
        if not config_check["valid"]:
            raise ValidationError("; ".join(config_check["errors"]))

        with self.repository.transaction() as connection:
            existing = self.repository.get_setting_by_provider_key(connection, provider_key)
            if existing is not None:
                raise ValidationError(f"a setting for provider '{provider_key}' already exists")
            provider_type = provider_registry.provider_type_for(provider_key)
            public_id = self.repository.create_setting(
                connection, provider_key=provider_key, provider_type=provider_type, enabled=enabled, config=config,
            )
            self._audit(
                connection, provider_key=provider_key, setting_public_id=public_id, action="created",
                admin_id=admin_id, changed_fields=["provider_key", "enabled", "config"],
            )
            self._memory(connection, provider_key=provider_key, setting_public_id=public_id, event_type="created", recorded_by=admin_id)
            setting_row = self.repository.get_setting(connection, public_id)
            return self._build_summary(connection, setting_row)

    def update_provider_setting(self, setting_public_id: str, *, config: dict[str, Any] | None, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            if config is None:
                return self._build_summary(connection, setting_row)
            config_check = provider_validator.validate_config(provider_key=setting_row["provider_key"], config=config)
            if not config_check["valid"]:
                raise ValidationError("; ".join(config_check["errors"]))
            self.repository.update_setting(connection, setting_public_id, {"config_json": config})
            self._audit(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                action="updated", admin_id=admin_id, changed_fields=["config"],
            )
            updated_row = self.repository.get_setting(connection, setting_public_id)
            return self._build_summary(connection, updated_row)

    def enable_provider(self, setting_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            self.repository.update_setting(connection, setting_public_id, {"enabled": True})
            self._audit(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                action="enabled", admin_id=admin_id, changed_fields=["enabled"],
            )
            self._memory(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                event_type="enabled", recorded_by=admin_id,
            )
            updated_row = self.repository.get_setting(connection, setting_public_id)
            return self._build_summary(connection, updated_row)

    def disable_provider(self, setting_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            self.repository.update_setting(connection, setting_public_id, {"enabled": False})
            self._audit(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                action="disabled", admin_id=admin_id, changed_fields=["enabled"],
            )
            self._memory(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                event_type="disabled", recorded_by=admin_id,
            )
            updated_row = self.repository.get_setting(connection, setting_public_id)
            return self._build_summary(connection, updated_row)

    def archive_provider_setting(self, setting_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            self.repository.archive_setting(connection, setting_public_id)
            self._audit(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                action="archived", admin_id=admin_id, changed_fields=["archived", "enabled"],
            )
            self._memory(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                event_type="archived", recorded_by=admin_id,
            )
            updated_row = self.repository.get_setting(connection, setting_public_id)
            return self._build_summary(connection, updated_row)

    # -- secrets ------------------------------------------------------------------

    def set_secret(self, setting_public_id: str, *, secret_name: str, raw_value: str, admin_id: str) -> dict[str, Any]:
        # Encrypt BEFORE any repository call -- the plaintext value is never
        # passed to a database write.
        encrypted_value = secret_encryptor.encrypt_secret(raw_value)
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            self.repository.upsert_secret(
                connection, setting_public_id=setting_public_id, secret_name=secret_name, encrypted_value=encrypted_value,
            )
            self._audit(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                action="secret_set", admin_id=admin_id,
                changed_fields=[audit_event_builder.secret_field_name(secret_name)],
            )
            self._memory(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                event_type="secret_set", recorded_by=admin_id,
            )
            updated_row = self.repository.get_setting(connection, setting_public_id)
            return self._build_summary(connection, updated_row)

    def delete_secret(self, setting_public_id: str, *, secret_name: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            self.repository.delete_secret(connection, setting_public_id=setting_public_id, secret_name=secret_name)
            self._audit(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                action="secret_deleted", admin_id=admin_id,
                changed_fields=[audit_event_builder.secret_field_name(secret_name)],
            )
            self._memory(
                connection, provider_key=setting_row["provider_key"], setting_public_id=setting_public_id,
                event_type="secret_deleted", recorded_by=admin_id,
            )
            updated_row = self.repository.get_setting(connection, setting_public_id)
            return self._build_summary(connection, updated_row)

    # -- connection test ------------------------------------------------------------

    def test_connection(
        self, setting_public_id: str, *, secret_name: str = "api_key", timeout_seconds: float | None = None, admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            setting_row = self.repository.get_setting(connection, setting_public_id)
            secret_row = self.repository.get_secret(connection, setting_public_id=setting_public_id, secret_name=secret_name)
        provider_key = setting_row["provider_key"]

        decrypted = None
        if secret_row is not None:
            decrypted = secret_encryptor.decrypt_secret(secret_row["encrypted_value"])

        request = connection_test_request.build(
            provider_key=provider_key, decrypted_api_key=decrypted, timeout_seconds=timeout_seconds,
        )
        adapter = adapter_for_provider(provider_key)
        raw_result = adapter.test_connection(
            api_key=request["decrypted_api_key"], timeout_seconds=request["timeout_seconds"],
        )
        decrypted = None  # never persisted, never logged; explicitly cleared here too

        result = connection_test_result.normalize(provider_key=provider_key, raw_result=raw_result)

        with self.repository.transaction() as connection:
            self._audit(
                connection, provider_key=provider_key, setting_public_id=setting_public_id,
                action="test_connection", admin_id=admin_id, changed_fields=[],
            )
            self._memory(
                connection, provider_key=provider_key, setting_public_id=setting_public_id,
                event_type="test_connection_run", recorded_by=admin_id,
            )
        return provider_settings_sanitizer.sanitize(result)

    # -- export / import ------------------------------------------------------------

    def export_settings(self) -> dict[str, Any]:
        # Deliberately never calls list_secrets() -- a structural
        # guarantee, not just a masking step.
        with self.repository.transaction() as connection:
            rows = self.repository.list_settings(connection)
            setting_dicts = [public_setting_row(row) for row in rows]
        return provider_settings_sanitizer.sanitize(settings_export_builder.build(setting_dicts))

    def import_settings_metadata(self, payload: dict[str, Any], *, admin_id: str) -> dict[str, Any]:
        validation = settings_import_validator.validate(payload)
        if not validation["valid"]:
            raise ValidationError("; ".join(validation["errors"]))

        updated = []
        with self.repository.transaction() as connection:
            for entry in validation["providers"]:
                existing = self.repository.get_setting_by_provider_key(connection, entry["provider_key"])
                if existing is None:
                    continue
                fields: dict[str, Any] = {}
                if "enabled" in entry:
                    fields["enabled"] = bool(entry["enabled"])
                if "config" in entry:
                    fields["config_json"] = entry["config"]
                if fields:
                    self.repository.update_setting(connection, existing["public_id"], fields)
                    self._audit(
                        connection, provider_key=entry["provider_key"], setting_public_id=existing["public_id"],
                        action="imported", admin_id=admin_id, changed_fields=sorted(fields.keys()),
                    )
                updated_row = self.repository.get_setting(connection, existing["public_id"])
                updated.append(self._build_summary(connection, updated_row))
        return {"items": updated}


__all__ = ["MiniBrainProviderSettingsService"]
