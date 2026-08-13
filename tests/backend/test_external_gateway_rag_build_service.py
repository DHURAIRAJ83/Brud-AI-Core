"""MB-41: service-level tests for the RAG-build continuation of
ExternalGatewayDatasetBridgeService.export_accepted_session(). Real
database, real MB-21 gateway (MockProviderClient only), real
DatasetService, real RagIngestionService/RagRetrievalService --
nothing about the RAG pipeline itself is mocked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.rag import RagRepository
from backend.models.rag import EmbeddingModelCreate, KnowledgeSpaceCreate
from backend.services.external_ai_provider_client import MockProviderClient
from backend.services.external_gateway_dataset_bridge_service import ExternalGatewayDatasetBridgeService
from backend.services.mini_brain_external_ai_gateway_service import MiniBrainExternalAiGatewayService
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_retrieval_service import RagRetrievalService

ADMIN_ID = "00000000-0000-0000-0000-0000000000b1"
KNOWN_PHRASE = "KAVERI-MANGO-9931"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    result = Settings(
        database_path=tmp_path / "rag_build.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    with database_connection(result.resolved_database_path) as connection:
        connection.execute(
            "INSERT INTO admin_accounts(public_id, username, display_name, password_hash) VALUES (?,?,?,?)",
            (ADMIN_ID, "rag-build-test-admin", "RAG Build Test Admin", "hash"),
        )
        connection.commit()
    return result


def _rag_services(settings: Settings) -> tuple[RagIngestionService, RagRetrievalService]:
    repo = RagRepository(settings.resolved_database_path)
    return RagIngestionService(repo, settings), RagRetrievalService(repo, settings)


def _register_embedding_model(rag_ingestion: RagIngestionService) -> dict:
    return rag_ingestion.create_embedding_model(
        EmbeddingModelCreate(
            name="mb41-test-embedder", version="1", provider_type="local_custom_embedding",
            dimensions=64, maximum_input_tokens=2048, supported_languages=["en"],
        ),
        ADMIN_ID,
    )


_DEFAULT_CANNED_TEXT = (
    f"MB-41 RAG build verification document. Test phrase: {KNOWN_PHRASE}. "
    "This content is long enough to clear the chunk-quality minimum-character threshold "
    "so it is accepted for embedding rather than rejected as too short."
)


def _accepted_session(settings: Settings, *, canned_text: str = _DEFAULT_CANNED_TEXT) -> tuple[MiniBrainExternalAiGatewayService, dict]:
    mock = MockProviderClient(provider_key="mock1", canned_text=canned_text)
    gateway = MiniBrainExternalAiGatewayService(settings, provider_clients={"mock1": mock})
    session = gateway.create_session(topic="MB-41 RAG build test", purpose="data_acquisition_assistance", admin_id=ADMIN_ID)
    sid = session["public_id"]
    gateway.run_validate_authorization_stage(sid, authorization_note="rag build test", admin_id=ADMIN_ID)
    gateway.run_sanitize_inputs_stage(sid, admin_stated_need="find data", admin_id=ADMIN_ID)
    gateway.run_select_providers_stage(sid, requested_provider_keys=["mock1"], admin_id=ADMIN_ID)
    gateway.run_dispatch_requests_stage(sid, admin_id=ADMIN_ID)
    gateway.run_collect_responses_stage(sid, admin_id=ADMIN_ID)
    gateway.run_normalize_responses_stage(sid, admin_id=ADMIN_ID)
    gateway.run_analyze_agreement_stage(sid, admin_id=ADMIN_ID)
    gateway.run_build_evidence_stage(sid, admin_id=ADMIN_ID)
    gateway.generate_report_stage(sid, admin_id=ADMIN_ID)
    session = gateway.admin_review(sid, decision="accept", admin_id=ADMIN_ID)
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


# -- RAG objects are created (all present, all real) ----------------------------------


def test_build_rag_index_creates_all_expected_objects(settings: Settings) -> None:
    rag_ingestion, rag_retrieval = _rag_services(settings)
    _register_embedding_model(rag_ingestion)
    space = rag_ingestion.create_space(
        KnowledgeSpaceCreate(name="MB-41 space", slug="mb41-space"), ADMIN_ID
    )
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(
        settings, gateway_service=gateway, rag_ingestion_service=rag_ingestion, rag_retrieval_service=rag_retrieval,
    )

    result = bridge.export_accepted_session(
        session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True,
        rag_knowledge_space_public_id=space["public_id"], build_rag_index=True,
        retrieval_profile_name="MB-41 retrieval profile",
    )

    assert len(result["source_version_public_ids"]) == 1
    assert len(result["chunk_set_public_ids"]) == 1
    assert len(result["embedding_run_public_ids"]) == 1
    assert len(result["vector_index_public_ids"]) == 1
    assert result["retrieval_profile_public_id"] is not None

    # Every object is a real, independently-fetchable row.
    version = rag_ingestion.get_source_version(result["source_version_public_ids"][0])
    assert version["status"] == "ready"
    chunk_set = rag_ingestion.get_chunk_set(result["chunk_set_public_ids"][0])
    assert chunk_set["status"] == "validated"
    embedding_run = rag_ingestion.get_embedding_run(result["embedding_run_public_ids"][0])
    assert embedding_run["status"] in {"completed", "completed_with_warnings"}
    vector_index = rag_ingestion.get_vector_index(result["vector_index_public_ids"][0])
    assert vector_index["status"] == "validated"  # built + validated, not active
    profile = rag_retrieval.get_profile(result["retrieval_profile_public_id"])
    assert profile["name"] == "MB-41 retrieval profile"


# -- profile (and index) are not active automatically ----------------------------------


def test_retrieval_profile_is_not_active_automatically(settings: Settings) -> None:
    rag_ingestion, rag_retrieval = _rag_services(settings)
    _register_embedding_model(rag_ingestion)
    space = rag_ingestion.create_space(KnowledgeSpaceCreate(name="MB-41 space 2", slug="mb41-space-2"), ADMIN_ID)
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(
        settings, gateway_service=gateway, rag_ingestion_service=rag_ingestion, rag_retrieval_service=rag_retrieval,
    )
    result = bridge.export_accepted_session(
        session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True,
        rag_knowledge_space_public_id=space["public_id"], build_rag_index=True,
    )

    profile = rag_retrieval.get_profile(result["retrieval_profile_public_id"])
    assert profile["status"] not in {"active"}
    vector_index = rag_ingestion.get_vector_index(result["vector_index_public_ids"][0])
    assert vector_index["status"] != "active"


def test_retrieval_fails_until_explicit_second_admin_approval(settings: Settings) -> None:
    from backend.models.rag import RetrievalFiltersPayload, RetrieveRequest

    rag_ingestion, rag_retrieval = _rag_services(settings)
    _register_embedding_model(rag_ingestion)
    space = rag_ingestion.create_space(KnowledgeSpaceCreate(name="MB-41 space 3", slug="mb41-space-3"), ADMIN_ID)
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(
        settings, gateway_service=gateway, rag_ingestion_service=rag_ingestion, rag_retrieval_service=rag_retrieval,
    )
    result = bridge.export_accepted_session(
        session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True,
        rag_knowledge_space_public_id=space["public_id"], build_rag_index=True,
    )
    profile_id = result["retrieval_profile_public_id"]

    with pytest.raises(ValidationError):
        rag_retrieval.retrieve(
            RetrieveRequest(retrieval_profile_public_id=profile_id, query=KNOWN_PHRASE, filters=RetrievalFiltersPayload()),
            ADMIN_ID,
        )

    # Second, explicit admin approval -- never performed by the bridge itself.
    rag_retrieval.validate_profile(profile_id, ADMIN_ID)
    rag_retrieval.activate_profile(profile_id, ADMIN_ID)
    rag_ingestion.activate_vector_index(result["vector_index_public_ids"][0], ADMIN_ID)

    retrieval = rag_retrieval.retrieve(
        RetrieveRequest(retrieval_profile_public_id=profile_id, query=KNOWN_PHRASE, filters=RetrievalFiltersPayload()),
        ADMIN_ID,
    )
    assert retrieval["results"]
    assert KNOWN_PHRASE in retrieval["results"][0]["normalized_text"]


# -- duplicate export does not rebuild the index ----------------------------------------


def test_duplicate_export_does_not_rebuild_the_index(settings: Settings) -> None:
    rag_ingestion, rag_retrieval = _rag_services(settings)
    _register_embedding_model(rag_ingestion)
    space = rag_ingestion.create_space(KnowledgeSpaceCreate(name="MB-41 space 4", slug="mb41-space-4"), ADMIN_ID)
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(
        settings, gateway_service=gateway, rag_ingestion_service=rag_ingestion, rag_retrieval_service=rag_retrieval,
    )

    first = bridge.export_accepted_session(
        session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True,
        rag_knowledge_space_public_id=space["public_id"], build_rag_index=True,
    )
    assert len(first["vector_index_public_ids"]) == 1

    second = bridge.export_accepted_session(
        session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True,
        rag_knowledge_space_public_id=space["public_id"], build_rag_index=True,
        target_source_public_id=first["dataset_source_public_id"],
    )
    # The second call is a full duplicate (same provider run already
    # exported) -- no new RAG source, no new pipeline objects.
    assert second["created_record_public_ids"] == []
    assert second["vector_index_public_ids"] == []
    assert second["retrieval_profile_public_id"] is None

    with database_connection(settings.resolved_database_path) as connection:
        count = connection.execute("SELECT COUNT(*) AS n FROM rag_vector_indexes").fetchone()["n"]
    assert count == 1  # still only the one real index from the first export


# -- failure rolls back / never exposes partial RAG objects -----------------------------


def test_missing_embedding_model_fails_before_any_rag_object_is_created(settings: Settings) -> None:
    # No embedding model registered at all -- "No new embedding
    # algorithm" means the bridge must refuse, not invent one.
    rag_ingestion, rag_retrieval = _rag_services(settings)
    space = rag_ingestion.create_space(KnowledgeSpaceCreate(name="MB-41 space 5", slug="mb41-space-5"), ADMIN_ID)
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(
        settings, gateway_service=gateway, rag_ingestion_service=rag_ingestion, rag_retrieval_service=rag_retrieval,
    )

    with pytest.raises(ValidationError):
        bridge.export_accepted_session(
            session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True,
            rag_knowledge_space_public_id=space["public_id"], build_rag_index=True,
        )

    with database_connection(settings.resolved_database_path) as connection:
        assert connection.execute("SELECT COUNT(*) AS n FROM rag_source_versions").fetchone()["n"] == 0
        assert connection.execute("SELECT COUNT(*) AS n FROM rag_vector_indexes").fetchone()["n"] == 0
        assert connection.execute("SELECT COUNT(*) AS n FROM rag_retrieval_profiles").fetchone()["n"] == 0

    events = _audit_events(settings, session["public_id"])
    assert "external_gateway_rag_build_started" in events
    assert "external_gateway_rag_build_failed" in events
    assert "external_gateway_rag_build_completed" not in events
    # The dataset export itself (records, source) genuinely succeeded and
    # must still show as completed -- only the RAG continuation failed.
    assert "external_gateway_dataset_export_completed" in events
    assert "external_gateway_dataset_export_failed" not in events


def test_failure_never_creates_a_retrieval_profile(settings: Settings) -> None:
    # A model exists (a real, schema-valid provider_type) but
    # `local_sentence_transformer` genuinely raises NotImplementedError
    # at real compute time -- Phase 16 never auto-downloads a local
    # model for it (see core_model.rag.embedding.compute_embedding).
    # This forces a real failure partway through the pipeline, after a
    # source version and chunk set already exist.
    rag_ingestion, rag_retrieval = _rag_services(settings)
    rag_ingestion.create_embedding_model(
        EmbeddingModelCreate(
            name="broken-model", version="1", provider_type="local_sentence_transformer",
            dimensions=64, maximum_input_tokens=2048, supported_languages=["en"],
        ),
        ADMIN_ID,
    )
    space = rag_ingestion.create_space(KnowledgeSpaceCreate(name="MB-41 space 6", slug="mb41-space-6"), ADMIN_ID)
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(
        settings, gateway_service=gateway, rag_ingestion_service=rag_ingestion, rag_retrieval_service=rag_retrieval,
    )

    with pytest.raises(ValidationError):
        bridge.export_accepted_session(
            session["public_id"], admin_id=ADMIN_ID, ingest_to_rag=True,
            rag_knowledge_space_public_id=space["public_id"], build_rag_index=True,
        )

    # A chunk set was created (chunking itself doesn't need the model);
    # embedding produced zero usable vectors, so `build_vector_index`
    # itself (unmodified) raises before ever reaching "active" -- its own
    # in-transaction status="failed" update is rolled back along with the
    # rest of that same transaction when the ValidationError propagates,
    # so the row is left at its pre-build "building" status; the actual
    # safety property that matters is verified below: never "active",
    # and no retrieval profile ever created, since that step only runs
    # after a successful vector index build.
    with database_connection(settings.resolved_database_path) as connection:
        index_statuses = [
            row["status"] for row in connection.execute("SELECT status FROM rag_vector_indexes").fetchall()
        ]
        assert all(status != "active" for status in index_statuses)
        assert connection.execute("SELECT COUNT(*) AS n FROM rag_retrieval_profiles").fetchone()["n"] == 0

    events = _audit_events(settings, session["public_id"])
    assert "external_gateway_rag_build_failed" in events


def test_build_rag_index_requires_ingest_to_rag(settings: Settings) -> None:
    rag_ingestion, rag_retrieval = _rag_services(settings)
    gateway, session = _accepted_session(settings)
    bridge = ExternalGatewayDatasetBridgeService(
        settings, gateway_service=gateway, rag_ingestion_service=rag_ingestion, rag_retrieval_service=rag_retrieval,
    )
    with pytest.raises(ValidationError):
        bridge.export_accepted_session(session["public_id"], admin_id=ADMIN_ID, build_rag_index=True)
