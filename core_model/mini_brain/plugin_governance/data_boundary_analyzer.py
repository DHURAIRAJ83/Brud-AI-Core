"""MB-24: Data Boundary Analyzer -- pure. Cross-checks a manifest's
own declared scopes against its own declared data boundaries
(allowed_domains, filesystem_roots) for internal consistency --
flagging contradictions like a network scope with no allowed domains,
or an unbounded filesystem root. This never verifies a plugin
actually honors these boundaries at runtime; no runtime exists in
this phase.
"""

from __future__ import annotations

from typing import Any

_UNBOUNDED_ROOTS = frozenset({"/", "", "C:\\", "c:\\"})


def analyze_data_boundaries(
    *, requested_scopes: list[str], allowed_domains: list[str], filesystem_roots: list[str],
) -> dict[str, Any]:
    issues: list[str] = []

    if "network.http.allowed_domains" in requested_scopes and not allowed_domains:
        issues.append("network scope requested but allowed_domains is empty")

    if any(scope.startswith("filesystem.") for scope in requested_scopes) and not filesystem_roots:
        issues.append("filesystem scope requested but filesystem_roots is empty")

    for root in filesystem_roots:
        if root.strip() in _UNBOUNDED_ROOTS:
            issues.append(f"filesystem_roots contains an unbounded root path: {root!r}")

    if len(set(allowed_domains)) != len(allowed_domains):
        issues.append("allowed_domains contains duplicate entries")

    if len(set(filesystem_roots)) != len(filesystem_roots):
        issues.append("filesystem_roots contains duplicate entries")

    return {
        "issues": issues, "well_bounded": not issues,
        "disclosure": "checks internal consistency of declared data boundaries only -- never verifies the plugin actually honors them, since no runtime exists in this phase",
    }
