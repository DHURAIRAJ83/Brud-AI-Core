# Phase 17.7 — Decay & Reinforcement Mathematical Specification
**Brud Mini Brain: Deterministic CPU-First Scoring & Anti-Inflation Rules**

## 1. Metric Distinctions

| Metric | Range | Semantics | Mutation Triggers |
|:---|:---:|:---|:---|
| **Confidence (`confidence_score`)** | $[0.0, 100.0]$ | Epistemic certainty of the claim | Boosted by verified repeat observations ($+2.0/\text{obs}$, max $+15.0$) or admin confirmation ($95.0+$). |
| **Importance (`importance_score`)** | $[0.0, 100.0]$ | Domain priority / operational impact | Base category weight boosted by admin approval ($+10.0$) and access frequency ($+1.5/\text{access}$, max $+10.0$). |
| **Freshness (`freshness_state`)** | Discrete Enum | Temporal validity window state | `FRESH` ($\text{age} < 0.25\text{TTL}$), `AGING` ($<0.75\text{TTL}$), `STALE` ($<1.0\text{TTL}$), `EXPIRED` ($\ge 1.0\text{TTL}$). |
| **Evidence Count (`evidence_count`)** | $\mathbb{Z}^+ \ge 1$ | Count of distinct verified observations | Increments ONLY when a new distinct user/turn observation confirms the statement. |
| **Access Frequency (`access_count`)** | $\mathbb{Z}^+ \ge 0$ | Number of times retrieved in context | Increments on context assembly / retrieval execution. |

---

## 2. Deterministic Decay Function (CPU-First)

To compute the effective operational rank score without LLMs:

$$\text{effective\_rank\_score} = (0.4 \times \text{importance}) + (0.3 \times \text{confidence}) + \Delta_{\text{topic}} + \Delta_{\text{task}} - \text{Penalty}_{\text{freshness}}$$

### Freshness Penalty ($\text{Penalty}_{\text{freshness}}$):
$$\text{Penalty}_{\text{freshness}} = \begin{cases} 
0.0 & \text{if } \text{freshness\_state} = \text{FRESH} \\
5.0 & \text{if } \text{freshness\_state} = \text{AGING} \\
15.0 & \text{if } \text{freshness\_state} = \text{STALE} \\
40.0 & \text{if } \text{freshness\_state} = \text{EXPIRED}
\end{cases}$$

---

## 3. Anti-Inflation Reinforcement Rules

1. **Retrieval Access $\ne$ Evidence**:
   - Querying a memory increments `access_count += 1`.
   - `evidence_count` remains UNCHANGED.
   - `confidence_score` is NOT inflated by read traffic.

2. **Observation Reinforcement**:
   - When a new observation matches an existing canonical memory (via Exact, Normalized, or Semantic Duplicate with cosine $\ge 0.88$):
     - $\text{evidence\_count}_{\text{new}} = \text{evidence\_count}_{\text{old}} + \text{evidence\_count}_{\text{candidate}}$
     - $\text{confidence\_score}_{\text{new}} = \min(100.0, \text{base\_confidence} + \min(15.0, (\text{evidence\_count}_{\text{new}} - 1) \times 2.0))$
     - $\text{freshness\_state}_{\text{new}} = \text{FRESH}$
     - `last_accessed_at` is updated to current UTC.
     - Immutable event `MEMORY_REINFORCED` is recorded with candidate provenance.
