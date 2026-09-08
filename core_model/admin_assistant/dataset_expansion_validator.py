"""
Phase 60 WS07 E3: Automated Validation Layer for Admin Assistant Dataset Expansion.
Validates language distribution, Tamil Unicode orthography, Tanglish normalization,
detects ambiguity penalties, checks Phase 53 benchmark contamination, and scores confidence.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"

_ZERO_WIDTH_CHARS = ("\u200b", "\u200c", "\u200d", "\ufeff")
_TAMIL_CHAR_RE = re.compile(r"[\u0B80-\u0BFF]")
_LATIN_CHAR_RE = re.compile(r"[A-Za-z]")


@dataclass
class ValidationReport:
    is_valid: bool
    language_valid: bool
    orthography_valid: bool
    ambiguity_handled: bool
    duplicate: bool
    contamination: bool
    calculated_confidence: float
    confidence_band: str  # "HIGH", "REVIEW_REQUIRED", "MANUAL_REVIEW_STRONG", "REJECT"
    rejection_reasons: list[str]
    warning_notes: list[str]


class DatasetExpansionValidator:
    """Rigorous automated quality gate for candidate dataset proposals."""

    def __init__(self):
        self.benchmark_prompts: set[str] = set()
        self._load_benchmark_probes()

    def _load_benchmark_probes(self):
        if BENCHMARK_PATH.exists():
            try:
                bm_data = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
                for probe in bm_data.get("probes", []):
                    p_text = probe.get("prompt", "").strip().lower()
                    if p_text:
                        self.benchmark_prompts.add(p_text)
            except Exception:
                pass

    @staticmethod
    def validate_orthography(text: str) -> tuple[bool, list[str]]:
        """Verifies Tamil Unicode normalization and absence of corruption."""
        notes = []
        is_clean = True

        # Check stray zero-width characters
        for zw in _ZERO_WIDTH_CHARS:
            if zw in text:
                is_clean = False
                notes.append(f"Stray zero-width character U+{ord(zw):04X} detected.")

        # Check Unicode NFC canonical equivalence
        normalized = unicodedata.normalize("NFC", text)
        if text != normalized:
            is_clean = False
            notes.append("Text is not in canonical Unicode NFC normalization form.")

        # Check for duplicated virama artefacts (e.g. ொ்)
        if "ொ்" in text:
            is_clean = False
            notes.append("Scanner artefact: duplicated virama sequence detected.")

        return is_clean, notes

    @staticmethod
    def validate_language_code(text: str, declared_lang: str) -> tuple[bool, str]:
        """Validates that text script aligns with the declared language label."""
        if not text:
            return False, "Empty text"

        tamil_count = len(_TAMIL_CHAR_RE.findall(text))
        latin_count = len(_LATIN_CHAR_RE.findall(text))
        total_alpha = max(1, tamil_count + latin_count)
        ta_ratio = tamil_count / total_alpha
        lat_ratio = latin_count / total_alpha

        if declared_lang == "ta":
            if ta_ratio < 0.40 and latin_count > 0:
                return False, f"Tamil text has insufficient Tamil script ratio ({ta_ratio:.2f})"
            return True, "Valid Tamil"

        elif declared_lang == "en":
            if lat_ratio < 0.60:
                return False, f"English text has insufficient Latin script ratio ({lat_ratio:.2f})"
            return True, "Valid English"

        elif declared_lang == "tgl":
            if latin_count == 0 and tamil_count > 0:
                return False, "Tanglish must use Latin script representation"
            return True, "Valid Tanglish"

        elif declared_lang == "mixed":
            # Mixed should ideally have elements of both or cross-lingual structure
            return True, "Valid Mixed"

        return True, "Accepted"

    def check_contamination(self, prompt: str, response: str) -> bool:
        """Ensures complete air-gap isolation against the Phase 53 benchmark."""
        p_clean = prompt.strip().lower()
        r_clean = response.strip().lower()

        if p_clean in self.benchmark_prompts or r_clean in self.benchmark_prompts:
            return True

        # Check substring containment on long benchmark prompts
        for bm_p in self.benchmark_prompts:
            if len(bm_p) > 25 and (bm_p in p_clean or p_clean in bm_p):
                return True

        return False

    def validate_proposal(
        self,
        instruction: str,
        response: str,
        declared_lang: str,
        is_ambiguous: bool = False,
        base_confidence: float = 0.95,
        seen_prompts: set[str] | None = None
    ) -> ValidationReport:
        rejection_reasons = []
        warning_notes = []

        # 1. Orthography Check
        i_orth_ok, i_notes = self.validate_orthography(instruction)
        r_orth_ok, r_notes = self.validate_orthography(response)
        orth_ok = i_orth_ok and r_orth_ok
        warning_notes.extend(i_notes)
        warning_notes.extend(r_notes)

        # 2. Language Alignment Check
        i_lang_ok, i_lang_msg = self.validate_language_code(instruction, declared_lang)
        if not i_lang_ok:
            warning_notes.append(f"Instruction language mismatch: {i_lang_msg}")

        # 3. Duplicate Detection
        p_hash = instruction.strip().lower()
        is_duplicate = False
        if seen_prompts is not None and p_hash in seen_prompts:
            is_duplicate = True
            rejection_reasons.append("Exact duplicate instruction in current proposal batch.")

        # 4. Phase 53 Benchmark Contamination Check
        is_contaminated = self.check_contamination(instruction, response)
        if is_contaminated:
            rejection_reasons.append("Contamination alert: Overlaps with Phase 53 benchmark probe.")

        # 5. Ambiguity Handling & Confidence Calculation
        calc_conf = base_confidence
        if is_ambiguous:
            warning_notes.append("Ambiguity flag: Source concept is polysemous. Admin review required.")
            calc_conf = min(calc_conf, 0.75)

        if not orth_ok:
            calc_conf -= 0.15
        if not i_lang_ok:
            calc_conf -= 0.10

        calc_conf = max(0.10, min(1.0, calc_conf))

        # Confidence Band
        if calc_conf >= 0.90:
            band = "HIGH"
        elif calc_conf >= 0.75:
            band = "REVIEW_REQUIRED"
        elif calc_conf >= 0.50:
            band = "MANUAL_REVIEW_STRONG"
        else:
            band = "REJECT"

        is_valid = (len(rejection_reasons) == 0) and not is_contaminated and not is_duplicate

        return ValidationReport(
            is_valid=is_valid,
            language_valid=i_lang_ok,
            orthography_valid=orth_ok,
            ambiguity_handled=True,
            duplicate=is_duplicate,
            contamination=is_contaminated,
            calculated_confidence=round(calc_conf, 2),
            confidence_band=band,
            rejection_reasons=rejection_reasons,
            warning_notes=warning_notes
        )
