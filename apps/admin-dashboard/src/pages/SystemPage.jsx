import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import { getSystemStatus } from '../services/api.js'

export default function SystemPage() {
  const [system, setSystem] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { getSystemStatus().then(setSystem).catch((reason) => setError(reason.message)) }, [])

  if (error) return <div className="notice error-notice"><strong>Unable to load system status</strong><p>{error}</p></div>
  if (!system) return <div className="notice">Loading database, configuration, and audit status…</div>
  const { database, configuration, audit } = system
  return <>
    <section className="system-heading"><span>Read-only control plane</span><h2>System foundation</h2><p>Safe operational metadata only. Paths and secret values are never displayed.</p></section>
    <h3>Database</h3><section className="card-grid">
      <StatusCard label="Database health" value={database.status} tone="good" />
      <StatusCard label="Schema version" value={database.schema_version} />
      <StatusCard label="Journal mode" value={database.journal_mode} tone={database.journal_mode === 'wal' ? 'good' : 'waiting'} />
      <StatusCard label="Foreign keys" value={database.foreign_keys ? 'enabled' : 'disabled'} tone={database.foreign_keys ? 'good' : 'waiting'} />
      <StatusCard label="Automatic backup" value={database.backup_enabled ? 'enabled' : 'disabled'} />
      <StatusCard label="Latest backup" value={database.latest_backup?.filename ?? 'No backup yet'} />
    </section>
    <h3>Runtime configuration</h3><section className="metric-grid">
      <StatusCard label="Environment" value={configuration.environment} />
      <StatusCard label="Log level" value={configuration.log_level} />
      <StatusCard label="Audit" value={configuration.audit_enabled ? 'enabled' : 'disabled'} tone="good" />
    </section>
    <h3>Recent audit events</h3>
    {audit.items.length === 0 ? <div className="notice">No audit events have been recorded.</div> :
      <div className="audit-list">{audit.items.map((event) => <article key={event.public_id}>
        <div><strong>{event.action.replaceAll('_', ' ')}</strong><span>{event.outcome}</span></div>
        <small>{new Date(event.created_at).toLocaleString()}</small>
      </article>)}</div>}
  </>
}
