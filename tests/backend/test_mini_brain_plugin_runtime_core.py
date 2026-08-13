"""MB-25: pure-module unit tests for core_model/mini_brain/plugin_runtime/.

Covers package manifest validation, checksum-based signature/trust
evaluation, entrypoint resolution, execution context building, the
permission/consent gates, filesystem/network guards, the timeout
runner (including a real timeout and a real completion), result
sanitization, audit record assembly, execution report generation, and
the public-chat/admin-assistant mode guards plus the top-level
combined runtime policy decision.
"""

import time
from pathlib import Path

import pytest

from core_model.mini_brain.plugin_runtime.admin_assistant_runtime_guard import evaluate_admin_assistant_execution
from core_model.mini_brain.plugin_runtime.audit_record_builder import build_audit_record
from core_model.mini_brain.plugin_runtime.consent_gate import evaluate_execution_consent
from core_model.mini_brain.plugin_runtime.execution_context_builder import build_execution_context
from core_model.mini_brain.plugin_runtime.execution_report_builder import generate_execution_report
from core_model.mini_brain.plugin_runtime.filesystem_guard import check_path_allowed
from core_model.mini_brain.plugin_runtime.network_guard import check_domain_allowed
from core_model.mini_brain.plugin_runtime.permission_gate import evaluate_execution_permission
from core_model.mini_brain.plugin_runtime.plugin_entrypoint_resolver import resolve_entrypoint
from core_model.mini_brain.plugin_runtime.plugin_manifest_loader import validate_package_manifest
from core_model.mini_brain.plugin_runtime.plugin_runtime_policy import evaluate_execution_policy
from core_model.mini_brain.plugin_runtime.plugin_signature_checker import evaluate_signature_trust, verify_checksum
from core_model.mini_brain.plugin_runtime.public_chat_runtime_guard import evaluate_public_chat_execution
from core_model.mini_brain.plugin_runtime.result_serializer import sanitize_result
from core_model.mini_brain.plugin_runtime.timeout_runner import run_with_timeout

VALID_PACKAGE_MANIFEST = {
    "plugin_id": "weather_lookup", "name": "Weather Lookup", "version": "1.0.0", "entrypoint": "main.py",
    "permissions": ["network.http.allowed_domains"], "public_chat_enabled": True, "admin_assistant_enabled": True,
    "description": "Deterministic stub weather lookup.",
}

# -- plugin_manifest_loader -------------------------------------------------------------------


def test_validate_package_manifest_accepts_valid_manifest() -> None:
    result = validate_package_manifest(manifest=VALID_PACKAGE_MANIFEST)
    assert result["valid"] is True


def test_validate_package_manifest_rejects_missing_field() -> None:
    manifest = dict(VALID_PACKAGE_MANIFEST)
    del manifest["entrypoint"]
    result = validate_package_manifest(manifest=manifest)
    assert result["valid"] is False


def test_validate_package_manifest_rejects_non_py_entrypoint() -> None:
    manifest = dict(VALID_PACKAGE_MANIFEST, entrypoint="main.sh")
    result = validate_package_manifest(manifest=manifest)
    assert result["valid"] is False


def test_validate_package_manifest_rejects_oversized_permissions() -> None:
    manifest = dict(VALID_PACKAGE_MANIFEST, permissions=["chat.read.current"] * 21)
    result = validate_package_manifest(manifest=manifest)
    assert result["valid"] is False


def test_validate_package_manifest_rejects_non_bool_flags() -> None:
    manifest = dict(VALID_PACKAGE_MANIFEST, public_chat_enabled="yes")
    result = validate_package_manifest(manifest=manifest)
    assert result["valid"] is False


# -- plugin_signature_checker -------------------------------------------------------------------


def test_verify_checksum_matches() -> None:
    result = verify_checksum(expected_checksum_sha256="abc123", actual_checksum_sha256="abc123")
    assert result["verified"] is True


def test_verify_checksum_mismatch() -> None:
    result = verify_checksum(expected_checksum_sha256="abc123", actual_checksum_sha256="def456")
    assert result["verified"] is False


def test_verify_checksum_no_expected() -> None:
    result = verify_checksum(expected_checksum_sha256=None, actual_checksum_sha256="def456")
    assert result["verified"] is False
    assert result["matches"] is None


def test_evaluate_signature_trust_never_cryptographically_verified() -> None:
    result = evaluate_signature_trust(signature_placeholder="unsigned", checksum_verified=True)
    assert result["signature_cryptographically_verified"] is False
    assert result["checksum_verified"] is True


# -- plugin_entrypoint_resolver -------------------------------------------------------------------


