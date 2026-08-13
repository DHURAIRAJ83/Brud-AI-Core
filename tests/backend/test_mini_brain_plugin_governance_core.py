"""MB-24: pure-module unit tests for core_model/mini_brain/plugin_governance/.

Covers manifest validation (valid/invalid/unknown scope), the fixed
permission scope registry, capability classification, data-boundary
analysis, deterministic risk scoring, trust signal evaluation, sandbox/
filesystem/network policy building, the runtime permission engine
(allow/deny/require_consent/require_admin_review/disabled), consent
validity/expiry, deterministic execution-token payload hashing, audit
record assembly, marketplace policy, and the final governance report.
"""

import pytest

from core_model.mini_brain.plugin_governance.audit_record_builder import build_audit_record
from core_model.mini_brain.plugin_governance.consent_policy_engine import build_consent_record, is_consent_valid
from core_model.mini_brain.plugin_governance.data_boundary_analyzer import analyze_data_boundaries
from core_model.mini_brain.plugin_governance.filesystem_policy_builder import build_filesystem_policy
from core_model.mini_brain.plugin_governance.network_policy_builder import build_network_policy
from core_model.mini_brain.plugin_governance.permission_scope_registry import (
    SCOPE_REGISTRY,
    is_known_scope,
    is_public_chat_available,
    known_scopes,
    scope_definition,
)
from core_model.mini_brain.plugin_governance.plugin_capability_classifier import classify_capabilities
from core_model.mini_brain.plugin_governance.plugin_execution_token_builder import (
    build_execution_token,
    is_token_expired,
)
from core_model.mini_brain.plugin_governance.plugin_manifest_validator import (
    MAX_ALLOWED_DOMAINS,
    MAX_SCOPES,
    validate_manifest,
)
from core_model.mini_brain.plugin_governance.plugin_marketplace_policy import evaluate_marketplace_policy
from core_model.mini_brain.plugin_governance.plugin_risk_scorer import compute_risk_score
from core_model.mini_brain.plugin_governance.plugin_runtime_report_generator import generate_governance_report
from core_model.mini_brain.plugin_governance.plugin_trust_evaluator import evaluate_trust_signals
from core_model.mini_brain.plugin_governance.runtime_policy_evaluator import evaluate_permission
from core_model.mini_brain.plugin_governance.sandbox_profile_builder import build_sandbox_profile

VALID_MANIFEST = {
    "plugin_id": "weather-lookup", "name": "Weather Lookup", "version": "1.0.0", "author": "Acme Co",
    "description": "Looks up weather.", "entrypoint": "main.js",
    "requested_scopes": ["filesystem.read.user_selected", "network.http.allowed_domains"],
    "allowed_domains": ["api.weather.example"], "filesystem_roots": ["/home/user/weather-cache"],
    "ui_components": [], "local_storage_usage": True, "cloud_storage_usage": False,
    "minimum_brud_version": "1.0.0", "signature_placeholder": "unsigned", "homepage": "https://example.com",
    "support_url": "https://example.com/support",
}

# -- permission_scope_registry -------------------------------------------------------------------


def test_known_scopes_matches_the_full_task_spec_registry() -> None:
    scopes = known_scopes()
    assert len(scopes) == 17
    for expected in (
        "chat.read.current", "chat.read.history", "filesystem.read.user_selected",
        "filesystem.write.user_selected", "network.http.allowed_domains", "image.generate.local",
        "image.generate.external", "calendar.read", "calendar.write", "email.send", "clipboard.read",
        "clipboard.write", "microphone.capture", "camera.capture", "plugin.storage.local",
        "plugin.storage.cloud", "admin.assistant.invoke",
    ):
        assert expected in scopes


def test_every_scope_definition_has_all_required_fields() -> None:
    for scope_key, definition in SCOPE_REGISTRY.items():
        assert definition["sensitivity"] in ("low", "medium", "high", "critical"), scope_key
        assert isinstance(definition["consent_required"], bool)
        assert isinstance(definition["admin_review_required"], bool)
        assert isinstance(definition["public_chat_available"], bool)


