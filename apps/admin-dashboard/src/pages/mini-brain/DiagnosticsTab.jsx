import StatusCard from '../../components/StatusCard.jsx'

export default function DiagnosticsTab({ diagnostics }) {
  if (!diagnostics) return null
  return (
    <>
      <section className="metric-grid">
        <StatusCard label="Config issues" value={diagnostics.config_issues.length} tone={diagnostics.config_issues.length ? 'waiting' : 'good'} />
        <StatusCard label="Event count" value={diagnostics.event_count} tone="neutral" />
        <StatusCard label="Runtime backend" value={diagnostics.runtime_backend} tone="neutral" />
        <StatusCard label="Model integrated" value={String(diagnostics.model_integrated)} tone="neutral" />
      </section>
      {diagnostics.config_issues.length > 0 && (
        <div className="form-error" role="alert">
          {diagnostics.config_issues.map((issue) => <div key={issue}>{issue}</div>)}
        </div>
      )}
    </>
  )
}
