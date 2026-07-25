"""Exact and normalized-duplicate detection via deterministic checksums.

Every checksum variant is computed the same way every time -- there is
no randomness anywhere in this module, so the same corpus always
produces the same duplicate clusters.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WHITESPACE_PATTERN = re.compile(r"\s+")
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s஀-௿]")


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def raw_checksum(text: str) -> str:
    return _checksum(text)


def whitespace_insensitive_checksum(text: str) -> str:
    return _checksum(_WHITESPACE_PATTERN.sub(" ", text).strip())


def punctuation_normalized_checksum(text: str) -> str:
    collapsed = _WHITESPACE_PATTERN.sub(" ", _PUNCTUATION_PATTERN.sub("", text)).strip()
    return _checksum(collapsed)


def case_normalized_checksum(text: str) -> str:
    """Lowercases Latin runs only -- Tamil has no case distinction, so
    this never touches Tamil-script characters."""

    lowered = "".join(char.lower() if "A" <= char <= "Z" else char for char in text)
    return _checksum(_WHITESPACE_PATTERN.sub(" ", lowered).strip())


def tamil_safe_normalized_checksum(text: str) -> str:
    """NFC-normalizes then applies the same whitespace/punctuation
    collapsing as the other normalized checksums -- never strips Tamil
    combining marks, since NFC never removes them (see
    ``unicode_normalization.py``)."""

    nfc = unicodedata.normalize("NFC", text)
    collapsed = _WHITESPACE_PATTERN.sub(" ", _PUNCTUATION_PATTERN.sub("", nfc)).strip()
    return _checksum(collapsed)


def all_checksums(text: str) -> dict[str, str]:
    return {
        "raw": raw_checksum(text),
        "whitespace_insensitive": whitespace_insensitive_checksum(text),
        "punctuation_normalized": punctuation_normalized_checksum(text),
        "case_normalized": case_normalized_checksum(text),
        "tamil_safe_normalized": tamil_safe_normalized_checksum(text),
    }


def classify_exact_duplicate(
    candidate_checksums: dict[str, str], existing_checksums: list[dict[str, str]]
) -> dict[str, str | None]:
    """Returns the single most specific status:
    ``exact_duplicate`` (raw checksum matches) beats
    ``normalized_duplicate`` (any normalized variant matches) beats
    ``unique``."""

    for existing in existing_checksums:
        if candidate_checksums["raw"] == existing["raw"]:
            return {"status": "exact_duplicate", "matched_reference": existing.get("reference")}
    for existing in existing_checksums:
        if any(
            candidate_checksums[key] == existing[key]
            for key in ("whitespace_insensitive", "punctuation_normalized", "case_normalized",
                        "tamil_safe_normalized")
        ):
            return {
                "status": "normalized_duplicate",
                "matched_reference": existing.get("reference"),
            }
    return {"status": "unique", "matched_reference": None}
