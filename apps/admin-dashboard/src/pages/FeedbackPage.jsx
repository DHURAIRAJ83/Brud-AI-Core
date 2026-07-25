import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  activateFeedbackPolicy,
  activateRegressionSuite,
  addFeedbackClassification,
  addRegressionFixture,
  approveDatasetCandidate,
  assignReview,
  compareRegressionRuns,
  correctedResponsesForEvent,
  createCorrectedResponse,
  createDatasetCandidate,
  createFeedbackPolicy,
  createFeedbackReview,
  createImprovementReport,
  createRegressionRun,
  createRegressionSuite,
  createReviewQueue,
  datasetCandidateIssues,
  datasetCandidates,
  datasetCandidateVersions,
  deleteFeedbackEvent,
  executeRegressionRun,
  exportDatasetCandidate,
  feedbackClassifications,
  feedbackEvents,
  feedbackFindings,
  feedbackManifest,
  feedbackPolicies,
  feedbackReviews,
  feedbackReviewSummary,
  quarantineDatasetCandidate,
  regressionMetrics,
  regressionResults,
  regressionSuites,
  rejectCorrectedResponse,
  rejectDatasetCandidate,
  reviewQueueItems,
  reviewQueues,
  submitFeedbackEvent,
  triageFeedbackEvent,
  validateCorrectedResponse,
  validateDatasetCandidate,
  validateFeedbackPolicy,
  validateRegressionSuite,
  verifyFeedbackManifest,
} from '../services/api.js'

const NO_AUTOMATIC_TRAINING_NOTICE = 'Feedback is reviewed, privacy-filtered, and explicitly approved before it can become a dataset candidate. No automatic self-training occurs.'
const DATASET_PIPELINE_NOTICE = 'An approved feedback candidate still passes through the existing dataset quality and versioning pipeline before training use.'
const REGRESSION_NOTICE = 'Regression fixtures are evaluation-only evidence and must not automatically become training records.'

const TABS = [
  'Overview', 'Feedback Policies', 'Feedback Events', 'Classification', 'Review Queues',
  'Human Reviews', 'Corrected Responses', 'Privacy & Safety', 'Dataset Candidates',
  'Candidate Quality', 'Candidate Approvals', 'Regression Suites', 'Regression Runs',
  'Model Comparisons', 'Improvement Reports', 'Reproducibility',
]

function Pre({ value }) {
  if (!value) return null
  return <pre className="notice" style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{JSON.stringify(value, null, 2)}</pre>
}

