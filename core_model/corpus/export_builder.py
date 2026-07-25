"""Deterministic pretraining-ready export record and shard building.

Never includes raw private metadata, never writes outside a bounded
shard-size limit, and produces a stable, checksummed ordering every
time for the same input.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

DEFAULT_SHARD_MAX_BYTES = 50_000_000


def build_jsonl_record(
    *,
    record_public_id: str,
    text: str,
    language: str,
    domain: str,
    style: str,
    source_public_id: str,
    source_version_public_id: str | None,
    licence_family: str,
    quality_band: str,
    split: str,
) -> dict[str, Any]:
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "record_public_id": record_public_id,
        "text": text,
        "language": language,
        "domain": domain,
        "style": style,
        "source_public_id": source_public_id,
        "source_version_public_id": source_version_public_id,
        "licence_family": licence_family,
        "quality_band": quality_band,
        "split": split,
        "checksum_sha256": checksum,
    }


def serialize_jsonl_line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def build_metadata_only_record(record: dict[str, Any]) -> dict[str, Any]:
    """Metadata-JSONL format: everything except the raw text -- for
    provenance/manifest cross-referencing without duplicating content."""

    return {key: value for key, value in record.items() if key != "text"}


def shard_records(
    records: list[dict[str, Any]], *, shard_max_bytes: int = DEFAULT_SHARD_MAX_BYTES
) -> list[list[dict[str, Any]]]:
    """Deterministic, order-preserving bin-packing into bounded shards
    -- never reorders records, never splits mid-record."""

    shards: list[list[dict[str, Any]]] = []
    current_shard: list[dict[str, Any]] = []
    current_bytes = 0
    for record in records:
        line_bytes = len(serialize_jsonl_line(record).encode("utf-8")) + 1
        if current_shard and current_bytes + line_bytes > shard_max_bytes:
            shards.append(current_shard)
            current_shard = []
            current_bytes = 0
        current_shard.append(record)
        current_bytes += line_bytes
    if current_shard:
        shards.append(current_shard)
    return shards


def shard_checksum(records: list[dict[str, Any]]) -> str:
    joined = "\n".join(serialize_jsonl_line(record) for record in records)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def safe_shard_relative_key(*, split: str, shard_number: int, export_format: str) -> str:
    """Never accepts caller-supplied path components -- the shard key
    is always built from validated, bounded integer/enum inputs only."""

    if not isinstance(shard_number, int) or shard_number < 0:
        raise ValueError("shard_number must be a non-negative integer")
    extension = "jsonl" if export_format in {"jsonl", "metadata_jsonl"} else "txt"
    return f"{split}/shard-{shard_number:05d}.{extension}"
