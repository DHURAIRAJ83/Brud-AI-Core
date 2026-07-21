export default function StatusCard({ label, value, tone = 'neutral' }) {
  return <article className="status-card"><div className={`status-icon ${tone}`}>●</div><span>{label}</span><strong>{String(value).replaceAll('_', ' ')}</strong></article>
}
