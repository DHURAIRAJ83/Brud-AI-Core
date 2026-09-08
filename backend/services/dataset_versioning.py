"""Dataset version build, split, manifest, checksum, and export services."""

from __future__ import annotations

import hashlib
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json, redact_secrets
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.dataset_quality import DatasetQualityRepository, _public
from backend.models.dataset_versions import BuildCreate, BuildRunRequest, DatasetVersionCreate


def _audit(connection, event: str, admin_id: str, resource_id: str, **metadata) -> None:
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
            "dataset_version",
            resource_id,
            "success",
            dumps_json(redact_secrets(metadata)),
        ),
    )


# Phase 2.7I, Finding B: bumped only when `_checksum_payload_v*()`'s own
# byte representation changes in a way that would change the checksum
# for identical input records -- never for a pure refactor. A dataset
# version's own manifest records which version produced its checksum
# (`checksum_payload_version`), so `verify_version()` can always
# recompute a pre-existing version's checksum the exact way it was
# originally computed, never the current default.
CHECKSUM_PAYLOAD_VERSION = 2


def _safe_name(name: str, version: str) -> str:
    raw = f"{name}_{version}".lower()
    safe = re.sub(r"[^a-z0-9._-]+", "_", raw).strip("._")
    return safe or f"dataset_{uuid4().hex[:8]}"


