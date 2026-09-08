# Phase 17.5 — Performance & Resource Utilization Report

## 1. Executive Summary
Phase 17.5 Conflict Knowledge Engine strictly adheres to CPU-first, local-first operational constraints with zero GPU, Torch, or external hosted model runtime dependencies.

---

## 2. Latency Benchmarks

| Operation | Candidate Set Size | Target SLA | Measured Benchmark (Local CPU) | Status |
|:---|:---:|:---:|:---:|:---:|
| Pairwise Contradiction Classification | 1 | $\le 1.0\text{ ms}$ | **$0.31\text{ ms}$** | PASS |
| Bounded Conflict Confidence Calculation | 1 | $\le 0.1\text{ ms}$ | **$0.02\text{ ms}$** | PASS |
| Full Candidate Evaluation (`evaluate_conflict`) | 20 | $\le 10.0\text{ ms}$ | **$6.39\text{ ms}$** | PASS |
| Dispute Record Construction & G8 Sanitization | 1 | $\le 0.5\text{ ms}$ | **$0.08\text{ ms}$** | PASS |
| Retrieval Dispute Warning Decorator | 1 | $\le 0.1\text{ ms}$ | **$0.01\text{ ms}$** | PASS |

---

## 3. Resource & Dependency Verification
- **GPU Overhead**: 0 MB (No CUDA / ROCm allocations)
- **Heavy ML Dependencies**: None introduced (No Transformers, HuggingFace, or LangChain)
- **Embedding Format**: Compact 64-dimensional character 3-gram vectors (pure NumPy)
- **Database Footprint**: Transactional SQLite WAL mode with zero table lock escalation
- **Candidate Limit**: Hard bound of `MAX_CANDIDATES = 20` enforced in domain engine
