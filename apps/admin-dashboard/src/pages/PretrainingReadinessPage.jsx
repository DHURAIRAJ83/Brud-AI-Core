import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  activateTokenizerVersion,
  approveTokenizerCandidate,
  baseModelReadinessEvaluation,
  baseModelReadinessEvaluations,
  createBaseModelReadinessEvaluation,
  createDatasetSnapshot,
  createResourceEstimate,
  createSmokeRun,
  createTokenizerCandidateComparison,
  createTokenizerCorpusBuild,
  datasetSnapshots,
  resourceEstimates,
  smokeRuns,
  tokenizerCandidateComparison,
  tokenizerCorpusBuild,
  tokenizerCorpusBuilds,
  validateTrainingConfig,
} from '../services/api.js'

const NOTICE =
  'Phase 21A is a preparation and safety gate for future base-model pretraining. Nothing here starts long-running or production-scale training, and no result is connected to the public chatbot.'

const TABS = [
  'Overview', 'Tokenizer Corpus', 'Tokenizer Candidates', 'Model Profiles',
  'Dataset Snapshot', 'Training Config & Smoke Runs', 'Readiness',
]

export default function PretrainingReadinessPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '' })
  const [panelError, setPanelError] = useState('')

  const [builds, setBuilds] = useState({ items: [] })
  const [releaseId, setReleaseId] = useState('')
  const [selectedBuildId, setSelectedBuildId] = useState('')
  const [buildDetail, setBuildDetail] = useState(null)

  const [vocabSizes, setVocabSizes] = useState('2000,4000,8000')
  const [comparisonId, setComparisonId] = useState('')
  const [comparisonDetail, setComparisonDetail] = useState(null)
  const [approveTokenizerId, setApproveTokenizerId] = useState('')

  const [estimates, setEstimates] = useState({ items: [] })
  const [profileForm, setProfileForm] = useState({ profile_name: 'micro_smoke_test', vocabulary_size: 4000 })

  const [snapshots, setSnapshots] = useState({ items: [] })
  const [snapshotForm, setSnapshotForm] = useState({ tokenizer_version_public_id: '', maximum_sequence_length: 64 })

  const [smokeList, setSmokeList] = useState({ items: [] })
  const [smokeForm, setSmokeForm] = useState({ snapshot_id: '', estimate_id: '', total_steps: 10 })
  const [validationResult, setValidationResult] = useState(null)

  const [readinessList, setReadinessList] = useState({ items: [] })
  const [readinessForm, setReadinessForm] = useState({ snapshot_id: '', comparison_id: '', estimate_id: '', smoke_run_id: '' })
  const [readinessDetail, setReadinessDetail] = useState(null)

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [buildList, estimateList, snapshotList, smokeItems, readinessItems] = await Promise.all([
        tokenizerCorpusBuilds(), resourceEstimates(), datasetSnapshots(), smokeRuns(), baseModelReadinessEvaluations(),
      ])
      setBuilds(buildList)
      setEstimates(estimateList)
      setSnapshots(snapshotList)
      setSmokeList(smokeItems)
      setReadinessList(readinessItems)
      setState({ loading: false, error: '' })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function submitBuild(event) {
    event.preventDefault()
    try {
      await createTokenizerCorpusBuild({ corpus_release_public_id: releaseId })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadBuildDetail(id) {
    setSelectedBuildId(id)
    setBuildDetail(await tokenizerCorpusBuild(id).catch(() => null))
  }

  async function submitComparison(event) {
    event.preventDefault()
    try {
      const vocabulary_sizes = vocabSizes.split(',').map((v) => Number(v.trim())).filter(Boolean)
      const created = await createTokenizerCandidateComparison({
        tokenizer_corpus_build_public_id: selectedBuildId, vocabulary_sizes,
      })
      setComparisonId(created.public_id)
      setComparisonDetail(created)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadComparison() {
    setComparisonDetail(await tokenizerCandidateComparison(comparisonId).catch(() => null))
  }

  async function runApproveTokenizer() {
    try {
      const updated = await approveTokenizerCandidate(comparisonDetail.public_id, {
        tokenizer_version_public_id: approveTokenizerId,
      })
      setComparisonDetail(updated)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runActivateTokenizer() {
    try {
      await activateTokenizerVersion(approveTokenizerId)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitEstimate(event) {
    event.preventDefault()
    try {
      await createResourceEstimate({
        ...profileForm, vocabulary_size: Number(profileForm.vocabulary_size),
      })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitSnapshot(event) {
    event.preventDefault()
    try {
      await createDatasetSnapshot({
        corpus_release_public_id: releaseId,
        tokenizer_version_public_id: snapshotForm.tokenizer_version_public_id,
        maximum_sequence_length: Number(snapshotForm.maximum_sequence_length),
      })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runValidateConfig() {
    try {
      setValidationResult(
        await validateTrainingConfig({
          pretraining_dataset_snapshot_public_id: smokeForm.snapshot_id,
          base_model_resource_estimate_public_id: smokeForm.estimate_id,
          configuration: { total_steps: Number(smokeForm.total_steps) },
        }),
      )
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitSmokeRun(event) {
    event.preventDefault()
    try {
      await createSmokeRun({
        pretraining_dataset_snapshot_public_id: smokeForm.snapshot_id,
        base_model_resource_estimate_public_id: smokeForm.estimate_id,
        total_steps: Number(smokeForm.total_steps),
      })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitReadiness(event) {
    event.preventDefault()
    try {
      const created = await createBaseModelReadinessEvaluation({
        pretraining_dataset_snapshot_public_id: readinessForm.snapshot_id,
        tokenizer_candidate_comparison_public_id: readinessForm.comparison_id || null,
        base_model_resource_estimate_public_id: readinessForm.estimate_id || null,
        pretraining_smoke_run_public_id: readinessForm.smoke_run_id || null,
      })
      setReadinessDetail(created)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadReadinessDetail(id) {
    setReadinessDetail(await baseModelReadinessEvaluation(id).catch(() => null))
  }

  if (state.loading) return <section className="notice">Loading pretraining readiness…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Production Tokenizer &amp; Pretraining Readiness</h2>
          <p className="notice">{NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Pretraining readiness sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Tokenizer Corpus Builds</h3>
          {(builds.items ?? []).length === 0 && <article>None yet.</article>}
          {(builds.items ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadBuildDetail(item.public_id)}>
              <strong>{item.public_id.slice(0, 8)}</strong>
              <span>{item.sufficiency_state}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              <div className="metric-grid">
                <StatusCard label="Tokenizer Corpus Builds" value={(builds.items ?? []).length} tone="neutral" />
                <StatusCard label="Resource Estimates" value={(estimates.items ?? []).length} tone="neutral" />
                <StatusCard label="Dataset Snapshots" value={(snapshots.items ?? []).length} tone="neutral" />
                <StatusCard label="Smoke Runs" value={(smokeList.items ?? []).length} tone="neutral" />
                <StatusCard label="Readiness Evaluations" value={(readinessList.items ?? []).length} tone="neutral" />
              </div>
              <p className="notice">
                Pipeline: exported corpus release → tokenizer corpus build → candidate training/
                evaluation → approval/activation → model resource estimate → frozen dataset
                snapshot → training-config validation → tiny bounded smoke run → 17-dimension
                readiness gate.
              </p>
              <p className="notice">A governed dataset version built from approved Data Studio content can be handed off here from the Builds &amp; Pipelines page -- the handoff never starts a pretraining run automatically; this page's own readiness/run controls remain the only way to start one.</p>
            </>
          )}

          {tab === 'Tokenizer Corpus' && (
            <>
              <h3>Build Tokenizer Corpus from an Exported Corpus Release</h3>
              <form className="inline-form" onSubmit={submitBuild}>
                <input placeholder="Corpus release public ID" value={releaseId}
                  onChange={(event) => setReleaseId(event.target.value)} required />
                <button type="submit">Build</button>
              </form>
              {buildDetail && (
                <article>
                  <div>Status: {buildDetail.status} — {buildDetail.sufficiency_state}</div>
                  <div>Records: {buildDetail.total_records}, characters: {buildDetail.total_characters}</div>
                  <div>Tamil-only: {buildDetail.tamil_only_record_count}, English-only: {buildDetail.english_only_record_count},
                    Tanglish: {buildDetail.tanglish_record_count}, Mixed: {buildDetail.mixed_record_count}</div>
                  <div>Duplicate exclusions: {buildDetail.duplicate_exclusion_count},
                    contamination exclusions: {buildDetail.contamination_exclusion_count}</div>
                  <pre>{JSON.stringify(buildDetail.domain_distribution, null, 2)}</pre>
                </article>
              )}
            </>
          )}

          {tab === 'Tokenizer Candidates' && (
            <>
              <h3>Train &amp; Compare Tokenizer Candidates</h3>
              <p className="notice">Selected build: {selectedBuildId || '(select one from the list on the left)'}</p>
              <form className="inline-form" onSubmit={submitComparison}>
                <input placeholder="Vocabulary sizes, comma separated" value={vocabSizes}
                  onChange={(event) => setVocabSizes(event.target.value)} required />
                <button type="submit">Train &amp; compare candidates</button>
              </form>
              <div className="inline-form">
                <input placeholder="Existing comparison public ID" value={comparisonId}
                  onChange={(event) => setComparisonId(event.target.value)} />
                <button onClick={loadComparison}>Load</button>
              </div>
              {comparisonDetail && (
                <article>
                  <div>Recommended tokenizer: {comparisonDetail.recommended_tokenizer_version_public_id ?? 'none (all candidates rejected)'}</div>
                  {(comparisonDetail.evaluations ?? []).map((item) => (
                    <div key={item.public_id}>
                      vocab {item.vocabulary_size}: {item.final_status} — {item.rationale}
                    </div>
                  ))}
                  <div className="inline-form">
                    <input placeholder="Tokenizer version public ID" value={approveTokenizerId}
                      onChange={(event) => setApproveTokenizerId(event.target.value)} />
                    <button onClick={runApproveTokenizer}>Approve as recommended</button>
                    <button onClick={runActivateTokenizer}>Activate (requires passing Phase 7 evaluation)</button>
                  </div>
                </article>
              )}
            </>
          )}

          {tab === 'Model Profiles' && (
            <>
              <h3>CPU-Safe Model Resource Estimates</h3>
              <form className="inline-form" onSubmit={submitEstimate}>
                <select value={profileForm.profile_name}
                  onChange={(event) => setProfileForm({ ...profileForm, profile_name: event.target.value })}>
                  <option value="micro_smoke_test">Profile A — Micro Smoke Test (~1-3M params)</option>
                  <option value="small_experimental">Profile B — Small Experimental (~10-30M params)</option>
                  <option value="maximum_safe_local">Profile C — Maximum Safe Local (calculated)</option>
                </select>
                <input type="number" placeholder="Vocabulary size" value={profileForm.vocabulary_size}
                  onChange={(event) => setProfileForm({ ...profileForm, vocabulary_size: event.target.value })} required />
                <button type="submit">Estimate</button>
              </form>
              {(estimates.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <strong>{item.profile_name}</strong> — {item.parameter_count.toLocaleString()} params
                  <div>Peak RAM: {(item.estimated_peak_ram_bytes / 1e6).toFixed(1)} MB
                    (ceiling {(item.safe_ram_ceiling_bytes / 1e6).toFixed(0)} MB) —
                    {item.within_safe_limit ? ' within limit' : ' EXCEEDS LIMIT'}</div>
                  <div>Estimated speed: {item.estimated_tokens_per_second.toFixed(1)} tokens/sec</div>
                </article>
              ))}
            </>
          )}

          {tab === 'Dataset Snapshot' && (
            <>
              <h3>Freeze an Immutable Pretraining Dataset Snapshot</h3>
              <form className="inline-form" onSubmit={submitSnapshot}>
                <input placeholder="Corpus release public ID" value={releaseId}
                  onChange={(event) => setReleaseId(event.target.value)} required />
                <input placeholder="Tokenizer version public ID" value={snapshotForm.tokenizer_version_public_id}
                  onChange={(event) => setSnapshotForm({ ...snapshotForm, tokenizer_version_public_id: event.target.value })} required />
                <input type="number" placeholder="Max sequence length" value={snapshotForm.maximum_sequence_length}
                  onChange={(event) => setSnapshotForm({ ...snapshotForm, maximum_sequence_length: event.target.value })} />
                <button type="submit">Freeze snapshot</button>
              </form>
              {(snapshots.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <strong>{item.public_id.slice(0, 8)}</strong> —
                  train {item.train_record_count}/{item.train_token_count}tok,
                  validation {item.validation_record_count}/{item.validation_token_count}tok,
                  test {item.test_record_count}/{item.test_token_count}tok
                </article>
              ))}
            </>
          )}

          {tab === 'Training Config & Smoke Runs' && (
            <>
              <h3>Tiny Bounded Pretraining Smoke Test</h3>
              <div className="inline-form">
                <input placeholder="Dataset snapshot public ID" value={smokeForm.snapshot_id}
                  onChange={(event) => setSmokeForm({ ...smokeForm, snapshot_id: event.target.value })} />
                <input placeholder="Resource estimate public ID (micro_smoke_test)" value={smokeForm.estimate_id}
                  onChange={(event) => setSmokeForm({ ...smokeForm, estimate_id: event.target.value })} />
                <input type="number" placeholder="Total steps" value={smokeForm.total_steps}
                  onChange={(event) => setSmokeForm({ ...smokeForm, total_steps: event.target.value })} />
                <button onClick={runValidateConfig}>Validate config</button>
              </div>
              {validationResult && (
                <article className={validationResult.status === 'fail' ? 'error-notice' : ''}>
                  <div>Status: {validationResult.status}</div>
                  {validationResult.failures?.length > 0 && <div>Failures: {validationResult.failures.join(', ')}</div>}
                  {validationResult.warnings?.length > 0 && <div>Warnings: {validationResult.warnings.join(', ')}</div>}
                </article>
              )}
              <form className="inline-form" onSubmit={submitSmokeRun}>
                <button type="submit">Run smoke test</button>
              </form>
              {(smokeList.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <strong>{item.public_id.slice(0, 8)}</strong> — {item.status}
                  <div>Loss: {item.initial_training_loss?.toFixed?.(3)} → {item.final_training_loss?.toFixed?.(3)},
                    validation: {item.validation_loss?.toFixed?.(3)}</div>
                  <div>Resume verified: {String(!!item.resume_verified)}, checkpoint: {item.checkpoint_checksum_sha256?.slice(0, 12) ?? 'none'}</div>
                  {item.degeneration_findings?.length > 0 && <div className="error-notice">Findings: {item.degeneration_findings.join(', ')}</div>}
                </article>
              ))}
            </>
          )}

          {tab === 'Readiness' && (
            <>
              <h3>Base-Model Pretraining Readiness Gate</h3>
              <form className="inline-form" onSubmit={submitReadiness}>
                <input placeholder="Dataset snapshot public ID" value={readinessForm.snapshot_id}
                  onChange={(event) => setReadinessForm({ ...readinessForm, snapshot_id: event.target.value })} required />
                <input placeholder="Tokenizer comparison public ID (optional)" value={readinessForm.comparison_id}
                  onChange={(event) => setReadinessForm({ ...readinessForm, comparison_id: event.target.value })} />
                <input placeholder="Resource estimate public ID (optional)" value={readinessForm.estimate_id}
                  onChange={(event) => setReadinessForm({ ...readinessForm, estimate_id: event.target.value })} />
                <input placeholder="Smoke run public ID (optional)" value={readinessForm.smoke_run_id}
                  onChange={(event) => setReadinessForm({ ...readinessForm, smoke_run_id: event.target.value })} />
                <button type="submit">Evaluate readiness</button>
              </form>
              {(readinessList.items ?? []).map((item) => (
                <button key={item.public_id} className="training-job-row" onClick={() => loadReadinessDetail(item.public_id)}>
                  <strong>{item.overall_result}</strong>
                  <span>{item.public_id.slice(0, 8)}</span>
                </button>
              ))}
              {readinessDetail && (
                <article>
                  <div><strong>Overall: {readinessDetail.overall_result}</strong></div>
                  {(readinessDetail.dimensions ?? []).map((dim) => (
                    <div key={dim.public_id}>{dim.dimension}: {dim.status}</div>
                  ))}
                  {readinessDetail.hard_failure_reasons?.length > 0 && (
                    <div className="notice error-notice">
                      Hard failures: {readinessDetail.hard_failure_reasons.join(', ')}
                    </div>
                  )}
                </article>
              )}
            </>
          )}
        </section>
      </div>
    </section>
  )
}
