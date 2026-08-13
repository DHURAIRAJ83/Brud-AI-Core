"""MB-24: Brud Mini Brain Plugin & Tool Runtime Governance Center --
the orchestration layer for the task spec's own 14-stage workflow.

This is a governance layer only: no plugin binary is ever executed,
no real sandbox or OS-level isolation exists, and no execution token
issued here is a real cryptographic credential. Every stage after
registration reads back the plugin's own already-stored manifest
fields and calls exactly one pure `core_model.mini_brain.
plugin_governance` module -- never a second policy implementation.

Two explicit actions exist beyond the spec's literal 14 stage names,
both documented here and in the final report: `enable_plugin()` (a
plugin is always created `status='disabled'`; only this explicit,
admin-authenticated call -- never anything automatic -- can move it to
`'enabled'`, and it doubles as the admin-review checkpoint high/
critical-risk scopes require) and the `disable_plugin()`/
`archive_plugin()` split (mirroring MB-21/22's own two-step close
pattern: disable is reversible, archive is not and is the only method
permitted to write the permanent `mini_brain_plugin_runtime_memory`
row).
"""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_plugin_governance import (
    MiniBrainPluginGovernanceRepository,
    public_consent_row,
    public_memory_row,
    public_permission_row,
    public_plugin_row,
)
from core_model.mini_brain.plugin_governance import (
    consent_policy_engine,
    data_boundary_analyzer,
    filesystem_policy_builder,
    network_policy_builder,
    plugin_capability_classifier,
    plugin_execution_token_builder,
    plugin_manifest_validator,
    plugin_marketplace_policy,
    plugin_risk_scorer,
    plugin_runtime_report_generator,
    plugin_trust_evaluator,
    runtime_policy_evaluator,
    sandbox_profile_builder,
)
from core_model.mini_brain.public_chat_runtime.session_builder import hash_client_key
from core_model.release.manifest import manifest_checksum

