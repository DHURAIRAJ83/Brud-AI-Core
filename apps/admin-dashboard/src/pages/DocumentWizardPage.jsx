import { useEffect, useRef, useState } from 'react'
import {
  chunkCoverageReport, confirmDatasetVersionBuild, documentDatasetVersionStatus, documentDetail,
  documentHandoffSplitPreview, documentHandoffs, documentPages, documentRepeatedElements,
  documentSftCandidateSummary, documentSftExports, documentTamilQualitySummary, documentWorkspace,
  documents, ingestDocumentSftHandoff, previewDocumentSftHandoff, proposeDatasetVersion,
  validateDocumentSftExport,
} from '../services/api.js'

const STEP_DEFINITIONS = [
  { key: 'upload', label: '1. Upload' },
  { key: 'extract', label: '2. Extract' },
  { key: 'review_pages', label: '3. Review Pages' },
  { key: 'cleanup', label: '4. Cleanup' },
  { key: 'tamil_quality', label: '5. Tamil Quality' },
  { key: 'chunks', label: '6. Create Chunks' },
  { key: 'sft_generate', label: '7. Generate SFT' },
  { key: 'sft_review', label: '8. Review Candidates' },
  { key: 'export', label: '9. Export JSONL' },
  { key: 'validate_export', label: '10. Validate Export' },
  { key: 'dataset_handoff', label: '11. Dataset Handoff' },
  { key: 'preview_split', label: '12. Preview Split' },
  { key: 'build_version', label: '13. Build Dataset Version' },
  { key: 'training_readiness', label: '14. Training Readiness' },
]

