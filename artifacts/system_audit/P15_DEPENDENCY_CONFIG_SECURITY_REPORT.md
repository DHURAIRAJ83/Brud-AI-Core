# P15.9 — DEPENDENCY & CONFIGURATION SECURITY REPORT

**Execution Timestamp:** 2026-09-04T21:49:39+05:30  
**Test Suite:** `tests/e2e/test_p15_dependency_config.py`  
**Test Results:** **7 passed in 2.99s (100% PASS)**  
**Verification Level:** `pip check` (0 broken requirements), Pydantic origin validation, TOML dependency pinning audit, NPM package exact pinning, and secret key fail-closed enforcement.

---

## 1. Executive Summary

Phase 15.9 performed an audit of all Python runtime dependencies, frontend dependencies, configuration security defaults, and environment bounds:
- **Python Dependencies (`pyproject.toml`):** 100% of runtime dependencies specify both upper and lower bounds (`>=` and `<`) or compatible release bounds (`~=`), eliminating supply-chain drift hazards. `pip check` reported **"No broken requirements found."**
- **Frontend Dependencies (`apps/admin-dashboard/package.json`):** Core dependencies (`react: 19.2.8`, `react-dom: 19.2.8`, `vite: 8.1.5`, `@vitejs/plugin-react: 6.0.3`) are pinned to exact immutable versions without wildcard `*` or loose version ranges.
- **CORS & Origin Hardening:** Pydantic validators fail closed when encountering wildcard CORS origins (`*` or partial wildcards `https://*.example.com`). All origins must parse as valid HTTP/HTTPS URLs. Malformed schemes (e.g. `javascript:`) are rejected.
- **Production Configuration Defaults:**
  - `debug = False` by default.
  - `database_wal = True` (WAL mode enabled for ACID crash recovery).
  - `database_auto_backup = True`.
  - `audit_enabled = True` (tamper-evident audit logging active).
  - `admin_lockout_minutes >= 15` and `admin_max_failed_logins <= 5` for brute-force resistance.
- **Filesystem Containment:** Database paths, models, and data exports are strictly bounded within `allowed_data_dir` and `allowed_model_dir`. Rogue directory escapes are rejected at boot time.
- **Fail-Closed Secret Encryption:** In accordance with G10, `BRUD_SECRET_ENCRYPTION_KEY` is required for storing upstream AI credentials. Missing master keys immediately trigger `EncryptionUnavailableError` rather than writing unencrypted secrets.

---

## 2. Test Execution Matrix

| Test ID | Scenario | Verification Scope | Observed Behavior | Status |
|---|---|---|---|---|
| `DEP-001` | Wildcard CORS Rejection | `admin_origin="*"`, `chatbot_origin="https://*.example.com"` | Pydantic validation rejected both: `"wildcard CORS origins are not allowed"` | **PASS** |
| `DEP-002` | Malformed Origin URLs | Injected `javascript:alert(1)` scheme | Rejected by `AnyHttpUrl` validation | **PASS** |
| `DEP-003` | Safe Production Defaults | Inspect default config values in `Settings` | `debug=False`, `WAL=True`, `auto_backup=True`, `audit=True` verified | **PASS** |
| `DEP-004` | Python Dependency Pinning | Audit `pyproject.toml` dependencies | 100% of runtime dependencies bounded with upper and lower limits | **PASS** |
| `DEP-005` | Frontend Dependency Pinning | Audit `apps/admin-dashboard/package.json` | React (19.2.8), Vite (8.1.5) pinned to exact versions, 0 wildcards | **PASS** |
| `DEP-006` | Filesystem Containment | Path outside `allowed_data_dir` without external flag | Pydantic validation rejected path escaping allowed data boundary | **PASS** |
| `DEP-007` | Secret Encryption Fail-Closed | Missing `BRUD_SECRET_ENCRYPTION_KEY` | Raised `EncryptionUnavailableError`, zero plaintext secrets written | **PASS** |

---

## 3. Detailed Audit Findings

### 3.1 Python Dependencies (`pyproject.toml`)
- `fastapi>=0.115,<0.116`
- `uvicorn[standard]>=0.34,<0.35`
- `pydantic-settings>=2.7,<3.0`
- `pwdlib[argon2]>=0.2,<1.0`
- `python-multipart>=0.0.20,<1.0`
- `PyMuPDF>=1.24,<2.0`
- `pytesseract>=0.3.13,<1.0`
- `Pillow>=10.4,<12.0`
- `sentencepiece>=0.2,<0.3`
- `cryptography>=44,<50`
- `torch>=2.13,<3.0`
- `numpy~=2.5`
- `python-docx>=1.1,<2.0`
- `llama-cpp-python>=0.3,<0.4`
- `gguf>=0.19,<0.20`
*No unpinned or wildcard dependencies exist.*

### 3.2 Frontend Dependencies (`apps/admin-dashboard/package.json`)
- React 19.2.8 and Vite 8.1.5 are pinned without floating ranges (`^` or `~`), ensuring deterministic frontend bundle builds.

### 3.3 Configuration Hardening
- `debug` is hard-coded to `False` in default settings.
- All secrets are excluded from Pydantic `repr` / serialized model dumps (`exclude=True`).

---

## 4. Architectural Invariant Compliance
- **G10 (Zero Secret Leakage):** Secrets encrypted with Fernet; missing keys fail closed.
- **G11 (Fail-Closed Governance):** Unvalidated origins, unconfined filesystem paths, and malformed configurations fail closed at startup.

---

## 5. Certification Status
**PHASE 15.9 STATUS: CERTIFIED PASS**  
Evidence recorded from live pytest execution (`test_p15_dependency_config.py` — 7/7 passed in 2.99s, `pip check` — 0 errors).
