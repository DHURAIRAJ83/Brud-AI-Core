"""Repository for Phase 19 corpus policies, source registry, licences,
snapshots/files, extraction/normalization runs, segments, language/
domain/style assessments, quality/privacy/safety findings,
deduplication/contamination runs, collections, balance policies,
builds, partitions, versions, exports, manifests, and comparisons."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import NotFoundError

INTERNAL = {
    "id",
    "corpus_policy_id",
    "source_id",
    "snapshot_id",
    "extraction_run_id",
    "source_file_id",
    "normalization_run_id",
    "extracted_document_id",
    "normalized_document_id",
    "segment_id",
    "deduplication_run_id",
    "cluster_id",
    "contamination_run_id",
    "collection_id",
    "balance_policy_id",
    "build_id",
    "corpus_version_id",
    "export_id",
    "left_version_id",
    "right_version_id",
    "quality_assessment_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("corpus row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class CorpusRepository:
    def __init__(self, database_path) -> None:
        self.database_path = database_path

    def transaction(self):
        from backend.database.repositories.base import BaseRepository

        return BaseRepository(self.database_path).transaction()

    # --- policies -----------------------------------------------------

    def create_policy(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_policies(public_id,name,description,supported_languages_json,
            allowed_source_types_json,allowed_licence_statuses_json,require_verified_origin,
            require_licence_review,require_privacy_scan,require_safety_scan,
            require_quality_assessment,require_deduplication,require_contamination_check,
            maximum_source_bytes,maximum_document_characters,maximum_segment_characters,
            minimum_segment_characters,default_retention_seconds,export_format_policy_json,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("description", ""),
                values.get("supported_languages_json", '["ta","en","tgl","mixed"]'),
                values.get("allowed_source_types_json", "[]"),
                values.get(
                    "allowed_licence_statuses_json", '["approved","approved_with_conditions"]'
                ),
                1 if values.get("require_verified_origin", True) else 0,
                1 if values.get("require_licence_review", True) else 0,
                1 if values.get("require_privacy_scan", True) else 0,
                1 if values.get("require_safety_scan", True) else 0,
                1 if values.get("require_quality_assessment", True) else 0,
                1 if values.get("require_deduplication", True) else 0,
                1 if values.get("require_contamination_check", True) else 0,
                values.get("maximum_source_bytes", 200_000_000),
                values.get("maximum_document_characters", 2_000_000),
                values.get("maximum_segment_characters", 8000),
                values.get("minimum_segment_characters", 100),
                values.get("default_retention_seconds", 31_536_000),
                values.get("export_format_policy_json", '{"formats":["jsonl"]}'),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def policy(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_policies WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus policy not found")
        return row

    def list_policies(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_policies ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_policy(
        self, connection: sqlite3.Connection, policy_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_policies SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), policy_id),
        )

    # --- source registry -----------------------------------------------------

    def create_source(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_source_registries(public_id,corpus_policy_id,title,source_type,
            author_or_organisation,publisher,original_publication_date,source_reference,language,
            domain,ownership_claim,origin_reference_public_id,intended_use,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["corpus_policy_id"],
                values["title"],
                values["source_type"],
                values.get("author_or_organisation"),
                values.get("publisher"),
                values.get("original_publication_date"),
                values.get("source_reference", ""),
                values.get("language", "unknown"),
                values.get("domain", "general"),
                values.get("ownership_claim", "unknown"),
                values.get("origin_reference_public_id"),
                values.get("intended_use", "pretraining_corpus"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def source(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT s.*, p.public_id AS corpus_policy_public_id
            FROM corpus_source_registries s JOIN corpus_policies p ON p.id=s.corpus_policy_id
            WHERE s.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("corpus source not found")
        return row

    def list_sources(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_source_registries ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_source(
        self, connection: sqlite3.Connection, source_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_source_registries SET {columns}, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=?",
            (*fields.values(), source_id),
        )

    # --- source licences -----------------------------------------------------

    def create_licence(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_source_licences(public_id,source_id,licence_family,
            licence_name,licence_version,licence_text_reference,copyright_holder,
            allowed_uses_json,prohibited_uses_json,attribution_required,share_alike_required,
            commercial_use_permitted,modification_permitted,ai_training_permitted,
            redistribution_permitted,evidence_type,review_status,valid_from,expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["source_id"],
                values["licence_family"],
                values.get("licence_name"),
                values.get("licence_version"),
                values.get("licence_text_reference"),
                values.get("copyright_holder"),
                values.get("allowed_uses_json", "[]"),
                values.get("prohibited_uses_json", "[]"),
                1 if values.get("attribution_required") else 0,
                1 if values.get("share_alike_required") else 0,
                1 if values.get("commercial_use_permitted") else 0,
                1 if values.get("modification_permitted") else 0,
                1 if values.get("ai_training_permitted") else 0,
                1 if values.get("redistribution_permitted") else 0,
                values.get("evidence_type", "admin_asserted"),
                values.get("review_status", "unknown"),
                values.get("valid_from"),
                values.get("expires_at"),
            ),
        )
        return public_id

    def licence(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_source_licences WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus licence not found")
        return row

    def latest_licence_for_source(
        self, connection: sqlite3.Connection, source_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM corpus_source_licences WHERE source_id=?
            ORDER BY created_at DESC, id DESC LIMIT 1""",
            (source_id,),
        ).fetchone()

    def list_licences(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_source_licences ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_licence(
        self, connection: sqlite3.Connection, licence_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_source_licences SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), licence_id),
        )

    # --- snapshots -----------------------------------------------------

    def create_snapshot(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        next_version = connection.execute(
            """SELECT COALESCE(MAX(version_number),0)+1 FROM corpus_source_snapshots
            WHERE source_id=?""",
            (values["source_id"],),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_source_snapshots(public_id,source_id,version_number,
            source_checksum_sha256,file_inventory_checksum_sha256,total_bytes,total_files,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["source_id"],
                next_version,
                values["source_checksum_sha256"],
                values["file_inventory_checksum_sha256"],
                values.get("total_bytes", 0),
                values.get("total_files", 0),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def snapshot(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT sn.*, s.public_id AS source_public_id
            FROM corpus_source_snapshots sn JOIN corpus_source_registries s ON s.id=sn.source_id
            WHERE sn.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("corpus snapshot not found")
        return row

    def snapshots_for_source(
        self, connection: sqlite3.Connection, source_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_source_snapshots WHERE source_id=? ORDER BY version_number DESC",
            (source_id,),
        ).fetchall()

    def update_snapshot(
        self, connection: sqlite3.Connection, snapshot_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_source_snapshots SET {columns} WHERE id=?",
            (*fields.values(), snapshot_id),
        )

    # --- source files -----------------------------------------------------

    def create_file(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_source_files(public_id,snapshot_id,logical_filename,
            safe_relative_storage_key,mime_type,size_bytes,checksum_sha256,page_count,
            character_estimate,extraction_eligible) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["snapshot_id"],
                values["logical_filename"],
                values["safe_relative_storage_key"],
                values["mime_type"],
                values["size_bytes"],
                values["checksum_sha256"],
                values.get("page_count"),
                values.get("character_estimate"),
                1 if values.get("extraction_eligible", True) else 0,
            ),
        )
        return public_id

    def file(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_source_files WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus source file not found")
        return row

    def files_for_snapshot(
        self, connection: sqlite3.Connection, snapshot_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_source_files WHERE snapshot_id=? ORDER BY id",
            (snapshot_id,),
        ).fetchall()

    def update_file(
        self, connection: sqlite3.Connection, file_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_source_files SET {columns} WHERE id=?", (*fields.values(), file_id)
        )

    # --- extraction runs -----------------------------------------------------

    def create_extraction_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_extraction_runs(public_id,snapshot_id,extraction_method,
            ocr_language_configuration,created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["snapshot_id"],
                values["extraction_method"],
                values.get("ocr_language_configuration", "tam+eng"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def extraction_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*, sn.public_id AS snapshot_public_id
            FROM corpus_extraction_runs r JOIN corpus_source_snapshots sn ON sn.id=r.snapshot_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("extraction run not found")
        return row

    def update_extraction_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_extraction_runs SET {columns} WHERE id=?", (*fields.values(), run_id)
        )

    def count_active_extraction_runs(self, connection: sqlite3.Connection) -> int:
        return connection.execute(
            "SELECT COUNT(*) FROM corpus_extraction_runs WHERE status='running'"
        ).fetchone()[0]

    # --- extracted documents -----------------------------------------------------

    def create_extracted_document(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_extracted_documents(public_id,extraction_run_id,
            source_file_id,document_sequence,raw_text,raw_text_checksum_sha256,
            page_or_section_range,extraction_confidence,ocr_used,language_estimate,
            character_count,issue_summary_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["extraction_run_id"],
                values["source_file_id"],
                values["document_sequence"],
                values.get("raw_text", ""),
                values["raw_text_checksum_sha256"],
                values.get("page_or_section_range"),
                values.get("extraction_confidence"),
                1 if values.get("ocr_used") else 0,
                values.get("language_estimate", "unknown"),
                values.get("character_count", 0),
                values.get("issue_summary_json", "[]"),
            ),
        )
        return public_id

    def extracted_document(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_extracted_documents WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("extracted document not found")
        return row

    def documents_for_extraction_run(
        self, connection: sqlite3.Connection, run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM corpus_extracted_documents WHERE extraction_run_id=?
            ORDER BY document_sequence""",
            (run_id,),
        ).fetchall()

    # --- normalization runs -----------------------------------------------------

    def create_normalization_run(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_normalization_runs(public_id,extraction_run_id,
            normalization_version,created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                public_id,
                values["extraction_run_id"],
                values.get("normalization_version", "v1"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def normalization_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*, e.public_id AS extraction_run_public_id
            FROM corpus_normalization_runs r
            JOIN corpus_extraction_runs e ON e.id=r.extraction_run_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("normalization run not found")
        return row

    def update_normalization_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_normalization_runs SET {columns} WHERE id=?", (*fields.values(), run_id)
        )

    def count_active_normalization_runs(self, connection: sqlite3.Connection) -> int:
        return connection.execute(
            "SELECT COUNT(*) FROM corpus_normalization_runs WHERE status='running'"
        ).fetchone()[0]

    # --- normalized documents -----------------------------------------------------

    def create_normalized_document(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_normalized_documents(public_id,normalization_run_id,
            extracted_document_id,normalized_text,normalized_text_checksum_sha256,
            unicode_integrity_status,ocr_corrections_applied,boilerplate_removals_applied,
            transformation_counts_json) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["normalization_run_id"],
                values["extracted_document_id"],
                values.get("normalized_text", ""),
                values["normalized_text_checksum_sha256"],
                values.get("unicode_integrity_status", "unknown"),
                values.get("ocr_corrections_applied", 0),
                values.get("boilerplate_removals_applied", 0),
                values.get("transformation_counts_json", "{}"),
            ),
        )
        return public_id

    def normalized_document(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_normalized_documents WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("normalized document not found")
        return row

    def documents_for_normalization_run(
        self, connection: sqlite3.Connection, run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_normalized_documents WHERE normalization_run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()

    # --- segments -----------------------------------------------------

    def create_segment(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_segments(public_id,normalized_document_id,sequence_number,
            segmentation_strategy,heading_hierarchy_json,text,text_checksum_sha256,
            character_count,sentence_count,token_estimate) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["normalized_document_id"],
                values["sequence_number"],
                values["segmentation_strategy"],
                values.get("heading_hierarchy_json", "[]"),
                values["text"],
                values["text_checksum_sha256"],
                values["character_count"],
                values.get("sentence_count", 0),
                values.get("token_estimate", 0),
            ),
        )
        return public_id

    def segment(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_segments WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus segment not found")
        return row

    def segments_for_normalization_run(
        self, connection: sqlite3.Connection, normalization_run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT seg.* FROM corpus_segments seg
            JOIN corpus_normalized_documents nd ON nd.id = seg.normalized_document_id
            WHERE nd.normalization_run_id=? ORDER BY nd.id, seg.sequence_number""",
            (normalization_run_id,),
        ).fetchall()

    def list_all_segments(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute("SELECT * FROM corpus_segments ORDER BY id").fetchall()

    # --- language/domain/style assessments -----------------------------------------------------

    def record_language_assessment(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_language_assessments(public_id,segment_id,language_category,
            tamil_script_ratio,latin_script_ratio,digit_ratio,symbol_ratio,tamil_lexical_evidence,
            tanglish_lexical_evidence,mixed_language_evidence,confidence,
            unsupported_character_ratio) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["segment_id"],
                values["language_category"],
                values.get("tamil_script_ratio", 0),
                values.get("latin_script_ratio", 0),
                values.get("digit_ratio", 0),
                values.get("symbol_ratio", 0),
                values.get("tamil_lexical_evidence", 0),
                values.get("tanglish_lexical_evidence", 0),
                values.get("mixed_language_evidence", 0),
                values.get("confidence", 0),
                values.get("unsupported_character_ratio", 0),
            ),
        )
        return public_id

    def record_domain_assessment(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_domain_assessments(public_id,segment_id,primary_domain,
            secondary_domains_json,rule_evidence_json,confidence,classifier_version)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["segment_id"],
                values["primary_domain"],
                values.get("secondary_domains_json", "[]"),
                values.get("rule_evidence_json", "{}"),
                values.get("confidence", 0),
                values.get("classifier_version", "v1"),
            ),
        )
        return public_id

    def record_style_assessment(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_style_assessments(public_id,segment_id,style,confidence,
            classifier_version) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["segment_id"],
                values["style"],
                values.get("confidence", 0),
                values.get("classifier_version", "v1"),
            ),
        )
        return public_id

    def assessments_for_segment(
        self, connection: sqlite3.Connection, segment_id: int
    ) -> dict[str, Any]:
        language = connection.execute(
            "SELECT * FROM corpus_language_assessments WHERE segment_id=? ORDER BY id DESC LIMIT 1",
            (segment_id,),
        ).fetchone()
        domain = connection.execute(
            "SELECT * FROM corpus_domain_assessments WHERE segment_id=? ORDER BY id DESC LIMIT 1",
            (segment_id,),
        ).fetchone()
        style = connection.execute(
            "SELECT * FROM corpus_style_assessments WHERE segment_id=? ORDER BY id DESC LIMIT 1",
            (segment_id,),
        ).fetchone()
        return {"language": language, "domain": domain, "style": style}

    # --- quality assessments -----------------------------------------------------

    def record_quality_assessment(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_quality_assessments(public_id,subject_type,
            subject_reference_public_id,dimension,status,score,details_json)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["subject_type"],
                values["subject_reference_public_id"],
                values["dimension"],
                values.get("status", "not_assessed"),
                values.get("score"),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def quality_assessment(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_quality_assessments WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("quality assessment not found")
        return row

    def quality_assessments_for_subject(
        self, connection: sqlite3.Connection, subject_type: str, subject_reference_public_id: str
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM corpus_quality_assessments WHERE subject_type=?
            AND subject_reference_public_id=? ORDER BY id""",
            (subject_type, subject_reference_public_id),
        ).fetchall()

    def record_quality_issue(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_quality_issues(public_id,quality_assessment_id,issue_code,
            severity,details_json) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["quality_assessment_id"],
                values["issue_code"],
                values.get("severity", "medium"),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def issues_for_assessment(
        self, connection: sqlite3.Connection, assessment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_quality_issues WHERE quality_assessment_id=? ORDER BY id",
            (assessment_id,),
        ).fetchall()

    # --- privacy/safety findings -----------------------------------------------------

    def record_privacy_finding(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_privacy_findings(public_id,segment_id,category,status,
            redaction_action,finding_count,detector_version,details_json)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values.get("segment_id"),
                values["category"],
                values["status"],
                values.get("redaction_action"),
                values.get("finding_count", 1),
                values.get("detector_version", "v1"),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def record_safety_finding(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_safety_findings(public_id,segment_id,category,
            behavior_class,status,detector_version,details_json) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values.get("segment_id"),
                values["category"],
                values.get("behavior_class", "descriptive"),
                values["status"],
                values.get("detector_version", "v1"),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def findings_for_segment(
        self, connection: sqlite3.Connection, segment_id: int
    ) -> dict[str, Any]:
        privacy = connection.execute(
            "SELECT * FROM corpus_privacy_findings WHERE segment_id=? ORDER BY id", (segment_id,)
        ).fetchall()
        safety = connection.execute(
            "SELECT * FROM corpus_safety_findings WHERE segment_id=? ORDER BY id", (segment_id,)
        ).fetchall()
        return {"privacy": privacy, "safety": safety}

    # --- deduplication -----------------------------------------------------

    def create_deduplication_run(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_deduplication_runs(public_id,scope_description,
            near_duplicate_method,near_duplicate_threshold,created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            (
                public_id,
                values.get("scope_description", ""),
                values.get("near_duplicate_method", "character_ngram_jaccard"),
                values.get("near_duplicate_threshold", 0.85),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def deduplication_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_deduplication_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("deduplication run not found")
        return row

    def update_deduplication_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_deduplication_runs SET {columns} WHERE id=?", (*fields.values(), run_id)
        )

    def count_active_deduplication_runs(self, connection: sqlite3.Connection) -> int:
        return connection.execute(
            "SELECT COUNT(*) FROM corpus_deduplication_runs WHERE status='running'"
        ).fetchone()[0]

    def create_duplicate_cluster(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_duplicate_clusters(public_id,deduplication_run_id,cluster_type,
            representative_segment_public_id,representative_selection_reason,member_count,action)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["deduplication_run_id"],
                values["cluster_type"],
                values["representative_segment_public_id"],
                values.get("representative_selection_reason", ""),
                values.get("member_count", 0),
                values.get("action", "keep_representative"),
            ),
        )
        return public_id

    def duplicate_cluster(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_duplicate_clusters WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("duplicate cluster not found")
        return row

    def clusters_for_run(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_duplicate_clusters WHERE deduplication_run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()

    def create_duplicate_member(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_duplicate_members(public_id,cluster_id,segment_id,
            similarity_score,is_representative) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["cluster_id"],
                values["segment_id"],
                values.get("similarity_score", 1.0),
                1 if values.get("is_representative") else 0,
            ),
        )
        return public_id

    def members_for_cluster(
        self, connection: sqlite3.Connection, cluster_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_duplicate_members WHERE cluster_id=? ORDER BY id", (cluster_id,)
        ).fetchall()

    # --- contamination -----------------------------------------------------

    def create_contamination_run(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_contamination_runs(public_id,scope_description,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (public_id, values.get("scope_description", ""), values["created_by_admin_public_id"]),
        )
        return public_id

    def contamination_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_contamination_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("contamination run not found")
        return row

    def update_contamination_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_contamination_runs SET {columns} WHERE id=?", (*fields.values(), run_id)
        )

    def record_contamination_finding(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_contamination_findings(public_id,contamination_run_id,
            segment_id,issue_type,matched_reference,blocks_training) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["contamination_run_id"],
                values["segment_id"],
                values["issue_type"],
                values.get("matched_reference"),
                1 if values.get("blocks_training", True) else 0,
            ),
        )
        return public_id

    def findings_for_contamination_run(
        self, connection: sqlite3.Connection, run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_contamination_findings WHERE contamination_run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()

    # --- collections -----------------------------------------------------

    def create_collection(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_collections(public_id,name,description,intended_use,
            language_policy_json,domain_policy_json,style_policy_json,licence_policy_json,
            quality_policy_json,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("description", ""),
                values.get("intended_use", "pretraining_corpus"),
                values.get("language_policy_json", "{}"),
                values.get("domain_policy_json", "{}"),
                values.get("style_policy_json", "{}"),
                values.get("licence_policy_json", "{}"),
                values.get("quality_policy_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def collection(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_collections WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus collection not found")
        return row

    def list_collections(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_collections ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_collection(
        self, connection: sqlite3.Connection, collection_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_collections SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), collection_id),
        )

    def create_collection_member(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_collection_members(public_id,collection_id,segment_id,
            eligibility_status,inclusion_reason,exclusion_reason,licence_status,quality_status,
            duplicate_status,contamination_status) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["collection_id"],
                values["segment_id"],
                values.get("eligibility_status", "eligible"),
                values.get("inclusion_reason", ""),
                values.get("exclusion_reason"),
                values.get("licence_status", "unknown"),
                values.get("quality_status", "not_assessed"),
                values.get("duplicate_status", "unique"),
                values.get("contamination_status", "clean"),
            ),
        )
        return public_id

    def members_for_collection(
        self, connection: sqlite3.Connection, collection_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_collection_members WHERE collection_id=? ORDER BY id",
            (collection_id,),
        ).fetchall()

    # --- balance policies -----------------------------------------------------

    def create_balance_policy(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_balance_policies(public_id,name,description,
            language_targets_json,domain_targets_json,style_targets_json,
            source_type_targets_json,licence_family_targets_json,content_length_targets_json,
            quality_band_targets_json,maximum_single_source_share,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values.get("description", ""),
                values.get("language_targets_json", "{}"),
                values.get("domain_targets_json", "{}"),
                values.get("style_targets_json", "{}"),
                values.get("source_type_targets_json", "{}"),
                values.get("licence_family_targets_json", "{}"),
                values.get("content_length_targets_json", "{}"),
                values.get("quality_band_targets_json", "{}"),
                values.get("maximum_single_source_share", 0.3),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def balance_policy(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_balance_policies WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("balance policy not found")
        return row

    def list_balance_policies(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_balance_policies ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_balance_policy(
        self, connection: sqlite3.Connection, policy_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_balance_policies SET {columns}, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=?",
            (*fields.values(), policy_id),
        )

    # --- builds -----------------------------------------------------

    def create_build(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_builds(public_id,corpus_policy_id,balance_policy_id,
            deduplication_run_id,contamination_run_id,collection_ids_json,
            partition_configuration_json,export_policy_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["corpus_policy_id"],
                values["balance_policy_id"],
                values.get("deduplication_run_id"),
                values.get("contamination_run_id"),
                values.get("collection_ids_json", "[]"),
                values.get("partition_configuration_json", "{}"),
                values.get("export_policy_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def build(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_builds WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus build not found")
        return row

    def list_builds(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_builds ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_build(
        self, connection: sqlite3.Connection, build_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_builds SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), build_id),
        )

    def count_active_builds(self, connection: sqlite3.Connection) -> int:
        return connection.execute(
            "SELECT COUNT(*) FROM corpus_builds WHERE status IN ('validating','building')"
        ).fetchone()[0]

    def create_build_member(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_build_members(public_id,build_id,segment_id,collection_id,
            selection_rank,balance_bucket,inclusion_weight,included,exclusion_reason,
            final_quality_band,final_licence_decision,split) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["build_id"],
                values["segment_id"],
                values["collection_id"],
                values.get("selection_rank", 0),
                values.get("balance_bucket", ""),
                values.get("inclusion_weight", 1.0),
                1 if values.get("included", True) else 0,
                values.get("exclusion_reason"),
                values.get("final_quality_band", "unassessed"),
                values.get("final_licence_decision", "unknown"),
                values.get("split"),
            ),
        )
        return public_id

    def members_for_build(self, connection: sqlite3.Connection, build_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_build_members WHERE build_id=? ORDER BY id", (build_id,)
        ).fetchall()

    def create_partition(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_partitions(public_id,build_id,split,segment_count,seed,
            checksum_sha256,holdout_evidence_json) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["build_id"],
                values["split"],
                values.get("segment_count", 0),
                values.get("seed", 42),
                values["checksum_sha256"],
                values.get("holdout_evidence_json", "{}"),
            ),
        )
        return public_id

    def partitions_for_build(
        self, connection: sqlite3.Connection, build_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_partitions WHERE build_id=? ORDER BY split", (build_id,)
        ).fetchall()

    # --- versions -----------------------------------------------------

    def create_version(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_versions(public_id,build_id,semantic_version,
            train_segment_count,validation_segment_count,test_segment_count,
            language_distribution_json,domain_distribution_json,style_distribution_json,
            source_distribution_json,licence_distribution_json,total_characters,
            estimated_tokens,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["build_id"],
                values["semantic_version"],
                values.get("train_segment_count", 0),
                values.get("validation_segment_count", 0),
                values.get("test_segment_count", 0),
                values.get("language_distribution_json", "{}"),
                values.get("domain_distribution_json", "{}"),
                values.get("style_distribution_json", "{}"),
                values.get("source_distribution_json", "{}"),
                values.get("licence_distribution_json", "{}"),
                values.get("total_characters", 0),
                values.get("estimated_tokens", 0),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_versions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus version not found")
        return row

    def list_versions(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_versions ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def update_version(
        self, connection: sqlite3.Connection, version_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_versions SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), version_id),
        )

    # --- exports -----------------------------------------------------

    def create_export(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_exports(public_id,corpus_version_id,export_format,
            shard_max_bytes,created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["corpus_version_id"],
                values.get("export_format", "jsonl"),
                values.get("shard_max_bytes", 50_000_000),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def export(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_exports WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus export not found")
        return row

    def update_export(
        self, connection: sqlite3.Connection, export_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE corpus_exports SET {columns} WHERE id=?", (*fields.values(), export_id)
        )

    def create_export_shard(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_export_shards(public_id,export_id,split,shard_number,
            record_count,total_characters,estimated_tokens,relative_storage_key,
            file_size_bytes,checksum_sha256) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["export_id"],
                values["split"],
                values["shard_number"],
                values.get("record_count", 0),
                values.get("total_characters", 0),
                values.get("estimated_tokens", 0),
                values["relative_storage_key"],
                values.get("file_size_bytes", 0),
                values["checksum_sha256"],
            ),
        )
        return public_id

    def shards_for_export(
        self, connection: sqlite3.Connection, export_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM corpus_export_shards WHERE export_id=? ORDER BY split, shard_number",
            (export_id,),
        ).fetchall()

    # --- manifests -----------------------------------------------------

    def create_manifest(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_manifests(public_id,corpus_version_id,manifest_json,
            manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (
                public_id,
                values["corpus_version_id"],
                values["manifest_json"],
                values["manifest_checksum_sha256"],
            ),
        )
        return public_id

    def latest_manifest_for_version(
        self, connection: sqlite3.Connection, version_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM corpus_manifests WHERE corpus_version_id=?
            ORDER BY created_at DESC, id DESC LIMIT 1""",
            (version_id,),
        ).fetchone()

    # --- comparisons -----------------------------------------------------

    def create_comparison(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO corpus_comparisons(public_id,left_version_id,right_version_id,
            compatibility,comparison_json,created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["left_version_id"],
                values["right_version_id"],
                values["compatibility"],
                values.get("comparison_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def comparison(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM corpus_comparisons WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("corpus comparison not found")
        return row
