"""MB-40: service-level tests for ExternalGatewayDatasetBridgeService --
real database, real MB-21 gateway service (mocked provider client only,
same `MockProviderClient` double MB-21's own tests use -- no real
network call), real DatasetService, real RagIngestionService.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.external_ai_provider_client import MockProviderClient
from backend.services.external_gateway_dataset_bridge_service import ExternalGatewayDatasetBridgeService
from backend.services.mini_brain_external_ai_gateway_service import MiniBrainExternalAiGatewayService
from backend.services.rag_ingestion_service import RagIngestionService
from backend.database.repositories.rag import RagRepository
from backend.models.rag import KnowledgeSpaceCreate

ADMIN_ID = "00000000-0000-0000-0000-000000000042"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    result = Settings(
        database_path=tmp_path / "bridge.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    with database_connection(result.resolved_database_path) as connection:
        connection.execute(
            "INSERT INTO admin_accounts(public_id, username, display_name, password_hash) VALUES (?,?,?,?)",
            (ADMIN_ID, "bridge-test-admin", "Bridge Test Admin", "hash"),
        )
        connection.commit()
    return result


def _gateway(settings: Settings, provider_clients: dict) -> MiniBrainExternalAiGatewayService:
    return MiniBrainExternalAiGatewayService(settings, provider_clients=provider_clients)


def _run_to_report(gateway: MiniBrainExternalAiGatewayService, session_public_id: str, admin_id: str, *, provider_keys: list[str]) -> dict:
    session = gateway.run_validate_authorization_stage(session_public_id, authorization_note="bridge test authorization", admin_id=admin_id)
    session = gateway.run_sanitize_inputs_stage(session["public_id"], admin_stated_need="find Tamil speech datasets", admin_id=admin_id)
    session = gateway.run_select_providers_stage(session["public_id"], requested_provider_keys=provider_keys, admin_id=admin_id)
    session = gateway.run_dispatch_requests_stage(session["public_id"], admin_id=admin_id)
    session = gateway.run_collect_responses_stage(session["public_id"], admin_id=admin_id)
    session = gateway.run_normalize_responses_stage(session["public_id"], admin_id=admin_id)
    session = gateway.run_analyze_agreement_stage(session["public_id"], admin_id=admin_id)
    session = gateway.run_build_evidence_stage(session["public_id"], admin_id=admin_id)
    session = gateway.generate_report_stage(session["public_id"], admin_id=admin_id)
    return session


def _accepted_session(settings: Settings, *, canned_text: str = "Tamil speech dataset guidance from a provider.") -> tuple[MiniBrainExternalAiGatewayService, dict]:
    mock = MockProviderClient(provider_key="mock1", canned_text=canned_text)
    gateway = _gateway(settings, {"mock1": mock})
    session = gateway.create_session(
        topic="Tamil dataset sourcing", purpose="data_acquisition_assistance", admin_id=ADMIN_ID,
    )
    session = _run_to_report(gateway, session["public_id"], ADMIN_ID, provider_keys=["mock1"])
    assert session["stage"] == "awaiting_admin_review"
    session = gateway.admin_review(session["public_id"], decision="accept", admin_id=ADMIN_ID)
    assert session["status"] == "admin_accepted"
    return gateway, session


def _audit_events(settings: Settings, session_public_id: str) -> list[str]:
    with database_connection(settings.resolved_database_path) as connection:
        rows = connection.execute(
            "SELECT event_type FROM audit_logs WHERE resource_public_id=? AND "
            "resource_type='external_gateway_dataset_bridge' ORDER BY id",
            (session_public_id,),
        ).fetchall()
    return [row["event_type"] for row in rows]


# -- accepted session creates real draft records ---------------------------------------


def test_accepted_session_creates_draft_dataset_records(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)

    result = bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)

    assert len(result["created_record_public_ids"]) == 1
    assert result["duplicate_provider_run_public_ids"] == []
    assert result["skipped_provider_run_public_ids"] == []

    with database_connection(settings.resolved_database_path) as connection:
        row = connection.execute(
            "SELECT status, output_text, source_id FROM dataset_records WHERE public_id=?",
            (result["created_record_public_ids"][0],),
        ).fetchone()
    assert row["status"] == "draft"
    assert "Tamil speech dataset guidance" in row["output_text"]

    with database_connection(settings.resolved_database_path) as connection:
        source_row = connection.execute(
            "SELECT public_id, metadata_json FROM dataset_sources WHERE public_id=?",
            (result["dataset_source_public_id"],),
        ).fetchone()
    assert source_row is not None
    import json

    source_metadata = json.loads(source_row["metadata_json"])
    assert source_metadata["source"] == "external_provider"
    assert source_metadata["external_gateway_session_public_id"] == session["public_id"]


def test_created_record_metadata_records_source_provenance(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    result = bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)

    with database_connection(settings.resolved_database_path) as connection:
        row = connection.execute(
            "SELECT metadata_json FROM dataset_records WHERE public_id=?",
            (result["created_record_public_ids"][0],),
        ).fetchone()
    import json

    metadata = json.loads(row["metadata_json"])
    assert metadata["source"] == "external_provider"
    assert metadata["external_gateway_session_public_id"] == session["public_id"]
    assert metadata["provider_name"] == "mock1"
    assert "exported_at" in metadata


# -- rejected / not-yet-accepted sessions never export ----------------------------------


def test_rejected_session_creates_no_records(settings: Settings) -> None:
    mock = MockProviderClient(provider_key="mock1", canned_text="some text")
    gateway = _gateway(settings, {"mock1": mock})
    session = gateway.create_session(topic="t", purpose="data_acquisition_assistance", admin_id=ADMIN_ID)
    session = _run_to_report(gateway, session["public_id"], ADMIN_ID, provider_keys=["mock1"])
    session = gateway.admin_review(session["public_id"], decision="reject", admin_id=ADMIN_ID)
    assert session["status"] == "admin_rejected"

    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    with pytest.raises(ValidationError):
        bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)

    with database_connection(settings.resolved_database_path) as connection:
        count = connection.execute("SELECT COUNT(*) AS n FROM dataset_records").fetchone()["n"]
    assert count == 0


def test_needs_followup_session_creates_no_records(settings: Settings) -> None:
    mock = MockProviderClient(provider_key="mock1", canned_text="some text")
    gateway = _gateway(settings, {"mock1": mock})
    session = gateway.create_session(topic="t", purpose="data_acquisition_assistance", admin_id=ADMIN_ID)
    session = _run_to_report(gateway, session["public_id"], ADMIN_ID, provider_keys=["mock1"])
    session = gateway.admin_review(session["public_id"], decision="needs_followup", admin_id=ADMIN_ID)

    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    with pytest.raises(ValidationError):
        bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)


def test_pending_session_before_any_review_creates_no_records(settings: Settings) -> None:
    mock = MockProviderClient(provider_key="mock1", canned_text="some text")
    gateway = _gateway(settings, {"mock1": mock})
    session = gateway.create_session(topic="t", purpose="data_acquisition_assistance", admin_id=ADMIN_ID)
    session = _run_to_report(gateway, session["public_id"], ADMIN_ID, provider_keys=["mock1"])
    assert session["stage"] == "awaiting_admin_review"

    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    with pytest.raises(ValidationError):
        bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)


# -- duplicate handling (real DatasetService content-hash dedupe reused) ---------------


def test_exporting_the_same_accepted_session_twice_reports_duplicates(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)

    first = bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)
    assert len(first["created_record_public_ids"]) == 1

    second = bridge.export_accepted_session(
        session["public_id"], admin_id=ADMIN_ID, target_source_public_id=first["dataset_source_public_id"],
    )
    assert second["created_record_public_ids"] == []
    assert len(second["duplicate_provider_run_public_ids"]) == 1

    with database_connection(settings.resolved_database_path) as connection:
        count = connection.execute("SELECT COUNT(*) AS n FROM dataset_records").fetchone()["n"]
    assert count == 1


# -- audit events -----------------------------------------------------------------------


def test_successful_export_writes_started_and_completed_audit_events(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)

    events = _audit_events(settings, session["public_id"])
    assert "external_gateway_dataset_export_started" in events
    assert "external_gateway_dataset_export_completed" in events
    assert "external_gateway_dataset_export_failed" not in events


def test_refused_export_writes_no_started_or_completed_event(settings: Settings) -> None:
    mock = MockProviderClient(provider_key="mock1", canned_text="some text")
    gateway = _gateway(settings, {"mock1": mock})
    session = gateway.create_session(topic="t", purpose="data_acquisition_assistance", admin_id=ADMIN_ID)
    session = _run_to_report(gateway, session["public_id"], ADMIN_ID, provider_keys=["mock1"])
    session = gateway.admin_review(session["public_id"], decision="reject", admin_id=ADMIN_ID)

    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    with pytest.raises(ValidationError):
        bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)

    # The status check happens before the started/completed audit pair --
    # a refused export must not even claim to have started.
    events = _audit_events(settings, session["public_id"])
    assert events == []


# -- the gateway's own review logic is never touched -------------------------------------


def test_gateway_review_events_are_unaffected_by_export(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    events_before = gateway.events(session["public_id"])["items"]

    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)

    events_after = gateway.events(session["public_id"])["items"]
    assert len(events_after) == len(events_before)  # export writes to its own audit trail, not the gateway's


# -- optional RAG ingestion flag ----------------------------------------------------------


def test_ingest_to_rag_requires_a_space_id(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    with pytest.raises(ValidationError):
        bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True)


def test_ingest_to_rag_registers_a_real_rag_source_when_requested(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    rag = RagIngestionService(RagRepository(settings.resolved_database_path), settings)
    space = rag.create_space(KnowledgeSpaceCreate(name="MB-40 bridge space", slug="mb40-bridge-space"), ADMIN_ID)

    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway, rag_ingestion_service=rag)
    result = bridge.export_accepted_session(
        session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True, rag_knowledge_space_public_id=space["public_id"],
    )
    assert len(result["rag_source_public_ids"]) == 1
    rag_source = rag.get_source(result["rag_source_public_ids"][0])
    assert rag_source["public_id"] == result["rag_source_public_ids"][0]


def test_ingest_to_rag_false_by_default_never_touches_rag(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    result = bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID)
    assert result["ingest_to_rag"] is False
    assert result["rag_source_public_ids"] == []


def test_export_requires_real_admin_id(settings: Settings) -> None:
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(settings, gateway_service=gateway)
    with pytest.raises(ValidationError):
        bridge.export_accepted_session(session["public_id"], admin_id="")
