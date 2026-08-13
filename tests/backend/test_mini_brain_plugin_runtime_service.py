"""MB-25: service-level tests for MiniBrainPluginRuntimeService
against a real, seeded temp database and a real on-disk plugin package
(the `weather_lookup` reference plugin shipped at data/plugins/) --
no mocks. Drives the full workflow through real MB-24 governance
(register, validate, classify, risk-score, sandbox/filesystem/network
policy, enable, consent, grant, token issuance) and then MB-25's own
13-stage execution workflow end to end.
"""

import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.mini_brain_plugin_governance_service import MiniBrainPluginGovernanceService
from backend.services.mini_brain_plugin_runtime_service import MiniBrainPluginRuntimeService

pytestmark = pytest.mark.anyio

REAL_PLUGIN_DIR = Path(__file__).resolve().parents[2] / "data" / "plugins"

GOVERNANCE_MANIFEST = {
    "plugin_id": "weather_lookup", "name": "Weather Lookup", "version": "1.0.0", "author": "Brud AI",
    "description": "Deterministic stub weather lookup.", "entrypoint": "main.py",
    "requested_scopes": ["network.http.allowed_domains"], "allowed_domains": ["api.weather.example"],
    "filesystem_roots": [], "ui_components": [], "local_storage_usage": False, "cloud_storage_usage": False,
    "minimum_brud_version": "1.0.0", "signature_placeholder": "unsigned", "homepage": "https://example.com",
    "support_url": "https://example.com/support",
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
        document_report_dir=tmp_path / "documents" / "reports", plugin_package_dir=REAL_PLUGIN_DIR,
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


def _svc(app: FastAPI) -> tuple[MiniBrainPluginGovernanceService, MiniBrainPluginRuntimeService]:
    gov = MiniBrainPluginGovernanceService(app.state.settings)
    rt = MiniBrainPluginRuntimeService(app.state.settings, governance=gov)
    return gov, rt


def _approve_and_enable(gov: MiniBrainPluginGovernanceService, manifest: dict, admin_id: str = "admin-1") -> str:
    plugin = gov.register_plugin(manifest=manifest, admin_id=admin_id)
    plugin_id = plugin["public_id"]
    gov.run_validate_manifest_stage(plugin_id, admin_id=admin_id)
    gov.run_classify_capabilities_stage(plugin_id, admin_id=admin_id)
    gov.run_compute_risk_stage(plugin_id, admin_id=admin_id)
    gov.run_build_sandbox_stage(plugin_id, admin_id=admin_id)
    gov.run_build_filesystem_policy_stage(plugin_id, admin_id=admin_id)
    gov.run_build_network_policy_stage(plugin_id, admin_id=admin_id)
    gov.enable_plugin(plugin_id, admin_id=admin_id)
    return plugin_id


# -- successful execution ------------------------------------------------------------------------


async def test_successful_public_chat_execution(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    result = rt.execute_for_public_chat(
        plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"},
        requester_user_id_hash=consent["user_id_hash"], execution_token=token,
    )
    assert result["status"] == "completed"
    assert result["duration_ms"] is not None


# -- disabled plugin rejection ------------------------------------------------------------------------


async def test_disabled_plugin_rejection(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin = gov.register_plugin(manifest=GOVERNANCE_MANIFEST, admin_id="admin-1")
    plugin_id = plugin["public_id"]
    gov.run_validate_manifest_stage(plugin_id, admin_id="admin-1")
    gov.run_classify_capabilities_stage(plugin_id, admin_id="admin-1")
    gov.run_compute_risk_stage(plugin_id, admin_id="admin-1")
    gov.run_build_sandbox_stage(plugin_id, admin_id="admin-1")
    gov.run_build_filesystem_policy_stage(plugin_id, admin_id="admin-1")
    gov.run_build_network_policy_stage(plugin_id, admin_id="admin-1")
    # never enabled

    request = rt.create_execution_request(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"}, execution_mode="public_chat", requester_user_id_hash="uh")
    result = rt.run_execution(request["public_id"], execution_token=None)
    assert result["status"] == "denied"
    assert "not 'enabled'" in result["denial_reason"]


# -- permission denial ------------------------------------------------------------------------


async def test_permission_denial_when_scope_never_granted(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    # no consent, no grant, no token -- request_consent/grant never called
    request = rt.create_execution_request(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"}, execution_mode="public_chat", requester_user_id_hash="uh")
    result = rt.run_execution(request["public_id"], execution_token=None)
    assert result["status"] == "denied"
    assert "no execution token" in result["denial_reason"]


# -- consent denial (valid token+grant but no consent recorded for a fresh user) ------------------


async def test_consent_denial(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    # a different user, never granted consent
    other_user_hash = gov.hash_identity(raw_identity="user-2")
    request = rt.create_execution_request(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"}, execution_mode="public_chat", requester_user_id_hash=other_user_hash)
    result = rt.run_execution(request["public_id"], execution_token=token)
    assert result["status"] == "denied"
    assert "consent" in result["denial_reason"]


# -- timeout ------------------------------------------------------------------------


async def test_timeout(api_app: FastAPI, tmp_path: Path) -> None:
    slow_root = tmp_path / "alt_plugins"
    slow_dir = slow_root / "slow_plugin"
    slow_dir.mkdir(parents=True)
    (slow_dir / "main.py").write_text("import time\n\ndef run(context, arguments):\n    time.sleep(2)\n    return {'ok': True}\n")
    (slow_dir / "plugin.json").write_text(
        '{"plugin_id": "slow_plugin", "name": "Slow Plugin", "version": "1.0.0", "entrypoint": "main.py", '
        '"permissions": ["network.http.allowed_domains"], "public_chat_enabled": true, '
        '"admin_assistant_enabled": true, "description": "slow test plugin"}'
    )

    gov, _ = _svc(api_app)
    alt_settings = Settings(
        database_path=api_app.state.settings.database_path, database_backup_dir=api_app.state.settings.database_backup_dir,
        allowed_data_dir=tmp_path, document_dir=api_app.state.settings.document_dir,
        document_report_dir=api_app.state.settings.document_report_dir,
        plugin_package_dir=slow_root, allow_external_storage=True, log_level="CRITICAL",
    )
    rt_alt = MiniBrainPluginRuntimeService(alt_settings, governance=gov)

    manifest = dict(GOVERNANCE_MANIFEST, plugin_id="slow_plugin", name="Slow Plugin")
    plugin_id = _approve_and_enable(gov, manifest)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    request = rt_alt.create_execution_request(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={}, execution_mode="public_chat", requester_user_id_hash=consent["user_id_hash"])
    result = rt_alt.run_execution(request["public_id"], execution_token=token, timeout_seconds=0.3)
    assert result["status"] == "timeout"
    shutil.rmtree(slow_root, ignore_errors=True)


# -- filesystem violation / network violation ------------------------------------------------------------


async def test_network_violation_denied(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    request = rt.create_execution_request(
        plugin_public_id=plugin_id, scope_key="network.http.allowed_domains",
        arguments={"location": "London", "requested_domains": ["evil.example"]}, execution_mode="public_chat",
        requester_user_id_hash=consent["user_id_hash"],
    )
    result = rt.run_execution(request["public_id"], execution_token=token)
    assert result["status"] == "denied"
    assert "allowed_domains" in result["denial_reason"]


async def test_filesystem_violation_denied(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    manifest = dict(GOVERNANCE_MANIFEST, requested_scopes=["filesystem.read.user_selected"], filesystem_roots=["/home/user/approved-root"], allowed_domains=[])
    plugin_id = _approve_and_enable(gov, manifest)
    consent = gov.request_consent(plugin_id, scope_key="filesystem.read.user_selected", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="filesystem.read.user_selected", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["filesystem.read.user_selected"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    request = rt.create_execution_request(
        plugin_public_id=plugin_id, scope_key="filesystem.read.user_selected",
        arguments={"requested_paths": ["/etc/passwd"]}, execution_mode="public_chat",
        requester_user_id_hash=consent["user_id_hash"],
    )
    result = rt.run_execution(request["public_id"], execution_token=token)
    assert result["status"] == "denied"
    assert "filesystem root" in result["denial_reason"]


# -- public-chat admin-scope denial ------------------------------------------------------------------


async def test_public_chat_admin_scope_denial(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    manifest = dict(GOVERNANCE_MANIFEST, requested_scopes=["email.send"], allowed_domains=[])
    plugin_id = _approve_and_enable(gov, manifest)
    consent = gov.request_consent(plugin_id, scope_key="email.send", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="email.send", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["email.send"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    request = rt.create_execution_request(plugin_public_id=plugin_id, scope_key="email.send", arguments={}, execution_mode="public_chat", requester_user_id_hash=consent["user_id_hash"])
    result = rt.run_execution(request["public_id"], execution_token=token)
    assert result["status"] == "denied"
    assert "not available to public chat" in result["denial_reason"]


# -- admin-assistant success ------------------------------------------------------------------------


async def test_admin_assistant_success(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    result = rt.execute_for_admin_assistant(
        plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"},
        requester_admin_public_id="admin-1", execution_token=token,
    )
    assert result["status"] == "completed"


async def test_admin_assistant_requires_real_admin_id(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    with pytest.raises(ValidationError):
        rt.execute_for_admin_assistant(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={}, requester_admin_public_id="", execution_token=None)


# -- result sanitization / audit logging ------------------------------------------------------------


async def test_result_sanitization_persisted(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    result = rt.execute_for_public_chat(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"}, requester_user_id_hash=consent["user_id_hash"], execution_token=token)
    io_items = rt.list_io(result["public_id"])["items"]
    assert len(io_items) == 2
    output_item = next(i for i in io_items if i["io_type"] == "output")
    assert token["token_hash"] not in output_item["sanitized_payload"]["text"]


async def test_audit_logging_records_stage_events(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    result = rt.execute_for_public_chat(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"}, requester_user_id_hash=consent["user_id_hash"], execution_token=token)
    events = rt.list_events(result["public_id"])["items"]
    event_types = {e["event_type"] for e in events}
    assert {"execution_requested", "execution_started", "execution_finished"} <= event_types


# -- archive flow ------------------------------------------------------------------------


async def test_archive_flow(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    result = rt.execute_for_public_chat(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"}, requester_user_id_hash=consent["user_id_hash"], execution_token=token)
    archived = rt.archive_execution(result["public_id"], admin_id="admin-1")
    assert archived["status"] == "archived"
    with pytest.raises(ValidationError):
        rt.archive_execution(result["public_id"], admin_id="admin-1")

    memory = rt.list_memory()["items"]
    assert len(memory) == 1


# -- byte-level proof MB-24 remains unchanged ------------------------------------------------------


async def test_mb24_plugin_record_unchanged_by_mb25(api_app: FastAPI) -> None:
    gov, rt = _svc(api_app)
    plugin_id = _approve_and_enable(gov, GOVERNANCE_MANIFEST)
    consent = gov.request_consent(plugin_id, scope_key="network.http.allowed_domains", raw_user_identity="user-1", consent_given=True, ttl_seconds=3600.0, admin_id="admin-1")
    gov.grant_permission(plugin_id, scope_key="network.http.allowed_domains", user_id_hash=consent["user_id_hash"], admin_id="admin-1")
    token = gov.issue_execution_token(plugin_id, scope_keys=["network.http.allowed_domains"], raw_user_identity="user-1", raw_session_identity="session-1", admin_id="admin-1")

    plugin_before = gov.plugin(plugin_id)
    rt.execute_for_public_chat(plugin_public_id=plugin_id, scope_key="network.http.allowed_domains", arguments={"location": "London"}, requester_user_id_hash=consent["user_id_hash"], execution_token=token)
    plugin_after = gov.plugin(plugin_id)
    assert plugin_before == plugin_after
