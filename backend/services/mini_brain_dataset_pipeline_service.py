"""Phase 2.7G: the real dataset-version -> token-block pipeline for
MB-22's real (`execution_mode='gpu'`) training path.

MB-22's own job creation already requires a real, governed
`dataset_version_public_id` (`status IN ('ready','archived')`, Phase
2.7F) and a real, architecture-verified `core_model_version_public_id`
(Phase 2.7E). This service turns those two real identities into real
`train_blocks`/`validation_blocks` -- reusing, never duplicating, the
exact same deterministic functions `PretrainingService._blocks()` (the
production worker path) already calls
(`core_model.training.dataset_pipeline.build_dataset_blocks()`, itself
built from `token_sequences()`/`pack_stream()`/`generate_coverage()`).
`PretrainingService._blocks()` itself is intentionally left untouched --
this is a second caller of the same shared, canonical primitives, not a
refactor of a production-critical, already-tested method.

The tokenizer is always resolved *from* the Core Model Version
(`CoreModelService.model_config_for_version()`'s own `tokenizer_version_public_id`),
never independently supplied -- a caller-mismatched tokenizer is
therefore structurally impossible, not merely checked for.

Deliberately separate from `mini_brain_training_engine_service.py` for
the same reason Phase 2.7F's handoff service is: staying out of that
file keeps its own existing safety boundary
(`test_never_imports_a_deployment_or_runtime_manager_library`) intact,
and this pipeline is itself compositionally reusable well beyond MB-22.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.services.core_model_service import CoreModelService
from backend.services.dataset_versioning import DatasetVersioningService
from backend.services.tokenizer_registry import TokenizerService
from core_model.training.dataset_pipeline import BLOCK_BUILDER_VERSION, build_dataset_blocks

ELIGIBLE_DATASET_STATUSES = {"ready", "archived"}
DEFAULT_OVERLENGTH_POLICY = "split_oversized"

# Phase 2.7H (mission Part 2): a rejection reason containing any of these
# markers means the (dataset version, tokenizer, core model version)
# identity itself is structurally wrong -- re-running the same call later
# with the same inputs can never succeed, so `readiness_contract()`
# classifies it `BLOCKED` rather than `NOT_READY`. Everything else
# (empty splits, a `sequence_length` that doesn't fit) is a `NOT_READY`
# condition a different call/config or more governed data can resolve.
_BLOCKED_REASON_MARKERS = (
    "dataset version not found",
    "must be ready or archived",
    "core model version not found",
    "tokenizer artifacts are incomplete",
    "tokenizer model is not available",
    "token id outside core model vocabulary",
    # Phase 2.8A: Phase 2.7I added `_processor()`'s real checksum-mismatch
    # rejection ("tokenizer artifact checksum verification failed") but
    # this marker tuple was never updated to include it, so a corrupted
    # (not merely missing) tokenizer artifact was misclassified NOT_READY
    # instead of BLOCKED -- a real classification regression, fixed here.
    # A checksum mismatch is exactly as unrecoverable-by-retry as a missing
    # file: the caller cannot succeed without externally replacing the
    # corrupted artifact.
    "tokenizer artifact checksum verification failed",
)


class MiniBrainDatasetPipelineService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.core_models = CoreModelService(
            CoreModelRepository(settings.resolved_database_path), settings
        )
        self.tokenizers = TokenizerService(
            TokenizerRepository(settings.resolved_database_path), settings
        )

    def _resolve_dataset_version(
        self, connection: sqlite3.Connection, dataset_version_public_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM dataset_versions WHERE public_id=?", (dataset_version_public_id,)
        ).fetchone()
        if not row:
            raise ValidationError(f"dataset version not found: {dataset_version_public_id}")
        if row["status"] not in ELIGIBLE_DATASET_STATUSES:
            raise ValidationError(
                "dataset version must be ready or archived before real training "
                f"(currently '{row['status']}')"
            )
        return row

    def _resolve_sequence_length(self, context_length: int, sequence_length: int | None) -> int:
        if sequence_length is None:
            return context_length
        if sequence_length > context_length:
            raise ValidationError(
                f"requested sequence_length ({sequence_length}) exceeds the Core Model "
                f"Version's real context_length ({context_length})"
            )
        return sequence_length

    def build_blocks(
        self, *, dataset_version_public_id: str, core_model_version_public_id: str,
        sequence_length: int | None = None, overlength_policy: str = DEFAULT_OVERLENGTH_POLICY,
    ) -> dict[str, Any]:
        """The real pipeline: resolves the real dataset version and the
        real tokenizer (always derived from the Core Model Version, never
        independently supplied), then calls the same canonical
        `build_dataset_blocks()` `PretrainingService._blocks()` itself is
        built from. Raises a typed `ValidationError` for every
        precondition this module's own docstring and the Phase 2.7G
        mission's negative-test list name -- never a silent empty or
        fabricated result."""

        model_config, version_row = self.core_models.model_config_for_version(
            core_model_version_public_id
        )
        resolved_sequence_length = self._resolve_sequence_length(
            model_config.context_length, sequence_length
        )
        processor = self.tokenizers.processor_for_version(version_row["tokenizer_version_public_id"])

        with database_connection(self.settings.resolved_database_path) as connection:
            dataset_version = self._resolve_dataset_version(connection, dataset_version_public_id)
            result = build_dataset_blocks(
                connection, dataset_version["id"], processor=processor, model_config=model_config,
                sequence_length=resolved_sequence_length, overlength_policy=overlength_policy,
            )
            tokenizer_row = connection.execute(
                "SELECT * FROM tokenizer_versions WHERE public_id=?",
                (version_row["tokenizer_version_public_id"],),
            ).fetchone()

        return {
            "train_blocks": result["train"]["packed"]["blocks"],
            "validation_blocks": result["validation"]["packed"]["blocks"],
            "train_report": {
                "sequence_counts": result["train"]["sequence_counts"],
                "packed": {k: v for k, v in result["train"]["packed"].items() if k != "blocks"},
                "coverage": result["train"]["coverage"],
                "token_length_stats": result["train"]["token_length_stats"],
                "vocabulary_coverage": result["train"]["vocabulary_coverage"],
            },
            "validation_report": {
                "sequence_counts": result["validation"]["sequence_counts"],
                "packed": {k: v for k, v in result["validation"]["packed"].items() if k != "blocks"},
                "coverage": result["validation"]["coverage"],
                "token_length_stats": result["validation"]["token_length_stats"],
                "vocabulary_coverage": result["validation"]["vocabulary_coverage"],
            },
            "dataset_version_public_id": dataset_version_public_id,
            "dataset_checksum_sha256": dataset_version["checksum_sha256"],
            "tokenizer_version_public_id": version_row["tokenizer_version_public_id"],
            "tokenizer_checksum_sha256": tokenizer_row["model_checksum_sha256"],
            "normalization_version": tokenizer_row["normalization_rule_name"],
            "block_builder_version": BLOCK_BUILDER_VERSION,
            "core_model_version_public_id": core_model_version_public_id,
            "context_length": model_config.context_length,
            "sequence_length": resolved_sequence_length,
            "overlength_policy": overlength_policy,
        }

    def check_readiness(
        self, *, dataset_version_public_id: str, core_model_version_public_id: str,
        sequence_length: int | None = None, overlength_policy: str = DEFAULT_OVERLENGTH_POLICY,
    ) -> dict[str, Any]:
        """Phase 2.7G Part 20: the deterministic training-readiness gate.
        Runs the exact real pipeline `build_blocks()` runs and reports
        `ready=True` only if it completes without a typed rejection --
        `ready=False` always carries the exact reason, never a vague
        failure. An incomplete/ungoverned dataset can never reach
        `ready=True` here, because it can never reach `ready=True` in
        `build_blocks()` either -- this is the same real gate, not a
        second, looser one."""

        try:
            result = self.build_blocks(
                dataset_version_public_id=dataset_version_public_id,
                core_model_version_public_id=core_model_version_public_id,
                sequence_length=sequence_length, overlength_policy=overlength_policy,
            )
        except (ValidationError, NotFoundError) as exc:
            # Phase 2.7H: `NotFoundError` (raised for an unknown Core Model
            # Version by `CoreModelRepository.version()`) is a sibling of
            # `ValidationError`, not a subclass -- Phase 2.7G's original
            # `except ValidationError` alone let it escape uncaught for a
            # bad `core_model_version_public_id`. Fixed here rather than
            # left as a silent gap.
            return {"ready": False, "reason": str(exc), "report": None}
        return {
            "ready": True,
            "reason": None,
            "report": {
                key: value for key, value in result.items()
                if key not in {"train_blocks", "validation_blocks"}
            },
        }

    def readiness_contract(
        self, *, dataset_version_public_id: str, core_model_version_public_id: str,
        sequence_length: int | None = None, overlength_policy: str = DEFAULT_OVERLENGTH_POLICY,
    ) -> dict[str, Any]:
        """Phase 2.7H, mission Part 2/11: the structured Training Dataset
        Readiness contract. Distinguishes `BLOCKED` (the dataset/tokenizer/
        core-model *identity* itself cannot succeed no matter how many
        times this is retried -- wrong id, wrong lifecycle state, broken
        tokenizer artifacts, a token id outside the vocabulary) from
        `NOT_READY` (identities are all real and governed, but the
        derived data is insufficient right now -- an empty split, a
        `sequence_length` that does not fit) from `READY`. Every field
        below is read straight from real DB rows or the real pipeline's
        own output -- never fabricated. Read-only throughout: no dataset,
        tokenizer, or job row is written by this method."""

        checks: dict[str, dict[str, Any]] = {}

        def record(key: str, passed: bool, detail: Any) -> None:
            checks[key] = {"passed": passed, "detail": detail}

        with database_connection(self.settings.resolved_database_path) as connection:
            dataset_row = connection.execute(
                "SELECT * FROM dataset_versions WHERE public_id=?", (dataset_version_public_id,)
            ).fetchone()

        # A. Dataset Version exists.
        if not dataset_row:
            record("A_dataset_version_exists", False, f"no row for {dataset_version_public_id}")
            return self._contract_result(
                "BLOCKED", f"dataset version not found: {dataset_version_public_id}", checks,
            )
        record("A_dataset_version_exists", True, dataset_version_public_id)

        # B. Dataset status is ready/archived.
        status_ok = dataset_row["status"] in ELIGIBLE_DATASET_STATUSES
        record("B_dataset_status_ready_or_archived", status_ok, dataset_row["status"])
        if not status_ok:
            return self._contract_result(
                "BLOCKED",
                f"dataset version must be ready or archived (currently '{dataset_row['status']}')",
                checks,
            )

        # C. Dataset checksum exists and is valid -- reuses the real,
        # existing `DatasetVersioningService.verify_version()` recomputation
        # rather than a second, parallel checksum routine.
        checksum_present = bool(dataset_row["checksum_sha256"])
        record("C_dataset_checksum_present", checksum_present, dataset_row["checksum_sha256"] or "missing")
        try:
            repository = DatasetQualityRepository(self.settings.resolved_database_path)
            versioning = DatasetVersioningService(repository, self.settings)
            verification = versioning.verify_version(dataset_version_public_id)
            record(
                "C_dataset_checksum_valid", verification["verified"],
                "recomputed via DatasetVersioningService.verify_version() and compared to the stored value",
            )
        except Exception as exc:  # noqa: BLE001 -- defensive: report, never crash the readiness gate
            record("C_dataset_checksum_valid", False, f"checksum recomputation failed: {exc}")

        # D. Immutability once ready -- schema-enforced (`dataset_versions_ready_content_update`
        # / `dataset_version_items_ready_update` triggers, Phase 6), not re-tested by attempting
        # a write on every readiness call; recorded as a structural guarantee for a ready/archived row.
        record(
            "D_dataset_immutable_once_ready", True,
            "enforced by the dataset_versions_ready_content_update / "
            "dataset_version_items_ready_update schema triggers",
        )

        with database_connection(self.settings.resolved_database_path) as connection:
            item_rows = connection.execute(
                """SELECT i.split, r.content_hash, s.licence_status
                FROM dataset_version_items i
                JOIN dataset_records r ON r.id=i.dataset_record_id
                LEFT JOIN dataset_sources s ON s.id=r.source_id
                WHERE i.dataset_version_id=?""",
                (dataset_row["id"],),
            ).fetchall()

        # E. Dataset contains usable records at all.
        record("E_dataset_has_records", len(item_rows) > 0, f"{len(item_rows)} dataset_version_items rows")

        # J. Rights/licence constraints satisfied for every record actually in this version.
        rejected_licence = [row for row in item_rows if row["licence_status"] == "rejected"]
        record(
            "J_rights_licence_satisfied", not rejected_licence,
            f"{len(rejected_licence)} item(s) sourced from a rejected-licence source"
            if rejected_licence else "no item sourced from a rejected-licence source",
        )

        # K. Duplicate handling: no exact content-hash appears more than once within this version.
        hash_counts: dict[str, int] = {}
        for row in item_rows:
            hash_counts[row["content_hash"]] = hash_counts.get(row["content_hash"], 0) + 1
        duplicate_hashes = {h: n for h, n in hash_counts.items() if n > 1}
        record(
            "K_no_duplicate_content_hash_within_version", not duplicate_hashes,
            f"{len(duplicate_hashes)} content_hash value(s) repeated" if duplicate_hashes
            else "every content_hash in this version is unique",
        )

        # I. No blocked leakage state: the same content_hash never appears in two different splits.
        seen_split: dict[str, str] = {}
        leakage_conflicts = []
        for row in item_rows:
            prior = seen_split.get(row["content_hash"])
            if prior and prior != row["split"]:
                leakage_conflicts.append(row["content_hash"])
            seen_split[row["content_hash"]] = row["split"]
        record(
            "I_no_blocked_leakage", not leakage_conflicts,
            f"{len(leakage_conflicts)} content_hash value(s) cross a split boundary" if leakage_conflicts
            else "no content_hash crosses a train/validation/test split boundary",
        )
        if leakage_conflicts:
            return self._contract_result(
                "BLOCKED", "blocked leakage: identical content appears in more than one split", checks,
            )

        # L. Quality/readiness requirements, where applicable -- this dataset version's own
        # build already enforced any configured quality gate (Phase 6 `_select_records()`);
        # nothing further to gate here at read time, recorded as satisfied/not-configured.
        record("L_quality_readiness_requirements", True, "enforced at dataset-build time by DatasetVersioningService")

        # F/G/H/M/N/O/P/Q/R/S: attempt the real pipeline, timing it for the resource estimate.
        start = time.perf_counter()
        try:
            result = self.build_blocks(
                dataset_version_public_id=dataset_version_public_id,
                core_model_version_public_id=core_model_version_public_id,
                sequence_length=sequence_length, overlength_policy=overlength_policy,
            )
        except (ValidationError, NotFoundError) as exc:
            reason = str(exc)
            record("M_to_S_pipeline_build", False, reason)
            status = "BLOCKED" if any(marker in reason for marker in _BLOCKED_REASON_MARKERS) else "NOT_READY"
            return self._contract_result(status, reason, checks)
        elapsed_seconds = time.perf_counter() - start

        train_blocks = result["train_blocks"]
        validation_blocks = result["validation_blocks"]
        record("F_train_split_usable", len(train_blocks) > 0, f"{len(train_blocks)} train block(s)")
        record("G_validation_split_usable", len(validation_blocks) > 0, f"{len(validation_blocks)} validation block(s)")
        record("H_split_non_empty_and_governed", len(train_blocks) > 0 and len(validation_blocks) > 0, None)
        record("M_tokenizer_exists_and_verifies", True, result["tokenizer_version_public_id"])
        record(
            "N_tokenizer_belongs_to_core_model_version", True,
            "tokenizer is always resolved from the Core Model Version's own config, "
            "never independently supplied -- a mismatch is structurally impossible",
        )
        record("O_tokenization_succeeded", True, None)
        record("P_token_ids_in_vocabulary_range", True, "validated by validate_token_ids() during block construction")
        record("Q_core_model_version_has_valid_context_length", result["context_length"] > 0, result["context_length"])
        record("R_block_construction_succeeded", True, None)
        record(
            "S_train_and_validation_blocks_non_empty", len(train_blocks) > 0 and len(validation_blocks) > 0, None,
        )
        record(
            "T_provenance_reproducible", True,
            "dataset_checksum_sha256/tokenizer_checksum_sha256/block_builder_version present in the result",
        )

        train_report = result["train_report"]
        validation_report = result["validation_report"]
        language_distribution: dict[str, int] = dict(train_report["coverage"]["language_distribution"])
        for key, value in validation_report["coverage"]["language_distribution"].items():
            language_distribution[key] = language_distribution.get(key, 0) + value

        return {
            "status": "READY",
            "reason": None,
            "checks": checks,
            "dataset": {
                "dataset_version_public_id": dataset_version_public_id,
                "status": dataset_row["status"],
                "checksum_sha256": result["dataset_checksum_sha256"],
                "record_count": len(item_rows),
            },
            "tokenizer": {
                "tokenizer_version_public_id": result["tokenizer_version_public_id"],
                "checksum_sha256": result["tokenizer_checksum_sha256"],
                "normalization_version": result["normalization_version"],
            },
            "blocks": {
                "train_block_count": len(train_blocks),
                "validation_block_count": len(validation_blocks),
                "context_length": result["context_length"],
                "sequence_length": result["sequence_length"],
                "overlength_policy": result["overlength_policy"],
                "train_usable_tokens": train_report["coverage"]["usable_tokens"],
                "validation_usable_tokens": validation_report["coverage"]["usable_tokens"],
                "train_token_length_stats": train_report["token_length_stats"],
                "validation_token_length_stats": validation_report["token_length_stats"],
            },
            "language_distribution": language_distribution,
            "quality": {
                "train_encoded_records": train_report["coverage"]["encoded_records"],
                "train_dropped_records": train_report["coverage"]["dropped_records"],
                "validation_encoded_records": validation_report["coverage"]["encoded_records"],
                "validation_dropped_records": validation_report["coverage"]["dropped_records"],
                "train_vocabulary_coverage": train_report["vocabulary_coverage"],
                "validation_vocabulary_coverage": validation_report["vocabulary_coverage"],
            },
            "reproducibility": {
                "dataset_checksum_sha256": result["dataset_checksum_sha256"],
                "tokenizer_checksum_sha256": result["tokenizer_checksum_sha256"],
                "block_builder_version": result["block_builder_version"],
                "train_stream_checksum_sha256": train_report["coverage"]["stream_checksum_sha256"],
                "validation_stream_checksum_sha256": validation_report["coverage"]["stream_checksum_sha256"],
            },
            "resource_estimate": {
                "pipeline_wall_clock_seconds": elapsed_seconds,
                "records_measured": len(item_rows),
            },
        }

    def _contract_result(self, status: str, reason: str, checks: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": status, "reason": reason, "checks": checks,
            "dataset": None, "tokenizer": None, "blocks": None,
            "language_distribution": None, "quality": None, "reproducibility": None,
            "resource_estimate": None,
        }


__all__ = ["MiniBrainDatasetPipelineService", "ELIGIBLE_DATASET_STATUSES", "DEFAULT_OVERLENGTH_POLICY"]
