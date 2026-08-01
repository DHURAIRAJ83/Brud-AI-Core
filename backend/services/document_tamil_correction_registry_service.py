"""Versioned, reviewable Tamil correction-rule registry (Task Finalization
§13/§14/§15). Rules never activate themselves and are never fetched from an
external dictionary -- every rule enters as a `draft`, proposed by an admin
(or, for `draft`/`needs_review` only, the Admin Assistant's governed propose
path), and only a human Admin can move a rule to `approved` or `active`.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.documents import DocumentRepository, decode

_RULE_JSON: set[str] = set()

_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"needs_review", "rejected"}),
    "needs_review": frozenset({"approved", "draft", "rejected"}),
    "approved": frozenset({"active", "rejected"}),
    "active": frozenset({"rejected"}),
    "rejected": frozenset({"draft"}),
}
_ACTION_TARGET_STATUS = {
    "submit_review": "needs_review",
    "approve": "approved",
    "activate": "active",
    "reject": "rejected",
}


class DocumentTamilCorrectionRegistryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)

    def create_rule(
        self,
        *,
        incorrect_form: str,
        approved_correction: str,
        issue_category: str,
        evidence: str,
        confidence_band: str,
        meaning_change_risk: str,
        admin_id: str,
        public_id: str | None = None,
    ) -> dict[str, Any]:
        if not incorrect_form.strip() or not approved_correction.strip():
            raise ValidationError("incorrect_form and approved_correction are required")
        automatic_proposal_allowed = meaning_change_risk == "mechanical"
        human_review_required = meaning_change_risk in ("meaning_sensitive", "ambiguous")
        rule_id = public_id or str(uuid4())
        with self.repository.transaction() as connection:
            connection.execute(
                """INSERT INTO document_tamil_correction_rules(
                    public_id,incorrect_form,approved_correction,issue_category,evidence,
                    confidence_band,meaning_change_risk,automatic_proposal_allowed,
                    human_review_required,created_by_admin_public_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    rule_id, incorrect_form, approved_correction, issue_category, evidence,
                    confidence_band, meaning_change_risk, 1 if automatic_proposal_allowed else 0,
                    1 if human_review_required else 0, admin_id,
                ),
            )
        return self.get_rule(rule_id)

    def get_rule(self, rule_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM document_tamil_correction_rules WHERE public_id=?",
                (rule_public_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("document tamil correction rule not found")
        return decode(row, _RULE_JSON)

    def list_rules(
        self, page: int = 1, page_size: int = 50, status: str | None = None
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            clauses, params = ["1=1"], []
            if status:
                clauses.append("status=?")
                params.append(status)
            where = " AND ".join(clauses)
            total = connection.execute(
                f"SELECT COUNT(*) FROM document_tamil_correction_rules WHERE {where}", params
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = connection.execute(
                f"SELECT * FROM document_tamil_correction_rules WHERE {where} "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            ).fetchall()
        return {
            "items": [decode(row, _RULE_JSON) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def transition(
        self, rule_public_id: str, action: str, admin_id: str, notes: str = ""
    ) -> dict[str, Any]:
        if action not in _ACTION_TARGET_STATUS:
            raise ValidationError(f"unsupported Tamil correction rule action: {action!r}")
        target_status = _ACTION_TARGET_STATUS[action]
        with self.repository.transaction() as connection:
            rule = connection.execute(
                "SELECT * FROM document_tamil_correction_rules WHERE public_id=?",
                (rule_public_id,),
            ).fetchone()
            if rule is None:
                raise NotFoundError("document tamil correction rule not found")
            current_status = rule["status"]
            if target_status not in _TRANSITIONS.get(current_status, frozenset()):
                raise ValidationError(
                    f"cannot transition Tamil correction rule from "
                    f"'{current_status}' to '{target_status}'"
                )
            new_version = (
                rule["rule_version"] + 1 if target_status == "active" else rule["rule_version"]
            )
            connection.execute(
                "UPDATE document_tamil_correction_rules SET status=?,rule_version=?,"
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (target_status, new_version, rule["id"]),
            )
            connection.execute(
                """INSERT INTO document_tamil_correction_rule_reviews(
                    public_id,rule_id,action,actor_reference,notes
                ) VALUES (?,?,?,?,?)""",
                (str(uuid4()), rule["id"], action, admin_id, notes),
            )
        return self.get_rule(rule_public_id)

    def review_history(self, rule_public_id: str) -> dict[str, Any]:
        rule = self.get_rule(rule_public_id)
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM document_tamil_correction_rule_reviews WHERE rule_id=("
                "SELECT id FROM document_tamil_correction_rules WHERE public_id=?"
                ") ORDER BY id",
                (rule_public_id,),
            ).fetchall()
        return {"rule": rule, "items": [dict(row) for row in rows]}
