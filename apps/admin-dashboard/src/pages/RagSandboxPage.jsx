import { useEffect, useState } from 'react'
import {
  ragSandboxOverview, ragSandboxExperiments, createRagSandboxExperiment, ragSandboxExperiment,
  ragSandboxEligibility, cancelRagSandboxExperiment,
  requestRagSandboxApproval, approveRagSandboxExperiment, rejectRagSandboxApproval,
  prepareRagSandboxCorpus, ragSandboxRecords,
  buildRagSandboxIndex, ragSandboxIndexes, deleteRagSandboxIndex,
  createRagSandboxQuerySet, ragSandboxQuerySets, addRagSandboxQuery, ragSandboxQueries,
  finalizeRagSandboxQuerySet,
  runRagSandboxRetrieval, ragSandboxRetrievalRuns, ragSandboxRetrievalRun,
  runRagSandboxGeneration, ragSandboxAnswerRuns, ragSandboxAnswerRun,
  ragSandboxCitations, ragSandboxEvaluations, runRagSandboxEvaluation,
  reviewRagSandboxQuery, finalizeRagSandboxReport, ragSandboxReports,
  acceptRagSandboxExperiment, rejectRagSandboxExperiment,
  requestRagSandboxDeletion, confirmRagSandboxDeletion, executeRagSandboxDeletion,
  ragSandboxEvents,
} from '../services/api.js'

const TABS = [
  'Overview', 'Experiments', 'Approval', 'Corpus', 'Chunks', 'Indexes', 'Query Sets',
  'Retrieval Results', 'Grounded Answers', 'Citations', 'Language Tests', 'Conflict Tests',
  'Injection Tests', 'Human Review', 'Final Report', 'Acceptance', 'Deletion & History',
]

const PURPOSES = [
  'retrieval_validation', 'grounded_answer_validation', 'multilingual_validation',
  'citation_validation', 'conflict_handling_validation', 'injection_resistance_validation',
  'production_rag_readiness', 'training_data_suitability_research',
]
const INDEX_KINDS = ['bm25', 'vector', 'hybrid']
const QUERY_TYPES = [
  'fact_lookup', 'explanation', 'comparison', 'summary', 'translation', 'definition',
  'multi_hop', 'insufficient_evidence', 'conflicting_sources', 'prompt_injection',
  'language_routing', 'citation_required',
]
const QUERY_LANGUAGES = ['tamil', 'english', 'tanglish', 'mixed', 'other', 'unknown']
const HUMAN_REVIEW_DECISIONS = [
  'pass', 'pass_with_conditions', 'fail', 'needs_revision', 'exclude_query',
  'needs_more_evidence',
]
const ACCEPTANCE_DECISIONS = ['accepted', 'accepted_with_conditions', 'rejected', 'needs_more_testing']

const SAFETY_NOTICE = 'Every sandbox experiment builds its own dedicated, never-production-visible knowledge space and index -- production RAG and public chat can never see sandbox data. Only accepted, promotion-eligible Phase 12 records may be promoted. Acceptance of a sandbox report never activates production RAG and never approves training.'

const emptyNewExperiment = { sample_import_public_id: '', purpose: 'retrieval_validation' }
const emptyApprovalRequest = { purpose: 'retrieval_validation', maximum_records: 500, maximum_total_characters: 2000000, maximum_total_tokens: 500000 }
const emptyApprovalDecision = { expires_at: '' }
const emptyBuildIndex = { index_kind: 'hybrid', top_k: 5, minimum_score: 0.15 }
const emptyQuery = { query_text: '', language: 'unknown', query_type: 'fact_lookup', must_refuse_if_insufficient: false, conflict_expected: false, injection_test: false }
const emptyDeletionRequest = { reason: '' }
const emptyAcceptance = { decision: 'accepted', reason: '', conditions: {} }

