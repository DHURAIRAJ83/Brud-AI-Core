import { useEffect, useState } from 'react'

// Phase 1 redesign: every child key below is an existing, unchanged
// `active` string already handled by App.jsx -- regrouping them here never
// renames or moves the underlying page, so bookmarked "#Datasets" style
// hash URLs keep working exactly as before. This file is regex-parsed by
// the backend (tests/core_model/test_admin_assistant_registries.py's
// `_real_nav_keys()`), which requires every `{ key: '...', label: '...' }`
// entry to stay on a single line -- do not reformat across multiple lines.

const systemOperationsGroup = {
  key: 'System & Operations',
  label: 'System & Operations',
  group: true,
  children: [
    { key: 'System', label: 'System' },
    { key: 'Pilot Operations', label: 'Pilot Operations' },
    { key: 'Pilot Metrics', label: 'Pilot Metrics' },
    { key: 'Production Readiness', label: 'Production Readiness' },
  ],
}

const dataWorkspaceGroup = {
  key: 'Data Workspace',
  label: 'Data Workspace',
  group: true,
  children: [
    // ariaLabel disambiguates this from the top-level "Overview" item for
    // assistive tech (both would otherwise share the accessible name
    // "Overview"); the visible label stays short since nesting under
    // "Data Workspace" already disambiguates it visually.
    { key: 'Data Overview', label: 'Overview', ariaLabel: 'Data Overview' },
    { key: 'Datasets', label: 'Datasets' },
    { key: 'Manual Data', label: 'Manual Data' },
    { key: 'Sources & Rights', label: 'Sources & Rights' },
    { key: 'External Data Providers', label: 'External Data Providers' },
    { key: 'Dataset Discovery', label: 'Dataset Discovery' },
    { key: 'Dataset Verification', label: 'Dataset Verification' },
    { key: 'Sample Import & Quarantine', label: 'Sample Import & Quarantine' },
    { key: 'Incremental Training', label: 'Incremental Training' },
    { key: 'Documents', label: 'Documents' },
    { key: 'Document Wizard', label: 'Document Wizard' },
    { key: 'Data Workspace Wizard', label: 'Data Workspace Wizard' },
    { key: 'Chunk & Record Studio', label: 'Chunk & Record Studio' },
    { key: 'Quality & Approval', label: 'Quality & Approval' },
    { key: 'Builds & Pipelines', label: 'Builds & Pipelines' },
    { key: 'Data Help', label: 'Help & Guide' },
  ],
}

const knowledgeRetrievalGroup = {
  key: 'Knowledge & Retrieval',
  label: 'Knowledge & Retrieval',
  group: true,
  children: [
    { key: 'RAG Sandbox', label: 'RAG Sandbox' },
    { key: 'Corpus Builder', label: 'Corpus Builder' },
    { key: 'Knowledge & RAG', label: 'Knowledge & RAG' },
    { key: 'Gateway → Dataset/RAG', label: 'Gateway → Dataset/RAG' },
    { key: 'Knowledge Routing', label: 'Knowledge Routing' },
    { key: 'Public Chat Routing', label: 'Public Chat Routing' },
    { key: 'Knowledge Gaps', label: 'Knowledge Gaps' },
    { key: 'Trusted Web', label: 'Trusted Web' },
    { key: 'Prompt Optimization', label: 'Prompt Optimization' },
  ],
}

const modelTrainingGroup = {
  key: 'Model & Training',
  label: 'Model & Training',
  group: true,
  children: [
    { key: 'Tokenizer', label: 'Tokenizer' },
    { key: 'Core Model', label: 'Core Model' },
    { key: 'Training', label: 'Training' },
    { key: 'Base Training', label: 'Base Training' },
    { key: 'Instruction Tuning', label: 'Instruction Tuning' },
    { key: 'Model Registry', label: 'Model Registry' },
    { key: 'Inference Runtime', label: 'Inference Runtime' },
    { key: 'Pretraining Readiness', label: 'Pretraining Readiness' },
    { key: 'Evaluation', label: 'Evaluation' },
  ],
}

// Named "Conversation & Assistants" (not just "Assistants") so a later
// phase can split Admin Assistant/Brud Mini Brain into a dedicated
// "Assistants" group once the Assistant Center ships, without another
// structural rewrite.
const conversationAssistantsGroup = {
  key: 'Conversation & Assistants',
  label: 'Conversation & Assistants',
  group: true,
  children: [
    { key: 'Conversation & Memory', label: 'Conversation & Memory' },
    { key: 'Feedback & Improvement', label: 'Feedback & Improvement' },
    { key: 'Deterministic Tools', label: 'Deterministic Tools' },
    { key: 'Admin Assistant', label: 'Admin Assistant' },
    { key: 'Assistant Center', label: 'Assistant Center' },
    { key: 'Brud Mini Brain', label: 'Brud Mini Brain' },
  ],
}

export const navTree = [
  { key: 'Overview', label: 'Overview' },
  systemOperationsGroup,
  dataWorkspaceGroup,
  knowledgeRetrievalGroup,
  modelTrainingGroup,
  conversationAssistantsGroup,
]

// Flat list of every reachable page key, preserved for anything (tests,
// future callers) that wants the full set without caring about grouping.
export const menuItems = navTree.flatMap((item) => (item.group ? item.children.map((c) => c.key) : item.key))

function isWithin(active, item) {
  return active === item.key || (item.group && item.children.some((child) => child.key === active))
}

export default function Sidebar({ active, open, onSelect, onClose }) {
  const groups = navTree.filter((item) => item.group)
  const [expandedGroups, setExpandedGroups] = useState(() =>
    Object.fromEntries(groups.map((group) => [group.key, isWithin(active, group)]))
  )

  useEffect(() => {
    const owner = groups.find((group) => isWithin(active, group))
    if (owner) setExpandedGroups((previous) => ({ ...previous, [owner.key]: true }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active])

  function toggleGroup(key) {
    setExpandedGroups((previous) => ({ ...previous, [key]: !previous[key] }))
  }

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
              aria-expanded={Boolean(expandedGroups[item.key])}
              aria-controls={`nav-group-${item.key}`}
              onClick={() => toggleGroup(item.key)}
            >
              <span>{item.label}</span>
              <span className="nav-caret" aria-hidden="true">{expandedGroups[item.key] ? '▾' : '▸'}</span>
            </button>
            {expandedGroups[item.key] && (
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
