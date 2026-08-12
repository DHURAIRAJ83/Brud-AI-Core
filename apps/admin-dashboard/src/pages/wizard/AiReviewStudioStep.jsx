import { useCallback, useEffect, useMemo, useState } from 'react'
import Button from '../../components/Button.jsx'
import ErrorBanner from '../../components/ErrorBanner.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import {
  documentSftCandidateSummary,
  documentSftCandidates,
  generateDocumentSftCandidates,
  reviewDocumentSftCandidate,
} from '../../services/api.js'

// Real LCS-based word diff -- no new dependency. Used to highlight exactly
// which words changed between the original AI output and the admin's edits.
function diffWords(original, edited) {
  const a = (original || '').split(/(\s+)/)
  const b = (edited || '').split(/(\s+)/)
  const m = a.length
  const n = b.length
  const table = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1])
    }
  }
  const result = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (a[i] === b[j]) { result.push({ type: 'same', text: a[i] }); i += 1; j += 1 }
    else if (table[i + 1][j] >= table[i][j + 1]) { result.push({ type: 'removed', text: a[i] }); i += 1 }
    else { result.push({ type: 'added', text: b[j] }); j += 1 }
  }
  while (i < m) { result.push({ type: 'removed', text: a[i] }); i += 1 }
  while (j < n) { result.push({ type: 'added', text: b[j] }); j += 1 }
  return result
}

function DiffLine({ original, edited }) {
  if (original === edited) return <p>{edited}</p>
  const parts = diffWords(original, edited)
  return (
    <p>
      {parts.map((part, index) => {
        if (part.type === 'same') return <span key={index}>{part.text}</span>
        const className = part.type === 'removed' ? 'wizard-diff-removed' : 'wizard-diff-added'
        return <span key={index} className={className}>{part.text}</span>
      })}
    </p>
  )
}

export default function AiReviewStudioStep({ documentId, onComplete, toast }) {
  const [candidates, setCandidates] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const [editedInstruction, setEditedInstruction] = useState('')
  const [editedContext, setEditedContext] = useState('')
  const [editedResponse, setEditedResponse] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState('')
  const [detached, setDetached] = useState(false)

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

  const selected = candidates.find((item) => item.public_id === selectedId) ?? null

  useEffect(() => {
    setEditedInstruction(selected?.instruction ?? '')
    setEditedContext(selected?.context ?? '')
    setEditedResponse(selected?.response ?? '')
    setNotes('')
  }, [selectedId, selected?.instruction, selected?.context, selected?.response])

  const hasUnsavedEdits = useMemo(() => {
    if (!selected) return false
    return editedInstruction !== (selected.instruction ?? '')
      || editedContext !== (selected.context ?? '')
      || editedResponse !== (selected.response ?? '')
  }, [selected, editedInstruction, editedContext, editedResponse])

  useEffect(() => {
    if (!hasUnsavedEdits) return undefined
    function handleBeforeUnload(event) {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedEdits])

  async function generate() {
    setGenerating(true)
    try {
      await generateDocumentSftCandidates(documentId, {})
      toast.success('SFT candidates generated.')
      await load()
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setGenerating(false)
    }
  }

  async function runReview(action) {
    if (!selected) return
    setBusy(action)
    try {
      const options = action === 'edit'
        ? { edited_instruction: editedInstruction, edited_context: editedContext, edited_response: editedResponse, notes }
        : { notes }
      await reviewDocumentSftCandidate(documentId, selected.public_id, { action, ...options })
      await load()
      const label = { approve: 'approved', reject: 'rejected', needs_correction: 'flagged for correction', edit: 'edits saved' }[action]
      if (action === 'edit') {
        toast.success(`Candidate ${label}.`)
      } else {
        onComplete({ toastMessage: `Candidate ${label}.` })
      }
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBusy('')
    }
  }

  if (loading) return <Skeleton lines={5} />
  if (error) return <ErrorBanner message={error} onRetry={load} />

  return (
    <section className="candidate-review">
      <header className="section-heading">
        <div>
          <h3>AI Review Studio</h3>
          <p>Generated only from approved chunks with verified rights. Edit, then approve/reject/flag for correction.</p>
        </div>
        <Button variant="secondary" loading={generating} onClick={generate}>Generate SFT candidates</Button>
      </header>

      {summary && (
        <section className="metric-grid">
          <article className="status-card"><span>Total candidates</span><strong>{summary.total_candidates}</strong></article>
          <article className="status-card"><span>Approved</span><strong>{summary.approved_count}</strong></article>
        </section>
      )}

      {candidates.length === 0 ? (
        <div className="notice">No SFT candidates yet. Approve pages and generate chunks first, then generate candidates here.</div>
      ) : (
        <div className="training-grid">
          <div className="data-list">
            {candidates.map((item) => (
              <article key={item.public_id} className={item.public_id === selectedId ? 'active' : ''}>
                <div>
                  <strong>{item.task.replaceAll('_', ' ')}</strong>
                  <span>{item.quality_status} · rights {item.rights_status}</span>
                </div>
                <button type="button" onClick={() => setSelectedId(item.public_id)}>Review</button>
              </article>
            ))}
          </div>

          {selected && (
            <div className="training-detail">
              <div className="section-heading">
                <h3>Raw AI output</h3>
                <Button variant="ghost" size="sm" onClick={() => setDetached((value) => !value)}>
                  {detached ? 'Dock preview' : 'Detach preview'}
                </Button>
              </div>
              <p><strong>Instruction:</strong> {selected.instruction}</p>
              {selected.context && <p><strong>Context:</strong> {selected.context}</p>}
              <p><strong>Response:</strong> {selected.response}</p>

              <h3>Editable form</h3>
              <label>
                Instruction
                <textarea rows={2} value={editedInstruction} onChange={(event) => setEditedInstruction(event.target.value)} />
              </label>
              <label>
                Context
                <textarea rows={2} value={editedContext} onChange={(event) => setEditedContext(event.target.value)} />
              </label>
              <label>
                Response
                <textarea rows={4} value={editedResponse} onChange={(event) => setEditedResponse(event.target.value)} />
              </label>
              {hasUnsavedEdits && <p className="unsaved-note">Unsaved edits</p>}

              <div className={`wizard-diff ${detached ? 'wizard-diff-detached' : ''}`}>
                <div>
                  <h3>Original vs. edited (instruction)</h3>
                  <DiffLine original={selected.instruction} edited={editedInstruction} />
                </div>
                <div>
                  <h3>Original vs. edited (response)</h3>
                  <DiffLine original={selected.response} edited={editedResponse} />
                </div>
              </div>

              <label>
                Notes
                <textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
              </label>

              {selected.rights_status !== 'verified' && (
                <p className="row-warning">Rights not verified -- cannot approve until the linked source's rights are confirmed.</p>
              )}

              <div className="review-actions">
                <Button size="sm" variant="secondary" loading={busy === 'edit'} disabled={!hasUnsavedEdits} onClick={() => runReview('edit')}>
                  Save Edits
                </Button>
                <Button
                  size="sm" variant="success" loading={busy === 'approve'}
                  disabled={selected.quality_status === 'approved' || selected.rights_status !== 'verified'}
                  onClick={() => runReview('approve')}
                >
                  Approve
                </Button>
                <Button size="sm" variant="danger" loading={busy === 'reject'} disabled={selected.quality_status === 'rejected'} onClick={() => runReview('reject')}>
                  Reject
                </Button>
                <Button size="sm" variant="warning" loading={busy === 'needs_correction'} onClick={() => runReview('needs_correction')}>
                  Needs Correction
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
