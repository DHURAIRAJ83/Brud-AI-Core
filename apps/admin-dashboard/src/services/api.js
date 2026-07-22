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
