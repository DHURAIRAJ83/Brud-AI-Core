"""Phase 20 formal pretraining-readiness gate.

Aggregates real, already-computed signals from every earlier Phase 19/
20 stage (licence review, quality assessments, privacy/safety
findings, deduplication, contamination, balance, partitions, tokenizer
analysis, manifest, export) into the 15-dimension gate defined in
``core_model.corpus.readiness`` -- this service never re-derives a
signal a prior stage already computed and persisted, and never
upgrades a warning to a pass.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import ReadinessEvaluationCreate
from core_model.corpus.manifest import verify_manifest_checksum
from core_model.corpus.partitioning import verify_partition_isolation
from core_model.corpus.readiness import READINESS_DIMENSIONS, overall_readiness

_UNICODE_CORRUPTION_WARN_THRESHOLD = 0.02


class CorpusReadinessService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def evaluate(self, payload: ReadinessEvaluationCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            build_row = self.repository.build(connection, payload.build_public_id)
            tokenizer_analysis_id = None
            if payload.tokenizer_analysis_public_id:
                tokenizer_analysis_id = self.repository.tokenizer_analysis(
                    connection, payload.tokenizer_analysis_public_id
                )["id"]

            evaluation_public_id = self.repository.create_readiness_evaluation(
                connection,
                {
                    "build_id": build_row["id"],
                    "tokenizer_analysis_id": tokenizer_analysis_id,
                    "created_by_admin_public_id": admin_id,
                },
            )
            evaluation_row = self.repository.readiness_evaluation(connection, evaluation_public_id)
            self.repository.update_readiness_evaluation(
                connection, evaluation_row["id"], {"status": "running"}
            )

            members = [
                dict(m) for m in self.repository.members_for_build(connection, build_row["id"])
            ]
            included = [m for m in members if m["included"]]
            hard_failure_reasons: list[str] = []
            results: dict[str, str] = dict.fromkeys(READINESS_DIMENSIONS, "not_evaluated")

            results["source_governance"], reasons = self._check_source_governance(
                connection, included
            )
            hard_failure_reasons.extend(reasons)

            results["licence_compliance"], reasons = self._check_dimension_via_quality(
                connection, included, "licence_completeness"
            )
            if results["licence_compliance"] == "fail":
                hard_failure_reasons.append("unapproved_training_licence")

            results["provenance_completeness"], reasons = self._check_dimension_via_quality(
                connection, included, "provenance_completeness"
            )
            if results["provenance_completeness"] == "fail":
                hard_failure_reasons.append("missing_provenance")

            results["privacy_safety"], _ = self._check_dimension_via_quality(
                connection, included, "privacy_safety"
            )
            if self._has_blocked_privacy_finding(connection, included):
                results["privacy_safety"] = "fail"
                hard_failure_reasons.append("privacy_severe_findings")

            results["content_safety"], _ = self._check_dimension_via_quality(
                connection, included, "safety_quality"
            )

            results["extraction_quality"], _ = self._check_dimension_via_quality(
                connection, included, "ocr_quality"
            )
            results["normalization_integrity"] = self._check_unicode_integrity(
                connection, included, hard_failure_reasons
            )
            results["segment_quality"], _ = self._check_dimension_via_quality(
                connection, included, "sentence_completeness"
            )

            results["deduplication_completion"] = self._check_run_completed(
                connection, build_row["deduplication_run_id"], "corpus_deduplication_runs"
            )
            results["contamination_completion"] = self._check_contamination(
                connection, build_row, included, hard_failure_reasons
            )
            results["balance_adequacy"] = self._check_balance(connection, build_row, included)
            results["partition_integrity"] = self._check_partition_integrity(
                connection, build_row, included, hard_failure_reasons
            )
            results["tokenizer_compatibility"] = self._check_tokenizer_compatibility(
                connection, tokenizer_analysis_id
            )
            results["manifest_integrity"] = self._check_manifest(
                connection, build_row, hard_failure_reasons
            )
            results["export_integrity"] = self._check_export(
                connection, build_row, hard_failure_reasons
            )

            overall = overall_readiness(results)
            for dimension, status in results.items():
                self.repository.record_readiness_dimension(
                    connection,
                    {
                        "evaluation_id": evaluation_row["id"], "dimension": dimension,
                        "status": status, "details_json": "{}",
                    },
                )
            self.repository.update_readiness_evaluation(
                connection, evaluation_row["id"],
                {
                    "status": "completed", "overall_result": overall,
                    "hard_failure_reasons_json": dumps_json(sorted(set(hard_failure_reasons))),
                },
            )
            self._audit(
                connection, "corpus_readiness_evaluated", admin_id, evaluation_public_id,
                overall_result=overall,
            )
            return self._detail(connection, evaluation_public_id)

    # --- dimension checks -----------------------------------------------------

    def _check_source_governance(self, connection, included) -> tuple[str, list[str]]:
        if not included:
            return "not_evaluated", []
        segment_ids = [m["segment_id"] for m in included]
        placeholders = ",".join("?" * len(segment_ids))
        rows = connection.execute(
            f"""SELECT DISTINCT reg.production_lifecycle_status FROM corpus_segments seg
            JOIN corpus_normalized_documents nd ON nd.id = seg.normalized_document_id
            JOIN corpus_extracted_documents ed ON ed.id = nd.extracted_document_id
            JOIN corpus_source_files f ON f.id = ed.source_file_id
            JOIN corpus_source_snapshots snap ON snap.id = f.snapshot_id
            JOIN corpus_source_registries reg ON reg.id = snap.source_id
            WHERE seg.id IN ({placeholders})""",
            segment_ids,
        ).fetchall()
        statuses = {row["production_lifecycle_status"] for row in rows}
        if statuses <= {"approved", "ingested"}:
            return "pass", []
        if statuses & {"rejected", "retired"}:
            return "fail", ["source_not_production_approved"]
        return "warning", []

    def _check_dimension_via_quality(
        self, connection, included, dimension: str
    ) -> tuple[str, list[str]]:
        if not included:
            return "not_evaluated", []
        segment_public_ids = [
            row["public_id"]
            for row in (
                connection.execute(
                    "SELECT public_id FROM corpus_segments WHERE id=?", (m["segment_id"],)
                ).fetchone()
                for m in included
            )
        ]
        placeholders = ",".join("?" * len(segment_public_ids))
        rows = connection.execute(
            f"""SELECT status FROM corpus_quality_assessments
            WHERE subject_type='segment' AND dimension=?
            AND subject_reference_public_id IN ({placeholders})""",
            (dimension, *segment_public_ids),
        ).fetchall()
        if not rows:
            return "not_evaluated", []
        statuses = [row["status"] for row in rows]
        if any(s == "fail" for s in statuses):
            return "fail", []
        if any(s == "warning" for s in statuses):
            return "warning", []
        return "pass", []

    def _has_blocked_privacy_finding(self, connection, included) -> bool:
        if not included:
            return False
        segment_ids = [m["segment_id"] for m in included]
        placeholders = ",".join("?" * len(segment_ids))
        row = connection.execute(
            f"""SELECT COUNT(*) FROM corpus_privacy_findings
            WHERE segment_id IN ({placeholders}) AND status='blocked'""",
            segment_ids,
        ).fetchone()
        return row[0] > 0

    def _check_unicode_integrity(
        self, connection, included, hard_failure_reasons: list[str]
    ) -> str:
        if not included:
            return "not_evaluated"
        segment_ids = [m["segment_id"] for m in included]
        placeholders = ",".join("?" * len(segment_ids))
        rows = connection.execute(
            f"""SELECT nd.unicode_integrity_status FROM corpus_segments seg
            JOIN corpus_normalized_documents nd ON nd.id = seg.normalized_document_id
            WHERE seg.id IN ({placeholders})""",
            segment_ids,
        ).fetchall()
        total = len(rows) or 1
        corrupted = sum(1 for row in rows if row["unicode_integrity_status"] != "valid")
        ratio = corrupted / total
        if ratio > _UNICODE_CORRUPTION_WARN_THRESHOLD * 2:
            hard_failure_reasons.append("unsupported_unicode_corruption_above_threshold")
            return "fail"
        if ratio > _UNICODE_CORRUPTION_WARN_THRESHOLD:
            return "warning"
        return "pass"

    def _check_run_completed(self, connection, run_id: int | None, table: str) -> str:
        if run_id is None:
            return "not_evaluated"
        row = connection.execute(f"SELECT status FROM {table} WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return "not_evaluated"
        if row["status"] in {"completed", "completed_with_warnings"}:
            return "pass" if row["status"] == "completed" else "warning"
        return "fail"

    def _check_contamination(
        self, connection, build_row, included, hard_failure_reasons: list[str]
    ) -> str:
        base = self._check_run_completed(
            connection, build_row["contamination_run_id"], "corpus_contamination_runs"
        )
        if build_row["contamination_run_id"] is None:
            return base
        train_segment_ids = {
            m["segment_id"] for m in included if m.get("split") == "train"
        }
        if train_segment_ids:
            placeholders = ",".join("?" * len(train_segment_ids))
            rows = connection.execute(
                f"""SELECT COUNT(*) FROM corpus_contamination_findings
                WHERE contamination_run_id=? AND blocks_training=1
                AND segment_id IN ({placeholders})""",
                (build_row["contamination_run_id"], *train_segment_ids),
            ).fetchone()
            if rows[0] > 0:
                hard_failure_reasons.append("protected_evaluation_contamination_in_train")
                return "fail"
        return base

    def _check_balance(self, connection, build_row, included) -> str:
        if not included:
            return "not_evaluated"
        balance_row = connection.execute(
            "SELECT * FROM corpus_balance_policies WHERE id=?", (build_row["balance_policy_id"],)
        ).fetchone()
        targets = loads_json(balance_row["domain_targets_json"], default={})
        if not targets:
            return "not_evaluated"
        from core_model.corpus.balancing import compare_to_targets, compute_actual_distribution

        for member in included:
            domain_row = connection.execute(
                "SELECT primary_domain FROM corpus_domain_assessments WHERE segment_id=? "
                "ORDER BY id DESC LIMIT 1",
                (member["segment_id"],),
            ).fetchone()
            member["domain"] = domain_row["primary_domain"] if domain_row else "general"
        actual = compute_actual_distribution(included, key="domain")
        report = compare_to_targets(actual, {k: tuple(v) for k, v in targets.items()})
        if any(
            item["status"] in ("overrepresented", "underrepresented")
            for item in report.values()
        ):
            return "warning"
        return "pass"

    def _check_partition_integrity(
        self, connection, build_row, included, hard_failure_reasons: list[str]
    ) -> str:
        partitions = self.repository.partitions_for_build(connection, build_row["id"])
        if not partitions:
            return "not_evaluated"
        assignment: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
        for member in included:
            if not member.get("split"):
                continue
            segment_row = connection.execute(
                "SELECT public_id FROM corpus_segments WHERE id=?", (member["segment_id"],)
            ).fetchone()
            assignment[member["split"]].append(segment_row["public_id"])

        clusters: list[list[str]] = []
        seen_clusters: dict[int, list[str]] = {}
        for member in included:
            cluster_row = connection.execute(
                """SELECT c.id AS cluster_id FROM corpus_duplicate_members m
                JOIN corpus_duplicate_clusters c ON c.id = m.cluster_id
                WHERE m.segment_id=? ORDER BY m.id DESC LIMIT 1""",
                (member["segment_id"],),
            ).fetchone()
            if cluster_row is None:
                continue
            segment_row = connection.execute(
                "SELECT public_id FROM corpus_segments WHERE id=?", (member["segment_id"],)
            ).fetchone()
            seen_clusters.setdefault(cluster_row["cluster_id"], []).append(segment_row["public_id"])
        clusters = [ids for ids in seen_clusters.values() if len(ids) > 1]

        isolation = verify_partition_isolation(assignment, duplicate_clusters=clusters)
        if not isolation["isolated"]:
            hard_failure_reasons.append("duplicate_leakage_across_partitions")
            return "fail"
        return "pass"

    def _check_tokenizer_compatibility(self, connection, tokenizer_analysis_id: int | None) -> str:
        if tokenizer_analysis_id is None:
            return "not_evaluated"
        row = connection.execute(
            "SELECT unknown_token_rate, long_sequence_rate FROM corpus_tokenizer_analyses "
            "WHERE id=?",
            (tokenizer_analysis_id,),
        ).fetchone()
        if row is None or row["unknown_token_rate"] is None:
            return "not_evaluated"
        if row["unknown_token_rate"] > 0.1 or (row["long_sequence_rate"] or 0) > 0.2:
            return "warning"
        return "pass"

    def _check_manifest(self, connection, build_row, hard_failure_reasons: list[str]) -> str:
        version_row = connection.execute(
            "SELECT * FROM corpus_versions WHERE build_id=? ORDER BY id DESC LIMIT 1",
            (build_row["id"],),
        ).fetchone()
        if version_row is None or version_row["manifest_checksum_sha256"] is None:
            return "not_evaluated"
        manifest_row = connection.execute(
            "SELECT * FROM corpus_manifests WHERE corpus_version_id=? ORDER BY id DESC LIMIT 1",
            (version_row["id"],),
        ).fetchone()
        if manifest_row is None:
            return "not_evaluated"
        if not verify_manifest_checksum(
            manifest_row["manifest_json"], manifest_row["manifest_checksum_sha256"]
        ):
            hard_failure_reasons.append("failed_manifest_verification")
            return "fail"
        return "pass"

    def _check_export(self, connection, build_row, hard_failure_reasons: list[str]) -> str:
        version_row = connection.execute(
            "SELECT * FROM corpus_versions WHERE build_id=? ORDER BY id DESC LIMIT 1",
            (build_row["id"],),
        ).fetchone()
        if version_row is None:
            return "not_evaluated"
        export_row = connection.execute(
            "SELECT * FROM corpus_exports WHERE corpus_version_id=? ORDER BY id DESC LIMIT 1",
            (version_row["id"],),
        ).fetchone()
        if export_row is None:
            return "not_evaluated"
        if export_row["status"] not in {"completed", "completed_with_warnings"}:
            hard_failure_reasons.append("corrupt_export")
            return "fail"
        shards = connection.execute(
            "SELECT COUNT(*) FROM corpus_export_shards "
            "WHERE export_id=? AND checksum_sha256 IS NULL",
            (export_row["id"],),
        ).fetchone()
        if shards[0] > 0:
            hard_failure_reasons.append("corrupt_export")
            return "fail"
        return "pass" if export_row["status"] == "completed" else "warning"

    # --- read -----------------------------------------------------

    def _detail(self, connection, public_id: str) -> dict[str, Any]:
        row = self.repository.readiness_evaluation(connection, public_id)
        result = public_row(row)
        result["dimensions"] = [
            public_row(dim)
            for dim in self.repository.dimensions_for_readiness_evaluation(connection, row["id"])
        ]
        return result

    def get_evaluation(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return self._detail(connection, public_id)

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
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "corpus", resource_id, "success", dumps_json(metadata),
            ),
        )
