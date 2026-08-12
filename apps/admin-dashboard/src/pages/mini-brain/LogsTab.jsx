export default function LogsTab({ logs }) {
  return (
    <div className="data-list">
      <p className="notice">{logs.total} event(s) recorded, most recent first.</p>
      {logs.items.map((item) => (
        <article key={item.public_id}>
          <strong>{item.event_type}</strong> — {item.level} — {item.message}
          <div><small>{item.created_at}</small></div>
        </article>
      ))}
    </div>
  )
}
