# Phase 17.9: Memory Reasoning & Recall Planning Specification

## 1. Executive Summary & Purpose
Phase 17.9 defines the **Advanced Memory Reasoning & Recall Planning Layer** for the Brud Mini Brain memory subsystem. While Phase 17.8 successfully delivers deterministic, multi-signal memory retrieval (`MemoryRecallEngine`), memory items in Phase 17.8 are evaluated and scored as independent records.

Phase 17.9 introduces higher-order reasoning over the retrieved memory set:
1. **Multi-Memory Relationship Synthesis**: Identifying dependencies, temporal ordering, and corroborations among retrieved memories.
2. **Contradiction-Aware Partitioning**: Segregating active truth, historical facts, and contested observations.
3. **Procedural Workflow Reconstruction**: Assembling step-by-step sequences with dependency checks.
4. **Preference Consistency Reasoning**: Resolving global vs temporary user preferences deterministically.
5. **Reasoning-Ready Memory Packets**: Producing structured, provenance-preserving context objects (`MemoryReasoningPacket`) ready for consumption by reasoning engines and LLM runtime context builders without information loss.

---

## 2. Core Architecture Principles
- **Pure CPU Domain Reasoning**: Zero dependencies on GPU, PyTorch, Transformers, or external probabilistic LLMs for memory structure assembly.
- **Deterministic Mathematical Reasoning**: All graph traversal, relationship scores, and evidence aggregations are closed-form and bit-exact reproducible.
- **Zero Database Schema Migrations**: Operates entirely within the existing SQLite WAL schema by leveraging `memory_items`, `memory_item_versions`, `memory_item_events`, `memory_disputes`, and Phase 17.8 `MemoryRecallResult`.
- **Anti-Inflation Preservation (G4)**: Memory reasoning and context packet formation NEVER increment `evidence_count` or inflate memory confidence.
- **Tenant Scope & Governance Isolation (G1, G5)**: Reasoning is strictly scoped to `participant_scope_key`.

---

## 3. Mathematical Reasoning & Coherence Model

### 3.1 Pairwise Memory Relationship Score ($R_{ij}$)
For any pair of retrieved memories $m_i$ and $m_j$ in the candidate set:

$$R_{ij} = \text{clamp}\Big(0.0, 1.0, w_{\text{vec}} \cdot S_{\text{vec}}(m_i, m_j) + w_{\text{lex}} \cdot S_{\text{lex}}(m_i, m_j) + \delta_{\text{category}}(m_i, m_j) + \delta_{\text{temporal}}(m_i, m_j)\Big)$$

Where:
- $S_{\text{vec}}(m_i, m_j) \in [0.0, 1.0]$: 64-dimensional cosine vector similarity.
- $S_{\text{lex}}(m_i, m_j) \in [0.0, 1.0]$: Normalized lexical token overlap.
- $\delta_{\text{category}}(m_i, m_j) = 0.15$ if $m_i.\text{category} == m_j.\text{category}$, else $0.0$.
- $\delta_{\text{temporal}}(m_i, m_j) = 0.10 \times \exp(-\Delta t / \tau)$ where $\Delta t = |t_i - t_j|$ in seconds.

### 3.2 Reasoning Packet Coherence Score ($C_{\text{packet}}$)
$$C_{\text{packet}} = \text{clamp}\Bigg(0.0, 100.0, \frac{1}{|M|} \sum_{i \in M} \text{score}(m_i) + \frac{20.0}{|M|(|M|-1)} \sum_{i < j} R_{ij} - P_{\text{dispute}} - P_{\text{fragmentation}}\Bigg)$$

Where:
- $P_{\text{dispute}}$: Penalty applied if contested facts coexist without explicit conflict policy resolution.
- $P_{\text{fragmentation}}$: Penalty if retrieved items lack topical or procedural connectedness.

---

## 4. Operational Pipeline
```
Phase 17.8 MemoryRecallResult (Retrieved Items)
                   ↓
1. Relationship & Dependency Detection (Topic, Temporal, Procedural)
                   ↓
2. Contradiction & Dispute Partitioning (Ground Truth vs Contested vs Superseded)
                   ↓
3. Procedural Sequence Alignment (Step 1 → Step 2 → Step 3)
                   ↓
4. Preference Synthesis (Explicit vs Inferred, Scope Hierarchy)
                   ↓
5. Deterministic Packet Assembly & Compression (MemoryReasoningPacket)
                   ↓
Downstream Chat Orchestration & LLM Prompt Runtime
```
