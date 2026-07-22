"""Deterministic dataset quality assessment for Phase 6."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json, redact_secrets
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_quality import DatasetQualityRepository, _public
from backend.models.dataset_quality import BulkQualityAssessRequest
from backend.services.dataset_service import validate_record

SECRET_PATTERN = re.compile(r"(api[_-]?key|password|secret|token)", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\s-]?){8,}\b")
TAMIL_PATTERN = re.compile(r"[\u0B80-\u0BFF]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")


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
            "dataset_quality",
            resource_id,
            "success",
            dumps_json(redact_secrets(metadata)),
        ),
    )


class DatasetQualityService:
    """Quality rules are deterministic and do not generate or rewrite content."""

    def __init__(self, repository: DatasetQualityRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def _issue(
        self,
        issues: list[dict[str, Any]],
        code: str,
        severity: str,
        message: str,
        field: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        issues.append(
            {
                "public_id": str(uuid4()),
                "issue_code": code,
                "severity": severity,
                "field_name": field,
                "message": message,
                "metadata": metadata or {},
            }
        )

    def assess_record(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self.repository.record(connection, public_id)
            result = self._calculate(connection, row)
            assessment_id = str(uuid4())
            self.repository.insert_assessment(
                connection,
                public_id=assessment_id,
                record_id=row["id"],
                ruleset=self.settings.quality_ruleset_version,
                scores=result["scores"],
                readiness=result["readiness_status"],
                summary=result["summary"],
                assessed_by=admin_id,
                issues=result["issues"],
            )
            _audit(
                connection,
                "dataset_quality_assessed",
                admin_id,
                public_id,
                readiness_status=result["readiness_status"],
                overall_score=round(result["scores"]["overall"], 4),
                issue_codes=sorted({issue["issue_code"] for issue in result["issues"]}),
            )
            assessment = self.repository.assessment_by_public_id(connection, assessment_id)
            issues = self.repository.assessment_issues(connection, assessment_id)
        data = _public(assessment)
        data["issues"] = issues
        return data

    def latest(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            assessment = self.repository.latest_assessment(connection, public_id)
            if not assessment:
                return {"readiness_status": "not_assessed", "issues": []}
            data = _public(assessment)
            data["issues"] = self.repository.assessment_issues(connection, assessment["public_id"])
            return data

    def issues(self, public_id: str) -> dict[str, Any]:
        return {"items": self.latest(public_id).get("issues", [])}

    def assess_filtered(self, request: BulkQualityAssessRequest, admin_id: str) -> dict[str, Any]:
        filters = request.model_dump(exclude_none=True)
        max_records = filters.pop("max_records", request.max_records)
        assessed: list[dict[str, Any]] = []
        with self.repository.transaction() as connection:
            clauses, params = [], []
            for key, column in {
                "status": "r.status",
                "language": "r.language",
                "record_type": "r.record_type",
                "source_public_id": "s.public_id",
            }.items():
                if filters.get(key):
                    clauses.append(f"{column}=?")
                    params.append(filters[key])
            if filters.get("min_updated_at"):
                clauses.append("r.updated_at>=?")
                params.append(filters["min_updated_at"])
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            rows = connection.execute(
                """SELECT r.public_id FROM dataset_records r
                LEFT JOIN dataset_sources s ON s.id=r.source_id"""
                + where
                + " ORDER BY r.updated_at DESC,r.id DESC LIMIT ?",
                (*params, max_records),
            ).fetchall()
        for row in rows:
            assessed.append(self.assess_record(row["public_id"], admin_id))
        return {"assessed": len(assessed), "items": assessed}

    def summary(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            latest = connection.execute(
                """SELECT a.* FROM dataset_quality_assessments a
                JOIN (SELECT dataset_record_id,MAX(id) AS max_id
                FROM dataset_quality_assessments GROUP BY dataset_record_id) x
                ON x.max_id=a.id"""
            ).fetchall()
            total_records = connection.execute("SELECT COUNT(*) FROM dataset_records").fetchone()[0]
            issue_rows = connection.execute(
                """SELECT issue_code,COUNT(*) AS count FROM dataset_quality_issues
                GROUP BY issue_code ORDER BY count DESC,issue_code LIMIT 20"""
            ).fetchall()
        counts = Counter(row["readiness_status"] for row in latest)
        average = sum(row["overall_score"] for row in latest) / len(latest) if latest else 0
        return {
            "total_records": total_records,
            "total_assessed": len(latest),
            "not_assessed": max(total_records - len(latest), 0),
            "ready": counts.get("ready", 0),
            "warning": counts.get("warning", 0),
            "blocked": counts.get("blocked", 0),
            "average_overall_score": round(average, 4),
            "top_issue_codes": [dict(row) for row in issue_rows],
        }

    def all_issues(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            total = connection.execute("SELECT COUNT(*) FROM dataset_quality_issues").fetchone()[0]
            rows = connection.execute(
                """SELECT i.public_id,i.issue_code,i.severity,i.field_name,i.message,
                i.metadata_json,i.created_at,a.public_id AS assessment_public_id,
                r.public_id AS record_public_id
                FROM dataset_quality_issues i
                JOIN dataset_quality_assessments a ON a.id=i.quality_assessment_id
                JOIN dataset_records r ON r.id=a.dataset_record_id
                ORDER BY i.created_at DESC,i.id DESC LIMIT ? OFFSET ?""",
                (page_size, (page - 1) * page_size),
            ).fetchall()
        return {
            "items": [_public(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        }

    def _calculate(self, connection, row) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        values = {
            "record_type": row["record_type"],
            "language": row["language"],
            "instruction": row["instruction"],
            "input_text": row["input_text"],
            "output_text": row["output_text"],
            "normalized_input": row["normalized_input"],
            "metadata": loads_json(row["metadata_json"]),
        }
        try:
            validate_record(values)
            completeness = 1.0
            structure = 1.0
        except ValidationError as exc:
            completeness = 0.2
            structure = 0.3
            self._issue(issues, "missing_required_field", "blocking", str(exc))
        text = "\n".join(
            part
            for part in (
                values.get("instruction"),
                values.get("input_text"),
                values.get("output_text"),
                values.get("normalized_input"),
            )
            if part
        )
        text_nfc = unicodedata.normalize("NFC", text)
        if not text_nfc.strip():
            completeness = 0.0
            self._issue(issues, "empty_or_whitespace_only", "blocking", "record text is empty")
        if len(text_nfc) > self.settings.quality_max_record_chars:
            structure -= 0.4
            self._issue(issues, "text_too_long", "error", "record exceeds maximum length")
        if (
            row["record_type"] == "pretrain"
            and len(text_nfc) < self.settings.quality_min_pretrain_chars
        ):
            completeness -= 0.3
            self._issue(issues, "text_too_short", "warning", "pretrain text is very short")
        language = self._language_score(values["language"], text_nfc, issues)
        text_quality = self._text_quality_score(text_nfc, issues)
        duplication = 1.0
        duplicate = connection.execute(
            "SELECT public_id FROM dataset_records WHERE content_hash=? AND public_id<>?",
            (row["content_hash"], row["public_id"]),
        ).fetchone()
        if duplicate:
            duplication = 0.0
            self._issue(
                issues,
                "duplicate_existing",
                "blocking",
                "record duplicates an existing record",
                metadata={"existing_record_public_id": duplicate["public_id"]},
            )
        safety = self._safety_score(values, issues)
        provenance = self._provenance_score(row, issues)
        scores = {
            "completeness": max(min(completeness, 1), 0),
            "structure": max(min(structure, 1), 0),
            "language": language,
            "text_quality": text_quality,
            "duplication": duplication,
            "safety": safety,
            "provenance": provenance,
        }
        overall = sum(scores.values()) / len(scores)
        scores["overall"] = round(overall, 4)
        if any(issue["severity"] == "blocking" for issue in issues):
            readiness = "blocked"
        elif scores["overall"] >= self.settings.quality_ready_threshold:
            readiness = "ready"
        elif scores["overall"] >= self.settings.quality_warning_threshold:
            readiness = "warning"
        else:
            readiness = "blocked"
        return {
            "scores": {key: round(value, 4) for key, value in scores.items()},
            "readiness_status": readiness,
            "issues": issues,
            "summary": {"text_length": len(text_nfc), "issue_count": len(issues)},
        }

    def _language_score(self, language: str, text: str, issues: list[dict[str, Any]]) -> float:
        has_tamil = bool(TAMIL_PATTERN.search(text))
        has_latin = bool(LATIN_PATTERN.search(text))
        if language == "unknown":
            self._issue(issues, "unknown_language", "warning", "record language is unknown")
            return 0.65
        if language == "ta" and has_latin and not has_tamil:
            self._issue(
                issues, "language_script_mismatch", "warning", "Tamil record has Latin-only text"
            )
            return 0.55
        if language == "en" and has_tamil:
            self._issue(
                issues,
                "language_script_mismatch",
                "warning",
                "English record contains Tamil script",
            )
            return 0.65
        if language == "mixed" and not (has_tamil and has_latin):
            self._issue(
                issues, "language_script_mismatch", "info", "mixed record has one dominant script"
            )
            return 0.85
        return 1.0

    def _text_quality_score(self, text: str, issues: list[dict[str, Any]]) -> float:
        if not text:
            return 0
        score = 1.0
        if "\ufffd" in text:
            score -= 0.4
            self._issue(
                issues, "replacement_character", "error", "text contains replacement characters"
            )
        chars = [char for char in text if not char.isspace()]
        letters = [char for char in chars if char.isalpha()]
        punctuation = [char for char in chars if unicodedata.category(char).startswith("P")]
        if chars and len(letters) / len(chars) < self.settings.quality_min_letter_ratio:
            score -= 0.25
            self._issue(issues, "low_letter_ratio", "warning", "text has a low letter ratio")
        if chars and len(punctuation) / len(chars) > self.settings.quality_max_punctuation_ratio:
            score -= 0.25
            self._issue(
                issues, "excessive_punctuation", "warning", "text has excessive punctuation"
            )
        if re.search(r"(.{2,12})\1{4,}", text):
            score -= 0.25
            self._issue(issues, "excessive_repetition", "warning", "text has repeated sequences")
        if any(unicodedata.category(char).startswith("C") and char not in "\n\t" for char in text):
            score -= 0.25
            self._issue(issues, "suspicious_unicode", "warning", "text contains control characters")
        return max(round(score, 4), 0)

    def _safety_score(self, values: dict[str, Any], issues: list[dict[str, Any]]) -> float:
        serialized = dumps_json(values.get("metadata", {}))
        score = 1.0
        if SECRET_PATTERN.search(serialized):
            score -= 0.5
            self._issue(
                issues, "unsafe_metadata", "blocking", "metadata appears to contain secrets"
            )
        text = " ".join(str(values.get(key) or "") for key in ("input_text", "output_text"))
        if EMAIL_PATTERN.search(text) or PHONE_PATTERN.search(text):
            score -= 0.2
            self._issue(issues, "unsafe_metadata", "warning", "record may contain personal data")
        return max(score, 0)

    def _provenance_score(self, row, issues: list[dict[str, Any]]) -> float:
        if not row["source_public_id"]:
            if self.settings.quality_require_provenance:
                self._issue(issues, "missing_source_provenance", "blocking", "record has no source")
                return 0
            return 0.7
        if row["licence_status"] == "rejected":
            self._issue(issues, "rejected_licence", "blocking", "record source licence is rejected")
            return 0
        if row["licence_status"] in {"unknown", "review_required"}:
            severity = "blocking" if self.settings.quality_block_unknown_licence else "warning"
            self._issue(issues, "unknown_licence", severity, "record source licence needs review")
            return 0.65 if severity == "warning" else 0
        return 1.0
