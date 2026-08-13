"""MB-25: Brud Mini Brain Secure Plugin Execution Runtime -- the
orchestration layer for the task spec's own 13-stage workflow.

This is the first Mini Brain phase that actually runs plugin code --
but only ever an admin-approved, on-disk `.py` file loaded via
`importlib` (never a string from a chat message, never a downloaded
file, never `eval`/`exec`), and only after independently re-deriving
MB-24's own permission decision fresh, every single time, from MB-24's
own real repository state. MB-25 never trusts a cached or stale
decision and never bypasses MB-24: `runtime_policy_evaluator.
evaluate_permission()` -- the exact same function MB-24's own service
uses -- is called here too, with freshly-queried grant and consent
data, never a shortcut.

Filesystem and network guards are best-effort and cooperative: a
plugin's `run()` is called directly, with no container or process
isolation, so these guards only stop a well-behaved plugin that
declares its intended paths/domains up front (via its own arguments)
before this service checks them -- they cannot intercept a plugin that
imports `open`/`requests` directly and ignores the declared contract.
This is disclosed explicitly in every execution report (Step 20).
"""

from __future__ import annotations

import importlib.util
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_plugin_runtime_execution import (
    MiniBrainPluginRuntimeExecutionRepository,
    public_execution_row,
    public_io_row,
    public_memory_row,
)
from backend.services.mini_brain_plugin_governance_service import MiniBrainPluginGovernanceService
from core_model.mini_brain.plugin_governance import permission_scope_registry
from core_model.mini_brain.plugin_governance.consent_policy_engine import is_consent_valid
from core_model.mini_brain.plugin_governance.plugin_execution_token_builder import is_token_expired
from core_model.mini_brain.plugin_governance.runtime_policy_evaluator import evaluate_permission
from core_model.mini_brain.plugin_runtime import (
    admin_assistant_runtime_guard,
    audit_record_builder,
    consent_gate,
    execution_context_builder,
    execution_report_builder,
    filesystem_guard,
    network_guard,
    permission_gate,
    plugin_entrypoint_resolver,
    plugin_manifest_loader,
    plugin_runtime_policy,
    plugin_signature_checker,
    public_chat_runtime_guard,
    result_serializer,
    timeout_runner,
)
from core_model.release.artifact_inventory import file_checksum
from core_model.release.manifest import manifest_checksum

