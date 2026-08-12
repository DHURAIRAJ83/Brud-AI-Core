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

// UI filters over the one governed assistant backend -- never separate
// bots (task rule: "assistant modes are UI filters, not separate
// assistants"). Mirrors core_model.admin_assistant.dashboard_registry
// .ASSISTANT_MODES exactly.
const MODES = [
  { key: 'guide', label: 'Guide' },
  { key: 'data', label: 'Data' },
  { key: 'governance', label: 'Governance' },
  { key: 'rag', label: 'RAG' },
  { key: 'model', label: 'Model' },
  { key: 'system', label: 'System' },
]

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
const MIN_WIDTH = 320
const MAX_WIDTH = 900
const MIN_HEIGHT = 320
const DOCK_WIDTH = 380

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
  const [mode, setMode] = useState('guide')
  const [pagesByNavKey, setPagesByNavKey] = useState({})
  const [pagesLoaded, setPagesLoaded] = useState(false)
  const [llmAvailable, setLlmAvailable] = useState(null)
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
    height: storedLayout?.height ?? 560,
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
      base = { top: '5vh', left: '5vw', right: 'auto', bottom: 'auto', width: '90vw', height: '90vh', maxHeight: '90vh' }
    } else if (layoutMode === 'docked-left') {
      base = { top: 0, left: 0, right: 'auto', bottom: 'auto', width: rect.width || DOCK_WIDTH, height: '100vh', maxHeight: '100vh', borderRadius: 0 }
    } else if (layoutMode === 'docked-right') {
      base = { top: 0, right: 0, left: 'auto', bottom: 'auto', width: rect.width || DOCK_WIDTH, height: '100vh', maxHeight: '100vh', borderRadius: 0 }
    } else if (layoutMode === 'floating' && rect.x != null) {
      base = { top: rect.y, left: rect.x, right: 'auto', bottom: 'auto', width: rect.width, height: rect.height, maxHeight: rect.height }
    } else {
      return undefined
    }
    if (minimized) {
      const { height, maxHeight, ...rest } = base
      return rest
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
    // MB-45: reads the same runtime-resolution state that actually
    // answers /chat and /grounded-chat, instead of the old Phase-8
    // health check (a different, unrelated backend) -- see docs/audit
    // /MB45_WIDGET_BACKEND_CONSOLIDATION_2026_08_11.md.
    miniBrainWidgetHealth().then((data) => setLlmAvailable(data.available)).catch(() => setLlmAvailable(false))
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

  // The launcher button only exists in the DOM while the card is closed,
  // so `launcherRef` cannot be focused synchronously inside the handler
  // that closes the card (the button hasn't been (re)rendered yet at that
  // point) -- this effect runs after the close has actually committed,
  // and `hasOpenedRef` keeps it from stealing focus on first mount.
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
        const focusable = cardRef.current.querySelectorAll('button, input, textarea, [tabindex]:not([tabindex="-1"])')
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
        Assistant
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
          <strong>Brud AI Assistant</strong>
        </div>
        <div className="assistant-card-header-actions">
          <button
            type="button"
            aria-label="Dock left"
            aria-pressed={layoutMode === 'docked-left'}
            onClick={dockLeft}
          >⇤</button>
          <button
            type="button"
            aria-label="Dock right"
            aria-pressed={layoutMode === 'docked-right'}
            onClick={dockRight}
          >⇥</button>
          <button
            type="button"
            aria-label={layoutMode === 'fullscreen' ? 'Exit large chat mode' : 'Enter large chat mode'}
            aria-pressed={layoutMode === 'fullscreen'}
            onClick={toggleFullScreen}
          >⛶</button>
          <button
            type="button"
            aria-label={minimized ? 'Restore Admin Assistant' : 'Minimize Admin Assistant'}
            aria-expanded={!minimized}
            onClick={() => setMinimized((value) => !value)}
          >{minimized ? '▢' : '_'}</button>
          <button
            type="button"
            aria-label="Close Admin Assistant"
            onClick={() => setOpen(false)}
          >×</button>
        </div>
      </header>

      {!minimized && <>
        <nav className="assistant-mode-row" aria-label="Assistant mode filter">
          {MODES.map((item) => (
            <button
              key={item.key}
              type="button"
              className={mode === item.key ? 'active' : ''}
              aria-pressed={mode === item.key}
              onClick={() => setMode(item.key)}
            >{item.label}</button>
          ))}
        </nav>

        <div className="assistant-language-row">
          <label htmlFor="assistant-response-language">Reply language</label>
          <select
            id="assistant-response-language"
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
          <div className="notice error-notice assistant-language-error">{languageError}</div>
        )}

        {onOpenMiniBrainAssistant && (
          <div className="assistant-mini-brain-link-row">
            <button type="button" className="assistant-mini-brain-link" onClick={onOpenMiniBrainAssistant}>
              Open Mini Brain Assistant / Mini Brain Assistant திற
            </button>
          </div>
        )}

        {llmAvailable === false && (
          <div className="assistant-llm-notice">
            AI response generation is unavailable right now. Page help and pending-work
            guidance still work.
          </div>
        )}
      </>}

      {/* Kept mounted (never conditionally removed) across minimize/restore,
          hidden with CSS instead -- ChatPanel owns its own session/message
          state now, so unmounting it on minimize would silently discard an
          in-progress conversation the moment an admin collapses the card. */}
      <div style={minimized ? { display: 'none' } : undefined}>
        <ChatPanel
          variant="compact"
          admin={admin}
          onFeedback={handleFeedback}
          toast={toast}
          suggestions={SUGGESTIONS}
          emptyGreeting={NO_ADMIN_GREETING}
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
