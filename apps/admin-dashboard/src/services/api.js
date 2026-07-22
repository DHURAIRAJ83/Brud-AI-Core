const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
let csrfToken = null
let csrfHeaderName = 'X-CSRF-Token'

async function request(path, options = {}) {
  const headers = { ...(options.headers ?? {}) }
  if (options.body) headers['Content-Type'] = 'application/json'
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
