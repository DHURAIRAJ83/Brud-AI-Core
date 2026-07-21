export default function ChatInput({ value, language, loading, onChange, onLanguage, onSubmit }) {
  return (
    <form className="composer" onSubmit={onSubmit}>
      <label className="sr-only" htmlFor="message">Message</label>
      <textarea id="message" rows="2" maxLength="4000" placeholder="Type your message…" value={value}
        onChange={(event) => onChange(event.target.value)} disabled={loading} />
      <div className="composer-actions">
        <label><span className="sr-only">Language</span>
          <select value={language} onChange={(event) => onLanguage(event.target.value)} disabled={loading}>
            <option value="auto">Auto</option><option value="ta">தமிழ்</option>
            <option value="en">English</option><option value="tanglish">Tanglish</option>
          </select>
        </label>
        <button type="submit" disabled={loading || !value.trim()}>{loading ? 'Sending…' : 'Send'}</button>
      </div>
    </form>
  )
}
