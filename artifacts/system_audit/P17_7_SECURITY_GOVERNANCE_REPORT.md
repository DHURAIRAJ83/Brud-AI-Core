# Phase 17.7 — Security & Guardrails Revalidation Report
**Brud Mini Brain: G1–G14 Invariant Audit & Security Boundaries**

## 1. G1–G14 Invariant Mapping for Lifecycle & Freshness

| Invariant | Requirement | Lifecycle Risk | Enforcement Strategy | Test Requirement |
|:---|:---|:---|:---|:---|
| **G1 (Autonomy Boundary)** | AI must remain advisory; zero autonomous truth mutation | Autonomous expiration or archival of SYSTEM/ADMIN knowledge | `evaluate_governance()` blocks auto-state changes on SYSTEM/ADMIN; requires admin ID. | Verify SYSTEM/ADMIN memories cannot be auto-expired without admin token. |
| **G4 (Zero Fake Intelligence)** | Pure deterministic algorithms without fake ML stubs | Non-deterministic or LLM-generated decay scores | Mathematical decay curves with explicit threshold formulas. | Verify deterministic output reproducibility across runs. |
| **G5 (Strict Scope Isolation)** | Zero cross-tenant or cross-participant mutation | Batch lifecycle sweeps modifying memories across participant boundaries | Every lifecycle query and batch job filters strictly on `participant_scope_key`. | Verify batch expiration on Tenant A never mutates Tenant B. |
| **G8 (Zero Secret Leakage)** | No secret or credential entered into metadata or events | Lifecycle event details leaking sensitive payload text | Events record only opaque public IDs (`memory_item_public_id`, `admin_id`). | Scan all generated event `details_json` for credential tokens. |
| **G9 (Observability / Tracing)** | Complete immutable audit ledger | Silent state updates without actor attribution | Every state transition appends a record to `memory_item_events` and `audit_logs`. | Verify audit event created for every freshness/status mutation. |
| **G10/G11 (Durability & WAL)** | Atomic transactions with complete rollback on error | Partial state updates (e.g. status changed but event failed) | All multi-table updates wrapped in `with self.repository.transaction():`. | Inject fault during update; verify complete rollback. |

---

## 2. Actor Attribution & Admin Security
- **Scheduled Sweeps**: Executed with actor `system_lifecycle_daemon`.
- **Manual Archival / Reactivation**: Executed with explicit `admin_id` passed through CSRF and auth middleware.
- **Audit Logging**: Every transition logs `action`, `actor`, `resource_public_id`, `outcome`, and timestamp.
