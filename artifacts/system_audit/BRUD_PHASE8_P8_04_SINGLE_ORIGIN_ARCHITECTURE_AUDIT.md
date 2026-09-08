# BRUD PHASE 8 — P8-04 SINGLE-ORIGIN ARCHITECTURE AUDIT
# COMPREHENSIVE ARCHITECTURE & DEPLOYMENT TOPOLOGY AUDIT

**Phase:** Phase 8 Subphase 4 (P8-04-A: Single-Origin Architecture Audit)  
**Date:** 2026-09-08  
**Git Baseline:** `03119a55b948681a98d377e089bdcfdb3e2338ec` (`v1.1.0-p8-03`)  
**Phase 6 Baseline:** `v1.0.0-phase6` (`a0284a90d67395df327001b3b4deb7aa779f0715`) — FROZEN & INTACT  
**Phase 7 Baseline:** `v1.1.0-p7-02` (`f2a608ed1c0f6bddd0277296eb32c3cfd8f78758`) — FROZEN & INTACT  
**Target:** Single-Origin Topology, iframe Retirement Strategy, and Cross-Origin Storage Elimination  
**Status:** ✅ **AUDIT COMPLETE — AWAITING P8-04-B AUTHORIZATION (HARD STOP)**

---

## 1. Executive Summary

In Phase 8 Subphases P8-01 through P8-03, Brud AI established a production-grade anonymous session security model:
1. **P8-01:** Audited conversation ownership, cryptographic requirements, and storage boundaries.
2. **P8-02:** Implemented backend anonymous session endpoints (`/api/chat/session`, `/api/chat/session/{id}/messages`, `/api/chat/session/{id}/clear`), 256-bit SHA-256 hashed session tokens, rolling 24h TTL, 7-day hard expiry, and IDOR protection.
3. **P8-03:** Integrated the session lifecycle into `apps/chatbot`, verifying in headless Chromium that anonymous tokens, history restoration, "New Chat", "Clear Chat", and expiry recovery function seamlessly.

However, the public website (`apps/website`) currently accesses the chatbot via an `<iframe>` embedding (`http://127.0.0.1:5173` in development, or cross-port iframe). 

Because **browser `sessionStorage` is strictly scoped to the origin of the document accessing it**, running the chatbot inside an iframe isolates `sessionStorage` to the iframe's origin. Transitioning from an iframe embedding to a **Single-Origin Deployment** fundamentally alters the security context, storage boundary, routing behavior, and deployment topology.

This audit analyzes the **11 mandatory technical dimensions** required to safely retire the iframe and achieve unified single-origin deployment without risking regressions, duplicate pipelines, or admin security leaks.

---

## 2. Current Architecture vs. Target Single-Origin Topology

### 2.1 Current Development Topology (Dual-Port / Iframe Embedding)

```
Browser Top-Level Window (Origin: http://127.0.0.1:5175 - apps/website)
  │
  ├── Navigates to /chat
  └── Renders <iframe src="http://127.0.0.1:5173" />
        │
        └── Iframe Window (Origin: http://127.0.0.1:5173 - apps/chatbot)
              ├── sessionStorage ['brud_anon_conversation_id', 'brud_anon_session_token']
              │     (Scoped ONLY to http://127.0.0.1:5173)
              └── fetch('/api/chat') -> Proxied via Vite to http://127.0.0.1:8000
```

**Limitations of Current State:**
- Two distinct browser origins in development (`:5175` and `:5173`).
- Storage partitioning: Top-level window cannot read iframe's session; iframe cannot sync state with main app.
- Mobile keyboard and layout issues: nested viewport scrolling within iframe on iOS/Android.
- Clickjacking surface: Chatbot must allow iframe embedding (`frame-ancestors`), preventing strict `X-Frame-Options: DENY`.

---

### 2.2 Target Single-Origin Topology (Production & Unified Dev)

