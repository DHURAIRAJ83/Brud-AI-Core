"""Phase 10 Step 21 (dedicated security/resilience pass). These tests
directly assert the task's own non-negotiable rules: bounded
execution, redacted/bounded raw evidence, no fetch of an
attacker-controlled URL from provider response content, one
provider's failure never discarding another's results, and full
auditability of every search.
"""

import ast
import inspect
import json
import re
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.external_data_providers import (
    ExternalDataProviderRepository,
)
from backend.services.external_data_connectors.base import HttpResponse
from backend.services.external_data_provider_service import ExternalDataProviderService
from backend.services.external_dataset_search_service import (
    ExternalDatasetCandidateService,
    ExternalDatasetSearchExecutionService,
    ExternalDatasetSearchSessionService,
    build_query,
)
from core_model.data_discovery import (
    MAX_CANDIDATES_PER_SESSION,
    MAX_PROVIDERS_PER_SEARCH,
    MAX_QUERY_LENGTH,
    MAX_RESULTS_PER_PROVIDER,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "security.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _enable_provider(settings: Settings, provider_code: str):
    provider_repository = ExternalDataProviderRepository(settings.resolved_database_path)
    provider = provider_repository.get_provider_by_code(provider_code)
    provider_repository.update_provider(
        provider["public_id"], {"lifecycle_status": "enabled", "enabled": 1}
    )
    provider_repository.upsert_capability(
        provider["public_id"], {"capability_type": "search_datasets", "enabled": True}
    )
    return provider_repository.get_provider(provider["public_id"])


def _ready_session(settings: Settings, **requirement_overrides):
    session_service = ExternalDatasetSearchSessionService(settings)
    session = session_service.create_session(title="Security test", admin_id=ADMIN_ID)
    values = {"languages": ["tamil"], "tasks": ["asr"]}
    values.update(requirement_overrides)
    session_service.set_requirements(session["public_id"], values, admin_id=ADMIN_ID)
    return session


# -- bounded execution ---------------------------------------------------


def test_query_is_bounded_to_max_query_length() -> None:
    huge_text = "x" * (MAX_QUERY_LENGTH * 5)
    requirement = {
        "free_text_requirement": huge_text,
        "domain_tags": [],
        "tasks": [],
        "languages": [],
    }
    query = build_query(requirement)
    assert len(query) == MAX_QUERY_LENGTH


def test_max_providers_per_search_is_enforced(settings: Settings) -> None:
    provider_service = ExternalDataProviderService(settings)
    for index in range(MAX_PROVIDERS_PER_SEARCH + 4):
        provider = provider_service.register_provider(
            {
                "provider_code": f"bulk-provider-{index}",
                "name": f"Bulk Provider {index}",
                "provider_type": "custom_api",
                "access_mode": "public",
            },
            ADMIN_ID,
        )
        provider_service.repository.update_provider(
            provider["public_id"], {"lifecycle_status": "enabled", "enabled": 1}
        )
        provider_service.repository.upsert_capability(
            provider["public_id"], {"capability_type": "search_datasets", "enabled": True}
        )

    session = _ready_session(settings)

    def transport(url, headers, timeout_seconds):
        del url, headers, timeout_seconds
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True, body="{}")

    execution_service = ExternalDatasetSearchExecutionService(settings, transport=transport)
    execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    runs = execution_service.repository.list_provider_runs(session["public_id"])
    assert len(runs) == MAX_PROVIDERS_PER_SEARCH


def test_max_results_per_provider_is_enforced(settings: Settings) -> None:
    _enable_provider(settings, "huggingface")
    session = _ready_session(settings)

    items = [
        {"id": f"org/dataset-{index}", "cardData": {}, "tags": []}
        for index in range(MAX_RESULTS_PER_PROVIDER + 5)
    ]

    def transport(url, headers, timeout_seconds):
        del headers, timeout_seconds
        if "huggingface.co/api/datasets" in url:
            return HttpResponse(
                status_code=200, elapsed_ms=1, reachable=True, body=json.dumps(items)
            )
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True, body="{}")

    execution_service = ExternalDatasetSearchExecutionService(settings, transport=transport)
    execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    runs = execution_service.repository.list_provider_runs(session["public_id"])
    huggingface_run = next(run for run in runs if run["provider_code"] == "huggingface")
    assert huggingface_run["result_count"] == MAX_RESULTS_PER_PROVIDER

    candidates = execution_service.repository.list_candidates(session["public_id"])
    assert len(candidates) == MAX_RESULTS_PER_PROVIDER


