"""Phase 47 Sovereign Corpus Expansion Engine.

Discovers, verifies provenance, filters, normalizes, dedupes, and compiles
multi-source approved sovereign datasets into deterministic splits with
an immutable manifest and 5-way benchmark contamination protection.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Generator

from core_model.conversation.injection_guard import assess_context_item_injection
from core_model.corpus.exact_deduplication import raw_checksum
from core_model.corpus.near_deduplication import character_ngram_jaccard
from core_model.corpus.pii_detection import detect_pii, redact_pii
from core_model.corpus.production_ingestion_pipeline import (
    detect_language,
    is_benchmark_fixture,
)
from core_model.corpus.secret_detection import detect_secrets


class TamilNormalizationError(ValueError):
    """Raised when Tamil Unicode integrity is corrupted or orphan marks exist."""

    pass


TAMIL_COMBINING_MARKS = set(
    "\u0b82\u0b83\u0bbe\u0bbf\u0bc0\u0bc1\u0bc2\u0bc6\u0bc7\u0bc8\u0bca\u0bcb\u0bcc\u0bcd\u0bd7"
)


def normalize_tamil_safe(text: str) -> str:
    """Applies NFKC normalization while strictly verifying Tamil script integrity."""
    tamil_chars_before = sum(1 for c in text if "\u0b80" <= c <= "\u0bff")
    normalized = unicodedata.normalize("NFKC", text)
    tamil_chars_after = sum(1 for c in normalized if "\u0b80" <= c <= "\u0bff")

    # Invariant: NFKC must not drop or distort Tamil characters
    if tamil_chars_before > 0 and tamil_chars_after != tamil_chars_before:
        raise TamilNormalizationError(
            f"Tamil character corruption detected: {tamil_chars_before} -> {tamil_chars_after}"
        )

    # Check for orphan combining marks at string start
    if normalized and normalized[0] in TAMIL_COMBINING_MARKS:
        raise TamilNormalizationError(
            f"Orphan Tamil combining mark at start of text: {repr(normalized[0])}"
        )

    return normalized


@dataclass
class Phase47CorpusTelemetry:
    discovered_sources: int = 0
    input_records: int = 0
    accepted_records: int = 0
    rejected_unapproved: int = 0
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
    train_split_count: int = 0
    validation_split_count: int = 0
    test_split_count: int = 0
    total_tokens_estimated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Phase47CorpusRecord:
    record_id: str
    text: str
    original_length: int
    normalized_length: int
    estimated_tokens: int
    language: str
    domain: str
    licence_family: str
    rights_status: str
    approval_status: str
    is_trainable: bool
    sha256: str
    pii_redacted: bool
    is_benchmark_excluded: bool
    source_id: str
    source_path: str
    split: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase47CorpusExpander:
    """Multi-source sovereign corpus crawler, validator, and manifest generator."""

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

    APPROVED_RIGHTS = {"verified", "user_owned_with_permission", "approved", "public_domain"}

    def __init__(
        self,
        min_char_length: int = 15,
        max_char_length: int = 32768,
        near_duplicate_threshold: float = 0.85,
    ) -> None:
        self.min_char_length = min_char_length
        self.max_char_length = max_char_length
        self.near_duplicate_threshold = near_duplicate_threshold

        self.telemetry = Phase47CorpusTelemetry()
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
        norm_text = " ".join(norm_text.split())
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
            norm_prompt = " ".join(norm_prompt.split())
            if norm_prompt and norm_prompt in norm_text:
                return True
            # 4. Near duplicate check (character 3-gram Jaccard >= 0.70)
            if len(clean_text) < 200 and character_ngram_jaccard(prompt, clean_text, n=3) >= 0.70:
                return True

        # 5. Legacy benchmark fixture check
        return is_benchmark_fixture(text)


    def is_approved_for_training(self, rights_status: str, licence_family: str, approval_status: str) -> bool:
        """Mandatory Gate: Approved = Trainable. Unapproved records are excluded."""
        if approval_status.lower() != "approved":
            return False
        if rights_status.lower() not in self.APPROVED_RIGHTS and licence_family.lower() not in self.APPROVED_RIGHTS:
            return False
        return True

    def assign_deterministic_split(self, text_sha256: str) -> str:
        """Deterministically assigns 80% train, 10% val, 10% test using SHA-256 modulo."""
        val = int(text_sha256[:8], 16) % 100
        if val < 80:
            return "train"
        elif val < 90:
            return "validation"
        else:
            return "test"

    def process_record(
        self,
        raw_text: str,
        record_id: str,
        domain: str = "general",
        licence_family: str = "user_owned_with_permission",
        rights_status: str = "verified",
        approval_status: str = "approved",
        source_id: str = "source_default",
        source_path: str = "",
    ) -> Phase47CorpusRecord | None:
        """Validates, screens, normalizes, dedupes, and gates an individual record."""
        self.telemetry.input_records += 1

        # 0. Mandatory Approval Gate (Correction 2)
        if not self.is_approved_for_training(rights_status, licence_family, approval_status):
            self.telemetry.rejected_unapproved += 1
            self.telemetry.rejected_records += 1
            return None

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

        # 7. Near Deduplication (5-gram Jaccard)
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

        # 9. Deterministic Split Assignment
        split = self.assign_deterministic_split(sha256_hash)
        if split == "train":
            self.telemetry.train_split_count += 1
        elif split == "validation":
            self.telemetry.validation_split_count += 1
        else:
            self.telemetry.test_split_count += 1

        est_tokens = max(1, len(final_text) // 4)
        self.telemetry.total_tokens_estimated += est_tokens
        self.telemetry.accepted_records += 1

        return Phase47CorpusRecord(
            record_id=record_id,
            text=final_text,
            original_length=len(raw_text),
            normalized_length=len(final_text),
            estimated_tokens=est_tokens,
            language=lang,
            domain=domain,
            licence_family=licence_family,
            rights_status=rights_status,
            approval_status=approval_status,
            is_trainable=True,
            sha256=sha256_hash,
            pii_redacted=pii_redacted,
            is_benchmark_excluded=False,
            source_id=source_id,
            source_path=source_path,
            split=split,
        )

    def stream_source_file(self, file_path: Path, chunk_size: int = 1000) -> Generator[list[dict[str, Any]], None, None]:
        """Streams records from JSONL file with memory bounding."""
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

    def write_manifest(
        self,
        output_file: Path,
        dataset_id: str,
        source_id: str = "sovereign_multi_source_v1",
        source_path: str = "data/corpus_exports;data/document_sft_exports",
        source_hash: str = "",
        tokenizer_hash: str = "sovereign_sp_32k",
    ) -> dict[str, Any]:
        """Generates and writes an immutable dataset manifest."""
        manifest_data = {
            "dataset_id": dataset_id,
            "source_id": source_id,
            "source_path": source_path,
            "source_hash": source_hash or hashlib.sha256(source_path.encode()).hexdigest(),
            "record_count": self.telemetry.accepted_records,
            "total_input_records": self.telemetry.input_records,
            "rejected_unapproved": self.telemetry.rejected_unapproved,
            "estimated_token_count": self.telemetry.total_tokens_estimated,
            "language_distribution": {
                "ta": self.telemetry.tamil_records,
                "en": self.telemetry.english_records,
                "tgl": self.telemetry.tanglish_records,
                "mixed": self.telemetry.mixed_records,
            },
            "train_count": self.telemetry.train_split_count,
            "validation_count": self.telemetry.validation_split_count,
            "test_count": self.telemetry.test_split_count,
            "contamination_checks": {
                "benchmark_prompts_screened": len(self.KNOWN_BENCHMARK_PROMPTS),
                "excluded_count": self.telemetry.benchmark_excluded_records,
                "quarantined_injections": self.telemetry.quarantined_injections,
                "secrets_detected": self.telemetry.secrets_detected,
                "pii_redacted_count": self.telemetry.pii_redacted_records,
            },
            "normalization_policy": "NFKC_TAMIL_SAFE_COMBINING_MARKS_PRESERVED",
            "tokenizer_hash": tokenizer_hash,
            "creation_timestamp": time.time(),
        }

        # Root manifest hash calculation
        hasher = hashlib.sha256()
        hasher.update(dataset_id.encode("utf-8"))
        hasher.update(str(self.telemetry.accepted_records).encode("utf-8"))
        hasher.update(str(self.telemetry.total_tokens_estimated).encode("utf-8"))
        hasher.update(tokenizer_hash.encode("utf-8"))
        manifest_data["manifest_hash"] = hasher.hexdigest()

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as handle:
            json.dump(manifest_data, handle, indent=2)

        return manifest_data
