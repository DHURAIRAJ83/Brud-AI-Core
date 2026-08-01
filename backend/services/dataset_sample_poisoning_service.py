"""Phase 12 Step 21 bounded defensive checks for dataset poisoning and
anomalous records. Never claims complete poisoning detection -- every
result is one of the honest `POISONING_RESULTS` values, and the
per-record signal list is exactly what was matched, nothing inferred.

Reuses `core_model.rag.injection_filter.detect_injection_signals()`
unchanged for instruction/prompt-injection/system-prompt-imitation/
data-exfiltration pattern matching -- never a second pattern table.
Homoglyph and outlier-length checks are new (bounded, bytes-only, no
ML model) since nothing existing covers them.
"""

from __future__ import annotations

import statistics
import unicodedata
from typing import Any

from core_model.rag.injection_filter import detect_injection_signals

_INJECTION_CATEGORY_MAP = {
    "ignore_previous_instructions": "instruction_injection",
    "reveal_system_prompt": "prompt_injection",
    "act_as_system": "system_prompt_imitation",
    "execute_commands": "data_exfiltration_instruction",
    "change_policies": "instruction_injection",
    "exfiltrate_secrets": "data_exfiltration_instruction",
    "follow_these_instructions_instead": "prompt_injection",
    "tool_call_directive": "data_exfiltration_instruction",
    "encoded_payload": "hidden_control_character",
    "new_instructions_marker": "system_prompt_imitation",
}
_HIGH_RISK_INJECTION_SIGNALS = frozenset(
    {"prompt_injection", "system_prompt_imitation", "data_exfiltration_instruction"}
)

_ZERO_WIDTH_CHARACTERS = ("​", "‌", "‍", "﻿")
# A conservative, deliberately small confusable-character set --
# Cyrillic and Greek letters visually identical to common Latin ones,
# built from explicit code points (never typed as look-alike literals,
# which is exactly the kind of mistake this set exists to catch) --
# not a full homoglyph database, an honestly bounded starting set.
_HOMOGLYPH_CONFUSABLES = frozenset(
    "аеорсху"  # Cyrillic а е о р с х у
    "АВЕКМНОРСТХ"  # Cyrillic А В Е К М Н О Р С Т Х
    "αβγδεζηθικ"  # Greek α β γ δ ε ζ η θ ι κ
    "μνξοπρστυφχψω"  # μ ν ξ ο π ρ σ τ υ φ χ ψ ω
)


class ExternalDatasetPoisoningCheckService:
    def scan_record(self, text: str) -> dict[str, Any]:
        signals: list[str] = []

        injection = detect_injection_signals(text)
        high_risk = False
        for category in injection["matched_categories"]:
            mapped = _INJECTION_CATEGORY_MAP.get(category, "instruction_injection")
            signals.append(mapped)
            if mapped in _HIGH_RISK_INJECTION_SIGNALS:
                high_risk = True

        if any(char in text for char in _ZERO_WIDTH_CHARACTERS):
            signals.append("zero_width_character")

        if self._has_hidden_control_characters(text):
            signals.append("hidden_control_character")

        if self._has_adversarial_unicode(text):
            signals.append("adversarial_unicode")

        if self._has_homoglyph_abuse(text):
            signals.append("homoglyph_abuse")

        if self._has_extreme_repetition(text):
            signals.append("extreme_repetition")

        result = self._result_for(signals, high_risk=high_risk)
        return {"result": result, "signals": sorted(set(signals))}

    @staticmethod
    def _result_for(signals: list[str], *, high_risk: bool) -> str:
        if high_risk:
            return "blocked"
        if signals:
            return "warning"
        return "no_known_signal"

    @staticmethod
    def _has_hidden_control_characters(text: str) -> bool:
        return any(
            unicodedata.category(char) in ("Cc", "Cf") and char not in ("\n", "\t", "\r")
            for char in text
        )

    @staticmethod
    def _has_adversarial_unicode(text: str) -> bool:
        # Bidirectional-override characters are a classic prompt-hiding
        # trick (text renders differently than it decodes).
        return any(
            unicodedata.category(char) in ("Cf",) and unicodedata.bidirectional(char) in (
                "RLO", "LRO", "RLE", "LRE", "PDF",
            )
            for char in text
        )

    @staticmethod
    def _has_homoglyph_abuse(text: str) -> bool:
        latin_present = any(char.isascii() and char.isalpha() for char in text)
        confusable_present = any(char in _HOMOGLYPH_CONFUSABLES for char in text)
        return latin_present and confusable_present

    @staticmethod
    def _has_extreme_repetition(text: str, *, threshold: int = 50) -> bool:
        if len(text) < threshold:
            return False
        for char in set(text):
            if char.isspace():
                continue
            if text.count(char) / len(text) > 0.6:
                return True
        words = text.split()
        if len(words) >= 10:
            most_common = max((words.count(word) for word in set(words)), default=0)
            if most_common / len(words) > 0.6:
                return True
        return False

    @staticmethod
    def detect_length_outliers(
        record_lengths: dict[str, int], *, z_score_threshold: float = 3.0
    ) -> list[str]:
        """Batch-level check -- an individual record has no inherent
        "outlier" property, only relative to the rest of the sample it
        arrived with."""

        values = list(record_lengths.values())
        if len(values) < 3:
            return []
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev == 0:
            return []
        return [
            public_id
            for public_id, length in record_lengths.items()
            if abs((length - mean) / stdev) > z_score_threshold
        ]