```
Public Domain: https://brud.ai (Single Origin)
  │
  ├── /                ──▶ Public Website SPA (apps/website)
  ├── /features, /faq  ──▶ Public Website Pages
  ├── /chat            ──▶ Native Canonical Chat (No iframe)
  └── /api/*           ──▶ Reverse Proxy ──▶ FastAPI Backend (127.0.0.1:8000)

Admin Domain: https://admin.brud.ai (Completely Isolated Origin)
  │
  ├── /                ──▶ Admin Dashboard SPA (apps/admin-dashboard)
  └── /api/admin/*     ──▶ Reverse Proxy ──▶ FastAPI Backend (127.0.0.1:8000)
```

**Key Advantages:**
- Zero iframe boundaries: native DOM rendering, instant page transitions, perfect mobile responsiveness.
- Unified `sessionStorage`: anonymous session tokens persist cleanly across site navigation in the same tab.
- Enables strict anti-framing policy: `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'` can be enforced everywhere on the public site.
- Zero CORS overhead: all browser requests are same-origin (`https://brud.ai`).

---

## 3. Deep Audit Across 11 Mandatory Dimensions

### 3.1 Website → iframe → Chatbot → Backend Routing
- **Current State:**
  - `apps/website/src/pages/ChatPage.jsx` renders an `<iframe>` pointing to `VITE_CHATBOT_URL` (default `http://127.0.0.1:5173`).
  - Loading timeouts (6s fallback to "Chat Unavailable" state) are managed via `iframe.addEventListener('load')`.
- **Findings:**
  - The iframe was an intentional Phase 7 zero-duplication stopgap.
  - While it prevented code duplication between `apps/website` and `apps/chatbot`, it introduced nested layout scrollbars, postMessage / storage boundaries, and iframe lifecycle overhead.
- **Single-Origin Impact:**
  - Direct integration allows `apps/website` to directly render the canonical chat component tree (`ChatPage.jsx`, `ChatInput.jsx`, `ChatMessages.jsx`, `ChatHeader.jsx`) or route directly to the single-origin chat bundle.

---

### 3.2 CORS & Reverse-Proxy Boundaries
- **Current State:**
  - `backend/main.py` uses `CORSMiddleware`:
    ```python
    allow_origins=active_settings.cors_origins  # ["http://localhost:5173", "5174", "5175", "127.0.0.1:..."]
    allow_credentials=True
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"]
    allow_headers=["Content-Type", "Accept", "X-Trace-Id", active_settings.csrf_header_name]
    ```
  - Both `apps/website/vite.config.js` and `apps/chatbot/vite.config.js` proxy `/api` to `http://127.0.0.1:8000`.
- **Findings:**
  - Notice that `backend/main.py` line 104 lists:
    `allow_headers=["Content-Type", "Accept", "X-Trace-Id", active_settings.csrf_header_name]`
    In local dev through Vite proxy, `X-Session-Token` bypasses CORS because Vite proxy makes server-to-server requests. But in direct cross-origin browser fetch without proxy, `X-Session-Token` would require explicit inclusion in CORS `allow_headers`!
- **Single-Origin Impact:**
  - In single-origin production (`https://brud.ai`), all `/api/*` calls are same-origin requests handled by Nginx/Caddy. **CORS is completely bypassed**, eliminating preflight latency and CORS header misconfiguration vulnerabilities.

---

### 3.3 `sessionStorage` Origin Implications
- **Current State:**
  - `apps/chatbot/src/services/api.js` stores:
    - `brud_anon_conversation_id`
    - `brud_anon_session_token`
  - In iframe, these are scoped to the iframe URL origin (`http://127.0.0.1:5173`).
