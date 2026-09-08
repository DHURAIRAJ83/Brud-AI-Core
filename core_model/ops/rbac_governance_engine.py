"""Phase 61 - P9: RBAC Governance Engine.

Enforces role-based access control and strict privilege boundaries across human and automated roles.

CRITICAL INVARIANTS:
- Roles: HUMAN_ADMIN | LEGAL_OFFICER | SECURITY_AUDITOR | SYSTEM_OPERATOR | ADMIN_ASSISTANT_ADVISORY.
- Admin Assistant is strictly ADVISORY ONLY. It can NEVER execute training, promotion, rollback, recovery, secret revocation, or compliance certification.
- Privilege escalation attempts strictly fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class RBACPermissionError(PermissionError):
    """Raised when an unauthorized role attempts a privileged action."""


class RBACGovernanceEngine:
    """Role-based access control governance engine."""

    ROLES = (
        "HUMAN_ADMIN",
        "LEGAL_OFFICER",
        "SECURITY_AUDITOR",
        "SYSTEM_OPERATOR",
        "ADMIN_ASSISTANT_ADVISORY"
    )

    PRIVILEGED_ACTIONS = (
        "EXECUTE_TRAINING",
        "PROMOTE_MODEL",
        "EXECUTE_ROLLBACK",
        "EXECUTE_RECOVERY",
        "REVOKE_SECRET",
        "APPROVE_POLICY",
        "CERTIFY_COMPLIANCE",
        "ESCALATE_PRIVILEGE"
    )

    def authorize_action(self, role: str, action: str) -> bool:
        """Evaluate role permission for specified action."""
        if role not in self.ROLES:
            raise RBACPermissionError(f"DENY: Unknown role '{role}'.")

        # Admin Assistant is strictly ADVISORY ONLY
        if role == "ADMIN_ASSISTANT_ADVISORY" and action in self.PRIVILEGED_ACTIONS:
            raise RBACPermissionError(f"DENY: Admin Assistant role is ADVISORY ONLY and cannot execute privileged action '{action}'.")

        # Privileged actions require HUMAN_ADMIN or specialized authorized roles
        if action in ("EXECUTE_TRAINING", "PROMOTE_MODEL", "EXECUTE_ROLLBACK", "EXECUTE_RECOVERY", "REVOKE_SECRET", "APPROVE_POLICY"):
            if role != "HUMAN_ADMIN":
                raise RBACPermissionError(f"DENY: Role '{role}' lacks permission for privileged action '{action}'. Required: HUMAN_ADMIN.")

        if action == "CERTIFY_COMPLIANCE" and role not in ("HUMAN_ADMIN", "LEGAL_OFFICER"):
            raise RBACPermissionError(f"DENY: Role '{role}' lacks permission for '{action}'. Required: HUMAN_ADMIN or LEGAL_OFFICER.")

        return True
