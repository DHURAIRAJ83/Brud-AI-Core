"""MB-07: Version Manager -- pure decision layer only. Validates and
suggests "Brud-X.Y" version strings. The actual immutable persistence
(a version can never be overwritten once created) is NOT reimplemented
here -- it is the existing `ModelReleaseService.create_release()`,
which already enforces uniqueness per family at the database layer.
This module only decides, ahead of that call, whether a proposed
version string is well-formed and monotonically ahead of every
existing version for the family.
"""

from __future__ import annotations

import re
from typing import Any

VERSION_PATTERN = re.compile(r"^Brud-(\d+)\.(\d+)$")


def parse_version(version: str) -> tuple[int, int] | None:
    match = VERSION_PATTERN.match(version)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def validate_next_version(*, proposed: str, existing_versions: list[str]) -> dict[str, Any]:
    reasons: list[str] = []
    parsed = parse_version(proposed)
    if parsed is None:
        reasons.append(f"{proposed!r} does not match the required 'Brud-<major>.<minor>' format")
        return {"valid": False, "reasons": reasons}

    if proposed in existing_versions:
        reasons.append(f"version {proposed!r} already exists for this family -- versions are never overwritten")

    existing_parsed = [p for v in existing_versions if (p := parse_version(v)) is not None]
    if existing_parsed and parsed <= max(existing_parsed):
        highest = max(existing_parsed)
        reasons.append(
            f"proposed version Brud-{parsed[0]}.{parsed[1]} is not ahead of the highest "
            f"existing version Brud-{highest[0]}.{highest[1]}"
        )

    return {"valid": not reasons, "reasons": reasons}


def suggest_next_version(existing_versions: list[str]) -> str:
    existing_parsed = [p for v in existing_versions if (p := parse_version(v)) is not None]
    if not existing_parsed:
        return "Brud-0.1"
    major, minor = max(existing_parsed)
    return f"Brud-{major}.{minor + 1}"
