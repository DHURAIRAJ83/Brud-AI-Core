"""Phase 61 - P1: Global Canonical Novelty Ledger Database Repository.

Provides persistent storage, querying, lineage lookup, content hash verification,
native vs synthetic token accounting tracking, and duplicate detection for the
Phase 61 Global Canonical Novelty Ledger (`global_novelty_ledger`).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Sequence
from uuid import uuid4

from backend.database.repositories.base import BaseRepository, NotFoundError


class GlobalNoveltyLedgerRepository(BaseRepository):
    """Database repository interface for `global_novelty_ledger` table."""

    def register_record(
        self,
        *,
        content_sha256: str,
        normalized_content_sha256: str,
        lineage_id: str,
        rights_status: str = "RIGHTS_PENDING",
        provenance_status: str = "UNVERIFIED",
        domain: str = "OTHER",
        language: str = "ta",
        native_or_synthetic: str = "NATIVE",
        tokenizer_version: str = "v2",
        token_count: int = 0,
        native_token_count: int = 0,
        synthetic_token_count: int = 0,
        translated_token_count: int = 0,
        derived_token_count: int = 0,
        source_id: str | None = None,
        source_url: str | None = None,
        source_type: str | None = None,
        book_id: str | None = None,
        page_id: str | None = None,
        record_id: str | None = None,
        dataset_id: str | None = None,
        parent_lineage_id: str | None = None,
        first_seen_dataset: str | None = None,
        canonical_status: str = "ACTIVE",
        novelty_status: str = "TRUE_GLOBAL_NEW",
    ) -> dict[str, Any]:
        """Register a new record into global_novelty_ledger."""
        record_public_id = f"gnl-{uuid4().hex[:12]}"
        query = """
            INSERT INTO global_novelty_ledger (
                record_public_id, source_id, source_url, source_type, book_id, page_id,
                record_id, dataset_id, content_sha256, normalized_content_sha256, lineage_id,
                parent_lineage_id, rights_status, provenance_status, domain, language,
                native_or_synthetic, tokenizer_version, token_count, native_token_count,
                synthetic_token_count, translated_token_count, derived_token_count,
                first_seen_dataset, canonical_status, novelty_status
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """
        with self.transaction() as conn:
            conn.execute(
                query,
                (
                    record_public_id, source_id, source_url, source_type, book_id, page_id,
                    record_id, dataset_id, content_sha256, normalized_content_sha256, lineage_id,
                    parent_lineage_id, rights_status, provenance_status, domain, language,
                    native_or_synthetic, tokenizer_version, token_count, native_token_count,
                    synthetic_token_count, translated_token_count, derived_token_count,
                    first_seen_dataset or dataset_id, canonical_status, novelty_status
                )
            )
        return self.get_by_public_id(record_public_id)

    def find_by_content_hash(self, content_sha256: str) -> dict[str, Any] | None:
        """Find record by exact content SHA-256 hash."""
        query = "SELECT * FROM global_novelty_ledger WHERE content_sha256 = ? LIMIT 1"
        with self.connection() as conn:
            cursor = conn.execute(query, (content_sha256,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_normalized_hash(self, normalized_content_sha256: str) -> dict[str, Any] | None:
        """Find record by normalized content SHA-256 hash."""
        query = "SELECT * FROM global_novelty_ledger WHERE normalized_content_sha256 = ? LIMIT 1"
        with self.connection() as conn:
            cursor = conn.execute(query, (normalized_content_sha256,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_public_id(self, record_public_id: str) -> dict[str, Any]:
        """Fetch record by public ID or raise NotFoundError."""
        query = "SELECT * FROM global_novelty_ledger WHERE record_public_id = ?"
        with self.connection() as conn:
            cursor = conn.execute(query, (record_public_id,))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"GlobalNoveltyLedger record {record_public_id} not found")
            return dict(row)

    def get_summary_statistics(self) -> dict[str, Any]:
        """Compute aggregate global corpus statistics."""
        query = """
            SELECT
                COUNT(*) as total_records,
                COALESCE(SUM(token_count), 0) as total_tokens,
                COALESCE(SUM(native_token_count), 0) as total_native_tokens,
                COALESCE(SUM(synthetic_token_count), 0) as total_synthetic_tokens,
                COALESCE(SUM(translated_token_count), 0) as total_translated_tokens,
                COALESCE(SUM(derived_token_count), 0) as total_derived_tokens,
                COUNT(DISTINCT lineage_id) as total_lineages,
                COUNT(DISTINCT book_id) as total_books
            FROM global_novelty_ledger
        """
        with self.connection() as conn:
            cursor = conn.execute(query)
            row = cursor.fetchone()
            return dict(row) if row else {
                "total_records": 0, "total_tokens": 0, "total_native_tokens": 0,
                "total_synthetic_tokens": 0, "total_translated_tokens": 0,
                "total_derived_tokens": 0, "total_lineages": 0, "total_books": 0
            }
