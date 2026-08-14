"""Automated backup-encryption CLI.

Encrypts the latest plaintext database backup, verifies the encrypted
copy is genuinely restorable via a full isolated restore drill (decrypt
into a temp dir, open as a real SQLite database, run PRAGMA
integrity_check), and only then deletes the plaintext original.

This exists because `ProductionBackupEncryptionService.encrypt_latest_backup`
is otherwise only reachable through an authenticated admin API call or an
Admin Assistant chat action -- there is no automatic path today (Phase 6A
finding). This script closes that gap without modifying the service
itself or any API route: it calls the existing, unmodified service code
directly, the same pattern `backend/admin_cli.py` already uses for
admin-account management.

Never deletes anything unless verify_encrypted_restore() reports
result_status == "passed". A failed or blocked verification leaves both
the plaintext original and any partial encrypted output in place and
exits non-zero, so a human notices instead of silently losing backup
coverage. Idempotent across repeated runs: encrypted files never match
the plaintext backup glob (`brud_ai_before_v*_*.db`), so a second run
after a successful encrypt+delete simply finds the next-newest plaintext
backup, if any, or reports nothing to do.

Intended to run periodically (e.g. via a systemd timer) after the app's
own auto-backup mechanism has produced a new plaintext backup. Requires
the backup-encryption key to already be configured (the environment
variable named by Settings.backup_encryption_key_env_var) -- this script
never generates or stores a key itself.
"""

import sys

from backend.core.config import get_settings
from backend.database.repositories.base import ValidationError
from backend.services.production_backup_restore_readiness_service import (
    ProductionBackupEncryptionService,
)

_SYSTEM_ACTOR = "system-automated-backup-encryption"


def run() -> int:
    settings = get_settings()
    service = ProductionBackupEncryptionService(settings)

    try:
        encrypt_result = service.encrypt_latest_backup(admin_id=_SYSTEM_ACTOR)
    except ValidationError as exc:
        message = str(exc)
        if "no backup is present" in message:
            print("no plaintext backup present -- nothing to encrypt")
            return 0
        print(f"backup encryption failed: {exc}", file=sys.stderr)
        return 1

    source_filename = encrypt_result["source_filename"]
    print(f"encrypted {source_filename} -> {encrypt_result['encrypted_filename']}")

    verify_result = service.verify_encrypted_restore(admin_id=_SYSTEM_ACTOR)
    if verify_result["result_status"] != "passed":
        print(
            "encrypted backup failed isolated restore verification -- "
            f"status={verify_result['result_status']} findings={verify_result['findings']}. "
            "Plaintext original NOT deleted.",
            file=sys.stderr,
        )
        return 1

    backup_path = settings.resolved_backup_dir / source_filename
    backup_path.unlink()
    print(f"verified encrypted backup is restorable; deleted plaintext original {source_filename}")
    return 0


def main(argv: list[str] | None = None) -> int:
    del argv  # no arguments -- this command does exactly one thing
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
