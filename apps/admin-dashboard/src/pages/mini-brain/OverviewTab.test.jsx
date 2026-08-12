import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OverviewTab from './OverviewTab.jsx'

const STATUS = { enabled: true, runtime_status: 'running', health: { status: 'healthy' } }
const VERSION = { module_version: '1.0.0', phase: 'MB-01' }

describe('OverviewTab', () => {
  it('shows a loading skeleton until both status and version have loaded', () => {
    render(<OverviewTab status={null} version={null} busy={false} toggle={vi.fn()} runHealthCheck={vi.fn()} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(screen.queryByText('Enabled')).not.toBeInTheDocument()
  })

  it('renders real status/version fields once loaded', () => {
    render(<OverviewTab status={STATUS} version={VERSION} busy={false} toggle={vi.fn()} runHealthCheck={vi.fn()} />)
    expect(screen.getByText('Enabled').closest('article')).toHaveTextContent('true')
    expect(screen.getByText('Runtime status').closest('article')).toHaveTextContent('running')
    expect(screen.getByText('Health').closest('article')).toHaveTextContent('healthy')
    expect(screen.getByText('Version').closest('article')).toHaveTextContent('1.0.0')
    expect(screen.getByText('Phase').closest('article')).toHaveTextContent('MB-01')
  })

  it('calls toggle when the enable/disable button is clicked, labeled by current status', async () => {
    const user = userEvent.setup()
    const toggle = vi.fn()
    render(<OverviewTab status={STATUS} version={VERSION} busy={false} toggle={toggle} runHealthCheck={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Disable Brud Mini Brain' }))
    expect(toggle).toHaveBeenCalled()
  })

  it('shows the enable label when disabled, and disables the button while busy', () => {
    render(<OverviewTab status={{ ...STATUS, enabled: false }} version={VERSION} busy={true} toggle={vi.fn()} runHealthCheck={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Enable Brud Mini Brain' })).toBeDisabled()
  })

  it('calls runHealthCheck when clicked', async () => {
    const user = userEvent.setup()
    const runHealthCheck = vi.fn()
    render(<OverviewTab status={STATUS} version={VERSION} busy={false} toggle={vi.fn()} runHealthCheck={runHealthCheck} />)
    await user.click(screen.getByRole('button', { name: 'Run health check' }))
    expect(runHealthCheck).toHaveBeenCalled()
  })
})
