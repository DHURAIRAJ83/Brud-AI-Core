import { useEffect, useState } from 'react'
import {
  knowledgeGapOverview, knowledgeGapCases, knowledgeGapCase, knowledgeGapOccurrences,
  knowledgeGapReviews, knowledgeGapNotes, knowledgeGapEvents, reviewKnowledgeGapCase,
  addKnowledgeGapNote, resolveKnowledgeGapCase, archiveKnowledgeGapCase, assessKnowledgeGapHandoff,
  knowledgeGapClusters, proposeKnowledgeGapMerge, confirmKnowledgeGapMerge,
  recalculateKnowledgeGapClusterPriority, knowledgeGapDailyReports, generateKnowledgeGapDailyReport,
  requestKnowledgeGapDeletion, knowledgeGapDeletionPreview, confirmKnowledgeGapDeletion,
  executeKnowledgeGapDeletion,
} from '../services/api.js'

const tabs = [
  'Overview', 'New Cases', 'Priority Queue', 'Clusters', 'Tamil Gaps', 'RAG Gaps',
  'Web Demand', 'Tool Demand', 'Language Failures', 'Operational Failures',
  'RAG Handoff', 'Training Assessment', 'Daily Report', 'Deletion & History',
]

const NO_RAW_TEXT_NOTE = 'Redacted canonical questions only -- raw user text is never stored or shown here.'

const REVIEW_DECISIONS = [
  'confirm_gap', 'reclassify', 'keep_separate', 'needs_evidence', 'send_to_rag_research',
  'send_to_evaluation', 'mark_training_assessment_candidate', 'reject', 'block', 'archive',
]
const RESOLUTION_TYPES = [
  'answered_by_existing_model', 'resolved_by_routing_rule', 'resolved_by_approved_rag',
  'requires_trusted_web', 'requires_tool', 'requires_translation',
  'requires_language_policy_fix', 'requires_safety_policy_fix', 'requires_operational_fix',
  'evaluation_case_created', 'future_training_assessment', 'not_reproducible',
  'duplicate_resolved', 'rejected', 'blocked',
]

export default function KnowledgeGapsPage() {
  const [tab, setTab] = useState('Overview')
  const [error, setError] = useState('')
  const [overview, setOverview] = useState(null)
  const [cases, setCases] = useState([])
  const [selectedCase, setSelectedCase] = useState(null)

  useEffect(() => { refreshOverview() }, [])

  async function refreshOverview() {
    try { setOverview(await knowledgeGapOverview()) } catch (reason) { setError(reason.message) }
  }

  async function loadCases(query = '') {
    try { setCases((await knowledgeGapCases(query)).cases) } catch (reason) { setError(reason.message) }
  }

  function selectTab(value) {
    setTab(value)
    setSelectedCase(null)
    if (value === 'New Cases') loadCases('?status=new')
    if (value === 'Priority Queue') loadCases('?priority_band=critical')
    if (value === 'RAG Gaps') loadCases('?event_type=knowledge_gap')
    if (value === 'Web Demand') loadCases('?event_type=web_capability_gap')
    if (value === 'Tool Demand') loadCases('?event_type=tool_capability_gap')
    if (value === 'Language Failures') loadCases('?event_type=language_failure')
    if (value === 'Operational Failures') loadCases('?event_type=operational_failure')
    if (value === 'Tamil Gaps') loadCases('')
    if (value === 'RAG Handoff') loadCases('')
    if (value === 'Training Assessment') loadCases('')
  }

  async function openCaseDetail(publicId) {
    try {
      const [caseData, occurrences, reviews, notes, events] = await Promise.all([
        knowledgeGapCase(publicId), knowledgeGapOccurrences(publicId), knowledgeGapReviews(publicId),
        knowledgeGapNotes(publicId), knowledgeGapEvents(publicId),
      ])
      setSelectedCase({ ...caseData, occurrences: occurrences.occurrences, reviews: reviews.reviews, notes: notes.notes, events: events.events })
    } catch (reason) { setError(reason.message) }
  }

  return (
    <section className="documents-workspace">
      <header className="section-heading">
        <div>
          <h2>Knowledge Gaps</h2>
          <p>
            Phase 19 registry of unresolved public-chat cases -- knowledge gaps, capability gaps
            (Web/Tool unavailable), language failures, and operational incidents, kept separate
            from safety refusals and normal clarifications. {NO_RAW_TEXT_NOTE} RAG-research and
            training-assessment eligibility here are advisory only -- final approval always
            happens through the existing RAG and training workflows.
          </p>
        </div>
        <button onClick={refreshOverview}>Refresh</button>
      </header>
      <div className="dataset-tabs">
        {tabs.map((value) => (
          <button key={value} className={tab === value ? 'active' : ''} onClick={() => selectTab(value)}>{value}</button>
        ))}
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}

      {tab === 'Overview' && <OverviewTab overview={overview} />}
      {['New Cases', 'Priority Queue', 'RAG Gaps', 'Web Demand', 'Tool Demand', 'Language Failures', 'Operational Failures'].includes(tab) && (
        <CaseListTab tab={tab} cases={cases} onOpen={openCaseDetail} />
      )}
      {tab === 'Tamil Gaps' && <TamilGapsTab cases={cases} onOpen={openCaseDetail} />}
      {tab === 'RAG Handoff' && <HandoffTab cases={cases} onOpen={openCaseDetail} field="eligible_for_rag_research" />}
      {tab === 'Training Assessment' && <HandoffTab cases={cases} onOpen={openCaseDetail} field="eligible_for_training_assessment" />}
      {tab === 'Clusters' && <ClustersTab setError={setError} />}
      {tab === 'Daily Report' && <DailyReportTab setError={setError} />}
      {tab === 'Deletion & History' && <DeletionHistoryTab setError={setError} onOpen={openCaseDetail} />}

      {selectedCase && (
        <CaseDetailPanel caseData={selectedCase} onClose={() => setSelectedCase(null)}
          onChanged={() => openCaseDetail(selectedCase.public_id)} setError={setError} />
      )}
    </section>
  )
}

