"""Phase 21A bridge: materializes one approved, exported Phase 20
corpus release into the *existing* Phase 6 dataset-version format
(`dataset_records`/`dataset_versions`/`dataset_version_items`) so that
Phase 7's `TokenizerService` and Phase 9's `PretrainingService` can
consume real corpus content completely unchanged -- no parallel
tokenizer-training or pretraining data path is introduced.

Never copies unapproved or mutable source data: the release must
already be `finalized` or `exported`, and only build members marked
`included=1` (i.e. already passed licence/quality/privacy/safety/
deduplication/contamination checks during the Phase 20 build) are
materialized.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError


def materialize_corpus_release(connection, release_row, *, name_prefix: str) -> dict[str, Any]:
    if release_row["status"] not in ("finalized", "exported"):
        raise ValidationError(
            "corpus release must be finalized or exported before it can be materialized"
        )
    version_row = connection.execute(
        "SELECT * FROM corpus_versions WHERE id=?", (release_row["corpus_version_id"],)
    ).fetchone()
    build_row = connection.execute(
        "SELECT * FROM corpus_builds WHERE id=?", (version_row["build_id"],)
    ).fetchone()
    members = connection.execute(
        """SELECT m.*, s.public_id AS segment_public_id, s.text AS segment_text,
        s.character_count FROM corpus_build_members m
        JOIN corpus_segments s ON s.id = m.segment_id
        WHERE m.build_id=? AND m.included=1 ORDER BY m.id""",
        (build_row["id"],),
    ).fetchall()
    if not members:
        raise ValidationError("corpus release has no included segments to materialize")

    source_public_id = str(uuid4())
    connection.execute(
        """INSERT INTO dataset_sources(public_id,name,language,source_type,licence_status,
        metadata_json) VALUES (?,?,?,?,?,?)""",
        (
            source_public_id,
            f"{name_prefix} (materialized from corpus release {release_row['public_id']})",
            "mixed",
            "manual",
            "approved",
            dumps_json({"corpus_release_public_id": release_row["public_id"]}),
        ),
    )
    source_id = connection.execute(
        "SELECT id FROM dataset_sources WHERE public_id=?", (source_public_id,)
    ).fetchone()["id"]

    record_ids_by_split: dict[str, list[int]] = {"train": [], "validation": [], "test": []}
    total_characters = 0
    for member in members:
        text = member["segment_text"]
        if not text or not text.strip():
            continue
        record_public_id = str(uuid4())
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        connection.execute(
            """INSERT INTO dataset_records(source_id,content,language,status,public_id,
            record_type,input_text,output_text,content_hash,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                source_id,
                text,
                "unknown",
                "approved",
                record_public_id,
                "pretrain",
                text,
                text,
                content_hash,
                dumps_json({"segment_public_id": member["segment_public_id"]}),
            ),
        )
        record_id = connection.execute(
            "SELECT id FROM dataset_records WHERE public_id=?", (record_public_id,)
        ).fetchone()["id"]
        split = member["split"] or "train"
        record_ids_by_split.setdefault(split, []).append(record_id)
        total_characters += len(text)

    total_records = sum(len(ids) for ids in record_ids_by_split.values())
    if not record_ids_by_split["train"]:
        raise ValidationError("materialized corpus release has no train-split records")

    dataset_version_public_id = str(uuid4())
    dataset_name = f"phase21a_{name_prefix.lower().replace(' ', '_')}"
    version_label = uuid4().hex[:12]
    checksum = hashlib.sha256(
        "|".join(
            str(record_id)
            for split in ("train", "validation", "test")
            for record_id in record_ids_by_split[split]
        ).encode("utf-8")
    ).hexdigest()
    connection.execute(
        """INSERT INTO dataset_versions(public_id,name,version,description,status,
        manifest_json,record_count,checksum_sha256,finalized_at)
        VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (
            dataset_version_public_id,
            dataset_name,
            version_label,
            f"Materialized from corpus release {release_row['public_id']} for Phase 21A",
            "ready",
            dumps_json(
                {
                    "corpus_release_public_id": release_row["public_id"],
                    "corpus_build_public_id": build_row["public_id"],
                }
            ),
            total_records,
            checksum,
        ),
    )
    dataset_version_id = connection.execute(
        "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_version_public_id,)
    ).fetchone()["id"]

    sequence = 0
    for split in ("train", "validation", "test"):
        for record_id in record_ids_by_split[split]:
            connection.execute(
                """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,
                split,sequence_number) VALUES (?,?,?,?)""",
                (dataset_version_id, record_id, split, sequence),
            )
            sequence += 1

    return {
        "dataset_version_id": dataset_version_id,
        "dataset_version_public_id": dataset_version_public_id,
        "train_record_count": len(record_ids_by_split["train"]),
        "validation_record_count": len(record_ids_by_split["validation"]),
        "test_record_count": len(record_ids_by_split["test"]),
        "total_records": total_records,
        "total_characters": total_characters,
        "build_row": build_row,
        "version_row": version_row,
    }