def test_is_known_scope() -> None:
    assert is_known_scope("chat.read.current") is True
    assert is_known_scope("not.a.real.scope") is False


def test_is_public_chat_available_false_for_unknown_scope() -> None:
    assert is_public_chat_available("not.a.real.scope") is False


def test_high_sensitivity_scopes_are_never_public_chat_available() -> None:
    for scope_key in ("filesystem.write.user_selected", "calendar.write", "email.send", "microphone.capture", "camera.capture", "admin.assistant.invoke"):
        assert scope_definition(scope_key)["public_chat_available"] is False, scope_key


# -- plugin_manifest_validator -------------------------------------------------------------------


def test_validate_manifest_accepts_a_valid_manifest() -> None:
    result = validate_manifest(manifest=VALID_MANIFEST)
    assert result["valid"] is True
    assert result["problems"] == []


def test_validate_manifest_rejects_missing_required_field() -> None:
    manifest = dict(VALID_MANIFEST)
    del manifest["entrypoint"]
    result = validate_manifest(manifest=manifest)
    assert result["valid"] is False
    assert any("entrypoint" in problem for problem in result["problems"])


def test_validate_manifest_rejects_unknown_scope() -> None:
    manifest = dict(VALID_MANIFEST, requested_scopes=["not.a.real.scope"])
    result = validate_manifest(manifest=manifest)
    assert result["valid"] is False
    assert any("unknown" in problem for problem in result["problems"])


def test_validate_manifest_rejects_blank_plugin_id() -> None:
    manifest = dict(VALID_MANIFEST, plugin_id="   ")
    result = validate_manifest(manifest=manifest)
    assert result["valid"] is False


def test_validate_manifest_rejects_oversized_scope_list() -> None:
    manifest = dict(VALID_MANIFEST, requested_scopes=["chat.read.current"] * (MAX_SCOPES + 1))
    result = validate_manifest(manifest=manifest)
    assert result["valid"] is False
    assert any("requested_scopes exceeds" in problem for problem in result["problems"])


def test_validate_manifest_rejects_oversized_domain_list() -> None:
    manifest = dict(VALID_MANIFEST, allowed_domains=[f"d{i}.example.com" for i in range(MAX_ALLOWED_DOMAINS + 1)])
    result = validate_manifest(manifest=manifest)
    assert result["valid"] is False
    assert any("allowed_domains exceeds" in problem for problem in result["problems"])


def test_validate_manifest_rejects_wrong_type() -> None:
    manifest = dict(VALID_MANIFEST, requested_scopes="not-a-list")
    result = validate_manifest(manifest=manifest)
    assert result["valid"] is False


# -- plugin_capability_classifier / data_boundary_analyzer --------------------------------------


def test_classify_capabilities_maps_scopes_to_categories() -> None:
    result = classify_capabilities(requested_scopes=VALID_MANIFEST["requested_scopes"])
    assert "filesystem_access" in result["capability_categories"]
    assert "network_access" in result["capability_categories"]
    assert result["unknown_scopes"] == []


def test_classify_capabilities_flags_unknown_scope() -> None:
    result = classify_capabilities(requested_scopes=["not.a.real.scope"])
    assert result["unknown_scopes"] == ["not.a.real.scope"]


def test_classify_capabilities_flags_high_or_critical() -> None:
    result = classify_capabilities(requested_scopes=["email.send"])
    assert result["requests_high_or_critical_scope"] is True


def test_analyze_data_boundaries_well_bounded_for_valid_manifest() -> None:
    result = analyze_data_boundaries(
        requested_scopes=VALID_MANIFEST["requested_scopes"], allowed_domains=VALID_MANIFEST["allowed_domains"],
        filesystem_roots=VALID_MANIFEST["filesystem_roots"],
    )
    assert result["well_bounded"] is True