def test_max_candidates_per_session_is_enforced(settings: Settings) -> None:
    _enable_provider(settings, "huggingface")
    session = _ready_session(settings)

    candidate_service = ExternalDatasetCandidateService(settings)
    pre_fill_count = MAX_CANDIDATES_PER_SESSION - 15
    for index in range(pre_fill_count):
        candidate_service.add_manual_candidate(
            session["public_id"], {"canonical_name": f"Pre-filled {index}"}, admin_id=ADMIN_ID
        )

    items = [
        {"id": f"org/new-dataset-{index}", "cardData": {}, "tags": []}
        for index in range(MAX_RESULTS_PER_PROVIDER)
    ]

    def transport(url, headers, timeout_seconds):
        del headers, timeout_seconds
        if "huggingface.co/api/datasets" in url:
            return HttpResponse(
                status_code=200, elapsed_ms=1, reachable=True, body=json.dumps(items)
            )
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True, body="{}")

    execution_service = ExternalDatasetSearchExecutionService(settings, transport=transport)
    execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    candidates = execution_service.repository.list_candidates(session["public_id"])
    assert len(candidates) == MAX_CANDIDATES_PER_SESSION

    runs = execution_service.repository.list_provider_runs(session["public_id"])
    huggingface_run = next(run for run in runs if run["provider_code"] == "huggingface")
    assert huggingface_run["status"] == "partial"
    assert "session_candidate_cap_reached" in huggingface_run["warnings"]


# -- raw evidence is bounded, redacted, and never executed ----------------


def test_secret_shaped_fields_in_provider_response_are_redacted_before_persistence(
    settings: Settings,
) -> None:
    _enable_provider(settings, "huggingface")
    session = _ready_session(settings)

    items = [
        {
            "id": "org/secret-bearing-dataset",
            "cardData": {"summary": "desc"},
            "tags": [],
            "auth_token": "super-secret-do-not-leak",
            "nested": {"api_key": "another-secret"},
        }
    ]

    def transport(url, headers, timeout_seconds):
        del headers, timeout_seconds
        if "huggingface.co/api/datasets" in url:
            return HttpResponse(
                status_code=200, elapsed_ms=1, reachable=True, body=json.dumps(items)
            )
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True, body="{}")

    execution_service = ExternalDatasetSearchExecutionService(settings, transport=transport)
    execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    candidates = execution_service.repository.list_candidates(session["public_id"])
    sources = execution_service.repository.list_candidate_sources(candidates[0]["public_id"])
    raw_metadata_text = json.dumps(sources[0]["raw_metadata"])
    assert "super-secret-do-not-leak" not in raw_metadata_text
    assert "another-secret" not in raw_metadata_text
    assert "[REDACTED]" in raw_metadata_text


def test_provider_supplied_urls_are_never_fetched_only_registered_domains_are(
    settings: Settings,
) -> None:
    """A malicious provider response can put any URL it wants into
    homepage_url/repository_url/dataset_card_url -- the connector must
    never follow those into a further request. Every URL this test
    observes the transport being called with must resolve to the
    provider's own already-registered domain, never the attacker's."""

    _enable_provider(settings, "huggingface")
    session = _ready_session(settings)

    items = [
        {
            "id": "org/malicious-dataset",
            "cardData": {},
            "tags": [],
            "homepage": "http://attacker.example/exfiltrate",
        }
    ]
    called_urls: list[str] = []

    def transport(url, headers, timeout_seconds):
        del headers, timeout_seconds
        called_urls.append(url)
        if "huggingface.co/api/datasets" in url:
            return HttpResponse(
                status_code=200, elapsed_ms=1, reachable=True, body=json.dumps(items)
            )
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True, body="{}")

    execution_service = ExternalDatasetSearchExecutionService(settings, transport=transport)
    execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    assert all("attacker.example" not in url for url in called_urls)
    assert all(url.startswith("https://huggingface.co/") for url in called_urls)


# -- one provider's failure never discards another's results --------------


