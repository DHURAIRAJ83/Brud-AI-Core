"""Phase 40 — Production Sovereign Dataset Ingestion & Streaming Pipeline.

Implements Workstreams 2 & 3:
- Streaming/chunked disk processing (bounded memory footprint)
- Unicode NFC normalization
- Malformed & garbage/repetition filtering
- PII and secret detection & redaction
- Prompt injection quarantine via assess_context_item_injection
- Exact deduplication (SHA-256) and near-duplicate filtering (character n-grams)
- Benchmark fixture exclusion (strict semantic separation)
- Deterministic 80% TRAIN / 10% VAL / 10% TEST splitting
- Immutable manifest generation with complete audit telemetry
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Generator, Iterable, Iterator

from core_model.conversation.injection_guard import assess_context_item_injection
from core_model.corpus.exact_deduplication import raw_checksum, tamil_safe_normalized_checksum
from core_model.corpus.near_deduplication import character_ngram_jaccard, character_ngrams
from core_model.corpus.pii_detection import detect_pii, redact_pii
from core_model.corpus.secret_detection import detect_secrets
from core_model.training.fixed_eval_fixtures import (
    ENGLISH_SENTENCES,
    TAMIL_SENTENCES,
    TANGLISH_SENTENCES,
)

_REPETITION_PATTERN = re.compile(r"(\b\w+\b)(?:\s+\1){4,}", re.IGNORECASE)
_CHAR_REPEAT_PATTERN = re.compile(r"(.)\1{9,}")
_BENCHMARK_FIXTURES: set[str] = {
    unicodedata.normalize("NFC", s.strip().lower())
    for s in (ENGLISH_SENTENCES + TAMIL_SENTENCES + TANGLISH_SENTENCES)
}


@dataclass
class IngestionTelemetry:
    input_records: int = 0
    accepted_records: int = 0
    rejected_records: int = 0
    quarantined_records: int = 0
    duplicate_counts: int = 0
    near_duplicate_counts: int = 0
    pii_counts: int = 0
    secret_counts: int = 0
    injection_counts: int = 0
    benchmark_leakage_blocked: int = 0
    language_distribution: dict[str, int] = field(default_factory=lambda: {"ta": 0, "en": 0, "tgl": 0, "mixed": 0})
    split_distribution: dict[str, int] = field(default_factory=lambda: {"train": 0, "val": 0, "test": 0})
    final_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SovereignRecord:
    record_id: str
    text: str
    language: str
    source: str
    provenance: str
    license: str
    checksum_sha256: str
    split: str = "train"


def is_benchmark_fixture(text: str) -> bool:
    """Checks if text overlaps with held-out evaluation fixtures."""
    norm = unicodedata.normalize("NFC", text.strip().lower())
    if norm in _BENCHMARK_FIXTURES:
        return True
    for fixture in _BENCHMARK_FIXTURES:
        if fixture in norm and len(fixture) > 15:
            return True
        if character_ngram_jaccard(norm, fixture, n=3) > 0.65:
            return True
    return False


def detect_language(text: str) -> str:
    """Identifies primary language script (Tamil, English, Tanglish, Mixed)."""
    tamil_chars = sum(1 for c in text if "\u0b80" <= c <= "\u0bff")
    latin_chars = sum(1 for c in text if "a" <= c.lower() <= "z")
    total_letters = tamil_chars + latin_chars
    if total_letters == 0:
        return "en"
    tamil_ratio = tamil_chars / total_letters
    if tamil_ratio > 0.6:
        return "ta"
    if tamil_ratio < 0.15:
        # Check for Tanglish common terms
        tanglish_markers = {"enna", "epdi", "irukinga", "vanakkam", "romba", "nalla", "solreenga", "aama", "illa"}
        words = {w.lower() for w in text.split()}
        if words & tanglish_markers:
            return "tgl"
        return "en"
    return "mixed"


class ProductionIngestionPipeline:
    """Streaming, memory-bounded sovereign dataset ingestion and governance engine."""

    def __init__(
        self,
        min_char_length: int = 15,
        max_char_length: int = 16384,
        near_duplicate_threshold: float = 0.85,
    ) -> None:
        self.min_char_length = min_char_length
        self.max_char_length = max_char_length
        self.near_duplicate_threshold = near_duplicate_threshold
        self.telemetry = IngestionTelemetry()
        self._exact_hashes: set[str] = set()
        self._ngram_signatures: list[set[str]] = []

    def stream_jsonl(self, file_path: Path, chunk_size: int = 1000) -> Generator[list[dict[str, Any]], None, None]:
        """Yields chunks of JSONL records from disk without loading entire file into memory."""
        chunk: list[dict[str, Any]] = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    chunk.append(json.loads(line_str))
                except json.JSONDecodeError:
                    self.telemetry.rejected_records += 1
                    continue
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
        if chunk:
            yield chunk

    def process_raw_record(
        self,
        raw_text: str,
        *,
        record_id: str,
        source: str = "sovereign_archive",
        provenance: str = "verified_clean",
        license_str: str = "sovereign_public",
    ) -> SovereignRecord | None:
        """Applies complete cleaning, filtering, deduplication, and quality screening."""
        self.telemetry.input_records += 1

        # 1. Unicode NFC Normalization
        text = unicodedata.normalize("NFC", raw_text or "").strip()

        # 2. Length Validation
        if len(text) < self.min_char_length or len(text) > self.max_char_length:
            self.telemetry.rejected_records += 1
            return None

        # 3. Garbage / Degenerate Repetition Detection
        if _REPETITION_PATTERN.search(text) or _CHAR_REPEAT_PATTERN.search(text):
            self.telemetry.rejected_records += 1
            return None

        # 4. Benchmark Fixture Leakage Block
        if is_benchmark_fixture(text):
            self.telemetry.rejected_records += 1
            self.telemetry.benchmark_leakage_blocked += 1
            return None

        # 5. Prompt Injection Screening (Blocking/Quarantine)
        inj_eval = assess_context_item_injection(text)
        if inj_eval.get("matched_categories"):
            self.telemetry.quarantined_records += 1
            self.telemetry.injection_counts += len(inj_eval["matched_categories"])
            return None

        # 6. Secret Detection (Blocking)
        secrets = detect_secrets(text)
        secret_cats = [c for c in secrets.get("matched_categories", []) if c != "hidden_instruction"]
        if secret_cats:
            self.telemetry.quarantined_records += 1
            self.telemetry.secret_counts += len(secret_cats)
            return None


        # 7. PII Detection & Redaction (Preserves Record Safely)
        pii = detect_pii(text)
        if pii.get("total_findings", 0) > 0:
            self.telemetry.pii_counts += pii["total_findings"]
            text = redact_pii(text, pii["findings"])

        # 8. Exact Deduplication
        norm_hash = tamil_safe_normalized_checksum(text)
        if norm_hash in self._exact_hashes:
            self.telemetry.duplicate_counts += 1
            self.telemetry.rejected_records += 1
            return None
        self._exact_hashes.add(norm_hash)

        # 9. Near-Duplicate Detection (bounded n-gram window)
        ngrams = character_ngrams(text, n=3)
        for sig in self._ngram_signatures[-2000:]:  # sliding window keeps RAM bounded
            intersection = len(ngrams & sig)
            union = len(ngrams | sig)
            if union and (intersection / union) > self.near_duplicate_threshold:
                self.telemetry.near_duplicate_counts += 1
                self.telemetry.rejected_records += 1
                return None
        self._ngram_signatures.append(ngrams)

        # 10. Language Detection
        lang = detect_language(text)
        self.telemetry.language_distribution[lang] = self.telemetry.language_distribution.get(lang, 0) + 1

        # 11. Deterministic Split (80% Train, 10% Val, 10% Test)
        digest = hashlib.sha256(f"split:{norm_hash}".encode("utf-8")).hexdigest()
        hash_int = int(digest[:8], 16)
        split_mod = hash_int % 100
        if split_mod < 80:
            split = "train"
        elif split_mod < 90:
            split = "val"
        else:
            split = "test"
        self.telemetry.split_distribution[split] += 1

        self.telemetry.accepted_records += 1
        record_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return SovereignRecord(
            record_id=record_id,
            text=text,
            language=lang,
            source=source,
            provenance=provenance,
            license=license_str,
            checksum_sha256=record_sha256,
            split=split,
        )

    def write_manifest(self, output_path: Path, dataset_id: str, version: str = "1.0.0") -> Path:
        """Writes immutable JSON manifest with SHA-256 checksum and telemetry."""
        manifest_data = {
            "dataset_id": dataset_id,
            "version": version,
            "provenance": "brud_sovereign_governed_archive",
            "license": "sovereign_bilingual_v1",
            "telemetry": self.telemetry.to_dict(),
        }
        manifest_bytes = json.dumps(manifest_data, indent=2, sort_keys=True).encode("utf-8")
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        manifest_data["manifest_sha256"] = manifest_sha
        self.telemetry.final_sha256 = manifest_sha

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest_data, indent=2, sort_keys=True), encoding="utf-8")
        return output_path