class DatasetVersioningService:
    def __init__(self, repository: DatasetQualityRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def create_version(self, payload: DatasetVersionCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            parent_id = None
            if payload.parent_dataset_version_public_id:
                parent_id = self.repository.version(
                    connection, payload.parent_dataset_version_public_id
                )["id"]
            public_id = self.repository.create_version(
                connection,
                public_id=str(uuid4()),
                name=payload.name,
                version=payload.version,
                description=payload.description,
                parent_id=parent_id,
            )
            _audit(connection, "dataset_version_created", admin_id, public_id)
            return _public(self.repository.version(connection, public_id))

    def list_versions(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            items, total = self.repository.list_versions(connection, page, page_size)
        return self._page(items, total, page, page_size)

    def get_version(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return _public(self.repository.version(connection, public_id))

    def patch_version(self, public_id: str, patch: dict[str, Any], admin_id: str) -> dict[str, Any]:
        allowed = {key: value for key, value in patch.items() if key in {"name", "description"}}
        with self.repository.transaction() as connection:
            row = self.repository.version(connection, public_id)
            self.repository.require_draft_version(row)
            if allowed:
                assignments = ",".join(f"{key}=?" for key in allowed)
                connection.execute(
                    f"UPDATE dataset_versions SET {assignments} WHERE public_id=?",
                    (*allowed.values(), public_id),
                )
            _audit(
                connection, "dataset_version_updated", admin_id, public_id, fields=sorted(allowed)
            )
            return _public(self.repository.version(connection, public_id))

    def archive_version(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.version(connection, public_id)
            if row["status"] != "ready":
                raise ValidationError("only ready dataset versions can be archived")
            connection.execute(
                "UPDATE dataset_versions SET status='archived' WHERE public_id=?", (public_id,)
            )
            _audit(connection, "dataset_version_archived", admin_id, public_id)
            return _public(self.repository.version(connection, public_id))

    def create_build(self, payload: BuildCreate, admin_id: str) -> dict[str, Any]:
        split = self._split_config(
            payload.split_configuration.model_dump() if payload.split_configuration else {}
        )
        filters = {
            **payload.selection_filters,
            "minimum_quality_score": payload.minimum_quality_score,
            "require_ready_quality": payload.require_ready_quality,
        }
        with self.repository.transaction() as connection:
            version_id = self.repository.create_version(
                connection,
                public_id=str(uuid4()),
                name=payload.dataset_name,
                version=payload.dataset_version,
                description=payload.description,
            )
            version = self.repository.version(connection, version_id)
            build_id = self.repository.create_build(
                connection,
                public_id=str(uuid4()),
                version_id=version["id"],
                name=f"{payload.dataset_name} {payload.dataset_version}",
                filters=filters,
                split=split,
                created_by=admin_id,
            )
            _audit(connection, "dataset_build_created", admin_id, build_id, filters=filters)
            return _public(self.repository.build(connection, build_id))

    def list_builds(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            items, total = self.repository.list_builds(connection, page, page_size)
        return self._page(items, total, page, page_size)

    def get_build(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return _public(self.repository.build(connection, public_id))

    def validate_build(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            build = self.repository.build(connection, public_id)
            filters = loads_json(build["selection_filters_json"])
            split = loads_json(build["split_configuration_json"])
            records, excluded = self._select_records(connection, filters)
            groups = self._groups(records)
            splits = self._split_groups(groups, split)
            leakage = self._leakage(splits)
            preview = self._preview(records, excluded, splits, leakage)
            self.repository.add_build_event(
                connection,
                public_id,
                "validation_completed",
                build["status"],
                build["status"],
                None,
                {"selected_records": len(records), "leakage": leakage["status"]},
            )
            _audit(
                connection,
                "dataset_build_validated",
                admin_id,
                public_id,
                selected_records=len(records),
                leakage_status=leakage["status"],
            )
        return preview

    def run_build(self, public_id: str, payload: BuildRunRequest, admin_id: str) -> dict[str, Any]:
        if not payload.confirm:
            raise ValidationError("build confirmation is required")
        with self.repository.transaction() as connection:
            build = self.repository.build(connection, public_id)
            if build["status"] in {"completed", "completed_with_warnings"}:
                return _public(build)
            if build["status"] not in {"draft", "validating", "failed"}:
                raise ValidationError("build is not runnable in its current status")
            version = self.repository.version(connection, build["dataset_version_public_id"])
            self.repository.require_draft_version(version)
            filters = loads_json(build["selection_filters_json"])
            split = loads_json(build["split_configuration_json"])
            records, excluded = self._select_records(connection, filters)
            if not records:
                raise ValidationError("dataset build requires at least one approved record")
            groups = self._groups(records)
            splits = self._split_groups(groups, split)
            leakage = self._leakage(splits)
            if leakage["status"] == "blocked":
                raise ValidationError("blocked leakage prevents dataset finalization")
            if leakage["status"] == "warning" and not payload.allow_warnings:
                raise ValidationError("leakage warnings require explicit confirmation")
            connection.execute(
                "UPDATE dataset_versions SET status='building' WHERE id=?", (version["id"],)
            )
            connection.execute(
                "DELETE FROM dataset_version_items WHERE dataset_version_id=?", (version["id"],)
            )
            sequence = 0
            for split_name in ("train", "validation", "test"):
                for record in splits[split_name]:
                    connection.execute(
                        """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,
                        split,sequence_number) VALUES (?,?,?,?)""",
                        (version["id"], record["id"], split_name, sequence),
                    )
                    sequence += 1
            manifest, checksum = self._manifest(version, records, splits, filters, split, admin_id)
            distributions = self._distributions(records, splits)
            status = "completed_with_warnings" if leakage["status"] == "warning" else "completed"
            connection.execute(
                """UPDATE dataset_versions SET status='ready',manifest_json=?,record_count=?,
                language_distribution_json=?,split_distribution_json=?,checksum_sha256=?,
                finalized_at=CURRENT_TIMESTAMP,quality_summary_json=?,source_distribution_json=?,
                record_type_distribution_json=?,build_configuration_json=? WHERE id=?""",
                (
                    dumps_json(manifest),
                    len(records),
                    dumps_json(distributions["language"]),
                    dumps_json(distributions["split"]),
                    checksum,
                    dumps_json(distributions["quality"]),
                    dumps_json(distributions["source_type"]),
                    dumps_json(distributions["record_type"]),
                    dumps_json({"selection_filters": filters, "split_configuration": split}),
                    version["id"],
                ),
            )
            connection.execute(
                """UPDATE dataset_build_jobs SET status=?,total_candidate_records=?,
                selected_records=?,excluded_records=?,train_records=?,validation_records=?,
                test_records=?,warning_records=?,error_records=0,progress=1,started_at=COALESCE(started_at,CURRENT_TIMESTAMP),
                completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (
                    status,
                    len(records) + len(excluded),
                    len(records),
                    len(excluded),
                    len(splits["train"]),
                    len(splits["validation"]),
                    len(splits["test"]),
                    1 if leakage["status"] == "warning" else 0,
                    public_id,
                ),
            )
            self.repository.add_build_event(
                connection,
                public_id,
                "build_completed",
                "building",
                status,
                None,
                {"checksum": checksum[:12]},
            )
            _audit(
                connection,
                "dataset_build_completed",
                admin_id,
                public_id,
                dataset_version_public_id=version["public_id"],
                checksum_prefix=checksum[:12],
                record_count=len(records),
            )
            return _public(self.repository.build(connection, public_id))

    def version_items(self, public_id: str, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            total = connection.execute(
                "SELECT COUNT(*) FROM dataset_version_items WHERE dataset_version_id=?",
                (version["id"],),
            ).fetchone()[0]
            rows = connection.execute(
                """SELECT i.split,i.sequence_number,r.public_id,r.record_type,r.language,
                r.instruction,r.input_text,r.output_text,r.normalized_input,r.content_hash
                FROM dataset_version_items i JOIN dataset_records r ON r.id=i.dataset_record_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number LIMIT ? OFFSET ?""",
                (version["id"], page_size, (page - 1) * page_size),
            ).fetchall()
        return self._page([_public(row) for row in rows], total, page, page_size)

    def manifest(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            return loads_json(version["manifest_json"])

    def verify_version(self, public_id: str, admin_id: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            records = connection.execute(
                """SELECT r.*,i.split,i.sequence_number,s.public_id AS source_public_id,
                s.source_type,s.licence_status,s.name AS source_name
                FROM dataset_version_items i JOIN dataset_records r ON r.id=i.dataset_record_id
                LEFT JOIN dataset_sources s ON s.id=r.source_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
                (version["id"],),
            ).fetchall()
            splits = {"train": [], "validation": [], "test": []}
            for row in records:
                splits[row["split"]].append(row)
            # Phase 2.7I: re-verify using whichever checksum payload
            # version this version's own already-stored manifest was
            # actually built with -- a pre-Phase-2.7I version's manifest
            # predates the `checksum_payload_version` key entirely, so it
            # defaults to `1` (the original, full-per-record-text
            # payload), never the new default -- never a false-negative
            # "unverified" result caused only by this phase's own change.
            stored_payload_version = loads_json(version["manifest_json"]).get("checksum_payload_version", 1)
            manifest, checksum = self._manifest(
                version,
                list(records),
                splits,
                loads_json(version["build_configuration_json"]).get("selection_filters", {}),
                loads_json(version["build_configuration_json"]).get("split_configuration", {}),
                "verification",
                payload_version=stored_payload_version,
            )
            ok = checksum == version["checksum_sha256"]
            if admin_id:
                _audit(
                    connection,
                    "dataset_checksum_verified",
                    admin_id,
                    public_id,
                    checksum_prefix=checksum[:12],
                    verified=ok,
                )
        return {
            "verified": ok,
            "checksum_sha256": checksum,
            "stored_checksum_sha256": version["checksum_sha256"],
            "manifest": manifest,
        }

    def create_export(
        self, version_public_id: str, export_format: str, admin_id: str
    ) -> dict[str, Any]:
        if export_format not in {"jsonl", "manifest_json", "split_jsonl_bundle"}:
            raise ValidationError("unsupported export format")
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, version_public_id)
            if version["status"] not in {"ready", "archived"}:
                raise ValidationError("only ready or archived dataset versions can be exported")
            records = connection.execute(
                """SELECT r.*,i.split,i.sequence_number,s.public_id AS source_public_id,
                s.source_type,s.licence_status,s.name AS source_name
                FROM dataset_version_items i JOIN dataset_records r ON r.id=i.dataset_record_id
                LEFT JOIN dataset_sources s ON s.id=r.source_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number""",
                (version["id"],),
            ).fetchall()
            if len(records) > self.settings.dataset_export_max_records:
                raise ValidationError("dataset export record limit exceeded")
            public_id = str(uuid4())
            safe = _safe_name(version["name"], version["version"]) + "_" + public_id[:8]
            target_dir = self.settings.resolved_dataset_export_dir / safe
            if target_dir.exists():
                raise ConflictError("dataset export already exists")
            target_dir.mkdir(parents=True, exist_ok=False)
            split_files = self._write_export_files(target_dir, version, records)
            checksum = self._checksum_files(target_dir, split_files)
            connection.execute(
                """INSERT INTO dataset_exports(public_id,dataset_version_id,export_format,status,
                safe_name,record_count,checksum_sha256,file_manifest_json,created_by_admin_public_id,
                completed_at) VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (
                    public_id,
                    version["id"],
                    export_format,
                    "completed",
                    safe,
                    len(records),
                    checksum,
                    dumps_json({"files": split_files}),
                    admin_id,
                ),
            )
            connection.execute(
                "UPDATE dataset_versions SET export_status='completed' WHERE id=?", (version["id"],)
            )
            _audit(
                connection,
                "dataset_export_created",
                admin_id,
                public_id,
                dataset_version_public_id=version_public_id,
                checksum_prefix=checksum[:12],
            )
            return _public(self.repository.export(connection, public_id))

    def list_exports(self, version_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": self.repository.list_exports(connection, version_public_id)}

    def get_export(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return _public(self.repository.export(connection, public_id))

    def verify_export(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.export(connection, public_id)
            base = self.settings.resolved_dataset_export_dir / row["safe_name"]
            files = loads_json(row["file_manifest_json"]).get("files", [])
            checksum = self._checksum_files(base, files)
            ok = checksum == row["checksum_sha256"]
            _audit(connection, "dataset_export_verified", admin_id, public_id, verified=ok)
        return {
            "verified": ok,
            "checksum_sha256": checksum,
            "stored_checksum_sha256": row["checksum_sha256"],
        }

    def export_file(self, public_id: str) -> Path:
        with self.repository.transaction() as connection:
            row = self.repository.export(connection, public_id)
            manifest = loads_json(row["file_manifest_json"])
        path = self.settings.resolved_dataset_export_dir / row["safe_name"] / "manifest.json"
        if "manifest.json" not in manifest.get("files", []) or not path.is_file():
            raise ValidationError("export manifest is not available")
        return path

    def events(self, build_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": self.repository.build_events(connection, build_public_id)}

    def _select_records(self, connection, filters: dict[str, Any]):
        records = self.repository.selectable_records(
            connection, filters, self.settings.dataset_export_max_records
        )
        selected, excluded = [], []
        min_score = float(filters.get("minimum_quality_score", 0))
        require_ready = bool(filters.get("require_ready_quality", False))
        seen_hashes: set[str] = set()
        for record in records:
            assessment = connection.execute(
                """SELECT * FROM dataset_quality_assessments WHERE dataset_record_id=?
                ORDER BY created_at DESC,id DESC LIMIT 1""",
                (record["id"],),
            ).fetchone()
            if record["content_hash"] in seen_hashes:
                excluded.append(
                    {"record_public_id": record["public_id"], "reason": "duplicate_hash"}
                )
                continue
            if assessment and assessment["overall_score"] < min_score:
                excluded.append(
                    {"record_public_id": record["public_id"], "reason": "quality_score"}
                )
                continue
            if require_ready and (not assessment or assessment["readiness_status"] != "ready"):
                excluded.append(
                    {"record_public_id": record["public_id"], "reason": "quality_readiness"}
                )
                continue
            seen_hashes.add(record["content_hash"])
            selected.append(record)
        return selected, excluded

    def _split_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        split = {
            "train_percent": raw.get("train_percent", self.settings.dataset_default_train_percent),
            "validation_percent": raw.get(
                "validation_percent", self.settings.dataset_default_validation_percent
            ),
            "test_percent": raw.get("test_percent", self.settings.dataset_default_test_percent),
            "seed": raw.get("seed", self.settings.dataset_split_seed),
        }
        if split["train_percent"] + split["validation_percent"] + split["test_percent"] != 100:
            raise ValidationError("split percentages must total 100")
        return split

    def _groups(self, records) -> list[list[Any]]:
        buckets: dict[str, list[Any]] = defaultdict(list)
        for record in records:
            metadata = loads_json(record["metadata_json"])
            document_group = metadata.get("document_public_id")
            page_start = metadata.get("source_page_start")
            page_end = metadata.get("source_page_end")
            if document_group and page_start:
                key = f"document:{document_group}:{page_start}:{page_end}"
            else:
                key = f"hash:{record['content_hash'] or record['public_id']}"
            buckets[key].append(record)
        return [buckets[key] for key in sorted(buckets)]

    def _split_groups(self, groups: list[list[Any]], split: dict[str, Any]) -> dict[str, list[Any]]:
        shuffled = list(groups)
        random.Random(split["seed"]).shuffle(shuffled)
        total = sum(len(group) for group in shuffled)
        if total <= 2:
            targets = {"train": total, "validation": 0, "test": 0}
        elif total < 20:
            targets = {"train": max(total - 1, 1), "validation": 1, "test": 0}
        else:
            targets = {
                "train": math.floor(total * split["train_percent"] / 100),
                "validation": math.floor(total * split["validation_percent"] / 100),
                "test": 0,
            }
            targets["test"] = total - targets["train"] - targets["validation"]
        output = {"train": [], "validation": [], "test": []}
        for group in shuffled:
            target = min(output, key=lambda name: len(output[name]) - targets[name])
            output[target].extend(sorted(group, key=lambda row: row["public_id"]))
        for name in output:
            output[name].sort(key=lambda row: (row["content_hash"], row["public_id"]))
        return output

    def _leakage(self, splits: dict[str, list[Any]]) -> dict[str, Any]:
        seen: dict[str, str] = {}
        conflicts = []
        for split_name, records in splits.items():
            for record in records:
                digest = record["content_hash"]
                if digest in seen and seen[digest] != split_name:
                    conflicts.append({"content_hash": digest, "splits": [seen[digest], split_name]})
                seen[digest] = split_name
        return {"status": "blocked" if conflicts else "safe", "conflicts": conflicts}

    def _preview(self, records, excluded, splits, leakage):
        return {
            "candidate_records": len(records) + len(excluded),
            "selected_records": len(records),
            "excluded_records": len(excluded),
            "excluded": excluded[:100],
            "split_counts": {key: len(value) for key, value in splits.items()},
            "leakage": leakage,
        }

    def _distributions(self, records, splits):
        return {
            "language": dict(Counter(row["language"] for row in records)),
            "record_type": dict(Counter(row["record_type"] for row in records)),
            "source_type": dict(Counter(row["source_type"] or "unknown" for row in records)),
            "split": {key: len(value) for key, value in splits.items()},
            "quality": {},
        }

    def _manifest(self, version, records, splits, filters, split_config, admin_id, *, payload_version: int | None = None):
        """Phase 2.7I: `payload_version` selects both how the checksum is
        computed and whether the stored manifest embeds a full per-record
        identity list. A fresh build (`run_build()`, no `payload_version`
        passed) always uses the current `CHECKSUM_PAYLOAD_VERSION` and
        records it in the manifest itself
        (`content["checksum_payload_version"]`). Re-verifying an existing
        version (`verify_version()`) instead passes the version the
        version's own already-stored manifest recorded, so a
        pre-Phase-2.7I dataset version (whose manifest predates this key
        entirely, defaulting to `1`) is re-verified with the exact
        original, unmodified payload shape -- never silently invalidated
        by a change to how *new* checksums are computed.

        Finding B (Phase 2.7H report §13): `payload_version==1`'s
        `record_public_ids_by_split` -- one `{public_id, content_hash,
        source_public_id}` entry per real record -- made both the
        checksum input AND the *stored* `manifest_json` itself grow
        linearly with record count, exceeding `Settings.
        max_metadata_bytes` (65536 bytes) at a few hundred records
        regardless of the compactness of any single record's entry.
        `payload_version==2` drops this list from both: the checksum is
        instead a small, fixed-size identity JSON combined with a
        chained, incrementally-hashed per-record fingerprint
        (`_checksum_fingerprint_v2()`, never materialized as one big JSON
        value), and the stored manifest keeps only the real, already-
        bounded aggregate distributions (language/record-type/source-
        type/split counts -- bounded by the number of *distinct*
        categories, never by record count) plus a pointer to
        `version_items()`, the real, existing, paginated API that already
        exposes exactly the same per-record identity information without
        any size ceiling. Both the checksum computation and the persisted
        manifest are now O(1) in size with respect to record count."""

        if payload_version is None:
            payload_version = CHECKSUM_PAYLOAD_VERSION
        distributions = self._distributions(records, splits)
        content = {
            "project": "Brud AI",
            "dataset_name": version["name"],
            "dataset_version": version["version"],
            "schema_version": 6,
            "quality_ruleset_version": self.settings.quality_ruleset_version,
            "created_by_admin_public_id": admin_id,
            "record_count": len(records),
            "split_counts": distributions["split"],
            "language_distribution": distributions["language"],
            "record_type_distribution": distributions["record_type"],
            "source_type_distribution": distributions["source_type"],
            "selection_filters": filters,
            "split_configuration": split_config,
            "split_seed": split_config.get("seed", self.settings.dataset_split_seed),
            "checksum_algorithm": "sha256",
            "checksum_payload_version": payload_version,
            "parent_dataset_version": None,
        }
        if payload_version == 1:
            content["record_public_ids_by_split"] = {
                name: [
                    {
                        "public_id": row["public_id"],
                        "content_hash": row["content_hash"],
                        "source_public_id": row["source_public_id"],
                    }
                    for row in rows
                ]
                for name, rows in splits.items()
            }
            checksum_input = dumps_json(self._checksum_payload_v1(content, splits)).encode("utf-8")
        else:
            content["per_record_identity"] = (
                "not embedded in this manifest to keep manifest size bounded regardless of "
                "dataset size (Phase 2.7I) -- fetch it via DatasetVersioningService.version_items() "
                "/ GET /admin/datasets/versions/{public_id}/items, paginated, at any time"
            )
            checksum_input = self._checksum_fingerprint_v2(content, splits)
        checksum = hashlib.sha256(checksum_input).hexdigest()
        content["content_checksum"] = checksum
        return content, checksum

    def _checksum_payload_v1(self, manifest, splits):
        """The original (pre-Phase-2.7I) checksum payload shape, kept
        byte-for-byte unchanged so a dataset version built before this
        phase can still be re-verified against its own originally-stored
        checksum. Never used for a fresh build after this phase -- only
        for re-verifying an existing v1 manifest. Do not modify this
        method; add new behavior to `_checksum_fingerprint_v2` instead."""

        rows = []
        for split_name in ("train", "validation", "test"):
            for row in splits[split_name]:
                rows.append(
                    {
                        "split": split_name,
                        "public_id": row["public_id"],
                        "record_type": row["record_type"],
                        "language": row["language"],
                        "instruction": row["instruction"],
                        "input_text": row["input_text"],
                        "output_text": row["output_text"],
                        "normalized_input": row["normalized_input"],
                        "content_hash": row["content_hash"],
                        "source_public_id": row["source_public_id"],
                    }
                )
        return {
            "identity": {
                k: manifest[k]
                for k in ("project", "dataset_name", "dataset_version", "schema_version")
            },
            "records": rows,
        }

    def _checksum_fingerprint_v2(self, manifest, splits) -> bytes:
        """Phase 2.7I, Finding B: the real fix. Mission Part 7, Option B
        ("hashing a deterministic ordered record fingerprint sequence
        rather than embedding the complete record metadata in the
        checksum JSON") applied literally: every record contributes one
        compact, deterministic, delimited fingerprint string
        (`split|public_id|record_type|language|content_hash|
        source_public_id`) that is fed straight into a running SHA-256 via
        `hashlib.sha256().update()`, in the same deterministic
        train-then-validation-then-test / `sequence_number` order
        `fetch_split_records()` and every other real consumer already
        uses -- no per-record JSON object, no big list, no
        `dumps_json()` call over record-count-many entries, ever. Memory
        and serialized-payload size are therefore both O(1) with respect
        to record count; only a single 64-byte running digest is held at
        any time regardless of whether the dataset has 40 or 40,000,000
        records.

        Every non-redundant field the old payload compared is still
        included per record (`split`, `public_id`, `record_type`,
        `language`, `source_public_id`); `content_hash` alone already
        deterministically captures `instruction`/`input_text`/
        `output_text`/`normalized_input` (`dataset_service.content_hash()`,
        `backend/services/dataset_service.py:54-64`) for every record
        created through the real record-creation/document-ingestion path,
        so no content, provenance, or split-reassignment change the old
        payload could detect goes undetected here -- the checksum
        contract (Part 8) is unchanged, only its size-scaling is fixed. A
        `\\x00` separator after every record's fingerprint makes the
        sequence unambiguous (a value containing a literal `|` can never
        be confused with a field boundary from an adjacent record)."""

        identity_json = dumps_json(
            {k: manifest[k] for k in ("project", "dataset_name", "dataset_version", "schema_version")}
        ).encode("utf-8")
        fingerprint = hashlib.sha256()
        for split_name in ("train", "validation", "test"):
            for row in splits[split_name]:
                fingerprint.update(
                    "|".join(
                        (
                            split_name,
                            row["public_id"] or "",
                            row["record_type"] or "",
                            row["language"] or "",
                            row["content_hash"] or "",
                            row["source_public_id"] or "",
                        )
                    ).encode("utf-8")
                )
                fingerprint.update(b"\x00")
        return identity_json + b"|" + fingerprint.hexdigest().encode("utf-8")

    def _write_export_files(self, target_dir: Path, version, records) -> list[str]:
        manifest = loads_json(version["manifest_json"])
        (target_dir / "manifest.json").write_text(dumps_json(manifest) + "\n", encoding="utf-8")
        files = ["manifest.json"]
        by_split = {"train": [], "validation": [], "test": []}
        for row in records:
            by_split[row["split"]].append(row)
        for split_name, rows in by_split.items():
            filename = f"{split_name}.jsonl"
            with (target_dir / filename).open("w", encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    handle.write(dumps_json(self._export_record(row)) + "\n")
            files.append(filename)
        return files

    def _export_record(self, row) -> dict[str, Any]:
        return {
            "public_id": row["public_id"],
            "record_type": row["record_type"],
            "language": row["language"],
            "instruction": row["instruction"],
            "input_text": row["input_text"],
            "output_text": row["output_text"],
            "normalized_input": row["normalized_input"],
            "source_public_id": row["source_public_id"],
        }

    def _checksum_files(self, base: Path, files: list[str]) -> str:
        digest = hashlib.sha256()
        for filename in sorted(files):
            path = (base / filename).resolve()
            if not path.is_relative_to(base.resolve()):
                raise ValidationError("invalid export file reference")
            digest.update(filename.encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def _page(self, items, total: int, page: int, page_size: int) -> dict[str, Any]:
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        }