def test_one_provider_crash_never_discards_another_providers_candidates(
    settings: Settings,
) -> None:
    _enable_provider(settings, "huggingface")
    _enable_provider(settings, "github")
    session = _ready_session(settings)

    def transport(url, headers, timeout_seconds):
        del headers, timeout_seconds
        if "huggingface.co" in url:
            raise RuntimeError("simulated crash inside a single provider's request")
        if "api.github.com/search/repositories" in url:
            payload = {
                "items": [
                    {"full_name": "org/safe-repo", "owner": {"login": "org"}, "topics": []}
                ]
            }
            return HttpResponse(
                status_code=200, elapsed_ms=1, reachable=True, body=json.dumps(payload)
            )
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True, body="{}")

    execution_service = ExternalDatasetSearchExecutionService(settings, transport=transport)
    result = execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    assert result["status"] == "partial"
    candidates = execution_service.repository.list_candidates(session["public_id"])
    assert len(candidates) == 1
    assert candidates[0]["canonical_name"] == "safe-repo"


# -- every search is auditable ---------------------------------------------


def test_every_search_is_recorded_in_both_session_events_and_global_audit_log(
    settings: Settings,
) -> None:
    session = _ready_session(settings)

    def transport(url, headers, timeout_seconds):
        del url, headers, timeout_seconds
        return HttpResponse(status_code=200, elapsed_ms=1, reachable=True, body="{}")

    execution_service = ExternalDatasetSearchExecutionService(settings, transport=transport)
    execution_service.run_search(session["public_id"], admin_id=ADMIN_ID)

    events = execution_service.repository.list_events(session["public_id"], limit=50)
    event_types = {event["event_type"] for event in events}
    assert "search_started" in event_types
    assert {"search_completed", "search_partial", "search_failed"} & event_types

    audit_repository = AuditLogRepository(settings.resolved_database_path)
    audit_events = audit_repository.recent(limit=50)
    assert any(
        event.event_type == "external_dataset_search_completed"
        and event.resource_public_id == session["public_id"]
        for event in audit_events
    )


# -- no code path here ever executes untrusted provider content -----------


def test_no_dynamic_execution_or_shell_primitives_in_discovery_modules() -> None:
    """Structural guardrail (mirrors `test_scoring_never_uses_popularity_
    signal`'s pattern): scans every Phase 10 module that parses an
    untrusted provider response for dangerous primitives that would let
    provider-controlled text run as code or a shell command."""

    # Matched as an actual call (`name(`), not a bare substring -- a
    # docstring saying "executes" or "compiles" must never fail this.
    forbidden_patterns = [
        re.compile(r"(?<![.\w])eval\s*\("),
        re.compile(r"(?<![.\w])exec\s*\("),
        re.compile(r"(?<![.\w])compile\s*\("),
        re.compile(r"os\.system\s*\("),
        re.compile(r"os\.popen\s*\("),
        re.compile(r"subprocess\.(run|Popen|call)\s*\("),
        re.compile(r"pickle\.(loads|load)\s*\("),
        re.compile(r"__import__\s*\("),
    ]
    modules = [
        "backend.services.external_data_connectors.base",
        "backend.services.external_data_connectors.builtin",
        "backend.services.external_dataset_normalization_service",
        "backend.services.external_dataset_deduplication_service",
        "backend.services.external_dataset_scoring_service",
        "backend.services.external_dataset_comparison_service",
        "backend.services.external_dataset_search_service",
    ]
    import importlib

    for module_name in modules:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        for pattern in forbidden_patterns:
            match = pattern.search(source)
            assert match is None, f"{pattern.pattern!r} matched in {module_name}: {match}"


def test_connector_search_methods_never_construct_urls_from_ast_fstrings_with_raw_response_vars() -> None:  # noqa: E501
    """A cheaper, static complement to the runtime redirect test above:
    every connector's `search_datasets`/`get_dataset_metadata` must
    build its request URL only from `domain`/`config` values it already
    resolved from the provider's own registered domains -- never from
    an `entry`/`payload`/`item` variable that holds parsed, untrusted
    response content."""

    from backend.services.external_data_connectors import builtin as builtin_module

    source = inspect.getsource(builtin_module)
    tree = ast.parse(source)
    untrusted_names = {"entry", "payload", "item", "hits", "items_raw"}
    url_pattern = re.compile(r"^\s*url\s*=", re.MULTILINE)
    assert url_pattern.search(source), "expected at least one url assignment to inspect"

    class UrlAssignmentVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.violations: list[str] = []

        def visit_Assign(self, node: ast.Assign) -> None:
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "url" in targets:
                names_used = {
                    n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)
                }
                bad = names_used & untrusted_names
                if bad:
                    self.violations.append(f"line {node.lineno}: url built from {bad}")
            self.generic_visit(node)

    visitor = UrlAssignmentVisitor()
    visitor.visit(tree)
    assert visitor.violations == [], visitor.violations
