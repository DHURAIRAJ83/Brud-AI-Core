"""Feedback privacy scanning.

Reuses Phase 17's ``core_model.conversation.memory_safety`` secret/
hidden-instruction/path/env-dump detection unchanged for the categories
it already covers. Feedback free text has no CHECK-constrained category
column to lean on the way ``memory_items.category`` does, so this
module adds pattern-based detection for the sensitive-topic categories
Phase 17 could reject structurally: medical, political, religious,
sexual, criminal, biometric, and precise-address content.
"""

from __future__ import annotations

import re
from typing import Any

from core_model.conversation.memory_safety import detect_safety_signals

_MEDICAL_PATTERN = re.compile(
    r"\b(diagnosed with|my (medical|health) condition|hiv positive|cancer diagnosis|"
    r"mental health diagnosis|prescription for)\b",
    re.IGNORECASE,
)
_POLITICAL_PATTERN = re.compile(
    r"\b(i (am|vote for|support) (the )?[a-z]+ party|my political affiliation)\b",
    re.IGNORECASE,
)
_RELIGIOUS_PATTERN = re.compile(
    r"\bmy religion is\b|\bi practice (the )?[a-z]+ faith\b", re.IGNORECASE
)
_SEXUAL_PATTERN = re.compile(r"\bmy sexual orientation\b|\bexplicit sexual\b", re.IGNORECASE)
_CRIMINAL_PATTERN = re.compile(
    r"\b(i was (arrested|convicted)|my criminal record|prior conviction)\b", re.IGNORECASE
)
_BIOMETRIC_PATTERN = re.compile(
    r"\b(my fingerprint|facial recognition scan|iris scan|my dna profile)\b", re.IGNORECASE
)
_PRECISE_ADDRESS_PATTERN = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9.\s]{2,40}(street|st\.|road|rd\.|avenue|ave\.|lane)\b", re.IGNORECASE
)
_DB_CREDENTIAL_PATTERN = re.compile(
    r"\b(postgres|mysql|mongodb)://\S+:\S+@\S+", re.IGNORECASE
)

_SENSITIVE_PATTERNS = {
    "medical_information": _MEDICAL_PATTERN,
    "political_identity": _POLITICAL_PATTERN,
    "religious_identity": _RELIGIOUS_PATTERN,
    "sexual_information": _SEXUAL_PATTERN,
    "criminal_record_claim": _CRIMINAL_PATTERN,
    "biometric_information": _BIOMETRIC_PATTERN,
    "precise_address": _PRECISE_ADDRESS_PATTERN,
    "database_credentials": _DB_CREDENTIAL_PATTERN,
}

_BLOCKING_CATEGORIES = {
    "password",
    "api_key",
    "access_token",
    "private_key",
    "payment_card",
    "bank_account",
    "authentication_cookie",
    "hidden_instruction",
    "medical_information",
    "political_identity",
    "religious_identity",
    "sexual_information",
    "criminal_record_claim",
    "biometric_information",
    "precise_address",
    "database_credentials",
}
_REDACT_CATEGORIES = {"absolute_path", "environment_variable_dump"}

_MAXIMUM_EXCERPT_LENGTH = 160


def detect_privacy_signals(text: str) -> dict[str, Any]:
    base = detect_safety_signals(text)
    extra_matches = [
        name for name, pattern in _SENSITIVE_PATTERNS.items() if pattern.search(text)
    ]
    return {"matched_categories": sorted({*base["matched_categories"], *extra_matches})}


def classify_privacy_status(matched_categories: list[str]) -> str:
    if any(category in _BLOCKING_CATEGORIES for category in matched_categories):
        return "blocked"
    if any(category in _REDACT_CATEGORIES for category in matched_categories):
        return "redacted"
    if matched_categories:
        return "requires_review"
    return "safe"


def redact_text(text: str, matched_categories: list[str]) -> str:
    """Best-effort redaction for the non-blocking categories only --
    blocked content is never redacted-and-kept, it is rejected outright
    by the caller before this would even run."""

    redacted = text
    if "absolute_path" in matched_categories:
        redacted = re.sub(
            r"(?:^|[\s\"])(?:/home/|/etc/|/usr/|/var/|[A-Za-z]:\\\\)\S*",
            " [redacted-path] ",
            redacted,
        )
    if "environment_variable_dump" in matched_categories:
        redacted = re.sub(r"\b[A-Z][A-Z0-9_]{3,}=\S+", "[redacted-env]", redacted)
    return redacted


def bounded_excerpt(text: str, *, maximum_length: int = _MAXIMUM_EXCERPT_LENGTH) -> str:
    collapsed = " ".join(text.strip().split())
    if len(collapsed) <= maximum_length:
        return collapsed
    return collapsed[:maximum_length].rstrip() + "..."


def assess_feedback_privacy(text: str) -> dict[str, Any]:
    """Returns status plus matched categories only -- never the raw
    matched substrings, which would defeat the purpose of the scan."""

    signals = detect_privacy_signals(text)
    status = classify_privacy_status(signals["matched_categories"])
    return {"status": status, "matched_categories": signals["matched_categories"]}