- **Audit Analysis:**
  1. **Cross-Page Navigation Persistence:**
     - In single-origin, if a user navigates `Home -> /chat -> /features -> /chat`, the top-level window maintains the same `sessionStorage`. When returning to `/chat`, the user's active session is hydrated immediately without loss.
  2. **Tab Isolation:**
     - `sessionStorage` is strictly tab-scoped. Opening a new tab automatically creates an independent anonymous session, preventing multi-tab conversation collisions.
  3. **Privacy Zeroing:**
     - When the user clicks "Clear Chat", `clearStoredSession()` clears the keys from `sessionStorage` and `POST /api/chat/session/{id}/clear` closes the session in SQLite. This behavior remains 100% sound under single origin.
  4. **Leakage Risk & Boundary Hygiene:**
     - Could public website pages read anonymous session tokens? The website has zero third-party scripts, zero ads, and zero external trackers. Storing anonymous ephemeral tokens in `sessionStorage` on `brud.ai` carries low privilege risk because anonymous tokens grant access ONLY to that specific anonymous conversation's turns, not administrative or user accounts. To prevent token extraction via XSS, CSP headers, strict dependency hygiene, sanitized DOM rendering, and input/output validation remain mandatory defense-in-depth controls rather than assuming absolute zero risk.

---

### 3.4 API Path Consistency
- **Current State:**
  - `apps/chatbot/src/services/api.js`:
    ```javascript
    const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
    // Paths: /api/health, /api/chat, /api/chat/session, /api/chat/session/:id/messages, /api/chat/session/:id/clear
    ```
  - `apps/website`:
    - Proxies `/api` to backend at `http://127.0.0.1:8000`.
- **Findings:**
  - Both applications consistently use relative paths prefixed with `/api`.
  - In production single origin, Nginx routes `location /api/ { proxy_pass http://127.0.0.1:8000; }`.
  - Zero URL rewriting or path translation is required.

---

### 3.5 Production Reverse-Proxy Topology
- **Current State in `deploy/reverse-proxy/nginx.conf.example`:**
  - Currently exposes `location / { proxy_pass http://127.0.0.1:8000; }` on `<PUBLIC_DOMAIN>`. This was designed when only FastAPI served endpoints.
- **Production Target Nginx Architecture:**
  ```nginx
  # Public Virtual Host (https://brud.ai)
  server {
      server_name brud.ai;
      
      # 1. Static Web & Public Assets (Built Vite dist)
      location / {
          root /var/www/brud-public/dist;
          try_files $uri $uri/ /index.html;
          expires 1h;
      }
      
      # 2. Static Asset Hashing
      location /assets/ {
          root /var/www/brud-public/dist;
          expires 1y;
          add_header Cache-Control "public, immutable";
      }

      # 3. Backend API Gateway
      location /api/ {
          proxy_pass http://127.0.0.1:8000/api/;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
      }
  }

  # Isolated Admin Virtual Host (https://admin.brud.ai)
  server {
      server_name admin.brud.ai;
      
      location / {
          root /var/www/brud-admin/dist;
          try_files $uri $uri/ /index.html;
      }
      
      location /api/ {
          proxy_pass http://127.0.0.1:8001/api/; # Or isolated backend binding
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
      }
  }
  ```

---

### 3.6 `/chat` Routing & Navigation Models
Three implementation models exist for `/chat`:
1. **Model 1: Direct Component Integration (Unified SPA - RECOMMENDED)**
   - `apps/website/src/pages/ChatPage.jsx` replaces the `<iframe>` with the canonical `apps/chatbot` component tree.
   - Pro: Seamless client-side routing via `react-router-dom`; single bundle build; zero layout flashes.
   - Pro: Shared navbar, brand, and theme tokens.
2. **Model 2: Multi-SPA / Sub-Path Mounting (`/chat/`)**
   - Nginx routes `/` to `apps/website` and `/chat` to `apps/chatbot`.
   - Con: Requires hard page reloads when transitioning between website and chat.
   - Con: Potential asset collision if both apps output to `/assets/`.
