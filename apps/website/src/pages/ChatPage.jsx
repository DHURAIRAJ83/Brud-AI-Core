import CanonicalChatPage from '@chatbot/pages/ChatPage.jsx'
import '@chatbot/index.css'

// ============================================================
// PUBLIC CHAT PAGE — P8-04 SINGLE-ORIGIN INTEGRATION
// ============================================================
//
// ARCHITECTURE DECISION (P8-04):
//
// Native Component Integration:
// The canonical chat interface from apps/chatbot/src/pages/ChatPage.jsx
// is directly mounted on the /chat route within the public website SPA.
//
// The previous Phase 7 <iframe> stopgap is completely RETIRED:
//   - Zero iframe boundaries
//   - Unified sessionStorage under the top-level origin
//   - Zero duplication of chat pipeline or components
//   - Perfect mobile responsiveness and keyboard viewport handling
//   - Enables strict X-Frame-Options: DENY across all public routes
// ============================================================

export default function ChatPage() {
  return (
    <div className="website-chat-container" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - var(--nav-height))' }}>
      {/* Integration notice */}
      <div className="container" style={{ paddingTop: 'var(--space-4)', paddingBottom: 'var(--space-2)', flexShrink: 0 }}>
        <div className="chat-integration-notice">
          <p>
            <strong style={{ color: 'var(--color-text-accent)' }}>Public Chat</strong>
            {' — '}
            Powered by the Brud AI canonical chat pipeline. Supports Tamil, English, and Tanglish.
            No account required.
          </p>
        </div>
      </div>

      {/* Canonical Chatbot — Native Component Integration (Zero iframe) */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', paddingInline: 'var(--space-4)', paddingBottom: 'var(--space-4)' }}>
        <CanonicalChatPage />
      </div>
    </div>
  )
}
