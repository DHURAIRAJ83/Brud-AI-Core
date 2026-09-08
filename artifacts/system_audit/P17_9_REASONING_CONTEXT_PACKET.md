# Phase 17.9: Reasoning Context Packet Specification

## 1. Objective
Define the canonical domain data structure (`MemoryReasoningPacket`) output by the reasoning layer for consumption by downstream reasoning and prompt assembly pipelines.

---

## 2. Structure Definition
```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class MemoryReasoningPacket:
    query: str
    participant_scope_key: str
    retrieval_mode: str
    coherence_score: float                           # [0.0, 100.0]
    active_facts: tuple[dict[str, Any], ...]         # Uncontested active truths
    historical_facts: tuple[dict[str, Any], ...]     # Historical context memories
    procedural_chains: tuple[dict[str, Any], ...]    # Ordered workflow steps
    resolved_preferences: dict[str, Any]             # Resolved active user preferences
    evidence_clusters: tuple[dict[str, Any], ...]    # Corroborating evidence groups
    disputed_items: tuple[dict[str, Any], ...]       # Contested items with advisory warnings
    provenance_citations: tuple[dict[str, Any], ...] # Citation mappings & source IDs
    warnings: tuple[str, ...]                        # System/safety/conflict warnings
    total_token_estimate: int                        # Estimated token footprint
    assembled_epoch: float                           # Deterministic timestamp
```

---

## 3. Formatting & Prompt Integration
The packet provides a deterministic `.to_context_block()` helper that formats all facts into structured markdown sections:
- `[Active Facts]`
- `[Workflow Steps]`
- `[User Preferences]`
- `[Historical Context]` (if `HISTORICAL` mode)
- `[Disputed / Contested Items]` (if present under `prefer_recent`)
All sections preserve citation markers (e.g. `[mem:pub_abc123]`) and contain zero secrets/credentials.
