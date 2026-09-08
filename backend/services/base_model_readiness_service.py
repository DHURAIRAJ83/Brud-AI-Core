"""Phase 21A base-model pretraining-readiness gate: aggregates real
signals already computed by every earlier Phase 21A step (tokenizer
corpus sufficiency, candidate evaluation, activation, dataset
snapshot, resource estimate, smoke run) plus a live re-verification of
the corpus release manifest, tokenizer artifact, and checkpoint --
never fabricates a dimension result, and never upgrades a warning to
a pass."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.pretraining_readiness import (
    PretrainingReadinessRepository,
    public_row,
)
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.pretraining_readiness import BaseModelReadinessEvaluationCreate
from backend.services.pretraining_service import PretrainingService
from backend.services.tokenizer_registry import TokenizerService
from core_model.corpus.manifest import verify_manifest_checksum
from core_model.pretraining_readiness.readiness import READINESS_DIMENSIONS, overall_readiness


class BaseModelReadinessService:
    def __init__(
        self,
        readiness_repository: PretrainingReadinessRepository,
        corpus_repository: CorpusRepository,
        pretraining_repository: PretrainingRepository,
        settings: Settings,
    ) -> None:
        self.readiness_repository = readiness_repository
        self.corpus_repository = corpus_repository
        self.settings = settings
        self.tokenizer_service = TokenizerService(
            TokenizerRepository(settings.resolved_database_path), settings
        )
        self.pretraining_service = PretrainingService(pretraining_repository, settings)

    def evaluate(
        self, payload: BaseModelReadinessEvaluationCreate, admin_id: str
    ) -> dict[str, Any]:
        # Phase 7C-44: opens with immediate=True. This block reads up to 4
        # rows (snapshot/comparison/estimate/smoke_run) before its own
        # writes (create_base_model_readiness_evaluation,
        # update_base_model_readiness_evaluation) -- a READ-THEN-WRITE
        # shape. Phase 7C-36/37 established this shape suffers severe
        # deferred-BEGIN lock-upgrade contention once pooled; Phase 7C-43's
        # own real Barrier-synchronized qualification of this exact block
        # additionally found the contention is severe (44-57%) even
        # unpooled under concurrent load, unlike every previously-qualified
        # shape -- immediate=True eliminated it completely (0%) in both
        # pooled and unpooled configurations across every trial.
        with self.readiness_repository.transaction(immediate=True) as connection:
            snapshot = self.readiness_repository.pretraining_dataset_snapshot(
                connection, payload.pretraining_dataset_snapshot_public_id
            )
            comparison = None
            if payload.tokenizer_candidate_comparison_public_id:
                comparison = self.readiness_repository.tokenizer_candidate_comparison(
                    connection, payload.tokenizer_candidate_comparison_public_id
                )
            estimate = None
            if payload.base_model_resource_estimate_public_id:
                estimate = self.readiness_repository.base_model_resource_estimate(
                    connection, payload.base_model_resource_estimate_public_id
                )
            smoke_run = None
            if payload.pretraining_smoke_run_public_id:
                smoke_run = self.readiness_repository.pretraining_smoke_run(
                    connection, payload.pretraining_smoke_run_public_id
                )

            evaluation_public_id = self.readiness_repository.create_base_model_readiness_evaluation(
                connection,
                {
                    "pretraining_dataset_snapshot_id": snapshot["id"],
                    "tokenizer_candidate_comparison_id": comparison["id"] if comparison else None,
                    "base_model_resource_estimate_id": estimate["id"] if estimate else None,
                    "pretraining_smoke_run_id": smoke_run["id"] if smoke_run else None,
                    "created_by_admin_public_id": admin_id,
                },
            )
            evaluation_row = self.readiness_repository.base_model_readiness_evaluation(
                connection, evaluation_public_id
            )
            self.readiness_repository.update_base_model_readiness_evaluation(
                connection, evaluation_row["id"], {"status": "running"}
            )
            release_row = connection.execute(
                "SELECT * FROM corpus_releases WHERE id=?", (snapshot["corpus_release_id"],)
            ).fetchone()
            tokenizer_row = connection.execute(
                "SELECT * FROM tokenizer_versions WHERE id=?", (snapshot["tokenizer_version_id"],)
            ).fetchone()

        results: dict[str, str] = dict.fromkeys(READINESS_DIMENSIONS, "not_evaluated")
        hard_failure_reasons: list[str] = []

        # --- tokenizer dimensions -----------------------------------------------------
        recommended_evaluation = None
        if comparison is not None:
            with self.readiness_repository.transaction() as connection:
                evaluations = self.readiness_repository.evaluations_for_comparison(
                    connection, comparison["id"]
                )
            for row in evaluations:
                if row["tokenizer_version_id"] == snapshot["tokenizer_version_id"]:
                    recommended_evaluation = row
                    break
        if recommended_evaluation is not None:
            status_map = {
                "rejected": "fail", "experimental": "warning",
                "recommended": "pass", "production_candidate": "pass",
            }
            results["tokenizer_quality"] = status_map.get(
                recommended_evaluation["final_status"], "not_evaluated"
            )
            if results["tokenizer_quality"] == "fail":
                hard_failure_reasons.append("tokenizer_quality_rejected")

        with self.readiness_repository.transaction() as connection:
            # Joined on `corpus_release_id`, not `dataset_version_id`: the
            # tokenizer corpus build and the pretraining snapshot each
            # materialize their *own* dataset_version row from the same
            # corpus release, so they never share a dataset_version_id.
            build_row = connection.execute(
                "SELECT sufficiency_state FROM tokenizer_corpus_builds "
                "WHERE corpus_release_id=? ORDER BY id DESC LIMIT 1",
                (snapshot["corpus_release_id"],),
            ).fetchone()
        if build_row is not None:
            results["tokenizer_corpus_sufficiency"] = {
                "insufficient": "fail", "experimental": "warning",
                "candidate": "pass", "production_candidate": "pass",
            }.get(build_row["sufficiency_state"], "not_evaluated")

        try:
            self.tokenizer_service.processor_for_version(tokenizer_row["public_id"])
            results["tokenizer_artifact_integrity"] = "pass"
        except Exception:  # noqa: BLE001
            results["tokenizer_artifact_integrity"] = "fail"
            hard_failure_reasons.append("tokenizer_artifact_verification_failed")

        results["tokenizer_activation"] = {
            "active": "pass", "staging": "warning", "retired": "warning", "archived": "warning",
        }.get(tokenizer_row["lifecycle_status"], "fail")

        # --- corpus/dataset dimensions -----------------------------------------------------
        with self.corpus_repository.transaction() as connection:
            manifest_row = connection.execute(
                """SELECT manifest_json, manifest_checksum_sha256 FROM corpus_manifests
                WHERE corpus_version_id=? ORDER BY id DESC LIMIT 1""",
                (release_row["corpus_version_id"],),
            ).fetchone()
        if release_row["status"] not in ("finalized", "exported"):
            results["corpus_release_integrity"] = "fail"
            hard_failure_reasons.append("corpus_release_not_finalized")
        elif manifest_row is not None and verify_manifest_checksum(
            manifest_row["manifest_json"], manifest_row["manifest_checksum_sha256"]
        ):
            results["corpus_release_integrity"] = "pass"
        else:
            results["corpus_release_integrity"] = "fail"
            hard_failure_reasons.append("corpus_manifest_verification_failed")

        snapshot_manifest_current = (
            manifest_row is not None
            and snapshot["manifest_checksum_sha256"] == manifest_row["manifest_checksum_sha256"]
        )
        snapshot_tokenizer_current = (
            snapshot["tokenizer_checksum_sha256"] == tokenizer_row["model_checksum_sha256"]
        )
        results["dataset_snapshot_integrity"] = (
            "pass" if snapshot_manifest_current and snapshot_tokenizer_current else "fail"
        )
        if results["dataset_snapshot_integrity"] == "fail":
            hard_failure_reasons.append("dataset_snapshot_reference_mismatch")

        results["partition_isolation"] = (
            "pass"
            if snapshot["train_record_count"] > 0
            and snapshot["validation_record_count"] > 0
            and snapshot["test_record_count"] > 0
            else "fail"
        )
        if results["partition_isolation"] == "fail":
            hard_failure_reasons.append("dataset_snapshot_split_incomplete")

        results["tokenization_statistics"] = (
            "pass"
            if snapshot["train_token_count"] > 0 and snapshot["validation_token_count"] > 0
            else "warning"
        )

        # --- model/training dimensions -----------------------------------------------------
        if estimate is not None:
            results["model_configuration_safety"] = (
                "pass" if estimate["within_safe_limit"] else "fail"
            )
            if not estimate["within_safe_limit"]:
                hard_failure_reasons.append("model_resource_estimate_unsafe")

        if smoke_run is not None:
            findings = loads_json(smoke_run["degeneration_findings_json"], default=[])
            results["data_loader_reliability"] = (
                "pass"
                if smoke_run["status"] in ("completed", "completed_with_warnings")
                else "fail"
            )
            results["training_configuration_validity"] = (
                "pass" if smoke_run["status"] != "failed" else "fail"
            )
            loss_finite = (
                smoke_run["initial_training_loss"] is not None
                and smoke_run["final_training_loss"] is not None
            )
            results["forward_backward_stability"] = (
                "pass" if loss_finite and not findings else ("fail" if findings else "warning")
            )
            if findings:
                hard_failure_reasons.append("smoke_run_degeneration_detected")

            if smoke_run["checkpoint_public_id"]:
                verify_result = self.pretraining_service.verify_checkpoint(
                    smoke_run["checkpoint_public_id"], admin_id
                )
                results["checkpoint_integrity"] = (
                    "pass" if verify_result["verified"] else "fail"
                )
                if not verify_result["verified"]:
                    hard_failure_reasons.append("smoke_checkpoint_verification_failed")
            else:
                results["checkpoint_integrity"] = "fail"
                hard_failure_reasons.append("smoke_checkpoint_missing")

            results["resume_integrity"] = "pass" if smoke_run["resume_verified"] else "fail"
            if not smoke_run["resume_verified"]:
                hard_failure_reasons.append("smoke_resume_not_verified")

            results["validation_execution"] = (
                "pass" if smoke_run["validation_loss"] is not None else "warning"
            )

            if estimate is not None and smoke_run["peak_process_memory_bytes"]:
                results["resource_safety"] = (
                    "pass"
                    if smoke_run["peak_process_memory_bytes"] <= estimate["safe_ram_ceiling_bytes"]
                    else "fail"
                )
                if results["resource_safety"] == "fail":
                    hard_failure_reasons.append("observed_memory_exceeded_safe_ceiling")

        with self.corpus_repository.transaction() as connection:
            audit_count = connection.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE resource_public_id IN (?,?,?,?)",
                (
                    payload.pretraining_dataset_snapshot_public_id,
                    payload.tokenizer_candidate_comparison_public_id or "",
                    payload.base_model_resource_estimate_public_id or "",
                    payload.pretraining_smoke_run_public_id or "",
                ),
            ).fetchone()[0]
        results["audit_completeness"] = "pass" if audit_count > 0 else "warning"

        overall = overall_readiness(results)
        with self.readiness_repository.transaction() as connection:
            for dimension, status in results.items():
                self.readiness_repository.record_base_model_readiness_dimension(
                    connection,
                    {
                        "evaluation_id": evaluation_row["id"], "dimension": dimension,
                        "status": status, "details_json": "{}",
                    },
                )
            self.readiness_repository.update_base_model_readiness_evaluation(
                connection,
                evaluation_row["id"],
                {
                    "status": "completed", "overall_result": overall,
                    "hard_failure_reasons_json": dumps_json(sorted(set(hard_failure_reasons))),
                },
            )
            self._audit(
                connection, "base_model_readiness_evaluated", admin_id, evaluation_public_id,
                overall_result=overall,
            )
            return self._detail(connection, evaluation_public_id)

    def _detail(self, connection, public_id: str) -> dict[str, Any]:
        row = self.readiness_repository.base_model_readiness_evaluation(connection, public_id)
        result = public_row(row)
        result["dimensions"] = [
            public_row(dim)
            for dim in self.readiness_repository.dimensions_for_evaluation(connection, row["id"])
        ]
        return result

    def get_evaluation(self, public_id: str) -> dict[str, Any]:
        with self.readiness_repository.transaction() as connection:
            return self._detail(connection, public_id)

    def list_evaluations(self) -> dict[str, Any]:
        with self.readiness_repository.transaction() as connection:
            return {
                "items": [
                    public_row(row)
                    for row in self.readiness_repository.list_base_model_readiness_evaluations(
                        connection
                    )
                ]
            }

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "pretraining_readiness", resource_id, "success", dumps_json(metadata),
            ),
        )
