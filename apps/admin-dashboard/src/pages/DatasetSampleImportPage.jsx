import { useEffect, useState } from 'react'
import {
  sampleImports, createSampleImport, sampleImport, cancelSampleImport,
  requestSampleImportApproval, approveSampleImport, rejectSampleImportApproval,
  downloadSampleFile, sampleFiles, sampleFile,
  validateSampleFiles, extractSampleArchives, scanSample, parseSample,
  sampleRecords, reviewSampleRecord, createSampleRecordRevision,
  sampleIssues, reviewSampleIssue,
  runSampleQualityChecks, runSampleDuplicateChecks, runSampleContaminationChecks,
  finalizeSampleImport, sampleImportReport,
  requestSampleDeletion, executeSampleDeletion, sampleImportEvents,
} from '../services/api.js'

const TABS = [
  'Overview', 'Sample Imports', 'Approval', 'Files', 'Security Scan', 'Parsed Records',
  'PII & Sensitive Data', 'Quality', 'Duplicates & Conflicts', 'Contamination',
  'Human Review', 'Final Report', 'Deletion & History',
]

const PURPOSES = [
  'manual_review', 'quality_evaluation', 'rag_sandbox_preparation',
  'format_validation', 'language_validation', 'security_validation',
]
const SELECTION_METHODS = [
  'deterministic_first_n', 'deterministic_seeded_sample', 'bounded_row_range',
  'bounded_split_subset', 'specific_approved_files', 'manual_file_selection',
  'provider_sample_endpoint', 'provider_file_metadata',
]
const REVIEW_DECISIONS = [
  'accept', 'accept_with_conditions', 'edit_derived_copy', 'redact_derived_copy',
  'exclude', 'reject_file', 'reject_sample', 'needs_more_evidence',
]
const ISSUE_CATEGORIES = [
  'pii', 'safety', 'quality', 'duplicate', 'conflict', 'contamination', 'poisoning',
]

const SAFETY_NOTICE = 'This workspace only ever downloads a small, bounded, separately-approved sample into isolated quarantine storage -- it never downloads a full dataset, clones a repository, executes downloaded content, activates RAG, creates a training dataset version, starts training, or releases a model. No quarantined record ever enters RAG or training. Original quarantined files/records are never modified.'

const emptyNewImport = {
  verification_case_public_id: '', candidate_public_id: '', purpose: 'manual_review',
  selection_method: 'deterministic_first_n', requested_count: 100,
}
const emptyApprovalRequest = { purpose: 'manual_review', requested_record_limit: 500, requested_byte_limit: 20_000_000 }
const emptyApprovalDecision = { approved_record_limit: 500, approved_byte_limit: 20_000_000, expires_at: '' }
const emptyDownload = { source_url: '', allowed_domains: '', original_filename: '' }
const emptyDeletionRequest = { reason: '' }

