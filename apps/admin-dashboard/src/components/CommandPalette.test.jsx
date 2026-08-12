import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CommandPalette from './CommandPalette.jsx'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('CommandPalette', () => {
  it('is not rendered until Ctrl+K/Cmd+K is pressed', () => {
    render(<CommandPalette onSelect={vi.fn()} />)
    expect(screen.queryByRole('dialog', { name: 'Command palette' })).not.toBeInTheDocument()
  })

  it('opens on Ctrl+K and shows every real nav page by default', async () => {
    const user = userEvent.setup()
    render(<CommandPalette onSelect={vi.fn()} />)
    await user.keyboard('{Control>}k{/Control}')
    expect(screen.getByRole('dialog', { name: 'Command palette' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Pilot Metrics/ })).toBeInTheDocument()
  })

  it('opens on Cmd+K (metaKey) too', async () => {
    const user = userEvent.setup()
    render(<CommandPalette onSelect={vi.fn()} />)
    await user.keyboard('{Meta>}k{/Meta}')
    expect(screen.getByRole('dialog', { name: 'Command palette' })).toBeInTheDocument()
  })

  it('filters results as the admin types', async () => {
    const user = userEvent.setup()
    render(<CommandPalette onSelect={vi.fn()} />)
    await user.keyboard('{Control>}k{/Control}')
    await user.type(screen.getByLabelText('Search pages'), 'prompt optimization')
    expect(screen.getByRole('option', { name: /Prompt Optimization/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Pilot Metrics/ })).not.toBeInTheDocument()
  })

  it('shows an empty state for a query matching nothing', async () => {
    const user = userEvent.setup()
    render(<CommandPalette onSelect={vi.fn()} />)
    await user.keyboard('{Control>}k{/Control}')
    await user.type(screen.getByLabelText('Search pages'), 'zzzznonexistent')
    expect(screen.getByText('No matching pages.')).toBeInTheDocument()
  })

  it('clicking a result calls onSelect with the real key and closes the palette', async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(<CommandPalette onSelect={onSelect} />)
    await user.keyboard('{Control>}k{/Control}')
    await user.type(screen.getByLabelText('Search pages'), 'pilot metrics')
    await user.click(screen.getByRole('option', { name: /Pilot Metrics/ }))
    expect(onSelect).toHaveBeenCalledWith('Pilot Metrics')
    expect(screen.queryByRole('dialog', { name: 'Command palette' })).not.toBeInTheDocument()
  })

  it('Enter selects the currently active result', async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(<CommandPalette onSelect={onSelect} />)
    await user.keyboard('{Control>}k{/Control}')
    await user.type(screen.getByLabelText('Search pages'), 'pilot metrics')
    await user.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledWith('Pilot Metrics')
  })

  it('Escape closes the palette', async () => {
    const user = userEvent.setup()
    render(<CommandPalette onSelect={vi.fn()} />)
    await user.keyboard('{Control>}k{/Control}')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Command palette' })).not.toBeInTheDocument()
  })
})
