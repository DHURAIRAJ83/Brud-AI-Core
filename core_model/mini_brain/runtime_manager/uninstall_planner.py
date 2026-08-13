"""MB-30: Uninstall Planner -- pure. Given an already-fetched
installation record, builds a removal plan (which file to delete,
which row to mark removed) -- the actual file deletion and database
write happen in the service layer.
"""

from __future__ import annotations

from typing import Any


def build_removal_plan(*, installation: dict[str, Any]) -> dict[str, Any]:
    return {
        "public_id": installation["public_id"],
        "model_name": installation["model_name"],
        "file_to_delete": installation["install_path"],
        "was_installed": installation.get("status") == "installed",
    }
