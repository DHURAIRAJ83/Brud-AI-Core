import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  approveRollbackPlan,
  assessReleaseEligibility,
  buildReleaseBundle,
  collectReleaseArtifacts,
  compareReleases,
  createRelease,
  createReleaseCandidate,
  createReleaseFamily,
  createReleaseManifest,
  createReleaseModelCard,
  createRollbackPlan,
  deprecateRelease,
  executeRollbackPlan,
  releaseApprovals,
  releaseBundles,
  releaseCandidate,
  releaseCandidates,
  releaseComparison,
  releaseEligibility,
  releaseFamilies,
  releaseIssues,
  releaseManifest,
  releaseModelCard,
  releases,
  retireRelease,
  rollbackPlan,
  submitReleaseApproval,
  validateReleaseModelCard,
  validateRollbackPlan,
  verifyReleaseArtifacts,
  verifyReleaseBundle,
  verifyReleaseManifest,
} from '../services/api.js'

const REGISTRY_NOTICE = 'A registered release is not automatically deployable or available to the public chatbot.'
const BLOCKED_NOTICE = 'This candidate is blocked by evaluation, integrity, safety, licensing, or lineage requirements and cannot be released.'

const TABS = [
  'Overview', 'Release Families', 'Candidates', 'Artifact Inventory', 'Eligibility',
  'Model Cards', 'Manifests', 'Approvals', 'Releases', 'Comparisons', 'Bundles', 'Rollback',
]

