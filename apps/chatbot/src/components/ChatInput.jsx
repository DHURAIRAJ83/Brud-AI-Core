export default function ChatInput({ value, languageOverride, loading, onChange, onLanguageOverride, onSubmit }) {
  return (
    <form className="composer" onSubmit={onSubmit}>
      <label className="sr-only" htmlFor="message">Message</label>
      <textarea id="message" rows="2" maxLength="4000" placeholder="Type your message…" value={value}
        onChange={(event) => onChange(event.target.value)} disabled={loading} />
      <div className="composer-actions">
        <label htmlFor="language-override"><span className="sr-only">Answer language</span>
          <select
            id="language-override"
            value={languageOverride}
            onChange={(event) => onLanguageOverride(event.target.value)}
            disabled={loading}
          >
            <option value="auto">Auto</option>
            <option value="ta">தமிழ்</option>
            <option value="en">English</option>
          </select>
        </label>
        <button type="submit" disabled={loading || !value.trim()}>{loading ? 'Sending…' : 'Send'}</button>
      </div>
    </form>
  )
}
