"""Phase 51 Sovereign Corpus Diversity Analyzer.

Measures linguistic, domain, lexical, and structural diversity across
approved sovereign records:
- Language balance (Tamil / English / Tanglish / Mixed)
- Domain entropy & distribution
- Vocabulary diversity (Type-Token Ratio / TTR)
- Sentence & sequence length distributions
- Character set diversity
- Duplicate / repetition metrics
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from core_model.corpus.phase47_corpus_expander import Phase47CorpusRecord


@dataclass
class DiversityMetrics:
    total_records: int
    total_characters: int
    total_tokens_estimated: int
    total_words: int
    unique_words: int
    type_token_ratio: float  # unique_words / total_words
    character_entropy: float
    domain_entropy: float
    language_distribution: dict[str, int]
    language_ratios: dict[str, float]
    domain_distribution: dict[str, int]
    source_distribution: dict[str, int]
    sentence_length_mean: float
    sentence_length_stddev: float
    record_length_min: int
    record_length_max: int
    record_length_median: float
    tamil_character_percentage: float
    english_character_percentage: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase51DiversityAnalyzer:
    """Computes comprehensive diversity metrics across sovereign corpus records."""

    @classmethod
    def analyze_records(cls, records: Sequence[Phase47CorpusRecord]) -> DiversityMetrics:
        """Analyzes a collection of Phase47CorpusRecord instances."""
        if not records:
            return DiversityMetrics(
                total_records=0,
                total_characters=0,
                total_tokens_estimated=0,
                total_words=0,
                unique_words=0,
                type_token_ratio=0.0,
                character_entropy=0.0,
                domain_entropy=0.0,
                language_distribution={},
                language_ratios={},
                domain_distribution={},
                source_distribution={},
                sentence_length_mean=0.0,
                sentence_length_stddev=0.0,
                record_length_min=0,
                record_length_max=0,
                record_length_median=0.0,
                tamil_character_percentage=0.0,
                english_character_percentage=0.0,
            )

        total_records = len(records)
        total_chars = sum(len(r.text) for r in records)
        total_tokens = sum(r.estimated_tokens for r in records)

        all_words: list[str] = []
        all_sentences: list[str] = []
        lang_counts: Counter[str] = Counter()
        domain_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        record_lengths: list[int] = []

        total_tamil_chars = 0
        total_english_chars = 0

        for r in records:
            text = r.text
            record_lengths.append(len(text))
            lang_counts[r.language] += 1
            domain_counts[r.domain] += 1
            source_counts[r.source_id] += 1

            # Count characters
            for c in text:
                if "\u0b80" <= c <= "\u0bff":
                    total_tamil_chars += 1
                elif c.isascii() and c.isalpha():
                    total_english_chars += 1

            # Tokenize words roughly
            words = [w.strip() for w in re.split(r"\s+", text) if w.strip()]
            all_words.extend([w.lower() for w in words])

            # Sentences
            sents = [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]
            all_sentences.extend(sents)

        total_words = len(all_words)
        unique_words = len(set(all_words))
        ttr = unique_words / max(1, total_words)

        # Character entropy
        char_counts = Counter("".join(r.text for r in records))
        char_entropy = -sum(
            (count / total_chars) * math.log2(count / total_chars)
            for count in char_counts.values()
            if count > 0
        ) if total_chars > 0 else 0.0

        # Domain entropy
        domain_entropy = -sum(
            (count / total_records) * math.log2(count / total_records)
            for count in domain_counts.values()
            if count > 0
        )

        # Sentence length stats
        sent_lens = [len(s) for s in all_sentences] or [0]
        mean_sent_len = sum(sent_lens) / len(sent_lens)
        var_sent = sum((l - mean_sent_len) ** 2 for l in sent_lens) / max(1, len(sent_lens))
        std_sent = math.sqrt(var_sent)

        # Record length stats
        sorted_lens = sorted(record_lengths)
        median_len = sorted_lens[len(sorted_lens) // 2]

        return DiversityMetrics(
            total_records=total_records,
            total_characters=total_chars,
            total_tokens_estimated=total_tokens,
            total_words=total_words,
            unique_words=unique_words,
            type_token_ratio=round(ttr, 4),
            character_entropy=round(char_entropy, 4),
            domain_entropy=round(domain_entropy, 4),
            language_distribution=dict(lang_counts),
            language_ratios={k: round(v / total_records, 4) for k, v in lang_counts.items()},
            domain_distribution=dict(domain_counts),
            source_distribution=dict(source_counts),
            sentence_length_mean=round(mean_sent_len, 2),
            sentence_length_stddev=round(std_sent, 2),
            record_length_min=min(record_lengths),
            record_length_max=max(record_lengths),
            record_length_median=float(median_len),
            tamil_character_percentage=round((total_tamil_chars / max(1, total_chars)) * 100.0, 2),
            english_character_percentage=round((total_english_chars / max(1, total_chars)) * 100.0, 2),
        )