function computeSteps({
  document, pages, workspace, repeated, tamilSummary, chunkCoverage, sftSummary, exportsList,
  handoffs, datasetVersionStatus,
}) {
  const failedPages = pages.filter(item => item.extraction_status === 'failed').length
  const reviewCounts = workspace?.review_status_counts || {}
  const reviewed = (reviewCounts.approved || 0) + (reviewCounts.rejected || 0) + (reviewCounts.excluded || 0)
  const pendingRepeated = repeated.filter(item => item.status === 'suggested').length
  const chunkCount = Object.keys(chunkCoverage || {}).length
  const approvedSft = sftSummary?.approved_count || 0
  const totalSft = sftSummary?.total_candidates || 0
  const latestExport = exportsList[0] || null
  const latestHandoff = handoffs?.[0] || null
  const versionBuilt = datasetVersionStatus?.status === 'version_built'

  return {
    upload: {
      status: 'completed', pages_or_records_affected: document.page_count,
      blocking_issues: [], warnings: [], recommended_next_action: 'Proceed to extraction.',
    },
    extract: {
      status: failedPages > 0 ? 'needs_review' : pages.length ? 'completed' : 'not_started',
      pages_or_records_affected: pages.length,
      blocking_issues: failedPages > 0 ? [`${failedPages} page(s) failed extraction`] : [],
      warnings: [], recommended_next_action: failedPages > 0 ? 'Request an OCR/extraction rerun on failed pages.' : 'Review extracted pages.',
    },
    review_pages: {
      status: !pages.length ? 'blocked' : reviewed === pages.length ? 'completed' : (reviewCounts.pending || 0) === pages.length ? 'not_started' : 'in_progress',
      pages_or_records_affected: pages.length,
      blocking_issues: !pages.length ? ['no pages extracted yet'] : [],
      warnings: workspace?.low_confidence_page_count ? [`${workspace.low_confidence_page_count} low-confidence page(s)`] : [],
      recommended_next_action: 'Approve, correct, or exclude each page in Page Review.',
    },
    cleanup: {
      status: !repeated.length ? 'not_started' : pendingRepeated > 0 ? 'needs_review' : 'completed',
      pages_or_records_affected: repeated.length,
      blocking_issues: [], warnings: pendingRepeated > 0 ? [`${pendingRepeated} cleanup suggestion(s) pending review`] : [],
      recommended_next_action: !repeated.length ? 'Detect repeated headers/footers/page numbers.' : 'Review pending cleanup suggestions.',
    },
    tamil_quality: {
      status: !tamilSummary || !tamilSummary.total_issues ? 'not_started' : tamilSummary.pending_count > 0 ? 'needs_review' : 'ready',
      pages_or_records_affected: tamilSummary?.total_issues || 0,
      blocking_issues: [], warnings: tamilSummary?.pending_count ? [`${tamilSummary.pending_count} Tamil quality issue(s) pending`] : [],
      recommended_next_action: 'Run Tamil quality detection and review any pending issues.',
    },
    chunks: {
      status: reviewed < pages.length && pages.length > 0 ? 'blocked' : chunkCount > 0 ? 'completed' : 'not_started',
      pages_or_records_affected: chunkCount,
      blocking_issues: reviewed < pages.length && pages.length > 0 ? ['not every page is reviewed yet'] : [],
      warnings: [], recommended_next_action: 'Generate semantic chunks from approved pages in Chunk & Record Studio.',
    },
    sft_generate: {
      status: chunkCount === 0 ? 'blocked' : totalSft > 0 ? 'completed' : 'not_started',
      pages_or_records_affected: totalSft,
      blocking_issues: chunkCount === 0 ? ['no approved chunks yet'] : [],
      warnings: [], recommended_next_action: 'Generate SFT candidates from approved chunks (vision_required pages are automatically excluded).',
    },
    sft_review: {
      status: totalSft === 0 ? 'blocked' : approvedSft === totalSft ? 'completed' : 'needs_review',
      pages_or_records_affected: totalSft,
      blocking_issues: totalSft === 0 ? ['no SFT candidates generated yet'] : [],
      warnings: [], recommended_next_action: 'Approve, reject, or correct each SFT candidate.',
    },
    export: {
      status: approvedSft === 0 ? 'blocked' : latestExport ? 'completed' : 'ready',
      pages_or_records_affected: latestExport?.record_count || 0,
      blocking_issues: approvedSft === 0 ? ['no approved SFT candidates yet'] : [],
      warnings: [], recommended_next_action: latestExport ? `Latest export: ${latestExport.record_count} record(s), checksum ${latestExport.checksum_sha256.slice(0, 12)}…` : 'Export approved candidates to JSONL.',
    },
    validate_export: {
      status: !latestExport ? 'blocked' : 'ready',
      pages_or_records_affected: latestExport?.record_count || 0,
      blocking_issues: !latestExport ? ['no JSONL export yet'] : [],
      warnings: [], recommended_next_action: 'Re-derive the export checksum from disk and confirm it matches the stored manifest.',
    },
    dataset_handoff: {
      status: !latestExport ? 'blocked' : latestHandoff ? 'completed' : 'ready',
      pages_or_records_affected: latestHandoff?.imported_count || 0,
      blocking_issues: !latestExport ? ['no JSONL export yet'] : [],
      warnings: [], recommended_next_action: latestHandoff ? `${latestHandoff.imported_count} record(s) imported into dataset source ${latestHandoff.dataset_source_public_id.slice(0, 8)}…` : 'Preview then ingest the export into the dataset-record system.',
    },
    preview_split: {
      status: !latestHandoff ? 'blocked' : latestHandoff.dataset_build_public_id ? 'ready' : 'not_started',
      pages_or_records_affected: 0,
      blocking_issues: !latestHandoff ? ['no dataset handoff yet'] : !latestHandoff.dataset_build_public_id ? ['propose a dataset-version build first'] : [],
      warnings: [], recommended_next_action: 'Propose a dataset-version build, then preview its train/validation/test split and leakage checks.',
    },
    build_version: {
      status: !latestHandoff?.dataset_build_public_id ? 'blocked' : versionBuilt ? 'completed' : 'ready',
      pages_or_records_affected: 0,
      blocking_issues: !latestHandoff?.dataset_build_public_id ? ['no dataset-version build proposed yet'] : [],
      warnings: [], recommended_next_action: versionBuilt ? `Dataset version built: ${datasetVersionStatus.dataset_version_public_id?.slice(0, 8)}…` : 'Review the split preview, then confirm the build explicitly.',
    },
    training_readiness: {
      status: !versionBuilt ? 'blocked' : 'ready',
      pages_or_records_affected: latestExport?.record_count || 0,
      blocking_issues: !versionBuilt ? ['no dataset version has been built yet'] : [],
      warnings: [], recommended_next_action: 'Dataset version creation does not start training. Training requires a separate Admin approval on the Instruction Tuning page.',
    },
  }
}

const STEP_COUNT = STEP_DEFINITIONS.length

