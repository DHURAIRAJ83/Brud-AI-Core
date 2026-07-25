"""Provenance evidence.

Filenames are never provenance. Every derived segment must resolve
back to its originating source through a chain of checksums and public
IDs -- never a filename lookup.
"""

from __future__ import annotations

import hashlib
from typing import Any


def content_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_provenance_record(
    *,
    source_public_id: str,
    original_creator: str | None,
    publisher: str | None,
    collection_method: str,
    ingestion_date: str,
    original_checksum: str,
    file_checksum: str,
    snapshot_checksum: str,
    derived_document_checksums: list[str],
    transformation_versions: dict[str, str],
    licence_evidence_reference: str | None,
    approval_evidence_reference: str | None,
) -> dict[str, Any]:
    return {
        "source_public_id": source_public_id,
        "original_creator": original_creator,
        "publisher": publisher,
        "collection_method": collection_method,
        "ingestion_date": ingestion_date,
        "original_checksum_sha256": original_checksum,
        "file_checksum_sha256": file_checksum,
        "snapshot_checksum_sha256": snapshot_checksum,
        "derived_document_checksums_sha256": derived_document_checksums,
        "transformation_versions": transformation_versions,
        "licence_evidence_reference": licence_evidence_reference,
        "approval_evidence_reference": approval_evidence_reference,
        "deletion_or_dispute_state": "none",
    }


def provenance_completeness(record: dict[str, Any]) -> tuple[bool, list[str]]:
    """Every field a training export must be able to point back to.
    Returns (complete, missing_fields) -- never a silent pass."""

    required = (
        "source_public_id", "collection_method", "ingestion_date",
        "original_checksum_sha256", "snapshot_checksum_sha256",
    )
    missing = [field for field in required if not record.get(field)]
    return not missing, missing


def mark_deleted_or_disputed(record: dict[str, Any], *, state: str, reason: str) -> dict[str, Any]:
    """Records a source-deletion/dispute state without discarding the
    checksums that already-derived segments still reference."""

    updated = dict(record)
    updated["deletion_or_dispute_state"] = state
    updated["deletion_or_dispute_reason"] = reason
    return updated
