import { useCallback, useEffect, useState } from 'react'
import Button from '../../components/Button.jsx'
import ErrorBanner from '../../components/ErrorBanner.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import { copyToClipboard } from '../../utils/clipboard.js'
import {
  createRagChunkSet,
  createRagSource,
  createRagSourceVersion,
  documentChunks,
  documentDetail,
  ragSpaces,
  validateRagChunkSet,
  validateRagSourceVersion,
} from '../../services/api.js'

const LARGE_DOCUMENT_THRESHOLD_BYTES = 5_000_000
const PREVIEW_CHAR_LIMIT = 4000

function CopyButton({ label, value, toast }) {
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={async () => {
        const copied = await copyToClipboard(value)
        if (copied) toast.success(`${label} copied.`)
        else toast.error(`Could not copy ${label.toLowerCase()}.`)
      }}
    >
      Copy {label}
    </Button>
  )
}

export default function BuildRagStep({ documentId, onComplete, onNavigate, toast }) {
  const [spaces, setSpaces] = useState([])
  const [spaceId, setSpaceId] = useState('')
  const [content, setContent] = useState('')
  const [contentBytes, setContentBytes] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [building, setBuilding] = useState(false)
  const [result, setResult] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [spacesResult, chunksResult, detail] = await Promise.all([
        ragSpaces(),
        documentChunks(documentId),
        documentDetail(documentId),
      ])
      const items = spacesResult.items ?? []
      setSpaces(items)
      setSpaceId((current) => current || items[0]?.public_id || '')
      const approvedText = (chunksResult.items ?? [])
        .filter((chunk) => chunk.status === 'approved')
        .map((chunk) => chunk.active_revision?.text || '')
        .join('\n\n')
      setContent(approvedText || `Content from ${detail.original_filename}`)
      setContentBytes(new Blob([approvedText]).size)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setLoading(false)
    }
  }, [documentId])

  useEffect(() => { load() }, [load])

  async function build() {
    if (!spaceId) {
      toast.error('Choose a knowledge space first.')
      return
    }
    setBuilding(true)
    try {
      const source = await createRagSource(spaceId, {
        source_type: 'plain_text', title: `Wizard ingestion ${documentId}`, language: 'ta',
        licence_status: 'unknown', content,
      })
      const version = await createRagSourceVersion(source.public_id)
      await validateRagSourceVersion(version.public_id)
      const chunkSet = await createRagChunkSet(version.public_id, { chunking_strategy: 'heading_aware' })
      await validateRagChunkSet(chunkSet.public_id)
      setResult({ sourceId: source.public_id, versionId: version.public_id, chunkSetId: chunkSet.public_id })
      onComplete({ toastMessage: 'RAG source, version, and chunk set created and validated.' })
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBuilding(false)
    }
  }

  if (loading) return <Skeleton lines={4} />
  if (error) return <ErrorBanner message={error} onRetry={load} />

  const isLarge = contentBytes > LARGE_DOCUMENT_THRESHOLD_BYTES
  const preview = isLarge ? content.slice(0, PREVIEW_CHAR_LIMIT) : content

  return (
    <section>
      <h3>Build RAG</h3>
      <p className="notice">
        Creates a real RAG source, source version, and chunk set from the document's approved chunk text --
        the first real step of RAG ingestion. Embedding model selection, vector/keyword index build, and
        retrieval profile activation are separate, more involved decisions that stay on the Knowledge &amp;
        RAG page -- this step honestly reports what it actually built, not that RAG is fully live.
      </p>

      {!result ? (
        <>
          <label>
            Knowledge space
            <select value={spaceId} onChange={(event) => setSpaceId(event.target.value)}>
              {spaces.length === 0 && <option value="">No knowledge spaces yet</option>}
              {spaces.map((space) => <option key={space.public_id} value={space.public_id}>{space.name}</option>)}
            </select>
          </label>

          {isLarge && (
            <p className="row-warning">
              Preview truncated -- content is {(contentBytes / 1_000_000).toFixed(1)}MB. The full content will
              still be sent to the API.
            </p>
          )}
          <pre className="notice" style={{ whiteSpace: 'pre-wrap', maxHeight: '220px', overflow: 'auto' }}>{preview}</pre>

          <Button variant="primary" loading={building} disabled={!spaceId} onClick={build}>Build RAG</Button>
        </>
      ) : (
        <div className="notice success-note">
          <strong>RAG source created and validated.</strong>
          <div className="data-list">
            <article>
              <div><strong>Source</strong><span>{result.sourceId}</span></div>
              <CopyButton label="Source ID" value={result.sourceId} toast={toast} />
            </article>
            <article>
              <div><strong>Version</strong><span>{result.versionId}</span></div>
              <CopyButton label="Version ID" value={result.versionId} toast={toast} />
            </article>
            <article>
              <div><strong>Chunk set</strong><span>{result.chunkSetId}</span></div>
              <CopyButton label="Chunk set ID" value={result.chunkSetId} toast={toast} />
            </article>
          </div>
          <Button variant="secondary" onClick={() => onNavigate?.('Knowledge & RAG')}>
            Continue building the embedding &amp; index in Knowledge &amp; RAG
          </Button>
        </div>
      )}
    </section>
  )
}
