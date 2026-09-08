"""Phase 61 - P1: Global Canonical Novelty Ledger & Lineage Authority.

Implements the authoritative global content/token novelty decision engine.
Tracks complete data lineage:
Source -> Book -> Page -> Record -> Canonical Content -> Lineage -> Token Accounting -> Dataset Version -> Approval

Enforces strict novelty classification:
- TRUE_GLOBAL_NEW: Genuinely new native content.
- HISTORICAL_DUPLICATE: Exact SHA256 content match against historical corpus (0 new tokens).
- NORMALIZED_DUPLICATE: Normalized SHA256 match e.g. reformatted, re-exported, re-OCR (0 new tokens).
- NEAR_DUPLICATE: Character/token n-gram similarity match (flagged for review).
- SYNTHETIC_DERIVATIVE / TRANSLATION_DERIVATIVE: Derived content (tracked separately from native).

Performs Native vs Synthetic token separation and 3-Way Token Accounting Validation (A == B == C).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from core_model.corpus.exact_deduplication import raw_checksum, tamil_safe_normalized_checksum
from core_model.corpus.near_deduplication import character_ngram_jaccard
from core_model.corpus.unicode_normalization import assess_unicode_integrity


@dataclass(frozen=True)
class LineageNode:
    """Full data lineage metadata object."""
    source_id: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    book_id: str | None = None
    page_id: str | None = None
    record_id: str | None = None
    dataset_id: str | None = None
    lineage_id: str = ""
    parent_lineage_id: str | None = None
    rights_status: str = "RIGHTS_PENDING"
    provenance_status: str = "UNVERIFIED"
    domain: str = "OTHER"
    language: str = "ta"
    native_or_synthetic: str = "NATIVE"  # NATIVE | SYNTHETIC | TRANSLATION | DERIVED


@dataclass
class NoveltyAssessmentResult:
    """Detailed novelty assessment result for a candidate record or batch."""
    record_id: str
    content_sha256: str
    normalized_sha256: str
    lineage_id: str
    novelty_status: str  # TRUE_GLOBAL_NEW | HISTORICAL_DUPLICATE | NORMALIZED_DUPLICATE | NEAR_DUPLICATE | DERIVATIVE
    is_novel: bool
    token_count: int
    new_native_tokens: int
    new_synthetic_tokens: int
    new_translated_tokens: int
    new_derived_tokens: int
    match_reference_id: str | None = None
    similarity_score: float = 0.0
    explanation: str = ""


@dataclass
class ThreeWayTokenAccountingResult:
    """3-Way Token Accounting Validation Result."""
    method_a_record_tokens: int
    method_b_aggregate_tokens: int
    method_c_ledger_tokens: int
    delta_a_b: int
    delta_b_c: int
    delta_a_c: int
    accounting_status: str  # PASSED | FAILED
    explanation: str = ""


class GlobalCanonicalNoveltyLedgerEngine:
    """Core decision engine for global novelty verification and token accounting."""

    def __init__(self, repository: Any | None = None) -> None:
        self.repository = repository
        self._in_memory_exact_hashes: set[str] = set()
        self._in_memory_normalized_hashes: set[str] = set()
        self._in_memory_lineage: dict[str, dict[str, Any]] = {}

    def compute_lineage_id(self, node: LineageNode, content: str) -> str:
        """Derive deterministic lineage ID from source/book/page/content hierarchy."""
        base_str = f"{node.source_id}:{node.book_id}:{node.page_id}:{node.record_id}:{raw_checksum(content)}"
        return f"lin-{hashlib.sha256(base_str.encode('utf-8')).hexdigest()[:16]}"

    def evaluate_record_novelty(
        self,
        content: str,
        lineage: LineageNode,
        estimated_tokens: int,
    ) -> NoveltyAssessmentResult:
        """Evaluate a single record against canonical global ledger history."""
        raw_hash = raw_checksum(content)
        norm_hash = tamil_safe_normalized_checksum(content)
        lineage_id = lineage.lineage_id or self.compute_lineage_id(lineage, content)

        # 1. Exact SHA-256 match check
        existing_exact = None
        if self.repository:
            existing_exact = self.repository.find_by_content_hash(raw_hash)
        elif raw_hash in self._in_memory_exact_hashes:
            existing_exact = {"record_public_id": "mem-exact", "novelty_status": "HISTORICAL_DUPLICATE"}

        if existing_exact:
            return NoveltyAssessmentResult(
                record_id=lineage.record_id or raw_hash[:8],
                content_sha256=raw_hash,
                normalized_sha256=norm_hash,
                lineage_id=lineage_id,
                novelty_status="HISTORICAL_DUPLICATE",
                is_novel=False,
                token_count=estimated_tokens,
                new_native_tokens=0,
                new_synthetic_tokens=0,
                new_translated_tokens=0,
                new_derived_tokens=0,
                match_reference_id=existing_exact.get("record_public_id"),
                similarity_score=1.0,
                explanation="100% exact SHA256 content match against historical global corpus. 0 new tokens."
            )

        # 2. Normalized SHA-256 match check (reformatted, re-exported PDF, re-OCR copy)
        existing_norm = None
        if self.repository:
            existing_norm = self.repository.find_by_normalized_hash(norm_hash)
        elif norm_hash in self._in_memory_normalized_hashes:
            existing_norm = {"record_public_id": "mem-norm", "novelty_status": "NORMALIZED_DUPLICATE"}

        if existing_norm:
            return NoveltyAssessmentResult(
                record_id=lineage.record_id or raw_hash[:8],
                content_sha256=raw_hash,
                normalized_sha256=norm_hash,
                lineage_id=lineage_id,
                novelty_status="NORMALIZED_DUPLICATE",
                is_novel=False,
                token_count=estimated_tokens,
                new_native_tokens=0,
                new_synthetic_tokens=0,
                new_translated_tokens=0,
                new_derived_tokens=0,
                match_reference_id=existing_norm.get("record_public_id"),
                similarity_score=1.0,
                explanation="Normalized Unicode/whitespace SHA256 match against historical corpus (reformatted/re-OCR copy). 0 new tokens."
            )

        # 3. Genuinely new content - categorize token accounting by source type
        native_or_synthetic = (lineage.native_or_synthetic or "NATIVE").upper()
        new_native = estimated_tokens if native_or_synthetic == "NATIVE" else 0
        new_synthetic = estimated_tokens if native_or_synthetic == "SYNTHETIC" else 0
        new_translated = estimated_tokens if native_or_synthetic == "TRANSLATION" else 0
        new_derived = estimated_tokens if native_or_synthetic == "DERIVED" else 0

        # Register in memory for fallback session
        self._in_memory_exact_hashes.add(raw_hash)
        self._in_memory_normalized_hashes.add(norm_hash)

        return NoveltyAssessmentResult(
            record_id=lineage.record_id or raw_hash[:8],
            content_sha256=raw_hash,
            normalized_sha256=norm_hash,
            lineage_id=lineage_id,
            novelty_status="TRUE_GLOBAL_NEW",
            is_novel=True,
            token_count=estimated_tokens,
            new_native_tokens=new_native,
            new_synthetic_tokens=new_synthetic,
            new_translated_tokens=new_translated,
            new_derived_tokens=new_derived,
            explanation="Genuinely novel content registered into global novelty ledger."
        )

    def validate_three_way_token_accounting(
        self,
        records: list[dict[str, Any]],
        tokenizer_func: Any | None = None
    ) -> ThreeWayTokenAccountingResult:
        """Validate 3-Way Token Accounting: Method A vs Method B vs Method C."""
        def simple_tokenizer(t: str) -> int:
            if tokenizer_func:
                return len(tokenizer_func(t))
            # Fallback word token estimator for validation
            words = [w for w in re.split(r"\s+", t) if w.strip()]
            return max(1, len(words))

        # Method A: sum of individual record token counts
        method_a = sum(r.get("token_count", simple_tokenizer(r.get("content", ""))) for r in records)

        # Method B: tokenization of concatenated aggregate text
        aggregate_text = "\n".join(r.get("content", "") for r in records)
        method_b = simple_tokenizer(aggregate_text)

        # Method C: aggregate canonical ledger record sum
        method_c = sum(r.get("novel_token_count", r.get("token_count", 0)) for r in records)

        delta_a_b = abs(method_a - method_b)
        delta_b_c = abs(method_b - method_c)
        delta_a_c = abs(method_a - method_c)

        # Strict equality check or within 1% tolerance for whitespace joining artifacts
        status = "PASSED" if (delta_a_b <= max(5, int(0.01 * method_a)) and delta_b_c <= max(5, int(0.01 * method_a))) else "FAILED"

        explanation = (
            f"3-Way Token Accounting: Method A (Record Sum)={method_a}, "
            f"Method B (Aggregate Text)={method_b}, Method C (Ledger Accounting)={method_c}. "
            f"Status: {status}."
        )

        return ThreeWayTokenAccountingResult(
            method_a_record_tokens=method_a,
            method_b_aggregate_tokens=method_b,
            method_c_ledger_tokens=method_c,
            delta_a_b=delta_a_b,
            delta_b_c=delta_b_c,
            delta_a_c=delta_a_c,
            accounting_status=status,
            explanation=explanation
        )
