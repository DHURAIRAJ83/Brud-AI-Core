import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  activateModelRelease,
  activateRagReleaseCandidate,
  approveModelRelease,
  approveRagPromotion,
  assessApiAbuseReadiness,
  assessBackupEncryption,
  assessDeploymentReadiness,
  buildRagReleaseCandidate,
  checkBackupArtifactSecurity,
  checkBackupReadiness,
  checkReleaseCandidateArtifacts,
  checkRestoreReadiness,
  compileReadinessReport,
  createModelReleaseRequest,
  createRagPromotionRequest,
  createProductionRegressionRun,
  createProductionRollbackPlan,
  encryptLatestBackup,
  executeModelCanary,
  executeProductionRegressionBatch,
  finalizeProductionRegressionRun,
  latestReadinessReport,
  modelReleaseEligibility,
  modelReleaseRequest,
  modelReleaseRequests,
  productionReadinessOverview,
  productionRagEligibility,
  productionSystemHealth,
  ragPromotionRequest,
  ragPromotionRequests,
  ragReleaseCandidate,
  ragReleaseCandidates,
  rejectModelReleaseRequest,
  requestModelReleaseApproval,
  requestRagPromotionApproval,
  rollbackModelRelease,
  rollbackRagReleaseCandidate,
  startModelCanary,
  stopModelCanary,
  submitAcceptanceReview,
  submitModelReleaseRequest,
  submitRagPromotionRequest,
  validateModelReleaseRequest,
  validateRagReleaseCandidate,
  validateProductionRollbackPlan,
  verifyEncryptedRestore,
  scanBackupSidecarFiles,
  verifySecretRedaction,
} from '../services/api.js'

const NOTICE =
  'Phase 15 is a governance layer over the existing RAG and model-release infrastructure. Production RAG promotion and model release are separate workflows, each requiring its own build/validation, its own Admin approval, and its own activation. This page never bypasses an earlier approval and never silently activates production.'

const TABS = [
  'Overview', 'RAG Promotion', 'RAG Candidates', 'Model Release', 'Canary & Activation',
  'Artifact Security', 'API Abuse & Secrets', 'Backup & Deployment', 'Regression',
  'Readiness Report & Acceptance',
]

function tabFromHash() {
  const queryIndex = window.location.hash.indexOf('?')
  if (queryIndex === -1) return 'Overview'
  const requested = new URLSearchParams(window.location.hash.slice(queryIndex + 1)).get('tab')
  return requested && TABS.includes(requested) ? requested : 'Overview'
}

