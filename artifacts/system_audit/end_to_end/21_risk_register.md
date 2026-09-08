# Master Brud AI End-to-End Audit — 21: Master Risk Register

**Audit Date:** 2026-09-01  
**Auditor:** Principal Risk Architect & Governance Auditor  
**Confidence Rating:** HIGH CONFIDENCE  

---

## End-to-End System Risk Matrix

| Risk ID | Domain | Risk Description | Severity | Probability | Impact | Active Controls & Remediation |
|---|---|---|---|---|---|---|
| **RSK-E2E-01** | Model | Premature Promotion to Public Users: 528k model serving low-quality looping text | 🔴 **CRITICAL** | Low (Blocked in code) | High | 🔒 **MITIGATED IN CODE**: `candidate_traffic_share = 0.0`, promotion strictly barred. |
| **RSK-E2E-02** | Model | Context Attention Saturation: Model forgetting conversation turns beyond 128 tokens | 🟠 **HIGH** | High | High | Planned: WS07 Stage C (E4 Context Scaling to $T=512$). |
| **RSK-E2E-03** | Model | Capacity Bottleneck: Under-parameterized model failing factual and reasoning probes | 🟠 **HIGH** | High | High | Planned: WS07 Stage C (E5 Capacity Scaling to ~3.2M parameters). |
| **RSK-E2E-04** | Inference | Greedy Repetition Loops: Raw weights looping 3-grams indefinitely | 🟠 **HIGH** | High (in raw weights) | High | 🔒 **MITIGATED IN DECODING**: $\theta=1.25$ + no-repeat 3-gram drops repetition to 0.0000. |
| **RSK-E2E-05** | Data | Synthetic Data Domination: Machine data corrupting natural Tamil grammar | 🟠 **HIGH** | Medium | High | 🔒 **MITIGATED IN CODE**: 8:1 synthetic volume cap and mandatory human review queue. |
| **RSK-E2E-06** | Security | Admin Role Desynchronization: Roles stored in env overrides rather than DB schema | 🟡 **MEDIUM** | Medium | Medium | Mitigated: Fails closed to `AdminRole.ADMIN` with strict proposal/execution barriers. |
| **RSK-E2E-07** | Infrastructure| Host CPU Starvation during Long-Run Training | 🟡 **MEDIUM** | Medium | Medium | 🔒 **MITIGATED IN CODE**: `torch.set_num_threads(2)` and 2 GB RAM hard ceiling enforced. |
| **RSK-E2E-08** | RAG | Semantic Search Inaccuracy: Hashing-trick embeddings failing on complex semantic queries | 🟡 **MEDIUM** | High | Medium | Acceptable for keyword matching; roadmap item P2: integrate trained bi-encoder. |
| **RSK-E2E-09** | Deployment | Absence of Standardized Containerization (No Docker) | 🟡 **MEDIUM** | High | Medium | Roadmap item P2: author production Dockerfile and compose manifests. |
| **RSK-E2E-10** | Codebase | Duplicate Class Names Across Standalone Runners | 🟢 **LOW** | Low | Low | Refactor `BrudSmallV2Model` into dedicated architecture module in future phase. |