MAX_ARGUMENTS_BYTES = 8_000
_TERMINAL_STATUSES = frozenset({"completed", "failed", "timeout", "denied", "cancelled"})


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainPluginRuntimeService:
    def __init__(self, settings: Settings, *, governance: MiniBrainPluginGovernanceService | None = None) -> None:
        self.settings = settings
        self.repository = MiniBrainPluginRuntimeExecutionRepository(settings.resolved_database_path)
        self.governance = governance or MiniBrainPluginGovernanceService(settings)

    # -- diagnostics ------------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        return {
            "plugins_executed_without_mb24_approval": False,
            "plugins_executed_while_disabled": False,
            "consent_bypassed": False,
            "admin_review_bypassed": False,
            "shell_commands_executed": False,
            "subprocesses_executed": False,
            "downloaded_code_executed": False,
            "packages_auto_installed": False,
            "unrestricted_filesystem_access_permitted": False,
            "unrestricted_network_access_permitted": False,
            "raw_chat_history_accessible_without_grant": False,
            "admin_only_scopes_accessible_from_public_chat": False,
            "code_from_user_prompt_ever_executed": False,
            "container_isolation_exists": False,
            "process_isolation_exists": False,
            "cpu_quota_enforced": False,
            "memory_quota_enforced": False,
            "signed_plugin_verification_performed": False,
            "one_execution_per_request": True,
            "writes_scope": (
                "own tables only (mini_brain_plugin_runtime_executions, mini_brain_plugin_runtime_io, "
                "mini_brain_plugin_runtime_execution_events, mini_brain_plugin_runtime_execution_memory); "
                "never MB-24's own mini_brain_plugin_runtime_events/_memory tables"
            ),
        }

    # -- helpers -------------------------------------------------------------

    def _event(self, connection, execution_id: int | None, event_type: str, *, stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None) -> None:
        record = audit_record_builder.build_audit_record(
            event_type=event_type, execution_public_id=None, stage=stage, actor="system", metadata=metadata or {},
        )
        self.repository.create_event(connection, execution_id=execution_id, event_type=event_type, stage=stage, message=message, metadata=record["metadata"])

    def _resolve_package_dir(self, plugin_id_slug: str) -> Path:
        return self.settings.resolved_plugin_package_dir / plugin_id_slug

    # -- reads -----------------------------------------------------------------

    def execution(self, execution_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_execution_row(self.repository.get_execution(connection, execution_public_id))

    def list_executions(self, *, limit: int = 50, offset: int = 0, status: str | None = None, plugin_public_id: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_executions(connection, limit=limit, offset=offset, status=status, plugin_public_id=plugin_public_id)
        return {"items": [public_execution_row(row) for row in rows]}

    def list_io(self, execution_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            execution_row = self.repository.get_execution(connection, execution_public_id)
            rows = self.repository.list_io(connection, execution_id=execution_row["id"], limit=limit, offset=offset)
        return {"items": [public_io_row(row) for row in rows]}

    def list_events(self, execution_public_id: str | None = None, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            execution_id = None
            if execution_public_id:
                execution_id = self.repository.get_execution(connection, execution_public_id)["id"]
            rows = self.repository.list_events(connection, execution_id=execution_id, limit=limit, offset=offset)
        return {"items": [dict(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    def statistics(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self.repository.statistics(connection)

    # -- stage 1: create execution request --------------------------------------

    def create_execution_request(
        self, *, plugin_public_id: str, scope_key: str, arguments: dict[str, Any], execution_mode: str,
        requester_user_id_hash: str | None = None, requester_admin_public_id: str | None = None,
    ) -> dict[str, Any]:
        if execution_mode not in ("public_chat", "admin_assistant", "admin_manual"):
            raise ValidationError(f"unknown execution_mode: {execution_mode!r}")
        serialized_arguments = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
        if len(serialized_arguments.encode("utf-8")) > MAX_ARGUMENTS_BYTES:
            raise ValidationError(f"arguments exceed the maximum bound of {MAX_ARGUMENTS_BYTES} bytes")

        with self.repository.transaction() as connection:
            public_id = self.repository.create_execution(
                connection, plugin_public_id=plugin_public_id, execution_mode=execution_mode, scope_key=scope_key,
                arguments=arguments, granted_scopes=[], requester_user_id_hash=requester_user_id_hash,
                requester_admin_public_id=requester_admin_public_id,
            )
            execution_row = self.repository.get_execution(connection, public_id)
            self._event(connection, execution_row["id"], "execution_requested", stage="create_execution_request", message=f"mode={execution_mode} scope={scope_key}")
            return public_execution_row(self.repository.get_execution(connection, public_id))

    def cancel_execution(self, execution_public_id: str, *, admin_id: str) -> dict[str, Any]:
        execution_data = self.execution(execution_public_id)
        if execution_data["status"] != "pending":
            raise ValidationError(f"execution status must be 'pending' to cancel (currently '{execution_data['status']}')")
        with self.repository.transaction() as connection:
            execution_row = self.repository.get_execution(connection, execution_public_id)
            self.repository.update_execution(connection, execution_public_id, {"status": "cancelled", "completed_at": _now()})
            self._event(connection, execution_row["id"], "execution_cancelled", stage="cancel", message=f"cancelled by {admin_id}")
            return public_execution_row(self.repository.get_execution(connection, execution_public_id))

    # -- stages 2-10: run execution -----------------------------------------------------

    def _deny(self, connection, execution_public_id: str, execution_id: int, reason: str) -> dict[str, Any]:
        self.repository.update_execution(connection, execution_public_id, {"status": "denied", "denial_reason": reason, "completed_at": _now()})
        self._event(connection, execution_id, "execution_denied", stage="policy_check", message=reason)
        return public_execution_row(self.repository.get_execution(connection, execution_public_id))

    def run_execution(
        self, execution_public_id: str, *, execution_token: dict[str, Any] | None, admin_authorized: bool = False,
        timeout_seconds: float = timeout_runner.DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        execution_data = self.execution(execution_public_id)
        if execution_data["status"] != "pending":
            raise ValidationError(f"execution status must be 'pending' to run (currently '{execution_data['status']}')")

        # -- stage 2: validate plugin registration ------------------------------------
        plugin_data = self.governance.plugin(execution_data["plugin_public_id"])

        # -- stage 3: validate plugin enabled ------------------------------------------
        if plugin_data["status"] != "enabled":
            with self.repository.transaction() as connection:
                execution_row = self.repository.get_execution(connection, execution_public_id)
                return self._deny(connection, execution_public_id, execution_row["id"], f"plugin status is '{plugin_data['status']}', not 'enabled'")

        # -- stage 4: validate execution token ------------------------------------------
        if execution_token is None:
            with self.repository.transaction() as connection:
                execution_row = self.repository.get_execution(connection, execution_public_id)
                return self._deny(connection, execution_public_id, execution_row["id"], "no execution token was supplied")

        payload = execution_token["payload"]
        recomputed_hash = manifest_checksum(payload)
        token_valid = (
            recomputed_hash == execution_token["token_hash"]
            and payload["plugin_id"] == execution_data["plugin_public_id"]
            and execution_data["scope_key"] in payload["granted_scopes"]
            and not is_token_expired(expires_at_epoch_seconds=payload["expires_at"], now_epoch_seconds=time.time())
        )
        if not token_valid:
            with self.repository.transaction() as connection:
                execution_row = self.repository.get_execution(connection, execution_public_id)
                return self._deny(connection, execution_public_id, execution_row["id"], "execution token failed validation (tampered, expired, or scope mismatch)")

        # -- stages 5-6: validate permission policy + consent, re-derived fresh from MB-24 -----
        permissions = self.governance.list_permissions(execution_data["plugin_public_id"])["items"]
        granted_scope_keys = [p["scope_key"] for p in permissions if p["status"] == "granted"]

        has_valid_consent = False
        if execution_data["requester_user_id_hash"]:
            with self.governance.repository.transaction() as connection:
                gov_plugin_row = self.governance.repository.get_plugin(connection, execution_data["plugin_public_id"])
                consent_row = self.governance.repository.latest_consent(
                    connection, plugin_id=gov_plugin_row["id"], user_id_hash=execution_data["requester_user_id_hash"],
                    scope_key=execution_data["scope_key"],
                )
            if consent_row is not None:
                expires_at = consent_row["expires_at"]
                has_valid_consent = is_consent_valid(
                    consent_given=bool(consent_row["consent_given"]),
                    expires_at_epoch_seconds=(datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp() if expires_at else None),
                    now_epoch_seconds=time.time(),
                )["valid"]
        elif execution_data["execution_mode"] == "admin_assistant" and admin_authorized:
            # Admin Assistant executions have no associated end-user to grant
            # consent on behalf of -- the admin's own real, already-verified
            # authorization (never a bypass, see admin_assistant_runtime_guard)
            # is the accountable substitute when there is no user context.
            has_valid_consent = True
        elif execution_data["execution_mode"] == "admin_manual" and execution_data["requester_admin_public_id"]:
            # Same reasoning as admin_assistant: a manual admin-dashboard
            # execution has no associated end-user either -- the real admin
            # identity already required by this mode's own guard is the
            # accountable substitute.
            has_valid_consent = True

        mb24_decision = evaluate_permission(
            scope_key=execution_data["scope_key"], plugin_status=plugin_data["status"],
            is_public_chat=execution_data["execution_mode"] == "public_chat", has_valid_consent=has_valid_consent,
            admin_reviewed=plugin_data["admin_reviewed"], risk_level=plugin_data["risk_level"],
        )
        scope_definition = permission_scope_registry.scope_definition(execution_data["scope_key"]) or {}
        permission_result = permission_gate.evaluate_execution_permission(required_scope=execution_data["scope_key"], granted_scope_keys=granted_scope_keys)
        consent_result = consent_gate.evaluate_execution_consent(
            required_scope=execution_data["scope_key"], consent_required=bool(scope_definition.get("consent_required")), has_valid_consent=has_valid_consent,
        )

        if execution_data["execution_mode"] == "public_chat":
            mode_guard = public_chat_runtime_guard.evaluate_public_chat_execution(
                public_chat_enabled=plugin_data.get("public_chat_enabled", True), required_scope=execution_data["scope_key"],
            )
        elif execution_data["execution_mode"] == "admin_assistant":
            mode_guard = admin_assistant_runtime_guard.evaluate_admin_assistant_execution(
                admin_assistant_enabled=plugin_data.get("admin_assistant_enabled", True), admin_authorized=admin_authorized,
            )
        else:
            mode_guard = {"allowed": bool(execution_data["requester_admin_public_id"]), "reason": None if execution_data["requester_admin_public_id"] else "admin_manual execution requires a real admin identity"}

        policy = plugin_runtime_policy.evaluate_execution_policy(
            plugin_status=plugin_data["status"], permission_result=permission_result, consent_result=consent_result,
            mode_guard_result=mode_guard,
        )
        if mb24_decision["decision"] != "allow" or not policy["may_execute"]:
            reasons = policy["reasons"] + (mb24_decision["reasons"] if mb24_decision["decision"] != "allow" else [])
            with self.repository.transaction() as connection:
                execution_row = self.repository.get_execution(connection, execution_public_id)
                return self._deny(connection, execution_public_id, execution_row["id"], "; ".join(reasons) or "policy evaluation denied execution")

        # -- stage 7: build execution context ------------------------------------------
        sandbox = plugin_data.get("sandbox_profile") or {}
        context = execution_context_builder.build_execution_context(
            execution_public_id=execution_public_id, plugin_public_id=execution_data["plugin_public_id"],
            granted_scopes=granted_scope_keys, memory_limit_mb=sandbox.get("memory_limit_mb"),
            cpu_time_limit_ms=sandbox.get("cpu_time_limit_ms"), requester_kind=execution_data["execution_mode"],
            requester_id_hash=execution_data["requester_user_id_hash"],
        )

        # -- stage 8: apply runtime guards (declared-intent, cooperative) -----------------
        guard_violations: list[str] = []
        arguments = execution_data["arguments"]
        filesystem_policy = plugin_data.get("filesystem_policy") or {}
        network_policy = plugin_data.get("network_policy") or {}
        for requested_path in arguments.get("requested_paths", []) or []:
            check = filesystem_guard.check_path_allowed(requested_path=requested_path, allowed_roots=filesystem_policy.get("filesystem_roots", []))
            if not check["allowed"]:
                guard_violations.append(check["reason"])
        for requested_domain in arguments.get("requested_domains", []) or []:
            check = network_guard.check_domain_allowed(requested_domain=requested_domain, allowed_domains=network_policy.get("allowed_domains", []))
            if not check["allowed"]:
                guard_violations.append(check["reason"])

        if guard_violations:
            with self.repository.transaction() as connection:
                execution_row = self.repository.get_execution(connection, execution_public_id)
                return self._deny(connection, execution_public_id, execution_row["id"], "; ".join(guard_violations))

        # -- signature / checksum check ------------------------------------------------
        plugin_id_slug = plugin_data["plugin_id"]
        package_dir = self._resolve_package_dir(plugin_id_slug)
        manifest_path = package_dir / "plugin.json"
        package_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_validation = plugin_manifest_loader.validate_package_manifest(manifest=package_manifest)
        if not manifest_validation["valid"]:
            with self.repository.transaction() as connection:
                execution_row = self.repository.get_execution(connection, execution_public_id)
                return self._deny(connection, execution_public_id, execution_row["id"], f"on-disk package manifest invalid: {manifest_validation['problems']}")

        entrypoint_path = plugin_entrypoint_resolver.resolve_entrypoint(package_dir=package_dir, entrypoint=package_manifest["entrypoint"])
        actual_checksum = file_checksum(entrypoint_path)
        checksum_result = plugin_signature_checker.verify_checksum(
            expected_checksum_sha256=plugin_data.get("manifest_checksum_sha256") or None, actual_checksum_sha256=actual_checksum,
        )
        # note: MB-24's own manifest_checksum_sha256 covers the *governance* manifest,
        # not this on-disk package file -- checksum_result is recorded for audit/trust
        # visibility only and never blocks execution on its own in this phase.

        # -- stage 9: execute plugin (the one real side effect in this service) -----------
        with self.repository.transaction() as connection:
            self.repository.update_execution(connection, execution_public_id, {"status": "running", "started_at": _now()})
            execution_row = self.repository.get_execution(connection, execution_public_id)
            self._event(connection, execution_row["id"], "execution_started", stage="execute")

        spec = importlib.util.spec_from_file_location(f"mb25_plugin_{plugin_id_slug}", entrypoint_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        run_result = timeout_runner.run_with_timeout(module.run, args=(context, arguments), timeout_seconds=timeout_seconds)

        # -- stage 10: capture result ----------------------------------------------------
        sanitized_input = result_serializer.sanitize_result(result=arguments, allowed_filesystem_roots=filesystem_policy.get("filesystem_roots", []))
        sanitized_output = result_serializer.sanitize_result(
            result=run_result["result"] if run_result["result"] is not None else {"error": run_result["error"]},
            allowed_filesystem_roots=filesystem_policy.get("filesystem_roots", []),
        )

        final_status = run_result["status"]
        with self.repository.transaction() as connection:
            execution_row = self.repository.get_execution(connection, execution_public_id)
            self.repository.update_execution(
                connection, execution_public_id,
                {
                    "status": final_status, "duration_ms": run_result["duration_ms"], "completed_at": _now(),
                    "granted_scopes_json": granted_scope_keys, "token_hash_verified": execution_token["token_hash"],
                },
            )
            self.repository.create_io(
                connection, execution_id=execution_row["id"], io_type="input",
                sanitized_payload={"text": sanitized_input["sanitized_output_text"]}, truncated=sanitized_input["truncated"],
                redaction_categories=sanitized_input["redaction_categories_applied"],
            )
            self.repository.create_io(
                connection, execution_id=execution_row["id"], io_type="output",
                sanitized_payload={"text": sanitized_output["sanitized_output_text"]}, truncated=sanitized_output["truncated"],
                redaction_categories=sanitized_output["redaction_categories_applied"],
            )
            self._event(
                connection, execution_row["id"], "execution_finished", stage="capture_result",
                message=f"status={final_status} duration_ms={run_result['duration_ms']}",
                metadata={"checksum_verified": checksum_result["verified"]},
            )
            return public_execution_row(self.repository.get_execution(connection, execution_public_id))

    # -- stage 11: generate execution report ---------------------------------------------

    def generate_execution_report(self, execution_public_id: str) -> dict[str, Any]:
        execution_data = self.execution(execution_public_id)
        io_items = self.list_io(execution_public_id)["items"]
        output_summary = next((item["sanitized_payload"] for item in io_items if item["io_type"] == "output"), {})

        report = execution_report_builder.generate_execution_report(
            execution_public_id=execution_public_id, plugin_public_id=execution_data["plugin_public_id"],
            execution_mode=execution_data["execution_mode"], status=execution_data["status"],
            duration_ms=execution_data["duration_ms"], scope_key=execution_data["scope_key"],
            guard_violations=[execution_data["denial_reason"]] if execution_data.get("denial_reason") else [],
            sanitized_output_summary=output_summary, generated_at=_now(),
        )
        with self.repository.transaction() as connection:
            execution_row = self.repository.get_execution(connection, execution_public_id)
            self._event(connection, execution_row["id"], "report_generated", stage="generate_execution_report")
        return report

    # -- stage 12: record external audit event ----------------------------------------------

    def record_external_event(self, execution_public_id: str, *, event_type: str, message: str = "", metadata: dict[str, Any] | None = None, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            execution_row = self.repository.get_execution(connection, execution_public_id)
            self._event(connection, execution_row["id"], event_type, stage=execution_row["status"], message=message, metadata={**(metadata or {}), "admin_id": admin_id})
            return {"recorded": True}

    # -- stage 13: archive execution -------------------------------------------------------

    def archive_execution(self, execution_public_id: str, *, admin_id: str) -> dict[str, Any]:
        execution_data = self.execution(execution_public_id)
        if execution_data["status"] not in _TERMINAL_STATUSES:
            raise ValidationError(f"execution status must be terminal to archive (currently '{execution_data['status']}')")

        with self.repository.transaction() as connection:
            execution_row = self.repository.get_execution(connection, execution_public_id)
            events = self.repository.list_events(connection, execution_id=execution_row["id"], limit=100, offset=0)
            guard_violation_count = sum(1 for e in events if e["event_type"] == "execution_denied")

            self.repository.create_memory(
                connection, execution_id=execution_row["id"], plugin_public_id=execution_data["plugin_public_id"],
                final_status=execution_data["status"], duration_ms=execution_data["duration_ms"],
                guard_violation_count=guard_violation_count, recorded_by=admin_id,
            )
            self.repository.update_execution(connection, execution_public_id, {"status": "archived"})
            self._event(connection, execution_row["id"], "execution_archived", stage="archive", message=f"archived by {admin_id}")
            return public_execution_row(self.repository.get_execution(connection, execution_public_id))

    # -- convenience entrypoints: public chat / admin assistant / admin manual --------------

    def execute_for_public_chat(
        self, *, plugin_public_id: str, scope_key: str, arguments: dict[str, Any], requester_user_id_hash: str,
        execution_token: dict[str, Any] | None, timeout_seconds: float = timeout_runner.DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        request = self.create_execution_request(
            plugin_public_id=plugin_public_id, scope_key=scope_key, arguments=arguments, execution_mode="public_chat",
            requester_user_id_hash=requester_user_id_hash,
        )
        return self.run_execution(request["public_id"], execution_token=execution_token, timeout_seconds=timeout_seconds)

    def execute_for_admin_assistant(
        self, *, plugin_public_id: str, scope_key: str, arguments: dict[str, Any], requester_admin_public_id: str,
        execution_token: dict[str, Any] | None, timeout_seconds: float = timeout_runner.DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        if not requester_admin_public_id:
            raise ValidationError("Admin Assistant execution requires a real admin identity -- Admin Assistant is not a bypass")
        request = self.create_execution_request(
            plugin_public_id=plugin_public_id, scope_key=scope_key, arguments=arguments, execution_mode="admin_assistant",
            requester_admin_public_id=requester_admin_public_id,
        )
        return self.run_execution(request["public_id"], execution_token=execution_token, admin_authorized=True, timeout_seconds=timeout_seconds)

    def execute_manual(
        self, *, plugin_public_id: str, scope_key: str, arguments: dict[str, Any], requester_admin_public_id: str,
        execution_token: dict[str, Any] | None, timeout_seconds: float = timeout_runner.DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        if not requester_admin_public_id:
            raise ValidationError("a real admin identity is required to manually execute a plugin")
        request = self.create_execution_request(
            plugin_public_id=plugin_public_id, scope_key=scope_key, arguments=arguments, execution_mode="admin_manual",
            requester_admin_public_id=requester_admin_public_id,
        )
        return self.run_execution(request["public_id"], execution_token=execution_token, timeout_seconds=timeout_seconds)


__all__ = ["MiniBrainPluginRuntimeService"]
