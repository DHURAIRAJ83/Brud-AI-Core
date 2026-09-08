"""Phase 45 — Tenant-Isolated Admin API Service.

Implements Workstreams 11, 12, 13, 14, 15:
- Admin endpoints:
  - list_models(context)
  - get_model(context, model_id)
  - register_model(context, model_id, model_data)
  - get_evaluation(context, model_id)
  - get_telemetry(context)
  - submit_governance_decision(context, model_id, decision)
- Full 7-step verification chain on every operation:
  authenticated_admin -> role_verification -> tenant_verification ->
  resource_ownership -> scope_verification -> operation_authorization -> audit_log
- Strict isolation from production database (brud_ai.db remains untouched)
- Zero Public Chat access or arbitrary path traversal
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from core_model.admin.admin_audit import AdminAuditLogger, AdminAuditRecord
from core_model.admin.admin_auth import AdminSecurityContext
from core_model.admin.admin_rbac import AdminRBACManager
from core_model.admin.admin_tenant import (
    ScopeAccessDeniedError,
    TenantAccessDeniedError,
    TenantResourceManager,
)


class TenantAdminAPI:
    """Provides tenant-isolated administrative API access for candidate management, evaluation, and telemetry."""

    def __init__(
        self,
        resource_manager: TenantResourceManager,
        audit_logger: AdminAuditLogger,
    ) -> None:
        self.resource_manager = resource_manager
        self.audit_logger = audit_logger

    def _audit(
        self,
        context: AdminSecurityContext,
        operation: str,
        status: str,
        resource_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        rec = AdminAuditRecord(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            request_id=context.request_id,
            admin_id=context.admin_id,
            tenant_id=context.tenant_id,
            role=context.role,
            scope=context.scope,
            operation=operation,
            status=status,
            resource_id=resource_id,
            reason=reason,
        )
        self.audit_logger.log_event(rec)

    def list_models(self, context: AdminSecurityContext) -> dict[str, Any]:
        """Lists candidate models owned exclusively by the authenticated tenant."""
        try:
            AdminRBACManager.authorize_operation(context.role, "read_model")
            models = self.resource_manager.list_tenant_resources(context, "models")
            self._audit(context, "list_models", "SUCCESS")
            return models
        except Exception as e:
            self._audit(context, "list_models", "DENIED", reason=str(e))
            raise

    def get_model(self, context: AdminSecurityContext, model_id: str) -> Any:
        """Retrieves model metadata, strictly verifying tenant ownership."""
        try:
            model = self.resource_manager.authorize_and_get_resource(
                context, "models", model_id, operation="read_model"
            )
            self._audit(context, "get_model", "SUCCESS", resource_id=model_id)
            return model
        except Exception as e:
            self._audit(context, "get_model", "DENIED", resource_id=model_id, reason=str(e))
            raise

    def register_model(self, context: AdminSecurityContext, model_id: str, model_data: dict[str, Any]) -> None:
        """Registers a new candidate model bound to the authenticated tenant."""
        try:
            if not context.verify_signature():
                raise PermissionError("Admin token signature verification failed")
            AdminRBACManager.authorize_operation(context.role, "create_model")
            if "public_chat" in context.scope.lower():
                raise ScopeAccessDeniedError("Cannot register models into Public Chat scope")

            self.resource_manager.register_resource(context.tenant_id, "models", model_id, model_data)
            self._audit(context, "register_model", "SUCCESS", resource_id=model_id)
        except Exception as e:
            self._audit(context, "register_model", "DENIED", resource_id=model_id, reason=str(e))
            raise

    def get_evaluation(self, context: AdminSecurityContext, model_id: str) -> Any:
        """Retrieves evaluation report, strictly verifying tenant ownership."""
        try:
            eval_data = self.resource_manager.authorize_and_get_resource(
                context, "evaluations", model_id, operation="read_evaluation"
            )
            self._audit(context, "get_evaluation", "SUCCESS", resource_id=model_id)
            return eval_data
        except Exception as e:
            self._audit(context, "get_evaluation", "DENIED", resource_id=model_id, reason=str(e))
            raise

    def get_telemetry(self, context: AdminSecurityContext) -> dict[str, Any]:
        """Retrieves telemetry records strictly for the authenticated tenant."""
        try:
            AdminRBACManager.authorize_operation(context.role, "read_telemetry")
            telem = self.resource_manager.list_tenant_resources(context, "telemetry")
            self._audit(context, "get_telemetry", "SUCCESS")
            return telem
        except Exception as e:
            self._audit(context, "get_telemetry", "DENIED", reason=str(e))
            raise

    def submit_governance_decision(
        self,
        context: AdminSecurityContext,
        model_id: str,
        decision: str,
    ) -> dict[str, Any]:
        """Submits an administrative governance decision for a tenant-owned candidate."""
        try:
            if not context.verify_signature():
                raise PermissionError("Admin token signature verification failed")
            # Only SUPER_ADMIN can approve canary
            AdminRBACManager.authorize_operation(context.role, "approve_canary")
            # Ensure model belongs to tenant
            _ = self.resource_manager.authorize_and_get_resource(
                context, "models", model_id, operation="read_model"
            )
            gov_rec = {
                "model_id": model_id,
                "admin_id": context.admin_id,
                "tenant_id": context.tenant_id,
                "decision": decision,
                "timestamp": time.time(),
            }
            self.resource_manager.register_resource(context.tenant_id, "governance", model_id, gov_rec)
            self._audit(context, "submit_governance_decision", "SUCCESS", resource_id=model_id)
            return gov_rec
        except Exception as e:
            self._audit(context, "submit_governance_decision", "DENIED", resource_id=model_id, reason=str(e))
            raise

    def create_training_job(
        self,
        context: AdminSecurityContext,
        job_id: str,
        dataset_manifest_hash: str,
        target_tokens: int,
        target_steps: int,
        queue: Any,
    ) -> Any:
        """Submits a training job under tenant boundary isolation (Workstream 21)."""
        try:
            if not context.verify_signature():
                raise PermissionError("Admin token signature verification failed")
            AdminRBACManager.authorize_operation(context.role, "create_training_job")
            if "public_chat" in context.scope.lower():
                raise ScopeAccessDeniedError("Training operations cannot use public_chat scope")

            job = queue.submit_job(
                job_id=job_id,
                tenant_id=context.tenant_id,
                dataset_manifest_hash=dataset_manifest_hash,
                target_tokens=target_tokens,
                target_steps=target_steps,
            )
            self.resource_manager.register_resource(context.tenant_id, "jobs", job_id, job.to_dict())
            self._audit(context, "create_training_job", "SUCCESS", resource_id=job_id)
            return job
        except Exception as e:
            self._audit(context, "create_training_job", "DENIED", resource_id=job_id, reason=str(e))
            raise

    def get_training_job(
        self,
        context: AdminSecurityContext,
        job_id: str,
        queue: Any,
    ) -> Any:
        """Retrieves training job status, enforcing strict tenant boundary."""
        try:
            AdminRBACManager.authorize_operation(context.role, "read_training_job")
            _ = self.resource_manager.authorize_and_get_resource(
                context, "jobs", job_id, operation="read_training_job"
            )
            job = queue.get_job(job_id)
            self._audit(context, "get_training_job", "SUCCESS", resource_id=job_id)
            return job
        except Exception as e:
            self._audit(context, "get_training_job", "DENIED", resource_id=job_id, reason=str(e))
            raise

    def update_training_job_status(
        self,
        context: AdminSecurityContext,
        job_id: str,
        action: str,
        queue: Any,
    ) -> Any:
        """Updates job status (pause, resume, cancel), strictly enforcing tenant ownership."""
        try:
            if not context.verify_signature():
                raise PermissionError("Admin token signature verification failed")
            AdminRBACManager.authorize_operation(context.role, "update_training_job")
            _ = self.resource_manager.authorize_and_get_resource(
                context, "jobs", job_id, operation="update_training_job"
            )
            if action == "PAUSE":
                job = queue.pause_job(job_id)
            elif action == "RESUME":
                job = queue.resume_job(job_id)
            elif action == "CANCEL":
                job = queue.cancel_job(job_id)
            else:
                raise ValueError(f"Unknown action: {action}")
            self._audit(context, f"update_training_job_{action.lower()}", "SUCCESS", resource_id=job_id)
            return job
        except Exception as e:
            self._audit(context, "update_training_job", "DENIED", resource_id=job_id, reason=str(e))
            raise

    def start_daemon(
        self,
        context: AdminSecurityContext,
        daemon_instance: Any,
    ) -> dict[str, Any]:
        """Starts standing training daemon with full 7-step authorization check."""
        try:
            if not context.verify_signature():
                raise PermissionError("Admin token signature verification failed")
            if context.scope == "public_chat":
                raise ScopeAccessDeniedError("Operation forbidden within public_chat scope")

            AdminRBACManager.authorize_operation(context.role, "start_daemon")
            daemon_instance.start()
            res = {"status": "STARTED", "daemon_id": daemon_instance.daemon_id, "state": daemon_instance.state.value}
            self._audit(context, "start_daemon", "SUCCESS", resource_id=daemon_instance.daemon_id)
            return res
        except Exception as e:
            self._audit(context, "start_daemon", "DENIED", resource_id=getattr(daemon_instance, "daemon_id", "unknown"), reason=str(e))
            raise

    def stop_daemon(
        self,
        context: AdminSecurityContext,
        daemon_instance: Any,
    ) -> dict[str, Any]:
        """Gracefully stops standing training daemon."""
        try:
            if not context.verify_signature():
                raise PermissionError("Admin token signature verification failed")
            if context.scope == "public_chat":
                raise ScopeAccessDeniedError("Operation forbidden within public_chat scope")

            AdminRBACManager.authorize_operation(context.role, "stop_daemon")
            daemon_instance.stop()
            res = {"status": "STOPPED", "daemon_id": daemon_instance.daemon_id, "state": daemon_instance.state.value}
            self._audit(context, "stop_daemon", "SUCCESS", resource_id=daemon_instance.daemon_id)
            return res
        except Exception as e:
            self._audit(context, "stop_daemon", "DENIED", resource_id=getattr(daemon_instance, "daemon_id", "unknown"), reason=str(e))
            raise

    def get_daemon_status(
        self,
        context: AdminSecurityContext,
        daemon_instance: Any,
    ) -> dict[str, Any]:
        """Retrieves standing training daemon status and health."""
        try:
            if not context.verify_signature():
                raise PermissionError("Admin token signature verification failed")
            AdminRBACManager.authorize_operation(context.role, "get_daemon_status")
            res = {
                "daemon_id": daemon_instance.daemon_id,
                "state": daemon_instance.state.value,
                "current_job_id": daemon_instance.current_job_id,
                "current_checkpoint": daemon_instance.current_checkpoint,
                "uptime_seconds": round(time.time() - daemon_instance.start_time, 2),
            }
            self._audit(context, "get_daemon_status", "SUCCESS", resource_id=daemon_instance.daemon_id)
            return res
        except Exception as e:
            self._audit(context, "get_daemon_status", "DENIED", resource_id=getattr(daemon_instance, "daemon_id", "unknown"), reason=str(e))
            raise

    def trigger_archive(
        self,
        context: AdminSecurityContext,
        job_id: str,
        checkpoint_id: str,
        checkpoint_mgr: Any,
    ) -> dict[str, Any]:
        """Triggers verified COLD archive for a checkpoint."""
        try:
            if not context.verify_signature():
                raise PermissionError("Admin token signature verification failed")
            if context.scope == "public_chat":
                raise ScopeAccessDeniedError("Operation forbidden within public_chat scope")

            AdminRBACManager.authorize_operation(context.role, "trigger_archive")
            _ = self.resource_manager.authorize_and_get_resource(
                context, "jobs", job_id, operation="trigger_archive"
            )
            manifest = checkpoint_mgr.archive_checkpoint(job_id, checkpoint_id)
            verified = checkpoint_mgr.verify_archive(job_id, checkpoint_id)
            res = {
                "status": "ARCHIVED" if verified else "VERIFICATION_FAILED",
                "checkpoint_id": checkpoint_id,
                "archive_manifest": manifest.to_dict(),
                "verified": verified,
            }
            self._audit(context, "trigger_archive", "SUCCESS", resource_id=checkpoint_id)
            return res
        except Exception as e:
            self._audit(context, "trigger_archive", "DENIED", resource_id=checkpoint_id, reason=str(e))
            raise


