from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import ConflictError
from backend.database.repositories.documents import DocumentRepository, decode


@pytest.fixture
def repository(tmp_path: Path) -> DocumentRepository:
    database_path = tmp_path / "documents.db"
    initialize_database(database_path)
    return DocumentRepository(database_path)


def _make_document_and_page(repository: DocumentRepository) -> tuple[int, int]:
    with repository.transaction() as connection:
        connection.execute(
            """INSERT INTO document_sources(
                public_id, original_filename, stored_filename, document_type, mime_type,
                file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
                created_by_admin_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "doc-repo-1",
                "test.pdf",
                "test-stored.pdf",
                "pdf",
                "application/pdf",
                2048,
                "hash-repo-1",
                1,
                "auto",
                "ready",
                "admin-1",
            ),
        )
        document_id = connection.execute(
            "SELECT id FROM document_sources WHERE public_id=?", ("doc-repo-1",)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO document_pages(public_id, document_source_id, page_number) VALUES (?,?,?)",
            ("page-repo-1", document_id, 1),
        )
        page_id = connection.execute(
            "SELECT id FROM document_pages WHERE public_id=?", ("page-repo-1",)
        ).fetchone()[0]
        return document_id, page_id


def test_create_and_list_extractions(repository: DocumentRepository) -> None:
    _, page_id = _make_document_and_page(repository)
    with repository.transaction() as connection:
        repository.create_extraction(
            connection,
            {
                "document_page_id": page_id,
                "extraction_method": "embedded",
                "raw_text": "hello world",
                "created_by_admin_public_id": "admin-1",
            },
        )
        repository.create_extraction(
            connection,
            {
                "document_page_id": page_id,
                "extraction_method": "ocr",
                "raw_text": "hello world (ocr)",
                "ocr_engine": "tesseract",
                "ocr_confidence": 0.82,
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        rows = [
            decode(r, {"preprocessing_metadata_json", "extraction_warnings_json"})
            for r in repository.list_extractions(connection, page_id)
        ]
    assert len(rows) == 2
    assert rows[0]["extraction_method"] == "ocr"
    assert rows[0]["ocr_confidence"] == 0.82
    assert rows[1]["extraction_method"] == "embedded"
    assert "document_page_id" not in rows[0]


def test_extractions_are_append_only(repository: DocumentRepository) -> None:
    _, page_id = _make_document_and_page(repository)
    with repository.transaction() as connection:
        public_id = repository.create_extraction(
            connection,
            {
                "document_page_id": page_id,
                "extraction_method": "embedded",
                "raw_text": "original",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with pytest.raises(ConflictError):
        with repository.transaction() as connection:
            connection.execute(
                "UPDATE document_page_extractions SET raw_text='changed' WHERE public_id=?",
                (public_id,),
            )


def test_page_review_update_and_event_history(repository: DocumentRepository) -> None:
    _, page_id = _make_document_and_page(repository)
    with repository.transaction() as connection:
        repository.update_page_review(
            connection,
            page_id,
            {"review_status": "approved", "reviewed_by_admin_public_id": "admin-2"},
        )
        repository.add_review_event(
            connection,
            {
                "document_page_id": page_id,
                "action": "approve",
                "review_status_after": "approved",
                "performed_by_admin_public_id": "admin-2",
            },
        )
    with repository.transaction() as connection:
        page = connection.execute(
            "SELECT review_status, reviewed_by_admin_public_id FROM document_pages WHERE id=?",
            (page_id,),
        ).fetchone()
        events = [decode(r, set()) for r in repository.list_review_events(connection, page_id)]
    assert page["review_status"] == "approved"
    assert page["reviewed_by_admin_public_id"] == "admin-2"
    assert len(events) == 1
    assert events[0]["action"] == "approve"


def test_repeated_elements_create_list_filter_and_update(repository: DocumentRepository) -> None:
    document_id, _ = _make_document_and_page(repository)
    with repository.transaction() as connection:
        public_id = repository.create_repeated_element(
            connection,
            {
                "document_source_id": document_id,
                "normalized_text": "confidential draft",
                "element_type": "header",
                "page_occurrences_json": "[1,2,3]",
                "confidence": 0.9,
            },
        )
    with repository.transaction() as connection:
        items = [
            decode(r, {"page_occurrences_json"})
            for r in repository.list_repeated_elements(connection, document_id)
        ]
        assert len(items) == 1
        assert items[0]["status"] == "suggested"

        element = repository.repeated_element(connection, public_id)
        repository.update_repeated_element(
            connection,
            element["id"],
            {"status": "accepted", "reviewed_by_admin_public_id": "admin-3"},
        )
    with repository.transaction() as connection:
        accepted = [
            decode(r, {"page_occurrences_json"})
            for r in repository.list_repeated_elements(connection, document_id, status="accepted")
        ]
        assert len(accepted) == 1
        suggested = repository.list_repeated_elements(connection, document_id, status="suggested")
        assert suggested == []


def test_clear_repeated_elements_only_removes_suggested(repository: DocumentRepository) -> None:
    document_id, _ = _make_document_and_page(repository)
    with repository.transaction() as connection:
        repository.create_repeated_element(
            connection,
            {
                "document_source_id": document_id,
                "normalized_text": "still suggested",
                "element_type": "footer",
                "confidence": 0.5,
            },
        )
        accepted_id = repository.create_repeated_element(
            connection,
            {
                "document_source_id": document_id,
                "normalized_text": "already accepted",
                "element_type": "header",
                "confidence": 0.9,
            },
        )
        element = repository.repeated_element(connection, accepted_id)
        repository.update_repeated_element(connection, element["id"], {"status": "accepted"})
    with repository.transaction() as connection:
        repository.clear_repeated_elements(connection, document_id)
    with repository.transaction() as connection:
        remaining = repository.list_repeated_elements(connection, document_id)
    assert len(remaining) == 1
    assert remaining[0]["normalized_text"] == "already accepted"
