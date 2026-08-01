import { useEffect, useState } from 'react'
import {
  approveManualDataRecord, archiveManualDataRecord, createManualDataDatasetCandidate,
  createManualDataRecord, createManualDataRevision, manualDataDuplicateCheck, manualDataHistory,
  manualDataQualityCheck, manualDataRecord, manualDataRecords, manualDataReviews, manualDataSummary,
  manualDataUsageSummary, manualDataVerifications, rejectManualDataRecord,
  requestManualDataCorrection, requestManualDataDomainReview, requestManualDataSourceVerification,
  restoreManualDataRecord, submitManualDataForReview, submitManualDataReview,
  submitManualDataVerification,
} from '../services/api.js'

const TABS = ['Overview', 'Create Data', 'Records', 'Review Queue', 'Verification Queue', 'Approved', 'Rejected', 'History']

const RECORD_TYPES = [
  'plain_text', 'language_example', 'conversation', 'question_answer', 'instruction_response',
  'dictionary_entry', 'translation_pair', 'tanglish_normalization', 'knowledge_note',
  'grammar_example', 'evaluation_case_draft',
]

const RECORD_STATUSES = [
  'draft', 'needs_review', 'needs_source_verification', 'needs_domain_review', 'approved',
  'rejected', 'archived',
]

const LANGUAGE_CODES = ['ta', 'en', 'tgl', 'mixed', 'unknown']
const FACT_DEPENDENCIES = ['none', 'low', 'medium', 'high']
const KNOWLEDGE_RISKS = ['language_only', 'general', 'domain_specific', 'high_risk', 'time_sensitive']
const CREATION_METHODS = ['human_created', 'admin_created', 'teacher_created', 'ai_assisted', 'imported_manual', 'derived_manual']
const TARGET_USES = ['rag', 'training', 'evaluation', 'commercial', 'public_export', 'redistribution']
const REVIEW_TYPES = ['language', 'translation', 'factual', 'domain', 'general']
const VERIFICATION_TYPES = ['source_verification', 'factual_verification', 'domain_verification', 'time_sensitivity_revalidation']

const CONTENT_FIELDS_BY_TYPE = {
  plain_text: ['tamil_text', 'english_text', 'tanglish_text'],
  language_example: ['tamil_text', 'english_text', 'tanglish_text'],
  grammar_example: ['tamil_text', 'english_text', 'tanglish_text'],
  conversation: ['turns'],
  question_answer: ['question_text', 'answer_text'],
  instruction_response: ['instruction_text', 'response_text'],
  dictionary_entry: ['word', 'part_of_speech', 'meanings', 'examples', 'english_text'],
  translation_pair: ['input_text', 'output_text'],
  tanglish_normalization: ['tanglish_text', 'tamil_text', 'english_text'],
  knowledge_note: ['title', 'input_text'],
  evaluation_case_draft: ['question_text', 'answer_text'],
}

const FIELD_LABELS = {
  tamil_text: 'Tamil text', english_text: 'English text', tanglish_text: 'Tanglish text',
  question_text: 'Question', answer_text: 'Answer', instruction_text: 'Instruction',
  response_text: 'Response', word: 'Word', part_of_speech: 'Part of speech',
  meanings: 'Meanings (one per line)', examples: 'Examples (one per line)',
  input_text: 'Input / source text', output_text: 'Output / target text', title: 'Title',
}

const emptyContent = {
  title: '', input_text: '', output_text: '', instruction_text: '', response_text: '',
  question_text: '', answer_text: '', tamil_text: '', english_text: '', tanglish_text: '',
  word: '', part_of_speech: '', meanings: '', examples: '', turns: [],
}

const emptyRecordForm = {
  record_type: 'plain_text', primary_language: 'ta', input_language: '', output_language: '',
  domain: '', topic: '', difficulty: '', audience: '', style: '', fact_dependency: 'none',
  knowledge_risk: 'language_only', creation_method: 'admin_created', requested_uses: [],
}

