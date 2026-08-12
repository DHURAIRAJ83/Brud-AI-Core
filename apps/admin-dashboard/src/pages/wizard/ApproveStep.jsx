import { useCallback, useEffect, useState } from 'react'
import Button from '../../components/Button.jsx'
import ErrorBanner from '../../components/ErrorBanner.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import { bulkApproveDocumentSftCandidates, documentSftCandidateSummary, documentSftCandidates } from '../../services/api.js'

function isLowRiskPending(item) {
  return item.quality_status === 'pending_review' && item.rights_status === 'verified' && item.generation_method === 'template_heuristic_v1'
}

export default function ApproveStep({ documentId, onComplete, toast }) {
  const [candidates, setCandidates] = useState([])
  const [summary, setSummary] = useState(null)
  const [selected, setSelected] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [list, summaryResult] = await Promise.all([
        documentSftCandidates(documentId),
        documentSftCandidateSummary(documentId).catch(() => null),
      ])
      setCandidates(list.items ?? [])
      setSummary(summaryResult)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setLoading(false)
    }
  }, [documentId])

  useEffect(() => { load() }, [load])

  const lowRiskPending = candidates.filter(isLowRiskPending)

  function toggle(id) {
    setSelected((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]))
  }

  async function bulkApprove() {
    setBusy(true)
    try {
      await bulkApproveDocumentSftCandidates(documentId, selected)
      toast.success(`${selected.length} candidate(s) bulk-approved.`)
      setSelected([])
      await load()
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBusy(false)
    }
  }

  function confirmAndContinue() {
    onComplete({ toastMessage: 'Review approved. Continuing to Build RAG.' })
  }

  if (loading) return <Skeleton lines={4} />
  if (error) return <ErrorBanner message={error} onRetry={load} />

  const approvedCount = summary?.approved_count ?? candidates.filter((item) => item.quality_status === 'approved').length

  return (
    <section>
      <h3>Approve</h3>
      <p className="notice">A final batch gate before RAG ingestion -- confirm counts below, optionally bulk-approve remaining low-risk candidates.</p>

      <section className="metric-grid">
        <article className="status-card"><span>Total candidates</span><strong>{candidates.length}</strong></article>
        <article className="status-card"><span>Approved</span><strong>{approvedCount}</strong></article>
        <article className="status-card"><span>Pending</span><strong>{candidates.filter((item) => item.quality_status === 'pending_review').length}</strong></article>
        <article className="status-card"><span>Rejected</span><strong>{candidates.filter((item) => item.quality_status === 'rejected').length}</strong></article>
      </section>

      {lowRiskPending.length > 0 && (
        <>
          <h3>Remaining low-risk candidates</h3>
          <div className="candidate-list">
            {lowRiskPending.map((item) => (
              <article key={item.public_id}>
                <header>
                  <input
                    type="checkbox"
                    aria-label={`Select candidate ${item.public_id}`}
                    checked={selected.includes(item.public_id)}
                    onChange={() => toggle(item.public_id)}
                  />
                  <strong>{item.task.replaceAll('_', ' ')}</strong>
                </header>
              </article>
            ))}
          </div>
          <Button variant="secondary" loading={busy} disabled={selected.length === 0} onClick={bulkApprove}>
            Bulk approve {selected.length} selected (low-risk only)
          </Button>
        </>
      )}

      <div className="wizard-nav">
        <Button variant="primary" onClick={confirmAndContinue}>Confirm and continue</Button>
      </div>
    </section>
  )
}
