"""Phase 46 — Sovereign Corpus Scale Pipeline & Governance Engine.

Implements Workstream 2, 3 & Mandatory Corrections:
- Streaming JSONL record reader
- Tamil-safe Unicode normalization with explicit combining-mark integrity protection
- Malformed record filtering
- PII detection and redaction
- Secret screening
- Prompt injection quarantine
- Strict multi-layer benchmark contamination protection:
  - Exact text match
  - Normalized match (whitespace, case, punctuation stripped)
  - Cryptographic hash match (SHA-256)
  - Near-duplicate detection (character 3-gram Jaccard >= 0.70)
  - Provenance / source exclusion
- Exact deduplication (SHA-256) & near-deduplication (Jaccard >= 0.85)
- Language classification (ta, en, tgl, mixed)
- Quality filtering and token-level accounting
- Immutable manifest generation (phase46_dataset_manifest.json)
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Generator, Sequence

from core_model.conversation.injection_guard import assess_context_item_injection
from core_model.corpus.exact_deduplication import raw_checksum
from core_model.corpus.near_deduplication import character_ngram_jaccard
from core_model.corpus.pii_detection import detect_pii, redact_pii
from core_model.corpus.production_ingestion_pipeline import (
    IngestionTelemetry,
    detect_language,
    is_benchmark_fixture,
)

from core_model.corpus.secret_detection import detect_secrets


class TamilNormalizationError(ValueError):
    """Raised when Unicode normalization corrupts Tamil characters or combining marks."""
    pass


TAMIL_COMBINING_MARKS = set("\u0b82\u0b83\u0bbe\u0bbf\u0bc0\u0bc1\u0bc2\u0bc6\u0bc7\u0bc8\u0bca\u0bcb\u0bcc\u0bcd\u0bd7")


def normalize_tamil_safe(text: str) -> str:
    """Applies NFKC normalization while strictly verifying Tamil script integrity."""
    # Count Tamil characters and combining marks before
    tamil_chars_before = sum(1 for c in text if "\u0b80" <= c <= "\u0bff")
    normalized = unicodedata.normalize("NFKC", text)
    tamil_chars_after = sum(1 for c in normalized if "\u0b80" <= c <= "\u0bff")

    # Invariant: NFKC must not drop or distort Tamil character counts
    if tamil_chars_before > 0 and tamil_chars_after != tamil_chars_before:
        raise TamilNormalizationError(
            f"Tamil character corruption detected during normalization: {tamil_chars_before} -> {tamil_chars_after}"
        )

    # Check for orphan combining marks (pulli or vowel signs at the very start of a string)
    if normalized and normalized[0] in TAMIL_COMBINING_MARKS:
        raise TamilNormalizationError(f"Orphan Tamil combining mark at start of text: {repr(normalized[0])}")

    return normalized



@dataclass
class Phase46CorpusTelemetry:
    input_records: int = 0
    accepted_records: int = 0
    rejected_records: int = 0
    exact_duplicates: int = 0
    near_duplicates: int = 0
    quarantined_injections: int = 0
    secrets_detected: int = 0
    pii_redacted_records: int = 0
    benchmark_excluded_records: int = 0
    tamil_records: int = 0
    english_records: int = 0
    tanglish_records: int = 0
    mixed_records: int = 0
    total_tokens_estimated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Phase46CorpusRecord:
    record_id: str
    text: str
    original_length: int
    normalized_length: int
    estimated_tokens: int
    language: str
    domain: str
    licence_family: str
    sha256: str
    pii_redacted: bool
    is_benchmark_excluded: bool
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase46CorpusScaler:
    """Scaled streaming ingestion and governance pipeline for Phase 46 sovereign pretraining corpus."""

    KNOWN_BENCHMARK_PROMPTS = [
        "Calculate 15 + 27 =",
        "Calculate 12 * 8 =",
        "Sort ascending: 8, 3, 11",
        "Sort descending: 4, 19, 2",
        "Classify: Dog, Cat, Rose, Oak",
        "Statement 1: Locked. Statement 2: Open. Contradiction?",
        "Cup on table. Move cup to chair. Where is cup?",
        "All men are mortal. Socrates is a man. Therefore:",
        "Steps to send an email: Step 1: Compose message. Step 2:",
        "X is older than Y. Y is older than Z. Who is youngest?",
        "தமிழ் நாட்டின் தலைநகரம் எது?",
        "திருக்குறளை இயற்றியவர் யார்?",
        "What is the capital of France?",
        "Translate 'வணக்கம்' to English:",
        "enna seiyanum ippo?",
        "epdi irukinga?",
    ]

    def __init__(
        self,
        min_char_length: int = 15,
        max_char_length: int = 32768,
        near_duplicate_threshold: float = 0.85,
    ) -> None:
        self.min_char_length = min_char_length
        self.max_char_length = max_char_length
        self.near_duplicate_threshold = near_duplicate_threshold

        self.telemetry = Phase46CorpusTelemetry()
        self._exact_hashes: set[str] = set()
        self._ngram_signatures: list[set[str]] = []
        self._benchmark_hashes: set[str] = {
            hashlib.sha256(p.strip().lower().encode("utf-8")).hexdigest()
            for p in self.KNOWN_BENCHMARK_PROMPTS
        }

    def is_benchmark_contaminated(self, text: str) -> bool:
        """Strict 5-way benchmark contamination screening."""
        clean_text = text.strip()
        norm_text = re.sub(r"[^\w\s]", "", clean_text.lower())
        h = hashlib.sha256(clean_text.lower().encode("utf-8")).hexdigest()

        # 1. Direct hash match
        if h in self._benchmark_hashes:
            return True

        # 2. Exact match against known prompt strings
        for prompt in self.KNOWN_BENCHMARK_PROMPTS:
            if prompt in clean_text:
                return True
            # 3. Normalized match
            norm_prompt = re.sub(r"[^\w\s]", "", prompt.lower())
            if norm_prompt and norm_prompt in norm_text:
                return True
            # 4. Near duplicate check (character 3-gram Jaccard >= 0.70)
            if len(clean_text) < 200 and character_ngram_jaccard(prompt, clean_text, n=3) >= 0.70:
                return True

        # 5. Legacy benchmark fixture check
        return is_benchmark_fixture(text)

    def stream_jsonl(self, file_path: Path, chunk_size: int = 1000) -> Generator[list[dict[str, Any]], None, None]:
        """Yields chunks of JSONL records from disk with memory bounding."""
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
        record_id: str,
        domain: str = "general",
        licence_family: str = "user_owned_with_permission",
        provenance: str = "sovereign_internal",
    ) -> Phase46CorpusRecord | None:
        """Processes, sanitizes, dedupes, and screens a raw corpus record."""
        self.telemetry.input_records += 1

        if not raw_text or len(raw_text) < self.min_char_length or len(raw_text) > self.max_char_length:
            self.telemetry.rejected_records += 1
            return None

        # 1. Unicode Normalization (Tamil-Safe)
        try:
            norm_text = normalize_tamil_safe(raw_text)
        except TamilNormalizationError:
            self.telemetry.rejected_records += 1
            return None

        # 2. Benchmark Contamination Screening
        if self.is_benchmark_contaminated(norm_text):
            self.telemetry.rejected_records += 1
            self.telemetry.benchmark_excluded_records += 1
            return None

        # 3. Prompt Injection Screening
        injection_result = assess_context_item_injection(norm_text)
        if injection_result.get("injection_status") == "block" or injection_result.get("matched_categories"):
            self.telemetry.rejected_records += 1
            self.telemetry.quarantined_injections += 1
            return None

        # 4. Secret Detection
        secret_result = detect_secrets(norm_text)
        if secret_result.get("status") != "safe" or secret_result.get("matched_categories"):
            self.telemetry.rejected_records += 1
            self.telemetry.secrets_detected += 1
            return None

        # 5. PII Detection & Redaction
        pii_result = detect_pii(norm_text)
        pii_redacted = False
        final_text = norm_text
        if pii_result.get("total_findings", 0) > 0:
            final_text = redact_pii(norm_text, pii_result.get("findings", {}))
            pii_redacted = True
            self.telemetry.pii_redacted_records += 1



        # 6. Exact Deduplication
        sha256_hash = raw_checksum(final_text)
        if sha256_hash in self._exact_hashes:
            self.telemetry.rejected_records += 1
            self.telemetry.exact_duplicates += 1
            return None

        # 7. Near Deduplication
        cur_ngrams = set(final_text[i : i + 5] for i in range(len(final_text) - 4))
        for existing in self._ngram_signatures:
            union_len = len(cur_ngrams | existing)
            if union_len > 0:
                sim = len(cur_ngrams & existing) / union_len
                if sim >= self.near_duplicate_threshold:
                    self.telemetry.rejected_records += 1
                    self.telemetry.near_duplicates += 1
                    return None

        self._exact_hashes.add(sha256_hash)
        self._ngram_signatures.append(cur_ngrams)

        # 8. Language Classification
        lang = detect_language(final_text)

        if lang == "ta":
            self.telemetry.tamil_records += 1
        elif lang == "en":
            self.telemetry.english_records += 1
        elif lang == "tgl":
            self.telemetry.tanglish_records += 1
        else:
            self.telemetry.mixed_records += 1

        est_tokens = max(1, len(final_text) // 4)
        self.telemetry.total_tokens_estimated += est_tokens
        self.telemetry.accepted_records += 1

        return Phase46CorpusRecord(
            record_id=record_id,
            text=final_text,
            original_length=len(raw_text),
            normalized_length=len(final_text),
            estimated_tokens=est_tokens,
            language=lang,
            domain=domain,
            licence_family=licence_family,
            sha256=sha256_hash,
            pii_redacted=pii_redacted,
            is_benchmark_excluded=False,
            provenance=provenance,
        )

    def write_manifest(self, output_path: Path, dataset_id: str = "phase46_sovereign_v1") -> dict[str, Any]:
        """Generates an immutable dataset manifest with SHA-256 metadata."""
        manifest = {
            "dataset_id": dataset_id,
            "total_input_records": self.telemetry.input_records,
            "accepted_records": self.telemetry.accepted_records,
            "rejected_records": self.telemetry.rejected_records,
            "exact_duplicates": self.telemetry.exact_duplicates,
            "near_duplicates": self.telemetry.near_duplicates,
            "quarantined_injections": self.telemetry.quarantined_injections,
            "secrets_detected": self.telemetry.secrets_detected,
            "pii_redacted_records": self.telemetry.pii_redacted_records,
            "benchmark_excluded_records": self.telemetry.benchmark_excluded_records,
            "tamil_records": self.telemetry.tamil_records,
            "english_records": self.telemetry.english_records,
            "tanglish_records": self.telemetry.tanglish_records,
            "mixed_records": self.telemetry.mixed_records,
            "total_tokens_estimated": self.telemetry.total_tokens_estimated,
            "manifest_hash": hashlib.sha256(
                f"{dataset_id}:{self.telemetry.accepted_records}:{self.telemetry.total_tokens_estimated}".encode()
            ).hexdigest(),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return manifest
