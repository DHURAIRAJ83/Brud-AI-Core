// Mirrors core_model/admin_assistant/dashboard_registry.py::DOCUMENT_NAVIGATION_TARGETS
// exactly -- one entry per real, already-existing Documents/Wizard UI section. Kept in
// parity by tests/core_model/test_admin_assistant_registries.py, which regex-parses this
// file the same way it already parses Sidebar.jsx. Do not add a key here without adding
// the matching NavigationTarget in dashboard_registry.py, and vice versa.
export const DOCUMENT_NAV_TARGETS = {
  'overview': { navKey: 'Documents', documentsTab: 'Overview' },
  'pages': { navKey: 'Documents', documentsTab: 'Processing' },
  'critical-pages': { navKey: 'Documents', documentsTab: 'Processing' },
  'cleanup': { navKey: 'Documents', documentsTab: 'Repeated Elements' },
  'tamil-quality': { navKey: 'Documents', documentsTab: 'Tamil Quality' },
  'sft-generation': { navKey: 'Documents', documentsTab: 'SFT Candidates' },
  'sft-candidates': { navKey: 'Documents', documentsTab: 'SFT Candidates' },
  'export': { navKey: 'Documents', documentsTab: 'Export' },
  'media-tables': { navKey: 'Documents', documentsTab: 'Media & Tables' },
  'security-review': { navKey: 'Documents', documentsTab: 'Security Review' },
  'dataset-handoff': { navKey: 'Document Wizard', wizardStep: 11 },
  'split-preview': { navKey: 'Document Wizard', wizardStep: 12 },
  'dataset-version': { navKey: 'Document Wizard', wizardStep: 13 },
  'training-readiness': { navKey: 'Document Wizard', wizardStep: 14 },
  'chunks': { navKey: 'Chunk & Record Studio' },
  'assistant': { navKey: 'Admin Assistant' },
}

const DOCUMENTS_TAB_KEYS = Object.fromEntries(
  Object.entries(DOCUMENT_NAV_TARGETS).filter(([, value]) => value.navKey === 'Documents').map(([key]) => [key, key]),
)

export function isKnownDocumentsTabKey(key) {
  return Boolean(DOCUMENTS_TAB_KEYS[key])
}

export function resolveDocumentNavigation(tabKey, documentPublicId) {
  const target = DOCUMENT_NAV_TARGETS[tabKey]
  if (!target) return null
  return { ...target, tabKey, documentPublicId: documentPublicId ?? null }
}

export function buildDocumentsHash(documentPublicId, tabKey) {
  const params = new URLSearchParams()
  if (documentPublicId) params.set('document', documentPublicId)
  if (tabKey) params.set('tab', tabKey)
  const query = params.toString()
  return `#${encodeURIComponent('Documents')}${query ? `?${query}` : ''}`
}

export function buildWizardHash(documentPublicId, step) {
  const params = new URLSearchParams()
  if (documentPublicId) params.set('document', documentPublicId)
  if (step) params.set('step', String(step))
  const query = params.toString()
  return `#${encodeURIComponent('Document Wizard')}${query ? `?${query}` : ''}`
}

// Parses `PageName?document=<id>&tab=<key>|step=<n>` from the raw hash (without the
// leading '#'). Never trusts the query string as an API path or DOM selector -- only
// the two known keys are ever read.
export function parseHash(rawHash) {
  const decoded = decodeURIComponent(rawHash || '')
  const [page, query = ''] = decoded.split('?')
  const params = new URLSearchParams(query)
  const documentPublicId = params.get('document') || null
  const tab = params.get('tab') || null
  const stepRaw = params.get('step')
  const step = stepRaw && /^\d+$/.test(stepRaw) ? Number(stepRaw) : null
  return { page: page || 'Overview', documentPublicId, tab, step }
}
