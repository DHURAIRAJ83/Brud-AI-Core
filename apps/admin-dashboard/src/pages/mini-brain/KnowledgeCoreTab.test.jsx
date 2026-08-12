import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import KnowledgeCoreTab from './KnowledgeCoreTab.jsx'

function baseProps(overrides = {}) {
  return {
    knowledgeSubTab: 'Domains',
    selectKnowledgeSubTab: vi.fn(),
    kcDomains: [],
    seedKnowledge: vi.fn(),
    kcQuery: '',
    setKcQuery: vi.fn(),
    runKnowledgeSearch: vi.fn((event) => event?.preventDefault?.()),
    kcResults: [],
    openKnowledgeItem: vi.fn(),
    kcSelectedItem: null,
    runValidation: vi.fn(),
    kcValidation: null,
    kcCoverage: null,
    ...overrides,
  }
}

describe('KnowledgeCoreTab', () => {
  it('renders all four sub-tabs and shows a real seed button when there are no domains', async () => {
    const user = userEvent.setup()
    const selectKnowledgeSubTab = vi.fn()
    render(<KnowledgeCoreTab {...baseProps({ selectKnowledgeSubTab })} />)
    for (const label of ['Domains', 'Search', 'Validation', 'Coverage']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Seed default knowledge' }))
    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(selectKnowledgeSubTab).toHaveBeenCalledWith('Search')
  })

  it('renders real domain StatusCards when domains are loaded', () => {
    render(<KnowledgeCoreTab {...baseProps({ kcDomains: [{ public_id: 'd1', name: 'Runtime', item_count: 4 }] })} />)
    expect(screen.getByText('Runtime').closest('article')).toHaveTextContent('4 items')
  })

  it('Search sub-tab: submits a real query and shows a selected item', async () => {
    const user = userEvent.setup()
    const runKnowledgeSearch = vi.fn((event) => event?.preventDefault?.())
    const openKnowledgeItem = vi.fn()
    render(<KnowledgeCoreTab {...baseProps({
      knowledgeSubTab: 'Search',
      kcResults: [{ public_id: 'k1', title: 'Runtime API', category: 'api', description: 'desc' }],
      kcSelectedItem: { title: 'Runtime API', description: 'desc', source: 'code', version: '1', status: 'active', tags: ['a'], relationships: [] },
      runKnowledgeSearch, openKnowledgeItem,
    })} />)
    const searchForm = screen.getByPlaceholderText('title, keyword, API, service...').closest('form')
    await user.click(within(searchForm).getByRole('button', { name: 'Search' }))
    expect(runKnowledgeSearch).toHaveBeenCalled()
    await user.click(screen.getAllByText('Runtime API')[0])
    expect(openKnowledgeItem).toHaveBeenCalledWith('k1')
    expect(screen.getByText('No relationships recorded.')).toBeInTheDocument()
  })

  it('Validation sub-tab: shows real issue counts', () => {
    render(<KnowledgeCoreTab {...baseProps({
      knowledgeSubTab: 'Validation',
      kcValidation: { summary: { duplicate: 2 }, issue_count: 2 },
    })} />)
    expect(screen.getByText('duplicate').closest('article')).toHaveTextContent('2')
    expect(screen.getByText(/2 total issue\(s\)/)).toBeInTheDocument()
  })

  it('Coverage sub-tab: shows real per-domain coverage rows', () => {
    render(<KnowledgeCoreTab {...baseProps({
      knowledgeSubTab: 'Coverage',
      kcCoverage: {
        overall: { total_items: 10, documentation_coverage_pct: 50, catalog_coverage_pct: null },
        domains: [{ domain: 'Runtime', item_count: 10, documented_count: 5, documentation_coverage_pct: 50, catalog_coverage_pct: null }],
      },
    })} />)
    expect(screen.getAllByText('Catalog coverage')[0].closest('article')).toHaveTextContent('unknown')
    expect(screen.getByRole('row', { name: /Runtime/ })).toHaveTextContent('unknown')
  })
})
