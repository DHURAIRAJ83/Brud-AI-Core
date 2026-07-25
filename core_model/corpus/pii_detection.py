"""Personal-information detection.

PII handling is policy-controlled: redact, quarantine, or block,
depending on corpus policy and source type -- unlike genuine secrets
(``secret_detection.py``), which are always blocked outright. Redaction
placeholders are typed and deterministic; raw sensitive values are
never returned by this module's own output.
"""

from __future__ import annotations

import re
from typing import Any

_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b")
_AADHAAR_LIKE_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_PAN_LIKE_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_PASSPORT_LIKE_PATTERN = re.compile(r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b")
_PRECISE_ADDRESS_PATTERN = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9.\s]{2,40}(street|st\.|road|rd\.|avenue|ave\.|lane|nagar|salai)\b",
    re.IGNORECASE,
)
_MEDICAL_RECORD_PATTERN = re.compile(
    r"\b(diagnosed with|patient (id|name)|medical record number|prescription for)\b",
    re.IGNORECASE,
)

_REDACTION_PLACEHOLDERS = {
    "email": "<EMAIL_REDACTED>",
    "phone": "<PHONE_REDACTED>",
    "aadhaar_like": "<PERSONAL_ID_REDACTED>",
    "pan_like": "<PERSONAL_ID_REDACTED>",
    "passport_like": "<PERSONAL_ID_REDACTED>",
    "precise_address": "<ADDRESS_REDACTED>",
    "personal_medical_record": "<PERSONAL_ID_REDACTED>",
}

_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": _EMAIL_PATTERN,
    "phone": _PHONE_PATTERN,
    "aadhaar_like": _AADHAAR_LIKE_PATTERN,
    "pan_like": _PAN_LIKE_PATTERN,
    "passport_like": _PASSPORT_LIKE_PATTERN,
    "precise_address": _PRECISE_ADDRESS_PATTERN,
    "personal_medical_record": _MEDICAL_RECORD_PATTERN,
}


def detect_pii(text: str) -> dict[str, Any]:
    findings: dict[str, int] = {}
    for category, pattern in _PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings[category] = len(matches)
    return {"findings": findings, "total_findings": sum(findings.values())}


def redact_pii(text: str, findings: dict[str, int]) -> str:
    redacted = text
    for category in findings:
        pattern = _PATTERNS[category]
        redacted = pattern.sub(_REDACTION_PLACEHOLDERS[category], redacted)
    return redacted


def decide_pii_action(
    findings: dict[str, int], *, policy_action: str = "redact"
) -> str:
    """``policy_action`` is one of redact/quarantine/block, chosen by
    corpus policy per source type -- this function never overrides the
    policy's own choice, it only reports what would happen if no
    findings exist."""

    if not findings:
        return "safe"
    if policy_action not in {"redact", "quarantine", "block"}:
        policy_action = "redact"
    return policy_action
