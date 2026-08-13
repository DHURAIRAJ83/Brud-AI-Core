"""MB-24: Filesystem Policy Builder -- pure. Builds a declarative,
normalized filesystem policy from a plugin's own declared roots --
policy metadata only. No file is ever opened, read, or written by
this module.
"""

from __future__ import annotations

from typing import Any


def build_filesystem_policy(*, filesystem_roots: list[str], read_requested: bool, write_requested: bool) -> dict[str, Any]:
    roots = sorted({root.strip() for root in filesystem_roots if root.strip()})
    return {
        "filesystem_roots": roots, "root_count": len(roots),
        "read_enabled": read_requested and bool(roots), "write_enabled": write_requested and bool(roots),
        "disclosure": "declarative policy metadata only -- no real filesystem access is granted or performed by this module",
    }
