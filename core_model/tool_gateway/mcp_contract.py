"""Phase 20 Step 23 -- internal MCP-compatible contract.

Every current tool source (`built_in_deterministic`, the only one with
a real, executing implementation in this phase) and every future
source (`internal_service`, `external_mcp`) is described through the
same `ToolDescriptor`/`ToolInvocationRequest`/`ToolInvocationResult`
shape. `Settings.external_mcp_enabled` defaults to `False`
(Step 23's own required default), and
`DeterministicToolRegistry`/`DeterministicToolExecutionService` (Step
17) refuse to execute *any* `external_mcp`-sourced descriptor
regardless of that flag in this phase -- no external MCP server
configuration is even accepted through any Phase 20 API. The flag
exists purely so a future phase has one documented, auditable place to
eventually change this, not because Phase 20 offers a working path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDescriptor:
    tool_name: str
    tool_version: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: str
    source: str
    permission: str
    public_enabled: bool
    admin_enabled: bool
    timeout_seconds: float
    maximum_input_size: int


@dataclass(frozen=True)
class ToolInvocationRequest:
    tool_name: str
    input_payload: dict[str, Any]
    request_id: str
    is_public_request: bool = True


@dataclass(frozen=True)
class ToolInvocationResult:
    tool_name: str
    tool_version: str
    status: str
    output_payload: dict[str, Any] | None
    error_code: str | None
    latency_ms: int
    execution_public_id: str | None = None


@dataclass(frozen=True)
class ToolPermissionContext:
    is_public_request: bool
    is_admin_request: bool = False
    external_mcp_enabled: bool = False


class ToolExecutionError(RuntimeError):
    def __init__(self, error_code: str, message: str = "") -> None:
        super().__init__(message or error_code)
        self.error_code = error_code


__all__ = [
    "ToolDescriptor",
    "ToolExecutionError",
    "ToolInvocationRequest",
    "ToolInvocationResult",
    "ToolPermissionContext",
]
