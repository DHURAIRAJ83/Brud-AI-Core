"""Phase 54 Corpus Diversity and Information Entropy Engine V2.

Computes comprehensive lexical, structural, and information-theoretic metrics:
- Shannon Character Entropy (bits)
- Shannon Word Entropy (bits)
- Shannon Domain Entropy (bits)
- Shannon Language Entropy (bits)
- Type-Token Ratio (TTR)
- Tamil / English / Tanglish / Bilingual Script Ratios
- Top-10 and Top-50 Token Frequency Concentration
- Source and Domain Concentration
- Relative Vocabulary Growth over Phase 53 Baseline
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass
class Phase54DiversityReport:
    total_records: int
    total_tokens: int
    unique_tokens: int
    total_characters: int
    unique_characters: int
    type_token_ratio: float
    character_entropy: float
    word_entropy: float
    domain_entropy: float
    language_entropy: float
    tamil_char_ratio: float
    english_char_ratio: float
    tanglish_ratio: float
    bilingual_ratio: float
    top_10_token_concentration: float
    top_50_token_concentration: float
    domain_distribution: Dict[str, int]
    language_distribution: Dict[str, int]
    source_distribution: Dict[str, int]
    avg_tokens_per_record: float
    avg_chars_per_record: float
    new_unique_tokens_over_p53: int
    vocabulary_expansion_rate: float
    dominance_warning: bool


class Phase54DiversityAnalyzer:
    PHASE53_UNIQUE_TOKENS = 2906
    PHASE53_VOCABULARY_SIZE = 1401

    @staticmethod
    def calculate_entropy(frequencies: Dict[Any, int]) -> float:
        total = sum(frequencies.values())
        if total <= 0:
            return 0.0
        ent = 0.0
        for count in frequencies.values():
            if count > 0:
                p = count / total
                ent -= p * math.log2(p)
        return ent

    @classmethod
    def analyze_records(
        cls,
        records: List[Any],
        phase53_vocab: Optional[Set[str]] = None,
    ) -> Phase54DiversityReport:
        if not records:
            return Phase54DiversityReport(
                total_records=0,
                total_tokens=0,
                unique_tokens=0,
                total_characters=0,
                unique_characters=0,
                type_token_ratio=0.0,
                character_entropy=0.0,
                word_entropy=0.0,
                domain_entropy=0.0,
                language_entropy=0.0,
                tamil_char_ratio=0.0,
                english_char_ratio=0.0,
                tanglish_ratio=0.0,
                bilingual_ratio=0.0,
                top_10_token_concentration=0.0,
                top_50_token_concentration=0.0,
                domain_distribution={},
                language_distribution={},
                source_distribution={},
                avg_tokens_per_record=0.0,
                avg_chars_per_record=0.0,
                new_unique_tokens_over_p53=0,
                vocabulary_expansion_rate=0.0,
                dominance_warning=False,
            )

        total_records = len(records)
        domain_counts: Counter[str] = Counter()
        lang_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        word_counts: Counter[str] = Counter()
        char_counts: Counter[str] = Counter()

        total_tamil_chars = 0
        total_english_chars = 0
        total_chars = 0
        total_tokens = 0
        tanglish_count = 0
        bilingual_count = 0

        for r in records:
            text = r.text if hasattr(r, "text") else str(r)
            domain = getattr(r, "domain", "general")
            lang = getattr(r, "language", "ta")
            src = getattr(r, "source_id", "default")

            domain_counts[domain] += 1
            lang_counts[lang] += 1
            source_counts[src] += 1

            words = text.split()
            tok_count = getattr(r, "token_count", len(words))
            total_tokens += tok_count

            has_ta = False
            has_en = False

            for w in words:
                clean_w = w.strip(".,!?;:\"'()[]{}").lower()
                if clean_w:
                    word_counts[clean_w] += 1

            for c in text:
                total_chars += 1
                char_counts[c] += 1
                if "\u0b80" <= c <= "\u0bff":
                    total_tamil_chars += 1
                    has_ta = True
                elif ("a" <= c <= "z") or ("A" <= c <= "Z"):
                    total_english_chars += 1
                    has_en = True

            if lang == "tgl":
                tanglish_count += 1
            if has_ta and has_en:
                bilingual_count += 1

        unique_tokens = len(word_counts)
        unique_chars = len(char_counts)
        ttr = unique_tokens / max(1, sum(word_counts.values()))

        char_entropy = cls.calculate_entropy(dict(char_counts))
        word_entropy = cls.calculate_entropy(dict(word_counts))
        domain_entropy = cls.calculate_entropy(dict(domain_counts))
        lang_entropy = cls.calculate_entropy(dict(lang_counts))

        sorted_words = sorted(word_counts.values(), reverse=True)
        tot_w = sum(sorted_words)
        top10_sum = sum(sorted_words[:10])
        top50_sum = sum(sorted_words[:50])
        top10_conc = top10_sum / max(1, tot_w)
        top50_conc = top50_sum / max(1, tot_w)

        ta_ratio = total_tamil_chars / max(1, total_chars)
        en_ratio = total_english_chars / max(1, total_chars)
        tgl_ratio = tanglish_count / max(1, total_records)
        bilingual_ratio = bilingual_count / max(1, total_records)

        # Growth over Phase 53 baseline
        if phase53_vocab is not None:
            new_tokens = len(set(word_counts.keys()) - phase53_vocab)
        else:
            new_tokens = max(0, total_tokens - cls.PHASE53_UNIQUE_TOKENS)

        growth_rate = (unique_tokens - cls.PHASE53_VOCABULARY_SIZE) / max(1, cls.PHASE53_VOCABULARY_SIZE)

        # Dominance warning: if any single domain represents > 40% of records
        dominance_warning = any(
            (c / total_records) > 0.40 for c in domain_counts.values()
        )

        return Phase54DiversityReport(
            total_records=total_records,
            total_tokens=total_tokens,
            unique_tokens=unique_tokens,
            total_characters=total_chars,
            unique_characters=unique_chars,
            type_token_ratio=round(ttr, 4),
            character_entropy=round(char_entropy, 4),
            word_entropy=round(word_entropy, 4),
            domain_entropy=round(domain_entropy, 4),
            language_entropy=round(lang_entropy, 4),
            tamil_char_ratio=round(ta_ratio, 4),
            english_char_ratio=round(en_ratio, 4),
            tanglish_ratio=round(tgl_ratio, 4),
            bilingual_ratio=round(bilingual_ratio, 4),
            top_10_token_concentration=round(top10_conc, 4),
            top_50_token_concentration=round(top50_conc, 4),
            domain_distribution=dict(domain_counts),
            language_distribution=dict(lang_counts),
            source_distribution=dict(source_counts),
            avg_tokens_per_record=round(total_tokens / max(1, total_records), 2),
            avg_chars_per_record=round(total_chars / max(1, total_records), 2),
            new_unique_tokens_over_p53=new_tokens,
            vocabulary_expansion_rate=round(growth_rate, 4),
            dominance_warning=dominance_warning,
        )