def test_analyze_data_boundaries_flags_unbounded_root() -> None:
    result = analyze_data_boundaries(
        requested_scopes=["filesystem.read.user_selected"], allowed_domains=[], filesystem_roots=["/"],
    )
    assert result["well_bounded"] is False
    assert any("unbounded" in issue for issue in result["issues"])


def test_analyze_data_boundaries_flags_network_scope_without_domains() -> None:
    result = analyze_data_boundaries(requested_scopes=["network.http.allowed_domains"], allowed_domains=[], filesystem_roots=[])
    assert result["well_bounded"] is False


# -- plugin_risk_scorer -- deterministic, and a real high-risk plugin -----------------------------


def test_compute_risk_score_is_deterministic() -> None:
    kwargs = {"sensitivity_counts": {"low": 1, "medium": 1, "high": 0, "critical": 0}, "domain_count": 2, "filesystem_write_requested": False, "cloud_storage_usage": False}
    first = compute_risk_score(**kwargs)
    second = compute_risk_score(**kwargs)
    assert first["risk_score"] == second["risk_score"]
    assert first["risk_level"] == second["risk_level"]


def test_compute_risk_score_high_risk_plugin() -> None:
    result = compute_risk_score(
        sensitivity_counts={"low": 0, "medium": 0, "high": 2, "critical": 1}, domain_count=10,
        filesystem_write_requested=True, cloud_storage_usage=True,
    )
    assert result["risk_level"] in ("high", "critical")
    assert result["risk_score"] > 20


def test_compute_risk_score_low_risk_plugin() -> None:
    result = compute_risk_score(sensitivity_counts={"low": 1, "medium": 0, "high": 0, "critical": 0}, domain_count=0, filesystem_write_requested=False, cloud_storage_usage=False)
    assert result["risk_level"] == "low"


# -- plugin_trust_evaluator -------------------------------------------------------------------


def test_evaluate_trust_signals_never_verifies_signature() -> None:
    result = evaluate_trust_signals(manifest=VALID_MANIFEST)
    assert result["signals"]["signature_verified"] is False
    assert result["trust_score"] >= 1


def test_evaluate_trust_signals_zero_for_empty_manifest_metadata() -> None:
    manifest = dict(VALID_MANIFEST, homepage="", support_url="", author="", signature_placeholder="")
    result = evaluate_trust_signals(manifest=manifest)
    assert result["trust_score"] == 0


# -- sandbox_profile_builder / filesystem_policy_builder / network_policy_builder -----------------


def test_build_sandbox_profile_never_permits_background_execution() -> None:
    profile = build_sandbox_profile(
        requested_scopes=VALID_MANIFEST["requested_scopes"], allowed_domains=VALID_MANIFEST["allowed_domains"],
        filesystem_roots=VALID_MANIFEST["filesystem_roots"], risk_level="critical",
    )
    assert profile["background_execution"] is False


def test_build_sandbox_profile_elevated_memory_for_high_risk() -> None:
    low = build_sandbox_profile(requested_scopes=[], allowed_domains=[], filesystem_roots=[], risk_level="low")
    high = build_sandbox_profile(requested_scopes=[], allowed_domains=[], filesystem_roots=[], risk_level="critical")
    assert high["memory_limit_mb"] > low["memory_limit_mb"]


def test_build_filesystem_policy_write_disabled_without_roots() -> None:
    policy = build_filesystem_policy(filesystem_roots=[], read_requested=True, write_requested=True)
    assert policy["read_enabled"] is False
    assert policy["write_enabled"] is False


def test_build_network_policy_normalizes_domains() -> None:
    policy = build_network_policy(network_enabled=True, allowed_domains=["Example.COM", "example.com"])
    assert policy["allowed_domains"] == ["example.com"]
    assert policy["domain_count"] == 1


def test_build_network_policy_empty_when_disabled() -> None:
    policy = build_network_policy(network_enabled=False, allowed_domains=["example.com"])
    assert policy["allowed_domains"] == []


