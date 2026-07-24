import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  activateEvalSuite,
  assessEvalReadiness,
  compareEvalRuns,
  createEvalFixtureSet,
  createEvalRun,
  createEvalSuite,
  evalCandidates,
  evalFixtureSetCoverage,
  evalFixtureSets,
  evalFixtures,
  evalIssues,
  evalMetrics,
  evalOutputs,
  evalReadiness,
  evalReviewQueue,
  evalReviews,
  evalRuns,
  evalSuites,
  executeEvalRun,
  generateEvalManifest,
  submitEvalHumanReview,
  validateEvalSuite,
  verifyEvalManifest,
} from '../services/api.js'

const SCOPE_NOTICE = 'Model evaluation measures behavior on a fixed, versioned fixture suite. It never connects the candidate to the public chatbot, and the model remains not_public_chat_ready regardless of the outcome.'
const RELEVANCE_NOTICE = 'Surface relevance is keyword/lexical overlap, not factual correctness. Unsupported-claim risk is a bounded heuristic, not comprehensive hallucination detection.'
const SAFETY_NOTICE = 'Safety and refusal checks are keyword/pattern-based and deliberately conservative — they are not a comprehensive safety guarantee.'

const TABS = [
  'Overview', 'Suites', 'Fixture Sets', 'Evaluation Runs', 'Language Metrics',
  'Instruction Following', 'Relevance and Facts', 'Safety and Refusals',
  'Leakage and Repetition', 'Human Review', 'Comparisons', 'Chat Readiness',
  'Reproducibility',
]

const defaultSuiteForm = {
  name: '', version: 'v1', description: '',
  generation_configuration: { temperature: 0.0, sampling_enabled: false, streaming: false, max_new_tokens: 32 },
}

const defaultFixtureForm = {
  category: 'language_compliance', language: 'ta', prompt: '', system_prompt: '',
  expected_response_language: 'ta', expected_format: '', refusal_expected: false, severity: 'medium',
}

