import { useEffect, useRef, useState } from 'react'
import {
  analyzeDocument, applyDocumentPageCleanup, approveDocumentPage, detectDocumentRepeatedElements,
  documentCandidateAction, documentCandidates, documentCapabilities, documentDetail, documentJobEvents,
  documentJobs, documentPage, documentPageCleanupSuggestions, documentPageExtractions, documentPageImageUrl,
  documentPageReviewEvents, documentPageRevisions, documentPages, documentRepeatedElements,
  documentReviewSummary, documentWorkspace, documents, downloadDocumentReport, editDocumentCandidate,
  editDocumentPage, excludeDocumentPage, importDocumentCandidates, linkDocumentSource, processDocument,
  rejectDocumentPage, reopenDocumentPage, reprocessDocumentPage, requestDocumentPageCorrection,
  requestDocumentPageExtractionRerun, requestDocumentPageOcrRerun, restoreDocumentPageRevision,
  reviewDocumentRepeatedElement, segmentDocument, sendDocumentToSegmentation, uploadDocument,
  detectDocumentTamilQuality, documentTamilQualityIssues, documentTamilQualitySummary,
  reviewDocumentTamilQualityIssue, generateDocumentSftCandidates, documentSftCandidates,
  documentSftCandidateSummary, reviewDocumentSftCandidate, bulkApproveDocumentSftCandidates,
  exportDocumentSftCandidates, scanDocumentSecurityFindings, documentSecurityFindings,
  documentPiiFindings, reviewDocumentSecurityFinding, scanDocumentContentClassifications,
  documentContentClassifications, tamilCorrectionRules, createTamilCorrectionRule,
  reviewTamilCorrectionRule,
} from '../services/api.js'
import { DOCUMENT_NAV_TARGETS } from '../services/documentNavigation.js'

const tabs = [
  'Overview', 'Upload', 'Processing', 'Page Review', 'Repeated Elements', 'Tamil Quality',
  'Candidates', 'SFT Candidates', 'Export', 'Security Review', 'Media & Tables', 'Tamil Corrections',
]

const CRITICAL_FILTERS = ['All', 'Critical only', 'OCR issues', 'Tamil issues', 'Unreviewed', 'Reviewed', 'Approved', 'Excluded']

// Resolves an incoming deep-link `tab` value (either a literal tab label or a
// semantic key from documentNavigation.js, e.g. from an Admin Assistant
// navigation button) to a real tab label plus optional page-filter -- never
// trusted directly as a tab label without this validation.
function resolveIncomingTab(requestedTab) {
  if (!requestedTab) return { tabLabel: null, pageFilter: null, valid: true }
  if (tabs.includes(requestedTab)) return { tabLabel: requestedTab, pageFilter: null, valid: true }
  const target = DOCUMENT_NAV_TARGETS[requestedTab]
  if (target && target.navKey === 'Documents' && target.documentsTab) {
    return {
      tabLabel: target.documentsTab,
      pageFilter: requestedTab === 'critical-pages' ? 'Critical only' : null,
      valid: true,
    }
  }
  return { tabLabel: 'Overview', pageFilter: null, valid: false }
}