export default function ProductionReadinessPage() {
  // The active sub-tab is encoded into the URL hash (alongside the
  // top-level page name App.jsx already writes there) so a hard refresh
  // on, say, "Model Release" returns to that tab instead of always
  // resetting to "Overview".
  const [tab, setTab] = useState(tabFromHash)
  useEffect(() => {
    const pageName = window.location.hash.slice(1).split('?')[0]
    const params = new URLSearchParams()
    params.set('tab', tab)
    window.history.replaceState(null, '', `#${pageName}?${params.toString()}`)
  }, [tab])
  const [state, setState] = useState({ loading: true, error: '' })
  const [panelError, setPanelError] = useState('')
  const [overview, setOverview] = useState({})

  const [ragExperimentId, setRagExperimentId] = useState('')
  const [ragEligibility, setRagEligibility] = useState(null)
  const [ragPromotionForm, setRagPromotionForm] = useState({
    rag_sandbox_experiment_public_id: '', knowledge_space_public_id: '',
  })
  const [ragPromotions, setRagPromotions] = useState({ items: [] })
  const [selectedPromotionId, setSelectedPromotionId] = useState('')
  const [promotionDetail, setPromotionDetail] = useState(null)
  const [ragApprovalId, setRagApprovalId] = useState('')

  const [ragCandidateId, setRagCandidateId] = useState('')
  const [ragCandidateDetail, setRagCandidateDetail] = useState(null)
  const [promotionCandidates, setPromotionCandidates] = useState({ items: [] })

  const [checkpointId, setCheckpointId] = useState('')
  const [modelEligibility, setModelEligibility] = useState(null)
  const [releaseForm, setReleaseForm] = useState({
    incremental_training_checkpoint_public_id: '', model_release_family_public_id: '',
  })
  const [releaseRequests, setReleaseRequests] = useState({ items: [] })
  const [selectedReleaseId, setSelectedReleaseId] = useState('')
  const [releaseDetail, setReleaseDetail] = useState(null)
  const [modelApprovalId, setModelApprovalId] = useState('')

  const [assignmentId, setAssignmentId] = useState('')
  const [rollbackPlanForm, setRollbackPlanForm] = useState({
    target_type: 'model', current_active_version: '', rollback_steps: '',
  })
  const [rollbackPlanId, setRollbackPlanId] = useState('')
  const [canaryReleaseId, setCanaryReleaseId] = useState('')

  const [artifactCandidateId, setArtifactCandidateId] = useState('')
  const [artifactResults, setArtifactResults] = useState(null)

  const [abuseResult, setAbuseResult] = useState(null)
  const [redactionResult, setRedactionResult] = useState(null)
  const [backupSidecarScanResult, setBackupSidecarScanResult] = useState(null)

  const [backupResult, setBackupResult] = useState(null)
  const [restoreResult, setRestoreResult] = useState(null)
  const [backupEncryptionResult, setBackupEncryptionResult] = useState(null)
  const [encryptBackupResult, setEncryptBackupResult] = useState(null)
  const [encryptedRestoreResult, setEncryptedRestoreResult] = useState(null)
  const [deploymentResult, setDeploymentResult] = useState(null)
  const [healthResult, setHealthResult] = useState(null)

  const [regressionBatchPlan, setRegressionBatchPlan] = useState('[]')
  const [regressionRunId, setRegressionRunId] = useState('')
  const [regressionBatchForm, setRegressionBatchForm] = useState({
    batch_name: '', test_paths: '',
  })

  const [report, setReport] = useState(null)
  const [reviewForm, setReviewForm] = useState({ decision: 'accepted', reason: '' })

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [overviewData, promotions, releases] = await Promise.all([
        productionReadinessOverview(), ragPromotionRequests(), modelReleaseRequests(),
      ])
      setOverview(overviewData)
      setRagPromotions(promotions)
      setReleaseRequests(releases)
      setState({ loading: false, error: '' })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  function fail(error) { setPanelError(error.message) }

  async function checkRagEligibility() {
    try { setRagEligibility(await productionRagEligibility(ragExperimentId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function submitCreateRagPromotion(event) {
    event.preventDefault()
    try {
      await createRagPromotionRequest(ragPromotionForm)
      setPanelError('')
      await load()
    } catch (error) { fail(error) }
  }

  async function loadPromotion(id) {
    setSelectedPromotionId(id)
    try {
      setPromotionDetail(await ragPromotionRequest(id))
      setPromotionCandidates(await ragReleaseCandidates(id))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitRagPromotion() {
    try { setPromotionDetail(await submitRagPromotionRequest(selectedPromotionId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function requestRagApproval() {
    try {
      const approval = await requestRagPromotionApproval(selectedPromotionId)
      setRagApprovalId(approval.public_id)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function approveRagPromotionRequest() {
    try {
      setPromotionDetail(await approveRagPromotion(ragApprovalId))
      setPanelError('')
      await loadPromotion(selectedPromotionId)
    } catch (error) { fail(error) }
  }

  async function buildCandidate() {
    try {
      const candidate = await buildRagReleaseCandidate(selectedPromotionId)
      setRagCandidateId(candidate.public_id)
      setPromotionCandidates(await ragReleaseCandidates(selectedPromotionId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function loadRagCandidate(id) {
    setRagCandidateId(id)
    try { setRagCandidateDetail(await ragReleaseCandidate(id)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function validateCandidate() {
    try {
      const result = await validateRagReleaseCandidate(ragCandidateId)
      setRagCandidateDetail(result.candidate)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function activateCandidate() {
    try {
      await activateRagReleaseCandidate(ragCandidateId)
      setRagCandidateDetail(await ragReleaseCandidate(ragCandidateId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function rollbackCandidate() {
    try {
      await rollbackRagReleaseCandidate(ragCandidateId)
      setRagCandidateDetail(await ragReleaseCandidate(ragCandidateId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function checkModelEligibility() {
    try { setModelEligibility(await modelReleaseEligibility(checkpointId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function submitCreateReleaseRequest(event) {
    event.preventDefault()
    try {
      await createModelReleaseRequest(releaseForm)
      setPanelError('')
      await load()
    } catch (error) { fail(error) }
  }

  async function loadReleaseRequest(id) {
    setSelectedReleaseId(id)
    try { setReleaseDetail(await modelReleaseRequest(id)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function submitReleaseRequest() {
    try {
      setReleaseDetail(await submitModelReleaseRequest(selectedReleaseId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function validateReleaseRequest() {
    try {
      setReleaseDetail(await validateModelReleaseRequest(selectedReleaseId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function requestModelApproval() {
    try {
      const approval = await requestModelReleaseApproval(selectedReleaseId)
      setModelApprovalId(approval.public_id)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function approveModelReleaseRequest() {
    try {
      await approveModelRelease(modelApprovalId)
      setReleaseDetail(await modelReleaseRequest(selectedReleaseId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function rejectReleaseRequest() {
    try {
      setReleaseDetail(await rejectModelReleaseRequest(selectedReleaseId))
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitCreateRollbackPlan(event) {
    event.preventDefault()
    try {
      const plan = await createProductionRollbackPlan({
        target_type: rollbackPlanForm.target_type,
        current_active_version: rollbackPlanForm.current_active_version || null,
        rollback_steps: rollbackPlanForm.rollback_steps
          .split('\n')
          .map((step) => step.trim())
          .filter((step) => step.length > 0),
      })
      setRollbackPlanId(plan.public_id)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function validatePlan() {
    try { await validateProductionRollbackPlan(rollbackPlanId); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function startCanary() {
    try {
      await startModelCanary(canaryReleaseId, { assignment_public_id: assignmentId, percentage: 100, max_request_count: 10 })
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function executeCanary() {
    try {
      await executeModelCanary(canaryReleaseId, {
        assignment_public_id: assignmentId, fixture_prompts: ['hello', 'வணக்கம்'],
      })
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function stopCanary() {
    try {
      await stopModelCanary(canaryReleaseId, { assignment_public_id: assignmentId, reason: 'admin_stop' })
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function activateRelease() {
    try {
      await activateModelRelease(canaryReleaseId, {
        assignment_public_id: assignmentId, rollback_plan_public_id: rollbackPlanId,
        explicit_activation_confirmed: true,
      })
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function rollbackRelease() {
    try {
      await rollbackModelRelease(canaryReleaseId, {
        assignment_public_id: assignmentId, rollback_plan_public_id: rollbackPlanId,
        reason: 'admin-initiated rollback',
      })
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function checkArtifactSecurity() {
    try { setArtifactResults(await checkReleaseCandidateArtifacts(artifactCandidateId)); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function checkBackupArtifacts() {
    try { setArtifactResults({ items: [await checkBackupArtifactSecurity()] }); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runAbuseCheck() {
    try { setAbuseResult(await assessApiAbuseReadiness()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runRedactionCheck() {
    try { setRedactionResult(await verifySecretRedaction()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runBackupSidecarScan() {
    try { setBackupSidecarScanResult(await scanBackupSidecarFiles()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runBackupCheck() {
    try { setBackupResult(await checkBackupReadiness()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runRestoreCheck() {
    try { setRestoreResult(await checkRestoreReadiness()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runBackupEncryptionAssessment() {
    try { setBackupEncryptionResult(await assessBackupEncryption()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runEncryptLatestBackup() {
    try { setEncryptBackupResult(await encryptLatestBackup()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runVerifyEncryptedRestore() {
    try { setEncryptedRestoreResult(await verifyEncryptedRestore()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runDeploymentAssessment() {
    try { setDeploymentResult(await assessDeploymentReadiness()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function runHealthSnapshot() {
    try { setHealthResult(await productionSystemHealth()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function submitCreateRegressionRun(event) {
    event.preventDefault()
    try {
      let batchPlan = []
      try { batchPlan = JSON.parse(regressionBatchPlan || '[]') }
      catch { throw new Error('Batch plan must be valid JSON.') }
      const run = await createProductionRegressionRun({ batch_plan: batchPlan })
      setRegressionRunId(run.public_id)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function submitExecuteBatch(event) {
    event.preventDefault()
    try {
      await executeProductionRegressionBatch(regressionRunId, {
        batch_name: regressionBatchForm.batch_name,
        test_paths: regressionBatchForm.test_paths.split(',').map((s) => s.trim()).filter(Boolean),
      })
      setPanelError('')
    } catch (error) { fail(error) }
  }

  async function finalizeRun() {
    try { await finalizeProductionRegressionRun(regressionRunId); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function compileReport() {
    try { setReport(await compileReadinessReport()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function loadLatestReport() {
    try { setReport(await latestReadinessReport()); setPanelError('') }
    catch (error) { fail(error) }
  }

  async function submitReview(event) {
    event.preventDefault()
    try {
      await submitAcceptanceReview(report.public_id, reviewForm)
      setPanelError('')
    } catch (error) { fail(error) }
  }

  if (state.loading) return <section className="notice">Loading production readiness…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Production Readiness</h2>
          <p className="notice">{NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Production readiness sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Promotions / Releases</h3>
          {(ragPromotions.items ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadPromotion(item.public_id)}>
              <strong>{item.promotion_code}</strong>
              <span>{item.status}</span>
            </button>
          ))}
          {(releaseRequests.items ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadReleaseRequest(item.public_id)}>
              <strong>{item.request_code}</strong>
              <span>{item.status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              <div className="metric-grid">
                <StatusCard label="RAG promotions awaiting approval" value={overview.rag_promotions_awaiting_approval ?? 0} tone="neutral" />
                <StatusCard label="RAG candidates awaiting validation" value={overview.rag_candidates_awaiting_validation ?? 0} tone="neutral" />
                <StatusCard label="RAG activations pending" value={overview.rag_activations_pending ?? 0} tone="neutral" />
                <StatusCard label="Model releases awaiting validation" value={overview.model_releases_awaiting_validation ?? 0} tone="neutral" />
                <StatusCard label="Model releases awaiting approval" value={overview.model_releases_awaiting_approval ?? 0} tone="neutral" />
                <StatusCard label="Canaries running" value={overview.canaries_running ?? 0} tone="neutral" />
                <StatusCard label="Activation failures" value={overview.activation_failures ?? 0} tone={overview.activation_failures ? 'warning' : 'neutral'} />
                <StatusCard label="Rollback readiness failures" value={overview.rollback_readiness_failures ?? 0} tone={overview.rollback_readiness_failures ? 'warning' : 'neutral'} />
                <StatusCard label="Artifact security failures" value={overview.artifact_security_failures ?? 0} tone={overview.artifact_security_failures ? 'warning' : 'neutral'} />
                <StatusCard label="Backups out of date" value={overview.backups_out_of_date ?? 0} tone={overview.backups_out_of_date ? 'warning' : 'neutral'} />
                <StatusCard label="Backups not encrypted" value={overview.backups_not_encrypted ?? 0} tone={overview.backups_not_encrypted ? 'warning' : 'neutral'} />
                <StatusCard label="Regression batches failing" value={overview.regression_batches_failing ?? 0} tone={overview.regression_batches_failing ? 'warning' : 'neutral'} />
                <StatusCard label="Readiness reports awaiting acceptance" value={overview.readiness_reports_awaiting_acceptance ?? 0} tone="neutral" />
              </div>
              <p className="notice">
                RAG track: accepted RAG sandbox report → production RAG eligibility → promotion
                request → separate Admin approval → candidate build → validation → activation
                (with automatic rollback on a failed post-activation check).
                Model track: accepted Phase 14 checkpoint → eligibility → release request →
                validation → separate Admin approval → optional canary → activation (requires a
                verified rollback plan) → optional rollback.
              </p>
            </>
          )}

          {tab === 'RAG Promotion' && (
            <>
              <h3>Check Production RAG Eligibility</h3>
              <div className="inline-form">
                <input placeholder="Accepted RAG sandbox experiment public ID" value={ragExperimentId}
                  onChange={(event) => setRagExperimentId(event.target.value)} />
                <button onClick={checkRagEligibility}>Check eligibility</button>
              </div>
              {ragEligibility && (
                <article className={ragEligibility.eligible ? '' : 'error-notice'}>
                  <div><strong>Eligible: {String(ragEligibility.eligible)}</strong></div>
                  {(ragEligibility.blocking_reasons ?? []).map((reason) => <div key={reason}>{reason}</div>)}
                </article>
              )}

              <h3>Create a Production RAG Promotion Request</h3>
              <form className="inline-form" onSubmit={submitCreateRagPromotion}>
                <input placeholder="RAG sandbox experiment public ID" value={ragPromotionForm.rag_sandbox_experiment_public_id}
                  onChange={(event) => setRagPromotionForm({ ...ragPromotionForm, rag_sandbox_experiment_public_id: event.target.value })} required />
                <input placeholder="Knowledge space public ID" value={ragPromotionForm.knowledge_space_public_id}
                  onChange={(event) => setRagPromotionForm({ ...ragPromotionForm, knowledge_space_public_id: event.target.value })} required />
                <button type="submit">Create request</button>
              </form>

              {promotionDetail && (
                <article>
                  <div><strong>Status: {promotionDetail.status}</strong></div>
                  <div className="notice">Promotion ID: {promotionDetail.public_id}</div>
                  <div className="inline-form">
                    <button onClick={submitRagPromotion}>Submit for review</button>
                    <button onClick={requestRagApproval}>Request approval</button>
                    <button onClick={buildCandidate}>Build release candidate</button>
                  </div>
                  {ragApprovalId && (
                    <div className="inline-form">
                      <div className="notice">Approval: {ragApprovalId}</div>
                      <button onClick={approveRagPromotionRequest}>Approve</button>
                    </div>
                  )}
                  <h4>Candidates</h4>
                  {(promotionCandidates.items ?? []).map((item) => (
                    <button key={item.public_id} className="training-job-row" onClick={() => { loadRagCandidate(item.public_id); setTab('RAG Candidates') }}>
                      <strong>{item.public_id.slice(0, 8)}</strong>
                      <span>{item.status}</span>
                    </button>
                  ))}
                </article>
              )}
            </>
          )}

          {tab === 'RAG Candidates' && (
            <>
              <div className="inline-form">
                <input placeholder="RAG release candidate public ID" value={ragCandidateId}
                  onChange={(event) => setRagCandidateId(event.target.value)} />
                <button onClick={() => loadRagCandidate(ragCandidateId)}>Load</button>
                <button onClick={validateCandidate}>Validate</button>
                <button onClick={activateCandidate}>Activate</button>
                <button onClick={rollbackCandidate}>Rollback to previous</button>
              </div>
              {ragCandidateDetail && (
                <article>
                  <div><strong>Status: {ragCandidateDetail.status}</strong></div>
                  <div className="notice">Production visible: {String(Boolean(ragCandidateDetail.production_visible))}</div>
                  <div className="notice">Index checksum: {ragCandidateDetail.index_checksum_sha256}</div>
                </article>
              )}
              <p className="notice">Validation runs structural checks only; activation runs real post-activation retrieval smoke checks and rolls back automatically if they fail.</p>
            </>
          )}

          {tab === 'Model Release' && (
            <>
              <h3>Check Model Release Eligibility</h3>
              <div className="inline-form">
                <input placeholder="Accepted Phase 14 checkpoint public ID" value={checkpointId}
                  onChange={(event) => setCheckpointId(event.target.value)} />
                <button onClick={checkModelEligibility}>Check eligibility</button>
              </div>
              {modelEligibility && (
                <article className={modelEligibility.eligible ? '' : 'error-notice'}>
                  <div><strong>Eligible: {String(modelEligibility.eligible)}</strong></div>
                  {(modelEligibility.blocking_reasons ?? []).map((reason) => <div key={reason}>{reason}</div>)}
                </article>
              )}

              <h3>Create a Production Model Release Request</h3>
              <form className="inline-form" onSubmit={submitCreateReleaseRequest}>
                <input placeholder="Checkpoint public ID" value={releaseForm.incremental_training_checkpoint_public_id}
                  onChange={(event) => setReleaseForm({ ...releaseForm, incremental_training_checkpoint_public_id: event.target.value })} required />
                <input placeholder="Model release family public ID (optional)" value={releaseForm.model_release_family_public_id}
                  onChange={(event) => setReleaseForm({ ...releaseForm, model_release_family_public_id: event.target.value })} />
                <button type="submit">Create request</button>
              </form>

              {releaseDetail && (
                <article>
                  <div><strong>Status: {releaseDetail.status}</strong></div>
                  <div className="notice">Request ID: {releaseDetail.public_id}</div>
                  <div className="inline-form">
                    <button onClick={submitReleaseRequest}>Submit for review</button>
                    <button onClick={validateReleaseRequest}>Validate</button>
                    <button onClick={requestModelApproval}>Request approval</button>
                    <button onClick={rejectReleaseRequest}>Reject</button>
                  </div>
                  {modelApprovalId && (
                    <div className="inline-form">
                      <div className="notice">Approval: {modelApprovalId}</div>
                      <button onClick={approveModelReleaseRequest}>Approve</button>
                    </div>
                  )}
                </article>
              )}
            </>
          )}

          {tab === 'Canary & Activation' && (
            <>
              <p className="notice">Activation always requires an already-approved release request, an already-approved inference_model_assignment (built via the existing Inference Runtime page), and a verified rollback plan.</p>
              <h3>Rollback Plan</h3>
              <form className="inline-form" onSubmit={submitCreateRollbackPlan}>
                <select value={rollbackPlanForm.target_type}
                  onChange={(event) => setRollbackPlanForm({ ...rollbackPlanForm, target_type: event.target.value })}>
                  <option value="model">model</option>
                  <option value="rag">rag</option>
                </select>
                <input placeholder="Current active version public ID (for rollback target)" value={rollbackPlanForm.current_active_version}
                  onChange={(event) => setRollbackPlanForm({ ...rollbackPlanForm, current_active_version: event.target.value })} />
                <textarea placeholder="Rollback steps (one per line)" value={rollbackPlanForm.rollback_steps}
                  onChange={(event) => setRollbackPlanForm({ ...rollbackPlanForm, rollback_steps: event.target.value })} />
                <button type="submit">Create plan</button>
              </form>
              {rollbackPlanId && (
                <div className="inline-form">
                  <div className="notice">Plan: {rollbackPlanId}</div>
                  <button onClick={validatePlan}>Validate plan</button>
                </div>
              )}

              <h3>Canary / Activation</h3>
              <div className="inline-form">
                <input placeholder="Release request public ID" value={canaryReleaseId}
                  onChange={(event) => setCanaryReleaseId(event.target.value)} />
                <input placeholder="Assignment public ID" value={assignmentId}
                  onChange={(event) => setAssignmentId(event.target.value)} />
              </div>
              <div className="inline-form">
                <button onClick={startCanary}>Start canary</button>
                <button onClick={executeCanary}>Execute canary</button>
                <button onClick={stopCanary}>Stop canary</button>
                <button onClick={activateRelease}>Activate</button>
                <button onClick={rollbackRelease}>Rollback</button>
              </div>
            </>
          )}

          {tab === 'Artifact Security' && (
            <>
              <div className="inline-form">
                <input placeholder="Model release candidate public ID" value={artifactCandidateId}
                  onChange={(event) => setArtifactCandidateId(event.target.value)} />
                <button onClick={checkArtifactSecurity}>Check candidate artifacts</button>
                <button onClick={checkBackupArtifacts}>Check backup file security</button>
              </div>
              {(artifactResults?.items ?? []).map((item) => (
                <article key={item.public_id} className={item.result_status === 'failed' ? 'error-notice' : ''}>
                  <div><strong>{item.artifact_type}: {item.result_status}</strong></div>
                  {(item.findings ?? []).map((finding) => <div key={finding}>{finding}</div>)}
                </article>
              ))}
            </>
          )}

          {tab === 'API Abuse & Secrets' && (
            <>
              <div className="inline-form">
                <button onClick={runAbuseCheck}>Run API-abuse readiness check</button>
                <button onClick={runRedactionCheck}>Verify secret redaction</button>
                <button onClick={runBackupSidecarScan}>Scan backup sidecar files for secrets</button>
              </div>
              {abuseResult && (
                <article className={abuseResult.result_status === 'failed' ? 'error-notice' : ''}>
                  <div><strong>API abuse readiness: {abuseResult.result_status}</strong></div>
                  {(abuseResult.findings ?? []).map((finding) => <div key={finding}>{finding}</div>)}
                </article>
              )}
              {redactionResult && (
                <article className={redactionResult.result_status === 'failed' ? 'error-notice' : ''}>
                  <div><strong>Secret redaction: {redactionResult.result_status}</strong></div>
                </article>
              )}
              {backupSidecarScanResult && (
                <article className={backupSidecarScanResult.result_status === 'failed' ? 'error-notice' : ''}>
                  <div><strong>Backup sidecar secret scan: {backupSidecarScanResult.result_status}</strong></div>
                  {backupSidecarScanResult.findings.map((finding) => <div key={finding}>{finding}</div>)}
                </article>
              )}
            </>
          )}

          {tab === 'Backup & Deployment' && (
            <>
              <div className="inline-form">
                <button onClick={runBackupCheck}>Check backup readiness</button>
                <button onClick={runRestoreCheck}>Check restore readiness (isolated drill)</button>
                <button onClick={runBackupEncryptionAssessment}>Assess backup encryption</button>
                <button onClick={runEncryptLatestBackup}>Encrypt latest backup</button>
                <button onClick={runVerifyEncryptedRestore}>Verify encrypted restore (isolated drill)</button>
                <button onClick={runDeploymentAssessment}>Assess deployment readiness</button>
                <button onClick={runHealthSnapshot}>System health snapshot</button>
              </div>
              {backupResult && <article><div><strong>Backup: {backupResult.result_status}</strong></div></article>}
              {restoreResult && <article><div><strong>Restore drill: {restoreResult.result_status}</strong></div></article>}
              {backupEncryptionResult && (
                <article className={backupEncryptionResult.result_status === 'not_encrypted' ? 'error-notice' : ''}>
                  <div><strong>Backup encryption: {backupEncryptionResult.result_status}</strong></div>
                  {backupEncryptionResult.findings.map((finding) => <div key={finding}>{finding}</div>)}
                </article>
              )}
              {encryptBackupResult && (
                <article><div><strong>Encrypted: {encryptBackupResult.encrypted_filename}</strong></div></article>
              )}
              {encryptedRestoreResult && (
                <article className={encryptedRestoreResult.result_status === 'blocked' ? 'error-notice' : ''}>
                  <div><strong>Encrypted restore drill: {encryptedRestoreResult.result_status}</strong></div>
                  {encryptedRestoreResult.findings.map((finding) => <div key={finding}>{finding}</div>)}
                </article>
              )}
              {deploymentResult && (
                <article className={deploymentResult.result_status === 'blocked' ? 'error-notice' : ''}>
                  <div><strong>Deployment readiness: {deploymentResult.result_status}</strong></div>
                  {(deploymentResult.blocking_reasons ?? []).map((reason) => <div key={reason}>{reason}</div>)}
                </article>
              )}
              {healthResult && <article><div><strong>System health: {healthResult.overall_status}</strong></div></article>}
            </>
          )}

          {tab === 'Regression' && (
            <>
              <h3>Create a Regression Run</h3>
              <form className="inline-form" onSubmit={submitCreateRegressionRun}>
                <textarea placeholder='Batch plan JSON, e.g. [{"batch_name":"backend","command":["tests/backend/test_x.py"]}]'
                  value={regressionBatchPlan} onChange={(event) => setRegressionBatchPlan(event.target.value)} />
                <button type="submit">Create run</button>
              </form>
              {regressionRunId && (
                <>
                  <div className="notice">Run: {regressionRunId}</div>
                  <form className="inline-form" onSubmit={submitExecuteBatch}>
                    <input placeholder="Batch name" value={regressionBatchForm.batch_name}
                      onChange={(event) => setRegressionBatchForm({ ...regressionBatchForm, batch_name: event.target.value })} required />
                    <input placeholder="Test paths, comma separated" value={regressionBatchForm.test_paths}
                      onChange={(event) => setRegressionBatchForm({ ...regressionBatchForm, test_paths: event.target.value })} required />
                    <button type="submit">Execute batch</button>
                  </form>
                  <button onClick={finalizeRun}>Finalize run</button>
                </>
              )}
            </>
          )}

          {tab === 'Readiness Report & Acceptance' && (
            <>
              <div className="inline-form">
                <button onClick={compileReport}>Compile new readiness report</button>
                <button onClick={loadLatestReport}>Load latest report</button>
              </div>
              {report && (
                <article className={report.recommendation === 'blocked' ? 'error-notice' : ''}>
                  <div><strong>v{report.report_version}: {report.recommendation}</strong></div>
                  <div className="notice">Report ID: {report.public_id}</div>
                  <div className="notice">Checksum: {report.report_checksum_sha256}</div>
                </article>
              )}
              {report && (
                <>
                  <h3>Final Production Acceptance Decision</h3>
                  <form className="inline-form" onSubmit={submitReview}>
                    <select value={reviewForm.decision}
                      onChange={(event) => setReviewForm({ ...reviewForm, decision: event.target.value })}>
                      <option value="accepted">Accepted</option>
                      <option value="accepted_with_conditions">Accepted with conditions</option>
                      <option value="rejected">Rejected</option>
                      <option value="needs_remediation">Needs remediation</option>
                    </select>
                    <input placeholder="Reason" value={reviewForm.reason}
                      onChange={(event) => setReviewForm({ ...reviewForm, reason: event.target.value })} required />
                    <button type="submit">Record decision</button>
                  </form>
                  <p className="notice">A review only binds to the latest report; a stale (superseded) report is rejected.</p>
                </>
              )}
            </>
          )}
        </section>
      </div>
    </section>
  )
}
