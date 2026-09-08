import { useEffect, useRef, useState } from 'react'
import ChatHeader from '../components/ChatHeader.jsx'
import ChatInput from '../components/ChatInput.jsx'
import ChatMessages from '../components/ChatMessages.jsx'
import {
  clearSession,
  clearStoredSession,
  getHealth,
  getSessionMessages,
  getStoredSession,
  initSession,
  sendChatFeedback,
  sendChatMessage,
} from '../services/api.js'

const REQUEST_TIMEOUT_MS = 30000

async function sha256Hex(text) {
  const encoded = new TextEncoder().encode(text)
  const digest = await crypto.subtle.digest('SHA-256', encoded)
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

function withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((_resolve, reject) => setTimeout(() => reject(new Error('timeout')), ms)),
  ])
}

export default function ChatPage() {
  const [health, setHealth] = useState('checking')
  const [messages, setMessages] = useState([])
  const [message, setMessage] = useState('')
  const [languageOverride, setLanguageOverride] = useState('auto')
  const [memoryConsent, setMemoryConsent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState('')
  const [rateLimited, setRateLimited] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [sessionToken, setSessionToken] = useState(null)
  const [feedbackSubmitted, setFeedbackSubmitted] = useState({})
  const [lastFailedText, setLastFailedText] = useState('')

  const hydrationIdRef = useRef(0)

  // 1. Health check & Session initialization/hydration on mount
  useEffect(() => {
    getHealth().then((data) => setHealth(data.status)).catch(() => setHealth('offline'))

    const currentHydration = ++hydrationIdRef.current
    async function hydrateOrInitSession() {
      const stored = typeof getStoredSession === 'function' ? getStoredSession() : null
      if (stored?.conversationId && stored?.sessionToken) {
        try {
          if (typeof getSessionMessages === 'function') {
            const history = await getSessionMessages(stored.conversationId, stored.sessionToken)
            if (hydrationIdRef.current !== currentHydration) return
            if (Array.isArray(history?.messages)) {
              setConversationId(stored.conversationId)
              setSessionToken(stored.sessionToken)
              if (history.messages.length > 0) {
                setMessages(
                  history.messages
                    .filter((m) => m.content != null)
                    .map((m) => ({
                      id: m.id || crypto.randomUUID(),
                      role: m.role,
                      text: m.content,
                      routeUsed: m.role === 'assistant' ? 'core_model' : null,
                    }))
                )
              }
              return
            }
          }
        } catch {
          if (hydrationIdRef.current !== currentHydration) return
          // Stale, expired, or invalid session in storage -> clear and create fresh session
          if (typeof clearStoredSession === 'function') {
            clearStoredSession()
          }
        }
      }

      // No stored session or failed hydration -> initialize fresh anonymous session
      if (typeof initSession === 'function') {
        try {
          const session = await initSession({ languagePreference: languageOverride })
          if (hydrationIdRef.current !== currentHydration) return
          if (session?.conversation_id) {
            setConversationId(session.conversation_id)
            setSessionToken(session.session_token || null)
          }
        } catch {
          // Best effort; if offline, session will be retried on first message
        }
      }
    }

    hydrateOrInitSession()
  }, [])

  async function startNewChat() {
    hydrationIdRef.current++
    if (loading || clearing) return
    setError('')
    setRateLimited(false)
    setMessages([])
    setFeedbackSubmitted({})
    setLastFailedText('')
    if (typeof clearStoredSession === 'function') {
      clearStoredSession()
    }
    setConversationId(null)
    setSessionToken(null)

    if (typeof initSession === 'function') {
      try {
        const session = await initSession({ languagePreference: languageOverride })
        if (session?.conversation_id) {
          setConversationId(session.conversation_id)
          setSessionToken(session.session_token || null)
        }
      } catch (err) {
        setError('Could not initialize a new chat session. Please check your connection.')
      }
    }
  }

  async function handleClearChat() {
    hydrationIdRef.current++
    if (loading || clearing || messages.length === 0) return
    setClearing(true)
    setError('')
    try {
      const activeConvId = conversationId || (typeof getStoredSession === 'function' ? getStoredSession()?.conversationId : null)
      const activeToken = sessionToken || (typeof getStoredSession === 'function' ? getStoredSession()?.sessionToken : null)

      if (activeConvId && activeToken && typeof clearSession === 'function') {
        await clearSession(activeConvId, activeToken)
      } else if (typeof clearStoredSession === 'function') {
        clearStoredSession()
      }

      setMessages([])
      setFeedbackSubmitted({})
      setConversationId(null)
      setSessionToken(null)

      // Automatically initialize a fresh session for subsequent chat
      if (typeof initSession === 'function') {
        const newSession = await initSession({ languagePreference: languageOverride })
        if (newSession?.conversation_id) {
          setConversationId(newSession.conversation_id)
          setSessionToken(newSession.session_token || null)
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to clear chat session.')
    } finally {
      setClearing(false)
    }
  }

  async function submitText(text) {
    if (!text || loading || clearing) return
    const userMessageId = crypto.randomUUID()
    setMessages((current) => [...current, { id: userMessageId, role: 'user', text }])
    setMessage('')
    setLoading(true)
    setError('')
    setRateLimited(false)
    setLastFailedText('')

    try {
      let activeConvId = conversationId
      let activeToken = sessionToken

      // Lazily create session if not yet present
      if (!activeConvId && typeof initSession === 'function') {
        try {
          const fresh = await initSession({ languagePreference: languageOverride })
          if (fresh?.conversation_id) {
            activeConvId = fresh.conversation_id
            activeToken = fresh.session_token || null
            setConversationId(activeConvId)
            setSessionToken(activeToken)
          }
        } catch {
          // Proceed with unauthenticated fallback
        }
      }

      const data = await withTimeout(
        sendChatMessage({
          message: text,
          conversationId: activeConvId,
          sessionToken: activeToken,
          languageOverride,
          memoryConsent,
          clientRequestId: userMessageId,
        }),
        REQUEST_TIMEOUT_MS,
      )

      if (data.conversation_id) setConversationId(data.conversation_id)

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: data.reply,
          routeUsed: data.route_used,
          requestId: data.request_id,
          clarificationRequired: data.clarification_required,
          insufficientEvidence: data.insufficient_evidence,
          safetyStatus: data.safety_status,
          citations: data.citations || [],
          freshnessStatus: data.freshness_status,
          limitations: data.limitations || [],
          toolName: data.tool_name,
          toolVersion: data.tool_version,
          toolStatus: data.tool_status,
          fallbacksAttempted: data.fallbacks_attempted || [],
        },
      ])
    } catch (requestError) {
      if (requestError.message === 'timeout') {
        setError('The request took too long. Please try again.')
      } else if (requestError.status === 429 || requestError.code === 'CHAT_RATE_LIMITED') {
        setRateLimited(true)
        setError('Too many messages -- please wait a moment before trying again.')
      } else if (
        requestError.status === 401 ||
        requestError.code === 'CHAT_SESSION_EXPIRED' ||
        requestError.code === 'CHAT_SESSION_FORBIDDEN'
      ) {
        if (typeof clearStoredSession === 'function') {
          clearStoredSession()
        }
        setConversationId(null)
        setSessionToken(null)
        setError('Your previous chat session has expired. A fresh session will start on your next message.')
      } else {
        setError(requestError.message)
      }
      setLastFailedText(text)
    } finally {
      setLoading(false)
    }
  }

  async function submit(event) {
    event.preventDefault()
    const text = message.trim()
    await submitText(text)
  }

  async function retry() {
    if (!lastFailedText) return
    await submitText(lastFailedText)
  }

  async function handleFeedback(assistantMessage, feedbackType) {
    try {
      const answerHash = await sha256Hex(assistantMessage.text)
      await sendChatFeedback({
        requestId: assistantMessage.requestId,
        routeUsed: assistantMessage.routeUsed,
        answerHash,
        feedbackType,
      })
      setFeedbackSubmitted((current) => ({ ...current, [assistantMessage.id]: feedbackType }))
    } catch {
      // Feedback is best-effort; a failed submission must never disrupt the conversation.
    }
  }

  return (
    <main className="chat-shell">
      <ChatHeader
        health={health}
        onNewChat={startNewChat}
        onClearChat={handleClearChat}
        hasMessages={messages.length > 0}
        clearing={clearing}
      />
      <ChatMessages messages={messages} onFeedback={handleFeedback} feedbackSubmitted={feedbackSubmitted} />
      {error && (
        <div className="error" role="alert">
          {error}
          {!rateLimited && lastFailedText && (
            <button type="button" className="retry-button" onClick={retry}>
              Retry
            </button>
          )}
        </div>
      )}
      <label className="memory-consent">
        <input
          type="checkbox"
          checked={memoryConsent}
          onChange={(event) => setMemoryConsent(event.target.checked)}
        />
        Remember this conversation
      </label>
      <ChatInput
        value={message}
        languageOverride={languageOverride}
        loading={loading || clearing || rateLimited}
        onChange={setMessage}
        onLanguageOverride={setLanguageOverride}
        onSubmit={submit}
      />
    </main>
  )
}