export default function DatasetSampleImportPage({ initialVerificationCasePublicId, onOpenRagSandbox }) {
  const [tab, setTab] = useState('Overview')
  const [imports, setImports] = useState([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [newImportForm, setNewImportForm] = useState(emptyNewImport)
  const [selectedId, setSelectedId] = useState('')
  const [selected, setSelected] = useState(null)

  const [approval, setApproval] = useState(undefined)
  const [approvalRequestForm, setApprovalRequestForm] = useState(emptyApprovalRequest)
  const [approvalDecisionForm, setApprovalDecisionForm] = useState(emptyApprovalDecision)

  const [files, setFiles] = useState([])
  const [downloadForm, setDownloadForm] = useState(emptyDownload)
  const [filePreview, setFilePreview] = useState(null)

  const [records, setRecords] = useState([])
  const [recordReviewDrafts, setRecordReviewDrafts] = useState({})

  const [issueCategoryFilter, setIssueCategoryFilter] = useState('')
  const [issues, setIssues] = useState([])
  const [issueReviewDrafts, setIssueReviewDrafts] = useState({})

  const [report, setReport] = useState(null)
  const [deletionRequestForm, setDeletionRequestForm] = useState(emptyDeletionRequest)
  const [events, setEvents] = useState([])

  function loadImports() {
    sampleImports('?page_size=100').then((data) => setImports(data.items)).catch((reason) => setError(reason.message))
  }

  useEffect(() => { loadImports() }, [])

  useEffect(() => {
    if (!initialVerificationCasePublicId) return
    sampleImports(`?verification_case_public_id=${initialVerificationCasePublicId}&page_size=1`)
      .then((data) => { if (data.items.length > 0) selectImport(data.items[0].public_id) })
      .catch(() => {})
    setNewImportForm((form) => ({ ...form, verification_case_public_id: initialVerificationCasePublicId }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialVerificationCasePublicId])

  function selectImport(publicId) {
    setSelectedId(publicId)
    setSelected(null)
    setError(''); setNotice('')
    refreshSelected(publicId)
    setTab('Files')
  }

  // Independent fetches run together (Promise.all), not chained one
  // after another -- a lesson carried over from Phase 11's own
  // sequential-refresh lag (see docs/sample_import/
  // phase12_sample_import_quarantine.md's "known limitations" note).
  function refreshSelected(publicId = selectedId) {
    if (!publicId) return
    const requestId = publicId
    Promise.all([
      sampleImport(publicId),
      sampleFiles(publicId),
      sampleRecords(publicId, '?page_size=100'),
      sampleIssues(publicId, issueCategoryFilter ? `?issue_category=${issueCategoryFilter}` : ''),
      sampleImportReport(publicId).catch(() => null),
      sampleImportEvents(publicId),
    ]).then(([importData, filesData, recordsData, issuesData, reportData, eventsData]) => {
      if (requestId !== selectedId && requestId !== publicId) return
      setSelected(importData)
      setFiles(filesData.items)
      setRecords(recordsData.items)
      setIssues(issuesData.items)
      setReport(reportData)
      setEvents(eventsData.items)
    }).catch((reason) => setError(reason.message))
  }

  useEffect(() => { if (selectedId) refreshSelected(selectedId) }, [issueCategoryFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  async function action(label, fn) {
    setBusy(label); setError(''); setNotice('')
    try {
      await fn()
      loadImports()
      refreshSelected()
      setNotice(`${label}: done.`)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitNewImport(event) {
    event.preventDefault()
    if (!newImportForm.verification_case_public_id.trim() || !newImportForm.candidate_public_id.trim()) return
    setBusy('Create sample import'); setError('')
    try {
      const created = await createSampleImport({ ...newImportForm, requested_count: Number(newImportForm.requested_count) || 0 })
      loadImports()
      selectImport(created.public_id)
      setNotice(`Sample import ${created.sample_import_code} created. It will not download anything until an Admin approves it.`)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitApprovalRequest(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Request approval', async () => {
      await requestSampleImportApproval(selectedId, {
        ...approvalRequestForm,
        requested_record_limit: Number(approvalRequestForm.requested_record_limit),
        requested_byte_limit: Number(approvalRequestForm.requested_byte_limit),
      })
    })
  }

  async function submitApprovalDecision(event) {
    event.preventDefault()
    if (!selectedId || !approvalDecisionForm.expires_at) { setError('An expiry date is required to approve.'); return }
    action('Approve sample import', () => approveSampleImport(selectedId, {
      ...approvalDecisionForm,
      approved_record_limit: Number(approvalDecisionForm.approved_record_limit),
      approved_byte_limit: Number(approvalDecisionForm.approved_byte_limit),
    }))
  }

  async function submitDownload(event) {
    event.preventDefault()
    if (!selectedId || !downloadForm.source_url.trim() || !downloadForm.allowed_domains.trim()) return
    action('Download approved sample', async () => {
      await downloadSampleFile(selectedId, {
        source_url: downloadForm.source_url,
        allowed_domains: downloadForm.allowed_domains.split(',').map((d) => d.trim()).filter(Boolean),
        original_filename: downloadForm.original_filename || null,
      })
      setDownloadForm(emptyDownload)
    })
  }

  async function openFilePreview(fileId) {
    try {
      const data = await sampleFile(selectedId, fileId, '?preview=true')
      setFilePreview(data)
    } catch (reason) { setError(reason.message) }
  }

  async function submitRecordReview(recordId) {
    const draft = recordReviewDrafts[recordId] || {}
    if (!draft.decision || !draft.reason?.trim()) { setError('A decision and a non-empty reason are required to review a record.'); return }
    if (draft.decision === 'edit_derived_copy' || draft.decision === 'redact_derived_copy') {
      action(`Review record ${recordId}`, () => createSampleRecordRevision(selectedId, recordId, draft))
    } else {
      action(`Review record ${recordId}`, () => reviewSampleRecord(selectedId, recordId, draft))
    }
  }

  async function submitIssueReview(issueId) {
    const draft = issueReviewDrafts[issueId] || {}
    if (!draft.decision || !draft.reason?.trim()) { setError('A decision and a non-empty reason are required to review an issue.'); return }
    action(`Review issue ${issueId}`, () => reviewSampleIssue(selectedId, issueId, draft))
  }

  async function submitDeletionRequest(event) {
    event.preventDefault()
    if (!selectedId || !deletionRequestForm.reason.trim()) return
    action('Request deletion', async () => {
      await requestSampleDeletion(selectedId, deletionRequestForm)
      setDeletionRequestForm(emptyDeletionRequest)
    })
  }

  const pendingCounts = {
    pii: issues.filter((i) => i.issue_category === 'pii' && !i.reviewer_decision).length,
    safety: issues.filter((i) => i.issue_category === 'safety' && !i.reviewer_decision).length,
    quality: issues.filter((i) => i.issue_category === 'quality' && !i.reviewer_decision).length,
    duplicate: issues.filter((i) => i.issue_category === 'duplicate' && !i.reviewer_decision).length,
    contamination: issues.filter((i) => i.issue_category === 'contamination').length,
  }

  const currentPage = <>
    <section className="intro">
      <div><span>Data research studio</span><h2>Sample Import &amp; Quarantine</h2></div>
      <div className="phase-number">P12</div>
    </section>
    <div className="notice">{SAFETY_NOTICE}</div>
    {error && <div className="notice error-notice">{error}</div>}
    {notice && <div className="success-note">{notice}</div>}
    <nav aria-label="Sample Import & Quarantine sections" style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
      {TABS.map((item) => (
        <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>
      ))}
    </nav>

    {tab === 'Overview' && <>
      <h3>What this workspace does</h3>
      <p>Safely inspect a small, bounded, separately-approved sample from a finalized dataset verification case: download into quarantine, validate file safety, scan for malware-like content, parse supported formats, and check for PII, safety issues, quality problems, duplicates, and evaluation contamination.</p>
      {selected && <div className="notice" style={{ marginTop: '1rem' }}>
        <h4>{selected.sample_import_code}</h4>
        <p>Status: <strong>{selected.status}</strong> · Stage: <strong>{selected.current_stage}</strong> · Purpose: <strong>{selected.purpose}</strong></p>
        <p>Files: <strong>{files.length}</strong> · Records: <strong>{records.length}</strong> · Quarantine bytes: <strong>{selected.quarantine_bytes_used}</strong></p>
        <p>PII pending: <strong>{pendingCounts.pii}</strong> · Safety pending: <strong>{pendingCounts.safety}</strong> · Quality pending: <strong>{pendingCounts.quality}</strong> · Duplicates: <strong>{pendingCounts.duplicate}</strong> · Contamination: <strong>{pendingCounts.contamination}</strong></p>
        <p>RAG sandbox eligible: <strong>{selected.rag_sandbox_eligible === null ? 'not yet finalized' : selected.rag_sandbox_eligible ? 'yes' : 'no'}</strong> · Training assessment: <strong>{selected.training_assessment_status || 'not_assessed'}</strong></p>
      </div>}
      {!selected && <p>Select or create a sample import in the &quot;Sample Imports&quot; tab to get started.</p>}
    </>}

    {tab === 'Sample Imports' && <>
      <h3>Sample imports</h3>
      <form onSubmit={submitNewImport} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem', margin: '1rem 0' }}>
        <label>Verification case public ID<input required value={newImportForm.verification_case_public_id} onChange={(e) => setNewImportForm({ ...newImportForm, verification_case_public_id: e.target.value })} /></label>
        <label>Candidate public ID<input required value={newImportForm.candidate_public_id} onChange={(e) => setNewImportForm({ ...newImportForm, candidate_public_id: e.target.value })} /></label>
        <label>Purpose
          <select value={newImportForm.purpose} onChange={(e) => setNewImportForm({ ...newImportForm, purpose: e.target.value })}>
            {PURPOSES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label>Selection method
          <select value={newImportForm.selection_method} onChange={(e) => setNewImportForm({ ...newImportForm, selection_method: e.target.value })}>
            {SELECTION_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label>Requested record count<input type="number" min="0" value={newImportForm.requested_count} onChange={(e) => setNewImportForm({ ...newImportForm, requested_count: e.target.value })} /></label>
        <button type="submit" disabled={!!busy}>Create sample import proposal</button>
      </form>
      <table>
        <thead><tr><th>Code</th><th>Status</th><th>Stage</th><th>Purpose</th><th>RAG sandbox eligible</th><th></th></tr></thead>
        <tbody>
          {imports.map((item) => (
            <tr key={item.public_id}>
              <td>{item.sample_import_code}</td>
              <td>{item.status}</td>
              <td>{item.current_stage}</td>
              <td>{item.purpose}</td>
              <td>{item.rag_sandbox_eligible === null ? '—' : item.rag_sandbox_eligible ? 'yes' : 'no'}</td>
              <td>
                <button onClick={() => selectImport(item.public_id)}>Open</button>
                {item.locked_at === null && item.status !== 'cancelled' && item.status !== 'deleted' && <button disabled={!!busy} onClick={() => action('Cancel import', () => cancelSampleImport(item.public_id))}>Cancel</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>}

    {tab === 'Approval' && <>
      <h3>Approval{selected ? ` — ${selected.sample_import_code}` : ''}</h3>
      {!selected && <p>Select a sample import first.</p>}
      {selected && <>
        <p>Dataset verification and sample-import approval are two separate decisions. Approval binds the record/byte limits, dataset version/revision, and expiry; if the underlying verification case changes afterward, the approval becomes stale and download is rejected.</p>
        <h4>Request approval</h4>
        <form onSubmit={submitApprovalRequest} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Requested record limit<input type="number" min="1" value={approvalRequestForm.requested_record_limit} onChange={(e) => setApprovalRequestForm({ ...approvalRequestForm, requested_record_limit: e.target.value })} /></label>
          <label>Requested byte limit<input type="number" min="1" value={approvalRequestForm.requested_byte_limit} onChange={(e) => setApprovalRequestForm({ ...approvalRequestForm, requested_byte_limit: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Request approval</button>
        </form>

        <h4 style={{ marginTop: '1.5rem' }}>Admin decision</h4>
        <form onSubmit={submitApprovalDecision} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Approved record limit<input type="number" min="1" value={approvalDecisionForm.approved_record_limit} onChange={(e) => setApprovalDecisionForm({ ...approvalDecisionForm, approved_record_limit: e.target.value })} /></label>
          <label>Approved byte limit<input type="number" min="1" value={approvalDecisionForm.approved_byte_limit} onChange={(e) => setApprovalDecisionForm({ ...approvalDecisionForm, approved_byte_limit: e.target.value })} /></label>
          <label>Expiry (ISO date)<input required value={approvalDecisionForm.expires_at} onChange={(e) => setApprovalDecisionForm({ ...approvalDecisionForm, expires_at: e.target.value })} placeholder="2026-12-31T00:00:00" /></label>
          <div style={{ display: 'flex', gap: '.5rem' }}>
            <button type="submit" disabled={!!busy}>Approve sample import</button>
            <button type="button" disabled={!!busy} onClick={() => action('Reject approval', () => rejectSampleImportApproval(selectedId, { reason: 'Rejected by Admin' }))}>Reject</button>
          </div>
        </form>
      </>}
    </>}

    {tab === 'Files' && <>
      <h3>Files{selected ? ` — ${selected.sample_import_code}` : ''}</h3>
      {!selected && <p>Select a sample import first.</p>}
      {selected && <>
        <h4>Download an approved file</h4>
        <form onSubmit={submitDownload} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
          <label>Source URL<input required value={downloadForm.source_url} onChange={(e) => setDownloadForm({ ...downloadForm, source_url: e.target.value })} /></label>
          <label>Allowed domains (comma-separated)<input required value={downloadForm.allowed_domains} onChange={(e) => setDownloadForm({ ...downloadForm, allowed_domains: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Download into quarantine</button>
        </form>
        <div style={{ display: 'flex', gap: '.5rem', margin: '1rem 0' }}>
          <button disabled={!!busy} onClick={() => action('Validate files', () => validateSampleFiles(selectedId))}>Validate files</button>
          <button disabled={!!busy} onClick={() => action('Extract archives', () => extractSampleArchives(selectedId))}>Extract archives</button>
        </div>
        <table>
          <thead><tr><th>Filename</th><th>Status</th><th>Blocked class</th><th>Size</th><th>Archive</th><th></th></tr></thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.public_id}>
                <td>{f.safe_filename}</td>
                <td>{f.status}</td>
                <td>{f.blocked_class || '—'}</td>
                <td>{f.size_bytes}</td>
                <td>{f.is_archive ? f.archive_format : '—'}</td>
                <td>{f.status === 'safe_for_scan' && !f.is_archive && <button onClick={() => openFilePreview(f.public_id)}>Preview</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filePreview && <div className="notice" style={{ marginTop: '1rem' }}>
          <p><strong>{filePreview.safe_filename}</strong> ({filePreview.status})</p>
          <pre style={{ whiteSpace: 'pre-wrap', maxHeight: '16rem', overflow: 'auto' }}>{filePreview.text_preview || '(no preview available)'}</pre>
        </div>}
      </>}
    </>}

    {tab === 'Security Scan' && <>
      <h3>Security Scan{selected ? ` — ${selected.sample_import_code}` : ''}</h3>
      {!selected && <p>Select a sample import first.</p>}
      {selected && <>
        <p>Deterministic checks only -- executable/script/macro signatures, polyglot mismatches, HTML scripts, CSV formula injection, pickle signatures. This never claims full malware detection.</p>
        <button disabled={!!busy} onClick={() => action('Scan sample', () => scanSample(selectedId))}>Run security scan</button>
        <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Filename</th><th>Status</th></tr></thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.public_id}><td>{f.safe_filename}</td><td>{f.status}</td></tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Parsed Records' && <>
      <h3>Parsed Records{selected ? ` — ${selected.sample_import_code}` : ''}</h3>
      {!selected && <p>Select a sample import first.</p>}
      {selected && <>
        <button disabled={!!busy} onClick={() => action('Parse sample', () => parseSample(selectedId))}>Parse validated files</button>
        <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Source</th><th>Language</th><th>Status</th><th>Preview</th><th>Review</th></tr></thead>
          <tbody>
            {records.map((r) => {
              const draft = recordReviewDrafts[r.public_id] || { decision: 'accept', reason: '' }
              return (
                <tr key={r.public_id}>
                  <td>{r.source_row_or_page || '—'}</td>
                  <td>{r.language || '—'}</td>
                  <td>{r.status}</td>
                  <td style={{ maxWidth: '18rem' }}>{(r.normalized_content || '').slice(0, 120)}</td>
                  <td>
                    <select value={draft.decision} onChange={(e) => setRecordReviewDrafts({ ...recordReviewDrafts, [r.public_id]: { ...draft, decision: e.target.value } })}>
                      {REVIEW_DECISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
                    </select>
                    <input placeholder="reason (required)" value={draft.reason} onChange={(e) => setRecordReviewDrafts({ ...recordReviewDrafts, [r.public_id]: { ...draft, reason: e.target.value } })} style={{ width: '10rem', marginLeft: '.25rem' }} />
                    <button disabled={!!busy} onClick={() => submitRecordReview(r.public_id)} style={{ marginLeft: '.25rem' }}>Submit</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </>}
    </>}

    {['PII & Sensitive Data', 'Quality', 'Duplicates & Conflicts', 'Contamination'].includes(tab) && <>
      <h3>{tab}{selected ? ` — ${selected.sample_import_code}` : ''}</h3>
      {!selected && <p>Select a sample import first.</p>}
      {selected && <>
        <div style={{ display: 'flex', gap: '.5rem', margin: '1rem 0' }}>
          <button disabled={!!busy} onClick={() => action('Run quality checks', () => runSampleQualityChecks(selectedId))}>Run language/quality/PII/safety checks</button>
          <button disabled={!!busy} onClick={() => action('Run duplicate checks', () => runSampleDuplicateChecks(selectedId))}>Run duplicate checks</button>
          <button disabled={!!busy} onClick={() => action('Run contamination checks', () => runSampleContaminationChecks(selectedId))}>Run contamination checks</button>
        </div>
        <table>
          <thead><tr><th>Category</th><th>Type</th><th>Status</th><th>Severity</th><th>Reviewer decision</th><th>Review</th></tr></thead>
          <tbody>
            {issues.filter((i) => (
              (tab === 'PII & Sensitive Data' && i.issue_category === 'pii') ||
              (tab === 'Quality' && (i.issue_category === 'quality' || i.issue_category === 'safety')) ||
              (tab === 'Duplicates & Conflicts' && (i.issue_category === 'duplicate' || i.issue_category === 'conflict')) ||
              (tab === 'Contamination' && i.issue_category === 'contamination')
            )).map((i) => {
              const draft = issueReviewDrafts[i.public_id] || { decision: 'accept', reason: '' }
              return (
                <tr key={i.public_id}>
                  <td>{i.issue_category}</td>
                  <td>{i.issue_type}</td>
                  <td>{i.status}</td>
                  <td>{i.severity || '—'}</td>
                  <td>{i.reviewer_decision || 'pending review'}</td>
                  <td>
                    <select value={draft.decision} onChange={(e) => setIssueReviewDrafts({ ...issueReviewDrafts, [i.public_id]: { ...draft, decision: e.target.value } })}>
                      {REVIEW_DECISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
                    </select>
                    <input placeholder="reason (required)" value={draft.reason} onChange={(e) => setIssueReviewDrafts({ ...issueReviewDrafts, [i.public_id]: { ...draft, reason: e.target.value } })} style={{ width: '10rem', marginLeft: '.25rem' }} />
                    <button disabled={!!busy} onClick={() => submitIssueReview(i.public_id)} style={{ marginLeft: '.25rem' }}>Submit</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Human Review' && <>
      <h3>Human review workflow{selected ? ` — ${selected.sample_import_code}` : ''}</h3>
      {!selected && <p>Select a sample import first.</p>}
      {selected && <>
        <p>Workflow: eligibility check → request approval → Admin approves → bounded download → file validation → archive safety → security scan → parsing → PII/safety/quality/duplicate/contamination checks → Admin review (Parsed Records / PII &amp; Sensitive Data / Quality / Duplicates &amp; Conflicts / Contamination tabs) → finalize.</p>
        <p>Filter issues by category:
          <select value={issueCategoryFilter} onChange={(e) => setIssueCategoryFilter(e.target.value)} style={{ marginLeft: '.5rem' }}>
            <option value="">all</option>
            {ISSUE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </p>
        <table>
          <thead><tr><th>Category</th><th>Type</th><th>Status</th><th>Reviewer</th><th>Reason</th></tr></thead>
          <tbody>
            {issues.map((i) => (
              <tr key={i.public_id}><td>{i.issue_category}</td><td>{i.issue_type}</td><td>{i.status}</td><td>{i.reviewed_by || '—'}</td><td>{i.review_reason || '—'}</td></tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Final Report' && <>
      <h3>Final Report{selected ? ` — ${selected.sample_import_code}` : ''}</h3>
      {!selected && <p>Select a sample import first.</p>}
      {selected && <>
        {selected.locked_at === null && <>
          <p>Not finalized yet. Finalizing is refused while any blocked file/issue remains unreviewed.</p>
          <button disabled={!!busy} onClick={() => action('Finalize', () => finalizeSampleImport(selectedId))}>Finalize sample validation report</button>
        </>}
        {selected.locked_at !== null && report && <div className="notice">
          <p>Finalized at <strong>{selected.locked_at}</strong>.</p>
          <p style={{ fontSize: '1.1em' }}>
            {report.rag_sandbox_eligible
              ? <strong>Eligible for RAG Sandbox</strong>
              : <strong>Not Eligible for RAG Sandbox</strong>}
          </p>
          <p>Training-assessment readiness (advisory only, never an approval): <strong>{report.training_assessment_status}</strong></p>
          <p>Accepted records: <strong>{report.report?.record_counts?.accepted ?? 0}</strong> · Excluded: <strong>{report.report?.record_counts?.excluded ?? 0}</strong></p>
          <p>Recommended next step: {report.report?.recommended_next_step}</p>
          {report.rag_sandbox_eligible && onOpenRagSandbox && <div style={{ marginTop: '1rem', display: 'flex', gap: '.5rem' }}>
            <button onClick={() => onOpenRagSandbox(selectedId)}>Create RAG Sandbox Proposal</button>
            <button onClick={() => onOpenRagSandbox(selectedId)}>Open Existing RAG Sandbox</button>
          </div>}
        </div>}
      </>}
    </>}

    {tab === 'Deletion & History' && <>
      <h3>Deletion &amp; History{selected ? ` — ${selected.sample_import_code}` : ''}</h3>
      {!selected && <p>Select a sample import first.</p>}
      {selected && <>
        <h4>Request deletion</h4>
        <p>Removes only the quarantined payload (original/derived files). Manifests, checksums, reports, and audit history are always retained.</p>
        <form onSubmit={submitDeletionRequest} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Reason<textarea required rows={2} value={deletionRequestForm.reason} onChange={(e) => setDeletionRequestForm({ reason: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Request deletion</button>
        </form>
        <button disabled={!!busy} onClick={() => action('Execute deletion', () => executeSampleDeletion(selectedId))} style={{ marginTop: '.5rem' }}>Confirm &amp; execute deletion</button>

        <h4 style={{ marginTop: '1.5rem' }}>Events</h4>
        <div className="audit-list">
          {events.map((event) => (
            <article key={event.public_id}>
              <div><strong>{event.event_type.replaceAll('_', ' ')}</strong><span>{event.performed_by_admin_public_id}</span></div>
              <small>{event.summary} — {event.created_at}</small>
            </article>
          ))}
        </div>
      </>}
    </>}
  </>

  return currentPage
}
