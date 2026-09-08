"""Phase 53 Sovereign Corpus Diversity Analyzer.

Measures comprehensive lexical diversity, character/word/domain entropy,
language distributions, sequence lengths, and top-token concentration.
"""

from __future__ import annotations

import collections
import math
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DiversityReport(BaseModel):
    """Detailed analytical metrics covering corpus diversity and quality."""

    total_records: int
    total_characters: int
    total_words: int
    unique_words: int
    type_token_ratio: float
    character_entropy: float
    word_entropy: float
    domain_entropy: float
    tamil_char_ratio: float
    english_char_ratio: float
    other_char_ratio: float
    language_distribution: Dict[str, int]
    domain_distribution: Dict[str, int]
    source_distribution: Dict[str, int]
    length_distribution: Dict[str, int]
    mean_sentence_length_words: float
    top_10_token_concentration: float
    dominance_warning: bool
    warning_message: str = ""


class Phase53DiversityAnalyzer:
    """Computes multidimensional diversity and information-theoretic metrics for sovereign corpus."""

    @staticmethod
    def calculate_entropy(counts: Dict[str, int]) -> float:
        """Calculates Shannon entropy in bits for a frequency distribution."""
        total = sum(counts.values())
        if total == 0:
            return 0.0
        entropy = 0.0
        for cnt in counts.values():
            if cnt > 0:
                p = cnt / total
                entropy -= p * math.log2(p)
        return entropy

    @classmethod
    def analyze_records(cls, records: List[Any]) -> DiversityReport:
        """Analyzes a collection of GovernedRecord instances."""
        if not records:
            return DiversityReport(
                total_records=0,
                total_characters=0,
                total_words=0,
                unique_words=0,
                type_token_ratio=0.0,
                character_entropy=0.0,
                word_entropy=0.0,
                domain_entropy=0.0,
                tamil_char_ratio=0.0,
                english_char_ratio=0.0,
                other_char_ratio=0.0,
                language_distribution={},
                domain_distribution={},
                source_distribution={},
                length_distribution={"short": 0, "medium": 0, "long": 0},
                mean_sentence_length_words=0.0,
                top_10_token_concentration=0.0,
                dominance_warning=False,
                warning_message="Empty corpus provided",
            )

        char_counts: Dict[str, int] = collections.defaultdict(int)
        word_counts: Dict[str, int] = collections.defaultdict(int)
        domain_counts: Dict[str, int] = collections.defaultdict(int)
        source_counts: Dict[str, int] = collections.defaultdict(int)
        lang_counts: Dict[str, int] = collections.defaultdict(int)

        total_chars = 0
        tamil_chars = 0
        english_chars = 0
        total_words = 0
        record_word_lengths: List[int] = []
        length_dist = {"short (<50 ch)": 0, "medium (50-200 ch)": 0, "long (>200 ch)": 0}

        for rec in records:
            text = rec.text if hasattr(rec, "text") else str(rec)
            c_len = len(text)
            total_chars += c_len

            if c_len < 50:
                length_dist["short (<50 ch)"] += 1
            elif c_len <= 200:
                length_dist["medium (50-200 ch)"] += 1
            else:
                length_dist["long (>200 ch)"] += 1

            for ch in text:
                char_counts[ch] += 1
                if "\u0b80" <= ch <= "\u0bff":
                    tamil_chars += 1
                elif "a" <= ch.lower() <= "z":
                    english_chars += 1

            words = text.split()
            w_len = len(words)
            total_words += w_len
            record_word_lengths.append(w_len)
            for w in words:
                word_counts[w.lower()] += 1

            domain = getattr(rec, "domain", "general")
            domain_counts[domain] += 1

            src = getattr(rec, "source_id", "unknown")
            source_counts[src] += 1

            lang = getattr(rec, "language", "ta")
            lang_counts[lang] += 1

        ttr = len(word_counts) / max(1, total_words)
        char_entropy = cls.calculate_entropy(char_counts)
        word_entropy = cls.calculate_entropy(word_counts)
        domain_entropy = cls.calculate_entropy(domain_counts)

        ta_ratio = tamil_chars / max(1, total_chars)
        en_ratio = english_chars / max(1, total_chars)
        other_ratio = max(0.0, 1.0 - (ta_ratio + en_ratio))

        sorted_words = sorted(word_counts.values(), reverse=True)
        top_10_words_sum = sum(sorted_words[:10])
        top_10_concentration = top_10_words_sum / max(1, total_words)

        mean_words = total_words / len(records)

        # Warning threshold check
        dominance_warn = False
        msg = "Corpus diversity within normal operating parameters."
        if top_10_concentration > 0.35:
            dominance_warn = True
            msg = f"WARNING: Top 10 tokens account for {top_10_concentration*100:.1f}% of total words (> 35% threshold)."
        elif len(domain_counts) < 3:
            dominance_warn = True
            msg = f"WARNING: Insufficient domain diversity ({len(domain_counts)} domains < 3)."

        return DiversityReport(
            total_records=len(records),
            total_characters=total_chars,
            total_words=total_words,
            unique_words=len(word_counts),
            type_token_ratio=round(ttr, 4),
            character_entropy=round(char_entropy, 4),
            word_entropy=round(word_entropy, 4),
            domain_entropy=round(domain_entropy, 4),
            tamil_char_ratio=round(ta_ratio, 4),
            english_char_ratio=round(en_ratio, 4),
            other_char_ratio=round(other_ratio, 4),
            language_distribution=dict(lang_counts),
            domain_distribution=dict(domain_counts),
            source_distribution=dict(source_counts),
            length_distribution=length_dist,
            mean_sentence_length_words=round(mean_words, 2),
            top_10_token_concentration=round(top_10_concentration, 4),
            dominance_warning=dominance_warn,
            warning_message=msg,
        )