function OverviewTab({ overview }) {
  if (!overview) return <div className="notice">Loading...</div>
  return (
    <>
      <div className="notice">{NO_RAW_TEXT_NOTE}</div>
      <h3>Case volume</h3>
      <section className="metric-grid">
        <article className="status-card"><span>Total cases</span><strong>{overview.total_cases}</strong></article>
        <article className="status-card"><span>Awaiting review</span><strong>{overview.cases_awaiting_review}</strong></article>
        <article className="status-card"><span>Eligible for RAG research</span><strong>{overview.cases_eligible_for_rag_research}</strong></article>
        <article className="status-card"><span>Eligible for training assessment</span><strong>{overview.cases_eligible_for_training_assessment}</strong></article>
      </section>
      <h3>By event type</h3>
      <section className="metric-grid">
        {Object.entries(overview.by_event_type || {}).map(([type, count]) => (
          <article className="status-card" key={type}><span>{type}</span><strong>{count}</strong></article>
        ))}
      </section>
      <h3>By priority band</h3>
      <section className="metric-grid">
        {Object.entries(overview.by_priority_band || {}).map(([band, count]) => (
          <article className="status-card" key={band}><span>{band}</span><strong>{count}</strong></article>
        ))}
      </section>
      <h3>Tamil / Web / Tool / Language demand</h3>
      <section className="metric-grid">
        <article className="status-card"><span>Tamil capability cases</span><strong>{overview.tamil?.tamil_capability_cases ?? 0}</strong></article>
        <article className="status-card"><span>Tamil-first priority boosted</span><strong>{overview.tamil?.tamil_first_priority_boosted ?? 0}</strong></article>
        <article className="status-card"><span>Web-unavailable demand</span><strong>{overview.web_demand?.web_capability_gap_cases ?? 0}</strong></article>
        <article className="status-card"><span>Tool-unavailable demand</span><strong>{overview.tool_demand?.tool_capability_gap_cases ?? 0}</strong></article>
        <article className="status-card"><span>Wrong-language failures</span><strong>{overview.language_failures?.language_failure_cases ?? 0}</strong></article>
      </section>
    </>
  )
}

function CaseRow({ item, onOpen }) {
  return (
    <tr>
      <td>{item.canonical_question || (item.content_unavailable_for_review ? '(redaction unavailable)' : '--')}</td>
      <td>{item.event_type}</td>
      <td>{item.language}</td>
      <td>{item.frequency}</td>
      <td>{item.priority_band}</td>
      <td>{item.status}</td>
      <td><button type="button" onClick={() => onOpen(item.public_id)}>Details</button></td>
    </tr>
  )
}

function CaseListTab({ tab, cases, onOpen }) {
  return (
    <>
      <h3>{tab}</h3>
      <table>
        <thead><tr><th>Canonical question</th><th>Type</th><th>Language</th><th>Freq</th><th>Priority</th><th>Status</th><th></th></tr></thead>
        <tbody>{cases.map((item) => <CaseRow key={item.public_id} item={item} onOpen={onOpen} />)}</tbody>
      </table>
      {cases.length === 0 && <p className="notice">No cases in this view yet.</p>}
    </>
  )
}

