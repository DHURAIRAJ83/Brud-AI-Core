"""Deterministic ambiguity / clarification-need detection (Step 7).

Small, bounded, explicit rule checks -- never "every short sentence is
ambiguous" (Step 23's own false-positive control: a short but complete
question like "987654 x 12345" or "18748 English words" must never be
flagged, since it contains no pronoun, no bare action verb, and no
unknown acronym). At most one clarifying signal is ever reported as the
primary `matched_category`, even if more than one rule fires.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core_model.knowledge_routing import POLICY_VERSION

_BARE_PRONOUN_SUBJECTS = ("it", "that", "this", "they", "அது", "இது", "அவை")
_WH_STARTERS = (
    "what about", "how about", "why", "how", "what", "when", "where",
    "ஏன்", "எப்படி", "என்ன",
)

_BARE_ACTION_VERBS = (
    "fix", "update", "delete", "remove", "change", "apply", "submit", "cancel", "reset",
    "மாற்று", "நீக்கு", "சமர்ப்பி",
)

_KNOWN_ACRONYMS = frozenset(
    {
        "AI", "API", "RAG", "GST", "PAN", "UPI", "OTP", "FAQ", "URL", "PDF", "SQL", "CPU",
        "GPU", "CSV", "JSON", "HTTP", "HTTPS", "TN", "ID",
    }
)
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,4}\b")

_CONFLICT_PAIRS = (
    ("enable", "disable"), ("turn on", "turn off"), ("start", "stop"), ("allow", "block"),
)

# Minimum token count above which a bare-pronoun-subject match is ignored --
# a long sentence using "it" mid-sentence with other nouns present is not
# the same ambiguity risk as a 2-3 word fragment.
_SHORT_FRAGMENT_TOKEN_LIMIT = 6


@dataclass(frozen=True)
class AmbiguityResult:
    value: str  # "ambiguous" | "not_ambiguous"
    matched_category: str | None
    confidence_band: str
    reason_codes: tuple[str, ...]
    matched_rules: tuple[str, ...]
    policy_version: str
    secondary_values: tuple[str, ...] = field(default_factory=tuple)


def _token_count(text: str) -> int:
    return len([t for t in text.split() if t.strip()])


def classify_ambiguity(text: str) -> AmbiguityResult:
    text_lower = text.lower().strip()
    tokens = [t.strip(".,!?;:\"'()") for t in text_lower.split() if t.strip()]
    token_count = len(tokens)

    for enable_word, disable_word in _CONFLICT_PAIRS:
        if enable_word in text_lower and disable_word in text_lower:
            return AmbiguityResult(
                value="ambiguous",
                matched_category="conflicting_instruction",
                confidence_band="high",
                reason_codes=("AMBIGUOUS_CONFLICTING_INSTRUCTION",),
                matched_rules=(enable_word, disable_word),
                policy_version=POLICY_VERSION,
            )

    if token_count <= _SHORT_FRAGMENT_TOKEN_LIMIT:
        starts_with_wh = any(text_lower.startswith(starter) for starter in _WH_STARTERS)
        has_bare_pronoun = any(pronoun in tokens for pronoun in _BARE_PRONOUN_SUBJECTS)
        if starts_with_wh and has_bare_pronoun:
            return AmbiguityResult(
                value="ambiguous",
                matched_category="unclear_pronoun",
                confidence_band="medium",
                reason_codes=("AMBIGUOUS_UNCLEAR_PRONOUN",),
                matched_rules=tuple(p for p in _BARE_PRONOUN_SUBJECTS if p in tokens),
                policy_version=POLICY_VERSION,
            )

        if tokens and tokens[0] in _BARE_ACTION_VERBS and token_count <= 2:
            return AmbiguityResult(
                value="ambiguous",
                matched_category="incomplete_action",
                confidence_band="medium",
                reason_codes=("AMBIGUOUS_INCOMPLETE_ACTION",),
                matched_rules=(tokens[0],),
                policy_version=POLICY_VERSION,
            )

    acronym_hits = tuple(
        match for match in _ACRONYM_RE.findall(text) if match not in _KNOWN_ACRONYMS
    )
    if acronym_hits and token_count <= _SHORT_FRAGMENT_TOKEN_LIMIT:
        return AmbiguityResult(
            value="ambiguous",
            matched_category="unknown_acronym",
            confidence_band="low",
            reason_codes=("AMBIGUOUS_UNKNOWN_ACRONYM",),
            matched_rules=acronym_hits,
            policy_version=POLICY_VERSION,
        )

    return AmbiguityResult(
        value="not_ambiguous",
        matched_category=None,
        confidence_band="medium",
        reason_codes=("NOT_AMBIGUOUS_DETERMINISTIC_ROUTE",),
        matched_rules=(),
        policy_version=POLICY_VERSION,
    )


__all__ = ["AmbiguityResult", "classify_ambiguity"]