# -- runtime_policy_evaluator (the permission engine) ---------------------------------------------


def test_evaluate_permission_unknown_scope_denies() -> None:
    result = evaluate_permission(scope_key="not.a.real.scope", plugin_status="enabled", is_public_chat=False, has_valid_consent=False, admin_reviewed=True, risk_level="low")
    assert result["decision"] == "deny"


def test_evaluate_permission_disabled_plugin() -> None:
    result = evaluate_permission(scope_key="chat.read.current", plugin_status="disabled", is_public_chat=False, has_valid_consent=False, admin_reviewed=True, risk_level="low")
    assert result["decision"] == "disabled"


def test_evaluate_permission_archived_plugin() -> None:
    result = evaluate_permission(scope_key="chat.read.current", plugin_status="archived", is_public_chat=False, has_valid_consent=False, admin_reviewed=True, risk_level="low")
    assert result["decision"] == "disabled"


def test_evaluate_permission_public_chat_denied_high_sensitivity_scope() -> None:
    result = evaluate_permission(scope_key="email.send", plugin_status="enabled", is_public_chat=True, has_valid_consent=True, admin_reviewed=True, risk_level="low")
    assert result["decision"] == "deny"


def test_evaluate_permission_requires_admin_review_for_admin_review_scope() -> None:
    result = evaluate_permission(scope_key="email.send", plugin_status="enabled", is_public_chat=False, has_valid_consent=True, admin_reviewed=False, risk_level="low")
    assert result["decision"] == "require_admin_review"


def test_evaluate_permission_requires_admin_review_for_high_risk_plugin() -> None:
    result = evaluate_permission(scope_key="chat.read.current", plugin_status="enabled", is_public_chat=False, has_valid_consent=False, admin_reviewed=False, risk_level="critical")
    assert result["decision"] == "require_admin_review"


def test_evaluate_permission_requires_consent() -> None:
    result = evaluate_permission(scope_key="filesystem.read.user_selected", plugin_status="enabled", is_public_chat=False, has_valid_consent=False, admin_reviewed=True, risk_level="low")
    assert result["decision"] == "require_consent"


def test_evaluate_permission_allows_when_all_checks_pass() -> None:
    result = evaluate_permission(scope_key="filesystem.read.user_selected", plugin_status="enabled", is_public_chat=False, has_valid_consent=True, admin_reviewed=True, risk_level="low")
    assert result["decision"] == "allow"


def test_evaluate_permission_low_sensitivity_scope_allowed_without_consent() -> None:
    result = evaluate_permission(scope_key="chat.read.current", plugin_status="enabled", is_public_chat=False, has_valid_consent=False, admin_reviewed=True, risk_level="low")
    assert result["decision"] == "allow"


# -- consent_policy_engine -------------------------------------------------------------------


def test_is_consent_valid_false_when_not_given() -> None:
    result = is_consent_valid(consent_given=False, expires_at_epoch_seconds=None, now_epoch_seconds=1000.0)
    assert result["valid"] is False


def test_is_consent_valid_expires() -> None:
    result = is_consent_valid(consent_given=True, expires_at_epoch_seconds=1000.0, now_epoch_seconds=2000.0)
    assert result["valid"] is False
    assert result["reason"] == "consent has expired"


def test_is_consent_valid_never_expires_without_ttl() -> None:
    result = is_consent_valid(consent_given=True, expires_at_epoch_seconds=None, now_epoch_seconds=999_999_999.0)
    assert result["valid"] is True


def test_build_consent_record_computes_expiry_from_ttl() -> None:
    record = build_consent_record(scope_key="chat.read.history", consent_given=True, ttl_seconds=3600.0, now_epoch_seconds=1000.0)
    assert record["expires_at"] == 4600.0


