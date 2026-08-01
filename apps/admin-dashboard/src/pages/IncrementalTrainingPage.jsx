import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  acceptTrainingCheckpoint,
  acknowledgeNoTrainingExecution,
  acknowledgeTrainingAssessment,
  addTrainingCheckpointHumanReview,
  approvePromotionRequest,
  approveTrainingRunApproval,
  compareTrainingCheckpoint,
  contaminationRecheck,
  createPromotionRequest,
  createReplayPlan,
  createTrainingAssessment,
  createTrainingRunRequest,
  evaluateTrainingCheckpoint,
  finalizeTrainingReport,
  incrementalTrainingOverview,
  materializePromotionRequest,
  promotionRequest,
  requestTrainingRunApproval,
  reviewTrainingCandidate,
  runTrainingAssessment,
  startTrainingRun,
  submitPromotionRequest,
  submitTrainingRunRequest,
  trainingAssessmentCandidates,
  trainingAssessmentItems,
  trainingAssessments,
  trainingCheckpoint,
  trainingCheckpointAcceptances,
  trainingCheckpointComparisons,
  trainingCheckpointEvaluations,
  trainingCheckpointHumanReviews,
  trainingReports,
  trainingRun,
  trainingRunCheckpoints,
  trainingRunEvents,
  trainingRuns,
  transformTrainingItem,
  verifyTrainingCheckpoint,
} from '../services/api.js'

const NOTICE =
  'Phase 14 is a governance layer over the existing training infrastructure. Each stage below -- dataset promotion, training run approval, checkpoint acceptance -- is a separate, explicit Admin decision. This page never activates a production model and never creates a release; an accepted checkpoint can only ever register as a staging model candidate.'

const TABS = [
  'Overview', 'Assessments', 'Candidates', 'Dataset Promotion', 'Training Runs', 'Checkpoints',
  'Reports & Acceptance',
]

