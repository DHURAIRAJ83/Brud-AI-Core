"""Phase 15 Step 17: artifact security -- an independent, read-only
second pass over artifacts the existing registries already collected.

Never re-collects or re-derives an artifact; only reuses the storage
key/checksum/root each existing service already recorded
(`ModelReleaseService.collect_artifacts`, backup files under
`settings.resolved_backup_dir`, `production_rag_release_candidates`
checksums) and independently re-verifies confinement, unexpected
executables, and checksum integrity. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.api.routes.system import _latest_backup
from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.production_backup_restore_readiness_service import encrypted_backup_paths
from core_model.release.artifact_inventory import (
    detect_unexpected_executable,
    file_checksum,
    resolve_confined_path,
)

logger = logging.getLogger(__name__)

_ARTIFACT_TYPE_MAP = {
    "model_checkpoint": "checkpoint",
    "tokenizer_model": "tokenizer",
    "tokenizer_vocab": "tokenizer",
    "dataset_manifest": "dataset_manifest",
    "base_training_manifest": "training_manifest",
    "instruction_tuning_manifest": "training_manifest",
    "evaluation_manifest": "training_manifest",
    "model_config": "configuration",
    "licence_notice": "configuration",
    "model_card": "configuration",
}


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"production_artifact_security_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_artifact_security_check",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "production_artifact_security_audit_write_failed", extra={"action": action}
        )


class ProductionArtifactSecurityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._release_repository = ModelReleaseRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _root_for(self, artifact_type: str) -> Path:
        if artifact_type == "model_checkpoint":
            return self.settings.resolved_pretraining_dir
        if artifact_type in ("tokenizer_model", "tokenizer_vocab"):
            return self.settings.resolved_tokenizer_dir
        return self.settings.resolved_release_artifact_dir

    def _verify_one(self, artifact: dict[str, Any], *, admin_id: str) -> dict[str, Any]:
        root = self._root_for(artifact["artifact_type"])
        findings: list[str] = []
        checks: dict[str, Any] = {}
        try:
            resolved = resolve_confined_path(root, artifact["storage_key"])
            checks["path_confined"] = True
        except ValueError:
            checks["path_confined"] = False
            findings.append("path_not_confined")

        if checks["path_confined"]:
            exists = resolved.is_dir() if artifact["artifact_type"] == "model_checkpoint" \
                else resolved.is_file()
            checks["exists"] = exists
            if not exists:
                findings.append("artifact_missing")
            else:
                files = (
                    [f for f in resolved.rglob("*") if f.is_file()]
                    if resolved.is_dir() else [resolved]
                )
                unexpected_executable = any(detect_unexpected_executable(f) for f in files)
                checks["unexpected_executable_present"] = unexpected_executable
                if unexpected_executable:
                    findings.append("unexpected_executable_present")
                if resolved.is_file():
                    recomputed = file_checksum(resolved)
                    checksum_matches = recomputed == artifact["checksum"]
                    checks["checksum_matches"] = checksum_matches
                    if not checksum_matches:
                        findings.append("checksum_mismatch")
        else:
            checks["exists"] = False

        result_status = "passed"
        if any(f in {"path_not_confined", "unexpected_executable_present", "checksum_mismatch"}
               for f in findings):
            result_status = "failed"
        elif findings:
            result_status = "passed_with_warning"

        recorded = self.repository.add_artifact_security_check(
            {
                "artifact_type": _ARTIFACT_TYPE_MAP.get(artifact["artifact_type"], "configuration"),
                "artifact_reference": artifact["public_id"],
                "result_status": result_status,
                "checks": checks,
                "findings": findings,
                "created_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="check_artifact", actor_reference=admin_id,
            resource_public_id=recorded["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status, "findings": findings},
        )
        return recorded

    def check_release_candidate_artifacts(
        self, candidate_public_id: str, *, admin_id: str
    ) -> list[dict[str, Any]]:
        with self._release_repository.transaction() as connection:
            candidate = self._release_repository.candidate(connection, candidate_public_id)
            artifacts = [
                dict(row)
                for row in self._release_repository.artifacts_for_candidate(
                    connection, candidate["id"]
                )
            ]
        return [self._verify_one(artifact, admin_id=admin_id) for artifact in artifacts]

    def check_backup_artifact(self, *, admin_id: str) -> dict[str, Any]:
        backup_dir = self.settings.resolved_backup_dir
        findings: list[str] = []
        checks: dict[str, Any] = {}
        latest = _latest_backup(backup_dir) if backup_dir.exists() else None
        checks["backup_present"] = latest is not None
        if latest is None:
            findings.append("no_backup_present")
            result_status = "not_configured"
        else:
            backup_path = backup_dir / latest["filename"]
            try:
                resolved = resolve_confined_path(backup_dir, latest["filename"])
                checks["path_confined"] = True
            except ValueError:
                checks["path_confined"] = False
                findings.append("path_not_confined")
                resolved = backup_path
            mode = resolved.stat().st_mode if resolved.exists() else 0
            world_writable = bool(mode & 0o002)
            checks["world_writable"] = world_writable
            if world_writable:
                findings.append("backup_file_world_writable")
            # Informational only (Phase 15A Step 19-21): whether the
            # latest backup has an encrypted sibling never fails this
            # check by itself -- encryption readiness is assessed and
            # gated separately by ProductionBackupEncryptionAssessmentService.
            _, meta_path = encrypted_backup_paths(backup_dir, latest["filename"])
            checks["encrypted_sidecar_present"] = meta_path.exists()
            result_status = "failed" if (
                not checks.get("path_confined", True) or world_writable
            ) else "passed"

        recorded = self.repository.add_artifact_security_check(
            {
                "artifact_type": "backup",
                "artifact_reference": (latest or {}).get("filename", "none"),
                "result_status": result_status,
                "checks": checks,
                "findings": findings,
                "created_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="check_backup", actor_reference=admin_id,
            resource_public_id=recorded["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return recorded

    def check_rag_release_candidate_artifact(
        self, rag_release_candidate_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        candidate = self.repository.get_rag_release_candidate(rag_release_candidate_public_id)
        findings: list[str] = []
        checks: dict[str, Any] = {
            "index_checksum_present": bool(candidate.get("index_checksum_sha256")),
            "chunk_checksum_present": bool(candidate.get("chunk_checksum_set_hash")),
        }
        if not checks["index_checksum_present"]:
            findings.append("index_checksum_missing")
        if not checks["chunk_checksum_present"]:
            findings.append("chunk_checksum_missing")
        result_status = "passed" if not findings else "failed"

        recorded = self.repository.add_artifact_security_check(
            {
                "artifact_type": "rag_index",
                "artifact_reference": rag_release_candidate_public_id,
                "result_status": result_status,
                "checks": checks,
                "findings": findings,
                "created_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="check_rag_index", actor_reference=admin_id,
            resource_public_id=recorded["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return recorded


__all__ = ["ProductionArtifactSecurityService"]
