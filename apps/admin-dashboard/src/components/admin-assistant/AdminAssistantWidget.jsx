import { useEffect, useRef, useState } from 'react'
import {
  assistantHealth,
  assistantLanguagePreference,
  assistantPages,
  sendAssistantChatMessage,
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

function uid() {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function MessageBubble({ message, onNavigate, onFeedback }) {
  const isUser = message.role === 'user'
  return (
    <div className={`assistant-message ${isUser ? 'assistant-message-user' : 'assistant-message-bot'}`}>
      <p>{message.text}</p>
      {message.navigationTarget && (
        <button
          type="button"
          className="assistant-nav-button"
          onClick={() => onNavigate(message.navigationTarget.nav_key)}
        >
          Go to {message.navigationTarget.nav_key}
        </button>
      )}
      {!isUser && !message.pending && (
        message.feedbackGiven ? (
          <small className="assistant-feedback-thanks">Thanks for the feedback.</small>
        ) : (
          <div className="assistant-feedback-row">
            <button type="button" onClick={() => onFeedback(message, 'helpful')} aria-label="Mark helpful">Helpful</button>
            <button type="button" onClick={() => onFeedback(message, 'not_helpful')} aria-label="Mark not helpful">Not helpful</button>
          </div>
        )
      )}
    </div>
  )
}

export default function AdminAssistantWidget({ active, onNavigate, admin }) {
  const [open, setOpen] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const [mode, setMode] = useState('guide')
  const [pagesByNavKey, setPagesByNavKey] = useState({})
  const [pagesLoaded, setPagesLoaded] = useState(false)
  const [llmAvailable, setLlmAvailable] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [language, setLanguage] = useState('auto')
  const [languageLoaded, setLanguageLoaded] = useState(false)
  const [languageSaving, setLanguageSaving] = useState(false)
  const [languageError, setLanguageError] = useState('')
  const inputRef = useRef(null)
  const launcherRef = useRef(null)
  const cardRef = useRef(null)

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
    assistantHealth().then((data) => setLlmAvailable(data.llm_available)).catch(() => setLlmAvailable(false))
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

  useEffect(() => {
    if (open && !minimized) inputRef.current?.focus()
  }, [open, minimized])

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

  async function send(text) {
    const trimmed = (text ?? input).trim()
    if (!trimmed || sending) return
    setError('')
    setInput('')
    const userMessage = { id: uid(), role: 'user', text: trimmed }
    setMessages((previous) => [...previous, userMessage])
    setSending(true)
    try {
      const response = await sendAssistantChatMessage({
        message: trimmed,
        page_id: currentPageId,
        mode,
      })
      setMessages((previous) => [
        ...previous,
        {
          id: uid(),
          role: 'assistant',
          text: response.answer,
          navigationTarget: response.navigation_target,
          status: response.status,
        },
      ])
    } catch (reason) {
      setError(reason.message)
    } finally {
      setSending(false)
    }
  }

  async function giveFeedback(message, rating) {
    setMessages((previous) => previous.map((item) => (item.id === message.id ? { ...item, feedbackGiven: true } : item)))
    try {
      await submitAssistantFeedback({ rating, page_id: currentPageId, message_reference: message.id })
    } catch {
      // Feedback is best-effort; the UI already shows a thank-you and never blocks the chat.
    }
  }

  function handleNavigate(navKey) {
    onNavigate(navKey)
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
    <div className={`assistant-card ${minimized ? 'assistant-card-minimized' : ''}`} ref={cardRef} role="dialog" aria-label="Brud AI Admin Assistant">
      <header className="assistant-card-header">
        <strong>Brud AI Assistant</strong>
        <div className="assistant-card-header-actions">
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

        {llmAvailable === false && (
          <div className="assistant-llm-notice">
            AI response generation is unavailable right now. Page help and pending-work
            guidance still work.
          </div>
        )}

        <div className="assistant-messages">
          {!pagesLoaded && messages.length === 0 && (
            <p className="assistant-loading-notice">Loading dashboard context…</p>
          )}
          {pagesLoaded && messages.length === 0 && (
            <div className="assistant-suggestions">
              <p>{admin?.display_name ? `Hello, ${admin.display_name}.` : 'Hello.'} Ask me anything about this dashboard, in Tamil, English, or Tanglish.</p>
              <button type="button" onClick={() => send('How do I use this page?')}>How do I use this page?</button>
              <button type="button" onClick={() => send('What is pending right now?')}>What needs my attention?</button>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} onNavigate={handleNavigate} onFeedback={giveFeedback} />
          ))}
          {sending && <div className="assistant-message assistant-message-bot assistant-message-pending">Thinking…</div>}
        </div>

        {error && <div className="notice error-notice assistant-error">{error}</div>}

        <form
          className="assistant-input-row"
          onSubmit={(event) => { event.preventDefault(); send() }}
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={pagesLoaded ? 'Type a question…' : 'Loading…'}
            aria-label="Message to the Admin Assistant"
            disabled={!pagesLoaded}
          />
          <button type="submit" disabled={!pagesLoaded || sending || !input.trim()}>Send</button>
        </form>
      </>}
    </div>
  )
}
