import { useEffect, useState } from 'react'

// "Data" groups the data-related pages (Phase 1 unified navigation). Every
// child key below is an existing, unchanged `active` string already handled
// by App.jsx -- grouping them here never renames or moves the underlying
// page, so bookmarked "#Datasets" style hash URLs keep working exactly as
// before. Only "Data Overview" and "Data Help" are new pages.
const dataGroup = {
  key: 'Data',
  label: 'Data',
  group: true,
  children: [
    // ariaLabel disambiguates this from the top-level "Overview" item for
    // assistive tech (both would otherwise share the accessible name
    // "Overview"); the visible label stays short since nesting under "Data"
    // already disambiguates it visually.
    { key: 'Data Overview', label: 'Overview', ariaLabel: 'Data Overview' },
    { key: 'Datasets', label: 'Datasets' },
    { key: 'Manual Data', label: 'Manual Data' },
    { key: 'Sources & Rights', label: 'Sources & Rights' },
    { key: 'External Data Providers', label: 'External Data Providers' },
    { key: 'Dataset Discovery', label: 'Dataset Discovery' },
    { key: 'Dataset Verification', label: 'Dataset Verification' },
    { key: 'Sample Import & Quarantine', label: 'Sample Import & Quarantine' },
    { key: 'RAG Sandbox', label: 'RAG Sandbox' },
    { key: 'Incremental Training', label: 'Incremental Training' },
    { key: 'Documents', label: 'Documents' },
    { key: 'Document Wizard', label: 'Document Wizard' },
    { key: 'Chunk & Record Studio', label: 'Chunk & Record Studio' },
    { key: 'Quality & Approval', label: 'Quality & Approval' },
    { key: 'Builds & Pipelines', label: 'Builds & Pipelines' },
    { key: 'Corpus Builder', label: 'Corpus Builder' },
    { key: 'Knowledge & RAG', label: 'Knowledge & RAG' },
    { key: 'Pretraining Readiness', label: 'Pretraining Readiness' },
    { key: 'Evaluation', label: 'Evaluation' },
    { key: 'Data Help', label: 'Help & Guide' },
  ],
}

export const navTree = [
  { key: 'Overview', label: 'Overview' },
  { key: 'System', label: 'System' },
  dataGroup,
  { key: 'Tokenizer', label: 'Tokenizer' },
  { key: 'Core Model', label: 'Core Model' },
  { key: 'Training', label: 'Training' },
  { key: 'Base Training', label: 'Base Training' },
  { key: 'Instruction Tuning', label: 'Instruction Tuning' },
  { key: 'Model Registry', label: 'Model Registry' },
  { key: 'Inference Runtime', label: 'Inference Runtime' },
  { key: 'Production Readiness', label: 'Production Readiness' },
  { key: 'Knowledge Routing', label: 'Knowledge Routing' },
  { key: 'Public Chat Routing', label: 'Public Chat Routing' },
  { key: 'Knowledge Gaps', label: 'Knowledge Gaps' },
  { key: 'Trusted Web', label: 'Trusted Web' },
  { key: 'Deterministic Tools', label: 'Deterministic Tools' },
  { key: 'Conversation & Memory', label: 'Conversation & Memory' },
  { key: 'Feedback & Improvement', label: 'Feedback & Improvement' },
  { key: 'Chat Testing', label: 'Chat Testing' },
  { key: 'Admin Assistant', label: 'Admin Assistant' },
  { key: 'Audit Logs', label: 'Audit Logs' },
  { key: 'Settings', label: 'Settings' },
]

// Flat list of every reachable page key, preserved for anything (tests,
// future callers) that wants the full set without caring about grouping.
export const menuItems = navTree.flatMap((item) => (item.group ? item.children.map((c) => c.key) : item.key))

function isWithin(active, item) {
  return active === item.key || (item.group && item.children.some((child) => child.key === active))
}

export default function Sidebar({ active, open, onSelect, onClose }) {
  const [expanded, setExpanded] = useState(() => isWithin(active, dataGroup))

  useEffect(() => {
    if (isWithin(active, dataGroup)) setExpanded(true)
  }, [active])

  function choose(key) {
    onSelect(key)
    onClose()
  }

  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="side-brand"><span>B</span><div><strong>Brud AI</strong><small>Control center</small></div></div>
      <nav aria-label="Admin modules">
        {navTree.map((item) => item.group ? (
          <div className="nav-group" key={item.key}>
            <button
              type="button"
              className={`nav-group-toggle ${isWithin(active, item) ? 'active-group' : ''}`}
              aria-expanded={expanded}
              aria-controls={`nav-group-${item.key}`}
              onClick={() => setExpanded((value) => !value)}
            >
              <span>{item.label}</span>
              <span className="nav-caret" aria-hidden="true">{expanded ? '▾' : '▸'}</span>
            </button>
            {expanded && (
              <div className="nav-children" id={`nav-group-${item.key}`} role="group" aria-label={`${item.label} pages`}>
                {item.children.map((child) => (
                  <button
                    key={child.key}
                    className={active === child.key ? 'active' : ''}
                    aria-current={active === child.key ? 'page' : undefined}
                    aria-label={child.ariaLabel}
                    onClick={() => choose(child.key)}
                  >{child.label}</button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <button
            key={item.key}
            className={active === item.key ? 'active' : ''}
            aria-current={active === item.key ? 'page' : undefined}
            onClick={() => choose(item.key)}
          >{item.label}</button>
        ))}
      </nav>
      <div className="phase-tag">Phase 21A · Tokenizer &amp; pretraining readiness</div>
    </aside>
  )
}
