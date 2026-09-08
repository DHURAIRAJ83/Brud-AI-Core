# BRUD PHASE 7 — P7-01 PUBLIC WEBSITE FOUNDATION
# FINAL ACCEPTANCE DOCUMENT

**Phase:** P7-01  
**Date:** 2026-09-08  
**Git Branch:** phase-5-performance-polish  
**Git HEAD:** f290954641be92ba052d590a86a1abe2db24f5e7  
**P6 Tag (frozen):** v1.0.0-phase6 (untouched)

---

## 1. Scope

P7-01 implements the Public Website Foundation for Brud AI as a new standalone
application `apps/website/`. Phase 6 is frozen and fully regression-verified.

---

## 2. Architecture

New app: apps/website/ (Vite 8.1.5 + React 19.2.8 + react-router-dom v6, port 5175)

apps/chatbot/          -- Canonical chat UI       (port 5173) -- UNCHANGED
apps/admin-dashboard/  -- Admin portal            (port 5174) -- UNCHANGED
apps/website/          -- Public website [NEW]    (port 5175)
backend/               -- FastAPI API             (port 8000) -- UNCHANGED

Chat Integration: iframe pointing to canonical chatbot (VITE_CHATBOT_URL).
No duplicate inference pipeline. No copied chatbot source files.

---

## 3. Routes

/ -> HomePage
/chat -> ChatPage (iframe boundary to canonical chatbot)
/features -> FeaturesPage
/how-it-works -> HowItWorksPage
/faq -> FaqPage
/desktop -> DesktopPage (Coming Soon)
/privacy -> PrivacyPage
/terms -> TermsPage
/help -> HelpPage
/* -> NotFoundPage (404)

Admin routes NOT registered: /admin -> 404, /admin-login -> 404, /dashboard -> 404

---

## 4. Public / Admin Boundary

Admin routes in public router: None
Admin imports in website src: None (import statements)
Admin nav links in Navbar: None
Admin-dashboard app modified: No (git diff empty)
Backend admin auth modified: No (git diff empty)
Backend authorization: Unchanged (real security boundary)

---

## 5. Security Checks

Hardcoded secrets in website src: None
API keys embedded: None
Private keys in frontend: None
Fake download URLs: None (Desktop buttons are disabled)
Admin routes exposed: None

---

## 6. Test Results

Command: npm test --prefix apps/website
Runner: Vitest v4.1.11
Result: 22/22 PASS

- Public route rendering (10): all pass
- Admin isolation (3): /admin, /admin-login, /dashboard -> 404
- Navbar content (2): public links present, admin links absent
- HomePage content (3): brand, Start Chat, Explore Features
- ChatPage architecture (2): renders, shows Public Chat identification
- DesktopPage (2): Coming Soon badge, no enabled download

---

## 7. Build Results

apps/website npm run build:         PASS (32 modules, 448ms)
apps/chatbot npm run build:         PASS (regression)
apps/admin-dashboard npm run build: PASS (regression)

---

## 8. Audit Results

Total checks: 34
Pass: 34
Fail: 0
Warn: 0
Test pass: 22
Test fail: 0

VERDICT: PASS

---

## 9. Known Limitations / P8 Dependencies

- Anonymous session / account architecture: deferred to P8/P9
- Desktop application binary: not yet built
- Single-origin deployment: deferred to P8
- Finalized legal privacy/retention policy: deferred
- VITE_CHATBOT_URL must be configured in production environment

---

## 10. Git State

Branch: phase-5-performance-polish
HEAD SHA: f290954641be92ba052d590a86a1abe2db24f5e7
Working tree: only apps/website/ and scratch/ added (new files only)
v1.0.0-phase6 tag: intact

---

## 11. Final Verdict

P7-01 PASS

All 34 audit checks pass.
22/22 unit tests pass.
All 3 app builds succeed.
Admin security boundary verified.
No duplicate chat pipeline.
No existing P6 functionality damaged.
v1.0.0-phase6 tag intact.

STOP -- Awaiting explicit authorization for P7-02.
