"""Phase 15: Centralized, deterministic Text/NLP processing pipeline for Brud AI.

Reuses existing repository capabilities:
- Language detection: core_model.mini_brain.prompting.language_detector
- Tanglish normalization: core_model.mini_brain.prompting.tanglish_normalizer
- Text normalization: core_model.rag.text_normalization
- Language policy: core_model.public_chat.language_policy

Strictly read-only, side-effect free, deterministic, and fail-closed.
Performs no database writes, no tool calls, no subprocesses, and no network calls.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from core_model.mini_brain.prompting.language_detector import detect_language
from core_model.mini_brain.prompting.tanglish_normalizer import normalize_tanglish
from core_model.rag.text_normalization import normalize_source_text

NLP_NORMALIZATION_VERSION = "v1.0"

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_SQL_PATTERN = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|CREATE TABLE)\b", re.IGNORECASE)
_CODE_COMMAND_PATTERN = re.compile(r"\b(git|npm|pip|python3?|pytest|docker|curl|wget|cd|ls|mkdir|chmod|sudo|systemctl)\b")
_CODE_SYNTAX_PATTERN = re.compile(r"[{}\[\];()=>|&<>]|\b(def|class|import|return|function|const|let|var|if|else|for|while)\b")
_WORD_TOKEN_RE = re.compile(r"\w+|\S")


@dataclass(frozen=True)
class NLPResult:
    original_text: str
    normalized_text: str
    detected_language: str  # "ta", "en", "tanglish", "mixed", "unknown"
    language_confidence: float
    is_tanglish: bool
    is_mixed_language: bool
    is_technical_code: bool
    normalization_applied: bool
    normalization_notes: tuple[str, ...]
    tokens: tuple[str, ...]
    nlp_normalization_version: str = NLP_NORMALIZATION_VERSION


def is_code_or_technical_text(text: str) -> bool:
    """Returns True if the text contains code snippets, URLs, emails, SQL,
    or shell commands that must be protected from linguistic transformation.
    """
    if not text or not text.strip():
        return False
    if _URL_PATTERN.search(text) or _EMAIL_PATTERN.search(text):
        return True
    if _SQL_PATTERN.search(text):
        return True
    if _CODE_COMMAND_PATTERN.search(text) and (" " in text or "/" in text or "-" in text):
        return True
    if _CODE_SYNTAX_PATTERN.search(text) and len(re.findall(r"[{}\[\];()=>]", text)) >= 2:
        return True
    return False


def _compute_confidence(analysis: dict[str, Any], lang: str) -> float:
    """Computes a deterministic 0.0 - 1.0 confidence score from the
    underlying language_detector analysis dict."""
    if lang == "unknown":
        return 0.0

    tamil_ratio = float(analysis.get("tamil_ratio", 0.0))
    eff_ratio = float(analysis.get("effective_tamil_ratio", 0.0))
    tanglish_words = analysis.get("tanglish_signal_words", [])

    if lang == "ta":
        return round(min(0.5 + (tamil_ratio * 0.5), 1.0), 2)
    elif lang == "en":
        latin_chars = int(analysis.get("latin_char_count", 0))
        if latin_chars > 0 and not tanglish_words:
            return 0.95 if latin_chars > 10 else 0.85
        return 0.70
    elif lang == "tanglish":
        word_count = len(tanglish_words)
        if word_count >= 3:
            return 0.95
        elif word_count >= 1:
            return 0.85
        return 0.65
    elif lang == "mixed":
        return round(min(0.60 + (eff_ratio * 0.30), 0.95), 2)

    return 0.50


def process_text(
    text: str | None,
    *,
    apply_tanglish_normalization: bool = True,
) -> NLPResult:
    """Centralized, deterministic Text/NLP processing pipeline.

    Performs:
    1. Input validation & null/empty safety
    2. Unicode NFC & control-character normalization
    3. Technical code & command protection
    4. Language & Tanglish detection
    5. Conditional Tanglish-to-Tamil normalization
    6. Tokenization
    7. Fail-closed, structured NLPResult compilation
    """
    if text is None:
        raw_text = ""
    else:
        raw_text = str(text)

    notes: list[str] = []

    if not raw_text or not raw_text.strip():
        return NLPResult(
            original_text=raw_text,
            normalized_text="",
            detected_language="unknown",
            language_confidence=0.0,
            is_tanglish=False,
            is_mixed_language=False,
            is_technical_code=False,
            normalization_applied=False,
            normalization_notes=("empty_input",),
            tokens=(),
        )

    # 1. Unicode & Source Normalization
    source_norm = normalize_source_text(raw_text)
    norm_text = source_norm["normalized_text"]
    notes.append("unicode_nfc_and_whitespace_normalized")

    # 2. Technical Code Protection
    is_tech = is_code_or_technical_text(raw_text)
    if is_tech:
        notes.append("technical_code_protected")

    # 3. Language Detection
    lang_analysis = detect_language(norm_text)
    raw_lang = str(lang_analysis.get("language", "english"))

    # Map internal label to standard taxonomy: "tamil" -> "ta", "english" -> "en"
    if raw_lang == "tamil":
        detected_language = "ta"
    elif raw_lang == "english":
        detected_language = "en"
    elif raw_lang == "tanglish":
        detected_language = "tanglish"
    elif raw_lang == "mixed":
        detected_language = "mixed"
    else:
        detected_language = "unknown"

    # If non-alphabetic
    if lang_analysis.get("tamil_char_count", 0) == 0 and lang_analysis.get("latin_char_count", 0) == 0:
        detected_language = "unknown"

    is_tgl = (detected_language == "tanglish")
    is_mix = (detected_language == "mixed")
    confidence = _compute_confidence(lang_analysis, detected_language)

    # 4. Tanglish Normalization (if applicable & not technical code)
    final_text = norm_text
    normalization_applied = False

    if (is_tgl or is_mix) and apply_tanglish_normalization and not is_tech:
        tanglish_norm = normalize_tanglish(norm_text)
        if tanglish_norm != norm_text:
            final_text = tanglish_norm
            normalization_applied = True
            notes.append("tanglish_to_tamil_normalized")

    # 5. Tokenization
    tokens = tuple(_WORD_TOKEN_RE.findall(final_text))

    return NLPResult(
        original_text=raw_text,
        normalized_text=final_text,
        detected_language=detected_language,
        language_confidence=confidence,
        is_tanglish=is_tgl,
        is_mixed_language=is_mix,
        is_technical_code=is_tech,
        normalization_applied=normalization_applied or (norm_text != raw_text),
        normalization_notes=tuple(notes),
        tokens=tokens,
        nlp_normalization_version=NLP_NORMALIZATION_VERSION,
    )
