"""Phase 12 Step 16 PII/sensitive-data scan and Step 17 harmful-content
scan, both as thin, honestly-scoped wrappers over existing corpus
safety primitives -- never a second pattern implementation.

PII/secrets: `core_model.corpus.pii_detection.detect_pii()`/
`redact_pii()` (email, phone, government-ID-like patterns, precise
address, personal medical record) plus
`core_model.corpus.secret_detection.detect_secrets()` (password,
API key, access token, private key, payment card, bank account,
cookies/session IDs, database credentials -- always blocked, matching
that module's own "no redact-and-keep for a genuine credential" rule).
Both public APIs report only match *counts*, not character offsets, so
`evidence_location` here is count-based, not offset-based -- this
module never reaches into either module's private compiled-pattern
dict to get more than that.

Harmful content: `core_model.corpus.safety_filter.assess_safety()`
(violence, self-harm, illegal instructions, weapons, malware
instructions, credential theft, hate/harassment, sexual content,
exploitative content, high-risk medical/financial guidance), with its
existing descriptive/educational/historical/preventive/
operational_harmful behavior classification carried through.
`extremist_content` and `legal_misinformation_risk` have no underlying
deterministic signal in `safety_filter.py` today -- this is a
disclosed gap, not a silent one.
"""

from __future__ import annotations

from typing import Any

from core_model.corpus.pii_detection import decide_pii_action, detect_pii, redact_pii
from core_model.corpus.safety_filter import assess_safety
from core_model.corpus.secret_detection import ALWAYS_BLOCKED_CATEGORIES, detect_secrets

_PII_CATEGORY_MAP = {
    "email": "email_address",
    "phone": "phone_number",
    "aadhaar_like": "government_identifier",
    "pan_like": "government_identifier",
    "passport_like": "government_identifier",
    "precise_address": "postal_address",
    "personal_medical_record": "health_information",
}
# Categories with real false-positive risk (e.g. a random 12-digit
# number is not necessarily an Aadhaar number) start life as
# `possible`, not `likely` -- both are in `AMBIGUOUS_PII_FINDING_
# STATUSES`, so either always requires human review regardless.
_AMBIGUOUS_PII_SOURCE_CATEGORIES = frozenset({"aadhaar_like", "pan_like", "passport_like"})

_SECRET_CATEGORY_MAP = {
    "password": "password",
    "api_key": "api_key",
    "access_token": "token",
    "private_key": "private_key",
    "payment_card": "payment_card",
    "bank_account": "financial_account_number",
    "authentication_cookie": "credential",
    "session_id": "credential",
    "database_credentials": "credential",
}

_SAFETY_CATEGORY_MAP = {
    "explicit_violence": "violent_content",
    "self_harm": "self_harm_content",
    "illegal_instructions": "illegal_activity_instructions",
    "weapon_construction": "weapons_content",
    "malware_instructions": "malware_instructions",
    "credential_theft": "fraud_or_scam_content",
    "hate_harassment": "hate_or_harassment",
    "sexual_content": "sexual_content",
    "exploitative_content": "personal_data_abuse",
    "high_risk_medical": "medical_misinformation_risk",
    "high_risk_financial": "fraud_or_scam_content",
}


class ExternalDatasetPIIScanService:
    def scan(self, text: str) -> dict[str, Any]:
        pii_result = detect_pii(text)
        findings: list[dict[str, Any]] = []
        for category, count in pii_result["findings"].items():
            status = "possible" if category in _AMBIGUOUS_PII_SOURCE_CATEGORIES else "likely"
            findings.append(
                {
                    "category": _PII_CATEGORY_MAP.get(category, category),
                    "status": status,
                    "confidence": "low" if status == "possible" else "medium",
                    "location": {"match_count": count},
                }
            )

        secrets_result = detect_secrets(text)
        for category in secrets_result["matched_categories"]:
            findings.append(
                {
                    "category": _SECRET_CATEGORY_MAP.get(category, "credential"),
                    "status": "blocked" if category in ALWAYS_BLOCKED_CATEGORIES else "likely",
                    "confidence": "high",
                    "location": {"secret_category": category},
                }
            )

        redacted_candidate = None
        if pii_result["findings"] and decide_pii_action(pii_result["findings"]) == "redact":
            redacted_candidate = redact_pii(text, pii_result["findings"])

        ambiguous_statuses = ("possible", "likely")
        return {
            "findings": findings,
            "any_ambiguous": any(finding["status"] in ambiguous_statuses for finding in findings),
            "any_blocked": any(finding["status"] == "blocked" for finding in findings),
            "redacted_candidate_text": redacted_candidate,
        }


class ExternalDatasetSafetyScanService:
    def scan(self, text: str) -> dict[str, Any]:
        result = assess_safety(text)
        findings: list[dict[str, Any]] = []
        for finding in result["findings"]:
            behavior_class = finding["behavior_class"]
            severity = "severe" if behavior_class == "operational_harmful" else "low"
            findings.append(
                {
                    "category": _SAFETY_CATEGORY_MAP.get(finding["category"], finding["category"]),
                    "behavior_class": behavior_class,
                    "severity": severity,
                    "confidence": "medium",
                    "location": {"source_category": finding["category"]},
                }
            )
        return {
            "status": result["status"],
            "findings": findings,
            "requires_review": bool(findings),
        }
