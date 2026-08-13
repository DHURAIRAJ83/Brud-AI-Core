"""MB-04A: Tanglish -> Tamil word-level normalization.

A fixed, deterministic lookup dictionary -- never a transliteration
model, never AI. Coverage is intentionally practical rather than
exhaustive: common everyday Tanglish connector words plus the Brud
Admin domain vocabulary (dataset, training, workflow, etc.) most
likely to appear in Admin questions. This is used ONLY internally (to
strengthen language-signal and knowledge-search grounding before
prompting the model) -- normalized text is never shown to the user,
per MB-04A's own instruction.
"""

from __future__ import annotations

import re

# Longest phrases first so multi-word idioms match before their
# individual words would. Matching is case-insensitive, word-boundary.
TANGLISH_TO_TAMIL: dict[str, str] = {
    # common connectors / grammar words
    "epadi": "எப்படி", "eppadi": "எப்படி", "epadiya": "எப்படியா",
    "pannalam": "பண்ணலாம்", "pannunga": "பண்ணுங்க", "panren": "பண்றேன்",
    "panra": "பண்ற", "pannanum": "பண்ணணும்", "pannuvom": "பண்ணுவோம்",
    "panniten": "பண்ணிட்டேன்",
    "venum": "வேண்டும்", "vendum": "வேண்டும்", "vendaam": "வேண்டாம்",
    "venaam": "வேண்டாம்",
    "irukku": "இருக்கு", "irukka": "இருக்க", "irukkanum": "இருக்கணும்",
    "iruku": "இருக்கு",
    "illa": "இல்ல", "illai": "இல்லை", "illainu": "இல்லைனு",
    "seyya": "செய்ய", "seiya": "செய்ய", "seiyanum": "செய்யணும்",
    "sollunga": "சொல்லுங்க", "sollu": "சொல்லு", "solra": "சொல்ற",
    "kudu": "குடு", "kudukka": "குடுக்க", "kudunga": "குடுங்க",
    "edhu": "எது", "yedhu": "எது", "enna": "என்ன", "yenna": "என்ன",
    "ippo": "இப்போ", "ippove": "இப்போவே",
    "apparam": "அப்பறம்", "appuram": "அப்புறம்",
    "mattum": "மட்டும்", "matum": "மட்டும்",
    "ellam": "எல்லாம்", "ellaam": "எல்லாம்",
    "romba": "ரொம்ப", "rompa": "ரொம்ப",
    "nalla": "நல்ல",
    "korachu": "கொஞ்சம்", "konjam": "கொஞ்சம்", "kunjam": "கொஞ்சம்",
    "thevai": "தேவை", "thevaiya": "தேவையா",
    "mudiyuma": "முடியுமா", "mudiyum": "முடியும்", "mudiyala": "முடியல",
    "epo": "எப்போ", "evlo": "எவ்ளோ", "evalo": "எவ்ளோ",
    "yaaru": "யாரு", "yaru": "யாரு",
    "enga": "எங்க", "engeyum": "எங்கேயும்",
    "seri": "சரி", "sari": "சரி",
    "aama": "ஆமா", "aamam": "ஆமாம்",
    "illainga": "இல்லைங்க",
    "vaanga": "வாங்க", "poga": "போக", "pogalam": "போகலாம்",
    "paaru": "பாரு", "paakalam": "பார்க்கலாம்",
    "theriyuma": "தெரியுமா", "theriyum": "தெரியும்",
    "puriyuthu": "புரியுது", "puriyala": "புரியல",
    # Brud/Admin domain vocabulary
    "dataset": "தரவுத்தொகுப்பு", "datasets": "தரவுத்தொகுப்புகள்",
    "training": "பயிற்சி", "tokenizer": "டோக்கனைசர்",
    "model": "மாடல்", "workflow": "பணிப்பாய்வு",
    "dashboard": "டாஷ்போர்டு", "admin": "நிர்வாகி",
    "settings": "அமைப்புகள்", "prepare": "தயார் செய்",
    "create": "உருவாக்கு", "start": "தொடங்கு", "check": "சரிபார்",
}

_PHRASE_KEYS_BY_LENGTH = sorted(TANGLISH_TO_TAMIL, key=len, reverse=True)
_WORD_TOKEN_RE = re.compile(r"[A-Za-z']+|[^A-Za-z']+")


def normalize_tanglish(text: str) -> str:
    """Word-level substitution, longest-key-first, case-insensitive,
    preserving everything that isn't a matched Tanglish word (Tamil
    script, punctuation, numbers, unmatched English words) exactly as
    written. Internal use only -- never surfaced to the user."""

    tokens = _WORD_TOKEN_RE.findall(text)
    out: list[str] = []
    for token in tokens:
        lowered = token.lower()
        replacement = TANGLISH_TO_TAMIL.get(lowered)
        out.append(replacement if replacement is not None else token)
    return "".join(out)


def normalization_coverage(text: str) -> dict[str, object]:
    """Diagnostic: how much of the Latin-script word content in this
    text was actually recognized and normalized, so callers/tests can
    see coverage gaps rather than assume full normalization happened."""

    words = re.findall(r"[A-Za-z']+", text)
    latin_words = [w for w in words]
    matched = [w for w in latin_words if w.lower() in TANGLISH_TO_TAMIL]
    return {
        "latin_word_count": len(latin_words),
        "matched_word_count": len(matched),
        "unmatched_words": sorted({w for w in latin_words if w.lower() not in TANGLISH_TO_TAMIL}),
    }