function buildContentPayload(content) {
  return {
    ...content,
    meanings: content.meanings ? content.meanings.split('\n').map((s) => s.trim()).filter(Boolean) : [],
    examples: content.examples ? content.examples.split('\n').map((s) => s.trim()).filter(Boolean) : [],
  }
}

const CONTENT_FIELD_KEYS = [
  'title', 'input_text', 'output_text', 'instruction_text', 'response_text',
  'question_text', 'answer_text', 'tamil_text', 'english_text', 'tanglish_text',
  'word', 'part_of_speech',
]

function contentFromRevision(revision) {
  if (!revision) return emptyContent
  const picked = {}
  for (const key of CONTENT_FIELD_KEYS) picked[key] = revision[key] || ''
  return {
    ...emptyContent,
    ...picked,
    meanings: (revision.meanings || []).join('\n'),
    examples: (revision.examples || []).join('\n'),
    turns: (revision.metadata || {}).turns || [],
  }
}

function ContentFields({ recordType, content, setContent, idPrefix }) {
  function addTurn() {
    setContent({ ...content, turns: [...content.turns, { role: 'user', language: '', content: '' }] })
  }
  function updateTurn(index, patch) {
    setContent({ ...content, turns: content.turns.map((t, i) => (i === index ? { ...t, ...patch } : t)) })
  }
  function removeTurn(index) {
    setContent({ ...content, turns: content.turns.filter((_, i) => i !== index) })
  }
  return (
    <>
      {(CONTENT_FIELDS_BY_TYPE[recordType] || []).map((field) => {
        if (field === 'turns') {
          return (
            <div className="turn-list" key={`${idPrefix}-turns`}>
              {content.turns.map((turn, index) => (
                <div className="turn-row" key={index}>
                  <select value={turn.role} onChange={(e) => updateTurn(index, { role: e.target.value })}>
                    <option value="user">user</option>
                    <option value="assistant">assistant</option>
                    <option value="system">system</option>
                  </select>
                  <input value={turn.content} onChange={(e) => updateTurn(index, { content: e.target.value })} placeholder="Turn content" />
                  <button type="button" onClick={() => removeTurn(index)}>Remove</button>
                </div>
              ))}
              <button type="button" onClick={addTurn}>Add turn</button>
            </div>
          )
        }
        return (
          <label key={`${idPrefix}-${field}`}>
            {FIELD_LABELS[field] || field}
            <textarea value={content[field] || ''} onChange={(e) => setContent({ ...content, [field]: e.target.value })} />
          </label>
        )
      })}
    </>
  )
}

function RecordSelector({ items, selectedId, onSelect }) {
  return (
    <div className="panel-controls">
      <label>Record
        <select value={selectedId} onChange={(e) => onSelect(e.target.value)}>
          <option value="">Choose a record</option>
          {items.map((item) => <option key={item.public_id} value={item.public_id}>{item.record_code} -- {item.record_type} ({item.status})</option>)}
        </select>
      </label>
    </div>
  )
}

