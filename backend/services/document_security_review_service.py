"""Prompt-injection and PII detection for untrusted document text (Task
Finalization §18/§19). All PDF/document text is treated as untrusted data:
detected content is stored, flagged, and gated -- never executed, never
allowed to alter Admin Assistant or system behavior, and secrets/absolute
paths always block export. Reuses the same secret/absolute-path patterns
already relied on for JSONL export scanning (`core_model.release.manifest`)
rather than a second implementation of that specific check.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.documents import DocumentRepository, decode
from core_model.release.manifest import _ABSOLUTE_PATH_PATTERN, _SECRET_LIKE_PATTERN

_FINDING_JSON: set[str] = set()

_PROMPT_INJECTION_PATTERNS = re.compile(
    r"ignore (?:the )?(?:previous|prior|above) instructions|"
    r"disregard (?:your|the) (?:previous|prior) instructions|"
    r"reveal (?:the )?system prompt|"
    r"execute this command|"
    r"change your (?:policy|behavior|rules)|"
    r"send (?:this )?data externally|"
    r"follow this hidden instruction|"
    r"you are now (?:a|an|in) ",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+91[\s-]?)?(?:\(\d{2,4}\)[\s-]?)?\d{3,5}[\s-]\d{3,4}[\s-]?\d{0,4}(?!\w)"
)
_ADDRESS_PATTERN = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9 ]{2,40}\s(?:street|st\.?|road|rd\.?|avenue|ave\.?|"
    r"nagar|colony|lane)\b",
    re.IGNORECASE,
)
_GOVERNMENT_ID_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{4}\s?\d{4}\s?\d{4}\b")
_BANK_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b|\b\d{9,18}\b")
# No existing detector in the repository covers markup/query injection
# payloads (as opposed to natural-language prompt injection) -- this is a
# genuine gap, not a duplicate of anything. Kept intentionally narrow
# (unambiguous attack-shaped syntax only) to avoid false positives on
# ordinary Tamil/English/Tanglish prose that merely mentions databases or
# scripts.
_XSS_PATTERN = re.compile(
    r"<script\b|javascript:\s*\S|on(?:error|load|click|mouseover|focus)\s*=", re.IGNORECASE
)
_SQL_INJECTION_PATTERN = re.compile(
    r";\s*(?:DROP|DELETE\s+FROM|TRUNCATE)\s+TABLE\b|\bUNION\s+SELECT\b|'\s*OR\s*'1'\s*=\s*'1|--\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_ACTION_BY_FINDING_TYPE = {
    "prompt_injection": "exclude_from_sft",
    "pii_email": "require_review",
    "pii_phone": "require_review",
    "pii_address": "require_review",
    "pii_government_id": "require_review",
    "pii_bank": "require_review",
    "pii_secret": "block_export",
    "pii_path": "block_export",
    "xss_payload": "block_export",
    "sql_injection_payload": "block_export",
}
_CONFIDENCE_BY_FINDING_TYPE = {
    "prompt_injection": "medium",
    "pii_email": "high",
    "pii_phone": "medium",
    "pii_address": "low",
    "pii_government_id": "low",
    "pii_bank": "low",
    "pii_secret": "high",
    "pii_path": "high",
    "xss_payload": "high",
    "sql_injection_payload": "high",
}


def _content_hash(document_id: int, page_number: int, finding_type: str, matched_text: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{document_id}:{page_number}:{finding_type}:{matched_text}".encode())
    return digest.hexdigest()


def _findings_for_text(text: str) -> list[tuple[str, str, str]]:
    """Returns (finding_type, matched_text, reason_code) tuples."""

    results: list[tuple[str, str, str]] = []
    for match in _PROMPT_INJECTION_PATTERNS.finditer(text):
        results.append(("prompt_injection", match.group(0), "prompt_injection_phrase_detected"))
    for match in _SECRET_LIKE_PATTERN.finditer(text):
        results.append(("pii_secret", match.group(0), "secret_like_content_detected"))
    for match in _ABSOLUTE_PATH_PATTERN.finditer(text):
        results.append(("pii_path", match.group(0).strip(), "absolute_path_detected"))
    for match in _EMAIL_PATTERN.finditer(text):
        results.append(("pii_email", match.group(0), "email_pattern_detected"))
    for match in _GOVERNMENT_ID_PATTERN.finditer(text):
        results.append(("pii_government_id", match.group(0), "government_id_pattern_detected"))
    for match in _ADDRESS_PATTERN.finditer(text):
        results.append(("pii_address", match.group(0), "address_pattern_detected"))
    for match in _BANK_PATTERN.finditer(text):
        results.append(("pii_bank", match.group(0), "bank_account_pattern_detected"))
    for match in _PHONE_PATTERN.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 7:
            results.append(("pii_phone", match.group(0), "phone_pattern_detected"))
    for match in _XSS_PATTERN.finditer(text):
        results.append(("xss_payload", match.group(0), "xss_payload_detected"))
    for match in _SQL_INJECTION_PATTERN.finditer(text):
        results.append(("sql_injection_payload", match.group(0), "sql_injection_payload_detected"))
    return results


# Priority order for the single primary reason code returned by
# `assess_text_safety` when multiple categories match -- most severe /
# most unambiguous attack shape first. Checked as an exact category-name
# prefix, never a loose substring match, so e.g. "pii_secret" (a
# credential found by this module's own document-scoped scan) is never
# mistaken for the generic "pii_*" categories `detect_pii` reports.
_REASON_CODE_PRIORITY: list[tuple[str, str]] = [
    ("prompt_injection", "PROMPT_INJECTION_DETECTED"),
    ("pii_secret", "SECRET_DETECTED"),
    ("pii_path", "SECRET_DETECTED"),
    ("password", "SECRET_DETECTED"),
    ("api_key", "SECRET_DETECTED"),
    ("access_token", "SECRET_DETECTED"),
    ("private_key", "SECRET_DETECTED"),
    ("payment_card", "SECRET_DETECTED"),
    ("bank_account", "SECRET_DETECTED"),
    ("authentication_cookie", "SECRET_DETECTED"),
    ("session_id", "SECRET_DETECTED"),
    ("database_credentials", "SECRET_DETECTED"),
    ("xss_payload", "MALICIOUS_PAYLOAD_DETECTED"),
    ("sql_injection_payload", "MALICIOUS_PAYLOAD_DETECTED"),
    ("pii_", "PII_DETECTED"),
]


def assess_text_safety(text: str) -> dict[str, Any]:
    """Deterministic, non-persisting content-safety assessment for a single
    piece of candidate training text (Phase 2.7B). Reuses this module's own
    document-scoped pattern set (`_findings_for_text` -- prompt injection,
    secrets/absolute paths, and the XSS/SQL-injection payload patterns added
    this phase) plus the project's canonical, already-widely-reused corpus
    detectors (`core_model.corpus.pii_detection.detect_pii`,
    `core_model.corpus.secret_detection.detect_secrets`,
    `core_model.corpus.safety_filter.assess_safety`). Introduces no new
    classifier and calls no external service or model. Never returns or
    persists matched substrings -- only category labels -- so callers can
    audit/store the result without exposing the underlying sensitive text.

    Policy for this gate specifically (documented in the Phase 2.7B report):
    any detected secret, prompt-injection phrase, XSS/SQL-injection payload,
    or `assess_safety`-classified operational-harmful content blocks
    outright. Any detected PII blocks outright too -- a deliberately
    stricter choice than `decide_pii_action`'s general-purpose
    redact/quarantine default, appropriate for training-data approval
    specifically. `assess_safety` findings classified as merely descriptive/
    educational/historical/preventive (not operational_harmful) do NOT
    block, preserving that detector's own nuance.
    """

    from core_model.corpus.pii_detection import detect_pii
    from core_model.corpus.safety_filter import assess_safety
    from core_model.corpus.secret_detection import detect_secrets

    categories: set[str] = set()
    for finding_type, _matched_text, _reason_code in _findings_for_text(text):
        categories.add(finding_type)

    secrets_result = detect_secrets(text)
    if secrets_result["status"] in ("blocked", "requires_review"):
        categories.update(secrets_result["matched_categories"])

    pii_result = detect_pii(text)
    if pii_result["findings"]:
        categories.update(f"pii_{key}" for key in pii_result["findings"])

    safety_result = assess_safety(text)
    if safety_result["status"] == "blocked":
        categories.update(finding["category"] for finding in safety_result["findings"])

    if not categories:
        return {"status": "passed", "categories": [], "reason_code": None}

    reason_code = "CONTENT_SAFETY_FAILED"
    for prefix, code in _REASON_CODE_PRIORITY:
        if any(category.startswith(prefix) for category in categories):
            reason_code = code
            break
    return {"status": "blocked", "categories": sorted(categories), "reason_code": reason_code}


class DocumentSecurityReviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)

    def scan_document(self, document_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            pages = connection.execute(
                "SELECT page_number,cleaned_text FROM document_pages WHERE "
                "document_source_id=? AND cleaned_text IS NOT NULL ORDER BY page_number",
                (document["id"],),
            ).fetchall()
            created = 0
            max_per_page = self.settings.document_security_max_findings_per_page
            for page in pages:
                text = page["cleaned_text"] or ""
                if not text.strip():
                    continue
                created_for_page = 0
                for finding_type, matched_text, reason_code in _findings_for_text(text):
                    if created_for_page >= max_per_page:
                        break
                    digest = _content_hash(
                        document["id"], page["page_number"], finding_type, matched_text
                    )
                    exists = connection.execute(
                        "SELECT 1 FROM document_security_findings WHERE content_hash=?",
                        (digest,),
                    ).fetchone()
                    if exists:
                        continue
                    connection.execute(
                        """INSERT INTO document_security_findings(
                            public_id,document_source_id,page_number,finding_type,matched_text,
                            confidence_band,reason_code,action,content_hash
                        ) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            str(uuid4()), document["id"], page["page_number"], finding_type,
                            matched_text, _CONFIDENCE_BY_FINDING_TYPE[finding_type], reason_code,
                            _ACTION_BY_FINDING_TYPE[finding_type], digest,
                        ),
                    )
                    created += 1
                    created_for_page += 1
        return self.summary(document_public_id)

    def list_findings(
        self,
        document_public_id: str,
        page: int = 1,
        page_size: int = 50,
        finding_type: str | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            clauses = ["document_source_id=?"]
            params: list[Any] = [document["id"]]
            if finding_type:
                clauses.append("finding_type=?")
                params.append(finding_type)
            where = " AND ".join(clauses)
            total = connection.execute(
                f"SELECT COUNT(*) FROM document_security_findings WHERE {where}", params
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = connection.execute(
                f"SELECT * FROM document_security_findings WHERE {where} "
                "ORDER BY page_number,id LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            ).fetchall()
        return {
            "items": [decode(row, _FINDING_JSON) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def summary(self, document_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            rows = connection.execute(
                "SELECT finding_type,action,COUNT(*) count FROM document_security_findings "
                "WHERE document_source_id=? GROUP BY finding_type,action",
                (document["id"],),
            ).fetchall()
        by_type: dict[str, int] = {}
        by_action: dict[str, int] = {}
        total = 0
        for row in rows:
            by_type[row["finding_type"]] = by_type.get(row["finding_type"], 0) + row["count"]
            by_action[row["action"]] = by_action.get(row["action"], 0) + row["count"]
            total += row["count"]
        return {
            "document_public_id": document_public_id,
            "total_findings": total,
            "by_finding_type": by_type,
            "by_action": by_action,
            "export_blocking_count": by_action.get("block_export", 0),
        }

    def has_export_blocking_findings(self, document_public_id: str) -> bool:
        return self.summary(document_public_id)["export_blocking_count"] > 0

    def review(
        self, document_public_id: str, finding_public_id: str, action: str, admin_id: str
    ) -> dict[str, Any]:
        if action not in ("reviewed", "dismissed"):
            from backend.database.repositories.base import ValidationError

            raise ValidationError(f"unsupported security finding review action: {action!r}")
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            connection.execute(
                "UPDATE document_security_findings SET review_status=?,"
                "updated_at=CURRENT_TIMESTAMP WHERE document_source_id=? AND public_id=?",
                (action, document["id"], finding_public_id),
            )
        return self.list_findings(document_public_id)
