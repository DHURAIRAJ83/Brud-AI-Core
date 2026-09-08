"""Phase 61 - P2: Autonomous Tamil Book Acquisition Database Repository.

Provides persistent SQLite storage for:
- Source Registry (`book_acquisition_sources`)
- Book Acquisition Registry (`book_acquisition_registry`)
- Admin Review Queue (`admin_review_queue`)
"""

from __future__ import annotations

import sqlite3
from typing import Any, Sequence
from uuid import uuid4

from backend.database.repositories.base import BaseRepository, NotFoundError


class BookAcquisitionRepository(BaseRepository):
    """Database repository interface for Phase 61 P2 Acquisition tables."""

    # --- SOURCE REGISTRY METHODS ---

    def register_source(
        self,
        *,
        source_name: str,
        base_url: str,
        source_id: str | None = None,
        source_type: str = "DIGITAL_LIBRARY",
        language: str = "ta",
        publisher: str | None = None,
        rights_policy_url: str | None = None,
        licence_type: str = "PUBLIC_DOMAIN",
        training_permission: str = "PERMITTED",  # PERMITTED | UNKNOWN | RESTRICTED
        robots_status: str = "ALLOWED",
        terms_status: str = "VERIFIED",
        discovery_method: str = "CONFIGURED",
        trust_level: str = "HIGH",
        active: bool = True,
    ) -> dict[str, Any]:
        """Register a new digital library source into book_acquisition_sources."""
        final_source_id = source_id or f"src-{uuid4().hex[:8]}"
        query = """
            INSERT INTO book_acquisition_sources (
                source_id, source_name, base_url, source_type, language, publisher,
                rights_policy_url, licence_type, training_permission, robots_status,
                terms_status, discovery_method, trust_level, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.transaction() as conn:
            conn.execute(
                query,
                (
                    final_source_id, source_name, base_url, source_type, language, publisher,
                    rights_policy_url, licence_type, training_permission, robots_status,
                    terms_status, discovery_method, trust_level, 1 if active else 0
                )
            )
        return self.get_source_by_id(final_source_id)

    def get_source_by_id(self, source_id: str) -> dict[str, Any]:
        query = "SELECT * FROM book_acquisition_sources WHERE source_id = ?"
        with self.connection() as conn:
            cursor = conn.execute(query, (source_id,))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Book acquisition source {source_id} not found")
            return dict(row)

    def list_active_sources(self) -> list[dict[str, Any]]:
        query = "SELECT * FROM book_acquisition_sources WHERE active = 1 ORDER BY source_name ASC"
        with self.connection() as conn:
            cursor = conn.execute(query)
            return [dict(r) for r in cursor.fetchall()]

    # --- BOOK ACQUISITION REGISTRY METHODS ---

    def register_book(
        self,
        *,
        source_id: str,
        title: str,
        source_url: str,
        download_url: str,
        author: str = "Unknown",
        year: str | None = None,
        language: str = "ta",
        domain: str = "LITERATURE",
        rights_url: str | None = None,
        metadata_url: str | None = None,
        file_format: str = "pdf",
        download_status: str = "DISCOVERED",
        rights_status: str = "LICENSE_UNKNOWN",
        rights_evidence_text: str | None = None,
        confidence_score: float = 1.0,
        discovery_reason: str | None = None,
        book_id: str | None = None,
    ) -> dict[str, Any]:
        """Register a discovered book into book_acquisition_registry."""
        final_book_id = book_id or f"book-{uuid4().hex[:10]}"
        query = """
            INSERT INTO book_acquisition_registry (
                book_id, source_id, title, author, year, language, domain, source_url,
                rights_url, download_url, metadata_url, file_format, download_status,
                rights_status, rights_evidence_text, confidence_score, discovery_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.transaction() as conn:
            conn.execute(
                query,
                (
                    final_book_id, source_id, title, author, year, language, domain, source_url,
                    rights_url, download_url, metadata_url, file_format, download_status,
                    rights_status, rights_evidence_text, confidence_score, discovery_reason
                )
            )
        return self.get_book_by_id(final_book_id)

    def get_book_by_id(self, book_id: str) -> dict[str, Any]:
        query = "SELECT * FROM book_acquisition_registry WHERE book_id = ?"
        with self.connection() as conn:
            cursor = conn.execute(query, (book_id,))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Book acquisition record {book_id} not found")
            return dict(row)

    def update_book_acquisition_status(
        self,
        book_id: str,
        *,
        download_status: str,
        checksum_sha256: str | None = None,
        local_artifact_path: str | None = None,
        rights_status: str | None = None,
        rights_evidence_text: str | None = None,
    ) -> dict[str, Any]:
        """Update book status, checksum, local path, and rights status."""
        query = """
            UPDATE book_acquisition_registry
            SET download_status = ?,
                checksum_sha256 = COALESCE(?, checksum_sha256),
                local_artifact_path = COALESCE(?, local_artifact_path),
                rights_status = COALESCE(?, rights_status),
                rights_evidence_text = COALESCE(?, rights_evidence_text),
                updated_at = CURRENT_TIMESTAMP
            WHERE book_id = ?
        """
        with self.transaction() as conn:
            conn.execute(query, (download_status, checksum_sha256, local_artifact_path, rights_status, rights_evidence_text, book_id))
        return self.get_book_by_id(book_id)

    # --- ADMIN REVIEW QUEUE METHODS ---

    def create_admin_review_item(
        self,
        *,
        book_id: str,
        rights_status: str,
        quality_status: str,
        provenance_status: str,
        novelty_status: str,
        token_accounting_status: str,
        dataset_version_id: str | None = None,
        admin_notes: str | None = None,
    ) -> dict[str, Any]:
        """Create a new item in the Admin Review Queue."""
        review_id = f"rev-{uuid4().hex[:10]}"
        query = """
            INSERT INTO admin_review_queue (
                review_id, book_id, dataset_version_id, rights_status, quality_status,
                provenance_status, novelty_status, token_accounting_status, admin_decision, admin_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_REVIEW', ?)
        """
        with self.transaction() as conn:
            conn.execute(
                query,
                (
                    review_id, book_id, dataset_version_id, rights_status, quality_status,
                    provenance_status, novelty_status, token_accounting_status, admin_notes
                )
            )
        return self.get_review_by_id(review_id)

    def get_review_by_id(self, review_id: str) -> dict[str, Any]:
        query = "SELECT * FROM admin_review_queue WHERE review_id = ?"
        with self.connection() as conn:
            cursor = conn.execute(query, (review_id,))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Admin review queue item {review_id} not found")
            return dict(row)

    def update_admin_decision(
        self,
        review_id: str,
        *,
        admin_decision: str,  # APPROVED | REJECTED | QUARANTINED
        reviewed_by: str,
        admin_notes: str | None = None,
    ) -> dict[str, Any]:
        """Record explicit Admin approval decision."""
        query = """
            UPDATE admin_review_queue
            SET admin_decision = ?,
                reviewed_by = ?,
                admin_notes = COALESCE(?, admin_notes),
                reviewed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE review_id = ?
        """
        with self.transaction() as conn:
            conn.execute(query, (admin_decision, reviewed_by, admin_notes, review_id))
        return self.get_review_by_id(review_id)