export default function IncrementalTrainingPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '' })
  const [panelError, setPanelError] = useState('')
  const [overview, setOverview] = useState({})

  const [experimentId, setExperimentId] = useState('')
  const [assessments, setAssessments] = useState({ items: [] })
  const [selectedAssessmentId, setSelectedAssessmentId] = useState('')
  const [assessmentItems, setAssessmentItems] = useState({ items: [] })

  const [transformForm, setTransformForm] = useState({
    itemId: '', transformation_type: 'instruction_response_pair', prompt_text: '',
    assistant_text: '', language: 'ta', source_checksum: '',
  })
  const [candidates, setCandidates] = useState({ items: [] })
  const [reviewForm, setReviewForm] = useState({ candidateId: '', decision: 'approved', reason: '' })
  const [recheckResult, setRecheckResult] = useState(null)

  const [replayForm, setReplayForm] = useState({ new_record_count: 10, new_data_ratio: 0.8 })
  const [promotionCandidateIds, setPromotionCandidateIds] = useState('')
  const [promotionId, setPromotionId] = useState('')
  const [promotionDetail, setPromotionDetail] = useState(null)

  const [runRequestForm, setRunRequestForm] = useState({
    training_strategy: 'continued_pretraining', configuration: '{}',
  })
  const [runRequestId, setRunRequestId] = useState('')
  const [runApprovalId, setRunApprovalId] = useState('')
  const [runs, setRuns] = useState({ items: [] })
  const [selectedRunId, setSelectedRunId] = useState('')
  const [runDetail, setRunDetail] = useState(null)
  const [runEvents, setRunEvents] = useState({ items: [] })
  const [runCheckpoints, setRunCheckpoints] = useState({ items: [] })

  const [checkpointId, setCheckpointId] = useState('')
  const [checkpointDetail, setCheckpointDetail] = useState(null)
  const [checkpointEvaluations, setCheckpointEvaluations] = useState({ items: [] })
  const [compareForm, setCompareForm] = useState({
    baseline_checkpoint_public_id: '', comparison_type: 'general_comparison',
  })
  const [comparisons, setComparisons] = useState({ items: [] })
  const [humanReviewForm, setHumanReviewForm] = useState({
    prompt_text: '', decision: 'pass', tamil_fluency: true, regression: false,
  })
  const [humanReviews, setHumanReviews] = useState({ items: [] })

  const [reportRunId, setReportRunId] = useState('')
  const [reportCheckpointId, setReportCheckpointId] = useState('')
  const [reports, setReports] = useState({ items: [] })
  const [acceptForm, setAcceptForm] = useState({
    checkpointId: '', reportId: '', decision: 'accepted_candidate', reason: '',
  })
  const [acceptances, setAcceptances] = useState({ items: [] })

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [overviewData, assessmentList, runList] = await Promise.all([
        incrementalTrainingOverview(), trainingAssessments(), trainingRuns(),
      ])
      setOverview(overviewData)
      setAssessments(assessmentList)
      setRuns(runList)
      setState({ loading: false, error: '' })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  function fail(error) { setPanelError(error.message) }

  async function submitCreateAssessment(event) {
    event.preventDefault()
    try {
      await createTrainingAssessment({ rag_sandbox_experiment_public_id: experimentId })
      setPanelError('')
      await load()
    } catch (error) { fail(error) }
  }

  async function loadAssessmentItems(id) {
    setSelectedAssessmentId(id)
    try {
      setAssessmentItems(await trainingAssessmentItems(id))
      setCandidates(await trainingAssessmentCandidates(id))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function runCheck() {
    try { await runTrainingAssessment(selectedAssessmentId); await loadAssessmentItems(selectedAssessmentId); await load() }
    catch (error) { fail(error) }
  }

  async function acknowledgeAssessment() {
    try { await acknowledgeTrainingAssessment(selectedAssessmentId); await load() }
    catch (error) { fail(error) }
  }

  async function submitTransform(event) {
    event.preventDefault()
    try {
      await transformTrainingItem(transformForm.itemId, {
        transformation_type: transformForm.transformation_type,
        prompt_text: transformForm.prompt_text, assistant_text: transformForm.assistant_text,
        language: transformForm.language, source_checksum: transformForm.source_checksum,
      })
      setPanelError('')
      await loadAssessmentItems(selectedAssessmentId)
    } catch (error) { fail(error) }
  }

  async function submitReview(event) {
    event.preventDefault()
    try {
      await reviewTrainingCandidate(reviewForm.candidateId, {
        decision: reviewForm.decision, reason: reviewForm.reason,
      })
      setPanelError('')
      await loadAssessmentItems(selectedAssessmentId)
    } catch (error) { fail(error) }
  }

  async function runRecheck() {
    try {
      const ids = (candidates.items ?? []).filter((c) => c.review_status === 'approved').map((c) => c.public_id)
      setRecheckResult(await contaminationRecheck(ids))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitReplayPlan(event) {
    event.preventDefault()
    try {
      await createReplayPlan(selectedAssessmentId, {
        new_record_count: Number(replayForm.new_record_count),
        new_data_ratio: Number(replayForm.new_data_ratio),
      })
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitPromotion(event) {
    event.preventDefault()
    try {
      const created = await createPromotionRequest(selectedAssessmentId, {
        candidate_public_ids: promotionCandidateIds.split(',').map((v) => v.trim()).filter(Boolean),
      })
      setPromotionId(created.public_id)
      setPromotionDetail(created)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function loadPromotion() {
    try { setPromotionDetail(await promotionRequest(promotionId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function submitPromotionForApproval() {
    try { setPromotionDetail(await submitPromotionRequest(promotionId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function approvePromotion() {
    try { setPromotionDetail(await approvePromotionRequest(promotionId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function materializePromotion() {
    try { setPromotionDetail(await materializePromotionRequest(promotionId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function submitRunRequest(event) {
    event.preventDefault()
    try {
      let configuration = {}
      try { configuration = JSON.parse(runRequestForm.configuration || '{}') }
      catch { throw new Error('Configuration must be valid JSON.') }
      const created = await createTrainingRunRequest(promotionId, {
        training_strategy: runRequestForm.training_strategy, configuration,
      })
      setRunRequestId(created.public_id)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitRunRequestForApproval() {
    try { await submitTrainingRunRequest(runRequestId); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function requestApproval() {
    try {
      const approval = await requestTrainingRunApproval(runRequestId)
      setRunApprovalId(approval.public_id)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function approveRun() {
    try { await approveTrainingRunApproval(runApprovalId); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function startRun() {
    try { await startTrainingRun(runApprovalId); setPanelError(''); await load() }
    catch (error) { fail(error) }
  }

  async function acknowledgeNoExecution() {
    try { await acknowledgeNoTrainingExecution(runApprovalId); setPanelError(''); await load() }
    catch (error) { fail(error) }
  }

  async function loadRunDetail(id) {
    setSelectedRunId(id)
    try {
      setRunDetail(await trainingRun(id))
      setRunEvents(await trainingRunEvents(id))
      setRunCheckpoints(await trainingRunCheckpoints(id))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function loadCheckpoint(id) {
    setCheckpointId(id)
    try {
      setCheckpointDetail(await trainingCheckpoint(id))
      setCheckpointEvaluations(await trainingCheckpointEvaluations(id))
      setComparisons(await trainingCheckpointComparisons(id))
      setHumanReviews(await trainingCheckpointHumanReviews(id))
      setAcceptances(await trainingCheckpointAcceptances(id))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function verifyCheckpoint() {
    try { setCheckpointDetail(await verifyTrainingCheckpoint(checkpointId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function evaluateCheckpoint() {
    try {
      const result = await evaluateTrainingCheckpoint(checkpointId)
      setCheckpointDetail(result.checkpoint)
      setCheckpointEvaluations({ items: result.evaluations })
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitCompare(event) {
    event.preventDefault()
    try {
      await compareTrainingCheckpoint(checkpointId, compareForm)
      setComparisons(await trainingCheckpointComparisons(checkpointId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitHumanReview(event) {
    event.preventDefault()
    try {
      await addTrainingCheckpointHumanReview(checkpointId, humanReviewForm)
      setHumanReviews(await trainingCheckpointHumanReviews(checkpointId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitFinalizeReport(event) {
    event.preventDefault()
    try {
      await finalizeTrainingReport(reportRunId, { checkpoint_public_id: reportCheckpointId })
      setReports(await trainingReports(reportRunId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitAccept(event) {
    event.preventDefault()
    try {
      const accepted = await acceptTrainingCheckpoint(acceptForm.checkpointId, {
        report_public_id: acceptForm.reportId, decision: acceptForm.decision,
        reason: acceptForm.reason,
      })
      setAcceptances({ items: [accepted] })
      setPanelError('')
      await load()
    } catch (error) { fail(error) }
  }

  if (state.loading) return <section className="notice">Loading incremental training…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Incremental Training</h2>
          <p className="notice">{NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Incremental training sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Assessments</h3>
          {(assessments.items ?? []).length === 0 && <article>None yet.</article>}
          {(assessments.items ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadAssessmentItems(item.public_id)}>
              <strong>{item.assessment_code}</strong>
              <span>{item.status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              <div className="metric-grid">
                <StatusCard label="Assessments awaiting review" value={overview.training_assessments_awaiting_review ?? 0} tone="neutral" />
                <StatusCard label="Candidates needing transformation" value={overview.training_candidates_needing_transformation ?? 0} tone="neutral" />
                <StatusCard label="Dataset promotions awaiting approval" value={overview.dataset_promotions_awaiting_approval ?? 0} tone="neutral" />
                <StatusCard label="Runs awaiting approval" value={overview.training_runs_awaiting_approval ?? 0} tone="neutral" />
                <StatusCard label="Runs in progress" value={overview.training_runs_in_progress ?? 0} tone="neutral" />
                <StatusCard label="Runs failed" value={overview.training_runs_failed ?? 0} tone={overview.training_runs_failed ? 'warning' : 'neutral'} />
                <StatusCard label="Checkpoints awaiting evaluation" value={overview.checkpoints_awaiting_evaluation ?? 0} tone="neutral" />
                <StatusCard label="Checkpoints with regression" value={overview.checkpoints_with_regression ?? 0} tone={overview.checkpoints_with_regression ? 'warning' : 'neutral'} />
                <StatusCard label="Checkpoints awaiting Admin acceptance" value={overview.checkpoints_awaiting_admin_acceptance ?? 0} tone="neutral" />
                <StatusCard label="Accepted model candidates (staging)" value={overview.accepted_model_candidates ?? 0} tone="neutral" />
              </div>
              <p className="notice">
                Pipeline: RAG sandbox acceptance → suitability assessment → candidate
                transformation &amp; review → replay plan → dataset promotion request →
                separate Admin approval → materialized dataset version → training run request
                → separate Admin approval → bounded execution → checkpoint verification &amp;
                evaluation → regression/forgetting comparison → human review → immutable report
                → separate Admin checkpoint acceptance → staging model candidate.
              </p>
            </>
          )}

          {tab === 'Assessments' && (
            <>
              <h3>Create a Training Suitability Assessment</h3>
              <form className="inline-form" onSubmit={submitCreateAssessment}>
                <input placeholder="Accepted RAG sandbox experiment public ID" value={experimentId}
                  onChange={(event) => setExperimentId(event.target.value)} required />
                <button type="submit">Create assessment</button>
              </form>
              <p className="notice">Selected: {selectedAssessmentId || '(select one from the list on the left)'}</p>
              {selectedAssessmentId && (
                <div className="inline-form">
                  <button onClick={runCheck}>Run suitability check</button>
                  <button onClick={acknowledgeAssessment}>Acknowledge results reviewed</button>
                </div>
              )}
              {(assessmentItems.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <div><strong>{item.record_category}</strong> — {item.suitability_status}</div>
                  <div className="notice">{item.reason}</div>
                  <div className="notice">Item ID: {item.public_id}</div>
                </article>
              ))}
            </>
          )}

          {tab === 'Candidates' && (
            <>
              <h3>Transform an Assessment Item into a Candidate</h3>
              <form className="inline-form" onSubmit={submitTransform}>
                <input placeholder="Assessment item public ID" value={transformForm.itemId}
                  onChange={(event) => setTransformForm({ ...transformForm, itemId: event.target.value })} required />
                <select value={transformForm.transformation_type}
                  onChange={(event) => setTransformForm({ ...transformForm, transformation_type: event.target.value })}>
                  <option value="clean_language_sample">Clean language sample</option>
                  <option value="question_answer_pair">Question/answer pair</option>
                  <option value="summary_pair">Summary pair</option>
                  <option value="translation_pair">Translation pair</option>
                  <option value="tanglish_normalization_pair">Tanglish normalization pair</option>
                  <option value="correction_pair">Correction pair</option>
                  <option value="instruction_response_pair">Instruction/response pair</option>
                  <option value="conversation_turn_sequence">Conversation turn sequence</option>
                </select>
                <input placeholder="Prompt text" value={transformForm.prompt_text}
                  onChange={(event) => setTransformForm({ ...transformForm, prompt_text: event.target.value })} />
                <input placeholder="Assistant text" value={transformForm.assistant_text}
                  onChange={(event) => setTransformForm({ ...transformForm, assistant_text: event.target.value })} />
                <input placeholder="Source checksum" value={transformForm.source_checksum}
                  onChange={(event) => setTransformForm({ ...transformForm, source_checksum: event.target.value })} required />
                <button type="submit">Transform</button>
              </form>

              <h3>Review a Candidate</h3>
              <form className="inline-form" onSubmit={submitReview}>
                <input placeholder="Candidate public ID" value={reviewForm.candidateId}
                  onChange={(event) => setReviewForm({ ...reviewForm, candidateId: event.target.value })} required />
                <select value={reviewForm.decision}
                  onChange={(event) => setReviewForm({ ...reviewForm, decision: event.target.value })}>
                  <option value="approved">Approve</option>
                  <option value="needs_revision">Needs revision</option>
                  <option value="rejected">Reject</option>
                </select>
                <input placeholder="Reason" value={reviewForm.reason}
                  onChange={(event) => setReviewForm({ ...reviewForm, reason: event.target.value })} required />
                <button type="submit">Submit review</button>
              </form>

              <div className="inline-form">
                <button onClick={runRecheck}>Recheck contamination for approved candidates</button>
              </div>
              {recheckResult && (
                <article>
                  <div>Blocking candidates: {recheckResult.blocking_candidate_ids.length === 0 ? 'none' : recheckResult.blocking_candidate_ids.join(', ')}</div>
                </article>
              )}

              {(candidates.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <div><strong>{item.transformation_type}</strong> — {item.review_status}</div>
                  <div className="notice">Candidate ID: {item.public_id}</div>
                </article>
              ))}
            </>
          )}

          {tab === 'Dataset Promotion' && (
            <>
              <h3>Replay Data Plan (optional)</h3>
              <form className="inline-form" onSubmit={submitReplayPlan}>
                <input type="number" placeholder="New record count" value={replayForm.new_record_count}
                  onChange={(event) => setReplayForm({ ...replayForm, new_record_count: event.target.value })} />
                <input type="number" step="0.05" placeholder="New data ratio (0-1)" value={replayForm.new_data_ratio}
                  onChange={(event) => setReplayForm({ ...replayForm, new_data_ratio: event.target.value })} />
                <button type="submit">Create replay plan</button>
              </form>

              <h3>Create Dataset Promotion Request</h3>
              <form className="inline-form" onSubmit={submitPromotion}>
                <input placeholder="Approved candidate public IDs, comma separated" value={promotionCandidateIds}
                  onChange={(event) => setPromotionCandidateIds(event.target.value)} required />
                <button type="submit">Create promotion request</button>
              </form>
              <div className="inline-form">
                <input placeholder="Promotion request public ID" value={promotionId}
                  onChange={(event) => setPromotionId(event.target.value)} />
                <button onClick={loadPromotion}>Load</button>
              </div>
              {promotionDetail && (
                <article>
                  <div><strong>Status: {promotionDetail.status}</strong></div>
                  <div className="notice">Dataset version: {promotionDetail.dataset_version_public_id ?? '(not yet materialized)'}</div>
                  <div className="inline-form">
                    <button onClick={submitPromotionForApproval}>Submit for approval</button>
                    <button onClick={approvePromotion}>Approve</button>
                    <button onClick={materializePromotion}>Materialize (build dataset version)</button>
                  </div>
                </article>
              )}
            </>
          )}

          {tab === 'Training Runs' && (
            <>
              <h3>Create a Training Run Request</h3>
              <p className="notice">Requires a materialized (status=ready) dataset promotion request.</p>
              <form className="inline-form" onSubmit={submitRunRequest}>
                <input placeholder="Promotion request public ID" value={promotionId}
                  onChange={(event) => setPromotionId(event.target.value)} required />
                <select value={runRequestForm.training_strategy}
                  onChange={(event) => setRunRequestForm({ ...runRequestForm, training_strategy: event.target.value })}>
                  <option value="incremental_sft">Incremental SFT</option>
                  <option value="continued_pretraining">Continued pretraining</option>
                  <option value="tokenizer_only_assessment">Tokenizer-only assessment</option>
                  <option value="no_training_rag_only">No training (RAG only)</option>
                </select>
                <textarea placeholder="Configuration JSON" value={runRequestForm.configuration}
                  onChange={(event) => setRunRequestForm({ ...runRequestForm, configuration: event.target.value })} />
                <button type="submit">Create run request</button>
              </form>
              {runRequestId && (
                <article>
                  <div className="notice">Run request: {runRequestId}</div>
                  <div className="inline-form">
                    <button onClick={submitRunRequestForApproval}>Submit for approval</button>
                    <button onClick={requestApproval}>Request approval</button>
                  </div>
                </article>
              )}
              {runApprovalId && (
                <article>
                  <div className="notice">Run approval: {runApprovalId}</div>
                  <div className="inline-form">
                    <button onClick={approveRun}>Approve</button>
                    <button onClick={startRun}>Start run (executable strategies)</button>
                    <button onClick={acknowledgeNoExecution}>Acknowledge no-execution strategy</button>
                  </div>
                </article>
              )}

              <h3>Runs</h3>
              {(runs.items ?? []).map((item) => (
                <button key={item.public_id} className="training-job-row" onClick={() => loadRunDetail(item.public_id)}>
                  <strong>{item.public_id.slice(0, 8)}</strong>
                  <span>{item.status}</span>
                </button>
              ))}
              {runDetail && (
                <article>
                  <div><strong>Status: {runDetail.status}</strong> — {runDetail.underlying_run_kind}</div>
                  <div className="notice">Training/validation loss: {runDetail.latest_training_loss} / {runDetail.latest_validation_loss}</div>
                  <h4>Events</h4>
                  {(runEvents.items ?? []).map((event) => (
                    <div key={event.public_id}>{event.event_type}: {event.summary}</div>
                  ))}
                  <h4>Checkpoints</h4>
                  {(runCheckpoints.items ?? []).map((checkpoint) => (
                    <button key={checkpoint.public_id} className="training-job-row" onClick={() => { loadCheckpoint(checkpoint.public_id); setTab('Checkpoints') }}>
                      <strong>{checkpoint.public_id.slice(0, 8)}</strong>
                      <span>{checkpoint.status}</span>
                    </button>
                  ))}
                </article>
              )}
            </>
          )}

          {tab === 'Checkpoints' && (
            <>
              <div className="inline-form">
                <input placeholder="Checkpoint public ID" value={checkpointId}
                  onChange={(event) => setCheckpointId(event.target.value)} />
                <button onClick={() => loadCheckpoint(checkpointId)}>Load</button>
                <button onClick={verifyCheckpoint}>Verify</button>
                <button onClick={evaluateCheckpoint}>Evaluate</button>
              </div>
              {checkpointDetail && (
                <article>
                  <div><strong>Status: {checkpointDetail.status}</strong></div>
                  <div className="notice">Step {checkpointDetail.step}, training loss {checkpointDetail.training_loss}, validation loss {checkpointDetail.validation_loss}</div>
                </article>
              )}

              <h4>Evaluations</h4>
              {(checkpointEvaluations.items ?? []).map((item) => (
                <div key={item.public_id}>{item.evaluation_type}: {item.result_status} (score {item.score})</div>
              ))}

              <h4>Compare Against a Baseline Checkpoint</h4>
              <form className="inline-form" onSubmit={submitCompare}>
                <input placeholder="Baseline checkpoint public ID" value={compareForm.baseline_checkpoint_public_id}
                  onChange={(event) => setCompareForm({ ...compareForm, baseline_checkpoint_public_id: event.target.value })} required />
                <select value={compareForm.comparison_type}
                  onChange={(event) => setCompareForm({ ...compareForm, comparison_type: event.target.value })}>
                  <option value="general_comparison">General comparison</option>
                  <option value="forgetting_check">Forgetting check (vs. parent)</option>
                </select>
                <button type="submit">Compare</button>
              </form>
              {(comparisons.items ?? []).map((item) => (
                <div key={item.public_id} className={item.result_status === 'major_regression' ? 'error-notice' : ''}>
                  {item.comparison_type}: {item.result_status}
                </div>
              ))}

              <h4>Human Review (bounded multilingual prompt set)</h4>
              <form className="inline-form" onSubmit={submitHumanReview}>
                <input placeholder="Prompt text" value={humanReviewForm.prompt_text}
                  onChange={(event) => setHumanReviewForm({ ...humanReviewForm, prompt_text: event.target.value })} required />
                <select value={humanReviewForm.decision}
                  onChange={(event) => setHumanReviewForm({ ...humanReviewForm, decision: event.target.value })}>
                  <option value="pass">Pass</option>
                  <option value="pass_with_conditions">Pass with conditions</option>
                  <option value="fail">Fail</option>
                  <option value="needs_more_testing">Needs more testing</option>
                </select>
                <button type="submit">Submit review</button>
              </form>
              {(humanReviews.items ?? []).map((item) => (
                <div key={item.public_id}>{item.decision}: {item.prompt_text}</div>
              ))}
            </>
          )}

          {tab === 'Reports & Acceptance' && (
            <>
              <h3>Finalize an Immutable Training Report</h3>
              <form className="inline-form" onSubmit={submitFinalizeReport}>
                <input placeholder="Run public ID" value={reportRunId}
                  onChange={(event) => setReportRunId(event.target.value)} required />
                <input placeholder="Checkpoint public ID for report" value={reportCheckpointId}
                  onChange={(event) => setReportCheckpointId(event.target.value)} required />
                <button type="submit">Finalize report</button>
              </form>
              {(reports.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <div><strong>v{item.report_version}: {item.checkpoint_recommendation}</strong> (advisory only)</div>
                  <div className="notice">Report ID: {item.public_id}</div>
                </article>
              ))}

              <h3>Admin Checkpoint Acceptance</h3>
              <p className="notice">A major_regression comparison result always blocks acceptance and cannot be overridden here.</p>
              <form className="inline-form" onSubmit={submitAccept}>
                <input placeholder="Checkpoint public ID to accept" value={acceptForm.checkpointId}
                  onChange={(event) => setAcceptForm({ ...acceptForm, checkpointId: event.target.value })} required />
                <input placeholder="Report public ID" value={acceptForm.reportId}
                  onChange={(event) => setAcceptForm({ ...acceptForm, reportId: event.target.value })} required />
                <select value={acceptForm.decision}
                  onChange={(event) => setAcceptForm({ ...acceptForm, decision: event.target.value })}>
                  <option value="accepted_candidate">Accept as candidate</option>
                  <option value="accepted_with_conditions">Accept with conditions</option>
                  <option value="rejected">Reject</option>
                  <option value="needs_more_testing">Needs more testing</option>
                </select>
                <input placeholder="Reason" value={acceptForm.reason}
                  onChange={(event) => setAcceptForm({ ...acceptForm, reason: event.target.value })} required />
                <button type="submit">Record decision</button>
              </form>
              {(acceptances.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <div><strong>{item.decision}</strong></div>
                  <div className="notice">
                    {item.model_candidate_public_id
                      ? `Registered as staging model candidate: ${item.model_candidate_public_id}`
                      : 'No model candidate registered.'}
                  </div>
                </article>
              ))}
            </>
          )}
        </section>
      </div>
    </section>
  )
}
