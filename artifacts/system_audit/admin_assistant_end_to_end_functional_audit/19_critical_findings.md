# 19 CRITICAL FINDINGS REGISTRY

- **P0 Findings**: 0. (Zero critical functional breakdowns or security breaches).
- **P1 Findings**: 0. (Zero major missing governance controls).
- **P2 Findings**:
  - `P2-01`: Floating Chat Widget invokes `/api/admin/mini-brain/llm-runtime/chat` directly rather than `/api/admin/assistant/chat` (tool-using agent orchestrator).
  - `P2-02`: Provider settings and continuous learning status are viewable on Admin Dashboard pages, but chat does not expose dedicated tool commands to inspect them dynamically.
- **P3 / P4 Findings**: 0.