3. **Model 3: Standalone Chat with Cross-Links**
   - Public website links to `chat.brud.ai` (separate subdomain).
   - Con: Breaks single-origin benefits and fragments user experience.

---

### 3.7 Chatbot Asset Serving & Vite Subpath (`base`) Configuration
- **Current State:**
  - `apps/chatbot/vite.config.js` has no `base` setting (defaults to `/`).
  - Output files: `dist/assets/index-*.js`, `dist/assets/index-*.css`.
- **Audit Finding:**
  - If Model 1 (Unified Component Integration) is chosen, Vite compiles all public routes together; no subpath adjustments needed.
  - If Model 2 is chosen, `apps/chatbot/vite.config.js` would need `base: '/chat/'`, which alters asset resolution and requires test updates.

---

### 3.8 Admin-Origin Isolation (Rule 22 Enforcement)
- **Current State:**
  - Admin Dashboard lives in `apps/admin-dashboard/`.
  - Admin login endpoint: `POST /api/auth/login`.
  - Admin cookies:
    - Name: `brud_admin_session`, `brud_csrf`
    - Scope: `path="/api/admin"`, `samesite="strict"`, `httponly=True`.
- **Audit Findings:**
  1. Direct navigation on public routes to `/admin*` returns 404 in `apps/website` (verified in P7-02 with 87/87 tests).
  2. Public bundles contain zero admin code, zero admin routes, and zero admin state.
  3. Single-origin unification of `/chat` with `apps/website` introduces **no identified admin isolation regression under the audited conditions** because the admin dashboard remains strictly on its own origin (`admin.brud.ai` or port 5174 in dev).
  4. Even if an admin user uses the public chat, the browser's `path="/api/admin"` restriction guarantees the admin session cookie is never sent to `/api/chat` or `/api/chat/session`.

---

### 3.9 CSP & Frame Policy (Clickjacking Defense)
- **Current State:**
  - `backend/core/security_headers_middleware.py`:
    `"X-Frame-Options": "DENY"`
  - `apps/website/src/pages/ChatPage.jsx` embeds `apps/chatbot` via iframe.
- **Audit Finding:**
  - Currently, because `apps/chatbot` is framed by `apps/website`, the chatbot server cannot set `X-Frame-Options: DENY`.
  - **Retiring the iframe enables maximum security posture:**
    Both the public website and backend can enforce:
    ```http
    X-Frame-Options: DENY
    Content-Security-Policy: frame-ancestors 'none';
    ```
    This enables enforcement of a strict anti-framing policy (`frame-ancestors 'none'` / `X-Frame-Options: DENY`), mitigating UI redressing and clickjacking risks across the entire Brud AI public perimeter.

---

### 3.10 Cookie & Token Boundary Analysis
- **Current State:**
  - Public chat sessions use **zero cookies**.
  - Authentication is purely header-based: `X-Session-Token: <64-character-token>`.
  - Token storage is purely in memory and `sessionStorage`.
- **Audit Finding:**
  - Public anonymous chat endpoints use header-based authentication (`X-Session-Token`) rather than ambient credentials (cookies), meaning there is no cookie-based CSRF exposure on `/api/chat` or `/api/chat/session`.
  - Anonymous tokens remain strictly decoupled from admin session cookies (`brud_admin_session`, `brud_csrf`). Because `sessionStorage` tokens could theoretically be accessed if an XSS vulnerability existed, strict Content Security Policy (CSP), dependency hygiene, sanitized DOM rendering, and robust input/output handling must be continuously maintained. Absolute "zero risk" claims are avoided; security is maintained through rigorous defense-in-depth.

---

### 3.11 Port Matrix & Process Topology

