"""Phase 45 — Admin Role-Based Access Control (RBAC).

Implements Workstream 13:
- Roles:
  - SUPER_ADMIN: High-risk operations (subject to two-person rule)
  - ADMIN: Candidate, evaluation, and management operations
  - AUDITOR: Read-only access to evaluation and telemetry
- Operation permissions mapping
- Enforces principle of least privilege
"""

from __future__ import annotations


class RolePermissionDeniedError(PermissionError):
    """Raised when an admin role attempts an unauthorized action."""
    pass


class AdminRBACManager:
    """Evaluates role permissions against requested operations."""

    ROLE_PERMISSIONS = {
        "AUDITOR": {
            "read_model",
            "read_evaluation",
            "read_telemetry",
            "read_audit_log",
            "read_training_job",
            "get_daemon_status",
        },
        "ADMIN": {
            "read_model",
            "create_model",
            "read_evaluation",
            "create_evaluation",
            "read_telemetry",
            "read_audit_log",
            "propose_canary",
            "create_training_job",
            "read_training_job",
            "update_training_job",
            "start_daemon",
            "stop_daemon",
            "pause_training",
            "resume_training",
            "get_daemon_status",
            "trigger_archive",
        },
        "SUPER_ADMIN": {
            "read_model",
            "create_model",
            "read_evaluation",
            "create_evaluation",
            "read_telemetry",
            "read_audit_log",
            "propose_canary",
            "approve_canary",
            "execute_rollback",
            "create_training_job",
            "read_training_job",
            "update_training_job",
            "start_daemon",
            "stop_daemon",
            "pause_training",
            "resume_training",
            "get_daemon_status",
            "trigger_archive",
        },
    }



    @classmethod
    def authorize_operation(cls, role: str, operation: str) -> None:
        """Verifies if the specified role is authorized for the operation."""
        if role not in cls.ROLE_PERMISSIONS:
            raise RolePermissionDeniedError(f"Unknown or invalid role: {role}")

        allowed = cls.ROLE_PERMISSIONS[role]
        if operation not in allowed:
            raise RolePermissionDeniedError(
                f"Operation '{operation}' denied for role '{role}' (insufficient permissions)"
            )
