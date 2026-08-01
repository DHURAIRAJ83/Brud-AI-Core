"""Tamil Unicode/OCR quality detection and conservative correction review.

Reuses `core_model.corpus.unicode_normalization` and
`core_model.corpus.tamil_normalization` (Phase 19) unchanged for the
actual detection/normalization logic -- this module only classifies
their output into a per-page issue queue and a review workflow;
nothing here reimplements Unicode integrity checking or Tamil OCR
substitution. Applying an accepted correction reuses
`PDFResearchWorkspaceService.save_draft()` so page revision history
stays the single source of truth for page text -- this service never
writes to `document_pages` directly.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.documents import DocumentRepository, decode
from backend.models.documents import TamilQualityReviewAction
from backend.services.document_service import audit, now
from backend.services.document_workspace_service import DocumentPageRevisionService
from core_model.corpus.tamil_normalization import normalize_tamil_text
from core_model.corpus.unicode_normalization import (
    assess_unicode_integrity,
    tamil_combining_marks_preserved,
)
from core_model.document_workspace.cleanup_suggestions import suggest_suspicious_latin_in_tamil

_ISSUE_JSON: set[str] = set()
_ACTION_TO_STATUS = {
    "accept": "accepted",
    "reject": "rejected",
    "edit": "edited",
    "ignore": "ignored",
}
_CONTEXT_CHARS = 200


def _content_hash(document_id: int, page_number: int, issue_type: str, original: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{document_id}:{page_number}:{issue_type}:{original}".encode())
    return digest.hexdigest()


def _issues_for_page(cleaned_text: str, raw_text: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    context = cleaned_text[:_CONTEXT_CHARS]
    integrity = assess_unicode_integrity(cleaned_text)
    if integrity["replacement_character_count"] > 0:
        issues.append(
            {
                "issue_type": "invalid_unicode",
                "context": context,
                "original_text": cleaned_text,
                "suggested_text": "",
                "confidence_band": "high",
                "reason_code": "replacement_character_detected",
                "correction_risk": "mandatory_review",
                "human_review_required": True,
            }
        )
    if integrity["mojibake_count"] > 0:
        issues.append(
            {
                "issue_type": "ocr_character_substitution",
                "context": context,
                "original_text": cleaned_text,
                "suggested_text": "",
                "confidence_band": "medium",
                "reason_code": "mojibake_detected",
                "correction_risk": "preview_required",
                "human_review_required": True,
            }
        )
    if not tamil_combining_marks_preserved(raw_text, cleaned_text):
        issues.append(
            {
                "issue_type": "broken_combining_mark",
                "context": context,
                "original_text": cleaned_text,
                "suggested_text": "",
                "confidence_band": "medium",
                "reason_code": "combining_marks_not_preserved",
                "correction_risk": "mandatory_review",
                "human_review_required": True,
            }
        )
    normalized = normalize_tamil_text(cleaned_text)
    counts = normalized["transformation_counts"]
    if normalized["normalized_text"] != cleaned_text and (
        counts.get("tamil_ocr_substitutions") or counts.get("stray_zero_width_characters")
    ):
        issue_type = (
            "ocr_character_substitution"
            if counts.get("tamil_ocr_substitutions")
            else "zero_width_corruption"
        )
        issues.append(
            {
                "issue_type": issue_type,
                "context": context,
                "original_text": cleaned_text,
                "suggested_text": normalized["normalized_text"],
                "confidence_band": "high",
                "reason_code": "mechanical_normalization_available",
                "correction_risk": "mechanical",
                "human_review_required": False,
            }
        )
    if suggest_suspicious_latin_in_tamil(cleaned_text):
        issues.append(
            {
                "issue_type": "non_tamil_glyph_contamination",
                "context": context,
                "original_text": cleaned_text,
                "suggested_text": "",
                "confidence_band": "low",
                "reason_code": "suspicious_latin_in_tamil_context",
                "correction_risk": "preview_required",
                "human_review_required": True,
            }
        )
    return issues


class DocumentTamilQualityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)
        self.workspace = DocumentPageRevisionService(settings)

    def detect(self, document_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            pages = connection.execute(
                "SELECT page_number,raw_text,cleaned_text FROM document_pages "
                "WHERE document_source_id=? AND cleaned_text IS NOT NULL ORDER BY page_number",
                (document["id"],),
            ).fetchall()
            created = 0
            max_per_page = self.settings.document_tamil_max_findings_per_page
            for page in pages:
                text = page["cleaned_text"] or ""
                if not text.strip():
                    continue
                created_for_page = 0
                for issue in _issues_for_page(text, page["raw_text"] or text):
                    if created_for_page >= max_per_page:
                        break
                    digest = _content_hash(
                        document["id"], page["page_number"], issue["issue_type"],
                        issue["original_text"],
                    )
                    exists = connection.execute(
                        "SELECT 1 FROM document_tamil_quality_issues WHERE content_hash=?",
                        (digest,),
                    ).fetchone()
                    if exists:
                        continue
                    connection.execute(
                        """INSERT INTO document_tamil_quality_issues(
                            public_id,document_source_id,page_number,issue_type,context,
                            original_text,suggested_text,confidence_band,reason_code,
                            correction_risk,human_review_required,content_hash
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            str(uuid4()),
                            document["id"],
                            page["page_number"],
                            issue["issue_type"],
                            issue["context"],
                            issue["original_text"],
                            issue["suggested_text"],
                            issue["confidence_band"],
                            issue["reason_code"],
                            issue["correction_risk"],
                            1 if issue["human_review_required"] else 0,
                            digest,
                        ),
                    )
                    created += 1
                    created_for_page += 1
            audit(
                connection, "document_tamil_quality_detected", admin_id, document_public_id,
                issues_created=created,
            )
        return self.summary(document_public_id)

    def summary(self, document_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            rows = connection.execute(
                "SELECT issue_type,review_status,correction_risk,COUNT(*) count "
                "FROM document_tamil_quality_issues WHERE document_source_id=? "
                "GROUP BY issue_type,review_status,correction_risk",
                (document["id"],),
            ).fetchall()
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        total = 0
        for row in rows:
            by_type[row["issue_type"]] = by_type.get(row["issue_type"], 0) + row["count"]
            by_status[row["review_status"]] = by_status.get(row["review_status"], 0) + row["count"]
            by_risk[row["correction_risk"]] = by_risk.get(row["correction_risk"], 0) + row["count"]
            total += row["count"]
        return {
            "document_public_id": document_public_id,
            "total_issues": total,
            "by_issue_type": by_type,
            "by_review_status": by_status,
            "by_correction_risk": by_risk,
            "pending_count": by_status.get("pending", 0),
        }

    def list_issues(
        self,
        document_public_id: str,
        page: int = 1,
        page_size: int = 50,
        review_status: str | None = None,
        issue_type: str | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            clauses = ["document_source_id=?"]
            params: list[Any] = [document["id"]]
            if review_status:
                clauses.append("review_status=?")
                params.append(review_status)
            if issue_type:
                clauses.append("issue_type=?")
                params.append(issue_type)
            where = " AND ".join(clauses)
            total = connection.execute(
                f"SELECT COUNT(*) FROM document_tamil_quality_issues WHERE {where}", params
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = connection.execute(
                f"SELECT * FROM document_tamil_quality_issues WHERE {where} "
                "ORDER BY page_number,id LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            ).fetchall()
        return {
            "items": [decode(row, _ISSUE_JSON) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def review(
        self,
        document_public_id: str,
        issue_public_id: str,
        payload: TamilQualityReviewAction,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            issue = self.repository.tamil_quality_issue(connection, document["id"], issue_public_id)
            if issue["review_status"] != "pending":
                raise ValidationError("this Tamil quality issue has already been reviewed")
            apply_text: str | None = None
            if payload.action == "accept":
                if issue["correction_risk"] == "mandatory_review" and not payload.edited_text:
                    raise ValidationError(
                        "meaning-changing or ambiguous Tamil corrections require a manual "
                        "edit, not a direct accept"
                    )
                apply_text = payload.edited_text or issue["suggested_text"]
                if not apply_text:
                    raise ValidationError("no suggested correction is available to accept")
            elif payload.action == "edit":
                if not payload.edited_text:
                    raise ValidationError("edited_text is required for the edit action")
                apply_text = payload.edited_text
            duplicates: list[Any] = []
            if payload.apply_to_exact_duplicates_only and apply_text is not None:
                duplicates = connection.execute(
                    "SELECT id,page_number FROM document_tamil_quality_issues "
                    "WHERE document_source_id=? AND issue_type=? AND original_text=? "
                    "AND review_status='pending' AND public_id!=?",
                    (document["id"], issue["issue_type"], issue["original_text"], issue_public_id),
                ).fetchall()
            new_status = _ACTION_TO_STATUS[payload.action]
            connection.execute(
                "UPDATE document_tamil_quality_issues SET review_status=?,"
                "reviewed_by_admin_public_id=?,reviewed_at=?,updated_at=? WHERE id=?",
                (new_status, admin_id, now(), now(), issue["id"]),
            )
            for duplicate in duplicates:
                connection.execute(
                    "UPDATE document_tamil_quality_issues SET review_status='accepted',"
                    "reviewed_by_admin_public_id=?,reviewed_at=?,updated_at=? WHERE id=?",
                    (admin_id, now(), now(), duplicate["id"]),
                )
            audit(
                connection, "document_tamil_quality_reviewed", admin_id, document_public_id,
                issue_public_id=issue_public_id, action=payload.action,
                duplicate_count=len(duplicates),
            )
        if apply_text is not None:
            self.workspace.save_draft(
                document_public_id, issue["page_number"], apply_text, admin_id,
                change_summary=f"Tamil quality correction ({issue['issue_type']})",
                correction_types=["tamil_quality"],
            )
            for duplicate in duplicates:
                self.workspace.save_draft(
                    document_public_id, duplicate["page_number"], apply_text, admin_id,
                    change_summary=(
                        f"Tamil quality correction applied to exact duplicate "
                        f"({issue['issue_type']})"
                    ),
                    correction_types=["tamil_quality"],
                )
        return self.list_issues(document_public_id)
