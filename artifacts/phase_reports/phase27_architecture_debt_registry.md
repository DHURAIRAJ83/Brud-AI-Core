# Phase 27 Architecture Debt Registry

This registry tracks technical debt, architectural findings, and enhancement opportunities identified across **Phases 13 through 26**.

> [!IMPORTANT]
> **READ-ONLY FINDINGS REGISTRY**:
> This document records architectural observations only. **NO SOURCE CODE MODIFICATIONS ARE ALLOWED DURING PHASE 27**.

---

## Architecture Debt Items

### Debt Item 1: Legacy Health Endpoint Coexistence
- **ID**: DEBT-27-01
- **Category**: API Architecture
- **Phase**: Phase 15 & Phase 26
- **File**: [`backend/api/routes/mini_brain_health.py`](file:///home/dhurai/Projects/brud-ai/backend/api/routes/mini_brain_health.py) & [`backend/api/routes/observability_admin.py`](file:///home/dhurai/Projects/brud-ai/backend/api/routes/observability_admin.py)
- **Finding**: Legacy `/api/v1/health` and `/admin/mini-brain/health` endpoints coexist with Phase 26 `/admin/phase26/health` endpoint.
- **Evidence**: Legacy routes perform basic ping checks; Phase 26 performs 8-category structured health observations.
- **Severity**: LOW
- **Impact**: Minor confusion for API consumers looking for comprehensive system health versus basic uptime.
- **Recommendation**: Maintain legacy endpoints for basic uptime probes while routing admin dashboard health inspection to `/admin/phase26`.
- **Implementation Required**: No immediate code change required.
- **Priority**: P4 (Nice to Have)

---

### Debt Item 2: Settings Dependency Import Path Standardization
- **ID**: DEBT-27-02
- **Category**: Dependency Structure
- **Phase**: Phase 24, Phase 25, Phase 26
- **File**: [`backend/api/routes/observability_admin.py`](file:///home/dhurai/Projects/brud-ai/backend/api/routes/observability_admin.py)
- **Finding**: `SettingsDependency` is imported from `backend.api.dependencies` in modern routers, while older routers imported directly from `backend.core.config`.
- **Evidence**: [`backend/api/dependencies.py`](file:///home/dhurai/Projects/brud-ai/backend/api/dependencies.py) provides the canonical FastAPI Annotated dependency alias.
- **Severity**: INFO
- **Impact**: Minor inconsistency in import statements across admin route plugins.
- **Recommendation**: Standardize all route plugin imports to use `from backend.api.dependencies import SettingsDependency`.
- **Implementation Required**: Clean import refactoring in future phases.
- **Priority**: P4 (Minor Cleanup)

---

### Debt Item 3: Concurrency Lock Expiration Strategy
- **ID**: DEBT-27-03
- **Category**: Concurrency & Locking
- **Phase**: Phase 24, Phase 25, Phase 26
- **File**: [`backend/database/repositories/observability_repository.py`](file:///home/dhurai/Projects/brud-ai/backend/database/repositories/observability_repository.py)
- **Finding**: Lock tables (`phase24_release_locks`, `phase25_deployment_locks`, `phase26_health_locks`) rely on explicit try/finally release blocks in service methods.
- **Evidence**: If a process crashes violently mid-operation, lock records remain in the SQLite table until manually cleared.
- **Severity**: LOW
- **Impact**: Orphaned locks could prevent re-attempting operations if server crashes unexpectedly.
- **Recommendation**: Add a TTL/timestamp-based lock cleanup helper for administrative lock release in future maintenance tooling.
- **Implementation Required**: Additive administrative lock reset tool.
- **Priority**: P3 (Medium Priority for Ops)

---

### Debt Item 4: Combined Integration Suite Runtime
- **ID**: DEBT-27-04
- **Category**: Test Architecture
- **Phase**: Phases 13–26
- **File**: `tests/core_model/`
- **Finding**: Full combined regression suite execution time is ~142 seconds for 1,128 tests.
- **Evidence**: 1,128 tests execute synchronously in pytest.
- **Severity**: INFO
- **Impact**: Longer CI test runs.
- **Recommendation**: Utilize pytest-xdist for parallel test execution in CI environment.
- **Implementation Required**: CI configuration update.
- **Priority**: P4 (Tooling Optimization)

---

## Summary Scorecard

| Category | Debt Level | Risk Assessment | Action Priority |
| :--- | :---: | :--- | :--- |
| **Domain Architecture** | ZERO DEBT | Pure dataclasses, zero side-effects, full compliance | None |
| **Repository Architecture** | LOW DEBT | Clean additive DDL, explicit indexes, isolated connections | P4 |
| **Backend Services** | ZERO DEBT | Clear separation of responsibilities, idempotency enforced | None |
| **API Routers** | LOW DEBT | Server-side RBAC enforced, minor import path variance | P4 |
| **Concurrency & Locks** | LOW DEBT | Try/finally lock release intact, TTL cleanup recommended | P3 |
| **Security & Governance** | ZERO DEBT | AST clean, zero autonomous execution, DB untouched | None |
