"""Phase 15 Step 24 / Phase 15A Steps 2-4: full regression, run in
bounded, targeted batches -- either admin-composed (`create_run`, legacy
Phase 15 shape, unchanged) or resolved from the checked-in, checksum-
verified canonical manifest (`create_manifest_run`/`execute_registered_batch`,
Phase 15A).

A broad, unbounded `pytest tests/` invocation has repeatedly been
killed by this sandboxed environment with zero output during this
project (see docs/production/phase15_text_nlp_production_readiness_plan.md)
-- this service therefore never runs one. Every batch has its own
bounded timeout; a batch that cannot complete within it is recorded as
`environment_incomplete`, never silently dropped or reported as a
pass or a genuine failure -- this is the "environment-failure
separation" the spec requires.

The canonical-manifest path never accepts an admin-supplied command or
argument: `execute_registered_batch()` only ever resolves a `batch_id`
against the manifest file loaded from disk (re-validated, checksum and
all, on every single call -- a modified manifest is rejected even if a
run was created before the edit) and executes exactly the command that
was checked into `config/production_regression_manifest.json`, with the
sole substitution of the literal token `${PYTHON}` for `sys.executable`.
No `shell=True`, no string interpolation, no admin-controlled argv entry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from core_model.release.artifact_inventory import resolve_confined_path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST_PATH = _REPO_ROOT / "config" / "production_regression_manifest.json"
_TESTS_ROOT = (_REPO_ROOT / "tests").resolve()
_PASSED_RE = re.compile(r"(\d+) passed")
_FAILED_RE = re.compile(r"(\d+) failed")
_ERROR_RE = re.compile(r"(\d+) error")

REQUIRED_MANIFEST_CATEGORIES = frozenset(
    {
        "database_migrations", "database_integrity", "database_repositories",
        "backend_services", "backend_api", "core_model", "rag", "training",
        "model_registry", "production_readiness", "admin_assistant", "security",
        "frontend_unit", "frontend_build", "browser_e2e", "static_analysis",
        "secret_scan", "forbidden_write_scan",
    }
)
_REQUIRED_MANIFEST_KEYS = (
    "manifest_version", "name", "description", "created_at", "updated_at",
    "required_environment", "batches", "finalization_policy", "manifest_checksum_sha256",
)
_REQUIRED_BATCH_KEYS = (
    "batch_id", "title", "category", "working_directory", "command", "timeout_seconds",
    "required", "retry_policy", "expected_artifacts", "failure_classification_rules",
)
_SECRET_LOG_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
)
_MAX_RAW_SUMMARY_BYTES = 4000

_RUN_LOCKS: dict[str, threading.Lock] = {}
_RUN_LOCKS_GUARD = threading.Lock()


def _run_lock(regression_run_public_id: str) -> threading.Lock:
    """One in-process lock per regression run, so two concurrent requests
    can never execute two batches for the same run at once. Process-local
    only (matches this single-worker dev deployment); a multi-worker
    production deployment would need a DB-level lock, out of scope here."""

    with _RUN_LOCKS_GUARD:
        return _RUN_LOCKS.setdefault(regression_run_public_id, threading.Lock())


def _parse_pytest_summary(output: str) -> tuple[int, int, int]:
    passed = int(m.group(1)) if (m := _PASSED_RE.search(output)) else 0
    failed = int(m.group(1)) if (m := _FAILED_RE.search(output)) else 0
    error = int(m.group(1)) if (m := _ERROR_RE.search(output)) else 0
    return passed, failed, error


def _redact_and_bound(output: str) -> str:
    for pattern in _SECRET_LOG_PATTERNS:
        output = pattern.sub("[REDACTED]", output)
    return output[-_MAX_RAW_SUMMARY_BYTES:]


def compute_manifest_checksum(manifest: dict[str, Any]) -> str:
    payload = {k: v for k, v in manifest.items() if k != "manifest_checksum_sha256"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_manifest_schema(manifest: dict[str, Any]) -> list[str]:
    """Pure structural validation -- returns a list of problems, empty if valid."""

    problems: list[str] = []
    for key in _REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            problems.append(f"missing required top-level key: {key!r}")
    batches = manifest.get("batches")
    if not isinstance(batches, list) or not batches:
        problems.append("'batches' must be a non-empty list")
        return problems

    seen_ids: set[str] = set()
    seen_categories: set[str] = set()
    for entry in batches:
        if not isinstance(entry, dict):
            problems.append("every batch entry must be an object")
            continue
        for key in _REQUIRED_BATCH_KEYS:
            if key not in entry:
                problems.append(f"batch missing required key {key!r}: {entry.get('batch_id')!r}")
        batch_id = entry.get("batch_id")
        if batch_id in seen_ids:
            problems.append(f"duplicate batch_id: {batch_id!r}")
        elif batch_id:
            seen_ids.add(batch_id)
        category = entry.get("category")
        if category is not None:
            seen_categories.add(category)
        if category not in REQUIRED_MANIFEST_CATEGORIES:
            problems.append(f"unknown category {category!r} for batch {batch_id!r}")
        command = entry.get("command")
        if not isinstance(command, list) or not command:
            problems.append(f"batch {batch_id!r} command must be a non-empty list")

    missing_categories = REQUIRED_MANIFEST_CATEGORIES - seen_categories
    if missing_categories:
        problems.append(f"manifest is missing required categories: {sorted(missing_categories)}")
    return problems


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
                event_type=f"production_regression_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_regression_run",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("production_regression_audit_write_failed", extra={"action": action})


class ProductionRegressionService:
    def __init__(self, settings: Settings, *, manifest_path: Path | None = None) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._manifest_path = manifest_path or _DEFAULT_MANIFEST_PATH
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    # -- canonical manifest (Phase 15A) --------------------------------------------------------

    def load_manifest(self) -> dict[str, Any]:
        if not self._manifest_path.exists():
            raise NotFoundError(f"canonical regression manifest not found: {self._manifest_path}")
        try:
            manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"canonical regression manifest is not valid JSON: {exc}"
            ) from exc

        problems = validate_manifest_schema(manifest)
        if problems:
            raise ValidationError(
                "canonical regression manifest failed schema validation: " + "; ".join(problems)
            )
        stored_checksum = manifest.get("manifest_checksum_sha256")
        recomputed = compute_manifest_checksum(manifest)
        if stored_checksum != recomputed:
            raise ValidationError(
                "canonical regression manifest checksum mismatch -- the file on disk does not "
                "match its own recorded checksum and cannot be trusted"
            )
        return manifest

    def list_registered_batches(self) -> list[dict[str, Any]]:
        return self.load_manifest()["batches"]

    def get_registered_batch(self, batch_id: str) -> dict[str, Any]:
        for batch in self.list_registered_batches():
            if batch["batch_id"] == batch_id:
                return batch
        raise NotFoundError(f"unregistered batch_id: {batch_id!r}")

    def create_manifest_run(self, *, admin_id: str) -> dict[str, Any]:
        manifest = self.load_manifest()
        binding = {
            "manifest_version": manifest["manifest_version"],
            "manifest_checksum_sha256": manifest["manifest_checksum_sha256"],
            "batch_ids": [b["batch_id"] for b in manifest["batches"]],
            "required_batch_ids": [b["batch_id"] for b in manifest["batches"] if b["required"]],
        }
        run = self.create_run([binding], admin_id=admin_id)
        _audit(
            self._audit, action="create_manifest_run", actor_reference=admin_id,
            resource_public_id=run["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"manifest_checksum_sha256": manifest["manifest_checksum_sha256"]},
        )
        return run

    def _run_manifest_binding(self, regression_run_public_id: str) -> dict[str, Any]:
        run = self.repository.get_regression_run(regression_run_public_id)
        batch_plan = run["batch_plan"]
        if not isinstance(batch_plan, list) or not batch_plan or "manifest_checksum_sha256" not in (
            batch_plan[0] if batch_plan else {}
        ):
            raise ValidationError(
                "this regression run was not created from the canonical manifest "
                "(use create_manifest_run() first)"
            )
        return batch_plan[0]

    def execute_registered_batch(
        self, regression_run_public_id: str, batch_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        binding = self._run_manifest_binding(regression_run_public_id)
        manifest = self.load_manifest()
        if manifest["manifest_checksum_sha256"] != binding["manifest_checksum_sha256"]:
            raise ValidationError(
                "the canonical regression manifest has changed since this run was created -- "
                "create a fresh manifest run"
            )
        if batch_id not in binding["batch_ids"]:
            raise ValidationError(f"batch_id {batch_id!r} is not part of this run's manifest")

        lock = _run_lock(regression_run_public_id)
        if not lock.acquire(blocking=False):
            raise ValidationError(
                "another batch is already executing for this regression run -- only one "
                "batch may run at a time per run"
            )
        try:
            batch = self.get_registered_batch(batch_id)
            resolved_command = [
                sys.executable if token == "${PYTHON}" else token for token in batch["command"]
            ]
            working_directory = (_REPO_ROOT / batch["working_directory"]).resolve()
            rules = batch["failure_classification_rules"]
            started = time.perf_counter()
            try:
                proc = subprocess.run(  # noqa: S603 -- argv comes only from the verified manifest
                    resolved_command, cwd=working_directory, capture_output=True, text=True,
                    timeout=batch["timeout_seconds"], check=False,
                )
                duration = time.perf_counter() - started
                output = proc.stdout + proc.stderr
                passed, failed, error = _parse_pytest_summary(output)
                if proc.returncode in rules.get("passed_if_exit_code_in", [0]):
                    status = "passed"
                elif proc.returncode in rules.get("environment_failed_if_exit_code_in", []):
                    status = "environment_incomplete"
                else:
                    status = "failed"
                raw_summary = _redact_and_bound(output)
            except subprocess.TimeoutExpired:
                duration = float(batch["timeout_seconds"])
                passed, failed, error = 0, 0, 0
                status = "environment_incomplete"
                raw_summary = f"batch timed out after {batch['timeout_seconds']}s"

            result = self.repository.add_regression_result(
                regression_run_public_id,
                {
                    "batch_name": f"{batch['category']}:{batch['batch_id']}",
                    "command": " ".join(resolved_command),
                    "status": status,
                    "passed_count": passed,
                    "failed_count": failed,
                    "error_count": error,
                    "duration_seconds": duration,
                    "raw_summary": raw_summary,
                },
            )
        finally:
            lock.release()

        _audit(
            self._audit, action="execute_registered_batch", actor_reference=admin_id,
            resource_public_id=result["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"status": status, "batch_id": batch_id, "category": batch["category"]},
        )
        return result

    def finalize_manifest_run(
        self, regression_run_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        binding = self._run_manifest_binding(regression_run_public_id)
        results = self.repository.list_regression_results(regression_run_public_id)
        by_batch = {}
        for result in results:
            batch_id = result["batch_name"].split(":", 1)[-1]
            by_batch[batch_id] = result

        required_ids = binding["required_batch_ids"]
        missing = [batch_id for batch_id in required_ids if batch_id not in by_batch]
        failed_ids = [
            batch_id for batch_id in required_ids
            if batch_id in by_batch and by_batch[batch_id]["status"] == "failed"
        ]
        environment_incomplete_ids = [
            batch_id for batch_id in required_ids
            if batch_id in by_batch and by_batch[batch_id]["status"] == "environment_incomplete"
        ]

        if missing:
            fine_status = "blocked"
        elif failed_ids:
            fine_status = "failed"
        elif environment_incomplete_ids:
            fine_status = "passed_with_environment_limitations"
        else:
            fine_status = "passed"

        db_status = {
            "passed": "completed",
            "passed_with_environment_limitations": "environment_incomplete",
            "failed": "completed_with_failures",
            "blocked": "environment_incomplete",
        }[fine_status]
        run = self.repository.update_regression_run_status(regression_run_public_id, db_status)

        self.repository.record_readiness_event(
            {
                "event_type": "canonical_regression_finalized",
                "resource_type": "production_regression_run",
                "resource_public_id": regression_run_public_id,
                "summary": f"result_status={fine_status}",
                "metadata": {
                    "fine_status": fine_status,
                    "missing_required_batch_ids": missing,
                    "failed_required_batch_ids": failed_ids,
                    "environment_incomplete_required_batch_ids": environment_incomplete_ids,
                    "manifest_checksum_sha256": binding["manifest_checksum_sha256"],
                    "manifest_version": binding["manifest_version"],
                },
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="finalize_manifest_run", actor_reference=admin_id,
            resource_public_id=regression_run_public_id, outcome=AuditOutcome.SUCCESS,
            metadata={"fine_status": fine_status, "missing": missing, "failed": failed_ids},
        )
        return {**run, "fine_status": fine_status, "missing_required_batch_ids": missing}

    def create_run(self, batch_plan: list[dict[str, Any]], *, admin_id: str) -> dict[str, Any]:
        if not batch_plan:
            raise ValidationError("a regression run requires at least one batch")
        run = self.repository.create_regression_run(
            {
                "run_code": f"REG-{uuid4().hex[:16]}",
                "batch_plan": batch_plan,
                "created_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="create_run", actor_reference=admin_id,
            resource_public_id=run["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"batch_count": len(batch_plan)},
        )
        return run

    def execute_batch(
        self,
        regression_run_public_id: str,
        batch_name: str,
        test_paths: list[str],
        *,
        admin_id: str,
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        # Security: this legacy path (unlike the checksum-verified manifest path
        # above) takes admin-supplied test_paths directly. Each entry is resolved
        # and confined to `tests/` via resolve_confined_path() -- rejecting
        # absolute paths, `..` escapes, and anything outside `tests/` -- so an
        # admin session cannot smuggle a flag-like argv entry or point pytest at
        # an arbitrary file with side-effecting conftest.py code. shell=True is
        # never used.
        for entry in test_paths:
            resolved = resolve_confined_path(_REPO_ROOT, entry)
            if not resolved.is_relative_to(_TESTS_ROOT):
                raise ValueError(f"test path '{entry}' must resolve under tests/")
        command = [sys.executable, "-m", "pytest", *test_paths, "-q"]
        started = time.perf_counter()
        try:
            proc = subprocess.run(  # noqa: S603 -- fixed interpreter + confined, validated test paths only
                command, cwd=_REPO_ROOT, capture_output=True, text=True,
                timeout=timeout_seconds, check=False,
            )
            duration = time.perf_counter() - started
            output = proc.stdout + proc.stderr
            passed, failed, error = _parse_pytest_summary(output)
            status = "passed" if proc.returncode == 0 else "failed"
            raw_summary = output[-4000:]
        except subprocess.TimeoutExpired:
            duration = float(timeout_seconds)
            passed, failed, error = 0, 0, 0
            status = "environment_incomplete"
            raw_summary = f"batch timed out after {timeout_seconds}s"

        result = self.repository.add_regression_result(
            regression_run_public_id,
            {
                "batch_name": batch_name,
                "command": " ".join(command),
                "status": status,
                "passed_count": passed,
                "failed_count": failed,
                "error_count": error,
                "duration_seconds": duration,
                "raw_summary": raw_summary,
            },
        )
        _audit(
            self._audit, action="execute_batch", actor_reference=admin_id,
            resource_public_id=result["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"status": status, "batch_name": batch_name},
        )
        return result

    def finalize_run(self, regression_run_public_id: str, *, admin_id: str) -> dict[str, Any]:
        results = self.repository.list_regression_results(regression_run_public_id)
        if not results:
            raise ValidationError("cannot finalize a regression run with no batch results")
        if any(r["status"] == "environment_incomplete" for r in results):
            status = "environment_incomplete"
        elif any(r["status"] == "failed" for r in results):
            status = "completed_with_failures"
        else:
            status = "completed"
        run = self.repository.update_regression_run_status(regression_run_public_id, status)
        _audit(
            self._audit, action="finalize_run", actor_reference=admin_id,
            resource_public_id=regression_run_public_id, outcome=AuditOutcome.SUCCESS,
            metadata={"status": status},
        )
        return run


__all__ = [
    "REQUIRED_MANIFEST_CATEGORIES",
    "ProductionRegressionService",
    "compute_manifest_checksum",
    "validate_manifest_schema",
]