def test_resolve_entrypoint_real_package(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "sample_plugin"
    pkg_dir.mkdir()
    (pkg_dir / "main.py").write_text("def run(context, arguments):\n    return {}\n")
    resolved = resolve_entrypoint(package_dir=pkg_dir, entrypoint="main.py")
    assert resolved.exists()
    assert resolved.name == "main.py"


def test_resolve_entrypoint_rejects_non_py() -> None:
    with pytest.raises(ValueError):
        resolve_entrypoint(package_dir=Path("/tmp"), entrypoint="main.sh")


def test_resolve_entrypoint_rejects_escape(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "sample_plugin"
    pkg_dir.mkdir()
    with pytest.raises(ValueError):
        resolve_entrypoint(package_dir=pkg_dir, entrypoint="../../etc/passwd.py")


def test_resolve_entrypoint_rejects_missing_file(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "sample_plugin"
    pkg_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        resolve_entrypoint(package_dir=pkg_dir, entrypoint="missing.py")


# -- execution_context_builder -------------------------------------------------------------------


def test_build_execution_context_never_includes_a_token_or_secret() -> None:
    context = build_execution_context(
        execution_public_id="exec-1", plugin_public_id="plugin-1", granted_scopes=["chat.read.current"],
        memory_limit_mb=256, cpu_time_limit_ms=5000, requester_kind="public_chat", requester_id_hash="uh",
    )
    assert "token" not in context
    assert "admin_id" not in context
    assert context["granted_scopes"] == ["chat.read.current"]


# -- permission_gate / consent_gate -------------------------------------------------------------------


def test_evaluate_execution_permission_allowed() -> None:
    result = evaluate_execution_permission(required_scope="chat.read.current", granted_scope_keys=["chat.read.current"])
    assert result["allowed"] is True


def test_evaluate_execution_permission_denied_when_not_granted() -> None:
    result = evaluate_execution_permission(required_scope="email.send", granted_scope_keys=["chat.read.current"])
    assert result["allowed"] is False


def test_evaluate_execution_consent_not_required() -> None:
    result = evaluate_execution_consent(required_scope="chat.read.current", consent_required=False, has_valid_consent=False)
    assert result["allowed"] is True


def test_evaluate_execution_consent_required_and_missing() -> None:
    result = evaluate_execution_consent(required_scope="chat.read.history", consent_required=True, has_valid_consent=False)
    assert result["allowed"] is False


def test_evaluate_execution_consent_required_and_present() -> None:
    result = evaluate_execution_consent(required_scope="chat.read.history", consent_required=True, has_valid_consent=True)
    assert result["allowed"] is True


# -- filesystem_guard / network_guard -------------------------------------------------------------------


def test_check_path_allowed_inside_root() -> None:
    result = check_path_allowed(requested_path="/home/user/plugin-data/file.txt", allowed_roots=["/home/user/plugin-data"])
    assert result["allowed"] is True


def test_check_path_allowed_outside_root() -> None:
    result = check_path_allowed(requested_path="/etc/passwd", allowed_roots=["/home/user/plugin-data"])
    assert result["allowed"] is False


def test_check_path_allowed_no_roots_configured() -> None:
    result = check_path_allowed(requested_path="/home/user/plugin-data/file.txt", allowed_roots=[])
    assert result["allowed"] is False


def test_check_path_allowed_rejects_traversal_style_escape() -> None:
    result = check_path_allowed(requested_path="/home/user/plugin-data/../../etc/passwd", allowed_roots=["/home/user/plugin-data"])
    assert result["allowed"] is False


def test_check_domain_allowed_exact_match() -> None:
    result = check_domain_allowed(requested_domain="api.weather.example", allowed_domains=["api.weather.example"])
    assert result["allowed"] is True


def test_check_domain_allowed_wildcard_subdomain() -> None:
    result = check_domain_allowed(requested_domain="api.weather.example", allowed_domains=["*.weather.example"])
    assert result["allowed"] is True


def test_check_domain_allowed_denied() -> None:
    result = check_domain_allowed(requested_domain="evil.example", allowed_domains=["api.weather.example"])
    assert result["allowed"] is False


# -- timeout_runner -- real completion and a real timeout -------------------------------------------------------------------


def test_run_with_timeout_completes() -> None:
    def fast_fn(context, arguments):
        return {"ok": True}

    result = run_with_timeout(fast_fn, args=({}, {}), timeout_seconds=2.0)
    assert result["status"] == "completed"
    assert result["result"] == {"ok": True}
    assert result["duration_ms"] >= 0


def test_run_with_timeout_real_timeout() -> None:
    def slow_fn(context, arguments):
        time.sleep(2)
        return {"ok": True}

    result = run_with_timeout(slow_fn, args=({}, {}), timeout_seconds=0.2)
    assert result["status"] == "timeout"
    assert "disclosure" in result


def test_run_with_timeout_captures_exception() -> None:
    def broken_fn(context, arguments):
        raise ValueError("boom")

    result = run_with_timeout(broken_fn, args=({}, {}), timeout_seconds=2.0)
    assert result["status"] == "failed"
    assert "boom" in result["error"]


def test_run_with_timeout_bounds_to_max() -> None:
    def fast_fn(context, arguments):
        return {"ok": True}

    result = run_with_timeout(fast_fn, args=({}, {}), timeout_seconds=999.0)
    assert result["status"] == "completed"


# -- result_serializer -------------------------------------------------------------------


def test_sanitize_result_redacts_secret() -> None:
    result = sanitize_result(result={"token": "api_key=sk-abc123def456"}, allowed_filesystem_roots=[])
    assert "sk-abc123def456" not in result["sanitized_output_text"]
    assert "secret_like_content" in result["redaction_categories_applied"]


def test_sanitize_result_preserves_paths_inside_sandbox() -> None:
    # a root outside /home, /etc, /usr, /var so MB-23's own blanket
    # absolute-path pass never touches it -- isolates the sandbox-aware
    # pass's own preserve-inside-sandbox behavior for this test.
    result = sanitize_result(result={"path": "/opt/plugin-sandbox/output.txt"}, allowed_filesystem_roots=["/opt/plugin-sandbox"])
    assert "/opt/plugin-sandbox/output.txt" in result["sanitized_output_text"]


def test_sanitize_result_redacts_paths_outside_sandbox() -> None:
    result = sanitize_result(result={"path": "/opt/other-plugin/secret/config.yaml"}, allowed_filesystem_roots=["/opt/plugin-sandbox"])
    assert "/opt/other-plugin/secret" not in result["sanitized_output_text"]
    assert "filesystem_path_outside_sandbox" in result["redaction_categories_applied"]


def test_sanitize_result_still_redacts_home_path_even_inside_sandbox() -> None:
    """MB-23's own blanket /home/ redaction is deliberately conservative
    and must not be weakened by sandbox awareness -- a sandbox root
    under /home/<user>/... still has its username redacted."""
    result = sanitize_result(result={"path": "/home/realuser/plugin-sandbox/output.txt"}, allowed_filesystem_roots=["/home/realuser/plugin-sandbox"])
    assert "/home/realuser" not in result["sanitized_output_text"]


def test_sanitize_result_truncates_oversized_output() -> None:
    result = sanitize_result(result={"text": "x" * 10_000}, allowed_filesystem_roots=[])
    assert result["truncated"] is True


# -- audit_record_builder -------------------------------------------------------------------


def test_build_audit_record_never_decides_anything() -> None:
    record = build_audit_record(event_type="execution_completed", execution_public_id="exec-1", stage="execute", actor="system", metadata={})
    assert record["event_type"] == "execution_completed"


# -- execution_report_builder -------------------------------------------------------------------


def test_generate_execution_report_discloses_all_step20_limitations() -> None:
    report = generate_execution_report(
        execution_public_id="exec-1", plugin_public_id="plugin-1", execution_mode="public_chat", status="completed",
        duration_ms=12.3, scope_key="chat.read.current", guard_violations=[], sanitized_output_summary={}, generated_at="now",
    )
    for key in (
        "no_container_isolation", "no_process_isolation", "no_cpu_quota_enforcement", "no_memory_quota_enforcement",
        "no_signed_plugin_verification", "no_package_marketplace", "no_automatic_updates", "no_remote_plugin_execution",
    ):
        assert report[key] is True, key


# -- public_chat_runtime_guard / admin_assistant_runtime_guard / plugin_runtime_policy -----------------------------


def test_evaluate_public_chat_execution_denied_when_not_enabled() -> None:
    result = evaluate_public_chat_execution(public_chat_enabled=False, required_scope="chat.read.current")
    assert result["allowed"] is False


def test_evaluate_public_chat_execution_denied_for_high_sensitivity_scope() -> None:
    result = evaluate_public_chat_execution(public_chat_enabled=True, required_scope="email.send")
    assert result["allowed"] is False


def test_evaluate_public_chat_execution_allowed() -> None:
    result = evaluate_public_chat_execution(public_chat_enabled=True, required_scope="chat.read.current")
    assert result["allowed"] is True


def test_evaluate_admin_assistant_execution_requires_both_flags() -> None:
    assert evaluate_admin_assistant_execution(admin_assistant_enabled=False, admin_authorized=True)["allowed"] is False
    assert evaluate_admin_assistant_execution(admin_assistant_enabled=True, admin_authorized=False)["allowed"] is False
    assert evaluate_admin_assistant_execution(admin_assistant_enabled=True, admin_authorized=True)["allowed"] is True


def test_evaluate_execution_policy_denies_when_plugin_not_enabled() -> None:
    result = evaluate_execution_policy(
        plugin_status="disabled", permission_result={"allowed": True, "reason": None},
        consent_result={"allowed": True, "reason": None}, mode_guard_result={"allowed": True, "reason": None},
    )
    assert result["may_execute"] is False


def test_evaluate_execution_policy_allows_when_everything_passes() -> None:
    result = evaluate_execution_policy(
        plugin_status="enabled", permission_result={"allowed": True, "reason": None},
        consent_result={"allowed": True, "reason": None}, mode_guard_result={"allowed": True, "reason": None},
    )
    assert result["may_execute"] is True


def test_evaluate_execution_policy_collects_all_reasons() -> None:
    result = evaluate_execution_policy(
        plugin_status="enabled", permission_result={"allowed": False, "reason": "no permission"},
        consent_result={"allowed": False, "reason": "no consent"}, mode_guard_result={"allowed": True, "reason": None},
    )
    assert result["may_execute"] is False
    assert "no permission" in result["reasons"]
    assert "no consent" in result["reasons"]
