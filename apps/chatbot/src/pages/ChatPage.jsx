import { useEffect, useState } from 'react'
import ChatHeader from '../components/ChatHeader.jsx'
import ChatInput from '../components/ChatInput.jsx'
import ChatMessages from '../components/ChatMessages.jsx'
import { getHealth, sendChatFeedback, sendChatMessage } from '../services/api.js'

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
  const [error, setError] = useState('')
  const [rateLimited, setRateLimited] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [feedbackSubmitted, setFeedbackSubmitted] = useState({})
  const [lastFailedText, setLastFailedText] = useState('')

  useEffect(() => { getHealth().then((data) => setHealth(data.status)).catch(() => setHealth('offline')) }, [])

  async function submitText(text) {
    if (!text || loading) return
    const userMessageId = crypto.randomUUID()
    setMessages((current) => [...current, { id: userMessageId, role: 'user', text }])
    setMessage(''); setLoading(true); setError(''); setRateLimited(false); setLastFailedText('')
    try {
      const data = await withTimeout(
        sendChatMessage({
          message: text,
          conversationId,
          languageOverride,
          memoryConsent,
          clientRequestId: userMessageId,
        }),
        REQUEST_TIMEOUT_MS,
      )
      if (data.conversation_id) setConversationId(data.conversation_id)
      setMessages((current) => [...current, {
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
      }])
    } catch (requestError) {
      if (requestError.message === 'timeout') {
        setError('The request took too long. Please try again.')
      } else if (requestError.status === 429 || requestError.code === 'CHAT_RATE_LIMITED') {
        setRateLimited(true)
        setError('Too many messages -- please wait a moment before trying again.')
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
      <ChatHeader health={health} />
      <ChatMessages messages={messages} onFeedback={handleFeedback} feedbackSubmitted={feedbackSubmitted} />
      {error && (
        <div className="error" role="alert">
          {error}
          {!rateLimited && lastFailedText && (
            <button type="button" className="retry-button" onClick={retry}>Retry</button>
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
        loading={loading || rateLimited}
        onChange={setMessage}
        onLanguageOverride={setLanguageOverride}
        onSubmit={submit}
      />
    </main>
  )
}
