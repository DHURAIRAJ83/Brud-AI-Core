import { useEffect, useState } from 'react'
import {
  approveChunk, approveStructuredRecord, archiveChunk, assignChunkParent, chunkClassificationSuggestions,
  chunkCoverageReport, chunkDetail, chunkDuplicateCheck, chunkHistory, chunkQualityCheck, chunkReviewHistory,
  classifyChunk, createManualChunk, createStructuredRecordFromChunks, createStructuredRecordRagCandidate,
  documentChunks, documents, editChunkText, excludeChunk, exportStructuredRecordToDataset,
  generateChunks, mergeChunk, moveChunkBoundary, rejectChunk, rejectStructuredRecord, reopenChunk, reorderChunks,
  requestChunkBoundaryCorrection, requestChunkClassificationCorrection, reviseStructuredRecord, restoreChunk,
  splitChunk, structuredRecordConflictCheck, structuredRecordDetail, structuredRecordHistory, structuredRecords,
  structuredRecordUsageCheck, submitChunkForReview, submitStructuredRecordForReview,
} from '../services/api.js'

const tabs = [
  'Overview', 'Documents', 'Chunk Editor', 'Structure', 'Record Builder',
  'Review Queue', 'Conflicts', 'Approved', 'History',
]

const CHUNK_TYPES = [
  'heading', 'subheading', 'paragraph', 'definition', 'example', 'dictionary_entry',
  'grammar_rule', 'question', 'answer', 'instruction', 'response', 'translation_source',
  'translation_target', 'tanglish_text', 'tamil_text', 'english_text', 'table', 'table_row',
  'list', 'footnote', 'caption', 'reference', 'metadata', 'irrelevant', 'unknown',
]

const RECORD_TYPES = [
  'plain_text', 'language_example', 'conversation', 'question_answer', 'instruction_response',
  'dictionary_entry', 'translation_pair', 'tanglish_normalization', 'knowledge_note', 'grammar_example', 'rag_chunk',
]

const FIELDS_BY_RECORD_TYPE = {
  plain_text: ['text'],
  language_example: ['text'],
  conversation: ['text'],
  question_answer: ['question', 'answer', 'context'],
  instruction_response: ['instruction', 'context', 'response'],
  dictionary_entry: ['word', 'part_of_speech', 'meanings_json', 'examples_json', 'synonyms_json', 'antonyms_json'],
  translation_pair: ['source_language', 'source_text', 'target_language', 'target_text'],
  tanglish_normalization: ['tanglish_text', 'normalized_tamil', 'english_meaning'],
  knowledge_note: ['title', 'text'],
  grammar_example: ['grammar_rule', 'correct_example', 'incorrect_example', 'correction'],
  rag_chunk: ['text'],
}

const FIELD_LABELS = {
  text: 'Text', question: 'Question', answer: 'Answer', context: 'Context', instruction: 'Instruction',
  response: 'Response', word: 'Word', part_of_speech: 'Part of speech', meanings_json: 'Meanings (JSON array)',
  examples_json: 'Examples (JSON array)', synonyms_json: 'Synonyms (JSON array)', antonyms_json: 'Antonyms (JSON array)',
  source_language: 'Source language', source_text: 'Source text', target_language: 'Target language',
  target_text: 'Target text', tanglish_text: 'Tanglish text', normalized_tamil: 'Normalized Tamil',
  english_meaning: 'English meaning', title: 'Title', grammar_rule: 'Grammar rule', correct_example: 'Correct example',
  incorrect_example: 'Incorrect example', correction: 'Correction',
}

