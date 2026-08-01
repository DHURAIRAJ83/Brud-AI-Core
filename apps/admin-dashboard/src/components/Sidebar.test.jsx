import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Sidebar, { menuItems, navTree } from './Sidebar.jsx'

// Every page key that existed before the Phase 1 Data-menu restructure.
// These are the literal `active` strings App.jsx switches on and the
// `#hash` values already bookmarked by admins -- Phase 1 must not rename,
// remove, or restructure any of them.
const PRE_PHASE1_KEYS = [
  'Overview', 'System', 'Datasets', 'Documents', 'Tokenizer', 'Core Model',
  'Training', 'Base Training', 'Instruction Tuning', 'Evaluation', 'Model Registry',
  'Inference Runtime', 'Knowledge & RAG', 'Conversation & Memory', 'Feedback & Improvement',
  'Corpus Builder', 'Pretraining Readiness', 'Chat Testing', 'Admin Assistant',
  'Audit Logs', 'Settings',
]

// Derived from navTree itself (single source of truth) rather than hand-listed,
// so this test can't drift from whatever labels the Sidebar actually renders.
const DATA_GROUP = navTree.find((item) => item.group)
const DATA_CHILDREN = DATA_GROUP.children

function renderSidebar(active) {
  const onSelect = vi.fn()
  const onClose = vi.fn()
  render(<Sidebar active={active} open={false} onSelect={onSelect} onClose={onClose} />)
  return { onSelect, onClose }
}

describe('Sidebar: existing route/key preservation', () => {
  it('keeps every pre-Phase-1 page key reachable (no rename, no removal)', () => {
    for (const key of PRE_PHASE1_KEYS) {
      expect(menuItems).toContain(key)
    }
  })

  it('does not silently duplicate a key across top-level and grouped entries', () => {
    expect(new Set(menuItems).size).toBe(menuItems.length)
  })
})

describe('Sidebar: Data parent menu', () => {
  it('renders one collapsible "Data" group containing every data-related real page', () => {
    renderSidebar('Overview')
    expect(screen.getByRole('button', { name: /^Data$/ })).toBeInTheDocument()
    // Collapsed by default when active is unrelated to Data.
    for (const label of ['Datasets', 'Documents', 'Corpus Builder']) {
      expect(screen.queryByRole('button', { name: label })).not.toBeInTheDocument()
    }
  })

  it('expands on click and reveals every Data child page', async () => {
    const user = userEvent.setup()
    renderSidebar('Overview')
    await user.click(screen.getByRole('button', { name: /^Data$/ }))
    for (const child of DATA_CHILDREN) {
      expect(screen.getByRole('button', { name: child.ariaLabel ?? child.label })).toBeInTheDocument()
    }
  })

  it('collapses again on a second click', async () => {
    const user = userEvent.setup()
    renderSidebar('Overview')
    const toggle = screen.getByRole('button', { name: /^Data$/ })
    await user.click(toggle)
    expect(screen.getByRole('button', { name: 'Datasets' })).toBeInTheDocument()
    await user.click(toggle)
    expect(screen.queryByRole('button', { name: 'Datasets' })).not.toBeInTheDocument()
  })

  it('auto-expands when the active page is a Data child (direct URL / refresh case)', () => {
    renderSidebar('Documents')
    expect(screen.getByRole('button', { name: 'Documents' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Data$/ })).toHaveAttribute('aria-expanded', 'true')
  })

  it('keeps every Data child clickable and reports its exact existing key to onSelect', async () => {
    const user = userEvent.setup()
    const { onSelect, onClose } = renderSidebar('Overview')
    await user.click(screen.getByRole('button', { name: /^Data$/ }))
    for (const child of DATA_CHILDREN) {
      onSelect.mockClear()
      onClose.mockClear()
      await user.click(screen.getByRole('button', { name: child.ariaLabel ?? child.label }))
      expect(onSelect).toHaveBeenCalledWith(child.key)
      expect(onClose).toHaveBeenCalled()
    }
  })

  it('keeps every non-Data top-level item present, unmoved, and clickable', async () => {
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
  it('marks exactly one button as the current page (no duplicate active state)', () => {
    // 'Corpus Builder' is a Data child, so the group is already auto-expanded
    // on mount -- no click needed (and clicking the toggle here would collapse it).
    renderSidebar('Corpus Builder')
    const current = screen.getAllByRole('button').filter((el) => el.getAttribute('aria-current') === 'page')
    expect(current).toHaveLength(1)
    expect(current[0]).toHaveTextContent('Corpus Builder')
  })

  it('gives the Data toggle a distinct active-family style, not the leaf .active class', async () => {
    const user = userEvent.setup()
    renderSidebar('Evaluation')
    await user.click(screen.getByRole('button', { name: /^Data$/ }))
    const toggle = screen.getByRole('button', { name: /^Data$/ })
    expect(toggle.className).toContain('active-group')
    expect(toggle.className).not.toContain(' active ')
  })

  it('exposes aria-expanded on the group toggle in both states', async () => {
    const user = userEvent.setup()
    renderSidebar('Overview')
    const toggle = screen.getByRole('button', { name: /^Data$/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
  })

  it('supports keyboard activation of the group toggle (Enter and Space)', async () => {
    const user = userEvent.setup()
    renderSidebar('Overview')
    await user.tab() // focus moves into the nav; first focusable is Overview
    const toggle = screen.getByRole('button', { name: /^Data$/ })
    toggle.focus()
    await user.keyboard('{Enter}')
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard(' ')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
  })

  it('groups children under a labelled, ARIA-identifiable region when expanded', async () => {
    const user = userEvent.setup()
    renderSidebar('Overview')
    await user.click(screen.getByRole('button', { name: /^Data$/ }))
    const group = screen.getByRole('group', { name: /Data pages/i })
    expect(within(group).getByRole('button', { name: 'Datasets' })).toBeInTheDocument()
  })
})
