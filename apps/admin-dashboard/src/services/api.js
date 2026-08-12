const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
let csrfToken = null
let csrfHeaderName = 'X-CSRF-Token'

async function request(path, options = {}) {
  const { timeoutMs, ...fetchOptions } = options
  const headers = { ...(fetchOptions.headers ?? {}) }
  if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  if (fetchOptions.method && fetchOptions.method !== 'GET') {
    if (!csrfToken) await getCsrf()
    headers[csrfHeaderName] = csrfToken
  }
  // MB-48: opt-in only -- most admin CRUD calls are fast and must never
  // be newly bounded by a timeout that could change their behavior;
  // only the specific real-model-generation call sites below pass
  // timeoutMs, matched to the backend's own configured timeout plus
  // headroom for network/queueing, never shorter than it.
  let controller
  let timer
  if (timeoutMs) {
    controller = new AbortController()
    timer = setTimeout(() => controller.abort(), timeoutMs)
  }
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      // MB-48: this is a live admin control plane -- every GET reads
      // state that can change from another tab/page/action moments
      // earlier (e.g. the grounded-chat default retrieval profile);
      // never let the browser's implicit HTTP cache serve a stale
      // response for it.
      credentials: 'include', cache: 'no-store', ...fetchOptions, headers,
      ...(controller ? { signal: controller.signal } : {}),
    })
  } catch (reason) {
    if (reason.name === 'AbortError') {
      throw new Error('The request took too long and was cancelled. The local model may still be generating -- try again in a moment.')
    }
    throw new Error('Network error -- could not reach the backend. Check that it is running and try again.')
  } finally {
    if (timer) clearTimeout(timer)
  }
  if (!response.ok) {
    let message = response.status === 401 ? 'Your admin session has expired.' : 'Request failed.'
    try { const data = await response.json(); message = data.error?.message ?? data.detail ?? message } catch { /* safe generic message */ }
    const error = new Error(typeof message === 'string' ? message : 'Validation failed.')
    error.status = response.status
    throw error
  }
  return response.json()
}

export async function login(username, password) {
  const data = await fetch(`${API_BASE}/api/admin/auth/login`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!data.ok) throw new Error('Invalid username or password.')
  csrfToken = null
  await getCsrf()
  return data.json()
}

export const getMe = () => request('/api/admin/auth/me')
export async function getCsrf() {
  const data = await fetch(`${API_BASE}/api/admin/auth/csrf`, { credentials: 'include' })
  if (!data.ok) throw new Error('Authentication required.')
  const payload = await data.json()
  csrfToken = payload.csrf_token
  csrfHeaderName = payload.header_name
  return csrfToken
}
export async function logout() { const result = await request('/api/admin/auth/logout', { method: 'POST' }); csrfToken = null; return result }
export const getOverview = () => request('/api/admin/overview')
export async function getSystemStatus() {
  const [database, configuration, schema, audit] = await Promise.all([
    request('/api/admin/system/database'), request('/api/admin/system/configuration'),
    request('/api/admin/system/schema'), request('/api/admin/audit/recent?limit=8'),
  ])
  return { database, configuration, schema, audit }
}
export const systemRecentAudit = (limit = 20, offset = 0) => request(`/api/admin/audit/recent?limit=${limit}&offset=${offset}`)
export const systemPilotMetrics = () => request('/api/admin/system/pilot-metrics')
export const datasetStatistics = () => request('/api/admin/datasets/statistics')
export const datasetSources = (query = '') => request(`/api/admin/datasets/sources${query}`)
export const createDatasetSource = (body) => request('/api/admin/datasets/sources', { method: 'POST', body: JSON.stringify(body) })
export const updateDatasetSource = (id, body) => request(`/api/admin/datasets/sources/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const datasetRecords = (query = '') => request(`/api/admin/datasets/records${query}`)
export const createDatasetRecord = (body) => request('/api/admin/datasets/records', { method: 'POST', body: JSON.stringify(body) })
export const updateDatasetRecord = (id, body) => request(`/api/admin/datasets/records/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const datasetDuplicates = () => request('/api/admin/datasets/duplicates')
export const recordAction = (id, action, body) => request(`/api/admin/datasets/records/${id}/${action}`, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
export const recordReviews = (id) => request(`/api/admin/datasets/records/${id}/reviews`)
export const importJobs = (query = '') => request(`/api/admin/datasets/imports${query}`)
export const importRows = (id, query = '') => request(`/api/admin/datasets/imports/${id}/rows${query}`)
export const importEvents = (id) => request(`/api/admin/datasets/imports/${id}/events`)
export const uploadImport = (form) => request('/api/admin/datasets/imports', { method: 'POST', body: form })
export const parseImport = (id) => request(`/api/admin/datasets/imports/${id}/parse`, { method: 'POST' })
export const updateImportMapping = (id, body) => request(`/api/admin/datasets/imports/${id}/mapping`, { method: 'PATCH', body: JSON.stringify(body) })
export const confirmImport = (id, body) => request(`/api/admin/datasets/imports/${id}/confirm`, { method: 'POST', body: JSON.stringify(body) })
export const cancelImport = (id) => request(`/api/admin/datasets/imports/${id}/cancel`, { method: 'POST' })
export async function downloadImportReport(id) {
  if (!csrfToken) await getCsrf()
  const response = await fetch(`${API_BASE}/api/admin/datasets/imports/${id}/report`, { credentials: 'include', headers: { [csrfHeaderName]: csrfToken } })
  if (!response.ok) throw new Error('Could not create the import report.')
  return response.blob()
}
export const documentCapabilities = () => request('/api/admin/documents/capabilities')
export const documents = (query = '') => request(`/api/admin/documents${query}`)
export const documentDetail = (id) => request(`/api/admin/documents/${id}`)
export const uploadDocument = (form) => request('/api/admin/documents', { method: 'POST', body: form })
export const analyzeDocument = (id) => request(`/api/admin/documents/${id}/analyze`, { method: 'POST' })
export const processDocument = (id, body) => request(`/api/admin/documents/${id}/process`, { method: 'POST', body: JSON.stringify(body) })
export const documentPages = (id, query = '') => request(`/api/admin/documents/${id}/pages${query}`)
export const documentPage = (id, number) => request(`/api/admin/documents/${id}/pages/${number}`)
export const editDocumentPage = (id, number, body) => request(`/api/admin/documents/${id}/pages/${number}`, { method: 'PATCH', body: JSON.stringify(body) })
export const reprocessDocumentPage = (id, number, body) => request(`/api/admin/documents/${id}/pages/${number}/reprocess`, { method: 'POST', body: JSON.stringify(body) })
export const segmentDocument = (id, body) => request(`/api/admin/documents/${id}/segment`, { method: 'POST', body: JSON.stringify(body) })
export const documentCandidates = (id, query = '') => request(`/api/admin/documents/${id}/candidates${query}`)
export const editDocumentCandidate = (id, candidate, body) => request(`/api/admin/documents/${id}/candidates/${candidate}`, { method: 'PATCH', body: JSON.stringify(body) })
export const documentCandidateAction = (id, candidate, action) => request(`/api/admin/documents/${id}/candidates/${candidate}/${action}`, { method: 'POST' })
export const importDocumentCandidates = (id) => request(`/api/admin/documents/${id}/candidates/import`, { method: 'POST', body: JSON.stringify({ confirm: true }) })
export const documentJobs = (id) => request(`/api/admin/documents/${id}/jobs`)
export const documentJobEvents = (id) => request(`/api/admin/documents/jobs/${id}/events`)
export async function downloadDocumentReport(id) {
  const response = await fetch(`${API_BASE}/api/admin/documents/${id}/report`, { credentials: 'include' })
  if (!response.ok) throw new Error('Could not create the document report.')
  return response.blob()
}

// Phase 4: PDF Research Workspace (additive) -------------------------------
const DOC = (id) => `/api/admin/documents/${id}`
export const documentWorkspace = (id) => request(`${DOC(id)}/workspace`)
export const linkDocumentSource = (id, sourcePublicId) => request(`${DOC(id)}/source-link`, { method: 'POST', body: JSON.stringify({ source_public_id: sourcePublicId }) })
export async function documentPageImageUrl(id, pageNumber) {
  const response = await fetch(`${API_BASE}${DOC(id)}/pages/${pageNumber}/image`, { credentials: 'include' })
  if (!response.ok) throw new Error('Could not render the page image.')
  return URL.createObjectURL(await response.blob())
}
export const documentPageExtractions = (id, pageNumber) => request(`${DOC(id)}/pages/${pageNumber}/extractions`)
export const documentPageRevisions = (id, pageNumber) => request(`${DOC(id)}/pages/${pageNumber}/revisions`)
export const restoreDocumentPageRevision = (id, pageNumber, revisionNumber) => request(`${DOC(id)}/pages/${pageNumber}/revisions/${revisionNumber}/restore`, { method: 'POST' })
export const approveDocumentPage = (id, pageNumber, notes = '') => request(`${DOC(id)}/pages/${pageNumber}/approve`, { method: 'POST', body: JSON.stringify({ notes }) })
export const rejectDocumentPage = (id, pageNumber, notes = '') => request(`${DOC(id)}/pages/${pageNumber}/reject`, { method: 'POST', body: JSON.stringify({ notes }) })
export const excludeDocumentPage = (id, pageNumber, notes = '') => request(`${DOC(id)}/pages/${pageNumber}/exclude`, { method: 'POST', body: JSON.stringify({ notes }) })
export const reopenDocumentPage = (id, pageNumber, notes = '') => request(`${DOC(id)}/pages/${pageNumber}/reopen`, { method: 'POST', body: JSON.stringify({ notes }) })
export const requestDocumentPageCorrection = (id, pageNumber, notes = '') => request(`${DOC(id)}/pages/${pageNumber}/request-correction`, { method: 'POST', body: JSON.stringify({ notes }) })
export const requestDocumentPageOcrRerun = (id, pageNumber, ocrLanguage = null) => request(`${DOC(id)}/pages/${pageNumber}/request-ocr-rerun`, { method: 'POST', body: JSON.stringify({ ocr_language: ocrLanguage }) })
export const requestDocumentPageExtractionRerun = (id, pageNumber, strategy = 'auto') => request(`${DOC(id)}/pages/${pageNumber}/request-extraction-rerun`, { method: 'POST', body: JSON.stringify({ strategy }) })
export const documentPageReviewEvents = (id, pageNumber) => request(`${DOC(id)}/pages/${pageNumber}/review-events`)
export const documentReviewSummary = (id) => request(`${DOC(id)}/review-summary`)
export const documentPageCleanupSuggestions = (id, pageNumber) => request(`${DOC(id)}/pages/${pageNumber}/cleanup-suggestions`)
export const applyDocumentPageCleanup = (id, pageNumber, suggestions) => request(`${DOC(id)}/pages/${pageNumber}/apply-cleanup`, { method: 'POST', body: JSON.stringify({ suggestions }) })
export const detectDocumentRepeatedElements = (id) => request(`${DOC(id)}/repeated-elements/detect`, { method: 'POST' })
export const documentRepeatedElements = (id, status) => request(`${DOC(id)}/repeated-elements${status ? `?status=${status}` : ''}`)
export const reviewDocumentRepeatedElement = (id, elementId, action, options = {}) => request(`${DOC(id)}/repeated-elements/${elementId}/review`, { method: 'POST', body: JSON.stringify({ action, confirm: false, target_pages: null, ...options }) })
export const sendDocumentToSegmentation = (id, body) => request(`${DOC(id)}/send-to-segmentation`, { method: 'POST', body: JSON.stringify(body) })

// Document SFT workflow (migration 043, additive) --------------------------
export const detectDocumentTamilQuality = (id) => request(`${DOC(id)}/tamil-quality/detect`, { method: 'POST' })
export const documentTamilQualityIssues = (id, query = '') => request(`${DOC(id)}/tamil-quality${query}`)
export const documentTamilQualitySummary = (id) => request(`${DOC(id)}/tamil-quality/summary`)
export const reviewDocumentTamilQualityIssue = (id, issueId, body) => request(`${DOC(id)}/tamil-quality/${issueId}/review`, { method: 'POST', body: JSON.stringify(body) })
export const generateDocumentSftCandidates = (id, body = {}) => request(`${DOC(id)}/sft-candidates/generate`, { method: 'POST', body: JSON.stringify(body) })
export const documentSftCandidates = (id, query = '') => request(`${DOC(id)}/sft-candidates${query}`)
export const documentSftCandidateSummary = (id) => request(`${DOC(id)}/sft-candidates/summary`)
export const reviewDocumentSftCandidate = (id, candidateId, body) => request(`${DOC(id)}/sft-candidates/${candidateId}/review`, { method: 'POST', body: JSON.stringify(body) })
export const bulkApproveDocumentSftCandidates = (id, candidatePublicIds) => request(`${DOC(id)}/sft-candidates/bulk-approve`, { method: 'POST', body: JSON.stringify({ candidate_public_ids: candidatePublicIds, confirm: true }) })
export const exportDocumentSftCandidates = (id) => request(`${DOC(id)}/sft-export`, { method: 'POST', body: JSON.stringify({ confirm: true }) })
export const documentSftExports = (id) => request(`${DOC(id)}/sft-exports`)

// --- Production integration: overview / generator eligibility -------------------------------
export const documentOverview = (id) => request(`${DOC(id)}/overview`)
export const documentGeneratorEligibility = (id) => request(`${DOC(id)}/generator-eligibility`)

// --- Production integration: dataset handoff -------------------------------------------------
export const validateDocumentSftExport = (id, exportId) => request(`${DOC(id)}/sft-export/${exportId}/validate`, { method: 'POST' })
export const previewDocumentSftHandoff = (id, exportId) => request(`${DOC(id)}/sft-export/${exportId}/handoff-preview`, { method: 'POST' })
export const ingestDocumentSftHandoff = (id, exportId) => request(`${DOC(id)}/sft-export/${exportId}/handoff-ingest`, { method: 'POST', body: JSON.stringify({ confirm: true }) })
export const documentHandoffs = (id) => request(`${DOC(id)}/handoffs`)
export const documentHandoff = (id, handoffId) => request(`${DOC(id)}/handoffs/${handoffId}`)
export const proposeDatasetVersion = (id, handoffId, datasetName, datasetVersion) => request(`${DOC(id)}/handoffs/${handoffId}/dataset-version-proposal`, { method: 'POST', body: JSON.stringify({ dataset_name: datasetName, dataset_version: datasetVersion }) })
export const documentHandoffSplitPreview = (id, handoffId) => request(`${DOC(id)}/handoffs/${handoffId}/split-preview`)
export const confirmDatasetVersionBuild = (id, handoffId) => request(`${DOC(id)}/handoffs/${handoffId}/confirm-build`, { method: 'POST', body: JSON.stringify({ confirm: true }) })
export const documentDatasetVersionStatus = (id) => request(`${DOC(id)}/dataset-version-status`)

// --- Production integration: content classification (media & tables) -------------------------
export const scanDocumentContentClassifications = (id) => request(`${DOC(id)}/content-classifications/scan`, { method: 'POST' })
export const documentContentClassifications = (id, query = '') => request(`${DOC(id)}/content-classifications${query}`)

// --- Production integration: security / PII review ---------------------------------------------
export const scanDocumentSecurityFindings = (id) => request(`${DOC(id)}/security/scan`, { method: 'POST' })
export const documentSecurityFindings = (id, query = '') => request(`${DOC(id)}/security-findings${query}`)
export const documentPiiFindings = (id, query = '') => request(`${DOC(id)}/pii-findings${query}`)
export const reviewDocumentSecurityFinding = (id, findingId, action) => request(`${DOC(id)}/security/${findingId}/review`, { method: 'POST', body: JSON.stringify({ action }) })

// --- Production integration: Tamil correction rules (global registry) --------------------------
const TCR = '/api/admin/document-tamil-correction-rules'
export const tamilCorrectionRules = (query = '') => request(`${TCR}${query}`)
export const tamilCorrectionRule = (ruleId) => request(`${TCR}/${ruleId}`)
export const createTamilCorrectionRule = (body) => request(TCR, { method: 'POST', body: JSON.stringify(body) })
export const reviewTamilCorrectionRule = (ruleId, action, notes = '') => request(`${TCR}/${ruleId}/review`, { method: 'POST', body: JSON.stringify({ action, notes }) })
export const tamilCorrectionRuleHistory = (ruleId) => request(`${TCR}/${ruleId}/history`)

export const qualitySummary = () => request('/api/admin/datasets/quality/summary')
export const qualityIssues = (query = '') => request(`/api/admin/datasets/quality/issues${query}`)
export const assessQuality = (body = {}) => request('/api/admin/datasets/quality/assess', { method: 'POST', body: JSON.stringify(body) })
export const assessRecordQuality = (id) => request(`/api/admin/datasets/records/${id}/quality/assess`, { method: 'POST', body: JSON.stringify({ force: true }) })
export const recordQuality = (id) => request(`/api/admin/datasets/records/${id}/quality`)
export const datasetVersions = (query = '') => request(`/api/admin/datasets/versions${query}`)
export const createDatasetVersion = (body) => request('/api/admin/datasets/versions', { method: 'POST', body: JSON.stringify(body) })
export const datasetVersion = (id) => request(`/api/admin/datasets/versions/${id}`)
export const datasetVersionItems = (id, query = '') => request(`/api/admin/datasets/versions/${id}/items${query}`)
export const datasetVersionManifest = (id) => request(`/api/admin/datasets/versions/${id}/manifest`)
export const verifyDatasetVersion = (id) => request(`/api/admin/datasets/versions/${id}/verify`, { method: 'POST' })
export const createDatasetBuild = (body) => request('/api/admin/datasets/builds', { method: 'POST', body: JSON.stringify(body) })
export const datasetBuilds = (query = '') => request(`/api/admin/datasets/builds${query}`)
export const validateDatasetBuild = (id) => request(`/api/admin/datasets/builds/${id}/validate`, { method: 'POST' })
export const runDatasetBuild = (id, body) => request(`/api/admin/datasets/builds/${id}/run`, { method: 'POST', body: JSON.stringify(body) })
export const datasetBuildEvents = (id) => request(`/api/admin/datasets/builds/${id}/events`)
export const createDatasetExport = (id, body = { export_format: 'jsonl' }) => request(`/api/admin/datasets/versions/${id}/exports`, { method: 'POST', body: JSON.stringify(body) })
export const datasetExports = (id) => request(`/api/admin/datasets/versions/${id}/exports`)
export const verifyDatasetExport = (id) => request(`/api/admin/datasets/exports/${id}/verify`, { method: 'POST' })
export const tokenizerCapabilities = () => request('/api/admin/tokenizers/capabilities')
export const tokenizerFamilies = (query = '') => request(`/api/admin/tokenizers/families${query}`)
export const createTokenizerFamily = (body) => request('/api/admin/tokenizers/families', { method: 'POST', body: JSON.stringify(body) })
export const tokenizerVersions = (query = '') => request(`/api/admin/tokenizers/versions${query}`)
export const createTokenizerVersion = (body) => request('/api/admin/tokenizers/versions', { method: 'POST', body: JSON.stringify(body) })
export const tokenizerJobs = (query = '') => request(`/api/admin/tokenizers/jobs${query}`)
export const createTokenizerJob = (body) => request('/api/admin/tokenizers/jobs', { method: 'POST', body: JSON.stringify(body) })
export const tokenizerJobAction = (id, action) => request(`/api/admin/tokenizers/jobs/${id}/${action}`, { method: 'POST' })
export const tokenizerJobEvents = (id) => request(`/api/admin/tokenizers/jobs/${id}/events`)
export const tokenizerEncode = (id, text) => request(`/api/admin/tokenizers/versions/${id}/encode`, { method: 'POST', body: JSON.stringify({ text }) })
export const tokenizerDecode = (id, ids) => request(`/api/admin/tokenizers/versions/${id}/decode`, { method: 'POST', body: JSON.stringify({ ids }) })
export const tokenizerCompare = (body) => request('/api/admin/tokenizers/compare', { method: 'POST', body: JSON.stringify(body) })
export const activateTokenizer = (id) => request(`/api/admin/tokenizers/versions/${id}/activate`, { method: 'POST' })
export const retireTokenizer = (id) => request(`/api/admin/tokenizers/versions/${id}/retire`, { method: 'POST' })
export const verifyTokenizer = (id) => request(`/api/admin/tokenizers/versions/${id}/verify`, { method: 'POST' })
export const tokenizerAssignments = () => request('/api/admin/tokenizers/assignments')
export const patchTokenizerAssignment = (key, body) => request(`/api/admin/tokenizers/assignments/${key}`, { method: 'PATCH', body: JSON.stringify(body) })
export const createTokenizerExport = (id, body = { export_format: 'sentencepiece_bundle' }) => request(`/api/admin/tokenizers/versions/${id}/exports`, { method: 'POST', body: JSON.stringify(body) })
export const tokenizerExports = (id) => request(`/api/admin/tokenizers/versions/${id}/exports`)
export const verifyTokenizerExport = (id) => request(`/api/admin/tokenizers/exports/${id}/verify`, { method: 'POST' })
export const coreModelCapabilities = () => request('/api/admin/core-models/capabilities')
export const coreModelFamilies = (query = '') => request(`/api/admin/core-models/families${query}`)
export const createCoreModelFamily = (body) => request('/api/admin/core-models/families', { method: 'POST', body: JSON.stringify(body) })
export const coreModelConfigs = (query = '') => request(`/api/admin/core-models/configs${query}`)
export const estimateCoreModelConfig = (body) => request('/api/admin/core-models/configs/estimate', { method: 'POST', body: JSON.stringify(body) })
export const createCoreModelConfig = (body) => request('/api/admin/core-models/configs', { method: 'POST', body: JSON.stringify(body) })
export const validateCoreModelConfig = (id) => request(`/api/admin/core-models/configs/${id}/validate`, { method: 'POST' })
export const coreModelVersions = (query = '') => request(`/api/admin/core-models/versions${query}`)
export const createCoreModelVersion = (body) => request('/api/admin/core-models/versions', { method: 'POST', body: JSON.stringify(body) })
export const coreModelVersionAction = (id, action, body) => request(`/api/admin/core-models/versions/${id}/${action}`, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
export const coreModelChecks = (id) => request(`/api/admin/core-models/versions/${id}/checks`)
export const coreModelCheckpoints = (id) => request(`/api/admin/core-models/versions/${id}/checkpoints`)
export const verifyCoreModelCheckpoint = (id) => request(`/api/admin/core-models/checkpoints/${id}/verify`, { method: 'POST' })
export const coreModelAssignments = () => request('/api/admin/core-models/assignments')
export const patchCoreModelAssignment = (key, body) => request(`/api/admin/core-models/assignments/${key}`, { method: 'PATCH', body: JSON.stringify(body) })
export const pretrainingCapabilities = () => request('/api/admin/pretraining/capabilities')
export const pretrainingPreflight = (body) => request('/api/admin/pretraining/preflight', { method: 'POST', body: JSON.stringify(body) })
export const pretrainingJobs = (query = '') => request(`/api/admin/pretraining/jobs${query}`)
export const createPretrainingJob = (body) => request('/api/admin/pretraining/jobs', { method: 'POST', body: JSON.stringify(body) })
export const pretrainingJobAction = (id, action) => request(`/api/admin/pretraining/jobs/${id}/${action}`, { method: 'POST' })
export const pretrainingEvents = (id) => request(`/api/admin/pretraining/jobs/${id}/events`)
export const pretrainingMetrics = (id) => request(`/api/admin/pretraining/jobs/${id}/metrics`)
export const pretrainingCheckpoints = (id) => request(`/api/admin/pretraining/jobs/${id}/checkpoints`)
export const verifyPretrainingCheckpoint = (id) => request(`/api/admin/pretraining/checkpoints/${id}/verify`, { method: 'POST' })
export const promotePretrainingCheckpoint = (id, overrideComment) => request(`/api/admin/pretraining/checkpoints/${id}/promote`, { method: 'POST', body: JSON.stringify(overrideComment ? { override_comment: overrideComment } : {}) })
export const pretrainingWorkers = () => request('/api/admin/pretraining/workers')
export const pretrainingWorker = (id) => request(`/api/admin/pretraining/workers/${id}`)
export const generatePretrainingCoverage = (id) => request(`/api/admin/pretraining/jobs/${id}/coverage`, { method: 'POST' })
export const pretrainingCoverage = (id) => request(`/api/admin/pretraining/jobs/${id}/coverage`)
export const pretrainingStreams = (id) => request(`/api/admin/pretraining/jobs/${id}/streams`)
export const verifyPretrainingStreams = (id) => request(`/api/admin/pretraining/jobs/${id}/streams/verify`, { method: 'POST' })
export const staleJobs = () => request('/api/admin/pretraining/recovery/stale-jobs')
export const recoverPretrainingJob = (id, comment) => request(`/api/admin/pretraining/jobs/${id}/recover`, { method: 'POST', body: JSON.stringify(comment ? { comment } : {}) })
export const jobRecoveries = (id) => request(`/api/admin/pretraining/jobs/${id}/recoveries`)
export const pretrainingSummary = (id) => request(`/api/admin/pretraining/jobs/${id}/summary`)
export const assessJobQuality = (id) => request(`/api/admin/pretraining/jobs/${id}/quality/assess`, { method: 'POST' })
export const jobQuality = (id) => request(`/api/admin/pretraining/jobs/${id}/quality`)
export const jobQualityIssues = (id) => request(`/api/admin/pretraining/jobs/${id}/quality/issues`)
export const compareCheckpoints = (left, right) => request('/api/admin/pretraining/checkpoints/compare', { method: 'POST', body: JSON.stringify({ left_checkpoint_public_id: left, right_checkpoint_public_id: right }) })
export const compareJobs = (left, right) => request('/api/admin/pretraining/jobs/compare', { method: 'POST', body: JSON.stringify({ left_job_public_id: left, right_job_public_id: right }) })
export const retentionPreview = (id) => request(`/api/admin/pretraining/jobs/${id}/retention/preview`, { method: 'POST' })
export const retentionApply = (id, checkpointIds) => request(`/api/admin/pretraining/jobs/${id}/retention/apply`, { method: 'POST', body: JSON.stringify({ checkpoint_public_ids: checkpointIds }) })

export const baseTrainingExperiments = (query = '') => request(`/api/admin/base-training/experiments${query}`)
export const createBaseTrainingExperiment = (body) => request('/api/admin/base-training/experiments', { method: 'POST', body: JSON.stringify(body) })
export const baseTrainingExperiment = (id) => request(`/api/admin/base-training/experiments/${id}`)
export const patchBaseTrainingExperiment = (id, body) => request(`/api/admin/base-training/experiments/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const generateBaseTrainingProfile = (id) => request(`/api/admin/base-training/experiments/${id}/profile`, { method: 'POST' })
export const baseTrainingProfile = (id) => request(`/api/admin/base-training/experiments/${id}/profile`)
export const evaluateBaseTrainingTokenizer = (id) => request(`/api/admin/base-training/experiments/${id}/tokenizer-evaluate`, { method: 'POST' })
export const baseTrainingTokenizerEvaluation = (id) => request(`/api/admin/base-training/experiments/${id}/tokenizer-evaluation`)
export const createBaseTrainingRun = (id, body) => request(`/api/admin/base-training/experiments/${id}/runs`, { method: 'POST', body: JSON.stringify(body) })
export const baseTrainingRuns = (id) => request(`/api/admin/base-training/experiments/${id}/runs`)
export const baseTrainingRun = (runId) => request(`/api/admin/base-training/runs/${runId}`)
export const queueBaseTrainingRun = (runId) => request(`/api/admin/base-training/runs/${runId}/queue`, { method: 'POST' })
export const evaluateBaseTrainingRun = (runId) => request(`/api/admin/base-training/runs/${runId}/evaluate`, { method: 'POST' })
export const baseTrainingLanguageMetrics = (runId) => request(`/api/admin/base-training/runs/${runId}/language-metrics`)
export const baseTrainingLearningChecks = (runId) => request(`/api/admin/base-training/runs/${runId}/learning-checks`)
export const compareBaseTrainingRuns = (id, left, right) => request(`/api/admin/base-training/experiments/${id}/compare-runs`, { method: 'POST', body: JSON.stringify({ left_run_public_id: left, right_run_public_id: right }) })
export const baseTrainingComparisons = (id) => request(`/api/admin/base-training/experiments/${id}/comparisons`)
export const selectBaseTrainingCandidate = (id, overrideComment) => request(`/api/admin/base-training/experiments/${id}/select-candidate`, { method: 'POST', body: JSON.stringify(overrideComment ? { override_comment: overrideComment } : {}) })
export const baseTrainingCandidate = (id) => request(`/api/admin/base-training/experiments/${id}/candidate`)
export const baseTrainingManifest = (id) => request(`/api/admin/base-training/experiments/${id}/manifest`)
export const verifyBaseTrainingManifest = (id) => request(`/api/admin/base-training/experiments/${id}/manifest/verify`, { method: 'POST' })

export const instructionTuningExperiments = (query = '') => request(`/api/admin/instruction-tuning/experiments${query}`)
export const createInstructionTuningExperiment = (body) => request('/api/admin/instruction-tuning/experiments', { method: 'POST', body: JSON.stringify(body) })
export const instructionTuningExperiment = (id) => request(`/api/admin/instruction-tuning/experiments/${id}`)
export const patchInstructionTuningExperiment = (id, body) => request(`/api/admin/instruction-tuning/experiments/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const generateInstructionTuningProfile = (id) => request(`/api/admin/instruction-tuning/experiments/${id}/profile`, { method: 'POST' })
export const instructionTuningProfile = (id) => request(`/api/admin/instruction-tuning/experiments/${id}/profile`)
export const instructionTuningTemplates = () => request('/api/admin/instruction-tuning/templates')
export const createInstructionTuningTemplate = (body) => request('/api/admin/instruction-tuning/templates', { method: 'POST', body: JSON.stringify(body) })
export const instructionTuningTemplate = (id) => request(`/api/admin/instruction-tuning/templates/${id}`)
export const validateInstructionTuningTemplate = (id) => request(`/api/admin/instruction-tuning/templates/${id}/validate`, { method: 'POST' })
export const createInstructionTuningRun = (id, body) => request(`/api/admin/instruction-tuning/experiments/${id}/runs`, { method: 'POST', body: JSON.stringify(body) })
export const instructionTuningRuns = (id) => request(`/api/admin/instruction-tuning/experiments/${id}/runs`)
export const instructionTuningRun = (runId) => request(`/api/admin/instruction-tuning/runs/${runId}`)
export const queueInstructionTuningRun = (runId) => request(`/api/admin/instruction-tuning/runs/${runId}/queue`, { method: 'POST' })
export const evaluateInstructionTuningRun = (runId) => request(`/api/admin/instruction-tuning/runs/${runId}/evaluate`, { method: 'POST' })
export const instructionTuningMetrics = (runId) => request(`/api/admin/instruction-tuning/runs/${runId}/metrics`)
export const instructionTuningLanguageMetrics = (runId) => request(`/api/admin/instruction-tuning/runs/${runId}/language-metrics`)
export const instructionTuningLearningChecks = (runId) => request(`/api/admin/instruction-tuning/runs/${runId}/learning-checks`)
export const diagnosticGenerate = (runId, promptText, maxNewTokens) => request(`/api/admin/instruction-tuning/runs/${runId}/diagnostic-generate`, { method: 'POST', body: JSON.stringify({ prompt_text: promptText, max_new_tokens: maxNewTokens }) })
export const compareInstructionTuningRuns = (id, left, right) => request(`/api/admin/instruction-tuning/experiments/${id}/compare-runs`, { method: 'POST', body: JSON.stringify({ left_run_public_id: left, right_run_public_id: right }) })
export const instructionTuningComparisons = (id) => request(`/api/admin/instruction-tuning/experiments/${id}/comparisons`)
export const selectInstructionTuningCandidate = (id, overrideComment) => request(`/api/admin/instruction-tuning/experiments/${id}/select-candidate`, { method: 'POST', body: JSON.stringify(overrideComment ? { override_comment: overrideComment } : {}) })
export const instructionTuningCandidate = (id) => request(`/api/admin/instruction-tuning/experiments/${id}/candidate`)
export const instructionTuningManifest = (id) => request(`/api/admin/instruction-tuning/experiments/${id}/manifest`)
export const verifyInstructionTuningManifest = (id) => request(`/api/admin/instruction-tuning/experiments/${id}/manifest/verify`, { method: 'POST' })

export const evalCandidates = () => request('/api/admin/model-evaluation/candidates')
export const evalSuites = () => request('/api/admin/model-evaluation/suites')
export const createEvalSuite = (body) => request('/api/admin/model-evaluation/suites', { method: 'POST', body: JSON.stringify(body) })
export const evalSuite = (id) => request(`/api/admin/model-evaluation/suites/${id}`)
export const validateEvalSuite = (id) => request(`/api/admin/model-evaluation/suites/${id}/validate`, { method: 'POST' })
export const activateEvalSuite = (id) => request(`/api/admin/model-evaluation/suites/${id}/activate`, { method: 'POST' })
export const evalFixtureSets = (suiteId) => request(`/api/admin/model-evaluation/suites/${suiteId}/fixture-sets`)
export const createEvalFixtureSet = (suiteId, body) => request(`/api/admin/model-evaluation/suites/${suiteId}/fixture-sets`, { method: 'POST', body: JSON.stringify(body) })
export const evalFixtureSet = (id) => request(`/api/admin/model-evaluation/fixture-sets/${id}`)
export const evalFixtureSetCoverage = (id) => request(`/api/admin/model-evaluation/fixture-sets/${id}/coverage`)
export const evalFixtures = (fixtureSetId) => request(`/api/admin/model-evaluation/fixture-sets/${fixtureSetId}/fixtures`)
export const evalRuns = () => request('/api/admin/model-evaluation/runs')
export const createEvalRun = (body) => request('/api/admin/model-evaluation/runs', { method: 'POST', body: JSON.stringify(body) })
export const evalRun = (runId) => request(`/api/admin/model-evaluation/runs/${runId}`)
export const executeEvalRun = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/execute`, { method: 'POST' })
export const evalOutputs = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/outputs`)
export const evalMetrics = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/metrics`)
export const evalIssues = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/issues`)
export const submitEvalHumanReview = (body) => request('/api/admin/model-evaluation/human-reviews', { method: 'POST', body: JSON.stringify(body) })
export const evalReviewQueue = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/review-queue`)
export const evalReviews = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/reviews`)
export const assessEvalReadiness = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/assess-readiness`, { method: 'POST' })
export const evalReadiness = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/readiness`)
export const compareEvalRuns = (left, right) => request('/api/admin/model-evaluation/comparisons', { method: 'POST', body: JSON.stringify({ left_run_public_id: left, right_run_public_id: right }) })
export const generateEvalManifest = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/manifest`, { method: 'POST' })
export const verifyEvalManifest = (runId) => request(`/api/admin/model-evaluation/runs/${runId}/manifest/verify`, { method: 'POST' })

export const releaseFamilies = () => request('/api/admin/model-releases/families')
export const createReleaseFamily = (body) => request('/api/admin/model-releases/families', { method: 'POST', body: JSON.stringify(body) })
export const releaseFamily = (id) => request(`/api/admin/model-releases/families/${id}`)
export const patchReleaseFamily = (id, body) => request(`/api/admin/model-releases/families/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const releaseCandidates = () => request('/api/admin/model-releases/candidates')
export const createReleaseCandidate = (body) => request('/api/admin/model-releases/candidates', { method: 'POST', body: JSON.stringify(body) })
export const releaseCandidate = (id) => request(`/api/admin/model-releases/candidates/${id}`)
export const collectReleaseArtifacts = (id) => request(`/api/admin/model-releases/candidates/${id}/collect-artifacts`, { method: 'POST' })
export const verifyReleaseArtifacts = (id) => request(`/api/admin/model-releases/candidates/${id}/verify-artifacts`, { method: 'POST' })
export const assessReleaseEligibility = (id) => request(`/api/admin/model-releases/candidates/${id}/eligibility/assess`, { method: 'POST' })
export const releaseEligibility = (id) => request(`/api/admin/model-releases/candidates/${id}/eligibility`)
export const releaseIssues = (id) => request(`/api/admin/model-releases/candidates/${id}/issues`)
export const createReleaseModelCard = (id) => request(`/api/admin/model-releases/candidates/${id}/model-card`, { method: 'POST' })
export const releaseModelCard = (id) => request(`/api/admin/model-releases/candidates/${id}/model-card`)
export const validateReleaseModelCard = (id) => request(`/api/admin/model-releases/candidates/${id}/model-card/validate`, { method: 'POST' })
export const createReleaseManifest = (id) => request(`/api/admin/model-releases/candidates/${id}/manifest`, { method: 'POST' })
export const releaseManifest = (id) => request(`/api/admin/model-releases/candidates/${id}/manifest`)
export const verifyReleaseManifest = (id) => request(`/api/admin/model-releases/candidates/${id}/manifest/verify`, { method: 'POST' })
export const submitReleaseApproval = (id, body) => request(`/api/admin/model-releases/candidates/${id}/approvals`, { method: 'POST', body: JSON.stringify(body) })
export const releaseApprovals = (id) => request(`/api/admin/model-releases/candidates/${id}/approvals`)
export const releases = () => request('/api/admin/model-releases/releases')
export const createRelease = (body) => request('/api/admin/model-releases/releases', { method: 'POST', body: JSON.stringify(body) })
export const release = (id) => request(`/api/admin/model-releases/releases/${id}`)
export const deprecateRelease = (id) => request(`/api/admin/model-releases/releases/${id}/deprecate`, { method: 'POST' })
export const retireRelease = (id) => request(`/api/admin/model-releases/releases/${id}/retire`, { method: 'POST' })
export const compareReleases = (left, right) => request('/api/admin/model-releases/releases/compare', { method: 'POST', body: JSON.stringify({ left_release_public_id: left, right_release_public_id: right }) })
export const releaseComparison = (id) => request(`/api/admin/model-releases/comparisons/${id}`)
export const buildReleaseBundle = (id) => request(`/api/admin/model-releases/releases/${id}/bundle`, { method: 'POST' })
export const releaseBundles = (id) => request(`/api/admin/model-releases/releases/${id}/bundles`)
export const verifyReleaseBundle = (id) => request(`/api/admin/model-releases/bundles/${id}/verify`, { method: 'POST' })
export const createRollbackPlan = (releaseId, body) => request(`/api/admin/model-releases/releases/${releaseId}/rollback-plans`, { method: 'POST', body: JSON.stringify(body) })
export const rollbackPlan = (id) => request(`/api/admin/model-releases/rollback-plans/${id}`)
export const validateRollbackPlan = (id) => request(`/api/admin/model-releases/rollback-plans/${id}/validate`, { method: 'POST' })
export const approveRollbackPlan = (id) => request(`/api/admin/model-releases/rollback-plans/${id}/approve`, { method: 'POST' })
export const executeRollbackPlan = (id) => request(`/api/admin/model-releases/rollback-plans/${id}/execute`, { method: 'POST' })

