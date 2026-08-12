import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import Breadcrumbs, { findBreadcrumb } from './Breadcrumbs.jsx'
import { navTree } from './Sidebar.jsx'

describe('findBreadcrumb', () => {
  it('returns a single crumb for an ungrouped top-level page', () => {
    expect(findBreadcrumb(navTree, 'Overview')).toEqual(['Overview'])
  })

  it('returns "Group › Page" for a grouped page, using ariaLabel when present', () => {
    expect(findBreadcrumb(navTree, 'Data Overview')).toEqual(['Data Workspace', 'Data Overview'])
    expect(findBreadcrumb(navTree, 'Documents')).toEqual(['Data Workspace', 'Documents'])
    expect(findBreadcrumb(navTree, 'Knowledge & RAG')).toEqual(['Knowledge & Retrieval', 'Knowledge & RAG'])
  })

  it('falls back to the raw key for an unrecognized active page', () => {
    expect(findBreadcrumb(navTree, 'Nonexistent Page')).toEqual(['Nonexistent Page'])
  })
})

describe('Breadcrumbs component', () => {
  it('renders a single crumb with no separator for an ungrouped page', () => {
    render(<Breadcrumbs active="Overview" />)
    const nav = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(nav).toHaveTextContent('Overview')
    expect(nav.querySelector('.breadcrumb-separator')).not.toBeInTheDocument()
  })

  it('renders "Group › Page" for a grouped page', () => {
    render(<Breadcrumbs active="Documents" />)
    const nav = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(nav).toHaveTextContent('Data Workspace')
    expect(nav).toHaveTextContent('Documents')
    expect(nav.querySelector('.breadcrumb-separator')).toBeInTheDocument()
  })
})
