# PHASE 17.8 — RANKING MODEL & MATHEMATICAL SPECIFICATION
# DETERMINISTIC MULTI-SIGNAL RECALL SCORING

**Document ID**: `P17_8_RANKING_MODEL_REPORT`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  

---

## 1. Mathematical Scoring Formulation

The Phase 17.8 deterministic ranking model synthesizes semantic similarity, lexical overlap, domain importance, confidence calibration, contextual relevance, temporal freshness decay, and conflict status into a single calibrated ranking score bounded strictly to the interval $[0.0, 100.0]$.

### Core Formulation:

$$\text{effective\_recall\_score} = \text{clamp}\left(0.0, 100.0, S_{\text{relevance}} + S_{\text{intrinsic}} + S_{\text{context}} - P_{\text{penalties}}\right)$$

Where:
1. **Relevance Component ($S_{\text{relevance}} \in [0.0, 70.0]$)**:
   $$S_{\text{relevance}} = (w_{\text{vector}} \cdot S_{\text{vector}} \times 40.0) + (w_{\text{keyword}} \cdot S_{\text{keyword}} \times 30.0)$$
   - $S_{\text{vector}} \in [0.0, 1.0]$: Cosine similarity between query and memory 64-dim embedding.
   - $S_{\text{keyword}} \in [0.0, 1.0]$: Normalized token overlap ratio.
   - Default normalized weights: $w_{\text{vector}} = 0.6$, $w_{\text{keyword}} = 0.4$.

2. **Intrinsic Memory Component ($S_{\text{intrinsic}} \in [0.0, 30.0]$)**:
   $$S_{\text{intrinsic}} = (0.20 \times \text{importance\_score}) + (0.10 \times \text{confidence\_score})$$
   - $\text{importance\_score} \in [0.0, 100.0]$: Category base + access boost + admin boost (from Phase 17.3).
   - $\text{confidence\_score} \in [0.0, 100.0]$: Provenance source base + distinct observation reinforcement.

3. **Contextual Intelligence Boost ($S_{\text{context}} \in [0.0, 45.0]$)**:
   $$S_{\text{context}} = \Delta_{\text{topic}} + \Delta_{\text{task}}$$
   - $\Delta_{\text{topic}} = +20.0$ if memory matches active conversational topic (Phase 17.2).
   - $\Delta_{\text{task}} = +25.0$ if memory matches active task objective.

4. **Penalties ($P_{\text{penalties}} \ge 0.0$)**:
   $$P_{\text{penalties}} = P_{\text{freshness}} + P_{\text{conflict}}$$
   - Freshness penalty ($P_{\text{freshness}}$):
     - `FRESH`: $0.0$
     - `AGING`: $5.0$
     - `STALE`: $15.0$
     - `EXPIRED`: $40.0$ (in `CURRENT` mode) / $0.0$ (in `HISTORICAL` mode).
   - Conflict penalty ($P_{\text{conflict}}$):
     - Unresolved active dispute (`DETECTED`, `PENDING_REVIEW`): $20.0$.
     - Clean / no conflict: $0.0$.

---

## 2. Weight Configuration Data Structure

```python
@dataclass(frozen=True)
class MemoryRecallWeights:
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    importance_weight: float = 0.20
    confidence_weight: float = 0.10
    topic_boost: float = 20.0
    task_boost: float = 25.0
    conflict_penalty: float = 20.0
    stale_penalty: float = 15.0
    expired_penalty: float = 40.0
    minimum_score_threshold: float = 15.0
```

---

## 3. Mathematical Invariants & Guardrails

1. **Deterministic Bounding**:
   - Every intermediate arithmetic step is finite.
   - If `math.isnan(score)` or `math.isinf(score)`, fallback returns `0.0`.
   - Output is clamped via `round(max(0.0, min(100.0, raw_score)), 2)`.

2. **Strict Deterministic Tie-Breaking**:
   - Primary: `effective_recall_score` (Descending)
   - Secondary: `confidence_score` (Descending)
   - Tertiary: `importance_score` (Descending)
   - Quaternary: `memory_item_public_id` (Ascending lexicographical order)
   - Zero random or nondeterministic tie resolutions.

3. **No LLM / Generative Hallucination**:
   - Zero LLM judgment or stochastic model evaluation during ranking.
   - All weights are fixed, transparent, and auditable.