export default function ChunkStudioPage() {
  const [tab, setTab] = useState('Overview')
  const [busy, setBusy] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState('')
  const [docItems, setDocItems] = useState([]), [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [chunks, setChunks] = useState([]), [selectedChunkId, setSelectedChunkId] = useState('')
  const [chunkDetailData, setChunkDetailData] = useState(null), [coverage, setCoverage] = useState(null)
  const [records, setRecords] = useState([]), [selectedRecordId, setSelectedRecordId] = useState('')
  const [recordDetailData, setRecordDetailData] = useState(null)

  useEffect(() => { refreshDocuments(); refreshRecords() }, [])

  async function refreshDocuments() {
    try { setDocItems((await documents()).items) } catch (reason) { setError(reason.message) }
  }

  async function refreshRecords(status) {
    try { setRecords((await structuredRecords(status ? `?status=${status}` : '')).items) } catch (reason) { setError(reason.message) }
  }

  async function refreshChunks(documentId) {
    try {
      const listing = await documentChunks(documentId)
      setChunks(listing.items)
    } catch (reason) { setError(reason.message) }
  }

  async function openDocument(documentId) {
    setSelectedDocumentId(documentId)
    setSelectedChunkId(''); setChunkDetailData(null); setCoverage(null)
    await refreshChunks(documentId)
  }

  async function openChunk(chunkId) {
    try {
      setSelectedChunkId(chunkId)
      setChunkDetailData(await chunkDetail(chunkId))
    } catch (reason) { setError(reason.message) }
  }

  async function action(label, callback) {
    setBusy(label); setError('')
    try {
      await callback()
      setNotice(`${label} completed.`)
      if (selectedDocumentId) await refreshChunks(selectedDocumentId)
      if (selectedChunkId) await openChunk(selectedChunkId)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function recordAction(label, callback) {
    setBusy(label); setError('')
    try {
      await callback()
      setNotice(`${label} completed.`)
      await refreshRecords()
      if (selectedRecordId) setRecordDetailData(await structuredRecordDetail(selectedRecordId))
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function loadCoverage() {
    try { setCoverage(await chunkCoverageReport(selectedDocumentId)) } catch (reason) { setError(reason.message) }
  }

  async function openRecord(id) {
    try { setSelectedRecordId(id); setRecordDetailData(await structuredRecordDetail(id)) } catch (reason) { setError(reason.message) }
  }

  return <section className="documents-workspace">
    <header className="section-heading">
      <div><h2>Chunk &amp; Record Studio</h2><p>Split, merge, classify, and structure reviewed document chunks into structured dataset candidates.</p></div>
      <button onClick={() => { refreshDocuments(); refreshRecords() }}>Refresh</button>
    </header>
    <div className="dataset-tabs">{tabs.map((value) => <button key={value} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}>{value}</button>)}</div>
    {notice && <div className="success-note" role="status">{notice}</div>}
    {error && <div className="form-error" role="alert">{error}</div>}

    {tab === 'Overview' && <OverviewTab docItems={docItems} chunks={chunks} records={records} />}

    {tab === 'Documents' && <DocumentsTab
      docItems={docItems} selectedDocumentId={selectedDocumentId} openDocument={openDocument}
      generate={() => action('Chunk generation', () => generateChunks(selectedDocumentId))}
      createManual={(body) => action('Manual chunk created', () => createManualChunk(selectedDocumentId, body))}
      busy={busy}
    />}

    {tab === 'Chunk Editor' && <ChunkEditorTab
      selectedDocumentId={selectedDocumentId} chunks={chunks} selectedChunkId={selectedChunkId} openChunk={openChunk}
      chunkDetailData={chunkDetailData} busy={busy}
      editText={(text, summary) => action('Text edit', () => editChunkText(selectedChunkId, { text, change_summary: summary }))}
      split={(splitAt) => action('Split', () => splitChunk(selectedChunkId, splitAt))}
      merge={(otherId) => action('Merge', () => mergeChunk(selectedChunkId, otherId))}
      moveBoundary={(body) => action('Boundary move', () => moveChunkBoundary(selectedChunkId, body))}
      classify={(chunkType) => action('Classification', () => classifyChunk(selectedChunkId, chunkType))}
      loadSuggestions={() => chunkClassificationSuggestions(selectedChunkId)}
      submitReview={() => action('Submitted for review', () => submitChunkForReview(selectedChunkId))}
      approve={() => action('Approve', () => approveChunk(selectedChunkId))}
      reject={() => action('Reject', () => rejectChunk(selectedChunkId))}
      exclude={() => action('Exclude', () => excludeChunk(selectedChunkId))}
      reopen={() => action('Reopen', () => reopenChunk(selectedChunkId))}
      requestBoundaryCorrection={() => action('Boundary correction requested', () => requestChunkBoundaryCorrection(selectedChunkId))}
      requestClassificationCorrection={() => action('Classification correction requested', () => requestChunkClassificationCorrection(selectedChunkId))}
      archive={() => action('Archive', () => archiveChunk(selectedChunkId))}
      restore={() => action('Restore', () => restoreChunk(selectedChunkId))}
      qualityCheck={() => chunkQualityCheck(selectedChunkId)}
      duplicateCheck={() => chunkDuplicateCheck(selectedChunkId)}
    />}

    {tab === 'Structure' && <StructureTab
      chunks={chunks} selectedDocumentId={selectedDocumentId} busy={busy}
      assignParent={(chunkId, parentId) => action('Parent assigned', () => assignChunkParent(chunkId, parentId))}
      reorder={(ordering) => action('Reordered', () => reorderChunks(selectedDocumentId, ordering))}
    />}

    {tab === 'Record Builder' && <RecordBuilderTab
      chunks={chunks} busy={busy}
      create={(recordType, chunkIds, fields) => recordAction('Structured record created', () => createStructuredRecordFromChunks({ record_type: recordType, chunk_public_ids: chunkIds, fields }))}
    />}

    {tab === 'Review Queue' && <ReviewQueueTab
      chunks={chunks} selectedDocumentId={selectedDocumentId} busy={busy}
      approve={(id) => action('Approve', () => approveChunk(id))}
      reject={(id) => action('Reject', () => rejectChunk(id))}
      openChunk={openChunk}
    />}

    {tab === 'Conflicts' && <ConflictsTab
      records={records} busy={busy}
      conflictCheck={structuredRecordConflictCheck}
      loadCoverage={loadCoverage} coverage={coverage} selectedDocumentId={selectedDocumentId}
    />}

    {tab === 'Approved' && <ApprovedTab
      chunks={chunks} records={records} loadApprovedRecords={() => refreshRecords('approved')}
      busy={busy}
      usageCheck={structuredRecordUsageCheck}
      exportDataset={(id) => recordAction('Exported to dataset', () => exportStructuredRecordToDataset(id))}
      ragHandoff={(id) => recordAction('RAG handoff', () => createStructuredRecordRagCandidate(id))}
    />}

    {tab === 'History' && <HistoryTab
      selectedChunkId={selectedChunkId} selectedRecordId={selectedRecordId}
      records={records} openRecord={openRecord} recordDetailData={recordDetailData}
      loadChunkHistory={() => chunkHistory(selectedChunkId)}
      loadChunkReviewHistory={() => chunkReviewHistory(selectedChunkId)}
      loadRecordHistory={() => structuredRecordHistory(selectedRecordId)}
      submitRecordReview={() => recordAction('Submitted for review', () => submitStructuredRecordForReview(selectedRecordId))}
      approveRecord={() => recordAction('Approve', () => approveStructuredRecord(selectedRecordId))}
      rejectRecord={() => recordAction('Reject', () => rejectStructuredRecord(selectedRecordId))}
      reviseRecord={(fields, summary) => recordAction('Revised', () => reviseStructuredRecord(selectedRecordId, { fields, change_summary: summary }))}
      busy={busy}
    />}
  </section>
}

function OverviewTab({ docItems, chunks, records }) {
  const chunkStatusCounts = Object.fromEntries(
    ['draft', 'needs_review', 'needs_structure_review', 'needs_content_review', 'approved', 'rejected', 'excluded', 'archived']
      .map((status) => [status, chunks.filter((c) => c.status === status).length]),
  )
  const recordStatusCounts = Object.fromEntries(
    ['draft', 'needs_review', 'approved', 'rejected', 'archived'].map((status) => [status, records.filter((r) => r.status === status).length]),
  )
  return <>
    <h3>Documents</h3>
    <section className="metric-grid">
      <article className="status-card"><span>Total documents</span><strong>{docItems.length}</strong></article>
    </section>
    <h3>Chunks (selected document)</h3>
    <section className="metric-grid">
      {Object.entries(chunkStatusCounts).map(([key, value]) => <article className="status-card" key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{value}</strong></article>)}
    </section>
    <h3>Structured record candidates</h3>
    <section className="metric-grid">
      {Object.entries(recordStatusCounts).map(([key, value]) => <article className="status-card" key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{value}</strong></article>)}
    </section>
  </>
}

function DocumentsTab({ docItems, selectedDocumentId, openDocument, generate, createManual, busy }) {
  const [manualText, setManualText] = useState(''), [manualPage, setManualPage] = useState(1), [manualType, setManualType] = useState('paragraph')
  return <>
    <h3>Select a document</h3>
    <p>Only documents with approved pages and a linked source can generate chunks.</p>
    <div className="document-list">
      {docItems.map((item) => (
        <button key={item.public_id} className={item.public_id === selectedDocumentId ? 'active' : ''} onClick={() => openDocument(item.public_id)}>
          <strong>{item.original_filename}</strong><span>{item.page_count} pages · {item.status}</span>
        </button>
      ))}
    </div>
    {selectedDocumentId && (
      <>
        <div className="panel-controls">
          <button disabled={Boolean(busy)} onClick={generate}>Generate draft chunks from approved pages</button>
        </div>
        <h4>Create a manual chunk</h4>
        <div className="panel-controls">
          <label>Page number<input type="number" min="1" value={manualPage} onChange={(e) => setManualPage(e.target.value)} /></label>
          <label>Chunk type
            <select value={manualType} onChange={(e) => setManualType(e.target.value)}>
              {CHUNK_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
        </div>
        <label>Text<textarea value={manualText} onChange={(e) => setManualText(e.target.value)} rows="4" /></label>
        <button
          disabled={Boolean(busy) || !manualText.trim()}
          onClick={() => createManual({ text: manualText, chunk_type: manualType, page_number: Number(manualPage), language: 'unknown' })}
        >Create manual chunk</button>
      </>
    )}
  </>
}

function ChunkEditorTab({
  selectedDocumentId, chunks, selectedChunkId, openChunk, chunkDetailData, busy,
  editText, split, merge, moveBoundary, classify, loadSuggestions, submitReview, approve, reject, exclude, reopen,
  requestBoundaryCorrection, requestClassificationCorrection, archive, restore, qualityCheck, duplicateCheck,
}) {
  const [text, setText] = useState(''), [summary, setSummary] = useState('')
  const [splitAt, setSplitAt] = useState(''), [mergeTarget, setMergeTarget] = useState('')
  const [neighborId, setNeighborId] = useState(''), [edge, setEdge] = useState('end'), [newOffset, setNewOffset] = useState('')
  const [suggestions, setSuggestions] = useState([]), [quality, setQuality] = useState(null), [duplicate, setDuplicate] = useState(null)
  useEffect(() => { setText(chunkDetailData?.active_revision?.text || ''); setSummary('') }, [chunkDetailData])
  if (!selectedDocumentId) return <div className="notice">Select a document from the Documents tab first.</div>
  return <div className="page-review-split">
    <div className="page-image-pane">
      <h4>Chunks in reading order</h4>
      <div className="candidate-list">
        {chunks.map((chunk) => (
          <article key={chunk.public_id} className={chunk.public_id === selectedChunkId ? 'active' : ''}>
            <header><strong>#{chunk.reading_order} {chunk.chunk_type}</strong><span>{chunk.status}</span></header>
            <p>{(chunk.active_revision?.text || '').slice(0, 120)}</p>
            <button type="button" onClick={() => openChunk(chunk.public_id)}>Open</button>
          </article>
        ))}
      </div>
    </div>
    <div className="page-text-pane">
      {!chunkDetailData ? <div className="notice">Select a chunk to edit.</div> : (
        <>
          <h4>Chunk {chunkDetailData.chunk_code} <span className="review-status-badge">{chunkDetailData.status}</span></h4>
          <label>Text<textarea value={text} onChange={(e) => setText(e.target.value)} rows="8" /></label>
          <label>Change summary<input value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
          <div className="review-actions">
            <button disabled={Boolean(busy) || text === chunkDetailData.active_revision?.text} onClick={() => editText(text, summary)}>Save text correction</button>
          </div>

          <h4>Classification</h4>
          <div className="panel-controls">
            <select value={chunkDetailData.chunk_type} onChange={(e) => classify(e.target.value)}>
              {CHUNK_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <button type="button" onClick={async () => setSuggestions((await loadSuggestions()).items)}>Load suggestions</button>
          </div>
          {suggestions.length > 0 && <ul>{suggestions.map((s, i) => <li key={i}>{s.suggested_type} -- {s.reason} (confidence {s.confidence})</li>)}</ul>}

          <h4>Boundary editing</h4>
          <div className="panel-controls">
            <label>Split at offset<input type="number" value={splitAt} onChange={(e) => setSplitAt(e.target.value)} /></label>
            <button type="button" disabled={Boolean(busy) || !splitAt} onClick={() => split(Number(splitAt))}>Split</button>
          </div>
          <div className="panel-controls">
            <label>Merge with chunk (public id)<input value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)} /></label>
            <button type="button" disabled={Boolean(busy) || !mergeTarget} onClick={() => merge(mergeTarget)}>Merge</button>
          </div>
          <div className="panel-controls">
            <label>Neighbor chunk (public id)<input value={neighborId} onChange={(e) => setNeighborId(e.target.value)} /></label>
            <label>Edge
              <select value={edge} onChange={(e) => setEdge(e.target.value)}>
                <option value="start">start</option>
                <option value="end">end</option>
              </select>
            </label>
            <label>New offset<input type="number" value={newOffset} onChange={(e) => setNewOffset(e.target.value)} /></label>
            <button
              type="button"
              disabled={Boolean(busy) || !neighborId || newOffset === ''}
              onClick={() => moveBoundary({ neighbor_chunk_public_id: neighborId, edge, new_offset: Number(newOffset) })}
            >Move boundary</button>
          </div>

          <h4>Review decision</h4>
          <div className="review-actions">
            <button disabled={Boolean(busy)} onClick={submitReview}>Submit for review</button>
            <button disabled={Boolean(busy)} onClick={approve}>Approve</button>
            <button disabled={Boolean(busy)} onClick={reject}>Reject</button>
            <button disabled={Boolean(busy)} onClick={exclude}>Exclude</button>
            <button disabled={Boolean(busy)} onClick={reopen}>Reopen</button>
            <button disabled={Boolean(busy)} onClick={requestBoundaryCorrection}>Request boundary correction</button>
            <button disabled={Boolean(busy)} onClick={requestClassificationCorrection}>Request classification correction</button>
            <button disabled={Boolean(busy)} onClick={archive}>Archive</button>
            <button disabled={Boolean(busy)} onClick={restore}>Restore</button>
          </div>

          <h4>Quality &amp; duplicates</h4>
          <div className="panel-controls">
            <button type="button" onClick={async () => setQuality(await qualityCheck())}>Run quality check</button>
            <button type="button" onClick={async () => setDuplicate(await duplicateCheck())}>Run duplicate check</button>
          </div>
          {quality && <p>Score {quality.overall_score} · blocking: {quality.blocking_issues.join(', ') || 'none'}</p>}
          {duplicate && <p>Exact duplicate: {duplicate.exact_duplicate_chunk_public_id || 'none'}</p>}
        </>
      )}
    </div>
  </div>
}

function StructureTab({ chunks, selectedDocumentId, busy, assignParent, reorder }) {
  const [order, setOrder] = useState(chunks.map((c) => c.public_id))
  useEffect(() => { setOrder(chunks.map((c) => c.public_id)) }, [chunks])
  function move(index, direction) {
    const next = [...order]
    const target = index + direction
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    setOrder(next)
  }
  if (!selectedDocumentId) return <div className="notice">Select a document from the Documents tab first.</div>
  return <>
    <h3>Reading order</h3>
    <ol>
      {order.map((chunkId, index) => {
        const chunk = chunks.find((c) => c.public_id === chunkId)
        return <li key={chunkId}>
          {chunk?.chunk_type} -- {(chunk?.active_revision?.text || '').slice(0, 60)}
          <button type="button" onClick={() => move(index, -1)}>Up</button>
          <button type="button" onClick={() => move(index, 1)}>Down</button>
          <label>Parent chunk id<input placeholder="parent chunk public id" onBlur={(e) => e.target.value && assignParent(chunkId, e.target.value)} /></label>
        </li>
      })}
    </ol>
    <button disabled={Boolean(busy)} onClick={() => reorder(order)}>Save reading order</button>
  </>
}

function RecordBuilderTab({ chunks, busy, create }) {
  const [recordType, setRecordType] = useState('plain_text')
  const [selectedChunks, setSelectedChunks] = useState([])
  const [fields, setFields] = useState({})
  function toggleChunk(id) {
    setSelectedChunks((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]))
  }
  return <>
    <h3>Structured record candidate</h3>
    <label>Record type
      <select value={recordType} onChange={(e) => { setRecordType(e.target.value); setFields({}) }}>
        {RECORD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
    </label>
    <h4>Select source chunks (must be reviewed)</h4>
    <div className="candidate-list">
      {chunks.map((chunk) => (
        <label key={chunk.public_id}>
          <input type="checkbox" checked={selectedChunks.includes(chunk.public_id)} onChange={() => toggleChunk(chunk.public_id)} />
          {chunk.chunk_type} ({chunk.status}) -- {(chunk.active_revision?.text || '').slice(0, 80)}
        </label>
      ))}
    </div>
    <h4>Fields</h4>
    {(FIELDS_BY_RECORD_TYPE[recordType] || []).map((field) => (
      <label key={field}>{FIELD_LABELS[field] || field}
        <textarea value={fields[field] || ''} onChange={(e) => setFields({ ...fields, [field]: e.target.value })} />
      </label>
    ))}
    <button disabled={Boolean(busy) || !selectedChunks.length} onClick={() => create(recordType, selectedChunks, fields)}>Create structured record candidate</button>
  </>
}

function ReviewQueueTab({ chunks, selectedDocumentId, busy, approve, reject, openChunk }) {
  const needsReview = chunks.filter((c) => ['needs_review', 'needs_structure_review', 'needs_content_review'].includes(c.status))
  if (!selectedDocumentId) return <div className="notice">Select a document from the Documents tab first.</div>
  return <>
    <h3>Chunks needing review</h3>
    {!needsReview.length ? <div className="notice">Nothing in the review queue for this document.</div> : (
      <div className="candidate-list">
        {needsReview.map((chunk) => (
          <article key={chunk.public_id}>
            <header><strong>{chunk.chunk_type}</strong><span>{chunk.status}</span></header>
            <p>{(chunk.active_revision?.text || '').slice(0, 150)}</p>
            <div className="review-actions">
              <button disabled={Boolean(busy)} onClick={() => openChunk(chunk.public_id)}>Open in Chunk Editor</button>
              <button disabled={Boolean(busy)} onClick={() => approve(chunk.public_id)}>Approve</button>
              <button disabled={Boolean(busy)} onClick={() => reject(chunk.public_id)}>Reject</button>
            </div>
          </article>
        ))}
      </div>
    )}
  </>
}

function ConflictsTab({ records, busy, conflictCheck, loadCoverage, coverage, selectedDocumentId }) {
  const [results, setResults] = useState({})
  async function check(id) {
    const result = await conflictCheck(id)
    setResults((prev) => ({ ...prev, [id]: result }))
  }
  return <>
    <h3>Text coverage conflicts</h3>
    {selectedDocumentId
      ? <button disabled={Boolean(busy)} onClick={loadCoverage}>Check page coverage</button>
      : <div className="notice">Select a document from the Documents tab to check coverage.</div>}
    {coverage && Object.entries(coverage).map(([page, report]) => (
      <p key={page}>Page {page}: assigned {Math.round(report.assigned_ratio * 100)}%, unassigned {Math.round(report.unassigned_ratio * 100)}%, overlaps {report.overlap_count}</p>
    ))}
    <h3>Structured record conflicts</h3>
    <div className="candidate-list">
      {records.map((record) => (
        <article key={record.public_id}>
          <header><strong>{record.candidate_code}</strong><span>{record.record_type} · {record.status}</span></header>
          <button type="button" onClick={() => check(record.public_id)}>Run conflict check</button>
          {results[record.public_id] && (
            <p>{results[record.public_id].conflict ? `${results[record.public_id].conflict.type} with ${results[record.public_id].conflict.candidate_public_id}` : 'No conflict detected.'}</p>
          )}
        </article>
      ))}
    </div>
  </>
}

function ApprovedTab({ chunks, records, loadApprovedRecords, busy, usageCheck, exportDataset, ragHandoff }) {
  const [decisions, setDecisions] = useState({})
  useEffect(() => { loadApprovedRecords() }, [])
  const approvedChunks = chunks.filter((c) => c.status === 'approved')
  const approvedRecords = records.filter((r) => r.status === 'approved')
  async function check(id, use) {
    const decision = await usageCheck(id, use)
    setDecisions((prev) => ({ ...prev, [id]: decision }))
  }
  return <>
    <h3>Approved chunks</h3>
    <p>{approvedChunks.length} approved chunk(s) in the currently selected document.</p>
    <h3>Approved structured records</h3>
    <div className="candidate-list">
      {approvedRecords.map((record) => (
        <article key={record.public_id}>
          <header><strong>{record.candidate_code}</strong><span>{record.record_type}</span></header>
          <div className="panel-controls">
            {['rag', 'training', 'evaluation', 'commercial', 'public_export', 'redistribution'].map((use) => (
              <button key={use} type="button" onClick={() => check(record.public_id, use)}>{use}?</button>
            ))}
          </div>
          {decisions[record.public_id] && <p>{decisions[record.public_id].allowed ? 'Allowed' : `Blocked: ${decisions[record.public_id].blocking_reasons.join(', ')}`}</p>}
          <div className="review-actions">
            <button disabled={Boolean(busy)} onClick={() => exportDataset(record.public_id)}>Export to Existing Dataset Record</button>
            <button disabled={Boolean(busy)} onClick={() => ragHandoff(record.public_id)}>Mark ready for RAG</button>
          </div>
        </article>
      ))}
    </div>
  </>
}

function HistoryTab({
  selectedChunkId, selectedRecordId, records, openRecord, recordDetailData,
  loadChunkHistory, loadChunkReviewHistory, loadRecordHistory,
  submitRecordReview, approveRecord, rejectRecord, reviseRecord, busy,
}) {
  const [chunkEvents, setChunkEvents] = useState(null), [chunkReviews, setChunkReviews] = useState(null)
  const [recordHistory, setRecordHistory] = useState(null)
  const [reviseFields, setReviseFields] = useState({}), [reviseSummary, setReviseSummary] = useState('')
  return <>
    <h3>Chunk history</h3>
    {!selectedChunkId ? <div className="notice">Select a chunk in the Chunk Editor tab first.</div> : (
      <>
        <button type="button" onClick={async () => setChunkEvents(await loadChunkHistory())}>Load chunk history</button>
        <button type="button" onClick={async () => setChunkReviews(await loadChunkReviewHistory())}>Load review history</button>
        {chunkEvents && <ol>{chunkEvents.events.map((e) => <li key={e.public_id}>{e.event_type} by {e.performed_by_admin_public_id} at {e.created_at}</li>)}</ol>}
        {chunkReviews && <ol>{chunkReviews.items.map((r) => <li key={r.public_id}>{r.action} -&gt; {r.status_after} by {r.performed_by_admin_public_id}</li>)}</ol>}
      </>
    )}
    <h3>Structured record history</h3>
    <label>Record<select value={selectedRecordId} onChange={(e) => openRecord(e.target.value)}>
      <option value="">Choose a record</option>
      {records.map((r) => <option key={r.public_id} value={r.public_id}>{r.candidate_code} -- {r.record_type} ({r.status})</option>)}
    </select></label>
    {recordDetailData && (
      <div className="history-panel">
        <p>Status: {recordDetailData.status}</p>
        <div className="review-actions">
          <button disabled={Boolean(busy)} onClick={submitRecordReview}>Submit for review</button>
          <button disabled={Boolean(busy)} onClick={approveRecord}>Approve</button>
          <button disabled={Boolean(busy)} onClick={rejectRecord}>Reject</button>
        </div>
        <h4>Create a new revision</h4>
        {(FIELDS_BY_RECORD_TYPE[recordDetailData.record_type] || []).map((field) => (
          <label key={field}>{FIELD_LABELS[field] || field}
            <textarea defaultValue={recordDetailData.active_revision?.[field] || ''} onChange={(e) => setReviseFields({ ...reviseFields, [field]: e.target.value })} />
          </label>
        ))}
        <label>Change summary<input value={reviseSummary} onChange={(e) => setReviseSummary(e.target.value)} /></label>
        <button disabled={Boolean(busy)} onClick={() => reviseRecord(reviseFields, reviseSummary)}>Save new revision</button>
        <button type="button" onClick={async () => setRecordHistory(await loadRecordHistory())}>Load revision/review history</button>
        {recordHistory && (
          <>
            <h4>Revisions</h4>
            <ol>{recordHistory.revisions.map((r) => <li key={r.public_id}>#{r.revision_number} -- {r.change_summary}</li>)}</ol>
            <h4>Reviews</h4>
            <ol>{recordHistory.reviews.map((r) => <li key={r.public_id}>{r.review_status} by {r.reviewer_admin_public_id} -- {r.comments}</li>)}</ol>
          </>
        )}
      </div>
    )}
  </>
}
