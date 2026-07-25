import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  activateCorpusPolicy,
  addCorpusCollectionMember,
  assessCorpusSegment,
  compareCorpusVersions,
  corpusBalancePolicies,
  corpusBuild,
  corpusBuildBalanceReport,
  corpusBuilds,
  corpusCollection,
  corpusCollections,
  corpusComparison,
  corpusContaminationRun,
  corpusDeduplicationRun,
  corpusExport,
  corpusExtractionRun,
  corpusManifest,
  corpusNormalizationRun,
  corpusPolicies,
  corpusSnapshot,
  corpusSnapshotsForSource,
  corpusSource,
  corpusSourceTrainingEligibility,
  corpusSources,
  corpusVersion,
  corpusVersions,
  createCorpusBalancePolicy,
  createCorpusBuild,
  createCorpusCollection,
  createCorpusContaminationRun,
  createCorpusDeduplicationRun,
  createCorpusExport,
  createCorpusExtractionRun,
  createCorpusLicence,
  createCorpusNormalizationRun,
  createCorpusPolicy,
  createCorpusSnapshot,
  createCorpusSource,
  createCorpusVersion,
  generateCorpusManifest,
  reviewCorpusLicence,
  segmentCorpusDocument,
  transitionCorpusSource,
  validateCorpusPolicy,
  verifyCorpusSourceOrigin,
} from '../services/api.js'

const NO_AUTO_TRAINING_NOTICE =
  'Only approved, provenance-complete, licence-compatible, privacy-safe content may enter a Brud AI training corpus. Finalizing a corpus export never starts model training automatically.'

const TABS = [
  'Overview', 'Policies', 'Sources & Licences', 'Snapshots & Extraction',
  'Normalization & Segmentation', 'Quality & Safety', 'Deduplication & Contamination',
  'Collections & Balance', 'Builds & Partitions', 'Versions, Export & Manifest', 'Compare',
]