export default function DocumentWizardPage({
  onNavigate, initialDocumentPublicId, initialStep, onNavigationChange, onOpenDatasetVersion,
} = {}) {
  const [items, setItems] = useState([]), [selectedId, setSelectedId] = useState('')
  const [state, setState] = useState(null), [error, setError] = useState(''), [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const [handoffPreview, setHandoffPreview] = useState(null)
  const [splitPreview, setSplitPreview] = useState(null)
  const [datasetName, setDatasetName] = useState(''), [datasetVersion, setDatasetVersion] = useState('v1')
  const [notFound, setNotFound] = useState(false)
  const appliedDeepLinkRef = useRef('')

  useEffect(() => {
    documents().then(response => setItems(response.items)).catch(reason => setError(reason.message))
  }, [])

  // Re-applies `initialDocumentPublicId`/`initialStep` whenever they
  // change, not just on first mount -- browser Back/Forward changes these
  // props on an already-mounted DocumentWizardPage (never a remount), so a
  // mount-only effect would silently ignore it. Guarded by a ref so an
  // unrelated `items` reload never re-triggers the same deep link.
  useEffect(() => {
    if (!items.length || !initialDocumentPublicId) return
    const key = `${initialDocumentPublicId}:${initialStep || ''}`
    if (appliedDeepLinkRef.current === key) return
    appliedDeepLinkRef.current = key
    const match = items.find(item => item.public_id === initialDocumentPublicId)
    if (!match) { setNotFound(true); return }
    loadDocument(initialDocumentPublicId, { silent: true }).then(() => {
      if (initialStep && (initialStep < 1 || initialStep > STEP_COUNT)) {
        setNotice('The requested wizard step is unavailable -- showing the full guided status instead.')
      } else if (initialStep) {
        const stepKey = STEP_DEFINITIONS[initialStep - 1].key
        window.requestAnimationFrame?.(() => {
          const element = document.getElementById(`wizard-step-${stepKey}`)
          if (element && typeof element.scrollIntoView === 'function') element.scrollIntoView({ block: 'center' })
        })
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialDocumentPublicId, initialStep, items])

  async function loadDocument(publicId, { silent = false } = {}) {
    setSelectedId(publicId); setLoading(true); setError(''); setNotice(''); setNotFound(false)
    setHandoffPreview(null); setSplitPreview(null)
    // `silent` is used when this call is reconciling state TO match an
    // incoming deep-link URL (browser Back/Forward, or the initial load) --
    // pushing `step: null` here would overwrite the real `step` the URL
    // already carries, an instant before the effect below re-applies it.
    if (!silent) onNavigationChange?.(publicId, null)
    try {
      const [document, pageList, workspace, repeated, tamilSummary, chunkCoverage, sftSummary, exportsList, handoffsResponse, datasetVersionStatus] = await Promise.all([
        documentDetail(publicId), documentPages(publicId), documentWorkspace(publicId),
        documentRepeatedElements(publicId).catch(() => ({ items: [] })),
        documentTamilQualitySummary(publicId).catch(() => null),
        chunkCoverageReport(publicId).catch(() => ({})),
        documentSftCandidateSummary(publicId).catch(() => null),
        documentSftExports(publicId).then(response => response.items).catch(() => []),
        documentHandoffs(publicId).then(response => response.items).catch(() => []),
        documentDatasetVersionStatus(publicId).catch(() => null),
      ])
      setState({
        document, pages: pageList.items, workspace, repeated: repeated.items,
        tamilSummary, chunkCoverage, sftSummary, exportsList, handoffs: handoffsResponse,
        datasetVersionStatus,
      })
    } catch (reason) { setError(reason.message); setState(null) } finally { setLoading(false) }
  }

  const steps = state ? computeSteps(state) : null
  const latestExport = state?.exportsList?.[0] || null
  const latestHandoff = state?.handoffs?.[0] || null

  async function handleValidateExport() {
    setError(''); setNotice('')
    try {
      const result = await validateDocumentSftExport(selectedId, latestExport.public_id)
      setNotice(result.valid ? 'Export checksum verified -- matches the stored manifest.' : `Export validation failed: ${result.reason || 'checksum mismatch'}`)
    } catch (reason) { setError(reason.message) }
  }

  async function handlePreviewHandoff() {
    setError(''); setNotice('')
    try { setHandoffPreview(await previewDocumentSftHandoff(selectedId, latestExport.public_id)) }
    catch (reason) { setError(reason.message) }
  }

  async function handleConfirmIngest() {
    setError(''); setNotice('')
    try {
      await ingestDocumentSftHandoff(selectedId, latestExport.public_id)
      setHandoffPreview(null)
      // `loadDocument()` resets `notice` to '' at its own start (it's a
      // full document refresh, not just this handler's concern) -- setting
      // the success message *before* awaiting it would have the message
      // clobbered in the same render tick and never actually reach the
      // screen. Setting it after is the fix.
      await loadDocument(selectedId)
      setNotice('Records ingested into the dataset-record system.')
    } catch (reason) { setError(reason.message) }
  }

  async function handleProposeVersion() {
    setError(''); setNotice('')
    try {
      await proposeDatasetVersion(selectedId, latestHandoff.public_id, datasetName || `document-sft-${selectedId.slice(0, 8)}`, datasetVersion || 'v1')
      await loadDocument(selectedId)
      setNotice('Dataset-version build proposed as a draft (not yet built).')
    } catch (reason) { setError(reason.message) }
  }

  async function handlePreviewSplit() {
    setError(''); setNotice('')
    try { setSplitPreview(await documentHandoffSplitPreview(selectedId, latestHandoff.public_id)) }
    catch (reason) { setError(reason.message) }
  }

  async function handleConfirmBuild() {
    setError(''); setNotice('')
    try {
      await confirmDatasetVersionBuild(selectedId, latestHandoff.public_id)
      setSplitPreview(null)
      await loadDocument(selectedId)
      setNotice('Dataset version built. Training was NOT started -- it requires a separate Admin approval.')
    } catch (reason) { setError(reason.message) }
  }

  return <section className="documents-workspace">
    <header className="section-heading">
      <div><h2>Document Processing Wizard</h2><p>Guided status across Upload → Extract → Review → Cleanup → Tamil Quality → Chunks → SFT → Export → Dataset Handoff → Training Readiness. Every step reads real, current document state -- nothing here is simulated.</p></div>
    </header>
    <div className="panel-controls">
      <label>Document<select value={selectedId} onChange={event => loadDocument(event.target.value)}>
        <option value="">Select a document…</option>
        {items.map(item => <option key={item.public_id} value={item.public_id}>{item.original_filename} ({item.page_count} pages)</option>)}
      </select></label>
      <button onClick={() => onNavigate?.('Documents')}>Open Documents page</button>
    </div>
    {notFound && <div className="form-error" role="alert">The requested document was not found. Select a document below.</div>}
    {error && <div className="form-error" role="alert">{error}</div>}
    {notice && <div className="notice">{notice}</div>}
    {loading && <div className="notice">Loading wizard status…</div>}
    {!steps ? <div className="notice">Select a document to see its guided status.</div> : (
      <div className="candidate-list">
        {STEP_DEFINITIONS.map(({ key, label }) => {
          const info = steps[key]
          return <article key={key} id={`wizard-step-${key}`}>
            <header><strong>{label}</strong><span className="review-status-badge">{info.status.replaceAll('_', ' ')}</span></header>
            <p>{info.pages_or_records_affected} page(s)/record(s) affected</p>
            {info.blocking_issues.map(issue => <p className="row-warning" key={issue}>Blocked: {issue}</p>)}
            {info.warnings.map(warning => <p className="row-warning" key={warning}>{warning}</p>)}
            <p><em>Next:</em> {info.recommended_next_action}</p>
            {key === 'validate_export' && latestExport && (
              <button type="button" onClick={handleValidateExport}>Validate export checksum</button>
            )}
            {key === 'dataset_handoff' && latestExport && !latestHandoff && (
              <div className="panel-controls">
                <button type="button" onClick={handlePreviewHandoff}>Preview handoff</button>
                {handoffPreview && (
                  <div className="notice">
                    <p>{handoffPreview.eligible_count} eligible, {handoffPreview.duplicate_count} duplicate, {handoffPreview.lineage_missing_count} missing lineage of {handoffPreview.record_count} record(s).</p>
                    <button type="button" onClick={handleConfirmIngest}>Confirm ingestion (irreversible -- creates dataset records)</button>
                  </div>
                )}
              </div>
            )}
            {key === 'preview_split' && latestHandoff && !latestHandoff.dataset_build_public_id && (
              <div className="panel-controls">
                <input placeholder="dataset name" value={datasetName} onChange={event => setDatasetName(event.target.value)} />
                <input placeholder="version (e.g. v1)" value={datasetVersion} onChange={event => setDatasetVersion(event.target.value)} />
                <button type="button" onClick={handleProposeVersion}>Propose dataset-version build (draft only)</button>
              </div>
            )}
            {key === 'preview_split' && latestHandoff?.dataset_build_public_id && (
              <div className="panel-controls">
                <button type="button" onClick={handlePreviewSplit}>Preview split</button>
                {splitPreview && (
                  <div className="notice">
                    <p>Selected: {splitPreview.selected_records}, excluded: {splitPreview.excluded_records}, leakage: {splitPreview.leakage?.status}</p>
                    <p>Split counts: {JSON.stringify(splitPreview.split_counts)}</p>
                  </div>
                )}
              </div>
            )}
            {key === 'build_version' && latestHandoff?.dataset_build_public_id && steps.build_version.status !== 'completed' && (
              <button type="button" onClick={handleConfirmBuild} disabled={!splitPreview}>
                Confirm dataset-version build{!splitPreview ? ' (preview the split first)' : ''}
              </button>
            )}
            {key === 'build_version' && steps.build_version.status === 'completed' && (
              <button
                type="button"
                onClick={() => onOpenDatasetVersion
                  ? onOpenDatasetVersion(state.datasetVersionStatus.dataset_version_public_id)
                  : onNavigate?.('Datasets')}
              >
                Open resulting dataset version
              </button>
            )}
          </article>
        })}
      </div>
    )}
  </section>
}
