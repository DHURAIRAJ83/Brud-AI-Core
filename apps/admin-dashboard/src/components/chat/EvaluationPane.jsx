import { useCallback, useEffect, useState } from 'react'
import Button from '../Button.jsx'
import Skeleton from '../Skeleton.jsx'
import { ecAutoEvaluate } from '../../services/api.js'

export default function EvaluationPane({ toast, onNavigate }) {
  const [evaluating, setEvaluating] = useState(false)
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  const runEvaluation = useCallback(async () => {
    setEvaluating(true)
    setError('')
    try {
      const res = await ecAutoEvaluate({
        run_id: `run-${Date.now().toString(36)}`,
        model_version: 'rudran-candidate-v1',
        dataset_version: 'ds-curated-v2',
        baseline_model_version: 'production-base-v1',
      })
      setReport(res?.report || res)
      toast?.success('Automated model evaluation completed.')
    } catch (err) {
      setError(err.message || 'Evaluation failed to execute')
      toast?.error(err.message || 'Evaluation failed')
    } finally {
      setEvaluating(false)
    }
  }, [toast])

  useEffect(() => {
    runEvaluation()
  }, [runEvaluation])

  return (
    <div className="assistant-pane" style={{ padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', height: '100%', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h4 style={{ margin: 0, fontSize: '0.95rem' }}>📈 Post-Training Evaluation</h4>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>
            17-Category Suite • Baseline Comparison
          </span>
        </div>
        <Button size="sm" variant="primary" disabled={evaluating} onClick={runEvaluation}>
          {evaluating ? 'Evaluating…' : '▶ Run Evaluation'}
        </Button>
      </div>

      {evaluating && (
        <div style={{ padding: '1rem', background: 'var(--color-surface)', borderRadius: '8px' }}>
          <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem' }}>Running 17-category automated evaluation suite…</p>
          <Skeleton lines={6} />
        </div>
      )}

      {error && (
        <div style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.1)', color: '#f87171', borderRadius: '6px', fontSize: '0.8rem' }}>
          ⚠️ {error}
        </div>
      )}

      {report && !evaluating && (
        <>
          {/* Verdict Banner */}
          <div style={{
            padding: '0.75rem',
            borderRadius: '8px',
            background: report.recommendation === 'READY' || report.recommendation === 'READY WITH LIMITATIONS'
              ? 'rgba(16, 185, 129, 0.12)'
              : 'rgba(239, 68, 68, 0.12)',
            border: `1px solid ${
              report.recommendation === 'READY' || report.recommendation === 'READY WITH LIMITATIONS'
                ? 'rgba(16, 185, 129, 0.3)'
                : 'rgba(239, 68, 68, 0.3)'
            }`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>Candidate: {report.model_version}</div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: report.recommendation === 'READY' ? '#34d399' : '#fbbf24' }}>
                Verdict: {report.recommendation}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-muted-text)' }}>Score vs Baseline</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>
                {report.overall_score != null ? `${(report.overall_score * 100).toFixed(1)}%` : 'N/A'}{' '}
                <span style={{ fontSize: '0.75rem', color: (report.overall_delta ?? 0) >= 0 ? '#34d399' : '#f87171' }}>
                  ({(report.overall_delta ?? 0) >= 0 ? '+' : ''}{((report.overall_delta ?? 0) * 100).toFixed(1)}%)
                </span>
              </div>
            </div>
          </div>

          {/* Natural Language Summary */}
          {report.natural_language_summary && (
            <div style={{ background: 'var(--color-surface)', padding: '0.65rem 0.75rem', borderRadius: '6px', border: '1px solid var(--color-border)', fontSize: '0.78rem', lineHeight: '1.45' }}>
              <strong>Admin Summary:</strong>
              <p style={{ margin: '0.25rem 0 0 0', color: 'var(--color-text-secondary, #cbd5e1)' }}>
                {report.natural_language_summary}
              </p>
            </div>
          )}

          {/* 17 Categories */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>Category Breakdown (17 Tests):</div>
            <div style={{ maxHeight: '220px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px', paddingRight: '4px' }}>
              {(report.categories || []).map((cat, idx) => (
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--color-surface)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.75rem', border: '1px solid var(--color-border)' }}>
                  <span>{cat.name}</span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600 }}>{(cat.candidate_score * 100).toFixed(0)}%</span>
                    <span style={{
                      fontSize: '0.7rem',
                      color: cat.status === 'IMPROVED' ? '#34d399' : cat.status === 'REGRESSED' ? '#f87171' : 'var(--color-muted-text)',
                    }}>
                      {cat.status === 'IMPROVED' ? '▲' : cat.status === 'REGRESSED' ? '▼' : '—'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
            {onNavigate && (
              <>
                <Button size="sm" variant="secondary" onClick={() => onNavigate('Evaluation')}>View Full Evaluation</Button>
                <Button size="sm" variant="secondary" onClick={() => onNavigate('Core Model')}>Open Model Registry</Button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
