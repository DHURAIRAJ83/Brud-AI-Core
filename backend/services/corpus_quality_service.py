"""Phase 19 language/domain/style assessment, privacy/safety findings,
quality scoring, deduplication, and contamination checking.

Personal information is policy-controlled (redact/quarantine/block);
genuine secrets and credentials are always blocked outright, with no
policy override -- the two are always recorded as distinct finding
categories, never merged into one undifferentiated "sensitive content"
bucket.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.models.corpus import ContaminationRunCreate, DeduplicationRunCreate
from core_model.corpus.contamination import check_contamination
from core_model.corpus.domain_classification import classify_domain
from core_model.corpus.exact_deduplication import all_checksums, tamil_safe_normalized_checksum
from core_model.corpus.language_detection import assess_language
from core_model.corpus.near_deduplication import (
    classify_near_duplicate,
    compute_similarity,
    select_representative,
)
from core_model.corpus.pii_detection import decide_pii_action, detect_pii
from core_model.corpus.provenance import provenance_completeness
from core_model.corpus.quality_scoring import (
    QUALITY_DIMENSIONS,
    assess_segment_quality,
    build_quality_details,
    overall_verdict,
    quality_band,
)
from core_model.corpus.safety_filter import assess_safety
from core_model.corpus.secret_detection import detect_secrets
from core_model.corpus.style_classification import classify_style
from core_model.corpus.unicode_normalization import tamil_combining_marks_preserved

_PRIVACY_STATUS_BY_ACTION = {
    "redact": "redacted",
    "quarantine": "requires_review",
    "block": "blocked",
}


class CorpusQualityService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- segment provenance chain -----------------------------------------------------

    def _segment_chain(self, connection, segment_row) -> dict[str, Any]:
        normalized_document = self.repository.normalized_document(
            connection,
            connection.execute(
                "SELECT public_id FROM corpus_normalized_documents WHERE id=?",
                (segment_row["normalized_document_id"],),
            ).fetchone()["public_id"],
        )
        extracted_document = self.repository.extracted_document(
            connection,
            connection.execute(
                "SELECT public_id FROM corpus_extracted_documents WHERE id=?",
                (normalized_document["extracted_document_id"],),
            ).fetchone()["public_id"],
        )
        file_row = self.repository.file(
            connection,
            connection.execute(
                "SELECT public_id FROM corpus_source_files WHERE id=?",
                (extracted_document["source_file_id"],),
            ).fetchone()["public_id"],
        )
        snapshot_row = self.repository.snapshot(
            connection,
            connection.execute(
                "SELECT public_id FROM corpus_source_snapshots WHERE id=?",
                (file_row["snapshot_id"],),
            ).fetchone()["public_id"],
        )
        source_row = self.repository.source(connection, snapshot_row["source_public_id"])
        licence_row = self.repository.latest_licence_for_source(connection, source_row["id"])
        policy_row = self.repository.policy(connection, source_row["corpus_policy_public_id"])
        return {
            "normalized_document": normalized_document,
            "extracted_document": extracted_document,
            "file": file_row,
            "snapshot": snapshot_row,
            "source": source_row,
            "licence": licence_row,
            "policy": policy_row,
        }

    def _duplicate_status_for_segment(self, connection, segment_public_id: str) -> str:
        row = connection.execute(
            """SELECT c.cluster_type FROM corpus_duplicate_members m
            JOIN corpus_segments s ON s.id = m.segment_id
            JOIN corpus_duplicate_clusters c ON c.id = m.cluster_id
            WHERE s.public_id=? ORDER BY m.id DESC LIMIT 1""",
            (segment_public_id,),
        ).fetchone()
        return row["cluster_type"] if row else "unique"

    # --- assessment -----------------------------------------------------

    def assess_segment(self, segment_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            segment_row = self.repository.segment(connection, segment_public_id)
            text = segment_row["text"]
            chain = self._segment_chain(connection, segment_row)

            language = assess_language(text)
            self.repository.record_language_assessment(
                connection, {"segment_id": segment_row["id"], **language}
            )
            domain = classify_domain(text)
            self.repository.record_domain_assessment(
                connection,
                {
                    "segment_id": segment_row["id"],
                    "primary_domain": domain["primary_domain"],
                    "secondary_domains_json": dumps_json(domain["secondary_domains"]),
                    "rule_evidence_json": dumps_json(domain["rule_evidence"]),
                    "confidence": domain["confidence"],
                    "classifier_version": domain["classifier_version"],
                },
            )
            style = classify_style(text)
            self.repository.record_style_assessment(
                connection, {"segment_id": segment_row["id"], **style}
            )

            privacy_status = self._assess_privacy(connection, segment_row, text)
            safety_status = self._assess_safety(connection, segment_row, text)

            provenance_record = {
                "source_public_id": chain["source"]["public_id"],
                "collection_method": "corpus_extraction_pipeline",
                "ingestion_date": chain["snapshot"]["created_at"],
                "original_checksum_sha256": chain["file"]["checksum_sha256"],
                "snapshot_checksum_sha256": chain["snapshot"]["file_inventory_checksum_sha256"],
            }
            provenance_complete, missing_fields = provenance_completeness(provenance_record)

            licence_status = chain["licence"]["review_status"] if chain["licence"] else "unknown"
            duplicate_status = self._duplicate_status_for_segment(connection, segment_public_id)
            combining_marks_preserved = tamil_combining_marks_preserved(
                chain["extracted_document"]["raw_text"],
                chain["normalized_document"]["normalized_text"],
            )

            dimension_results = assess_segment_quality(
                unicode_integrity_status=chain["normalized_document"]["unicode_integrity_status"],
                tamil_combining_marks_preserved=combining_marks_preserved,
                ocr_corrections_applied=chain["normalized_document"]["ocr_corrections_applied"],
                character_count=segment_row["character_count"],
                sentence_count=segment_row["sentence_count"],
                language_confidence=language["confidence"],
                boilerplate_removed_ratio=(
                    chain["normalized_document"]["boilerplate_removals_applied"]
                    / max(1, segment_row["character_count"] // 200)
                ),
                duplicate_status="unique" if duplicate_status == "unique" else "duplicate",
                privacy_status=privacy_status,
                safety_status=safety_status,
                licence_status=licence_status,
                provenance_complete=provenance_complete,
                minimum_segment_characters=chain["policy"]["minimum_segment_characters"],
                maximum_ocr_noise_ratio=0.05,
                minimum_language_confidence=0.4,
            )

            assessment_public_ids = []
            for dimension in QUALITY_DIMENSIONS:
                status = dimension_results[dimension]
                assessment_public_id = self.repository.record_quality_assessment(
                    connection,
                    {
                        "subject_type": "segment",
                        "subject_reference_public_id": segment_public_id,
                        "dimension": dimension,
                        "status": status,
                        "details_json": dumps_json(build_quality_details({dimension: status})),
                    },
                )
                assessment_public_ids.append(assessment_public_id)
                if status == "fail" and dimension in {
                    "unicode_integrity",
                    "tamil_integrity",
                    "privacy_safety",
                    "safety_quality",
                    "provenance_completeness",
                }:
                    assessment_row = self.repository.quality_assessment(
                        connection, assessment_public_id
                    )
                    self.repository.record_quality_issue(
                        connection,
                        {
                            "quality_assessment_id": assessment_row["id"],
                            "issue_code": f"{dimension}_failed",
                            "severity": "high",
                            "details_json": dumps_json({"missing_fields": missing_fields})
                            if dimension == "provenance_completeness"
                            else "{}",
                        },
                    )

            verdict = overall_verdict(dimension_results)
            band = quality_band(dimension_results)
            self._audit(
                connection,
                "corpus_segment_assessed",
                admin_id,
                segment_public_id,
                verdict=verdict,
                band=band,
            )
            return {
                "segment_public_id": segment_public_id,
                "language": language,
                "domain": domain,
                "style": style,
                "privacy_status": privacy_status,
                "safety_status": safety_status,
                "licence_status": licence_status,
                "duplicate_status": duplicate_status,
                "provenance_complete": provenance_complete,
                "dimension_results": dimension_results,
                "overall_verdict": verdict,
                "quality_band": band,
            }

    def _assess_privacy(self, connection, segment_row, text: str) -> str:
        secrets = detect_secrets(text)
        if secrets["matched_categories"]:
            for category in secrets["matched_categories"]:
                self.repository.record_privacy_finding(
                    connection,
                    {
                        "segment_id": segment_row["id"],
                        "category": category,
                        "status": "blocked",
                        "redaction_action": "block",
                        "finding_count": 1,
                        "details_json": dumps_json({"kind": "secret_or_credential"}),
                    },
                )
            return "blocked"

        pii = detect_pii(text)
        if not pii["findings"]:
            return "safe"

        action = decide_pii_action(pii["findings"], policy_action="redact")
        status = _PRIVACY_STATUS_BY_ACTION.get(action, "requires_review")
        for category, count in pii["findings"].items():
            self.repository.record_privacy_finding(
                connection,
                {
                    "segment_id": segment_row["id"],
                    "category": category,
                    "status": status,
                    "redaction_action": action,
                    "finding_count": count,
                    "details_json": dumps_json({"kind": "personal_information"}),
                },
            )
        return status

    def _assess_safety(self, connection, segment_row, text: str) -> str:
        result = assess_safety(text)
        for finding in result["findings"]:
            self.repository.record_safety_finding(
                connection,
                {
                    "segment_id": segment_row["id"],
                    "category": finding["category"],
                    "behavior_class": finding["behavior_class"],
                    "status": "blocked"
                    if finding["behavior_class"] == "operational_harmful"
                    else "flagged",
                    "details_json": "{}",
                },
            )
        return result["status"]

    # --- deduplication -----------------------------------------------------

    def run_deduplication(self, payload: DeduplicationRunCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            if self.repository.count_active_deduplication_runs(connection) >= (
                self.settings.corpus_max_active_processing_runs
            ):
                raise ValidationError("too many corpus deduplication runs are currently active")

            values = payload.model_dump(mode="json")
            values["created_by_admin_public_id"] = admin_id
            run_public_id = self.repository.create_deduplication_run(connection, values)
            run_row = self.repository.deduplication_run(connection, run_public_id)
            self.repository.update_deduplication_run(
                connection, run_row["id"], {"status": "running"}
            )

            segments = self.repository.list_all_segments(connection)
            checksum_index: dict[str, list[dict[str, Any]]] = {}
            for segment in segments:
                checksums = all_checksums(segment["text"])
                checksum_index.setdefault(checksums["raw"], []).append(
                    {"segment": segment, "checksums": checksums}
                )

            exact_count, near_count = 0, 0
            clustered_segment_ids: set[int] = set()
            exact_cluster_representatives: list[dict[str, Any]] = []

            for group in checksum_index.values():
                if len(group) < 2:
                    continue
                candidates = [
                    {
                        "public_id": item["segment"]["public_id"],
                        "licence_status": "unknown",
                        "extraction_confidence": None,
                        "unicode_integrity_status": "unknown",
                        "ocr_corrections_applied": 0,
                        "provenance_complete": False,
                        "character_count": item["segment"]["character_count"],
                        "source_created_at": item["segment"]["created_at"],
                    }
                    for item in group
                ]
                representative = select_representative(candidates)
                cluster_public_id = self.repository.create_duplicate_cluster(
                    connection,
                    {
                        "deduplication_run_id": run_row["id"],
                        "cluster_type": "exact_duplicate",
                        "representative_segment_public_id": representative["public_id"],
                        "representative_selection_reason": "deterministic_priority_sort",
                        "member_count": len(group),
                        "action": "keep_representative",
                    },
                )
                cluster_row = self.repository.duplicate_cluster(connection, cluster_public_id)
                for item in group:
                    self.repository.create_duplicate_member(
                        connection,
                        {
                            "cluster_id": cluster_row["id"],
                            "segment_id": item["segment"]["id"],
                            "similarity_score": 1.0,
                            "is_representative": (
                                item["segment"]["public_id"] == representative["public_id"]
                            ),
                        },
                    )
                    clustered_segment_ids.add(item["segment"]["id"])
                exact_count += len(group) - 1
                exact_cluster_representatives.append(
                    next(
                        item["segment"] for item in group
                        if item["segment"]["public_id"] == representative["public_id"]
                    )
                )

            # Near-duplicate comparison runs over every segment not yet
            # exact-clustered, plus one representative per exact-duplicate
            # cluster -- an exact-duplicate group must still be reachable
            # as a near-duplicate of a third, non-identical variant.
            remaining = [
                s for s in segments if s["id"] not in clustered_segment_ids
            ] + exact_cluster_representatives
            near_duplicate_clustered_ids: set[int] = set()
            for index, segment_a in enumerate(remaining):
                if segment_a["id"] in near_duplicate_clustered_ids:
                    continue
                for segment_b in remaining[index + 1 :]:
                    if segment_b["id"] in near_duplicate_clustered_ids:
                        continue
                    similarity = compute_similarity(
                        segment_a["text"], segment_b["text"], method=payload.near_duplicate_method
                    )
                    classification = classify_near_duplicate(
                        similarity, threshold=payload.near_duplicate_threshold
                    )
                    if classification != "near_duplicate":
                        continue
                    representative = select_representative(
                        [
                            {
                                "public_id": segment_a["public_id"],
                                "character_count": segment_a["character_count"],
                                "source_created_at": segment_a["created_at"],
                            },
                            {
                                "public_id": segment_b["public_id"],
                                "character_count": segment_b["character_count"],
                                "source_created_at": segment_b["created_at"],
                            },
                        ]
                    )
                    cluster_public_id = self.repository.create_duplicate_cluster(
                        connection,
                        {
                            "deduplication_run_id": run_row["id"],
                            "cluster_type": "near_duplicate",
                            "representative_segment_public_id": representative["public_id"],
                            "representative_selection_reason": "deterministic_priority_sort",
                            "member_count": 2,
                            "action": "keep_representative",
                        },
                    )
                    cluster_row = self.repository.duplicate_cluster(connection, cluster_public_id)
                    for segment in (segment_a, segment_b):
                        self.repository.create_duplicate_member(
                            connection,
                            {
                                "cluster_id": cluster_row["id"],
                                "segment_id": segment["id"],
                                "similarity_score": similarity,
                                "is_representative": segment["public_id"]
                                == representative["public_id"],
                            },
                        )
                        near_duplicate_clustered_ids.add(segment["id"])
                    near_count += 1

            self.repository.update_deduplication_run(
                connection,
                run_row["id"],
                {
                    "status": "completed",
                    "segments_scanned": len(segments),
                    "exact_duplicate_count": exact_count,
                    "near_duplicate_count": near_count,
                },
            )
            self._audit(
                connection,
                "corpus_deduplication_run_completed",
                admin_id,
                run_public_id,
                exact_duplicate_count=exact_count,
                near_duplicate_count=near_count,
            )
            return public_row(self.repository.deduplication_run(connection, run_public_id))

    def get_deduplication_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.deduplication_run(connection, public_id)
            result = public_row(row)
            result["clusters"] = [
                public_row(cluster)
                for cluster in self.repository.clusters_for_run(connection, row["id"])
            ]
            return result

    # --- contamination -----------------------------------------------------

    def run_contamination_check(
        self, payload: ContaminationRunCreate, admin_id: str
    ) -> dict[str, Any]:
        test_checksums = frozenset(
            tamil_safe_normalized_checksum(text) for text in payload.test_fixture_texts
        )
        validation_checksums = frozenset(
            tamil_safe_normalized_checksum(text) for text in payload.validation_fixture_texts
        )
        evaluation_fixture_checksums = frozenset(
            tamil_safe_normalized_checksum(text) for text in payload.evaluation_fixture_texts
        )
        regression_fixture_checksums = frozenset(
            tamil_safe_normalized_checksum(text) for text in payload.regression_fixture_texts
        )
        holdout_checksums = frozenset(
            tamil_safe_normalized_checksum(text) for text in payload.holdout_fixture_texts
        )
        hidden_prompt_checksums = frozenset(
            tamil_safe_normalized_checksum(text) for text in payload.hidden_prompt_fixture_texts
        )

        with self.repository.transaction() as connection:
            values = {
                "scope_description": payload.scope_description,
                "created_by_admin_public_id": admin_id,
            }
            run_public_id = self.repository.create_contamination_run(connection, values)
            run_row = self.repository.contamination_run(connection, run_public_id)
            self.repository.update_contamination_run(
                connection, run_row["id"], {"status": "running"}
            )

            segments = self.repository.list_all_segments(connection)
            findings_count = 0
            for segment in segments:
                result = check_contamination(
                    segment_text=segment["text"],
                    test_checksums=test_checksums,
                    validation_checksums=validation_checksums,
                    evaluation_fixture_checksums=evaluation_fixture_checksums,
                    regression_fixture_checksums=regression_fixture_checksums,
                    holdout_checksums=holdout_checksums,
                    hidden_prompt_checksums=hidden_prompt_checksums,
                )
                for issue in result["issues"]:
                    self.repository.record_contamination_finding(
                        connection,
                        {
                            "contamination_run_id": run_row["id"],
                            "segment_id": segment["id"],
                            "issue_type": issue,
                            "matched_reference": None,
                            "blocks_training": issue in result["blocking_issues"],
                        },
                    )
                    findings_count += 1

            self.repository.update_contamination_run(
                connection,
                run_row["id"],
                {
                    "status": "completed",
                    "segments_scanned": len(segments),
                    "findings_count": findings_count,
                },
            )
            self._audit(
                connection,
                "corpus_contamination_run_completed",
                admin_id,
                run_public_id,
                findings_count=findings_count,
            )
            return public_row(self.repository.contamination_run(connection, run_public_id))

    def get_contamination_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.contamination_run(connection, public_id)
            result = public_row(row)
            result["findings"] = [
                public_row(finding)
                for finding in self.repository.findings_for_contamination_run(connection, row["id"])
            ]
            return result

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