def test_build_consent_record_no_expiry_without_ttl() -> None:
    record = build_consent_record(scope_key="chat.read.history", consent_given=True, ttl_seconds=None, now_epoch_seconds=1000.0)
    assert record["expires_at"] is None


# -- plugin_execution_token_builder -- deterministic payload hashing -----------------------------


def test_build_execution_token_is_deterministic() -> None:
    kwargs = dict(
        plugin_public_id="plugin-1", granted_scopes=["chat.read.current"], user_id_hash="uh", session_id_hash="sh",
        issued_at_epoch_seconds=1000.0, nonce="fixed-nonce",
    )
    first = build_execution_token(**kwargs)
    second = build_execution_token(**kwargs)
    assert first["token_hash"] == second["token_hash"]
    assert len(first["token_hash"]) == 64


def test_build_execution_token_hash_changes_with_scopes() -> None:
    base = dict(plugin_public_id="plugin-1", user_id_hash="uh", session_id_hash="sh", issued_at_epoch_seconds=1000.0, nonce="fixed-nonce")
    a = build_execution_token(granted_scopes=["chat.read.current"], **base)
    b = build_execution_token(granted_scopes=["chat.read.history"], **base)
    assert a["token_hash"] != b["token_hash"]


def test_build_execution_token_rejects_too_many_scopes() -> None:
    with pytest.raises(ValueError):
        build_execution_token(
            plugin_public_id="p", granted_scopes=["chat.read.current"] * 21, user_id_hash="u", session_id_hash="s",
            issued_at_epoch_seconds=1000.0, nonce="n",
        )


def test_build_execution_token_rejects_non_positive_ttl() -> None:
    with pytest.raises(ValueError):
        build_execution_token(
            plugin_public_id="p", granted_scopes=["chat.read.current"], user_id_hash="u", session_id_hash="s",
            issued_at_epoch_seconds=1000.0, nonce="n", ttl_seconds=0,
        )


def test_is_token_expired() -> None:
    assert is_token_expired(expires_at_epoch_seconds=1000.0, now_epoch_seconds=1000.0) is True
    assert is_token_expired(expires_at_epoch_seconds=1000.0, now_epoch_seconds=999.0) is False


# -- plugin_marketplace_policy -------------------------------------------------------------------


def test_evaluate_marketplace_policy_never_permits_auto_install_or_enable() -> None:
    result = evaluate_marketplace_policy(source="manual_upload")
    assert result["auto_install_permitted"] is False
    assert result["auto_enable_permitted"] is False
    assert result["requires_manual_admin_registration"] is True


def test_evaluate_marketplace_policy_rejects_unknown_source() -> None:
    result = evaluate_marketplace_policy(source="internet_auto_scan")
    assert result["allowed"] is False


# -- audit_record_builder -------------------------------------------------------------------


def test_build_audit_record_never_decides_anything_itself() -> None:
    record = build_audit_record(event_type="permission_granted", plugin_public_id="p1", stage="grant_permission", actor="admin-1", metadata={"scope_key": "chat.read.current"})
    assert record["event_type"] == "permission_granted"
    assert record["actor"] == "admin-1"


# -- plugin_runtime_report_generator -------------------------------------------------------------------


def test_generate_governance_report_discloses_all_step20_limitations() -> None:
    report = generate_governance_report(
        plugin_public_id="p1", name="n", version="1.0.0", status="enabled", stage="governance_report",
        validation_report={"valid": True}, capability_classification={}, risk_score=5.0, risk_level="low",
        trust_signals={}, sandbox_profile={}, filesystem_policy={}, network_policy={},
        permission_summary={"granted_count": 1}, event_count=3, generated_at="now",
    )
    for key in (
        "no_real_sandbox_execution", "no_os_level_isolation", "no_signed_plugin_verification", "no_drm",
        "no_anti_tamper_protection", "no_marketplace_billing", "no_automatic_update_system",
        "no_plugin_binary_execution", "execution_tokens_are_governance_metadata_only",
    ):
        assert report[key] is True, key
