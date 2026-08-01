"""Phase 19 Step 6 -- privacy-redacted canonical question generation.

Reuses `core_model.corpus.secret_detection.detect_secrets()` and
`core_model.corpus.pii_detection.detect_pii()` verbatim for detection;
applies Phase 19's own Step-6 placeholder vocabulary
(`core_model.knowledge_gap.REDACTION_PLACEHOLDERS`) rather than the
corpus module's `<X_REDACTED>` tokens (a presentation-layer choice for
this registry's own review UI, not new detection logic -- see the plan
doc section 5). A genuine secret hit is never redacted-and-kept, honoring
`secret_detection.py`'s own "always block" policy: the case falls back
to `content_unavailable_for_review=True` with only a hash retained.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from core_model.corpus.pii_detection import detect_pii, redact_pii
from core_model.corpus.secret_detection import detect_secrets
from core_model.knowledge_gap import REDACTION_PLACEHOLDERS

# Remaps `pii_detection.redact_pii()`'s own `<X_REDACTED>` placeholder
# vocabulary onto Step 6's `[X]` vocabulary -- a presentation-layer
# substitution over the module's public output, never a second
# detection/redaction implementation.
_CORPUS_PLACEHOLDER_TO_STEP6 = {
    "<EMAIL_REDACTED>": REDACTION_PLACEHOLDERS["email"],
    "<PHONE_REDACTED>": REDACTION_PLACEHOLDERS["phone"],
    "<PERSONAL_ID_REDACTED>": REDACTION_PLACEHOLDERS["identifier"],
    "<ADDRESS_REDACTED>": REDACTION_PLACEHOLDERS["address"],
}
_PII_FINDING_CATEGORY = {
    "email": "email",
    "phone": "phone",
    "aadhaar_like": "identifier",
    "pan_like": "identifier",
    "passport_like": "identifier",
    "precise_address": "address",
    "personal_medical_record": "identifier",
}

_SELF_INTRODUCTION_PATTERNS = (
    re.compile(r"\bmy name is\s+[A-Za-z][A-Za-z .'-]{1,60}", re.IGNORECASE),
    re.compile(r"\bi am\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
    re.compile(r"நான்\s+[஀-௿]{2,30}\s+(என்பவன்|என்பவள்|என்று)"),
)

_PRIVATE_CONTEXT_PATTERNS = (
    re.compile(r"\bthat (thing|stuff) i told you\b", re.IGNORECASE),
    re.compile(r"\bwhat i (said|mentioned) (before|earlier)\b", re.IGNORECASE),
    re.compile(r"நான்\s+முன்பு\s+(சொன்ன|கூறிய)"),
)


@dataclass(frozen=True)
class PrivacyResult:
    input_hash: str
    redacted_question: str | None
    content_unavailable_for_review: bool
    redaction_categories: tuple[str, ...] = field(default_factory=tuple)


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _redact_person(text: str) -> tuple[str, bool]:
    changed = False
    for pattern in _SELF_INTRODUCTION_PATTERNS:
        if pattern.search(text):
            text = pattern.sub(REDACTION_PLACEHOLDERS["person"], text)
            changed = True
    return text, changed


def _redact_private_context(text: str, *, involves_memory: bool) -> tuple[str, bool]:
    if not involves_memory:
        return text, False
    changed = False
    for pattern in _PRIVATE_CONTEXT_PATTERNS:
        if pattern.search(text):
            text = pattern.sub(REDACTION_PLACEHOLDERS["private_context"], text)
            changed = True
    return text, changed


class KnowledgeGapPrivacyService:
    """Stateless -- every method is a pure function over its input text."""

    def process(self, text: str, *, involves_memory: bool = False) -> PrivacyResult:
        input_hash = _hash(text)

        secrets = detect_secrets(text)
        if secrets["status"] == "blocked":
            return PrivacyResult(
                input_hash=input_hash,
                redacted_question=None,
                content_unavailable_for_review=True,
                redaction_categories=("secret",),
            )

        categories: list[str] = []

        pii = detect_pii(text)
        findings = pii["findings"]
        working = redact_pii(text, findings) if findings else text
        for corpus_placeholder, step6_placeholder in _CORPUS_PLACEHOLDER_TO_STEP6.items():
            if corpus_placeholder in working:
                working = working.replace(corpus_placeholder, step6_placeholder)
        categories.extend(
            _PII_FINDING_CATEGORY[category]
            for category in findings
            if category in _PII_FINDING_CATEGORY
        )

        working, person_changed = _redact_person(working)
        if person_changed:
            categories.append("person")

        working, private_context_changed = _redact_private_context(
            working, involves_memory=involves_memory
        )
        if private_context_changed:
            categories.append("private_context")

        if secrets["status"] == "requires_review":
            # A weaker, non-blocking secret-adjacent signal (e.g. a bare
            # session-id-shaped token with low confidence) -- safer to
            # withhold the redacted text entirely than guess at a
            # placeholder substitution for a pattern this module itself
            # only rates "requires review", not a confirmed match.
            return PrivacyResult(
                input_hash=input_hash,
                redacted_question=None,
                content_unavailable_for_review=True,
                redaction_categories=tuple(sorted(set(categories)) or ("secret",)),
            )

        return PrivacyResult(
            input_hash=input_hash,
            redacted_question=working,
            content_unavailable_for_review=False,
            redaction_categories=tuple(sorted(set(categories))),
        )


__all__ = ["KnowledgeGapPrivacyService", "PrivacyResult"]
