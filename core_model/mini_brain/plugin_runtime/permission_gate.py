"""MB-25: Permission Gate -- pure. The execution-time check that the
exact scope this execution needs is currently `granted` in MB-24's own
records -- never re-deciding policy itself (that decision already
happened in MB-24's `runtime_policy_evaluator`), only confirming the
grant is real and current.
"""

from __future__ import annotations

from typing import Any


def evaluate_execution_permission(*, required_scope: str, granted_scope_keys: list[str]) -> dict[str, Any]:
    allowed = required_scope in granted_scope_keys
    return {
        "allowed": allowed,
        "reason": None if allowed else f"scope '{required_scope}' is not currently granted for this plugin",
    }