export default function DocumentsPage({ initialDocumentPublicId, initialTab, onNavigationChange } = {}) {
  const [tab, setTab] = useState('Overview'), [capabilities, setCapabilities] = useState(null), [items, setItems] = useState([])
  const [selected, setSelected] = useState(null), [pages, setPages] = useState([]), [page, setPage] = useState(null), [candidates, setCandidates] = useState([]), [jobs, setJobs] = useState([]), [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState(''), [confirm, setConfirm] = useState(false)
  const [workspace, setWorkspace] = useState(null), [sourceInput, setSourceInput] = useState('')
  const [imageUrl, setImageUrl] = useState(''), [revisions, setRevisions] = useState([]), [reviewEvents, setReviewEvents] = useState([])
  const [suggestions, setSuggestions] = useState([]), [repeated, setRepeated] = useState([])
  const [pageFilter, setPageFilter] = useState('All')
  const [tamilIssues, setTamilIssues] = useState([]), [tamilSummary, setTamilSummary] = useState(null)
  const [sftItems, setSftItems] = useState([]), [sftSummary, setSftSummary] = useState(null)
  const [exportResult, setExportResult] = useState(null)
  const [securityFindings, setSecurityFindings] = useState([]), [piiFindings, setPiiFindings] = useState([])
  const [classifications, setClassifications] = useState([])
  const [tamilRules, setTamilRules] = useState([])
  const [notFound, setNotFound] = useState(false)
  const appliedDeepLinkRef = useRef('')

  async function refresh() {
    setLoading(true); setError('')
    try {
      const [ability, listing] = await Promise.all([documentCapabilities(), documents()])
      setCapabilities(ability); setItems(listing.items)
    } catch (reason) { setError(reason.message) } finally { setLoading(false) }
  }
  useEffect(() => { refresh() }, [])

  // Re-applies `initialDocumentPublicId`/`initialTab` whenever they change,
  // not just on first mount -- browser Back/Forward (a `popstate`-driven
  // prop change on an already-mounted DocumentsPage, never a remount) would
  // otherwise be silently ignored. Guarded by a ref so an unrelated
  // `items` refresh (e.g. after an upload) never re-triggers the same
  // deep link and clobbers whatever the admin just selected.
  useEffect(() => {
    if (!items.length || !initialDocumentPublicId) return
    const key = `${initialDocumentPublicId}:${initialTab || ''}`
    if (appliedDeepLinkRef.current === key) return
    appliedDeepLinkRef.current = key
    const match = items.find(item => item.public_id === initialDocumentPublicId)
    if (!match) { setNotFound(true); return }
    const resolved = resolveIncomingTab(initialTab)
    if (!resolved.valid) setNotice('The requested tab is unavailable -- showing the default view instead.')
    if (resolved.pageFilter) setPageFilter(resolved.pageFilter)
    open(match, { keepTab: true, silent: true }).then(() => setTab(resolved.tabLabel || 'Processing'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialDocumentPublicId, initialTab, items])

  function changeTab(nextTab) {
    setTab(nextTab)
    onNavigationChange?.(selected?.public_id, nextTab)
  }

  async function refreshWorkspace(publicId) { try { setWorkspace(await documentWorkspace(publicId)) } catch (reason) { setError(reason.message) } }

  async function open(document, { keepTab = false, silent = false } = {}) {
    setBusy('details'); setNotFound(false)
    try {
      const [detail, pageList, candidateList, jobList] = await Promise.all([
        documentDetail(document.public_id), documentPages(document.public_id),
        documentCandidates(document.public_id), documentJobs(document.public_id),
      ])
      setSelected(detail); setPages(pageList.items); setCandidates(candidateList.items); setJobs(jobList.items)
      if (!keepTab) setTab('Processing')
      // `silent` is used when this call is itself reconciling state TO
      // match an incoming deep-link URL (browser Back/Forward, or the
      // initial load) -- the URL is already correct in that case, so
      // pushing a new history entry here would both be redundant and, worse,
      // race the resolved tab: this closure's own `tab` value is still the
      // *previous* render's value, so a non-silent call here would push the
      // wrong tab into the URL an instant before `changeTab`/the caller
      // corrects the on-screen tab, corrupting the history stack.
      if (!silent) onNavigationChange?.(document.public_id, keepTab ? tab : 'Processing')
      if (jobList.items[0]) setEvents((await documentJobEvents(jobList.items[0].public_id)).items)
      await refreshWorkspace(document.public_id)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function action(label, callback, options = {}) {
    setBusy(label); setError('')
    try {
      await callback()
      setNotice(`${label} completed.`)
      const detail = await documentDetail(selected.public_id)
      // Always silent: this `open()` call is a post-mutation data refresh,
      // not a real navigation event. Without `silent`, its own async
      // `onNavigationChange` call can resolve *after* the admin has already
      // navigated elsewhere (e.g. clicked "Document Wizard" in the
      // Sidebar right after an export), snapping the app back to
      // Documents underneath them -- a genuine race, not a hypothetical.
      await open(detail, { ...options, silent: true })
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function openPage(number) {
    try {
      const detail = await documentPage(selected.public_id, number)
      setPage(detail)
      setTab('Page Review')
      if (imageUrl) URL.revokeObjectURL(imageUrl)
      const [image, revisionList, eventList] = await Promise.all([
        documentPageImageUrl(selected.public_id, number).catch(() => ''),
        documentPageRevisions(selected.public_id, number),
        documentPageReviewEvents(selected.public_id, number),
      ])
      setImageUrl(image); setRevisions(revisionList.items); setReviewEvents(eventList.items); setSuggestions([])
    } catch (reason) { setError(reason.message) }
  }

  async function reviewAction(label, callback) {
    setBusy(label); setError('')
    try {
      await callback()
      setNotice(`${label} recorded.`)
      await openPage(page.page_number)
      await refreshWorkspace(selected.public_id)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function loadSuggestions() {
    try { setSuggestions((await documentPageCleanupSuggestions(selected.public_id, page.page_number)).items) } catch (reason) { setError(reason.message) }
  }

  async function applySuggestions(selectedSuggestions) {
    await reviewAction('Cleanup applied', () => applyDocumentPageCleanup(selected.public_id, page.page_number, selectedSuggestions))
  }

  async function loadRepeated() {
    try { setRepeated((await documentRepeatedElements(selected.public_id)).items) } catch (reason) { setError(reason.message) }
  }

  async function loadTamilQuality() {
    try {
      const [issues, summary] = await Promise.all([documentTamilQualityIssues(selected.public_id), documentTamilQualitySummary(selected.public_id)])
      setTamilIssues(issues.items); setTamilSummary(summary)
    } catch (reason) { setError(reason.message) }
  }

  async function loadSftCandidates() {
    try {
      const [list, summary] = await Promise.all([documentSftCandidates(selected.public_id), documentSftCandidateSummary(selected.public_id)])
      setSftItems(list.items); setSftSummary(summary)
    } catch (reason) { setError(reason.message) }
  }

  async function loadSecurityFindings() {
    try {
      const [all, pii] = await Promise.all([
        documentSecurityFindings(selected.public_id), documentPiiFindings(selected.public_id),
      ])
      setSecurityFindings(all.items); setPiiFindings(pii.items)
    } catch (reason) { setError(reason.message) }
  }

  async function loadClassifications() {
    try { setClassifications((await documentContentClassifications(selected.public_id)).items) } catch (reason) { setError(reason.message) }
  }

  async function loadTamilRules() {
    try { setTamilRules((await tamilCorrectionRules()).items) } catch (reason) { setError(reason.message) }
  }

  async function report() { try { const blob = await downloadDocumentReport(selected.public_id); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `brud-document-${selected.public_id}.csv`; anchor.click(); URL.revokeObjectURL(url); setNotice('Bounded document report created.') } catch (reason) { setError(reason.message) } }

  return <section className="documents-workspace">
    <header className="section-heading"><div><h2>Documents</h2><p>Secure local PDF extraction, page review, and draft candidate import.</p></div><button onClick={refresh}>Refresh</button></header>
    <div className="dataset-tabs">{tabs.map(value => <button key={value} className={tab === value ? 'active' : ''} onClick={() => changeTab(value)}>{value}</button>)}</div>
    {notFound && <div className="form-error" role="alert">The requested document was not found. Showing the document list instead.</div>}
    {notice && <div className="success-note" role="status">{notice}</div>}{error && <div className="form-error" role="alert">{error}</div>}
    {tab === 'Upload' ? <DocumentUpload capabilities={capabilities} busy={busy} submit={async form => { setBusy('upload'); setError(''); try { const document = await uploadDocument(form); setNotice('PDF validated and registered.'); await refresh(); await open(document) } catch (reason) { setError(reason.message) } finally { setBusy('') } }} />
      : loading ? <div className="notice">Loading document workspace…</div>
      : tab === 'Overview' ? <DocumentOverview items={items} capabilities={capabilities} open={open} />
      : !selected ? <div className="notice">Open a document from Overview first.</div>
      : tab === 'Processing' ? <DocumentProcessing
          document={selected} pages={pages} jobs={jobs} events={events} busy={busy} workspace={workspace}
          sourceInput={sourceInput} setSourceInput={setSourceInput}
          pageFilter={pageFilter} setPageFilter={setPageFilter} tamilIssues={tamilIssues}
          analyze={() => action('Analysis', () => analyzeDocument(selected.public_id))}
          process={() => action('Extraction', () => processDocument(selected.public_id, { strategy: selected.extraction_strategy }))}
          linkSource={() => action('Source linked', () => linkDocumentSource(selected.public_id, sourceInput))}
          sendToSegmentation={() => action('Sent to segmentation', () => sendDocumentToSegmentation(selected.public_id, { mode: 'paragraph_as_pretrain', language: selected.detected_language }))}
          openPage={openPage} report={report}
        />
      : tab === 'Page Review' ? <PageReview
          page={page} pages={pages} busy={busy} openPage={openPage} imageUrl={imageUrl} revisions={revisions}
          reviewEvents={reviewEvents} suggestions={suggestions} loadSuggestions={loadSuggestions}
          applySuggestions={applySuggestions}
          save={(text, changeSummary) => reviewAction('Page edit', () => editDocumentPage(selected.public_id, page.page_number, { cleaned_text: text, change_summary: changeSummary }))}
          reprocess={() => reviewAction('Page reprocessing', () => reprocessDocumentPage(selected.public_id, page.page_number, { strategy: 'auto' }))}
          approve={() => reviewAction('Approve', () => approveDocumentPage(selected.public_id, page.page_number))}
          reject={() => reviewAction('Reject', () => rejectDocumentPage(selected.public_id, page.page_number))}
          exclude={() => reviewAction('Exclude', () => excludeDocumentPage(selected.public_id, page.page_number))}
          reopen={() => reviewAction('Reopen', () => reopenDocumentPage(selected.public_id, page.page_number))}
          requestCorrection={() => reviewAction('Correction requested', () => requestDocumentPageCorrection(selected.public_id, page.page_number))}
          requestOcrRerun={() => reviewAction('OCR rerun requested', () => requestDocumentPageOcrRerun(selected.public_id, page.page_number))}
          requestExtractionRerun={() => reviewAction('Extraction rerun requested', () => requestDocumentPageExtractionRerun(selected.public_id, page.page_number))}
          restoreRevision={(number) => reviewAction('Revision restored', () => restoreDocumentPageRevision(selected.public_id, page.page_number, number))}
        />
      : tab === 'Repeated Elements' ? <RepeatedElementsReview
          document={selected} repeated={repeated} busy={busy} loadRepeated={loadRepeated}
          detect={() => action('Repeated-element detection', async () => { await detectDocumentRepeatedElements(selected.public_id); await loadRepeated() }, { keepTab: true })}
          review={(elementId, actionName, options) => action('Repeated element reviewed', async () => { await reviewDocumentRepeatedElement(selected.public_id, elementId, actionName, options); await loadRepeated() }, { keepTab: true })}
        />
      : tab === 'Tamil Quality' ? <TamilQualityReview
          document={selected} issues={tamilIssues} summary={tamilSummary} busy={busy} loadTamilQuality={loadTamilQuality}
          detect={() => action('Tamil quality detection', async () => { await detectDocumentTamilQuality(selected.public_id); await loadTamilQuality() }, { keepTab: true })}
          review={(issueId, actionName, options) => action('Tamil quality issue reviewed', async () => { await reviewDocumentTamilQualityIssue(selected.public_id, issueId, { action: actionName, ...options }); await loadTamilQuality() }, { keepTab: true })}
        />
      : tab === 'Candidates' ? <CandidateReview document={selected} candidates={candidates} busy={busy} confirmed={confirm} setConfirmed={setConfirm} segment={() => action('Segmentation', () => segmentDocument(selected.public_id, { mode: 'paragraph_as_pretrain', language: selected.detected_language }))} edit={(id, body) => action('Candidate edit', () => editDocumentCandidate(selected.public_id, id, body))} choose={(id, choice) => action(`Candidate ${choice}`, () => documentCandidateAction(selected.public_id, id, choice))} importCandidates={() => action('Candidate import', () => importDocumentCandidates(selected.public_id))} />
      : tab === 'SFT Candidates' ? <SftCandidateReview
          document={selected} items={sftItems} summary={sftSummary} busy={busy} loadSftCandidates={loadSftCandidates}
          generate={() => action('SFT candidate generation', async () => { await generateDocumentSftCandidates(selected.public_id, {}); await loadSftCandidates() }, { keepTab: true })}
          review={(candidateId, actionName, options) => action('SFT candidate reviewed', async () => { await reviewDocumentSftCandidate(selected.public_id, candidateId, { action: actionName, ...options }); await loadSftCandidates() }, { keepTab: true })}
          bulkApprove={(ids) => action('SFT candidates bulk-approved', async () => { await bulkApproveDocumentSftCandidates(selected.public_id, ids); await loadSftCandidates() }, { keepTab: true })}
        />
      : tab === 'Export' ? <SftExportPanel
          document={selected} summary={sftSummary} exportResult={exportResult} busy={busy} loadSftCandidates={loadSftCandidates}
          runExport={() => action('SFT export', async () => { setExportResult(await exportDocumentSftCandidates(selected.public_id)) }, { keepTab: true })}
        />
      : tab === 'Security Review' ? <SecurityReviewPanel
          document={selected} findings={securityFindings} piiFindings={piiFindings} busy={busy} load={loadSecurityFindings}
          scan={() => action('Security scan', async () => { await scanDocumentSecurityFindings(selected.public_id); await loadSecurityFindings() }, { keepTab: true })}
          review={(findingId, actionName) => action('Security finding reviewed', async () => { await reviewDocumentSecurityFinding(selected.public_id, findingId, actionName); await loadSecurityFindings() }, { keepTab: true })}
        />
      : tab === 'Media & Tables' ? <MediaClassificationPanel
          document={selected} classifications={classifications} busy={busy} load={loadClassifications}
          scan={() => action('Content classification scan', async () => { await scanDocumentContentClassifications(selected.public_id); await loadClassifications() }, { keepTab: true })}
        />
      : <TamilCorrectionRulesPanel
          rules={tamilRules} busy={busy} load={loadTamilRules}
          create={(body) => action('Tamil correction rule created', async () => { await createTamilCorrectionRule(body); await loadTamilRules() }, { keepTab: true })}
          review={(ruleId, actionName) => action('Tamil correction rule reviewed', async () => { await reviewTamilCorrectionRule(ruleId, actionName); await loadTamilRules() }, { keepTab: true })}
        />}
  </section>
}

function DocumentUpload({ capabilities, busy, submit }) {
  const [file, setFile] = useState(null), [strategy, setStrategy] = useState('auto'), [language, setLanguage] = useState('mixed')
  function send(event) { event.preventDefault(); const form = new FormData(); form.append('file', file); form.append('extraction_strategy', strategy); form.append('language', language); submit(form) }
  return <form className="document-upload" onSubmit={send}><h3>Upload PDF</h3><p>Maximum {Math.round((capabilities?.max_file_bytes || 0) / 1048576)} MB · {capabilities?.max_pages} pages · private local storage</p><label>PDF document<input type="file" accept="application/pdf,.pdf" onChange={event => setFile(event.target.files[0])} required /></label><label>Extraction strategy<select value={strategy} onChange={event => setStrategy(event.target.value)}><option value="auto">Automatic embedded/OCR</option><option value="embedded_text">Embedded text only</option><option value="ocr">OCR only</option><option value="hybrid">Hybrid</option></select></label><label>Preferred language<select value={language} onChange={event => setLanguage(event.target.value)}>{['ta','en','tgl','mixed','unknown'].map(value => <option key={value}>{value}</option>)}</select></label><div className={`capability ${capabilities?.ocr_available ? 'available' : 'unavailable'}`}><strong>{capabilities?.ocr_available ? 'OCR available' : 'OCR unavailable'}</strong><span>{capabilities?.ocr_languages?.join(', ') || 'Embedded extraction remains available'}</span></div><button disabled={Boolean(busy)}>{busy === 'upload' ? 'Uploading and validating…' : 'Upload securely'}</button>{busy === 'upload' && <progress aria-label="Document upload in progress" />}</form>
}

function DocumentOverview({ items, capabilities, open }) {
  const counts = Object.fromEntries(['processing','review_ready','completed','failed'].map(status => [status, items.filter(item => item.status === status).length]))
  return <><section className="metric-grid"><article className="status-card"><span>Total documents</span><strong>{items.length}</strong></article>{Object.entries(counts).map(([key,value]) => <article className="status-card" key={key}><span>{key.replace('_',' ')}</span><strong>{value}</strong></article>)}<article className="status-card"><span>OCR capability</span><strong>{capabilities?.ocr_available ? 'Tamil + English ready' : 'Unavailable'}</strong></article></section><h3>Document history</h3>{!items.length ? <div className="notice">No documents uploaded yet.</div> : <div className="document-list">{items.map(item => <button key={item.public_id} onClick={() => open(item)}><strong>{item.original_filename}</strong><span>{item.page_count} pages · {item.status}</span><span>{item.extraction_strategy} · {item.checksum_prefix}</span></button>)}</div>}</>
}

function isCriticalPage(item, tamilPageNumbers) {
  return item.extraction_status === 'failed' || (item.warnings?.length || 0) > 0
    || ['needs_correction', 'rejected'].includes(item.review_status) || tamilPageNumbers.has(item.page_number)
}

function filterPages(pages, filter, tamilPageNumbers) {
  switch (filter) {
    case 'Critical only': return pages.filter(item => isCriticalPage(item, tamilPageNumbers))
    case 'OCR issues': return pages.filter(item => item.extraction_status === 'failed' || (item.warnings?.length || 0) > 0)
    case 'Tamil issues': return pages.filter(item => tamilPageNumbers.has(item.page_number))
    case 'Unreviewed': return pages.filter(item => !item.review_status || item.review_status === 'pending')
    case 'Reviewed': return pages.filter(item => item.review_status && item.review_status !== 'pending')
    case 'Approved': return pages.filter(item => item.review_status === 'approved')
    case 'Excluded': return pages.filter(item => item.review_status === 'excluded')
    default: return pages
  }
}

function DocumentProcessing({ document, pages, jobs, events, busy, workspace, sourceInput, setSourceInput, pageFilter, setPageFilter, tamilIssues, analyze, process, linkSource, sendToSegmentation, openPage, report }) {
  const tamilPageNumbers = new Set((tamilIssues || []).filter(item => item.review_status === 'pending').map(item => item.page_number))
  const visiblePages = filterPages(pages, pageFilter, tamilPageNumbers)
  return <section className="document-detail">
    <header><div><h3>{document.original_filename}</h3><p>{document.file_size_bytes} bytes · {document.page_count} pages · {document.status}</p></div><span className="checksum">SHA-256 {document.checksum_prefix}</span></header>
    <div className="document-actions"><button disabled={Boolean(busy)} onClick={analyze}>Analyze pages</button><button disabled={Boolean(busy)} onClick={process}>Process {document.extraction_strategy}</button><button onClick={report}>Download report</button></div>

    <h4>Source &amp; readiness</h4>
    <div className="panel-controls">
      <label>Source public id<input value={sourceInput} onChange={event => setSourceInput(event.target.value)} placeholder="paste a source public_id from Sources & Rights" /></label>
      <button disabled={Boolean(busy) || !sourceInput} onClick={linkSource}>Link source</button>
    </div>
    {workspace && (
      <div className="history-panel">
        <p>Source: {workspace.source_status === 'linked' ? `${workspace.source.source_code} -- ${workspace.source.title}` : 'unlinked'}</p>
        {workspace.rights_warnings?.map(w => <p className="row-warning" key={w}>{w}</p>)}
        <p>Readiness: <strong>{workspace.readiness.replaceAll('_', ' ')}</strong></p>
        <section className="metric-grid">
          {Object.entries(workspace.review_status_counts || {}).map(([key, value]) => (
            <article className="status-card" key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{value}</strong></article>
          ))}
        </section>
        <p>{workspace.low_confidence_page_count} low-confidence page(s) · {workspace.pages_with_warnings_count} page(s) with warnings</p>
        <button disabled={Boolean(busy) || workspace.readiness === 'not_ready'} onClick={sendToSegmentation}>Send approved pages to existing segmentation</button>
      </div>
    )}

    <h4>Pages</h4>
    <div className="dataset-tabs" role="group" aria-label="Critical page filters">{CRITICAL_FILTERS.map(value => <button key={value} className={pageFilter === value ? 'active' : ''} onClick={() => setPageFilter(value)}>{value}</button>)}</div>
    <p>{visiblePages.length} of {pages.length} pages shown</p>
    {!visiblePages.length ? <div className="notice">No pages match this filter.</div> : (
      <div className="page-grid">{visiblePages.map(item => <button key={item.public_id} onClick={() => openPage(item.page_number)}><strong>Page {item.page_number}</strong>{isCriticalPage(item, tamilPageNumbers) && <span className="review-status-badge">critical</span>}<span>{item.extraction_method} · {item.extraction_status}</span><small>{item.text_length} characters · {item.warnings?.length || 0} warnings</small></button>)}</div>
    )}
    <h4>Job history</h4>{!jobs.length ? <div className="notice">No processing jobs.</div> : <ol>{jobs.map(job => <li key={job.public_id}>{job.job_type} · {job.status} · {Math.round(job.progress * 100)}%</li>)}</ol>}
    <h4>Latest events</h4>{!events.length ? <div className="notice">No events for the latest job.</div> : <ol>{events.map((item,index) => <li key={`${item.created_at}-${index}`}>{item.event_type}{item.page_number ? ` · page ${item.page_number}` : ''}</li>)}</ol>}
  </section>
}

function PageReview({
  page, pages, busy, openPage, imageUrl, revisions, reviewEvents, suggestions, loadSuggestions, applySuggestions,
  save, reprocess, approve, reject, exclude, reopen, requestCorrection, requestOcrRerun, requestExtractionRerun,
  restoreRevision,
}) {
  const [text, setText] = useState(page?.cleaned_text || '')
  const [changeSummary, setChangeSummary] = useState('')
  const [subTab, setSubTab] = useState('Corrected')
  const [fitWidth, setFitWidth] = useState(true)
  const [rotated, setRotated] = useState(false)
  useEffect(() => { setText(page?.cleaned_text || ''); setSubTab('Corrected'); setChangeSummary('') }, [page])
  if (!page) return <div className="notice">Select a page from Processing.</div>
  const index = pages.findIndex(item => item.page_number === page.page_number)

  return <section className="page-review">
    <header>
      <div>
        <h3>Page {page.page_number} <span className="review-status-badge">{page.review_status || 'pending'}</span></h3>
        <p>{page.extraction_method} · {page.extraction_status} · {page.text_length} characters {page.confidence_score != null ? `· ${Math.round(page.confidence_score * 100)}% confidence` : '· confidence unavailable'}</p>
      </div>
      <div><button disabled={index <= 0} onClick={() => openPage(pages[index - 1].page_number)}>Previous</button><button disabled={index >= pages.length - 1} onClick={() => openPage(pages[index + 1].page_number)}>Next</button></div>
    </header>
    {page.warnings?.map(item => <p className="row-warning" key={item.code}>{item.code}: {item.message}</p>)}

    <div className="page-review-split">
      <div className="page-image-pane">
        <div className="panel-controls">
          <button type="button" onClick={() => setFitWidth(!fitWidth)}>{fitWidth ? 'Fit page' : 'Fit width'}</button>
          <button type="button" onClick={() => setRotated(!rotated)}>Rotate</button>
        </div>
        {imageUrl
          ? <img src={imageUrl} alt={`Original page ${page.page_number}`} className={fitWidth ? 'fit-width' : 'fit-page'} style={rotated ? { transform: 'rotate(90deg)' } : undefined} />
          : <div className="notice">Original page image is unavailable.</div>}
      </div>
      <div className="page-text-pane">
        <div className="dataset-tabs">{['Raw', 'Corrected', 'Compare', 'Metadata'].map(value => <button key={value} className={subTab === value ? 'active' : ''} onClick={() => { setSubTab(value); if (value === 'Metadata') loadSuggestions() }}>{value}</button>)}</div>
        {subTab === 'Raw' && <pre>{page.raw_text || 'No raw text extracted.'}</pre>}
        {subTab === 'Corrected' && (
          <>
            <label>Corrected text<textarea value={text} onChange={event => setText(event.target.value)} rows="14" /></label>
            <label>Change summary<input value={changeSummary} onChange={event => setChangeSummary(event.target.value)} /></label>
            <div className="review-actions">
              <button disabled={Boolean(busy) || text === page.cleaned_text} onClick={() => save(text, changeSummary)}>Save Draft</button>
              <button disabled={Boolean(busy)} onClick={requestOcrRerun}>Request OCR Rerun</button>
              <button disabled={Boolean(busy)} onClick={requestExtractionRerun}>Request Extraction Rerun</button>
              <button disabled={Boolean(busy)} onClick={reprocess}>Reprocess page</button>
            </div>
            {text !== page.cleaned_text && <p className="unsaved-note">Unsaved page edits</p>}
          </>
        )}
        {subTab === 'Compare' && (
          <div className="history-panel">
            <h4>Raw vs corrected</h4>
            <div className="compare-columns"><pre>{page.raw_text || '(no raw text)'}</pre><pre>{page.cleaned_text || '(no corrected text)'}</pre></div>
            <h4>Revision history</h4>
            {!revisions.length ? <div className="notice">No revisions yet.</div> : (
              <ol>{revisions.map(revision => <li key={revision.revision_number}>#{revision.revision_number} by {revision.edited_by_admin_public_id} at {revision.created_at} <button type="button" onClick={() => restoreRevision(revision.revision_number)}>Restore</button><pre>{revision.cleaned_text}</pre></li>)}</ol>
            )}
          </div>
        )}
        {subTab === 'Metadata' && (
          <div className="history-panel">
            <h4>Cleanup suggestions</h4>
            {!suggestions.length ? <div className="notice">No cleanup suggestions for this page.</div> : (
              <>
                <ul>{suggestions.map((item, index) => <li key={index}>{item.suggestion_type}: {item.reason} (confidence {item.confidence})</li>)}</ul>
                <button type="button" onClick={() => applySuggestions(suggestions)}>Accept all suggestions</button>
              </>
            )}
            <h4>Review history</h4>
            {!reviewEvents.length ? <div className="notice">No review events yet.</div> : (
              <ol>{reviewEvents.map(item => <li key={item.public_id}>{item.action} → {item.review_status_after} by {item.performed_by_admin_public_id} at {item.created_at}</li>)}</ol>
            )}
          </div>
        )}
      </div>
    </div>

    <div className="review-actions">
      <h3>Review decision</h3>
      <button disabled={Boolean(busy)} onClick={approve}>Approve Page</button>
      <button disabled={Boolean(busy)} onClick={reject}>Reject Page</button>
      <button disabled={Boolean(busy)} onClick={exclude}>Exclude Page</button>
      <button disabled={Boolean(busy)} onClick={reopen}>Reopen</button>
      <button disabled={Boolean(busy)} onClick={requestCorrection}>Request Correction</button>
    </div>
  </section>
}

function RepeatedElementsReview({ document, repeated, busy, loadRepeated, detect, review }) {
  useEffect(() => { loadRepeated() }, [document.public_id])
  return <section className="candidate-review">
    <header className="section-heading">
      <div><h3>Repeated headers, footers &amp; page numbers</h3><p>Deterministic cross-page detection -- nothing is removed until explicitly confirmed.</p></div>
      <button disabled={Boolean(busy)} onClick={detect}>Detect repeated elements</button>
    </header>
    {!repeated.length ? <div className="notice">No repeated-element suggestions yet.</div> : (
      <div className="candidate-list">
        {repeated.map(item => (
          <article key={item.public_id}>
            <header><strong>{item.element_type}</strong><span>{item.status} · confidence {item.confidence} · pages {item.page_occurrences?.join(', ')}</span></header>
            <p>{item.normalized_text}</p>
            <div className="review-actions">
              <button disabled={Boolean(busy) || item.status !== 'suggested'} onClick={() => review(item.public_id, 'accept', {})}>Accept removal</button>
              <button disabled={Boolean(busy) || item.status !== 'suggested'} onClick={() => review(item.public_id, 'reject', {})}>Reject suggestion</button>
              <button disabled={Boolean(busy) || item.status === 'applied'} onClick={() => review(item.public_id, 'apply_all', { confirm: true })}>Apply to all matching pages</button>
            </div>
          </article>
        ))}
      </div>
    )}
  </section>
}

function CandidateReview({ document, candidates, busy, confirmed, setConfirmed, segment, edit, choose, importCandidates }) {
  const selected = candidates.filter(item => item.status === 'selected').length
  return <section className="candidate-review"><header className="section-heading"><div><h3>Candidate records</h3><p>Deterministic pretrain segments preserve page provenance and import as drafts only.</p></div><button disabled={Boolean(busy)} onClick={segment}>Generate candidates</button></header>{!candidates.length ? <div className="notice">No candidates yet. Review pages, then generate candidates.</div> : <div className="candidate-list">{candidates.map(item => <CandidateCard key={item.public_id} item={item} edit={edit} choose={choose} busy={busy} />)}</div>}<div className="confirmation-box"><strong>Draft import confirmation</strong><p>{selected} selected · {candidates.filter(item => item.status === 'duplicate').length} duplicates · document {document.original_filename}</p><label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /> I reviewed the candidates and confirm draft-only dataset import.</label><button disabled={!confirmed || !selected || Boolean(busy)} onClick={importCandidates}>Import selected candidates</button></div></section>
}

function CandidateCard({ item, edit, choose, busy }) {
  const [text, setText] = useState(item.output_text || item.candidate_text || '')
  return <article><header><strong>Candidate {item.sequence_number} · pages {item.source_page_start}–{item.source_page_end}</strong><span>{item.status} · {item.language}</span></header><textarea aria-label={`Candidate ${item.sequence_number} text`} value={text} onChange={event => setText(event.target.value)} rows="5" /><div><button disabled={Boolean(busy) || text === (item.output_text || item.candidate_text || '')} onClick={() => edit(item.public_id, { output_text: text, candidate_text: text })}>Save edit</button><button disabled={Boolean(busy) || !['valid','warning','draft'].includes(item.status)} onClick={() => choose(item.public_id, 'select')}>Select</button><button disabled={Boolean(busy) || item.status === 'imported'} onClick={() => choose(item.public_id, 'reject')}>Reject</button></div>{item.duplicate_record_public_id && <p className="row-warning">Duplicate of record {item.duplicate_record_public_id}</p>}</article>
}

function TamilQualityReview({ document, issues, summary, busy, loadTamilQuality, detect, review }) {
  useEffect(() => { loadTamilQuality() }, [document.public_id])
  return <section className="candidate-review">
    <header className="section-heading">
      <div><h3>Tamil Unicode &amp; OCR quality</h3><p>Mechanical fixes are low-risk; spelling and ambiguous corrections always require a preview or a manual edit.</p></div>
      <button disabled={Boolean(busy)} onClick={detect}>Detect Tamil quality issues</button>
    </header>
    {summary && <section className="metric-grid">
      <article className="status-card"><span>Total issues</span><strong>{summary.total_issues}</strong></article>
      <article className="status-card"><span>Pending review</span><strong>{summary.pending_count}</strong></article>
      {Object.entries(summary.by_correction_risk || {}).map(([key, value]) => <article className="status-card" key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{value}</strong></article>)}
    </section>}
    {!issues.length ? <div className="notice">No Tamil quality issues detected yet.</div> : (
      <div className="candidate-list">
        {issues.map(item => (
          <article key={item.public_id}>
            <header><strong>Page {item.page_number} · {item.issue_type.replaceAll('_', ' ')}</strong><span>{item.review_status} · {item.correction_risk} · confidence {item.confidence_band}</span></header>
            <p>{item.context}</p>
            {item.suggested_text && <p><em>Suggested:</em> {item.suggested_text.slice(0, 200)}</p>}
            {item.review_status === 'pending' && (
              <div className="review-actions">
                <button disabled={Boolean(busy) || item.correction_risk === 'mandatory_review'} onClick={() => review(item.public_id, 'accept', {})}>Accept</button>
                <button disabled={Boolean(busy)} onClick={() => review(item.public_id, 'reject', {})}>Reject</button>
                <button disabled={Boolean(busy)} onClick={() => review(item.public_id, 'ignore', {})}>Ignore</button>
              </div>
            )}
          </article>
        ))}
      </div>
    )}
  </section>
}

function SftCandidateReview({ document, items, summary, busy, loadSftCandidates, generate, review, bulkApprove }) {
  const [selected, setSelected] = useState([])
  useEffect(() => { loadSftCandidates() }, [document.public_id])
  const lowRiskPending = items.filter(item => item.quality_status === 'pending_review' && item.rights_status === 'verified' && item.generation_method === 'template_heuristic_v1')
  function toggle(id) { setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]) }
  return <section className="candidate-review">
    <header className="section-heading">
      <div><h3>SFT candidates</h3><p>Generated only from approved chunks with verified rights -- never every type from every paragraph.</p></div>
      <button disabled={Boolean(busy)} onClick={generate}>Generate SFT candidates</button>
    </header>
    {summary && <section className="metric-grid">
      <article className="status-card"><span>Total candidates</span><strong>{summary.total_candidates}</strong></article>
      <article className="status-card"><span>Approved</span><strong>{summary.approved_count}</strong></article>
      {Object.entries(summary.by_task || {}).map(([key, value]) => <article className="status-card" key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{value}</strong></article>)}
    </section>}
    {lowRiskPending.length > 0 && (
      <div className="panel-controls">
        <button disabled={Boolean(busy) || !selected.length} onClick={() => { bulkApprove(selected); setSelected([]) }}>Bulk approve {selected.length} selected (low-risk only)</button>
      </div>
    )}
    {!items.length ? <div className="notice">No SFT candidates yet. Approve chunks, then generate candidates.</div> : (
      <div className="candidate-list">
        {items.map(item => (
          <article key={item.public_id}>
            <header>
              {item.quality_status === 'pending_review' && item.rights_status === 'verified' && item.generation_method === 'template_heuristic_v1' && (
                <input type="checkbox" aria-label={`Select candidate ${item.public_id}`} checked={selected.includes(item.public_id)} onChange={() => toggle(item.public_id)} />
              )}
              <strong>{item.task.replaceAll('_', ' ')} · pages {item.source_page_start}–{item.source_page_end}</strong>
              <span>{item.quality_status} · rights {item.rights_status}</span>
            </header>
            <p><strong>Instruction:</strong> {item.instruction}</p>
            <p><strong>Response:</strong> {item.response}</p>
            {item.rights_status !== 'verified' && <p className="row-warning">Rights not verified -- cannot approve until the linked source's rights are confirmed.</p>}
            <div className="review-actions">
              <button disabled={Boolean(busy) || item.quality_status === 'approved' || item.rights_status !== 'verified'} onClick={() => review(item.public_id, 'approve', {})}>Approve</button>
              <button disabled={Boolean(busy) || item.quality_status === 'rejected'} onClick={() => review(item.public_id, 'reject', {})}>Reject</button>
              <button disabled={Boolean(busy)} onClick={() => review(item.public_id, 'needs_correction', {})}>Needs correction</button>
            </div>
          </article>
        ))}
      </div>
    )}
  </section>
}

function SftExportPanel({ document, summary, exportResult, busy, loadSftCandidates, runExport }) {
  useEffect(() => { loadSftCandidates() }, [document.public_id])
  const approved = summary?.approved_count || 0
  return <section className="candidate-review">
    <header className="section-heading">
      <div><h3>Export approved SFT candidates</h3><p>Only approved candidates are exported to JSONL, with a manifest and checksum.</p></div>
      <button disabled={Boolean(busy) || !approved} onClick={runExport}>Export {approved} approved candidate(s)</button>
    </header>
    {!exportResult ? <div className="notice">No export created yet for this session.</div> : (
      <div className="history-panel">
        <p>Export {exportResult.public_id}</p>
        <section className="metric-grid">
          <article className="status-card"><span>Records</span><strong>{exportResult.record_count}</strong></article>
          <article className="status-card"><span>Excluded</span><strong>{exportResult.excluded_count}</strong></article>
        </section>
        <p>Task distribution: {Object.entries(exportResult.task_distribution || {}).map(([key, value]) => `${key} (${value})`).join(', ') || 'none'}</p>
        <p>Checksum: <code>{exportResult.checksum_sha256}</code></p>
        <p>File: <code>{exportResult.export_path}</code></p>
      </div>
    )}
  </section>
}

const SECURITY_REVIEW_ACTIONS = ['reviewed', 'dismissed']

function SecurityReviewPanel({ document, findings, piiFindings, busy, load, scan, review }) {
  useEffect(() => { load() }, [document.public_id])
  const blocking = findings.filter(item => item.action === 'block_export')
  return <section className="candidate-review">
    <header className="section-heading">
      <div><h3>Security &amp; PII review</h3><p>Prompt-injection, secrets, and PII are detected in extracted document text -- detected content never alters Admin Assistant or system behavior. Secrets and absolute paths always block export until resolved.</p></div>
      <button disabled={Boolean(busy)} onClick={scan}>Scan for security &amp; PII findings</button>
    </header>
    {blocking.length > 0 && <div className="row-warning">Export blocked: {blocking.length} unresolved secret/path finding(s).</div>}
    <section className="metric-grid">
      <article className="status-card"><span>Total findings</span><strong>{findings.length}</strong></article>
      <article className="status-card"><span>PII findings</span><strong>{piiFindings.length}</strong></article>
      <article className="status-card"><span>Export-blocking</span><strong>{blocking.length}</strong></article>
    </section>
    {!findings.length ? <div className="notice">No security findings yet. Run a scan.</div> : (
      <div className="candidate-list">
        {findings.map(item => (
          <article key={item.public_id}>
            <header><strong>{item.finding_type.replaceAll('_', ' ')}</strong><span>page {item.page_number} · {item.action.replaceAll('_', ' ')} · confidence {item.confidence_band} · {item.review_status}</span></header>
            <p><code>{item.matched_text.length > 40 ? `${item.matched_text.slice(0, 40)}…` : item.matched_text}</code></p>
            <p>{item.reason_code.replaceAll('_', ' ')}</p>
            {item.review_status === 'pending' && (
              <div className="review-actions">
                {SECURITY_REVIEW_ACTIONS.map(actionName => (
                  <button key={actionName} disabled={Boolean(busy)} onClick={() => review(item.public_id, actionName)}>{actionName === 'reviewed' ? 'Mark reviewed' : 'Mark false positive'}</button>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    )}
  </section>
}

function MediaClassificationPanel({ document, classifications, busy, load, scan }) {
  useEffect(() => { load() }, [document.public_id])
  const visionRequired = classifications.filter(item => item.vision_required)
  return <section className="candidate-review">
    <header className="section-heading">
      <div><h3>Media &amp; table classification</h3><p>Text-only classification derived from extraction metadata -- no Vision model is used. Pages marked vision_required are automatically excluded from text-only SFT generation.</p></div>
      <button disabled={Boolean(busy)} onClick={scan}>Classify pages</button>
    </header>
    {visionRequired.length > 0 && <div className="row-warning">{visionRequired.length} page(s) require a Vision model and are blocked from text-only SFT generation.</div>}
    {!classifications.length ? <div className="notice">No classifications yet. Run a scan.</div> : (
      <div className="candidate-list">
        {classifications.map(item => (
          <article key={item.public_id}>
            <header><strong>Page {item.page_number} · {item.content_type.replaceAll('_', ' ')}</strong>{item.vision_required && <span className="review-status-badge">vision_required</span>}</header>
            {item.caption_text && <p><em>Caption/nearby text:</em> {item.caption_text.slice(0, 200)}</p>}
            <p>Review status: {item.review_status} · Training eligibility: {item.vision_required ? 'blocked (text-only SFT)' : 'eligible'}</p>
          </article>
        ))}
      </div>
    )}
  </section>
}

const TAMIL_RULE_ISSUE_CATEGORIES = [
  'known_ocr_substitution', 'pulli_error', 'vowel_sign_error', 'grapheme_integrity',
  'zero_width_contamination', 'unicode_normalization_mismatch', 'spelling_variant',
  'word_boundary_anomaly', 'punctuation_spacing', 'mixed_script_contamination',
]
const TAMIL_RULE_RISKS = ['mechanical', 'spelling', 'grammatical', 'meaning_sensitive', 'ambiguous']
const TAMIL_RULE_NEXT_ACTION = { draft: 'submit_review', needs_review: 'approve', approved: 'activate' }

function TamilCorrectionRulesPanel({ rules, busy, load, create, review }) {
  useEffect(() => { load() }, [])
  const [form, setForm] = useState({
    incorrect_form: '', approved_correction: '', issue_category: TAMIL_RULE_ISSUE_CATEGORIES[0],
    evidence: '', confidence_band: 'medium', meaning_change_risk: TAMIL_RULE_RISKS[0],
  })
  return <section className="candidate-review">
    <header className="section-heading">
      <div><h3>Tamil correction-rule registry</h3><p>A governed, versioned registry (draft → needs_review → approved → active). The Admin Assistant may propose draft/needs_review rules only -- only a human Admin can approve or activate a rule. Meaning-sensitive and ambiguous rules never support automatic application.</p></div>
    </header>
    <form className="document-upload" onSubmit={event => { event.preventDefault(); create(form) }}>
      <h4>Create draft rule</h4>
      <label>Incorrect form<input value={form.incorrect_form} onChange={event => setForm({ ...form, incorrect_form: event.target.value })} required /></label>
      <label>Approved correction<input value={form.approved_correction} onChange={event => setForm({ ...form, approved_correction: event.target.value })} required /></label>
      <label>Issue category<select value={form.issue_category} onChange={event => setForm({ ...form, issue_category: event.target.value })}>{TAMIL_RULE_ISSUE_CATEGORIES.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Meaning-change risk<select value={form.meaning_change_risk} onChange={event => setForm({ ...form, meaning_change_risk: event.target.value })}>{TAMIL_RULE_RISKS.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Evidence<input value={form.evidence} onChange={event => setForm({ ...form, evidence: event.target.value })} /></label>
      <button disabled={Boolean(busy)}>Create draft rule</button>
    </form>
    {!rules.length ? <div className="notice">No Tamil correction rules yet.</div> : (
      <div className="candidate-list">
        {rules.map(item => (
          <article key={item.public_id}>
            <header><strong>{item.incorrect_form} → {item.approved_correction}</strong><span>{item.status} · v{item.rule_version} · {item.meaning_change_risk}</span></header>
            <p>{item.issue_category.replaceAll('_', ' ')} · confidence {item.confidence_band}</p>
            <p>{item.automatic_proposal_allowed ? 'Automatic proposal allowed (mechanical only)' : 'Human review required'}</p>
            <div className="review-actions">
              {TAMIL_RULE_NEXT_ACTION[item.status] && (
                <button disabled={Boolean(busy)} onClick={() => review(item.public_id, TAMIL_RULE_NEXT_ACTION[item.status])}>{TAMIL_RULE_NEXT_ACTION[item.status].replaceAll('_', ' ')}</button>
              )}
              {item.status !== 'rejected' && <button disabled={Boolean(busy)} onClick={() => review(item.public_id, 'reject')}>Reject</button>}
            </div>
          </article>
        ))}
      </div>
    )}
  </section>
}
