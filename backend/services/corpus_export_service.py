"""Phase 19 corpus export, manifest generation, and version comparison.

Exports only ever read from a finalized ``corpus_versions`` row's
already-included build members -- never from raw segments directly --
so an export can never bypass the licence/quality/privacy/safety/
deduplication/contamination pipeline that produced that version.
Finalizing an export never starts model training; that remains a
separate, explicitly-triggered, out-of-scope action.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import CorpusCompareRequest, ExportCreate
from core_model.corpus import EXPORT_NOT_TRAINING_TRIGGER_NOTICE
from core_model.corpus.comparison import compare_versions
from core_model.corpus.export_builder import (
    build_jsonl_record,
    safe_shard_relative_key,
    serialize_jsonl_line,
    shard_checksum,
    shard_records,
)
from core_model.corpus.manifest import (
    REQUIRED_CORPUS_MANIFEST_FIELDS,
    manifest_checksum,
    missing_required_fields,
    scan_for_sensitive_content,
)


class CorpusExportService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- exports -----------------------------------------------------

    def create_export(
        self, version_public_id: str, payload: ExportCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version_row = self.repository.version(connection, version_public_id)
            if version_row["status"] != "ready":
                raise ValidationError("corpus version must be ready before it can be exported")
            build_row = connection.execute(
                "SELECT * FROM corpus_builds WHERE id=?", (version_row["build_id"],)
            ).fetchone()

            values = {
                "corpus_version_id": version_row["id"],
                "export_format": payload.export_format,
                "shard_max_bytes": payload.shard_max_bytes,
                "created_by_admin_public_id": admin_id,
            }
            export_public_id = self.repository.create_export(connection, values)
            export_row = self.repository.export(connection, export_public_id)
            self.repository.update_export(connection, export_row["id"], {"status": "running"})

            members = [
                dict(member)
                for member in self.repository.members_for_build(connection, build_row["id"])
                if member["included"]
            ]

            export_dir = self.settings.resolved_corpus_export_dir / export_public_id
            export_dir.mkdir(parents=True, exist_ok=True)

            total_shards, total_records, total_bytes = 0, 0, 0
            for split in ("train", "validation", "test"):
                split_members = [m for m in members if m["split"] == split]
                if not split_members:
                    continue
                records = []
                for member in split_members:
                    segment_row = connection.execute(
                        "SELECT public_id, text FROM corpus_segments WHERE id=?",
                        (member["segment_id"],),
                    ).fetchone()
                    language_row = connection.execute(
                        "SELECT language_category FROM corpus_language_assessments "
                        "WHERE segment_id=? ORDER BY id DESC LIMIT 1",
                        (member["segment_id"],),
                    ).fetchone()
                    domain_row = connection.execute(
                        "SELECT primary_domain FROM corpus_domain_assessments "
                        "WHERE segment_id=? ORDER BY id DESC LIMIT 1",
                        (member["segment_id"],),
                    ).fetchone()
                    style_row = connection.execute(
                        "SELECT style FROM corpus_style_assessments "
                        "WHERE segment_id=? ORDER BY id DESC LIMIT 1",
                        (member["segment_id"],),
                    ).fetchone()
                    collection_row = connection.execute(
                        "SELECT public_id FROM corpus_collections WHERE id=?",
                        (member["collection_id"],),
                    ).fetchone()
                    records.append(
                        build_jsonl_record(
                            record_public_id=segment_row["public_id"],
                            text=segment_row["text"],
                            language=language_row["language_category"]
                            if language_row
                            else "unknown",
                            domain=domain_row["primary_domain"] if domain_row else "general",
                            style=style_row["style"] if style_row else "formal",
                            source_public_id=collection_row["public_id"] if collection_row else "",
                            source_version_public_id=version_public_id,
                            licence_family=member["final_licence_decision"],
                            quality_band=member["final_quality_band"],
                            split=split,
                        )
                    )

                for shard_number, shard in enumerate(
                    shard_records(records, shard_max_bytes=payload.shard_max_bytes)
                ):
                    relative_key = safe_shard_relative_key(
                        split=split, shard_number=shard_number, export_format=payload.export_format
                    )
                    shard_path = export_dir / relative_key
                    shard_path.parent.mkdir(parents=True, exist_ok=True)
                    body = "\n".join(serialize_jsonl_line(record) for record in shard)
                    shard_path.write_text(body, encoding="utf-8")

                    checksum = shard_checksum(shard)
                    total_characters = sum(len(record["text"]) for record in shard)
                    self.repository.create_export_shard(
                        connection,
                        {
                            "export_id": export_row["id"],
                            "split": split,
                            "shard_number": shard_number,
                            "record_count": len(shard),
                            "total_characters": total_characters,
                            "estimated_tokens": total_characters // 4,
                            "relative_storage_key": relative_key,
                            "file_size_bytes": len(body.encode("utf-8")),
                            "checksum_sha256": checksum,
                        },
                    )
                    total_shards += 1
                    total_records += len(shard)
                    total_bytes += len(body.encode("utf-8"))

            self.repository.update_export(
                connection,
                export_row["id"],
                {
                    "status": "completed",
                    "relative_storage_directory": export_public_id,
                    "total_shards": total_shards,
                    "total_records": total_records,
                    "total_bytes": total_bytes,
                },
            )
            self._audit(
                connection,
                "corpus_export_completed",
                admin_id,
                export_public_id,
                total_shards=total_shards,
                total_records=total_records,
            )
            result = self._export_detail(connection, export_public_id)
            result["notice"] = EXPORT_NOT_TRAINING_TRIGGER_NOTICE
            return result

    def _export_detail(self, connection, public_id: str) -> dict[str, Any]:
        row = self.repository.export(connection, public_id)
        result = public_row(row)
        result["shards"] = [
            public_row(shard) for shard in self.repository.shards_for_export(connection, row["id"])
        ]
        return result

    def get_export(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self._export_detail(connection, public_id)

    # --- manifests -----------------------------------------------------

    def generate_manifest(self, version_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version_row = self.repository.version(connection, version_public_id)
            build_row = connection.execute(
                "SELECT * FROM corpus_builds WHERE id=?", (version_row["build_id"],)
            ).fetchone()
            export_row = connection.execute(
                """SELECT * FROM corpus_exports WHERE corpus_version_id=?
                ORDER BY id DESC LIMIT 1""",
                (version_row["id"],),
            ).fetchone()
            shard_checksums = []
            if export_row is not None:
                shard_checksums = [
                    shard["checksum_sha256"]
                    for shard in self.repository.shards_for_export(connection, export_row["id"])
                ]

            manifest = {
                "corpus_policy_checksum": str(build_row["corpus_policy_id"]),
                "source_registry_public_ids": loads_json(
                    build_row["collection_ids_json"], default=[]
                ),
                "source_licence_decisions": loads_json(version_row["licence_distribution_json"]),
                "source_snapshot_checksums": [],
                "extraction_configuration": {},
                "normalization_configuration": {},
                "ocr_cleanup_configuration": {"version": "v1"},
                "segmentation_configuration": {},
                "privacy_detector_version": "v1",
                "safety_detector_version": "v1",
                "quality_thresholds": {
                    "minimum_segment_characters": self.settings.corpus_min_segment_characters,
                },
                "deduplication_configuration": {
                    "near_duplicate_threshold": self.settings.corpus_near_duplicate_threshold,
                },
                "contamination_configuration": {},
                "collection_checksums": {},
                "balance_policy_checksum": str(build_row["balance_policy_id"]),
                "partition_configuration": loads_json(build_row["partition_configuration_json"]),
                "segment_counts": {
                    "train": version_row["train_segment_count"],
                    "validation": version_row["validation_segment_count"],
                    "test": version_row["test_segment_count"],
                },
                "language_distribution": loads_json(version_row["language_distribution_json"]),
                "domain_distribution": loads_json(version_row["domain_distribution_json"]),
                "style_distribution": loads_json(version_row["style_distribution_json"]),
                "licence_distribution": loads_json(version_row["licence_distribution_json"]),
                "excluded_item_counts": {
                    "excluded_segment_count": build_row["excluded_segment_count"],
                },
                "corpus_version": version_row["semantic_version"],
                "export_shard_checksums": shard_checksums,
                "known_limitations": [
                    "Quality dimensions marked heuristic are not measured facts.",
                    EXPORT_NOT_TRAINING_TRIGGER_NOTICE,
                ],
                "software_versions": {"corpus_builder": "phase19-v1"},
                "created_at": version_row["created_at"],
            }
            missing = missing_required_fields(manifest)
            if missing:
                raise ValidationError(f"manifest is missing required fields: {missing}")
            sensitive = scan_for_sensitive_content(manifest)
            if sensitive:
                raise ValidationError(
                    f"manifest scan found disallowed sensitive content: {sensitive}"
                )

            checksum = manifest_checksum(manifest)
            manifest_public_id = self.repository.create_manifest(
                connection,
                {
                    "corpus_version_id": version_row["id"],
                    "manifest_json": dumps_json(manifest),
                    "manifest_checksum_sha256": checksum,
                },
            )
            self.repository.update_version(
                connection, version_row["id"], {"manifest_checksum_sha256": checksum}
            )
            self._audit(connection, "corpus_manifest_generated", admin_id, manifest_public_id)
            return {
                "manifest_public_id": manifest_public_id,
                "manifest": manifest,
                "manifest_checksum_sha256": checksum,
                "required_fields": list(REQUIRED_CORPUS_MANIFEST_FIELDS),
            }

    def get_manifest(self, version_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version_row = self.repository.version(connection, version_public_id)
            manifest_row = self.repository.latest_manifest_for_version(
                connection, version_row["id"]
            )
            if manifest_row is None:
                raise ValidationError("no manifest has been generated for this corpus version")
            return {
                "manifest": loads_json(manifest_row["manifest_json"]),
                "manifest_checksum_sha256": manifest_row["manifest_checksum_sha256"],
            }

    # --- comparisons -----------------------------------------------------

    def compare(self, payload: CorpusCompareRequest, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            left_row = self.repository.version(connection, payload.left_version_public_id)
            right_row = self.repository.version(connection, payload.right_version_public_id)

            left_build = connection.execute(
                "SELECT * FROM corpus_builds WHERE id=?", (left_row["build_id"],)
            ).fetchone()
            right_build = connection.execute(
                "SELECT * FROM corpus_builds WHERE id=?", (right_row["build_id"],)
            ).fetchone()

            def _summary(version_row, build_row) -> dict[str, Any]:
                return {
                    "total_records": (
                        version_row["train_segment_count"]
                        + version_row["validation_segment_count"]
                        + version_row["test_segment_count"]
                    ),
                    "estimated_tokens": version_row["estimated_tokens"],
                    "language_distribution": loads_json(version_row["language_distribution_json"]),
                    "domain_distribution": loads_json(version_row["domain_distribution_json"]),
                    "style_distribution": loads_json(version_row["style_distribution_json"]),
                    "licence_distribution": loads_json(version_row["licence_distribution_json"]),
                    "balance_policy_checksum": str(build_row["balance_policy_id"]),
                    "partition_configuration_checksum": str(
                        build_row["partition_configuration_json"]
                    ),
                    "corpus_policy_public_id": str(build_row["corpus_policy_id"]),
                    "collection_ids": loads_json(build_row["collection_ids_json"], default=[]),
                }

            comparison = compare_versions(
                left=_summary(left_row, left_build), right=_summary(right_row, right_build)
            )
            comparison_public_id = self.repository.create_comparison(
                connection,
                {
                    "left_version_id": left_row["id"],
                    "right_version_id": right_row["id"],
                    "compatibility": comparison["compatibility"],
                    "comparison_json": dumps_json(comparison),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection,
                "corpus_versions_compared",
                admin_id,
                comparison_public_id,
                compatibility=comparison["compatibility"],
            )
            return public_row(self.repository.comparison(connection, comparison_public_id))

    def get_comparison(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.comparison(connection, public_id))

    # --- audit -----------------------------------------------------

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event,
                "admin",
                "{}",
                str(uuid4()),
                event,
                "admin",
                admin_id,
                "corpus",
                resource_id,
                "success",
                dumps_json(metadata),
            ),
        )
