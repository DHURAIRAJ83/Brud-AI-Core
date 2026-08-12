import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SessionList from './SessionList.jsx'

const ITEMS = [
  { id: 's1', title: 'Session about datasets', subtitle: 'active', meta: '5 messages', status: 'active' },
  { id: 's2', title: 'Session about RAG', subtitle: 'completed', meta: '2 messages', status: 'completed' },
]

describe('SessionList', () => {
  it('renders every real item passed in', () => {
    render(<SessionList items={ITEMS} activeId={null} onSelect={vi.fn()} />)
    expect(screen.getByText('Session about datasets')).toBeInTheDocument()
    expect(screen.getByText('Session about RAG')).toBeInTheDocument()
  })

  it('shows the empty-state label when there are no items at all', () => {
    render(<SessionList items={[]} activeId={null} onSelect={vi.fn()} emptyLabel="No conversations yet." />)
    expect(screen.getByText('No conversations yet.')).toBeInTheDocument()
  })

  it('filters items with real client-side search over title/subtitle', async () => {
    const user = userEvent.setup()
    render(<SessionList items={ITEMS} activeId={null} onSelect={vi.fn()} />)
    await user.type(screen.getByLabelText('Search conversations'), 'RAG')
    expect(screen.getByText('Session about RAG')).toBeInTheDocument()
    expect(screen.queryByText('Session about datasets')).not.toBeInTheDocument()
  })

  it('shows a distinct "no match" message when search excludes everything', async () => {
    const user = userEvent.setup()
    render(<SessionList items={ITEMS} activeId={null} onSelect={vi.fn()} />)
    await user.type(screen.getByLabelText('Search conversations'), 'zzz-nonexistent')
    expect(screen.getByText('No conversations match this search.')).toBeInTheDocument()
  })

  it('calls onSelect with the real item id when clicked, and marks the active one', () => {
    const onSelect = vi.fn()
    render(<SessionList items={ITEMS} activeId="s2" onSelect={onSelect} />)
    screen.getByText('Session about datasets').closest('button').click()
    expect(onSelect).toHaveBeenCalledWith('s1')
    expect(screen.getByText('Session about RAG').closest('button')).toHaveAttribute('aria-current', 'true')
  })

  it('renders a delete button only when onDelete is provided, calling it with the real id', () => {
    const onDelete = vi.fn()
    const { rerender } = render(<SessionList items={ITEMS} activeId={null} onSelect={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Delete/ })).not.toBeInTheDocument()

    rerender(<SessionList items={ITEMS} activeId={null} onSelect={vi.fn()} onDelete={onDelete} />)
    screen.getByRole('button', { name: 'Delete Session about datasets' }).click()
    expect(onDelete).toHaveBeenCalledWith('s1')
  })
})