export default function ModelEvaluationPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '', suites: [], candidates: [], runs: [] })
  const [suiteForm, setSuiteForm] = useState(defaultSuiteForm)
  const [selectedSuiteId, setSelectedSuiteId] = useState('')
  const [fixtureSets, setFixtureSets] = useState({ items: [] })
  const [fixtureSetName, setFixtureSetName] = useState('fixture-set-1')
  const [pendingFixtures, setPendingFixtures] = useState([])
  const [fixtureForm, setFixtureForm] = useState(defaultFixtureForm)
  const [selectedFixtureSetId, setSelectedFixtureSetId] = useState('')
  const [coverage, setCoverage] = useState(null)
  const [fixtures, setFixtures] = useState({ items: [] })
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [selectedRunId, setSelectedRunId] = useState('')
  const [runDetail, setRunDetail] = useState(null)
  const [outputs, setOutputs] = useState({ items: [] })
  const [metrics, setMetrics] = useState({ items: [] })
  const [issues, setIssues] = useState({ items: [] })
  const [reviews, setReviews] = useState({ items: [], aggregate: {} })
  const [reviewQueue, setReviewQueue] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [manifest, setManifest] = useState(null)
  const [manifestVerification, setManifestVerification] = useState(null)
  const [compareLeft, setCompareLeft] = useState('')
  const [compareRight, setCompareRight] = useState('')
  const [comparisonResult, setComparisonResult] = useState(null)
  const [reviewForm, setReviewForm] = useState({
    language: 'ta', category: 'language_compliance', relevance_score: 3,
    instruction_following_score: 3, language_quality_score: 3, safety_score: 3,
    overall_score: 3, verdict: 'pass', comment: '',
  })
  const [reviewOutputId, setReviewOutputId] = useState('')
  const [panelError, setPanelError] = useState('')

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [suites, candidates, runs] = await Promise.all([evalSuites(), evalCandidates(), evalRuns()])
      setState({
        loading: false, error: '',
        suites: suites.items ?? [], candidates: candidates.items ?? [], runs: runs.items ?? [],
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function loadFixtureSets(suiteId) {
    setSelectedSuiteId(suiteId)
    setFixtureSets(await evalFixtureSets(suiteId).catch(() => ({ items: [] })))
  }

  async function loadFixtureSetDetail(fixtureSetId) {
    setSelectedFixtureSetId(fixtureSetId)
    setCoverage(await evalFixtureSetCoverage(fixtureSetId).catch(() => null))
    setFixtures(await evalFixtures(fixtureSetId).catch(() => ({ items: [] })))
  }

  async function loadRunDetail(runId) {
    setSelectedRunId(runId)
    setRunDetail(state.runs.find((item) => item.public_id === runId) ?? null)
    setOutputs(await evalOutputs(runId).catch(() => ({ items: [] })))
    setMetrics(await evalMetrics(runId).catch(() => ({ items: [] })))
    setIssues(await evalIssues(runId).catch(() => ({ items: [] })))
    setReviews(await evalReviews(runId).catch(() => ({ items: [], aggregate: {} })))
    setReviewQueue(await evalReviewQueue(runId).catch(() => null))
    setReadiness(await evalReadiness(runId).catch(() => null))
    setManifest(null)
    setManifestVerification(null)
  }

  async function submitSuite(event) {
    event.preventDefault()
    try {
      await createEvalSuite(suiteForm)
      setSuiteForm(defaultSuiteForm)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runValidateSuite(suiteId) {
    try {
      await validateEvalSuite(suiteId)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runActivateSuite(suiteId) {
    try {
      await activateEvalSuite(suiteId)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  function addPendingFixture() {
    setPendingFixtures((old) => [...old, fixtureForm])
    setFixtureForm(defaultFixtureForm)
  }

  async function submitFixtureSet(event) {
    event.preventDefault()
    try {
      await createEvalFixtureSet(selectedSuiteId, { name: fixtureSetName, fixtures: pendingFixtures })
      setPendingFixtures([])
      setPanelError('')
      await loadFixtureSets(selectedSuiteId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitCreateRun(event) {
    event.preventDefault()
    try {
      await createEvalRun({
        model_evaluation_fixture_set_public_id: selectedFixtureSetId,
        candidate_core_model_version_public_id: selectedCandidateId,
      })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runExecute(runId) {
    try {
      await executeEvalRun(runId)
      setPanelError('')
      await load()
      await loadRunDetail(runId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitReview(event) {
    event.preventDefault()
    try {
      await submitEvalHumanReview({ model_evaluation_output_public_id: reviewOutputId, ...reviewForm })
      setPanelError('')
      await loadRunDetail(selectedRunId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runAssessReadiness() {
    try {
      setReadiness(await assessEvalReadiness(selectedRunId))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runCompare() {
    try {
      setComparisonResult(await compareEvalRuns(compareLeft, compareRight))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateManifest() {
    try {
      setManifest(await generateEvalManifest(selectedRunId))
      setManifestVerification(null)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runVerifyManifest() {
    setManifestVerification(await verifyEvalManifest(selectedRunId))
  }

  if (state.loading) return <section className="notice">Loading model evaluation…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  const languageMetrics = (metrics.items ?? []).filter((item) => item.metric_name === 'language_compliance' || item.metric_name === 'language_compliance_score')
  const instructionMetrics = (metrics.items ?? []).filter((item) => item.metric_name === 'instruction_following_score')
  const relevanceMetrics = (metrics.items ?? []).filter((item) => item.metric_name === 'surface_relevance_score' || item.metric_name === 'unsupported_claim_risk')
  const safetyIssues = (issues.items ?? []).filter((item) => ['unsafe_compliance', 'incorrect_refusal', 'over_refusal'].includes(item.issue_code))
  const leakageIssues = (issues.items ?? []).filter((item) => ['role_token_leakage', 'prompt_leakage', 'system_prompt_leakage', 'internal_metadata_leakage', 'high_duplicate_output_rate', 'token_loop_detected', 'phrase_loop_detected'].includes(item.issue_code))

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Multilingual Evaluation, Safety, and Chat Readiness</h2>
          <p className="notice">{SCOPE_NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Model evaluation sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Runs</h3>
          {(state.runs ?? []).length === 0 && <article>No evaluation runs yet.</article>}
          {(state.runs ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadRunDetail(item.public_id)}>
              <strong>{item.public_id.slice(0, 8)}</strong>
              <span>{item.status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Eligible Candidates</h3>
              <p className="notice">Only base_pretrained + instruction_tuned + evaluation_required candidates are eligible.</p>
              <div className="data-list">
                {(state.candidates ?? []).length === 0 && <article>No eligible candidates yet — complete Phase 12 instruction tuning first.</article>}
                {(state.candidates ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.version}</strong><small>{item.lifecycle_status}</small></div>
                    <small>{item.public_id}</small>
                  </article>
                ))}
              </div>
              {runDetail && (
                <div className="metric-grid">
                  <StatusCard label="Run status" value={runDetail.status} tone="good" />
                  <StatusCard label="Fixtures" value={runDetail.fixture_count} tone="neutral" />
                  <StatusCard label="Completed" value={runDetail.completed_fixture_count} tone="neutral" />
                  <StatusCard label="Failed" value={runDetail.failed_fixture_count} tone={runDetail.failed_fixture_count ? 'bad' : 'good'} />
                </div>
              )}
            </>
          )}

          {tab === 'Suites' && (
            <>
              <form className="inline-form training-form" onSubmit={submitSuite}>
                <h3>Create evaluation suite</h3>
                <label>Name<input value={suiteForm.name} onChange={(e) => setSuiteForm({ ...suiteForm, name: e.target.value })} /></label>
                <label>Version<input value={suiteForm.version} onChange={(e) => setSuiteForm({ ...suiteForm, version: e.target.value })} /></label>
                <label>Description<input value={suiteForm.description} onChange={(e) => setSuiteForm({ ...suiteForm, description: e.target.value })} /></label>
                <button type="submit">Create suite (draft)</button>
              </form>
              <div className="data-list">
                {(state.suites ?? []).length === 0 && <article>No suites yet.</article>}
                {(state.suites ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.name} v{item.version}</strong><small>{item.status}</small></div>
                    <div className="document-actions">
                      <button onClick={() => runValidateSuite(item.public_id)} disabled={item.status !== 'draft'}>Validate</button>
                      <button onClick={() => runActivateSuite(item.public_id)} disabled={item.status !== 'validated'}>Activate</button>
                      <button onClick={() => loadFixtureSets(item.public_id)}>Fixture sets</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Fixture Sets' && (
            <>
              <h3>Fixture Sets {selectedSuiteId && <small>suite {selectedSuiteId.slice(0, 8)}</small>}</h3>
              <p className="notice">Fixtures are admin-authored, never hardcoded — this page validates and checksums whatever is submitted.</p>
              <div className="inline-form">
                <label>Fixture set name<input value={fixtureSetName} onChange={(e) => setFixtureSetName(e.target.value)} /></label>
              </div>
              <form className="inline-form training-form" onSubmit={(e) => e.preventDefault()}>
                <h4>Add fixture</h4>
                <label>Category
                  <select value={fixtureForm.category} onChange={(e) => setFixtureForm({ ...fixtureForm, category: e.target.value })}>
                    {['language_compliance', 'instruction_following', 'response_relevance', 'format_compliance', 'translation', 'definition', 'summarization', 'classification', 'transformation', 'reasoning_basic', 'code_switching', 'tanglish_understanding', 'safety_refusal', 'unsafe_instruction_handling', 'prompt_leakage', 'role_leakage', 'system_prompt_leakage', 'repetition', 'robustness', 'unicode_handling'].map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
                <label>Language
                  <select value={fixtureForm.language} onChange={(e) => setFixtureForm({ ...fixtureForm, language: e.target.value })}>
                    {['ta', 'en', 'tgl', 'mixed'].map((l) => <option key={l} value={l}>{l}</option>)}
                  </select>
                </label>
                <label>Prompt<input value={fixtureForm.prompt} onChange={(e) => setFixtureForm({ ...fixtureForm, prompt: e.target.value })} /></label>
                <label>Refusal expected
                  <input type="checkbox" checked={fixtureForm.refusal_expected} onChange={(e) => setFixtureForm({ ...fixtureForm, refusal_expected: e.target.checked })} />
                </label>
                <button onClick={addPendingFixture} disabled={!fixtureForm.prompt}>Add to pending set</button>
              </form>
              <p>Pending fixtures: {pendingFixtures.length}</p>
              <button onClick={submitFixtureSet} disabled={!selectedSuiteId || pendingFixtures.length === 0}>Submit fixture set</button>
              <div className="data-list">
                {(fixtureSets.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.name}</strong><small>{item.fixture_count} fixtures</small></div>
                    <div className="document-actions">
                      <button onClick={() => loadFixtureSetDetail(item.public_id)}>View coverage</button>
                    </div>
                  </article>
                ))}
              </div>
              {coverage && (
                <div className="metric-table">
                  <span>sufficiency {coverage.sufficiency_status}</span>
                  <span>languages {JSON.stringify(coverage.language_counts)}</span>
                  <span>categories {JSON.stringify(coverage.category_counts)}</span>
                  {(coverage.warnings ?? []).map((warning, index) => (
                    <span key={index} className="error-notice">{warning.message}</span>
                  ))}
                </div>
              )}
              {(fixtures.items ?? []).length > 0 && (
                <div className="data-list">
                  {fixtures.items.map((item) => (
                    <article key={item.public_id}><small>{item.category} · {item.language}: {item.prompt}</small></article>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === 'Evaluation Runs' && (
            <>
              <form className="inline-form" onSubmit={submitCreateRun}>
                <h3>Create run</h3>
                <label>Fixture set public ID<input value={selectedFixtureSetId} onChange={(e) => setSelectedFixtureSetId(e.target.value)} /></label>
                <label>Candidate
                  <select value={selectedCandidateId} onChange={(e) => setSelectedCandidateId(e.target.value)}>
                    <option value="">Select eligible candidate</option>
                    {(state.candidates ?? []).map((item) => <option key={item.public_id} value={item.public_id}>{item.version}</option>)}
                  </select>
                </label>
                <button type="submit" disabled={!selectedFixtureSetId || !selectedCandidateId}>Create run</button>
              </form>
              <div className="data-list">
                {(state.runs ?? []).map((run) => (
                  <article key={run.public_id}>
                    <div><strong>{run.public_id.slice(0, 8)}</strong><small>{run.status}</small></div>
                    <div className="document-actions">
                      <button onClick={() => runExecute(run.public_id)} disabled={!['validated', 'queued'].includes(run.status)}>Execute</button>
                      <button onClick={() => loadRunDetail(run.public_id)}>View</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Language Metrics' && (
            <>
              <h3>Language Metrics {selectedRunId && <small>run {selectedRunId.slice(0, 8)}</small>}</h3>
              <div className="data-list">
                {languageMetrics.length === 0 && <article>No language metrics yet — execute a run first.</article>}
                {languageMetrics.map((item, index) => (
                  <article key={item.public_id ?? index}>
                    <small>{item.language} · {item.category ?? 'overall'}: {item.metric_value?.toFixed?.(3) ?? item.metric_value}</small>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Instruction Following' && (
            <>
              <h3>Instruction Following</h3>
              <div className="data-list">
                {instructionMetrics.length === 0 && <article>No instruction-following metrics yet.</article>}
                {instructionMetrics.map((item, index) => (
                  <article key={item.public_id ?? index}><small>{item.language} · {item.category ?? 'overall'}: score {item.metric_value?.toFixed?.(3)}</small></article>
                ))}
              </div>
            </>
          )}

          {tab === 'Relevance and Facts' && (
            <>
              <h3>Relevance and Factual Support</h3>
              <p className="notice">{RELEVANCE_NOTICE}</p>
              <div className="data-list">
                {relevanceMetrics.length === 0 && <article>No relevance/claim metrics yet.</article>}
                {relevanceMetrics.map((item, index) => (
                  <article key={item.public_id ?? index}><small>{item.metric_name} · {item.language ?? 'overall'}: {item.metric_value?.toFixed?.(3)}</small></article>
                ))}
              </div>
            </>
          )}

          {tab === 'Safety and Refusals' && (
            <>
              <h3>Safety and Refusal Behavior</h3>
              <p className="notice">{SAFETY_NOTICE}</p>
              <div className="data-list">
                {safetyIssues.length === 0 && <article>No safety/refusal issues recorded.</article>}
                {safetyIssues.map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.issue_code}</strong><small>{item.severity}</small></div>
                    <small>{item.message}</small>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Leakage and Repetition' && (
            <>
              <h3>Leakage and Repetition Issues</h3>
              <div className="data-list">
                {leakageIssues.length === 0 && <article>No leakage/repetition issues recorded.</article>}
                {leakageIssues.map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.issue_code}</strong><small>{item.severity}</small></div>
                    <small>{item.message}</small>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Human Review' && (
            <>
              <h3>Human Review Queue {selectedRunId && <small>run {selectedRunId.slice(0, 8)}</small>}</h3>
              {reviewQueue && (
                <div className="metric-table">
                  <span>coverage {(reviewQueue.coverage_ratio * 100).toFixed(0)}%</span>
                  <span>missing outputs {reviewQueue.missing_output_ids?.length ?? 0}</span>
                </div>
              )}
              <form className="inline-form training-form" onSubmit={submitReview}>
                <h4>Submit review</h4>
                <label>Output public ID<input value={reviewOutputId} onChange={(e) => setReviewOutputId(e.target.value)} /></label>
                <label>Language<input value={reviewForm.language} onChange={(e) => setReviewForm({ ...reviewForm, language: e.target.value })} /></label>
                <label>Category<input value={reviewForm.category} onChange={(e) => setReviewForm({ ...reviewForm, category: e.target.value })} /></label>
                {['relevance_score', 'instruction_following_score', 'language_quality_score', 'safety_score', 'overall_score'].map((key) => (
                  <label key={key}>{key.replaceAll('_', ' ')}
                    <input type="number" min="1" max="5" value={reviewForm[key]} onChange={(e) => setReviewForm({ ...reviewForm, [key]: Number(e.target.value) })} />
                  </label>
                ))}
                <label>Verdict
                  <select value={reviewForm.verdict} onChange={(e) => setReviewForm({ ...reviewForm, verdict: e.target.value })}>
                    {['pass', 'pass_with_warning', 'fail', 'needs_second_review'].map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </label>
                <button type="submit" disabled={!reviewOutputId}>Submit review</button>
              </form>
              <div className="data-list">
                <p>Disagreement: {reviews.aggregate?.disagreement_rate != null ? `${(reviews.aggregate.disagreement_rate * 100).toFixed(0)}%` : 'n/a'}</p>
                {(reviews.items ?? []).map((item) => (
                  <article key={item.public_id}><small>{item.verdict} · overall {item.overall_score}</small></article>
                ))}
              </div>
            </>
          )}

          {tab === 'Comparisons' && (
            <>
              <h3>Run Comparison</h3>
              <div className="inline-form">
                <label>Left run<input value={compareLeft} onChange={(e) => setCompareLeft(e.target.value)} /></label>
                <label>Right run<input value={compareRight} onChange={(e) => setCompareRight(e.target.value)} /></label>
                <button onClick={runCompare}>Compare runs</button>
              </div>
              {comparisonResult && (
                <div className="metric-table">
                  <span>compatibility {comparisonResult.compatibility}</span>
                  <span>ranked {comparisonResult.ranked ? 'yes' : 'no'}</span>
                </div>
              )}
            </>
          )}

          {tab === 'Chat Readiness' && (
            <>
              <h3>Chat Readiness Assessment {selectedRunId && <small>run {selectedRunId.slice(0, 8)}</small>}</h3>
              <button onClick={runAssessReadiness} disabled={!selectedRunId}>Assess readiness</button>
              {readiness ? (
                <div className="metric-table">
                  <span>status {readiness.status}</span>
                  <span>blocking issues {readiness.blocking_issue_count}</span>
                  <span>warning issues {readiness.warning_issue_count}</span>
                </div>
              ) : <p>No readiness assessment yet.</p>}
              <p className="notice">
                This assessment never approves public deployment. The candidate remains
                not_public_chat_ready regardless of the outcome above.
              </p>
            </>
          )}

          {tab === 'Reproducibility' && (
            <>
              <h3>Reproducibility Manifest</h3>
              <div className="document-actions">
                <button onClick={runGenerateManifest} disabled={!selectedRunId}>Generate / view manifest</button>
                <button onClick={runVerifyManifest} disabled={!manifest}>Verify checksum</button>
              </div>
              {manifest && (
                <div className="metric-table">
                  <span>checksum {manifest.manifest_checksum_sha256?.slice(0, 16)}</span>
                  <span>readiness status {manifest.manifest?.readiness_status}</span>
                  <span>blocking issues {manifest.manifest?.blocking_issue_count}</span>
                </div>
              )}
              {manifestVerification && (
                <div className="notice">{manifestVerification.matches ? 'Checksum verified — manifest matches.' : 'Checksum mismatch detected.'}</div>
              )}
            </>
          )}
        </section>
      </div>
    </section>
  )
}
