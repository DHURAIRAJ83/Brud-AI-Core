# P17 Context Intelligence Report: Brud Mini Brain Intelligence 2.0

**Audit Date**: 2026-09-06  
**Auditor**: Antigravity AI Assistant & Engineering Runtime  
**Target Scope**: Phase 17.2 — Context Intelligence Layer  
**Baseline Status**: Phase 16 Production Go-Live Ready (163/163 Tests Passed, G1–G14 Active)

---

## 1. Executive Summary

Phase 17.2 implements a dedicated, testable, and CPU/local-first **Context Intelligence** layer for the Brud Mini Brain / Admin Assistant Runtime.

The new Context Intelligence engine sits cleanly above the existing canonical context orchestrator (`core_model/conversation/context_orchestrator.py`), providing:
1. **Bounded Active Topic Tracking**: Categorizes conversation topics against domain taxonomy (`database_backup`, `rag_duplicate_detection`, `training_dataset`, `model_release`, `security_review`, `system_health`, etc.).
2. **Topic Transition Detection**: Accurately classifies topic continuity into `CONTINUATION`, `RELATED_TOPIC`, `NEW_TOPIC`, or `UNKNOWN`.
3. **Reference & Anaphora Resolution**: Resolves Tamil pronouns ("அது", "இது", "இதில்", "முந்தையது", "அந்த file") and English pronouns ("it", "this", "the previous one", "that file") against recent bounded turns without hallucination.
4. **Unresolved Question Tracking**: Maintains an active buffer of unanswered user inquiries and marks them resolved upon adequate diagnostic reply.
5. **Documented Context Relevance Ranking**: Employs a multi-dimensional scoring formula (0–100 scale) balancing task relevance, topic relevance, reference relevance, unresolved question relevance, and recency.
6. **Token Budgeting & Pruning**: Enforces strict token limits, prioritizing high-relevance and recent turns while pruning older, low-relevance turns.
7. **Zero Secret Leakage (G8)**: Sanitizes and redacts credentials, bearer tokens, and API keys across all context items and state.

---

## 2. Architecture & Layer Integration

```mermaid
flowchart TD
    UserTurn[User Request / Message] --> SecretScrub[Message Sanitizer / G8 Redaction]
    SecretScrub --> TopicEngine[1. Topic Detection & Transition Engine]
    TopicEngine --> AnaphoraResolver[2. Tamil & English Reference Resolver]
    AnaphoraResolver --> UnresolvedTracker[3. Unresolved Question Tracker]
    UnresolvedTracker --> RelevanceScorer[4. Turn Relevance Scorer (0-100 scale)]
    RelevanceScorer --> BudgetSelector[5. Token Budget Allocation & Pruning]
    BudgetSelector --> CanonicalOrchestrator[6. Canonical Context Orchestrator\n(core_model/conversation/context_orchestrator.py)]
    CanonicalOrchestrator --> ContextStateOut[ContextState Data Contract]
    ContextStateOut --> LlmRuntime[MiniBrainLlmRuntimeService / Provider Generation]
```

---

## 3. Data Contract (`ContextState`)

The data contract is formalized in `core_model/mini_brain/intelligence/context_intelligence.py`:

```python
@dataclass
class ContextState:
    conversation_id: str
    active_topic: str | None
    previous_topic: str | None
    topic_changed: bool
    topic_transition: str  # CONTINUATION | RELATED_TOPIC | NEW_TOPIC | UNKNOWN
    current_intent: str
    unresolved_questions: list[dict[str, Any]]
    resolved_references: list[dict[str, Any]]
    relevant_turns: list[dict[str, Any]]
    context_budget: dict[str, Any]
    context_items: list[dict[str, Any]]
    trace_id: str | None
```

---

## 4. Algorithmic Specifications

### 4.1. Relevance Scoring Formula
$$\text{Relevance Score} = \text{Task Relevance } (0\text{--}30) + \text{Topic Relevance } (0\text{--}25) + \text{Reference Relevance } (0\text{--}20) + \text{Unresolved Relevance } (0\text{--}15) + \text{Recency Score } (0\text{--}10)$$
- **Score Range**: Bounded $[0.0, 100.0]$.
- **Task Relevance**: $30.0$ if turn matches the active administrative task.
- **Topic Relevance**: $25.0$ if turn matches active topic; $15.0$ if within same domain cluster.
- **Reference Relevance**: Up to $20.0 \times \text{confidence}$ if turn contains the resolved entity.
- **Unresolved Relevance**: $15.0$ if turn pertains to a pending diagnostic question.
- **Recency Score**: Up to $10.0 \times (\text{turn\_index} / \text{total\_turns})$.

### 4.2. Reference Resolution Accuracy
- When unambiguous entity/file/model exists in history $\to$ `status = "RESOLVED"`, $\text{confidence} \ge 0.75$.
- When context is empty or ambiguous $\to$ `status = "UNKNOWN"`, $\text{resolved\_entity} = \text{None}$, $\text{confidence} = 0.0$.
- **Zero Hallucination Guarantee**: Entities are strictly grounded in recent conversation turns.

---

## 5. Duplicate Logic & Guardrail Verification

- **Canonical Context Orchestrator**: `core_model/conversation/context_orchestrator.py` remains the single canonical context builder. No competing context assembly system was introduced.
- **No Heavy NLP Dependencies**: Operates on pure Python regex and deterministic taxonomy with sub-millisecond latency.
- **Security G8**: All context state scrubbed against secret leak patterns.
- **Advisory Only G1**: Context Intelligence performs read-only context analysis and does not autonomously mutate runtime state.
