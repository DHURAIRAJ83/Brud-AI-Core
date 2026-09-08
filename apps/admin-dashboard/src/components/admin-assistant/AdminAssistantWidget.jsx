import { useEffect, useRef, useState } from 'react'
import ChatPanel from '../chat/ChatPanel.jsx'
import { useToast } from '../Toast.jsx'
import {
  assistantLanguagePreference,
  assistantPages,
  miniBrainWidgetHealth,
  setAssistantLanguagePreference,
  submitAssistantFeedback,
} from '../../services/api.js'

// Mirrors backend.services.admin_assistant_language_service
// .RESPONSE_LANGUAGES exactly -- the saved value stays this exact
// machine enum; only the visible label is localized to the language
// it names (தமிழ் for Tamil, etc.).
const LANGUAGE_OPTIONS = [
  { key: 'tamil', label: 'தமிழ்' },
  { key: 'english', label: 'English' },
  { key: 'tanglish', label: 'Tanglish' },
  { key: 'auto', label: 'Auto' },
]

const SUGGESTIONS = ['How do I use this page?', 'What is pending right now?']
const NO_ADMIN_GREETING = 'Hello. Ask me anything about this dashboard, in Tamil, English, or Tanglish.'

// Hand-rolled drag/resize/dock/maximize -- no new dependency (matches the
// zero-new-runtime-dependency discipline from Phases 1-2). Persisted
// separately from ThemeProvider's own key, same versioned-schema +
// defensive-parse convention.
const LAYOUT_STORAGE_KEY = 'brud-admin-assistant-widget-layout-v1'
const LAYOUT_MODES = ['default', 'floating', 'docked-left', 'docked-right', 'fullscreen']
const MIN_WIDTH = 380
const MAX_WIDTH = 900
const MIN_HEIGHT = 400
const DOCK_WIDTH = 480

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function readStoredLayout() {
  try {
    const raw = localStorage.getItem(LAYOUT_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!LAYOUT_MODES.includes(parsed?.mode)) return null
    return parsed
  } catch {
    return null
  }
}

function writeStoredLayout(layout) {
  try {
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify({ version: 1, ...layout }))
  } catch {
    // Layout persistence is best-effort only -- never blocks the widget.
  }
}

