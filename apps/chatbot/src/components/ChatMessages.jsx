const ROUTE_LABELS = {
  core_model: 'Model',
  approved_rag: 'RAG',
  memory: 'Memory',
  trusted_web: 'Web',
  tool: 'Tool',
  clarify: 'Clarification',
  refuse: 'Refused',
  insufficient: 'Unavailable',
}

const FRESHNESS_WARNING_TEXT = {
  stale: 'This information may be out of date.',
  possibly_stale: 'This information may not be fully current.',
  undated: 'The source has no date, so how current this is cannot be confirmed.',
  conflicting: 'Sources disagree on how current this information is.',
}

const FEEDBACK_OPTIONS = [
  { type: 'thumbs_up', label: 'Helpful' },
  { type: 'thumbs_down', label: 'Not helpful' },
  { type: 'language_report', label: 'Wrong language' },
  { type: 'safety_report', label: 'Unsafe' },
]

function RouteLabel({ route }) {
  if (!route || !ROUTE_LABELS[route]) return null
  return <span className={`route-label route-${route}`}>{ROUTE_LABELS[route]}</span>
}

function FeedbackControls({ message, onFeedback, submittedType }) {
  if (message.role !== 'assistant' || !message.requestId) return null
  if (submittedType) {
    return <p className="feedback-done">Thanks for the feedback.</p>
  }
  return (
    <div className="feedback-controls" role="group" aria-label="Rate this answer">
      {FEEDBACK_OPTIONS.map((option) => (
        <button
          key={option.type}
          type="button"
          className="feedback-button"
          onClick={() => onFeedback(message, option.type)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

function WebCitations({ message }) {
  if (message.routeUsed !== 'trusted_web' || !message.citations?.length) return null
  const conflictLimitation = message.limitations?.includes('source_conflict_disclosed')
  return (
    <div className="web-citations">
      {conflictLimitation && (
        <p className="freshness-warning" role="note">
          Trusted sources disagree on this -- see the sources below.
        </p>
      )}
      {message.freshnessStatus && FRESHNESS_WARNING_TEXT[message.freshnessStatus] && (
        <p className="freshness-warning" role="note">{FRESHNESS_WARNING_TEXT[message.freshnessStatus]}</p>
      )}
      <ul className="citation-list">
        {message.citations.map((citation) => (
          <li key={citation.citation_id}>
            <a href={citation.url} target="_blank" rel="noreferrer">
              {citation.title || citation.document_or_site_name || citation.url}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ToolResult({ message }) {
  if (message.routeUsed !== 'tool') return null
  return (
    <p className="tool-result-meta">
      Tool: {message.toolName}{message.toolVersion ? ` (${message.toolVersion})` : ''}
    </p>
  )
}

export default function ChatMessages({ messages, onFeedback, feedbackSubmitted }) {
  if (!messages.length) {
    return (
      <div className="empty-state">
        <div className="empty-mark">அ</div>
        <h2>Start a conversation</h2>
        <p>Try Tamil, English, or Tanglish -- Tanglish input always answers in Tamil.</p>
      </div>
    )
  }
  return (
    <div className="messages" aria-live="polite">
      {messages.map((message) => (
        <div className={`message ${message.role}`} key={message.id}>
          <span>
            {message.role === 'user' ? 'You' : 'Brud AI'}
            {message.role === 'assistant' && <RouteLabel route={message.routeUsed} />}
          </span>
          <p>{message.text}</p>
          {message.role === 'assistant' && <ToolResult message={message} />}
          {message.role === 'assistant' && <WebCitations message={message} />}
          {message.role === 'assistant' && (
            <FeedbackControls
              message={message}
              onFeedback={onFeedback}
              submittedType={feedbackSubmitted?.[message.id]}
            />
          )}
        </div>
      ))}
    </div>
  )
}
