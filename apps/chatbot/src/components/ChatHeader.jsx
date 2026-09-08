import HealthBadge from './HealthBadge.jsx'

export default function ChatHeader({
  health,
  onNewChat,
  onClearChat,
  hasMessages = false,
  clearing = false,
}) {
  return (
    <header className="chat-header">
      <div>
        <div className="brand">BRUD AI</div>
        <h1>Brud Chat</h1>
      </div>
      <div className="chat-header-actions">
        {onNewChat && (
          <button
            type="button"
            id="new-chat-button"
            className="session-action-button new-chat-button"
            onClick={onNewChat}
            title="Start a new chat session"
            aria-label="New Chat"
          >
            New Chat
          </button>
        )}
        {onClearChat && hasMessages && (
          <button
            type="button"
            id="clear-chat-button"
            className="session-action-button clear-chat-button"
            onClick={onClearChat}
            disabled={clearing}
            title="Clear and close this conversation"
            aria-label="Clear Chat"
          >
            {clearing ? 'Clearing...' : 'Clear'}
          </button>
        )}
        <HealthBadge status={health} />
      </div>
    </header>
  )
}