| Service | Development Port | Production Exposure | Reverse Proxy Target |
|---|---|---|---|
| **Public Website** | `5175` | Unified Single-Origin (`443`) | Static SPA (`/`) |
| **Canonical Chat** | `5173` (Dev iframe) | Unified into `/chat` (No port) | Native Component on `/chat` |
| **FastAPI Backend** | `8000` | Loopback only (`127.0.0.1:8000`) | `/api/` upstream |
| **Admin Dashboard** | `5174` | Isolated Subdomain (`admin.brud.ai`) | Static SPA (`admin.brud.ai/`) |

---

## 4. Architectural Comparison: Iframe Retirement Options

| Evaluation Metric | Option A: Native Component Integration | Option B: Multi-SPA Reverse Proxy Subpath | Option C: Maintain Iframe Boundary |
|---|---|---|---|
| **Single-Origin Cohesion** | ✅ **100% Unified SPA** | ⚠️ Split SPAs on same domain | ❌ Multi-origin / iframe boundary |
| **sessionStorage Scope** | ✅ Top-level `brud.ai` | ✅ Top-level `brud.ai` | ❌ Isolated to iframe origin |
| **Mobile Responsiveness** | ✅ Perfect (native scroll/keyboard) | ⚠️ Acceptable | ❌ Double scrollbars / iOS bugs |
| **Clickjacking Protection** | ✅ `frame-ancestors 'none'` | ✅ `frame-ancestors 'none'` | ❌ Requires frame permission |
| **Page Navigation Speed** | ✅ Instant (client-side router) | ❌ Hard browser reload | ⚠️ Iframe load delay (up to 6s) |
| **Code Duplication Risk** | ✅ **Zero** (reuses canonical chat components) | ✅ Zero | ✅ Zero |
| **Maintenance Simplicity** | ✅ Single public build | ⚠️ Two public build pipelines | ⚠️ Two dev servers & preview configs |

### Architectural Conclusion:
**Option A (Native Component Integration)** is decisively the superior architecture. It eliminates iframe performance lags, solves mobile viewport bugs, allows strict anti-framing CSPs, and unifies `sessionStorage` while strictly preventing code duplication by directly importing and reusing the canonical chat UI.

---

## 5. Proposed Implementation Roadmap: P8-04-B & P8-04-C

### Gate P8-04-B: Controlled Native Integration
1. **Component Packaging & Import:**
   - Integrate canonical chat components (`ChatPage`, `ChatInput`, `ChatMessages`, `ChatHeader`, `HealthBadge`) into `apps/website/src/pages/ChatPage.jsx`.
   - Preserve standalone execution of `apps/chatbot` for headless/isolated verification.
2. **Unified Session Storage:**
   - Both standalone chatbot and website `/chat` use the identical `api.js` session client and `sessionStorage` keys.
3. **Responsive & Mobile Polish:**
   - Ensure native full-height layout (`100dvh` / mobile browser toolbar handling) without iframe clipping.

### Gate P8-04-C: Browser E2E & Full Regression
1. **Playwright E2E:**
   - Update `apps/website/e2e` tests to verify native `/chat` interaction, session persistence across navigation, and clear-chat functionality.
2. **Security & CSP Verification:**
   - Validate `X-Frame-Options: DENY` and `frame-ancestors 'none'` on public routes.
   - Verify admin isolation remains 100% intact (zero admin routes, zero token contamination).
3. **Build & Release:**
   - Verify all 3 frontend production builds (`website`, `chatbot`, `admin-dashboard`).
   - Run backend test suites (17/17 session tests + 20/20 core tests).
   - Git commit, push, tag `v1.1.0-p8-04`.

---

## 6. Gate Decision & Hard Stop Notice

> **AUDIT DECISION: ✅ P8-04-A COMPLETE & VERIFIED**  
> **Status:** All 11 architectural dimensions audited and documented.  
> **Rule Compliance:** Zero source code changes made; working tree remains 100% clean.  
> **Next Step:** Awaiting user review and explicit authorization for **P8-04-B (Controlled Native Integration)**.  
>  
> 🛑 **HARD STOP ENFORCED.**
