export default function ChatMessages({ messages }) {
  if (!messages.length) {
    return (
      <div className="empty-state">
        <div className="empty-mark">அ</div>
        <h2>Start a conversation</h2>
        <p>Try Tamil, English, Tanglish, or a mix. Phase 1 currently returns a foundation response.</p>
      </div>
    )
  }
  return (
    <div className="messages" aria-live="polite">
      {messages.map((message) => (
        <div className={`message ${message.role}`} key={message.id}>
          <span>{message.role === 'user' ? 'You' : 'Brud AI'}</span>
          <p>{message.text}</p>
        </div>
      ))}
    </div>
  )
}
