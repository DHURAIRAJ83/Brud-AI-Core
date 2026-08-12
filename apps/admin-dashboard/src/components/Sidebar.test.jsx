import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Sidebar, { menuItems, navTree } from './Sidebar.jsx'

// The exact 45 real page keys as of the Phase 3 redesign (the 44 keys that
// existed after Phase 2's Data Workspace Wizard addition, plus Phase 3's one
// deliberate, disclosed addition: "Assistant Center"), frozen here as
// a literal snapshot so it can never silently drift. These are the literal
// `active` strings App.jsx switches on and the `#hash` values already
// bookmarked by admins -- future phases must never rename or remove one;
// a new phase that adds a real page updates this list intentionally, the
// same way this list itself grew from 44 to 45.
const PRE_REDESIGN_KEYS = [
  'Overview', 'System', 'Pilot Operations', 'Pilot Metrics', 'Tokenizer', 'Core Model',
  'Training', 'Base Training', 'Instruction Tuning', 'Model Registry', 'Inference Runtime',
  'Production Readiness', 'Knowledge Routing', 'Public Chat Routing', 'Knowledge Gaps',
  'Trusted Web', 'Deterministic Tools', 'Conversation & Memory', 'Feedback & Improvement',
  'Admin Assistant', 'Assistant Center', 'Brud Mini Brain', 'Data Overview', 'Datasets', 'Manual Data',
  'Sources & Rights', 'External Data Providers', 'Dataset Discovery', 'Dataset Verification',
  'Sample Import & Quarantine', 'RAG Sandbox', 'Incremental Training', 'Documents',
  'Document Wizard', 'Data Workspace Wizard', 'Chunk & Record Studio', 'Quality & Approval',
  'Builds & Pipelines', 'Corpus Builder', 'Knowledge & RAG', 'Gateway → Dataset/RAG',
  'Prompt Optimization', 'Pretraining Readiness', 'Evaluation', 'Data Help',
]

// Every real nav group, derived from navTree itself (single source of
// truth) so tests can't drift from whatever the Sidebar actually renders.
const GROUPS = navTree.filter((item) => item.group)

function renderSidebar(active) {
  const onSelect = vi.fn()
  const onClose = vi.fn()
  render(<Sidebar active={active} open={false} onSelect={onSelect} onClose={onClose} />)
  return { onSelect, onClose }
}

describe('Sidebar: existing route/key preservation', () => {
  it('keeps every pre-redesign page key reachable (no rename, no removal)', () => {
    for (const key of PRE_REDESIGN_KEYS) {
      expect(menuItems).toContain(key)
    }
  })

  it('reorganizes into named groups without losing, renaming, or adding any key', () => {
    expect(new Set(menuItems)).toEqual(new Set(PRE_REDESIGN_KEYS))
  })

  it('does not silently duplicate a key across top-level and grouped entries', () => {
    expect(new Set(menuItems).size).toBe(menuItems.length)
  })
})

