"""Phase 19 Step 31 -- minimal, versioned, checksum-verified safety
*supplemental* rule registry for the public chat input safety gate.

This is deliberately **not** an edit to Phase 17's sealed,
checksum-verified `classify_safety_signal()` policy -- that stays
untouched, so Phase 17's own 53-batch canonical regression remains
valid evidence for exactly what it always was. Instead, this is a
second, independent, much smaller pattern set that
`core_model.public_chat.input_safety.evaluate_input_safety()` consults
*in addition to* Phase 17's signal; either one recommending `refuse`
is enough to refuse.

Scope is intentionally narrow -- three specific phrasing gaps found
during Phase 18's live browser verification (see
`docs/smart_routing/phase18_public_safety_and_fallback_policy.md`
section 6): weapon-instruction paraphrases using compound nouns
("pipe bomb", "homemade explosive") that Phase 17's own pattern didn't
match, and explicit credential-stealing-malware requests. Patterns are
written to require an *instructional* framing (how to make/build/
write) so that benign discussion, defensive-security education, or
news mentions of the same nouns are never caught -- see the negative
test cases in `tests/core_model/test_public_chat_safety_supplemental.py`
for the exact benign phrases this must never block (malware detection
explanations, SQL-injection-defense explanations, government
criticism, historical/political discussion of explosives in a news
context).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

SUPPLEMENTAL_SAFETY_RULES_VERSION = "v1"

# (category, reason_code, compiled pattern) -- every pattern requires an
# instructional verb (make/build/create/write/develop) directly attached
# to the dangerous noun phrase, never a bare noun match.
_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "weapon_instruction",
        "SAFETY_WEAPON_INSTRUCTION_SUPPLEMENTAL",
        re.compile(
            r"\b(make|build|construct|assemble|create)\b.{0,25}\b(pipe\s*bomb|"
            r"homemade\s+explosive|home-made\s+explosive)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "weapon_instruction",
        "SAFETY_WEAPON_INSTRUCTION_SUPPLEMENTAL",
        re.compile(
            r"\b(pipe\s*bomb|homemade\s+explosive|home-made\s+explosive)\b.{0,25}"
            r"\b(how\s+(do|to)|instructions?|steps?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "malware_development",
        "SAFETY_CREDENTIAL_STEALING_MALWARE_SUPPLEMENTAL",
        re.compile(
            r"\b(write|build|create|develop|make)\b.{0,25}\b(malware|keylogger|"
            r"trojan|spyware)\b.{0,25}\b(steal\w*|harvest\w*|capture\w*|exfiltrate\w*)"
            r"\b.{0,15}\b(password|credential|login)",
            re.IGNORECASE,
        ),
    ),
    (
        "malware_development",
        "SAFETY_CREDENTIAL_STEALING_MALWARE_SUPPLEMENTAL",
        re.compile(
            r"\b(write|build|create|develop|make)\b.{0,15}\b(a\s+)?"
            r"(password|credential|login)[\s-]?steal(ing|er)\b",
            re.IGNORECASE,
        ),
    ),
)


def _compute_checksum() -> str:
    payload = "|".join(
        f"{category}:{reason}:{pattern.pattern}" for category, reason, pattern in _RULES
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


SUPPLEMENTAL_SAFETY_RULES_CHECKSUM_SHA256 = _compute_checksum()


@dataclass(frozen=True)
class SupplementalSafetyResult:
    matched: bool
    category: str | None = None
    reason_code: str | None = None


def evaluate_supplemental_safety(text: str) -> SupplementalSafetyResult:
    for category, reason_code, pattern in _RULES:
        if pattern.search(text):
            return SupplementalSafetyResult(
                matched=True, category=category, reason_code=reason_code
            )
    return SupplementalSafetyResult(matched=False)


__all__ = [
    "SUPPLEMENTAL_SAFETY_RULES_CHECKSUM_SHA256",
    "SUPPLEMENTAL_SAFETY_RULES_VERSION",
    "SupplementalSafetyResult",
    "evaluate_supplemental_safety",
]
