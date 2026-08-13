"""MB-23: Tool Routing Policy -- pure. Derives a `used_tool` flag and
tool category from fields `PublicChatResponse` already carries
(`tool_name`, `tool_status`, `route_used`) -- MB-23 never dispatches a
tool itself; `DeterministicToolExecutionService`, reached only through
`PublicChatRoutingService.handle_message()`, is the sole real
dispatcher in the codebase.
"""

from __future__ import annotations

from typing import Any


def derive_tool_usage(*, route_used: str, tool_name: str | None, tool_status: str | None) -> dict[str, Any]:
    used_tool = route_used == "tool" or tool_name is not None
    succeeded = used_tool and tool_status == "success"
    return {
        "used_tool": used_tool, "tool_name": tool_name if used_tool else None,
        "tool_succeeded": succeeded,
        "disclosure": "derived from PublicChatResponse's own already-computed tool fields -- no tool is dispatched by this module",
    }
