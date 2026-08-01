"""Phase 19 Step 31 -- minimal, versioned, checksum-verified ambiguity
*supplemental* pattern set for mixed Tamil-English requests.

Not an edit to Phase 17's sealed classification policy -- a second,
independent, much narrower pattern set consulted only by
`PublicChatRoutingService` after Phase 17's own classification has
already run, and only when Phase 17 did *not* already recommend
`clarify`. It exists to close the one gap found during Phase 18's live
browser verification: "அதை apply செய்" (a Tamil unclear-pronoun object
+ an English instructional verb, with no stated referent) did not
trigger Phase 17's `AMBIGUOUS_UNCLEAR_PRONOUN` pattern.

Scope is deliberately narrow: the pattern requires an unclear Tamil
demonstrative pronoun ("அதை"/"இதை", "it"/"this") directly followed
(within a short span) by a bare English verb in an imperative/
infinitive shape, with **no** intervening noun that would supply a
referent. It must never fire on a normal, unambiguous mixed-language
sentence that already names its subject -- see the negative test
cases in `tests/core_model/test_public_chat_ambiguity_supplemental.py`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

SUPPLEMENTAL_AMBIGUITY_PATTERNS_VERSION = "v1"

_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "அதை apply செய்" / "இதை check பண்ணு" -- Tamil unclear-pronoun object
    # immediately followed by a bare English verb and a Tamil light-verb
    # ending, with nothing else in between (no named subject/object).
    re.compile(
        r"^\s*(அதை|இதை)\s+[a-zA-Z]{2,20}\s+(செய்|பண்ணு|பன்னு)[\w஀-௿]*\s*[?.!]?\s*$"
    ),
    # Latin-script Tanglish spelling of the same shape: "athai apply
    # seiy" / "idhai check pannu".
    re.compile(
        r"^\s*(athai|idhai)\s+[a-zA-Z]{2,20}\s+(sei\w*|pannu\w*|panu\w*)\s*[?.!]?\s*$",
        re.IGNORECASE,
    ),
)


def _compute_checksum() -> str:
    payload = "|".join(pattern.pattern for pattern in _PATTERNS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


SUPPLEMENTAL_AMBIGUITY_PATTERNS_CHECKSUM_SHA256 = _compute_checksum()


@dataclass(frozen=True)
class SupplementalAmbiguityResult:
    matched: bool
    reason_code: str | None = None


def evaluate_supplemental_ambiguity(text: str) -> SupplementalAmbiguityResult:
    for pattern in _PATTERNS:
        if pattern.match(text.strip()):
            return SupplementalAmbiguityResult(
                matched=True, reason_code="AMBIGUOUS_MIXED_LANGUAGE_UNCLEAR_PRONOUN_SUPPLEMENTAL"
            )
    return SupplementalAmbiguityResult(matched=False)


__all__ = [
    "SUPPLEMENTAL_AMBIGUITY_PATTERNS_CHECKSUM_SHA256",
    "SUPPLEMENTAL_AMBIGUITY_PATTERNS_VERSION",
    "SupplementalAmbiguityResult",
    "evaluate_supplemental_ambiguity",
]
