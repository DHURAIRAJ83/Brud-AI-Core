import { useEffect, useRef, useState } from 'react'

// ============================================================
// PUBLIC CHAT PAGE — P7-01 INTEGRATION BOUNDARY
// ============================================================
//
// ARCHITECTURE DECISION (P7-01):
//
// apps/chatbot/ is the canonical, production-qualified public chat
// application. It runs as a standalone Vite/React app at port 5173.
//
// This page (apps/website/src/pages/ChatPage.jsx) does NOT:
//   - Duplicate the chat pipeline
//   - Import from apps/chatbot/
//   - Create a second /api/chat endpoint
//   - Duplicate inference, RAG, or tool logic
//
// Integration approach for P7-01:
//   The chat UI is embedded via an <iframe> pointing to the
//   canonical chatbot app. This is the zero-duplication strategy.
//
//   In production (single-origin deployment):
//     The chatbot is served at the same origin; the iframe src
//     resolves to the same domain.
//
//   In development (dual-port):
//     The iframe points to http://127.0.0.1:5173 (the chatbot).
//
// P8 dependency: anonymous session + unified origin deployment.
// When both apps share an origin, this page will integrate more
// tightly. Until then, the iframe boundary is the correct approach.
//
// ============================================================

const CHATBOT_URL = import.meta.env.VITE_CHATBOT_URL ?? 'http://127.0.0.1:5173'

export default function ChatPage() {
  const iframeRef = useRef(null)
  const [iframeStatus, setIframeStatus] = useState('loading') // 'loading' | 'ready' | 'unavailable'

  useEffect(() => {
    const iframe = iframeRef.current
    if (!iframe) return

    const timer = setTimeout(() => {
      // If the iframe hasn't loaded after 6 s, show unavailable state
      setIframeStatus((s) => (s === 'loading' ? 'unavailable' : s))
    }, 6000)

    function onLoad() {
      clearTimeout(timer)
      setIframeStatus('ready')
    }

    function onError() {
      clearTimeout(timer)
      setIframeStatus('unavailable')
    }

    iframe.addEventListener('load', onLoad)
    iframe.addEventListener('error', onError)
    return () => { clearTimeout(timer); iframe.removeEventListener('load', onLoad); iframe.removeEventListener('error', onError) }
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - var(--nav-height))' }}>
      {/* Integration notice */}
      <div className="container" style={{ paddingTop: 'var(--space-4)', paddingBottom: 'var(--space-2)', flexShrink: 0 }}>
        <div className="chat-integration-notice">
          <p>
            <strong style={{ color: 'var(--color-text-accent)' }}>Public Chat</strong>
            {' — '}
            Powered by the Brud AI canonical chat pipeline. Supports Tamil, English, and Tanglish.
            No account required.{' '}
            {iframeStatus === 'loading' && <span style={{ color: 'var(--color-text-muted)' }}>Connecting…</span>}
            {iframeStatus === 'unavailable' && (
              <span style={{ color: 'var(--color-warning)' }}>
                Chat service is not available right now. Please ensure the backend is running.
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Canonical chatbot — iframe boundary */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', paddingInline: 'var(--space-4)', paddingBottom: 'var(--space-4)' }}>
        {iframeStatus === 'unavailable' ? (
          <div style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--space-4)',
            background: 'var(--color-bg-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
          }}>
            <div style={{ fontSize: '3rem' }} aria-hidden="true">⚠️</div>
            <h2 style={{ fontSize: 'var(--font-size-xl)', color: 'var(--color-text-primary)', margin: 0 }}>
              Chat Unavailable
            </h2>
            <p style={{ color: 'var(--color-text-secondary)', textAlign: 'center', maxWidth: 400, margin: 0, fontSize: 'var(--font-size-sm)' }}>
              The Brud AI chat service could not be reached. This may happen if the backend
              server is not running. Please try again later or consult the{' '}
              <a href="/help">help page</a>.
            </p>
          </div>
        ) : (
          <iframe
            ref={iframeRef}
            src={CHATBOT_URL}
            title="Brud AI Public Chat"
            aria-label="Brud AI public chat interface"
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              borderRadius: 'var(--radius-lg)',
              opacity: iframeStatus === 'ready' ? 1 : 0.4,
              transition: 'opacity 0.3s ease',
            }}
            allow="clipboard-write"
            loading="eager"
          />
        )}
      </div>
    </div>
  )
}