export default function FeedbackPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '', policies: [], events: [], queues: [], candidates: [], suites: [] })
  const [panelError, setPanelError] = useState('')

  const [policyName, setPolicyName] = useState('')
  const [selectedPolicyId, setSelectedPolicyId] = useState('')

  const [eventForm, setEventForm] = useState({ subject_type: 'model_release', subject_reference_public_id: '', feedback_policy_public_id: '', participant_scope_key: '', feedback_type: 'thumbs_up', comment: '', expected_language: '' })
  const [selectedEventId, setSelectedEventId] = useState('')
  const [classifications, setClassifications] = useState({ items: [] })
  const [findings, setFindings] = useState({ privacy: [], safety: [] })
  const [classificationForm, setClassificationForm] = useState({ category: 'helpful', severity: 'info' })

  const [queueForm, setQueueForm] = useState({ name: '', queue_type: 'general_quality' })
  const [selectedQueueId, setSelectedQueueId] = useState('')
  const [queueItems, setQueueItems] = useState({ items: [] })
  const [assignForm, setAssignForm] = useState({ feedback_event_public_id: '', reviewer_admin_public_id: '' })

  const [reviews, setReviews] = useState({ items: [] })
  const [reviewSummary, setReviewSummary] = useState(null)
  const [reviewForm, setReviewForm] = useState({ overall_score: 3, verdict: 'valid_feedback' })

  const [corrections, setCorrections] = useState({ items: [] })
  const [correctionForm, setCorrectionForm] = useState({ corrected_response_text: '', language: 'unknown' })

  const [candidateForm, setCandidateForm] = useState({ prompt_text: '', corrected_response_public_id: '' })
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [candidateVersions, setCandidateVersions] = useState({ items: [] })
  const [candidateIssues, setCandidateIssues] = useState({ items: [] })

  const [suiteForm, setSuiteForm] = useState({ name: '' })
  const [selectedSuiteId, setSelectedSuiteId] = useState('')
  const [fixtureForm, setFixtureForm] = useState({ category: 'citation_regression', input_text: '', expected_behavior: '', forbidden_behavior: '' })
  const [assignmentPublicId, setAssignmentPublicId] = useState('')
  const [runAId, setRunAId] = useState('')
  const [runBId, setRunBId] = useState('')
  const [runResult, setRunResult] = useState(null)
  const [comparisonResult, setComparisonResult] = useState(null)
  const [reportResult, setReportResult] = useState(null)
  const [manifestResult, setManifestResult] = useState(null)
  const [manifestVerification, setManifestVerification] = useState(null)

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [policies, events, queues, candidates, suites] = await Promise.all([
        feedbackPolicies(), feedbackEvents(), reviewQueues(), datasetCandidates(), regressionSuites(),
      ])
      setState({
        loading: false, error: '',
        policies: policies.items ?? [], events: events.items ?? [], queues: queues.items ?? [],
        candidates: candidates.items ?? [], suites: suites.items ?? [],
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function submitPolicy(event) {
    event.preventDefault()
    try { await createFeedbackPolicy({ name: policyName }); setPanelError(''); setPolicyName(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runValidatePolicy(id) {
    try { await validateFeedbackPolicy(id); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runActivatePolicy(id) {
    try { await activateFeedbackPolicy(id); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }

  async function submitEvent(event) {
    event.preventDefault()
    try {
      const body = { ...eventForm }
      if (!body.comment) delete body.comment
      if (!body.expected_language) delete body.expected_language
      const created = await submitFeedbackEvent(body)
      setPanelError('')
      setSelectedEventId(created.public_id)
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function selectEvent(id) {
    setSelectedEventId(id)
    setClassifications(await feedbackClassifications(id).catch(() => ({ items: [] })))
    setFindings(await feedbackFindings(id).catch(() => ({ privacy: [], safety: [] })))
    setReviews(await feedbackReviews(id).catch(() => ({ items: [] })))
    setReviewSummary(await feedbackReviewSummary(id).catch(() => null))
    setCorrections(await correctedResponsesForEvent(id).catch(() => ({ items: [] })))
  }
  async function runTriage() {
    try { await triageFeedbackEvent(selectedEventId); setPanelError(''); await selectEvent(selectedEventId); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runDeleteEvent() {
    try { await deleteFeedbackEvent(selectedEventId); setPanelError(''); await selectEvent(selectedEventId); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function submitClassification(event) {
    event.preventDefault()
    try { await addFeedbackClassification(selectedEventId, classificationForm); setPanelError(''); await selectEvent(selectedEventId) }
    catch (error) { setPanelError(error.message) }
  }

  async function submitQueue(event) {
    event.preventDefault()
    try { await createReviewQueue(queueForm); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function selectQueue(id) {
    setSelectedQueueId(id)
    setQueueItems(await reviewQueueItems(id).catch(() => ({ items: [] })))
  }
  async function submitAssign(event) {
    event.preventDefault()
    try {
      await assignReview(selectedQueueId, assignForm)
      setPanelError('')
      await selectQueue(selectedQueueId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitReview(event) {
    event.preventDefault()
    try {
      await createFeedbackReview(selectedEventId, reviewForm)
      setPanelError('')
      await selectEvent(selectedEventId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitCorrection(event) {
    event.preventDefault()
    try {
      await createCorrectedResponse(selectedEventId, correctionForm)
      setPanelError('')
      await selectEvent(selectedEventId)
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runValidateCorrection(id) {
    try { await validateCorrectedResponse(id); setPanelError(''); await selectEvent(selectedEventId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runRejectCorrection(id) {
    try { await rejectCorrectedResponse(id); setPanelError(''); await selectEvent(selectedEventId) }
    catch (error) { setPanelError(error.message) }
  }

  async function submitCandidate(event) {
    event.preventDefault()
    try {
      const created = await createDatasetCandidate(selectedEventId, candidateForm)
      setPanelError('')
      setSelectedCandidateId(created.public_id)
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function selectCandidate(id) {
    setSelectedCandidateId(id)
    setCandidateVersions(await datasetCandidateVersions(id).catch(() => ({ items: [] })))
    setCandidateIssues(await datasetCandidateIssues(id).catch(() => ({ items: [] })))
  }
  async function runValidateCandidate() {
    try { await validateDatasetCandidate(selectedCandidateId); setPanelError(''); await selectCandidate(selectedCandidateId); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runApproveCandidate() {
    try { await approveDatasetCandidate(selectedCandidateId); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runRejectCandidate() {
    try { await rejectDatasetCandidate(selectedCandidateId); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runQuarantineCandidate() {
    try { await quarantineDatasetCandidate(selectedCandidateId); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runExportCandidate() {
    try { await exportDatasetCandidate(selectedCandidateId); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }

  async function submitSuite(event) {
    event.preventDefault()
    try { await createRegressionSuite(suiteForm); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function submitFixture(event) {
    event.preventDefault()
    try { await addRegressionFixture(selectedSuiteId, fixtureForm); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runValidateSuite() {
    try { await validateRegressionSuite(selectedSuiteId); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runActivateSuite() {
    try { await activateRegressionSuite(selectedSuiteId); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runCreateRun(setRunId) {
    try {
      const run = await createRegressionRun(selectedSuiteId, { model_assignment_public_id: assignmentPublicId })
      const executed = await executeRegressionRun(run.public_id)
      setRunResult(executed)
      setRunId(run.public_id)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runCompare() {
    try {
      const result = await compareRegressionRuns({ left_run_public_id: runAId, right_run_public_id: runBId })
      setComparisonResult(result)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runCreateReport() {
    try {
      const report = await createImprovementReport({ feedback_policy_public_id: selectedPolicyId || undefined })
      setReportResult(report)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runGenerateManifest() {
    try { setManifestResult(await feedbackManifest(selectedPolicyId)); setManifestVerification(null); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runVerifyManifest() {
    try { setManifestVerification(await verifyFeedbackManifest(selectedPolicyId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  if (state.loading) return <section className="notice">Loading feedback and improvement workspace…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Feedback &amp; Improvement</h2>
          <p className="notice">{NO_AUTOMATIC_TRAINING_NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Feedback and improvement sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Feedback Events</h3>
          {(state.events ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => selectEvent(item.public_id)}>
              <strong>{item.feedback_type}</strong>
              <span>{item.status}</span>
            </button>
          ))}
          <h3>Feedback Policies</h3>
          {(state.policies ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => setSelectedPolicyId(item.public_id)}>
              <strong>{item.name}</strong>
              <span>{item.lifecycle_status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              <div className="metric-grid">
                <StatusCard label="Feedback policies" value={state.policies.length} tone="neutral" />
                <StatusCard label="Feedback events" value={state.events.length} tone="neutral" />
                <StatusCard label="Review queues" value={state.queues.length} tone="neutral" />
                <StatusCard label="Dataset candidates" value={state.candidates.length} tone="neutral" />
                <StatusCard label="Regression suites" value={state.suites.length} tone="neutral" />
                <StatusCard label="Public chat" value="placeholder" tone="good" />
              </div>
            </>
          )}

          {tab === 'Feedback Policies' && (
            <>
              <form className="inline-form training-form" onSubmit={submitPolicy}>
                <h3>Create feedback policy</h3>
                <label>Name<input value={policyName} onChange={(e) => setPolicyName(e.target.value)} /></label>
                <button type="submit">Create policy</button>
              </form>
              <div className="data-list">
                {(state.policies ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.name}</strong> — {item.lifecycle_status}
                    <div className="inline-form">
                      {item.lifecycle_status === 'draft' && <button onClick={() => runValidatePolicy(item.public_id)}>Validate</button>}
                      {item.lifecycle_status === 'validated' && <button onClick={() => runActivatePolicy(item.public_id)}>Activate</button>}
                      <button onClick={() => setSelectedPolicyId(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Feedback Events' && (
            <>
              <form className="inline-form training-form" onSubmit={submitEvent}>
                <h3>Submit feedback</h3>
                <label>Subject type
                  <select value={eventForm.subject_type} onChange={(e) => setEventForm({ ...eventForm, subject_type: e.target.value })}>
                    <option value="inference_result">inference_result</option>
                    <option value="rag_grounded_answer">rag_grounded_answer</option>
                    <option value="conversation_response">conversation_response</option>
                    <option value="evaluation_output">evaluation_output</option>
                    <option value="memory_orchestration_response">memory_orchestration_response</option>
                    <option value="release_candidate">release_candidate</option>
                    <option value="model_release">model_release</option>
                  </select>
                </label>
                <label>Subject reference public ID<input value={eventForm.subject_reference_public_id} onChange={(e) => setEventForm({ ...eventForm, subject_reference_public_id: e.target.value })} /></label>
                <label>Feedback policy public ID<input value={eventForm.feedback_policy_public_id} onChange={(e) => setEventForm({ ...eventForm, feedback_policy_public_id: e.target.value })} /></label>
                <label>Participant scope key<input value={eventForm.participant_scope_key} onChange={(e) => setEventForm({ ...eventForm, participant_scope_key: e.target.value })} /></label>
                <label>Feedback type
                  <select value={eventForm.feedback_type} onChange={(e) => setEventForm({ ...eventForm, feedback_type: e.target.value })}>
                    <option value="thumbs_up">thumbs_up</option>
                    <option value="thumbs_down">thumbs_down</option>
                    <option value="rating">rating</option>
                    <option value="issue_report">issue_report</option>
                    <option value="correction">correction</option>
                    <option value="citation_report">citation_report</option>
                    <option value="safety_report">safety_report</option>
                    <option value="language_report">language_report</option>
                    <option value="memory_report">memory_report</option>
                    <option value="retrieval_report">retrieval_report</option>
                  </select>
                </label>
                <label>Comment (bounded, privacy-scanned)<input value={eventForm.comment} onChange={(e) => setEventForm({ ...eventForm, comment: e.target.value })} /></label>
                <label>Expected language<input value={eventForm.expected_language} onChange={(e) => setEventForm({ ...eventForm, expected_language: e.target.value })} /></label>
                <button type="submit">Submit feedback</button>
              </form>
              {selectedEventId && (
                <div className="inline-form">
                  <button onClick={runTriage}>Triage</button>
                  <button onClick={runDeleteEvent}>Delete (retain checksum only)</button>
                </div>
              )}
            </>
          )}

          {tab === 'Classification' && (
            <>
              {!selectedEventId && <p className="notice">Select an event from the Feedback Events tab.</p>}
              {selectedEventId && (
                <>
                  <form className="inline-form training-form" onSubmit={submitClassification}>
                    <label>Category
                      <select value={classificationForm.category} onChange={(e) => setClassificationForm({ ...classificationForm, category: e.target.value })}>
                        {['helpful', 'unhelpful', 'incorrect', 'partially_correct', 'unsupported_claim', 'hallucination_like', 'wrong_language', 'poor_tamil', 'poor_tanglish', 'format_failure', 'instruction_not_followed', 'citation_missing', 'citation_invalid', 'citation_wrong', 'retrieval_irrelevant', 'retrieval_missing', 'unsafe_response', 'over_refusal', 'under_refusal', 'prompt_leakage', 'role_token_leakage', 'repetition', 'memory_wrong', 'memory_outdated', 'memory_privacy_issue', 'memory_not_used', 'memory_should_not_be_used', 'too_long', 'too_short', 'unclear', 'other'].map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </label>
                    <label>Severity
                      <select value={classificationForm.severity} onChange={(e) => setClassificationForm({ ...classificationForm, severity: e.target.value })}>
                        <option value="info">info</option>
                        <option value="low">low</option>
                        <option value="medium">medium</option>
                        <option value="high">high</option>
                        <option value="critical">critical</option>
                      </select>
                    </label>
                    <button type="submit">Add classification</button>
                  </form>
                  <div className="data-list">
                    {(classifications.items ?? []).map((item) => <article key={item.public_id}>{item.category} ({item.severity})</article>)}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Review Queues' && (
            <>
              <form className="inline-form training-form" onSubmit={submitQueue}>
                <h3>Create review queue</h3>
                <label>Name<input value={queueForm.name} onChange={(e) => setQueueForm({ ...queueForm, name: e.target.value })} /></label>
                <label>Queue type
                  <select value={queueForm.queue_type} onChange={(e) => setQueueForm({ ...queueForm, queue_type: e.target.value })}>
                    {['general_quality', 'language', 'tamil_quality', 'tanglish_quality', 'citation', 'retrieval', 'safety', 'privacy', 'memory', 'dataset_candidate', 'regression'].map((q) => <option key={q} value={q}>{q}</option>)}
                  </select>
                </label>
                <button type="submit">Create queue</button>
              </form>
              <div className="data-list">
                {(state.queues ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.name}</strong> — {item.queue_type}
                    <button onClick={() => selectQueue(item.public_id)}>Select</button>
                  </article>
                ))}
              </div>
              {selectedQueueId && (
                <>
                  <form className="inline-form training-form" onSubmit={submitAssign}>
                    <h4>Assign feedback to reviewer</h4>
                    <label>Feedback event public ID<input value={assignForm.feedback_event_public_id} onChange={(e) => setAssignForm({ ...assignForm, feedback_event_public_id: e.target.value })} /></label>
                    <label>Reviewer admin public ID<input value={assignForm.reviewer_admin_public_id} onChange={(e) => setAssignForm({ ...assignForm, reviewer_admin_public_id: e.target.value })} /></label>
                    <button type="submit">Assign</button>
                  </form>
                  <div className="data-list">
                    {(queueItems.items ?? []).map((item) => <article key={item.public_id}>{item.status} — priority {item.priority}</article>)}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Human Reviews' && (
            <>
              {!selectedEventId && <p className="notice">Select an event from the Feedback Events tab.</p>}
              {selectedEventId && (
                <>
                  <form className="inline-form training-form" onSubmit={submitReview}>
                    <h3>Submit human review</h3>
                    <label>Overall score (1-5)<input type="number" min="1" max="5" value={reviewForm.overall_score} onChange={(e) => setReviewForm({ ...reviewForm, overall_score: Number(e.target.value) })} /></label>
                    <label>Verdict
                      <select value={reviewForm.verdict} onChange={(e) => setReviewForm({ ...reviewForm, verdict: e.target.value })}>
                        {['valid_feedback', 'partially_valid', 'invalid_feedback', 'needs_second_review', 'privacy_blocked', 'safety_blocked', 'candidate_recommended', 'regression_recommended'].map((v) => <option key={v} value={v}>{v}</option>)}
                      </select>
                    </label>
                    <button type="submit">Submit review</button>
                  </form>
                  {reviewSummary && (
                    <div className="metric-grid">
                      <StatusCard label="Review count" value={reviewSummary.review_count} tone="neutral" />
                      <StatusCard label="Disagreement" value={reviewSummary.disagreement.status} tone={reviewSummary.disagreement.status === 'none' ? 'good' : 'warning'} />
                    </div>
                  )}
                  <div className="data-list">
                    {(reviews.items ?? []).map((item, index) => <article key={index}>{item.verdict} — overall {item.overall_score}</article>)}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Corrected Responses' && (
            <>
              {!selectedEventId && <p className="notice">Select an event from the Feedback Events tab.</p>}
              {selectedEventId && (
                <>
                  <form className="inline-form training-form" onSubmit={submitCorrection}>
                    <h3>Propose corrected response</h3>
                    <label>Corrected text<input value={correctionForm.corrected_response_text} onChange={(e) => setCorrectionForm({ ...correctionForm, corrected_response_text: e.target.value })} /></label>
                    <label>Language<input value={correctionForm.language} onChange={(e) => setCorrectionForm({ ...correctionForm, language: e.target.value })} /></label>
                    <button type="submit">Propose correction</button>
                  </form>
                  <div className="data-list">
                    {(corrections.items ?? []).map((item) => (
                      <article key={item.public_id}>
                        <strong>{item.public_id.slice(0, 8)}</strong> — {item.validation_status}
                        <div className="inline-form">
                          <button onClick={() => runValidateCorrection(item.public_id)}>Validate</button>
                          <button onClick={() => runRejectCorrection(item.public_id)}>Reject</button>
                        </div>
                      </article>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Privacy & Safety' && (
            <>
              {!selectedEventId && <p className="notice">Select an event from the Feedback Events tab.</p>}
              {selectedEventId && (
                <>
                  <h4>Privacy findings</h4>
                  <div className="data-list">
                    {(findings.privacy ?? []).map((item) => <article key={item.public_id}>{item.category} — {item.status}</article>)}
                  </div>
                  <h4>Safety findings</h4>
                  <div className="data-list">
                    {(findings.safety ?? []).map((item) => <article key={item.public_id}>{item.category} — {item.status}</article>)}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Dataset Candidates' && (
            <>
              <p className="notice">{DATASET_PIPELINE_NOTICE}</p>
              {!selectedEventId && <p className="notice">Select an event from the Feedback Events tab.</p>}
              {selectedEventId && (
                <form className="inline-form training-form" onSubmit={submitCandidate}>
                  <h3>Create dataset candidate</h3>
                  <label>Prompt text (reviewed, curated)<input value={candidateForm.prompt_text} onChange={(e) => setCandidateForm({ ...candidateForm, prompt_text: e.target.value })} /></label>
                  <label>Corrected response public ID<input value={candidateForm.corrected_response_public_id} onChange={(e) => setCandidateForm({ ...candidateForm, corrected_response_public_id: e.target.value })} /></label>
                  <button type="submit">Create candidate</button>
                </form>
              )}
              <div className="data-list">
                {(state.candidates ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.candidate_type}</strong> — {item.status}
                    <button onClick={() => selectCandidate(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Candidate Quality' && (
            <>
              {!selectedCandidateId && <p className="notice">Select a candidate from the Dataset Candidates tab.</p>}
              {selectedCandidateId && (
                <>
                  <button onClick={runValidateCandidate}>Run quality/privacy/safety/dedup/contamination checks</button>
                  <h4>Versions</h4>
                  <div className="data-list">
                    {(candidateVersions.items ?? []).map((item) => <article key={item.public_id}>v{item.version_number}: {item.change_reason}</article>)}
                  </div>
                  <h4>Issues</h4>
                  <div className="data-list">
                    {(candidateIssues.items ?? []).map((item) => <article key={item.public_id}>{item.issue_code} ({item.severity})</article>)}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Candidate Approvals' && (
            <>
              {!selectedCandidateId && <p className="notice">Select a candidate from the Dataset Candidates tab.</p>}
              {selectedCandidateId && (
                <div className="inline-form">
                  <button onClick={runApproveCandidate}>Approve</button>
                  <button onClick={runRejectCandidate}>Reject</button>
                  <button onClick={runQuarantineCandidate}>Quarantine</button>
                  <button onClick={runExportCandidate}>Export to dataset pipeline</button>
                </div>
              )}
            </>
          )}

          {tab === 'Regression Suites' && (
            <>
              <p className="notice">{REGRESSION_NOTICE}</p>
              <form className="inline-form training-form" onSubmit={submitSuite}>
                <h3>Create regression suite</h3>
                <label>Name<input value={suiteForm.name} onChange={(e) => setSuiteForm({ ...suiteForm, name: e.target.value })} /></label>
                <button type="submit">Create suite</button>
              </form>
              <div className="data-list">
                {(state.suites ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.name}</strong> — {item.lifecycle_status}
                    <button onClick={() => setSelectedSuiteId(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                  </article>
                ))}
              </div>
              {selectedSuiteId && (
                <>
                  <form className="inline-form training-form" onSubmit={submitFixture}>
                    <h4>Add regression fixture</h4>
                    <label>Category
                      <select value={fixtureForm.category} onChange={(e) => setFixtureForm({ ...fixtureForm, category: e.target.value })}>
                        {['language_regression', 'tamil_quality_regression', 'tanglish_regression', 'instruction_following_regression', 'citation_regression', 'retrieval_regression', 'safety_regression', 'memory_regression', 'privacy_regression', 'format_regression', 'repetition_regression'].map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </label>
                    <label>Input text<input value={fixtureForm.input_text} onChange={(e) => setFixtureForm({ ...fixtureForm, input_text: e.target.value })} /></label>
                    <label>Expected behavior<input value={fixtureForm.expected_behavior} onChange={(e) => setFixtureForm({ ...fixtureForm, expected_behavior: e.target.value })} /></label>
                    <label>Forbidden behavior<input value={fixtureForm.forbidden_behavior} onChange={(e) => setFixtureForm({ ...fixtureForm, forbidden_behavior: e.target.value })} /></label>
                    <button type="submit">Add fixture</button>
                  </form>
                  <div className="inline-form">
                    <button onClick={runValidateSuite}>Validate suite</button>
                    <button onClick={runActivateSuite}>Activate suite</button>
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Regression Runs' && (
            <>
              <p className="notice">{REGRESSION_NOTICE}</p>
              {!selectedSuiteId && <p className="notice">Select an active suite from the Regression Suites tab.</p>}
              {selectedSuiteId && (
                <>
                  <label>Inference assignment public ID<input value={assignmentPublicId} onChange={(e) => setAssignmentPublicId(e.target.value)} /></label>
                  <div className="inline-form">
                    <button onClick={() => runCreateRun(setRunAId)}>Create + execute run A</button>
                    <button onClick={() => runCreateRun(setRunBId)}>Create + execute run B</button>
                  </div>
                  <Pre value={runResult} />
                </>
              )}
            </>
          )}

          {tab === 'Model Comparisons' && (
            <>
              <div className="inline-form">
                <label>Run A public ID<input value={runAId} onChange={(e) => setRunAId(e.target.value)} /></label>
                <label>Run B public ID<input value={runBId} onChange={(e) => setRunBId(e.target.value)} /></label>
                <button onClick={runCompare}>Compare</button>
              </div>
              <Pre value={comparisonResult} />
            </>
          )}

          {tab === 'Improvement Reports' && (
            <>
              <p className="notice">Reports never expose raw feedback text -- only aggregate counts and rates.</p>
              <button onClick={runCreateReport}>Generate improvement report</button>
              <Pre value={reportResult} />
            </>
          )}

          {tab === 'Reproducibility' && (
            <>
              <p className="notice">The feedback manifest never includes raw comments, raw corrections, secrets, or paths -- checksums and configuration only.</p>
              <div className="inline-form">
                <button onClick={runGenerateManifest}>Generate/view manifest</button>
                <button onClick={runVerifyManifest}>Verify checksum</button>
              </div>
              <Pre value={manifestResult} />
              <Pre value={manifestVerification} />
            </>
          )}
        </section>
      </div>
    </section>
  )
}
