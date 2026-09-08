# Master Brud AI System Audit — 17: Master Risk Register

**Audit Date:** 2026-09-01  
**Auditor:** Principal Risk Architect & Governance Auditor  
**Confidence Rating:** HIGH CONFIDENCE  

---

## Master Risk Matrix

| Risk ID | Category | Risk Description | Severity | Probability | Impact | Mitigation Status / Controls |
|---|---|---|---|---|---|---|
| **RSK-01** | Model | Premature Promotion to Public Users: 528k model hallucinating / looping tokens | 🔴 **CRITICAL** | Low (Blocked in code) | High | 🔒 **MITIGATED IN CODE**: `candidate_traffic_share = 0.0`, promotion strictly blocked. |
| **RSK-02** | Model | Context Attention Saturation: Model forgetting conversation turns beyond 128 tokens | 🟠 **HIGH** | High | High | Planned: WS07 Stage C (E4 Context Scaling to $T=512$). |
| **RSK-03** | Data | Synthetic Data Domination: Machine-generated text corrupting human Tamil nuances | 🟠 **HIGH** | Medium | High | 🔒 **MITIGATED IN CODE**: 8:1 synthetic volume cap and mandatory human review queue. |
| **RSK-04** | Inference | Repetition Degeneration: Greedy decoding looping 3-grams indefinitely | 🟠 **HIGH** | High (in raw weights) | High | 🔒 **MITIGATED IN DECODING**: $\theta=1.25$ + no-repeat 3-gram eliminates repetition to 0.0000. |
| **RSK-05** | Security | Admin Role Desynchronization: Roles stored in env overrides rather than DB schema | 🟡 **MEDIUM** | Medium | Medium | Mitigated: Fails closed to `AdminRole.ADMIN` with strict proposal/execution barriers. |
| **RSK-06** | Infrastructure| Host CPU Starvation during Long-Run Training | 🟡 **MEDIUM** | Medium | Medium | 🔒 **MITIGATED IN CODE**: `torch.set_num_threads(2)` and 2 GB RAM hard ceiling enforced. |
| **RSK-07** | RAG | Semantic Search Inaccuracy: Hashing-trick embeddings failing on complex semantic queries | 🟡 **MEDIUM** | High | Medium | Acceptable for keyword matching; roadmap item P2: integrate trained bi-encoder. |
| **RSK-08** | Deployment | Absence of Standardized Containerization (No Docker) | 🟡 **MEDIUM** | High | Medium | Roadmap item P2: author production Dockerfile and compose manifests. |
