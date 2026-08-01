"""JSONL export of approved document SFT candidates, with a manifest and checksum.

Reuses `core_model.corpus.manifest.manifest_checksum`/`scan_for_sensitive_content`
(Phase 14's checksum/secret-scan implementation) unchanged -- no second checksum or
secret-scanning implementation. Exports only `quality_status='approved'` candidates;
`export_path` is always stored relative to `settings.resolved_document_sft_export_dir`,
never as an absolute filesystem path.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.documents import DocumentRepository
from backend.services.document_service import audit
from core_model.corpus.manifest import manifest_checksum, scan_for_sensitive_content


def _export_row(row: Any) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "record_count": row["record_count"],
        "excluded_count": row["excluded_count"],
        "task_distribution": loads_json(row["task_distribution_json"], default={}),
        "language_distribution": loads_json(row["language_distribution_json"], default={}),
        "domain_distribution": loads_json(row["domain_distribution_json"], default={}),
        "source_document_ids": loads_json(row["source_document_ids_json"], default=[]),
        "rights_summary": loads_json(row["rights_summary_json"], default={}),
        "quality_summary": loads_json(row["quality_summary_json"], default={}),
        "checksum_sha256": row["checksum_sha256"],
        "export_path": row["export_path"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


class DocumentSftExportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)

    def export(self, document_public_id: str, admin_id: str) -> dict[str, Any]:
        from backend.services.document_security_review_service import (
            DocumentSecurityReviewService,
        )

        security = DocumentSecurityReviewService(self.settings)
        if security.has_export_blocking_findings(document_public_id):
            raise ValidationError(
                "this document has unresolved security findings (secret or absolute-path "
                "content) that block export -- resolve them before exporting"
            )
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            approved = connection.execute(
                "SELECT * FROM document_sft_candidates WHERE document_source_id=? "
                "AND quality_status='approved' ORDER BY id",
                (document["id"],),
            ).fetchall()
            excluded = connection.execute(
                "SELECT COUNT(*) FROM document_sft_candidates WHERE document_source_id=? "
                "AND quality_status!='approved'",
                (document["id"],),
            ).fetchone()[0]
        if not approved:
            raise ValidationError("no approved SFT candidates are available to export")

        records: list[dict[str, Any]] = []
        task_distribution: dict[str, int] = {}
        language_distribution: dict[str, int] = {}
        domain_distribution: dict[str, int] = {}
        for row in approved:
            record = {
                "instruction": row["instruction"],
                "context": row["context"],
                "response": row["response"],
                "input_language": row["input_language"],
                "output_language": row["output_language"],
                "task": row["task"],
                "domain": row["domain"],
                "difficulty": row["difficulty"],
                "source_id": row["public_id"],
                "rights_status": row["rights_status"],
            }
            records.append(record)
            task_distribution[row["task"]] = task_distribution.get(row["task"], 0) + 1
            language_distribution[row["input_language"]] = (
                language_distribution.get(row["input_language"], 0) + 1
            )
            domain_distribution[row["domain"]] = domain_distribution.get(row["domain"], 0) + 1

        manifest_payload = {"records": records}
        concerns = scan_for_sensitive_content(manifest_payload)
        if concerns:
            raise ValidationError(
                f"export blocked by sensitive-content scan: {', '.join(concerns)}"
            )

        export_id = str(uuid4())
        export_dir = self.settings.resolved_document_sft_export_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        relative_filename = f"{export_id}.jsonl"
        jsonl_content = "\n".join(dumps_json(record) for record in records) + "\n"
        (export_dir / relative_filename).write_text(jsonl_content, encoding="utf-8")

        manifest = {
            "record_count": len(records),
            "excluded_count": excluded,
            "task_distribution": task_distribution,
            "language_distribution": language_distribution,
            "domain_distribution": domain_distribution,
            "source_document_ids": [document_public_id],
            "rights_summary": {"verified": len(records)},
            "quality_summary": {"approved": len(records)},
        }
        checksum = manifest_checksum(manifest)

        with self.repository.transaction() as connection:
            connection.execute(
                """INSERT INTO document_sft_exports(
                    public_id,record_count,excluded_count,task_distribution_json,
                    language_distribution_json,domain_distribution_json,
                    source_document_ids_json,rights_summary_json,quality_summary_json,
                    checksum_sha256,export_path,created_by
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    export_id,
                    len(records),
                    excluded,
                    dumps_json(task_distribution),
                    dumps_json(language_distribution),
                    dumps_json(domain_distribution),
                    dumps_json([document_public_id]),
                    dumps_json(manifest["rights_summary"]),
                    dumps_json(manifest["quality_summary"]),
                    checksum,
                    relative_filename,
                    admin_id,
                ),
            )
            audit(
                connection, "document_sft_exported", admin_id, document_public_id,
                export_public_id=export_id, record_count=len(records),
            )
        return self.get_export(export_id)

    def get_export(self, export_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM document_sft_exports WHERE public_id=?", (export_public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("document sft export not found")
        return _export_row(row)

    def list_exports(self, document_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            self.repository.document(connection, document_public_id)
            rows = connection.execute(
                "SELECT * FROM document_sft_exports WHERE EXISTS ("
                "SELECT 1 FROM json_each(source_document_ids_json) WHERE value=?"
                ") ORDER BY created_at DESC",
                (document_public_id,),
            ).fetchall()
        return {"items": [_export_row(row) for row in rows]}

    def validate_export(self, export_public_id: str) -> dict[str, Any]:
        """Re-derives the manifest checksum from the JSONL file currently on
        disk and compares it against the value stored at export time --
        detects on-disk tampering or corruption without mutating anything."""

        export = self.get_export(export_public_id)
        path = self.settings.resolved_document_sft_export_dir / export["export_path"]
        if not path.is_file():
            return {"valid": False, "reason": "export_file_missing", "export": export}
        records = [
            record for record in path.read_text(encoding="utf-8").strip().split("\n") if record
        ]
        manifest = {
            "record_count": export["record_count"],
            "excluded_count": export["excluded_count"],
            "task_distribution": export["task_distribution"],
            "language_distribution": export["language_distribution"],
            "domain_distribution": export["domain_distribution"],
            "source_document_ids": export["source_document_ids"],
            "rights_summary": export["rights_summary"],
            "quality_summary": export["quality_summary"],
        }
        recomputed_checksum = manifest_checksum(manifest)
        return {
            "valid": (
                recomputed_checksum == export["checksum_sha256"]
                and len(records) == export["record_count"]
            ),
            "stored_checksum": export["checksum_sha256"],
            "recomputed_checksum": recomputed_checksum,
            "on_disk_record_count": len(records),
            "manifest_record_count": export["record_count"],
            "export": export,
        }
