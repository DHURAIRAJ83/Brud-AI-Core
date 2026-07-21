const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function getOverview() {
  const response = await fetch(`${API_BASE}/api/admin/overview`)
  if (!response.ok) throw new Error(`Overview request failed (${response.status})`)
  return response.json()
}
