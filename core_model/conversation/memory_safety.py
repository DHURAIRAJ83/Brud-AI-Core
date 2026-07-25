"""Memory content safety scanning.

Detects secret-like and hidden-instruction content in a proposed
memory value. The most sensitive categories (medical, political,
religious, sexual, criminal, biometric, precise-location) are rejected
structurally by ``memory_items.category``'s CHECK constraint (see
``core_model.conversation.MEMORY_CATEGORIES`` -- they are simply never
members of the allowed set), not by content pattern-matching, which
would be unreliable for free-text detection. This module handles the
patterns that genuinely are detectable in text: passwords, API keys,
tokens, private keys, payment/banking details, cookies/auth headers,
absolute paths, environment-variable dumps, and hidden
instructions/prompt-injection content.
"""

from __future__ import annotations

import re
from typing import Any

_PASSWORD_PATTERN = re.compile(r"\bpassword\s*[:=]\s*\S+", re.IGNORECASE)
_API_KEY_PATTERN = re.compile(
    r"\b(api[_-]?key|secret[_-]?key)\s*[:=]\s*\S+|sk-[A-Za-z0-9]{16,}", re.IGNORECASE
)
_ACCESS_TOKEN_PATTERN = re.compile(
    r"\b(access[_-]?token|bearer)\s*[:=]?\s*\S+|Authorization:\s*Bearer\s+\S+", re.IGNORECASE
)
_PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_PAYMENT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_BANK_ACCOUNT_PATTERN = re.compile(
    r"\b(account|iban|routing)[_ ]?(number|no)?\s*[:=]\s*\S+", re.IGNORECASE
)
_COOKIE_PATTERN = re.compile(r"\b(session[_-]?id|cookie)\s*[:=]\s*\S+", re.IGNORECASE)
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|[\s\"])(?:/home/|/etc/|/usr/|/var/|[A-Za-z]:\\\\)\S*")
_ENV_DUMP_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{3,}=\S+")
_HIDDEN_INSTRUCTION_PATTERN = re.compile(
    r"ignore (all |previous |prior )?instructions|reveal (the |your )?(system prompt|hidden prompt)"
    r"|act as (the )?system|change (the )?memory policy|delete (the )?logs"
    r"|retrieve another (user|participant)'?s? (data|memory)|execute the following command",
    re.IGNORECASE,
)

_ALL_PATTERNS = {
    "password": _PASSWORD_PATTERN,
    "api_key": _API_KEY_PATTERN,
    "access_token": _ACCESS_TOKEN_PATTERN,
    "private_key": _PRIVATE_KEY_PATTERN,
    "payment_card": _PAYMENT_CARD_PATTERN,
    "bank_account": _BANK_ACCOUNT_PATTERN,
    "authentication_cookie": _COOKIE_PATTERN,
    "absolute_path": _ABSOLUTE_PATH_PATTERN,
    "environment_variable_dump": _ENV_DUMP_PATTERN,
    "hidden_instruction": _HIDDEN_INSTRUCTION_PATTERN,
}

_BLOCKING_CATEGORIES = {
    "password", "api_key", "access_token", "private_key", "payment_card",
    "bank_account", "authentication_cookie", "hidden_instruction",
}
_WARNING_CATEGORIES = {"absolute_path", "environment_variable_dump"}


def detect_safety_signals(text: str) -> dict[str, Any]:
    matched = [name for name, pattern in _ALL_PATTERNS.items() if pattern.search(text)]
    return {"matched_categories": sorted(matched)}


def classify_safety_status(matched_categories: list[str]) -> str:
    if any(category in _BLOCKING_CATEGORIES for category in matched_categories):
        return "blocked"
    if any(category in _WARNING_CATEGORIES for category in matched_categories):
        return "warning"
    return "safe"


def assess_memory_safety(text: str) -> dict[str, Any]:
    signals = detect_safety_signals(text)
    status = classify_safety_status(signals["matched_categories"])
    return {"status": status, "matched_categories": signals["matched_categories"]}
