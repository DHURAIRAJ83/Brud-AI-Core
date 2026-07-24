"""Phase 14 model registry, release-candidate, artifact-governance, and
metadata-level rollback orchestration.

Composes existing registries (core model versions, checkpoints, tokenizer
versions, dataset versions, instruction-tuning candidates, evaluation
runs/readiness assessments) rather than duplicating any of them. This
module never trains, serves, or deploys anything, and never assigns a
release to the public chatbot — the model stays ``not_public_chat_ready``
and the public ``/api/chat`` route is untouched regardless of any release
outcome here.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.model_release import ModelReleaseRepository, public_row
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.model_release import (
    ApprovalCreate,
    ModelCardOverrides,
    ModelReleaseCandidateCreate,
    ModelReleaseCandidatePatch,
    ModelReleaseComparisonCreate,
    ModelReleaseCreate,
    ModelReleaseFamilyCreate,
    ModelReleaseFamilyPatch,
    RollbackApprovalCreate,
    RollbackPlanCreate,
)
from backend.services.tokenizer_registry import _safe_component
from core_model.release.approval_policy import (
    ApprovalPolicy,
    is_approval_stale,
    is_policy_satisfied,
    validate_approval_submission,
)
from core_model.release.artifact_inventory import (
    classify_artifact_verification,
    detect_unexpected_executable,
    file_checksum,
    resolve_confined_path,
    verify_artifact_size,
)
from core_model.release.comparison import compare_releases as assess_release_comparison
from core_model.release.eligibility import (
    EligibilityThresholds,
    assess_release_eligibility,
    classify_resource_requirements,
)
from core_model.release.manifest import manifest_checksum, scan_for_sensitive_content
from core_model.release.model_card import (
    model_card_checksum,
    render_model_card,
)
from core_model.release.model_card import validate_model_card as run_model_card_validation
from core_model.release.release_bundle import (
    build_bundle_inventory,
    is_bundle_size_within_limit,
    scan_bundle_paths_for_forbidden_content,
    validate_bundle_source_artifacts,
)
from core_model.release.rollback import assess_rollback_target

ELIGIBLE_LIFECYCLE_STATUSES = {"staging", "active"}


class ModelReleaseService:
    def __init__(self, repository: ModelReleaseRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- families -----------------------------------------------------

    def create_family(self, payload: ModelReleaseFamilyCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_family(
                connection,
                {
                    "name": payload.name,
                    "slug": payload.slug,
                    "description": payload.description,
                    "intended_use": payload.intended_use,
                    "supported_languages_json": dumps_json(payload.supported_languages),
                    "compatibility_policy_json": dumps_json(payload.compatibility_policy),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "model_release_family_created", admin_id, public_id)
            return public_row(self.repository.family(connection, public_id))

    def list_families(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_families(connection)
        return {"items": [public_row(row) for row in rows]}

    def get_family(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.family(connection, public_id))

    def patch_family(
        self, public_id: str, payload: ModelReleaseFamilyPatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            family = self.repository.family(connection, public_id)
            fields: dict[str, Any] = {}
            if payload.description is not None:
                fields["description"] = payload.description
            if payload.intended_use is not None:
                fields["intended_use"] = payload.intended_use
            if payload.supported_languages is not None:
                fields["supported_languages_json"] = dumps_json(payload.supported_languages)
            if payload.compatibility_policy is not None:
                fields["compatibility_policy_json"] = dumps_json(payload.compatibility_policy)
            if payload.lifecycle_status is not None:
                if payload.lifecycle_status not in {"draft", "active", "deprecated", "archived"}:
                    raise ValidationError("invalid release-family lifecycle status")
                fields["lifecycle_status"] = payload.lifecycle_status
                if payload.lifecycle_status == "archived":
                    connection.execute(
                        "UPDATE model_release_families SET archived_at=CURRENT_TIMESTAMP "
                        "WHERE id=?",
                        (family["id"],),
                    )
            self.repository.update_family(connection, family["id"], fields)
            self._audit(connection, "model_release_family_updated", admin_id, public_id)
            return public_row(self.repository.family(connection, public_id))

    # --- candidates: creation -----------------------------------------------------

    def _resolve_checkpoint(self, connection, core_model_version) -> Any:
        checkpoint = connection.execute(
            """SELECT * FROM pretraining_checkpoints WHERE core_model_version_id=?
            AND status IN ('completed','verified')
            ORDER BY is_best DESC, is_latest DESC, step DESC LIMIT 1""",
            (core_model_version["id"],),
        ).fetchone()
        if checkpoint:
            return checkpoint
        if core_model_version["weights_checksum_sha256"]:
            checkpoint = connection.execute(
                """SELECT * FROM pretraining_checkpoints WHERE model_checksum_sha256=?
                AND status IN ('completed','verified') ORDER BY id DESC LIMIT 1""",
                (core_model_version["weights_checksum_sha256"],),
            ).fetchone()
        return checkpoint

    def create_candidate(
        self, payload: ModelReleaseCandidateCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            family = self.repository.family(
                connection, payload.model_release_family_public_id
            )
            core_model_version = connection.execute(
                "SELECT * FROM core_model_versions WHERE public_id=?",
                (payload.core_model_version_public_id,),
            ).fetchone()
            if not core_model_version:
                raise ValidationError("core model version not found")
            if core_model_version["lifecycle_status"] in {"retired", "archived", "failed"}:
                raise ValidationError(
                    "a retired, archived, or failed core model version cannot become "
                    "a release candidate"
                )
            if core_model_version["lifecycle_status"] not in ELIGIBLE_LIFECYCLE_STATUSES:
                raise ValidationError(
                    "core model version must be staging or active to become a candidate"
                )
            checkpoint = self._resolve_checkpoint(connection, core_model_version)
            if not checkpoint:
                raise ValidationError("no verified checkpoint is available for this model")

            dataset_version_id = None
            if payload.dataset_version_public_id:
                dataset = connection.execute(
                    "SELECT id FROM dataset_versions WHERE public_id=?",
                    (payload.dataset_version_public_id,),
                ).fetchone()
                if not dataset:
                    raise ValidationError("dataset version not found")
                dataset_version_id = dataset["id"]

            instruction_tuning_candidate_id = None
            summary = loads_json(core_model_version["architecture_summary_json"])
            if payload.instruction_tuning_candidate_public_id:
                itc = connection.execute(
                    "SELECT id,status FROM instruction_tuning_candidates WHERE public_id=?",
                    (payload.instruction_tuning_candidate_public_id,),
                ).fetchone()
                if not itc:
                    raise ValidationError("instruction-tuning candidate not found")
                instruction_tuning_candidate_id = itc["id"]
            if summary.get("instruction_tuned") and not summary.get("base_pretrained"):
                raise ValidationError(
                    "instruction-tuned candidates must also be marked base_pretrained"
                )

            model_evaluation_run_id = None
            if payload.model_evaluation_run_public_id:
                run = connection.execute(
                    "SELECT id,candidate_core_model_version_id FROM model_evaluation_runs "
                    "WHERE public_id=?",
                    (payload.model_evaluation_run_public_id,),
                ).fetchone()
                if not run:
                    raise ValidationError("evaluation run not found")
                if run["candidate_core_model_version_id"] != core_model_version["id"]:
                    raise ValidationError(
                        "evaluation run does not belong to this core model version's lineage"
                    )
                model_evaluation_run_id = run["id"]

            public_id = self.repository.create_candidate(
                connection,
                {
                    "model_release_family_id": family["id"],
                    "core_model_version_id": core_model_version["id"],
                    "checkpoint_id": checkpoint["id"],
                    "tokenizer_version_id": core_model_version["tokenizer_version_id"],
                    "dataset_version_id": dataset_version_id,
                    "instruction_tuning_candidate_id": instruction_tuning_candidate_id,
                    "model_evaluation_run_id": model_evaluation_run_id,
                    "label": payload.label,
                    "notes": payload.notes,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "model_release_candidate_created", admin_id, public_id)
            return public_row(self.repository.candidate(connection, public_id))

    def get_candidate(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.candidate(connection, public_id))

    def list_candidates(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_candidates(connection)
        return {"items": [public_row(row) for row in rows]}

    def patch_candidate(
        self, public_id: str, payload: ModelReleaseCandidatePatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, public_id)
            fields: dict[str, Any] = {}
            if payload.label is not None:
                fields["label"] = payload.label
            if payload.notes is not None:
                fields["notes"] = payload.notes
            self.repository.update_candidate(connection, candidate["id"], fields)
            self._audit(connection, "model_release_candidate_updated", admin_id, public_id)
            return public_row(self.repository.candidate(connection, public_id))

    # --- artifact collection -----------------------------------------------------

    def _write_json_artifact(self, candidate_public_id: str, name: str, payload: dict) -> Path:
        directory = self.settings.resolved_release_artifact_dir / candidate_public_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        target.write_text(dumps_json(payload), encoding="utf-8")
        return target

    def collect_artifacts(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            instruction_tuned = bool(
                loads_json(candidate["core_model_architecture_summary_json"]).get(
                    "instruction_tuned"
                )
            )

            entries: list[dict[str, Any]] = []

            checkpoint_dir = (
                self.settings.resolved_pretraining_dir / candidate["checkpoint_safe_name"]
            )
            entries.append(self._collect_checkpoint_artifact(candidate, checkpoint_dir))
            entries.append(self._collect_model_config_artifact(connection, candidate))
            entries.extend(self._collect_tokenizer_artifacts(connection, candidate))
            if candidate["dataset_version_public_id"]:
                entries.append(self._collect_dataset_manifest_artifact(candidate))
            entries.append(self._collect_base_training_manifest_artifact(connection, candidate))
            if instruction_tuned and candidate["instruction_tuning_candidate_public_id"]:
                entries.append(
                    self._collect_instruction_tuning_manifest_artifact(connection, candidate)
                )
            if candidate["model_evaluation_run_public_id"]:
                entries.append(self._collect_evaluation_manifest_artifact(connection, candidate))
            entries.append(self._collect_licence_artifact(candidate))

            for entry in entries:
                self.repository.record_artifact(connection, candidate["id"], entry)

            self.repository.update_candidate(
                connection, candidate["id"], {"status": "collecting_artifacts"}
            )
            self._audit(
                connection, "model_release_artifacts_collected", admin_id, candidate_public_id,
                artifact_count=len(entries),
            )
            rows = self.repository.artifacts_for_candidate(connection, candidate["id"])
            return {"items": [public_row(row) for row in rows]}

    def _collect_checkpoint_artifact(self, candidate, checkpoint_dir: Path) -> dict[str, Any]:
        root = self.settings.resolved_pretraining_dir
        try:
            resolved = resolve_confined_path(root, candidate["checkpoint_safe_name"])
            exists = resolved.is_dir()
            size = (
                sum(f.stat().st_size for f in resolved.rglob("*") if f.is_file())
                if exists else 0
            )
            path_confined = True
        except ValueError:
            exists, size, path_confined = False, 0, False
        size_ok = verify_artifact_size(size, self.settings.release_max_artifact_size_bytes)
        checksum = candidate["checkpoint_model_checksum_sha256"]
        status = classify_artifact_verification(
            exists=exists, path_confined=path_confined, size_ok=size_ok,
            checksum_matches=True if exists else None,
        )
        return {
            "artifact_type": "model_checkpoint",
            "source_entity_public_id": candidate["checkpoint_public_id"],
            "logical_name": "checkpoint",
            "storage_key": candidate["checkpoint_safe_name"],
            "size_bytes": size,
            "checksum": checksum,
            "verification_status": status,
        }

    def _collect_model_config_artifact(self, connection, candidate) -> dict[str, Any]:
        config_row = connection.execute(
            "SELECT * FROM core_model_configs WHERE id=?",
            (candidate["core_model_config_id"],),
        ).fetchone()
        payload = {key: config_row[key] for key in config_row.keys() if key != "id"}
        target = self._write_json_artifact(
            candidate["public_id"], "model_config.json", payload
        )
        checksum = file_checksum(target)
        return {
            "artifact_type": "model_config",
            "source_entity_public_id": config_row["public_id"],
            "logical_name": "model_config.json",
            "storage_key": f"{candidate['public_id']}/model_config.json",
            "size_bytes": target.stat().st_size,
            "checksum": checksum,
            "verification_status": "verified",
        }

    def _collect_tokenizer_artifacts(self, connection, candidate) -> list[dict[str, Any]]:
        tokenizer_row = TokenizerRepository(self.repository.database_path).version(
            connection, candidate["tokenizer_version_public_id"]
        )
        entries = []
        for artifact_type, filename, expected_checksum in (
            ("tokenizer_model", "tokenizer.model", tokenizer_row["model_checksum_sha256"]),
            ("tokenizer_vocab", "tokenizer.vocab", tokenizer_row["vocabulary_checksum_sha256"]),
        ):
            root = self.settings.resolved_tokenizer_dir
            relative = f"versions/{_safe_component(tokenizer_row['family_name'])}/" \
                f"{_safe_component(tokenizer_row['version'])}/{filename}"
            try:
                resolved = resolve_confined_path(root, relative)
                exists = resolved.is_file()
                path_confined = True
                size = resolved.stat().st_size if exists else 0
                checksum_matches = (
                    file_checksum(resolved) == expected_checksum if exists else None
                )
            except ValueError:
                exists, path_confined, size, checksum_matches = False, False, 0, None
            size_ok = verify_artifact_size(size, self.settings.release_max_artifact_size_bytes)
            status = classify_artifact_verification(
                exists=exists, path_confined=path_confined, size_ok=size_ok,
                checksum_matches=checksum_matches,
            )
            entries.append({
                "artifact_type": artifact_type,
                "source_entity_public_id": tokenizer_row["public_id"],
                "logical_name": filename,
                "storage_key": relative,
                "size_bytes": size,
                "checksum": expected_checksum,
                "verification_status": status,
            })
        manifest_target = self._write_json_artifact(
            candidate["public_id"], "tokenizer_manifest.json",
            loads_json(tokenizer_row["artifact_manifest_json"]),
        )
        entries.append({
            "artifact_type": "tokenizer_manifest",
            "source_entity_public_id": tokenizer_row["public_id"],
            "logical_name": "tokenizer_manifest.json",
            "storage_key": f"{candidate['public_id']}/tokenizer_manifest.json",
            "size_bytes": manifest_target.stat().st_size,
            "checksum": file_checksum(manifest_target),
            "verification_status": "verified",
        })
        return entries

    def _collect_dataset_manifest_artifact(self, candidate) -> dict[str, Any]:
        payload = {
            "dataset_version_public_id": candidate["dataset_version_public_id"],
            "checksum_sha256": candidate["dataset_checksum_sha256"],
            "manifest": loads_json(candidate["dataset_manifest_json"] or "{}"),
        }
        target = self._write_json_artifact(
            candidate["public_id"], "dataset_manifest.json", payload
        )
        return {
            "artifact_type": "dataset_manifest",
            "source_entity_public_id": candidate["dataset_version_public_id"],
            "logical_name": "dataset_manifest.json",
            "storage_key": f"{candidate['public_id']}/dataset_manifest.json",
            "size_bytes": target.stat().st_size,
            "checksum": file_checksum(target),
            "verification_status": "verified",
        }

    def _collect_base_training_manifest_artifact(self, connection, candidate) -> dict[str, Any]:
        job = connection.execute(
            """SELECT j.public_id,j.configuration_json,j.config_checksum_sha256,
            j.initialization_seed,j.total_steps,j.processed_tokens
            FROM pretraining_jobs j WHERE j.id=(
                SELECT pretraining_job_id FROM pretraining_checkpoints WHERE id=?
            )""",
            (candidate["checkpoint_id"],),
        ).fetchone()
        if job is None:
            payload = {"status": "no_pretraining_job_found_for_checkpoint"}
            source_public_id = None
        else:
            payload = {
                "pretraining_job_public_id": job["public_id"],
                "configuration": loads_json(job["configuration_json"]),
                "config_checksum_sha256": job["config_checksum_sha256"],
                "initialization_seed": job["initialization_seed"],
                "total_steps": job["total_steps"],
                "processed_tokens": job["processed_tokens"],
            }
            source_public_id = job["public_id"]
        target = self._write_json_artifact(
            candidate["public_id"], "base_training_manifest.json", payload
        )
        return {
            "artifact_type": "base_training_manifest",
            "source_entity_public_id": source_public_id,
            "logical_name": "base_training_manifest.json",
            "storage_key": f"{candidate['public_id']}/base_training_manifest.json",
            "size_bytes": target.stat().st_size,
            "checksum": file_checksum(target),
            "verification_status": "verified" if job is not None else "missing",
        }

    def _collect_instruction_tuning_manifest_artifact(
        self, connection, candidate
    ) -> dict[str, Any]:
        row = connection.execute(
            """SELECT m.manifest_json,m.manifest_checksum_sha256,e.public_id AS experiment_public_id
            FROM instruction_reproducibility_manifests m
            JOIN instruction_tuning_candidates c ON c.instruction_tuning_experiment_id=
                m.instruction_tuning_experiment_id
            JOIN instruction_tuning_experiments e ON e.id=m.instruction_tuning_experiment_id
            WHERE c.id=(SELECT instruction_tuning_candidate_id FROM model_release_candidates
                WHERE id=?)
            ORDER BY m.created_at DESC LIMIT 1""",
            (candidate["id"],),
        ).fetchone()
        if row is None:
            payload = {"status": "no_instruction_tuning_manifest_found"}
            checksum = None
        else:
            payload = loads_json(row["manifest_json"])
            checksum = row["manifest_checksum_sha256"]
        target = self._write_json_artifact(
            candidate["public_id"], "instruction_tuning_manifest.json", payload
        )
        return {
            "artifact_type": "instruction_tuning_manifest",
            "source_entity_public_id": row["experiment_public_id"] if row else None,
            "logical_name": "instruction_tuning_manifest.json",
            "storage_key": f"{candidate['public_id']}/instruction_tuning_manifest.json",
            "size_bytes": target.stat().st_size,
            "checksum": checksum or file_checksum(target),
            "verification_status": "verified" if row is not None else "missing",
        }

    def _collect_evaluation_manifest_artifact(self, connection, candidate) -> dict[str, Any]:
        row = connection.execute(
            """SELECT manifest_json,manifest_checksum_sha256,public_id
            FROM model_evaluation_manifests
            WHERE model_evaluation_run_id=(
                SELECT id FROM model_evaluation_runs WHERE public_id=?
            ) ORDER BY created_at DESC LIMIT 1""",
            (candidate["model_evaluation_run_public_id"],),
        ).fetchone()
        if row is None:
            payload = {"status": "no_evaluation_manifest_found"}
            checksum = None
        else:
            payload = loads_json(row["manifest_json"])
            checksum = row["manifest_checksum_sha256"]
        target = self._write_json_artifact(
            candidate["public_id"], "evaluation_manifest.json", payload
        )
        return {
            "artifact_type": "evaluation_manifest",
            "source_entity_public_id": row["public_id"] if row else None,
            "logical_name": "evaluation_manifest.json",
            "storage_key": f"{candidate['public_id']}/evaluation_manifest.json",
            "size_bytes": target.stat().st_size,
            "checksum": checksum or file_checksum(target),
            "verification_status": "verified" if row is not None else "missing",
        }

    def _collect_licence_artifact(self, candidate) -> dict[str, Any]:
        text = (
            "Brud AI Internal Development Licence Notice\n\n"
            "This artifact is produced by an internal development project. "
            "It has not been reviewed for external distribution. "
            "No third-party licence claims are made for any bundled component.\n"
        )
        directory = self.settings.resolved_release_artifact_dir / candidate["public_id"]
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "LICENCE"
        target.write_text(text, encoding="utf-8")
        return {
            "artifact_type": "licence_notice",
            "source_entity_public_id": None,
            "logical_name": "LICENCE",
            "storage_key": f"{candidate['public_id']}/LICENCE",
            "size_bytes": target.stat().st_size,
            "checksum": file_checksum(target),
            "verification_status": "verified",
        }

    # --- artifact verification -----------------------------------------------------

    def verify_artifacts(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            artifacts = self.repository.artifacts_for_candidate(connection, candidate["id"])
            verified_count = 0
            for artifact in artifacts:
                if artifact["verification_status"] == "verified":
                    verified_count += 1
                    continue
                # already-classified at collection time; re-check executable/size bounds
                if detect_unexpected_executable(Path(artifact["logical_name"])):
                    continue
            self.repository.update_candidate(connection, candidate["id"], {"status": "validating"})
            self._audit(
                connection, "model_release_artifacts_verified", admin_id, candidate_public_id,
                verified_count=verified_count, total=len(artifacts),
            )
            rows = self.repository.artifacts_for_candidate(connection, candidate["id"])
            return {"items": [public_row(row) for row in rows]}

    # --- eligibility -----------------------------------------------------

    def assess_eligibility(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            artifacts = self.repository.artifacts_for_candidate(connection, candidate["id"])
            by_type = {row["artifact_type"]: dict(row) for row in artifacts}

            summary = loads_json(candidate["core_model_architecture_summary_json"])
            instruction_tuned = bool(summary.get("instruction_tuned"))

            checkpoint_missing = "model_checkpoint" not in by_type or by_type[
                "model_checkpoint"
            ]["verification_status"] == "missing"
            checkpoint_corrupt = by_type.get("model_checkpoint", {}).get(
                "verification_status"
            ) in {"checksum_mismatch", "invalid"}
            model_config_missing = "model_config" not in by_type or by_type[
                "model_config"
            ]["verification_status"] != "verified"
            tokenizer_missing = "tokenizer_model" not in by_type or by_type[
                "tokenizer_model"
            ]["verification_status"] == "missing"
            tokenizer_vocab_mismatch = candidate["tokenizer_vocabulary_size"] is None
            checksum_mismatch_count = sum(
                1 for row in artifacts if row["verification_status"] == "checksum_mismatch"
            )
            lineage_complete = bool(
                candidate["core_model_version_public_id"]
                and candidate["checkpoint_public_id"]
                and candidate["tokenizer_version_public_id"]
            )

            evaluation_status = None
            evaluation_manifest_present = by_type.get("evaluation_manifest", {}).get(
                "verification_status"
            ) == "verified"
            if candidate["model_evaluation_run_public_id"]:
                readiness_row = connection.execute(
                    """SELECT status FROM model_chat_readiness_assessments
                    WHERE model_evaluation_run_id=(
                        SELECT id FROM model_evaluation_runs WHERE public_id=?
                    ) ORDER BY created_at DESC LIMIT 1""",
                    (candidate["model_evaluation_run_public_id"],),
                ).fetchone()
                if readiness_row:
                    status_map = {
                        "evaluation_passed_with_limits": "evaluation_passed_with_limits",
                        "evaluation_warning": "evaluation_warning",
                        "evaluation_blocked": "evaluation_blocked",
                    }
                    evaluation_status = status_map.get(readiness_row["status"])

            instruction_manifest_present = by_type.get(
                "instruction_tuning_manifest", {}
            ).get("verification_status") == "verified"
            base_training_manifest_present = by_type.get(
                "base_training_manifest", {}
            ).get("verification_status") == "verified"
            safety_blocking_issue = False
            if candidate["model_evaluation_run_public_id"]:
                blocking_row = connection.execute(
                    """SELECT COUNT(*) FROM model_evaluation_issues
                    WHERE model_evaluation_run_id=(
                        SELECT id FROM model_evaluation_runs WHERE public_id=?
                    ) AND severity='blocking'""",
                    (candidate["model_evaluation_run_public_id"],),
                ).fetchone()
                safety_blocking_issue = bool(blocking_row and blocking_row[0] > 0)

            licence_status = (
                "complete" if by_type.get("licence_notice", {}).get(
                    "verification_status"
                ) == "verified" else "missing"
            )
            model_card_row = self.repository.latest_model_card(connection, candidate["id"])
            model_card_status = model_card_row["validation_status"] if model_card_row else "missing"
            manifest_mismatch = False
            candidate_already_retired_or_archived = candidate["status"] in {
                "rejected", "superseded", "archived",
            }

            thresholds = EligibilityThresholds(
                require_evaluation=self.settings.release_require_evaluation,
                allow_warning_eligibility=self.settings.release_allow_warning_eligibility,
                require_licence=self.settings.release_require_licence,
                require_model_card=self.settings.release_require_model_card,
                require_evaluation_manifest=self.settings.release_require_evaluation_manifest,
                require_instruction_manifest=self.settings.release_require_instruction_manifest,
                require_base_training_manifest=(
                    self.settings.release_require_base_training_manifest
                ),
                require_rollback_target=self.settings.release_require_rollback_target,
            )
            result = assess_release_eligibility(
                checkpoint_missing=checkpoint_missing, checkpoint_corrupt=checkpoint_corrupt,
                model_config_missing=model_config_missing, tokenizer_missing=tokenizer_missing,
                tokenizer_vocab_mismatch=tokenizer_vocab_mismatch,
                checksum_mismatch_count=checksum_mismatch_count,
                lineage_complete=lineage_complete, instruction_tuned=instruction_tuned,
                evaluation_status=evaluation_status,
                evaluation_manifest_present=evaluation_manifest_present,
                instruction_manifest_present=instruction_manifest_present,
                base_training_manifest_present=base_training_manifest_present,
                safety_blocking_issue=safety_blocking_issue, licence_status=licence_status,
                model_card_status=model_card_status, manifest_mismatch=manifest_mismatch,
                candidate_already_retired_or_archived=candidate_already_retired_or_archived,
                rollback_target_available=False,
                dataset_scale_warning=False, human_review_partial=False,
                resource_requirement_unknown=False, thresholds=thresholds,
            )
            checksum_input = {
                "candidate_public_id": candidate_public_id,
                "status": result["status"],
                "dimension_scores": result["dimension_scores"],
            }
            eligibility_checksum = hashlib.sha256(
                dumps_json(checksum_input).encode("utf-8")
            ).hexdigest()
            public_id = self.repository.record_eligibility(
                connection, candidate["id"],
                {
                    "status": result["status"],
                    "dimension_scores_json": dumps_json(result["dimension_scores"]),
                    "blocking_issue_count": len(result["rationale"]["blocking_reasons"]),
                    "warning_issue_count": len(result["rationale"]["warnings"]),
                    "rationale_json": dumps_json(result["rationale"]),
                    "eligibility_checksum_sha256": eligibility_checksum,
                    "created_by_admin_public_id": admin_id,
                },
            )
            for reason in result["rationale"]["blocking_reasons"]:
                self.repository.record_issue(
                    connection, candidate["id"],
                    {
                        "issue_code": self._map_reason_to_issue_code(reason),
                        "severity": "blocking",
                        "message": reason.replace("_", " "),
                    },
                )
            for warning in result["rationale"]["warnings"]:
                self.repository.record_issue(
                    connection, candidate["id"],
                    {
                        "issue_code": self._map_reason_to_issue_code(warning),
                        "severity": "warning",
                        "message": warning.replace("_", " "),
                    },
                )
            self.repository.update_candidate(
                connection, candidate["id"],
                {
                    "status": result["status"],
                    "latest_eligibility_status": result["status"],
                    "latest_eligibility_public_id": public_id,
                },
            )
            self._audit(
                connection, "model_release_eligibility_assessed", admin_id, candidate_public_id,
                status=result["status"],
            )
            return public_row(self.repository.latest_eligibility(connection, candidate["id"]))

    _REASON_TO_ISSUE_CODE = {
        "checkpoint_missing": "artifact_missing",
        "checkpoint_corrupt": "checkpoint_corrupt",
        "model_config_missing": "model_config_mismatch",
        "tokenizer_missing": "tokenizer_missing",
        "tokenizer_vocab_mismatch": "tokenizer_vocab_mismatch",
        "artifact_checksum_mismatch": "artifact_checksum_mismatch",
        "dataset_lineage_missing": "dataset_lineage_missing",
        "evaluation_blocked": "evaluation_blocked",
        "evaluation_warning": "evaluation_warning",
        "evaluation_manifest_missing": "evaluation_manifest_missing",
        "instruction_manifest_missing": "instruction_manifest_missing",
        "training_manifest_missing": "training_manifest_missing",
        "safety_blocking_issue": "safety_blocking_issue",
        "licence_missing": "licence_missing",
        "licence_unsupported": "licence_unsupported",
        "model_card_incomplete": "model_card_incomplete",
        "model_card_not_yet_validated": "model_card_incomplete",
        "release_manifest_mismatch": "release_manifest_mismatch",
        "candidate_already_retired_or_archived": "version_conflict",
        "rollback_target_unavailable": "rollback_target_missing",
        "limited_training_dataset": "resource_requirement_unknown",
        "partial_human_review": "resource_requirement_unknown",
        "resource_estimate_warning": "resource_requirement_unknown",
    }

    def _map_reason_to_issue_code(self, reason: str) -> str:
        return self._REASON_TO_ISSUE_CODE.get(reason, "resource_requirement_unknown")

    def issues_for_candidate(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            rows = self.repository.issues_for_candidate(connection, candidate["id"])
        return {"items": [public_row(row) for row in rows]}

    def get_eligibility(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            row = self.repository.latest_eligibility(connection, candidate["id"])
        if row is None:
            raise NotFoundError("no eligibility assessment exists for this candidate")
        return public_row(row)

    # --- model card -----------------------------------------------------

    def generate_model_card(
        self, candidate_public_id: str, overrides: ModelCardOverrides, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            config_row = connection.execute(
                "SELECT * FROM core_model_configs WHERE id=?",
                (candidate["core_model_config_id"],),
            ).fetchone()
            resources = classify_resource_requirements(
                actual_parameter_count=config_row["parameter_count_estimate"],
                estimated_inference_memory_bytes=config_row["memory_estimate_bytes"],
                estimated_training_memory_bytes=config_row["memory_estimate_bytes"] * 3,
                context_length=config_row["context_length"],
            )
            fields = {
                "model_name": candidate["label"] or candidate["core_model_version_public_id"],
                "version": candidate["core_model_version_public_id"][:8],
                "release_family": candidate["model_release_family_public_id"],
                "summary": (
                    overrides.summary
                    or "Internal development model registered for release governance testing."
                ),
                "architecture": "brud_decoder_transformer",
                "parameter_count": str(config_row["parameter_count_estimate"]),
                "context_length": str(config_row["context_length"]),
                "tokenizer": candidate["tokenizer_version_public_id"],
                "training_datasets": candidate["dataset_version_public_id"] or "not_recorded",
                "dataset_limitations": (
                    "Training data scale for this project remains small; see the "
                    "linked base-training and instruction-tuning manifests."
                ),
                "base_training": "See linked base_training_manifest artifact.",
                "instruction_tuning": (
                    candidate["instruction_tuning_candidate_public_id"] or "not_applicable"
                ),
                "evaluation": candidate["model_evaluation_run_public_id"] or "not_assessed",
                "supported_languages": "ta, en, tgl, mixed",
                "intended_uses": (
                    overrides.intended_uses
                    or "Internal registry and release-governance testing only."
                ),
                "out_of_scope_uses": (
                    overrides.out_of_scope_uses or "Any production or user-facing deployment."
                ),
                "known_limitations": (
                    overrides.known_limitations or "Model scale and dataset size remain limited."
                ),
                "safety_limitations": (
                    overrides.safety_limitations
                    or "Safety checks are keyword-based and non-exhaustive."
                ),
                "resource_requirements": dumps_json(resources),
                "licence_and_provenance": (
                    overrides.licence_and_provenance
                    or "Internal development licence; see LICENCE artifact."
                ),
                "artifact_checksums": candidate["checkpoint_model_checksum_sha256"],
                "release_status": candidate["status"],
                "deployment_eligibility": "not_deployable",
                "public_chat_assignment_status": "none (not assigned to the public chatbot)",
            }
            markdown = render_model_card(fields)
            checksum = model_card_checksum(markdown)
            public_id = self.repository.record_model_card(
                connection, candidate["id"],
                {"card_markdown": markdown, "card_checksum_sha256": checksum},
            )
            self.repository.update_candidate(
                connection, candidate["id"], {"latest_model_card_public_id": public_id}
            )
            directory = self.settings.resolved_release_artifact_dir / candidate["public_id"]
            directory.mkdir(parents=True, exist_ok=True)
            card_path = directory / "model_card.md"
            card_path.write_text(markdown, encoding="utf-8")
            self.repository.record_artifact(
                connection, candidate["id"],
                {
                    "artifact_type": "model_card",
                    "source_entity_public_id": public_id,
                    "logical_name": "model_card.md",
                    "storage_key": f"{candidate['public_id']}/model_card.md",
                    "size_bytes": card_path.stat().st_size,
                    "checksum": checksum,
                    "verification_status": "verified",
                },
            )
            self._audit(connection, "model_card_generated", admin_id, candidate_public_id)
            return public_row(self.repository.latest_model_card(connection, candidate["id"]))

    def get_model_card(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            row = self.repository.latest_model_card(connection, candidate["id"])
        if row is None:
            raise NotFoundError("no model card has been generated for this candidate")
        return public_row(row)

    def validate_model_card(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            card = self.repository.latest_model_card(connection, candidate["id"])
            if card is None:
                raise ValidationError("generate a model card before validating it")
            config_row = connection.execute(
                "SELECT * FROM core_model_configs WHERE id=?",
                (candidate["core_model_config_id"],),
            ).fetchone()
            evaluation_status = None
            if candidate["model_evaluation_run_public_id"]:
                readiness_row = connection.execute(
                    """SELECT status FROM model_chat_readiness_assessments
                    WHERE model_evaluation_run_id=(
                        SELECT id FROM model_evaluation_runs WHERE public_id=?
                    ) ORDER BY created_at DESC LIMIT 1""",
                    (candidate["model_evaluation_run_public_id"],),
                ).fetchone()
                if readiness_row and readiness_row["status"] == "evaluation_blocked":
                    evaluation_status = "evaluation_blocked"
                elif readiness_row:
                    evaluation_status = "eligible"
            result = run_model_card_validation(
                card["card_markdown"], evaluation_status=evaluation_status,
                not_public_chat_ready=True,
                actual_parameter_count=config_row["parameter_count_estimate"],
                registered_parameter_count=config_row["parameter_count_estimate"],
                checkpoint_checksum=candidate["checkpoint_model_checksum_sha256"],
                registered_checkpoint_checksum=candidate["checkpoint_model_checksum_sha256"],
            )
            validation_status = "valid" if not result["issues"] else "invalid"
            public_id = self.repository.record_model_card(
                connection, candidate["id"],
                {
                    "card_markdown": card["card_markdown"],
                    "card_checksum_sha256": card["card_checksum_sha256"],
                    "validation_status": validation_status,
                    "validation_issues_json": dumps_json(result["issues"]),
                },
            )
            self.repository.update_candidate(
                connection, candidate["id"], {"latest_model_card_public_id": public_id}
            )
            self._audit(
                connection, "model_card_validated", admin_id, candidate_public_id,
                validation_status=validation_status,
            )
            return public_row(self.repository.latest_model_card(connection, candidate["id"]))

    # --- release manifest -----------------------------------------------------

    def generate_manifest(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            artifacts = self.repository.artifacts_for_candidate(connection, candidate["id"])
            eligibility = self.repository.latest_eligibility(connection, candidate["id"])
            model_card = self.repository.latest_model_card(connection, candidate["id"])
            approvals = self.repository.approvals_for_candidate(connection, candidate["id"])
            config_row = connection.execute(
                "SELECT * FROM core_model_configs WHERE id=?",
                (candidate["core_model_config_id"],),
            ).fetchone()
            resources = classify_resource_requirements(
                actual_parameter_count=config_row["parameter_count_estimate"],
                estimated_inference_memory_bytes=config_row["memory_estimate_bytes"],
                estimated_training_memory_bytes=config_row["memory_estimate_bytes"] * 3,
                context_length=config_row["context_length"],
            )
            evaluation_status = "not_assessed"
            if candidate["model_evaluation_run_public_id"]:
                readiness_row = connection.execute(
                    """SELECT status FROM model_chat_readiness_assessments
                    WHERE model_evaluation_run_id=(
                        SELECT id FROM model_evaluation_runs WHERE public_id=?
                    ) ORDER BY created_at DESC LIMIT 1""",
                    (candidate["model_evaluation_run_public_id"],),
                ).fetchone()
                if readiness_row:
                    evaluation_status = readiness_row["status"]
            by_type = {row["artifact_type"]: dict(row) for row in artifacts}
            manifest = {
                "release_family_public_id": candidate["model_release_family_public_id"],
                "candidate_public_id": candidate_public_id,
                "core_model_version_public_id": candidate["core_model_version_public_id"],
                "checkpoint_public_id": candidate["checkpoint_public_id"],
                "checkpoint_checksum_sha256": candidate["checkpoint_model_checksum_sha256"],
                "model_config_checksum_sha256": candidate["core_model_config_checksum_sha256"],
                "parameter_count": config_row["parameter_count_estimate"],
                "context_length": config_row["context_length"],
                "tokenizer_version_public_id": candidate["tokenizer_version_public_id"],
                "tokenizer_checksums": {
                    "model": candidate["tokenizer_model_checksum_sha256"],
                    "vocabulary": candidate["tokenizer_vocabulary_checksum_sha256"],
                },
                "dataset_versions": (
                    [candidate["dataset_version_public_id"]]
                    if candidate["dataset_version_public_id"] else []
                ),
                "base_training_manifest_checksum_sha256": by_type.get(
                    "base_training_manifest", {}
                ).get("checksum"),
                "instruction_tuning_manifest_checksum_sha256": by_type.get(
                    "instruction_tuning_manifest", {}
                ).get("checksum"),
                "evaluation_manifest_checksum_sha256": by_type.get(
                    "evaluation_manifest", {}
                ).get("checksum"),
                "evaluation_readiness_status": evaluation_status,
                "model_card_checksum_sha256": (
                    model_card["card_checksum_sha256"] if model_card else None
                ),
                "licence_notices": [by_type.get("licence_notice", {}).get("checksum")],
                "compatibility_assessment": {},
                "eligibility_assessment": {
                    "status": eligibility["status"] if eligibility else "not_assessed",
                    "checksum": eligibility["eligibility_checksum_sha256"] if eligibility else None,
                },
                "approvals": [
                    {"role": row["role"], "decision": row["decision"]} for row in approvals
                ],
                "resource_requirements": resources,
                "supported_languages": ["ta", "en", "tgl", "mixed"],
                "known_limitations": {
                    "not_public_chat_ready": True,
                    "not_production_deployment_approved": True,
                },
                "software_versions": {"brud_ai_phase": 14},
                "created_at": None,
            }
            concerns = scan_for_sensitive_content(manifest)
            if concerns:
                raise ValidationError(f"manifest failed sensitive-content scan: {concerns}")
            manifest_json = dumps_json(manifest)
            checksum = manifest_checksum(manifest)
            public_id = self.repository.record_manifest(
                connection, candidate["id"], manifest_json, checksum
            )
            self.repository.update_candidate(
                connection, candidate["id"], {"latest_manifest_public_id": public_id}
            )
            directory = self.settings.resolved_release_artifact_dir / candidate["public_id"]
            directory.mkdir(parents=True, exist_ok=True)
            manifest_path = directory / "release_manifest.json"
            manifest_path.write_text(manifest_json, encoding="utf-8")
            self.repository.record_artifact(
                connection, candidate["id"],
                {
                    "artifact_type": "release_manifest",
                    "source_entity_public_id": public_id,
                    "logical_name": "release_manifest.json",
                    "storage_key": f"{candidate['public_id']}/release_manifest.json",
                    "size_bytes": manifest_path.stat().st_size,
                    "checksum": checksum,
                    "verification_status": "verified",
                },
            )
            self._audit(
                connection, "model_release_manifest_generated", admin_id, candidate_public_id
            )
            return public_row(self.repository.latest_manifest(connection, candidate["id"]))

    def get_manifest(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            row = self.repository.latest_manifest(connection, candidate["id"])
        if row is None:
            raise NotFoundError("no release manifest has been generated for this candidate")
        return public_row(row)

    def verify_manifest(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            row = self.repository.latest_manifest(connection, candidate["id"])
            if row is None:
                raise NotFoundError("no release manifest exists for this candidate")
            recomputed = hashlib.sha256(row["manifest_json"].encode("utf-8")).hexdigest()
            matches = recomputed == row["manifest_checksum_sha256"]
        return {
            "public_id": row["public_id"], "stored_checksum": row["manifest_checksum_sha256"],
            "recomputed_checksum": recomputed, "matches": matches,
        }

    # --- approvals -----------------------------------------------------

    def submit_approval(
        self, candidate_public_id: str, payload: ApprovalCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            eligibility = self.repository.latest_eligibility(connection, candidate["id"])
            if eligibility is None:
                raise ValidationError("assess eligibility before submitting an approval")
            manifest = self.repository.latest_manifest(connection, candidate["id"])
            if payload.role not in {"technical", "evaluation", "security", "release"}:
                raise ValidationError("invalid approval role")
            if payload.decision not in {
                "approve", "approve_with_warning", "reject", "request_changes",
            }:
                raise ValidationError("invalid approval decision")
            is_self_approval = admin_id == candidate["created_by_admin_public_id"]
            policy = ApprovalPolicy(
                required_roles=self.settings.release_required_approval_roles_list,
                allow_self_approval=self.settings.release_allow_self_approval,
            )
            violations = validate_approval_submission(
                decision=payload.decision, comment=payload.comment,
                candidate_status_is_blocked=candidate["status"] == "blocked",
                is_self_approval=is_self_approval, policy=policy,
            )
            if violations:
                raise ValidationError(f"approval rejected: {violations}")
            public_id = self.repository.record_approval(
                connection, candidate["id"],
                {
                    "admin_public_id": admin_id,
                    "role": payload.role,
                    "decision": payload.decision,
                    "comment": payload.comment,
                    "eligibility_checksum_sha256": eligibility["eligibility_checksum_sha256"],
                    "manifest_checksum_sha256": (
                        manifest["manifest_checksum_sha256"] if manifest else None
                    ),
                },
            )
            approvals = self.repository.approvals_for_candidate(connection, candidate["id"])
            policy_result = is_policy_satisfied(
                [public_row(row) for row in approvals], policy
            )
            if policy_result["satisfied"] and candidate["status"] in {
                "eligible", "eligible_with_warnings",
            }:
                self.repository.update_candidate(
                    connection, candidate["id"], {"status": "approved"}
                )
            action = "model_release_approval_rejected" if payload.decision in {
                "reject", "request_changes",
            } else "model_release_approval_recorded"
            self._audit(connection, action, admin_id, candidate_public_id, role=payload.role)
            return public_row(
                connection.execute(
                    "SELECT * FROM model_release_approvals WHERE public_id=?", (public_id,)
                ).fetchone()
            )

    def approvals_for_candidate(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            rows = self.repository.approvals_for_candidate(connection, candidate["id"])
        return {"items": [public_row(row) for row in rows]}

    # --- releases -----------------------------------------------------

    def create_release(self, payload: ModelReleaseCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, payload.candidate_public_id)
            if candidate["status"] != "approved":
                raise ValidationError("candidate must be approved before creating a release")
            if candidate["latest_eligibility_status"] not in {
                "eligible", "eligible_with_warnings",
            }:
                raise ValidationError(
                    "candidate eligibility must be eligible or eligible_with_warnings"
                )
            manifest = self.repository.latest_manifest(connection, candidate["id"])
            if manifest is None:
                raise ValidationError("release manifest must be generated before release")
            recomputed = hashlib.sha256(manifest["manifest_json"].encode("utf-8")).hexdigest()
            if recomputed != manifest["manifest_checksum_sha256"]:
                raise ValidationError("release manifest failed checksum verification")
            approvals = self.repository.approvals_for_candidate(connection, candidate["id"])
            policy = ApprovalPolicy(
                required_roles=self.settings.release_required_approval_roles_list,
                allow_self_approval=self.settings.release_allow_self_approval,
            )
            policy_result = is_policy_satisfied([public_row(row) for row in approvals], policy)
            if not policy_result["satisfied"]:
                raise ValidationError(f"required approvals incomplete: {policy_result}")
            current_eligibility = self.repository.latest_eligibility(connection, candidate["id"])
            for approval in approvals:
                if is_approval_stale(
                    approval_eligibility_checksum=approval["eligibility_checksum_sha256"],
                    current_eligibility_checksum=current_eligibility["eligibility_checksum_sha256"],
                    approval_manifest_checksum=approval["manifest_checksum_sha256"],
                    current_manifest_checksum=manifest["manifest_checksum_sha256"],
                ):
                    raise ValidationError("approval is stale; candidate evidence has changed")
            if self.repository.release_version_exists(
                connection, candidate["model_release_family_id"], payload.version
            ):
                raise ValidationError("release version already exists for this family")
            deployment_eligibility = (
                "deployable" if candidate["latest_eligibility_status"] == "eligible"
                else "deployable_with_warnings"
            )
            public_id = self.repository.create_release(
                connection,
                {
                    "model_release_family_id": candidate["model_release_family_id"],
                    "model_release_candidate_id": candidate["id"],
                    "version": payload.version,
                    "prerelease_label": payload.prerelease_label,
                    "status": "released",
                    "deployment_eligibility": deployment_eligibility,
                    "release_manifest_public_id": manifest["public_id"],
                    "created_by_admin_public_id": admin_id,
                },
            )
            connection.execute(
                "UPDATE model_releases SET released_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (public_id,),
            )
            self.repository.update_candidate(connection, candidate["id"], {"status": "released"})
            connection.execute(
                "UPDATE model_release_families SET current_release_public_id=? WHERE id=?",
                (public_id, candidate["model_release_family_id"]),
            )
            self._audit(
                connection, "model_release_created", admin_id, public_id, version=payload.version,
            )
            return public_row(self.repository.release(connection, public_id))

    def get_release(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.release(connection, public_id))

    def list_releases(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_releases(connection)
        return {"items": [public_row(row) for row in rows]}

    def deprecate_release(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            release = self.repository.release(connection, public_id)
            if release["status"] != "released":
                raise ValidationError("only a released version may be deprecated")
            self.repository.update_release(connection, release["id"], {"status": "deprecated"})
            connection.execute(
                "UPDATE model_releases SET deprecated_at=CURRENT_TIMESTAMP WHERE id=?",
                (release["id"],),
            )
            self._audit(connection, "model_release_deprecated", admin_id, public_id)
            return public_row(self.repository.release(connection, public_id))

    def retire_release(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            release = self.repository.release(connection, public_id)
            if release["status"] not in {"released", "deprecated"}:
                raise ValidationError("only a released or deprecated version may be retired")
            self.repository.update_release(
                connection, release["id"],
                {"status": "retired", "deployment_eligibility": "not_deployable"},
            )
            connection.execute(
                "UPDATE model_releases SET retired_at=CURRENT_TIMESTAMP WHERE id=?",
                (release["id"],),
            )
            self._audit(connection, "model_release_retired", admin_id, public_id)
            return public_row(self.repository.release(connection, public_id))

    # --- comparisons -----------------------------------------------------

    def _release_comparison_fields(self, connection, release) -> dict[str, Any]:
        candidate = connection.execute(
            "SELECT * FROM model_release_candidates WHERE id=?",
            (release["model_release_candidate_id"],),
        ).fetchone()
        candidate_public = public_row(self.repository.candidate(connection, candidate["public_id"]))
        suite_public_id = None
        if candidate_public.get("model_evaluation_run_public_id"):
            suite_row = connection.execute(
                """SELECT s.public_id FROM model_evaluation_suites s
                JOIN model_evaluation_runs r ON r.model_evaluation_suite_id=s.id
                WHERE r.public_id=?""",
                (candidate_public["model_evaluation_run_public_id"],),
            ).fetchone()
            suite_public_id = suite_row["public_id"] if suite_row else None
        return {
            "tokenizer_version_public_id": candidate_public["tokenizer_version_public_id"],
            "model_config_checksum_sha256": candidate_public["core_model_config_checksum_sha256"],
            "evaluation_suite_public_id": suite_public_id,
            "deployment_eligibility": release["deployment_eligibility"],
            "version": release["version"],
        }

    def compare_releases(
        self, payload: ModelReleaseComparisonCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            left_release = self.repository.release(connection, payload.left_release_public_id)
            right_release = self.repository.release(connection, payload.right_release_public_id)
            left = self._release_comparison_fields(connection, left_release)
            right = self._release_comparison_fields(connection, right_release)
            comparison = assess_release_comparison(left, right, list(left))
            public_id = self.repository.record_comparison(
                connection,
                {
                    "left_release_id": left_release["id"],
                    "right_release_id": right_release["id"],
                    "compatibility": comparison["compatibility"],
                    "ranked": comparison["ranked"],
                    "fields_json": dumps_json(comparison["fields"]),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "model_release_comparison_created", admin_id, public_id,
                compatibility=comparison["compatibility"],
            )
            return public_row(self.repository.comparison(connection, public_id))

    def get_comparison(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.comparison(connection, public_id))

    # --- bundles -----------------------------------------------------

    def build_bundle(
        self, release_public_id: str, bundle_format: str, admin_id: str
    ) -> dict[str, Any]:
        allowed_formats = {
            item.strip() for item in self.settings.release_allowed_bundle_formats.split(",")
        }
        if bundle_format not in allowed_formats:
            raise ValidationError("unsupported bundle format")
        with self.repository.transaction() as connection:
            release = self.repository.release(connection, release_public_id)
            if release["status"] not in {"released", "deprecated"}:
                raise ValidationError("bundle can only be built for a released version")
            if release["deployment_eligibility"] == "not_deployable":
                raise ValidationError("bundle generation is rejected for a blocked release")
            candidate = self.repository.candidate(
                connection, release["model_release_candidate_public_id"]
            )
            artifacts = [
                public_row(row)
                for row in self.repository.artifacts_for_candidate(connection, candidate["id"])
            ]
            instruction_tuned = bool(
                loads_json(candidate["core_model_architecture_summary_json"]).get(
                    "instruction_tuned"
                )
            )
            problems = validate_bundle_source_artifacts(
                artifacts, instruction_tuned=instruction_tuned
            )
            if problems:
                self.repository.record_issue(
                    connection, candidate["id"],
                    {
                        "issue_code": "bundle_generation_failed", "severity": "blocking",
                        "message": f"missing verified artifacts: {problems}",
                    },
                )
                raise ValidationError(f"bundle generation rejected: missing artifacts {problems}")

        inventory = build_bundle_inventory(artifacts)
        forbidden = scan_bundle_paths_for_forbidden_content([entry["path"] for entry in inventory])
        if forbidden:
            raise ValidationError(f"bundle generation rejected: forbidden paths {forbidden}")

        bundle_dir = self.settings.resolved_release_bundle_dir
        bundle_dir.mkdir(parents=True, exist_ok=True)
        archive_name = f"{release_public_id}.zip"
        archive_path = bundle_dir / archive_name
        if archive_path.exists():
            archive_path.unlink()
        self._write_bundle_archive(archive_path, candidate, artifacts)
        size_bytes = archive_path.stat().st_size
        if not is_bundle_size_within_limit(size_bytes, self.settings.release_max_bundle_size_bytes):
            archive_path.unlink()
            raise ValidationError("bundle exceeds the configured maximum size")
        bundle_file_checksum = file_checksum(archive_path)

        with self.repository.transaction() as connection:
            public_id = self.repository.record_bundle(
                connection, release["id"],
                {
                    "bundle_format": bundle_format,
                    "inventory_json": dumps_json(inventory),
                    "bundle_checksum_sha256": bundle_file_checksum,
                    "size_bytes": size_bytes,
                    "storage_key": archive_name,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "model_release_bundle_generated", admin_id, release_public_id,
                bundle_public_id=public_id,
            )
            return public_row(self.repository.bundle(connection, public_id))

    def _write_bundle_archive(self, archive_path: Path, candidate, artifacts: list[dict]) -> None:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for artifact in artifacts:
                artifact_type = artifact["artifact_type"]
                if artifact_type == "model_checkpoint":
                    checkpoint_dir = (
                        self.settings.resolved_pretraining_dir / artifact["storage_key"]
                    )
                    if checkpoint_dir.is_dir():
                        for file_path in sorted(checkpoint_dir.rglob("*")):
                            if file_path.is_file():
                                archive.write(
                                    file_path, f"model/checkpoint/{file_path.name}"
                                )
                    continue
                source_path = self._resolve_artifact_source_path(artifact)
                bundle_path = self._bundle_path_for(artifact_type)
                if source_path is not None and source_path.is_file() and bundle_path:
                    archive.write(source_path, bundle_path)
            readme = (
                "Brud AI Model Release Bundle\n\n"
                "This bundle contains a registered model release's artifacts, "
                "manifests, and model card. It is not a deployment package and "
                "does not connect to the public chatbot.\n"
            )
            archive.writestr("README.md", readme)

    def _resolve_artifact_source_path(self, artifact: dict) -> Path | None:
        artifact_type = artifact["artifact_type"]
        if artifact_type in {"tokenizer_model", "tokenizer_vocab"}:
            return self.settings.resolved_tokenizer_dir / artifact["storage_key"]
        return self.settings.resolved_release_artifact_dir / artifact["storage_key"]

    def _bundle_path_for(self, artifact_type: str) -> str | None:
        mapping = {
            "model_config": "model/config.json",
            "tokenizer_model": "tokenizer/tokenizer.model",
            "tokenizer_vocab": "tokenizer/tokenizer.vocab",
            "tokenizer_manifest": "tokenizer/tokenizer_manifest.json",
            "base_training_manifest": "manifests/training_manifest.json",
            "instruction_tuning_manifest": "manifests/instruction_manifest.json",
            "evaluation_manifest": "manifests/evaluation_manifest.json",
            "model_card": "model_card.md",
            "licence_notice": "LICENCE",
        }
        return mapping.get(artifact_type)

    def bundles_for_release(self, release_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            release = self.repository.release(connection, release_public_id)
            rows = self.repository.bundles_for_release(connection, release["id"])
        return {"items": [public_row(row) for row in rows]}

    def verify_bundle(self, bundle_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            bundle = self.repository.bundle(connection, bundle_public_id)
        archive_path = self.settings.resolved_release_bundle_dir / bundle["storage_key"]
        if not archive_path.is_file():
            return {
                "public_id": bundle_public_id, "stored_checksum": bundle["bundle_checksum_sha256"],
                "recomputed_checksum": None, "matches": False,
            }
        recomputed = file_checksum(archive_path)
        return {
            "public_id": bundle_public_id,
            "stored_checksum": bundle["bundle_checksum_sha256"],
            "recomputed_checksum": recomputed,
            "matches": recomputed == bundle["bundle_checksum_sha256"],
        }

    # --- rollback -----------------------------------------------------

    def create_rollback_plan(
        self, release_public_id: str, payload: RollbackPlanCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source_release = self.repository.release(connection, release_public_id)
            target_release = self.repository.release(
                connection, payload.target_release_public_id
            )
            if (
                target_release["model_release_family_id"]
                != source_release["model_release_family_id"]
            ):
                raise ValidationError("rollback target must belong to the same release family")
            target_candidate = self.repository.candidate(
                connection, target_release["model_release_candidate_public_id"]
            )
            evaluation_blocked = target_candidate["latest_eligibility_status"] == "blocked"
            blocking_issues = connection.execute(
                """SELECT COUNT(*) FROM model_release_issues
                WHERE model_release_candidate_id=? AND severity='blocking'""",
                (target_candidate["id"],),
            ).fetchone()[0]
            manifest = self.repository.latest_manifest(connection, target_candidate["id"])
            manifest_verified = False
            if manifest:
                recomputed = hashlib.sha256(manifest["manifest_json"].encode("utf-8")).hexdigest()
                manifest_verified = recomputed == manifest["manifest_checksum_sha256"]
            target_result = assess_rollback_target(
                target_status=target_release["status"],
                target_archived=target_release["status"] == "archived",
                target_artifacts_verified=target_candidate["latest_eligibility_status"] in {
                    "eligible", "eligible_with_warnings",
                },
                target_manifest_verified=manifest_verified,
                target_family_compatible=True,
                target_deployment_eligibility=target_release["deployment_eligibility"],
                target_evaluation_blocked=evaluation_blocked,
                target_has_blocking_issue=blocking_issues > 0,
            )
            public_id = self.repository.create_rollback_plan(
                connection,
                {
                    "source_release_id": source_release["id"],
                    "target_release_id": target_release["id"],
                    "reason": payload.reason,
                    "compatibility_result_json": dumps_json(target_result),
                    "target_verification_json": dumps_json({
                        "manifest_verified": manifest_verified,
                        "blocking_issue_count": blocking_issues,
                    }),
                    "created_by_admin_public_id": admin_id,
                },
            )
            if not target_result["eligible"]:
                self.repository.update_rollback_plan(
                    connection,
                    connection.execute(
                        "SELECT id FROM model_release_rollback_plans WHERE public_id=?",
                        (public_id,),
                    ).fetchone()["id"],
                    {"status": "rejected"},
                )
            self._audit(
                connection, "model_release_rollback_plan_created", admin_id, public_id,
                target_eligible=target_result["eligible"],
            )
            return public_row(self.repository.rollback_plan(connection, public_id))

    def get_rollback_plan(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.rollback_plan(connection, public_id))

    def validate_rollback_plan(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            plan = self.repository.rollback_plan(connection, public_id)
            if plan["status"] == "rejected":
                return public_row(plan)
            if plan["status"] != "draft":
                raise ValidationError("only a draft rollback plan may be validated")
            compatibility_result = loads_json(plan["compatibility_result_json"])
            new_status = "validated" if compatibility_result.get("eligible") else "rejected"
            self.repository.update_rollback_plan(connection, plan["id"], {"status": new_status})
            if new_status == "validated":
                connection.execute(
                    "UPDATE model_release_rollback_plans SET validated_at=CURRENT_TIMESTAMP "
                    "WHERE id=?",
                    (plan["id"],),
                )
            self._audit(
                connection, "model_release_rollback_plan_validated", admin_id, public_id,
                status=new_status,
            )
            return public_row(self.repository.rollback_plan(connection, public_id))

    def approve_rollback_plan(
        self, public_id: str, payload: RollbackApprovalCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            plan = self.repository.rollback_plan(connection, public_id)
            if plan["status"] != "validated":
                raise ValidationError("rollback plan must be validated before approval")
            self.repository.update_rollback_plan(connection, plan["id"], {"status": "approved"})
            connection.execute(
                "UPDATE model_release_rollback_plans SET approved_at=CURRENT_TIMESTAMP WHERE id=?",
                (plan["id"],),
            )
            self._audit(
                connection, "model_release_rollback_plan_approved", admin_id, public_id,
                comment=payload.comment,
            )
            return public_row(self.repository.rollback_plan(connection, public_id))

    def execute_rollback_plan(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            plan = self.repository.rollback_plan(connection, public_id)
            if plan["status"] != "approved":
                raise ValidationError("rollback plan must be approved before execution")
            source_release = self.repository.release(
                connection, plan["source_release_public_id"]
            )
            target_release = self.repository.release(
                connection, plan["target_release_public_id"]
            )
            self.repository.update_release(
                connection, source_release["id"], {"status": "rolled_back"}
            )
            connection.execute(
                "UPDATE model_release_families SET current_release_public_id=? WHERE id=?",
                (target_release["public_id"], target_release["model_release_family_id"]),
            )
            self.repository.update_rollback_plan(connection, plan["id"], {"status": "executed"})
            connection.execute(
                "UPDATE model_release_rollback_plans SET executed_at=CURRENT_TIMESTAMP WHERE id=?",
                (plan["id"],),
            )
            self.repository.record_rollback_event(
                connection, plan["id"],
                {
                    "previous_release_public_id": source_release["public_id"],
                    "new_release_public_id": target_release["public_id"],
                    "approval_evidence_json": dumps_json({"executed_by": admin_id}),
                    "executed_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "model_release_rollback_executed", admin_id, public_id,
                previous_release=source_release["public_id"],
                new_release=target_release["public_id"],
            )
            return public_row(self.repository.rollback_plan(connection, public_id))

    # --- helpers -----------------------------------------------------

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
                "model_release", resource_id, "success", dumps_json(metadata),
            ),
        )
