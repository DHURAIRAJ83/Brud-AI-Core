import { useCallback, useEffect, useState } from 'react'
import Button from '../../components/Button.jsx'
import ErrorBanner from '../../components/ErrorBanner.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import { approveChunk, classifyChunk, documentChunks, generateChunks, submitChunkForReview } from '../../services/api.js'

const CHUNK_TYPES = [
  'heading', 'subheading', 'paragraph', 'definition', 'example', 'dictionary_entry',
  'grammar_rule', 'question', 'answer', 'instruction', 'response', 'translation_source',
  'translation_target', 'tanglish_text', 'tamil_text', 'english_text', 'table', 'table_row',
  'list', 'footnote', 'caption', 'reference', 'metadata', 'irrelevant', 'unknown',
]

export default function ChunkStep({ documentId, onComplete, toast }) {
  const [chunks, setChunks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)
  // "definition" (not "paragraph") by default -- SFT candidate generation
  // in the next step only produces candidates from a specific set of
  // chunk types (definition/dictionary_entry/example/grammar_rule as
  // standalone types, or question+answer/instruction+response pairs);
  // "paragraph" is never eligible, so defaulting to it would silently
  // leave AI Review Studio empty.
  const [chunkType, setChunkType] = useState('definition')
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const listing = await documentChunks(documentId)
      setChunks(listing.items ?? [])
    } catch (reason) {
      setError(reason.message)
    } finally {
      setLoading(false)
    }
  }, [documentId])

  useEffect(() => { load() }, [load])

  async function generate() {
    setGenerating(true)
    try {
      await generateChunks(documentId)
      const listing = await documentChunks(documentId)
      setChunks(listing.items ?? [])
      if ((listing.items ?? []).length === 0) {
        toast.error('No chunks were generated -- the document may need approved pages first.')
      }
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setGenerating(false)
    }
  }

  // Classify, submit for review, and approve a chunk in one real sequence
  // -- the same three real calls Chunk & Record Studio's own reviewer
  // flow uses, just combined so the wizard's Chunk step can unblock SFT
  // candidate generation (which only runs from approved chunks) without
  // duplicating the full editor experience.
  async function approve(chunkId) {
    setBusy(chunkId)
    try {
      await classifyChunk(chunkId, chunkType)
      await submitChunkForReview(chunkId)
      await approveChunk(chunkId)
      await load()
      onComplete({ toastMessage: 'Chunk classified and approved.' })
    } catch (reason) {
      toast.error(reason.message)
    } finally {
      setBusy('')
    }
  }

  if (loading) return <Skeleton lines={4} />
  if (error) return <ErrorBanner message={error} onRetry={load} />

  return (
    <section>
      <h3>Chunk</h3>
      <p className="notice">
        Generates draft semantic chunks from the document's approved pages, then approves at least one so
        AI Review Studio can generate SFT candidates from it. Splitting, merging, and the full review queue
        stay on Chunk &amp; Record Studio.
      </p>
      <Button variant="primary" loading={generating} onClick={generate}>Generate draft chunks from approved pages</Button>

      {chunks.length === 0 ? (
        <div className="notice">No chunks yet.</div>
      ) : (
        <>
          <label>
            Chunk type (applied when approving)
            <select value={chunkType} onChange={(event) => setChunkType(event.target.value)}>
              {CHUNK_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>
          <div className="data-list">
            {chunks.map((chunk) => (
              <article key={chunk.public_id}>
                <div>
                  <strong>#{chunk.reading_order} {chunk.chunk_type}</strong>
                  <span>{chunk.status}</span>
                </div>
                <small>{(chunk.active_revision?.text || '').slice(0, 120)}</small>
                <Button
                  size="sm" variant="success" loading={busy === chunk.public_id}
                  disabled={chunk.status === 'approved'}
                  onClick={() => approve(chunk.public_id)}
                >
                  {chunk.status === 'approved' ? 'Approved' : 'Classify & approve'}
                </Button>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