for (const group of GROUPS) {
  describe(`Sidebar: "${group.label}" group`, () => {
    it(`renders one collapsible "${group.label}" group containing every real child page`, () => {
      renderSidebar('Overview')
      expect(screen.getByRole('button', { name: group.label, exact: true })).toBeInTheDocument()
      // Collapsed by default when active is unrelated (Overview is always
      // ungrouped, so it's never a member of any group).
      for (const child of group.children.slice(0, 3)) {
        expect(screen.queryByRole('button', { name: child.ariaLabel ?? child.label })).not.toBeInTheDocument()
      }
    })

    it('expands on click and reveals every child page', async () => {
      const user = userEvent.setup()
      renderSidebar('Overview')
      await user.click(screen.getByRole('button', { name: group.label, exact: true }))
      for (const child of group.children) {
        expect(screen.getByRole('button', { name: child.ariaLabel ?? child.label })).toBeInTheDocument()
      }
    })

    it('collapses again on a second click', async () => {
      const user = userEvent.setup()
      renderSidebar('Overview')
      const toggle = screen.getByRole('button', { name: group.label, exact: true })
      const firstChild = group.children[0]
      await user.click(toggle)
      expect(screen.getByRole('button', { name: firstChild.ariaLabel ?? firstChild.label })).toBeInTheDocument()
      await user.click(toggle)
      expect(screen.queryByRole('button', { name: firstChild.ariaLabel ?? firstChild.label })).not.toBeInTheDocument()
    })

    it('auto-expands when the active page is a child (direct URL / refresh case)', () => {
      const firstChild = group.children[0]
      renderSidebar(firstChild.key)
      expect(screen.getByRole('button', { name: firstChild.ariaLabel ?? firstChild.label })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: group.label, exact: true })).toHaveAttribute('aria-expanded', 'true')
    })

    it('keeps every child clickable and reports its exact existing key to onSelect', async () => {
      const user = userEvent.setup()
      const { onSelect, onClose } = renderSidebar('Overview')
      await user.click(screen.getByRole('button', { name: group.label, exact: true }))
      for (const child of group.children) {
        onSelect.mockClear()
        onClose.mockClear()
        await user.click(screen.getByRole('button', { name: child.ariaLabel ?? child.label }))
        expect(onSelect).toHaveBeenCalledWith(child.key)
        expect(onClose).toHaveBeenCalled()
      }
    })
  })
}

describe('Sidebar: ungrouped top-level items', () => {
  it('keeps every ungrouped top-level item present, unmoved, and clickable', async () => {
    const user = userEvent.setup()
    const { onSelect } = renderSidebar('Overview')
    const topLevel = navTree.filter((item) => !item.group)
    for (const item of topLevel) {
      onSelect.mockClear()
      await user.click(screen.getByRole('button', { name: item.label }))
      expect(onSelect).toHaveBeenCalledWith(item.key)
    }
  })
})

describe('Sidebar: active-state and ARIA correctness', () => {
  // Generic group-toggle mechanics -- exercised against one representative
  // group/child pair since the underlying behavior is uniform across all
  // groups (already covered exhaustively per group above).
  const sampleGroup = GROUPS[0]
  const sampleChild = sampleGroup.children[0]

  it('marks exactly one button as the current page (no duplicate active state)', () => {
    // A group child is already a member of an auto-expanded group on
    // mount -- no click needed (and clicking the toggle here would
    // collapse it).
    renderSidebar(sampleChild.key)
    const current = screen.getAllByRole('button').filter((el) => el.getAttribute('aria-current') === 'page')
    expect(current).toHaveLength(1)
    expect(current[0]).toHaveTextContent(sampleChild.ariaLabel ?? sampleChild.label)
  })

  it('gives a group toggle a distinct active-family style, not the leaf .active class', async () => {
    const user = userEvent.setup()
    renderSidebar(sampleChild.key)
    const toggle = screen.getByRole('button', { name: sampleGroup.label, exact: true })
    await user.click(toggle)
    await user.click(toggle)
    expect(toggle.className).toContain('active-group')
    expect(toggle.className).not.toContain(' active ')
  })

  it('exposes aria-expanded on a group toggle in both states', async () => {
    const user = userEvent.setup()
    renderSidebar('Overview')
    const toggle = screen.getByRole('button', { name: sampleGroup.label, exact: true })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
  })

  it('supports keyboard activation of a group toggle (Enter and Space)', async () => {
    const user = userEvent.setup()
    renderSidebar('Overview')
    const toggle = screen.getByRole('button', { name: sampleGroup.label, exact: true })
    toggle.focus()
    await user.keyboard('{Enter}')
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard(' ')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
  })

  it('groups children under a labelled, ARIA-identifiable region when expanded', async () => {
    const user = userEvent.setup()
    renderSidebar('Overview')
    await user.click(screen.getByRole('button', { name: sampleGroup.label, exact: true }))
    const group = screen.getByRole('group', { name: new RegExp(`${sampleGroup.label} pages`, 'i') })
    expect(within(group).getByRole('button', { name: sampleChild.ariaLabel ?? sampleChild.label })).toBeInTheDocument()
  })
})