function ReviewWorkspace({
  selectedId, detail, quality, duplicate, reviews, verifications,
  reviewForm, setReviewForm, verificationForm, setVerificationForm,
  approveUses, setApproveUses, rejectReason, setRejectReason,
  revisionContent, setRevisionContent, revisionSummary, setRevisionSummary,
  onSubmitForReview, onRequestCorrection, onRequestSourceVerification, onRequestDomainReview,
  onRunQualityCheck, onSubmitReview, onSubmitVerification, onApprove, onReject, onArchive,
  onCreateRevision,
}) {
  if (!selectedId || !detail) return null
  return (
    <div className="history-panel">
      <h3>Record: {detail.record_code} ({detail.status})</h3>
      <p>Type: {detail.record_type} · Source: {detail.source_title} ({detail.source_public_id})</p>
      {detail.active_revision && <pre>{JSON.stringify(detail.active_revision, null, 2)}</pre>}

      <div className="panel-controls">
        <button type="button" onClick={onSubmitForReview}>Submit for review</button>
        <button type="button" onClick={onRequestCorrection}>Request correction</button>
        <button type="button" onClick={onRequestSourceVerification}>Request source verification</button>
        <button type="button" onClick={onRequestDomainReview}>Request domain review</button>
        <button type="button" onClick={onRunQualityCheck}>Run quality &amp; duplicate check</button>
      </div>

      {quality && (
        <div>
          <h3>Quality assessment</h3>
          <p>Overall score: {quality.overall_score}</p>
          {quality.blocking_issues.length > 0 && (
            <ul className="blocking-issues">{quality.blocking_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
          )}
          {duplicate && <p>Duplicate status: {duplicate.duplicate_status}</p>}
        </div>
      )}

      <h3>Submit a review</h3>
      <div className="panel-controls">
        <label>Review type
          <select value={reviewForm.review_type} onChange={(e) => setReviewForm({ ...reviewForm, review_type: e.target.value })}>
            {REVIEW_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>Decision
          <select value={reviewForm.review_status} onChange={(e) => setReviewForm({ ...reviewForm, review_status: e.target.value })}>
            <option value="approved">approved</option>
            <option value="changes_requested">changes_requested</option>
            <option value="rejected">rejected</option>
          </select>
        </label>
        <label>Comments<input value={reviewForm.comments} onChange={(e) => setReviewForm({ ...reviewForm, comments: e.target.value })} /></label>
        <button type="button" onClick={onSubmitReview}>Submit review</button>
      </div>
      {reviews.length > 0 && (
        <ul>{reviews.map((r) => <li key={r.public_id}>{r.review_type}: {r.review_status} -- {r.comments}</li>)}</ul>
      )}

      <h3>Source verification</h3>
      <div className="panel-controls">
        <label>Verification type
          <select value={verificationForm.verification_type} onChange={(e) => setVerificationForm({ ...verificationForm, verification_type: e.target.value })}>
            {VERIFICATION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>Status
          <select value={verificationForm.verification_status} onChange={(e) => setVerificationForm({ ...verificationForm, verification_status: e.target.value })}>
            <option value="pending">pending</option>
            <option value="verified">verified</option>
            <option value="rejected">rejected</option>
            <option value="expired">expired</option>
          </select>
        </label>
        <label>Supporting source public id (optional)
          <input value={verificationForm.source_public_id} onChange={(e) => setVerificationForm({ ...verificationForm, source_public_id: e.target.value })} />
        </label>
        <label>Notes<input value={verificationForm.verification_notes} onChange={(e) => setVerificationForm({ ...verificationForm, verification_notes: e.target.value })} /></label>
        <button type="button" onClick={onSubmitVerification}>Record verification</button>
      </div>
      {verifications.length > 0 && (
        <ul>{verifications.map((v) => <li key={v.public_id}>{v.verification_type}: {v.verification_status}</li>)}</ul>
      )}

      <h3>Approve for specific uses</h3>
      <div className="use-checkbox-grid">
        {TARGET_USES.map((use) => (
          <label className="rights-checkbox" key={use}>
            <input
              type="checkbox"
              checked={approveUses.includes(use)}
              onChange={(e) => setApproveUses(e.target.checked ? [...approveUses, use] : approveUses.filter((u) => u !== use))}
            /> {use}
          </label>
        ))}
      </div>
      <div className="review-actions">
        <button type="button" onClick={onApprove}>Approve for selected uses</button>
        <label>Rejection reason<input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} /></label>
        <button type="button" onClick={onReject}>Reject</button>
        <button type="button" onClick={onArchive}>Archive</button>
      </div>
      {detail.blocked_uses && Object.keys(detail.blocked_uses).length > 0 && (
        <p>Blocked uses: {Object.entries(detail.blocked_uses).map(([use, code]) => `${use}: ${code}`).join(', ')}</p>
      )}

      <h3>Edit content (creates a new revision -- the current revision is preserved)</h3>
      <div className="inline-form">
        <ContentFields recordType={detail.record_type} content={revisionContent} setContent={setRevisionContent} idPrefix="revision" />
        <label>Change summary<input value={revisionSummary} onChange={(e) => setRevisionSummary(e.target.value)} /></label>
        <button type="button" className="rights-save-button" onClick={onCreateRevision}>Create new revision</button>
      </div>
    </div>
  )
}

export default function ManualDataPage() {
  const [tab, setTab] = useState('Overview')
  const [summary, setSummary] = useState(null)
  const [records, setRecords] = useState({ items: [], total: 0 })
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [search, setSearch] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const [recordForm, setRecordForm] = useState(emptyRecordForm)
  const [sourceMode, setSourceMode] = useState('existing')
  const [sourcePublicId, setSourcePublicId] = useState('')
  const [newSourceForm, setNewSourceForm] = useState({ source_code: '', title: '', source_type: 'human_created' })
  const [content, setContent] = useState(emptyContent)

  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState(null)
  const [quality, setQuality] = useState(null)
  const [duplicate, setDuplicate] = useState(null)
  const [reviews, setReviews] = useState([])
  const [verifications, setVerifications] = useState([])
  const [historyData, setHistoryData] = useState(null)
  const [usageSummary, setUsageSummary] = useState(null)

  const [reviewForm, setReviewForm] = useState({ review_type: 'language', review_status: 'approved', comments: '' })
  const [verificationForm, setVerificationForm] = useState({ verification_type: 'factual_verification', verification_status: 'verified', source_public_id: '', verification_notes: '' })
  const [rejectReason, setRejectReason] = useState('')
  const [approveUses, setApproveUses] = useState([])
  const [revisionContent, setRevisionContent] = useState(emptyContent)
  const [revisionSummary, setRevisionSummary] = useState('')

  async function loadSummary() {
    try { setSummary(await manualDataSummary()) } catch (reason) { setError(reason.message) }
  }

  async function loadRecords() {
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.set('status', statusFilter)
      if (typeFilter) params.set('record_type', typeFilter)
      if (search) params.set('search', search)
      params.set('page_size', '100')
      setRecords(await manualDataRecords(`?${params.toString()}`))
    } catch (reason) { setError(reason.message) }
  }

  useEffect(() => { loadSummary(); loadRecords() }, [])
  useEffect(() => { loadRecords() }, [statusFilter, typeFilter, search])

  async function openRecord(publicId) {
    setSelectedId(publicId)
    setQuality(null); setDuplicate(null); setHistoryData(null); setUsageSummary(null)
    try {
      const record = await manualDataRecord(publicId)
      setDetail(record)
      setRevisionContent(contentFromRevision(record.active_revision))
      setReviews((await manualDataReviews(publicId)).items)
      setVerifications((await manualDataVerifications(publicId)).items)
    } catch (reason) { setError(reason.message) }
  }

  async function createNewRevision() {
    if (!selectedId) return setError('Choose a record first.')
    setError('')
    try {
      await createManualDataRevision(selectedId, {
        content: buildContentPayload(revisionContent),
        change_summary: revisionSummary,
      })
      setNotice('New revision created; the previous approved revision is preserved.')
      setRevisionSummary('')
      await refreshAfterAction(selectedId)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshAfterAction(publicId) {
    await Promise.all([loadRecords(), loadSummary()])
    if (publicId) await openRecord(publicId)
  }

  async function createRecord(event) {
    event.preventDefault()
    setNotice(''); setError('')
    const payload = {
      ...recordForm,
      input_language: recordForm.input_language || null,
      output_language: recordForm.output_language || null,
      content: buildContentPayload(content),
    }
    if (sourceMode === 'existing') payload.source_public_id = sourcePublicId
    else payload.new_source = newSourceForm
    try {
      const created = await createManualDataRecord(payload)
      setNotice(`Draft record ${created.record_code} created.`)
      setContent(emptyContent)
      setRecordForm(emptyRecordForm)
      setSourceMode('existing')
      setSourcePublicId('')
      setNewSourceForm({ source_code: '', title: '', source_type: 'human_created' })
      await Promise.all([loadRecords(), loadSummary()])
    } catch (reason) { setError(reason.message) }
  }

  async function runAction(fn, ...args) {
    setError('')
    try {
      await fn(...args)
      setNotice('Action recorded.')
      await refreshAfterAction(selectedId)
    } catch (reason) { setError(reason.message) }
  }

  async function submitReview() {
    if (!selectedId) return setError('Choose a record first.')
    await runAction(submitManualDataReview, selectedId, reviewForm)
  }

  async function submitVerification() {
    if (!selectedId) return setError('Choose a record first.')
    const payload = { ...verificationForm, source_public_id: verificationForm.source_public_id || null }
    await runAction(submitManualDataVerification, selectedId, payload)
  }

  async function runQualityCheck() {
    if (!selectedId) return setError('Choose a record first.')
    try {
      setQuality(await manualDataQualityCheck(selectedId))
      setDuplicate(await manualDataDuplicateCheck(selectedId))
    } catch (reason) { setError(reason.message) }
  }

  async function loadHistory() {
    if (!selectedId) return setError('Choose a record first.')
    try {
      setHistoryData(await manualDataHistory(selectedId))
      setUsageSummary(await manualDataUsageSummary(selectedId))
    } catch (reason) { setError(reason.message) }
  }

  async function approveRecord() {
    if (!selectedId) return setError('Choose a record first.')
    await runAction(approveManualDataRecord, selectedId, { approved_uses: approveUses })
  }

  async function rejectRecord() {
    if (!selectedId) return setError('Choose a record first.')
    await runAction(rejectManualDataRecord, selectedId, { reason: rejectReason })
  }

  async function createCandidate(publicId) {
    setError('')
    try {
      const result = await createManualDataDatasetCandidate(publicId, { notes: 'Created from Manual Data Studio' })
      setNotice(`Dataset candidate created: ${result.exported_dataset_record_public_id}`)
      await refreshAfterAction(publicId)
    } catch (reason) { setError(reason.message) }
  }

  const reviewQueue = records.items.filter((r) => ['needs_review', 'needs_source_verification', 'needs_domain_review'].includes(r.status))
  const verificationQueue = records.items.filter((r) => r.status === 'needs_source_verification')
  const approvedItems = records.items.filter((r) => r.status === 'approved')
  const rejectedItems = records.items.filter((r) => r.status === 'rejected')

  const reviewWorkspaceProps = {
    selectedId, detail, quality, duplicate, reviews, verifications,
    reviewForm, setReviewForm, verificationForm, setVerificationForm,
    approveUses, setApproveUses, rejectReason, setRejectReason,
    revisionContent, setRevisionContent, revisionSummary, setRevisionSummary,
    onSubmitForReview: () => runAction(submitManualDataForReview, selectedId),
    onRequestCorrection: () => runAction(requestManualDataCorrection, selectedId, ''),
    onRequestSourceVerification: () => runAction(requestManualDataSourceVerification, selectedId, ''),
    onRequestDomainReview: () => runAction(requestManualDataDomainReview, selectedId, ''),
    onRunQualityCheck: runQualityCheck,
    onSubmitReview: submitReview,
    onSubmitVerification: submitVerification,
    onApprove: approveRecord,
    onReject: rejectRecord,
    onArchive: () => runAction(archiveManualDataRecord, selectedId),
    onCreateRevision: createNewRevision,
  }

  return (
    <section className="manual-data-workspace">
      <header className="section-heading">
        <div>
          <h2>Manual Data</h2>
          <p>Create, review, verify, and approve hand-authored Tamil/English/Tanglish records -- every record starts as a draft and is traceable to a source.</p>
        </div>
      </header>
      <div className="dataset-tabs">
        {TABS.map((item) => <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>)}
      </div>
      {notice && <div className="success-note" role="status">{notice}</div>}
      {error && <div className="form-error" role="alert">{error}</div>}

      {tab === 'Overview' && summary && (
        <section className="metric-grid">
          <article className="status-card"><span>Total manual records</span><strong>{summary.total}</strong></article>
          {RECORD_STATUSES.map((status) => (
            <article className="status-card" key={status}>
              <span>{status.replaceAll('_', ' ')}</span>
              <strong>{summary.by_status[status] || 0}</strong>
            </article>
          ))}
        </section>
      )}

      {tab === 'Create Data' && (
        <form className="inline-form" onSubmit={createRecord}>
          <h2>Create a manual data record</h2>
          <label>Data type
            <select value={recordForm.record_type} onChange={(e) => setRecordForm({ ...recordForm, record_type: e.target.value })}>
              {RECORD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>Primary language
            <select value={recordForm.primary_language} onChange={(e) => setRecordForm({ ...recordForm, primary_language: e.target.value })}>
              {LANGUAGE_CODES.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </label>
          <label>Creation method
            <select value={recordForm.creation_method} onChange={(e) => setRecordForm({ ...recordForm, creation_method: e.target.value })}>
              {CREATION_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>

          {recordForm.record_type === 'translation_pair' && (
            <>
              <label>Input language
                <select value={recordForm.input_language} onChange={(e) => setRecordForm({ ...recordForm, input_language: e.target.value })}>
                  <option value="">Choose</option>
                  {LANGUAGE_CODES.map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              </label>
              <label>Output language
                <select value={recordForm.output_language} onChange={(e) => setRecordForm({ ...recordForm, output_language: e.target.value })}>
                  <option value="">Choose</option>
                  {LANGUAGE_CODES.map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              </label>
            </>
          )}

          <label>Domain<input value={recordForm.domain} onChange={(e) => setRecordForm({ ...recordForm, domain: e.target.value })} /></label>
          <label>Topic<input value={recordForm.topic} onChange={(e) => setRecordForm({ ...recordForm, topic: e.target.value })} /></label>
          <label>Difficulty<input value={recordForm.difficulty} onChange={(e) => setRecordForm({ ...recordForm, difficulty: e.target.value })} /></label>

          <label>Fact dependency
            <select value={recordForm.fact_dependency} onChange={(e) => setRecordForm({ ...recordForm, fact_dependency: e.target.value })}>
              {FACT_DEPENDENCIES.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label>Knowledge risk
            <select value={recordForm.knowledge_risk} onChange={(e) => setRecordForm({ ...recordForm, knowledge_risk: e.target.value })}>
              {KNOWLEDGE_RISKS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </label>

          <div className="use-checkbox-grid">
            <span>Requested uses (a request, not automatic permission):</span>
            {TARGET_USES.map((use) => (
              <label className="rights-checkbox" key={use}>
                <input
                  type="checkbox"
                  checked={recordForm.requested_uses.includes(use)}
                  onChange={(e) => setRecordForm({
                    ...recordForm,
                    requested_uses: e.target.checked
                      ? [...recordForm.requested_uses, use]
                      : recordForm.requested_uses.filter((u) => u !== use),
                  })}
                /> {use}
              </label>
            ))}
          </div>

          <div className="panel-controls" style={{ gridColumn: '1 / -1' }}>
            <label>Source
              <select value={sourceMode} onChange={(e) => setSourceMode(e.target.value)}>
                <option value="existing">Use existing source</option>
                <option value="new">Create human-created source</option>
              </select>
            </label>
            {sourceMode === 'existing' ? (
              <label>Source public id<input value={sourcePublicId} onChange={(e) => setSourcePublicId(e.target.value)} placeholder="paste a source public_id from Sources & Rights" /></label>
            ) : (
              <>
                <label>Source code<input value={newSourceForm.source_code} onChange={(e) => setNewSourceForm({ ...newSourceForm, source_code: e.target.value })} placeholder="SRC-HUMAN-DHURAI-0001" /></label>
                <label>Source title<input value={newSourceForm.title} onChange={(e) => setNewSourceForm({ ...newSourceForm, title: e.target.value })} placeholder="Dhurai -- Spoken Tamil" /></label>
              </>
            )}
          </div>

          <h3 style={{ gridColumn: '1 / -1' }}>Content ({recordForm.record_type})</h3>
          <ContentFields recordType={recordForm.record_type} content={content} setContent={setContent} idPrefix="create" />

          <button className="rights-save-button">Save draft</button>
        </form>
      )}

      {tab === 'Records' && (
        <>
          <div className="dataset-tabs" role="group" aria-label="Record filters">
            <input placeholder="Search record code, domain, topic..." value={search} onChange={(e) => setSearch(e.target.value)} />
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {RECORD_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">All types</option>
              {RECORD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          {!records.items.length ? <div className="notice">No manual data records match this filter.</div> : (
            <div className="data-list">
              {records.items.map((item) => (
                <article key={item.public_id}>
                  <div><strong>{item.record_code}</strong><small>{item.record_type} · {item.status} · {item.source_title}</small></div>
                  <div>
                    <button onClick={() => openRecord(item.public_id)}>Open</button>
                    {item.status === 'archived'
                      ? <button onClick={() => runAction(restoreManualDataRecord, item.public_id)}>Restore</button>
                      : <button onClick={() => runAction(archiveManualDataRecord, item.public_id)}>Archive</button>}
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'Review Queue' && (
        <>
          <RecordSelector items={reviewQueue} selectedId={selectedId} onSelect={openRecord} />
          {!reviewQueue.length && <div className="notice">Nothing is waiting for review right now.</div>}
          <ReviewWorkspace {...reviewWorkspaceProps} />
        </>
      )}

      {tab === 'Verification Queue' && (
        <>
          <RecordSelector items={verificationQueue} selectedId={selectedId} onSelect={openRecord} />
          {!verificationQueue.length && <div className="notice">Nothing is waiting for source verification right now.</div>}
          <ReviewWorkspace {...reviewWorkspaceProps} />
        </>
      )}

      {tab === 'Approved' && (
        !approvedItems.length ? <div className="notice">No approved records yet.</div> : (
          <div className="data-list">
            {approvedItems.map((item) => (
              <article key={item.public_id}>
                <div><strong>{item.record_code}</strong><small>{item.record_type} · approved uses: {(item.approved_uses || []).join(', ') || 'none'}</small></div>
                <div>
                  <button onClick={() => openRecord(item.public_id)}>Open</button>
                  {item.exported_dataset_record_public_id
                    ? <span>Exported: {item.exported_dataset_record_public_id}</span>
                    : <button onClick={() => createCandidate(item.public_id)}>Create Dataset Candidate</button>}
                </div>
              </article>
            ))}
          </div>
        )
      )}

      {tab === 'Rejected' && (
        !rejectedItems.length ? <div className="notice">No rejected records right now.</div> : (
          <div className="data-list">
            {rejectedItems.map((item) => (
              <article key={item.public_id}>
                <div><strong>{item.record_code}</strong><small>{item.record_type}</small></div>
                <button onClick={() => openRecord(item.public_id)}>Review</button>
              </article>
            ))}
          </div>
        )
      )}

      {tab === 'History' && (
        <>
          <RecordSelector items={records.items} selectedId={selectedId} onSelect={openRecord} />
          <div className="panel-controls">
            <button type="button" onClick={loadHistory}>Load history</button>
          </div>
          {historyData && (
            <div className="history-panel">
              <h3>Revisions</h3>
              <ol>{historyData.revisions.map((r) => <li key={r.public_id}>#{r.revision_number} -- {r.change_summary} ({r.created_at})</li>)}</ol>
              <h3>Events</h3>
              <ol>{historyData.events.map((e) => <li key={e.public_id}>{e.event_type}: {e.status_before} → {e.status_after} ({e.created_at})</li>)}</ol>
              {usageSummary && (
                <>
                  <h3>Usage eligibility (all target uses)</h3>
                  <section className="metric-grid">
                    {Object.entries(usageSummary).map(([use, decision]) => (
                      <article className="status-card" key={use}>
                        <span>{use.replaceAll('_', ' ')}</span>
                        <strong>{decision.allowed ? 'Allowed' : 'Blocked'}</strong>
                      </article>
                    ))}
                  </section>
                </>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}
