import { useCallback, useEffect, useState } from 'react'
import Button from '../../components/Button.jsx'
import ErrorBanner from '../../components/ErrorBanner.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import { analyzeDocument, approveDocumentPage, documentDetail, documentPages, processDocument } from '../../services/api.js'

export default function OcrStep({ documentId, onComplete, toast }) {
  const [detail, setDetail] = useState(null)
  const [pages, setPages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [detailResult, pagesResult] = await Promise.all([
        documentDetail(documentId),
        documentPages(documentId).catch(() => ({ items: [] })),
      ])
      setDetail(detailResult)
      setPages(pagesResult.items ?? [])
    } catch (reason) {
      setError(reason.message)
    } finally {
      setLoading(false)
    }
  }, [documentId])

  useEffect(() => { load() }, [load])

  async function runAnalyze() {
    setBusy('analyze')
    try {
      await analyzeDocument(documentId)
      toast.success('Pages analyzed.')
      await load()
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBusy('')
    }
  }

  async function runProcess() {
    setBusy('process')
    try {
      await processDocument(documentId, { strategy: detail?.extraction_strategy ?? 'auto' })
      toast.success('OCR/extraction complete.')
      await load()
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBusy('')
    }
  }

  async function approve(pageNumber) {
    setBusy(`approve-${pageNumber}`)
    try {
      await approveDocumentPage(documentId, pageNumber)
      await load()
      onComplete({ toastMessage: `Page ${pageNumber} approved.` })
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBusy('')
    }
  }

  if (loading && !detail) return <Skeleton lines={4} />
  if (error) return <ErrorBanner message={error} onRetry={load} />

  return (
    <section>
      <h3>OCR &amp; extraction</h3>
      <p className="notice">
        Deep per-page editing (manual text correction, OCR rerun, revisions) stays on the Documents page --
        this step only unblocks Chunk generation by getting at least one page approved.
      </p>
      <div className="document-actions">
        <Button variant="secondary" loading={busy === 'analyze'} onClick={runAnalyze}>Analyze pages</Button>
        <Button variant="primary" loading={busy === 'process'} onClick={runProcess}>
          Process {detail?.extraction_strategy ?? 'auto'}
        </Button>
      </div>

      {pages.length === 0 ? (
        <div className="notice">No pages yet -- analyze and process the document first.</div>
      ) : (
        <div className="page-grid">
          {pages.map((page) => (
            <div key={page.page_number} className="notice">
              <strong>Page {page.page_number}</strong>
              <span className="review-status-badge">{page.review_status || 'pending'}</span>
              <div>
                <Button
                  size="sm"
                  variant="success"
                  loading={busy === `approve-${page.page_number}`}
                  disabled={page.review_status === 'approved'}
                  onClick={() => approve(page.page_number)}
                >
                  {page.review_status === 'approved' ? 'Approved' : 'Approve'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
