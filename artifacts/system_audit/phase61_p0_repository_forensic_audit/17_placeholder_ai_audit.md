# 17 PLACEHOLDER / FAKE AI AUDIT

## Heuristic & Mock Component Findings

1. **Admin Intent Classification**:
   -  relies on hardcoded string keywords (, , ) rather than LLM inference.
2. **Domain Classification**:
   -  uses simple keyword counting heuristics.
3. **Tool Selection**:
   -  uses lookup tables rather than autonomous tool selection.
