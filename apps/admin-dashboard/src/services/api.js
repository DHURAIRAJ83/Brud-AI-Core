const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function getOverview() {
  return request('/api/admin/overview')
}

async function request(path) {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json()
}

export async function getSystemStatus() {
  const [database, configuration, schema, audit] = await Promise.all([
    request('/api/admin/system/database'),
    request('/api/admin/system/configuration'),
    request('/api/admin/system/schema'),
    request('/api/admin/audit/recent?limit=8'),
  ])
  return { database, configuration, schema, audit }
}
