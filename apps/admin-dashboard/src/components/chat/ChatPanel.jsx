import { useCallback, useEffect, useState } from 'react'
import Button from '../Button.jsx'
import Skeleton from '../Skeleton.jsx'
import CitationCard from './CitationCard.jsx'
import SessionList from './SessionList.jsx'
import { copyToClipboard } from '../../utils/clipboard.js'
import { formatMessageText } from '../../utils/markdown.jsx'
import {
  lrChat,
  lrDeleteSession,
  lrMessages,
  lrSessions,
  miniBrainDefaultRetrievalProfile,
  sendMiniBrainGroundedMessage,
} from '../../services/api.js'

function uid() {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

// lrMessages() rows use role: 'admin' | 'assistant' (MiniBrainPage's own
// convention), and never include citations (only the live grounded-chat
// response does) -- a reloaded past session honestly shows its text but
// not its original citations, rather than fabricating them.
function normalizeStoredMessage(row) {
  return {
    id: row.public_id,
    role: row.role === 'admin' ? 'user' : 'assistant',
    text: row.sanitized_text,
    citations: undefined,
  }
}

export default function ChatPanel({
  variant = 'compact',
  admin,
  onFeedback,
  toast,
  suggestions = [],
  emptyGreeting = 'Ask a question to get started.',
}) {
  const [sessions, setSessions] = useState([])
  const [sessionsLoaded, setSessionsLoaded] = useState(false)
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [useKnowledgeBase, setUseKnowledgeBase] = useState(false)
  const [groundedWarning, setGroundedWarning] = useState('')
  const [lastUserText, setLastUserText] = useState('')

  const loadSessions = useCallback(async () => {
    try {
      const result = await lrSessions()
      setSessions(result.items ?? [])
    } catch {
      setSessions([])
    } finally {
      setSessionsLoaded(true)
    }
  }, [])

  useEffect(() => { loadSessions() }, [loadSessions])

  async function selectSession(id) {
    setActiveSessionId(id)
    setError('')
    try {
      const result = await lrMessages(id)
      setMessages((result.items ?? []).map(normalizeStoredMessage))
    } catch (reason) {
      setError(reason.message)
    }
  }

  function startNewSession() {
    setActiveSessionId(null)
    setMessages([])
    setError('')
  }

  async function deleteSession(id) {
    try {
      await lrDeleteSession(id)
      if (id === activeSessionId) startNewSession()
      await loadSessions()
      toast?.success('Conversation deleted.')
    } catch (reason) {
      toast?.error(reason.message)
    }
  }

  async function send(overrideText) {
    const trimmed = (overrideText ?? input).trim()
    if (!trimmed || sending) return
    setError('')
    setInput('')
    setLastUserText(trimmed)
    const userMessage = { id: uid(), role: 'user', text: trimmed }
    setMessages((previous) => [...previous, userMessage])
    setSending(true)

    // Resolved fresh on every grounded send, never cached -- matches the
    // same real requirement the floating widget already satisfies.
    let profileId = null
    if (useKnowledgeBase) {
      try {
        const defaultProfile = await miniBrainDefaultRetrievalProfile()
        profileId = defaultProfile.retrieval_profile_public_id || null
      } catch {
        profileId = null
      }
    }
    const grounded = useKnowledgeBase && Boolean(profileId)
    if (useKnowledgeBase && !profileId) {
      setGroundedWarning('No active knowledge base profile is available yet -- answering without it.')
    } else if (groundedWarning) {
      setGroundedWarning('')
    }

    try {
      const response = grounded
        ? await sendMiniBrainGroundedMessage(activeSessionId, trimmed, profileId)
        : await lrChat(activeSessionId, trimmed)
      setActiveSessionId(response.session.public_id)
      setMessages((previous) => [
        ...previous,
        {
          id: uid(), role: 'assistant', text: response.reply.sanitized_text,
          citations: grounded ? response.citations : undefined,
        },
      ])
      loadSessions()
    } catch (reason) {
      setError(reason.message)
      toast?.error(reason.message)
    } finally {
      setSending(false)
    }
  }

  // Resends the prior user message text through the same real send path --
  // not a guaranteed-different-answer promise (no dedicated "regenerate"
  // backend endpoint exists), disclosed honestly rather than faked.
  function regenerate() {
    if (!lastUserText || sending) return
    send(lastUserText)
  }

  async function copyMessage(text) {
    const copied = await copyToClipboard(text)
    if (copied) toast?.success('Copied to clipboard.')
    else toast?.error('Could not copy to clipboard.')
  }

  async function giveFeedback(message, rating) {
    setMessages((previous) => previous.map((item) => (item.id === message.id ? { ...item, feedbackGiven: true } : item)))
    try {
      await onFeedback(message, rating)
    } catch {
      // Feedback is best-effort; the UI already shows a thank-you and never blocks the chat.
    }
  }

  const sessionItems = sessions.map((session) => ({
    id: session.public_id,
    title: session.title || session.public_id,
    subtitle: session.status,
    meta: `${session.total_messages ?? 0} messages`,
    status: session.status,
  }))

  return (
    <div className={`chat-panel chat-panel-${variant}`}>
      {variant === 'full' && (
        <div className="chat-panel-sessions">
          <Button variant="secondary" size="sm" onClick={startNewSession}>New conversation</Button>
          {!sessionsLoaded ? (
            <Skeleton lines={3} />
          ) : (
            <SessionList items={sessionItems} activeId={activeSessionId} onSelect={selectSession} onDelete={deleteSession} emptyLabel="No conversations yet." />
          )}
        </div>
      )}

      <div className="chat-panel-main">
        <div className="chat-panel-controls">
          <label>
            <input
              type="checkbox"
              checked={useKnowledgeBase}
              onChange={(event) => { setUseKnowledgeBase(event.target.checked); setGroundedWarning('') }}
            />
            {' '}Use knowledge base
          </label>
        </div>
        {groundedWarning && <div className="notice error-notice">{groundedWarning}</div>}

        <div className="chat-panel-messages">
          {messages.length === 0 && (
            <div className="chat-panel-empty">
              <p>{admin?.display_name ? `Hello, ${admin.display_name}.` : emptyGreeting}</p>
              {suggestions.map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => send(suggestion)}>{suggestion}</button>
              ))}
            </div>
          )}
          {messages.map((message) => (
            <div key={message.id} className={`chat-message ${message.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'}`}>
              <p>{formatMessageText(message.text)}</p>
              {message.citations && message.citations.length > 0 && (
                <div className="chat-message-citations">
                  {message.citations.map((citation, index) => (
                    <CitationCard key={`${citation.source_public_id}-${index}`} citation={citation} />
                  ))}
                </div>
              )}
              {message.role === 'assistant' && (
                <div className="chat-message-actions">
                  <Button size="sm" variant="ghost" onClick={() => copyMessage(message.text)}>Copy</Button>
                  {onFeedback && (
                    message.feedbackGiven ? (
                      <small className="chat-message-feedback-thanks">Thanks for the feedback.</small>
                    ) : (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => giveFeedback(message, 'helpful')} aria-label="Mark helpful">Helpful</Button>
                        <Button size="sm" variant="ghost" onClick={() => giveFeedback(message, 'not_helpful')} aria-label="Mark not helpful">Not helpful</Button>
                      </>
                    )
                  )}
                </div>
              )}
            </div>
          ))}
          {sending && <div className="chat-message chat-message-assistant chat-message-pending">Thinking…</div>}
        </div>

        {error && <div className="notice error-notice">{error}</div>}

        <div className="chat-panel-footer-actions">
          <Button size="sm" variant="ghost" disabled={!lastUserText || sending} onClick={regenerate}>Regenerate</Button>
        </div>

        <form className="chat-panel-input-row" onSubmit={(event) => { event.preventDefault(); send() }}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Type a question…"
            aria-label="Message"
          />
          <Button type="submit" variant="primary" disabled={sending || !input.trim()}>Send</Button>
        </form>
      </div>
    </div>
  )
}