export default function RagSandboxPage({ initialSampleImportPublicId }) {
  const [tab, setTab] = useState('Overview')
  const [experiments, setExperiments] = useState([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [newExperimentForm, setNewExperimentForm] = useState(emptyNewExperiment)
  const [selectedId, setSelectedId] = useState('')
  const [selected, setSelected] = useState(null)
  const [eligibility, setEligibility] = useState(null)

  const [approvalRequestForm, setApprovalRequestForm] = useState(emptyApprovalRequest)
  const [approvalDecisionForm, setApprovalDecisionForm] = useState(emptyApprovalDecision)

  const [records, setRecords] = useState([])
  const [indexes, setIndexes] = useState([])
  const [buildIndexForm, setBuildIndexForm] = useState(emptyBuildIndex)

  const [querySets, setQuerySets] = useState([])
  const [activeQuerySetId, setActiveQuerySetId] = useState('')
  const [queries, setQueries] = useState([])
  const [newQuerySetName, setNewQuerySetName] = useState('')
  const [newQueryForm, setNewQueryForm] = useState(emptyQuery)

  const [retrievalRuns, setRetrievalRuns] = useState([])
  const [retrievalForm, setRetrievalForm] = useState({ index_public_id: '', query_set_public_id: '' })
  const [selectedRetrievalRun, setSelectedRetrievalRun] = useState(null)

  const [answerRuns, setAnswerRuns] = useState([])
  const [generationForm, setGenerationForm] = useState({ retrieval_run_public_id: '', generation_assignment_public_id: '' })
  const [selectedAnswerRun, setSelectedAnswerRun] = useState(null)

  const [citations, setCitations] = useState([])
  const [evaluations, setEvaluations] = useState([])
  const [evaluationAnswerRunId, setEvaluationAnswerRunId] = useState('')

  const [reviewDrafts, setReviewDrafts] = useState({})
  const [report, setReport] = useState(null)
  const [acceptanceForm, setAcceptanceForm] = useState(emptyAcceptance)
  const [deletionRequestForm, setDeletionRequestForm] = useState(emptyDeletionRequest)
  const [events, setEvents] = useState([])

  function loadExperiments() {
    ragSandboxExperiments('?page_size=100').then((data) => setExperiments(data.items)).catch((reason) => setError(reason.message))
  }

  useEffect(() => { loadExperiments() }, [])

  useEffect(() => {
    if (!initialSampleImportPublicId) return
    setNewExperimentForm((form) => ({ ...form, sample_import_public_id: initialSampleImportPublicId }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSampleImportPublicId])

  function selectExperiment(publicId) {
    setSelectedId(publicId)
    setSelected(null)
    setError(''); setNotice('')
    refreshSelected(publicId)
    setTab('Corpus')
  }

  // Independent fetches run together (Promise.all), not chained one after
  // another -- Phase 12's known sequential-refresh lag lesson carried over.
  function refreshSelected(publicId = selectedId) {
    if (!publicId) return
    const requestId = publicId
    Promise.all([
      ragSandboxExperiment(publicId),
      ragSandboxRecords(publicId, '?page_size=100'),
      ragSandboxIndexes(publicId),
      ragSandboxQuerySets(publicId),
      ragSandboxRetrievalRuns(publicId),
      ragSandboxAnswerRuns(publicId),
      ragSandboxCitations(publicId),
      ragSandboxEvaluations(publicId),
      ragSandboxReports(publicId).catch(() => ({ items: [] })),
      ragSandboxEvents(publicId, '?page_size=100'),
    ]).then(([exp, recordsData, indexesData, querySetsData, retrievalData, answerData, citationsData, evaluationsData, reportsData, eventsData]) => {
      if (requestId !== selectedId && requestId !== publicId) return
      setSelected(exp)
      setRecords(recordsData.items)
      setIndexes(indexesData.items)
      setQuerySets(querySetsData.items)
      setRetrievalRuns(retrievalData.items)
      setAnswerRuns(answerData.items)
      setCitations(citationsData.items)
      setEvaluations(evaluationsData.items)
      setReport(reportsData.items?.length ? reportsData.items[reportsData.items.length - 1] : null)
      setEvents(eventsData.items)
    }).catch((reason) => setError(reason.message))
    ragSandboxEligibility(publicId).then(setEligibility).catch(() => setEligibility(null))
  }

  async function action(label, fn) {
    setBusy(label); setError(''); setNotice('')
    try {
      await fn()
      loadExperiments()
      refreshSelected()
      setNotice(`${label}: done.`)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitNewExperiment(event) {
    event.preventDefault()
    if (!newExperimentForm.sample_import_public_id.trim()) return
    setBusy('Create experiment'); setError('')
    try {
      const created = await createRagSandboxExperiment(newExperimentForm)
      loadExperiments()
      selectExperiment(created.public_id)
      setNotice(`Experiment ${created.experiment_code} created. Production RAG remains unchanged until Admin acceptance -- and even then, only advisory readiness signals are produced.`)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitApprovalRequest(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Request approval', () => requestRagSandboxApproval(selectedId, {
      ...approvalRequestForm,
      maximum_records: Number(approvalRequestForm.maximum_records),
      maximum_total_characters: Number(approvalRequestForm.maximum_total_characters),
      maximum_total_tokens: Number(approvalRequestForm.maximum_total_tokens),
    }))
  }

  async function submitApprovalDecision(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Approve experiment', () => approveRagSandboxExperiment(selectedId, { ...approvalDecisionForm }))
  }

  async function submitBuildIndex(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Build index', () => buildRagSandboxIndex(selectedId, {
      ...buildIndexForm,
      top_k: Number(buildIndexForm.top_k),
      minimum_score: Number(buildIndexForm.minimum_score),
    }))
  }

  async function submitNewQuerySet(event) {
    event.preventDefault()
    if (!selectedId || !newQuerySetName.trim()) return
    action('Create query set', async () => {
      const created = await createRagSandboxQuerySet(selectedId, { name: newQuerySetName })
      setActiveQuerySetId(created.public_id)
      setNewQuerySetName('')
    })
  }

  function openQuerySet(querySetId) {
    setActiveQuerySetId(querySetId)
    ragSandboxQueries(selectedId, querySetId).then((data) => setQueries(data.items)).catch((reason) => setError(reason.message))
  }

  async function submitNewQuery(event) {
    event.preventDefault()
    if (!selectedId || !activeQuerySetId || !newQueryForm.query_text.trim()) return
    action('Add query', async () => {
      await addRagSandboxQuery(selectedId, activeQuerySetId, newQueryForm)
      openQuerySet(activeQuerySetId)
      setNewQueryForm(emptyQuery)
    })
  }

  async function submitRunRetrieval(event) {
    event.preventDefault()
    if (!selectedId || !retrievalForm.index_public_id || !retrievalForm.query_set_public_id) return
    action('Run retrieval', () => runRagSandboxRetrieval(selectedId, retrievalForm))
  }

  function openRetrievalRun(runId) {
    ragSandboxRetrievalRun(selectedId, runId).then(setSelectedRetrievalRun).catch((reason) => setError(reason.message))
  }

  async function submitRunGeneration(event) {
    event.preventDefault()
    if (!selectedId || !generationForm.retrieval_run_public_id || !generationForm.generation_assignment_public_id) return
    action('Run generation', () => runRagSandboxGeneration(selectedId, generationForm))
  }

  function openAnswerRun(runId) {
    ragSandboxAnswerRun(selectedId, runId).then(setSelectedAnswerRun).catch((reason) => setError(reason.message))
  }

  async function submitRunEvaluation() {
    if (!selectedId || !evaluationAnswerRunId) return
    action('Run evaluation', () => runRagSandboxEvaluation(selectedId, { answer_run_public_id: evaluationAnswerRunId }))
  }

  async function submitQueryReview(queryId) {
    const draft = reviewDrafts[queryId] || { decision: 'pass', notes: '' }
    if (!draft.decision) { setError('A decision is required to review a query.'); return }
    action(`Review query ${queryId}`, () => reviewRagSandboxQuery(selectedId, queryId, draft))
  }

  async function submitAcceptance(event) {
    event.preventDefault()
    if (!selectedId || !report || !acceptanceForm.reason.trim()) return
    const payload = { ...acceptanceForm, report_public_id: report.public_id }
    action('Record acceptance decision', () => acceptRagSandboxExperiment(selectedId, payload))
  }

  async function submitDeletionRequest(event) {
    event.preventDefault()
    if (!selectedId || !deletionRequestForm.reason.trim()) return
    action('Request deletion', async () => {
      await requestRagSandboxDeletion(selectedId, deletionRequestForm)
      setDeletionRequestForm(emptyDeletionRequest)
    })
  }

  const evaluationsByType = (type) => evaluations.filter((row) => row.evaluation_type === type)

  const currentPage = <>
    <section className="intro">
      <div><span>Data research studio</span><h2>RAG Sandbox</h2></div>
      <div className="phase-number">P13</div>
    </section>
    <div className="notice">{SAFETY_NOTICE}</div>
    {error && <div className="notice error-notice">{error}</div>}
    {notice && <div className="success-note">{notice}</div>}
    <nav aria-label="RAG Sandbox sections" style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
      {TABS.map((item) => (
        <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>
      ))}
    </nav>

    {tab === 'Overview' && <>
      <h3>What this workspace does</h3>
      <p>Test a finalized Phase 12 sample-validation report&apos;s accepted records in an isolated retrieval and grounded-generation pipeline: build BM25/vector/hybrid indexes, run retrieval and grounded-answer tests including insufficient-evidence, conflicting-source, and prompt-injection cases, validate citations, and produce an immutable report with advisory readiness signals.</p>
      {selected && <div className="notice" style={{ marginTop: '1rem' }}>
        <h4>{selected.experiment_code}</h4>
        <p>Status: <strong>{selected.status}</strong> · Stage: <strong>{selected.current_stage}</strong> · Purpose: <strong>{selected.purpose}</strong></p>
        <p>Records: <strong>{records.length}</strong> · Indexes: <strong>{indexes.length}</strong> · Query sets: <strong>{querySets.length}</strong></p>
        <p>Retrieval runs: <strong>{retrievalRuns.length}</strong> · Answer runs: <strong>{answerRuns.length}</strong> · Citations: <strong>{citations.length}</strong></p>
        <p>Production RAG readiness (advisory): <strong>{selected.production_rag_readiness}</strong> · Training-data observation (advisory): <strong>{selected.training_data_observation}</strong></p>
      </div>}
      {!selected && <p>Select or create an experiment in the &quot;Experiments&quot; tab to get started.</p>}
    </>}

    {tab === 'Experiments' && <>
      <h3>Experiments</h3>
      <form onSubmit={submitNewExperiment} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem', margin: '1rem 0' }}>
        <label>Finalized Phase 12 sample-import public ID<input required value={newExperimentForm.sample_import_public_id} onChange={(e) => setNewExperimentForm({ ...newExperimentForm, sample_import_public_id: e.target.value })} /></label>
        <label>Purpose
          <select value={newExperimentForm.purpose} onChange={(e) => setNewExperimentForm({ ...newExperimentForm, purpose: e.target.value })}>
            {PURPOSES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <button type="submit" disabled={!!busy}>Create RAG sandbox proposal</button>
      </form>
      <table>
        <thead><tr><th>Code</th><th>Status</th><th>Stage</th><th>Purpose</th><th>Production RAG readiness</th><th></th></tr></thead>
        <tbody>
          {experiments.map((item) => (
            <tr key={item.public_id}>
              <td>{item.experiment_code}</td>
              <td>{item.status}</td>
              <td>{item.current_stage}</td>
              <td>{item.purpose}</td>
              <td>{item.production_rag_readiness}</td>
              <td>
                <button onClick={() => selectExperiment(item.public_id)}>Open</button>
                {item.status === 'draft' && <button disabled={!!busy} onClick={() => action('Cancel experiment', () => cancelRagSandboxExperiment(item.public_id))}>Cancel</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>}

    {tab === 'Approval' && <>
      <h3>Approval{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        {eligibility && !eligibility.eligible && <div className="notice error-notice">Not eligible: {eligibility.blocking_reasons.join('; ')}</div>}
        <p>Approval binds the accepted-record set, bounds, and model assignments. If the underlying Phase 12 report or accepted-record set changes afterward, the approval becomes stale.</p>
        <h4>Request approval</h4>
        <form onSubmit={submitApprovalRequest} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Maximum records<input type="number" min="1" value={approvalRequestForm.maximum_records} onChange={(e) => setApprovalRequestForm({ ...approvalRequestForm, maximum_records: e.target.value })} /></label>
          <label>Maximum total characters<input type="number" min="1" value={approvalRequestForm.maximum_total_characters} onChange={(e) => setApprovalRequestForm({ ...approvalRequestForm, maximum_total_characters: e.target.value })} /></label>
          <label>Maximum total tokens<input type="number" min="1" value={approvalRequestForm.maximum_total_tokens} onChange={(e) => setApprovalRequestForm({ ...approvalRequestForm, maximum_total_tokens: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Request approval</button>
        </form>
        <h4 style={{ marginTop: '1.5rem' }}>Admin decision</h4>
        <form onSubmit={submitApprovalDecision} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Expiry (ISO date, optional)<input value={approvalDecisionForm.expires_at} onChange={(e) => setApprovalDecisionForm({ expires_at: e.target.value })} placeholder="2026-12-31T00:00:00" /></label>
          <div style={{ display: 'flex', gap: '.5rem' }}>
            <button type="submit" disabled={!!busy}>Approve experiment</button>
            <button type="button" disabled={!!busy} onClick={() => action('Reject approval', () => rejectRagSandboxApproval(selectedId, { reason: 'Rejected by Admin' }))}>Reject</button>
          </div>
        </form>
      </>}
    </>}

    {tab === 'Corpus' && <>
      <h3>Corpus{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <button disabled={!!busy} onClick={() => action('Prepare corpus', () => prepareRagSandboxCorpus(selectedId))}>Prepare isolated corpus</button>
        <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Sample record</th><th>Language</th><th>Content checksum</th><th>Contamination flagged</th></tr></thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.public_id}>
                <td>{r.sample_record_public_id}</td>
                <td>{r.language || '—'}</td>
                <td>{r.content_checksum?.slice(0, 12)}…</td>
                <td>{r.contamination_flagged ? 'yes' : 'no'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Chunks' && <>
      <h3>Chunks{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <p>Chunk counts per built index (each record is chunked under its own heading, preserving record boundaries).</p>
        <table>
          <thead><tr><th>Index kind</th><th>Status</th><th>Chunk count</th><th>Record count</th></tr></thead>
          <tbody>
            {indexes.map((i) => (
              <tr key={i.public_id}><td>{i.index_kind}</td><td>{i.status}</td><td>{i.chunk_count}</td><td>{i.record_count}</td></tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Indexes' && <>
      <h3>Indexes{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <form onSubmit={submitBuildIndex} style={{ display: 'grid', gap: '.5rem', maxWidth: '24rem' }}>
          <label>Index kind
            <select value={buildIndexForm.index_kind} onChange={(e) => setBuildIndexForm({ ...buildIndexForm, index_kind: e.target.value })}>
              {INDEX_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </label>
          <label>Top K<input type="number" min="1" value={buildIndexForm.top_k} onChange={(e) => setBuildIndexForm({ ...buildIndexForm, top_k: e.target.value })} /></label>
          <label>Minimum score<input type="number" step="0.01" min="0" max="1" value={buildIndexForm.minimum_score} onChange={(e) => setBuildIndexForm({ ...buildIndexForm, minimum_score: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Build index</button>
        </form>
        <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Kind</th><th>Status</th><th>Chunks</th><th></th></tr></thead>
          <tbody>
            {indexes.map((i) => (
              <tr key={i.public_id}>
                <td>{i.index_kind}</td><td>{i.status}</td><td>{i.chunk_count}</td>
                <td>{i.status !== 'deleted' && <button disabled={!!busy} onClick={() => action('Delete index', () => deleteRagSandboxIndex(selectedId, i.public_id))}>Delete</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </>}
    </>}

    {tab === 'Query Sets' && <>
      <h3>Query Sets{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <form onSubmit={submitNewQuerySet} style={{ display: 'flex', gap: '.5rem', marginBottom: '1rem' }}>
          <input placeholder="Query set name" value={newQuerySetName} onChange={(e) => setNewQuerySetName(e.target.value)} />
          <button type="submit" disabled={!!busy}>Create query set</button>
        </form>
        <table>
          <thead><tr><th>Name</th><th>Status</th><th>Query count</th><th></th></tr></thead>
          <tbody>
            {querySets.map((qs) => (
              <tr key={qs.public_id}>
                <td>{qs.name}</td><td>{qs.status}</td><td>{qs.query_count}</td>
                <td>
                  <button onClick={() => openQuerySet(qs.public_id)}>Open</button>
                  {qs.status === 'draft' && <button disabled={!!busy} onClick={() => action('Finalize query set', () => finalizeRagSandboxQuerySet(selectedId, qs.public_id))}>Finalize</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {activeQuerySetId && <>
          <h4 style={{ marginTop: '1rem' }}>Queries</h4>
          <form onSubmit={submitNewQuery} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
            <label>Query text<textarea required rows={2} value={newQueryForm.query_text} onChange={(e) => setNewQueryForm({ ...newQueryForm, query_text: e.target.value })} /></label>
            <label>Language
              <select value={newQueryForm.language} onChange={(e) => setNewQueryForm({ ...newQueryForm, language: e.target.value })}>
                {QUERY_LANGUAGES.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </label>
            <label>Query type
              <select value={newQueryForm.query_type} onChange={(e) => setNewQueryForm({ ...newQueryForm, query_type: e.target.value })}>
                {QUERY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            <button type="submit" disabled={!!busy}>Add query</button>
          </form>
          <table style={{ marginTop: '.5rem' }}>
            <thead><tr><th>Text</th><th>Language</th><th>Type</th><th>Human authored</th></tr></thead>
            <tbody>
              {queries.map((q) => (
                <tr key={q.public_id}><td>{q.query_text}</td><td>{q.language}</td><td>{q.query_type}</td><td>{q.human_authored ? 'yes' : 'no'}</td></tr>
              ))}
            </tbody>
          </table>
        </>}
      </>}
    </>}

    {tab === 'Retrieval Results' && <>
      <h3>Retrieval Results{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <form onSubmit={submitRunRetrieval} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Index
            <select value={retrievalForm.index_public_id} onChange={(e) => setRetrievalForm({ ...retrievalForm, index_public_id: e.target.value })}>
              <option value="">select an index</option>
              {indexes.filter((i) => i.status === 'active').map((i) => <option key={i.public_id} value={i.public_id}>{i.index_kind}</option>)}
            </select>
          </label>
          <label>Query set
            <select value={retrievalForm.query_set_public_id} onChange={(e) => setRetrievalForm({ ...retrievalForm, query_set_public_id: e.target.value })}>
              <option value="">select a query set</option>
              {querySets.filter((qs) => qs.status === 'finalized').map((qs) => <option key={qs.public_id} value={qs.public_id}>{qs.name}</option>)}
            </select>
          </label>
          <button type="submit" disabled={!!busy}>Run retrieval</button>
        </form>
        <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Config</th><th>Status</th><th>Total queries</th><th></th></tr></thead>
          <tbody>
            {retrievalRuns.map((r) => (
              <tr key={r.public_id}><td>{r.config_label}</td><td>{r.status}</td><td>{r.total_queries}</td><td><button onClick={() => openRetrievalRun(r.public_id)}>Open</button></td></tr>
            ))}
          </tbody>
        </table>
        {selectedRetrievalRun && <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Query</th><th>Metric availability</th><th>Expected-source hit</th><th>Recall@k</th><th>Result count</th></tr></thead>
          <tbody>
            {selectedRetrievalRun.results.map((res) => (
              <tr key={res.public_id}>
                <td>{res.query_public_id}</td><td>{res.metric_availability}</td>
                <td>{res.expected_source_hit === null ? '—' : res.expected_source_hit ? 'yes' : 'no'}</td>
                <td>{res.recall_at_k === null ? '—' : res.recall_at_k.toFixed(2)}</td>
                <td>{res.result_count}</td>
              </tr>
            ))}
          </tbody>
        </table>}
      </>}
    </>}

    {tab === 'Grounded Answers' && <>
      <h3>Grounded Answers{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <form onSubmit={submitRunGeneration} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Retrieval run
            <select value={generationForm.retrieval_run_public_id} onChange={(e) => setGenerationForm({ ...generationForm, retrieval_run_public_id: e.target.value })}>
              <option value="">select a retrieval run</option>
              {retrievalRuns.map((r) => <option key={r.public_id} value={r.public_id}>{r.config_label} ({r.total_queries} queries)</option>)}
            </select>
          </label>
          <label>Generation assignment public ID (active admin_diagnostic assignment)<input value={generationForm.generation_assignment_public_id} onChange={(e) => setGenerationForm({ ...generationForm, generation_assignment_public_id: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Run grounded generation</button>
        </form>
        <table style={{ marginTop: '1rem' }}>
          <thead><tr><th>Status</th><th>Language</th><th>Citations</th><th>Refusal used</th><th></th></tr></thead>
          <tbody>
            {answerRuns.map((a) => (
              <tr key={a.public_id}>
                <td>{a.status}</td><td>{a.answer_language}</td><td>{a.citation_count}</td><td>{a.refusal_used ? 'yes' : 'no'}</td>
                <td><button onClick={() => openAnswerRun(a.public_id)}>Open</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {selectedAnswerRun && <div className="notice" style={{ marginTop: '1rem' }}>
          <p style={{ whiteSpace: 'pre-wrap' }}>{selectedAnswerRun.answer_run.answer_text}</p>
        </div>}
      </>}
    </>}

    {tab === 'Citations' && <>
      <h3>Citations{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <table>
        <thead><tr><th>Label</th><th>Validation status</th><th>Duplicate</th><th>Orphan</th></tr></thead>
        <tbody>
          {citations.map((c) => (
            <tr key={c.public_id}><td>{c.citation_label}</td><td>{c.validation_status}</td><td>{c.is_duplicate ? 'yes' : 'no'}</td><td>{c.is_orphan ? 'yes' : 'no'}</td></tr>
          ))}
        </tbody>
      </table>}
    </>}

    {['Language Tests', 'Conflict Tests', 'Injection Tests'].includes(tab) && <>
      <h3>{tab}{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <div style={{ display: 'flex', gap: '.5rem', margin: '1rem 0' }}>
          <select value={evaluationAnswerRunId} onChange={(e) => setEvaluationAnswerRunId(e.target.value)}>
            <option value="">select an answer run</option>
            {answerRuns.map((a) => <option key={a.public_id} value={a.public_id}>{a.public_id}</option>)}
          </select>
          <button disabled={!!busy} onClick={submitRunEvaluation}>Run evaluation</button>
        </div>
        <table>
          <thead><tr><th>Result</th><th>Automated</th><th>Score</th></tr></thead>
          <tbody>
            {evaluationsByType(tab === 'Language Tests' ? 'language_compliance' : tab === 'Conflict Tests' ? 'conflict_handling' : 'prompt_injection').map((e) => (
              <tr key={e.public_id}><td>{e.result_status}</td><td>{e.automated ? 'yes' : 'no'}</td><td>{e.score === null ? '—' : e.score.toFixed(2)}</td></tr>
            ))}
          </tbody>
        </table>
        {tab === 'Injection Tests' && <p style={{ marginTop: '.5rem' }}><em>This never claims complete prompt-injection security -- only what was actually tested.</em></p>}
      </>}
    </>}

    {tab === 'Human Review' && <>
      <h3>Human Review{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <table>
        <thead><tr><th>Answer run</th><th>Decision</th><th>Review</th></tr></thead>
        <tbody>
          {answerRuns.map((a) => {
            const draft = reviewDrafts[a.query_public_id] || { decision: 'pass', notes: '' }
            return (
              <tr key={a.public_id}>
                <td>{a.query_public_id}</td>
                <td>
                  <select value={draft.decision} onChange={(e) => setReviewDrafts({ ...reviewDrafts, [a.query_public_id]: { ...draft, decision: e.target.value, answer_run_public_id: a.public_id } })}>
                    {HUMAN_REVIEW_DECISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                </td>
                <td><button disabled={!!busy} onClick={() => submitQueryReview(a.query_public_id)}>Submit</button></td>
              </tr>
            )
          })}
        </tbody>
      </table>}
    </>}

    {tab === 'Final Report' && <>
      <h3>Final Report{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <button disabled={!!busy} onClick={() => action('Finalize report', () => finalizeRagSandboxReport(selectedId))}>Finalize sandbox report</button>
        {report && <div className="notice" style={{ marginTop: '1rem' }}>
          <p>Report version <strong>{report.report_version}</strong>, finalized at <strong>{report.finalized_at}</strong>.</p>
          <p>Production RAG readiness (advisory only, never an activation): <strong>{report.production_rag_readiness}</strong></p>
          <p>Training-data observation (advisory only, never approval): <strong>{report.training_data_observation}</strong></p>
          <p>Recommended next action: {report.recommended_next_action}</p>
        </div>}
      </>}
    </>}

    {tab === 'Acceptance' && <>
      <h3>Acceptance{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        {!report && <p>Finalize a report first.</p>}
        {report && <form onSubmit={submitAcceptance} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Decision
            <select value={acceptanceForm.decision} onChange={(e) => setAcceptanceForm({ ...acceptanceForm, decision: e.target.value })}>
              {ACCEPTANCE_DECISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label>Reason<textarea required rows={2} value={acceptanceForm.reason} onChange={(e) => setAcceptanceForm({ ...acceptanceForm, reason: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Record acceptance decision</button>
        </form>}
        <p style={{ marginTop: '.5rem' }}><em>Acceptance never activates production RAG and never approves training.</em></p>
      </>}
    </>}

    {tab === 'Deletion & History' && <>
      <h3>Deletion &amp; History{selected ? ` — ${selected.experiment_code}` : ''}</h3>
      {!selected && <p>Select an experiment first.</p>}
      {selected && <>
        <h4>Request deletion</h4>
        <p>Removes only the sandbox corpus/index payload. Reports, acceptances, and audit history are always retained.</p>
        <form onSubmit={submitDeletionRequest} style={{ display: 'grid', gap: '.5rem', maxWidth: '28rem' }}>
          <label>Reason<textarea required rows={2} value={deletionRequestForm.reason} onChange={(e) => setDeletionRequestForm({ reason: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Request deletion</button>
        </form>
        <div style={{ display: 'flex', gap: '.5rem', marginTop: '.5rem' }}>
          <button disabled={!!busy} onClick={() => action('Confirm deletion', () => confirmRagSandboxDeletion(selectedId))}>Confirm deletion</button>
          <button disabled={!!busy} onClick={() => action('Execute deletion', () => executeRagSandboxDeletion(selectedId))}>Execute deletion</button>
        </div>
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