function TamilGapsTab({ cases, onOpen }) {
  const tamilCases = cases.filter((c) => c.language === 'ta' || (c.priority_reason_codes || []).includes('TAMIL_FIRST_PRIORITY_APPLIED'))
  return <CaseListTab tab="Tamil Gaps" cases={tamilCases} onOpen={onOpen} />
}

function HandoffTab({ cases, onOpen, field }) {
  const eligible = cases.filter((c) => c[field])
  return (
    <>
      <p>Advisory only -- source-rights review, RAG-sandbox trial, and training approval all remain separate, human-controlled workflows.</p>
      <CaseListTab tab={field === 'eligible_for_rag_research' ? 'RAG Handoff' : 'Training Assessment'} cases={eligible} onOpen={onOpen} />
    </>
  )
}

function ClustersTab({ setError }) {
  const [clusters, setClusters] = useState([])
  const [mergeIds, setMergeIds] = useState('')
  const [proposal, setProposal] = useState(null)
  const [canonicalQuestion, setCanonicalQuestion] = useState('')
  const [language, setLanguage] = useState('en')

  useEffect(() => { load() }, [])
  async function load() {
    try { setClusters((await knowledgeGapClusters()).clusters) } catch (reason) { setError(reason.message) }
  }
  async function propose() {
    try {
      const ids = mergeIds.split(',').map((id) => id.trim()).filter(Boolean)
      setProposal(await proposeKnowledgeGapMerge({ case_public_ids: ids }))
    } catch (reason) { setError(reason.message) }
  }
  async function confirm() {
    try {
      const ids = mergeIds.split(',').map((id) => id.trim()).filter(Boolean)
      await confirmKnowledgeGapMerge({
        case_public_ids: ids, stale_check_fingerprint: proposal.stale_check_fingerprint,
        canonical_question: canonicalQuestion, primary_language: language,
      })
      setProposal(null); setMergeIds(''); await load()
    } catch (reason) { setError(reason.message) }
  }
  async function recalc(id) {
    try { await recalculateKnowledgeGapClusterPriority(id); await load() } catch (reason) { setError(reason.message) }
  }

  return (
    <>
      <h3>Clusters</h3>
      <table>
        <thead><tr><th>Canonical question</th><th>Frequency</th><th>Priority</th><th>Status</th><th></th></tr></thead>
        <tbody>
          {clusters.map((c) => (
            <tr key={c.public_id}>
              <td>{c.canonical_question}</td><td>{c.frequency}</td><td>{c.priority_band}</td><td>{c.status}</td>
              <td><button type="button" onClick={() => recalc(c.public_id)}>Recalculate priority</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>Propose a merge</h4>
      <p>Only exact/normalized duplicates auto-merge on capture -- everything else (including this manual proposal) requires this explicit Admin confirmation step.</p>
      <input placeholder="case-id-1, case-id-2" value={mergeIds} onChange={(e) => setMergeIds(e.target.value)} />
      <button type="button" onClick={propose}>Preview merge</button>
      {proposal && (
        <div className="history-panel">
          <p>Decisions: {proposal.decisions.map((d) => `${d.case_public_id}->${d.decision}`).join(', ') || '(no automatic match -- review manually)'}</p>
          <input placeholder="Canonical question for merged cluster" value={canonicalQuestion} onChange={(e) => setCanonicalQuestion(e.target.value)} />
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option><option value="ta">Tamil</option><option value="tgl">Tanglish</option>
          </select>
          <button type="button" onClick={confirm}>Confirm merge</button>
        </div>
      )}
    </>
  )
}

function DailyReportTab({ setError }) {
  const [reports, setReports] = useState([])
  useEffect(() => { load() }, [])
  async function load() {
    try { setReports((await knowledgeGapDailyReports()).reports) } catch (reason) { setError(reason.message) }
  }
  async function generate() {
    try { await generateKnowledgeGapDailyReport(); await load() } catch (reason) { setError(reason.message) }
  }
  return (
    <>
      <h3>Daily Knowledge-Gap Report</h3>
      <button type="button" onClick={generate}>Generate today's report</button>
      {reports.map((r) => (
        <div className="history-panel" key={r.public_id}>
          <p>{r.report_date}</p>
          <pre>{JSON.stringify(r.summary, null, 2)}</pre>
        </div>
      ))}
    </>
  )
}

function DeletionHistoryTab({ setError, onOpen }) {
  const [caseId, setCaseId] = useState('')
  const [preview, setPreview] = useState(null)

  async function loadPreview() {
    try { setPreview(await knowledgeGapDeletionPreview(caseId)) } catch (reason) { setError(reason.message) }
  }
  async function request() {
    try { await requestKnowledgeGapDeletion(caseId, { reason: 'admin requested' }); await loadPreview() } catch (reason) { setError(reason.message) }
  }
  async function confirm() {
    try { await confirmKnowledgeGapDeletion(caseId) } catch (reason) { setError(reason.message) }
  }
  async function execute() {
    try { await executeKnowledgeGapDeletion(caseId); onOpen(caseId) } catch (reason) { setError(reason.message) }
  }

  return (
    <>
      <h3>Deletion &amp; History</h3>
      <p>Deletion never removes the case's audit trail -- only the redacted/canonical question payload.</p>
      <input placeholder="case public id" value={caseId} onChange={(e) => setCaseId(e.target.value)} />
      <button type="button" onClick={loadPreview}>Load impact preview</button>
      {preview && <pre className="history-panel">{JSON.stringify(preview, null, 2)}</pre>}
      <div className="panel-controls">
        <button type="button" onClick={request}>Request deletion</button>
        <button type="button" onClick={confirm}>Confirm deletion</button>
        <button type="button" onClick={execute}>Execute deletion</button>
      </div>
    </>
  )
}

function CaseDetailPanel({ caseData, onClose, onChanged, setError }) {
  const [decision, setDecision] = useState(REVIEW_DECISIONS[0])
  const [comment, setComment] = useState('')
  const [noteType, setNoteType] = useState('investigation')
  const [noteText, setNoteText] = useState('')
  const [resolutionType, setResolutionType] = useState(RESOLUTION_TYPES[0])

  async function submitReview() {
    try { await reviewKnowledgeGapCase(caseData.public_id, { decision, comment: comment || null }); onChanged() } catch (reason) { setError(reason.message) }
  }
  async function submitNote() {
    try { await addKnowledgeGapNote(caseData.public_id, { note_type: noteType, note_text: noteText }); setNoteText(''); onChanged() } catch (reason) { setError(reason.message) }
  }
  async function submitResolve() {
    try { await resolveKnowledgeGapCase(caseData.public_id, { resolution_type: resolutionType }); onChanged() } catch (reason) { setError(reason.message) }
  }
  async function submitArchive() {
    try { await archiveKnowledgeGapCase(caseData.public_id); onChanged() } catch (reason) { setError(reason.message) }
  }
  async function submitAssessHandoff() {
    try { await assessKnowledgeGapHandoff(caseData.public_id); onChanged() } catch (reason) { setError(reason.message) }
  }

  return (
    <div className="history-panel" aria-label="Case detail">
      <button type="button" onClick={onClose}>Close</button>
      <h3>{caseData.canonical_question || '(redaction unavailable -- hash only)'}</h3>
      <p>Type: {caseData.event_type} · Status: {caseData.status} · Stage: {caseData.stage} · Priority: {caseData.priority_band}</p>
      <p>Reason codes: {(caseData.reason_codes || []).join(', ')}</p>
      <p>RAG-research eligible: {String(caseData.eligible_for_rag_research)} · Training-assessment eligible: {String(caseData.eligible_for_training_assessment)}</p>

      <h4>Occurrences ({caseData.occurrences.length})</h4>
      <h4>Notes ({caseData.notes.length})</h4>
      <ul>{caseData.notes.map((n) => <li key={n.public_id}>[{n.note_type}] {n.note_text_redacted}</li>)}</ul>
      <h4>Status history</h4>
      <ul>{caseData.events.map((e) => <li key={e.public_id}>{e.from_status ?? '(new)'} -&gt; {e.to_status} ({e.reason})</li>)}</ul>

      <h4>Actions</h4>
      <div className="panel-controls">
        <select value={decision} onChange={(e) => setDecision(e.target.value)}>
          {REVIEW_DECISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <input placeholder="comment" value={comment} onChange={(e) => setComment(e.target.value)} />
        <button type="button" onClick={submitReview}>Submit review</button>
      </div>
      <div className="panel-controls">
        <select value={noteType} onChange={(e) => setNoteType(e.target.value)}>
          {['investigation', 'possible_source', 'rights_concern', 'answer_draft', 'routing_issue', 'language_issue', 'safety_issue', 'operational_issue', 'resolution_note'].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input placeholder="note text (PII/secret-scanned before saving)" value={noteText} onChange={(e) => setNoteText(e.target.value)} />
        <button type="button" onClick={submitNote}>Add note</button>
      </div>
      <div className="panel-controls">
        <select value={resolutionType} onChange={(e) => setResolutionType(e.target.value)}>
          {RESOLUTION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <button type="button" onClick={submitResolve}>Resolve</button>
        <button type="button" onClick={submitArchive}>Archive</button>
        <button type="button" onClick={submitAssessHandoff}>Recompute RAG/training eligibility</button>
      </div>
    </div>
  )
}
