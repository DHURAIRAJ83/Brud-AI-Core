import { useCallback, useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import { systemPilotMetrics } from '../services/api.js'

const NOTICE = 'MB-48: internal pilot usage telemetry -- every counter below is a row already written to the existing audit_logs table (no external analytics service, no new table). Counts are cumulative since this database was created.'

const METRIC_LABELS = {
  widget_plain_chat_count: 'Widget plain chats sent',
  widget_grounded_chat_count: 'Widget grounded chats sent',
  grounded_chat_citation_render_count: 'Grounded replies with citations shown',
  retrieval_profile_switch_count: 'Default retrieval profile switches',
  prompt_optimization_run_count: 'Prompt optimization runs',
  gateway_export_run_count: 'Gateway dataset exports',
}

export default function PilotMetricsPage() {
  const [state, setState] = useState({ loading: true, error: '' })

  const load = useCallback(async () => {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const counts = await systemPilotMetrics()
      setState({ loading: false, error: '', counts })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (state.loading) return <div className="notice">Loading pilot metrics…</div>
  if (state.error) {
    return (
      <div className="notice error-notice">
        <strong>Unable to load pilot metrics</strong>
        <p>{state.error}</p>
        <button type="button" onClick={load}>Retry</button>
      </div>
    )
  }

  const { counts } = state
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0)

  return (
    <>
      <section className="system-heading">
        <span>Internal pilot</span>
        <h2>Pilot Metrics</h2>
        <p>{NOTICE}</p>
      </section>
      <button type="button" onClick={load} style={{ marginBottom: '16px' }}>Refresh</button>

      {total === 0 ? (
        <div className="notice">No pilot usage has been recorded yet -- counts will appear here once admins start using the widget, RAG page, prompt optimization, and gateway export.</div>
      ) : (
        <section className="card-grid">
          {Object.entries(METRIC_LABELS).map(([key, label]) => (
            <StatusCard key={key} label={label} value={counts[key] ?? 0} tone={(counts[key] ?? 0) > 0 ? 'good' : 'neutral'} />
          ))}
        </section>
      )}
    </>
  )
}
