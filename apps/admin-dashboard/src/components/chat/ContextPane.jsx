import { useCallback, useEffect, useState } from 'react'
import Button from '../Button.jsx'
import Skeleton from '../Skeleton.jsx'
import { miniBrainContext } from '../../services/api.js'

export default function ContextPane({ toast, onNavigate, onAskAboutContext }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [context, setContext] = useState(null)

  const fetchContext = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await miniBrainContext()
      setContext(data)
    } catch (err) {
      setError(err.message || 'Context unavailable')
      toast?.error('Failed to load operational context')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    fetchContext()
  }, [fetchContext])

  if (loading) {
    return (
      <div className="assistant-pane" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <h4 style={{ margin: 0 }}>📊 Loading System Context…</h4>
        <Skeleton lines={8} />
      </div>
    )
  }

  if (error || !context) {
    return (
      <div className="assistant-pane" style={{ padding: '1rem', textAlign: 'center' }}>
        <p style={{ color: 'var(--color-error, #f87171)', margin: '0 0 0.75rem 0' }}>
          ⚠️ {error || 'Context unavailable'}
        </p>
        <Button size="sm" variant="secondary" onClick={fetchContext}>Retry</Button>
      </div>
    )
  }

  const {
    system = {},
    providers = {},
    models = {},
    datasets = {},
    training = {},
    evaluation = {},
    rag = {},
    governance = {},
    recent_events = [],
    recommendations = [],
  } = context

  return (
    <div className="assistant-pane" style={{ padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', height: '100%', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h4 style={{ margin: 0, fontSize: '0.95rem' }}>📊 Operational Context</h4>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>
            Phase 61 Canonical • Live Snapshot
          </span>
        </div>
        <Button size="sm" variant="ghost" onClick={fetchContext} title="Refresh Context">🔄 Refresh</Button>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div style={{ background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '8px', padding: '0.5rem 0.75rem' }}>
          <strong style={{ fontSize: '0.8rem', color: '#38bdf8' }}>💡 Recommendations</strong>
          <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.78rem' }}>
            {recommendations.map((rec, i) => (
              <li key={i} style={{ margin: '2px 0' }}>
                {rec.message}{' '}
                {onNavigate && rec.nav_key && (
                  <button
                    type="button"
                    style={{ background: 'none', border: 'none', color: '#38bdf8', textDecoration: 'underline', cursor: 'pointer', padding: 0, font: 'inherit' }}
                    onClick={() => onNavigate(rec.nav_key)}
                  >
                    Open {rec.nav_key}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Subsystem Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
        {/* System & Health */}
        <div style={{ background: 'var(--color-surface)', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>System Status</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: system.overall_status === 'healthy' ? '#34d399' : '#fbbf24' }}>
            ● {system.overall_status || 'healthy'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--color-muted-text)' }}>DB Connected: {system.database_connected ? 'Yes' : 'No'}</div>
        </div>

        {/* Models */}
        <div style={{ background: 'var(--color-surface)', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>Active Runtime</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {models.backend_type || 'auto'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--color-muted-text)' }}>Local: {models.local_available ? 'Ready' : 'Not Loaded'}</div>
        </div>

        {/* Datasets */}
        <div style={{ background: 'var(--color-surface)', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>Datasets</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
            {datasets.total_dataset_versions ?? 0} Versions
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--color-muted-text)' }}>Ready: {datasets.training_ready ? 'Yes' : 'Pending'}</div>
        </div>

        {/* Training */}
        <div style={{ background: 'var(--color-surface)', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>Training Engine</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
            {training.training_gate_locked ? 'Gate Locked' : 'Unlocked'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--color-muted-text)' }}>Runs: {training.total_runs ?? 0}</div>
        </div>

        {/* Evaluation */}
        <div style={{ background: 'var(--color-surface)', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>Evaluation</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
            {evaluation.evaluation_status || 'None'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--color-muted-text)' }}>Score: {evaluation.latest_score != null ? `${(evaluation.latest_score * 100).toFixed(1)}%` : 'N/A'}</div>
        </div>

        {/* Governance */}
        <div style={{ background: 'var(--color-surface)', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>Governance</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#38bdf8' }}>
            {governance.admin_assistant_authority || 'ADVISORY_ONLY'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--color-muted-text)' }}>Pending: {governance.pending_proposals_count ?? 0}</div>
        </div>
      </div>

      {/* Deep-Link Shortcuts */}
      <div style={{ marginTop: '0.25rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-muted-text)' }}>Quick Dashboard Links:</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
          {onNavigate && (
            <>
              <Button size="sm" variant="secondary" onClick={() => onNavigate('Datasets')}>Open Datasets</Button>
              <Button size="sm" variant="secondary" onClick={() => onNavigate('Core Model')}>Open Models</Button>
              <Button size="sm" variant="secondary" onClick={() => onNavigate('Training')}>Open Training</Button>
              <Button size="sm" variant="secondary" onClick={() => onNavigate('Evaluation')}>Open Evaluation</Button>
              <Button size="sm" variant="secondary" onClick={() => onNavigate('Governance')}>Open Governance</Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
