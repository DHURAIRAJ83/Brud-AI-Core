"""MB-48 P5: internal pilot usage telemetry -- every counter is a real
row in the existing, already-append-only `audit_logs` table (via
`AuditLogRepository`), never a new table or an external analytics
service. Covers `record_pilot_metric`/`pilot_metric_counts` directly,
plus the real service call sites that emit them
(`MiniBrainLlmRuntimeService.chat/grounded_chat/
set_default_retrieval_profile`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories import AuditLogRepository
from backend.models.domain import AuditEventCreate
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from backend.services.pilot_metrics import PILOT_METRIC_ACTIONS, pilot_metric_counts, record_pilot_metric


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allowed_model_dir=tmp_path / "models", allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


class _RecordingAdapter:
    backend_type = "local"

    def is_available(self) -> bool:
        return True

    def generate(self, *, messages, max_tokens=None, temperature=None):
        return {"text": "reply", "backend_type": "local", "tokens_generated": 1, "latency_ms": 1.0, "error_message": None}


class _StubRetrievalService:
    def __init__(self, results: list[dict]) -> None:
        self._results = results

    def retrieve(self, payload, admin_id):
        return {"public_id": "run-1", "results": self._results}


MB35_CHUNK = {
    "chunk_public_id": "chunk-1",
    "source_public_id": "c1cf3a96-f92d-4a61-a2cf-d448f947a057",
    "source_version_public_id": "ea0ad840-42b8-43f2-9419-5a384c0e050e",
    "rank": 1,
    "combined_score": 0.5,
    "normalized_text": "Test phrase",
}


class _StubRetrievalServiceForDefault:
    def __init__(self, profile: dict) -> None:
        self._profile = profile

    def get_profile(self, public_id: str) -> dict:
        return self._profile

    def list_profiles(self) -> dict:
        return {"items": [self._profile]}


def test_all_six_metrics_are_defined() -> None:
    assert set(PILOT_METRIC_ACTIONS) == {
        "widget_plain_chat_count",
        "widget_grounded_chat_count",
        "grounded_chat_citation_render_count",
        "retrieval_profile_switch_count",
        "prompt_optimization_run_count",
        "gateway_export_run_count",
    }


def test_pilot_metric_counts_starts_at_zero(settings: Settings) -> None:
    counts = pilot_metric_counts(settings)
    assert counts == {metric: 0 for metric in PILOT_METRIC_ACTIONS}


def test_record_pilot_metric_writes_a_real_audit_row_and_is_counted(settings: Settings) -> None:
    record_pilot_metric(settings, "widget_plain_chat_count")
    record_pilot_metric(settings, "widget_plain_chat_count")
    assert pilot_metric_counts(settings)["widget_plain_chat_count"] == 2

    events = AuditLogRepository(settings.resolved_database_path).recent(limit=10)
    assert len([event for event in events if event.action == "widget_plain_chat_count"]) == 2
    assert all(event.event_type == "pilot_metric" for event in events)


def test_record_pilot_metric_rejects_gateway_export_run_count(settings: Settings) -> None:
    # gateway_export_run_count is derived from an event the export
    # service already writes -- nothing should record it directly.
    with pytest.raises(ValueError):
        record_pilot_metric(settings, "gateway_export_run_count")


def test_record_pilot_metric_rejects_unknown_metric(settings: Settings) -> None:
    with pytest.raises(ValueError):
        record_pilot_metric(settings, "not_a_real_metric")


def test_record_pilot_metric_is_a_noop_when_audit_disabled(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allowed_model_dir=tmp_path / "models", allow_external_storage=True, log_level="CRITICAL",
        audit_enabled=False,
    )
    initialize_database(settings.resolved_database_path)
    record_pilot_metric(settings, "widget_plain_chat_count")
    assert pilot_metric_counts(settings)["widget_plain_chat_count"] == 0


def test_gateway_export_run_count_counts_the_existing_export_audit_action(settings: Settings) -> None:
    # Real reuse of ExternalGatewayDatasetBridgeService's own existing
    # audit action -- simulated here by writing the same action a real
    # completed export already writes, without re-running the whole
    # export pipeline.
    AuditLogRepository(settings.resolved_database_path).append(
        AuditEventCreate(
            event_type="external_gateway_dataset_bridge", actor_type="admin",
            action="external_gateway_dataset_export_completed", resource_type="gateway_session",
        )
    )
    assert pilot_metric_counts(settings)["gateway_export_run_count"] == 1


def test_chat_records_widget_plain_chat_count(settings: Settings) -> None:
    service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: _RecordingAdapter())
    service.chat(session_id=None, message="hello", admin_id="admin-1")
    assert pilot_metric_counts(settings)["widget_plain_chat_count"] == 1
    assert pilot_metric_counts(settings)["widget_grounded_chat_count"] == 0


def test_grounded_chat_with_citations_records_both_grounded_and_citation_metrics(settings: Settings) -> None:
    stub_retrieval = _StubRetrievalService(results=[MB35_CHUNK])
    service = MiniBrainLlmRuntimeService(
        settings, adapter_factory=lambda: _RecordingAdapter(), retrieval_service=stub_retrieval,
    )
    service.grounded_chat(
        session_id=None, message="What is the test phrase?",
        retrieval_profile_public_id="profile-1", top_k=4, admin_id="admin-1",
    )
    counts = pilot_metric_counts(settings)
    assert counts["widget_grounded_chat_count"] == 1
    assert counts["grounded_chat_citation_render_count"] == 1
    assert counts["widget_plain_chat_count"] == 0


def test_grounded_chat_without_a_profile_does_not_record_citation_metric(settings: Settings) -> None:
    service = MiniBrainLlmRuntimeService(settings, adapter_factory=lambda: _RecordingAdapter())
    service.grounded_chat(
        session_id=None, message="What is the test phrase?",
        retrieval_profile_public_id=None, top_k=4, admin_id="admin-1",
    )
    counts = pilot_metric_counts(settings)
    assert counts["widget_grounded_chat_count"] == 1
    assert counts["grounded_chat_citation_render_count"] == 0


def test_set_default_retrieval_profile_records_switch_count(settings: Settings) -> None:
    stub = _StubRetrievalServiceForDefault(profile={"public_id": "profile-b", "name": "Profile B", "status": "active"})
    service = MiniBrainLlmRuntimeService(settings, retrieval_service=stub)
    service.set_default_retrieval_profile("profile-b", "admin-1")
    assert pilot_metric_counts(settings)["retrieval_profile_switch_count"] == 1