MANIFEST_FIELDS = (
    "plugin_id", "name", "version", "author", "description", "entrypoint", "requested_scopes",
    "allowed_domains", "filesystem_roots", "ui_components", "local_storage_usage", "cloud_storage_usage",
    "minimum_brud_version", "signature_placeholder", "homepage", "support_url",
)
_ANALYSIS_COMPLETE_STAGES = frozenset({"evaluate_permission", "grant_permission", "issue_token", "governance_report"})


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _timed(fn, /, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn(**kwargs)
    return result, round((time.perf_counter() - started) * 1000, 3)


class MiniBrainPluginGovernanceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainPluginGovernanceRepository(settings.resolved_database_path)
        self._salt = settings.mini_brain_public_chat_runtime_hash_salt

    # -- helpers -------------------------------------------------------

    def hash_identity(self, *, raw_identity: str) -> str:
        """Reuses MB-23's own session-hashing approach directly --
        the same salted-SHA-256 pattern, never a second implementation."""
        return hash_client_key(raw_client_key=raw_identity, salt=self._salt)

    def _manifest_from_row(self, plugin_row: dict[str, Any]) -> dict[str, Any]:
        return {field: plugin_row[field] for field in MANIFEST_FIELDS}

    def _event(self, connection, plugin_id: int | None, event_type: str, *, stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None) -> None:
        self.repository.create_event(connection, plugin_id=plugin_id, event_type=event_type, stage=stage, message=message, metadata=metadata)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "plugin_binaries_ever_executed": False,
            "real_sandbox_or_os_isolation_exists": False,
            "signed_plugin_verification_performed": False,
            "drm_or_anti_tamper_protection_exists": False,
            "marketplace_billing_performed": False,
            "automatic_update_system_exists": False,
            "auto_install_from_internet_performed": False,
            "auto_enable_after_upload_performed": False,
            "auto_permission_grant_performed": False,
            "mb16_through_mb23_data_modified": False,
            "training_jobs_started": False,
            "releases_approved": False,
            "csrf_or_admin_auth_bypassed": False,
            "execution_tokens_are_governance_metadata_only": True,
            "plugins_start_disabled": True,
            "writes_scope": (
                "own tables only (mini_brain_plugins, mini_brain_plugin_permissions, "
                "mini_brain_plugin_consents, mini_brain_plugin_runtime_events, "
                "mini_brain_plugin_runtime_memory)"
            ),
        }

    # -- reads -----------------------------------------------------------

    def plugin(self, plugin_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    def list_plugins(self, *, limit: int = 50, offset: int = 0, status: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_plugins(connection, limit=limit, offset=offset, status=status)
        return {"items": [public_plugin_row(row) for row in rows]}

    def list_permissions(self, plugin_public_id: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            rows = self.repository.list_permissions(connection, plugin_id=plugin_row["id"], limit=limit, offset=offset)
        return {"items": [public_permission_row(row) for row in rows]}

    def list_consents(self, plugin_public_id: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            rows = self.repository.list_consents(connection, plugin_id=plugin_row["id"], limit=limit, offset=offset)
        return {"items": [public_consent_row(row) for row in rows]}

    def list_events(self, plugin_public_id: str | None = None, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            plugin_id = None
            if plugin_public_id:
                plugin_id = self.repository.get_plugin(connection, plugin_public_id)["id"]
            rows = self.repository.list_events(connection, plugin_id=plugin_id, limit=limit, offset=offset)
        return {"items": [dict(row) for row in rows]}

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    # -- stage 1: register plugin --------------------------------------------

    def register_plugin(self, *, manifest: dict[str, Any], admin_id: str, source: str = "manual_upload") -> dict[str, Any]:
        marketplace = plugin_marketplace_policy.evaluate_marketplace_policy(source=source)
        if not marketplace["allowed"]:
            raise ValidationError(marketplace["reason"])

        missing = [field for field in MANIFEST_FIELDS if field not in manifest]
        if missing:
            raise ValidationError(f"manifest is missing required field(s): {missing}")

        checksum = manifest_checksum({field: manifest[field] for field in MANIFEST_FIELDS})

        with self.repository.transaction() as connection:
            public_id = self.repository.create_plugin(
                connection, plugin_id=manifest["plugin_id"], name=manifest["name"], version=manifest["version"],
                author=manifest["author"], description=manifest["description"], entrypoint=manifest["entrypoint"],
                requested_scopes=manifest["requested_scopes"], allowed_domains=manifest["allowed_domains"],
                filesystem_roots=manifest["filesystem_roots"], ui_components=manifest["ui_components"],
                local_storage_usage=bool(manifest["local_storage_usage"]),
                cloud_storage_usage=bool(manifest["cloud_storage_usage"]),
                minimum_brud_version=manifest["minimum_brud_version"],
                signature_placeholder=manifest["signature_placeholder"], homepage=manifest["homepage"],
                support_url=manifest["support_url"], manifest_checksum_sha256=checksum,
                registered_by_admin_public_id=admin_id,
            )
            plugin_row = self.repository.get_plugin(connection, public_id)
            self._event(
                connection, plugin_row["id"], "plugin_registered", stage="register",
                message=f"registered '{manifest['name']}' v{manifest['version']} from source={source}",
            )
            return public_plugin_row(self.repository.get_plugin(connection, public_id))

    # -- stage 2: validate manifest ------------------------------------------

    def run_validate_manifest_stage(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["stage"] != "register":
            raise ValidationError(f"plugin is at stage '{plugin_data['stage']}', not 'register'")

        manifest = self._manifest_from_row(plugin_data)
        report, latency_ms = _timed(plugin_manifest_validator.validate_manifest, manifest=manifest)
        report["latency_ms"] = latency_ms
        if not report["valid"]:
            raise ValidationError(f"manifest validation failed: {report['problems']}")

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(
                connection, plugin_public_id, {"validation_report_json": report, "stage": "classify_capabilities"},
            )
            self._event(connection, plugin_row["id"], "manifest_validated", stage="validate_manifest")
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- stage 3: classify capabilities ---------------------------------------

    def run_classify_capabilities_stage(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["stage"] != "classify_capabilities":
            raise ValidationError(f"plugin is at stage '{plugin_data['stage']}', not 'classify_capabilities'")

        classification = plugin_capability_classifier.classify_capabilities(requested_scopes=plugin_data["requested_scopes"])
        boundaries = data_boundary_analyzer.analyze_data_boundaries(
            requested_scopes=plugin_data["requested_scopes"], allowed_domains=plugin_data["allowed_domains"],
            filesystem_roots=plugin_data["filesystem_roots"],
        )
        trust = plugin_trust_evaluator.evaluate_trust_signals(manifest=self._manifest_from_row(plugin_data))
        combined = {"classification": classification, "boundaries": boundaries, "trust": trust}

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(
                connection, plugin_public_id,
                {"capability_classification_json": combined, "stage": "compute_risk"},
            )
            self._event(connection, plugin_row["id"], "capabilities_classified", stage="classify_capabilities")
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- stage 4: compute risk score --------------------------------------------

    def run_compute_risk_stage(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["stage"] != "compute_risk":
            raise ValidationError(f"plugin is at stage '{plugin_data['stage']}', not 'compute_risk'")

        sensitivity_counts = plugin_data["capability_classification"]["classification"]["sensitivity_counts"]
        risk = plugin_risk_scorer.compute_risk_score(
            sensitivity_counts=sensitivity_counts, domain_count=len(plugin_data["allowed_domains"]),
            filesystem_write_requested="filesystem.write.user_selected" in plugin_data["requested_scopes"],
            cloud_storage_usage=plugin_data["cloud_storage_usage"],
        )

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(
                connection, plugin_public_id,
                {"risk_score": risk["risk_score"], "risk_level": risk["risk_level"], "stage": "build_sandbox"},
            )
            self._event(
                connection, plugin_row["id"], "risk_computed", stage="compute_risk",
                message=f"risk_score={risk['risk_score']} risk_level={risk['risk_level']}",
            )
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- stage 5: build sandbox profile ------------------------------------------

    def run_build_sandbox_stage(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["stage"] != "build_sandbox":
            raise ValidationError(f"plugin is at stage '{plugin_data['stage']}', not 'build_sandbox'")

        sandbox = sandbox_profile_builder.build_sandbox_profile(
            requested_scopes=plugin_data["requested_scopes"], allowed_domains=plugin_data["allowed_domains"],
            filesystem_roots=plugin_data["filesystem_roots"], risk_level=plugin_data["risk_level"] or "low",
        )

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(
                connection, plugin_public_id, {"sandbox_profile_json": sandbox, "stage": "build_filesystem_policy"},
            )
            self._event(connection, plugin_row["id"], "sandbox_profile_built", stage="build_sandbox")
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- stage 6: build filesystem policy -------------------------------------------

    def run_build_filesystem_policy_stage(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["stage"] != "build_filesystem_policy":
            raise ValidationError(f"plugin is at stage '{plugin_data['stage']}', not 'build_filesystem_policy'")

        policy = filesystem_policy_builder.build_filesystem_policy(
            filesystem_roots=plugin_data["filesystem_roots"],
            read_requested="filesystem.read.user_selected" in plugin_data["requested_scopes"],
            write_requested="filesystem.write.user_selected" in plugin_data["requested_scopes"],
        )

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(
                connection, plugin_public_id, {"filesystem_policy_json": policy, "stage": "build_network_policy"},
            )
            self._event(connection, plugin_row["id"], "filesystem_policy_built", stage="build_filesystem_policy")
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- stage 7: build network policy -------------------------------------------

    def run_build_network_policy_stage(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["stage"] != "build_network_policy":
            raise ValidationError(f"plugin is at stage '{plugin_data['stage']}', not 'build_network_policy'")

        sandbox = plugin_data["sandbox_profile"]
        policy = network_policy_builder.build_network_policy(
            network_enabled=sandbox.get("network_enabled", False), allowed_domains=plugin_data["allowed_domains"],
        )

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(
                connection, plugin_public_id, {"network_policy_json": policy, "stage": "evaluate_permission"},
            )
            self._event(connection, plugin_row["id"], "network_policy_built", stage="build_network_policy")
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- explicit admin action: enable plugin (never automatic) -----------------------

    def enable_plugin(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        if not admin_id:
            raise ValidationError("a real admin identity is required to enable a plugin")
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["status"] != "disabled":
            raise ValidationError(f"plugin status must be 'disabled' to enable (currently '{plugin_data['status']}')")
        if plugin_data["stage"] not in _ANALYSIS_COMPLETE_STAGES:
            raise ValidationError("all governance analysis stages must complete before a plugin can be enabled")

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(
                connection, plugin_public_id,
                {"status": "enabled", "admin_reviewed": True, "admin_reviewed_by": admin_id, "admin_reviewed_at": _now()},
            )
            self._event(connection, plugin_row["id"], "plugin_enabled", stage=plugin_data["stage"], message=f"enabled by {admin_id}")
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- stage 8: evaluate permission request ------------------------------------------

    def run_evaluate_permission_stage(
        self, plugin_public_id: str, *, scope_key: str, is_public_chat: bool, user_id_hash: str | None = None,
        admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)
        if scope_key not in plugin_data["requested_scopes"]:
            raise ValidationError(f"scope '{scope_key}' was never requested by this plugin's manifest")

        has_valid_consent = False
        if user_id_hash:
            with self.repository.transaction() as connection:
                plugin_row = self.repository.get_plugin(connection, plugin_public_id)
                consent_row = self.repository.latest_consent(
                    connection, plugin_id=plugin_row["id"], user_id_hash=user_id_hash, scope_key=scope_key,
                )
            if consent_row is not None:
                expires_at = consent_row["expires_at"]
                validity = consent_policy_engine.is_consent_valid(
                    consent_given=bool(consent_row["consent_given"]),
                    expires_at_epoch_seconds=(datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp() if expires_at else None),
                    now_epoch_seconds=time.time(),
                )
                has_valid_consent = validity["valid"]

        evaluation = runtime_policy_evaluator.evaluate_permission(
            scope_key=scope_key, plugin_status=plugin_data["status"], is_public_chat=is_public_chat,
            has_valid_consent=has_valid_consent, admin_reviewed=plugin_data["admin_reviewed"],
            risk_level=plugin_data["risk_level"],
        )

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            existing_permission = self.repository.find_permission(connection, plugin_id=plugin_row["id"], scope_key=scope_key)
            if existing_permission is None:
                self.repository.create_permission(connection, plugin_id=plugin_row["id"], scope_key=scope_key, decision=evaluation["decision"])
            else:
                self.repository.update_permission(connection, existing_permission["public_id"], {"decision": evaluation["decision"]})

            current_summary = public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))["permission_evaluation"]
            current_summary[scope_key] = evaluation
            self.repository.update_plugin(connection, plugin_public_id, {"permission_evaluation_json": current_summary})

            self._event(
                connection, plugin_row["id"], "permission_evaluated", stage="evaluate_permission",
                message=f"scope={scope_key} decision={evaluation['decision']}",
            )
            return evaluation

    # -- stage 9: request user consent -----------------------------------------------

    def request_consent(
        self, plugin_public_id: str, *, scope_key: str, raw_user_identity: str, consent_given: bool,
        ttl_seconds: float | None, admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)
        if scope_key not in plugin_data["requested_scopes"]:
            raise ValidationError(f"scope '{scope_key}' was never requested by this plugin's manifest")

        user_id_hash = self.hash_identity(raw_identity=raw_user_identity)
        record = consent_policy_engine.build_consent_record(
            scope_key=scope_key, consent_given=consent_given, ttl_seconds=ttl_seconds, now_epoch_seconds=time.time(),
        )

        def _fmt(epoch_seconds: float | None) -> str | None:
            return datetime.fromtimestamp(epoch_seconds, tz=UTC).strftime("%Y-%m-%d %H:%M:%S") if epoch_seconds else None

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.create_consent(
                connection, plugin_id=plugin_row["id"], user_id_hash=user_id_hash, scope_key=scope_key,
                consent_given=consent_given, consent_at=_fmt(record["consent_at"]), expires_at=_fmt(record["expires_at"]),
            )
            self._event(
                connection, plugin_row["id"], "consent_recorded", stage="request_consent",
                message=f"scope={scope_key} consent_given={consent_given}",
            )
            return {"user_id_hash": user_id_hash, "scope_key": scope_key, "consent_given": consent_given, "expires_at": _fmt(record["expires_at"])}

    # -- stage 10: grant permission (only method that may grant) ------------------------

    def grant_permission(self, plugin_public_id: str, *, scope_key: str, user_id_hash: str | None, admin_id: str) -> dict[str, Any]:
        if not admin_id:
            raise ValidationError("a real admin identity is required to grant a permission")
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["status"] != "enabled":
            raise ValidationError(f"plugin status must be 'enabled' to grant a permission (currently '{plugin_data['status']}')")

        has_valid_consent = False
        if user_id_hash:
            with self.repository.transaction() as connection:
                plugin_row = self.repository.get_plugin(connection, plugin_public_id)
                consent_row = self.repository.latest_consent(connection, plugin_id=plugin_row["id"], user_id_hash=user_id_hash, scope_key=scope_key)
            if consent_row is not None:
                expires_at = consent_row["expires_at"]
                has_valid_consent = consent_policy_engine.is_consent_valid(
                    consent_given=bool(consent_row["consent_given"]),
                    expires_at_epoch_seconds=(datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp() if expires_at else None),
                    now_epoch_seconds=time.time(),
                )["valid"]

        evaluation = runtime_policy_evaluator.evaluate_permission(
            scope_key=scope_key, plugin_status=plugin_data["status"], is_public_chat=False,
            has_valid_consent=has_valid_consent, admin_reviewed=plugin_data["admin_reviewed"],
            risk_level=plugin_data["risk_level"],
        )
        if evaluation["decision"] != "allow":
            raise ValidationError(f"cannot grant scope '{scope_key}': current policy decision is '{evaluation['decision']}' ({evaluation['reasons']})")

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            existing_permission = self.repository.find_permission(connection, plugin_id=plugin_row["id"], scope_key=scope_key)
            if existing_permission is None:
                permission_public_id = self.repository.create_permission(connection, plugin_id=plugin_row["id"], scope_key=scope_key, decision="allow")
            else:
                permission_public_id = existing_permission["public_id"]
            granted = self.repository.update_permission(
                connection, permission_public_id,
                {"status": "granted", "decision": "allow", "granted_by_admin_public_id": admin_id, "granted_at": _now()},
            )
            if plugin_data["stage"] == "evaluate_permission":
                self.repository.update_plugin(connection, plugin_public_id, {"stage": "grant_permission"})
            self._event(connection, plugin_row["id"], "permission_granted", stage="grant_permission", message=f"scope={scope_key}", metadata={"admin_id": admin_id})
            return public_permission_row(granted)

    def revoke_permission(self, plugin_public_id: str, *, scope_key: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            existing_permission = self.repository.find_permission(connection, plugin_id=plugin_row["id"], scope_key=scope_key)
            if existing_permission is None or existing_permission["status"] != "granted":
                raise ValidationError(f"no granted permission exists for scope '{scope_key}'")
            revoked = self.repository.update_permission(connection, existing_permission["public_id"], {"status": "revoked", "revoked_at": _now()})
            self._event(connection, plugin_row["id"], "permission_revoked", stage=plugin_row["stage"], message=f"scope={scope_key}", metadata={"admin_id": admin_id})
            return public_permission_row(revoked)

    # -- stage 11: issue execution token (only method that may issue) ---------------------

    def issue_execution_token(
        self, plugin_public_id: str, *, scope_keys: list[str], raw_user_identity: str, raw_session_identity: str,
        admin_id: str, ttl_seconds: float = plugin_execution_token_builder.DEFAULT_TOKEN_TTL_SECONDS,
    ) -> dict[str, Any]:
        if not admin_id:
            raise ValidationError("a real admin identity is required to issue an execution token")
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["status"] != "enabled":
            raise ValidationError(f"plugin status must be 'enabled' to issue a token (currently '{plugin_data['status']}')")

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            granted_rows = self.repository.list_permissions(connection, plugin_id=plugin_row["id"], limit=100, offset=0)
        granted_scopes = {row["scope_key"] for row in granted_rows if row["status"] == "granted"}
        missing = [scope for scope in scope_keys if scope not in granted_scopes]
        if missing:
            raise ValidationError(f"cannot issue a token for ungranted scope(s): {missing}")

        user_id_hash = self.hash_identity(raw_identity=raw_user_identity)
        session_id_hash = self.hash_identity(raw_identity=raw_session_identity)
        nonce = secrets.token_hex(16)
        token = plugin_execution_token_builder.build_execution_token(
            plugin_public_id=plugin_public_id, granted_scopes=scope_keys, user_id_hash=user_id_hash,
            session_id_hash=session_id_hash, issued_at_epoch_seconds=time.time(), nonce=nonce, ttl_seconds=ttl_seconds,
        )

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            if plugin_row["stage"] == "grant_permission":
                self.repository.update_plugin(connection, plugin_public_id, {"stage": "issue_token"})
            self._event(
                connection, plugin_row["id"], "execution_token_issued", stage="issue_token",
                message=f"scopes={scope_keys}",
                metadata={"token_hash": token["token_hash"], "expires_at": token["expires_at"], "granted_scopes": scope_keys},
            )
            return token

    # -- stage 12: record runtime event -------------------------------------------------

    def record_runtime_event(self, plugin_public_id: str, *, event_type: str, message: str = "", metadata: dict[str, Any] | None = None, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self._event(connection, plugin_row["id"], event_type, stage=plugin_row["stage"], message=message, metadata={**(metadata or {}), "admin_id": admin_id})
            return {"recorded": True}

    # -- stage 13: generate governance report ---------------------------------------------

    def generate_report(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        plugin_data = self.plugin(plugin_public_id)

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            granted_count = self.repository.granted_permission_count(connection, plugin_id=plugin_row["id"])
            consent_total = self.repository.consent_count(connection, plugin_id=plugin_row["id"])
            event_total = self.repository.event_count(connection, plugin_id=plugin_row["id"])

        report = plugin_runtime_report_generator.generate_governance_report(
            plugin_public_id=plugin_public_id, name=plugin_data["name"], version=plugin_data["version"],
            status=plugin_data["status"], stage=plugin_data["stage"], validation_report=plugin_data["validation_report"],
            capability_classification=plugin_data["capability_classification"], risk_score=plugin_data["risk_score"],
            risk_level=plugin_data["risk_level"], trust_signals=plugin_data["capability_classification"].get("trust", {}),
            sandbox_profile=plugin_data["sandbox_profile"], filesystem_policy=plugin_data["filesystem_policy"],
            network_policy=plugin_data["network_policy"], permission_summary={"granted_count": granted_count},
            event_count=event_total, generated_at=_now(),
        )

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(connection, plugin_public_id, {"governance_report_json": report, "stage": "governance_report"})
            self._event(connection, plugin_row["id"], "governance_report_generated", stage="governance_report", message=f"granted={granted_count} consents={consent_total} events={event_total}")
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- stage 14: disable / archive plugin ------------------------------------------------

    def disable_plugin(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["status"] != "enabled":
            raise ValidationError(f"plugin status must be 'enabled' to disable (currently '{plugin_data['status']}')")

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            self.repository.update_plugin(connection, plugin_public_id, {"status": "disabled"})
            self._event(connection, plugin_row["id"], "plugin_disabled", stage=plugin_row["stage"], message=f"disabled by {admin_id}")
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    def archive_plugin(self, plugin_public_id: str, *, admin_id: str) -> dict[str, Any]:
        plugin_data = self.plugin(plugin_public_id)
        if plugin_data["status"] not in ("disabled", "enabled"):
            raise ValidationError(f"plugin status must be 'disabled' or 'enabled' to archive (currently '{plugin_data['status']}')")

        with self.repository.transaction() as connection:
            plugin_row = self.repository.get_plugin(connection, plugin_public_id)
            granted_count = self.repository.granted_permission_count(connection, plugin_id=plugin_row["id"])
            consent_total = self.repository.consent_count(connection, plugin_id=plugin_row["id"])
            event_total = self.repository.event_count(connection, plugin_id=plugin_row["id"])

            self.repository.update_plugin(connection, plugin_public_id, {"status": "archived", "stage": "archived", "archived_at": _now()})
            self.repository.create_memory(
                connection, plugin_id=plugin_row["id"], final_status="archived", total_permissions_granted=granted_count,
                total_consents_recorded=consent_total, total_runtime_events=event_total, risk_score=plugin_data["risk_score"],
                risk_level=plugin_data["risk_level"], recorded_by_admin_public_id=admin_id,
            )
            self._event(connection, plugin_row["id"], "plugin_archived", stage="archived", message=f"archived by {admin_id}", metadata={"granted_count": granted_count})
            return public_plugin_row(self.repository.get_plugin(connection, plugin_public_id))

    # -- public chat / admin assistant integration policy helper (step 12/13) -----------------

    def check_plugin_policy(self, plugin_public_id: str, *, scope_key: str, is_public_chat: bool) -> dict[str, Any]:
        """Never reveals a secret -- no token, no internal database id,
        no manifest field beyond what's needed to answer four booleans.
        Admin Assistant is not a bypass: it calls this exact same method
        (with is_public_chat=False) before any execution token can ever
        be issued -- there is no separate, shortcut evaluation path."""
        plugin_data = self.plugin(plugin_public_id)
        if scope_key not in plugin_data["requested_scopes"]:
            return {"tool_visible": False, "tool_executable": False, "consent_required": False, "admin_review_required": False, "reason": "scope not requested by this plugin"}

        evaluation = runtime_policy_evaluator.evaluate_permission(
            scope_key=scope_key, plugin_status=plugin_data["status"], is_public_chat=is_public_chat,
            has_valid_consent=False, admin_reviewed=plugin_data["admin_reviewed"], risk_level=plugin_data["risk_level"],
        )
        decision = evaluation["decision"]
        return {
            "tool_visible": decision != "deny" and plugin_data["status"] != "archived",
            "tool_executable": decision == "allow",
            "consent_required": decision == "require_consent",
            "admin_review_required": decision == "require_admin_review",
        }


__all__ = ["MiniBrainPluginGovernanceService"]