export default function ModelRegistryPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '', families: [], candidates: [], releases: [] })
  const [familyForm, setFamilyForm] = useState({ name: '', slug: '' })
  const [candidateForm, setCandidateForm] = useState({ model_release_family_public_id: '', core_model_version_public_id: '', dataset_version_public_id: '', model_evaluation_run_public_id: '', label: '' })
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [candidateDetail, setCandidateDetail] = useState(null)
  const [issues, setIssues] = useState({ items: [] })
  const [eligibility, setEligibility] = useState(null)
  const [modelCard, setModelCard] = useState(null)
  const [manifest, setManifest] = useState(null)
  const [manifestVerification, setManifestVerification] = useState(null)
  const [approvals, setApprovals] = useState({ items: [] })
  const [approvalForm, setApprovalForm] = useState({ role: 'release', decision: 'approve', comment: '' })
  const [releaseForm, setReleaseForm] = useState({ candidate_public_id: '', version: '' })
  const [selectedReleaseId, setSelectedReleaseId] = useState('')
  const [bundles, setBundles] = useState({ items: [] })
  const [bundleVerification, setBundleVerification] = useState(null)
  const [compareLeft, setCompareLeft] = useState('')
  const [compareRight, setCompareRight] = useState('')
  const [comparisonResult, setComparisonResult] = useState(null)
  const [rollbackForm, setRollbackForm] = useState({ source_release: '', target_release: '', reason: '' })
  const [rollbackPlanId, setRollbackPlanId] = useState('')
  const [rollbackDetail, setRollbackDetail] = useState(null)
  const [panelError, setPanelError] = useState('')

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [families, candidates, releaseList] = await Promise.all([releaseFamilies(), releaseCandidates(), releases()])
      setState({
        loading: false, error: '',
        families: families.items ?? [], candidates: candidates.items ?? [], releases: releaseList.items ?? [],
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function loadCandidateDetail(candidateId) {
    setSelectedCandidateId(candidateId)
    setPanelError('')
    setCandidateDetail(await releaseCandidate(candidateId).catch(() => null))
    setIssues(await releaseIssues(candidateId).catch(() => ({ items: [] })))
    setEligibility(await releaseEligibility(candidateId).catch(() => null))
    setModelCard(await releaseModelCard(candidateId).catch(() => null))
    setManifest(await releaseManifest(candidateId).catch(() => null))
    setManifestVerification(null)
    setApprovals(await releaseApprovals(candidateId).catch(() => ({ items: [] })))
  }

  async function submitFamily(event) {
    event.preventDefault()
    try {
      await createReleaseFamily(familyForm)
      setFamilyForm({ name: '', slug: '' })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitCandidate(event) {
    event.preventDefault()
    try {
      const body = { ...candidateForm }
      if (!body.dataset_version_public_id) delete body.dataset_version_public_id
      if (!body.model_evaluation_run_public_id) delete body.model_evaluation_run_public_id
      if (!body.label) delete body.label
      await createReleaseCandidate(body)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runCollectArtifacts() {
    try {
      await collectReleaseArtifacts(selectedCandidateId)
      setPanelError('')
      await loadCandidateDetail(selectedCandidateId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runVerifyArtifacts() {
    try {
      await verifyReleaseArtifacts(selectedCandidateId)
      setPanelError('')
      await loadCandidateDetail(selectedCandidateId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runAssessEligibility() {
    try {
      setEligibility(await assessReleaseEligibility(selectedCandidateId))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateCard() {
    try {
      setModelCard(await createReleaseModelCard(selectedCandidateId))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runValidateCard() {
    try {
      setModelCard(await validateReleaseModelCard(selectedCandidateId))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateManifest() {
    try {
      setManifest(await createReleaseManifest(selectedCandidateId))
      setManifestVerification(null)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runVerifyManifest() {
    setManifestVerification(await verifyReleaseManifest(selectedCandidateId))
  }

  async function submitApproval(event) {
    event.preventDefault()
    try {
      await submitReleaseApproval(selectedCandidateId, approvalForm)
      setPanelError('')
      await loadCandidateDetail(selectedCandidateId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitRelease(event) {
    event.preventDefault()
    try {
      await createRelease(releaseForm)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadBundles(releaseId) {
    setSelectedReleaseId(releaseId)
    setBundles(await releaseBundles(releaseId).catch(() => ({ items: [] })))
    setBundleVerification(null)
  }

  async function runBuildBundle() {
    try {
      await buildReleaseBundle(selectedReleaseId)
      setPanelError('')
      await loadBundles(selectedReleaseId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runVerifyBundle(bundleId) {
    setBundleVerification(await verifyReleaseBundle(bundleId))
  }

  async function runCompare() {
    try {
      setComparisonResult(await compareReleases(compareLeft, compareRight))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitRollback(event) {
    event.preventDefault()
    try {
      const created = await createRollbackPlan(rollbackForm.source_release, {
        target_release_public_id: rollbackForm.target_release, reason: rollbackForm.reason,
      })
      setRollbackPlanId(created.public_id)
      setRollbackDetail(created)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runValidateRollback() {
    try {
      setRollbackDetail(await validateRollbackPlan(rollbackPlanId))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runApproveRollback() {
    try {
      setRollbackDetail(await approveRollbackPlan(rollbackPlanId))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runExecuteRollback() {
    try {
      setRollbackDetail(await executeRollbackPlan(rollbackPlanId))
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function viewRollback() {
    setRollbackDetail(await rollbackPlan(rollbackPlanId).catch(() => null))
  }

  if (state.loading) return <section className="notice">Loading model registry…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  const isBlocked = candidateDetail?.status === 'blocked'

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Model Registry and Release Governance</h2>
          <p className="notice">{REGISTRY_NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Model registry sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}
      {isBlocked && <div className="notice error-notice">{BLOCKED_NOTICE}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Candidates</h3>
          {(state.candidates ?? []).length === 0 && <article>No release candidates yet.</article>}
          {(state.candidates ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadCandidateDetail(item.public_id)}>
              <strong>{item.label ?? item.public_id.slice(0, 8)}</strong>
              <span>{item.status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              {candidateDetail && (
                <div className="metric-grid">
                  <StatusCard label="Candidate status" value={candidateDetail.status} tone="good" />
                  <StatusCard label="Core model" value={candidateDetail.core_model_lifecycle_status} tone="neutral" />
                  <StatusCard label="Checkpoint" value={candidateDetail.checkpoint_status} tone="neutral" />
                  <StatusCard label="Tokenizer" value={candidateDetail.tokenizer_version_public_id?.slice(0, 8)} tone="neutral" />
                </div>
              )}
              <p className="notice">
                Source model, checkpoint checksum, tokenizer, dataset lineage, and training lineage
                are all shown per-candidate in the Candidates and Artifact Inventory tabs.
              </p>
              <p className="notice">The full source-to-model trace (source, PDF page, chunk, structured record, dataset record, dataset version, training run, evaluation, release) for a release's dataset version is queryable from the Builds &amp; Pipelines page's Lineage tab.</p>
            </>
          )}

          {tab === 'Release Families' && (
            <>
              <form className="inline-form training-form" onSubmit={submitFamily}>
                <h3>Create release family</h3>
                <label>Name<input value={familyForm.name} onChange={(e) => setFamilyForm({ ...familyForm, name: e.target.value })} /></label>
                <label>Slug<input value={familyForm.slug} onChange={(e) => setFamilyForm({ ...familyForm, slug: e.target.value })} /></label>
                <button type="submit">Create family</button>
              </form>
              <div className="data-list">
                {(state.families ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.name}</strong><small>{item.lifecycle_status}</small></div>
                    <small>current release: {item.current_release_public_id ? item.current_release_public_id.slice(0, 8) : 'none'}</small>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Candidates' && (
            <>
              <form className="inline-form training-form" onSubmit={submitCandidate}>
                <h3>Create release candidate</h3>
                <label>Family
                  <select value={candidateForm.model_release_family_public_id} onChange={(e) => setCandidateForm({ ...candidateForm, model_release_family_public_id: e.target.value })}>
                    <option value="">Select family</option>
                    {(state.families ?? []).map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Core model version public ID<input value={candidateForm.core_model_version_public_id} onChange={(e) => setCandidateForm({ ...candidateForm, core_model_version_public_id: e.target.value })} /></label>
                <label>Dataset version public ID (optional)<input value={candidateForm.dataset_version_public_id} onChange={(e) => setCandidateForm({ ...candidateForm, dataset_version_public_id: e.target.value })} /></label>
                <label>Evaluation run public ID (optional)<input value={candidateForm.model_evaluation_run_public_id} onChange={(e) => setCandidateForm({ ...candidateForm, model_evaluation_run_public_id: e.target.value })} /></label>
                <label>Label<input value={candidateForm.label} onChange={(e) => setCandidateForm({ ...candidateForm, label: e.target.value })} /></label>
                <button type="submit">Create candidate</button>
              </form>
              {candidateDetail && (
                <div className="metric-table">
                  <span>candidate {candidateDetail.public_id.slice(0, 8)}</span>
                  <span>status {candidateDetail.status}</span>
                  <span>instruction tuned: {candidateDetail.core_model_architecture_summary?.instruction_tuned ? 'yes' : 'no'}</span>
                  <span>checkpoint checksum {candidateDetail.checkpoint_model_checksum_sha256?.slice(0, 16)}</span>
                </div>
              )}
              <div className="document-actions">
                <button onClick={runCollectArtifacts} disabled={!selectedCandidateId}>Collect artifacts</button>
                <button onClick={runVerifyArtifacts} disabled={!selectedCandidateId}>Verify artifacts</button>
              </div>
            </>
          )}

          {tab === 'Artifact Inventory' && (
            <>
              <h3>Artifact Inventory {selectedCandidateId && <small>candidate {selectedCandidateId.slice(0, 8)}</small>}</h3>
              <div className="data-list">
                {(issues.items ?? []).length === 0 && <article>No issues recorded — collect and verify artifacts first.</article>}
                {(issues.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.issue_code}</strong><small>{item.severity}</small></div>
                    <small>{item.message}</small>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Eligibility' && (
            <>
              <h3>Eligibility Assessment</h3>
              <button onClick={runAssessEligibility} disabled={!selectedCandidateId}>Assess eligibility</button>
              {eligibility ? (
                <div className="metric-table">
                  <span>status {eligibility.status}</span>
                  <span>blocking issues {eligibility.blocking_issue_count}</span>
                  <span>warning issues {eligibility.warning_issue_count}</span>
                </div>
              ) : <p>No eligibility assessment yet.</p>}
            </>
          )}

          {tab === 'Model Cards' && (
            <>
              <h3>Model Card</h3>
              <div className="document-actions">
                <button onClick={runGenerateCard} disabled={!selectedCandidateId}>Generate model card</button>
                <button onClick={runValidateCard} disabled={!modelCard}>Validate model card</button>
              </div>
              {modelCard && (
                <div className="metric-table">
                  <span>checksum {modelCard.card_checksum_sha256?.slice(0, 16)}</span>
                  <span>validation {modelCard.validation_status}</span>
                  {(modelCard.validation_issues ?? []).map((issue, index) => (
                    <span key={index} className="error-notice">{issue}</span>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === 'Manifests' && (
            <>
              <h3>Release Manifest</h3>
              <div className="document-actions">
                <button onClick={runGenerateManifest} disabled={!selectedCandidateId}>Generate manifest</button>
                <button onClick={runVerifyManifest} disabled={!manifest}>Verify checksum</button>
              </div>
              {manifest && <div className="metric-table"><span>checksum {manifest.manifest_checksum_sha256?.slice(0, 16)}</span></div>}
              {manifestVerification && (
                <div className="notice">{manifestVerification.matches ? 'Checksum verified — manifest matches.' : 'Checksum mismatch detected.'}</div>
              )}
            </>
          )}

          {tab === 'Approvals' && (
            <>
              <form className="inline-form training-form" onSubmit={submitApproval}>
                <h3>Submit approval</h3>
                <label>Role
                  <select value={approvalForm.role} onChange={(e) => setApprovalForm({ ...approvalForm, role: e.target.value })}>
                    {['technical', 'evaluation', 'security', 'release'].map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </label>
                <label>Decision
                  <select value={approvalForm.decision} onChange={(e) => setApprovalForm({ ...approvalForm, decision: e.target.value })}>
                    {['approve', 'approve_with_warning', 'reject', 'request_changes'].map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                </label>
                <label>Comment<input value={approvalForm.comment} onChange={(e) => setApprovalForm({ ...approvalForm, comment: e.target.value })} /></label>
                <button type="submit" disabled={!selectedCandidateId}>Submit approval</button>
              </form>
              <div className="data-list">
                {(approvals.items ?? []).map((item) => (
                  <article key={item.public_id}><small>{item.role}: {item.decision}</small></article>
                ))}
              </div>
            </>
          )}

          {tab === 'Releases' && (
            <>
              <form className="inline-form" onSubmit={submitRelease}>
                <h3>Create release</h3>
                <label>Candidate public ID<input value={releaseForm.candidate_public_id} onChange={(e) => setReleaseForm({ ...releaseForm, candidate_public_id: e.target.value })} /></label>
                <label>Version<input value={releaseForm.version} onChange={(e) => setReleaseForm({ ...releaseForm, version: e.target.value })} placeholder="0.1.0" /></label>
                <button type="submit">Create release</button>
              </form>
              <div className="data-list">
                {(state.releases ?? []).length === 0 && <article>No releases yet.</article>}
                {(state.releases ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.version}</strong><small>{item.status}</small></div>
                    <small>deployment eligibility: {item.deployment_eligibility}</small>
                    <div className="document-actions">
                      <button onClick={() => deprecateRelease(item.public_id).then(load)}>Deprecate</button>
                      <button onClick={() => retireRelease(item.public_id).then(load)}>Retire</button>
                      <button onClick={() => loadBundles(item.public_id)}>Bundles</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Comparisons' && (
            <>
              <h3>Release Comparison</h3>
              <div className="inline-form">
                <label>Left release<input value={compareLeft} onChange={(e) => setCompareLeft(e.target.value)} /></label>
                <label>Right release<input value={compareRight} onChange={(e) => setCompareRight(e.target.value)} /></label>
                <button onClick={runCompare}>Compare releases</button>
              </div>
              {comparisonResult && (
                <div className="metric-table">
                  <span>compatibility {comparisonResult.compatibility}</span>
                  <span>ranked {comparisonResult.ranked ? 'yes' : 'no'}</span>
                </div>
              )}
            </>
          )}

          {tab === 'Bundles' && (
            <>
              <h3>Release Bundle {selectedReleaseId && <small>release {selectedReleaseId.slice(0, 8)}</small>}</h3>
              <button onClick={runBuildBundle} disabled={!selectedReleaseId}>Build bundle</button>
              <div className="data-list">
                {(bundles.items ?? []).length === 0 && <article>No bundles yet.</article>}
                {(bundles.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.bundle_format}</strong><small>{item.size_bytes} bytes</small></div>
                    <small>checksum {item.bundle_checksum_sha256?.slice(0, 16)}</small>
                    <div className="document-actions">
                      <button onClick={() => runVerifyBundle(item.public_id)}>Verify</button>
                    </div>
                  </article>
                ))}
              </div>
              {bundleVerification && (
                <div className="notice">{bundleVerification.matches ? 'Checksum verified — bundle matches.' : 'Checksum mismatch detected.'}</div>
              )}
            </>
          )}

          {tab === 'Rollback' && (
            <>
              <form className="inline-form training-form" onSubmit={submitRollback}>
                <h3>Create rollback plan</h3>
                <label>Source release (public ID)<input value={rollbackForm.source_release} onChange={(e) => setRollbackForm({ ...rollbackForm, source_release: e.target.value })} /></label>
                <label>Target release (public ID)<input value={rollbackForm.target_release} onChange={(e) => setRollbackForm({ ...rollbackForm, target_release: e.target.value })} /></label>
                <label>Reason<input value={rollbackForm.reason} onChange={(e) => setRollbackForm({ ...rollbackForm, reason: e.target.value })} /></label>
                <button type="submit">Create rollback plan</button>
              </form>
              <div className="inline-form">
                <label>Rollback plan public ID<input value={rollbackPlanId} onChange={(e) => setRollbackPlanId(e.target.value)} /></label>
                <button onClick={viewRollback} disabled={!rollbackPlanId}>View</button>
                <button onClick={runValidateRollback} disabled={!rollbackPlanId}>Validate</button>
                <button onClick={runApproveRollback} disabled={!rollbackPlanId}>Approve</button>
                <button onClick={runExecuteRollback} disabled={!rollbackPlanId}>Execute</button>
              </div>
              {rollbackDetail && (
                <div className="metric-table">
                  <span>status {rollbackDetail.status}</span>
                  <span>source {rollbackDetail.source_release_public_id?.slice(0, 8)}</span>
                  <span>target {rollbackDetail.target_release_public_id?.slice(0, 8)}</span>
                </div>
              )}
              <p className="notice">
                Rollback is metadata-only: it never starts or stops any server, never changes
                environment variables, and never touches the public chatbot's model assignment.
              </p>
            </>
          )}
        </section>
      </div>
    </section>
  )
}
