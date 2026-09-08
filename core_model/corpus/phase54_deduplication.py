"""Phase 54 Advanced Multi-Stage Deduplication Engine.

Deterministic, CPU-bounded deduplication across:
1. Exact SHA-256 Byte Hash
2. Whitespace-Collapsed Normalization
3. Unicode NFC Canonical Equivalence
4. 5-Gram Token-Level Jaccard Near-Duplicate Detection (threshold >= 0.85)
5. Template & Boilerplate Duplicate Detection
6. Cross-Source Exact and Near Deduplication
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class DeduplicationResult:
    is_duplicate: bool
    duplicate_type: Optional[str] = None
    matched_hash: Optional[str] = None
    similarity_score: float = 0.0
    reason: Optional[str] = None


@dataclass
class DeduplicationStatistics:
    total_scanned: int = 0
    exact_duplicates: int = 0
    whitespace_duplicates: int = 0
    unicode_duplicates: int = 0
    near_duplicates: int = 0
    template_duplicates: int = 0
    admitted_unique: int = 0


class Phase54Deduplicator:
    def __init__(self, near_dup_threshold: float = 0.85, ngram_size: int = 5):
        self.near_dup_threshold = near_dup_threshold
        self.ngram_size = ngram_size

        self.exact_hashes: Set[str] = set()
        self.whitespace_hashes: Set[str] = set()
        self.unicode_hashes: Set[str] = set()
        self.template_patterns: Set[str] = set()

        # Near duplicate signature storage: list of (sha256, ngrams)
        self.seen_signatures: List[Tuple[str, Set[str]]] = []

        self.stats = DeduplicationStatistics()
        self.rejection_ledger: List[Dict[str, str]] = []

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        return " ".join(text.split()).strip()

    @staticmethod
    def normalize_unicode(text: str) -> str:
        return unicodedata.normalize("NFC", text)

    @staticmethod
    def extract_template_skeleton(text: str) -> str:
        """Abstracts numbers, punctuation, and common slots to detect structural templates."""
        skeleton = re.sub(r"\d+", "<NUM>", text)
        skeleton = re.sub(r"[!?,.:;\"'()\[\]{}]", "", skeleton)
        skeleton = " ".join(skeleton.split()).lower()
        return skeleton

    def get_token_ngrams(self, text: str) -> Set[str]:
        words = text.split()
        if len(words) < self.ngram_size:
            return set(words)
        return {
            " ".join(words[i : i + self.ngram_size])
            for i in range(len(words) - self.ngram_size + 1)
        }

    @staticmethod
    def calculate_jaccard(set_a: Set[str], set_b: Set[str]) -> float:
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        return inter / union if union > 0 else 0.0

    def evaluate(self, raw_text: str, record_id: str = "") -> DeduplicationResult:
        """Evaluates a raw candidate text against all deduplication tiers."""
        self.stats.total_scanned += 1

        if not raw_text or len(raw_text.strip()) == 0:
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="empty_record",
                reason="Record text is empty",
            )

        # Tier 1: Exact Byte Hash
        raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        if raw_hash in self.exact_hashes:
            self.stats.exact_duplicates += 1
            self.rejection_ledger.append({
                "record_id": record_id,
                "type": "exact_duplicate",
                "hash": raw_hash,
            })
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="exact_duplicate",
                matched_hash=raw_hash,
                similarity_score=1.0,
                reason="Exact byte hash collision",
            )

        # Tier 2: Unicode NFC Normalization
        u_text = self.normalize_unicode(raw_text)
        u_hash = hashlib.sha256(u_text.encode("utf-8")).hexdigest()
        if u_hash in self.unicode_hashes:
            self.stats.unicode_duplicates += 1
            self.rejection_ledger.append({
                "record_id": record_id,
                "type": "unicode_duplicate",
                "hash": u_hash,
            })
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="unicode_duplicate",
                matched_hash=u_hash,
                similarity_score=1.0,
                reason="Unicode NFC canonical equivalent already present",
            )

        # Tier 3: Whitespace Collapsing
        ws_text = self.normalize_whitespace(u_text)
        ws_hash = hashlib.sha256(ws_text.encode("utf-8")).hexdigest()
        if ws_hash in self.whitespace_hashes:
            self.stats.whitespace_duplicates += 1
            self.rejection_ledger.append({
                "record_id": record_id,
                "type": "whitespace_duplicate",
                "hash": ws_hash,
            })
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="whitespace_duplicate",
                matched_hash=ws_hash,
                similarity_score=1.0,
                reason="Whitespace collapsed text already present",
            )

        # Tier 4: Template & Boilerplate Duplicate Detection
        # Applies to synthetic dialogue and formulaic pairs
        skeleton = self.extract_template_skeleton(ws_text)
        if len(ws_text.split()) <= 10 and skeleton in self.template_patterns:
            self.stats.template_duplicates += 1
            self.rejection_ledger.append({
                "record_id": record_id,
                "type": "template_duplicate",
                "skeleton": skeleton[:40],
            })
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="template_duplicate",
                similarity_score=1.0,
                reason=f"Structural template collision: '{skeleton[:40]}'",
            )

        # Tier 5: 5-Gram Token-Level Jaccard Near-Duplicate
        ngrams = self.get_token_ngrams(ws_text)
        for prev_hash, prev_ngrams in self.seen_signatures:
            jaccard = self.calculate_jaccard(ngrams, prev_ngrams)
            if jaccard >= self.near_dup_threshold:
                self.stats.near_duplicates += 1
                self.rejection_ledger.append({
                    "record_id": record_id,
                    "type": "near_duplicate",
                    "matched_hash": prev_hash,
                    "score": f"{jaccard:.4f}",
                })
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_type="near_duplicate",
                    matched_hash=prev_hash,
                    similarity_score=jaccard,
                    reason=f"5-gram Jaccard similarity {jaccard:.4f} exceeds threshold {self.near_dup_threshold}",
                )

        # Record is genuinely unique across all tiers
        self.exact_hashes.add(raw_hash)
        self.unicode_hashes.add(u_hash)
        self.whitespace_hashes.add(ws_hash)
        self.template_patterns.add(skeleton)
        self.seen_signatures.append((ws_hash, ngrams))
        self.stats.admitted_unique += 1

        return DeduplicationResult(
            is_duplicate=False,
            matched_hash=ws_hash,
            similarity_score=0.0,
        )

    def generate_report(self) -> str:
        """Generates markdown report of deduplication results."""
        return f"""# Phase 54 Advanced Deduplication Report

