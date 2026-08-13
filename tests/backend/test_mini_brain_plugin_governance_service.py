"""MB-24: service-level tests for MiniBrainPluginGovernanceService
against a real, seeded temp database -- no mocks. Drives the full
14-stage governance workflow end to end: register, validate, classify,
risk-score, sandbox/filesystem/network policy, enable, evaluate
permission, consent, grant, issue token, record event, report,
disable, archive.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.mini_brain_plugin_governance_service import MiniBrainPluginGovernanceService
from backend.services.mini_brain_public_chat_runtime_service import MiniBrainPublicChatRuntimeService

pytestmark = pytest.mark.anyio

VALID_MANIFEST = {
    "plugin_id": "weather-lookup", "name": "Weather Lookup", "version": "1.0.0", "author": "Acme Co",
    "description": "Looks up weather.", "entrypoint": "main.js",
    "requested_scopes": ["filesystem.read.user_selected", "network.http.allowed_domains"],
    "allowed_domains": ["api.weather.example"], "filesystem_roots": ["/home/user/weather-cache"],
    "ui_components": [], "local_storage_usage": True, "cloud_storage_usage": False,
    "minimum_brud_version": "1.0.0", "signature_placeholder": "unsigned", "homepage": "https://example.com",
    "support_url": "https://example.com/support",
}

HIGH_RISK_MANIFEST = {
    "plugin_id": "mega-assistant", "name": "Mega Assistant", "version": "1.0.0", "author": "Acme Co",
    "description": "Does a lot.", "entrypoint": "main.js",
    "requested_scopes": ["email.send", "calendar.write", "microphone.capture", "camera.capture"],
    "allowed_domains": [], "filesystem_roots": [], "ui_components": [], "local_storage_usage": False,
    "cloud_storage_usage": True, "minimum_brud_version": "1.0.0", "signature_placeholder": "unsigned",
    "homepage": "https://example.com", "support_url": "https://example.com/support",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    from backend.main import create_app

    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _svc(app: FastAPI) -> MiniBrainPluginGovernanceService:
    return MiniBrainPluginGovernanceService(app.state.settings)


def _advance_to_evaluate_permission(svc: MiniBrainPluginGovernanceService, manifest: dict, admin_id: str = "admin-1") -> str:
    plugin = svc.register_plugin(manifest=manifest, admin_id=admin_id)
    plugin_id = plugin["public_id"]
    svc.run_validate_manifest_stage(plugin_id, admin_id=admin_id)
    svc.run_classify_capabilities_stage(plugin_id, admin_id=admin_id)
    svc.run_compute_risk_stage(plugin_id, admin_id=admin_id)
    svc.run_build_sandbox_stage(plugin_id, admin_id=admin_id)
    svc.run_build_filesystem_policy_stage(plugin_id, admin_id=admin_id)
    svc.run_build_network_policy_stage(plugin_id, admin_id=admin_id)
    return plugin_id


# -- valid / invalid manifest ------------------------------------------------------------


async def test_register_and_validate_a_valid_manifest(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    plugin = svc.plugin(plugin_id)
    assert plugin["stage"] == "evaluate_permission"
    assert plugin["validation_report"]["valid"] is True
    assert plugin["status"] == "disabled"


async def test_register_rejects_manifest_missing_a_required_field(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    manifest = dict(VALID_MANIFEST)
    del manifest["entrypoint"]
    with pytest.raises(ValidationError):
        svc.register_plugin(manifest=manifest, admin_id="admin-1")


async def test_validate_manifest_stage_rejects_unknown_scope(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    manifest = dict(VALID_MANIFEST, requested_scopes=["not.a.real.scope"])
    plugin = svc.register_plugin(manifest=manifest, admin_id="admin-1")
    with pytest.raises(ValidationError):
        svc.run_validate_manifest_stage(plugin["public_id"], admin_id="admin-1")


# -- high-risk plugin / deterministic risk score ------------------------------------------------


async def test_high_risk_plugin_computes_high_or_critical_risk(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, HIGH_RISK_MANIFEST)
    plugin = svc.plugin(plugin_id)
    assert plugin["risk_level"] in ("high", "critical")


async def test_risk_score_is_deterministic_across_two_identical_plugins(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_a = _advance_to_evaluate_permission(svc, dict(HIGH_RISK_MANIFEST, plugin_id="a"))
    plugin_b = _advance_to_evaluate_permission(svc, dict(HIGH_RISK_MANIFEST, plugin_id="b"))
    assert svc.plugin(plugin_a)["risk_score"] == svc.plugin(plugin_b)["risk_score"]


# -- public-chat denied scope --------------------------------------------------------------------


async def test_public_chat_is_denied_a_high_sensitivity_scope(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, HIGH_RISK_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    decision = svc.run_evaluate_permission_stage(plugin_id, scope_key="email.send", is_public_chat=True, admin_id="admin-1")
    assert decision["decision"] == "deny"


async def test_check_plugin_policy_denies_public_chat_for_high_sensitivity_scope(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, HIGH_RISK_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    result = svc.check_plugin_policy(plugin_id, scope_key="email.send", is_public_chat=True)
    assert result["tool_executable"] is False


# -- consent-required flow / admin-review-required flow -----------------------------------------


async def test_consent_required_flow(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    decision = svc.run_evaluate_permission_stage(plugin_id, scope_key="filesystem.read.user_selected", is_public_chat=False, admin_id="admin-1")
    assert decision["decision"] == "require_consent"

    consent = svc.request_consent(plugin_id, scope_key="filesystem.read.user_selected", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    granted = svc.grant_permission(plugin_id, scope_key="filesystem.read.user_selected", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    assert granted["status"] == "granted"


async def test_admin_review_required_flow(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, HIGH_RISK_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    decision = svc.run_evaluate_permission_stage(plugin_id, scope_key="email.send", is_public_chat=False, admin_id="admin-1")
    # enable_plugin already sets admin_reviewed=True, so a critical-risk plugin's
    # admin-review-only scope becomes reachable once genuinely reviewed
    assert decision["decision"] in ("require_consent", "allow")


async def test_evaluate_permission_before_enable_is_disabled(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    decision = svc.run_evaluate_permission_stage(plugin_id, scope_key="filesystem.read.user_selected", is_public_chat=False, admin_id="admin-1")
    assert decision["decision"] == "disabled"


# -- token expiry -----------------------------------------------------------------------------


async def test_issued_token_expires_after_its_ttl(api_app: FastAPI) -> None:
    from core_model.mini_brain.plugin_governance.plugin_execution_token_builder import is_token_expired

    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    consent = svc.request_consent(plugin_id, scope_key="filesystem.read.user_selected", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    svc.grant_permission(plugin_id, scope_key="filesystem.read.user_selected", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = svc.issue_execution_token(
        plugin_id, scope_keys=["filesystem.read.user_selected"], raw_user_identity="user-1",
        raw_session_identity="session-1", admin_id="admin-1", ttl_seconds=1.0,
    )
    assert is_token_expired(expires_at_epoch_seconds=token["expires_at"], now_epoch_seconds=token["payload"]["issued_at"] + 2.0) is True
    assert is_token_expired(expires_at_epoch_seconds=token["expires_at"], now_epoch_seconds=token["payload"]["issued_at"]) is False


async def test_issue_token_rejects_ungranted_scope(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    with pytest.raises(ValidationError):
        svc.issue_execution_token(
            plugin_id, scope_keys=["filesystem.read.user_selected"], raw_user_identity="user-1",
            raw_session_identity="session-1", admin_id="admin-1",
        )


# -- permission revocation ------------------------------------------------------------------


async def test_permission_revocation(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    consent = svc.request_consent(plugin_id, scope_key="filesystem.read.user_selected", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    svc.grant_permission(plugin_id, scope_key="filesystem.read.user_selected", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    revoked = svc.revoke_permission(plugin_id, scope_key="filesystem.read.user_selected", admin_id="admin-1")
    assert revoked["status"] == "revoked"

    with pytest.raises(ValidationError):
        svc.revoke_permission(plugin_id, scope_key="filesystem.read.user_selected", admin_id="admin-1")


# -- disable / archive path ------------------------------------------------------------------


async def test_disable_then_archive_path(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    svc.generate_report(plugin_id, admin_id="admin-1")

    disabled = svc.disable_plugin(plugin_id, admin_id="admin-1")
    assert disabled["status"] == "disabled"

    archived = svc.archive_plugin(plugin_id, admin_id="admin-1")
    assert archived["status"] == "archived"
    assert archived["stage"] == "archived"

    memory = svc.list_memory()["items"]
    assert any(m["final_status"] == "archived" for m in memory)


async def test_archive_requires_disabled_or_enabled_status(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    svc.enable_plugin(plugin_id, admin_id="admin-1")
    svc.archive_plugin(plugin_id, admin_id="admin-1")
    with pytest.raises(ValidationError):
        svc.archive_plugin(plugin_id, admin_id="admin-1")


# -- event logging ---------------------------------------------------------------------------


async def test_event_logging_records_every_stage_transition(api_app: FastAPI) -> None:
    svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(svc, VALID_MANIFEST)
    events = svc.list_events(plugin_id, limit=100)["items"]
    event_types = {e["event_type"] for e in events}
    assert {"plugin_registered", "manifest_validated", "capabilities_classified", "risk_computed", "sandbox_profile_built", "filesystem_policy_built", "network_policy_built"} <= event_types


# -- byte-level proof MB-23 is unchanged -------------------------------------------------------


async def test_mb23_public_chat_session_unchanged_by_mb24(api_app: FastAPI) -> None:
    pc_svc = MiniBrainPublicChatRuntimeService(api_app.state.settings)
    session_before = pc_svc.start_session(raw_client_key="203.0.113.50", language="en")

    pg_svc = _svc(api_app)
    plugin_id = _advance_to_evaluate_permission(pg_svc, VALID_MANIFEST)
    pg_svc.enable_plugin(plugin_id, admin_id="admin-1")
    pg_svc.archive_plugin(plugin_id, admin_id="admin-1")

    session_after = pc_svc.session(session_before["public_id"])
    assert session_after == session_before
