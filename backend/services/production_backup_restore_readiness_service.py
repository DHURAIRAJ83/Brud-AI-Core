"""Phase 15 Steps 20-21: backup and restore readiness, extended by
Phase 15A Steps 14-18 with backup-encryption assessment and governed
encryption.

Reuses the *existing, unmodified* backup/database-status mechanics
(`backend.api.routes.system._latest_backup`, `database_connection`,
`migration_status`, `PRAGMA integrity_check`) rather than building a
parallel backup or restore system. The restore drill copies the
latest backup into an isolated temporary directory and verifies it
there -- it never touches the live database and never performs an
actual restore. See
docs/production/phase15_text_nlp_production_readiness_plan.md and
docs/production/phase15a_production_verification_plan.md.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import shutil
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.api.routes.system import _latest_backup
from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.connection import database_connection
from backend.database.migrations import migration_status, sha256_file
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome

logger = logging.getLogger(__name__)

_ENCRYPTION_FORMAT_VERSION = 1
_ENCRYPTION_ALGORITHM = "AES-256-GCM"
_NONCE_BYTES = 12

# Phase 15A Step 32: one process-local lock per backup directory, so two
# concurrent encrypt/verify-restore calls against the *same* backup
# directory can never interleave writes to the same `.enc`/`.enc.meta.json`
# pair (which could otherwise pair one attempt's ciphertext with another
# attempt's nonce/checksum metadata). Mirrors the identical pattern
# already used for canonical regression batch execution
# (`production_regression_service._run_lock`). Process-local only; a
# multi-worker production deployment would need a filesystem or DB-level
# lock, out of scope here.
_BACKUP_ENCRYPTION_LOCKS: dict[str, threading.Lock] = {}
_BACKUP_ENCRYPTION_LOCKS_GUARD = threading.Lock()


def _backup_encryption_lock(backup_dir: Path) -> threading.Lock:
    key = str(backup_dir.resolve())
    with _BACKUP_ENCRYPTION_LOCKS_GUARD:
        return _BACKUP_ENCRYPTION_LOCKS.setdefault(key, threading.Lock())


def _load_encryption_key(settings: Settings) -> bytes:
    """Reads the encryption key from the environment variable named by
    `settings.backup_encryption_key_env_var` -- never from the database,
    never from a request payload. Fails closed (raises) rather than
    falling back to any plaintext path if the key is missing or
    malformed.
    """
    key_env_var = settings.backup_encryption_key_env_var
    raw = os.environ.get(key_env_var)
    if not raw:
        raise ValidationError(
            f"backup encryption key is not present in the {key_env_var} environment variable"
        )
    try:
        key = base64.urlsafe_b64decode(raw)
    except Exception as exc:
        raise ValidationError(f"{key_env_var} does not hold a valid base64-encoded key") from exc
    if len(key) != 32:
        raise ValidationError(f"{key_env_var} must decode to a 32-byte (256-bit) AES-GCM key")
    return key


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
                event_type=f"production_backup_restore_readiness_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_backup_readiness_check",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "production_backup_restore_readiness_audit_write_failed", extra={"action": action}
        )


class ProductionBackupReadinessService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def check_backup_readiness(
        self, *, admin_id: str, max_age_seconds: int | None = None
    ) -> dict[str, Any]:
        backup_dir = self.settings.resolved_backup_dir
        latest = _latest_backup(backup_dir) if backup_dir.exists() else None
        details: dict[str, Any] = {"auto_backup_enabled": self.settings.database_auto_backup}
        findings: list[str] = []

        if latest is None:
            result_status = "not_configured"
            findings.append("no_backup_present")
            age_seconds = None
        else:
            created_at = datetime.fromisoformat(latest["created_at"])
            age_seconds = int((datetime.now(UTC) - created_at).total_seconds())
            details["latest_backup_filename"] = latest["filename"]
            details["latest_backup_age_seconds"] = age_seconds
            if not self.settings.database_auto_backup:
                findings.append("auto_backup_disabled")
            if max_age_seconds is not None and age_seconds > max_age_seconds:
                findings.append("latest_backup_stale")
            result_status = (
                "failed" if "latest_backup_stale" in findings
                else "passed_with_warning" if findings
                else "passed"
            )

        recorded = self.repository.add_backup_readiness_check(
            {
                "check_type": "backup",
                "result_status": result_status,
                "latest_backup_filename": (latest or {}).get("filename"),
                "latest_backup_age_seconds": age_seconds,
                "details": {**details, "findings": findings},
                "created_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="check_backup", actor_reference=admin_id,
            resource_public_id=recorded["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return recorded


class ProductionRestoreReadinessService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def check_restore_readiness(self, *, admin_id: str) -> dict[str, Any]:
        backup_dir = self.settings.resolved_backup_dir
        latest = _latest_backup(backup_dir) if backup_dir.exists() else None
        details: dict[str, Any] = {}
        findings: list[str] = []

        if latest is None:
            result_status = "not_configured"
            findings.append("no_backup_present")
        else:
            source = backup_dir / latest["filename"]
            with tempfile.TemporaryDirectory(prefix="brud_restore_drill_") as drill_dir:
                drill_path = Path(drill_dir) / "restore_drill.db"
                shutil.copy2(source, drill_path)
                try:
                    with database_connection(drill_path) as connection:
                        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                    status = migration_status(drill_path)
                    details["integrity_check"] = integrity
                    details["schema_version"] = status["current_version"]
                    if integrity != "ok":
                        findings.append("restored_copy_failed_integrity_check")
                    if not status["current_version"]:
                        findings.append("restored_copy_has_no_schema_version")
                except Exception as exc:  # noqa: BLE001 -- isolated drill, any failure is a finding
                    findings.append(f"restore_drill_raised: {exc}")
                    details["exception"] = str(exc)
            result_status = "failed" if findings else "passed"

        recorded = self.repository.add_backup_readiness_check(
            {
                "check_type": "restore",
                "result_status": result_status,
                "latest_backup_filename": (latest or {}).get("filename"),
                "details": {**details, "findings": findings},
                "created_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="check_restore", actor_reference=admin_id,
            resource_public_id=recorded["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return recorded


def encrypted_backup_paths(backup_dir: Path, filename: str) -> tuple[Path, Path]:
    """Naming convention for a backup's encrypted sibling and its sidecar
    metadata file, shared by the assessment (Step 14), the encryption
    service (Step 15-16), and the isolated restore-verification service
    (Step 17-18) so all three agree on the same on-disk layout.
    """
    return backup_dir / f"{filename}.enc", backup_dir / f"{filename}.enc.meta.json"


class ProductionBackupEncryptionService:
    """Phase 15A Steps 15-16: governed backup encryption. Encrypts the
    latest already-existing plaintext backup (this service never creates
    a new backup itself -- backups are already produced by the existing
    migration/auto-backup mechanism in `backend.database.migrations`)
    using AES-256-GCM with a key read from the environment variable named
    by `Settings.backup_encryption_key_env_var`. The key is held in
    memory only for the duration of a single encrypt/decrypt call, never
    logged, never returned by any API, and never written to the
    database -- only the environment variable's *name* is ever recorded.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def encrypt_latest_backup(self, *, admin_id: str) -> dict[str, Any]:
        backup_dir = self.settings.resolved_backup_dir
        latest = _latest_backup(backup_dir) if backup_dir.exists() else None
        if latest is None:
            raise ValidationError("no backup is present to encrypt")

        lock = _backup_encryption_lock(backup_dir)
        if not lock.acquire(blocking=False):
            raise ValidationError(
                "another backup-encryption operation is already running for this backup "
                "directory -- only one may run at a time"
            )
        try:
            backup_path = backup_dir / latest["filename"]
            key = _load_encryption_key(self.settings)
            source_checksum = sha256_file(backup_path)
            plaintext = backup_path.read_bytes()
            nonce = os.urandom(_NONCE_BYTES)
            ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
            del plaintext, key

            encrypted_path, meta_path = encrypted_backup_paths(backup_dir, latest["filename"])
            encrypted_path.write_bytes(ciphertext)
            encrypted_checksum = hashlib.sha256(ciphertext).hexdigest()
            meta = {
                "format_version": _ENCRYPTION_FORMAT_VERSION,
                "algorithm": _ENCRYPTION_ALGORITHM,
                "key_reference": self.settings.backup_encryption_key_env_var,
                "created_at": datetime.now(UTC).isoformat(),
                "source_artifact_type": "backup",
                "source_filename": latest["filename"],
                "source_checksum": source_checksum,
                "encrypted_checksum": encrypted_checksum,
                "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
            }
            meta_path.write_text(dumps_json(meta), encoding="utf-8")
        finally:
            lock.release()

        event = self.repository.record_readiness_event(
            {
                "event_type": "encrypted_backup_created",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"encrypted {latest['filename']}",
                "metadata": {
                    "source_filename": latest["filename"],
                    "encrypted_filename": encrypted_path.name,
                    "algorithm": _ENCRYPTION_ALGORITHM,
                    "key_reference_env_var": self.settings.backup_encryption_key_env_var,
                    "source_checksum": source_checksum,
                    "encrypted_checksum": encrypted_checksum,
                },
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="encrypt_backup", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"source_filename": latest["filename"]},
        )
        return {
            "result_status": "encrypted",
            "source_filename": latest["filename"],
            "encrypted_filename": encrypted_path.name,
            "source_checksum": source_checksum,
            "encrypted_checksum": encrypted_checksum,
            "event": event,
        }

    def decrypt_backup(
        self, backup_dir: Path, source_filename: str
    ) -> tuple[bytes, dict[str, Any]]:
        """Decrypts an encrypted backup and verifies both its ciphertext
        and plaintext checksums against the sidecar metadata. Returns
        `(plaintext_bytes, meta)`. Always fails closed (raises
        `ValidationError`) on any missing file, wrong key, corrupted
        ciphertext, or checksum mismatch -- never returns partial or
        unverified plaintext. Callers (e.g. the isolated restore
        verification in Step 17-18) are responsible for writing the
        returned bytes only into an isolated temporary location, never
        the live database path.
        """
        encrypted_path, meta_path = encrypted_backup_paths(backup_dir, source_filename)
        if not encrypted_path.exists() or not meta_path.exists():
            raise ValidationError("no encrypted backup is present for this source filename")

        meta = loads_json(meta_path.read_text(encoding="utf-8"), default={})
        key = _load_encryption_key(self.settings)
        nonce = base64.urlsafe_b64decode(meta["nonce"])
        ciphertext = encrypted_path.read_bytes()

        encrypted_checksum = hashlib.sha256(ciphertext).hexdigest()
        if encrypted_checksum != meta.get("encrypted_checksum"):
            raise ValidationError(
                "encrypted backup checksum mismatch -- ciphertext may be corrupted"
            )

        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise ValidationError(
                "decryption failed -- wrong key or corrupted/tampered ciphertext"
            ) from exc
        finally:
            del key

        plaintext_checksum = hashlib.sha256(plaintext).hexdigest()
        if plaintext_checksum != meta.get("source_checksum"):
            raise ValidationError(
                "decrypted backup checksum does not match the original source checksum"
            )
        return plaintext, meta

    def verify_encrypted_restore(self, *, admin_id: str) -> dict[str, Any]:
        """Phase 15A Steps 17-18: fully isolated encrypted-restore drill.
        Decrypts the latest encrypted backup into a brand-new
        `tempfile.TemporaryDirectory()`, opens *that* copy with its own
        `sqlite3` connection, runs the same integrity checks the
        plaintext restore drill already uses, and deletes the temp
        directory (including the decrypted plaintext) once the `with`
        block exits -- on success or failure alike. The live database
        and the real backup files are never opened for write; only the
        isolated copy is ever touched.
        """
        backup_dir = self.settings.resolved_backup_dir
        latest = _latest_backup(backup_dir) if backup_dir.exists() else None
        details: dict[str, Any] = {}
        findings: list[str] = []

        if latest is None:
            result_status = "not_configured"
            findings.append("no_backup_present")
        else:
            encrypted_path, meta_path = encrypted_backup_paths(backup_dir, latest["filename"])
            if not encrypted_path.exists() or not meta_path.exists():
                result_status = "not_configured"
                findings.append("latest_backup_not_encrypted")
            else:
                lock = _backup_encryption_lock(backup_dir)
                if not lock.acquire(blocking=False):
                    findings.append(
                        "decrypt_failed: another backup-encryption operation is already "
                        "running for this backup directory"
                    )
                    result_status = "blocked"
                    plaintext = None
                else:
                    try:
                        plaintext, _meta = self.decrypt_backup(backup_dir, latest["filename"])
                    except ValidationError as exc:
                        findings.append(f"decrypt_failed: {exc}")
                        result_status = "blocked"
                        plaintext = None
                    finally:
                        lock.release()

                if plaintext is not None:
                    drill_prefix = "brud_encrypted_restore_drill_"
                    with tempfile.TemporaryDirectory(prefix=drill_prefix) as drill_dir:
                        drill_path = Path(drill_dir) / "encrypted_restore_drill.db"
                        drill_path.write_bytes(plaintext)
                        del plaintext
                        try:
                            with database_connection(drill_path) as connection:
                                integrity = connection.execute(
                                    "PRAGMA integrity_check"
                                ).fetchone()[0]
                            status = migration_status(drill_path)
                            details["integrity_check"] = integrity
                            details["schema_version"] = status["current_version"]
                            if integrity != "ok":
                                findings.append("decrypted_copy_failed_integrity_check")
                            if not status["current_version"]:
                                findings.append("decrypted_copy_has_no_schema_version")
                        except Exception as exc:  # noqa: BLE001 -- isolated drill, any failure is a finding
                            findings.append(f"encrypted_restore_drill_raised: {exc}")
                            details["exception"] = str(exc)
                    result_status = "failed" if findings else "passed"

        event = self.repository.record_readiness_event(
            {
                "event_type": "encrypted_restore_verified",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"result_status={result_status}",
                "metadata": {
                    "details": details, "findings": findings,
                    "latest_backup_filename": (latest or {}).get("filename"),
                },
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="verify_encrypted_restore", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return {
            "result_status": result_status, "details": details, "findings": findings,
            "event": event,
        }


class ProductionBackupEncryptionAssessmentService:
    """Phase 15A Step 14: an honest, read-only assessment of whether the
    latest backup is encrypted at rest. Never encrypts, decrypts, or
    modifies anything -- see ProductionBackupEncryptionService (Step
    15-16) for the governed encryption capability this assessment
    reports on. Absence of evidence (no sidecar, no key present) is
    always reported as `not_encrypted`/`not_configured`, never guessed
    or assumed to be `encrypted`.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def assess(self, *, admin_id: str) -> dict[str, Any]:
        backup_dir = self.settings.resolved_backup_dir
        latest = _latest_backup(backup_dir) if backup_dir.exists() else None
        key_env_var = self.settings.backup_encryption_key_env_var
        key_present = bool(os.environ.get(key_env_var))

        checks: dict[str, Any] = {
            # `cryptography` is a hard pyproject.toml dependency (Phase
            # 15A) -- the library itself is always available; whether it
            # is actually *used* for the latest backup is the separate,
            # per-backup check below.
            "encryption_library_available": True,
            "key_reference_configured": bool(key_env_var),
            "key_present_in_environment": key_present,
        }
        findings: list[str] = []
        if not key_present:
            findings.append("no_encryption_key_present_in_environment")

        if latest is None:
            result_status = "not_configured"
            findings.append("no_backup_present")
            sidecar_present = False
        else:
            _, meta_path = encrypted_backup_paths(backup_dir, latest["filename"])
            sidecar_present = meta_path.exists()
            checks["latest_backup_has_encrypted_sidecar"] = sidecar_present
            if not sidecar_present:
                findings.append("latest_backup_not_encrypted")
            result_status = "encrypted" if sidecar_present and key_present else "not_encrypted"

        event = self.repository.record_readiness_event(
            {
                "event_type": "backup_encryption_assessed",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"result_status={result_status}",
                "metadata": {
                    "checks": checks, "findings": findings,
                    "key_reference_env_var": key_env_var,
                    "latest_backup_filename": (latest or {}).get("filename"),
                },
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="assess_encryption", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return {
            "result_status": result_status, "checks": checks, "findings": findings, "event": event,
        }


__all__ = [
    "ProductionBackupReadinessService",
    "ProductionRestoreReadinessService",
    "ProductionBackupEncryptionAssessmentService",
    "ProductionBackupEncryptionService",
    "encrypted_backup_paths",
]
