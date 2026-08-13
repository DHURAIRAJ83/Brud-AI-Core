"""MB-25: Filesystem Guard -- pure. Canonical-path containment check
against MB-24's own already-approved `filesystem_roots` -- the task
spec's own Step 10 ("use canonical path resolution before
comparison"). This module never opens, reads, or writes a file; it
only decides whether a requested path would be allowed.
"""

from __future__ import annotations

import os
from typing import Any


def check_path_allowed(*, requested_path: str, allowed_roots: list[str]) -> dict[str, Any]:
    if not allowed_roots:
        return {"allowed": False, "reason": "no filesystem roots are approved for this plugin", "matched_root": None}

    normalized_requested = os.path.normpath(os.path.abspath(requested_path))
    for root in allowed_roots:
        normalized_root = os.path.normpath(os.path.abspath(root))
        if normalized_requested == normalized_root or normalized_requested.startswith(normalized_root + os.sep):
            return {"allowed": True, "reason": None, "matched_root": root}

    return {
        "allowed": False, "matched_root": None,
        "reason": f"path '{requested_path}' is outside every filesystem root approved for this plugin",
    }
