"""Phase 12 Steps 10-13/18-20 pipeline orchestration: validate, extract,
scan, parse, and run quality/duplicate/contamination checks over a
sample import's quarantined files/records.

The single shared implementation both the REST API
(`backend/api/routes/dataset_sample_import.py`) and the Admin
Assistant executors (`admin_assistant_service.py`) call -- avoids two
independent copies of the same orchestration drifting apart. No raw
SQL: every step here only ever calls repository/service methods.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.services.dataset_sample_archive_safety_service import (
    ExternalDatasetArchiveSafetyService,
)
from backend.services.dataset_sample_contamination_service import (
    ExternalDatasetContaminationService,
)
from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService
from backend.services.dataset_sample_file_validation_service import (
    ExternalDatasetFileValidationService,
)
from backend.services.dataset_sample_language_service import ExternalDatasetSampleLanguageService
from backend.services.dataset_sample_normalization_service import (
    ExternalDatasetSampleNormalizationService,
)
from backend.services.dataset_sample_parsing_service import ExternalDatasetSampleParsingService
from backend.services.dataset_sample_pii_safety_service import (
    ExternalDatasetPIIScanService,
    ExternalDatasetSafetyScanService,
)
from backend.services.dataset_sample_quality_service import ExternalDatasetQualityService
from backend.services.dataset_sample_quarantine_service import ExternalDatasetQuarantineService


def extension_of(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".tar.gz"):
        return ".tar.gz"
    return Path(lowered).suffix


class ExternalDatasetSamplePipelineService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._quarantine = ExternalDatasetQuarantineService(settings)

    def validate_files(self, sample_import_id: str, *, admin_id: str) -> list[dict[str, Any]]:
        validator = ExternalDatasetFileValidationService()
        results = []
        for file_record in self._samples.list_files(sample_import_id, status="pending"):
            path = self._quarantine.original_file_path(
                sample_import_id, file_record["safe_filename"]
            )
            if not path.exists():
                continue
            outcome = validator.validate_file(
                path, original_filename=file_record["original_filename"]
            )
            results.append(
                self._samples.update_file(
                    file_record["public_id"],
                    {
                        "status": outcome["status"],
                        "detected_mime": outcome["detected_mime"],
                        "detected_signature": outcome["detected_signature"],
                        "blocked_class": outcome["blocked_class"],
                        "rejection_reason": outcome["rejection_reason"],
                        "is_archive": int(outcome["is_archive"]),
                        "archive_format": outcome["archive_format"],
                        "encoding": outcome["encoding"],
                    },
                )
            )
        self._samples.update_sample_import(sample_import_id, {"current_stage": "file_validation"})
        self._samples.record_event(
            sample_import_id,
            {
                "event_type": "extraction_completed",
                "summary": f"Validated {len(results)} file(s)",
                "performed_by_admin_public_id": admin_id,
            },
        )
        return results

    def extract_archives(self, sample_import_id: str, *, admin_id: str) -> list[dict[str, Any]]:
        archive_service = ExternalDatasetArchiveSafetyService()
        summaries = []
        for file_record in self._samples.list_files(sample_import_id):
            if not file_record["is_archive"] or file_record["status"] != "safe_for_scan":
                continue
            archive_path = self._quarantine.original_file_path(
                sample_import_id, file_record["safe_filename"]
            )
            destination = self._quarantine.derived_dir(sample_import_id) / file_record["public_id"]
            result = archive_service.extract(
                archive_path, destination, archive_format=file_record["archive_format"]
            )
            self._samples.record_extraction_event(
                sample_import_id,
                {
                    "archive_file_public_id": file_record["public_id"],
                    "event_type": "aborted_bomb_detected" if result.aborted else "completed",
                    "expanded_bytes": result.expanded_bytes,
                    "member_count": result.member_count,
                    "performed_by_admin_public_id": admin_id,
                },
            )
            for rejected in result.rejected:
                self._samples.record_extraction_event(
                    sample_import_id,
                    {
                        "archive_file_public_id": file_record["public_id"],
                        "event_type": "member_rejected",
                        "member_path": rejected.member_path,
                        "rejection_reason": rejected.reason,
                        "performed_by_admin_public_id": admin_id,
                    },
                )
            summaries.append(
                {
                    "file_public_id": file_record["public_id"],
                    "extracted": len(result.extracted),
                    "rejected": len(result.rejected),
                    "aborted": result.aborted,
                    "abort_reason": result.abort_reason,
                }
            )
        self._samples.update_sample_import(
            sample_import_id, {"current_stage": "archive_extraction"}
        )
        return summaries

    def scan_files(self, sample_import_id: str, *, admin_id: str) -> list[dict[str, Any]]:
        from backend.services.dataset_sample_security_scan_service import (
            ExternalDatasetSecurityScanService,
        )

        scanner = ExternalDatasetSecurityScanService()
        results = []
        for file_record in self._samples.list_files(sample_import_id):
            if file_record["status"] not in ("safe_for_scan", "validated"):
                continue
            path = self._quarantine.original_file_path(
                sample_import_id, file_record["safe_filename"]
            )
            if not path.exists():
                continue
            content = path.read_bytes()
            outcome = scanner.scan_file(
                content,
                original_filename=file_record["original_filename"],
                file_validation_result=file_record,
            )
            result = self._samples.record_scan_result(
                sample_import_id,
                {
                    "file_public_id": file_record["public_id"],
                    "verdict": outcome["verdict"],
                    "matched_signals": outcome["matched_signals"],
                    "reason": outcome["reason"],
                    "scanner_version": "phase12-deterministic-scanner-v1",
                },
            )
            if outcome["verdict"] != "blocked":
                self._samples.update_file(file_record["public_id"], {"status": "validated"})
            results.append(result)
        self._samples.update_sample_import(
            sample_import_id, {"status": "scanning", "current_stage": "security_scan"}
        )
        return results

    def parse_files(self, sample_import_id: str, *, admin_id: str) -> list[dict[str, Any]]:
        parser = ExternalDatasetSampleParsingService()
        normalizer = ExternalDatasetSampleNormalizationService()
        created_records = []
        for file_record in self._samples.list_files(sample_import_id, status="validated"):
            path = self._quarantine.original_file_path(
                sample_import_id, file_record["safe_filename"]
            )
            if not path.exists() or file_record["is_archive"]:
                continue
            extension = extension_of(file_record["original_filename"])
            content = path.read_bytes()
            try:
                parsed = parser.parse(content, extension=extension)
            except Exception:  # noqa: BLE001 - unsupported/parsing failure never aborts the batch
                continue
            source_checksum = file_record["checksum"] or ""
            for parsed_record in parsed.records:
                normalized = normalizer.normalize(
                    parsed_record, source_checksum=source_checksum, ocr_derived=parsed.ocr_derived
                )
                created_records.append(
                    self._samples.add_record(
                        sample_import_id,
                        {
                            "source_file_public_id": file_record["public_id"],
                            "source_row_or_page": normalized.source_row_or_page,
                            "raw_content": normalized.raw_content,
                            "normalized_content": normalized.normalized_content,
                            "structured_payload": normalized.structured_payload,
                            "source_checksum": normalized.source_checksum,
                            "record_checksum": normalized.record_checksum,
                            "parser_version": normalized.parser_version,
                            "normalizer_version": normalized.normalizer_version,
                            "ocr_derived": normalized.ocr_derived,
                            "status": "normalized",
                        },
                    )
                )
        self._samples.update_sample_import(sample_import_id, {"current_stage": "content_parsing"})
        self._samples.record_event(
            sample_import_id,
            {
                "event_type": "parsing_completed",
                "summary": f"Parsed {len(created_records)} record(s)",
                "performed_by_admin_public_id": admin_id,
            },
        )
        return created_records

    def run_quality_checks(self, sample_import_id: str, *, admin_id: str) -> list[dict[str, Any]]:
        del admin_id
        quality = ExternalDatasetQualityService()
        language = ExternalDatasetSampleLanguageService()
        pii = ExternalDatasetPIIScanService()
        safety = ExternalDatasetSafetyScanService()
        created_issues = []
        for record in self._samples.list_records(sample_import_id, limit=100):
            lang_result = language.validate(record["normalized_content"])
            quality_result = quality.assess(
                raw_content=record["raw_content"],
                normalized_content=record["normalized_content"],
                structured_payload=record["structured_payload"],
                detected_language=lang_result["language"],
            )
            for issue in quality_result["issues"]:
                created_issues.append(
                    self._samples.add_record_issue(
                        sample_import_id,
                        {
                            "record_public_id": record["public_id"],
                            "issue_category": "quality",
                            "issue_type": issue["issue_type"],
                            "status": quality_result["state"],
                        },
                    )
                )
            pii_result = pii.scan(record["normalized_content"])
            for finding in pii_result["findings"]:
                created_issues.append(
                    self._samples.add_record_issue(
                        sample_import_id,
                        {
                            "record_public_id": record["public_id"],
                            "issue_category": "pii",
                            "issue_type": finding["category"],
                            "status": finding["status"],
                            "confidence": finding["confidence"],
                            "location": finding["location"],
                        },
                    )
                )
            safety_result = safety.scan(record["normalized_content"])
            for finding in safety_result["findings"]:
                created_issues.append(
                    self._samples.add_record_issue(
                        sample_import_id,
                        {
                            "record_public_id": record["public_id"],
                            "issue_category": "safety",
                            "issue_type": finding["category"],
                            "status": safety_result["status"],
                            "severity": finding["severity"],
                            "confidence": finding["confidence"],
                        },
                    )
                )
        self._samples.update_sample_import(sample_import_id, {"current_stage": "quality_scan"})
        return created_issues

    def run_duplicate_checks(self, sample_import_id: str, *, admin_id: str) -> list[dict[str, Any]]:
        del admin_id
        duplicate_service = ExternalDatasetDuplicateService()
        records = self._samples.list_records(sample_import_id, limit=100)
        groups = duplicate_service.group_exact_duplicates(records)
        near_duplicate_groups = duplicate_service.group_near_duplicates(records)
        groups += [group for group in near_duplicate_groups if group not in groups]
        created_issues = []
        for index, group in enumerate(groups):
            for record_public_id in group:
                created_issues.append(
                    self._samples.add_record_issue(
                        sample_import_id,
                        {
                            "record_public_id": record_public_id,
                            "issue_category": "duplicate",
                            "issue_type": "exact_duplicate",
                            "status": "open",
                            "related_group_id": f"dup-group-{index}",
                        },
                    )
                )
        self._samples.update_sample_import(sample_import_id, {"current_stage": "duplicate_scan"})
        return created_issues

    def run_contamination_checks(
        self, sample_import_id: str, *, admin_id: str
    ) -> list[dict[str, Any]]:
        del admin_id
        contamination_service = ExternalDatasetContaminationService()
        created_issues = []
        for record in self._samples.list_records(sample_import_id, limit=100):
            result = contamination_service.check(record["normalized_content"])
            if result["status"] == "confirmed_overlap":
                created_issues.append(
                    self._samples.add_record_issue(
                        sample_import_id,
                        {
                            "record_public_id": record["public_id"],
                            "issue_category": "contamination",
                            "issue_type": result["issues"][0] if result["issues"] else "unknown",
                            "status": result["status"],
                            "contamination_reference": ",".join(result["issues"]),
                        },
                    )
                )
        self._samples.update_sample_import(
            sample_import_id, {"current_stage": "contamination_scan"}
        )
        return created_issues
