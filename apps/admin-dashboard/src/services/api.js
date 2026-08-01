const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
let csrfToken = null
let csrfHeaderName = 'X-CSRF-Token'

async function request(path, options = {}) {
  const headers = { ...(options.headers ?? {}) }
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  if (options.method && options.method !== 'GET') {
    if (!csrfToken) await getCsrf()
    headers[csrfHeaderName] = csrfToken
  }
  const response = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...options, headers })
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
export const documentSftExport = (id, exportId) => request(`${DOC(id)}/sft-export/${exportId}`)
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
export const pretrainingEstimate = (body) => request('/api/admin/pretraining/estimate', { method: 'POST', body: JSON.stringify(body) })
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
export const patchEvalSuite = (id, body) => request(`/api/admin/model-evaluation/suites/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
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
export const ragSpace = (id) => request(`${RAG}/spaces/${id}`)
export const patchRagSpace = (id, body) => request(`${RAG}/spaces/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const ragSources = (spaceId) => request(`${RAG}/spaces/${spaceId}/sources`)
export const createRagSource = (spaceId, body) => request(`${RAG}/spaces/${spaceId}/sources`, { method: 'POST', body: JSON.stringify(body) })
export const ragSource = (id) => request(`${RAG}/sources/${id}`)
export const patchRagSource = (id, body) => request(`${RAG}/sources/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const ragSourceVersions = (sourceId) => request(`${RAG}/sources/${sourceId}/versions`)
export const createRagSourceVersion = (sourceId) => request(`${RAG}/sources/${sourceId}/versions`, { method: 'POST' })
export const ragSourceVersion = (id) => request(`${RAG}/versions/${id}`)
export const validateRagSourceVersion = (id) => request(`${RAG}/versions/${id}/validate`, { method: 'POST' })
export const ragChunkSets = (versionId) => request(`${RAG}/versions/${versionId}/chunk-sets`)
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
export const ragRetrievalProfile = (id) => request(`${RAG}/retrieval-profiles/${id}`)
export const patchRagRetrievalProfile = (id, body) => request(`${RAG}/retrieval-profiles/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const validateRagRetrievalProfile = (id) => request(`${RAG}/retrieval-profiles/${id}/validate`, { method: 'POST' })
export const activateRagRetrievalProfile = (id) => request(`${RAG}/retrieval-profiles/${id}/activate`, { method: 'POST' })
export const ragRetrieve = (body) => request(`${RAG}/retrieve`, { method: 'POST', body: JSON.stringify(body) })
export const ragRetrievalRun = (id) => request(`${RAG}/retrieval-runs/${id}`)
export const ragRetrievalResults = (id) => request(`${RAG}/retrieval-runs/${id}/results`)
export const ragGroundedAnswer = (body) => request(`${RAG}/grounded-answer`, { method: 'POST', body: JSON.stringify(body) })
export const ragGroundedRequest = (id) => request(`${RAG}/grounded-requests/${id}`)
export const ragGroundedAnswerResult = (id) => request(`${RAG}/grounded-requests/${id}/answer`)
export const ragGroundedCitations = (id) => request(`${RAG}/grounded-requests/${id}/citations`)
export const ragGroundedIssues = (id) => request(`${RAG}/grounded-requests/${id}/issues`)
export const createRagChatLabSession = (body) => request(`${RAG}/chat-lab/sessions`, { method: 'POST', body: JSON.stringify(body) })
export const ragChatLabSession = (id) => request(`${RAG}/chat-lab/sessions/${id}`)
export const postRagChatLabMessage = (id, message, retrievalProfilePublicId) => request(`${RAG}/chat-lab/sessions/${id}/messages`, { method: 'POST', body: JSON.stringify({ message, retrieval_profile_public_id: retrievalProfilePublicId }) })
export const closeRagChatLabSession = (id) => request(`${RAG}/chat-lab/sessions/${id}/close`, { method: 'POST' })
export const ragEvaluationSuites = () => request(`${RAG}/evaluation-suites`)
export const createRagEvaluationSuite = (spaceId, body) => request(`${RAG}/spaces/${spaceId}/evaluation-suites`, { method: 'POST', body: JSON.stringify(body) })
export const ragEvaluationSuite = (id) => request(`${RAG}/evaluation-suites/${id}`)
export const addRagEvaluationFixture = (suiteId, body) => request(`${RAG}/evaluation-suites/${suiteId}/fixtures`, { method: 'POST', body: JSON.stringify(body) })
export const createRagEvaluationRun = (suiteId, body) => request(`${RAG}/evaluation-suites/${suiteId}/runs`, { method: 'POST', body: JSON.stringify(body) })
export const ragEvaluationRun = (id) => request(`${RAG}/evaluation-runs/${id}`)
export const executeRagEvaluationRun = (id) => request(`${RAG}/evaluation-runs/${id}/execute`, { method: 'POST' })
export const ragEvaluationMetrics = (id) => request(`${RAG}/evaluation-runs/${id}/metrics`)
export const createRagIndexComparison = (body) => request(`${RAG}/index-comparisons`, { method: 'POST', body: JSON.stringify(body) })
export const ragIndexComparison = (id) => request(`${RAG}/index-comparisons/${id}`)
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
export const improvementReport = (id) => request(`${FB}/improvement-reports/${id}`)

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
export const ragSourceRightsCheck = (sourceId) => request(`/api/admin/rag/sources/${sourceId}/rights-check`)

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
export const discoveryComparison = (comparisonId) => request(`${DD}/comparisons/${comparisonId}`)

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
export const ragValidationResults = (id) => request(`${PRR}/rag/candidates/${id}/validation-results`)
export const activateRagReleaseCandidate = (id) => request(`${PRR}/rag/candidates/${id}/activate`, { method: 'POST', body: JSON.stringify({}) })
export const rollbackRagReleaseCandidate = (id) => request(`${PRR}/rag/candidates/${id}/rollback`, { method: 'POST', body: JSON.stringify({}) })
export const ragActivationEvents = (id) => request(`${PRR}/rag/candidates/${id}/activation-events`)

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
export const acceptanceReviews = (reportId) => request(`${PRR}/readiness-reports/${reportId}/acceptance-reviews`)

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
export const knowledgeGapCluster = (id) => request(`${KG}/clusters/${id}`)
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
