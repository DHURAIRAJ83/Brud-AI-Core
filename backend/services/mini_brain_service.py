"""MB-01: Brud Mini Brain -- foundation service.

Composes `MiniBrainRepository` (storage) and `MiniBrainRuntime`
(in-process lifecycle skeleton) exactly the way every other feature in
this codebase composes a repository with a runtime/domain layer --
this file is the only place that talks to both. It never touches
`admin_assistant_*` tables/services or `InferenceRuntimeService`:
Mini Brain's independence from the existing Admin Assistant is
enforced here, not just in the database schema.
"""

from __future__ import annotations

import time
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain import MiniBrainRepository, public_row
from backend.services.mini_brain_runtime import MiniBrainNotImplementedError, MiniBrainRuntime
from core_model.mini_brain.config import DEFAULT_CONFIG, validate_config
from core_model.mini_brain.status import decide_health
from core_model.mini_brain.version import version_info


class MiniBrainService:
    def __init__(self, repository: MiniBrainRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # -- status / settings --------------------------------------------

    def get_status(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = public_row(self.repository.ensure_settings_row(connection))
        health = decide_health(
            enabled=bool(row["enabled"]),
            runtime_status=row["runtime_status"],
            config_valid=not validate_config({**DEFAULT_CONFIG, **row["config"]}),
        )
        return {**row, "health": health, "version": version_info()}

    def get_settings(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.ensure_settings_row(connection))

    def update_settings(self, payload: dict[str, Any], admin_id: str) -> dict[str, Any]:
        merged_config = {**DEFAULT_CONFIG, **payload.get("config", {})}
        issues = validate_config(merged_config)
        if issues:
            raise ValidationError(f"invalid mini brain configuration: {issues}")
        with self.repository.transaction() as connection:
            row = public_row(
                self.repository.update_settings(
                    connection, fields={"config_json": merged_config}, admin_public_id=admin_id
                )
            )
            self.repository.record_event(
                connection,
                event_type="config_updated",
                message="Mini Brain configuration updated",
                details={"config": merged_config},
                actor_admin_public_id=admin_id,
            )
        return row

    # -- enable / disable (module lifecycle) ---------------------------

    def enable(self, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            current = public_row(self.repository.ensure_settings_row(connection))
            runtime = MiniBrainRuntime(config={**DEFAULT_CONFIG, **current["config"]})
            try:
                result = runtime.start()
            except MiniBrainNotImplementedError as exc:
                self.repository.record_event(
                    connection, event_type="runtime_error", level="error",
                    message=str(exc), actor_admin_public_id=admin_id,
                )
                raise ValidationError(str(exc)) from exc
            row = public_row(
                self.repository.update_settings(
                    connection,
                    fields={
                        "enabled": 1, "runtime_status": result["status"],
                        "last_started_at": _now_sql(),
                    },
                    admin_public_id=admin_id,
                )
            )
            self.repository.record_event(
                connection, event_type="module_enabled",
                message="Mini Brain module enabled", actor_admin_public_id=admin_id,
            )
            self.repository.record_event(
                connection, event_type="runtime_started",
                message="Mini Brain runtime skeleton started (no model loaded)",
                actor_admin_public_id=admin_id,
            )
        return row

    def disable(self, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            current = public_row(self.repository.ensure_settings_row(connection))
            runtime = MiniBrainRuntime(config={**DEFAULT_CONFIG, **current["config"]})
            runtime.status = current["runtime_status"]
            result = runtime.stop() if runtime.status != "stopped" else {"status": "stopped"}
            row = public_row(
                self.repository.update_settings(
                    connection,
                    fields={
                        "enabled": 0, "runtime_status": result["status"],
                        "last_stopped_at": _now_sql(),
                    },
                    admin_public_id=admin_id,
                )
            )
            self.repository.record_event(
                connection, event_type="module_disabled",
                message="Mini Brain module disabled", actor_admin_public_id=admin_id,
            )
            self.repository.record_event(
                connection, event_type="runtime_stopped",
                message="Mini Brain runtime skeleton stopped", actor_admin_public_id=admin_id,
            )
        return row

    # -- health / diagnostics / logs -----------------------------------

    def health(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = public_row(self.repository.ensure_settings_row(connection))
            result = decide_health(
                enabled=bool(row["enabled"]),
                runtime_status=row["runtime_status"],
                config_valid=not validate_config({**DEFAULT_CONFIG, **row["config"]}),
            )
            self.repository.update_settings(
                connection,
                fields={
                    "last_health_check_at": _now_sql(),
                    "last_health_status": result["status"],
                },
                admin_public_id=None,
            )
            self.repository.record_event(
                connection, event_type="health_check",
                message=f"health check: {result['status']}", details=result,
            )
        return result

    def diagnostics(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = public_row(self.repository.ensure_settings_row(connection))
            event_count = self.repository.count_events(connection)
        config = {**DEFAULT_CONFIG, **row["config"]}
        return {
            "settings": row,
            "config_issues": validate_config(config),
            "event_count": event_count,
            "version": version_info(),
            "runtime_backend": config.get("runtime_backend"),
            "model_integrated": False,
        }

    def list_logs(self, *, limit: int = 25, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = [public_row(row) for row in self.repository.list_events(
                connection, limit=limit, offset=offset
            )]
            total = self.repository.count_events(connection)
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    def version(self) -> dict[str, Any]:
        return version_info()

    # -- placeholder interfaces (never fabricate a result) --------------

    def _placeholder(self, interface: str, admin_id: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            self.repository.record_event(
                connection, event_type="placeholder_call",
                message=f"{interface} interface called (not implemented in MB-01)",
                details={"interface": interface}, actor_admin_public_id=admin_id,
            )
        return {
            "available": False,
            "interface": interface,
            "reason": "not_implemented_in_mb01",
            "message": "Brud Mini Brain ships no model in MB-01 -- this is a placeholder "
            "interface reserved for a future phase.",
        }

    def placeholder_inference(self, admin_id: str) -> dict[str, Any]:
        return self._placeholder("inference", admin_id)

    def placeholder_knowledge(self, admin_id: str) -> dict[str, Any]:
        return self._placeholder("knowledge", admin_id)

    def placeholder_memory(self, admin_id: str) -> dict[str, Any]:
        return self._placeholder("memory", admin_id)

    def placeholder_suggestion(self, admin_id: str) -> dict[str, Any]:
        return self._placeholder("suggestion", admin_id)

    def placeholder_context(self, admin_id: str) -> dict[str, Any]:
        """MB-02's Brud Context Interface -- what Mini Brain will use
        to understand the Admin Dashboard, dataset rules, training
        workflow, and RAG workflow it runs alongside. Not implemented
        in MB-01."""

        return self._placeholder("context", admin_id)


def _now_sql() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
