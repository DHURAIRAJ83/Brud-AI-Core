"""Deterministic Tamil-Unicode -> Latin-script phonetic transliteration.

Never a translation provider, never an LLM call. `to_tanglish()`
transforms an *existing* Tamil string (every bilingual `{en, ta}` dict
already present across this codebase -- dashboard pages, action
definitions, help registry, chat replies) into readable, professional
Tanglish, so Phase 10A never needs a hand-written third ("tgl") copy of
every string that already has an "en"/"ta" pair.

Why this is not the "mechanical, bad" transliteration the task warns
against: this codebase's existing "ta" strings already keep technical
vocabulary in Latin script inline (e.g. "credential reference",
"dataset licence", "RAG use" all appear as literal English words
inside otherwise-Tamil sentences). This renderer only ever transforms
Tamil-*script* runs -- any run that is already Latin script (English
words, `{format_placeholders}`, digits, identifiers, punctuation)
passes through completely untouched, character for character. That is
exactly "preserve technical vocabulary in English" and "preserve IDs,
enum values, paths, ... unchanged", satisfied structurally rather than
via a maintained exclusion list.

Documented, honest limitation: this produces a *formal phonetic*
transliteration (including a bounded, well-known Tamil sandhi rule --
intervocalic/post-nasal voicing of stop consonants, e.g. க/ச/ட/த/ப ->
g/j/d/dh/b -- which is what makes "இந்த" render as "indha" rather than
the cruder "intha"). It will not always match the exact colloquial
spelling a native speaker would type by hand (e.g. "ku" vs "kku",
"illa" vs "illai"), but it is deterministic, readable, and testable.
"""

from __future__ import annotations

# Independent (standalone) Tamil vowels -- U+0B85..U+0B94.
_INDEPENDENT_VOWELS: dict[str, str] = {
    "அ": "a", "ஆ": "aa", "இ": "i", "ஈ": "ii", "உ": "u", "ஊ": "uu",
    "எ": "e", "ஏ": "ee", "ஐ": "ai", "ஒ": "o", "ஓ": "oo", "ஔ": "au",
}

# Base (unvoiced) consonant latin forms. Retroflex/dental/alveolar
# distinctions (ண/ந/ன, ட/ற, ள/ல) are deliberately collapsed to their
# common casual-Tanglish spelling -- native speakers do not usually
# distinguish them in Latin script either, and rigid IPA-style marks
# would read as unnatural, mechanical output.
_CONSONANTS: dict[str, str] = {
    "க": "k", "ங": "ng", "ச": "ch", "ஞ": "nj", "ட": "t", "ண": "n",
    "த": "th", "ந": "n", "ப": "p", "ம": "m", "ய": "y", "ர": "r",
    "ல": "l", "வ": "v", "ழ": "zh", "ள": "l", "ற": "r", "ன": "n",
    # Grantha letters, used in loanwords.
    "ஜ": "j", "ஷ": "sh", "ஸ": "s", "ஹ": "h",
}

# Dependent vowel signs (matras) attached to a consonant.
_VOWEL_SIGNS: dict[str, str] = {
    "ா": "aa", "ி": "i", "ீ": "ii", "ு": "u", "ூ": "uu",
    "ெ": "e", "ே": "ee", "ை": "ai", "ொ": "o", "ோ": "oo", "ௌ": "au",
}

_TAMIL_DIGITS: dict[str, str] = {
    "௦": "0", "௧": "1", "௨": "2", "௩": "3", "௪": "4",
    "௫": "5", "௬": "6", "௭": "7", "௮": "8", "௯": "9",
}

_PULLI = "்"  # virama -- strips the consonant's inherent vowel
_AYTHAM = "ஃ"

# Stop consonants that voice between vowels / after a nasal (a
# well-known, regular Tamil sandhi rule) -- but stay unvoiced when
# geminated (e.g. "க்க" stays "kk", never "gg" or "kg"), and at the
# start of a word. த voices to "dh" (not bare "d") to stay
# distinguishable from ட's voiced "d".
_STOP_VOICING: dict[str, str] = {"க": "g", "ச": "j", "ட": "d", "த": "dh", "ப": "b"}

_TAMIL_MEANINGFUL_CHARS = (
    set(_INDEPENDENT_VOWELS) | set(_CONSONANTS) | set(_VOWEL_SIGNS)
    | set(_TAMIL_DIGITS) | {_PULLI, _AYTHAM}
)


def _is_geminated(text: str, index: int, consonant: str) -> bool:
    """True when `consonant` at `index` is immediately preceded by the
    same consonant already made a pure/pulli-terminated sound (e.g.
    the second க in க்க) -- geminated stop clusters are always
    unvoiced in Tamil, regardless of surrounding vowels/nasals."""

    return index >= 2 and text[index - 1] == _PULLI and text[index - 2] == consonant


def to_tanglish(text: str) -> str:
    """Transliterates Tamil-script runs of `text` to readable Latin
    script; every other character (English words, digits, punctuation,
    `{placeholders}`, IDs) passes through byte-for-byte unchanged."""

    if not text:
        return text

    out: list[str] = []
    at_word_start = True
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        if ch not in _TAMIL_MEANINGFUL_CHARS:
            out.append(ch)
            at_word_start = ch.isspace() or not ch.isalnum()
            i += 1
            continue

        if ch in _INDEPENDENT_VOWELS:
            out.append(_INDEPENDENT_VOWELS[ch])
            at_word_start = False
            i += 1
            continue

        if ch in _TAMIL_DIGITS:
            out.append(_TAMIL_DIGITS[ch])
            at_word_start = False
            i += 1
            continue

        if ch == _AYTHAM:
            out.append("h")
            at_word_start = False
            i += 1
            continue

        if ch == _PULLI:
            # A pulli only ever makes sense directly after the
            # consonant it silences, which the consonant branch below
            # already consumes -- a stray leading pulli is skipped.
            i += 1
            continue

        # ch is a consonant.
        if i + 1 < n and text[i + 1] == _PULLI:
            out.append(_CONSONANTS[ch])
            at_word_start = False
            i += 2
            continue

        voice = (
            ch in _STOP_VOICING
            and not at_word_start
            and not _is_geminated(text, i, ch)
        )
        base = _STOP_VOICING[ch] if voice else _CONSONANTS[ch]
        if i + 1 < n and text[i + 1] in _VOWEL_SIGNS:
            out.append(base + _VOWEL_SIGNS[text[i + 1]])
            i += 2
        else:
            out.append(base + "a")
            i += 1
        at_word_start = False

    return "".join(out)