export default function AdminAssistantWidget({ active, onNavigate, onOpenMiniBrainAssistant, admin }) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const [pagesByNavKey, setPagesByNavKey] = useState({})
  const [pagesLoaded, setPagesLoaded] = useState(false)
  const [llmAvailable, setLlmAvailable] = useState(null)
  const [healthInfo, setHealthInfo] = useState({ available: null, backend_type: 'auto', current_model: null })
  const [language, setLanguage] = useState('auto')
  const [languageLoaded, setLanguageLoaded] = useState(false)
  const [languageSaving, setLanguageSaving] = useState(false)
  const [languageError, setLanguageError] = useState('')
  const launcherRef = useRef(null)
  const cardRef = useRef(null)

  const storedLayout = useRef(readStoredLayout()).current
  const [layoutMode, setLayoutMode] = useState(storedLayout?.mode ?? 'default')
  const [rect, setRect] = useState({
    x: storedLayout?.x ?? null,
    y: storedLayout?.y ?? null,
    width: storedLayout?.width ?? DOCK_WIDTH,
    height: storedLayout?.height ?? 640,
  })
  const rectRef = useRef(rect)
  const dragStateRef = useRef(null)
  const resizeStateRef = useRef(null)

  function updateRect(next) {
    rectRef.current = next
    setRect(next)
  }

  function beginDrag(event) {
    event.currentTarget.setPointerCapture?.(event.pointerId)
    const cardRect = cardRef.current.getBoundingClientRect()
    dragStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startLeft: cardRect.left,
      startTop: cardRect.top,
      width: rectRef.current.width || cardRect.width,
      height: rectRef.current.height || cardRect.height,
    }
  }

  function onDragMove(event) {
    const drag = dragStateRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    const nextX = clamp(drag.startLeft + (event.clientX - drag.startClientX), 0, Math.max(0, window.innerWidth - drag.width))
    const nextY = clamp(drag.startTop + (event.clientY - drag.startClientY), 0, Math.max(0, window.innerHeight - drag.height))
    setLayoutMode('floating')
    updateRect({ x: nextX, y: nextY, width: drag.width, height: drag.height })
  }

  function endDrag(event) {
    const drag = dragStateRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    dragStateRef.current = null
    writeStoredLayout({ mode: 'floating', ...rectRef.current })
  }

  function beginResize(event) {
    event.stopPropagation()
    event.currentTarget.setPointerCapture?.(event.pointerId)
    const cardRect = cardRef.current.getBoundingClientRect()
    resizeStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startWidth: rectRef.current.width || cardRect.width,
      startHeight: rectRef.current.height || cardRect.height,
      left: rectRef.current.x ?? cardRect.left,
      top: rectRef.current.y ?? cardRect.top,
    }
  }

  function onResizeMove(event) {
    const resize = resizeStateRef.current
    if (!resize || resize.pointerId !== event.pointerId) return
    const nextWidth = clamp(resize.startWidth + (event.clientX - resize.startClientX), MIN_WIDTH, Math.min(MAX_WIDTH, window.innerWidth - resize.left - 8))
    const nextHeight = clamp(resize.startHeight + (event.clientY - resize.startClientY), MIN_HEIGHT, window.innerHeight - resize.top - 8)
    setLayoutMode('floating')
    updateRect({ x: resize.left, y: resize.top, width: nextWidth, height: nextHeight })
  }

  function endResize(event) {
    const resize = resizeStateRef.current
    if (!resize || resize.pointerId !== event.pointerId) return
    resizeStateRef.current = null
    writeStoredLayout({ mode: 'floating', ...rectRef.current })
  }

  function dockLeft() {
    setLayoutMode('docked-left')
    writeStoredLayout({ mode: 'docked-left', ...rectRef.current })
  }

  function dockRight() {
    setLayoutMode('docked-right')
    writeStoredLayout({ mode: 'docked-right', ...rectRef.current })
  }

  function toggleFullScreen() {
    setLayoutMode((current) => {
      const next = current === 'fullscreen' ? 'default' : 'fullscreen'
      writeStoredLayout({ mode: next, ...rectRef.current })
      return next
    })
  }

  function widgetStyle() {
    let base
    if (layoutMode === 'fullscreen') {
      base = { top: '3vh', left: '3vw', right: 'auto', bottom: 'auto', width: '94vw', height: '94vh', maxHeight: '94vh', zIndex: 1000 }
    } else if (layoutMode === 'docked-left') {
      base = { top: 0, left: 0, right: 'auto', bottom: 0, width: rect.width || DOCK_WIDTH, height: '100vh', maxHeight: '100vh', borderRadius: 0, zIndex: 1000 }
    } else if (layoutMode === 'docked-right') {
      base = { top: 0, right: 0, left: 'auto', bottom: 0, width: rect.width || DOCK_WIDTH, height: '100vh', maxHeight: '100vh', borderRadius: 0, zIndex: 1000 }
    } else if (layoutMode === 'floating' && rect.x != null) {
      base = { top: rect.y, left: rect.x, right: 'auto', bottom: 'auto', width: rect.width, height: rect.height, maxHeight: rect.height, zIndex: 1000 }
    } else {
      // Default: Right-side full-height workspace drawer
      base = { top: 0, right: 0, bottom: 0, height: '100vh', maxHeight: '100vh', width: 'min(480px, 92vw)', borderRadius: 0, zIndex: 1000 }
    }
    if (minimized) {
      const { height, maxHeight, ...rest } = base
      return { ...rest, top: 'auto', bottom: '24px', right: '24px', width: '320px', height: 'auto', borderRadius: '12px' }
    }
    return base
  }

  useEffect(() => {
    if (!open || pagesLoaded) return
    assistantPages()
      .then((data) => {
        const byNavKey = {}
        for (const item of data.items) byNavKey[item.nav_key] = item
        setPagesByNavKey(byNavKey)
      })
      .catch(() => {})
      .finally(() => setPagesLoaded(true))

    miniBrainWidgetHealth()
      .then((data) => {
        setLlmAvailable(data.available)
        setHealthInfo({
          available: data.available,
          backend_type: data.backend_type || 'auto',
          current_model: data.current_model || null,
        })
      })
      .catch(() => {
        setLlmAvailable(false)
        setHealthInfo({ available: false, backend_type: 'unavailable', current_model: null })
      })
  }, [open, pagesLoaded])

  useEffect(() => {
    if (!open || languageLoaded) return
    assistantLanguagePreference()
      .then((data) => setLanguage(data.response_language))
      .catch(() => {})
      .finally(() => setLanguageLoaded(true))
  }, [open, languageLoaded])

  async function changeLanguage(nextLanguage) {
    const previous = language
    setLanguage(nextLanguage)
    setLanguageSaving(true)
    setLanguageError('')
    try {
      await setAssistantLanguagePreference(nextLanguage)
    } catch (reason) {
      setLanguage(previous)
      setLanguageError(reason.message)
    } finally {
      setLanguageSaving(false)
    }
  }

  const hasOpenedRef = useRef(false)
  useEffect(() => {
    if (open) {
      hasOpenedRef.current = true
    } else if (hasOpenedRef.current) {
      launcherRef.current?.focus()
    }
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        setOpen(false)
        return
      }
      if (event.key === 'Tab' && cardRef.current) {
        const focusable = cardRef.current.querySelectorAll('button, input, textarea, select, [tabindex]:not([tabindex="-1"])')
        if (!focusable.length) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open])

  const currentPage = pagesByNavKey[active]
  const currentPageId = currentPage?.page_id ?? 'overview'

  async function handleFeedback(message, rating) {
    await submitAssistantFeedback({ rating, page_id: currentPageId, message_reference: message.id })
  }

  if (!open) {
    return (
      <button
        ref={launcherRef}
        type="button"
        className="assistant-launcher"
        aria-label="Open Admin Assistant"
        onClick={() => { setOpen(true); setMinimized(false) }}
      >
        <span style={{ marginRight: '6px' }}>🧠</span> Assistant
      </button>
    )
  }

  return (
    <div
      className={`assistant-card ${minimized ? 'assistant-card-minimized' : ''} ${layoutMode !== 'default' ? `assistant-card-${layoutMode}` : ''}`}
      style={widgetStyle()}
      ref={cardRef}
      role="dialog"
      aria-label="Brud AI Admin Assistant"
    >
      <header className="assistant-card-header">
        <div
          className="assistant-drag-handle"
          onPointerDown={beginDrag}
          onPointerMove={onDragMove}
          onPointerUp={endDrag}
        >
          <div className="assistant-header-icon-box" aria-hidden="true">🧠</div>
          <div className="assistant-header-brand">
            <div className="assistant-header-title-row">
              <strong className="assistant-header-title">Brud AI Assistant</strong>
              <span
                className={`assistant-runtime-badge status-${
                  llmAvailable === false
                    ? 'offline'
                    : healthInfo.backend_type === 'local'
                    ? 'local'
                    : healthInfo.backend_type === 'external'
                    ? 'provider'
                    : 'auto'
                }`}
                title={healthInfo.current_model ? `Active Model: ${healthInfo.current_model}` : undefined}
              >
                <span className="assistant-runtime-dot" aria-hidden="true" />
                {llmAvailable === false
                  ? 'Offline'
                  : healthInfo.backend_type === 'local'
                  ? 'Local LLM'
                  : healthInfo.backend_type === 'external'
                  ? 'Provider'
                  : 'Auto Routing'}
              </span>
            </div>
            <span className="assistant-header-subtitle">Mini Brain • Admin Intelligence Layer</span>
          </div>
        </div>
        <div className="assistant-card-header-actions">
          <button
            type="button"
            className="assistant-win-btn"
            aria-label="Dock left"
            aria-pressed={layoutMode === 'docked-left'}
            onClick={dockLeft}
            title="Dock left"
          >
            <span className="assistant-win-icon" aria-hidden="true">⇤</span>
          </button>
          <button
            type="button"
            className="assistant-win-btn"
            aria-label="Dock right"
            aria-pressed={layoutMode === 'docked-right'}
            onClick={dockRight}
            title="Dock right"
          >
            <span className="assistant-win-icon" aria-hidden="true">⇥</span>
          </button>
          <button
            type="button"
            className="assistant-win-btn"
            aria-label={layoutMode === 'fullscreen' ? 'Exit large chat mode' : 'Enter large chat mode'}
            aria-pressed={layoutMode === 'fullscreen'}
            onClick={toggleFullScreen}
            title={layoutMode === 'fullscreen' ? 'Exit large chat mode' : 'Enter large chat mode'}
          >
            <span className="assistant-win-icon" aria-hidden="true">⛶</span>
          </button>
          <button
            type="button"
            className="assistant-win-btn"
            aria-label={minimized ? 'Restore Admin Assistant' : 'Minimize Admin Assistant'}
            aria-expanded={!minimized}
            onClick={() => setMinimized((value) => !value)}
            title={minimized ? 'Restore Admin Assistant' : 'Minimize Admin Assistant'}
          >
            <span className="assistant-win-icon" aria-hidden="true">{minimized ? '▢' : '—'}</span>
          </button>
          <button
            type="button"
            className="assistant-win-btn assistant-win-btn-close"
            aria-label="Close Admin Assistant"
            onClick={() => setOpen(false)}
            title="Close Assistant"
          >
            <span className="assistant-win-icon" aria-hidden="true">✕</span>
          </button>
        </div>
      </header>

      {!minimized && (
        <>
          <div className="assistant-language-row">
            <label htmlFor="assistant-response-language">Reply language</label>
            <select
              id="assistant-response-language"
              className="assistant-lang-select"
              value={language}
              disabled={!languageLoaded || languageSaving}
              onChange={(event) => changeLanguage(event.target.value)}
            >
              {LANGUAGE_OPTIONS.map((item) => (
                <option key={item.key} value={item.key}>{item.label}</option>
              ))}
            </select>
          </div>

          {languageError && (
            <div className="notice error-notice assistant-language-error" style={{ margin: '4px 12px', fontSize: '0.75rem' }}>{languageError}</div>
          )}

          {onOpenMiniBrainAssistant && (
            <div className="assistant-mini-brain-link-row">
              <button
                type="button"
                className="assistant-mini-brain-link"
                onClick={onOpenMiniBrainAssistant}
              >
                <span>Mini Brain Assistant / Mini Brain Assistant திற</span>
                <span className="assistant-mini-brain-arrow" aria-hidden="true">↗</span>
              </button>
            </div>
          )}

          {llmAvailable === false && (
            <div className="assistant-llm-notice">
              <span className="assistant-notice-icon" aria-hidden="true">⚠️</span>
              <span>AI response generation is unavailable right now. Page help and pending-work guidance still work.</span>
            </div>
          )}
        </>
      )}

      {/* Main Workspace: kept mounted to preserve conversation state across minimize */}
      <div style={{ flex: 1, minHeight: 0, display: minimized ? 'none' : 'flex', flexDirection: 'column' }}>
        <ChatPanel
          variant="compact"
          admin={admin}
          onFeedback={handleFeedback}
          toast={toast}
          suggestions={SUGGESTIONS}
          emptyGreeting={NO_ADMIN_GREETING}
          onNavigate={onNavigate}
        />
      </div>

      {layoutMode === 'floating' && !minimized && (
        <div
          className="assistant-resize-handle"
          data-testid="assistant-resize-handle"
          aria-hidden="true"
          onPointerDown={beginResize}
          onPointerMove={onResizeMove}
          onPointerUp={endResize}
        />
      )}
    </div>
  )
}
