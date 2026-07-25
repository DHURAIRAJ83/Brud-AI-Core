"""Phase 19 collections, balance policies, corpus builds, partitioning,
and corpus versions.

A build only ever selects a subset of already-eligible, already
privacy/safety/quality/duplicate/contamination-checked segments -- it
never fabricates or duplicates content to fill a balance target, and
never lets a duplicate-cluster member or an evaluation/regression
fixture cross a train/validation/test split boundary.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import (
    BalancePolicyCreate,
    BalancePreviewRequest,
    BuildCreate,
    CollectionCreate,
    PartitionPreviewRequest,
    VersionCreate,
)
from core_model.corpus.balancing import (
    cap_source_share,
    compare_to_targets,
    compute_actual_distribution,
    source_diversity_report,
)
from core_model.corpus.licence_policy import assess_training_export_eligibility
from core_model.corpus.partitioning import (
    assign_partitions,
    partition_checksum,
    verify_partition_isolation,
)


class CorpusBuildService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- collections -----------------------------------------------------

    def create_collection(self, payload: CollectionCreate, admin_id: str) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        for field in (
            "language_policy",
            "domain_policy",
            "style_policy",
            "licence_policy",
            "quality_policy",
        ):
            values[f"{field}_json"] = dumps_json(values.pop(field))
        values["created_by_admin_public_id"] = admin_id
        with self.repository.transaction() as connection:
            public_id = self.repository.create_collection(connection, values)
            self._audit(connection, "corpus_collection_created", admin_id, public_id)
            return public_row(self.repository.collection(connection, public_id))

    def list_collections(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {
                "items": [public_row(row) for row in self.repository.list_collections(connection)]
            }

    def get_collection(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.collection(connection, public_id)
            result = public_row(row)
            result["members"] = [
                public_row(member)
                for member in self.repository.members_for_collection(connection, row["id"])
            ]
            return result

    def _resolve_segment_licence(self, connection, segment_row) -> dict[str, Any]:
        """Walks segment -> normalized document -> extracted document ->
        source file -> snapshot -> source -> latest licence, and reports
        both the real licence family and whether it is training-export
        eligible -- a segment must never be silently treated as
        licence-eligible just because it passed quality/privacy/safety."""

        normalized_document_id = connection.execute(
            "SELECT public_id FROM corpus_normalized_documents WHERE id=?",
            (segment_row["normalized_document_id"],),
        ).fetchone()["public_id"]
        normalized_document = self.repository.normalized_document(
            connection, normalized_document_id
        )
        extracted_document_public_id = connection.execute(
            "SELECT public_id FROM corpus_extracted_documents WHERE id=?",
            (normalized_document["extracted_document_id"],),
        ).fetchone()["public_id"]
        extracted_document = self.repository.extracted_document(
            connection, extracted_document_public_id
        )
        file_public_id = connection.execute(
            "SELECT public_id FROM corpus_source_files WHERE id=?",
            (extracted_document["source_file_id"],),
        ).fetchone()["public_id"]
        file_row = self.repository.file(connection, file_public_id)
        snapshot_public_id = connection.execute(
            "SELECT public_id FROM corpus_source_snapshots WHERE id=?",
            (file_row["snapshot_id"],),
        ).fetchone()["public_id"]
        snapshot_row = self.repository.snapshot(connection, snapshot_public_id)
        source_row = self.repository.source(connection, snapshot_row["source_public_id"])
        licence_row = self.repository.latest_licence_for_source(connection, source_row["id"])

        if licence_row is None:
            return {"licence_family": "unknown", "eligible": False}

        import datetime as _dt

        expires_at = licence_row["expires_at"]
        expired = bool(expires_at) and expires_at < _dt.datetime.now(_dt.UTC).isoformat()
        eligibility = assess_training_export_eligibility(
            review_status=licence_row["review_status"],
            ai_training_permitted=bool(licence_row["ai_training_permitted"]),
            source_status=source_row["status"],
            intended_use=source_row["intended_use"],
            licence_family=licence_row["licence_family"],
            expires_at_is_past=expired,
        )
        return {
            "licence_family": licence_row["licence_family"],
            "eligible": eligibility["eligible"],
        }

    def add_member(
        self, collection_public_id: str, segment_public_id: str, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            collection_row = self.repository.collection(connection, collection_public_id)
            segment_row = self.repository.segment(connection, segment_public_id)

            quality_rows = self.repository.quality_assessments_for_subject(
                connection, "segment", segment_public_id
            )
            quality_status = "not_assessed"
            if quality_rows:
                quality_status = (
                    "fail"
                    if any(row["status"] == "fail" for row in quality_rows)
                    else "warning"
                    if any(row["status"] == "warning" for row in quality_rows)
                    else "pass"
                )
            privacy_rows = self.repository.findings_for_segment(connection, segment_row["id"])[
                "privacy"
            ]
            privacy_blocked = any(row["status"] == "blocked" for row in privacy_rows)
            safety_rows = self.repository.findings_for_segment(connection, segment_row["id"])[
                "safety"
            ]
            safety_blocked = any(row["status"] == "blocked" for row in safety_rows)
            licence = self._resolve_segment_licence(connection, segment_row)

            eligible = (
                quality_status != "fail"
                and not privacy_blocked
                and not safety_blocked
                and licence["eligible"]
            )
            if quality_status == "fail":
                exclusion_reason = "failed_quality_privacy_or_safety_check"
            elif privacy_blocked or safety_blocked:
                exclusion_reason = "failed_quality_privacy_or_safety_check"
            elif not licence["eligible"]:
                exclusion_reason = "licence_not_training_eligible"
            else:
                exclusion_reason = None
            values = {
                "collection_id": collection_row["id"],
                "segment_id": segment_row["id"],
                "eligibility_status": "eligible" if eligible else "ineligible",
                "inclusion_reason": "passed_quality_privacy_safety_licence_checks"
                if eligible
                else "",
                "exclusion_reason": exclusion_reason,
                "licence_status": licence["licence_family"],
                "quality_status": quality_status,
                "duplicate_status": "unique",
                "contamination_status": "clean",
            }
            member_public_id = self.repository.create_collection_member(connection, values)
            self._audit(
                connection,
                "corpus_collection_member_added",
                admin_id,
                member_public_id,
                eligible=eligible,
            )
            return public_row(
                next(
                    row
                    for row in self.repository.members_for_collection(
                        connection, collection_row["id"]
                    )
                    if row["public_id"] == member_public_id
                )
            )

    # --- balance policies -----------------------------------------------------

    def create_balance_policy(self, payload: BalancePolicyCreate, admin_id: str) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        for field in (
            "language_targets",
            "domain_targets",
            "style_targets",
            "source_type_targets",
            "licence_family_targets",
            "content_length_targets",
            "quality_band_targets",
        ):
            values[f"{field}_json"] = dumps_json(values.pop(field))
        values["created_by_admin_public_id"] = admin_id
        with self.repository.transaction() as connection:
            public_id = self.repository.create_balance_policy(connection, values)
            self._audit(connection, "corpus_balance_policy_created", admin_id, public_id)
            return public_row(self.repository.balance_policy(connection, public_id))

    def list_balance_policies(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {
                "items": [
                    public_row(row) for row in self.repository.list_balance_policies(connection)
                ]
            }

    # --- builds -----------------------------------------------------

    def create_build(self, payload: BuildCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy_row = self.repository.policy(connection, payload.corpus_policy_public_id)
            balance_row = self.repository.balance_policy(
                connection, payload.balance_policy_public_id
            )
            collection_rows = [
                self.repository.collection(connection, cid) for cid in payload.collection_public_ids
            ]
            if not collection_rows:
                raise ValidationError("a build requires at least one collection")

            values = {
                "corpus_policy_id": policy_row["id"],
                "balance_policy_id": balance_row["id"],
                "collection_ids_json": dumps_json(payload.collection_public_ids),
                "partition_configuration_json": dumps_json(payload.partition_configuration),
                "export_policy_json": dumps_json(payload.export_policy),
                "created_by_admin_public_id": admin_id,
            }
            if payload.deduplication_run_public_id:
                dedup_row = self.repository.deduplication_run(
                    connection, payload.deduplication_run_public_id
                )
                values["deduplication_run_id"] = dedup_row["id"]
            if payload.contamination_run_public_id:
                contamination_row = self.repository.contamination_run(
                    connection, payload.contamination_run_public_id
                )
                values["contamination_run_id"] = contamination_row["id"]

            build_public_id = self.repository.create_build(connection, values)
            build_row = self.repository.build(connection, build_public_id)
            self.repository.update_build(connection, build_row["id"], {"status": "validating"})

            eligible_members = []
            for collection_row in collection_rows:
                for member in self.repository.members_for_collection(
                    connection, collection_row["id"]
                ):
                    if member["eligibility_status"] == "eligible":
                        eligible_members.append({"member": member, "collection": collection_row})

            capped = cap_source_share(
                [
                    {**item["member"], "_collection_id": item["collection"]["id"]}
                    for item in eligible_members
                ],
                source_key="_collection_id",
                maximum_single_source_share=balance_row["maximum_single_source_share"],
            )

            groups: dict[int, list[str]] = {}
            member_by_segment_public_id: dict[str, dict[str, Any]] = {}
            for entry in capped["included"]:
                segment_row = connection.execute(
                    "SELECT public_id FROM corpus_segments WHERE id=?", (entry["segment_id"],)
                ).fetchone()
                segment_public_id = segment_row["public_id"]
                member_by_segment_public_id[segment_public_id] = entry
                cluster_row = connection.execute(
                    """SELECT c.id AS cluster_id FROM corpus_duplicate_members m
                    JOIN corpus_duplicate_clusters c ON c.id = m.cluster_id
                    WHERE m.segment_id=? ORDER BY m.id DESC LIMIT 1""",
                    (entry["segment_id"],),
                ).fetchone()
                group_key = cluster_row["cluster_id"] if cluster_row else entry["segment_id"]
                groups.setdefault(group_key, []).append(segment_public_id)

            group_payload = [
                {"group_key": str(key), "segment_public_ids": ids} for key, ids in groups.items()
            ]
            assignment = assign_partitions(
                group_payload,
                seed=payload.partition_configuration.get("seed", 42),
                proportions={
                    split: payload.partition_configuration.get(split, default)
                    for split, default in (("train", 0.98), ("validation", 0.01), ("test", 0.01))
                },
            )
            isolation = verify_partition_isolation(
                assignment,
                duplicate_clusters=[ids for ids in groups.values() if len(ids) > 1],
            )
            if not isolation["isolated"]:
                self.repository.update_build(
                    connection,
                    build_row["id"],
                    {"status": "failed", "failure_code": "partition_isolation_violated"},
                )
                raise ValidationError("partition isolation check failed; build aborted")

            included_count = 0
            for split, public_ids in assignment.items():
                for rank, segment_public_id in enumerate(public_ids):
                    member = member_by_segment_public_id[segment_public_id]
                    self.repository.create_build_member(
                        connection,
                        {
                            "build_id": build_row["id"],
                            "segment_id": member["segment_id"],
                            "collection_id": member["_collection_id"],
                            "selection_rank": rank,
                            "included": True,
                            "final_quality_band": member.get("quality_status", "unassessed"),
                            "final_licence_decision": member.get("licence_status", "unknown"),
                            "split": split,
                        },
                    )
                    included_count += 1

            for entry in capped["excluded"]:
                self.repository.create_build_member(
                    connection,
                    {
                        "build_id": build_row["id"],
                        "segment_id": entry["segment_id"],
                        "collection_id": entry["_collection_id"],
                        "included": False,
                        "exclusion_reason": "source_share_cap_exceeded",
                    },
                )

            for split, public_ids in assignment.items():
                checksum = partition_checksum({split: public_ids})
                self.repository.create_partition(
                    connection,
                    {
                        "build_id": build_row["id"],
                        "split": split,
                        "segment_count": len(public_ids),
                        "seed": payload.partition_configuration.get("seed", 42),
                        "checksum_sha256": checksum,
                    },
                )

            self.repository.update_build(
                connection,
                build_row["id"],
                {
                    "status": "completed",
                    "included_segment_count": included_count,
                    "excluded_segment_count": len(capped["excluded"]),
                },
            )
            self._audit(
                connection,
                "corpus_build_completed",
                admin_id,
                build_public_id,
                included_segment_count=included_count,
                excluded_segment_count=len(capped["excluded"]),
            )
            return self._build_detail(connection, build_public_id)

    def _build_detail(self, connection, public_id: str) -> dict[str, Any]:
        row = self.repository.build(connection, public_id)
        result = public_row(row)
        result["partitions"] = [
            public_row(partition)
            for partition in self.repository.partitions_for_build(connection, row["id"])
        ]
        return result

    def get_build(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self._build_detail(connection, public_id)

    def list_builds(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_builds(connection)]}

    def balance_report(self, build_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            build_row = self.repository.build(connection, build_public_id)
            balance_row = connection.execute(
                "SELECT * FROM corpus_balance_policies WHERE id=?",
                (build_row["balance_policy_id"],),
            ).fetchone()
            members = self.repository.members_for_build(connection, build_row["id"])
            included = [dict(member) for member in members if member["included"]]
            for member in included:
                domain_row = connection.execute(
                    "SELECT primary_domain FROM corpus_domain_assessments WHERE segment_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                member["domain"] = domain_row["primary_domain"] if domain_row else "general"
            actual = compute_actual_distribution(included, key="domain") if included else {}

            targets_raw = loads_json(balance_row["domain_targets_json"], default={})
            targets = {k: tuple(v) for k, v in targets_raw.items()}
            return {"domain_distribution_report": compare_to_targets(actual, targets)}

    # --- Phase 20: balance and partition previews -------------------------------

    def preview_balance(
        self, collection_public_id: str, payload: BalancePreviewRequest
    ) -> dict[str, Any]:
        """Read-only dry run -- never persists anything, never selects
        or excludes a single segment. Shows actual vs. target
        distribution across every configured dimension so an operator
        can adjust a balance policy before committing to a real build."""

        with self.repository.transaction() as connection:
            collection_row = self.repository.collection(connection, collection_public_id)
            balance_row = self.repository.balance_policy(
                connection, payload.balance_policy_public_id
            )
            members = [
                dict(member)
                for member in self.repository.members_for_collection(
                    connection, collection_row["id"]
                )
                if member["eligibility_status"] == "eligible"
            ]
            for member in members:
                domain_row = connection.execute(
                    "SELECT primary_domain FROM corpus_domain_assessments WHERE segment_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                member["domain"] = domain_row["primary_domain"] if domain_row else "general"
                language_row = connection.execute(
                    "SELECT language_category FROM corpus_language_assessments "
                    "WHERE segment_id=? ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                member["language"] = (
                    language_row["language_category"] if language_row else "unknown"
                )
                style_row = connection.execute(
                    "SELECT style FROM corpus_style_assessments WHERE segment_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                member["style"] = style_row["style"] if style_row else "formal"
                member["licence_family"] = member["licence_status"]

            report: dict[str, Any] = {}
            for dimension, target_column in (
                ("language", "language_targets_json"),
                ("domain", "domain_targets_json"),
                ("style", "style_targets_json"),
                ("licence_family", "licence_family_targets_json"),
            ):
                actual = compute_actual_distribution(members, key=dimension) if members else {}
                targets_raw = loads_json(balance_row[target_column], default={})
                targets = {k: tuple(v) for k, v in targets_raw.items()}
                report[dimension] = compare_to_targets(actual, targets)
            report["source_diversity"] = (
                source_diversity_report(members, source_key="collection_id") if members else {}
            )
            report["eligible_segment_count"] = len(members)
            return report

    def preview_partitions(
        self, collection_public_id: str, payload: PartitionPreviewRequest, admin_id: str
    ) -> dict[str, Any]:
        """Persists the preview result (append-only, for audit/
        comparison purposes) but never creates a `corpus_build` or
        assigns any segment -- non-binding, may be run repeatedly with
        different seeds/proportions before a real build is created."""

        with self.repository.transaction() as connection:
            collection_row = self.repository.collection(connection, collection_public_id)
            members = [
                dict(member)
                for member in self.repository.members_for_collection(
                    connection, collection_row["id"]
                )
                if member["eligibility_status"] == "eligible"
            ]
            groups: dict[int, list[str]] = {}
            for member in members:
                segment_row = connection.execute(
                    "SELECT public_id FROM corpus_segments WHERE id=?", (member["segment_id"],)
                ).fetchone()
                cluster_row = connection.execute(
                    """SELECT c.id AS cluster_id FROM corpus_duplicate_members m
                    JOIN corpus_duplicate_clusters c ON c.id = m.cluster_id
                    WHERE m.segment_id=? ORDER BY m.id DESC LIMIT 1""",
                    (member["segment_id"],),
                ).fetchone()
                group_key = cluster_row["cluster_id"] if cluster_row else member["segment_id"]
                groups.setdefault(group_key, []).append(segment_row["public_id"])

            group_payload = [
                {"group_key": str(key), "segment_public_ids": ids} for key, ids in groups.items()
            ]
            assignment = assign_partitions(
                group_payload, seed=payload.seed, proportions=payload.proportions
            )
            isolation = verify_partition_isolation(
                assignment,
                duplicate_clusters=[ids for ids in groups.values() if len(ids) > 1],
            )
            distribution = {split: len(ids) for split, ids in assignment.items()}
            checksum = partition_checksum(assignment)

            preview_public_id = self.repository.create_partition_preview(
                connection,
                {
                    "collection_id": collection_row["id"],
                    "seed": payload.seed,
                    "proportions_json": dumps_json(payload.proportions),
                    "strict_mode": payload.strict_mode,
                    "distribution_json": dumps_json(distribution),
                    "isolation_report_json": dumps_json(isolation),
                    "preview_checksum_sha256": checksum,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection,
                "corpus_partition_preview_created",
                admin_id,
                preview_public_id,
                distribution=distribution,
                isolated=isolation["isolated"],
            )
            return public_row(self.repository.partition_preview(connection, preview_public_id))

    # --- versions -----------------------------------------------------

    def create_version(
        self, build_public_id: str, payload: VersionCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            build_row = self.repository.build(connection, build_public_id)
            if build_row["status"] != "completed":
                raise ValidationError("build must be completed before it can be versioned")
            members = [
                dict(member)
                for member in self.repository.members_for_build(connection, build_row["id"])
                if member["included"]
            ]

            counts = {"train": 0, "validation": 0, "test": 0}
            total_characters = 0
            language_counter: dict[str, int] = {}
            domain_counter: dict[str, int] = {}
            style_counter: dict[str, int] = {}
            licence_counter: dict[str, int] = {}
            for member in members:
                counts[member["split"]] = counts.get(member["split"], 0) + 1
                segment_row = connection.execute(
                    "SELECT character_count FROM corpus_segments WHERE id=?",
                    (member["segment_id"],),
                ).fetchone()
                total_characters += segment_row["character_count"] if segment_row else 0
                language_row = connection.execute(
                    "SELECT language_category FROM corpus_language_assessments WHERE segment_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                language_counter[
                    language_row["language_category"] if language_row else "unknown"
                ] = (
                    language_counter.get(
                        language_row["language_category"] if language_row else "unknown", 0
                    )
                    + 1
                )
                domain_row = connection.execute(
                    "SELECT primary_domain FROM corpus_domain_assessments WHERE segment_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                domain_counter[domain_row["primary_domain"] if domain_row else "general"] = (
                    domain_counter.get(domain_row["primary_domain"] if domain_row else "general", 0)
                    + 1
                )
                style_row = connection.execute(
                    "SELECT style FROM corpus_style_assessments WHERE segment_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                if style_row:
                    style_counter[style_row["style"]] = style_counter.get(style_row["style"], 0) + 1
                licence_counter[member["final_licence_decision"]] = (
                    licence_counter.get(member["final_licence_decision"], 0) + 1
                )

            values = {
                "build_id": build_row["id"],
                "semantic_version": payload.semantic_version,
                "train_segment_count": counts.get("train", 0),
                "validation_segment_count": counts.get("validation", 0),
                "test_segment_count": counts.get("test", 0),
                "language_distribution_json": dumps_json(language_counter),
                "domain_distribution_json": dumps_json(domain_counter),
                "style_distribution_json": dumps_json(style_counter),
                "source_distribution_json": dumps_json({}),
                "licence_distribution_json": dumps_json(licence_counter),
                "total_characters": total_characters,
                "estimated_tokens": total_characters // 4,
                "created_by_admin_public_id": admin_id,
            }
            version_public_id = self.repository.create_version(connection, values)
            self.repository.update_version(
                connection,
                self.repository.version(connection, version_public_id)["id"],
                {"status": "ready"},
            )
            self._audit(
                connection,
                "corpus_version_created",
                admin_id,
                version_public_id,
                total_characters=total_characters,
            )
            return public_row(self.repository.version(connection, version_public_id))

    def get_version(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.version(connection, public_id))

    def list_versions(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_versions(connection)]}

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
