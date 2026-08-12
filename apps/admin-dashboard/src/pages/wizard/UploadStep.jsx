import { useEffect, useState } from 'react'
import Button from '../../components/Button.jsx'
import ErrorBanner from '../../components/ErrorBanner.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import { dataSources, documentWorkspace, documents, linkDocumentSource, uploadDocument } from '../../services/api.js'

export default function UploadStep({ documentId, documentTitle, onDocumentReady, onComplete, toast }) {
  const [docList, setDocList] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [file, setFile] = useState(null)
  const [strategy, setStrategy] = useState('auto')
  const [language, setLanguage] = useState('ta')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // A page cannot be approved (blocking the Chunk step) until its document
  // has a linked data source -- a real backend constraint, not a UI
  // choice. Selecting/uploading a document only finishes this step once a
  // source is confirmed linked (or already was).
  const [pendingDocument, setPendingDocument] = useState(null) // { id, title }
  const [checkingLink, setCheckingLink] = useState(false)
  const [sourceOptions, setSourceOptions] = useState([])
  const [selectedSourceId, setSelectedSourceId] = useState('')
  const [linking, setLinking] = useState(false)

  useEffect(() => {
    documents()
      .then((data) => setDocList(data.items ?? []))
      .catch(() => setDocList([]))
      .finally(() => setLoaded(true))
  }, [])

  async function chooseDocument(id, title) {
    setPendingDocument({ id, title })
    setCheckingLink(true)
    try {
      const workspace = await documentWorkspace(id)
      if (workspace.source_status === 'linked') {
        onDocumentReady(id, title)
        onComplete({ toastMessage: `"${title}" is ready (source already linked).` })
        return
      }
      const sources = await dataSources('').catch(() => ({ items: [] }))
      setSourceOptions(sources.items ?? [])
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setCheckingLink(false)
    }
  }

  async function resume(item) {
    await chooseDocument(item.public_id, item.original_filename)
  }

  async function submit(event) {
    event.preventDefault()
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('extraction_strategy', strategy)
      form.append('language', language)
      const document = await uploadDocument(form)
      await chooseDocument(document.public_id, document.original_filename)
    } catch (reason) {
      setError(reason.message)
      toast.error(reason.message)
    } finally {
      setBusy(false)
    }
  }

  async function linkSource() {
    if (!pendingDocument || !selectedSourceId) return
    setLinking(true)
    try {
      await linkDocumentSource(pendingDocument.id, selectedSourceId)
      onDocumentReady(pendingDocument.id, pendingDocument.title)
      onComplete({ toastMessage: `Data source linked to "${pendingDocument.title}".` })
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setLinking(false)
    }
  }

  if (documentId) {
    return (
      <section className="notice">
        <strong>Document selected</strong>
        <p>{documentTitle || documentId}</p>
      </section>
    )
  }

  if (pendingDocument) {
    return (
      <section>
        <h3>Link a data source</h3>
        <p className="notice">
          "{pendingDocument.title}" has no linked data source yet -- pages can't be approved (and Chunk
          generation stays blocked) until one is linked.
        </p>
        {checkingLink ? (
          <Skeleton lines={2} />
        ) : sourceOptions.length === 0 ? (
          <div className="notice">No data sources yet. Create one on the Sources &amp; Rights page, then come back and resume this document.</div>
        ) : (
          <>
            <label>
              Data source
              <select value={selectedSourceId} onChange={(event) => setSelectedSourceId(event.target.value)}>
                <option value="">Choose a source…</option>
                {sourceOptions.map((source) => (
                  <option key={source.public_id} value={source.public_id}>{source.source_code} -- {source.title}</option>
                ))}
              </select>
            </label>
            <Button variant="primary" loading={linking} disabled={!selectedSourceId} onClick={linkSource}>
              Link source
            </Button>
          </>
        )}
      </section>
    )
  }

  return (
    <section>
      <h3>Upload a document</h3>
      <p className="notice">Start a new document, or resume one already uploaded on the Documents page.</p>

      {error && <ErrorBanner message={error} onRetry={() => setError('')} />}

      <form className="inline-form" onSubmit={submit}>
        <label style={{ gridColumn: '1 / -1' }}>
          PDF document
          <input type="file" accept="application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
        <label>
          Extraction strategy
          <select value={strategy} onChange={(event) => setStrategy(event.target.value)}>
            <option value="auto">Auto</option>
            <option value="embedded_text">Embedded text</option>
            <option value="ocr">OCR</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </label>
        <label>
          Language
          <select value={language} onChange={(event) => setLanguage(event.target.value)}>
            <option value="ta">Tamil</option>
            <option value="en">English</option>
            <option value="mixed">Tanglish</option>
          </select>
        </label>
        <div style={{ gridColumn: '1 / -1' }}>
          <Button type="submit" variant="primary" loading={busy} disabled={!file}>Upload securely</Button>
        </div>
      </form>

      <h3>Resume an existing document</h3>
      {!loaded ? (
        <Skeleton lines={3} />
      ) : docList.length === 0 ? (
        <div className="notice">No documents uploaded yet.</div>
      ) : (
        <div className="document-list">
          {docList.map((item) => (
            <button key={item.public_id} type="button" onClick={() => resume(item)}>
              <strong>{item.original_filename}</strong>
              <span>{item.page_count} pages · {item.status}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
