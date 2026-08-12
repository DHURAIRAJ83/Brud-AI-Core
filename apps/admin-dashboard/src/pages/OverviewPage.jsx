import { useCallback, useEffect, useState } from 'react'
import Button from '../components/Button.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusCard from '../components/StatusCard.jsx'
import {
  getOverview,
  miniBrainDefaultRetrievalProfile,
  miniBrainWidgetHealth,
  ragSpaces,
  systemPilotMetrics,
  systemRecentAudit,
} from '../services/api.js'

export default function OverviewPage({ onNavigate }) {
  const [state, setState] = useState({ loading: true, error: '' })

  const load = useCallback(async () => {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [overview, spaces, metrics, health, defaultProfile, audit] = await Promise.all([
        getOverview(),
        ragSpaces(),
        systemPilotMetrics(),
        miniBrainWidgetHealth(),
        miniBrainDefaultRetrievalProfile(),
        systemRecentAudit(20),
      ])
      setState({
        loading: false, error: '',
        overview, health, defaultProfile, metrics,
        knowledgeSpaceCount: (spaces.items ?? []).length,
        auditEvents: audit.items ?? [],
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (state.loading) {
    return (
      <>
        <section className="system-heading"><span>Overview</span><h2>Overview</h2></section>
        <section className="overview-card-grid">
          {Array.from({ length: 8 }, (_, index) => (
            <article key={index} className="status-card"><Skeleton lines={2} /></article>
          ))}
        </section>
      </>
    )
  }

  if (state.error) {
    return (
      <>
        <section className="system-heading"><span>Overview</span><h2>Overview</h2></section>
        <ErrorBanner title="Unable to load overview" message={state.error} onRetry={load} />
      </>
    )
  }

  const { overview, health, defaultProfile, metrics, knowledgeSpaceCount, auditEvents } = state

  return (
    <>
      <section className="system-heading">
        <span>Overview</span>
        <h2>Overview</h2>
        <p>A single-entry snapshot of Brud AI's current state -- data, knowledge, runtime, and usage.</p>
      </section>
      <button type="button" onClick={load} style={{ marginBottom: '16px' }}>Refresh</button>

      <section className="overview-card-grid">
        <StatusCard label="Total Datasets" value={overview.dataset_sources} />
        <StatusCard label="Knowledge Spaces" value={knowledgeSpaceCount} />
        <StatusCard label="Total Chats" value={metrics.widget_plain_chat_count} />
        <StatusCard label="Total Grounded Chats" value={metrics.widget_grounded_chat_count} />
        <StatusCard label="Total Prompt Runs" value={metrics.prompt_optimization_run_count} />
        <StatusCard label="Gateway Exports" value={metrics.gateway_export_run_count} />
        <StatusCard label="Runtime Health" value={health.available ? 'available' : 'unavailable'} tone={health.available ? 'good' : 'waiting'} />
        <StatusCard
          label="Active Retrieval Profile"
          value={defaultProfile.retrieval_profile_public_id ? defaultProfile.name : 'none set'}
          tone={defaultProfile.retrieval_profile_public_id ? 'good' : 'waiting'}
        />
      </section>

      <h3>Quick Actions</h3>
      <section className="quick-actions">
        <Button variant="primary" onClick={() => onNavigate?.('Data Workspace Wizard')}>Upload Dataset</Button>
        <Button variant="secondary" onClick={() => onNavigate?.('Brud Mini Brain')}>Start Grounded Chat</Button>
        <Button variant="secondary" onClick={() => onNavigate?.('Knowledge & RAG')}>Switch Profile</Button>
        <Button variant="ghost" onClick={() => onNavigate?.('Pilot Metrics')}>Open Pilot Metrics</Button>
      </section>

      <h3>Recent Activity</h3>
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