export default function CorpusPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '', policies: [], sources: [] })
  const [panelError, setPanelError] = useState('')

  const [policyForm, setPolicyForm] = useState({ name: '' })

  const [sourceForm, setSourceForm] = useState({
    corpus_policy_public_id: '', title: '', source_type: 'manual_admin_text',
  })
  const [selectedSourceId, setSelectedSourceId] = useState('')
  const [sourceDetail, setSourceDetail] = useState(null)
  const [eligibility, setEligibility] = useState(null)
  const [licenceForm, setLicenceForm] = useState({
    licence_family: 'public_domain', ai_training_permitted: false,
  })
  const [reviewForm, setReviewForm] = useState({ review_status: 'approved' })
  const [licenceId, setLicenceId] = useState('')

  const [snapshotFiles, setSnapshotFiles] = useState('')
  const [snapshots, setSnapshots] = useState({ items: [] })
  const [selectedSnapshotId, setSelectedSnapshotId] = useState('')
  const [snapshotDetail, setSnapshotDetail] = useState(null)

  const [extractionMethod, setExtractionMethod] = useState('plain_text')
  const [extractionRunId, setExtractionRunId] = useState('')
  const [extractionRun, setExtractionRun] = useState(null)

  const [normalizationRunId, setNormalizationRunId] = useState('')
  const [normalizationRun, setNormalizationRun] = useState(null)

  const [segmentationStrategy, setSegmentationStrategy] = useState('heading_section')
  const [segmentIds, setSegmentIds] = useState([])
  const [assessments, setAssessments] = useState({})

  const [dedupThreshold, setDedupThreshold] = useState(0.85)
  const [dedupRunId, setDedupRunId] = useState('')
  const [dedupRun, setDedupRun] = useState(null)
  const [contaminationRunId, setContaminationRunId] = useState('')
  const [contaminationRun, setContaminationRun] = useState(null)

  const [collections, setCollections] = useState({ items: [] })
  const [collectionForm, setCollectionForm] = useState({ name: '' })
  const [selectedCollectionId, setSelectedCollectionId] = useState('')
  const [collectionDetail, setCollectionDetail] = useState(null)
  const [memberSegmentId, setMemberSegmentId] = useState('')
  const [balancePolicies, setBalancePolicies] = useState({ items: [] })
  const [balanceForm, setBalanceForm] = useState({ name: '', maximum_single_source_share: 0.3 })

  const [builds, setBuilds] = useState({ items: [] })
  const [buildForm, setBuildForm] = useState({
    corpus_policy_public_id: '', balance_policy_public_id: '', collection_public_ids: '',
  })
  const [selectedBuildId, setSelectedBuildId] = useState('')
  const [buildDetail, setBuildDetail] = useState(null)
  const [balanceReport, setBalanceReport] = useState(null)

  const [versions, setVersions] = useState({ items: [] })
  const [versionForm, setVersionForm] = useState({ semantic_version: '' })
  const [selectedVersionId, setSelectedVersionId] = useState('')
  const [versionDetail, setVersionDetail] = useState(null)
  const [exportDetail, setExportDetail] = useState(null)
  const [manifestDetail, setManifestDetail] = useState(null)

  const [compareLeft, setCompareLeft] = useState('')
  const [compareRight, setCompareRight] = useState('')
  const [comparisonResult, setComparisonResult] = useState(null)

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [policies, sources, snapshotList, collectionList, balanceList, buildList, versionList] =
        await Promise.all([
          corpusPolicies(), corpusSources(), Promise.resolve({ items: [] }),
          corpusCollections(), corpusBalancePolicies(), corpusBuilds(), corpusVersions(),
        ])
      setState({
        loading: false, error: '',
        policies: policies.items ?? [], sources: sources.items ?? [],
      })
      setCollections(collectionList)
      setBalancePolicies(balanceList)
      setBuilds(buildList)
      setVersions(versionList)
      void snapshotList
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function submitPolicy(event) {
    event.preventDefault()
    try {
      await createCorpusPolicy(policyForm)
      setPolicyForm({ name: '' })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runValidatePolicy(policyId) {
    try {
      await validateCorpusPolicy(policyId)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runActivatePolicy(policyId) {
    try {
      await activateCorpusPolicy(policyId)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitSource(event) {
    event.preventDefault()
    try {
      await createCorpusSource(sourceForm)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadSourceDetail(sourceId) {
    setSelectedSourceId(sourceId)
    setPanelError('')
    setSourceDetail(await corpusSource(sourceId).catch(() => null))
    setEligibility(await corpusSourceTrainingEligibility(sourceId).catch(() => null))
    setSnapshots(await corpusSnapshotsForSource(sourceId).catch(() => ({ items: [] })))
  }

  async function runTransition(target) {
    try {
      await transitionCorpusSource(selectedSourceId, { target_status: target })
      setPanelError('')
      await loadSourceDetail(selectedSourceId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runVerifyOrigin() {
    try {
      await verifyCorpusSourceOrigin(selectedSourceId, { evidence: 'Verified by admin in dashboard' })
      setPanelError('')
      await loadSourceDetail(selectedSourceId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitLicence(event) {
    event.preventDefault()
    try {
      const created = await createCorpusLicence(selectedSourceId, licenceForm)
      setLicenceId(created.public_id)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitLicenceReview(event) {
    event.preventDefault()
    try {
      await reviewCorpusLicence(licenceId, reviewForm)
      setPanelError('')
      await loadSourceDetail(selectedSourceId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitSnapshot(event) {
    event.preventDefault()
    try {
      const files = snapshotFiles
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .map((relative_path) => ({ relative_path }))
      await createCorpusSnapshot(selectedSourceId, { files })
      setPanelError('')
      await loadSourceDetail(selectedSourceId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadSnapshotDetail(snapshotId) {
    setSelectedSnapshotId(snapshotId)
    setSnapshotDetail(await corpusSnapshot(snapshotId).catch(() => null))
  }

  async function submitExtraction(event) {
    event.preventDefault()
    try {
      const created = await createCorpusExtractionRun(selectedSnapshotId, {
        extraction_method: extractionMethod,
      })
      setExtractionRunId(created.public_id)
      setExtractionRun(created)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadExtractionRun() {
    setExtractionRun(await corpusExtractionRun(extractionRunId).catch(() => null))
  }

  async function runNormalization() {
    try {
      const created = await createCorpusNormalizationRun(extractionRunId, {})
      setNormalizationRunId(created.public_id)
      setNormalizationRun(created)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadNormalizationRun() {
    setNormalizationRun(await corpusNormalizationRun(normalizationRunId).catch(() => null))
  }

  async function runSegmentation(documentId) {
    try {
      const result = await segmentCorpusDocument(documentId, { strategy: segmentationStrategy })
      setSegmentIds((prior) => [...prior, ...(result.segment_public_ids ?? [])])
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runAssessment(segmentId) {
    try {
      const result = await assessCorpusSegment(segmentId)
      setAssessments((prior) => ({ ...prior, [segmentId]: result }))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runDeduplication() {
    try {
      const created = await createCorpusDeduplicationRun({
        near_duplicate_threshold: Number(dedupThreshold),
      })
      setDedupRunId(created.public_id)
      setDedupRun(created)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadDedupRun() {
    setDedupRun(await corpusDeduplicationRun(dedupRunId).catch(() => null))
  }

  async function runContamination() {
    try {
      const created = await createCorpusContaminationRun({})
      setContaminationRunId(created.public_id)
      setContaminationRun(created)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadContaminationRun() {
    setContaminationRun(await corpusContaminationRun(contaminationRunId).catch(() => null))
  }

  async function submitCollection(event) {
    event.preventDefault()
    try {
      await createCorpusCollection(collectionForm)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadCollectionDetail(collectionId) {
    setSelectedCollectionId(collectionId)
    setCollectionDetail(await corpusCollection(collectionId).catch(() => null))
  }

  async function submitAddMember(event) {
    event.preventDefault()
    try {
      await addCorpusCollectionMember(selectedCollectionId, { segment_public_id: memberSegmentId })
      setPanelError('')
      await loadCollectionDetail(selectedCollectionId)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitBalancePolicy(event) {
    event.preventDefault()
    try {
      await createCorpusBalancePolicy({
        ...balanceForm, maximum_single_source_share: Number(balanceForm.maximum_single_source_share),
      })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitBuild(event) {
    event.preventDefault()
    try {
      const collectionIds = buildForm.collection_public_ids
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
      await createCorpusBuild({ ...buildForm, collection_public_ids: collectionIds })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadBuildDetail(buildId) {
    setSelectedBuildId(buildId)
    setBuildDetail(await corpusBuild(buildId).catch(() => null))
    setBalanceReport(await corpusBuildBalanceReport(buildId).catch(() => null))
  }

  async function submitVersion(event) {
    event.preventDefault()
    try {
      await createCorpusVersion(selectedBuildId, versionForm)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadVersionDetail(versionId) {
    setSelectedVersionId(versionId)
    setVersionDetail(await corpusVersion(versionId).catch(() => null))
    setExportDetail(null)
    setManifestDetail(null)
  }

  async function runExport() {
    try {
      setExportDetail(await createCorpusExport(selectedVersionId, {}))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateManifest() {
    try {
      setManifestDetail(await generateCorpusManifest(selectedVersionId))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runViewManifest() {
    setManifestDetail(await corpusManifest(selectedVersionId).catch(() => null))
  }

  async function runCompare() {
    try {
      const created = await compareCorpusVersions({
        left_version_public_id: compareLeft, right_version_public_id: compareRight,
      })
      setComparisonResult(created)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadComparison(id) {
    setComparisonResult(await corpusComparison(id).catch(() => null))
  }

  if (state.loading) return <section className="notice">Loading corpus builder…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Tamil Corpus Builder</h2>
          <p className="notice">{NO_AUTO_TRAINING_NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Corpus builder sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Sources</h3>
          {(state.sources ?? []).length === 0 && <article>No corpus sources yet.</article>}
          {(state.sources ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadSourceDetail(item.public_id)}>
              <strong>{item.title}</strong>
              <span>{item.status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              <div className="metric-grid">
                <StatusCard label="Policies" value={state.policies.length} tone="neutral" />
                <StatusCard label="Sources" value={state.sources.length} tone="neutral" />
                <StatusCard label="Collections" value={(collections.items ?? []).length} tone="neutral" />
                <StatusCard label="Builds" value={(builds.items ?? []).length} tone="neutral" />
                <StatusCard label="Versions" value={(versions.items ?? []).length} tone="neutral" />
              </div>
              <p className="notice">
                Pipeline: trusted source → licence and provenance review → immutable snapshot →
                extraction → Tamil-safe normalization → cleaning and quality checks → privacy and
                safety filtering → deduplication → language/domain labelling → balancing →
                immutable corpus version → future pretraining export.
              </p>
            </>
          )}

          {tab === 'Policies' && (
            <>
              <h3>Corpus Policies</h3>
              <form className="inline-form" onSubmit={submitPolicy}>
                <input placeholder="Policy name" value={policyForm.name}
                  onChange={(event) => setPolicyForm({ name: event.target.value })} required />
                <button type="submit">Create policy</button>
              </form>
              {(state.policies ?? []).map((policy) => (
                <article key={policy.public_id}>
                  <strong>{policy.name}</strong> — {policy.lifecycle_status}
                  <div>min segment chars: {policy.minimum_segment_characters}</div>
                  <div className="inline-form">
                    <button disabled={policy.lifecycle_status !== 'draft'}
                      onClick={() => runValidatePolicy(policy.public_id)}>Validate</button>
                    <button disabled={policy.lifecycle_status !== 'validated'}
                      onClick={() => runActivatePolicy(policy.public_id)}>Activate</button>
                  </div>
                </article>
              ))}
            </>
          )}

          {tab === 'Sources & Licences' && (
            <>
              <h3>Register Source</h3>
              <form className="inline-form" onSubmit={submitSource}>
                <select value={sourceForm.corpus_policy_public_id}
                  onChange={(event) => setSourceForm({ ...sourceForm, corpus_policy_public_id: event.target.value })} required>
                  <option value="">Policy…</option>
                  {state.policies.map((policy) => (
                    <option key={policy.public_id} value={policy.public_id}>{policy.name}</option>
                  ))}
                </select>
                <input placeholder="Title" value={sourceForm.title}
                  onChange={(event) => setSourceForm({ ...sourceForm, title: event.target.value })} required />
                <input placeholder="Source type" value={sourceForm.source_type}
                  onChange={(event) => setSourceForm({ ...sourceForm, source_type: event.target.value })} required />
                <button type="submit">Register</button>
              </form>

              {sourceDetail && (
                <>
                  <h4>{sourceDetail.title} ({sourceDetail.status})</h4>
                  <div className="inline-form">
                    <button onClick={() => runTransition('origin_review')}>→ origin_review</button>
                    <button onClick={() => runTransition('licence_review')}>→ licence_review</button>
                    <button onClick={() => runTransition('approved')}>→ approved</button>
                    <button onClick={() => runTransition('rejected')}>→ rejected</button>
                    <button onClick={runVerifyOrigin}>Verify origin</button>
                  </div>
                  {eligibility && (
                    <p className={eligibility.eligible ? 'notice' : 'notice error-notice'}>
                      Training eligible: {String(eligibility.eligible)}
                      {eligibility.blocking_reasons?.length > 0 &&
                        ` (${eligibility.blocking_reasons.join(', ')})`}
                    </p>
                  )}

                  <h4>Licence</h4>
                  <form className="inline-form" onSubmit={submitLicence}>
                    <select value={licenceForm.licence_family}
                      onChange={(event) => setLicenceForm({ ...licenceForm, licence_family: event.target.value })}>
                      <option value="public_domain">public_domain</option>
                      <option value="cc0">cc0</option>
                      <option value="cc_by">cc_by</option>
                      <option value="government_open_data">government_open_data</option>
                      <option value="organisation_owned">organisation_owned</option>
                      <option value="all_rights_reserved">all_rights_reserved</option>
                      <option value="unknown">unknown</option>
                    </select>
                    <label>
                      <input type="checkbox" checked={licenceForm.ai_training_permitted}
                        onChange={(event) => setLicenceForm({ ...licenceForm, ai_training_permitted: event.target.checked })} />
                      AI training permitted
                    </label>
                    <button type="submit">Record licence</button>
                  </form>
                  <form className="inline-form" onSubmit={submitLicenceReview}>
                    <input placeholder="Licence public ID" value={licenceId}
                      onChange={(event) => setLicenceId(event.target.value)} required />
                    <select value={reviewForm.review_status}
                      onChange={(event) => setReviewForm({ review_status: event.target.value })}>
                      <option value="approved">approved</option>
                      <option value="approved_with_conditions">approved_with_conditions</option>
                      <option value="restricted">restricted</option>
                      <option value="blocked">blocked</option>
                      <option value="disputed">disputed</option>
                    </select>
                    <button type="submit">Review licence</button>
                  </form>

                  <h4>Snapshots</h4>
                  <form className="inline-form" onSubmit={submitSnapshot}>
                    <textarea placeholder="One approved relative file path per line"
                      value={snapshotFiles} onChange={(event) => setSnapshotFiles(event.target.value)} required />
                    <button type="submit">Create snapshot</button>
                  </form>
                  {(snapshots.items ?? []).map((snapshot) => (
                    <button key={snapshot.public_id} className="training-job-row"
                      onClick={() => loadSnapshotDetail(snapshot.public_id)}>
                      <strong>v{snapshot.version_number}</strong>
                      <span>{snapshot.status} — {snapshot.total_files} files</span>
                    </button>
                  ))}
                </>
              )}
            </>
          )}

          {tab === 'Snapshots & Extraction' && (
            <>
              <h3>Snapshot Detail</h3>
              {snapshotDetail && (
                <article>
                  <div>Snapshot: {snapshotDetail.public_id}</div>
                  <div>Files: {(snapshotDetail.files ?? []).length}</div>
                </article>
              )}
              <h3>Extraction</h3>
              <form className="inline-form" onSubmit={submitExtraction}>
                <select value={extractionMethod} onChange={(event) => setExtractionMethod(event.target.value)}>
                  <option value="plain_text">plain_text</option>
                  <option value="markdown_text">markdown_text</option>
                  <option value="html_snapshot_text">html_snapshot_text</option>
                  <option value="embedded_pdf_text">embedded_pdf_text</option>
                  <option value="tesseract_ocr">tesseract_ocr</option>
                  <option value="dataset_record_projection">dataset_record_projection</option>
                  <option value="manual_content">manual_content</option>
                </select>
                <button type="submit">Run extraction on selected snapshot</button>
              </form>
              <div className="inline-form">
                <input placeholder="Extraction run public ID" value={extractionRunId}
                  onChange={(event) => setExtractionRunId(event.target.value)} />
                <button onClick={loadExtractionRun}>Load</button>
              </div>
              {extractionRun && (
                <article>
                  <div>Status: {extractionRun.status}</div>
                  <div>Documents created: {extractionRun.documents_created}</div>
                  <div>Failed files: {extractionRun.failed_files}</div>
                </article>
              )}
            </>
          )}

          {tab === 'Normalization & Segmentation' && (
            <>
              <h3>Normalization</h3>
              <div className="inline-form">
                <button onClick={runNormalization}>Run normalization on extraction run above</button>
                <input placeholder="Normalization run public ID" value={normalizationRunId}
                  onChange={(event) => setNormalizationRunId(event.target.value)} />
                <button onClick={loadNormalizationRun}>Load</button>
              </div>
              {normalizationRun && (
                <article>
                  <div>Status: {normalizationRun.status}</div>
                  <h4>Documents</h4>
                  {(normalizationRun.documents ?? []).map((document) => (
                    <div key={document.public_id} className="inline-form">
                      <span>{document.public_id.slice(0, 8)} — {document.unicode_integrity_status}</span>
                      <select value={segmentationStrategy} onChange={(event) => setSegmentationStrategy(event.target.value)}>
                        <option value="heading_section">heading_section</option>
                        <option value="paragraph">paragraph</option>
                        <option value="sentence_group">sentence_group</option>
                        <option value="record_based">record_based</option>
                        <option value="fixed_character_window">fixed_character_window</option>
                      </select>
                      <button onClick={() => runSegmentation(document.public_id)}>Segment</button>
                    </div>
                  ))}
                </article>
              )}
              <h4>Segments produced this session</h4>
              {segmentIds.map((segmentId) => (
                <div key={segmentId} className="inline-form">
                  <span>{segmentId.slice(0, 8)}</span>
                  <button onClick={() => runAssessment(segmentId)}>Assess quality/privacy/safety</button>
                  {assessments[segmentId] && (
                    <span>
                      {assessments[segmentId].overall_verdict} ({assessments[segmentId].quality_band})
                    </span>
                  )}
                </div>
              ))}
            </>
          )}

          {tab === 'Quality & Safety' && (
            <>
              <h3>Segment Assessments</h3>
              {Object.entries(assessments).map(([segmentId, result]) => (
                <article key={segmentId}>
                  <strong>{segmentId.slice(0, 8)}</strong> — {result.overall_verdict} / {result.quality_band}
                  <div>Language: {result.language?.language_category}</div>
                  <div>Domain: {result.domain?.primary_domain}</div>
                  <div>Privacy: {result.privacy_status} · Safety: {result.safety_status}</div>
                  <div>Licence: {result.licence_status} · Provenance complete: {String(result.provenance_complete)}</div>
                </article>
              ))}
              {Object.keys(assessments).length === 0 && (
                <p className="notice">Run assessments from the Normalization &amp; Segmentation tab.</p>
              )}
            </>
          )}

          {tab === 'Deduplication & Contamination' && (
            <>
              <h3>Deduplication</h3>
              <div className="inline-form">
                <input type="number" step="0.01" min="0" max="1" value={dedupThreshold}
                  onChange={(event) => setDedupThreshold(event.target.value)} />
                <button onClick={runDeduplication}>Run corpus-wide deduplication</button>
                <input placeholder="Run public ID" value={dedupRunId} onChange={(event) => setDedupRunId(event.target.value)} />
                <button onClick={loadDedupRun}>Load</button>
              </div>
              {dedupRun && (
                <article>
                  <div>Status: {dedupRun.status}</div>
                  <div>Exact duplicates: {dedupRun.exact_duplicate_count}</div>
                  <div>Near duplicates: {dedupRun.near_duplicate_count}</div>
                </article>
              )}

              <h3>Contamination</h3>
              <div className="inline-form">
                <button onClick={runContamination}>Run corpus-wide contamination check</button>
                <input placeholder="Run public ID" value={contaminationRunId} onChange={(event) => setContaminationRunId(event.target.value)} />
                <button onClick={loadContaminationRun}>Load</button>
              </div>
              {contaminationRun && (
                <article>
                  <div>Status: {contaminationRun.status}</div>
                  <div>Findings: {contaminationRun.findings_count}</div>
                </article>
              )}
            </>
          )}

          {tab === 'Collections & Balance' && (
            <>
              <h3>Collections</h3>
              <form className="inline-form" onSubmit={submitCollection}>
                <input placeholder="Collection name" value={collectionForm.name}
                  onChange={(event) => setCollectionForm({ name: event.target.value })} required />
                <button type="submit">Create collection</button>
              </form>
              {(collections.items ?? []).map((collection) => (
                <button key={collection.public_id} className="training-job-row"
                  onClick={() => loadCollectionDetail(collection.public_id)}>
                  <strong>{collection.name}</strong>
                  <span>{collection.lifecycle_status}</span>
                </button>
              ))}
              {collectionDetail && (
                <>
                  <form className="inline-form" onSubmit={submitAddMember}>
                    <input placeholder="Segment public ID" value={memberSegmentId}
                      onChange={(event) => setMemberSegmentId(event.target.value)} required />
                    <button type="submit">Add member</button>
                  </form>
                  <div>Members: {(collectionDetail.members ?? []).length}</div>
                </>
              )}

              <h3>Balance Policies</h3>
              <form className="inline-form" onSubmit={submitBalancePolicy}>
                <input placeholder="Policy name" value={balanceForm.name}
                  onChange={(event) => setBalanceForm({ ...balanceForm, name: event.target.value })} required />
                <input type="number" step="0.01" min="0" max="1" value={balanceForm.maximum_single_source_share}
                  onChange={(event) => setBalanceForm({ ...balanceForm, maximum_single_source_share: event.target.value })} />
                <button type="submit">Create balance policy</button>
              </form>
              {(balancePolicies.items ?? []).map((policy) => (
                <article key={policy.public_id}>{policy.name} — cap {policy.maximum_single_source_share}</article>
              ))}
            </>
          )}

          {tab === 'Builds & Partitions' && (
            <>
              <h3>Builds</h3>
              <form className="inline-form" onSubmit={submitBuild}>
                <select value={buildForm.corpus_policy_public_id}
                  onChange={(event) => setBuildForm({ ...buildForm, corpus_policy_public_id: event.target.value })} required>
                  <option value="">Policy…</option>
                  {state.policies.map((policy) => <option key={policy.public_id} value={policy.public_id}>{policy.name}</option>)}
                </select>
                <select value={buildForm.balance_policy_public_id}
                  onChange={(event) => setBuildForm({ ...buildForm, balance_policy_public_id: event.target.value })} required>
                  <option value="">Balance policy…</option>
                  {(balancePolicies.items ?? []).map((policy) => <option key={policy.public_id} value={policy.public_id}>{policy.name}</option>)}
                </select>
                <input placeholder="Collection IDs, comma separated" value={buildForm.collection_public_ids}
                  onChange={(event) => setBuildForm({ ...buildForm, collection_public_ids: event.target.value })} required />
                <button type="submit">Create build</button>
              </form>
              {(builds.items ?? []).map((build) => (
                <button key={build.public_id} className="training-job-row" onClick={() => loadBuildDetail(build.public_id)}>
                  <strong>{build.public_id.slice(0, 8)}</strong>
                  <span>{build.status} — {build.included_segment_count} included</span>
                </button>
              ))}
              {buildDetail && (
                <article>
                  <div>Partitions:</div>
                  {(buildDetail.partitions ?? []).map((partition) => (
                    <div key={partition.public_id}>{partition.split}: {partition.segment_count} segments</div>
                  ))}
                  {balanceReport && <pre>{JSON.stringify(balanceReport, null, 2)}</pre>}
                </article>
              )}
            </>
          )}

          {tab === 'Versions, Export & Manifest' && (
            <>
              <h3>Versions</h3>
              <form className="inline-form" onSubmit={submitVersion}>
                <input placeholder="Build public ID (selected from Builds tab)" value={selectedBuildId}
                  onChange={(event) => setSelectedBuildId(event.target.value)} required />
                <input placeholder="Semantic version, e.g. 1.0.0" value={versionForm.semantic_version}
                  onChange={(event) => setVersionForm({ semantic_version: event.target.value })} required />
                <button type="submit">Create version</button>
              </form>
              {(versions.items ?? []).map((version) => (
                <button key={version.public_id} className="training-job-row" onClick={() => loadVersionDetail(version.public_id)}>
                  <strong>{version.semantic_version}</strong>
                  <span>{version.status} — {version.train_segment_count} train segments</span>
                </button>
              ))}
              {versionDetail && (
                <>
                  <div className="inline-form">
                    <button onClick={runExport}>Export corpus version</button>
                    <button onClick={runGenerateManifest}>Generate manifest</button>
                    <button onClick={runViewManifest}>View manifest</button>
                  </div>
                  {exportDetail && (
                    <article>
                      <div>Export status: {exportDetail.status}</div>
                      <div>Shards: {(exportDetail.shards ?? []).length}, records: {exportDetail.total_records}</div>
                      <p className="notice">{exportDetail.notice}</p>
                    </article>
                  )}
                  {manifestDetail && (
                    <article>
                      <div>Manifest checksum: {manifestDetail.manifest_checksum_sha256}</div>
                    </article>
                  )}
                </>
              )}
            </>
          )}

          {tab === 'Compare' && (
            <>
              <h3>Compare Corpus Versions</h3>
              <div className="inline-form">
                <input placeholder="Left version public ID" value={compareLeft} onChange={(event) => setCompareLeft(event.target.value)} />
                <input placeholder="Right version public ID" value={compareRight} onChange={(event) => setCompareRight(event.target.value)} />
                <button onClick={runCompare}>Compare</button>
                <input placeholder="Existing comparison public ID" onBlur={(event) => event.target.value && loadComparison(event.target.value)} />
              </div>
              {comparisonResult && (
                <article>
                  <div>Compatibility: {comparisonResult.compatibility}</div>
                  <pre>{JSON.stringify(comparisonResult.comparison, null, 2)}</pre>
                </article>
              )}
            </>
          )}
        </section>
      </div>
    </section>
  )
}
