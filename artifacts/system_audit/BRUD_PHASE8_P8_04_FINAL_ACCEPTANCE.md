# BRUD AI — Phase 8 Subphase 4 (P8-04) Single-Origin Architecture & Deployment Acceptance Report

**Phase:** Phase 8 Subphase 4 (P8-04: Single-Origin Deployment & Iframe Retirement)  
**Date:** 2026-09-08  
**Baseline Git Tag:** `v1.1.0-p8-03` (`03119a5`)  
**Release Git Tag:** `v1.1.0-p8-04`  
**Status:** ✅ **P8-04 COMPLETE — ALL CRITICAL GATES PASSED (100%)**

---

## 1. Executive Summary

Phase 8 Subphase 4 (P8-04) officially achieves **Single-Origin Deployment & Iframe Retirement** for Brud AI. 
Following the controlled gate workflow (P8-04-A Architecture Audit → P8-04-B Native Component Integration → P8-04-C Browser E2E & Full Security Regression), the previous Phase 7 `<iframe>` stopgap has been completely retired in favor of native component mounting on `/chat`.

All 5 core commitments and invariants have been verified:
1. **Zero Component Duplication:** Canonical chat components from `apps/chatbot` are directly reused via Vite path aliasing (`@chatbot`). Zero code duplication exists between `apps/website` and `apps/chatbot`.
2. **Iframe Fully Retired:** Zero `<iframe>` elements exist in the DOM on `/chat`.
3. **Single-Origin Session Continuity:** `sessionStorage` anonymous tokens (`brud_anon_session_token`, `brud_anon_conversation_id`) reside natively under the top-level origin (`https://brud.ai`), maintaining seamless session continuity across client-side router navigation (`/` ↔ `/features` ↔ `/chat`) and page reloads.
4. **Admin Isolation Preserved:** Admin dashboard remains strictly isolated on its dedicated origin (`admin.brud.ai`). Zero admin code, routes, or cookies leak into the public website bundle.
5. **Backend Invariant Maintained:** Exactly 0 diff in `backend/` and database migrations.

---

## 2. P8-04 Verification Matrix

| Gate / Component | Verification Command | Result | Evidence / Details |
|---|---|---|---|
| **P8-04-A Audit** | Architecture & Topology Audit | ✅ PASS | 11/11 architectural dimensions audited & approved |
| **P8-04-B Native Mount** | Vite `@chatbot` Aliasing & Iframe Removal | ✅ PASS | Direct import of canonical `ChatPage`, zero copy-paste |
| **Playwright Browser E2E** | `node scratch/p8_04_browser_e2e_verification.js` | ✅ PASS | 7/7 real headless Chromium scenarios (100% pass) |
| **Zero Iframe Audit** | Real DOM locator check (`iframe = 0`) | ✅ PASS | Exactly 0 iframes rendered on `/chat` |
| **Session Continuity** | `/` → `/chat` → `/features` → `/chat` | ✅ PASS | Session tokens persisted cleanly across SPA route changes |
| **History Hydration** | Hard browser reload on `/chat` | ✅ PASS | Backend conversation history restored seamlessly |
| **Lifecycle Controls** | New Chat & Clear Chat | ✅ PASS | Reset and deactivation functions verified natively |
| **Token Recovery** | Stale / expired session token handling | ✅ PASS | Auto-recovery generating fresh anonymous session token |
| **Anti-Framing Policy** | `X-Frame-Options: DENY` | ✅ PASS | Verified across all backend endpoints |
| **Admin Route Isolation** | `/admin`, `/dashboard`, `/admin-login` | ✅ PASS | All return 404 on public website origin |
| **Token Boundary** | Public `document.cookie` inspection | ✅ PASS | Empty; zero admin session cookie leakage |
| **Bundle Leakage** | `grep -rn '/admin-login' apps/website/dist` | ✅ PASS | 0 results (zero admin routes in public bundle) |
| **Website Unit Tests** | `npm --prefix apps/website run test -- --run` | ✅ PASS | **23 / 23 PASS** (1.73s) |
| **Website Production Build** | `npm --prefix apps/website run build` | ✅ PASS | `vite build` PASS (274ms; 282.97 kB) |
| **Chatbot Unit Tests** | `npm --prefix apps/chatbot run test -- --run` | ✅ PASS | **38 / 38 PASS** (3.15s) |
| **Chatbot Production Build** | `npm --prefix apps/chatbot run build` | ✅ PASS | `vite build` PASS (264ms; 202.19 kB) |
| **Admin Dashboard Build** | `npm --prefix apps/admin-dashboard run build` | ✅ PASS | `vite build` PASS (1.30s; zero regression) |
| **Backend Session Suite** | `pytest test_anonymous_chat_session.py` | ✅ PASS | **17 / 17 PASS** (94.68s) |
| **Backend API & Security** | `pytest test_api.py test_public_chat_security.py` | ✅ PASS | **20 / 20 PASS** (95.59s) |

---

## 3. Changed Files & Diff Audit

### 3.1 Working Tree Diff Summary (`git diff --stat`)

```
 apps/website/src/pages/ChatPage.jsx   | 121 +++++-----------------------------
 apps/website/src/test/routes.test.jsx |   7 ++
 apps/website/src/test/setup.js        |  14 ++++
 apps/website/vite.config.js           |  15 +++++
 4 files changed, 53 insertions(+), 104 deletions(-)
```

### 3.2 Invariant Verification Across Components

```bash
$ git diff --stat apps/admin-dashboard apps/chatbot backend
# Output: (Empty - Exact 0 Diff)
```

- `backend/`: **0 lines changed**
- `backend/database/`: **0 lines changed**
- `apps/admin-dashboard/`: **0 lines changed**
- `apps/chatbot/`: **0 lines changed**
- `apps/website/`: Only integration wiring and unit test assertions modified (+53 / -104 lines)

---

## 4. Architectural Outcomes

1. **Clean Monorepo Sharing:** `apps/website` imports canonical components directly from `apps/chatbot/src/pages/ChatPage.jsx`. Monorepo React multi-instance deduplication is enforced via Vite config.
2. **Superior UX & Responsiveness:** Chat is rendered directly in the website DOM with native viewport calculations, zero cross-frame event latency, and zero scrollbar jumping.
3. **No Identified Admin Isolation Regression:** The admin dashboard remains strictly hosted on its dedicated origin (`admin.brud.ai`), with zero bundle contamination and strict cookie path scoping.
4. **Enhanced Anti-Framing Protection:** Elimination of cross-origin chat embedding allows public website perimeter to enforce strict anti-framing policies (`X-Frame-Options: DENY`, `frame-ancestors 'none'`).

---

## 5. Release Qualification Sign-Off

All acceptance criteria for **Phase 8 Subphase 4 (P8-04)** are completely satisfied. The release commit and tag `v1.1.0-p8-04` are authorized for creation.
