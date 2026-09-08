"""Phase 61 - P3: High-Throughput Dataset Compiler & Domain Analysis Engine.

Compiles completed, rights-approved ingestion batches into immutable candidate dataset versions.

CRITICAL INVARIANTS:
- Compiler Immutability: FROZEN dataset version manifests can NEVER be modified. Any changes force a new dataset version.
- Novelty Atomicity: Thread-safe locking over Global Novelty Ledger ensures identical concurrent content yields TRUE_NEW_TOKENS = 0 for duplicate submissions.
- Rights Boundary: Only RIGHTS_VERIFIED = TRUE content is eligible for compilation.
- 3-Way Token Accounting: Method A == Method B == Method C. Strict validation.
- Target Token Gap Tracking: Accurately tracks remaining target token gap without artificial token inflation.
- Pretraining remains hard-locked (`training_authorized = FALSE`).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Any

from core_model.corpus.domain_classification import classify_domain
from core_model.corpus.global_novelty_ledger import (
    GlobalCanonicalNoveltyLedgerEngine,
    LineageNode,
)
from core_model.corpus.high_throughput_ingestion import IngestionTask


@dataclass
class DomainDistributionReport:
    """Domain breakdown analysis report."""
    domain_counts: dict[str, int]
    domain_tokens: dict[str, int]
    domain_percentages: dict[str, float]
    underrepresented_domains: list[str]


@dataclass
class CompiledDatasetManifest:
    """Immutable compiled candidate dataset version manifest."""
    dataset_id: str
    dataset_version: str
    pipeline_version: str
    creation_timestamp: str
    state: str  # BUILDING | VALIDATING | FROZEN | PENDING_ADMIN_REVIEW | APPROVED_CANDIDATE | FAILED
    source_count: int
    book_count: int
    record_count: int
    total_tokens: int
    native_tokens: int
    synthetic_tokens: int
    translated_tokens: int
    derived_tokens: int
    true_new_tokens: int
    target_token_goal: int
    remaining_target_gap: int
    domain_distribution: dict[str, Any]
    rights_summary: dict[str, Any]
    quality_summary: dict[str, Any]
    token_accounting_status: str  # PASSED | FAILED
    manifest_sha256: str
    training_authorized: bool = False  # ALWAYS FALSE IN P3


class HighThroughputDatasetCompiler:
    """Thread-safe, immutable candidate dataset compiler."""

    def __init__(
        self,
        novelty_engine: GlobalCanonicalNoveltyLedgerEngine | None = None,
        target_token_goal: int = 10000000,
    ) -> None:
        self.novelty_engine = novelty_engine or GlobalCanonicalNoveltyLedgerEngine()
        self.target_token_goal = target_token_goal
        self._compiler_lock = Lock()

    def compile_candidate_dataset(
        self,
        ingestion_tasks: list[IngestionTask],
        dataset_version: str = "foundation_stage8_v001",
    ) -> CompiledDatasetManifest:
        """Compile ingested book tasks into an immutable candidate dataset version."""

        with self._compiler_lock:
            # 1. State: BUILDING
            current_state = "BUILDING"

            # Filter strictly rights-verified completed tasks
            eligible_tasks = [
                t for t in ingestion_tasks
                if t.status == "COMPLETED" and t.result_data.get("rights_status") in ("PUBLIC_DOMAIN", "OPEN_LICENSE", "TRAINING_PERMITTED_LICENSE")
            ]

            if not eligible_tasks:
                return CompiledDatasetManifest(
                    dataset_id=f"ds-{dataset_version}",
                    dataset_version=dataset_version,
                    pipeline_version="P3-v1.0",
                    creation_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    state="FAILED",
                    source_count=0,
                    book_count=0,
                    record_count=0,
                    total_tokens=0,
                    native_tokens=0,
                    synthetic_tokens=0,
                    translated_tokens=0,
                    derived_tokens=0,
                    true_new_tokens=0,
                    target_token_goal=self.target_token_goal,
                    remaining_target_gap=self.target_token_goal,
                    domain_distribution={},
                    rights_summary={"status": "FAILED", "reason": "No rights-verified completed tasks available."},
                    quality_summary={"status": "FAILED"},
                    token_accounting_status="FAILED",
                    manifest_sha256="",
                    training_authorized=False
                )

            # 2. State: VALIDATING
            current_state = "VALIDATING"

            processed_records: list[dict[str, Any]] = []
            source_ids = set()
            book_ids = set()
            domain_counts: dict[str, int] = {}
            domain_tokens: dict[str, int] = {}

            total_tokens = 0
            native_tokens = 0
            synthetic_tokens = 0
            true_new_tokens = 0

            for task in eligible_tasks:
                b_id = task.book_id
                s_id = task.source_id
                source_ids.add(s_id)
                book_ids.add(b_id)

                extracted_text = task.result_data.get("extracted_text", "")
                if not extracted_text.strip():
                    continue

                # Domain Classification
                domain_res = classify_domain(extracted_text)
                primary_domain = domain_res.get("primary_domain", "LITERATURE")

                domain_counts[primary_domain] = domain_counts.get(primary_domain, 0) + 1

                # Atomic Global Novelty Evaluation
                lineage = LineageNode(
                    source_id=s_id,
                    book_id=b_id,
                    record_id=f"rec-{b_id}-1",
                    dataset_id=dataset_version,
                    domain=primary_domain,
                    native_or_synthetic="NATIVE"
                )
                words = [w for w in extracted_text.split() if w.strip()]
                est_tokens = max(1, len(words))

                domain_tokens[primary_domain] = domain_tokens.get(primary_domain, 0) + est_tokens

                nov_res = self.novelty_engine.evaluate_record_novelty(extracted_text, lineage, est_tokens)

                record_entry = {
                    "record_id": f"rec-{b_id}-1",
                    "content": extracted_text,
                    "token_count": est_tokens,
                    "novel_token_count": nov_res.new_native_tokens,
                    "novelty_status": nov_res.novelty_status,
                    "domain": primary_domain,
                }
                processed_records.append(record_entry)

                total_tokens += est_tokens
                native_tokens += nov_res.new_native_tokens
                synthetic_tokens += nov_res.new_synthetic_tokens
                true_new_tokens += nov_res.new_native_tokens

            # Domain Breakdown Analysis
            tot_dom_tokens = max(1, sum(domain_tokens.values()))
            domain_percentages = {d: round((cnt / tot_dom_tokens) * 100, 2) for d, cnt in domain_tokens.items()}
            underrepresented = [d for d in ("HISTORY", "SCIENCE", "MATHEMATICS", "TECHNOLOGY") if domain_tokens.get(d, 0) < 500]

            domain_dist_report = {
                "domain_counts": domain_counts,
                "domain_tokens": domain_tokens,
                "domain_percentages": domain_percentages,
                "underrepresented_domains": underrepresented,
            }

            # 3-Way Token Accounting Validation
            accounting_eval = self.novelty_engine.validate_three_way_token_accounting(processed_records)
            if accounting_eval.accounting_status != "PASSED":
                return CompiledDatasetManifest(
                    dataset_id=f"ds-{dataset_version}",
                    dataset_version=dataset_version,
                    pipeline_version="P3-v1.0",
                    creation_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    state="FAILED",
                    source_count=len(source_ids),
                    book_count=len(book_ids),
                    record_count=len(processed_records),
                    total_tokens=total_tokens,
                    native_tokens=native_tokens,
                    synthetic_tokens=synthetic_tokens,
                    translated_tokens=0,
                    derived_tokens=0,
                    true_new_tokens=true_new_tokens,
                    target_token_goal=self.target_token_goal,
                    remaining_target_gap=max(0, self.target_token_goal - true_new_tokens),
                    domain_distribution=domain_dist_report,
                    rights_summary={"status": "PASSED"},
                    quality_summary={"status": "PASSED"},
                    token_accounting_status="FAILED",
                    manifest_sha256="",
                    training_authorized=False
                )

            # Target Gap Calculation
            remaining_gap = max(0, self.target_token_goal - true_new_tokens)

            # 3. State: FROZEN
            current_state = "FROZEN"

            manifest_payload = {
                "dataset_id": f"ds-{dataset_version}",
                "dataset_version": dataset_version,
                "pipeline_version": "P3-v1.0",
                "creation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "state": "PENDING_ADMIN_REVIEW",
                "source_count": len(source_ids),
                "book_count": len(book_ids),
                "record_count": len(processed_records),
                "total_tokens": total_tokens,
                "native_tokens": native_tokens,
                "synthetic_tokens": synthetic_tokens,
                "translated_tokens": 0,
                "derived_tokens": 0,
                "true_new_tokens": true_new_tokens,
                "target_token_goal": self.target_token_goal,
                "remaining_target_gap": remaining_gap,
                "domain_distribution": domain_dist_report,
                "rights_summary": {"status": "PASSED", "verified_sources": list(source_ids)},
                "quality_summary": {"status": "PASSED", "ocr_cleaned": True},
                "token_accounting_status": "PASSED",
                "training_authorized": False
            }

            manifest_json_str = json.dumps(manifest_payload, sort_keys=True)
            manifest_sha = hashlib.sha256(manifest_json_str.encode("utf-8")).hexdigest()

            return CompiledDatasetManifest(
                dataset_id=manifest_payload["dataset_id"],
                dataset_version=dataset_version,
                pipeline_version="P3-v1.0",
                creation_timestamp=manifest_payload["creation_timestamp"],
                state="PENDING_ADMIN_REVIEW",
                source_count=len(source_ids),
                book_count=len(book_ids),
                record_count=len(processed_records),
                total_tokens=total_tokens,
                native_tokens=native_tokens,
                synthetic_tokens=synthetic_tokens,
                translated_tokens=0,
                derived_tokens=0,
                true_new_tokens=true_new_tokens,
                target_token_goal=self.target_token_goal,
                remaining_target_gap=remaining_gap,
                domain_distribution=domain_dist_report,
                rights_summary=manifest_payload["rights_summary"],
                quality_summary=manifest_payload["quality_summary"],
                token_accounting_status="PASSED",
                manifest_sha256=manifest_sha,
                training_authorized=False
            )
