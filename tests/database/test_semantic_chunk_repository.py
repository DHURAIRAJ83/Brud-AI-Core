from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.documents import DocumentRepository
from backend.database.repositories.semantic_chunks import SemanticChunkRepository, public_row


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "chunks.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> SemanticChunkRepository:
    return SemanticChunkRepository(database_path)


def _make_source(database_path: Path) -> int:
    source_repo = DataSourceRepository(database_path)
    with source_repo.transaction() as connection:
        public_id = source_repo.create_source(
            connection,
            {
                "source_code": "SRC-CHUNK-TEST-0001",
                "title": "Test source",
                "source_type": "document_derived",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with source_repo.transaction() as connection:
        return source_repo.source(connection, public_id)["id"]


def _make_document(database_path: Path) -> int:
    doc_repo = DocumentRepository(database_path)
    with doc_repo.transaction() as connection:
        connection.execute(
            """INSERT INTO document_sources(
                public_id, original_filename, stored_filename, document_type, mime_type,
                file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
                created_by_admin_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "doc-chunk-test",
                "a.pdf",
                "a-stored.pdf",
                "pdf",
                "application/pdf",
                1024,
                "hashchunktest",
                1,
                "auto",
                "review_ready",
                "admin-1",
            ),
        )
        return connection.execute(
            "SELECT id FROM document_sources WHERE public_id=?", ("doc-chunk-test",)
        ).fetchone()["id"]


def test_create_read_update_chunk(repository: SemanticChunkRepository, database_path: Path) -> None:
    source_id = _make_source(database_path)
    document_id = _make_document(database_path)
    with repository.transaction() as connection:
        public_id = repository.create_chunk(
            connection,
            {
                "chunk_code": "CHK-0001",
                "document_source_id": document_id,
                "data_source_id": source_id,
                "chunk_type": "paragraph",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        row = public_row(repository.chunk(connection, public_id))
        assert row["chunk_code"] == "CHK-0001"
        assert row["status"] == "draft"
        assert "id" not in row
        assert "document_source_id" not in row
        repository.update_chunk(
            connection, repository.chunk(connection, public_id)["id"], {"status": "needs_review"}
        )
    with repository.transaction() as connection:
        row = public_row(repository.chunk(connection, public_id))
        assert row["status"] == "needs_review"


def test_create_and_list_revisions(
    repository: SemanticChunkRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    document_id = _make_document(database_path)
    with repository.transaction() as connection:
        chunk_public_id = repository.create_chunk(
            connection,
            {
                "chunk_code": "CHK-0002",
                "document_source_id": document_id,
                "data_source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
        chunk_id = repository.chunk(connection, chunk_public_id)["id"]
        repository.create_revision(
            connection,
            {
                "chunk_id": chunk_id,
                "revision_number": 1,
                "text": "hello",
                "normalized_text": "hello",
                "content_hash": "hash1",
                "page_number": 1,
                "start_locator_json": '{"page":1,"offset":0}',
                "end_locator_json": '{"page":1,"offset":5}',
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        chunk_id = repository.chunk(connection, chunk_public_id)["id"]
        revisions = repository.list_revisions(connection, chunk_id)
        assert len(revisions) == 1
        assert repository.latest_revision_number(connection, chunk_id) == 1


def test_relations_and_cycle_lookup(
    repository: SemanticChunkRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    document_id = _make_document(database_path)
    with repository.transaction() as connection:
        parent_public = repository.create_chunk(
            connection,
            {
                "chunk_code": "CHK-P",
                "document_source_id": document_id,
                "data_source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
        child_public = repository.create_chunk(
            connection,
            {
                "chunk_code": "CHK-C",
                "document_source_id": document_id,
                "data_source_id": source_id,
                "parent_chunk_id": repository.chunk(connection, parent_public)["id"],
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        parent_id = repository.chunk(connection, parent_public)["id"]
        child_id = repository.chunk(connection, child_public)["id"]
        assert repository.parent_id_of(connection, child_id) == parent_id
        repository.create_relation(
            connection,
            {
                "source_chunk_id": child_id,
                "target_chunk_id": parent_id,
                "relationship_type": "child_of",
                "created_by_admin_public_id": "admin-1",
            },
        )
        relations = repository.list_relations(connection, child_id)
        assert len(relations) == 1
        assert relations[0]["relationship_type"] == "child_of"


def test_events_and_reviews(repository: SemanticChunkRepository, database_path: Path) -> None:
    source_id = _make_source(database_path)
    document_id = _make_document(database_path)
    with repository.transaction() as connection:
        chunk_public_id = repository.create_chunk(
            connection,
            {
                "chunk_code": "CHK-EVT",
                "document_source_id": document_id,
                "data_source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
        chunk_id = repository.chunk(connection, chunk_public_id)["id"]
        repository.add_event(
            connection,
            {
                "chunk_id": chunk_id,
                "event_type": "chunk_created",
                "performed_by_admin_public_id": "admin-1",
            },
        )
        repository.create_review(
            connection,
            {
                "chunk_id": chunk_id,
                "action": "approve",
                "status_after": "approved",
                "performed_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        chunk_id = repository.chunk(connection, chunk_public_id)["id"]
        assert len(repository.list_events(connection, chunk_id)) == 1
        assert len(repository.list_reviews(connection, chunk_id)) == 1
