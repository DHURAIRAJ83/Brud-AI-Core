"""Shared result dataclass for every Phase 17 classifier layer (Step 2).

Every layer returns exactly these fields: `value`, `confidence_band`
(`high|medium|low|unknown` -- never a fabricated numeric score),
`reason_codes` (stable strings from `reason_codes.REASON_CODE_REGISTRY`),
`matched_rules` (the literal keyword/rule hits, for explainability), and
`policy_version`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LayerResult:
    value: str
    confidence_band: str
    reason_codes: tuple[str, ...]
    matched_rules: tuple[str, ...]
    policy_version: str
    secondary_values: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["LayerResult"]