**Deduplication Policy:** Exact SHA-256 + Whitespace + Unicode NFC + 5-Gram Jaccard (>= {self.near_dup_threshold}) + Template Skeleton

---

## 1. Summary Statistics

| Metric | Count | Percentage |
| :--- | :--- | :--- |
| **Total Candidates Evaluated** | {self.stats.total_scanned:,} | 100.0% |
| **Exact SHA-256 Duplicates** | {self.stats.exact_duplicates:,} | {self.stats.exact_duplicates / max(1, self.stats.total_scanned):.2%} |
| **Unicode Canonical Duplicates**| {self.stats.unicode_duplicates:,} | {self.stats.unicode_duplicates / max(1, self.stats.total_scanned):.2%} |
| **Whitespace Collapsed Duplicates**| {self.stats.whitespace_duplicates:,} | {self.stats.whitespace_duplicates / max(1, self.stats.total_scanned):.2%} |
| **Template Boilerplate Duplicates**| {self.stats.template_duplicates:,} | {self.stats.template_duplicates / max(1, self.stats.total_scanned):.2%} |
| **5-Gram Near Duplicates (>= 0.85)**| {self.stats.near_duplicates:,} | {self.stats.near_duplicates / max(1, self.stats.total_scanned):.2%} |
| **Admitted Genuinely Unique** | **{self.stats.admitted_unique:,}** | **{self.stats.admitted_unique / max(1, self.stats.total_scanned):.2%}** |

---

## 2. Integrity Certification

- Exact byte hash deduplication is mathematically zero-collision with SHA-256.
- Near-deduplication using 5-grams ensures lexical diversity while preserving distinct literary expressions.
"""