const IR = '/api/admin/inference-runtime'
export const runtimeProfiles = () => request(`${IR}/profiles`)
export const createRuntimeProfile = (body) => request(`${IR}/profiles`, { method: 'POST', body: JSON.stringify(body) })
export const runtimeProfile = (id) => request(`${IR}/profiles/${id}`)
export const patchRuntimeProfile = (id, body) => request(`${IR}/profiles/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const runtimeInstances = () => request(`${IR}/instances`)
export const createRuntimeInstance = (runtimeProfilePublicId) => request(`${IR}/instances`, { method: 'POST', body: JSON.stringify({ runtime_profile_public_id: runtimeProfilePublicId }) })
export const runtimeInstance = (id) => request(`${IR}/instances/${id}`)
export const startRuntimeInstance = (id) => request(`${IR}/instances/${id}/start`, { method: 'POST' })
export const stopRuntimeInstance = (id) => request(`${IR}/instances/${id}/stop`, { method: 'POST' })
export const loadRuntimeInstance = (id, releasePublicId) => request(`${IR}/instances/${id}/load`, { method: 'POST', body: JSON.stringify({ release_public_id: releasePublicId }) })
export const unloadRuntimeInstance = (id) => request(`${IR}/instances/${id}/unload`, { method: 'POST' })
export const runtimeInstanceHealthCheck = (id) => request(`${IR}/instances/${id}/health-check`, { method: 'POST' })
export const assessRuntimeCompatibility = (releaseId, runtimeProfilePublicId) => request(`${IR}/releases/${releaseId}/compatibility/assess`, { method: 'POST', body: JSON.stringify({ runtime_profile_public_id: runtimeProfilePublicId }) })
export const runtimeCompatibility = (releaseId) => request(`${IR}/releases/${releaseId}/compatibility`)
export const assignmentScopes = () => request(`${IR}/assignment-scopes`)
export const assignments = () => request(`${IR}/assignments`)
export const createAssignment = (body) => request(`${IR}/assignments`, { method: 'POST', body: JSON.stringify(body) })
export const assignment = (id) => request(`${IR}/assignments/${id}`)
export const patchAssignment = (id, body) => request(`${IR}/assignments/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const validateAssignment = (id) => request(`${IR}/assignments/${id}/validate`, { method: 'POST' })
export const approveAssignment = (id, body) => request(`${IR}/assignments/${id}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const activateAssignment = (id, explicitActivationConfirmed = false) => request(`${IR}/assignments/${id}/activate`, { method: 'POST', body: JSON.stringify({ explicit_activation_confirmed: explicitActivationConfirmed }) })
export const pauseAssignment = (id) => request(`${IR}/assignments/${id}/pause`, { method: 'POST' })
export const resumeAssignment = (id) => request(`${IR}/assignments/${id}/resume`, { method: 'POST' })
export const assignmentVersions = (id) => request(`${IR}/assignments/${id}/versions`)
export const assignmentEvents = (id) => request(`${IR}/assignments/${id}/events`)
export const runtimeDiagnosticGenerate = (id, body) => request(`${IR}/assignments/${id}/diagnostic-generate`, { method: 'POST', body: JSON.stringify(body) })
export const createChatLabSession = (id, body) => request(`${IR}/assignments/${id}/sessions`, { method: 'POST', body: JSON.stringify(body) })
export const chatLabSession = (id) => request(`${IR}/sessions/${id}`)
export const postChatLabMessage = (id, message) => request(`${IR}/sessions/${id}/messages`, { method: 'POST', body: JSON.stringify({ message }) })
export const closeChatLabSession = (id) => request(`${IR}/sessions/${id}/close`, { method: 'POST' })
export const startCanary = (id, body) => request(`${IR}/assignments/${id}/canary/start`, { method: 'POST', body: JSON.stringify(body) })
export const executeCanary = (id, fixturePrompts) => request(`${IR}/assignments/${id}/canary/execute`, { method: 'POST', body: JSON.stringify({ fixture_prompts: fixturePrompts }) })
export const stopCanary = (id, reason = 'admin_stop') => request(`${IR}/assignments/${id}/canary/stop`, { method: 'POST', body: JSON.stringify({ reason }) })
export const canaryResults = (id) => request(`${IR}/assignments/${id}/canary/results`)
export const rollbackPreview = (id, targetVersionPublicId) => request(`${IR}/assignments/${id}/rollback/preview`, { method: 'POST', body: JSON.stringify({ target_version_public_id: targetVersionPublicId }) })
export const rollbackExecute = (id, targetVersionPublicId) => request(`${IR}/assignments/${id}/rollback/execute`, { method: 'POST', body: JSON.stringify({ target_version_public_id: targetVersionPublicId }) })
export const runtimeManifest = (id) => request(`${IR}/assignments/${id}/manifest`)
export const verifyRuntimeManifest = (id) => request(`${IR}/assignments/${id}/manifest/verify`, { method: 'POST' })

const RAG = '/api/admin/rag'
export const ragSpaces = () => request(`${RAG}/spaces`)
export const createRagSpace = (body) => request(`${RAG}/spaces`, { method: 'POST', body: JSON.stringify(body) })
export const patchRagSpace = (id, body) => request(`${RAG}/spaces/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const ragSources = (spaceId) => request(`${RAG}/spaces/${spaceId}/sources`)
export const createRagSource = (spaceId, body) => request(`${RAG}/spaces/${spaceId}/sources`, { method: 'POST', body: JSON.stringify(body) })
export const patchRagSource = (id, body) => request(`${RAG}/sources/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const ragSourceVersions = (sourceId) => request(`${RAG}/sources/${sourceId}/versions`)
export const createRagSourceVersion = (sourceId) => request(`${RAG}/sources/${sourceId}/versions`, { method: 'POST' })
export const validateRagSourceVersion = (id) => request(`${RAG}/versions/${id}/validate`, { method: 'POST' })
export const createRagChunkSet = (versionId, body) => request(`${RAG}/versions/${versionId}/chunk-sets`, { method: 'POST', body: JSON.stringify(body) })
export const ragChunkSet = (id) => request(`${RAG}/chunk-sets/${id}`)
export const ragChunks = (chunkSetId) => request(`${RAG}/chunk-sets/${chunkSetId}/chunks`)
export const validateRagChunkSet = (id) => request(`${RAG}/chunk-sets/${id}/validate`, { method: 'POST' })
export const ragEmbeddingModels = () => request(`${RAG}/embedding-models`)
export const createRagEmbeddingModel = (body) => request(`${RAG}/embedding-models`, { method: 'POST', body: JSON.stringify(body) })
export const createRagEmbeddingRun = (chunkSetId, body) => request(`${RAG}/chunk-sets/${chunkSetId}/embedding-runs`, { method: 'POST', body: JSON.stringify(body) })
export const ragEmbeddingRun = (id) => request(`${RAG}/embedding-runs/${id}`)
export const executeRagEmbeddingRun = (id) => request(`${RAG}/embedding-runs/${id}/execute`, { method: 'POST' })
export const verifyRagEmbeddingRun = (id) => request(`${RAG}/embedding-runs/${id}/verify`)
export const createRagVectorIndex = (embeddingRunId, body = {}) => request(`${RAG}/embedding-runs/${embeddingRunId}/vector-index`, { method: 'POST', body: JSON.stringify(body) })
export const ragVectorIndex = (id) => request(`${RAG}/vector-indexes/${id}`)
export const buildRagVectorIndex = (id) => request(`${RAG}/vector-indexes/${id}/build`, { method: 'POST' })
export const validateRagVectorIndex = (id) => request(`${RAG}/vector-indexes/${id}/validate`, { method: 'POST' })
export const activateRagVectorIndex = (id) => request(`${RAG}/vector-indexes/${id}/activate`, { method: 'POST' })
export const createRagKeywordIndex = (chunkSetId, body = {}) => request(`${RAG}/chunk-sets/${chunkSetId}/keyword-index`, { method: 'POST', body: JSON.stringify(body) })
export const ragKeywordIndex = (id) => request(`${RAG}/keyword-indexes/${id}`)
export const buildRagKeywordIndex = (id) => request(`${RAG}/keyword-indexes/${id}/build`, { method: 'POST' })
export const validateRagKeywordIndex = (id) => request(`${RAG}/keyword-indexes/${id}/validate`, { method: 'POST' })
export const activateRagKeywordIndex = (id) => request(`${RAG}/keyword-indexes/${id}/activate`, { method: 'POST' })
export const ragRetrievalProfiles = () => request(`${RAG}/retrieval-profiles`)
export const createRagRetrievalProfile = (spaceId, body) => request(`${RAG}/spaces/${spaceId}/retrieval-profiles`, { method: 'POST', body: JSON.stringify(body) })
export const patchRagRetrievalProfile = (id, body) => request(`${RAG}/retrieval-profiles/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const validateRagRetrievalProfile = (id) => request(`${RAG}/retrieval-profiles/${id}/validate`, { method: 'POST' })
export const activateRagRetrievalProfile = (id) => request(`${RAG}/retrieval-profiles/${id}/activate`, { method: 'POST' })
export const deactivateRagRetrievalProfile = (id) => request(`${RAG}/retrieval-profiles/${id}/deactivate`, { method: 'POST' })
export const ragLatestVectorIndexForSpace = (spaceId) => request(`${RAG}/spaces/${spaceId}/latest-vector-index`)
export const ragRetrieve = (body) => request(`${RAG}/retrieve`, { method: 'POST', body: JSON.stringify(body) })
export const ragGroundedAnswer = (body) => request(`${RAG}/grounded-answer`, { method: 'POST', body: JSON.stringify(body) })
export const createRagChatLabSession = (body) => request(`${RAG}/chat-lab/sessions`, { method: 'POST', body: JSON.stringify(body) })
export const postRagChatLabMessage = (id, message, retrievalProfilePublicId) => request(`${RAG}/chat-lab/sessions/${id}/messages`, { method: 'POST', body: JSON.stringify({ message, retrieval_profile_public_id: retrievalProfilePublicId }) })
export const closeRagChatLabSession = (id) => request(`${RAG}/chat-lab/sessions/${id}/close`, { method: 'POST' })
export const ragEvaluationSuites = () => request(`${RAG}/evaluation-suites`)
export const createRagEvaluationSuite = (spaceId, body) => request(`${RAG}/spaces/${spaceId}/evaluation-suites`, { method: 'POST', body: JSON.stringify(body) })
export const addRagEvaluationFixture = (suiteId, body) => request(`${RAG}/evaluation-suites/${suiteId}/fixtures`, { method: 'POST', body: JSON.stringify(body) })
export const createRagEvaluationRun = (suiteId, body) => request(`${RAG}/evaluation-suites/${suiteId}/runs`, { method: 'POST', body: JSON.stringify(body) })
export const executeRagEvaluationRun = (id) => request(`${RAG}/evaluation-runs/${id}/execute`, { method: 'POST' })
export const ragEvaluationMetrics = (id) => request(`${RAG}/evaluation-runs/${id}/metrics`)
export const createRagIndexComparison = (body) => request(`${RAG}/index-comparisons`, { method: 'POST', body: JSON.stringify(body) })
export const generateRagManifest = (spaceId) => request(`${RAG}/spaces/${spaceId}/manifest`, { method: 'POST' })
export const verifyRagManifest = (spaceId) => request(`${RAG}/spaces/${spaceId}/manifest/verify`)

const CM = '/api/admin/conversation-memory'
export const memoryPolicies = () => request(`${CM}/policies`)
export const createMemoryPolicy = (body) => request(`${CM}/policies`, { method: 'POST', body: JSON.stringify(body) })
export const memoryPolicy = (id) => request(`${CM}/policies/${id}`)
export const patchMemoryPolicy = (id, body) => request(`${CM}/policies/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const validateMemoryPolicy = (id) => request(`${CM}/policies/${id}/validate`, { method: 'POST' })
export const activateMemoryPolicy = (id) => request(`${CM}/policies/${id}/activate`, { method: 'POST' })
export const conversationSessions = () => request(`${CM}/sessions`)
export const createConversationSession = (body) => request(`${CM}/sessions`, { method: 'POST', body: JSON.stringify(body) })
export const conversationSession = (id) => request(`${CM}/sessions/${id}`)
export const pauseConversationSession = (id) => request(`${CM}/sessions/${id}/pause`, { method: 'POST' })
export const resumeConversationSession = (id) => request(`${CM}/sessions/${id}/resume`, { method: 'POST' })
export const closeConversationSession = (id) => request(`${CM}/sessions/${id}/close`, { method: 'POST' })
export const expireConversationSession = (id) => request(`${CM}/sessions/${id}/expire`, { method: 'POST' })
export const conversationSessionTurns = (id) => request(`${CM}/sessions/${id}/turns`)
export const postConversationMessage = (id, body) => request(`${CM}/sessions/${id}/messages`, { method: 'POST', body: JSON.stringify(body) })
export const orchestrationRun = (id) => request(`${CM}/orchestration-runs/${id}`)
export const orchestrationContext = (id) => request(`${CM}/orchestration-runs/${id}/context`)
export const orchestrationResponse = (id) => request(`${CM}/orchestration-runs/${id}/response`)
export const orchestrationIssues = (id) => request(`${CM}/orchestration-runs/${id}/issues`)
export const createConversationSummary = (sessionId, body = {}) => request(`${CM}/sessions/${sessionId}/summaries`, { method: 'POST', body: JSON.stringify(body) })
export const conversationSummaries = (sessionId) => request(`${CM}/sessions/${sessionId}/summaries`)
export const conversationSummary = (id) => request(`${CM}/summaries/${id}`)
export const validateConversationSummary = (id) => request(`${CM}/summaries/${id}/validate`, { method: 'POST' })
export const acceptConversationSummary = (id) => request(`${CM}/summaries/${id}/accept`, { method: 'POST' })
export const rejectConversationSummary = (id) => request(`${CM}/summaries/${id}/reject`, { method: 'POST' })
export const memoryConsents = () => request(`${CM}/consents`)
export const createMemoryConsent = (body) => request(`${CM}/consents`, { method: 'POST', body: JSON.stringify(body) })
export const memoryConsent = (id) => request(`${CM}/consents/${id}`)
export const revokeMemoryConsent = (id) => request(`${CM}/consents/${id}/revoke`, { method: 'POST' })
export const expireMemoryConsent = (id) => request(`${CM}/consents/${id}/expire`, { method: 'POST' })
export const memoryItems = (participantScopeKey) => request(`${CM}/memory-items${participantScopeKey ? `?participant_scope_key=${encodeURIComponent(participantScopeKey)}` : ''}`)
export const createMemoryItem = (body) => request(`${CM}/memory-items`, { method: 'POST', body: JSON.stringify(body) })
export const memoryItem = (id) => request(`${CM}/memory-items/${id}`)
export const confirmMemoryItem = (id) => request(`${CM}/memory-items/${id}/confirm`, { method: 'POST' })
export const rejectMemoryItem = (id) => request(`${CM}/memory-items/${id}/reject`, { method: 'POST' })
export const correctMemoryItem = (id, body) => request(`${CM}/memory-items/${id}/correct`, { method: 'POST', body: JSON.stringify(body) })
export const expireMemoryItem = (id) => request(`${CM}/memory-items/${id}/expire`, { method: 'POST' })
export const deleteMemoryItem = (id) => request(`${CM}/memory-items/${id}/delete`, { method: 'POST' })
export const memoryItemVersions = (id) => request(`${CM}/memory-items/${id}/versions`)
export const memoryItemEvents = (id) => request(`${CM}/memory-items/${id}/events`)
export const memoryRetrievalProfiles = () => request(`${CM}/retrieval-profiles`)
export const createMemoryRetrievalProfile = (body) => request(`${CM}/retrieval-profiles`, { method: 'POST', body: JSON.stringify(body) })
export const memoryRetrievalProfile = (id) => request(`${CM}/retrieval-profiles/${id}`)
export const validateMemoryRetrievalProfile = (id) => request(`${CM}/retrieval-profiles/${id}/validate`, { method: 'POST' })
export const activateMemoryRetrievalProfile = (id) => request(`${CM}/retrieval-profiles/${id}/activate`, { method: 'POST' })
export const retrieveMemory = (body) => request(`${CM}/retrieve`, { method: 'POST', body: JSON.stringify(body) })
export const memoryRetrievalRun = (id) => request(`${CM}/retrieval-runs/${id}`)
export const memoryRetrievalResults = (id) => request(`${CM}/retrieval-runs/${id}/results`)
export const memoryEvaluationSuites = () => request(`${CM}/evaluation-suites`)
export const createMemoryEvaluationSuite = (body) => request(`${CM}/evaluation-suites`, { method: 'POST', body: JSON.stringify(body) })
export const addMemoryEvaluationFixture = (suiteId, body) => request(`${CM}/evaluation-suites/${suiteId}/fixtures`, { method: 'POST', body: JSON.stringify(body) })
export const createMemoryEvaluationRun = (suiteId, body) => request(`${CM}/evaluation-suites/${suiteId}/runs`, { method: 'POST', body: JSON.stringify(body) })
export const executeMemoryEvaluationRun = (id) => request(`${CM}/evaluation-runs/${id}/execute`, { method: 'POST' })
export const memoryEvaluationRun = (id) => request(`${CM}/evaluation-runs/${id}`)
export const memoryEvaluationMetrics = (id) => request(`${CM}/evaluation-runs/${id}/metrics`)
export const generateMemoryManifest = (policyId) => request(`${CM}/policies/${policyId}/manifest`, { method: 'POST' })
export const verifyMemoryManifest = (policyId) => request(`${CM}/policies/${policyId}/manifest/verify`)

const FB = '/api/admin/feedback'
export const feedbackPolicies = () => request(`${FB}/policies`)
export const createFeedbackPolicy = (body) => request(`${FB}/policies`, { method: 'POST', body: JSON.stringify(body) })
export const feedbackPolicy = (id) => request(`${FB}/policies/${id}`)
export const patchFeedbackPolicy = (id, body) => request(`${FB}/policies/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const validateFeedbackPolicy = (id) => request(`${FB}/policies/${id}/validate`, { method: 'POST' })
export const activateFeedbackPolicy = (id) => request(`${FB}/policies/${id}/activate`, { method: 'POST' })

export const feedbackEvents = (participantScopeKey) => request(`${FB}/events${participantScopeKey ? `?participant_scope_key=${encodeURIComponent(participantScopeKey)}` : ''}`)
export const submitFeedbackEvent = (body) => request(`${FB}/events`, { method: 'POST', body: JSON.stringify(body) })
export const feedbackEvent = (id) => request(`${FB}/events/${id}`)
export const triageFeedbackEvent = (id) => request(`${FB}/events/${id}/triage`, { method: 'POST' })
export const deleteFeedbackEvent = (id) => request(`${FB}/events/${id}/delete`, { method: 'POST' })
export const feedbackClassifications = (id) => request(`${FB}/events/${id}/classifications`)
export const addFeedbackClassification = (id, body) => request(`${FB}/events/${id}/classifications`, { method: 'POST', body: JSON.stringify(body) })
export const feedbackFindings = (id) => request(`${FB}/events/${id}/findings`)

export const reviewQueues = () => request(`${FB}/review-queues`)
export const createReviewQueue = (body) => request(`${FB}/review-queues`, { method: 'POST', body: JSON.stringify(body) })
export const reviewQueue = (id) => request(`${FB}/review-queues/${id}`)
export const assignReview = (queueId, body) => request(`${FB}/review-queues/${queueId}/assign`, { method: 'POST', body: JSON.stringify(body) })
export const reviewQueueItems = (queueId) => request(`${FB}/review-queues/${queueId}/items`)

export const createFeedbackReview = (eventId, body) => request(`${FB}/events/${eventId}/reviews`, { method: 'POST', body: JSON.stringify(body) })
export const feedbackReviews = (eventId) => request(`${FB}/events/${eventId}/reviews`)
export const feedbackReviewSummary = (eventId) => request(`${FB}/events/${eventId}/review-summary`)

export const createCorrectedResponse = (eventId, body) => request(`${FB}/events/${eventId}/corrected-responses`, { method: 'POST', body: JSON.stringify(body) })
export const correctedResponsesForEvent = (eventId) => request(`${FB}/events/${eventId}/corrected-responses`)
export const correctedResponse = (id) => request(`${FB}/corrected-responses/${id}`)
export const validateCorrectedResponse = (id) => request(`${FB}/corrected-responses/${id}/validate`, { method: 'POST' })
export const rejectCorrectedResponse = (id) => request(`${FB}/corrected-responses/${id}/reject`, { method: 'POST' })

export const datasetCandidates = () => request(`${FB}/dataset-candidates`)
export const createDatasetCandidate = (eventId, body) => request(`${FB}/events/${eventId}/dataset-candidates`, { method: 'POST', body: JSON.stringify(body) })
export const datasetCandidate = (id) => request(`${FB}/dataset-candidates/${id}`)
export const validateDatasetCandidate = (id) => request(`${FB}/dataset-candidates/${id}/validate`, { method: 'POST' })
export const approveDatasetCandidate = (id, body) => request(`${FB}/dataset-candidates/${id}/approve`, { method: 'POST', body: JSON.stringify(body || {}) })
export const rejectDatasetCandidate = (id, body) => request(`${FB}/dataset-candidates/${id}/reject`, { method: 'POST', body: JSON.stringify(body || {}) })
export const quarantineDatasetCandidate = (id, body) => request(`${FB}/dataset-candidates/${id}/quarantine`, { method: 'POST', body: JSON.stringify(body || {}) })
export const datasetCandidateVersions = (id) => request(`${FB}/dataset-candidates/${id}/versions`)
export const datasetCandidateIssues = (id) => request(`${FB}/dataset-candidates/${id}/issues`)
export const exportDatasetCandidate = (id) => request(`${FB}/dataset-candidates/${id}/export`, { method: 'POST' })

export const regressionSuites = () => request(`${FB}/regression-suites`)
export const createRegressionSuite = (body) => request(`${FB}/regression-suites`, { method: 'POST', body: JSON.stringify(body) })
export const regressionSuite = (id) => request(`${FB}/regression-suites/${id}`)
export const addRegressionFixture = (suiteId, body) => request(`${FB}/regression-suites/${suiteId}/fixtures`, { method: 'POST', body: JSON.stringify(body) })
export const validateRegressionSuite = (id) => request(`${FB}/regression-suites/${id}/validate`, { method: 'POST' })
export const activateRegressionSuite = (id) => request(`${FB}/regression-suites/${id}/activate`, { method: 'POST' })

export const createRegressionRun = (suiteId, body) => request(`${FB}/regression-suites/${suiteId}/runs`, { method: 'POST', body: JSON.stringify(body) })
export const executeRegressionRun = (id) => request(`${FB}/regression-runs/${id}/execute`, { method: 'POST' })
export const regressionRun = (id) => request(`${FB}/regression-runs/${id}`)
export const regressionResults = (id) => request(`${FB}/regression-runs/${id}/results`)
export const regressionMetrics = (id) => request(`${FB}/regression-runs/${id}/metrics`)

export const compareRegressionRuns = (body) => request(`${FB}/regression-runs/compare`, { method: 'POST', body: JSON.stringify(body) })
export const comparison = (id) => request(`${FB}/comparisons/${id}`)
export const createImprovementReport = (body) => request(`${FB}/improvement-reports`, { method: 'POST', body: JSON.stringify(body || {}) })

export const feedbackManifest = (policyId) => request(`${FB}/policies/${policyId}/manifest`)
export const verifyFeedbackManifest = (policyId) => request(`${FB}/policies/${policyId}/manifest/verify`, { method: 'POST' })

const CORPUS = '/api/admin/corpus'
export const corpusPolicies = () => request(`${CORPUS}/policies`)
export const createCorpusPolicy = (body) => request(`${CORPUS}/policies`, { method: 'POST', body: JSON.stringify(body) })
export const corpusPolicy = (id) => request(`${CORPUS}/policies/${id}`)
export const patchCorpusPolicy = (id, body) => request(`${CORPUS}/policies/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const validateCorpusPolicy = (id) => request(`${CORPUS}/policies/${id}/validate`, { method: 'POST' })
export const activateCorpusPolicy = (id) => request(`${CORPUS}/policies/${id}/activate`, { method: 'POST' })

export const corpusSources = () => request(`${CORPUS}/sources`)
export const createCorpusSource = (body) => request(`${CORPUS}/sources`, { method: 'POST', body: JSON.stringify(body) })
export const corpusSource = (id) => request(`${CORPUS}/sources/${id}`)
export const patchCorpusSource = (id, body) => request(`${CORPUS}/sources/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const transitionCorpusSource = (id, body) => request(`${CORPUS}/sources/${id}/transition`, { method: 'POST', body: JSON.stringify(body) })
export const verifyCorpusSourceOrigin = (id, body) => request(`${CORPUS}/sources/${id}/verify-origin`, { method: 'POST', body: JSON.stringify(body) })
export const corpusSourceTrainingEligibility = (id) => request(`${CORPUS}/sources/${id}/training-eligibility`)

export const createCorpusLicence = (sourceId, body) => request(`${CORPUS}/sources/${sourceId}/licences`, { method: 'POST', body: JSON.stringify(body) })
export const reviewCorpusLicence = (id, body) => request(`${CORPUS}/licences/${id}/review`, { method: 'POST', body: JSON.stringify(body) })

export const createCorpusSnapshot = (sourceId, body) => request(`${CORPUS}/sources/${sourceId}/snapshots`, { method: 'POST', body: JSON.stringify(body) })
export const corpusSnapshotsForSource = (sourceId) => request(`${CORPUS}/sources/${sourceId}/snapshots`)
export const corpusSnapshot = (id) => request(`${CORPUS}/snapshots/${id}`)

export const createCorpusExtractionRun = (snapshotId, body) => request(`${CORPUS}/snapshots/${snapshotId}/extraction-runs`, { method: 'POST', body: JSON.stringify(body) })
export const corpusExtractionRun = (id) => request(`${CORPUS}/extraction-runs/${id}`)

export const createCorpusNormalizationRun = (extractionRunId, body) => request(`${CORPUS}/extraction-runs/${extractionRunId}/normalization-runs`, { method: 'POST', body: JSON.stringify(body || {}) })
export const corpusNormalizationRun = (id) => request(`${CORPUS}/normalization-runs/${id}`)

export const segmentCorpusDocument = (documentId, body) => request(`${CORPUS}/normalized-documents/${documentId}/segment`, { method: 'POST', body: JSON.stringify(body || {}) })

export const assessCorpusSegment = (id) => request(`${CORPUS}/segments/${id}/assess`, { method: 'POST' })

export const createCorpusDeduplicationRun = (body) => request(`${CORPUS}/deduplication-runs`, { method: 'POST', body: JSON.stringify(body || {}) })
export const corpusDeduplicationRun = (id) => request(`${CORPUS}/deduplication-runs/${id}`)

export const createCorpusContaminationRun = (body) => request(`${CORPUS}/contamination-runs`, { method: 'POST', body: JSON.stringify(body || {}) })
export const corpusContaminationRun = (id) => request(`${CORPUS}/contamination-runs/${id}`)

export const corpusCollections = () => request(`${CORPUS}/collections`)
export const createCorpusCollection = (body) => request(`${CORPUS}/collections`, { method: 'POST', body: JSON.stringify(body) })
export const corpusCollection = (id) => request(`${CORPUS}/collections/${id}`)
export const addCorpusCollectionMember = (id, body) => request(`${CORPUS}/collections/${id}/members`, { method: 'POST', body: JSON.stringify(body) })

export const corpusBalancePolicies = () => request(`${CORPUS}/balance-policies`)
export const createCorpusBalancePolicy = (body) => request(`${CORPUS}/balance-policies`, { method: 'POST', body: JSON.stringify(body) })

export const corpusBuilds = () => request(`${CORPUS}/builds`)
export const createCorpusBuild = (body) => request(`${CORPUS}/builds`, { method: 'POST', body: JSON.stringify(body) })
export const corpusBuild = (id) => request(`${CORPUS}/builds/${id}`)
export const corpusBuildBalanceReport = (id) => request(`${CORPUS}/builds/${id}/balance-report`)

export const corpusVersions = () => request(`${CORPUS}/versions`)
export const createCorpusVersion = (buildId, body) => request(`${CORPUS}/builds/${buildId}/versions`, { method: 'POST', body: JSON.stringify(body) })
export const corpusVersion = (id) => request(`${CORPUS}/versions/${id}`)

export const createCorpusExport = (versionId, body) => request(`${CORPUS}/versions/${versionId}/exports`, { method: 'POST', body: JSON.stringify(body || {}) })
export const corpusExport = (id) => request(`${CORPUS}/exports/${id}`)

export const generateCorpusManifest = (versionId) => request(`${CORPUS}/versions/${versionId}/manifest`, { method: 'POST' })
export const corpusManifest = (versionId) => request(`${CORPUS}/versions/${versionId}/manifest`)

export const compareCorpusVersions = (body) => request(`${CORPUS}/compare`, { method: 'POST', body: JSON.stringify(body) })

// --- Phase 20 -----------------------------------------------------

export const setCorpusSourceReviewMetadata = (id, body) => request(`${CORPUS}/sources/${id}/review-metadata`, { method: 'PATCH', body: JSON.stringify(body) })
export const advanceCorpusSourceProductionLifecycle = (id, body) => request(`${CORPUS}/sources/${id}/production-lifecycle`, { method: 'POST', body: JSON.stringify(body) })

export const corpusNormalizationProfiles = () => request(`${CORPUS}/normalization-profiles`)
export const createCorpusNormalizationProfile = (body) => request(`${CORPUS}/normalization-profiles`, { method: 'POST', body: JSON.stringify(body) })
export const activateCorpusNormalizationProfile = (id) => request(`${CORPUS}/normalization-profiles/${id}/activate`, { method: 'POST' })
export const archiveCorpusNormalizationProfile = (id) => request(`${CORPUS}/normalization-profiles/${id}/archive`, { method: 'POST' })

export const corpusSegmentationProfiles = () => request(`${CORPUS}/segmentation-profiles`)
export const createCorpusSegmentationProfile = (body) => request(`${CORPUS}/segmentation-profiles`, { method: 'POST', body: JSON.stringify(body) })
export const activateCorpusSegmentationProfile = (id) => request(`${CORPUS}/segmentation-profiles/${id}/activate`, { method: 'POST' })
export const archiveCorpusSegmentationProfile = (id) => request(`${CORPUS}/segmentation-profiles/${id}/archive`, { method: 'POST' })

export const inspectCorpusSourceFile = (sourceId, body) => request(`${CORPUS}/sources/${sourceId}/inspect-file`, { method: 'POST', body: JSON.stringify(body) })
export const corpusIngestionJobs = (sourceId) => request(`${CORPUS}/sources/${sourceId}/ingestion-jobs`)
export const createCorpusIngestionJob = (sourceId, body) => request(`${CORPUS}/sources/${sourceId}/ingestion-jobs`, { method: 'POST', body: JSON.stringify(body) })
export const corpusIngestionJob = (id) => request(`${CORPUS}/ingestion-jobs/${id}`)
export const runCorpusIngestionJob = (id, body) => request(`${CORPUS}/ingestion-jobs/${id}/run`, { method: 'POST', body: JSON.stringify(body) })
export const cancelCorpusIngestionJob = (id) => request(`${CORPUS}/ingestion-jobs/${id}/cancel`, { method: 'POST' })
export const retryCorpusIngestionJob = (id) => request(`${CORPUS}/ingestion-jobs/${id}/retry`, { method: 'POST' })

export const corpusSegmentAssessments = (id) => request(`${CORPUS}/segments/${id}/assessments`)
export const correctCorpusSegmentLabel = (id, body) => request(`${CORPUS}/segments/${id}/correct-label`, { method: 'POST', body: JSON.stringify(body) })

export const corpusProtectedContentSets = () => request(`${CORPUS}/protected-content-sets`)
export const createCorpusProtectedContentSet = (body) => request(`${CORPUS}/protected-content-sets`, { method: 'POST', body: JSON.stringify(body) })
export const corpusProtectedContentSet = (id) => request(`${CORPUS}/protected-content-sets/${id}`)
export const activateCorpusProtectedContentSet = (id) => request(`${CORPUS}/protected-content-sets/${id}/activate`, { method: 'POST' })
export const addCorpusProtectedContentEntries = (id, body) => request(`${CORPUS}/protected-content-sets/${id}/entries`, { method: 'POST', body: JSON.stringify(body) })

export const previewCorpusBalance = (collectionId, body) => request(`${CORPUS}/collections/${collectionId}/preview-balance`, { method: 'POST', body: JSON.stringify(body) })
export const previewCorpusPartitions = (collectionId, body) => request(`${CORPUS}/collections/${collectionId}/preview-partitions`, { method: 'POST', body: JSON.stringify(body || {}) })

export const createCorpusTokenizerAnalysis = (body) => request(`${CORPUS}/tokenizer-analyses`, { method: 'POST', body: JSON.stringify(body) })
export const corpusTokenizerAnalysis = (id) => request(`${CORPUS}/tokenizer-analyses/${id}`)

export const createCorpusReadinessEvaluation = (body) => request(`${CORPUS}/readiness-evaluations`, { method: 'POST', body: JSON.stringify(body) })
export const corpusReadinessEvaluation = (id) => request(`${CORPUS}/readiness-evaluations/${id}`)

export const corpusReleases = () => request(`${CORPUS}/releases`)
export const createCorpusRelease = (body) => request(`${CORPUS}/releases`, { method: 'POST', body: JSON.stringify(body) })
export const corpusRelease = (id) => request(`${CORPUS}/releases/${id}`)
export const validateCorpusRelease = (id) => request(`${CORPUS}/releases/${id}/validate`, { method: 'POST' })
export const approveCorpusRelease = (id, body) => request(`${CORPUS}/releases/${id}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const finalizeCorpusRelease = (id) => request(`${CORPUS}/releases/${id}/finalize`, { method: 'POST' })
export const exportCorpusRelease = (id, body) => request(`${CORPUS}/releases/${id}/export`, { method: 'POST', body: JSON.stringify(body) })
export const retireCorpusRelease = (id) => request(`${CORPUS}/releases/${id}/retire`, { method: 'POST' })
export const corpusComparison = (id) => request(`${CORPUS}/comparisons/${id}`)

// --- Phase 21A -----------------------------------------------------

const PR = '/api/admin/pretraining-readiness'

export const tokenizerCorpusBuilds = () => request(`${PR}/tokenizer-corpus-builds`)
export const createTokenizerCorpusBuild = (body) => request(`${PR}/tokenizer-corpus-builds`, { method: 'POST', body: JSON.stringify(body) })
export const tokenizerCorpusBuild = (id) => request(`${PR}/tokenizer-corpus-builds/${id}`)

export const createTokenizerCandidateComparison = (body) => request(`${PR}/tokenizer-candidate-comparisons`, { method: 'POST', body: JSON.stringify(body) })
export const tokenizerCandidateComparison = (id) => request(`${PR}/tokenizer-candidate-comparisons/${id}`)
export const approveTokenizerCandidate = (id, body) => request(`${PR}/tokenizer-candidate-comparisons/${id}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const activateTokenizerVersion = (id) => request(`${PR}/tokenizer-versions/${id}/activate`, { method: 'POST' })

export const resourceEstimates = () => request(`${PR}/resource-estimates`)
export const createResourceEstimate = (body) => request(`${PR}/resource-estimates`, { method: 'POST', body: JSON.stringify(body) })
export const resourceEstimate = (id) => request(`${PR}/resource-estimates/${id}`)

export const datasetSnapshots = () => request(`${PR}/dataset-snapshots`)
export const createDatasetSnapshot = (body) => request(`${PR}/dataset-snapshots`, { method: 'POST', body: JSON.stringify(body) })
export const datasetSnapshot = (id) => request(`${PR}/dataset-snapshots/${id}`)

export const validateTrainingConfig = (body) => request(`${PR}/training-config/validate`, { method: 'POST', body: JSON.stringify(body) })
export const smokeRuns = () => request(`${PR}/smoke-runs`)
export const createSmokeRun = (body) => request(`${PR}/smoke-runs`, { method: 'POST', body: JSON.stringify(body) })
export const smokeRun = (id) => request(`${PR}/smoke-runs/${id}`)

export const baseModelReadinessEvaluations = () => request(`${PR}/readiness-evaluations`)
export const createBaseModelReadinessEvaluation = (body) => request(`${PR}/readiness-evaluations`, { method: 'POST', body: JSON.stringify(body) })
export const baseModelReadinessEvaluation = (id) => request(`${PR}/readiness-evaluations/${id}`)

const AA = '/api/admin/assistant'
export const assistantOverview = () => request(`${AA}/overview`)
export const assistantActions = () => request(`${AA}/actions`)
export const assistantProposals = (status) => request(`${AA}/proposals${status ? `?status=${status}` : ''}`)
export const assistantProposal = (id) => request(`${AA}/proposals/${id}`)
export const createAssistantProposal = (body) => request(`${AA}/proposals`, { method: 'POST', body: JSON.stringify(body) })
export const reviewAssistantProposal = (id, body) => request(`${AA}/proposals/${id}/review`, { method: 'POST', body: JSON.stringify(body) })
export const executeAssistantProposal = (id) => request(`${AA}/proposals/${id}/execute`, { method: 'POST' })
export const cancelAssistantProposal = (id, body = {}) => request(`${AA}/proposals/${id}/cancel`, { method: 'POST', body: JSON.stringify(body) })

// --- Phase 8: Floating Context-Aware Admin Assistant ----------------------

export const assistantPages = () => request(`${AA}/pages`)
export const assistantHealth = () => request(`${AA}/health`)
export const sendAssistantChatMessage = (body) => request(`${AA}/chat`, { method: 'POST', body: JSON.stringify(body) })
export const submitAssistantFeedback = (body) => request(`${AA}/feedback`, { method: 'POST', body: JSON.stringify(body) })

// -- MB-31F/MB-34A: widget->Mini Brain backend switch (reversible; see AdminAssistantWidget.jsx) --
// ChatRequest (backend/models/mini_brain_llm_runtime.py) accepts only
// { session_id, message } -- page_id/mode are widget-local UI state, not
// part of this backend's request schema.
// MB-48: local CPU model generation can legitimately take 60-130+
// seconds; 120s gives real headroom without leaving a hung request
// spinning forever with no feedback.
export const sendMiniBrainWidgetMessage = (sessionId, message) => request('/api/admin/mini-brain/llm-runtime/chat', { method: 'POST', body: JSON.stringify({ session_id: sessionId || null, message }), timeoutMs: 120_000 })

// --- Phase 10A: Admin Assistant response-language preference --------------

export const assistantLanguagePreference = () => request(`${AA}/preferences`)
export const setAssistantLanguagePreference = (response_language) => request(`${AA}/preferences`, { method: 'PATCH', body: JSON.stringify({ response_language }) })
export const previewAssistantLanguage = (body) => request(`${AA}/preferences/preview`, { method: 'POST', body: JSON.stringify(body) })

const DS = '/api/admin/data-sources'
export const dataSources = (query = '') => request(`${DS}${query}`)
export const createDataSource = (body) => request(DS, { method: 'POST', body: JSON.stringify(body) })
export const dataSource = (id) => request(`${DS}/${id}`)
export const updateDataSource = (id, body) => request(`${DS}/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const archiveDataSource = (id) => request(`${DS}/${id}/archive`, { method: 'POST' })
export const restoreDataSource = (id) => request(`${DS}/${id}/restore`, { method: 'POST' })

export const dataSourceRights = (id) => request(`${DS}/${id}/rights`)
export const upsertDataSourceRights = (id, body) => request(`${DS}/${id}/rights`, { method: 'PUT', body: JSON.stringify(body) })
export const submitDataSourceForReview = (id) => request(`${DS}/${id}/submit-review`, { method: 'POST' })
export const verifyDataSource = (id, body) => request(`${DS}/${id}/verify`, { method: 'POST', body: JSON.stringify(body) })
export const restrictDataSource = (id, body) => request(`${DS}/${id}/restrict`, { method: 'POST', body: JSON.stringify(body) })
export const rejectDataSource = (id, body) => request(`${DS}/${id}/reject`, { method: 'POST', body: JSON.stringify(body) })

export const dataSourceLinks = (id) => request(`${DS}/${id}/links`)
export const createDataSourceLink = (id, body) => request(`${DS}/${id}/links`, { method: 'POST', body: JSON.stringify(body) })
export const deleteDataSourceLink = (id, linkId) => request(`${DS}/${id}/links/${linkId}`, { method: 'DELETE' })

export const checkDataSourceUsage = (id, targetUse) => request(`${DS}/${id}/usage-check`, { method: 'POST', body: JSON.stringify({ target_use: targetUse }) })
export const dataSourceUsageSummary = (id) => request(`${DS}/${id}/usage-summary`)
export const dataSourceHistory = (id) => request(`${DS}/${id}/history`)
export const dataSourceVerificationEvents = (id) => request(`${DS}/${id}/verification-events`)

// Preflight checks exposed by the existing dataset/RAG systems (Phase 2
// integration, Step 9) -- neither changes its own endpoint's behaviour.
export const datasetVersionRightsSummary = (versionId, targetUse = 'training') => request(`/api/admin/datasets/versions/${versionId}/rights-summary?target_use=${targetUse}`)

const MD = '/api/admin/manual-data'
export const manualDataRecords = (query = '') => request(`${MD}${query}`)
export const manualDataSummary = () => request(`${MD}/summary`)
export const createManualDataRecord = (body) => request(MD, { method: 'POST', body: JSON.stringify(body) })
export const manualDataRecord = (id) => request(`${MD}/${id}`)
export const updateManualDataRecord = (id, body) => request(`${MD}/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const archiveManualDataRecord = (id) => request(`${MD}/${id}/archive`, { method: 'POST' })
export const restoreManualDataRecord = (id) => request(`${MD}/${id}/restore`, { method: 'POST' })

export const manualDataRevisions = (id) => request(`${MD}/${id}/revisions`)
export const createManualDataRevision = (id, body) => request(`${MD}/${id}/revisions`, { method: 'POST', body: JSON.stringify(body) })

export const submitManualDataForReview = (id) => request(`${MD}/${id}/submit-review`, { method: 'POST' })
export const requestManualDataCorrection = (id, notes = '') => request(`${MD}/${id}/request-correction?notes=${encodeURIComponent(notes)}`, { method: 'POST' })
export const requestManualDataSourceVerification = (id, notes = '') => request(`${MD}/${id}/request-source-verification?notes=${encodeURIComponent(notes)}`, { method: 'POST' })
export const requestManualDataDomainReview = (id, notes = '') => request(`${MD}/${id}/request-domain-review?notes=${encodeURIComponent(notes)}`, { method: 'POST' })
export const submitManualDataReview = (id, body) => request(`${MD}/${id}/review`, { method: 'POST', body: JSON.stringify(body) })
export const manualDataReviews = (id) => request(`${MD}/${id}/reviews`)
export const submitManualDataVerification = (id, body) => request(`${MD}/${id}/verify`, { method: 'POST', body: JSON.stringify(body) })
export const manualDataVerifications = (id) => request(`${MD}/${id}/verifications`)
export const approveManualDataRecord = (id, body) => request(`${MD}/${id}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const rejectManualDataRecord = (id, body) => request(`${MD}/${id}/reject`, { method: 'POST', body: JSON.stringify(body) })

export const manualDataQualityCheck = (id) => request(`${MD}/${id}/quality-check`, { method: 'POST' })
export const manualDataDuplicateCheck = (id) => request(`${MD}/${id}/duplicate-check`, { method: 'POST' })

export const manualDataUsageCheck = (id, targetUse) => request(`${MD}/${id}/usage-check`, { method: 'POST', body: JSON.stringify({ target_use: targetUse }) })
export const manualDataUsageSummary = (id) => request(`${MD}/${id}/usage-summary`)
export const manualDataHistory = (id) => request(`${MD}/${id}/history`)
export const createManualDataDatasetCandidate = (id, body = {}) => request(`${MD}/${id}/create-dataset-candidate`, { method: 'POST', body: JSON.stringify(body) })

// --- Phase 5: Semantic Chunk & Structured Record Studio -----------------

const SC = '/api/admin/semantic-chunks'
const SR = '/api/admin/structured-records'

export const generateChunks = (documentId) => request(`${SC}/document/${documentId}/generate`, { method: 'POST' })
export const documentChunks = (documentId, query = '') => request(`${SC}/document/${documentId}${query}`)
export const reorderChunks = (documentId, chunkPublicIds) => request(`${SC}/document/${documentId}/reorder`, { method: 'POST', body: JSON.stringify({ chunk_public_ids: chunkPublicIds }) })
export const chunkCoverageReport = (documentId) => request(`${SC}/document/${documentId}/coverage`)
export const createManualChunk = (documentId, body) => request(`${SC}/document/${documentId}/manual`, { method: 'POST', body: JSON.stringify(body) })

export const chunkDetail = (chunkId) => request(`${SC}/${chunkId}`)
export const chunkHistory = (chunkId) => request(`${SC}/${chunkId}/history`)
export const chunkClassificationSuggestions = (chunkId) => request(`${SC}/${chunkId}/classification-suggestions`)
export const editChunkText = (chunkId, body) => request(`${SC}/${chunkId}`, { method: 'PATCH', body: JSON.stringify(body) })
export const splitChunk = (chunkId, splitAt) => request(`${SC}/${chunkId}/split`, { method: 'POST', body: JSON.stringify({ split_at: splitAt }) })
export const mergeChunk = (chunkId, otherChunkPublicId) => request(`${SC}/${chunkId}/merge`, { method: 'POST', body: JSON.stringify({ other_chunk_public_id: otherChunkPublicId }) })
export const moveChunkBoundary = (chunkId, body) => request(`${SC}/${chunkId}/move-boundary`, { method: 'POST', body: JSON.stringify(body) })
export const classifyChunk = (chunkId, chunkType, notes = '') => request(`${SC}/${chunkId}/classify`, { method: 'POST', body: JSON.stringify({ chunk_type: chunkType, notes }) })
export const assignChunkParent = (chunkId, parentChunkPublicId) => request(`${SC}/${chunkId}/assign-parent`, { method: 'POST', body: JSON.stringify({ parent_chunk_public_id: parentChunkPublicId }) })
export const archiveChunk = (chunkId) => request(`${SC}/${chunkId}/archive`, { method: 'POST' })
export const restoreChunk = (chunkId) => request(`${SC}/${chunkId}/restore`, { method: 'POST' })

export const submitChunkForReview = (chunkId, notes = '') => request(`${SC}/${chunkId}/submit-review`, { method: 'POST', body: JSON.stringify({ notes }) })
export const approveChunk = (chunkId, notes = '') => request(`${SC}/${chunkId}/approve`, { method: 'POST', body: JSON.stringify({ notes }) })
export const rejectChunk = (chunkId, notes = '') => request(`${SC}/${chunkId}/reject`, { method: 'POST', body: JSON.stringify({ notes }) })
export const excludeChunk = (chunkId, notes = '') => request(`${SC}/${chunkId}/exclude`, { method: 'POST', body: JSON.stringify({ notes }) })
export const reopenChunk = (chunkId, notes = '') => request(`${SC}/${chunkId}/reopen`, { method: 'POST', body: JSON.stringify({ notes }) })
export const requestChunkBoundaryCorrection = (chunkId, notes = '') => request(`${SC}/${chunkId}/request-boundary-correction`, { method: 'POST', body: JSON.stringify({ notes }) })
export const requestChunkClassificationCorrection = (chunkId, notes = '') => request(`${SC}/${chunkId}/request-classification-correction`, { method: 'POST', body: JSON.stringify({ notes }) })
export const chunkReviewHistory = (chunkId) => request(`${SC}/${chunkId}/review-history`)

export const chunkQualityCheck = (chunkId) => request(`${SC}/${chunkId}/quality-check`, { method: 'POST' })
export const chunkDuplicateCheck = (chunkId) => request(`${SC}/${chunkId}/duplicate-check`, { method: 'POST' })

export const structuredRecords = (query = '') => request(`${SR}${query}`)
export const createStructuredRecordFromChunks = (body) => request(`${SR}/from-chunks`, { method: 'POST', body: JSON.stringify(body) })
export const structuredRecordDetail = (id) => request(`${SR}/${id}`)
export const structuredRecordHistory = (id) => request(`${SR}/${id}/history`)
export const reviseStructuredRecord = (id, body) => request(`${SR}/${id}/revision`, { method: 'POST', body: JSON.stringify(body) })
export const submitStructuredRecordForReview = (id) => request(`${SR}/${id}/submit-review`, { method: 'POST' })
export const approveStructuredRecord = (id) => request(`${SR}/${id}/approve`, { method: 'POST' })
export const rejectStructuredRecord = (id) => request(`${SR}/${id}/reject`, { method: 'POST' })
export const archiveStructuredRecord = (id) => request(`${SR}/${id}/archive`, { method: 'POST' })
export const structuredRecordUsageCheck = (id, targetUse) => request(`${SR}/${id}/usage-check`, { method: 'POST', body: JSON.stringify({ target_use: targetUse }) })
export const structuredRecordConflictCheck = (id) => request(`${SR}/${id}/conflict-check`, { method: 'POST' })
export const exportStructuredRecordToDataset = (id) => request(`${SR}/${id}/export-dataset`, { method: 'POST' })
export const createStructuredRecordRagCandidate = (id) => request(`${SR}/${id}/create-rag-candidate`, { method: 'POST' })

// --- Phase 6: Quality, Duplicate, Conflict & Approval Integration -------

const GOV = '/api/admin/data-governance'

export const governanceQueue = (query = '') => request(`${GOV}/queue${query}`)
export const openGovernanceReviewItem = (body) => request(`${GOV}/review/open`, { method: 'POST', body: JSON.stringify(body) })
export const governanceReviewItem = (id) => request(`${GOV}/review/${id}`)
export const governanceReviewItemHistory = (id) => request(`${GOV}/review/${id}/history`)
export const assignGovernanceReviewItem = (id, assigneeAdminPublicId) => request(`${GOV}/review/${id}/assign`, { method: 'POST', body: JSON.stringify({ assignee_admin_public_id: assigneeAdminPublicId }) })
export const setGovernanceReviewItemStatus = (id, status, notes = '') => request(`${GOV}/review/${id}/status`, { method: 'POST', body: JSON.stringify({ status, notes }) })
export const addGovernanceReviewItemNote = (id, note) => request(`${GOV}/review/${id}/note`, { method: 'POST', body: JSON.stringify({ note }) })

export const assessGovernanceQuality = (entityType, entityPublicId) => request(`${GOV}/quality/${entityType}/${entityPublicId}/assess`, { method: 'POST' })

export const governanceDuplicateGroups = (query = '') => request(`${GOV}/duplicates${query}`)
export const syncManualDataDuplicate = (recordPublicId) => request(`${GOV}/duplicates/manual-data/${recordPublicId}/sync`, { method: 'POST' })
export const syncChunkDuplicate = (chunkPublicId) => request(`${GOV}/duplicates/chunk/${chunkPublicId}/sync`, { method: 'POST' })
export const resolveGovernanceDuplicateGroup = (groupId, body) => request(`${GOV}/duplicates/${groupId}/resolve`, { method: 'POST', body: JSON.stringify(body) })

export const governanceConflictGroups = (query = '') => request(`${GOV}/conflicts${query}`)
export const syncStructuredRecordConflict = (candidatePublicId) => request(`${GOV}/conflicts/structured-record/${candidatePublicId}/sync`, { method: 'POST' })
export const resolveGovernanceConflictGroup = (groupId, body) => request(`${GOV}/conflicts/${groupId}/resolve`, { method: 'POST', body: JSON.stringify(body) })

export const governanceApprovalStatus = (entityType, entityPublicId) => request(`${GOV}/approvals/${entityType}/${entityPublicId}`)
export const evaluateGovernanceApproval = (entityType, entityPublicId, targetUse) => request(`${GOV}/approvals/${entityType}/${entityPublicId}/${targetUse}/evaluate`, { method: 'POST' })
export const overrideGovernanceApproval = (entityType, entityPublicId, targetUse, body) => request(`${GOV}/approvals/${entityType}/${entityPublicId}/${targetUse}/override`, { method: 'POST', body: JSON.stringify(body) })

export const governanceExportReadiness = (entityType, entityPublicId, targetUse) => request(`${GOV}/export-readiness/${entityType}/${entityPublicId}/${targetUse}`)

// --- Phase 7: Dataset Version, RAG & Training Pipeline Integration -------

const GB = '/api/admin/governed-builds'
const LINEAGE = '/api/admin/data-lineage'

export const governedBuildSummary = () => request(`${GB}/summary`)
export const governedBuilds = (query = '') => request(`${GB}${query}`)
export const createGovernedBuild = (body) => request(GB, { method: 'POST', body: JSON.stringify(body) })
export const governedBuild = (id) => request(`${GB}/${id}`)
export const updateGovernedBuild = (id, body) => request(`${GB}/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const previewGovernedBuild = (id) => request(`${GB}/${id}/preview`, { method: 'POST' })
export const preflightGovernedBuild = (id) => request(`${GB}/${id}/preflight`, { method: 'POST' })
export const confirmGovernedBuild = (id) => request(`${GB}/${id}/confirm`, { method: 'POST' })
export const executeGovernedBuild = (id) => request(`${GB}/${id}/execute`, { method: 'POST' })
export const cancelGovernedBuild = (id) => request(`${GB}/${id}/cancel`, { method: 'POST' })
export const updateGovernedBuildSelection = (id, itemPublicId, included) => request(`${GB}/${id}/selection`, { method: 'POST', body: JSON.stringify({ item_public_id: itemPublicId, included }) })
export const governedBuildItems = (id) => request(`${GB}/${id}/items`)
export const governedBuildBlockedItems = (id) => request(`${GB}/${id}/blocked-items`)
export const governedBuildManifest = (id) => request(`${GB}/${id}/manifest`)
export const generateGovernedBuildManifest = (id) => request(`${GB}/${id}/manifest`, { method: 'POST' })
export const governedBuildHistory = (id) => request(`${GB}/${id}/history`)

export const governedDatasetVersionHandoff = (id) => request(`${GB}/${id}/dataset-version`, { method: 'POST' })
export const governedRagHandoff = (id, body) => request(`${GB}/${id}/rag-handoff`, { method: 'POST', body: JSON.stringify(body) })
export const governedTokenizerHandoff = (id) => request(`${GB}/${id}/tokenizer-handoff`, { method: 'POST' })
export const governedPretrainingHandoff = (id) => request(`${GB}/${id}/pretraining-handoff`, { method: 'POST' })
export const governedSftHandoff = (id) => request(`${GB}/${id}/sft-handoff`, { method: 'POST' })
export const governedEvaluationHandoff = (id) => request(`${GB}/${id}/evaluation-handoff`, { method: 'POST' })
export const governedPublicExportPreflight = (id) => request(`${GB}/${id}/public-export-preflight`, { method: 'POST' })
export const governedCommercialPreflight = (id) => request(`${GB}/${id}/commercial-preflight`, { method: 'POST' })

export const lineageForEntity = (entityType, entityId) => request(`${LINEAGE}/entity/${entityType}/${entityId}`)
export const lineageUpstreamOf = (entityType, entityId) => request(`${LINEAGE}/entity/${entityType}/${entityId}/upstream`)
export const lineageDownstreamOf = (entityType, entityId) => request(`${LINEAGE}/entity/${entityType}/${entityId}/downstream`)
export const lineageForSource = (sourcePublicId) => request(`${LINEAGE}/source/${sourcePublicId}`)
export const lineageForModelRelease = (releasePublicId) => request(`${LINEAGE}/model-release/${releasePublicId}`)

// --- Phase 9: External Data Provider Registry -----------------------------

const EDP = '/api/admin/external-data-providers'

export const externalDataProviders = (query = '') => request(`${EDP}${query}`)
export const registerExternalDataProvider = (body) => request(EDP, { method: 'POST', body: JSON.stringify(body) })
export const externalDataProvider = (id) => request(`${EDP}/${id}`)
export const updateExternalDataProvider = (id, body) => request(`${EDP}/${id}`, { method: 'PATCH', body: JSON.stringify(body) })

export const verifyExternalDataProvider = (id) => request(`${EDP}/${id}/verify`, { method: 'POST' })
export const setProviderTrustStatus = (id, body) => request(`${EDP}/${id}/trust-status`, { method: 'POST', body: JSON.stringify(body) })
export const testProviderConnection = (id, body = {}) => request(`${EDP}/${id}/test-connection`, { method: 'POST', body: JSON.stringify(body) })
export const providerConnectionTests = (id) => request(`${EDP}/${id}/connection-tests`)

export const enableExternalDataProvider = (id) => request(`${EDP}/${id}/enable`, { method: 'POST' })
export const disableExternalDataProvider = (id) => request(`${EDP}/${id}/disable`, { method: 'POST' })
export const restrictExternalDataProvider = (id) => request(`${EDP}/${id}/restrict`, { method: 'POST' })
export const blockExternalDataProvider = (id) => request(`${EDP}/${id}/block`, { method: 'POST' })
export const archiveExternalDataProvider = (id) => request(`${EDP}/${id}/archive`, { method: 'POST' })

export const providerDomains = (id) => request(`${EDP}/${id}/domains`)
export const addProviderDomain = (id, body) => request(`${EDP}/${id}/domains`, { method: 'POST', body: JSON.stringify(body) })
export const verifyProviderDomain = (id, domainId, body) => request(`${EDP}/${id}/domains/${domainId}/verify`, { method: 'POST', body: JSON.stringify(body) })

export const providerCapabilities = (id) => request(`${EDP}/${id}/capabilities`)
export const setProviderCapabilities = (id, body) => request(`${EDP}/${id}/capabilities`, { method: 'PUT', body: JSON.stringify(body) })

export const providerCredentialStatus = (id) => request(`${EDP}/${id}/credential-status`)
export const configureProviderCredential = (id, body) => request(`${EDP}/${id}/credentials`, { method: 'POST', body: JSON.stringify(body) })
export const revokeProviderCredential = (id, body) => request(`${EDP}/${id}/credentials/revoke`, { method: 'POST', body: JSON.stringify(body) })

export const providerHistory = (id) => request(`${EDP}/${id}/history`)

// --- Phase 10: Live Dataset Discovery, Normalization & Comparison --------

const DD = '/api/admin/dataset-discovery'

export const discoverySessions = (query = '') => request(`${DD}/sessions${query}`)
export const createDiscoverySession = (body) => request(`${DD}/sessions`, { method: 'POST', body: JSON.stringify(body) })
export const discoverySession = (id) => request(`${DD}/sessions/${id}`)
export const cancelDiscoverySession = (id) => request(`${DD}/sessions/${id}/cancel`, { method: 'POST' })

export const discoveryRequirements = (id) => request(`${DD}/sessions/${id}/requirements`)
export const setDiscoveryRequirements = (id, body) => request(`${DD}/sessions/${id}/requirements`, { method: 'PUT', body: JSON.stringify(body) })

export const runDiscoverySearch = (id) => request(`${DD}/sessions/${id}/search`, { method: 'POST' })

export const discoveryCandidates = (id, includeExcluded = true) => request(`${DD}/sessions/${id}/candidates?include_excluded=${includeExcluded}`)
export const addManualDiscoveryCandidate = (id, body) => request(`${DD}/sessions/${id}/candidates`, { method: 'POST', body: JSON.stringify(body) })
export const discoveryCandidate = (candidateId) => request(`${DD}/candidates/${candidateId}`)
export const excludeDiscoveryCandidate = (candidateId) => request(`${DD}/candidates/${candidateId}/exclude`, { method: 'POST' })
export const restoreDiscoveryCandidate = (candidateId) => request(`${DD}/candidates/${candidateId}/restore`, { method: 'POST' })

export const discoveryProviderRuns = (id) => request(`${DD}/sessions/${id}/provider-runs`)
export const discoveryEvents = (id) => request(`${DD}/sessions/${id}/events`)

export const discoveryComparisons = (id) => request(`${DD}/sessions/${id}/comparisons`)
export const createDiscoveryComparison = (id, body) => request(`${DD}/sessions/${id}/comparisons`, { method: 'POST', body: JSON.stringify(body) })

// --- Phase 11: Licence Evidence, Terms Snapshot & Dataset Verification ----

const DV = '/api/admin/dataset-verification'

export const verificationOverview = () => request(`${DV}/overview`)
export const verificationCases = (query = '') => request(`${DV}/cases${query}`)
export const createVerificationCase = (body) => request(`${DV}/cases`, { method: 'POST', body: JSON.stringify(body) })
export const verificationCase = (id) => request(`${DV}/cases/${id}`)
export const startVerificationCase = (id) => request(`${DV}/cases/${id}/start`, { method: 'POST' })
export const cancelVerificationCase = (id) => request(`${DV}/cases/${id}/cancel`, { method: 'POST' })

export const verificationEvidence = (id, query = '') => request(`${DV}/cases/${id}/evidence${query}`)
export const collectVerificationEvidence = (id, body) => request(`${DV}/cases/${id}/evidence/collect`, { method: 'POST', body: JSON.stringify(body) })
export const addManualVerificationEvidence = (id, body) => request(`${DV}/cases/${id}/evidence/manual`, { method: 'POST', body: JSON.stringify(body) })
export const refreshVerificationEvidence = (id, evidenceId) => request(`${DV}/cases/${id}/evidence/${evidenceId}/refresh`, { method: 'POST' })

export const verificationIdentity = (id) => request(`${DV}/cases/${id}/identity`)
export const assessVerificationIdentity = (id) => request(`${DV}/cases/${id}/identity/assess`, { method: 'POST' })
export const recordManualIdentitySignal = (id, body) => request(`${DV}/cases/${id}/identity/manual-signal`, { method: 'POST', body: JSON.stringify(body) })

export const assessVerificationLicence = (id) => request(`${DV}/cases/${id}/licence/assess`, { method: 'POST' })
export const verificationTerms = (id) => request(`${DV}/cases/${id}/terms`)

export const verificationPermissions = (id) => request(`${DV}/cases/${id}/permissions`)
export const verificationPermissionReviews = (id) => request(`${DV}/cases/${id}/permissions/reviews`)
export const assessVerificationPermissions = (id) => request(`${DV}/cases/${id}/permissions/assess`, { method: 'POST' })
export const assessVerificationCommercialUse = (id, body) => request(`${DV}/cases/${id}/permissions/commercial-use`, { method: 'POST', body: JSON.stringify(body) })
export const reviewVerificationPermission = (id, permissionType, body) => request(`${DV}/cases/${id}/permissions/${permissionType}/review`, { method: 'POST', body: JSON.stringify(body) })

export const verificationUpstreams = (id) => request(`${DV}/cases/${id}/upstreams`)
export const addVerificationUpstream = (id, body) => request(`${DV}/cases/${id}/upstreams`, { method: 'POST', body: JSON.stringify(body) })
export const verifyVerificationUpstream = (id, upstreamId, body) => request(`${DV}/cases/${id}/upstreams/${upstreamId}/verify`, { method: 'POST', body: JSON.stringify(body) })

export const verificationConflicts = (id) => request(`${DV}/cases/${id}/conflicts`)
export const detectVerificationConflicts = (id) => request(`${DV}/cases/${id}/conflicts/detect`, { method: 'POST' })
export const resolveVerificationConflict = (id, conflictId, body) => request(`${DV}/cases/${id}/conflicts/${conflictId}/resolve`, { method: 'POST', body: JSON.stringify(body) })

export const finalizeVerificationCase = (id) => request(`${DV}/cases/${id}/finalize`, { method: 'POST' })
export const verificationReport = (id) => request(`${DV}/cases/${id}/report`)
export const reverifyVerificationCase = (id) => request(`${DV}/cases/${id}/reverify`, { method: 'POST' })

export const verificationWithdrawalNotices = (id) => request(`${DV}/cases/${id}/withdrawal-notices`)
export const recordVerificationWithdrawalNotice = (id, body) => request(`${DV}/cases/${id}/withdrawal-notices`, { method: 'POST', body: JSON.stringify(body) })

export const verificationEvents = (id) => request(`${DV}/cases/${id}/events`)

export const verificationExistingSource = (id) => request(`${DV}/cases/${id}/source-rights/existing-source`)
export const draftVerificationSourceRightsProposal = (id) => request(`${DV}/cases/${id}/source-rights/draft-proposal`, { method: 'POST' })

// --- Phase 12: Approved Sample Import, Quarantine, File Safety, PII & Quality ----

const SI = '/api/admin/dataset-sample-imports'

export const sampleImportOverview = () => request(`${SI}/overview`)
export const sampleImports = (query = '') => request(`${SI}/sample-imports${query}`)
export const createSampleImport = (body) => request(`${SI}/sample-imports`, { method: 'POST', body: JSON.stringify(body) })
export const sampleImport = (id) => request(`${SI}/sample-imports/${id}`)
export const cancelSampleImport = (id) => request(`${SI}/sample-imports/${id}/cancel`, { method: 'POST' })

export const requestSampleImportApproval = (id, body) => request(`${SI}/sample-imports/${id}/request-approval`, { method: 'POST', body: JSON.stringify(body) })
export const approveSampleImport = (id, body) => request(`${SI}/sample-imports/${id}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const rejectSampleImportApproval = (id, body) => request(`${SI}/sample-imports/${id}/reject-approval`, { method: 'POST', body: JSON.stringify(body) })

export const downloadSampleFile = (id, body) => request(`${SI}/sample-imports/${id}/download`, { method: 'POST', body: JSON.stringify(body) })
export const sampleFiles = (id) => request(`${SI}/sample-imports/${id}/files`)
export const sampleFile = (id, fileId, query = '') => request(`${SI}/sample-imports/${id}/files/${fileId}${query}`)

export const validateSampleFiles = (id) => request(`${SI}/sample-imports/${id}/validate-files`, { method: 'POST' })
export const extractSampleArchives = (id) => request(`${SI}/sample-imports/${id}/extract`, { method: 'POST' })
export const scanSample = (id) => request(`${SI}/sample-imports/${id}/scan`, { method: 'POST' })
export const parseSample = (id) => request(`${SI}/sample-imports/${id}/parse`, { method: 'POST' })

export const sampleRecords = (id, query = '') => request(`${SI}/sample-imports/${id}/records${query}`)
export const sampleRecord = (id, recordId) => request(`${SI}/sample-imports/${id}/records/${recordId}`)
export const reviewSampleRecord = (id, recordId, body) => request(`${SI}/sample-imports/${id}/records/${recordId}/review`, { method: 'POST', body: JSON.stringify(body) })
export const createSampleRecordRevision = (id, recordId, body) => request(`${SI}/sample-imports/${id}/records/${recordId}/create-revision`, { method: 'POST', body: JSON.stringify(body) })

export const sampleIssues = (id, query = '') => request(`${SI}/sample-imports/${id}/issues${query}`)
export const reviewSampleIssue = (id, issueId, body) => request(`${SI}/sample-imports/${id}/issues/${issueId}/review`, { method: 'POST', body: JSON.stringify(body) })

export const runSampleQualityChecks = (id) => request(`${SI}/sample-imports/${id}/run-quality-checks`, { method: 'POST' })
export const runSampleDuplicateChecks = (id) => request(`${SI}/sample-imports/${id}/run-duplicate-checks`, { method: 'POST' })
export const runSampleContaminationChecks = (id) => request(`${SI}/sample-imports/${id}/run-contamination-checks`, { method: 'POST' })

export const finalizeSampleImport = (id) => request(`${SI}/sample-imports/${id}/finalize`, { method: 'POST' })
export const sampleImportReport = (id) => request(`${SI}/sample-imports/${id}/report`)

export const requestSampleDeletion = (id, body) => request(`${SI}/sample-imports/${id}/request-deletion`, { method: 'POST', body: JSON.stringify(body) })
export const executeSampleDeletion = (id) => request(`${SI}/sample-imports/${id}/execute-deletion`, { method: 'POST' })

export const sampleImportEvents = (id) => request(`${SI}/sample-imports/${id}/events`)

const RS = '/api/admin/rag-sandbox'

export const ragSandboxOverview = () => request(`${RS}/overview`)
export const ragSandboxExperiments = (query = '') => request(`${RS}/experiments${query}`)
export const createRagSandboxExperiment = (body) => request(`${RS}/experiments`, { method: 'POST', body: JSON.stringify(body) })
export const ragSandboxExperiment = (id) => request(`${RS}/experiments/${id}`)
export const ragSandboxEligibility = (id) => request(`${RS}/experiments/${id}/eligibility`)
export const cancelRagSandboxExperiment = (id) => request(`${RS}/experiments/${id}/cancel`, { method: 'POST' })

export const requestRagSandboxApproval = (id, body) => request(`${RS}/experiments/${id}/request-approval`, { method: 'POST', body: JSON.stringify(body) })
export const approveRagSandboxExperiment = (id, body) => request(`${RS}/experiments/${id}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const rejectRagSandboxApproval = (id, body) => request(`${RS}/experiments/${id}/reject-approval`, { method: 'POST', body: JSON.stringify(body) })

export const prepareRagSandboxCorpus = (id) => request(`${RS}/experiments/${id}/prepare-corpus`, { method: 'POST', body: JSON.stringify({}) })
export const ragSandboxRecords = (id, query = '') => request(`${RS}/experiments/${id}/records${query}`)

export const buildRagSandboxIndex = (id, body) => request(`${RS}/experiments/${id}/build-index`, { method: 'POST', body: JSON.stringify(body) })
export const ragSandboxIndexes = (id) => request(`${RS}/experiments/${id}/indexes`)
export const deleteRagSandboxIndex = (id, indexId) => request(`${RS}/experiments/${id}/indexes/${indexId}/delete`, { method: 'POST' })

export const createRagSandboxQuerySet = (id, body) => request(`${RS}/experiments/${id}/query-sets`, { method: 'POST', body: JSON.stringify(body) })
export const ragSandboxQuerySets = (id) => request(`${RS}/experiments/${id}/query-sets`)
export const addRagSandboxQuery = (id, querySetId, body) => request(`${RS}/experiments/${id}/query-sets/${querySetId}/queries`, { method: 'POST', body: JSON.stringify(body) })
export const ragSandboxQueries = (id, querySetId) => request(`${RS}/experiments/${id}/query-sets/${querySetId}/queries`)
export const finalizeRagSandboxQuerySet = (id, querySetId) => request(`${RS}/experiments/${id}/query-sets/${querySetId}/finalize`, { method: 'POST' })

export const runRagSandboxRetrieval = (id, body) => request(`${RS}/experiments/${id}/run-retrieval`, { method: 'POST', body: JSON.stringify(body) })
export const ragSandboxRetrievalRuns = (id) => request(`${RS}/experiments/${id}/retrieval-runs`)
export const ragSandboxRetrievalRun = (id, runId) => request(`${RS}/experiments/${id}/retrieval-runs/${runId}`)

export const runRagSandboxGeneration = (id, body) => request(`${RS}/experiments/${id}/run-generation`, { method: 'POST', body: JSON.stringify(body) })
export const ragSandboxAnswerRuns = (id) => request(`${RS}/experiments/${id}/answer-runs`)
export const ragSandboxAnswerRun = (id, runId) => request(`${RS}/experiments/${id}/answer-runs/${runId}`)

export const ragSandboxCitations = (id) => request(`${RS}/experiments/${id}/citations`)
export const ragSandboxEvaluations = (id, query = '') => request(`${RS}/experiments/${id}/evaluations${query}`)
export const runRagSandboxEvaluation = (id, body) => request(`${RS}/experiments/${id}/evaluations/run`, { method: 'POST', body: JSON.stringify(body) })

export const reviewRagSandboxQuery = (id, queryId, body) => request(`${RS}/experiments/${id}/queries/${queryId}/review`, { method: 'POST', body: JSON.stringify(body) })
export const finalizeRagSandboxReport = (id) => request(`${RS}/experiments/${id}/finalize-report`, { method: 'POST' })
export const ragSandboxReports = (id) => request(`${RS}/experiments/${id}/report`)

export const acceptRagSandboxExperiment = (id, body) => request(`${RS}/experiments/${id}/accept`, { method: 'POST', body: JSON.stringify(body) })
export const rejectRagSandboxExperiment = (id, body) => request(`${RS}/experiments/${id}/reject`, { method: 'POST', body: JSON.stringify(body) })

export const requestRagSandboxDeletion = (id, body) => request(`${RS}/experiments/${id}/request-deletion`, { method: 'POST', body: JSON.stringify(body) })
export const confirmRagSandboxDeletion = (id) => request(`${RS}/experiments/${id}/confirm-deletion`, { method: 'POST' })
export const executeRagSandboxDeletion = (id) => request(`${RS}/experiments/${id}/execute-deletion`, { method: 'POST' })

export const ragSandboxEvents = (id, query = '') => request(`${RS}/experiments/${id}/events${query}`)

const IT = '/api/admin/incremental-training'

export const incrementalTrainingOverview = () => request(`${IT}/overview`)

export const createTrainingAssessment = (body) => request(`${IT}/assessments`, { method: 'POST', body: JSON.stringify(body) })
export const runTrainingAssessment = (id) => request(`${IT}/assessments/${id}/run`, { method: 'POST', body: JSON.stringify({}) })
export const acknowledgeTrainingAssessment = (id) => request(`${IT}/assessments/${id}/review`, { method: 'POST', body: JSON.stringify({}) })
export const trainingAssessments = (query = '') => request(`${IT}/assessments${query}`)
export const trainingAssessment = (id) => request(`${IT}/assessments/${id}`)
export const trainingAssessmentItems = (id, query = '') => request(`${IT}/assessments/${id}/items${query}`)
export const trainingAssessmentCandidates = (id, query = '') => request(`${IT}/assessments/${id}/candidates${query}`)

export const transformTrainingItem = (itemId, body) => request(`${IT}/items/${itemId}/transform`, { method: 'POST', body: JSON.stringify(body) })
export const reviewTrainingCandidate = (candidateId, body) => request(`${IT}/candidates/${candidateId}/review`, { method: 'POST', body: JSON.stringify(body) })
export const trainingCandidate = (candidateId) => request(`${IT}/candidates/${candidateId}`)
export const trainingCandidateRevisions = (candidateId) => request(`${IT}/candidates/${candidateId}/revisions`)

export const contaminationRecheck = (candidateIds) => request(`${IT}/contamination-recheck?${candidateIds.map((id) => `candidate_public_ids=${encodeURIComponent(id)}`).join('&')}`)

export const createReplayPlan = (assessmentId, body) => request(`${IT}/assessments/${assessmentId}/replay-plans`, { method: 'POST', body: JSON.stringify(body) })
export const replayPlans = (assessmentId) => request(`${IT}/assessments/${assessmentId}/replay-plans`)
export const replayPlan = (id) => request(`${IT}/replay-plans/${id}`)

export const createPromotionRequest = (assessmentId, body) => request(`${IT}/assessments/${assessmentId}/promotion-requests`, { method: 'POST', body: JSON.stringify(body) })
export const submitPromotionRequest = (id) => request(`${IT}/promotion-requests/${id}/submit`, { method: 'POST', body: JSON.stringify({}) })
export const approvePromotionRequest = (id, body = {}) => request(`${IT}/promotion-requests/${id}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const materializePromotionRequest = (id) => request(`${IT}/promotion-requests/${id}/materialize`, { method: 'POST', body: JSON.stringify({}) })
export const promotionRequest = (id) => request(`${IT}/promotion-requests/${id}`)

export const createTrainingRunRequest = (promotionId, body) => request(`${IT}/promotion-requests/${promotionId}/run-requests`, { method: 'POST', body: JSON.stringify(body) })
export const submitTrainingRunRequest = (id) => request(`${IT}/run-requests/${id}/submit`, { method: 'POST', body: JSON.stringify({}) })
export const requestTrainingRunApproval = (id) => request(`${IT}/run-requests/${id}/request-approval`, { method: 'POST', body: JSON.stringify({}) })
export const trainingRunRequest = (id) => request(`${IT}/run-requests/${id}`)
export const approveTrainingRunApproval = (id, body = {}) => request(`${IT}/run-approvals/${id}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const rejectTrainingRunApproval = (id) => request(`${IT}/run-approvals/${id}/reject`, { method: 'POST', body: JSON.stringify({}) })
export const trainingRunApproval = (id) => request(`${IT}/run-approvals/${id}`)

export const startTrainingRun = (approvalId) => request(`${IT}/run-approvals/${approvalId}/start`, { method: 'POST', body: JSON.stringify({}) })
export const acknowledgeNoTrainingExecution = (approvalId) => request(`${IT}/run-approvals/${approvalId}/acknowledge-no-execution`, { method: 'POST', body: JSON.stringify({}) })
export const trainingRuns = (query = '') => request(`${IT}/runs${query}`)
export const trainingRun = (id) => request(`${IT}/runs/${id}`)
export const trainingRunEvents = (id, query = '') => request(`${IT}/runs/${id}/events${query}`)
export const trainingRunCheckpoints = (id) => request(`${IT}/runs/${id}/checkpoints`)

export const verifyTrainingCheckpoint = (id) => request(`${IT}/checkpoints/${id}/verify`, { method: 'POST', body: JSON.stringify({}) })
export const evaluateTrainingCheckpoint = (id) => request(`${IT}/checkpoints/${id}/evaluate`, { method: 'POST', body: JSON.stringify({}) })
export const trainingCheckpoint = (id) => request(`${IT}/checkpoints/${id}`)
export const trainingCheckpointEvaluations = (id) => request(`${IT}/checkpoints/${id}/evaluations`)

export const compareTrainingCheckpoint = (id, body) => request(`${IT}/checkpoints/${id}/compare`, { method: 'POST', body: JSON.stringify(body) })
export const trainingCheckpointComparisons = (id) => request(`${IT}/checkpoints/${id}/comparisons`)

export const addTrainingCheckpointHumanReview = (id, body) => request(`${IT}/checkpoints/${id}/human-reviews`, { method: 'POST', body: JSON.stringify(body) })
export const trainingCheckpointHumanReviews = (id) => request(`${IT}/checkpoints/${id}/human-reviews`)

export const finalizeTrainingReport = (runId, body) => request(`${IT}/runs/${runId}/reports`, { method: 'POST', body: JSON.stringify(body) })
export const trainingReports = (runId) => request(`${IT}/runs/${runId}/reports`)
export const trainingReport = (id) => request(`${IT}/reports/${id}`)

export const acceptTrainingCheckpoint = (id, body) => request(`${IT}/checkpoints/${id}/accept`, { method: 'POST', body: JSON.stringify(body) })
export const trainingCheckpointAcceptances = (id) => request(`${IT}/checkpoints/${id}/acceptances`)

const PRR = '/api/admin/production-readiness'

export const productionReadinessOverview = () => request(`${PRR}/overview`)

export const productionRagEligibility = (experimentId, commercialUseContext = 'unknown') => request(`${PRR}/rag/eligibility/${experimentId}?commercial_use_context=${encodeURIComponent(commercialUseContext)}`)
export const createRagPromotionRequest = (body) => request(`${PRR}/rag/promotion-requests`, { method: 'POST', body: JSON.stringify(body) })
export const ragPromotionRequests = (status = '') => request(`${PRR}/rag/promotion-requests${status ? `?status=${status}` : ''}`)
export const ragPromotionRequest = (id) => request(`${PRR}/rag/promotion-requests/${id}`)
export const submitRagPromotionRequest = (id) => request(`${PRR}/rag/promotion-requests/${id}/submit`, { method: 'POST', body: JSON.stringify({}) })
export const requestRagPromotionApproval = (id) => request(`${PRR}/rag/promotion-requests/${id}/approval/request`, { method: 'POST', body: JSON.stringify({}) })
export const approveRagPromotion = (approvalId, body = {}) => request(`${PRR}/rag/promotion-approvals/${approvalId}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const buildRagReleaseCandidate = (promotionId) => request(`${PRR}/rag/promotion-requests/${promotionId}/candidates`, { method: 'POST', body: JSON.stringify({}) })
export const ragReleaseCandidates = (promotionId) => request(`${PRR}/rag/promotion-requests/${promotionId}/candidates`)
export const ragReleaseCandidate = (id) => request(`${PRR}/rag/candidates/${id}`)
export const validateRagReleaseCandidate = (id) => request(`${PRR}/rag/candidates/${id}/validate`, { method: 'POST', body: JSON.stringify({}) })
export const activateRagReleaseCandidate = (id) => request(`${PRR}/rag/candidates/${id}/activate`, { method: 'POST', body: JSON.stringify({}) })
export const rollbackRagReleaseCandidate = (id) => request(`${PRR}/rag/candidates/${id}/rollback`, { method: 'POST', body: JSON.stringify({}) })

export const modelReleaseEligibility = (checkpointId) => request(`${PRR}/model/eligibility/${checkpointId}`)
export const createModelReleaseRequest = (body) => request(`${PRR}/model/release-requests`, { method: 'POST', body: JSON.stringify(body) })
export const modelReleaseRequests = (status = '') => request(`${PRR}/model/release-requests${status ? `?status=${status}` : ''}`)
export const modelReleaseRequest = (id) => request(`${PRR}/model/release-requests/${id}`)
export const submitModelReleaseRequest = (id) => request(`${PRR}/model/release-requests/${id}/submit`, { method: 'POST', body: JSON.stringify({}) })
export const validateModelReleaseRequest = (id) => request(`${PRR}/model/release-requests/${id}/validate`, { method: 'POST', body: JSON.stringify({}) })
export const requestModelReleaseApproval = (id) => request(`${PRR}/model/release-requests/${id}/approval/request`, { method: 'POST', body: JSON.stringify({}) })
export const approveModelRelease = (approvalId, body = {}) => request(`${PRR}/model/release-approvals/${approvalId}/approve`, { method: 'POST', body: JSON.stringify(body) })
export const rejectModelReleaseRequest = (id) => request(`${PRR}/model/release-requests/${id}/reject`, { method: 'POST', body: JSON.stringify({}) })
export const startModelCanary = (id, body) => request(`${PRR}/model/release-requests/${id}/canary/start`, { method: 'POST', body: JSON.stringify(body) })
export const executeModelCanary = (id, body) => request(`${PRR}/model/release-requests/${id}/canary/execute`, { method: 'POST', body: JSON.stringify(body) })
export const stopModelCanary = (id, body) => request(`${PRR}/model/release-requests/${id}/canary/stop`, { method: 'POST', body: JSON.stringify(body) })
export const activateModelRelease = (id, body) => request(`${PRR}/model/release-requests/${id}/activate`, { method: 'POST', body: JSON.stringify(body) })
export const rollbackModelRelease = (id, body) => request(`${PRR}/model/release-requests/${id}/rollback`, { method: 'POST', body: JSON.stringify(body) })
export const modelActivationEvents = (id) => request(`${PRR}/model/release-requests/${id}/activation-events`)
export const modelPostActivationChecks = (id) => request(`${PRR}/model/release-requests/${id}/post-activation-checks`)

export const createProductionRollbackPlan = (body) => request(`${PRR}/rollback-plans`, { method: 'POST', body: JSON.stringify(body) })
export const validateProductionRollbackPlan = (id) => request(`${PRR}/rollback-plans/${id}/validate`, { method: 'POST', body: JSON.stringify({}) })
export const rollbackPlans = (targetType = '') => request(`${PRR}/rollback-plans${targetType ? `?target_type=${targetType}` : ''}`)
export const productionRollbackPlan = (id) => request(`${PRR}/rollback-plans/${id}`)

export const checkReleaseCandidateArtifacts = (id) => request(`${PRR}/artifact-security/release-candidates/${id}/check`, { method: 'POST', body: JSON.stringify({}) })
export const checkBackupArtifactSecurity = () => request(`${PRR}/artifact-security/backup/check`, { method: 'POST', body: JSON.stringify({}) })
export const checkRagCandidateArtifactSecurity = (id) => request(`${PRR}/artifact-security/rag-candidates/${id}/check`, { method: 'POST', body: JSON.stringify({}) })
export const artifactSecurityChecks = (artifactType = '') => request(`${PRR}/artifact-security/checks${artifactType ? `?artifact_type=${artifactType}` : ''}`)

export const assessApiAbuseReadiness = () => request(`${PRR}/api-abuse-readiness/assess`, { method: 'POST', body: JSON.stringify({}) })
export const verifySecretRedaction = () => request(`${PRR}/secret-scan/verify-redaction`, { method: 'POST', body: JSON.stringify({}) })
export const scanFrontendBundle = () => request(`${PRR}/secret-scan/frontend-bundle`, { method: 'POST', body: JSON.stringify({}) })
export const scanDomainModelFields = () => request(`${PRR}/secret-scan/domain-model-fields`, { method: 'POST', body: JSON.stringify({}) })
export const scanBackupSidecarFiles = () => request(`${PRR}/secret-scan/backup-sidecar-files`, { method: 'POST', body: JSON.stringify({}) })

export const checkBackupReadiness = (body = {}) => request(`${PRR}/backup-readiness/check`, { method: 'POST', body: JSON.stringify(body) })
export const assessBackupEncryption = () => request(`${PRR}/backup-readiness/assess-encryption`, { method: 'POST' })
export const encryptLatestBackup = () => request(`${PRR}/backup-readiness/encrypt`, { method: 'POST' })
export const verifyEncryptedRestore = () => request(`${PRR}/backup-readiness/verify-encrypted-restore`, { method: 'POST' })
export const checkRestoreReadiness = () => request(`${PRR}/restore-readiness/check`, { method: 'POST', body: JSON.stringify({}) })
export const backupReadinessChecks = (checkType = '') => request(`${PRR}/backup-readiness/checks${checkType ? `?check_type=${checkType}` : ''}`)
export const assessDeploymentReadiness = () => request(`${PRR}/deployment-readiness/assess`, { method: 'POST', body: JSON.stringify({}) })
export const latestDeploymentReadiness = () => request(`${PRR}/deployment-readiness/latest`)
export const productionSystemHealth = () => request(`${PRR}/system-health`)

export const createProductionRegressionRun = (body) => request(`${PRR}/regression/runs`, { method: 'POST', body: JSON.stringify(body) })
export const executeProductionRegressionBatch = (id, body) => request(`${PRR}/regression/runs/${id}/batches`, { method: 'POST', body: JSON.stringify(body) })
export const finalizeProductionRegressionRun = (id) => request(`${PRR}/regression/runs/${id}/finalize`, { method: 'POST', body: JSON.stringify({}) })
export const productionRegressionRuns = () => request(`${PRR}/regression/runs`)
export const productionRegressionRun = (id) => request(`${PRR}/regression/runs/${id}`)
export const productionRegressionResults = (id) => request(`${PRR}/regression/runs/${id}/results`)

export const compileReadinessReport = () => request(`${PRR}/readiness-reports`, { method: 'POST', body: JSON.stringify({}) })
export const readinessReports = () => request(`${PRR}/readiness-reports`)
export const latestReadinessReport = () => request(`${PRR}/readiness-reports/latest`)
export const readinessReport = (id) => request(`${PRR}/readiness-reports/${id}`)
export const submitAcceptanceReview = (reportId, body) => request(`${PRR}/readiness-reports/${reportId}/acceptance-review`, { method: 'POST', body: JSON.stringify(body) })

const KR = '/api/admin/knowledge-routing'
export const knowledgeRoutingPolicy = () => request(`${KR}/policy`)
export const knowledgeRoutingReasonCodes = () => request(`${KR}/reason-codes`)
export const knowledgeRoutingContextTypes = () => request(`${KR}/context-types`)
export const classifyKnowledgeRoutingText = (body) => request(`${KR}/classify`, { method: 'POST', body: JSON.stringify(body) })
export const classifyKnowledgeRoutingRecord = (body) => request(`${KR}/classify-record`, { method: 'POST', body: JSON.stringify(body) })
export const knowledgeRoutingDecision = (id) => request(`${KR}/decisions/${id}`)
export const knowledgeRoutingDecisions = (query = '') => request(`${KR}/decisions${query}`)
export const knowledgeRoutingMetrics = () => request(`${KR}/metrics`)

const PCR = '/api/admin/public-chat-routing'
export const publicChatRoutingOverview = () => request(`${PCR}/overview`)
export const publicChatRoutingEvents = (query = '') => request(`${PCR}/events${query}`)
export const publicChatRoutingEvent = (id) => request(`${PCR}/events/${id}`)

const KG = '/api/admin/knowledge-gaps'
export const knowledgeGapOverview = () => request(`${KG}/overview`)
export const knowledgeGapCases = (query = '') => request(`${KG}/cases${query}`)
export const knowledgeGapCase = (id) => request(`${KG}/cases/${id}`)
export const knowledgeGapOccurrences = (id) => request(`${KG}/cases/${id}/occurrences`)
export const knowledgeGapReviews = (id) => request(`${KG}/cases/${id}/reviews`)
export const knowledgeGapNotes = (id) => request(`${KG}/cases/${id}/notes`)
export const knowledgeGapEvents = (id) => request(`${KG}/cases/${id}/events`)
export const reviewKnowledgeGapCase = (id, body) => request(`${KG}/cases/${id}/review`, { method: 'POST', body: JSON.stringify(body) })
export const addKnowledgeGapNote = (id, body) => request(`${KG}/cases/${id}/notes`, { method: 'POST', body: JSON.stringify(body) })
export const resolveKnowledgeGapCase = (id, body) => request(`${KG}/cases/${id}/resolve`, { method: 'POST', body: JSON.stringify(body) })
export const archiveKnowledgeGapCase = (id) => request(`${KG}/cases/${id}/archive`, { method: 'POST', body: '{}' })
export const assessKnowledgeGapHandoff = (id) => request(`${KG}/cases/${id}/assess-handoff`, { method: 'POST', body: '{}' })
export const knowledgeGapClusters = (query = '') => request(`${KG}/clusters${query}`)
export const proposeKnowledgeGapMerge = (body) => request(`${KG}/clusters/propose-merge`, { method: 'POST', body: JSON.stringify(body) })
export const confirmKnowledgeGapMerge = (body) => request(`${KG}/clusters/confirm-merge`, { method: 'POST', body: JSON.stringify(body) })
export const recalculateKnowledgeGapClusterPriority = (id) => request(`${KG}/clusters/${id}/recalculate-priority`, { method: 'POST', body: '{}' })
export const knowledgeGapDailyReports = () => request(`${KG}/reports/daily`)
export const generateKnowledgeGapDailyReport = () => request(`${KG}/reports/daily/generate`, { method: 'POST', body: '{}' })
export const requestKnowledgeGapDeletion = (id, body) => request(`${KG}/cases/${id}/request-deletion`, { method: 'POST', body: JSON.stringify(body) })
export const knowledgeGapDeletionPreview = (id) => request(`${KG}/cases/${id}/deletion-preview`)
export const confirmKnowledgeGapDeletion = (id) => request(`${KG}/cases/${id}/confirm-deletion`, { method: 'POST', body: '{}' })
export const executeKnowledgeGapDeletion = (id) => request(`${KG}/cases/${id}/execute-deletion`, { method: 'POST', body: '{}' })

const TW = '/api/admin/trusted-web'
export const trustedWebOverview = () => request(`${TW}/overview`)
export const trustedWebProviders = () => request(`${TW}/providers`)
export const trustedWebPolicy = () => request(`${TW}/policy`)
export const trustedWebSearchEvents = (query = '') => request(`${TW}/search-events${query}`)
export const trustedWebEvidence = (query = '') => request(`${TW}/evidence${query}`)
export const trustedWebFetchEvents = (query = '') => request(`${TW}/fetch-events${query}`)
export const trustedWebHealth = () => request(`${TW}/health`)
export const trustedWebTestSearch = (body) => request(`${TW}/test-search`, { method: 'POST', body: JSON.stringify(body) })
export const trustedWebVerifySource = (body) => request(`${TW}/verify-source`, { method: 'POST', body: JSON.stringify(body) })

const DT = '/api/admin/deterministic-tools'
export const toolsOverview = () => request(`${DT}/overview`)
export const toolsRegistry = () => request(`${DT}/registry`)
export const toolsExecutionEvents = (query = '') => request(`${DT}/execution-events${query}`)
export const toolsTest = (body) => request(`${DT}/test`, { method: 'POST', body: JSON.stringify(body) })

const MB = '/api/admin/mini-brain'
export const miniBrainStatus = () => request(`${MB}/status`)
export const miniBrainSettings = () => request(`${MB}/settings`)
export const updateMiniBrainSettings = (body) => request(`${MB}/settings`, { method: 'PATCH', body: JSON.stringify(body) })
export const enableMiniBrain = () => request(`${MB}/enable`, { method: 'POST', body: '{}' })
export const disableMiniBrain = () => request(`${MB}/disable`, { method: 'POST', body: '{}' })
export const miniBrainHealth = () => request(`${MB}/health`)
export const miniBrainRuntimeHealth = () => request(`${MB}/runtime-health`)
export const miniBrainDiagnostics = () => request(`${MB}/diagnostics`)
export const miniBrainVersion = () => request(`${MB}/version`)
export const miniBrainLogs = (query = '') => request(`${MB}/logs${query}`)

const MBKC = '/api/admin/mini-brain/knowledge-core'
export const seedKnowledgeCore = () => request(`${MBKC}/seed`, { method: 'POST', body: '{}' })
export const knowledgeCoreDomains = () => request(`${MBKC}/domains`)
export const knowledgeCoreItem = (id) => request(`${MBKC}/items/${id}`)
export const searchKnowledgeCore = (query = '') => request(`${MBKC}/search${query}`)
export const runKnowledgeCoreValidation = () => request(`${MBKC}/validate`, { method: 'POST', body: '{}' })
export const knowledgeCoreCoverage = () => request(`${MBKC}/coverage`)

const MBIE = '/api/admin/mini-brain/intelligence'
export const analyzeQuestion = (question) => request(`${MBIE}/analyze`, { method: 'POST', body: JSON.stringify({ question }) })

const MBRT = '/api/admin/mini-brain/runtime'
export const registerRuntimeModel = (body) => request(`${MBRT}/models`, { method: 'POST', body: JSON.stringify(body) })
export const listRuntimeModels = () => request(`${MBRT}/models`)
export const runtimeModelInfo = (id) => request(`${MBRT}/models/${id}`)
export const loadRuntimeModel = (modelPublicId) => request(`${MBRT}/load`, { method: 'POST', body: JSON.stringify({ model_public_id: modelPublicId }) })
export const unloadRuntimeModel = () => request(`${MBRT}/unload`, { method: 'POST', body: '{}' })
export const reloadRuntimeModel = () => request(`${MBRT}/reload`, { method: 'POST', body: '{}' })
export const runtimeStatus = () => request(`${MBRT}/status`)
export const runtimeStatistics = () => request(`${MBRT}/statistics`)
export const runtimeDiagnostics = () => request(`${MBRT}/diagnostics`)

const MBQ = '/api/admin/mini-brain/quality'
export const qualityCheck = (body) => request(`${MBQ}/check`, { method: 'POST', body: JSON.stringify(body) })
export const qualityValidate = (body) => request(`${MBQ}/validate`, { method: 'POST', body: JSON.stringify(body) })
export const qualityReport = (body) => request(`${MBQ}/report`, { method: 'POST', body: JSON.stringify(body) })
export const qualityFormat = (text) => request(`${MBQ}/format`, { method: 'POST', body: JSON.stringify({ text }) })
export const qualityGenerate = (body) => request(`${MBQ}/generate`, { method: 'POST', body: JSON.stringify(body) })
export const qualityDiagnostics = () => request(`${MBQ}/diagnostics`)

const MBC = '/api/admin/mini-brain/capability'
export const capabilityGenerate = (question) => request(`${MBC}/generate`, { method: 'POST', body: JSON.stringify({ question }) })
export const capabilityDiagnostics = () => request(`${MBC}/diagnostics`)

const MBDI = '/api/admin/mini-brain/dataset-intelligence'
export const datasetIntelligenceReport = (sourcePublicId) => request(`${MBDI}/report`, { method: 'POST', body: JSON.stringify({ source_public_id: sourcePublicId }) })
export const datasetIntelligenceDiagnostics = () => request(`${MBDI}/diagnostics`)

const MBDA = '/api/admin/mini-brain/dataset-advanced'
export const datasetAdvancedReport = (sourcePublicId) => request(`${MBDA}/report`, { method: 'POST', body: JSON.stringify({ source_public_id: sourcePublicId }) })
export const datasetAdvancedDiagnostics = () => request(`${MBDA}/diagnostics`)

const MBLS = '/api/admin/mini-brain/learning-supervisor'
export const learningSupervisorProfiles = () => request(`${MBLS}/hyperparameter-profiles`)
export const learningSupervisorSessions = () => request(`${MBLS}/sessions`)
export const learningSupervisorCreateSession = (body) => request(`${MBLS}/sessions`, { method: 'POST', body: JSON.stringify(body) })
export const learningSupervisorSession = (id) => request(`${MBLS}/sessions/${id}`)
export const learningSupervisorEvents = (id) => request(`${MBLS}/sessions/${id}/events`)
export const learningSupervisorValidateDataset = (id) => request(`${MBLS}/sessions/${id}/validate-dataset`, { method: 'POST', body: '{}' })
export const learningSupervisorDecideDataset = (id, decision) => request(`${MBLS}/sessions/${id}/decide-dataset`, { method: 'POST', body: JSON.stringify({ decision }) })
export const learningSupervisorRunRag = (id, body) => request(`${MBLS}/sessions/${id}/rag-evaluation`, { method: 'POST', body: JSON.stringify(body) })
export const learningSupervisorFinalizeRag = (id) => request(`${MBLS}/sessions/${id}/rag-evaluation/finalize`, { method: 'POST', body: '{}' })
export const learningSupervisorDecideRag = (id, decision) => request(`${MBLS}/sessions/${id}/decide-rag`, { method: 'POST', body: JSON.stringify({ decision }) })
export const learningSupervisorSubmitTraining = (id, body) => request(`${MBLS}/sessions/${id}/training-request`, { method: 'POST', body: JSON.stringify(body) })
export const learningSupervisorMonitorTraining = (id) => request(`${MBLS}/sessions/${id}/training-monitor`)
export const learningSupervisorAnalyzeTraining = (id) => request(`${MBLS}/sessions/${id}/analyze-training`, { method: 'POST', body: '{}' })
export const learningSupervisorRunBenchmark = (id, body) => request(`${MBLS}/sessions/${id}/benchmark`, { method: 'POST', body: JSON.stringify(body) })
export const learningSupervisorCompareModels = (id, body) => request(`${MBLS}/sessions/${id}/compare-models`, { method: 'POST', body: JSON.stringify(body) })
export const learningSupervisorRecommendations = (id) => request(`${MBLS}/sessions/${id}/recommendations`, { method: 'POST', body: '{}' })
export const learningSupervisorAdminReview = (id, decision) => request(`${MBLS}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })
export const learningSupervisorReleaseCandidate = (id, body) => request(`${MBLS}/sessions/${id}/release-candidate`, { method: 'POST', body: JSON.stringify(body) })

const MBRP = '/api/admin/mini-brain/release-pipeline'
export const releasePipelineDiagnostics = () => request(`${MBRP}/diagnostics`)
export const releasePipelineSessions = () => request(`${MBRP}/sessions`)
export const releasePipelineCreateSession = (body) => request(`${MBRP}/sessions`, { method: 'POST', body: JSON.stringify(body) })
export const releasePipelineSession = (id) => request(`${MBRP}/sessions/${id}`)
export const releasePipelineEvents = (id) => request(`${MBRP}/sessions/${id}/events`)
export const releasePipelineValidateCheckpoint = (id) => request(`${MBRP}/sessions/${id}/validate`, { method: 'POST', body: '{}' })
export const releasePipelineConvert = (id) => request(`${MBRP}/sessions/${id}/convert`, { method: 'POST', body: '{}' })
export const releasePipelineQuantize = (id) => request(`${MBRP}/sessions/${id}/quantize`, { method: 'POST', body: '{}' })
export const releasePipelineVerify = (id) => request(`${MBRP}/sessions/${id}/verify`, { method: 'POST', body: '{}' })
export const releasePipelinePerformance = (id) => request(`${MBRP}/sessions/${id}/performance`, { method: 'POST', body: '{}' })
export const releasePipelineCreateVersion = (id, body) => request(`${MBRP}/sessions/${id}/version`, { method: 'POST', body: JSON.stringify(body) })
export const releasePipelineRegistry = (id) => request(`${MBRP}/sessions/${id}/register`)
export const releasePipelineAdminReview = (id, decision) => request(`${MBRP}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })
export const releasePipelineActivate = (id, quantizationLevel) => request(`${MBRP}/sessions/${id}/activate`, { method: 'POST', body: JSON.stringify({ quantization_level: quantizationLevel }) })
export const releasePipelineEvaluateRollback = (id, targetVersion) => request(`${MBRP}/sessions/${id}/rollback/evaluate`, { method: 'POST', body: JSON.stringify({ target_version: targetVersion }) })
export const releasePipelineExecuteRollback = (id, body) => request(`${MBRP}/sessions/${id}/rollback`, { method: 'POST', body: JSON.stringify(body) })
export const releasePipelineReport = (id) => request(`${MBRP}/sessions/${id}/report`)

const MBCL = '/api/admin/mini-brain/continuous-learning'
export const continuousLearningDiagnostics = () => request(`${MBCL}/diagnostics`)
export const continuousLearningSessions = () => request(`${MBCL}/sessions`)
export const continuousLearningCreateSession = (cycleWindowDays) => request(`${MBCL}/sessions`, { method: 'POST', body: JSON.stringify({ cycle_window_days: cycleWindowDays }) })
export const continuousLearningSession = (id) => request(`${MBCL}/sessions/${id}`)
export const continuousLearningEvents = (id) => request(`${MBCL}/sessions/${id}/events`)
export const continuousLearningCollectFeedback = (id) => request(`${MBCL}/sessions/${id}/feedback`, { method: 'POST', body: '{}' })
export const continuousLearningAnalyzeFailures = (id) => request(`${MBCL}/sessions/${id}/failures`, { method: 'POST', body: '{}' })
export const continuousLearningAnalyzeHallucinations = (id) => request(`${MBCL}/sessions/${id}/hallucinations`, { method: 'POST', body: '{}' })
export const continuousLearningAnalyzeKnowledgeGaps = (id) => request(`${MBCL}/sessions/${id}/knowledge-gaps`, { method: 'POST', body: '{}' })
export const continuousLearningDetectWeakTopics = (id) => request(`${MBCL}/sessions/${id}/topics`, { method: 'POST', body: '{}' })
export const continuousLearningAnalyzeDifficulty = (id) => request(`${MBCL}/sessions/${id}/difficulty`, { method: 'POST', body: '{}' })
export const continuousLearningRecommendDatasets = (id) => request(`${MBCL}/sessions/${id}/datasets`, { method: 'POST', body: '{}' })
export const continuousLearningRecommendTraining = (id) => request(`${MBCL}/sessions/${id}/training`, { method: 'POST', body: '{}' })
export const continuousLearningRankPriorities = (id) => request(`${MBCL}/sessions/${id}/priority`, { method: 'POST', body: '{}' })
export const continuousLearningGenerateReport = (id) => request(`${MBCL}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const continuousLearningAdminReview = (id, decision) => request(`${MBCL}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBCLC = '/api/admin/mini-brain/continuous-learning-center'
export const clcDiagnostics = () => request(`${MBCLC}/diagnostics`)
export const clcListMemory = () => request(`${MBCLC}/memory`)
export const clcRecordMemory = (body) => request(`${MBCLC}/memory`, { method: 'POST', body: JSON.stringify(body) })
export const clcSessions = () => request(`${MBCLC}/sessions`)
export const clcCreateSession = () => request(`${MBCLC}/sessions`, { method: 'POST', body: '{}' })
export const clcSession = (id) => request(`${MBCLC}/sessions/${id}`)
export const clcEvents = (id) => request(`${MBCLC}/sessions/${id}/events`)
export const clcEvolveKnowledgeGaps = (id) => request(`${MBCLC}/sessions/${id}/knowledge-gap-evolution`, { method: 'POST', body: '{}' })
export const clcBuildLearningQueue = (id) => request(`${MBCLC}/sessions/${id}/learning-queue`, { method: 'POST', body: '{}' })
export const clcBuildDraft = (id, topic) => request(`${MBCLC}/sessions/${id}/draft`, { method: 'POST', body: JSON.stringify({ topic: topic || null }) })
export const clcPrepareProviderRequest = (id, requestedProviders) => request(`${MBCLC}/sessions/${id}/provider-request`, { method: 'POST', body: JSON.stringify({ requested_providers: requestedProviders }) })
export const clcIngestProviderResults = (id, providerOutputs) => request(`${MBCLC}/sessions/${id}/provider-consensus`, { method: 'POST', body: JSON.stringify({ provider_outputs: providerOutputs }) })
export const clcPlanDatasetEvolution = (id, existingDatasetSourcePublicId) => request(`${MBCLC}/sessions/${id}/dataset-evolution`, { method: 'POST', body: JSON.stringify({ existing_dataset_source_public_id: existingDatasetSourcePublicId || null }) })
export const clcBuildRoadmap = (id) => request(`${MBCLC}/sessions/${id}/roadmap`, { method: 'POST', body: '{}' })
export const clcGenerateRecommendation = (id) => request(`${MBCLC}/sessions/${id}/recommendation`, { method: 'POST', body: '{}' })
export const clcGenerateReport = (id) => request(`${MBCLC}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const clcAdminReview = (id, decision) => request(`${MBCLC}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBRC = '/api/admin/mini-brain/research-center'
export const rcDiagnostics = () => request(`${MBRC}/diagnostics`)
export const rcListProviders = () => request(`${MBRC}/providers`)
export const rcAddProvider = (body) => request(`${MBRC}/providers`, { method: 'POST', body: JSON.stringify(body) })
export const rcSetProviderStatus = (providerKey, status) => request(`${MBRC}/providers/${providerKey}/status`, { method: 'POST', body: JSON.stringify({ status }) })
export const rcListMemory = () => request(`${MBRC}/memory`)
export const rcRecordMemory = (id, notes) => request(`${MBRC}/sessions/${id}/memory`, { method: 'POST', body: JSON.stringify({ notes: notes || '' }) })
export const rcSessions = () => request(`${MBRC}/sessions`)
export const rcCreateSession = (topic) => request(`${MBRC}/sessions`, { method: 'POST', body: JSON.stringify({ topic }) })
export const rcSession = (id) => request(`${MBRC}/sessions/${id}`)
export const rcEvents = (id) => request(`${MBRC}/sessions/${id}/events`)
export const rcPrepareResearchRequest = (id, planningCenterSessionPublicId, priority) => request(`${MBRC}/sessions/${id}/research-request`, { method: 'POST', body: JSON.stringify({ planning_center_session_public_id: planningCenterSessionPublicId || null, priority: priority || null }) })
export const rcSelectMode = (id, mode, requestedProviderKeys) => request(`${MBRC}/sessions/${id}/mode`, { method: 'POST', body: JSON.stringify({ mode, requested_provider_keys: requestedProviderKeys || [] }) })
export const rcBuildLocalDraft = (id, existingDatasetSourcePublicId) => request(`${MBRC}/sessions/${id}/local-draft`, { method: 'POST', body: JSON.stringify({ existing_dataset_source_public_id: existingDatasetSourcePublicId || null }) })
export const rcPrepareProviderRequestPackage = (id) => request(`${MBRC}/sessions/${id}/provider-request`, { method: 'POST', body: '{}' })
export const rcIngestProviderResults = (id, providerOutputs) => request(`${MBRC}/sessions/${id}/provider-consensus`, { method: 'POST', body: JSON.stringify({ provider_outputs: providerOutputs }) })
export const rcBuildDatasetDraft = (id) => request(`${MBRC}/sessions/${id}/dataset-draft`, { method: 'POST', body: '{}' })
export const rcGenerateReport = (id) => request(`${MBRC}/sessions/${id}/report`)
export const rcAdminReviewDraft = (id, decision) => request(`${MBRC}/sessions/${id}/draft-review`, { method: 'POST', body: JSON.stringify({ decision }) })
export const rcRunRagEvaluation = (id, body) => request(`${MBRC}/sessions/${id}/rag-evaluation`, { method: 'POST', body: JSON.stringify(body) })
export const rcFinalizeRagEvaluation = (id) => request(`${MBRC}/sessions/${id}/rag-evaluation/finalize`, { method: 'POST', body: '{}' })
export const rcAdminReviewRag = (id, decision) => request(`${MBRC}/sessions/${id}/rag-review`, { method: 'POST', body: JSON.stringify({ decision }) })
export const rcCheckTrainingGate = (id) => request(`${MBRC}/sessions/${id}/training-gate`, { method: 'POST', body: '{}' })
export const rcAnalyzeTrainingReport = (id, learningSupervisorSessionPublicId) => request(`${MBRC}/sessions/${id}/training-report`, { method: 'POST', body: JSON.stringify({ learning_supervisor_session_public_id: learningSupervisorSessionPublicId }) })

const MBDE = '/api/admin/mini-brain/dataset-evolution'
export const deDiagnostics = () => request(`${MBDE}/diagnostics`)
export const deSessions = () => request(`${MBDE}/sessions`)
export const deCreateSession = (datasetSourcePublicId) => request(`${MBDE}/sessions`, { method: 'POST', body: JSON.stringify({ dataset_source_public_id: datasetSourcePublicId }) })
export const deSession = (id) => request(`${MBDE}/sessions/${id}`)
export const deEvents = (id) => request(`${MBDE}/sessions/${id}/events`)
export const deRunKnowledgeEvolution = (id) => request(`${MBDE}/sessions/${id}/knowledge-evolution`, { method: 'POST', body: '{}' })
export const deRunDatasetEvolution = (id) => request(`${MBDE}/sessions/${id}/dataset-evolution`, { method: 'POST', body: '{}' })
export const deRunSimulation = (id) => request(`${MBDE}/sessions/${id}/simulation`, { method: 'POST', body: '{}' })
export const deGenerateRecommendation = (id) => request(`${MBDE}/sessions/${id}/recommendation`, { method: 'POST', body: '{}' })
export const deGenerateReport = (id) => request(`${MBDE}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const deAdminReview = (id, decision) => request(`${MBDE}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })
export const deRunRagEvaluation = (id, body) => request(`${MBDE}/sessions/${id}/rag-evaluation`, { method: 'POST', body: JSON.stringify(body) })
export const deFinalizeRagEvaluation = (id) => request(`${MBDE}/sessions/${id}/rag-evaluation/finalize`, { method: 'POST', body: '{}' })
export const deAdminReviewRag = (id, decision) => request(`${MBDE}/sessions/${id}/rag-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBPC = '/api/admin/mini-brain/pipeline-coordinator'
export const pcDiagnostics = () => request(`${MBPC}/diagnostics`)
export const pcSessions = () => request(`${MBPC}/sessions`)
export const pcCreateSession = (topic) => request(`${MBPC}/sessions`, { method: 'POST', body: JSON.stringify({ topic }) })
export const pcSession = (id) => request(`${MBPC}/sessions/${id}`)
export const pcEvents = (id) => request(`${MBPC}/sessions/${id}/events`)
export const pcLinkResearch = (id, mb09SessionPublicId) => request(`${MBPC}/sessions/${id}/link-research`, { method: 'POST', body: JSON.stringify({ mb09_session_public_id: mb09SessionPublicId }) })
export const pcLinkResearchCenter = (id, mb10SessionPublicId) => request(`${MBPC}/sessions/${id}/link-research-center`, { method: 'POST', body: JSON.stringify({ mb10_session_public_id: mb10SessionPublicId }) })
export const pcRefreshResearchCenter = (id) => request(`${MBPC}/sessions/${id}/refresh-research-center`, { method: 'POST', body: '{}' })
export const pcLinkDatasetEvolution = (id, mb11SessionPublicId) => request(`${MBPC}/sessions/${id}/link-dataset-evolution`, { method: 'POST', body: JSON.stringify({ mb11_session_public_id: mb11SessionPublicId }) })
export const pcRunRagFirstEnforcement = (id) => request(`${MBPC}/sessions/${id}/rag-first-enforcement`, { method: 'POST', body: '{}' })
export const pcLinkTraining = (id, mb06SessionPublicId) => request(`${MBPC}/sessions/${id}/link-training`, { method: 'POST', body: JSON.stringify({ mb06_session_public_id: mb06SessionPublicId }) })
export const pcRefreshTraining = (id) => request(`${MBPC}/sessions/${id}/refresh-training`, { method: 'POST', body: '{}' })
export const pcGenerateTrainingReadiness = (id) => request(`${MBPC}/sessions/${id}/training-readiness`, { method: 'POST', body: '{}' })
export const pcGenerateTimeline = (id) => request(`${MBPC}/sessions/${id}/timeline`, { method: 'POST', body: '{}' })
export const pcPredictImprovement = (id) => request(`${MBPC}/sessions/${id}/improvement-prediction`, { method: 'POST', body: '{}' })
export const pcGenerateRecommendation = (id) => request(`${MBPC}/sessions/${id}/recommendation`, { method: 'POST', body: '{}' })
export const pcGenerateReport = (id) => request(`${MBPC}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const pcAdminDecide = (id, decision) => request(`${MBPC}/sessions/${id}/admin-decision`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBLI = '/api/admin/mini-brain/language-intelligence'
export const liDiagnostics = () => request(`${MBLI}/diagnostics`)
export const liSessions = () => request(`${MBLI}/sessions`)
export const liCreateSession = (datasetSourcePublicId) => request(`${MBLI}/sessions`, { method: 'POST', body: JSON.stringify({ dataset_source_public_id: datasetSourcePublicId }) })
export const liSession = (id) => request(`${MBLI}/sessions/${id}`)
export const liEvents = (id) => request(`${MBLI}/sessions/${id}/events`)
export const liRunLanguageScan = (id) => request(`${MBLI}/sessions/${id}/language-scan`, { method: 'POST', body: '{}' })
export const liRunUnicodeValidation = (id) => request(`${MBLI}/sessions/${id}/unicode-validation`, { method: 'POST', body: '{}' })
export const liRunSpellAnalysis = (id) => request(`${MBLI}/sessions/${id}/spell-analysis`, { method: 'POST', body: '{}' })
export const liRunGrammarAnalysis = (id) => request(`${MBLI}/sessions/${id}/grammar-analysis`, { method: 'POST', body: '{}' })
export const liRunOcrAnalysis = (id) => request(`${MBLI}/sessions/${id}/ocr-analysis`, { method: 'POST', body: '{}' })
export const liRunTanglishAnalysis = (id) => request(`${MBLI}/sessions/${id}/tanglish-analysis`, { method: 'POST', body: '{}' })
export const liRunTranslationAnalysis = (id, pairs) => request(`${MBLI}/sessions/${id}/translation-analysis`, { method: 'POST', body: JSON.stringify({ pairs: pairs || [] }) })
export const liRunDatasetDraft = (id) => request(`${MBLI}/sessions/${id}/dataset-draft`, { method: 'POST', body: '{}' })
export const liRunQualityScore = (id) => request(`${MBLI}/sessions/${id}/quality-score`, { method: 'POST', body: '{}' })
export const liGenerateReport = (id) => request(`${MBLI}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const liAdminReview = (id, decision) => request(`${MBLI}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBVI = '/api/admin/mini-brain/vision-intelligence'
export const viDiagnostics = () => request(`${MBVI}/diagnostics`)
export const viSessions = () => request(`${MBVI}/sessions`)
export const viCreateSession = (documentSourcePublicId, datasetSourcePublicId) => request(`${MBVI}/sessions`, { method: 'POST', body: JSON.stringify({ document_source_public_id: documentSourcePublicId, dataset_source_public_id: datasetSourcePublicId || null }) })
export const viSession = (id) => request(`${MBVI}/sessions/${id}`)
export const viEvents = (id) => request(`${MBVI}/sessions/${id}/events`)
export const viImages = (id) => request(`${MBVI}/sessions/${id}/images`)
export const viObjects = (id, status) => request(`${MBVI}/sessions/${id}/objects${status ? `?status=${status}` : ''}`)
export const viRunImageExtraction = (id) => request(`${MBVI}/sessions/${id}/image-extraction`, { method: 'POST', body: '{}' })
export const viRunImageQuality = (id) => request(`${MBVI}/sessions/${id}/image-quality`, { method: 'POST', body: '{}' })
export const viRunVisionUnderstanding = (id) => request(`${MBVI}/sessions/${id}/vision-understanding`, { method: 'POST', body: '{}' })
export const viRunOcrCrossValidation = (id, datasetText, languageReportStatus) => request(`${MBVI}/sessions/${id}/ocr-cross-validation`, { method: 'POST', body: JSON.stringify({ dataset_text: datasetText || null, language_report_status: languageReportStatus || null }) })
export const viRunCaption = (id, adminCaption) => request(`${MBVI}/sessions/${id}/caption`, { method: 'POST', body: JSON.stringify({ admin_caption: adminCaption || null }) })
export const viRunBoundingBoxPlan = (id) => request(`${MBVI}/sessions/${id}/bounding-box-plan`, { method: 'POST', body: '{}' })
export const viAnnotate = (id, action, objectPublicId, payload) => request(`${MBVI}/sessions/${id}/annotate`, { method: 'POST', body: JSON.stringify({ action, object_public_id: objectPublicId || null, payload: payload || {} }) })
export const viFinishAnnotation = (id) => request(`${MBVI}/sessions/${id}/annotation/finish`, { method: 'POST', body: '{}' })
export const viRunKnowledgeGraph = (id) => request(`${MBVI}/sessions/${id}/knowledge-graph`, { method: 'POST', body: '{}' })
export const viRunQaGeneration = (id) => request(`${MBVI}/sessions/${id}/qa-generation`, { method: 'POST', body: '{}' })
export const viRunDatasetDraft = (id) => request(`${MBVI}/sessions/${id}/dataset-draft`, { method: 'POST', body: '{}' })
export const viRunQualityScore = (id) => request(`${MBVI}/sessions/${id}/quality-score`, { method: 'POST', body: '{}' })
export const viGenerateReport = (id) => request(`${MBVI}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const viAdminReview = (id, decision) => request(`${MBVI}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBVM = '/api/admin/mini-brain/vision-model'
export const vmDiagnostics = () => request(`${MBVM}/diagnostics`)
export const vmProviders = (status) => request(`${MBVM}/providers${status ? `?status=${status}` : ''}`)
export const vmSetProviderStatus = (providerKey, status) => request(`${MBVM}/providers/${providerKey}/status`, { method: 'POST', body: JSON.stringify({ status }) })
export const vmSessions = () => request(`${MBVM}/sessions`)
export const vmCreateSession = (visionSessionPublicId, providerKey, languageSessionPublicId) => request(`${MBVM}/sessions`, { method: 'POST', body: JSON.stringify({ vision_session_public_id: visionSessionPublicId, provider_key: providerKey, language_session_public_id: languageSessionPublicId || null }) })
export const vmSession = (id) => request(`${MBVM}/sessions/${id}`)
export const vmEvents = (id) => request(`${MBVM}/sessions/${id}/events`)
export const vmPredictions = (id, reviewStatus) => request(`${MBVM}/sessions/${id}/predictions${reviewStatus ? `?review_status=${reviewStatus}` : ''}`)
export const vmCorrections = (id) => request(`${MBVM}/sessions/${id}/corrections`)
export const vmLearningMemory = () => request(`${MBVM}/learning-memory`)
export const vmRunImageLoad = (id) => request(`${MBVM}/sessions/${id}/image-load`, { method: 'POST', body: '{}' })
export const vmRunProviderSelection = (id, modelPath, mmprojPath) => request(`${MBVM}/sessions/${id}/provider-selection`, { method: 'POST', body: JSON.stringify({ model_path: modelPath || null, mmproj_path: mmprojPath || null }) })
export const vmRunObjectDetection = (id) => request(`${MBVM}/sessions/${id}/object-detection`, { method: 'POST', body: '{}' })
export const vmRunSceneDetection = (id) => request(`${MBVM}/sessions/${id}/scene-detection`, { method: 'POST', body: '{}' })
export const vmRunCaption = (id) => request(`${MBVM}/sessions/${id}/caption`, { method: 'POST', body: '{}' })
export const vmRunRelationshipDetection = (id) => request(`${MBVM}/sessions/${id}/relationship-detection`, { method: 'POST', body: '{}' })
export const vmRunOcrCrossValidation = (id, datasetText) => request(`${MBVM}/sessions/${id}/ocr-cross-validation`, { method: 'POST', body: JSON.stringify({ dataset_text: datasetText || null }) })
export const vmRunQualityScore = (id) => request(`${MBVM}/sessions/${id}/quality-score`, { method: 'POST', body: '{}' })
export const vmReviewPrediction = (id, action, predictionPublicId, payload) => request(`${MBVM}/sessions/${id}/review`, { method: 'POST', body: JSON.stringify({ action, prediction_public_id: predictionPublicId || null, payload: payload || {} }) })
export const vmFinishReview = (id) => request(`${MBVM}/sessions/${id}/review/finish`, { method: 'POST', body: '{}' })
export const vmRunCorrectionMemory = (id) => request(`${MBVM}/sessions/${id}/correction-memory`, { method: 'POST', body: '{}' })
export const vmRunKnowledgeGraph = (id) => request(`${MBVM}/sessions/${id}/knowledge-graph`, { method: 'POST', body: '{}' })
export const vmRunDatasetDraft = (id) => request(`${MBVM}/sessions/${id}/dataset-draft`, { method: 'POST', body: '{}' })
export const vmGenerateReport = (id) => request(`${MBVM}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const vmAdminReview = (id, decision) => request(`${MBVM}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBMD = '/api/admin/mini-brain/multimodal-dataset-generator'
export const mdDiagnostics = () => request(`${MBMD}/diagnostics`)
export const mdSessions = () => request(`${MBMD}/sessions`)
export const mdCreateSession = (documentSourcePublicId, opts = {}) => request(`${MBMD}/sessions`, { method: 'POST', body: JSON.stringify({ document_source_public_id: documentSourcePublicId, dataset_source_public_id: opts.datasetSourcePublicId || null, language_session_public_id: opts.languageSessionPublicId || null, vision_session_public_id: opts.visionSessionPublicId || null, vision_model_session_public_id: opts.visionModelSessionPublicId || null }) })
export const mdSession = (id) => request(`${MBMD}/sessions/${id}`)
export const mdEvents = (id) => request(`${MBMD}/sessions/${id}/events`)
export const mdRecords = (id, recordType, status) => {
  const params = new URLSearchParams()
  if (recordType) params.set('record_type', recordType)
  if (status) params.set('status', status)
  const qs = params.toString()
  return request(`${MBMD}/sessions/${id}/records${qs ? `?${qs}` : ''}`)
}
export const mdDatasetMemory = () => request(`${MBMD}/dataset-memory`)
export const mdRunCollectSources = (id) => request(`${MBMD}/sessions/${id}/collect-sources`, { method: 'POST', body: '{}' })
export const mdRunCollectText = (id) => request(`${MBMD}/sessions/${id}/collect-text`, { method: 'POST', body: '{}' })
export const mdRunCollectImages = (id) => request(`${MBMD}/sessions/${id}/collect-images`, { method: 'POST', body: '{}' })
export const mdRunMergeMetadata = (id) => request(`${MBMD}/sessions/${id}/merge-metadata`, { method: 'POST', body: '{}' })
export const mdRunConversationBuilder = (id) => request(`${MBMD}/sessions/${id}/conversation-builder`, { method: 'POST', body: '{}' })
export const mdRunInstructionBuilder = (id) => request(`${MBMD}/sessions/${id}/instruction-builder`, { method: 'POST', body: '{}' })
export const mdRunDatasetDraft = (id) => request(`${MBMD}/sessions/${id}/dataset-draft`, { method: 'POST', body: '{}' })
export const mdRunQualityAnalysis = (id) => request(`${MBMD}/sessions/${id}/quality-analysis`, { method: 'POST', body: '{}' })
export const mdRunDuplicateDetection = (id) => request(`${MBMD}/sessions/${id}/duplicate-detection`, { method: 'POST', body: '{}' })
export const mdGenerateReport = (id) => request(`${MBMD}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const mdAdminReview = (id, decision) => request(`${MBMD}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })
export const mdDeleteDraft = (id) => request(`${MBMD}/sessions/${id}/delete-draft`, { method: 'POST', body: '{}' })
export const mdExportDraft = (id, format) => request(`${MBMD}/sessions/${id}/export-draft`, { method: 'POST', body: JSON.stringify({ export_format: format || 'json' }) })
export const mdSplitDataset = (id, recordPublicIds) => request(`${MBMD}/sessions/${id}/split`, { method: 'POST', body: JSON.stringify({ record_public_ids: recordPublicIds }) })
export const mdMergeDatasets = (sessionPublicIds) => request(`${MBMD}/merge`, { method: 'POST', body: JSON.stringify({ session_public_ids: sessionPublicIds }) })

const MBVR = '/api/admin/mini-brain/vision-rag'
export const vrDiagnostics = () => request(`${MBVR}/diagnostics`)
export const vrSessions = () => request(`${MBVR}/sessions`)
export const vrCreateSession = (multimodalDatasetSessionPublicId, query) => request(`${MBVR}/sessions`, { method: 'POST', body: JSON.stringify({ multimodal_dataset_session_public_id: multimodalDatasetSessionPublicId, query }) })
export const vrSession = (id) => request(`${MBVR}/sessions/${id}`)
export const vrEvents = (id) => request(`${MBVR}/sessions/${id}/events`)
export const vrEvidence = (id, evidenceType, status) => {
  const params = new URLSearchParams()
  if (evidenceType) params.set('evidence_type', evidenceType)
  if (status) params.set('status', status)
  const qs = params.toString()
  return request(`${MBVR}/sessions/${id}/evidence${qs ? `?${qs}` : ''}`)
}
export const vrRagMemory = () => request(`${MBVR}/rag-memory`)
export const vrRunTextRetrieval = (id) => request(`${MBVR}/sessions/${id}/text-retrieval`, { method: 'POST', body: '{}' })
export const vrRunOcrRetrieval = (id) => request(`${MBVR}/sessions/${id}/ocr-retrieval`, { method: 'POST', body: '{}' })
export const vrRunImageRetrieval = (id) => request(`${MBVR}/sessions/${id}/image-retrieval`, { method: 'POST', body: '{}' })
export const vrRunObjectRetrieval = (id) => request(`${MBVR}/sessions/${id}/object-retrieval`, { method: 'POST', body: '{}' })
export const vrRunKnowledgeGraphRetrieval = (id) => request(`${MBVR}/sessions/${id}/knowledge-graph-retrieval`, { method: 'POST', body: '{}' })
export const vrRunEvidenceFusion = (id) => request(`${MBVR}/sessions/${id}/evidence-fusion`, { method: 'POST', body: '{}' })
export const vrRunAnswer = (id) => request(`${MBVR}/sessions/${id}/answer`, { method: 'POST', body: '{}' })
export const vrRunQuality = (id) => request(`${MBVR}/sessions/${id}/quality`, { method: 'POST', body: '{}' })
export const vrRunHallucinationCheck = (id) => request(`${MBVR}/sessions/${id}/hallucination-check`, { method: 'POST', body: '{}' })
export const vrGenerateReport = (id) => request(`${MBVR}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const vrCorrect = (id, action, payload) => request(`${MBVR}/sessions/${id}/correct`, { method: 'POST', body: JSON.stringify({ action, payload: payload || {} }) })
export const vrAdminReview = (id, decision) => request(`${MBVR}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBVO = '/api/admin/mini-brain/voice'
export const voDiagnostics = () => request(`${MBVO}/diagnostics`)
export const voSessions = (status, sessionMode) => request(`${MBVO}/sessions?${status ? `status=${status}&` : ''}${sessionMode ? `session_mode=${sessionMode}` : ''}`)
export const voSession = (id) => request(`${MBVO}/sessions/${id}`)
export const voEvents = (sessionId) => request(`${MBVO}/events${sessionId ? `?session_id=${sessionId}` : ''}`)
export const voMemory = () => request(`${MBVO}/memory`)
export const voStatistics = () => request(`${MBVO}/statistics`)
export const voTestStt = (audioBase64) => request(`${MBVO}/test-stt`, { method: 'POST', body: JSON.stringify({ audio_base64: audioBase64 }) })
export const voTestTts = (text) => request(`${MBVO}/test-tts`, { method: 'POST', body: JSON.stringify({ text }) })

const PUBLIC_VO = '/api/public/voice'
export const voPublicCreateSession = (explicitConsent, languageOverride) => request(`${PUBLIC_VO}/sessions`, { method: 'POST', body: JSON.stringify({ session_mode: 'public_chat', explicit_consent: !!explicitConsent, language_override: languageOverride || 'auto' }) })
export const voPublicSendChunk = (id, sequence, audioBase64) => request(`${PUBLIC_VO}/sessions/${id}/chunks`, { method: 'POST', body: JSON.stringify({ sequence, audio_base64: audioBase64 }) })
export const voPublicFinishSession = (id) => request(`${PUBLIC_VO}/sessions/${id}/finish`, { method: 'POST', body: '{}' })

const MBPS = '/api/admin/mini-brain/provider-settings'
export const psDiagnostics = () => request(`${MBPS}/diagnostics`)
export const psProviders = (providerType, enabled) => request(`${MBPS}/providers?${providerType ? `provider_type=${providerType}&` : ''}${enabled !== undefined && enabled !== null ? `enabled=${enabled}` : ''}`)
export const psCreateProvider = (providerKey, enabled, config) => request(`${MBPS}/providers`, { method: 'POST', body: JSON.stringify({ provider_key: providerKey, enabled: !!enabled, config: config || {} }) })
export const psUpdateProvider = (id, config) => request(`${MBPS}/providers/${id}`, { method: 'PATCH', body: JSON.stringify({ config }) })
export const psEnableProvider = (id) => request(`${MBPS}/providers/${id}/enable`, { method: 'POST', body: '{}' })
export const psDisableProvider = (id) => request(`${MBPS}/providers/${id}/disable`, { method: 'POST', body: '{}' })
export const psSetSecret = (id, secretName, value) => request(`${MBPS}/providers/${id}/secrets`, { method: 'POST', body: JSON.stringify({ secret_name: secretName, value }) })
export const psDeleteSecret = (id, secretName) => request(`${MBPS}/providers/${id}/secrets/${secretName}`, { method: 'DELETE' })
export const psTestConnection = (id, secretName, timeoutSeconds) => request(`${MBPS}/providers/${id}/test`, { method: 'POST', body: JSON.stringify({ secret_name: secretName || 'api_key', timeout_seconds: timeoutSeconds || 10 }) })
export const psProviderAudit = (id) => request(`${MBPS}/providers/${id}/audit`)
export const psArchiveProvider = (id) => request(`${MBPS}/providers/${id}/archive`, { method: 'POST', body: '{}' })
export const psMemory = () => request(`${MBPS}/memory`)

const MBLR = '/api/admin/mini-brain/llm-runtime'
export const lrDiagnostics = () => request(`${MBLR}/diagnostics`)
// MB-45: single source of truth for the Admin Assistant widget's health
// banner -- reads the same runtime-resolution state used by /chat and
// /grounded-chat, replacing the old Phase-8 assistantHealth() call that
// checked an unrelated Phase-15 inference assignment.
export const miniBrainWidgetHealth = () => request(`${MBLR}/widget-health`)
export const lrSessions = (status) => request(`${MBLR}/sessions${status ? `?status=${status}` : ''}`)
export const lrSession = (id) => request(`${MBLR}/sessions/${id}`)
export const lrMessages = (id) => request(`${MBLR}/sessions/${id}/messages`)
export const lrDeleteSession = (id) => request(`${MBLR}/sessions/${id}`, { method: 'DELETE' })
export const lrChat = (sessionId, message) => request(`${MBLR}/chat`, { method: 'POST', body: JSON.stringify({ session_id: sessionId || null, message }) })
// MB-37: grounded chat -- retrieves RAG evidence via an existing retrieval profile and
// injects it into the same local Mini Brain runtime `/chat` already uses.
export const sendMiniBrainGroundedMessage = (sessionId, message, retrievalProfilePublicId, topK = 4) => request(`${MBLR}/grounded-chat`, { method: 'POST', body: JSON.stringify({ session_id: sessionId || null, message, retrieval_profile_public_id: retrievalProfilePublicId || null, top_k: topK }), timeoutMs: 120_000 })
// MB-42: read-only lookup used by the floating widget's "Use knowledge base" toggle.
// MB-48: cache-busting query param -- this is called from multiple
// independently-mounted components (the widget, the RAG page) that can
// legitimately overlap in time; without it, the browser's own GET
// request-coalescing (a connection-layer optimization, unaffected by
// `cache: 'no-store'`) can silently serve one caller the *other*
// caller's still-in-flight, pre-switch response for this exact URL --
// confirmed directly via network-timing captured during
// e2e/tests/10-grounded-chat.spec.js.
export const miniBrainDefaultRetrievalProfile = () => request(`${MBLR}/grounded-chat/default-retrieval-profile?_=${Date.now()}`)
// MB-43: admin-chosen default grounded-chat retrieval profile.
export const miniBrainSetDefaultRetrievalProfile = (retrievalProfilePublicId) => request(`${MBLR}/grounded-chat/default-retrieval-profile`, { method: 'POST', body: JSON.stringify({ retrieval_profile_public_id: retrievalProfilePublicId }) })
export const lrExplainPage = (sessionId, pageId, navKey) => request(`${MBLR}/explain-page`, { method: 'POST', body: JSON.stringify({ session_id: sessionId || null, page_id: pageId || null, nav_key: navKey || null }) })
export const lrSummarizeReport = (sessionId, report) => request(`${MBLR}/summarize-report`, { method: 'POST', body: JSON.stringify({ session_id: sessionId || null, report: report || {} }) })
export const lrSummarizeRegression = (sessionId, regressionResult) => request(`${MBLR}/summarize-regression`, { method: 'POST', body: JSON.stringify({ session_id: sessionId || null, regression_result: regressionResult || {} }) })
export const lrExplainError = (sessionId, errorMessage) => request(`${MBLR}/explain-error`, { method: 'POST', body: JSON.stringify({ session_id: sessionId || null, error_message: errorMessage }) })
export const lrNextActions = (sessionId, statusSnapshot) => request(`${MBLR}/next-actions`, { method: 'POST', body: JSON.stringify({ session_id: sessionId || null, status_snapshot: statusSnapshot || {} }) })

// MB-04A: Prompt & Context Optimization. MB-47: real, tested backend
// with zero UI surface until now.
const MBPO = '/api/admin/mini-brain/prompt-optimization'
export const promptLanguageDetect = (question) => request(`${MBPO}/language-detect`, { method: 'POST', body: JSON.stringify({ question }) })
export const promptTemplates = () => request(`${MBPO}/templates`)
// MB-48: client-side timeout always exceeds the backend's own configured
// timeout_seconds (+30s headroom for network/queueing), so the client
// never gives up before the backend legitimately would.
export const promptGenerate = (question, { maxTokens, timeoutSeconds, knowledgeBudgetChars } = {}) => request(`${MBPO}/generate`, { method: 'POST', body: JSON.stringify({ question, max_tokens: maxTokens || 256, timeout_seconds: timeoutSeconds || 90.0, knowledge_budget_chars: knowledgeBudgetChars || 900 }), timeoutMs: ((timeoutSeconds || 90.0) * 1000) + 30_000 })
export const promptCompare = (question, { maxTokens, timeoutSeconds, knowledgeBudgetChars } = {}) => request(`${MBPO}/compare`, { method: 'POST', body: JSON.stringify({ question, max_tokens: maxTokens || 256, timeout_seconds: timeoutSeconds || 90.0, knowledge_budget_chars: knowledgeBudgetChars || 900 }), timeoutMs: ((timeoutSeconds || 90.0) * 2 * 1000) + 30_000 })

const MBLC = '/api/admin/mini-brain/local-setup'
export const lcHardware = () => request(`${MBLC}/hardware`)
export const lcScanModels = () => request(`${MBLC}/scan-models`)
export const lcRecommendations = () => request(`${MBLC}/recommendations`)
export const lcSaveLocalModel = (modelPath, contextLength, maxTokens, temperature, threads, additionalModelDirs) => request(`${MBLC}/save-local-model`, { method: 'POST', body: JSON.stringify({ model_path: modelPath || null, context_length: Number(contextLength) || 2048, max_tokens: Number(maxTokens) || 512, temperature: Number(temperature), threads: Number(threads) || 4, additional_model_dirs: additionalModelDirs || null }) })
export const lcSaveProvider = (providerKey, apiKey, model, enabled) => request(`${MBLC}/save-provider`, { method: 'POST', body: JSON.stringify({ provider_key: providerKey, api_key: apiKey || null, model: model || null, enabled: !!enabled }) })
export const lcProvidersCatalog = () => request(`${MBLC}/providers/catalog`)
export const lcSetupGuide = () => request(`${MBLC}/setup-guide`)
export const lcDiagnostics = () => request(`${MBLC}/diagnostics`)

const MBRM = '/api/admin/mini-brain/runtime-manager'
export const rmHardware = () => request(`${MBRM}/hardware`)
export const rmCatalog = () => request(`${MBRM}/catalog`)
export const rmInstalled = () => request(`${MBRM}/installed`)
export const rmStatus = () => request(`${MBRM}/status`)
export const rmRecommendation = () => request(`${MBRM}/recommendation`)
export const rmDownload = (modelId) => request(`${MBRM}/download`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) })
export const rmVerify = (modelId) => request(`${MBRM}/verify`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) })
export const rmInstall = (modelId) => request(`${MBRM}/install`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) })
export const rmLoad = (modelId, contextLength, maxTokens, temperature, threads) => request(`${MBRM}/load`, { method: 'POST', body: JSON.stringify({ model_id: modelId, context_length: Number(contextLength) || 2048, max_tokens: Number(maxTokens) || 512, temperature: Number(temperature), threads: Number(threads) || 4 }) })
export const rmUnload = () => request(`${MBRM}/unload`, { method: 'POST', body: '{}' })
export const rmBenchmark = (modelId, prompt) => request(`${MBRM}/benchmark`, { method: 'POST', body: JSON.stringify({ model_id: modelId, prompt: prompt || 'Say hello in one short sentence.' }) })
export const rmRemove = (modelId) => request(`${MBRM}/remove`, { method: 'POST', body: JSON.stringify({ model_id: modelId }) })
export const rmEvents = () => request(`${MBRM}/events`)
export const rmMemory = () => request(`${MBRM}/memory`)

const MBTP = '/api/admin/mini-brain/training-pipeline'
export const tpDiagnostics = () => request(`${MBTP}/diagnostics`)
export const tpSessions = () => request(`${MBTP}/sessions`)
export const tpCreateSession = (topic) => request(`${MBTP}/sessions`, { method: 'POST', body: JSON.stringify({ topic }) })
export const tpSession = (id) => request(`${MBTP}/sessions/${id}`)
export const tpEvents = (id) => request(`${MBTP}/sessions/${id}/events`)
export const tpPackages = (id) => request(`${MBTP}/sessions/${id}/packages`)
export const tpPackageMetadata = (packageId) => request(`${MBTP}/packages/${packageId}`)
export const tpMemory = () => request(`${MBTP}/memory`)
export const tpRagMemory = () => request(`${MBTP}/rag-memory`)
export const tpRunCollectDatasets = (id, datasetSessionPublicIds) => request(`${MBTP}/sessions/${id}/collect-datasets`, { method: 'POST', body: JSON.stringify({ dataset_session_public_ids: datasetSessionPublicIds }) })
export const tpRunCollectRagMemory = (id, ragSessionPublicIds) => request(`${MBTP}/sessions/${id}/collect-rag-memory`, { method: 'POST', body: JSON.stringify({ rag_session_public_ids: ragSessionPublicIds || [] }) })
export const tpRunAnalyzeLanguage = (id) => request(`${MBTP}/sessions/${id}/analyze-language`, { method: 'POST', body: '{}' })
export const tpRunAnalyzeVision = (id) => request(`${MBTP}/sessions/${id}/analyze-vision`, { method: 'POST', body: '{}' })
export const tpRunAnalyzeTokenizer = (id) => request(`${MBTP}/sessions/${id}/analyze-tokenizer`, { method: 'POST', body: '{}' })
export const tpRunPlanSplits = (id, seed) => request(`${MBTP}/sessions/${id}/plan-splits`, { method: 'POST', body: JSON.stringify({ seed: seed ?? null }) })
export const tpRunPlanCurriculum = (id) => request(`${MBTP}/sessions/${id}/plan-curriculum`, { method: 'POST', body: '{}' })
export const tpRunEstimateHardware = (id) => request(`${MBTP}/sessions/${id}/estimate-hardware`, { method: 'POST', body: '{}' })
export const tpRunBuildPackage = (id) => request(`${MBTP}/sessions/${id}/build-package`, { method: 'POST', body: '{}' })
export const tpGenerateReport = (id) => request(`${MBTP}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const tpAdminReview = (id, decision) => request(`${MBTP}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBEC = '/api/admin/mini-brain/evaluation-center'
export const ecDiagnostics = () => request(`${MBEC}/diagnostics`)
export const ecSessions = () => request(`${MBEC}/sessions`)
export const ecCreateSession = (topic) => request(`${MBEC}/sessions`, { method: 'POST', body: JSON.stringify({ topic }) })
export const ecSession = (id) => request(`${MBEC}/sessions/${id}`)
export const ecEvents = (id) => request(`${MBEC}/sessions/${id}/events`)
export const ecResults = (id, category) => request(`${MBEC}/sessions/${id}/results${category ? `?category=${category}` : ''}`)
export const ecExports = (id) => request(`${MBEC}/sessions/${id}/exports`)
export const ecMemory = () => request(`${MBEC}/memory`)
export const ecRunCollectDatasets = (id, datasetSessionPublicIds) => request(`${MBEC}/sessions/${id}/collect-datasets`, { method: 'POST', body: JSON.stringify({ dataset_session_public_ids: datasetSessionPublicIds }) })
export const ecRunCollectRagSessions = (id, ragSessionPublicIds) => request(`${MBEC}/sessions/${id}/collect-rag-sessions`, { method: 'POST', body: JSON.stringify({ rag_session_public_ids: ragSessionPublicIds || [] }) })
export const ecRunCollectTrainingPackages = (id, trainingPackageSessionPublicIds) => request(`${MBEC}/sessions/${id}/collect-training-packages`, { method: 'POST', body: JSON.stringify({ training_package_session_public_ids: trainingPackageSessionPublicIds || [] }) })
export const ecRunLanguageBenchmarks = (id) => request(`${MBEC}/sessions/${id}/language-benchmarks`, { method: 'POST', body: '{}' })
export const ecRunOcrBenchmarks = (id) => request(`${MBEC}/sessions/${id}/ocr-benchmarks`, { method: 'POST', body: '{}' })
export const ecRunGroundingRetrievalBenchmarks = (id) => request(`${MBEC}/sessions/${id}/grounding-retrieval-benchmarks`, { method: 'POST', body: '{}' })
export const ecRunMultimodalBenchmarks = (id) => request(`${MBEC}/sessions/${id}/multimodal-benchmarks`, { method: 'POST', body: '{}' })
export const ecRunPackageBenchmarks = (id) => request(`${MBEC}/sessions/${id}/package-benchmarks`, { method: 'POST', body: '{}' })
export const ecRunRegression = (id, baselineSessionPublicId) => request(`${MBEC}/sessions/${id}/regression`, { method: 'POST', body: JSON.stringify({ baseline_session_public_id: baselineSessionPublicId || null }) })
export const ecGenerateReport = (id) => request(`${MBEC}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const ecAdminReview = (id, decision) => request(`${MBEC}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBRG = '/api/admin/mini-brain/release-governance'
export const rgDiagnostics = () => request(`${MBRG}/diagnostics`)
export const rgSessions = () => request(`${MBRG}/sessions`)
export const rgCreateSession = (topic) => request(`${MBRG}/sessions`, { method: 'POST', body: JSON.stringify({ topic }) })
export const rgSession = (id) => request(`${MBRG}/sessions/${id}`)
export const rgEvents = (id) => request(`${MBRG}/sessions/${id}/events`)
export const rgArtifacts = (id) => request(`${MBRG}/sessions/${id}/artifacts`)
export const rgMemory = () => request(`${MBRG}/memory`)
export const rgRunCollectDatasets = (id, datasetSessionPublicIds) => request(`${MBRG}/sessions/${id}/collect-datasets`, { method: 'POST', body: JSON.stringify({ dataset_session_public_ids: datasetSessionPublicIds }) })
export const rgRunCollectRag = (id, ragSessionPublicIds) => request(`${MBRG}/sessions/${id}/collect-rag`, { method: 'POST', body: JSON.stringify({ rag_session_public_ids: ragSessionPublicIds || [] }) })
export const rgRunCollectPackage = (id, trainingPackageSessionPublicId) => request(`${MBRG}/sessions/${id}/collect-package`, { method: 'POST', body: JSON.stringify({ training_package_session_public_id: trainingPackageSessionPublicId }) })
export const rgRunCollectEvaluation = (id, evaluationSessionPublicId) => request(`${MBRG}/sessions/${id}/collect-evaluation`, { method: 'POST', body: JSON.stringify({ evaluation_session_public_id: evaluationSessionPublicId }) })
export const rgRunSafety = (id) => request(`${MBRG}/sessions/${id}/run-safety`, { method: 'POST', body: '{}' })
export const rgRunCompliance = (id) => request(`${MBRG}/sessions/${id}/run-compliance`, { method: 'POST', body: '{}' })
export const rgRunBenchmarks = (id) => request(`${MBRG}/sessions/${id}/run-benchmarks`, { method: 'POST', body: '{}' })
export const rgBuildRiskRollback = (id) => request(`${MBRG}/sessions/${id}/build-risk-rollback`, { method: 'POST', body: '{}' })
export const rgBuildPackage = (id) => request(`${MBRG}/sessions/${id}/build-package`, { method: 'POST', body: '{}' })
export const rgGenerateReport = (id) => request(`${MBRG}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const rgAdminReview = (id, decision) => request(`${MBRG}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })

const MBGA = '/api/admin/mini-brain/external-ai-gateway'
export const gaDiagnostics = () => request(`${MBGA}/diagnostics`)
export const gaSessions = () => request(`${MBGA}/sessions`)
export const gaCreateSession = (topic, purpose, datasetSessionPublicIds, ragSessionPublicId) => request(`${MBGA}/sessions`, { method: 'POST', body: JSON.stringify({ topic, purpose, dataset_session_public_ids: datasetSessionPublicIds || [], rag_session_public_id: ragSessionPublicId || null }) })
export const gaSession = (id) => request(`${MBGA}/sessions/${id}`)
export const gaEvents = (id) => request(`${MBGA}/sessions/${id}/events`)
export const gaProviderRuns = (id) => request(`${MBGA}/sessions/${id}/provider-runs`)
export const gaMemory = () => request(`${MBGA}/memory`)
export const gaAuthorize = (id, authorizationNote) => request(`${MBGA}/sessions/${id}/authorize`, { method: 'POST', body: JSON.stringify({ authorization_note: authorizationNote }) })
export const gaSanitize = (id, adminStatedNeed) => request(`${MBGA}/sessions/${id}/sanitize`, { method: 'POST', body: JSON.stringify({ admin_stated_need: adminStatedNeed || '' }) })
export const gaSelectProviders = (id, requestedProviderKeys) => request(`${MBGA}/sessions/${id}/select-providers`, { method: 'POST', body: JSON.stringify({ requested_provider_keys: requestedProviderKeys }) })
export const gaDispatch = (id, timeoutSeconds, retainRawResponses) => request(`${MBGA}/sessions/${id}/dispatch`, { method: 'POST', body: JSON.stringify({ timeout_seconds: timeoutSeconds || 30.0, retain_raw_responses: !!retainRawResponses }) })
export const gaCollect = (id) => request(`${MBGA}/sessions/${id}/collect`, { method: 'POST', body: '{}' })
export const gaNormalize = (id) => request(`${MBGA}/sessions/${id}/normalize`, { method: 'POST', body: '{}' })
export const gaAnalyze = (id) => request(`${MBGA}/sessions/${id}/analyze`, { method: 'POST', body: '{}' })
export const gaBuildEvidence = (id) => request(`${MBGA}/sessions/${id}/build-evidence`, { method: 'POST', body: '{}' })
export const gaGenerateReport = (id) => request(`${MBGA}/sessions/${id}/report`, { method: 'POST', body: '{}' })
export const gaAdminReview = (id, decision) => request(`${MBGA}/sessions/${id}/admin-review`, { method: 'POST', body: JSON.stringify({ decision }) })
export const gaArchive = (id) => request(`${MBGA}/sessions/${id}/archive`, { method: 'POST', body: '{}' })

// MB-40/41: exports an admin_accepted External AI Gateway session into
// Dataset Studio, and (opt-in) on into a RAG knowledge space + index in
// the same call. MB-47: this was the one real, tested route (18+10
// passing tests) with zero api.js binding until now.
const MBEGDB = '/api/admin/mini-brain/external-ai-gateway-dataset-bridge'
export const egdbExportToDataset = (sessionId, payload) => request(`${MBEGDB}/sessions/${sessionId}/export-to-dataset`, { method: 'POST', body: JSON.stringify(payload), timeoutMs: 60_000 })

const MBTE = '/api/admin/mini-brain/training-engine'
export const teDiagnostics = () => request(`${MBTE}/diagnostics`)
export const teJobs = () => request(`${MBTE}/jobs`)
export const teCreateJob = (topic, trainingPackageSessionPublicId, releaseGovernanceSessionPublicId, executionMode) => request(`${MBTE}/jobs`, { method: 'POST', body: JSON.stringify({ topic, training_package_session_public_id: trainingPackageSessionPublicId, release_governance_session_public_id: releaseGovernanceSessionPublicId, execution_mode: executionMode || 'simulation' }) })
export const teJob = (id) => request(`${MBTE}/jobs/${id}`)
export const teEvents = (id) => request(`${MBTE}/jobs/${id}/events`)
export const teCheckpoints = (id) => request(`${MBTE}/jobs/${id}/checkpoints`)
export const teMetrics = (id) => request(`${MBTE}/jobs/${id}/metrics`)
export const teAudit = (id) => request(`${MBTE}/jobs/${id}/audit`)
export const teMemory = () => request(`${MBTE}/memory`)
export const teValidateRelease = (id) => request(`${MBTE}/jobs/${id}/validate-release`, { method: 'POST', body: '{}' })
export const teValidatePackage = (id) => request(`${MBTE}/jobs/${id}/validate-package`, { method: 'POST', body: '{}' })
export const teAuthorize = (id, authorizationReason) => request(`${MBTE}/jobs/${id}/authorize`, { method: 'POST', body: JSON.stringify({ authorization_reason: authorizationReason }) })
export const tePlanResources = (id) => request(`${MBTE}/jobs/${id}/plan-resources`, { method: 'POST', body: '{}' })
export const teBuildManifest = (id) => request(`${MBTE}/jobs/${id}/build-manifest`, { method: 'POST', body: '{}' })
export const teReserveRuntime = (id) => request(`${MBTE}/jobs/${id}/reserve-runtime`, { method: 'POST', body: '{}' })
export const teStart = (id) => request(`${MBTE}/jobs/${id}/start`, { method: 'POST', body: '{}' })
export const teStreamMetric = (id, step, epoch) => request(`${MBTE}/jobs/${id}/metrics`, { method: 'POST', body: JSON.stringify({ step, epoch }) })
export const teSaveCheckpoint = (id, step, epoch) => request(`${MBTE}/jobs/${id}/checkpoints`, { method: 'POST', body: JSON.stringify({ step, epoch }) })
export const tePause = (id) => request(`${MBTE}/jobs/${id}/pause`, { method: 'POST', body: '{}' })
export const teResume = (id) => request(`${MBTE}/jobs/${id}/resume`, { method: 'POST', body: '{}' })
export const teCancel = (id) => request(`${MBTE}/jobs/${id}/cancel`, { method: 'POST', body: '{}' })
export const teFinalize = (id) => request(`${MBTE}/jobs/${id}/finalize`, { method: 'POST', body: '{}' })
export const teGenerateReport = (id) => request(`${MBTE}/jobs/${id}/report`, { method: 'POST', body: '{}' })
export const teArchive = (id) => request(`${MBTE}/jobs/${id}/archive`, { method: 'POST', body: '{}' })

const MBPCR = '/api/admin/mini-brain/public-chat'
export const pcrDiagnostics = () => request(`${MBPCR}/diagnostics`)
export const pcrSessions = (status) => request(`${MBPCR}/sessions${status ? `?status=${status}` : ''}`)
export const pcrSession = (id) => request(`${MBPCR}/sessions/${id}`)
export const pcrMessages = (id) => request(`${MBPCR}/sessions/${id}/messages`)
export const pcrSignals = (id) => request(`${MBPCR}/sessions/${id}/signals`)
export const pcrSessionEvents = (id) => request(`${MBPCR}/sessions/${id}/events`)
export const pcrClusters = () => request(`${MBPCR}/clusters`)
export const pcrGenerateCandidates = (minimumFrequency) => request(`${MBPCR}/candidates/generate`, { method: 'POST', body: JSON.stringify({ minimum_frequency: minimumFrequency || 2 }) })
export const pcrCandidates = (status) => request(`${MBPCR}/candidates${status ? `?status=${status}` : ''}`)
export const pcrCandidate = (id) => request(`${MBPCR}/candidates/${id}`)
export const pcrCandidateEvents = (id) => request(`${MBPCR}/candidates/${id}/events`)
export const pcrReviewCandidate = (id, decision, notes) => request(`${MBPCR}/candidates/${id}/review`, { method: 'POST', body: JSON.stringify({ decision, notes: notes || null }) })
export const pcrAnalytics = () => request(`${MBPCR}/analytics`)
export const pcrExportAnalytics = () => request(`${MBPCR}/exports/analytics`)
export const pcrExportCandidates = (status) => request(`${MBPCR}/exports/candidates${status ? `?status=${status}` : ''}`)

const PUBLIC_PC = '/api/public/chat'
export const pcrStartSession = (language) => request(`${PUBLIC_PC}/sessions`, { method: 'POST', body: JSON.stringify({ language: language || 'auto' }) })
export const pcrSendMessage = (id, message) => request(`${PUBLIC_PC}/sessions/${id}/messages`, { method: 'POST', body: JSON.stringify({ message }) })
export const pcrSubmitFeedback = (id, satisfactionRating, comment) => request(`${PUBLIC_PC}/sessions/${id}/feedback`, { method: 'POST', body: JSON.stringify({ satisfaction_rating: satisfactionRating ?? null, comment: comment || null }) })
export const pcrEndSession = (id) => request(`${PUBLIC_PC}/sessions/${id}/end`, { method: 'POST', body: '{}' })

const MBPG = '/api/admin/mini-brain/plugin-governance'
export const pgDiagnostics = () => request(`${MBPG}/diagnostics`)
export const pgPlugins = (status) => request(`${MBPG}/plugins${status ? `?status=${status}` : ''}`)
export const pgPlugin = (id) => request(`${MBPG}/plugins/${id}`)
export const pgRegisterPlugin = (manifest, source) => request(`${MBPG}/plugins`, { method: 'POST', body: JSON.stringify({ manifest, source: source || 'manual_upload' }) })
export const pgValidateManifest = (id) => request(`${MBPG}/plugins/${id}/validate`, { method: 'POST', body: '{}' })
export const pgClassifyCapabilities = (id) => request(`${MBPG}/plugins/${id}/classify`, { method: 'POST', body: '{}' })
export const pgComputeRiskScore = (id) => request(`${MBPG}/plugins/${id}/risk-score`, { method: 'POST', body: '{}' })
export const pgBuildSandboxProfile = (id) => request(`${MBPG}/plugins/${id}/sandbox-profile`, { method: 'POST', body: '{}' })
export const pgBuildFilesystemPolicy = (id) => request(`${MBPG}/plugins/${id}/filesystem-policy`, { method: 'POST', body: '{}' })
export const pgBuildNetworkPolicy = (id) => request(`${MBPG}/plugins/${id}/network-policy`, { method: 'POST', body: '{}' })
export const pgEnablePlugin = (id) => request(`${MBPG}/plugins/${id}/enable`, { method: 'POST', body: '{}' })
export const pgEvaluatePermission = (id, scopeKey, isPublicChat, userIdHash) => request(`${MBPG}/plugins/${id}/evaluate-permission`, { method: 'POST', body: JSON.stringify({ scope_key: scopeKey, is_public_chat: !!isPublicChat, user_id_hash: userIdHash || null }) })
export const pgRequestConsent = (id, scopeKey, rawUserIdentity, consentGiven, ttlSeconds) => request(`${MBPG}/plugins/${id}/request-consent`, { method: 'POST', body: JSON.stringify({ scope_key: scopeKey, raw_user_identity: rawUserIdentity, consent_given: !!consentGiven, ttl_seconds: ttlSeconds ?? null }) })
export const pgGrantPermission = (id, scopeKey, userIdHash) => request(`${MBPG}/plugins/${id}/grant-permission`, { method: 'POST', body: JSON.stringify({ scope_key: scopeKey, user_id_hash: userIdHash || null }) })
export const pgRevokePermission = (id, scopeKey) => request(`${MBPG}/plugins/${id}/revoke-permission`, { method: 'POST', body: JSON.stringify({ scope_key: scopeKey }) })
export const pgIssueToken = (id, scopeKeys, rawUserIdentity, rawSessionIdentity, ttlSeconds) => request(`${MBPG}/plugins/${id}/issue-token`, { method: 'POST', body: JSON.stringify({ scope_keys: scopeKeys, raw_user_identity: rawUserIdentity, raw_session_identity: rawSessionIdentity, ttl_seconds: ttlSeconds || 300 }) })
export const pgRuntimeEvent = (id, eventType, message, metadata) => request(`${MBPG}/plugins/${id}/runtime-event`, { method: 'POST', body: JSON.stringify({ event_type: eventType, message: message || '', metadata: metadata || {} }) })
export const pgGenerateReport = (id) => request(`${MBPG}/plugins/${id}/report`, { method: 'POST', body: '{}' })
export const pgDisablePlugin = (id) => request(`${MBPG}/plugins/${id}/disable`, { method: 'POST', body: '{}' })
export const pgArchivePlugin = (id) => request(`${MBPG}/plugins/${id}/archive`, { method: 'POST', body: '{}' })
export const pgEvents = (id) => request(`${MBPG}/plugins/${id}/events`)
export const pgConsents = (id) => request(`${MBPG}/plugins/${id}/consents`)
export const pgPermissions = (id) => request(`${MBPG}/plugins/${id}/permissions`)
export const pgMemory = () => request(`${MBPG}/memory`)

const PUBLIC_PG = '/api/public/plugin-policy'
export const pgCheckPolicy = (pluginId, scopeKey) => request(`${PUBLIC_PG}/check?plugin_id=${encodeURIComponent(pluginId)}&scope_key=${encodeURIComponent(scopeKey)}`)

const MBPR = '/api/admin/mini-brain/plugin-runtime'
export const prDiagnostics = () => request(`${MBPR}/diagnostics`)
export const prExecute = (pluginPublicId, scopeKey, argumentsObj, executionToken, timeoutSeconds) => request(`${MBPR}/execute`, { method: 'POST', body: JSON.stringify({ plugin_public_id: pluginPublicId, scope_key: scopeKey, arguments: argumentsObj || {}, execution_token: executionToken, timeout_seconds: timeoutSeconds || 5.0 }) })
export const prExecutions = (status, pluginPublicId) => request(`${MBPR}/executions?${status ? `status=${status}&` : ''}${pluginPublicId ? `plugin_public_id=${pluginPublicId}` : ''}`)
export const prExecution = (id) => request(`${MBPR}/executions/${id}`)
export const prExecutionLogs = (id) => request(`${MBPR}/executions/${id}/logs`)
export const prGenerateReport = (id) => request(`${MBPR}/executions/${id}/report`, { method: 'POST', body: '{}' })
export const prCancelExecution = (id) => request(`${MBPR}/executions/${id}/cancel`, { method: 'POST', body: '{}' })
export const prArchiveExecution = (id) => request(`${MBPR}/executions/${id}/archive`, { method: 'POST', body: '{}' })
export const prRuntimeEvent = (id, eventType, message, metadata) => request(`${MBPR}/executions/${id}/runtime-event`, { method: 'POST', body: JSON.stringify({ event_type: eventType, message: message || '', metadata: metadata || {} }) })
export const prMemory = () => request(`${MBPR}/memory`)
export const prStatistics = () => request(`${MBPR}/statistics`)

const PUBLIC_PR = '/api/public/plugin-runtime'
export const prPublicExecute = (pluginPublicId, scopeKey, argumentsObj, rawUserIdentity, executionToken) => request(`${PUBLIC_PR}/execute`, { method: 'POST', body: JSON.stringify({ plugin_public_id: pluginPublicId, scope_key: scopeKey, arguments: argumentsObj || {}, raw_user_identity: rawUserIdentity, execution_token: executionToken }) })
