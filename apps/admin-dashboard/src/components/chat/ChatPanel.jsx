import { useCallback, useEffect, useRef, useState } from 'react'
import Button from '../Button.jsx'
import Skeleton from '../Skeleton.jsx'
import CitationCard from './CitationCard.jsx'
import SessionList from './SessionList.jsx'
import AssistantSettingsPane from './AssistantSettingsPane.jsx'
import DatasetGeneratePane from './DatasetGeneratePane.jsx'
import ContextPane from './ContextPane.jsx'
import EvaluationPane from './EvaluationPane.jsx'
import { copyToClipboard } from '../../utils/clipboard.js'
import { formatMessageText } from '../../utils/markdown.jsx'
import {
  assistantUpload,
  lrChat,
  lrChatStream,
  lrDeleteSession,
  lrMessages,
  lrSessions,
  miniBrainDefaultRetrievalProfile,
  miniBrainWidgetHealth,
  sendMiniBrainGroundedMessage,
} from '../../services/api.js'

function uid() {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function normalizeStoredMessage(row) {
  return {
    id: row.public_id,
    role: row.role === 'admin' ? 'user' : 'assistant',
    text: row.sanitized_text,
    citations: undefined,
  }
}

const DEFAULT_QUICK_ACTIONS = [
  'System Status',
  'Model Status',
  'Dataset Status',
  'Training Status',
  'Latest Evaluation',
  'Pending Admin Actions',
]

export default function ChatPanel({
  variant = 'compact',
  admin,
  onFeedback,
  toast,
  suggestions = [],
  emptyGreeting = 'Ask a question to get started.',
  onNavigate,
}) {
  const [activeTab, setActiveTab] = useState('chat')
  const [sessions, setSessions] = useState([])
  const [sessionsLoaded, setSessionsLoaded] = useState(false)
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [attachedFile, setAttachedFile] = useState(null)
  const fileInputRef = useRef(null)
  const textareaRef = useRef(null)
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const isNearBottomRef = useRef(true)
  const [showScrollBottom, setShowScrollBottom] = useState(false)
  const [error, setError] = useState('')
  const [useKnowledgeBase, setUseKnowledgeBase] = useState(false)
  const [activeProfileName, setActiveProfileName] = useState('')
  const [groundedWarning, setGroundedWarning] = useState('')
  const [lastUserText, setLastUserText] = useState('')
  const [executionMode, setExecutionMode] = useState('auto')
  const [selectedProvider, setSelectedProvider] = useState('')
  const [activeModelInfo, setActiveModelInfo] = useState({ model: 'Auto Routing', backend_type: 'auto' })

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

  const loadHealth = useCallback(async () => {
    try {
      const h = await miniBrainWidgetHealth()
      if (h?.current_model) {
        setActiveModelInfo({
          model: h.current_model,
          backend_type: h.backend_type,
        })
      }
    } catch {
      // Best-effort health check
    }
  }, [])

  const loadProfile = useCallback(async () => {
    try {
      const p = await miniBrainDefaultRetrievalProfile()
      if (p?.name) {
        setActiveProfileName(p.name)
      } else {
        setActiveProfileName('')
      }
    } catch {
      setActiveProfileName('')
    }
  }, [])

  useEffect(() => {
    loadSessions()
    loadHealth()
    loadProfile()
  }, [loadSessions, loadHealth, loadProfile])

  const handleScroll = useCallback(() => {
    if (messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current
      const nearBottom = scrollHeight - scrollTop - clientHeight < 100
      isNearBottomRef.current = nearBottom
      setShowScrollBottom(!nearBottom && messages.length > 2)
    }
  }, [messages.length])

  // Smooth auto-scroll when new messages arrive if user is near bottom
  useEffect(() => {
    if (isNearBottomRef.current && messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, sending, uploading])

  function scrollToBottom() {
    isNearBottomRef.current = true
    setShowScrollBottom(false)
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }

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
    setAttachedFile(null)
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
    isNearBottomRef.current = true

    let profileId = null
    if (useKnowledgeBase) {
      try {
        const defaultProfile = await miniBrainDefaultRetrievalProfile()
        profileId = defaultProfile.retrieval_profile_public_id || null
        if (defaultProfile?.name) setActiveProfileName(defaultProfile.name)
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

    const routingOptions = {
      execution_mode: executionMode,
      provider_key: selectedProvider || null,
      grounded: grounded,
      retrieval_profile_public_id: profileId,
      top_k: 4,
    }

    const assistantMsgId = uid()
    let streamFailed = false

    try {
      // Create placeholder assistant message
      setMessages((previous) => [
        ...previous,
        {
          id: assistantMsgId,
          role: 'assistant',
          text: '',
          citations: undefined,
          isStreaming: true,
        },
      ])

      await lrChatStream(
        activeSessionId,
        trimmed,
        routingOptions,
        (event, data) => {
          if (event === 'start' && data?.session_id) {
            setActiveSessionId(data.session_id)
          } else if (event === 'metadata') {
            if (data?.citations) {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantMsgId ? { ...m, citations: data.citations } : m))
              )
            }
          } else if (event === 'token' && data?.text) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, text: (m.text || '') + data.text } : m
              )
            )
          } else if (event === 'error') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, text: m.text ? m.text + `\n[Error: ${data.message}]` : `Error: ${data.message}` }
                  : m
              )
            )
          }
        }
      )

      setMessages((prev) =>
        prev.map((m) => (m.id === assistantMsgId ? { ...m, isStreaming: false } : m))
      )
      loadSessions()
      loadHealth()
    } catch (reason) {
      streamFailed = true
      // Remove failed streaming placeholder and fallback to non-streaming lrChat
      setMessages((prev) => prev.filter((m) => m.id !== assistantMsgId))
      try {
        let replyText = ''
        let citations = undefined
        if (grounded) {
          const response = await sendMiniBrainGroundedMessage(activeSessionId, trimmed, profileId, 4, routingOptions)
          if (response?.session?.public_id) setActiveSessionId(response.session.public_id)
          replyText = response?.reply?.sanitized_text || 'No response text returned.'
          citations = response?.citations
        } else {
          const response = await lrChat(activeSessionId, trimmed, routingOptions)
          if (response?.session?.public_id) setActiveSessionId(response.session.public_id)
          replyText = response?.reply?.sanitized_text || 'No response text returned.'
        }

        setMessages((previous) => [
          ...previous,
          {
            id: uid(),
            role: 'assistant',
            text: replyText,
            citations: citations,
          },
        ])
        loadSessions()
        loadHealth()
      } catch (fallbackErr) {
        setError(fallbackErr.message)
        toast?.error(fallbackErr.message)
      }
    } finally {
      setSending(false)
    }
  }

  async function handleFileUpload(event) {
    const file = event.target.files?.[0]
    if (!file || uploading || sending) return
    event.target.value = ''
    setError('')
    setAttachedFile(file)
    setUploading(true)
    isNearBottomRef.current = true
    const userMsg = {
      id: uid(),
      role: 'user',
      text: `📎 Attached file: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`,
    }
    setMessages((previous) => [...previous, userMsg])
    try {
      const res = await assistantUpload(file, activeSessionId)
      const assistantReply = {
        id: uid(),
        role: 'assistant',
        text: res.summary,
        recommendation: res.action_recommendation,
      }
      setMessages((previous) => [...previous, assistantReply])
      toast?.success(`Uploaded ${file.name}`)
    } catch (err) {
      setError(err.message)
      toast?.error(err.message)
    } finally {
      setUploading(false)
      setAttachedFile(null)
    }
  }

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
      await onFeedback?.(message, rating)
    } catch {
      // Best-effort
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
    }
  }

  const sessionItems = sessions.map((session) => ({
    id: session.public_id,
    title: session.title || session.public_id,
    subtitle: session.status,
    meta: `${session.total_messages ?? 0} messages`,
    status: session.status,
  }))

  const allSuggestions = [
    ...(suggestions || []),
    ...DEFAULT_QUICK_ACTIONS.filter((qa) => !suggestions.includes(qa)),
  ]

  return (
    <div className={`chat-panel chat-panel-${variant}`}>
      <div className="chat-panel-layout">
        {/* Canonical 5-Workspace Left Navigation Bar */}
        <nav className="chat-left-nav" aria-label="Assistant Sections">
          <button
            type="button"
            className={`chat-nav-btn ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
            title="Assistant Chat"
            aria-label="Assistant Chat"
          >
            <span className="chat-nav-icon">💬</span>
            <span>Chat</span>
          </button>
          <button
            type="button"
            className={`chat-nav-btn ${activeTab === 'context' ? 'active' : ''}`}
            onClick={() => setActiveTab('context')}
            title="Dashboard Context"
            aria-label="Dashboard Context"
          >
            <span className="chat-nav-icon">📊</span>
            <span>Context</span>
          </button>
          <button
            type="button"
            className={`chat-nav-btn ${activeTab === 'settings' || activeTab === 'models' ? 'active' : ''}`}
            onClick={() => setActiveTab('settings')}
            title="Provider & AI Settings"
            aria-label="Provider & AI Settings"
          >
            <span className="chat-nav-icon">⚙️</span>
            <span>Models</span>
          </button>
          <button
            type="button"
            className={`chat-nav-btn ${activeTab === 'generate' || activeTab === 'data' ? 'active' : ''}`}
            onClick={() => setActiveTab('generate')}
            title="Dataset Generator (MB-16)"
            aria-label="Dataset Generator"
          >
            <span className="chat-nav-icon">⚡</span>
            <span>Data</span>
          </button>
          <button
            type="button"
            className={`chat-nav-btn ${activeTab === 'evaluation' ? 'active' : ''}`}
            onClick={() => setActiveTab('evaluation')}
            title="Post-Training Evaluation"
            aria-label="Post-Training Evaluation"
          >
            <span className="chat-nav-icon">📈</span>
            <span>Eval</span>
          </button>
        </nav>

        <div className="chat-panel-content-area">
          {activeTab === 'context' && (
            <ContextPane toast={toast} onNavigate={onNavigate} />
          )}

          {(activeTab === 'settings' || activeTab === 'models') && (
            <AssistantSettingsPane toast={toast} onNavigate={onNavigate} />
          )}

          {(activeTab === 'generate' || activeTab === 'data') && (
            <DatasetGeneratePane toast={toast} onNavigate={onNavigate} />
          )}

          {activeTab === 'evaluation' && (
            <EvaluationPane toast={toast} onNavigate={onNavigate} />
          )}

          {activeTab === 'chat' && (
            <div className="chat-inner-workspace">
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

              <div className="chat-main-col">
                {/* ── Controls bar: KB toggle + mode + model badge ── */}
                <div className="chat-controls-bar">
                  <div className="chat-controls-left">
                    {/* Knowledge Base Toggle */}
                    <label
                      className={`chat-kb-toggle${useKnowledgeBase ? ' active' : ''}`}
                      title={useKnowledgeBase ? `Live Admin Knowledge (${activeProfileName || 'Default'})` : 'General Knowledge Only'}
                    >
                      <input
                        type="checkbox"
                        checked={useKnowledgeBase}
                        onChange={(event) => { setUseKnowledgeBase(event.target.checked); setGroundedWarning('') }}
                        aria-label="Use knowledge base"
                      />
                      <span>
                        {useKnowledgeBase
                          ? (activeProfileName ? `✓ Knowledge Base (${activeProfileName})` : '✓ Knowledge Base (Live)')
                          : '○ Knowledge Base (General)'}
                      </span>
                    </label>

                    {/* Mode Selector */}
                    <div className="chat-mode-group">
                      <span className="chat-mode-label">Mode:</span>
                      <select
                        className="chat-select"
                        value={executionMode}
                        onChange={(e) => setExecutionMode(e.target.value)}
                        aria-label="Execution Mode"
                      >
                        <option value="auto">Auto (Fallback)</option>
                        <option value="local">Local Model</option>
                        <option value="provider">External Provider</option>
                      </select>
                    </div>

                    {executionMode === 'provider' && (
                      <select
                        className="chat-select"
                        value={selectedProvider}
                        onChange={(e) => setSelectedProvider(e.target.value)}
                        aria-label="Select Provider"
                      >
                        <option value="">Any Configured</option>
                        <option value="openrouter">OpenRouter</option>
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="gemini">Google Gemini</option>
                      </select>
                    )}
                  </div>

                  <div className="chat-controls-right">
                    <span
                      className={`chat-model-badge ${
                        activeModelInfo.backend_type === 'unavailable'
                          ? 'chat-model-badge-unavailable'
                          : activeModelInfo.backend_type === 'local'
                          ? 'chat-model-badge-local'
                          : 'chat-model-badge-provider'
                      }`}
                    >
                      ● {activeModelInfo.model}
                    </span>
                    {messages.length > 0 && (
                      <Button size="sm" variant="ghost" onClick={startNewSession} title="Start new conversation" aria-label="Clear conversation">
                        + New
                      </Button>
                    )}
                  </div>
                </div>

                {groundedWarning && (
                  <div className="chat-grounded-warning">
                    ⚠️ {groundedWarning}
                  </div>
                )}

                {/* Scrollable Message Viewport */}
                <div
                  ref={messagesContainerRef}
                  onScroll={handleScroll}
                  className="chat-panel-messages"
                >
                  {messages.length === 0 && (
                    <div className="chat-welcome-hero">
                      <div className="chat-welcome-card">
                        <div className="chat-welcome-title-row">
                          <span className="chat-welcome-icon">🧠</span>
                          <strong className="chat-welcome-title">Brud AI Admin Assistant</strong>
                        </div>
                        <p className="chat-welcome-greeting">
                          {admin?.display_name ? `Hello, ${admin.display_name}.` : emptyGreeting}
                        </p>
                        <p className="chat-welcome-desc">
                          I am your administrative intelligence layer for Brud AI. I can inspect system health, models, providers, datasets, training, evaluation, RAG, memory, governance, and recent events.
                        </p>
                      </div>

                      <div className="chat-quick-actions">
                        <span className="chat-quick-actions-label">Quick Actions</span>
                        <div className="chat-suggestions-grid">
                          {allSuggestions.map((suggestion) => (
                            <button
                              key={suggestion}
                              type="button"
                              className="chat-suggestion-chip"
                              onClick={() => send(suggestion)}
                            >
                              {suggestion}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={message.role === 'user' ? 'chat-msg-user chat-message-user' : 'chat-msg-assistant chat-message-assistant'}
                    >
                      {message.role === 'assistant' && (
                        <div className="chat-msg-header">
                          <span>🧠</span> Brud AI
                        </div>
                      )}
                      <div>{formatMessageText(message.text)}</div>

                      {message.recommendation && (
                        <div className="chat-msg-recommendation">
                          <p style={{ margin: '0 0 6px 0' }}>{message.recommendation.message}</p>
                          {onNavigate && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => onNavigate(message.recommendation.nav_key)}
                            >
                              Go to {message.recommendation.nav_key}
                            </Button>
                          )}
                        </div>
                      )}

                      {message.citations && message.citations.length > 0 && (
                        <div className="chat-message-citations">
                          {message.citations.map((citation, index) => (
                            <CitationCard key={`${citation.source_public_id}-${index}`} citation={citation} />
                          ))}
                        </div>
                      )}

                      {message.role === 'assistant' && (
                        <div className="chat-msg-actions">
                          <Button size="sm" variant="ghost" onClick={() => copyMessage(message.text)} aria-label="Copy" title="Copy response">Copy</Button>
                          {onFeedback && (
                            message.feedbackGiven ? (
                              <small className="chat-msg-feedback-thanks">Thanks for the feedback.</small>
                            ) : (
                              <>
                                <Button size="sm" variant="ghost" onClick={() => giveFeedback(message, 'helpful')} aria-label="Mark helpful" title="Mark helpful">👍 Helpful</Button>
                                <Button size="sm" variant="ghost" onClick={() => giveFeedback(message, 'not_helpful')} aria-label="Mark not helpful" title="Mark not helpful">👎 Not helpful</Button>
                              </>
                            )
                          )}
                        </div>
                      )}
                    </div>
                  ))}

                  {sending && !messages.some((m) => m.isStreaming && m.text) && (
                    <div className="chat-msg-pending">
                      <span>🧠</span> Brud AI is thinking…
                    </div>
                  )}

                  {uploading && (
                    <div className="chat-msg-pending">
                      <span>📄</span> Processing and registering document…
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Floating scroll-to-bottom indicator */}
                {showScrollBottom && (
                  <button
                    type="button"
                    onClick={scrollToBottom}
                    className="chat-scroll-bottom-badge"
                  >
                    ↓ New response
                  </button>
                )}

                {error && (
                  <div className="chat-error-notice">
                    <strong>⚠️ Unable to generate response:</strong> {error}
                  </div>
                )}

                {/* Sticky Input Footer */}
                <div className="chat-footer">
                  <div className="chat-footer-meta-row">
                    {attachedFile ? (
                      <div className="chat-attachment-chip">
                        <span>📎 {attachedFile.name}</span>
                        <button type="button" className="chat-attachment-remove" onClick={() => setAttachedFile(null)} aria-label="Remove attachment">×</button>
                      </div>
                    ) : (
                      <span className="chat-footer-hint">Press Enter to send, Shift+Enter for newline</span>
                    )}

                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={regenerate}
                      disabled={!lastUserText || sending || uploading}
                      aria-label="Regenerate"
                      title="Regenerate last response"
                    >
                      ↺ Regenerate
                    </Button>
                  </div>

                  <form className="chat-input-row" onSubmit={(event) => { event.preventDefault(); send() }}>
                    <input
                      type="file"
                      ref={fileInputRef}
                      style={{ display: 'none' }}
                      accept=".pdf,.jsonl,.json,.csv,.tsv,.txt"
                      onChange={handleFileUpload}
                    />
                    <button
                      type="button"
                      className="chat-attach-btn"
                      title="Attach document (PDF, CSV, JSON, TXT)"
                      aria-label="Attach file"
                      disabled={uploading || sending}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      📎
                    </button>
                    <textarea
                      ref={textareaRef}
                      className="chat-textarea"
                      value={input}
                      onChange={(event) => setInput(event.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Type a question or attach a PDF…"
                      aria-label="Message"
                      rows={1}
                    />
                    <Button
                      type="submit"
                      variant="primary"
                      disabled={sending || uploading || !input.trim()}
                      style={{ height: '38px', padding: '0 14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}
                    >
                      {sending ? 'Thinking…' : 'Send'}
                    </Button>
                  </form>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
