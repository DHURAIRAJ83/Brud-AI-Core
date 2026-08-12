import { useState } from 'react'
import Button from '../../components/Button.jsx'
import { detectDocumentRepeatedElements, documentRepeatedElements, reviewDocumentRepeatedElement } from '../../services/api.js'

export default function CleanStep({ documentId, onComplete, toast }) {
  const [repeated, setRepeated] = useState([])
  const [detected, setDetected] = useState(false)
  const [busy, setBusy] = useState('')

  async function detect() {
    setBusy('detect')
    try {
      await detectDocumentRepeatedElements(documentId)
      const result = await documentRepeatedElements(documentId)
      setRepeated(result.items ?? [])
      setDetected(true)
      toast.success('Repeated-element detection complete.')
      onComplete({ toastMessage: 'Cleanup pass recorded.' })
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBusy('')
    }
  }

  async function review(elementId, actionName, options = {}) {
    setBusy(elementId)
    try {
      await reviewDocumentRepeatedElement(documentId, elementId, actionName, options)
      const result = await documentRepeatedElements(documentId)
      setRepeated(result.items ?? [])
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBusy('')
    }
  }

  return (
    <section>
      <h3>Clean</h3>
      <p className="notice">
        Deterministic cross-page detection of repeated headers/footers/page numbers -- nothing is removed
        until explicitly confirmed. Per-page cleanup suggestions stay on the Documents page for deeper work.
      </p>
      <Button variant="secondary" loading={busy === 'detect'} onClick={detect}>Detect repeated elements</Button>

      {detected && repeated.length === 0 && <div className="notice">No repeated-element suggestions found.</div>}

      {repeated.length > 0 && (
        <div className="candidate-list">
          {repeated.map((item) => (
            <article key={item.public_id}>
              <header>
                <strong>{item.element_type}</strong>
                <span>{item.status} · confidence {item.confidence} · pages {item.page_occurrences?.join(', ')}</span>
              </header>
              <p>{item.normalized_text}</p>
              <div className="review-actions">
                <Button size="sm" variant="success" disabled={busy === item.public_id || item.status !== 'suggested'} onClick={() => review(item.public_id, 'accept', {})}>
                  Accept removal
                </Button>
                <Button size="sm" variant="ghost" disabled={busy === item.public_id || item.status !== 'suggested'} onClick={() => review(item.public_id, 'reject', {})}>
                  Reject suggestion
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
