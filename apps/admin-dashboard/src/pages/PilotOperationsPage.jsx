import { useCallback, useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  getSystemStatus,
  miniBrainDefaultRetrievalProfile,
  miniBrainWidgetHealth,
  ragRetrievalProfiles,
  ragSpaces,
  systemRecentAudit,
} from '../services/api.js'

const NOTICE = 'MB-48: a single, lightweight, read-only view of what an internal pilot admin actually needs to check first -- reuses the exact same endpoints the widget, RAG page, and System page already call. Adds no new backend surface.'

export default function PilotOperationsPage() {
  const [state, setState] = useState({ loading: true, error: '' })

  const load = useCallback(async () => {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [health, defaultProfile, spaces, profiles, audit, system] = await Promise.all([
        miniBrainWidgetHealth(),
        miniBrainDefaultRetrievalProfile(),
        ragSpaces(),
        ragRetrievalProfiles(),
        systemRecentAudit(20),
        getSystemStatus(),
      ])
      setState({
        loading: false, error: '',
        health, defaultProfile,
        knowledgeSpaceCount: (spaces.items ?? []).length,
        activeProfileCount: (profiles.items ?? []).filter((item) => item.status === 'active').length,
        auditEvents: audit.items ?? [],
        schemaVersion: system.database.schema_version,
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (state.loading) return <div className="notice">Loading pilot operations status…</div>
  if (state.error) {
    return (
      <div className="notice error-notice">
        <strong>Unable to load pilot operations status</strong>
        <p>{state.error}</p>
        <button type="button" onClick={load}>Retry</button>
      </div>
    )
  }

  const { health, defaultProfile, knowledgeSpaceCount, activeProfileCount, auditEvents, schemaVersion } = state

  return (
    <>
      <section className="system-heading">
        <span>Internal pilot</span>
        <h2>Pilot Operations</h2>
        <p>{NOTICE}</p>
      </section>
      <button type="button" onClick={load} style={{ marginBottom: '16px' }}>Refresh</button>

      <h3>Runtime</h3>
      <section className="card-grid">
        <StatusCard label="Runtime backend" value={health.backend_type} tone={health.available ? 'good' : 'waiting'} />
        <StatusCard label="Loaded model" value={health.current_model ?? 'none'} tone={health.loaded ? 'good' : 'waiting'} />
        <StatusCard label="Runtime health" value={health.available ? 'available' : 'unavailable'} tone={health.available ? 'good' : 'waiting'} />
        <StatusCard label="Database schema version" value={schemaVersion} />
      </section>
      {!health.available && health.error_message && (
        <p className="notice">Runtime status: {health.error_message}</p>
      )}

      <h3>Grounded chat</h3>
      <section className="card-grid">
        <StatusCard
          label="Active retrieval profile"
          value={defaultProfile.retrieval_profile_public_id ? defaultProfile.name : 'none set'}
          tone={defaultProfile.retrieval_profile_public_id ? 'good' : 'waiting'}
        />
        <StatusCard label="Knowledge spaces" value={knowledgeSpaceCount} />
        <StatusCard label="Active retrieval profiles" value={activeProfileCount} />
      </section>

      <h3>Recent audit events (last 20)</h3>
      {auditEvents.length === 0 ? (
        <div className="notice">No audit events have been recorded yet.</div>
      ) : (
        <div className="audit-list">
          {auditEvents.map((event) => (
            <article key={event.public_id}>
              <div>
                <strong>{event.event_type.replaceAll('_', ' ')}</strong>
                <span>{event.outcome}</span>
              </div>
              <small>{new Date(event.created_at).toLocaleString()}</small>
            </article>
          ))}
        </div>
      )}
    </>
  )
}
