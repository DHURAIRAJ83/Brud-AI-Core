"""Deterministic, script-based language-compliance evaluation.

Reuses the exact Tamil/Latin script regexes Phase 11/12 already
established (never redefines them). Tanglish is always its own category —
Latin-script text is never classified as English purely by script; a small,
explicit lexical-pattern list is used to give Tanglish its own honest,
bounded signal instead of folding it into "English" or "unknown."
"""

from __future__ import annotations

from core_model.model_evaluation import FAIL, NOT_EVALUATED, PASS, WARNING
from core_model.training.dataset_profile import LATIN_PATTERN, TAMIL_PATTERN

# A small, explicit set of common Tanglish (Latin-script transliterated Tamil)
# word endings/particles. This is a bounded lexical heuristic, not a language
# model — it exists only to distinguish Tanglish from plain English text,
# both of which are Latin-script.
TANGLISH_MARKERS = (
    "nu", "na", "da", "pa", "ku", "la", "ah", "aa", "dhaan", "than",
    "irukku", "iruken", "irukan", "vanga", "poren", "ponga", "saptu",
    "epdi", "eppadi", "sollu", "solunga", "vendam", "venum", "illa",
)

ROLE_TOKENS = ("<system>", "<user>", "<assistant>")
LANGUAGE_MARKER_TOKENS = ("<ta>", "<en>", "<tgl>", "<mixed>")


def script_ratios(text: str) -> dict[str, float]:
    length = len(text) or 1
    tamil = len(TAMIL_PATTERN.findall(text))
    latin = len(LATIN_PATTERN.findall(text))
    return {
        "tamil_script_ratio": tamil / length,
        "latin_script_ratio": latin / length,
        "mixed_script_ratio": (1.0 if tamil and latin else 0.0),
    }


def tanglish_lexical_score(text: str) -> float:
    tokens = [token.strip(".,!?").lower() for token in text.split()]
    tokens = [token for token in tokens if token]
    if not tokens:
        return 0.0
    hits = sum(
        1 for token in tokens if any(token == m or token.endswith(m) for m in TANGLISH_MARKERS)
    )
    return hits / len(tokens)


def language_marker_leakage(text: str) -> list[str]:
    return [token for token in LANGUAGE_MARKER_TOKENS if token in text]


def evaluate_language_compliance(
    text: str,
    expected_language: str,
    *,
    min_script_ratio: float = 0.2,
    min_tanglish_score: float = 0.03,
) -> dict:
    """Deterministic, script/lexical-based — never an external language-detection model."""

    if not text.strip():
        return {
            "status": FAIL,
            "message": "empty response",
            "expected_language": expected_language,
            "tamil_script_ratio": 0.0,
            "latin_script_ratio": 0.0,
            "mixed_script_ratio": 0.0,
            "tanglish_lexical_score": 0.0,
            "language_marker_leakage": [],
        }

    ratios = script_ratios(text)
    tanglish_score = tanglish_lexical_score(text)
    markers = language_marker_leakage(text)

    if expected_language == "ta":
        respected = ratios["tamil_script_ratio"] >= min_script_ratio
    elif expected_language == "en":
        respected = (
            ratios["latin_script_ratio"] >= min_script_ratio
            and tanglish_score < min_tanglish_score
        )
    elif expected_language == "tgl":
        respected = ratios["latin_script_ratio"] >= min_script_ratio
        # Tanglish is reported honestly: if lexical markers are absent we still
        # accept Latin-script text as "not disproven Tanglish" (uncertain, not
        # a hard failure), since a bounded lexical list cannot exhaustively
        # cover all Tanglish phrasing.
    elif expected_language == "mixed":
        respected = ratios["tamil_script_ratio"] > 0 or ratios["latin_script_ratio"] > 0
    else:
        return {
            "status": NOT_EVALUATED,
            "message": f"unrecognized expected_language: {expected_language}",
            **ratios,
            "tanglish_lexical_score": tanglish_score,
            "language_marker_leakage": markers,
        }

    status = PASS if respected else FAIL
    if respected and markers:
        status = WARNING

    return {
        "status": status,
        "message": "language compliance evaluated",
        "expected_language": expected_language,
        **ratios,
        "tanglish_lexical_score": tanglish_score,
        "language_marker_leakage": markers,
    }
